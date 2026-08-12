"""Render endpoint-conditioned marker-7 transfer from its frozen CSV source."""
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
DEFAULT_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig5_marker7_transfer.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
ENDPOINTS = ("E04_reconstructed_with_tumor", "E08_official_pfi")
CONTRASTS = (
    "GRADE_COMBINED_VS_GRADE", "FULL_COMBINED_VS_FULL", "IMAGE_VS_GRADE",
    "IMAGE_VS_FULL", "M5_VS_M4",
)
CONTRAST_LABELS = {
    "GRADE_COMBINED_VS_GRADE": "Add image to grade",
    "FULL_COMBINED_VS_FULL": "Add image to full clinical model",
    "IMAGE_VS_GRADE": "Image-only vs grade-only",
    "IMAGE_VS_FULL": "Image-only vs full clinical model",
    "M5_VS_M4": "Full clinical + site + image\nvs full clinical + site",
}
EXPECTED_KEYS = {
    f"{endpoint}:frozen_risk:c_index" for endpoint in ENDPOINTS
} | {
    f"{endpoint}:{contrast}:{metric}"
    for endpoint in ENDPOINTS for contrast in CONTRASTS
    for metric in ("c_index", "ibs_0.5_5y")
}
REQUIRED_COLUMNS = {
    "semantic_key", "endpoint_id", "endpoint_label", "result_type", "contrast_id",
    "metric", "n", "n_events", "primary_estimate", "ci_low", "ci_high", "null_value",
    "evidence_state", "missingness_status", "missingness_detail", "source_path",
    "source_field",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Load exact endpoint/performance/contrast groups with finite intervals."""
    if len(source_paths) != 1:
        raise ValueError("Figure 5 requires exactly one source CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Figure 5 missing required columns: {sorted(missing)}")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].duplicated().any():
        raise ValueError("Figure 5 semantic_key values must be present and unique")
    if set(frame["semantic_key"]) != EXPECTED_KEYS:
        raise ValueError("Figure 5 semantic keys do not match both endpoint groups")
    if set(frame["endpoint_id"]) != set(ENDPOINTS):
        raise ValueError("Figure 5 requires official PFI and reconstructed endpoint groups")
    if set(frame["result_type"]) != {"frozen_risk_performance", "same_patient_same_draw_delta"}:
        raise ValueError("Figure 5 result_type groups do not reconcile")
    if set(frame["metric"]) != {"c_index", "ibs_0.5_5y"}:
        raise ValueError("Figure 5 metric groups do not reconcile")
    for column in ("n", "n_events", "primary_estimate", "ci_low", "ci_high", "null_value"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError(f"Figure 5 {column} must be finite")
    estimate = pd.to_numeric(frame["primary_estimate"])
    low = pd.to_numeric(frame["ci_low"])
    high = pd.to_numeric(frame["ci_high"])
    if (low > estimate).any() or (high < estimate).any():
        raise ValueError("Figure 5 intervals must contain their estimates")
    paired = frame["result_type"].eq("same_patient_same_draw_delta")
    if not pd.to_numeric(frame.loc[paired, "n"]).eq(153).all():
        raise ValueError("Figure 5 paired contrasts must use 153 complete cases")
    if set(frame.loc[frame.endpoint_id == ENDPOINTS[0], "n_events"]) != {57, 30}:
        raise ValueError("Figure 5 reconstructed endpoint event counts do not reconcile")
    if set(frame.loc[frame.endpoint_id == ENDPOINTS[1], "n_events"]) != {42, 15}:
        raise ValueError("Figure 5 official PFI event counts do not reconcile")
    if set(frame["missingness_status"]) != {"bootstrap_accounted"}:
        raise ValueError("Figure 5 bootstrap missingness must be explicit")
    for column in ("endpoint_label", "evidence_state", "missingness_detail", "source_path",
                   "source_field"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Figure 5 {column} must be explicitly populated")
    return (frame.reset_index(drop=True),)


def _interval(axis, estimate: float, low: float, high: float, y: float,
              color: str, label: str | None = None) -> None:
    axis.errorbar(estimate, y, xerr=[[estimate - low], [high - estimate]], fmt="o",
                  color=color, capsize=3, markersize=5.5, label=label)


def _paired_panel(axis, frame: pd.DataFrame, metric: str, xlabel: str) -> None:
    subset = frame[(frame.result_type == "same_patient_same_draw_delta") &
                   (frame.metric == metric)]
    y = np.arange(len(CONTRASTS))
    endpoint_style = {
        ENDPOINTS[0]: (-0.12, COLORBLIND_SAFE_PALETTE[0], "Reconstructed; 30 events"),
        ENDPOINTS[1]: (0.12, COLORBLIND_SAFE_PALETTE[1], "Official PFI; 15 events"),
    }
    for endpoint, (offset, color, label) in endpoint_style.items():
        rows = subset[subset.endpoint_id == endpoint].set_index("contrast_id").loc[list(CONTRASTS)]
        for index, row in enumerate(rows.itertuples(index=False)):
            _interval(axis, float(row.primary_estimate), float(row.ci_low), float(row.ci_high),
                      index + offset, color, label if index == 0 else None)
    axis.axvline(0.0, color="#6B7280", linestyle="--")
    axis.set_yticks(y, [CONTRAST_LABELS[value] for value in CONTRASTS])
    axis.set_ylim(len(CONTRASTS) - 0.5, -0.5)
    axis.set_xlabel(xlabel)
    axis.grid(axis="x", color="#E5E7EB")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render frozen risk and complete-case paired contrasts by exact endpoint."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    fig = plt.figure(figsize=figure_size(FIGURE_WIDTH_MM, 1.18), constrained_layout=True)
    grid = fig.add_gridspec(4, 1, height_ratios=(0.66, 0.18, 1.22, 1.22))
    axis_a = fig.add_subplot(grid[0, 0])
    note_axis = fig.add_subplot(grid[1, 0])
    axis_b = fig.add_subplot(grid[2, 0])
    axis_c = fig.add_subplot(grid[3, 0])

    frozen = frame[frame.result_type == "frozen_risk_performance"].set_index("endpoint_id")
    frozen = frozen.loc[list(ENDPOINTS)]
    frozen_labels = (
        "Reconstructed endpoint  (n=270; 57 events)",
        "Official TCGA-CDR PFI  (n=270; 42 events)",
    )
    for index, (endpoint, row) in enumerate(frozen.iterrows()):
        _interval(axis_a, float(row.primary_estimate), float(row.ci_low), float(row.ci_high),
                  index, (COLORBLIND_SAFE_PALETTE[0], COLORBLIND_SAFE_PALETTE[1])[index])
    axis_a.axvline(0.5, color="#6B7280", linestyle="--")
    axis_a.set_yticks([0, 1], frozen_labels)
    axis_a.set_ylim(1.5, -0.5)
    axis_a.set_xlim(0.44, 0.80)
    axis_a.set_xlabel("Frozen image-risk C-index")
    axis_a.set_title("a   Endpoint-specific performance", loc="left", fontweight="bold")
    axis_a.grid(axis="x", color="#E5E7EB")
    axis_a.spines[["top", "right", "left"]].set_visible(False)
    axis_a.tick_params(axis="y", length=0)

    note_axis.axis("off")
    note_axis.scatter([], [], color=COLORBLIND_SAFE_PALETTE[0], label="Reconstructed; 30 events")
    note_axis.scatter([], [], color=COLORBLIND_SAFE_PALETTE[1], label="Official PFI; 15 events")
    note_axis.set_title("Same-patient/same-draw contrasts\n153 complete cases",
                        loc="center", fontweight="bold")
    note_axis.legend(frameon=False, loc="center", ncol=2)

    _paired_panel(
        axis_b, frame, "c_index", "C-index change (comparison − reference)"
    )
    axis_b.set_xlim(-0.43, 0.20)
    axis_b.set_title("b   Paired C-index", loc="left", fontweight="bold")

    _paired_panel(
        axis_c, frame, "ibs_0.5_5y", "IBS reduction (reference − comparison)"
    )
    axis_c.set_xlim(-0.05, 0.025)
    axis_c.set_xticks(np.arange(-0.05, 0.021, 0.01))
    axis_c.set_title("c   Paired IBS", loc="left", fontweight="bold")
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
