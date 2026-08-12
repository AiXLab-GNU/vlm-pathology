"""Render target-specific molecular qualification summaries from saved CSV data."""
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
DEFAULT_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig3_molecular_qualification.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
SITES = ("CH", "EJ", "G9", "HC", "KK", "YL")
EXPECTED_KEYS = {
    "pten:frozen_primary", "pten:configuration_summary",
    "spop:frozen_primary", "spop:configuration_summary",
    "ar:frozen_primary", "ar:configuration_summary",
} | {f"spop:site:{site}" for site in SITES}
GLOBAL_SEED_CELL_RANGE_TYPE = "global_correlated_seed_cell_range"
REQUIRED_COLUMNS = {
    "semantic_key", "target", "component", "cohort", "encoder", "metric",
    "analysis_unit", "patient_denominator", "event_count", "null_value",
    "primary_estimate", "interval_low", "interval_high", "interval_type",
    "range_low", "range_high", "n_correlated_cells", "evidence_state",
    "missingness_status", "missingness_detail", "source_path", "source_field",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Load and validate all target, interval, range, and missingness groups."""
    if len(source_paths) != 1:
        raise ValueError("Figure 3 requires exactly one source CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Figure 3 missing required columns: {sorted(missing)}")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].duplicated().any():
        raise ValueError("Figure 3 semantic_key values must be present and unique")
    if set(frame["semantic_key"]) != EXPECTED_KEYS:
        raise ValueError("Figure 3 semantic keys do not match the frozen target/site groups")
    if set(frame["target"]) != {"PTEN", "SPOP", "AR"}:
        raise ValueError("Figure 3 requires PTEN, SPOP, and AR target groups")
    if set(frame["component"]) != {"frozen_primary", "configuration_summary", "site_audit"}:
        raise ValueError("Figure 3 component groups do not reconcile")
    for column in ("patient_denominator", "null_value", "primary_estimate",
                   "n_correlated_cells"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError(f"Figure 3 {column} must be finite")
    if (pd.to_numeric(frame["patient_denominator"]) <= 0).any():
        raise ValueError("Figure 3 patient denominators must be positive")
    raw_interval_low = frame["interval_low"]
    raw_interval_high = frame["interval_high"]
    interval_low_present = (
        raw_interval_low.notna() & raw_interval_low.astype(str).str.strip().ne("")
    )
    interval_high_present = (
        raw_interval_high.notna() & raw_interval_high.astype(str).str.strip().ne("")
    )
    if interval_low_present.ne(interval_high_present).any():
        raise ValueError("Figure 3 interval bounds must be paired")
    interval_low = pd.to_numeric(raw_interval_low, errors="coerce")
    interval_high = pd.to_numeric(raw_interval_high, errors="coerce")
    if ((interval_low_present & ~np.isfinite(interval_low)) |
            (interval_high_present & ~np.isfinite(interval_high))).any():
        raise ValueError("Figure 3 populated interval bounds must be finite numeric values")
    undefined = frame["missingness_status"].eq("primary_metric_undefined")
    interval_applicable = frame["component"].eq("frozen_primary") | (
        frame["component"].eq("site_audit") & ~undefined
    )
    if interval_low_present.ne(interval_applicable).any():
        raise ValueError("Figure 3 interval missingness disagrees with applicability")
    estimate = pd.to_numeric(frame["primary_estimate"])
    if (interval_low[interval_applicable] > estimate[interval_applicable]).any() or (
        interval_high[interval_applicable] < estimate[interval_applicable]
    ).any():
        raise ValueError("Figure 3 intervals must contain their estimates")
    ranged = frame["component"].eq("configuration_summary")
    if not frame.loc[ranged, "interval_type"].astype(str).eq(
        GLOBAL_SEED_CELL_RANGE_TYPE
    ).all():
        raise ValueError(
            "Figure 3 configuration summaries require the global correlated "
            "seed-cell range type"
        )
    raw_range_low = frame["range_low"]
    raw_range_high = frame["range_high"]
    range_low_present = raw_range_low.notna() & raw_range_low.astype(str).str.strip().ne("")
    range_high_present = raw_range_high.notna() & raw_range_high.astype(str).str.strip().ne("")
    if range_low_present.ne(range_high_present).any():
        raise ValueError("Figure 3 range bounds must be paired")
    range_low = pd.to_numeric(raw_range_low, errors="coerce")
    range_high = pd.to_numeric(raw_range_high, errors="coerce")
    if ((range_low_present & ~np.isfinite(range_low)) |
            (range_high_present & ~np.isfinite(range_high))).any():
        raise ValueError("Figure 3 populated range bounds must be finite numeric values")
    if range_low_present.ne(ranged).any():
        raise ValueError("Figure 3 range missingness disagrees with component")
    if (range_low[ranged] > estimate[ranged]).any() or (
        range_high[ranged] < estimate[ranged]
    ).any():
        raise ValueError("Figure 3 global seed-cell ranges must contain their summaries")
    if set(frame.loc[undefined, "semantic_key"]) != {"spop:site:CH"}:
        raise ValueError("Figure 3 undefined primary metric must be explicit for SPOP site CH")
    for column in ("interval_type", "evidence_state", "missingness_status",
                   "missingness_detail", "source_path", "source_field"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Figure 3 {column} must be explicitly populated")
    return (frame.reset_index(drop=True),)


def _errorbar(axis, row: pd.Series, y: float, color: str, label: str | None = None) -> None:
    estimate = float(row.primary_estimate)
    axis.errorbar(
        estimate, y,
        xerr=[[estimate - float(row.interval_low)], [float(row.interval_high) - estimate]],
        fmt="o", color=color, markersize=6, capsize=3.5, label=label,
    )


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render AUROC, correlation, and SPOP site evidence on separate axes."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    fig = plt.figure(figsize=figure_size(FIGURE_WIDTH_MM, 0.78), constrained_layout=True)
    grid = fig.add_gridspec(3, 2, height_ratios=(0.85, 0.16, 1.15))
    axis_a = fig.add_subplot(grid[0, 0])
    axis_b = fig.add_subplot(grid[0, 1])
    legend_axis = fig.add_subplot(grid[1, :])
    axis_c = fig.add_subplot(grid[2, :])

    for y, target, color in ((0, "PTEN", COLORBLIND_SAFE_PALETTE[0]),
                             (1, "SPOP", COLORBLIND_SAFE_PALETTE[1])):
        primary = frame[(frame.target == target) & (frame.component == "frozen_primary")].iloc[0]
        summary = frame[(frame.target == target) &
                        (frame.component == "configuration_summary")].iloc[0]
        _errorbar(axis_a, primary, y - 0.10, color,
                  "Frozen primary; patient bootstrap" if y == 0 else None)
        axis_a.plot([summary.range_low, summary.range_high], [y + 0.15, y + 0.15],
                    color=color, linewidth=4, solid_capstyle="butt",
                    label="Global correlated seed-cell range" if y == 0 else None)
        axis_a.scatter(float(summary.primary_estimate), y + 0.15, color="white",
                       edgecolor=color, linewidth=1.3, s=32, zorder=3)
    axis_a.axvline(0.5, color="#6B7280", linestyle="--")
    axis_a.set_yticks([0, 1], ["PTEN", "SPOP"])
    axis_a.set_xlabel("Patient AUROC")
    axis_a.set_xlim(0.30, 0.80)
    axis_a.set_ylim(1.6, -0.5)
    axis_a.set_title("a   Binary targets", loc="left", fontweight="bold")

    ar_primary = frame[(frame.target == "AR") & (frame.component == "frozen_primary")].iloc[0]
    ar_summary = frame[(frame.target == "AR") &
                       (frame.component == "configuration_summary")].iloc[0]
    _errorbar(axis_b, ar_primary, 0.0, COLORBLIND_SAFE_PALETTE[2])
    axis_b.plot([ar_summary.range_low, ar_summary.range_high], [0.28, 0.28],
                color=COLORBLIND_SAFE_PALETTE[2], linewidth=4, solid_capstyle="butt")
    axis_b.scatter(float(ar_summary.primary_estimate), 0.28, color="white",
                   edgecolor=COLORBLIND_SAFE_PALETTE[2], linewidth=1.3, s=32, zorder=3)
    axis_b.axvline(0.0, color="#6B7280", linestyle="--")
    axis_b.set_yticks([0.0, 0.28], ["Frozen primary", "Seed-cell range"])
    axis_b.set_xlabel("Patient Spearman correlation")
    axis_b.set_xlim(-0.03, 0.34)
    axis_b.set_ylim(0.55, -0.25)
    axis_b.set_title("b   AR association", loc="left", fontweight="bold")

    handles, labels = axis_a.get_legend_handles_labels()
    legend_axis.axis("off")
    legend_axis.legend(handles, labels, frameon=False, loc="center", ncol=2)

    sites = frame[frame.component == "site_audit"].set_index(
        frame.loc[frame.component == "site_audit", "semantic_key"].str.rsplit(":", n=1).str[-1]
    )
    y = np.arange(len(SITES))
    for index, site in enumerate(SITES):
        row = sites.loc[site]
        if row.metric == "patient_auroc":
            _errorbar(axis_c, row, index, COLORBLIND_SAFE_PALETTE[1])
        else:
            axis_c.scatter(0.5, index, marker="x", s=55, color=COLORBLIND_SAFE_PALETTE[3],
                           linewidth=1.5)
            axis_c.text(0.515, index, "AUROC undefined; 0/23 events", va="center")
    axis_c.axvline(0.5, color="#6B7280", linestyle="--")
    axis_c.set_yticks(y, [f"{site}  (n={int(sites.loc[site].patient_denominator)})"
                         for site in SITES])
    axis_c.set_xlabel("SPOP patient AUROC")
    axis_c.set_xlim(0.20, 1.02)
    axis_c.set_ylim(len(SITES) - 0.5, -0.5)
    axis_c.set_title("c   SPOP site audit", loc="left", fontweight="bold")

    for axis in (axis_a, axis_b, axis_c):
        axis.grid(axis="x", color="#E5E7EB")
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="y", length=0)
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
