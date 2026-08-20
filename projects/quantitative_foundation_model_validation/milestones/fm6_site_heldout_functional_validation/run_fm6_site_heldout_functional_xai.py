#!/usr/bin/env python3
"""Run the prespecified TCGA tissue-source-site-held-out FM6 XAI validation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm6_site_heldout_functional_validation"
OUTPUTS = MILESTONE / "outputs"
INTERNAL_MILESTONE = PROJECT / "milestones/fm6_internal_development_pilot"
INTERNAL_OUTPUTS = INTERNAL_MILESTONE / "outputs"
INTERNAL_ARTIFACTS = (
    ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot"
)
SOURCE = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/tcga_prad_current_gdc_bcr"

INTERNAL_ANALYSIS = INTERNAL_MILESTONE / "analyze_fm6_tcga_internal_pilot.py"
SPEC = importlib.util.spec_from_file_location("fm6_internal_analysis", INTERNAL_ANALYSIS)
BASE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BASE)

SEED = 260820
PCA_COMPONENTS = 64
RIDGE_ALPHA = 1000.0
COX_ALPHA = 1000.0
RANDOM_CONTROLS = 100
BOOTSTRAPS = 2000
MIN_SITE_SUBJECTS = 20
MIN_SITE_EVENTS = 5
EXPECTED_SITES = ("EJ", "G9", "HC", "J4", "KK", "V1", "YL")
EXPECTED_SUBJECTS = 392
EXPECTED_EVENTS = 80
EXPECTED_EVALUATION_SUBJECTS = 289
EXPECTED_EVALUATION_EVENTS = 69
EXPECTED_INPUT_SHA256 = {
    "development_subjects.csv": "c36bfc442f6f33aaa6887eb6882c62f8984561e2336a35b6ab30eab370e1d814",
    "fm6_tcga_conch_tile_embeddings.npy": "99c6d5f3bc59070a7c2e74f3c6f3adc3f7f8db5cf6d8837465bde955953e9d2d",
    "fm6_tcga_virchow_tile_embeddings.npy": "4e23555436084c1154dbfdd94df86ddff556617fa41864615fb505f438f17ca7",
    "fm6_tcga_whole_tissue_tile_manifest.csv": "d4fe8ba50ec0e129ebcc7e5b529b4d26bb724de89f8869bb06648716ab4a9c04",
}


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def tissue_source_site(case_id: str) -> str:
    parts = str(case_id).split("-")
    if len(parts) < 3 or parts[0] != "TCGA" or len(parts[1]) != 2:
        raise ValueError(f"invalid TCGA case barcode: {case_id}")
    return parts[1]


def source_site_table(subjects: pd.DataFrame) -> pd.DataFrame:
    frame = subjects[["case_id", "bcr_event"]].copy()
    frame["tissue_source_site"] = frame.case_id.map(tissue_source_site)
    table = (
        frame.groupby("tissue_source_site", sort=True)
        .agg(n_subjects=("case_id", "size"), n_events=("bcr_event", "sum"))
        .reset_index()
    )
    table["evaluation_eligible"] = (
        table.n_subjects.ge(MIN_SITE_SUBJECTS) & table.n_events.ge(MIN_SITE_EVENTS)
    )
    return table


def verify_inputs() -> dict[str, str]:
    paths = {
        "development_subjects.csv": SOURCE / "development_subjects.csv",
        "fm6_tcga_conch_tile_embeddings.npy": INTERNAL_ARTIFACTS / "fm6_tcga_conch_tile_embeddings.npy",
        "fm6_tcga_virchow_tile_embeddings.npy": INTERNAL_ARTIFACTS / "fm6_tcga_virchow_tile_embeddings.npy",
        "fm6_tcga_whole_tissue_tile_manifest.csv": INTERNAL_OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv",
    }
    observed = {name: sha256_file(path) for name, path in paths.items()}
    if observed != EXPECTED_INPUT_SHA256:
        raise RuntimeError(f"FM6 input hash mismatch: {observed}")
    paired = json.loads((INTERNAL_OUTPUTS / "fm6_tcga_paired_embedding_audit.json").read_text())
    if paired.get("status") != "PASS" or not paired.get("crop_hashes_identical_across_encoders"):
        raise RuntimeError("paired embedding audit is not locked PASS")
    return observed


def survival_target(event: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.asarray(
        [(bool(e), float(t)) for e, t in zip(event, time, strict=True)],
        dtype=[("event", "?"), ("time", "<f8")],
    )


def fit_head(
    x_train: np.ndarray, event_train: np.ndarray, time_train: np.ndarray
) -> tuple[StandardScaler, PCA, CoxPHSurvivalAnalysis, float, float]:
    scaler = StandardScaler()
    xs_train = scaler.fit_transform(x_train)
    pca = PCA(
        n_components=min(PCA_COMPONENTS, len(x_train) - 1, x_train.shape[1]),
        svd_solver="randomized",
        random_state=SEED,
    )
    z_train = pca.fit_transform(xs_train)
    cox = CoxPHSurvivalAnalysis(alpha=COX_ALPHA, n_iter=200)
    cox.fit(z_train, survival_target(event_train, time_train))
    train_risk = cox.predict(z_train)
    return (
        scaler,
        pca,
        cox,
        float(train_risk.mean()),
        float(max(train_risk.std(ddof=0), 1e-8)),
    )


def predict_standardized_head(
    model: tuple[StandardScaler, PCA, CoxPHSurvivalAnalysis, float, float],
    x: np.ndarray,
) -> np.ndarray:
    scaler, pca, cox, mean, standard_deviation = model
    return (cox.predict(pca.transform(scaler.transform(x))) - mean) / standard_deviation


def predict_scaled_head(
    model: tuple[StandardScaler, PCA, CoxPHSurvivalAnalysis, float, float],
    xs: np.ndarray,
) -> np.ndarray:
    _, pca, cox, mean, standard_deviation = model
    return (cox.predict(pca.transform(xs)) - mean) / standard_deviation


def concordance_counts(
    event: np.ndarray, time: np.ndarray, risk: np.ndarray
) -> tuple[float, float]:
    result = concordance_index_censored(
        event.astype(bool), time.astype(float), risk.astype(float)
    )
    numerator = float(result[1]) + 0.5 * float(result[3])
    denominator = float(result[1] + result[2] + result[3])
    if denominator <= 0:
        raise ValueError("no comparable survival pairs")
    return numerator, denominator


def stratified_c_index(
    event: np.ndarray, time: np.ndarray, risk: np.ndarray, site: np.ndarray
) -> float:
    numerator = 0.0
    denominator = 0.0
    for value in sorted(np.unique(site)):
        selected = site == value
        try:
            site_numerator, site_denominator = concordance_counts(
                event[selected], time[selected], risk[selected]
            )
        except ValueError:
            continue
        numerator += site_numerator
        denominator += site_denominator
    if denominator <= 0:
        raise ValueError("no stratified comparable survival pairs")
    return numerator / denominator


def ordinary_c_index(event: np.ndarray, time: np.ndarray, risk: np.ndarray) -> float:
    return float(
        concordance_index_censored(
            event.astype(bool), time.astype(float), risk.astype(float)
        )[0]
    )


def analyze_encoder(
    encoder: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float]]:
    subject, x, _ = BASE.load_subject_data(encoder)
    subject = subject.copy()
    subject["tissue_source_site"] = subject.case_id.map(tissue_source_site)
    site_table = source_site_table(subject)
    eligible_sites = tuple(site_table.loc[site_table.evaluation_eligible, "tissue_source_site"])
    if eligible_sites != EXPECTED_SITES:
        raise RuntimeError(f"eligible site universe changed: {eligible_sites}")
    event = subject.bcr_event.to_numpy(int)
    time = subject.bcr_time_days.to_numpy(float)
    isup = subject.isup_grade_group.to_numpy(float)
    sites = subject.tissue_source_site.to_numpy(str)

    prediction_rows: list[dict[str, object]] = []
    site_rows: list[dict[str, object]] = []
    random_by_site: dict[str, np.ndarray] = {}

    for site_index, held_out_site in enumerate(eligible_sites):
        test = sites == held_out_site
        train = ~test
        model = fit_head(x[train], event[train], time[train])
        scaler = model[0]
        xs_train = scaler.transform(x[train])
        xs_test = scaler.transform(x[test])
        direction = Ridge(alpha=RIDGE_ALPHA).fit(xs_train, isup[train]).coef_.astype(float)
        full_risk = predict_standardized_head(model, x[test])
        erased_test = BASE.erase_direction(xs_test, direction)
        target_risk = predict_scaled_head(model, erased_test)
        probe_prediction = Ridge(alpha=RIDGE_ALPHA).fit(xs_train, isup[train]).predict(xs_test)

        rng = np.random.default_rng(
            SEED + 1000 * (1 if encoder == "conch" else 2) + site_index
        )
        random_directions, variance_ratios, concept_cosines = BASE.variance_matched_random_directions(
            xs_train, direction, RANDOM_CONTROLS, rng
        )
        random_risk = np.empty((RANDOM_CONTROLS, int(test.sum())), dtype=np.float64)
        for draw, random_direction in enumerate(random_directions):
            random_risk[draw] = predict_scaled_head(
                model, BASE.erase_direction(xs_test, random_direction)
            )
        random_by_site[held_out_site] = random_risk

        test_subject = subject.loc[test].reset_index(drop=True)
        for index, row in test_subject.iterrows():
            prediction_rows.append(
                {
                    "encoder": encoder,
                    "case_id": row.case_id,
                    "tissue_source_site": held_out_site,
                    "bcr_event": int(row.bcr_event),
                    "bcr_time_days": float(row.bcr_time_days),
                    "isup_grade_group": float(row.isup_grade_group),
                    "isup_prediction": float(probe_prediction[index]),
                    "full_risk": float(full_risk[index]),
                    "target_erased_risk": float(target_risk[index]),
                }
            )

        full_c = ordinary_c_index(event[test], time[test], full_risk)
        target_c = ordinary_c_index(event[test], time[test], target_risk)
        site_rows.append(
            {
                "encoder": encoder,
                "tissue_source_site": held_out_site,
                "n_train": int(train.sum()),
                "events_train": int(event[train].sum()),
                "n_test": int(test.sum()),
                "events_test": int(event[test].sum()),
                "full_c_index": full_c,
                "target_erased_c_index": target_c,
                "delta_use": full_c - target_c,
                "isup_spearman": float(stats.spearmanr(isup[test], probe_prediction).statistic),
                "random_removed_variance_ratio_median": float(np.median(variance_ratios)),
                "random_removed_variance_ratio_min": float(np.min(variance_ratios)),
                "random_removed_variance_ratio_max": float(np.max(variance_ratios)),
                "random_concept_abs_cosine_median": float(np.median(concept_cosines)),
                "random_concept_abs_cosine_max": float(np.max(concept_cosines)),
            }
        )

    predictions = pd.DataFrame(prediction_rows)
    site_metrics = pd.DataFrame(site_rows)
    if predictions.case_id.duplicated().any() or len(predictions) != EXPECTED_EVALUATION_SUBJECTS:
        raise RuntimeError("held-out subject membership is not unique and complete")
    if int(predictions.bcr_event.sum()) != EXPECTED_EVALUATION_EVENTS:
        raise RuntimeError("held-out event universe changed")

    event_eval = predictions.bcr_event.to_numpy(int)
    time_eval = predictions.bcr_time_days.to_numpy(float)
    site_eval = predictions.tissue_source_site.to_numpy(str)
    full_eval = predictions.full_risk.to_numpy(float)
    target_eval = predictions.target_erased_risk.to_numpy(float)
    full_stratified = stratified_c_index(event_eval, time_eval, full_eval, site_eval)
    target_stratified = stratified_c_index(event_eval, time_eval, target_eval, site_eval)
    target_delta = full_stratified - target_stratified

    random_matrix = np.empty((RANDOM_CONTROLS, len(predictions)), dtype=np.float64)
    for held_out_site in eligible_sites:
        position = np.flatnonzero(site_eval == held_out_site)
        random_matrix[:, position] = random_by_site[held_out_site]
    random_rows = []
    random_deltas = np.empty(RANDOM_CONTROLS, dtype=float)
    for draw in range(RANDOM_CONTROLS):
        random_c = stratified_c_index(
            event_eval, time_eval, random_matrix[draw], site_eval
        )
        random_deltas[draw] = full_stratified - random_c
        random_rows.append(
            {
                "encoder": encoder,
                "draw": draw,
                "random_erased_stratified_c_index": random_c,
                "random_delta_use": random_deltas[draw],
            }
        )
    p_value = float((1 + np.sum(random_deltas >= target_delta)) / (RANDOM_CONTROLS + 1))
    summary = {
        "n_evaluation_sites": float(len(eligible_sites)),
        "n_evaluation_subjects": float(len(predictions)),
        "n_evaluation_events": float(event_eval.sum()),
        "isup_site_heldout_spearman": float(
            stats.spearmanr(
                predictions.isup_grade_group.to_numpy(float),
                predictions.isup_prediction.to_numpy(float),
            ).statistic
        ),
        "full_stratified_c_index": full_stratified,
        "target_erased_stratified_c_index": target_stratified,
        "target_delta_use": target_delta,
        "full_pooled_c_index": ordinary_c_index(event_eval, time_eval, full_eval),
        "target_erased_pooled_c_index": ordinary_c_index(event_eval, time_eval, target_eval),
        "random_delta_p95": float(np.quantile(random_deltas, 0.95)),
        "target_vs_random_p_one_sided": p_value,
        "positive_site_deltas": float(site_metrics.delta_use.gt(0).sum()),
    }
    return predictions, site_metrics, pd.DataFrame(random_rows), summary


def bootstrap_encoder(
    predictions: pd.DataFrame, encoder: str
) -> tuple[pd.DataFrame, dict[str, tuple[float, float]]]:
    rng = np.random.default_rng(SEED + (10 if encoder == "conch" else 20))
    site = predictions.tissue_source_site.to_numpy(str)
    event = predictions.bcr_event.to_numpy(int)
    time = predictions.bcr_time_days.to_numpy(float)
    full = predictions.full_risk.to_numpy(float)
    target = predictions.target_erased_risk.to_numpy(float)
    draws = {"full_stratified_c_index": [], "target_erased_stratified_c_index": [], "target_delta_use": []}
    site_positions = {value: np.flatnonzero(site == value) for value in sorted(np.unique(site))}
    for _ in range(BOOTSTRAPS):
        sampled = np.concatenate(
            [rng.choice(position, size=len(position), replace=True) for position in site_positions.values()]
        )
        try:
            full_value = stratified_c_index(event[sampled], time[sampled], full[sampled], site[sampled])
            target_value = stratified_c_index(event[sampled], time[sampled], target[sampled], site[sampled])
        except ValueError:
            continue
        draws["full_stratified_c_index"].append(full_value)
        draws["target_erased_stratified_c_index"].append(target_value)
        draws["target_delta_use"].append(full_value - target_value)
    rows = []
    intervals: dict[str, tuple[float, float]] = {}
    for metric, values in draws.items():
        array = np.asarray(values, dtype=float)
        if len(array) < int(0.95 * BOOTSTRAPS):
            raise RuntimeError(f"too few valid bootstrap draws for {encoder} {metric}")
        low, high = (float(value) for value in np.quantile(array, [0.025, 0.975]))
        intervals[metric] = (low, high)
        rows.append(
            {
                "encoder": encoder,
                "metric": metric,
                "valid_draws": len(array),
                "ci_low": low,
                "ci_high": high,
            }
        )
    return pd.DataFrame(rows), intervals


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=p_values.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, key in enumerate(ordered):
        running = max(running, (total - rank) * p_values[key])
        adjusted[key] = min(1.0, running)
    return adjusted


def run() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    input_hashes = verify_inputs()
    source_subjects = pd.read_csv(SOURCE / "development_subjects.csv")
    if len(source_subjects) != EXPECTED_SUBJECTS or int(source_subjects.bcr_event.sum()) != EXPECTED_EVENTS:
        raise RuntimeError("source universe changed")
    site_table = source_site_table(source_subjects)
    site_table.to_csv(
        OUTPUTS / "fm6_site_heldout_source_site_audit.csv", index=False, lineterminator="\n"
    )

    prediction_frames = []
    site_frames = []
    random_frames = []
    bootstrap_frames = []
    summaries: dict[str, dict[str, float]] = {}
    intervals_by_encoder: dict[str, dict[str, tuple[float, float]]] = {}
    for encoder in ("conch", "virchow"):
        print(f"site-held-out analysis: {encoder}", flush=True)
        predictions, site_metrics, random_controls, summary = analyze_encoder(encoder)
        bootstrap, intervals = bootstrap_encoder(predictions, encoder)
        prediction_frames.append(predictions)
        site_frames.append(site_metrics)
        random_frames.append(random_controls)
        bootstrap_frames.append(bootstrap)
        summaries[encoder] = summary
        intervals_by_encoder[encoder] = intervals

    p_adjusted = holm_adjust(
        {encoder: values["target_vs_random_p_one_sided"] for encoder, values in summaries.items()}
    )
    summary_rows = []
    evidence_rows = []
    for encoder in ("conch", "virchow"):
        values = summaries[encoder]
        intervals = intervals_by_encoder[encoder]
        row = {"encoder": encoder, **values}
        row.update(
            {
                "full_stratified_c_index_ci_low": intervals["full_stratified_c_index"][0],
                "full_stratified_c_index_ci_high": intervals["full_stratified_c_index"][1],
                "target_delta_use_ci_low": intervals["target_delta_use"][0],
                "target_delta_use_ci_high": intervals["target_delta_use"][1],
                "target_vs_random_p_holm": p_adjusted[encoder],
            }
        )
        passed = bool(
            row["full_stratified_c_index_ci_low"] > 0.50
            and row["target_delta_use_ci_low"] > 0
            and row["target_vs_random_p_holm"] <= 0.05
            and row["positive_site_deltas"] >= 5
        )
        row["site_heldout_functional_transport_pass"] = passed
        summary_rows.append(row)
        evidence_rows.append(
            {
                "encoder": encoder,
                "site_heldout_functional_transport": "PASS" if passed else "FAIL_OR_INCONCLUSIVE",
                "independent_external_transport": "NOT_TESTED_EMBARGOED",
                "tumor_specific_mechanism": "NOT_ESTABLISHED",
                "strong_external_H2": "PROHIBITED",
            }
        )

    summary_frame = pd.DataFrame(summary_rows)
    passes = int(summary_frame.site_heldout_functional_transport_pass.sum())
    if passes == 2:
        overall_status = "PASS_REPLICATED_SITE_HELDOUT_FUNCTIONAL_TRANSPORT"
    elif passes == 1:
        overall_status = "PARTIAL_ENCODER_SPECIFIC_SITE_HELDOUT_EVIDENCE"
    else:
        overall_status = "FAIL_OR_INCONCLUSIVE_SITE_HELDOUT_EVIDENCE"
    evidence = pd.DataFrame(evidence_rows)
    evidence["overall_status"] = overall_status

    output_frames = {
        "fm6_site_heldout_subject_predictions.csv": pd.concat(prediction_frames, ignore_index=True),
        "fm6_site_heldout_site_metrics.csv": pd.concat(site_frames, ignore_index=True),
        "fm6_site_heldout_random_controls.csv": pd.concat(random_frames, ignore_index=True),
        "fm6_site_heldout_bootstrap_intervals.csv": pd.concat(bootstrap_frames, ignore_index=True),
        "fm6_site_heldout_summary.csv": summary_frame,
        "fm6_site_heldout_evidence_chain.csv": evidence,
    }
    for filename, frame in output_frames.items():
        frame.to_csv(OUTPUTS / filename, index=False, lineterminator="\n")

    report_lines = [
        "---",
        "document_id: fm6-site-heldout-functional-xai-report",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: report",
        "status: generated",
        "created: 2026-08-20",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_site_heldout_functional_validation/outputs/fm6-site-heldout-functional-xai-report.md",
        "---",
        "",
        "# FM6 site-held-out functional XAI validation",
        "",
        "## Evidence scope",
        "",
        "This is TCGA tissue-source-site-held-out internal transport evidence. It is not an independent external-cohort validation, tumor-specific mechanism, clinical validation, or biomarker discovery result.",
        "",
        f"- Evaluation sites: {', '.join(EXPECTED_SITES)}",
        f"- Held-out subjects/events: {EXPECTED_EVALUATION_SUBJECTS}/{EXPECTED_EVALUATION_EVENTS}",
        f"- Overall prespecified status: **{overall_status}**",
        "",
        "## Prespecified results",
        "",
    ]
    for row in summary_frame.itertuples(index=False):
        report_lines.extend(
            [
                f"### {row.encoder}",
                "",
                f"- Site-held-out ISUP Spearman: {row.isup_site_heldout_spearman:.3f}",
                f"- Full-head stratified C-index: {row.full_stratified_c_index:.3f} (95% CI {row.full_stratified_c_index_ci_low:.3f}–{row.full_stratified_c_index_ci_high:.3f})",
                f"- Target-erased stratified C-index: {row.target_erased_stratified_c_index:.3f}",
                f"- Targeted delta_use: {row.target_delta_use:.3f} (95% CI {row.target_delta_use_ci_low:.3f}–{row.target_delta_use_ci_high:.3f})",
                f"- Matched-random p95: {row.random_delta_p95:.3f}; one-sided p={row.target_vs_random_p_one_sided:.4f}; Holm p={row.target_vs_random_p_holm:.4f}",
                f"- Positive site-specific deltas: {int(row.positive_site_deltas)}/7",
                f"- Encoder gate: {'PASS' if row.site_heldout_functional_transport_pass else 'FAIL_OR_INCONCLUSIVE'}",
                "",
            ]
        )
    report_lines.extend(
        [
            "## Interpretation boundary",
            "",
            "The result is locked without retuning. Even a positive gate supports only multi-site held-out whole-tissue functional sensitivity within TCGA. CHIMERA remains excluded; LEOPARD independent external analysis is assessed separately, and this result alone does not establish independent external T or strong external H2.",
            "",
        ]
    )
    report_path = OUTPUTS / "fm6-site-heldout-functional-xai-report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    hashed_outputs = sorted([*output_frames, report_path.name, "fm6_site_heldout_source_site_audit.csv"])
    config = {
        "protocol": "fm6-site-heldout-functional-xai-protocol",
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "pca_components": PCA_COMPONENTS,
        "ridge_alpha": RIDGE_ALPHA,
        "cox_alpha": COX_ALPHA,
        "random_controls": RANDOM_CONTROLS,
        "bootstraps": BOOTSTRAPS,
        "eligible_sites": list(EXPECTED_SITES),
        "overall_status": overall_status,
        "claim_ceiling": "TCGA site-held-out internal whole-tissue functional transport only; independent external T and strong H2 prohibited",
        "input_sha256": input_hashes,
        "output_sha256": {name: sha256_file(OUTPUTS / name) for name in hashed_outputs},
        "volatile_fields": ["finished_at_utc"],
    }
    (OUTPUTS / "fm6_site_heldout_run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(config, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
