"""Render marker-7 discrimination/calibration from saved CSV source tables only."""
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
AUC_SOURCE = ROOT / "models/marker7_td_auc_curve.csv"
CALIBRATION_SOURCE = ROOT / "models/marker7_calibration_3y_5y.csv"


def load_sources(auc_csv: Path = AUC_SOURCE, calibration_csv: Path = CALIBRATION_SOURCE):
    auc = pd.read_csv(auc_csv)
    calibration = pd.read_csv(calibration_csv)
    if len(auc) != 17:
        raise ValueError(f"Figure 8 AUC source must contain exactly 17 rows, found {len(auc)}")
    if len(calibration) != 10:
        raise ValueError(
            f"Figure 8 calibration source must contain exactly 10 rows, found {len(calibration)}"
        )
    required_auc = {"time_years", "td_auc", "mean_auc_1_to_5y"}
    required_cal = {
        "horizon_years", "risk_group", "n", "events",
        "mean_predicted_event_probability", "km_observed_event_probability",
    }
    if not required_auc.issubset(auc.columns) or not required_cal.issubset(calibration.columns):
        raise ValueError("Figure 8 saved-source schema is incomplete")
    if auc["time_years"].duplicated().any():
        raise ValueError("Figure 8 AUC time keys must be unique")
    if calibration.duplicated(["horizon_years", "risk_group"]).any():
        raise ValueError("Figure 8 calibration keys must be unique")
    if set(pd.to_numeric(calibration["horizon_years"])) != {3.0, 5.0}:
        raise ValueError("Figure 8 calibration horizons must be 3 and 5 years")
    if calibration.groupby("horizon_years").size().to_dict() != {3.0: 5, 5.0: 5}:
        raise ValueError("Figure 8 requires five risk groups per horizon")
    for frame, columns in ((auc, required_auc), (calibration, required_cal)):
        for column in columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            if values.isna().any() or not np.isfinite(values).all():
                raise ValueError(f"Figure 8 {column} must be finite")
    return auc, calibration


def render(auc_csv: Path = AUC_SOURCE, calibration_csv: Path = CALIBRATION_SOURCE,
           output_pdf: Path = HERE / "fig8_marker7_survival_curves.pdf") -> None:
    auc, calibration = load_sources(auc_csv, calibration_csv)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    axes[0].plot(auc["time_years"], auc["td_auc"], marker="o", linewidth=1.8)
    axes[0].axhline(0.5, color="0.5", linestyle="--", linewidth=1)
    axes[0].set(xlabel="Time (years)", ylabel="Time-dependent AUROC",
                title="Marker 7: zero-shot discrimination", ylim=(0.45, 0.8))
    for horizon, part in calibration.groupby("horizon_years"):
        axes[1].plot(part["mean_predicted_event_probability"],
                     part["km_observed_event_probability"], marker="o",
                     label=f"{horizon:g} years")
    limit = 1.08 * max(calibration["mean_predicted_event_probability"].max(),
                       calibration["km_observed_event_probability"].max())
    axes[1].plot([0, limit], [0, limit], color="0.5", linestyle="--", linewidth=1)
    axes[1].set(xlabel="Mean predicted event probability", ylabel="Kaplan--Meier observed",
                title="Calibration by risk quintile", xlim=(0, limit), ylim=(0, limit))
    axes[1].legend(frameon=False)
    fig.tight_layout()
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_pdf, bbox_inches="tight",
                metadata={"Creator": "fig8_marker7_survival_curves.py", "CreationDate": None,
                          "ModDate": None})
    fig.savefig(output_pdf.with_suffix(".png"), dpi=220, bbox_inches="tight",
                metadata={"Software": "fig8_marker7_survival_curves.py"})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auc", type=Path, default=AUC_SOURCE)
    parser.add_argument("--calibration", type=Path, default=CALIBRATION_SOURCE)
    parser.add_argument("--output", type=Path, default=HERE / "fig8_marker7_survival_curves.pdf")
    args = parser.parse_args()
    render(args.auc, args.calibration, args.output)
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
