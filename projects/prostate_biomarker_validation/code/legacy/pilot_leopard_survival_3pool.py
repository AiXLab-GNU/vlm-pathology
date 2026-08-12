"""LEOPARD 3-pool survival comparison -- docs/04_publication_strategy.md §7-2's single most
load-bearing planned result. Tests whether the qualification protocol (docs/10_protocol_freeze.md)
actually changes marker selection AND whether that selection matters clinically, not just
"does some marker correlate with recurrence."

Three evidence pools (LEOPARD-specific composition -- marker 3 is structurally unavailable,
no ERG-stained images exist for this H&E-only cohort, see pilot_leopard_marker_scores.py):
  (1) Naive pool         = {marker1, marker2, marker4, marker6}
  (2) Qualified pool     = {marker1, marker2, marker4}          (protocol_freeze.md §8)
  (3) All-candidate pool = {marker1, marker2, marker4, marker5, marker6}

IMPORTANT SCOPE CAVEAT (locked in 2026-07-31 after verifying the public LEOPARD data page
directly): the public training_labels.csv has NO clinical covariates (no grade/PSA/stage) --
confirmed by fetching the LEOPARD data page twice. So "incremental value over clinical
baseline" (docs/04's original criterion 3) cannot be tested with this data alone; every
comparison here is against a covariate-free null (intercept/baseline-hazard-only) model, i.e.
this is "outcome association" evidence, per the pre-registered fallback in docs/04 and
docs/10_protocol_freeze.md.

Also note (publication_strategy.md §7-2): the public LEOPARD training dataset carries a
publication embargo (results using it can't be published before the official LEOPARD
challenge + baseline papers) -- this script is for internal validation now; embargo status
must be re-confirmed with the organizers before any of these specific numbers go in a
submitted manuscript.

Metrics per pool, all from 5-fold CV (out-of-fold, never in-sample):
  - Harrell's C-index (concordance_index_censored)
  - Time-dependent AUROC at 5-year horizon (cumulative_dynamic_auc)
  - Integrated Brier score over [0, 10] years
  - Calibration slope (Cox regression of event ~ out-of-fold linear predictor; slope near 1
    = well calibrated)
  - Likelihood-ratio test vs a covariate-free null Cox model (in-sample, on the full cohort,
    standard practice for this kind of nested-model test -- same discipline as
    pilot_confounder_audit.py)
  - Decision-curve net benefit at the 5-year horizon (landmark analysis, patients censored
    before 5y excluded -- their 5-year status is genuinely unknown, noted as a limitation
    rather than imputed)

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_leopard_survival_3pool.py
"""
import os

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sksurv.metrics import concordance_index_censored, cumulative_dynamic_auc, integrated_brier_score
from sksurv.linear_model import CoxPHSurvivalAnalysis

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
SCORES_CSV = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/marker_scores.csv")
HORIZON_YEARS = 5.0
IBS_TIMES = np.linspace(0.5, 10, 50)
N_SPLITS = 5
SEED = 0

POOLS = {
    "naive":     ["marker1_gleason", "marker2_phenotype", "marker4_pten_loss", "marker6_ar_score"],
    "qualified": ["marker1_gleason", "marker2_phenotype", "marker4_pten_loss"],
    "all_candidate": ["marker1_gleason", "marker2_phenotype", "marker4_pten_loss",
                       "marker5_spop_mut", "marker6_ar_score"],
}


def to_structured(event, time):
    return np.array(list(zip(event.astype(bool), time)),
                     dtype=[("event", bool), ("time", float)])


def cv_predict_risk(X, event, time, n_splits=N_SPLITS, seed=SEED):
    """Out-of-fold linear predictor (log relative hazard) from CoxPHSurvivalAnalysis."""
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof_risk = np.full(len(X), np.nan)
    oof_surv_funcs = [None] * len(X)
    for tr, te in kf.split(X):
        scaler = StandardScaler().fit(X[tr])
        Xtr, Xte = scaler.transform(X[tr]), scaler.transform(X[te])
        y_tr = to_structured(event[tr], time[tr])
        model = CoxPHSurvivalAnalysis(alpha=0.1)
        model.fit(Xtr, y_tr)
        oof_risk[te] = model.predict(Xte)
        surv_fns = model.predict_survival_function(Xte)
        for local_i, global_i in enumerate(te):
            oof_surv_funcs[global_i] = surv_fns[local_i]
    return oof_risk, oof_surv_funcs


def evaluate_pool(name, features, df):
    print(f"\n{'='*90}\nPool: {name}  ({features})\n{'='*90}")
    X = df[features].values.astype(float)
    event = df["event"].values
    time = df["follow_up_years"].values
    y_struct = to_structured(event, time)

    oof_risk, oof_surv_funcs = cv_predict_risk(X, event, time)

    # 1. C-index (out-of-fold)
    c_index = concordance_index_censored(event.astype(bool), time, oof_risk)[0]

    # 2. time-dependent AUROC at HORIZON_YEARS (needs a survival-fn-derived risk score;
    #    use 1 - S(horizon) per patient, evaluated against the full-cohort structured array
    #    as the "training" distribution for the censoring-weight estimator, per sksurv convention)
    risk_at_horizon = np.array([1 - fn(HORIZON_YEARS) for fn in oof_surv_funcs])
    try:
        auc_t, mean_auc = cumulative_dynamic_auc(y_struct, y_struct, risk_at_horizon,
                                                   [HORIZON_YEARS])
        td_auc = auc_t[0]
    except ValueError as e:
        td_auc = float("nan")
        print(f"  [time-dependent AUROC failed: {e}]")

    # 3. Integrated Brier score
    surv_probs = np.array([[fn(t) for t in IBS_TIMES] for fn in oof_surv_funcs])
    try:
        ibs = integrated_brier_score(y_struct, y_struct, surv_probs, IBS_TIMES)
    except ValueError as e:
        ibs = float("nan")
        print(f"  [IBS failed: {e}]")

    # 4. Calibration slope: Cox regression of event~time on the single OOF linear predictor
    calib_df = pd.DataFrame({"lp": oof_risk, "time": time, "event": event})
    cph_calib = CoxPHFitter()
    cph_calib.fit(calib_df, duration_col="time", event_col="event")
    calib_slope = cph_calib.params_["lp"]

    # 5. Likelihood-ratio test vs covariate-free null (in-sample, full cohort, standard
    #    practice for this nested-model comparison -- same discipline as pilot_confounder_audit.py)
    full_df = df[features + ["follow_up_years", "event"]].copy()
    cph_full = CoxPHFitter()
    cph_full.fit(full_df, duration_col="follow_up_years", event_col="event")
    lr_stat = cph_full.log_likelihood_ratio_test().test_statistic
    lr_p = cph_full.log_likelihood_ratio_test().p_value

    # 6. Decision-curve net benefit at HORIZON_YEARS (landmark: drop censored-before-horizon)
    known = (time >= HORIZON_YEARS) | ((event == 1) & (time <= HORIZON_YEARS))
    y_horizon = ((event == 1) & (time <= HORIZON_YEARS))[known]
    risk_known = risk_at_horizon[known]
    n_dropped = (~known).sum()
    thresholds = np.linspace(0.02, 0.5, 25)
    net_benefits = []
    n = len(y_horizon)
    for pt in thresholds:
        pred_pos = risk_known >= pt
        tp = (pred_pos & y_horizon).sum()
        fp = (pred_pos & ~y_horizon).sum()
        nb = tp / n - fp / n * (pt / (1 - pt))
        net_benefits.append(nb)
    nb_at_10pct = np.interp(0.10, thresholds, net_benefits)

    print(f"  n={len(df)}, C-index(OOF)={c_index:.3f}, time-dep AUROC@{HORIZON_YEARS:.0f}y={td_auc:.3f}, "
          f"IBS={ibs:.4f}")
    print(f"  calibration slope={calib_slope:+.3f} (1.0 = perfect), "
          f"LRT vs null: chi2={lr_stat:.2f} p={lr_p:.4g}")
    print(f"  DCA: net benefit @ 10% threshold = {nb_at_10pct:+.4f} "
          f"(landmark n={n}, {n_dropped} censored-before-{HORIZON_YEARS:.0f}y dropped)")

    return dict(pool=name, n=len(df), c_index=c_index, td_auc=td_auc, ibs=ibs,
                calib_slope=calib_slope, lr_stat=lr_stat, lr_p=lr_p,
                nb_at_10pct=nb_at_10pct, thresholds=thresholds, net_benefits=net_benefits)


def main():
    df = pd.read_csv(SCORES_CSV)
    print(f"LEOPARD cohort: n={len(df)}, events={df['event'].sum()}, "
          f"median follow-up={df['follow_up_years'].median():.2f}y")

    results = {}
    for name, features in POOLS.items():
        results[name] = evaluate_pool(name, features, df)

    print(f"\n{'='*90}\nSUMMARY\n{'='*90}")
    print(f"{'pool':15s} {'n':>4s} {'C-index':>9s} {'td-AUROC':>9s} {'IBS':>8s} "
          f"{'calib':>8s} {'LRT p':>10s} {'NB@10%':>9s}")
    for name, r in results.items():
        print(f"{name:15s} {r['n']:4d} {r['c_index']:9.3f} {r['td_auc']:9.3f} {r['ibs']:8.4f} "
              f"{r['calib_slope']:8.3f} {r['lr_p']:10.4g} {r['nb_at_10pct']:9.4f}")

    pd.DataFrame([{k: v for k, v in r.items() if k not in ("thresholds", "net_benefits")}
                  for r in results.values()]).to_csv(
        os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/pool_comparison_summary.csv"), index=False)


if __name__ == "__main__":
    main()
