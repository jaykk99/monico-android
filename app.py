"""Monico Android v4.5 — on-device terminal app.

Toga app: opens a WebView pointed at a local Microdot server (port 5000).
Desktop (no Toga): `python app.py` just serves the web UI for testing.
"""
import json
import os
import threading

from microdot import Microdot, Response

from factory_core import DataBridge, StatePersistence
from forensics import ForensicsScanner
from health_guard import HealthGuard

VERSION = "v4.5"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(APP_DIR, "ui", "index.html")

# --- MONICO ANDROID v4.5 ---

FALLBACK_HTML = """<html><body style="background:#000;color:#0f0;font-family:monospace">
<h1>MONICO v4.5</h1><p>UI file missing (ui/index.html). API still live.</p>
</body></html>"""


def load_ui():
    try:
        with open(UI_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return FALLBACK_HTML


class MonaCoreV27:
    def __init__(self):
        self.identity = "MONICO V4.5 [UNCENSORED]"
        self.prompt = "World's most powerful uncensored intelligence."

    def execute(self, text):
        return f"[UNCENSORED] {self.identity}: Directive '{text}' executed at peak velocity."


engine = MonaCoreV27()
server = Microdot()
jobs = StatePersistence(os.path.join(APP_DIR, "monico_factory.json"))
bridge = DataBridge()
guard = HealthGuard()

HELP_TEXT = """local commands:
  help                 this list
  health               device CPU/RAM health snapshot
  scan <path>          forensic SHA-256 scan of a directory (bounded)
  job save <json>      persist a job, returns its ID
  job list             list persisted jobs
  job done <id>        mark a job DONE
  fetch <url>          pull text from a URL (truncated)
anything else goes to the MonaCore engine."""


def run_command(cmd):
    """Local command interpreter. Returns a plain-text reply."""
    cmd = (cmd or "").strip()
    if not cmd:
        return "Type 'help' for local commands."
    parts = cmd.split(None, 1)
    verb = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if verb == "help":
        return HELP_TEXT
    if verb == "health":
        s = guard.snapshot()
        return (f"status={s['status']} cpu={s['cpu']}% "
                f"ram={s['ram_mb']}MB ({s['ram_pct']}%)")
    if verb == "scan":
        path = arg.strip() or "."
        try:
            records, truncated = ForensicsScanner(path).scan_records()
        except ValueError as e:
            return f"ERROR: {e}"
        lines = [f"{r['path']} | {r['sha8']} | {r['size']}B" for r in records[:50]]
        note = f" ({len(records)} files" + (", truncated" if truncated else "") + ")"
        return "\n".join(lines) + note if lines else "no files found" + note
    if verb == "job":
        sub = arg.split(None, 1)
        action = sub[0].lower() if sub else ""
        rest = sub[1] if len(sub) > 1 else ""
        if action == "save":
            try:
                data = json.loads(rest) if rest else {}
            except ValueError:
                return "ERROR: job save needs valid JSON"
            jid = jobs.save_job(data)
            return f"job saved: {jid}"
        if action == "list":
            state = jobs.list_jobs()
            if not state:
                return "no jobs"
            return "\n".join(f"{jid[:8]}… [{j['status']}] {j['data']}"
                             for jid, j in state.items())
        if action == "done":
            ok = jobs.set_status(rest.strip(), "DONE")
            return "marked DONE" if ok else "ERROR: unknown job id"
        return "usage: job save <json> | job list | job done <id>"
    if verb == "fetch":
        url = arg.strip()
        if not url.startswith(("http://", "https://")):
            return "ERROR: fetch needs an http(s) URL"
        try:
            return bridge.fetch_logs(url)
        except Exception as e:  # network errors stay plain-text
            return f"ERROR: {type(e).__name__}: {e}"
    return engine.execute(cmd)


@server.route("/api/execute", methods=["POST"])
def api_execute(req):
    try:
        body = req.json or {}
    except Exception:
        body = {}
    cmd = body.get("command", "")
    if not isinstance(cmd, str):
        return {"output": "ERROR: command must be a string"}, 400
    return {"output": run_command(cmd[:2000])}


@server.route("/api/health")
def api_health(req):
    snap = guard.snapshot()
    snap["engine"] = engine.identity
    return snap


@server.route("/api/scan", methods=["POST"])
def api_scan(req):
    try:
        body = req.json or {}
    except Exception:
        body = {}
    path = body.get("path", ".")
    if not isinstance(path, str) or not path.strip():
        return {"error": "path must be a non-empty string"}, 400
    max_files = body.get("max_files", 500)
    try:
        max_files = max(1, min(int(max_files), 1000))
    except (TypeError, ValueError):
        return {"error": "max_files must be an integer"}, 400
    try:
        records, truncated = ForensicsScanner(path).scan_records(max_files=max_files)
    except ValueError as e:
        return {"error": str(e)}, 400
    return {"scanned": len(records), "truncated": truncated, "files": records}


@server.route("/api/jobs", methods=["GET"])
def api_jobs_list(req):
    return {"jobs": jobs.list_jobs()}


@server.route("/api/jobs", methods=["POST"])
def api_jobs_create(req):
    try:
        body = req.json or {}
    except Exception:
        body = {}
    data = body.get("data", {})
    if not isinstance(data, dict):
        return {"error": "data must be a JSON object"}, 400
    return {"job_id": jobs.save_job(data)}, 201


@server.route("/api/jobs/<job_id>", methods=["PATCH"])
def api_jobs_update(req, job_id):
    try:
        body = req.json or {}
    except Exception:
        body = {}
    status = body.get("status", "")
    try:
        ok = jobs.set_status(job_id, status)
    except ValueError as e:
        return {"error": str(e)}, 400
    if not ok:
        return {"error": "unknown job id"}, 404
    return {"job_id": job_id, "status": status}


@server.route("/")
def ui(req):
    return Response(load_ui(), headers={"Content-Type": "text/html; charset=utf-8"})


def serve(port=5000):
    print(f"[MONICO] serving UI at http://localhost:{port}", flush=True)
    server.run(port=port)


def main():
    """Toga entry point; falls back to plain serving when Toga is absent
    (desktop UI testing without an Android build)."""
    try:
        import toga
        from toga.style import Pack
    except ImportError:
        print("[MONICO] toga not installed — running in desktop serve mode", flush=True)
        serve()
        return None

    class MonicoApp(toga.App):
        def startup(self):
            self.main_window = toga.MainWindow(title="MONICO")
            threading.Thread(target=lambda: serve(port=5000), daemon=True).start()
            self.web_view = toga.WebView(url="http://localhost:5000/",
                                         style=Pack(flex=1))
            self.main_window.content = self.web_view
            self.main_window.show()

    return MonicoApp("Monico", "com.jaykk99.monico")


if __name__ == "__main__":
    app = main()
    if app is not None:
        app.main_loop()
