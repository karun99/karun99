#!/usr/bin/env python3
"""Sahaja guardrail: enforce minimal-force effort budget on the proposed update."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bio import alert_context, load_config, output, save_state, state  # noqa: E402


def main() -> int:
    config = load_config()
    sahaja = config.get("sahaja", {})
    limits = sahaja.get("constraints", {})
    alert = alert_context()

    diff_lines = int(alert.get("diff_lines") or 0)
    files = int(alert.get("files_touched") or 0)
    method = alert.get("method") or "native_dependabot_update"
    rollback = bool(alert.get("rollback_plan"))

    failures: list[str] = []

    if limits.get("max_diff_lines") and diff_lines > int(limits["max_diff_lines"]):
        failures.append(f"SAH-001 diff {diff_lines} > {limits['max_diff_lines']}")
    if limits.get("max_files_touched") and files > int(limits["max_files_touched"]):
        failures.append(f"SAH-001 files {files} > {limits['max_files_touched']}")
    if limits.get("no_new_dependencies") and alert.get("new_dependencies"):
        failures.append("SAH-001 new dependency introduced")

    order = [m for m in sahaja.get("preference_order", []) if isinstance(m, str)]
    if method == "fork_with_backport" and order[:1] == ["native_dependabot_update"]:
        failures.append("SAH-002 fork while native update available")

    if method in ("fork_with_backport", "pinned_version_bump") and not rollback:
        failures.append("SAH-003 rollback plan required")

    verdict = "fail" if failures else "pass"
    current = state()
    current["sahaja"] = {"verdict": verdict, "failures": failures}
    save_state(current)

    output("verdict", verdict)
    output("failures", failures)
    print(f"[sahaja] verdict={verdict} failures={failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
