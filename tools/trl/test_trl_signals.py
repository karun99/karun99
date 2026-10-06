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

from trl_tracker import is_docker_path, is_entry_path, is_manifest_path


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

    def test_no_entry(self):
        self.assertFalse(has_entry(lowercased(["readme.md", "LICENSE"])))


if __name__ == "__main__":
    unittest.main(verbosity=2)