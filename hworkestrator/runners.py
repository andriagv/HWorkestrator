"""Run the two skills: cppwork (deterministic) and latexwork (Claude solves, XeLaTeX builds)."""
import html
import re
import subprocess
import sys
from pathlib import Path

from .config import settings

SKILLS_DIR = Path(__file__).parent / "skills"

LATEX_SYSTEM = r"""You solve a university assignment for a GTU student and
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


def _run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        lines = [l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()]
        raise RuntimeError(lines[-1] if lines else f"{Path(cmd[1]).name} failed")
    return r.stdout


def result_name(week_label):
    return f"დავალება {week_label} - {settings.student_name}"


# ---------- cppwork ----------
def header_args(course):
    """Student header data for the skills' build scripts (comes from .env, never from code)."""
    return ["--student", settings.student_name, "--group", settings.student_group, "--course", course]


def run_cppwork(pptx, week_label, outdir, course, stdin=None):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{result_name(week_label)}.docx"
    cmd = [sys.executable, str(SKILLS_DIR / "cppwork/scripts/build.py"), str(pptx),
           "--week", week_label, "--out", str(out), *header_args(course)]
    for item in stdin or []:
        cmd += ["--stdin", item]
    log = _run(cmd)
    return out, log


# ---------- text extraction ----------
def extract_text(path):
    path = Path(path)
    suf = path.suffix.lower()
    if suf == ".docx":
        import docx
        d = docx.Document(str(path))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(parts)
    if suf == ".pdf":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    if suf in (".txt", ".md", ".tex"):
        return path.read_text(encoding="utf8", errors="ignore")
    raise ValueError(f"unsupported assignment file type: {path.name}")


PLACEHOLDERS = {"შეიტანეთ დავალების ტექსტი"}   # Moodle filler text on empty assignments


def html_to_text(s):
    from bs4 import BeautifulSoup
    text = BeautifulSoup(html.unescape(s or ""), "html.parser").get_text("\n").strip()
    return "" if text.rstrip(". ") in PLACEHOLDERS else text


# ---------- latexwork ----------
def solve_to_latex(task_text, week_label):  # noqa: week_label kept for future prompts
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=settings.anthropic_model, max_tokens=12000,
        system=LATEX_SYSTEM.replace("{student}", settings.student_name or "the student"),
        messages=[{"role": "user", "content": f"Assignment text:\n\n{task_text}"}])
    body = "".join(b.text for b in msg.content if b.type == "text").strip()
    body = re.sub(r"^```(?:latex|tex)?\s*|\s*```$", "", body)
    if "\\problem" not in body:
        raise RuntimeError("model output has no \\problem — unexpected format")
    return body


def run_latexwork(task_text, week_label, outdir, course):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    body = outdir / "body.tex"
    body.write_text(solve_to_latex(task_text, week_label), encoding="utf8")
    folder = outdir / "latex_result"
    name = f"Assignment_{week_label}"
    log = _run([sys.executable, str(SKILLS_DIR / "latexwork/scripts/build.py"), str(body),
                "--week", week_label, "--name", name, "--outdir", str(folder), *header_args(course)])
    pdf = folder / f"{name}.pdf"
    final = outdir / f"{result_name(week_label)}.pdf"
    final.write_bytes(pdf.read_bytes())
    zipped = Path(__import__("shutil").make_archive(str(outdir / f"{name}_tex"), "zip", folder))
    return final, zipped, log
