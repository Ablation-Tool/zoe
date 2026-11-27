import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import gemseal
import gemseal_tripwire


@unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux inotify")
class TripwireTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.key = self.root / "private" / "vault.key"
        self.addCleanup(self.temporary.cleanup)

    def make_vault(self):
        return gemseal_tripwire.init_vault(self.vault, self.key)

    def test_init_creates_encrypted_canary_and_external_key(self):
        canary = self.make_vault()
        self.assertEqual(canary.read_bytes()[:8], b"GEMSEAL1")
        self.assertNotIn(b"This GEMSEAL canary", canary.read_bytes())
        self.assertEqual(len(self.key.read_bytes()), 32)
        self.assertNotIn(self.key, list(self.vault.iterdir()))

    def test_init_rejects_key_inside_vault(self):
        with self.assertRaises(gemseal_tripwire.TripwireError):
            gemseal_tripwire.init_vault(self.vault, self.vault / "vault.key")
        self.assertFalse(self.vault.exists())

    def test_init_rejects_invalid_canary_name(self):
        with self.assertRaises(gemseal_tripwire.TripwireError):
            gemseal_tripwire.init_vault(self.vault, self.key, "nested/canary.gemseal")
        self.assertFalse(self.vault.exists())

    def test_log_must_be_outside_vault(self):
        self.make_vault()
        watcher = gemseal_tripwire.TripwireWatcher(
            self.vault, self.vault / "audit.jsonl", alert_stream=io.StringIO()
        )
        self.addCleanup(watcher._close)
        with self.assertRaises(gemseal_tripwire.TripwireError):
            watcher.prepare()

    def test_real_open_publishes_json_event(self):
        canary = self.make_vault()
        log = self.root / "audit.jsonl"
        alerts = io.StringIO()
        watcher = gemseal_tripwire.TripwireWatcher(
            self.vault, log, once=True, dedup=0, alert_stream=alerts
        )
        errors = []
        thread = threading.Thread(target=self.run_watcher, args=(watcher, errors))
        thread.start()
        self.assertTrue(watcher.ready.wait(5), "watcher did not become ready")
        with canary.open("rb") as container:
            container.read(1)
        thread.join(5)
        self.assertFalse(thread.is_alive(), "watcher did not stop after one event")
        self.assertEqual(errors, [])
        records = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertTrue(records)
        self.assertEqual(records[0]["path"], str(canary))
        self.assertIn("open", records[0]["events"])
        self.assertIn("TRIPWIRE", alerts.getvalue())

    @staticmethod
    def run_watcher(watcher, errors):
        try:
            watcher.run()
        except Exception as error:
            errors.append(error)


if __name__ == "__main__":
    unittest.main()
