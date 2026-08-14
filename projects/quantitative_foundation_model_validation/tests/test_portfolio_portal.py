import tempfile
import unittest
from pathlib import Path

from projects.quantitative_foundation_model_validation.governance_portal import portfolio


class PortfolioPortalTests(unittest.TestCase):
    def test_portfolio_uses_all_three_canonical_sequence_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            data = portfolio.portfolio_data(review_root=Path(directory))
        self.assertEqual(len(data["projects"]), 3)
        self.assertEqual(
            {project["id"] for project in data["projects"]},
            {
                "precise_pni_candidate_triage",
                "quantitative_foundation_model_validation",
                "prostate_biomarker_validation",
            },
        )
        for project in data["projects"]:
            self.assertGreater(len(project["milestones"]), 5)
            self.assertIn(project["current_gate"]["status_key"], {"active", "complete"})
            self.assertGreaterEqual(project["progress_percent"], 0)
            self.assertLessEqual(project["progress_percent"], 100)

    def test_artifacts_are_explicit_and_owner_preserving(self):
        data = portfolio.portfolio_data(review_root=Path(tempfile.mkdtemp()))
        artifacts = {artifact["id"]: artifact for artifact in data["artifacts"]}
        self.assertIn("medical-metric-atlas", artifacts)
        self.assertEqual(artifacts["medical-metric-atlas"]["owner"], "shared_infrastructure")
        self.assertTrue(artifacts["medical-metric-atlas"]["available"])
        for artifact_id, config in portfolio.ARTIFACTS.items():
            path = portfolio.artifact_path(artifact_id)
            path.relative_to(portfolio.REPOSITORY_ROOT)
            self.assertEqual(path, (portfolio.REPOSITORY_ROOT / config["path"]).resolve())

    def test_admin_and_clinician_surveys_are_hash_chained_per_project(self):
        with tempfile.TemporaryDirectory() as directory:
            review_root = Path(directory)
            admin_payload = {
                "project_id": "precise_pni_candidate_triage",
                "reviewer_name": "Admin Reviewer",
                "reviewer_title": "Research Operations",
                "signature": "Admin Reviewer",
                "decision": "ready",
                "scope_confirmed": True,
                "evidence_traceable": True,
                "governance_complete": True,
                "data_integrity_confirmed": True,
                "comment": "",
            }
            first = portfolio.append_review_survey("admin", admin_payload, review_root)
            second = portfolio.append_review_survey("admin", admin_payload, review_root)
            self.assertIsNone(first["previous_record_sha256"])
            self.assertEqual(second["previous_record_sha256"], first["record_sha256"])

            clinician_payload = {
                "project_id": "quantitative_foundation_model_validation",
                "reviewer_name": "Clinical Reviewer",
                "reviewer_title": "Pathologist",
                "signature": "Clinical Reviewer",
                "decision": "clinically_acceptable",
                "claim_boundary_clear": True,
                "visual_quality_adequate": True,
                "workflow_fit_reviewed": True,
                "confidence": 4,
                "comment": "",
            }
            clinician = portfolio.append_review_survey("clinician", clinician_payload, review_root)
            self.assertEqual(clinician["confidence"], 4)
            summary = portfolio.review_summary(review_root)
            self.assertEqual(summary["precise_pni_candidate_triage"]["admin"], 2)
            self.assertEqual(summary["quantitative_foundation_model_validation"]["clinician"], 1)

    def test_review_validation_rejects_unsigned_or_unexplained_revision(self):
        base = {
            "project_id": "prostate_biomarker_validation",
            "reviewer_name": "Reviewer",
            "reviewer_title": "Pathologist",
            "signature": "Different",
            "decision": "revise",
            "claim_boundary_clear": True,
            "visual_quality_adequate": True,
            "workflow_fit_reviewed": True,
            "confidence": 3,
            "comment": "",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(portfolio.PortfolioError):
                portfolio.append_review_survey("clinician", base, root)
            base["signature"] = "Reviewer"
            with self.assertRaises(portfolio.PortfolioError):
                portfolio.append_review_survey("clinician", base, root)

    def test_portal_has_distinct_project_and_review_pages(self):
        web = portfolio.PORTAL_ROOT / "web"
        for name in (
            "index.html",
            "pni.html",
            "quantitative.html",
            "biomarker.html",
            "admin-review.html",
            "clinician-review.html",
            "artifacts.html",
            "qfm-governance.html",
        ):
            self.assertTrue((web / name).is_file(), name)
        server = (portfolio.PORTAL_ROOT / "portal_server.py").read_text(encoding="utf-8")
        self.assertIn('route == "/api/survey/admin"', server)
        self.assertIn('route == "/api/survey/clinician"', server)
        self.assertNotIn('default="0.0.0.0"', server)


if __name__ == "__main__":
    unittest.main()
