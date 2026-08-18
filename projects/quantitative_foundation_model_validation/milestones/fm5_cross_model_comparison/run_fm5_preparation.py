#!/usr/bin/env python3
"""Prepare the scope-capped FM5 entry contract without running FM5 analyses."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
STUDY = ROOT / "projects/quantitative_foundation_model_validation"
RECORDS = STUDY / "preexperiment/governance_records"
FM2 = STUDY / "milestones/fm2_paired_manifest/outputs"
FM3 = STUDY / "milestones/fm3_paired_embeddings/outputs"
FM4 = STUDY / "milestones/fm4_concept_benchmark/outputs"
OUT = Path(__file__).resolve().parent / "outputs"

PROTOCOL_ID = "P0-QFMV-2026-08-11-APPROVED-001"
SEED = 20260811
BOOTSTRAP_REPLICATES = 2000
ENTRY_OUTPUTS = (
    "fm5-entry-packet.md",
    "fm5_analysis_family.csv",
    "fm5_source_manifest.csv",
    "fm5_discordance_definition.csv",
    "fm5_entry_checklist.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def require_hash(path: Path, expected: str, label: str) -> None:
    observed = sha256(path)
    if observed != expected:
        raise RuntimeError(f"{label} hash mismatch: expected {expected}, observed {observed}")


def main() -> None:
    fm4_config = json.loads((FM4 / "benchmark_run_config.json").read_text(encoding="utf-8"))
    if fm4_config.get("status") != "complete_approved_exploratory_descriptive_h1":
        raise RuntimeError("FM4 is not complete under the approved descriptive H1 scope")
    if fm4_config.get("clean_rerun", {}).get("status") != "pass":
        raise RuntimeError("FM4 clean rerun did not pass")
    if fm4_config.get("clean_rerun", {}).get("mismatch_count") != 0:
        raise RuntimeError("FM4 clean rerun contains deterministic mismatches")
    for name, expected in fm4_config["output_hashes_excluding_run_config"].items():
        require_hash(FM4 / name, expected, f"FM4 output {name}")
    for name, expected in fm4_config["source_hashes"].items():
        if name.endswith("_embedding"):
            continue
        source_path = {
            "paired_sample_manifest.csv": FM2 / name,
            "embedding_bundle_manifest.csv": FM3 / name,
            "embedding_row_manifest.csv": FM3 / name,
            "fm4_shared_fold_manifest.csv": FM4 / name,
            "fm4_scope_approval_manifest.json": RECORDS / name,
        }[name]
        require_hash(source_path, expected, f"FM4 source {name}")

    paired = read_csv(FM2 / "paired_sample_manifest.csv")
    embedding_rows = read_csv(FM3 / "embedding_row_manifest.csv")
    subject_predictions = read_csv(FM4 / "fm4_subject_predictions.csv")
    if len(paired) != 1218 or len(embedding_rows) != 1218:
        raise RuntimeError("FM2/FM3 frozen paired row count is not 1,218")
    if [row["sample_id"] for row in paired] != [row["sample_id"] for row in embedding_rows]:
        raise RuntimeError("FM2/FM3 row order mismatch")
    if len(subject_predictions) != 50:
        raise RuntimeError("FM4 subject prediction table must contain 25 paired subjects per encoder")
    subjects = sorted({row["subject_id"] for row in paired})
    if len(subjects) != 25:
        raise RuntimeError("FM5 entry is limited to the frozen 25-subject cohort")

    bundle = read_csv(FM3 / "embedding_bundle_manifest.csv")
    for row in bundle:
        array_path = ROOT / row["array_path"]
        if not array_path.is_file():
            raise RuntimeError(f"embedding source is missing: {row['array_path']}")
        require_hash(array_path, row["array_sha256"], f"{row['encoder']} embedding")

    OUT.mkdir(parents=True, exist_ok=True)
    source_paths = [
        Path(__file__).resolve().parent / "run_fm5_comparison.py",
        RECORDS / "g8_approval_manifest.json",
        RECORDS / "g9_handoff_manifest.json",
        RECORDS / "fm4_scope_approval_manifest.json",
        RECORDS / "p0_gate_matrix_final.csv",
        RECORDS / "main_study_unlock_matrix_final.csv",
        FM2 / "paired_sample_manifest.csv",
        FM3 / "embedding_bundle_manifest.csv",
        FM3 / "embedding_row_manifest.csv",
        FM4 / "fm4_oof_predictions.csv",
        FM4 / "fm4_subject_predictions.csv",
        FM4 / "fm4_summary.csv",
        FM4 / "fm4_paired_deltas.csv",
        FM4 / "benchmark_run_config.json",
    ]
    source_rows = [
        {
            "source_role": "governance" if "governance_records" in str(path) else "analysis_input",
            "canonical_path": str(path.relative_to(ROOT)),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
            "required_unchanged_at_execution": True,
        }
        for path in source_paths
    ]
    for row in bundle:
        source_rows.append(
            {
                "source_role": "paired_embedding",
                "canonical_path": row["array_path"],
                "sha256": row["array_sha256"],
                "size_bytes": (ROOT / row["array_path"]).stat().st_size,
                "required_unchanged_at_execution": True,
            }
        )
    write_csv(OUT / "fm5_source_manifest.csv", source_rows)

    family_rows = [
        {
            "family_id": "FM5-PRIMARY-DESCRIPTIVE",
            "analysis_unit": "subject",
            "estimand": "Spearman(CONCH subject-mean OOF prediction, Virchow subject-mean OOF prediction)",
            "role": "primary_descriptive_agreement",
            "uncertainty": "paired subject bootstrap percentile 95% CI",
            "replicates": BOOTSTRAP_REPLICATES,
            "multiplicity": "descriptive_only_no_p_or_q_values",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "family_id": "FM5-PRIMARY-DESCRIPTIVE",
            "analysis_unit": "subject",
            "estimand": "Spearman(CONCH subject residual, Virchow subject residual)",
            "role": "primary_descriptive_residual_agreement",
            "uncertainty": "paired subject bootstrap percentile 95% CI",
            "replicates": BOOTSTRAP_REPLICATES,
            "multiplicity": "descriptive_only_no_p_or_q_values",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "family_id": "FM5-PRIMARY-DESCRIPTIVE",
            "analysis_unit": "subject",
            "estimand": "mean(abs_error_CONCH - abs_error_Virchow)",
            "role": "primary_descriptive_paired_error_effect",
            "uncertainty": "paired subject bootstrap percentile 95% CI",
            "replicates": BOOTSTRAP_REPLICATES,
            "multiplicity": "descriptive_only_no_p_or_q_values",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "family_id": "FM5-PRIMARY-DESCRIPTIVE",
            "analysis_unit": "subject_mean_embedding",
            "estimand": "centered linear CKA(CONCH, Virchow)",
            "role": "primary_descriptive_representation_similarity",
            "uncertainty": "paired subject bootstrap percentile 95% CI",
            "replicates": BOOTSTRAP_REPLICATES,
            "multiplicity": "descriptive_only_no_p_or_q_values",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "family_id": "FM5-SECONDARY-DESCRIPTIVE",
            "analysis_unit": "tile_clustered_by_subject",
            "estimand": "prediction/residual Spearman and centered linear CKA",
            "role": "secondary_granularity_description",
            "uncertainty": "subject-cluster bootstrap for agreement; CKA point estimate only",
            "replicates": BOOTSTRAP_REPLICATES,
            "multiplicity": "descriptive_only_no_p_or_q_values",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "family_id": "FM5-AUDIT",
            "analysis_unit": "subject",
            "estimand": "reproduction audit of P0-M7 and FM4 source values",
            "role": "consistency_audit_not_new_hypothesis",
            "uncertainty": "exact source/output hash plus numeric tolerance audit",
            "replicates": 0,
            "multiplicity": "not_applicable",
            "claim_ceiling": "reproducibility_audit_only",
        },
    ]
    write_csv(OUT / "fm5_analysis_family.csv", family_rows)

    discordance_rows = [
        {
            "class": "concordant_high",
            "rule": "CONCH prediction >= CONCH subject median AND Virchow prediction >= Virchow subject median",
            "interpretation": "both OOF predictions are in their encoder-specific high half; not correctness or biology",
        },
        {
            "class": "concordant_low",
            "rule": "CONCH prediction < CONCH subject median AND Virchow prediction < Virchow subject median",
            "interpretation": "both OOF predictions are in their encoder-specific low half; not correctness or biology",
        },
        {
            "class": "conch_only",
            "rule": "CONCH prediction >= CONCH subject median AND Virchow prediction < Virchow subject median",
            "interpretation": "technical rank discordance only; not a CONCH-specific concept claim",
        },
        {
            "class": "virchow_only",
            "rule": "CONCH prediction < CONCH subject median AND Virchow prediction >= Virchow subject median",
            "interpretation": "technical rank discordance only; not a Virchow-specific concept claim",
        },
    ]
    write_csv(OUT / "fm5_discordance_definition.csv", discordance_rows)

    checklist_rows = [
        ("FM4 approved completion", "met", "approved descriptive H1 benchmark complete"),
        ("FM4 clean rerun", "met", "11/11 deterministic outputs byte-identical"),
        ("P0-G7 scope", "met_with_amber_cap", "shared 394.24um descriptive comparison only"),
        ("FM2/FM3 membership and row order", "met", "1,218 paired tiles; 25 subjects; mismatch 0"),
        ("FM5 estimands and analysis families", "prepared", "primary and secondary descriptive families frozen"),
        ("paired uncertainty", "prepared", "2,000 paired subject bootstraps; undefined retained"),
        ("multiplicity", "descriptive_only", "no confirmatory p/q values or superiority gate"),
        ("discordance rules", "prepared", "encoder-specific subject medians; four technical strata"),
        ("scanner/stain metadata", "not_met", "robustness analyses and claims remain prohibited"),
        ("additional medical target or H2 endpoint", "not_met", "target expansion and H2 remain locked"),
        ("research-lead scope approval", "met", "existing P0-G8/G9 and FM4 approval cover the locked model-target-FOV and claim ceiling"),
    ]
    write_csv(
        OUT / "fm5_entry_checklist.csv",
        [
            {"requirement": requirement, "status": status, "evidence_or_consequence": evidence}
            for requirement, status, evidence in checklist_rows
        ],
    )

    report = [
        "---",
        "document_id: fm5-entry-packet",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: protocol",
        "status: prepared_pending_research_lead_approval",
        "created: 2026-08-14",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/outputs/fm5-entry-packet.md",
        "---",
        "",
        "# FM5 cross-model comparison entry packet",
        "",
        "- Entry decision: **GO — 기존 P0-G8/G9 및 FM4 승인 범위로 실행 가능**",
        "- P0-G7 basis: **Amber**, shared 394.24 µm descriptive scope only",
        "- Samples: 1,218 paired tiles, 25 subjects, five frozen subject-grouped folds",
        "- Target: `tumor_fraction` only; T2 descriptive-only, not confirmatory",
        "- Encoders: frozen CONCH and frozen Virchow",
        "- Claim ceiling: internal descriptive cross-encoder consistency only",
        "",
        "## 고정 estimand와 family",
        "",
        "Primary descriptive family는 subject-mean OOF prediction Spearman, subject residual Spearman, subject paired absolute-error difference, subject-mean embedding centered linear CKA다. Secondary family는 subject-clustered tile-level prediction/residual agreement와 tile-level CKA point estimate다. P0-M7 및 FM4 값은 새 가설이 아닌 source-hash/numeric consistency audit로만 재생성한다.",
        "",
        "## Paired uncertainty와 multiplicity",
        "",
        "모든 primary uncertainty는 동일 subject draw를 양 encoder에 적용하는 2,000회 paired subject bootstrap percentile 95% CI다. undefined replicate는 삭제하지 않고 수와 비율을 저장한다. 이 family는 descriptive-only이므로 confirmatory p-value, q-value, 통과 threshold 또는 league table을 만들지 않는다. CI는 정밀도 범위이며 우월성 검정이 아니다.",
        "",
        "## Discordance 정의",
        "",
        "각 encoder의 frozen subject-level OOF prediction median을 결과 계산 전에 고정된 cutoff 규칙으로 사용해 `concordant_high`, `concordant_low`, `conch_only`, `virchow_only`를 분류한다. 이 분류는 기술적 rank discordance이며 correctness, model-specific biology 또는 encoder superiority를 뜻하지 않는다.",
        "",
        "## 중단 기준",
        "",
        "- 기존 P0-G8 Conditional Go, P0-G9 pass 또는 FM4 scope approval manifest가 없거나 승인 model–target–FOV/claim ceiling과 다르면 embedding/prediction을 불러오기 전에 중단한다.",
        "- FM4 승인·완료·11/11 clean-rerun 상태 또는 등록 source/output hash가 달라지면 중단한다.",
        "- FM2/FM3/FM4 sample ID, subject, fold, truth, row order가 1:1이 아니거나 1,218 tiles/25 subjects가 아니면 중단한다.",
        "- embedding/prediction/truth에 비유한 nonfinite 값, duplicate 또는 누락이 있으면 중단한다.",
        "- primary bootstrap의 undefined 비율이 5%를 넘으면 해당 estimand를 unstable/not-evaluable로 보고하고 해석을 중단한다; replicate는 보존한다.",
        "- scanner/stain, external transport, 추가 target, 질병 endpoint/H2 또는 PNI 분석이 필요해지면 범위 확대 없이 중단한다.",
        "",
        "## 허용 결론",
        "",
        "동일 내부 표본과 물리 FOV에서 두 frozen representation과 FM4 OOF 예측이 어느 정도 일치하거나 기술적으로 불일치하는지, 그리고 그 기술적 대비의 paired uncertainty를 기술할 수 있다.",
        "",
        "## 금지 결론",
        "",
        "encoder superiority, scanner/stain robustness, external transportability, disease prediction/H2 functional utilization, clinical 또는 whole-slide PNI diagnosis, 단일 target에서의 일반적 model-specific concept, 승인되지 않은 추가 의료지표 해석은 금지한다.",
        "",
        "기존 승인은 이 고정 분석계약의 Amber 범위 실행을 해제한다. 데이터로 충족되지 않은 과학적 gate는 여전히 대체하지 않는다.",
    ]
    packet_path = OUT / "fm5-entry-packet.md"
    packet_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    config = {
        "schema_version": "fm5-entry-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": PROTOCOL_ID,
        "status": "ready_existing_approval_scope_locked",
        "execution_authorized": True,
        "seed": SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "counts": {"paired_tiles": 1218, "subjects": 25, "outer_folds": 5, "encoders": 2, "targets": 1},
        "scope": "tumor_fraction × CONCH/Virchow × shared 394.24um; internal descriptive cross-model comparison only",
        "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        "source_hashes": {row["canonical_path"]: row["sha256"] for row in source_rows},
        "output_hashes_excluding_run_config": {
            name: sha256(OUT / name)
            for name in ENTRY_OUTPUTS
        },
    }
    (OUT / "fm5_entry_run_config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": config["status"], **config["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
