#!/usr/bin/env python3
"""Check the whole setup without changing anything: Python packages, system tools, .env values, and the
connections to Telegram, Claude, Moodle and Google Drive that the configured subjects need.

    python scripts/doctor.py            # everything, including network checks
    python scripts/doctor.py --offline  # no network calls

Prints one line per check (✅ ok / ❌ problem + what to do / ➖ not needed) and exits 1 if anything failed.
Secret values are never printed.
"""
import argparse
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)                                  # config.py loads .env from the working directory

failed = 0


def show(ok, what, hint=""):
    global failed
    mark = {True: "✅", False: "❌", None: "➖"}[ok]
    failed += ok is False
    print(f"{mark} {what}" + (f"\n     → {hint}" if hint and ok is False else ""))


def check(what, fn, hint=""):
    """Run fn(); a returned string is shown as detail, an exception is a failure."""
    try:
        detail = fn()
        show(True, what + (f": {detail}" if detail else ""))
    except Exception as e:  # noqa: BLE001 — every failure is reported, never raised
        show(False, f"{what}: {str(e).splitlines()[0][:160]}", hint)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip the network checks")
    online = not ap.parse_args().offline

    print("== Python")
    show(sys.version_info >= (3, 11), f"Python {sys.version.split()[0]}", "install Python 3.11 or newer")
    for mod in ("telegram", "anthropic", "requests", "docx", "pypdf", "bs4", "PIL", "dotenv"):
        check(f"package {mod}", lambda m=mod: importlib.import_module(m) and "", "pip install -r requirements.txt")

    print("\n== .env and subjects")
    show(Path(".env").exists(), ".env exists", "cp .env.example .env")
    from hworkestrator import pricing, sources
    from hworkestrator.config import settings
    from hworkestrator.registry import SKILLS, SUBJECTS
    used_sources = {s["source"] for s in SUBJECTS.values()}
    llm_skills = [k for k in SKILLS if pricing.uses_llm(k)]
    print(f"   subjects: {', '.join(f'{k} ({s['source']})' for k, s in SUBJECTS.items())}")
    print(f"   skills:   {', '.join(SKILLS)}")
    for src in used_sources:
        check(f"source '{src}' exists", lambda s=src: sources.get(s) and "", "add it to SOURCES in sources/__init__.py")

    def need(name, value, hint, required=True):
        show(bool(value) if required else None, f"{name} is set" if value or required else f"{name} (not needed)",
             hint)
    need("TELEGRAM_BOT_TOKEN", settings.telegram_token, "Telegram → @BotFather → /newbot")
    need("OWNER_TELEGRAM_ID", settings.owner_id, "Telegram → @userinfobot → your numeric id")
    need("STUDENT_NAME", settings.student_name, "your name exactly as in the document header")
    need("STUDENT_GROUP", settings.student_group, "your group as in the document header")
    need("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY"), "console.anthropic.com → API keys",
         required=bool(llm_skills))
    need("MOODLE_TOKEN", settings.moodle_token, "python scripts/get_moodle_token.py", required="moodle" in used_sources)
    for name, value in (("GOOGLE_CLIENT_ID", settings.google_client_id),
                        ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
                        ("GOOGLE_REFRESH_TOKEN", settings.google_refresh_token),
                        ("DRIVE_ROOT_FOLDER_ID", settings.drive_root_folder_id)):
        need(name, value, "see README → Google Drive (scripts/google_auth.py writes the GOOGLE_* values)",
             required="drive" in used_sources)
    bad = [k for k, v in os.environ.items() if v.strip().startswith("#")]
    show(not bad, "no comment text read as a value" + (f" ({', '.join(bad)})" if bad else ""),
         "in .env, put comments on their own line: `KEY=   # comment` makes the value '# comment'")

    print("\n== System tools (only for the skills in registry.SKILLS)")
    if "cppwork" in SKILLS:
        show(bool(shutil.which("g++")), "g++ (cppwork)", "install a C++ compiler (Xcode CLT / build-essential)")
    if {"latexwork", "secwork"} & set(SKILLS):
        show(bool(shutil.which("xelatex")), "xelatex (latexwork, secwork)", "install MacTeX / texlive-xetex")
        if shutil.which("kpsewhich"):
            for font in ("FreeSerif.otf", "FreeMono.otf"):
                found = subprocess.run(["kpsewhich", font], capture_output=True, text=True).stdout.strip()
                show(bool(found), f"font {font}", "install GNU FreeFont (fonts-freefont-otf / tex-gyre)")

    if not online:
        print("\n(network checks skipped)")
        return
    print("\n== Connections")
    import requests
    if settings.telegram_token:
        base = settings.telegram_api_base or "https://api.telegram.org"

        def tg():
            j = requests.get(f"{base}/bot{settings.telegram_token}/getMe", timeout=20).json()
            if not j.get("ok"):
                raise RuntimeError(j.get("description", "not ok"))
            return "@" + j["result"]["username"]
        check("Telegram bot", tg, "check TELEGRAM_BOT_TOKEN (or TELEGRAM_API_BASE if Telegram is blocked)")
    if llm_skills and os.getenv("ANTHROPIC_API_KEY"):
        def claude():
            import anthropic
            anthropic.Anthropic().models.list(limit=1)
            return f"key works, default model {settings.anthropic_model}"
        check("Claude API", claude, "check ANTHROPIC_API_KEY and the account's credit")
    if "moodle" in used_sources and settings.moodle_token:
        def moodle():
            info = sources.get("moodle").client().call("core_webservice_get_site_info")
            return f"{info.get('sitename')} as {info.get('fullname')}"
        check(f"Moodle {settings.moodle_url}", moodle, "check MOODLE_URL / MOODLE_TOKEN")
    if "drive" in used_sources and settings.google_refresh_token:
        def drive():
            f = sources.get("drive").client().get(settings.drive_root_folder_id)
            return f"course folder '{f['name']}'"
        check("Google Drive", drive, "403 SERVICE_DISABLED → enable Drive API in the right project; "
                                     "invalid_grant → run scripts/google_auth.py again (publish the OAuth app)")
    print("\n== Subjects (what the bot would list)")
    from hworkestrator import pipeline
    for key, s in SUBJECTS.items():
        check(f"{key} — {s['title']}", lambda k=key: f"{len(pipeline.list_items(k))} item(s)",
              "fix the subject's source settings in registry.py (e.g. the Moodle 'match' text)")


if __name__ == "__main__":
    main()
    print("\nAll good." if not failed else f"\n{failed} problem(s) — fix the ❌ lines above.")
    sys.exit(1 if failed else 0)
