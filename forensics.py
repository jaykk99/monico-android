import toga
import os
import hashlib

class ForensicsScanner:
    """Advanced on-device forensic auditing module for Monico Android."""
    def __init__(self, target_path="/"):
        self.target = target_path

    def deep_scan(self):
        summary = []
        for root, _, files in os.walk(self.target):
            for f in files[:100]:
                try:
                    fp = os.path.join(root, f)
                    h = hashlib.sha256(open(fp, 'rb').read()).hexdigest()
                    summary.append(f"{fp} | {h[:8]}")
                except: continue
        return "\n".join(summary)

# --- App Integration ---
# [Integrated into app.py via the Evolution Cycle]