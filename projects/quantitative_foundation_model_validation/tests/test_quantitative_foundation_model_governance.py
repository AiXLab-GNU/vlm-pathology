import json
import tempfile
import unittest
from pathlib import Path

from projects.quantitative_foundation_model_validation.governance_portal import governance


class QuantitativeFoundationModelGovernanceTests(unittest.TestCase):
    def test_current_evidence_snapshot_and_portal_data_are_complete(self):
        snapshot = governance.evidence_snapshot()
        self.assertEqual(snapshot["protocol_id"], governance.PROTOCOL_ID)
        self.assertEqual(len(snapshot["files"]), len(governance.EVIDENCE_FILES))
        self.assertEqual(len(snapshot["snapshot_sha256"]), 64)
        data = governance.portal_data(records_dir=Path(tempfile.mkdtemp()))
        self.assertEqual(len(data["questions"]), 6)
        self.assertEqual(data["summary"]["candidate_combinations"], 2)
        self.assertTrue(any(not row["can_approval_resolve"] for row in data["scientific_boundaries"]))

    def test_approval_requires_matching_signature_and_attestations(self):
        with tempfile.TemporaryDirectory() as directory:
            records = Path(directory)
            payload = {
                "reviewer_role": "research_lead",
                "reviewer_name": "Jin Hyun Kim",
                "signature": "different",
                "decision": "conditional_go",
            }
            with self.assertRaises(governance.GovernanceError):
                governance.append_approval(payload, records_dir=records)
            payload["signature"] = payload["reviewer_name"]
            with self.assertRaises(governance.GovernanceError):
                governance.append_approval(payload, records_dir=records)

    def test_research_lead_approval_is_required_and_advisory_review_is_nonblocking(self):
        with tempfile.TemporaryDirectory() as directory:
            records = Path(directory) / "records"
            advisory = {
                "reviewer_role": "pathology",
                "reviewer_name": "Advisory Reviewer",
                "signature": "Advisory Reviewer",
                "decision": "revise",
            }
            governance.append_approval(advisory, records_dir=records)
            payload = {
                "reviewer_role": "research_lead",
                "reviewer_name": "Research Lead",
                "signature": "Research Lead",
                "decision": "conditional_go",
                **{key: True for key in governance.REQUIRED_ATTESTATIONS},
            }
            governance.append_approval(payload, records_dir=records)
            rows = governance.approval_records(records)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["previous_record_sha256"], rows[0]["record_sha256"])
            readiness = governance.g8_readiness(records_dir=records)
            self.assertTrue(readiness["ready_to_finalize"])
            self.assertTrue(readiness["roles"]["research_lead"]["required"])
            self.assertFalse(readiness["roles"]["pathology"]["required"])
            manifest = governance.finalize_g8(records_dir=records)
            self.assertEqual(manifest["decision"], "Conditional Go")
            self.assertEqual(len(manifest["approvers"]), 1)
            self.assertEqual(len(manifest["advisory_reviews"]), 1)
            self.assertTrue((records / "g8_approval_manifest.json").is_file())
            self.assertTrue((records / "g8_adjudication_summary.csv").is_file())
            self.assertTrue((records / "G8_FINAL_DECISION.md").is_file())
            self.assertEqual(manifest, governance.finalize_g8(records_dir=records))
            with self.assertRaises(governance.GovernanceError):
                governance.append_approval(payload, records_dir=records)

    def test_portal_is_loopback_only_and_static_assets_are_self_contained(self):
        portal = governance.PORTAL_ROOT
        server_source = (portal / "portal_server.py").read_text(encoding="utf-8")
        html = (portal / "web/qfm-governance.html").read_text(encoding="utf-8")
        self.assertIn('default="127.0.0.1"', server_source)
        self.assertNotIn("0.0.0.0", server_source)
        self.assertIn('id="approval-form"', html)
        self.assertIn('id="run-m9"', html)
        self.assertNotIn("https://", html)
        portfolio_html = (portal / "web/index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="home"', portfolio_html)
        self.assertIn("/clinician-review.html", portfolio_html)
        javascript = (portal / "web/app.js").read_text(encoding="utf-8")
        self.assertIn("const formElement = event.currentTarget", javascript)
        self.assertNotIn("event.currentTarget.reset()", javascript)

    def test_normalized_run_config_ignores_only_documented_volatile_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left.json"
            right = Path(directory) / "right.json"
            left.write_text(json.dumps({"x": 1, "started_at_utc": "a", "nested": {"execution_seconds": 1}}))
            right.write_text(json.dumps({"x": 1, "started_at_utc": "b", "nested": {"execution_seconds": 9}}))
            self.assertEqual(governance._normalized_config(left), governance._normalized_config(right))
            right.write_text(json.dumps({"x": 2, "started_at_utc": "b"}))
            self.assertNotEqual(governance._normalized_config(left), governance._normalized_config(right))


if __name__ == "__main__":
    unittest.main()
