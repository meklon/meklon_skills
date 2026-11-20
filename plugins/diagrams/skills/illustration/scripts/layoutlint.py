#!/usr/bin/env python3
"""layoutlint — layout checks for engineering illustrations, on geometry only (no renderer needed).

Core: check(W, H, texts, rects, lines) works on a *journal* of what was drawn:
  texts  dict(id, s, bb=(x, y, w, h) ink box, size, fill, role='text'|'tag'|'glyph')
  rects  dict(id, bb, fill, role='box'|'tag'|'swatch', own=<text id for a tag>, name=optional)
  lines  dict(id, polys=[[(x, y), ...]], arrow=bool, stroke)
The SVG kit (kit.py) fills this journal itself while drawing — text widths come from the same font file
the picture names, through PIL. No Inkscape, no browser.

Optional second source: load_svg(path) builds the same journal from any flat SVG (text / rect / path / line /
circle, no transforms) using `inkscape --query-all` for real glyph boxes — a cross-check that the renderer
used the font the metrics assumed, and a way to lint SVGs made by something else.

CLI:  layoutlint.py picture.svg [--preview 1000] [--min-px 8] [--page '#ffffff'] [--png annotated.png]
      (needs inkscape; the page colour is read from the first full-canvas rect unless --page is given)

ERROR  TEXT×TEXT    two texts overlap
ERROR  TEXT×TAG     a pill / arrow-label background covers a foreign text
ERROR  TEXT-EDGE    text crosses the border of a box (out of its card, or into a neighbour)
ERROR  TEXT-CANVAS  text outside the canvas
ERROR  LINE×TEXT    a line or arrow runs through a text (a label sitting on its own line is fine)
ERROR  ARROW×BOX    an arrow runs through a card that is neither its source nor its target
ERROR  BOX×BOX      two sibling cards overlap
ERROR  SMALL        font size below --min-px once the picture is scaled to --preview px wide
WARN   GRID×TEXT    a hairline grid (contrast < 1.35 to the page colour) under texts — aggregated per colour
WARN   TIGHT-PAD    text closer than --pad px to the border of its own box
WARN   TIGHT-GAP    two facing sibling cards closer than --gap px
WARN   DETOUR       arrow with > 3 segments, or > 1.6x longer than the direct route
WARN   ROW-HEIGHT   sibling cards with the same top but different heights
WARN   EMPTY        a card whose bottom 40 % (and > 48 px) is empty
WARN   CONTRAST     text vs its box fill below 4.5:1 (WCAG AA)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


# ------------------------------------------------------------------ geometry
def inter(a, b, m=0.0):
    return not (a[0] + a[2] <= b[0] + m or b[0] + b[2] <= a[0] + m or a[1] + a[3] <= b[1] + m or b[1] + b[3] <= a[1] + m)


def contains(r, q, tol=0.5):
    return (r[0] - tol <= q[0] and r[1] - tol <= q[1] and q[0] + q[2] <= r[0] + r[2] + tol
            and q[1] + q[3] <= r[1] + r[3] + tol)


def shrink(r, m):
    return (r[0] + m, r[1] + m, r[2] - 2 * m, r[3] - 2 * m)


def seg_hits_rect(p, q, r):
    """segment p-q intersects the open rectangle r (Liang-Barsky)"""
    x0, y0, x1, y1 = r[0], r[1], r[0] + r[2], r[1] + r[3]
    if x1 <= x0 or y1 <= y0:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < 1e-9:
            if qq <= 0:
                return False
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 >= t1:
            return False
    return True


def path_points(d):
    """M L H V Z C S Q T A (abs / rel) -> polylines; curves approximated by their end points"""
    toks = re.findall(r"[MLHVZCSQTAmlhvzcsqta]|-?[\d.]+(?:e-?\d+)?", d)
    nargs = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)
    polys, pts, cur, start, cmd, i = [], [], [0.0, 0.0], [0.0, 0.0], "M", 0
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if pts:
                    pts.append(tuple(start))
                cur = list(start)
                continue
        n = nargs[cmd.upper()]
        v = [float(x) for x in toks[i:i + n]]
        i += n
        rel, C = cmd.islower(), cmd.upper()
        if C == "M":
            if pts:
                polys.append(pts)
            cur = [cur[0] + v[0], cur[1] + v[1]] if rel else v[:]
            start, pts = cur[:], [tuple(cur)]
            cmd = "l" if rel else "L"
            continue
        if C == "H":
            cur = [cur[0] + v[0] if rel else v[0], cur[1]]
        elif C == "V":
            cur = [cur[0], cur[1] + v[0] if rel else v[0]]
        else:
            cur = [cur[0] + v[-2], cur[1] + v[-1]] if rel else [v[-2], v[-1]]
        pts.append(tuple(cur))
    if pts:
        polys.append(pts)
    return polys


def _lum(c):
    c = (c or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        return None
    v = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    if la is None or lb is None:
        return None
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ------------------------------------------------------------------ core
def check(W, H, texts, rects, lines, preview=1000, min_px=8.0, gap=10.0, pad=6.0, page="#ffffff"):
    """page: background colour — a hairline is judged against it (dark themes)."""
    issues = []

    def add(level, code, msg, *bbs):
        issues.append(dict(level=level, code=code, msg=msg, bbs=[[float(v) for v in b] for b in bbs]))

    boxes = [r for r in rects if r.get("role", "box") == "box" and not (r["bb"][2] >= W - 1 and r["bb"][3] >= H - 1)]
    tags = [r for r in rects if r.get("role") == "tag"]
    skip = {t["id"] for t in texts if t.get("role") in ("tag", "glyph")}
    opaque = [r for r in rects if (r.get("fill") or "none") not in ("none", "transparent")]
    for b in boxes:
        kids = [q for q in boxes if q is not b and contains(b["bb"], q["bb"]) and q["bb"] != b["bb"]]
        b["leaf"] = not kids
        par = [q for q in boxes if q is not b and contains(q["bb"], b["bb"]) and q["bb"] != b["bb"]]
        b["parent"] = min(par, key=lambda q: q["bb"][2] * q["bb"][3])["id"] if par else None
        b["inner"] = sorted((t for t in texts if t["id"] not in skip and contains(b["bb"], t["bb"], 1)),
                            key=lambda t: (t["bb"][1], t["bb"][0]))
        b["name"] = b.get("name") or (b["inner"][0]["s"][:40] if b["inner"] else b["id"])

    # SMALL — judged at the width people actually see (task-tracker preview, laptop)
    k = preview / W
    small = {}
    for t in texts:
        if t.get("role") != "glyph" and t["size"] * k < min_px - 1e-6:
            small.setdefault(t["size"], []).append(t)
    for s, lst in sorted(small.items()):
        add("ERROR", "SMALL", f"{s:g}px -> {s * k:.1f}px at {preview}px wide: {len(lst)} texts, e.g. «{lst[0]['s'][:40]}»",
            *[t["bb"] for t in lst[:20]])

    for i, a in enumerate(texts):
        for c in texts[i + 1:]:
            if inter(a["bb"], c["bb"], 0.8) and not ({a.get("role"), c.get("role")} & {"glyph"}):
                add("ERROR", "TEXT×TEXT", f"«{a['s'][:35]}» × «{c['s'][:35]}»", a["bb"], c["bb"])
    for r in tags:
        own = next((t["s"] for t in texts if t["id"] == r.get("own")), "?")
        for t in texts:
            if t["id"] != r.get("own") and t.get("role") != "glyph" and inter(r["bb"], t["bb"], 0.8):
                add("ERROR", "TEXT×TAG", f"tag «{own[:30]}» covers «{t['s'][:35]}»", r["bb"], t["bb"])
        for b in boxes:   # a tag mostly inside a card but clipping its border reads as a glitch;
            #               a badge deliberately centred on the border (about half in) is a style, not a bug
            ix = max(0, min(r["bb"][0] + r["bb"][2], b["bb"][0] + b["bb"][2]) - max(r["bb"][0], b["bb"][0]))
            iy = max(0, min(r["bb"][1] + r["bb"][3], b["bb"][1] + b["bb"][3]) - max(r["bb"][1], b["bb"][1]))
            frac = ix * iy / (r["bb"][2] * r["bb"][3])
            if b["leaf"] and (0.75 < frac < 0.999 or 0 < frac < 0.25):
                add("WARN", "TAG-EDGE", f"tag «{own[:30]}» clips the border of «{b['name']}»", r["bb"])

    for t in texts:
        x, y, w, h = t["bb"]
        if x < 0 or y < 0 or x + w > W or y + h > H:
            add("ERROR", "TEXT-CANVAS", f"«{t['s'][:40]}» outside the canvas", t["bb"])
        if t["id"] in skip:
            continue
        for b in boxes:
            if inter(b["bb"], t["bb"], 0.5) and not contains(b["bb"], t["bb"], 0.5):
                add("ERROR", "TEXT-EDGE", f"«{t['s'][:40]}» crosses the border of «{b['name']}»", t["bb"], b["bb"])
        hosts = [b for b in boxes if contains(b["bb"], t["bb"], 0.5)]
        if hosts:
            hb = min(hosts, key=lambda q: q["bb"][2] * q["bb"][3])
            bx, by, bw, bh = hb["bb"]
            m = min(x - bx, y - by, bx + bw - x - w, by + bh - y - h)
            if m < pad:
                add("WARN", "TIGHT-PAD", f"«{t['s'][:40]}» {m:.1f}px from the border of «{hb['name']}»", t["bb"])
        under = [r for r in opaque if r.get("z", -1) < t.get("z", 1e9) and contains(r["bb"], t["bb"], 0.5)]
        if under:
            bg = max(under, key=lambda r: r.get("z", 0))       # what is actually painted under the text
            cr = contrast(t.get("fill"), bg.get("fill"))
            if cr is not None and cr < 4.5:
                add("WARN", "CONTRAST", f"«{t['s'][:40]}» {t['fill']} on {bg['fill']}: {cr:.1f}:1", t["bb"])

    grid = {}
    for ln in lines:
        segs = [(p, q) for poly in ln["polys"] for p, q in zip(poly, poly[1:])]
        if not segs:
            continue
        xs = [p[0] for poly in ln["polys"] for p in poly]
        ys = [p[1] for poly in ln["polys"] for p in poly]
        lbb = (min(xs) - 2, min(ys) - 2, max(xs) - min(xs) + 4, max(ys) - min(ys) + 4)
        kind = "arrow" if ln.get("arrow") else "line"
        lz = ln.get("z", 0)
        for t in texts:
            if t["id"] in skip:
                continue
            if any(r.get("z", -1) > lz and r.get("z", -1) < t.get("z", 1e9) and contains(r["bb"], t["bb"], 1)
                   for r in opaque):
                continue        # the line is painted over by the box the text sits on
            r = (t["bb"][0] - 2, t["bb"][1] - 2, t["bb"][2] + 4, t["bb"][3] + 4)
            if any(seg_hits_rect(p, q, r) for p, q in segs):
                cr = contrast(ln.get("stroke"), page)
                if not ln.get("arrow") and cr is not None and cr < 1.35:     # hairline grid: nit, aggregated
                    grid.setdefault(ln.get("stroke"), []).append(t)
                else:
                    add("ERROR", "LINE×TEXT", f"{kind} {ln.get('stroke')} runs through «{t['s'][:40]}»", t["bb"], lbb)
        if not ln.get("arrow"):
            continue
        for b in boxes:
            if b["leaf"] and any(seg_hits_rect(p, q, shrink(b["bb"], 5)) for p, q in segs):
                add("ERROR", "ARROW×BOX", f"arrow {ln.get('stroke')} runs through «{b['name']}»", b["bb"], lbb)
        length = sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in segs)
        a0, a1 = ln["polys"][0][0], ln["polys"][-1][-1]
        direct = abs(a0[0] - a1[0]) + abs(a0[1] - a1[1])
        if len(segs) > 3 or (direct > 0 and length > 1.6 * direct and length > 250):
            add("WARN", "DETOUR", f"arrow {ln.get('stroke')}: {len(segs)} segments, {length:.0f}px for {direct:.0f}px direct", lbb)

    for col, ts in grid.items():
        uniq = list({t["id"]: t for t in ts}.values())
        add("WARN", "GRID×TEXT", f"grid line {col} runs under {len(uniq)} texts, e.g. «{uniq[0]['s'][:30]}»: "
            f"give labels a background or stop the grid", *[t["bb"] for t in uniq[:10]])
    for t in texts:
        if t.get("orphan"):
            add("WARN", "ORPHAN", f"«{t['s']}» is alone on the last line: rephrase or change the width", t["bb"])
    # whole-picture budget: a picture that needs scrolling or reading like a page belongs in text
    words = sum(len(t["s"].split()) for t in texts if t.get("role") != "glyph")
    if H / W > 1.25:
        add("WARN", "CANVAS", f"canvas {W:.0f}x{H:.0f} (H/W {H / W:.2f}) is taller than a laptop screen: split it")
    if words > 450:
        add("WARN", "WORDS", f"{words} words on the picture: move detail to the task text (aim < 300)")
    leaves = [b for b in boxes if b["leaf"]]
    for i, a in enumerate(boxes):
        for c in boxes[i + 1:]:
            if a["parent"] != c["parent"] or contains(a["bb"], c["bb"]) or contains(c["bb"], a["bb"]):
                continue
            if inter(a["bb"], c["bb"], 0.5):
                add("ERROR", "BOX×BOX", f"«{a['name']}» overlaps «{c['name']}»", a["bb"], c["bb"])
                continue
            ax, ay, aw, ah = a["bb"]
            cx, cy, cw, ch = c["bb"]
            dx = max(cx - (ax + aw), ax - (cx + cw))
            dy = max(cy - (ay + ah), ay - (cy + ch))
            if dx < 0 <= dy < gap or dy < 0 <= dx < gap:
                add("WARN", "TIGHT-GAP", f"«{a['name']}» and «{c['name']}»: {max(dx, dy):.1f}px apart", a["bb"], c["bb"])
    seen = set()
    for a in leaves:
        for c in leaves:
            if c is a or c["parent"] != a["parent"] or abs(c["bb"][1] - a["bb"][1]) > 1.5:
                continue
            key = tuple(sorted((a["id"], c["id"])))
            wr = max(a["bb"][2], c["bb"][2]) / max(1, min(a["bb"][2], c["bb"][2]))
            if key not in seen and abs(a["bb"][3] - c["bb"][3]) > 2 and wr <= 1.35:
                seen.add(key)
                add("WARN", "ROW-HEIGHT", f"«{a['name']}» {a['bb'][3]:.0f}px vs «{c['name']}» {c['bb'][3]:.0f}px, same top",
                    a["bb"], c["bb"])
    for b in leaves:
        if b["inner"] and not b.get("equal_row"):
            bottom = max(t["bb"][1] + t["bb"][3] for t in b["inner"])
            empty = b["bb"][1] + b["bb"][3] - bottom
            if empty > max(48, 0.4 * b["bb"][3]):
                add("WARN", "EMPTY", f"«{b['name']}»: bottom {empty:.0f}px of {b['bb'][3]:.0f}px empty", b["bb"])
    return issues


def report(issues, title="", show_warn=True):
    ne = sum(i["level"] == "ERROR" for i in issues)
    print(f"{title}: {ne} errors, {len(issues) - ne} warnings")
    for n, i in enumerate(issues, 1):
        if show_warn or i["level"] == "ERROR":
            print(f"  {n:3d} {i['level']:5s} {i['code']:11s} {i['msg']}")
    return ne


def summary(issues):
    """'2 ERROR (TEXT×TEXT×2), 3 WARN (TIGHT-PAD×2, EMPTY)' — one line for the kit's write()"""
    out = []
    for lvl in ("ERROR", "WARN"):
        codes = {}
        for i in issues:
            if i["level"] == lvl:
                codes[i["code"]] = codes.get(i["code"], 0) + 1
        n = sum(codes.values())
        tail = ", ".join(f"{c}×{k}" if k > 1 else c for c, k in sorted(codes.items(), key=lambda x: -x[1]))
        out.append(f"{n} {lvl}" + (f" ({tail})" if tail else ""))
    return ", ".join(out)


def page_of(path):
    """colour of the first full-canvas rect (the page), else white"""
    root = ET.parse(path).getroot()
    for el in root.iter():
        if el.tag.replace(NS, "") == "rect" and _num(el.get("x")) <= 0 and _num(el.get("y")) <= 0 and \
                (el.get("width") in (None, "100%") or _num(el.get("width")) >= _num(root.get("width"), 1e9) - 1):
            return el.get("fill") or "#ffffff"
    return "#ffffff"


def annotate(png, W, issues, out):
    """red / orange frames + issue numbers over a rendered PNG — for the visual pass"""
    from PIL import Image, ImageDraw
    im = Image.open(png).convert("RGB")
    k = im.width / W
    d = ImageDraw.Draw(im)
    for n, it in enumerate(issues, 1):
        col = (220, 0, 0) if it["level"] == "ERROR" else (230, 140, 0)
        for b in it["bbs"][:2]:
            d.rectangle([b[0] * k - 2, b[1] * k - 2, (b[0] + b[2]) * k + 2, (b[1] + b[3]) * k + 2], outline=col, width=3)
        if it["bbs"]:
            b = it["bbs"][0]
            d.text((b[0] * k, max(0, b[1] * k - 14)), str(n), fill=col)
    im.save(out)


# ------------------------------------------------------------------ optional: journal from an SVG via inkscape
NS = "{http://www.w3.org/2000/svg}"


def _num(v, default=0.0):
    try:
        return float(re.match(r"-?[\d.]+", str(v)).group())
    except Exception:
        return default


def load_svg(path, env=None):
    """env: environment for inkscape (kit passes FONTCONFIG_FILE so the bundled fonts are used)"""
    tree = ET.parse(path)
    root = tree.getroot()
    vb = [float(x) for x in re.split(r"[\s,]+", root.get("viewBox").strip())] if root.get("viewBox") else None
    W = vb[2] if vb else _num(root.get("width"))
    H = vb[3] if vb else _num(root.get("height"))
    items, transforms = [], [0]

    def style(el, parents):
        st = {}
        for e in parents + [el]:
            for k in ("font-size", "fill", "stroke", "marker-end", "marker-start"):
                if e.get(k) is not None:
                    st[k] = e.get(k)
            for part in (e.get("style") or "").split(";"):
                if ":" in part:
                    a, b = part.split(":", 1)
                    st[a.strip()] = b.strip()
        return st

    def walk(el, parents, hidden):
        tag = el.tag.replace(NS, "")
        hidden = hidden or tag in ("defs", "marker", "clipPath", "symbol", "pattern")
        if el.get("transform") and not hidden:
            transforms[0] += 1
        if tag in ("text", "rect", "path", "line", "polyline", "circle", "ellipse") and not hidden:
            el.set("id", f"L{len(items)}")
            items.append((el, tag, style(el, parents)))
        for ch in list(el):
            walk(ch, parents + [el], hidden)

    walk(root, [], False)
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "ids.svg")
        tree.write(tmp)
        out = subprocess.run(["inkscape", "--query-all", tmp], capture_output=True, text=True, env=env).stdout
    bb = {p[0]: tuple(float(x) for x in p[1:]) for p in (ln.split(",") for ln in out.splitlines()) if len(p) == 5}
    sx = (vb[2] / _num(root.get("width"), vb[2])) if vb else 1.0
    texts, rects, lines, circles = [], [], [], []
    for z, (el, tag, st) in enumerate(items):
        b = bb.get(el.get("id"))
        if b is None:
            continue
        b = tuple(v * sx for v in b)
        if tag == "text":
            s = "".join(el.itertext()).strip()
            if s:
                texts.append(dict(id=el.get("id"), s=s, bb=b, size=_num(st.get("font-size"), 16),
                                  fill=st.get("fill", "#000000"), role="text", z=z))
        elif tag == "rect":
            r = (_num(el.get("x")), _num(el.get("y")), _num(el.get("width")), _num(el.get("height")))
            if r[2] > 0 and r[3] > 0:
                # cards have a border; fill-only rects are bands / bars / row highlights: opaque, but not boxes
                stroked = st.get("stroke", "none") not in ("none", "")
                rects.append(dict(id=el.get("id"), bb=r, fill=st.get("fill", "#000000"),
                                  role="box" if stroked else "band", z=z))
        elif tag in ("path", "line", "polyline"):
            if st.get("stroke", "none") == "none":
                continue
            if tag == "line":
                polys = [[(_num(el.get("x1")), _num(el.get("y1"))), (_num(el.get("x2")), _num(el.get("y2")))]]
            elif tag == "polyline":
                v = [float(x) for x in re.split(r"[\s,]+", el.get("points", "").strip()) if x]
                polys = [list(zip(v[0::2], v[1::2]))]
            else:
                polys = path_points(el.get("d", ""))
            lines.append(dict(id=el.get("id"), polys=polys, arrow=bool(st.get("marker-end") or st.get("marker-start")),
                              stroke=st.get("stroke"), z=z))
        elif tag in ("circle", "ellipse"):
            circles.append(b)
    # roles the kit would have told us: glyphs inside bullet circles, tags (pill / label backgrounds), swatches
    for t in texts:
        if any(contains(c, t["bb"], 1.5) for c in circles):
            t["role"] = "glyph"
    for r in rects:
        inside = [t for t in texts if t["role"] != "glyph" and contains(r["bb"], t["bb"], 1)]
        if r["role"] == "band" and not (len(inside) == 1 and r["bb"][3] <= inside[0]["size"] * 2.4):
            continue
        if len(inside) == 1 and r["bb"][3] <= inside[0]["size"] * 2.4 and r["bb"][2] <= inside[0]["bb"][2] + 4 * inside[0]["size"]:
            r["role"], r["own"] = "tag", inside[0]["id"]
            inside[0]["role"] = "tag"
        elif not inside and r["bb"][2] < 60 and r["bb"][3] < 30:
            r["role"] = "swatch"
    return W, H, texts, rects, lines, transforms[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svg")
    ap.add_argument("--preview", type=int, default=1000)
    ap.add_argument("--min-px", type=float, default=8.0)
    ap.add_argument("--gap", type=float, default=10.0)
    ap.add_argument("--pad", type=float, default=6.0)
    ap.add_argument("--png", help="annotated PNG output (renders the SVG with inkscape if no PNG lies next to it)")
    ap.add_argument("--page", help="page colour (default: the SVG's first full-canvas rect)")
    ap.add_argument("--errors-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    W, H, texts, rects, lines, ntr = load_svg(a.svg)
    issues = check(W, H, texts, rects, lines, a.preview, a.min_px, a.gap, a.pad, page=a.page or page_of(a.svg))
    if ntr:
        print(f"note: {ntr} transformed elements; geometry of those is not reliable")
    if a.json:
        print(json.dumps(issues, ensure_ascii=False, indent=1))
    else:
        report(issues, a.svg, not a.errors_only)
    if a.png:
        src = a.svg[:-4] + ".png"
        if not os.path.exists(src):
            subprocess.run(["inkscape", a.svg, "--export-type=png", f"--export-filename={src}", "--export-width=2400"],
                           check=True, capture_output=True)
        annotate(src, W, issues, a.png)
    sys.exit(1 if any(i["level"] == "ERROR" for i in issues) else 0)


if __name__ == "__main__":
    main()
