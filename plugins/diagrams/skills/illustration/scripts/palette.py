"""Colour math and family generators for the illustration kit. Pure Python, no dependencies.

    oklch(L, C, H) -> hex          hex2oklch(hex) -> (L, C, H)       contrast(a, b) -> WCAG ratio
    family(hue, chroma)            card family for a LIGHT page: border / fill / title / solid / glyph / tint / soft
    family_night(hue, chroma)      the same roles for a DARK page (fill = lifted surface, title = pale tint)
    tokens(theme)                  flat {token: hex} of a theme (palette_check, swatches)
    mpl_rc(theme)                  matplotlib rcParams in the theme's colours and font

A theme is a dict of tokens (see themes/light.py); kit.use_theme() builds it. The family recipe is the house
style: change the hue, never the recipe — every family gets the same harmony and guaranteed text contrast.
"""
import math

# ----------------------------------------------------------------------------------------------
# colour math (sRGB <-> OKLab / OKLCH, WCAG contrast)
# ----------------------------------------------------------------------------------------------


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _delin(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex2rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb2hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


def _lin2oklab(r, g, b):
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _oklab2lin(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def hex2oklab(h):
    return _lin2oklab(*(_lin(c) for c in hex2rgb(h)))


def hex2oklch(h):
    L, a, b = hex2oklab(h)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def oklch(L, C, H):
    """OKLCH -> hex; chroma is reduced until the colour fits sRGB (hue and lightness kept)."""
    for _ in range(80):
        a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
        rgb = _oklab2lin(L, a, b)
        if all(-1e-7 <= c <= 1 + 1e-7 for c in rgb):
            break
        C *= 0.97
    return rgb2hex(_delin(min(1, max(0, c))) for c in rgb)


def luminance(h):
    r, g, b = (_lin(c) for c in hex2rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    ya, yb = luminance(a), luminance(b)
    return (max(ya, yb) + 0.05) / (min(ya, yb) + 0.05)


def lstar(h):
    """CIE L* (0..100) — what the colour becomes in greyscale print."""
    y = luminance(h)
    return 116 * y ** (1 / 3) - 16 if y > 216 / 24389 else y * 24389 / 27


def chroma(h):
    return hex2oklch(h)[1]


# ----------------------------------------------------------------------------------------------
# family generators
# ----------------------------------------------------------------------------------------------
def _yellowness(hue):
    d = min(abs(hue - 90), 360 - abs(hue - 90))
    return math.exp(-(d / 35) ** 2)


def family(hue, chroma=0.115, *, title_min=7.0, text_on_fill="#5f6b7a", page="#ffffff", solid_hue=None,
           solid_light=None):
    """Card family for a light page, from one hue (OKLCH degrees).

    fill   = same hue, L 0.96-0.975, chroma x0.17   -> a tint you feel more than see
    border = same hue, L 0.60 (+ up to 0.13 for yellows, which go muddy when dark), full chroma
    title  = same hue, darkest needed for >= title_min:1 on the fill (default 7:1, AAA)
    solid  = filled marks / arrows / status dots: white glyph >= 4.5:1
             (yellows: light solid + dark glyph instead — dark yellow is olive)
    tint   = L 0.90, chroma x0.42: light bars, highlighted cells; title on it >= 4.5:1
    soft   = L 0.76, chroma x0.62: secondary lines next to a mark (gantt lead-in), never alone
    Guarantees: title/fill >= title_min, text_on_fill/fill >= 4.5, glyph/solid >= 4.5.
    """
    y = _yellowness(hue)
    sh = hue if solid_hue is None else solid_hue
    light = (y > 0.5) if solid_light is None else solid_light
    fL = 0.962 + 0.012 * y
    o = math.exp(-((min(abs(hue - 55), 360 - abs(hue - 55))) / 25) ** 2)
    fh = hue + 12 * o                               # very light oranges read salmon: lean fill to apricot
    fill = oklch(fL, chroma * (0.17 + 0.09 * y), fh)
    while contrast(text_on_fill, fill) < 4.5 and fL < 0.995:
        fL += 0.003
        fill = oklch(fL, chroma * (0.17 + 0.09 * y), fh)
    border = oklch(0.60 + 0.13 * y, chroma, hue)
    th = hue - 10 * y                                # dark yellows turn olive: lean them to amber
    tL = 0.52
    title = oklch(tL, chroma * 0.92, th)
    while contrast(title, fill) < title_min and tL > 0.1:
        tL -= 0.005
        title = oklch(tL, chroma * 0.92, th)
    if light:
        solid = oklch(0.80, chroma * 1.08, sh)
        gL = 0.42
        glyph = oklch(gL, chroma * 0.7, sh - 10 * y)
        while (contrast(glyph, solid) < 4.5 or contrast(glyph, page) < 7) and gL > 0.1:
            gL -= 0.005
            glyph = oklch(gL, chroma * 0.7, sh - 10 * y)
    else:
        sL = 0.60
        solid = oklch(sL, chroma * 1.05, sh)
        while contrast("#ffffff", solid) < 4.5 and sL > 0.1:
            sL -= 0.005
            solid = oklch(sL, chroma * 1.05, sh)
        glyph = "#ffffff"
    tint = oklch(0.90, chroma * 0.42, hue)
    soft = oklch(0.76, chroma * 0.62, hue)
    return {"border": border, "fill": fill, "title": title, "solid": solid, "glyph": glyph, "tint": tint,
            "soft": soft}


def family_night(hue, chroma=0.11, *, muted, glyph, title_min=7.0, yellow=None, solid_L=None, fill_L=0.258):
    """Card family for a dark page, from one hue — the light recipe inverted.

    fill   L 0.258, chroma x0.30  — a surface lifted from the page by ~0.05 (yellows x0.17: no olive-brown)
    border L 0.47,  chroma x0.70  — thin and dim; on dark a bright frame shouts louder than the content
    title  L >= 0.85 pale tint    — >= title_min:1 on the fill (AAA)
    solid  L 0.80 glowing mark    — carries a DARK glyph (>= 4.5:1)
    tint   L 0.37,  chroma x0.55  — bars, highlighted cells; title on it >= 4.5
    soft   L 0.60,  chroma x0.70  — secondary lines (dependency lead-ins, context strokes)
    muted / glyph: the theme's caption colour and dark glyph colour (contrast is guaranteed against them).
    """
    if yellow is None:
        yellow = _yellowness(hue) > 0.5
    fill = oklch(fill_L, chroma * (0.17 if yellow else 0.30), hue)
    border = oklch(0.47 + (0.04 if yellow else 0), chroma * 0.70, hue)
    tL = 0.85
    title = oklch(tL, chroma * 0.75, hue)
    while contrast(title, fill) < title_min and tL < 0.99:
        tL += 0.005
        title = oklch(tL, chroma * 0.75, hue)
    sL = solid_L or (0.80 + (0.03 if yellow else 0))
    solid = oklch(sL, chroma, hue)
    while contrast(glyph, solid) < 4.5 and sL < 0.99:
        sL += 0.005
        solid = oklch(sL, chroma, hue)
    return {"border": border, "fill": fill, "title": title, "solid": solid, "glyph": glyph,
            "tint": oklch(0.37, chroma * 0.55, hue), "soft": oklch(0.60, chroma * 0.70, hue)}


# ----------------------------------------------------------------------------------------------
# theme helpers
# ----------------------------------------------------------------------------------------------
def tokens(th):
    """Flat {token: hex} of a theme dict — used by palette_check (off-palette colours) and swatches."""
    t = {f"neutral.{k}": v for k, v in th["NEUTRAL"].items()}
    for f, d in th["FAMILY"].items():
        t.update({f"{f}.{k}": v for k, v in d.items()})
    for s, (fill, stroke, _, gc) in th["STATUS"].items():
        t[f"status.{s}"] = fill
        t[f"status.{s}.glyph"] = gc
        if stroke:
            t[f"status.{s}.ring"] = stroke
    t.update({f"flow.{k}": v for k, v in th["FLOW"].items()})
    t.update({f"flow.{k}": v for k, (v, _) in th.get("FLOW_DASH", {}).items()})
    t.update({f"series.{k}": v for k, v in th["SERIES"].items()})
    t.update({f"band.{k}": v for k, v in th["BAND"].items()})
    t["head_fg"] = th.get("HEAD_FG", "#ffffff")
    for i, c in enumerate(th.get("EXTRA", ())):
        t[f"extra.{i}"] = c
    return t


def mpl_rc(th, font_family=None):
    """rcParams for matplotlib in the theme's palette. font_family: the family registered by kit.mpl_style()."""
    N, S = th["NEUTRAL"], th["SERIES"]
    cyc = [S["after"], S["before"], S.get("extra", th["FLOW"]["f3"]), th["FLOW"].get("f4", N["subtle"]),
           S.get("neutral_mark", N["subtle"])]
    rc = {
        "figure.facecolor": N["page"], "axes.facecolor": N["page"], "savefig.facecolor": N["page"],
        "text.color": N["ink"], "axes.labelcolor": N["ink2"], "axes.titlecolor": N["ink"],
        "axes.edgecolor": N["subtle"], "xtick.color": N["muted"], "ytick.color": N["muted"],
        "xtick.labelcolor": N["muted"], "ytick.labelcolor": N["muted"], "grid.color": N["grid"],
        "grid.linewidth": 0.8, "legend.labelcolor": N["ink2"], "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
    }
    try:
        rc["axes.prop_cycle"] = __import__("cycler").cycler(color=cyc)
    except ImportError:
        pass
    if font_family:
        rc["font.family"] = font_family
    return rc
