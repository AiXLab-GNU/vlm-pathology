from __future__ import annotations

import math
import json
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "infrastructure/packages/vlm_pathology_metrics/src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from vlm_pathology_metrics import (  # noqa: E402
    ALL_REGISTERED_MEASURES,
    ANALYSIS_CATALOG,
    CATALOG,
    COMBINATIONS,
    DISEASE_USES,
    REFERENCES,
    analysis_catalog,
    all_metric_disease_scopes,
    benjamini_hochberg,
    binary_discrimination,
    capture_fraction,
    catalog,
    dice_coefficient,
    disease_uses,
    exact_binomial_ci,
    export_catalog,
    get_measure,
    export_survey,
    frozen_combined_score,
    get_metric,
    metric_disease_scope,
    paired_effect,
    percentile_interval,
    recommend_combinations,
    review_coverage,
    top_k_precision,
)


class MetricCatalogTests(unittest.TestCase):
    def test_tier_files_and_web_catalog_are_synchronized(self):
        package_root = ROOT / "infrastructure/packages/vlm_pathology_metrics"
        tier_root = package_root / "src/vlm_pathology_metrics/data/medical"
        tier_files = sorted(tier_root.glob("tier*.tsv"))
        self.assertEqual(len(tier_files), 4)
        self.assertEqual(
            [path.read_text(encoding="utf-8").count("\n") - 1 for path in tier_files],
            [16, 12, 20, 10],
        )

        subprocess.run(
            [sys.executable, str(package_root / "scripts/build_web_catalog.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        web_data_path = package_root / "web/data/catalog-data.js"
        first_build = web_data_path.read_bytes()
        subprocess.run(
            [sys.executable, str(package_root / "scripts/build_web_catalog.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(first_build, web_data_path.read_bytes())
        web_data = first_build.decode("utf-8")
        prefix = "window.METRIC_CATALOG = "
        self.assertTrue(web_data.startswith(prefix))
        payload = json.loads(web_data.removeprefix(prefix).removesuffix(";\n"))
        self.assertEqual(payload["summary"]["medical_total"], len(CATALOG))
        self.assertEqual(payload["summary"]["analysis_total"], len(ANALYSIS_CATALOG))
        self.assertEqual(payload["summary"]["legacy_total"], 113)
        self.assertEqual(
            sum(len(item["parent_metric_ids"]) for item in payload["medical"]), 44
        )
        self.assertEqual(
            {item["metric_id"] for item in payload["medical"]},
            {item.metric_id for item in CATALOG},
        )
        self.assertEqual(
            set(payload["source"]), {"medical", "analysis", "legacy"}
        )

    def test_web_entrypoint_has_required_assets_and_mount_points(self):
        class StructureParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
                self.assets = []

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if "id" in attributes:
                    self.ids.append(attributes["id"])
                if tag == "script" and "src" in attributes:
                    self.assets.append(attributes["src"])
                if tag == "link" and "href" in attributes:
                    self.assets.append(attributes["href"])

        web_root = ROOT / "infrastructure/packages/vlm_pathology_metrics/web"
        parser = StructureParser()
        parser.feed((web_root / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue({
            "tier-map", "metric-network", "network-anchor-filter",
            "network-node-count", "network-edge-count", "lineage-graph",
            "metric-detail", "metric-grid", "analysis-bars", "source-paths",
        } <= set(parser.ids))
        self.assertEqual(
            parser.assets, ["styles.css", "data/catalog-data.js", "app.js"]
        )
        self.assertTrue(all((web_root / asset).is_file() for asset in parser.assets))

    def test_catalog_is_complete_unique_and_traceable(self):
        self.assertGreaterEqual(len(CATALOG), 50)
        self.assertEqual(len(CATALOG), len({item.metric_id for item in CATALOG}))
        self.assertEqual({item.tier for item in CATALOG}, {"T1", "T2", "T3", "T4"})
        self.assertFalse(any(item.metric_id.startswith("evaluation.") for item in CATALOG))
        self.assertTrue(any(item.metric_id == "evaluation.roc_auc" for item in ANALYSIS_CATALOG))
        self.assertEqual(
            len(ALL_REGISTERED_MEASURES),
            len({item.metric_id for item in ALL_REGISTERED_MEASURES}),
        )
        by_id = {item.metric_id: item for item in CATALOG}
        for item in CATALOG:
            if item.tier == "T1":
                self.assertFalse(item.parent_metric_ids)
            else:
                self.assertTrue(item.parent_metric_ids)
                self.assertTrue(set(item.parent_metric_ids) <= set(by_id))

    def test_catalog_filters_and_lookup(self):
        active = catalog(tier="T1", status="active")
        self.assertTrue(active)
        self.assertTrue(all(item.tier == "T1" for item in active))
        self.assertEqual(get_metric("pathology.isup_grade_group").tier, "T1")
        self.assertEqual(get_metric("contour.contact_length").status, "deferred")
        with self.assertRaises(KeyError):
            get_metric("evaluation.roc_auc")
        self.assertEqual(get_measure("evaluation.roc_auc").domain, "model_evaluation")
        self.assertTrue(analysis_catalog(domain="model_evaluation"))
        with self.assertRaises(KeyError):
            get_metric("not.a.metric")

    def test_catalog_exports_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            csv_path = export_catalog(root / "catalog.csv", format="csv")
            markdown_path = export_catalog(root / "catalog.md", format="markdown")
            self.assertEqual(csv_path.read_text(encoding="utf-8").count("\n"), len(CATALOG) + 1)
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("pathology.isup_grade_group", markdown)
            self.assertIn("contour.contact_length", markdown)


class GuardedCalculatorTests(unittest.TestCase):
    def test_frozen_combined_score_uses_immutable_weights(self):
        self.assertAlmostEqual(frozen_combined_score(0.9, 0.8, 0.7), 0.835)
        values = frozen_combined_score([0.0, 1.0], [0.0, 1.0], [0.0, 1.0])
        np.testing.assert_allclose(values, [0.0, 1.0])
        with self.assertRaises(ValueError):
            frozen_combined_score(1.1, 0.5, 0.5)

    def test_budget_metrics_never_treat_unreviewed_as_negative(self):
        self.assertEqual(capture_fraction(2, 4), 0.5)
        self.assertEqual(review_coverage(4, 5), 0.8)
        self.assertTrue(math.isnan(top_k_precision(2, 5, 4)))
        self.assertEqual(top_k_precision(2, 5, 5), 0.4)
        with self.assertRaises(ValueError):
            top_k_precision(5, 4, 4)

    def test_binary_discrimination_retains_single_class_failure(self):
        valid = binary_discrimination([0, 1], [0.1, 0.9])
        self.assertTrue(valid.valid)
        self.assertEqual(valid.roc_auc, 1.0)
        self.assertEqual(valid.average_precision, 1.0)
        undefined = binary_discrimination([1, 1], [0.1, 0.9])
        self.assertFalse(undefined.valid)
        self.assertEqual(undefined.failure_reason, "single_outcome_class")
        self.assertTrue(math.isnan(undefined.roc_auc))

    def test_uncertainty_helpers_account_for_undefined_replicates(self):
        summary = percentile_interval([0.1, float("nan"), 0.3])
        self.assertEqual((summary.requested, summary.valid, summary.undefined), (3, 2, 1))
        self.assertAlmostEqual(summary.undefined_fraction, 1 / 3)
        low, high = exact_binomial_ci(7, 7)
        self.assertAlmostEqual(low, 0.5903836027749966)
        self.assertEqual(high, 1.0)

    def test_image_spatial_and_multiplicity_helpers(self):
        self.assertEqual(dice_coefficient([1, 0, 1], [1, 1, 0]), 0.5)
        difference, ratio = paired_effect(0.4, 0.2)
        self.assertAlmostEqual(difference, 0.2)
        self.assertGreater(ratio, 0)
        np.testing.assert_allclose(
            benjamini_hochberg([0.01, 0.04, 0.03]),
            [0.03, 0.04, 0.04],
        )


class DiseaseSurveyTests(unittest.TestCase):
    def test_survey_links_are_unique_and_nonempty(self):
        self.assertGreaterEqual(len(REFERENCES), 20)
        self.assertGreaterEqual(len(DISEASE_USES), 18)
        self.assertGreaterEqual(len(COMBINATIONS), 20)
        self.assertEqual(len(REFERENCES), len({item.reference_id for item in REFERENCES}))
        self.assertEqual(len(DISEASE_USES), len({item.use_id for item in DISEASE_USES}))
        self.assertEqual(len(COMBINATIONS), len({item.combination_id for item in COMBINATIONS}))
        local_references = [item for item in REFERENCES if not item.url.startswith("https://")]
        self.assertTrue(local_references)
        self.assertTrue(all((ROOT / item.url).is_file() for item in local_references))
        self.assertTrue(all(
            item.url.startswith("https://pubmed.ncbi.nlm.nih.gov/")
            for item in REFERENCES if item.url.startswith("https://")
        ))
        medical_ids = {item.metric_id for item in CATALOG}
        analysis_ids = {item.metric_id for item in ANALYSIS_CATALOG}
        for item in (*DISEASE_USES, *COMBINATIONS):
            self.assertFalse(set(item.medical_metric_ids) & set(item.analysis_measure_ids))
            self.assertTrue(set(item.medical_metric_ids) <= medical_ids)
            self.assertTrue(set(item.analysis_measure_ids) <= analysis_ids)

    def test_every_metric_has_exactly_one_conservative_scope(self):
        scopes = all_metric_disease_scopes()
        self.assertEqual(len(scopes), len(ALL_REGISTERED_MEASURES))
        self.assertEqual(
            {item.metric_id for item in scopes},
            {item.metric_id for item in ALL_REGISTERED_MEASURES},
        )
        self.assertTrue(all(not item.standalone_diagnostic_use for item in scopes))
        self.assertTrue(
            metric_disease_scope("spatial.amacr_positive_fraction")
            .diagnostic_adjuvant_mapping
        )
        self.assertFalse(
            metric_disease_scope("evaluation.roc_auc").standalone_diagnostic_use
        )

    def test_disease_selection_preserves_readiness_boundaries(self):
        pni = disease_uses(disease_id="prostate_pni")
        self.assertEqual({item.package_readiness for item in pni}, {
            "ready_project", "deferred_until_contours",
        })
        ready = recommend_combinations("prostate_pni", readiness="ready_project")
        self.assertEqual([item.combination_id for item in ready], ["C002"])
        self.assertEqual(
            recommend_combinations("prostate_spop")[0].package_readiness,
            "unsupported_current_design",
        )

    def test_survey_export_contains_all_normalized_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            outputs = export_survey(temporary)
            self.assertEqual({path.name for path in outputs}, {
                "all_metric_disease_scopes.csv",
                "disease_metric_uses.csv",
                "metric_combinations.csv",
                "survey_references.csv",
            })
            scope_csv = (Path(temporary) / "all_metric_disease_scopes.csv").read_text(
                encoding="utf-8"
            )
            self.assertEqual(scope_csv.count("\n"), len(ALL_REGISTERED_MEASURES) + 1)
            self.assertIn("standalone_diagnostic_use", scope_csv)


if __name__ == "__main__":
    unittest.main()
    analysis_catalog,
