"""Benchmark our reconstructed TCGA-PRAD recurrence-style label against standard TCGA-CDR
endpoints (Tier-1 review item 1.2 -- asked twice by the reviewer, in different words: "benchmark
this label against standard TCGA endpoints (PFI, DFS/RFS) to quantify concordance and potential
misclassification").

Our label (resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv, built by build_bcr_labels.py) is derived from GDC
`follow_ups.disease_response == "wt-with tumor"` (a clinical-assessment-based construct), after
the previous label file in that directory turned out to have no traceable provenance (see
docs/03_experimental_results.md §6e). The standard comparison point is Liu et al. 2018's
TCGA-CDR endpoints (PFS, DFS), carried by cBioPortal study `prad_tcga_pan_can_atlas_2018`
(verified directly: PFS_STATUS/PFS_MONTHS populated for 494/494 patients, DFS_STATUS/DFS_MONTHS
for 334/494 -- DFS is only defined for patients with a curative-intent procedure and no prior
malignancy, per TCGA-CDR convention, hence the smaller n).

Three things, for the overlap with our embedded TCGA-PRAD cohort (270 patients):
  1. Event-status agreement: our GDC-follow_ups-derived event vs PFS_STATUS and vs DFS_STATUS
     (Cohen's kappa + confusion matrix).
  2. Time correlation: our follow_up_y vs PFS_MONTHS/DFS_MONTHS (Spearman rho), for patients
     where both are defined.
  3. Re-run marker 7's zero-shot external-validation test
     (pilot_tcga_prad_recurrence_external.py's core logic) using PFS and DFS DIRECTLY as the
     outcome instead of our reconstructed label -- if marker7_risk also predicts the standard
     TCGA-CDR endpoints well, that substantially strengthens the marker-7 result and directly
     answers the reviewer's label-quality concern. If it doesn't, that's an important, honestly
     reportable finding about how label-definition-specific the original C-index=0.673 result is.

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_label_benchmark.py
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.metrics import cohen_kappa_score, confusion_matrix, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored, cumulative_dynamic_auc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
LEOPARD_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
BCR_CSV = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv")
RECURRENCE_ONLY_CSV = os.path.join(
    ROOT, "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv")
PANCAN_JSON = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pancan_clinical.json")


def to_struct(e, t):
    return np.array(list(zip(e.astype(bool), t)), dtype=[("event", bool), ("time", float)])


def load_pancan_endpoints():
    data = json.load(open(PANCAN_JSON))
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    def parse_status(v):
        if v is None:
            return np.nan
        return float(str(v).split(":")[0])

    def parse_months(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return np.nan

    all_ids = set(by_attr.get("PFS_STATUS", {})) | set(by_attr.get("DFS_STATUS", {}))
    out = pd.DataFrame({"case_id": sorted(all_ids)})
    out["pfs_event"] = out["case_id"].map({k: parse_status(v) for k, v in by_attr["PFS_STATUS"].items()})
    out["pfs_months"] = out["case_id"].map({k: parse_months(v) for k, v in by_attr["PFS_MONTHS"].items()})
    out["dfs_event"] = out["case_id"].map({k: parse_status(v) for k, v in by_attr.get("DFS_STATUS", {}).items()})
    out["dfs_months"] = out["case_id"].map({k: parse_months(v) for k, v in by_attr.get("DFS_MONTHS", {}).items()})
    return out


def load_embedded_cohort():
    """270-patient overlap with the CONCH embedding cache, same patient-level mean-pooling as
    pilot_tcga_prad_recurrence_external.py."""
    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))
    df = pd.DataFrame(X)
    df["case_id"] = meta["case_id"].values
    patient_X = df.groupby("case_id").mean().values
    patient_ids = df.groupby("case_id").mean().index.values
    return patient_X, patient_ids


def concordance_report(name, our_event, other_event, mask_name="patients with both labels defined"):
    mask = ~(np.isnan(our_event) | np.isnan(other_event))
    n = mask.sum()
    if n < 5:
        print(f"  [skip] {name}: only {n} {mask_name}")
        return None
    o, x = our_event[mask].astype(int), other_event[mask].astype(int)
    agree = (o == x).mean()
    kappa = cohen_kappa_score(o, x)
    cm = confusion_matrix(o, x)
    print(f"  {name} (n={n}): agreement={agree:.3f}, Cohen's kappa={kappa:.3f}")
    print(f"    confusion matrix (rows=our event, cols={name}):\n{cm}")
    return dict(name=name, n=n, agreement=agree, kappa=kappa)


def time_correlation(name, our_time_y, other_time_m):
    mask = ~(np.isnan(our_time_y) | np.isnan(other_time_m))
    n = mask.sum()
    if n < 5:
        print(f"  [skip] {name}: only {n} patients with both times defined")
        return None
    rho, p = stats.spearmanr(our_time_y[mask] * 12.0, other_time_m[mask])
    print(f"  {name} (n={n}): Spearman rho={rho:+.3f}, p={p:.4g} "
          f"(our follow_up_y*12 vs {name} months)")
    return dict(name=name, n=n, rho=rho, p=p)


def zeroshot_marker7_on_outcome(Xt, ids_t, event_t, time_t_months, outcome_name):
    """LEOPARD-fitted PCA(8)+Cox risk score, applied zero-shot, scored against a DIRECT
    TCGA-CDR endpoint (PFS or DFS) instead of our reconstructed label."""
    mask = ~(np.isnan(event_t) | np.isnan(time_t_months)) & (time_t_months > 0)
    Xt, event_t, time_t_months = Xt[mask], event_t[mask].astype(bool), time_t_months[mask]
    time_t_y = time_t_months / 12.0
    n_events = event_t.sum()
    print(f"\n  Outcome = {outcome_name}: n={len(Xt)}, events={n_events}")
    if n_events < 5 or len(Xt) < 20:
        print(f"    [skip] too few events/patients")
        return None

    Xl = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    metal = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    sc = StandardScaler().fit(Xl)
    pca = PCA(n_components=8, random_state=0).fit(sc.transform(Xl))
    y_l = to_struct(metal["event"].values, metal["follow_up_years"].values)
    cox = CoxPHSurvivalAnalysis(alpha=1.0).fit(pca.transform(sc.transform(Xl)), y_l)

    risk = cox.predict(pca.transform(sc.transform(Xt)))
    c_index = concordance_index_censored(event_t, time_t_y, risk)[0]
    y_t = to_struct(event_t, time_t_y)
    surv_fns = cox.predict_survival_function(pca.transform(sc.transform(Xt)))
    risk_at_5y = np.array([1 - fn(5.0) for fn in surv_fns])
    try:
        auc_t, _ = cumulative_dynamic_auc(y_l, y_t, risk_at_5y, [5.0])
        td_auc = auc_t[0]
    except ValueError as e:
        td_auc = float("nan")
        print(f"    [td-AUROC failed: {e}]")
    print(f"    zero-shot LEOPARD->TCGA-PRAD({outcome_name}): C-index={c_index:.3f}  "
          f"td-AUROC@5y={td_auc:.3f}")
    landmark = {}
    for horizon in (3.0, 5.0):
        eligible = (event_t & (time_t_y <= horizon)) | (time_t_y >= horizon)
        label = event_t[eligible] & (time_t_y[eligible] <= horizon)
        if label.sum() >= 2 and (~label).sum() >= 2:
            landmark[f"auc_{int(horizon)}y"] = roc_auc_score(label, risk[eligible])
        else:
            landmark[f"auc_{int(horizon)}y"] = float("nan")
    censored = ~event_t
    censor_rho, censor_p = stats.spearmanr(risk[censored], time_t_y[censored])
    return dict(outcome=outcome_name, n=len(Xt), n_events=int(n_events),
                c_index=c_index, td_auc=td_auc, **landmark,
                censor_time_rho=censor_rho, censor_time_p=censor_p)


def main():
    bcr = pd.read_csv(BCR_CSV)
    recurrence_only = pd.read_csv(RECURRENCE_ONLY_CSV).rename(
        columns={"event": "recurrence_only_event", "follow_up_y": "recurrence_only_follow_up_y"})
    pancan = load_pancan_endpoints()
    Xt, ids_t = load_embedded_cohort()

    merged = pd.DataFrame({"case_id": ids_t}).merge(bcr, on="case_id", how="inner")
    merged = merged.merge(recurrence_only, on="case_id", how="left")
    merged = merged.merge(pancan, on="case_id", how="left")
    print(f"Embedded TCGA-PRAD cohort: n={len(merged)}, our-label events={merged['event'].sum()}")
    print(f"  PFS defined for {merged['pfs_event'].notna().sum()}/{len(merged)}")
    print(f"  DFS defined for {merged['dfs_event'].notna().sum()}/{len(merged)}")

    print(f"\n{'='*80}\n1. Event-status agreement: our label vs standard TCGA-CDR endpoints\n{'='*80}")
    agree_pfs = concordance_report("PFS_STATUS", merged["event"].values, merged["pfs_event"].values)
    agree_dfs = concordance_report("DFS_STATUS", merged["event"].values, merged["dfs_event"].values)

    print(f"\n{'='*80}\n2. Time correlation: our follow_up_y vs PFS/DFS months\n{'='*80}")
    time_pfs = time_correlation("PFS_MONTHS", merged["follow_up_y"].values, merged["pfs_months"].values)
    time_dfs = time_correlation("DFS_MONTHS", merged["follow_up_y"].values, merged["dfs_months"].values)

    print(f"\n{'='*80}\n3. Marker 7 zero-shot transfer, scored DIRECTLY against PFS/DFS\n{'='*80}")
    id_to_idx = {cid: i for i, cid in enumerate(ids_t)}
    idx = [id_to_idx[cid] for cid in merged["case_id"]]
    X_ordered = Xt[idx]

    r_pfs = zeroshot_marker7_on_outcome(X_ordered, merged["case_id"].values,
                                        merged["pfs_event"].values, merged["pfs_months"].values, "PFS")
    r_dfs = zeroshot_marker7_on_outcome(X_ordered, merged["case_id"].values,
                                        merged["dfs_event"].values, merged["dfs_months"].values, "DFS")
    r_recurrence_only = zeroshot_marker7_on_outcome(
        X_ordered, merged["case_id"].values,
        merged["recurrence_only_event"].values,
        merged["recurrence_only_follow_up_y"].values * 12.0,
        "recurrence_only_after_tumor_free")

    print(f"\n{'='*80}\nSUMMARY (compare to original: our-label zero-shot C-index=0.673)\n{'='*80}")
    rows = []
    for label, r in [("agreement_PFS", agree_pfs), ("agreement_DFS", agree_dfs),
                      ("time_corr_PFS", time_pfs), ("time_corr_DFS", time_dfs),
                      ("zeroshot_PFS", r_pfs), ("zeroshot_DFS", r_dfs),
                      ("zeroshot_recurrence_only", r_recurrence_only)]:
        if r is not None:
            print(f"  {label}: {r}")
            rows.append({"check": label, **r})
    pd.DataFrame(rows).to_csv(
        os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv"), index=False)
    print(f"\nsaved resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv")


if __name__ == "__main__":
    main()
