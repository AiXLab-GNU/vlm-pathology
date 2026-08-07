"""Build the approved CPU-only R5 AR/SPOP evidence-closure artifacts.

The analysis reuses frozen CONCH embeddings.  Whole-slide files are opened only
to read page-0 TIFF tags; pixel arrays and full-file hashes are intentionally not
read because the 300 slides total roughly 247 GiB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
import tifffile
from scipy import stats
from scipy.optimize import brentq
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
AR_NAME = "ar_site_characteristics.csv"
METADATA_NAME = "ar_slide_metadata_availability.csv"
SPOP_NAME = "spop_site_summary.csv"
POWER_NAME = "spop_power_summary.csv"
PREDICTIONS_NAME = "spop_site_predictions.csv"
CONFIG_NAME = "ar_spop_evidence_run_config.json"
MANIFEST_NAME = "ar_spop_evidence_manifest.csv"
OUTPUT_NAMES = (AR_NAME, METADATA_NAME, SPOP_NAME, POWER_NAME, PREDICTIONS_NAME, CONFIG_NAME)
MIN_SITE_SLIDES = 20
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 0


class EvidenceClosureError(RuntimeError):
    """Raised when a frozen R5 input or derived invariant does not reconcile."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
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


def minimum_detectable_auroc(
    n_positive: int, n_negative: int, *, alpha: float = 0.05, power: float = 0.80
) -> float:
    """Hanley--McNeil fixed-score normal-approximation AUROC MDE."""
    threshold = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)

    def equation(auc: float) -> float:
        q1 = auc / (2 - auc)
        q2 = 2 * auc**2 / (1 + auc)
        variance = (
            auc * (1 - auc)
            + (n_positive - 1) * (q1 - auc**2)
            + (n_negative - 1) * (q2 - auc**2)
        ) / (n_positive * n_negative)
        return (auc - 0.5) / np.sqrt(variance) - threshold

    return float(brentq(equation, 0.500001, 0.999999))


def bootstrap_patient_auc(
    prediction: np.ndarray, truth: np.ndarray, *, n_boot: int = N_BOOTSTRAP, seed: int = 0
) -> dict:
    """Patient-row bootstrap retaining the accounting for every undefined draw."""
    prediction = np.asarray(prediction, dtype=float)
    truth = np.asarray(truth, dtype=int)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    undefined = 0
    for _ in range(n_boot):
        indices = rng.integers(0, len(truth), len(truth))
        if len(np.unique(truth[indices])) < 2:
            undefined += 1
            continue
        values.append(float(roc_auc_score(truth[indices], prediction[indices])))
    if values:
        ci_low, ci_high = np.percentile(values, [2.5, 97.5])
    else:
        ci_low = ci_high = np.nan
    return {
        "n_bootstrap_requested": int(n_boot),
        "n_bootstrap_valid": len(values),
        "n_bootstrap_undefined": undefined,
        "bootstrap_undefined_fraction": undefined / n_boot if n_boot else np.nan,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
    }


def _patient_frame(slides: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        conflicts = slides.groupby("case_id", sort=True)[column].nunique(dropna=False)
        if (conflicts != 1).any():
            raise EvidenceClosureError(f"conflicting patient-level {column}")
    return slides.drop_duplicates("case_id").set_index("case_id").sort_index()


def build_ar_site_characteristics(
    slides: pd.DataFrame, forest: pd.DataFrame, *, min_site_slides: int = MIN_SITE_SLIDES
) -> pd.DataFrame:
    """Describe AR/Gleason at patient level while preserving slide-level forest effects."""
    forest = forest.loc[forest["kind"].eq("leave-one-site-out")].copy()
    if forest.site.duplicated().any():
        raise EvidenceClosureError("duplicate frozen AR forest row")
    forest = forest.set_index("site")
    eligible_sites = set(slides.site.value_counts().loc[lambda count: count >= min_site_slides].index)
    if set(forest.index) != eligible_sites:
        raise EvidenceClosureError("frozen AR forest row site set does not reconcile")
    rows = []
    for site, site_slides in slides.groupby("site", sort=True):
        patients = _patient_frame(site_slides, ["ar_score", "gleason_sum"])
        ar = pd.to_numeric(patients.ar_score, errors="coerce")
        gleason = pd.to_numeric(patients.gleason_sum, errors="coerce")
        eligible = len(site_slides) >= min_site_slides
        if eligible and site not in forest.index:
            raise EvidenceClosureError(f"missing frozen AR forest row for eligible site {site}")
        effect = forest.loc[site] if eligible else None
        if effect is not None:
            expected_counts = (int(site_slides.ar_score.notna().sum()), int(ar.notna().sum()))
            try:
                stored_counts = (int(effect.n_slides), int(effect.n_patients))
                effect_values = np.asarray([effect.rho, effect.ci_lo, effect.ci_hi], dtype=float)
            except (TypeError, ValueError, OverflowError) as exc:
                raise EvidenceClosureError(f"invalid frozen AR forest row for site {site}") from exc
            valid_interval = (
                np.isfinite(effect_values).all()
                and np.all((-1.0 <= effect_values) & (effect_values <= 1.0))
                and effect_values[1] <= effect_values[0] <= effect_values[2]
            )
            if stored_counts != expected_counts or not valid_interval:
                raise EvidenceClosureError(f"frozen AR forest row does not reconcile for site {site}")
        rows.append({
            "site": site,
            "n_slides": len(site_slides),
            "n_patients": len(patients),
            "n_ar_evaluable_slides": int(site_slides.ar_score.notna().sum()),
            "n_ar_evaluable_patients": int(ar.notna().sum()),
            "n_ar_missing_slides": int(site_slides.ar_score.isna().sum()),
            "n_ar_missing_patients": int(ar.isna().sum()),
            "n_gleason_evaluable_slides": int(site_slides.gleason_sum.notna().sum()),
            "n_gleason_evaluable_patients": int(gleason.notna().sum()),
            "n_gleason_missing_slides": int(site_slides.gleason_sum.isna().sum()),
            "n_gleason_missing_patients": int(gleason.isna().sum()),
            "forest_eligible": bool(eligible),
            "forest_exclusion_reason": "" if eligible else "n_slides_lt_20",
            "ar_q25": ar.quantile(0.25, interpolation="linear"),
            "ar_median": ar.quantile(0.50, interpolation="linear"),
            "ar_q75": ar.quantile(0.75, interpolation="linear"),
            "ar_mean": ar.mean(),
            "ar_sd": ar.std(ddof=1),
            "gleason_q25": gleason.quantile(0.25, interpolation="linear"),
            "gleason_median": gleason.quantile(0.50, interpolation="linear"),
            "gleason_q75": gleason.quantile(0.75, interpolation="linear"),
            "loo_rho": effect.rho if effect is not None else np.nan,
            "loo_ci_low": effect.ci_lo if effect is not None else np.nan,
            "loo_ci_high": effect.ci_hi if effect is not None else np.nan,
            "loo_metric_unit": "slide" if eligible else "not_applicable",
            "bootstrap_unit": "patient_cluster" if eligible else "not_applicable",
            "n_bootstrap_requested": N_BOOTSTRAP if eligible else 0,
            "n_bootstrap_valid": N_BOOTSTRAP if eligible else 0,
            "n_bootstrap_undefined": 0,
            "bootstrap_undefined_fraction": 0.0 if eligible else np.nan,
        })
    return pd.DataFrame(rows)


def fit_spop_site_predictions(
    X: np.ndarray, slides: pd.DataFrame, *, min_site_slides: int = MIN_SITE_SLIDES
) -> pd.DataFrame:
    """Reconstruct the historical balanced-logistic leave-one-site-out predictions."""
    if len(X) != len(slides) or not np.isfinite(X).all():
        raise EvidenceClosureError("embedding/metadata alignment or finiteness failure")
    rows = []
    sites = slides.site.to_numpy()
    truth = slides.spop_mut.to_numpy(dtype=int)
    for site in sorted(slides.site.value_counts().loc[lambda value: value >= min_site_slides].index):
        test = sites == site
        train = ~test
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"),
        )
        model.fit(X[train], truth[train])
        probability = model.predict_proba(X[test])[:, 1]
        held_out = slides.loc[test]
        for (_, record), predicted in zip(held_out.iterrows(), probability):
            rows.append({
                "record_level": "slide", "held_out_site": site,
                "file_name": record.file_name, "case_id": record.case_id,
                "true_label": int(record.spop_mut),
                "predicted_probability": float(predicted), "n_component_slides": 1,
                "model_specification": "StandardScaler+LogisticRegression(C=1.0,class_weight=balanced,max_iter=2000)",
                "reconstruction_status": "reconstructed_from_frozen_conch_embedding",
            })
        patient = pd.DataFrame({
            "case_id": held_out.case_id.to_numpy(), "true_label": held_out.spop_mut.to_numpy(),
            "predicted_probability": probability,
        }).groupby("case_id", sort=True).agg(
            true_label=("true_label", "mean"),
            predicted_probability=("predicted_probability", "mean"),
            n_component_slides=("predicted_probability", "size"),
        ).reset_index()
        if not np.allclose(patient.true_label, patient.true_label.round()):
            raise EvidenceClosureError(f"conflicting SPOP labels within patient at site {site}")
        for record in patient.itertuples(index=False):
            rows.append({
                "record_level": "patient", "held_out_site": site, "file_name": "",
                "case_id": record.case_id, "true_label": int(round(record.true_label)),
                "predicted_probability": float(record.predicted_probability),
                "n_component_slides": int(record.n_component_slides),
                "model_specification": "StandardScaler+LogisticRegression(C=1.0,class_weight=balanced,max_iter=2000)",
                "reconstruction_status": "mean_slide_probability_patient_aggregation",
            })
    return pd.DataFrame(rows)


def build_spop_site_summary(
    slides: pd.DataFrame, predictions: pd.DataFrame, *, min_site_slides: int = MIN_SITE_SLIDES,
    n_boot: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED,
) -> pd.DataFrame:
    """Keep all sites and make undefined/small-class status explicit."""
    rows = []
    slide_predictions = predictions.loc[predictions.record_level.eq("slide")]
    for site, site_slides in slides.groupby("site", sort=True):
        patient_labels = _patient_frame(site_slides, ["spop_mut"])
        n_pos_slides = int(site_slides.spop_mut.sum())
        n_neg_slides = int(len(site_slides) - n_pos_slides)
        n_pos_patients = int(patient_labels.spop_mut.sum())
        n_neg_patients = int(len(patient_labels) - n_pos_patients)
        eligible = len(site_slides) >= min_site_slides
        historical = eligible and min(n_pos_slides, n_neg_slides) >= 5
        site_pred = slide_predictions.loc[slide_predictions.held_out_site.eq(site)]
        patient_auc = slide_auc = np.nan
        boot = {"n_bootstrap_requested": 0, "n_bootstrap_valid": 0,
                "n_bootstrap_undefined": 0, "bootstrap_undefined_fraction": np.nan,
                "ci_low": np.nan, "ci_high": np.nan}
        if eligible:
            if set(site_pred.file_name) != set(site_slides.file_name):
                raise EvidenceClosureError(f"SPOP prediction alignment failure for site {site}")
            patient = site_pred.groupby("case_id", sort=True).agg(
                true_label=("true_label", "mean"),
                predicted_probability=("predicted_probability", "mean"),
            )
            patient_truth = patient.true_label.round().astype(int).to_numpy()
            if len(np.unique(patient_truth)) == 2:
                patient_auc = float(roc_auc_score(patient_truth, patient.predicted_probability))
            boot = bootstrap_patient_auc(
                patient.predicted_probability.to_numpy(), patient_truth, n_boot=n_boot, seed=seed
            )
            if historical:
                slide_auc = float(roc_auc_score(site_pred.true_label, site_pred.predicted_probability))
        if not eligible:
            status = "not_reconstructed_n_slides_lt_20"
            warning = "not_applicable"
        elif n_pos_patients == 0 or n_neg_patients == 0:
            status = "undefined_single_class"
            warning = "single_patient_class"
        elif min(n_pos_patients, n_neg_patients) < 5:
            status = "complete_with_small_class_warning"
            warning = "min_patient_class_lt_5"
        else:
            status = "complete"
            warning = "none"
        rows.append({
            "site": site, "n_slides": len(site_slides), "n_patients": len(patient_labels),
            "n_evaluable_slides": len(site_slides), "n_positive_slides": n_pos_slides,
            "n_negative_slides": n_neg_slides, "n_missing_slides": 0,
            "n_evaluable_patients": len(patient_labels), "n_positive_patients": n_pos_patients,
            "n_negative_patients": n_neg_patients, "n_missing_patients": 0,
            "large_site_eligible": bool(eligible),
            "historical_slide_reportable": bool(historical),
            "patient_metric_defined": bool(np.isfinite(patient_auc)),
            "small_class_warning": warning, "status_reason": status,
            "slide_auroc_historical": slide_auc, "patient_auroc": patient_auc,
            "bootstrap_seed": seed if eligible else np.nan, **boot,
            "patient_ci_low": boot["ci_low"], "patient_ci_high": boot["ci_high"],
            "model_specification": "StandardScaler+balanced_LogisticRegression_LOSO",
            "reconstruction_status": status,
        })
    result = pd.DataFrame(rows)
    return result.drop(columns=["ci_low", "ci_high"])


def _tag_value(page, name: str):
    tag = page.tags.get(name)
    return None if tag is None else tag.value


def scan_slide_header(path: Path) -> dict:
    """Read selected page-0 TIFF tags without decoding any image pixels."""
    with tifffile.TiffFile(path) as tiff:
        page = tiff.pages[0]
        description = _tag_value(page, "ImageDescription")
        description = "" if description is None else str(description)
        parsed = {}
        for key, value in re.findall(r"(?:^|\|)\s*([^|=]+?)\s*=\s*([^|]*)", description):
            parsed[key.strip().lower()] = value.strip()
        icc_tag = page.tags.get(34675) or page.tags.get("InterColorProfile")
        icc_value = None if icc_tag is None else icc_tag.value
        if "icc profile" in parsed:
            icc_raw = parsed["icc profile"]
        elif icc_value is None:
            icc_raw = ""
        else:
            payload = icc_value if isinstance(icc_value, bytes) else str(icc_value).encode()
            icc_raw = f"sha256:{hashlib.sha256(payload).hexdigest()};bytes:{len(payload)}"
        explicit_stain = any("stain" in key for key in parsed)
        canonical = {
            "description": description,
            "image_width": _tag_value(page, "ImageWidth"),
            "image_length": _tag_value(page, "ImageLength"),
            "appmag": parsed.get("appmag", ""), "mpp": parsed.get("mpp", ""),
            "scanscope_id": parsed.get("scanscope id", ""), "icc": icc_raw,
        }
        canonical_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return {
            "header_read_status": "complete",
            "image_description_available": bool(description),
            "scanscope_id_available": "scanscope id" in parsed,
            "scanscope_id_raw": parsed.get("scanscope id", ""),
            "appmag_available": "appmag" in parsed, "appmag_raw": parsed.get("appmag", ""),
            "mpp_available": "mpp" in parsed, "mpp_raw": parsed.get("mpp", ""),
            "icc_profile_available": "icc profile" in parsed or icc_value is not None,
            "icc_profile_raw": icc_raw,
            "xresolution_tag_available": _tag_value(page, "XResolution") is not None,
            "make_tag_available": _tag_value(page, "Make") is not None,
            "model_tag_available": _tag_value(page, "Model") is not None,
            "software_tag_available": _tag_value(page, "Software") is not None,
            "explicit_stain_field_available": bool(explicit_stain),
            "stain_metadata_status": "not_available",
            "canonical_header_sha256": canonical_hash,
        }


def load_cohort(root: Path) -> tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    """Load and exactly reconcile the frozen cache, clinical labels, and GDC manifest."""
    meta_path = root / "models/tcga_prad_conch_cache/meta.csv"
    embedding_path = root / "models/tcga_prad_conch_cache/X.npy"
    clinical_path = root / "models/tcga_prad_clinical_extra/prad_pub_sample_clinical.json"
    manifest_path = root / "opendataset/TCGA-PRAD/manifest.csv"
    slides = pd.read_csv(meta_path)
    if list(slides.columns) != ["file_name", "case_id", "erg_fusion", "n_tiles"]:
        raise EvidenceClosureError("unexpected frozen cache metadata schema")
    if len(slides) != 300 or slides.file_name.nunique() != 300 or slides.case_id.nunique() != 273:
        raise EvidenceClosureError("expected exact 300-slide/273-patient frozen cache")
    expected_case = slides.file_name.str.extract(r"^(TCGA-[^-]+-[^-]+)", expand=False)
    if not expected_case.equals(slides.case_id):
        raise EvidenceClosureError("filename-to-patient mapping mismatch")
    if not slides.file_name.str.contains(r"-01Z-", regex=True).all():
        raise EvidenceClosureError("non-primary-tumor sample in cache")
    slides["site"] = slides.case_id.str.split("-").str[1]
    if slides.site.nunique() != 22:
        raise EvidenceClosureError("expected exactly 22 TSS sites")

    X = np.load(embedding_path)
    if X.shape[0] != len(slides) or X.ndim != 2 or not np.isfinite(X).all():
        raise EvidenceClosureError("frozen embedding alignment/finiteness failure")

    records = json.loads(clinical_path.read_text(encoding="utf-8"))
    wanted = {"AR_SCORE", "REVIEWED_GLEASON_SUM", "SPOP_MUTATION"}
    values: dict[str, dict[str, str]] = {attribute: {} for attribute in wanted}
    for record in records:
        attribute = record.get("clinicalAttributeId")
        if attribute not in wanted:
            continue
        patient = str(record["patientId"])
        if record.get("sampleId") != f"{patient}-01":
            raise EvidenceClosureError(f"sample/patient mapping mismatch for {attribute}:{patient}")
        value = str(record["value"])
        previous = values[attribute].get(patient)
        if previous is not None and previous != value:
            raise EvidenceClosureError(f"conflicting clinical values for {attribute}:{patient}")
        values[attribute][patient] = value
    for attribute in sorted(wanted):
        missing = set(slides.case_id) - set(values[attribute])
        if missing:
            raise EvidenceClosureError(f"missing {attribute} for {len(missing)} patients")
    slides["ar_score"] = slides.case_id.map(values["AR_SCORE"]).astype(float)
    slides["gleason_sum"] = slides.case_id.map(values["REVIEWED_GLEASON_SUM"]).astype(float)
    slides["spop_mut"] = slides.case_id.map(values["SPOP_MUTATION"]).astype(int)
    patients = _patient_frame(slides, ["ar_score", "gleason_sum", "spop_mut"])
    if int(patients.spop_mut.sum()) != 29 or int((patients.spop_mut == 0).sum()) != 244:
        raise EvidenceClosureError("expected exact SPOP patient classes 29/244")

    gdc = pd.read_csv(manifest_path)
    required = {"file_id", "file_name", "file_size", "case_id"}
    if not required.issubset(gdc.columns) or gdc.file_name.duplicated().any():
        raise EvidenceClosureError("invalid GDC manifest schema or duplicate filename")
    selected = gdc.loc[gdc.file_name.isin(slides.file_name)].copy()
    if len(selected) != 300 or set(selected.file_name) != set(slides.file_name):
        raise EvidenceClosureError("cache/GDC manifest set mismatch")
    selected = selected.set_index("file_name").loc[slides.file_name].reset_index()
    validate_gdc_identifiers(selected, expected_count=300)
    if not np.array_equal(selected.case_id.to_numpy(), slides.case_id.to_numpy()):
        raise EvidenceClosureError("GDC/cache case mapping mismatch")
    return X, slides, selected


def validate_gdc_identifiers(frame: pd.DataFrame, *, expected_count: int) -> None:
    if "file_id" not in frame or len(frame) != expected_count:
        raise EvidenceClosureError("GDC file_id count/schema mismatch")
    identifiers = frame.file_id.astype("string")
    if identifiers.isna().any() or identifiers.str.strip().eq("").any() or identifiers.nunique() != expected_count:
        raise EvidenceClosureError("GDC file_id values must be complete and unique")


def build_metadata_availability(root: Path, slides: pd.DataFrame, gdc: pd.DataFrame) -> pd.DataFrame:
    """Scan page-0 metadata for the exact 300 cache slides."""
    gdc_by_name = gdc.set_index("file_name")
    rows = []
    for record in slides.itertuples(index=False):
        path = root / "opendataset/TCGA-PRAD/slides" / record.file_name
        if not path.is_file():
            raise EvidenceClosureError(f"missing WSI: {record.file_name}")
        manifest = gdc_by_name.loc[record.file_name]
        actual_size = path.stat().st_size
        if int(manifest.file_size) != actual_size:
            raise EvidenceClosureError(f"WSI size mismatch: {record.file_name}")
        header = scan_slide_header(path)
        rows.append({
            "file_name": record.file_name, "case_id": record.case_id, "site": record.site,
            "gdc_file_id": manifest.file_id, "expected_file_size": int(manifest.file_size),
            "actual_file_size": actual_size, **header,
            "full_file_sha256_status": "not_computed_large_input",
        })
    result = pd.DataFrame(rows)
    if len(result) != 300 or result.file_name.nunique() != 300:
        raise EvidenceClosureError("metadata output is not exact 300-slide set")
    return result


def build_power_summary() -> pd.DataFrame:
    limitation = (
        "Fixed-score normal approximation; excludes probe-training uncertainty, OOF dependence, "
        "site heterogeneity, configuration selection, and multiplicity; not an effect-exclusion bound."
    )
    rows = []
    for power in (0.80, 0.90):
        rows.append({
            "cohort": "TCGA-PRAD", "analysis_unit": "patient", "n_positive": 29,
            "n_negative": 244, "null_auroc": 0.5, "alpha": 0.05,
            "alternative": "two_sided", "target_power": power,
            "minimum_detectable_auroc": minimum_detectable_auroc(29, 244, power=power),
            "variance_method": "Hanley-McNeil AUROC variance",
            "solver": "scipy.optimize.brentq", "solver_lower": 0.500001,
            "solver_upper": 0.999999, "approximation_scope": "fixed_score_normal_approximation",
            "limitation": limitation,
        })
    return pd.DataFrame(rows)


class FileSnapshot:
    def __init__(self, path: Path, artifact_path: str, size_bytes: int, mtime_ns: int, sha256: str):
        self.path = path
        self.artifact_path = artifact_path
        self.size_bytes = size_bytes
        self.mtime_ns = mtime_ns
        self.sha256 = sha256


def snapshot_files(paths: list[Path], root: Path) -> dict[Path, FileSnapshot]:
    snapshots = {}
    for original in paths:
        path = Path(original).absolute()
        try:
            relative = path.relative_to(root.absolute()).as_posix()
        except ValueError as exc:
            raise EvidenceClosureError(f"input outside repository root: {path}") from exc
        stat = path.stat()
        snapshots[path] = FileSnapshot(path, relative, stat.st_size, stat.st_mtime_ns, sha256_file(path))
    return snapshots


def assert_snapshots_unchanged(
    before: dict[Path, FileSnapshot], after: dict[Path, FileSnapshot]
) -> None:
    if set(before) != set(after):
        raise EvidenceClosureError("input snapshot set changed")
    for path in before:
        if (before[path].size_bytes, before[path].sha256) != (after[path].size_bytes, after[path].sha256):
            raise EvidenceClosureError(f"input changed during run: {before[path].artifact_path}")


MANIFEST_COLUMNS = [
    "artifact_kind", "artifact_role", "artifact_path", "size_bytes",
    "sha256_before", "sha256_after", "source_unchanged_assertion",
    "full_file_sha256_status", "canonical_header_sha256", "gdc_file_id",
    "included_in_output_hashes", "hash_exclusion_reason",
    "generated_at_utc", "elapsed_seconds", "volatile_fields", "lineage_limitation",
]


def build_manifest(
    root: Path,
    input_before: dict[Path, FileSnapshot],
    input_after: dict[Path, FileSnapshot],
    input_roles: dict[Path, str],
    slide_metadata: pd.DataFrame,
    output_paths: list[Path],
    manifest_path: Path,
    generated_at_utc: str,
    elapsed_seconds: float,
) -> pd.DataFrame:
    rows = []
    for path, before in sorted(input_before.items(), key=lambda item: item[1].artifact_path):
        after = input_after[path]
        rows.append({
            "artifact_kind": "input", "artifact_role": input_roles[path],
            "artifact_path": before.artifact_path, "size_bytes": before.size_bytes,
            "sha256_before": before.sha256, "sha256_after": after.sha256,
            "source_unchanged_assertion": before.sha256 == after.sha256,
            "full_file_sha256_status": "computed", "canonical_header_sha256": "",
            "gdc_file_id": "",
            "included_in_output_hashes": False, "hash_exclusion_reason": "input_not_output",
            "generated_at_utc": "", "elapsed_seconds": "", "volatile_fields": "",
            "lineage_limitation": "",
        })
    for record in slide_metadata.itertuples(index=False):
        rows.append({
            "artifact_kind": "input", "artifact_role": "svs_header_only",
            "artifact_path": f"opendataset/TCGA-PRAD/slides/{record.file_name}",
            "size_bytes": int(record.actual_file_size), "sha256_before": "", "sha256_after": "",
            "source_unchanged_assertion": int(record.actual_file_size) == int(record.expected_file_size),
            "full_file_sha256_status": "not_computed_large_input",
            "canonical_header_sha256": record.canonical_header_sha256,
            "gdc_file_id": record.gdc_file_id,
            "included_in_output_hashes": False,
            "hash_exclusion_reason": "247GiB_collection_header_only_scope",
            "generated_at_utc": "", "elapsed_seconds": "", "volatile_fields": "",
            "lineage_limitation": "",
        })
    for path in output_paths:
        rows.append({
            "artifact_kind": "output", "artifact_role": path.name,
            "artifact_path": path.name, "size_bytes": path.stat().st_size,
            "sha256_before": "", "sha256_after": sha256_file(path),
            "source_unchanged_assertion": "", "full_file_sha256_status": "computed",
            "canonical_header_sha256": "", "included_in_output_hashes": True,
            "gdc_file_id": "",
            "hash_exclusion_reason": "", "generated_at_utc": "", "elapsed_seconds": "",
            "volatile_fields": "", "lineage_limitation": "",
        })
    rows.append({
        "artifact_kind": "output", "artifact_role": MANIFEST_NAME,
        "artifact_path": MANIFEST_NAME, "size_bytes": "", "sha256_before": "", "sha256_after": "",
        "source_unchanged_assertion": "", "full_file_sha256_status": "excluded",
        "canonical_header_sha256": "", "gdc_file_id": "", "included_in_output_hashes": False,
        "hash_exclusion_reason": "self_referential_manifest", "generated_at_utc": generated_at_utc,
        "elapsed_seconds": f"{elapsed_seconds:.6f}",
        "volatile_fields": "generated_at_utc;elapsed_seconds", "lineage_limitation": (
            "Current 300-slide CONCH cache has no matching generation log/config; upstream embedding "
            "lineage remains unresolved and current cache hashes are treated as frozen inputs."
        ),
    })
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


def normalize_manifest_for_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["generated_at_utc"] = ""
    result["elapsed_seconds"] = ""
    return result


def _runtime_versions() -> dict:
    return {
        "python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
        "tifffile": tifffile.__version__,
    }


def _input_contract(root: Path) -> tuple[list[Path], dict[Path, str]]:
    roles = {
        root / "models/tcga_prad_conch_cache/X.npy": "frozen_conch_embeddings",
        root / "models/tcga_prad_conch_cache/meta.csv": "frozen_cache_metadata",
        root / "models/tcga_prad_clinical_extra/prad_pub_sample_clinical.json": "clinical_labels",
        root / "opendataset/TCGA-PRAD/manifest.csv": "gdc_manifest",
        root / "models/ar_site_forest_summary.csv": "frozen_ar_forest",
        root / "models/spop_classweight_ablation_summary.csv": "frozen_spop_ablation",
        root / "models/pilot_tcga_prad_site_split.py": "historical_site_runner",
        root / "models/pilot_ar_site_forest.py": "historical_ar_runner",
        root / "models/pilot_spop_classweight_ablation.py": "historical_spop_runner",
        root / "models/build_ar_spop_evidence_closure.py": "analysis_entry_point",
        root / "environment.yml": "environment_specification",
        root / "requirements-lock.txt": "requirements_lock",
        root / "AGENTS.md": "repository_instructions",
        root / "paper/MajorRevision-v1-remaining-experiments-and-revision-plan.md": "approved_R5_design",
    }
    missing = [path for path in roles if not path.is_file()]
    if missing:
        raise EvidenceClosureError(f"missing declared inputs: {[str(path) for path in missing]}")
    return list(roles), {path.absolute(): role for path, role in roles.items()}


def _validate_real_outputs(
    ar: pd.DataFrame, metadata: pd.DataFrame, spop: pd.DataFrame,
    power: pd.DataFrame, predictions: pd.DataFrame,
) -> None:
    if (len(ar), len(metadata), len(spop), len(power), len(predictions)) != (22, 300, 22, 2, 433):
        raise EvidenceClosureError("R5 output row-count contract failed")
    eligible = {"CH", "EJ", "G9", "HC", "KK", "YL"}
    if set(ar.loc[ar.forest_eligible, "site"]) != eligible:
        raise EvidenceClosureError("AR six-site eligibility mismatch")
    if (
        int(ar.loc[ar.forest_eligible, "n_slides"].sum()) != 224
        or int(ar.loc[ar.forest_eligible, "n_patients"].sum()) != 209
    ):
        raise EvidenceClosureError("AR six-site 224-slide/209-patient subtotal mismatch")
    if set(spop.loc[spop.historical_slide_reportable, "site"]) != {"EJ", "KK", "YL"}:
        raise EvidenceClosureError("historical SPOP reportable-site mismatch")
    availability = {
        "image_description_available": 300, "appmag_available": 300, "mpp_available": 300,
        "scanscope_id_available": 280, "icc_profile_available": 280,
        "xresolution_tag_available": 0, "make_tag_available": 0,
        "model_tag_available": 0, "software_tag_available": 0,
        "explicit_stain_field_available": 0,
    }
    for column, expected in availability.items():
        if int(metadata[column].sum()) != expected:
            raise EvidenceClosureError(f"header availability mismatch for {column}")
    if not metadata.stain_metadata_status.eq("not_available").all():
        raise EvidenceClosureError("stain metadata must remain not_available")
    expected_spop = {
        "CH": (np.nan, np.nan, np.nan, 0, 2000),
        "EJ": (0.6126373626373626, 0.4182375643224699, 0.7982894736842103, 2000, 0),
        "G9": (0.7, 0.4230769230769231, 0.9230769230769232, 1766, 234),
        "HC": (0.7575757575757573, 0.5, 0.9393939393939392, 1908, 92),
        "KK": (0.5733333333333333, 0.2729166666666667, 0.8401944444444445, 1998, 2),
        "YL": (0.625, 0.2823529411764705, 1.0, 1969, 31),
    }
    indexed = spop.set_index("site")
    for site, (auc, ci_low, ci_high, valid, undefined) in expected_spop.items():
        row = indexed.loc[site]
        if (int(row.n_bootstrap_valid), int(row.n_bootstrap_undefined)) != (valid, undefined):
            raise EvidenceClosureError(f"bootstrap accounting mismatch for {site}")
        actual = np.asarray([row.patient_auroc, row.patient_ci_low, row.patient_ci_high], dtype=float)
        expected = np.asarray([auc, ci_low, ci_high], dtype=float)
        if not np.allclose(actual, expected, rtol=0, atol=1e-15, equal_nan=True):
            raise EvidenceClosureError(f"SPOP audited value mismatch for {site}")
    if not np.allclose(
        power.minimum_detectable_auroc,
        [0.6613666946979635, 0.6847459836958563], rtol=0, atol=1e-14,
    ):
        raise EvidenceClosureError("MDE values do not reproduce frozen specification")


def run_analysis(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Path]:
    """Run R5 from frozen inputs, validate a full staging set, then publish it."""
    started = time.perf_counter()
    root = Path(root).absolute()
    output_dir = root / "models" if output_dir is None else Path(output_dir).absolute()
    expected_python = (root / ".venv/bin/python").absolute()
    if Path(sys.executable).absolute() != expected_python:
        raise EvidenceClosureError(f"run with mandated controller: {expected_python}")
    input_paths, input_roles = _input_contract(root)
    input_before = snapshot_files(input_paths, root)

    X, slides, gdc = load_cohort(root)
    forest = pd.read_csv(root / "models/ar_site_forest_summary.csv")
    if list(forest.columns) != ["site", "n_slides", "n_patients", "rho", "ci_lo", "ci_hi", "kind"]:
        raise EvidenceClosureError("unexpected frozen AR forest schema")
    slide_paths = [root / "opendataset/TCGA-PRAD/slides" / name for name in slides.file_name]
    slide_stats_before = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in slide_paths}

    ar = build_ar_site_characteristics(slides, forest)
    metadata = build_metadata_availability(root, slides, gdc)
    predictions = fit_spop_site_predictions(X, slides)
    spop = build_spop_site_summary(slides, predictions)
    power = build_power_summary()
    _validate_real_outputs(ar, metadata, spop, power, predictions)

    slide_stats_after = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in slide_paths}
    if slide_stats_before != slide_stats_after:
        raise EvidenceClosureError("WSI size/mtime changed during header-only scan")
    input_after = snapshot_files(input_paths, root)
    assert_snapshots_unchanged(input_before, input_after)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    with tempfile.TemporaryDirectory(prefix=".ar-spop-stage-", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        frames = {
            AR_NAME: ar, METADATA_NAME: metadata, SPOP_NAME: spop,
            POWER_NAME: power, PREDICTIONS_NAME: predictions,
        }
        for name, frame in frames.items():
            _write_csv(frame, stage / name)
        config = {
            "analysis_id": "R5_ar_spop_evidence_closure",
            "analysis_role": "exploratory internal site transportability and power-description audit",
            "bootstrap": {"unit": "patient_row", "draws": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED,
                          "interval": "percentile_2.5_97.5", "undefined_draws": "retained_and_counted"},
            "ar": {"descriptors": "patient_level", "quantile_interpolation": "linear",
                   "sd_ddof": 1, "stored_loo_effect_unit": "slide",
                   "stored_loo_bootstrap_unit": "patient_cluster"},
            "spop": {"site_model": "StandardScaler+LogisticRegression(C=1.0,class_weight=balanced,max_iter=2000)",
                     "large_site_min_slides": 20, "historical_slide_min_per_class": 5,
                     "patient_aggregation": "mean_slide_probability"},
            "mde": {"n_positive": 29, "n_negative": 244, "alpha": 0.05,
                    "powers": [0.8, 0.9], "method": "Hanley-McNeil_fixed_score_normal_approximation"},
            "slide_io": {"scope": "page0_TIFF_headers_only", "pixel_arrays_read": False,
                         "full_file_hashes": "not_computed_large_input_247GiB_collection",
                         "stain_policy": "not_available_never_inferred",
                         "scanscope_policy": "raw_header_identifier_not_validated_scanner_model",
                         "scanner_site_interpretation": (
                             "Raw ScanScope identifiers are confounded with tissue-source site; no causal "
                             "scanner, site, or stain attribution is supported."
                         )},
            "runtime": {"entry": ".venv/bin/python", "device": "CPU", "versions": _runtime_versions()},
            "input_sha256": {snapshot.artifact_path: snapshot.sha256
                             for snapshot in sorted(input_before.values(), key=lambda item: item.artifact_path)},
            "source_unchanged_assertion": True,
            "upstream_lineage_limitation": (
                "The current 300-slide CONCH cache overwrote an older 266-slide cache without a matching "
                "generation log/config; current cache hashes are frozen here but upstream embedding-run "
                "lineage remains unresolved."
            ),
            "outputs": list(OUTPUT_NAMES) + [MANIFEST_NAME],
            "volatile_manifest_fields": ["generated_at_utc", "elapsed_seconds"],
        }
        _write_json(config, stage / CONFIG_NAME)
        staged_outputs = [stage / name for name in OUTPUT_NAMES]
        manifest = build_manifest(
            root, input_before, input_after, input_roles, metadata, staged_outputs,
            stage / MANIFEST_NAME, generated_at, time.perf_counter() - started,
        )
        _write_csv(manifest, stage / MANIFEST_NAME)
        if manifest.loc[manifest.artifact_path.eq(MANIFEST_NAME), "sha256_after"].iloc[0] != "":
            raise EvidenceClosureError("manifest contains a self hash")
        output_dir.mkdir(parents=True, exist_ok=True)
        installed = {}
        for name in (*OUTPUT_NAMES, MANIFEST_NAME):
            destination = output_dir / name
            os.replace(stage / name, destination)
            installed[name] = destination
    return installed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = parse_args(argv)
    outputs = run_analysis(arguments.root, arguments.output_dir)
    summary = {
        "status": "complete", "ar_sites": 22, "metadata_slides": 300,
        "spop_sites": 22, "outputs": {name: str(path) for name, path in outputs.items()},
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
