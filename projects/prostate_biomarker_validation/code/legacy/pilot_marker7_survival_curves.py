"""1--5 year td-AUROC and 3/5-year calibration for marker-7 zero-shot transfer."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import cumulative_dynamic_auc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_tcga_prad_recurrence_external import (  # noqa: E402
    LEOPARD_CACHE,
    load_tcga_patient_level,
    to_struct,
)


def main():
    X_tcga, event, follow_up, case_ids = load_tcga_patient_level()
    X_leopard = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    leopard_meta = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    scaler = StandardScaler().fit(X_leopard)
    pca = PCA(n_components=8, random_state=0).fit(scaler.transform(X_leopard))
    y_leopard = to_struct(leopard_meta["event"].to_numpy(),
                          leopard_meta["follow_up_years"].to_numpy())
    model = CoxPHSurvivalAnalysis(alpha=1.0).fit(
        pca.transform(scaler.transform(X_leopard)), y_leopard)
    tcga_features = pca.transform(scaler.transform(X_tcga))
    risk = model.predict(tcga_features)
    survival_functions = model.predict_survival_function(tcga_features)
    y_tcga = to_struct(event, follow_up)

    times = np.linspace(1.0, 5.0, 17)
    auc, mean_auc = cumulative_dynamic_auc(y_leopard, y_tcga, risk, times)
    auc_frame = pd.DataFrame({"time_years": times, "td_auc": auc})
    auc_frame["mean_auc_1_to_5y"] = mean_auc
    auc_frame.to_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_td_auc_curve.csv"), index=False)

    calibration_rows = []
    base = pd.DataFrame({"case_id": case_ids, "event": event, "follow_up_y": follow_up,
                         "risk": risk})
    for horizon in (3.0, 5.0):
        frame = base.copy()
        frame["predicted_event_probability"] = np.asarray(
            [1 - fn(horizon) for fn in survival_functions])
        frame["risk_group"] = pd.qcut(frame["predicted_event_probability"], 5,
                                       labels=False, duplicates="drop")
        for group, part in frame.groupby("risk_group"):
            km = KaplanMeierFitter().fit(part["follow_up_y"], part["event"])
            observed = 1 - float(km.predict(horizon))
            calibration_rows.append({
                "horizon_years": horizon, "risk_group": int(group), "n": len(part),
                "events": int(part["event"].sum()),
                "mean_predicted_event_probability": part["predicted_event_probability"].mean(),
                "km_observed_event_probability": observed,
            })
    calibration = pd.DataFrame(calibration_rows)
    calibration.to_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_calibration_3y_5y.csv"), index=False)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    axes[0].plot(times, auc, marker="o", linewidth=1.8)
    axes[0].axhline(0.5, color="0.5", linestyle="--", linewidth=1)
    axes[0].set(xlabel="Time (years)", ylabel="Time-dependent AUROC",
                title="Marker 7: zero-shot discrimination", ylim=(0.45, 0.8))
    for horizon, part in calibration.groupby("horizon_years"):
        axes[1].plot(part["mean_predicted_event_probability"],
                     part["km_observed_event_probability"], marker="o", label=f"{horizon:g} years")
    limit = max(calibration["mean_predicted_event_probability"].max(),
                calibration["km_observed_event_probability"].max()) * 1.08
    axes[1].plot([0, limit], [0, limit], color="0.5", linestyle="--", linewidth=1)
    axes[1].set(xlabel="Mean predicted event probability", ylabel="Kaplan--Meier observed",
                title="Calibration by risk quintile", xlim=(0, limit), ylim=(0, limit))
    axes[1].legend(frameon=False)
    fig.tight_layout()
    for extension in ("pdf", "png"):
        fig.savefig(os.path.join(ROOT, f"paper/figures/fig_marker7_survival_curves.{extension}"),
                    dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(auc_frame.to_string(index=False))
    print(calibration.to_string(index=False))


if __name__ == "__main__":
    main()
