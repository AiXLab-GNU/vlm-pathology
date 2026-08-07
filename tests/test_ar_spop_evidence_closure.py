"""Tests for the approved R5 AR/SPOP evidence-closure analysis."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "models/build_ar_spop_evidence_closure.py"
REAL_INPUTS = all(
    (ROOT / path).exists()
    for path in (
        "models/tcga_prad_conch_cache/X.npy",
        "models/tcga_prad_conch_cache/meta.csv",
        "models/tcga_prad_clinical_extra/prad_pub_sample_clinical.json",
        "opendataset/TCGA-PRAD/manifest.csv",
        "models/ar_site_forest_summary.csv",
    )
)

if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location("ar_spop_closure", SCRIPT)
    closure = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(closure)
else:
    closure = None


@unittest.skipIf(closure is None, "R5 entry point not implemented")
class ArSpopUnitTests(unittest.TestCase):
    def test_hanley_mcneil_mde_matches_frozen_values(self):
        self.assertAlmostEqual(
            closure.minimum_detectable_auroc(29, 244, power=0.80),
            0.6613666946979635,
            places=14,
        )
        self.assertAlmostEqual(
            closure.minimum_detectable_auroc(29, 244, power=0.90),
            0.6847459836958563,
            places=14,
        )
        self.assertGreater(
            closure.minimum_detectable_auroc(29, 244, power=0.90),
            closure.minimum_detectable_auroc(29, 244, power=0.80),
        )

    def test_bootstrap_preserves_every_undefined_draw(self):
        result = closure.bootstrap_patient_auc(
            np.array([0.1, 0.2, 0.3]), np.array([0, 0, 0]), n_boot=25, seed=0
        )
        self.assertEqual(result["n_bootstrap_requested"], 25)
        self.assertEqual(result["n_bootstrap_valid"], 0)
        self.assertEqual(result["n_bootstrap_undefined"], 25)
        self.assertTrue(np.isnan(result["ci_low"]))
        self.assertEqual(result, closure.bootstrap_patient_auc(
            np.array([0.1, 0.2, 0.3]), np.array([0, 0, 0]), n_boot=25, seed=0
        ))

    def test_ar_descriptors_are_patient_level_but_forest_effect_is_slide_level(self):
        slides = pd.DataFrame(
            {
                "file_name": ["a1", "a2", "b1", "c1"],
                "case_id": ["TCGA-AA-1", "TCGA-AA-1", "TCGA-AA-2", "TCGA-BB-1"],
                "site": ["AA", "AA", "AA", "BB"],
                "ar_score": [0.0, 0.0, 10.0, 5.0],
                "gleason_sum": [6.0, 6.0, 8.0, 7.0],
                "spop_mut": [0, 0, 1, 0],
            }
        )
        forest = pd.DataFrame(
            [{"site": "AA", "n_slides": 3, "n_patients": 2, "rho": 0.2,
              "ci_lo": -0.1, "ci_hi": 0.4, "kind": "leave-one-site-out"}]
        )
        result = closure.build_ar_site_characteristics(slides, forest, min_site_slides=3)
        aa = result.set_index("site").loc["AA"]
        self.assertEqual(aa.ar_median, 5.0)
        self.assertEqual(aa.gleason_median, 7.0)
        self.assertEqual(aa.loo_metric_unit, "slide")
        self.assertEqual(aa.bootstrap_unit, "patient_cluster")
        self.assertTrue(aa.forest_eligible)
        self.assertFalse(result.set_index("site").loc["BB"].forest_eligible)

    def test_ar_forest_rows_require_unique_finite_count_alignment(self):
        slides = pd.DataFrame({
            "file_name": ["a1", "a2"], "case_id": ["TCGA-AA-1", "TCGA-AA-2"],
            "site": ["AA", "AA"], "ar_score": [1.0, 2.0],
            "gleason_sum": [7.0, 8.0], "spop_mut": [0, 1],
        })
        valid = {"site": "AA", "n_slides": 2, "n_patients": 2, "rho": 0.2,
                 "ci_lo": -0.1, "ci_hi": 0.4, "kind": "leave-one-site-out"}
        broken = [
            pd.DataFrame([{**valid, "n_slides": 3}]),
            pd.DataFrame([valid, valid]),
            pd.DataFrame([{**valid, "rho": np.nan}]),
            pd.DataFrame([{**valid, "rho": 2.0}]),
            pd.DataFrame([{**valid, "ci_lo": 0.5, "ci_hi": -0.5}]),
            pd.DataFrame([valid, {**valid, "site": "ZZ"}]),
        ]
        for forest in broken:
            with self.subTest(rows=len(forest), rho=forest.iloc[0].rho), self.assertRaisesRegex(
                closure.EvidenceClosureError, "forest row"
            ):
                closure.build_ar_site_characteristics(slides, forest, min_site_slides=2)

    def test_spop_summary_keeps_all_sites_and_historical_rule_is_explicit(self):
        rows = []
        for site, n, positives in (("AA", 20, 5), ("BB", 20, 4), ("CC", 3, 1)):
            for index in range(n):
                rows.append({
                    "file_name": f"{site}-{index}", "case_id": f"TCGA-{site}-{index}",
                    "site": site, "spop_mut": int(index < positives),
                })
        slides = pd.DataFrame(rows)
        predictions = pd.DataFrame(
            [{
                "record_level": "slide", "held_out_site": row.site,
                "file_name": row.file_name, "case_id": row.case_id,
                "true_label": row.spop_mut, "predicted_probability": index / 100,
                "n_component_slides": 1,
            } for index, row in slides[slides.site.isin(["AA", "BB"])].iterrows()]
        )
        summary = closure.build_spop_site_summary(
            slides, predictions, min_site_slides=20, n_boot=20, seed=0
        ).set_index("site")
        self.assertEqual(set(summary.index), {"AA", "BB", "CC"})
        self.assertTrue(summary.loc["AA", "historical_slide_reportable"])
        self.assertFalse(summary.loc["BB", "historical_slide_reportable"])
        self.assertFalse(summary.loc["CC", "large_site_eligible"])

    def test_header_scan_never_reads_pixels_or_infers_stain(self):
        class Tag:
            def __init__(self, value): self.value = value

        class Page:
            tags = {
                "ImageDescription": Tag(
                    "Aperio|AppMag = 40|MPP = 0.25|ScanScope ID = SS1|ICC Profile = ScanScope v1"
                ),
                "ImageWidth": Tag(10), "ImageLength": Tag(20),
            }
            def asarray(self): raise AssertionError("pixel read is forbidden")

        class FakeTiff:
            pages = [Page()]
            def __enter__(self): return self
            def __exit__(self, *args): return False

        with patch.object(closure.tifffile, "TiffFile", return_value=FakeTiff()):
            result = closure.scan_slide_header(Path("fake.svs"))
        self.assertEqual(result["scanscope_id_raw"], "SS1")
        self.assertEqual(result["appmag_raw"], "40")
        self.assertTrue(result["icc_profile_available"])
        self.assertEqual(result["icc_profile_raw"], "ScanScope v1")
        self.assertFalse(result["explicit_stain_field_available"])
        self.assertEqual(result["stain_metadata_status"], "not_available")
        self.assertEqual(len(result["canonical_header_sha256"]), 64)

    def test_header_scan_recognizes_binary_icc_tag_without_textual_field(self):
        class Tag:
            def __init__(self, value, name): self.value, self.name = value, name
        class Page:
            tags = {
                "ImageDescription": Tag("Aperio|AppMag = 40|MPP = 0.25", "ImageDescription"),
                34675: Tag(b"icc-bytes", "InterColorProfile"),
            }
        class FakeTiff:
            pages = [Page()]
            def __enter__(self): return self
            def __exit__(self, *args): return False
        with patch.object(closure.tifffile, "TiffFile", return_value=FakeTiff()):
            result = closure.scan_slide_header(Path("fake.svs"))
        self.assertTrue(result["icc_profile_available"])
        self.assertTrue(result["icc_profile_raw"].startswith("sha256:"))

    def test_manifest_omits_full_slide_hash_and_its_own_hash(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.csv"; source.write_text("x\n1\n", encoding="utf-8")
            output = root / "out.csv"; output.write_text("x\n2\n", encoding="utf-8")
            slide = pd.DataFrame([{
                "file_name": "slide.svs", "gdc_file_id": "id", "expected_file_size": 9,
                "actual_file_size": 9, "canonical_header_sha256": "a" * 64,
            }])
            snapshots = closure.snapshot_files([source], root)
            manifest = closure.build_manifest(
                root, snapshots, snapshots, {source: "cache_meta"}, slide, [output],
                root / closure.MANIFEST_NAME, "2026-08-06T00:00:00Z", 1.0,
            )
            slide_row = manifest.loc[manifest.artifact_role.eq("svs_header_only")].iloc[0]
            self.assertEqual(slide_row.gdc_file_id, "id")
            self.assertEqual(slide_row.full_file_sha256_status, "not_computed_large_input")
            self.assertEqual(slide_row.sha256_before, "")
            self_row = manifest.loc[manifest.artifact_path.eq(closure.MANIFEST_NAME)].iloc[0]
            self.assertEqual(self_row.sha256_after, "")
            self.assertEqual(self_row.hash_exclusion_reason, "self_referential_manifest")

    def test_gdc_identifiers_must_be_complete_and_unique(self):
        valid = pd.DataFrame({"file_id": ["id-a", "id-b"]})
        closure.validate_gdc_identifiers(valid, expected_count=2)
        for values in (["id-a", ""], ["id-a", "id-a"]):
            with self.subTest(values=values), self.assertRaisesRegex(
                closure.EvidenceClosureError, "GDC file_id"
            ):
                closure.validate_gdc_identifiers(pd.DataFrame({"file_id": values}), expected_count=2)


@unittest.skipIf(closure is None or not REAL_INPUTS, "real R5 inputs absent")
class ArSpopRealIntegrationTests(unittest.TestCase):
    def test_real_run_matches_audited_counts_and_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = closure.run_analysis(ROOT, Path(temporary_directory))
            ar = pd.read_csv(result[closure.AR_NAME])
            metadata = pd.read_csv(result[closure.METADATA_NAME])
            spop = pd.read_csv(result[closure.SPOP_NAME]).set_index("site")
            power = pd.read_csv(result[closure.POWER_NAME])
            predictions = pd.read_csv(result[closure.PREDICTIONS_NAME])
            config = __import__("json").loads(Path(result[closure.CONFIG_NAME]).read_text())
            self.assertEqual(len(ar), 22)
            self.assertEqual(len(metadata), 300)
            self.assertEqual(len(spop), 22)
            self.assertEqual(len(power), 2)
            self.assertEqual(set(ar.loc[ar.forest_eligible, "site"]), {"CH", "EJ", "G9", "HC", "KK", "YL"})
            self.assertEqual(int(ar.loc[ar.forest_eligible, "n_slides"].sum()), 224)
            self.assertEqual(int(ar.loc[ar.forest_eligible, "n_patients"].sum()), 209)
            self.assertEqual(set(spop.index[spop.historical_slide_reportable]), {"EJ", "KK", "YL"})
            self.assertEqual(int(metadata.scanscope_id_available.sum()), 280)
            self.assertEqual(int(metadata.explicit_stain_field_available.sum()), 0)
            self.assertTrue((metadata.stain_metadata_status == "not_available").all())
            expected = {
                "CH": (np.nan, 0, 2000), "EJ": (0.61264, 2000, 0),
                "G9": (0.70000, 1766, 234), "HC": (0.75758, 1908, 92),
                "KK": (0.57333, 1998, 2), "YL": (0.62500, 1969, 31),
            }
            for site, (auc, valid, undefined) in expected.items():
                row = spop.loc[site]
                if np.isnan(auc): self.assertTrue(np.isnan(row.patient_auroc))
                else: self.assertAlmostEqual(row.patient_auroc, auc, places=5)
                self.assertEqual(row.n_bootstrap_valid, valid)
                self.assertEqual(row.n_bootstrap_undefined, undefined)
            self.assertEqual(len(predictions), 433)
            caveat = config["slide_io"]["scanner_site_interpretation"].lower()
            self.assertIn("confound", caveat)
            self.assertIn("causal", caveat)
            self.assertEqual(power.n_positive.unique().tolist(), [29])
            self.assertEqual(power.n_negative.unique().tolist(), [244])
            corrupted = spop.reset_index()
            corrupted.loc[corrupted.site.eq("EJ"), "patient_auroc"] = 0.5
            with self.assertRaisesRegex(closure.EvidenceClosureError, "SPOP audited value"):
                closure._validate_real_outputs(ar, metadata, corrupted, power, predictions)

    def test_real_clean_rerun_csvs_and_config_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first, second = root / "first", root / "second"
            closure.run_analysis(ROOT, first)
            closure.run_analysis(ROOT, second)
            for name in (closure.AR_NAME, closure.METADATA_NAME, closure.SPOP_NAME,
                         closure.POWER_NAME, closure.PREDICTIONS_NAME, closure.CONFIG_NAME):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)
            a = pd.read_csv(first / closure.MANIFEST_NAME, dtype=str, keep_default_na=False)
            b = pd.read_csv(second / closure.MANIFEST_NAME, dtype=str, keep_default_na=False)
            pd.testing.assert_frame_equal(
                closure.normalize_manifest_for_comparison(a),
                closure.normalize_manifest_for_comparison(b),
            )


class ArSpopRedGateTests(unittest.TestCase):
    def test_required_entry_point_exists(self):
        self.assertTrue(SCRIPT.exists(), "R5 RED: evidence-closure entry point is missing")


if __name__ == "__main__":
    unittest.main()
