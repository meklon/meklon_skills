"""night — dark theme for slides and screen-share.

Page deep blue-graphite (L 0.205), never black (black + light text = halation on projectors). Ink 0.93, not #fff.
Body in the Plex «Text» cut (450), titles 600 (700 clots light-on-dark), a little letter-spacing on small sizes,
line height 1.45. Families from palette.family_night(): the fill is a lifted surface, the title a pale tint, the
solid a soft glowing mark that carries a DARK glyph. Accents L 0.78-0.84, chroma <= 0.13 — muted glow, no neon.
Borders thin (1.1 px) and dim. Filled marks get a faint halo (GLOW).
"""
from palette import family_night, oklch

HUE_N, CH_N = 255, 0.022
HUES = {
    "ours":      (242, 0.115),  # our platform — cold ice blue
    "external":  (298, 0.075),  # other teams / vendors — dusty lavender, never a status
    "focus":     (62, 0.115),   # the subject of this picture — warm apricot
    "ok":        (168, 0.115),  # done / checked — mint
    "attention": (82, 0.120),   # needs a decision — amber
    "danger":    (25, 0.130),   # failure / blocked — coral, reserved
}
SOLID_L = {"ours": 0.77, "ok": 0.845}   # sky vs mint: same lightness reads as one colour — split by L


def n(L, c=CH_N):
    return oklch(L, c, HUE_N)


NEUTRAL = {
    "page":     n(0.205),          # background of the whole picture
    "surface":  n(0.235),          # cards, footer blocks, panels
    "tile":     n(0.245),          # KPI tiles, neutral cards
    "hairline": n(0.255, 0.018),   # row separators, track behind bars
    "band":     n(0.268),          # gantt section bands, table group rows
    "grid":     n(0.29, 0.018),    # week grid, faint frames
    "rule":     n(0.29, 0.018),    # hairline card border
    "head":     n(0.30),           # table header / number badges (ink on it)
    "subtle":   n(0.525, 0.025),   # non-text: neutral borders, planned ring, axis line
    "arrow":    n(0.70, 0.02),     # default (uncoloured) arrow
    "muted":    n(0.735, 0.022),   # captions, owners, notes — the floor for any text
    "ink2":     n(0.845, 0.016),   # secondary text
    "ink":      n(0.935, 0.010),   # titles, body
}
DARK_GLYPH = n(0.20, 0.03)          # glyph on a glowing mark


def build(hues=None, neutral=None):
    N = dict(NEUTRAL, **(neutral or {}))
    H = dict(HUES, **(hues or {}))
    own = hues or {}
    F = {k: family_night(h, c, muted=N["muted"], glyph=DARK_GLYPH,
                         yellow=(k == "attention") if k not in own else None,
                         solid_L=SOLID_L.get(k) if k not in own else None) for k, (h, c) in H.items()}
    if "danger" not in (hues or {}):
        F["danger"]["solid"] = oklch(0.70, 0.135, 27)   # deeper than done-mint: apart for red-green CVD
    F["neutral"] = {"border": N["subtle"], "fill": N["tile"], "title": N["ink"], "solid": N["muted"],
                    "glyph": DARK_GLYPH, "tint": N["head"], "soft": n(0.42, 0.02)}
    F["white"] = dict(F["neutral"], fill=N["surface"], title=N["ink"])
    PAGE = N["page"]
    STATUS = {
        #              fill                          stroke                     glyph glyph colour
        "done":        (F["ok"]["solid"],            None,                      "✓", DARK_GLYPH),
        "in_progress": (PAGE,                        F["ours"]["solid"],        "◐", F["ours"]["solid"]),
        "waiting":     (F["external"]["fill"],       oklch(0.66, 0.075, 298),   "…", F["external"]["title"]),
        "attention":   (F["attention"]["solid"],     None,                      "!", DARK_GLYPH),
        "planned":     (PAGE,                        N["subtle"],               "",  N["muted"]),
        "blocked":     (F["danger"]["solid"],        None,                      "✕", DARK_GLYPH),
    }
    return dict(
        NAME="night", DARK=True, CARD_STYLE="pastel", STRIP_FAMILIES=(),
        NEUTRAL=N, FAMILY=F, HEAD_FG=N["ink"],
        STATUS=STATUS,
        STATUS_SHAPE={"done": "filled", "in_progress": "half", "waiting": "ring", "attention": "diamond",
                      "planned": "ring-hollow", "blocked": "filled"},
        STATUS_LABEL={"done": "done", "in_progress": "in progress", "waiting": "waiting on others",
                      "attention": "decision needed", "planned": "planned", "blocked": "blocked"},
        FLOW={"f1": F["ours"]["solid"],     # ice blue — logs / our pipeline
              "f2": oklch(0.78, 0.115, 62),  # apricot  — the primary data being watched
              "f3": F["ok"]["solid"],       # mint     — results / alerts going out
              "f4": oklch(0.72, 0.13, 338),  # rose     — a fourth stream
              "f5": n(0.58, 0.02)},          # slate    — control / orchestration
        FLOW_DASH={"depends": (n(0.60, 0.03), "6 5"), "planned": (N["subtle"], "4 4"),
                   "secondary": (F["ours"]["solid"], "6 5")},
        SERIES={"before": oklch(0.68, 0.13, 40), "after": F["ours"]["solid"], "neutral": n(0.545, 0.02),
                "neutral_mark": n(0.60, 0.02), "extra": F["ok"]["solid"]},
        BAND={"highlight": F["attention"]["fill"], "quarter": n(0.225, 0.024), "today": F["ours"]["solid"],
              "due": F["danger"]["solid"]},
        TYPE={
            "title":    (30, 600, 0.0),
            "subtitle": (16, 450, 0.15),
            "section":  (20, 600, 0.1),
            "panel":    (17, 600, 0.15),
            "card":     (15.5, 600, 0.15),
            "body":     (14.5, 450, 0.2),
            "small":    (13, 450, 0.3),
            "mono":     (13, 400, 0.0),
            "pill":     (13, 600, 0.4),
            "label":    (13, 500, 0.3),
            "kpi":      (36, 500, 0.0),
            "eyebrow":  (13, 600, 1.3),
        },
        LH=1.45,
        TRACK_BY_SIZE=((13.5, 0.3), (16, 0.2), (22, 0.1)),   # default tracking: light on dark needs air
        WEIGHT={"regular": 450, "bold": 600},
        MARGIN=40, PAD=16, GAP=20, ZONE_PAD=20,
        RX_CARD=10, RX_ZONE=12, RX_TAG="round", RX_PILL="round",
        SW_CARD=1.1, SW_ZONE=1.1, SW_ARROW=1.8, SW_FLOW=2.4, SW_STRIP=3.0, DASH="6 5",
        ARROW_HEAD=(6, "M0,0 L10,5 L0,10 z"),
        LABEL={"fill": "page", "sw": 1.0, "pad": 16},
        TAG_FILL="fill",
        ZONE={"family": "white", "stroke": "grid", "title_role": "panel", "upper": False},
        KPI={"frame": "tile", "layout": "value-top", "accent_bar": True},
        GLOW=0.22, DARK_GLYPH=DARK_GLYPH, EXTRA=(),
    )
