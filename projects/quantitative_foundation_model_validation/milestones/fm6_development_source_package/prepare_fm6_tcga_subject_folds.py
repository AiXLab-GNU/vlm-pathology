#!/usr/bin/env python3
"""Create the locked subject-level outer folds for TCGA FM6 development."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.model_selection import StratifiedKFold


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MILESTONE_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = MILESTONE_ROOT / "outputs"
LOCAL_ROOT = (
    REPOSITORY_ROOT
    / "resources/data/quantitative_foundation_model_validation/local-data"
    / "tcga_prad_current_gdc_bcr"
)
SUBJECT_TABLE = LOCAL_ROOT / "development_subjects.csv"
FOLD_TABLE = LOCAL_ROOT / "development_outer_folds.csv"
SEED = 260815
N_SPLITS = 5
PROTOCOL_ID = "QFMV-FM6-TCGA-FOLDS-2026-08-15-001"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def stratification_stratum(event: int, grade: int) -> str:
    if event == 1 and grade <= 2:
        return "event1_gg1_2"
    return f"event{event}_gg{grade}"


def main() -> int:
    rows = sorted(read_csv(SUBJECT_TABLE), key=lambda row: row["case_id"])
    if len(rows) != 392 or sum(int(row["bcr_event"]) for row in rows) != 80:
        raise RuntimeError("development subject/event universe changed")
    strata = np.asarray(
        [
            stratification_stratum(
                int(row["bcr_event"]), int(row["isup_grade_group"])
            )
            for row in rows
        ]
    )
    fold_ids = np.full(len(rows), -1, dtype=int)
    splitter = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    for fold_id, (_, test_indices) in enumerate(splitter.split(np.zeros(len(rows)), strata)):
        fold_ids[test_indices] = fold_id
    if set(fold_ids.tolist()) != set(range(N_SPLITS)):
        raise RuntimeError("outer fold assignment is incomplete")

    treatment = np.asarray(
        [row["both_treatments_documented"] == "True" for row in rows], dtype=bool
    )
    while True:
        treatment_counts = [int(treatment[fold_ids == fold].sum()) for fold in range(N_SPLITS)]
        high = int(np.argmax(treatment_counts))
        low = int(np.argmin(treatment_counts))
        if treatment_counts[high] - treatment_counts[low] <= 1:
            break
        swap: tuple[int, int] | None = None
        for high_index in np.flatnonzero((fold_ids == high) & treatment):
            for low_index in np.flatnonzero((fold_ids == low) & ~treatment):
                if strata[high_index] == strata[low_index]:
                    swap = (int(high_index), int(low_index))
                    break
            if swap is not None:
                break
        if swap is None:
            break
        fold_ids[swap[0]], fold_ids[swap[1]] = low, high

    fold_rows = [
        {
            "case_id": row["case_id"],
            "outer_fold": int(fold_ids[index]),
            "stratification_stratum": strata[index],
            "seed": SEED,
        }
        for index, row in enumerate(rows)
    ]
    write_csv(FOLD_TABLE, fold_rows, list(fold_rows[0]))

    balance_rows: list[dict[str, Any]] = []
    for fold_id in range(N_SPLITS):
        selected = [row for index, row in enumerate(rows) if fold_ids[index] == fold_id]
        balance_rows.append(
            {
                "outer_fold": fold_id,
                "n_subjects": len(selected),
                "n_events": sum(int(row["bcr_event"]) for row in selected),
                "n_treatment_documented": sum(
                    row["both_treatments_documented"] == "True" for row in selected
                ),
                **{
                    f"n_isup_{grade}": sum(
                        int(row["isup_grade_group"]) == grade for row in selected
                    )
                    for grade in range(1, 6)
                },
            }
        )
    balance_path = OUTPUT_DIR / "fm6_tcga_outer_fold_balance.csv"
    write_csv(balance_path, balance_rows, list(balance_rows[0]))
    config = {
        "protocol_id": PROTOCOL_ID,
        "seed": SEED,
        "n_splits": N_SPLITS,
        "stratification": "bcr_event_x_exact_isup_except_rare_event_gg1_2_combined_then_treatment_swap_balance",
        "n_subjects": len(rows),
        "n_events": sum(int(row["bcr_event"]) for row in rows),
        "subject_source_sha256": sha256_file(SUBJECT_TABLE),
        "local_fold_manifest_sha256": sha256_file(FOLD_TABLE),
        "balance_sha256": sha256_file(balance_path),
        "script_sha256": sha256_file(Path(__file__)),
    }
    config_path = OUTPUT_DIR / "fm6_tcga_outer_fold_run_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"config": config, "balance": balance_rows}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
