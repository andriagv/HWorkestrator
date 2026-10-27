---
name: hw-setup
description: Interactive first-time setup of this HWorkestrator homework bot for the person who cloned it — interviews them (university, name, group, subjects, where assignments are posted and uploaded: Moodle / other LMS / Google Drive), collects their tokens step by step, connects the sources, builds or adapts a skill per subject from one example assignment, and verifies everything with scripts/doctor.py. Use when someone wants to set up, install, configure or adapt this repository/bot for themselves, or resumes an unfinished setup.
argument-hint: "[resume]"
---

# hw-setup — make this homework bot theirs

You are setting up this repository for the person in front of you. You end with **their** Telegram bot: it knows
their subjects, reads assignments from their platform, solves them with skills fitted to their courses, and
uploads only when they press ✅. Talk to them **in their language** (ask which one if unsure); keep code, comments
and commits in English.

Before the first question, read `README.md` (Architecture + Files) and skim `docs/AGENT_SETUP.md`. That file is
the reference for every step below: the token instructions, the source contract and the skill workflow.

## Ground rules
- **Secrets and personal data only in `.env`** (gitignored), never in code, commits or chat. Never print `.env`.
  Check values with `python scripts/doctor.py`.
- **They enter their own credentials.** Ask for one value at a time and say exactly where to find it; then write it
  into `.env` yourself. Password-based scripts (`scripts/get_moodle_token.py`) must be run by them in their terminal
  (suggest typing `! python scripts/get_moodle_token.py` in the prompt).
- **Nothing is uploaded during setup.** Uploads reach their lecturer; only do one if they explicitly ask.
- **Claude calls cost money:** test skills with `model="haiku"` and tell them the cost shown.
- Ask **one topic at a time**. Offer choices when the answer is one of a few options (use your question tool if
  you have one), and free text for names. After each block, confirm what you understood.

## Progress file — so setup can stop and resume
Keep `.setup/progress.md` (gitignored, no secrets) up to date after every answered block and finished step:
```markdown
# HWorkestrator setup progress
## Answers
- language: … | university: … | name in header: … | group: … | hosting: computer / cloud
- platform(s): …
## Subjects
| key | title | source | example assignment | example solution | upload to / file name | skill |
## Steps
- [ ] 1 environment  - [ ] 2 telegram  - [ ] 3 claude  - [ ] 4 sources  - [ ] 5 subjects
- [ ] 6 skills  - [ ] 7 look & language  - [ ] 8 verify  - [ ] 9 hand-over
## Notes / open questions
```
If the file exists (or the argument is `resume`), read it, summarise where they are, and continue from the
first unchecked step.

## The interview
**A. About them**
1. Which language should we talk in, and which language should the documents be written in?
2. Which university? *If it is GTU (Georgian Technical University), say this repo was built there: the Moodle
   source (elearning.gtu.ge), the headers and four skills may fit as they are. Then ask which subjects they take
   and fast-track: you mostly need their `.env` and `registry.py` subjects.*
3. Name and group, exactly as they must appear on the title block of their homework.

**B. Platform** — for each place they deal with, ask:
4. Where do lecturers **post** assignments? (Moodle, another LMS such as Canvas / Google Classroom / Blackboard,
   Google Drive folders, email/Telegram/other)
5. Where must solutions be **uploaded**, and how must the file be named?
For Moodle, get the site URL. For another LMS, find out (search the web if you need to) whether it has an API
students can use and how they would log in, before promising automation. If uploading can't be automated, the
bot generates the file and they upload it by hand.

**C. Subjects** — ask for the list, then for each subject:
6. Exact course name (as on the platform) and which platform it uses.
7. **One example assignment** (file path or pasted text/screenshot) and **one example of a good finished
   solution** (their own or a classmate's, or a precise description: file type, sections, header, code/screenshots/
   formulas, length).
8. Anything the lecturer is strict about (format, file type, naming, language).

**D. Hosting**
9. Their own computer (simplest; the bot runs while it's on) or the cloud (`docs/DEPLOY.md`)?

Write the answers into the progress file, show the summary table and get a "yes" before step 1.

## Steps (run `python scripts/doctor.py` after each one; it shows what is still missing)
1. **Environment.** `pip install -r requirements.txt`, `cp .env.example .env` if missing, `python -m pytest -q`
   (must pass before you change anything). Install system tools only for the skills they'll use
   (`doctor.py --offline` lists them).
2. **Telegram.** Walk them through @BotFather `/newbot` → `TELEGRAM_BOT_TOKEN`, and @userinfobot →
   `OWNER_TELEGRAM_ID`. Also write `STUDENT_NAME` and `STUDENT_GROUP` from the interview.
3. **Claude.** console.anthropic.com → API key → `ANTHROPIC_API_KEY`. Explain that it is pay-per-use and that
   the bot shows the price before every run.
4. **Sources**, one platform at a time, following `docs/AGENT_SETUP.md` Phase 3:
   - Moodle → `MOODLE_URL`, then they run `scripts/get_moodle_token.py`.
   - Google Drive → Cloud project, **enable Drive API in that project**, publish the OAuth app, download the
     Desktop-client JSON, then they run `scripts/google_auth.py <json>`. `DRIVE_ROOT_FOLDER_ID` comes from the folder URL.
     Look at the real folder (`pipeline.drive_folder()`) and adapt `sources/gdrive.py` if it's organised differently.
   - Another LMS → write `hworkestrator/sources/<platform>.py` following the contract in
     `sources/__init__.py`, register it in `SOURCES`, and add a fake to `tests/fakes.py` plus tests.
5. **Subjects.** Rewrite `SUBJECTS` in `hworkestrator/registry.py` from the interview: `title`, `source`, `match`
   (Moodle: a substring of the course name), `skills`. Remove this repo's example subjects they don't take.
   `doctor.py` must list items for every subject. For Moodle, check that weeks are found (`sources/weeks.py`).
6. **Skills — one per kind of homework**, following `docs/AGENT_SETUP.md` Phase 4. For each subject:
   compare its example assignment + solution with the existing skills (`cppwork`, `latexwork`, `jupiterwork`,
   `secwork`). Then **reuse, adapt (prompt/labels/layout), or create** `hworkestrator/skills/<name>/` (`runner.py` +
   `scripts/build.py` + `assets/`, following the contract in `skills/__init__.py`) and register it in
   `registry.SKILLS`. Run it on **their example assignment** with `model="haiku"`, render the result (PDF pages to
   images, open the docx) and compare it with their example solution section by section. Show it to them and
   iterate until they say it matches. Add a test that mocks `llm.claude`.
7. **Look & language.** Logos (`skills/*/assets/logo_*.png`), the university name and header labels (preambles,
   templates), the prompt language and the "GTU student" wording in each `runner.py`, and the result file name
   (`result_name()` in `skills/common.py`). Remove skills they don't use.
8. **Verify.** Run `python -m pytest -q` and `python scripts/doctor.py` (all ✅). Then start the bot with
   `python -m hworkestrator` (in the background if they prefer; output to `bot.log`). Only one instance may run
   per token, and `.env` is read at startup. They send `/start` and walk one real assignment to the upload screen;
   **pressing upload is their call**. For cloud hosting, follow `docs/DEPLOY.md` and stop the local bot first.
9. **Hand-over** (in their language): how to start, stop and restart the bot; what's in `.env`; their subjects →
   skills; how to add a subject or skill later (*"run /hw-setup resume, or give me the subject name + one example
   assignment"*); what wasn't tested; and known limits (assignments that are only images aren't read). Offer to
   commit the code changes to *their* fork. Never commit `.env` or `.setup/`.
