#!/usr/bin/env python3
"""Verify promoted PBV evidence and build the QFM alignment manuscript bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/qfm-alignment-matplotlib")
os.environ.setdefault("SOURCE_DATE_EPOCH", "1786766400")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


WORKSPACE = Path(__file__).resolve().parent
REPO_ROOT = WORKSPACE.parents[3]
PROVENANCE = WORKSPACE / "provenance"
BUILD_ROOT = WORKSPACE
FIGURES = BUILD_ROOT / "figures"
GENERATED = BUILD_ROOT / "generated"

COLORS = {
    "supported": "#167D6D",
    "transportable": "#167D6D",
    "context_sensitive": "#D99A2B",
    "unsupported": "#C44E52",
    "unsupported_in_frozen_design": "#C44E52",
    "unresolved": "#D99A2B",
    "not_evaluated": "#D9D9D9",
    "not_applicable": "#F4F4F4",
    "not_tested": "#8C8C8C",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify_sources() -> dict[str, Path]:
    sources: dict[str, Path] = {}
    failures: list[str] = []
    for row in read_csv(PROVENANCE / "source_evidence_manifest.csv"):
        path = REPO_ROOT / row["path"]
        sources[row["source_id"]] = path
        if not path.is_file():
            failures.append(f"missing:{row['source_id']}:{path}")
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != int(row["size_bytes"]):
            failures.append(
                f"size:{row['source_id']}:expected={row['size_bytes']}:actual={actual_size}"
            )
        if actual_hash != row["sha256"]:
            failures.append(
                f"sha256:{row['source_id']}:expected={row['sha256']}:actual={actual_hash}"
            )
    if failures:
        raise RuntimeError("Source-evidence verification failed:\n" + "\n".join(failures))
    return sources


def index_rows(rows: Iterable[dict[str, str]], key: str = "semantic_key") -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows}


def index_numeric_source(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Index heterogeneous immutable source tables without rewriting them."""
    if not rows:
        return {}
    columns = set(rows[0])
    if "semantic_key" in columns:
        return index_rows(rows)
    if {"encoder", "contrast_id"}.issubset(columns):
        return {f"{row['encoder']}:{row['contrast_id']}": row for row in rows}
    if "encoder" in columns:
        return {row["encoder"]: row for row in rows}
    if "cohort" in columns:
        return {row["cohort"]: row for row in rows}
    if "provider" in columns:
        return {row["provider"]: row for row in rows}
    raise RuntimeError(f"No numeric source key contract for columns: {sorted(columns)}")


def as_float(value: str) -> float:
    return float(value) if value not in {"", "NA", "nan"} else float("nan")


def interval(ax, y: float, row: dict[str, str], low: str, high: str, color: str) -> None:
    estimate = as_float(row["primary_estimate"])
    lo = as_float(row.get(low, ""))
    hi = as_float(row.get(high, ""))
    if np.isfinite(lo) and np.isfinite(hi):
        ax.errorbar(estimate, y, xerr=[[estimate - lo], [hi - estimate]], fmt="o", color=color, capsize=3)
    else:
        ax.plot(estimate, y, "o", color=color, markerfacecolor="white", markeredgewidth=1.5)


def style_axis(ax, title: str, null: float) -> None:
    ax.axvline(null, color="#777777", linestyle="--", linewidth=0.9)
    ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
    ax.grid(axis="x", color="#E6E6E6", linewidth=0.7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)


def render_alignment_map(sources: dict[str, Path]) -> None:
    rows = read_csv(sources["PBV-EVIDENCE-MATRIX"])
    # The immutable PBV source grouped two morphology targets for its original
    # presentation.  This manuscript makes six target-specific claims, so split
    # that display row without altering the promoted evidence source.
    presentation_rows: list[dict[str, str]] = []
    for row in rows:
        if row["target"] == "Grade and phenotype":
            presentation_rows.extend(
                [{**row, "target": target} for target in ("Grade/ISUP", "Tumor phenotype/content")]
            )
        else:
            target = "AR activity" if row["target"] == "Androgen-receptor activity" else row["target"]
            presentation_rows.append({**row, "target": target})
    rows = presentation_rows
    targets = list(dict.fromkeys(row["target"] for row in rows))
    axes = list(dict.fromkeys(row["axis"] for row in rows)) + ["Functional use"]
    code = {
        "not_applicable": 0,
        "not_evaluated": 1,
        "unresolved": 2,
        "context_sensitive": 3,
        "supported": 4,
        "not_tested": 5,
        "unsupported": 6,
    }
    matrix = np.full((len(targets), len(axes)), code["not_evaluated"], dtype=int)
    labels = np.full((len(targets), len(axes)), "NE", dtype=object)
    label_map = {
        "supported": "S",
        "unresolved": "U",
        "context_sensitive": "C",
        "not_evaluated": "NE",
        "not_applicable": "NA",
        "unsupported": "X",
    }
    for row in rows:
        i = targets.index(row["target"])
        j = axes.index(row["axis"])
        state = row["state"]
        matrix[i, j] = code[state]
        labels[i, j] = label_map[state]
    functional_status = {
        "Grade/ISUP": ("context_sensitive", "EF"),
        "Tumor phenotype/content": ("not_tested", "BL"),
        "PTEN": ("not_tested", "NR"),
        "AR activity": ("not_tested", "NR"),
        "SPOP": ("unsupported", "NQ"),
        "Recurrence": ("not_applicable", "NA"),
    }
    for target, (state, label) in functional_status.items():
        i = targets.index(target)
        matrix[i, -1] = code[state]
        labels[i, -1] = label
    palette = [
        COLORS["not_applicable"],
        COLORS["not_evaluated"],
        COLORS["unresolved"],
        "#E9C46A",
        COLORS["supported"],
        COLORS["not_tested"],
        COLORS["unsupported"],
    ]
    from matplotlib.colors import ListedColormap

    fig, ax = plt.subplots(figsize=(11.0, 4.8))
    ax.imshow(matrix, cmap=ListedColormap(palette), vmin=0, vmax=6, aspect="auto")
    for i in range(len(targets)):
        for j in range(len(axes)):
            color = "white" if matrix[i, j] in {4, 5, 6} else "#222222"
            ax.text(j, i, labels[i, j], ha="center", va="center", fontsize=8, color=color, fontweight="bold")
    ax.set_xticks(range(len(axes)), axes, rotation=32, ha="right", fontsize=8)
    ax.set_yticks(range(len(targets)), targets, fontsize=9)
    ax.set_title("Known-target alignment evidence and scoped functional-use status", loc="left", fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig1_alignment_map.pdf", bbox_inches="tight")
    plt.close(fig)


def render_human_ai_linkage_map(sources: dict[str, Path]) -> None:
    """Render the target-to-representation-to-judgment evidence boundary."""
    transport = index_rows(read_csv(sources["PBV-TRANSPORT"]))
    molecular = index_rows(read_csv(sources["PBV-MOLECULAR"]))
    outcome = index_rows(read_csv(sources["PBV-OUTCOME"]))
    fm6 = index_numeric_source(read_csv(sources["QFM-FM6-SUMMARY"]))
    contrasts = index_numeric_source(read_csv(sources["QFM-FM6-CONTRASTS"]))
    external = index_numeric_source(read_csv(sources["QFM-FM6-LEOPARD-EXTERNAL"]))
    chimera = index_numeric_source(read_csv(sources["QFM-FM6-CHIMERA-EXTERNAL"]))

    rows = [
        {
            "target": "Grade / ISUP\narchitectural severity",
            "feature": (
                "ISUP-predictive embedding direction\n"
                f"CONCH OOF rho = {as_float(fm6['conch']['isup_spearman']):.3f}\n"
                f"Virchow OOF rho = {as_float(fm6['virchow']['isup_spearman']):.3f}"
            ),
            "judgment": (
                "Locked BCR-head sensitivity\n"
                f"CONCH delta C = {as_float(contrasts['conch:full_minus_target_fixed']['estimate_left_minus_right']):.3f}\n"
                f"Virchow delta C = {as_float(contrasts['virchow:full_minus_target_fixed']['estimate_left_minus_right']):.3f}\n"
                f"LEOPARD full C = {as_float(external['conch']['full_c_index']):.3f} / "
                f"{as_float(external['virchow']['full_c_index']):.3f}; neither passed\n"
                f"CHIMERA delta C = {as_float(chimera['conch']['target_delta_use']):.3f} / "
                f"{as_float(chimera['virchow']['target_delta_use']):.3f}; Virchow passed"
            ),
            "target_state": "supported",
            "feature_state": "supported",
            "judgment_state": "context_sensitive",
            "judgment_link": True,
        },
        {
            "target": "Tumor phenotype /\ncontent",
            "feature": (
                "CONCH phenotype-probe score\n"
                f"NADT rho = {as_float(transport['phenotype:nadt']['primary_estimate']):.3f}\n"
                f"PANDA AUROC = {as_float(transport['phenotype_panda:karolinska']['primary_estimate']):.3f} / "
                f"{as_float(transport['phenotype_panda:radboud']['primary_estimate']):.3f}"
            ),
            "judgment": (
                "Currently blocked for BCR-head test\n"
                "same-cohort independent\n"
                "tumor-content truth unavailable"
            ),
            "target_state": "supported",
            "feature_state": "supported",
            "judgment_state": "not_tested",
            "judgment_link": False,
        },
        {
            "target": "PTEN loss\nmolecular axis",
            "feature": (
                "CONCH PTEN-probe score\n"
                f"primary AUROC = {as_float(molecular['pten:frozen_primary']['primary_estimate']):.3f}\n"
                "beyond-grade unresolved"
            ),
            "judgment": (
                "Feasible follow-up; not run\n"
                "needs overlap, event-power,\n"
                "fold and erasure protocol"
            ),
            "target_state": "context_sensitive",
            "feature_state": "context_sensitive",
            "judgment_state": "not_tested",
            "judgment_link": False,
        },
        {
            "target": "AR activity\nmolecular axis",
            "feature": (
                "CONCH AR-probe score\n"
                f"primary rho = {as_float(molecular['ar:frozen_primary']['primary_estimate']):.3f}\n"
                "beyond-grade / site unresolved"
            ),
            "judgment": (
                "Feasible follow-up; not run\n"
                "needs overlap, event-power,\n"
                "fold and erasure protocol"
            ),
            "target_state": "context_sensitive",
            "feature_state": "context_sensitive",
            "judgment_state": "not_tested",
            "judgment_link": False,
        },
        {
            "target": "SPOP mutation\nmolecular axis",
            "feature": (
                "SPOP-probe score\n"
                f"primary AUROC = {as_float(molecular['spop:frozen_primary']['primary_estimate']):.3f}\n"
                "unsupported in frozen design"
            ),
            "judgment": "No qualified feature\nfor head-use testing",
            "target_state": "unsupported",
            "feature_state": "unsupported",
            "judgment_state": "not_tested",
            "judgment_link": False,
        },
        {
            "target": "Recurrence\noutcome axis",
            "feature": (
                "Transferred image-risk score\n"
                f"C-index = {as_float(outcome['E04_reconstructed_with_tumor:frozen_risk:c_index']['primary_estimate']):.3f} reconstructed\n"
                f"C-index = {as_float(outcome['E08_official_pfi:frozen_risk:c_index']['primary_estimate']):.3f} official PFI"
            ),
            "judgment": (
                "Not applicable as input erasure\n"
                "recurrence is the outcome;\n"
                "validate prognosis externally"
            ),
            "target_state": "context_sensitive",
            "feature_state": "context_sensitive",
            "judgment_state": "not_tested",
            "judgment_link": False,
        },
    ]

    face = {
        "supported": "#D9EEE9",
        "context_sensitive": "#F7E6BC",
        "unsupported": "#F4D1D2",
        "not_tested": "#E5E5E5",
    }
    edge = {
        "supported": COLORS["supported"],
        "context_sensitive": COLORS["context_sensitive"],
        "unsupported": COLORS["unsupported"],
        "not_tested": COLORS["not_tested"],
    }
    columns = [(0.035, 0.25), (0.36, 0.315), (0.75, 0.215)]
    y_positions = np.linspace(5.65, 0.65, len(rows))
    height = 0.72

    fig, ax = plt.subplots(figsize=(12.0, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 6.65)
    ax.axis("off")
    ax.set_title(
        "Which clinical coordinate is represented, through which AI feature, and how far it reaches the judgment",
        loc="left",
        fontsize=12,
        fontweight="bold",
        pad=14,
    )
    headers = [
        "Clinically interpretable coordinate",
        "Operational AI feature in the frozen representation",
        "Evidence about downstream judgment",
    ]
    for (x, width), header in zip(columns, headers):
        ax.text(x + width / 2, 6.22, header, ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    for y, row in zip(y_positions, rows):
        states = [row["target_state"], row["feature_state"], row["judgment_state"]]
        texts = [row["target"], row["feature"], row["judgment"]]
        for (x, width), state, label in zip(columns, states, texts):
            box = FancyBboxPatch(
                (x, y - height / 2),
                width,
                height,
                boxstyle="round,pad=0.012,rounding_size=0.015",
                linewidth=1.25,
                edgecolor=edge[state],
                facecolor=face[state],
            )
            ax.add_patch(box)
            ax.text(x + width / 2, y, label, ha="center", va="center", fontsize=8.2, linespacing=1.25)

        first_arrow = FancyArrowPatch(
            (columns[0][0] + columns[0][1] + 0.006, y),
            (columns[1][0] - 0.006, y),
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.2,
            color=edge[row["feature_state"]],
        )
        ax.add_patch(first_arrow)
        second_state = row["judgment_state"]
        second_arrow = FancyArrowPatch(
            (columns[1][0] + columns[1][1] + 0.006, y),
            (columns[2][0] - 0.006, y),
            arrowstyle="-|>" if row["judgment_link"] else "-",
            mutation_scale=10,
            linewidth=1.2,
            linestyle="-" if row["judgment_link"] else "--",
            color=edge[second_state],
        )
        ax.add_patch(second_arrow)

    legend_y = 0.08
    legend_items = [
        ("supported", "supported / transported"),
        ("context_sensitive", "conditional or internal exploratory"),
        ("unsupported", "unsupported in the frozen design"),
        ("not_tested", "head-use not established (reason shown)"),
    ]
    x = 0.06
    for state, label in legend_items:
        ax.add_patch(FancyBboxPatch((x, legend_y), 0.018, 0.12, boxstyle="round,pad=0.002", facecolor=face[state], edgecolor=edge[state]))
        ax.text(x + 0.025, legend_y + 0.06, label, va="center", fontsize=7.5)
        x += 0.235
    fig.tight_layout()
    fig.savefig(FIGURES / "fig7_human_ai_linkage_map.pdf", bbox_inches="tight")
    plt.close(fig)


def render_known_target_alignment(sources: dict[str, Path]) -> None:
    transport = read_csv(sources["PBV-TRANSPORT"])
    molecular = index_rows(read_csv(sources["PBV-MOLECULAR"]))
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.3))

    grade = [row for row in transport if row["signal"] == "Gleason"]
    labels = [f"{r['cohort']} {r['institution']}\n({r['analysis_unit']}, n={r['n']})" for r in grade]
    for y, row in enumerate(grade):
        interval(axes[0, 0], y, row, "ci_low", "ci_high", COLORS["transportable"])
    axes[0, 0].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[0, 0].invert_yaxis()
    style_axis(axes[0, 0], "a  Grade alignment (Spearman rho)", 0.0)

    phenotype = [row for row in transport if row["signal"] == "Phenotype"]
    labels = [f"{r['cohort']} {r['institution']}\n{r['metric']}" for r in phenotype]
    for y, row in enumerate(phenotype):
        interval(axes[0, 1], y, row, "ci_low", "ci_high", COLORS["transportable"])
        null = 0.0 if "spearman" in row["metric"] else 0.5
        axes[0, 1].plot(null, y, marker="|", color="#777777", markersize=10)
    axes[0, 1].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[0, 1].invert_yaxis()
    axes[0, 1].set_title("b  Phenotype alignment (row-specific metric)", loc="left", fontweight="bold", fontsize=10)
    axes[0, 1].grid(axis="x", color="#E6E6E6", linewidth=0.7)
    axes[0, 1].spines[["top", "right", "left"]].set_visible(False)
    axes[0, 1].tick_params(axis="y", length=0)

    binary_keys = ["pten:frozen_primary", "spop:frozen_primary"]
    for y, key in enumerate(binary_keys):
        interval(axes[1, 0], y, molecular[key], "interval_low", "interval_high", COLORS[molecular[key]["evidence_state"]])
    axes[1, 0].set_yticks([0, 1], ["PTEN loss", "SPOP mutation"])
    axes[1, 0].invert_yaxis()
    style_axis(axes[1, 0], "c  Binary molecular alignment (AUROC)", 0.5)

    ar = molecular["ar:frozen_primary"]
    interval(axes[1, 1], 0, ar, "interval_low", "interval_high", COLORS[ar["evidence_state"]])
    axes[1, 1].set_yticks([0], ["AR activity"])
    axes[1, 1].set_ylim(0.7, -0.7)
    style_axis(axes[1, 1], "d  Continuous molecular alignment (Spearman rho)", 0.0)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig2_known_target_alignment.pdf", bbox_inches="tight")
    plt.close(fig)


def render_conditional_alignment(sources: dict[str, Path]) -> None:
    conditional = read_csv(sources["PBV-CONDITIONAL"])
    molecular = read_csv(sources["PBV-MOLECULAR"])
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.5))

    increments = [row for row in conditional if row["audit_type"] == "grade_adjusted_increment"]
    labels = [f"{r['target']} / {r['encoder']}\n{r['metric']} increment" for r in increments]
    for y, row in enumerate(increments):
        interval(axes[0], y, row, "ci_low", "ci_high", COLORS["context_sensitive"])
    axes[0].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[0].invert_yaxis()
    style_axis(axes[0], "a  Beyond-grade increment", 0.0)

    sites = [row for row in conditional if row["audit_type"] == "ar_site_transport"]
    labels = [r["site"] for r in sites]
    for y, row in enumerate(sites):
        interval(axes[1], y, row, "ci_low", "ci_high", COLORS["context_sensitive"])
    axes[1].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[1].invert_yaxis()
    style_axis(axes[1], "b  AR pooled and site estimates", 0.0)

    spop_sites = [
        row for row in molecular
        if row["component"] == "site_audit" and row["metric"] == "patient_auroc"
    ]
    labels = [f"{r['semantic_key'].split(':')[-1]} ({r['event_count']}/{r['patient_denominator']})" for r in spop_sites]
    for y, row in enumerate(spop_sites):
        interval(axes[2], y, row, "interval_low", "interval_high", COLORS["unsupported_in_frozen_design"])
    axes[2].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[2].invert_yaxis()
    style_axis(axes[2], "c  SPOP site AUROC (events/patients)", 0.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig3_conditional_alignment.pdf", bbox_inches="tight")
    plt.close(fig)


def render_stability(sources: dict[str, Path]) -> None:
    rows = [row for row in read_csv(sources["PBV-STABILITY"]) if row["component"] == "configuration_range"]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    labels = []
    for y, row in enumerate(rows):
        null = as_float(row["null_value"])
        low = as_float(row["range_low"]) - null
        high = as_float(row["range_high"]) - null
        mean = as_float(row["primary_estimate"]) - null
        state = row["evidence_state"]
        ax.errorbar(mean, y, xerr=[[mean - low], [high - mean]], fmt="o", color=COLORS[state], capsize=3)
        labels.append(
            f"{display_text(row['marker'])}  "
            f"({row['n_null_crossings']}/{row['n_configurations']} null-straddling)"
        )
    ax.axvline(0, color="#666666", linestyle="--", linewidth=0.9)
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("Observed metric minus target-specific null")
    ax.set_title("Correlated encoder--scale--tile--seed sensitivity", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#E6E6E6", linewidth=0.7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig4_representation_sensitivity.pdf", bbox_inches="tight")
    plt.close(fig)


def render_setting_contrasts(sources: dict[str, Path]) -> None:
    rows = read_csv(sources["PBV-STABILITY-CONTRASTS"])
    markers = ["gleason", "phenotype", "pten", "spop", "ar", "marker7"]
    contrast_specs = [
        ("native_vs_1.76", "a  Shared scale minus native scale"),
        ("virchow_vs_conch_at_1.76", "b  Virchow minus CONCH at 1.76 mpp"),
        ("tile64_vs16", "c  64 tiles minus 16 tiles"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.8), sharey=True)
    for ax, (contrast_id, title) in zip(axes, contrast_specs):
        values = [
            [as_float(row["delta_b_minus_a"]) for row in rows if row["contrast"] == contrast_id and row["marker"] == marker]
            for marker in markers
        ]
        boxes = ax.boxplot(
            values,
            orientation="horizontal",
            positions=np.arange(1, len(markers) + 1),
            widths=0.55,
            patch_artist=True,
            showfliers=True,
            medianprops={"color": "#222222", "linewidth": 1.2},
            whiskerprops={"color": "#666666"},
            capprops={"color": "#666666"},
            flierprops={"marker": ".", "markersize": 2.5, "markerfacecolor": "#777777", "markeredgecolor": "#777777"},
        )
        for patch, marker in zip(boxes["boxes"], markers):
            state = "unsupported_in_frozen_design" if marker == "spop" else (
                "transportable" if marker in {"gleason", "phenotype"} else "context_sensitive"
            )
            patch.set_facecolor(COLORS[state])
            patch.set_alpha(0.75)
        ax.axvline(0, color="#666666", linestyle="--", linewidth=0.9)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=9)
        ax.grid(axis="x", color="#E6E6E6", linewidth=0.7)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(np.arange(1, len(markers) + 1), ["Grade", "Phenotype", "PTEN", "SPOP", "AR", "Recurrence"])
    axes[0].invert_yaxis()
    fig.supxlabel("Paired change in the target-specific performance metric", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig5_setting_contrasts.pdf", bbox_inches="tight")
    plt.close(fig)


def render_outcome_contrasts(sources: dict[str, Path]) -> None:
    rows = [row for row in read_csv(sources["PBV-OUTCOME"]) if row["result_type"] == "same_patient_same_draw_delta"]
    endpoint_specs = [
        ("E04_reconstructed_with_tumor", "Reconstructed with-tumor"),
        ("E08_official_pfi", "Official TCGA-CDR PFI"),
    ]
    metric_specs = [("c_index", "C-index improvement"), ("ibs_0.5_5y", "IBS improvement")]
    contrast_order = [
        "GRADE_COMBINED_VS_GRADE",
        "FULL_COMBINED_VS_FULL",
        "IMAGE_VS_GRADE",
        "IMAGE_VS_FULL",
        "M5_VS_M4",
    ]
    contrast_labels = {
        "GRADE_COMBINED_VS_GRADE": "Grade + image vs grade",
        "FULL_COMBINED_VS_FULL": "Full clinical + image vs full clinical",
        "IMAGE_VS_GRADE": "Image vs grade",
        "IMAGE_VS_FULL": "Image vs full clinical",
        "M5_VS_M4": "Add image to clinical + site (M5 vs M4)",
    }
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.8))
    for i, (endpoint_id, endpoint_label) in enumerate(endpoint_specs):
        for j, (metric, metric_label) in enumerate(metric_specs):
            ax = axes[i, j]
            lookup = {
                row["contrast_id"]: row
                for row in rows
                if row["endpoint_id"] == endpoint_id and row["metric"] == metric
            }
            for y, contrast_id in enumerate(contrast_order):
                interval(ax, y, lookup[contrast_id], "ci_low", "ci_high", COLORS["context_sensitive"])
            ax.set_yticks(range(len(contrast_order)), [contrast_labels[item] for item in contrast_order], fontsize=8)
            ax.invert_yaxis()
            style_axis(ax, f"{chr(97 + i * 2 + j)}  {endpoint_label}: {metric_label}", 0.0)
            n = lookup[contrast_order[0]]["n"]
            events = lookup[contrast_order[0]]["n_events"]
            ax.text(0.98, 0.03, f"n={n}; events={events}", transform=ax.transAxes, ha="right", va="bottom", fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig6_outcome_contrasts.pdf", bbox_inches="tight")
    plt.close(fig)


def render_supplementary_stability_grid(sources: dict[str, Path]) -> None:
    rows = read_csv(sources["PBV-STABILITY-GRID"])
    markers = ["gleason", "phenotype", "pten", "spop", "ar", "marker7"]
    configurations = sorted(
        {(r["encoder"], float(r["target_mpp"]), int(r["tiles_per_slide"])) for r in rows},
        key=lambda item: (item[0], item[1], item[2]),
    )
    lookup = {
        (r["marker"], r["encoder"], float(r["target_mpp"]), int(r["tiles_per_slide"])):
        as_float(r["mean"]) - as_float(r["null_value"])
        for r in rows
    }
    matrix = np.array(
        [[lookup[(marker, encoder, mpp, tiles)] for encoder, mpp, tiles in configurations] for marker in markers]
    )
    bound = float(np.nanmax(np.abs(matrix)))
    fig, ax = plt.subplots(figsize=(12.0, 4.6))
    image = ax.imshow(matrix, cmap="RdBu_r", vmin=-bound, vmax=bound, aspect="auto")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:+.2f}", ha="center", va="center", fontsize=6)
    labels = [f"{encoder}\n{mpp:g} mpp / {tiles}" for encoder, mpp, tiles in configurations]
    ax.set_xticks(range(len(labels)), labels, rotation=55, ha="right", fontsize=7)
    ax.set_yticks(range(len(markers)), [display_text(marker) for marker in markers], fontsize=8)
    ax.set_title("All 72 encoder--scale--tile configuration means minus target-specific null", loc="left", fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="metric minus null")
    fig.tight_layout()
    fig.savefig(FIGURES / "sfig1_full_stability_grid.pdf", bbox_inches="tight")
    plt.close(fig)


def tex(value: str) -> str:
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_\\allowbreak{}",
        "{": "\\{",
        "}": "\\}",
    }
    return "".join(replacements.get(char, char) for char in value)


DISPLAY_TEXT = {
    "morphologic": "Morphologic",
    "molecular": "Molecular",
    "outcome": "Outcome",
    "androgen_receptor_activity": "AR activity",
    "post_hoc_recurrence_risk": "Post-hoc recurrence risk",
    "patient_case_image_or_session": "Patient, case image, or session",
    "patient_or_case_image": "Patient or case image",
    "spearman_rho": "Spearman rho",
    "spearman_rho_or_auroc": "Spearman rho or AUROC",
    "patient_spearman_rho": "Patient Spearman rho",
    "patient_auroc": "Patient AUROC",
    "patient_c_index": "Patient C-index",
    "c_index_and_paired_increment": "C-index and paired increment",
    "c_index": "C-index",
    "ibs_0.5_5y": "IBS (0.5--5 years)",
    "auroc": "AUROC",
    "r2": "R2",
    "gleason": "Grade",
    "phenotype": "Phenotype",
    "pten": "PTEN",
    "spop": "SPOP",
    "ar": "AR activity",
    "marker7": "Recurrence risk",
    "grade_information_is_recoverable_and_directionally_transports": "Grade information is recoverable and directionally transports",
    "morphology_linked_phenotype_is_recoverable_and_transports": "Morphology-linked phenotype is recoverable and transports",
    "within_cohort_PTEN_related_information_is_recoverable": "Within-cohort PTEN-related information is recoverable",
    "unsupported_in_the_frozen_primary_design": "Unsupported in the frozen primary design",
    "positive_pooled_within_cohort_alignment": "Positive pooled within-cohort alignment",
    "exploratory_endpoint_conditioned_alignment": "Exploratory endpoint-conditioned alignment",
    "transportable": "Transportable",
    "context_sensitive": "Context-sensitive",
    "unsupported_in_frozen_design": "Unsupported in frozen design",
    "descriptive_framework": "Descriptive framework",
    "internal_exploratory": "Internal exploratory",
    "deferred_follow_up": "Deferred follow-up",
    "not_tested": "Not tested",
    "internal_exploratory_only": "Internal exploratory only",
    "not_claimed": "Not claimed",
    "native_vs_1.76": "Shared 1.76 mpp - native scale",
    "virchow_vs_conch_at_1.76": "Virchow - CONCH at 1.76 mpp",
    "tile64_vs16": "64 tiles - 16 tiles",
    "frozen risk": "Frozen image-risk score",
    "FULL_COMBINED_VS_FULL": "Full clinical + image vs full clinical",
    "GRADE_COMBINED_VS_GRADE": "Grade + image vs grade",
    "IMAGE_VS_FULL": "Image vs full clinical",
    "IMAGE_VS_GRADE": "Image vs grade",
    "M5_VS_M4": "Add image to clinical + site (M5 vs M4)",
    "interval_not_saved": "Interval not saved",
    "replicate_accounting_not_saved": "Replicate accounting not saved",
    "bootstrap_accounted": "Bootstrap accounted",
    "event_count_not_applicable": "Event count not applicable",
    "event_count_not_recorded_in_source": "Event count not recorded in source",
    "primary_metric_undefined": "Primary metric undefined",
    "undefined_single_class": "Undefined: single class",
    "transport": "External transport",
    "molecular_evidence": "Molecular alignment",
    "conditional/site": "Conditional and site audits",
    "patient": "Patient",
    "case image": "Case image",
    "session": "Session",
    "tumor phenotype or content": "Tumor phenotype or content",
    "primary": "Primary",
    "secondary": "Secondary",
    "exploratory": "Exploratory",
    "continuous_marker_target": "Continuous or ordinal marker target",
    "binary_marker_target": "Binary marker target",
    "PTEN_or_AR_beyond_grade": "PTEN or AR beyond grade",
    "reconstructed_with_tumor": "Reconstructed recurrence with tumor",
    "strict_recurrence_only": "Strict recurrence only",
    "TCGA_CDR_PFS": "TCGA-CDR PFS",
    "TCGA_CDR_DFS": "TCGA-CDR DFS",
    "official_TCGA_CDR_PFI": "Official TCGA-CDR PFI",
    "three_and_five_year_landmark": "Three- and five-year landmarks",
    "delta_auroc_or_delta_r2": "Delta AUROC or delta R2",
    "c_index_td_auc_ibs": "C-index, time-dependent AUROC, and IBS",
    "c_index_td_auc": "C-index and time-dependent AUROC",
    "c_index_td_auc_landmark_auc": "C-index, time-dependent AUROC, and landmark AUROC",
    "c_index_and_endpoint_concordance": "C-index and endpoint concordance",
    "landmark_c_index_or_auroc": "Landmark C-index or AUROC",
    "known_target_recoverability": "Known-target recoverability",
    "conditional_uniqueness": "Conditional uniqueness beyond grade",
    "recurrence_alignment": "Recurrence alignment",
    "sensitivity": "Sensitivity analysis",
    "outcome_alignment": "Outcome alignment",
    "not_a_disease_decision": "Not a disease decision",
    "not_a_molecular_diagnosis": "Not a molecular diagnosis",
    "not_functional_use": "Not evidence of functional use",
    "not_official_PFI": "Not official PFI",
    "not_renamed_as_PFI": "Not relabeled as PFI",
    "not_equivalent_to_reconstructed_recurrence": "Not equivalent to reconstructed recurrence",
    "not_time_to_event_equivalence": "Not equivalent to a time-to-event analysis",
}


def display_text(value: str) -> str:
    """Convert registry/source codes to publication-facing text without changing source data."""
    return DISPLAY_TEXT.get(value, value.replace("_", " "))


def display_accounting(value: str) -> str:
    """Compact bootstrap accounting while retaining numerator and denominator."""
    return (
        display_text(value)
        .replace(" of 2000 bootstrap replicates undefined", "/2,000")
        .replace(" of 2000 paired bootstrap draws undefined", "/2,000")
    )


def write_table(
    path: Path,
    caption: str,
    label: str,
    headers: list[str],
    rows: list[list[str]],
    widths: str,
    *,
    tabcolsep: str | None = None,
    arraystretch: str | None = None,
    font_size: str = "\\scriptsize",
) -> None:
    lines = [
        "\\begin{table}[H]",
        "\\centering",
        font_size,
    ]
    if tabcolsep is not None:
        lines.append(f"\\setlength{{\\tabcolsep}}{{{tabcolsep}}}")
    if arraystretch is not None:
        lines.append(f"\\renewcommand{{\\arraystretch}}{{{arraystretch}}}")
    lines.extend([
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{widths}}}",
        "\\toprule",
        " & ".join(tex(item) for item in headers) + " \\\\",
        "\\midrule",
    ])
    lines.extend(" & ".join(tex(item) for item in row) + " \\\\" for row in rows)
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def generate_tables(sources: dict[str, Path]) -> None:
    claims = read_csv(PROVENANCE / "claim_evidence_matrix.csv")
    summary = [row for row in claims if row["claim_id"] in {"A02", "A03", "A04", "A05", "A06"}]
    claims_by_id = {row["claim_id"]: row for row in summary}
    evidence_state_names = {
        "transportable": "Transportable",
        "context_sensitive": "Context-sensitive",
        "unsupported_in_frozen_design": "Unsupported (frozen design)",
    }
    alignment_rows = [
        [
            "Grade/ISUP",
            evidence_state_names[claims_by_id["A02"]["evidence_state"]],
            "Grade information is recoverable and directionally transports across compatible external resources",
            "Internal locked-BCR-head sensitivity; external transport was encoder-specific: neither encoder passed LEOPARD, while Virchow alone passed CHIMERA",
        ],
        [
            "Tumor phenotype/content",
            evidence_state_names[claims_by_id["A02"]["evidence_state"]],
            "Morphology-linked phenotype is recoverable and transports directionally; the external target is grade-derived tumor/benign status, not exact tumor-content truth",
            "Currently blocked: same-cohort independent tumor-content truth unavailable",
        ],
        [
            "PTEN",
            evidence_state_names[claims_by_id["A03"]["evidence_state"]],
            claims_by_id["A03"]["claim"],
            "Feasible follow-up; not run",
        ],
        [
            "AR activity",
            evidence_state_names[claims_by_id["A04"]["evidence_state"]],
            claims_by_id["A04"]["claim"],
            "Feasible follow-up; not run",
        ],
        [
            "SPOP",
            evidence_state_names[claims_by_id["A05"]["evidence_state"]],
            "Evaluated against an available genomic reference, but no reliable frozen-design signal was established",
            "Not qualified: recoverability unsupported",
        ],
        [
            "Recurrence",
            evidence_state_names[claims_by_id["A06"]["evidence_state"]],
            claims_by_id["A06"]["claim"],
            "Not applicable as input erasure; prognostic validation required",
        ],
    ]
    write_table(
        GENERATED / "table1_alignment_summary.tex",
        "Evidence-qualified candidate shared coordinates. States summarize the available axis-specific evidence: transportable means directional external transfer was retained; context-sensitive means interpretation narrowed under a clinical, site, representation, sampling, or endpoint audit; unsupported means the frozen primary design did not qualify the signal. Functional use refers specifically to intervention on a locked BCR head and is not implied by recoverability.",
        "tab:alignment-summary",
        ["Target", "State", "Permitted interpretation", "Functional use"],
        alignment_rows,
        "@{}>{\\raggedright\\arraybackslash}p{0.15\\textwidth}"
        ">{\\raggedright\\arraybackslash}p{0.16\\textwidth}"
        ">{\\raggedright\\arraybackslash}p{0.38\\textwidth}"
        ">{\\raggedright\\arraybackslash}p{0.23\\textwidth}@{}",
        tabcolsep="3pt",
        arraystretch="1.18",
        font_size="\\footnotesize",
    )

    targets = read_csv(PROVENANCE / "alignment_target_registry.csv")
    write_table(
        GENERATED / "stable1_target_registry.tex",
        "Registered target definitions and interpretation boundaries. The unit and metric specify how each target was evaluated; the permitted-interpretation column is the claim ceiling and does not imply disease prediction or functional use by a downstream head.",
        "tab:supp-target-registry",
        ["ID", "Layer", "Target", "Unit", "Metric", "Permitted interpretation"],
        [[r["target_id"], display_text(r["target_layer"]), display_text(r["target_label"]), display_text(r["primary_unit"]), display_text(r["primary_metric"]), display_text(r["permitted_interpretation"])] for r in targets],
        "@{}p{0.04\\textwidth}p{0.10\\textwidth}p{0.15\\textwidth}p{0.17\\textwidth}p{0.13\\textwidth}p{0.27\\textwidth}@{}",
    )

    primary_rows = read_csv(sources["PBV-TRANSPORT"])
    primary_rows += [r for r in read_csv(sources["PBV-MOLECULAR"]) if r["component"] == "frozen_primary"]
    formatted = []
    for r in primary_rows:
        target = r.get("signal") or r.get("target")
        cohort = r["cohort"]
        metric = display_text(r["metric"])
        unit = display_text(r["analysis_unit"])
        n = r.get("n") or r.get("patient_denominator")
        estimate = f"{as_float(r['primary_estimate']):.3f}"
        lo = r.get("ci_low") or r.get("interval_low") or ""
        hi = r.get("ci_high") or r.get("interval_high") or ""
        interval_text = "unavailable" if not lo or not hi else f"{float(lo):.3f} to {float(hi):.3f}"
        formatted.append([target, cohort, metric, unit, n, estimate, interval_text])
    write_table(
        GENERATED / "stable2_primary_estimates.tex",
        "Primary known-target alignment estimates. Metrics, analysis units, and denominators are row-specific; intervals are 95 percent patient-bootstrap intervals where retained, and unavailable intervals were not reconstructed.",
        "tab:supp-primary-estimates",
        ["Target", "Cohort", "Metric", "Unit", "n", "Estimate", "Interval"],
        formatted,
        "@{}p{0.10\\textwidth}p{0.12\\textwidth}p{0.13\\textwidth}p{0.11\\textwidth}p{0.05\\textwidth}p{0.08\\textwidth}p{0.22\\textwidth}@{}",
    )
    write_table(
        GENERATED / "table2_primary_evidence.tex",
        "Complete primary recoverability and external morphology-transport estimates. Metrics and analysis units remain row-specific; unavailable intervals were not reconstructed.",
        "tab:primary-evidence",
        ["Target", "Cohort", "Metric", "Unit", "n", "Estimate", "Interval"],
        formatted,
        "@{}p{0.10\\textwidth}p{0.12\\textwidth}p{0.13\\textwidth}p{0.11\\textwidth}p{0.05\\textwidth}p{0.08\\textwidth}p{0.22\\textwidth}@{}",
    )

    increments = [r for r in read_csv(sources["PBV-CONDITIONAL"]) if r["audit_type"] == "grade_adjusted_increment"]
    write_table(
        GENERATED / "stable3_conditional_increments.tex",
        "Held-out molecular-target increments beyond grade. Delta is the image-augmented model minus the grade reference on untouched outer-fold patients; positive values favor adding the image score. Intervals are 95 percent patient-bootstrap intervals.",
        "tab:supp-conditional-increments",
        ["Target", "Encoder", "Metric", "n", "Delta", "Interval"],
        [[r["target"], r["encoder"], display_text(r["metric"]), r["n_patients"], f"{as_float(r['primary_estimate']):+.3f}", f"{as_float(r['ci_low']):+.3f} to {as_float(r['ci_high']):+.3f}"] for r in increments],
        "@{}p{0.12\\textwidth}p{0.12\\textwidth}p{0.12\\textwidth}p{0.08\\textwidth}p{0.13\\textwidth}p{0.28\\textwidth}@{}",
    )

    stability = [r for r in read_csv(sources["PBV-STABILITY"]) if r["component"] == "configuration_range"]
    write_table(
        GENERATED / "stable4_stability_summary.tex",
        "Observed ranges across 12 correlated encoder--scale--tile configurations. Mean and range summarize the five-seed configuration values; null-straddling is the number of configurations whose observed seed range crossed the target-specific null, out of 12. These are sensitivity summaries, not independent validations.",
        "tab:supp-stability",
        ["Target", "Metric", "Null", "Mean", "Range", "Null-straddling"],
        [[display_text(r["marker"]), display_text(r["metric"]), f"{as_float(r['null_value']):.1f}", f"{as_float(r['primary_estimate']):.3f}", f"{as_float(r['range_low']):.3f} to {as_float(r['range_high']):.3f}", f"{r['n_null_crossings']}/{r['n_configurations']}"] for r in stability],
        "@{}p{0.10\\textwidth}p{0.19\\textwidth}p{0.08\\textwidth}p{0.10\\textwidth}p{0.23\\textwidth}p{0.15\\textwidth}@{}",
    )

    molecular_sites = [r for r in read_csv(sources["PBV-MOLECULAR"]) if r["component"] == "site_audit"]
    ar_sites = [r for r in read_csv(sources["PBV-CONDITIONAL"]) if r["audit_type"] == "ar_site_transport"]
    site_rows: list[list[str]] = []
    for r in ar_sites:
        site_rows.append([
            "AR",
            r["site"],
            display_text(r["metric"]),
            r["n_patients"],
            "not applicable",
            f"{as_float(r['primary_estimate']):.3f}",
            f"{as_float(r['ci_low']):.3f} to {as_float(r['ci_high']):.3f}",
            display_accounting(r["missingness_status"]),
        ])
    for r in molecular_sites:
        site = r["semantic_key"].split(":")[-1]
        undefined = r["metric"] != "patient_auroc"
        site_rows.append([
            "SPOP",
            site,
            "AUROC",
            r["patient_denominator"],
            r["event_count"],
            "undefined" if undefined else f"{as_float(r['primary_estimate']):.3f}",
            "unavailable" if undefined else f"{as_float(r['interval_low']):.3f} to {as_float(r['interval_high']):.3f}",
            display_accounting(r["missingness_detail"]),
        ])
    write_table(
        GENERATED / "stable_site_audits.tex",
        "Complete AR and SPOP site audits. AR effects are slide-level with patient-cluster intervals; SPOP uses patient AUROC. The CH SPOP row is undefined because no positive event was present. Bootstrap accounting reports undefined draws out of 2,000 where applicable.",
        "tab:supp-site-audits",
        ["Target", "Site", "Metric", "Patients", "Events", "Estimate", "Interval", "Accounting"],
        site_rows,
        "@{}p{0.055\\textwidth}p{0.06\\textwidth}p{0.11\\textwidth}p{0.065\\textwidth}p{0.065\\textwidth}p{0.08\\textwidth}p{0.16\\textwidth}p{0.16\\textwidth}@{}",
    )

    contrast_rows = read_csv(sources["PBV-STABILITY-CONTRASTS"])
    contrast_names = ["native_vs_1.76", "virchow_vs_conch_at_1.76", "tile64_vs16"]
    marker_names = ["gleason", "phenotype", "pten", "spop", "ar", "marker7"]
    contrast_summary: list[list[str]] = []
    for contrast_name in contrast_names:
        for marker in marker_names:
            group = [r for r in contrast_rows if r["contrast"] == contrast_name and r["marker"] == marker]
            values = np.array([as_float(r["delta_b_minus_a"]) for r in group], dtype=float)
            contrast_summary.append([
                display_text(contrast_name),
                display_text(marker),
                str(len(group)),
                f"{float(np.median(values)):+.3f}",
                f"{float(np.min(values)):+.3f} to {float(np.max(values)):+.3f}",
                str(sum(r["null_crossing"] == "True" for r in group)),
                str(sum(r["exact_tie"] == "True" for r in group)),
            ])
    write_table(
        GENERATED / "stable_contrast_summary.tex",
        "Complete summary of the 390 seed-matched setting contrasts. Delta direction is setting B minus setting A in the named contrast.",
        "tab:supp-contrast-summary",
        ["Contrast", "Target", "Pairs", "Median delta", "Range", "Null crossing", "Exact ties"],
        contrast_summary,
        "@{}p{0.15\\textwidth}p{0.11\\textwidth}p{0.06\\textwidth}p{0.10\\textwidth}p{0.17\\textwidth}p{0.10\\textwidth}p{0.08\\textwidth}@{}",
    )

    endpoints = read_csv(PROVENANCE / "endpoint_hierarchy.csv")
    write_table(
        GENERATED / "stable5_endpoint_hierarchy.tex",
        "Registered endpoint hierarchy and non-equivalence boundaries. Primary rows define known-target recoverability, secondary rows test conditional or horizon-specific questions, and exploratory rows audit recurrence definitions. Each row keeps its own metric and boundary; endpoint IDs are not interchangeable outcomes.",
        "tab:supp-endpoints",
        ["ID", "Hierarchy", "Target or endpoint", "Metric", "Role", "Boundary"],
        [[r["endpoint_id"], display_text(r["hierarchy"]), display_text(r["target_or_endpoint"]), display_text(r["metric"]), display_text(r["role"]), display_text(r["non_equivalence_boundary"])] for r in endpoints],
        "@{}p{0.05\\textwidth}p{0.12\\textwidth}p{0.16\\textwidth}p{0.14\\textwidth}p{0.15\\textwidth}p{0.17\\textwidth}@{}",
    )

    outcome_rows = read_csv(sources["PBV-OUTCOME"])
    for endpoint_id, filename, label, caption in [
        (
            "E04_reconstructed_with_tumor",
            "stable_outcome_reconstructed.tex",
            "tab:supp-outcome-reconstructed",
            "Complete frozen-risk and paired comparisons for the reconstructed recurrence-with-tumor endpoint. Paired rows use the same patients and bootstrap draws. C-index delta is augmented or first model minus reference; IBS delta is reference minus augmented or first model, so positive values favor the augmented or first model. Intervals are 95 percent patient-bootstrap intervals; accounting reports undefined draws out of 2,000.",
        ),
        (
            "E08_official_pfi",
            "stable_outcome_official_pfi.tex",
            "tab:supp-outcome-official-pfi",
            "Complete frozen-risk and paired comparisons for official TCGA-CDR PFI. Paired rows use the same patients and bootstrap draws. C-index delta is augmented or first model minus reference; IBS delta is reference minus augmented or first model, so positive values favor the augmented or first model. Intervals are 95 percent patient-bootstrap intervals; accounting reports undefined draws out of 2,000.",
        ),
    ]:
        selected = [r for r in outcome_rows if r["endpoint_id"] == endpoint_id]
        formatted_outcomes = []
        for r in selected:
            comparison = "frozen risk" if r["result_type"] == "frozen_risk_performance" else r["contrast_id"]
            formatted_outcomes.append([
                display_text(comparison),
                display_text(r["metric"]),
                r["n"],
                r["n_events"],
                f"{as_float(r['primary_estimate']):+.3f}",
                f"{as_float(r['ci_low']):+.3f} to {as_float(r['ci_high']):+.3f}",
                display_accounting(r["missingness_detail"]),
            ])
        write_table(
            GENERATED / filename,
            caption,
            label,
            ["Comparison", "Metric", "n", "Events", "Estimate", "Interval", "Undefined / 2,000"],
            formatted_outcomes,
            "@{}p{0.23\\textwidth}p{0.11\\textwidth}p{0.04\\textwidth}p{0.06\\textwidth}p{0.08\\textwidth}p{0.16\\textwidth}p{0.11\\textwidth}@{}",
        )

    site_functional = index_numeric_source(read_csv(sources["QFM-FM6-SITE-HELDOUT"]))
    external_functional = index_numeric_source(read_csv(sources["QFM-FM6-LEOPARD-EXTERNAL"]))
    chimera_functional = index_numeric_source(read_csv(sources["QFM-FM6-CHIMERA-EXTERNAL"]))
    functional_transport_rows: list[list[str]] = []
    for encoder in ("conch", "virchow"):
        site_row = site_functional[encoder]
        functional_transport_rows.append([
            "TCGA site-heldout",
            encoder,
            f"{as_float(site_row['full_stratified_c_index']):.3f} "
            f"({as_float(site_row['full_stratified_c_index_ci_low']):.3f} to "
            f"{as_float(site_row['full_stratified_c_index_ci_high']):.3f})",
            f"{as_float(site_row['target_delta_use']):+.3f} "
            f"({as_float(site_row['target_delta_use_ci_low']):+.3f} to "
            f"{as_float(site_row['target_delta_use_ci_high']):+.3f})",
            "Pass" if site_row["site_heldout_functional_transport_pass"] == "True" else "Fail or inconclusive",
        ])
        external_row = external_functional[encoder]
        functional_transport_rows.append([
            "LEOPARD external",
            encoder,
            f"{as_float(external_row['full_c_index']):.3f} "
            f"({as_float(external_row['full_c_index_ci_low']):.3f} to "
            f"{as_float(external_row['full_c_index_ci_high']):.3f})",
            f"{as_float(external_row['target_delta_use']):+.3f} "
            f"({as_float(external_row['target_delta_use_ci_low']):+.3f} to "
            f"{as_float(external_row['target_delta_use_ci_high']):+.3f})",
            "Pass" if external_row["external_whole_tissue_functional_transport_pass"] == "True" else "Fail or inconclusive",
        ])
        chimera_row = chimera_functional[encoder]
        functional_transport_rows.append([
            "CHIMERA external",
            encoder,
            f"{as_float(chimera_row['full_c_index']):.3f} "
            f"({as_float(chimera_row['full_c_index_ci_low']):.3f} to "
            f"{as_float(chimera_row['full_c_index_ci_high']):.3f})",
            f"{as_float(chimera_row['target_delta_use']):+.3f} "
            f"({as_float(chimera_row['target_delta_use_ci_low']):+.3f} to "
            f"{as_float(chimera_row['target_delta_use_ci_high']):+.3f})",
            "Pass" if chimera_row["functional_erasure_gate_pass"] == "True" else "Fail or inconclusive",
        ])
    write_table(
        GENERATED / "stable_external_functional_transport.tex",
        "Locked site-heldout and independent-patient functional-transport tests. C-index intervals and targeted erasure deltas use 2,000 patient-bootstrap draws. Passing required valid full-head discrimination, a positive targeted-delta interval, matched-random significance after Holm correction, and the family-specific gate. CHIMERA used 95 patients and 27 events, limiting precision.",
        "tab:supp-functional-transport",
        ["Frame", "Encoder", "Full-head C-index (95% CI)", "Target delta (95% CI)", "Gate"],
        functional_transport_rows,
        "@{}p{0.16\\textwidth}p{0.10\\textwidth}p{0.20\\textwidth}p{0.20\\textwidth}p{0.16\\textwidth}@{}",
    )

    missingness_groups = {
        "transport": read_csv(sources["PBV-TRANSPORT"]),
        "molecular_evidence": read_csv(sources["PBV-MOLECULAR"]),
        "conditional/site": read_csv(sources["PBV-CONDITIONAL"]),
        "outcome": read_csv(sources["PBV-OUTCOME"]),
    }
    missingness_summary: list[list[str]] = []
    for component, component_rows in missingness_groups.items():
        counts = Counter(r["missingness_status"] for r in component_rows)
        for status, count in sorted(counts.items()):
            missingness_summary.append([display_text(component), display_text(status), str(count)])
    write_table(
        GENERATED / "stable_missingness_summary.tex",
        "Row-level availability and uncertainty-accounting states retained in the promoted evidence. Counts are source-table rows, not patients or independent tests; unavailable quantities and undefined single-class estimates were preserved rather than reconstructed.",
        "tab:supp-missingness-summary",
        ["Evidence component", "Availability/accounting state", "Rows"],
        missingness_summary,
        "@{}p{0.27\\textwidth}p{0.48\\textwidth}p{0.10\\textwidth}@{}",
    )

    write_table(
        GENERATED / "stable6_claim_matrix.tex",
        "Claim--evidence and functional-use boundary. A identifiers denote this manuscript's claims, C identifiers denote promoted source claims, and T identifiers denote registered targets. The state summarizes the qualified evidence, whereas functional use records whether a locked-head intervention was tested; recoverability alone does not establish head use.",
        "tab:supp-claim-matrix",
        ["Claim", "Source claims", "Targets", "State", "Functional use"],
        [[r["claim_id"], r["source_claim_ids"].replace(";", "; "), r["target_ids"].replace(";", "; "), display_text(r["evidence_state"]), display_text(r["functional_use_status"])] for r in claims],
        "@{}p{0.05\\textwidth}p{0.12\\textwidth}p{0.16\\textwidth}p{0.23\\textwidth}p{0.13\\textwidth}@{}",
    )


def verify_numeric_mapping(sources: dict[str, Path]) -> list[dict[str, str]]:
    cache: dict[str, dict[str, dict[str, str]]] = {}
    report: list[dict[str, str]] = []
    for row in read_csv(PROVENANCE / "numeric_qa_mapping.csv"):
        source_id = row["source_id"]
        if source_id not in cache:
            cache[source_id] = index_numeric_source(read_csv(sources[source_id]))
        source_row = cache[source_id][row["semantic_key"]]
        field = row["field"]
        if field == "n_null_crossings/n_configurations":
            actual = f"{source_row['n_null_crossings']}/{source_row['n_configurations']}"
        else:
            value = float(source_row[field])
            actual = format(value, row["format"])
        status = "PASS" if actual == row["expected_display"] else "FAIL"
        report.append({"numeric_id": row["numeric_id"], "expected": row["expected_display"], "actual": actual, "status": status})
    failures = [row for row in report if row["status"] != "PASS"]
    if failures:
        raise RuntimeError("Numeric QA failed: " + json.dumps(failures, indent=2))
    return report


def verify_manuscript_semantics(sources: dict[str, Path]) -> list[str]:
    """Fail closed on headline provenance, units, endpoints, and interval contracts."""
    section_paths = {
        "results": WORKSPACE / "sections" / "results.tex",
        "methods": WORKSPACE / "sections" / "methods.tex",
        "supplement": WORKSPACE / "sections" / "supplementary_information.tex",
    }
    section_text = {
        name: " ".join(path.read_text(encoding="utf-8").split())
        for name, path in section_paths.items()
    }
    failures: list[str] = []
    checks: list[str] = []

    def require(name: str, section: str, fragment: str) -> None:
        if fragment not in section_text[section]:
            failures.append(f"{name}:{section}:missing={fragment}")
        else:
            checks.append(name)

    # Every mapped headline value must come from a registered source and appear in its
    # declared manuscript section. This prevents an unmapped display value from replacing
    # a source-linked value while retaining a superficially successful source-hash check.
    manifest_ids = {row["source_id"] for row in read_csv(PROVENANCE / "source_evidence_manifest.csv")}
    for row in read_csv(PROVENANCE / "numeric_qa_mapping.csv"):
        if row["source_id"] not in manifest_ids:
            failures.append(f"numeric-source-unregistered:{row['numeric_id']}:{row['source_id']}")
            continue
        section = "supplement" if row["manuscript_location"].startswith("supplement") else "results"
        displays = {
            row["expected_display"],
            row["expected_display"].lstrip("+"),
            row["expected_display"].replace("/", " of "),
        }
        if not any(display in section_text[section] for display in displays):
            failures.append(
                f"numeric-display-missing:{row['numeric_id']}:{section}:{row['expected_display']}"
            )
        else:
            checks.append(f"numeric-display:{row['numeric_id']}")

    transport = index_rows(read_csv(sources["PBV-TRANSPORT"]))
    molecular = index_rows(read_csv(sources["PBV-MOLECULAR"]))
    outcomes = index_rows(read_csv(sources["PBV-OUTCOME"]))
    fm6 = {row["encoder"].casefold(): row for row in read_csv(sources["QFM-FM6-SUMMARY"])}
    chimera = {row["encoder"].casefold(): row for row in read_csv(sources["QFM-FM6-CHIMERA-EXTERNAL"])}

    require("nadt-denominator-unit", "results", f"{transport['gleason:nadt']['n']} patients")
    require("panda-karolinska-unit", "results", f"{transport['gleason_panda:karolinska']['n']} case images")
    require("panda-radboud-unit", "results", f"{transport['gleason_panda:radboud']['n']} case images")
    require("precise-session-unit", "results", f"{transport['gleason_precise:all']['n']} imaging sessions")
    require("molecular-denominator", "results", f"{molecular['pten:frozen_primary']['patient_denominator']} TCGA-PRAD patients")
    require("patient-bootstrap-main", "results", "patient-bootstrap interval")
    require("patient-bootstrap-methods", "methods", "patient-bootstrap intervals")
    require("site-cluster-interval", "methods", "patients resampled as clusters")

    reconstructed = outcomes["E04_reconstructed_with_tumor:frozen_risk:c_index"]
    official = outcomes["E08_official_pfi:frozen_risk:c_index"]
    require("reconstructed-denominator", "results", f"{reconstructed['n']}-patient transfer frame")
    require("reconstructed-events", "results", f"{reconstructed['n_events']} events")
    require("official-events", "results", f"{official['n_events']} events")
    require("complete-case-denominator", "results", "153 complete cases")
    require("endpoint-separation", "methods", "Reconstructed recurrence and official PFI were evaluated separately")
    require("oof-contract", "methods", "patient-disjoint out-of-fold or locked external output")
    require("no-retrospective-endpoint-substitution", "supplement", "must not be pooled")

    conch = fm6["conch"]
    require("fm6-denominator", "results", f"{conch['n_subjects']} TCGA-PRAD patients")
    require("fm6-events", "results", f"{conch['n_events']} BCR events")
    require("fm6-random-p-conch", "results", f"p={float(conch['target_vs_random_p_one_sided']):.4f}")
    require("fm6-clean-hash-count", "supplement", "All 20 regenerated hashes matched exactly")
    require("computational-not-external", "results", "not an independent-cohort replication")
    require("chimera-denominator", "results", f"{chimera['conch']['n_subjects']} CHIMERA patients")
    require("chimera-events", "results", f"{chimera['conch']['n_events']} BCR events")
    require("chimera-conch-status", "results", "CONCH therefore remained fail or inconclusive")
    require("chimera-virchow-status", "results", "Virchow passed every prespecified gate")
    require("chimera-rerun", "supplement", "all six nonvolatile output hashes exactly")
    require("no-encoder-superiority", "methods", "not designed as a formal encoder-superiority comparison")

    if failures:
        raise RuntimeError("Manuscript semantic QA failed:\n" + "\n".join(failures))
    return checks


def prepare_build_root(build_root: Path) -> None:
    """Stage immutable manuscript sources when rendering outside the tracked workspace."""
    if build_root == WORKSPACE:
        return
    build_root.mkdir(parents=True, exist_ok=True)
    for source_name in ("main.tex", "supplement.tex"):
        shutil.copy2(WORKSPACE / source_name, build_root / source_name)
    shutil.copytree(WORKSPACE / "sections", build_root / "sections", dirs_exist_ok=True)
    shutil.copytree(WORKSPACE / "provenance", build_root / "provenance", dirs_exist_ok=True)


def build_pdfs() -> list[str]:
    engine = shutil.which("xelatex")
    if engine is None:
        return ["xelatex unavailable; PDF build skipped"]
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "1786766400"
    messages: list[str] = []
    for source in ("main.tex", "supplement.tex"):
        for _ in range(2):
            completed = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", source],
                cwd=BUILD_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode:
                tail = "\n".join(completed.stdout.splitlines()[-30:])
                raise RuntimeError(f"XeLaTeX failed for {source}:\n{tail}")
        messages.append(f"built:{source}")
    return messages


def main() -> int:
    global BUILD_ROOT, FIGURES, GENERATED
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Render into an isolated directory (for example, a fresh /tmp path).",
    )
    args = parser.parse_args()
    if args.output_root is not None:
        BUILD_ROOT = args.output_root.resolve()
        FIGURES = BUILD_ROOT / "figures"
        GENERATED = BUILD_ROOT / "generated"
        prepare_build_root(BUILD_ROOT)
    FIGURES.mkdir(exist_ok=True)
    GENERATED.mkdir(exist_ok=True)
    sources = verify_sources()
    numeric_report = verify_numeric_mapping(sources)
    semantic_report = verify_manuscript_semantics(sources)
    messages = [
        f"verified_sources={len(sources)}",
        f"numeric_rows={len(numeric_report)}",
        f"semantic_contracts={len(semantic_report)}",
    ]
    if not args.verify_only:
        render_alignment_map(sources)
        render_known_target_alignment(sources)
        render_conditional_alignment(sources)
        render_stability(sources)
        render_setting_contrasts(sources)
        render_outcome_contrasts(sources)
        render_human_ai_linkage_map(sources)
        render_supplementary_stability_grid(sources)
        generate_tables(sources)
        if not args.no_pdf:
            messages.extend(build_pdfs())
    report = {
        "status": "PASS",
        "source_count": len(sources),
        "numeric_qa_count": len(numeric_report),
        "semantic_qa_count": len(semantic_report),
        "messages": messages,
    }
    (GENERATED / "build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
