"""Shared helpers for the BIO-inspired audit scripts.

Per BIO_AUDIT.md maintainer notes, all behavior is driven by the YAML blocks
embedded in BIO_AUDIT.md — the scripts read their configuration from there.
"""

from __future__ import annotations

import json
import os

try:
    import yaml
except ImportError:  # pragma: no cover - handled at call sites
    yaml = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(os.path.realpath(__file__))))
BIO_AUDIT = os.path.join(ROOT, "BIO_AUDIT.md")
STATE_FILE = os.path.join(ROOT, ".bio", "state.json")
HISTORY = os.path.join(ROOT, "audit", "dependabot_alert_history")

PRIORITY_ORDER = ["P3", "P2", "P1", "P0"]


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _iter_blocks():
    if yaml is None:
        raise SystemExit("PyYAML is required. Install it with: pip install pyyaml")
    with open(BIO_AUDIT, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    inside, buf = False, []
    for line in lines:
        if not inside and line.strip() == "```yaml":
            inside, buf = True, []
            continue
        if inside and line.strip() == "```":
            inside = False
            try:
                data = yaml.safe_load("\n".join(buf))
            except yaml.YAMLError:
                continue
            if isinstance(data, dict):
                yield data
            continue
        if inside:
            buf.append(line)


def load_config() -> dict:
    """Merge every top-level mapping in BIO_AUDIT.md into one config dict."""
    merged: dict = {}
    for block in _iter_blocks():
        for key, value in block.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
    return merged


def load(path: str) -> dict:
    """Load a JSON document, returning {} when missing or malformed."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def state() -> dict:
    return load(STATE_FILE)


def save_state(data: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def output(name: str, value) -> None:
    """Emit a GitHub Actions step output and echo it for local runs."""
    text = value if isinstance(value, str) else json.dumps(value)
    print(f"{name}={text}")
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={text}\n")


def append_history(record: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def strongest_priority(*priorities: str) -> str:
    best = "P3"
    for priority in priorities:
        if priority in PRIORITY_ORDER and PRIORITY_ORDER.index(priority) > PRIORITY_ORDER.index(best):
            best = priority
    return best


def pr_number():
    """Best-effort PR number from the Actions event payload or environment."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        pull = data.get("pull_request") or {}
        number = data.get("number") or pull.get("number")
        if number:
            return int(number)
    raw = os.environ.get("PR_NUMBER")
    return int(raw) if raw and raw.isdigit() else None


def alert_context() -> dict:
    """Alert under audit: env JSON, else .bio/alert_context.json, else empty."""
    raw = os.environ.get("ALERT_CONTEXT")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return load(os.path.join(ROOT, ".bio", "alert_context.json"))
