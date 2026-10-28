# Turning HWorkestrator into *your* homework bot: instructions for an AI coding agent

You are an AI coding agent (Claude Code, Codex, Cursor…) working in a fresh clone of this repository for a
student. Your job is to build **their** homework automation: their university platform, their subjects and the
kind of assignments they get. Talk to the student in **their** language. Code, comments and commits stay in English.

This repository was built by a student of the Georgian Technical University (GTU). Everything GTU-specific in it
(Moodle at elearning.gtu.ge, four subjects, four skills, Georgian document headers) is **one working example**,
not the product. Reuse what fits, replace what doesn't.

## The system in one picture
Read the **Architecture** and **Files** sections of `README.md` first. In short:
```
Telegram bot (always)               hworkestrator/bot.py
   │  subject → assignment → skill → model/price → result → ✅ upload
   ▼
Pipeline                            hworkestrator/pipeline.py   list_items → overview → prepare → submit
   │                                     (knows no platform and no skill)
   ├── Sources (one per subject)    hworkestrator/sources/      moodle.py, gdrive.py, <another LMS>.py
   │      contract: list_items / overview / submit  — see sources/__init__.py
   └── Skills (per kind of homework) hworkestrator/skills/<name>/  runner.py + scripts/ + assets/
          contract: NEEDS / USES_LLM / run / estimate — see skills/__init__.py
Configuration: hworkestrator/registry.py (subjects → source + skills; skill labels) · .env (tokens, personal data)
```
What every student gets: the Telegram flow, with the human approving every upload. Where assignments come from,
where results go, and how each subject's homework is solved are what you build together with the student.

## Ground rules
- **Secrets and personal data only in `.env`** (gitignored) or the host's secret settings, never in code,
  templates, tests, commits or chat. Check a value is set with `grep -c '^NAME=.' .env`; don't print `.env`.
- **The student enters their own credentials.** Ask for one value at a time, tell them where to find it, and write
  it into `.env` for them. A script that needs a password (`scripts/get_moodle_token.py`) asks for it itself.
- **Uploading is outward-facing** (it goes to the lecturer). During setup only list, read and generate locally.
  Upload only when the student explicitly asks, into a place they chose.
- **Running a skill with Claude costs money.** Test with `model="haiku"` and tell the student the cost shown.
- **`.env` gotcha:** `python-dotenv` reads `KEY=   # comment` as the value `# comment`. Comments go on their own
  line; empty values stay empty.
- **Only one running bot per token**, and `.env` is read only at startup. Restart the bot after changing `.env`.

## Phase 1 — interview (ask; don't guess)
Ask these questions, then summarise the answers and get the student's confirmation before editing anything.
1. **Who:** university, name and group exactly as they must appear in the document header, document language.
2. **Platform:** where do lecturers post assignments and collect solutions? Moodle (any university's), another LMS
   (Canvas, Google Classroom, Blackboard…), Google Drive folders, or a mix? Per subject.
3. **Subjects:** the exact name of every subject they want automated, and for each one:
   - **one example assignment** (the file the lecturer gave, or a screenshot/text);
   - **one example of a finished solution** in the expected form (their own or a classmate's), or a precise
     description: file type, structure, header, code/screenshots/formulas, length, language;
   - where that subject's solution is uploaded and how the file must be named.
4. **Hosting:** their own computer (simplest; the bot runs while it is on) or the cloud (`docs/DEPLOY.md`).

If the student is from GTU and takes the same kind of subjects, the existing setup may fit almost unchanged.
Still check every subject against an example.

## Phase 2 — the common core: environment + Telegram + Claude
1. Python 3.11+, then `pip install -r requirements.txt`; `cp .env.example .env`.
2. `python -m pytest -q` passes before you change anything (tests use dummy data, never `.env`).
3. Telegram: @BotFather → `/newbot` → `TELEGRAM_BOT_TOKEN`; @userinfobot → `OWNER_TELEGRAM_ID` (the bot answers
   only this id). Claude: console.anthropic.com → `ANTHROPIC_API_KEY` (`ANTHROPIC_MODEL` = default model).
4. `STUDENT_NAME`, `STUDENT_GROUP`.
5. System tools only as the chosen skills need them (for example `g++`, XeLaTeX + fonts). The `Dockerfile` lists them.

## Phase 3 — sources: where assignments come from and where results go
A source answers four questions for a subject: *what can be chosen* (`list_items`), *what is in it*
(`overview` → the downloaded files, the assignment text, the upload targets), *where can it be uploaded* (targets) and
*how to upload* (`submit`). Each source is one module in `hworkestrator/sources/`, registered in `SOURCES` in
`sources/__init__.py`. A subject's `"source"` picks the module, and every upload target carries `{"kind": <source>}`.

**Moodle (any university running Moodle):**
- `MOODLE_URL` = their site. The student runs `python scripts/get_moodle_token.py`, which saves `MOODLE_TOKEN`. If
  the site disables the mobile web service, check *Preferences → Security keys*. If there is no token at all,
  tell them Moodle cannot be automated this way.
- Subject entry: `"source": "moodle", "match": "<substring of the course name>"`.
- Weeks are found from section names like "VI კვირა" / "Week 6" (`sources/weeks.py`). Run `overview()` on a real week; if
  nothing is found, adapt `find_week_section` / `week_sections` to their section naming.

**Google Drive:**
1. console.cloud.google.com → new project → *Library* → **Google Drive API → Enable**. Check that the project
   selector shows this project; a 403 `SERVICE_DISABLED` means the API is enabled in the wrong project.
2. *OAuth consent screen* → External → add the student as a test user → **Publish app**. In "Testing" status the
   token expires after 7 days.
3. *Credentials → OAuth client ID → Desktop app* → **Download JSON** → the student runs
   `python scripts/google_auth.py <client_secret.json>`, which writes the three `GOOGLE_*` values into `.env`.
4. `DRIVE_ROOT_FOLDER_ID` = the id at the end of the course folder's URL. Subject entry: `"source": "drive"`.
5. The current code expects assignment *files* in that folder (number in the file name) and lets the student pick
   the upload folder in the chat. Look at the real folder (`pipeline.drive_folder()`) and adapt `list_items`,
   `overview` and `folder` in `sources/gdrive.py` if their lecturer organises it differently (for example one folder per
   assignment, or a separate folder per subject). One root folder per subject means moving the folder id from
   `.env` into the subject entry.

**Another LMS or source:** add `sources/<platform>.py` in the same shape as `sources/moodle.py`: a small client
class over its REST API (download + upload), then the three functions `list_items`, `overview`, `submit`. Register
it in `SOURCES` and use its name as the subject's `"source"`. Add a fake of it in `tests/fakes.py` with tests. Confirm that the platform has an API and how the student authenticates (token,
OAuth) **before** writing code. If uploads cannot be automated, let the bot generate and send the file, and the
student uploads it by hand. That is a fine result.

Check each source read-only:
`python -c "from hworkestrator import pipeline; print(pipeline.list_items('<subject key>'))"`.

## Phase 4 — skills: one per kind of homework, built from the student's example
A skill turns an assignment into the finished file. The existing ones are templates to copy from:

| skill | input → output | pattern worth copying |
|---|---|---|
| `cppwork` | lecture .pptx / .pdf / .docx → Word with C++ examples + screenshots | no LLM; extract → compile → render |
| `latexwork` | math/theory → LaTeX → PDF | Claude writes a body, a fixed preamble owns the layout |
| `jupiterwork` | data-science tasks → executed .ipynb | write code → **run it** → repair → explain from real outputs |
| `secwork` | security tasks → PDF + docx with code/output | JSON solution → run code → analysis from real output → PDF |

**Workflow for each subject:**
1. Read the example assignment and the example solution. Write down what the result must contain: the file type,
   sections and their names, header fields, what is computed vs. written, code language, plots/screenshots/formulas,
   and how tasks are numbered.
2. If an existing skill already produces that, reuse it. Adjust its prompt and labels if needed.
3. Otherwise **create `skills/<name>/`**:
   - `scripts/build.py`: a standalone script that turns a structured solution (JSON or a text body) into the final
     file, with the header taken from `--student/--group/--course` (never hard-coded). It owns the layout
     completely, so the model never produces formatting.
   - `assets/`: logos and templates (a .docx template, a LaTeX preamble).
   - `runner.py` (the contract is in `skills/__init__.py`): `NEEDS`, `USES_LLM`, `estimate()`, and `run()` — a Claude
     prompt (via `llm.claude`) that returns the structured solution → build → **verify** (run
     the code, compile, execute; feed errors back for at most 2 repairs) → if the text interprets results, a
     second Claude call writes it **from the real outputs** → final build. Never ship placeholders.
   - Register it: one line in `registry.SKILLS` (button label) and the subject's `"skills"` list. Nothing else
     changes: the pipeline, prices and bot pick it up through the contract.
   - A test in `tests/test_skills.py` that mocks `llm.claude` and runs the real build.
4. **Prove it on the example:** run the skill on the student's example assignment (`model="haiku"`). Render the
   output (PDF pages to images, open the docx) and compare it with the example solution, section by section. Fix
   the differences, then show the student and iterate until they say it matches.

**Look and language:** logos are in `skills/*/assets/logo_*.png`. Header labels and the university name are in
the preambles, templates and build scripts. Prompts in each `skills/<name>/runner.py` currently say "GTU student" and ask for
Georgian: change them to the student's university and language. `result_name()` in `skills/common.py` sets the file
name. Use what
their lecturers expect.

**Remove what they don't use:** subjects, skills and sources from this example that the student doesn't need,
plus the tests that cover them. Keep `pytest` green.

## Phase 5 — end-to-end check (no upload)
1. `python -m pytest -q`.
2. For every subject: `list_items` → `overview` on a real assignment. Show the student what was found.
3. Generate one real result per skill with `model="haiku"`, and compare it once more with the student's example.
4. `python -m hworkestrator`. The student sends `/start` and walks one assignment through to the upload screen.
   **Pressing upload is their decision.**

## Phase 6 — hand-over
Tell the student, in their language: what runs where, and how to start, stop and restart it; which values are in
`.env`; which subjects and skills exist and how to add one later (*"give the agent the subject name and one example
assignment + solution, and point it at Phase 4"*); what was not tested; and the known limits (for example,
assignments that are only images are not read). Commit the code changes if they want, never `.env`.
