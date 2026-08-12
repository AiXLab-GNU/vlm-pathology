"""Render the complete validated stability grid and paired contrasts by marker."""
from __future__ import annotations

import argparse
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from projects.prostate_biomarker_validation.paper.figures.fig9_scale_tile_heatmap import (
    CONTRASTS,
    ENCODERS,
    MARKERS,
    MARKER_LABELS,
    MARKER_MAPPING,
    NATIVE_MPP,
    SHARED_MPP,
    TILES,
    validate_contrasts,
    validate_grid,
)
from projects.prostate_biomarker_validation.paper.figures.style import (
    COLORBLIND_SAFE_PALETTE,
    DOUBLE_COLUMN_MM,
    PANEL_FONT_PT,
    apply_journal_style,
    figure_size,
)


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_GRID = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_grid.csv"
DEFAULT_CONTRASTS = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_contrasts.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
PDF_METADATA = {
    "Creator": "vlm-pathology",
    "Producer": "vlm-pathology",
    "CreationDate": None,
    "ModDate": None,
}
CONTRAST_TITLES = {
    "native_vs_1.76": "Scale contrast (native to 1.76 mpp)",
    "virchow_vs_conch_at_1.76": "Encoder contrast (1.76 mpp)",
    "tile64_vs16": "Tile-count contrast (64 minus 16)",
}
METRIC_LABELS = {
    "patient_spearman_rho": "Spearman correlation − null",
    "patient_auroc": "AUROC − null",
    "patient_c_index": "C-index − null",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reuse the frozen Figure 9 validators for both complete saved sources."""
    if len(source_paths) != 2:
        raise ValueError("Supplementary Figure 3 requires grid and contrast CSVs")
    grid = validate_grid(pd.read_csv(Path(source_paths[0])))
    contrasts = validate_contrasts(pd.read_csv(Path(source_paths[1])))
    cell_values = _individual_cell_values(contrasts)
    for row in grid.itertuples(index=False):
        seed_values = [
            cell_values.get(
                _cell_id(row.marker, row.encoder, seed, row.tiles_per_slide, row.target_mpp)
            )
            for seed in range(5)
        ]
        if any(value is None for value in seed_values):
            raise ValueError(
                "Supplementary Figure 3 grid mean cannot reconcile: seed cell is missing"
            )
        reconstructed_mean = float(np.mean(seed_values))
        if not np.isclose(reconstructed_mean, float(row.mean), rtol=0, atol=1e-12):
            raise ValueError(
                "Supplementary Figure 3 grid mean does not reconcile with saved seed cells"
            )
    return grid, contrasts


def _cell_id(marker: str, encoder: str, seed: int, tile: int, mpp: float) -> str:
    return f"{marker}__{encoder.lower()}__s{seed}__t{tile}__mpp{mpp:.2f}"


def _individual_cell_values(contrasts: pd.DataFrame) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in contrasts.itertuples(index=False):
        for cell_id, value in ((row.cell_id_a, row.patient_metric_a),
                               (row.cell_id_b, row.patient_metric_b)):
            value = float(value)
            if cell_id in values and not np.isclose(values[cell_id], value, rtol=0, atol=1e-12):
                raise ValueError("Supplementary Figure 3 repeated cell values disagree")
            values[cell_id] = value
    if len(values) != 360:
        raise ValueError(
            f"Supplementary Figure 3 requires all 360 individual cells, found {len(values)}"
        )
    return values


def _heatmap_page(marker: str, grid: pd.DataFrame):
    metric, null = MARKER_MAPPING[marker]
    matrices: dict[str, np.ndarray] = {}
    crossings: dict[str, np.ndarray] = {}
    for encoder in ENCODERS:
        columns = [(NATIVE_MPP[encoder], tile) for tile in TILES]
        columns += [(SHARED_MPP, tile) for tile in TILES]
        matrix = np.empty((1, 6), dtype=float)
        crossing_counts = np.empty((1, 6), dtype=int)
        rows = grid[(grid["marker"] == marker) & (grid["encoder"] == encoder)].set_index(
            ["target_mpp", "tiles_per_slide"]
        )
        for column_index, (mpp, tile) in enumerate(columns):
            try:
                row = rows.loc[(mpp, tile)]
            except KeyError as error:
                raise ValueError(
                    f"Supplementary Figure 3 grid is missing {marker}/{encoder}/{tile}/{mpp}"
                ) from error
            matrix[0, column_index] = float(row["mean"]) - null
            crossing_counts[0, column_index] = int(row["n_chance_or_worse"])
        matrices[encoder] = matrix
        crossings[encoder] = crossing_counts
    limit = max(abs(float(matrix.min())) for matrix in matrices.values())
    limit = max(limit, max(abs(float(matrix.max())) for matrix in matrices.values()), 1e-6)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    cmap = LinearSegmentedColormap.from_list(
        "stability_delta", (COLORBLIND_SAFE_PALETTE[1], "#F9FAFB", COLORBLIND_SAFE_PALETTE[0])
    )
    fig, axes = plt.subplots(
        2, 1, figsize=figure_size(FIGURE_WIDTH_MM, 0.42), constrained_layout=True,
    )
    fig.add_artist(
        Rectangle(
            (0.49, 0.99), 0.02, 0.01, transform=fig.transFigure,
            facecolor="white", edgecolor="none", zorder=-10,
        )
    )
    image = None
    for panel_index, (axis, encoder) in enumerate(zip(axes, ENCODERS)):
        matrix = matrices[encoder]
        image = axis.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")
        for column in range(6):
                normalized = norm(matrix[0, column])
                color = "white" if abs(normalized - 0.5) > 0.30 else "#111827"
                axis.text(
                    column, 0,
                    f"{matrix[0, column]:+.2f}\n{crossings[encoder][0, column]}/5≤null",
                    ha="center", va="center", color=color, fontsize=8.0,
                )
        native = NATIVE_MPP[encoder]
        labels = [f"{tile}\n{native:g}" for tile in TILES]
        labels += [f"{tile}\n{SHARED_MPP:g}" for tile in TILES]
        axis.set_xticks(range(6), labels)
        axis.set_yticks([0], ["5-seed mean"])
        axis.set_xlabel("Tiles per slide / target mpp")
        axis.set_title(
            f"{chr(ord('a') + panel_index)}   {encoder}", loc="left", fontweight="bold"
        )
        axis.tick_params(length=0)
    colorbar = fig.colorbar(image, ax=axes, shrink=0.78, pad=0.025)
    colorbar.set_label(METRIC_LABELS[metric])
    fig.suptitle(MARKER_LABELS[marker], fontweight="bold", fontsize=PANEL_FONT_PT)
    return fig


def _contrast_page(contrast_name: str, contrasts: pd.DataFrame):
    fig = plt.figure(figsize=figure_size(FIGURE_WIDTH_MM, 1.02), constrained_layout=True)
    grid = fig.add_gridspec(4, 2, height_ratios=(1.0, 1.0, 1.0, 0.13))
    axes = np.array([
        [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])],
        [fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])],
        [fig.add_subplot(grid[2, 0]), fig.add_subplot(grid[2, 1])],
    ])
    for panel_index, (axis, marker) in enumerate(zip(axes.flat, MARKERS)):
        rows = contrasts[(contrasts.contrast == contrast_name) &
                         (contrasts.marker == marker)].sort_values("pair_id")
        if rows.empty:
            raise ValueError(
                f"Supplementary Figure 3 has no {contrast_name} rows for {marker}"
            )
        y = np.arange(len(rows))
        colors = np.where(rows["null_crossing"].astype(bool),
                          COLORBLIND_SAFE_PALETTE[1], COLORBLIND_SAFE_PALETTE[0])
        axis.scatter(rows["delta_b_minus_a"], y, c=colors, s=16, alpha=0.82,
                     edgecolor="none")
        axis.axvline(0.0, color="#6B7280", linestyle="--")
        axis.set_yticks([])
        axis.set_xlabel("Paired metric difference")
        panel_letter = chr(ord("a") + panel_index)
        axis.set_title(f"{panel_letter}   {MARKER_LABELS[marker]}  (n={len(rows)})",
                       loc="left", fontweight="bold", fontsize=PANEL_FONT_PT)
        axis.grid(axis="x", color="#E5E7EB")
        axis.spines[["top", "right", "left"]].set_visible(False)
    legend_axis = fig.add_subplot(grid[3, :])
    legend_axis.axis("off")
    handles = (
        Line2D([], [], marker="o", linestyle="none", color=COLORBLIND_SAFE_PALETTE[0],
               label="Endpoints remain on the same side of null"),
        Line2D([], [], marker="o", linestyle="none", color=COLORBLIND_SAFE_PALETTE[1],
               label="Endpoints cross the marker-specific null"),
    )
    legend_axis.legend(handles=handles, frameon=False, loc="center", ncol=2)
    fig.suptitle(CONTRAST_TITLES[contrast_name], fontweight="bold", fontsize=PANEL_FONT_PT)
    return fig


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render six complete cell-grid pages and three full contrast pages."""
    grid, contrasts = load_sources(source_paths)
    apply_journal_style()
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output_pdf.stem}-", suffix=".pdf", dir=output_pdf.parent, delete=False
        ) as handle:
            staged = Path(handle.name)
        with PdfPages(staged, metadata=PDF_METADATA) as pages:
            for marker in MARKERS:
                figure = _heatmap_page(marker, grid)
                pages.savefig(
                    figure, bbox_inches="tight", pad_inches=0,
                    facecolor="white", edgecolor="white",
                )
                plt.close(figure)
            for contrast_name in CONTRASTS:
                figure = _contrast_page(contrast_name, contrasts)
                pages.savefig(
                    figure, bbox_inches="tight", pad_inches=0,
                    facecolor="white", edgecolor="white",
                )
                plt.close(figure)
        if staged.stat().st_size == 0:
            raise RuntimeError("Supplementary Figure 3 renderer produced an empty PDF")
        os.replace(staged, output_pdf)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
        plt.close("all")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--contrasts", type=Path, default=DEFAULT_CONTRASTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.grid, args.contrasts), args.output)


if __name__ == "__main__":
    main()
