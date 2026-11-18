# Inbox Assistant: demo

A public demo of my AI email assistant, with **made-up emails only**. It is a static copy of
the real dashboard: same page code (`ui/view.py`), styles and scripts (`ui/static/`), with
`demo.js` standing in for the server. Every button works, but nothing is read from or sent to
any mailbox.

What the real assistant does:

- Reads new mail from three inboxes (personal, work, alumni) every few minutes.
- Uses Claude (Haiku) to sort each email: needs a reply, a task, an opportunity, or FYI.
  Newsletters and mass emails are filtered out.
- Sends a Telegram alert only for urgent things (an interview, a form with a deadline, someone
  writing directly and waiting on an answer); everything else waits for digests at 9 AM and 4 PM.
- Drafts replies; I edit them in the dashboard and press Send (30-second undo).
- Puts meetings and deadlines on Google Calendar with reminders 3 days before.
- Hides threads I've already replied to; one tap mutes or always-shows a sender.

Stack: Python, Claude API, Gmail and Google Calendar APIs, GitHub Actions, Telegram Bot API,
Shiny for Python on Google Cloud Run.

## Run it locally

```zsh
pip install -r requirements.txt
python build.py --serve        # then open http://localhost:8000
```

## Publishing

`.github/workflows/pages.yml` builds the site and publishes it on GitHub Pages on every push
and once a day (so the dates stay current). Settings → Pages → Source: **GitHub Actions**.
