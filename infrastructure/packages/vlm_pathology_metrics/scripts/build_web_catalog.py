#!/usr/bin/env python3
"""Build deterministic browser data from the package's tiered TSV catalogs."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PACKAGE_ROOT / "src/vlm_pathology_metrics/data"
OUTPUT = PACKAGE_ROOT / "web/data/catalog-data.js"
TIER_FILES = (
    DATA_ROOT / "medical/tier1_clinician_native.tsv",
    DATA_ROOT / "medical/tier2_clinician_anchored.tsv",
    DATA_ROOT / "medical/tier3_research_computational.tsv",
    DATA_ROOT / "medical/tier4_model_derived.tsv",
)
ANALYSIS_FILE = DATA_ROOT / "analysis/analysis_measure_catalog.tsv"
LEGACY_FILE = DATA_ROOT / "legacy/metric_catalog_113.tsv"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def split_ids(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def main() -> None:
    medical = [row for path in TIER_FILES for row in read_tsv(path)]
    analysis = read_tsv(ANALYSIS_FILE)
    legacy = read_tsv(LEGACY_FILE)
    medical_ids = {row["metric_id"] for row in medical}
    analysis_ids = {row["metric_id"] for row in analysis}
    legacy_ids = {row["metric_id"] for row in legacy}
    if len(medical_ids) != len(medical) or len(analysis_ids) != len(analysis):
        raise RuntimeError("duplicate IDs in tiered catalogs")
    legacy_medical_ids = medical_ids & legacy_ids
    if legacy_ids != legacy_medical_ids | analysis_ids or legacy_medical_ids & analysis_ids:
        raise RuntimeError("medical and analysis catalogs do not partition the legacy registry")
    tier_rank = {f"T{number}": number for number in range(1, 5)}
    tier_by_id = {row["metric_id"]: row["tier"] for row in medical}
    for row in medical:
        parents = split_ids(row["parent_metric_ids"])
        row["parent_metric_ids"] = parents
        if row["tier"] == "T1" and parents:
            raise RuntimeError(f"T1 has parent: {row['metric_id']}")
        for parent in parents:
            if parent not in medical_ids:
                raise RuntimeError(f"unknown parent {parent} for {row['metric_id']}")
            if tier_rank[tier_by_id[parent]] >= tier_rank[row["tier"]]:
                raise RuntimeError(f"invalid tier direction {parent} -> {row['metric_id']}")
    medical.sort(key=lambda row: (tier_rank[row["tier"]], row["domain"], row["metric_id"]))
    analysis.sort(key=lambda row: (row["domain"], row["metric_id"]))
    payload = {
        "schema_version": "medical-metric-tiers-0.3",
        "source": {
            "medical": [str(path.relative_to(PACKAGE_ROOT)) for path in TIER_FILES],
            "analysis": str(ANALYSIS_FILE.relative_to(PACKAGE_ROOT)),
            "legacy": str(LEGACY_FILE.relative_to(PACKAGE_ROOT)),
        },
        "tier_meta": [
            {"tier": "T1", "name": "Clinician native", "name_ko": "임상의 직접 기록", "short": "의료 기준축"},
            {"tier": "T2", "name": "Clinician anchored", "name_ko": "임상 앵커 파생", "short": "고정 파생계측"},
            {"tier": "T3", "name": "Research computational", "name_ko": "연구 계산 특징", "short": "영상·공간 proxy"},
            {"tier": "T4", "name": "Model derived", "name_ko": "모델 파생값", "short": "score·rank·표현"},
        ],
        "summary": {
            "medical_total": len(medical),
            "analysis_total": len(analysis),
            "legacy_total": len(legacy),
            "tier_counts": dict(sorted(Counter(row["tier"] for row in medical).items())),
            "status_counts": dict(sorted(Counter(row["status"] for row in medical).items())),
            "analysis_domain_counts": dict(sorted(Counter(row["domain"] for row in analysis).items())),
        },
        "medical": medical,
        "analysis": analysis,
    }
    content = "window.METRIC_CATALOG = " + json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True,
    ) + ";\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
