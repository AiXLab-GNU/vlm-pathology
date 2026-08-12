"""Small, guarded calculators shared by repository analyses.

These functions intentionally fail closed or return NaN where the project rules make a
metric undefined. They do not perform label imputation or endpoint construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.stats import beta, spearmanr, t
from sklearn.metrics import average_precision_score, cohen_kappa_score, roc_auc_score


def _nonnegative_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or int(value) != value or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return int(value)


def safe_fraction(numerator: int | float, denominator: int | float) -> float:
    """Return numerator / denominator, or NaN for a zero denominator."""
    if not np.isfinite([numerator, denominator]).all():
        raise ValueError("fraction inputs must be finite")
    if denominator < 0 or numerator < 0:
        raise ValueError("fraction inputs must be non-negative")
    if numerator > denominator:
        raise ValueError("numerator cannot exceed denominator")
    return float(numerator / denominator) if denominator else float("nan")


def capture_fraction(captured: int, total_positive: int) -> float:
    """Fraction of evaluable reviewed positives captured by a review budget."""
    return safe_fraction(captured, total_positive)


def review_coverage(evaluable_count: int, budget_count: int) -> float:
    """Fraction of all post-NMS budget candidates with evaluable review labels."""
    return safe_fraction(evaluable_count, budget_count)


def top_k_precision(captured: int, budget_count: int, evaluable_count: int) -> float:
    """Known top-k precision, defined only with complete evaluable coverage."""
    captured = _nonnegative_integer(captured, "captured")
    budget_count = _nonnegative_integer(budget_count, "budget_count")
    evaluable_count = _nonnegative_integer(evaluable_count, "evaluable_count")
    if evaluable_count > budget_count or captured > evaluable_count:
        raise ValueError("counts are internally inconsistent")
    if evaluable_count != budget_count:
        return float("nan")
    return safe_fraction(captured, budget_count)


def exact_binomial_ci(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided Clopper-Pearson interval; undefined when trials is zero."""
    successes = _nonnegative_integer(successes, "successes")
    trials = _nonnegative_integer(trials, "trials")
    if successes > trials:
        raise ValueError("successes cannot exceed trials")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    if trials == 0:
        return float("nan"), float("nan")
    low = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    high = 1.0 if successes == trials else float(
        beta.ppf(1 - alpha / 2, successes + 1, trials - successes)
    )
    return low, high


def frozen_combined_score(
    prototype_percentile: float | Sequence[float],
    text_pni_percentile: float | Sequence[float],
    nerve_percentile: float | Sequence[float],
) -> float | np.ndarray:
    """Apply the immutable 0.50/0.35/0.15 PRECISE score weights."""
    prototype = np.asarray(prototype_percentile, dtype=float)
    text_pni = np.asarray(text_pni_percentile, dtype=float)
    nerve = np.asarray(nerve_percentile, dtype=float)
    prototype, text_pni, nerve = np.broadcast_arrays(prototype, text_pni, nerve)
    if not all(np.isfinite(array).all() for array in (prototype, text_pni, nerve)):
        raise ValueError("score percentiles must be finite")
    if not all(((0 <= array) & (array <= 1)).all() for array in (prototype, text_pni, nerve)):
        raise ValueError("score percentiles must lie in [0, 1]")
    result = 0.50 * prototype + 0.35 * text_pni + 0.15 * nerve
    return float(result) if result.ndim == 0 else result


@dataclass(frozen=True, slots=True)
class BinaryDiscrimination:
    roc_auc: float
    average_precision: float
    n_evaluable: int
    n_positive: int
    n_negative: int
    valid: bool
    failure_reason: str


def binary_discrimination(labels: Sequence[int], scores: Sequence[float]) -> BinaryDiscrimination:
    """Compute AUROC and AP after the caller has selected evaluable observations."""
    y = np.asarray(labels)
    score = np.asarray(scores, dtype=float)
    if y.ndim != 1 or score.ndim != 1 or len(y) != len(score):
        raise ValueError("labels and scores must be one-dimensional and equally sized")
    if not np.isin(y, [0, 1]).all():
        raise ValueError("labels must contain only 0 and 1; missing labels must be filtered explicitly")
    if not np.isfinite(score).all():
        raise ValueError("scores must be finite")
    n_positive = int(np.sum(y == 1))
    n_negative = int(np.sum(y == 0))
    if n_positive == 0 or n_negative == 0:
        return BinaryDiscrimination(
            float("nan"), float("nan"), len(y), n_positive, n_negative,
            False, "single_outcome_class",
        )
    return BinaryDiscrimination(
        roc_auc=float(roc_auc_score(y, score)),
        average_precision=float(average_precision_score(y, score)),
        n_evaluable=len(y),
        n_positive=n_positive,
        n_negative=n_negative,
        valid=True,
        failure_reason="",
    )


def spearman_rho(observed: Sequence[float], predicted: Sequence[float]) -> float:
    """Spearman rank correlation with strict finite, paired inputs."""
    observed_array = np.asarray(observed, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)
    if observed_array.ndim != 1 or predicted_array.ndim != 1 or len(observed_array) != len(predicted_array):
        raise ValueError("inputs must be one-dimensional and equally sized")
    if len(observed_array) < 2 or not np.isfinite(observed_array).all() or not np.isfinite(predicted_array).all():
        return float("nan")
    return float(spearmanr(observed_array, predicted_array).statistic)


def raw_agreement(first: Sequence[object], second: Sequence[object]) -> float:
    """Fraction of exactly matching paired categorical labels."""
    first_array = np.asarray(first, dtype=object)
    second_array = np.asarray(second, dtype=object)
    if first_array.ndim != 1 or second_array.ndim != 1 or len(first_array) != len(second_array):
        raise ValueError("inputs must be one-dimensional and equally sized")
    return float(np.mean(first_array == second_array)) if len(first_array) else float("nan")


def cohen_kappa(first: Sequence[object], second: Sequence[object], *, quadratic: bool = False) -> float:
    """Cohen kappa, optionally with quadratic ordinal weights."""
    first_array = np.asarray(first)
    second_array = np.asarray(second)
    if first_array.ndim != 1 or second_array.ndim != 1 or len(first_array) != len(second_array):
        raise ValueError("inputs must be one-dimensional and equally sized")
    if len(first_array) == 0:
        return float("nan")
    return float(cohen_kappa_score(first_array, second_array, weights="quadratic" if quadratic else None))


def dice_coefficient(first_mask: Sequence[bool], second_mask: Sequence[bool]) -> float:
    """Sørensen-Dice overlap; returns 1 when both masks are empty."""
    first = np.asarray(first_mask, dtype=bool)
    second = np.asarray(second_mask, dtype=bool)
    if first.shape != second.shape:
        raise ValueError("masks must have identical shapes")
    denominator = int(first.sum() + second.sum())
    return 1.0 if denominator == 0 else float(2 * np.logical_and(first, second).sum() / denominator)


def paired_effect(near: float, distant: float, *, pseudocount: float = 1e-6) -> tuple[float, float]:
    """Return near-minus-distant difference and stabilized log2 ratio."""
    if not np.isfinite([near, distant]).all() or near < 0 or distant < 0:
        raise ValueError("near and distant values must be finite and non-negative")
    if pseudocount <= 0:
        raise ValueError("pseudocount must be positive")
    return float(near - distant), float(np.log2((near + pseudocount) / (distant + pseudocount)))


@dataclass(frozen=True, slots=True)
class IntervalSummary:
    low: float
    high: float
    requested: int
    valid: int
    undefined: int
    undefined_fraction: float


def percentile_interval(replicates: Iterable[float], *, requested: int | None = None,
                        alpha: float = 0.05) -> IntervalSummary:
    """Percentile interval that retains and reports undefined replicate accounting."""
    values = np.asarray(tuple(replicates), dtype=float)
    requested_count = len(values) if requested is None else _nonnegative_integer(requested, "requested")
    if requested_count != len(values):
        raise ValueError("requested must equal the number of supplied replicate records")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    finite = values[np.isfinite(values)]
    valid = len(finite)
    undefined = requested_count - valid
    if valid:
        low, high = np.quantile(finite, [alpha / 2, 1 - alpha / 2])
    else:
        low = high = float("nan")
    return IntervalSummary(
        float(low), float(high), requested_count, valid, undefined,
        float(undefined / requested_count) if requested_count else float("nan"),
    )


def student_t_interval(values: Sequence[float], *, alpha: float = 0.05) -> tuple[float, float]:
    """Descriptive Student-t interval across correlated sampling-seed settings."""
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) < 2:
        return float("nan"), float("nan")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    mean = float(array.mean())
    half_width = float(t.ppf(1 - alpha / 2, len(array) - 1) * array.std(ddof=1) / np.sqrt(len(array)))
    return mean - half_width, mean + half_width


def benjamini_hochberg(p_values: Sequence[float]) -> np.ndarray:
    """Return monotone Benjamini-Hochberg adjusted q-values."""
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all() or not ((0 <= values) & (values <= 1)).all():
        raise ValueError("p-values must be a finite one-dimensional array in [0, 1]")
    count = len(values)
    if count == 0:
        return np.array([], dtype=float)
    order = np.argsort(values, kind="stable")
    ranked = values[order] * count / np.arange(1, count + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1].clip(0, 1)
    result = np.empty(count, dtype=float)
    result[order] = adjusted
    return result
