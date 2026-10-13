#!/usr/bin/env python3
"""Dunce circuit breaker: aggregate guardrail verdicts into one consensus gate.

Verdict values: `pass` (safe to auto-merge), `hold` (retain, no merge, no
incident), `fail` (quarantine + post-mortem). DUN-001 confidence floor and a
P0 Jataka priority both force `fail`.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bio import ROOT, output, save_state, state  # noqa: E402

LOCK = os.path.join(ROOT, ".bio", "automation_lock.json")


def main() -> int:
    snap = state()
    verdicts = {
        name: snap.get(name, {}).get("verdict", "pass")
        for name in ("jataka", "soul", "sahaja")
    }
    priority = snap.get("jataka", {}).get("priority", "P3")

    if os.path.exists(LOCK):
        output("verdict", "fail")
        output("confidence", 0.0)
        print("[dunce] kill switch engaged — halting")
        return 0

    hard = [f"{name}:{value}" for name, value in verdicts.items() if value in ("fail", "block", "quarantine")]
    soft = [f"{name}:hold" for name, value in verdicts.items() if value == "hold"]

    if priority == "P0":
        hard.append("jataka:P0 (no autonomous merge)")

    confidence = round((len(verdicts) - len(hard)) / max(len(verdicts), 1), 2)
    if confidence < 0.75 and "jataka:P0 (no autonomous merge)" not in hard:
        hard.append(f"DUN-001 confidence {confidence} < 0.75")

    verdict = "fail" if hard else ("hold" if soft else "pass")

    snap["dunce"] = {"verdict": verdict, "confidence": confidence, "failures": hard, "priority": priority}
    save_state(snap)

    output("verdict", verdict)
    output("confidence", confidence)
    print(f"[dunce] verdict={verdict} confidence={confidence} failures={hard + soft}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
