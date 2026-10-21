#!/usr/bin/env python3
"""Ask Moodle for a mobile-web-service token and write it to .env as MOODLE_TOKEN.

Run it yourself in a terminal: it prompts for your elearning.gtu.ge username/password
(password is not echoed), sends them ONLY to the Moodle server, and stores just the token.
Nothing is printed except success/failure.

    python scripts/get_moodle_token.py
"""
import getpass, os, re, sys

import requests

URL = os.getenv("MOODLE_URL", "https://elearning.gtu.ge").rstrip("/")
user = input("elearning username: ").strip()
pw = getpass.getpass("elearning password: ")

r = requests.post(f"{URL}/login/token.php",
                  data={"username": user, "password": pw, "service": "moodle_mobile_app"}, timeout=30)
j = r.json()
if "token" not in j:
    print("No token:", j.get("error") or j, "| code:", j.get("errorcode"))
    print("-> the mobile web service is probably disabled for students on this site.")
    sys.exit(1)

env = ".env"
text = open(env, encoding="utf8").read() if os.path.exists(env) else ""
line = f"MOODLE_TOKEN={j['token']}"
text = re.sub(r"^MOODLE_TOKEN=.*$", line, text, flags=re.M) if re.search(r"^MOODLE_TOKEN=", text, re.M) \
    else text + ("\n" if text and not text.endswith("\n") else "") + line + "\n"
open(env, "w", encoding="utf8").write(text)
os.chmod(env, 0o600)
print("OK — MOODLE_TOKEN saved to .env")
