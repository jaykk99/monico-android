import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

# Stub toga (no Android Toga on desktop); only the Microdot server is exercised.
toga = types.ModuleType("toga")
toga.style = types.ModuleType("toga.style")


class _Pack:
    def __init__(self, **kw):
        pass


toga.style.Pack = _Pack


class _MainWindow:
    def __init__(self, title=""):
        pass

    def show(self):
        pass


toga.MainWindow = _MainWindow


class _WebView:
    def __init__(self, url="", style=None):
        pass


toga.WebView = _WebView


class _App:
    def __init__(self, *a, **k):
        pass

    def main_loop(self):
        pass


toga.App = _App
sys.modules["toga"] = toga
sys.modules["toga.style"] = toga.style

import app  # noqa: E402
from factory_core import StatePersistence  # noqa: E402
from forensics import ForensicsScanner  # noqa: E402
from health_guard import HealthGuard  # noqa: E402

PORT = 5056
BASE = f"http://127.0.0.1:{PORT}"


def _start_server_once():
    t = threading.Thread(
        target=lambda: app.server.run(port=PORT, debug=False), daemon=True
    )
    t.start()
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=2)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("test server did not start")


_started = False


def _ensure_server():
    global _started
    if not _started:
        _start_server_once()
        _started = True


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_server()

    def test_root_returns_ui(self):
        code, text = _get("/")
        self.assertEqual(code, 200)
        self.assertIn("MONICO", text)

    def test_health(self):
        code, text = _get("/api/health")
        self.assertEqual(code, 200)
        self.assertIn("cpu", text)

    def test_execute(self):
        code, data = _post("/api/execute", {"command": "ping"})
        self.assertEqual(code, 200)
        self.assertIn("ping", data["output"])

    def test_execute_empty_body(self):
        code, data = _post("/api/execute", {})
        self.assertEqual(code, 200)
        self.assertIn("output", data)


class ForensicsTest(unittest.TestCase):
    def test_deep_scan_lists_files(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write("hello")
        out = ForensicsScanner(d).deep_scan()
        self.assertIn("a.txt", out)
        self.assertEqual(len(out.strip().splitlines()), 1)


class FactoryCoreTest(unittest.TestCase):
    def test_save_and_load_job(self):
        p = os.path.join(tempfile.mkdtemp(), "state.json")
        sp = StatePersistence(p)
        jid = sp.save_job({"step": 1})
        state = sp.load_state()
        self.assertIn(jid, state)
        self.assertEqual(state[jid]["data"], {"step": 1})
        self.assertEqual(state[jid]["status"], "PENDING")


class HealthGuardTest(unittest.TestCase):
    def test_check_returns_fields(self):
        res = HealthGuard().check()
        self.assertIn(res["status"], ("OPTIMAL", "THROTTLING"))
        self.assertIn("cpu", res)
        self.assertIn("ram", res)


if __name__ == "__main__":
    unittest.main()
