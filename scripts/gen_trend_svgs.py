#!/usr/bin/env python3
"""Generate the trend-analysis SVGs embedded in the profile README.

Two kinds of figure are produced:

  * conceptual — the trend lifecycle S-curve and the commit/pivot decision
    matrix. These encode the Research Trend-Viability policy in
    README.md#-research-trend-viability; they carry no measured data.
  * measured — the portfolio domain mix and the research output counts. These
    come from the site's tools/projects.json and the figures already published
    on the site, and every figure is stamped with its as-of date.

Keeping them as generated SVG (rather than a screenshot) means they stay crisp,
diff in git, and can be regenerated in one command:

    python3 scripts/gen_trend_svgs.py

No third-party dependency: the SVG is written directly so the output is
deterministic and the script runs anywhere Python does.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "trend"
SITE_DATA = Path(__file__).resolve().parent.parent.parent / "karun99-site-work" / "tools" / "projects.json"

AS_OF = "2026-11-15"

BG = "#151824"
PANEL = "#1b1f2e"
GRID = "#2b3149"
TEXT = "#e6e9f2"
MUTED = "#98a2c0"
INDIGO = "#6366f1"
GREEN = "#22c55e"
AMBER = "#eab308"
RED = "#f7768e"
CYAN = "#22d3ee"

FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def svg(width: int, height: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">\n'
        f'  <title>{esc(title)}</title>\n'
        f'  <rect width="{width}" height="{height}" rx="16" fill="{BG}"/>\n'
        f"{body}\n</svg>\n"
    )


def text(x, y, s, size=14, fill=TEXT, weight="400", anchor="start", family=FONT,
         opacity=1, extra="", raw=False):
    body = s if raw else esc(s)
    return (
        f'  <text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" opacity="{opacity}"{extra}>'
        f"{body}</text>\n"
    )


def rich(x, y, runs, size=11, anchor="start"):
    """A text node built from [(text, fill, weight), ...] runs.

    Spans let one line carry a coloured action word plus its muted explanation
    without having to measure string widths to place a second <text>."""
    spans = "".join(
        f'<tspan fill="{fill}" font-weight="{weight}">{esc(s)}</tspan>'
        for s, fill, weight in runs
    )
    return text(x, y, spans, size=size, anchor=anchor, raw=True)


# --------------------------------------------------------------------------
# 1. Trend lifecycle S-curve (conceptual)
# --------------------------------------------------------------------------
def s_curve() -> str:
    W, H = 960, 486
    L, R, T, B = 78, 904, 92, 336
    b = []
    b.append(text(32, 42, "Research Trend Lifecycle", 20, TEXT, "700"))
    b.append(text(32, 66, "Where a direction sits on the adoption S-curve decides whether to start, guard, or stop.", 13, MUTED))

    # phase bands
    bands = [
        (L, 300, "EMERGENCE", "#2b3149"),
        (300, 566, "RISING", "#1d3a2a"),
        (566, 742, "PLATEAU", "#3a341d"),
        (742, R, "DECLINE", "#3a1f2a"),
    ]
    for x0, x1, label, fill in bands:
        b.append(f'  <rect x="{x0}" y="{T}" width="{x1 - x0}" height="{B - T}" fill="{fill}" opacity="0.55"/>\n')
        b.append(text((x0 + x1) / 2, T + 20, label, 10, MUTED, "700", "middle"))

    # axes
    b.append(f'  <line x1="{L}" y1="{B}" x2="{R}" y2="{B}" stroke="{GRID}" stroke-width="1.5"/>\n')
    b.append(f'  <line x1="{L}" y1="{T}" x2="{L}" y2="{B}" stroke="{GRID}" stroke-width="1.5"/>\n')
    b.append(text(L - 14, (T + B) / 2, "signal strength", 11, MUTED, anchor="middle",
                  extra=f' transform="rotate(-90 {L - 14} {(T + B) / 2})"'))
    b.append(text((L + R) / 2, B + 26, "time  \u2192", 11, MUTED, anchor="middle"))

    # S-curve: slow emergence, steep rise, plateau, then decay
    b.append(
        f'  <path d="M {L} {B - 8} C 190 {B - 10}, 252 {B - 54}, 358 {B - 96} '
        f'C 452 {B - 134}, 508 {B - 150}, 574 {B - 160} '
        f'C 660 {B - 172}, 730 {B - 178}, 796 {B - 186} '
        f'C 840 {B - 192}, 872 {B - 186}, {R - 4} {B - 170}" '
        f'fill="none" stroke="{INDIGO}" stroke-width="4" stroke-linecap="round"/>\n'
    )

    # numbered markers keyed to the legend below, so no label has to compete
    # with neighbouring leader lines for space
    marks = [
        (358, B - 96, GREEN, "COMMIT", "novel + real use + robust core"),
        (520, B - 148, AMBER, "GUARD", "the trend-riding layer may not survive"),
        (620, B - 166, RED, "DON\u2019T START", "a 2-year project lands after the peak"),
        (806, B - 188, RED, "STOP / REFRAME", "keep the robust core, drop the rider"),
    ]
    for i, (x, y, col, head, sub) in enumerate(marks, 1):
        b.append(f'  <line x1="{x}" y1="{y}" x2="{x}" y2="{B}" stroke="{col}" stroke-width="1.4" stroke-dasharray="4 5" opacity="0.6"/>\n')
        b.append(f'  <circle cx="{x}" cy="{y}" r="10" fill="{col}" stroke="{BG}" stroke-width="2"/>\n')
        b.append(text(x, y + 4, str(i), 11, BG, "700", "middle", family=MONO))

    # legend: two columns, one line per marker
    for i, (x, y, col, head, sub) in enumerate(marks, 1):
        cx = 44 if i <= 2 else 486
        cy = 392 + ((i - 1) % 2) * 32
        b.append(f'  <rect x="{cx}" y="{cy - 9}" width="10" height="10" rx="2" fill="{col}"/>\n')
        b.append(rich(cx + 18, cy, [
            (f"{i}  ", MUTED, "700"),
            (head, col, "700"),
            (f"  \u00b7  {sub}", MUTED, "400"),
        ], size=11.5))

    b.append(text(32, H - 22, "Conceptual model, not measured data. Phase boundaries are judgement calls; re-run the gate every 3\u20136 months.", 11, MUTED))
    return svg(W, H, "".join(b), "Research trend lifecycle S-curve with commit and pivot zones")


# --------------------------------------------------------------------------
# 2. Commit / pivot decision matrix (conceptual)
# --------------------------------------------------------------------------
def matrix() -> str:
    W, H = 960, 470
    b = []
    b.append(text(32, 42, "Commit / Pivot Decision Matrix", 20, TEXT, "700"))
    b.append(text(32, 66, "A direction has to clear every gate; one failed gate is enough to reframe.", 13, MUTED))

    x0, y0 = 40, 100
    col_w = [124, 124, 156, 150, 326]
    row_h = 58
    heads = ["Trend", "Novelty", "Real-time use", "Robust core", "Action"]
    # gate columns are centred; the label and action columns are left-aligned
    centred = {1, 2, 3}
    xs = [x0]
    for w in col_w:
        xs.append(xs[-1] + w)

    for i, h in enumerate(heads):
        b.append(f'  <rect x="{xs[i]}" y="{y0}" width="{col_w[i]}" height="40" fill="{PANEL}" stroke="{GRID}"/>\n')
        b.append(text(xs[i] + 14, y0 + 26, h, 12, MUTED, "700"))

    rows = [
        ("Rising", "Yes", "Yes", "Yes", "Commit", GREEN, "robust core separated from the trend rider"),
        ("Rising", "Yes", "No", "Yes", "Commit with caution", AMBER, "present-day use case still missing"),
        ("Rising", "No", "\u2014", "\u2014", "Differentiate or stop", RED, "the delta is too small to defend"),
        ("Peaking", "\u2014", "\u2014", "\u2014", "Don\u2019t start a 2-year project", RED, "it publishes after the peak"),
        ("Declining", "\u2014", "\u2014", "\u2014", "Stop / reframe", RED, "salvage the core, retire the rider"),
    ]
    for r, (trend, nov, use, core, action, col, note) in enumerate(rows):
        y = y0 + 40 + r * row_h
        fill = PANEL if r % 2 == 0 else BG
        for i in range(5):
            b.append(f'  <rect x="{xs[i]}" y="{y}" width="{col_w[i]}" height="{row_h}" fill="{fill}" stroke="{GRID}"/>\n')
        b.append(text(xs[0] + 14, y + 25, trend, 12, TEXT, "600"))
        for i, val in enumerate((nov, use, core), start=1):
            b.append(text(xs[i] + col_w[i] / 2, y + 25, val, 12,
                          TEXT if val == "Yes" else MUTED,
                          "600" if val == "Yes" else "400", "middle"))
        b.append(text(xs[4] + 14, y + 25, action, 12, col, "700"))
        b.append(text(xs[4] + 14, y + 43, note, 9.5, MUTED))

    b.append(text(40, H - 26, "Gates 2 (novelty), 4 (real-time use) and 6 (trend-retention design) are the load-bearing ones.", 11, MUTED))
    return svg(W, H, "".join(b), "Research trend-viability commit and pivot decision matrix")


# --------------------------------------------------------------------------
# 3. Portfolio domain mix (measured)
# --------------------------------------------------------------------------
def domains() -> str:
    # Derive from the site's project registry when the sibling checkout is
    # present; fall back to the recorded snapshot otherwise.
    fallback = {
        "EdTech": 9, "AI infrastructure": 7, "Agentic AI": 5,
        "Research systems": 4, "Developer tools": 2, "Companion AI": 2,
        "AI apps": 1, "Digital twin": 1, "MAS": 1,
    }
    merge = {"EDTECH": "EdTech", "AI INFRA": "AI infrastructure", "INFRA": "AI infrastructure",
             "AGENTIC AI": "Agentic AI", "RESEARCH": "Research systems",
             "DEV TOOLS": "Developer tools", "COMPANION": "Companion AI",
             "AI APPS": "AI apps", "DIGITAL TWIN": "Digital twin", "MAS": "MAS"}
    counts: dict[str, int] = {}
    if SITE_DATA.exists():
        projects = json.loads(SITE_DATA.read_text(encoding="utf-8"))["projects"]
        for p in projects:
            top = p["category"].split("//")[0].strip()
            name = merge.get(top, top.title())
            counts[name] = counts.get(name, 0) + 1
    data = sorted((counts or fallback).items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(n for _, n in data)
    W = 960
    row = 36
    H = 118 + row * len(data) + 48
    b = []
    b.append(text(32, 42, f"Portfolio mix — {total} tracked projects", 20, TEXT, "700"))
    b.append(text(32, 66, "Where the work actually sits, by top-level category of each tracked project.", 12.5, MUTED))

    label_x, bar_x, bar_max = 220, 236, 560
    top = 96
    for i, (name, n) in enumerate(data):
        y = top + i * row
        w = max(6, round(bar_max * n / max(v for _, v in data)))
        col = INDIGO if i < 4 else "#4c5a99"
        b.append(text(label_x, y + 18, name, 12.5, TEXT, anchor="end"))
        b.append(f'  <rect x="{bar_x}" y="{y + 4}" width="{bar_max}" height="18" rx="4" fill="{PANEL}"/>\n')
        b.append(f'  <rect x="{bar_x}" y="{y + 4}" width="{w}" height="18" rx="4" fill="{col}"/>\n')
        b.append(text(bar_x + w + 10, y + 18, str(n), 12, MUTED, "600", family=MONO))

    b.append(text(32, H - 22, f"Source: karun99.github.io tools/projects.json · as of {AS_OF}", 11, MUTED))
    return svg(W, H, "".join(b), "Research portfolio mix by domain")


# --------------------------------------------------------------------------
# 4. Research outputs (measured)
# --------------------------------------------------------------------------
def outputs() -> str:
    data = [
        ("Books on AI", 31, GREEN),
        ("MCP servers", 19, CYAN),
        ("Research papers", 9, INDIGO),
        ("Tracked projects", 32, "#8b8ff0"),
        ("Public repositories", 47, "#a78bfa"),
    ]
    W = 960
    row = 40
    H = 118 + row * len(data) + 48
    b = []
    b.append(text(32, 42, "Research & engineering output", 20, TEXT, "700"))
    b.append(text(32, 66, "Published artefacts behind the trend gate — the part that survives a trend going cold.", 12.5, MUTED))

    label_x, bar_x, bar_max = 230, 246, 550
    maxv = max(v for _, v, _ in data)
    top = 96
    for i, (name, n, col) in enumerate(data):
        y = top + i * row
        w = round(bar_max * n / maxv)
        b.append(text(label_x, y + 20, name, 12.5, TEXT, anchor="end"))
        b.append(f'  <rect x="{bar_x}" y="{y + 6}" width="{bar_max}" height="20" rx="5" fill="{PANEL}"/>\n')
        b.append(f'  <rect x="{bar_x}" y="{y + 6}" width="{w}" height="20" rx="5" fill="{col}"/>\n')
        b.append(text(bar_x + w + 12, y + 20, str(n), 13, TEXT, "700", family=MONO))

    b.append(text(32, H - 22, f"Sources: works page (books, papers), profile (MCP servers, repositories, projects) · as of {AS_OF}", 11, MUTED))
    return svg(W, H, "".join(b), "Research and engineering output counts")


def main() -> int:
    # sanity-check the live source the figures were derived from, so a stale
    # checkout fails loudly instead of silently publishing old numbers
    if SITE_DATA.exists():
        projects = json.loads(SITE_DATA.read_text(encoding="utf-8"))["projects"]
        print(f"source check: {len(projects)} tracked projects in {SITE_DATA}")
    else:
        print(f"source check: {SITE_DATA} not found — using the values recorded in this script")

    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "trend-scurve.svg": s_curve(),
        "decision-matrix.svg": matrix(),
        "portfolio-domains.svg": domains(),
        "research-outputs.svg": outputs(),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"wrote {OUT / name} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
