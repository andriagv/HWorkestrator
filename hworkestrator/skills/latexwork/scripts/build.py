#!/usr/bin/env python3
"""Assemble preamble + header + body.tex into a full .tex, compile with XeLaTeX,
and put <name>.tex and <name>.pdf (plus latex_assets/ with the logos) in --outdir
(default: a folder ~/Desktop/<name>/ so everything stays together).

usage: build.py BODY.tex --week IV [--name Assignment_IV] [--outdir DIR]
       [--student NAME --group GROUP --course COURSE]   (or env STUDENT_NAME / STUDENT_GROUP / COURSE_NAME)
BODY.tex contains only the content: \\problem{1}{...} \\answer ... (no preamble).
"""
import argparse, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("body")
    ap.add_argument("--week", required=True)
    ap.add_argument("--name")
    ap.add_argument("--student", default=os.getenv("STUDENT_NAME", ""))
    ap.add_argument("--group", default=os.getenv("STUDENT_GROUP", ""))
    ap.add_argument("--course", default=os.getenv("COURSE_NAME", ""))
    ap.add_argument("--outdir", help="default: ~/Desktop/<name>/")
    a = ap.parse_args()

    missing = [n for n, v in (("--student/STUDENT_NAME", a.student), ("--group/STUDENT_GROUP", a.group),
                              ("--course/COURSE_NAME", a.course)) if not v]
    if missing:
        sys.exit("Missing header data: " + ", ".join(missing))
    name = a.name or f"Assignment_{a.week}"
    out = os.path.expanduser(a.outdir) if a.outdir else os.path.join(os.path.expanduser("~/Desktop"), name)
    os.makedirs(os.path.join(out, "latex_assets"), exist_ok=True)
    for f in ("logo_banner.png", "logo_seal.png"):
        shutil.copy(os.path.join(ASSETS, f), os.path.join(out, "latex_assets", f))

    pre = open(os.path.join(ASSETS, "preamble.tex"), encoding="utf8").read()
    body = open(a.body, encoding="utf8").read()
    def tex_escape(t):  # single pass so replacements are not escaped again
        table = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                 "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
        return "".join(table.get(ch, ch) for ch in t)

    defs = "".join("\\newcommand{\\%s}{%s}\n" % (k, tex_escape(v)) for k, v in (
        ("assignmentweek", a.week), ("assignmentstudent", a.student),
        ("assignmentgroup", a.group), ("assignmentcourse", a.course)))
    tex = (pre + "\n" + defs + "\\begin{document}\n"
           "\\assignmentheader\n\n" + body.strip() + "\n\n\\end{document}\n")
    tex_path = os.path.join(out, name + ".tex")
    open(tex_path, "w", encoding="utf8").write(tex)

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(2):
            r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                                f"-output-directory={tmp}", tex_path],
                               cwd=out, capture_output=True, text=True)
            if r.returncode:
                log = r.stdout[-2500:]
                print("XeLaTeX FAILED:\n" + log)
                sys.exit(1)
        shutil.copy(os.path.join(tmp, name + ".pdf"), os.path.join(out, name + ".pdf"))
        warn = [l for l in open(os.path.join(tmp, name + ".log"), errors="ignore")
                if "Missing character" in l or "Overfull \\hbox" in l]
    for w in warn[:8]:
        print("warning:", w.strip())
    print("Saved:", tex_path)
    print("Saved:", os.path.join(out, name + ".pdf"))


if __name__ == "__main__":
    main()
