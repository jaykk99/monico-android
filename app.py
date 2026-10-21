"""Monico Android v4.5 — on-device terminal app.

Toga app: opens a WebView pointed at a local Microdot server (port 5000).
Desktop (no Toga): `python app.py` just serves the web UI for testing.
"""
import hashlib
import json
import os
import platform
import shutil
import threading
import time
from collections import deque

from microdot import Microdot, Response

from factory_core import DataBridge, StatePersistence
from forensics import ForensicsScanner
from health_guard import HealthGuard

VERSION = "v4.5"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(APP_DIR, "ui", "index.html")

# Bounds so one command can never hang or blow up the on-device server.
LS_MAX_ENTRIES = 200
CAT_MAX_CHARS = 10000
HASH_MAX_BYTES = 10 * 1024 * 1024
FIND_MAX_MATCHES = 200
BATCH_MAX_COMMANDS = 20

COMMANDS = ("help", "health", "scan", "job", "fetch", "ls", "cat",
            "hash", "disk", "find", "date", "uptime", "sysinfo",
            "ps", "net", "head", "tail", "wc", "du", "log")

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

# Recent commands seen by the API layer (newest first, capped).
# Populated by /api/execute and /api/execute/batch only, so unit tests
# calling run_command() directly never pollute it.
cmdlog = deque(maxlen=50)


def log_command(cmd, output):
    cmdlog.appendleft({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "command": cmd[:200],
        "ok": not output.startswith("ERROR"),
    })

HELP_TEXT = """local commands:
  help                 this list
  health [full]        device CPU/RAM health snapshot (full: limits + disk)
  scan <path>          forensic SHA-256 scan of a directory (bounded)
  job save <json>      persist a job, returns its ID
  job list             list persisted jobs
  job done <id>        mark a job DONE
  job get <id>         show one job as JSON
  job clear            delete ALL jobs from the queue
  fetch <url>          pull text from a URL (truncated)
  ls <path>            list a directory (200 entries max)
  cat <file>           print a text file (10k chars max, no binaries)
  hash <file>          full SHA-256 hex of a file (10 MiB read max)
  disk                 disk usage for the app volume
  find <dir> <text>    filename substring search (200 matches max)
  date                 current date/time
  uptime               device uptime
  sysinfo              platform, python, cpu count, total RAM
  ps                   top processes by CPU (25 max)
  net                  network bytes/packets sent/received
  head <file> [n]      first n lines of a text file (default 20)
  tail <file> [n]      last n lines of a text file (default 20)
  wc <file>            line/word/byte counts (10 MiB max)
  du <path>            disk used under a directory
  log                  recent commands run through the API (newest first)
anything else goes to the MonaCore engine."""


def _resolve_file(target):
    """Resolve a user path; returns (abspath, error). Never follows symlinks."""
    p = os.path.abspath(os.path.expanduser(target))
    if os.path.islink(p):
        return None, f"ERROR: symlinks not followed: {target}"
    if not os.path.isfile(p):
        return None, f"ERROR: not a file: {target}"
    return p, None


def _resolve_dir(target):
    p = os.path.abspath(os.path.expanduser(target))
    if not os.path.isdir(p):
        return None, f"ERROR: not a directory: {target}"
    return p, None


def cmd_ls(arg):
    p, err = _resolve_dir(arg.strip() or ".")
    if err:
        return err
    try:
        names = sorted(os.listdir(p))[:LS_MAX_ENTRIES]
    except OSError as e:
        return f"ERROR: {e}"
    if not names:
        return "(empty)"
    lines = []
    for name in names:
        fp = os.path.join(p, name)
        try:
            if os.path.isdir(fp) and not os.path.islink(fp):
                lines.append(f"{name}/")
            else:
                lines.append(f"{name}  {os.path.getsize(fp)}B")
        except OSError:
            lines.append(name)
    out = "\n".join(lines)
    if len(names) >= LS_MAX_ENTRIES:
        out += f"\n…truncated at {LS_MAX_ENTRIES} entries"
    return out


def cmd_cat(arg):
    target = arg.strip()
    if not target:
        return "usage: cat <file>"
    p, err = _resolve_file(target)
    if err:
        return err
    try:
        with open(p, "rb") as f:
            data = f.read(CAT_MAX_CHARS + 1)
    except OSError as e:
        return f"ERROR: {e}"
    if b"\x00" in data:
        return "ERROR: binary file, not text"
    text = data[:CAT_MAX_CHARS].decode("utf-8", errors="replace")
    if len(data) > CAT_MAX_CHARS:
        text += f"\n…[truncated at {CAT_MAX_CHARS} chars]"
    return text if text else "(empty file)"


def cmd_hash(arg):
    target = arg.strip()
    if not target:
        return "usage: hash <file>"
    p, err = _resolve_file(target)
    if err:
        return err
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            remaining = HASH_MAX_BYTES
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                h.update(chunk)
                remaining -= len(chunk)
    except OSError as e:
        return f"ERROR: {e}"
    return h.hexdigest()


def cmd_disk():
    du = shutil.disk_usage(APP_DIR)
    return (f"total={du.total // 1024 // 1024}MB "
            f"used={du.used // 1024 // 1024}MB "
            f"free={du.free // 1024 // 1024}MB")


def cmd_find(arg):
    parts = arg.split(None, 1)
    if len(parts) < 2:
        return "usage: find <dir> <name-substring>"
    p, err = _resolve_dir(parts[0])
    if err:
        return err
    pat = parts[1].lower()
    matches = []
    for root, _dirs, files in os.walk(p, followlinks=False):
        for name in files:
            if pat in name.lower():
                matches.append(os.path.join(root, name))
                if len(matches) >= FIND_MAX_MATCHES:
                    break
        if len(matches) >= FIND_MAX_MATCHES:
            break
    if not matches:
        return "no matches"
    out = "\n".join(matches)
    if len(matches) >= FIND_MAX_MATCHES:
        out += f"\n…truncated at {FIND_MAX_MATCHES} matches"
    return out


def cmd_uptime():
    import psutil
    secs = int(time.time() - psutil.boot_time())
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    bits = []
    if days:
        bits.append(f"{days}d")
    if hours:
        bits.append(f"{hours}h")
    if mins:
        bits.append(f"{mins}m")
    bits.append(f"{secs}s")
    return "uptime " + " ".join(bits)


def cmd_sysinfo():
    import psutil
    total_mb = psutil.virtual_memory().total // 1024 // 1024
    return (f"platform={platform.system()} {platform.machine()} "
            f"python={platform.python_version()} "
            f"cpus={psutil.cpu_count()} ram_total={total_mb}MB")


def cmd_ps():
    import psutil
    rows = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            rows.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda i: i.get("cpu_percent") or 0, reverse=True)
    lines = []
    for i in rows[:25]:
        mem = i.get("memory_info")
        mem_mb = mem.rss // 1024 // 1024 if mem else 0
        lines.append("%6s %5.1f%% %5dMB %s"
                     % (i.get("pid"), i.get("cpu_percent") or 0,
                        mem_mb, i.get("name") or "?"))
    return "\n".join(lines) if lines else "no processes visible"


def cmd_net():
    import psutil
    c = psutil.net_io_counters()
    return ("sent=%dKB recv=%dKB pkts_sent=%d pkts_recv=%d"
            % (c.bytes_sent // 1024, c.bytes_recv // 1024,
               c.packets_sent, c.packets_recv))


def _parse_file_n(arg, name):
    """Split '<file> [n]' args. Returns (target, n, error)."""
    parts = arg.split()
    if not parts:
        return None, 0, f"usage: {name} <file> [n]"
    target = parts[0]
    n = 20
    if len(parts) > 1:
        try:
            n = int(parts[1])
        except ValueError:
            return None, 0, "ERROR: n must be an integer"
    if not 1 <= n <= 200:
        return None, 0, "ERROR: n must be 1..200"
    return target, n, None


def cmd_head(arg):
    target, n, err = _parse_file_n(arg, "head")
    if err:
        return err
    p, ferr = _resolve_file(target)
    if ferr:
        return ferr
    try:
        with open(p, "rb") as f:
            data = f.read(CAT_MAX_CHARS * 2 + 1)
    except OSError as e:
        return f"ERROR: {e}"
    if b"\x00" in data:
        return "ERROR: binary file, not text"
    lines = data.decode("utf-8", errors="replace").splitlines()[:n]
    out = "\n".join(lines)
    return out if out else "(empty file)"


def cmd_tail(arg):
    target, n, err = _parse_file_n(arg, "tail")
    if err:
        return err
    p, ferr = _resolve_file(target)
    if ferr:
        return ferr
    try:
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            # Read at most the last 64 KiB; enough for 200 short lines.
            start = max(0, size - 65536)
            f.seek(start)
            data = f.read()
    except OSError as e:
        return f"ERROR: {e}"
    if b"\x00" in data:
        return "ERROR: binary file, not text"
    text = data.decode("utf-8", errors="replace")
    if start > 0:
        # we may have started mid-line; drop the partial first line
        text = text.split("\n", 1)[1] if "\n" in text else ""
    lines = text.splitlines()[-n:]
    out = "\n".join(lines)
    return out if out else "(empty file)"


def cmd_wc(arg):
    target = arg.strip()
    if not target:
        return "usage: wc <file>"
    p, err = _resolve_file(target)
    if err:
        return err
    lines = words = size = 0
    try:
        with open(p, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > HASH_MAX_BYTES:
                    return ("ERROR: file over %d MiB, too big to count"
                            % (HASH_MAX_BYTES // 1024 // 1024))
                lines += chunk.count(b"\n")
                words += len(chunk.split())
    except OSError as e:
        return f"ERROR: {e}"
    return f"{lines} lines, {words} words, {size} bytes"


def cmd_du(arg):
    target = arg.strip() or "."
    p, err = _resolve_dir(target)
    if err:
        return err
    total = files = 0
    for root, _dirs, names in os.walk(p, followlinks=False):
        for name in names:
            fp = os.path.join(root, name)
            try:
                if os.path.islink(fp):
                    continue
                total += os.path.getsize(fp)
                files += 1
            except OSError:
                continue
            if files >= 50000:
                return (f"over 50000 files, {total // 1024}KB so far "
                        "(truncated)")
    return f"{total // 1024}KB in {files} files"


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
        base = (f"status={s['status']} cpu={s['cpu']}% "
                f"ram={s['ram_mb']}MB ({s['ram_pct']}%)")
        if arg.strip().lower() == "full":
            du = shutil.disk_usage(APP_DIR)
            return (base +
                    f" limits: cpu<={guard.cpu_limit}% ram<={guard.ram_limit}MB"
                    f" disk_free={du.free // 1024 // 1024}MB ts={s['ts']}")
        return base
    if verb == "ls":
        return cmd_ls(arg)
    if verb == "cat":
        return cmd_cat(arg)
    if verb == "hash":
        return cmd_hash(arg)
    if verb == "disk":
        return cmd_disk()
    if verb == "find":
        return cmd_find(arg)
    if verb == "date":
        return time.strftime("%Y-%m-%d %H:%M:%S %Z")
    if verb == "uptime":
        return cmd_uptime()
    if verb == "sysinfo":
        return cmd_sysinfo()
    if verb == "ps":
        return cmd_ps()
    if verb == "net":
        return cmd_net()
    if verb == "head":
        return cmd_head(arg)
    if verb == "tail":
        return cmd_tail(arg)
    if verb == "wc":
        return cmd_wc(arg)
    if verb == "du":
        return cmd_du(arg)
    if verb == "log":
        if not cmdlog:
            return "no commands logged yet"
        return "\n".join(f"{e['at']}  [{'OK' if e['ok'] else 'ERR'}]  {e['command']}"
                         for e in list(cmdlog)[:20])
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
        if action == "get":
            j = jobs.get_job(rest.strip())
            return json.dumps(j) if j else "ERROR: unknown job id"
        if action == "clear":
            jobs.clear()
            return "job queue cleared"
        return "usage: job save <json> | job list | job done <id> | job get <id> | job clear"
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
    out = run_command(cmd[:2000])
    log_command(cmd, out)
    return {"output": out}


@server.route("/api/execute/batch", methods=["POST"])
def api_execute_batch(req):
    """Run up to BATCH_MAX_COMMANDS commands in one call, in order."""
    try:
        body = req.json or {}
    except Exception:
        body = {}
    cmds = body.get("commands", [])
    if not isinstance(cmds, list):
        return {"error": "commands must be a list of strings"}, 400
    results = []
    for c in cmds[:BATCH_MAX_COMMANDS]:
        if not isinstance(c, str):
            results.append({"command": c,
                            "output": "ERROR: command must be a string"})
            continue
        out = run_command(c[:2000])
        log_command(c, out)
        results.append({"command": c, "output": out})
    return {"results": results}


@server.route("/api/cmdlog")
def api_cmdlog(req):
    return {"commands": list(cmdlog)}


@server.route("/api/ps")
def api_ps(req):
    """Top processes by CPU as JSON (same data as the ps command)."""
    import psutil
    rows = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            i = p.info
            mem = i.get("memory_info")
            rows.append({
                "pid": i.get("pid"),
                "name": i.get("name") or "?",
                "cpu_pct": round(i.get("cpu_percent") or 0, 1),
                "mem_mb": (mem.rss // 1024 // 1024) if mem else 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda r: r["cpu_pct"], reverse=True)
    return {"processes": rows[:25]}


@server.route("/api/version")
def api_version(req):
    return {"version": VERSION, "engine": engine.identity,
            "commands": sorted(COMMANDS)}


@server.route("/api/disk")
def api_disk(req):
    du = shutil.disk_usage(APP_DIR)
    return {"total_mb": du.total // 1024 // 1024,
            "used_mb": du.used // 1024 // 1024,
            "free_mb": du.free // 1024 // 1024}


@server.route("/api/sysinfo")
def api_sysinfo(req):
    import psutil
    du = shutil.disk_usage(APP_DIR)
    vm = psutil.virtual_memory()
    return {
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "cpus": psutil.cpu_count(),
        "ram_total_mb": vm.total // 1024 // 1024,
        "uptime_s": int(time.time() - psutil.boot_time()),
        "disk": {"total_mb": du.total // 1024 // 1024,
                 "used_mb": du.used // 1024 // 1024,
                 "free_mb": du.free // 1024 // 1024},
    }


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


@server.route("/api/jobs", methods=["DELETE"])
def api_jobs_clear(req):
    jobs.clear()
    return {"ok": True, "cleared": True}


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
