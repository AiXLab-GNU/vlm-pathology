"""Render saved marker-7 time-dependent AUC and calibration diagnostics."""
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
DEFAULT_AUC_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_td_auc_curve.csv"
DEFAULT_CALIBRATION_SOURCE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_calibration_3y_5y.csv"
DEFAULT_METADATA_SOURCE = ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig5_marker7_transfer.csv"
DEFAULT_OUTPUT = Path(__file__).with_suffix(".pdf")
FIGURE_WIDTH_MM = DOUBLE_COLUMN_MM
AUC_COLUMNS = {"time_years", "td_auc", "mean_auc_1_to_5y"}
CALIBRATION_COLUMNS = {
    "horizon_years", "risk_group", "n", "events",
    "mean_predicted_event_probability", "km_observed_event_probability",
}
METADATA_COLUMNS = {
    "semantic_key", "endpoint_id", "endpoint_label", "result_type", "metric",
    "n", "n_events",
}
EXPECTED_ENDPOINT_ID = "E04_reconstructed_with_tumor"
EXPECTED_ENDPOINT_LABEL = "Reconstructed with-tumor endpoint"
EXPECTED_METADATA_KEY = f"{EXPECTED_ENDPOINT_ID}:frozen_risk:c_index"


def load_sources(
    source_paths: Sequence[Path],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Load the legacy curves and fail closed unless endpoint metadata reconciles."""
    if len(source_paths) != 3:
        raise ValueError(
            "Supplementary Figure 2 requires AUC, calibration and endpoint metadata CSVs"
        )
    auc = pd.read_csv(Path(source_paths[0]))
    calibration = pd.read_csv(Path(source_paths[1]))
    metadata = pd.read_csv(Path(source_paths[2]))
    missing_auc = AUC_COLUMNS - set(auc.columns)
    missing_calibration = CALIBRATION_COLUMNS - set(calibration.columns)
    if missing_auc:
        raise ValueError(f"Supplementary Figure 2 AUC missing columns: {sorted(missing_auc)}")
    if missing_calibration:
        raise ValueError(
            "Supplementary Figure 2 calibration missing columns: "
            f"{sorted(missing_calibration)}"
        )
    missing_metadata = METADATA_COLUMNS - set(metadata.columns)
    if missing_metadata:
        raise ValueError(
            "Supplementary Figure 2 endpoint metadata missing columns: "
            f"{sorted(missing_metadata)}"
        )
    if auc["time_years"].duplicated().any():
        raise ValueError("Supplementary Figure 2 time_years keys must be unique")
    if calibration.duplicated(["horizon_years", "risk_group"]).any():
        raise ValueError("Supplementary Figure 2 horizon/risk keys must be unique")
    if len(auc) != 17 or not np.allclose(
        np.sort(pd.to_numeric(auc["time_years"])), np.arange(1.0, 5.01, 0.25)
    ):
        raise ValueError("Supplementary Figure 2 requires the complete 1--5 year AUC grid")
    expected_calibration = {(horizon, group) for horizon in (3.0, 5.0) for group in range(5)}
    actual_calibration = set(map(tuple, calibration[["horizon_years", "risk_group"]].to_numpy()))
    if actual_calibration != expected_calibration:
        raise ValueError("Supplementary Figure 2 requires five groups at 3 and 5 years")
    for label, frame, columns in (
        ("AUC", auc, AUC_COLUMNS), ("calibration", calibration, CALIBRATION_COLUMNS)
    ):
        for column in columns:
            values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
            if not np.isfinite(values).all():
                raise ValueError(
                    f"Supplementary Figure 2 {label}.{column} contains missing/non-finite values"
                )
    if not auc["mean_auc_1_to_5y"].nunique() == 1:
        raise ValueError("Supplementary Figure 2 integrated mean AUC must be a saved constant")
    for column in ("td_auc", "mean_auc_1_to_5y"):
        if not pd.to_numeric(auc[column]).between(0, 1).all():
            raise ValueError(f"Supplementary Figure 2 {column} must lie in [0, 1]")
    for column in ("mean_predicted_event_probability", "km_observed_event_probability"):
        if not pd.to_numeric(calibration[column]).between(0, 1).all():
            raise ValueError(f"Supplementary Figure 2 {column} must lie in [0, 1]")
    if not pd.to_numeric(calibration["n"]).eq(54).all():
        raise ValueError("Supplementary Figure 2 calibration groups must each contain 54 patients")
    if (pd.to_numeric(calibration["events"]) > pd.to_numeric(calibration["n"])).any():
        raise ValueError("Supplementary Figure 2 events cannot exceed group size")
    endpoint_rows = metadata.loc[metadata["semantic_key"].eq(EXPECTED_METADATA_KEY)]
    if len(endpoint_rows) != 1:
        raise ValueError("Supplementary Figure 2 requires one reconstructed frozen-risk row")
    endpoint = endpoint_rows.iloc[0]
    if (
        endpoint["endpoint_id"] != EXPECTED_ENDPOINT_ID
        or endpoint["endpoint_label"] != EXPECTED_ENDPOINT_LABEL
        or endpoint["result_type"] != "frozen_risk_performance"
        or endpoint["metric"] != "c_index"
    ):
        raise ValueError("Supplementary Figure 2 endpoint identity does not reconcile")
    endpoint_n = int(pd.to_numeric(endpoint["n"], errors="raise"))
    endpoint_events = int(pd.to_numeric(endpoint["n_events"], errors="raise"))
    if (endpoint_n, endpoint_events) != (270, 57):
        raise ValueError("Supplementary Figure 2 endpoint frame must be n=270 with 57 events")
    calibration_totals = calibration.groupby("horizon_years", sort=True).agg(
        n=("n", "sum"), events=("events", "sum")
    )
    if not (
        calibration_totals["n"].eq(endpoint_n).all()
        and calibration_totals["events"].eq(endpoint_events).all()
    ):
        raise ValueError(
            "Supplementary Figure 2 calibration totals disagree with endpoint metadata"
        )
    return (
        auc.sort_values("time_years").reset_index(drop=True),
        calibration.sort_values(["horizon_years", "risk_group"]).reset_index(drop=True),
        endpoint,
    )


def render(source_paths: Sequence[Path], output_pdf: Path) -> None:
    """Render the saved time trajectory and horizon-specific calibration."""
    auc, calibration, endpoint = load_sources(source_paths)
    apply_journal_style()
    fig, (axis_a, axis_b) = plt.subplots(
        1, 2, figsize=figure_size(FIGURE_WIDTH_MM, 0.56), constrained_layout=True,
    )
    fig.suptitle(
        f"{endpoint['endpoint_label']} only "
        f"(n={int(endpoint['n'])}; {int(endpoint['n_events'])} events)\n"
        "not Official TCGA-CDR PFI",
        fontweight="bold",
        fontsize=PANEL_FONT_PT,
    )
    axis_a.plot(auc["time_years"], auc["td_auc"], marker="o", markersize=4.5,
                color=COLORBLIND_SAFE_PALETTE[0])
    axis_a.axhline(0.5, color="#6B7280", linestyle="--", label="Chance")
    mean_auc = float(auc["mean_auc_1_to_5y"].iloc[0])
    axis_a.axhline(mean_auc, color=COLORBLIND_SAFE_PALETTE[1], linestyle=":",
                   label=f"Integrated mean = {mean_auc:.3f}")
    axis_a.set_xlabel("Time (years)")
    axis_a.set_ylabel("Time-dependent AUROC")
    axis_a.set_ylim(0.45, 0.80)
    axis_a.set_title("a   Time-dependent discrimination", loc="left", fontweight="bold")
    axis_a.legend(frameon=False, loc="lower left")

    for horizon, color in ((3.0, COLORBLIND_SAFE_PALETTE[0]),
                           (5.0, COLORBLIND_SAFE_PALETTE[1])):
        rows = calibration[calibration.horizon_years == horizon]
        axis_b.plot(rows["mean_predicted_event_probability"],
                    rows["km_observed_event_probability"], marker="o", markersize=5.5,
                    color=color, label=f"{horizon:g} years")
        for row in rows.itertuples(index=False):
            axis_b.annotate(f"Q{int(row.risk_group) + 1}",
                            (row.mean_predicted_event_probability,
                             row.km_observed_event_probability),
                            xytext=(4, 4), textcoords="offset points")
    axis_b.plot([0, 1], [0, 1], color="#6B7280", linestyle="--", label="Ideal")
    axis_b.set_xlabel("Mean predicted event probability")
    axis_b.set_ylabel("Kaplan–Meier observed probability")
    axis_b.set_xlim(0, 1.03)
    axis_b.set_ylim(0, 1.03)
    axis_b.set_title("b   Calibration by risk quintile", loc="left", fontweight="bold")
    axis_b.legend(frameon=False, loc="upper left")
    for axis in (axis_a, axis_b):
        axis.grid(color="#E5E7EB")
        axis.spines[["top", "right"]].set_visible(False)
    save_vector_figure(fig, Path(output_pdf))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auc", type=Path, default=DEFAULT_AUC_SOURCE)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_SOURCE)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render((args.auc, args.calibration, args.metadata), args.output)


if __name__ == "__main__":
    main()
