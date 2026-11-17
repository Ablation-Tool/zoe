from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import wave

from PIL import Image, ImageDraw, ImageFont
from zoe_autonomy.actuation import ActuationPolicy
from zoe_autonomy.capabilities import (
    BrowserAutomation,
    ComputeRunner,
    ConnectedServices,
    InstrumentRegistry,
    JobScheduler,
    MCPClient,
    MediaTools,
    Notifier,
    ResearchConnector,
    ResearchMemory,
)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/browser"):
            body = b"<html><title>Dynamic Zoe</title><body>Loading<script>document.body.innerText='JavaScript ready'</script></body></html>"
            content_type = "text/html"
        elif self.path.startswith("/research"):
            body = json.dumps({"message": {"items": [{"title": ["Test Research"], "DOI": "10.0000/test", "URL": "https://example.com/research", "publisher": "Example"}]}}).encode()
            content_type = "application/json"
        elif self.path.startswith("/service"):
            if self.headers.get("Authorization") != "Bearer service-secret":
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps({"connected": True}).encode()
            content_type = "application/json"
        elif self.path.startswith("/acp"):
            body = json.dumps({"protocol": "acp", "agents": ["owned-agent"]}).encode()
            content_type = "application/json"
        else:
            body = b"ok"
            content_type = "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps({"received": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class CapabilityCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.actuation = ActuationPolicy(self.root / "actuation")
        self.actuation.enable(["all"], owner_approved=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def test_01_real_browser_javascript_and_screenshot(self):
        output = self.root / "browser.png"
        result = BrowserAutomation().browse(self.base + "/browser", output, headless=False)
        self.assertEqual(result["title"], "Dynamic Zoe")
        self.assertIn("JavaScript ready", result["text"])
        self.assertTrue(result["javascript_executed"])
        self.assertTrue(output.is_file())

    def test_02_research_connector_and_citations(self):
        connector = ResearchConnector(self.actuation, {"crossref": self.base + "/research"})
        result = connector.search("crossref", "test", 5)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["records"][0]["doi"], "10.0000/test")
        self.assertTrue(result["audit_hash"])

    def test_03_persistent_memory_contradictions_and_search(self):
        memory = ResearchMemory(self.root / "memory.sqlite")
        source = memory.add_source("Evidence", "Accessible volume measures breadth", "https://example.com/source")
        self.assertEqual(source, memory.add_source("Evidence", "Accessible volume measures breadth"))
        first = memory.add_claim("Breadth is correctness", source)
        second = memory.add_claim("Breadth is not correctness", source)
        memory.contradict(first, second, "The repository separates breadth and correctness")
        self.assertEqual(len(memory.search("Breadth")["claims"]), 2)
        exported = memory.export()
        self.assertEqual(len(exported["sources"]), 1)
        self.assertEqual(len(exported["contradictions"]), 1)

    def test_04_connected_service_and_acp(self):
        os.environ["ZOE_SERVICE_KEY"] = "service-secret"
        try:
            services = ConnectedServices(self.actuation)
            result = services.request(self.base + "/service", "ZOE_SERVICE_KEY")
            self.assertTrue(result["succeeded"])
            self.assertTrue(result["document"]["connected"])
            protocol = services.request(self.base + "/acp")
            self.assertEqual(protocol["document"]["agents"], ["owned-agent"])
        finally:
            os.environ.pop("ZOE_SERVICE_KEY", None)

    def test_05_scheduled_job_executes_and_becomes_resumable(self):
        scheduler = JobScheduler(self.root / "jobs.json")
        scheduler.add("harmless", [sys.executable, "-c", "print('job-ok')"])
        results = scheduler.run_due()
        self.assertEqual(results[0]["result"]["stdout"].strip(), "job-ok")
        self.assertEqual(scheduler.run_due(), [])
        self.assertEqual(scheduler.status()[0]["status"], "completed")

    def test_06_compute_resource_evidence(self):
        result = ComputeRunner().run([sys.executable, "-c", "print(sum(range(100)))"])
        self.assertTrue(result["succeeded"])
        self.assertEqual(result["stdout"].strip(), "4950")
        self.assertIn("wall_seconds", result)
        self.assertIn("available", ComputeRunner().gpu())

    def test_07_mcp_initialize_list_and_call(self):
        server = self.root / "mcp_server.py"
        server.write_text("""
import json,sys
for line in sys.stdin:
    message=json.loads(line)
    if 'id' not in message: continue
    method=message['method']
    if method=='initialize': result={'protocolVersion':'2025-03-26','serverInfo':{'name':'mock','version':'1'}}
    elif method=='tools/list': result={'tools':[{'name':'echo','description':'echo'}]}
    elif method=='tools/call': result={'content':[{'type':'text','text':message['params']['arguments']['text']}]}
    else: result={}
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}),flush=True)
""", encoding="utf-8")
        with MCPClient([sys.executable, str(server)], timeout=10) as client:
            client.initialize()
            client.initialized()
            self.assertEqual(client.list_tools()["tools"][0]["name"], "echo")
            result = client.call_tool("echo", {"text": "protocol-ok"})
            self.assertEqual(result["content"][0]["text"], "protocol-ok")

    def test_08_desktop_and_webhook_notifications(self):
        notifier = Notifier(self.actuation)
        desktop = notifier.desktop("test", executable="/bin/echo")
        self.assertTrue(desktop["succeeded"])
        webhook = notifier.webhook(self.base + "/webhook", "zoe-notification")
        self.assertEqual(webhook["result"]["status"], 200)

    def test_09_image_wav_ocr_pdf_and_video_media(self):
        media = MediaTools(self.actuation)
        image_path = self.root / "text.png"
        image = Image.new("RGB", (500, 160), "white")
        draw = ImageDraw.Draw(image)
        draw.text((30, 35), "ZOE", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80), fill="black")
        image.save(image_path)
        self.assertEqual(media.image_info(image_path)["width"], 500)
        self.assertIn("ZOE", media.ocr(image_path).upper())
        wav_path = self.root / "tone.wav"
        with wave.open(str(wav_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(index / 10))) for index in range(4000)))
        self.assertAlmostEqual(media.wav_info(wav_path)["duration_seconds"], .5)
        stream = b"BT /F1 18 Tf 72 720 Td (Zoe Autonomy) Tj ET"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ]
        document = bytearray(b"%PDF-1.4\n")
        offsets = []
        for number, item in enumerate(objects, 1):
            offsets.append(len(document))
            document.extend(f"{number} 0 obj\n".encode() + item + b"\nendobj\n")
        xref = len(document)
        document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        document.extend(b"0000000000 65535 f \n")
        for offset in offsets:
            document.extend(f"{offset:010d} 00000 n \n".encode())
        document.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        paper = self.root / "sample.pdf"
        paper.write_bytes(document)
        self.assertIn("Zoe Autonomy", media.pdf_text(paper))
        video = self.root / "sample.mp4"
        subprocess.run([
            "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "testsrc=size=64x64:rate=1:duration=1", "-pix_fmt", "yuv420p", "-y", str(video),
        ], check=True)
        frame = media.video_frame(video, self.root / "frame.png")
        self.assertTrue(frame.is_file())

    def test_10_simulated_and_virtual_serial_instruments(self):
        registry = InstrumentRegistry(self.root / "instruments.json", self.actuation)
        registry.add_simulator("sim", {"*IDN?": "ZOE-SIM"})
        result = registry.execute("sim", "*IDN?")
        self.assertEqual(result["response"], "ZOE-SIM")
        import pty
        import tty
        master, slave = pty.openpty()
        tty.setraw(master)
        tty.setraw(slave)
        registry.add_serial("serial", os.ttyname(slave))
        def responder():
            import select
            ready, _, _ = select.select([master], [], [], 2)
            if ready:
                os.read(master, 32)
                os.write(master, b"OK42")
        thread = threading.Thread(target=responder)
        thread.start()
        try:
            response = registry.execute("serial", "READ", "1", read_bytes=4)
            self.assertEqual(response["response_text"], "OK42")
        finally:
            thread.join(timeout=3)
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
