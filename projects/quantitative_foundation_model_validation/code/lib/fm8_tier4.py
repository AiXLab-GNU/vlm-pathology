"""Leakage-controlled utilities for FM8 whole-tissue Tier 4 discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored


LATENT_RANKS = (4, 8, 16, 32)
LATENT_ALPHAS = (1.0, 10.0, 100.0, 1000.0)
PROJECTION_ALPHAS = (1.0, 10.0, 100.0, 1000.0)
SMALL_COX_ALPHAS = (0.1, 1.0, 10.0, 100.0)
MODEL_COLUMNS = (
    "baseline_risk",
    "latent_risk",
    "additive_risk",
    "interaction_risk",
)


def survival_target(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.asarray(
        [(bool(e), float(t)) for e, t in zip(event, time, strict=True)],
        dtype=[("event", "?"), ("time", "<f8")],
    )


def harrell_c_index(event: np.ndarray, time: np.ndarray, risk: np.ndarray) -> float:
    event = np.asarray(event, dtype=bool)
    time = np.asarray(time, dtype=float)
    risk = np.asarray(risk, dtype=float)
    if len(event) < 2 or event.sum() == 0 or not np.isfinite(risk).all():
        return np.nan
    try:
        return float(concordance_index_censored(event, time, risk)[0])
    except Exception:
        return np.nan


@dataclass
class KnownProjector:
    x_scaler: StandardScaler
    panel_mean: np.ndarray
    panel_scale: np.ndarray
    active_panel_columns: np.ndarray
    directions: np.ndarray
    alpha: float


def _panel_scaling(panel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    panel = np.asarray(panel, dtype=float)
    mean = np.nanmean(panel, axis=0)
    scale = np.nanstd(panel, axis=0, ddof=0)
    active = np.isfinite(mean) & np.isfinite(scale) & (scale > 1e-12)
    safe_scale = np.where(active, scale, 1.0)
    return mean, safe_scale, active


def fit_known_projector(x: np.ndarray, panel: np.ndarray, alpha: float) -> KnownProjector:
    x = np.asarray(x, dtype=float)
    panel = np.asarray(panel, dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(panel).all():
        raise RuntimeError("known-projector input contains nonfinite values")
    scaler = StandardScaler().fit(x)
    xs = scaler.transform(x)
    panel_mean, panel_scale, active = _panel_scaling(panel)
    if not active.any():
        directions = np.zeros((x.shape[1], 0), dtype=float)
    else:
        ys = (panel[:, active] - panel_mean[active]) / panel_scale[active]
        ridge = Ridge(alpha=float(alpha), fit_intercept=False).fit(xs, ys)
        coefficients = np.atleast_2d(ridge.coef_)
        q, r = np.linalg.qr(coefficients.T, mode="reduced")
        keep = np.abs(np.diag(r)) > 1e-10
        directions = q[:, keep]
    return KnownProjector(
        x_scaler=scaler,
        panel_mean=panel_mean,
        panel_scale=panel_scale,
        active_panel_columns=active,
        directions=directions,
        alpha=float(alpha),
    )


def apply_known_projector(projector: KnownProjector, x: np.ndarray) -> np.ndarray:
    xs = projector.x_scaler.transform(np.asarray(x, dtype=float))
    if projector.directions.shape[1] == 0:
        return xs
    return xs - (xs @ projector.directions) @ projector.directions.T


def _projection_validation_mse(
    train_x: np.ndarray,
    train_panel: np.ndarray,
    test_x: np.ndarray,
    test_panel: np.ndarray,
    alpha: float,
) -> float:
    x_scaler = StandardScaler().fit(train_x)
    panel_mean, panel_scale, active = _panel_scaling(train_panel)
    if not active.any():
        return 0.0
    train_y = (train_panel[:, active] - panel_mean[active]) / panel_scale[active]
    test_y = (test_panel[:, active] - panel_mean[active]) / panel_scale[active]
    model = Ridge(alpha=float(alpha), fit_intercept=False).fit(
        x_scaler.transform(train_x), train_y
    )
    prediction = model.predict(x_scaler.transform(test_x))
    return float(np.mean((test_y - prediction) ** 2))


def select_projection_alpha(
    x: np.ndarray, panel: np.ndarray, folds: np.ndarray
) -> tuple[float, pd.DataFrame]:
    rows: list[dict[str, float]] = []
    unique = np.unique(folds)
    for alpha in PROJECTION_ALPHAS:
        scores = []
        for fold in unique:
            train = folds != fold
            test = folds == fold
            scores.append(
                _projection_validation_mse(
                    x[train], panel[train], x[test], panel[test], alpha
                )
            )
        mean = float(np.mean(scores))
        se = float(np.std(scores, ddof=1) / np.sqrt(len(scores))) if len(scores) > 1 else 0.0
        rows.append({"alpha": float(alpha), "mean_mse": mean, "mse_se": se})
    table = pd.DataFrame(rows)
    best = table.sort_values(["mean_mse", "alpha"], ascending=[True, False]).iloc[0]
    eligible = table[table.mean_mse <= float(best.mean_mse + best.mse_se)]
    selected = eligible.sort_values("alpha", ascending=False).iloc[0]
    return float(selected.alpha), table


@dataclass
class LatentModel:
    projector: KnownProjector
    pca: PCA
    cox: CoxPHSurvivalAnalysis
    risk_mean: float
    risk_scale: float
    rank: int
    alpha: float
    projection_alpha: float


def fit_latent_model(
    x: np.ndarray,
    panel: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    *,
    rank: int,
    alpha: float,
    projection_alpha: float,
    seed: int,
) -> LatentModel:
    projector = fit_known_projector(x, panel, projection_alpha)
    residual = apply_known_projector(projector, x)
    actual_rank = min(int(rank), residual.shape[1], len(residual) - 1)
    if actual_rank < 1:
        raise RuntimeError("latent PCA has no valid component")
    pca = PCA(n_components=actual_rank, svd_solver="randomized", random_state=int(seed))
    z = pca.fit_transform(residual)
    cox = CoxPHSurvivalAnalysis(alpha=float(alpha), n_iter=300)
    cox.fit(z, survival_target(event, time))
    risk = cox.predict(z)
    risk_scale = float(np.std(risk, ddof=0))
    if not np.isfinite(risk_scale) or risk_scale <= 1e-10:
        risk_scale = 1.0
    return LatentModel(
        projector=projector,
        pca=pca,
        cox=cox,
        risk_mean=float(np.mean(risk)),
        risk_scale=risk_scale,
        rank=actual_rank,
        alpha=float(alpha),
        projection_alpha=float(projection_alpha),
    )


def predict_latent(model: LatentModel, x: np.ndarray) -> np.ndarray:
    residual = apply_known_projector(model.projector, x)
    risk = model.cox.predict(model.pca.transform(residual))
    return (risk - model.risk_mean) / model.risk_scale


def select_one_se(table: pd.DataFrame) -> pd.Series:
    required = {"rank", "alpha", "mean_score", "score_se"}
    if not required.issubset(table.columns):
        raise RuntimeError(f"one-SE table missing columns: {sorted(required - set(table.columns))}")
    finite = table[np.isfinite(table.mean_score)].copy()
    if finite.empty:
        raise RuntimeError("no finite model-selection score")
    best = finite.sort_values(
        ["mean_score", "rank", "alpha"], ascending=[False, True, False]
    ).iloc[0]
    eligible = finite[finite.mean_score >= float(best.mean_score - best.score_se)]
    return eligible.sort_values(["rank", "alpha"], ascending=[True, False]).iloc[0]


def cross_validated_latent_selection(
    x: np.ndarray,
    panel: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    folds: np.ndarray,
    *,
    seed: int,
) -> tuple[dict[str, float | int], np.ndarray, pd.DataFrame, pd.DataFrame]:
    projection_alpha, projection_table = select_projection_alpha(x, panel, folds)
    unique = np.unique(folds)
    predictions: dict[tuple[int, float], np.ndarray] = {
        (rank, alpha): np.full(len(x), np.nan, dtype=float)
        for rank in LATENT_RANKS
        for alpha in LATENT_ALPHAS
    }
    fold_scores: dict[tuple[int, float], list[float]] = {
        key: [] for key in predictions
    }
    for fold in unique:
        train = folds != fold
        test = folds == fold
        projector = fit_known_projector(x[train], panel[train], projection_alpha)
        train_residual = apply_known_projector(projector, x[train])
        test_residual = apply_known_projector(projector, x[test])
        max_rank = min(max(LATENT_RANKS), train_residual.shape[1], train.sum() - 1)
        pca = PCA(n_components=max_rank, svd_solver="randomized", random_state=int(seed + fold))
        train_z_full = pca.fit_transform(train_residual)
        test_z_full = pca.transform(test_residual)
        for rank in LATENT_RANKS:
            actual_rank = min(rank, max_rank)
            train_z = train_z_full[:, :actual_rank]
            test_z = test_z_full[:, :actual_rank]
            for alpha in LATENT_ALPHAS:
                key = (rank, alpha)
                try:
                    cox = CoxPHSurvivalAnalysis(alpha=float(alpha), n_iter=300)
                    cox.fit(train_z, survival_target(event[train], time[train]))
                    train_risk = cox.predict(train_z)
                    scale = max(float(np.std(train_risk, ddof=0)), 1e-10)
                    test_risk = (cox.predict(test_z) - float(np.mean(train_risk))) / scale
                    predictions[key][test] = test_risk
                    fold_scores[key].append(harrell_c_index(event[test], time[test], test_risk))
                except Exception:
                    fold_scores[key].append(np.nan)
    rows = []
    for (rank, alpha), values in fold_scores.items():
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        mean = float(np.mean(finite)) if len(finite) else np.nan
        se = (
            float(np.std(finite, ddof=1) / np.sqrt(len(finite)))
            if len(finite) > 1
            else 0.0
        )
        rows.append(
            {
                "rank": rank,
                "alpha": alpha,
                "mean_score": mean,
                "score_se": se,
                "oof_c_index": harrell_c_index(event, time, predictions[(rank, alpha)]),
                "valid_folds": len(finite),
            }
        )
    table = pd.DataFrame(rows)
    selected = select_one_se(table)
    key = (int(selected["rank"]), float(selected["alpha"]))
    oof = predictions[key]
    if not np.isfinite(oof).all():
        raise RuntimeError("selected latent model did not produce complete inner OOF scores")
    config: dict[str, float | int] = {
        "rank": key[0],
        "alpha": key[1],
        "projection_alpha": projection_alpha,
    }
    return config, oof, table, projection_table


@dataclass
class SmallCoxModel:
    scaler: StandardScaler
    cox: CoxPHSurvivalAnalysis
    risk_mean: float
    risk_scale: float
    alpha: float


def fit_small_cox(
    features: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    alpha: float,
) -> SmallCoxModel:
    scaler = StandardScaler().fit(features)
    z = scaler.transform(features)
    cox = CoxPHSurvivalAnalysis(alpha=float(alpha), n_iter=300)
    cox.fit(z, survival_target(event, time))
    risk = cox.predict(z)
    scale = max(float(np.std(risk, ddof=0)), 1e-10)
    return SmallCoxModel(scaler, cox, float(np.mean(risk)), scale, float(alpha))


def predict_small_cox(model: SmallCoxModel, features: np.ndarray) -> np.ndarray:
    risk = model.cox.predict(model.scaler.transform(features))
    return (risk - model.risk_mean) / model.risk_scale


def select_small_cox_alpha(
    features: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    folds: np.ndarray,
) -> tuple[float, pd.DataFrame]:
    rows = []
    for alpha in SMALL_COX_ALPHAS:
        scores = []
        for fold in np.unique(folds):
            train = folds != fold
            test = folds == fold
            try:
                model = fit_small_cox(features[train], event[train], time[train], alpha)
                score = harrell_c_index(
                    event[test], time[test], predict_small_cox(model, features[test])
                )
            except Exception:
                score = np.nan
            scores.append(score)
        finite = np.asarray(scores, dtype=float)
        finite = finite[np.isfinite(finite)]
        mean = float(np.mean(finite)) if len(finite) else np.nan
        se = (
            float(np.std(finite, ddof=1) / np.sqrt(len(finite)))
            if len(finite) > 1
            else 0.0
        )
        rows.append(
            {"alpha": float(alpha), "mean_score": mean, "score_se": se, "valid_folds": len(finite)}
        )
    table = pd.DataFrame(rows)
    finite = table[np.isfinite(table.mean_score)].copy()
    if finite.empty:
        raise RuntimeError("no finite small-Cox selection score")
    best = finite.sort_values(["mean_score", "alpha"], ascending=[False, False]).iloc[0]
    eligible = finite[finite.mean_score >= float(best.mean_score - best.score_se)]
    selected = eligible.sort_values("alpha", ascending=False).iloc[0]
    return float(selected.alpha), table


def stacked_features(isup: np.ndarray, latent: np.ndarray, family: str) -> np.ndarray:
    isup = np.asarray(isup, dtype=float)
    latent = np.asarray(latent, dtype=float)
    if family == "baseline":
        return isup[:, None]
    if family == "additive":
        return np.column_stack([isup, latent])
    if family == "interaction":
        return np.column_stack([isup, latent, isup * latent])
    raise ValueError(f"unknown stacked family: {family}")


def outer_oof_predictions(
    x: np.ndarray,
    panel: np.ndarray,
    isup: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    folds: np.ndarray,
    *,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictions = pd.DataFrame(
        {
            "outer_fold": folds.astype(int),
            "event": event.astype(int),
            "time": time.astype(float),
            "isup": isup.astype(float),
            "baseline_risk": np.nan,
            "latent_risk": np.nan,
            "additive_risk": np.nan,
            "interaction_risk": np.nan,
            "prediction_count": 0,
        }
    )
    setting_rows: list[dict[str, object]] = []
    selection_rows: list[pd.DataFrame] = []
    for outer_fold in np.unique(folds):
        train = folds != outer_fold
        test = folds == outer_fold
        inner_folds = folds[train]
        config, inner_latent, latent_table, projection_table = cross_validated_latent_selection(
            x[train], panel[train], event[train], time[train], inner_folds, seed=seed + int(outer_fold) * 100
        )
        latent_model = fit_latent_model(
            x[train],
            panel[train],
            event[train],
            time[train],
            rank=int(config["rank"]),
            alpha=float(config["alpha"]),
            projection_alpha=float(config["projection_alpha"]),
            seed=seed + int(outer_fold),
        )
        test_latent = predict_latent(latent_model, x[test])
        predictions.loc[test, "latent_risk"] = test_latent
        for family, column in [
            ("baseline", "baseline_risk"),
            ("additive", "additive_risk"),
            ("interaction", "interaction_risk"),
        ]:
            train_features = stacked_features(isup[train], inner_latent, family)
            test_features = stacked_features(isup[test], test_latent, family)
            alpha, small_table = select_small_cox_alpha(
                train_features, event[train], time[train], inner_folds
            )
            model = fit_small_cox(train_features, event[train], time[train], alpha)
            predictions.loc[test, column] = predict_small_cox(model, test_features)
            selected_row = small_table.copy()
            selected_row.insert(0, "outer_fold", int(outer_fold))
            selected_row.insert(1, "selection_family", family)
            selection_rows.append(selected_row)
            setting_rows.append(
                {
                    "outer_fold": int(outer_fold),
                    "model_family": family,
                    "alpha": alpha,
                    "latent_rank": int(config["rank"]),
                    "latent_alpha": float(config["alpha"]),
                    "projection_alpha": float(config["projection_alpha"]),
                }
            )
        latent_selection = latent_table.copy()
        latent_selection.insert(0, "outer_fold", int(outer_fold))
        latent_selection.insert(1, "selection_family", "latent")
        selection_rows.append(latent_selection)
        projection_selection = projection_table.rename(
            columns={"mean_mse": "mean_score", "mse_se": "score_se"}
        )
        projection_selection["mean_score"] *= -1
        projection_selection.insert(0, "outer_fold", int(outer_fold))
        projection_selection.insert(1, "selection_family", "projection")
        selection_rows.append(projection_selection)
        predictions.loc[test, "prediction_count"] += 1
    if not np.isfinite(predictions[list(MODEL_COLUMNS)].to_numpy()).all():
        raise RuntimeError("source OOF predictions contain nonfinite values")
    return predictions, pd.DataFrame(setting_rows), pd.concat(selection_rows, ignore_index=True, sort=False)


@dataclass
class FinalSourceModels:
    latent: LatentModel
    baseline: SmallCoxModel
    additive: SmallCoxModel
    interaction: SmallCoxModel
    source_stacking_latent: np.ndarray
    settings: dict[str, float | int]


def fit_final_source_models(
    x: np.ndarray,
    panel: np.ndarray,
    isup: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    folds: np.ndarray,
    *,
    seed: int,
) -> tuple[FinalSourceModels, pd.DataFrame]:
    config, stacking_latent, latent_table, projection_table = cross_validated_latent_selection(
        x, panel, event, time, folds, seed=seed
    )
    latent = fit_latent_model(
        x,
        panel,
        event,
        time,
        rank=int(config["rank"]),
        alpha=float(config["alpha"]),
        projection_alpha=float(config["projection_alpha"]),
        seed=seed,
    )
    models: dict[str, SmallCoxModel] = {}
    settings: dict[str, float | int] = dict(config)
    selection_rows = []
    for family in ("baseline", "additive", "interaction"):
        features = stacked_features(isup, stacking_latent, family)
        alpha, table = select_small_cox_alpha(features, event, time, folds)
        models[family] = fit_small_cox(features, event, time, alpha)
        settings[f"{family}_alpha"] = alpha
        table.insert(0, "selection_family", family)
        selection_rows.append(table)
    latent_table.insert(0, "selection_family", "latent")
    selection_rows.append(latent_table)
    projection_table = projection_table.rename(
        columns={"mean_mse": "mean_score", "mse_se": "score_se"}
    )
    projection_table["mean_score"] *= -1
    projection_table.insert(0, "selection_family", "projection")
    selection_rows.append(projection_table)
    bundle = FinalSourceModels(
        latent=latent,
        baseline=models["baseline"],
        additive=models["additive"],
        interaction=models["interaction"],
        source_stacking_latent=stacking_latent,
        settings=settings,
    )
    return bundle, pd.concat(selection_rows, ignore_index=True, sort=False)


def predict_external_models(
    models: FinalSourceModels, x: np.ndarray, isup: np.ndarray
) -> pd.DataFrame:
    latent = predict_latent(models.latent, x)
    return pd.DataFrame(
        {
            "baseline_risk": predict_small_cox(
                models.baseline, stacked_features(isup, latent, "baseline")
            ),
            "latent_risk": latent,
            "additive_risk": predict_small_cox(
                models.additive, stacked_features(isup, latent, "additive")
            ),
            "interaction_risk": predict_small_cox(
                models.interaction, stacked_features(isup, latent, "interaction")
            ),
        }
    )


def validate_oof_coverage(frame: pd.DataFrame, expected_subjects: Iterable[str]) -> None:
    expected = set(expected_subjects)
    if set(frame.subject_id.astype(str)) != expected:
        raise RuntimeError("OOF subject membership changed")
    if frame.subject_id.astype(str).duplicated().any():
        raise RuntimeError("OOF subject is duplicated")
    if not frame.prediction_count.eq(1).all():
        raise RuntimeError("each source subject must receive exactly one OOF prediction")


def _performance_values(frame: pd.DataFrame) -> dict[str, float]:
    values = {
        "baseline_c_index": harrell_c_index(frame.event, frame.time, frame.baseline_risk),
        "latent_only_c_index": harrell_c_index(frame.event, frame.time, frame.latent_risk),
        "additive_c_index": harrell_c_index(frame.event, frame.time, frame.additive_risk),
        "interaction_c_index": harrell_c_index(frame.event, frame.time, frame.interaction_risk),
    }
    values["delta_additive"] = values["additive_c_index"] - values["baseline_c_index"]
    values["delta_interaction"] = values["interaction_c_index"] - values["additive_c_index"]
    return values


def patient_bootstrap_performance(
    frame: pd.DataFrame,
    *,
    cohort: str,
    encoder: str,
    draws: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    point = _performance_values(frame)
    rng = np.random.default_rng(int(seed))
    rows = []
    for replicate in range(int(draws)):
        index = rng.integers(0, len(frame), len(frame))
        sampled = frame.iloc[index]
        values = _performance_values(sampled)
        values.update({"replicate": replicate, "cohort": cohort, "encoder": encoder})
        rows.append(values)
    replicate_table = pd.DataFrame(rows)
    summaries = []
    for metric, estimate in point.items():
        values = replicate_table[metric].to_numpy(float)
        valid = values[np.isfinite(values)]
        low, high = (np.quantile(valid, [0.025, 0.975]) if len(valid) else (np.nan, np.nan))
        summaries.append(
            {
                "cohort": cohort,
                "encoder": encoder,
                "metric": metric,
                "estimate": estimate,
                "ci_low": float(low),
                "ci_high": float(high),
                "n_valid": int(len(valid)),
                "n_undefined": int(draws - len(valid)),
            }
        )
    return pd.DataFrame(summaries), replicate_table


def coefficient_bootstrap(
    features: np.ndarray,
    event: np.ndarray,
    time: np.ndarray,
    *,
    alpha: float,
    coefficient_index: int,
    draws: int,
    seed: int,
) -> dict[str, float | int]:
    model = fit_small_cox(features, event, time, alpha)
    estimate = float(model.cox.coef_[coefficient_index])
    rng = np.random.default_rng(int(seed))
    values = np.full(draws, np.nan)
    for replicate in range(draws):
        index = rng.integers(0, len(event), len(event))
        try:
            fitted = fit_small_cox(features[index], event[index], time[index], alpha)
            values[replicate] = float(fitted.cox.coef_[coefficient_index])
        except Exception:
            continue
    valid = values[np.isfinite(values)]
    low, high = (np.quantile(valid, [0.025, 0.975]) if len(valid) else (np.nan, np.nan))
    return {
        "coefficient": estimate,
        "hazard_ratio_per_model_sd": float(np.exp(estimate)),
        "ci_low": float(low),
        "ci_high": float(high),
        "hazard_ratio_ci_low": float(np.exp(low)),
        "hazard_ratio_ci_high": float(np.exp(high)),
        "n_valid": int(len(valid)),
        "n_undefined": int(draws - len(valid)),
    }


def assign_functional_roles(
    *,
    source: dict[str, float | int],
    external: dict[str, float],
    shortcut_status: str,
) -> dict[str, str]:
    standalone = (
        float(source["latent_only"]) > 0.5
        and float(external["latent_only"]) > 0.5
        and int(source["positive_fold_count"]) >= 4
    )
    complementary = (
        float(source["delta_additive"]) > 0
        and float(external["delta_additive"]) > 0
    )
    interactive = (
        float(source["interaction_coefficient"]) != 0
        and float(source["delta_interaction"]) > 0
        and float(external["delta_interaction"]) > 0
    )
    redundant = standalone and abs(float(external["delta_additive"])) <= 0.01
    reproduced = standalone or complementary or interactive or redundant
    if shortcut_status in {"FAIL_MATERIAL_ASSOCIATION", "PARTIAL_NOT_EVALUABLE"}:
        reproduction = "not_qualified_shortcut_unresolved"
    elif reproduced:
        reproduction = "externally_reproduced_tier4"
    else:
        reproduction = "not_reproduced"
    return {
        "standalone_status": "supported" if standalone else "not_supported",
        "complementary_status": "supported" if complementary else "not_supported",
        "interaction_status": "supported" if interactive else "not_supported",
        "redundancy_status": "supported" if redundant else "not_supported",
        "external_reproduction_status": reproduction,
    }


def endpoint_lane_readiness() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "endpoint": "bcr",
                "source_cohort": "TCGA-PRAD",
                "external_cohort": "CHIMERA",
                "analysis_unit": "patient",
                "label_contract": "bcr_event_plus_follow_up_time_cohort_specific_units_no_pooling",
                "status": "READY",
                "required_action": "run_locked_tier4_analysis",
            },
            {
                "endpoint": "cancer_presence",
                "source_cohort": "NADT",
                "external_cohort": "PANDA",
                "analysis_unit": "patient_required",
                "label_contract": "benign_vs_cancer_uncertain_hgpin_atypical_preserved",
                "status": "NOT_READY",
                "required_action": "hash_locked_shared_manifest_qfm_use_authorization_patient_id_and_label_map",
            },
            {
                "endpoint": "grading",
                "source_cohort": "NADT_cancer",
                "external_cohort": "PANDA_cancer",
                "analysis_unit": "patient_required",
                "label_contract": "ordinal_isup_or_gleason_cancer_only_benign_excluded",
                "status": "NOT_READY",
                "required_action": "hash_locked_shared_manifest_qfm_use_authorization_patient_id_and_ordinal_label_map",
            },
        ]
    )
