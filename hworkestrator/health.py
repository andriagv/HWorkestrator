"""Tiny HTTP endpoint so hosts that need a listening port / HTTP pings (Hugging Face Spaces, uptime
monitors, Render...) see the bot as alive. Enabled only when HEALTH_PORT (or PORT in health mode) is set."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"HWorkestrator bot is running\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_HEAD = do_GET

    def log_message(self, *args):          # keep the bot log clean
        pass


def start(port):
    server = HTTPServer(("0.0.0.0", int(port)), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
