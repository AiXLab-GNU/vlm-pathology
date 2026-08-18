#!/usr/bin/env python3
"""Lock the TCGA-PRAD current-GDC ISUP/BCR development source package.

This stage creates source and semantic handoff records only. It does not train a probe,
disease head, or encoder, and it does not execute H2 or inspect CHIMERA model outcomes.
Patient-level tables remain under the ignored project-local data root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MILESTONE_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = MILESTONE_ROOT / "outputs"
LOCAL_ROOT = (
    REPOSITORY_ROOT
    / "resources/data/quantitative_foundation_model_validation/local-data"
    / "tcga_prad_current_gdc_bcr"
)
ENTRY_AUDIT_SCRIPT = (
    REPOSITORY_ROOT
    / "projects/quantitative_foundation_model_validation/milestones/fm6_entry_audit"
    / "run_fm6_entry_audit.py"
)
GDC_SNAPSHOT = (
    REPOSITORY_ROOT
    / "resources/artifacts/quantitative_foundation_model_validation/fm6_entry_audit"
    / "gdc_tcga_prad_clinical_snapshot.json"
)
TCGA_MANIFEST = REPOSITORY_ROOT / "resources/data/shared/opendataset/TCGA-PRAD/manifest.csv"
TCGA_SLIDES = REPOSITORY_ROOT / "resources/data/shared/opendataset/TCGA-PRAD/slides"
TCGA_DATASET_MANIFEST = REPOSITORY_ROOT / "resources/data/manifests/tcga_prad.yaml"
CHIMERA_DATASET_MANIFEST = REPOSITORY_ROOT / "resources/data/manifests/chimera_task1.yaml"
CHIMERA_ELIGIBILITY = (
    REPOSITORY_ROOT
    / "projects/quantitative_foundation_model_validation/milestones"
    / "fm6_external_cohort_acquisition/outputs/fm6_external_cohort_eligibility.csv"
)
GDC_FILE_METADATA = LOCAL_ROOT / "gdc_development_file_metadata.json"
LOCAL_CONTENT_VERIFICATION = LOCAL_ROOT / "development_slide_content_verification.csv"
GDC_FILES_API = "https://api.gdc.cancer.gov/files"
GDC_DATA_URL = "https://api.gdc.cancer.gov/data/{file_id}"
PROTOCOL = (
    REPOSITORY_ROOT
    / "projects/quantitative_foundation_model_validation/docs/protocols"
    / "fm6-isup-bcr-source-and-power-protocol-ko.md"
)
PREPROCESSING_PROTOCOL = (
    REPOSITORY_ROOT
    / "projects/quantitative_foundation_model_validation/docs/protocols"
    / "fm6-tcga-wsi-preprocessing-and-aggregation-protocol-ko.md"
)
FOLD_TABLE = LOCAL_ROOT / "development_outer_folds.csv"
FOLD_CONFIG = OUTPUT_DIR / "fm6_tcga_outer_fold_run_config.json"
LOCAL_HEADER_QC = LOCAL_ROOT / "development_wsi_header_qc.csv"
HEADER_QC_CONFIG = OUTPUT_DIR / "fm6_tcga_wsi_qc_run_config.json"
PROTOCOL_ID = "QFMV-FM6-DEVELOPMENT-SOURCE-2026-08-15-001"
STATUS = "DEVELOPMENT_SOURCE_HASH_LOCKED_ACQUISITION_AND_HARMONIZATION_HOLD_H2_LOCKED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
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


def relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY_ROOT))


def load_entry_module():
    spec = importlib.util.spec_from_file_location("qfm_fm6_entry_audit", ENTRY_AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load FM6 entry-audit parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_gdc_file_metadata(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    file_ids = sorted({row["file_id"] for row in rows})
    payload = {
        "filters": {"op": "in", "content": {"field": "file_id", "value": file_ids}},
        "fields": "file_id,file_name,file_size,md5sum,state,access,data_type,data_format,experimental_strategy",
        "format": "json",
        "size": str(len(file_ids) + 10),
    }
    response = requests.post(GDC_FILES_API, json=payload, timeout=180)
    response.raise_for_status()
    hits = sorted(response.json()["data"]["hits"], key=lambda row: row["file_id"])
    if {row["file_id"] for row in hits} != set(file_ids):
        raise RuntimeError("GDC file metadata response does not match the locked file UUID set")
    locked = {
        "schema_version": "qfmv-fm6-gdc-file-metadata-1.0",
        "request_url": GDC_FILES_API,
        "request_payload": payload,
        "hits": hits,
    }
    GDC_FILE_METADATA.parent.mkdir(parents=True, exist_ok=True)
    GDC_FILE_METADATA.write_text(
        json.dumps(locked, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return {row["file_id"]: row for row in hits}


def load_gdc_file_metadata(
    rows: list[dict[str, str]], *, refresh: bool
) -> dict[str, dict[str, Any]]:
    if refresh or not GDC_FILE_METADATA.is_file():
        return fetch_gdc_file_metadata(rows)
    payload = json.loads(GDC_FILE_METADATA.read_text(encoding="utf-8"))
    metadata = {row["file_id"]: row for row in payload["hits"]}
    if set(metadata) != {row["file_id"] for row in rows}:
        raise RuntimeError("cached GDC metadata UUID set differs from the development WSI set")
    return metadata


def download_one(
    row: dict[str, str], metadata: dict[str, Any], *, retries: int = 8
) -> tuple[str, str]:
    destination = TCGA_SLIDES / row["file_name"]
    expected_size = int(row["file_size"])
    expected_md5 = str(metadata["md5sum"]).lower()
    if int(metadata["file_size"]) != expected_size or metadata["file_name"] != row["file_name"]:
        return row["file_name"], "FAILED locked manifest differs from GDC metadata"
    if destination.is_file() and destination.stat().st_size == expected_size:
        observed_md5 = md5_file(destination)
        if observed_md5 == expected_md5:
            return row["file_name"], "reused-md5-verified"
        invalid = destination.with_name(
            destination.name + f".invalid-md5-{observed_md5[:12]}"
        )
        if invalid.exists():
            return row["file_name"], f"FAILED repeated MD5 mismatch {observed_md5}"
        destination.replace(invalid)

    TCGA_SLIDES.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if destination.exists():
        return row["file_name"], f"FAILED existing final file has unexpected size {destination.stat().st_size}"
    if partial.exists() and partial.stat().st_size > expected_size:
        partial.unlink()

    for attempt in range(1, retries + 1):
        try:
            if partial.exists() and partial.stat().st_size == expected_size:
                observed_md5 = md5_file(partial)
                if observed_md5 == expected_md5:
                    partial.replace(destination)
                    return row["file_name"], "resumed-complete-md5-verified"
                partial.unlink()
            offset = partial.stat().st_size if partial.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with requests.get(
                GDC_DATA_URL.format(file_id=row["file_id"]),
                headers=headers,
                stream=True,
                timeout=(60, 600),
            ) as response:
                response.raise_for_status()
                append = bool(offset and response.status_code == 206)
                mode = "ab" if append else "wb"
                with partial.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if partial.stat().st_size != expected_size:
                raise IOError(
                    f"size mismatch {partial.stat().st_size} != {expected_size}"
                )
            observed_md5 = md5_file(partial)
            if observed_md5 != expected_md5:
                partial.unlink()
                raise IOError(f"MD5 mismatch {observed_md5} != {expected_md5}")
            partial.replace(destination)
            return row["file_name"], "downloaded-md5-verified"
        except Exception as error:  # network and integrity failures are retried together
            if attempt == retries:
                return row["file_name"], f"FAILED after {retries} attempts: {error}"
            time.sleep(min(60, 5 * attempt))
    raise AssertionError("unreachable")


def download_missing_slides(
    rows: list[dict[str, str]], metadata: dict[str, dict[str, Any]], workers: int
) -> list[tuple[str, str]]:
    cached_failed: set[str] = set()
    if LOCAL_CONTENT_VERIFICATION.is_file():
        cached_failed = {
            row["file_id"]
            for row in read_csv(LOCAL_CONTENT_VERIFICATION)
            if row.get("status") != "PASS"
        }
    missing = [
        row
        for row in rows
        if row["file_id"] in cached_failed
        or not (TCGA_SLIDES / row["file_name"]).is_file()
        or (TCGA_SLIDES / row["file_name"]).stat().st_size != int(row["file_size"])
    ]
    print(
        f"download target: {len(missing)} slides / "
        f"{sum(int(row['file_size']) for row in missing)} bytes; workers={workers}",
        flush=True,
    )
    failures: list[tuple[str, str]] = []
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_one, row, metadata[row["file_id"]]): row
            for row in missing
        }
        for future in as_completed(futures):
            name, status = future.result()
            completed += 1
            print(f"[{completed}/{len(missing)}] {name}: {status}", flush=True)
            if status.startswith("FAILED"):
                failures.append((name, status))
    return failures


def verify_local_content(
    rows: list[dict[str, str]], metadata: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        path = TCGA_SLIDES / row["file_name"]
        expected_size = int(row["file_size"])
        expected_md5 = str(metadata[row["file_id"]]["md5sum"]).lower()
        size_complete = path.is_file() and path.stat().st_size == expected_size
        observed_md5 = md5_file(path) if size_complete else ""
        passed = size_complete and observed_md5 == expected_md5
        results.append(
            {
                "file_id": row["file_id"],
                "file_name": row["file_name"],
                "expected_bytes": expected_size,
                "expected_md5": expected_md5,
                "observed_md5": observed_md5,
                "status": "PASS" if passed else "FAIL",
            }
        )
        print(
            f"verify [{index}/{len(rows)}] {row['file_name']}: "
            f"{'PASS' if passed else 'FAIL'}",
            flush=True,
        )
    write_csv(LOCAL_CONTENT_VERIFICATION, results, list(results[0]))
    return results


def source_row(source_id: str, path: Path, role: str, visibility: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "path": relative(path),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "portal_visibility": visibility,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--refresh-file-metadata", action="store_true")
    parser.add_argument("--verify-local-content", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 16:
        raise ValueError("--workers must be between 1 and 16")
    started = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)

    required = [
        ENTRY_AUDIT_SCRIPT,
        GDC_SNAPSHOT,
        TCGA_MANIFEST,
        TCGA_DATASET_MANIFEST,
        CHIMERA_DATASET_MANIFEST,
        CHIMERA_ELIGIBILITY,
        PROTOCOL,
    ]
    missing = [relative(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing required source(s): {missing}")

    entry = load_entry_module()
    snapshot = json.loads(GDC_SNAPSHOT.read_text(encoding="utf-8"))
    case_data, gdc_summary = entry.summarize_gdc(snapshot["hits"])
    wsi_rows = sorted(
        read_csv(TCGA_MANIFEST), key=lambda row: (row["case_id"], row["file_id"])
    )
    rows_by_case: dict[str, list[dict[str, str]]] = {}
    for row in wsi_rows:
        rows_by_case.setdefault(row["case_id"], []).append(row)

    eligible_statuses = {"event_with_time", "censored_with_follow_up"}
    eligible_case_ids = {
        case_id
        for case_id in set(rows_by_case) & set(case_data)
        if case_data[case_id]["isup"] is not None
        and case_data[case_id]["bcr_status"] in eligible_statuses
    }
    development_wsi_rows = [row for row in wsi_rows if row["case_id"] in eligible_case_ids]
    metadata = load_gdc_file_metadata(
        development_wsi_rows, refresh=args.refresh_file_metadata
    )
    download_failures: list[tuple[str, str]] = []
    if args.download_missing:
        download_failures = download_missing_slides(
            development_wsi_rows, metadata, args.workers
        )
    verification_rows: list[dict[str, Any]] = []
    if args.verify_local_content:
        verification_rows = verify_local_content(development_wsi_rows, metadata)
    elif LOCAL_CONTENT_VERIFICATION.is_file():
        verification_rows = read_csv(LOCAL_CONTENT_VERIFICATION)

    subject_rows: list[dict[str, Any]] = []
    slide_rows: list[dict[str, Any]] = []
    for case_id in sorted(set(rows_by_case) & set(case_data)):
        case = case_data[case_id]
        if case["isup"] is None or case["bcr_status"] not in eligible_statuses:
            continue
        case_slides = rows_by_case[case_id]
        local_count = 0
        for slide in case_slides:
            local_path = TCGA_SLIDES / slide["file_name"]
            local_complete = (
                local_path.is_file()
                and local_path.stat().st_size == int(slide["file_size"])
            )
            local_count += int(local_complete)
            slide_rows.append(
                {
                    "case_id": case_id,
                    "file_id": slide["file_id"],
                    "file_name": slide["file_name"],
                    "expected_bytes": int(slide["file_size"]),
                    "expected_md5": metadata[slide["file_id"]]["md5sum"],
                    "local_complete": local_complete,
                    "local_relative_path": relative(local_path),
                }
            )
        subject_rows.append(
            {
                "case_id": case_id,
                "isup_grade_group": case["isup"],
                "isup_source": case["isup_source"],
                "bcr_event": case["bcr_event"],
                "bcr_time_days": case["bcr_days"],
                "bcr_status": case["bcr_status"],
                "radiation_documented": case["radiation_documented"],
                "pharmaceutical_documented": case["pharmaceutical_documented"],
                "both_treatments_documented": case["both_documented"],
                "n_manifest_slides": len(case_slides),
                "n_local_slides": local_count,
                "all_manifest_slides_local": local_count == len(case_slides),
            }
        )

    subject_path = LOCAL_ROOT / "development_subjects.csv"
    slide_path = LOCAL_ROOT / "development_slides.csv"
    write_csv(subject_path, subject_rows, list(subject_rows[0]))
    write_csv(slide_path, slide_rows, list(slide_rows[0]))

    n_subjects = len(subject_rows)
    n_events = sum(int(row["bcr_event"]) for row in subject_rows)
    n_treatment = sum(bool(row["both_treatments_documented"]) for row in subject_rows)
    n_treatment_events = sum(
        bool(row["both_treatments_documented"]) and int(row["bcr_event"])
        for row in subject_rows
    )
    n_local_subjects = sum(bool(row["all_manifest_slides_local"]) for row in subject_rows)
    n_local_events = sum(
        bool(row["all_manifest_slides_local"]) and int(row["bcr_event"])
        for row in subject_rows
    )
    n_slides = len(slide_rows)
    n_local_slides = sum(bool(row["local_complete"]) for row in slide_rows)
    verified_by_id = {
        row["file_id"]: row.get("status") == "PASS" for row in verification_rows
    }
    n_content_verified = sum(
        verified_by_id.get(row["file_id"], False) for row in slide_rows
    )
    missing_bytes = sum(
        int(row["expected_bytes"]) for row in slide_rows if not row["local_complete"]
    )
    slide_counts = Counter(int(row["n_manifest_slides"]) for row in subject_rows)

    payload_complete = n_local_slides == n_slides
    content_verified = n_content_verified == n_slides
    current_status = (
        "DEVELOPMENT_SOURCE_PAYLOAD_VERIFIED_PREPROCESSING_GATE_H2_LOCKED"
        if payload_complete and content_verified
        else STATUS
    )
    blocking_reason = (
        "WSI payload and GDC MD5 are complete; TCGA-CHIMERA recurrence threshold/censoring "
        "equivalence, independently validated tumor-region handling, disease-head minimum "
        "validity, effect-size power input, and the external embargo gate are not locked"
        if payload_complete and content_verified
        else
        "remaining WSI payload or GDC MD5 verification is incomplete; TCGA-CHIMERA recurrence "
        "threshold/censoring equivalence, tumor-region and patient aggregation rules, "
        "scanner/stain metadata, and a disease-head effect size for power simulation are not locked"
    )
    eligibility = [{
        "cohort_id": "TCGA-PRAD-current-GDC",
        "role": "development_isup_bcr_source_package",
        "n_subjects": n_subjects,
        "n_events": n_events,
        "n_treatment_documented": n_treatment,
        "n_treatment_documented_events": n_treatment_events,
        "n_manifest_slides": n_slides,
        "n_local_slides": n_local_slides,
        "n_content_verified_slides": n_content_verified,
        "n_all_slides_local_subjects": n_local_subjects,
        "n_all_slides_local_events": n_local_events,
        "missing_local_slide_bytes": missing_bytes,
        "bcr_time_unit": "days",
        "source_package_hash_locked": True,
        "development_analysis_ready": False,
        "h2_unlocked": False,
        "status": current_status,
        "blocking_reason": blocking_reason,
    }]
    eligibility_path = OUTPUT_DIR / "fm6_tcga_development_eligibility.csv"
    write_csv(eligibility_path, eligibility, list(eligibility[0]))

    slide_summary = [
        {"manifest_slides_per_subject": count, "n_subjects": n}
        for count, n in sorted(slide_counts.items())
    ]
    slide_summary_path = OUTPUT_DIR / "fm6_tcga_slide_count_summary.csv"
    write_csv(slide_summary_path, slide_summary, list(slide_summary[0]))

    harmonization = [
        {
            "field": "metric",
            "tcga": "reported_grade_group_or_fixed_Gleason_derivation",
            "chimera": "reported_ISUP_with_fixed_Gleason_consistency_QC",
            "status": "aligned_with_external_three_record_sensitivity_rule",
            "primary_pooling": "prohibited",
        },
        {
            "field": "bcr_event_definition",
            "tcga": "explicit_GDC_biochemical_recurrence_type",
            "chimera": "any_post_surgery_PSA_ge_0.1_ug_per_l",
            "status": "not_proven_threshold_equivalent",
            "primary_pooling": "prohibited",
        },
        {
            "field": "time",
            "tcga": "days_to_recurrence_or_max_days_to_follow_up",
            "chimera": "months_to_recurrence_or_last_PSA",
            "status": "unit_convertible_but_censoring_process_not_proven_equivalent",
            "primary_pooling": "prohibited",
        },
        {
            "field": "specimen",
            "tcga": "diagnostic_prostatectomy_WSI_manifest",
            "chimera": "prostatectomy_WSI",
            "status": "conceptually_aligned_specimen_verification_pending",
            "primary_pooling": "prohibited",
        },
        {
            "field": "treatment",
            "tcga": "radiation_and_pharmaceutical_documentation",
            "chimera": "earlier_therapy_without_complete_adjuvant_salvage_history",
            "status": "not_equivalent_incomplete_external_postoperative_treatment",
            "primary_pooling": "prohibited",
        },
    ]
    harmonization_path = OUTPUT_DIR / "fm6_tcga_chimera_endpoint_harmonization.csv"
    write_csv(harmonization_path, harmonization, list(harmonization[0]))

    chimera = read_csv(CHIMERA_ELIGIBILITY)[0]
    power_rows = [
        {
            "cohort": "TCGA-PRAD-current-GDC",
            "role": "development",
            "n_subjects": n_subjects,
            "n_events": n_events,
            "analysis_universe": "WSI_ISUP_exact_BCR_time",
            "effect_input": "pending_locked_disease_head_and_delta_use",
            "simulation_status": "NOT_RUN_EFFECT_INPUT_UNAVAILABLE",
        },
        {
            "cohort": "CHIMERA-TASK1",
            "role": "independent_external_candidate",
            "n_subjects": 92,
            "n_events": int(chimera["n_bcr_events"]),
            "analysis_universe": "ISUP_Gleason_concordant_primary_universe",
            "effect_input": "pending_development_only_effect_distribution",
            "simulation_status": "NOT_RUN_EFFECT_INPUT_UNAVAILABLE",
        },
    ]
    power_path = OUTPUT_DIR / "fm6_power_simulation_input_status.csv"
    write_csv(power_path, power_rows, list(power_rows[0]))

    source_rows = [
        source_row("gdc_clinical_snapshot", GDC_SNAPSHOT, "patient_clinical_source", "never_serve"),
        source_row("tcga_wsi_remote_manifest", TCGA_MANIFEST, "wsi_file_id_and_size_lock", "project_internal"),
        source_row("tcga_dataset_access_manifest", TCGA_DATASET_MANIFEST, "shared_asset_authorization", "project_internal"),
        source_row("chimera_dataset_manifest", CHIMERA_DATASET_MANIFEST, "external_source_contract", "project_internal"),
        source_row("fm6_source_power_protocol", PROTOCOL, "protocol", "project_internal"),
        source_row("fm6_wsi_preprocessing_protocol", PREPROCESSING_PROTOCOL, "protocol", "project_internal"),
        source_row("fm6_entry_parser", ENTRY_AUDIT_SCRIPT, "endpoint_normalizer", "project_internal"),
        source_row("gdc_file_metadata", GDC_FILE_METADATA, "wsi_md5_source_lock", "never_serve"),
    ]
    source_rows.extend([
        source_row("normalized_development_subjects", subject_path, "patient_level_development_table", "never_serve"),
        source_row("development_slide_inventory", slide_path, "patient_level_slide_table", "never_serve"),
    ])
    if LOCAL_CONTENT_VERIFICATION.is_file():
        source_rows.append(
            source_row(
                "local_content_verification",
                LOCAL_CONTENT_VERIFICATION,
                "local_wsi_md5_verification",
                "never_serve",
            )
        )
    if FOLD_TABLE.is_file() and FOLD_CONFIG.is_file():
        source_rows.extend(
            [
                source_row("development_outer_folds", FOLD_TABLE, "patient_fold_manifest", "never_serve"),
                source_row("development_outer_fold_config", FOLD_CONFIG, "fold_hash_config", "project_internal"),
            ]
        )
    if LOCAL_HEADER_QC.is_file() and HEADER_QC_CONFIG.is_file():
        source_rows.extend(
            [
                source_row("development_wsi_header_qc", LOCAL_HEADER_QC, "patient_slide_technical_qc", "never_serve"),
                source_row("development_wsi_header_qc_config", HEADER_QC_CONFIG, "wsi_qc_hash_config", "project_internal"),
            ]
        )
    source_manifest_path = OUTPUT_DIR / "fm6_tcga_development_source_manifest.csv"
    write_csv(source_manifest_path, source_rows, list(source_rows[0]))

    report_path = OUTPUT_DIR / "fm6-development-source-package-report.md"
    report_path.write_text(
        f"""---
document_id: fm6-development-source-package-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: active
created: 2026-08-15
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_development_source_package/outputs/fm6-development-source-package-report.md
---

# FM6 TCGA-PRAD 개발 source package 보고서

- Protocol: `{PROTOCOL_ID}`
- 상태: **{current_status}**
- claim ceiling/H2 변화: **없음**

## 고정한 개발 source

- current-GDC clinical snapshot: {gdc_summary['n_cases']} cases, `{sha256_file(GDC_SNAPSHOT)}`
- WSI·ISUP·exact-BCR/time 개발 universe: **{n_subjects}명/{n_events} events**
- 방사선·약물치료 모두 documented: **{n_treatment}명/{n_treatment_events} events**
- remote-locked WSI: **{n_slides}장**; 환자당 {min(slide_counts)}–{max(slide_counts)}장
- 현재 완전 로컬 WSI 환자: **{n_local_subjects}명/{n_local_events} events**,
  slide {n_local_slides}/{n_slides}장
- GDC MD5 content 검증: **{n_content_verified}/{n_slides}장**
- 미확보 payload: **{missing_bytes} bytes**

GDC snapshot, WSI file UUID/size manifest, endpoint normalizer와 patient-level 정규화표를
SHA-256으로 묶었다. 환자별 임상·slide 표는 ignored local-data에 보존하고 포털에는
`never_serve`로 등록했다.

## Harmonization 판정

TCGA의 event는 GDC에 biochemical recurrence type이 명시되고 recurrence day가 있는 경우다.
CHIMERA는 수술 후 PSA `>=0.1 ug/L`이라는 명시 threshold를 사용한다. 시간 단위는 각각
days/months로 변환 가능하지만, TCGA의 PSA threshold와 censoring 관찰과정이 CHIMERA와
동일하다고 입증되지 않았다. 따라서 **두 코호트의 patient-level pooling은 금지**하고,
TCGA에서 규칙을 고정한 뒤 CHIMERA에는 재학습 없는 external transport만 허용 후보로 둔다.

## 아직 실행할 수 없는 것

payload·GDC MD5, outcome-blind WSI 기술 QC, 환자 단위 fold, 물리 FOV와 slide/환자 primary
aggregation 규칙은 고정했다. 그러나 이 패키지는 아직 development analysis-ready가 아니다.
독립 검증된 tumor-region 처리, TCGA–CHIMERA endpoint equivalence, disease-head 최소 유효성과
`delta_use` effect input이 없다. 그러므로 power simulation, disease head 학습, targeted
erasure, 외부 결과 및 residual marker 탐색은 계속 잠근다. CHIMERA의 27 events를 근거 없이
strong external H2에 충분하다고 간주하지 않는다.
""",
        encoding="utf-8",
    )

    output_paths = [
        eligibility_path,
        slide_summary_path,
        harmonization_path,
        power_path,
        source_manifest_path,
        report_path,
    ]
    config = {
        "protocol_id": PROTOCOL_ID,
        "status": current_status,
        "claim_ceiling_changed": False,
        "h2_unlocked": False,
        "development_analysis_ready": False,
        "gdc_snapshot_retrieved_at_utc": snapshot["retrieved_at_utc"],
        "gdc_snapshot_sha256": sha256_file(GDC_SNAPSHOT),
        "normalized_subjects_sha256": sha256_file(subject_path),
        "development_slides_sha256": sha256_file(slide_path),
        "script_sha256": sha256_file(Path(__file__)),
        "summary": {
            "n_subjects": n_subjects,
            "n_events": n_events,
            "n_treatment_documented": n_treatment,
            "n_treatment_documented_events": n_treatment_events,
            "n_manifest_slides": n_slides,
            "n_local_slides": n_local_slides,
            "n_content_verified_slides": n_content_verified,
            "n_all_slides_local_subjects": n_local_subjects,
            "n_all_slides_local_events": n_local_events,
            "missing_local_slide_bytes": missing_bytes,
        },
        "output_sha256": {path.name: sha256_file(path) for path in output_paths},
        "execution_time_seconds": round(time.time() - started, 6),
        "volatile_fields": ["execution_time_seconds"],
    }
    config_path = OUTPUT_DIR / "fm6_development_source_run_config.json"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": current_status, "summary": config["summary"]}, indent=2))
    verification_failed = bool(args.verify_local_content and n_content_verified != n_slides)
    if download_failures or verification_failed:
        print(json.dumps({"download_failures": download_failures}, indent=2), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
