"""Build the approved R3 official TCGA-CDR PFI evidence artifacts.

This audit applies the already-frozen marker-7 patient risk to the official
Liu et al. TCGA-CDR PFI event/time fields.  Comparator endpoints remain
separate rows with explicit endpoint identifiers; missing outcomes are never
treated as censoring or as negative events.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import scipy
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]

MAPPING_NAME = "tcga_cdr_pfi_mapping.csv"
CONCORDANCE_NAME = "pfi_endpoint_concordance.csv"
PERFORMANCE_NAME = "pfi_performance_summary.csv"
PREDICTIONS_NAME = "tcga_cdr_pfi_patient_predictions.csv"
CONFIG_NAME = "tcga_cdr_pfi_run_config.json"
MANIFEST_NAME = "tcga_cdr_pfi_run_manifest.csv"
DETERMINISTIC_OUTPUT_NAMES = (
    MAPPING_NAME,
    CONCORDANCE_NAME,
    PERFORMANCE_NAME,
    PREDICTIONS_NAME,
    CONFIG_NAME,
)
PUBLICATION_ORDER = DETERMINISTIC_OUTPUT_NAMES + (MANIFEST_NAME,)
ALL_OUTPUT_NAMES = PUBLICATION_ORDER

OFFICIAL_ENDPOINT_ID = "official_tcga_cdr_pfi"
RECONSTRUCTED_ENDPOINT_ID = "reconstructed_gdc_disease_response"
PFS_ENDPOINT_ID = "cbioportal_tcga_cdr_pfs"
DFS_ENDPOINT_ID = "cbioportal_tcga_cdr_dfs"
RECURRENCE_ONLY_ENDPOINT_ID = "gdc_recurrence_only_after_tumor_free"
ENDPOINT_ORDER = (
    OFFICIAL_ENDPOINT_ID,
    RECONSTRUCTED_ENDPOINT_ID,
    PFS_ENDPOINT_ID,
    DFS_ENDPOINT_ID,
    RECURRENCE_ONLY_ENDPOINT_ID,
)

ENDPOINT_LABELS = {
    OFFICIAL_ENDPOINT_ID: "Official TCGA-CDR PFI",
    RECONSTRUCTED_ENDPOINT_ID: "Reconstructed GDC disease-response endpoint",
    PFS_ENDPOINT_ID: "cBioPortal TCGA-CDR PFS",
    DFS_ENDPOINT_ID: "cBioPortal TCGA-CDR DFS",
    RECURRENCE_ONLY_ENDPOINT_ID: "GDC recurrence-only after tumor-free",
}
ENDPOINT_SOURCES = {
    OFFICIAL_ENDPOINT_ID: "TCGA-CDR Supplemental Table S1, TCGA-CDR sheet, PFI/PFI.time",
    RECONSTRUCTED_ENDPOINT_ID: "confounder_nested_predictions.csv grade_only event/follow_up_y",
    PFS_ENDPOINT_ID: "prad_pancan_clinical.json PFS_STATUS/PFS_MONTHS",
    DFS_ENDPOINT_ID: "prad_pancan_clinical.json DFS_STATUS/DFS_MONTHS",
    RECURRENCE_ONLY_ENDPOINT_ID: "bcr_recurrence_only.csv event/follow_up_y",
}

EXPECTED_OFFICIAL_SHA256 = "ea594c0fbb6731477c7ac511fab449ca9c38b0d42d269591ed9f5c4090e75a5a"
EXPECTED_MANIFEST_SHA256 = "84cf76cf2a813bc8bff10abec2d2e295f74c9cd7d9458556514432b8bab54ac0"
EXPECTED_RISK_SHA256 = "3d5015a05d6f0564c1f03a22529234157523f7d487e0e45e166dccf83eab29ca"
EXPECTED_OFFICIAL_MD5 = "a4591b2dcee39591f59e5e25a6ce75fa"
EXPECTED_OFFICIAL_SIZE = 2945129
EXPECTED_FILE_UUID = "1b5f413e-a8d1-4d10-92eb-7c4ae739ed81"
EXPECTED_DOWNLOAD_URL = f"https://api.gdc.cancer.gov/data/{EXPECTED_FILE_UUID}"
EXPECTED_OFFICIAL_FILENAME = "TCGA-CDR-SupplementalTableS1.xlsx"
EXPECTED_PUBLISHER = "National Cancer Institute Genomic Data Commons"
OFFICIAL_SHEET = "TCGA-CDR"
EXPECTED_RISK_N = 270
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 20260806
BARCODE_RE = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}$")


class EvidenceError(RuntimeError):
    """Raised when an immutable input or R3 reconciliation invariant fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 - verifies the official GDC manifest, not security.
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.17g", na_rep="")


def _write_json(value: dict, path: Path) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _normalize_barcode(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def _require_columns(frame: pd.DataFrame, columns: set[str], role: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise EvidenceError(f"{role} missing columns: {missing}")


def select_frozen_risk(frame: pd.DataFrame, *, expected_n: int = EXPECTED_RISK_N) -> pd.DataFrame:
    """Select the frozen patient risk and verify duplicated fully-adjusted risk values."""
    required = {
        "case_id", "marker", "analysis", "scope", "marker7_risk", "event", "follow_up_y"
    }
    _require_columns(frame, required, "frozen risk source")
    source = frame.copy()
    source["risk_source_row_number"] = np.arange(len(source), dtype=int) + 2
    marker = source.loc[
        source.marker.eq("marker7_recurrence") & source.scope.eq("patient")
    ].copy()
    grade = marker.loc[marker.analysis.eq("grade_only")].copy()
    grade["case_id"] = grade.case_id.map(_normalize_barcode)
    if grade.case_id.eq("").any() or not grade.case_id.map(lambda value: bool(BARCODE_RE.fullmatch(value))).all():
        raise EvidenceError("invalid grade_only TCGA patient barcode")
    if grade.case_id.duplicated().any():
        raise EvidenceError("grade_only frozen risk case_id values must be unique")
    if len(grade) != expected_n:
        raise EvidenceError(f"grade_only frozen risk must contain exactly {expected_n} rows")

    for column in ("marker7_risk", "event", "follow_up_y"):
        grade[column] = pd.to_numeric(grade[column], errors="coerce")
    if not np.isfinite(grade.marker7_risk).all():
        raise EvidenceError("grade_only marker7_risk must be finite")
    if grade.event.isna().any() or not grade.event.isin([0.0, 1.0]).all():
        raise EvidenceError("reconstructed event must be fully observed and binary")
    if grade.follow_up_y.isna().any() or not np.isfinite(grade.follow_up_y).all() or (grade.follow_up_y <= 0).any():
        raise EvidenceError("reconstructed follow_up_y must be finite and positive")

    adjusted = marker.loc[marker.analysis.eq("fully_adjusted")].copy()
    adjusted["case_id"] = adjusted.case_id.map(_normalize_barcode)
    if adjusted.case_id.duplicated().any():
        raise EvidenceError("fully_adjusted marker-7 patient IDs must be unique")
    if not set(adjusted.case_id).issubset(set(grade.case_id)):
        raise EvidenceError("fully_adjusted marker-7 patients are not a subset of grade_only")
    adjusted["marker7_risk"] = pd.to_numeric(adjusted.marker7_risk, errors="coerce")
    if not np.isfinite(adjusted.marker7_risk).all():
        raise EvidenceError("fully_adjusted marker7_risk must be finite")
    grade_risk = grade.set_index("case_id").marker7_risk
    adjusted_risk = adjusted.set_index("case_id").marker7_risk
    if len(adjusted_risk) and not np.array_equal(
        grade_risk.loc[adjusted_risk.index].to_numpy(), adjusted_risk.to_numpy()
    ):
        raise EvidenceError("fully_adjusted duplicate marker7_risk disagrees with grade_only")

    return grade.sort_values("case_id", kind="stable").reset_index(drop=True)


def _numeric_endpoint(event_raw, time_raw, *, prefix: str) -> tuple[float, float, list[str]]:
    reasons: list[str] = []
    event = np.nan
    time_value = np.nan
    if pd.isna(event_raw) or str(event_raw).strip() == "":
        reasons.append(f"missing_{prefix}_event")
    else:
        try:
            candidate = float(event_raw)
        except (TypeError, ValueError):
            candidate = np.nan
        if not np.isfinite(candidate) or candidate not in (0.0, 1.0):
            reasons.append(f"nonbinary_{prefix}_event")
        else:
            event = candidate
    if pd.isna(time_raw) or str(time_raw).strip() == "":
        reasons.append(f"missing_{prefix}_time")
    else:
        try:
            candidate_time = float(time_raw)
        except (TypeError, ValueError):
            candidate_time = np.nan
        if not np.isfinite(candidate_time):
            reasons.append(f"nonfinite_{prefix}_time")
        elif candidate_time <= 0:
            reasons.append(f"nonpositive_{prefix}_time")
        else:
            time_value = candidate_time
    if reasons:
        event = np.nan
        time_value = np.nan
    return event, time_value, reasons


def build_official_mapping(risk: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Map every frozen patient to official PFI while retaining explicit invalid reasons."""
    _require_columns(risk, {"case_id", "marker7_risk"}, "risk frame")
    _require_columns(
        official, {"bcr_patient_barcode", "type", "PFI", "PFI.time"}, "official Table S1"
    )
    source = official.loc[official.type.astype(str).str.strip().eq("PRAD")].copy()
    if "_source_row_number" not in source:
        source["_source_row_number"] = source.index.to_numpy(dtype=int) + 2
    source["_normalized_barcode"] = source.bcr_patient_barcode.map(_normalize_barcode)
    grouped = {barcode: group for barcode, group in source.groupby("_normalized_barcode", sort=False)}
    rows = []
    for record in risk.itertuples(index=False):
        case_id = _normalize_barcode(record.case_id)
        matches = grouped.get(case_id)
        base = {
            "case_id": case_id,
            "risk_source_row_number": getattr(record, "risk_source_row_number", np.nan),
            "marker7_risk": float(record.marker7_risk),
            "normalized_barcode": case_id,
            "official_source_sheet": OFFICIAL_SHEET,
            "n_official_matches": 0 if matches is None else len(matches),
            "official_source_row_number": "",
            "official_barcode_raw": "",
            "official_cancer_type": "",
            "official_pfi_event_raw": np.nan,
            "official_pfi_time_days_raw": np.nan,
            "official_pfi_event": np.nan,
            "official_pfi_time_days": np.nan,
            "official_pfi_time_years": np.nan,
            "mapping_status": "unmapped",
            "endpoint_status": "not_evaluable",
            "exclusion_reason": "official_barcode_not_found",
        }
        if matches is None or matches.empty:
            rows.append(base)
            continue
        if len(matches) != 1:
            base.update({
                "official_source_row_number": "|".join(map(str, matches._source_row_number)),
                "official_barcode_raw": "|".join(matches.bcr_patient_barcode.astype(str)),
                "official_cancer_type": "|".join(matches.type.astype(str)),
                "official_pfi_event_raw": "|".join(matches.PFI.astype(str)),
                "official_pfi_time_days_raw": "|".join(matches["PFI.time"].astype(str)),
                "mapping_status": "ambiguous",
                "exclusion_reason": "duplicate_official_barcode",
            })
            rows.append(base)
            continue
        match = matches.iloc[0]
        event, time_days, reasons = _numeric_endpoint(
            match.PFI, match["PFI.time"], prefix="official_pfi"
        )
        base.update({
            "official_source_row_number": str(int(match._source_row_number)),
            "official_barcode_raw": str(match.bcr_patient_barcode),
            "official_cancer_type": str(match.type),
            "official_pfi_event_raw": match.PFI,
            "official_pfi_time_days_raw": match["PFI.time"],
            "mapping_status": "one_to_one",
            "exclusion_reason": ";".join(reasons),
        })
        if not reasons:
            base.update({
                "official_pfi_event": event,
                "official_pfi_time_days": time_days,
                "official_pfi_time_years": time_days / 365.25,
                "endpoint_status": "evaluable",
            })
        rows.append(base)
    return pd.DataFrame(rows)


def validate_canonical_mapping(mapping: pd.DataFrame) -> None:
    """Require an unambiguous official row for every canonical risk patient."""
    _require_columns(
        mapping, {"case_id", "mapping_status", "endpoint_status", "exclusion_reason"},
        "official PFI mapping",
    )
    invalid = mapping.loc[~mapping.mapping_status.eq("one_to_one")]
    if not invalid.empty:
        counts = invalid.mapping_status.value_counts(dropna=False).to_dict()
        raise EvidenceError(
            f"canonical official PFI mapping is not one-to-one for {len(invalid)} patients: {counts}"
        )


def _official_source(root: Path) -> tuple[pd.DataFrame, dict]:
    directory = root / "local-data/TCGA-CDR"
    xlsx = directory / EXPECTED_OFFICIAL_FILENAME
    manifest_path = directory / "PanCan-Clinical_Open_GDC-Manifest_1.txt"
    provenance_path = directory / "source_provenance.json"
    for path in (xlsx, manifest_path, provenance_path):
        if not path.is_file():
            raise EvidenceError(f"missing official source artifact: {path}")
    if sha256_file(xlsx) != EXPECTED_OFFICIAL_SHA256:
        raise EvidenceError("official TCGA-CDR workbook SHA256 mismatch")
    if sha256_file(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise EvidenceError("official GDC manifest SHA256 mismatch")
    if xlsx.stat().st_size != EXPECTED_OFFICIAL_SIZE or md5_file(xlsx) != EXPECTED_OFFICIAL_MD5:
        raise EvidenceError("official TCGA-CDR workbook GDC size/MD5 mismatch")

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    expected_provenance = {
        "archived_filename": EXPECTED_OFFICIAL_FILENAME,
        "download_url": EXPECTED_DOWNLOAD_URL,
        "file_uuid": EXPECTED_FILE_UUID,
        "gdc_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "publisher": EXPECTED_PUBLISHER,
        "sha256": EXPECTED_OFFICIAL_SHA256,
        "size_bytes": EXPECTED_OFFICIAL_SIZE,
        "supplement_sheet": OFFICIAL_SHEET,
    }
    for key, expected in expected_provenance.items():
        if provenance.get(key) != expected:
            raise EvidenceError(f"official source provenance mismatch: {key}")
    manifest = pd.read_csv(manifest_path, sep="\t", dtype=str)
    if len(manifest) != 1:
        raise EvidenceError("official GDC manifest must contain exactly one artifact")
    row = manifest.iloc[0]
    if (
        row.get("id") != EXPECTED_FILE_UUID
        or row.get("filename") != EXPECTED_OFFICIAL_FILENAME
        or row.get("md5") != EXPECTED_OFFICIAL_MD5
        or int(row.get("size", -1)) != EXPECTED_OFFICIAL_SIZE
    ):
        raise EvidenceError("official GDC manifest fields do not reconcile")

    official = pd.read_excel(xlsx, sheet_name=OFFICIAL_SHEET)
    _require_columns(
        official, {"bcr_patient_barcode", "type", "PFI", "PFI.time"}, "official Table S1"
    )
    official["_source_row_number"] = np.arange(len(official), dtype=int) + 2
    metadata = {
        "archived_filename": EXPECTED_OFFICIAL_FILENAME,
        "download_url": EXPECTED_DOWNLOAD_URL,
        "file_uuid": EXPECTED_FILE_UUID,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "publisher": EXPECTED_PUBLISHER,
        "sha256": EXPECTED_OFFICIAL_SHA256,
        "size_bytes": EXPECTED_OFFICIAL_SIZE,
        "supplement_sheet": OFFICIAL_SHEET,
    }
    return official, metadata


def _base_prediction(
    case_id: str, endpoint_id: str, risk: float, *, event=np.nan, time_value=np.nan,
    time_unit: str, time_years=np.nan, mapping_status: str = "one_to_one",
    endpoint_status: str = "evaluable", exclusion_reason: str = "",
) -> dict:
    return {
        "case_id": case_id,
        "endpoint_id": endpoint_id,
        "endpoint_label": ENDPOINT_LABELS[endpoint_id],
        "endpoint_source": ENDPOINT_SOURCES[endpoint_id],
        "marker7_risk": float(risk),
        "event": event,
        "time_value_source": time_value,
        "time_unit_source": time_unit,
        "time_years": time_years,
        "mapping_status": mapping_status,
        "endpoint_status": endpoint_status,
        "exclusion_reason": exclusion_reason,
    }


def _official_predictions(risk: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    indexed = mapping.set_index("case_id")
    rows = []
    for record in risk.itertuples(index=False):
        match = indexed.loc[record.case_id]
        rows.append(_base_prediction(
            record.case_id, OFFICIAL_ENDPOINT_ID, record.marker7_risk,
            event=match.official_pfi_event,
            time_value=match.official_pfi_time_days,
            time_unit="days",
            time_years=match.official_pfi_time_years,
            mapping_status=match.mapping_status,
            endpoint_status=match.endpoint_status,
            exclusion_reason=match.exclusion_reason if isinstance(match.exclusion_reason, str) else "",
        ))
    return pd.DataFrame(rows)


def _reconstructed_predictions(risk: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([
        _base_prediction(
            row.case_id, RECONSTRUCTED_ENDPOINT_ID, row.marker7_risk,
            event=float(row.event), time_value=float(row.follow_up_y), time_unit="years",
            time_years=float(row.follow_up_y), mapping_status="frozen_risk_row",
        )
        for row in risk.itertuples(index=False)
    ])


def _clinical_json_predictions(root: Path, risk: pd.DataFrame, endpoint_id: str) -> pd.DataFrame:
    prefix = "PFS" if endpoint_id == PFS_ENDPOINT_ID else "DFS"
    data = json.loads(
        (root / "models/tcga_prad_clinical_extra/prad_pancan_clinical.json").read_text(
            encoding="utf-8"
        )
    )
    values: dict[tuple[str, str], list] = {}
    for item in data:
        if not isinstance(item, dict):
            raise EvidenceError("clinical endpoint JSON contains a non-object record")
        attribute = item.get("clinicalAttributeId")
        if attribute in {f"{prefix}_STATUS", f"{prefix}_MONTHS"}:
            patient = _normalize_barcode(item.get("patientId"))
            values.setdefault((attribute, patient), []).append(item.get("value"))
    rows = []
    for record in risk.itertuples(index=False):
        event_values = values.get((f"{prefix}_STATUS", record.case_id), [])
        time_values = values.get((f"{prefix}_MONTHS", record.case_id), [])
        if not event_values or not time_values:
            rows.append(_base_prediction(
                record.case_id, endpoint_id, record.marker7_risk, time_unit="months",
                mapping_status="unmapped", endpoint_status="not_evaluable",
                exclusion_reason="endpoint_not_available_for_patient",
            ))
            continue
        if len(event_values) != 1 or len(time_values) != 1:
            rows.append(_base_prediction(
                record.case_id, endpoint_id, record.marker7_risk, time_unit="months",
                mapping_status="ambiguous", endpoint_status="not_evaluable",
                exclusion_reason="duplicate_endpoint_attribute",
            ))
            continue
        raw_event = str(event_values[0]).split(":", 1)[0].strip()
        event, months, reasons = _numeric_endpoint(raw_event, time_values[0], prefix=prefix.lower())
        if reasons:
            rows.append(_base_prediction(
                record.case_id, endpoint_id, record.marker7_risk, time_unit="months",
                mapping_status="one_to_one", endpoint_status="not_evaluable",
                exclusion_reason=";".join(reasons),
            ))
        else:
            rows.append(_base_prediction(
                record.case_id, endpoint_id, record.marker7_risk, event=event,
                time_value=months, time_unit="months", time_years=months / 12.0,
            ))
    return pd.DataFrame(rows)


def _recurrence_only_predictions(root: Path, risk: pd.DataFrame) -> pd.DataFrame:
    source = pd.read_csv(root / "opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv")
    _require_columns(source, {"case_id", "event", "follow_up_y"}, "recurrence-only source")
    source["_normalized_barcode"] = source.case_id.map(_normalize_barcode)
    grouped = {key: value for key, value in source.groupby("_normalized_barcode", sort=False)}
    rows = []
    for record in risk.itertuples(index=False):
        matches = grouped.get(record.case_id)
        if matches is None or matches.empty:
            rows.append(_base_prediction(
                record.case_id, RECURRENCE_ONLY_ENDPOINT_ID, record.marker7_risk,
                time_unit="years", mapping_status="unmapped", endpoint_status="not_evaluable",
                exclusion_reason="endpoint_not_available_for_patient",
            ))
            continue
        if len(matches) != 1:
            rows.append(_base_prediction(
                record.case_id, RECURRENCE_ONLY_ENDPOINT_ID, record.marker7_risk,
                time_unit="years", mapping_status="ambiguous", endpoint_status="not_evaluable",
                exclusion_reason="duplicate_endpoint_row",
            ))
            continue
        match = matches.iloc[0]
        event, years, reasons = _numeric_endpoint(
            match.event, match.follow_up_y, prefix="recurrence_only"
        )
        if reasons:
            rows.append(_base_prediction(
                record.case_id, RECURRENCE_ONLY_ENDPOINT_ID, record.marker7_risk,
                time_unit="years", endpoint_status="not_evaluable",
                exclusion_reason=";".join(reasons),
            ))
        else:
            rows.append(_base_prediction(
                record.case_id, RECURRENCE_ONLY_ENDPOINT_ID, record.marker7_risk,
                event=event, time_value=years, time_unit="years", time_years=years,
            ))
    return pd.DataFrame(rows)


def build_patient_predictions(root: Path, risk: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    frames = [
        _official_predictions(risk, mapping),
        _reconstructed_predictions(risk),
        _clinical_json_predictions(root, risk, PFS_ENDPOINT_ID),
        _clinical_json_predictions(root, risk, DFS_ENDPOINT_ID),
        _recurrence_only_predictions(root, risk),
    ]
    predictions = pd.concat(frames, ignore_index=True)
    expected = len(risk) * len(ENDPOINT_ORDER)
    if len(predictions) != expected or predictions.duplicated(["endpoint_id", "case_id"]).any():
        raise EvidenceError("patient prediction endpoint/case reconciliation failed")
    return predictions


def _comparable_pairs(event: np.ndarray, event_time: np.ndarray, risk: np.ndarray):
    event = np.asarray(event, dtype=bool)
    event_time = np.asarray(event_time, dtype=float)
    risk = np.asarray(risk, dtype=float)
    if not (event.ndim == event_time.ndim == risk.ndim == 1) or not (
        len(event) == len(event_time) == len(risk)
    ):
        raise EvidenceError("C-index arrays must be aligned one-dimensional vectors")
    if not np.isfinite(event_time).all() or not np.isfinite(risk).all() or (event_time <= 0).any():
        raise EvidenceError("C-index times/risks must be finite and times positive")
    left, right = np.triu_indices(len(event), 1)
    left_earlier = (event_time[left] < event_time[right]) & event[left]
    right_earlier = (event_time[right] < event_time[left]) & event[right]
    left_tied_event = (
        (event_time[left] == event_time[right]) & event[left] & ~event[right]
    )
    right_tied_event = (
        (event_time[left] == event_time[right]) & event[right] & ~event[left]
    )
    comparable = left_earlier | right_earlier | left_tied_event | right_tied_event
    left = left[comparable]
    right = right[comparable]
    event_is_left = (left_earlier | left_tied_event)[comparable]
    event_risk = np.where(event_is_left, risk[left], risk[right])
    other_risk = np.where(event_is_left, risk[right], risk[left])
    difference = event_risk - other_risk
    tied = np.abs(difference) <= 1e-8
    score = np.where(tied, 0.5, (difference > 0).astype(float))
    tied_time = event_time[left] == event_time[right]
    return left, right, score, tied, tied_time


def harrell_c_index(
    event: np.ndarray, event_time: np.ndarray, risk: np.ndarray
) -> tuple[float, int, int, int, int]:
    """Harrell C with the same comparable-pair rules used by scikit-survival."""
    left, _right, score, tied, tied_time = _comparable_pairs(event, event_time, risk)
    if len(left) == 0:
        return np.nan, 0, 0, 0, 0
    concordant = int((score == 1.0).sum())
    discordant = int((score == 0.0).sum())
    tied_risk = int(tied.sum())
    return float(score.mean()), concordant, discordant, tied_risk, int(tied_time.sum())


def bootstrap_c_index(
    event: np.ndarray, event_time: np.ndarray, risk: np.ndarray, *,
    n_boot: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Patient-row bootstrap retaining and counting every undefined replicate."""
    event = np.asarray(event, dtype=bool)
    event_time = np.asarray(event_time, dtype=float)
    risk = np.asarray(risk, dtype=float)
    left, right, score, _tied, _tied_time = _comparable_pairs(event, event_time, risk)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    undefined = 0
    for _ in range(n_boot):
        sampled = rng.integers(0, len(event), len(event))
        counts = np.bincount(sampled, minlength=len(event)).astype(np.int64)
        weights = counts[left] * counts[right]
        denominator = int(weights.sum())
        if denominator == 0:
            undefined += 1
            continue
        values.append(float(np.dot(weights, score) / denominator))
    if values:
        ci_low, ci_high = np.percentile(np.asarray(values), [2.5, 97.5])
        ci_low, ci_high = float(ci_low), float(ci_high)
    else:
        ci_low = ci_high = np.nan
    return {
        "n_bootstrap_requested": int(n_boot),
        "n_bootstrap_valid": len(values),
        "n_bootstrap_undefined": undefined,
        "bootstrap_undefined_fraction": undefined / n_boot if n_boot else np.nan,
        "c_index_ci_low": ci_low,
        "c_index_ci_high": ci_high,
    }


def build_performance_summary(
    predictions: pd.DataFrame, *, n_boot: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED
) -> pd.DataFrame:
    rows = []
    for endpoint_id in ENDPOINT_ORDER:
        endpoint = predictions.loc[predictions.endpoint_id.eq(endpoint_id)]
        evaluable = endpoint.loc[endpoint.endpoint_status.eq("evaluable")]
        event = evaluable.event.to_numpy(dtype=float)
        time_years = evaluable.time_years.to_numpy(dtype=float)
        risk = evaluable.marker7_risk.to_numpy(dtype=float)
        if len(evaluable) and (
            not np.isfinite(event).all() or not np.isin(event, [0.0, 1.0]).all()
            or not np.isfinite(time_years).all() or (time_years <= 0).any()
        ):
            raise EvidenceError(f"invalid evaluable endpoint values for {endpoint_id}")
        metric = harrell_c_index(event.astype(bool), time_years, risk)
        boot = bootstrap_c_index(
            event.astype(bool), time_years, risk, n_boot=n_boot, seed=seed
        )
        rows.append({
            "endpoint_id": endpoint_id,
            "endpoint_label": ENDPOINT_LABELS[endpoint_id],
            "endpoint_source": ENDPOINT_SOURCES[endpoint_id],
            "n_frozen_risk_patients": len(endpoint),
            "n_evaluable": len(evaluable),
            "n_excluded": len(endpoint) - len(evaluable),
            "n_events": int(event.sum()),
            "n_censored": int(len(event) - event.sum()),
            "analysis_time_unit": "years",
            "risk_direction": "higher_marker7_risk_is_worse",
            "c_index": metric[0],
            "n_concordant_pairs": metric[1],
            "n_discordant_pairs": metric[2],
            "n_tied_risk_pairs": metric[3],
            "n_tied_time_pairs": metric[4],
            "bootstrap_unit": "patient_row",
            "bootstrap_seed": seed,
            **boot,
            "status": "complete" if np.isfinite(metric[0]) else "undefined_no_comparable_pairs",
        })
    return pd.DataFrame(rows)


def _cohen_kappa(ref: np.ndarray, cmp: np.ndarray) -> float:
    n = len(ref)
    if n == 0:
        return np.nan
    agreement = float((ref == cmp).mean())
    ref0, ref1 = int((ref == 0).sum()), int((ref == 1).sum())
    cmp0, cmp1 = int((cmp == 0).sum()), int((cmp == 1).sum())
    expected = (ref0 * cmp0 + ref1 * cmp1) / (n * n)
    if expected == 1.0:
        return np.nan
    value = (agreement - expected) / (1.0 - expected)
    if abs(value) < 1e-15:
        value = 0.0
    if abs(value - 1.0) < 1e-15:
        value = 1.0
    return float(value)


def build_endpoint_concordance(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compare official PFI with every other endpoint on common evaluable patients."""
    required = {"case_id", "endpoint_id", "endpoint_status", "event", "time_years"}
    _require_columns(predictions, required, "patient predictions")
    reference_all = predictions.loc[predictions.endpoint_id.eq(OFFICIAL_ENDPOINT_ID)]
    reference = reference_all.loc[reference_all.endpoint_status.eq("evaluable"), [
        "case_id", "event", "time_years"
    ]].rename(columns={"event": "ref_event", "time_years": "ref_time_years"})
    comparator_ids = [
        value for value in predictions.endpoint_id.drop_duplicates().tolist()
        if value != OFFICIAL_ENDPOINT_ID
    ]
    rows = []
    for endpoint_id in comparator_ids:
        comparison_all = predictions.loc[predictions.endpoint_id.eq(endpoint_id)]
        comparison = comparison_all.loc[
            comparison_all.endpoint_status.eq("evaluable"), ["case_id", "event", "time_years"]
        ].rename(columns={"event": "cmp_event", "time_years": "cmp_time_years"})
        common = reference.merge(comparison, on="case_id", how="inner", validate="one_to_one")
        ref = common.ref_event.to_numpy(dtype=int)
        cmp = common.cmp_event.to_numpy(dtype=int)
        n00 = int(((ref == 0) & (cmp == 0)).sum())
        n01 = int(((ref == 0) & (cmp == 1)).sum())
        n10 = int(((ref == 1) & (cmp == 0)).sum())
        n11 = int(((ref == 1) & (cmp == 1)).sum())
        if len(common) >= 2:
            rho, p_value = stats.spearmanr(common.ref_time_years, common.cmp_time_years)
            rho, p_value = float(rho), float(p_value)
            if abs(rho - 1.0) < 1e-15:
                rho = 1.0
            elif abs(rho + 1.0) < 1e-15:
                rho = -1.0
        else:
            rho = p_value = np.nan
        rows.append({
            "reference_endpoint_id": OFFICIAL_ENDPOINT_ID,
            "comparison_endpoint_id": endpoint_id,
            "n_reference_evaluable": len(reference),
            "n_comparison_evaluable": len(comparison),
            "n_common_evaluable": len(common),
            "n_reference_events_common": int(ref.sum()),
            "n_comparison_events_common": int(cmp.sum()),
            "n_ref0_cmp0": n00,
            "n_ref0_cmp1": n01,
            "n_ref1_cmp0": n10,
            "n_ref1_cmp1": n11,
            "event_agreement": float((ref == cmp).mean()) if len(common) else np.nan,
            "cohen_kappa": _cohen_kappa(ref, cmp),
            "n_time_pairs": len(common),
            "time_spearman_rho": rho,
            "time_spearman_p": p_value,
            "time_comparison_unit": "years",
            "status": "complete" if len(common) else "undefined_no_common_evaluable_patients",
        })
    return pd.DataFrame(rows)


def _input_contract(root: Path) -> tuple[list[Path], dict[Path, str]]:
    roles = {
        root / f"local-data/TCGA-CDR/{EXPECTED_OFFICIAL_FILENAME}": "official_tcga_cdr_table_s1",
        root / "local-data/TCGA-CDR/PanCan-Clinical_Open_GDC-Manifest_1.txt": "official_gdc_manifest",
        root / "local-data/TCGA-CDR/source_provenance.json": "official_source_provenance",
        root / "models/confounder_nested_predictions.csv": "frozen_marker7_risk",
        root / "models/tcga_prad_clinical_extra/prad_pancan_clinical.json": "pfs_dfs_comparator",
        root / "opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv": "recurrence_only_comparator",
        root / "models/build_tcga_cdr_pfi_evidence.py": "analysis_entry_point",
        root / "models/pilot_tcga_prad_label_benchmark.py": "historical_endpoint_benchmark",
        root / "paper/MajorRevision-v1-remaining-experiments-and-revision-plan.md": "approved_R3_card",
        root / "AGENTS.md": "repository_instructions",
    }
    missing = [str(path) for path in roles if not path.is_file()]
    if missing:
        raise EvidenceError(f"missing declared inputs: {missing}")
    return list(roles), {path.absolute(): role for path, role in roles.items()}


def _snapshot_files(paths: list[Path], root: Path) -> dict[Path, dict]:
    snapshots = {}
    for raw_path in paths:
        path = raw_path.absolute()
        snapshots[path] = {
            "artifact_path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return snapshots


def _assert_unchanged(before: dict[Path, dict], after: dict[Path, dict]) -> None:
    if set(before) != set(after):
        raise EvidenceError("input snapshot set changed")
    for path in before:
        if (
            before[path]["size_bytes"] != after[path]["size_bytes"]
            or before[path]["sha256"] != after[path]["sha256"]
        ):
            raise EvidenceError(f"input changed during run: {before[path]['artifact_path']}")


MANIFEST_COLUMNS = [
    "artifact_kind", "artifact_role", "artifact_path", "size_bytes",
    "sha256_before", "sha256_after", "source_unchanged_assertion",
    "included_in_output_hashes", "hash_exclusion_reason", "generated_at_utc",
    "elapsed_seconds", "volatile_fields",
]


def _build_manifest(
    before: dict[Path, dict], after: dict[Path, dict], roles: dict[Path, str],
    staged_outputs: list[Path], generated_at: str, elapsed: float,
) -> pd.DataFrame:
    rows = []
    for path, snapshot in sorted(before.items(), key=lambda item: item[1]["artifact_path"]):
        rows.append({
            "artifact_kind": "input",
            "artifact_role": roles[path],
            "artifact_path": snapshot["artifact_path"],
            "size_bytes": snapshot["size_bytes"],
            "sha256_before": snapshot["sha256"],
            "sha256_after": after[path]["sha256"],
            "source_unchanged_assertion": snapshot["sha256"] == after[path]["sha256"],
            "included_in_output_hashes": False,
            "hash_exclusion_reason": "input_not_output",
            "generated_at_utc": "",
            "elapsed_seconds": "",
            "volatile_fields": "",
        })
    for path in staged_outputs:
        rows.append({
            "artifact_kind": "output",
            "artifact_role": path.name,
            "artifact_path": path.name,
            "size_bytes": path.stat().st_size,
            "sha256_before": "",
            "sha256_after": sha256_file(path),
            "source_unchanged_assertion": "",
            "included_in_output_hashes": True,
            "hash_exclusion_reason": "",
            "generated_at_utc": "",
            "elapsed_seconds": "",
            "volatile_fields": "",
        })
    rows.append({
        "artifact_kind": "output",
        "artifact_role": MANIFEST_NAME,
        "artifact_path": MANIFEST_NAME,
        "size_bytes": "",
        "sha256_before": "",
        "sha256_after": "",
        "source_unchanged_assertion": "",
        "included_in_output_hashes": False,
        "hash_exclusion_reason": "self_referential_manifest",
        "generated_at_utc": generated_at,
        "elapsed_seconds": f"{elapsed:.6f}",
        "volatile_fields": "generated_at_utc;elapsed_seconds",
    })
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


MAPPING_COLUMNS = [
    "case_id", "risk_source_row_number", "marker7_risk", "normalized_barcode",
    "official_source_sheet", "n_official_matches", "official_source_row_number",
    "official_barcode_raw", "official_cancer_type", "official_pfi_event_raw",
    "official_pfi_time_days_raw", "official_pfi_event", "official_pfi_time_days",
    "official_pfi_time_years", "mapping_status", "endpoint_status", "exclusion_reason",
]
CONCORDANCE_COLUMNS = [
    "reference_endpoint_id", "comparison_endpoint_id", "n_reference_evaluable",
    "n_comparison_evaluable", "n_common_evaluable", "n_reference_events_common",
    "n_comparison_events_common", "n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0",
    "n_ref1_cmp1", "event_agreement", "cohen_kappa", "n_time_pairs",
    "time_spearman_rho", "time_spearman_p", "time_comparison_unit", "status",
]
PERFORMANCE_COLUMNS = [
    "endpoint_id", "endpoint_label", "endpoint_source", "n_frozen_risk_patients",
    "n_evaluable", "n_excluded", "n_events", "n_censored", "analysis_time_unit",
    "risk_direction", "c_index", "n_concordant_pairs", "n_discordant_pairs",
    "n_tied_risk_pairs", "n_tied_time_pairs", "bootstrap_unit", "bootstrap_seed",
    "n_bootstrap_requested", "n_bootstrap_valid", "n_bootstrap_undefined",
    "bootstrap_undefined_fraction", "c_index_ci_low", "c_index_ci_high", "status",
]
PREDICTION_COLUMNS = [
    "case_id", "endpoint_id", "endpoint_label", "endpoint_source", "marker7_risk",
    "event", "time_value_source", "time_unit_source", "time_years", "mapping_status",
    "endpoint_status", "exclusion_reason",
]


def _read_staged_csv(directory: Path, name: str, expected_columns: list[str]) -> pd.DataFrame:
    path = directory / name
    if not path.is_file():
        raise EvidenceError(f"missing staged output: {name}")
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise EvidenceError(f"staged CSV cannot be read: {name}") from exc
    if list(frame.columns) != expected_columns:
        raise EvidenceError(f"staged CSV schema mismatch: {name}")
    return frame


def _validate_staged_outputs(
    directory: Path, *, n_risk: int, n_boot: int, seed: int | None = None
) -> None:
    """Re-read and reconcile every staged artifact before publication."""
    directory = Path(directory)
    mapping = _read_staged_csv(directory, MAPPING_NAME, MAPPING_COLUMNS)
    concordance = _read_staged_csv(directory, CONCORDANCE_NAME, CONCORDANCE_COLUMNS)
    performance = _read_staged_csv(directory, PERFORMANCE_NAME, PERFORMANCE_COLUMNS)
    predictions = _read_staged_csv(directory, PREDICTIONS_NAME, PREDICTION_COLUMNS)

    if len(mapping) != n_risk or mapping.case_id.duplicated().any():
        raise EvidenceError("staged mapping patient key/count mismatch")
    validate_canonical_mapping(mapping)
    if not pd.to_numeric(mapping.n_official_matches, errors="coerce").eq(1).all():
        raise EvidenceError("staged mapping does not contain exactly one official match per patient")

    expected_prediction_keys = n_risk * len(ENDPOINT_ORDER)
    if (
        len(predictions) != expected_prediction_keys
        or predictions.duplicated(["endpoint_id", "case_id"]).any()
        or set(predictions.endpoint_id) != set(ENDPOINT_ORDER)
        or not predictions.groupby("endpoint_id").size().eq(n_risk).all()
    ):
        raise EvidenceError("staged patient prediction endpoint/case key mismatch")

    if (
        len(performance) != len(ENDPOINT_ORDER)
        or performance.endpoint_id.duplicated().any()
        or set(performance.endpoint_id) != set(ENDPOINT_ORDER)
        or not pd.to_numeric(performance.n_frozen_risk_patients, errors="coerce").eq(n_risk).all()
        or not pd.to_numeric(performance.n_bootstrap_requested, errors="coerce").eq(n_boot).all()
    ):
        raise EvidenceError("staged performance endpoint/count contract failed")
    valid = pd.to_numeric(performance.n_bootstrap_valid, errors="coerce")
    undefined = pd.to_numeric(performance.n_bootstrap_undefined, errors="coerce")
    if not (valid + undefined).eq(n_boot).all():
        raise EvidenceError("staged performance bootstrap accounting failed")

    expected_comparators = set(ENDPOINT_ORDER) - {OFFICIAL_ENDPOINT_ID}
    confusion_columns = ["n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0", "n_ref1_cmp1"]
    if (
        len(concordance) != len(expected_comparators)
        or concordance.comparison_endpoint_id.duplicated().any()
        or set(concordance.comparison_endpoint_id) != expected_comparators
        or not concordance.reference_endpoint_id.eq(OFFICIAL_ENDPOINT_ID).all()
        or not concordance[confusion_columns].sum(axis=1).eq(
            pd.to_numeric(concordance.n_common_evaluable, errors="coerce")
        ).all()
    ):
        raise EvidenceError("staged endpoint concordance key/arithmetic mismatch")

    config_path = directory / CONFIG_NAME
    if not config_path.is_file():
        raise EvidenceError(f"missing staged output: {CONFIG_NAME}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise EvidenceError("staged run config cannot be read") from exc
    performance_config = config.get("performance", {})
    if (
        config.get("outputs") != list(ALL_OUTPUT_NAMES)
        or config.get("endpoints") != list(ENDPOINT_ORDER)
        or performance_config.get("bootstrap_draws") != n_boot
        or (seed is not None and performance_config.get("bootstrap_seed") != seed)
        or "openpyxl" not in config.get("runtime", {}).get("versions", {})
    ):
        raise EvidenceError("staged run config contract failed")

    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise EvidenceError(f"missing staged output: {MANIFEST_NAME}")
    try:
        manifest = pd.read_csv(manifest_path, keep_default_na=False)
    except Exception as exc:
        raise EvidenceError("staged run manifest cannot be read") from exc
    if list(manifest.columns) != MANIFEST_COLUMNS:
        raise EvidenceError("staged run manifest schema mismatch")
    self_rows = manifest.loc[manifest.artifact_path.eq(MANIFEST_NAME)]
    if (
        len(self_rows) != 1
        or self_rows.iloc[0].sha256_after != ""
        or str(self_rows.iloc[0].included_in_output_hashes) != "False"
        or self_rows.iloc[0].hash_exclusion_reason != "self_referential_manifest"
    ):
        raise EvidenceError("staged run manifest self-hash contract failed")
    output_rows = manifest.loc[
        manifest.artifact_kind.eq("output") & ~manifest.artifact_path.eq(MANIFEST_NAME)
    ]
    if set(output_rows.artifact_path) != set(DETERMINISTIC_OUTPUT_NAMES):
        raise EvidenceError("staged run manifest output set mismatch")
    for record in output_rows.itertuples(index=False):
        path = directory / record.artifact_path
        if (
            str(record.included_in_output_hashes) != "True"
            or record.sha256_after != sha256_file(path)
            or int(record.size_bytes) != path.stat().st_size
        ):
            raise EvidenceError(f"staged output hash/size mismatch: {record.artifact_path}")
    input_rows = manifest.loc[manifest.artifact_kind.eq("input")]
    if input_rows.empty or not (
        (input_rows.sha256_before == input_rows.sha256_after)
        & input_rows.source_unchanged_assertion.map(str).eq("True")
    ).all():
        raise EvidenceError("staged run manifest input reconciliation failed")


def validate_run_parameters(root: Path, output_dir: Path, *, n_boot: int, seed: int) -> None:
    if n_boot <= 0:
        raise EvidenceError("n_boot must be positive")
    canonical_output = (Path(root).resolve() / "models").resolve()
    if Path(output_dir).resolve() == canonical_output and (
        n_boot != N_BOOTSTRAP or seed != BOOTSTRAP_SEED
    ):
        raise EvidenceError(
            "canonical models output requires bootstrap draws=2000 and seed=20260806"
        )


def _publish(staged: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Install a validated set with rollback; the manifest is the final commit marker."""
    missing = [name for name in PUBLICATION_ORDER if name not in staged or not staged[name].is_file()]
    if missing:
        raise EvidenceError(f"staged publication set is incomplete: {missing}")
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    destinations = {name: output_dir / name for name in PUBLICATION_ORDER}
    with tempfile.TemporaryDirectory(
        prefix=".tcga-cdr-pfi-backup-", dir=output_dir.parent
    ) as temporary:
        backup = Path(temporary)
        for name, destination in destinations.items():
            if destination.exists():
                shutil.copy2(destination, backup / name)
        installed: set[str] = set()
        try:
            for name in PUBLICATION_ORDER:
                os.replace(staged[name], destinations[name])
                installed.add(name)
        except Exception as exc:
            for name, destination in destinations.items():
                previous = backup / name
                if previous.exists():
                    os.replace(previous, destination)
                elif name in installed and destination.exists():
                    destination.unlink()
            raise EvidenceError("atomic publication failed; previous output set restored") from exc
    return destinations


def run_analysis(
    root: Path = ROOT, output_dir: Path | None = None, *,
    n_boot: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED,
) -> dict[str, Path]:
    """Run R3 from immutable inputs, validate staging, and publish the six outputs."""
    started = time.perf_counter()
    root = Path(root).resolve()
    output_dir = root / "models" if output_dir is None else Path(output_dir).resolve()
    validate_run_parameters(root, output_dir, n_boot=n_boot, seed=seed)
    if Path(sys.executable).absolute() != (root / ".venv/bin/python").absolute():
        raise EvidenceError(f"run with mandated controller: {root / '.venv/bin/python'}")
    inputs, roles = _input_contract(root)
    before = _snapshot_files(inputs, root)
    risk_path = root / "models/confounder_nested_predictions.csv"
    if sha256_file(risk_path) != EXPECTED_RISK_SHA256:
        raise EvidenceError("frozen marker-7 risk source SHA256 mismatch")

    official, official_metadata = _official_source(root)
    risk = select_frozen_risk(pd.read_csv(risk_path))
    mapping = build_official_mapping(risk, official)
    validate_canonical_mapping(mapping)
    predictions = build_patient_predictions(root, risk, mapping)
    performance = build_performance_summary(predictions, n_boot=n_boot, seed=seed)
    concordance = build_endpoint_concordance(predictions)
    if len(mapping) != len(risk) or len(predictions) != len(risk) * len(ENDPOINT_ORDER):
        raise EvidenceError("R3 output row reconciliation failed")

    after = _snapshot_files(inputs, root)
    _assert_unchanged(before, after)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tcga-cdr-pfi-stage-", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        frames = {
            MAPPING_NAME: mapping,
            CONCORDANCE_NAME: concordance,
            PERFORMANCE_NAME: performance,
            PREDICTIONS_NAME: predictions,
        }
        for name, frame in frames.items():
            _write_csv(frame, stage / name)
        config = {
            "analysis_id": "R3_official_TCGA_CDR_PFI",
            "analysis_role": "exploratory endpoint audit of frozen marker-7 risk",
            "official_source": official_metadata,
            "frozen_risk": {
                "source": "models/confounder_nested_predictions.csv",
                "sha256": EXPECTED_RISK_SHA256,
                "selector": {"marker": "marker7_recurrence", "analysis": "grade_only", "scope": "patient"},
                "n_unique_patients": len(risk),
                "fully_adjusted_overlap_risk_agreement": True,
            },
            "endpoints": list(ENDPOINT_ORDER),
            "time_conversion": {"days_to_years": "divide_by_365.25", "months_to_years": "divide_by_12"},
            "missing_outcome_policy": "never_convert_missing_invalid_or_unmapped_to_censored_or_no",
            "performance": {
                "metric": "Harrell_C_index",
                "risk_direction": "higher_marker7_risk_is_worse",
                "bootstrap_unit": "patient_row",
                "bootstrap_draws": n_boot,
                "bootstrap_seed": seed,
                "interval": "percentile_2.5_97.5",
                "undefined_replicates": "retained_and_counted",
            },
            "counts": {
                row.endpoint_id: {
                    "n_evaluable": int(row.n_evaluable), "n_events": int(row.n_events),
                    "n_excluded": int(row.n_excluded),
                }
                for row in performance.itertuples(index=False)
            },
            "input_sha256": {
                snapshot["artifact_path"]: snapshot["sha256"]
                for snapshot in sorted(before.values(), key=lambda item: item["artifact_path"])
            },
            "source_unchanged_assertion": True,
            "runtime": {
                "entry": ".venv/bin/python", "device": "CPU",
                "versions": {
                    "python": sys.version.split()[0], "numpy": np.__version__,
                    "pandas": pd.__version__, "scipy": scipy.__version__,
                    "openpyxl": openpyxl.__version__,
                },
            },
            "outputs": list(ALL_OUTPUT_NAMES),
            "atomic_publication": (
                "all artifacts staged and re-read; backup+rollback os.replace per file; "
                "manifest installed last"
            ),
            "volatile_manifest_fields": ["generated_at_utc", "elapsed_seconds"],
        }
        _write_json(config, stage / CONFIG_NAME)
        staged_outputs = [stage / name for name in DETERMINISTIC_OUTPUT_NAMES]
        manifest = _build_manifest(
            before, after, roles, staged_outputs, generated_at, time.perf_counter() - started
        )
        _write_csv(manifest, stage / MANIFEST_NAME)
        if manifest.loc[manifest.artifact_path.eq(MANIFEST_NAME), "sha256_after"].iloc[0] != "":
            raise EvidenceError("run manifest must not contain a self hash")
        _validate_staged_outputs(
            stage, n_risk=len(risk), n_boot=n_boot, seed=seed
        )
        staged = {name: stage / name for name in ALL_OUTPUT_NAMES}
        return _publish(staged, output_dir)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bootstrap-draws", type=int, default=N_BOOTSTRAP)
    parser.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = parse_args(argv)
    outputs = run_analysis(
        arguments.root, arguments.output_dir,
        n_boot=arguments.bootstrap_draws, seed=arguments.bootstrap_seed,
    )
    performance = pd.read_csv(outputs[PERFORMANCE_NAME])
    official = performance.loc[performance.endpoint_id.eq(OFFICIAL_ENDPOINT_ID)].iloc[0]
    print(json.dumps({
        "status": "complete",
        "official_pfi_n": int(official.n_evaluable),
        "official_pfi_events": int(official.n_events),
        "official_pfi_c_index": float(official.c_index),
        "outputs": {name: str(path) for name, path in outputs.items()},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
