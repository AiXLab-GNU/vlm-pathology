"""Render the submission evidence-state map from its frozen CSV source."""
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
DEFAULT_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig1_qualification_map.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM

REQUIRED_COLUMNS = {
    "semantic_key", "claim_id", "display_order", "claim_label", "marker", "hierarchy",
    "evidence_state", "qualification_decision", "limitation", "primary_estimate",
    "missingness_status", "missingness_detail", "source_path", "source_field",
}
EXPECTED_KEYS = {f"C{index:02d}" for index in range(1, 9)}
EXPECTED_STATES = {
    "descriptive_framework", "transportable", "context_sensitive",
    "unsupported_in_frozen_design",
}
EXPECTED_HIERARCHIES = {"primary", "exploratory", "supporting"}
EXPECTED_HIERARCHY_BY_KEY = {
    "C01": "primary",
    "C02": "primary",
    "C03": "primary",
    "C04": "primary",
    "C05": "primary",
    "C06": "exploratory",
    "C07": "exploratory",
    "C08": "supporting",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Load one exact qualification-map source and reject incomplete semantics."""
    if len(source_paths) != 1:
        raise ValueError("Figure 1 requires exactly one source CSV")
    frame = pd.read_csv(Path(source_paths[0]))
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Figure 1 missing required columns: {sorted(missing)}")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].duplicated().any():
        raise ValueError("Figure 1 semantic_key values must be present and unique")
    if set(frame["semantic_key"]) != EXPECTED_KEYS:
        raise ValueError("Figure 1 requires the complete C01--C08 claim groups")
    if set(frame["evidence_state"]) != EXPECTED_STATES:
        raise ValueError("Figure 1 evidence-state groups do not reconcile")
    if set(frame["hierarchy"]) != EXPECTED_HIERARCHIES:
        raise ValueError("Figure 1 evidence hierarchy groups do not reconcile")
    hierarchy_by_key = frame.set_index("semantic_key")["hierarchy"].to_dict()
    if hierarchy_by_key != EXPECTED_HIERARCHY_BY_KEY:
        raise ValueError("Figure 1 claim-specific evidence hierarchy does not reconcile")
    if not frame["claim_id"].eq(frame["semantic_key"]).all():
        raise ValueError("Figure 1 claim_id must match its semantic claim key")
    if set(frame["missingness_status"]) != {"not_applicable"}:
        raise ValueError("Figure 1 framework missingness must be explicitly not_applicable")
    for column in ("display_order", "primary_estimate"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError(f"Figure 1 {column} must be finite")
    if set(pd.to_numeric(frame["display_order"]).astype(int)) != set(range(1, 9)):
        raise ValueError("Figure 1 display_order must contain 1--8 exactly")
    for column in ("claim_id", "marker", "hierarchy", "qualification_decision",
                   "missingness_detail", "source_path", "source_field"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Figure 1 {column} must be explicitly populated")
    return (frame.sort_values("display_order").reset_index(drop=True),)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render a compact state matrix at double-column width."""
    (frame,) = load_sources(source_paths)
    apply_journal_style()
    selected = frame[
        frame["semantic_key"].isin(("C02", "C03", "C04", "C05", "C06", "C07"))
    ]
    labels = {
        "C02": "Grade and phenotype",
        "C03": "PTEN loss",
        "C04": "SPOP mutation",
        "C05": "AR activity",
        "C06": "Post-hoc recurrence transfer",
        "C07": "Post-hoc recurrence increment",
    }
    state_order = ("transportable", "context_sensitive", "unsupported_in_frozen_design")
    state_labels = ("Transportable", "Context-\nsensitive", "Unsupported\nin frozen design")
    state_colors = {
        "transportable": COLORBLIND_SAFE_PALETTE[2],
        "context_sensitive": COLORBLIND_SAFE_PALETTE[1],
        "unsupported_in_frozen_design": COLORBLIND_SAFE_PALETTE[3],
    }

    fig, (axis, scope) = plt.subplots(
        1, 2, figsize=figure_size(FIGURE_WIDTH_MM, 0.48),
        gridspec_kw={"width_ratios": (2.35, 1.0)}, constrained_layout=True,
    )
    y = np.arange(len(selected))
    axis.set_xlim(-0.5, 2.5)
    axis.set_ylim(len(selected) - 0.5, -0.5)
    for row_index, row in enumerate(selected.itertuples(index=False)):
        state_index = state_order.index(row.evidence_state)
        axis.scatter(state_index, row_index, s=165, color=state_colors[row.evidence_state],
                     edgecolor="white", linewidth=1.2, zorder=3)
    for x in np.arange(-0.5, 3.0, 1.0):
        axis.axvline(x, color="#D1D5DB", linewidth=1.0, zorder=0)
    for yy in np.arange(-0.5, len(selected) + 0.5, 1.0):
        axis.axhline(yy, color="#E5E7EB", linewidth=1.0, zorder=0)
    axis.set_xticks(range(3), state_labels)
    axis.tick_params(axis="x", labelsize=8)
    axis.set_yticks(y, [labels[key] for key in selected["semantic_key"]])
    axis.tick_params(length=0)
    axis.spines[:].set_visible(False)
    axis.set_title("a   Evidence state", loc="left", fontweight="bold")

    hierarchy_counts = selected["hierarchy"].value_counts().reindex(
        ["primary", "exploratory"], fill_value=0
    )
    scope.barh([0, 1], hierarchy_counts.to_numpy(),
               color=(COLORBLIND_SAFE_PALETTE[0], COLORBLIND_SAFE_PALETTE[3]))
    scope.set_yticks([0, 1], ["Primary", "Exploratory"])
    scope.set_xlabel("Decisions")
    scope.set_xlim(0, max(4, int(hierarchy_counts.max()) + 1))
    scope.set_xticks(np.arange(0, max(4, int(hierarchy_counts.max()) + 1) + 0.1, 1))
    scope.invert_yaxis()
    scope.grid(axis="x", color="#E5E7EB")
    scope.spines[["top", "right", "left"]].set_visible(False)
    scope.tick_params(axis="y", length=0)
    scope.set_title("b   Evidence\nhierarchy", loc="left", fontweight="bold")
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.source,), args.output)


if __name__ == "__main__":
    main()
