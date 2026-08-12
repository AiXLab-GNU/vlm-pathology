"""Render detailed saved discrimination estimates; no curve coordinates are inferred."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from projects.prostate_biomarker_validation.paper.figures.fig2_transportable_signals import load_sources as _load_transport_sources
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


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Reuse the exact transported-signal source contract."""
    return _load_transport_sources(source_paths)


def _label(row: pd.Series) -> str:
    institution = "" if row.institution == row.cohort else f" / {row.institution.capitalize()}"
    unit = {"patient": "patients", "case_image": "cases", "session": "sessions"}[row.analysis_unit]
    return f"{row.cohort}{institution}  (n={int(row.n)} {unit})"


def _plot(
    axis, rows: pd.DataFrame, null: float, xlabel: str, color: str,
    annotation_offset: tuple[float, float] = (8, 0),
    annotation_ha: str = "left",
) -> None:
    rows = rows.reset_index(drop=True)
    y = np.arange(len(rows))
    for index, row in rows.iterrows():
        estimate = float(row.primary_estimate)
        if pd.notna(row.ci_low):
            axis.errorbar(
                estimate, index,
                xerr=[[estimate - float(row.ci_low)], [float(row.ci_high) - estimate]],
                fmt="o", color=color, markersize=6, capsize=3.5,
            )
        else:
            axis.scatter(estimate, index, s=42, facecolor="white", edgecolor=color,
                         linewidth=1.5, zorder=3)
        axis.annotate(
            f"{estimate:.3f}", (estimate, index), xytext=annotation_offset,
            textcoords="offset points", ha=annotation_ha,
            va="bottom" if annotation_offset[1] > 0 else "center",
        )
    axis.axvline(null, color="#6B7280", linestyle="--")
    axis.set_yticks(y, [_label(row) for _, row in rows.iterrows()])
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.set_xlabel(xlabel)
    axis.grid(axis="x", color="#E5E7EB")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render all saved transport estimates in metric-specific panels."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    fig, (axis_a, axis_b, axis_c) = plt.subplots(
        3, 1, figsize=figure_size(FIGURE_WIDTH_MM, 0.95),
        gridspec_kw={"height_ratios": (1.35, 1.0, 1.0)}, constrained_layout=True,
    )

    gleason = frame[(frame.signal == "Gleason") & (frame.metric == "spearman_rho")]
    phenotype_rho = frame[(frame.signal == "Phenotype") &
                          (frame.metric == "spearman_rho")]
    phenotype_auc = frame[(frame.signal == "Phenotype") & (frame.metric == "auroc")]
    _plot(axis_a, gleason, 0.0, "Spearman correlation", COLORBLIND_SAFE_PALETTE[0])
    axis_a.set_xlim(-0.05, 1.02)
    axis_a.set_title("a   Gleason rank association", loc="left", fontweight="bold")

    _plot(
        axis_b, phenotype_rho, 0.0, "Spearman correlation", COLORBLIND_SAFE_PALETTE[2],
        annotation_offset=(0, 8), annotation_ha="center",
    )
    axis_b.set_xlim(-0.05, 1.02)
    axis_b.set_title("b   Phenotype rank association", loc="left", fontweight="bold")

    _plot(axis_c, phenotype_auc, 0.5, "AUROC", COLORBLIND_SAFE_PALETTE[2])
    axis_c.set_xlim(0.45, 1.02)
    axis_c.set_title("c   Phenotype discrimination", loc="left", fontweight="bold")
    axis_c.scatter([], [], s=42, facecolor="white", edgecolor="#374151", linewidth=1.5,
                   label="Interval not saved")
    axis_c.legend(frameon=False, loc="lower right")
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
