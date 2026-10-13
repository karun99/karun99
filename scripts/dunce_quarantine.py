#!/usr/bin/env python3
"""Dunce quarantine: label and comment on a PR that failed the consensus gate."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bio import pr_number, state  # noqa: E402

API = "https://api.github.com"


def gh(path: str, method: str = "GET", body: dict | None = None):
    request = urllib.request.Request(f"{API}{path}", method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "dunce")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, data=data, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        return {"__http_error__": err.code}
    except Exception:
        return {"__http_error__": -1}


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    number = pr_number()
    snap = state()
    dunce = snap.get("dunce", {})
    jataka = snap.get("jataka", {})
    reason = "; ".join(dunce.get("failures", []) or [jataka.get("reason", "guardrail fail")])

    labels = ["dunce:quarantined"]
    if jataka.get("priority"):
        labels.append(f"prio/{jataka['priority']}")

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not repo or not number or not token:
        print(f"[dunce] (dry-run) quarantine PR #{number} labels={labels} reason={reason}")
        return 0

    gh(f"/repos/{repo}/issues/{number}/labels", "POST", {"labels": labels})
    gh(f"/repos/{repo}/issues/{number}/comments", "POST",
       {"body": f"🔥 **Dunce quarantine** — autonomous merge halted.\n\n{reason}"})
    print(f"[dunce] quarantined PR #{number}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
