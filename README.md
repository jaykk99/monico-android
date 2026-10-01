# 📱 Monico Android

**Monico terminal for Android** — a Python/Toga mobile app with an embedded
local web server (Microdot) serving a tabbed terminal UI
(Terminal, Forensics, System, Jobs). Fully on-device, keyless, works offline.

## Status: v4.5 (Briefcase/Toga app)

## What it actually is
- `app.py` — Toga app: opens a `toga.WebView` pointed at a local Microdot
  server on port 5000. On desktop without Toga installed, `python app.py`
  just serves the web UI (handy for UI testing).
- `ui/index.html` — the actual app UI: self-contained (no CDN, works offline),
  terminal with command history, forensics scanner panel, live system stats,
  job queue. All output is rendered XSS-safe.
- `POST /api/execute` — local command interpreter:
  `help`, `health`, `scan <path>`, `job save <json> | job list | job done <id>`,
  `fetch <url>`; anything else goes to the built-in `MonaCoreV27` engine,
  which returns a canned status line (no external AI model call — offline, keyless).
- `GET /api/health` — CPU/RAM snapshot via `HealthGuard`.
- `POST /api/scan` — bounded forensic SHA-256 scan of a directory
  (default 500 files max, 1 MiB hashed per file, skips symlinks).
- `GET/POST /api/jobs`, `PATCH /api/jobs/<id>` — persistent job queue
  (`StatePersistence`, atomic writes).
- `health_guard.py` — standalone CPU/RAM health checker
  (`--once` for a single check, `--interval N` for the watch loop).
- `factory_core.py` — `StatePersistence` (JSON job store) and `DataBridge`
  (real HTTP log fetcher, truncated).
- `forensics.py` — `ForensicsScanner` with safety bounds.

## Run locally (desktop, for UI testing)
```bash
pip install -r requirements.txt
python3 app.py        # serves the UI at http://localhost:5000
python3 health_guard.py --once
python3 -m unittest tests.test_smoke   # 22 tests
```

## Termux quick start
```bash
bash termux_install.sh
```

## Build a native APK
Requires the **Android SDK** (Briefcase cannot build Android targets without it —
it was not available in this environment, so no APK was produced here):

1. Install a JDK 17+, the Android SDK (cmdline-tools), accept licenses,
   and set `ANDROID_HOME` / `ANDROID_SDK_ROOT`.
2. `pip install briefcase`
3. `briefcase create android` — generates the Gradle project from `pyproject.toml`
4. `briefcase build android` — compiles the APK (needs network for Gradle deps)
5. `briefcase run android` — installs on a connected device/emulator,
   or find the APK under `build/monicoandroid/android/gradle/app/build/outputs/apk/`

Config lives in `pyproject.toml` (`[tool.briefcase]`):
bundle `com.jaykk99.monicoandroid`, phone + tablet, appcompat/material deps.

## Notes
- No API keys required; everything runs on-device.
- The forensics scanner is bounded (500 files / 1 MiB per file by default);
  pass `max_files` to `/api/scan` to adjust (cap 1000).
- Runtime state (`monico_factory.json`) is git-ignored.
