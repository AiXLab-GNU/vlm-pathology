#!/usr/bin/env python3
"""Render FM6 internal-pilot figures only from saved CSV source tables."""
from __future__ import annotations

import os
import hashlib
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/qfm_fm6_matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
OUTPUTS = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm6_internal_development_pilot/outputs"
FIGURES = OUTPUTS / "figures"
COLORS = {"conch": "#2F6B9A", "virchow": "#C75B39"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def save(figure: plt.Figure, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURES / f"{name}.png", dpi=220, bbox_inches="tight")
    figure.savefig(
        FIGURES / f"{name}.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None, "Creator": "QFM FM6 deterministic renderer"},
    )
    plt.close(figure)


def figure_isup_recoverability(oof: pd.DataFrame, summary: pd.DataFrame) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 4.0), sharex=True, sharey=True)
    for axis, encoder in zip(axes, ["conch", "virchow"], strict=True):
        frame = oof[oof.encoder.eq(encoder)]
        rng = np.random.default_rng(260818)
        jitter = rng.uniform(-0.08, 0.08, len(frame))
        axis.scatter(frame.isup_grade_group + jitter, frame.isup_prediction, s=14, alpha=0.42, color=COLORS[encoder], linewidths=0)
        medians = frame.groupby("isup_grade_group").isup_prediction.median()
        axis.plot(medians.index, medians.values, marker="o", color="black", linewidth=1.5, label="grade median")
        row = summary[summary.encoder.eq(encoder)].iloc[0]
        axis.text(0.04, 0.95, f"OOF Spearman = {row.isup_spearman:.3f}\nMAE = {row.isup_mae:.3f}", transform=axis.transAxes, va="top")
        axis.set_title(encoder.upper() if encoder == "conch" else "Virchow")
        axis.set_xlabel("Observed ISUP Grade Group")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("OOF predicted ISUP")
    figure.suptitle("Whole-tissue ISUP recoverability (internal development)")
    figure.tight_layout()
    save(figure, "fm6-figure-1-isup-recoverability")


def figure_erasure_controls(summary: pd.DataFrame) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), sharex=True, sharey=True)
    for axis, encoder in zip(axes, ["conch", "virchow"], strict=True):
        random = pd.read_csv(OUTPUTS / f"fm6_{encoder}_matched_random_erasure_controls.csv")
        row = summary[summary.encoder.eq(encoder)].iloc[0]
        axis.hist(random.delta_use, bins=18, color="#B9C2C9", edgecolor="white")
        axis.axvline(row.target_fixed_delta_use, color=COLORS[encoder], linewidth=2.2, label="ISUP-correlated direction")
        axis.axvline(row.random_delta_p95, color="black", linestyle="--", linewidth=1.3, label="random p95")
        axis.set_title(encoder.upper() if encoder == "conch" else "Virchow")
        axis.set_xlabel("Full minus erased C-index")
        axis.grid(alpha=0.2, axis="y")
    axes[0].set_ylabel("Matched-random controls")
    axes[1].legend(frameon=False, fontsize=8)
    figure.suptitle("ISUP-correlated fixed-head sensitivity versus variance-matched controls")
    figure.tight_layout()
    save(figure, "fm6-figure-2-erasure-controls")


def figure_head_comparison(summary: pd.DataFrame, bootstrap: pd.DataFrame) -> None:
    labels = ["ISUP", "AI full", "AI erased", "AI refit", "ISUP+AI"]
    metrics = ["isup_only_risk", "full_risk", "target_fixed_risk", "target_refit_risk", "isup_plus_ai_risk"]
    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.0), sharey=True)
    for axis, encoder in zip(axes, ["conch", "virchow"], strict=True):
        frame = bootstrap[bootstrap.encoder.eq(encoder)].set_index("metric").loc[metrics]
        x = np.arange(len(labels))
        estimate = frame.estimate.to_numpy(float)
        error = np.vstack([estimate - frame.ci_low.to_numpy(float), frame.ci_high.to_numpy(float) - estimate])
        axis.bar(x, estimate, color=COLORS[encoder], alpha=0.82)
        axis.errorbar(x, estimate, yerr=error, fmt="none", color="black", capsize=3, linewidth=1)
        axis.axhline(0.5, color="black", linestyle="--", linewidth=1)
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.set_title(encoder.upper() if encoder == "conch" else "Virchow")
        axis.grid(alpha=0.2, axis="y")
    axes[0].set_ylabel("OOF Harrell C-index (patient bootstrap 95% CI)")
    figure.suptitle("BCR head validity, erasure, refit, and clinical combination")
    figure.tight_layout()
    save(figure, "fm6-figure-3-bcr-head-comparison")


def main() -> None:
    oof = pd.read_csv(OUTPUTS / "fm6_tcga_patient_oof_predictions.csv")
    summary = pd.read_csv(OUTPUTS / "fm6_tcga_internal_pilot_summary.csv")
    bootstrap = pd.read_csv(OUTPUTS / "fm6_tcga_patient_bootstrap_intervals.csv")
    figure_isup_recoverability(oof, summary)
    figure_erasure_controls(summary)
    figure_head_comparison(summary, bootstrap)
    records = []
    for path in sorted(FIGURES.iterdir()):
        if path.suffix in {".png", ".pdf"}:
            records.append({
                "figure_file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "source_tables": "fm6_tcga_patient_oof_predictions.csv;fm6_tcga_internal_pilot_summary.csv;fm6_tcga_patient_bootstrap_intervals.csv;fm6_<encoder>_matched_random_erasure_controls.csv",
            })
    pd.DataFrame(records).to_csv(OUTPUTS / "fm6_figure_manifest.csv", index=False, lineterminator="\n")
    print(f"rendered 3 figure families to {FIGURES}")


if __name__ == "__main__":
    main()
