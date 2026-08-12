"""Render the frozen primary-configuration CONCH/Virchow snapshot for seven markers.

Values and their analysis units come from the saved, provenance-bearing source table
``paper/figure_data/fig3_primary_snapshot.csv``.  This is distinct from the correlated Gate A
grid shown separately in Figure 9.  Metrics differ across markers, so only within-marker encoder
pairs are comparable.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SOURCE = PROJECT_ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig3_primary_snapshot.csv"
EXPECTED_COLUMNS = [
    "marker_id",
    "display_order",
    "marker_label",
    "cohort",
    "metric",
    "analysis_unit",
    "conch_value",
    "virchow_value",
    "note",
    "upstream_source",
    "upstream_fields",
]
EXPECTED_CORE = {
    1: (1, "Grade", "NADT", "ρ", "patient", 0.4783626326797877, 0.5133276979921874, ""),
    2: (2, "Phenotype", "NADT", "ρ", "patient", 0.8046203170759654, 0.7563565046659657, ""),
    3: (3, "ERG→Grade", "NADT", "ρ", "patient", 0.5244160374868407, 0.6643009193406669, ""),
    4: (4, "PTEN loss", "TCGA-PRAD", "AUROC", "slide", 0.6174008207934337, 0.6084815321477428, ""),
    5: (
        5,
        "SPOP mut.",
        "TCGA-PRAD",
        "AUROC",
        "slide",
        0.5083122895622896,
        0.4240319865319865,
        "Primary unsupported\\nNeither robust positive nor null",
    ),
    6: (6, "AR activity", "TCGA-PRAD", "ρ", "slide", 0.1827419470405023, 0.2300511493594673, ""),
    7: (
        7,
        "Recurrence",
        "TCGA-PRAD",
        "C-index",
        "patient",
        0.673,
        0.533,
        "Endpoint/encoder/scale-limited\\nOfficial PFI complete; interval includes 0.5",
    ),
}

CONCH_COLOR = "#2a78d6"
VIRCHOW_COLOR = "#eb6834"
MUTED = "#898781"
GRID = "#e1e0d9"
CIRCLED = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 6: "⑥", 7: "⑦"}


def load_snapshot(path: Path = SOURCE) -> pd.DataFrame:
    """Load the frozen source table and reject any schema, key, unit, or value drift."""
    frame = pd.read_csv(path, keep_default_na=False)
    if frame.columns.tolist() != EXPECTED_COLUMNS:
        raise ValueError(f"Fig3 source schema mismatch: {frame.columns.tolist()}")
    if len(frame) != 7:
        raise ValueError(f"Fig3 source must contain exactly 7 rows, got {len(frame)}")

    for column in ("marker_id", "display_order"):
        numeric = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(numeric).all() or not np.equal(numeric, np.floor(numeric)).all():
            raise ValueError(f"Fig3 {column} must contain finite integers")
        frame[column] = numeric.astype(int)
    for column in ("conch_value", "virchow_value"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[column]).all():
            raise ValueError(f"Fig3 {column} must contain finite values")

    if frame["marker_id"].tolist() != list(range(1, 8)):
        raise ValueError("Fig3 marker_id/order must be exactly 1..7")
    if frame["display_order"].tolist() != list(range(1, 8)):
        raise ValueError("Fig3 display_order must be exactly 1..7")

    core_columns = [
        "display_order",
        "marker_label",
        "cohort",
        "metric",
        "analysis_unit",
        "conch_value",
        "virchow_value",
        "note",
    ]
    for row in frame.itertuples(index=False):
        actual = tuple(getattr(row, column) for column in core_columns)
        if actual != EXPECTED_CORE[row.marker_id]:
            raise ValueError(
                f"Fig3 frozen contract mismatch for marker {row.marker_id}: {actual!r}"
            )
        sources = row.upstream_source.split(";")
        if not sources or any(not source.strip() for source in sources):
            raise ValueError(f"Fig3 marker {row.marker_id} has invalid upstream_source")
        missing = [source for source in sources if not (PROJECT_ROOT / source).is_file()]
        if missing:
            raise ValueError(f"Fig3 marker {row.marker_id} upstream files missing: {missing}")
        if not row.upstream_fields.strip():
            raise ValueError(f"Fig3 marker {row.marker_id} has blank upstream_fields")
    return frame


def render_snapshot(frame: pd.DataFrame, output_pdf: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    x = np.arange(len(frame))
    width = 0.34
    conch_values = frame["conch_value"].tolist()
    virchow_values = frame["virchow_value"].tolist()
    ax.bar(x - width / 2, conch_values, width=width, color=CONCH_COLOR, label="CONCH", zorder=3)
    ax.bar(x + width / 2, virchow_values, width=width, color=VIRCHOW_COLOR, label="Virchow", zorder=3)

    for xi, value in zip(x - width / 2, conch_values):
        ax.text(xi, value + 0.015, f"{value:.3f}", ha="center", va="bottom", fontsize=7.6, color="#0b0b0b")
    for xi, value in zip(x + width / 2, virchow_values):
        ax.text(xi, value + 0.015, f"{value:.3f}", ha="center", va="bottom", fontsize=7.6, color="#0b0b0b")

    for xi, row in zip(x, frame.itertuples(index=False)):
        if row.note:
            ax.text(
                xi,
                -0.09,
                row.note.replace("\\n", "\n"),
                ha="center",
                va="top",
                fontsize=7.0,
                color=MUTED,
                style="italic",
            )

    labels = [
        f"{CIRCLED[row.marker_id]} {row.marker_label}\n"
        f"({row.cohort},\n{row.analysis_unit} {row.metric})"
        for row in frame.itertuples(index=False)
    ]
    ax.axhline(0, color="#c3c2b7", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.3, color="#52514e")
    ax.set_ylabel("Reported value (metric varies by marker — see x-axis)", fontsize=9, color="#52514e")
    ax.set_ylim(-0.22, 0.95)
    ax.legend(loc="upper right", frameon=False, fontsize=9.5, labelcolor="#0b0b0b")
    ax.set_title(
        "Frozen primary-configuration cross-encoder snapshot",
        fontsize=12,
        color="#0b0b0b",
        loc="left",
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0,
        1.01,
        "Distinct from the correlated Gate A grid; metric varies by marker",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color=MUTED,
    )
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e", labelsize=8)

    plt.tight_layout()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_pdf, facecolor=fig.get_facecolor(),
                metadata={"Creator": "fig3_conch_vs_virchow.py", "CreationDate": None,
                          "ModDate": None})
    plt.savefig(output_pdf.with_suffix(".png"), facecolor=fig.get_facecolor(),
                metadata={"Software": "fig3_conch_vs_virchow.py"})
    plt.close(fig)


def main() -> None:
    output = Path(__file__).with_suffix(".pdf")
    render_snapshot(load_snapshot(), output)
    print(f"saved {output}")


if __name__ == "__main__":
    main()
