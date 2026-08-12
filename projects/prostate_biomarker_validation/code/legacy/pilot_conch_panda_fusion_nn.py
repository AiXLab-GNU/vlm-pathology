"""Re-test G-N6c's negative fusion result (NADT (1)+(2) learned combiner made things WORSE,
fixed 50:50 average only tied the single-marker baseline) at PANDA scale, to distinguish two
explanations that NADT's n=39 patients couldn't tell apart:
  H1: (1)+(2) genuinely lack exploitable synergy, regardless of combiner power.
  H2: the NADT combiner failed specifically because ~39 patients is too few to estimate fusion
      weights reliably (the G-N6c lesson) -- with PANDA's ~565-570 slides per institution, a
      learned combiner (even a small NN, not just linear RidgeCV) might now find real synergy.

Protocol: train marker (1)-style (RidgeCV, TUMOR-only slides, target=isup_grade) and marker
(2)-style (LogisticRegression, all slides, target=tumor-vs-benign) probes on ONE PANDA
institution, producing verdict features for both institutions; fuse those two verdicts via
(a) the fixed 50:50 z-scored average (G-N6c's fallback rule) and (b) a small MLP (2->8->1),
10-seed ensemble per the attention-MIL saga's lesson (never trust a single learned-combiner
run at this point in the project); evaluate Spearman rho against isup_grade on the FULLY
HELD-OUT other institution. Repeat with roles swapped (train=radboud/test=karolinska).

No patient grouping is used (PANDA's train.csv has no patient ID field) -- the institution
split itself is the leakage-proof boundary here, same as marker (1)/(2)'s PANDA validation.

Reuses resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/X_panda.npy (no re-embedding).

Run with the CONCH-only venv (fast -- no embedding, just probe fits + eval):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_panda_fusion_nn.py
"""
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
PANDA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache")
N_SEEDS = 10


def fit_marker1(X, isup, ridge_alphas=np.logspace(-2, 6, 25)):
    mask = isup >= 1
    probe = make_pipeline(StandardScaler(), RidgeCV(alphas=ridge_alphas))
    probe.fit(X[mask], isup[mask])
    return probe


def fit_marker2(X, isup):
    y = (isup >= 1).astype(int)
    probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    probe.fit(X, y)
    return probe


def fixed_fusion(v1_train, v2_train, v1_test, v2_test):
    m1, s1 = v1_train.mean(), v1_train.std()
    m2, s2 = v2_train.mean(), v2_train.std()
    z1 = (v1_test - m1) / s1
    z2 = (v2_test - m2) / s2
    return 0.5 * z1 + 0.5 * z2


def nn_fusion(v1_train, v2_train, y_train, v1_test, v2_test, isup_test, n_seeds=N_SEEDS):
    Xtr = np.stack([v1_train, v2_train], axis=1)
    Xte = np.stack([v1_test, v2_test], axis=1)
    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)
    preds = []
    for seed in range(n_seeds):
        mlp = MLPRegressor(hidden_layer_sizes=(8,), max_iter=2000, random_state=seed,
                            early_stopping=True, n_iter_no_change=20)
        mlp.fit(Xtr_s, y_train)
        preds.append(mlp.predict(Xte_s))
    preds = np.stack(preds)  # (n_seeds, n_test)
    per_seed_rho = [stats.spearmanr(p, isup_test)[0] for p in preds]
    return preds.mean(axis=0), np.array(per_seed_rho)


def run_direction(X, isup, providers, train_prov, test_prov):
    tr = providers == train_prov
    te = providers == test_prov

    m1 = fit_marker1(X[tr], isup[tr])
    m2 = fit_marker2(X[tr], isup[tr])

    v1_tr, v2_tr = m1.predict(X[tr]), m2.predict_proba(X[tr])[:, 1]
    v1_te, v2_te = m1.predict(X[te]), m2.predict_proba(X[te])[:, 1]
    isup_te = isup[te]

    rho1, p1 = stats.spearmanr(v1_te, isup_te)
    rho2, p2 = stats.spearmanr(v2_te, isup_te)
    fused_fixed = fixed_fusion(v1_tr, v2_tr, v1_te, v2_te)
    rho_fixed, p_fixed = stats.spearmanr(fused_fixed, isup_te)
    fused_nn_mean, per_seed_rho = nn_fusion(v1_tr, v2_tr, isup[tr], v1_te, v2_te, isup_te)
    rho_nn, p_nn = stats.spearmanr(fused_nn_mean, isup_te)

    print(f"\ntrain={train_prov} (n={tr.sum()}) -> test={test_prov} (n={te.sum()})")
    print(f"  marker(1) alone      : rho={rho1:+.3f}  p={p1:.4g}")
    print(f"  marker(2) alone      : rho={rho2:+.3f}  p={p2:.4g}")
    print(f"  fixed 50:50 fusion   : rho={rho_fixed:+.3f}  p={p_fixed:.4g}")
    print(f"  NN fusion (10-seed avg): rho={rho_nn:+.3f}  p={p_nn:.4g}")
    print(f"    per-seed rho: mean={per_seed_rho.mean():+.3f} std={per_seed_rho.std():.3f} "
          f"min={per_seed_rho.min():+.3f} max={per_seed_rho.max():+.3f}")
    return dict(train=train_prov, test=test_prov, rho1=rho1, rho2=rho2,
                rho_fixed=rho_fixed, rho_nn=rho_nn, nn_seed_mean=per_seed_rho.mean(),
                nn_seed_std=per_seed_rho.std())


def main():
    X = np.load(os.path.join(PANDA_CACHE, "X_panda.npy"))
    meta = pd.read_csv(os.path.join(PANDA_CACHE, "meta_panda.csv"))
    isup = meta["isup_grade"].values
    providers = meta["data_provider"].values
    print(f"n={len(isup)} slides, providers={np.unique(providers).tolist()}")

    results = []
    results.append(run_direction(X, isup, providers, "karolinska", "radboud"))
    results.append(run_direction(X, isup, providers, "radboud", "karolinska"))

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    df.to_csv(os.path.join(PANDA_CACHE, "panda_fusion_nn_results.csv"), index=False)


if __name__ == "__main__":
    main()
