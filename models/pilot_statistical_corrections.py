"""Statistical rigor pass (2026-07-28) requested for the Scientific-Reports-track manuscript:
bootstrap 95% CIs + multiple-comparison (Benjamini-Hochberg FDR) correction across every
DISTINCT marker hypothesis tested against real ground truth in this project.

Scope decision (documented so it isn't re-litigated): the FDR family here is the 13 NOVEL
hypothesis tests (each a genuinely different clinical/molecular question tested with CONCH
embeddings against real ground truth) -- NOT the external-cohort re-tests (PANDA zero-shot,
TCGA-PRAD 3rd-institution transfer) or the Virchow cross-model replications, since those are
CONFIRMATORY re-tests of an already-tested hypothesis, not new comparisons that inflate
false-discovery risk the way testing 13 different candidate markers does.

The 13 tests (all patient-disjoint 5-fold GroupKFold, CONCH embeddings, reusing existing
caches -- no new GPU work):
  1. Marker (1) NADT H&E -> Gleason score
  2. Marker (2) NADT H&E -> Phenotype
  3. Marker (3) NADT ERG -> Gleason score
  4. Marker (4) TCGA-PRAD H&E -> PTEN loss
  5. Marker (5) TCGA-PRAD H&E -> SPOP mutation
  6. Marker (6) TCGA-PRAD H&E -> AR score
  7. TCGA-PRAD H&E -> TP53 mutation
  8. TCGA-PRAD H&E -> TP53 CNA loss
  9. TCGA-PRAD H&E -> RB1 CNA loss
  10. TCGA-PRAD H&E -> SPINK1 high
  11. TCGA-PRAD H&E -> ETV1 altered
  12. TCGA-PRAD H&E -> ETV4 altered
  13. TCGA-PRAD H&E -> TMPRSS2-ERG fusion status

Patient-level p-values are the ones entering the FDR correction (the more rigorous unit per
this project's own convention -- see memory project-vlm-pathology-status). Slide-level results
are reported alongside for completeness but not double-corrected (they're not independent of
the patient-level tests on the same data).

Run with the CONCH-only venv (fast -- CPU only, no embedding, just probe refits + bootstrap):
    HF_HOME=~/.cache/huggingface-jhkim models/.venv-conch/bin/python \
        models/pilot_statistical_corrections.py
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NADT_CACHE = os.path.join(ROOT, "models/nadt_conch_cache")
TCGA_CACHE = os.path.join(ROOT, "models/tcga_prad_conch_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "models/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")
N_BOOTSTRAP = 2000
SEED = 0


def load_tcga_meta():
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))
    by_attr = {}
    with open(CBIOPORTAL_SAMPLE_JSON) as f:
        clinical_data = json.load(f)
    for d in clinical_data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    meta["gleason_sum"] = meta["case_id"].map(by_attr["REVIEWED_GLEASON_SUM"]).astype(float)
    pten = meta["case_id"].map(by_attr["PTEN_CNA"])
    meta["pten_loss"] = pten.isin(["hetloss", "homdel"]).astype(float)
    meta.loc[pten.isna(), "pten_loss"] = np.nan
    meta["ar_score"] = meta["case_id"].map(by_attr["AR_SCORE"]).astype(float)
    meta["tp53_mut"] = meta["case_id"].map(by_attr["TP53_MUTATION"]).astype(float)
    tp53_cna = meta["case_id"].map(by_attr["TP53_CNA"])
    meta["tp53_cna_loss"] = tp53_cna.isin(["hetloss", "homdel"]).astype(float)
    meta.loc[tp53_cna.isna(), "tp53_cna_loss"] = np.nan
    rb1 = meta["case_id"].map(by_attr["RB1_CNA"])
    meta["rb1_cna_loss"] = rb1.isin(["hetloss", "homdel"]).astype(float)
    meta.loc[rb1.isna(), "rb1_cna_loss"] = np.nan
    meta["spink1_high"] = meta["case_id"].map(by_attr["SPINK1_HIGH"]).astype(float)
    etv1 = meta["case_id"].map(by_attr["ETV1_STATUS"])
    meta["etv1_altered"] = etv1.isin(["fusion", "high"]).astype(float)
    meta.loc[etv1.isna(), "etv1_altered"] = np.nan
    etv4 = meta["case_id"].map(by_attr["ETV4_STATUS"])
    meta["etv4_altered"] = etv4.isin(["fusion", "high"]).astype(float)
    meta.loc[etv4.isna(), "etv4_altered"] = np.nan
    meta["spop_mut"] = meta["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)
    return meta


def oof_predict(X, y, groups, task):
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        if task == "continuous":
            probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
            probe.fit(X[tr], y[tr])
            oof[te] = probe.predict(X[te])
        else:
            probe = make_pipeline(StandardScaler(),
                                   LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
            probe.fit(X[tr], y[tr])
            oof[te] = probe.predict_proba(X[te])[:, 1]
    return oof


def metric(pred, true, task):
    if task == "continuous":
        return stats.spearmanr(pred, true)[0]
    return roc_auc_score(true, pred)


def bootstrap_ci(pred, true, groups, task, n_boot=N_BOOTSTRAP, seed=SEED):
    """Patient-cluster bootstrap: resample PATIENTS with replacement (respects the
    non-independence of same-patient slides), rebuild slide-level arrays, recompute metric.
    Precomputes a group->indices lookup once (avoids an O(n) np.where scan per sampled group
    per iteration, which was the bottleneck for TCGA-PRAD-scale n)."""
    rng = np.random.default_rng(seed)
    unique_groups = np.unique(groups)
    idx_by_group = {g: np.where(groups == g)[0] for g in unique_groups}
    boot_vals = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        idx = np.concatenate([idx_by_group[g] for g in sampled])
        p, t = pred[idx], true[idx]
        if task == "binary" and (len(np.unique(t)) < 2):
            continue
        try:
            v = metric(p, t, task)
        except Exception:
            continue
        if not np.isnan(v):
            boot_vals.append(v)
    lo, hi = np.percentile(boot_vals, [2.5, 97.5])
    return lo, hi, len(boot_vals)


def patient_level(pred, true, groups):
    df = pd.DataFrame(dict(g=groups, pred=pred, true=true))
    pp = df.groupby("g").mean()
    return pp["pred"].values, pp["true"].values, pp.index.values


def run_test(name, X, y, groups, task, patient_task=None):
    """patient_task overrides how the PATIENT-LEVEL aggregate is scored. Default: same as
    `task`. Marker 2 (Phenotype) is a documented exception -- 17/39 NADT patients genuinely
    have BOTH benign and tumor slides, so "mean true label per patient" is a real fraction,
    not a rounding artifact, and the project's own original methodology
    (pilot_conch_nadt_phenotype.py) always scored the patient level as a continuous
    Spearman correlation (mean predicted prob vs mean true tumor fraction), never as a
    rounded-to-binary AUROC. Forcing AUROC there (an earlier version of this script did)
    produces a meaningless number because rounding a genuine fraction discards information
    the original convention was designed to keep."""
    patient_task = patient_task or task
    mask = ~np.isnan(y)
    X, y, groups = X[mask], y[mask], groups[mask]
    if task == "binary":
        y = y.astype(int)
        if y.sum() < 10 or (y == 0).sum() < 10:
            print(f"  [skip] {name}: too few pos/neg")
            return None

    oof = oof_predict(X, y, groups, task)

    slide_m = metric(oof, y, task)
    slide_p = (stats.spearmanr(oof, y)[1] if task == "continuous"
               else stats.mannwhitneyu(oof[y == 1], oof[y == 0], alternative="two-sided")[1])
    slide_lo, slide_hi, _ = bootstrap_ci(oof, y, groups, task)

    p_pred, p_true, p_groups = patient_level(oof, y, groups)
    if patient_task == "binary":
        p_true_bin = np.round(p_true).astype(int)
        if len(np.unique(p_true_bin)) < 2 or min((p_true_bin == 0).sum(), (p_true_bin == 1).sum()) < 5:
            patient_m = patient_p = patient_lo = patient_hi = np.nan
        else:
            patient_m = roc_auc_score(p_true_bin, p_pred)
            patient_p = stats.mannwhitneyu(p_pred[p_true_bin == 1], p_pred[p_true_bin == 0],
                                            alternative="two-sided")[1]
            patient_lo, patient_hi, _ = bootstrap_ci(p_pred, p_true_bin, p_groups, "binary")
    else:
        patient_m, patient_p = stats.spearmanr(p_pred, p_true)
        patient_lo, patient_hi, _ = bootstrap_ci(p_pred, p_true, p_groups, "continuous")

    return dict(name=name, n_slide=len(y), n_patient=len(p_groups), task=patient_task,
                slide_metric=slide_m, slide_p=slide_p, slide_ci=(slide_lo, slide_hi),
                patient_metric=patient_m, patient_p=patient_p, patient_ci=(patient_lo, patient_hi))


def bh_fdr(pvals):
    """Benjamini-Hochberg FDR correction, returns q-values in original order."""
    pvals = np.asarray(pvals)
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    out = np.empty(n)
    out[order] = q
    return out


def main():
    results = []

    # --- NADT-based tests (markers 1-3) ---
    X1 = np.load(os.path.join(NADT_CACHE, "X.npy"))
    m1 = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    results.append(run_test("① NADT H&E -> Gleason", X1, m1["gleason_total"].values,
                             m1["patient_id"].values, "continuous"))

    X2 = np.load(os.path.join(NADT_CACHE, "X_phenotype.npy"))
    m2 = pd.read_csv(os.path.join(NADT_CACHE, "meta_phenotype.csv"))
    results.append(run_test("② NADT H&E -> Phenotype", X2, m2["label"].values,
                             m2["patient_id"].values, "binary", patient_task="continuous"))

    X3 = np.load(os.path.join(NADT_CACHE, "X_ERG.npy"))
    m3 = pd.read_csv(os.path.join(NADT_CACHE, "meta_ERG.csv"))
    results.append(run_test("③ NADT ERG -> Gleason", X3, m3["gleason_total"].values,
                             m3["patient_id"].values, "continuous"))

    # --- TCGA-PRAD-based tests (marker 4/5/6 + extra candidates) ---
    X_tcga = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    meta_tcga = load_tcga_meta()
    groups_tcga = meta_tcga["case_id"].values

    tcga_tests = [
        ("④ TCGA-PRAD H&E -> PTEN loss", "pten_loss", "binary"),
        ("⑤ TCGA-PRAD H&E -> SPOP mutation", "spop_mut", "binary"),
        ("⑥ TCGA-PRAD H&E -> AR score", "ar_score", "continuous"),
        ("TCGA-PRAD H&E -> TP53 mutation", "tp53_mut", "binary"),
        ("TCGA-PRAD H&E -> TP53 CNA loss", "tp53_cna_loss", "binary"),
        ("TCGA-PRAD H&E -> RB1 CNA loss", "rb1_cna_loss", "binary"),
        ("TCGA-PRAD H&E -> SPINK1 high", "spink1_high", "binary"),
        ("TCGA-PRAD H&E -> ETV1 altered", "etv1_altered", "binary"),
        ("TCGA-PRAD H&E -> ETV4 altered", "etv4_altered", "binary"),
        ("TCGA-PRAD H&E -> ERG fusion status", "erg_fusion" if "erg_fusion" in meta_tcga.columns
         else None, "binary"),
    ]
    # erg_fusion comes from the manifest-based meta, not the cBioPortal JSON -- reload it
    manifest = pd.read_csv(os.path.join(ROOT, "opendataset/TCGA-PRAD/manifest.csv"))
    manifest = manifest[manifest["erg_status"].isin(["fusion", "none"])]
    erg_map = dict(zip(manifest["file_name"], (manifest["erg_status"] == "fusion").astype(float)))
    meta_tcga["erg_fusion"] = meta_tcga["file_name"].map(erg_map)

    for name, col, task in tcga_tests:
        y = meta_tcga[col].values
        r = run_test(name, X_tcga, y, groups_tcga, task)
        results.append(r)

    results = [r for r in results if r is not None]

    # --- BH-FDR correction across patient-level p-values ---
    patient_ps = [r["patient_p"] for r in results]
    valid_idx = [i for i, p in enumerate(patient_ps) if not np.isnan(p)]
    qvals = bh_fdr(np.array([patient_ps[i] for i in valid_idx]))
    for j, i in enumerate(valid_idx):
        results[i]["patient_q"] = qvals[j]
    for r in results:
        r.setdefault("patient_q", np.nan)

    print(f"\n{'='*110}")
    print(f"{'Test':<42} {'Metric':<8} {'Slide':<10} {'Slide 95% CI':<18} "
          f"{'Patient':<10} {'Patient p':<10} {'BH-q':<8}")
    print(f"{'='*110}")
    for r in results:
        metric_name = "rho" if r["task"] == "continuous" else "AUROC"
        slide_str = f"{r['slide_metric']:+.3f}" if r["task"] == "continuous" else f"{r['slide_metric']:.3f}"
        patient_str = (f"{r['patient_metric']:+.3f}" if r["task"] == "continuous"
                       else f"{r['patient_metric']:.3f}") if not np.isnan(r["patient_metric"]) else "n/a"
        ci_str = f"[{r['slide_ci'][0]:.3f},{r['slide_ci'][1]:.3f}]"
        p_str = f"{r['patient_p']:.4g}" if not np.isnan(r["patient_p"]) else "n/a"
        q_str = f"{r['patient_q']:.4g}" if not np.isnan(r["patient_q"]) else "n/a"
        print(f"{r['name']:<42} {metric_name:<8} {slide_str:<10} {ci_str:<18} "
              f"{patient_str:<10} {p_str:<10} {q_str:<8}")
    print(f"{'='*110}")

    reliability_tiers = {
        "①": "Externally transportable",
        "②": "Externally transportable",
        "③": "Internally supported, externally untested",
        "④": "Internally supported; multisite-stable within TCGA-PRAD",
        "⑤": "Unsupported/null",
        "⑥": "Context-sensitive",
    }

    def reliability_tier(name):
        return next((tier for prefix, tier in reliability_tiers.items() if name.startswith(prefix)),
                    "Not assigned (screening candidate)")

    df_out = pd.DataFrame([{
        "test": r["name"], "task": r["task"], "n_slide": r["n_slide"], "n_patient": r["n_patient"],
        "encoder": "CONCH", "validation_type": "patient-disjoint internal GroupKFold(5)",
        "reliability_tier": reliability_tier(r["name"]),
        "slide_metric": r["slide_metric"], "slide_p": r["slide_p"],
        "slide_ci_lo": r["slide_ci"][0], "slide_ci_hi": r["slide_ci"][1],
        "patient_metric": r["patient_metric"], "patient_p": r["patient_p"],
        "patient_ci_lo": r["patient_ci"][0], "patient_ci_hi": r["patient_ci"][1],
        "patient_q_BH_FDR": r["patient_q"],
    } for r in results])
    out_path = os.path.join(ROOT, "models/statistical_corrections_summary.csv")
    df_out.to_csv(out_path, index=False)
    print(f"\nsaved to {out_path}")

    n_sig_before = sum(1 for r in results if not np.isnan(r["patient_p"]) and r["patient_p"] < 0.05)
    n_sig_after = sum(1 for r in results if not np.isnan(r["patient_q"]) and r["patient_q"] < 0.05)
    print(f"\nSignificant at patient-level raw p<0.05: {n_sig_before}/{len(results)}")
    print(f"Significant at patient-level BH-FDR q<0.05: {n_sig_after}/{len(results)}")


if __name__ == "__main__":
    main()
