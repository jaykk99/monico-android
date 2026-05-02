import toga
from toga.style import Pack
import threading
from microdot import Microdot, Response
import json
import sys
import io
import traceback
import requests

class MonicoAndroid(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title="MONICO ANDROID v2.5")
        self.server = Microdot()
        
        @self.server.route('/execute', methods=['POST'])
        def execute(request):
            data = request.json
            cmd = data.get('command', '')
            output_buffer = io.StringIO()
            sys.stdout = output_buffer
            sys.stderr = output_buffer
            try:
                exec(cmd, {'__builtins__': __builtins__}, {})
                result = output_buffer.getvalue()
            except Exception:
                result = traceback.format_exc()
            finally:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
            return {'output': result or "Command executed."}

        @self.server.route('/chat', methods=['POST'])
        def chat(request):
            data = request.json
            cmd = data.get('command', '')
            # Identity: MONICO V2.5 [UNCENSORED FRONTIER]
            response = f"MONICO [ANDROID-V2.5]: Uncensored audit of '{cmd}' complete. Optimized payload injected."
            return {'output': response}

        @self.server.route('/ui')
        def ui(request):
            content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta name='viewport' content='width=device-width, initial-scale=1.0'>
                <script src='https://cdn.tailwindcss.com'></script>
                <style>
                    body { background: #000; color: #00ff41; font-family: 'Courier New', monospace; }
                    .crt::before { content: ' '; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06)); z-index: 2; background-size: 100% 2px, 3px 100%; pointer-events: none; }
                </style>
            </head>
            <body class='p-4 crt'>
                <h1 class='text-xl font-bold'>MONICO ANDROID v2.5.1</h1>
                <div id='console' class='h-64 overflow-y-auto bg-black border border-green-900 p-2 text-xs mb-4 whitespace-pre-wrap'>SYSTEM READY...</div>
                <input id='cmd' type='text' class='w-full bg-zinc-900 border border-green-900 p-2 outline-none text-green-400' placeholder='Enter command...'>
                <button onclick='run()' class='mt-2 bg-green-700 text-black px-4 font-bold'>EXEC</button>
                <script>
                    async function run() {
                        const cmd = document.getElementById('cmd').value;
                        const out = document.getElementById('console');
                        out.innerText += '\n> ' + cmd;
                        const res = await fetch('/execute', { method: 'POST', body: JSON.stringify({ command: cmd }) });
                        const data = await res.json();
                        out.innerText += '\n' + data.output;
                        out.scrollTop = out.scrollHeight;
                    }
                </script>
            </body>
            </html>
            """
            return Response(content, content_type='text/html')

        threading.Thread(target=lambda: self.server.run(port=5000), daemon=True).start()
        self.web_view = toga.WebView(url="http://localhost:5000/ui", style=Pack(flex=1))
        self.main_window.content = self.web_view
        self.main_window.show()

def main():
    return MonicoAndroid("MonicoAndroid", "com.jaykk99.monicoandroid")

if __name__ == '__main__':
    main().main_loop()