"""light — the default theme: pastel cards on white.

Pastel fill + mid-chroma border + dark title of the same hue; cool slate neutrals; IBM Plex Sans 400/600/700;
orthogonal arrows with white tags. Families are built by palette.family(hue, chroma) — change a hue in
`hues=`, never the recipe:  kit.use_theme("light", hues={"ours": (235, 0.12)}).
"""
from palette import family, oklch

HUES = {
    #  meaning      hue  chroma   notes
    "ours":      (256, 0.115),  # our components / platform — calm blue, the "home" colour
    "external":  (305, 0.100),  # client / vendor / other team — dusty violet, never a status colour
    "focus":     (58, 0.140),   # the subject of THIS picture (one zone) — warm orange
    "ok":        (160, 0.110),  # works / checked — emerald, not traffic-light
    "attention": (90, 0.135),   # limit, needs a decision — ochre; light solid + dark glyph
    "danger":    (27, 0.150),   # breach, failure, blocked — brick red, reserved
}

NEUTRAL = {
    "page":     "#ffffff",  # page background (no off-white)
    "surface":  "#ffffff",  # 'white' cards, panels
    "tile":     "#f4f6f8",  # KPI tiles, neutral cards, zones
    "band":     "#eef1f5",  # table group rows, gantt section bands
    "hairline": "#e9edf1",  # faint separators, track behind bars
    "grid":     "#dde2e8",  # table rules, chart grid
    "rule":     "#dde2e8",  # hairline card border (hairline cards only)
    "subtle":   "#8a96a6",  # non-text only: neutral borders, planned ring, axis line
    "arrow":    "#444b55",  # default (uncoloured) arrow
    "head":     "#33404d",  # dark table header / number badges; white text 10.6:1
    "muted":    "#5f6b7a",  # captions, notes, tick labels — the FLOOR for any text, 5.4:1
    "ink2":     "#3e4a59",  # secondary text: owners, axis titles, 9.3:1
    "ink":      "#1f2933",  # titles, body text, 14.8:1
}


def build(hues=None, neutral=None):
    N = dict(NEUTRAL, **(neutral or {}))
    H = dict(HUES, **(hues or {}))
    F = {k: family(h, c, text_on_fill=N["muted"], page=N["page"]) for k, (h, c) in H.items()}
    if "ok" not in (hues or {}):
        F["ok"]["solid"] = family(166, 0.11)["solid"]       # done-green leans teal: apart from red for deuteranopia
    if "danger" not in (hues or {}):
        F["danger"]["solid"] = oklch(0.47, 0.15, 28)        # deeper than the border: apart from done-green (CVD)
    F["neutral"] = {"border": N["subtle"], "fill": N["tile"], "title": N["head"], "solid": N["muted"],
                    "glyph": "#ffffff", "tint": N["grid"], "soft": oklch(0.84, 0.012, 250)}
    F["white"] = dict(F["neutral"], fill=N["surface"], title=N["ink"])

    # status — colour + shape + glyph; greyscale is carried by shape first
    STATUS = {
        #              fill                          stroke                 glyph  glyph colour
        "done":        (F["ok"]["solid"],            None,                  "✓", "#ffffff"),
        "in_progress": (N["page"],                   F["ours"]["solid"],    "◐", F["ours"]["solid"]),
        "waiting":     (oklch(0.88, 0.055, 305),     F["external"]["solid"], "…", F["external"]["title"]),
        "attention":   (F["attention"]["solid"],     None,                  "!", F["attention"]["glyph"]),
        "planned":     (N["page"],                   N["subtle"],           "•", N["muted"]),
        "blocked":     (F["danger"]["solid"],        None,                  "✕", "#ffffff"),
    }
    FLOW = {
        "f1": F["ours"]["solid"],        # blue    — config / artefacts / "our" pipeline
        "f2": oklch(0.683, 0.15, 49),    # orange  — the primary data being watched (traffic, requests)
        "f3": oklch(0.525, 0.097, 162),  # green   — results / events / alerts going out
        "f4": oklch(0.595, 0.137, 352),  # rose    — a fourth stream (sync, billing, external pull)
        "f5": N["arrow"],                # slate   — control / orchestration
    }
    return dict(
        NAME="light", DARK=False, CARD_STYLE="pastel", STRIP_FAMILIES=(),
        NEUTRAL=N, FAMILY=F, HEAD_FG="#ffffff",
        STATUS=STATUS,
        STATUS_SHAPE={"done": "filled", "in_progress": "half", "waiting": "ring", "attention": "filled",
                      "planned": "ring-hollow", "blocked": "filled"},
        STATUS_LABEL={"done": "done", "in_progress": "in progress", "waiting": "waiting on others",
                      "attention": "attention, limit", "planned": "planned", "blocked": "blocked"},
        FLOW=FLOW,
        FLOW_DASH={"secondary": (F["ours"]["solid"], "7 5"), "depends": (N["arrow"], "7 5"),
                   "planned": (N["subtle"], "4 4")},
        SERIES={"before": oklch(0.66, 0.16, 45), "after": oklch(0.56, 0.14, 256),
                "neutral": oklch(0.84, 0.012, 250), "neutral_mark": N["subtle"], "extra": FLOW["f3"]},
        BAND={"highlight": F["attention"]["fill"], "incident": oklch(0.975, 0.014, 40), "today": N["ink"]},
        # role: (size, weight, letter-spacing) on a 1600-wide canvas; 13 px is the floor (8.1 px at 1000 wide)
        TYPE={
            "title":    (30, 700, 0),     # what + date, one line
            "subtitle": (16, 400, 0),     # scope, boundaries, what is NOT shown
            "section":  (20, 700, 0),     # heading outside boxes ("Why it is built this way")
            "panel":    (18, 600, 0),     # zone title
            "card":     (15.5, 600, 0),   # card title
            "body":     (14.5, 400, 0),   # card text, bullets, table cells
            "small":    (13, 400, 0),     # secondary line, legend, footnote — the floor
            "mono":     (13, 400, 0),     # technical values (IBM Plex Mono)
            "pill":     (13, 600, 0),     # tag text
            "label":    (13, 500, 0),     # arrow tag text
            "kpi":      (36, 700, 0),     # big number
            "eyebrow":  (13, 700, 0.6),   # UPPERCASE row labels
        },
        LH=1.4, TRACK_BY_SIZE=(), WEIGHT={"regular": 400, "bold": 700},
        MARGIN=40, PAD=16, GAP=20, ZONE_PAD=20,
        RX_CARD=8, RX_ZONE=10, RX_TAG=4, RX_PILL="round",
        SW_CARD=1.4, SW_ZONE=1.4, SW_ARROW=2.0, SW_FLOW=2.6, SW_STRIP=3.0, DASH="7 5",
        ARROW_HEAD=(6, "M0,0 L10,5 L0,10 z"),
        LABEL={"fill": "page", "sw": 1.0, "pad": 16},     # arrow tag: white box, border in the arrow colour
        TAG_FILL="fill",                                  # tag(): family fill + family border + title text
        ZONE={"family": "neutral", "title_role": "panel", "upper": False},
        KPI={"frame": "family", "layout": "caption-top", "accent_bar": False},
        GLOW=0.0, EXTRA=(),
    )
