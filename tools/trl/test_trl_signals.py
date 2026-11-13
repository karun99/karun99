#!/usr/bin/env python3
"""Regression tests for the file-layout predicates in trl_tracker.

These predicates decide up to 14 of the 100 TRL points, and all three were
previously broken in ways that silently mis-scored every repository:

  - has_docker iterated a hardcoded list of candidate *names*, so
    f.startswith(...) tested the candidate rather than the repo file and the
    result was unconditionally True (every repo earned a Docker bonus).
  - has_manifest and has_entry used exact membership against a list of full
    paths, so "backend/pyproject.toml" never matched "pyproject.toml" and
    nested monorepo layouts lost 10 points.

The predicates are imported from trl_tracker itself so the tests cannot drift
from the implementation; analyze() reaches the GitHub API directly, which is
why the helpers are factored out as pure functions.
Run: python3 tools/trl/test_trl_signals.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trl_tracker
from trl_tracker import (
    api_retry,
    ci_is_green,
    has_project_workflow,
    is_ci_run,
    is_docker_path,
    is_entry_path,
    is_manifest_path,
    has_lockfile,
    runs_for_default_branch,
    is_test_path,
)


def has_manifest(paths):
    return any(is_manifest_path(p.lower()) for p in paths)


def has_entry(paths):
    return any(is_entry_path(p.lower()) for p in paths)


def has_docker(paths):
    return any(is_docker_path(p.lower()) for p in paths)


def lowercased(paths):
    return [p.lower() for p in paths]


class HasDockerTest(unittest.TestCase):
    def test_repo_without_docker_files_is_false(self):
        """The core regression: this used to return True for every repo."""
        self.assertFalse(has_docker(lowercased(["readme.md", "src/index.js", "package.json"])))

    def test_empty_tree_is_false(self):
        self.assertFalse(has_docker([]))

    def test_root_dockerfile(self):
        self.assertTrue(has_docker(lowercased(["Dockerfile"])))

    def test_nested_dockerfile(self):
        self.assertTrue(has_docker(lowercased(["deploy/Dockerfile"])))

    def test_variants(self):
        for path in ("docker-compose.yml", "compose.yaml", "compose.yml",
                     "infra/docker-compose.prod.yml", "dockerfile.dev"):
            with self.subTest(path=path):
                self.assertTrue(has_docker(lowercased([path])))

    def test_similarly_named_file_is_false(self):
        """'docker-compose-notes.md' is documentation, not a compose file."""
        self.assertFalse(has_docker(lowercased(["docs/docker-compose-notes.md"])))


class HasManifestTest(unittest.TestCase):
    def test_root_manifest(self):
        self.assertTrue(has_manifest(lowercased(["package.json"])))

    def test_nested_manifests(self):
        """Previously False -- exact match against full paths."""
        self.assertTrue(has_manifest(lowercased(
            ["backend/pyproject.toml", "frontend/package.json"])))

    def test_requirements_txt_nested(self):
        self.assertTrue(has_manifest(lowercased(["backend/requirements.txt"])))

    def test_no_manifest(self):
        self.assertFalse(has_manifest(lowercased(["readme.md", "src/index.js"])))

    def test_similar_name_is_false(self):
        self.assertFalse(has_manifest(lowercased(["docs/package.json.md"])))


class HasEntryTest(unittest.TestCase):
    def test_root_entry(self):
        self.assertTrue(has_entry(lowercased(["main.py"])))

    def test_conventional_subpaths(self):
        """Previously False -- lost 4 code points on real monorepos."""
        self.assertTrue(has_entry(lowercased(["pkg/main.go", "src/main.py"])))

    def test_bin_and_cmd(self):
        self.assertTrue(has_entry(lowercased(["cmd/server/main.go"])))
        self.assertTrue(has_entry(lowercased(["bin/cli.js"])))

    def test_static_site_entry(self):
        self.assertTrue(has_entry(lowercased(["index.html"])))

    def test_next_app_router_layout(self):
        self.assertTrue(has_entry(lowercased(["src/app/layout.tsx"])))
        self.assertTrue(has_entry(lowercased(["app/layout.jsx"])))

    def test_no_entry(self):
        self.assertFalse(has_entry(lowercased(["readme.md", "LICENSE"])))


class HasLockfileTest(unittest.TestCase):
    def test_npm_lock_at_root_or_nested(self):
        self.assertTrue(has_lockfile(["package-lock.json"]))
        self.assertTrue(has_lockfile(["web-app/package-lock.json"]))

    def test_other_ecosystems(self):
        self.assertTrue(has_lockfile(["poetry.lock", "cargo.lock"]))
        self.assertTrue(has_lockfile(["go.sum"]))
        self.assertTrue(has_lockfile(["uv.lock"]))

    def test_manifest_is_not_a_lockfile(self):
        self.assertFalse(has_lockfile(["package.json", "requirements.txt"]))


class HasTestsTest(unittest.TestCase):
    def test_root_test_dir(self):
        self.assertTrue(is_test_path("test/app.js"))

    def test_nested_test_dir(self):
        """Previously False -- nested layouts lost the 6 validation points."""
        self.assertTrue(is_test_path("api/tests/test_neurobot.py"))
        self.assertTrue(is_test_path("backend/__tests__/x.js"))

    def test_python_test_module(self):
        self.assertTrue(is_test_path("pkg/test_engine.py"))
        self.assertTrue(is_test_path("pkg/engine_test.py"))

    def test_js_test_suffix(self):
        self.assertTrue(is_test_path("src/lib/storage.test.js"))
        self.assertTrue(is_test_path("src/lib/storage.spec.ts"))

    def test_docs_are_not_tests(self):
        self.assertFalse(is_test_path("docs/testing.md"))
        self.assertFalse(is_test_path("src/latest.ts"))
        self.assertFalse(is_test_path("src/contest.py"))


class ProjectWorkflowTest(unittest.TestCase):
    def test_auxiliary_only_workflows_do_not_count_as_ci(self):
        self.assertFalse(has_project_workflow([
            {"path": ".github/workflows/security.yml"},
            {"path": ".github/workflows/deploy.yml"},
            {"path": ".github/workflows/release.yml"},
        ]))

    def test_security_incident_name_does_not_match_ci_substring(self):
        self.assertFalse(has_project_workflow([
            {"path": ".github/workflows/security-incident.yml"},
        ]))

    def test_security_check_alone_does_not_count_as_code_ci(self):
        self.assertFalse(has_project_workflow([
            {"path": ".github/workflows/security-check.yml"},
        ]))

    def test_implicit_pipelines_do_not_count(self):
        self.assertFalse(has_project_workflow([
            {"path": "dynamic/dependabot/dependabot-updates"},
            {"path": "dynamic/pages/pages-build-deployment"},
        ]))

    def test_real_workflow_counts(self):
        self.assertTrue(has_project_workflow([
            {"path": ".github/workflows/ci.yml"},
            {"path": "dynamic/pages/pages-build-deployment"},
        ]))

    def test_empty_is_false(self):
        self.assertFalse(has_project_workflow([]))


class DefaultBranchRunsTest(unittest.TestCase):
    def test_dependabot_pr_branch_is_excluded(self):
        runs = [
            {"head_branch": "dependabot/npm_and_yarn/main/eslint-10.14.0",
             "conclusion": "failure"},
            {"head_branch": "main", "conclusion": "success"},
        ]
        kept = runs_for_default_branch(runs, "main")
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["conclusion"], "success")

    def test_unknown_branch_is_dropped(self):
        runs = [{"head_branch": None, "conclusion": "success"}]
        self.assertEqual(runs_for_default_branch(runs, "main"), [])


class RunsQueryTest(unittest.TestCase):
    """The run feed must ask GitHub for default-branch runs directly.

    s-ai generates so many Dependabot runs that the unfiltered first page of
    50 runs contained no run on main at all, and the project was scored as if
    its CI had never run.
    """

    def test_filters_to_the_default_branch(self):
        params = trl_tracker.runs_query("main")
        self.assertEqual(params["branch"], "main")
        self.assertEqual(params["status"], "completed")

    def test_window_is_wide_enough_for_busy_repositories(self):
        self.assertGreaterEqual(trl_tracker.runs_query("trunk")["per_page"], 100)


class RetryApiTest(unittest.TestCase):
    def test_retries_transient_failures(self):
        calls = {"n": 0}
        real = trl_tracker.api

        def flaky(path, params=None):
            calls["n"] += 1
            if calls["n"] < 3:
                return {"__http_error__": -1}
            return {"tree": [{"path": "README.md"}]}

        trl_tracker.api = flaky
        try:
            result = api_retry("/repos/o/r/git/trees/main")
        finally:
            trl_tracker.api = real
        self.assertEqual(calls["n"], 3)
        self.assertTrue(result["tree"])

    def test_gives_up_after_attempts(self):
        calls = {"n": 0}
        real = trl_tracker.api

        def broken(path, params=None):
            calls["n"] += 1
            return {"__http_error__": -1}

        trl_tracker.api = broken
        try:
            result = api_retry("/x", attempts=2)
        finally:
            trl_tracker.api = real
        self.assertEqual(calls["n"], 2)
        self.assertIn("__http_error__", result)


class CiSignalTest(unittest.TestCase):
    def test_successful_security_or_deploy_does_not_count_as_ci(self):
        runs = [
            {"name": "Deploy", "path": ".github/workflows/deploy.yml",
             "event": "push", "conclusion": "success"},
            {"name": "Security Audit", "path": ".github/workflows/security.yml",
             "event": "schedule", "conclusion": "success"},
        ]
        self.assertFalse(ci_is_green(runs))

    def test_successful_security_check_does_not_count_as_ci(self):
        self.assertFalse(ci_is_green([
            {"name": "Security Check", "path": ".github/workflows/security-check.yml",
             "event": "push", "conclusion": "success"},
        ]))

    def test_dependabot_runs_are_ignored(self):
        runs = [
            {"name": "npm_and_yarn in /. - Update", "path": "dynamic/dependabot/dependabot-updates",
             "event": "dynamic", "conclusion": "failure"},
            {"name": "CI", "path": ".github/workflows/ci.yml",
             "event": "push", "conclusion": "success"},
        ]
        self.assertFalse(is_ci_run(runs[0]))
        self.assertTrue(is_ci_run(runs[1]))
        self.assertTrue(ci_is_green(runs))

    def test_auxiliary_failures_do_not_break_ci(self):
        runs = [
            {"name": "Security Audit", "path": ".github/workflows/security.yml",
             "event": "schedule", "conclusion": "failure"},
            {"name": "CI", "path": ".github/workflows/ci.yml",
             "event": "pull_request", "conclusion": "success"},
        ]
        self.assertTrue(ci_is_green(runs))

    def test_latest_ci_failure_is_red(self):
        runs = [
            {"name": "CI", "path": ".github/workflows/ci.yml",
             "event": "push", "conclusion": "failure"},
            {"name": "CI", "path": ".github/workflows/ci.yml",
             "event": "push", "conclusion": "success"},
        ]
        self.assertFalse(ci_is_green(runs))

    def test_auxiliary_success_does_not_substitute_for_ci(self):
        runs = [
            {"name": "mcp-server", "path": ".github/workflows/mcp-server.yml",
             "event": "push", "conclusion": "success"},
        ]
        self.assertFalse(ci_is_green(runs))

    def test_cancelled_and_empty_runs_are_not_green(self):
        self.assertFalse(ci_is_green([]))
        self.assertFalse(ci_is_green([
            {"name": "CI", "path": ".github/workflows/ci.yml",
             "event": "push", "conclusion": "cancelled"},
        ]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
