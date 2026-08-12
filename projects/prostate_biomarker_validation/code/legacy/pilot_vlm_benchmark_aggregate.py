"""Aggregates raw per-model results (resources/projects/prostate_biomarker_validation/model_workspace/vlm_benchmark_cache/{model}/results_{set}.json,
written by pilot_vlm_benchmark_{gpt4o,claude,quilt,llavamed}.py, all sharing the identical
schema from vlm_benchmark_common.py) into the quantitative table required by
docs/05_vlm_benchmark_task_prompt.md:
  - score variance (task 1, collapse check) + Spearman rho vs true severity rank
  - hallucination rate (task 2)
  - forced-pairwise accuracy + position-bias rate (task 3)
  - in-context deltas for both (task 4 vs baseline)

Usage:
    .venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_aggregate.py --set pilot
    .venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_aggregate.py --set full
"""
import argparse
import json
import os

import numpy as np
from scipy.stats import spearmanr

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlm_benchmark_common import score_diagnosis_direction

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "vlm_benchmark_cache")
SEVERITY_RANK = {"NC": 0, "G3": 1, "G4_noncrib": 2, "G4_crib": 2, "G5": 3}
MODELS = ["gpt5", "claude", "quilt", "llavamed"]


def score_stats(rows):
    scored = [r for r in rows if r["score"] is not None]
    n_missing = len(rows) - len(scored)
    if not scored:
        return dict(n=len(rows), n_parsed=0, n_missing=n_missing, variance=None, rho=None, pval=None)
    scores = np.array([r["score"] for r in scored])
    ranks = np.array([SEVERITY_RANK[r["stratum"]] for r in scored])
    variance = float(np.var(scores))
    if len(set(scores.tolist())) > 1 and len(set(ranks.tolist())) > 1:
        rho, pval = spearmanr(scores, ranks)
    else:
        rho, pval = 0.0, 1.0
    return dict(n=len(rows), n_parsed=len(scored), n_missing=n_missing,
                variance=round(variance, 3), rho=round(float(rho), 3), pval=round(float(pval), 4))


def hallucination_stats(rows):
    n = len(rows)
    n_halluc = sum(1 for r in rows if r["hallucinated"])
    directions = [score_diagnosis_direction(r["response"], r["stratum"]) for r in rows]
    called = [m for _, m in directions if m is not None]
    diag_acc = round(sum(called) / len(called), 3) if called else None
    return dict(n=n, hallucination_rate=round(n_halluc / n, 3) if n else None,
                diagnosis_direction_accuracy=diag_acc, diagnosis_direction_n_called=len(called))


def pairwise_stats(rows):
    n = len(rows)
    parsed = [r for r in rows if r["choice"] is not None]
    n_correct = sum(1 for r in parsed if r["correct"])
    n_left = sum(1 for r in parsed if r["choice"] == "LEFT")
    accuracy = round(n_correct / len(parsed), 3) if parsed else None
    position_bias = round(max(n_left, len(parsed) - n_left) / len(parsed), 3) if parsed else None
    left_frac = round(n_left / len(parsed), 3) if parsed else None
    return dict(n=n, n_parsed=len(parsed), accuracy=accuracy,
                position_bias_rate=position_bias, left_pick_frac=left_frac)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["pilot", "full"], default="pilot")
    args = ap.parse_args()

    summary = {}
    for m in MODELS:
        path = os.path.join(CACHE_DIR, m, f"results_{args.set}.json")
        if not os.path.exists(path):
            print(f"[skip] {m}: no results file at {path}")
            continue
        with open(path) as f:
            log = json.load(f)

        row = {}
        row["task1_baseline"] = score_stats(log["task1"])
        row["task4_incontext"] = score_stats(log["task4_score"])
        row["task2_hallucination"] = hallucination_stats(log["task2"])
        row["task3_baseline"] = pairwise_stats(log["task3"])
        row["task4_pairwise_incontext"] = pairwise_stats(log["task4_pairwise"])
        summary[m] = row

    print(f"\n{'='*100}\nVLM HALLUCINATION BENCHMARK -- {args.set.upper()} SET SUMMARY\n{'='*100}\n")
    header = (f"{'model':<10} {'T1 var':>8} {'T1 rho':>8} {'T1 p':>8} "
              f"{'T2 halluc%':>11} {'T2 diagacc%':>12} {'T3 acc%':>9} {'T3 posbias%':>12} "
              f"{'T4-T1 var':>10} {'T4-T1 rho':>10} {'T4-T3 acc%':>11} {'T4-T3 posbias%':>15}")
    print(header)
    for m, row in summary.items():
        t1, t4s, t2, t3, t4p = (row["task1_baseline"], row["task4_incontext"],
                                 row["task2_hallucination"], row["task3_baseline"],
                                 row["task4_pairwise_incontext"])
        def pct(x):
            return f"{x*100:.1f}" if x is not None else "n/a"
        print(f"{m:<10} {t1['variance'] if t1['variance'] is not None else 'n/a':>8} "
              f"{t1['rho'] if t1['rho'] is not None else 'n/a':>8} "
              f"{t1['pval'] if t1['pval'] is not None else 'n/a':>8} "
              f"{pct(t2['hallucination_rate']):>11} {pct(t2['diagnosis_direction_accuracy']):>12} "
              f"{pct(t3['accuracy']):>9} "
              f"{pct(t3['position_bias_rate']):>12} "
              f"{t4s['variance'] if t4s['variance'] is not None else 'n/a':>10} "
              f"{t4s['rho'] if t4s['rho'] is not None else 'n/a':>10} "
              f"{pct(t4p['accuracy']):>11} {pct(t4p['position_bias_rate']):>15}")

    out_path = os.path.join(CACHE_DIR, f"summary_{args.set}.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
