"""The shared notebook between the agent and the dashboard: a few JSON files in the
private GitHub repo `email-agent-data`.

  items.json    written by the agent    summaries, drafts, deadlines, replied flags
  events.json   written by the agent    calendar entries it created
  stats.json    written by the agent    cost, filtered counts, last check, accounts
  actions.json  written by the dashboard  done / snoozed, edited drafts, sender rules

Each file has exactly one writer, so the two programs never overwrite each other.
Set DATA_LOCAL_DIR to use a plain folder instead of GitHub (testing, local runs).
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

API = "https://api.github.com"
DEFAULTS = {
    "items.json": {},
    "events.json": {"calendar_id": "", "by_key": {}},
    "stats.json": {},
    "actions.json": {"items": {}, "draft_edits": {}, "draft_ids": {},
                     "senders": {"muted": [], "calm": [], "always": []}},
}


class DataStoreError(RuntimeError):
    pass


class DataStore:
    def __init__(self, repo: str = "", token: str = "", local_dir: str = "", branch: str = "main"):
        self.repo, self.token, self.branch = repo, token, branch
        self.local = Path(local_dir) if local_dir else None
        self._sha: dict[str, str | None] = {}
        if not self.local and not (repo and token):
            raise DataStoreError("no data repo configured")

    # ------------------------------------------------------------- helpers
    def _headers(self, raw: bool = False) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _url(self, name: str) -> str:
        return f"{API}/repos/{self.repo}/contents/{name}"

    @staticmethod
    def _default(name: str):
        return json.loads(json.dumps(DEFAULTS.get(name, {})))

    # ---------------------------------------------------------------- read
    def load(self, name: str):
        if self.local:
            path = self.local / name
            if not path.exists():
                return self._default(name)
            return _merge_defaults(name, json.loads(path.read_text(encoding="utf-8") or "{}"))

        r = requests.get(self._url(name), headers=self._headers(), params={"ref": self.branch}, timeout=30)
        if r.status_code == 404:
            self._sha[name] = None
            return self._default(name)
        if r.status_code in (401, 403):
            raise DataStoreError(f"GitHub refused access to the data repo ({r.status_code}). "
                                 "The DATA_REPO_TOKEN may have expired.")
        r.raise_for_status()
        meta = r.json()
        self._sha[name] = meta.get("sha")
        if meta.get("content"):
            text = base64.b64decode(meta["content"]).decode("utf-8")
        else:  # files over 1 MB come without inline content
            r2 = requests.get(self._url(name), headers=self._headers(raw=True),
                              params={"ref": self.branch}, timeout=60)
            r2.raise_for_status()
            text = r2.text
        return _merge_defaults(name, json.loads(text or "{}"))

    # --------------------------------------------------------------- write
    def save(self, name: str, data, message: str = "") -> None:
        text = json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True)
        if self.local:
            self.local.mkdir(parents=True, exist_ok=True)
            (self.local / name).write_text(text, encoding="utf-8")
            return
        if name not in self._sha:
            self.load(name)
        body = {
            "message": message or f"update {name}",
            "content": base64.b64encode(text.encode("utf-8")).decode(),
            "branch": self.branch,
        }
        if self._sha.get(name):
            body["sha"] = self._sha[name]
        r = requests.put(self._url(name), headers=self._headers(), json=body, timeout=60)
        if r.status_code in (409, 422):
            raise DataStoreConflict(name)
        if r.status_code in (401, 403):
            raise DataStoreError(f"GitHub refused the write to {name} ({r.status_code}). "
                                 "Check DATA_REPO_TOKEN has Contents: Read and write.")
        r.raise_for_status()
        self._sha[name] = r.json()["content"]["sha"]

    def overwrite(self, name: str, data, message: str = "", attempts: int = 4) -> None:
        """Save a file only the agent writes (items, events, stats). If GitHub briefly
        rejects the write (e.g. the dashboard committed at the same moment), fetch the
        latest version id and try again; our copy is the one that should win."""
        for n in range(attempts):
            try:
                self.save(name, data, message)
                return
            except DataStoreConflict:
                time.sleep(1.0 * (n + 1))
                self._sha.pop(name, None)      # save() re-reads the current version id
        raise DataStoreError(f"could not save {name} after {attempts} tries")

    def update(self, name: str, change, message: str = "", attempts: int = 4):
        """Read-modify-write that survives someone else saving in between."""
        for n in range(attempts):
            data = self.load(name)
            change(data)
            try:
                self.save(name, data, message)
                return data
            except DataStoreConflict:
                time.sleep(0.5 * (n + 1))
        raise DataStoreError(f"could not save {name} after {attempts} tries")


class DataStoreConflict(DataStoreError):
    pass


def _merge_defaults(name: str, data):
    base = DataStore._default(name)
    if isinstance(base, dict) and isinstance(data, dict):
        for k, v in base.items():
            data.setdefault(k, v)
            if isinstance(v, dict) and isinstance(data[k], dict):
                for k2, v2 in v.items():
                    data[k].setdefault(k2, v2)
    return data


# ------------------------------------------------------------------ shared logic
# Used by both the agent and the dashboard, so they always agree on what is "open".

def item_tab(item: dict) -> str:
    if item.get("kind") == "waiting":
        return "waiting"
    if item.get("needs_reply"):
        return "reply"
    if item.get("opportunity"):
        return "opp"
    if item.get("action"):
        return "todo"
    return "fyi"


def is_open(item: dict, actions: dict, now: float | None = None) -> bool:
    """False if you replied, marked it done, or snoozed it into the future."""
    now = now or time.time()
    if item.get("replied") or item.get("resolved"):
        return False
    act = (actions.get("items") or {}).get(item["id"])
    if not act:
        return True
    if act.get("status") in ("done", "sent"):
        return False
    if act.get("status") == "snoozed" and act.get("until", 0) > now:
        return False
    return True
