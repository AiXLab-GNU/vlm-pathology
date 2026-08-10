"""Render endpoint concordance metrics and event-pair composition."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd

from paper.figures.style import (
    COLORBLIND_SAFE_PALETTE,
    DOUBLE_COLUMN_MM,
    apply_journal_style,
    figure_size,
    save_vector_figure,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "models/pfi_endpoint_concordance.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
ENDPOINTS = (
    "reconstructed_gdc_disease_response",
    "cbioportal_tcga_cdr_pfs",
    "cbioportal_tcga_cdr_dfs",
    "gdc_recurrence_only_after_tumor_free",
)
ENDPOINT_LABELS = {
    "reconstructed_gdc_disease_response": "Reconstructed",
    "cbioportal_tcga_cdr_pfs": "TCGA-CDR PFS",
    "cbioportal_tcga_cdr_dfs": "TCGA-CDR DFS",
    "gdc_recurrence_only_after_tumor_free": "Strict recurrence",
}
REQUIRED_COLUMNS = {
    "reference_endpoint_id", "comparison_endpoint_id", "n_reference_evaluable",
    "n_comparison_evaluable", "n_common_evaluable", "n_reference_events_common",
    "n_comparison_events_common", "n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0",
    "n_ref1_cmp1", "event_agreement", "cohen_kappa", "n_time_pairs",
    "time_spearman_rho", "time_spearman_p", "time_comparison_unit", "status",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    if len(source_paths) != 1:
        raise ValueError("Supplementary Figure 6 requires one endpoint-concordance CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    if set(frame.columns) != REQUIRED_COLUMNS:
        raise ValueError("Supplementary Figure 6 endpoint-concordance schema mismatch")
    if len(frame) != 4 or frame["comparison_endpoint_id"].duplicated().any():
        raise ValueError("Supplementary Figure 6 requires four unique endpoint comparisons")
    if set(frame["comparison_endpoint_id"].astype(str)) != set(ENDPOINTS):
        raise ValueError("Supplementary Figure 6 endpoint comparison set is incomplete")
    if not frame["reference_endpoint_id"].eq("official_tcga_cdr_pfi").all():
        raise ValueError("Supplementary Figure 6 reference endpoint must be Official PFI")
    if not frame["status"].eq("complete").all() or not frame["time_comparison_unit"].eq("years").all():
        raise ValueError("Supplementary Figure 6 requires complete year-based comparisons")
    count_columns = [
        "n_common_evaluable", "n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0", "n_ref1_cmp1",
    ]
    counts = frame[count_columns].apply(pd.to_numeric, errors="coerce")
    if counts.isna().any().any() or (counts < 0).any().any():
        raise ValueError("Supplementary Figure 6 contains invalid event-pair counts")
    pair_total = counts[["n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0", "n_ref1_cmp1"]].sum(axis=1)
    if not pair_total.eq(counts["n_common_evaluable"]).all():
        raise ValueError("Supplementary Figure 6 event-pair counts do not reconcile")
    recomputed = (counts["n_ref0_cmp0"] + counts["n_ref1_cmp1"]) / counts["n_common_evaluable"]
    if not np.allclose(recomputed, pd.to_numeric(frame["event_agreement"]), rtol=0, atol=1e-12):
        raise ValueError("Supplementary Figure 6 event agreement does not reconcile")
    metrics = frame[["event_agreement", "cohen_kappa", "time_spearman_rho"]].apply(
        pd.to_numeric, errors="coerce"
    )
    if not np.isfinite(metrics.to_numpy()).all() or ((metrics < -1) | (metrics > 1)).any().any():
        raise ValueError("Supplementary Figure 6 contains an invalid concordance metric")
    order = pd.Categorical(frame["comparison_endpoint_id"], ENDPOINTS, ordered=True)
    return (frame.assign(_order=order).sort_values("_order").drop(columns="_order").reset_index(drop=True),)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    figure, (heat_axis, stack_axis) = plt.subplots(
        1, 2, figsize=figure_size(155, 0.55), constrained_layout=True,
        gridspec_kw={"width_ratios": (1.1, 1.15)},
    )
    values = frame[["event_agreement", "cohen_kappa", "time_spearman_rho"]].to_numpy(float)
    image = heat_axis.imshow(values, cmap="Blues", norm=Normalize(vmin=0, vmax=1), aspect="auto")
    heat_axis.set_xticks(
        range(3),
        ["Event\nagreement", "Kappa", "Time\ncorrelation"],
    )
    labels = [ENDPOINT_LABELS[value] for value in frame["comparison_endpoint_id"]]
    heat_axis.set_yticks(range(4), labels)
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            color = "white" if values[row, column] >= 0.72 else "#111827"
            heat_axis.text(column, row, f"{values[row, column]:.3f}", ha="center", va="center", color=color)
    heat_axis.set_title("a   Agreement with Official PFI", loc="left", fontweight="bold")
    heat_axis.tick_params(length=0)
    colorbar = figure.colorbar(image, ax=heat_axis, shrink=0.76, pad=0.03)
    colorbar.set_label("Coefficient")

    components = ("n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0", "n_ref1_cmp1")
    component_labels = (
        "Neither event", "Comparison only", "Official PFI only", "Both events",
    )
    colors = ("#D1D5DB", COLORBLIND_SAFE_PALETTE[2], COLORBLIND_SAFE_PALETTE[1], COLORBLIND_SAFE_PALETTE[0])
    left = np.zeros(len(frame))
    for component, label, color in zip(components, component_labels, colors, strict=True):
        counts = frame[component].astype(float).to_numpy()
        fractions = counts / frame["n_common_evaluable"].astype(float).to_numpy()
        bars = stack_axis.barh(range(len(frame)), fractions, left=left, color=color, label=label)
        for row, (bar, count, fraction) in enumerate(zip(bars, counts.astype(int), fractions, strict=True)):
            if fraction >= 0.075:
                stack_axis.text(
                    left[row] + fraction / 2, bar.get_y() + bar.get_height() / 2,
                    str(count), ha="center", va="center",
                    color="white" if color != "#D1D5DB" else "#111827", fontweight="bold",
                )
        left += fractions
    stack_axis.set_yticks(range(4), labels)
    stack_axis.set_xlim(0, 1)
    stack_axis.set_xlabel("Fraction of common evaluable patients")
    stack_axis.set_title("b   Event-pair composition", loc="left", fontweight="bold")
    stack_axis.invert_yaxis()
    stack_axis.spines[["top", "right", "left"]].set_visible(False)
    stack_axis.tick_params(axis="y", length=0)
    stack_axis.grid(axis="x", color="#E5E7EB")
    figure.legend(loc="outside lower center", ncol=2, frameon=False)
    save_vector_figure(figure, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
