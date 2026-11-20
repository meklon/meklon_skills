#!/usr/bin/env python3
"""Colour validator for engineering illustrations. Pure Python (no numpy).

Usage
  palette_check.py --theme light               # a theme's tokens (light | graphite | night | path/to/theme.py):
                                               # text contrast on every surface, glyphs on marks, statuses,
                                               # flows and series (normal vision + CVD + greyscale)
  palette_check.py --svg pic.svg [--theme X]   # a picture: text-on-background contrast, stroke and status-mark
                                               # colours (CVD, grey), colours not in the theme (off-palette).
                                               # The page colour is read from the SVG (first full-canvas rect).
  palette_check.py --colors "#a,#b" [--page #fff]      # any colour set: CVD + normal + greyscale pairs
  palette_check.py --hues "ours=256,client=200:0.09,risk=27" [--dark]
                                               # families for NEW hues (OKLCH degrees[:chroma]) with
                                               # palette.family() / family_night(): text contrast + how far
                                               # the families' solids are apart
  add --quiet to print only WARN/FAIL lines.  Exit code 1 if any FAIL.

Thresholds
  text            >= 4.5:1  (>= 3:1 if font-size >= 24px or >= 18.7px bold)          WCAG 1.4.3
  glyph on a mark >= 4.5:1 PASS, 3-4.5 WARN (icon, WCAG 1.4.11), < 3 FAIL
  line / mark vs page  >= 3:1 PASS, below -> WARN (needs a label next to it)
  categorical pair (flows, statuses, series):
      normal vision  dE >= 15 PASS, 10-15 WARN, < 10 FAIL
      protan/deutan  dE >= 8 PASS, 6-8 WARN (only with a 2nd channel: label, dash, glyph), < 6 FAIL
      tritan         reported, WARN only (0.01 % prevalence; rely on labels)
  greyscale pair  dL* >= 10 PASS, 5-10 WARN, < 5 FAIL — unless shapes differ (then INFO)
  dE = Euclidean OKLab distance x100; CVD = Machado, Oliveira & Fernandes 2009, severity 1.0.
"""
import argparse
import itertools
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import palette as PAL  # noqa: E402
from palette import _delin, _lin, contrast, hex2oklab, hex2rgb, lstar, rgb2hex  # noqa: E402

MACHADO = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
VISION = ("normal", "protan", "deutan", "tritan")


class Report:
    """collects verdicts; prints them unless silent (quiet: only WARN/FAIL)"""

    def __init__(self, quiet=False, silent=False):
        self.items, self.quiet, self.silent = [], quiet, silent

    def say(self, s):
        if not self.silent:
            print(s)

    def verdict(self, level, msg):
        self.items.append((level, msg))
        if self.silent or (self.quiet and level in ("PASS", "INFO")):
            return
        print(f"  {level:4s}  {msg}")

    def count(self, level):
        return sum(1 for lv, _ in self.items if lv == level)


R = Report()


def simulate(h, kind):
    if kind == "normal":
        return h
    l = [_lin(c) for c in hex2rgb(h)]
    m = MACHADO[kind]
    return rgb2hex(_delin(min(1, max(0, sum(m[i][j] * l[j] for j in range(3))))) for i in range(3))


def dE(a, b, kind="normal"):
    pa, pb = hex2oklab(simulate(a, kind)), hex2oklab(simulate(b, kind))
    return 100 * sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5


# ---------------------------------------------------------------------------------------------
def check_text(pairs, title):
    """pairs: [(name, fg, bg, size_px, bold)]"""
    R.say(f"\n## {title}")
    for name, fg, bg, size, bold in pairs:
        r = contrast(fg, bg)
        need = 3.0 if (size >= 24 or (bold and size >= 18.7)) else 4.5
        R.verdict("PASS" if r >= need else "FAIL", f"{r:5.2f}:1  {name}  ({fg} on {bg}, need {need})")


def check_glyphs(pairs, title):
    R.say(f"\n## {title}")
    for name, fg, bg in pairs:
        r = contrast(fg, bg)
        R.verdict("PASS" if r >= 4.5 else "WARN" if r >= 3 else "FAIL", f"{r:5.2f}:1  {name}  ({fg} on {bg})")


def check_vs_page(cols, page, title):
    R.say(f"\n## {title}: contrast vs page {page} (lines/marks need 3:1)")
    for n, h in cols.items():
        r = contrast(h, page)
        R.verdict("PASS" if r >= 3 else "WARN", f"{r:5.2f}:1  {n} {h}" + ("" if r >= 3 else "  -> label it / thicker mark"))


def check_categorical(cols, title, shapes=None, grey=True, cap=None):
    """cols: {name: hex}. shapes: {name: shape} — pairs with different shapes are told apart by shape,
    so they are left out of the colour verdict and greyscale is INFO for them.
    grey=False: greyscale reported as INFO only (e.g. labelled arrows)."""
    R.say(f"\n## {title}: {', '.join(f'{k}={v}' for k, v in cols.items())}")
    if len(cols) < 2:
        return
    allpairs = list(itertools.combinations(cols.items(), 2))
    pairs = [p for p in allpairs if not shapes or shapes.get(p[0][0]) == shapes.get(p[1][0])]
    if shapes:
        R.say(f"        {len(allpairs) - len(pairs)} of {len(allpairs)} pairs differ in shape — colour verdict on the rest")
    for kind in VISION if pairs else ():
        ds = sorted((dE(a, b, kind), f"{na}~{nb}") for (na, a), (nb, b) in pairs)
        worst, wn = ds[0]
        if kind == "normal":
            lvl = "PASS" if worst >= 15 else "WARN" if worst >= 10 else "FAIL"
        elif kind == "tritan":
            lvl = "PASS" if worst >= 8 else "WARN"
        else:
            lvl = "PASS" if worst >= 8 else "WARN" if worst >= 6 else "FAIL"
        if cap == "WARN" and lvl == "FAIL":
            lvl = "WARN"
            wn += " — near-duplicate shades: one meaning -> one token; two meanings -> separate them"
        tail = ("  next: " + ", ".join(f"{d:.1f} {n}" for d, n in ds[1:3])) if len(ds) > 1 else ""
        R.verdict(lvl, f"{kind:7s} worst dE {worst:5.1f} ({wn}){tail}")
    ls = {n: lstar(h) for n, h in cols.items()}
    R.say("        greyscale L*: " + "  ".join(f"{n}={v:.0f}" for n, v in sorted(ls.items(), key=lambda x: x[1])))
    for (na, _), (nb, _) in allpairs:
        d = abs(ls[na] - ls[nb])
        if d >= 10:
            continue
        if not grey:
            R.verdict("INFO", f"grey dL* {d:4.1f} {na}~{nb} — needs label/dash in greyscale print")
        elif shapes and shapes.get(na) != shapes.get(nb):
            R.verdict("INFO", f"grey dL* {d:4.1f} {na}~{nb} — told apart by shape ({shapes.get(na)} / {shapes.get(nb)})")
        else:
            R.verdict("WARN" if d >= 5 else "FAIL", f"grey dL* {d:4.1f} {na}~{nb} — same in greyscale print")


# ---------------------------------------------------------------------------------------------
def load_theme(name, **kw):
    """light | graphite | night | path/to/theme.py -> theme dict (the same loader as kit.use_theme)"""
    import importlib.util
    path = name if name.endswith(".py") else os.path.join(HERE, "themes", f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"theme_{os.path.basename(path)[:-3]}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if hasattr(m, "build"):
        return m.build(**kw)
    return {k: getattr(m, k) for k in dir(m) if k.isupper()}


def check_theme(th):
    N, F = th["NEUTRAL"], th["FAMILY"]
    page = N["page"]
    surfaces = [k for k in ("page", "surface", "tile", "band") if k in N]
    text = []
    for s in surfaces:
        text += [(f"ink on {s}", N["ink"], N[s], 13, False), (f"ink2 on {s}", N["ink2"], N[s], 13, False),
                 (f"muted on {s}", N["muted"], N[s], 13, False)]
    text.append(("head_fg on head", th.get("HEAD_FG", "#ffffff"), N["head"], 13, True))
    for f, d in F.items():
        text += [(f"{f}: title on fill", d["title"], d["fill"], 13.5, True),
                 (f"{f}: ink on fill", N["ink"], d["fill"], 13, False),
                 (f"{f}: muted on fill", N["muted"], d["fill"], 13, False),
                 (f"{f}: title on tint", d["title"], d["tint"], 13, True),
                 (f"{f}: title on page", d["title"], page, 13, True)]
    for k, v in th["BAND"].items():
        if k not in ("today", "due"):
            text += [(f"band.{k}: ink", N["ink"], v, 13, False), (f"band.{k}: muted", N["muted"], v, 13, False)]
    check_text(text, "Text contrast (WCAG 2)")

    glyphs = [(f"status.{s} glyph '{g}'", gc, fill) for s, (fill, _, g, gc) in th["STATUS"].items() if g and g != "◐"]
    glyphs += [(f"{f}: glyph on solid", d["glyph"], d["solid"]) for f, d in F.items() if f not in ("white",)]
    check_glyphs(glyphs, "Glyphs on filled marks")

    # status: compare the colour that carries the mark's identity (ring colour for hollow marks)
    st_cols = {s: (fill if stroke is None or fill not in (page, "#ffffff") else stroke)
               for s, (fill, stroke, _, _) in th["STATUS"].items()}
    check_categorical(st_cols, "Statuses", shapes=th.get("STATUS_SHAPE"))
    FL = th["FLOW"]
    check_categorical(dict(FL), "Flows (arrows), all", grey=False)
    check_categorical({k: FL[k] for k in ("f1", "f2", "f3") if k in FL}, "Flows f1-f3 (the usual case)", grey=False)
    check_vs_page(dict(FL), page, "Flows")
    S = th["SERIES"]
    check_categorical({k: v for k, v in S.items() if k in ("before", "after", "neutral")}, "Series before/after/neutral")
    check_categorical({k: v for k, v in S.items() if k in ("before", "after", "neutral_mark", "extra")},
                      "Series as dots/lines", grey=False)
    check_vs_page(dict(S), page, "Series")
    fams = [f for f in F if f not in ("white",)]
    R.say("\n## Card families — informative: families are NOT separable by colour alone (never the only carrier)")
    for tier in ("border", "title", "fill"):
        cols = {f: F[f][tier] for f in fams}
        ds = sorted((min(dE(a, b, k) for k in ("protan", "deutan")), dE(a, b), f"{na}~{nb}")
                    for (na, a), (nb, b) in itertools.combinations(cols.items(), 2))
        R.verdict("INFO", f"{tier:6s} worst red-green dE {ds[0][0]:4.1f} ({ds[0][2]}), normal {ds[0][1]:4.1f};"
                  f" next {ds[1][0]:.1f} ({ds[1][2]}), {ds[2][0]:.1f} ({ds[2][2]})")


# ---------------------------------------------------------------------------------------------
def _norm(c):
    if not c or c == "none" or not c.startswith("#"):
        return None
    c = c.lower()
    return "#" + "".join(ch * 2 for ch in c[1:]) if len(c) == 4 else c


def _attr(el, name):
    st = el.get("style", "")
    m = re.search(rf"(?:^|;)\s*{name}\s*:\s*([^;]+)", st)
    return (m.group(1).strip() if m else el.get(name))


def _f(v, d=0.0):
    try:
        return float(re.sub(r"[a-z%]+$", "", v))
    except (TypeError, ValueError):
        return d


def _chroma(h):
    _, a, b = hex2oklab(h)
    return (a * a + b * b) ** 0.5


def check_svg(path, th=None):
    """Flat SVGs (the kit: absolute coords, no transforms). Page = first full-canvas rect. For matplotlib SVGs
    text is drawn as paths, so only the colour inventory, off-palette colours and stroke-colour CVD matter."""
    tree = ET.parse(path)
    ns = "{http://www.w3.org/2000/svg}"
    shapes, texts, strokes, dots, used = [], [], {}, {}, {}
    page = "#ffffff"
    hidden = set()
    known_shape = {}
    if th is not None:          # the theme knows each status mark's shape: use it instead of guessing
        pg = th["NEUTRAL"]["page"]
        for st, (fill, stroke, _, _) in th["STATUS"].items():
            known_shape[(stroke if stroke and fill in (pg, "#ffffff") else fill).lower()] = th["STATUS_SHAPE"][st]
    for el in tree.iter():
        tag = el.tag.replace(ns, "")
        if tag in ("defs", "marker", "clipPath", "filter", "pattern"):
            hidden.update(el.iter())
            continue
        if el in hidden:
            continue
        for a in ("fill", "stroke"):
            c = _norm(_attr(el, a))
            if c:
                used[c] = used.get(c, 0) + 1
        op = _f(_attr(el, "opacity"), 1)
        if tag == "rect":
            x, y, w, h = (_f(el.get(k)) for k in ("x", "y", "width", "height"))
            fill = _norm(_attr(el, "fill"))
            if not shapes and x <= 0 and y <= 0 and fill:
                page = fill                     # first full-canvas rect = the page
            if fill and w > 0 and h > 0 and op > 0.9:
                shapes.append((x, y, x + w, y + h, fill))
        elif tag == "circle":
            cx, cy, r = (_f(el.get(k)) for k in ("cx", "cy", "r"))
            fill, stroke = _norm(_attr(el, "fill")), _norm(_attr(el, "stroke"))
            if op < 0.9 or el.get("filter"):
                continue                        # halos behind glowing marks
            if fill:
                shapes.append((cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7, fill))
            if 3 < r < 14:
                key = stroke if stroke else fill
                if key:
                    dots[key] = known_shape.get(key) or (
                        "ring" if fill in (None, "#ffffff", page) or (stroke and stroke != fill) else "filled")
        elif tag in ("path", "line", "polyline"):
            s = _norm(_attr(el, "stroke"))
            if s and _f(_attr(el, "stroke-width"), 1) >= 1.5 and op > 0.9:
                strokes[s] = strokes.get(s, 0) + 1
        elif tag == "text":
            fill = _norm(_attr(el, "fill")) or "#000000"
            size = _f(_attr(el, "font-size"), 12)
            bold = _f(_attr(el, "font-weight") or "400", 400) >= 700
            x, y = _f(el.get("x")), _f(el.get("y"))
            s = "".join(el.itertext()).strip()
            texts.append((x, y - size * 0.35, fill, size, bold, s, len(shapes)))
    R.say(f"# SVG {path}  (page {page})")
    bad, n = [], 0
    for x, y, fg, size, bold, s, upto in texts:
        bg = page
        for x0, y0, x1, y1, f in shapes[:upto]:
            if x0 <= x <= x1 and y0 <= y <= y1:
                bg = f
        if fg == bg or (len(s) <= 2 and size < 12):     # digits inside step badges are checked as glyphs
            continue
        n += 1
        r = contrast(fg, bg)
        if r < (3.0 if (size >= 24 or (bold and size >= 18.7)) else 4.5):
            bad.append((r, fg, bg, size, s[:50]))
    R.say(f"\n## Text on background: {n} text runs checked")
    for r, fg, bg, size, s in sorted(bad)[:25]:
        R.verdict("FAIL", f"{r:4.2f}:1 {fg} on {bg} {size}px  “{s}”")
    if not bad:
        R.verdict("PASS", "every text run >= 4.5:1 (3:1 large)")
    chromatic = {c: k for c, k in strokes.items() if _chroma(c) > 0.04}
    check_categorical({c: c for c in chromatic}, "Coloured strokes (arrows / flows / box edges)", grey=False, cap="WARN")
    check_categorical({c: c for c in dots}, "Small circles (status marks)", shapes={c: k for c, k in dots.items()})
    if th is not None:
        known = {v.lower() for v in PAL.tokens(th).values()} | {"#ffffff", "#000000"}
        off = {c: k for c, k in used.items() if c not in known}
        R.say(f"\n## Palette conformity: {len(used)} colours used, {len(off)} not in the theme")
        for c, k in sorted(off.items(), key=lambda x: -x[1])[:20]:
            R.verdict("WARN", f"off-palette {c} used {k}x")
    return page


def run_svg(path, th=None, silent=True):
    """for kit.write(): returns the list of (level, msg) for one SVG"""
    global R
    old, R = R, Report(silent=silent)
    try:
        check_svg(path, th)
        return R.items
    finally:
        R = old


def main():
    global R
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", help="light | graphite | night | path/to/theme.py")
    ap.add_argument("--colors")
    ap.add_argument("--page", default=None, help="background for --colors (default: the theme's page, else white)")
    ap.add_argument("--svg", nargs="*")
    ap.add_argument("--hues")
    ap.add_argument("--dark", action="store_true", help="--hues: build families for a dark page (family_night)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    R = Report(quiet=a.quiet)
    th = load_theme(a.theme) if a.theme else None
    if a.colors:
        items = [c.strip() for c in a.colors.split(",") if c.strip()]
        cols = dict((c.split("=", 1) if "=" in c else (c, c)) for c in items)
        check_categorical(cols, "Colour set")
        check_vs_page(cols, a.page or (th["NEUTRAL"]["page"] if th else "#ffffff"), "Colour set")
    elif a.hues:
        base = th or load_theme("night" if a.dark else "light")
        N = base["NEUTRAL"]
        fams = {}
        for item in a.hues.split(","):
            name, spec = item.split("=")
            h, _, ch = spec.partition(":")
            if a.dark:
                fams[name.strip()] = PAL.family_night(float(h), float(ch) if ch else 0.11, muted=N["muted"],
                                                      glyph=base.get("DARK_GLYPH", N["page"]))
            else:
                fams[name.strip()] = PAL.family(float(h), float(ch) if ch else 0.115, text_on_fill=N["muted"])
        print("# Families")
        for nm, f in fams.items():
            print(f"  {nm:12s} " + "  ".join(f"{k}={v}" for k, v in f.items()))
        check_text([(f"{nm}: {k}", fg, f[bg], 13, True) for nm, f in fams.items()
                    for k, fg, bg in (("title on fill", f["title"], "fill"), ("muted on fill", N["muted"], "fill"),
                                      ("ink on fill", N["ink"], "fill"), ("title on tint", f["title"], "tint"))],
                   "Text contrast")
        check_glyphs([(f"{nm}: glyph on solid", f["glyph"], f["solid"]) for nm, f in fams.items()], "Glyphs")
        check_categorical({nm: f["solid"] for nm, f in fams.items()}, "Solids (marks / arrows) — must separate",
                          grey=False)
    elif a.svg:
        for p in a.svg:
            check_svg(p, th)
    else:
        th = th or load_theme("light")
        print(f"# Theme {th.get('NAME', a.theme)}")
        check_theme(th)
    nf = R.count("FAIL")
    print(f"\n{'FAIL: ' + str(nf) if nf else 'OK: no FAIL'} ({R.count('WARN')} WARN)")
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    main()
