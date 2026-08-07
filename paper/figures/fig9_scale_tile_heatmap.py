"""Render Figure 9 from the frozen Gate A summary and paired-contrast CSVs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_GRID = ROOT / "paper/figure_data/fig9_stability_grid.csv"
DEFAULT_CONTRASTS = ROOT / "paper/figure_data/fig9_stability_contrasts.csv"
DEFAULT_PDF = HERE / "fig9_scale_tile_heatmap.pdf"
DEFAULT_PNG = HERE / "fig9_scale_tile_heatmap.png"

MARKERS = ("gleason", "phenotype", "pten", "spop", "ar", "marker7")
MARKER_LABELS = {
    "gleason": "Gleason",
    "phenotype": "Phenotype",
    "pten": "PTEN",
    "spop": "SPOP",
    "ar": "AR",
    "marker7": "Marker 7",
}
MARKER_MAPPING = {
    "gleason": ("patient_spearman_rho", 0.0),
    "phenotype": ("patient_auroc", 0.5),
    "pten": ("patient_auroc", 0.5),
    "spop": ("patient_auroc", 0.5),
    "ar": ("patient_spearman_rho", 0.0),
    "marker7": ("patient_c_index", 0.5),
}
OUTCOME_MAPPING = {
    "gleason": "continuous", "phenotype": "binary", "pten": "binary",
    "spop": "binary", "ar": "continuous", "marker7": "survival",
}
ENCODERS = ("CONCH", "Virchow")
TILES = (16, 32, 64)
NATIVE_MPP = {"CONCH": 0.88, "Virchow": 0.44}
SHARED_MPP = 1.76
CONTRASTS = ("native_vs_1.76", "virchow_vs_conch_at_1.76", "tile64_vs16")
CONTRAST_LABELS = ("Native vs\n1.76", "Virchow vs CONCH\n@ 1.76", "64 vs 16\ntiles")

GRID_NUMERIC = (
    "chance_value", "tiles_per_slide", "target_mpp", "n_seeds", "mean",
    "sample_sd", "sampling_seed_t_ci_low", "sampling_seed_t_ci_high", "min", "max",
    "n_chance_or_worse", "chance_or_worse_rate", "n_ties", "null_value",
)
CONTRAST_NUMERIC = (
    "sampling_seed", "tiles_per_slide_a", "tiles_per_slide_b", "target_mpp_a",
    "target_mpp_b", "patient_metric_a", "patient_metric_b", "delta_b_minus_a", "null_value",
)


class FigureDataError(ValueError):
    """Raised when a Figure 9 source violates the frozen data contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise FigureDataError(f"{label} is missing required columns: {missing}")


def _require_finite(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise FigureDataError(f"{label}.{column} contains a missing or non-finite value")


def _strict_integer(value, column: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise FigureDataError(f"{column} must be an integer, found {value!r}") from error
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise FigureDataError(f"{column} must be an integer, found {value!r}")
    return int(numeric)


def _strict_boolean(value, column: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value in {"True", "False"}:
        return value == "True"
    raise FigureDataError(f"{column} must be exactly True or False, found {value!r}")


def _null_relation(value: float, null: float) -> str:
    if value < null:
        return "below_null"
    if value > null:
        return "above_null"
    return "at_null"


def _cell_id(marker: str, encoder: str, seed: int, tile: int, mpp: float) -> str:
    return f"{marker}__{encoder.lower()}__s{seed}__t{tile}__mpp{mpp:.2f}"


def validate_grid(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "marker", "metric", "chance_value", "encoder", "tiles_per_slide", "target_mpp",
        "n_seeds", "mean", "sampling_seed_t_ci_low", "sampling_seed_t_ci_high", "min", "max",
        "n_chance_or_worse", "chance_or_worse_rate", "seed_null_straddle", "n_ties",
        "outcome_type", "primary_metric", "null_value",
    }
    _require_columns(frame, required, "grid")
    _require_finite(frame, GRID_NUMERIC, "grid")
    if len(frame) != 72:
        raise FigureDataError(f"grid must contain exactly 72 rows, found {len(frame)}")
    key = ["marker", "encoder", "tiles_per_slide", "target_mpp"]
    if frame.duplicated(key).any():
        raise FigureDataError("grid contains duplicate marker/encoder/tile/scale keys")

    validated = frame.copy()
    actual = set()
    for index, row in validated.iterrows():
        marker = str(row.marker)
        encoder = str(row.encoder)
        metric_and_null = MARKER_MAPPING.get(marker)
        if metric_and_null is None:
            raise FigureDataError(f"unexpected marker: {marker}")
        metric, null = metric_and_null
        if str(row.metric) != metric or str(row.primary_metric) != metric:
            raise FigureDataError(f"unexpected metric mapping for {marker}")
        if float(row.chance_value) != null or float(row.null_value) != null:
            raise FigureDataError(f"unexpected null mapping for {marker}")
        if str(row.outcome_type) != OUTCOME_MAPPING[marker]:
            raise FigureDataError(f"unexpected outcome mapping for {marker}")
        if encoder not in ENCODERS:
            raise FigureDataError(f"unexpected encoder: {encoder}")
        tile = _strict_integer(row.tiles_per_slide, "tiles_per_slide")
        n_seeds = _strict_integer(row.n_seeds, "n_seeds")
        n_chance = _strict_integer(row.n_chance_or_worse, "n_chance_or_worse")
        n_ties = _strict_integer(row.n_ties, "n_ties")
        mpp = float(row.target_mpp)
        expected_mpps = {NATIVE_MPP[encoder], SHARED_MPP}
        if tile not in TILES or mpp not in expected_mpps:
            raise FigureDataError("grid contains an unexpected tile or scale axis value")
        if n_seeds != 5 or n_chance not in range(6) or n_ties not in range(6):
            raise FigureDataError("each grid row must summarize exactly five sampling seeds")
        straddle = _strict_boolean(row.seed_null_straddle, "seed_null_straddle")
        expected_straddle = float(row["min"]) < null < float(row["max"])
        if straddle != expected_straddle:
            raise FigureDataError("seed_null_straddle disagrees with the saved min/max and null")
        if not math.isclose(float(row.chance_or_worse_rate), n_chance / n_seeds, rel_tol=0, abs_tol=1e-12):
            raise FigureDataError("chance_or_worse_rate disagrees with its integer count")
        if float(row.sampling_seed_t_ci_low) > float(row.sampling_seed_t_ci_high):
            raise FigureDataError("sampling-seed interval bounds are reversed")
        validated.at[index, "tiles_per_slide"] = tile
        validated.at[index, "n_seeds"] = n_seeds
        validated.at[index, "n_chance_or_worse"] = n_chance
        validated.at[index, "n_ties"] = n_ties
        validated.at[index, "seed_null_straddle"] = straddle
        actual.add((marker, encoder, tile, mpp))

    expected = {
        (marker, encoder, tile, mpp)
        for marker in MARKERS
        for encoder in ENCODERS
        for tile in TILES
        for mpp in (NATIVE_MPP[encoder], SHARED_MPP)
    }
    if actual != expected:
        raise FigureDataError("grid keys do not match the complete frozen 72-configuration design")
    return validated


def _contrast_semantic_key(row) -> tuple:
    contrast = str(row.contrast)
    marker = str(row.marker)
    seed = _strict_integer(row.sampling_seed, "sampling_seed")
    if contrast == "native_vs_1.76":
        tile_a = _strict_integer(row.tiles_per_slide_a, "tiles_per_slide_a")
        tile_b = _strict_integer(row.tiles_per_slide_b, "tiles_per_slide_b")
        if row.encoder_a != row.encoder_b or tile_a != tile_b:
            raise FigureDataError("native-scale contrast has mismatched encoder or tile keys")
        encoder = str(row.encoder_a)
        if encoder not in ENCODERS:
            raise FigureDataError("native-scale contrast has an unexpected encoder")
        mpp_a, mpp_b = float(row.target_mpp_a), float(row.target_mpp_b)
        if mpp_a != NATIVE_MPP[encoder] or mpp_b != SHARED_MPP or tile_a not in TILES:
            raise FigureDataError("native-scale contrast has an unexpected scale pairing")
        expected_pair = f"native_vs_1.76__{marker}__{encoder.lower()}__s{seed}__t{tile_a}"
        expected_a = _cell_id(marker, encoder, seed, tile_a, mpp_a)
        expected_b = _cell_id(marker, encoder, seed, tile_b, mpp_b)
        key = (contrast, marker, encoder, seed, tile_a)
    if contrast == "virchow_vs_conch_at_1.76":
        tile_a = _strict_integer(row.tiles_per_slide_a, "tiles_per_slide_a")
        tile_b = _strict_integer(row.tiles_per_slide_b, "tiles_per_slide_b")
        if row.encoder_a != "CONCH" or row.encoder_b != "Virchow":
            raise FigureDataError("shared-scale encoder contrast has an unexpected encoder pairing")
        mpp_a, mpp_b = float(row.target_mpp_a), float(row.target_mpp_b)
        if mpp_a != SHARED_MPP or mpp_b != SHARED_MPP:
            raise FigureDataError("shared-scale encoder contrast must use 1.76 mpp")
        if tile_a != tile_b or tile_a not in TILES:
            raise FigureDataError("shared-scale encoder contrast has mismatched tile keys")
        expected_pair = f"virchow_vs_conch_at_1.76__{marker}__s{seed}__t{tile_a}"
        expected_a = _cell_id(marker, "CONCH", seed, tile_a, mpp_a)
        expected_b = _cell_id(marker, "Virchow", seed, tile_b, mpp_b)
        key = (contrast, marker, seed, tile_a)
    if contrast == "tile64_vs16":
        tile_a = _strict_integer(row.tiles_per_slide_a, "tiles_per_slide_a")
        tile_b = _strict_integer(row.tiles_per_slide_b, "tiles_per_slide_b")
        if row.encoder_a != row.encoder_b or tile_a != 16 or tile_b != 64:
            raise FigureDataError("tile contrast must compare 64 minus 16 within encoder")
        encoder = str(row.encoder_a)
        mpp_a, mpp_b = float(row.target_mpp_a), float(row.target_mpp_b)
        if encoder not in ENCODERS or mpp_a != mpp_b or mpp_a not in {NATIVE_MPP[encoder], SHARED_MPP}:
            raise FigureDataError("tile contrast has mismatched scale keys")
        expected_pair = f"tile64_vs16__{marker}__{encoder.lower()}__s{seed}__mpp{mpp_a:.2f}"
        expected_a = _cell_id(marker, encoder, seed, tile_a, mpp_a)
        expected_b = _cell_id(marker, encoder, seed, tile_b, mpp_b)
        key = (contrast, marker, encoder, seed, mpp_a)
    if contrast not in CONTRASTS:
        raise FigureDataError(f"unexpected contrast: {contrast}")
    if row.pair_id != expected_pair or row.cell_id_a != expected_a or row.cell_id_b != expected_b:
        raise FigureDataError(f"{contrast} pair/cell identities disagree with its axes")
    return key


def validate_contrasts(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "contrast", "pair_id", "cell_id_a", "cell_id_b", "marker", "outcome_type",
        "primary_metric", "sampling_seed", "encoder_a",
        "encoder_b", "tiles_per_slide_a", "tiles_per_slide_b", "target_mpp_a", "target_mpp_b",
        "patient_metric_a", "patient_metric_b", "delta_b_minus_a", "null_value",
        "metric_direction", "relation_a", "relation_b", "null_crossing", "exact_tie",
    }
    _require_columns(frame, required, "contrasts")
    _require_finite(frame, CONTRAST_NUMERIC, "contrasts")
    if len(frame) != 390:
        raise FigureDataError(f"contrasts must contain exactly 390 rows, found {len(frame)}")
    if frame["pair_id"].duplicated().any():
        raise FigureDataError("contrasts contain duplicate pair_id keys")
    counts = frame["contrast"].value_counts().to_dict()
    expected_counts = {"native_vs_1.76": 180, "virchow_vs_conch_at_1.76": 90, "tile64_vs16": 120}
    if counts != expected_counts:
        raise FigureDataError(f"contrast type counts do not match the frozen design: {counts}")

    validated = frame.copy()
    actual_keys = set()
    for index, row in validated.iterrows():
        marker = str(row.marker)
        if marker not in MARKER_MAPPING:
            raise FigureDataError(f"unexpected contrast marker: {marker}")
        metric, null = MARKER_MAPPING[marker]
        if str(row.primary_metric) != metric or float(row.null_value) != null:
            raise FigureDataError(f"unexpected contrast metric/null mapping for {marker}")
        if str(row.outcome_type) != OUTCOME_MAPPING[marker]:
            raise FigureDataError(f"unexpected contrast outcome mapping for {marker}")
        seed = _strict_integer(row.sampling_seed, "sampling_seed")
        if seed not in range(5):
            raise FigureDataError("contrast sampling seed is outside 0--4")
        if row.metric_direction != "higher_is_better":
            raise FigureDataError("contrast metric direction must be higher_is_better")
        crossing = _strict_boolean(row.null_crossing, "null_crossing")
        tie = _strict_boolean(row.exact_tie, "exact_tie")
        metric_a, metric_b = float(row.patient_metric_a), float(row.patient_metric_b)
        if not math.isclose(float(row.delta_b_minus_a), metric_b - metric_a, rel_tol=0, abs_tol=1e-12):
            raise FigureDataError("contrast delta disagrees with patient_metric_b - patient_metric_a")
        relation_a, relation_b = _null_relation(metric_a, null), _null_relation(metric_b, null)
        if row.relation_a != relation_a or row.relation_b != relation_b:
            raise FigureDataError("contrast relation labels disagree with endpoint metrics")
        if crossing != ({relation_a, relation_b} == {"below_null", "above_null"}):
            raise FigureDataError("null_crossing disagrees with relation_a/relation_b")
        if tie != (metric_a == metric_b):
            raise FigureDataError("exact_tie disagrees with endpoint metrics")
        validated.at[index, "sampling_seed"] = seed
        validated.at[index, "null_crossing"] = crossing
        validated.at[index, "exact_tie"] = tie
        actual_keys.add(_contrast_semantic_key(row))
    expected_keys = {
        ("native_vs_1.76", marker, encoder, seed, tile)
        for marker in MARKERS for encoder in ENCODERS for seed in range(5) for tile in TILES
    }
    expected_keys |= {
        ("virchow_vs_conch_at_1.76", marker, seed, tile)
        for marker in MARKERS for seed in range(5) for tile in TILES
    }
    expected_keys |= {
        ("tile64_vs16", marker, encoder, seed, round(mpp, 2))
        for marker in MARKERS for encoder in ENCODERS for seed in range(5)
        for mpp in (NATIVE_MPP[encoder], SHARED_MPP)
    }
    if actual_keys != expected_keys:
        raise FigureDataError("contrasts contain incomplete or duplicate semantic keys")
    return validated


def load_figure_data(grid_csv: Path, contrasts_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    return validate_grid(pd.read_csv(grid_csv)), validate_contrasts(pd.read_csv(contrasts_csv))


def _heatmap(ax, frame: pd.DataFrame, encoder: str, panel: str, norm, cmap) -> None:
    subset = frame[frame["encoder"] == encoder].copy()
    columns = [(NATIVE_MPP[encoder], tile) for tile in TILES] + [(SHARED_MPP, tile) for tile in TILES]
    values = np.empty((len(MARKERS), len(columns)))
    annotations: list[list[str]] = []
    for row_index, marker in enumerate(MARKERS):
        row_annotations = []
        for column_index, (mpp, tile) in enumerate(columns):
            row = subset[
                (subset["marker"] == marker)
                & (subset["tiles_per_slide"] == tile)
                & np.isclose(subset["target_mpp"], mpp)
            ].iloc[0]
            delta = float(row["mean"] - row["null_value"])
            values[row_index, column_index] = delta
            row_annotations.append(f"{delta:+.2f}\n{int(row['n_chance_or_worse'])}/5")
        annotations.append(row_annotations)
    ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")
    for row_index in range(values.shape[0]):
        for column_index in range(values.shape[1]):
            color = "white" if abs(norm(values[row_index, column_index]) - 0.5) > 0.29 else "#171717"
            ax.text(column_index, row_index, annotations[row_index][column_index], ha="center", va="center", fontsize=6.3, color=color)
    ax.set_xticks(range(6), [f"{tile}\n{mpp:g}" for mpp, tile in columns], fontsize=7)
    ax.set_yticks(range(6), [MARKER_LABELS[marker] for marker in MARKERS], fontsize=7.5)
    ax.set_xlabel("Tiles / slide and target mpp (native first, shared 1.76 second)", fontsize=7.5)
    ax.set_title(f"{panel}  {encoder}: mean minus marker-specific null\nannotation: Δnull and chance-or-worse sampling seeds / 5", loc="left", fontsize=9, fontweight="bold")
    ax.tick_params(length=0)


def _interval_panel(ax, frame: pd.DataFrame, marker: str, title: str) -> None:
    subset = frame[frame["marker"] == marker].copy()
    order = []
    labels = []
    for encoder in ENCODERS:
        for mpp_label, mpp in (("N", NATIVE_MPP[encoder]), ("S", SHARED_MPP)):
            for tile in TILES:
                row = subset[
                    (subset["encoder"] == encoder)
                    & (subset["tiles_per_slide"] == tile)
                    & np.isclose(subset["target_mpp"], mpp)
                ].iloc[0]
                order.append(row)
                labels.append(f"{encoder[0]}-{mpp_label}{tile}")
    means = np.array([float(row["mean"]) for row in order])
    lows = np.array([float(row["sampling_seed_t_ci_low"]) for row in order])
    highs = np.array([float(row["sampling_seed_t_ci_high"]) for row in order])
    x = np.arange(len(order))
    colors = ["#2867a5"] * 6 + ["#c35a2d"] * 6
    for start, stop, color in ((0, 6, "#2867a5"), (6, 12, "#c35a2d")):
        ax.errorbar(
            x[start:stop], means[start:stop],
            yerr=np.vstack([means[start:stop] - lows[start:stop], highs[start:stop] - means[start:stop]]),
            fmt="none", ecolor=color, elinewidth=1.2, capsize=2,
        )
    ax.scatter(x, means, c=colors, s=18, zorder=3)
    ax.axhline(MARKER_MAPPING[marker][1], color="#444444", lw=0.9, ls="--")
    ax.set_xticks(x, labels, rotation=45, ha="right", fontsize=6.2)
    ax.set_ylabel(MARKER_MAPPING[marker][0].replace("patient_", ""), fontsize=7)
    ax.set_title(title, loc="left", fontsize=8, fontweight="bold")
    ax.tick_params(axis="y", labelsize=6.5)
    ax.grid(axis="y", color="#dddddd", lw=0.5)


def _contrast_panel(ax, frame: pd.DataFrame) -> None:
    counts = np.zeros((len(MARKERS), len(CONTRASTS)), dtype=int)
    denominators = np.zeros_like(counts)
    for row_index, marker in enumerate(MARKERS):
        for column_index, contrast in enumerate(CONTRASTS):
            subset = frame[(frame["marker"] == marker) & (frame["contrast"] == contrast)]
            counts[row_index, column_index] = int(subset["null_crossing"].astype(bool).sum())
            denominators[row_index, column_index] = len(subset)
    rates = counts / denominators
    ax.imshow(rates, cmap="YlOrRd", vmin=0, vmax=max(0.01, float(rates.max())), aspect="auto")
    for row_index in range(len(MARKERS)):
        for column_index in range(len(CONTRASTS)):
            ax.text(column_index, row_index, f"{counts[row_index, column_index]}/{denominators[row_index, column_index]}", ha="center", va="center", fontsize=8, fontweight="bold")
    ax.set_xticks(range(3), CONTRAST_LABELS, fontsize=7)
    ax.set_yticks(range(6), [MARKER_LABELS[marker] for marker in MARKERS], fontsize=7.5)
    ax.set_title("D  Null-crossing counts in paired contrasts", loc="left", fontsize=9, fontweight="bold")
    ax.tick_params(length=0)


def build_figure(grid: pd.DataFrame, contrasts: pd.DataFrame):
    fig = plt.figure(figsize=(13.2, 9.2), dpi=180, facecolor="#fcfcfb", constrained_layout=True)
    outer = fig.add_gridspec(3, 2, height_ratios=(1.35, 0.52, 0.52))
    ax_a = fig.add_subplot(outer[0, 0])
    ax_b = fig.add_subplot(outer[0, 1])
    ax_c1 = fig.add_subplot(outer[1, 0])
    ax_c2 = fig.add_subplot(outer[2, 0])
    ax_d = fig.add_subplot(outer[1:, 1])

    all_delta = (grid["mean"] - grid["null_value"]).to_numpy(dtype=float)
    limit = max(abs(float(all_delta.min())), abs(float(all_delta.max())))
    norm = matplotlib.colors.TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("gate_a", ["#b3472d", "#f5f2eb", "#2867a5"])
    _heatmap(ax_a, grid, "CONCH", "A", norm, cmap)
    _heatmap(ax_b, grid, "Virchow", "B", norm, cmap)
    _interval_panel(ax_c1, grid, "spop", "C  SPOP — five-seed mean and sampling-seed t interval")
    _interval_panel(ax_c2, grid, "marker7", "Marker 7 — five-seed mean and sampling-seed t interval")
    _contrast_panel(ax_d, contrasts)
    fig.suptitle("Frozen Gate A sensitivity grid: 72 five-seed configurations and 390 paired contrasts", fontsize=12, fontweight="bold")
    fig.text(0.5, -0.015, "Heatmap magnitudes are interpreted within marker because metrics differ. Sampling-seed intervals describe five repeated tile-sampling seeds, not patient or population confidence intervals. Settings are correlated and share frozen cohorts and folds.", ha="center", fontsize=7.5)
    return fig


def render_figure(grid_csv: Path, contrasts_csv: Path, output_pdf: Path, output_png: Path) -> dict:
    grid_csv = Path(grid_csv).resolve()
    contrasts_csv = Path(contrasts_csv).resolve()
    output_pdf = Path(output_pdf).resolve()
    output_png = Path(output_png).resolve()
    grid, contrasts = load_figure_data(grid_csv, contrasts_csv)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    staged_pdf = None
    staged_png = None
    fig = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{output_pdf.stem}-", suffix=".pdf", dir=output_pdf.parent, delete=False) as handle:
            staged_pdf = Path(handle.name)
        with tempfile.NamedTemporaryFile(prefix=f".{output_png.stem}-", suffix=".png", dir=output_png.parent, delete=False) as handle:
            staged_png = Path(handle.name)
        fig = build_figure(grid, contrasts)
        fig.savefig(staged_pdf, bbox_inches="tight", metadata={"Creator": "fig9_scale_tile_heatmap.py", "CreationDate": None, "ModDate": None})
        fig.savefig(staged_png, bbox_inches="tight", dpi=220, metadata={"Software": "fig9_scale_tile_heatmap.py"})
        if staged_pdf.stat().st_size == 0 or staged_png.stat().st_size == 0:
            raise RuntimeError("Figure 9 renderer produced an empty output")
        os.replace(staged_pdf, output_pdf)
        staged_pdf = None
        os.replace(staged_png, output_png)
        staged_png = None
    finally:
        if fig is not None:
            plt.close(fig)
        for staged in (staged_pdf, staged_png):
            if staged is not None:
                staged.unlink(missing_ok=True)

    return {
        "grid_rows": len(grid),
        "contrast_rows": len(contrasts),
        "grid_path": str(grid_csv),
        "contrasts_path": str(contrasts_csv),
        "grid_sha256": sha256(grid_csv),
        "contrasts_sha256": sha256(contrasts_csv),
        "output_pdf": str(output_pdf),
        "output_png": str(output_png),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-csv", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--contrasts-csv", type=Path, default=DEFAULT_CONTRASTS)
    parser.add_argument("--output-pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output-png", type=Path, default=DEFAULT_PNG)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    record = render_figure(args.grid_csv, args.contrasts_csv, args.output_pdf, args.output_png)
    print(json.dumps(record, sort_keys=True))
    return record


if __name__ == "__main__":
    main()
