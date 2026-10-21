#!/usr/bin/env python3
"""Build + execute a Jupyter notebook from a "percent" source file, with the fixed GTU header.

usage: build.py CELLS.py --week 1 --course "COURSE" [--name Assignment_1] [--outdir DIR] [--html]
                         [--student NAME --group GROUP]   (default: env / ../profile.json)

CELLS.py format (jupytext "percent" style):
    # %% [markdown]
    # ## ამოცანა 1
    # markdown text, every line starts with "# "
    # %%
    import pandas as pd          <- a code cell
The header cell (logos + student/group/course/week/date) is prepended automatically.
The notebook is executed (kernel python3) so it is saved WITH outputs and plots.
"""
import argparse, base64, datetime, html, json, os, re, sys

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
NAVY = "#1F3A5F"


def parse_percent(path):
    cells, kind, buf = [], None, []

    def flush():
        if kind is None:
            return
        text = "\n".join(buf).strip("\n")
        if kind == "markdown":
            text = "\n".join(re.sub(r"^# ?", "", l) for l in text.split("\n"))
            cells.append(nbformat.v4.new_markdown_cell(text.strip("\n")))
        elif text.strip():
            cells.append(nbformat.v4.new_code_cell(text))

    for line in open(path, encoding="utf8").read().split("\n"):
        m = re.match(r"^# %%\s*(\[(markdown|code)\])?\s*$", line)
        if m:
            flush()
            kind, buf = (m.group(2) or "code"), []
        elif kind is not None:
            buf.append(line)
    flush()
    return cells


def data_uri(filename):
    return "data:image/png;base64," + base64.b64encode(open(os.path.join(ASSETS, filename), "rb").read()).decode()


def header_cell(student, group, course, week, date):
    cell = nbformat.v4.new_markdown_cell(
        f'<img src="{data_uri("logo_banner.png")}" style="width:60%"/>\n'
        f'<hr style="border:1.5px solid {NAVY}"/>\n\n'
        f'<table style="width:100%;border:none"><tr>'
        f'<td style="width:28%;text-align:center;border:1.5px dashed #9CA3AF">'
        f'<img src="{data_uri("logo_seal.png")}" style="width:130px"/></td>'
        f'<td style="padding-left:24px;border:none;text-align:left;line-height:1.7">'
        f'<b style="color:{NAVY}">სტუდენტი:</b> {html.escape(student)}<br>'
        f'<b style="color:{NAVY}">ჯგუფი:</b> {html.escape(group)}<br>'
        f'<b style="color:{NAVY}">კურსის დასახელება:</b> {html.escape(course)}<br>'
        f'<b style="color:{NAVY}">დავალების ნომერი:</b> {html.escape(week)}<br>'
        f'<b style="color:{NAVY}">თარიღი:</b> {date}'
        f'</td></tr></table>')
    return cell


def profile():
    try:
        return json.load(open(os.path.join(HERE, "..", "profile.json"), encoding="utf8"))
    except OSError:
        return {}


def summarize(nb):
    print("\n=== cell outputs (for writing the explanations) ===")
    for i, c in enumerate(nb.cells):
        if c.cell_type != "code":
            continue
        first = c.source.strip().split("\n")[0][:70]
        print(f"\n[cell {i}] {first}")
        for o in c.get("outputs", []):
            if o.output_type == "stream":
                print(o.text[:1500].rstrip())
            elif o.output_type in ("execute_result", "display_data"):
                if "text/plain" in o.data and "image/png" not in o.data:
                    print(str(o.data["text/plain"])[:1500])
                if "image/png" in o.data:
                    print("<plot/image>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cells")
    ap.add_argument("--week", required=True)
    ap.add_argument("--course", required=True)
    ap.add_argument("--name")
    ap.add_argument("--outdir")
    ap.add_argument("--student", default=os.getenv("STUDENT_NAME") or profile().get("student", ""))
    ap.add_argument("--group", default=os.getenv("STUDENT_GROUP") or profile().get("group", ""))
    ap.add_argument("--html", action="store_true", help="also export <name>.html")
    ap.add_argument("--no-run", action="store_true", help="do not execute (no outputs)")
    a = ap.parse_args()
    if not (a.student and a.group):
        sys.exit("Missing student/group: pass --student/--group, set STUDENT_NAME/STUDENT_GROUP or edit profile.json")

    name = a.name or f"Assignment_{a.week}"
    out = os.path.expanduser(a.outdir) if a.outdir else os.path.join(os.path.expanduser("~/Desktop"), name)
    os.makedirs(out, exist_ok=True)
    date = datetime.date.today().strftime("%d.%m.%Y")

    nb = nbformat.v4.new_notebook()
    nb.cells = [header_cell(a.student, a.group, a.course, a.week, date)] + parse_percent(a.cells)
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    if not a.no_run:
        try:
            NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": out}}).execute()
        except CellExecutionError as e:
            print("EXECUTION FAILED:\n", str(e)[-1800:])
            sys.exit(1)
    path = os.path.join(out, name + ".ipynb")
    nbformat.write(nb, path)
    print("Saved:", path)
    if a.html:
        from nbconvert import HTMLExporter
        body, _ = HTMLExporter().from_notebook_node(nb)
        open(os.path.join(out, name + ".html"), "w", encoding="utf8").write(body)
        print("Saved:", os.path.join(out, name + ".html"))
    if not a.no_run:
        summarize(nb)


if __name__ == "__main__":
    main()
