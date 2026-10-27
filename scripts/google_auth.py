#!/usr/bin/env python3
"""One-time: authorise Google Drive access and save GOOGLE_CLIENT_ID / _SECRET / _REFRESH_TOKEN into .env.

Needs an OAuth client of type "Desktop app" (Google Cloud → Credentials). Either
    python scripts/google_auth.py ~/Downloads/client_secret_XXXX.json     (the JSON Google lets you download)
or, with GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET already in .env,
    python scripts/google_auth.py
Log in with the Google account that owns/can edit the assignments folder.
"""
import http.server, json, os, re, sys, urllib.parse, webbrowser
from pathlib import Path

import requests

ENV = Path(__file__).resolve().parent.parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(ENV)
except ImportError:
    pass

if len(sys.argv) > 1:                  # client_secret_*.json: {"installed": {"client_id": ..., "client_secret": ...}}
    j = json.loads(Path(sys.argv[1]).expanduser().read_text())
    j = j.get("installed") or j.get("web") or j
    CID, SECRET = j["client_id"], j["client_secret"]
else:
    CID, SECRET = os.getenv("GOOGLE_CLIENT_ID", ""), os.getenv("GOOGLE_CLIENT_SECRET", "")
if not (CID and SECRET):
    sys.exit("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not found — pass the downloaded client_secret_*.json")
REDIRECT = "http://localhost:8765"
SCOPE = "https://www.googleapis.com/auth/drive"

url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": CID, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE,
    "access_type": "offline", "prompt": "consent"})
code = {}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code["v"] = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [None])[0]
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK, you can close this tab.")
    def log_message(self, *a): pass


def save_env(values):
    """Set KEY=value in .env (replacing an existing KEY= line, else appending)."""
    text = ENV.read_text(encoding="utf8") if ENV.exists() else ""
    for k, v in values.items():
        line = f"{k}={v}"
        text, n = re.subn(rf"^{k}=.*$", lambda _: line, text, flags=re.M)
        if not n:
            text = text.rstrip("\n") + "\n" + line + "\n"
    ENV.write_text(text, encoding="utf8")


print("Opening browser…"); webbrowser.open(url)
http.server.HTTPServer(("localhost", 8765), H).handle_request()
if not code.get("v"):
    sys.exit("No authorisation code received (access denied?)")
r = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": CID, "client_secret": SECRET, "code": code["v"],
    "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).json()
if "refresh_token" not in r:
    sys.exit(f"Google did not return a refresh token: {r.get('error_description') or r}")
save_env({"GOOGLE_CLIENT_ID": CID, "GOOGLE_CLIENT_SECRET": SECRET, "GOOGLE_REFRESH_TOKEN": r["refresh_token"]})
print(f"\n✅ Saved GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN into {ENV}")
print("   (on a cloud host, add the same three as secret environment variables)")
