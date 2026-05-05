#!/data/data/com.termux/files/usr/bin/bash

# --- MONICO ANDROID TERMUX BOOTSTRAP ---
echo "[!] Initializing Monico Android environment..."

# 1. Update and install core dependencies
apt update && apt upgrade -y
apt install python git build-essential binutils -y

# 2. Setup virtual environment
echo "[!] Setting up Python environment..."
python -m venv .monico-env
source .monico-env/bin/activate

# 3. Install Monico dependencies
pip install --upgrade pip
pip install briefcase microdot toga-android requests torch --no-cache-dir

# 4. Clone and launch
if [ ! -d "monico-android" ]; then
    git clone https://github.com/jaykk99/monico-android.git
fi

cd monico-android
echo "[!] Monico Android v2.5 Ready."
echo "[!] To launch the backend server: python app.py"
echo "[!] To build native APK: briefcase build android"
