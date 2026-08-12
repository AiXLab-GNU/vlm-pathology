"""Builds the stratified SICAPv2 test set for the formal VLM hallucination benchmark
(docs/05_vlm_benchmark_task_prompt.md). Samples ONLY from SICAPv2's own slide-disjoint
Test split (partition/Test/Test.xlsx) -- never Train, since this project's CONCH probes
were fit on Train (see pilot_conch_sicap_diagnostic.py) and the VLM benchmark needs to
stay a genuinely independent held-out set.

Strata (5): NC, G3, G4 non-cribriform (G4=1,G4C=0), G4 cribriform (G4C=1), G5.
Two output sizes:
  - pilot  (n=10, 2/stratum): quick/cheap sanity check before spending on the full run.
  - full   (n=75, 15/stratum): the actual benchmark set.
Plus a disjoint in-context exemplar pool (3/stratum, drawn from Test but never overlapping
either evaluation set) for the in-context-learning condition (task battery item 4).

Run:
    .venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/vlm_benchmark_testset.py   (or any python with pandas/openpyxl)
"""
import os
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SICAP_ROOT = os.path.join(REPO_ROOT, "opendataset", "SICAPv2", "SICAPv2")
IMAGES_DIR = os.path.join(SICAP_ROOT, "images")
OUT_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "vlm_benchmark_cache")

SEED = 20260729
N_PER_STRATUM_PILOT = 2
N_PER_STRATUM_FULL = 15
N_PER_STRATUM_INCONTEXT = 3

STRATA = ["NC", "G3", "G4_noncrib", "G4_crib", "G5"]
SEVERITY_RANK = {"NC": 0, "G3": 1, "G4_noncrib": 2, "G4_crib": 2, "G5": 3}


def load_test_split():
    df = pd.read_excel(os.path.join(SICAP_ROOT, "partition", "Test", "Test.xlsx"))
    def label(row):
        if row["NC"] == 1:
            return "NC"
        if row["G3"] == 1:
            return "G3"
        if row["G4"] == 1 and row["G4C"] == 1:
            return "G4_crib"
        if row["G4"] == 1 and row["G4C"] == 0:
            return "G4_noncrib"
        if row["G5"] == 1:
            return "G5"
        raise ValueError(f"unlabeled row: {row}")
    df = df.copy()
    df["stratum"] = df.apply(label, axis=1)
    df["path"] = df["image_name"].apply(lambda n: os.path.join(IMAGES_DIR, n))
    missing = df[~df["path"].apply(os.path.exists)]
    if len(missing):
        raise FileNotFoundError(f"{len(missing)} image files listed in Test.xlsx are missing on disk, e.g. {missing.iloc[0]['path']}")
    df["severity_rank"] = df["stratum"].map(SEVERITY_RANK)
    return df


def stratified_sample(df, n_per_stratum, exclude_names, rng_seed):
    picked = []
    for s in STRATA:
        pool = df[(df["stratum"] == s) & (~df["image_name"].isin(exclude_names))]
        if len(pool) < n_per_stratum:
            raise ValueError(f"stratum {s} has only {len(pool)} candidates, need {n_per_stratum}")
        picked.append(pool.sample(n=n_per_stratum, random_state=rng_seed))
    return pd.concat(picked, ignore_index=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_test_split()
    print("Test-split stratum counts:")
    print(df["stratum"].value_counts())

    # In-context exemplar pool first (reserved, excluded from both eval sets).
    incontext = stratified_sample(df, N_PER_STRATUM_INCONTEXT, exclude_names=set(), rng_seed=SEED)
    incontext_path = os.path.join(OUT_DIR, "incontext_exemplars.csv")
    incontext.to_csv(incontext_path, index=False)
    print(f"in-context exemplar pool: {len(incontext)} -> {incontext_path}")

    excl = set(incontext["image_name"])

    full = stratified_sample(df, N_PER_STRATUM_FULL, exclude_names=excl, rng_seed=SEED + 1)
    full_path = os.path.join(OUT_DIR, "testset_full.csv")
    full.to_csv(full_path, index=False)
    print(f"full eval set: {len(full)} -> {full_path}")

    # Pilot = first N_PER_STRATUM_PILOT rows per stratum from the full set (deterministic subset,
    # not an extra independent draw), so pilot results are directly a subset of the full run.
    pilot = full.groupby("stratum", group_keys=False).head(N_PER_STRATUM_PILOT).reset_index(drop=True)
    pilot_path = os.path.join(OUT_DIR, "testset_pilot.csv")
    pilot.to_csv(pilot_path, index=False)
    print(f"pilot eval set: {len(pilot)} -> {pilot_path}")

    print("\nFull-set stratum counts:\n", full["stratum"].value_counts())
    print("\nPilot-set stratum counts:\n", pilot["stratum"].value_counts())


if __name__ == "__main__":
    main()
