# Contributing

Thanks for helping! HWorkestrator becomes more useful with every university platform and every kind of homework
it supports. Contributions of both kinds are welcome.

## Good first contributions
- **Your university's platform**: an adapter for another LMS (Canvas, Google Classroom, Blackboard…) or a Moodle
  quirk (week/section naming in `sources/weeks.py`).
- **A new skill**: a kind of homework the existing skills don't cover (essays, SQL, MATLAB, lab reports…).
- **Fixes and docs**: anything that confused you during `/hw-setup`.

Not sure where to start? Open an [issue](../../issues/new/choose) or a [discussion](../../discussions).

## How the code is organised
See *How it works* in the [README](README.md). In short:
- **A platform** = one module in `hworkestrator/sources/` with `list_items`, `overview`, `submit`
  (contract in `sources/__init__.py`), registered in `SOURCES`.
- **A skill** = one folder in `hworkestrator/skills/<name>/` with `runner.py` (`NEEDS`, `USES_LLM`, `run`, `estimate`;
  contract in `skills/__init__.py`), `scripts/` and `assets/`, plus one line in `registry.SKILLS`.

An AI coding agent can do most of this for you: point it at [docs/AGENT_SETUP.md](docs/AGENT_SETUP.md).

## Workflow
1. Fork, create a branch, and make your change.
2. Run `python -m pytest -q`. Add tests for new sources (with a fake in `tests/fakes.py`) and skills (mock
   `llm.claude`). Tests must never touch real accounts.
3. Open a pull request that says what it does and how you tested it.

## Rules
- **No secrets or personal data** in code, tests, examples or screenshots: no tokens, names, group numbers or
  real course folder ids. They belong in `.env`.
- **Keep the human in the loop.** Nothing may be uploaded without the user's explicit ✅.
- Code and comments are in English; user-facing text can be in the user's language.
