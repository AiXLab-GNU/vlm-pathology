"""Behavior tests for the Gate E final manuscript claim artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from projects.prostate_biomarker_validation.code.legacy import build_revision_p0_artifacts as p0
from projects.prostate_biomarker_validation.paper.figures import fig9_scale_tile_heatmap as fig9


ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / ".venv/bin/python"
FIG9_SCRIPT = ROOT / "projects/prostate_biomarker_validation/paper/figures/fig9_scale_tile_heatmap.py"
FIG3_SCRIPT = ROOT / "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.py"
FIG3_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig3_primary_snapshot.csv"
CORE_RESULTS = ROOT / "projects/prostate_biomarker_validation/paper/sections/core_marker_results.tex"
INTRODUCTION = ROOT / "projects/prostate_biomarker_validation/paper/sections/introduction.tex"
QUALIFICATION_GATES = ROOT / "projects/prostate_biomarker_validation/paper/sections/qualification_gates.tex"
DOWNSTREAM_TRANSFER = ROOT / "projects/prostate_biomarker_validation/paper/sections/downstream_recurrence_transfer.tex"
FAILURE_MODES = ROOT / "projects/prostate_biomarker_validation/paper/sections/failure_modes.tex"
ACTIVE_SECTION_SOURCES = tuple(sorted((ROOT / "projects/prostate_biomarker_validation/paper/sections").glob("*.tex")))
GRID_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_grid.csv"
CONTRAST_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_contrasts.csv"
QC_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json"
R2_CELLS_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv"
R2_DELTAS_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_paired_deltas.csv"
R2_MEMBERSHIP_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_membership_manifest.csv"
R5_AR_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv"
R5_METADATA_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv"
R5_SPOP_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv"
R5_POWER_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv"
R5_PREDICTIONS_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_predictions.csv"
R3_MAPPING_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv"
R3_CONCORDANCE_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv"
R3_PERFORMANCE_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv"
R3_MANIFEST_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_run_manifest.csv"
R4_SUMMARY_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_common_cohort_summary.csv"
R4_DELTAS_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv"
R4_MANIFEST_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_run_manifest.csv"
CONFOUNDER_NESTED_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv"
CONFOUNDER_REFIT_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_refit_permutation_final2000_summary.csv"
BENCHMARK_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv"
RECURRENCE_ONLY_SOURCE = ROOT / "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv"
SUBMISSION_FIGURE_DIR = ROOT / "projects/prostate_biomarker_validation/paper/figure_data"
ALLOWED_EVIDENCE_STATES = {
    "transportable",
    "context_sensitive",
    "unsupported_in_frozen_design",
    "descriptive_framework",
}
COMMON_SUBMISSION_COLUMNS = (
    "semantic_key",
    "evidence_state",
    "primary_estimate",
    "missingness_status",
    "missingness_detail",
    "source_path",
    "source_field",
)
EXPECTED_SUBMISSION_SCHEMAS = {
    "fig1_qualification_map.csv": (
        "semantic_key", "claim_id", "display_order", "claim_label", "marker",
        "hierarchy", "evidence_state", "qualification_decision", "limitation",
        "primary_estimate", "missingness_status", "missingness_detail", "source_path",
        "source_field",
    ),
    "fig2_transportable_signals.csv": (
        "semantic_key", "signal", "cohort", "institution", "encoder", "metric",
        "analysis_unit", "n", "n_events", "primary_estimate", "ci_low", "ci_high",
        "evidence_state", "missingness_status", "missingness_detail", "source_path",
        "source_field",
    ),
    "fig3_molecular_qualification.csv": (
        "semantic_key", "target", "component", "cohort", "encoder", "metric",
        "analysis_unit", "patient_denominator", "event_count", "null_value",
        "primary_estimate", "interval_low", "interval_high", "interval_type",
        "range_low", "range_high", "n_correlated_cells", "evidence_state",
        "missingness_status", "missingness_detail", "source_path", "source_field",
    ),
    "fig4_confounder_site_audit.csv": (
        "semantic_key", "target", "audit_type", "site", "encoder", "metric",
        "analysis_unit", "cluster_unit", "interval_type", "n_slides", "n_patients",
        "n_events", "primary_estimate", "ci_low", "ci_high", "null_value",
        "evidence_state", "missingness_status", "missingness_detail", "source_path", "source_field",
    ),
    "fig5_marker7_transfer.csv": (
        "semantic_key", "endpoint_id", "endpoint_label", "result_type", "contrast_id",
        "metric", "n", "n_events", "primary_estimate", "ci_low", "ci_high",
        "null_value", "evidence_state", "missingness_status", "missingness_detail",
        "source_path", "source_field",
    ),
    "fig6_stability_overview.csv": (
        "semantic_key", "marker", "component", "metric", "null_value",
        "primary_estimate", "range_low", "range_high", "n_configurations",
        "n_correlated_cells", "n_null_crossings", "n_contrasts", "evidence_state",
        "missingness_status", "missingness_detail", "source_path", "source_field",
    ),
}
GATE_B_MANUSCRIPT_SOURCES = (
    ROOT / "projects/prostate_biomarker_validation/paper/main.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/abstract.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/prespecified_exploratory.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/qualification_gates.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/core_marker_results.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/confounder_site_audits.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/failure_modes.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/downstream_recurrence_transfer.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/limitations.tex",
    ROOT / "projects/prostate_biomarker_validation/paper/sections/supplement.tex",
)


class SubmissionFigureSourceContractTests(unittest.TestCase):
    """Catch malformed or semantically incomplete submission-facing numeric sources."""

    def test_submission_figure_sources_have_exact_schemas_and_valid_lineage(self):
        minimum_rows = {
            "fig1_qualification_map.csv": 7,
            "fig2_transportable_signals.csv": 4,
            "fig3_molecular_qualification.csv": 6,
        }
        for name, expected_schema in EXPECTED_SUBMISSION_SCHEMAS.items():
            with self.subTest(name=name):
                path = SUBMISSION_FIGURE_DIR / name
                self.assertTrue(path.is_file(), f"missing submission source: {name}")
                frame = pd.read_csv(path)
                self.assertEqual(tuple(frame.columns), expected_schema)
                self.assertFalse(frame["semantic_key"].duplicated().any())
                self.assertTrue(frame["semantic_key"].astype(str).str.len().gt(0).all())
                self.assertTrue(frame["evidence_state"].isin(ALLOWED_EVIDENCE_STATES).all())
                self.assertTrue(pd.to_numeric(frame["primary_estimate"], errors="coerce").notna().all())
                self.assertTrue(frame["missingness_status"].astype(str).str.len().gt(0).all())
                self.assertTrue(frame["missingness_detail"].astype(str).str.len().gt(0).all())
                self.assertTrue(frame["source_path"].astype(str).str.len().gt(0).all())
                self.assertTrue(frame["source_field"].astype(str).str.len().gt(0).all())
                if name in minimum_rows:
                    self.assertGreaterEqual(len(frame), minimum_rows[name])

                for row in frame.itertuples(index=False):
                    source_paths = str(row.source_path).split(";")
                    field_groups = str(row.source_field).split(";")
                    self.assertEqual(len(source_paths), len(field_groups))
                    for relative, fields in zip(source_paths, field_groups):
                        source = ROOT / relative
                        self.assertFalse(Path(relative).is_absolute())
                        self.assertTrue(source.is_file(), f"missing lineage source: {relative}")
                        source_columns = set(pd.read_csv(source, nrows=0).columns)
                        for field in fields.split("|"):
                            self.assertIn(field, source_columns, f"{field} absent from {relative}")

        qualification = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig1_qualification_map.csv")
        required_claim_fields = {
            "claim_id", "display_order", "claim", "marker", "hierarchy", "status",
            "reliability_tier", "limitation",
        }
        for source_field in qualification["source_field"]:
            self.assertTrue(required_claim_fields.issubset(set(str(source_field).split("|"))))

    def test_submission_sources_preserve_site_endpoint_and_grid_semantics(self):
        site_frame = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig4_confounder_site_audit.csv")
        self.assertEqual(
            set(site_frame.loc[site_frame["audit_type"].eq("ar_site_transport"), "site"]),
            {"CH", "EJ", "G9", "HC", "KK", "YL", "Pooled"},
        )
        nested_keys = set(
            site_frame.loc[site_frame["audit_type"].eq("grade_adjusted_increment"), "semantic_key"]
        )
        self.assertEqual(
            nested_keys,
            {"pten:CONCH:increment", "pten:Virchow:increment", "ar:CONCH:increment", "ar:Virchow:increment"},
        )
        held_out = site_frame.loc[
            site_frame["audit_type"].eq("ar_site_transport")
            & site_frame["site"].ne("Pooled")
        ]
        self.assertEqual(set(held_out["site"]), {"CH", "EJ", "G9", "HC", "KK", "YL"})
        self.assertTrue(held_out["analysis_unit"].eq("slide").all())
        self.assertTrue(held_out["cluster_unit"].eq("patient").all())
        self.assertTrue(held_out["interval_type"].eq("patient_cluster_bootstrap").all())
        self.assertTrue(held_out["n_slides"].notna().all())
        self.assertTrue(held_out["n_patients"].notna().all())
        required_ar_lineage = {"site", "n_slides", "n_patients", "rho", "ci_lo", "ci_hi", "kind"}
        for source_field in held_out["source_field"]:
            self.assertTrue(required_ar_lineage.issubset(set(str(source_field).split("|"))))
        pooled = site_frame.loc[
            site_frame["audit_type"].eq("ar_site_transport")
            & site_frame["site"].eq("Pooled")
        ].iloc[0]
        self.assertEqual(pooled["analysis_unit"], "patient")
        self.assertEqual(pooled["interval_type"], "patient_bootstrap")
        nested = site_frame.loc[site_frame["audit_type"].eq("grade_adjusted_increment")]
        self.assertTrue(nested["analysis_unit"].eq("patient").all())
        self.assertTrue(nested["interval_type"].eq("patient_bootstrap").all())

        transfer = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig5_marker7_transfer.csv")
        self.assertEqual(
            set(transfer["endpoint_id"]),
            {"E04_reconstructed_with_tumor", "E08_official_pfi"},
        )
        paired = transfer.loc[transfer["result_type"].eq("same_patient_same_draw_delta")]
        self.assertEqual(set(paired["endpoint_id"]), {"E04_reconstructed_with_tumor", "E08_official_pfi"})
        self.assertTrue(paired["n"].eq(153).all())

        stability = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig6_stability_overview.csv")
        self.assertEqual(set(stability["marker"]), set(p0.STABILITY_MARKERS))
        self.assertEqual(set(stability["component"]), {"configuration_range", "contrast_sensitivity"})
        ranges = stability.loc[stability["component"].eq("configuration_range")]
        self.assertEqual(int(ranges["n_configurations"].sum()), 72)
        self.assertTrue(ranges["n_correlated_cells"].eq(60).all())

        molecular = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig3_molecular_qualification.csv")
        configuration = molecular.loc[molecular["component"].eq("configuration_summary")]
        self.assertEqual(set(configuration["target"]), {"PTEN", "SPOP", "AR"})
        self.assertTrue(configuration["interval_low"].isna().all())
        self.assertTrue(configuration["interval_high"].isna().all())
        self.assertTrue(configuration["range_low"].notna().all())
        self.assertTrue(configuration["range_high"].notna().all())
        self.assertTrue(configuration["n_correlated_cells"].eq(60).all())
        self.assertTrue(
            configuration["interval_type"].eq(
                "global_correlated_seed_cell_range"
            ).all()
        )

    def test_molecular_source_validator_rejects_legacy_configuration_range_token(self):
        molecular = pd.read_csv(
            SUBMISSION_FIGURE_DIR / "fig3_molecular_qualification.csv"
        )
        configuration = molecular["component"].eq("configuration_summary")
        molecular.loc[configuration, "interval_type"] = (
            "correlated_configuration_range"
        )
        with self.assertRaisesRegex(ValueError, "seed-cell ranges"):
            p0.validate_submission_source(
                "fig3_molecular_qualification.csv", molecular, ROOT
            )

    def test_binary_event_count_missingness_is_distinct_from_continuous_not_applicable(self):
        molecular = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig3_molecular_qualification.csv")
        binary_molecular = molecular.loc[
            molecular["target"].isin(["PTEN", "SPOP"])
            & molecular["component"].isin(["frozen_primary", "configuration_summary"])
        ]
        self.assertEqual(
            set(binary_molecular["semantic_key"]),
            {
                "pten:frozen_primary", "pten:configuration_summary",
                "spop:frozen_primary", "spop:configuration_summary",
            },
        )
        self.assertTrue(binary_molecular["event_count"].isna().all())
        self.assertTrue(
            binary_molecular["missingness_status"].eq(
                "event_count_not_recorded_in_source"
            ).all()
        )
        self.assertTrue(binary_molecular["missingness_detail"].str.startswith(
            "binary endpoint event count is applicable but not recorded in the saved source rows"
        ).all())

        continuous_molecular = molecular.loc[molecular["target"].eq("AR")]
        self.assertTrue(continuous_molecular["event_count"].isna().all())
        self.assertTrue(
            continuous_molecular["missingness_status"].eq(
                "event_count_not_applicable"
            ).all()
        )
        self.assertTrue(continuous_molecular["missingness_detail"].str.startswith(
            "continuous endpoint; event count not applicable"
        ).all())

        confounder = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig4_confounder_site_audit.csv")
        binary_confounder = confounder.loc[confounder["target"].eq("PTEN")]
        self.assertEqual(
            set(binary_confounder["semantic_key"]),
            {"pten:CONCH:increment", "pten:Virchow:increment"},
        )
        self.assertTrue(binary_confounder["n_events"].isna().all())
        self.assertTrue(
            binary_confounder["missingness_status"].eq(
                "event_count_not_recorded_in_source"
            ).all()
        )
        self.assertTrue(binary_confounder["missingness_detail"].str.startswith(
            "binary endpoint event count is applicable but not recorded in the saved source rows"
        ).all())

        continuous_confounder = confounder.loc[confounder["target"].eq("AR")]
        self.assertTrue(continuous_confounder["n_events"].isna().all())
        self.assertTrue(
            continuous_confounder["missingness_status"].eq(
                "event_count_not_applicable"
            ).all()
        )
        self.assertTrue(continuous_confounder["missingness_detail"].str.startswith(
            "continuous endpoint; event count not applicable"
        ).all())

    def test_claim_and_endpoint_artifacts_use_submission_states_and_distinct_official_pfi(self):
        claims = pd.read_csv(ROOT / "projects/prostate_biomarker_validation/paper/claim_evidence_matrix.csv")
        self.assertTrue(claims["status"].isin(ALLOWED_EVIDENCE_STATES).all())
        self.assertIn("completion_status", claims.columns)
        self.assertNotIn("robust null", claims.loc[claims["claim_id"].eq("C04"), "claim"].iloc[0].lower())
        endpoints = pd.read_csv(ROOT / "projects/prostate_biomarker_validation/paper/endpoint_hierarchy.csv")
        self.assertIn("E08_official_pfi", set(endpoints["endpoint_id"]))
        self.assertNotEqual(
            endpoints.set_index("endpoint_id").loc["E08_official_pfi", "event_definition"],
            endpoints.set_index("endpoint_id").loc["E04_reconstructed_with_tumor", "event_definition"],
        )

    def test_submission_sources_disclose_unavailable_legacy_bootstrap_accounting(self):
        transport = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig2_transportable_signals.csv")
        nadt = transport.loc[transport["cohort"].eq("NADT")]
        self.assertTrue(nadt["missingness_status"].eq("replicate_accounting_not_saved").all())
        self.assertTrue(nadt["missingness_detail"].str.contains("2,000 requested").all())
        self.assertTrue(nadt["missingness_detail"].str.contains("valid and undefined").all())

        molecular = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig3_molecular_qualification.csv")
        frozen = molecular.loc[molecular["component"].eq("frozen_primary")]
        self.assertTrue(frozen["missingness_detail"].str.contains("replicate accounting").all())
        confounder = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig4_confounder_site_audit.csv")
        interval_rows = confounder.loc[confounder["interval_type"].str.contains("bootstrap")]
        self.assertTrue(
            interval_rows["missingness_detail"].str.contains("replicate accounting").all()
        )

    def test_claim_locations_reference_only_active_scientific_reports_sections(self):
        claims = pd.read_csv(ROOT / "projects/prostate_biomarker_validation/paper/claim_evidence_matrix.csv").set_index("claim_id")
        expected = {
            "C01": "sections/results.tex; sections/discussion.tex",
            "C02": "sections/results.tex; sections/discussion.tex",
            "C03": "sections/results.tex; sections/discussion.tex",
            "C04": "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex",
            "C05": "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex",
            "C06": "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex",
            "C07": "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex",
            "C08": "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex",
        }
        self.assertEqual(claims["manuscript_location"].to_dict(), expected)

    def test_qualification_validator_requires_lineage_for_every_presented_claim_column(self):
        frame = pd.read_csv(SUBMISSION_FIGURE_DIR / "fig1_qualification_map.csv")
        frame.loc[0, "source_field"] = "display_order|status|reliability_tier|limitation"
        with self.assertRaisesRegex(ValueError, "presentation lineage"):
            p0.validate_submission_source("fig1_qualification_map.csv", frame, ROOT)

    def test_whole_package_publish_rolls_back_all_ten_artifacts_after_replace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            paper_dir = Path(tmp) / "paper"
            figure_dir = paper_dir / "figure_data"
            figure_dir.mkdir(parents=True)
            relative_outputs = (
                "claim_evidence_matrix.csv", "claim_evidence_matrix.md",
                "endpoint_hierarchy.csv", "endpoint_hierarchy.md",
                "figure_data/fig1_qualification_map.csv",
                "figure_data/fig2_transportable_signals.csv",
                "figure_data/fig3_molecular_qualification.csv",
                "figure_data/fig4_confounder_site_audit.csv",
                "figure_data/fig5_marker7_transfer.csv",
                "figure_data/fig6_stability_overview.csv",
            )
            before = {}
            for index, relative in enumerate(relative_outputs):
                path = paper_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = f"old-generation-{index}".encode()
                path.write_bytes(payload)
                before[relative] = payload
            legacy = {
                paper_dir / "generated/stability_grid_marker_summary.tex": b"legacy-table",
                paper_dir / "protocol_change_log.csv": b"legacy-log",
                paper_dir / "protocol_provenance.json": b"legacy-provenance",
            }
            for path, payload in legacy.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

            calls = 0

            def fail_once_after_four_replacements(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 5:
                    raise OSError("injected package publication failure")
                os.replace(source, destination)

            with self.assertRaisesRegex(OSError, "injected package publication failure"):
                p0.build_revision_submission_package(
                    ROOT, paper_dir, replace_fn=fail_once_after_four_replacements
                )

            for relative, payload in before.items():
                self.assertEqual((paper_dir / relative).read_bytes(), payload)
            for path, payload in legacy.items():
                self.assertEqual(path.read_bytes(), payload)


class Figure3PrimarySnapshotTests(unittest.TestCase):
    def test_active_snapshot_uses_final_endpoint_conditioned_scope(self):
        script = FIG3_SCRIPT.read_text(encoding="utf-8")
        source = FIG3_SOURCE.read_text(encoding="utf-8")
        manuscript = CORE_RESULTS.read_text(encoding="utf-8")
        manuscript_flat = " ".join(manuscript.split())
        figure_sources = script + "\n" + source
        active = figure_sources + "\n" + manuscript

        for stale in (
            "both null", "large gap", "Virchow fails", "not with Virchow",
            "Gate A interim; Gate B pending", "Gate B/common-498 pending",
            "Common-498/PFI pending",
        ):
            self.assertNotIn(stale, active)
        for scoped in (
            "Frozen primary-configuration", "Primary unsupported",
            "Neither robust positive nor null", "Endpoint/encoder/scale-limited",
            "Official PFI complete; interval includes 0.5",
        ):
            self.assertIn(scoped, figure_sources)
        self.assertIn(r"figures/fig3_conch_vs_virchow.pdf", manuscript)
        self.assertIn("frozen primary-configuration snapshot", manuscript_flat)
        self.assertIn("distinct from the correlated Gate A grid", manuscript_flat)
        self.assertIn("unsupported in the frozen primary configuration", manuscript_flat)
        self.assertIn("neither a robust positive nor a robust null", manuscript_flat)
        self.assertIn("common-498 R2 is complete", manuscript_flat)
        self.assertIn("official-PFI C-index interval includes 0.5", manuscript_flat)
        self.assertIn("does not establish robust independent prognostic value", manuscript_flat)
        self.assertIn("fig3_primary_snapshot.csv", script)
        self.assertNotIn("DATA = [", script)
        self.assertIn("markers 1--3 and 7 are patient-level", manuscript_flat)
        self.assertIn("markers 4--6 are slide-level", manuscript_flat)

    def test_saved_source_contract_is_exact_and_fail_closed(self):
        from projects.prostate_biomarker_validation.paper.figures import fig3_conch_vs_virchow as fig3

        frame = fig3.load_snapshot(FIG3_SOURCE)
        self.assertEqual(
            frame.columns.tolist(),
            [
                "marker_id", "display_order", "marker_label", "cohort", "metric",
                "analysis_unit", "conch_value", "virchow_value", "note",
                "upstream_source", "upstream_fields",
            ],
        )
        self.assertEqual(frame["marker_id"].tolist(), list(range(1, 8)))
        self.assertEqual(
            frame.set_index("marker_id")["analysis_unit"].to_dict(),
            {1: "patient", 2: "patient", 3: "patient", 4: "slide", 5: "slide", 6: "slide", 7: "patient"},
        )
        self.assertAlmostEqual(
            float(frame.loc[frame["marker_id"] == 3, "conch_value"].iloc[0]),
            0.5244160374868407,
        )
        self.assertAlmostEqual(
            float(frame.loc[frame["marker_id"] == 4, "conch_value"].iloc[0]),
            0.6174008207934337,
        )
        self.assertEqual(float(frame.loc[frame["marker_id"] == 7, "virchow_value"].iloc[0]), 0.533)
        for sources in frame["upstream_source"]:
            for relative in sources.split(";"):
                self.assertTrue((ROOT / relative).is_file(), relative)
        self.assertTrue(frame["upstream_fields"].str.strip().ne("").all())

        source = pd.read_csv(FIG3_SOURCE)
        mutations = (
            ("missing schema column", lambda df: df.drop(columns=["metric"])),
            ("wrong marker key", lambda df: df.assign(marker_id=[1, 2, 3, 40, 5, 6, 7])),
            (
                "wrong aggregation unit",
                lambda df: df.assign(
                    analysis_unit=df["analysis_unit"].mask(df["marker_id"] == 4, "patient")
                ),
            ),
            (
                "wrong frozen value",
                lambda df: df.assign(
                    conch_value=df["conch_value"].mask(df["marker_id"] == 4, 0.999)
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "fig3.csv"
                mutate(source.copy()).to_csv(path, index=False)
                with self.assertRaises(ValueError):
                    fig3.load_snapshot(path)


class GateBManuscriptFramingTests(unittest.TestCase):
    def test_active_sources_integrate_completed_r2_through_r5_without_overclaiming(self):
        active = "\n".join(path.read_text(encoding="utf-8") for path in GATE_B_MANUSCRIPT_SOURCES)
        flat = " ".join(active.split())

        for stale in (
            "pending Gate B", "Gate B pending", "awaits Gate B", "deferred to Gate B",
            "finalizes the Gate B", "INTERIM GATE A WORKING MANUSCRIPT",
            "R2 analysis remains pending", "R2 remains pending", "pending common-498 R2",
            "common-498 R2 and official-PFI R3 analyses remain pending",
            "evidence closure remains pending R5", "R5 evidence-closure dependencies",
            "R2--R5 evidence-closure analyses remain pending",
            "official-PFI R3 remains pending", "Official PFI remains unassessed",
            "Official PFI remains unassessed pending R3", "R4 remains required",
            "C07 cannot be finalized before R4", "paired common-cohort R4 remains pending",
        ):
            self.assertNotIn(stale, active)

        for global_scope in (
            "did not overturn the prior directional observations",
            "bounds generalizability across configuration, endpoint, encoder, and site",
            "unresolved rather than contrary evidence",
        ):
            self.assertIn(global_scope, flat)

        for c04_scope in (
            "unsupported in the frozen primary configuration",
            "neither a robust positive nor a robust null",
            "modest effect and tumor dilution remain unresolved",
            "C04 evidence closure is complete",
            "scientific question remains unresolved",
        ):
            self.assertIn(c04_scope, flat)

        for c05_scope in (
            "positive pooled direction is consistent across the correlated Gate A settings",
            "site heterogeneity and transportability are neither supported nor refuted",
            "grade-independent increment remains unresolved",
            "No scanner, stain, or site causality is inferred",
            "C05 evidence closure is complete",
        ):
            self.assertIn(c05_scope, flat)

        for c06_scope in (
            "post-hoc, endpoint-specific exploratory signal",
            "effect size and transfer generalizability are limited by endpoint, encoder, and scale",
            "CONCH is higher in the current grid, while Virchow improves at the shared",
            "official PFI C-index was 0.586",
            "95\\% CI 0.482--0.689",
            "directionally non-contradictory but not strong support",
            "common-498 R2 sensitivity is complete",
        ):
            self.assertIn(c06_scope, flat)

        for c07_scope in (
            "same 153-patient complete-case cohort",
            "all official-PFI paired C-index and IBS intervals include zero",
            "does not establish robust independent or incremental prognostic value",
            "multiple imputation was not performed",
            "no PCA dimension is presented as an unbiased selected optimum",
        ):
            self.assertIn(c07_scope, flat)

        for r2_number in (
            "498 source patients and 85 source events",
            "270 target patients and 57 target events",
            "60 cells",
            "zero raw-to-common null crossings",
            "all 30 scale, 20 tile-budget, and 15 shared-scale encoder contrast directions",
            "-0.0023 to +0.0229",
        ):
            self.assertIn(r2_number, flat)

        for r5_number in (
            "224 slides and 209 patients",
            "280/300",
            "0/300",
            "EJ 0.613",
            "G9 0.700",
            "HC 0.758",
            "KK 0.573",
            "YL 0.625",
            "2,000, 0, 234, 92, 2, and 31",
            "0.661/0.685",
            "not effect-exclusion bounds",
        ):
            self.assertIn(r5_number, flat)

        for overclaim in (
            "rules out large effects above roughly 0.63",
            "establishes a robust SPOP null",
            "demonstrates a robust SPOP null",
            "scanner caused the effect", "stain caused the effect", "site caused the effect",
            "shows that scale causally improves transfer", "demonstrates universal encoder superiority",
            "constitutes independent replication of marker 7",
        ):
            self.assertNotIn(overclaim, flat)
        for required_negation in (
            "does not establish a causal scale effect or universal encoder superiority",
            "No scanner, stain, or site causality is inferred",
        ):
            self.assertIn(required_negation, flat)

    def test_active_c07_increment_language_is_final_but_narrow_after_r4(self):
        active = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "projects/prostate_biomarker_validation/paper/main.tex", *ACTIVE_SECTION_SOURCES)
        )
        flat = " ".join(active.split())

        for overclaim in (
            "it does not add to a full clinical+site model",
            "shows a held-out increment over grade alone",
            "changes the conclusion",
            "it adds over grade alone",
            "it adds held-out discrimination beyond a grade-only model",
            "risk and does not improve it",
            "image score supplies no detectable held-out increment",
            "does not improve discrimination",
            "confirming no held-out image increment",
            "grade-only increment for the post-hoc recurrence predictor",
            "marker 7's grade-only increment was",
            "establishes robust independent prognostic value",
            "clinically independent prognostic marker",
        ):
            self.assertNotIn(overclaim, flat)

        for final_scope in (
            "same-patient/same-draw R4 analysis",
            "reconstructed endpoint grade-plus-image versus grade delta C-index",
            "its paired IBS interval includes zero",
            "all official-PFI paired C-index and IBS intervals include zero",
            "does not establish robust independent or incremental prognostic value",
        ):
            self.assertIn(final_scope, flat)

    def test_active_marker7_language_is_descriptive_not_prognostic(self):
        downstream = " ".join(DOWNSTREAM_TRANSFER.read_text(encoding="utf-8").split())
        failure_modes = " ".join(FAILURE_MODES.read_text(encoding="utf-8").split())
        active_sections = " ".join(
            "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_SECTION_SOURCES).split()
        )

        for scoped in (
            "post-hoc descriptive observations",
            "unsupported or uncertain result",
            "not proof of prognostic validity, a causal mechanism, or a probability of chance discovery",
        ):
            self.assertIn(scoped, failure_modes)
        for categorical in (
            "found real signal", "genuine prognostic signal", "demonstrably exists",
            "contain real signal", "marker is real", "demonstrably present",
            "discovered'' this signal by chance",
            "carried real and cross-encoder-reproducible recurrence signal",
            "claimed null or uncertain one",
        ):
            self.assertNotIn(categorical, active_sections)
        for descriptive in (
            "exploratory in-cohort discrimination",
            "descriptive cross-encoder convergence",
            "does not establish prognostic validity, a causal mechanism, or a probability of chance discovery",
        ):
            self.assertIn(descriptive, downstream)
        for preserved_observation in (
            r"C-index $0.598$--$0.661$",
            r"$\rho=-0.42$, $p<10^{-4}$",
            r"C-index $0.622$--$0.675$",
            r"$\rho=+0.74$",
        ):
            self.assertIn(preserved_observation, downstream)

    def test_active_tier_uses_unsupported_without_equating_it_to_biological_null(self):
        active = " ".join(
            (INTRODUCTION.read_text(encoding="utf-8") + "\n" +
             QUALIFICATION_GATES.read_text(encoding="utf-8")).split()
        )

        self.assertIn(r"\emph{unsupported}", active)
        self.assertNotIn(r"\emph{unsupported-null}", active)
        self.assertNotIn(
            r"\emph{unsupported/null} (fails multiple-comparison correction",
            active,
        )
        self.assertIn(r"historical protocol label was \emph{unsupported/null}", active)
        self.assertIn(
            "statistical non-support under the tested design, not proof of a biological null",
            active,
        )

    def test_introduction_describes_marker7_as_endpoint_conditioned_without_dichotomy(self):
        introduction = " ".join(INTRODUCTION.read_text(encoding="utf-8").split())

        for categorical in (
            "contains real and cross-encoder-reproducible recurrence signal",
            "the marker is not real", "the marker is real but does not transfer",
            "discard a real signal",
        ):
            self.assertNotIn(categorical, introduction)
        self.assertIn(
            "post-hoc recurrence signal for transfer",
            introduction,
        )
        self.assertIn(
            "not another encoder or a deployable classifier",
            introduction,
        )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Figure9BehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.grid = self.root / "fig9_stability_grid.csv"
        self.contrasts = self.root / "fig9_stability_contrasts.csv"
        shutil.copyfile(GRID_SOURCE, self.grid)
        shutil.copyfile(CONTRAST_SOURCE, self.contrasts)
        self.pdf = self.root / "figure.pdf"
        self.png = self.root / "figure.png"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_renderer(self, *, expect_success: bool = True) -> subprocess.CompletedProcess:
        completed = subprocess.run(
            [
                str(PYTHON), str(FIG9_SCRIPT),
                "--grid-csv", str(self.grid),
                "--contrasts-csv", str(self.contrasts),
                "--output-pdf", str(self.pdf),
                "--output-png", str(self.png),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if expect_success and completed.returncode != 0:
            self.fail(completed.stderr or completed.stdout)
        if not expect_success and completed.returncode == 0:
            self.fail("renderer unexpectedly accepted invalid figure inputs")
        return completed

    def test_cli_renders_supplied_sources_and_reports_lineage(self):
        completed = self.run_renderer()

        self.assertTrue(self.pdf.is_file())
        self.assertTrue(self.png.is_file())
        record = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(record["grid_rows"], 72)
        self.assertEqual(record["contrast_rows"], 390)
        self.assertEqual(record["grid_sha256"], file_sha256(self.grid))
        self.assertEqual(record["contrasts_sha256"], file_sha256(self.contrasts))
        self.assertEqual(Path(record["output_pdf"]), self.pdf)
        self.assertEqual(Path(record["output_png"]), self.png)

    def test_cli_rejects_missing_and_duplicate_keys_without_replacing_outputs(self):
        invalid_mutations = (
            ("missing grid key", self.grid, lambda frame: frame.iloc[:-1].copy()),
            ("duplicate grid key", self.grid, lambda frame: pd.concat([frame, frame.iloc[[0]]])),
            ("missing contrast key", self.contrasts, lambda frame: frame.iloc[:-1].copy()),
            ("duplicate contrast key", self.contrasts, lambda frame: pd.concat([frame, frame.iloc[[0]]])),
        )
        for label, path, mutate in invalid_mutations:
            with self.subTest(label=label):
                shutil.copyfile(GRID_SOURCE, self.grid)
                shutil.copyfile(CONTRAST_SOURCE, self.contrasts)
                frame = pd.read_csv(path)
                mutate(frame).to_csv(path, index=False)
                self.pdf.write_bytes(b"existing-pdf")
                self.png.write_bytes(b"existing-png")

                self.run_renderer(expect_success=False)

                self.assertEqual(self.pdf.read_bytes(), b"existing-pdf")
                self.assertEqual(self.png.read_bytes(), b"existing-png")

    def test_cli_rejects_a_replaced_contrast_key(self):
        contrasts = pd.read_csv(self.contrasts)
        contrasts.loc[0, "tiles_per_slide_a"] = 128
        contrasts.loc[0, "tiles_per_slide_b"] = 128
        contrasts.to_csv(self.contrasts, index=False)
        self.pdf.write_bytes(b"existing-pdf")
        self.png.write_bytes(b"existing-png")

        self.run_renderer(expect_success=False)

        self.assertEqual(self.pdf.read_bytes(), b"existing-pdf")
        self.assertEqual(self.png.read_bytes(), b"existing-png")

    def test_renderer_rejects_row_preserving_malformed_values_without_replacement(self):
        mutations = (
            ("fractional n_seeds", "grid", 0, "n_seeds", 5.5),
            ("fractional summary count", "grid", 0, "n_chance_or_worse", 1.5),
            ("out-of-range summary count", "grid", 0, "n_ties", 6),
            ("fractional summary axis", "grid", 0, "tiles_per_slide", 16.5),
            ("inexact summary scale", "grid", 0, "target_mpp", 0.881),
            ("malformed summary boolean", "grid", 0, "seed_null_straddle", "sometimes"),
            ("fractional contrast seed", "contrasts", 0, "sampling_seed", 0.5),
            ("malformed crossing boolean", "contrasts", 0, "null_crossing", "sometimes"),
            ("malformed tie boolean", "contrasts", 0, "exact_tie", "sometimes"),
            ("inconsistent relation", "contrasts", 0, "relation_a", "below_null"),
            ("inconsistent delta", "contrasts", 0, "delta_b_minus_a", 99.0),
            ("wrong cell identity", "contrasts", 0, "cell_id_a", "wrong-cell"),
            ("wrong pair identity", "contrasts", 0, "pair_id", "wrong-pair"),
        )
        for label, source, row, column, value in mutations:
            with self.subTest(label=label):
                shutil.copyfile(GRID_SOURCE, self.grid)
                shutil.copyfile(CONTRAST_SOURCE, self.contrasts)
                path = self.grid if source == "grid" else self.contrasts
                frame = pd.read_csv(path)
                frame[column] = frame[column].astype(object)
                frame.loc[row, column] = value
                frame.to_csv(path, index=False)
                self.pdf.write_bytes(b"existing-pdf")
                self.png.write_bytes(b"existing-png")

                with self.assertRaises(fig9.FigureDataError):
                    fig9.render_figure(self.grid, self.contrasts, self.pdf, self.png)

                self.assertEqual(self.pdf.read_bytes(), b"existing-pdf")
                self.assertEqual(self.png.read_bytes(), b"existing-png")

    def test_both_supplied_sources_affect_rendered_png(self):
        self.run_renderer()
        baseline = self.png.read_bytes()

        grid = pd.read_csv(self.grid)
        grid.loc[0, "mean"] = float(grid.loc[0, "mean"]) + 0.04
        grid.to_csv(self.grid, index=False)
        self.run_renderer()
        grid_changed = self.png.read_bytes()
        self.assertNotEqual(file_sha256_bytes(baseline), file_sha256_bytes(grid_changed))

        shutil.copyfile(GRID_SOURCE, self.grid)
        contrasts = pd.read_csv(self.contrasts)
        contrasts.loc[0, "patient_metric_b"] = -0.01
        contrasts.loc[0, "delta_b_minus_a"] = (
            contrasts.loc[0, "patient_metric_b"] - contrasts.loc[0, "patient_metric_a"]
        )
        contrasts.loc[0, "relation_b"] = "below_null"
        contrasts.loc[0, "null_crossing"] = True
        contrasts.to_csv(self.contrasts, index=False)
        self.run_renderer()
        contrast_changed = self.png.read_bytes()
        self.assertNotEqual(file_sha256_bytes(baseline), file_sha256_bytes(contrast_changed))


def file_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class P0ArtifactBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.grid = self.root / "stability_summary.csv"
        self.contrasts = self.root / "stability_contrast_summary.csv"
        self.qc = self.root / "stability_qc_report.json"
        shutil.copyfile(GRID_SOURCE, self.grid)
        shutil.copyfile(CONTRAST_SOURCE, self.contrasts)
        shutil.copyfile(QC_SOURCE, self.qc)
        self.r2_cells = self.root / R2_CELLS_SOURCE.name
        self.r2_deltas = self.root / R2_DELTAS_SOURCE.name
        self.r2_membership = self.root / R2_MEMBERSHIP_SOURCE.name
        self.r5_ar = self.root / R5_AR_SOURCE.name
        self.r5_metadata = self.root / R5_METADATA_SOURCE.name
        self.r5_spop = self.root / R5_SPOP_SOURCE.name
        self.r5_power = self.root / R5_POWER_SOURCE.name
        self.r5_predictions = self.root / R5_PREDICTIONS_SOURCE.name
        self.r3_mapping = self.root / R3_MAPPING_SOURCE.name
        self.r3_concordance = self.root / R3_CONCORDANCE_SOURCE.name
        self.r3_performance = self.root / R3_PERFORMANCE_SOURCE.name
        self.r3_manifest = self.root / R3_MANIFEST_SOURCE.name
        self.r4_summary = self.root / R4_SUMMARY_SOURCE.name
        self.r4_deltas = self.root / R4_DELTAS_SOURCE.name
        self.r4_manifest = self.root / R4_MANIFEST_SOURCE.name
        self.confounder_nested = self.root / CONFOUNDER_NESTED_SOURCE.name
        self.confounder_refit = self.root / CONFOUNDER_REFIT_SOURCE.name
        for source, destination in (
            (R2_CELLS_SOURCE, self.r2_cells),
            (R2_DELTAS_SOURCE, self.r2_deltas),
            (R2_MEMBERSHIP_SOURCE, self.r2_membership),
            (R5_AR_SOURCE, self.r5_ar),
            (R5_METADATA_SOURCE, self.r5_metadata),
            (R5_SPOP_SOURCE, self.r5_spop),
            (R5_POWER_SOURCE, self.r5_power),
            (R5_PREDICTIONS_SOURCE, self.r5_predictions),
            (R3_MAPPING_SOURCE, self.r3_mapping),
            (R3_CONCORDANCE_SOURCE, self.r3_concordance),
            (R3_PERFORMANCE_SOURCE, self.r3_performance),
            (R3_MANIFEST_SOURCE, self.r3_manifest),
            (R4_SUMMARY_SOURCE, self.r4_summary),
            (R4_DELTAS_SOURCE, self.r4_deltas),
            (R4_MANIFEST_SOURCE, self.r4_manifest),
            (CONFOUNDER_NESTED_SOURCE, self.confounder_nested),
            (CONFOUNDER_REFIT_SOURCE, self.confounder_refit),
        ):
            shutil.copyfile(source, destination)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def claim_builder_kwargs(self) -> dict[str, Path]:
        return {
            "output_dir": self.root,
            "stability_summary_csv": self.grid,
            "stability_contrast_csv": self.contrasts,
            "stability_qc_json": self.qc,
            "r2_cells_csv": self.r2_cells,
            "r2_deltas_csv": self.r2_deltas,
            "r2_membership_csv": self.r2_membership,
            "r5_ar_csv": self.r5_ar,
            "r5_metadata_csv": self.r5_metadata,
            "r5_spop_csv": self.r5_spop,
            "r5_power_csv": self.r5_power,
            "r5_predictions_csv": self.r5_predictions,
            "r3_mapping_csv": self.r3_mapping,
            "r3_concordance_csv": self.r3_concordance,
            "r3_performance_csv": self.r3_performance,
            "r3_manifest_csv": self.r3_manifest,
            "r4_summary_csv": self.r4_summary,
            "r4_deltas_csv": self.r4_deltas,
            "r4_manifest_csv": self.r4_manifest,
            "confounder_nested_csv": self.confounder_nested,
            "confounder_refit_csv": self.confounder_refit,
        }

    def test_claim_builder_records_completed_r2_through_r5_with_narrow_r3_r4_interpretation(self):
        frame = p0.build_claim_evidence(**self.claim_builder_kwargs())

        by_id = frame.set_index("claim_id")
        self.assertNotIn("pending", by_id.loc["C02", "status"])
        self.assertNotIn("pending", by_id.loc["C03", "status"])
        self.assertEqual(by_id.loc["C04", "status"], "unsupported_in_frozen_design")
        self.assertEqual(by_id.loc["C05", "status"], "context_sensitive")
        self.assertEqual(by_id.loc["C06", "status"], "context_sensitive")
        self.assertEqual(by_id.loc["C07", "status"], "context_sensitive")
        self.assertEqual(by_id.loc["C04", "completion_status"], "r5_complete_interpretation_unresolved")
        self.assertEqual(by_id.loc["C05", "completion_status"], "r5_complete_transportability_unresolved")
        self.assertEqual(by_id.loc["C06", "completion_status"], "r3_complete_endpoint_conditioned_exploratory")
        self.assertEqual(by_id.loc["C07", "completion_status"], "r4_complete_no_robust_increment")
        for claim_id in ("C04", "C05", "C06"):
            self.assertNotIn("pending_gate_b", by_id.loc[claim_id, "status"])
            self.assertNotIn("Interim pending Gate B", by_id.loc[claim_id, "reliability_tier"])

        c04 = by_id.loc["C04"]
        self.assertIn("unsupported in the frozen primary configuration", c04["claim"])
        self.assertIn("neither a consistently positive effect nor a definitive absence", c04["claim"])
        self.assertNotIn("robust null", c04["claim"].lower())
        self.assertIn("modest effect and tumor dilution remain unresolved", c04["limitation"])
        self.assertIn("fixed-score approximation", c04["effect_summary"])
        self.assertIn("not an effect-exclusion bound", c04["limitation"])
        self.assertIn("EJ 0.613", c04["effect_summary"])
        self.assertIn("G9 0.700", c04["effect_summary"])
        self.assertIn("HC 0.758", c04["effect_summary"])
        self.assertIn("KK 0.573", c04["effect_summary"])
        self.assertIn("YL 0.625", c04["effect_summary"])
        self.assertIn("CH undefined", c04["effect_summary"])
        self.assertIn("undefined bootstrap counts CH/EJ/G9/HC/KK/YL = 2000/0/234/92/2/31", c04["effect_summary"])
        for source in (
            "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv", "resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_predictions.csv",
        ):
            self.assertIn(source, c04["source_csv"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/build_ar_spop_evidence_closure.py", c04["source_script"])

        c05 = by_id.loc["C05"]
        self.assertIn("positive pooled direction is consistent", c05["claim"])
        self.assertIn("neither supported nor refuted", c05["claim"])
        self.assertIn("Grade-independent increment remains unresolved", c05["limitation"])
        self.assertIn("No scanner, stain, or site causality", c05["limitation"])
        self.assertIn("six-site frame 224 slides/209 patients", c05["effect_summary"])
        self.assertIn("six LOO intervals include zero", c05["effect_summary"])
        self.assertIn("ScanScope raw ID 280/300", c05["effect_summary"])
        self.assertIn("explicit stain field 0/300", c05["effect_summary"])
        for source in (
            "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv",
        ):
            self.assertIn(source, c05["source_csv"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/build_ar_spop_evidence_closure.py", c05["source_script"])

        c06 = by_id.loc["C06"]
        self.assertIn("Post-hoc endpoint-specific exploratory signal", c06["claim"])
        self.assertIn("endpoint, encoder, and scale", c06["limitation"])
        self.assertIn("CONCH is higher", c06["effect_summary"])
        self.assertIn("Virchow improves at shared 1.76", c06["effect_summary"])
        self.assertIn("common-498 R2 complete", c06["effect_summary"])
        self.assertIn("498 source patients/85 events", c06["effect_summary"])
        self.assertIn("270 target patients/57 events", c06["effect_summary"])
        self.assertIn("60/60 raw-to-common null relation preserved", c06["effect_summary"])
        self.assertIn("30/30 scale, 20/20 tile, 15/15 encoder directions preserved", c06["effect_summary"])
        self.assertIn("-0.0023 to +0.0229", c06["effect_summary"])
        self.assertIn("official PFI interval includes 0.5", c06["limitation"])
        self.assertIn("official PFI n=270/42 events", c06["effect_summary"])
        self.assertIn("C-index 0.586 [0.482,0.689]", c06["effect_summary"])
        self.assertIn("event agreement 1.000", c06["effect_summary"])
        self.assertNotIn("R2 remains pending", c06["limitation"])
        for source in (
            "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_paired_deltas.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_membership_manifest.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv",
            "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv",
        ):
            self.assertIn(source, c06["source_csv"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/run_marker7_common_source_sensitivity.py", c06["source_script"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/build_tcga_cdr_pfi_evidence.py", c06["source_script"])

        c07 = by_id.loc["C07"]
        self.assertIn("no robust incremental value", c07["claim"])
        self.assertIn("reconstructed grade+image delta C +0.083 [+0.012,+0.157]", c07["effect_summary"])
        self.assertIn("official PFI grade+image delta C +0.032 [-0.040,+0.126]", c07["effect_summary"])
        self.assertIn("all official-PFI paired C-index and IBS intervals include zero", c07["limitation"])
        self.assertIn("153-patient complete-case", c07["limitation"])
        self.assertIn("multiple imputation was not performed", c07["limitation"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv", c07["source_csv"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/build_marker7_survival_paired_analysis.py", c07["source_script"])

        stability = by_id.loc["C08"]
        self.assertIn("correlated sensitivity audit", stability["validation_type"])
        self.assertNotIn("external validation", stability["validation_type"])
        self.assertEqual(stability["source_csv"], "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv")
        self.assertTrue((self.root / "claim_evidence_matrix.csv").is_file())
        self.assertTrue((self.root / "claim_evidence_matrix.md").is_file())

    def test_r2_null_crossing_treats_exact_null_as_a_distinct_relation(self):
        actual = p0.null_relation_crossing(
            pd.Series([0.5, 0.4, 0.5]),
            pd.Series([0.6, 0.5, 0.5]),
            null_value=0.5,
        )
        self.assertEqual(actual.tolist(), [True, True, False])

    def test_claim_numeric_prose_tracks_saved_pten_rows(self):
        nested = pd.read_csv(self.confounder_nested)
        pten = nested["marker"].eq("marker4_pten") & nested["scope"].eq("patient")
        nested.loc[pten, ["delta", "ci_low", "ci_high"]] = [0.123456, -0.222222, 0.333333]
        nested.to_csv(self.confounder_nested, index=False)
        refit = pd.read_csv(self.confounder_refit)
        pten_refit = refit["marker"].eq("marker4_pten") & refit["analysis"].eq("grade_only")
        refit.loc[pten_refit, "observed_delta"] = 0.123456
        refit.loc[pten_refit, "permutation_p_one_sided"] = 0.444444
        refit.to_csv(self.confounder_refit, index=False)

        claims = p0.build_claim_evidence(**self.claim_builder_kwargs()).set_index("claim_id")

        self.assertIn(
            "CONCH delta AUROC +0.123 [-0.222,+0.333], refit p=0.444",
            claims.loc["C03", "effect_summary"],
        )

    def test_endpoint_numeric_prose_tracks_saved_event_rows(self):
        benchmark = self.root / BENCHMARK_SOURCE.name
        recurrence = self.root / RECURRENCE_ONLY_SOURCE.name
        performance = self.root / R3_PERFORMANCE_SOURCE.name
        shutil.copyfile(BENCHMARK_SOURCE, benchmark)
        shutil.copyfile(RECURRENCE_ONLY_SOURCE, recurrence)
        shutil.copyfile(R3_PERFORMANCE_SOURCE, performance)
        benchmark_frame = pd.read_csv(benchmark)
        benchmark_frame.loc[benchmark_frame["check"].eq("zeroshot_DFS"), "n_events"] = 13
        benchmark_frame.loc[
            benchmark_frame["check"].eq("zeroshot_recurrence_only"), "n_events"
        ] = 9
        benchmark_frame.to_csv(benchmark, index=False)
        performance_frame = pd.read_csv(performance)
        performance_frame.loc[
            performance_frame["endpoint_id"].eq("official_tcga_cdr_pfi"), "n_events"
        ] = 44
        performance_frame.to_csv(performance, index=False)

        endpoints = p0.build_endpoint_hierarchy(
            output_dir=self.root,
            benchmark_csv=benchmark,
            recurrence_only_csv=recurrence,
            r3_performance_csv=performance,
        ).set_index("endpoint_id")

        self.assertIn("9 events", endpoints.loc["E05", "limitation"])
        self.assertIn("13 events", endpoints.loc["E07", "limitation"])
        self.assertIn("44 events", endpoints.loc["E08_official_pfi", "limitation"])

    def test_claim_builder_finalizes_c07_narrowly_and_uses_unsupported_semantics(self):
        frame = p0.build_claim_evidence(**self.claim_builder_kwargs()).set_index("claim_id")

        c01 = frame.loc["C01"]
        self.assertIn("unsupported signals", c01["claim"])
        self.assertNotIn("null signals", c01["claim"])
        self.assertIn("historical protocol label", c01["limitation"])
        self.assertIn("not proof of a biological null", c01["limitation"])

        c07 = frame.loc["C07"]
        self.assertEqual(c07["status"], "context_sensitive")
        self.assertEqual(c07["completion_status"], "r4_complete_no_robust_increment")
        self.assertIn("no robust incremental value", c07["claim"])
        self.assertIn("Exploratory; endpoint-conditioned", c07["reliability_tier"])
        self.assertIn("same-patient/same-draw", c07["validation_type"])
        self.assertIn("ΔC and ΔIBS", c07["validation_type"])
        self.assertIn("full+image delta C -0.001 [-0.020,+0.019]", c07["effect_summary"])
        self.assertIn("M5-M4 delta C -0.006 [-0.021,+0.006]", c07["effect_summary"])

    def test_stability_table_builder_derives_six_marker_rows(self):
        output = self.root / "stability_grid_marker_summary.tex"
        frame = p0.build_stability_grid_marker_summary(self.grid, self.contrasts, output)

        self.assertEqual(set(frame["marker"]), {"gleason", "phenotype", "pten", "spop", "ar", "marker7"})
        self.assertEqual(len(frame), 6)
        by_marker = frame.set_index("marker")
        expected_counts = {
            "gleason": (0, 0, 0, 0),
            "phenotype": (0, 0, 0, 0),
            "pten": (0, 0, 0, 0),
            "spop": (25, 8, 19, 4),
            "ar": (0, 0, 0, 0),
            "marker7": (1, 1, 1, 0),
        }
        for marker, counts in expected_counts.items():
            row = by_marker.loc[marker]
            self.assertEqual(
                tuple(int(row[column]) for column in (
                    "chance_or_worse_cells", "seed_null_straddles",
                    "native_scale_null_crossings", "shared_scale_encoder_null_crossings",
                )),
                counts,
            )
            self.assertEqual(
                tuple(int(row[column]) for column in (
                    "chance_or_worse_denominator", "seed_null_straddle_denominator",
                    "native_scale_denominator", "shared_scale_encoder_denominator",
                )),
                (60, 12, 30, 15),
            )
        self.assertAlmostEqual(by_marker.loc["spop", "observed_cell_min"], 0.347654041831543)
        self.assertAlmostEqual(by_marker.loc["spop", "observed_cell_max"], 0.679338609383833)
        self.assertAlmostEqual(by_marker.loc["ar", "observed_cell_min"], 0.136426368970623)
        self.assertAlmostEqual(by_marker.loc["ar", "observed_cell_max"], 0.296879165419096)
        self.assertTrue(output.is_file())
        rendered = output.read_text(encoding="utf-8")
        self.assertIn("25/60", rendered)
        self.assertIn("Shared-scale encoder crossing", rendered)
        self.assertIn("Frozen Gate A stability-grid summary derived from the saved", rendered)
        self.assertIn(r"\resizebox{\textwidth}{!}{%", rendered)
        self.assertIn("\\end{tabular}%\n}", rendered)
        self.assertIn("19/30", rendered)
        self.assertIn("4/15", rendered)

    def test_p0_builders_reject_replaced_keys_and_malformed_boolean_types(self):
        mutations = (
            ("replaced summary key", "grid", 0, "target_mpp", 9.99),
            ("fractional summary count", "grid", 0, "n_chance_or_worse", 1.5),
            ("malformed summary boolean", "grid", 0, "seed_null_straddle", "sometimes"),
            ("replaced contrast key", "contrasts", 0, "tiles_per_slide_a", 128),
            ("shifted contrast seed", "contrasts", 0, "sampling_seed", 0.5),
            ("malformed contrast boolean", "contrasts", 0, "null_crossing", "sometimes"),
        )
        for label, source, row, column, value in mutations:
            with self.subTest(label=label):
                shutil.copyfile(GRID_SOURCE, self.grid)
                shutil.copyfile(CONTRAST_SOURCE, self.contrasts)
                path = self.grid if source == "grid" else self.contrasts
                frame = pd.read_csv(path)
                frame[column] = frame[column].astype(object)
                frame.loc[row, column] = value
                frame.to_csv(path, index=False)

                with self.assertRaises(ValueError):
                    p0.build_stability_grid_marker_summary(
                        self.grid, self.contrasts, self.root / "invalid.tex"
                    )

    def test_claim_builder_fails_closed_on_incomplete_or_semantically_changed_r2_sources(self):
        def shift_first_common_pair(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[0, "common498_metric_a"] += 0.01
            changed.loc[0, "common498_metric_b"] += 0.01
            return changed

        def replace_first_pair_id(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[0, "pair_id"] = "unexpected-pair"
            return changed

        def make_two_membership_events_fractional(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed["event"] = changed["event"].astype(float)
            common = changed.loc[changed["common_source_member"]]
            negative_id = common.loc[common["event"].eq(0), "source_case_id"].iloc[0]
            positive_id = common.loc[common["event"].eq(1), "source_case_id"].iloc[0]
            changed.loc[changed["source_case_id"].isin([negative_id, positive_id]), "event"] = 0.5
            return changed

        def corrupt_membership_status(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[0, "outcome_consistency_status"] = "inconsistent"
            return changed

        def corrupt_cell_axis_link(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[0, "encoder"] = "FAKE"
            changed.loc[0, "source_configuration_id"] = "fake__s9__mpp9.99"
            return changed

        def replace_membership_configuration(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            original = "conch__s0__mpp0.88"
            rows = changed["source_configuration_id"].eq(original)
            changed.loc[rows, "source_configuration_id"] = "fake__s9__mpp9.99"
            changed.loc[rows, "encoder"] = "FAKE"
            changed.loc[rows, "sampling_seed"] = 9
            changed.loc[rows, "target_mpp"] = 9.99
            return changed

        def replace_common_case_identity(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            case_id = changed.loc[changed["common_source_member"], "source_case_id"].iloc[0]
            changed.loc[changed["source_case_id"].eq(case_id), "source_case_id"] = "FAKE_CASE"
            return changed

        mutations = (
            (self.r2_cells, lambda frame: frame.iloc[:-1].copy()),
            (self.r2_cells, lambda frame: frame.assign(
                common_minus_saved_raw=frame["common_minus_saved_raw"] + 0.1
            )),
            (self.r2_deltas, lambda frame: frame.assign(direction_status="reversed")),
            (self.r2_deltas, lambda frame: frame.assign(
                common498_delta_b_minus_a=frame["common498_delta_b_minus_a"] + 0.1
            )),
            (self.r2_deltas, shift_first_common_pair),
            (self.r2_deltas, replace_first_pair_id),
            (self.r2_membership, lambda frame: frame.iloc[:-1].copy()),
            (self.r2_membership, make_two_membership_events_fractional),
            (self.r2_membership, corrupt_membership_status),
            (self.r2_cells, corrupt_cell_axis_link),
            (self.r2_cells, lambda frame: frame.assign(
                marker=frame["marker"].mask(frame.index == 0, "other_marker")
            )),
            (self.r2_cells, lambda frame: frame.assign(canonical_cohort="WRONG-COHORT")),
            (self.r2_cells, lambda frame: frame.assign(outcome_type="classification")),
            (self.r2_cells, lambda frame: frame.assign(primary_metric="auroc")),
            (self.r2_cells, lambda frame: frame.assign(raw_reproduction_error_vs_saved=999.0)),
            (self.r2_membership, replace_membership_configuration),
            (self.r2_membership, replace_common_case_identity),
            (self.r2_membership, lambda frame: frame.assign(
                follow_up_years=frame["follow_up_years"].mask(frame.index == 0, -1.0)
            )),
            (self.r2_membership, lambda frame: frame.assign(
                source_row_index=frame["source_row_index"].mask(frame.index == 0, 999)
            )),
        )
        originals = {path: path.read_bytes() for path, _ in mutations}
        for path, mutate in mutations:
            with self.subTest(path=path.name):
                for restore_path, payload in originals.items():
                    restore_path.write_bytes(payload)
                frame = pd.read_csv(path)
                mutate(frame).to_csv(path, index=False)
                with self.assertRaises(ValueError):
                    p0.build_claim_evidence(**self.claim_builder_kwargs())

    def test_claim_builder_fails_closed_on_incomplete_or_overstated_r5_sources(self):
        def out_of_range_first_prediction(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[0, "predicted_probability"] = 2.0
            return changed

        def make_ch_ci_look_defined(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            ch = changed["site"].eq("CH")
            changed.loc[ch, ["patient_ci_low", "patient_ci_high"]] = [0.4, 0.6]
            changed.loc[ch, "status_reason"] = "complete"
            return changed

        def remove_small_class_warning(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[changed["site"].eq("G9"), "small_class_warning"] = "none"
            return changed

        def corrupt_prediction_reconstruction_status(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[0, "reconstruction_status"] = "unknown"
            return changed

        def replace_nonlarge_site(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            changed.loc[changed["site"].eq("2A"), "site"] = "ZZ"
            return changed

        def corrupt_prediction_file_link(frame: pd.DataFrame) -> pd.DataFrame:
            changed = frame.copy()
            slide_row = changed["record_level"].eq("slide").idxmax()
            changed.loc[slide_row, "file_name"] = "foreign-slide.svs"
            return changed

        mutations = (
            (self.r5_ar, lambda frame: frame.iloc[:-1].copy()),
            (self.r5_metadata, lambda frame: frame.iloc[:-1].copy()),
            (self.r5_spop, lambda frame: frame.iloc[:-1].copy()),
            (self.r5_spop, lambda frame: frame.assign(bootstrap_undefined_fraction=0.0)),
            (self.r5_spop, make_ch_ci_look_defined),
            (self.r5_spop, remove_small_class_warning),
            (self.r5_power, lambda frame: frame.assign(limitation="effect excluded")),
            (self.r5_predictions, lambda frame: frame.iloc[:-1].copy()),
            (self.r5_predictions, out_of_range_first_prediction),
            (self.r5_predictions, lambda frame: frame.assign(
                predicted_probability=1.0 - frame["predicted_probability"]
            )),
            (self.r5_predictions, corrupt_prediction_reconstruction_status),
            (self.r5_ar, replace_nonlarge_site),
            (self.r5_spop, replace_nonlarge_site),
            (self.r5_metadata, lambda frame: frame.assign(
                site=frame["site"].mask(frame.index == 0, "ZZ")
            )),
            (self.r5_power, lambda frame: frame.assign(analysis_unit="slide")),
            (self.r5_power, lambda frame: frame.assign(null_auroc=0.4)),
            (self.r5_predictions, corrupt_prediction_file_link),
            (self.r5_ar, lambda frame: frame.assign(
                loo_rho=frame["loo_rho"].mask(frame["site"].eq("EJ"), 99.0)
            )),
            (self.r5_ar, lambda frame: frame.assign(
                n_bootstrap_requested=0,
                n_bootstrap_valid=0,
                n_bootstrap_undefined=999,
                bootstrap_undefined_fraction=999.0,
            )),
            (self.r5_spop, lambda frame: frame.assign(
                patient_ci_low=frame["patient_ci_low"].mask(frame["site"].eq("EJ"), 0.0),
                patient_ci_high=frame["patient_ci_high"].mask(frame["site"].eq("EJ"), 1.0),
            )),
            (self.r5_power, lambda frame: frame.assign(cohort="OTHER")),
            (self.r5_metadata, lambda frame: frame.assign(canonical_header_sha256="NOT_A_SHA256")),
        )
        originals = {path: path.read_bytes() for path, _ in mutations}
        for path, mutate in mutations:
            with self.subTest(path=path.name):
                for restore_path, payload in originals.items():
                    restore_path.write_bytes(payload)
                frame = pd.read_csv(path)
                mutate(frame).to_csv(path, index=False)
                with self.assertRaises(ValueError):
                    p0.build_claim_evidence(**self.claim_builder_kwargs())

    def test_protocol_change_log_preserves_gate_b_and_adds_r2_through_r5_closure(self):
        output = self.root / "protocol_change_log.csv"

        frame = p0.build_protocol_change_log(output)

        gate_b = frame[frame["change"].str.contains("Gate B", regex=False)]
        self.assertEqual(len(gate_b), 1)
        self.assertIn("did not overturn", gate_b.iloc[0]["interpretation"])
        closure = frame[frame["change"].str.contains("R2/R5", regex=False)]
        self.assertEqual(len(closure), 1)
        self.assertIn("R2 common-498 complete", closure.iloc[0]["interpretation"])
        self.assertIn("R5 evidence closure complete", closure.iloc[0]["interpretation"])
        self.assertIn("R3", closure.iloc[0]["interpretation"])
        self.assertIn("R4", closure.iloc[0]["interpretation"])
        self.assertNotIn("R5 pending", closure.iloc[0]["interpretation"])
        final = frame[frame["change"].str.contains("R3/R4", regex=False)]
        self.assertEqual(len(final), 1)
        self.assertIn("official PFI complete", final.iloc[0]["interpretation"])
        self.assertIn("no robust independent or incremental prognostic value", final.iloc[0]["interpretation"])
        fig3 = frame[frame["change"].str.contains("Figure 3", regex=False)]
        self.assertEqual(len(fig3), 1)
        self.assertIn("0.585", fig3.iloc[0]["interpretation"])
        self.assertIn("0.524416", fig3.iloc[0]["interpretation"])
        self.assertIn("patient/slide analysis units", fig3.iloc[0]["interpretation"])
        self.assertTrue(output.is_file())

    def test_protocol_provenance_includes_r2_through_r5_entrypoints_tests_and_outputs(self):
        output = self.root / "protocol_provenance.json"
        change_log = self.root / "protocol_change_log.csv"

        p0.build_protocol_provenance(output_json=output, change_log_csv=change_log)

        payload = json.loads(output.read_text(encoding="utf-8"))
        paths = {record["path"] for record in payload["files"]}
        expected = {
            *p0.R2_R5_PROVENANCE_RELATIVE_PATHS,
            *p0.R3_R4_PROVENANCE_RELATIVE_PATHS,
            "projects/prostate_biomarker_validation/paper/figure_data/fig3_primary_snapshot.csv",
            "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.py",
            "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.pdf",
            "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.png",
        }
        self.assertEqual(expected - paths, set())
        self.assertNotIn(
            str(output.resolve()), {record["resolved_path"] for record in payload["files"]}
        )
        by_path = {record["path"]: record for record in payload["files"]}
        for path in expected:
            self.assertRegex(by_path[path]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(by_path[path]["sha256"], file_sha256(ROOT / path))
        self.assertTrue(change_log.is_file())

    def test_protocol_provenance_rejects_a_missing_required_r2_r5_path(self):
        with self.assertRaisesRegex(ValueError, "required provenance"):
            p0.validate_required_provenance_paths([self.root / "missing-r2-output.csv"])

    def test_endpoint_hierarchy_records_official_pfi_as_complete_but_uncertain(self):
        frame = p0.build_endpoint_hierarchy(output_dir=self.root).set_index("endpoint_id")

        e08 = frame.loc["E08_official_pfi"]
        self.assertEqual(e08["endpoint"], "official TCGA-CDR PFI")
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv", e08["source"])
        self.assertIn("resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv", e08["source"])
        self.assertEqual(e08["status"], "complete_but_uncertain")
        self.assertIn("42 events", e08["limitation"])
        self.assertIn("C-index interval includes 0.5", e08["limitation"])
        self.assertTrue((self.root / "endpoint_hierarchy.csv").is_file())
        self.assertTrue((self.root / "endpoint_hierarchy.md").is_file())


if __name__ == "__main__":
    unittest.main()
