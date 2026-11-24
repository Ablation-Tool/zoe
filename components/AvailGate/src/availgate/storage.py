"""Transactional sessions and disposable cache with separate retention."""

import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

from .config import paths
from .contracts import Problem, utc

CACHE_LIMIT = 16 * 1024 * 1024
SESSION_LIMIT = 64 * 1024 * 1024


def cache_key(operation, options):
    return hashlib.sha256(json.dumps([operation, options], sort_keys=True).encode()).hexdigest()


class Store:
    def __init__(self, directory=None):
        self.directory = directory or paths()[1]
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / "research.sqlite3"
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise Problem("storage_version", "Database was created by a newer AvailGate version.")
            db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, created REAL, expires REAL, data TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (name TEXT PRIMARY KEY, created TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, session TEXT REFERENCES sessions(name) ON DELETE CASCADE, created TEXT, kind TEXT, data TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS events_session ON events(session, id)")
            db.execute("PRAGMA user_version=1")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def cached(self, key):
        with self.connect() as db:
            row = db.execute("SELECT created, expires, data FROM cache WHERE key=?", (key,)).fetchone()
        if row is None or row[1] <= time.time():
            return None
        data = json.loads(row[2])
        retrieved = data.get("retrieved_at") or data.get("cache", {}).get("retrieved_at") or utc(row[0])
        observed = datetime.fromisoformat(retrieved).timestamp()
        return data, {"hit": True, "retrieved_at": retrieved,
                      "age_seconds": round(max(0, time.time() - observed), 2), "expires_at": utc(row[1])}

    def cache(self, key, value, ttl=86400):
        data = json.dumps(value, ensure_ascii=False)
        if len(data.encode()) > CACHE_LIMIT:
            return
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM cache WHERE expires<=? OR key=?", (now, key))
            size = db.execute("SELECT COALESCE(SUM(length(CAST(data AS BLOB))),0) FROM cache").fetchone()[0]
            while size + len(data.encode()) > CACHE_LIMIT:
                row = db.execute("SELECT key, length(CAST(data AS BLOB)) FROM cache ORDER BY created LIMIT 1").fetchone()
                db.execute("DELETE FROM cache WHERE key=?", (row[0],))
                size -= row[1]
            db.execute("INSERT INTO cache VALUES(?,?,?,?)", (key, now, now + ttl, data))

    def clear_cache(self):
        with self.connect() as db:
            return db.execute("DELETE FROM cache").rowcount

    @staticmethod
    def validate_name(name):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name):
            raise Problem("session_name", "Use 1–80 letters, digits, dots, dashes, or underscores, starting with a letter or digit.", invalid=True)

    def create(self, name):
        self.validate_name(name)
        try:
            with self.connect() as db:
                if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 1000:
                    raise Problem("storage_limit", "Session limit reached; delete an unneeded session.")
                db.execute("INSERT INTO sessions VALUES(?,?)", (name, utc()))
        except sqlite3.IntegrityError:
            raise Problem("session_exists", "A session with this name already exists.", invalid=True)
        return self.show(name)

    def require(self, name):
        self.validate_name(name)
        with self.connect() as db:
            if db.execute("SELECT 1 FROM sessions WHERE name=?", (name,)).fetchone() is None:
                raise Problem("session_missing", "Session does not exist; create it first.", invalid=True)

    def append(self, name, kind, value):
        self.require(name)
        data = json.dumps(value, ensure_ascii=False)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            size = db.execute("SELECT COALESCE(SUM(length(CAST(data AS BLOB))),0) FROM events").fetchone()[0]
            if size + len(data.encode()) > SESSION_LIMIT:
                raise Problem("storage_limit", "Saved research limit reached (64 MiB). Export and delete unneeded sessions.")
            db.execute("INSERT INTO events(session, created, kind, data) VALUES(?,?,?,?)", (name, utc(), kind, data))

    def list(self):
        with self.connect() as db:
            return [{"name": name, "created_at": created, "event_count": count} for name, created, count in
                    db.execute("SELECT s.name,s.created,count(e.id) FROM sessions s LEFT JOIN events e ON e.session=s.name GROUP BY s.name ORDER BY s.created")]

    def save_event(self, name, kind, value):
        """A storage failure must not discard a completed, possibly paid search."""
        try:
            self.append(name, kind, value)
            value["persistence"] = {"session": name, "saved": True}
        except (Problem, sqlite3.Error, OSError):
            value["persistence"] = {"session": name, "saved": False}
            value["warnings"].append("Research completed but could not be saved to the session. Export this response before retrying.")
            if value["status"] == "ok":
                value["status"] = "partial"

    def show(self, name):
        self.require(name)
        with self.connect() as db:
            created = db.execute("SELECT created FROM sessions WHERE name=?", (name,)).fetchone()[0]
            events = [{"id": index, "created_at": when, "kind": kind, "data": json.loads(data)}
                      for index, when, kind, data in db.execute(
                          "SELECT id,created,kind,data FROM events WHERE session=? ORDER BY id", (name,))]
        return {"name": name, "created_at": created, "events": events}

    def delete(self, name):
        self.require(name)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE name=?", (name,))
        return {"deleted": name, "recoverable": False}


def markdown(session):
    lines = [f"# Research: {session['name']}", "", f"Created: {session['created_at']}"]
    for event in session["events"]:
        value = event["data"]
        lines += ["", f"## {event['kind']} — {event['created_at']}", ""]
        if event["kind"] in ("note", "question"):
            lines += ["Agent/user-authored text:", "", *["> " + line for line in value["text"].splitlines()]]
        elif event["kind"] == "search":
            lines += [f"Query: {value['query']}", "", f"Status: {value['status']}", ""]
            for item in value["results"]:
                lines += [f"- {item['title']} — <{item['url']}>",
                          f"  Search snippet (unverified): {item['snippet']}"]
        elif event["kind"] == "read":
            doc = value.get("document")
            if not doc:
                lines += ["Read failed; see JSON export for diagnostics."]
                continue
            lines += [f"Source: <{doc['final_url']}>", "", f"Retrieved: {doc['retrieved_at']}",
                      f"Text hash: {doc['text_hash']}; truncated: {doc['truncated']}", "",
                      "Captured source text:", "", *["> " + line for line in doc["text"].splitlines()]]
    return "\n".join(lines) + "\n"
