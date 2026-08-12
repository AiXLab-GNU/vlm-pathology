"""R4 common-cohort, same-draw paired survival analysis for marker 7.

The reconstructed endpoint and official TCGA-CDR PFI are separate endpoint namespaces.
All models use the frozen marker-7 patient folds, and every bootstrap replicate is retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, NamedTuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = Path(__file__).resolve()
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 0
MIN_TRAIN_EVENTS = 5
MAX_UNDEFINED_FRACTION = 0.01
COMMON_N = 153
RECONSTRUCTED_EVENTS = 30
OFFICIAL_PFI_EVENTS = 15
COMMON_PATIENT_ID_SHA256 = "92a235307c549ecf329eb2450eb31833b4adbb80d130b61c18f32617049b7976"

SUMMARY_NAME = "marker7_survival_common_cohort_summary.csv"
DELTAS_NAME = "marker7_survival_paired_deltas.csv"
BOOTSTRAP_NAME = "marker7_survival_bootstrap_replicates.csv"
OOF_NAME = "marker7_survival_oof_survival_predictions.csv"
CONFIG_NAME = "marker7_survival_paired_run_config.json"
MANIFEST_NAME = "marker7_survival_paired_run_manifest.csv"
DIAGNOSTICS_NAME = "marker7_survival_fold_diagnostics.csv"
OUTPUT_NAMES = (
    SUMMARY_NAME,
    DELTAS_NAME,
    BOOTSTRAP_NAME,
    OOF_NAME,
    CONFIG_NAME,
    DIAGNOSTICS_NAME,
    MANIFEST_NAME,
)


class R4IntegrityError(RuntimeError):
    """Raised when an R4 design, lineage, or numerical invariant fails."""


class ModelSpec(NamedTuple):
    model_id: str
    analysis_family: str
    engine: str
    covariates: tuple[str, ...]


class ContrastSpec(NamedTuple):
    contrast_id: str
    model_a: str
    model_b: str
    estimand: str


def model_registry() -> tuple[ModelSpec, ...]:
    full = ("gleason_sum", "age", "t_stage", "psa", "margin_positive")
    return (
        ModelSpec("N_IMAGE", "nested", "lifelines_unpenalized", ("marker7_risk",)),
        ModelSpec("N_GRADE_CLINICAL", "nested", "lifelines_unpenalized", ("gleason_sum",)),
        ModelSpec(
            "N_GRADE_COMBINED", "nested", "lifelines_unpenalized",
            ("gleason_sum", "marker7_risk"),
        ),
        ModelSpec("N_FULL_CLINICAL", "nested", "lifelines_unpenalized", full),
        ModelSpec("N_FULL_COMBINED", "nested", "lifelines_unpenalized", full + ("marker7_risk",)),
        ModelSpec("H_M0", "hierarchy", "sksurv_coxph_alpha_1", ("gleason_sum",)),
        ModelSpec("H_M1", "hierarchy", "sksurv_coxph_alpha_1", ("gleason_sum", "age")),
        ModelSpec(
            "H_M2", "hierarchy", "sksurv_coxph_alpha_1",
            ("gleason_sum", "psa", "t_stage"),
        ),
        ModelSpec(
            "H_M3", "hierarchy", "sksurv_coxph_alpha_1",
            ("gleason_sum", "psa", "t_stage", "margin_positive"),
        ),
        ModelSpec(
            "H_M4", "hierarchy", "sksurv_coxph_alpha_1",
            ("gleason_sum", "psa", "t_stage", "margin_positive", "site"),
        ),
        ModelSpec(
            "H_M5", "hierarchy", "sksurv_coxph_alpha_1",
            ("gleason_sum", "psa", "t_stage", "margin_positive", "site", "marker7_risk"),
        ),
    )


def contrast_registry() -> tuple[ContrastSpec, ...]:
    return (
        ContrastSpec("IMAGE_VS_GRADE", "N_GRADE_CLINICAL", "N_IMAGE", "descriptive"),
        ContrastSpec(
            "GRADE_COMBINED_VS_GRADE", "N_GRADE_CLINICAL", "N_GRADE_COMBINED", "incremental"
        ),
        ContrastSpec("IMAGE_VS_FULL", "N_FULL_CLINICAL", "N_IMAGE", "descriptive"),
        ContrastSpec(
            "FULL_COMBINED_VS_FULL", "N_FULL_CLINICAL", "N_FULL_COMBINED", "incremental"
        ),
        ContrastSpec("M5_VS_M4", "H_M4", "H_M5", "incremental"),
    )


def time_grid() -> np.ndarray:
    return np.arange(5, 51, dtype=float) / 10.0


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise R4IntegrityError(f"{label} missing columns: {missing}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def id_list_sha256(ids: Iterable[str]) -> str:
    payload = "\n".join(map(str, ids)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _numeric_equal(a: pd.Series, b: pd.Series, *, atol: float = 1e-12) -> bool:
    return bool(np.allclose(
        pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce"),
        rtol=0.0, atol=atol, equal_nan=False,
    ))


def reconcile_common_cohort(
    nested: pd.DataFrame,
    hierarchy: pd.DataFrame,
    frozen_folds: pd.DataFrame,
    endpoint: pd.DataFrame,
    *,
    expected_n: int = COMMON_N,
    expected_events: int = RECONSTRUCTED_EVENTS,
    expected_id_hash: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Reconcile the fixed complete-case patients and attach only canonical frozen folds."""
    required_features = [
        "case_id", "gleason_sum", "marker7_risk", "event", "follow_up_y", "age",
        "t_stage", "psa", "margin_positive", "fold",
    ]
    _require_columns(nested, required_features, "nested predictions")
    selected = nested.copy()
    if "marker" in selected:
        selected = selected.loc[selected["marker"].eq("marker7_recurrence")]
    if "analysis" in selected:
        selected = selected.loc[selected["analysis"].eq("fully_adjusted")]
    if "scope" in selected:
        selected = selected.loc[selected["scope"].eq("patient")]
    if selected["case_id"].duplicated().any():
        raise R4IntegrityError("duplicate patient in fully-adjusted nested predictions")
    if len(selected) != expected_n:
        raise R4IntegrityError(f"common cohort count changed: {len(selected)} != {expected_n}")

    _require_columns(hierarchy, ["case_id", "model", "event", "follow_up_y", "fold"],
                     "hierarchy predictions")
    common_ids = set(selected["case_id"].astype(str))
    hierarchy_parts: dict[str, pd.DataFrame] = {}
    for model in ("M3", "M4", "M5"):
        part = hierarchy.loc[hierarchy["model"].eq(model)].copy()
        if part["case_id"].duplicated().any() or set(part["case_id"].astype(str)) != common_ids:
            raise R4IntegrityError("M3/M4/M5 patient sets do not reconcile with the common patient set")
        hierarchy_parts[model] = part.set_index("case_id").sort_index()
    for model, part in hierarchy_parts.items():
        aligned = selected.set_index("case_id").sort_index()
        if not _numeric_equal(aligned["event"], part["event"]) or not _numeric_equal(
            aligned["follow_up_y"], part["follow_up_y"]
        ):
            raise R4IntegrityError(f"{model} endpoint differs from the nested common cohort")

    _require_columns(endpoint, ["case_id", "event", "follow_up_y"], "reconstructed endpoint")
    if endpoint["case_id"].duplicated().any():
        raise R4IntegrityError("duplicate patient in reconstructed endpoint")
    endpoint_common = endpoint.loc[endpoint["case_id"].astype(str).isin(common_ids)].set_index(
        "case_id"
    ).sort_index()
    aligned = selected.set_index("case_id").sort_index()
    if len(endpoint_common) != expected_n or not _numeric_equal(aligned["event"], endpoint_common["event"]):
        raise R4IntegrityError("reconstructed endpoint event mismatch")
    if not _numeric_equal(aligned["follow_up_y"], endpoint_common["follow_up_y"]):
        raise R4IntegrityError("reconstructed endpoint time mismatch")

    _require_columns(frozen_folds, ["marker", "case_id", "fold"], "frozen folds")
    marker_folds = frozen_folds.loc[frozen_folds["marker"].eq("marker7")].copy()
    if marker_folds["case_id"].duplicated().any():
        raise R4IntegrityError("duplicate marker7 frozen fold assignment")
    marker_folds = marker_folds.loc[marker_folds["case_id"].astype(str).isin(common_ids)]
    if len(marker_folds) != expected_n or set(marker_folds["case_id"].astype(str)) != common_ids:
        raise R4IntegrityError("frozen fold patient set differs from common cohort")
    fold_numeric = pd.to_numeric(marker_folds["fold"], errors="coerce")
    if fold_numeric.isna().any() or not np.equal(fold_numeric % 1, 0).all():
        raise R4IntegrityError("frozen folds are not integers")
    marker_folds["fold"] = fold_numeric.astype(int)
    if set(marker_folds["fold"]) != set(range(5)):
        raise R4IntegrityError("common cohort must retain all five canonical folds")

    legacy = hierarchy_parts["M4"]["fold"].astype(int)
    canonical = marker_folds.set_index("case_id")["fold"].sort_index()
    legacy_agreement = int((legacy == canonical).sum())
    common = selected.drop(columns=["fold"]).merge(
        marker_folds[["case_id", "fold"]], on="case_id", how="inner", validate="one_to_one"
    )
    common["case_id"] = common["case_id"].astype(str)
    common["site"] = common["case_id"].str.split("-").str[1]
    common = common.sort_values("case_id").reset_index(drop=True)
    if common["site"].isna().any() or common["site"].eq("").any():
        raise R4IntegrityError("site could not be derived from a TCGA case ID")
    finite_columns = [
        "gleason_sum", "marker7_risk", "event", "follow_up_y", "age", "t_stage", "psa",
        "margin_positive",
    ]
    numeric = common[finite_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise R4IntegrityError("common cohort contains missing or non-finite values")
    common[finite_columns] = numeric
    if not set(common["event"].astype(int)).issubset({0, 1}):
        raise R4IntegrityError("event must be binary")
    if (common["follow_up_y"] <= 0).any():
        raise R4IntegrityError("follow-up must be positive")
    if int(common["event"].sum()) != expected_events:
        raise R4IntegrityError(
            f"common endpoint event count changed: {int(common['event'].sum())} != {expected_events}"
        )
    patient_hash = id_list_sha256(common["case_id"])
    if expected_id_hash is not None and patient_hash != expected_id_hash:
        raise R4IntegrityError("common patient membership hash changed")
    diagnostics = {
        "n_patients": len(common),
        "n_events": int(common["event"].sum()),
        "common_patient_id_sha256": patient_hash,
        "legacy_fold_agreement_n": legacy_agreement,
        "canonical_fold_counts": common["fold"].value_counts().sort_index().to_dict(),
    }
    return common, diagnostics


def load_reconstructed_common_cohort(root: Path = ROOT) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(root)
    return reconcile_common_cohort(
        pd.read_csv(root / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_predictions.csv"),
        pd.read_csv(root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_predictions.csv"),
        pd.read_csv(root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv"),
        pd.read_csv(root / "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv"),
        expected_n=COMMON_N,
        expected_events=RECONSTRUCTED_EVENTS,
        expected_id_hash=COMMON_PATIENT_ID_SHA256,
    )


def normalize_endpoint(
    common: pd.DataFrame,
    source: pd.DataFrame,
    *,
    endpoint_id: str,
    event_col: str,
    time_col: str,
    expected_events: int,
) -> pd.DataFrame:
    _require_columns(common, ["case_id"], "common cohort")
    _require_columns(source, ["case_id", event_col, time_col], endpoint_id)
    source = source[["case_id", event_col, time_col]].copy()
    if source["case_id"].duplicated().any():
        consistency = source.groupby("case_id")[[event_col, time_col]].nunique(dropna=False)
        if (consistency > 1).any().any():
            raise R4IntegrityError(f"{endpoint_id} has conflicting duplicate patients")
        source = source.drop_duplicates("case_id")
    base = common.drop(columns=["event", "follow_up_y", "time_years", "endpoint_id"],
                       errors="ignore").copy()
    merged = base.merge(source, on="case_id", how="left", validate="one_to_one")
    merged = merged.rename(columns={event_col: "event", time_col: "time_years"})
    values = merged[["event", "time_years"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise R4IntegrityError(f"{endpoint_id} is incomplete for the fixed common cohort")
    merged[["event", "time_years"]] = values
    if not set(merged["event"].astype(int)).issubset({0, 1}):
        raise R4IntegrityError(f"{endpoint_id} event is not binary")
    if (merged["time_years"] <= 0).any():
        raise R4IntegrityError(f"{endpoint_id} contains non-positive follow-up")
    if int(merged["event"].sum()) != expected_events:
        raise R4IntegrityError(
            f"{endpoint_id} event count changed: {int(merged['event'].sum())} != {expected_events}"
        )
    merged["event"] = merged["event"].astype(int)
    merged["endpoint_id"] = endpoint_id
    return merged.sort_values("case_id").reset_index(drop=True)


def _structured(event: np.ndarray, follow_up: np.ndarray) -> np.ndarray:
    return np.array(
        list(zip(np.asarray(event, dtype=bool), np.asarray(follow_up, dtype=float))),
        dtype=[("event", bool), ("time", float)],
    )


def validate_survival_probabilities(probabilities: np.ndarray, *, atol: float = 1e-12) -> None:
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 2 or probabilities.shape[1] == 0:
        raise R4IntegrityError("survival probabilities must be a non-empty 2D matrix")
    if not np.isfinite(probabilities).all():
        raise R4IntegrityError("survival probability is non-finite")
    if (probabilities < -atol).any() or (probabilities > 1.0 + atol).any():
        raise R4IntegrityError("survival probability lies outside [0, 1]")
    if (np.diff(probabilities, axis=1) > atol).any():
        raise R4IntegrityError("survival probability increases over time")


def _fit_censoring_km(event: np.ndarray, follow_up: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Reverse Kaplan--Meier with disease-event ties removed before censoring."""
    event = np.asarray(event, dtype=bool)
    follow_up = np.asarray(follow_up, dtype=float)
    if len(event) == 0 or len(event) != len(follow_up) or not np.isfinite(follow_up).all():
        raise R4IntegrityError("invalid censoring-KM training outcome")
    unique_times = np.unique(follow_up)
    probabilities = np.empty(len(unique_times), dtype=float)
    survival = 1.0
    for index, value in enumerate(unique_times):
        at_time = follow_up == value
        n_disease_events = int(np.sum(at_time & event))
        n_censored = int(np.sum(at_time & ~event))
        # Reverse-KM tie convention: disease events at this time leave the risk set
        # before censoring events contribute to the censoring hazard.
        n_at_risk = int(np.sum(follow_up >= value)) - n_disease_events
        if n_censored:
            if n_at_risk <= 0 or n_censored > n_at_risk:
                raise R4IntegrityError("censoring KM has an invalid risk set")
            survival *= 1.0 - n_censored / n_at_risk
        probabilities[index] = survival
    return unique_times, probabilities


def _predict_censoring_km(
    unique_times: np.ndarray, probabilities: np.ndarray, query: np.ndarray, *, left_limit: bool
) -> np.ndarray:
    query = np.asarray(query, dtype=float)
    if (query > unique_times[-1]).any() and probabilities[-1] > 0:
        raise R4IntegrityError("outer training fold lacks censoring-KM time support")
    side = "left" if left_limit else "right"
    indices = np.searchsorted(unique_times, query, side=side) - 1
    result = np.ones(len(query), dtype=float)
    within = indices >= 0
    result[within] = probabilities[np.minimum(indices[within], len(probabilities) - 1)]
    beyond = query > unique_times[-1]
    result[beyond] = 0.0
    return result


def ipcw_brier_contributions(
    train_event: np.ndarray,
    train_time: np.ndarray,
    test_event: np.ndarray,
    test_time: np.ndarray,
    survival_probability: np.ndarray,
    times: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    """Fold-contained Graf Brier contributions using G(T-) for observed events."""
    times = np.asarray(times, dtype=float)
    survival_probability = np.asarray(survival_probability, dtype=float)
    test_event = np.asarray(test_event, dtype=bool)
    test_time = np.asarray(test_time, dtype=float)
    train_event = np.asarray(train_event, dtype=bool)
    train_time = np.asarray(train_time, dtype=float)
    if len(times) == 0 or not np.all(np.diff(times) > 0):
        raise R4IntegrityError("Brier time grid must be strictly increasing")
    if survival_probability.shape != (len(test_time), len(times)):
        raise R4IntegrityError("survival probability shape does not match patients/time grid")
    validate_survival_probabilities(survival_probability)
    if int(train_event.sum()) < MIN_TRAIN_EVENTS:
        raise R4IntegrityError("outer training fold has too few events")
    censor_times, censor_probabilities = _fit_censoring_km(train_event, train_time)
    g_grid = _predict_censoring_km(
        censor_times, censor_probabilities, times, left_limit=False
    )
    if not np.isfinite(g_grid).all() or (g_grid <= 0).any():
        raise R4IntegrityError("outer training censoring survival is undefined or zero on grid")

    g_event_left = np.ones(len(test_time), dtype=float)
    relevant_event = test_event & (test_time <= times[-1])
    if relevant_event.any():
        g_event_left[relevant_event] = _predict_censoring_km(
            censor_times, censor_probabilities, test_time[relevant_event], left_limit=True
        )
    if not np.isfinite(g_event_left[relevant_event]).all() or (
        g_event_left[relevant_event] <= 0
    ).any():
        raise R4IntegrityError("G(T-) is undefined or zero for an observed event")

    contributions = np.zeros_like(survival_probability, dtype=float)
    for column, horizon in enumerate(times):
        is_event = test_event & (test_time <= horizon)
        is_at_risk = test_time > horizon
        contributions[:, column] = (
            np.square(survival_probability[:, column]) * is_event / g_event_left
            + np.square(1.0 - survival_probability[:, column]) * is_at_risk / g_grid[column]
        )
    if not np.isfinite(contributions).all():
        raise R4IntegrityError("IPCW Brier contribution is non-finite")
    diagnostics = {
        "g_at_grid_min": float(g_grid.min()),
        "g_at_grid_max": float(g_grid.max()),
        "g_event_left_min": float(g_event_left[relevant_event].min()) if relevant_event.any() else 1.0,
    }
    return contributions, diagnostics


def make_bootstrap_draws(
    case_ids: np.ndarray | pd.Series | list[str], *, n_boot: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED
) -> tuple[np.ndarray, pd.DataFrame]:
    case_ids = np.asarray(case_ids, dtype=str)
    if len(case_ids) == 0 or len(np.unique(case_ids)) != len(case_ids):
        raise R4IntegrityError("bootstrap input must contain unique patients")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(case_ids), size=(n_boot, len(case_ids)), dtype=np.int64)
    rows = []
    for replicate_id, indices in enumerate(draws):
        rows.append({
            "replicate_id": replicate_id,
            "sample_index_sha256": hashlib.sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest(),
            "n_sampled_patients": len(indices),
            "n_unique_patients": len(np.unique(indices)),
        })
    return draws, pd.DataFrame(rows)


def _harrell_c_index(event: np.ndarray, time_value: np.ndarray, risk: np.ndarray) -> float:
    event = np.asarray(event, dtype=bool)
    time_value = np.asarray(time_value, dtype=float)
    risk = np.asarray(risk, dtype=float)
    if not (np.isfinite(time_value).all() and np.isfinite(risk).all()):
        raise ValueError("non-finite concordance input")
    try:
        from lifelines.utils import concordance_index

        return float(concordance_index(time_value, -risk, event))
    except ModuleNotFoundError:
        # The lightweight controller environment intentionally omits lifelines;
        # unit fixtures use this exact fallback while the pinned worker uses lifelines.
        pass
    concordant = 0.0
    comparable = 0
    for left in range(len(event) - 1):
        for right in range(left + 1, len(event)):
            if time_value[left] < time_value[right] and event[left]:
                early, late = left, right
            elif time_value[right] < time_value[left] and event[right]:
                early, late = right, left
            elif time_value[left] == time_value[right] and event[left] != event[right]:
                early, late = (left, right) if event[left] else (right, left)
            else:
                continue
            comparable += 1
            if risk[early] > risk[late]:
                concordant += 1.0
            elif risk[early] == risk[late]:
                concordant += 0.5
    if comparable == 0:
        raise ZeroDivisionError("no comparable pairs")
    return concordant / comparable


def bootstrap_model_metrics(
    patients: pd.DataFrame,
    draws: np.ndarray,
    draw_metadata: pd.DataFrame,
    *,
    endpoint_id: str,
) -> pd.DataFrame:
    _require_columns(
        patients,
        ["case_id", "event", "time_years", "model_id", "linear_predictor", "ibs_contribution"],
        "patient metric frame",
    )
    if len(draws) != len(draw_metadata) or draw_metadata["replicate_id"].tolist() != list(
        range(len(draws))
    ):
        raise R4IntegrityError("bootstrap draw IDs are missing or compressed")
    rows: list[dict[str, Any]] = []
    for model_id, model_frame in patients.groupby("model_id", sort=False):
        model_frame = model_frame.sort_values("case_id").reset_index(drop=True)
        if len(model_frame) != draws.shape[1]:
            raise R4IntegrityError("model patient set does not match bootstrap draw width")
        event = model_frame["event"].to_numpy(dtype=bool)
        follow_up = model_frame["time_years"].to_numpy(dtype=float)
        risk = model_frame["linear_predictor"].to_numpy(dtype=float)
        ibs_patient = model_frame["ibs_contribution"].to_numpy(dtype=float)
        for meta, indices in zip(draw_metadata.itertuples(index=False), draws):
            common = {
                "record_type": "model",
                "endpoint_id": endpoint_id,
                "replicate_id": int(meta.replicate_id),
                "sample_index_sha256": str(meta.sample_index_sha256),
                "n_sampled_patients": int(meta.n_sampled_patients),
                "n_unique_patients": int(meta.n_unique_patients),
                "n_events": int(event[indices].sum()),
                "model_id": str(model_id),
                "contrast_id": "",
                "model_a": "",
                "model_b": "",
                "raw_delta_b_minus_a": np.nan,
            }
            try:
                c_value = _harrell_c_index(event[indices], follow_up[indices], risk[indices])
                c_valid, c_reason = True, ""
            except (ValueError, ZeroDivisionError):
                c_value, c_valid, c_reason = np.nan, False, "no_comparable_pairs"
            rows.append({
                **common, "metric": "c_index", "estimate": c_value,
                "valid": c_valid, "failure_reason": c_reason,
            })
            ibs_value = float(np.mean(ibs_patient[indices]))
            ibs_valid = bool(np.isfinite(ibs_value))
            rows.append({
                **common, "metric": "ibs_0.5_5y", "estimate": ibs_value if ibs_valid else np.nan,
                "valid": ibs_valid, "failure_reason": "" if ibs_valid else "nonfinite_ibs",
            })
    return pd.DataFrame(rows)


def paired_replicate_deltas(
    replicates: pd.DataFrame, model_a: str, model_b: str, contrast_id: str
) -> pd.DataFrame:
    keys = ["endpoint_id", "replicate_id", "metric"]
    a = replicates.loc[replicates["model_id"].eq(model_a)].copy()
    b = replicates.loc[replicates["model_id"].eq(model_b)].copy()
    if a.duplicated(keys).any() or b.duplicated(keys).any() or set(map(tuple, a[keys].to_numpy())) != set(
        map(tuple, b[keys].to_numpy())
    ):
        raise R4IntegrityError(f"{contrast_id} model replicate keys do not pair")
    paired = a.merge(b, on=keys, how="inner", suffixes=("_a", "_b"), validate="one_to_one")
    if not (paired["sample_index_sha256_a"] == paired["sample_index_sha256_b"]).all():
        raise R4IntegrityError(f"{contrast_id} draw identity differs between models")
    valid = paired["valid_a"].astype(bool) & paired["valid_b"].astype(bool)
    raw = paired["estimate_b"] - paired["estimate_a"]
    improvement = np.where(paired["metric"].eq("c_index"), raw, -raw)
    raw = raw.where(valid, np.nan)
    improvement = pd.Series(improvement, index=paired.index).where(valid, np.nan)
    out = pd.DataFrame({
        "record_type": "contrast",
        "endpoint_id": paired["endpoint_id"],
        "replicate_id": paired["replicate_id"].astype(int),
        "sample_index_sha256": paired["sample_index_sha256_a"],
        "n_sampled_patients": paired["n_sampled_patients_a"].astype(int),
        "n_unique_patients": paired["n_unique_patients_a"].astype(int),
        "n_events": paired["n_events_a"].astype(int),
        "model_id": "",
        "contrast_id": contrast_id,
        "model_a": model_a,
        "model_b": model_b,
        "metric": paired["metric"],
        "estimate": improvement,
        "raw_delta_b_minus_a": raw,
        "improvement_delta": improvement,
        "valid": valid,
        "failure_reason": np.where(
            valid, "", np.where(~paired["valid_a"].astype(bool), paired["failure_reason_a"], paired["failure_reason_b"])
        ),
    })
    return out.sort_values(["endpoint_id", "replicate_id", "metric"]).reset_index(drop=True)


def _fit_one_fold(
    spec: ModelSpec, train: pd.DataFrame, test: pd.DataFrame, times: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    warning_messages: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if spec.engine == "lifelines_unpenalized":
            from lifelines import CoxPHFitter

            scaler = StandardScaler().fit(train[list(spec.covariates)])
            train_x = pd.DataFrame(
                scaler.transform(train[list(spec.covariates)]), columns=spec.covariates
            )
            test_x = pd.DataFrame(
                scaler.transform(test[list(spec.covariates)]), columns=spec.covariates
            )
            fit_frame = train_x.copy()
            fit_frame["time"] = train["time_years"].to_numpy()
            fit_frame["event"] = train["event"].to_numpy()
            model = CoxPHFitter(
                baseline_estimation_method="breslow", penalizer=0.0, l1_ratio=0.0
            ).fit(fit_frame, duration_col="time", event_col="event", show_progress=False)
            coefficient = model.params_.to_numpy(dtype=float)
            risk = model.predict_log_partial_hazard(test_x).to_numpy(dtype=float)
            survival = model.predict_survival_function(test_x, times=times).to_numpy(dtype=float).T
            feature_names = list(spec.covariates)
        elif spec.engine == "sksurv_coxph_alpha_1":
            from sksurv.linear_model import CoxPHSurvivalAnalysis

            categorical = [name for name in spec.covariates if name == "site"]
            numeric = [name for name in spec.covariates if name != "site"]
            transformers: list[tuple[str, Any, list[str]]] = [
                ("numeric", StandardScaler(), numeric)
            ]
            if categorical:
                transformers.append((
                    "site", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical
                ))
            preprocess = ColumnTransformer(transformers)
            train_x = preprocess.fit_transform(train[list(spec.covariates)])
            test_x = preprocess.transform(test[list(spec.covariates)])
            model = CoxPHSurvivalAnalysis(
                alpha=1.0, ties="breslow", n_iter=100, tol=1e-9, verbose=0
            ).fit(train_x, _structured(train["event"], train["time_years"]))
            coefficient = np.asarray(model.coef_, dtype=float)
            risk = np.asarray(model.predict(test_x), dtype=float)
            functions = model.predict_survival_function(test_x)
            survival = np.asarray([[function(value) for value in times] for function in functions])
            feature_names = list(preprocess.get_feature_names_out())
        else:  # pragma: no cover - registry validation prevents this branch
            raise R4IntegrityError(f"unknown model engine: {spec.engine}")
        warning_messages = [f"{type(item.message).__name__}:{item.message}" for item in caught]
    if any("Convergence" in message for message in warning_messages):
        raise R4IntegrityError(f"{spec.model_id} emitted a convergence warning")
    if not np.isfinite(coefficient).all() or not np.isfinite(risk).all():
        raise R4IntegrityError(f"{spec.model_id} produced a non-finite coefficient or risk")
    validate_survival_probabilities(survival)
    return risk, survival, coefficient, feature_names


def fit_oof_models(endpoint: pd.DataFrame, times: np.ndarray | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    times = time_grid() if times is None else np.asarray(times, dtype=float)
    _require_columns(
        endpoint,
        ["endpoint_id", "case_id", "event", "time_years", "fold", "site", "gleason_sum",
         "marker7_risk", "age", "t_stage", "psa", "margin_positive"],
        "endpoint cohort",
    )
    if endpoint["case_id"].duplicated().any() or len(endpoint) != COMMON_N:
        raise R4IntegrityError("endpoint cohort is not the fixed 153 unique patients")
    endpoint_ids = endpoint["endpoint_id"].unique()
    if len(endpoint_ids) != 1:
        raise R4IntegrityError("one OOF fit call must contain exactly one endpoint")
    endpoint_id = str(endpoint_ids[0])
    oof_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    for spec in model_registry():
        seen: set[str] = set()
        for fold in range(5):
            train = endpoint.loc[endpoint["fold"].ne(fold)].reset_index(drop=True)
            test = endpoint.loc[endpoint["fold"].eq(fold)].reset_index(drop=True)
            if set(train["case_id"]) & set(test["case_id"]):
                raise R4IntegrityError("outer-fold patient leakage")
            if len(test) == 0 or int(train["event"].sum()) < MIN_TRAIN_EVENTS:
                raise R4IntegrityError("outer fold is empty or has too few training events")
            risk, survival, coefficients, feature_names = _fit_one_fold(spec, train, test, times)
            contributions, ipc_diag = ipcw_brier_contributions(
                train["event"].to_numpy(), train["time_years"].to_numpy(),
                test["event"].to_numpy(), test["time_years"].to_numpy(), survival, times,
            )
            for local_index, patient in enumerate(test.itertuples(index=False)):
                if patient.case_id in seen:
                    raise R4IntegrityError("patient received more than one OOF prediction")
                seen.add(patient.case_id)
                for time_index, horizon in enumerate(times):
                    oof_rows.append({
                        "endpoint_id": endpoint_id,
                        "case_id": patient.case_id,
                        "fold": fold,
                        "model_id": spec.model_id,
                        "analysis_family": spec.analysis_family,
                        "model_engine": spec.engine,
                        "covariates": "+".join(spec.covariates),
                        "event": int(patient.event),
                        "time_years": float(patient.time_years),
                        "evaluation_time_years": float(horizon),
                        "linear_predictor": float(risk[local_index]),
                        "survival_probability": float(survival[local_index, time_index]),
                        "ipcw_brier_contribution": float(contributions[local_index, time_index]),
                    })
            diagnostic_rows.append({
                "endpoint_id": endpoint_id,
                "model_id": spec.model_id,
                "analysis_family": spec.analysis_family,
                "model_engine": spec.engine,
                "covariates": "+".join(spec.covariates),
                "fold": fold,
                "n_train": len(train),
                "n_train_events": int(train["event"].sum()),
                "n_test": len(test),
                "n_test_events": int(test["event"].sum()),
                "n_encoded_features": len(feature_names),
                "max_abs_coefficient": float(np.max(np.abs(coefficients))),
                "g_at_grid_min": ipc_diag["g_at_grid_min"],
                "g_event_left_min": ipc_diag["g_event_left_min"],
                "survival_probability_min": float(survival.min()),
                "survival_probability_max": float(survival.max()),
                "status": "ok",
            })
        if seen != set(endpoint["case_id"]):
            raise R4IntegrityError(f"{spec.model_id} OOF patient coverage mismatch")
    return pd.DataFrame(oof_rows), pd.DataFrame(diagnostic_rows)


def patient_metric_frame(oof: pd.DataFrame, times: np.ndarray | None = None) -> pd.DataFrame:
    times = time_grid() if times is None else np.asarray(times, dtype=float)
    rows: list[dict[str, Any]] = []
    keys = ["endpoint_id", "model_id", "case_id"]
    for (endpoint_id, model_id, case_id), part in oof.groupby(keys, sort=False):
        part = part.sort_values("evaluation_time_years")
        np.testing.assert_allclose(part["evaluation_time_years"].to_numpy(), times, rtol=0, atol=1e-12)
        contribution = part["ipcw_brier_contribution"].to_numpy(dtype=float)
        ibs_patient = float(np.trapezoid(contribution, times) / (times[-1] - times[0]))
        rows.append({
            "endpoint_id": endpoint_id,
            "model_id": model_id,
            "case_id": case_id,
            "event": int(part["event"].iloc[0]),
            "time_years": float(part["time_years"].iloc[0]),
            "linear_predictor": float(part["linear_predictor"].iloc[0]),
            "ibs_contribution": ibs_patient,
        })
    return pd.DataFrame(rows).sort_values(["endpoint_id", "model_id", "case_id"]).reset_index(drop=True)


def _point_metrics(patient: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (endpoint_id, model_id), part in patient.groupby(["endpoint_id", "model_id"], sort=False):
        rows.extend([
            {"endpoint_id": endpoint_id, "model_id": model_id, "metric": "c_index",
             "estimate": _harrell_c_index(part["event"], part["time_years"], part["linear_predictor"])},
            {"endpoint_id": endpoint_id, "model_id": model_id, "metric": "ibs_0.5_5y",
             "estimate": float(part["ibs_contribution"].mean())},
        ])
    return pd.DataFrame(rows)


def summarize_models(patient: pd.DataFrame, model_replicates: pd.DataFrame) -> pd.DataFrame:
    point = _point_metrics(patient).set_index(["endpoint_id", "model_id", "metric"])
    registry = {spec.model_id: spec for spec in model_registry()}
    rows = []
    for keys, group in model_replicates.groupby(["endpoint_id", "model_id", "metric"], sort=False):
        endpoint_id, model_id, metric = keys
        valid = group["valid"].astype(bool) & group["estimate"].notna()
        values = group.loc[valid, "estimate"].astype(float)
        spec = registry[model_id]
        base = patient.loc[(patient["endpoint_id"] == endpoint_id) & (patient["model_id"] == model_id)]
        rows.append({
            "endpoint_id": endpoint_id,
            "model_id": model_id,
            "analysis_family": spec.analysis_family,
            "model_engine": spec.engine,
            "covariates": "+".join(spec.covariates),
            "n_patients": base["case_id"].nunique(),
            "n_events": int(base.drop_duplicates("case_id")["event"].sum()),
            "metric": metric,
            "estimate": float(point.loc[keys, "estimate"]),
            "ci_low": float(values.quantile(0.025)) if len(values) else np.nan,
            "ci_high": float(values.quantile(0.975)) if len(values) else np.nan,
            "n_bootstrap_requested": len(group),
            "n_bootstrap_valid": int(valid.sum()),
            "n_bootstrap_undefined": int((~valid).sum()),
            "bootstrap_undefined_fraction": float((~valid).mean()),
        })
    return pd.DataFrame(rows).sort_values(["endpoint_id", "model_id", "metric"]).reset_index(drop=True)


def build_contrast_outputs(
    patient: pd.DataFrame, model_replicates: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    points = _point_metrics(patient).set_index(["endpoint_id", "model_id", "metric"])
    replicate_parts = []
    summary_rows = []
    for endpoint_id in sorted(patient["endpoint_id"].unique()):
        endpoint_reps = model_replicates.loc[model_replicates["endpoint_id"].eq(endpoint_id)]
        endpoint_patient = patient.loc[patient["endpoint_id"].eq(endpoint_id)]
        n_events = int(endpoint_patient.drop_duplicates("case_id")["event"].sum())
        for contrast in contrast_registry():
            delta = paired_replicate_deltas(
                endpoint_reps, contrast.model_a, contrast.model_b, contrast.contrast_id
            )
            replicate_parts.append(delta)
            for metric in ("c_index", "ibs_0.5_5y"):
                part = delta.loc[delta["metric"].eq(metric)]
                valid = part["valid"].astype(bool) & part["estimate"].notna()
                values = part.loc[valid, "estimate"].astype(float)
                estimate_a = float(points.loc[(endpoint_id, contrast.model_a, metric), "estimate"])
                estimate_b = float(points.loc[(endpoint_id, contrast.model_b, metric), "estimate"])
                raw = estimate_b - estimate_a
                improvement = raw if metric == "c_index" else -raw
                summary_rows.append({
                    "endpoint_id": endpoint_id,
                    "contrast_id": contrast.contrast_id,
                    "estimand": contrast.estimand,
                    "model_a": contrast.model_a,
                    "model_b": contrast.model_b,
                    "metric": metric,
                    "metric_a": estimate_a,
                    "metric_b": estimate_b,
                    "raw_delta_b_minus_a": raw,
                    "improvement_delta": improvement,
                    "improvement_ci_low": float(values.quantile(0.025)) if len(values) else np.nan,
                    "improvement_ci_high": float(values.quantile(0.975)) if len(values) else np.nan,
                    "n_patients": endpoint_patient["case_id"].nunique(),
                    "n_events": n_events,
                    "n_bootstrap_requested": len(part),
                    "n_bootstrap_valid": int(valid.sum()),
                    "n_bootstrap_undefined": int((~valid).sum()),
                    "bootstrap_undefined_fraction": float((~valid).mean()),
                    "delta_definition": "model_b-model_a" if metric == "c_index" else "IBS_a-IBS_b",
                })
    return pd.DataFrame(summary_rows), pd.concat(replicate_parts, ignore_index=True)


def snapshot_paths(paths: Iterable[Path], root: Path) -> dict[Path, dict[str, Any]]:
    result = {}
    root = Path(root).resolve()
    for path in paths:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise R4IntegrityError(f"missing required input: {resolved}")
        stat = resolved.stat()
        try:
            logical = resolved.relative_to(root).as_posix()
        except ValueError:
            logical = str(resolved)
        result[resolved] = {
            "artifact_path": logical,
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256(resolved),
        }
    return result


def assert_snapshots_unchanged(
    before: Mapping[Path, Mapping[str, Any]], after: Mapping[Path, Mapping[str, Any]]
) -> None:
    if set(before) != set(after):
        raise R4IntegrityError("input snapshot set changed during run")
    for path in before:
        if before[path]["sha256"] != after[path]["sha256"]:
            raise R4IntegrityError(f"input changed during run: {path}")


def build_run_manifest(
    *,
    root: Path,
    input_before: Mapping[Path, Mapping[str, Any]],
    input_after: Mapping[Path, Mapping[str, Any]],
    input_roles: Mapping[Path, str],
    output_paths: list[Path],
    manifest_path: Path,
    software: Mapping[str, str],
    generated_at_utc: str,
    elapsed_seconds: float,
) -> pd.DataFrame:
    rows = []
    for path, before in input_before.items():
        after = input_after[path]
        rows.append({
            "artifact_kind": "input", "artifact_role": input_roles.get(path, "input"),
            "artifact_path": before["artifact_path"], "size_bytes": after["size_bytes"],
            "mtime_ns": after["mtime_ns"], "sha256_before": before["sha256"],
            "sha256_after": after["sha256"],
            "hash_reconciled": before["sha256"] == after["sha256"],
            "software_version": json.dumps(dict(software), sort_keys=True),
            "included_in_output_hashes": False, "hash_exclusion_reason": "immutable_input",
            "volatile_fields": "",
            "generated_at_utc": "", "elapsed_seconds": "",
        })
    for path in output_paths:
        stat = path.stat()
        rows.append({
            "artifact_kind": "output", "artifact_role": path.stem,
            "artifact_path": path.name, "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns), "sha256_before": "", "sha256_after": _sha256(path),
            "hash_reconciled": True, "software_version": json.dumps(dict(software), sort_keys=True),
            "included_in_output_hashes": True, "hash_exclusion_reason": "",
            "volatile_fields": "mtime_ns",
            "generated_at_utc": "", "elapsed_seconds": "",
        })
    rows.append({
        "artifact_kind": "manifest", "artifact_role": "run_manifest",
        "artifact_path": manifest_path.name, "size_bytes": "", "mtime_ns": "",
        "sha256_before": "", "sha256_after": "", "hash_reconciled": True,
        "software_version": json.dumps(dict(software), sort_keys=True),
        "included_in_output_hashes": False, "hash_exclusion_reason": "self_referential_manifest",
        "volatile_fields": "generated_at_utc;elapsed_seconds",
        "generated_at_utc": generated_at_utc, "elapsed_seconds": elapsed_seconds,
    })
    return pd.DataFrame(rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.17g", na_rep="")


def _worker_software() -> dict[str, str]:
    import lifelines
    import sklearn
    import sksurv

    return {
        "python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__, "scikit_survival": sksurv.__version__,
        "lifelines": lifelines.__version__, "executable": str(Path(sys.executable).resolve()),
    }


def _worker_run(job_path: Path) -> None:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    output_dir = Path(job["output_dir"])
    endpoints = [pd.DataFrame(records) for records in job["endpoints"]]
    oof_parts, diagnostic_parts = [], []
    for endpoint in endpoints:
        oof, diagnostics = fit_oof_models(endpoint)
        oof_parts.append(oof)
        diagnostic_parts.append(diagnostics)
    oof = pd.concat(oof_parts, ignore_index=True)
    diagnostics = pd.concat(diagnostic_parts, ignore_index=True)
    patient = patient_metric_frame(oof)
    canonical_ids = sorted(patient["case_id"].unique())
    draws, draw_meta = make_bootstrap_draws(canonical_ids)
    model_parts = []
    for endpoint_id, endpoint_patient in patient.groupby("endpoint_id", sort=True):
        ordered_parts = []
        for _, model_part in endpoint_patient.groupby("model_id", sort=False):
            ordered_parts.append(model_part.set_index("case_id").loc[canonical_ids].reset_index())
        ordered = pd.concat(ordered_parts, ignore_index=True)
        model_parts.append(bootstrap_model_metrics(
            ordered, draws, draw_meta, endpoint_id=str(endpoint_id)
        ))
    model_replicates = pd.concat(model_parts, ignore_index=True)
    summary = summarize_models(patient, model_replicates)
    deltas, contrast_replicates = build_contrast_outputs(patient, model_replicates)
    replicates = pd.concat([model_replicates, contrast_replicates], ignore_index=True, sort=False)
    for frame in (summary, deltas):
        if (frame["bootstrap_undefined_fraction"] > MAX_UNDEFINED_FRACTION).any():
            raise R4IntegrityError("bootstrap undefined fraction exceeds the frozen threshold")
    _write_csv(summary, output_dir / SUMMARY_NAME)
    _write_csv(deltas, output_dir / DELTAS_NAME)
    _write_csv(replicates, output_dir / BOOTSTRAP_NAME)
    oof_output = oof.copy()
    oof_output["evaluation_time_years"] = oof_output["evaluation_time_years"].map(
        lambda value: f"{float(value):.1f}"
    )
    _write_csv(oof_output, output_dir / OOF_NAME)
    _write_csv(diagnostics, output_dir / DIAGNOSTICS_NAME)
    (output_dir / "worker_status.json").write_text(
        json.dumps({"software": _worker_software(), "status": "ok"}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_worker(interpreter: Path) -> dict[str, str]:
    result = subprocess.run(
        [str(interpreter), str(SCRIPT), "--probe-worker"], capture_output=True, text=True, check=True
    )
    probe = json.loads(result.stdout)
    expected = {
        "numpy": "2.4.6", "pandas": "2.3.3", "scikit_learn": "1.9.0",
        "scikit_survival": "0.28.0", "lifelines": "0.30.3",
    }
    for key, value in expected.items():
        if probe.get(key) != value:
            raise R4IntegrityError(f"worker {key} version mismatch: {probe.get(key)} != {value}")
    return probe


def _load_official_pfi(common: pd.DataFrame, path: Path) -> pd.DataFrame:
    source = pd.read_csv(path)
    if "endpoint_id" in source:
        source = source.loc[source["endpoint_id"].astype(str).str.contains("PFI", case=False)]
    if any(name in source.columns for name in ("pfs_event", "dfs_event", "PFS_STATUS", "DFS_STATUS")):
        if not any(name in source.columns for name in ("pfi_event", "PFI_EVENT", "event")):
            raise R4IntegrityError("PFS/DFS cannot substitute for official PFI")
    event_col = next((name for name in ("pfi_event", "PFI_EVENT", "event") if name in source), None)
    time_col = next((name for name in (
        "pfi_time_years", "PFI_TIME_YEARS", "time_years", "follow_up_y"
    ) if name in source), None)
    if event_col is None or time_col is None:
        raise R4IntegrityError("official PFI source lacks normalized event/time-in-years columns")
    return normalize_endpoint(
        common, source, endpoint_id="E08_official_pfi", event_col=event_col, time_col=time_col,
        expected_events=OFFICIAL_PFI_EVENTS,
    )


def official_pfi_input_paths(root: Path = ROOT) -> tuple[Path, Path]:
    root = Path(root)
    return (
        root / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_patient_predictions.csv",
        root / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_run_manifest.csv",
    )


def _validate_real_outputs(directory: Path, endpoint_ids: set[str]) -> None:
    summary = pd.read_csv(directory / SUMMARY_NAME)
    deltas = pd.read_csv(directory / DELTAS_NAME)
    replicates = pd.read_csv(directory / BOOTSTRAP_NAME, low_memory=False)
    oof = pd.read_csv(directory / OOF_NAME)
    diagnostics = pd.read_csv(directory / DIAGNOSTICS_NAME)
    if set(summary["endpoint_id"]) != endpoint_ids or set(deltas["endpoint_id"]) != endpoint_ids:
        raise R4IntegrityError("summary/delta endpoints are missing or mixed")
    if set(oof["endpoint_id"]) != endpoint_ids or set(diagnostics["endpoint_id"]) != endpoint_ids:
        raise R4IntegrityError("OOF/diagnostic endpoints are missing or mixed")
    expected_oof = len(endpoint_ids) * COMMON_N * len(model_registry()) * len(time_grid())
    if len(oof) != expected_oof or oof.duplicated(
        ["endpoint_id", "case_id", "model_id", "evaluation_time_years"]
    ).any():
        raise R4IntegrityError("OOF survival output key/count mismatch")
    if not np.isfinite(oof[["linear_predictor", "survival_probability", "ipcw_brier_contribution"]]).all().all():
        raise R4IntegrityError("OOF survival output contains non-finite values")
    expected_replicates = len(endpoint_ids) * N_BOOTSTRAP * 2 * (
        len(model_registry()) + len(contrast_registry())
    )
    if len(replicates) != expected_replicates:
        raise R4IntegrityError("bootstrap replicate row count mismatch")
    counts = replicates.groupby(["endpoint_id", "record_type", "metric", "model_id", "contrast_id"],
                                 dropna=False).size()
    if not counts.eq(N_BOOTSTRAP).all():
        raise R4IntegrityError("bootstrap replicate IDs were deleted or compressed")
    if diagnostics["status"].ne("ok").any() or len(diagnostics) != len(endpoint_ids) * 55:
        raise R4IntegrityError("fold diagnostics are incomplete")


def _publish(staged: Mapping[str, Path], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    destinations = {name: output_dir / name for name in OUTPUT_NAMES}
    with tempfile.TemporaryDirectory(prefix="r4-paired-backup-", dir=output_dir.parent) as temporary:
        backup = Path(temporary)
        for name, destination in destinations.items():
            if destination.exists():
                shutil.copy2(destination, backup / name)
        installed: set[str] = set()
        try:
            for name in OUTPUT_NAMES:
                os.replace(staged[name], destinations[name])
                installed.add(name)
        except Exception as exc:
            for name, destination in destinations.items():
                old = backup / name
                if old.exists():
                    os.replace(old, destination)
                elif name in installed and destination.exists():
                    destination.unlink()
            raise R4IntegrityError("atomic publication failed; previous output set restored") from exc
    return destinations


def run_analysis(*, root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Path]:
    started = time.perf_counter()
    root = Path(root).resolve()
    output_dir = (root / "resources/projects/prostate_biomarker_validation/model_workspace" if output_dir is None else Path(output_dir)).resolve()
    pfi_path, pfi_manifest = official_pfi_input_paths(root)
    has_official_pfi = pfi_path.exists()
    if has_official_pfi and not pfi_manifest.exists():
        raise R4IntegrityError("official PFI predictions exist without the R3 run manifest")

    inputs = [
        root / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_predictions.csv",
        root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_predictions.csv",
        root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
        root / "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv",
        root / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested.py",
        root / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_clinical_hierarchy.py",
        root / "environment.yml", root / "requirements-lock.txt", SCRIPT,
    ]
    if has_official_pfi:
        inputs.extend([pfi_path, pfi_manifest])
    roles = {path.resolve(): path.name for path in inputs}
    before = snapshot_paths(inputs, root)

    common, common_diagnostics = load_reconstructed_common_cohort(root)
    reconstructed = normalize_endpoint(
        common, common[["case_id", "event", "follow_up_y"]],
        endpoint_id="E04_reconstructed_with_tumor", event_col="event", time_col="follow_up_y",
        expected_events=RECONSTRUCTED_EVENTS,
    )
    endpoints = [reconstructed]
    if has_official_pfi:
        pfi_manifest_frame = pd.read_csv(pfi_manifest, dtype=str, keep_default_na=False)
        r3_inputs = pfi_manifest_frame.loc[pfi_manifest_frame["artifact_kind"].eq("input")]
        if "source_unchanged_assertion" not in pfi_manifest_frame or not r3_inputs[
            "source_unchanged_assertion"
        ].eq("True").all():
            raise R4IntegrityError("R3 manifest contains an unreconciled input")
        r3_output = pfi_manifest_frame.loc[
            pfi_manifest_frame["artifact_kind"].eq("output")
            & pfi_manifest_frame["artifact_path"].map(lambda value: Path(value).name).eq(pfi_path.name)
        ]
        if (
            len(r3_output) != 1
            or r3_output.iloc[0]["sha256_after"] != _sha256(pfi_path)
            or r3_output.iloc[0]["included_in_output_hashes"] != "True"
        ):
            raise R4IntegrityError("R3 manifest does not bind the official PFI predictions")
        endpoints.append(_load_official_pfi(common, pfi_path))
    worker = root / "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python"
    worker_probe = _validate_worker(worker)

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r4-marker7-paired-", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        job = {
            "output_dir": str(stage),
            "endpoints": [frame.replace({np.nan: None}).to_dict("records") for frame in endpoints],
        }
        job_path = stage / "worker_job.json"
        job_path.write_text(json.dumps(job, sort_keys=True) + "\n", encoding="utf-8")
        subprocess.run(
            [str(worker), str(SCRIPT), "--worker", "--job", str(job_path)], check=True
        )
        status = json.loads((stage / "worker_status.json").read_text(encoding="utf-8"))
        if status.get("status") != "ok" or status.get("software") != worker_probe:
            raise R4IntegrityError("worker status/probe mismatch")
        endpoint_ids = {str(frame["endpoint_id"].iloc[0]) for frame in endpoints}
        _validate_real_outputs(stage, endpoint_ids)
        run_config = {
            "schema_version": "1.0", "analysis_id": "marker7_survival_paired_analysis",
            "entry_environment": ".venv/bin/python",
            "worker_environment": "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python",
            "worker_software": worker_probe,
            "common_cohort": common_diagnostics,
            "endpoint_ids": sorted(endpoint_ids),
            "models": [spec._asdict() for spec in model_registry()],
            "contrasts": [spec._asdict() for spec in contrast_registry()],
            "time_grid_years": time_grid().tolist(),
            "ipcw": "fold-train censoring KM; G(T-) for event, G(t) for at-risk",
            "bootstrap": {"n": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED, "unit": "patient row"},
            "delta": {"c_index": "model_b-model_a", "ibs": "IBS_a-IBS_b"},
            "thresholds": {"min_train_events": MIN_TRAIN_EVENTS,
                           "max_undefined_fraction": MAX_UNDEFINED_FRACTION},
            "outputs": list(OUTPUT_NAMES),
        }
        (stage / CONFIG_NAME).write_text(
            json.dumps(run_config, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        after = snapshot_paths(inputs, root)
        assert_snapshots_unchanged(before, after)
        manifest = build_run_manifest(
            root=root, input_before=before, input_after=after, input_roles=roles,
            output_paths=[stage / name for name in OUTPUT_NAMES if name != MANIFEST_NAME],
            manifest_path=stage / MANIFEST_NAME, software=worker_probe,
            generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            elapsed_seconds=time.perf_counter() - started,
        )
        _write_csv(manifest, stage / MANIFEST_NAME)
        staged = {name: stage / name for name in OUTPUT_NAMES}
        if any(not path.is_file() for path in staged.values()):
            raise R4IntegrityError("staged R4 output set is incomplete")
        return _publish(staged, output_dir)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--probe-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--job", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.probe_worker:
        print(json.dumps(_worker_software(), sort_keys=True))
        return
    if args.worker:
        if args.job is None:
            raise SystemExit("--worker requires --job")
        _worker_run(args.job)
        return
    outputs = run_analysis(root=args.root, output_dir=args.output_dir)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
