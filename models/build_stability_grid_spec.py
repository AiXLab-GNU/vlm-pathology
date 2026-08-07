"""Freeze the minimum MR-v1 stability-grid cells and patient-disjoint fold assignments.

This script does not embed slides.  It creates the auditable design inputs that the smoke and
full GPU runs must consume, preventing cell-specific changes to seeds, scales, or folds.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "models"))

from pilot_confounder_audit import load_data  # noqa: E402
from pilot_marker7_confounder_audit import build_cohort  # noqa: E402

SEEDS = list(range(5))
TILE_COUNTS = [16, 32, 64]
SCALES = {"CONCH": [0.88, 1.76], "Virchow": [0.44, 1.76]}
MARKERS = [
    ("gleason", "NADT-Prostate", "continuous", "patient_spearman_rho"),
    ("phenotype", "NADT-Prostate", "binary", "patient_auroc"),
    ("pten", "TCGA-PRAD", "binary", "patient_auroc"),
    ("spop", "TCGA-PRAD", "binary", "patient_auroc"),
    ("ar", "TCGA-PRAD", "continuous", "patient_spearman_rho"),
    ("marker7", "LEOPARD-to-TCGA-PRAD", "survival", "patient_c_index"),
]


def build_spec() -> pd.DataFrame:
    rows = []
    for marker, cohort, outcome_type, metric in MARKERS:
        for encoder, scales in SCALES.items():
            for seed in SEEDS:
                for tiles in TILE_COUNTS:
                    for target_mpp in scales:
                        rows.append({
                            "cell_id": f"{marker}__{encoder.lower()}__s{seed}__t{tiles}__mpp{target_mpp:.2f}",
                            "marker": marker,
                            "canonical_cohort": cohort,
                            "outcome_type": outcome_type,
                            "primary_metric": metric,
                            "encoder": encoder,
                            "sampling_seed": seed,
                            "tiles_per_slide": tiles,
                            "target_mpp": target_mpp,
                            "fold_file": "models/stability_fold_assignments.csv",
                            "status": "pending",
                        })
    frame = pd.DataFrame(rows)
    assert len(frame) == 360
    assert frame["cell_id"].is_unique
    return frame


def assign_group_folds(marker: str, cohort: str, groups: np.ndarray) -> pd.DataFrame:
    groups = np.asarray(groups, dtype=str)
    unique_groups = pd.unique(groups)
    case_frame = pd.DataFrame({"case_id": unique_groups})
    # Equal one-row-per-patient input makes this a stable patient-level partition independent
    # of slide multiplicity and guarantees that no patient crosses folds.
    splitter = GroupKFold(n_splits=5)
    case_frame["fold"] = -1
    dummy = np.zeros(len(case_frame))
    for fold, (_, test) in enumerate(splitter.split(dummy[:, None], dummy, case_frame["case_id"])):
        case_frame.loc[test, "fold"] = fold
    case_frame.insert(0, "canonical_cohort", cohort)
    case_frame.insert(0, "marker", marker)
    assert (case_frame["fold"] >= 0).all()
    assert not case_frame.duplicated(["marker", "case_id"]).any()
    return case_frame


def build_folds() -> pd.DataFrame:
    parts = []
    nadt_grade = pd.read_csv(ROOT / "models/nadt_conch_cache/meta.csv")
    parts.append(assign_group_folds("gleason", "NADT-Prostate", nadt_grade["patient_id"].values))

    nadt_pheno = pd.read_csv(ROOT / "models/nadt_conch_cache/meta_phenotype.csv")
    parts.append(assign_group_folds("phenotype", "NADT-Prostate", nadt_pheno["patient_id"].values))

    _, tcga = load_data()
    tcga_specs = [("pten", "pten_loss"), ("ar", "ar_score")]
    for marker, label in tcga_specs:
        mask = tcga[label].notna()
        parts.append(assign_group_folds(marker, "TCGA-PRAD", tcga.loc[mask, "case_id"].values))

    spop = pd.read_csv(ROOT / "models/virchow_tcga_prad_cache/meta_spop.csv")
    spop = spop.loc[spop["spop_mut"].notna()]
    parts.append(assign_group_folds("spop", "TCGA-PRAD", spop["case_id"].values))

    marker7 = build_cohort()
    parts.append(assign_group_folds(
        "marker7", "LEOPARD-to-TCGA-PRAD", marker7["case_id"].values))
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    spec = build_spec()
    folds = build_folds()
    spec.to_csv(ROOT / "models/stability_grid_spec.csv", index=False)
    folds.to_csv(ROOT / "models/stability_fold_assignments.csv", index=False)
    print(f"saved {len(spec)} cells and {len(folds)} marker-patient fold assignments")
    print(folds.groupby('marker').agg(n_cases=('case_id', 'nunique'), n_folds=('fold', 'nunique')))


if __name__ == "__main__":
    main()
