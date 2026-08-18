#!/usr/bin/env python3
"""Acquire and audit the public CHIMERA Task 1 external ISUP--BCR cohort."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MILESTONE_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = MILESTONE_ROOT / "outputs"
LOCAL_ROOT = (
    REPOSITORY_ROOT
    / "resources"
    / "data"
    / "quantitative_foundation_model_validation"
    / "local-data"
    / "chimera_task1"
)
LOCAL_INVENTORY = LOCAL_ROOT / "source_inventory.csv"
LOCAL_CLINICAL_TABLE = LOCAL_ROOT / "normalized_clinical.csv"
LOCAL_LOCK = LOCAL_ROOT / ".acquisition.lock"

PROTOCOL_ID = "QFMV-FM6-EXTERNAL-ACQUISITION-2026-08-14-001"
BUCKET_BASE = "https://chimera-challenge.s3.amazonaws.com"
TASK_PREFIX = "v2/task1/"
LIST_URL = f"{BUCKET_BASE}/"
OFFICIAL_DATA_URL = "https://chimera.grand-challenge.org/dataset-download/"
LICENSE = "CC-BY-NC-SA-4.0"
PUBLICATION_POLICY = "embargo_until_challenge_and_baseline_journal_papers_are_published"
BCR_DEFINITION = "any_post_surgery_psa_ge_0.1_ug_per_l"
BCR_TIME_UNIT = "months"
RETRIEVED_ON = "2026-08-14"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
CHUNK_BYTES = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_isup_grade_group(primary: int, secondary: int) -> int:
    """Derive the standard Grade Group from primary and secondary Gleason patterns."""
    score = primary + secondary
    if score <= 6:
        return 1
    if (primary, secondary) == (3, 4):
        return 2
    if (primary, secondary) == (4, 3):
        return 3
    if score == 8:
        return 4
    if score >= 9:
        return 5
    raise ValueError(f"unsupported Gleason combination: {primary}+{secondary}")


def source_field_state(payload: dict[str, Any], key: str) -> str:
    """Preserve missing-key, null, blank and observed source states."""
    if key not in payload:
        return "missing_key"
    value = payload[key]
    if value is None:
        return "null"
    if isinstance(value, str) and not value.strip():
        return "blank"
    return "observed"


def verify_local_inventory_hashes(
    inventory_path: Path = LOCAL_INVENTORY,
    repository_root: Path = REPOSITORY_ROOT,
    *,
    progress: bool = False,
) -> dict[str, Any]:
    """Recompute every locally acquired object hash without network access."""
    rows = read_csv(inventory_path)
    if not rows:
        raise ValueError(f"empty or missing source inventory: {inventory_path}")
    failures: list[dict[str, str]] = []
    verified_bytes = 0
    for index, row in enumerate(rows, start=1):
        path = repository_root / row["local_relative_path"]
        reason = ""
        observed_sha256 = ""
        if not path.is_file():
            reason = "missing_file"
        elif path.stat().st_size != int(row["remote_size"]):
            reason = "size_mismatch"
        else:
            observed_sha256 = sha256_file(path)
            verified_bytes += path.stat().st_size
            if observed_sha256 != row["sha256"]:
                reason = "sha256_mismatch"
        if reason:
            failures.append(
                {
                    "remote_key": row["remote_key"],
                    "reason": reason,
                    "expected_sha256": row.get("sha256", ""),
                    "observed_sha256": observed_sha256,
                }
            )
        if progress and (index % 25 == 0 or index == len(rows)):
            print(
                f"[verify {index}/{len(rows)}] bytes={verified_bytes} "
                f"failures={len(failures)}",
                flush=True,
            )
    return {
        "status": "PASS" if not failures else "FAIL",
        "inventory_rows": len(rows),
        "verified_bytes": verified_bytes,
        "failure_count": len(failures),
        "failures": failures,
    }


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def acquire_process_lock():
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    handle = LOCAL_LOCK.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError("another CHIMERA acquisition process is already running") from error
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def list_task_objects() -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        query: dict[str, str] = {"list-type": "2", "prefix": TASK_PREFIX}
        if token:
            query["continuation-token"] = token
        url = f"{LIST_URL}?{urllib.parse.urlencode(query)}"
        with urllib.request.urlopen(url, timeout=120) as response:
            root = ET.fromstring(response.read())
        for item in root.findall("s3:Contents", S3_NS):
            objects.append(
                {
                    "key": item.findtext("s3:Key", default="", namespaces=S3_NS),
                    "size": int(item.findtext("s3:Size", default="0", namespaces=S3_NS)),
                    "etag": item.findtext("s3:ETag", default="", namespaces=S3_NS).strip('"'),
                    "last_modified": item.findtext(
                        "s3:LastModified", default="", namespaces=S3_NS
                    ),
                }
            )
        if root.findtext("s3:IsTruncated", default="false", namespaces=S3_NS) != "true":
            break
        token = root.findtext("s3:NextContinuationToken", namespaces=S3_NS)
        if not token:
            raise RuntimeError("S3 listing is truncated without a continuation token")
    return objects


def object_role(key: str) -> str | None:
    if key.startswith(f"{TASK_PREFIX}clinical_data/") and key.endswith(".json"):
        return "clinical_json"
    if key.startswith(f"{TASK_PREFIX}pathology/images/") and key.endswith("_tissue.tif"):
        return "tissue_mask"
    if key.startswith(f"{TASK_PREFIX}pathology/images/") and key.endswith(".tif"):
        return "prostatectomy_wsi"
    return None


def local_path_for_key(key: str) -> Path:
    if not key.startswith(TASK_PREFIX):
        raise ValueError(f"object is outside Task 1 prefix: {key}")
    relative = Path(key.removeprefix(TASK_PREFIX))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe object key: {key}")
    return LOCAL_ROOT / relative


def object_url(key: str) -> str:
    return f"{BUCKET_BASE}/{urllib.parse.quote(key, safe='/')}"


def download_object(obj: dict[str, Any], previous: dict[str, str]) -> dict[str, Any]:
    target = local_path_for_key(obj["key"])
    target.parent.mkdir(parents=True, exist_ok=True)
    expected_size = int(obj["size"])
    if target.is_file() and target.stat().st_size == expected_size:
        previous_hash = previous.get("sha256", "")
        if (
            previous.get("etag") == obj["etag"]
            and previous.get("remote_size") == str(expected_size)
            and len(previous_hash) == 64
        ):
            return {**obj, "path": target, "sha256": previous_hash, "reused": True}
        return {**obj, "path": target, "sha256": sha256_file(target), "reused": True}

    part = target.with_name(f"{target.name}.part")
    start = part.stat().st_size if part.is_file() else 0
    if start > expected_size:
        part.unlink()
        start = 0

    digest = hashlib.sha256()
    mode = "wb"
    headers: dict[str, str] = {}
    if start:
        with part.open("rb") as stream:
            for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
                digest.update(chunk)
        headers["Range"] = f"bytes={start}-"
        mode = "ab"

    request = urllib.request.Request(object_url(obj["key"]), headers=headers)
    with urllib.request.urlopen(request, timeout=300) as response:
        if start and response.status != 206:
            start = 0
            digest = hashlib.sha256()
            mode = "wb"
        with part.open(mode) as stream:
            while True:
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                stream.write(chunk)
                digest.update(chunk)

    if part.stat().st_size != expected_size:
        raise RuntimeError(
            f"size mismatch for {obj['key']}: {part.stat().st_size} != {expected_size}"
        )
    os.replace(part, target)
    return {**obj, "path": target, "sha256": digest.hexdigest(), "reused": False}


def acquire_objects(
    objects: list[dict[str, Any]], workers: int
) -> list[dict[str, Any]]:
    previous = {row["remote_key"]: row for row in read_csv(LOCAL_INVENTORY)}
    missing_bytes = sum(
        int(obj["size"])
        for obj in objects
        if not (
            local_path_for_key(obj["key"]).is_file()
            and local_path_for_key(obj["key"]).stat().st_size == int(obj["size"])
        )
    )
    free_bytes = shutil.disk_usage(LOCAL_ROOT.parent).free
    if free_bytes < missing_bytes + 5 * 1024**3:
        raise RuntimeError(
            f"insufficient free space: need {missing_bytes + 5 * 1024**3}, have {free_bytes}"
        )

    acquired: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_object, obj, previous.get(obj["key"], {})): obj
            for obj in objects
        }
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            acquired.append(result)
            print(
                f"[{index}/{len(objects)}] {'reused' if result['reused'] else 'downloaded'} "
                f"{result['key']} ({result['size']} bytes)",
                flush=True,
            )
    return sorted(acquired, key=lambda row: row["key"])


def parse_clinical(acquired: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in acquired:
        if object_role(obj["key"]) != "clinical_json":
            continue
        payload = json.loads(obj["path"].read_text(encoding="utf-8"))
        subject_id = Path(obj["key"]).stem
        bcr = int(float(payload["BCR"]))
        isup_reported = int(payload["ISUP"])
        primary = int(payload["primary_gleason"])
        secondary = int(payload["secondary_gleason"])
        isup_derived = derive_isup_grade_group(primary, secondary)
        time_value = float(payload["time_to_follow-up/BCR"])
        bcr_psa_state = source_field_state(payload, "BCR_PSA")
        tertiary_state = source_field_state(payload, "tertiary_gleason")
        earlier_therapy = str(payload["earlier_therapy"])
        if bcr not in {0, 1} or not 1 <= isup_reported <= 5 or time_value < 0:
            raise ValueError(f"invalid ISUP/BCR fields for subject {subject_id}")
        if bcr == 1 and bcr_psa_state != "observed":
            raise ValueError(f"BCR event lacks observed recurrence PSA for subject {subject_id}")
        if float(payload["pre_operative_PSA"]) < 0:
            raise ValueError(f"negative pre-operative PSA for subject {subject_id}")
        if int(payload["positive_surgical_margins"]) not in {0, 1, 2}:
            raise ValueError(f"invalid surgical-margin state for subject {subject_id}")
        rows.append(
            {
                "subject_id": subject_id,
                "isup_grade_group_reported": isup_reported,
                "gleason_derived_isup_grade_group": isup_derived,
                "isup_gleason_consistency": (
                    "concordant" if isup_reported == isup_derived else "source_discordant"
                ),
                "primary_gleason": primary,
                "secondary_gleason": secondary,
                "tertiary_gleason": payload.get("tertiary_gleason"),
                "tertiary_gleason_source_state": tertiary_state,
                "bcr_event": bcr,
                "time_to_follow_up_or_bcr_months": time_value,
                "bcr_time_unit": BCR_TIME_UNIT,
                "bcr_definition": BCR_DEFINITION,
                "bcr_psa": payload.get("BCR_PSA"),
                "bcr_psa_source_state": bcr_psa_state,
                "age_at_prostatectomy": int(payload["age_at_prostatectomy"]),
                "earlier_therapy": earlier_therapy,
                "earlier_therapy_state": (
                    "unknown" if earlier_therapy.strip().lower() == "unknown" else "observed"
                ),
                "pre_operative_psa": float(payload["pre_operative_PSA"]),
                "pt_stage": str(payload["pT_stage"]),
                "positive_surgical_margins": int(payload["positive_surgical_margins"]),
                "positive_lymph_nodes": str(payload["positive_lymph_nodes"]),
                "capsular_penetration": str(payload["capsular_penetration"]),
                "invasion_seminal_vesicles": str(payload["invasion_seminal_vesicles"]),
                "lymphovascular_invasion": str(payload["lymphovascular_invasion"]),
            }
        )
    if len({row["subject_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate CHIMERA clinical subject IDs")
    return sorted(rows, key=lambda row: row["subject_id"])


def build_local_inventory(
    relevant: list[dict[str, Any]], acquired: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    acquired_by_key = {row["key"]: row for row in acquired}
    previous = {row["remote_key"]: row for row in read_csv(LOCAL_INVENTORY)}
    rows: list[dict[str, Any]] = []
    for obj in relevant:
        local_path = local_path_for_key(obj["key"])
        current = acquired_by_key.get(obj["key"])
        prior = previous.get(obj["key"], {})
        local_complete = local_path.is_file() and local_path.stat().st_size == int(obj["size"])
        sha256 = current["sha256"] if current else prior.get("sha256", "")
        if not local_complete:
            sha256 = ""
        rows.append(
            {
                "remote_key": obj["key"],
                "role": object_role(obj["key"]),
                "remote_size": obj["size"],
                "etag": obj["etag"],
                "last_modified": obj["last_modified"],
                "local_relative_path": str(local_path.relative_to(REPOSITORY_ROOT)),
                "local_complete": local_complete,
                "sha256": sha256,
            }
        )
    write_csv(LOCAL_INVENTORY, rows, list(rows[0].keys()))
    return rows


def aggregate_results(
    clinical_rows: list[dict[str, Any]], inventory_rows: list[dict[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    image_cases: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in inventory_rows:
        if row["role"] not in {"prostatectomy_wsi", "tissue_mask"}:
            continue
        parts = Path(row["remote_key"]).parts
        subject_id = parts[4]
        image_cases[subject_id][row["role"]] += 1

    clinical_ids = {str(row["subject_id"]) for row in clinical_rows}
    wsi_ids = {subject for subject, counts in image_cases.items() if counts["prostatectomy_wsi"]}
    wsi_stems = {
        row["remote_key"].removesuffix(".tif")
        for row in inventory_rows
        if row["role"] == "prostatectomy_wsi"
    }
    mask_stems = {
        row["remote_key"].removesuffix("_tissue.tif")
        for row in inventory_rows
        if row["role"] == "tissue_mask"
    }
    local_wsi = [
        row
        for row in inventory_rows
        if row["role"] == "prostatectomy_wsi" and str(row["local_complete"]).lower() == "true"
    ]
    local_masks = [
        row
        for row in inventory_rows
        if row["role"] == "tissue_mask" and str(row["local_complete"]).lower() == "true"
    ]
    complete_wsi_ids = {
        Path(row["remote_key"]).parts[4]
        for row in local_wsi
    }
    local_image_sha256_complete = sum(
        len(str(row["sha256"])) == 64
        for row in inventory_rows
        if row["role"] in {"prostatectomy_wsi", "tissue_mask"}
        and str(row["local_complete"]).lower() == "true"
    )
    slide_counts = Counter(
        counts["prostatectomy_wsi"] for counts in image_cases.values()
    )
    n_discordant = sum(
        row["isup_gleason_consistency"] == "source_discordant"
        for row in clinical_rows
    )
    summary = {
        "n_subjects": len(clinical_rows),
        "n_events": sum(int(row["bcr_event"]) for row in clinical_rows),
        "bcr_definition": BCR_DEFINITION,
        "bcr_time_unit": BCR_TIME_UNIT,
        "n_isup_complete": sum(
            row["isup_grade_group_reported"] is not None for row in clinical_rows
        ),
        "n_isup_gleason_concordant": len(clinical_rows) - n_discordant,
        "n_isup_gleason_discordant": n_discordant,
        "n_bcr_time_complete": sum(
            row["time_to_follow_up_or_bcr_months"] is not None for row in clinical_rows
        ),
        "n_bcr_psa_observed": sum(
            row["bcr_psa_source_state"] == "observed" for row in clinical_rows
        ),
        "n_earlier_therapy_documented": sum(
            row["earlier_therapy"] not in {None, ""} for row in clinical_rows
        ),
        "n_earlier_therapy_known": sum(
            row["earlier_therapy_state"] == "observed" for row in clinical_rows
        ),
        "n_remote_wsi": sum(counts["prostatectomy_wsi"] for counts in image_cases.values()),
        "n_remote_masks": sum(counts["tissue_mask"] for counts in image_cases.values()),
        "n_remote_wsi_mask_pairs": len(wsi_stems & mask_stems),
        "n_remote_unpaired_wsi": len(wsi_stems - mask_stems),
        "n_remote_unpaired_masks": len(mask_stems - wsi_stems),
        "n_wsi_subjects": len(wsi_ids),
        "n_clinical_wsi_linked": len(clinical_ids & wsi_ids),
        "clinical_wsi_subject_sets_equal": clinical_ids == wsi_ids,
        "n_local_wsi": len(local_wsi),
        "n_local_masks": len(local_masks),
        "n_local_wsi_subjects": len(complete_wsi_ids),
        "n_local_image_sha256_complete": local_image_sha256_complete,
        "min_wsi_per_subject": min(
            counts["prostatectomy_wsi"] for counts in image_cases.values()
        ),
        "max_wsi_per_subject": max(
            counts["prostatectomy_wsi"] for counts in image_cases.values()
        ),
        "remote_image_bytes": sum(
            int(row["remote_size"])
            for row in inventory_rows
            if row["role"] in {"prostatectomy_wsi", "tissue_mask"}
        ),
        "local_image_bytes": sum(
            int(row["remote_size"])
            for row in inventory_rows
            if row["role"] in {"prostatectomy_wsi", "tissue_mask"}
            and str(row["local_complete"]).lower() == "true"
        ),
    }
    grade_rows: list[dict[str, Any]] = []
    for grade in range(1, 6):
        selected = [
            row for row in clinical_rows if row["isup_grade_group_reported"] == grade
        ]
        grade_rows.append(
            {
                "isup_grade_group": grade,
                "n_subjects": len(selected),
                "n_bcr_events": sum(int(row["bcr_event"]) for row in selected),
            }
        )
    therapy_counts = Counter(str(row["earlier_therapy"]) for row in clinical_rows)
    therapy_rows = [
        {"earlier_therapy": key, "n_subjects": value}
        for key, value in sorted(therapy_counts.items())
    ]
    slide_rows = [
        {"wsi_per_subject": count, "n_subjects": n_subjects}
        for count, n_subjects in sorted(slide_counts.items())
    ]
    qc_rows = [
        {
            "check_id": "isup_gleason_concordance",
            "value": summary["n_isup_gleason_concordant"],
            "denominator": summary["n_subjects"],
            "status": "QC_FLAGGED",
            "interpretation": (
                f"{summary['n_isup_gleason_discordant']} source records disagree with "
                "the standard primary/secondary Gleason-to-Grade-Group mapping"
            ),
        },
        {
            "check_id": "bcr_time_unit",
            "value": BCR_TIME_UNIT,
            "denominator": summary["n_subjects"],
            "status": "PASS",
            "interpretation": "official CHIMERA Task 1 reference-standard unit",
        },
        {
            "check_id": "clinical_wsi_subject_linkage",
            "value": summary["n_clinical_wsi_linked"],
            "denominator": summary["n_subjects"],
            "status": "PASS" if summary["clinical_wsi_subject_sets_equal"] else "FAIL",
            "interpretation": "clinical and pathology subject sets must be identical",
        },
        {
            "check_id": "wsi_mask_pairing",
            "value": summary["n_remote_wsi_mask_pairs"],
            "denominator": summary["n_remote_wsi"],
            "status": (
                "PASS"
                if not summary["n_remote_unpaired_wsi"]
                and not summary["n_remote_unpaired_masks"]
                else "FAIL"
            ),
            "interpretation": "every WSI must have exactly one foreground/background mask",
        },
    ]
    return grade_rows, therapy_rows, slide_rows, qc_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Download the 190 prostatectomy WSIs and their 190 tissue masks.",
    )
    parser.add_argument(
        "--offline-verify",
        action="store_true",
        help="Recompute every acquired object SHA-256 without network access.",
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        raise ValueError("workers must be between 1 and 8")
    if args.offline_verify and args.download_images:
        raise ValueError("--offline-verify and --download-images are mutually exclusive")

    started = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    process_lock = acquire_process_lock()

    if args.offline_verify:
        verification = verify_local_inventory_hashes(progress=True)
        print(json.dumps(verification, ensure_ascii=False, indent=2))
        process_lock.close()
        if verification["status"] != "PASS":
            raise RuntimeError("local CHIMERA inventory verification failed")
        return 0

    task_objects = list_task_objects()
    relevant = [obj for obj in task_objects if object_role(obj["key"])]
    clinical_objects = [obj for obj in relevant if object_role(obj["key"]) == "clinical_json"]
    image_objects = [obj for obj in relevant if object_role(obj["key"]) != "clinical_json"]
    selected = clinical_objects + (image_objects if args.download_images else [])
    acquired = acquire_objects(selected, workers=args.workers)
    inventory_rows = build_local_inventory(relevant, acquired)
    clinical_rows = parse_clinical(acquired)
    write_csv(LOCAL_CLINICAL_TABLE, clinical_rows, list(clinical_rows[0].keys()))

    grade_rows, therapy_rows, slide_rows, qc_rows, summary = aggregate_results(
        clinical_rows, inventory_rows
    )
    image_complete = (
        summary["n_local_wsi"] == summary["n_remote_wsi"]
        and summary["n_local_masks"] == summary["n_remote_masks"]
        and summary["n_local_wsi_subjects"] == summary["n_subjects"]
        and summary["clinical_wsi_subject_sets_equal"]
        and summary["n_remote_unpaired_wsi"] == 0
        and summary["n_remote_unpaired_masks"] == 0
        and summary["n_local_image_sha256_complete"]
        == summary["n_remote_wsi"] + summary["n_remote_masks"]
    )
    status = (
        "ACQUIRED_EXTERNAL_COHORT_SEMANTIC_QC_FLAGGED_PUBLICATION_EMBARGO_H2_LOCKED"
        if image_complete
        else "METADATA_ACQUIRED_IMAGE_PAYLOAD_PENDING"
    )

    eligibility_rows = [
        {
            "cohort_id": "CHIMERA-TASK1",
            "role": "independent_external_isup_bcr_candidate_qc_hold",
            "n_subjects": summary["n_subjects"],
            "n_bcr_events": summary["n_events"],
            "n_wsi_subjects": summary["n_wsi_subjects"],
            "n_isup_complete": summary["n_isup_complete"],
            "n_isup_gleason_concordant": summary["n_isup_gleason_concordant"],
            "n_isup_gleason_discordant": summary["n_isup_gleason_discordant"],
            "n_bcr_time_complete": summary["n_bcr_time_complete"],
            "bcr_time_unit": BCR_TIME_UNIT,
            "bcr_definition": BCR_DEFINITION,
            "n_earlier_therapy_documented": summary["n_earlier_therapy_documented"],
            "n_earlier_therapy_known": summary["n_earlier_therapy_known"],
            "min_wsi_per_subject": summary["min_wsi_per_subject"],
            "max_wsi_per_subject": summary["max_wsi_per_subject"],
            "local_wsi_complete": image_complete,
            "license": LICENSE,
            "publication_policy": PUBLICATION_POLICY,
            "status": status,
            "external_analysis_ready": False,
            "h2_unlocked": False,
            "blocking_reason": (
                "official publication embargo remains active; three reported ISUP/Gleason records "
                "require a locked discrepancy rule; post-prostatectomy adjuvant/salvage treatment "
                "fields, TCGA endpoint harmonization, tumor-region selection, and a powered locked "
                "H2 analysis protocol are absent"
            ),
        }
    ]
    eligibility_path = OUTPUT_DIR / "fm6_external_cohort_eligibility.csv"
    write_csv(eligibility_path, eligibility_rows, list(eligibility_rows[0].keys()))
    grade_path = OUTPUT_DIR / "fm6_chimera_isup_bcr_summary.csv"
    write_csv(grade_path, grade_rows, list(grade_rows[0].keys()))
    therapy_path = OUTPUT_DIR / "fm6_chimera_earlier_therapy_summary.csv"
    write_csv(therapy_path, therapy_rows, list(therapy_rows[0].keys()))
    slide_path = OUTPUT_DIR / "fm6_chimera_slide_count_summary.csv"
    write_csv(slide_path, slide_rows, list(slide_rows[0].keys()))
    qc_path = OUTPUT_DIR / "fm6_chimera_clinical_qc_summary.csv"
    write_csv(qc_path, qc_rows, list(qc_rows[0].keys()))

    report = f"""---
document_id: fm6-external-cohort-acquisition-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: active
created: 2026-08-14
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_external_cohort_acquisition/outputs/fm6-external-cohort-acquisition-report.md
---

# FM6 외부 ISUP–BCR 코호트 확보 보고서

- Protocol: `{PROTOCOL_ID}`
- 코호트: `CHIMERA Task 1`
- 공식 원천: [{OFFICIAL_DATA_URL}]({OFFICIAL_DATA_URL})
- 이용조건: `{LICENSE}` 및 `{PUBLICATION_POLICY}`
- 상태: **{status}**
- H2 허용 범위 변화: **없음**
- 포털 노출: acquisition 보고서는 `project_internal`; 원시자료·환자별 표·object inventory와
  embargo 대상 outcome-derived 표는 `never_serve`

## 확보 결과

- 임상 JSON: {summary['n_subjects']}명; reported ISUP {summary['n_isup_complete']}/{summary['n_subjects']},
  BCR status/time {summary['n_bcr_time_complete']}/{summary['n_subjects']}, BCR events {summary['n_events']}명
- BCR 정의·시간 단위: 수술 후 PSA `>=0.1 ug/L`; `{BCR_TIME_UNIT}`
- reported ISUP–primary/secondary Gleason 표준 매핑: concordant
  {summary['n_isup_gleason_concordant']}/{summary['n_subjects']}, source-discordant
  {summary['n_isup_gleason_discordant']}/{summary['n_subjects']}
- 원격 prostatectomy WSI: {summary['n_remote_wsi']}개, {summary['n_wsi_subjects']}명
- 원격 tissue mask: {summary['n_remote_masks']}개
- 환자당 WSI: {summary['min_wsi_per_subject']}–{summary['max_wsi_per_subject']}개; 후속 분석 전
  slide-to-subject aggregation을 고정해야 함
- 임상–WSI subject 연결: {summary['n_clinical_wsi_linked']}/{summary['n_subjects']}명
- 로컬 WSI/mask: {summary['n_local_wsi']}/{summary['n_remote_wsi']},
  {summary['n_local_masks']}/{summary['n_remote_masks']}
- 로컬 image payload: {summary['local_image_bytes']} / {summary['remote_image_bytes']} bytes
- `earlier_therapy` documented: {summary['n_earlier_therapy_documented']}/{summary['n_subjects']}명;
  known {summary['n_earlier_therapy_known']}/{summary['n_subjects']}명

임상 원천과 영상은 TCGA-PRAD와 독립된 CHIMERA Task 1 코호트다. 공개 임상 JSON에는
reported ISUP, primary/secondary/tertiary Gleason, BCR status, BCR 또는 censoring까지의
개월 단위 시간, pre-operative PSA, 연령, 병기, margin, 림프절·피막·정낭·림프혈관 침범과
`earlier_therapy`가 포함된다. `missing_key`, `blank`, `unknown`과 source의 `x` 상태는
환자별 local 정규화표에서 음성으로 바꾸지 않고 보존한다.

## 적격성 판정

CHIMERA Task 1은 동일 환자의 일반 H&E prostatectomy WSI, reported ISUP/Gleason 및
BCR status/time을 연결하므로 외부 ISUP–BCR **후보 source**의 핵심 구조 요건을 충족한다.
그러나 semantic QC와 분석 적격성은 아직 통과하지 않았으며 다음 이유로 강한 H2와
결과 공개를 계속 잠근다.

1. 공식 data page의 challenge/baseline journal paper 출판 전 embargo가 현재 명시돼 있다.
2. reported ISUP와 primary/secondary Gleason의 표준 매핑이 3명에서 불일치한다. 원본을
   수정하지 않고 사전 고정 제외·민감도 규칙을 적용해야 한다.
3. `earlier_therapy`는 있으나 수술 후 adjuvant/salvage 방사선·약물치료와 censoring 처리에
   필요한 완전한 치료 이력은 제공되지 않는다.
4. CHIMERA의 BCR threshold와 TCGA endpoint를 같은 estimand로 사용할 harmonization,
   tumor-region 선택, 가변 slide 수의 patient aggregation이 아직 고정되지 않았다.
5. TCGA source에서 고정할 disease head, ISUP subspace, matched-control erasure와 외부
   최소 사건 수·분석 기준이 아직 사전 등록되지 않았다.
6. 이 확보 단계에서는 CONCH/Virchow embedding, disease head 또는 추론적 outcome 분석을
   수행하지 않았다. ISUP별 사건 수는 source-integrity 기술표로만 생성했으며 embargo 동안
   포털·외부 결과 route에 노출하지 않는다.

따라서 이 코호트는 `independent_external_isup_bcr_candidate_qc_hold`로 등록하되,
embargo 해제 확인, semantic discrepancy 규칙과 H2 protocol 고정 전에는 모델 결과를
산출·공개하지 않는다.
"""
    report_path = OUTPUT_DIR / "fm6-external-cohort-acquisition-report.md"
    report_path.write_text(report, encoding="utf-8")

    source_rows = [
        {
            "source_id": "chimera_task1_s3_inventory",
            "local_path": str(LOCAL_INVENTORY.relative_to(REPOSITORY_ROOT)),
            "bytes": LOCAL_INVENTORY.stat().st_size,
            "sha256": sha256_file(LOCAL_INVENTORY),
            "tracked": False,
            "role": "object_level_source_inventory",
            "portal_visibility": "never_serve",
        },
        {
            "source_id": "chimera_task1_normalized_clinical",
            "local_path": str(LOCAL_CLINICAL_TABLE.relative_to(REPOSITORY_ROOT)),
            "bytes": LOCAL_CLINICAL_TABLE.stat().st_size,
            "sha256": sha256_file(LOCAL_CLINICAL_TABLE),
            "tracked": False,
            "role": "patient_level_normalized_clinical_source",
            "portal_visibility": "never_serve",
        },
    ]
    source_path = OUTPUT_DIR / "fm6_external_source_manifest.csv"
    write_csv(source_path, source_rows, list(source_rows[0].keys()))

    deterministic_outputs = [
        eligibility_path,
        grade_path,
        therapy_path,
        slide_path,
        qc_path,
        report_path,
        source_path,
    ]
    config = {
        "protocol_id": PROTOCOL_ID,
        "cohort_id": "CHIMERA-TASK1",
        "official_data_url": OFFICIAL_DATA_URL,
        "source_prefix": TASK_PREFIX,
        "retrieved_on": RETRIEVED_ON,
        "license": LICENSE,
        "publication_policy": PUBLICATION_POLICY,
        "bcr_definition": BCR_DEFINITION,
        "bcr_time_unit": BCR_TIME_UNIT,
        "status": status,
        "h2_unlocked": False,
        "claim_ceiling_changed": False,
        "download_images_requested": args.download_images,
        "summary": summary,
        "local_inventory_sha256": sha256_file(LOCAL_INVENTORY),
        "local_clinical_sha256": sha256_file(LOCAL_CLINICAL_TABLE),
        "script_sha256": sha256_file(Path(__file__)),
        "output_sha256": {path.name: sha256_file(path) for path in deterministic_outputs},
        "execution_time_seconds": round(time.time() - started, 6),
        "volatile_fields": ["execution_time_seconds"],
    }
    config_path = OUTPUT_DIR / "fm6_external_cohort_run_config.json"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "summary": summary}, ensure_ascii=False, indent=2))
    process_lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
