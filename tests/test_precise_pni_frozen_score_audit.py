from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "models"))

from audit_precise_pni_frozen_scores import (  # noqa: E402
    AuditIntegrityError,
    build_error_review,
    attach_bootstrap_summary,
    cluster_bootstrap,
    compute_budget_capture,
    compute_score_metrics,
    compute_subtype_and_stratum,
    normalize_full_score_header,
    normalize_review,
    run_audit,
    spatial_nms,
    validate_and_merge,
)


class NormalizationTests(unittest.TestCase):
    def review_fixture(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "candidate_id": ["C-1", "C-2"],
                "review_order": [1, 2],
                "image_id": ["sub-01_ses-01", "sub-02_ses-01"],
                "x0": [0, 10],
                "y0": [0, 10],
                "window_px": [100, 100],
                "window_um": [300.0, 300.0],
                "reviewer_id": [np.nan, ""],
                "nerve_present": [" YES ", np.nan],
                "pni_present": ["no", ""],
                "tumor_nerve_relation": ["none", np.nan],
                "confidence": ["high", ""],
                "notes": [np.nan, "wider field"],
            }
        )

    def test_normalize_preserves_missing_outcomes_and_does_not_mutate_source(self):
        source = self.review_fixture()
        before = source.copy(deep=True)

        normalized, events = normalize_review(source)

        pd.testing.assert_frame_equal(source, before)
        self.assertEqual(normalized["reviewer_id"].tolist(), ["Song", "Song"])
        self.assertEqual(normalized.loc[0, "nerve_present"], "yes")
        self.assertTrue(pd.isna(normalized.loc[1, "nerve_present"]))
        self.assertTrue(pd.isna(normalized.loc[1, "pni_present"]))
        self.assertIn("nerve_present_source", normalized.columns)
        self.assertEqual(normalized.loc[0, "nerve_present_source"], " YES ")
        self.assertTrue(any(e["check"] == "missing_outcome_fields" for e in events))
        notes_event = next(e for e in events if e["check"] == "missing_optional_notes")
        self.assertEqual(notes_event["n_affected"], 1)

    def test_duplicate_candidate_or_review_order_is_fatal(self):
        source = self.review_fixture()
        source.loc[1, "candidate_id"] = "C-1"
        with self.assertRaises(AuditIntegrityError):
            normalize_review(source)

        source = self.review_fixture()
        source.loc[1, "review_order"] = 1
        with self.assertRaises(AuditIntegrityError):
            normalize_review(source)

    def test_malformed_first_header_is_repaired_only_when_values_reconcile(self):
        malformed = pd.DataFrame(
            {
                "/tmp/review.htmlimage_id": ["sub-01_ses-01", "sub-02_ses-01"],
                "combined_score": [0.9, 0.8],
            }
        )
        repaired, event = normalize_full_score_header(
            malformed, {"sub-01_ses-01", "sub-02_ses-01"}
        )
        self.assertEqual(repaired.columns[0], "image_id")
        self.assertEqual(event["status"], "warning")

        bad = malformed.copy()
        bad.iloc[1, 0] = "sub-99_ses-01"
        with self.assertRaises(AuditIntegrityError):
            normalize_full_score_header(bad, {"sub-01_ses-01", "sub-02_ses-01"})


class NmsAndReconciliationTests(unittest.TestCase):
    def test_nms_suppresses_strictly_inside_threshold_and_retains_equality(self):
        scores = pd.DataFrame(
            {
                "image_id": ["slide", "slide", "slide", "slide"],
                "x0": [0, 74, 75, 200],
                "y0": [0, 0, 0, 0],
                "window_px": [100, 100, 100, 100],
                "combined_score": [0.9, 0.8, 0.7, 0.6],
            }
        )

        retained = spatial_nms(scores)

        self.assertEqual(retained["x0"].tolist(), [0, 75, 200])
        self.assertEqual(retained["nms_rank"].tolist(), [1, 2, 3])

    def test_nms_orders_by_combined_score_before_geometry(self):
        scores = pd.DataFrame(
            {
                "image_id": ["slide", "slide"],
                "x0": [0, 20],
                "y0": [0, 0],
                "window_px": [100, 100],
                "combined_score": [0.2, 0.9],
            }
        )
        retained = spatial_nms(scores)
        self.assertEqual(retained["x0"].tolist(), [20])

    def test_reconciliation_rejects_score_or_stratum_mismatch(self):
        manifest = pd.DataFrame(
            {
                "candidate_id": ["C-1"],
                "review_order": [1],
                "image_id": ["sub-01_ses-01"],
                "x0": [0],
                "y0": [0],
                "window_px": [100],
                "window_um": [300.0],
                "combined_score": [0.9],
                "prototype_score": [0.1],
                "text_pni_score": [0.2],
                "nerve_score": [0.3],
                "prototype_score_pct": [0.4],
                "text_pni_score_pct": [0.5],
                "nerve_score_pct": [0.6],
                "within_slide_pct": [1.0],
                "selection_stratum": ["high"],
                "image_rank": [1],
            }
        )
        review = manifest[
            ["candidate_id", "review_order", "image_id", "x0", "y0", "window_px", "window_um"]
        ].assign(
            reviewer_id="Song",
            nerve_present="no",
            pni_present="no",
            tumor_nerve_relation="none",
            confidence="high",
            notes=pd.NA,
        )
        nms = manifest.drop(columns=["candidate_id", "review_order", "selection_stratum"]).copy()
        nms["nms_rank"] = 1

        bad_manifest = manifest.copy()
        bad_manifest.loc[0, "combined_score"] = 0.8
        with self.assertRaises(AuditIntegrityError):
            validate_and_merge(review, bad_manifest, nms)

        bad_manifest = manifest.copy()
        bad_manifest.loc[0, "selection_stratum"] = "mid"
        with self.assertRaises(AuditIntegrityError):
            validate_and_merge(review, bad_manifest, nms)


class EndpointTests(unittest.TestCase):
    def audit_fixture(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        nms = pd.DataFrame(
            {
                "image_id": ["sub-01_ses-01", "sub-01_ses-01", "sub-02_ses-01", "sub-02_ses-01"],
                "x0": [0, 100, 0, 100],
                "y0": [0, 0, 0, 0],
                "window_px": [100] * 4,
                "nms_rank": [1, 2, 1, 2],
                "combined_score": [0.9, 0.4, 0.8, 0.3],
            }
        )
        audit = pd.DataFrame(
            {
                "candidate_id": ["C-1", "C-2", "C-3"],
                "review_order": [1, 2, 3],
                "image_id": ["sub-01_ses-01", "sub-01_ses-01", "sub-02_ses-01"],
                "subject_id": ["sub-01", "sub-01", "sub-02"],
                "x0": [0, 100, 100],
                "y0": [0, 0, 0],
                "window_px": [100] * 3,
                "nms_rank": [1, 2, 2],
                "pni_present": ["yes", "no", "no"],
                "nerve_present": ["yes", "no", "yes"],
                "tumor_nerve_relation": ["touching", "none", "adjacent"],
                "selection_stratum": ["high", "mid", "high"],
                "prototype_score": [0.9, 0.2, 0.3],
                "text_pni_score": [0.8, 0.1, 0.2],
                "nerve_score": [0.7, 0.1, 0.6],
                "combined_score": [0.9, 0.2, 0.4],
                "tumor_fraction": [0.2, 0.3, 0.4],
                "stroma_fraction": [0.8, 0.7, 0.6],
                "labeled_fraction": [1.0, 1.0, 1.0],
                "rgb_tissue_fraction": [0.9, 0.9, 0.9],
                "confidence": ["high", "high", "medium"],
                "notes": [pd.NA, pd.NA, "nerve only"],
            }
        )
        return audit, nms

    def test_budget_capture_keeps_unreviewed_candidates_out_of_precision(self):
        audit, nms = self.audit_fixture()

        result = compute_budget_capture(audit, nms, max_k=2)

        pni_k1 = result[(result.endpoint == "pni") & (result.k == 1)].iloc[0]
        self.assertEqual(int(pni_k1.captured_positive), 1)
        self.assertEqual(int(pni_k1.total_positive), 1)
        self.assertAlmostEqual(float(pni_k1.capture_fraction), 1.0)
        self.assertEqual(int(pni_k1.budget_candidate_count), 2)
        self.assertEqual(int(pni_k1.evaluable_review_count), 1)
        self.assertAlmostEqual(float(pni_k1.review_coverage), 0.5)
        self.assertTrue(pd.isna(pni_k1.top_k_precision))
        self.assertAlmostEqual(float(pni_k1.exact_ci_low), 0.025, places=6)
        touching = result[(result.endpoint == "pni_touching") & (result.k == 1)].iloc[0]
        surrounding = result[(result.endpoint == "pni_surrounding") & (result.k == 1)].iloc[0]
        self.assertEqual(int(touching.total_positive), 1)
        self.assertEqual(int(surrounding.total_positive), 0)
        self.assertTrue(pd.isna(surrounding.capture_fraction))

    def test_budget_precision_exists_only_with_complete_evaluable_coverage(self):
        audit, nms = self.audit_fixture()
        missing_top = pd.DataFrame(
            {
                **{column: [nms.iloc[2][column]] for column in ["image_id", "x0", "y0", "window_px", "nms_rank", "combined_score"]},
                "candidate_id": ["C-4"],
                "review_order": [4],
                "subject_id": ["sub-02"],
                "pni_present": ["no"],
                "nerve_present": ["no"],
                "tumor_nerve_relation": ["none"],
                "selection_stratum": ["low_random"],
                "prototype_score": [0.1],
                "text_pni_score": [0.1],
                "nerve_score": [0.1],
                "tumor_fraction": [0.2],
                "stroma_fraction": [0.8],
                "labeled_fraction": [1.0],
                "rgb_tissue_fraction": [0.9],
                "confidence": ["high"],
                "notes": [pd.NA],
            }
        )
        complete = pd.concat([audit, missing_top], ignore_index=True)
        result = compute_budget_capture(complete, nms, max_k=2)
        pni_k2 = result[(result.endpoint == "pni") & (result.k == 2)].iloc[0]
        self.assertEqual(float(pni_k2.review_coverage), 1.0)
        self.assertAlmostEqual(float(pni_k2.top_k_precision), 0.25)

    def test_score_metrics_and_group_summaries_use_reviewed_labels(self):
        audit, _ = self.audit_fixture()
        metrics = compute_score_metrics(audit)
        self.assertEqual(set(metrics.metric), {"roc_auc", "average_precision"})
        self.assertEqual(set(metrics.score), {"prototype", "text_pni", "nerve", "combined"})
        self.assertTrue((metrics.point_estimate.between(0.0, 1.0)).all())

        summary = compute_subtype_and_stratum(audit)
        high = summary[(summary.summary_type == "stratum") & (summary.group == "high")].iloc[0]
        self.assertEqual(int(high.reviewed_count), 2)
        self.assertEqual(int(high.pni_positive_count), 1)
        self.assertEqual(int(high.nerve_positive_count), 2)

    def test_error_review_has_deterministic_nonhistologic_reasons(self):
        audit, _ = self.audit_fixture()
        errors = build_error_review(audit)
        self.assertIn("high_ranked_pni_negative", "|".join(errors.error_review_reason))
        self.assertIn("nerve_positive_pni_negative", "|".join(errors.error_review_reason))
        self.assertFalse(any("ganglion" in value for value in errors.error_review_reason))


class BootstrapTests(unittest.TestCase):
    def bootstrap_fixture(self) -> pd.DataFrame:
        rows = []
        for subject_id, label, base in [("sub-01", "yes", 0.9), ("sub-02", "no", 0.2), ("sub-03", "no", 0.1)]:
            for session, rank in [("ses-01", 1), ("ses-02", 2)]:
                rows.append(
                    {
                        "candidate_id": f"{subject_id}-{session}",
                        "subject_id": subject_id,
                        "image_id": f"{subject_id}_{session}",
                        "nms_rank": rank,
                        "pni_present": label,
                        "nerve_present": "yes" if label == "yes" else "no",
                        "tumor_nerve_relation": "touching" if label == "yes" else "none",
                        "prototype_score": base,
                        "text_pni_score": base - 0.01,
                        "nerve_score": base - 0.02,
                        "combined_score": base - 0.03,
                    }
                )
        return pd.DataFrame(rows)

    def test_cluster_bootstrap_is_deterministic_and_retains_failures(self):
        audit = self.bootstrap_fixture()
        first = cluster_bootstrap(audit, seed=17, n_replicates=30, max_k=2)
        second = cluster_bootstrap(audit, seed=17, n_replicates=30, max_k=2)
        pd.testing.assert_frame_equal(first, second)

        auc = first[(first.analysis_family == "score") & (first.metric == "roc_auc")]
        self.assertEqual(len(auc), 30 * 4)
        self.assertTrue((auc.groupby(["score"]).size() == 30).all())
        self.assertGreater(int((~auc.valid).sum()), 0)
        self.assertEqual(set(auc.loc[~auc.valid, "failure_reason"]), {"single_outcome_class"})
        self.assertEqual(len(first[first.analysis_family == "capture"]), 30 * 4 * 2)

    def test_bootstrap_summary_accounts_for_every_requested_replicate(self):
        audit = self.bootstrap_fixture()
        reps = cluster_bootstrap(audit, seed=5, n_replicates=20, max_k=2)
        point_budget = pd.DataFrame(
            [{"endpoint": endpoint, "k": k, "capture_fraction": 1.0} for endpoint in ["pni", "nerve", "pni_touching", "pni_surrounding"] for k in [1, 2]]
        )
        point_scores = compute_score_metrics(audit)
        budget, scores = attach_bootstrap_summary(point_budget, point_scores, reps, 20)
        self.assertTrue(
            (
                budget.n_bootstrap_valid.astype(int)
                + budget.n_bootstrap_undefined.astype(int)
                == 20
            ).all()
        )
        self.assertTrue(
            (
                scores.n_bootstrap_valid.astype(int)
                + scores.n_bootstrap_undefined.astype(int)
                == 20
            ).all()
        )


class EndToEndTests(unittest.TestCase):
    def test_run_audit_writes_required_outputs_without_mutating_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            image_id = "sub-01_ses-01"
            full = pd.DataFrame(
                {
                    "image_id": [image_id] * 4,
                    "mpp": [0.25] * 4,
                    "window_um": [300.0] * 4,
                    "x0": [0, 100, 200, 300],
                    "y0": [0] * 4,
                    "window_px": [100] * 4,
                    "tumor_fraction": [0.2] * 4,
                    "stroma_fraction": [0.8] * 4,
                    "labeled_fraction": [1.0] * 4,
                    "mask_priority": [0.5] * 4,
                    "rgb_tissue_fraction": [0.9] * 4,
                    "prototype_score": [0.9, 0.7, 0.3, 0.1],
                    "text_pni_score": [0.9, 0.7, 0.3, 0.1],
                    "nerve_score": [0.9, 0.7, 0.3, 0.1],
                    "prototype_score_pct": [1.0, 0.75, 0.5, 0.25],
                    "text_pni_score_pct": [1.0, 0.75, 0.5, 0.25],
                    "nerve_score_pct": [1.0, 0.75, 0.5, 0.25],
                    "combined_score": [1.0, 0.75, 0.5, 0.25],
                    "global_rank": [1, 2, 3, 4],
                    "image_rank": [1, 2, 3, 4],
                }
            )
            manifest = full.copy()
            manifest["within_slide_pct"] = [1.0, 0.75, 0.5, 0.25]
            manifest["selection_stratum"] = ["high", "high", "mid", "low_random"]
            manifest["review_order"] = [1, 2, 3, 4]
            manifest["candidate_id"] = ["C-1", "C-2", "C-3", "C-4"]
            review = manifest[
                ["candidate_id", "review_order", "image_id", "x0", "y0", "window_px", "window_um"]
            ].copy()
            review["reviewer_id"] = ""
            review["nerve_present"] = ["yes", "no", "no", "no"]
            review["pni_present"] = ["yes", "no", "no", "no"]
            review["tumor_nerve_relation"] = ["touching", "none", "none", "none"]
            review["confidence"] = ["high"] * 4
            review["notes"] = pd.NA
            paths = {
                "review": base / "review.csv",
                "manifest": base / "manifest.csv",
                "scores": base / "scores.csv",
                "candidate_config": base / "candidate_config.json",
                "build_summary": base / "build_summary.json",
            }
            review.to_csv(paths["review"], index=False)
            manifest.to_csv(paths["manifest"], index=False)
            full.to_csv(paths["scores"], index=False)
            paths["candidate_config"].write_text(
                json.dumps({"window_um": 300.0, "score_weights": {"prototype": 0.5, "text_pni": 0.35, "nerve": 0.15}})
            )
            paths["build_summary"].write_text(json.dumps({"seed": 20260803, "n_total": 4}))
            before = paths["review"].read_bytes()

            output = base / "audit"
            run_audit(output, **paths, seed=11, n_bootstrap=5, max_k=3)

            required = {
                "normalized_review.csv", "data_integrity_report.csv", "candidate_audit_table.csv",
                "review_budget_capture.csv", "score_metric_summary.csv", "cluster_bootstrap_replicates.csv",
                "subtype_and_stratum_summary.csv", "error_review_table.csv", "run_config.json",
                "RESULTS_REPORT.md", "fig_review_budget_capture.png", "fig_review_budget_capture.pdf",
                "fig_score_distributions.png", "fig_score_distributions.pdf",
            }
            self.assertEqual(required, {path.name for path in output.iterdir()})
            self.assertEqual(before, paths["review"].read_bytes())
            config = json.loads((output / "run_config.json").read_text())
            self.assertNotIn("run_config.json", config["output_sha256"])
            self.assertEqual(len(pd.read_csv(output / "normalized_review.csv")), 4)
if __name__ == "__main__":
    unittest.main()
