#!/usr/bin/env python3
"""TRL Tracker - real-time Technology Readiness Level validation.

Reads tools/trl/projects.json, scores each repository against a 9-level
TRL rubric using live GitHub signals, and rewrites the TRL section of the
profile README. Runs locally or as a scheduled GitHub Action.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
HERE = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
README = os.path.join(ROOT, "README.md")

# (min_score, level, name, description)
TRL_STAGES = [
    (0, 1, "Title", "Problem statement & repository established"),
    (11, 2, "Idea / Concept", "Approach, feasibility & design documented"),
    (23, 3, "Proof of Concept", "Core concept demonstrated with working code"),
    (36, 4, "Core Components", "Essential building blocks implemented"),
    (49, 5, "Integrated Prototype", "Components integrated into a runnable prototype"),
    (61, 6, "Validated Working System", "Automated validation & tests passing"),
    (71, 7, "Realistic Environment Demo", "Demonstrated in a realistic environment (CI/CD, containers, live demo)"),
    (79, 8, "Complete, Tested System", "Fully qualified, secured & deployment-ready"),
    (87, 9, "Operational Validation", "Proven in real-world production use"),
]

TRL_COLORS = ["6b7280", "6b7280", "f97316", "f97316", "eab308", "eab308", "22c55e", "22c55e", "8b5cf6"]
TRL_STARS = ["●", "●", "●●", "●●", "●●●", "●●●", "●●●●", "●●●●", "●●●●●"]

# Dependency manifests, matched on basename so nested layouts count.
MANIFEST_FILES = frozenset((
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "requirements.txt", "pipfile", "gemfile",
))

# Conventional entry-point filenames, matched on basename at any depth.
ENTRY_FILES = frozenset((
    "main.py", "__main__.py", "app.py", "cli.py", "index.js", "index.ts",
    "index.tsx", "index.html", "main.go", "main.rs", "manage.py", "server.js",
    "server.ts", "wsgi.py", "asgi.py",
))

# Conventional entry-point subpaths that are not literally named main/index.
ENTRY_PREFIXES = ("bin/", "cmd/", "pkg/main.go", "src/main.", "src/index.")

# Framework entry points: a Next.js App Router root layout is the file that
# bootstraps every route, exactly as main() does for a library.
FRAMEWORK_ENTRY_PREFIXES = ("app/layout.", "src/app/layout.")

# Lockfiles are concrete evidence of an installable, reproducible dependency
# graph. They stand in for repository size when judging code maturity, so a
# small complete app is not penalised for being small.
LOCK_FILES = frozenset((
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "poetry.lock", "pipfile.lock", "uv.lock", "cargo.lock", "go.sum",
    "composer.lock",
))

# Container definitions, matched on basename so nested paths (infra/Dockerfile)
# count. Variants are recognised explicitly rather than by a loose prefix, so
# that documentation such as docs/docker-compose-notes.md is not mistaken for a
# compose file.
DOCKER_FILES = frozenset(("dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"))
DOCKER_VARIANT_PREFIXES = ("docker-compose.", "compose.")

# Workflows that actually validate the code. Dependabot/pages automation and
# auxiliary jobs (security scanning, npm publishing, JOSS review) are separate
# operations: a red security scan or an unpublished release must not be scored
# as "the CI gate is failing".
CI_WORKFLOW_HINTS = frozenset((
    "ci", "test", "tests", "testing", "build", "builds", "lint",
    "linter", "check", "checks", "validate", "validation",
))


def workflow_tokens(workflow: dict) -> set[str]:
    """Return exact words from the workflow name and path."""
    value = f"{workflow.get('name') or ''} {workflow.get('path') or ''}".lower()
    return {token for token in re.split(r"[^a-z0-9]+", value) if token}


def is_ci_workflow(workflow: dict) -> bool:
    """True when a workflow is named for code validation or building."""
    path = (workflow.get("path") or "").lower()
    if path.startswith("dynamic/"):
        return False
    tokens = workflow_tokens(workflow)
    explicit_validation = tokens & {
        "ci", "test", "tests", "testing", "build", "builds", "lint",
        "linter", "validate", "validation",
    }
    if "security" in tokens and not explicit_validation:
        return False
    return bool(tokens & CI_WORKFLOW_HINTS)


def has_project_workflow(workflows: list[dict]) -> bool:
    """True if the repo defines a workflow for code validation or builds.

    GitHub's API always includes the implicit ``dynamic/`` Dependabot and Pages
    pipelines; security, release, and deployment workflows alone also do not
    establish a code-validation pipeline.
    """
    return any(is_ci_workflow(w) for w in workflows)


def is_ci_run(run: dict) -> bool:
    """True if the workflow run is a code-validation CI run.

    Ignores Dependabot/Pages ``dynamic`` runs and requires a validation/build
    token so an unrelated successful workflow cannot stand in for CI.
    """
    path = (run.get("path") or "").lower()
    if run.get("event") == "dynamic" or path.startswith("dynamic/"):
        return False
    return is_ci_workflow(run)


def ci_is_green(run_list: list[dict]) -> bool:
    """True when the most recent meaningful CI run succeeded.

    A successful deploy, release, or security scan is not evidence that code
    validation passed, so runs without a validation/build workflow name do not
    count as green.
    """
    ci_runs = [r for r in run_list
               if is_ci_run(r)
               and r.get("conclusion") not in (None, "cancelled", "skipped")]
    return bool(ci_runs) and ci_runs[0].get("conclusion") == "success"


def runs_for_default_branch(run_list: list[dict], branch: str) -> list[dict]:
    """Keep only runs whose head branch is the repository's default branch.

    Pull-request runs from Dependabot or a feature branch land in the same
    workflow-runs feed. Scoring "latest CI" from that feed made a failing bump
    PR look like the project's own CI was red on main.
    """
    return [r for r in run_list if r.get("head_branch") == branch]


def is_manifest_path(path: str) -> bool:
    """True if the repo-relative path is a dependency manifest at any depth."""
    return os.path.basename(path) in MANIFEST_FILES


def is_entry_path(path: str) -> bool:
    """True if the path is a conventional program entry point."""
    if os.path.basename(path) in ENTRY_FILES:
        return True
    if any(path.startswith(prefix) for prefix in ENTRY_PREFIXES):
        return True
    return any(path.startswith(prefix) for prefix in FRAMEWORK_ENTRY_PREFIXES)


def has_lockfile(paths) -> bool:
    """True if any path is a dependency lockfile at any depth."""
    return any(os.path.basename(path) in LOCK_FILES for path in paths)


def is_docker_path(path: str) -> bool:
    """True if the path is a container definition at any depth."""
    base = os.path.basename(path)
    if base in DOCKER_FILES:
        return True
    if base.startswith("dockerfile."):
        return True
    return base.startswith(DOCKER_VARIANT_PREFIXES) and base.endswith((".yml", ".yaml"))


TEST_DIR_SEGMENTS = frozenset(("test", "tests", "spec", "specs", "__tests__"))
TEST_FILE_SUFFIXES = (
    "_test.py", ".test.js", ".test.jsx", ".test.ts", ".test.tsx",
    ".spec.js", ".spec.jsx", ".spec.ts", ".spec.tsx",
)


def is_test_path(path: str) -> bool:
    """True if the path is a test file, at any depth.

    The old check only matched ``test/`` and ``tests/`` at the repository root,
    so a conventional nested layout such as ``api/tests/test_api.py`` or
    ``backend/pkg/foo_test.py`` scored as having no tests at all.
    """
    parts = path.split("/")
    if any(segment in TEST_DIR_SEGMENTS for segment in parts[:-1]):
        return True
    base = parts[-1]
    if base.startswith("test_") and base.endswith(".py"):
        return True
    return base.endswith(TEST_FILE_SUFFIXES)


def api(path: str, params: dict | None = None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "trl-tracker")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return {"__http_error__": e.code}
    except Exception:
        return {"__http_error__": -1}


def api_retry(path: str, params: dict | None = None, attempts: int = 3):
    """``api`` with a couple of retries for transient transport failures.

    A dropped connection used to look like an empty repository: the tree call
    returned an error dict, every file-layout signal became False, and the repo
    silently lost up to 14 points. Retrying turns a flaky read into a slow read
    instead of a wrong score.
    """
    result = None
    for _ in range(attempts):
        result = api(path, params)
        if is_ok(result):
            return result
    return result


def is_ok(value) -> bool:
    return isinstance(value, (list, dict)) and not (isinstance(value, dict) and "__http_error__" in value)


def runs_query(default_branch: str) -> dict:
    """Query parameters for the workflow-runs feed.

    Filtering to the default branch keeps Dependabot and feature-branch runs
    from crowding the recent-run window. On a busy repository the first page of
    unfiltered runs can be entirely automated bumps, so no default-branch run
    is visible even though CI is green on main.
    """
    return {"branch": default_branch, "per_page": 100, "status": "completed"}


def analyze(owner: str, repo: str) -> dict | None:
    meta = api(f"/repos/{owner}/{repo}")
    if not isinstance(meta, dict) or "__http_error__" in meta or "full_name" not in meta:
        return None

    branch = meta.get("default_branch", "main")
    languages = api(f"/repos/{owner}/{repo}/languages") or {}
    wfs = api_retry(f"/repos/{owner}/{repo}/actions/workflows")
    runs = api_retry(f"/repos/{owner}/{repo}/actions/runs", runs_query(branch))
    releases = api(f"/repos/{owner}/{repo}/releases", {"per_page": 1})
    tags = api(f"/repos/{owner}/{repo}/tags", {"per_page": 1})
    contributors = api(f"/repos/{owner}/{repo}/contributors", {"per_page": 100})
    readme = api(f"/repos/{owner}/{repo}/readme")
    tree = api_retry(f"/repos/{owner}/{repo}/git/trees/{branch}", {"recursive": "1"})

    wf_list = wfs.get("workflows", []) if isinstance(wfs, dict) else []
    # GitHub always reports the implicit Dependabot and Pages pipelines. Those
    # are not the project's own automation, so they must not earn the CI bonus.
    has_ci = has_project_workflow(wf_list)
    latest_ok = False
    if isinstance(runs, dict):
        latest_ok = ci_is_green(
            runs_for_default_branch(runs.get("workflow_runs", []), branch))

    has_release = is_ok(releases) and len(releases) > 0
    has_tags = is_ok(tags) and len(tags) > 0

    files, lower = [], []
    if isinstance(tree, dict) and tree.get("tree"):
        for t in tree["tree"]:
            if t.get("type") == "blob":
                files.append(t["path"])
                lower.append(t["path"].lower())
    n_files = len(files)

    has_readme = isinstance(readme, dict) and readme.get("download_url") is not None
    license_ok = bool(meta.get("license"))
    has_docs = any(f.startswith(("docs/", "documentation/")) for f in lower)
    # Manifests are matched on basename: backend/pyproject.toml and
    # frontend/package.json are real manifests. Exact-match against full paths
    # silently missed every nested layout.
    has_manifest = any(is_manifest_path(f) for f in lower)
    # Entry points: conventional basenames at any depth, plus the well-known
    # conventional subpaths that are not literally called main/index.
    has_entry = any(is_entry_path(f) for f in lower)
    has_tests = any(is_test_path(f) for f in lower)
    # Docker: iterate the repo's own file list. The previous version iterated a
    # hardcoded list of candidate *names*, so f.startswith(...) was testing the
    # candidate rather than the repo file and has_docker was always True.
    has_docker = any(is_docker_path(f) for f in lower)
    lockfile = has_lockfile(lower)

    size_mb = (meta.get("size") or 0) / 1024.0
    stars = meta.get("stargazers_count") or 0
    forks = meta.get("forks_count") or 0
    n_langs = len({k.lower() for k in (languages or {})})
    n_contributors = len(contributors) if isinstance(contributors, list) else 0

    now = dt.datetime.now(dt.timezone.utc)

    def days_since(iso: str | None) -> int:
        if not iso:
            return 10 ** 9
        try:
            return (now - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
        except Exception:
            return 10 ** 9

    active_days = days_since(meta.get("pushed_at"))
    age_days = days_since(meta.get("created_at"))

    # --- Documentation (max 15)
    doc = 0
    if has_readme:
        doc += 7
    if license_ok:
        doc += 5
    if has_docs or meta.get("has_wiki"):
        doc += 3
    doc = min(doc, 15)

    # --- Code maturity (max 20)
    # A lockfile proves an installable dependency graph, so it earns the same
    # substance credit as a >=1 MB checkout. Small complete apps are not
    # penalised for shipping less vendored weight than larger ones.
    code = 0
    if size_mb >= 1.0 or lockfile:
        code += 4
    if has_manifest:
        code += 6
    if has_entry:
        code += 4
    if n_langs >= 2 or size_mb >= 10:
        code += 3
    if n_files >= 20:
        code += 3
    code = min(code, 20)

    # --- Integration (max 25)
    integ = 0
    if has_ci:
        integ += 8
    if has_release or has_tags:
        integ += 7
    if has_docker:
        integ += 4
    if meta.get("homepage") or meta.get("has_pages"):
        integ += 4
    if meta.get("has_issues"):
        integ += 2
    integ = min(integ, 25)

    # --- Validation (max 20)
    val = 0
    if has_ci and latest_ok:
        val += 10
    if has_tests:
        val += 6
    if active_days <= 90:
        val += 4
    val = min(val, 20)

    # --- Adoption & operations (max 20)
    adopt = 0
    adopt += 0 if stars == 0 else 3 if stars < 5 else 5 if stars < 20 else 7 if stars < 100 else 9
    adopt += 0 if forks == 0 else 2 if forks < 3 else 4 if forks < 10 else 6
    if n_contributors >= 2:
        adopt += 2
    if age_days >= 180:
        adopt += 3
    adopt = min(adopt, 20)

    total = round(doc + code + integ + val + adopt)
    stage = next((s for s in reversed(TRL_STAGES) if total >= s[0]), TRL_STAGES[0])
    _, level, name, _desc = stage

    url_slug = f"https://github.com/{owner}/{repo}"
    pushed = meta.get("pushed_at", "")[:10]
    desc = (meta.get("description") or "").strip()

    return {
        "repo": repo,
        "url": url_slug,
        "level": level,
        "name": name,
        "score": total,
        "stars": TRL_STARS[level - 1] + f" {level}",
        "breakdown": {"docs": doc, "code": code, "integration": integ, "validation": val, "adoption": adopt},
        "signals": {
            "ci": "ok" if has_ci and latest_ok else ("fail" if has_ci else None),
            "tests": has_tests,
            "release": has_release,
            "docker": has_docker,
            "live": bool(meta.get("homepage") or meta.get("has_pages")),
            "docs": has_docs,
            "license": license_ok,
            "active": active_days <= 90,
            "contributors": n_contributors >= 2,
            "stars": stars,
            "forks": forks,
            "pushed": pushed,
            "desc": desc,
        },
    }


def trl_badge(level: int, name: str) -> str:
    color = TRL_COLORS[(level - 1) % len(TRL_COLORS)]
    label = urllib.parse.quote(f"TRL {level}")
    msg = urllib.parse.quote(name)
    url = f"https://img.shields.io/badge/{label}-{msg}-{color}?style=flat-square"
    return f"![TRL {level}: {name}]({url})"


def bar(score: int) -> str:
    filled = max(0, min(10, round(score / 10)))
    return "█" * filled + "░" * (10 - filled)


SIG_ICONS = {
    "ci": "✅ CI",
    "ci_fail": "❌ CI",
    "tests": "🧪 Tests",
    "release": "📦 Release",
    "docker": "🐳 Docker",
    "live": "🌐 Demo",
    "docs": "📄 Docs",
    "license": "🛡️ License",
    "active": "⚡ Active",
    "contributors": "👥 Team",
}


def signals_row(sig: dict) -> str:
    chips = []
    if sig["ci"] == "ok":
        chips.append(SIG_ICONS["ci"])
    elif sig["ci"] == "fail":
        chips.append(SIG_ICONS["ci_fail"])
    for key in ("tests", "release", "docker", "live", "docs", "license", "active"):
        if sig[key]:
            chips.append(SIG_ICONS[key])
    if sig["contributors"]:
        chips.append(SIG_ICONS["contributors"])
    return " · ".join(chips) if chips else "—"


def render_table(results: list[dict]) -> str:
    lines = [
        "| Project | TRL Level | Efficiency | Live Signals |",
        "|---------|-----------|------------|--------------|",
    ]
    for r in sorted(results, key=lambda x: (-x["score"], x["repo"].lower())):
        proj = f"[**{r['repo']}**]({r['url']})"
        trl = trl_badge(r["level"], r["name"])
        rank = ("🔬 " if r["level"] <= 2 else "🧪 " if r["level"] <= 4 else "🔗 " if r["level"] == 5
                else "✅ " if r["level"] == 6 else "🏭 " if r["level"] == 7 else "🚀 " if r["level"] == 8 else "🌍 ")
        eff = f"`{r['score']}/100` `{bar(r['score'])}`"
        lines.append(f"| {rank}{proj} | {trl} | {eff} | {signals_row(r['signals'])} |")
    return "\n".join(lines)


def table_block(results: list[dict]) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    head = (f"_Last updated: {now} · recomputed automatically every 6 hours by the "
            f"[TRL Tracker action](.github/workflows/trl-tracker.yml)._\n")
    body = render_table(results)
    footer = ("<sub>Efficiency 0–100 = live-weighted validation score. "
              "Docs & license · code/entry-point maturity · CI/CD, releases, Docker "
              "& live deployment · automated tests & green CI · stars, forks, contributors & age.</sub>")
    return f"<!-- TRL-TABLE -->\n{head}{body}\n\n{footer}\n<!-- /TRL-TABLE -->"


def update_readme(results: list[dict]) -> bool:
    if not os.path.exists(README):
        return False
    text = open(README, encoding="utf-8").read()
    block = table_block(results)
    orig = text

    if "\n<!-- TRL-TIMESTAMP -->\n" in text:
        text = text.replace("\n<!-- TRL-TIMESTAMP -->\n", "\n", 1)

    start_marker, end_marker = "<!-- TRL-TABLE -->", "<!-- /TRL-TABLE -->"
    if start_marker in text and end_marker in text:
        text = text[:text.index(start_marker)] + block + text[text.index(end_marker) + len(end_marker):]

    if text != orig:
        open(README, "w", encoding="utf-8").write(text)
        return True
    return False


def main() -> int:
    cfg_path = os.path.join(HERE, "projects.json")
    if not os.path.exists(cfg_path):
        print(f"[trl] config not found: {cfg_path}", file=sys.stderr)
        return 1
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    owner = cfg.get("owner", "karun99")

    results, failed = [], []
    for repo in cfg["repos"]:
        print(f"[trl] {owner}/{repo} ... ", flush=True)
        r = analyze(owner, repo)
        if r is None:
            failed.append(repo)
            print("   ✗ skipped", flush=True)
            continue
        results.append(r)
        print(f"   ✓ TRL {r['level']} · {r['name']} · {r['score']}/100", flush=True)

    changed = update_readme(results)
    print(f"\n[trl] scored {len(results)} repositories"
          f" ({'skipped: ' + ', '.join(failed) if failed else 'all ok'})")
    print(f"[trl] README updated: {changed}")
    return 0 if not failed else 1  # 0 even on partial failures; report count below


if __name__ == "__main__":
    raise SystemExit(main())
