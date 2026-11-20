#!/usr/bin/env python3
"""Minimal picture: header, three cards with arrows, status bullets.  python3 hello.py [light|graphite|night]"""
import os
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import kit as K  # noqa: E402

K.use_theme(sys.argv[1] if len(sys.argv) > 1 else "light")
W, M = 1200, K.MARGIN

K.text(M, 56, "Nightly backup of the orders database", role="title")
K.text(M, 86, "pg_dump → S3 → restore test · status 20.11.2026", role="subtitle", color=K.MUTED)
K.legend(M, 120, [("arrow", "f1", "backup data"), ("arrow", "f3", "check result"),
                  ("status", "done", "done"), ("status", "attention", "needs a decision")])

cards = K.cards_row(M, 150, W - 2 * M, [
    dict(color="ours", title="orders-db", lines=["PostgreSQL 16, 220 GB.", ("pg_dump at 02:00", "mono")]),
    dict(color="external", title="S3 bucket", lines=["Object lock 35 days.", ("cloud provider", K.MUTED)]),
    dict(color="ok", title="Restore test", lines=["Every Monday on a scratch VM.", ("last: 18.11, 41 min", K.MUTED)]),
], gap=130)
K.connect(cards[0], cards[1], flow_name="f1", lab="dump · 38 min")
K.connect(cards[1], cards[2], flow_name="f3", lab="restore")

y = cards[0]["y"] + cards[0]["h"] + 40
foot = K.bullets_row(M, y, W - 2 * M, [
    ("ok", "Works", [("done", "Dumps finish before 03:00 every night."),
                     ("done", "Restore test passed 6 weeks in a row.")]),
    ("attention", "Decide", [("attention", "Dump time grows 4 % a month: switch to pgBackRest by Q2?"),
                             ("planned", "Owner: DBA on duty.")]),
])

out = os.path.join(HERE, "out", f"hello-{K.NAME}.svg")
K.write(out, W, int(foot[0]["y"] + foot[0]["h"] + M))
