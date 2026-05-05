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

# --- MONACO ANDROID v2.5 CORE ---
D_MODEL = 256
N_HEADS = 8
N_LAYERS = 4
MAX_REASON_DEPTH = 6

class BitLinear(nn.Linear):
    def forward(self, x):
        w = self.weight
        scale = w.abs().mean().clamp(min=1e-8)
        w_ternary = torch.sign(w) * (w.abs() > 0.5 * scale).float()
        w_ste = w + (w_ternary - w).detach()
        return F.linear(x, w_ste, self.bias)

class MonaCoreV27(nn.Module):
    def __init__(self, vocab_size=256):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, D_MODEL)
        self.pos = nn.Embedding(2048, D_MODEL)
        self.blocks = nn.ModuleList([nn.TransformerEncoderLayer(D_MODEL, N_HEADS, batch_first=True, norm_first=True) for _ in range(N_LAYERS)])
        self.norm = nn.LayerNorm(D_MODEL)
        self.actor = BitLinear(D_MODEL, vocab_size)

    def adaptive_reason(self, tokens):
        seq_len = tokens.size(1)
        pos_ids = torch.arange(seq_len, device=tokens.device).unsqueeze(0)
        for depth in range(1, MAX_REASON_DEPTH + 1):
            h = self.embed(tokens) + self.pos(pos_ids)
            for blk in self.blocks: h = blk(h)
            logits = self.actor(self.norm(h[:, -1, :]))
            # Simplified convergence for mobile
        return logits, depth

server = Microdot()
@server.route('/api/execute', methods=['POST'])
def execute(req):
    cmd = req.json.get('command', '')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: exec(cmd, {'__builtins__': __builtins__}, {})
        except: print(traceback.format_exc())
    return {'output': buf.getvalue() or 'OK'}

@server.route('/')
def ui(req):
    return Response("<html><body style='background:#000;color:#00ff41;font-family:monospace'><h1>MONICO ANDROID v2.5</h1><div id='out'></div><input id='in'><script>document.getElementById('in').onkeydown=async(e)=>{if(e.key=='Enter'){const r=await fetch('/api/execute',{method:'POST',body:JSON.stringify({command:e.target.value}),headers:{'Content-Type':'application/json'}});const d=await r.json();document.getElementById('out').innerText+='\n> '+d.output}}</script></body></html>", content_type='text/html')

class MonicoAndroid(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title="MONICO ANDROID")
        threading.Thread(target=lambda: server.run(port=5000), daemon=True).start()
        self.web_view = toga.WebView(url="http://localhost:5000/", style=Pack(flex=1))
        self.main_window.content = self.web_view
        self.main_window.show()

def main(): return MonicoAndroid("MonicoAndroid", "com.jaykk99.monicoandroid")
if __name__ == '__main__': main().main_loop()