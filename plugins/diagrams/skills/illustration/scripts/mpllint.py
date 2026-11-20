#!/usr/bin/env python3
"""mpllint — the same layout checks for matplotlib figures, from the renderer's own text extents.

In a generator, right before savefig:
    import mpllint; mpllint.report(fig)            # prints issues; mpllint.lint(fig) returns them

Or wrap an existing script without touching it (savefig is intercepted, output goes to --out):
    mpllint.py script.py [script args...] --out /some/dir

What it reads: every visible Text artist (titles, tick labels, annotations, fig.text) with
get_window_extent(renderer) — real glyph boxes in output pixels; FancyBboxPatch / Rectangle patches with a
visible edge as boxes (fill-only patches = bars / bands: opaque, not boxes); Line2D as lines.
Font size floor: size_pt * dpi / 72 * preview / figure_width_px.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layoutlint  # noqa: E402


def journal(fig):
    import matplotlib.colors as mcolors
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyBboxPatch, Rectangle
    from matplotlib.text import Text

    fig.canvas.draw()                         # layout must be final before extents are read
    r = fig.canvas.get_renderer()
    W, H = fig.bbox.width, fig.bbox.height
    px = fig.dpi / 72.0

    def flip(bb):                             # display coords (origin bottom-left) -> top-left like SVG
        return (bb.x0, H - bb.y1, bb.width, bb.height)

    def hexc(c):
        try:
            rgba = mcolors.to_rgba(c)
            return None if rgba[3] == 0 else mcolors.to_hex(rgba)
        except Exception:
            return None

    texts, rects, lines = [], [], []
    z = 0
    for a in fig.findobj(lambda x: x.get_visible()):
        z += 1
        if isinstance(a, Text):
            s = a.get_text().strip()
            if not s:
                continue
            bb = flip(a.get_window_extent(r))
            # extents are layout boxes (full ascent + descent), not ink: trim to roughly the ink box
            k = 0.16 * bb[3] / max(1, s.count("\n") + 1)
            bb = (bb[0], bb[1] + k, bb[2], bb[3] - 2 * k)
            texts.append(dict(id=f"t{len(texts)}", s=s.replace("\n", " ⏎ "), bb=bb,
                              size=a.get_fontsize() * px, fill=hexc(a.get_color()) or "#000000",
                              role="text", z=z + 10000 * a.get_zorder()))
        elif isinstance(a, FancyBboxPatch) or (isinstance(a, Rectangle) and a.axes is None):   # figure-level panels
            bb = a.get_window_extent(r)
            if bb.width < 2 or bb.height < 2 or (bb.width >= W - 1 and bb.height >= H - 1):
                continue
            edge = hexc(a.get_edgecolor()) if a.get_linewidth() > 0 else None
            fill = hexc(a.get_facecolor()) if a.get_fill() else None
            rects.append(dict(id=f"r{len(rects)}", bb=flip(bb), fill=fill or "none",
                              role="box" if edge else "band", z=z + 10000 * a.get_zorder()))
        elif isinstance(a, Rectangle):                                    # bars, bands inside axes
            bb = a.get_window_extent(r)
            if a is a.axes.patch or bb.width < 1 or bb.height < 1:
                continue
            fill = hexc(a.get_facecolor()) if a.get_fill() else None
            rects.append(dict(id=f"r{len(rects)}", bb=flip(bb), fill=fill or "none", role="band",
                              z=z + 10000 * a.get_zorder()))
        elif isinstance(a, Line2D):
            xy = a.get_transform().transform(a.get_xydata()) if len(a.get_xydata()) else []
            pts = [(float(x), float(H - y)) for x, y in xy]
            if len(pts) >= 2 and a.get_linestyle() not in ("None", "none", " ", ""):
                lines.append(dict(id=f"l{len(lines)}", polys=[pts], arrow=False, stroke=hexc(a.get_color()),
                                  z=z + 10000 * a.get_zorder()))
    return W, H, texts, rects, lines


def lint(fig, preview=1000, min_px=8.0, **kw):
    W, H, texts, rects, lines = journal(fig)
    return layoutlint.check(W, H, texts, rects, lines, preview=preview, min_px=min_px, **kw), W


def report(fig, title="figure", preview=1000, png=None, **kw):
    issues, W = lint(fig, preview, **kw)
    layoutlint.report(issues, title)
    if png:
        layoutlint.annotate(png, W, issues, png[:-4] + "-lint.png")
    return issues


def main():
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i:i + 2]
    script, sargs = args[0], args[1:]
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    orig = Figure.savefig
    done = []

    def savefig(self, fname, *a, **k):
        name = os.path.basename(str(fname))
        if out:
            fname = os.path.join(out, name)
        if not done:
            print(f"== lint before savefig ({name}) ==")
            done.append(report(self, name))
        res = orig(self, fname, *a, **k)
        if str(fname).endswith(".png") and done and os.path.exists(str(fname)):
            layoutlint.annotate(str(fname), self.bbox.width, done[0], str(fname)[:-4] + "-lint.png")
        return res

    Figure.savefig = savefig
    sys.argv = [script] + sargs
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
