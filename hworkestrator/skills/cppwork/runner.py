"""cppwork: lecture .pptx / .pdf / .docx → Word with every "საილუსტრაციო მაგალითი" (condition + C++ code), compile-checked,
with rendered terminal screenshots. Deterministic — no LLM."""
import sys
from pathlib import Path

from ..common import header_args, result_name, run_script

NEEDS = "lecture"
LECTURE_TYPES = (".pptx", ".pdf", ".docx")        # preferred first
USES_LLM = False
BUILD = Path(__file__).parent / "scripts/build.py"


def run(lecture, label, outdir, course, model=None, stdin=None):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{result_name(label)}.docx"
    cmd = [sys.executable, str(BUILD), str(lecture), "--week", label, "--out", str(out), *header_args(course)]
    for item in stdin or []:
        cmd += ["--stdin", item]
    return out, [], run_script(cmd)
