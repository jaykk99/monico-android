# How to Use Monico Android v4.5

On-device terminal app: a local web UI (served by Microdot, shown in a Toga
WebView on Android) with a real local command interpreter. No accounts, no
keys, no network needed.

## 1. Run it

**On Android (native APK):** see "Build a native APK" in README.md — requires
the Android SDK + Briefcase.

**On desktop (UI testing / demo):**
```bash
pip install -r requirements.txt
python3 app.py        # open http://localhost:5000
```

**In Termux:** `bash termux_install.sh`

## 2. The Terminal tab

Type a command, press Enter. `↑`/`↓` cycle history.

Local commands (all run on-device):

| command | what it does |
|---|---|
| `help` | list commands |
| `health` | CPU/RAM snapshot from HealthGuard |
| `scan <path>` | forensic SHA-256 scan of a directory (bounded) |
| `job save {"task":"…"}` | persist a job, prints its ID |
| `job list` | list persisted jobs |
| `job done <id>` | mark a job DONE |
| `fetch <url>` | pull text from a URL (truncated at 20k chars) |

Anything else is answered by the built-in MonaCore engine (canned on-device
response — there is no external model call).

## 3. The Forensics tab

Enter a directory, hit SCAN. Lists each file with size and SHA-256 prefix.
Safety bounds: 500 files max, 1 MiB hashed per file, symlinks skipped —
a scan can never hang the app. Results render in a table, XSS-safe.

## 4. The System tab

Live CPU/RAM bars and status (`OPTIMAL`/`THROTTLING` against the
30% CPU / 512 MB guard limits), engine identity, last-check timestamp.
Header LEDs show the same at a glance on every tab.

## 5. The Jobs tab

Save a JSON job, watch the queue, mark jobs DONE. Jobs persist in
`monico_factory.json` (atomic writes, survives restarts) — this is the
state store factory runs use to resume.

## 6. HealthGuard CLI

```bash
python3 health_guard.py --once              # single check, exit
python3 health_guard.py --interval 5         # watch loop (Ctrl-C stops)
```

## 7. API reference

- `GET /` — the UI
- `POST /api/execute` `{"command": "…"}` → `{"output": "…"}`
- `GET /api/health` → `{status, cpu, ram_mb, ram_pct, ts, engine}`
- `POST /api/scan` `{"path": "…", "max_files": 500}` → `{scanned, truncated, files[]}`
- `GET /api/jobs` → `{jobs: {id: {data, status}}}`
- `POST /api/jobs` `{"data": {…}}` → `{job_id}` (201)
- `PATCH /api/jobs/<id>` `{"status": "DONE"}` → `{job_id, status}`
