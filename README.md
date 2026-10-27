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
| ინფორმაციული უსაფრთხოება | Google Drive folder (the assignment files in it) | a folder you pick in the chat (the lecturer's folders), as `დავალება N - <your name>.pdf` |

Skills (in `hworkestrator/skills/`, also usable standalone in Claude Code):
- **cppwork** — lecture `.pptx` → Word with the "საილუსტრაციო მაგალითი" code, compile-checked, with generated screenshots. No LLM needed.
- **latexwork** — assignment → Claude solves it → LaTeX → PDF (XeLaTeX).
- **jupiterwork** — data-science assignment → Claude writes the notebook, it is executed (with plots), then the Georgian explanations are rewritten from the real outputs → `.ipynb`.
- **secwork** — information-security assignment (ciphers, encodings, key-space / probability questions, theory) → Claude writes each task's statement + Python code, the code is really run, then the analysis and "დასკვნები" are written from the real output → PDF (XeLaTeX; GTU banner + header, `ამოცანის პირობა` / code / output / `სურ. N.`) for upload, plus the same as .docx for manual edits.

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
- **ANTHROPIC_API_KEY** — console.anthropic.com → API keys (pay-per-use; latexwork, jupiterwork and secwork use it).
- **Google Drive** (info-security only), once:
  1. console.cloud.google.com → new project → *APIs & Services → Library* → enable **Google Drive API**.
  2. *OAuth consent screen* → External → fill the app name + your email → add yourself as a test user.
     Then press **Publish app** ("In production"; no review is needed for your own use). In "Testing" status Google
     expires the refresh token after 7 days and the bot stops seeing Drive.
  3. *Credentials → Create credentials → OAuth client ID → Desktop app* → **Download JSON** (`client_secret_….json`).
  4. `python scripts/google_auth.py ~/Downloads/client_secret_….json` → log in with the account that sees the course
     folder → "unverified app" → *Advanced → continue*. The script writes `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
     and `GOOGLE_REFRESH_TOKEN` into `.env` itself. Keep the JSON out of git (it is in `.gitignore`).
  5. `DRIVE_ROOT_FOLDER_ID` = the id at the end of the course folder's URL.
  The bot lists the **files** of that folder (newest first) as assignments; the number in the file name
  ("დავალება 3.pdf") becomes the assignment number. After generating, you browse the folder's subfolders (made by the
  lecturer, e.g. `4 დავ. მიმდინარე` → `<group>`) and press "ატვირთე აქ"; folders with the assignment number or your
  group are marked ⭐. Uploading the same file name again replaces it (new Drive version).

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
- ✅ secwork tested end-to-end with a fake Drive (`pytest`), and on the real Drive folder + a real Claude call (no upload).
- ⚠️ Drive + cppwork only works when the Drive task contains a lecture `.pptx` (Google Slides are exported to .pptx); for
  code tasks written as plain text use secwork.
- ⚠️ A task given only as an image (`.jpg`/`.png`) is not read yet — the bot lists it, but its text is not extracted.
