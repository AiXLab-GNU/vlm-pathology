"""Render transported grade and phenotype estimates from the submission CSV."""
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
DEFAULT_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig2_transportable_signals.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM

REQUIRED_COLUMNS = {
    "semantic_key", "signal", "cohort", "institution", "encoder", "metric",
    "analysis_unit", "n", "n_events", "primary_estimate", "ci_low", "ci_high",
    "evidence_state", "missingness_status", "missingness_detail", "source_path",
    "source_field",
}
EXPECTED_KEYS = {
    "gleason:nadt", "phenotype:nadt", "gleason_panda:karolinska",
    "gleason_panda:radboud", "phenotype_panda:karolinska",
    "phenotype_panda:radboud", "gleason_precise:all",
}
EXPECTED_MISSINGNESS_STATUSES = {
    "replicate_accounting_not_saved", "interval_not_saved",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Load the exact seven transported-signal rows with explicit missingness."""
    if len(source_paths) != 1:
        raise ValueError("Figure 2 requires exactly one source CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Figure 2 missing required columns: {sorted(missing)}")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].duplicated().any():
        raise ValueError("Figure 2 semantic_key values must be present and unique")
    if set(frame["semantic_key"]) != EXPECTED_KEYS:
        raise ValueError("Figure 2 semantic keys do not match the seven frozen estimates")
    if set(frame["cohort"]) != {"NADT", "PANDA", "PRECISE"}:
        raise ValueError("Figure 2 requires NADT, PANDA, and PRECISE cohorts")
    if set(frame["signal"]) != {"Gleason", "Phenotype"}:
        raise ValueError("Figure 2 requires Gleason and Phenotype groups")
    if set(frame["metric"]) != {"spearman_rho", "auroc"}:
        raise ValueError("Figure 2 metric groups do not reconcile")
    if set(frame["evidence_state"]) != {"transportable"}:
        raise ValueError("Figure 2 evidence_state must be transportable")
    if set(frame["missingness_status"]) != EXPECTED_MISSINGNESS_STATUSES:
        raise ValueError("Figure 2 interval missingness statuses do not reconcile")
    estimates = pd.to_numeric(frame["primary_estimate"], errors="coerce").to_numpy(float)
    denominators = pd.to_numeric(frame["n"], errors="coerce").to_numpy(float)
    if not np.isfinite(estimates).all() or not np.isfinite(denominators).all():
        raise ValueError("Figure 2 estimates and denominators must be finite")
    if (denominators <= 0).any() or not np.equal(denominators, np.floor(denominators)).all():
        raise ValueError("Figure 2 denominators must be positive integers")
    raw_low = frame["ci_low"]
    raw_high = frame["ci_high"]
    low_present = raw_low.notna() & raw_low.astype(str).str.strip().ne("")
    high_present = raw_high.notna() & raw_high.astype(str).str.strip().ne("")
    if low_present.ne(high_present).any():
        raise ValueError("Figure 2 interval bounds must be both present or both missing")
    low = pd.to_numeric(raw_low, errors="coerce")
    high = pd.to_numeric(raw_high, errors="coerce")
    if ((low_present & ~np.isfinite(low)) | (high_present & ~np.isfinite(high))).any():
        raise ValueError("Figure 2 populated interval bounds must be finite numeric values")
    has_interval = frame["missingness_status"].isin(
        {"none", "replicate_accounting_not_saved"}
    )
    if low_present.ne(has_interval).any():
        raise ValueError("Figure 2 interval missingness disagrees with missingness_status")
    if (low[has_interval] > estimates[has_interval]).any() or (
        high[has_interval] < estimates[has_interval]
    ).any():
        raise ValueError("Figure 2 interval bounds must contain the estimate")
    for column in ("institution", "encoder", "analysis_unit", "missingness_detail",
                   "source_path", "source_field"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Figure 2 {column} must be explicitly populated")
    return (frame.reset_index(drop=True),)


def _row_label(row: pd.Series) -> str:
    unit = {"patient": "patients", "case_image": "cases", "session": "sessions"}[row.analysis_unit]
    institution = "" if row.institution == row.cohort else f", {row.institution.capitalize()}"
    return f"{row.signal}: {row.cohort}{institution}\nn={int(row.n)} {unit}"


def _forest(axis, frame: pd.DataFrame, null: float, xlabel: str) -> None:
    rows = frame.reset_index(drop=True)
    y = np.arange(len(rows))
    colors = [COLORBLIND_SAFE_PALETTE[0] if signal == "Gleason"
              else COLORBLIND_SAFE_PALETTE[2] for signal in rows["signal"]]
    for index, row in rows.iterrows():
        estimate = float(row.primary_estimate)
        if pd.notna(row.ci_low):
            axis.errorbar(
                estimate, index,
                xerr=[[estimate - float(row.ci_low)], [float(row.ci_high) - estimate]],
                fmt="o", color=colors[index], capsize=3.5, markersize=6,
            )
        else:
            axis.scatter(estimate, index, s=42, facecolor="white", edgecolor=colors[index],
                         linewidth=1.5, zorder=3)
    axis.axvline(null, color="#6B7280", linestyle="--", linewidth=1.0)
    axis.set_yticks(y, [_row_label(row) for _, row in rows.iterrows()])
    axis.set_xlabel(xlabel)
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.grid(axis="x", color="#E5E7EB")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render rank correlation and AUROC on separate scales."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    correlations = frame[frame["metric"].eq("spearman_rho")]
    aurocs = frame[frame["metric"].eq("auroc")]
    fig, (axis_a, axis_b) = plt.subplots(
        2, 1, figsize=figure_size(FIGURE_WIDTH_MM, 0.72),
        gridspec_kw={"height_ratios": (1.0, 1.25)}, constrained_layout=True,
    )
    _forest(axis_a, correlations, 0.0, "Spearman correlation")
    axis_a.set_xlim(-0.05, 1.0)
    axis_a.set_title("a   Rank correlation", loc="left", fontweight="bold")

    _forest(axis_b, aurocs, 0.5, "AUROC")
    axis_b.set_xlim(0.45, 1.0)
    axis_b.set_title("b   Phenotype discrimination", loc="left", fontweight="bold")
    axis_b.scatter([], [], s=42, facecolor="white", edgecolor="#374151", linewidth=1.5,
                   label="Interval not saved")
    axis_b.legend(frameon=False, loc="lower right")
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
