---
name: illustration
description: >-
  Use when an engineering illustration is needed as a static image — an
  architecture or target-state diagram, a step-by-step process or rollout flow,
  a status board, a roadmap or gantt, an incident write-up with charts — for a
  report, a ticket in an issue tracker, a client, a slide or a document; also
  when an existing generated diagram has overlapping labels, text spilling out
  of boxes, arrows crossing boxes or is unreadable in a small preview. Triggers:
  "draw a diagram", "make an illustration / a picture for the report",
  "architecture diagram (as-built / target)", "status board", "roadmap / gantt
  as an image", "incident write-up with charts", "labels overlap", "unreadable
  in the preview".
---

# Engineering illustrations

A static picture (PNG + SVG) an engineer attaches to a report, a ticket, an
email to a client or a slide. It is drawn by a Python script on the kit in
`scripts/`: the kit knows the geometry of every element, so quality is checked
automatically, not by eye.

**The point:** the picture answers one question, reads in a 1000 px wide
preview and is calm in style. The reference style below is a guide, not a
template: topic, genre and audience can be anything. Only measurable thresholds
are hard rules.

**Not this skill:** an interactive dashboard or web page — build HTML instead;
a diagram in an engineers' README that people will edit by hand — Mermaid.

## Who draws

**A subagent draws; the main session sets the task and shows the result.**
Drawing accumulates ~100–130k tokens (previews, versions of `gen.py`, linter
output) — in the main session they would be re-read on every later turn.
The main session draws itself only for a tiny picture (the size of
`examples/hello.py`) or when the user explicitly asks to draw right here.

**1. Before starting — one question to the user** (AskUserQuestion if
available): which model draws.

| Model | Cost and time (rough) | What you get |
|---|---|---|
| Opus | ≈ $3–4, ~6 min | fuller and neater: more facts on the picture, careful layout |
| Sonnet | ≈ $0.5, 1–2 min | **simpler**: thinner content, some facts may not make it, closer to a sketch |

The figures come from one architecture diagram measured on 2026-11-20 — a
guide, not a promise. If the user already named the model, or said "quick" or
"cheaper", do not ask again. If you propose a theme other than `light` (see
"Themes"), ask in the same question.

**2. Start the subagent** (Agent, `model` per the answer) with a task made of:
- the path to this SKILL.md and the skill folder — "read it and follow it";
- **the facts verbatim**, as the user gave them or as they were established in
  the conversation, with dates and units; the reader, the language, the theme;
- the rule: only what is in the facts goes on the picture; wording that needs
  checking is not drawn but listed in the report;
- the output folder (the task folder or a scratch folder);
- what to return: paths to the PNG / preview / `gen.py`, the `write()` result,
  the WARNs left and why, questions about the facts.

The subagent cannot ask the user — everything that needs deciding is decided
before it starts.

**3. Show the result:** Read the preview; briefly — the check results and the
subagent's questions. The user's edits ("move this", "drop that") go to the
same subagent via SendMessage: it remembers its `gen.py` and edits it instead
of drawing from scratch.

## Work cycle (mandatory — for whoever draws)

1. **Question and form.** State the one question of the picture. Pick the form:
   flow (arrows), time (scale), comparison (table, bars), state (tiles,
   statuses). It does not fit — two pictures, not smaller type.
2. **Facts apart from layout.** Data as lists/dicts at the top of `gen.py`,
   layout on the kit below. Only checked numbers, with dates and units.
   Start from a copy of `examples/hello.py`; the API is in
   `references/kit-api.md` — read it **once**. Do not read `kit.py` whole
   (56 KB in context until the end of the job): for a detail,
   `grep -n "^def name" -A 25 scripts/kit.py`. The large example
   `examples/light-architecture/gen.py` — grep for the technique you need, too.
3. **Render:** the kit's `write()` writes SVG, PNG, a 1000 px preview and runs
   the layout linter and the palette check right away.
4. **0 ERROR.** Go through the WARNs: fix them or keep them deliberately and
   tell the user.
5. **Look at it:** Read the 1000 px preview; `*-lint.png` only when there are
   ERRORs/WARNs. Walk the visual checklist below — the script does not replace it.
6. **Iterate** in place: edit `gen.py` with Edit, do not rewrite the file; fix
   everything found in one render at once, not one item per render. 2–4
   renders are usually enough. **Stop** at 0 ERROR, WARNs dealt with and the
   checklist passed — further polishing does not pay off.
7. **Hand over** the PNG (a subagent — the paths in its report); keep `gen.py`
   and the SVG next to the result — they are how the picture gets edited a week
   later. Client illustrations never go into the plugin repository. Attach it
   to the ticket the way the user usually does it.

## Themes

| Theme | When | Character |
|---|---|---|
| `light` (default) | reports, tickets, clients | pastel fill + mid-saturation border + dark title of the same hue, cool slate neutrals |
| `graphite` | few colour meanings, the eye must follow the main flow | near-monochrome, white cards with a hairline border, one accent on the main flow only |
| `night` | slides, screen-shared calls | deep blue-graphite page, muted accents |

**Draw in `light`.** If another style fits better (the picture goes into
slides — `night`; one main flow and almost no colour meanings — `graphite`; the
client has a brand hue), **propose it and ask** in one sentence with the
reason, before rendering (when working through a subagent — the main session,
before starting it). Without a "yes", stay in `light`. If the user named the
theme, use it without asking.

A custom theme for a client is built from a couple of hues with
`family(hue, chroma)`; the generator guarantees the contrast; verify with
`palette_check`. How — `references/kit-api.md`. What each theme looks like —
`examples/*/sheet-1000.png` (for inspiration, not a template).

## Reference style (flexible)

**Skeleton.** Header: a title "subject — what it is" and a subtitle with the
date, scope and limits ("dev and prod, 20.11 · IDS only, blocks nothing"). A
legend right under the header — only when colour or line type carries meaning.
The body on a grid: zones (owner, trust boundary) → cards. At the bottom a row
of 3 conclusion blocks ("why it is built this way", "waiting on the client /
next on our side / accepted limits", "decision"). A one-line footnote: what
does not change, what is not shown.

**Colour is meaning, not decoration.** Ours — blue, external / client —
violet, the subject of the picture — orange (one zone), ok — green, attention —
ochre, red — failures and blockers only. No more than 3–4 families and 3
coloured flows per picture. A status is shape + glyph, colour comes second.
Text uses text colours or its family's title colour, never the border colour.

**Restraint.** One main accent. No serif display type or "magazine" flourish,
no filled saturated card headers, no neon or gradients — these were tried and
rejected: they look kitschy or hurt the eyes.

**Arrows.** Straight or with one bend. If a detour is needed, rearrange the
boxes. The label is a tag on the long segment of the arrow itself, not next to
it. A short arrow between neighbouring columns (gap < ~130 px) needs no tag —
the legend gives the meaning; `connect` warns when a tag does not fit. Flows
f1–f3 stay distinct under red-green colour blindness; f4–f5 only with a legend
and a tag. The tritan WARN on the f1/f3 pair in `light` is known and acceptable
when the lines have tags or a legend.

**Text.** Short statements, measured facts, one idea per line. The reader's
language and terms, one language per picture (the examples being in English is
no reason to draw in English for a reader who uses another language). Internal
references (MR numbers, ticket ids) only with an explanation. The most
important conclusion is never small grey italics.

## Genre pointers

| Genre | What usually helps |
|---|---|
| Architecture | zones left to right along the main flow; the main flow is one straight line; control and secrets in their own line style; "why it is built this way" at the bottom |
| Step-by-step process | a stage = number in a circle + title + grey "where / who"; a row of equal-height cards with arrows; stop conditions as tags inside cards; rollback as a separate card; a measured timeline last |
| Status board | KPI tiles (number + one line of meaning); a "capability × environment" table with statuses and notes; legend under the table; "waiting / next / limits" |
| Roadmap / gantt | section bands with a summary on the right; task / owner / scale; labelled today and due lines that never cross labels; scale cut to the active range; next steps with owners and dates |
| Incident write-up | 4–5 KPIs with "after"; charts with a claim as the title, a method line and a conclusion; a final "cause → fix → what to watch after rollout" |

## Hard thresholds (checked by the scripts)

| What | Threshold | Code |
|---|---|---|
| Type size in a 1000 px preview | ≥ 8 px any text, ≥ 9 px body (at W=1600: 13 and 14.5) | SMALL |
| Overlaps | texts do not overlap each other or tags | TEXT×TEXT, TEXT×TAG |
| Bounds | text inside its box and the canvas, ≥ 6 px from the border | TEXT-EDGE, TEXT-CANVAS, TIGHT-PAD |
| Lines | do not run over text; an arrow does not pass through another box | LINE×TEXT, ARROW×BOX |
| Gaps | ≥ 10 px between neighbouring boxes, equal within a row | TIGHT-GAP |
| Contrast | text ≥ 4.5:1 to its background, a glyph ≥ 3:1 | palette_check |
| Distinctness | statuses and flows distinct under colour blindness and in greyscale (otherwise a second channel: shape, dash, label) | palette_check |

Soft (WARN): an arrow detour, unequal heights in a row, an empty card bottom
> 40 %, a single word on the last line of a paragraph (ORPHAN), > ~450 words,
H/W > 1.3. Keep a WARN only when the difference is intended and its purpose is
visible: e.g. a card shorter than its neighbours so the main arrow can pass
below it (ROW-HEIGHT). An accidental height difference — align with
`cards_row` / `card_h`.

## Visual checklist (what the script will not catch)

1. Is the main flow or conclusion visible within 5 seconds?
2. No labels hanging apart from their arrow or object?
3. No arrows against the flow or cutting across another flow?
4. No holes: half an empty zone, an empty range on a scale?
5. Colour = meaning, the legend matches the picture, one accent?
6. An even rhythm of spacing, no near-touches?
7. No titles of 3+ lines, no one-word lines?
8. Is the text clear to the reader: no jargon or internal ids, dates and units in place?
9. Glyphs (✓, …, ⚠, non-Latin scripts) drawn, not boxes or a "V"?

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| a "V" or a box instead of ✓ | the font has no such glyph | statuses only through the kit's functions (vector glyphs) |
| text spills out of a box although the linter is clean | metrics came from one font, the renderer used another | render through the kit's `write()` (it hands the fonts to the renderer); with inkscape look at the journal crosscheck |
| a narrow font rendered wide | inkscape silently substitutes IBM Plex Sans Condensed | do not use Condensed |
| the linter is clean but it reads badly | the linter does not see composition | the visual checklist on the 1000 px preview |
| white text on a coloured plate / bar | contrast < 4.5:1 | dark text or the family's `title` colour |
| a matplotlib chart with overlaps | the kit does not see it | `scripts/mpllint.py`, tokens via `mpl_style()` |
| an arrow hits a gap or a corner, the linter is clean | the entry point was set by eye | `connect(at=…)` only inside the shared span of the two boxes; otherwise the kit bends the arrow — check the preview |
| a single word on the last line (ORPHAN) | the width was chosen for different text | a slightly wider card or a shorter phrase |

## Kit: quick start

`gen.py` lives next to the result (the task folder or a scratch folder); the
kit is imported from the skill folder — its path is given when the skill loads
("Base directory for this skill"). Run it with `python3 gen.py`.

```python
import os, sys
sys.dont_write_bytecode = True                # keep __pycache__ out of the skill folder
sys.path.insert(0, "<base dir of this skill>/scripts")
import kit as K

K.use_theme("light")                          # light | graphite | night | path to your own theme
W, M = 1200, K.MARGIN
K.text(M, 56, "Nightly backup of the orders database", role="title")
K.text(M, 86, "pg_dump → S3 → restore test · status 20.11.2026", role="subtitle", color=K.MUTED)
K.legend(M, 120, [("arrow", "f1", "backup data"), ("status", "done", "done")])

cards = K.cards_row(M, 150, W - 2 * M, [      # a row of equal-height cards, height from content
    dict(color="ours", title="orders-db", lines=["PostgreSQL 16, 220 GB.", ("pg_dump at 02:00", "mono")]),
    dict(color="external", title="S3 bucket", lines=["Object lock 35 days."]),
    dict(color="ok", title="Restore test", lines=[("last: 18.11, 41 min", K.MUTED)]),
], gap=130)
K.connect(cards[0], cards[1], flow_name="f1", lab="dump · 38 min")   # orthogonal arrow with a tag
K.connect(cards[1], cards[2], flow_name="f3", lab="restore")

y = cards[0]["y"] + cards[0]["h"] + 40
foot = K.bullets_row(M, y, W - 2 * M, [       # equal-height conclusion blocks at the bottom
    ("ok", "Works", [("done", "Restore test passed 6 weeks in a row.")]),
    ("attention", "Decide", [("attention", "Dump time grows 4 % a month: pgBackRest by Q2?")]),
])
K.write("out/backup.svg", W, int(foot[0]["y"] + foot[0]["h"] + M))
```

`write()` prints `layout: … ERROR`, `render: …`, `palette: … FAIL` and a final
`RESULT: OK | FIX`; on ERROR/FAIL it exits with code 1 after all files are
written — look at `out/<name>-lint.png`. Next to it: `<name>.png` (2400 px) and
`<name>-1000.png` (the preview — this is the one to Read).

The rest is in `references/kit-api.md`: text roles, `card` / `zone` / `connect`
(`at`, `via`), status `mark`, `kpi` / `kpi_row`, `table`, the gantt scale
`scale` + `bar`, simple charts `hbars` / `line_chart`, matplotlib (`mpl_style` +
`mpllint`), a custom theme. Working examples: `examples/hello.py`,
`examples/light-architecture/gen.py`.

## Environment

Python 3.10+ and Pillow are required. IBM Plex fonts live in `fonts/` (OFL) and
are picked up automatically; without them — DejaVu. Renderer — the first one
found: resvg, rsvg-convert, inkscape, cairosvg, headless Chrome. None found —
you get the SVG and the linter report from the geometry, no PNG; tell the user.
