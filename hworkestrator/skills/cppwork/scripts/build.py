#!/usr/bin/env python3
"""Lecture .pptx -> assignment .docx.

Extracts every "საილუსტრაციო მაგალითი_N" (condition + C++ code) from the
slides, tidies the code, syntax-checks it with g++, and fills the Word
template (header untouched except week number and today's date; output
boxes left empty).

usage: build.py LECTURE(.pptx|.pdf|.docx) --week "V" [--out OUT.docx] [--date DD.MM.YYYY]
       [--student NAME --group GROUP --course COURSE]   (or env STUDENT_NAME / STUDENT_GROUP / COURSE_NAME)
"""
import argparse, datetime, html, json, os, re, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

EXAMPLE_RE = re.compile(r"საილუსტრაციო\s*მაგალითი\s*_?\s*(\d+)\s*[:：]\s*(.*)", re.S)
STOP_RE = re.compile(r"^\s*(შედეგი|პროგრამული\s+კოდი|კოდი\s*-|Output|პროფ\.|(ორშაბათი|სამშაბათი|ოთხშაბათი|ხუთშაბათი|პარასკევი|შაბათი|კვირა),)", re.I)
TYPES = {"int", "float", "double", "char", "long", "short", "unsigned", "signed", "void", "bool", "auto", "const"}


# ---------- pptx extraction ----------
def slide_paragraphs(z):
    names = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                   key=lambda n: int(re.findall(r"\d+", n)[0]))
    for n in names:
        x = z.read(n).decode("utf8")
        paras = []
        for p in re.findall(r"<a:p>.*?</a:p>|<a:p [^>]*>.*?</a:p>", x, flags=re.S):
            p = re.sub(r"<a:br\s*/?>", "\n", p)
            t = html.unescape("".join(re.findall(r"<a:t>([^<]*)</a:t>|(\n)", p) and
                                      [a or b for a, b in re.findall(r"<a:t>([^<]*)</a:t>|(\n)", p)]))
            paras.extend(t.replace("\xa0", " ").split("\n"))
        yield paras



# ---------- other sources: PDF and Word lectures ----------
def pdf_pages(path, merged=True):
    """Lines of a PDF. pypdf, falling back to pdftotext. Bare page numbers and running headers/footers
    (prose lines repeated on most pages) are dropped, and the pages are merged into one stream: a
    code listing very often continues over a page break. merged=False gives one list per page."""
    texts = []
    try:
        from pypdf import PdfReader
        texts = [(pg.extract_text() or "") for pg in PdfReader(path).pages]
    except Exception:
        pass
    if not any(t.strip() for t in texts):
        try:
            out = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
            texts = out.split("\f")
        except OSError:
            texts = []
    per_page = [[l.replace("\xa0", " ").rstrip() for l in t.split("\n")] for t in texts]
    per_page = [[l for l in lines if not re.fullmatch(r"\s*\d{1,3}\s*", l)] for lines in per_page]
    repeated = set()
    if len(per_page) >= 2:
        seen = {}
        for lines in per_page:
            for l in {x.strip() for x in lines}:
                seen[l] = seen.get(l, 0) + 1
        need = max(2, int(0.6 * len(per_page)))
        repeated = {l for l, c in seen.items()
                    if c >= need and len(l) >= 8 and not re.search(r"[;{}]", l) and not l.startswith("#")}
    per_page = [[l for l in lines if l.strip() not in repeated] for lines in per_page]
    if merged:
        yield [l for lines in per_page for l in lines]
    else:
        yield from per_page


def docx_pages(path):
    """A Word lecture as one 'page' of paragraphs (line breaks inside a paragraph become lines)."""
    z = zipfile.ZipFile(path)
    x = z.read("word/document.xml").decode("utf8")
    lines = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S):
        p = p.replace("<w:tab/>", "<w:t>    </w:t>")
        p = re.sub(r"<w:br[^>]*/>", "\n", p)
        t = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>|(\n)", p) and
                                  [a or b for a, b in re.findall(r"<w:t[^>]*>([^<]*)</w:t>|(\n)", p)]))
        lines.extend(t.replace("\xa0", " ").split("\n"))
    yield lines


def pages(path, merged=True):
    """Lecture file -> iterator of pages (a page = list of text lines): pptx slides, a PDF (one merged
    stream, or per page with merged=False), or a docx."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return pdf_pages(path, merged)
    if ext == ".docx":
        return docx_pages(path)
    return slide_paragraphs(zipfile.ZipFile(path))


def is_slides(path):
    return os.path.splitext(path)[1].lower() == ".pptx"


def clean_slide_line(line):
    """Drop slide-annotation artifacts: unbalanced /* or */ and stray Georgian labels after code."""
    line = line.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    if "/*" in line and "*/" not in line:
        line = line[:line.index("/*")]
    elif "*/" in line and "/*" not in line:
        line = line.replace("*/", "")
    code, comment = split_comment(line)
    code = re.sub(r"(;)\s+[^\x00-\x7F].*$", r"\1", code)
    code = re.sub(r"(\b\w+(?:\s+\*?\w+)?\s*;)\s+[^\x00-\x7F][^\"]*$", r"\1", code) if code.strip() and not comment else code
    return (code + ("    " + comment if comment else "")).rstrip()



CODE_LABEL_RE = re.compile(r"^\s*კოდი\s*-?\s*code\b", re.I)
CODEY_RE = re.compile(r"[;{}]\s*(//.*)?$|^\s*#\s*include|^\s*(int|float|double|char|string|void|struct|using|for|while|if|return)\b")


def _collect_from(lines, i0, labelled, keep_blank=False):
    """One code block starting at/after lines[i0] -> (code_lines, index_after_block, start_index)."""
    code, depth, started, i, start = [], 0, False, i0, i0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not started:
            if re.match(r"\s*#\s*include", line) or (labelled and CODEY_RE.search(line)):
                started, start = True, i - 1
            else:
                continue
        if STOP_RE.match(line) or CODE_LABEL_RE.match(line):
            break
        line = clean_slide_line(line)
        if not line.strip() or re.fullmatch(r"\s*\d{1,3}\s*", line):
            if keep_blank and code and code[-1] != "" and not line.strip():
                code.append("")                     # one blank line between members (PDF/Word)
            continue
        code.append(line)
        code_only = split_comment(line)[0]
        depth += code_only.count("{") - code_only.count("}")
        if re.search(r"\bmain\b", " ".join(code)) and depth <= 0 and "}" in code_only:
            break
    while code and code[-1] == "":
        code.pop()
    if labelled:
        # drop trailing non-code lines (printed output etc.)
        while code and not CODEY_RE.search(code[-1]):
            code.pop()
        return code, i, start
    return (code if re.search(r"\bmain\b", " ".join(code)) else []), i, start


def collect_blocks(lines, labelled=False, with_pos=False, keep_blank=False):
    """All code blocks of a page. Normal page: from each #include until main() is closed (a block must
    contain main, so "#include <stack>" inside explanatory prose is ignored). Page carrying the
    "კოდი code" label (slides): the whole listing, even without main. With with_pos=True the items are
    (code, start_line_index)."""
    blocks, i = [], 0
    while i < len(lines):
        code, nxt, start = _collect_from(lines, i, labelled, keep_blank)
        if code:
            blocks.append((code, start))
        if nxt <= i:
            break
        i = nxt
        if labelled:
            break
    return blocks if with_pos else [c for c, _ in blocks]


def collect_code(lines, labelled=False):
    blocks = collect_blocks(lines, labelled)
    return blocks[0] if blocks else []


def heading_before(lines, upto):
    """For PDF/Word pages: the last short heading-like line before index `upto` (no code characters,
    not a sentence)."""
    best = ""
    for l in lines[:upto]:
        t = l.strip()
        if 2 <= len(t) <= 60 and not re.search(r"[;{}()=<>#]", t) and not re.fullmatch(r"[\d\W]+", t) \
                and not t.endswith((".", ",", ";", "!", "?")) \
                and not STOP_RE.match(t) and not CODE_LABEL_RE.match(t) and not EXAMPLE_RE.match(t):
            best = t
    return best


def extract_unmarked(path, merged=True):
    """Lectures without 'საილუსტრაციო მაგალითი' labels: take every code block, title it by the
    nearest preceding heading (a heading slide for pptx, a heading-like line for PDF/Word)."""
    out, heading, n = [], "", 0
    slides = is_slides(path)
    for paras in pages(path, merged):
        body = [p for p in paras if p.strip() and not p.strip().startswith("პროფ.")]
        labelled = slides and any(CODE_LABEL_RE.match(l) for l in paras)
        blocks = collect_blocks(paras, labelled, with_pos=True, keep_blank=not slides)
        if not blocks and not slides and any(CODE_LABEL_RE.match(l) for l in paras):
            blocks = collect_blocks(paras, True, with_pos=True, keep_blank=True)   # "კოდი code" listing without main
        if blocks:
            for code, start in blocks:
                if not slides:
                    heading = heading_before(paras, start) or heading
                n += 1
                title = f"{heading}: " if heading else ""
                out.append({"n": n, "cond": f"{title}ლექციაში მოცემული პროგრამა (კოდი და შედეგი).".strip(),
                            "code": code})
        elif slides and 1 <= len(body) <= 2 and len(body[0].strip()) <= 40 \
                and not re.search(r"თ\s*ე\s*მ\s*ა|გმადლობთ|რეზიუმე", body[0]):
            heading = body[0].strip()
        elif not slides:
            heading = heading_before(paras, len(paras)) or heading
    return out


def extract(path, merged=True):
    examples, cur, in_code = [], None, False
    wrapped = not is_slides(path)          # PDF/Word wrap the condition over several lines
    for paras in pages(path, merged):
        for line in paras:
            m = EXAMPLE_RE.match(line.strip())
            if m:
                cur = {"n": int(m.group(1)), "cond": re.sub(r"\s+", " ", m.group(2)).strip(), "code": []}
                examples.append(cur)
                in_code = False
                continue
            if cur is None:
                continue
            if not in_code:
                if re.match(r"\s*#\s*include", line):
                    in_code = True
                else:
                    if (wrapped and not cur["code"] and line.strip() and len(cur["cond"]) < 700
                            and not CODEY_RE.search(line) and not STOP_RE.match(line)):
                        cur["cond"] = (cur["cond"] + " " + line.strip()).strip()
                    continue
            if STOP_RE.match(line):
                cur = None if cur["code"] else cur
                in_code = False
                continue
            line = clean_slide_line(line)
            if not line.strip() or re.fullmatch(r"\s*\d{1,3}\s*", line):
                if wrapped and not line.strip() and cur["code"] and cur["code"][-1] != "":
                    cur["code"].append("")
                continue
            cur["code"].append(line)
            code_only = split_comment(line)[0]
            cur["depth"] = cur.get("depth", 0) + code_only.count("{") - code_only.count("}")
            if re.search(r"\bmain\b", " ".join(cur["code"])) and cur["depth"] <= 0 and "}" in code_only:
                in_code = False
                cur = None
    return [e for e in examples if e["code"]] if examples else []


# ---------- code tidying ----------
def split_comment(line):
    """-> (code, comment) honouring string literals."""
    i, q = 0, None
    while i < len(line):
        c = line[i]
        if q:
            if c == "\\":
                i += 1
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
        elif line.startswith("//", i) or line.startswith("/*", i):
            return line[:i], line[i:].strip()
        i += 1
    return line, ""


TOK = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|<<|>>|<=|>=|==|!=|&&|\|\||\+\+|--|->|::|[A-Za-z_]\w*|\d+(?:\.\d+)?|\S')


def fix_typos(code):
    code = re.sub(r"<<\s*e\s+ndl\b", "<< endl", code)          # slide typo "e ndl"
    code = re.sub(r"^(\s*)main\s*\(", r"\1int main(", code)       # main() without a return type
    return code


def tidy_code(code):
    code = fix_typos(code)
    toks = TOK.findall(code)
    out = []
    prev = None  # previous significant token
    for t in toks:
        unary_ctx = prev is None or prev in {"=", "(", ",", "<<", ">>", "+", "-", "*", "/", "{", "return", "==", "!=", "<=", ">=", "&&", "||", "["}
        if t in {"*", "&"} and unary_ctx:
            out.append(("sp", t, "nosp_after"))
        elif t in {"<<", ">>", "=", "==", "!=", "<=", ">=", "&&", "||", "+", "-", "/"}:
            out.append(("bin", t, ""))
        elif t == "*" and prev not in TYPES and prev not in {"*"}:
            out.append(("bin", t, ""))
        else:
            out.append(("tok", t, ""))
        prev = t
    s = ""
    for kind, t, flag in out:
        if kind == "bin":
            s = s.rstrip() + " " + t + " "
        elif t == ".":
            s = s.rstrip() + "."
        elif s.endswith(".") and t not in {",", ";", ")", "]"} and not s[-2:-1].isdigit() and not t[0].isdigit():
            s += t
        elif t in {",", ";"}:
            s = s.rstrip() + t + (" " if t == "," else "")
        elif t in {")", "]"}:
            s = s.rstrip() + t
        elif t in {"(", "["}:
            s = s.rstrip() + t if s and re.search(r"[\w\)\]]$", s.rstrip()) and not s.rstrip().endswith(("return", "<<", ">>")) else s + t
        else:
            glue = ""
            if s and not s.endswith((" ", "(", "[", "*", "&", "#")) :
                glue = " "
            if s.endswith(("*", "&")) and glue == "" and not s[:-1].endswith((" ", "(", "")):
                pass
            s += glue + t if not (s.endswith("#") ) else t
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\b(stack|queue|deque|vector|list|set|map|pair|priority_queue)\s*<\s*([^<>]*?)\s*>",
               r"\1<\2>", s)
    s = re.sub(r"^#\s*", "#", s)
    s = re.sub(r"<\s*(\w+)\s*>", r"<\1>", s) if s.startswith("#include") else s
    s = re.sub(r"\b(int|float|double|char|long|short|bool|void)\s\*(?=[),])", r"\1*", s)
    s = s.replace("& ", "&") if re.search(r"= *& ", s) else s
    return s


def tidy(lines, verbatim=False):
    """Slides: rebuild the layout (spacing, Allman braces, 4-space indent). PDF/Word code that already has
    its own indentation is kept as written (only typos/quotes are fixed)."""
    if verbatim and any(re.match(r"\s+\S", l) for l in lines):
        keep = [l for i, l in enumerate(lines)
                if l.strip() or not (i + 1 < len(lines) and lines[i + 1].lstrip().startswith("}"))]
        return [fix_typos(l).rstrip() for l in keep]
    flat = []
    for line in lines:
        code, comment = split_comment(line)
        code = code.strip()
        if code.startswith("#"):
            flat.append((re.sub(r"^#\s*include\s*<\s*(\w+)\s*>.*", r"#include <\1>", code), ""))
            continue
        # split "int main(){" into Allman style
        m = re.fullmatch(r"(.*?(?:\)|\b(?:struct|union|class)\s+\w+))\s*\{\s*(.*)", code)
        if m and m.group(1) and not code.startswith("{"):
            flat.append((tidy_code(m.group(1)), ""))
            flat.append(("{", ""))
            rest = m.group(2).strip()
            if rest:
                flat.append((tidy_code(rest), comment)); continue
            if comment:
                flat[-1] = ("{", comment)
            continue
        flat.append((tidy_code(code) if code else "", comment))
    out, depth = [], 0
    for i, (code, comment) in enumerate(flat):
        if code.startswith("}"):
            depth = max(depth - 1, 0)
        text = ("    " * depth + code) if code else ""
        if comment:
            text = (text + ("    " if code else "")) + comment if code else "    " * depth + comment
        out.append(text.rstrip())
        if code.endswith("{") or code == "{":
            depth += 1
        if code == "}" and depth == 0 and i + 1 < len(flat):
            out.append("")
        if code.startswith("using namespace") and i + 1 < len(flat) and False:
            out.append("")
    return out


def syntax_check(lines, label):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "t.cpp")
        open(f, "w").write("\n".join(lines) + "\n")
        r = subprocess.run(["g++", "-fsyntax-only", f], capture_output=True, text=True)
    ok = r.returncode == 0
    print(f"  {label}: {'compiles OK' if ok else 'COMPILE ERROR'}")
    if not ok:
        print(r.stderr[:600])
    return ok


# ---------- docx ----------
RPR = ('<w:rFonts w:ascii="Menlo" w:eastAsia="Times New Roman" w:hAnsi="Menlo" w:cs="Menlo"/>'
       '<w:sz w:val="18"/><w:szCs w:val="18"/><w:lang w:eastAsia="en-GB"/>')


def code_par(line):
    return ('<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:rPr>%s</w:rPr></w:pPr>'
            '<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % (RPR, RPR, html.escape(line, quote=False) if line else ""))


def shot_xml(rid, idx, w_px, h_px, max_w_cm=13.0, max_h_cm=8.6):
    w_cm = min(max_w_cm, max_h_cm * w_px / h_px)
    cx = int(w_cm * 360000)
    cy = int(cx * h_px / w_px)
    return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/>'
            '<wp:docPr id="%d" name="Screenshot %d"/><wp:cNvGraphicFramePr>'
            '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
            '</wp:cNvGraphicFramePr><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:nvPicPr><pic:cNvPr id="%d" name="shot%d.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            '</wp:inline></w:drawing></w:r>') % (cx, cy, 9000 + idx, idx, 9000 + idx, idx, rid, cx, cy)


def build_docx(examples, week, date, out, student, group, course):
    block = open(os.path.join(ASSETS, "task_block.xml"), encoding="utf8").read()
    parts = []
    for i, e in enumerate(examples):
        b = (block.replace("{{N}}", str(e["n"]))
                  .replace("{{CONDITION}}", html.escape(e["cond"], quote=False))
                  .replace("{{CODE}}", "".join(code_par(l) for l in e["code"]))
                  .replace("{{SHOT}}", e.get("shot_xml", "")))
        if i:
            b = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>' + b
        parts.append(b)
    with tempfile.TemporaryDirectory() as d:
        with zipfile.ZipFile(os.path.join(ASSETS, "template.docx")) as z:
            z.extractall(d)
        p = os.path.join(d, "word", "document.xml")
        s = open(p, encoding="utf8").read()
        s = (s.replace("{{WEEK}}", html.escape(week, quote=False))
              .replace("{{STUDENT}}", html.escape(student, quote=False))
              .replace("{{GROUP}}", html.escape(group, quote=False))
              .replace("{{COURSE}}", html.escape(course, quote=False))
              .replace("{{DATE}}", date)
              .replace("{{TASKS}}", "".join(parts)))
        open(p, "w", encoding="utf8").write(s)
        shots = [e for e in examples if e.get("shot")]
        if shots:
            os.makedirs(os.path.join(d, "word", "media"), exist_ok=True)
            rp = os.path.join(d, "word", "_rels", "document.xml.rels")
            rels = open(rp, encoding="utf8").read()
            add = ""
            for e in shots:
                shutil.copy(e["shot"], os.path.join(d, "word", "media", f"shot{e['n']}.png"))
                add += ('<Relationship Id="rIdShot%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                        'relationships/image" Target="media/shot%d.png"/>' % (e["n"], e["n"]))
            open(rp, "w", encoding="utf8").write(rels.replace("</Relationships>", add + "</Relationships>"))
        if os.path.exists(out):
            os.remove(out)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            # [Content_Types].xml first
            names = ["[Content_Types].xml"] + [os.path.relpath(os.path.join(r, f), d)
                                               for r, _, fs in os.walk(d) for f in fs
                                               if os.path.relpath(os.path.join(r, f), d) != "[Content_Types].xml"]
            for n in names:
                z.write(os.path.join(d, n), n)


def profile():
    """Optional local ../profile.json {"student", "group", "course"} (not part of the repo)."""
    try:
        return json.load(open(os.path.join(HERE, "..", "profile.json"), encoding="utf8"))
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx", help="lecture file: .pptx, .pdf or .docx")
    ap.add_argument("--week", required=True)
    ap.add_argument("--out")
    ap.add_argument("--date", default=datetime.date.today().strftime("%d.%m.%Y"))
    ap.add_argument("--student", default=os.getenv("STUDENT_NAME") or profile().get("student", ""), help="default: $STUDENT_NAME")
    ap.add_argument("--group", default=os.getenv("STUDENT_GROUP") or profile().get("group", ""), help="default: $STUDENT_GROUP")
    ap.add_argument("--course", default=os.getenv("COURSE_NAME") or profile().get("course", ""), help="default: $COURSE_NAME")
    ap.add_argument("--no-shots", action="store_true", help="leave output boxes empty")
    ap.add_argument("--stdin", action="append", default=[], metavar="N=v1,v2,...",
                    help="keyboard input for example N, e.g. --stdin 6=2,3,5,7,4,6")
    a = ap.parse_args()

    missing = [n for n, v in (("student (STUDENT_NAME)", a.student), ("group (STUDENT_GROUP)", a.group),
                              ("course (COURSE_NAME)", a.course)) if not v]
    if missing:
        sys.exit("Missing header data: " + ", ".join(missing) + " — pass --student/--group/--course or set the env vars.")
    examples, labelled = [], True
    for merged in ((True, False) if a.pptx.lower().endswith(".pdf") else (True,)):
        examples = extract(a.pptx, merged)
        if not examples:
            examples, labelled = extract_unmarked(a.pptx, merged), False
        if examples:
            break
    if examples and labelled:
        print(f"Found {len(examples)} examples")
    else:
        if not examples:
            sys.exit("ლექციაში კოდი ვერ ვიპოვე (არც 'საილუსტრაციო მაგალითი', არც #include ბლოკი).")
        print(f"No 'საილუსტრაციო მაგალითი' labels — using {len(examples)} code block(s) found in the slides")
    bad = 0
    for e in examples:
        e["code"] = tidy(e["code"], verbatim=not is_slides(a.pptx))
        bad += not syntax_check(e["code"], f"მაგალითი {e['n']}")
    if not a.no_shots:
        from PIL import Image
        import shot
        inputs = {}
        for item in a.stdin:
            k, v = item.split("=", 1)
            inputs[int(k)] = [x for x in re.split(r"[,\\s]+", v) if x]
        tmp = tempfile.mkdtemp()
        for e in examples:
            png = os.path.join(tmp, f"task{e['n']}.png")
            try:
                _, stdout, used = shot.render(e["code"], f"task{e['n']}", png, inputs.get(e["n"]))
            except Exception as ex:
                print(f"  მაგალითი {e['n']}: screenshot skipped ({ex})")
                continue
            w, h = Image.open(png).size
            e["shot"] = png
            e["shot_xml"] = shot_xml(f"rIdShot{e['n']}", e["n"], w, h)
            note = f" (input: {' '.join(map(str, used))})" if used else ""
            print(f"  მაგალითი {e['n']}: screenshot OK{note}")
    out = a.out or os.path.join(os.path.expanduser("~/Desktop"), f"Assignment_{a.week}.docx")
    build_docx(examples, a.week, a.date, out, a.student, a.group, a.course)
    print("Saved:", out)
    if bad:
        print(f"WARNING: {bad} example(s) did not compile — check them.")


if __name__ == "__main__":
    main()
