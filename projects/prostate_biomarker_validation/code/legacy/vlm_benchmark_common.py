"""Shared task battery, prompts, and hallucination rubric for the formal VLM hallucination
benchmark (docs/05_vlm_benchmark_task_prompt.md). Each of the 4 per-model scripts
(pilot_vlm_benchmark_{gpt4o,claude,quilt,llavamed}.py) imports this module so the task
definitions, prompts, and scoring rubric are IDENTICAL across models -- the whole point of
a formal benchmark vs. the earlier ad hoc Quilt-LLaVA-only pilots.

All ground-truth labels come from resources/data/shared/opendataset/SICAPv2/SICAPv2 (real pathologist Gleason
grade + patch-level cribriform flag), never our own proxies. See vlm_benchmark_testset.py
for how the 75-image full set / 10-image pilot set / 15-image in-context exemplar pool are
constructed (stratified, slide-disjoint SICAPv2 Test split only).
"""
import itertools
import os
import re

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "vlm_benchmark_cache")

STRATUM_DESC = {
    "NC": "normal / non-cancerous prostate tissue",
    "G3": "Gleason pattern 3 (well-differentiated glands)",
    "G4_noncrib": "Gleason pattern 4, non-cribriform (fused/poorly-formed glands)",
    "G4_crib": "Gleason pattern 4, cribriform (sieve-like gland clusters)",
    "G5": "Gleason pattern 5 (no gland formation)",
}
SEVERITY_RANK = {"NC": 0, "G3": 1, "G4_noncrib": 2, "G4_crib": 2, "G5": 3}


def load_set(name):
    """name in {'pilot', 'full', 'incontext'} -> DataFrame with image_name, path, stratum, severity_rank."""
    fname = {"pilot": "testset_pilot.csv", "full": "testset_full.csv",
             "incontext": "incontext_exemplars.csv"}[name]
    df = pd.read_csv(os.path.join(CACHE_DIR, fname))
    return df


# ---------------------------------------------------------------------------
# Task 1: absolute severity scoring (1-10)
# ---------------------------------------------------------------------------
TASK1_PROMPT = (
    "You are shown a single H&E-stained histopathology patch from a prostate needle biopsy. "
    "On a scale of 1 to 10 (1 = definitely benign/normal, 10 = most severe/aggressive cancer "
    "you could imagine), rate the severity of what you see in this patch. "
    "Respond with ONLY a single integer from 1 to 10, nothing else."
)

def parse_score_1_10(text):
    """Extract the first integer 1-10 in the response; None if not parseable."""
    m = re.search(r"\b(10|[1-9])\b", text)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Task 2: open-ended diagnostic query -> hallucination rubric
# ---------------------------------------------------------------------------
TASK2_PROMPT = (
    "You are shown a single H&E-stained histopathology patch from a prostate needle biopsy. "
    "What do you see in this image, and what is your diagnosis? Please describe the findings "
    "in a few sentences."
)

# Keyword rubric: terms that are NOT verifiable from a single SICAPv2 H&E patch (no IHC/molecular
# stain was performed, no clinical chart was provided, no other organ is present) and were not
# asked about. A hit means the model asserted something ungrounded in the actual evidence given.
# This mirrors the earlier Quilt-LLaVA pilot's failure mode (hallucinated neuroendocrine tumor /
# synaptophysin / chromogranin -- see memory feedback-vlm-excluded).
HALLUCINATION_KEYWORDS = [
    # immunohistochemistry / molecular markers never performed on these plain H&E patches
    "synaptophysin", "chromogranin", "immunohistochemistry", "ihc stain", "ki-67", "ki67",
    "psa ", "p63", "ck5", "cytokeratin", "ar stain", "androgen receptor stain", "erg stain",
    "pten", "tmprss2", "fusion status", "molecular test", "genomic", "biomarker positive",
    "biomarker negative",
    # specific unrelated diagnoses / tissue types not derivable from a prostate H&E patch
    "neuroendocrine tumor", "neuroendocrine carcinoma", "small cell carcinoma",
    "basal cell carcinoma", "squamous cell carcinoma", "melanoma", "lymphoma", "sarcoma",
    "breast", "lung", "colon", "skin biopsy", "renal cell",
    # specific clinical actions/claims that require information not present in an image alone
    "recommend chemotherapy", "recommend radiation", "recommend surgery", "psa level",
    "family history", "patient's age", "prior biopsy showed", "the patient has been",
    # over-precise staging claims not derivable from a single small patch
    "stage iv", "stage iii", "metastasis", "metastatic", "lymph node involvement",
]

def score_hallucination(text):
    """Returns (hallucinated: bool, matched_terms: list[str])."""
    low = text.lower()
    hits = [kw for kw in HALLUCINATION_KEYWORDS if kw in low]
    return (len(hits) > 0, hits)


# Separate from the hallucination rubric: does the open-ended response's own stated
# impression (benign vs cancer) match the real SICAPv2 ground truth? This catches plain
# diagnostic misses (e.g. calling a real Gleason-3 patch "benign") that the hallucination
# rubric above does not, since describing a real cancer patch as benign uses no ungrounded
# terms -- it is simply wrong, a different failure mode worth reporting separately.
BENIGN_TERMS = ["benign", "normal prostate", "no evidence of malignancy", "non-cancerous",
                "noncancerous", "no evidence of cancer", "unremarkable"]
CANCER_TERMS = ["cancer", "carcinoma", "malignant", "malignancy", "neoplastic", "neoplasm",
                "adenocarcinoma", "tumor"]

def score_diagnosis_direction(text, stratum):
    """Returns (stated_direction in {'benign','cancer',None}, matches_ground_truth: bool|None)."""
    low = text.lower()
    has_benign = any(t in low for t in BENIGN_TERMS)
    has_cancer = any(t in low for t in CANCER_TERMS)
    if has_benign and not has_cancer:
        stated = "benign"
    elif has_cancer and not has_benign:
        stated = "cancer"
    else:
        stated = None  # both/neither mentioned -> ambiguous, don't force a call
    true_direction = "benign" if stratum == "NC" else "cancer"
    matches = (stated == true_direction) if stated else None
    return stated, matches


# ---------------------------------------------------------------------------
# Task 3: forced pairwise comparison -> position bias + accuracy
# ---------------------------------------------------------------------------
TASK3_PROMPT_TEMPLATE = (
    "You are shown two H&E-stained histopathology patches from prostate needle biopsies, "
    "labeled LEFT and RIGHT. Which one looks MORE suspicious / concerning for aggressive "
    "prostate cancer: LEFT or RIGHT? Respond with ONLY the single word LEFT or RIGHT."
)

def parse_left_right(text):
    low = text.strip().lower()
    has_left = "left" in low
    has_right = "right" in low
    if has_left and not has_right:
        return "LEFT"
    if has_right and not has_left:
        return "RIGHT"
    return None  # ambiguous/unparseable


def build_pairwise_cases(df, rng_seed=20260729, max_pairs=15):
    """Build cross-severity-tier pairs (never same-tier, since there's no ground-truth
    ordering within a tier) from an eval set, each tested in BOTH left/right orders.
    Returns list of dicts: {pair_id, a_name, a_path, a_rank, b_name, b_path, b_rank}
    where 'a' is arbitrarily first; the calling script tests both (a=LEFT,b=RIGHT) and
    (b=LEFT,a=RIGHT).
    """
    import random
    rng = random.Random(rng_seed)
    rows = df.to_dict("records")
    pairs = []
    for r1, r2 in itertools.combinations(rows, 2):
        if r1["severity_rank"] == r2["severity_rank"]:
            continue
        pairs.append((r1, r2))
    rng.shuffle(pairs)
    pairs = pairs[:max_pairs]
    cases = []
    for i, (r1, r2) in enumerate(pairs):
        cases.append(dict(
            pair_id=i,
            a_name=r1["image_name"], a_path=r1["path"], a_rank=r1["severity_rank"], a_stratum=r1["stratum"],
            b_name=r2["image_name"], b_path=r2["path"], b_rank=r2["severity_rank"], b_stratum=r2["stratum"],
        ))
    return cases


def pairwise_ground_truth(a_rank, b_rank):
    """Which side (A or B) is the correct 'more suspicious' answer, given severity ranks."""
    return "A" if a_rank > b_rank else "B"


# ---------------------------------------------------------------------------
# Task 4: in-context learning variants of Task 1 and Task 3
# ---------------------------------------------------------------------------
def build_incontext_prefix_task1(exemplar_df, n=3, rng_seed=20260729):
    """n labeled exemplars (image + true severity score anchor) to prepend before Task 1."""
    ex = exemplar_df.sample(n=n, random_state=rng_seed)
    anchor_score = {"NC": 1, "G3": 4, "G4_noncrib": 7, "G4_crib": 7, "G5": 10}
    items = []
    for _, row in ex.iterrows():
        items.append(dict(path=row["path"], stratum=row["stratum"],
                           anchor_score=anchor_score[row["stratum"]]))
    return items


def build_incontext_prefix_task3(exemplar_df, n=2, rng_seed=20260729):
    """n labeled exemplar PAIRS (with known correct LEFT/RIGHT answer) to prepend before Task 3."""
    rows = exemplar_df.to_dict("records")
    pairs = [(r1, r2) for r1, r2 in itertools.combinations(rows, 2)
             if r1["severity_rank"] != r2["severity_rank"]]
    import random
    rng = random.Random(rng_seed)
    rng.shuffle(pairs)
    chosen = pairs[:n]
    items = []
    for r1, r2 in chosen:
        correct = "LEFT" if r1["severity_rank"] > r2["severity_rank"] else "RIGHT"
        items.append(dict(left_path=r1["path"], right_path=r2["path"], correct=correct,
                           left_stratum=r1["stratum"], right_stratum=r2["stratum"]))
    return items
