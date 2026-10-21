#!/usr/bin/env python3
"""One-time: authorise Google Drive access and print the refresh token for .env.

Needs GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (OAuth client of type "Desktop app").
Run locally:  python scripts/google_auth.py
Log in with the Google account that owns/can edit the assignments folder.
"""
import http.server, os, urllib.parse, webbrowser

import requests

CID, SECRET = os.environ["GOOGLE_CLIENT_ID"], os.environ["GOOGLE_CLIENT_SECRET"]
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


print("Opening browser…"); webbrowser.open(url)
http.server.HTTPServer(("localhost", 8765), H).handle_request()
r = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": CID, "client_secret": SECRET, "code": code["v"],
    "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).json()
print("\nGOOGLE_REFRESH_TOKEN=" + r["refresh_token"])
