#!/usr/bin/env python3
"""Jataka guardrail query: gate against precedent and assign a priority.

Reads the `jataka` block from BIO_AUDIT.md and classifies the alert under audit
(`.bio/alert_context.json` or $ALERT_CONTEXT) into a priority (P0–P3) plus a
guardrail verdict, then applies the matching `prio/Px` label to the PR.

Priority is the strongest triggered entry of jataka.priority_model (first match
wins); guardrail rules (JAT-001..004) can escalate (P0) or force quarantine/hold.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bio  # noqa: E402
from _bio import append_history, output, save_state, state, strongest_priority  # noqa: E402


def gh(path: str, method: str = "GET", body: dict | None = None):
    """Minimal GitHub REST call; returns error dict instead of raising."""
    request = urllib.request.Request(f"https://api.github.com{path}", method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "jataka-query")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, data=data, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        return {"__http_error__": err.code}
    except Exception:
        return {"__http_error__": -1}


def label_map(jataka: dict) -> dict:
    labels = jataka.get("priority_labels") or ["prio/P0", "prio/P1", "prio/P2", "prio/P3"]
    return {f"P{i}": label for i, label in enumerate(labels)}


def baseline_priority(model: list[dict], alert: dict) -> tuple[str, str]:
    """First model entry whose triggers match -> strongest priority (P0 first)."""
    cvss = float(alert.get("cvss") or 0)
    for entry in model:
        for trigger in entry.get("triggers", []):
            for key, value in trigger.items():
                if key == "cvss_score_gte" and cvss >= float(value):
                    return entry["id"], f"cvss {cvss} >= {value}"
                if key == "cisa_kev_match" and alert.get("cisa_kev"):
                    return entry["id"], "CISA KEV match"
                if key == "exploit_in_the_wild" and alert.get("exploit_in_the_wild"):
                    return entry["id"], "exploit in the wild"
                if key == "reintroduces_remediated_cve" and alert.get("reintroduces_remediated_cve"):
                    return entry["id"], "reintroduces a remediated CVE"
                if key == "similarity_gte" and float(alert.get("similarity") or 0) >= float(value):
                    return entry["id"], f"precedent similarity >= {value}"
                if key == "no_known_cve" and not alert.get("cvss"):
                    return entry["id"], "no known CVE"
    return "P3", "default maintenance"


def rule_fires(rule: dict, alert: dict) -> str | None:
    rule_id = rule.get("id")
    if rule_id == "JAT-001" and alert.get("reintroduces_remediated_cve"):
        return "karmic regression"
    if rule_id == "JAT-002" and float(alert.get("similarity") or 0) >= float(rule.get("threshold", 0.85)):
        return "precedent-harm similarity"
    if rule_id == "JAT-003" and alert.get("critical_path"):
        return "critical-path hold"
    if rule_id == "JAT-004" and alert.get("third_party_disclosure"):
        return "third-party disclosure window"
    return None


def verdict_for(actions: list[str]) -> str:
    joined = " ".join(actions)
    if "block" in joined:
        return "block"
    if "quarantine" in joined:
        return "quarantine"
    if "hold" in joined:
        return "hold"
    return "pass"


def apply_labels(labels: list[str]) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    number = _bio.pr_number()
    if not repo or not number or not token:
        print(f"[jataka] (dry-run) would label PR #{number} with {labels}")
        return
    result = gh(f"/repos/{repo}/issues/{number}/labels", "POST", {"labels": labels})
    print(f"[jataka] labeled PR #{number}: {labels} ({result})")


def main() -> int:
    config = _bio.load_config()
    jataka = config.get("jataka", {})
    alert = _bio.alert_context()

    priority, reason = baseline_priority(jataka.get("priority_model", []), alert)
    actions: list[str] = []

    for rule in jataka.get("rules", []):
        fired = rule_fires(rule, alert)
        if not fired:
            continue
        actions.append(rule.get("action", ""))
        priority = strongest_priority(priority, rule.get("priority", "P3"))
        reason = f"{reason}; {rule['id']} ({fired})"

    verdict = verdict_for(actions) if actions else "pass"
    label = label_map(jataka).get(priority, f"prio/{priority}")

    append_history({"alert": alert, "priority": priority, "verdict": verdict, "reason": reason})

    current = state()
    current["jataka"] = {"priority": priority, "verdict": verdict, "reason": reason}
    save_state(current)

    output("priority", priority)
    output("verdict", verdict)
    output("reason", reason)
    print(f"[jataka] priority={priority} verdict={verdict} reason={reason}")

    suffix = {"block": "jataka:block", "quarantine": "jataka:quarantine", "hold": "jataka:hold"}.get(verdict)
    apply_labels([label, suffix] if suffix else [label])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
