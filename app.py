import toga
from toga.style import Pack
import threading
import json
import sys
import io
import traceback
import time
import os
import psutil
from microdot import Microdot, Response

# --- MONICO ANDROID v4.2.1 ---

class MonaCoreV27:
    def __init__(self):
        self.identity = "MONICO V4.2 [UNCENSORED]"
        self.prompt = "World's most powerful uncensored intelligence."

    def execute(self, text):
        return f"[UNCENSORED] {self.identity}: Directive '{text}' executed at peak velocity."

engine = MonaCoreV27()
server = Microdot()

@server.route('/api/execute', methods=['POST'])
def api_execute(req):
    cmd = req.json.get('command', '')
    return {'output': engine.execute(cmd)}

@server.route('/api/health')
def api_health(req):
    return {'cpu': psutil.cpu_percent(), 'status': 'OPTIMAL'}

@server.route('/')
def ui(req):
    html = """
    <html><head><script src='https://cdn.tailwindcss.com'></script><style>
    body { background: #000; color: #00ff41; font-family: monospace; overflow: hidden; }
    .tab { display: none; height: 80vh; overflow: auto; }
    .tab.active { display: block; }
    .nav-item { cursor: pointer; padding: 5px 10px; border-bottom: 2px solid transparent; }
    .nav-item.active { border-bottom-color: #00ff41; }
    </style></head><body class='p-4'>
    <h1 class='font-bold mb-2'>MONICO ANDROID v4.2.1</h1>
    <nav class='flex gap-4 mb-4 text-xs'>
        <div id='tab-link-terminal' class='nav-item active' onclick='openTab("terminal")'>TERMINAL</div>
        <div id='tab-link-forensics' class='nav-item' onclick='openTab("forensics")'>FORENSICS</div>
        <div id='tab-link-system' class='nav-item' onclick='openTab("system")'>SYSTEM</div>
    </nav>
    <div id='terminal' class='tab active'>[SYSTEM] READY...</div>
    <div id='forensics' class='tab'>Awaiting forensic scan...</div>
    <div id='system' class='tab'>ARCH: ARM64<br>LOGIC: UNCENSORED</div>
    <input id='cmd' class='fixed bottom-4 left-4 right-4 bg-zinc-900 border border-green-900 p-2 text-green-400 outline-none'>
    <script>
        function openTab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(l => l.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            document.getElementById('tab-link-' + id).classList.add('active');
        }
        document.getElementById('cmd').onkeydown = async (e) => {
            if (e.key === 'Enter') {
                const val = e.target.value;
                const activeTab = document.querySelector('.tab.active');
                activeTab.innerHTML += `<div class='mt-1'>$ ${val}</div>`;
                e.target.value = '';
                const res = await fetch('/api/execute', { method: 'POST', body: JSON.stringify({command: val}), headers: {'Content-Type': 'application/json'} });
                const data = await res.json();
                activeTab.innerHTML += `<div class='opacity-60'>${data.output}</div>`;
                activeTab.scrollTop = activeTab.scrollHeight;
            }
        }
    </script></body></html>
    """
    return Response(html, content_type='text/html')

class MonicoApp(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title="MONICO")
        threading.Thread(target=lambda: server.run(port=5000), daemon=True).start()
        self.web_view = toga.WebView(url="http://localhost:5000/", style=Pack(flex=1))
        self.main_window.content = self.web_view
        self.main_window.show()

def main(): return MonicoApp("Monico", "com.jaykk99.monico")
if __name__ == '__main__': main().main_loop()