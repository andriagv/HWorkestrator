#!/usr/bin/env python3
"""Compile + run a C++ example and render an editor+terminal style screenshot (PNG).

The terminal text is the program's REAL output (compiled with g++ and executed here);
only the window chrome is drawn.
"""
import os, re, subprocess, tempfile

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import CppLexer
from pygments.token import Token

def _first(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("none of these fonts found: " + ", ".join(paths))


# macOS first, then Debian/Ubuntu (fonts-dejavu-core, fonts-noto-core)
MENLO = _first("/System/Library/Fonts/Menlo.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
GEORGIAN = _first("/System/Library/Fonts/SFGeorgian.ttf",
                  "/usr/share/fonts/truetype/noto/NotoSansGeorgian-Regular.ttf",
                  "/usr/share/fonts/opentype/noto/NotoSansGeorgian-Regular.ttf",
                  "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
                  "/usr/share/fonts/opentype/freefont/FreeSerif.otf")
UI = _first("/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

BG = (24, 25, 27)
PANEL = (31, 32, 34)
FG = (204, 204, 204)
DIM = (125, 128, 133)
LINE_NO = (110, 114, 120)
COL = {
    "kw": (242, 125, 110),      # int, float, return ...
    "kw2": (203, 139, 224),     # using namespace, #include
    "ns": (101, 214, 178),      # std
    "num": (181, 206, 168),
    "str": (156, 220, 254),
    "fn": (196, 170, 255),
    "op": (200, 150, 250),
    "brace": (255, 215, 0),
    "ptr": (110, 170, 240),
    "com": (115, 125, 120),
}
DEFAULT_INPUTS = [2, 3, 5, 7, 4, 6, 8, 9, 1, 2]


def classify(tok, text, nxt):
    if tok in Token.Comment.Preproc or tok in Token.Comment.PreprocFile:
        return COL["str"] if text.startswith("<") else COL["kw2"]
    if tok in Token.Comment:
        return COL["com"]
    if tok in Token.Keyword.Namespace or text in ("using", "namespace"):
        return COL["kw2"]
    if tok in Token.Keyword:
        return COL["kw2"] if text in ("return", "struct", "union", "if", "else", "for", "while") else COL["kw"]
    if tok in Token.Name.Namespace or text == "std":
        return COL["ns"]
    if tok in Token.Literal.Number:
        return COL["num"]
    if tok in Token.Literal.String:
        return COL["str"]
    if tok in Token.Name and nxt == "(":
        return COL["fn"]
    if text in ("endl", "cout", "cin") and False:
        return FG
    if text in ("<<", ">>"):
        return COL["op"]
    if text in "{}()[]" and text:
        return COL["brace"]
    if text == "*":
        return COL["ptr"]
    if text == "endl":
        return COL["op"]
    return FG


class Fonts:
    def __init__(self, size, scale):
        self.size = int(size * scale)
        self.mono = ImageFont.truetype(MENLO, self.size)
        self.geo = ImageFont.truetype(GEORGIAN, self.size)
        self.ui = ImageFont.truetype(UI, int(self.size * 0.95))
        self.cw = self.mono.getlength("M")

    def font(self, ch):
        return self.geo if "Ⴀ" <= ch <= "ჿ" else self.mono


def draw_text(d, f, x, y, text, color):
    for ch in text:
        d.text((x, y), ch, font=f.font(ch), fill=color)
        x += f.cw
    return x


def highlight_lines(lines):
    src = "\n".join(lines) + "\n"
    toks = list(lex(src, CppLexer()))
    out, cur = [], []
    for i, (tok, text) in enumerate(toks):
        nxt = None
        for _, t in toks[i + 1:]:
            if t.strip():
                nxt = t.strip()[0]
                break
            if t:
                nxt = None
                break
        for j, part in enumerate(text.split("\n")):
            if j:
                out.append(cur)
                cur = []
            if part:
                cur.append((part, classify(tok, part, nxt)))
    if cur:
        out.append(cur)
    return out[:len(lines)]


def run_program(code_lines, stdin_text):
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "p.cpp")
        exe = os.path.join(d, "p")
        open(src, "w").write("\n".join(code_lines) + "\n")
        r = subprocess.run(["g++", "-w", "-o", exe, src], capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr
        p = subprocess.run([exe], input=stdin_text, capture_output=True, text=True, timeout=10)
        return p.stdout, ""


def needs_inputs(code_lines):
    n = 0
    for l in code_lines:
        if "cin" in l:
            n += l.count(">>")
    return n


def render(code_lines, name, out_path, stdin_values=None, scale=2):
    """Returns (png_path, program_output, stdin_values_used)."""
    k = needs_inputs(code_lines)
    vals = list(stdin_values) if stdin_values else DEFAULT_INPUTS[:k]
    stdin_text = " ".join(map(str, vals)) + "\n" if k else ""
    stdout, err = run_program(code_lines, stdin_text)
    if stdout is None:
        raise RuntimeError("compile failed:\n" + err)

    f = Fonts(15, scale)
    s = scale
    out_lines = stdout.expandtabs(8).rstrip("\n").split("\n") if stdout.strip() else []
    # look of the fake terminal; override with SHOT_PROMPT / SHOT_BIN_DIR in .env
    prompt = os.getenv("SHOT_PROMPT", "user@computer cpp %")
    bin_dir = os.getenv("SHOT_BIN_DIR", "/home/user/cpp").rstrip("/")
    term = [("run", f"{prompt} {bin_dir}/{name}")]
    if k:
        term.append(("out", " ".join(map(str, vals))))
    term += [("out", l) for l in out_lines]
    term.append(("prompt", f"{prompt} "))

    lh = int(24 * s)
    pad = int(20 * s)
    gutter = int(70 * s)
    maxcols = max([len(l) for l in code_lines] + [len(t[1]) + 2 for t in term] + [60])
    width = max(int(900 * s), gutter + int(maxcols * f.cw) + pad * 2)
    tabs_h = int(46 * s)
    crumb_h = int(34 * s)
    code_h = (len(code_lines) + 1) * lh + int(14 * s)
    panel_tabs_h = int(44 * s)
    term_h = len(term) * lh + int(26 * s)
    height = tabs_h + crumb_h + code_h + panel_tabs_h + term_h

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    # tab bar
    d.rectangle([0, 0, width, tabs_h], fill=PANEL)
    tab_w = int(f.ui.getlength(name + ".cpp") + 80 * s)
    d.rectangle([int(20 * s), 0, int(20 * s) + tab_w, tabs_h], fill=BG)
    d.text((int(36 * s), int(11 * s)), "G+", font=f.ui, fill=(86, 156, 214))
    d.text((int(78 * s), int(11 * s)), name + ".cpp", font=f.ui, fill=(235, 235, 235))
    d.text((int(78 * s + f.ui.getlength(name + '.cpp') + 18 * s), int(9 * s)), "×", font=f.ui, fill=FG)
    # breadcrumb
    y0 = tabs_h
    d.text((int(36 * s), y0 + int(5 * s)), f"{name}.cpp  ›  ...", font=f.ui, fill=DIM)
    # code
    y = y0 + crumb_h
    hl = highlight_lines(code_lines)
    for i, parts in enumerate(hl):
        ln = str(i + 1)
        d.text((gutter - int(26 * s) - f.ui.getlength(ln), y + int(2 * s)), ln, font=f.ui, fill=LINE_NO)
        x = gutter
        for text, color in parts:
            x = draw_text(d, f, x, y, text, color)
        y += lh
    d.text((gutter - int(26 * s) - f.ui.getlength(str(len(code_lines) + 1)), y + int(2 * s)),
           str(len(code_lines) + 1), font=f.ui, fill=LINE_NO)
    y = y0 + crumb_h + code_h
    # panel tabs
    d.line([0, y, width, y], fill=(50, 52, 56), width=max(1, int(s)))
    x = int(36 * s)
    for label in ["Problems", "Output", "Debug Console", "Terminal", "Ports", "Query Results"]:
        w = f.ui.getlength(label)
        if label == "Terminal":
            d.rounded_rectangle([x - 14 * s, y + 6 * s, x + w + 14 * s, y + panel_tabs_h - 6 * s],
                                radius=6 * s, fill=(45, 47, 51))
            d.text((x, y + int(11 * s)), label, font=f.ui, fill=(240, 240, 240))
        else:
            d.text((x, y + int(11 * s)), label, font=f.ui, fill=DIM)
        x += int(w + 46 * s)
    # terminal
    y += panel_tabs_h + int(8 * s)
    for kind, text in term:
        tx = int(36 * s)
        if kind == "run":
            d.ellipse([tx, y + 6 * s, tx + 11 * s, y + 17 * s], fill=(70, 140, 190))
            draw_text(d, f, tx + 22 * s, y, text, FG)
        elif kind == "prompt":
            draw_text(d, f, tx + 22 * s, y, text, FG)
            cx = tx + 22 * s + len(text) * f.cw
            d.rectangle([cx, y + 2 * s, cx + f.cw * 0.9, y + lh - 4 * s], fill=(200, 200, 200))
        else:
            draw_text(d, f, tx + 22 * s, y, text, FG)
        y += lh
    img.save(out_path)
    return out_path, stdout, vals


if __name__ == "__main__":
    import sys
    code = open(sys.argv[1]).read().rstrip("\n").split("\n")
    print(render(code, os.path.splitext(os.path.basename(sys.argv[1]))[0], sys.argv[2])[1:])
