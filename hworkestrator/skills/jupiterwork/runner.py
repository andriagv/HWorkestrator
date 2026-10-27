"""jupiterwork: data-science / ML assignment → Claude writes the notebook → it is executed (repairing errors) →
Claude writes the Georgian explanations from the REAL outputs → executed .ipynb with plots."""
import json
import re
import subprocess
import sys
from pathlib import Path

from ... import llm
from ...config import settings
from ...documents import TASK_WORDS, expected_tasks
from ..common import result_name

NEEDS = "text"
USES_LLM = True
BUILD = Path(__file__).parent / "scripts/build.py"
# output tokens per task by size; measured: a typical task is ~1.25k tokens of code and ~1k of explanation
TOKENS = {"S": 700, "M": 1250, "L": 2000}
EXPLAIN_TOKENS = {"S": 500, "M": 1000, "L": 1600}

SYSTEM = r"""You solve a data-science / machine-learning university assignment and write the
solution as a Jupyter notebook in jupytext "percent" format (NO header — it is added automatically).
Format:
    # %% [markdown]
    # ## დავალება 1. <title>
    # <task statement in the assignment's wording>

    # %%
    <python code>

    # %% [markdown]
    # ### პასუხი
    # TODO
Rules:
- Every markdown line starts with "# ". Georgian prose for headings/explanations; code and comments in English.
- Per task: title+statement, code cell(s) that really run, then the "### პასუხი" cell containing just the
  line "# TODO" — the Georgian explanations are written in a later step, from the real outputs, so do NOT
  write them now (but make the code print everything the questions of the task need).
- Datasets must work OFFLINE: use sklearn built-ins (Iris, Wine, Breast Cancer, Diabetes). Do not use Titanic /
  California Housing / any CSV that needs a download or does not exist. Keep one dataset per task family.
- random_state=42; print the metrics asked (accuracy, precision, recall, F1, MAE, MSE, RMSE, R²).
- Plots: matplotlib/seaborn, English labels, always plt.show().
- The notebook is executed top to bottom: imports in the first code cell, no input(), no files.
- Output ONLY the percent-format source: no markdown fences, no commentary."""

EXPLAIN_SYSTEM = r"""You write the explanations ("პასუხი") of a data-science notebook from its REAL outputs.
Return ONLY a JSON object {"1": "<markdown>", "2": "<markdown>", ...}: one entry per task number, the
markdown being the Georgian answer that fully answers every question/bullet of that task and cites the
actual numbers from the outputs. No code fences, no commentary, valid JSON (escape newlines as \\n)."""


def missing_tasks(cells_text, task_text):
    have = {int(n) for n in re.findall(r"^#\s*#+\s*" + TASK_WORDS + r"\s*(\d+)", cells_text, flags=re.M | re.I)}
    return [n for n in expected_tasks(task_text) if n not in have]


def splice_answers(cells_text, answers):
    """Replace the markdown after '### პასუხი' of task N with answers[N] (percent-format source)."""
    lines = cells_text.split("\n")
    for n, md in answers.items():
        head = next((i for i, l in enumerate(lines) if re.match(rf"^#\s*#+\s*{TASK_WORDS}\s*{n}\b", l, re.I)), None)
        if head is None:
            raise ValueError(f"task {n} not found")
        ans = next((i for i in range(head, len(lines)) if re.match(r"^#\s*#+\s*პასუხი", lines[i])), None)
        if ans is None:
            raise ValueError(f"answer heading of task {n} not found")
        end = next((i for i in range(ans + 1, len(lines)) if lines[i].startswith("# %%")), len(lines))
        body = [("# " + l) if l.strip() else "#" for l in str(md).strip().split("\n")]
        lines[ans + 1:end] = body + [""]
    return "\n".join(lines)


def _build(cells_text, folder, name, label, course):
    cells = Path(folder) / "cells.py"
    Path(folder).mkdir(parents=True, exist_ok=True)
    cells.write_text(cells_text, encoding="utf8")
    cmd = [sys.executable, str(BUILD), str(cells), "--week", f"{label} კვირა", "--course", course, "--name", name,
           "--outdir", str(folder), "--student", settings.student_name, "--group", settings.student_group]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


def run(task_text, label, outdir, course, model=None):
    """Claude writes the notebook source, we execute it (repairing errors), then Claude writes the
    explanations from the REAL outputs and we execute again."""
    outdir = Path(outdir)
    folder, name = outdir / "nb_result", f"Assignment_{label}"
    ask = lambda user, n=32000: llm.strip_fences(llm.claude(SYSTEM, user, n, model))   # noqa: E731
    cells = ask(f"Assignment text:\n\n{task_text}")
    for _ in range(2):                                    # make sure no task was skipped
        gone = missing_tasks(cells, task_text)
        if not gone:
            break
        cells = ask(f"Assignment text:\n\n{task_text}\n\nYour previous source:\n{cells}\n\n"
                    f"It is missing tasks {gone}. Return the FULL source with ALL tasks.")
    ok, log = _build(cells, folder, name, label, course)
    for _ in range(2):                                    # repair loop
        if ok:
            break
        cells = ask(f"Assignment text:\n\n{task_text}\n\nYour previous notebook source:\n{cells}\n\n"
                    f"Executing it failed with:\n{log[-2500:]}\n\nReturn the full corrected source.")
        ok, log = _build(cells, folder, name, label, course)
    if not ok:
        raise RuntimeError("notebook execution failed: " + (log.strip().splitlines() or ["?"])[-1])
    outputs = log.split("=== cell outputs", 1)[-1][:9000]
    ok2, log2, revised = False, log, cells
    for _ in range(2):                                    # pass 2: the explanations (one retry)
        try:
            raw = llm.strip_fences(llm.claude(
                EXPLAIN_SYSTEM, f"Assignment text:\n\n{task_text}\n\nNotebook source:\n{cells}\n\n"
                f"REAL outputs of running it:\n{outputs}", 16000, model))
            answers = {int(k): v for k, v in json.loads(raw).items()}
            if set(answers) < set(expected_tasks(task_text)):
                raise ValueError("answers missing")
            revised = splice_answers(cells, answers)
            ok2, log2 = _build(revised, folder, name, label, course)
            if ok2 and "# TODO" not in revised:
                break
        except Exception:
            ok2 = False
    if not ok2 or "# TODO" in revised:                    # never ship a notebook with "TODO" answers
        raise RuntimeError("ახსნების (პასუხების) გენერაცია ვერ მოხერხდა — სცადე თავიდან ან სხვა მოდელით")
    final = outdir / f"{result_name(label)}.ipynb"
    final.write_bytes((folder / f"{name}.ipynb").read_bytes())
    return final, [], log2 if ok2 else log


def estimate(task_in, sizes):
    # +15% margin: an execution error now and then triggers an extra repair call
    first_out = int((sum(TOKENS[z] for z in sizes) + 300) * 1.15)
    second_out = int((sum(EXPLAIN_TOKENS[z] for z in sizes) + 200) * 1.15)
    return [(task_in + 1400, first_out),                      # write the notebook (code)
            (task_in + first_out + 500, second_out)]          # explanations from real outputs
