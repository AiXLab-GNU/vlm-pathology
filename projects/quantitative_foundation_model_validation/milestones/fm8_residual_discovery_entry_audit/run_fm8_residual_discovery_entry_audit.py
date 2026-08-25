#!/usr/bin/env python3
"""Generate the read-only FM8 residual-discovery entry audit bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm8_residual_discovery_entry_audit"
DEFAULT_OUTPUT = MILESTONE / "outputs"
PROTOCOL_ID = "fm8-residual-discovery-entry-audit-protocol"
SEED = 260825

FM2 = PROJECT / "milestones/fm2_paired_manifest/outputs"
FM3 = PROJECT / "milestones/fm3_paired_embeddings/outputs"
FM4 = PROJECT / "milestones/fm4_concept_benchmark/outputs"
FM5 = PROJECT / "milestones/fm5_cross_model_comparison/outputs"
FM6_DEV = PROJECT / "milestones/fm6_development_source_package/outputs"
FM6_INTERNAL = PROJECT / "milestones/fm6_internal_development_pilot/outputs"
FM6_SITE = PROJECT / "milestones/fm6_site_heldout_functional_validation/outputs"
FM6_LEOPARD = PROJECT / "milestones/fm6_external_functional_validation/outputs"
FM6_CHIMERA = PROJECT / "milestones/fm6_chimera_external_functional_validation/outputs"
FM6_ACQ = PROJECT / "milestones/fm6_external_cohort_acquisition/outputs"
QFM_DATA = ROOT / "resources/data/quantitative_foundation_model_validation/local-data"
QFM_ART = ROOT / "resources/artifacts/quantitative_foundation_model_validation"
TCGA_ART = QFM_ART / "fm6_internal_development_pilot"
LEOPARD_ART = QFM_ART / "fm6_external_functional_validation"
CHIMERA_ART = QFM_ART / "fm6_chimera_external_functional_validation"
PRECISE_ATTEMPT = PROJECT / (
    "preexperiment/governance_records/clean_rerun/attempt-20260812T135439Z"
)

MISSING_TOKENS = {
    "",
    "na",
    "nan",
    "none",
    "null",
    "unknown",
    "not_available",
    "not_documented",
}


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[dict[str, object]], fields: Sequence[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def missing(value: object) -> bool:
    return str(value).strip().lower() in MISSING_TOKENS


def duplicate_count(rows: Sequence[dict[str, str]], keys: Sequence[str]) -> int:
    values = [tuple(row[key] for key in keys) for row in rows]
    return len(values) - len(set(values))


def subject_fold_violations(
    rows: Sequence[dict[str, str]], subject: str, fold: str
) -> int:
    mapping: dict[str, set[str]] = {}
    for row in rows:
        mapping.setdefault(row[subject], set()).add(row[fold])
    return sum(len(folds) != 1 for folds in mapping.values())


def unique_count(rows: Sequence[dict[str, str]], field: str) -> int:
    return len({row[field] for row in rows if not missing(row[field])})


def evidence_manifest() -> list[dict[str, object]]:
    sources = [
        ("fm2_manifest", FM2 / "paired_sample_manifest.csv", "paired coordinates and PRECISE truth"),
        ("fm3_conch_embedding", PRECISE_ATTEMPT / "precise_conch_shared_fov_embeddings.npy", "frozen PRECISE CONCH embedding"),
        ("fm3_virchow_embedding", PRECISE_ATTEMPT / "precise_virchow_shared_fov_embeddings.npy", "frozen PRECISE Virchow embedding"),
        ("tcga_subjects", QFM_DATA / "tcga_prad_current_gdc_bcr/development_subjects.csv", "QFM-owned TCGA metric and outcome table"),
        ("tcga_tiles", FM6_INTERNAL / "fm6_tcga_whole_tissue_tile_manifest.csv", "TCGA paired physical-FOV membership"),
        ("tcga_predictions", FM6_INTERNAL / "fm6_tcga_patient_oof_predictions.csv", "locked-rule OOF scores and covariates"),
        ("tcga_conch_embedding", TCGA_ART / "fm6_tcga_conch_tile_embeddings.npy", "TCGA CONCH embedding"),
        ("tcga_virchow_embedding", TCGA_ART / "fm6_tcga_virchow_tile_embeddings.npy", "TCGA Virchow embedding"),
        ("tcga_technical", FM6_DEV / "fm6_tcga_wsi_technical_distribution.csv", "TCGA MPP/scanner/compression summary"),
        ("siteheldout_predictions", FM6_SITE / "fm6_site_heldout_subject_predictions.csv", "TCGA internal site-heldout predictions"),
        ("leopard_tiles", LEOPARD_ART / "fm6_leopard_tile_manifest.csv", "LEOPARD paired physical-FOV membership"),
        ("leopard_predictions", LEOPARD_ART / "fm6_leopard_patient_predictions.csv", "LEOPARD outcome and locked scores"),
        ("leopard_conch_embedding", LEOPARD_ART / "fm6_leopard_conch_tile_embeddings.npy", "LEOPARD CONCH embedding"),
        ("leopard_virchow_embedding", LEOPARD_ART / "fm6_leopard_virchow_tile_embeddings.npy", "LEOPARD Virchow embedding"),
        ("chimera_clinical", QFM_DATA / "chimera_task1/normalized_clinical.csv", "CHIMERA metric, outcome, and clinical table"),
        ("chimera_tiles", CHIMERA_ART / "fm6_chimera_tile_manifest.csv", "CHIMERA paired physical-FOV membership"),
        ("chimera_predictions", CHIMERA_ART / "analysis_runs/primary/fm6_chimera_patient_predictions.csv", "CHIMERA locked scores"),
        ("chimera_conch_embedding", CHIMERA_ART / "fm6_chimera_conch_tile_embeddings.npy", "CHIMERA CONCH embedding"),
        ("chimera_virchow_embedding", CHIMERA_ART / "fm6_chimera_virchow_tile_embeddings.npy", "CHIMERA Virchow embedding"),
        ("chimera_source_verification", CHIMERA_ART / "source_verification.json", "CHIMERA source payload verification"),
    ]
    result = []
    for source_id, path, role in sources:
        if not path.is_file():
            raise FileNotFoundError(path)
        result.append(
            {
                "source_id": source_id,
                "owner_project": "quantitative_foundation_model_validation",
                "path": relative(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "role": role,
                "availability": "PASS",
            }
        )
    return result


def source_integrity_rows() -> list[dict[str, object]]:
    specs = [
        (FM2 / "paired_sample_manifest.csv", ("sample_id",), "subject_id", "fold", 1218),
        (FM3 / "embedding_row_manifest.csv", ("embedding_row",), "subject_id", "fold", 1218),
        (FM4 / "fm4_subject_predictions.csv", ("encoder", "subject_id"), "subject_id", "outer_fold", 50),
        (FM5 / "fm5_discordance_manifest.csv", ("subject_id",), "subject_id", "outer_fold", 25),
        (QFM_DATA / "tcga_prad_current_gdc_bcr/development_subjects.csv", ("case_id",), "case_id", "", 392),
        (FM6_INTERNAL / "fm6_tcga_whole_tissue_tile_manifest.csv", ("tile_id",), "case_id", "outer_fold", 27968),
        (FM6_INTERNAL / "fm6_tcga_patient_oof_predictions.csv", ("encoder", "case_id"), "case_id", "outer_fold", 784),
        (FM6_SITE / "fm6_site_heldout_subject_predictions.csv", ("encoder", "case_id"), "case_id", "", 578),
        (LEOPARD_ART / "fm6_leopard_tile_manifest.csv", ("tile_id",), "case_id", "", 32512),
        (LEOPARD_ART / "fm6_leopard_patient_predictions.csv", ("encoder", "case_id"), "case_id", "", 1016),
        (QFM_DATA / "chimera_task1/normalized_clinical.csv", ("subject_id",), "subject_id", "", 95),
        (CHIMERA_ART / "fm6_chimera_tile_manifest.csv", ("tile_id",), "subject_id", "", 12160),
        (CHIMERA_ART / "analysis_runs/primary/fm6_chimera_patient_predictions.csv", ("encoder", "subject_id"), "subject_id", "", 190),
    ]
    output = []
    for path, keys, subject, fold, expected_rows in specs:
        rows = read_csv(path)
        columns = list(rows[0]) if rows else []
        missing_cells = sum(missing(row[column]) for row in rows for column in columns)
        fold_violations = subject_fold_violations(rows, subject, fold) if fold else 0
        status = "PASS" if len(rows) == expected_rows and duplicate_count(rows, keys) == 0 and fold_violations == 0 else "FAIL"
        output.append(
            {
                "path": relative(path),
                "rows": len(rows),
                "expected_rows": expected_rows,
                "columns": len(columns),
                "unique_patients": unique_count(rows, subject),
                "missing_cells": missing_cells,
                "duplicate_key_rows": duplicate_count(rows, keys),
                "patient_fold_violations": fold_violations,
                "sha256": sha256(path),
                "status": status,
            }
        )
    return output


def availability_rows() -> list[dict[str, object]]:
    rows = []

    def add(cohort: str, scope: str, encoder: str, n: int, slides: object, tiles: int, events: object,
            embedding: str, score: str, pairing: str, fold: str, metric: str, clinical: str,
            technical: str, outcome: str, metadata: str, provenance: str, rerun: str, use: str) -> None:
        rows.append({
            "cohort": cohort,
            "evidence_scope": scope,
            "encoder": encoder,
            "n_patients": n,
            "n_slides_or_sessions": slides,
            "n_tiles": tiles,
            "n_events": events,
            "frozen_embedding_and_weight_hash": embedding,
            "locked_disease_score_or_head": score,
            "paired_membership_and_coordinates": pairing,
            "patient_grouped_fold": fold,
            "known_metric_M": metric,
            "clinical_covariate_C": clinical,
            "technical_qc_covariate_Q": technical,
            "outcome_Y": outcome,
            "site_stain_scanner_mpp_tissue_grade_specimen": metadata,
            "provenance_and_hash": provenance,
            "clean_rerun": rerun,
            "fm8_entry_use": use,
        })

    for encoder in ("CONCH", "Virchow"):
        dim = 512 if encoder == "CONCH" else 2560
        add("PRECISE-FM2-FM5", "internal descriptive H1", encoder, 25, 27, 1218, "NA",
            f"PASS {dim}D; revision+weight+array SHA-256", "FAIL no disease score/head",
            "PASS 1:1 crop hash and physical boundary", "PASS five subject folds",
            "tumor_fraction only", "FAIL none", "PARTIAL MPP+tissue fraction",
            "FAIL no independent disease outcome", "FAIL scanner/stain/site/specimen detail absent",
            "PASS FM2/FM3 hash chain", "PASS FM4 11/11 and FM5 9/9", "not source for FM8 disease residual")
        add("TCGA-PRAD", "source internal whole-tissue", encoder, 392, 437, 27968, 80,
            f"PASS {dim}D; model/weight/input hashes", "PARTIAL OOF full_risk saved; head procedural not serialized",
            "PASS 1:1 crop hashes and row order", "PASS five patient folds",
            "ISUP only", "PARTIAL age/path-T; treatment documentation flags only; original age/path-T provenance crosses PBV workspace",
            "PARTIAL MPP+tissue fraction+compression; no color/blur/fold QC", "PASS BCR status/time",
            "PARTIAL TSS site+MPP+scanner(23/437 missing)+grade; stain/color/specimen/tumor purity absent",
            "PASS QFM source/output hashes", "PASS 20/20 nonvolatile", "candidate source after blockers")
        add("TCGA-PRAD-7-site", "internal site-heldout, not external", encoder, 289, "subset of 437", 0, 69,
            "PASS source patient embeddings", "PASS site-heldout scores saved",
            "PASS patient paired", "PASS leave-site-out within seven eligible sites",
            "ISUP only", "PARTIAL same TCGA limitations", "PARTIAL same TCGA limitations",
            "PASS BCR status/time", "PARTIAL seven TSS sites; same stain/QC gaps",
            "PASS run-config hashes", "PASS locked run; no separate exact-hash comparison", "internal stability evidence only")
        add("LEOPARD", "independent external", encoder, 508, 508, 32512, 87,
            f"PASS {dim}D; paired array present", "PASS TCGA-locked full/erased risk saved",
            "PASS 1:1 crop hashes and coordinates", "NA target receives locked rule",
            "FAIL ISUP/Gleason absent", "FAIL treatment and clinical panel absent",
            "PARTIAL MPP+tissue mask fraction only", "PASS BCR/follow-up",
            "FAIL site/stain/scanner/grade/specimen/color/QC absent", "PARTIAL source/label hashes; embedding arrays lack independent registered hash in lock",
            "PASS reported exact rerun", "not evaluable for same-panel residual recurrence")
        add("CHIMERA", "independent external", encoder, 95, 190, 12160, 27,
            f"PASS {dim}D; model/weight/array hashes", "PASS TCGA-locked full/erased risk saved",
            "PASS 1:1 physical FOV and decoded crop hash", "NA target receives locked rule",
            "PASS ISUP/Gleason; 3/95 discordant", "PARTIAL age/PSA/pT/margins etc.; earlier therapy missing 93/95",
            "PARTIAL MPP+tissue mask fraction only", "PASS BCR status/months; endpoint equivalence not established",
            "PARTIAL prostatectomy+grade+MPP; site/stain/scanner/color/blur/fold/compression absent",
            "PASS 475-object source verification and run hashes", "PASS 6/6 nonvolatile", "numeric recurrence candidate; shortcut/review blockers remain")
    return rows


def estimand_rows() -> list[dict[str, object]]:
    return [
        {"estimand": "Rscore", "item": "definition", "locked_specification": "S_k - g_k(M,C,Q)", "leakage_control": "g fit in source outer-training fold only", "status": "PASS"},
        {"estimand": "Rscore", "item": "analysis_unit", "locked_specification": "patient", "leakage_control": "all slides/tiles remain in patient fold", "status": "PASS"},
        {"estimand": "Rscore", "item": "model_family", "locked_specification": "ridge; alpha 0.01,0.1,1,10,100,1000; inner grouped CV one-SE", "leakage_control": "normalization/imputation/vocabulary trained in fold", "status": "PASS"},
        {"estimand": "Rscore", "item": "prediction", "locked_specification": "one OOF residual per patient and encoder", "leakage_control": "no target recalibration or outcome thresholding", "status": "PASS"},
        {"estimand": "Rrepr", "item": "definition", "locked_specification": "(I-P_M,k) Z_k", "leakage_control": "P_M,k estimated in source outer-training fold", "status": "PASS"},
        {"estimand": "Rrepr", "item": "analysis_unit", "locked_specification": "paired 394.24um physical-FOV tile with slide/patient clusters", "leakage_control": "patient fold controls all tiles", "status": "PASS"},
        {"estimand": "Rrepr", "item": "rank_regularization", "locked_specification": "ridge alpha budget as above; rank 1,2,4,8 with one-SE smallest rank; current ISUP panel max rank 1", "leakage_control": "encoder-specific train-fold fit only", "status": "PASS"},
        {"estimand": "Rrepr", "item": "ranking_scalar", "locked_specification": "Trepr_k=zscore_train(w_k^T Rrepr_k)", "leakage_control": "w, mean, SD locked from source training fold", "status": "PASS"},
        {"estimand": "both", "item": "manifest", "locked_specification": "separate residual type/encoder/unit manifests", "leakage_control": "no merged estimand or component matching", "status": "PASS"},
        {"estimand": "both", "item": "interpretation", "locked_specification": "residual after the available prespecified metric panel", "leakage_control": "no all-known-pathology or biomarker language", "status": "PASS"},
        {"estimand": "both", "item": "existing_stability", "locked_specification": "no residual manifest or fold/seed/rank stability result exists", "leakage_control": "must be evaluated after metadata repair and before review", "status": "NOT-EVALUABLE"},
    ]


def source_lock_rows() -> list[dict[str, object]]:
    specs = [
        ("source_cohort", "TCGA-PRAD 392 patients/80 events/437 WSI whole-tissue"),
        ("analysis_unit", "Rscore patient; Rrepr paired tile clustered by slide and patient"),
        ("inclusion_exclusion", "complete paired embedding+OOF score+ISUP+BCR+fold; explicit reason otherwise"),
        ("patient_grouping", "existing five folds shared across encoders"),
        ("model_hyperparameter", "ridge and fixed alpha/rank budgets; inner grouped CV one-SE"),
        ("positive_negative_threshold", "source OOF <=q10 or >=q90; no target change"),
        ("discordance_threshold", "absolute encoder percentile gap >=0.50"),
        ("common_residual", "same FOV, same sign, both extreme; morphology not presumed common biology"),
        ("matched_control", "both encoders p25-p75; match site/ISUP/specimen/tissue quartile/slide when possible"),
        ("sampling_cap", "<=8 tiles/patient, <=2/slide, <=4 slides/patient"),
        ("quota", "balance residual type, encoder, sign, site, ISUP, tissue-fraction quartile"),
        ("seed_tie_break", "seed 260825; SHA256(protocol|seed|sample_id) order"),
        ("missing_not_evaluable", "preserve and do not backfill empty quota cells"),
        ("uncertainty", "2000 patient-cluster bootstraps; undefined retained"),
        ("multiplicity", "separate Rscore/Rrepr, encoder, and external-cohort families; BH-FDR"),
        ("target_rule", "no refit, recalibration, threshold, quota, rank, or regularization change"),
        ("review_sample_size", "requires outcome-blind pathologist burden approval before activation"),
    ]
    return [{"lock_item": item, "prespecified_rule": rule, "target_locked": "yes", "activation_status": "LOCKED_CANDIDATE_NOT_EXECUTED_NO_GO"} for item, rule in specs]


def shortcut_rows() -> list[dict[str, object]]:
    items = [
        ("site/acquisition domain", "PASS TSS-derived for TCGA", "FAIL CHIMERA/LEOPARD site absent", "FAIL"),
        ("stain/color statistics", "FAIL absent", "FAIL absent", "FAIL"),
        ("scanner", "PARTIAL 23/437 missing", "FAIL absent", "FAIL"),
        ("MPP/physical FOV", "PASS 12 MPP values and 394.24um FOV", "PASS LEOPARD/CHIMERA", "PASS"),
        ("tissue fraction/area", "PASS thumbnail tissue fraction", "PASS mask tissue fraction", "PASS"),
        ("tumor purity/amount", "FAIL no independent tumor truth; detector gate failed", "FAIL tissue masks are not tumor masks", "FAIL"),
        ("grade/ISUP", "PASS ISUP", "PARTIAL CHIMERA yes; LEOPARD no", "FAIL"),
        ("specimen type", "FAIL not encoded per analysis row", "PARTIAL CHIMERA prostatectomy; LEOPARD absent", "FAIL"),
        ("blur", "FAIL absent", "FAIL absent", "FAIL"),
        ("fold artifact", "FAIL absent", "FAIL absent", "FAIL"),
        ("compression", "PASS TCGA slide summary", "FAIL absent", "FAIL"),
        ("QC failure", "PARTIAL header/thumbnail only", "PARTIAL sampling integrity only", "FAIL"),
        ("age", "PARTIAL 4/392 missing values across encoder rows; cross-project source provenance", "PASS CHIMERA; LEOPARD absent", "FAIL"),
        ("treatment", "PARTIAL documentation flags only", "FAIL CHIMERA 93/95 blank; LEOPARD absent", "FAIL"),
        ("stage/molecular", "PARTIAL path-T; molecular not in residual panel", "PARTIAL CHIMERA pT; molecular absent", "FAIL"),
    ]
    return [{"shortcut_variable": a, "source_TCGA": b, "external": c, "cross_cohort_audit_status": d, "candidate_promotion": "prohibited unless PASS"} for a, b, c, d in items]


def external_rows() -> list[dict[str, object]]:
    return [
        {"cohort": "TCGA 7-site heldout", "independence": "internal only", "encoder_scope": "CONCH", "same_panel": "yes ISUP", "paired_embedding": "PASS", "endpoint": "BCR days 289/69", "metadata": "partial", "recurrence_feasibility": "SUPPORTING_NOT_EXTERNAL", "limitation": "same TCGA source; CONCH site gate failed"},
        {"cohort": "TCGA 7-site heldout", "independence": "internal only", "encoder_scope": "Virchow", "same_panel": "yes ISUP", "paired_embedding": "PASS", "endpoint": "BCR days 289/69", "metadata": "partial", "recurrence_feasibility": "SUPPORTING_NOT_EXTERNAL", "limitation": "same TCGA source; Virchow-only site pass"},
        {"cohort": "LEOPARD", "independence": "independent external", "encoder_scope": "CONCH", "same_panel": "FAIL ISUP/C absent", "paired_embedding": "PASS 32512x512", "endpoint": "BCR years 508/87", "metadata": "FAIL", "recurrence_feasibility": "NOT-EVALUABLE", "limitation": "cannot apply same M,C,Q residual definition"},
        {"cohort": "LEOPARD", "independence": "independent external", "encoder_scope": "Virchow", "same_panel": "FAIL ISUP/C absent", "paired_embedding": "PASS 32512x2560", "endpoint": "BCR years 508/87", "metadata": "FAIL", "recurrence_feasibility": "NOT-EVALUABLE", "limitation": "cannot apply same M,C,Q residual definition"},
        {"cohort": "CHIMERA", "independence": "independent external", "encoder_scope": "CONCH", "same_panel": "PARTIAL ISUP+age+pT+tissue+MPP; treatment incomplete", "paired_embedding": "PASS 12160x512", "endpoint": "PSA>=0.1 BCR months 95/27", "metadata": "partial", "recurrence_feasibility": "PASS_NUMERIC_ONLY", "limitation": "CONCH functional gate failed; shortcut/review gates remain"},
        {"cohort": "CHIMERA", "independence": "independent external", "encoder_scope": "Virchow", "same_panel": "PARTIAL ISUP+age+pT+tissue+MPP; treatment incomplete", "paired_embedding": "PASS 12160x2560", "endpoint": "PSA>=0.1 BCR months 95/27", "metadata": "partial", "recurrence_feasibility": "PASS_NUMERIC_ONLY", "limitation": "Virchow-only prior T cannot establish common residual"},
    ]


def review_rows() -> list[dict[str, object]]:
    items = [
        ("hide encoder/residual/outcome/site", "specifiable", "PASS"),
        ("random candidate/control order", "seed 260825 deterministic permutation", "PASS"),
        ("morphology/artifact/adequacy/known concept/uncertainty fields", "schema can preserve all", "PASS"),
        ("not-evaluable preservation", "separate value; never negative/normal", "PASS"),
        ("patient/slide leakage prevention", "cluster items and reviewer split by patient", "PASS"),
        ("internal WSI provenance", "coordinate/crop hash key hidden from reviewer", "PASS"),
        ("inter/intraobserver and adjudication", "design possible; reviewer count/repeat fraction/adjudicator not approved", "NOT-EVALUABLE"),
        ("pathologist approval and burden", "no approval, item count, minutes/item, or burden record", "NOT-EVALUABLE"),
        ("patient-level data use", "TCGA terms not assembled in review record; CHIMERA written organizer clearance absent", "NOT-EVALUABLE"),
        ("PHI/access control", "local-only rule exists; reviewer role/access log not registered", "NOT-EVALUABLE"),
    ]
    return [{"review_requirement": a, "evidence_or_design": b, "status": c, "package_execution": "prohibited until all PASS"} for a, b, c in items]


def gate_rows() -> list[dict[str, object]]:
    return [
        {"gate_id": "G1", "required": "yes", "gate": "separate leakage-free Rrepr/Rscore computability", "status": "PASS", "evidence": "TCGA 392 patients, 27968 paired tiles, five folds, OOF scores; protocol sections 3.1-3.2", "resolution_needed": "none for computability; stability still separate"},
        {"gate_id": "G2", "required": "yes", "gate": "source threshold and sampling lock", "status": "PASS", "evidence": "protocol section 4 q10/q90, percentile-gap, caps, quotas, seed", "resolution_needed": "review N burden approval before activation"},
        {"gate_id": "G3", "required": "yes", "gate": "paired encoder comparison", "status": "PASS", "evidence": "FM2 1218 and FM6 TCGA/LEOPARD/CHIMERA paired row/crop audits all PASS", "resolution_needed": "no component-index comparison"},
        {"gate_id": "G4", "required": "yes", "gate": "shortcut metadata sufficiency", "status": "FAIL", "evidence": "stain/color, blur/fold, tumor purity, specimen and external scanner/site gaps; shortcut matrix", "resolution_needed": "hash-locked source+external metadata/measurements"},
        {"gate_id": "G5", "required": "yes", "gate": "independent source-locked recurrence feasibility", "status": "PASS", "evidence": "CHIMERA paired embeddings+ISUP/age/pT/tissue/MPP for 95 patients; numeric recurrence only", "resolution_needed": "shortcut metadata before morphology promotion; LEOPARD remains not evaluable"},
        {"gate_id": "G6", "required": "yes", "gate": "lawful reproducible blinded package", "status": "NOT-EVALUABLE", "evidence": "interface contract possible; no pathologist burden/approval, access role, or CHIMERA written review clearance", "resolution_needed": "approvals, DUA/IRB/access record, burden/adjudication plan"},
        {"gate_id": "G7", "required": "yes", "gate": "scope-correct limited interpretation", "status": "PASS", "evidence": "protocol restricts to residual after available prespecified metric panel and whole tissue", "resolution_needed": "do not use all-known-pathology, tumor-specific, or biomarker language"},
        {"gate_id": "R1", "required": "readiness", "gate": "residual fold/seed/rank stability", "status": "NOT-EVALUABLE", "evidence": "no Rrepr/Rscore manifest or stability artifact exists", "resolution_needed": "pre-review source-only stability audit after metadata repair"},
        {"gate_id": "R2", "required": "readiness", "gate": "cross-project covariate provenance", "status": "FAIL", "evidence": "FM6 age/path-T source points to PBV model_workspace generated state", "resolution_needed": "QFM-owned source or shared immutable hash-locked manifest"},
    ]


def blocker_rows() -> list[dict[str, object]]:
    return [
        {"priority": 1, "blocker_id": "B01", "blocker": "shortcut metadata incomplete", "required_evidence": "source and external stain/color, scanner, blur/fold/compression, specimen, tissue/tumor amount and QC at slide/tile level", "acceptance": "predefined completeness and cross-cohort semantic map; no silent imputation", "next_action": "acquire/derive without residual/outcome access and hash-lock"},
        {"priority": 2, "blocker_id": "B02", "blocker": "tumor amount/purity not independently evaluable", "required_evidence": "validated multi-domain detector or independent tumor annotations", "acceptance": "prespecified domain gate passed", "next_action": "do not reuse failed detector or claim tumor-specific residual"},
        {"priority": 3, "blocker_id": "B03", "blocker": "residual stability unknown", "required_evidence": "source-only Rrepr/Rscore fold, seed, rank, model-family and sampling stability tables", "acceptance": "protocol-defined stability threshold before review", "next_action": "run only after B01/B06 are resolved"},
        {"priority": 4, "blocker_id": "B04", "blocker": "blinded review authorization incomplete", "required_evidence": "pathologist approval, item/time burden, repeat fraction, adjudicator, IRB/DUA/access role and CHIMERA patient-level review permission", "acceptance": "all review feasibility rows PASS", "next_action": "obtain written governance records; do not export images"},
        {"priority": 5, "blocker_id": "B05", "blocker": "LEOPARD lacks same metric/covariate panel", "required_evidence": "patient-linked ISUP/Gleason, treatment, age/stage and technical metadata", "acceptance": "same source-locked M,C,Q semantics", "next_action": "obtain metadata or exclude LEOPARD from residual recurrence"},
        {"priority": 6, "blocker_id": "B06", "blocker": "age/path-T provenance crosses PBV generated workspace", "required_evidence": "QFM-owned source snapshot or registered shared immutable manifest with hash and allowed use", "acceptance": "no implicit cross-project generated dependency", "next_action": "promote source lawfully without copying generated PBV output"},
        {"priority": 7, "blocker_id": "B07", "blocker": "known metric panel is limited", "required_evidence": "repeatable independent gland/nuclear/microenvironment metrics if broader residual is intended", "acceptance": "metric registry and measurement gates passed", "next_action": "otherwise retain available-panel wording"},
        {"priority": 8, "blocker_id": "B08", "blocker": "TCGA-CHIMERA endpoint equivalence unresolved", "required_evidence": "censoring/PSA threshold/clinical process harmonization", "acceptance": "prespecified equivalence or explicit non-equivalence sensitivity plan", "next_action": "do not pool patients or retune target threshold"},
    ]


def report_text(table_counts: dict[str, int], clean_status: str) -> str:
    return f"""---
document_id: fm8-residual-discovery-entry-audit-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: complete
created: 2026-08-25
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm8_residual_discovery_entry_audit/outputs/fm8-residual-discovery-entry-audit-report.md
---

# FM8 residual-discovery entry audit report

## Final decision: NO-GO

FM8 본 residual-discovery 연구와 blinded pathology review를 시작할 자격이 없다. 필수
G4 shortcut-metadata gate가 FAIL이고, G6 blinded-review legality/reproducibility와 residual
stability가 NOT-EVALUABLE이다. 이 판정은 논문 1을 재개하지 않으며 기존 FM6 결과나
Virchow--CHIMERA encoder-specific whole-tissue T를 변경하지 않는다.

## Evidence inventory

`fm8_artifact_availability_matrix.csv` {table_counts['availability']}행과
`fm8_source_evidence_manifest.csv` {table_counts['evidence']}행을 생성했다. 확인된 핵심 수치는
다음과 같다.

- PRECISE FM2--FM5: 25명, 27 sessions, 1,218 paired tiles. 두 encoder의 crop hash,
  embedding row와 5개 환자 fold는 일치하지만 scanner/stain과 disease outcome/head가 없다.
- TCGA source: 392명/80 events, 437 WSI, 27,968 paired 394.24 µm tiles. OOF score는 encoder별
  392행이고 paired patient table은 784행이다. Age는 encoder-row 기준 8/784, path-T는
  18/784 결측이다. Scanner ID는 23/437 slides에서 missing이다.
- TCGA site-heldout: 7개 eligible TSS site, 289명/69 events. 이는 독립 external cohort가
  아니라 내부 site transport다.
- LEOPARD: 508명/87 events, 32,512 paired tiles. 두 encoder embedding과 outcome은 있으나
  ISUP/Gleason, treatment와 임상/기술 panel이 없어 동일 residual recurrence는 NOT-EVALUABLE이다.
- CHIMERA: 95명/27 events, 190 WSI, 12,160 paired tiles. ISUP/Gleason은 3/95 source
  discrepancy이고 earlier therapy는 93/95가 blank다. MPP와 tissue mask fraction은 있으나
  site/stain/scanner/color/blur/fold/compression은 없다.

모든 위 CSV의 row count, unique patient 수, key duplicate, fold independence, missing cell과
SHA-256은 `fm8_source_integrity_audit.csv` {table_counts['source_integrity']}행에 연결했다.

## Estimands and source lock

Rscore은 환자 단위 `S_k-g_k(M,C,Q)`, Rrepr은 paired tile 단위 `(I-P_M,k)Z_k`로 분리했다.
모든 normalization, imputation, regularization, rank와 projection은 source outer-training
fold 안에서만 적합하고 환자는 OOF residual을 한 번만 받는다. Rrepr ranking scalar는
head-projected `Trepr_k`로 별도 고정했다. 두 encoder embedding component를 직접 대응시키지
않는다.

Threshold는 source OOF q10/q90, discordance는 encoder percentile gap 0.50, seed는 {SEED},
sampling cap은 환자당 8/slide당 2/환자당 4 slides다. Target cohort에서는 refit,
recalibration, threshold/quota/rank 변경을 금지한다. 이 규칙은 NO-GO 해소 전 실행되지 않는다.

Known panel은 ISUP 중심이며 알려진 병리를 모두 제거하지 않는다. 허용 해석은
`residual after the available prespecified metric panel`뿐이다. Whole-tissue residual을
tumor-specific residual이나 biomarker로 부르지 않는다.

## Gate decisions

| Gate | Decision | Evidence-linked reason |
|---|---|---|
| G1 separate leakage-free Rrepr/Rscore | PASS | TCGA paired embeddings, OOF score, five patient folds and locked protocol |
| G2 source threshold/sampling lock | PASS | q10/q90, percentile gap, caps, quotas and seed fixed before residual execution |
| G3 paired encoder comparison | PASS | PRECISE, TCGA, LEOPARD and CHIMERA paired audits |
| G4 shortcut metadata sufficient | **FAIL** | stain/color, blur/fold, tumor amount/purity, specimen and external site/scanner gaps |
| G5 independent recurrence feasible | PASS, numeric only | CHIMERA supports same-panel numeric application; morphology promotion remains blocked |
| G6 lawful reproducible blinded package | **NOT-EVALUABLE** | no pathologist burden/approval, reviewer access record or written CHIMERA review clearance |
| G7 limited-panel interpretation | PASS | explicit available-panel and whole-tissue ceiling |
| R1 residual stability | **NOT-EVALUABLE** | no residual manifest or fold/seed/rank stability result |
| R2 cross-project source provenance | **FAIL** | age/path-T source points to PBV generated model workspace |

`fm8_gate_decision_matrix.csv` {table_counts['gates']}행이 machine-readable authority다. 필수
gate 하나라도 FAIL이면 NO-GO이므로 G4만으로도 전체 NO-GO다. NOT-EVALUABLE은 GO로
간주하지 않는다.

## Shortcut and external recurrence

Shortcut matrix {table_counts['shortcut']}행 중 cross-cohort PASS는 MPP/FOV와 tissue
fraction/area뿐이다. Tissue mask는 tumor mask가 아니며 실패한 independent detector gate를
대체하지 않는다. Shortcut과 morphology를 구분할 수 없는 item은 review candidate로
승격할 수 없다.

CHIMERA raw paired artifact는 두 encoder의 numeric recurrence 적용을 허용하지만 prior
Virchow-only functional T는 common residual gate가 아니다. LEOPARD는 동일 M,C,Q가 없어
source-locked residual recurrence가 NOT-EVALUABLE이다. Endpoint threshold와 censoring
equivalence가 없으므로 TCGA와 CHIMERA patient-level pooling은 금지한다.

## Blinded review feasibility

Encoder/residual/outcome/site masking, seeded random order, matched controls, not-evaluable
preservation, patient-clustered reviewer split, hidden WSI provenance와 repeat/adjudication
schema는 설계 가능하다. 그러나 pathologist 승인, review sample size와 minutes/item,
repeat fraction, adjudicator, IRB/DUA/access role 및 CHIMERA patient-level image review 권한이
없다. 이 증거가 문서화되기 전 package 생성·export와 실제 판독을 시작하지 않는다.

## Required next work

`fm8_blocker_action_list.csv` {table_counts['blockers']}행의 우선순서를 따른다. 먼저 shortcut
metadata와 QFM/shared covariate provenance를 hash-lock한다. 그 다음에만 source-only
residual stability를 감사하고, 마지막으로 review governance와 burden을 승인한다. 모든
필수 gate가 PASS가 된 새 entry audit 없이는 FM8 본 연구 또는 두 번째 논문 workstream을
개시하지 않는다.

## Reproducibility

이 audit은 기존 artifacts를 읽기만 했고 residual, target outcome tuning 또는 GPU 분석을
수행하지 않았다. Nonvolatile clean-rerun status는 `{clean_status}`다. 실행 seed, Python
version, input/output SHA-256와 volatile execution-time 제외 규칙은
`fm8_entry_audit_run_config.json`에 저장한다.
"""


def output_integrity_rows(output: Path, files: Iterable[Path]) -> list[dict[str, object]]:
    result = []
    for path in files:
        if path.suffix == ".csv":
            rows = read_csv(path)
            columns = list(rows[0]) if rows else []
            missing_cells = sum(missing(row[column]) for row in rows for column in columns)
            count_type = "data_rows"
            count = len(rows)
        else:
            columns = []
            missing_cells = 0
            count_type = "text_lines"
            count = len(path.read_text(encoding="utf-8").splitlines())
        result.append({
            "path": path.relative_to(output).as_posix(),
            "count_type": count_type,
            "count": count,
            "columns": len(columns),
            "missing_cells": missing_cells,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "status": "PASS",
        })
    return result


def clean_comparison_rows(output: Path, reference: Path | None, files: Sequence[str]) -> list[dict[str, object]]:
    rows = []
    for name in files:
        current = output / name
        current_hash = sha256(current)
        reference_hash = ""
        status = "NOT_RUN_REFERENCE_NOT_SUPPLIED"
        if reference is not None:
            candidate = reference / name
            if candidate.is_file():
                reference_hash = sha256(candidate)
                status = "PASS_EXACT_HASH" if current_hash == reference_hash else "FAIL_HASH_MISMATCH"
            else:
                status = "FAIL_REFERENCE_MISSING"
        rows.append({"output": name, "current_sha256": current_hash, "reference_sha256": reference_hash, "status": status})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reference-dir", type=Path)
    args = parser.parse_args()
    start = time.monotonic()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    evidence = evidence_manifest()
    source_integrity = source_integrity_rows()
    availability = availability_rows()
    estimands = estimand_rows()
    source_lock = source_lock_rows()
    shortcut = shortcut_rows()
    external = external_rows()
    review = review_rows()
    gates = gate_rows()
    blockers = blocker_rows()

    tables = {
        "fm8_source_evidence_manifest.csv": evidence,
        "fm8_source_integrity_audit.csv": source_integrity,
        "fm8_artifact_availability_matrix.csv": availability,
        "fm8_estimand_leakage_control_specification.csv": estimands,
        "fm8_source_lock_specification.csv": source_lock,
        "fm8_shortcut_audit_matrix.csv": shortcut,
        "fm8_external_recurrence_feasibility_matrix.csv": external,
        "fm8_blinded_review_feasibility_specification.csv": review,
        "fm8_gate_decision_matrix.csv": gates,
        "fm8_blocker_action_list.csv": blockers,
    }
    for name, rows in tables.items():
        write_csv(output / name, rows)

    base_files = list(tables)
    clean_status = "PASS_EXACT_HASH" if args.reference_dir is not None else "NOT_RUN_REFERENCE_NOT_SUPPLIED"
    counts = {
        "availability": len(availability),
        "evidence": len(evidence),
        "source_integrity": len(source_integrity),
        "shortcut": len(shortcut),
        "gates": len(gates),
        "blockers": len(blockers),
    }
    report = output / "fm8-residual-discovery-entry-audit-report.md"
    report.write_text(report_text(counts, clean_status), encoding="utf-8")
    base_files.append(report.name)

    comparison = clean_comparison_rows(output, args.reference_dir.resolve() if args.reference_dir else None, base_files)
    write_csv(output / "fm8_clean_rerun_comparison.csv", comparison)
    integrity_targets = [output / name for name in base_files] + [output / "fm8_clean_rerun_comparison.csv"]
    integrity = output_integrity_rows(output, integrity_targets)
    write_csv(output / "fm8_output_integrity.csv", integrity)

    nonvolatile = base_files + ["fm8_clean_rerun_comparison.csv", "fm8_output_integrity.csv"]
    run_config = {
        "protocol_id": PROTOCOL_ID,
        "decision": "NO-GO",
        "seed": SEED,
        "python_version": platform.python_version(),
        "script_path": relative(Path(__file__)),
        "script_sha256": sha256(Path(__file__)),
        "input_sha256": {row["source_id"]: row["sha256"] for row in evidence},
        "output_sha256": {name: sha256(output / name) for name in nonvolatile},
        "source_integrity_all_pass": all(row["status"] == "PASS" for row in source_integrity),
        "clean_rerun_status": clean_status,
        "volatile_fields": ["execution_time_seconds"],
        "execution_time_seconds": round(time.monotonic() - start, 6),
        "claim_ceiling": "entry audit only; no residual biomarker, tumor-specific mechanism, or paper-1 reopening",
    }
    (output / "fm8_entry_audit_run_config.json").write_text(
        json.dumps(run_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if any(row["status"] == "FAIL" for row in gates if row["required"] == "yes"):
        print("FM8 entry audit: NO-GO")
    else:
        raise RuntimeError("gate logic unexpectedly lacks a required FAIL")


if __name__ == "__main__":
    main()
