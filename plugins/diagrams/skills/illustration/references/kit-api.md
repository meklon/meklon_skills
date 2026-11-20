# kit.py — API reference

Logical canvas 1600 px wide (1200 for small pictures). Coordinates are absolute, `y` of text is the baseline.
Only Pillow is required; renderers and matplotlib are optional.

```python
import os, sys
sys.path.insert(0, "<skill>/scripts")
import kit as K
K.use_theme("light")                      # light | graphite | night | /path/my_theme.py
K.text(K.MARGIN, 56, "Title", role="title")
rs = K.cards_row(K.MARGIN, 120, 1600 - 2 * K.MARGIN, [dict(color="ours", title="api", lines=["..."]), ...])
K.connect(rs[0], rs[1], flow_name="f1", lab="HTTPS")
K.write("out/pic.svg", 1600, H, preview_path="pic-1000.png")
```

Call `use_theme()` before drawing. Names taken with `from kit import X` keep the value they had at import —
after switching themes read them as `K.X` (dicts `T`, `LS`, `C`, `TH` are updated in place).

## Theme tokens (after `use_theme`)

| name | what |
|---|---|
| `K.N` | neutrals: `page surface tile band hairline grid rule subtle arrow head muted ink2 ink` |
| `K.F` | families `ours external focus ok attention danger neutral white` → `border fill title solid glyph tint soft` |
| `K.INK K.INK2 K.MUTED K.SUBTLE K.PAGE` | shortcuts; `MUTED` is the floor for any text |
| `K.FLOW` | `f1`..`f5` arrow colours (f1 main/our pipeline, f2 primary data, f3 results/alerts, f4 4th stream, f5 control) |
| `K.FLOW_DASH` | named dashed styles `{name: (colour, dash)}`: `depends`, `planned`, graphite also `failure`, `waiting` |
| `K.STATUS`, `K.TH["STATUS_SHAPE"]` | `done in_progress waiting attention planned blocked` → (fill, stroke, glyph, glyph colour), shape |
| `K.SERIES`, `K.BAND` | chart roles `before after neutral neutral_mark extra`; bands `highlight incident today` |
| `K.T`, `K.LS`, `K.LH` | role → (size, weight); role → letter-spacing; line height |
| `K.MARGIN PAD GAP ZONE_PAD RX_CARD RX_ZONE SW_CARD SW_ZONE SW_ARROW SW_FLOW` | geometry |
| `K.TH` | the whole theme dict (`CARD_STYLE` pastel/hairline, `GLOW`, `WEIGHT`, `KPI`, `ZONE`, `LABEL` ...) |

Type roles: `title subtitle section panel card body small mono pill label kpi eyebrow`. 13 px (`small`) is the floor:
anything smaller fails the lint (SMALL) at a 1000 px preview.

## Text
- `text(x, y, s, size=None, bold=None, color=None, anchor="start", role=None, ls=None, upper=False, mono=False)` —
  one line; `role=` sets size/weight/tracking; `bold`: True / False / 300..700 (theme maps True→700 or 600,
  False→400 or 450). Returns the journal entry (`bb` = ink box).
- `para(x, y, w, s, size, color, bold, lh, mono)` → baseline after the last line; `para_h(w, s, ...)` → height.
- `eyebrow(x, y, s, color)` — small tracked capitals. `tw(s, size, bold, ls, mono)` width; `wrap(s, w, size, bold)`.

## Shapes and lines
- `rect(x, y, w, h, fill, stroke, sw, rx, dash, role="bg"|"box"|"tag", name, journal=True)` → `{x, y, w, h}`.
  `role="box"` makes it a card for the linter (text-edge, overlap checks); `bg` = opaque backdrop only.
- `box(x, y, w, h, color, dashed, ...)` — card frame in the theme's style (pastel: family fill+border;
  hairline: white + rule + left strip for emphasised families). `strip(r, colour)` adds a strip by hand.
- `line(x1, y1, x2, y2, color, width, dashed, journal=True)`; `polyline(pts, color)`;
  `arrow(d, color, dashed, width, head=True)` for an SVG path `d`. `journal=False` hides decoration
  (grids behind bars) from the linter — only for things that never meet text.
- `add(svg)` raw element, `defs(svg)` raw `<defs>` entry — not journaled, not linted.

## Marks and tags (vector glyphs, no font dependency)
- `mark(cx, cy, kind, r=8.5, glow=None)` — status: `done in_progress waiting attention planned blocked`
  (aliases `ok no warn wait prog`), `dot` = neutral bullet, any other string = numbered badge.
- `badge(cx, cy, "3", r=11, fill, fg, ring)` — step number. Numbered lists: `bullets(..., [("1", text), ("2", text)])`
  draws the same badges — never the glyphs ①②③ (missing in Plex: GLYPH warning).
- `bullets(x, y, w, [(kind, text[, bold]), ...], size)` → y after the list. `y` is the *baseline of the first
  line* (as for `text`), so after an `eyebrow` at baseline `y0` start bullets at about `y0 + 24`.
- `label(x, y, s, color)` — tag centred on a line (text colour made readable automatically).
- `pill(x, y, s, color_or_family, fg=None)` solid pill; `tag(x, y, s, family, mono=False)` outlined tag.
  Both take the baseline `y` and return the width.

## Layout
- `card(x, y, w, h, color, title, lines, pills=(), dashed=False)` — `h=None` sizes to content. A line is
  `"text"`, `("text", colour)`, `("text", "mono")` or a bullet list `[(kind, text), ...]`; `colour` is `#hex`,
  `ink` / `ink2` / `muted` / `subtle` or a family name (its title colour) — anything else raises. Returns `{x, y, w, h}`.
  A card with a table or mixed content inside: `box(x, y, w, h, fam)` + `text(..., role="card")` + `table(...)` /
  `bullets(...)` at your own `y`, sizing `h` from the returned `y` values.
- `card_h(w, title, lines, pills=())` — height a card needs. `measure(fn, *a)` runs a drawing fn without drawing.
- `row_x(x, w, n, gap, weights)` → `[(x, width)]`; `cards_row(x, y, w, specs, gap, weights, h, arrows=colour)`.
- `bullets_row(x, y, w, [(family, title, items), ...])` — equal-height footer blocks ("why / risks / next").
- `zone(x, y, w, h, color=None, title=None)` — container drawn *behind* what is already placed: size it last.
  `zone_top(y)` → where the first card of a zone starting at `y` goes (below its title); `x + ZONE_PAD` inside.
- `connect(a, b, sa=None, sb=None, color, dashed, at, via, lab, lab_at, flow_name)` — orthogonal arrow between two
  boxes: straight when they overlap on the cross axis (`at` = that coordinate, must lie inside the shared span
  minus 10 px — otherwise the arrow bends), else one Z/L-bend at `via`;
  `lab` puts a tag on the longest segment (stderr warning when the segment is too short for it); `flow_name="f2"` / `"depends"` takes colour + dash from the theme.

## Components
- `kpi(x, y, w, value, caption, fam="ours")` — KPI tile in the theme's style → rect; the caption wraps to the tile width,
  the value shrinks (down to the `section` size) to fit the tile.
- `kpi_row(x, y, w, [(value, caption[, family]), ...], gap, fam, weights)` — tiles of equal height in one row
  (EMPTY is not reported for them); use it instead of hand-measuring `kpi(h=...)`.
- `legend(x, y, [("arrow"|"flow", "f1", text), ("status", kind, text), ("family", fam, text),
  ("line", (colour, dash), text)])` → x after the last item. A dashed line: `("flow", "depends", text)` or
  `("line", K.FLOW_DASH["depends"], text)` — the same style `connect(flow_name="depends")` draws.
- `table(x, y, w, [(title, weight[, "end"|"mono"])], rows, row_h=30)` — cells `str`, `(str, colour)`,
  `("mark", kind, str)` → y below.
- Gantt: `sx = scale(date0, date1, x0, x1)` (dates or numbers), `bar(sx(a), sx(b), cy, kind, h=8, now=sx(today))`
  — bar styled by status (planned = outline, in_progress filled up to `now`).
- Charts: `hbars(x, y, w, [(label, value[, colour|series key])])`,
  `line_chart(x, y, w, h, [(name, values, colour|series key)], xlabels)`. For anything richer use matplotlib.

## write()
`write(path, W, H, png_width=2400, preview=1000, preview_path=None, strict=True, renderer=None, show_warn=12)`
(`show_warn` — how many WARN lines to print; ERRORs are always printed):
1. SVG → `path`; 2. layoutlint on the journal (theme page colour); 3. render PNG `<stem>.png` (2400 px);
4. preview (PIL) → `preview_path` or `<stem>-1000.png`; 5. `<stem>-lint.png` with issues framed (if any);
6. palette_check on the SVG against the theme; 7. crosscheck journal vs inkscape text boxes (if inkscape exists).

Stdout: `layout: N ERROR, M WARN (CODES)`, `render: <renderer>`, `palette: N FAIL, M WARN`, `crosscheck: ...`,
`RESULT: OK | FIX ...`. With `strict=True` (default) a layout ERROR or palette FAIL exits with code 1 *after*
all files are written (look at `-lint.png`). `strict=False` returns the result dict instead
(`ok, errors, warns, fails, issues, png, preview, renderer`). `reset()` starts a new picture in one process.

Lint codes — ERROR: `TEXT×TEXT TEXT×TAG TEXT-EDGE TEXT-CANVAS LINE×TEXT ARROW×BOX BOX×BOX SMALL`;
WARN: `GRID×TEXT TIGHT-PAD TIGHT-GAP DETOUR ROW-HEIGHT EMPTY CONTRAST TAG-EDGE CANVAS WORDS GLYPH ORPHAN`
(`ORPHAN`: a wrapped paragraph ends with a single word — rephrase or change the width)
(`GLYPH`: the font has no such character — draw it with `mark()` / `arrow()` instead).

Renderers, first available wins: `resvg` (CLI or `resvg_py`) → `rsvg-convert` → `inkscape` → `cairosvg` →
headless Chrome/Chromium. Force with `KIT_RENDERER=chrome` (or a comma list). Nothing found → SVG only, lint
still runs, and the output says there is no PNG. Notes: resvg draws the Plex «Text» cut (night body, 450) as
Regular (~1 % narrower); cairosvg knows only regular/bold weights and no blur filters (night halos are flat).

Fonts: `fonts/` of the skill → system → matplotlib's DejaVu → system DejaVu; metrics (PIL) come from the same file.
Renderers get the same files: temporary fonts.conf via `FONTCONFIG_FILE` (rsvg, inkscape, cairosvg, chrome),
`--use-fonts-dir` (resvg), `@font-face` data URIs (chrome). `KIT_FONT=dejavu` forces the fallback,
`KIT_FC_ISOLATE=1` hides system fonts from renderers. Do not use IBM Plex Sans Condensed (inkscape substitutes it).

## matplotlib
`K.mpl_style()` registers the kit's fonts and applies `palette.mpl_rc(K.TH)` (page, ink, grid, series cycle).
Before `savefig`: `import mpllint; mpllint.report(fig)` — the same layout checks from matplotlib's text extents.

## A new theme from a pair of tones
Families come from one hue each — `palette.family(hue, chroma)` (light page) or `family_night(...)` (dark page) —
with guaranteed text contrast, so a theme is mostly a choice of hues (OKLCH degrees):

```python
K.use_theme("light", hues={"ours": (235, 0.12), "focus": (40, 0.14)})   # one-off override
```
or a file `my_theme.py` (then `K.use_theme("/path/my_theme.py")`):
```python
from themes import light
def build(**kw):
    t = light.build(hues={"ours": (235, 0.12), "focus": (40, 0.14)}, **kw)
    t["NAME"] = "acme"
    return t
```
Keys missing in a custom theme are taken from `light`. Validate before use:
`python3 scripts/palette_check.py --theme /path/my_theme.py` (text contrast on every surface, CVD and greyscale
separation of statuses/flows/series) and `--hues "ours=235:0.12,focus=40:0.14" [--dark]` for a quick look at hues.
CLI linters: `layoutlint.py pic.svg` (any flat SVG, needs inkscape), `palette_check.py --svg pic.svg --theme X`.
