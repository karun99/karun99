#!/usr/bin/env python3
"""Dunce post-mortem: write a lessons-learned note and feed it back to Jataka."""

from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bio import ROOT, state  # noqa: E402

LESSONS = os.path.join(ROOT, ".dunce", "lessons")


def main() -> int:
    snap = state()
    jataka = snap.get("jataka", {})
    dunce = snap.get("dunce", {})

    verdict = dunce.get("verdict", "pass")
    priority = jataka.get("priority", "P3")
    if verdict == "pass" and priority not in ("P0", "P1"):
        print("[dunce] no post-mortem required")
        return 0

    lines = [
        f"# Lessons Learned — {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"- **Priority:** {priority}",
        f"- **Verdict:** {verdict}",
        f"- **Reason:** {jataka.get('reason', 'n/a')}",
        "",
        "## Root cause",
        jataka.get("reason", "n/a"),
        "",
        "## Affected versions",
        "- (populate from the alert / SBOM baseline)",
        "",
        "## Detection and response timeline",
        f"- gate verdict: {verdict}",
        f"- confidence: {dunce.get('confidence', 'n/a')}",
        "",
        "## Preventive measures",
        "- Feed this incident into Jataka precedent sources (audit/security_incidents.db)",
        "",
        "## Lessons learned",
    ]
    lines += [f"- {failure}" for failure in dunce.get("failures", [])] or ["- (none recorded)"]

    os.makedirs(LESSONS, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(LESSONS, f"{stamp}.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"[dunce] post-mortem written: {os.path.relpath(path, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
