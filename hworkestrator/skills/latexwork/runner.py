"""latexwork: math/theory assignment → Claude writes the LaTeX body → XeLaTeX builds the PDF (fixed header)."""
import shutil
import sys
from pathlib import Path

from ... import llm
from ...config import settings
from ..common import header_args, result_name, run_script

NEEDS = "text"
USES_LLM = True
BUILD = Path(__file__).parent / "scripts/build.py"
TOKENS = {"S": 1500, "M": 3500, "L": 6000}          # output tokens per task by size (measured ~3.5k typical)

SYSTEM = r"""You solve a university assignment for a GTU student and
write the solution as the BODY of a LaTeX document (no preamble, no \begin{document}).
Rules:
- Georgian prose (natural Georgian), formulas in LaTeX math. XeLaTeX with FreeSerif is used.
- For every task in the assignment write:
    \problem{N}{<the task statement, in the assignment's own wording>}
    \answer
    <full solution: key steps, computations, final result>
  If the assignment contains a single task, use one \problem and organise the answer into parts.
- Available packages: amsmath, amssymb, mathtools, cancel, enumitem, booktabs, array, tikz.
  Georgian words inside math: \text{...}. Use pmatrix/align*/cases/tabular as needed.
- Be mathematically careful: double-check every arithmetic result. If the task is ambiguous,
  choose a concrete reasonable option, say so in one sentence and use it consistently
  (the student's name is {student} unless told otherwise).
- Output ONLY the LaTeX body, no markdown fences, no commentary."""


def solve_to_latex(task_text, model=None):
    body = llm.strip_fences(llm.claude(SYSTEM.replace("{student}", settings.student_name or "the student"),
                                       f"Assignment text:\n\n{task_text}", model=model))
    if "\\problem" not in body:
        raise RuntimeError("model output has no \\problem — unexpected format")
    return body


def run(task_text, label, outdir, course, model=None):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    body = outdir / "body.tex"
    body.write_text(solve_to_latex(task_text, model), encoding="utf8")
    folder, name = outdir / "latex_result", f"Assignment_{label}"
    log = run_script([sys.executable, str(BUILD), str(body), "--week", label, "--name", name,
                      "--outdir", str(folder), *header_args(course)])
    final = outdir / f"{result_name(label)}.pdf"
    final.write_bytes((folder / f"{name}.pdf").read_bytes())
    zipped = Path(shutil.make_archive(str(outdir / f"{name}_tex"), "zip", folder))
    return final, [zipped], log


def estimate(task_in, sizes):
    return [(task_in + 900, sum(TOKENS[z] for z in sizes) + 500)]
