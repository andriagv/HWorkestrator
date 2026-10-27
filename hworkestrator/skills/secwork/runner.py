"""secwork: information-security assignment → Claude writes the tasks + Python code as JSON → the code is really
run (repairing errors) → Claude writes the analysis from the REAL output → PDF (uploaded) + docx (for edits)."""
import json
import subprocess
import sys
from pathlib import Path

from ... import llm
from ...config import settings
from ...documents import expected_tasks
from ..common import header_args, result_name

NEEDS = "text"
USES_LLM = True
BUILD = Path(__file__).parent / "scripts/build.py"
TOKENS = {"S": 600, "M": 1200, "L": 2200}            # statement + code pass (JSON), per task by size
EXPLAIN_TOKENS = {"S": 500, "M": 1000, "L": 1600}

SYSTEM = r"""You solve an information-security university assignment (ciphers, encodings, hashing,
number systems, probability of breaking a key, security theory...) for a GTU student.
Return ONLY a JSON object:
{"title": "<short Georgian title of the whole assignment, e.g. სახელისა და გვარის დაშიფვრა და ანალიზი>",
 "tasks": [{"n": 1, "title": "<short Georgian title>",
            "condition": ["<what this task does, in the assignment's wording>", "<keys / method / formulas>"],
            "code": "<complete Python 3 program, or \"\" for a theory-only task>",
            "caption": "<Georgian caption of the output, e.g. სახელისა და გვარის დაშიფვრის შედეგი>",
            "answer": ["<Georgian paragraph>", ...]}],
 "conclusions": []}
Rules:
- Split the assignment into tasks: numbered items as they are; an unnumbered list of steps ("encrypt...",
  "convert...", "analyse...") -> one task per step, in order. Never skip a step. Natural Georgian prose.
  Formulas as plain text with Unicode (C = (P + k) mod 26, P ⊕ K, ≡, ⁻¹, ≈), no LaTeX.
- "condition" states the concrete choices: the keys used (fixed, e.g. Caesar k = 7, Vigenère CIPHER, Vernam key
  of the text's length), how non-letters are handled, the formulas.
- A task that asks to encrypt/decrypt/compute/convert/compare/analyse gets a "code": standard library only,
  no input(), no files, no network, deterministic (fixed keys, or random.seed(42) and print the key).
  Every task's code is run on its own, so it is self-contained: a task that uses an earlier result recomputes
  it (or uses the same fixed values) — but keep it to what THAT task needs and print only its own results.
  Print every value the task asks for with aligned Georgian labels, e.g. print(f"{'ღია ტექსტი':<12}: {p}").
  Comments in Georgian. Byte values: hex as "0A 1F ...", binary 8 digits, octal 3 digits.
  For such a task leave "answer" as [] — the analysis is written later from the REAL output.
- A theory task gets "code": "" and a full Georgian "answer".
- Personal data: the student is {student}; when a cipher needs Latin letters, transliterate the name
  (e.g. ანდრია გვარამია -> Andria Gvaramia) and say so in the condition.
- Valid JSON only (escape newlines in code as \n), no markdown fences, no commentary."""

EXPLAIN_SYSTEM = r"""You write the analysis of an information-security assignment from the REAL outputs
of its programs. Return ONLY JSON:
{"answers": {"<task n>": ["<Georgian paragraph>", ...]}, "conclusions": ["<Georgian paragraph>", ...]}
"answers": ONLY for a task whose question is not answered by its output alone (e.g. "which is stronger and
why"); omit the others. "conclusions": numbered paragraphs "1. <method/aspect>. ..." — one per method or aspect
(what the output shows, key space, weaknesses: frequency analysis, brute force, key reuse...), each citing the
actual numbers from the outputs; then a last paragraph starting "საერთო დასკვნა:". Valid JSON, no fences."""


def build(sol, folder, label, course, run_code, pdf=False):
    """Write the solution JSON, call the build script (optionally running the code / typesetting the PDF).
    -> (ok, log, solution with the stored real outputs)."""
    path = Path(folder) / "solution.json"
    Path(folder).mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sol, ensure_ascii=False, indent=1), encoding="utf8")
    cmd = [sys.executable, str(BUILD), str(path), "--week", label, "--out", str(Path(folder) / "out.docx"),
           *header_args(course)]
    cmd += ["--run"] if run_code else []
    cmd += ["--pdf", str(Path(folder) / "out.pdf")] if pdf else []
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr, json.loads(path.read_text(encoding="utf8"))


def run(task_text, label, outdir, course, model=None):
    """Claude writes tasks + Python code, we run the code (repairing errors), then Claude explains the
    REAL outputs and writes the conclusions."""
    outdir = Path(outdir)
    folder = outdir / "sec_result"
    system = SYSTEM.replace("{student}", settings.student_name or "the student")
    user = f"Assignment text:\n\n{task_text}"
    ask = lambda extra="": llm.parse_json(llm.claude(system, user + extra, 24000, model))   # noqa: E731
    sol = ask()
    gone = [n for n in expected_tasks(task_text) if n not in {int(t["n"]) for t in sol["tasks"]}]
    if gone:                                              # make sure no task was skipped
        sol = ask(f"\n\nYour previous answer:\n{json.dumps(sol, ensure_ascii=False)}\n\n"
                  f"It is missing tasks {gone}. Return the FULL JSON with ALL tasks.")
    ok, log, sol = build(sol, folder, label, course, run_code=True)
    for _ in range(2):                                    # repair loop
        if ok:
            break
        sol = ask(f"\n\nYour previous answer:\n{json.dumps(sol, ensure_ascii=False)}\n\n"
                  f"Running the code failed with:\n{log[-2500:]}\n\nReturn the full corrected JSON.")
        ok, log, sol = build(sol, folder, label, course, run_code=True)
    if not ok:
        raise RuntimeError("კოდის გაშვება ვერ მოხერხდა: " + (log.strip().splitlines() or ["?"])[-1])
    coded = [t for t in sol["tasks"] if t.get("code", "").strip()]
    if coded:                                             # pass 2: analysis from the real outputs
        shown = "\n\n".join(f"Task {t['n']} code:\n{t['code']}\n\nREAL output:\n{t.get('output', '')[:3000]}"
                            for t in coded)
        ex = llm.parse_json(llm.claude(EXPLAIN_SYSTEM, f"{user}\n\n{shown}", 12000, model))
        answers = {int(k): v for k, v in (ex.get("answers") or {}).items()}
        for t in coded:
            t["answer"] = answers.get(int(t["n"])) or t.get("answer") or []
        sol["conclusions"] = ex.get("conclusions") or sol.get("conclusions") or []
    ok, log, sol = build(sol, folder, label, course, run_code=False, pdf=True)   # keeps the stored outputs
    if not ok:
        raise RuntimeError("PDF/docx build failed: " + (log.strip().splitlines() or ["?"])[-1])
    pdf, docx = outdir / f"{result_name(label)}.pdf", outdir / f"{result_name(label)}.docx"
    pdf.write_bytes((folder / "out.pdf").read_bytes())
    docx.write_bytes((folder / "out.docx").read_bytes())
    return pdf, [docx], log          # the PDF is uploaded; the .docx is sent too, for manual edits


def estimate(task_in, sizes):
    first_out = int((sum(TOKENS[z] for z in sizes) + 300) * 1.15)
    second_out = int((sum(EXPLAIN_TOKENS[z] for z in sizes) + 600) * 1.15)   # + conclusions
    return [(task_in + 900, first_out),                       # tasks + code
            (task_in + first_out + 600, second_out)]          # analysis from real outputs
