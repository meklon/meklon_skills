"""graphite — almost monochrome, one accent.

Graphite neutrals carry everything (text, borders, bars, marks). ONE accent — teal, the `focus` family — only on
the main flow and the key state; red only for failure; violet for external parties. Cards are white with a 1 px
hairline; emphasis is a 3 px strip on the left plus the family colour in the title. Statuses differ by SHAPE
first (filled / half / dashed ring / diamond / hollow ring / filled red). Title and KPI in Plex Light,
technical values in Plex Mono, section headings are small tracked capitals (eyebrows).
"""
from palette import family, oklch

H_N = 255
HUES = {
    "focus":     (195, 0.105),   # the accent: main flow, the key state
    "external":  (300, 0.070),   # client / vendor / other team — muted violet
    "attention": (80, 0.100),    # limit, needs a decision — muted ochre (strip / tag only)
    "danger":    (27, 0.165),    # failure only
}


def n(L, c=0.012):
    return oklch(L, c, H_N)


NEUTRAL = {
    "page":     "#ffffff",
    "surface":  "#ffffff",
    "tile":     n(0.978, 0.002),   # KPI tiles, swatch backgrounds, zones
    "band":     n(0.955, 0.004),   # lane stripes, table group rows
    "hairline": n(0.935, 0.004),   # faint separators
    "grid":     n(0.915, 0.005),   # chart grid, tracks
    "rule":     n(0.845, 0.007),   # hairline: card borders, separators
    "subtle":   n(0.665, 0.010),   # non-text: planned rings, axis line, waiting bars
    "arrow":    n(0.390, 0.016),   # default arrow (= ink2)
    "head":     n(0.255, 0.014),   # number circles, filled 'done' marks (= ink)
    "muted":    n(0.515, 0.014),   # captions, mono values — the floor for text
    "ink2":     n(0.390, 0.016),   # secondary text, bars, control arrows
    "ink":      n(0.255, 0.014),   # titles, body text
}


def build(hues=None, neutral=None):
    N = dict(NEUTRAL, **(neutral or {}))
    H = dict(HUES, **(hues or {}))
    F = {k: family(h, c, text_on_fill=N["muted"], page=N["page"]) for k, (h, c) in H.items()}
    if "danger" not in (hues or {}):
        F["danger"]["solid"] = oklch(0.50, 0.170, 27)      # deeper than the border: 'stop' in greyscale too
    INK, INK2 = N["ink"], N["ink2"]
    # ours / ok are graphite: the default card is plain white, 'done' is ink
    F["ours"] = {"border": N["rule"], "fill": N["tile"], "title": INK, "solid": INK2, "glyph": "#ffffff",
                 "tint": N["grid"], "soft": N["subtle"]}
    F["ok"] = {"border": N["subtle"], "fill": N["tile"], "title": INK, "solid": INK, "glyph": "#ffffff",
               "tint": N["grid"], "soft": N["subtle"]}
    F["neutral"] = {"border": N["rule"], "fill": N["tile"], "title": INK, "solid": INK2, "glyph": "#ffffff",
                    "tint": N["grid"], "soft": N["subtle"]}
    F["white"] = dict(F["neutral"], fill=N["surface"])
    TEAL, RED = F["focus"]["solid"], F["danger"]["solid"]
    STATUS = {
        #              fill          stroke         glyph  glyph colour
        "done":        (INK,         None,          "✓", "#ffffff"),
        "in_progress": (N["page"],   TEAL,          "◐", TEAL),       # the key state: accent
        "waiting":     (N["page"],   N["subtle"],   "…", INK2),       # dashed ring
        "attention":   (N["grid"],   INK,           "!", INK),        # diamond
        "planned":     (N["page"],   N["subtle"],   "",  N["muted"]),  # thin hollow ring
        "blocked":     (RED,         None,          "✕", "#ffffff"),  # the only red mark
    }
    return dict(
        NAME="graphite", DARK=False, CARD_STYLE="hairline",
        STRIP_FAMILIES=("focus", "danger", "external", "attention", "ok"),
        NEUTRAL=N, FAMILY=F, HEAD_FG="#ffffff",
        STATUS=STATUS,
        STATUS_SHAPE={"done": "filled", "in_progress": "half", "waiting": "ring-dashed", "attention": "diamond",
                      "planned": "ring-hollow", "blocked": "filled"},
        STATUS_LABEL={"done": "done", "in_progress": "in progress", "waiting": "waiting on a timer",
                      "attention": "works, with a caveat", "planned": "planned", "blocked": "failed · stop"},
        FLOW={"f1": TEAL,                       # main flow (the happy path) — the only coloured arrow
              "f2": INK2,                       # service calls / a second data stream
              "f3": INK,                        # results / events going out
              "f4": oklch(0.45, 0.10, 300),     # external party (darker than the violet strip: apart from teal)
              "f5": N["subtle"]},               # control / timer (draw dotted: FLOW_DASH["waiting"])
        FLOW_DASH={"failure": (RED, "6 4"), "waiting": (N["subtle"], "2 4"), "depends": (N["subtle"], "2 4"),
                   "planned": (N["subtle"], "4 4")},
        SERIES={"before": N["subtle"], "after": TEAL, "neutral": N["grid"], "neutral_mark": N["rule"],
                "extra": INK2},
        BAND={"highlight": F["focus"]["fill"], "incident": F["danger"]["fill"], "today": INK},
        TYPE={
            "title":    (42, 300, 0),     # big and light — the Swiss headline
            "subtitle": (16, 400, 0),
            "section":  (13, 500, 1.4),   # small tracked capitals (use eyebrow())
            "panel":    (13, 500, 1.4),   # zone title: an eyebrow too
            "card":     (16, 600, 0),
            "body":     (14.5, 400, 0),
            "small":    (13, 400, 0),
            "mono":     (13, 400, 0),     # technical values: timings, hosts, kinds
            "pill":     (13, 500, 0),
            "label":    (13, 500, 0),
            "kpi":      (40, 300, 0),     # big number — light, like the title
            "eyebrow":  (13, 500, 1.4),
        },
        LH=1.42, TRACK_BY_SIZE=(), WEIGHT={"regular": 400, "bold": 600},
        MARGIN=56, PAD=16, GAP=24, ZONE_PAD=20,
        RX_CARD=3, RX_ZONE=4, RX_TAG=2, RX_PILL=2,
        SW_CARD=1.0, SW_ZONE=1.0, SW_ARROW=1.4, SW_FLOW=2.2, SW_STRIP=3.0, DASH="6 4",
        ARROW_HEAD=(5.2, "M0,0.8 L10,5 L0,9.2 z"),
        LABEL={"fill": "page", "sw": 1.0, "pad": 14},
        TAG_FILL="page",                                  # tag(): white + family border + family title
        ZONE={"family": "neutral", "title_role": "panel", "upper": True},
        KPI={"frame": "tile", "layout": "value-top", "accent_bar": False},
        GLOW=0.0, EXTRA=(),
    )
