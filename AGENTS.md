# Notes for AI coding agents

- **Project map:** `README.md` → *Architecture* and *Files*. Sources (`hworkestrator/sources/`) and skills
  (`hworkestrator/skills/`) each follow a small contract described in their `__init__.py`.
- **Setting the project up for a new student:** follow `.claude/skills/hw-setup/SKILL.md` (in Claude Code: `/hw-setup`).
  The step-by-step reference is `docs/AGENT_SETUP.md`.
- **Check the setup:** `python scripts/doctor.py`, which is read-only. **Tests:** `python -m pytest -q`; they use fakes
  and never touch real accounts.
- **Rules:** secrets and personal data only in `.env` (never commit it or print it). Never upload to a
  lecturer's platform unless the user explicitly asks. Test Claude-based skills with the cheapest model.
