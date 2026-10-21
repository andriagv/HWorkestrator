# HWorkestrator

Telegram bot that does university homework end-to-end, with a human in the loop:

```
you → Telegram: choose subject → choose skill → type week (VI)
bot → finds the assignment (Moodle / Google Drive) → generates the file → sends it to the chat
you → ✅ upload     (or 🔁 redo / ❌ cancel)
bot → uploads it into the assignment slot
```

| Subject | Source | Upload target |
|---|---|---|
| მონაცემთა სტრუქტურები და ალგორითმები, SPSS, AI | elearning.gtu.ge (Moodle web-service API) | the week's assignment ("Add submission") |
| ინფორმაციული უსაფრთხოება | Google Drive folder | `დავალება N/<your group folder>/` as `დავალება N - <your name>` |

Skills (in `hworkestrator/skills/`, also usable standalone in Claude Code):
- **cppwork** — lecture `.pptx` → Word with the "საილუსტრაციო მაგალითი" code, compile-checked, with generated screenshots. No LLM needed.
- **latexwork** — assignment → Claude solves it → LaTeX → PDF (XeLaTeX).

Add a subject or skill: edit `hworkestrator/registry.py` (+ a branch in `pipeline.py` for new skill types).

## Setup

```bash
cp .env.example .env     # fill in the values below
pip install -r requirements.txt
python -m hworkestrator  # polling mode
```
Needs `g++` and `xelatex` locally (or use the Dockerfile).

### Where to get each value
- **TELEGRAM_BOT_TOKEN** — Telegram → @BotFather → `/newbot`.
- **OWNER_TELEGRAM_ID** — Telegram → @userinfobot → your numeric id. The bot ignores everyone else.
- **MOODLE_TOKEN** — elearning.gtu.ge → profile → Preferences → **Security keys** → *Moodle mobile web service*. Treat it like a password.
- **ANTHROPIC_API_KEY** — console.anthropic.com → API keys (pay-per-use; only latexwork uses it).
- **Google Drive** (info-security only): Google Cloud Console → new project → enable *Drive API* → OAuth consent screen → create an *OAuth client ID (Desktop app)* → put the id/secret in `.env` → run `python scripts/google_auth.py` once, log in with the account that has the folder, copy the printed `GOOGLE_REFRESH_TOKEN`.

**Personal data** (`STUDENT_NAME`, `STUDENT_GROUP`, Drive folder ids) is read only from `.env`; the code and the Word/LaTeX templates contain none. The course name in the header is taken from the subject (`registry.py`).

Never commit `.env`; on a host, set these as secret environment variables.

## Hosting (free)
The app is a Docker image (`Dockerfile`) and runs either way:
- `BOT_MODE=polling` — needs an always-on process.
- `BOT_MODE=webhook` + `WEBHOOK_URL=https://<host>` — for hosts that sleep when idle (e.g. Cloud Run, Render).

## Status
- ✅ cppwork on Moodle: tested with a fake Moodle (`pytest`) incl. real .pptx → .docx.
- ✅ latexwork build + bot wiring tested; the Claude call needs `ANTHROPIC_API_KEY`.
- ⚠️ Not yet tested against the real elearning.gtu.ge / Google Drive / Telegram (needs the tokens).
- ⚠️ Drive + cppwork only works when the Drive task contains a lecture `.pptx`; code tasks written from a plain task text are not implemented yet.
