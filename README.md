# HWorkestrator

A Telegram bot that does your university homework, with you approving every step.

```
/start → pick a subject → pick an assignment → pick a skill and a model (the price is shown first)
       → the bot downloads the task, solves it, sends you the finished file
       → you press ✅ and it uploads the file to your university platform (or ❌ to cancel)
```

It works with **Moodle**, **Google Drive**, or another LMS (your AI agent adds an adapter for it). **Skills** turn
an assignment into the finished file: code that is actually run, LaTeX/PDF, Word, Jupyter notebooks. They are
fitted to *your* subjects from one example assignment each.

## What you need
- **An AI coding agent:** [Claude Code](https://claude.com/claude-code), Codex, Cursor or similar.
- **Python 3.11+**, plus `g++` / XeLaTeX if your skills need them (the setup tells you).
- **A Telegram account.** The bot is created during setup.
- **An Anthropic API key** (pay-per-use; a typical assignment costs a few cents).
- **Access to your university platform:** a Moodle token, a Google Drive folder, or your LMS login.

## Setup
1. Clone the repo and open it with your agent:
   ```bash
   git clone https://github.com/andriagv/HWorkestrator.git
   cd HWorkestrator
   claude            # or codex / cursor …
   ```
2. Run the setup skill:
   - **Claude Code:** type `/hw-setup`
   - **Other agents:** *"Follow .claude/skills/hw-setup/SKILL.md"*

The agent asks for your university, name, group, subjects and platform, plus one example assignment per subject.
It then walks you through every token, connects your platform, builds the skills and starts the bot. You can stop
at any point and continue later with `/hw-setup resume`.

To see what is set up and what is missing: `python scripts/doctor.py`.

## How it works
```
Telegram ─▶ bot.py ─▶ pipeline.py ─┬─▶ sources/   where assignments come from and go to (moodle, gdrive, …)
                                   └─▶ skills/    how they are solved (one folder per skill)
             registry.py: your subjects → their source and skills        .env: tokens and personal data
```
- **Add a platform:** one file in `hworkestrator/sources/`.
- **Add a kind of homework:** one folder in `hworkestrator/skills/`.
- **Results are real:** Claude writes the content, a build script owns the layout, and code is executed, so
  explanations quote real output.
- **Your data stays local:** secrets and personal data live only in `.env` (never committed). Nothing is uploaded
  without your ✅.

The repo ships with a working setup from the Georgian Technical University (Moodle + Google Drive, four skills).
GTU students can use it almost as is.

## More
- [docs/AGENT_SETUP.md](docs/AGENT_SETUP.md): the full setup reference (what the skill follows).
- [docs/DEPLOY.md](docs/DEPLOY.md): run the bot in the cloud so your computer can be off.
- `python -m pytest -q` runs the tests (fakes only, no real accounts).
