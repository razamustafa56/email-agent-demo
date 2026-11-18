"""Made-up emails for the public demo. No real people, addresses or organizations.

Times are relative to `now`, so the demo always looks like "today" when it's rebuilt."""

from __future__ import annotations

from datetime import datetime, timedelta

ADDRESS = {"gmail": "me@example.com", "ud": "me@work.example.edu", "lums": "me@alumni.example.edu"}
NAME = {"gmail": "Personal", "ud": "Work", "lums": "Alumni"}
H = 3600


def build(now: float, tz) -> dict:
    today = datetime.fromtimestamp(now, tz)

    def day(n: int, fmt: str) -> str:
        d = today + timedelta(days=n)
        return d.strftime(fmt).replace(" 0", " ")

    def item(i, acc, who, addr, summary, ago_h, **kw):
        base = {
            "id": i, "kind": "inbox", "thread_id": "t" + i, "account_key": acc, "account_name": NAME[acc],
            "from_name": who, "from_addr": addr, "subject": kw.pop("subject", summary[:40]),
            "summary": summary, "received": int(now - ago_h * H), "relevant": True,
            "needs_reply": False, "urgency": 1, "opportunity": False, "action": "", "deadline": "",
            "body": kw.pop("body", summary), "draft_text": "", "draft_id": "",
            "send_from": ADDRESS[acc], "send_name": "Raza",
            "reply_meta": {"from_addr": addr, "subject": summary[:40], "thread_id": "t" + i,
                           "message_id": f"<{i}@example>", "references": "",
                           "to": [ADDRESS[acc]], "cc": kw.pop("cc", [])},
        }
        base.update(kw)
        base["internal_date"] = base["received"] * 1000
        return base

    items = [
        # ---- Work
        item("r1", "ud", "Dr. Helen Carter", "hcarter@example.edu",
             "Free in her office until 5 PM today, or on Zoom tomorrow at 2 PM.", 0.9,
             subject="Quick chat about the report?", needs_reply=True, urgency=3, deadline="Today 5 PM",
             alerted_at=int(now - 0.75 * H),
             body="Hi Raza,\n\nI'm in my office until 5 PM today if you'd like to stop by. Otherwise I can do "
                  "tomorrow at 2 PM on Zoom. Let me know which works.\n\nHelen",
             draft_text="Dear Dr. Carter,\n\nThank you for getting back to me so quickly. [I can stop by before "
                        "5 today / Tomorrow at 2 PM on Zoom works for me].\n\nBest regards,\nRaza"),
        item("t1", "ud", "IT Services", "it@example.edu",
             "Annual security awareness training assigned.", 8, action="Complete security training (5 min).",
             deadline=day(14, "%b %d")),
        item("f2", "ud", "Office Social Committee", "social@example.edu",
             "Free coffee and bagels in the lounge at 9 AM.", 5, urgency=0),
        {
            "id": "w-s1", "kind": "waiting", "thread_id": "ts1", "account_key": "ud", "account_name": "Work",
            "from_name": "Ana Ruiz", "from_addr": "ana.ruiz@example.edu", "subject": "Draft report, section 2",
            "summary": "Feedback on section 2 of the draft report", "received": int(now - 4 * 24 * H),
            "internal_date": int(now - 4 * 24 * H) * 1000, "follow_up_at": int(now - 24 * H),
            "relevant": True, "needs_reply": False, "urgency": 1, "opportunity": False,
            "action": "Follow up: no reply in 4 days (draft ready)", "deadline": "", "tab": "waiting",
            "body": "Hi Ana,\n\nCould you take a look at section 2 of the draft report when you have a moment?",
            "draft_text": "Hi Ana,\n\nJust checking in on section 2. No rush; any comments by [date] would be "
                          "very helpful.\n\nBest,\nRaza",
            "followup_drafted": True, "draft_id": "", "send_from": ADDRESS["ud"], "send_name": "Raza",
            "reply_meta": {"from_addr": "ana.ruiz@example.edu", "subject": "Draft report, section 2",
                           "thread_id": "ts1", "to": ["ana.ruiz@example.edu"], "cc": []},
        },
        # ---- Personal
        item("r2", "gmail", "Daniel Brooks", "dbrooks@example.org",
             "Asks whether the workshop slides can be shared by Friday.", 3,
             subject="Workshop slides", needs_reply=True, urgency=2, deadline="Fri", calendar_added=True,
             body="Hi Raza,\n\nGreat talk last week! Could you share the slides by Friday so we can post "
                  "them with the recording?\n\nThanks,\nDaniel",
             draft_text="Hi Daniel,\n\nThank you, glad it was useful. [Yes, I'll send the slides by Friday / "
                        "I'll need until ___].\n\nBest,\nRaza"),
        item("o1", "gmail", "Research Jobs Digest", "alerts@example.org",
             "Remote research analyst role: causal inference with survey and satellite data.", 4,
             opportunity=True, urgency=2, deadline="Apply by " + day(9, "%b %d"), addressed=False),
        item("t2", "gmail", "Study Registry", "support@example.org",
             "A co-author submitted edits to your study registration.", 7,
             action="Approve the registration edits.", deadline=day(3, "%a %b %d"), calendar_added=True),
        item("f3", "gmail", "City Library", "notices@example.org",
             "Your borrowed book is due next week.", 20, urgency=0),
        # ---- Alumni
        item("r3", "lums", "Sara Ahmed", "sara.ahmed@example.edu",
             "Would you mentor two current students this term?", 6,
             subject="Alumni mentorship", needs_reply=True, deadline="Wed",
             cc=["alumni.office@example.edu"],
             body="Dear Raza,\n\nOur alumni mentorship program is matching mentors for this term. Would you be "
                  "open to mentoring two students (about one call a month)?\n\nWarm regards,\nSara",
             draft_text="Dear Sara,\n\nThank you for thinking of me. [I'd be happy to mentor two students this "
                        "term].\n\nBest regards,\nRaza"),
        item("o2", "lums", "Policy Research Lab", "careers@example.org",
             "Paid 3-month research role on climate shocks and schooling.", 9,
             opportunity=True, deadline="Apply by " + day(15, "%b %d"), addressed=True),
        item("f1", "lums", "Alumni Office", "alumni@example.edu",
             "Homecoming weekend schedule is out.", 11, urgency=0),
        # Already replied: hidden everywhere (shows that replied threads disappear)
        item("x1", "gmail", "Old Thread", "old@example.org", "Replied already.", 2, needs_reply=True,
             replied=True),
    ]

    def ev(days, hour, minute, kind, title, acc, remind):
        start = (today + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        end = start + timedelta(minutes=15 if kind in ("deadline", "application") else 60)
        return {"kind": kind, "title": title, "start": start.isoformat(), "end": end.isoformat(),
                "account_key": acc, "remind": remind, "thread_id": "x", "item_id": "x"}

    events = {"calendar_id": "demo", "by_key": {
        "a": ev(1, 14, 0, "meeting", "Meeting: Zoom with Dr. Carter", "ud", "Reminders: 1 hour before"),
        "b": ev(3, 8, 0, "deadline", "Due: Workshop slides to Daniel", "gmail", "Reminders: morning of"),
        "c": ev(6, 8, 0, "deadline", "Due: Reply on alumni mentorship", "lums",
                "Reminders: " + day(3, "%a %b %d") + " and morning of"),
        "d": ev(9, 8, 0, "application", "Apply: Research analyst role", "gmail",
                "Reminders: " + day(6, "%a %b %d") + " and morning of"),
    }}
    stats = {
        "last_check": int(now - 6 * 60),
        "monthly": {today.strftime("%Y-%m"): {"cost": 0.42}},
        "skipped": [[int(now - H), "gmail"]] * 18 + [[int(now - H), "ud"]] * 6 + [[int(now - H), "lums"]] * 10,
        "accounts": [{"key": k, "name": NAME[k], "address": ADDRESS[k]} for k in ("gmail", "ud", "lums")],
    }
    actions = {"items": {}, "draft_edits": {}, "draft_ids": {}, "senders": {"muted": [], "calm": [], "always": []}}
    return {"items": {i["id"]: i for i in items}, "events": events, "stats": stats, "actions": actions}
