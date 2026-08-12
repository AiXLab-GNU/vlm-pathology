"""Shared final-size styling for Scientific Reports vector figures."""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from cycler import cycler


MIN_FONT_PT = 8.0
AXIS_FONT_PT = 9.0
PANEL_FONT_PT = 11.0
MIN_LINE_PT = 1.0
SINGLE_COLUMN_MM = 89
DOUBLE_COLUMN_MM = 180

COLORBLIND_SAFE_PALETTE = ("#0072B2", "#D55E00", "#009E73", "#6B7280")

_PDF_METADATA = {
    "Creator": "vlm-pathology",
    "Producer": "vlm-pathology",
    "CreationDate": None,
    "ModDate": None,
}


def apply_journal_style() -> None:
    """Apply the shared final-size Scientific Reports figure style."""
    mpl.rcParams.update(
        {
            "font.family": ["DejaVu Sans"],
            "font.size": MIN_FONT_PT,
            "axes.labelsize": AXIS_FONT_PT,
            "axes.titlesize": PANEL_FONT_PT,
            "xtick.labelsize": AXIS_FONT_PT,
            "ytick.labelsize": AXIS_FONT_PT,
            "legend.fontsize": AXIS_FONT_PT,
            "axes.linewidth": MIN_LINE_PT,
            "lines.linewidth": MIN_LINE_PT,
            "patch.linewidth": MIN_LINE_PT,
            "grid.linewidth": MIN_LINE_PT,
            "xtick.major.width": MIN_LINE_PT,
            "xtick.minor.width": MIN_LINE_PT,
            "ytick.major.width": MIN_LINE_PT,
            "ytick.minor.width": MIN_LINE_PT,
            "xtick.major.size": 3.5,
            "xtick.minor.size": 2.0,
            "ytick.major.size": 3.5,
            "ytick.minor.size": 2.0,
            "axes.prop_cycle": cycler(color=COLORBLIND_SAFE_PALETTE),
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
            "savefig.transparent": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def figure_size(width_mm: int, aspect: float) -> tuple[float, float]:
    """Return a figure size in inches for a final-width millimetre target."""
    width_inches = width_mm / 25.4
    return width_inches, width_inches * aspect


def save_vector_figure(fig: mpl.figure.Figure, output: Path) -> None:
    """Save and close a deterministic, tightly bounded vector PDF figure."""
    try:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            output,
            format="pdf",
            bbox_inches="tight",
            pad_inches=0,
            facecolor="white",
            edgecolor="white",
            metadata=_PDF_METADATA,
        )
    finally:
        plt.close(fig)
