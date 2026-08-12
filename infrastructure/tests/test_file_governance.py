"""Integration contract for repository file-level governance."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "infrastructure/migrations/2026-08-12-file-governance/FILE_GOVERNANCE_BASELINE.csv"
AUDITOR_PATH = ROOT / "infrastructure/scripts/audit_file_governance.py"


def load_auditor():
    spec = importlib.util.spec_from_file_location("audit_file_governance", AUDITOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FileGovernanceTest(unittest.TestCase):
    def test_every_managed_document_and_code_file_is_classified(self) -> None:
        result = subprocess.run(
            [str(ROOT / ".venv/bin/python"), str(ROOT / "infrastructure/scripts/audit_file_governance.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["managed_file_count"], payload["classified_file_count"])
        self.assertEqual(payload["failure_count"], 0)

    def test_baseline_has_unique_classified_paths_and_required_lineage(self) -> None:
        self.assertTrue(BASELINE.is_file())
        with BASELINE.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        paths = [row["path"] for row in rows]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertNotIn("unclassified", {row["file_class"] for row in rows})
        for row in rows:
            self.assertTrue(row["owner"])
            self.assertTrue(row["lifecycle"])
            self.assertTrue(row["provenance_role"])
            self.assertEqual(len(row["sha256"]), 64)
            path = ROOT / row["path"]
            self.assertTrue(path.is_file(), row["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                row["sha256"],
                row["path"],
            )

    def test_exception_scope_does_not_waive_new_filename_rules(self) -> None:
        auditor = load_auditor()
        exception = {"reason": "historical bundle"}
        new_bad_path = Path(
            "projects/prostate_biomarker_validation/paper/NEW_FILE.md"
        )
        status, _ = auditor.naming_status(
            new_bad_path, "manuscript_source", exception, set()
        )
        self.assertEqual(status, "fail")

        old_bad_path = Path(
            "projects/prostate_biomarker_validation/paper/LegacyName.md"
        )
        status, _ = auditor.naming_status(
            old_bad_path,
            "manuscript_source",
            exception,
            {old_bad_path.as_posix()},
        )
        self.assertEqual(status, "fixed_contract")

        canonical_path = Path(
            "projects/prostate_biomarker_validation/paper/reviewer-response.md"
        )
        status, _ = auditor.naming_status(
            canonical_path, "manuscript_source", exception, set()
        )
        self.assertEqual(status, "pass")


if __name__ == "__main__":
    unittest.main()
