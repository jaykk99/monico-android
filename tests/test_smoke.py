import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
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

# Isolate the job store so tests never touch the repo's real state file.
_tmp_jobs_dir = tempfile.mkdtemp()
app.jobs = StatePersistence(os.path.join(_tmp_jobs_dir, "jobs.json"))

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


def _read_json(resp):
    return json.loads(resp.read().decode("utf-8"))


def _get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _get_json(path):
    code, text = _get(path)
    return code, json.loads(text)


def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, _read_json(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


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

    def test_execute_help(self):
        code, data = _post("/api/execute", {"command": "help"})
        self.assertEqual(code, 200)
        self.assertIn("scan <path>", data["output"])

    def test_execute_health_command(self):
        code, data = _post("/api/execute", {"command": "health"})
        self.assertEqual(code, 200)
        self.assertIn("cpu=", data["output"])

    def test_execute_scan_command(self):
        code, data = _post("/api/execute", {"command": "scan " + REPO})
        self.assertEqual(code, 200)
        self.assertIn("files", data["output"])

    def test_execute_job_roundtrip(self):
        code, data = _post("/api/execute", {"command": 'job save {"step": 9}'})
        self.assertEqual(code, 200)
        self.assertIn("job saved:", data["output"])
        jid = data["output"].split("job saved:")[1].strip()
        code, data = _post("/api/execute", {"command": "job done " + jid})
        self.assertIn("marked DONE", data["output"])

    def test_execute_nonstring_command_rejected(self):
        code, _ = _post("/api/execute", {"command": ["not", "a", "string"]})
        self.assertEqual(code, 400)

    def test_health_fields(self):
        code, data = _get("/api/health")
        self.assertEqual(code, 200)
        payload = json.loads(data)
        for key in ("cpu", "ram_mb", "ram_pct", "status", "ts", "engine"):
            self.assertIn(key, payload)

    def test_root_serves_new_ui(self):
        code, text = _get("/")
        self.assertEqual(code, 200)
        self.assertIn("FORENSICS", text)
        self.assertNotIn("cdn.tailwindcss.com", text)  # fully offline UI


def _patch(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


class ScanApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_server()

    def test_scan_endpoint(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "b.txt"), "w") as f:
            f.write("world")
        code, data = _post("/api/scan", {"path": d})
        self.assertEqual(code, 200)
        self.assertEqual(data["scanned"], 1)
        self.assertEqual(data["files"][0]["path"], "b.txt")
        self.assertEqual(len(data["files"][0]["sha8"]), 8)

    def test_scan_bad_path_rejected(self):
        code, data = _post("/api/scan", {"path": "/nonexistent-xyz-123"})
        self.assertEqual(code, 400)
        self.assertIn("error", data)


class JobsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_server()

    def test_job_crud(self):
        code, data = _post("/api/jobs", {"data": {"task": "demo"}})
        self.assertEqual(code, 201)
        jid = data["job_id"]
        code, data = _get_json("/api/jobs")
        self.assertEqual(code, 200)
        self.assertEqual(data["jobs"][jid]["status"], "PENDING")
        code, data = _patch("/api/jobs/" + jid, {"status": "DONE"})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "DONE")

    def test_job_bad_status_rejected(self):
        code, data = _post("/api/jobs", {"data": {}})
        jid = data["job_id"]
        req = urllib.request.Request(
            BASE + "/api/jobs/" + jid, data=json.dumps({"status": "NOPE"}).encode(),
            method="PATCH", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("expected HTTP 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_job_unknown_id_404(self):
        req = urllib.request.Request(
            BASE + "/api/jobs/does-not-exist", data=json.dumps({"status": "DONE"}).encode(),
            method="PATCH", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("expected HTTP 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


class ForensicsTest(unittest.TestCase):
    def test_deep_scan_lists_files(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write("hello")
        out = ForensicsScanner(d).deep_scan()
        self.assertIn("a.txt", out)
        self.assertEqual(len(out.strip().splitlines()), 1)

    def test_scan_records_bounded(self):
        d = tempfile.mkdtemp()
        for i in range(10):
            with open(os.path.join(d, f"f{i}.txt"), "w") as f:
                f.write("x")
        records, truncated = ForensicsScanner(d).scan_records(max_files=4)
        self.assertEqual(len(records), 4)
        self.assertTrue(truncated)
        self.assertTrue(all(len(r["sha8"]) == 8 for r in records))

    def test_scan_bad_target_raises(self):
        with self.assertRaises(ValueError):
            ForensicsScanner("/nonexistent-xyz-123").scan_records()


class FactoryCoreTest(unittest.TestCase):
    def test_save_and_load_job(self):
        p = os.path.join(tempfile.mkdtemp(), "state.json")
        sp = StatePersistence(p)
        jid = sp.save_job({"step": 1})
        state = sp.load_state()
        self.assertIn(jid, state)
        self.assertEqual(state[jid]["data"], {"step": 1})
        self.assertEqual(state[jid]["status"], "PENDING")

    def test_set_status_lifecycle(self):
        p = os.path.join(tempfile.mkdtemp(), "state.json")
        sp = StatePersistence(p)
        jid = sp.save_job({"step": 1})
        self.assertTrue(sp.set_status(jid, "RUNNING"))
        self.assertEqual(sp.get_job(jid)["status"], "RUNNING")
        self.assertTrue(sp.set_status(jid, "DONE"))
        self.assertEqual(sp.get_job(jid)["status"], "DONE")
        self.assertFalse(sp.set_status("missing-id", "DONE"))
        with self.assertRaises(ValueError):
            sp.set_status(jid, "NOPE")


class HealthGuardTest(unittest.TestCase):
    def test_check_returns_fields(self):
        res = HealthGuard().check()
        self.assertIn(res["status"], ("OPTIMAL", "THROTTLING"))
        self.assertIn("cpu", res)
        self.assertIn("ram", res)


if __name__ == "__main__":
    unittest.main()
