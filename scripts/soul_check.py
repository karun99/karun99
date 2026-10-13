#!/usr/bin/env python3
"""Soul guardrail: enforce SECURITY.md intent invariants (license, lockfiles, pins)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bio import alert_context, load_config, output, save_state, state  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock",
             "Pipfile.lock", "requirements.txt", "uv.lock", "Cargo.lock", "go.sum")
MANIFESTS = ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Pipfile", "requirements.in")


def find(names: tuple[str, ...]) -> list[str]:
    found = []
    for base, _dirs, files in os.walk(ROOT):
        if ".git" in base:
            continue
        for name in files:
            if name in names:
                found.append(os.path.relpath(os.path.join(base, name), ROOT))
    return found


def main() -> int:
    config = load_config()
    soul = config.get("soul", {})
    inv = soul.get("invariants", {})
    alert = alert_context()

    failures: list[str] = []
    notes: list[str] = []

    license_name = (alert.get("license") or "").strip()
    allow = inv.get("license_allowlist", [])
    deny = inv.get("forbidden_licenses", [])
    if license_name:
        if license_name in deny:
            failures.append(f"SOUL-001 forbidden license {license_name}")
        elif allow and license_name not in allow:
            failures.append(f"SOUL-001 license {license_name} not in allowlist")
        else:
            notes.append(f"license ok ({license_name})")

    if inv.get("lockfiles_required"):
        manifests = find(MANIFESTS)
        locks = find(LOCKFILES)
        if manifests and not locks:
            failures.append(f"SOUL-004 lockfile required for {manifests}")

    if inv.get("pinned_direct_deps") and alert.get("direct") and not alert.get("pinned"):
        failures.append("SOUL-004 unpinned direct dependency")

    if alert.get("new_high_or_critical"):
        failures.append("SOUL-003 posture regression: new high/critical")

    if alert.get("unmaintained"):
        notes.append("SOUL-005 unmaintained package flagged for migration issue")

    verdict = "fail" if failures else "pass"
    current = state()
    current["soul"] = {"verdict": verdict, "failures": failures, "notes": notes}
    save_state(current)

    output("verdict", verdict)
    output("failures", failures)
    print(f"[soul] verdict={verdict} failures={failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
