#!/usr/bin/env python3
"""Audit whether ISUP/Gleason and biochemical recurrence can enter QFMV FM6.

This entry point audits source availability and endpoint semantics only. It does not train
an encoder, probe, or disease head. Patient-level GDC data are stored only in the ignored
project artifact root; tracked outputs contain aggregate counts and content hashes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MILESTONE_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = MILESTONE_ROOT / "outputs"
LOCAL_ARTIFACT_DIR = (
    REPOSITORY_ROOT
    / "resources"
    / "artifacts"
    / "quantitative_foundation_model_validation"
    / "fm6_entry_audit"
)
GDC_SNAPSHOT = LOCAL_ARTIFACT_DIR / "gdc_tcga_prad_clinical_snapshot.json"

FM1_PAIR_TABLE = (
    REPOSITORY_ROOT
    / "projects"
    / "quantitative_foundation_model_validation"
    / "milestones"
    / "fm1_metric_eligibility"
    / "outputs"
    / "metric_endpoint_independence.tsv"
)
LEOPARD_DATASET_MANIFEST = REPOSITORY_ROOT / "resources/data/manifests/leopard.yaml"
TCGA_DATASET_MANIFEST = REPOSITORY_ROOT / "resources/data/manifests/tcga_prad.yaml"
SHARED_DATA_ROOT = REPOSITORY_ROOT / "resources/data/shared/opendataset"
LEOPARD_LABELS = SHARED_DATA_ROOT / "LEOPARD/training_labels.csv"
LEOPARD_WSI_DIR = SHARED_DATA_ROOT / "LEOPARD/training"
TCGA_BCR_LABELS = SHARED_DATA_ROOT / "TCGA-PRAD-BCR/bcr.csv"
TCGA_RECURRENCE_ONLY_LABELS = (
    SHARED_DATA_ROOT / "TCGA-PRAD-BCR/bcr_recurrence_only.csv"
)
TCGA_BCR_DICTIONARY = (
    SHARED_DATA_ROOT / "TCGA-PRAD-BCR/bcr_label_data_dictionary.md"
)
TCGA_BCR_PROVENANCE = (
    SHARED_DATA_ROOT / "TCGA-PRAD-BCR/bcr_label_provenance.csv"
)
TCGA_WSI_MANIFEST = SHARED_DATA_ROOT / "TCGA-PRAD/manifest.csv"

GDC_API = "https://api.gdc.cancer.gov/cases"
GDC_FIELDS = (
    "submitter_id,"
    "diagnoses.gleason_grade_group,"
    "diagnoses.primary_gleason_grade,"
    "diagnoses.secondary_gleason_grade,"
    "diagnoses.gleason_score,"
    "diagnoses.treatments.treatment_type,"
    "diagnoses.treatments.treatment_or_therapy,"
    "follow_ups.progression_or_recurrence,"
    "follow_ups.days_to_recurrence,"
    "follow_ups.progression_or_recurrence_type,"
    "follow_ups.evidence_of_recurrence_type,"
    "follow_ups.first_event,"
    "follow_ups.days_to_first_event,"
    "follow_ups.disease_response,"
    "follow_ups.days_to_follow_up"
)
GDC_PAYLOAD: dict[str, Any] = {
    "filters": {
        "op": "in",
        "content": {"field": "project.project_id", "value": ["TCGA-PRAD"]},
    },
    "fields": GDC_FIELDS,
    "format": "json",
    "size": "600",
}
PROTOCOL_ID = "QFMV-FM6-ENTRY-AUDIT-2026-08-14-001"
QFM_PROJECT_ID = "quantitative_foundation_model_validation"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_manifest_projects(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^projects:\s*\[(.*?)\]\s*$", text, flags=re.MULTILINE)
    if not match:
        return []
    return [value.strip() for value in match.group(1).split(",") if value.strip()]


def fetch_gdc_snapshot(path: Path) -> dict[str, Any]:
    request = urllib.request.Request(
        GDC_API,
        data=json.dumps(GDC_PAYLOAD, sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    hits = sorted(payload["data"]["hits"], key=lambda row: row["submitter_id"])
    snapshot = {
        "schema_version": "qfmv-fm6-gdc-clinical-snapshot-1.0",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_url": GDC_API,
        "request_payload": GDC_PAYLOAD,
        "response_pagination": payload["data"].get("pagination", {}),
        "response_warnings": payload.get("warnings", {}),
        "hits": hits,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return snapshot


def load_gdc_snapshot(path: Path, *, refresh: bool) -> dict[str, Any]:
    if refresh or not path.is_file():
        return fetch_gdc_snapshot(path)
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_value(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def derive_isup(primary: Any, secondary: Any, score: Any) -> int | None:
    primary_value = numeric_value(primary)
    secondary_value = numeric_value(secondary)
    score_value = numeric_value(score)
    if primary_value is not None and secondary_value is not None:
        total = primary_value + secondary_value
        if total <= 6:
            return 1
        if primary_value == 3 and secondary_value == 4:
            return 2
        if primary_value == 4 and secondary_value == 3:
            return 3
        if total == 8:
            return 4
        if total >= 9:
            return 5
    if score_value is not None:
        if score_value <= 6:
            return 1
        if score_value == 8:
            return 4
        if score_value >= 9:
            return 5
    return None


def case_isup(case: dict[str, Any]) -> tuple[int | None, str]:
    values: set[int] = set()
    sources: set[str] = set()
    for diagnosis in case.get("diagnoses") or []:
        direct = numeric_value(diagnosis.get("gleason_grade_group"))
        if direct in {1, 2, 3, 4, 5}:
            values.add(direct)
            sources.add("reported_gleason_grade_group")
            continue
        derived = derive_isup(
            diagnosis.get("primary_gleason_grade"),
            diagnosis.get("secondary_gleason_grade"),
            diagnosis.get("gleason_score"),
        )
        if derived is not None:
            values.add(derived)
            sources.add("derived_from_reported_gleason_patterns_or_score")
    if len(values) == 1:
        return next(iter(values)), ";".join(sorted(sources))
    if len(values) > 1:
        return None, "conflicting_grade_records"
    return None, "missing_grade"


def case_treatment(case: dict[str, Any]) -> dict[str, bool]:
    status: dict[str, set[str]] = {"radiation": set(), "pharmaceutical": set()}
    for diagnosis in case.get("diagnoses") or []:
        for treatment in diagnosis.get("treatments") or []:
            treatment_type = str(treatment.get("treatment_type") or "").lower()
            value = str(treatment.get("treatment_or_therapy") or "").lower()
            if value not in {"yes", "no"}:
                continue
            if "radiation" in treatment_type:
                status["radiation"].add(value)
            if "pharmaceutical" in treatment_type:
                status["pharmaceutical"].add(value)
    return {
        "radiation_documented": bool(status["radiation"]),
        "pharmaceutical_documented": bool(status["pharmaceutical"]),
        "both_documented": bool(status["radiation"] and status["pharmaceutical"]),
    }


def case_has_any_direct_recurrence(case: dict[str, Any]) -> bool:
    for follow_up in case.get("follow_ups") or []:
        if follow_up.get("days_to_recurrence") is not None:
            return True
        value = str(follow_up.get("progression_or_recurrence") or "").strip().lower()
        if value and value not in {"unknown", "not reported", "not allowed to collect"}:
            return True
    return False


def case_bcr_endpoint(case: dict[str, Any]) -> dict[str, Any]:
    """Build an audit-only exact-BCR status from current harmonized GDC fields.

    Biochemical recurrence events require an explicit biochemical recurrence type and a
    non-negative recurrence time. Non-biochemical or untyped recurrence is excluded rather
    than silently censored. This function assesses availability; it does not freeze the
    final FM6 survival endpoint.
    """
    bcr_days: list[float] = []
    bcr_without_time = False
    other_or_untyped_recurrence = False
    censor_days: list[float] = []
    for follow_up in case.get("follow_ups") or []:
        progression = str(follow_up.get("progression_or_recurrence") or "").strip().lower()
        recurrence_type = str(
            follow_up.get("progression_or_recurrence_type")
            or follow_up.get("evidence_of_recurrence_type")
            or ""
        ).strip().lower()
        recurrence_day = follow_up.get("days_to_recurrence")
        if progression == "yes":
            if "biochemical" in recurrence_type:
                if isinstance(recurrence_day, (int, float)) and recurrence_day >= 0:
                    bcr_days.append(float(recurrence_day))
                else:
                    bcr_without_time = True
            else:
                other_or_untyped_recurrence = True
        follow_up_day = follow_up.get("days_to_follow_up")
        if isinstance(follow_up_day, (int, float)) and follow_up_day >= 0:
            censor_days.append(float(follow_up_day))

    if bcr_days:
        return {"status": "event_with_time", "event": 1, "days": min(bcr_days)}
    if bcr_without_time:
        return {"status": "event_missing_time", "event": 1, "days": None}
    if other_or_untyped_recurrence:
        return {"status": "competing_or_ambiguous_recurrence", "event": None, "days": None}
    if censor_days:
        return {"status": "censored_with_follow_up", "event": 0, "days": max(censor_days)}
    return {"status": "missing_follow_up", "event": None, "days": None}


def summarize_gdc(cases: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    case_data: dict[str, dict[str, Any]] = {}
    for case in cases:
        isup, isup_source = case_isup(case)
        treatment = case_treatment(case)
        bcr = case_bcr_endpoint(case)
        case_data[case["submitter_id"]] = {
            "isup": isup,
            "isup_source": isup_source,
            "any_direct_recurrence": case_has_any_direct_recurrence(case),
            "bcr_status": bcr["status"],
            "bcr_event": bcr["event"],
            "bcr_days": bcr["days"],
            **treatment,
        }
    summary = {
        "n_cases": len(case_data),
        "n_isup_available": sum(row["isup"] is not None for row in case_data.values()),
        "n_isup_conflict": sum(
            row["isup_source"] == "conflicting_grade_records" for row in case_data.values()
        ),
        "n_radiation_documented": sum(
            row["radiation_documented"] for row in case_data.values()
        ),
        "n_pharmaceutical_documented": sum(
            row["pharmaceutical_documented"] for row in case_data.values()
        ),
        "n_both_treatments_documented": sum(
            row["both_documented"] for row in case_data.values()
        ),
        "n_any_direct_recurrence_fields": sum(
            row["any_direct_recurrence"] for row in case_data.values()
        ),
        "n_bcr_event_with_time": sum(
            row["bcr_status"] == "event_with_time" for row in case_data.values()
        ),
        "n_bcr_event_missing_time": sum(
            row["bcr_status"] == "event_missing_time" for row in case_data.values()
        ),
        "n_bcr_censored_with_follow_up": sum(
            row["bcr_status"] == "censored_with_follow_up" for row in case_data.values()
        ),
        "n_bcr_competing_or_ambiguous": sum(
            row["bcr_status"] == "competing_or_ambiguous_recurrence"
            for row in case_data.values()
        ),
        "n_bcr_missing_follow_up": sum(
            row["bcr_status"] == "missing_follow_up" for row in case_data.values()
        ),
    }
    return case_data, summary


def event_summary(rows: list[dict[str, str]]) -> tuple[int, int]:
    return len(rows), sum(int(float(row["event"])) for row in rows)


def join_summary(
    outcome_rows: list[dict[str, str]],
    case_data: dict[str, dict[str, Any]],
    wsi_cases: set[str],
) -> dict[str, int]:
    joined = [
        row
        for row in outcome_rows
        if row["case_id"] in case_data and row["case_id"] in wsi_cases
    ]
    with_grade = [row for row in joined if case_data[row["case_id"]]["isup"] is not None]
    with_treatment = [
        row for row in with_grade if case_data[row["case_id"]]["both_documented"]
    ]
    return {
        "n_image_outcome_linked": len(joined),
        "n_image_isup_outcome_linked": len(with_grade),
        "n_image_isup_outcome_events": sum(int(float(row["event"])) for row in with_grade),
        "n_complete_treatment": len(with_treatment),
        "n_complete_treatment_events": sum(
            int(float(row["event"])) for row in with_treatment
        ),
    }


def gdc_bcr_join_summary(
    case_data: dict[str, dict[str, Any]], wsi_cases: set[str]
) -> dict[str, int]:
    eligible_statuses = {"event_with_time", "censored_with_follow_up"}
    outcome = [
        (case_id, row)
        for case_id, row in case_data.items()
        if case_id in wsi_cases and row["bcr_status"] in eligible_statuses
    ]
    with_grade = [(case_id, row) for case_id, row in outcome if row["isup"] is not None]
    with_treatment = [(case_id, row) for case_id, row in with_grade if row["both_documented"]]
    return {
        "n_image_outcome_linked": len(outcome),
        "n_image_outcome_events": sum(row["bcr_event"] == 1 for _, row in outcome),
        "n_image_isup_outcome_linked": len(with_grade),
        "n_image_isup_outcome_events": sum(row["bcr_event"] == 1 for _, row in with_grade),
        "n_complete_treatment": len(with_treatment),
        "n_complete_treatment_events": sum(
            row["bcr_event"] == 1 for _, row in with_treatment
        ),
    }


def source_row(source_id: str, path: Path, role: str, scope: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "path": str(path.relative_to(REPOSITORY_ROOT)),
        "role": role,
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else "",
        "sha256": sha256_file(path) if path.is_file() else "",
        "ownership_scope": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-gdc",
        action="store_true",
        help="Refresh the local untracked GDC clinical snapshot before auditing.",
    )
    args = parser.parse_args()
    started = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    fm1_pairs = read_csv(FM1_PAIR_TABLE, delimiter="\t")
    h2_pair = next(row for row in fm1_pairs if row["pair_id"] == "H2-001")
    leopard_projects = parse_manifest_projects(LEOPARD_DATASET_MANIFEST)
    tcga_projects = parse_manifest_projects(TCGA_DATASET_MANIFEST)

    leopard_rows = read_csv(LEOPARD_LABELS)
    leopard_n, leopard_events = event_summary(leopard_rows)
    leopard_wsi_n = sum(
        (LEOPARD_WSI_DIR / row["case_id"]).is_file() for row in leopard_rows
    )

    tcga_rows = read_csv(TCGA_BCR_LABELS)
    tcga_n, tcga_events = event_summary(tcga_rows)
    tcga_recurrence_rows = read_csv(TCGA_RECURRENCE_ONLY_LABELS)
    tcga_recurrence_n, tcga_recurrence_events = event_summary(tcga_recurrence_rows)
    tcga_wsi_rows = read_csv(TCGA_WSI_MANIFEST)
    tcga_wsi_cases = {row["case_id"] for row in tcga_wsi_rows}

    snapshot = load_gdc_snapshot(GDC_SNAPSHOT, refresh=args.refresh_gdc)
    case_data, gdc_summary = summarize_gdc(snapshot["hits"])
    tcga_exact_bcr_join = gdc_bcr_join_summary(case_data, tcga_wsi_cases)
    tcga_join = join_summary(tcga_rows, case_data, tcga_wsi_cases)
    tcga_recurrence_join = join_summary(
        tcga_recurrence_rows, case_data, tcga_wsi_cases
    )

    leopard_authorized = QFM_PROJECT_ID in leopard_projects
    tcga_authorized = QFM_PROJECT_ID in tcga_projects
    cohort_rows: list[dict[str, Any]] = [
        {
            "cohort_id": "LEOPARD",
            "candidate_role": "external_true_bcr_outcome_only",
            "endpoint_exact_name": "biochemical_recurrence_status_and_time",
            "n_outcome_subjects": leopard_n,
            "n_events": leopard_events,
            "n_wsi_subjects": leopard_wsi_n,
            "n_isup_outcome_linked": 0,
            "n_isup_outcome_events": 0,
            "n_treatment_complete": 0,
            "n_treatment_complete_events": 0,
            "endpoint_equivalent_to_true_bcr": True,
            "metric_endpoint_independence": h2_pair["endpoint_independence"],
            "qfm_manifest_authorized": leopard_authorized,
            "status": "blocked_missing_isup_and_treatment",
            "blocking_reason": (
                "official/local training labels contain only case_id,event,follow_up_years; "
                "no patient-level ISUP/Gleason or treatment covariates"
            ),
        },
        {
            "cohort_id": "TCGA-PRAD",
            "candidate_role": "development_true_bcr_candidate",
            "endpoint_exact_name": "gdc_biochemical_recurrence_status_and_time",
            "n_outcome_subjects": tcga_exact_bcr_join["n_image_outcome_linked"],
            "n_events": tcga_exact_bcr_join["n_image_outcome_events"],
            "n_wsi_subjects": len(tcga_wsi_cases),
            "n_isup_outcome_linked": tcga_exact_bcr_join["n_image_isup_outcome_linked"],
            "n_isup_outcome_events": tcga_exact_bcr_join["n_image_isup_outcome_events"],
            "n_treatment_complete": tcga_exact_bcr_join["n_complete_treatment"],
            "n_treatment_complete_events": tcga_exact_bcr_join["n_complete_treatment_events"],
            "endpoint_equivalent_to_true_bcr": True,
            "metric_endpoint_independence": h2_pair["endpoint_independence"],
            "qfm_manifest_authorized": tcga_authorized,
            "status": "candidate_blocked_manifest_power_and_external_metric_truth",
            "blocking_reason": (
                "current GDC has biochemical recurrence fields, but the QFM access manifest, "
                "prespecified power threshold, and an independent external cohort with ISUP truth "
                "and treatment covariates are absent"
            ),
        },
    ]
    cohort_fields = list(cohort_rows[0].keys())
    cohort_path = OUTPUT_DIR / "fm6_cohort_eligibility.csv"
    write_csv(cohort_path, cohort_rows, cohort_fields)

    source_rows = [
        source_row("fm1_h2_pair_registry", FM1_PAIR_TABLE, "eligibility_registry", "qfm_owned"),
        source_row("leopard_dataset_manifest", LEOPARD_DATASET_MANIFEST, "dataset_access_manifest", "repository"),
        source_row("leopard_labels", LEOPARD_LABELS, "true_bcr_labels", "shared_local_untracked"),
        source_row("tcga_dataset_manifest", TCGA_DATASET_MANIFEST, "dataset_access_manifest", "repository"),
        source_row("tcga_recurrence_style_labels", TCGA_BCR_LABELS, "coarse_outcome_labels", "shared_local_untracked"),
        source_row("tcga_recurrence_only_labels", TCGA_RECURRENCE_ONLY_LABELS, "sensitivity_outcome_labels", "shared_local_untracked"),
        source_row("tcga_endpoint_dictionary", TCGA_BCR_DICTIONARY, "endpoint_provenance", "shared_local_untracked"),
        source_row("tcga_endpoint_provenance", TCGA_BCR_PROVENANCE, "patient_level_provenance", "shared_local_untracked"),
        source_row("tcga_wsi_manifest", TCGA_WSI_MANIFEST, "image_case_linkage", "shared_local_untracked"),
        source_row("gdc_tcga_prad_clinical_snapshot", GDC_SNAPSHOT, "grade_treatment_availability_audit", "qfm_local_untracked"),
    ]
    source_path = OUTPUT_DIR / "fm6_source_manifest.csv"
    write_csv(source_path, source_rows, list(source_rows[0].keys()))

    gdc_path = OUTPUT_DIR / "fm6_gdc_field_completeness.csv"
    gdc_rows = [
        {"field_family": key, "n_subjects": value, "denominator": gdc_summary["n_cases"]}
        for key, value in gdc_summary.items()
        if key != "n_cases"
    ]
    write_csv(gdc_path, gdc_rows, ["field_family", "n_subjects", "denominator"])

    decision = "BLOCKED_NO_COMPLETE_DEVELOPMENT_AND_EXTERNAL_PAIR"
    report = f"""---
document_id: fm6-isup-bcr-entry-audit-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: active
created: 2026-08-14
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_entry_audit/outputs/fm6-entry-audit-report.md
---

# FM6 ISUP–BCR 진입 적격성 감사 보고서

- Protocol: `{PROTOCOL_ID}`
- 판정: **{decision}**
- 허용 범위 변화: **없음**
- H2-001의 이론적 독립성: `{h2_pair['endpoint_independence']}` / `{h2_pair['circularity']}`

## 핵심 결과

| 코호트 | Outcome | Outcome N/events | WSI | ISUP–outcome 연결 | 방사선·약물 documented | QFM manifest | 판정 |
|---|---|---:|---:|---:|---:|---|---|
| LEOPARD | PSA 기반 BCR status/time | {leopard_n}/{leopard_events} | {leopard_wsi_n} | 0 | 0 | {str(leopard_authorized).lower()} | ISUP·치료 정보 부재로 외부 semantic 검증 불가 |
| TCGA-PRAD | 현재 GDC biochemical recurrence | {tcga_exact_bcr_join['n_image_outcome_linked']}/{tcga_exact_bcr_join['n_image_outcome_events']} | {len(tcga_wsi_cases)} | {tcga_exact_bcr_join['n_image_isup_outcome_linked']} ({tcga_exact_bcr_join['n_image_isup_outcome_events']} events) | {tcga_exact_bcr_join['n_complete_treatment']} ({tcga_exact_bcr_join['n_complete_treatment_events']} events) | {str(tcga_authorized).lower()} | 개발 후보; manifest·power·외부 metric truth 부족 |

기존 로컬 TCGA `disease_response` 기반 endpoint는 {tcga_n}명/{tcga_events} events다.
더 엄격한 `tumor-free → with-tumor` sensitivity endpoint는
{tcga_recurrence_n}명/{tcga_recurrence_events} events이며, WSI·ISUP와 연결되는 표본은
{tcga_recurrence_join['n_image_isup_outcome_linked']}명/{tcga_recurrence_join['n_image_isup_outcome_events']} events다.
두 로컬 endpoint는 모두 현재 GDC의 명시적 biochemical recurrence endpoint와 구분하며,
FM6의 BCR endpoint로 사용하지 않는다.

공식 source 정의는 [LEOPARD Data](https://leopard.grand-challenge.org/data/),
[GDC clinical field registry](https://docs.gdc.cancer.gov/API/Users_Guide/Appendix_A_Available_Fields/),
[TCGA PRAD enrollment form](https://gdc.cancer.gov/system/files/public/file/Prostate%20Enrollment%20Form.pdf)을
사용했다. 실제 가용성 수치는 위 문서의 일반 설명이 아니라 hash가 기록된 로컬 label과
이번 GDC API snapshot에서 계산했다.

## 판정 근거

1. ISUP와 BCR은 정의상 비순환적이므로 `endpoint_independence=independent` 판정은 유지한다.
2. LEOPARD의 공식·로컬 training label 열은 `case_id,event,follow_up_years`뿐이다. BCR
   outcome과 WSI는 있지만 같은 환자의 ISUP/Gleason 및 치료 공변량이 없다.
3. 현재 GDC snapshot {gdc_summary['n_cases']}명 중 ISUP를 직접 또는 보고된 Gleason
   pattern/score에서 고정식으로 도출할 수 있는 환자는 {gdc_summary['n_isup_available']}명이다.
   명시적 biochemical recurrence와 시간이 있는 환자는 {gdc_summary['n_bcr_event_with_time']}명,
   평가 가능한 censoring time이 있는 환자는 {gdc_summary['n_bcr_censored_with_follow_up']}명이다.
4. 현재 GDC에는 이전 로컬 감사와 달리 biochemical recurrence type과 time이 채워져 있다.
   따라서 TCGA-PRAD는 개발 후보가 될 수 있지만, 이번 가용성 산출은 endpoint protocol과
   power를 아직 고정하지 않은 audit-only 집계다.
5. 기존 로컬 TCGA endpoint는 `disease_response=WT-With Tumor`를 사용하므로 재발과
   잔존질환을 분리하지 못한다. 이를 현재 GDC biochemical recurrence endpoint와 섞지 않는다.
6. LEOPARD와 TCGA dataset manifest 모두 현재 QFM을 허용 프로젝트로 등록하지 않는다.
   과학적 적격성이 먼저 충족되지 않았으므로 이번 감사에서 공유 manifest 승격은 하지 않았다.
7. TCGA에는 내부 개발 후보가 있지만, 같은 ISUP/Gleason metric truth와 치료 공변량을 가진
   독립 true-BCR 외부 코호트가 없다. 또한 최소 사건 수·검정력 기준이 사전 고정되지 않았다.
   따라서 `R+A+U+T` H2 진입은 아직 불가하다.

## 결론과 다음 단일 작업

FM6 H2 실험, disease-head 학습과 targeted erasure는 계속 잠근다. 다음 단일 작업은
**TCGA-PRAD의 현재 GDC biochemical recurrence endpoint를 QFM용 hash-locked 개발
source package와 사전 power protocol로 고정하는 것**이다. 이 개발 패키지에는 다음이
같은 subject ID로 연결돼야 한다.

- WSI와 고정 specimen/timepoint
- 병리의 보고 ISUP 또는 primary/secondary Gleason pattern
- 정확한 PSA 기반 BCR status와 time-to-event/censoring 정의
- 수술 및 보조 방사선·약물치료 변수
- site/scanner/stain metadata와 명시적 결측 사유

이 패키지와 사전 최소 사건 수가 고정되기 전에는 H2-001을 `eligible`로 승격하지 않는다.
기존 TCGA `disease_response` 기반 recurrence-style endpoint를 사용하려면 이름과 estimand가
다른 별도 탐색 subprotocol로 등록해야 한다. LEOPARD는 true-BCR outcome 외부셋 후보지만,
ISUP/Gleason과 치료 공변량이 추가 확보되지 않는 한 H2의 semantic transport를 완료할 수 없다.
TCGA 개발 subprotocol을 고정한 뒤에도 동일 metric truth와 치료 공변량을 가진 독립 외부
BCR cohort의 등록은 강한 H2 및 targeted erasure 실행을 위한 별도 후속 gate로 남는다.
"""
    report_path = OUTPUT_DIR / "fm6-entry-audit-report.md"
    report_path.write_text(report, encoding="utf-8")

    output_hashes = {
        path.name: sha256_file(path)
        for path in (cohort_path, source_path, gdc_path, report_path)
    }
    config = {
        "protocol_id": PROTOCOL_ID,
        "decision": decision,
        "entry_unlocked": False,
        "claim_ceiling_changed": False,
        "gdc_snapshot_path": str(GDC_SNAPSHOT.relative_to(REPOSITORY_ROOT)),
        "gdc_snapshot_sha256": sha256_file(GDC_SNAPSHOT),
        "gdc_request_payload_sha256": hashlib.sha256(
            json.dumps(GDC_PAYLOAD, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "source_manifest_sha256": sha256_file(source_path),
        "script_sha256": sha256_file(Path(__file__)),
        "execution_time_seconds": round(time.time() - started, 6),
        "output_sha256": output_hashes,
        "volatile_fields": ["execution_time_seconds"],
    }
    config_path = OUTPUT_DIR / "fm6_run_config.json"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "protocol_id": PROTOCOL_ID,
        "decision": decision,
        "leopard": {"subjects": leopard_n, "events": leopard_events, "isup_linked": 0},
        "tcga": {
            "subjects": tcga_exact_bcr_join["n_image_outcome_linked"],
            "events": tcga_exact_bcr_join["n_image_outcome_events"],
            "image_isup_outcome_linked": tcga_exact_bcr_join["n_image_isup_outcome_linked"],
            "image_isup_outcome_events": tcga_exact_bcr_join["n_image_isup_outcome_events"],
            "treatment_complete": tcga_exact_bcr_join["n_complete_treatment"],
            "treatment_complete_events": tcga_exact_bcr_join["n_complete_treatment_events"],
            "any_direct_recurrence_fields": gdc_summary["n_any_direct_recurrence_fields"],
        },
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
