"""Local On-Machine Dorothy Brain Library Trainer & FTS5 Retriever (100% Private Local).

Trains and indexes the user's private local Dorothy Brain Library (135 O'Reilly books across
6 pillars, 5,951 chapters, 66,127 figure catalog entries, and 44 NIRMT Textile Engineering PDFs)
into a private local SQLite FTS5 store outside the public git repository (`~/.zoe/`).

Strict Copyright & Constitutional Boundaries (`CONSTITUTION.md`):
  - Zero copyrighted book contents, figures, or PDFs are ever stored in this source file or
    committed to the public repository.
  - All discovery uses `Path.home()` or `ZOE_DOROTHY_LIBRARY_DIR`, degrading cleanly to an
    empty unavailable status on machines where the private library is absent.
  - `cloud_tokens_used`: 0, `sentience_claimed`: False, `clinical_action_authorized`: False.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Sequence
from urllib.parse import unquote, urlparse

DEFAULT_DB_PATH = Path.home() / ".zoe" / "dorothy_local_library.sqlite"

PILLAR_MANIFEST: Sequence[Dict[str, Any]] = (
    {
        "id": "00-human-brain",
        "label": "00 Human Brain & Neuroimaging",
        "books": 33,
        "size": "696 MB",
        "folder": "captures/human-brain-books/",
    },
    {
        "id": "01-science-imaging",
        "label": "01 Science & Medical Imaging",
        "books": 20,
        "size": "1.0 GB",
        "folder": "captures/dorothy-brain-library/01-science-imaging/",
    },
    {
        "id": "02-3d-modeling",
        "label": "02 3D Modeling & Graphics",
        "books": 26,
        "size": "1.6 GB",
        "folder": "captures/dorothy-brain-library/02-3d-modeling/",
    },
    {
        "id": "03-video-game-design",
        "label": "03 Video Game Design & Engines",
        "books": 24,
        "size": "1.9 GB",
        "folder": "captures/dorothy-brain-library/03-video-game-design/",
    },
    {
        "id": "04-autocad-cad",
        "label": "04 AutoCAD & Engineering CAD",
        "books": 19,
        "size": "1.1 GB",
        "folder": "captures/dorothy-brain-library/04-autocad-cad/",
    },
    {
        "id": "05-biomechanics-textiles",
        "label": "05 Biomechanics & Smart Textiles",
        "books": 13,
        "size": "438 MB",
        "folder": "captures/dorothy-brain-library/05-biomechanics-textiles/",
    },
    {
        "id": "nirmt-textile-pdfs",
        "label": "NIRMT Textile Engineering PDFs",
        "books": 44,
        "size": "698 MB",
        "folder": "captures/nirmt-textile-engineering-ebooks/",
    },
)

DESKTOP_PORTALS: Sequence[Dict[str, str]] = (
    {"label": "Visual Library Portal (135 books + 44 PDFs)", "path": "Desktop/Dorothy Brain Library/index.html"},
    {"label": "All 6 Book Folders Together", "path": "Desktop/Dorothy Brain Library/books/"},
    {"label": "44 NIRMT Textile Engineering PDFs (698 MB)", "path": "Desktop/Dorothy Brain Library/nirmt-textile-ebooks/"},
    {"label": "66,127 Consolidated Book Figures", "path": "Desktop/Dorothy Brain Library/images/"},
    {"label": "3D Brain + 5,951-Chapter Search & Vault", "path": "Desktop/Dorothy Brain Observatory/index.html"},
)


class _TextExtractor(HTMLParser):
    """Lightweight stdlib HTML-to-text extractor skipping script/style blocks."""

    def __init__(self, max_chars: int = 3200) -> None:
        super().__init__()
        self._skip = 0
        self._max = max_chars
        self._parts: List[str] = []
        self._len = 0

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        if tag in {"script", "style", "svg", "nav"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "nav"} and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip > 0 or self._len >= self._max:
            return
        chunk = " ".join(data.split())
        if chunk:
            self._parts.append(chunk)
            self._len += len(chunk) + 1

    def text(self) -> str:
        return " ".join(self._parts)[: self._max]


def _extract_html_excerpt(file_url_or_path: str, max_chars: int = 2800) -> str:
    if not file_url_or_path:
        return ""
    raw = file_url_or_path
    if raw.startswith("file://"):
        raw = unquote(urlparse(raw).path)
    path = Path(raw)
    if not path.is_file() and path.parent.suffix.lower() in {".html", ".htm"}:
        path = path.parent.parent / path.name
    if not path.is_file():
        return ""
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")[:48000]
    except OSError:
        return ""
    parser = _TextExtractor(max_chars=max_chars)
    try:
        parser.feed(html)
    except Exception:
        return ""
    return parser.text()


def _parse_js_assignment(path: Path, open_char: str) -> Any:
    text = path.read_text(encoding="utf-8")
    idx = text.index(open_char)
    return json.loads(text[idx:].rstrip(";\r\n "))


def _resolve_local_dirs() -> Dict[str, Path]:
    env_lib = os.environ.get("ZOE_DOROTHY_LIBRARY_DIR", "").strip()
    home = Path.home()
    return {
        "library": Path(env_lib) if env_lib else home / "Desktop" / "Dorothy Brain Library",
        "observatory": home / "Desktop" / "Dorothy Brain Observatory",
        "captures": home / "captures",
    }


def library_overview_text() -> str:
    """Return a clean human-readable map of the local Dorothy Brain Library (zero copyrighted text)."""
    lines = [
        "Dorothy Brain Local Research Library (135 O'Reilly books ~6.7 GB + 44 NIRMT PDFs 698 MB, 5,951 chapters, 66,127 figures; 100% local on your workstation, never uploaded to public GitHub):",
        "Desktop Portals:",
    ]
    for item in DESKTOP_PORTALS:
        lines.append(f"- {item['label']}: {item['path']}")
    lines.append("Source Folders (captures/):")
    for p in PILLAR_MANIFEST:
        lines.append(f"- {p['label']} ({p['books']} items, {p['size']}): {p['folder']}")
    return "\n".join(lines)


class DorothyLocalLibraryIndex:
    """Private local SQLite FTS5 trainer & fast retriever for the 135-book + 44-PDF library."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH).expanduser().resolve()
        self.dirs = _resolve_local_dirs()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
                kind,
                pillar,
                book_title,
                chapter_title,
                year,
                publisher,
                local_path,
                body,
                tokenize='porter unicode61'
            );
            """
        )

    def train_from_local_disk(self, *, extract_chapter_text: bool = True, max_excerpt_chars: int = 2400) -> Dict[str, Any]:
        """Scan local Desktop/Dorothy Brain Observatory catalogs and train the local FTS5 index."""
        obs_data = self.dirs["observatory"] / "data"
        vault_js = obs_data / "library_vault.js"
        chapters_js = obs_data / "library_chapters.js"
        if not vault_js.is_file():
            return {"ok": False, "reason": "local_library_not_present", "books_indexed": 0, "chapters_indexed": 0}

        vault = _parse_js_assignment(vault_js, "{")
        chapters = _parse_js_assignment(chapters_js, "[") if chapters_js.is_file() else []
        books = list(vault.get("books") or [])
        nirmt_pdfs = list(vault.get("nirmtPdfs") or [])
        figures_count = len(vault.get("images") or [])

        conn = self._connect()
        try:
            self._ensure_schema(conn)
            conn.execute("DELETE FROM docs")
            rows: List[tuple[str, str, str, str, str, str, str, str]] = []
            for b in books:
                rows.append((
                    "book",
                    str(b.get("pillar", "")),
                    str(b.get("title", "")),
                    f"Book Overview ({b.get('ch', 0)} chapters, {b.get('img', 0)} figures)",
                    str(b.get("year", "")),
                    str(b.get("pub", "")),
                    str(b.get("href", "")),
                    f"{b.get('title', '')} {b.get('pillar', '')} {b.get('pub', '')} ISBN {b.get('isbn', '')}",
                ))

            text_extracted = 0
            for ch in chapters:
                if not isinstance(ch, list) or len(ch) < 3:
                    continue
                b_idx = int(ch[0])
                book = books[b_idx] if 0 <= b_idx < len(books) else {}
                ch_title = str(ch[1])
                ch_href = str(ch[2])
                body = _extract_html_excerpt(ch_href, max_chars=max_excerpt_chars) if extract_chapter_text else ""
                if body:
                    text_extracted += 1
                rows.append((
                    "chapter",
                    str(book.get("pillar", "")),
                    str(book.get("title", "")),
                    ch_title,
                    str(book.get("year", "")),
                    str(book.get("pub", "")),
                    ch_href,
                    body or f"{book.get('title', '')} {ch_title}",
                ))

            for pdf in nirmt_pdfs:
                label = str(pdf.get("label", ""))
                rel = str(pdf.get("file", ""))
                rows.append((
                    "nirmt_pdf",
                    "nirmt-textile-pdfs",
                    label,
                    f"NIRMT Textile Engineering PDF ({pdf.get('mb', '')} MB)",
                    "",
                    "NIRMT",
                    rel,
                    f"{label} textile biomechanics engineering pdf",
                ))

            conn.executemany(
                "INSERT INTO docs(kind, pillar, book_title, chapter_title, year, publisher, local_path, body) VALUES (?,?,?,?,?,?,?,?)",
                rows,
            )
            stats = {
                "books_indexed": len(books),
                "chapters_indexed": len(chapters),
                "chapters_fulltext_extracted": text_extracted,
                "nirmt_pdfs_indexed": len(nirmt_pdfs),
                "figures_cataloged": figures_count,
                "total_fts_docs": len(rows),
            }
            for k, v in stats.items():
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (k, str(v)))
            conn.commit()
            return {"ok": True, "db_path": str(self.db_path), **stats}
        finally:
            conn.close()

    def status(self) -> Dict[str, Any]:
        """Return non-sensitive metadata counts for the local trained index."""
        out: Dict[str, Any] = {
            "available": False,
            "db_exists": self.db_path.is_file(),
            "pillars_count": len(PILLAR_MANIFEST),
            "desktop_portals_count": len(DESKTOP_PORTALS),
            "copyrighted_files_in_public_repo": False,
        }
        if not self.db_path.is_file():
            return out
        conn = self._connect()
        try:
            self._ensure_schema(conn)
            for row in conn.execute("SELECT key, value FROM meta"):
                k = str(row["key"])
                v = str(row["value"])
                out[k] = int(v) if v.isdigit() else v
            out["available"] = int(out.get("total_fts_docs", 0)) > 0
            return out
        except sqlite3.Error:
            return out
        finally:
            conn.close()

    def search(self, query: str, *, limit: int = 5) -> List[Dict[str, Any]]:
        """Query the trained local FTS5 index across all 135 books, 5,951 chapters, and 44 NIRMT PDFs."""
        if not self.db_path.is_file():
            return []
        tokens = [t for t in re.findall(r"[a-zA-Z0-9]{2,}", query.lower()) if t not in _QUERY_STOPWORDS]
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{t}"' for t in tokens[:8])
        conn = self._connect()
        try:
            self._ensure_schema(conn)
            cur = conn.execute(
                """
                SELECT kind, pillar, book_title, chapter_title, year, publisher,
                       snippet(docs, 7, '', '', ' ... ', 26) AS excerpt,
                       bm25(docs) AS rank
                FROM docs
                WHERE docs MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, max(1, min(int(limit), 12))),
            )
            hits: List[Dict[str, Any]] = []
            for r in cur.fetchall():
                hits.append({
                    "kind": str(r["kind"]),
                    "pillar": str(r["pillar"]),
                    "book_title": str(r["book_title"]),
                    "chapter_title": str(r["chapter_title"]),
                    "year": str(r["year"]),
                    "publisher": str(r["publisher"]),
                    "excerpt": " ".join(str(r["excerpt"] or "").split())[:260],
                })
            return hits
        except sqlite3.Error:
            return []
        finally:
            conn.close()


_QUERY_STOPWORDS = frozenset({
    "what", "where", "when", "which", "who", "how", "why", "does", "do", "did", "can", "could",
    "would", "should", "the", "and", "for", "with", "from", "that", "this", "these", "those",
    "about", "into", "your", "have", "has", "are", "was", "were", "tell", "show", "find",
    "search", "look", "please", "zoe", "book", "books", "chapter", "chapters", "library",
})
