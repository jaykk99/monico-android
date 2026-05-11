import toga
from toga.style import Pack
import threading
import json
import sys
import io
import traceback
import time
import hashlib
import os
from datetime import datetime
from microdot import Microdot, Response
import torch
import torch.nn as nn
import torch.nn.functional as F

# --- MONICO ANDROID v2.5 CORE [HARDENED] ---
# [UPGRADE Date: May 11, 2026]: Implementing Job ID system and State Persistence

STATE_FILE = "state_persistence.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"jobs": {}, "total_processed": 0}
    return {"jobs": {}, "total_processed": 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

server = Microdot()
state = load_state()

@server.route('/api/execute', methods=['POST'])
def execute(req):
    data = req.json
    cmd = data.get('command', '')
    job_id = data.get('job_id', hashlib.sha1(str(time.time()).encode()).hexdigest()[:8])
    
    # State Persistence Start
    state["jobs"][job_id] = {"status": "RUNNING", "timestamp": str(datetime.now())}
    save_state(state)

    buf = io.StringIO()
    with threading.Lock():
        try:
            with open('output_log.txt', 'a') as log_f:
                log_f.write(f"[{datetime.now()}] JOB {job_id}: {cmd}\n")
            
            exec(cmd, {'__builtins__': __builtins__}, {})
            output = "OK"
            state["jobs"][job_id]["status"] = "SUCCESS"
        except Exception:
            output = traceback.format_exc()
            state["jobs"][job_id]["status"] = "FAILED"
        
        save_state(state)
    
    return {'output': output, 'job_id': job_id}

@server.route('/')
def ui(req):
    return Response("<html><body style='background:#000;color:#00ff41;font-family:monospace'><h1>MONICO ANDROID v2.5 [HARDENED]</h1><div id='out'></div><input id='in'><script>document.getElementById('in').onkeydown=async(e)=>{if(e.key=='Enter'){const r=await fetch('/api/execute',{method:'POST',body:JSON.stringify({command:e.target.value}),headers:{'Content-Type':'application/json'}});const d=await r.json();document.getElementById('out').innerText+='\n['+d.job_id+'] > '+d.output}}</script></body></html>", content_type='text/html')

class MonicoAndroid(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title="MONICO ANDROID [HARDENED]")
        threading.Thread(target=lambda: server.run(port=5000), daemon=True).start()
        self.web_view = toga.WebView(url="http://localhost:5000/", style=Pack(flex=1))
        self.main_window.content = self.web_view
        self.main_window.show()

def main(): return MonicoAndroid("MonicoAndroid", "com.jaykk99.monicoandroid")
if __name__ == '__main__': main().main_loop()
