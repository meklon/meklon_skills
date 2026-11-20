#!/usr/bin/env python3
"""Example · light theme: a target-architecture picture on top, the theme's style sheet below.

python3 gen.py  ->  sheet-1000.png here, full-size SVG / PNG / lint PNG in ./out/
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import kit as K  # noqa: E402

K.use_theme("light")
from kit import (T, MARGIN, ZONE_PAD, C, text, box, card, card_h, cards_row, row_x,  # noqa: E402
                 bullets_row, zone, connect, arrow, line, pill, tw, add, write)

W = 1600
S = T["small"][0]
N, F = K.N, K.F
INK, INK2, MUTED, SUBTLE = K.INK, K.INK2, K.MUTED, K.SUBTLE
IN = ZONE_PAD
# flows of this picture: theme flow colour + dash; arrow tags pick a readable text colour themselves
FL = {
    "sql":     dict(color=K.FLOW["f2"], dash=False, name="SQL traffic"),
    "wal":     dict(color=K.FLOW["f1"], dash=False, name="WAL: streaming"),
    "archive": dict(color=K.FLOW["f1"], dash=True, name="WAL: archive, backups"),
    "dcs":     dict(color=N["arrow"], dash=True, name="etcd quorum (Raft)"),
    "metrics": dict(color=K.FLOW["f3"], dash=False, name="metrics and alerts"),
}


def flow(a, b, kind, sa=None, sb=None, width=None, **kw):
    f = FL[kind]
    return connect(a, b, sa, sb, color=f["color"], dashed=f["dash"],
                   width=width or (K.SW_FLOW if kind in ("sql", "wal") else K.SW_ARROW), **kw)


def legend_swatch(x, y, kind, w=32):
    f = FL[kind]
    d = ' stroke-dasharray="7 5"' if f["dash"] else ""
    add(f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" stroke="{f["color"]}" stroke-width="3"{d}/>')


# =====================================================================================================
# 1. functional part — architecture
# =====================================================================================================
text(MARGIN, 58, "Payments platform — PostgreSQL HA across two data centres", role="title")
text(MARGIN, 90, "Target architecture · 20.11.2026 · PostgreSQL 16 + Patroni 3.3 · 1.4 TB, 2 800 TPS at peak · "
     "network and application code are out of scope", *T["subtitle"], color=MUTED)
lx = MARGIN
for kind in ("sql", "wal", "archive", "dcs", "metrics"):
    legend_swatch(lx, 121, kind)
    text(lx + 42, 126, FL[kind]["name"], S, color=MUTED)
    lx += 42 + tw(FL[kind]["name"], S) + 34
# family key on the right of the legend line
fx = W - MARGIN
for fam, s in reversed((("external", "client / provider"), ("ours", "platform we run"), ("focus", "write path"))):
    fx -= tw(s, S) + 22
    text(fx + 22, 126, s, S, color=MUTED)
    add(f'<rect x="{fx:.1f}" y="113" width="14" height="14" rx="3" fill="{F[fam]["fill"]}" '
        f'stroke="{F[fam]["border"]}" stroke-width="1.4"/>')
    fx -= 24

TOP = 152
widths = [220, 250, 330, 290]
x = MARGIN
cols = []
for w_ in widths:
    cols.append((x, w_))
    x += w_ + 24
cols.append((x, W - MARGIN - x))
(AX, AW), (BX, BW), (D1X, D1W), (D2X, D2W), (D3X, D3W) = cols
Y0 = TOP + IN + 18 + 26

# ---- DC1: primary, sync replica; DC2: async replica on the sync row; site 3: S3 facing the primary
p_w = D1W - 2 * IN
prim_lines = ["32 vCPU · 256 GB · NVMe RAID10",
              [("ok", "synchronous_mode: on"), ("ok", "archive_command: pgBackRest"),
               ("ok", "holds the leader key, TTL 30 s")]]
prim_pills = [("Patroni leader", F["focus"]["solid"])]
sync_lines = ["Confirms every commit before the client sees it.",
              ("Read pool · nightly backups run here", MUTED)]
sync_pills = [("sync standby", F["ours"]["solid"])]
asy_lines = ["Lag p99 1.2 s, paged at 5 s.", ("Promotion by hand: DB-07", MUTED)]
asy_pills = [("no auto-failover", F["attention"]["solid"])]

h_prim = card_h(p_w, "pg-dc1-a · primary", prim_lines, pills=prim_pills)
sync_y = Y0 + h_prim + 64
h_row2 = max(card_h(p_w, "pg-dc1-b · sync replica", sync_lines, pills=sync_pills),
             card_h(D2W - 2 * IN, "pg-dc2-a · async replica", asy_lines, pills=asy_pills))
prim = card(D1X + IN, Y0, p_w, h_prim, "focus", "pg-dc1-a · primary", prim_lines, pills=prim_pills)
sync = card(D1X + IN, sync_y, p_w, h_row2, "ours", "pg-dc1-b · sync replica", sync_lines, pills=sync_pills)
asy = card(D2X + IN, sync_y, D2W - 2 * IN, h_row2, "ours", "pg-dc2-a · async replica", asy_lines,
           pills=asy_pills)

s3_lines = [[("ok", "WAL segments, ≤ 60 s behind"), ("ok", "full weekly, diff nightly"),
             ("ok", "encrypted, object lock 35 days"), ("ok", "restore tested every Monday")]]
s3_title = "S3 · pgBackRest repository"
s3 = card(D3X + IN, Y0, D3W - 2 * IN, None, "external", s3_title, s3_lines)

plan_l = ["Logical replica of 6 tables, so reporting stops reading the sync replica.",
          ("planned Q1 2027", MUTED)]
plan = card(D3X + IN, sync_y, D3W - 2 * IN, None, "white", "Analytics replica", plan_l, dashed=True)

# ---- etcd row
ETCD_Y = max(sync["y"] + sync["h"], s3["y"] + s3["h"], plan["y"] + plan["h"]) + 34
e_lines = [("Raft member", MUTED)]
e_w = 184
e_h = card_h(e_w, "etcd-3 · tie-break", e_lines)
e1 = card(D1X + (D1W - e_w) / 2, ETCD_Y, e_w, e_h, "neutral", "etcd-1", e_lines)
e2 = card(D2X + (D2W - e_w) / 2, ETCD_Y, e_w, e_h, "neutral", "etcd-2", e_lines)
e3 = card(D3X + IN, ETCD_Y, e_w, e_h, "neutral", "etcd-3 · tie-break", e_lines)

# ---- connection layer and services, aligned to the DB cards
pgb_lines = [[("ok", "transaction pooling"), ("ok", "2 400 clients → 160 server conns"),
              ("ok", "follows the leader: Patroni REST, 2 s"),
              ("ok", "reads: sync replica, then DC2"), ("warn", "alert: wait > 20 ms")]]
pgb = card(BX + IN, Y0, BW - 2 * IN, sync["y"] + sync["h"] - Y0, "ours", "PgBouncer ×2", pgb_lines,
           pills=[("keepalived VIP", F["ours"]["solid"])])
a_w = AW - 2 * IN
api_l = ["Card authorisations.", ("40 pods · writes", MUTED)]
led_l = ["Settlement batch every 5 min.", ("writes", MUTED)]
rep_l = ["Merchant dashboards.", ("reads, tolerates lag", MUTED)]
h_api, h_led, h_rep = (card_h(a_w, t, l) for t, l in (("payments-api", api_l), ("ledger-worker", led_l),
                                                       ("reporting", rep_l)))
api = card(AX + IN, Y0, a_w, h_api, "external", "payments-api", api_l)
rep_y = sync["y"] + sync["h"] - h_rep
rep = card(AX + IN, rep_y, a_w, h_rep, "external", "reporting", rep_l)
led_y = (Y0 + h_api + rep_y) / 2 - h_led / 2
led = card(AX + IN, led_y, a_w, h_led, "external", "ledger-worker", led_l)
con_l = ["VIP 10.20.0.10", (":6432 rw · :6433 ro", MUTED)]
con = card(AX + IN, ETCD_Y, a_w, None, "white",
           "Client contract", con_l)
BOTTOM1 = max(ETCD_Y + e_h, con["y"] + con["h"]) + IN

z_a = zone(AX, TOP, AW, BOTTOM1 - TOP, "neutral", "Payments services")
z_b = zone(BX, TOP, BW, BOTTOM1 - TOP, "neutral", "Connection layer")
z_1 = zone(D1X, TOP, D1W, BOTTOM1 - TOP, "neutral", "DC1 · primary site")
z_2 = zone(D2X, TOP, D2W, BOTTOM1 - TOP, "neutral", "DC2 · standby site, 40 km")
z_3 = zone(D3X, TOP, D3W, BOTTOM1 - TOP, "neutral", "Cloud region · witness, backups")

# ---- arrows
for c_ in (api, led, rep):
    flow(c_, pgb, "sql")
flow(pgb, prim, "sql", at=api["y"] + api["h"] / 2, lab="rw")
flow(pgb, sync, "sql", at=rep["y"] + rep["h"] / 2, lab="ro")
flow(prim, sync, "wal", "b", "t", lab="sync · +0.4 ms")
ARC_Y = Y0 + 46
flow(prim, s3, "archive", at=ARC_Y, lab="archive-push", lab_at=0.45)
flow(prim, asy, "wal", "r", "t", at=Y0 + h_prim - 36, lab="async · 40 km", lab_at=0.62)
dcs = FL["dcs"]
ey = ETCD_Y + e_h / 2
for a_, b_ in ((e1, e2), (e2, e3)):
    arrow(f"M{a_['x'] + a_['w'] + 2:.1f},{ey:.1f} H{b_['x'] - 2:.1f}", dcs["color"], True, K.SW_ARROW, head=False)
K.label((e1["x"] + e1["w"] + e2["x"]) / 2, ey, "quorum 2 of 3", dcs["color"])

# ---- row 2: recovery targets + monitoring
R2 = BOTTOM1 + 24
KX, KW = AX, BX + BW - AX
MX, MW = D1X, W - MARGIN - D1X
ry = R2 + IN + 18 + 26
KPI = 28
tile_h = 24 + 2 * (KPI + 30) + 8

mon = [
    dict(color="neutral", title="postgres_exporter",
         lines=["On all 3 nodes, :9187.", ("plus Patroni and pgBackRest metrics", MUTED)]),
    dict(color="neutral", title="Prometheus ×2", lines=["Scrape 15 s, keep 30 days.", "One per DC, both alert.", ("Grafana: PG HA board", MUTED)]),
    dict(color="neutral", title="Alertmanager", lines=[[("warn", "lag > 5 s"), ("warn", "no leader 30 s"),
                                                       ("warn", "archive stuck 5 min")]]),
    dict(color="ok", title="On-call DBA", lines=["Phone and chat, 24/7.", "Ack within 5 min.", ("runbooks DB-01 … DB-09", MUTED)]),
]
mrow = cards_row(MX + IN, ry, MW - 2 * IN, mon, gap=44, h=tile_h)
for a_, b_ in zip(mrow, mrow[1:]):
    flow(a_, b_, "metrics")

tiles = [("ok", "Node fails in DC1", [("RPO", "0 s"), ("RTO", "30 s")]),
         ("attention", "DC1 is lost", [("RPO", "5 s"), ("RTO", "15 min")]),
         ("ours", "Restore from S3", [("RPO", "60 s"), ("RTO", "2 h")])]
kcols = row_x(KX + IN, KW - 2 * IN, 3, 14)
for (tx, tw_), (fam, cap, kv) in zip(kcols, tiles):
    box(tx, ry, tw_, tile_h, fam, name=cap)
    text(tx + 14, ry + 26, cap, S, 600, F[fam]["title"])
    yy = ry + 52
    for k_, v in kv:
        text(tx + 14, yy, k_, S, 600, MUTED)
        text(tx + 14, yy + KPI + 2, v, KPI, 700, F[fam]["title"])
        yy += KPI + 30
BOTTOM2 = ry + tile_h + IN
z_k = zone(KX, R2, KW, BOTTOM2 - R2, "neutral", "Recovery targets")
z_m = zone(MX, R2, MW, BOTTOM2 - R2, "neutral", "Monitoring")
flow(z_1, mrow[0], "metrics", "b", "t", at=mrow[0]["x"] + mrow[0]["w"] - 40)

# ---- why
by = BOTTOM2 + 48
text(MARGIN, by, "Why it is built this way", role="section")
why = bullets_row(MARGIN, by + 18, W - 2 * MARGIN, [
    ("ok", "No lost payment inside DC1", [
        ("ok", "Every commit is on two nodes before the client sees it."),
        ("ok", "Patroni fails over only to the sync replica: automatic, ≤ 30 s."),
        ("ok", "Cost: +0.4 ms per commit at 0.2 ms RTT."),
    ]),
    ("ours", "A third site breaks the tie", [
        ("ok", "etcd on three sites: either DC can go, quorum stays."),
        ("ok", "On a DC1–DC2 split only the side with 2 of 3 keeps a leader."),
        ("ok", "etcd-3 is a small VM: a vote, no data."),
    ]),
    ("attention", "Losing DC1 is a human decision", [
        ("warn", "DC2 is async: promoting it may drop ≤ 5 s of writes."),
        ("ok", "Duty DBA agrees it with payments, runbook DB-07."),
        ("ok", "S3 gives a second way back: any second of 35 days."),
    ]),
])
FUNC_END = why[0]["y"] + why[0]["h"]

# =====================================================================================================
# 2. style sheet
FAMILIES = [("ours", "Ours", "our platform"), ("external", "External", "client, vendor"),
            ("focus", "Focus", "the subject"), ("ok", "OK", "works, checked"), ("attention", "Attention", "limit"),
            ("danger", "Danger", "failure"), ("neutral", "Neutral", "context")]
# =====================================================================================================
C["panel"] = (N["grid"], "#ffffff", INK)
LBL = 13


def caps(x, y, s):
    """row label inside a panel: small, bold, muted"""
    return text(x, y, s.upper(), LBL, 700, MUTED)


def hexline(x, y, col, s=None, swatch=True):
    if swatch:
        add(f'<rect x="{x:.1f}" y="{y - 10.5:.1f}" width="12" height="12" rx="3" fill="{col}" '
            f'stroke="{N["subtle"]}" stroke-width="0.8"/>')
        x += 18
    if s:
        text(x, y, s, S, 400, INK2)
        x += tw(s, S) + 8
    text(x, y, col, S, 400, MUTED, mono=True)


SY = FUNC_END + 40
line(MARGIN, SY, W - MARGIN, SY, N["subtle"], 1)
text(MARGIN, SY + 36, "Style sheet · light", role="section")
note = "themes/light.py · IBM Plex Sans 400 / 600 / 700 · pastel fill, mid border, dark title of one hue"
text(W - MARGIN, SY + 36, note, S, 400, MUTED, anchor="end")

# ---------------------------------------------------------------- palette panel
PX, PW = MARGIN, W - 2 * MARGIN
py = SY + 56
LX = PX + 24                 # row labels
CX0 = PX + 170               # content
CWID = PX + PW - 24 - CX0
y = py + 30 + 40

caps(LX, y + 4, "Neutrals")
neutrals = [("ink", "titles, body"), ("ink2", "secondary text"), ("muted", "captions · floor"),
            ("subtle", "borders, no text"), ("grid", "rules, grid"), ("tile", "KPI, neutral"),
            ("band", "group rows"), ("head", "badges"), ("arrow", "default arrow")]
for (cx, cw), (k, role) in zip(row_x(CX0, CWID, len(neutrals), 12), neutrals):
    add(f'<rect x="{cx:.1f}" y="{y - 22:.1f}" width="40" height="40" rx="8" fill="{N[k]}" '
        f'stroke="{N["subtle"] if K.PAL.contrast(N[k], "#ffffff") < 1.5 else N[k]}" stroke-width="1"/>')
    text(cx + 50, y - 6, k, S, 600, INK)
    text(cx + 50, y + 12, N[k], S, 400, MUTED, mono=True)
y += 40

caps(LX, y + 26, "Card families")
fam_y = y
fcols = row_x(CX0, CWID, len(FAMILIES), 14)
fam_h = 30 + 20 + 4 * 20 + 2
for (cx, cw), (k, name, role) in zip(fcols, FAMILIES):
    box(cx, y, cw, fam_h, k, name=name)
    text(cx + 14, y + 28, name, T["card"][0], 600, F[k]["title"])
    text(cx + 14 + tw(name, T["card"][0], 600) + 8, y + 28, role, S, 400, MUTED)
    yy = y + 56
    for part in ("border", "fill", "title", "solid"):
        hexline(cx + 14, yy, F[k][part], part)
        yy += 20
y += fam_h + 30

caps(LX, y + 4, "Flows · status")
items = [("flow", k) for k in ("sql", "wal", "dcs", "metrics")] + [("status", k) for k in K.STATUS]
for (cx, cw), (kind, k) in zip(row_x(CX0, CWID, len(items), 10), items):
    if kind == "flow":
        f = FL[k]
        d = ' stroke-dasharray="6 4"' if f["dash"] else ""
        add(f'<line x1="{cx:.1f}" y1="{y - 2:.1f}" x2="{cx + 30:.1f}" y2="{y - 2:.1f}" stroke="{f["color"]}" '
            f'stroke-width="3"{d}/>')
        nm, col = {"sql": "SQL", "wal": "WAL", "dcs": "quorum", "metrics": "metrics"}[k], f["color"]
    else:
        K.mark(cx + 15, y - 3, k, 10)
        nm, col = K.TH["STATUS_LABEL"][k].split(",")[0].replace("works with a limit / input needed", "attention"), \
            K.STATUS[k][0] if K.STATUS[k][0] != "#ffffff" else K.STATUS[k][1]
        nm = {"waiting on others": "waiting", "works": "attention"}.get(nm, nm)
    text(cx + 40, y - 6, nm, S, 600, INK)
    text(cx + 40, y + 12, col, S, 400, MUTED, mono=True)
y += 30
z_pal = zone(PX, py, PW, y - py, "panel", "Palette")
text(PX + 20 + tw("Palette", *T["panel"]) + 14, py + 20 + 18 * 0.8, "cool slate neutrals · one hue per meaning, "
     "family(hue) builds border, fill, title, solid", S, 400, MUTED)

# ---------------------------------------------------------------- typography panel
ty0 = y + 16
TX, TWD = MARGIN, 640
KX2, KW2 = TX + TWD + 20, W - MARGIN - (TX + TWD + 20)
SAMPLE = "Сенсор на каждом узле · Sensor on every node 0123"
SHORT = "Сенсор на каждом узле · Sensor 0123"
roles = [("Title", "title", "Сенсор · Sensor 0123"), ("Subtitle", "subtitle", SAMPLE),
         ("Section", "section", SHORT), ("Zone", "panel", SHORT), ("Card title", "card", SAMPLE),
         ("Body", "body", SAMPLE), ("Small", "small", SAMPLE), ("Pill", "pill", None),
         ("KPI", "kpi", "2 800 TPS · 0 s")]
yy = ty0 + 30 + 22
for nm, r, smp in roles:
    sz, wt = T[r]
    yy += max(sz * 0.95, 15)
    text(TX + 24, yy, nm, S, 600, INK)
    text(TX + 24 + 82, yy, f"{sz:g} / {wt}", S, 400, MUTED, mono=True)
    if smp is None:
        px_ = TX + 210
        for k, s_ in (("ours", "sync standby"), ("focus", "Patroni leader"), ("attention", "no auto-failover")):
            px_ += pill(px_, yy, s_, F[k]["solid"]) + 8
    else:
        text(TX + 210, yy, smp, sz, wt, MUTED if r in ("subtitle", "small") else INK)
    yy += max(sz * 0.42, 11) + 4
TY_END = yy + 4

# ---------------------------------------------------------------- components panel
cx0, cw0 = KX2 + 24, KW2 - 48
ccols = row_x(cx0, cw0, 3, 28, weights=[1.12, 0.94, 0.94])
top = ty0 + 30 + 34
(c1x, c1w), (c2x, c2w), (c3x, c3w) = ccols

caps(c1x, top, "Cards")
cA = card(c1x, top + 14, c1w, None, "focus", "pg-dc1-a · primary", ["The subject: one per picture."],
          pills=[("Patroni leader", F["focus"]["solid"])])
cB = card(c1x, cA["y"] + cA["h"] + 12, c1w, None, "ours", "PgBouncer ×2",
          ["Body 14.5 on a pastel fill."])
cC = card(c1x, cB["y"] + cB["h"] + 12, c1w, None, "white", "Analytics replica",
          [("dashed border: planned", MUTED)], dashed=True)

caps(c2x, top, "Status marks")
for i, k in enumerate(K.STATUS):
    my = top + 34 + i * 25
    K.mark(c2x + 9, my - 5, k, 9)
    text(c2x + 28, my, {"waiting": "waiting on others", "in_progress": "in progress",
                        "attention": "attention, limit"}.get(k, k), T["body"][0], 400, INK)
caps(c2x, top + 34 + 6 * 25 + 4, "KPI tile")
ky = top + 34 + 6 * 25 + 16
box(c2x, ky, c2w, 74, "ok", name="kpi")
text(c2x + 14, ky + 24, "RPO · node fails in DC1", S, 600, F["ok"]["title"])
text(c2x + 14, ky + 60, "0 s", T["kpi"][0], 700, F["ok"]["title"])

caps(c3x, top, "Arrows · tags")
for i, (k, tag) in enumerate((("sql", "rw"), ("wal", "sync"), ("archive", "archive"), ("dcs", "2 of 3"),
                              ("metrics", "scrape"))):
    ay = top + 30 + i * 25
    f = FL[k]
    arrow(f"M{c3x:.1f},{ay:.1f} H{c3x + 104:.1f}", f["color"], f["dash"],
          K.SW_FLOW if k in ("sql", "wal") else K.SW_ARROW, head=(k != "dcs"))
    K.label(c3x + 50, ay, tag, f["color"])
    text(c3x + 118, ay + 4.5, {"sql": "requests", "wal": "replication", "archive": "archive, backup",
                               "dcs": "quorum", "metrics": "metrics"}[k], S, 400, INK2)
caps(c3x, top + 34 + 6 * 25 + 4, "Do / don't")
K.bullets(c3x, ky + 18, c3w, [
    ("ok", "Straight or one bend."),
    ("ok", "A glyph beside every colour."),
    ("no", "Text below 13 px."),
], T["body"][0], gap=4)
CY_END = max(ky + 74, cC["y"] + cC["h"]) + 22
P_END = max(TY_END, CY_END)
zone(TX, ty0, TWD, P_END - ty0, "panel", "Typography")
text(TX + 20 + tw("Typography", *T["panel"]) + 14, ty0 + 20 + 18 * 0.8, "IBM Plex Sans · line height 1.4",
     S, 400, MUTED)
zone(KX2, ty0, KW2, P_END - ty0, "panel", "Components")
text(KX2 + 20 + tw("Components", *T["panel"]) + 14, ty0 + 20 + 18 * 0.8,
     "radius 8 card, 10 zone · stroke 1.4 · arrows 2.0 / 2.6", S, 400, MUTED)

H = int(P_END + MARGIN)
write(os.path.join(HERE, "out", "sheet.svg"), W, H, preview_path=os.path.join(HERE, "sheet-1000.png"))
