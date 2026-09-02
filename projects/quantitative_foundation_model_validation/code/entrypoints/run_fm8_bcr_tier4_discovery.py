#!/usr/bin/env python3
"""Run the locked FM8 TCGA-to-CHIMERA whole-tissue Tier 4 BCR analysis."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from projects.quantitative_foundation_model_validation.code.lib import fm8_tier4


ROOT = REPOSITORY_ROOT
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
OUTPUTS = PROJECT / "milestones/fm8_bcr_tier4_discovery/outputs"
ARTIFACT_ROOT = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm8_bcr_tier4_discovery"
TCGA_LOCAL = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/tcga_prad_current_gdc_bcr"
CHIMERA_LOCAL = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/chimera_task1"
FM6_INTERNAL_OUTPUTS = PROJECT / "milestones/fm6_internal_development_pilot/outputs"
FM6_INTERNAL_ARTIFACTS = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot"
FM6_EXTERNAL_ARTIFACTS = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_chimera_external_functional_validation"

SEED = 260831
BOOTSTRAPS = 2000
PROTOCOL_ID = "QFMV-FM8-BCR-TIER4-2026-08-31-001"
ENCODERS = ("conch", "virchow")
CANDIDATES = {"conch": "FM8-BCR-CON-L001", "virchow": "FM8-BCR-VIR-L001"}

INPUTS = {
    "tcga_subjects": (
        TCGA_LOCAL / "development_subjects.csv",
        "c36bfc442f6f33aaa6887eb6882c62f8984561e2336a35b6ab30eab370e1d814",
    ),
    "tcga_folds": (
        TCGA_LOCAL / "development_outer_folds.csv",
        "7c8b79237eb8cfaa2dc3b0da9f684e34bc10607d47730d8149a5e4e42e2e338c",
    ),
    "tcga_tiles": (
        FM6_INTERNAL_OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv",
        "d4fe8ba50ec0e129ebcc7e5b529b4d26bb724de89f8869bb06648716ab4a9c04",
    ),
    "tcga_header_qc": (TCGA_LOCAL / "development_wsi_header_qc.csv", None),
    "tcga_conch_embeddings": (
        FM6_INTERNAL_ARTIFACTS / "fm6_tcga_conch_tile_embeddings.npy",
        "99c6d5f3bc59070a7c2e74f3c6f3adc3f7f8db5cf6d8837465bde955953e9d2d",
    ),
    "tcga_virchow_embeddings": (
        FM6_INTERNAL_ARTIFACTS / "fm6_tcga_virchow_tile_embeddings.npy",
        "4e23555436084c1154dbfdd94df86ddff556617fa41864615fb505f438f17ca7",
    ),
    "chimera_clinical": (
        CHIMERA_LOCAL / "normalized_clinical.csv",
        "95e62aa7c0a70d065fbaa3bf9d688f7f7d2c7fc0b27635cb190331ad042773bb",
    ),
    "chimera_tiles": (
        FM6_EXTERNAL_ARTIFACTS / "fm6_chimera_tile_manifest.csv",
        "ba95d49626e01054f6efdf2c2d25509f01ed60e997b340785feb6add4781f38a",
    ),
    "chimera_conch_embeddings": (
        FM6_EXTERNAL_ARTIFACTS / "fm6_chimera_conch_tile_embeddings.npy",
        "dccfe69241a13e3b552da322d7f24b153d35b651cdb0f52f221b8035baf76aea",
    ),
    "chimera_virchow_embeddings": (
        FM6_EXTERNAL_ARTIFACTS / "fm6_chimera_virchow_tile_embeddings.npy",
        "2cfc6468a1963bb020760bb974004fed972d69f27491367db6464f306067c862",
    ),
}

NONVOLATILE_OUTPUTS = (
    "fm8_bcr_tier4_input_integrity.csv",
    "fm8_bcr_tier4_provenance_manifest.csv",
    "fm8_endpoint_lane_readiness.csv",
    "fm8_bcr_tier4_performance.csv",
    "fm8_bcr_tier4_effects.csv",
    "fm8_bcr_tier4_fold_stability.csv",
    "fm8_bcr_tier4_model_selection.csv",
    "fm8_bcr_tier4_candidate_registry.csv",
    "fm8_bcr_tier4_shortcut_audit.csv",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unavailable"


def _json_dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")


def audit_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    provenance = []
    for name, (path, expected_hash) in INPUTS.items():
        if not path.is_file():
            raise RuntimeError(f"missing locked input: {path.relative_to(ROOT)}")
        digest = sha256_file(path)
        if expected_hash is not None and digest != expected_hash:
            raise RuntimeError(f"locked input hash changed: {name}")
        row: dict[str, object] = {
            "input_id": name,
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest,
            "hash_status": "PASS" if expected_hash in {None, digest} else "FAIL",
        }
        if path.suffix == ".csv":
            frame = pd.read_csv(path)
            row.update({"rows": len(frame), "columns": len(frame.columns), "shape": "not_applicable"})
        else:
            values = np.load(path, mmap_mode="r", allow_pickle=False)
            if not np.isfinite(values).all():
                raise RuntimeError(f"nonfinite locked embedding: {name}")
            row.update({"rows": values.shape[0], "columns": values.shape[1], "shape": "x".join(map(str, values.shape))})
        rows.append(row)
        provenance.append(
            {
                "artifact_id": name,
                "cohort": "TCGA-PRAD" if name.startswith("tcga") else "CHIMERA",
                "owner": "quantitative_foundation_model_validation",
                "provenance_role": "frozen_input",
                "allowed_use": "fm8_bcr_whole_tissue_tier4_discovery",
                "path": path.relative_to(ROOT).as_posix(),
                "rows": row["rows"],
                "sha256": digest,
                "semantics": input_semantics(name),
            }
        )

    tcga_subjects = pd.read_csv(INPUTS["tcga_subjects"][0])
    tcga_folds = pd.read_csv(INPUTS["tcga_folds"][0])
    tcga_tiles = pd.read_csv(INPUTS["tcga_tiles"][0])
    chimera = pd.read_csv(INPUTS["chimera_clinical"][0], dtype={"subject_id": str})
    chimera_tiles = pd.read_csv(INPUTS["chimera_tiles"][0], dtype={"subject_id": str})
    checks = {
        "tcga_subject_count": len(tcga_subjects) == 392,
        "tcga_event_count": int(tcga_subjects.bcr_event.sum()) == 80,
        "tcga_fold_membership": set(tcga_subjects.case_id) == set(tcga_folds.case_id),
        "tcga_tile_membership": set(tcga_subjects.case_id) == set(tcga_tiles.case_id),
        "tcga_tile_count": len(tcga_tiles) == 27968,
        "tcga_slide_count": tcga_tiles.file_id.nunique() == 437,
        "tcga_embedding_rows_unique": not tcga_tiles.embedding_row.duplicated().any(),
        "chimera_subject_count": len(chimera) == 95,
        "chimera_event_count": int(chimera.bcr_event.sum()) == 27,
        "chimera_tile_membership": set(chimera.subject_id) == set(chimera_tiles.subject_id),
        "chimera_tile_count": len(chimera_tiles) == 12160,
        "chimera_slide_count": chimera_tiles.slide_id.nunique() == 190,
        "chimera_embedding_rows_unique": not chimera_tiles.embedding_row.duplicated().any(),
        "tcga_endpoint_complete": tcga_subjects[["bcr_event", "bcr_time_days", "isup_grade_group"]].notna().all().all(),
        "chimera_endpoint_complete": chimera[["bcr_event", "time_to_follow_up_or_bcr_months", "isup_grade_group_reported"]].notna().all().all(),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"input integrity failure: {failed}")
    for name, passed in checks.items():
        rows.append(
            {
                "input_id": name,
                "path": "cross_input_check",
                "bytes": 0,
                "sha256": "not_applicable",
                "hash_status": "PASS" if passed else "FAIL",
                "rows": 1,
                "columns": 1,
                "shape": "boolean",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(provenance)


def input_semantics(name: str) -> str:
    mapping = {
        "tcga_subjects": "patient_isup_bcr_event_and_follow_up_days",
        "tcga_folds": "fixed_patient_grouped_outer_folds",
        "tcga_tiles": "whole_tissue_394_24um_tile_to_slide_patient_manifest",
        "tcga_header_qc": "wsi_header_mpp_scanner_compression_and_thumbnail_qc",
        "chimera_clinical": "patient_reported_isup_bcr_event_and_follow_up_months",
        "chimera_tiles": "whole_tissue_394_24um_tile_to_slide_patient_manifest",
    }
    if "embedding" in name:
        return "frozen_tile_embedding_row_locked_to_tile_manifest"
    return mapping.get(name, "registered_input")


def aggregate_embeddings(
    cohort: str, encoder: str
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    if cohort == "TCGA-PRAD":
        manifest = pd.read_csv(INPUTS["tcga_tiles"][0])
        array = np.load(INPUTS[f"tcga_{encoder}_embeddings"][0], mmap_mode="r", allow_pickle=False)
        patient_column, slide_column = "case_id", "file_id"
        tissue_column = "thumbnail_tissue_fraction"
    elif cohort == "CHIMERA":
        manifest = pd.read_csv(INPUTS["chimera_tiles"][0], dtype={"subject_id": str})
        array = np.load(INPUTS[f"chimera_{encoder}_embeddings"][0], mmap_mode="r", allow_pickle=False)
        patient_column, slide_column = "subject_id", "slide_id"
        tissue_column = "mask_tissue_fraction"
    else:
        raise ValueError(cohort)
    if len(manifest) != len(array) or not np.array_equal(manifest.embedding_row.to_numpy(), np.arange(len(manifest))):
        raise RuntimeError(f"{cohort} {encoder} row order changed")
    slide_rows, slide_vectors = [], []
    for slide_id, rows in manifest.groupby(slide_column, sort=False):
        positions = rows.embedding_row.to_numpy(int)
        slide_vectors.append(np.asarray(array[positions], dtype=np.float64).mean(axis=0))
        slide_rows.append(
            {
                "subject_id": str(rows[patient_column].iloc[0]),
                "slide_id": str(slide_id),
                "n_tiles": len(rows),
                "mean_tissue_fraction": float(rows[tissue_column].mean()),
                "mean_mpp": float(rows.mpp.mean()),
            }
        )
    slide = pd.DataFrame(slide_rows)
    slide_x = np.stack(slide_vectors)
    patient_rows, patient_vectors = [], []
    for subject_id, rows in slide.groupby("subject_id", sort=True):
        positions = rows.index.to_numpy(int)
        patient_vectors.append(slide_x[positions].mean(axis=0))
        patient_rows.append(
            {
                "subject_id": str(subject_id),
                "n_slides": len(rows),
                "n_tiles": int(rows.n_tiles.sum()),
                "mean_tissue_fraction": float(rows.mean_tissue_fraction.mean()),
                "mean_mpp": float(rows.mean_mpp.mean()),
            }
        )
    patient = pd.DataFrame(patient_rows)
    x = np.stack(patient_vectors)
    if cohort == "TCGA-PRAD":
        clinical = pd.read_csv(INPUTS["tcga_subjects"][0]).rename(columns={"case_id": "subject_id"})
        folds = pd.read_csv(INPUTS["tcga_folds"][0]).rename(columns={"case_id": "subject_id"})
        patient = patient.merge(clinical, on="subject_id", validate="one_to_one")
        patient = patient.merge(folds[["subject_id", "outer_fold"]], on="subject_id", validate="one_to_one")
        patient["event"] = patient.bcr_event.astype(int)
        patient["time"] = patient.bcr_time_days.astype(float)
        patient["isup"] = patient.isup_grade_group.astype(float)
        patient["site"] = patient.subject_id.str.split("-").str[1]
        header = pd.read_csv(INPUTS["tcga_header_qc"][0])
        scanner = header.groupby("case_id").scanner_id.apply(
            lambda values: "|".join(sorted(set(values.dropna().astype(str)))) or "missing"
        )
        compression = header.groupby("case_id").compression.apply(
            lambda values: "|".join(sorted(set(values.dropna().astype(str)))) or "missing"
        )
        patient = patient.merge(scanner.rename("scanner_group"), left_on="subject_id", right_index=True, how="left")
        patient = patient.merge(compression.rename("compression_group"), left_on="subject_id", right_index=True, how="left")
    else:
        clinical = pd.read_csv(INPUTS["chimera_clinical"][0], dtype={"subject_id": str})
        patient = patient.merge(clinical, on="subject_id", validate="one_to_one")
        patient["event"] = patient.bcr_event.astype(int)
        patient["time"] = patient.time_to_follow_up_or_bcr_months.astype(float)
        patient["isup"] = patient.isup_grade_group_reported.astype(float)
        patient["site"] = "not_available"
        patient["scanner_group"] = "not_available"
        patient["compression_group"] = "not_available"
    patient["log1p_n_slides"] = np.log1p(patient.n_slides.astype(float))
    order = patient.subject_id.argsort(kind="stable").to_numpy()
    return patient.iloc[order].reset_index(drop=True), x[order], slide


def known_panel(patient: pd.DataFrame) -> np.ndarray:
    values = patient[["isup", "mean_tissue_fraction", "mean_mpp", "log1p_n_slides"]].to_numpy(float)
    if not np.isfinite(values).all():
        raise RuntimeError("known/QC panel contains nonfinite values")
    return values


def crop_color_qc(cohort: str, manifest: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if cohort == "TCGA-PRAD":
        cache = FM6_INTERNAL_ARTIFACTS / "shared_canonical_crops"
        patient_column, slide_column, hash_column = "case_id", "file_id", "level0_crop_sha256"
    else:
        cache = FM6_EXTERNAL_ARTIFACTS / "shared_canonical_crops"
        patient_column, slide_column, hash_column = "subject_id", "slide_id", "decoded_rgb_sha256"
    digest = hashlib.sha256()
    rows = []
    for slide_id, group in manifest.groupby(slide_column, sort=False):
        path = cache / f"{slide_id}.npz"
        if not path.is_file():
            raise RuntimeError(f"missing canonical crop cache: {path}")
        with np.load(path, allow_pickle=False) as payload:
            tile_ids = payload["tile_id"].astype(str)
            expected = group.tile_id.astype(str).to_numpy()
            if not np.array_equal(tile_ids, expected):
                raise RuntimeError(f"canonical crop order changed: {cohort} {slide_id}")
            hashes = payload[hash_column].astype(str)
            for tile_id, crop_hash in zip(tile_ids, hashes, strict=True):
                digest.update(f"{tile_id}|{crop_hash}\n".encode())
            pixels = payload["crop"][:, ::32, ::32, :].reshape(-1, 3).astype(np.float64)
        rgb_mean = pixels.mean(axis=0)
        rgb_std = pixels.std(axis=0, ddof=0)
        maximum = pixels.max(axis=1)
        minimum = pixels.min(axis=1)
        saturation = np.divide(maximum - minimum, maximum, out=np.zeros_like(maximum), where=maximum > 0)
        optical_density = -np.log((pixels + 1.0) / 256.0)
        rows.append(
            {
                "cohort": cohort,
                "subject_id": str(group[patient_column].iloc[0]),
                "slide_id": str(slide_id),
                "rgb_r_mean": rgb_mean[0],
                "rgb_g_mean": rgb_mean[1],
                "rgb_b_mean": rgb_mean[2],
                "rgb_r_std": rgb_std[0],
                "rgb_g_std": rgb_std[1],
                "rgb_b_std": rgb_std[2],
                "brightness_mean": pixels.mean(axis=1).mean(),
                "saturation_mean": saturation.mean(),
                "od_r_mean": optical_density[:, 0].mean(),
                "od_g_mean": optical_density[:, 1].mean(),
                "od_b_mean": optical_density[:, 2].mean(),
            }
        )
    slide = pd.DataFrame(rows)
    metrics = [column for column in slide.columns if column not in {"cohort", "subject_id", "slide_id"}]
    patient = slide.groupby(["cohort", "subject_id"], as_index=False)[metrics].mean()
    return patient, digest.hexdigest()


def categorical_eta_squared(values: pd.Series, score: pd.Series) -> float:
    frame = pd.DataFrame({"group": values.astype(str), "score": score.astype(float)}).dropna()
    grand = frame.score.mean()
    total = float(((frame.score - grand) ** 2).sum())
    if total <= 0:
        return np.nan
    between = sum(len(group) * (group.score.mean() - grand) ** 2 for _, group in frame.groupby("group"))
    return float(between / total)


def shortcut_audit(
    source: pd.DataFrame, external: pd.DataFrame, encoder: str
) -> tuple[pd.DataFrame, str]:
    rows = []
    continuous = [
        "isup",
        "mean_tissue_fraction",
        "mean_mpp",
        "log1p_n_slides",
        "rgb_r_mean",
        "rgb_g_mean",
        "rgb_b_mean",
        "rgb_r_std",
        "rgb_g_std",
        "rgb_b_std",
        "brightness_mean",
        "saturation_mean",
        "od_r_mean",
        "od_g_mean",
        "od_b_mean",
    ]
    signals: dict[tuple[str, str], float] = {}
    for cohort, frame in [("TCGA-PRAD", source), ("CHIMERA", external)]:
        for variable in continuous:
            rho = float(stats.spearmanr(frame[variable], frame.latent_risk).statistic)
            if not np.isfinite(rho):
                rho = np.nan
            signals[(cohort, variable)] = rho
            rows.append(
                {
                    "encoder": encoder,
                    "cohort": cohort,
                    "shortcut_variable": variable,
                    "variable_type": "continuous",
                    "estimate": rho,
                    "alert_threshold": 0.30,
                    "alert": bool(np.isfinite(rho) and abs(rho) >= 0.30),
                    "status": "EVALUATED" if np.isfinite(rho) else "NOT_EVALUABLE_ZERO_VARIANCE",
                }
            )
        for variable in ["site", "scanner_group", "compression_group"]:
            if frame[variable].eq("not_available").all():
                estimate, status = np.nan, "NOT_EVALUABLE_MISSING_METADATA"
            else:
                estimate, status = categorical_eta_squared(frame[variable], frame.latent_risk), "EVALUATED"
            rows.append(
                {
                    "encoder": encoder,
                    "cohort": cohort,
                    "shortcut_variable": variable,
                    "variable_type": "categorical",
                    "estimate": estimate,
                    "alert_threshold": 0.10,
                    "alert": bool(np.isfinite(estimate) and estimate >= 0.10),
                    "status": status,
                }
            )
        for missing in ["stain_label", "blur", "fold_artifact", "tumor_amount_or_purity", "specimen_type"]:
            rows.append(
                {
                    "encoder": encoder,
                    "cohort": cohort,
                    "shortcut_variable": missing,
                    "variable_type": "required_metadata",
                    "estimate": np.nan,
                    "alert_threshold": np.nan,
                    "alert": False,
                    "status": "NOT_EVALUABLE_MISSING_METADATA",
                }
            )
    repeated_alert = any(
        np.isfinite(signals[("TCGA-PRAD", variable)])
        and np.isfinite(signals[("CHIMERA", variable)])
        and abs(signals[("TCGA-PRAD", variable)]) >= 0.30
        and abs(signals[("CHIMERA", variable)]) >= 0.30
        and np.sign(signals[("TCGA-PRAD", variable)]) == np.sign(signals[("CHIMERA", variable)])
        for variable in continuous
    )
    acquisition_alert = any(
        bool(row["alert"])
        for row in rows
        if row["shortcut_variable"] in {"site", "scanner_group", "compression_group"}
        and row["status"] == "EVALUATED"
    )
    if repeated_alert or acquisition_alert:
        status = "FAIL_MATERIAL_ASSOCIATION"
    else:
        status = "PARTIAL_NOT_EVALUABLE"
    return pd.DataFrame(rows), status


def performance_lookup(table: pd.DataFrame, cohort: str, encoder: str) -> dict[str, float]:
    part = table[(table.cohort == cohort) & (table.encoder == encoder)].set_index("metric")
    return {metric: float(part.loc[metric, "estimate"]) for metric in part.index}


def build_report(
    performance: pd.DataFrame,
    effects: pd.DataFrame,
    registry: pd.DataFrame,
    readiness: pd.DataFrame,
    shortcut: pd.DataFrame,
    clean_status: str,
    execution_records: list[dict[str, object]] | None = None,
) -> str:
    lines = [
        "---",
        "document_id: fm8-bcr-tier4-discovery-report",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: report",
        "status: complete",
        "created: 2026-08-31",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm8_bcr_tier4_discovery/outputs/fm8-bcr-tier4-discovery-report-ko.md",
        "---",
        "",
        "# FM8 BCR Tier 4 잠재 디지털마커 탐색 결과",
        "",
        "## 범위와 역사적 경계",
        "",
        "이 분석은 TCGA-PRAD에서만 선택·적합한 whole-tissue 잠재 점수를 CHIMERA에 변경 없이 적용한 별도 FM8 계산 탐색이다. 2026-08-25 entry audit의 NO-GO와 논문 1 종결 상태는 그대로 보존한다. 본 결과는 Tier 3, 병리 형태, tumor-specific mechanism 또는 임상 biomarker 근거가 아니다.",
        "",
        "## Encoder별 성능",
        "",
        "| Encoder | Cohort | Baseline C | Latent-only C | Additive C | Interaction C | Delta additive | Delta interaction |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for encoder in ENCODERS:
        for cohort in ("TCGA-PRAD", "CHIMERA"):
            values = performance_lookup(performance, cohort, encoder)
            lines.append(
                f"| {encoder} | {cohort} | {values['baseline_c_index']:.3f} | {values['latent_only_c_index']:.3f} | {values['additive_c_index']:.3f} | {values['interaction_c_index']:.3f} | {values['delta_additive']:+.3f} | {values['delta_interaction']:+.3f} |"
            )
    lines.extend(["", "모든 CI, valid/undefined bootstrap 수와 fold 결과는 source table에 보존했다.", "", "## 후보 판정", ""])
    lines.append("| Candidate | Standalone | Complementary | Interactive | Redundant/supportive | Shortcut | External status |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in registry.itertuples(index=False):
        lines.append(
            f"| {row.candidate_id} | {row.standalone_status} | {row.complementary_status} | {row.interaction_status} | {row.redundancy_status} | {row.shortcut_status} | {row.external_reproduction_status} |"
        )
    alert_rows = shortcut[shortcut.alert.fillna(False)]
    lines.extend(
        [
            "",
            "## Shortcut 경보",
            "",
        ]
    )
    for row in alert_rows.itertuples(index=False):
        lines.append(
            f"- `{row.encoder}` / `{row.cohort}` / `{row.shortcut_variable}`: estimate={row.estimate:.3f}, prespecified alert threshold={row.alert_threshold:.2f}."
        )
    lines.extend(
        [
            "",
            "Source site/scanner 경보가 남고 external site/scanner와 tumor amount/purity를 평가할 수 없으므로 shortcut을 분리하지 못했다. 따라서 양성 기능 역할이 있더라도 두 후보 모두 `not qualified`다.",
            "",
            "## 다른 endpoint lane",
            "",
        ]
    )
    for row in readiness.itertuples(index=False):
        lines.append(f"- `{row.endpoint}`: **{row.status}** — {row.required_action}")
    lines.extend(
        [
            "",
            "Cancer presence와 grading은 label을 섞지 않았고 실행하지 않았다.",
            "",
            "## Tier 3 gate와 재현성",
            "",
            "좌표 localization, patch 선정, morphology 명명과 blinded pathology package는 생성하지 않았다. Full shortcut clearance, image-review 권한, 병리 승인과 외부 형태 반복의 별도 GO가 필요하다.",
            "",
            f"Clean rerun: `{clean_status}`.",
        ]
    )
    if execution_records:
        lines.extend(
            [
                "",
                "## 장기 실행 기록",
                "",
                "| Run | tmux session | shell/Python PID | UTC start--end | seconds | log | GPU | exit |",
                "|---|---|---|---|---:|---|---|---:|",
            ]
        )
        command_lines = []
        for config in execution_records:
            runtime = config["runtime"]
            lines.append(
                f"| {config['run_id']} | `{runtime['tmux_session']}` | {runtime.get('shell_pid', 'not_recorded')}/{runtime['pid']} | {runtime['started_utc']} -- {runtime['completed_utc']} | {runtime['execution_seconds']:.3f} | `{runtime.get('log_path', 'not_recorded')}` | {runtime['gpu_used']} | {runtime['exit_code']} |"
            )
            command_lines.append(f"- `{config['run_id']}` command: `{runtime.get('wrapper_command', runtime['command'])}`")
        lines.extend(["", *command_lines])
    return "\n".join(lines) + "\n"


def run_analysis(run_id: str, bootstrap_draws: int, publish: bool) -> dict[str, object]:
    started = time.time()
    run_dir = ARTIFACT_ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    integrity, provenance = audit_inputs()

    tcga_by_encoder: dict[str, tuple[pd.DataFrame, np.ndarray]] = {}
    chimera_by_encoder: dict[str, tuple[pd.DataFrame, np.ndarray]] = {}
    for encoder in ENCODERS:
        tcga_patient, tcga_x, _ = aggregate_embeddings("TCGA-PRAD", encoder)
        chimera_patient, chimera_x, _ = aggregate_embeddings("CHIMERA", encoder)
        tcga_by_encoder[encoder] = (tcga_patient, tcga_x)
        chimera_by_encoder[encoder] = (chimera_patient, chimera_x)
    if not tcga_by_encoder["conch"][0].subject_id.equals(tcga_by_encoder["virchow"][0].subject_id):
        raise RuntimeError("TCGA paired encoder patient order mismatch")
    if not chimera_by_encoder["conch"][0].subject_id.equals(chimera_by_encoder["virchow"][0].subject_id):
        raise RuntimeError("CHIMERA paired encoder patient order mismatch")

    tcga_manifest = pd.read_csv(INPUTS["tcga_tiles"][0])
    chimera_manifest = pd.read_csv(INPUTS["chimera_tiles"][0], dtype={"subject_id": str})
    tcga_color, tcga_crop_chain = crop_color_qc("TCGA-PRAD", tcga_manifest)
    chimera_color, chimera_crop_chain = crop_color_qc("CHIMERA", chimera_manifest)
    color_qc = pd.concat([tcga_color, chimera_color], ignore_index=True)
    _write_csv(color_qc, run_dir / "fm8_patient_color_qc.csv")
    provenance = pd.concat(
        [
            provenance,
            pd.DataFrame(
                [
                    {
                        "artifact_id": "tcga_canonical_crop_identity_chain",
                        "cohort": "TCGA-PRAD",
                        "owner": "quantitative_foundation_model_validation",
                        "provenance_role": "frozen_input_identity_chain",
                        "allowed_use": "fm8_shortcut_color_audit",
                        "path": FM6_INTERNAL_ARTIFACTS.joinpath("shared_canonical_crops").relative_to(ROOT).as_posix(),
                        "rows": 27968,
                        "sha256": tcga_crop_chain,
                        "semantics": "tile_id_plus_level0_crop_sha256_chain",
                    },
                    {
                        "artifact_id": "chimera_canonical_crop_identity_chain",
                        "cohort": "CHIMERA",
                        "owner": "quantitative_foundation_model_validation",
                        "provenance_role": "frozen_input_identity_chain",
                        "allowed_use": "fm8_shortcut_color_audit",
                        "path": FM6_EXTERNAL_ARTIFACTS.joinpath("shared_canonical_crops").relative_to(ROOT).as_posix(),
                        "rows": 12160,
                        "sha256": chimera_crop_chain,
                        "semantics": "tile_id_plus_decoded_rgb_sha256_chain",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    all_performance, all_bootstrap, all_effects = [], [], []
    all_fold, all_selection, all_shortcut, registries, local_predictions = [], [], [], [], []
    for encoder_index, encoder in enumerate(ENCODERS):
        source, source_x = tcga_by_encoder[encoder]
        external, external_x = chimera_by_encoder[encoder]
        event = source.event.to_numpy(int)
        follow_up = source.time.to_numpy(float)
        isup = source.isup.to_numpy(float)
        folds = source.outer_fold.to_numpy(int)
        oof, fold_settings, outer_selection = fm8_tier4.outer_oof_predictions(
            source_x,
            known_panel(source),
            isup,
            event,
            follow_up,
            folds,
            seed=SEED + encoder_index * 10000,
        )
        oof.insert(0, "subject_id", source.subject_id)
        fm8_tier4.validate_oof_coverage(oof, set(source.subject_id.astype(str)))
        final_models, final_selection = fm8_tier4.fit_final_source_models(
            source_x,
            known_panel(source),
            isup,
            event,
            follow_up,
            folds,
            seed=SEED + encoder_index * 10000 + 5000,
        )
        external_prediction = fm8_tier4.predict_external_models(
            final_models, external_x, external.isup.to_numpy(float)
        )
        external_prediction.insert(0, "subject_id", external.subject_id)
        external_prediction["event"] = external.event.to_numpy(int)
        external_prediction["time"] = external.time.to_numpy(float)
        external_prediction["isup"] = external.isup.to_numpy(float)

        source_summary, source_draws = fm8_tier4.patient_bootstrap_performance(
            oof,
            cohort="TCGA-PRAD",
            encoder=encoder,
            draws=bootstrap_draws,
            seed=SEED + encoder_index * 100 + 1,
        )
        external_summary, external_draws = fm8_tier4.patient_bootstrap_performance(
            external_prediction,
            cohort="CHIMERA",
            encoder=encoder,
            draws=bootstrap_draws,
            seed=SEED + encoder_index * 100 + 2,
        )
        for table, n_subjects, n_events in [
            (source_summary, len(source), int(source.event.sum())),
            (external_summary, len(external), int(external.event.sum())),
        ]:
            table["endpoint"] = "bcr"
            table["analysis_unit"] = "patient"
            table["n_subjects"] = n_subjects
            table["n_events"] = n_events
            table["candidate_id"] = CANDIDATES[encoder]
        all_performance.extend([source_summary, external_summary])
        all_bootstrap.extend([source_draws, external_draws])

        source_additive_features = fm8_tier4.stacked_features(
            source.isup.to_numpy(float), final_models.source_stacking_latent, "additive"
        )
        source_interaction_features = fm8_tier4.stacked_features(
            source.isup.to_numpy(float), final_models.source_stacking_latent, "interaction"
        )
        latent_effect = fm8_tier4.coefficient_bootstrap(
            source_additive_features,
            event,
            follow_up,
            alpha=float(final_models.settings["additive_alpha"]),
            coefficient_index=1,
            draws=bootstrap_draws,
            seed=SEED + encoder_index * 100 + 3,
        )
        interaction_effect = fm8_tier4.coefficient_bootstrap(
            source_interaction_features,
            event,
            follow_up,
            alpha=float(final_models.settings["interaction_alpha"]),
            coefficient_index=2,
            draws=bootstrap_draws,
            seed=SEED + encoder_index * 100 + 4,
        )
        all_effects.append(
            {
                "candidate_id": CANDIDATES[encoder],
                "encoder": encoder,
                "endpoint": "bcr",
                "effect": "latent_adjusted_for_isup",
                **latent_effect,
            }
        )
        all_effects.append(
            {
                "candidate_id": CANDIDATES[encoder],
                "encoder": encoder,
                "endpoint": "bcr",
                "effect": "prespecified_isup_by_latent_interaction",
                **interaction_effect,
            }
        )

        for fold in np.unique(folds):
            part = oof[oof.outer_fold == fold]
            values = {
                name: fm8_tier4.harrell_c_index(part.event, part.time, part[column])
                for name, column in [
                    ("baseline", "baseline_risk"),
                    ("latent_only", "latent_risk"),
                    ("additive", "additive_risk"),
                    ("interaction", "interaction_risk"),
                ]
            }
            all_fold.append(
                {
                    "candidate_id": CANDIDATES[encoder],
                    "encoder": encoder,
                    "outer_fold": int(fold),
                    "n_subjects": len(part),
                    "n_events": int(part.event.sum()),
                    **{f"{name}_c_index": value for name, value in values.items()},
                }
            )
        fold_settings.insert(0, "candidate_id", CANDIDATES[encoder])
        fold_settings.insert(1, "encoder", encoder)
        final_row = pd.DataFrame(
            [{"candidate_id": CANDIDATES[encoder], "encoder": encoder, "outer_fold": "final_source", "model_family": "final_bundle", **final_models.settings}]
        )
        all_selection.extend([fold_settings, final_row])

        source_scored = source.merge(
            oof[["subject_id", *fm8_tier4.MODEL_COLUMNS]], on="subject_id", validate="one_to_one"
        ).merge(tcga_color, on="subject_id", validate="one_to_one")
        external_scored = external.merge(
            external_prediction[["subject_id", *fm8_tier4.MODEL_COLUMNS]], on="subject_id", validate="one_to_one"
        ).merge(chimera_color, on="subject_id", validate="one_to_one")
        shortcut, shortcut_status = shortcut_audit(source_scored, external_scored, encoder)
        all_shortcut.append(shortcut)

        perf_source = performance_lookup(pd.concat(all_performance, ignore_index=True), "TCGA-PRAD", encoder)
        perf_external = performance_lookup(pd.concat(all_performance, ignore_index=True), "CHIMERA", encoder)
        fold_positive = sum(
            row["latent_only_c_index"] > 0.5
            for row in all_fold
            if row["encoder"] == encoder and np.isfinite(row["latent_only_c_index"])
        )
        roles = fm8_tier4.assign_functional_roles(
            source={
                "latent_only": perf_source["latent_only_c_index"],
                "delta_additive": perf_source["delta_additive"],
                "delta_interaction": perf_source["delta_interaction"],
                "interaction_coefficient": interaction_effect["coefficient"],
                "positive_fold_count": fold_positive,
            },
            external={
                "latent_only": perf_external["latent_only_c_index"],
                "delta_additive": perf_external["delta_additive"],
                "delta_interaction": perf_external["delta_interaction"],
            },
            shortcut_status=shortcut_status,
        )
        registries.append(
            {
                "candidate_id": CANDIDATES[encoder],
                "endpoint": "bcr",
                "encoder": encoder,
                "source_cohort": "TCGA-PRAD",
                "external_cohort": "CHIMERA",
                "medical_metric_tier": "T4_model_derived",
                "fm8_translation_tier": "Tier_4",
                "translation_tier": "FM8-Tier-4",
                **roles,
                "shortcut_status": shortcut_status,
                "claim_ceiling": "whole_tissue_tier4_hypothesis_not_tier3_not_tumor_specific",
                "evidence_path": "milestones/fm8_bcr_tier4_discovery/outputs/fm8_bcr_tier4_performance.csv",
            }
        )
        source_local = oof.copy()
        source_local.insert(0, "encoder", encoder)
        source_local.insert(1, "cohort", "TCGA-PRAD")
        external_local = external_prediction.copy()
        external_local.insert(0, "encoder", encoder)
        external_local.insert(1, "cohort", "CHIMERA")
        local_predictions.extend([source_local, external_local])
        selection_detail = outer_selection.copy()
        selection_detail.insert(0, "encoder", encoder)
        _write_csv(selection_detail, run_dir / f"fm8_{encoder}_selection_diagnostics.csv")

    performance = pd.concat(all_performance, ignore_index=True)
    bootstrap = pd.concat(all_bootstrap, ignore_index=True)
    effects = pd.DataFrame(all_effects)
    fold_stability = pd.DataFrame(all_fold)
    selection = pd.concat(all_selection, ignore_index=True, sort=False)
    shortcut = pd.concat(all_shortcut, ignore_index=True)
    registry = pd.DataFrame(registries)
    readiness = fm8_tier4.endpoint_lane_readiness()
    predictions = pd.concat(local_predictions, ignore_index=True, sort=False)

    tables = {
        "fm8_bcr_tier4_input_integrity.csv": integrity,
        "fm8_bcr_tier4_provenance_manifest.csv": provenance,
        "fm8_endpoint_lane_readiness.csv": readiness,
        "fm8_bcr_tier4_performance.csv": performance,
        "fm8_bcr_tier4_effects.csv": effects,
        "fm8_bcr_tier4_fold_stability.csv": fold_stability,
        "fm8_bcr_tier4_model_selection.csv": selection,
        "fm8_bcr_tier4_candidate_registry.csv": registry,
        "fm8_bcr_tier4_shortcut_audit.csv": shortcut,
    }
    for name, frame in tables.items():
        _write_csv(frame, run_dir / name)
        if publish:
            _write_csv(frame, OUTPUTS / name)
    _write_csv(predictions, run_dir / "fm8_bcr_tier4_patient_predictions.csv")
    _write_csv(bootstrap, run_dir / "fm8_bcr_tier4_bootstrap_replicates.csv")

    output_hashes = {name: sha256_file(run_dir / name) for name in NONVOLATILE_OUTPUTS}
    config = {
        "protocol_id": PROTOCOL_ID,
        "run_id": run_id,
        "seed": SEED,
        "bootstrap_draws": bootstrap_draws,
        "source_only_selection": True,
        "external_refit_recalibration_threshold_change": "prohibited",
        "endpoint": "bcr",
        "analysis_unit": "patient",
        "scope": "whole_tissue",
        "known_panel": ["isup", "mean_tissue_fraction", "mean_mpp", "log1p_n_slides"],
        "latent_ranks": list(fm8_tier4.LATENT_RANKS),
        "latent_alphas": list(fm8_tier4.LATENT_ALPHAS),
        "projection_alphas": list(fm8_tier4.PROJECTION_ALPHAS),
        "small_cox_alphas": list(fm8_tier4.SMALL_COX_ALPHAS),
        "input_hashes": {name: sha256_file(path) for name, (path, _) in INPUTS.items()},
        "output_hashes": output_hashes,
        "runtime": {
            "started_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(),
            "completed_utc": utc_now(),
            "execution_seconds": time.time() - started,
            "pid": os.getpid(),
            "shell_pid": os.environ.get("FM8_SHELL_PID", "not_recorded"),
            "tmux_session": os.environ.get("FM8_TMUX_SESSION", os.environ.get("TMUX", "not_in_tmux")),
            "command": " ".join(sys.argv),
            "wrapper_command": os.environ.get("FM8_WRAPPER_COMMAND", "not_recorded"),
            "log_path": os.environ.get("FM8_LOG_PATH", "not_recorded"),
            "exit_code_path": os.environ.get("FM8_EXIT_CODE_PATH", "not_recorded"),
            "gpu_used": False,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "unset"),
            "exit_code": 0,
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "pandas": importlib.metadata.version("pandas"),
            "scikit_learn": importlib.metadata.version("scikit-learn"),
            "scikit_survival": importlib.metadata.version("scikit-survival"),
            "git_head": git_head(),
        },
        "volatile_fields": [
            "runtime.started_utc", "runtime.completed_utc", "runtime.execution_seconds",
            "runtime.pid", "runtime.shell_pid", "runtime.tmux_session", "runtime.command",
            "runtime.wrapper_command", "runtime.log_path", "runtime.exit_code_path", "run_id",
        ],
    }
    _json_dump(run_dir / "fm8_bcr_tier4_run_config.json", config)
    if publish:
        _json_dump(OUTPUTS / "fm8_bcr_tier4_run_config.json", config)
        (OUTPUTS / "fm8-bcr-tier4-discovery-report-ko.md").write_text(
            build_report(performance, effects, registry, readiness, shortcut, "PENDING_CLEAN_RERUN"), encoding="utf-8"
        )
    return config


def compare_clean_rerun(first: str, second: str) -> pd.DataFrame:
    rows = []
    for name in NONVOLATILE_OUTPUTS:
        first_path = ARTIFACT_ROOT / "runs" / first / name
        second_path = ARTIFACT_ROOT / "runs" / second / name
        first_hash = sha256_file(first_path)
        second_hash = sha256_file(second_path)
        rows.append(
            {
                "output": name,
                "first_run": first,
                "second_run": second,
                "first_sha256": first_hash,
                "second_sha256": second_hash,
                "exact_match": first_hash == second_hash,
            }
        )
    comparison = pd.DataFrame(rows)
    _write_csv(comparison, OUTPUTS / "fm8_bcr_tier4_clean_rerun_comparison.csv")
    status = "PASS_EXACT_HASH" if comparison.exact_match.all() else "FAIL_HASH_MISMATCH"
    performance = pd.read_csv(OUTPUTS / "fm8_bcr_tier4_performance.csv")
    effects = pd.read_csv(OUTPUTS / "fm8_bcr_tier4_effects.csv")
    registry = pd.read_csv(OUTPUTS / "fm8_bcr_tier4_candidate_registry.csv")
    readiness = pd.read_csv(OUTPUTS / "fm8_endpoint_lane_readiness.csv")
    shortcut = pd.read_csv(OUTPUTS / "fm8_bcr_tier4_shortcut_audit.csv")
    execution_records = []
    for run_id in (first, second):
        config_path = ARTIFACT_ROOT / "runs" / run_id / "fm8_bcr_tier4_run_config.json"
        execution_records.append(json.loads(config_path.read_text(encoding="utf-8")))
    (OUTPUTS / "fm8-bcr-tier4-discovery-report-ko.md").write_text(
        build_report(performance, effects, registry, readiness, shortcut, status, execution_records), encoding="utf-8"
    )
    if not comparison.exact_match.all():
        raise RuntimeError("clean rerun nonvolatile output mismatch")
    return comparison


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="stage", required=True)
    subparsers.add_parser("audit")
    run = subparsers.add_parser("run")
    run.add_argument("--run-id", required=True)
    run.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAPS)
    run.add_argument("--publish", action="store_true")
    compare = subparsers.add_parser("compare-clean-rerun")
    compare.add_argument("--first-run", required=True)
    compare.add_argument("--second-run", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stage == "audit":
        integrity, provenance = audit_inputs()
        print(json.dumps({"status": "PASS", "integrity_rows": len(integrity), "provenance_rows": len(provenance)}, sort_keys=True))
    elif args.stage == "run":
        config = run_analysis(args.run_id, args.bootstrap_draws, args.publish)
        print(json.dumps({"status": "PASS", "run_id": args.run_id, "output_hashes": config["output_hashes"]}, sort_keys=True))
    else:
        comparison = compare_clean_rerun(args.first_run, args.second_run)
        print(json.dumps({"status": "PASS_EXACT_HASH", "outputs": len(comparison)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
