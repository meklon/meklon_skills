"""SVG kit for engineering illustrations: themes, a type scale, layout helpers, vector status marks and a self-lint.

    import sys; sys.path.insert(0, "<skill>/scripts")
    import kit as K
    K.use_theme("light")                 # light | graphite | night | /path/to/theme.py  (+ hues={...} overrides)
    ... draw with K.text / K.card / K.cards_row / K.connect / K.bullets_row / K.zone ...
    K.write("out/picture.svg", 1600, H)  # SVG -> PNG 2400 -> preview 1000 -> layoutlint -> palette_check

Every drawing call records its geometry in a journal (REG): the ink box of each text from the same font file
the SVG names (PIL metrics), boxes with their role, arrows as polylines, paint order. write() lints that journal
(no renderer needed), renders with whatever renderer is installed, checks colours in the SVG against the theme
and, if inkscape is there, cross-checks the journal against inkscape's real text boxes.

Fonts: IBM Plex Sans / Mono from <skill>/fonts, else installed system-wide, else DejaVu (matplotlib's copy, then
the system's). Renderers get the same files (FONTCONFIG_FILE / font dirs / @font-face), so metrics hold.
Env: KIT_THEME (default theme), KIT_RENDERER=resvg|rsvg|inkscape|cairosvg|chrome (force one; comma list = order),
KIT_FONT=dejavu (force the fallback font), KIT_FC_ISOLATE=1 (renderers see only the kit's fonts).
"""
import base64
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html import escape

from PIL import Image, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FONT_DIR = os.path.join(SKILL, "fonts")
sys.path.insert(0, HERE)
import layoutlint  # noqa: E402
import palette as PAL  # noqa: E402

# ====================================================================================================== fonts
SANS_FILES = {300: "IBMPlexSans-Light.ttf", 400: "IBMPlexSans-Regular.ttf", 450: "IBMPlexSans-Text.ttf",
              500: "IBMPlexSans-Medium.ttf", 600: "IBMPlexSans-SemiBold.ttf", 700: "IBMPlexSans-Bold.ttf"}
MONO_FILE = "IBMPlexMono-Regular.ttf"
DEJAVU = {400: "DejaVuSans.ttf", 700: "DejaVuSans-Bold.ttf"}
DEJAVU_MONO = "DejaVuSansMono.ttf"
SYSTEM_FONT_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.local/share/fonts"),
                    os.path.expanduser("~/.fonts"), "/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
                    "/System/Library/Fonts", "C:\\Windows\\Fonts"]
_sys_index = None


def _system_font(fname):
    global _sys_index
    if _sys_index is None:
        _sys_index = {}
        for d in SYSTEM_FONT_DIRS:
            for root, _, files in os.walk(d):
                for f in files:
                    _sys_index.setdefault(f, os.path.join(root, f))
    return _sys_index.get(fname)


def _mpl_font(fname):
    try:
        spec = importlib.util.find_spec("matplotlib")
        if spec is None or not spec.submodule_search_locations:
            return None
        p = os.path.join(list(spec.submodule_search_locations)[0], "mpl-data", "fonts", "ttf", fname)
        return p if os.path.exists(p) else None
    except Exception:
        return None


def _bundled(fname):
    p = os.path.join(FONT_DIR, fname)
    return p if os.path.exists(p) else None


def _resolve_fonts():
    """{family, mono_family, files {weight: path}, mono, svg {weight: (family, weight)}, faces [(fam, w, path)]}"""
    if os.environ.get("KIT_FONT", "plex").lower() != "dejavu":
        found = {w: _bundled(f) or _system_font(f) for w, f in SANS_FILES.items()}
        mono = _bundled(MONO_FILE) or _system_font(MONO_FILE)
        have = {w: p for w, p in found.items() if p}
        if 400 in have and (600 in have or 700 in have):
            files, svg = {}, {}
            for w in SANS_FILES:                      # a missing weight -> the nearest one that exists
                aw = w if w in have else min(have, key=lambda v: (abs(v - w), -v))
                files[w] = have[aw]
                # the Text cut is its own family for fontconfig / chrome; resvg only knows it as Plex Sans (-> Regular)
                svg[w] = ("IBM Plex Sans Text, IBM Plex Sans", 400) if aw == 450 else (None, aw)
            missing = [SANS_FILES[w] for w in SANS_FILES if w not in have]
            if missing:
                print(f"note: {', '.join(missing)} not found — nearest weight used instead")
            faces = [("IBM Plex Sans", aw, have[aw]) for aw in have if aw != 450]
            if 450 in have:
                faces.append(("IBM Plex Sans Text", 400, have[450]))
            mono_fam = "IBM Plex Mono"
            if not mono:
                mono, mono_fam = _font_path(DEJAVU_MONO), "DejaVu Sans Mono"
            if mono:
                faces.append((mono_fam, 400, mono))
            return dict(name="plex", family="IBM Plex Sans", mono_family=mono_fam, files=files, mono=mono,
                        svg=svg, faces=faces)
        print(f"note: IBM Plex Sans not found (put the TTFs into {FONT_DIR}) — falling back to DejaVu Sans")
    reg, bold, mono = _font_path(DEJAVU[400]), _font_path(DEJAVU[700]), _font_path(DEJAVU_MONO)
    if not reg:
        raise SystemExit("no usable font: neither IBM Plex Sans nor DejaVu Sans found")
    bold = bold or reg
    files = {w: (reg if w <= 500 else bold) for w in SANS_FILES}
    svg = {w: (None, 400 if w <= 500 else 700) for w in SANS_FILES}
    faces = [("DejaVu Sans", 400, reg), ("DejaVu Sans", 700, bold)] + ([("DejaVu Sans Mono", 400, mono)] if mono else [])
    return dict(name="dejavu", family="DejaVu Sans", mono_family="DejaVu Sans Mono", files=files, mono=mono or reg,
                svg=svg, faces=faces)


def _font_path(fname):
    return _bundled(fname) or _mpl_font(fname) or _system_font(fname)


FONTS = _resolve_fonts()
FAMILY = FONTS["family"]
_fc = {}


def _wt(bold):
    """True / None / False / int -> numeric weight in the current theme (night: bold = 600, regular = 450)"""
    if bold is True:
        return TH["WEIGHT"]["bold"]
    if bold is None or bold is False:
        return TH["WEIGHT"]["regular"]
    return int(bold)


def _near(w):
    return w if w in FONTS["files"] else min(FONTS["files"], key=lambda v: (abs(v - w), -v))


def _font(size, w, mono=False):
    k = (size, w, mono)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONTS["mono"] if mono else FONTS["files"][_near(w)], size)
    return _fc[k]


_nd = {}


def _missing(s, w, mono):
    """characters of s the font has no glyph for (the renderer would substitute another font or draw a box)"""
    out = []
    for ch in set(s):
        if ord(ch) < 128 or ch.isspace():
            continue
        k = (ch, _near(w), mono)
        if k not in _nd:
            f = _font(20, w, mono)
            def sig(c):
                m = f.getmask(c)
                return bytes(m), m.size, f.getlength(c)
            _nd[k] = sig(ch) == sig("\uffff")
        if _nd[k]:
            out.append(ch)
    return out


def _svg_font(w, mono):
    """(font-family attribute or None, svg weight) for a requested weight"""
    if mono:
        return f"{FONTS['mono_family']}, monospace", 400
    fam, sw = FONTS["svg"][_near(w)]
    return fam, sw


def _track(size):
    for lim, ls in TH.get("TRACK_BY_SIZE", ()):
        if size <= lim:
            return ls
    return 0.0


def tw(s, size=None, bold=None, ls=None, mono=False):
    """advance width of s in px, incl. letter-spacing (theme default for the size when ls is None)"""
    size = size or T["small"][0]
    ls = _track(size) if ls is None else ls
    return _font(size, 400 if mono else _wt(bold), mono).getlength(s) + ls * max(len(s) - 1, 0)


def wrap(s, width, size=None, bold=None, mono=False, ls=None):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if tw(t, size, bold, ls, mono) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _orphan(lines, j):
    """mark the journal entry of the last wrapped line when it is a single word (layoutlint: ORPHAN)"""
    if j is not None and len(lines) >= 2 and len(lines[-1].split()) == 1:
        j["orphan"] = True


# ====================================================================================================== themes
TH, T, LS, C = {}, {}, {}, {}
LEGACY = {"blue": "ours", "violet": "external", "orange": "focus", "green": "ok", "amber": "attention",
          "red": "danger", "grey": "neutral", "accent": "focus"}


def _load_theme(name, **overrides):
    path = name if name.endswith(".py") else os.path.join(HERE, "themes", f"{name}.py")
    if not os.path.exists(path):
        raise SystemExit(f"theme not found: {name} (light | graphite | night | path/to/theme.py)")
    spec = importlib.util.spec_from_file_location(f"kit_theme_{os.path.basename(path)[:-3]}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if hasattr(m, "build"):
        return m.build(**overrides)
    if overrides:
        raise SystemExit(f"theme {name} has no build(): overrides {list(overrides)} are not supported")
    return {k: getattr(m, k) for k in dir(m) if k.isupper()}


def use_theme(name=None, **overrides):
    """Switch the theme: 'light' (default) | 'graphite' | 'night' | path to a theme file.
    overrides go to the theme's build(): hues={"ours": (200, 0.11)}, neutral={"page": "#fafafa"}.
    Call it before drawing; names imported with `from kit import X` keep their old values — use K.X."""
    name = name or os.environ.get("KIT_THEME", "light")
    th = _load_theme(name, **overrides)
    if th.get("NAME") != "light" and name != "light":      # a partial custom theme inherits the rest
        base = _load_theme("light")
        base.update(th)
        th = base
    TH.clear()
    TH.update(th)
    T.clear()
    T.update({k: (v[0], v[1]) for k, v in th["TYPE"].items()})
    LS.clear()
    LS.update({k: v[2] for k, v in th["TYPE"].items()})
    N_, F_ = th["NEUTRAL"], th["FAMILY"]
    g = globals()
    g.update(N=N_, F=F_, FAM=F_, NAME=th["NAME"], DARK=th["DARK"], INK=N_["ink"], INK2=N_["ink2"], MUTED=N_["muted"],
             SUBTLE=N_["subtle"], PAGE=N_["page"], LH=th["LH"], FLOW=th["FLOW"], FLOW_DASH=th["FLOW_DASH"],
             STATUS=th["STATUS"], SERIES=th["SERIES"], BAND=th["BAND"],
             **{k: th[k] for k in ("MARGIN", "PAD", "GAP", "ZONE_PAD", "RX_CARD", "RX_ZONE", "SW_CARD", "SW_ZONE",
                                   "SW_ARROW", "SW_FLOW", "SW_STRIP")})
    C.clear()
    hair = th["CARD_STYLE"] == "hairline"
    for k, f in F_.items():
        if hair:
            C[k] = (N_["rule"], N_["surface"], f["title"] if k in th["STRIP_FAMILIES"] or k == "focus" else N_["ink"])
        else:
            C[k] = (f["border"], f["fill"], f["title"])
    C.update({old: C[new] for old, new in LEGACY.items() if new in C})
    return TH


# ====================================================================================================== journal
o = []
REG = {"texts": [], "rects": [], "lines": []}
_DEFS = []
_mute = [0]
_z = [0]
_MARKERS = []
_used = {"glow": False}


def reset():
    """start a new picture in the same process (journal, SVG body, defs)"""
    del o[:]
    for v in REG.values():
        del v[:]
    del _DEFS[:]
    del _MARKERS[:]
    _z[0] = 0
    _used["glow"] = False


def add(s):
    """raw SVG element (not journaled: the linter does not see it)"""
    o.append(s)


def defs(s):
    """raw element for <defs> (clipPath, gradient, pattern)"""
    _DEFS.append(s)


def _j(kind, **item):
    if _mute[0]:
        return None
    _z[0] += 1
    item["z"] = _z[0]
    item["id"] = f"{kind[0]}{len(REG[kind])}"
    REG[kind].append(item)
    return item


def measure(fn, *a, **kw):
    """run a drawing function without drawing: returns what it returns (e.g. the final y)"""
    n = len(o)
    _mute[0] += 1
    try:
        y = fn(*a, **kw)
    finally:
        _mute[0] -= 1
    del o[n:]
    return y


def _dash(dashed):
    if not dashed:
        return ""
    return f' stroke-dasharray="{TH["DASH"] if dashed is True else dashed}"'


# ====================================================================================================== text
def _ink(x, y, s, size, w, anchor, ls, mono):
    f = _font(size, w, mono)
    l, t, r, b = f.getbbox(s, anchor="ls")
    extra = ls * max(len(s) - 1, 0)
    adv = f.getlength(s) + extra
    x0 = x - adv / 2 if anchor == "middle" else (x - adv if anchor == "end" else x)
    return (x0 + l, y + t, max(r - l + extra, 0.1), max(b - t, 0.1))


def text(x, y, s, size=None, bold=None, color=None, anchor="start", italic=False, family=None, role=None,
         _role="text", ls=None, upper=False, mono=False, opacity=None):
    """One line at baseline y. role='title'|'subtitle'|'section'|'panel'|'card'|'body'|'small'|'mono'|'pill'|
    'kpi'|'eyebrow' sets size, weight and tracking from the theme (explicit size/bold/ls win).
    bold: True (theme bold) | False (theme regular) | 300..700. mono: IBM Plex Mono (one weight)."""
    if role:
        rs, rw = T[role]
        size = size if size is not None else rs
        bold = bold if bold is not None else rw
        ls = ls if ls is not None else LS[role]
        mono = mono or role == "mono"
    size = size if size is not None else T["small"][0]
    if upper:
        s = s.upper()
    ls = _track(size) if ls is None else ls
    w = 400 if mono else _wt(bold)
    fam, w_svg = _svg_font(w, mono)
    if family:
        fam = family
    it = ' font-style="italic"' if italic else ""
    fa = f' font-family="{fam}"' if fam else ""
    la = f' letter-spacing="{ls:g}"' if ls else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    color = color or INK
    add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:g}" font-weight="{w_svg}" fill="{color}" '
        f'text-anchor="{anchor}"{it}{fa}{la}{op}>{escape(s)}</text>')
    j = _j("texts", s=s, bb=_ink(x, y, s, size, w, anchor, ls, mono), size=size, fill=color, role=_role)
    miss = _missing(s, w, mono)
    if j and miss:
        j["missing"] = miss
    return j


def para(x, y, w, s, size=None, color=None, bold=None, lh=None, mono=False, ls=None):
    """wrapped paragraph from baseline y; returns the baseline after the last line"""
    size = size or T["body"][0]
    step = size * (lh or LH)
    lines, j = wrap(s, w, size, bold, mono, ls), None
    for line_ in lines:
        j = text(x, y, line_, size, bold, color, mono=mono, ls=ls)
        y += step
    _orphan(lines, j)
    return y


def para_h(w, s, size=None, bold=None, lh=None, mono=False):
    size = size or T["body"][0]
    return len(wrap(s, w, size, bold, mono)) * size * (lh or LH)


def eyebrow(x, y, s, color=None, anchor="start"):
    """small tracked capitals: section labels, column heads"""
    return text(x, y, s, color=color or MUTED, anchor=anchor, role="eyebrow", upper=True)


# ====================================================================================================== shapes
def rect(x, y, w, h, fill=None, stroke=None, sw=1.0, rx=0, dash=None, role="bg", name=None, journal=True,
         opacity=None, extra=""):
    """plain rect. role: 'box' (a card for the linter), 'bg' (opaque backdrop), 'tag'. fill None -> none"""
    st = f' stroke="{stroke}" stroke-width="{sw:g}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:g}" fill="{fill or "none"}"'
        f'{st}{_dash(dash)}{op}{extra}/>')
    j = _j("rects", bb=(x, y, w, h), fill=fill or "none", role=role, name=name) if journal else None
    return dict(x=x, y=y, w=w, h=h, _j=j)


def strip(r, color, sw=None):
    """emphasis strip on the left edge of a card (hairline style)"""
    sw = sw or SW_STRIP
    x, y, h, rx = r["x"], r["y"], r["h"], min(RX_CARD, r["h"] / 2)
    if rx <= sw:
        add(f'<path d="M{x:.1f},{y + rx:.1f} A{rx:g},{rx:g} 0 0 1 {x + rx:.1f},{y:.1f} H{x + sw:.1f} V{y + h:.1f} '
            f'H{x + rx:.1f} A{rx:g},{rx:g} 0 0 1 {x:.1f},{y + h - rx:.1f} Z" fill="{color}"/>')
    else:
        add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{sw:g}" height="{h:.1f}" fill="{color}"/>')


def line(x1, y1, x2, y2, color=None, width=1, dashed=False, journal=True, opacity=None, cap=None):
    """straight line; journal=False for decoration that never meets text (grid behind bars, separators)"""
    color = color or N["grid"]
    op = f' opacity="{opacity}"' if opacity is not None else ""
    lc = f' stroke-linecap="{cap}"' if cap else ""
    add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width:g}"'
        f'{_dash(dashed)}{op}{lc}/>')
    if journal:
        _j("lines", polys=[[(x1, y1), (x2, y2)]], arrow=False, stroke=color)


def polyline(pts, color, width=2, dashed=False, journal=True):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}"{_dash(dashed)} stroke-linejoin="round" '
        f'stroke-linecap="round"/>')
    if journal:
        _j("lines", polys=[list(pts)], arrow=False, stroke=color)


def arrow(d, color=None, dashed=False, width=None, head=True, journal=True):
    """path d with an arrow head; dashed: True (theme dash) or a dash string"""
    color = color or N["arrow"]
    width = width or SW_ARROW
    me = f' marker-end="url(#m{color.lstrip("#")})"' if head else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}"{_dash(dashed)}{me} '
        f'stroke-linejoin="round"/>')
    if journal:
        _j("lines", polys=layoutlint.path_points(d), arrow=head, stroke=color)
    if head and color not in _MARKERS:
        _MARKERS.append(color)


def flow(name):
    """(colour, dash or None) of a theme flow: 'f1'..'f5' or a FLOW_DASH name ('depends', 'planned', ...)"""
    if name in FLOW:
        return FLOW[name], None
    c, d = FLOW_DASH[name]
    return c, d


def swatch(x, y, color, dashed=False, w=32, width=3):
    """legend sample of a line style (y = the line's y)"""
    add(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + w:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="{width:g}"'
        f'{_dash(dashed)}/>')


# ====================================================================================================== colour helpers
def _readable(color, bg, prefer_title=True):
    """a text colour of the same hue as `color` with >= 4.5:1 on bg (arrow tags, labels)"""
    if prefer_title:
        for f in F.values():
            if color in (f["solid"], f["border"], f["soft"]) and PAL.contrast(f["title"], bg) >= 4.5:
                return f["title"]
    if PAL.contrast(color, bg) >= 4.5:
        return color
    L, ch, h = PAL.hex2oklch(color)
    if ch < 0.03:
        return INK2
    step = 0.02 if DARK else -0.02
    for _ in range(40):
        L = min(0.98, max(0.05, L + step))
        c = PAL.oklch(L, ch, h)
        if PAL.contrast(c, bg) >= 4.5:
            TH["EXTRA"] = tuple(TH.get("EXTRA", ())) + (c,)     # derived from a token: not off-palette
            return c
    return INK


def _family_of(color):
    for k, f in F.items():
        if color in (f["solid"], f["border"]):
            return k
    return None


def _round(rx, h):
    return h / 2 if rx == "round" else rx


# ====================================================================================================== tags
def label(x, y, s, color, size=None):
    """tag on a line, centred on (x, y): page-coloured box with a border in the line colour"""
    size = size or T["label"][0]
    L_ = TH["LABEL"]
    ls = LS.get("label", 0)
    w = tw(s, size, T["label"][1], ls) + L_["pad"]
    h = size * 1.6
    bg = N[L_["fill"]] if L_["fill"] in N else L_["fill"]
    rx = _round(TH["RX_TAG"], h)
    add(f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:g}" fill="{bg}" '
        f'stroke="{color}" stroke-width="{L_["sw"]:g}"/>')
    r = _j("rects", bb=(x - w / 2, y - h / 2, w, h), fill=bg, role="tag")
    fg = _readable(color, bg, prefer_title=not DARK and TH["NAME"] != "graphite")
    t = text(x, y + size * 0.36, s, size, T["label"][1], fg, "middle", _role="tag", ls=ls)
    if r:
        r["own"] = t["id"]
    return w


def pill(x, y, s, color, fg=None, size=None):
    """solid pill, y = baseline; color: hex or family name (its solid). Returns the width."""
    if color in F:
        color = F[color]["solid"]
    size = size or T["pill"][0]
    ls = LS.get("pill", 0)
    wt = T["pill"][1]
    if fg is None:
        fam = _family_of(color)
        if fam and PAL.contrast(F[fam]["glyph"], color) >= 4.5:
            fg = F[fam]["glyph"]
        else:
            dark = TH.get("DARK_GLYPH", INK)
            fg = "#ffffff" if PAL.contrast("#ffffff", color) >= PAL.contrast(dark, color) else dark
    w = tw(s, size, wt, ls) + 16 + 2 * bool(ls)
    h = size * 1.6
    top = y - size * 0.36 - h / 2
    add(f'<rect x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{_round(TH["RX_PILL"], h):g}" '
        f'fill="{color}"/>')
    r = _j("rects", bb=(x, top, w, h), fill=color, role="tag")
    t = text(x + w / 2, y, s, size, wt, fg, "middle", _role="tag", ls=ls)
    if r:
        r["own"] = t["id"]
    return w


def tag(x, y, s, fam="neutral", mono=False, size=None):
    """outlined tag, y = baseline: family border + family title text; fill = family fill (light, night) or the
    page (graphite). neutral/white: subtle border, ink2 text. Returns the width."""
    size = size or T["pill"][0]
    f = F[fam]
    neutral = fam in ("neutral", "white")
    fill = N["page"] if TH["TAG_FILL"] == "page" else f["fill"]
    border = N["subtle"] if neutral else f["border"]
    fg = INK2 if neutral else f["title"]
    wt = 400 if mono else T["pill"][1]
    ls = 0 if mono else LS.get("pill", 0)
    w = tw(s, size, wt, ls, mono) + 18
    h = size * 1.7
    top = y - size * 0.36 - h / 2
    add(f'<rect x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{_round(TH["RX_PILL"], h):g}" '
        f'fill="{fill}" stroke="{border}" stroke-width="1"/>')
    r = _j("rects", bb=(x, top, w, h), fill=fill, role="tag")
    t = text(x + w / 2, y, s, size, wt, fg, "middle", _role="tag", ls=ls, mono=mono)
    if r:
        r["own"] = t["id"]
    return w


# ====================================================================================================== marks
ALIAS = {"ok": "done", "no": "blocked", "warn": "attention", "wait": "waiting", "prog": "in_progress",
         "block": "blocked"}


def _glyph(cx, cy, g, gc, r):
    sw = max(1.5, 0.25 * r)
    if g == "✓":
        add(f'<path d="M{cx - 0.46 * r:.2f},{cy + 0.02 * r:.2f} L{cx - 0.12 * r:.2f},{cy + 0.36 * r:.2f} '
            f'L{cx + 0.48 * r:.2f},{cy - 0.34 * r:.2f}" fill="none" stroke="{gc}" stroke-width="{sw:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')
    elif g == "✕":
        q = 0.34 * r
        add(f'<path d="M{cx - q:.2f},{cy - q:.2f} L{cx + q:.2f},{cy + q:.2f} M{cx + q:.2f},{cy - q:.2f} '
            f'L{cx - q:.2f},{cy + q:.2f}" stroke="{gc}" stroke-width="{sw:.2f}" stroke-linecap="round"/>')
    elif g == "!":
        add(f'<path d="M{cx:.2f},{cy - 0.5 * r:.2f} L{cx:.2f},{cy + 0.1 * r:.2f}" stroke="{gc}" '
            f'stroke-width="{sw:.2f}" stroke-linecap="round"/>')
        add(f'<circle cx="{cx:.2f}" cy="{cy + 0.45 * r:.2f}" r="{sw * 0.6:.2f}" fill="{gc}"/>')
    elif g == "…":
        for dx in (-0.4 * r, 0, 0.4 * r):
            add(f'<circle cx="{cx + dx:.2f}" cy="{cy:.2f}" r="{max(1.0, 0.12 * r):.2f}" fill="{gc}"/>')
    elif g == "•":
        add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{0.28 * r:.2f}" fill="{gc}"/>')


def badge(cx, cy, s, r=11, fill=None, fg=None, ring=None, size=None):
    """numbered / lettered circle (step numbers). ring=colour draws a hollow one."""
    if ring:
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r - 0.6:.1f}" fill="{PAGE}" stroke="{ring}" stroke-width="1.2"/>')
        fg = fg or ring
    else:
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:g}" fill="{fill or N["head"]}"/>')
        fg = fg or TH["HEAD_FG"]
    size = size or round(min(13, max(9, r * 1.08)), 1)
    text(cx, cy + size * 0.36, str(s), size, True, fg, "middle", _role="glyph", ls=0)


def mark(cx, cy, kind, r=8.5, glow=None):
    """status mark — colour + shape + vector glyph. kind: done | in_progress | waiting | attention | planned |
    blocked (aliases ok/no/warn/wait/prog), 'dot' = neutral bullet, anything else = numbered badge."""
    k = ALIAS.get(kind, kind)
    if k == "dot":
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(2.4, r * 0.34):.1f}" fill="{INK2}"/>')
        return
    if k not in STATUS:
        badge(cx, cy, kind, r)
        return
    fill, stroke, g, gc = STATUS[k]
    shape = TH["STATUS_SHAPE"][k]
    if (TH["GLOW"] if glow is None else glow) and TH["GLOW"] and shape in ("filled", "diamond", "half"):
        _used["glow"] = True
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 6.5:.1f}" fill="{stroke if shape == "half" else fill}" '
            f'opacity="{TH["GLOW"]}" filter="url(#glow)"/>')
    sw = 1.6 if r >= 8 else 1.4
    if shape == "half":
        rr = r - sw / 2
        add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        add(f'<path d="M{cx:.1f},{cy - rr:.1f} A{rr:.1f},{rr:.1f} 0 0 0 {cx:.1f},{cy + rr:.1f} Z" fill="{stroke}"/>')
        return
    if shape == "diamond":
        q = r * 1.1
        add(f'<path d="M{cx:.2f},{cy - q:.2f} L{cx + q:.2f},{cy:.2f} L{cx:.2f},{cy + q:.2f} L{cx - q:.2f},{cy:.2f} Z" '
            f'fill="{fill}" stroke="{stroke or fill}" stroke-width="{1.3 if stroke else r * 0.3:.2f}" '
            f'stroke-linejoin="round"/>')
        _glyph(cx, cy, g, gc, r * 0.95)
        return
    st = f' stroke="{stroke}" stroke-width="{sw if shape != "ring-hollow" else 1.3}"' if stroke else ""
    if shape == "ring-dashed":
        st += ' stroke-dasharray="2.2 2"'
    rr = r - (sw / 2 if stroke else 0)
    add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr:.1f}" fill="{fill}"{st}/>')
    _glyph(cx, cy, g, gc, r)


def bullets(x, y, w, items, size=None, gap=6, lh=None, color=None):
    """items: (mark, text[, bold]) — mark is a status kind, 'dot', or a digit/letter badge"""
    size = size or T["body"][0]
    step = size * (lh or LH)
    r = size * 0.6
    for it in items:
        kind, s = it[0], it[1]
        bold = True if (len(it) > 2 and it[2]) else None
        mark(x + r, y - size * 0.34, kind, r, glow=False)
        lines, j = wrap(s, w - 2 * r - 10, size, bold), None
        for ln in lines:
            j = text(x + 2 * r + 10, y, ln, size, bold, color or INK)
            y += step
        _orphan(lines, j)
        y += gap
    return y


# ====================================================================================================== cards
def _c3(color):
    if isinstance(color, tuple):
        return color
    return C[color]


def box(x, y, w, h, color, dashed=False, width=None, rx=None, name=None, fill=None, strip_color=None):
    """card frame in the theme's style. pastel: family fill + border; hairline: surface + rule border and a
    strip on the left for STRIP_FAMILIES (strip_color=False to drop it, a colour to force one)"""
    b, f, _ = _c3(color)
    f = fill or f
    if dashed and TH["CARD_STYLE"] == "hairline":
        b = N["subtle"]
    rx = RX_CARD if rx is None else rx
    r = rect(x, y, w, h, f, b, width or SW_CARD, rx, dashed, role="box", name=name)
    fam = LEGACY.get(color, color) if isinstance(color, str) else None
    if strip_color is None and TH["CARD_STYLE"] == "hairline" and fam in TH["STRIP_FAMILIES"]:
        strip_color = F[fam]["solid"]
    if strip_color:
        strip(r, strip_color)
    return r


def _line_color(c):
    """card line colour: '#hex', 'mono', a neutral name (ink ink2 muted subtle) or a family name (its title)"""
    if not isinstance(c, str) or c.startswith("#") or c == "mono":
        return c
    if c in ("ink", "ink2", "muted", "subtle"):
        return N[c]
    if c in F:
        return F[c]["title"]
    raise ValueError(f"card line colour {c!r}: use '#hex', 'mono', ink/ink2/muted/subtle or a family name")


def _card_body(x, y, w, title, lines, size, tsize, tcolor, pills=()):
    pad = PAD
    ty = y + pad + tsize * 0.78
    for t in wrap(title, w - 2 * pad, tsize, True):
        text(x + pad, ty, t, tsize, True, tcolor)
        ty += tsize * LH
    if pills:
        px = x + pad
        ty += 2
        for s, col in pills:
            px += pill(px, ty + 2, s, col) + 8
        ty += T["pill"][0] * 1.6 + 2
    ty += 2
    for ln in lines:
        col, mono = INK, False
        if isinstance(ln, tuple):
            ln, col = ln[0], _line_color(ln[1])
            if col == "mono":
                col, mono = MUTED, True
        if isinstance(ln, list):
            ty = bullets(x + pad, ty, w - 2 * pad, ln, size, gap=4) - 4
            continue
        wl, j = wrap(ln, w - 2 * pad, size, mono=mono), None
        for t in wl:
            j = text(x + pad, ty, t, size, color=col, mono=mono)
            ty += size * LH
        _orphan(wl, j)
    return ty - size * LH + size * 0.25 + pad - y      # content height incl. padding


def card_h(w, title, lines, size=None, tsize=None, pills=()):
    """height a card needs for its content"""
    return measure(_card_body, 0, 0, w, title, lines, size or T["body"][0], tsize or T["card"][0], INK, pills)


def card(x, y, w, h, color, title, lines, size=None, dashed=False, tsize=None, name=None, pills=(),
         strip_color=None):
    """card: title + optional pills + lines. A line is a str, (str, colour), (str, 'mono') or a list of bullets
    [(mark, text), ...]. h=None -> exactly as tall as the content. Returns {x, y, w, h}."""
    size = size or T["body"][0]
    tsize = tsize or T["card"][0]
    if h is None:
        h = card_h(w, title, lines, size, tsize, pills)
    r = box(x, y, w, h, color, dashed=dashed, name=name or title, strip_color=strip_color)
    _card_body(x, y, w, title, lines, size, tsize, _c3(color)[2], pills)
    return r


def row_x(x, w, n, gap=None, weights=None):
    """[(x, width)] of n columns with equal gaps (weights: relative widths)"""
    gap = GAP if gap is None else gap
    weights = weights or [1] * n
    free = w - gap * (n - 1)
    out, cx = [], x
    for k in weights:
        cw = free * k / sum(weights)
        out.append((cx, cw))
        cx += cw + gap
    return out


def cards_row(x, y, w, specs, gap=None, weights=None, h=None, arrows=None):
    """a row of equal-height cards; specs: dict(color, title, lines[, pills, dashed]); arrows=colour links them"""
    cols = row_x(x, w, len(specs), gap, weights)
    hh = h or max(card_h(cw, s["title"], s["lines"], pills=s.get("pills", ())) for (cx, cw), s in zip(cols, specs))
    rs = [card(cx, y, cw, hh, s["color"], s["title"], s["lines"], dashed=s.get("dashed", False),
               pills=s.get("pills", ())) for (cx, cw), s in zip(cols, specs)]
    if arrows:
        for a, b in zip(rs, rs[1:]):
            connect(a, b, color=arrows)
    return rs


def bullets_row(x, y, w, blocks, gap=None, size=None):
    """footer blocks [(family, title, items)], equal heights = tallest content"""
    size = size or T["body"][0]
    cols = row_x(x, w, len(blocks), gap)
    tsz = T["card"][0] + 1
    zp = ZONE_PAD
    head = zp + tsz * 0.8 + tsz * 1.0 + size        # title baseline + one title-height gap + first cap
    body = max(measure(bullets, 0, 0, cw - 2 * zp, it, size) for (cx, cw), (_, _, it) in zip(cols, blocks))
    hh = head + body - 6 - size * LH + size * 0.3 + zp
    rs = []
    for (cx, cw), (col, t, it) in zip(cols, blocks):
        rs.append(box(cx, y, cw, hh, col, width=SW_CARD + (0.2 if TH["CARD_STYLE"] == "pastel" else 0),
                      rx=RX_ZONE if TH["CARD_STYLE"] == "pastel" else RX_CARD, name=t))
        text(cx + zp, y + zp + tsz * 0.8, t, tsz, True, _c3(col)[2])
        bullets(cx + zp, y + head, cw - 2 * zp, it, size)
    return rs


def zone(x, y, w, h, color=None, title=None, dashed=False, width=None, title_size=None, title_color=None):
    """container frame inserted *behind* everything drawn so far — size a zone after its content"""
    Z = TH["ZONE"]
    color = color or Z["family"]
    fam = F.get(LEGACY.get(color, color))
    if fam:
        b, f, tc = (N[Z["stroke"]] if Z.get("stroke") else fam["border"]), fam["fill"], fam["title"]
    else:
        b, f, tc = _c3(color)
    n = len(o)
    r = rect(x, y, w, h, f, b, width or SW_ZONE, RX_ZONE, dashed, role="box", name=title)
    o.insert(0, o.pop(n))
    if r["_j"]:
        r["_j"]["z"] = 0.5          # painted first
    if title:
        role = Z["title_role"]
        size = title_size or T[role][0]
        text(x + ZONE_PAD, y + ZONE_PAD + size * 0.8, title, size, T[role][1], title_color or tc, ls=LS[role],
             upper=Z.get("upper", False))
    return r


def zone_top(y):
    """baseline-free y where the first card inside a zone that starts at y should go (below the zone title)"""
    return y + ZONE_PAD + T[TH["ZONE"]["title_role"]][0] + 26


# ====================================================================================================== connectors
def connect(a, b, sa=None, sb=None, color=None, dashed=False, width=None, at=None, via=None, inset=2,
            lab=None, lab_at=0.5, flow_name=None, head=True):
    """Orthogonal arrow a -> b (dicts with x, y, w, h). Facing sides by default; straight when the boxes overlap
    on the cross axis (at = that coordinate), else one Z-bend at `via`. lab = tag on the longest segment.
    flow_name='f1'..'f5' or a FLOW_DASH name sets colour and dash from the theme."""
    if flow_name:
        color, d_ = flow(flow_name)
        dashed = dashed or d_ or False
    color = color or N["arrow"]
    ax2, bx2, ay2, by2 = a["x"] + a["w"], b["x"] + b["w"], a["y"] + a["h"], b["y"] + b["h"]
    if sa is None:
        if b["x"] >= ax2:
            sa, sb = "r", "l"
        elif bx2 <= a["x"]:
            sa, sb = "l", "r"
        elif b["y"] >= ay2:
            sa, sb = "b", "t"
        else:
            sa, sb = "t", "b"
    if sa in "rl" and sb in "rl":
        lo, hi = max(a["y"], b["y"]) + 10, min(ay2, by2) - 10
        x1 = ax2 + inset if sa == "r" else a["x"] - inset
        x2 = b["x"] - inset if sb == "l" else bx2 + inset
        if (lo <= hi and (at is None or lo <= at <= hi)):
            yy = at if at is not None else (lo + hi) / 2
            d = f"M{x1:.1f},{yy:.1f} H{x2:.1f}"
        else:
            y1 = at if at is not None else a["y"] + a["h"] / 2
            y2 = b["y"] + b["h"] / 2
            xv = via if via is not None else (x1 + x2) / 2
            d = f"M{x1:.1f},{y1:.1f} H{xv:.1f} V{y2:.1f} H{x2:.1f}"
    elif sa in "tb" and sb in "tb":
        lo, hi = max(a["x"], b["x"]) + 10, min(ax2, bx2) - 10
        y1 = ay2 + inset if sa == "b" else a["y"] - inset
        y2 = b["y"] - inset if sb == "t" else by2 + inset
        if (lo <= hi and (at is None or lo <= at <= hi)):
            xx = at if at is not None else (lo + hi) / 2
            d = f"M{xx:.1f},{y1:.1f} V{y2:.1f}"
        else:
            x1 = at if at is not None else a["x"] + a["w"] / 2
            x2 = b["x"] + b["w"] / 2
            yv = via if via is not None else (y1 + y2) / 2
            d = f"M{x1:.1f},{y1:.1f} V{yv:.1f} H{x2:.1f} V{y2:.1f}"
    else:   # one L-bend
        if sa in "tb":
            x1 = at if at is not None else a["x"] + a["w"] / 2
            y1 = ay2 + inset if sa == "b" else a["y"] - inset
            y2 = via if via is not None else b["y"] + b["h"] / 2
            x2 = b["x"] - inset if sb == "l" else bx2 + inset
            d = f"M{x1:.1f},{y1:.1f} V{y2:.1f} H{x2:.1f}"
        else:
            y1 = at if at is not None else a["y"] + a["h"] / 2
            x1 = ax2 + inset if sa == "r" else a["x"] - inset
            x2 = via if via is not None else b["x"] + b["w"] / 2
            y2 = b["y"] - inset if sb == "t" else by2 + inset
            d = f"M{x1:.1f},{y1:.1f} H{x2:.1f} V{y2:.1f}"
    arrow(d, color, dashed, width, head)
    if lab:
        p = layoutlint.path_points(d)[0]
        s0, s1 = max(zip(p, p[1:]), key=lambda q: abs(q[0][0] - q[1][0]) + abs(q[0][1] - q[1][1]))
        seg = abs(s0[0] - s1[0]) + abs(s0[1] - s1[1])
        need = (tw(lab, T["label"][0], T["label"][1], LS.get("label", 0)) + TH["LABEL"]["pad"] + 12
                if s0[1] == s1[1] else T["label"][0] * 1.6 + 12)
        if seg < need:
            print(f"connect: tag «{lab}» needs ~{need:.0f} px, longest segment is {seg:.0f} px — "
                  "widen the gap, move the tag to a longer arrow or explain the line in the legend",
                  file=sys.stderr)
        label(s0[0] + (s1[0] - s0[0]) * lab_at, s0[1] + (s1[1] - s0[1]) * lab_at, lab, color)
    return d


# ====================================================================================================== components
def kpi(x, y, w, value, caption, fam="ours", h=None, size=None):
    """KPI tile: big number + caption, framed per theme (light: family card; graphite/night: neutral tile)"""
    K_ = TH["KPI"]
    f = F[fam]
    vs, vw = (size or T["kpi"][0]), T["kpi"][1]
    while tw(value, vs, vw) > w - 30 and vs > T["section"][0]:      # value must fit the tile: shrink, don't spill
        vs -= 2
    cs = T["small"][0]
    if K_["layout"] == "caption-top":
        cap_lines = wrap(caption, w - 28, cs, True)
        cap = y + 14 + cs * 0.77
        val = cap + (len(cap_lines) - 1) * cs * 1.3 + 10 + vs * 0.72
        h = h or (val + 14 - y)
        r = box(x, y, w, h, fam, name=caption)
        for i, ln in enumerate(cap_lines):
            text(x + 14, cap + i * cs * 1.3, ln, cs, True, f["title"])
        text(x + 14, val, value, vs, vw, f["title"])
        return r
    top = 26 if K_["accent_bar"] else 19
    val = y + top + vs * 0.72
    cap_lines = wrap(caption, w - 32, cs)
    h = h or (val + 23 + (len(cap_lines) - 1) * cs * 1.3 + 14 + 2 * bool(K_["accent_bar"]) - y)
    r = rect(x, y, w, h, N["tile"], N["rule"], SW_CARD, RX_CARD, role="box", name=caption)
    if K_["accent_bar"]:
        add(f'<rect x="{x + 16:.1f}" y="{y + 12:.1f}" width="22" height="3" rx="1.5" fill="{f["solid"]}"/>')
    text(x + 16, val, value, vs, vw, f["title"])
    para(x + 16, val + 23, w - 32, caption, cs, MUTED, lh=1.3)
    return r


def kpi_row(x, y, w, items, gap=None, fam="ours", weights=None):
    """row of KPI tiles of equal height. items: (value, caption[, family]). Returns the rects."""
    cols = row_x(x, w, len(items), gap, weights)
    fams = [it[2] if len(it) > 2 else fam for it in items]
    h = max(measure(kpi, cx, y, cw, it[0], it[1], f)["h"] for (cx, cw), it, f in zip(cols, items, fams))
    tiles = [kpi(cx, y, cw, it[0], it[1], f, h=h) for (cx, cw), it, f in zip(cols, items, fams)]
    for t in tiles:
        if t.get("_j"):
            t["_j"]["equal_row"] = True         # empty bottom is by design: layoutlint skips EMPTY
    return tiles


def legend(x, y, items, gap=30, size=None, color=None):
    """one-line legend at baseline y; returns the x after the last item. items:
       ("flow", "f1" | dash-name, text)   line sample        ("arrow", "f1", text)   line with a head
       ("status", kind, text)             status mark        ("family", fam, text)   card colour chip
       ("line", (colour, dash|None), text)"""
    size = size or T["small"][0]
    color = color or MUTED
    cy = y - size * 0.35
    for kind, key, s in items:
        if kind in ("flow", "arrow", "line"):
            col, dash = key if kind == "line" else flow(key)
            if kind == "arrow":
                arrow(f"M{x:.1f},{cy:.1f} H{x + 34:.1f}", col, dash or False, journal=False)
            else:
                swatch(x, cy, col, dash or False)
            x += 42
        elif kind == "status":
            mark(x + 7.5, cy, key, 7.5, glow=False)
            x += 22
        elif kind == "family":
            c3 = _c3(key)
            if TH["CARD_STYLE"] == "hairline":
                add(f'<rect x="{x:.1f}" y="{cy - 7:.1f}" width="14" height="14" rx="2" fill="{N["surface"]}" '
                    f'stroke="{N["rule"]}"/>')
                if key in TH["STRIP_FAMILIES"]:
                    add(f'<rect x="{x:.1f}" y="{cy - 7:.1f}" width="3" height="14" fill="{F[key]["solid"]}"/>')
            else:
                add(f'<rect x="{x:.1f}" y="{cy - 7:.1f}" width="14" height="14" rx="3" fill="{c3[1]}" '
                    f'stroke="{c3[0]}" stroke-width="1.4"/>')
            x += 22
        text(x, y, s, size, None, color)
        x += tw(s, size) + gap
    return x - gap


def table(x, y, w, cols, rows, row_h=30, size=None, head=True, zebra=False):
    """simple table from header baseline y. cols: [(title, weight[, 'end' | 'mono'])]; a cell is a str,
    (str, colour), or ('mark', kind, str). Returns the y below the last row."""
    size = size or T["body"][0]
    xs = row_x(x, w, len(cols), 16, [c[1] for c in cols])
    if head:
        for (cx, cw), c in zip(xs, cols):
            eyebrow(cx + cw if "end" in c[2:] else cx, y, c[0], anchor="end" if "end" in c[2:] else "start")
        line(x, y + 10, x + w, y + 10, N["subtle"], 1, journal=False)
        y += 10
    for i, row in enumerate(rows):
        if zebra and i % 2 == 0:
            rect(x, y, w, row_h, N["band"], role="bg")
        base = y + row_h / 2 + size * 0.36
        for (cx, cw), c, cell in zip(xs, cols, row):
            end = "end" in c[2:]
            mono = "mono" in c[2:]
            if isinstance(cell, tuple) and cell[0] == "mark":
                mark(cx + 8, base - size * 0.34, cell[1], 7.5, glow=False)
                text(cx + 24, base, cell[2], size)
                continue
            s, col = (cell if isinstance(cell, tuple) else (cell, None))
            text(cx + cw if end else cx, base, s, size if not mono else T["mono"][0], color=col,
                 anchor="end" if end else "start", mono=mono)
        y += row_h
        if not zebra and i < len(rows) - 1:
            line(x, y, x + w, y, N["hairline"], 1, journal=False)
    return y


def scale(v0, v1, x0, x1):
    """linear map v -> x (numbers or datetime.date: dates map by ordinal)"""
    def num(v):
        return v.toordinal() if hasattr(v, "toordinal") else v
    a, b = num(v0), num(v1)
    return lambda v: x0 + (num(v) - a) * (x1 - x0) / (b - a)


def bar(x0, x1, cy, kind="planned", h=8, now=None, color=None):
    """gantt bar centred on cy. kind = status (done / in_progress / waiting / attention / blocked / planned) styles it;
    color= a plain filled bar instead. in_progress fills up to x=now."""
    top = cy - h / 2
    rx = h / 2
    if color:
        add(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{x1 - x0:.1f}" height="{h:g}" rx="{rx:g}" fill="{color}"/>')
        return
    k = ALIAS.get(kind, kind)
    fam = {"done": "ok", "in_progress": "ours", "waiting": "external", "attention": "attention",
           "blocked": "danger"}.get(k)
    if fam is None:          # planned: outline only
        add(f'<rect x="{x0 + 0.6:.1f}" y="{top + 0.6:.1f}" width="{max(0.1, x1 - x0 - 1.2):.1f}" height="{h - 1.2:g}" '
            f'rx="{rx - 0.6:g}" fill="none" stroke="{SUBTLE}" stroke-width="1.2"/>')
        return
    f = F[fam]
    st = f' stroke="{f["border"]}" stroke-width="1"' if k == "waiting" else ""
    add(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{x1 - x0:.1f}" height="{h:g}" rx="{rx:g}" fill="{f["tint"]}"{st}/>')
    if k == "in_progress" and now is not None and now > x0:
        add(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{min(now, x1) - x0:.1f}" height="{h:g}" rx="{rx:g}" '
            f'fill="{f["solid"]}"/>')


def hbars(x, y, w, items, label_w=180, row_h=28, vmax=None, color=None, fmt="{:g}", size=None):
    """horizontal bar chart from top y. items: (label, value[, colour or SERIES key]). Returns the y below."""
    size = size or T["body"][0]
    vmax = vmax or max(it[1] for it in items) or 1
    vw = max(tw(fmt.format(it[1]), size) for it in items) + 10
    bx, bw = x + label_w, w - label_w - vw
    line(bx, y, bx, y + row_h * len(items), N["subtle"], 1, journal=False)
    for i, it in enumerate(items):
        cy = y + i * row_h + row_h / 2
        col = it[2] if len(it) > 2 else (color or SERIES["after"])
        col = SERIES.get(col, col)
        text(bx - 10, cy + size * 0.36, it[0], size, anchor="end")
        L = bw * it[1] / vmax
        add(f'<rect x="{bx:.1f}" y="{cy - row_h * 0.3:.1f}" width="{max(L, 0.5):.1f}" height="{row_h * 0.6:.1f}" '
            f'fill="{col}"/>')
        text(bx + L + 8, cy + size * 0.36, fmt.format(it[1]), size, None, INK2)
    return y + row_h * len(items)


def line_chart(x, y, w, h, series, xlabels=(), ymax=None, ymin=0, yticks=4, fmt="{:g}", size=None, right=110):
    """line chart in the box (x, y, w, h): grid, y ticks, x labels, one line per series with an end label.
    series: [(name, [values], colour or SERIES key)]. Returns the y below the x labels."""
    size = size or T["small"][0]
    allv = [v for _, vs, _ in series for v in vs]
    ymax = ymax if ymax is not None else max(allv)
    gx0, gx1 = x + 44, x + w - right
    sy = scale(ymin, ymax, y + h, y)
    for i in range(yticks + 1):
        v = ymin + (ymax - ymin) * i / yticks
        line(gx0, sy(v), gx1, sy(v), N["grid"] if i else N["subtle"], 1, journal=False)
        text(gx0 - 8, sy(v) + size * 0.36, fmt.format(round(v, 6)), size, None, MUTED, "end")
    n = max(len(vs) for _, vs, _ in series)
    sx = scale(0, max(1, n - 1), gx0, gx1)
    for i, s in enumerate(xlabels):
        if s:
            text(sx(i), y + h + size * 1.5, s, size, None, MUTED, "middle")
    ends = []
    for name, vs, col in series:
        col = SERIES.get(col, col)
        pts = [(sx(i), sy(v)) for i, v in enumerate(vs)]
        polyline(pts, col, 2.2, journal=False)
        add(f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3.2" fill="{col}"/>')
        ends.append([pts[-1][1], name, col])
    ends.sort()
    for i in range(1, len(ends)):                    # keep end labels apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + size * 1.3)
    for yy, name, col in ends:
        text(gx1 + 10, yy + size * 0.36, name, size, True, _readable(col, PAGE, False))
    return y + h + size * 1.5 + 6


# ====================================================================================================== output
def svg_text(W, H):
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'font-family="{FAMILY}, sans-serif">', "<defs>"]
    size, path = TH["ARROW_HEAD"]
    for col in _MARKERS:
        m = col.lstrip("#")
        head.append(f'<marker id="m{m}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="{size:g}" '
                    f'markerHeight="{size:g}" orient="auto"><path d="{path}" fill="{col}"/></marker>')
    if TH["GLOW"]:
        head.append('<filter id="glow" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="3.2"/></filter>')
        head.append('<filter id="glowline" x="-2" y="-0.1" width="5" height="1.2"><feGaussianBlur stdDeviation="2.4"/>'
                    '</filter>')
    head += _DEFS
    head += ["</defs>", f'<rect width="{W}" height="{H}" fill="{PAGE}"/>']
    return "\n".join(head + o + ["</svg>"])


def lint(W, H, preview=1000, **kw):
    issues = layoutlint.check(W, H, REG["texts"], REG["rects"], REG["lines"], preview=preview, page=PAGE, **kw)
    miss = [t for t in REG["texts"] if t.get("missing")]
    if miss:
        chars = "".join(sorted({c for t in miss for c in t["missing"]}))
        issues.append(dict(level="WARN", code="GLYPH", bbs=[[float(v) for v in t["bb"]] for t in miss[:10]],
                           msg=f"{FAMILY} has no glyph for «{chars}» in {len(miss)} texts, e.g. «{miss[0]['s'][:30]}»: "
                               f"the renderer substitutes a font (draw it: mark(), arrow()) or rephrase"))
    return issues


_fcfile = []


def font_env():
    """environment for fontconfig-based renderers: a temporary fonts.conf whose <dir>s hold the kit's fonts.
    KIT_FC_ISOLATE=1 leaves the system fonts out (simulates a machine without IBM Plex installed)."""
    if not _fcfile:
        dirs = sorted({os.path.dirname(p) for _, _, p in FONTS["faces"]})
        tmp = tempfile.mkdtemp(prefix="kit-fc-")
        inc = "" if os.environ.get("KIT_FC_ISOLATE") == "1" else \
            '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
        conf = ('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>\n'
                + "".join(f"  <dir>{escape(d)}</dir>\n" for d in dirs) + inc
                + f"  <cachedir>{escape(os.path.join(tmp, 'cache'))}</cachedir>\n</fontconfig>\n")
        p = os.path.join(tmp, "fonts.conf")
        with open(p, "w") as fh:
            fh.write(conf)
        _fcfile.append(p)
    env = dict(os.environ)
    env["FONTCONFIG_FILE"] = _fcfile[0]
    return env


def _chrome_bin():
    for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if shutil.which(b):
            return shutil.which(b)
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def _r_resvg(svg, png, width):
    if shutil.which("resvg"):
        args = ["resvg", "-w", str(width)]
        for d in sorted({os.path.dirname(p) for _, _, p in FONTS["faces"]}):
            args += ["--use-fonts-dir", d]
        subprocess.run(args + [svg, png], check=True, capture_output=True, timeout=120)
        return "resvg"
    import resvg_py
    data = resvg_py.svg_to_bytes(svg_path=svg, width=width,
                                 font_dirs=sorted({os.path.dirname(p) for _, _, p in FONTS["faces"]}))
    with open(png, "wb") as fh:
        fh.write(bytes(data))
    return "resvg (python)"


def _r_rsvg(svg, png, width):
    subprocess.run(["rsvg-convert", "-w", str(width), "-o", png, svg], check=True, capture_output=True, env=font_env(),
                   timeout=120)
    return "rsvg-convert"


def _r_inkscape(svg, png, width):
    subprocess.run(["inkscape", svg, "--export-type=png", f"--export-filename={png}", f"--export-width={width}"],
                   check=True, capture_output=True, env=font_env(), timeout=300)
    return "inkscape"


def _r_cairosvg(svg, png, width):
    code = "import cairosvg,sys; cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2], output_width=int(sys.argv[3]))"
    subprocess.run([sys.executable, "-c", code, svg, png, str(width)], check=True, capture_output=True,
                   env=font_env(), timeout=300)
    return "cairosvg"


def _r_chrome(svg, png, width):
    src = open(svg, encoding="utf-8").read()
    m = re.search(r'<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"', src)
    W, H = float(m.group(1)), float(m.group(2))
    faces = []
    for fam, w, p in FONTS["faces"]:
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        faces.append(f'@font-face{{font-family:"{fam}";font-weight:{w};font-style:normal;'
                     f'src:url(data:font/ttf;base64,{b64}) format("truetype");}}')
    html = ('<!doctype html><html><head><meta charset="utf-8"><style>' + "".join(faces)
            + 'html,body{margin:0;padding:0;overflow:hidden;background:transparent}svg{display:block}</style></head>'
            + '<body>' + src[src.index("<svg"):] + "</body></html>")
    tmp = tempfile.mkdtemp(prefix="kit-chrome-", dir=os.path.dirname(os.path.abspath(png)))
    try:
        page = os.path.join(tmp, "page.html")
        out = os.path.join(tmp, "shot.png")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(html)
        subprocess.run([_chrome_bin(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--no-default-browser-check", f"--user-data-dir={os.path.join(tmp, 'profile')}",
                        f"--force-device-scale-factor={width / W:g}", f"--window-size={int(W)},{int(round(H))}",
                        f"--screenshot={out}", "file://" + page], check=True, capture_output=True,
                       env=font_env(), timeout=120)
        shutil.move(out, png)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "chrome headless"


RENDERERS = {
    "resvg": (_r_resvg, lambda: bool(shutil.which("resvg")) or importlib.util.find_spec("resvg_py") is not None),
    "rsvg": (_r_rsvg, lambda: bool(shutil.which("rsvg-convert"))),
    "inkscape": (_r_inkscape, lambda: bool(shutil.which("inkscape"))),
    "cairosvg": (_r_cairosvg, lambda: importlib.util.find_spec("cairosvg") is not None),
    "chrome": (_r_chrome, lambda: bool(_chrome_bin())),
}


def render(svg, png, width=2400, renderer=None):
    """SVG -> PNG with the first renderer that works (order: resvg, rsvg, inkscape, cairosvg, chrome; env
    KIT_RENDERER or renderer= overrides). Returns the renderer's name, or None if nothing could render."""
    order = (renderer or os.environ.get("KIT_RENDERER") or ",".join(RENDERERS)).split(",")
    for name in order:
        name = name.strip()
        if name not in RENDERERS:
            raise SystemExit(f"unknown renderer {name}: {', '.join(RENDERERS)}")
        fn, ok = RENDERERS[name]
        if not ok():
            continue
        try:
            used = fn(svg, png, width)
            if os.path.exists(png):
                return used
        except Exception as e:  # noqa: BLE001 — try the next one
            err = getattr(e, "stderr", b"") or b""
            print(f"render: {name} failed ({type(e).__name__}: {err[-200:].decode(errors='replace').strip() or e})")
    return None


def crosscheck(svg, tol=0.04, quiet=False):
    """compare journal text widths with inkscape's real boxes: > tol off means the renderer used another font"""
    W, H, texts, *_ = layoutlint.load_svg(svg, env=font_env())
    real = {}
    for t in texts:
        real.setdefault(t["s"], []).append(t["bb"][2])
    off = []
    for t in REG["texts"]:
        if t["role"] in ("glyph", "tag") or t["s"] not in real or len(t["s"]) < 12:
            continue
        r = min(real[t["s"]], key=lambda v: abs(v - t["bb"][2]))
        # PIL boxes include side bearings, inkscape's do not: allow ~0.2 em on top of tol
        if abs(r - t["bb"][2]) > max(2.5, tol * t["bb"][2]) + 0.2 * t["size"]:
            off.append((t["s"], t["bb"][2], r))
    if not quiet:
        if off:
            print(f"crosscheck: {len(off)} texts differ > {tol:.0%} from inkscape, e.g. «{off[0][0][:30]}» "
                  f"{off[0][1]:.0f} vs {off[0][2]:.0f}px — the renderer is not using {FAMILY}")
        else:
            print(f"crosscheck: journal matches inkscape's text boxes ({FAMILY})")
    return off


def write(path, W, H, png_width=2400, preview=1000, preview_path=None, check=True, annotate=True, strict=True,
          renderer=None, show_warn=12):
    """SVG -> PNG (png_width) -> preview (preview px, PIL) -> layoutlint on the journal -> palette_check on the SVG
    -> <name>-lint.png (issues framed on the PNG) -> crosscheck with inkscape (if installed).
    Files: <path>, <stem>.png, <stem>-lint.png next to path; preview at preview_path (default <stem>-1000.png).
    strict: exit with code 1 after writing everything if layoutlint has an ERROR or palette_check a FAIL.
    Returns dict(svg, png, preview, renderer, issues, errors, warns, fails, ok)."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stem = path[:-4] if path.endswith(".svg") else path
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg_text(W, H))
    name = os.path.basename(path)
    res = dict(svg=path, png=None, preview=None, renderer=None, issues=[], errors=0, warns=0, fails=0)
    print(f"== {name}: {W}x{H}, theme {NAME}, font {FAMILY}")
    if check:
        issues = lint(W, H, preview)
        res["issues"] = issues
        res["errors"] = sum(i["level"] == "ERROR" for i in issues)
        res["warns"] = len(issues) - res["errors"]
        print(f"layout:  {layoutlint.summary(issues)}")
        shown = 0
        for n, i in enumerate(issues, 1):
            if i["level"] == "ERROR" or shown < show_warn:
                shown += i["level"] != "ERROR"
                print(f"  {n:3d} {i['level']:5s} {i['code']:11s} {i['msg']}")
        if res["warns"] > shown:
            print(f"  ... {res['warns'] - shown} more WARN (write(..., show_warn=99) to list them)")
    png = stem + ".png"
    used = render(path, png, png_width, renderer)
    if used:
        res["png"], res["renderer"] = png, used
        im = Image.open(png).convert("RGB")
        prev = preview_path or f"{stem}-{preview}.png"
        os.makedirs(os.path.dirname(os.path.abspath(prev)), exist_ok=True)
        im.resize((preview, round(im.height * preview / im.width)), Image.LANCZOS).save(prev)
        res["preview"] = os.path.abspath(prev)
        print(f"render:  {used} -> {os.path.basename(png)} ({im.width}x{im.height}), preview {prev}")
        if check and res["issues"] and annotate:
            layoutlint.annotate(png, W, res["issues"], stem + "-lint.png")
            print(f"lint:    issues framed in {os.path.basename(stem)}-lint.png")
        elif os.path.exists(stem + "-lint.png"):
            os.remove(stem + "-lint.png")
    else:
        print("render:  no renderer found (resvg, rsvg-convert, inkscape, cairosvg, chrome) — SVG only; "
              "the layout lint above ran on the journal, there is NO PNG to look at")
    if check:
        import palette_check
        items = palette_check.run_svg(path, TH)
        res["fails"] = sum(lv == "FAIL" for lv, _ in items)
        nwarn = sum(lv == "WARN" for lv, _ in items)
        print(f"palette: {res['fails']} FAIL, {nwarn} WARN")
        for lv, msg in items:
            if lv == "FAIL" or (lv == "WARN" and nwarn <= 6):
                print(f"  {lv:5s} {msg}")
        if shutil.which("inkscape"):
            crosscheck(path)
    res["ok"] = res["errors"] == 0 and res["fails"] == 0
    print(f"RESULT:  {'OK' if res['ok'] else 'FIX: ' + str(res['errors']) + ' layout ERROR, ' + str(res['fails']) + ' palette FAIL'}")
    if strict and not res["ok"]:
        raise SystemExit(1)
    return res


def mpl_style(apply=True):
    """matplotlib in the current theme: registers the kit's font files, returns (and applies) rcParams"""
    import matplotlib
    from matplotlib import font_manager
    for _, _, p in FONTS["faces"]:
        try:
            font_manager.fontManager.addfont(p)
        except Exception:
            pass
    rc = PAL.mpl_rc(TH, FAMILY)
    if apply:
        matplotlib.rcParams.update(rc)
    return rc


use_theme()
