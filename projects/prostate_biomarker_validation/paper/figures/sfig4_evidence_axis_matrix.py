"""Render target-by-axis qualification coverage from the audited evidence matrix."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from projects.prostate_biomarker_validation.paper.figures.style import (
    DOUBLE_COLUMN_MM,
    apply_journal_style,
    figure_size,
    save_vector_figure,
)


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MATRIX = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/evidence_axis_matrix.csv"
DEFAULT_CLAIMS = ROOT / "projects/prostate_biomarker_validation/paper/claim_evidence_matrix.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
TARGETS = (
    "Grade and phenotype",
    "PTEN",
    "SPOP",
    "Androgen-receptor activity",
    "Recurrence",
)
AXES = (
    "Frozen primary",
    "Cross-cohort transport",
    "Clinical increment",
    "Site behavior",
    "Setting stability",
    "Endpoint fidelity",
)
STATES = (
    "supported",
    "context_sensitive",
    "unsupported",
    "unresolved",
    "not_evaluated",
    "not_applicable",
)
STATE_LABELS = {
    "supported": "Supported",
    "context_sensitive": "Conditional",
    "unsupported": "Unsupported",
    "unresolved": "Unresolved",
    "not_evaluated": "Not evaluated",
    "not_applicable": "N/A",
}
STATE_CELL_LABELS = {
    "supported": "S",
    "context_sensitive": "C",
    "unsupported": "U",
    "unresolved": "?",
    "not_evaluated": "--",
    "not_applicable": "N/A",
}
STATE_COLORS = {
    "supported": "#009E73",
    "context_sensitive": "#E69F00",
    "unsupported": "#6B7280",
    "unresolved": "#0072B2",
    "not_evaluated": "#E5E7EB",
    "not_applicable": "#FFFFFF",
}
REQUIRED_COLUMNS = {
    "target_order", "target", "axis_order", "axis", "state",
    "source_claim_ids", "interpretation", "next_evidence",
}


def load_sources(source_paths: Sequence[Path]) -> tuple[pd.DataFrame]:
    """Validate all target-axis cells and their links to C01--C08 claims."""
    if len(source_paths) != 2:
        raise ValueError("Supplementary Figure 4 requires matrix and claim CSV sources")
    matrix = pd.read_csv(Path(source_paths[0]))
    claims = pd.read_csv(Path(source_paths[1]))
    if set(matrix.columns) != REQUIRED_COLUMNS:
        missing = sorted(REQUIRED_COLUMNS - set(matrix.columns))
        extra = sorted(set(matrix.columns) - REQUIRED_COLUMNS)
        raise ValueError(f"evidence-axis matrix schema mismatch; missing={missing}, extra={extra}")
    if "claim_id" not in claims.columns or set(claims["claim_id"].astype(str)) != {
        f"C{index:02d}" for index in range(1, 9)
    }:
        raise ValueError("evidence-axis matrix requires the complete C01--C08 claim source")
    if matrix.astype(str).apply(lambda column: column.str.strip().eq("").any()).any():
        raise ValueError("evidence-axis matrix contains a blank semantic field")
    if matrix.duplicated(["target", "axis"]).any():
        raise ValueError("evidence-axis target/axis cells must be unique")
    expected = {(target, axis) for target in TARGETS for axis in AXES}
    observed = set(zip(matrix["target"], matrix["axis"], strict=False))
    if observed != expected:
        raise ValueError("evidence-axis matrix must contain the complete five-by-six grid")
    if set(matrix["state"]) - set(STATES):
        raise ValueError("evidence-axis matrix contains an unknown evidence state")
    if set(pd.to_numeric(matrix["target_order"])) != set(range(1, 6)):
        raise ValueError("evidence-axis target ordering is incomplete")
    if set(pd.to_numeric(matrix["axis_order"])) != set(range(1, 7)):
        raise ValueError("evidence-axis ordering is incomplete")
    known_claims = set(claims["claim_id"].astype(str))
    for value in matrix["source_claim_ids"].astype(str):
        linked = set(value.split(";"))
        if not linked or not linked.issubset(known_claims):
            raise ValueError(f"unknown source claim link: {value}")
    return (matrix.sort_values(["target_order", "axis_order"]).reset_index(drop=True),)


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render the complete target-by-axis evidence coverage grid."""
    (matrix,) = load_sources(source_paths)
    apply_journal_style()
    state_index = {state: index for index, state in enumerate(STATES)}
    values = np.array([
        [
            state_index[matrix.loc[
                matrix["target"].eq(target) & matrix["axis"].eq(axis), "state"
            ].iloc[0]]
            for axis in AXES
        ]
        for target in TARGETS
    ])
    colors = [STATE_COLORS[state] for state in STATES]
    figure, axis = plt.subplots(
        figsize=figure_size(FIGURE_WIDTH_MM, 0.54), constrained_layout=True
    )
    axis.imshow(
        values, cmap=ListedColormap(colors),
        norm=BoundaryNorm(np.arange(-0.5, len(STATES) + 0.5), len(STATES)),
        aspect="auto",
    )
    axis.set_xticks(
        np.arange(len(AXES)),
        [
            "Frozen\nprimary", "Cross-cohort\ntransport", "Clinical\nincrement",
            "Site\nbehavior", "Setting\nstability", "Endpoint\nfidelity",
        ],
    )
    axis.set_yticks(np.arange(len(TARGETS)), TARGETS)
    axis.tick_params(axis="both", length=0)
    axis.set_xticks(np.arange(-0.5, len(AXES), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(TARGETS), 1), minor=True)
    axis.grid(which="minor", color="#FFFFFF", linewidth=2)
    axis.tick_params(which="minor", bottom=False, left=False)
    for row_index, target in enumerate(TARGETS):
        for column_index, axis_name in enumerate(AXES):
            state = matrix.loc[
                matrix["target"].eq(target) & matrix["axis"].eq(axis_name), "state"
            ].iloc[0]
            text_color = "white" if state in {
                "supported", "context_sensitive", "unsupported", "unresolved"
            } else "#111827"
            axis.text(
                column_index, row_index, STATE_CELL_LABELS[state],
                ha="center", va="center", color=text_color, fontweight="bold",
            )
    axis.set_title(
        "Evidence coverage is target- and axis-specific", loc="left", fontweight="bold"
    )
    legend = [
        Patch(facecolor=STATE_COLORS[state], edgecolor="#D1D5DB", label=STATE_LABELS[state])
        for state in STATES
    ]
    axis.legend(
        handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.22),
        ncol=3, frameon=False,
    )
    save_vector_figure(figure, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.matrix, args.claims), args.output)


if __name__ == "__main__":
    main()
