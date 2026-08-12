"""Confounder audit for marker 7 (H&E -> direct recurrence risk), the one marker in the pool
that never went through this project's own grade-independence check (markers 4/6 did, via
pilot_confounder_audit.py; marker 7 is a post-hoc discovery from the LEOPARD session and was
never audited this way). Question: does marker 7's zero-shot risk score on TCGA-PRAD add
predictive value for the "wt-with tumor" recurrence-style outcome BEYOND Gleason grade alone,
or is it just another shadow of grade (which we already know predicts recurrence somewhat,
since higher-grade disease recurs more)?

Same design as pilot_confounder_audit.py, adapted to survival (Cox) instead of
logistic/linear regression, and same two-method discipline (parametric LRT + nonparametric
grade-stratified permutation) as pilot_confounder_permutation.py:
  - Clinical-only: CoxPH(event, time ~ grade)
  - Image-only: CoxPH(event, time ~ marker7_risk)  [zero-shot score, already computed]
  - Combined: CoxPH(event, time ~ grade + marker7_risk)
  - LRT: combined vs clinical-only (does marker7 add value beyond grade?)
  - Grade-stratified permutation: shuffle marker7_risk WITHIN grade strata, 2000 reps,
    compare observed partial-likelihood contribution to the null distribution.

Reuses existing artifacts, no new GPU work: TCGA-PRAD CONCH embeddings + grade (via
pilot_confounder_audit.load_data), marker 7's LEOPARD-fitted zero-shot risk scores (refit
inline, same recipe as pilot_tcga_prad_recurrence_external.py), and the GDC-rebuilt BCR-style
labels (resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv).

2026-08-03 EXTENSION (external review, Tier-1 item 1.1): the above audits only grade. The
reviewer asked whether marker 7 still adds value once PSA, T-stage, age, and surgical margin
status are also in the clinical model -- these are the standard covariates a real recurrence
model would use, and grade alone leaves residual confounding plausible. Extra covariates,
fetched via fetch_tcga_prad_clinical_extra.py and cached in
resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/*.json (verified directly, not assumed from field names, per
this project's convention -- see docstrings there):
  - age_at_index, ajcc_pathologic_t (GDC `cases` endpoint)
  - PREOPERATIVE_PSA, RESIDUAL_TUMOR (cBioPortal `prad_tcga_pub`, patient-level clinical data --
    confirmed these are NOT in the sample-level clinical JSON already used elsewhere in this
    project, which carries only molecular/genomic attributes)
T-stage is categorical with substages (T1-T4, a/b/c) -- simplified to major stage only (1-4;
when a patient has >1 GDC diagnosis record, the more advanced of the two is kept, affecting 9/500
patients) and noted as a simplification. Margin status (RESIDUAL_TUMOR: R0/R1/R2/RX) is
collapsed to a binary margin_positive = R1 or R2 (RX/missing -> NaN, i.e. unknown margin is
treated as missing, not negative). Any covariate whose missingness would drop the usable cohort
below a reasonable size is flagged and reported, not silently dropped from the writeup.

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_confounder_audit.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_confounder_audit import load_data as load_tcga_grade_data  # noqa: E402

TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
LEOPARD_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
BCR_CSV = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv")
CLINICAL_EXTRA_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra")
N_PERM = 2000
SEED = 0


def to_struct(e, t):
    return np.array(list(zip(e.astype(bool), t)), dtype=[("event", bool), ("time", float)])


def build_cohort():
    # marker 7 zero-shot risk score (LEOPARD-fitted PCA(8)+Cox, applied to TCGA-PRAD)
    X_tcga_full, meta_grade = load_tcga_grade_data()  # slide-level, has gleason_sum
    Xl = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    metal = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    sc = StandardScaler().fit(Xl)
    pca = PCA(n_components=8, random_state=SEED).fit(sc.transform(Xl))
    y_l = to_struct(metal["event"].values, metal["follow_up_years"].values)
    cox7 = CoxPHSurvivalAnalysis(alpha=1.0).fit(pca.transform(sc.transform(Xl)), y_l)
    slide_risk7 = cox7.predict(pca.transform(sc.transform(X_tcga_full)))

    meta_grade = meta_grade.copy()
    meta_grade["marker7_risk"] = slide_risk7

    # patient-level aggregation (mean over slides), matching pilot_tcga_prad_recurrence_external.py
    patient_df = meta_grade.groupby("case_id").agg(
        gleason_sum=("gleason_sum", "mean"), marker7_risk=("marker7_risk", "mean")).reset_index()

    bcr = pd.read_csv(BCR_CSV)
    cohort = patient_df.merge(bcr, on="case_id", how="inner")
    cohort = cohort.dropna(subset=["gleason_sum", "marker7_risk", "event", "follow_up_y"])
    return cohort


def load_extra_covariates():
    """age, T-stage (ordinal major stage 1-4), PSA, margin_positive -- keyed by case_id
    (== GDC submitter_id)."""
    gdc = json.load(open(os.path.join(CLINICAL_EXTRA_DIR, "gdc_tstage_age.json")))["data"]["hits"]
    t_stage_map, age_map = {}, {}
    t_rank = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}
    for h in gdc:
        cid = h["submitter_id"]
        age_map[cid] = h.get("demographic", {}).get("age_at_index", np.nan)
        diags = h.get("diagnoses", [])
        stages = []
        for d in diags:
            t = d.get("ajcc_pathologic_t")
            if t:
                major = t[:2]  # "T2c" -> "T2", "T3" -> "T3"
                if major in t_rank:
                    stages.append(t_rank[major])
        t_stage_map[cid] = max(stages) if stages else np.nan

    cbio = json.load(open(os.path.join(CLINICAL_EXTRA_DIR, "prad_pub_patient_clinical.json")))
    by_attr = {}
    for d in cbio:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]
    psa_raw = by_attr.get("PREOPERATIVE_PSA", {})
    margin_raw = by_attr.get("RESIDUAL_TUMOR", {})

    def to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return np.nan

    psa_map = {k: to_float(v) for k, v in psa_raw.items()}
    margin_map = {k: (1.0 if v in ("R1", "R2") else (0.0 if v == "R0" else np.nan))
                  for k, v in margin_raw.items()}

    all_ids = set(age_map) | set(t_stage_map) | set(psa_map) | set(margin_map)
    out = pd.DataFrame({"case_id": sorted(all_ids)})
    out["age"] = out["case_id"].map(age_map)
    out["t_stage"] = out["case_id"].map(t_stage_map)
    out["psa"] = out["case_id"].map(psa_map)
    out["margin_positive"] = out["case_id"].map(margin_map)
    return out


def extended_confounder_audit(cohort):
    """Fully-adjusted clinical model: grade + PSA + T-stage + age + margin, vs image-only,
    vs combined -- same LRT + grade-stratified-permutation structure as the grade-only audit
    above, but against a richer clinical baseline (Tier-1 review item 1.1)."""
    extra = load_extra_covariates()
    df = cohort.merge(extra, on="case_id", how="left")

    covariates = ["age", "t_stage", "psa", "margin_positive"]
    print(f"\n{'='*80}\nExtended clinical covariate missingness (n={len(df)} marker-7 cohort "
          f"patients)\n{'='*80}")
    for c in covariates:
        n_missing = df[c].isna().sum()
        print(f"  {c}: {n_missing}/{len(df)} missing ({100*n_missing/len(df):.0f}%)")

    complete = df.dropna(subset=["gleason_sum", "marker7_risk", "event", "follow_up_y"] + covariates)
    n_dropped = len(df) - len(complete)
    print(f"\nComplete-case cohort (all covariates present): n={len(complete)} "
          f"(dropped {n_dropped}/{len(df)}, mostly driven by PSA missingness -- PREOPERATIVE_PSA "
          f"is only recorded for {len(df) - df['psa'].isna().sum()}/{len(df)} of this cohort in "
          f"cBioPortal prad_tcga_pub)")
    if len(complete) < 60:
        print("  [WARNING] complete-case n is small -- report point estimates with wide CIs, "
              "not as a replacement for the grade-only audit above.")

    clinical_cols = ["gleason_sum"] + covariates
    print(f"\n{'='*80}\nFully-adjusted clinical model: grade+age+T-stage+PSA+margin "
          f"vs (that + marker7_risk)\n{'='*80}")
    lr_stat, p, m0, m1 = lrt_cox(complete, clinical_cols, clinical_cols + ["marker7_risk"],
                                  "follow_up_y", "event")
    print("Fully-adjusted clinical-only model:")
    print(m0.summary[["coef", "exp(coef)", "p"]])
    print("\nFully-adjusted clinical + marker7_risk model:")
    print(m1.summary[["coef", "exp(coef)", "p"]])
    print(f"\nLRT (marker7_risk beyond full clinical model): chi2={lr_stat:.3f}  p={p:.4g}")
    print(f"clinical-only (fully adjusted) concordance: {m0.concordance_index_:.3f}")
    print(f"combined (fully adjusted + marker7_risk) concordance: {m1.concordance_index_:.3f}")

    print(f"\n{'='*80}\nGrade-stratified permutation test against the fully-adjusted clinical "
          f"model (N={N_PERM})\n{'='*80}")
    rng = np.random.default_rng(SEED)
    grade = complete["gleason_sum"].values
    risk = complete["marker7_risk"].values
    strata = np.round(grade).astype(int)

    def combined_lrt_stat(risk_col):
        d = complete.copy()
        d["marker7_risk"] = risk_col
        _, _, mm0, mm1 = lrt_cox(d, clinical_cols, clinical_cols + ["marker7_risk"],
                                  "follow_up_y", "event")
        return 2 * (mm1.log_likelihood_ - mm0.log_likelihood_)

    observed = combined_lrt_stat(risk)
    null_stats = np.empty(N_PERM)
    for k in range(N_PERM):
        risk_perm = risk.copy()
        for s in np.unique(strata):
            idx = np.where(strata == s)[0]
            if len(idx) > 1:
                risk_perm[idx] = rng.permutation(risk[idx])
        try:
            null_stats[k] = combined_lrt_stat(risk_perm)
        except Exception:
            null_stats[k] = 0.0
    p_perm = (1 + np.sum(null_stats >= observed)) / (1 + N_PERM)
    print(f"observed LRT stat={observed:.3f}, null mean={null_stats.mean():.3f}, "
          f"null sd={null_stats.std():.3f}")
    print(f"permutation p (one-sided) = {p_perm:.4g}")

    return dict(n_complete=len(complete), n_dropped=n_dropped, lrt_chi2=lr_stat, lrt_p=p,
                perm_p=p_perm, hr_marker7=float(np.exp(m1.params_["marker7_risk"])),
                c_clinical_full=m0.concordance_index_, c_combined_full=m1.concordance_index_)


def lrt_cox(df, cols_null, cols_full, duration_col, event_col):
    m0 = CoxPHFitter().fit(df[cols_null + [duration_col, event_col]], duration_col, event_col)
    m1 = CoxPHFitter().fit(df[cols_full + [duration_col, event_col]], duration_col, event_col)
    lr_stat = 2 * (m1.log_likelihood_ - m0.log_likelihood_)
    df_diff = len(cols_full) - len(cols_null)
    p = stats.chi2.sf(lr_stat, df=df_diff)
    return lr_stat, p, m0, m1


def permutation_test(cohort, n_perm=N_PERM, seed=SEED):
    """Grade-stratified permutation: shuffle marker7_risk within Gleason-sum strata, refit the
    combined Cox model each time, compare the marker7 coefficient's partial LRT contribution."""
    rng = np.random.default_rng(seed)
    grade = cohort["gleason_sum"].values
    risk = cohort["marker7_risk"].values
    event = cohort["event"].values
    time = cohort["follow_up_y"].values

    def combined_lrt_stat(risk_col):
        df = pd.DataFrame({"gleason_sum": grade, "marker7_risk": risk_col,
                            "time": time, "event": event})
        _, _, m0, m1 = lrt_cox(df, ["gleason_sum"], ["gleason_sum", "marker7_risk"], "time", "event")
        return 2 * (m1.log_likelihood_ - m0.log_likelihood_)

    observed = combined_lrt_stat(risk)

    # round grade to nearest integer for stratification (continuous patient-mean grade)
    strata = np.round(grade).astype(int)
    null_stats = np.empty(n_perm)
    for k in range(n_perm):
        risk_perm = risk.copy()
        for s in np.unique(strata):
            idx = np.where(strata == s)[0]
            if len(idx) > 1:
                risk_perm[idx] = rng.permutation(risk[idx])
        try:
            null_stats[k] = combined_lrt_stat(risk_perm)
        except Exception:
            null_stats[k] = 0.0

    p = (1 + np.sum(null_stats >= observed)) / (1 + n_perm)
    return observed, null_stats, p


def main():
    cohort = build_cohort()
    print(f"n={len(cohort)} patients, events={cohort['event'].sum()}")

    print(f"\n{'='*80}\nLikelihood-ratio test: does marker7_risk add value beyond grade?\n{'='*80}")
    lr_stat, p, m0, m1 = lrt_cox(cohort, ["gleason_sum"], ["gleason_sum", "marker7_risk"],
                                  "follow_up_y", "event")
    print("Clinical-only (grade) model:")
    print(m0.summary[["coef", "p"]])
    print("\nCombined (grade + marker7_risk) model:")
    print(m1.summary[["coef", "p"]])
    print(f"\nLRT: chi2={lr_stat:.3f}  p={p:.4g}")

    print(f"\n{'='*80}\nImage-only (marker7_risk alone) model\n{'='*80}")
    m_img = CoxPHFitter().fit(cohort[["marker7_risk", "follow_up_y", "event"]],
                               "follow_up_y", "event")
    print(m_img.summary[["coef", "p"]])
    print(f"image-only concordance: {m_img.concordance_index_:.3f}")
    print(f"clinical-only concordance: {m0.concordance_index_:.3f}")
    print(f"combined concordance: {m1.concordance_index_:.3f}")

    print(f"\n{'='*80}\nGrade-stratified permutation test (N={N_PERM})\n{'='*80}")
    observed, null_stats, p_perm = permutation_test(cohort)
    print(f"observed LRT stat={observed:.3f}, null mean={null_stats.mean():.3f}, "
          f"null sd={null_stats.std():.3f}")
    print(f"permutation p (one-sided) = {p_perm:.4g}")

    print(f"\n{'#'*80}\n# EXTENDED: fully-adjusted clinical model (grade+age+T-stage+PSA+margin)\n{'#'*80}")
    ext = extended_confounder_audit(cohort)
    pd.DataFrame([ext]).to_csv(
        os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_extended_confounder_summary.csv"), index=False)
    print(f"\nsaved resources/projects/prostate_biomarker_validation/model_workspace/marker7_extended_confounder_summary.csv")


if __name__ == "__main__":
    main()
