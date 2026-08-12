"""Domain-shift diagnostic for the LEOPARD null result (2026-07-31): distinguishes "the
NADT/TCGA-PRAD-trained marker probes fail to transfer to LEOPARD" from "there's no
recurrence-relevant signal in these CONCH embeddings at all for this cohort." Unlike
pilot_leopard_marker_scores.py (zero-shot transfer of existing probes), this fits a NEW model
directly on LEOPARD's own embeddings against LEOPARD's own recurrence labels, in-cohort
5-fold CV -- this is a different, exploratory question from the original 3-pool qualification
design, not a replacement for it.

512-dim raw CONCH embeddings are far too high-dimensional to feed directly into a Cox model
with only 87 events (508 patients) -- standard rule of thumb wants ~10+ events per parameter,
so at most ~8 safely-supported parameters. PCA (fit on the train fold only, to avoid leakage)
reduces to a handful of components before a lightly-regularized Cox fit. Several component
counts are tried (not just one) to check whether any real, non-fragile signal exists -- same
discipline as pilot_confounder_audit.py's alpha sweep: a real effect should survive a
reasonable range of settings, a numerical fluke won't.

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_leopard_direct_recurrence.py
"""
import os

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored, cumulative_dynamic_auc

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
LEOPARD_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
HORIZON_YEARS = 5.0
N_SPLITS = 5
SEED = 0
N_COMPONENTS_GRID = [4, 8, 16, 32, 64]


def to_structured(event, time):
    return np.array(list(zip(event.astype(bool), time)), dtype=[("event", bool), ("time", float)])


def cv_c_index(X, event, time, n_components, seed=SEED):
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
    oof_risk = np.full(len(X), np.nan)
    oof_surv_funcs = [None] * len(X)
    for tr, te in kf.split(X):
        sc = StandardScaler().fit(X[tr])
        Xtr, Xte = sc.transform(X[tr]), sc.transform(X[te])
        pca = PCA(n_components=n_components, random_state=seed).fit(Xtr)
        Ztr, Zte = pca.transform(Xtr), pca.transform(Xte)
        y_tr = to_structured(event[tr], time[tr])
        model = CoxPHSurvivalAnalysis(alpha=1.0)
        model.fit(Ztr, y_tr)
        oof_risk[te] = model.predict(Zte)
        surv_fns = model.predict_survival_function(Zte)
        for local_i, global_i in enumerate(te):
            oof_surv_funcs[global_i] = surv_fns[local_i]
    return oof_risk, oof_surv_funcs


def main():
    X = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    event = meta["event"].values
    time = meta["follow_up_years"].values
    y_struct = to_structured(event, time)
    print(f"LEOPARD in-cohort direct-recurrence CV: n={len(X)}, events={event.sum()}")

    print(f"\n{'n_components':>13s} {'C-index(OOF)':>13s} {'td-AUROC@5y':>13s}")
    results = []
    for k in N_COMPONENTS_GRID:
        oof_risk, oof_surv_funcs = cv_c_index(X, event, time, k)
        c_index = concordance_index_censored(event.astype(bool), time, oof_risk)[0]
        risk_at_horizon = np.array([1 - fn(HORIZON_YEARS) for fn in oof_surv_funcs])
        try:
            auc_t, _ = cumulative_dynamic_auc(y_struct, y_struct, risk_at_horizon, [HORIZON_YEARS])
            td_auc = auc_t[0]
        except ValueError:
            td_auc = float("nan")
        print(f"{k:13d} {c_index:13.3f} {td_auc:13.3f}")
        results.append(dict(n_components=k, c_index=c_index, td_auc=td_auc))

    pd.DataFrame(results).to_csv(
        os.path.join(LEOPARD_CACHE, "direct_recurrence_pca_sweep.csv"), index=False)


if __name__ == "__main__":
    main()
