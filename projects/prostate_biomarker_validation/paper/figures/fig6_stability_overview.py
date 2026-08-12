"""Render a decision-level stability overview without the full heatmap grid."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from projects.prostate_biomarker_validation.paper.figures.style import (
    COLORBLIND_SAFE_PALETTE,
    DOUBLE_COLUMN_MM,
    PANEL_FONT_PT,
    apply_journal_style,
    figure_size,
    save_vector_figure,
)


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig6_stability_overview.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
MARKERS = ("gleason", "phenotype", "pten", "spop", "ar", "marker7")
MARKER_LABELS = {
    "gleason": "Gleason", "phenotype": "Phenotype", "pten": "PTEN",
    "spop": "SPOP", "ar": "AR", "marker7": "Recurrence risk",
}
EXPECTED_KEYS = {
    f"{marker}:{component}" for marker in MARKERS
    for component in ("configuration_range", "contrast_sensitivity")
}
REQUIRED_COLUMNS = {
    "semantic_key", "marker", "component", "metric", "null_value",
    "primary_estimate", "range_low", "range_high", "n_configurations",
    "n_correlated_cells", "n_null_crossings", "n_contrasts", "evidence_state",
    "missingness_status", "missingness_detail", "source_path", "source_field",
}
RANGE_METRICS = {
    "gleason": "patient_spearman_rho",
    "phenotype": "patient_auroc",
    "pten": "patient_auroc",
    "spop": "patient_auroc",
    "ar": "patient_spearman_rho",
    "marker7": "patient_c_index",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Load all six marker range/sensitivity pairs with finite summaries."""
    if len(source_paths) != 1:
        raise ValueError("Figure 6 requires exactly one source CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Figure 6 missing required columns: {sorted(missing)}")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].duplicated().any():
        raise ValueError("Figure 6 semantic_key values must be present and unique")
    if set(frame["semantic_key"]) != EXPECTED_KEYS:
        raise ValueError("Figure 6 semantic keys do not match six marker component pairs")
    if set(frame["marker"]) != set(MARKERS):
        raise ValueError("Figure 6 requires all six markers")
    if set(frame["component"]) != {"configuration_range", "contrast_sensitivity"}:
        raise ValueError("Figure 6 component groups do not reconcile")
    for column in ("null_value", "primary_estimate", "range_low", "range_high",
                   "n_configurations", "n_correlated_cells", "n_null_crossings",
                   "n_contrasts"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError(f"Figure 6 {column} must be finite")
    if (pd.to_numeric(frame["range_low"]) > pd.to_numeric(frame["range_high"])).any():
        raise ValueError("Figure 6 ranges are reversed")
    ranges = frame["component"].eq("configuration_range")
    contrasts = ~ranges
    range_estimates = pd.to_numeric(frame.loc[ranges, "primary_estimate"])
    if (pd.to_numeric(frame.loc[ranges, "range_low"]) > range_estimates).any() or (
        pd.to_numeric(frame.loc[ranges, "range_high"]) < range_estimates
    ).any():
        raise ValueError("Figure 6 configuration ranges must contain primary_estimate")
    expected_metrics = frame.apply(
        lambda row: RANGE_METRICS[row["marker"]]
        if row["component"] == "configuration_range" else "paired_delta",
        axis=1,
    )
    if not frame["metric"].eq(expected_metrics).all():
        raise ValueError("Figure 6 marker/component metric mapping does not reconcile")
    count_columns = (
        "n_configurations", "n_correlated_cells", "n_null_crossings", "n_contrasts"
    )
    for column in count_columns:
        values = pd.to_numeric(frame[column]).to_numpy(float)
        if (values < 0).any() or not np.equal(values, np.floor(values)).all():
            raise ValueError(f"Figure 6 {column} must contain nonnegative integer counts")
    if not pd.to_numeric(frame.loc[ranges, "n_configurations"]).eq(12).all():
        raise ValueError("Figure 6 range rows must summarize 12 configurations")
    if not pd.to_numeric(frame.loc[ranges, "n_correlated_cells"]).eq(60).all():
        raise ValueError("Figure 6 range rows must summarize 60 correlated cells")
    if not pd.to_numeric(frame.loc[contrasts, "n_contrasts"]).eq(65).all():
        raise ValueError("Figure 6 sensitivity rows must summarize 65 contrasts")
    if not pd.to_numeric(frame.loc[ranges, "n_contrasts"]).eq(0).all() or not (
        pd.to_numeric(frame.loc[contrasts, "n_configurations"]).eq(0).all()
        and pd.to_numeric(frame.loc[contrasts, "n_correlated_cells"]).eq(0).all()
    ):
        raise ValueError("Figure 6 component-specific count scopes do not reconcile")
    if (pd.to_numeric(frame.loc[ranges, "n_null_crossings"]) > 12).any() or (
        pd.to_numeric(frame.loc[contrasts, "n_null_crossings"]) > 65
    ).any():
        raise ValueError("Figure 6 null-crossing counts exceed their denominators")
    if set(frame["missingness_status"]) != {"none"}:
        raise ValueError("Figure 6 missingness_status must explicitly be none")
    for column in ("metric", "evidence_state", "missingness_detail", "source_path",
                   "source_field"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Figure 6 {column} must be explicitly populated")
    return (frame.reset_index(drop=True),)


def configuration_straddle_percentages(frame: pd.DataFrame) -> pd.Series:
    """Return percent of 12 configurations whose five-seed range straddles null."""
    rows = frame[frame["component"].eq("configuration_range")].set_index("marker")
    return 100.0 * pd.to_numeric(rows["n_null_crossings"]) / pd.to_numeric(
        rows["n_configurations"]
    )


def _range_panel(axis, frame: pd.DataFrame, markers: tuple[str, ...], xlabel: str,
                 color: str) -> None:
    rows = frame.set_index("marker").loc[list(markers)]
    y = np.arange(len(rows))
    for index, (marker, row) in enumerate(rows.iterrows()):
        null = float(row.null_value)
        low = float(row.range_low) - null
        high = float(row.range_high) - null
        mean = float(row.primary_estimate) - null
        axis.plot([low, high], [index, index], color=color, linewidth=4,
                  solid_capstyle="butt")
        axis.scatter(mean, index, s=38, facecolor="white", edgecolor=color,
                     linewidth=1.4, zorder=3)
    axis.axvline(0.0, color="#6B7280", linestyle="--")
    axis.set_yticks(y, [MARKER_LABELS[marker] for marker in markers])
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.set_xlabel(xlabel)
    axis.grid(axis="x", color="#E5E7EB")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render marker ranges relative to null and compact sensitivity counts."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    ranges = frame[frame.component == "configuration_range"]
    sensitivity = frame[frame.component == "contrast_sensitivity"].set_index("marker")
    fig = plt.figure(figsize=figure_size(FIGURE_WIDTH_MM, 0.68), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=(0.85, 1.25))
    axis_a = fig.add_subplot(grid[0, 0])
    axis_b = fig.add_subplot(grid[0, 1])
    axis_c = fig.add_subplot(grid[0, 2])
    axis_d = fig.add_subplot(grid[1, :])

    _range_panel(axis_a, ranges, ("gleason", "ar"), "Spearman correlation − null",
                 COLORBLIND_SAFE_PALETTE[0])
    axis_a.set_title("a   Rank correlations", loc="left", fontweight="bold")
    _range_panel(axis_b, ranges, ("phenotype", "pten", "spop"), "AUROC − null",
                 COLORBLIND_SAFE_PALETTE[2])
    axis_b.set_title("b   Binary targets", loc="left", fontweight="bold")
    _range_panel(axis_c, ranges, ("marker7",), "C-index − null",
                 COLORBLIND_SAFE_PALETTE[1])
    axis_c.set_title("c   Survival\nendpoint", loc="left", fontweight="bold")

    order = list(MARKERS)
    range_rows = ranges.set_index("marker").loc[order]
    contrast_rows = sensitivity.loc[order]
    y = np.arange(len(order))
    config_rates = configuration_straddle_percentages(frame).loc[order].to_numpy(float)
    contrast_rates = 100 * contrast_rows["n_null_crossings"].to_numpy(float) / 65.0
    axis_d.barh(y - 0.17, config_rates, height=0.30, color=COLORBLIND_SAFE_PALETTE[3],
                label="Configurations whose seed range straddled the null (of 12)")
    axis_d.barh(y + 0.17, contrast_rates, height=0.30, color=COLORBLIND_SAFE_PALETTE[1],
                label="Paired contrasts crossing null (of 65)")
    axis_d.set_yticks(y, [MARKER_LABELS[marker] for marker in order])
    axis_d.set_ylim(len(order) - 0.6, -0.6)
    axis_d.set_xlim(0, max(50, float(max(config_rates.max(), contrast_rates.max())) + 8))
    axis_d.set_xticks(np.arange(0, 71, 10))
    axis_d.set_xlabel("Null-crossing sensitivity (%)")
    axis_d.set_title(
        "d   Configuration sensitivity\n"
        "12 configurations; 60 correlated cells per target",
        loc="left", fontweight="bold",
    )
    axis_d.legend(frameon=False, loc="lower right")
    axis_d.grid(axis="x", color="#E5E7EB")
    axis_d.spines[["top", "right", "left"]].set_visible(False)
    axis_d.tick_params(axis="y", length=0)
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
