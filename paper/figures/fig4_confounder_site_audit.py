"""Render grade-adjusted and site audits from the frozen submission CSV."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paper.figures.style import (
    COLORBLIND_SAFE_PALETTE,
    DOUBLE_COLUMN_MM,
    PANEL_FONT_PT,
    apply_journal_style,
    figure_size,
    save_vector_figure,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "paper/figure_data/fig4_confounder_site_audit.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
SITES = ("CH", "EJ", "G9", "HC", "KK", "YL", "Pooled")
EXPECTED_KEYS = {
    "pten:CONCH:increment", "pten:Virchow:increment",
    "ar:CONCH:increment", "ar:Virchow:increment",
} | {f"ar:site:{site}" for site in SITES}
REQUIRED_COLUMNS = {
    "semantic_key", "target", "audit_type", "site", "encoder", "metric",
    "analysis_unit", "cluster_unit", "interval_type", "n_slides", "n_patients",
    "n_events", "primary_estimate", "ci_low", "ci_high", "null_value",
    "evidence_state", "missingness_status", "missingness_detail", "source_path",
    "source_field",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Load the exact confounder/site audit and fail on any semantic drift."""
    if len(source_paths) != 1:
        raise ValueError("Figure 4 requires exactly one source CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Figure 4 missing required columns: {sorted(missing)}")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].duplicated().any():
        raise ValueError("Figure 4 semantic_key values must be present and unique")
    if set(frame["semantic_key"]) != EXPECTED_KEYS:
        raise ValueError("Figure 4 semantic keys do not match the frozen audit")
    if set(frame["audit_type"]) != {"grade_adjusted_increment", "ar_site_transport"}:
        raise ValueError("Figure 4 requires increment and site-transport audit groups")
    if set(frame["site"]) != set(SITES):
        raise ValueError("Figure 4 site groups do not reconcile")
    if set(frame["encoder"]) != {"CONCH", "Virchow"}:
        raise ValueError("Figure 4 requires both encoder groups")
    for column in ("n_patients", "primary_estimate", "ci_low", "ci_high", "null_value"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError(f"Figure 4 {column} must be finite")
    estimate = pd.to_numeric(frame["primary_estimate"])
    low = pd.to_numeric(frame["ci_low"])
    high = pd.to_numeric(frame["ci_high"])
    if (low > estimate).any() or (high < estimate).any():
        raise ValueError("Figure 4 intervals must contain their estimates")
    site_rows = frame["audit_type"].eq("ar_site_transport")
    slide_counts = pd.to_numeric(frame.loc[site_rows, "n_slides"], errors="coerce")
    if slide_counts.isna().any() or not np.isfinite(slide_counts).all():
        raise ValueError("Figure 4 site slide counts must be finite")
    if frame["n_events"].notna().any():
        raise ValueError("Figure 4 unrecorded/not-applicable event counts must remain missing")
    for column in ("analysis_unit", "cluster_unit", "interval_type", "evidence_state",
                   "missingness_status", "missingness_detail", "source_path", "source_field"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Figure 4 {column} must be explicitly populated")
    return (frame.reset_index(drop=True),)


def _forest(axis, rows: pd.DataFrame, y_labels: list[str], xlabel: str,
            colors: list[str] | None = None) -> None:
    rows = rows.reset_index(drop=True)
    y = np.arange(len(rows))
    colors = colors or [COLORBLIND_SAFE_PALETTE[0]] * len(rows)
    for index, row in rows.iterrows():
        estimate = float(row.primary_estimate)
        axis.errorbar(
            estimate, index,
            xerr=[[estimate - float(row.ci_low)], [float(row.ci_high) - estimate]],
            fmt="o", color=colors[index], markersize=6, capsize=3.5,
        )
    axis.axvline(0.0, color="#6B7280", linestyle="--")
    axis.set_yticks(y, y_labels)
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.set_xlabel(xlabel)
    axis.grid(axis="x", color="#E5E7EB")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render target-specific increments separately from the AR site forest."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    fig = plt.figure(figsize=figure_size(FIGURE_WIDTH_MM, 0.72), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=(0.8, 1.35))
    axis_a = fig.add_subplot(grid[0, 0])
    axis_b = fig.add_subplot(grid[0, 1])
    axis_c = fig.add_subplot(grid[1, :])

    increments = frame[frame.audit_type == "grade_adjusted_increment"]
    pten = increments[increments.target == "PTEN"].sort_values("encoder")
    ar = increments[increments.target == "AR"].sort_values("encoder")
    palette = [COLORBLIND_SAFE_PALETTE[0], COLORBLIND_SAFE_PALETTE[1]]
    _forest(axis_a, pten, pten["encoder"].tolist(), "Held-out AUROC increment", palette)
    axis_a.set_xlim(-0.04, 0.10)
    axis_a.set_title("a   PTEN beyond grade", loc="left", fontweight="bold")

    _forest(axis_b, ar, ar["encoder"].tolist(), "Held-out R² increment", palette)
    axis_b.set_xlim(-0.05, 0.065)
    axis_b.set_xticks([-0.05, 0.0, 0.05])
    axis_b.set_title("b   AR beyond grade", loc="left", fontweight="bold")

    site = frame[frame.audit_type == "ar_site_transport"].set_index("site").loc[list(SITES)]
    labels = []
    for site_name, row in site.iterrows():
        if site_name == "Pooled":
            labels.append(f"Pooled  (n={int(row.n_patients)} patients)")
        else:
            labels.append(
                f"{site_name}  (n={int(row.n_slides)} slides / {int(row.n_patients)} patients)"
            )
    site_colors = [COLORBLIND_SAFE_PALETTE[3]] * 6 + [COLORBLIND_SAFE_PALETTE[2]]
    _forest(axis_c, site, labels, "AR Spearman correlation", site_colors)
    axis_c.set_xlim(-0.62, 0.64)
    axis_c.set_title("c   AR site transport", loc="left", fontweight="bold")
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
