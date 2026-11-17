from __future__ import annotations

from datetime import datetime, timedelta, timezone
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
import xml.etree.ElementTree as ET

from .actuation import ActuationPolicy, timestamp


class BrowserAutomation:
    def __init__(self, runner=None):
        self.runner = Path(runner or os.environ.get("ZOE_PLAYWRIGHT_RUNNER", Path.home() / ".agents/skills/playwright-skill/run.js"))

    def browse(self, url, screenshot=None, headless=False, timeout=60):
        if not self.runner.is_file():
            raise ValueError("Playwright runner is unavailable; set ZOE_PLAYWRIGHT_RUNNER")
        parsed = urlparse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("browser automation requires an HTTP(S) URL")
        screenshot = Path(screenshot).expanduser().resolve() if screenshot else None
        if screenshot and screenshot.exists():
            raise FileExistsError(f"browser screenshot already exists: {screenshot}")
        script = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({headless: process.env.ZOE_BROWSER_HEADLESS === '1'});
  try {
    const page = await browser.newPage();
    await page.goto(process.env.TARGET_URL, {waitUntil: 'domcontentloaded', timeout: 60000});
    const result = {
      url: page.url(),
      title: await page.title(),
      text: (await page.locator('body').innerText()).slice(0, 12000),
      links: await page.locator('a').evaluateAll(nodes => nodes.slice(0, 100).map(node => ({text: node.innerText, href: node.href}))),
      javascript_executed: await page.evaluate(() => true)
    };
    if (process.env.SCREENSHOT_PATH) {
      await page.screenshot({path: process.env.SCREENSHOT_PATH, fullPage: true});
      result.screenshot = process.env.SCREENSHOT_PATH;
    }
    console.log('ZOE_BROWSER_RESULT=' + JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
"""
        with tempfile.TemporaryDirectory(prefix="zoe-browser-") as directory:
            script_path = Path(directory) / "browse.js"
            script_path.write_text(script, encoding="utf-8")
            environment = os.environ.copy()
            environment.update({
                "TARGET_URL": url,
                "ZOE_BROWSER_HEADLESS": "1" if headless else "0",
                "SCREENSHOT_PATH": str(screenshot) if screenshot else "",
            })
            result = subprocess.run(
                ["node", str(self.runner), str(script_path)],
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        if result.returncode:
            raise RuntimeError(f"browser automation failed: {result.stderr[-2000:]}")
        line = next((line for line in result.stdout.splitlines() if line.startswith("ZOE_BROWSER_RESULT=")), None)
        if line is None:
            raise RuntimeError("browser returned no structured result")
        report = json.loads(line.split("=", 1)[1])
        if screenshot and not screenshot.is_file():
            raise RuntimeError("browser screenshot was not created")
        return report


class ResearchConnector:
    ENDPOINTS = {
        "crossref": "https://api.crossref.org/works",
        "arxiv": "https://export.arxiv.org/api/query",
        "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    }

    def __init__(self, policy=None, endpoints=None):
        self.policy = policy or ActuationPolicy()
        self.endpoints = {**self.ENDPOINTS, **(endpoints or {})}

    def request(self, url):
        response = self.policy.execute({"kind": "network", "url": url, "method": "GET", "timeout": 30})
        return response["result"]["body"], response["audit_hash"]

    def search(self, provider, query, limit=5):
        if provider not in self.endpoints:
            raise ValueError("research provider must be crossref, arxiv, or pubmed")
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("research query must contain 1-1000 characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
            raise ValueError("research result limit must be from 1 to 25")
        parameters = {"rows": str(limit)} if provider == "crossref" else {"count": str(limit)} if provider == "arxiv" else {"retmax": str(limit), "retmode": "json"}
        if provider == "crossref":
            parameters["query.bibliographic"] = query
        elif provider == "arxiv":
            parameters.update({"search_query": f"all:{query}", "max_results": str(limit)})
            parameters.pop("count", None)
        else:
            parameters["db"] = "pubmed"
            parameters["term"] = query
        url = self.endpoints[provider] + "?" + urlparse.urlencode(parameters)
        body, audit_hash = self.request(url)
        if provider == "crossref":
            document = json.loads(body)
            records = [{
                "title": " ".join(item.get("title", [])),
                "doi": item.get("DOI"),
                "url": item.get("URL"),
                "publisher": item.get("publisher"),
            } for item in document.get("message", {}).get("items", [])]
        elif provider == "arxiv":
            root = ET.fromstring(body)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}
            records = [{
                "title": " ".join((entry.findtext("atom:title", "", namespace)).split()),
                "id": entry.findtext("atom:id", "", namespace),
                "summary": " ".join((entry.findtext("atom:summary", "", namespace)).split()),
            } for entry in root.findall("atom:entry", namespace)]
        else:
            document = json.loads(body)
            identifiers = document.get("esearchresult", {}).get("idlist", [])
            records = [{"pmid": identifier, "url": f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"} for identifier in identifiers]
        return {"provider": provider, "query": query, "records": records, "count": len(records), "audit_hash": audit_hash}

    def feed(self, url):
        body, audit_hash = self.request(url)
        root = ET.fromstring(body)
        records = []
        for item in root.findall(".//item")[:25]:
            records.append({"title": item.findtext("title", ""), "link": item.findtext("link", ""), "description": item.findtext("description", "")})
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", namespace)[:25]:
            records.append({"title": entry.findtext("atom:title", "", namespace), "link": entry.findtext("atom:id", "", namespace), "description": entry.findtext("atom:summary", "", namespace)})
        return {"records": records, "count": len(records), "audit_hash": audit_hash}

    def sitemap(self, url):
        body, audit_hash = self.request(url)
        root = ET.fromstring(body)
        locations = [element.text for element in root.findall(".//{*}loc") if element.text]
        return {"urls": locations[:1000], "count": len(locations), "audit_hash": audit_hash}


class ResearchMemory:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as database:
            database.executescript("""
                CREATE TABLE IF NOT EXISTS sources(
                    id INTEGER PRIMARY KEY, url TEXT, title TEXT NOT NULL,
                    content TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL, created_utc TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS claims(
                    id INTEGER PRIMARY KEY, statement TEXT NOT NULL,
                    status TEXT NOT NULL, source_id INTEGER, created_utc TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id));
                CREATE TABLE IF NOT EXISTS contradictions(
                    id INTEGER PRIMARY KEY, claim_a INTEGER NOT NULL, claim_b INTEGER NOT NULL,
                    reason TEXT NOT NULL, created_utc TEXT NOT NULL,
                    FOREIGN KEY(claim_a) REFERENCES claims(id), FOREIGN KEY(claim_b) REFERENCES claims(id));
            """)

    @contextlib.contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def add_source(self, title, content, url=""):
        if not title.strip() or not content.strip() or len(content) > 10_000_000:
            raise ValueError("source title and bounded content are required")
        identity = hashlib.sha256(content.encode()).hexdigest()
        with self.connect() as database:
            existing = database.execute("SELECT id FROM sources WHERE sha256=?", (identity,)).fetchone()
            if existing:
                return existing["id"]
            cursor = database.execute(
                "INSERT INTO sources(url,title,content,sha256,created_utc) VALUES(?,?,?,?,?)",
                (url, title, content, identity, timestamp()),
            )
            return cursor.lastrowid

    def add_claim(self, statement, source_id=None, status="open"):
        if status not in {"open", "supported", "rejected", "contradicted"} or not statement.strip():
            raise ValueError("claim statement and valid status are required")
        with self.connect() as database:
            cursor = database.execute(
                "INSERT INTO claims(statement,status,source_id,created_utc) VALUES(?,?,?,?)",
                (statement, status, source_id, timestamp()),
            )
            return cursor.lastrowid

    def contradict(self, claim_a, claim_b, reason):
        with self.connect() as database:
            database.execute("UPDATE claims SET status='contradicted' WHERE id IN (?,?)", (claim_a, claim_b))
            cursor = database.execute(
                "INSERT INTO contradictions(claim_a,claim_b,reason,created_utc) VALUES(?,?,?,?)",
                (claim_a, claim_b, reason, timestamp()),
            )
            return cursor.lastrowid

    def search(self, query, limit=10):
        pattern = f"%{query}%"
        with self.connect() as database:
            sources = [dict(row) for row in database.execute(
                "SELECT id,url,title,sha256,created_utc FROM sources WHERE title LIKE ? OR content LIKE ? LIMIT ?",
                (pattern, pattern, limit),
            )]
            claims = [dict(row) for row in database.execute(
                "SELECT id,statement,status,source_id,created_utc FROM claims WHERE statement LIKE ? LIMIT ?",
                (pattern, limit),
            )]
        return {"sources": sources, "claims": claims}

    def export(self):
        with self.connect() as database:
            return {
                "sources": [dict(row) for row in database.execute("SELECT * FROM sources ORDER BY id")],
                "claims": [dict(row) for row in database.execute("SELECT * FROM claims ORDER BY id")],
                "contradictions": [dict(row) for row in database.execute("SELECT * FROM contradictions ORDER BY id")],
            }


class ConnectedServices:
    def __init__(self, actuation=None):
        self.actuation = actuation or ActuationPolicy()

    def request(self, url, token_env=None, method="GET", payload=None, timeout=30):
        if not self.actuation.enabled("network"):
            raise PermissionError("network actuation is not enabled")
        headers = {"Accept": "application/json", "User-Agent": "ZoeOneCapabilities/1.0"}
        if token_env:
            credential = os.environ.get(token_env)
            if not credential:
                raise ValueError(f"credential environment variable is not set: {token_env}")
            headers["Authorization"] = f"Bearer {credential}"
        data = json.dumps(payload).encode() if payload is not None else None
        request = urlrequest.Request(url, data=data, method=method, headers=headers)
        if data:
            request.add_header("Content-Type", "application/json")
        try:
            response = urlrequest.urlopen(request, timeout=timeout)
        except urlerror.HTTPError as error:
            response = error
        with response:
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise RuntimeError("connected service response exceeds 1 MiB")
            document = json.loads(body.decode("utf-8")) if body else None
            return {"status": response.status, "succeeded": 200 <= response.status < 300, "document": document}

    def github(self, path, timeout=30):
        if not self.actuation.enabled("host"):
            raise PermissionError("host actuation is not enabled")
        result = subprocess.run(
            ["gh", "api", path], capture_output=True, text=True, timeout=timeout, check=False,
        )
        if result.returncode:
            raise RuntimeError(f"GitHub API failed: {result.stderr[-1000:]}")
        return json.loads(result.stdout) if result.stdout.strip() else None


class JobScheduler:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()

    def _load(self):
        if not self.path.is_file():
            return {"schema_version": 1, "jobs": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, document):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def add(self, identifier, argv, interval_seconds=0, timeout=60):
        if not identifier or not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
            raise ValueError("job id and nonempty argv are required")
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) or not 0 <= interval_seconds <= 31_536_000:
            raise ValueError("job interval must be from zero to one year")
        document = self._load()
        if any(job["id"] == identifier for job in document["jobs"]):
            raise FileExistsError(f"job already exists: {identifier}")
        job = {
            "id": identifier,
            "argv": argv,
            "interval_seconds": interval_seconds,
            "timeout": timeout,
            "attempts": 0,
            "status": "scheduled",
            "next_run_utc": timestamp(),
            "last_result": None,
        }
        document["jobs"].append(job)
        self._save(document)
        return job

    def run_due(self):
        document = self._load()
        results = []
        now = datetime.now(timezone.utc)
        for job in document["jobs"]:
            if job["next_run_utc"] is None or datetime.fromisoformat(job["next_run_utc"].replace("Z", "+00:00")) > now:
                continue
            started = time.monotonic()
            try:
                result = subprocess.run(job["argv"], capture_output=True, text=True, timeout=job["timeout"], check=False)
                output = {
                    "returncode": result.returncode,
                    "stdout": result.stdout[-4096:],
                    "stderr": result.stderr[-4096:],
                }
                job["status"] = "completed" if result.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                output = {"returncode": None, "stdout": "", "stderr": "timeout"}
                job["status"] = "failed"
            job["attempts"] += 1
            job["last_result"] = {**output, "elapsed_seconds": time.monotonic() - started, "finished_utc": timestamp()}
            if job["interval_seconds"]:
                job["next_run_utc"] = (now + timedelta(seconds=job["interval_seconds"])).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                job["status"] = "scheduled"
            else:
                job["next_run_utc"] = None
            results.append({"id": job["id"], "status": job["status"], "result": job["last_result"]})
        self._save(document)
        return results

    def status(self):
        return self._load()["jobs"]


class ComputeRunner:
    def run(self, argv, mode="local", image=None, timeout=120):
        if mode not in {"local", "container"}:
            raise ValueError("compute mode must be local or container")
        if not isinstance(argv, list) or not argv:
            raise ValueError("compute argv is required")
        command = list(argv)
        if mode == "container":
            runtime = shutil.which("docker") or shutil.which("podman")
            if not runtime or not image:
                raise ValueError("container compute requires Docker or Podman and an image")
            command = [runtime, "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "512m", image, *argv]
        import resource
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError("compute job timed out")
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return {
            "mode": mode,
            "returncode": process.returncode,
            "succeeded": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace")[-65536:],
            "stderr": stderr.decode("utf-8", errors="replace")[-65536:],
            "wall_seconds": time.monotonic() - started,
            "user_cpu_seconds": usage.ru_utime - before.ru_utime,
            "system_cpu_seconds": usage.ru_stime - before.ru_stime,
            "max_rss_kib": usage.ru_maxrss,
        }

    def gpu(self):
        executable = shutil.which("nvidia-smi")
        if not executable:
            return {"available": False, "reason": "nvidia-smi is unavailable"}
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        return {"available": result.returncode == 0, "devices": result.stdout.strip().splitlines(), "stderr": result.stderr}

    def jupyter(self, notebook, output, timeout=300):
        executable = shutil.which("jupyter")
        if not executable:
            raise ValueError("Jupyter is unavailable")
        output = Path(output).expanduser().resolve()
        if output.exists():
            raise FileExistsError(output)
        return self.run([
            executable, "nbconvert", "--to", "notebook", "--execute", str(notebook),
            "--output", output.name, "--output-dir", str(output.parent),
        ], timeout=timeout)


class MCPClient:
    def __init__(self, argv, timeout=30):
        self.timeout = timeout
        self.process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, start_new_session=True,
        )
        self.identifier = 0

    def _read_response(self, identifier):
        import select
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                break
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed its output")
            message = json.loads(line)
            if message.get("id") == identifier:
                if "error" in message:
                    raise RuntimeError(f"MCP error: {message['error']}")
                return message.get("result")
        raise TimeoutError("MCP response timed out")

    def _notify(self, method, params=None):
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n")
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.identifier += 1
        self.process.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": self.identifier, "method": method, "params": params or {},
        }) + "\n")
        self.process.stdin.flush()
        return self._read_response(self.identifier)

    def initialize(self):
        return self.request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "zoe-one", "version": "1"},
        })

    def initialized(self):
        self._notify("notifications/initialized")

    def list_tools(self):
        return self.request("tools/list")

    def call_tool(self, name, arguments=None):
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class AgentProtocolConnector:
    def __init__(self, services=None):
        self.services = services or ConnectedServices()

    def acp_discover(self, url):
        return self.services.request(url)


class Notifier:
    def __init__(self, actuation=None):
        self.actuation = actuation or ActuationPolicy()

    def desktop(self, message, executable=None):
        if not self.actuation.enabled("host"):
            raise PermissionError("host actuation is not enabled")
        command = executable or shutil.which("notify-send")
        if not command:
            raise ValueError("desktop notification command is unavailable")
        result = subprocess.run([command, "Zoe One", message], capture_output=True, text=True, timeout=10, check=False)
        return {"succeeded": result.returncode == 0, "returncode": result.returncode, "stderr": result.stderr}

    def webhook(self, url, message):
        response = self.actuation.execute({
            "kind": "network", "url": url, "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"text": message}), "timeout": 30,
        })
        return response

    def email(self, host, port, sender, recipients, subject, message, password_env, username=None, use_ssl=True):
        if not self.actuation.enabled("network"):
            raise PermissionError("network actuation is not enabled")
        import smtplib
        from email.message import EmailMessage
        password = os.environ.get(password_env)
        if not password:
            raise ValueError(f"email credential environment variable is not set: {password_env}")
        document = EmailMessage()
        document["From"] = sender
        document["To"] = ", ".join(recipients)
        document["Subject"] = subject
        document.set_content(message)
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_class(host, port, timeout=30) as connection:
            if username:
                connection.login(username, password)
            connection.send_message(document)
        return {"succeeded": True, "recipients": recipients, "subject": subject}


class MediaTools:
    def __init__(self, actuation=None):
        self.actuation = actuation or ActuationPolicy()

    def image_info(self, path):
        from PIL import Image
        path = Path(path).expanduser().resolve()
        with Image.open(path) as image:
            return {
                "path": str(path), "width": image.width, "height": image.height,
                "mode": image.mode, "format": image.format,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }

    def wav_info(self, path):
        import wave
        path = Path(path).expanduser().resolve()
        with wave.open(str(path), "rb") as audio:
            return {
                "path": str(path), "channels": audio.getnchannels(),
                "sample_width": audio.getsampwidth(), "sample_rate": audio.getframerate(),
                "frames": audio.getnframes(), "duration_seconds": audio.getnframes() / audio.getframerate(),
            }

    def _command(self, argv, timeout=120):
        if not self.actuation.enabled("host"):
            raise PermissionError("host actuation is not enabled")
        result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2000:])
        return result.stdout

    def ocr(self, path):
        executable = shutil.which("tesseract")
        if not executable:
            raise ValueError("Tesseract OCR is unavailable")
        return self._command([executable, str(path), "stdout"]).decode("utf-8", errors="replace")

    def pdf_text(self, path):
        executable = shutil.which("pdftotext")
        if not executable:
            raise ValueError("pdftotext is unavailable")
        return self._command([executable, str(path), "-"]).decode("utf-8", errors="replace")[:1_000_000]

    def video_frame(self, video, output, at_seconds=0):
        executable = shutil.which("ffmpeg")
        if not executable:
            raise ValueError("ffmpeg is unavailable")
        output = Path(output).expanduser().resolve()
        if output.exists():
            raise FileExistsError(output)
        self._command([
            executable, "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds),
            "-i", str(video), "-frames:v", "1", "-y", str(output),
        ])
        return output

    def speak(self, text, output):
        executable = shutil.which("espeak") or shutil.which("espeak-ng")
        if not executable:
            raise ValueError("espeak speech synthesis is unavailable")
        output = Path(output).expanduser().resolve()
        if output.exists():
            raise FileExistsError(output)
        data = self._command([executable, "--stdout", text])
        output.write_bytes(data)
        return output

    def transcribe(self, audio, output_dir):
        executable = shutil.which("whisper") or shutil.which("whisper-cli")
        if not executable:
            raise ValueError("Whisper transcription is unavailable")
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._command([executable, str(audio), "--output_dir", str(output_dir)])
        return output_dir


class InstrumentRegistry:
    def __init__(self, path, actuation=None):
        self.path = Path(path).expanduser().resolve()
        self.actuation = actuation or ActuationPolicy()

    def _load(self):
        if not self.path.is_file():
            return {"schema_version": 1, "instruments": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, document):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def add_simulator(self, name, responses):
        document = self._load()
        document["instruments"] = [item for item in document["instruments"] if item["name"] != name]
        document["instruments"].append({"name": name, "driver": "simulated", "responses": responses})
        self._save(document)
        return name

    def add_serial(self, name, device):
        document = self._load()
        document["instruments"] = [item for item in document["instruments"] if item["name"] != name]
        document["instruments"].append({"name": name, "driver": "serial", "device": device})
        self._save(document)
        return name

    def execute(self, name, command, payload="", read_bytes=0):
        instrument = next((item for item in self._load()["instruments"] if item["name"] == name), None)
        if instrument is None:
            raise ValueError(f"unknown instrument: {name}")
        if instrument["driver"] == "simulated":
            response = instrument["responses"].get(command)
            if response is None:
                raise ValueError(f"simulated instrument has no response for {command}")
            return {"driver": "simulated", "command": command, "response": response}
        request = f"{command} {payload}\n".encode()
        result = self.actuation.execute({
            "kind": "hardware", "device": instrument["device"],
            "payload_hex": request.hex(), "read_bytes": read_bytes, "timeout": 2,
        })
        result["response_text"] = bytes.fromhex(result["result"]["read_hex"]).decode("utf-8", errors="replace")
        return result
