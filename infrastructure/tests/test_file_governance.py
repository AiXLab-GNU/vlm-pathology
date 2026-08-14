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
            # Generated products can contain protocol-declared volatile fields
            # such as execution timestamps.  Their baseline digest is a
            # point-in-time inventory value; owning-project manifests and tests
            # enforce their reproducibility contract.
            if row["lifecycle"] != "generated":
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

    def test_document_hierarchy_prefixes_encode_ancestry(self) -> None:
        auditor = load_auditor()
        cases = {
            "01-research-plan-ko.md": "01",
            "01-02-fm2-paired-manifest-ko.md": "01-02",
            "01-02-03-paired-manifest-schema-ko.md": "01-02-03",
        }
        for name, hierarchy_id in cases.items():
            match = auditor.HIERARCHY_DOC_NAME.fullmatch(name)
            self.assertIsNotNone(match, name)
            self.assertEqual(match.group("hierarchy_id"), hierarchy_id)
            self.assertIsNotNone(auditor.GENERAL_DOC_NAME.fullmatch(name), name)
        self.assertIsNone(
            auditor.HIERARCHY_DOC_NAME.fullmatch("14_FLAT_SEQUENCE_PLAN_KO.md")
        )
        self.assertIsNone(
            auditor.HIERARCHY_DOC_NAME.fullmatch("00-reserved-plan-ko.md")
        )

    def test_control_role_names_and_versions_fail_closed(self) -> None:
        auditor = load_auditor()
        for name in (
            "01-project-milestones-final.md",
            "01-01-project-execution-tracker-v1.md",
            "latest-survey.md",
        ):
            status, _ = auditor.naming_status(
                Path(f"projects/example/docs/research_plan/{name}"),
                "research_plan",
                None,
                set(),
            )
            self.assertEqual(status, "fail", name)
        status, _ = auditor.naming_status(
            Path("projects/example/docs/research_plan/01-01-project-milestones-v01.md"),
            "research_plan",
            None,
            set(),
        )
        self.assertEqual(status, "pass")

    def test_registered_projects_have_one_canonical_control_chain(self) -> None:
        auditor = load_auditor()
        for project_id in auditor.PROJECT_IDS:
            project = ROOT / "projects" / project_id
            metadata = auditor.read_simple_yaml(project / "PROJECT.yaml")
            paths = [project / metadata[key] for key in auditor.CONTROL_KEYS]
            self.assertTrue(all(path.is_file() for path in paths), project_id)
            identifiers = [auditor.hierarchy_id(path) for path in paths]
            self.assertEqual([len(value.split("-")) for value in identifiers], [1, 2, 3])
            self.assertIn("milestones", paths[1].name)
            self.assertIn("execution-tracker", paths[2].name)
            self.assertTrue((project / metadata["survey_index"]).is_file())


if __name__ == "__main__":
    unittest.main()
