"""Builds the dashboard page from the data repo's JSON. Pure functions, no network,
so it can be tested and previewed with sample data."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from htmltools import HTML, TagList, tags

from agent.datastore import is_open, item_tab

ACCOUNTS = [
    ("gmail", "Gmail", "Personal Gmail"),
    ("ud", "UD", "University of Delaware"),
    ("lums", "LUMS", "LUMS"),
]
ACC_LABEL = {k: lbl for k, lbl, _ in ACCOUNTS}
TABS = [("summary", "Summary"), ("reply", "To reply"), ("todo", "To do"),
        ("opp", "Opportunities"), ("waiting", "Waiting"), ("fyi", "FYI")]
DAY = 86400

ICON_CAL = HTML('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>')
ICON_BELL = HTML('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                 '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21h4"/></svg>')
ICON_CHEVRON = HTML('<svg class="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" '
                    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
                    'aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>')
ICON_CHECK = HTML('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                  'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                  '<path d="M5 12l5 5 9-10"/></svg>')
ICON_SNOOZE = HTML('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                   'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                   '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M5 3L2 6M22 6l-3-3"/></svg>')
ICON_OUT = HTML('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<path d="M7 17L17 7M8 7h9v9"/></svg>')


# ----------------------------------------------------------------- helpers
def fmt_received(ts: float, now: float, tz) -> str:
    d = datetime.fromtimestamp(ts, tz)
    today = datetime.fromtimestamp(now, tz).date()
    if d.date() == today:
        return d.strftime("%-I:%M %p")
    if d.date() == today - timedelta(days=1):
        return "Yesterday " + d.strftime("%-I:%M %p")
    return d.strftime("%a %b %-d")


def priority(it: dict) -> int:
    score = int(it.get("urgency", 0)) * 2
    if it.get("needs_reply"):
        score += 2
    if it.get("opportunity") or it.get("deadline"):
        score += 1
    return score


def newest_per_thread(items: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for it in items:
        cur = best.get(it["thread_id"])
        if cur is None or it.get("received", 0) >= cur.get("received", 0):
            best[it["thread_id"]] = it
    return list(best.values())


def gmail_link(item: dict, mailbox: str) -> str:
    return f"https://mail.google.com/mail/?authuser={mailbox}#all/{item['thread_id']}"


def _badge(text: str, cls: str):
    return tags.span(text, class_=f"badge {cls}")


def _acc_tag(acc: str):
    return tags.span(tags.span(class_="dot", aria_hidden="true"), ACC_LABEL.get(acc, acc),
                     class_=f"acc-tag acc-{acc}")


# ------------------------------------------------------------------ pieces
def summary_bullet(it: dict, now: float, tz):
    bits = []
    if it.get("urgency", 0) >= 3:
        bits.append(_badge("Urgent", "b-urgent"))
    if it.get("needs_reply"):
        bits.append(_badge("Needs reply", "b-reply"))
    if it.get("opportunity"):
        bits.append(_badge("Opportunity", "b-opp"))
    if it.get("deadline"):
        cls = "deadline urgent" if it.get("urgency", 0) >= 3 else "deadline"
        bits.append(tags.span(ICON_CAL, it["deadline"], class_=cls,
                              title="On your Google Calendar" if it.get("calendar_added") else None))
    bits.append(tags.span(fmt_received(it.get("received", now), now, tz), class_="when"))
    return tags.li(
        tags.button(
            tags.span(it.get("from_name") or it.get("from_addr", ""), class_="who"), " — ",
            it.get("summary", ""),
            tags.span(*bits, class_="meta"),
            class_="bullet", type="button", data_goto=it["id"],
        ),
        data_id=it["id"], data_acc=it.get("account_key", "gmail"),
    )


def card(it: dict, actions: dict, now: float, tz, mailbox: str):
    tab = it.get("tab") or item_tab(it)
    acc = it.get("account_key", "gmail")
    draft = (actions.get("draft_edits") or {}).get(it["id"], it.get("draft_text") or "")
    waiting = it.get("kind") == "waiting"

    head_badges = [tags.span(it.get("from_name") or it.get("from_addr", ""), class_="who"), _acc_tag(acc)]
    if it.get("urgency", 0) >= 3 and not waiting:
        head_badges.append(_badge("Urgent", "b-urgent"))
    if it.get("opportunity"):
        head_badges.append(_badge("Opportunity", "b-opp"))

    if waiting:
        days = max(0, int((now - it.get("received", now)) // DAY))
        line = it.get("summary", "")
        note = f"You wrote {fmt_received(it.get('received', now), now, tz)} · waiting {days} day{'s' if days != 1 else ''}"
        if it.get("followup_drafted"):
            note += " · follow-up draft ready"
    else:
        line = it.get("action") if tab == "todo" and it.get("action") else it.get("summary", "")
        notes = []
        if it.get("alerted_at"):
            notes.append("Alerted on Telegram at " + datetime.fromtimestamp(it["alerted_at"], tz).strftime("%-I:%M %p"))
        if it.get("opportunity") and it.get("vip") and not it.get("addressed"):
            notes.append("Shared by a VIP through a mailing list")
        notes.append("Received " + fmt_received(it.get("received", now), now, tz))
        note = " · ".join(notes)

    right = []
    if it.get("deadline"):
        right.append(tags.span(ICON_CAL, it["deadline"],
                               class_="deadline urgent" if it.get("urgency", 0) >= 3 else "deadline"))
    right.append(ICON_CHEVRON)

    body = [
        tags.div(tags.span("Your email" if waiting else "The email", class_="label"),
                 tags.p(it.get("body", "") or "(no text)", class_="email-text"), class_="block"),
    ]
    if draft:
        did = f"draft-{it['id']}"
        what = "Follow-up draft" if waiting else "Draft reply"
        body.append(tags.div(
            tags.label(f"{what} · sends from your {ACC_LABEL.get(acc, acc)} address", for_=did, class_="label"),
            tags.textarea(draft, id=did, rows="8", data_draft=it["id"]),
            tags.span("Fill in the words in [brackets]; a draft that still has them can't be sent.",
                      class_="hint"),
            class_="block"))

    buttons = []
    if draft:
        buttons.append(tags.button("Send…", type="button", class_="btn primary",
                                   data_op="compose", data_id=it["id"]))
        buttons.append(tags.button("Save draft to Gmail", type="button", class_="btn",
                                   data_op="save", data_id=it["id"]))
    buttons += [
        tags.button(ICON_CHECK, "They replied" if waiting else "Done", type="button", class_="btn",
                    data_op="done", data_id=it["id"]),
        tags.button(ICON_SNOOZE, "Snooze to tomorrow", type="button", class_="btn",
                    data_op="snooze", data_id=it["id"]),
        tags.a("Open in Gmail", ICON_OUT, href=gmail_link(it, mailbox), target="_blank",
               rel="noopener", class_="btn link"),
    ]
    body.append(tags.div(*buttons, class_="actions"))

    sender = it.get("from_addr", "")
    if sender and not waiting:
        body.append(tags.div(
            tags.span(f"Teach it about {sender}:", class_="teach-label"),
            tags.button("Never show this sender", type="button", class_="chip",
                        data_op="mute", data_id=it["id"], data_sender=sender),
            tags.button("Never urgent", type="button", class_="chip",
                        data_op="calm", data_id=it["id"], data_sender=sender),
            tags.button("Always show", type="button", class_="chip",
                        data_op="always", data_id=it["id"], data_sender=sender),
            class_="teach"))

    return tags.details(
        tags.summary(
            tags.span(tags.span(*head_badges, class_="head-row"),
                      tags.span(line, class_="line"),
                      tags.span(note, class_="note"), class_="head-main"),
            tags.span(*right, class_="head-side"),
            class_="card-head"),
        tags.div(*body, class_="card-body"),
        class_="card", data_id=it["id"], data_tab=tab, data_acc=acc,
    )


def calendar_panel(events: dict, now: float, tz):
    rows = []
    horizon = now + 30 * DAY
    evs = sorted((e for e in (events.get("by_key") or {}).values()
                  if datetime.fromisoformat(e["end"]).timestamp() >= now
                  and datetime.fromisoformat(e["start"]).timestamp() <= horizon),
                 key=lambda e: e["start"])
    for e in evs[:12]:
        start = datetime.fromisoformat(e["start"]).astimezone(tz)
        is_due = e.get("kind") in ("deadline", "application")
        when = start.strftime("%a") + ("" if is_due else start.strftime(" · %-I:%M %p"))
        rows.append(tags.div(
            tags.div(tags.span(start.strftime("%b"), class_="mon"), tags.span(start.strftime("%-d"), class_="day"),
                     class_=f"date acc-{e.get('account_key', 'gmail')}"),
            tags.div(tags.span(e.get("title", ""), class_="ev-title"),
                     tags.span(when, class_="ev-when"),
                     tags.span(ICON_BELL, e.get("remind", ""), class_="ev-remind"),
                     class_="ev-text"),
            class_="event", data_acc=e.get("account_key", "gmail")))
    if not rows:
        rows.append(tags.p("Nothing on the calendar from email yet.", class_="muted"))
    return tags.aside(
        tags.h2("Coming up"),
        tags.p("On your Google Calendar (“From email”), from your inbox and sent mail.", class_="muted"),
        *rows, class_="panel coming-up", aria_label="Coming up")


# -------------------------------------------------------------------- page
def build_page(data: dict, now: float | None = None, tz_name: str = "America/New_York"):
    now = now or time.time()
    tz = ZoneInfo(tz_name)
    items = list((data.get("items") or {}).values())
    actions = data.get("actions") or {}
    events = data.get("events") or {}
    stats = data.get("stats") or {}
    accounts = stats.get("accounts") or []
    mailbox = next((a["address"] for a in accounts if a.get("key") == "gmail"), "")

    live = [i for i in items if i.get("relevant") and is_open(i, actions, now)]
    for i in live:
        i.setdefault("tab", item_tab(i))
    inbox = newest_per_thread([i for i in live if i.get("kind", "inbox") == "inbox"])
    waiting = [i for i in live if i.get("kind") == "waiting"]

    # ---- Summary: last 24 hours, by account, most important first
    recent = [i for i in inbox if i.get("received", 0) >= now - DAY]
    skipped = [s for s in (stats.get("skipped") or []) if s[0] >= now - DAY]
    sections = []
    for key, _label, name in ACCOUNTS:
        mine = sorted((i for i in recent if i.get("account_key") == key),
                      key=lambda i: (-priority(i), -i.get("received", 0)))
        n_skip = sum(1 for s in skipped if s[1] == key)
        bullets = [summary_bullet(i, now, tz) for i in mine]
        if not bullets:
            bullets = [tags.li("Nothing that needs you.", class_="quiet")]
        sections.append(tags.section(
            tags.div(tags.h2(tags.span(class_="dot", aria_hidden="true"), name),
                     tags.span(f"{len(mine)} worth knowing", class_="count"), class_="sec-head"),
            tags.ul(*bullets),
            tags.p(f"+{n_skip} promotions, newsletters and mass emails filtered out" if n_skip
                   else "Nothing filtered out", class_="low"),
            class_=f"acc-section acc-{key}", data_acc=key))

    summary_panel = tags.div(
        tags.div(*sections,
                 tags.p("Last 24 hours, most important first. Threads you've replied to, and items "
                        "you marked done or snoozed, are hidden here and on Telegram.", class_="muted small"),
                 class_="summary-main"),
        calendar_panel(events, now, tz),
        class_="tab-panel summary-grid", id="p-summary")

    # ---- Action tabs
    def panel(key: str, rows: list[dict], empty: str):
        rows = sorted(rows, key=lambda i: (-priority(i), -i.get("received", 0)))
        return tags.div(*[card(i, actions, now, tz, mailbox) for i in rows],
                        tags.div(empty, class_="empty", data_for=key),
                        class_="tab-panel list", id=f"p-{key}")

    fyi_rows = [i for i in inbox if i["tab"] == "fyi" and i.get("received", 0) >= now - 3 * DAY]
    panels = [
        panel("reply", [i for i in inbox if i["tab"] == "reply"], "No replies waiting on you."),
        panel("todo", [i for i in inbox if i["tab"] == "todo"], "Nothing to do."),
        panel("opp", [i for i in inbox if i["tab"] == "opp"], "No open opportunities."),
        panel("waiting", sorted(waiting, key=lambda i: i.get("received", 0)),
              "You're not waiting on anyone."),
        panel("fyi", fyi_rows, "Nothing new to know."),
    ]

    # ---- Header
    month = datetime.fromtimestamp(now, tz).strftime("%Y-%m")
    cost = ((stats.get("monthly") or {}).get(month) or {}).get("cost", 0.0)
    last = stats.get("last_check")
    checked = ("Last checked " + fmt_received(last, now, tz)) if last else "Waiting for the agent's first run"

    filters = [tags.button(tags.span(class_="dot", aria_hidden="true"), "All", type="button",
                           class_="filter acc-all", data_filter="all", aria_pressed="true")]
    for key, label, _ in ACCOUNTS:
        filters.append(tags.button(tags.span(class_="dot", aria_hidden="true"), label, type="button",
                                   class_=f"filter acc-{key}", data_filter=key, aria_pressed="false"))

    tab_buttons = [tags.button(label, tags.span("0", class_="count", data_count=key), type="button",
                               role="tab", class_="tab", data_tab_btn=key,
                               aria_selected="true" if key == "summary" else "false")
                   for key, label in TABS]

    return tags.div(
        tags.header(
            tags.div(tags.h1("Inbox"),
                     tags.p(f"{checked} · ${cost:.2f} API cost this month ",
                            tags.button("Refresh", type="button", class_="linkish", data_op="refresh"),
                            class_="muted"),
                     class_="title"),
            tags.div(*filters, role="group", aria_label="Filter by account", class_="filters"),
            class_="top"),
        tags.nav(*tab_buttons, role="tablist", aria_label="Sections", class_="tabs"),
        summary_panel,
        *panels,
        id="app", class_="f-all t-summary",
    )


def login_page(message: str = ""):
    return tags.div(
        tags.div(
            tags.div(HTML('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" '
                          'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                          '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>'),
                     class_="logo"),
            tags.h1("Inbox"),
            tags.p("Your private email dashboard. Enter your password to continue.", class_="muted"),
            class_="login-head"),
        TagList(),
        class_="login-intro")
