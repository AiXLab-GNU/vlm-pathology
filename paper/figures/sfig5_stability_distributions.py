"""Render distributions of all saved seed-matched stability contrasts."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paper.figures.fig9_scale_tile_heatmap import (
    CONTRASTS,
    MARKERS,
    MARKER_LABELS,
    validate_contrasts,
)
from paper.figures.style import (
    COLORBLIND_SAFE_PALETTE,
    DOUBLE_COLUMN_MM,
    apply_journal_style,
    figure_size,
    save_vector_figure,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRASTS = ROOT / "paper/figure_data/fig9_stability_contrasts.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
CONTRAST_TITLES = {
    "native_vs_1.76": "Scale\nΔ shared − native",
    "virchow_vs_conch_at_1.76": "Encoder\nΔ Virchow − CONCH",
    "tile64_vs16": "Tile budget\nΔ 64 − 16 tiles",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    if len(source_paths) != 1:
        raise ValueError("Supplementary Figure 5 requires one contrast CSV")
    contrasts = validate_contrasts(pd.read_csv(Path(source_paths[0])))
    if len(contrasts) != 390 or contrasts["pair_id"].duplicated().any():
        raise ValueError("Supplementary Figure 5 requires 390 unique paired contrasts")
    expected_counts = {
        "native_vs_1.76": 180,
        "virchow_vs_conch_at_1.76": 90,
        "tile64_vs16": 120,
    }
    if contrasts["contrast"].value_counts().to_dict() != expected_counts:
        raise ValueError("Supplementary Figure 5 contrast counts do not reconcile")
    for contrast in CONTRASTS:
        subset = contrasts.loc[contrasts["contrast"].eq(contrast)]
        if set(subset["marker"].astype(str)) != set(MARKERS):
            raise ValueError(f"Supplementary Figure 5 is missing a marker for {contrast}")
    values = pd.to_numeric(contrasts["delta_b_minus_a"], errors="coerce")
    if not np.isfinite(values).all():
        raise ValueError("Supplementary Figure 5 contains a non-finite paired difference")
    return (contrasts.sort_values(["contrast", "marker", "pair_id"]).reset_index(drop=True),)


def _deterministic_offsets(count: int) -> np.ndarray:
    if count <= 1:
        return np.zeros(count)
    sequence = np.arange(count, dtype=float)
    centered = (sequence % 7) - 3
    return centered * 0.027


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    (contrasts,) = load_sources(source_paths)
    apply_journal_style()
    figure, axes = plt.subplots(
        1, 3, sharey=True,
        figsize=figure_size(175, 0.52),
        constrained_layout=True,
    )
    positions = np.arange(len(MARKERS))
    for panel_index, (axis, contrast) in enumerate(zip(axes, CONTRASTS, strict=True)):
        panel = contrasts.loc[contrasts["contrast"].eq(contrast)]
        distributions = [
            panel.loc[panel["marker"].eq(marker), "delta_b_minus_a"].astype(float).to_numpy()
            for marker in MARKERS
        ]
        violins = axis.violinplot(
            distributions, positions=positions, orientation="horizontal",
            showmeans=False, showmedians=False, showextrema=False, widths=0.72,
        )
        for body in violins["bodies"]:
            body.set_facecolor("#D1D5DB")
            body.set_edgecolor("#6B7280")
            body.set_alpha(0.72)
        axis.boxplot(
            distributions, positions=positions, orientation="horizontal", widths=0.20,
            showfliers=False, patch_artist=True,
            boxprops={"facecolor": "white", "edgecolor": "#374151"},
            medianprops={"color": "#111827", "linewidth": 1.5},
            whiskerprops={"color": "#374151"}, capprops={"color": "#374151"},
        )
        for marker_index, marker in enumerate(MARKERS):
            rows = panel.loc[panel["marker"].eq(marker)].sort_values("pair_id")
            colors = np.where(
                rows["null_crossing"].astype(bool),
                COLORBLIND_SAFE_PALETTE[1], COLORBLIND_SAFE_PALETTE[0],
            )
            axis.scatter(
                rows["delta_b_minus_a"].astype(float),
                marker_index + _deterministic_offsets(len(rows)),
                c=colors, s=9, alpha=0.58, edgecolor="none", zorder=3,
            )
        axis.axvline(0, color="#4B5563", linestyle="--")
        axis.set_title(
            f"{chr(ord('a') + panel_index)}   {CONTRAST_TITLES[contrast]}",
            loc="left", fontweight="bold", fontsize=9.0,
        )
        axis.set_yticks(positions, [MARKER_LABELS[marker] for marker in MARKERS])
        axis.grid(axis="x", color="#E5E7EB")
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="y", length=0)
    axes[0].invert_yaxis()
    axes[1].set_xlabel("Paired metric difference (B − A)")
    handles = (
        plt.Line2D([], [], marker="o", linestyle="none", color=COLORBLIND_SAFE_PALETTE[0],
                   label="Same side of null"),
        plt.Line2D([], [], marker="o", linestyle="none", color=COLORBLIND_SAFE_PALETTE[1],
                   label="Crosses marker-specific null"),
    )
    figure.legend(handles=handles, loc="outside lower center", ncol=2, frameon=False)
    save_vector_figure(figure, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contrasts", type=Path, default=DEFAULT_CONTRASTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.contrasts,), args.output)


if __name__ == "__main__":
    main()
