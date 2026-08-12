#!/usr/bin/env python3
"""Human G8 adjudication and reproducible P0-M9 handoff support.

Human approvals are append-only source records. Derived G8/G9 matrices are
written separately from the P0-M8 draft so a clean M8 rerun cannot silently
erase or fabricate an approval.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
PREEXPERIMENT = ROOT / "projects/quantitative_foundation_model_validation/preexperiment"
PORTAL_ROOT = Path(__file__).resolve().parent
RECORDS_DIR = PREEXPERIMENT / "governance_records"
RUN_SCRIPT = PREEXPERIMENT / "run_preexperiment.py"
FM1_OUTPUT_DIR = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm1_metric_eligibility/outputs"
FM1_OUTPUTS = (
    "FM1_REPORT.md",
    "fm1_summary.csv",
    "medical_metric_eligibility.tsv",
    "analysis_measure_boundary.tsv",
    "metric_endpoint_independence.tsv",
    "study_local_reference_candidates.tsv",
    "run_config.json",
)
MAIN_STUDY_OUTPUTS = {
    "fm1": (FM1_OUTPUT_DIR, FM1_OUTPUTS),
    "fm2": (
        ROOT / "projects/quantitative_foundation_model_validation/milestones/fm2_paired_manifest/outputs",
        ("FM2_REPORT.md", "paired_sample_manifest.csv", "manifest_qc.csv", "exclusion_flow.csv", "run_config.json"),
    ),
    "fm3": (
        ROOT / "projects/quantitative_foundation_model_validation/milestones/fm3_paired_embeddings/outputs",
        ("FM3_REPORT.md", "embedding_bundle_manifest.csv", "embedding_row_manifest.csv", "run_config.json"),
    ),
    "fm4": (
        ROOT / "projects/quantitative_foundation_model_validation/milestones/fm4_concept_benchmark/outputs",
        ("FM4_ENTRY_DECISION.md", "analysis_family.csv", "power_precision_plan.csv", "fm4_entry_checklist.csv", "fm4_shared_fold_manifest.csv", "run_config.json"),
    ),
}
FM4_APPROVAL_ATTESTATIONS = (
    "reviewed_fm4_packet",
    "accept_exploratory_scope",
    "accept_power_limit",
    "accept_fm4_prohibitions",
    "fm4_identity_attested",
)
PROTOCOL_ID = "P0-QFMV-2026-08-11-APPROVED-001"
REQUIRED_ROLES = ("research_lead",)
ADVISORY_ROLES = ("pathology", "statistics", "ml_data")
ALL_ROLES = REQUIRED_ROLES + ADVISORY_ROLES
ROLE_LABELS = {
    "research_lead": "연구책임자",
    "pathology": "병리",
    "statistics": "통계",
    "ml_data": "ML/데이터",
}
ALLOWED_DECISIONS = {"conditional_go", "revise", "stop"}
REQUIRED_ATTESTATIONS = (
    "reviewed_evidence",
    "accept_scope",
    "accept_risks",
    "accept_prohibitions",
    "identity_attested",
)
APPROVED_COMBINATIONS = (
    "CONCH–tumor_fraction–shared_394.24um–descriptive_only",
    "Virchow–tumor_fraction–shared_394.24um–descriptive_only",
)
PERMANENT_PROHIBITIONS = (
    "confirmatory target designation without measurement repeatability",
    "clinical or whole-slide PNI diagnostic inference",
    "encoder superiority inference",
    "scanner/stain robustness inference",
    "H2 disease-prediction analysis without an independent metric–endpoint pair, adequate subjects/events, and external validation",
)
EVIDENCE_FILES = (
    "PROTOCOL.md",
    "P0_REPORT.md",
    "integrated_gate_summary.csv",
    "p0_question_answer_matrix.csv",
    "model_target_fov_decision.csv",
    "unresolved_risk_register.csv",
    "p0_gate_matrix.csv",
    "main_study_unlock_matrix.csv",
    "concept_summary.csv",
    "scale_sampling_sensitivity.csv",
    "measurement_provenance.csv",
    "claim_evidence_matrix.csv",
    "run_config.json",
)
M9_REPORTS = (
    "positive_control_report.md",
    "M4_FEASIBILITY_REPORT.md",
    "M5_TECHNICAL_REPORT.md",
    "M6_CONCEPT_REPORT.md",
    "M7_ROBUSTNESS_REPORT.md",
    "P0_REPORT.md",
)
M9_ARRAYS = (
    "precise_conch_shared_fov_embeddings.npy",
    "precise_virchow_shared_fov_embeddings.npy",
    "precise_virchow_native_fov_embeddings.npy",
)


class GovernanceError(RuntimeError):
    """Raised when a governance gate cannot safely advance."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evidence_snapshot(evidence_dir: Path = PREEXPERIMENT) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for name in EVIDENCE_FILES:
        path = evidence_dir / name
        if not path.is_file():
            raise GovernanceError(f"필수 G8 근거 파일이 없습니다: {name}")
        files.append({"name": name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    snapshot = {"protocol_id": PROTOCOL_ID, "files": files}
    snapshot["snapshot_sha256"] = canonical_hash(snapshot)
    return snapshot


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise GovernanceError(f"손상된 승인 기록 {path}:{line_number}") from exc
    return records


def approval_records(records_dir: Path = RECORDS_DIR) -> list[dict[str, Any]]:
    return _read_jsonl(records_dir / "g8_approval_records.jsonl")


@contextmanager
def governance_lock(records_dir: Path):
    """Serialize append/finalize operations across portal and CLI processes."""
    records_dir.mkdir(parents=True, exist_ok=True)
    with (records_dir / ".governance.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def m9_execution_lock(records_dir: Path):
    """Prevent duplicate full-GPU reruns across multiple portal/CLI processes."""
    records_dir.mkdir(parents=True, exist_ok=True)
    with (records_dir / ".m9_execution.lock").open("a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GovernanceError("P0-M9 clean rerun이 다른 프로세스에서 이미 실행 중입니다.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def latest_approvals(records_dir: Path = RECORDS_DIR) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in approval_records(records_dir):
        role = record.get("reviewer_role")
        if role in ALL_ROLES:
            latest[role] = record
    return latest


def append_approval(
    payload: dict[str, Any],
    *,
    records_dir: Path = RECORDS_DIR,
    evidence_dir: Path = PREEXPERIMENT,
) -> dict[str, Any]:
    role = str(payload.get("reviewer_role", "")).strip()
    name = str(payload.get("reviewer_name", "")).strip()
    decision = str(payload.get("decision", "")).strip()
    signature = str(payload.get("signature", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    if role not in ALL_ROLES:
        raise GovernanceError("허용되지 않은 reviewer role입니다.")
    if len(name) < 2 or len(name) > 120:
        raise GovernanceError("검토자 실명을 입력하십시오.")
    if signature != name:
        raise GovernanceError("전자서명란에 검토자 실명을 동일하게 입력하십시오.")
    if decision not in ALLOWED_DECISIONS:
        raise GovernanceError("허용되지 않은 G8 판정입니다.")
    attestations = {key: bool(payload.get(key)) for key in REQUIRED_ATTESTATIONS}
    if decision == "conditional_go" and not all(attestations.values()):
        missing = [key for key, accepted in attestations.items() if not accepted]
        raise GovernanceError(f"Conditional Go에 필요한 확인 항목이 빠졌습니다: {missing}")
    snapshot = evidence_snapshot(evidence_dir)
    with governance_lock(records_dir):
        if (records_dir / "g8_approval_manifest.json").exists():
            raise GovernanceError("G8이 이미 확정되어 승인 ledger가 잠겼습니다.")
        if evidence_snapshot(evidence_dir)["snapshot_sha256"] != snapshot["snapshot_sha256"]:
            raise GovernanceError("승인 처리 중 근거 snapshot이 변경되었습니다. 다시 검토하십시오.")
        previous = approval_records(records_dir)
        previous_record = previous[-1]["record_sha256"] if previous else ""
        previous_for_role = next(
            (item["record_sha256"] for item in reversed(previous) if item.get("reviewer_role") == role),
            "",
        )
        record: dict[str, Any] = {
            "schema_version": "g8-approval-1.0",
            "protocol_id": PROTOCOL_ID,
            "reviewer_name": name,
            "reviewer_role": role,
            "reviewer_role_label": ROLE_LABELS[role],
            "decision": decision,
            "attestations": attestations,
            "approved_combinations": list(APPROVED_COMBINATIONS) if decision == "conditional_go" else [],
            "permanent_prohibitions": list(PERMANENT_PROHIBITIONS),
            "notes": notes,
            "submitted_at_utc": utc_now(),
            "evidence_snapshot_sha256": snapshot["snapshot_sha256"],
            "previous_record_sha256": previous_record,
            "previous_role_record_sha256": previous_for_role,
        }
        record["record_sha256"] = canonical_hash(record)
        with (records_dir / "g8_approval_records.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        snapshot_path = records_dir / f"evidence_snapshot_{snapshot['snapshot_sha256']}.json"
        if not snapshot_path.exists():
            snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return record


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def g8_readiness(
    *, records_dir: Path = RECORDS_DIR, evidence_dir: Path = PREEXPERIMENT,
) -> dict[str, Any]:
    latest = latest_approvals(records_dir)
    snapshot = evidence_snapshot(evidence_dir)
    role_status = {}
    for role in ALL_ROLES:
        record = latest.get(role)
        role_status[role] = {
            "label": ROLE_LABELS[role],
            "required": role in REQUIRED_ROLES,
            "present": record is not None,
            "reviewer_name": record.get("reviewer_name", "") if record else "",
            "decision": record.get("decision", "pending") if record else "pending",
            "submitted_at_utc": record.get("submitted_at_utc", "") if record else "",
            "evidence_current": bool(record and record.get("evidence_snapshot_sha256") == snapshot["snapshot_sha256"]),
            "record_sha256": record.get("record_sha256", "") if record else "",
        }
    required_status = [role_status[role] for role in REQUIRED_ROLES]
    complete = all(item["present"] for item in required_status)
    unanimous = complete and all(item["decision"] == "conditional_go" for item in required_status)
    evidence_current = complete and all(item["evidence_current"] for item in required_status)
    return {
        "roles": role_status,
        "required_roles": list(REQUIRED_ROLES),
        "advisory_roles": list(ADVISORY_ROLES),
        "required_role_count": len(REQUIRED_ROLES),
        "complete": complete,
        "unanimous_conditional_go": unanimous,
        "evidence_current": evidence_current,
        "ready_to_finalize": complete and unanimous and evidence_current,
        "evidence_snapshot_sha256": snapshot["snapshot_sha256"],
    }


def finalize_g8(
    *,
    records_dir: Path = RECORDS_DIR,
    evidence_dir: Path = PREEXPERIMENT,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir or records_dir
    with governance_lock(records_dir):
        final_path = output_dir / "g8_approval_manifest.json"
        if final_path.exists():
            return json.loads(final_path.read_text(encoding="utf-8"))
        readiness = g8_readiness(records_dir=records_dir, evidence_dir=evidence_dir)
        if not readiness["ready_to_finalize"]:
            raise GovernanceError("연구책임자의 최신 Conditional Go 승인과 동일 근거 snapshot이 필요합니다.")
        latest = latest_approvals(records_dir)
        approvals = [latest[role] for role in REQUIRED_ROLES]
        output_dir.mkdir(parents=True, exist_ok=True)
        finalized_at = utc_now()
        manifest: dict[str, Any] = {
            "schema_version": "g8-final-1.1",
            "protocol_id": PROTOCOL_ID,
            "decision": "Conditional Go",
            "status": "conditional_go_approved_pending_g9",
            "finalized_at_utc": finalized_at,
            "evidence_snapshot_sha256": readiness["evidence_snapshot_sha256"],
            "approval_record_sha256": [item["record_sha256"] for item in approvals],
            "approvers": [
                {key: item[key] for key in ("reviewer_name", "reviewer_role", "reviewer_role_label", "submitted_at_utc")}
                for item in approvals
            ],
            "governance_model": "independent_study_research_lead_final_approval",
            "advisory_reviews": [
                {
                    key: latest[role][key]
                    for key in ("reviewer_name", "reviewer_role", "reviewer_role_label", "decision", "submitted_at_utc")
                }
                for role in ADVISORY_ROLES
                if role in latest and latest[role].get("evidence_snapshot_sha256") == readiness["evidence_snapshot_sha256"]
            ],
            "approved_combinations": list(APPROVED_COMBINATIONS),
            "permanent_prohibitions": list(PERMANENT_PROHIBITIONS),
            "next_gate": "P0-M9 clean rerun and P0-G9 reproducibility handoff",
        }
        manifest["manifest_sha256"] = canonical_hash(manifest)
        (output_dir / "g8_approval_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_csv(
            output_dir / "g8_adjudication_summary.csv",
            ["reviewer_role", "reviewer_role_label", "reviewer_name", "decision", "submitted_at_utc", "record_sha256"],
            [
                {
                    "reviewer_role": item["reviewer_role"],
                    "reviewer_role_label": item["reviewer_role_label"],
                    "reviewer_name": item["reviewer_name"],
                    "decision": item["decision"],
                    "submitted_at_utc": item["submitted_at_utc"],
                    "record_sha256": item["record_sha256"],
                }
                for item in approvals
            ],
        )
        report = [
            "# P0-G8 연구책임자 최종 판정", "",
            f"- Protocol: `{PROTOCOL_ID}`",
            "- Decision: **Conditional Go**",
            f"- Finalized: `{finalized_at}`",
            f"- Evidence snapshot: `{readiness['evidence_snapshot_sha256']}`", "",
            "## 승인 model–target–FOV", "",
            *[f"- {item}" for item in APPROVED_COMBINATIONS], "",
            "## 필수 승인", "",
            *[
                f"- {item['reviewer_role_label']}: {item['reviewer_name']} — "
                f"{item['decision']} ({item['submitted_at_utc']})"
            for item in approvals
            ], "",
            "병리·통계·ML/데이터 검토는 이 독립 연구에서 비차단 자문이며, 필요 시 별도 기록한다.", "",
            "## 해제되지 않는 과학적 제한", "",
            *[f"- {item}" for item in PERMANENT_PROHIBITIONS], "",
            "이 기록은 P0-M9 clean rerun 진입만 승인한다. P0-G9 통과 전에는 대규모 본 연구 실행이 잠겨 있다.",
        ]
        (output_dir / "G8_FINAL_DECISION.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        return manifest


def _normalized_config(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    volatile = {
        "started_at_utc", "finished_at_utc", "execution_seconds", "git",
        "output_hashes_excluding_run_config",
    }

    def normalize(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: normalize(val) for key, val in item.items() if key not in volatile}
        if isinstance(item, list):
            return [normalize(val) for val in item]
        return item

    return normalize(value)


def m9_baseline_files(evidence_dir: Path = PREEXPERIMENT) -> list[str]:
    names = []
    for path in evidence_dir.iterdir():
        if path.is_file() and path.suffix.lower() in {".csv", ".tsv", ".md", ".npy"}:
            if path.name not in {"PROTOCOL.md"}:
                names.append(path.name)
    required = set(EVIDENCE_FILES) - {"PROTOCOL.md", "run_config.json"}
    required.update(M9_REPORTS)
    required.update(M9_ARRAYS)
    missing = sorted(name for name in required if not (evidence_dir / name).is_file())
    if missing:
        raise GovernanceError(f"M9 baseline 필수 산출물이 없습니다: {missing}")
    return sorted(set(names))


def compare_clean_rerun(
    attempt_dir: Path,
    *,
    baseline_dir: Path = PREEXPERIMENT,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    all_match = True
    for name in m9_baseline_files(baseline_dir):
        baseline = baseline_dir / name
        rerun = attempt_dir / name
        exists = rerun.is_file()
        left_hash = sha256_file(baseline)
        right_hash = sha256_file(rerun) if exists else ""
        match = exists and left_hash == right_hash
        rows.append({
            "artifact": name,
            "comparison": "byte_exact",
            "baseline_sha256": left_hash,
            "rerun_sha256": right_hash,
            "match": match,
            "notes": "" if match else ("missing rerun artifact" if not exists else "byte mismatch"),
        })
        all_match &= match
    baseline_config = baseline_dir / "run_config.json"
    rerun_config = attempt_dir / "run_config.json"
    config_match = rerun_config.is_file() and _normalized_config(baseline_config) == _normalized_config(rerun_config)
    rows.append({
        "artifact": "run_config.json",
        "comparison": "semantic_after_documented_volatile_field_exclusion",
        "baseline_sha256": sha256_file(baseline_config),
        "rerun_sha256": sha256_file(rerun_config) if rerun_config.is_file() else "",
        "match": config_match,
        "notes": "excluded: timestamps, execution seconds, git context, derived output hashes",
    })
    all_match &= config_match
    return rows, all_match


def _run_stage(stage: str, attempt_dir: Path, log_path: Path, extra: list[str] | None = None) -> None:
    command = [sys.executable, str(RUN_SCRIPT), "--stage", stage, *(extra or [])]
    environment = os.environ.copy()
    environment["P0_OUTPUT_DIR"] = str(attempt_dir)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {' '.join(command)}\n")
        log.flush()
        subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)


def run_m9_full(
    *, records_dir: Path = RECORDS_DIR, baseline_dir: Path = PREEXPERIMENT,
) -> dict[str, Any]:
    with m9_execution_lock(records_dir):
        return _run_m9_full_locked(records_dir=records_dir, baseline_dir=baseline_dir)


def _run_m9_full_locked(
    *, records_dir: Path = RECORDS_DIR, baseline_dir: Path = PREEXPERIMENT,
) -> dict[str, Any]:
    manifest_path = records_dir / "g8_approval_manifest.json"
    if not manifest_path.is_file():
        raise GovernanceError("P0-G8 finalize가 먼저 필요합니다.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "conditional_go_approved_pending_g9":
        raise GovernanceError("유효한 G8 Conditional Go manifest가 아닙니다.")
    if (records_dir / "g9_handoff_manifest.json").exists():
        raise GovernanceError("P0-G9 인계가 이미 확정되었습니다.")
    current_snapshot = evidence_snapshot(baseline_dir)["snapshot_sha256"]
    if current_snapshot != manifest.get("evidence_snapshot_sha256"):
        raise GovernanceError("승인 후 G8 근거 파일이 변경됐습니다. 연구책임자의 재검토가 필요합니다.")
    attempts_root = records_dir / "clean_rerun"
    attempts_root.mkdir(parents=True, exist_ok=True)
    attempt_id = datetime.now(timezone.utc).strftime("attempt-%Y%m%dT%H%M%SZ")
    attempt_dir = attempts_root / attempt_id
    attempt_dir.mkdir()
    shutil.copy2(baseline_dir / "PROTOCOL.md", attempt_dir / "PROTOCOL.md")
    log_path = attempt_dir / "m9_execution.log"
    status_path = records_dir / "m9_status.json"
    started = utc_now()
    status = {
        "status": "running", "attempt_id": attempt_id, "attempt_dir": str(attempt_dir),
        "started_at_utc": started, "mode": "full_gpu_clean_rerun",
    }
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        _run_stage("m3", attempt_dir, log_path)
        _run_stage("m4", attempt_dir, log_path)
        _run_stage("m5", attempt_dir, log_path, ["--m5-encoder", "conch"])
        _run_stage("m5", attempt_dir, log_path, ["--m5-encoder", "virchow"])
        _run_stage("m6", attempt_dir, log_path)
        _run_stage("m7-native", attempt_dir, log_path)
        _run_stage("m7", attempt_dir, log_path)
        _run_stage("m8", attempt_dir, log_path)
        comparison, reproducible = compare_clean_rerun(attempt_dir, baseline_dir=baseline_dir)
        _write_csv(
            attempt_dir / "clean_rerun_comparison.csv",
            ["artifact", "comparison", "baseline_sha256", "rerun_sha256", "match", "notes"],
            comparison,
        )
        with (attempt_dir / "source_inventory.csv").open(encoding="utf-8", newline="") as handle:
            source_inventory = list(csv.DictReader(handle))
        source_hashes_match = all(row["pre_post_match"] == "True" for row in source_inventory)
        clinician_hash_ok = any(
            row["source_id"] == "precise_clinician_review"
            and row["sha256_pre"] == "c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3"
            for row in source_inventory
        )
        passed = reproducible and source_hashes_match and clinician_hash_ok
        output_rows = []
        for path in sorted(attempt_dir.iterdir()):
            if path.is_file() and path.name not in {"output_hashes.csv", "reproducibility_manifest.json"}:
                output_rows.append({"artifact": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
        _write_csv(attempt_dir / "output_hashes.csv", ["artifact", "size_bytes", "sha256"], output_rows)
        reproducibility_manifest = {
            "schema_version": "p0-g9-1.0", "protocol_id": PROTOCOL_ID,
            "attempt_id": attempt_id, "mode": "full_gpu_clean_rerun",
            "started_at_utc": started, "finished_at_utc": utc_now(),
            "g8_manifest_sha256": manifest["manifest_sha256"],
            "all_deterministic_outputs_match": reproducible,
            "all_source_pre_post_hashes_match": source_hashes_match,
            "immutable_clinician_source_verified": clinician_hash_ok,
            "p0_g9_status": "pass" if passed else "revise_reproducibility_mismatch",
        }
        (attempt_dir / "reproducibility_manifest.json").write_text(
            json.dumps(reproducibility_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        status = {
            **status, "status": "pass" if passed else "revise", "finished_at_utc": utc_now(),
            "comparison_rows": len(comparison),
            "mismatch_count": sum(not bool(row["match"]) for row in comparison),
            "reproducibility_manifest": str(attempt_dir / "reproducibility_manifest.json"),
        }
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if passed:
            finalize_g9(attempt_dir, records_dir=records_dir, baseline_dir=baseline_dir)
        return status
    except Exception as exc:
        status = {**status, "status": "failed", "finished_at_utc": utc_now(), "error": str(exc)}
        status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        raise


def finalize_g9(
    attempt_dir: Path, *, records_dir: Path = RECORDS_DIR, baseline_dir: Path = PREEXPERIMENT,
) -> dict[str, Any]:
    reproducibility = json.loads((attempt_dir / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    if reproducibility.get("p0_g9_status") != "pass":
        raise GovernanceError("P0-G9 reproducibility 조건이 충족되지 않았습니다.")
    g8 = json.loads((records_dir / "g8_approval_manifest.json").read_text(encoding="utf-8"))
    finalized_at = utc_now()
    gate_fields, gates = _read_csv(baseline_dir / "p0_gate_matrix.csv")
    approver_text = "; ".join(
        f"{item['reviewer_name']} ({item['reviewer_role_label']})" for item in g8["approvers"]
    )
    for row in gates:
        if row["gate_id"] == "P0-G8":
            row.update({
                "status": "conditional_go_approved", "draft_decision": "Conditional Go",
                "entry_condition_met": "True",
                "direct_evidence": "g8_approval_manifest.json; g8_adjudication_summary.csv; G8_FINAL_DECISION.md",
                "unresolved_risk": "scope-capped scientific limitations remain",
                "next_unlocked": "P0-M9 clean rerun", "approver": approver_text,
                "approval_timestamp": g8["finalized_at_utc"],
            })
        elif row["gate_id"] == "P0-G9":
            row.update({
                "status": "pass_clean_rerun_handoff", "draft_decision": "Pass",
                "entry_condition_met": "True",
                "direct_evidence": "reproducibility_manifest.json; output_hashes.csv; clean_rerun_comparison.csv; handoff_to_main_study.md",
                "unresolved_risk": "none for approved descriptive combinations; permanent scope caps remain",
                "next_unlocked": "FM1/FM2 and scope-capped descriptive FM3",
                "still_prohibited": "; ".join(PERMANENT_PROHIBITIONS),
                "approver": f"{g8['approvers'][0]['reviewer_name']} (research lead); automatic reproducibility gate",
                "approval_timestamp": finalized_at,
            })
    _write_csv(records_dir / "p0_gate_matrix_final.csv", gate_fields, gates)
    unlock_fields, unlock = _read_csv(baseline_dir / "main_study_unlock_matrix.csv")
    updates = {
        "FM0": ("ready_for_final_protocol_lock", "approved scope protocol lock", "clinical/confirmatory scope expansion"),
        "FM1": ("unlocked_eligibility_audit", "full metric eligibility and H1/H2 shortlist audit", "confirmatory designation without added evidence"),
        "FM2": ("unlocked_scope_capped_manifest", "paired manifest freeze for approved descriptive combinations", "unapproved cohort/target expansion"),
        "FM3": ("unlocked_descriptive_shared_fov_only", "CONCH/Virchow shared-394.24um tumor descriptive extraction", "confirmatory, clinical, PNI, superiority inference"),
        "FM4": ("preparation_only_additional_gate_required", "analysis schema and power planning", "H2 or confirmatory benchmark without independent target/endpoint"),
        "FM5": ("preparation_only_amber_scope", "paired descriptive comparison planning", "encoder superiority or scanner/stain robustness claim"),
        "FM6": ("locked_additional_scientific_evidence_required", "none", "H2/complementarity until independent metric-endpoint, power and external set"),
        "FM7": ("protocol_preparation_only", "external protocol planning", "transport inference without multiple sites and sentinel truth"),
        "FM10": ("handoff_bundle_ready_scope_capped", "claim audit and reproducible handoff", "clinical or confirmatory final claim"),
    }
    for row in unlock:
        if row["main_stage"] in updates:
            status, allowed, prohibited = updates[row["main_stage"]]
            row["current_status"] = status
            row["currently_allowed"] = allowed
            row["currently_prohibited"] = prohibited
            row["evidence"] = "p0_gate_matrix_final.csv; handoff_to_main_study.md; G8_FINAL_DECISION.md"
    _write_csv(records_dir / "main_study_unlock_matrix_final.csv", unlock_fields, unlock)
    handoff = [
        "# P0-G9 본 연구 인계", "",
        f"- Protocol: `{PROTOCOL_ID}`", "- P0-G8: **Conditional Go approved**",
        "- P0-G9: **Pass — full GPU clean rerun reproducible**",
        f"- Finalized: `{finalized_at}`", f"- Clean attempt: `{attempt_dir}`", "",
        "## 현재 해제", "",
        "- FM1 지표 적격성·H1/H2 shortlist 감사",
        "- FM2 승인 범위 paired manifest 동결",
        "- FM3의 shared 394.24µm descriptive tumor 조합", "",
        "## 계속 잠금", "", *[f"- {item}" for item in PERMANENT_PROHIBITIONS], "",
        "G8/G9는 추가 과학적 증거를 대신하지 않는다. Confirmatory target, H2, 임상 및 우월성 주장은 각 추가 gate를 통과해야 한다.",
    ]
    (records_dir / "handoff_to_main_study.md").write_text("\n".join(handoff) + "\n", encoding="utf-8")
    result = {
        "schema_version": "g9-final-1.0", "protocol_id": PROTOCOL_ID,
        "status": "pass_clean_rerun_handoff", "finalized_at_utc": finalized_at,
        "attempt_dir": str(attempt_dir), "g8_manifest_sha256": g8["manifest_sha256"],
        "reproducibility_manifest_sha256": sha256_file(attempt_dir / "reproducibility_manifest.json"),
        "unlocked": ["FM1", "scope-capped FM2", "scope-capped descriptive FM3"],
        "still_locked": list(PERMANENT_PROHIBITIONS),
    }
    result["manifest_sha256"] = canonical_hash(result)
    (records_dir / "g9_handoff_manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def fm4_scope_snapshot() -> dict[str, Any]:
    """Hash the exact FM1-FM4 evidence reviewed for the FM4 entry decision."""
    required: list[Path] = [
        ROOT / "projects/quantitative_foundation_model_validation/docs/research_plan/14_FOUNDATION_MODEL_QUANTITATIVE_METRIC_VALIDATION_PLAN_KO.md",
        RECORDS_DIR / "g9_handoff_manifest.json",
        RECORDS_DIR / "main_study_unlock_matrix_final.csv",
    ]
    for stage, (directory, names) in MAIN_STUDY_OUTPUTS.items():
        if stage == "fm4":
            continue
        required.extend(directory / name for name in names)
    files = []
    for path in required:
        if not path.is_file():
            raise GovernanceError(f"FM4 승인 근거 파일이 없습니다: {path.relative_to(ROOT)}")
        files.append({
            "path": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    snapshot: dict[str, Any] = {
        "schema_version": "fm4-scope-snapshot-1.0",
        "protocol_id": PROTOCOL_ID,
        "files": files,
    }
    snapshot["snapshot_sha256"] = canonical_hash(snapshot)
    return snapshot


def fm4_scope_records(records_dir: Path = RECORDS_DIR) -> list[dict[str, Any]]:
    return _read_jsonl(records_dir / "fm4_scope_approval_records.jsonl")


def append_fm4_scope_approval(payload: dict[str, Any], *, records_dir: Path = RECORDS_DIR) -> dict[str, Any]:
    name = str(payload.get("reviewer_name", "")).strip()
    signature = str(payload.get("signature", "")).strip()
    decision = str(payload.get("decision", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    if len(name) < 2 or len(name) > 120:
        raise GovernanceError("연구책임자 실명을 입력하십시오.")
    if signature != name:
        raise GovernanceError("전자서명란에 연구책임자 실명을 동일하게 입력하십시오.")
    if decision not in {"approve", "revise", "stop"}:
        raise GovernanceError("허용되지 않은 FM4 판정입니다.")
    attestations = {key: bool(payload.get(key)) for key in FM4_APPROVAL_ATTESTATIONS}
    if decision == "approve" and not all(attestations.values()):
        missing = [key for key, accepted in attestations.items() if not accepted]
        raise GovernanceError(f"FM4 승인에 필요한 확인 항목이 빠졌습니다: {missing}")
    snapshot = fm4_scope_snapshot()
    with governance_lock(records_dir):
        if (records_dir / "fm4_scope_approval_manifest.json").is_file():
            raise GovernanceError("FM4 범위 승인이 이미 확정되어 ledger가 잠겼습니다.")
        if fm4_scope_snapshot()["snapshot_sha256"] != snapshot["snapshot_sha256"]:
            raise GovernanceError("승인 처리 중 FM4 근거 snapshot이 변경되었습니다.")
        previous = fm4_scope_records(records_dir)
        record: dict[str, Any] = {
            "schema_version": "fm4-scope-approval-1.0",
            "protocol_id": PROTOCOL_ID,
            "milestone": "FM4",
            "reviewer_name": name,
            "reviewer_role": "research_lead",
            "decision": decision,
            "attestations": attestations,
            "approved_scope": "tumor_fraction × CONCH/Virchow × shared 394.24um; exploratory descriptive H1 only" if decision == "approve" else "",
            "claim_ceiling": "internal_descriptive_recoverability_only",
            "notes": notes,
            "submitted_at_utc": utc_now(),
            "evidence_snapshot_sha256": snapshot["snapshot_sha256"],
            "previous_record_sha256": previous[-1]["record_sha256"] if previous else "",
        }
        record["record_sha256"] = canonical_hash(record)
        path = records_dir / "fm4_scope_approval_records.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        snapshot_path = records_dir / f"fm4_scope_snapshot_{snapshot['snapshot_sha256']}.json"
        if not snapshot_path.exists():
            snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return record


def fm4_scope_status(records_dir: Path = RECORDS_DIR) -> dict[str, Any]:
    snapshot = fm4_scope_snapshot()
    records = fm4_scope_records(records_dir)
    latest = records[-1] if records else None
    manifest_path = records_dir / "fm4_scope_approval_manifest.json"
    current = bool(latest and latest.get("evidence_snapshot_sha256") == snapshot["snapshot_sha256"])
    return {
        "latest": latest,
        "record_count": len(records),
        "evidence_snapshot_sha256": snapshot["snapshot_sha256"],
        "evidence_current": current,
        "ready_to_finalize": bool(latest and current and latest.get("decision") == "approve"),
        "finalized": manifest_path.is_file(),
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None,
    }


def finalize_fm4_scope(*, records_dir: Path = RECORDS_DIR) -> dict[str, Any]:
    with governance_lock(records_dir):
        path = records_dir / "fm4_scope_approval_manifest.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        status = fm4_scope_status(records_dir)
        if not status["ready_to_finalize"]:
            raise GovernanceError("현재 FM4 snapshot에 대한 연구책임자의 Approve 판정이 필요합니다.")
        record = status["latest"]
        manifest: dict[str, Any] = {
            "schema_version": "fm4-scope-final-1.0",
            "protocol_id": PROTOCOL_ID,
            "milestone": "FM4",
            "status": "approved_exploratory_descriptive_fm4",
            "finalized_at_utc": utc_now(),
            "approver": {"name": record["reviewer_name"], "role": "research_lead"},
            "approval_record_sha256": record["record_sha256"],
            "evidence_snapshot_sha256": status["evidence_snapshot_sha256"],
            "approved_scope": record["approved_scope"],
            "claim_ceiling": "internal_descriptive_recoverability_only",
            "still_prohibited": list(PERMANENT_PROHIBITIONS),
        }
        manifest["manifest_sha256"] = canonical_hash(manifest)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        report = [
            "# FM4 연구책임자 범위 승인", "",
            f"- Status: **{manifest['status']}**",
            f"- Approver: {record['reviewer_name']} (research lead)",
            f"- Finalized: `{manifest['finalized_at_utc']}`",
            f"- Evidence snapshot: `{status['evidence_snapshot_sha256']}`", "",
            "## 승인 범위", "", f"- {record['approved_scope']}", "",
            "## 해석 상한", "", "- internal descriptive recoverability only", "",
            "이 승인은 confirmatory, 질병예측/H2, 임상·PNI, scanner/stain, encoder 우월성 또는 외부 transport 주장을 해제하지 않는다.",
        ]
        (records_dir / "FM4_SCOPE_APPROVAL.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        return manifest


def portal_data(
    *, records_dir: Path = RECORDS_DIR, evidence_dir: Path = PREEXPERIMENT,
) -> dict[str, Any]:
    readiness = g8_readiness(records_dir=records_dir, evidence_dir=evidence_dir)
    config = json.loads((evidence_dir / "run_config.json").read_text(encoding="utf-8"))
    _, gates = _read_csv(evidence_dir / "p0_gate_matrix.csv")
    _, questions = _read_csv(evidence_dir / "p0_question_answer_matrix.csv")
    _, combinations = _read_csv(evidence_dir / "model_target_fov_decision.csv")
    _, risks = _read_csv(evidence_dir / "unresolved_risk_register.csv")
    m9_path = records_dir / "m9_status.json"
    g8_path = records_dir / "g8_approval_manifest.json"
    g9_path = records_dir / "g9_handoff_manifest.json"
    fm1_available = all((FM1_OUTPUT_DIR / name).is_file() for name in FM1_OUTPUTS)
    fm1 = {"available": fm1_available, "outputs": list(FM1_OUTPUTS)}
    if fm1_available:
        _, fm1_summary = _read_csv(FM1_OUTPUT_DIR / "fm1_summary.csv")
        fm1_config = json.loads((FM1_OUTPUT_DIR / "run_config.json").read_text(encoding="utf-8"))
        fm1.update({
            "summary": {row["measure"]: row["value"] for row in fm1_summary},
            "tier_counts": fm1_config["tier_counts"],
            "h1_status_counts": fm1_config["h1_status_counts"],
            "h2_status_counts": fm1_config["h2_status_counts"],
            "status": "registry_audit_complete_no_H2_execution_unlocked",
        })
    main_study = {}
    for stage, (directory, names) in MAIN_STUDY_OUTPUTS.items():
        available = all((directory / name).is_file() for name in names)
        main_study[stage] = {"available": available, "outputs": list(names)}
        if available:
            config_value = json.loads((directory / "run_config.json").read_text(encoding="utf-8"))
            main_study[stage]["counts"] = config_value.get("counts", {})
            if stage == "fm4":
                _, power_rows = _read_csv(directory / "power_precision_plan.csv")
                main_study[stage]["available_power"] = next(
                    row for row in power_rows if row["scenario"] == "available"
                )
            main_study[stage]["status"] = {
                "fm1": "registry audit complete",
                "fm2": "paired manifest frozen",
                "fm3": "clean embedding bundle registered",
                "fm4": "entry packet prepared; execution locked pending approval",
            }[stage]
    return {
        "protocol_id": PROTOCOL_ID,
        "draft_decision": "Conditional Go",
        "summary": {
            "medical_metrics": config.get("m8", {}).get("metric_taxonomy", {}).get("tier_counts", {}),
            "analysis_measures": config.get("m8", {}).get("metric_taxonomy", {}).get("analysis_measure_count", 73),
            "fully_benchmarked_target": "T2 tumor fraction",
            "candidate_combinations": 2,
            "source_hashes_match": config.get("all_source_pre_post_hashes_match", False),
            "immutable_clinician_source_verified": config.get("immutable_clinician_source_verified", False),
        },
        "gates": gates[:8], "questions": questions, "combinations": combinations, "risks": risks,
        "g8": {**readiness, "finalized": g8_path.is_file(), "manifest": json.loads(g8_path.read_text()) if g8_path.is_file() else None},
        "g9": {
            "status": json.loads(m9_path.read_text()) if m9_path.is_file() else {"status": "not_started"},
            "finalized": g9_path.is_file(),
            "manifest": json.loads(g9_path.read_text()) if g9_path.is_file() else None,
        },
        "fm1": fm1,
        "main_study": main_study,
        "fm4_scope_approval": fm4_scope_status(records_dir),
        "approved_combinations": list(APPROVED_COMBINATIONS),
        "permanent_prohibitions": list(PERMANENT_PROHIBITIONS),
        "scientific_boundaries": [
            {
                "issue": "정량 측정 반복성",
                "current_evidence": "독립 반복 판독 또는 ICC 근거 없음",
                "effect": "tumor fraction은 descriptive-only; confirmatory 지정 불가",
                "resolution": "고정 측정법과 독립 반복 측정·일치도 분석",
                "can_approval_resolve": False,
            },
            {
                "issue": "독립 표적의 수",
                "current_evidence": "완전 benchmark된 표적은 T2 tumor fraction 1개",
                "effect": "모델 특이 개념·보편적 우월성·H2 인과적 사용 주장 불가",
                "resolution": "독립 metric–endpoint pair, 적절한 표본/사건 수, 외부 검증",
                "can_approval_resolve": False,
            },
            {
                "issue": "scanner/stain 일반화",
                "current_evidence": "stain metadata 없음; alternate-MPP 2 subjects",
                "effect": "G7 Amber; 견고성 주장 불가",
                "resolution": "다기관·다스캐너 sentinel truth 및 사전 정의 분석",
                "can_approval_resolve": False,
            },
            {
                "issue": "P0-G8 책임자 판정",
                "current_evidence": "P0-M8 evidence bundle 완성, 연구책임자 최종 승인 필요",
                "effect": "P0-M9 clean rerun 진입 잠금",
                "resolution": "독립 연구 책임자의 동일 snapshot 승인; 전문 검토는 필요 시 비차단 자문",
                "can_approval_resolve": True,
            },
            {
                "issue": "P0-G9 재현성",
                "current_evidence": "clean full-GPU rerun 미실행",
                "effect": "FM1/FM2 및 범위 제한 FM3 인계 잠금",
                "resolution": "승인 snapshot 고정 후 별도 디렉터리 clean rerun과 hash 비교",
                "can_approval_resolve": False,
            },
        ],
        "evidence_files": list(EVIDENCE_FILES),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "finalize-g8", "run-m9"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "status":
        print(json.dumps(portal_data(), indent=2, ensure_ascii=False, sort_keys=True))
    elif args.command == "finalize-g8":
        print(json.dumps(finalize_g8(), indent=2, ensure_ascii=False, sort_keys=True))
    elif args.command == "run-m9":
        print(json.dumps(run_m9_full(), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
