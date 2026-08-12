"""Integration test for repository project separation."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ProjectBoundaryTest(unittest.TestCase):
    def test_repository_boundaries(self) -> None:
        result = subprocess.run(
            [str(ROOT / ".venv/bin/python"), str(ROOT / "infrastructure/scripts/validate_project_boundaries.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
