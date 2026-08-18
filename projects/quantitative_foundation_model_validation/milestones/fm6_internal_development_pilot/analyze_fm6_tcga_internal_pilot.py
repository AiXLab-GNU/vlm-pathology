#!/usr/bin/env python3
"""Analyze paired TCGA whole-tissue embeddings for the FM6 internal pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.metrics import cohen_kappa_score, mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm6_internal_development_pilot"
OUTPUTS = MILESTONE / "outputs"
LOCAL = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot"
SOURCE = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/tcga_prad_current_gdc_bcr"

SEED = 260817
BOOTSTRAPS = 2000
RANDOM_CONTROLS = 100
PERMUTED_CONTROLS = 20
ISUP_PERMUTATIONS = 200
RIDGE_ALPHAS = np.asarray([0.1, 1.0, 10.0, 100.0, 1000.0])
COX_ALPHAS = np.asarray([0.1, 1.0, 10.0, 100.0, 1000.0])
PCA_COMPONENTS = 64
SECONDARY_CLINICAL = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pancan_clinical.json"
SECONDARY_CLINICAL_SHA256 = "3e2ec994c7ca87638d99ccc5a2287430613a749143d01a3a36ae36191bbc4241"


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def survival_target(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.asarray([(bool(e), float(t)) for e, t in zip(event, time, strict=True)], dtype=[("event", "?"), ("time", "<f8")])


def c_index(event: np.ndarray, time: np.ndarray, risk: np.ndarray) -> float:
    return float(concordance_index_censored(event.astype(bool), time.astype(float), risk.astype(float))[0])


def safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    value = stats.spearmanr(left, right).statistic
    return float(value) if np.isfinite(value) else np.nan


def partial_spearman(left: np.ndarray, right: np.ndarray, covariates: np.ndarray) -> float:
    complete = np.isfinite(left) & np.isfinite(right) & np.isfinite(covariates).all(axis=1)
    left_rank = stats.rankdata(left[complete])
    right_rank = stats.rankdata(right[complete])
    covariate_rank = np.column_stack([stats.rankdata(covariates[complete, index]) for index in range(covariates.shape[1])])
    design = np.column_stack([np.ones(complete.sum()), covariate_rank])
    left_residual = left_rank - design @ np.linalg.lstsq(design, left_rank, rcond=None)[0]
    right_residual = right_rank - design @ np.linalg.lstsq(design, right_rank, rcond=None)[0]
    return safe_spearman(left_residual, right_residual)


def qwk(y: np.ndarray, prediction: np.ndarray) -> float:
    rounded = np.clip(np.rint(prediction), 1, 5).astype(int)
    return float(cohen_kappa_score(y.astype(int), rounded, weights="quadratic"))


def secondary_clinical_metrics() -> pd.DataFrame:
    if sha256_file(SECONDARY_CLINICAL) != SECONDARY_CLINICAL_SHA256:
        raise RuntimeError("secondary TCGA clinical source hash changed")
    source = pd.DataFrame(json.loads(SECONDARY_CLINICAL.read_text()))
    source = source[source.clinicalAttributeId.isin(["AGE", "PATH_T_STAGE"])].copy()
    pivot = source.pivot_table(index="patientId", columns="clinicalAttributeId", values="value", aggfunc="first")
    pivot = pivot.reset_index().rename(columns={"patientId": "case_id", "AGE": "age_years", "PATH_T_STAGE": "path_t_stage"})
    pivot["age_years"] = pd.to_numeric(pivot.age_years, errors="coerce")
    pivot["path_t_stage_ordinal"] = pivot.path_t_stage.map(
        lambda value: float(re.match(r"T([234])", str(value).upper()).group(1))
        if re.match(r"T([234])", str(value).upper()) else np.nan
    )
    return pivot[["case_id", "age_years", "path_t_stage", "path_t_stage_ordinal"]]


def load_subject_data(encoder: str) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    manifest = pd.read_csv(OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv")
    array = np.load(LOCAL / f"fm6_tcga_{encoder}_tile_embeddings.npy", mmap_mode="r", allow_pickle=False)
    if array.shape[0] != len(manifest):
        raise RuntimeError(f"{encoder} row mismatch")
    slide_vectors, slide_rows = [], []
    for file_id, rows in manifest.groupby("file_id", sort=False):
        positions = rows.embedding_row.to_numpy(int)
        slide_vectors.append(np.asarray(array[positions], dtype=np.float64).mean(axis=0))
        slide_rows.append({
            "case_id": rows.case_id.iloc[0],
            "file_id": file_id,
            "outer_fold": int(rows.outer_fold.iloc[0]),
            "n_tiles": len(rows),
            "mean_thumbnail_tissue_fraction": float(rows.thumbnail_tissue_fraction.mean()),
            "mpp": float(rows.mpp.iloc[0]),
        })
    slide = pd.DataFrame(slide_rows)
    slide_x = np.stack(slide_vectors)
    subject_vectors, subject_rows = [], []
    for case_id, rows in slide.groupby("case_id", sort=True):
        positions = rows.index.to_numpy(int)
        subject_vectors.append(slide_x[positions].mean(axis=0))
        subject_rows.append({
            "case_id": case_id,
            "outer_fold": int(rows.outer_fold.iloc[0]),
            "n_slides": len(rows),
            "n_tiles": int(rows.n_tiles.sum()),
            "mean_thumbnail_tissue_fraction": float(rows.mean_thumbnail_tissue_fraction.mean()),
            "mean_mpp": float(rows.mpp.mean()),
        })
    subject = pd.DataFrame(subject_rows)
    x = np.stack(subject_vectors)
    clinical = pd.read_csv(SOURCE / "development_subjects.csv")
    subject = subject.merge(clinical, on="case_id", validate="one_to_one")
    folds = pd.read_csv(SOURCE / "development_outer_folds.csv")
    subject = subject.drop(columns="outer_fold").merge(folds[["case_id", "outer_fold"]], on="case_id", validate="one_to_one")
    subject = subject.merge(secondary_clinical_metrics(), on="case_id", how="left", validate="one_to_one")
    order = subject.case_id.argsort(kind="stable").to_numpy()
    return subject.iloc[order].reset_index(drop=True), x[order], slide


def inner_ridge_alpha(x: np.ndarray, y: np.ndarray, folds: np.ndarray) -> float:
    best_alpha, best_score = float(RIDGE_ALPHAS[0]), -np.inf
    for alpha in RIDGE_ALPHAS:
        prediction = np.full(len(y), np.nan)
        for fold in np.unique(folds):
            train, test = folds != fold, folds == fold
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[train], y[train])
            prediction[test] = model.predict(x[test])
        score = safe_spearman(y, prediction)
        if np.isfinite(score) and score > best_score:
            best_alpha, best_score = float(alpha), score
    return best_alpha


def fit_cox_components(x: np.ndarray, event: np.ndarray, time: np.ndarray, alpha: float) -> tuple[StandardScaler, PCA, CoxPHSurvivalAnalysis, float, float]:
    scaler = StandardScaler()
    xs = scaler.fit_transform(x)
    n_components = min(PCA_COMPONENTS, len(x) - 1, x.shape[1])
    pca = PCA(n_components=n_components, svd_solver="randomized", random_state=SEED)
    z = pca.fit_transform(xs)
    cox = CoxPHSurvivalAnalysis(alpha=float(alpha), n_iter=200)
    cox.fit(z, survival_target(event, time))
    train_risk = cox.predict(z)
    return scaler, pca, cox, float(train_risk.mean()), float(max(train_risk.std(ddof=0), 1e-8))


def predict_cox(model: tuple[StandardScaler, PCA, CoxPHSurvivalAnalysis, float, float], x: np.ndarray) -> np.ndarray:
    scaler, pca, cox, mean, sd = model
    return (cox.predict(pca.transform(scaler.transform(x))) - mean) / sd


def inner_cox_alpha(x: np.ndarray, event: np.ndarray, time: np.ndarray, folds: np.ndarray) -> float:
    best_alpha, best_score = float(COX_ALPHAS[0]), -np.inf
    for alpha in COX_ALPHAS:
        prediction = np.full(len(event), np.nan)
        for fold in np.unique(folds):
            train, test = folds != fold, folds == fold
            try:
                model = fit_cox_components(x[train], event[train], time[train], float(alpha))
                prediction[test] = predict_cox(model, x[test])
            except Exception:
                prediction[test] = np.nan
        if np.isfinite(prediction).all():
            score = c_index(event, time, prediction)
            if score > best_score:
                best_alpha, best_score = float(alpha), score
    return best_alpha


def erase_direction(xs: np.ndarray, direction: np.ndarray) -> np.ndarray:
    norm = float(np.dot(direction, direction))
    if not np.isfinite(norm) or norm <= 1e-16:
        raise RuntimeError("invalid erasure direction")
    return xs - np.outer(xs @ direction / norm, direction)


def variance_matched_random_directions(
    xs: np.ndarray,
    target_direction: np.ndarray,
    n_directions: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construct unit random directions with exact training-fold removed variance.

    A random high-variance and low-variance right-singular direction are mixed with
    analytically chosen squared weights. This matches the target Rayleigh quotient
    while remaining outcome- and concept-label-blind after the target variance is set.
    """
    target_unit = target_direction / max(np.linalg.norm(target_direction), 1e-12)
    target_variance = float(np.mean((xs @ target_unit) ** 2))
    _, singular, vt = np.linalg.svd(xs, full_matrices=False)
    eigenvalues = singular ** 2 / len(xs)
    high_indices = np.flatnonzero(eigenvalues >= target_variance)
    low_indices = np.flatnonzero(eigenvalues <= target_variance)
    if len(high_indices) == 0:
        high_indices = np.asarray([int(np.argmax(eigenvalues))])
    directions, ratios, cosines = [], [], []
    attempts = 0
    while len(directions) < n_directions and attempts < n_directions * 200:
        attempts += 1
        high_index = int(rng.choice(high_indices))
        high_value = float(eigenvalues[high_index])
        high_vector = vt[high_index]
        use_null = len(low_indices) == 0 or bool(rng.integers(0, 5) == 0)
        if use_null:
            candidate = rng.normal(size=xs.shape[1])
            candidate -= vt.T @ (vt @ candidate)
            candidate_norm = np.linalg.norm(candidate)
            if candidate_norm <= 1e-10:
                continue
            low_vector = candidate / candidate_norm
            low_value = 0.0
        else:
            low_index = int(rng.choice(low_indices))
            low_vector = vt[low_index]
            low_value = float(eigenvalues[low_index])
        if high_value <= low_value + 1e-14:
            continue
        high_weight = float(np.clip((target_variance - low_value) / (high_value - low_value), 0.0, 1.0))
        sign = -1.0 if rng.integers(0, 2) else 1.0
        direction = np.sqrt(high_weight) * high_vector + sign * np.sqrt(1.0 - high_weight) * low_vector
        direction /= max(np.linalg.norm(direction), 1e-12)
        cosine = float(abs(np.dot(direction, target_unit)))
        observed = float(np.mean((xs @ direction) ** 2))
        directions.append(direction)
        ratios.append(observed / max(target_variance, 1e-16))
        cosines.append(cosine)
    if len(directions) != n_directions:
        raise RuntimeError("could not construct enough variance-matched random directions")
    return np.stack(directions), np.asarray(ratios), np.asarray(cosines)


def fit_standardized_cox(xs: np.ndarray, event: np.ndarray, time: np.ndarray, alpha: float) -> tuple[PCA, CoxPHSurvivalAnalysis, float, float]:
    n_components = min(PCA_COMPONENTS, len(xs) - 1, xs.shape[1])
    pca = PCA(n_components=n_components, svd_solver="randomized", random_state=SEED)
    z = pca.fit_transform(xs)
    cox = CoxPHSurvivalAnalysis(alpha=float(alpha), n_iter=200)
    cox.fit(z, survival_target(event, time))
    risk = cox.predict(z)
    return pca, cox, float(risk.mean()), float(max(risk.std(ddof=0), 1e-8))


def predict_standardized_cox(model: tuple[PCA, CoxPHSurvivalAnalysis, float, float], xs: np.ndarray) -> np.ndarray:
    pca, cox, mean, sd = model
    return (cox.predict(pca.transform(xs)) - mean) / sd


def fit_small_cox(train: np.ndarray, event: np.ndarray, time: np.ndarray, test: np.ndarray) -> np.ndarray:
    scaler = StandardScaler()
    train_z = scaler.fit_transform(train)
    test_z = scaler.transform(test)
    cox = CoxPHSurvivalAnalysis(alpha=1.0, n_iter=200)
    cox.fit(train_z, survival_target(event, time))
    train_risk = cox.predict(train_z)
    return (cox.predict(test_z) - train_risk.mean()) / max(train_risk.std(ddof=0), 1e-8)


def oof_continuous_probe(x: np.ndarray, target: np.ndarray, folds: np.ndarray) -> tuple[np.ndarray, dict[int, float]]:
    prediction = np.full(len(target), np.nan)
    settings: dict[int, float] = {}
    observed = np.isfinite(target)
    for outer_fold in sorted(np.unique(folds)):
        train = observed & (folds != outer_fold)
        test = observed & (folds == outer_fold)
        alpha = inner_ridge_alpha(x[train], target[train], folds[train])
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(x[train], target[train])
        prediction[test] = model.predict(x[test])
        settings[int(outer_fold)] = alpha
    return prediction, settings


def oof_risk_explanation(metrics: np.ndarray, risk: np.ndarray, folds: np.ndarray) -> np.ndarray:
    complete = np.isfinite(metrics).all(axis=1) & np.isfinite(risk)
    prediction = np.full(len(risk), np.nan)
    for outer_fold in sorted(np.unique(folds)):
        train = complete & (folds != outer_fold)
        test = complete & (folds == outer_fold)
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        model.fit(metrics[train], risk[train])
        prediction[test] = model.predict(metrics[test])
    return prediction


def analyze_encoder(encoder: str) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict[str, object]]:
    subject, x, _ = load_subject_data(encoder)
    event = subject.bcr_event.to_numpy(int)
    time = subject.bcr_time_days.to_numpy(float)
    isup = subject.isup_grade_group.to_numpy(float)
    folds = subject.outer_fold.to_numpy(int)
    n = len(subject)
    arrays = {
        "isup_prediction": np.full(n, np.nan),
        "full_risk": np.full(n, np.nan),
        "target_fixed_risk": np.full(n, np.nan),
        "target_refit_risk": np.full(n, np.nan),
        "isup_only_risk": np.full(n, np.nan),
        "isup_plus_ai_risk": np.full(n, np.nan),
        "random_fixed_risk": np.full((RANDOM_CONTROLS, n), np.nan),
        "permuted_fixed_risk": np.full((PERMUTED_CONTROLS, n), np.nan),
        "random_removed_variance_ratio": np.full((RANDOM_CONTROLS, len(np.unique(folds))), np.nan),
        "random_concept_abs_cosine": np.full((RANDOM_CONTROLS, len(np.unique(folds))), np.nan),
    }
    fold_records = []
    probe_alphas: dict[int, float] = {}
    for outer_fold in sorted(np.unique(folds)):
        train, test = folds != outer_fold, folds == outer_fold
        train_folds = folds[train]
        probe_alpha = inner_ridge_alpha(x[train], isup[train], train_folds)
        probe = make_pipeline(StandardScaler(), Ridge(alpha=probe_alpha))
        probe.fit(x[train], isup[train])
        arrays["isup_prediction"][test] = probe.predict(x[test])
        probe_alphas[int(outer_fold)] = probe_alpha

        cox_alpha = inner_cox_alpha(x[train], event[train], time[train], train_folds)
        head = fit_cox_components(x[train], event[train], time[train], cox_alpha)
        full_train_risk = predict_cox(head, x[train])
        arrays["full_risk"][test] = predict_cox(head, x[test])

        scaler, pca, cox, risk_mean, risk_sd = head
        xs_train, xs_test = scaler.transform(x[train]), scaler.transform(x[test])
        direction = Ridge(alpha=probe_alpha).fit(xs_train, isup[train]).coef_.astype(float)
        erased_train, erased_test = erase_direction(xs_train, direction), erase_direction(xs_test, direction)
        fixed_model = (pca, cox, risk_mean, risk_sd)
        arrays["target_fixed_risk"][test] = predict_standardized_cox(fixed_model, erased_test)
        refit_model = fit_standardized_cox(erased_train, event[train], time[train], cox_alpha)
        arrays["target_refit_risk"][test] = predict_standardized_cox(refit_model, erased_test)

        rng = np.random.default_rng(SEED + 1000 * (1 if encoder == "conch" else 2) + int(outer_fold))
        random_directions, variance_ratios, concept_cosines = variance_matched_random_directions(
            xs_train, direction, RANDOM_CONTROLS, rng
        )
        for draw, random_direction in enumerate(random_directions):
            random_test = erase_direction(xs_test, random_direction)
            arrays["random_fixed_risk"][draw, test] = predict_standardized_cox(fixed_model, random_test)
            arrays["random_removed_variance_ratio"][draw, int(outer_fold)] = variance_ratios[draw]
            arrays["random_concept_abs_cosine"][draw, int(outer_fold)] = concept_cosines[draw]
        for draw in range(PERMUTED_CONTROLS):
            permuted_y = rng.permutation(isup[train])
            permuted_direction = Ridge(alpha=probe_alpha).fit(xs_train, permuted_y).coef_.astype(float)
            permuted_test = erase_direction(xs_test, permuted_direction)
            arrays["permuted_fixed_risk"][draw, test] = predict_standardized_cox(fixed_model, permuted_test)

        arrays["isup_only_risk"][test] = fit_small_cox(
            isup[train][:, None], event[train], time[train], isup[test][:, None]
        )
        arrays["isup_plus_ai_risk"][test] = fit_small_cox(
            np.column_stack([isup[train], full_train_risk]), event[train], time[train],
            np.column_stack([isup[test], arrays["full_risk"][test]]),
        )
        fold_records.append({
            "encoder": encoder,
            "outer_fold": int(outer_fold),
            "n_train": int(train.sum()),
            "n_test": int(test.sum()),
            "events_train": int(event[train].sum()),
            "events_test": int(event[test].sum()),
            "ridge_probe_alpha": probe_alpha,
            "cox_alpha": cox_alpha,
            "pca_components": int(pca.n_components_),
        })

    if any(not np.isfinite(value).all() for value in arrays.values()):
        raise RuntimeError(f"nonfinite OOF output for {encoder}")

    age = subject.age_years.to_numpy(float)
    stage = subject.path_t_stage_ordinal.to_numpy(float)
    age_prediction, age_alphas = oof_continuous_probe(x, age, folds)
    stage_prediction, stage_alphas = oof_continuous_probe(x, stage, folds)
    arrays["age_prediction"] = age_prediction
    arrays["stage_prediction"] = stage_prediction
    metrics_isup = isup[:, None]
    metrics_panel = np.column_stack([isup, age, stage])
    arrays["risk_explanation_isup"] = oof_risk_explanation(metrics_isup, arrays["full_risk"], folds)
    arrays["risk_explanation_panel"] = oof_risk_explanation(metrics_panel, arrays["full_risk"], folds)
    arrays["clinical_panel_risk"] = np.full(n, np.nan)
    arrays["clinical_panel_plus_ai_risk"] = np.full(n, np.nan)
    complete_panel = np.isfinite(metrics_panel).all(axis=1)
    for outer_fold in sorted(np.unique(folds)):
        train = complete_panel & (folds != outer_fold)
        test = complete_panel & (folds == outer_fold)
        arrays["clinical_panel_risk"][test] = fit_small_cox(
            metrics_panel[train], event[train], time[train], metrics_panel[test]
        )
        arrays["clinical_panel_plus_ai_risk"][test] = fit_small_cox(
            np.column_stack([metrics_panel[train], arrays["full_risk"][train]]),
            event[train], time[train],
            np.column_stack([metrics_panel[test], arrays["full_risk"][test]]),
        )

    # Fold-preserving label-permutation null for whole-tissue ISUP recoverability.
    permutation_rho = np.empty(ISUP_PERMUTATIONS, dtype=float)
    rng = np.random.default_rng(SEED + (10 if encoder == "conch" else 20))
    for draw in range(ISUP_PERMUTATIONS):
        permuted = rng.permutation(isup)
        prediction = np.full(n, np.nan)
        for outer_fold in sorted(np.unique(folds)):
            train, test = folds != outer_fold, folds == outer_fold
            model = make_pipeline(StandardScaler(), Ridge(alpha=probe_alphas[int(outer_fold)]))
            model.fit(x[train], permuted[train])
            prediction[test] = model.predict(x[test])
        permutation_rho[draw] = safe_spearman(permuted, prediction)
    arrays["isup_permutation_rho"] = permutation_rho

    for record in fold_records:
        mask = folds == record["outer_fold"]
        record["isup_spearman_test"] = safe_spearman(isup[mask], arrays["isup_prediction"][mask])
        for name in ["full_risk", "target_fixed_risk", "target_refit_risk", "isup_only_risk", "isup_plus_ai_risk"]:
            try:
                record[f"{name}_c_index_test"] = c_index(event[mask], time[mask], arrays[name][mask])
            except Exception:
                record[f"{name}_c_index_test"] = np.nan

    oof = subject[[
        "case_id", "outer_fold", "isup_grade_group", "bcr_event", "bcr_time_days",
        "n_slides", "n_tiles", "mean_thumbnail_tissue_fraction", "mean_mpp",
    ]].copy()
    for name in ["isup_prediction", "full_risk", "target_fixed_risk", "target_refit_risk", "isup_only_risk", "isup_plus_ai_risk"]:
        oof[name] = arrays[name]
    oof["age_years"] = age
    oof["path_t_stage_ordinal"] = stage
    oof["age_prediction"] = age_prediction
    oof["stage_prediction"] = stage_prediction
    oof["risk_explanation_isup"] = arrays["risk_explanation_isup"]
    oof["risk_explanation_panel"] = arrays["risk_explanation_panel"]
    oof["clinical_panel_risk"] = arrays["clinical_panel_risk"]
    oof["clinical_panel_plus_ai_risk"] = arrays["clinical_panel_plus_ai_risk"]
    oof.insert(0, "encoder", encoder)

    full_c = c_index(event, time, arrays["full_risk"])
    target_c = c_index(event, time, arrays["target_fixed_risk"])
    refit_c = c_index(event, time, arrays["target_refit_risk"])
    random_c = np.asarray([c_index(event, time, row) for row in arrays["random_fixed_risk"]])
    permuted_c = np.asarray([c_index(event, time, row) for row in arrays["permuted_fixed_risk"]])
    target_delta = full_c - target_c
    random_delta = full_c - random_c
    permuted_delta = full_c - permuted_c
    age_mask = np.isfinite(age_prediction)
    stage_mask = np.isfinite(stage_prediction)
    panel_mask = np.isfinite(arrays["risk_explanation_panel"])
    isup_explanation_mask = np.isfinite(arrays["risk_explanation_isup"])
    summary = {
        "encoder": encoder,
        "n_subjects": n,
        "n_events": int(event.sum()),
        "isup_spearman": safe_spearman(isup, arrays["isup_prediction"]),
        "isup_mae": float(mean_absolute_error(isup, arrays["isup_prediction"])),
        "isup_qwk": qwk(isup, arrays["isup_prediction"]),
        "isup_permutation_p_one_sided": float((1 + np.sum(permutation_rho >= safe_spearman(isup, arrays["isup_prediction"]))) / (1 + len(permutation_rho))),
        "bcr_full_c_index": full_c,
        "bcr_isup_only_c_index": c_index(event, time, arrays["isup_only_risk"]),
        "bcr_isup_plus_ai_c_index": c_index(event, time, arrays["isup_plus_ai_risk"]),
        "target_fixed_c_index": target_c,
        "target_refit_c_index": refit_c,
        "target_fixed_delta_use": target_delta,
        "target_refit_delta_info": full_c - refit_c,
        "random_delta_median": float(np.median(random_delta)),
        "random_delta_p95": float(np.quantile(random_delta, 0.95)),
        "random_removed_variance_ratio_median": float(np.median(arrays["random_removed_variance_ratio"])),
        "random_removed_variance_ratio_min": float(np.min(arrays["random_removed_variance_ratio"])),
        "random_removed_variance_ratio_max": float(np.max(arrays["random_removed_variance_ratio"])),
        "random_concept_abs_cosine_median": float(np.median(arrays["random_concept_abs_cosine"])),
        "random_concept_abs_cosine_max": float(np.max(arrays["random_concept_abs_cosine"])),
        "target_vs_random_p_one_sided": float((1 + np.sum(random_delta >= target_delta)) / (1 + len(random_delta))),
        "permuted_delta_median": float(np.median(permuted_delta)),
        "permuted_delta_p95": float(np.quantile(permuted_delta, 0.95)),
        "target_vs_permuted_p_one_sided": float((1 + np.sum(permuted_delta >= target_delta)) / (1 + len(permuted_delta))),
        "isup_ai_risk_spearman": safe_spearman(isup, arrays["full_risk"]),
        "isup_ai_risk_partial_spearman_age_stage": partial_spearman(
            isup, arrays["full_risk"], np.column_stack([age, stage])
        ),
        "isup_ai_risk_r2": float(r2_score(arrays["full_risk"], Ridge(alpha=1.0).fit(isup[:, None], arrays["full_risk"]).predict(isup[:, None]))),
        "risk_change_isup_spearman": safe_spearman(isup, arrays["full_risk"] - arrays["target_fixed_risk"]),
        "age_n": int(age_mask.sum()),
        "age_oof_spearman": safe_spearman(age[age_mask], age_prediction[age_mask]),
        "age_oof_mae": float(mean_absolute_error(age[age_mask], age_prediction[age_mask])),
        "path_t_stage_n": int(stage_mask.sum()),
        "path_t_stage_oof_spearman": safe_spearman(stage[stage_mask], stage_prediction[stage_mask]),
        "path_t_stage_oof_mae": float(mean_absolute_error(stage[stage_mask], stage_prediction[stage_mask])),
        "risk_explanation_isup_n": int(isup_explanation_mask.sum()),
        "risk_explanation_isup_oof_r2": float(r2_score(arrays["full_risk"][isup_explanation_mask], arrays["risk_explanation_isup"][isup_explanation_mask])),
        "risk_explanation_panel_n": int(panel_mask.sum()),
        "risk_explanation_panel_oof_r2": float(r2_score(arrays["full_risk"][panel_mask], arrays["risk_explanation_panel"][panel_mask])),
        "risk_explanation_panel_delta_r2": float(
            r2_score(arrays["full_risk"][panel_mask], arrays["risk_explanation_panel"][panel_mask])
            - r2_score(arrays["full_risk"][panel_mask], arrays["risk_explanation_isup"][panel_mask])
        ),
        "bcr_clinical_panel_c_index_complete_case": c_index(event[panel_mask], time[panel_mask], arrays["clinical_panel_risk"][panel_mask]),
        "bcr_clinical_panel_plus_ai_c_index_complete_case": c_index(event[panel_mask], time[panel_mask], arrays["clinical_panel_plus_ai_risk"][panel_mask]),
        "risk_thumbnail_tissue_fraction_spearman": safe_spearman(
            arrays["full_risk"], subject.mean_thumbnail_tissue_fraction.to_numpy(float)
        ),
        "risk_mean_mpp_spearman": safe_spearman(arrays["full_risk"], subject.mean_mpp.to_numpy(float)),
        "risk_n_slides_spearman": safe_spearman(arrays["full_risk"], subject.n_slides.to_numpy(float)),
        "erasure_change_thumbnail_tissue_fraction_spearman": safe_spearman(
            arrays["full_risk"] - arrays["target_fixed_risk"],
            subject.mean_thumbnail_tissue_fraction.to_numpy(float),
        ),
        "head_minimum_validity_pass": False,
    }
    return oof, arrays, {"summary": summary, "folds": fold_records, "random_delta": random_delta, "permuted_delta": permuted_delta}


def bootstrap_ci(values: np.ndarray) -> tuple[float, float]:
    valid = values[np.isfinite(values)]
    return float(np.quantile(valid, 0.025)), float(np.quantile(valid, 0.975))


def bootstrap_results(oof_by_encoder: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    encoders = sorted(oof_by_encoder)
    base = oof_by_encoder[encoders[0]]
    if any(not base.case_id.equals(oof_by_encoder[name].case_id) for name in encoders[1:]):
        raise RuntimeError("encoder subject order mismatch")
    rng = np.random.default_rng(SEED + 99)
    rows, paired, within = [], [], []
    metrics = ["full_risk", "target_fixed_risk", "target_refit_risk", "isup_only_risk", "isup_plus_ai_risk"]
    samples = rng.integers(0, len(base), size=(BOOTSTRAPS, len(base)))
    stored: dict[tuple[str, str], np.ndarray] = {}
    for encoder in encoders:
        frame = oof_by_encoder[encoder]
        event = frame.bcr_event.to_numpy(int)
        time = frame.bcr_time_days.to_numpy(float)
        for metric in metrics:
            risk = frame[metric].to_numpy(float)
            draws = np.full(BOOTSTRAPS, np.nan)
            for index, sample in enumerate(samples):
                try:
                    draws[index] = c_index(event[sample], time[sample], risk[sample])
                except Exception:
                    pass
            low, high = bootstrap_ci(draws)
            observed = c_index(event, time, risk)
            rows.append({
                "encoder": encoder, "metric": metric, "estimate": observed,
                "ci_low": low, "ci_high": high,
                "bootstrap_valid": int(np.isfinite(draws).sum()),
                "bootstrap_undefined": int((~np.isfinite(draws)).sum()),
            })
            stored[(encoder, metric)] = draws
        isup = frame.isup_grade_group.to_numpy(float)
        pred = frame.isup_prediction.to_numpy(float)
        draws = np.asarray([safe_spearman(isup[sample], pred[sample]) for sample in samples])
        low, high = bootstrap_ci(draws)
        rows.append({
            "encoder": encoder, "metric": "isup_spearman", "estimate": safe_spearman(isup, pred),
            "ci_low": low, "ci_high": high, "bootstrap_valid": int(np.isfinite(draws).sum()),
            "bootstrap_undefined": int((~np.isfinite(draws)).sum()),
        })
        for contrast_id, left_metric, right_metric in [
            ("full_minus_target_fixed", "full_risk", "target_fixed_risk"),
            ("full_minus_target_refit", "full_risk", "target_refit_risk"),
            ("isup_plus_ai_minus_isup_only", "isup_plus_ai_risk", "isup_only_risk"),
        ]:
            difference = stored[(encoder, left_metric)] - stored[(encoder, right_metric)]
            low, high = bootstrap_ci(difference)
            left_observed = c_index(event, time, frame[left_metric].to_numpy(float))
            right_observed = c_index(event, time, frame[right_metric].to_numpy(float))
            within.append({
                "encoder": encoder,
                "contrast_id": contrast_id,
                "left_metric": left_metric,
                "right_metric": right_metric,
                "estimate_left_minus_right": left_observed - right_observed,
                "ci_low": low,
                "ci_high": high,
                "bootstrap_valid": int(np.isfinite(difference).sum()),
                "bootstrap_undefined": int((~np.isfinite(difference)).sum()),
            })
    if len(encoders) == 2:
        left, right = encoders
        for metric in metrics:
            difference = stored[(left, metric)] - stored[(right, metric)]
            low, high = bootstrap_ci(difference)
            paired.append({
                "metric": metric,
                "left_encoder": left,
                "right_encoder": right,
                "estimate_left_minus_right": c_index(base.bcr_event.to_numpy(int), base.bcr_time_days.to_numpy(float), oof_by_encoder[left][metric].to_numpy(float)) - c_index(base.bcr_event.to_numpy(int), base.bcr_time_days.to_numpy(float), oof_by_encoder[right][metric].to_numpy(float)),
                "ci_low": low, "ci_high": high,
                "bootstrap_valid": int(np.isfinite(difference).sum()),
                "bootstrap_undefined": int((~np.isfinite(difference)).sum()),
            })
    return pd.DataFrame(rows), pd.DataFrame(paired), pd.DataFrame(within)


def run() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    paired_audit = json.loads((OUTPUTS / "fm6_tcga_paired_embedding_audit.json").read_text())
    if paired_audit["status"] != "PASS":
        raise RuntimeError("paired embedding audit not passed")
    oof_by_encoder, analyses, summaries, folds = {}, {}, [], []
    for encoder in ["conch", "virchow"]:
        print(f"analyze {encoder}", flush=True)
        oof, arrays, details = analyze_encoder(encoder)
        oof_by_encoder[encoder] = oof
        analyses[encoder] = arrays
        summaries.append(details["summary"])
        folds.extend(details["folds"])
        pd.DataFrame({
            "draw": np.arange(RANDOM_CONTROLS),
            "delta_use": details["random_delta"],
            "removed_variance_ratio_median_across_folds": np.median(arrays["random_removed_variance_ratio"], axis=1),
            "removed_variance_ratio_min_across_folds": np.min(arrays["random_removed_variance_ratio"], axis=1),
            "removed_variance_ratio_max_across_folds": np.max(arrays["random_removed_variance_ratio"], axis=1),
            "concept_abs_cosine_median_across_folds": np.median(arrays["random_concept_abs_cosine"], axis=1),
            "concept_abs_cosine_max_across_folds": np.max(arrays["random_concept_abs_cosine"], axis=1),
        }).assign(encoder=encoder).to_csv(
            OUTPUTS / f"fm6_{encoder}_matched_random_erasure_controls.csv", index=False, lineterminator="\n"
        )
        pd.DataFrame({"draw": np.arange(PERMUTED_CONTROLS), "delta_use": details["permuted_delta"]}).assign(encoder=encoder).to_csv(
            OUTPUTS / f"fm6_{encoder}_label_permuted_erasure_controls.csv", index=False, lineterminator="\n"
        )
    all_oof = pd.concat(oof_by_encoder.values(), ignore_index=True)
    all_oof.to_csv(OUTPUTS / "fm6_tcga_patient_oof_predictions.csv", index=False, lineterminator="\n")
    summary = pd.DataFrame(summaries)
    bootstrap, paired, within = bootstrap_results(oof_by_encoder)
    for encoder in summary.encoder:
        row = bootstrap[(bootstrap.encoder.eq(encoder)) & (bootstrap.metric.eq("full_risk"))].iloc[0]
        summary.loc[summary.encoder.eq(encoder), "bcr_full_c_index_ci_low"] = row.ci_low
        summary.loc[summary.encoder.eq(encoder), "bcr_full_c_index_ci_high"] = row.ci_high
        summary.loc[summary.encoder.eq(encoder), "head_minimum_validity_pass"] = bool(row.ci_low > 0.50)
    summary.to_csv(OUTPUTS / "fm6_tcga_internal_pilot_summary.csv", index=False, lineterminator="\n")
    pd.DataFrame(folds).to_csv(OUTPUTS / "fm6_tcga_outer_fold_model_settings.csv", index=False, lineterminator="\n")
    bootstrap.to_csv(OUTPUTS / "fm6_tcga_patient_bootstrap_intervals.csv", index=False, lineterminator="\n")
    paired.to_csv(OUTPUTS / "fm6_tcga_paired_encoder_differences.csv", index=False, lineterminator="\n")
    within.to_csv(OUTPUTS / "fm6_tcga_within_encoder_contrasts.csv", index=False, lineterminator="\n")
    evidence_rows = []
    for row in summary.itertuples(index=False):
        association_ci = bootstrap[
            bootstrap.encoder.eq(row.encoder) & bootstrap.metric.eq("isup_only_risk")
        ].iloc[0]
        r_pass = bool(row.isup_spearman > 0 and row.isup_permutation_p_one_sided <= 0.05)
        a_pass = bool(association_ci.ci_low > 0.50)
        u_pass = bool(
            row.head_minimum_validity_pass
            and row.target_fixed_delta_use > 0
            and row.target_vs_random_p_one_sided <= 0.05
        )
        evidence_rows.append({
            "encoder": row.encoder,
            "R_recoverability": "PASS_WHOLE_TISSUE_DEVELOPMENT" if r_pass else "FAIL_OR_INCONCLUSIVE",
            "A_disease_association": "PASS_INTERNAL" if a_pass else "FAIL_OR_INCONCLUSIVE",
            "U_functional_sensitivity": "PASS_EXPLORATORY_WHOLE_TISSUE" if u_pass else "FAIL_OR_INCONCLUSIVE",
            "T_external_transport": "NOT_TESTED_LOCKED",
            "strong_H2": "PROHIBITED",
            "reason": "independent tumor-region truth, endpoint-equivalent external transport, power and embargo gates remain",
        })
    evidence_chain = pd.DataFrame(evidence_rows)
    evidence_chain.to_csv(OUTPUTS / "fm6_tcga_internal_evidence_chain.csv", index=False, lineterminator="\n")

    conch = oof_by_encoder["conch"]
    virchow = oof_by_encoder["virchow"]
    cross = pd.DataFrame([{
        "n_subjects": len(conch),
        "full_risk_spearman": safe_spearman(conch.full_risk.to_numpy(), virchow.full_risk.to_numpy()),
        "target_erasure_score_change_spearman": safe_spearman(
            (conch.full_risk - conch.target_fixed_risk).to_numpy(),
            (virchow.full_risk - virchow.target_fixed_risk).to_numpy(),
        ),
        "isup_probe_prediction_spearman": safe_spearman(conch.isup_prediction.to_numpy(), virchow.isup_prediction.to_numpy()),
        "interpretation": "paired internal whole-tissue development agreement; not external transport",
    }])
    cross.to_csv(OUTPUTS / "fm6_tcga_cross_encoder_agreement.csv", index=False, lineterminator="\n")
    event = conch.bcr_event.to_numpy(int)
    follow_up = conch.bcr_time_days.to_numpy(float)
    ensemble_full = (conch.full_risk.to_numpy(float) + virchow.full_risk.to_numpy(float)) / 2.0
    ensemble_erased = (
        conch.target_fixed_risk.to_numpy(float) + virchow.target_fixed_risk.to_numpy(float)
    ) / 2.0
    ensemble = pd.DataFrame([{
        "n_subjects": len(conch),
        "n_events": int(event.sum()),
        "mean_oof_risk_c_index": c_index(event, follow_up, ensemble_full),
        "mean_target_erased_oof_risk_c_index": c_index(event, follow_up, ensemble_erased),
        "mean_risk_delta_use": c_index(event, follow_up, ensemble_full) - c_index(event, follow_up, ensemble_erased),
        "interpretation": "fixed untrained mean of paired OOF encoder scores; internal development only",
    }])
    ensemble.to_csv(OUTPUTS / "fm6_tcga_cross_encoder_mean_score.csv", index=False, lineterminator="\n")

    # Approximate external planning power: rescale the TCGA patient-bootstrap SD by event count.
    power_rows = []
    rng = np.random.default_rng(SEED + 333)
    for encoder in summary.encoder:
        frame = oof_by_encoder[encoder]
        event = frame.bcr_event.to_numpy(int)
        time = frame.bcr_time_days.to_numpy(float)
        full = frame.full_risk.to_numpy(float)
        erased = frame.target_fixed_risk.to_numpy(float)
        delta = float(summary.loc[summary.encoder.eq(encoder), "target_fixed_delta_use"].iloc[0])
        draws = np.full(BOOTSTRAPS, np.nan)
        for index in range(BOOTSTRAPS):
            sample = rng.integers(0, len(frame), len(frame))
            try:
                draws[index] = c_index(event[sample], time[sample], full[sample]) - c_index(event[sample], time[sample], erased[sample])
            except Exception:
                pass
        sd_tcga = float(np.nanstd(draws, ddof=1))
        sd_external = sd_tcga * np.sqrt(80 / 27)
        random_p95 = float(summary.loc[summary.encoder.eq(encoder), "random_delta_p95"].iloc[0])
        simulated = rng.normal(delta, sd_external, size=100000)
        power = float(np.mean(simulated > random_p95))
        power_rows.append({
            "encoder": encoder,
            "development_subjects": 392,
            "development_events": 80,
            "external_candidate_subjects": 92,
            "external_candidate_events": 27,
            "observed_delta_use": delta,
            "development_bootstrap_sd": sd_tcga,
            "event_scaled_external_sd": sd_external,
            "matched_random_p95_threshold": random_p95,
            "approximate_directional_power": power,
            "power_status": "PASS_80_PERCENT" if power >= 0.80 else "FAIL_80_PERCENT_EXPLORATORY_ONLY",
            "limitation": "planning approximation; no CHIMERA model/outcome data used",
        })
    pd.DataFrame(power_rows).to_csv(OUTPUTS / "fm6_external_power_planning_approximation.csv", index=False, lineterminator="\n")

    report = [
        "# FM6 TCGA whole-tissue internal development pilot", "",
        "## Evidence scope", "",
        "This report is internal whole-tissue development evidence. It does not establish tumor-specific H1/H2, external transport, clinical validity, or a residual biomarker.", "",
        "## Primary results", "",
    ]
    for row in summary.itertuples(index=False):
        fixed_contrast = within[
            within.encoder.eq(row.encoder) & within.contrast_id.eq("full_minus_target_fixed")
        ].iloc[0]
        refit_contrast = within[
            within.encoder.eq(row.encoder) & within.contrast_id.eq("full_minus_target_refit")
        ].iloc[0]
        incremental_contrast = within[
            within.encoder.eq(row.encoder) & within.contrast_id.eq("isup_plus_ai_minus_isup_only")
        ].iloc[0]
        report.extend([
            f"### {row.encoder}", "",
            f"- Whole-tissue ISUP OOF Spearman: {row.isup_spearman:.3f}; MAE {row.isup_mae:.3f}; QWK {row.isup_qwk:.3f}; permutation p={row.isup_permutation_p_one_sided:.4f}",
            f"- BCR head OOF C-index: {row.bcr_full_c_index:.3f} (95% CI {row.bcr_full_c_index_ci_low:.3f}–{row.bcr_full_c_index_ci_high:.3f}); minimum-validity pass={row.head_minimum_validity_pass}",
            f"- ISUP-only / ISUP+AI C-index: {row.bcr_isup_only_c_index:.3f} / {row.bcr_isup_plus_ai_c_index:.3f}; paired delta 95% CI {incremental_contrast.ci_low:.3f}–{incremental_contrast.ci_high:.3f}",
            f"- ISUP-correlated fixed-head delta_use: {row.target_fixed_delta_use:.3f} (paired 95% CI {fixed_contrast.ci_low:.3f}–{fixed_contrast.ci_high:.3f}); matched-random p95 {row.random_delta_p95:.3f}; one-sided p={row.target_vs_random_p_one_sided:.4f}",
            f"- Refit delta_info: {row.target_refit_delta_info:.3f} (paired 95% CI {refit_contrast.ci_low:.3f}–{refit_contrast.ci_high:.3f})", "",
            f"- Secondary OOF recoverability: age rho={row.age_oof_spearman:.3f} (n={row.age_n}); path-T rho={row.path_t_stage_oof_spearman:.3f} (n={row.path_t_stage_n})",
            f"- AI-risk OOF explanation R2: ISUP={row.risk_explanation_isup_oof_r2:.3f}; ISUP+age+path-T={row.risk_explanation_panel_oof_r2:.3f}; delta={row.risk_explanation_panel_delta_r2:.3f}",
            f"- ISUP–AI risk Spearman / partial Spearman adjusted for age+path-T: {row.isup_ai_risk_spearman:.3f} / {row.isup_ai_risk_partial_spearman_age_stage:.3f}",
            f"- Complete-case clinical panel / clinical panel+AI C-index: {row.bcr_clinical_panel_c_index_complete_case:.3f} / {row.bcr_clinical_panel_plus_ai_c_index_complete_case:.3f}", "",
            f"- Technical correlations with AI risk (Spearman): tissue={row.risk_thumbnail_tissue_fraction_spearman:.3f}, MPP={row.risk_mean_mpp_spearman:.3f}, slide count={row.risk_n_slides_spearman:.3f}", "",
        ])
    report.extend([
        "## R/A/U/T gate interpretation", "",
        *[
            f"- {row.encoder}: R={row.R_recoverability}; A={row.A_disease_association}; U={row.U_functional_sensitivity}; T={row.T_external_transport}; strong H2={row.strong_H2}"
            for row in evidence_chain.itertuples(index=False)
        ], "",
        "## Interpretation boundary", "",
        "A positive fixed-head effect would show sensitivity to a whole-tissue direction correlated with ISUP, not proof that a tumor-specific ISUP mechanism caused the BCR judgment. Independent tumor-region truth, endpoint-equivalent external transport, adequate power, and embargo clearance remain required for strong H2.", "",
    ])
    (OUTPUTS / "fm6-tcga-internal-development-pilot-report.md").write_text("\n".join(report) + "\n")
    generated = sorted(path for path in OUTPUTS.iterdir() if path.is_file())
    config = {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "bootstraps": BOOTSTRAPS,
        "random_controls": RANDOM_CONTROLS,
        "permuted_controls": PERMUTED_CONTROLS,
        "isup_permutations": ISUP_PERMUTATIONS,
        "pca_components": PCA_COMPONENTS,
        "ridge_alphas": RIDGE_ALPHAS.tolist(),
        "cox_alphas": COX_ALPHAS.tolist(),
        "secondary_clinical_source": str(SECONDARY_CLINICAL.relative_to(ROOT)),
        "secondary_clinical_sha256": sha256_file(SECONDARY_CLINICAL),
        "secondary_clinical_allowed_fields": ["AGE", "PATH_T_STAGE"],
        "secondary_outcome_fields_used": [],
        "output_hashes": {
            path.name: sha256_file(path)
            for path in generated
            if path.name not in {
                "fm6_tcga_internal_pilot_analysis_run_config.json",
                "fm6_figure_manifest.csv",
            }
        },
        "claim_ceiling": "internal whole-tissue development evidence only",
    }
    (OUTPUTS / "fm6_tcga_internal_pilot_analysis_run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(summary.to_string(index=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
