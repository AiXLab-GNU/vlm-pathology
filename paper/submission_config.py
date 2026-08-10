"""Single source of truth for the Scientific Reports submission package."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from paper.figures.style import DOUBLE_COLUMN_MM


@dataclass(frozen=True)
class FigureSpec:
    figure_id: str
    label: str
    sources: Sequence[str]
    script: str
    output: str
    manuscript: str
    width_mm: int


@dataclass(frozen=True)
class TableSpec:
    table_id: str
    label: str
    sources: Sequence[str]
    script: str
    output: str
    manuscript: str


ACTIVE_MAIN_TEX = (
    "paper/main.tex",
    "paper/sections/abstract.tex",
    "paper/sections/introduction.tex",
    "paper/sections/results.tex",
    "paper/sections/discussion.tex",
    "paper/sections/methods.tex",
    "paper/sections/declarations.tex",
    "paper/sections/bibliography.tex",
    "paper/sections/figure_legends.tex",
)

ACTIVE_SUPPLEMENT_TEX = (
    "paper/supplement_main.tex",
    "paper/sections/supplementary_information.tex",
)

MAIN_FIGURES = (
    FigureSpec(
        "F1", "fig:qualification-framework",
        ("paper/figure_data/fig1_qualification_map.csv",),
        "paper/figures/fig1_qualification_map.py",
        "paper/figures/fig1_qualification_map.pdf", "paper/sections/results.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "F2", "fig:transportable-signals",
        ("paper/figure_data/fig2_transportable_signals.csv",),
        "paper/figures/fig2_transportable_signals.py",
        "paper/figures/fig2_transportable_signals.pdf", "paper/sections/results.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "F3", "fig:molecular-qualification",
        ("paper/figure_data/fig3_molecular_qualification.csv",),
        "paper/figures/fig3_molecular_qualification.py",
        "paper/figures/fig3_molecular_qualification.pdf", "paper/sections/results.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "F4", "fig:confounder-site-audit",
        ("paper/figure_data/fig4_confounder_site_audit.csv",),
        "paper/figures/fig4_confounder_site_audit.py",
        "paper/figures/fig4_confounder_site_audit.pdf", "paper/sections/results.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "F5", "fig:marker7-transfer",
        ("paper/figure_data/fig5_marker7_transfer.csv",),
        "paper/figures/fig5_marker7_transfer.py",
        "paper/figures/fig5_marker7_transfer.pdf", "paper/sections/results.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "F6", "fig:stability-overview",
        ("paper/figure_data/fig6_stability_overview.csv",),
        "paper/figures/fig6_stability_overview.py",
        "paper/figures/fig6_stability_overview.pdf", "paper/sections/results.tex", DOUBLE_COLUMN_MM,
    ),
)

SUPPLEMENT_FIGURES = (
    FigureSpec(
        "SF1", "fig:supp-discrimination-details",
        ("paper/figure_data/fig2_transportable_signals.csv",),
        "paper/figures/sfig1_detailed_roc.py",
        "paper/figures/sfig1_detailed_roc.pdf",
        "paper/sections/supplementary_information.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "SF2", "fig:supp-marker7-survival",
        (
            "models/marker7_td_auc_curve.csv",
            "models/marker7_calibration_3y_5y.csv",
            "paper/figure_data/fig5_marker7_transfer.csv",
        ),
        "paper/figures/sfig2_marker7_survival.py",
        "paper/figures/sfig2_marker7_survival.pdf",
        "paper/sections/supplementary_information.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "SF3", "fig:supp-stability-heatmaps",
        (
            "paper/figure_data/fig9_stability_grid.csv",
            "paper/figure_data/fig9_stability_contrasts.csv",
        ),
        "paper/figures/sfig3_stability_heatmaps.py",
        "paper/figures/sfig3_stability_heatmaps.pdf",
        "paper/sections/supplementary_information.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "SF4", "fig:supp-evidence-axis-matrix",
        (
            "paper/figure_data/evidence_axis_matrix.csv",
            "paper/claim_evidence_matrix.csv",
        ),
        "paper/figures/sfig4_evidence_axis_matrix.py",
        "paper/figures/sfig4_evidence_axis_matrix.pdf",
        "paper/sections/supplementary_information.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "SF5", "fig:supp-stability-distributions",
        ("paper/figure_data/fig9_stability_contrasts.csv",),
        "paper/figures/sfig5_stability_distributions.py",
        "paper/figures/sfig5_stability_distributions.pdf",
        "paper/sections/supplementary_information.tex", DOUBLE_COLUMN_MM,
    ),
    FigureSpec(
        "SF6", "fig:supp-endpoint-concordance",
        ("models/pfi_endpoint_concordance.csv",),
        "paper/figures/sfig6_endpoint_concordance.py",
        "paper/figures/sfig6_endpoint_concordance.pdf",
        "paper/sections/supplementary_information.tex", DOUBLE_COLUMN_MM,
    ),
)

TABLES = (
    TableSpec(
        "T1", "tab:qualification-summary",
        ("paper/claim_evidence_matrix.csv",),
        "paper/generate_submission_tables.py",
        "paper/generated/table1_qualification_summary.tex", "paper/sections/results.tex",
    ),
    TableSpec(
        "S1", "tab:supp-endpoint-hierarchy",
        ("paper/endpoint_hierarchy.csv",),
        "paper/generate_submission_tables.py",
        "paper/generated/stable1_endpoint_hierarchy.tex",
        "paper/sections/supplementary_information.tex",
    ),
    TableSpec(
        "S2", "tab:supp-family",
        ("models/revision_global_fdr_summary.csv",),
        "paper/generate_submission_tables.py",
        "paper/generated/stable2_multiplicity_family.tex",
        "paper/sections/supplementary_information.tex",
    ),
    TableSpec(
        "S3", "tab:supp-stability-summary",
        ("models/stability_summary.csv",),
        "paper/generate_submission_tables.py",
        "paper/generated/stable3_stability_summary.tex",
        "paper/sections/supplementary_information.tex",
    ),
    TableSpec(
        "S4", "tab:supp-evidence-axis-audit",
        (
            "paper/figure_data/evidence_axis_matrix.csv",
            "paper/claim_evidence_matrix.csv",
        ),
        "paper/generate_submission_tables.py",
        "paper/generated/stable4_evidence_axis_audit.tex",
        "paper/sections/supplementary_information.tex",
    ),
    TableSpec(
        "S5", "tab:supp-analysis-frame-inventory",
        (
            "paper/figure_data/fig2_transportable_signals.csv",
            "paper/figure_data/fig3_molecular_qualification.csv",
            "paper/figure_data/fig4_confounder_site_audit.csv",
            "paper/figure_data/fig5_marker7_transfer.csv",
            "paper/figure_data/fig9_stability_grid.csv",
            "paper/figure_data/fig9_stability_contrasts.csv",
        ),
        "paper/generate_submission_tables.py",
        "paper/generated/stable5_analysis_frame_inventory.tex",
        "paper/sections/supplementary_information.tex",
    ),
    TableSpec(
        "S6", "tab:supp-stability-contrast-summary",
        ("paper/figure_data/fig9_stability_contrasts.csv",),
        "paper/generate_submission_tables.py",
        "paper/generated/stable6_stability_contrast_summary.tex",
        "paper/sections/supplementary_information.tex",
    ),
    TableSpec(
        "S7", "tab:supp-endpoint-concordance",
        ("models/pfi_endpoint_concordance.csv",),
        "paper/generate_submission_tables.py",
        "paper/generated/stable7_endpoint_concordance.tex",
        "paper/sections/supplementary_information.tex",
    ),
)
