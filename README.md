# 📱 Monico Android

**Monico terminal for Android** — a Python/Toga mobile app with an embedded
local web server (Microdot) serving a tabbed terminal UI (Terminal, Forensics, System).

## Status: v4.4 (Briefcase/Toga app)

## What it actually is
- `app.py` — Toga app: opens a `toga.WebView` pointed at a local Microdot server on port 5000.
- `POST /api/execute` — sends a command string to the built-in `MonaCoreV27` engine, which returns a canned status line (there is no external AI model call; it works fully offline and keyless).
- `GET /api/health` — CPU usage via `psutil`.
- `health_guard.py` — standalone CPU/RAM health checker (30% CPU / 512 MB limits).
- `factory_core.py` — `StatePersistence` (JSON job store) and `DataBridge` (log fetcher stub).
- `forensics.py` — `ForensicsScanner`: walks a directory tree and lists SHA-256 prefixes per file.

## Run locally (desktop, for UI testing)
```bash
pip install -r requirements.txt
python app.py        # serves the UI at http://localhost:5000
python health_guard.py
```

## Termux quick start
```bash
bash termux_install.sh
```

## Build a native APK
Requires the Android SDK (Briefcase cannot build Android targets without it):
```bash
pip install briefcase
briefcase create android
briefcase build android
briefcase run android
```
See `HOW_TO_USE.md` for the full guide and `CONTRIBUTING.md` for contributions.

## Notes
- No API keys required; everything runs on-device.
- The forensics scanner defaults to `/` — pass a narrower path on real devices.
