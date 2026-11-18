"""Builds the public demo: a static copy of the real dashboard with made-up emails.

    python build.py            # writes the site to ./site
    python build.py --serve    # ... then serves it at http://localhost:8000

The page markup comes from the real dashboard's code (ui/view.py) and its styles and
scripts (ui/static). demo.js stands in for the server, so every button works but nothing
is read from or sent to any mailbox."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from htmltools import tags

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import demo_data  # noqa: E402
from ui import view  # noqa: E402

TZ_NAME = "America/New_York"
OUT = ROOT / "site"

# Account names shown in the demo
view.ACCOUNTS[:] = [("gmail", "Personal", "Personal"), ("ud", "Work", "Work"), ("lums", "Alumni", "Alumni")]
view.ACC_LABEL.clear()
view.ACC_LABEL.update({k: lbl for k, lbl, _ in view.ACCOUNTS})


def demo_now() -> float:
    """2:05 PM today (New York), so the demo always reads like mid-afternoon."""
    tz = ZoneInfo(TZ_NAME)
    return datetime.now(tz).replace(hour=14, minute=5, second=0, microsecond=0).timestamp()


def compose_info(data: dict) -> dict:
    """What the Send… dialog shows for each email, worked out here instead of on a server."""
    out = {}
    for it in data["items"].values():
        if not it.get("draft_text"):
            continue
        meta = it.get("reply_meta") or {}
        own = {a["address"] for a in data["stats"]["accounts"]}
        if it.get("kind") == "waiting":
            to = meta.get("to") or [it["from_addr"]]
        else:
            to = [it["from_addr"]]
        others = [c for c in meta.get("cc", []) if c not in own and c not in to]
        subject = it.get("subject", "")
        out[it["id"]] = {"from": it["send_from"], "to": to, "others": others,
                         "subject": subject if subject.lower().startswith("re:") else "Re: " + subject}
    return out


def banner(data: dict, now: float):
    items = [i for i in data["items"].values() if not i.get("replied")]
    filtered = len(data["stats"]["skipped"])
    alerts = sum(1 for i in items if i.get("alerted_at"))
    drafts = sum(1 for i in items if i.get("draft_text"))
    steps = [
        ("Reads", "New mail from three inboxes (personal, work, alumni), every few minutes."),
        ("Sorts", "Claude decides what matters: needs a reply, a task, an opportunity, or just FYI. "
                  "Newsletters and mass emails are filtered out."),
        ("Alerts", "My phone (Telegram) buzzes only for urgent things: an interview, a form with a "
                   "deadline, or someone writing to me directly and waiting on an answer. Everything "
                   "else waits for two short digests, at 9 AM and 4 PM."),
        ("Drafts", "Replies are drafted in my voice. I edit them here and press Send, with a 30-second "
                   "undo. Nothing is ever sent without me."),
        ("Schedules", "Meetings and deadlines go on my Google Calendar, with reminders 3 days before."),
        ("Learns", "Threads I've replied to disappear; one tap teaches it to mute or always show a sender."),
    ]
    return tags.section(
        tags.div(
            tags.span("Live demo · made-up emails", class_="demo-pill"),
            tags.h2("An AI email assistant that only interrupts me when something needs me"),
            tags.p("This is my real dashboard, filled with fictional emails. Click around: open an email, "
                   "edit a draft, press Send…, mark things done. Nothing here touches a real mailbox."),
            tags.ul(
                tags.li(tags.strong(str(filtered)), " mass emails filtered out today"),
                tags.li(tags.strong(str(alerts)), " phone alert"
                        + ("" if alerts == 1 else "s")),
                tags.li(tags.strong(str(drafts)), " replies drafted and waiting"),
                class_="demo-stats"),
            tags.details(
                tags.summary("How it works"),
                tags.ol(*[tags.li(tags.strong(a), " ", b) for a, b in steps]),
                tags.p("Built with Python, the Claude API (Haiku), the Gmail and Google Calendar APIs, "
                       "GitHub Actions, Telegram and Shiny for Python on Google Cloud Run.",
                       class_="demo-stack"),
                class_="demo-how"),
            class_="demo-inner"),
        class_="demo-banner", aria_label="About this demo")


def build() -> Path:
    tz = ZoneInfo(TZ_NAME)
    now = demo_now()
    data = demo_data.build(now, tz)
    page = view.build_page(json.loads(json.dumps(data)), now, TZ_NAME)
    payload = json.dumps({"compose": compose_info(data), "undo": 10}).replace("</", "<\\/")

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Inbox Assistant Demo</title>
<meta name="description" content="Demo of an AI email assistant: triage, drafted replies, calendar deadlines and alerts only when something needs attention.">
<meta name="theme-color" content="#F6F6F3">
<link rel="icon" href="icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600&display=swap">
<link rel="stylesheet" href="app.css">
<link rel="stylesheet" href="demo.css">
</head>
<body>
<div class="page container-fluid">
{banner(data, now)}
{page}
<div id="toast" role="status" aria-live="polite"></div>
</div>
<script type="application/json" id="demo-data">{payload}</script>
<script src="demo.js"></script>
<script src="app.js"></script>
</body>
</html>
"""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "index.html").write_text(doc, encoding="utf-8")
    for name in ("app.css", "app.js", "icon.png"):
        shutil.copy(ROOT / "ui" / "static" / name, OUT / name)
    for name in ("demo.css", "demo.js"):
        shutil.copy(ROOT / name, OUT / name)
    (OUT / ".nojekyll").write_text("")
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"Demo written to {out}")
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
        print("Open http://localhost:8000")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
