"""Contracts for Scientific Reports final-size vector figure rendering."""
from __future__ import annotations

import atexit
import hashlib
import importlib
import os
import re
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

# Matplotlib must see a writable configuration directory before it is imported.
_MPLCONFIGDIR = tempfile.TemporaryDirectory(prefix="scientific-reports-mpl-")
os.environ["MPLCONFIGDIR"] = _MPLCONFIGDIR.name
atexit.register(_MPLCONFIGDIR.cleanup)

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

from paper.figures.style import (
    AXIS_FONT_PT,
    DOUBLE_COLUMN_MM,
    MIN_FONT_PT,
    MIN_LINE_PT,
    PANEL_FONT_PT,
    SINGLE_COLUMN_MM,
    apply_journal_style,
    figure_size,
    save_vector_figure,
)


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DATA = ROOT / "paper" / "figure_data"

RENDERER_CONTRACTS = (
    (
        "paper.figures.fig1_qualification_map",
        (FIGURE_DATA / "fig1_qualification_map.csv",),
        (0, "evidence_state"),
        (0, ("semantic_key",)),
        (0, "evidence_state", "transportable"),
    ),
    (
        "paper.figures.fig2_transportable_signals",
        (FIGURE_DATA / "fig2_transportable_signals.csv",),
        (0, "n"),
        (0, ("semantic_key",)),
        (0, "cohort", "PRECISE"),
    ),
    (
        "paper.figures.fig3_molecular_qualification",
        (FIGURE_DATA / "fig3_molecular_qualification.csv",),
        (0, "interval_type"),
        (0, ("semantic_key",)),
        (0, "target", "AR"),
    ),
    (
        "paper.figures.fig4_confounder_site_audit",
        (FIGURE_DATA / "fig4_confounder_site_audit.csv",),
        (0, "cluster_unit"),
        (0, ("semantic_key",)),
        (0, "audit_type", "ar_site_transport"),
    ),
    (
        "paper.figures.fig5_marker7_transfer",
        (FIGURE_DATA / "fig5_marker7_transfer.csv",),
        (0, "n_events"),
        (0, ("semantic_key",)),
        (0, "endpoint_id", "E08_official_pfi"),
    ),
    (
        "paper.figures.fig6_stability_overview",
        (FIGURE_DATA / "fig6_stability_overview.csv",),
        (0, "n_null_crossings"),
        (0, ("semantic_key",)),
        (0, "marker", "spop"),
    ),
    (
        "paper.figures.sfig1_detailed_roc",
        (FIGURE_DATA / "fig2_transportable_signals.csv",),
        (0, "ci_low"),
        (0, ("semantic_key",)),
        (0, "signal", "Phenotype"),
    ),
    (
        "paper.figures.sfig2_marker7_survival",
        (
            ROOT / "models" / "marker7_td_auc_curve.csv",
            ROOT / "models" / "marker7_calibration_3y_5y.csv",
            FIGURE_DATA / "fig5_marker7_transfer.csv",
        ),
        (0, "td_auc"),
        (0, ("time_years",)),
        (1, "horizon_years", 5.0),
    ),
    (
        "paper.figures.sfig3_stability_heatmaps",
        (
            FIGURE_DATA / "fig9_stability_grid.csv",
            FIGURE_DATA / "fig9_stability_contrasts.csv",
        ),
        (0, "null_value"),
        (0, ("marker", "encoder", "tiles_per_slide", "target_mpp")),
        (0, "marker", "spop"),
    ),
)

FINITE_MUTATIONS = {
    "paper.figures.fig1_qualification_map": (0, "primary_estimate"),
    "paper.figures.fig2_transportable_signals": (0, "primary_estimate"),
    "paper.figures.fig3_molecular_qualification": (0, "primary_estimate"),
    "paper.figures.fig4_confounder_site_audit": (0, "primary_estimate"),
    "paper.figures.fig5_marker7_transfer": (0, "primary_estimate"),
    "paper.figures.fig6_stability_overview": (0, "primary_estimate"),
    "paper.figures.sfig1_detailed_roc": (0, "primary_estimate"),
    "paper.figures.sfig2_marker7_survival": (0, "td_auc"),
    "paper.figures.sfig3_stability_heatmaps": (0, "mean"),
}

EXPLICIT_MISSINGNESS_RENDERERS = {
    "paper.figures.fig1_qualification_map",
    "paper.figures.fig2_transportable_signals",
    "paper.figures.fig3_molecular_qualification",
    "paper.figures.fig4_confounder_site_audit",
    "paper.figures.fig5_marker7_transfer",
    "paper.figures.fig6_stability_overview",
    "paper.figures.sfig1_detailed_roc",
}


class FigureStyleTests(unittest.TestCase):
    def test_final_size_style_minima(self):
        apply_journal_style()
        self.assertGreaterEqual(mpl.rcParams["font.size"], MIN_FONT_PT)
        self.assertGreaterEqual(mpl.rcParams["axes.labelsize"], AXIS_FONT_PT)
        self.assertGreaterEqual(mpl.rcParams["xtick.labelsize"], AXIS_FONT_PT)
        self.assertGreaterEqual(mpl.rcParams["axes.titlesize"], PANEL_FONT_PT)
        self.assertGreaterEqual(mpl.rcParams["axes.linewidth"], MIN_LINE_PT)
        self.assertGreaterEqual(mpl.rcParams["lines.linewidth"], MIN_LINE_PT)
        self.assertGreaterEqual(mpl.rcParams["xtick.major.width"], MIN_LINE_PT)
        self.assertGreaterEqual(mpl.rcParams["xtick.minor.width"], MIN_LINE_PT)
        self.assertGreaterEqual(mpl.rcParams["ytick.major.width"], MIN_LINE_PT)
        self.assertGreaterEqual(mpl.rcParams["ytick.minor.width"], MIN_LINE_PT)

    def test_journal_style_uses_white_background_and_fixed_safe_palette(self):
        apply_journal_style()
        self.assertEqual(mpl.rcParams["font.family"], ["DejaVu Sans"])
        self.assertEqual(mpl.rcParams["figure.facecolor"], "white")
        self.assertEqual(mpl.rcParams["axes.facecolor"], "white")
        self.assertEqual(mpl.rcParams["savefig.facecolor"], "white")
        self.assertEqual(
            list(mpl.rcParams["axes.prop_cycle"].by_key()["color"]),
            ["#0072B2", "#D55E00", "#009E73", "#6B7280"],
        )

    def test_single_and_double_column_geometry(self):
        single_width, single_height = figure_size(SINGLE_COLUMN_MM, 0.62)
        double_width, double_height = figure_size(DOUBLE_COLUMN_MM, 0.62)
        self.assertAlmostEqual(single_width, 89 / 25.4)
        self.assertAlmostEqual(double_width, 180 / 25.4)
        self.assertAlmostEqual(single_height, single_width * 0.62)
        self.assertAlmostEqual(double_height, double_width * 0.62)

    def test_double_column_width_is_180_mm(self):
        width, _ = figure_size(180, 0.62)
        self.assertLess(abs(width - 180 / 25.4), 1e-9)

    @staticmethod
    def _fixture_figure():
        apply_journal_style()
        figure, axis = plt.subplots(figsize=figure_size(DOUBLE_COLUMN_MM, 0.4))
        axis.plot([0, 1], [0, 1], label="fixture")
        axis.set_xlabel("x")
        axis.set_ylabel("y")
        axis.legend()
        return figure

    def test_vector_save_is_deterministic_and_closes_figure(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "nested" / "output"
            first = output_root / "first.pdf"
            second = output_root / "second.pdf"

            first_figure = self._fixture_figure()
            first_number = first_figure.number
            save_vector_figure(first_figure, first)
            second_figure = self._fixture_figure()
            save_vector_figure(second_figure, second)

            self.assertTrue(first.exists())
            self.assertFalse(plt.fignum_exists(first_number))
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            )

    def test_vector_save_closes_figure_when_parent_creation_fails(self):
        figure = self._fixture_figure()
        figure_number = figure.number
        with patch.object(Path, "mkdir", side_effect=OSError("mkdir failure")):
            with self.assertRaisesRegex(OSError, "mkdir failure"):
                save_vector_figure(figure, Path("unwritable") / "figure.pdf")
        self.assertFalse(plt.fignum_exists(figure_number))

    def test_vector_save_closes_figure_when_pdf_write_fails(self):
        figure = self._fixture_figure()
        figure_number = figure.number
        with patch.object(figure, "savefig", side_effect=OSError("savefig failure")):
            with self.assertRaisesRegex(OSError, "savefig failure"):
                save_vector_figure(figure, Path("render-failure.pdf"))
        self.assertFalse(plt.fignum_exists(figure_number))


class SubmissionRendererTests(unittest.TestCase):
    @staticmethod
    def _temporary_sources(tmp: str, sources: tuple[Path, ...]) -> list[Path]:
        copied = []
        for index, source in enumerate(sources):
            target = Path(tmp) / f"source-{index}.csv"
            shutil.copyfile(source, target)
            copied.append(target)
        return copied

    @staticmethod
    def _media_box_widths_mm(pdf: Path) -> list[float]:
        boxes = re.findall(
            rb"/MediaBox\s*\[\s*([\d.+-]+)\s+([\d.+-]+)\s+"
            rb"([\d.+-]+)\s+([\d.+-]+)\s*\]",
            pdf.read_bytes(),
        )
        if not boxes:
            raise AssertionError(f"No MediaBox found in {pdf}")
        return [(float(x2) - float(x1)) * 25.4 / 72.0 for x1, _y1, x2, _y2 in boxes]

    def test_each_renderer_rejects_a_missing_required_column(self):
        for module_name, sources, required, _duplicate, _group in RENDERER_CONTRACTS:
            with self.subTest(renderer=module_name), tempfile.TemporaryDirectory() as tmp:
                module = importlib.import_module(module_name)
                paths = self._temporary_sources(tmp, sources)
                source_index, column = required
                frame = pd.read_csv(paths[source_index]).drop(columns=[column])
                frame.to_csv(paths[source_index], index=False)
                with self.assertRaises(ValueError):
                    module.load_sources(paths)

    def test_each_renderer_rejects_a_duplicate_semantic_key(self):
        for module_name, sources, _required, duplicate, _group in RENDERER_CONTRACTS:
            with self.subTest(renderer=module_name), tempfile.TemporaryDirectory() as tmp:
                module = importlib.import_module(module_name)
                paths = self._temporary_sources(tmp, sources)
                source_index, key_columns = duplicate
                frame = pd.read_csv(paths[source_index])
                if "semantic_key" in key_columns:
                    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
                else:
                    frame.iloc[-1] = frame.iloc[0]
                self.assertTrue(frame.duplicated(list(key_columns)).any())
                frame.to_csv(paths[source_index], index=False)
                with self.assertRaises(ValueError):
                    module.load_sources(paths)

    def test_each_renderer_rejects_a_missing_expected_group(self):
        for module_name, sources, _required, _duplicate, group in RENDERER_CONTRACTS:
            with self.subTest(renderer=module_name), tempfile.TemporaryDirectory() as tmp:
                module = importlib.import_module(module_name)
                paths = self._temporary_sources(tmp, sources)
                source_index, column, value = group
                frame = pd.read_csv(paths[source_index])
                frame = frame.loc[frame[column].ne(value)]
                frame.to_csv(paths[source_index], index=False)
                with self.assertRaises(ValueError):
                    module.load_sources(paths)

    def test_each_renderer_rejects_a_nonfinite_primary_value(self):
        for module_name, sources, _required, _duplicate, _group in RENDERER_CONTRACTS:
            with self.subTest(renderer=module_name), tempfile.TemporaryDirectory() as tmp:
                module = importlib.import_module(module_name)
                paths = self._temporary_sources(tmp, sources)
                source_index, column = FINITE_MUTATIONS[module_name]
                frame = pd.read_csv(paths[source_index])
                frame.loc[frame.index[0], column] = float("nan")
                frame.to_csv(paths[source_index], index=False)
                with self.assertRaises(ValueError):
                    module.load_sources(paths)

    def test_sfig2_fails_closed_on_endpoint_or_frame_metadata_mismatch(self):
        module = importlib.import_module("paper.figures.sfig2_marker7_survival")
        sources = RENDERER_CONTRACTS[7][1]
        mutations = (
            ("endpoint_id", "E08_official_pfi"),
            ("n", 269),
            ("n_events", 56),
        )
        for column, value in mutations:
            with self.subTest(column=column), tempfile.TemporaryDirectory() as tmp:
                paths = self._temporary_sources(tmp, sources)
                frame = pd.read_csv(paths[2])
                row = frame["semantic_key"].eq(
                    "E04_reconstructed_with_tumor:frozen_risk:c_index"
                )
                self.assertEqual(int(row.sum()), 1)
                frame.loc[row, column] = value
                frame.to_csv(paths[2], index=False)
                with self.assertRaises(ValueError):
                    module.load_sources(paths)

    def test_sfig2_fails_closed_when_calibration_totals_disagree_by_horizon(self):
        module = importlib.import_module("paper.figures.sfig2_marker7_survival")
        sources = RENDERER_CONTRACTS[7][1]
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._temporary_sources(tmp, sources)
            frame = pd.read_csv(paths[1])
            frame.loc[(frame["horizon_years"] == 5) & (frame["risk_group"] == 0), "events"] = 10
            frame.to_csv(paths[1], index=False)
            with self.assertRaises(ValueError):
                module.load_sources(paths)

    def test_renderers_with_missingness_columns_reject_blank_status(self):
        for module_name, sources, _required, _duplicate, _group in RENDERER_CONTRACTS:
            if module_name not in EXPLICIT_MISSINGNESS_RENDERERS:
                continue
            with self.subTest(renderer=module_name), tempfile.TemporaryDirectory() as tmp:
                module = importlib.import_module(module_name)
                paths = self._temporary_sources(tmp, sources)
                frame = pd.read_csv(paths[0])
                frame.loc[frame.index[0], "missingness_status"] = ""
                frame.to_csv(paths[0], index=False)
                with self.assertRaises(ValueError):
                    module.load_sources(paths)

    def test_each_renderer_is_double_column_and_byte_deterministic(self):
        for module_name, sources, _required, _duplicate, _group in RENDERER_CONTRACTS:
            with self.subTest(renderer=module_name), tempfile.TemporaryDirectory() as tmp:
                module = importlib.import_module(module_name)
                self.assertGreaterEqual(module.FIGURE_WIDTH_MM, DOUBLE_COLUMN_MM)
                first = Path(tmp) / "first.pdf"
                second = Path(tmp) / "second.pdf"
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    module.render(sources, first)
                    module.render(sources, second)
                self.assertEqual([str(item.message) for item in caught], [])
                self.assertGreater(first.stat().st_size, 1_000)
                self.assertTrue(first.read_bytes().startswith(b"%PDF"))
                widths_mm = self._media_box_widths_mm(first)
                for page, width_mm in enumerate(widths_mm, start=1):
                    placement_scale = DOUBLE_COLUMN_MM / width_mm
                    effective_font_pt = MIN_FONT_PT * placement_scale
                    effective_line_pt = MIN_LINE_PT * placement_scale
                    self.assertLessEqual(
                        width_mm, DOUBLE_COLUMN_MM + 1e-6,
                        msg=f"{module_name} page {page}: MediaBox={width_mm:.6f} mm",
                    )
                    self.assertGreaterEqual(
                        effective_font_pt, MIN_FONT_PT,
                        msg=(f"{module_name} page {page}: effective font "
                             f"{effective_font_pt:.6f} pt at 180 mm placement"),
                    )
                    self.assertGreaterEqual(
                        effective_line_pt, MIN_LINE_PT,
                        msg=(f"{module_name} page {page}: effective line "
                             f"{effective_line_pt:.6f} pt at 180 mm placement"),
                    )
                self.assertEqual(
                    hashlib.sha256(first.read_bytes()).hexdigest(),
                    hashlib.sha256(second.read_bytes()).hexdigest(),
                )

    def test_fig6_configuration_straddle_percentages_use_twelve_configurations(self):
        module = importlib.import_module("paper.figures.fig6_stability_overview")
        (frame,) = module.load_sources((FIGURE_DATA / "fig6_stability_overview.csv",))
        percentages = module.configuration_straddle_percentages(frame)
        self.assertAlmostEqual(percentages["spop"], 100 * 8 / 12)
        self.assertAlmostEqual(percentages["marker7"], 100 * 1 / 12)

    def test_fig3_requires_global_correlated_seed_cell_range_token(self):
        module = importlib.import_module("paper.figures.fig3_molecular_qualification")
        source = FIGURE_DATA / "fig3_molecular_qualification.csv"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / source.name
            shutil.copyfile(source, path)
            frame = pd.read_csv(path)
            configuration = frame["component"].eq("configuration_summary")
            frame.loc[configuration, "interval_type"] = (
                "correlated_configuration_range"
            )
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "seed-cell range type"):
                module.load_sources((path,))

    def test_fig3_visible_text_names_global_seed_cell_range(self):
        module = importlib.import_module("paper.figures.fig3_molecular_qualification")
        captured = []
        with patch.object(
            module, "save_vector_figure", side_effect=lambda fig, _out: captured.append(fig)
        ):
            module.render(
                (FIGURE_DATA / "fig3_molecular_qualification.csv",), Path("unused.pdf")
            )
        self.assertEqual(len(captured), 1)
        figure = captured[0]
        try:
            visible = " ".join(text.get_text() for text in figure.findobj(mpl.text.Text))
            self.assertIn("Global correlated seed-cell range", visible)
            self.assertIn("Seed-cell range", visible)
            self.assertNotIn("Configuration range", visible)
        finally:
            plt.close(figure)

    def test_fig5_visible_text_uses_scientific_comparisons_and_metric_specific_signs(self):
        module = importlib.import_module("paper.figures.fig5_marker7_transfer")
        captured = []
        with patch.object(module, "save_vector_figure", side_effect=lambda fig, _out: captured.append(fig)):
            module.render((FIGURE_DATA / "fig5_marker7_transfer.csv",), Path("unused.pdf"))
        self.assertEqual(len(captured), 1)
        figure = captured[0]
        try:
            visible = " ".join(text.get_text() for text in figure.findobj(mpl.text.Text))
            self.assertIn("Add image to grade", visible)
            self.assertIn(
                "Full clinical + site + image vs full clinical + site", visible.replace("\n", " ")
            )
            self.assertIn("C-index change (comparison − reference)", visible)
            self.assertIn("IBS reduction (reference − comparison)", visible)
            self.assertNotRegex(visible, r"\b(?:M[0-9]+|H_M[0-9]+|N_[A-Z_]+)\b")
        finally:
            plt.close(figure)

    def test_fig4_ar_increment_uses_three_readable_ticks(self):
        module = importlib.import_module("paper.figures.fig4_confounder_site_audit")
        captured = []
        with patch.object(
            module, "save_vector_figure", side_effect=lambda fig, _out: captured.append(fig)
        ):
            module.render(
                (FIGURE_DATA / "fig4_confounder_site_audit.csv",), Path("unused.pdf")
            )
        self.assertEqual(len(captured), 1)
        figure = captured[0]
        try:
            ar_increment_axis = figure.axes[1]
            self.assertEqual(
                ar_increment_axis.get_xticks().tolist(), [-0.05, 0.0, 0.05]
            )
        finally:
            plt.close(figure)

    def test_sfig1_phenotype_rank_annotation_is_offset_above_ci(self):
        module = importlib.import_module("paper.figures.sfig1_detailed_roc")
        captured = []
        with patch.object(
            module, "save_vector_figure", side_effect=lambda fig, _out: captured.append(fig)
        ):
            module.render(
                (FIGURE_DATA / "fig2_transportable_signals.csv",), Path("unused.pdf")
            )
        self.assertEqual(len(captured), 1)
        figure = captured[0]
        try:
            phenotype_rank_axis = figure.axes[1]
            annotation = next(
                text for text in phenotype_rank_axis.texts if text.get_text() == "0.800"
            )
            self.assertEqual(annotation.get_position()[0], 0)
            self.assertGreaterEqual(annotation.get_position()[1], 7)
            self.assertEqual(annotation.get_horizontalalignment(), "center")
        finally:
            plt.close(figure)

    def test_reviewer_round2_validator_bypass_mutations_fail_closed(self):
        cases = []

        def swapped_claim_hierarchies(frame):
            c05 = frame.index[frame["semantic_key"].eq("C05")][0]
            c06 = frame.index[frame["semantic_key"].eq("C06")][0]
            frame.loc[[c05, c06], "hierarchy"] = frame.loc[
                [c06, c05], "hierarchy"
            ].to_numpy()

        cases.append(
            (
                "paper.figures.fig1_qualification_map",
                "fig1_qualification_map.csv",
                swapped_claim_hierarchies,
            )
        )

        def blank_unavailable_interval_status(frame):
            row = frame.index[frame["missingness_status"].eq("interval_not_saved")][0]
            frame.loc[row, "missingness_status"] = ""

        cases.append(
            (
                "paper.figures.fig2_transportable_signals",
                "fig2_transportable_signals.csv",
                blank_unavailable_interval_status,
            )
        )

        def primary_outside_configuration_range(frame):
            row = frame.index[frame["component"].eq("configuration_range")][0]
            frame.loc[row, "primary_estimate"] = frame.loc[row, "range_high"] + 0.1

        cases.append(
            (
                "paper.figures.fig6_stability_overview",
                "fig6_stability_overview.csv",
                primary_outside_configuration_range,
            )
        )

        for module_name, filename, mutate in cases:
            with self.subTest(
                renderer=module_name, mutation=mutate.__name__
            ), tempfile.TemporaryDirectory() as tmp:
                source = FIGURE_DATA / filename
                path = Path(tmp) / filename
                shutil.copyfile(source, path)
                frame = pd.read_csv(path)
                mutate(frame)
                frame.to_csv(path, index=False)
                module = importlib.import_module(module_name)
                with self.assertRaises(ValueError):
                    module.load_sources((path,))

    def test_sfig3_rejects_grid_mean_that_disagrees_with_saved_seed_cells(self):
        module = importlib.import_module("paper.figures.sfig3_stability_heatmaps")
        sources = (
            FIGURE_DATA / "fig9_stability_grid.csv",
            FIGURE_DATA / "fig9_stability_contrasts.csv",
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._temporary_sources(tmp, sources)
            grid = pd.read_csv(paths[0])
            grid.loc[grid.index[0], "mean"] += 0.01
            grid.to_csv(paths[0], index=False)
            with self.assertRaisesRegex(ValueError, "mean.*reconcile"):
                module.load_sources(paths)

    def test_sfig3_heatmap_suptitle_has_in_canvas_glyph_margin(self):
        module = importlib.import_module("paper.figures.sfig3_stability_heatmaps")
        grid, _contrasts = module.load_sources(
            (
                FIGURE_DATA / "fig9_stability_grid.csv",
                FIGURE_DATA / "fig9_stability_contrasts.csv",
            )
        )
        module.apply_journal_style()
        figure = module._heatmap_page("phenotype", grid)
        try:
            figure.canvas.draw()
            title = figure._suptitle
            renderer = figure.canvas.get_renderer()
            glyph_box = title.get_window_extent(renderer)
            tight_box = figure.get_tightbbox(renderer)
            top_inset_pt = (tight_box.y1 * figure.dpi - glyph_box.y1) * 72 / figure.dpi
            self.assertGreaterEqual(top_inset_pt, 3.0)
        finally:
            plt.close(figure)

    def test_sfig4_evidence_axis_matrix_is_complete_and_deterministic(self):
        module = importlib.import_module("paper.figures.sfig4_evidence_axis_matrix")
        sources = (
            FIGURE_DATA / "evidence_axis_matrix.csv",
            ROOT / "paper/claim_evidence_matrix.csv",
        )
        (frame,) = module.load_sources(sources)
        self.assertEqual(len(frame), 30)
        self.assertEqual(
            frame["state"].value_counts().to_dict(),
            {
                "supported": 8,
                "not_evaluated": 7,
                "context_sensitive": 5,
                "unresolved": 5,
                "not_applicable": 4,
                "unsupported": 1,
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first.pdf", Path(tmp) / "second.pdf"
            module.render(sources, first)
            module.render(sources, second)
            self.assertGreater(first.stat().st_size, 1_000)
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            )
            self.assertLessEqual(
                max(self._media_box_widths_mm(first)), DOUBLE_COLUMN_MM + 1e-6
            )

        with tempfile.TemporaryDirectory() as tmp:
            paths = self._temporary_sources(tmp, sources)
            matrix = pd.read_csv(paths[0]).iloc[:-1]
            matrix.to_csv(paths[0], index=False)
            with self.assertRaisesRegex(ValueError, "complete five-by-six"):
                module.load_sources(paths)

    def test_reviewer_validator_mutations_fail_closed(self):
        cases = []

        def hierarchy(frame):
            frame.loc[frame.index[0], "hierarchy"] = "unapproved"

        cases.append(("paper.figures.fig1_qualification_map", "fig1_qualification_map.csv", hierarchy))

        def nonblank_bad_ci(frame):
            row = frame.index[frame["missingness_status"].eq("interval_not_saved")][0]
            frame["ci_low"] = frame["ci_low"].astype(object)
            frame["ci_high"] = frame["ci_high"].astype(object)
            frame.loc[row, ["ci_low", "ci_high"]] = ["bad", "bad"]

        def reversed_ci(frame):
            row = frame.index[frame["missingness_status"].isin(
                {"none", "replicate_accounting_not_saved"}
            )][0]
            frame.loc[row, ["ci_low", "ci_high"]] = [0.9, 0.1]

        cases.extend((
            ("paper.figures.fig2_transportable_signals", "fig2_transportable_signals.csv", nonblank_bad_ci),
            ("paper.figures.fig2_transportable_signals", "fig2_transportable_signals.csv", reversed_ci),
        ))

        def missing_applicable_interval(frame):
            row = frame.index[frame["component"].eq("frozen_primary")][0]
            frame.loc[row, "interval_low"] = float("nan")

        def reversed_configuration_range(frame):
            row = frame.index[frame["component"].eq("configuration_summary")][0]
            frame.loc[row, ["range_low", "range_high"]] = [0.9, 0.1]

        cases.extend((
            ("paper.figures.fig3_molecular_qualification", "fig3_molecular_qualification.csv", missing_applicable_interval),
            ("paper.figures.fig3_molecular_qualification", "fig3_molecular_qualification.csv", reversed_configuration_range),
        ))

        def wrong_metric(frame):
            row = frame.index[frame["marker"].eq("spop") & frame["component"].eq("configuration_range")][0]
            frame.loc[row, "metric"] = "patient_spearman_rho"

        def fractional_count(frame):
            row = frame.index[frame["component"].eq("configuration_range")][0]
            frame["n_null_crossings"] = frame["n_null_crossings"].astype(float)
            frame.loc[row, "n_null_crossings"] = 0.5

        def negative_count(frame):
            row = frame.index[frame["component"].eq("contrast_sensitivity")][0]
            frame.loc[row, "n_contrasts"] = -1

        def crossings_exceed_configurations(frame):
            row = frame.index[frame["component"].eq("configuration_range")][0]
            frame.loc[row, "n_null_crossings"] = 13

        cases.extend((
            ("paper.figures.fig6_stability_overview", "fig6_stability_overview.csv", wrong_metric),
            ("paper.figures.fig6_stability_overview", "fig6_stability_overview.csv", fractional_count),
            ("paper.figures.fig6_stability_overview", "fig6_stability_overview.csv", negative_count),
            ("paper.figures.fig6_stability_overview", "fig6_stability_overview.csv", crossings_exceed_configurations),
        ))

        for module_name, filename, mutate in cases:
            with self.subTest(renderer=module_name, mutation=mutate.__name__), tempfile.TemporaryDirectory() as tmp:
                source = FIGURE_DATA / filename
                path = Path(tmp) / filename
                shutil.copyfile(source, path)
                frame = pd.read_csv(path)
                mutate(frame)
                frame.to_csv(path, index=False)
                module = importlib.import_module(module_name)
                with self.assertRaises(ValueError):
                    module.load_sources((path,))

if __name__ == "__main__":
    unittest.main()
