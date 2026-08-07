"""Render final marker-7 paired survival results from frozen R4 CSV outputs."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUMMARY = ROOT / "models/marker7_survival_common_cohort_summary.csv"
DELTAS = ROOT / "models/marker7_survival_paired_deltas.csv"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRID = "#e1e0d9"

ENDPOINTS = ("E04_reconstructed_with_tumor", "E08_official_pfi")
MODELS = (
    "H_M0", "H_M1", "H_M2", "H_M3", "H_M4", "H_M5", "N_IMAGE",
    "N_GRADE_CLINICAL", "N_GRADE_COMBINED", "N_FULL_CLINICAL", "N_FULL_COMBINED",
)
CONTRASTS = (
    "IMAGE_VS_GRADE", "GRADE_COMBINED_VS_GRADE", "IMAGE_VS_FULL",
    "FULL_COMBINED_VS_FULL", "M5_VS_M4",
)
METRICS = ("c_index", "ibs_0.5_5y")


def load_sources(summary_csv: Path = SUMMARY, deltas_csv: Path = DELTAS):
    summary = pd.read_csv(summary_csv)
    deltas = pd.read_csv(deltas_csv)
    if len(summary) != 44:
        raise ValueError(f"Figure 7 summary must contain exactly 44 rows, found {len(summary)}")
    if len(deltas) != 20:
        raise ValueError(f"Figure 7 deltas must contain exactly 20 rows, found {len(deltas)}")
    summary_keys = set(map(tuple, summary[["endpoint_id", "model_id", "metric"]].to_numpy()))
    expected_summary = {(e, m, metric) for e in ENDPOINTS for m in MODELS for metric in METRICS}
    if summary_keys != expected_summary:
        raise ValueError("Figure 7 summary key set does not reconcile")
    delta_keys = set(map(tuple, deltas[["endpoint_id", "contrast_id", "metric"]].to_numpy()))
    expected_deltas = {(e, c, metric) for e in ENDPOINTS for c in CONTRASTS for metric in METRICS}
    if delta_keys != expected_deltas:
        raise ValueError("Figure 7 delta key set does not reconcile")
    numeric = (
        "estimate", "ci_low", "ci_high", "n_patients", "n_events",
    )
    for column in numeric:
        values = pd.to_numeric(summary[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all():
            raise ValueError(f"Figure 7 summary {column} must be finite")
    for column in ("improvement_delta", "improvement_ci_low", "improvement_ci_high", "n_patients"):
        values = pd.to_numeric(deltas[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all():
            raise ValueError(f"Figure 7 deltas {column} must be finite")
    if not pd.to_numeric(deltas["n_patients"]).eq(153).all():
        raise ValueError("Figure 7 paired contrasts must use 153 patients")
    return summary, deltas


def render(summary_csv: Path = SUMMARY, deltas_csv: Path = DELTAS,
           output_pdf: Path = HERE / "fig7_marker7_transfer.pdf") -> None:
    summary, deltas = load_sources(summary_csv, deltas_csv)
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(13.2, 4.8), dpi=200)
    fig.patch.set_facecolor("#fcfcfb")

    selected = deltas[
        deltas["metric"].eq("c_index")
        & deltas["contrast_id"].isin((
            "GRADE_COMBINED_VS_GRADE", "FULL_COMBINED_VS_FULL", "M5_VS_M4"
        ))
    ].copy()
    selected["label"] = selected["contrast_id"].map({
        "GRADE_COMBINED_VS_GRADE": "Grade + image − grade",
        "FULL_COMBINED_VS_FULL": "Full + image − full",
        "M5_VS_M4": "M5 − M4",
    })
    y = np.arange(3)
    offsets = {"E04_reconstructed_with_tumor": -0.12, "E08_official_pfi": 0.12}
    colors = {"E04_reconstructed_with_tumor": BLUE, "E08_official_pfi": ORANGE}
    names = {"E04_reconstructed_with_tumor": "Reconstructed", "E08_official_pfi": "Official PFI"}
    for endpoint in ENDPOINTS:
        rows = selected[selected["endpoint_id"].eq(endpoint)].set_index("contrast_id")
        order = ("GRADE_COMBINED_VS_GRADE", "FULL_COMBINED_VS_FULL", "M5_VS_M4")
        estimates = rows.loc[list(order), "improvement_delta"].to_numpy(float)
        lows = rows.loc[list(order), "improvement_ci_low"].to_numpy(float)
        highs = rows.loc[list(order), "improvement_ci_high"].to_numpy(float)
        ax_a.errorbar(estimates, y + offsets[endpoint],
                      xerr=np.vstack((estimates - lows, highs - estimates)), fmt="o",
                      color=colors[endpoint], capsize=4, linewidth=1.7, label=names[endpoint])
    ax_a.axvline(0, color="#333333", linewidth=1, linestyle="--")
    ax_a.set_yticks(y, ("Grade + image − grade", "Full + image − full", "M5 − M4"))
    ax_a.set_xlabel("Paired improvement in C-index")
    ax_a.set_title("(a) Same-patient/same-draw paired contrasts", loc="left", fontweight="bold")
    ax_a.legend(frameon=False)
    ax_a.grid(axis="x", color=GRID)
    ax_a.spines[["top", "right", "left"]].set_visible(False)
    ax_a.tick_params(axis="y", length=0)

    hierarchy = summary[
        summary["endpoint_id"].eq("E04_reconstructed_with_tumor")
        & summary["metric"].eq("c_index")
        & summary["model_id"].str.startswith("H_M")
    ].copy()
    hierarchy["order"] = hierarchy["model_id"].str.extract(r"(\d)$").astype(int)
    hierarchy = hierarchy.sort_values("order")
    x = hierarchy["order"].to_numpy(int)
    estimates = hierarchy["estimate"].to_numpy(float)
    ax_b.plot(x, estimates, "-o", color=BLUE, markersize=7, linewidth=2)
    for xi, estimate in zip(x, estimates):
        ax_b.text(xi, estimate + 0.012, f"{estimate:.3f}", ha="center", fontsize=8)
    ax_b.set_xticks(x, [f"M{i}" for i in x])
    ax_b.set_ylabel("OOF C-index")
    ax_b.set_title("(b) Reconstructed-endpoint hierarchy", loc="left", fontweight="bold")
    ax_b.grid(axis="y", color=GRID)
    ax_b.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Marker 7: endpoint-conditioned paired survival analysis", fontweight="bold")
    fig.tight_layout()
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_pdf, bbox_inches="tight", facecolor=fig.get_facecolor(),
                metadata={"Creator": "fig7_marker7_transfer.py", "CreationDate": None,
                          "ModDate": None})
    fig.savefig(output_pdf.with_suffix(".png"), bbox_inches="tight", dpi=220,
                facecolor=fig.get_facecolor(),
                metadata={"Software": "fig7_marker7_transfer.py"})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--deltas", type=Path, default=DELTAS)
    parser.add_argument("--output", type=Path, default=HERE / "fig7_marker7_transfer.pdf")
    args = parser.parse_args()
    render(args.summary, args.deltas, args.output)
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
