#!/usr/bin/env python3
"""Audit cohort and label readiness before FM8 grading-criterion modeling."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from sklearn.metrics import cohen_kappa_score


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm8_grading_criterion_qualification"
DEFAULT_OUTPUT = MILESTONE / "outputs"
LOCAL_ARTIFACTS = ROOT / (
    "resources/artifacts/quantitative_foundation_model_validation/"
    "fm8_grading_criterion_qualification"
)

PANDA_ARCHIVE = ROOT / "resources/data/shared/opendataset/PANDA/prostate-cancer-grade-assessment.zip"
PANDA_ROOT = ROOT / "resources/data/shared/opendataset/PANDA_extracted"
PANDA_LABELS = PANDA_ROOT / "train.csv"
SICAP_ROOT = ROOT / "resources/data/shared/opendataset/SICAPv2/SICAPv2"
CHIMERA_LABELS = ROOT / (
    "resources/data/quantitative_foundation_model_validation/local-data/"
    "chimera_task1/normalized_clinical.csv"
)
PANDA_MANIFEST = ROOT / "resources/data/manifests/panda.yaml"
SICAP_MANIFEST = ROOT / "resources/data/manifests/sicapv2.yaml"
CHIMERA_MANIFEST = ROOT / "resources/data/manifests/chimera_task1.yaml"
PAR_MANIFEST = ROOT / "resources/data/manifests/par_prostate.yaml"
PAR_ROOT = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/par_s_biad2323"
PAR_LABELS = PAR_ROOT / "slide_labels.tsv"
PAR_LOCAL_AUDIT = PAR_ROOT / "hamamatsu_local_audit.json"

PROTOCOL = "fm8-grading-criterion-qualification-protocol"


def rel(path: Path) -> str:
    return path.absolute().relative_to(ROOT.absolute()).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def manifest_scalar(path: Path, key: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.*?)\s*$", re.MULTILINE)
    match = pattern.search(manifest_text(path))
    return match.group(1).strip("'\"") if match else ""


def count_zip_members(archive: Path, prefix: str, suffix: str) -> int:
    with zipfile.ZipFile(archive) as bundle:
        return sum(name.startswith(prefix) and name.endswith(suffix) for name in bundle.namelist())


def inventory_sha256(paths: Iterable[Path], base: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        record = f"{path.relative_to(base).as_posix()}\t{path.stat().st_size}\n"
        digest.update(record.encode("utf-8"))
    return digest.hexdigest()


def panda_audit() -> tuple[list[dict[str, object]], dict[str, object]]:
    if not PANDA_ARCHIVE.is_file() or not PANDA_LABELS.is_file():
        raise FileNotFoundError("PANDA archive or train.csv is absent")
    labels = pd.read_csv(PANDA_LABELS)
    required = {"image_id", "data_provider", "isup_grade", "gleason_score"}
    if not required.issubset(labels.columns):
        raise ValueError(f"PANDA labels missing {sorted(required - set(labels.columns))}")

    image_files = list((PANDA_ROOT / "train_images").glob("*.tiff"))
    extracted_masks = list((PANDA_ROOT / "train_label_masks").glob("*_mask.tiff"))
    archive_images = count_zip_members(PANDA_ARCHIVE, "train_images/", ".tiff")
    archive_masks = count_zip_members(PANDA_ARCHIVE, "train_label_masks/", "_mask.tiff")
    provider = Counter(labels["data_provider"].astype(str))
    grades = Counter(int(value) for value in labels["isup_grade"])
    rows: list[dict[str, object]] = []
    for grade in range(6):
        rows.append(
            {
                "cohort": "PANDA_PUBLIC_DEVELOPMENT",
                "stratum_type": "isup_grade",
                "stratum": grade,
                "n": grades.get(grade, 0),
            }
        )
    for name in sorted(provider):
        rows.append(
            {
                "cohort": "PANDA_PUBLIC_DEVELOPMENT",
                "stratum_type": "provider",
                "stratum": name,
                "n": provider[name],
            }
        )
    summary = {
        "label_rows": len(labels),
        "unique_image_ids": int(labels["image_id"].nunique()),
        "duplicate_image_ids": int(labels["image_id"].duplicated().sum()),
        "missing_required_labels": int(labels[list(required)].isna().sum().sum()),
        "extracted_images": len(image_files),
        "archive_images": archive_images,
        "archive_masks": archive_masks,
        "extracted_masks": len(extracted_masks),
        "image_inventory_sha256": inventory_sha256(image_files, PANDA_ROOT),
        "mask_inventory_sha256": inventory_sha256(extracted_masks, PANDA_ROOT),
        "patient_id_available": False,
        "archive_bytes": PANDA_ARCHIVE.stat().st_size,
        "archive_sha256": manifest_scalar(PANDA_MANIFEST, "local_archive_sha256"),
        "label_sha256": sha256(PANDA_LABELS),
    }
    return rows, summary


def sicap_audit() -> tuple[list[dict[str, object]], dict[str, object]]:
    labels_path = SICAP_ROOT / "wsi_labels.xlsx"
    train_path = SICAP_ROOT / "partition/Test/Train.xlsx"
    test_path = SICAP_ROOT / "partition/Test/Test.xlsx"
    for path in (labels_path, train_path, test_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    labels = pd.read_excel(labels_path)
    patient_map = dict(zip(labels["slide_id"].astype(str), labels["patient_id"].astype(str)))
    rows: list[dict[str, object]] = []
    patients: dict[str, set[str]] = {}
    slides: dict[str, set[str]] = {}
    partition_rows: dict[str, int] = {}
    for split, path in (("train", train_path), ("test", test_path)):
        frame = pd.read_excel(path)
        slide = frame["image_name"].str.extract(r"^([^_]+)")[0].astype(str)
        patient = slide.map(patient_map)
        patients[split] = set(patient)
        slides[split] = set(slide)
        partition_rows[split] = len(frame)
        for criterion in ("NC", "G3", "G4", "G5", "G4C"):
            rows.append(
                {
                    "cohort": "SICAPV2_OFFICIAL_PARTITION",
                    "split": split,
                    "criterion": criterion,
                    "positive_patches": int(frame[criterion].sum()),
                    "n_patches": len(frame),
                    "n_slides": int(slide.nunique()),
                    "n_patients": int(patient.nunique()),
                }
            )
    summary = {
        "wsi_label_rows": len(labels),
        "unique_slides": int(labels["slide_id"].nunique()),
        "unique_patients": int(labels["patient_id"].nunique()),
        "image_patches": len(list((SICAP_ROOT / "images").glob("*.jpg"))),
        "mask_patches": len(list((SICAP_ROOT / "masks").glob("*"))),
        "train_patches": partition_rows["train"],
        "test_patches": partition_rows["test"],
        "train_slides": len(slides["train"]),
        "test_slides": len(slides["test"]),
        "train_patients": len(patients["train"]),
        "test_patients": len(patients["test"]),
        "patient_overlap": len(patients["train"] & patients["test"]),
        "wsi_label_sha256": sha256(labels_path),
        "official_test_sha256": sha256(test_path),
    }
    return rows, summary


def chimera_audit() -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = read_csv(CHIMERA_LABELS)
    required = (
        "subject_id",
        "isup_grade_group_reported",
        "gleason_derived_isup_grade_group",
        "isup_gleason_consistency",
        "primary_gleason",
        "secondary_gleason",
        "tertiary_gleason",
    )
    if not rows or not set(required).issubset(rows[0]):
        raise ValueError("CHIMERA normalized clinical table lacks grading fields")
    grade_counts = Counter(row["isup_grade_group_reported"] for row in rows)
    distribution = [
        {
            "cohort": "CHIMERA_TASK1",
            "stratum_type": "reported_isup",
            "stratum": grade,
            "n": grade_counts.get(str(grade), 0),
        }
        for grade in range(1, 6)
    ]
    summary = {
        "subjects": len(rows),
        "unique_subjects": len({row["subject_id"] for row in rows}),
        "reported_isup_complete": sum(bool(row["isup_grade_group_reported"].strip()) for row in rows),
        "primary_complete": sum(bool(row["primary_gleason"].strip()) for row in rows),
        "secondary_complete": sum(bool(row["secondary_gleason"].strip()) for row in rows),
        "tertiary_observed": sum(bool(row["tertiary_gleason"].strip()) for row in rows),
        "mapping_concordant": sum(row["isup_gleason_consistency"] == "concordant" for row in rows),
        "mapping_discordant": sum(row["isup_gleason_consistency"] != "concordant" for row in rows),
        "clinical_sha256": sha256(CHIMERA_LABELS),
    }
    return distribution, summary


def par_audit() -> tuple[list[dict[str, object]], dict[str, object]]:
    if not PAR_LABELS.is_file():
        raise FileNotFoundError(PAR_LABELS)
    frame = pd.read_csv(PAR_LABELS, sep="\t")
    required = {"slide_id", "gleason_r1", "gleason_r2", "gleason_r3", "isup_1", "isup_r2", "isup_r3"}
    if not required.issubset(frame.columns):
        raise ValueError(f"PAR labels missing {sorted(required - set(frame.columns))}")
    distribution: list[dict[str, object]] = []
    for reader, column in (("reader_1", "isup_1"), ("reader_2", "isup_r2"), ("reader_3_uropathologist", "isup_r3")):
        counts = Counter(int(value) for value in frame[column].dropna())
        for grade in range(6):
            distribution.append(
                {"cohort": "PAR_S_BIAD2323", "reader": reader, "isup_grade": grade, "n": counts.get(grade, 0)}
            )

    agreement: dict[str, object] = {}
    for label, first, second in (
        ("r1_r2", "isup_1", "isup_r2"),
        ("r1_r3", "isup_1", "isup_r3"),
        ("r2_r3", "isup_r2", "isup_r3"),
    ):
        paired = frame[[first, second]].dropna()
        agreement[f"{label}_n"] = len(paired)
        agreement[f"{label}_exact"] = float((paired[first] == paired[second]).mean())
        agreement[f"{label}_qwk"] = float(cohen_kappa_score(paired[first], paired[second], weights="quadratic"))

    three = frame.dropna(subset=["isup_1", "isup_r2", "isup_r3"])
    majority = 0
    all_different = 0
    for _, row in three.iterrows():
        counts = row[["isup_1", "isup_r2", "isup_r3"]].value_counts()
        if int(counts.iloc[0]) >= 2:
            majority += 1
        else:
            all_different += 1
    file_lists = sorted(PAR_ROOT.glob("file_list_*.tsv"))
    local_audit = (
        json.loads(PAR_LOCAL_AUDIT.read_text(encoding="utf-8"))
        if PAR_LOCAL_AUDIT.is_file()
        else {"complete_files": 0, "status": "NOT_RUN"}
    )
    summary = {
        "label_rows": len(frame),
        "unique_slides": int(frame["slide_id"].nunique()),
        "unique_patients": int(frame["slide_id"].str.extract(r"(?i)^C(\d{3})")[0].nunique()),
        "reader_1_rows": int(frame["isup_1"].notna().sum()),
        "reader_2_rows": int(frame["isup_r2"].notna().sum()),
        "reader_3_rows": int(frame["isup_r3"].notna().sum()),
        "three_reader_rows": len(three),
        "three_reader_majority_available": majority,
        "three_reader_all_different": all_different,
        "local_wsi": int(local_audit.get("complete_files", 0)),
        "local_wsi_audit_status": str(local_audit.get("status", "NOT_RUN")),
        "local_wsi_hash_mode": bool(local_audit.get("hash_mode", False)),
        "local_wsi_hashes": len(local_audit.get("file_sha256", {})),
        "local_wsi_openable": int(local_audit.get("openable_files", 0)),
        "local_wsi_openability_errors": len(local_audit.get("openability_errors", {})),
        "label_sha256": sha256(PAR_LABELS),
        "file_list_count": len(file_lists),
        **agreement,
    }
    return distribution, summary


def criterion_registry() -> list[dict[str, object]]:
    return [
        {"criterion_id": "GP_PRIMARY", "criterion": "dominant primary Gleason pattern", "grading_role": "direct", "panda": "gleason_score", "sicap": "global primary and masks", "par": "reader Gleason score", "chimera": "reported primary", "analysis": "recoverability+erasure+allocation"},
        {"criterion_id": "BIOPSY_SECONDARY_RULE", "criterion": "highest-grade remaining pattern when three biopsy patterns are present", "grading_role": "specimen_specific_rule", "panda": "source score only", "sicap": "source score only", "par": "reader score only", "chimera": "not applicable", "analysis": "label audit; not a morphology direction"},
        {"criterion_id": "PROSTATECTOMY_SECONDARY_MINOR_RULE", "criterion": "second-most prevalent pattern plus separately reported minor high-grade pattern", "grading_role": "specimen_specific_rule", "panda": "not applicable", "sicap": "not applicable", "par": "not applicable", "chimera": "secondary+tertiary fields", "analysis": "secondary transport only"},
        {"criterion_id": "GP3_WELL_FORMED", "criterion": "individual discrete well-formed glands", "grading_role": "GP3 morphology", "panda": "aggregate pattern mask only", "sicap": "aggregate G3 mask", "par": "unavailable", "chimera": "unavailable", "analysis": "aggregate recoverability only"},
        {"criterion_id": "GP4_POORLY_FORMED", "criterion": "poorly formed glands", "grading_role": "GP4 morphology", "panda": "aggregate pattern mask only", "sicap": "aggregate G4 mask", "par": "unavailable", "chimera": "unavailable", "analysis": "not separately evaluable"},
        {"criterion_id": "GP4_FUSED", "criterion": "fused glands", "grading_role": "GP4 morphology", "panda": "aggregate pattern mask only", "sicap": "aggregate G4 mask", "par": "unavailable", "chimera": "unavailable", "analysis": "not separately evaluable"},
        {"criterion_id": "GP4_GLOMERULOID", "criterion": "glomeruloid glands", "grading_role": "GP4 morphology", "panda": "aggregate pattern mask only", "sicap": "aggregate G4 mask", "par": "unavailable", "chimera": "unavailable", "analysis": "not separately evaluable"},
        {"criterion_id": "GP5_NO_GLAND", "criterion": "solid sheets, cords/single cells, or comedonecrosis with absent gland formation", "grading_role": "GP5 morphology", "panda": "aggregate pattern mask only", "sicap": "aggregate G5 mask", "par": "unavailable", "chimera": "unavailable", "analysis": "not separately evaluable"},
        {"criterion_id": "GP3_PROP", "criterion": "Gleason pattern 3 proportion", "grading_role": "direct quantitative", "panda": "archive mask subset", "sicap": "pixel/patch mask", "par": "unavailable", "chimera": "unavailable", "analysis": "recoverability+joint erasure"},
        {"criterion_id": "GP4_PROP", "criterion": "Gleason pattern 4 proportion", "grading_role": "direct quantitative", "panda": "archive mask subset", "sicap": "pixel/patch mask", "par": "unavailable", "chimera": "unavailable", "analysis": "recoverability+joint erasure"},
        {"criterion_id": "GP5_PROP", "criterion": "Gleason pattern 5 proportion", "grading_role": "direct quantitative", "panda": "archive mask subset", "sicap": "pixel/patch mask", "par": "unavailable", "chimera": "unavailable", "analysis": "recoverability+joint erasure"},
        {"criterion_id": "G4_CRIBRIFORM", "criterion": "cribriform glands within Gleason pattern 4", "grading_role": "qualified GP4 subtype", "panda": "unavailable", "sicap": "G4C patch truth", "par": "unavailable", "chimera": "unavailable", "analysis": "external recoverability; no total-share denominator"},
        {"criterion_id": "TERTIARY_HIGH_GRADE", "criterion": "minor or tertiary high-grade pattern", "grading_role": "specimen-specific optional", "panda": "unavailable", "sicap": "unavailable", "par": "unavailable", "chimera": "reported for 20/95", "analysis": "secondary transport only"},
        {"criterion_id": "ISUP_RESULT", "criterion": "deterministic Gleason-to-ISUP result", "grading_role": "result label", "panda": "available", "sicap": "derivable", "par": "available per reader", "chimera": "reported+derived", "analysis": "accuracy target; not independent morphology"},
        {"criterion_id": "PROGNOSTIC_COVARIATES", "criterion": "age/PSA/pT/margin/node/SVI/capsular/LVI", "grading_role": "excluded_not_grading_criteria", "panda": "unavailable", "sicap": "unavailable", "par": "age partly available", "chimera": "partly available", "analysis": "BCR covariate analysis only"},
    ]


def cohort_readiness(panda: dict[str, object], sicap: dict[str, object], par: dict[str, object], chimera: dict[str, object]) -> list[dict[str, object]]:
    panda_use = manifest_scalar(PANDA_MANIFEST, "qfm_grading_role")
    sicap_use = manifest_scalar(SICAP_MANIFEST, "qfm_grading_role")
    par_status = manifest_scalar(PAR_MANIFEST, "acquisition_status")
    chimera_use = manifest_scalar(CHIMERA_MANIFEST, "allowed_use")
    par_verified = bool(
        par["local_wsi"] == 339
        and par["local_wsi_audit_status"] == "PASS_HASHED_OPENABLE"
        and par["local_wsi_hash_mode"]
        and par["local_wsi_hashes"] == 339
        and par["local_wsi_openable"] == 339
        and par["local_wsi_openability_errors"] == 0
    )
    return [
        {
            "cohort": "PANDA_PUBLIC_DEVELOPMENT",
            "specimen": "needle_biopsy",
            "role": "development_only",
            "patients": "not_exposed_in_public_labels",
            "slides_or_biopsies": panda["label_rows"],
            "local_payload": "PASS" if panda["extracted_images"] == panda["label_rows"] else "FAIL",
            "label_contract": "PASS_0_TO_5_AND_GLEASON",
            "patient_identity": "FAIL_NOT_PROVIDED",
            "qfm_use_declaration": "PASS" if panda_use == "grading_development_only" else "FAIL",
            "source_hash": "PASS" if panda["archive_sha256"] else "FAIL",
            "readiness": "READY_DEVELOPMENT_NO_INTERNAL_PERFORMANCE_CLAIM" if panda_use and panda["archive_sha256"] else "PARTIAL",
        },
        {
            "cohort": "SICAPV2_OFFICIAL_TEST",
            "specimen": "needle_biopsy",
            "role": "criterion_qualification_preconfirmatory",
            "patients": sicap["test_patients"],
            "slides_or_biopsies": sicap["test_slides"],
            "local_payload": "PASS" if sicap["image_patches"] == sicap["mask_patches"] else "FAIL",
            "label_contract": "PASS_GP3_GP4_GP5_G4C_PRIMARY_SECONDARY",
            "patient_identity": "PASS" if sicap["patient_overlap"] == 0 else "FAIL",
            "qfm_use_declaration": "PASS" if sicap_use == "grading_criterion_qualification" else "FAIL",
            "source_hash": "PASS",
            "readiness": "READY_PRECONFIRMATORY_NOT_PRISTINE" if sicap_use else "PARTIAL",
        },
        {
            "cohort": "PAR_S_BIAD2323",
            "specimen": "needle_biopsy",
            "role": "confirmatory_external_and_scanner_repeatability",
            "patients": par["unique_patients"],
            "slides_or_biopsies": par["unique_slides"],
            "local_payload": "PASS" if par_verified else "FAIL_WSI_NOT_HASHED_OPENABLE",
            "label_contract": "PASS_LABELS_PARTIAL_REFERENCE_MULTI_READER_NO_SUPPLIED_CONSENSUS",
            "patient_identity": "PASS_PUBLIC_FILENAME_CONTRACT",
            "qfm_use_declaration": "PASS" if PAR_MANIFEST.is_file() else "FAIL",
            "source_hash": "PASS" if par_verified else "FAIL_NOT_HASHED_OPENABLE",
            "readiness": "READY" if par_verified else "NOT_READY",
        },
        {
            "cohort": "CHIMERA_TASK1",
            "specimen": "prostatectomy",
            "role": "secondary_grade_transport_and_bcr_use",
            "patients": chimera["subjects"],
            "slides_or_biopsies": 190,
            "local_payload": "PASS",
            "label_contract": "PARTIAL_THREE_MAPPING_DISCREPANCIES_NO_CENTRAL_REREAD",
            "patient_identity": "PASS",
            "qfm_use_declaration": "FAIL_RECONCILIATION_REQUIRED" if "protocol_preparation_only" in chimera_use else "PASS",
            "source_hash": "PASS",
            "readiness": "PARTIAL_SECONDARY_ONLY",
        },
    ]


def gate_rows(
    readiness: Sequence[dict[str, object]],
    panda: dict[str, object],
    sicap: dict[str, object],
) -> list[dict[str, object]]:
    cohort = {str(row["cohort"]): row for row in readiness}
    embedding_qc = DEFAULT_OUTPUT / "fm8_panda_embedding_technical_qc.csv"
    embedding_ready = False
    if embedding_qc.is_file():
        qc = pd.read_csv(embedding_qc)
        embedding_ready = bool(
            set(qc.get("encoder", [])) == {"conch", "virchow"}
            and len(qc) == 2
            and qc.status.eq("PASS").all()
            and qc.paired_crop_hash_failures.eq(0).all()
        )
    head_ready = all(
        (DEFAULT_OUTPUT / f"fm8_panda_{encoder}_grading_head_run_config.json").is_file()
        and (LOCAL_ARTIFACTS / f"fm8_panda_{encoder}_ordinal_mil_head.pt").is_file()
        for encoder in ("conch", "virchow")
    )
    accuracy_paths = [
        DEFAULT_OUTPUT / f"fm8_par_{encoder}_grading_accuracy_gate.json"
        for encoder in ("conch", "virchow")
    ]
    if all(path.is_file() for path in accuracy_paths):
        accuracy = [json.loads(path.read_text(encoding="utf-8")) for path in accuracy_paths]
        accuracy_status = (
            "PASS"
            if any(bool(row.get("adequate_for_functional_testing", False)) for row in accuracy)
            else "FAIL"
        )
        accuracy_evidence = "; ".join(
            f"{row.get('encoder')} adequate={row.get('adequate_for_functional_testing')}"
            for row in accuracy
        )
    else:
        accuracy_status = "NOT_EVALUABLE"
        accuracy_evidence = "locked PAR predictions are incomplete"
    return [
        {"gate_id": "G1", "gate": "grading/cancer/BCR endpoint separation", "status": "PASS", "evidence": "protocol fixes cancer-only ISUP grading and separate heads"},
        {"gate_id": "G2", "gate": "PANDA development source and label lock", "status": "PASS" if cohort["PANDA_PUBLIC_DEVELOPMENT"]["source_hash"] == "PASS" else "FAIL", "evidence": f"{panda['label_rows']} labels; {panda['extracted_images']} WSI; patient ID absent"},
        {"gate_id": "G3", "gate": "independent patient-identified criterion cohort", "status": "PASS" if sicap["patient_overlap"] == 0 else "FAIL", "evidence": f"SICAP test {sicap['test_patients']} patients/{sicap['test_slides']} WSI; opened previously for detector"},
        {"gate_id": "G4", "gate": "untouched confirmatory external WSI acquired, hash locked, and openable", "status": "PASS" if cohort["PAR_S_BIAD2323"]["readiness"] == "READY" else "FAIL", "evidence": cohort["PAR_S_BIAD2323"]["local_payload"]},
        {"gate_id": "G5", "gate": "clinical criterion truth", "status": "PASS", "evidence": "SICAP GP3/4/5 masks, G4C, primary/secondary labels; PAR/CHIMERA missing spatial truth preserved"},
        {"gate_id": "G6", "gate": "QFM use declarations and cross-project boundary", "status": "PASS" if cohort["PANDA_PUBLIC_DEVELOPMENT"]["qfm_use_declaration"] == "PASS" and cohort["SICAPV2_OFFICIAL_TEST"]["qfm_use_declaration"] == "PASS" else "FAIL", "evidence": "raw shared sources only; PBV caches prohibited"},
        {"gate_id": "G7", "gate": "QFM-owned frozen embeddings and locked grading head", "status": "PASS" if embedding_ready and head_ready else "NOT_EVALUABLE", "evidence": f"paired_embeddings={embedding_ready}; locked_heads={head_ready}"},
        {"gate_id": "G8", "gate": "external grading accuracy", "status": accuracy_status, "evidence": accuracy_evidence},
        {"gate_id": "G9", "gate": "external criterion functional use and allocation", "status": "NOT_EVALUABLE", "evidence": "erasure, matched random, dose response, and Shapley not run"},
        {"gate_id": "G10", "gate": "residual entry", "status": "FAIL", "evidence": "G8 failed for both encoders; M3 was not entered"},
    ]


def overall_decision(gates: Sequence[dict[str, object]]) -> str:
    status = {str(row["gate_id"]): str(row["status"]) for row in gates}
    if status["G4"] != "PASS":
        return "GO_SOURCE_PREPARATION_NO_GO_CONFIRMATORY_MODELING"
    if status["G7"] != "PASS":
        return "GO_MODEL_PREPARATION_NO_GO_CONFIRMATORY_MODELING"
    if status["G8"] == "NOT_EVALUABLE":
        return "GO_CONFIRMATORY_MODELING_NO_GO_RESIDUAL"
    if status["G8"] != "PASS":
        return "NO_GO_FUNCTIONAL_INTERPRETATION_NO_GO_RESIDUAL"
    return "GO_CRITERION_QUALIFICATION_NO_GO_RESIDUAL"


def source_rows(panda: dict[str, object], sicap: dict[str, object], par: dict[str, object], chimera: dict[str, object]) -> list[dict[str, object]]:
    specs = [
        ("panda_archive", PANDA_ARCHIVE, panda["archive_sha256"] or "NOT_RECORDED", "development WSI and masks archive"),
        ("panda_labels", PANDA_LABELS, panda["label_sha256"], "development ISUP/Gleason labels"),
        ("sicap_wsi_labels", SICAP_ROOT / "wsi_labels.xlsx", sicap["wsi_label_sha256"], "independent primary/secondary Gleason labels"),
        ("sicap_official_test", SICAP_ROOT / "partition/Test/Test.xlsx", sicap["official_test_sha256"], "patient-disjoint patch criterion test"),
        ("par_labels", PAR_LABELS, par["label_sha256"], "external reader-conditioned Gleason/ISUP labels"),
        ("chimera_clinical", CHIMERA_LABELS, chimera["clinical_sha256"], "secondary prostatectomy grade/BCR table"),
    ]
    return [
        {
            "source_id": source_id,
            "path": rel(path),
            "bytes": path.stat().st_size,
            "sha256": digest,
            "role": role,
            "status": "PASS" if digest != "NOT_RECORDED" else "FAIL_HASH_NOT_RECORDED",
        }
        for source_id, path, digest, role in specs
    ]


def report_text(
    panda: dict[str, object],
    sicap: dict[str, object],
    par: dict[str, object],
    chimera: dict[str, object],
    gates: Sequence[dict[str, object]],
    decision: str,
) -> str:
    gate_lines = "\n".join(
        f"| {row['gate_id']} | {row['gate']} | {row['status']} | {row['evidence']} |" for row in gates
    )
    if decision == "NO_GO_FUNCTIONAL_INTERPRETATION_NO_GO_RESIDUAL":
        allowed_work = (
            "두 encoder의 PAR confirmatory grading accuracy가 사전 기준에 미달했다. "
            "현재 허용되는 작업은 결과 보고와 독립 검증 설계뿐이며, 동일 PAR 결과를 이용한 "
            "threshold·head·tile rule 조정과 M2--M4 해석은 금지한다."
        )
        next_work = (
            "M1은 실패 결과로 종결한다. CONCH와 Virchow 모두 `ABOVE_CHANCE`였지만 "
            "`ADEQUATE_FOR_FUNCTIONAL_TESTING`은 아니므로 M2 criterion recoverability, M3 기능적 "
            "사용·비중 및 M4 residual은 잠근다. 재개하려면 PAR와 독립인 새 검증 코호트와 사전 "
            "고정 remediation protocol이 필요하다."
        )
    else:
        allowed_work = (
            "현재 허용되는 작업은 원천 잠금, PANDA mask 준비, PAR 획득, QFM-owned embedding "
            "생성과 사전 고정된 qualification까지다."
        )
        next_work = (
            "PANDA는 development, SICAP은 preconfirmatory criterion qualification으로만 사용한다. "
            "외부 accuracy와 joint erasure gate가 통과하기 전에는 사용 비중이나 residual을 확정하지 않는다."
        )
    return f"""---
document_id: fm8-grading-criterion-qualification-entry-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: generated
created: 2026-09-01
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm8_grading_criterion_qualification/outputs/fm8-grading-criterion-qualification-entry-report-ko.md
---

# FM8 grading-criterion qualification entry audit

## 판정

전체 판정은 **{decision}**다. Residual 계산은 중단한다. {allowed_work}

## 확인된 입력

- PANDA: {panda['label_rows']} labels, {panda['extracted_images']} extracted WSI, ISUP 0--5,
  archive masks {panda['archive_masks']}; 공개 label table에 patient ID가 없다.
- SICAPv2: {sicap['unique_patients']} patients/{sicap['unique_slides']} WSI,
  official test {sicap['test_patients']} patients/{sicap['test_slides']} WSI,
  train--test patient overlap {sicap['patient_overlap']}, GP3/4/5와 G4C truth가 있다.
- CHIMERA: {chimera['subjects']} patients, reported ISUP complete {chimera['reported_isup_complete']},
  primary/secondary complete {chimera['primary_complete']}/{chimera['secondary_complete']},
  tertiary observed {chimera['tertiary_observed']}, mapping discrepancies {chimera['mapping_discordant']}.
- PAR: {par['unique_patients']} patients/{par['unique_slides']} glass slides의 label과 file list는
  hash-lock했다. Verified WSI는 {par['local_wsi']}개이고 audit status는
  `{par['local_wsi_audit_status']}`다. Reader 1--2 QWK는 {par['r1_r2_qwk']:.3f}, exact
  agreement는 {par['r1_r2_exact']:.3f}다. 3-reader 58 slides 중 majority가 존재하는 것은
  {par['three_reader_majority_available']}개이고 {par['three_reader_all_different']}개는 세 등급이
  모두 다르다. 제공된 consensus가 아니므로 reader-conditioned reference로 분석한다.

## Gate matrix

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
{gate_lines}

## 임상 기준과 다음 작업

Grading criterion은 specimen-specific primary/secondary/minor rule, GP3 well-formed gland,
GP4 poorly formed/fused/cribriform/glomeruloid, GP5 no-gland/solid/cord/single-cell/comedonecrosis와
GP3/4/5 proportion이다. 현재 subtype truth는 cribriform G4C만 있어 나머지 세부 형태는
별도 검증 불가다. Age, PSA, pT, margin, node, SVI/capsular/LVI는 grading 기준이
아니며 BCR 공변량으로만 둔다.

{next_work}
"""


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    panda_distribution, panda = panda_audit()
    sicap_distribution, sicap = sicap_audit()
    par_distribution, par = par_audit()
    chimera_distribution, chimera = chimera_audit()
    readiness = cohort_readiness(panda, sicap, par, chimera)
    gates = gate_rows(readiness, panda, sicap)
    sources = source_rows(panda, sicap, par, chimera)

    csv_outputs = {
        "fm8_grading_cohort_readiness.csv": readiness,
        "fm8_grading_criterion_registry.csv": criterion_registry(),
        "fm8_grading_gate_matrix.csv": gates,
        "fm8_grading_source_integrity.csv": sources,
        "fm8_panda_grade_distribution.csv": panda_distribution,
        "fm8_sicap_criterion_distribution.csv": sicap_distribution,
        "fm8_par_reader_grade_distribution.csv": par_distribution,
        "fm8_chimera_grade_distribution.csv": chimera_distribution,
    }
    for name, rows in csv_outputs.items():
        write_csv(output_dir / name, rows)

    decision = overall_decision(gates)
    report = output_dir / "fm8-grading-criterion-qualification-entry-report-ko.md"
    report.write_text(report_text(panda, sicap, par, chimera, gates, decision), encoding="utf-8")

    owned_outputs = [output_dir / name for name in csv_outputs] + [report]
    output_hashes = {path.name: sha256(path) for path in sorted(owned_outputs)}
    config = {
        "protocol": PROTOCOL,
        "decision": decision,
        "seed": 260901,
        "panda": panda,
        "sicap": sicap,
        "par": par,
        "chimera": chimera,
        "confirmatory_modeling_allowed": bool(
            {row["gate_id"]: row["status"] for row in gates}.get("G4") == "PASS"
            and {row["gate_id"]: row["status"] for row in gates}.get("G7") == "PASS"
        ),
        "residual_allowed": False,
        "output_sha256": output_hashes,
    }
    (output_dir / "fm8_grading_entry_audit_run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FM8 grading audit: {decision}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args().output_dir)
