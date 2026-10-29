#!/data/data/com.termux/files/usr/bin/bash
# --- MONICO ANDROID TERMUX INSTALLER (fixed) ---
#
# Works three ways:
#   1. Inside a clone:        cd ~/monico-android && bash termux_install.sh
#   2. Downloaded on its own: bash ~/termux_install.sh   (clones the repo first)
#   3. One-liner:             curl -sL https://raw.githubusercontent.com/jaykk99/monico-android/main/termux_install.sh -o ~/termux_install.sh && bash ~/termux_install.sh
#
# What this does NOT install, on purpose:
#   - torch     : never imported by this app, and PyPI ships no wheel that
#                 runs on Termux (glibc manylinux wheels do not load on
#                 Android/bionic), so pip tries a huge source build and dies.
#   - briefcase : desktop tool for building the APK. It needs a computer +
#                 JDK + Android SDK; it cannot build an APK on the phone.
#   - toga      : only used inside the packaged APK. In plain Termux Python,
#                 app.py falls back to serving the web UI when toga is absent.
#                 Installing toga-android here actually BREAKS startup: the
#                 import succeeds, the fallback never runs, and Toga then
#                 crashes trying to load an Android platform factory.
#   - a venv    : psutil comes from the Termux package python-psutil
#                 (prebuilt). A venv would hide that system package, and
#                 pip-building psutil on-device needs a C toolchain.
set -e

REPO_URL="https://github.com/jaykk99/monico-android.git"
REPO_DIR="$HOME/monico-android"

echo "[!] Initializing Monico Android environment (Termux)..."

# 1. Find or fetch the repo, and work from its root.
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/app.py" ]; then
    REPO_DIR="$SCRIPT_DIR"
elif [ -f "$REPO_DIR/app.py" ]; then
    echo "[!] Found existing clone at $REPO_DIR"
else
    echo "[!] Cloning monico-android into $REPO_DIR ..."
    git clone "$REPO_URL" "$REPO_DIR" 2>/dev/null || {
        echo "[!] git is not installed yet - installing packages first, then cloning."
        pkg update -y
        pkg install -y python git
        git clone "$REPO_URL" "$REPO_DIR"
    }
fi
cd "$REPO_DIR"
if [ -d .git ]; then
    git pull -q 2>/dev/null || echo "[!] (pull skipped - continuing with what is here)"
fi

# 2. Termux packages: python + git + PREBUILT psutil (health_guard.py imports
#    psutil at module load, so the app will not start without it).
echo "[!] Installing Termux packages (python, git, python-psutil)..."
pkg update -y
pkg install -y python git python-psutil

# 3. Pure-Python deps from PyPI (these ship py3-none-any wheels that work
#    on Termux). psutil is deliberately NOT pip-installed - see step 2.
echo "[!] Installing Python dependencies (microdot, requests)..."
python -m pip install --upgrade pip
python -m pip install microdot requests

# 4. Verify the exact imports app.py needs, including the psutil route.
echo "[!] Verifying imports..."
if ! python -c "import microdot, requests, psutil" 2>/dev/null; then
    echo "[!] psutil import failed - falling back to a pip source build."
    pkg install -y clang make
    python -m pip install psutil
    python -c "import microdot, requests, psutil"
fi
python -c "import app; print('[!] app module imports OK')"

VERSION="$(cat VERSION 2>/dev/null || echo v4.5)"
echo ""
echo "[!] Monico Android $VERSION ready."
echo "[!] Launch it:"
echo ""
echo "    cd \"$REPO_DIR\""
echo "    python app.py"
echo ""
echo "[!] Then open this in your Android browser:"
echo ""
echo "    http://127.0.0.1:5000"
echo ""
echo "[!] No API keys needed. It runs fully on-device."
echo "[!] (Building a native APK needs Briefcase on a computer - it"
echo "    cannot be built from Termux on the phone itself.)"
