"""Integration test for project-scoped Git worktree governance."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class WorktreeRegistryTest(unittest.TestCase):
    def test_worktree_registry_matches_git(self) -> None:
        result = subprocess.run(
            [str(ROOT / ".venv/bin/python"), str(ROOT / "infrastructure/scripts/audit_worktrees.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
