"""Generate submission tables deterministically from audited CSV sources."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from paper.submission_config import TABLES
except ModuleNotFoundError:  # pragma: no cover - direct script entry point
    from submission_config import TABLES

ROUNDING = {
    "display_order": "{:.0f}",
}

CLAIM_COLUMNS = {
    "claim_id", "display_order", "claim", "hierarchy", "marker", "cohort", "encoder",
    "endpoint", "validation_type", "effect_summary", "source_csv", "source_script",
    "manuscript_location", "reliability_tier", "limitation", "mr_v1_item",
    "completion_status", "status",
}
ENDPOINT_COLUMNS = {
    "endpoint_id", "hierarchy", "endpoint", "cohort", "event_definition",
    "censoring_or_exclusion", "primary_metric", "multiplicity", "source", "status",
    "limitation",
}
MULTIPLICITY_COLUMNS = (
    "family_member_type", "test", "effect_metric", "effect", "p_value", "encoder",
    "validation_type", "reliability_tier", "q_value_BH_FDR_17_tests",
)
MULTIPLICITY_KEYS = (
    ("marker_hypothesis", "① NADT H&E -> Gleason"),
    ("marker_hypothesis", "② NADT H&E -> Phenotype"),
    ("marker_hypothesis", "③ NADT ERG -> Gleason"),
    ("marker_hypothesis", "④ TCGA-PRAD H&E -> PTEN loss"),
    ("marker_hypothesis", "⑤ TCGA-PRAD H&E -> SPOP mutation"),
    ("marker_hypothesis", "⑥ TCGA-PRAD H&E -> AR score"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> TP53 mutation"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> TP53 CNA loss"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> RB1 CNA loss"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> SPINK1 high"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> ETV1 altered"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> ETV4 altered"),
    ("marker_hypothesis", "TCGA-PRAD H&E -> ERG fusion status"),
    ("nested_refit_confounder_audit", "marker4_pten / grade_only"),
    ("nested_refit_confounder_audit", "marker6_ar / grade_only"),
    ("nested_refit_confounder_audit", "marker7_recurrence / grade_only"),
    ("nested_refit_confounder_audit", "marker7_recurrence / fully_adjusted"),
)
STABILITY_COLUMNS = (
    "marker", "metric", "chance_value", "encoder", "tiles_per_slide", "target_mpp",
    "n_seeds", "mean", "sample_sd", "sampling_seed_t_ci_low",
    "sampling_seed_t_ci_high", "min", "max", "n_chance_or_worse",
    "chance_or_worse_rate", "seed_null_straddle", "n_ties", "outcome_type",
    "primary_metric", "null_value",
)
STABILITY_LABELS = (
    ("gleason", "Gleason"), ("phenotype", "Phenotype"), ("pten", "PTEN"),
    ("ar", "AR"), ("spop", "SPOP"), ("marker7", "Marker 7"),
)
QUALIFICATION_DISPLAY_LABELS = {
    "C01": "Qualification logic",
    "C02": "Grade and phenotype transport",
    "C03": "PTEN qualification",
    "C04": "SPOP qualification",
    "C05": "AR qualification",
    "C06": "Recurrence transfer",
    "C07": "Recurrence increment",
    "C08": "Setting sensitivity",
}


def _escape(value: object) -> str:
    text = str(value)
    replacements = (
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
        ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
        ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _atomic_write(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", prefix=f".{path.name}-",
            dir=path.parent, delete=False,
        ) as handle:
            staged = Path(handle.name)
            handle.write(content)
        os.replace(staged, path)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def _validate(frame: pd.DataFrame, columns: set[str], key: str,
              expected_keys: set[str], description: str) -> pd.DataFrame:
    if set(frame.columns) != columns:
        missing = sorted(columns - set(frame.columns))
        extra = sorted(set(frame.columns) - columns)
        raise ValueError(f"{description} schema mismatch; missing={missing}, extra={extra}")
    if frame[key].isna().any() or frame[key].duplicated().any():
        raise ValueError(f"{description} {key} values must be populated and unique")
    if set(frame[key].astype(str)) != expected_keys:
        if description == "qualification summary":
            raise ValueError("qualification summary requires C01--C08 exactly")
        raise ValueError("endpoint hierarchy requires E01--E09 exactly")
    if frame.astype(str).apply(lambda column: column.str.strip().eq("").any()).any():
        raise ValueError(f"{description} cannot contain blank semantic fields")
    return frame


def render_qualification_summary(frame: pd.DataFrame, output_path: Path) -> Path:
    """Render all eight qualification decisions; reject incomplete claim semantics."""
    validated = _validate(
        frame.copy(), CLAIM_COLUMNS, "claim_id", {f"C{i:02d}" for i in range(1, 9)},
        "qualification summary",
    ).sort_values("display_order")
    rows = []
    for row in validated.itertuples(index=False):
        rows.append(
            f"{_escape(QUALIFICATION_DISPLAY_LABELS[row.claim_id])} & "
            f"{_escape(row.status.replace('_', ' '))} & "
            f"{_escape(row.reliability_tier)} \\\\"
        )
    tex = "\n".join((
        r"\begin{table}[htbp]", r"\centering", r"\small",
        r"\caption{Joint evidence map after target-specific qualification audits.}",
        r"\label{tab:qualification-summary}",
        r"\begin{tabular}{@{}p{0.18\textwidth}p{0.22\textwidth}p{0.52\textwidth}@{}}", r"\toprule",
        "Evidence question & Evidence state & Supported interpretation \\\\", r"\midrule",
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def render_endpoint_hierarchy(frame: pd.DataFrame, output_path: Path) -> Path:
    """Render the complete nine-row endpoint hierarchy without endpoint substitution."""
    validated = _validate(
        frame.copy(), ENDPOINT_COLUMNS, "endpoint_id", {
            "E01", "E02", "E03", "E04_reconstructed_with_tumor", "E05", "E06",
            "E07", "E08_official_pfi", "E09",
        },
        "endpoint hierarchy",
    ).sort_values("endpoint_id")
    rows = []
    for row in validated.itertuples(index=False):
        display_id = str(row.endpoint_id).split("_", 1)[0]
        rows.append(
            f"{_escape(display_id)} & {_escape(row.hierarchy)} & {_escape(row.endpoint)} & "
            f"{_escape(row.primary_metric)} \\\\"
        )
    tex = "\n".join((
        r"\begingroup", r"\small",
        r"\begin{longtable}{@{}p{0.06\textwidth}p{0.12\textwidth}p{0.38\textwidth}p{0.35\textwidth}@{}}",
        r"\caption{Endpoint hierarchy retained from the audited endpoint source.}",
        "\\label{tab:supp-endpoint-hierarchy}\\\\", r"\toprule",
        "ID & Hierarchy & Endpoint & Primary metric \\\\", r"\midrule", r"\endfirsthead",
        r"\toprule", "ID & Hierarchy & Endpoint & Primary metric \\\\", r"\midrule",
        r"\endhead", *rows, r"\bottomrule", r"\end{longtable}", r"\endgroup", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def _validate_exact_schema(frame: pd.DataFrame, columns: tuple[str, ...],
                           description: str) -> pd.DataFrame:
    if tuple(frame.columns) != columns:
        missing = sorted(set(columns) - set(frame.columns))
        extra = sorted(set(frame.columns) - set(columns))
        raise ValueError(
            f"{description} schema mismatch; expected_order={list(columns)}, "
            f"missing={missing}, extra={extra}"
        )
    return frame


def _scientific_tex(value: object) -> str:
    formatted = f"{float(value):.3g}"
    if "e" not in formatted:
        return formatted
    mantissa, exponent = formatted.split("e")
    return f"${mantissa}\\times10^{{{int(exponent)}}}$"


def _display_test(value: object) -> str:
    escaped = _escape(value)
    for number, symbol in enumerate("①②③④⑤⑥", start=1):
        escaped = escaped.replace(symbol, rf"\textcircled{{{number}}}")
    return escaped


def render_multiplicity_family(frame: pd.DataFrame, output_path: Path) -> Path:
    """Render the immutable 17-row revision-analysis multiplicity family."""
    validated = _validate_exact_schema(
        frame.copy(), MULTIPLICITY_COLUMNS, "multiplicity family"
    )
    keys = tuple(zip(
        validated["family_member_type"].astype(str), validated["test"].astype(str)
    ))
    if keys != MULTIPLICITY_KEYS or len(set(keys)) != 17:
        raise ValueError("multiplicity family requires the exact 17-row key order")
    if validated.isna().any().any():
        raise ValueError("multiplicity family cannot contain missing semantic fields")
    rows = []
    for row in validated.itertuples(index=False):
        rows.append(
            f"{_display_test(row.test)} & {_escape(row.effect_metric)} & "
            f"{_scientific_tex(row.effect)} & {_scientific_tex(row.p_value)} & "
            f"{_scientific_tex(row.q_value_BH_FDR_17_tests)} \\\\"
        )
    tex = "\n".join((
        r"\begingroup", r"\small",
        r"\begin{longtable}{@{}p{0.38\textwidth}p{0.14\textwidth}rrr@{}}",
        r"\caption{Complete saved 17-row revision-analysis multiplicity family. Effects and probability values are copied from the audited source; $q$ is the Benjamini--Hochberg value.}",
        r"\label{tab:supp-family}\\", r"\toprule",
        "Test & Metric & Effect & $p$ & $q$ \\\\", r"\midrule", r"\endfirsthead",
        r"\toprule", "Test & Metric & Effect & $p$ & $q$ \\\\", r"\midrule",
        r"\endhead", *rows, r"\bottomrule", r"\end{longtable}", r"\endgroup", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def _bool_series(series: pd.Series, description: str) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    if not normalized.isin({"true", "false"}).all():
        raise ValueError(f"{description} must contain only true/false values")
    return normalized.eq("true")


def render_stability_summary(frame: pd.DataFrame, output_path: Path) -> Path:
    """Recompute the six-target summary from all 72 validated configurations."""
    validated = _validate_exact_schema(
        frame.copy(), STABILITY_COLUMNS, "stability summary"
    )
    if set(validated["marker"].astype(str)) != {key for key, _ in STABILITY_LABELS}:
        raise ValueError("stability summary requires the exact six-marker set")
    expected_configs = {
        ("CONCH", tiles, mpp) for tiles in (16, 32, 64) for mpp in (0.88, 1.76)
    } | {
        ("Virchow", tiles, mpp) for tiles in (16, 32, 64) for mpp in (0.44, 1.76)
    }
    rows = []
    for marker, label in STABILITY_LABELS:
        subset = validated.loc[validated["marker"].astype(str).eq(marker)].copy()
        configs = list(zip(
            subset["encoder"].astype(str),
            pd.to_numeric(subset["tiles_per_slide"]).astype(int),
            pd.to_numeric(subset["target_mpp"]).astype(float),
        ))
        if len(subset) != 12 or len(set(configs)) != 12 or set(configs) != expected_configs:
            raise ValueError(f"{marker} requires exactly 12 unique configurations")
        if not pd.to_numeric(subset["n_seeds"]).eq(5).all():
            raise ValueError(f"{marker} configurations must each contain five seeds")
        nulls = pd.to_numeric(subset["null_value"])
        chances = pd.to_numeric(subset["chance_value"])
        if nulls.nunique() != 1 or not nulls.reset_index(drop=True).equals(
            chances.reset_index(drop=True)
        ):
            raise ValueError(f"{marker} null values are internally inconsistent")
        null = float(nulls.iloc[0])
        outcome_types = set(subset["outcome_type"].astype(str))
        if len(outcome_types) != 1:
            raise ValueError(f"{marker} outcome type is internally inconsistent")
        expected_null = 0.5 if next(iter(outcome_types)) in {"binary", "survival"} else 0.0
        if null != expected_null:
            raise ValueError(f"{marker} null value does not match outcome type")
        straddles = int(_bool_series(subset["seed_null_straddle"], marker).sum())
        t_contains = int((
            pd.to_numeric(subset["sampling_seed_t_ci_low"]).le(null)
            & pd.to_numeric(subset["sampling_seed_t_ci_high"]).ge(null)
        ).sum())
        rows.append(
            f"{label} & {pd.to_numeric(subset['min']).min():.3f} & "
            f"{pd.to_numeric(subset['max']).max():.3f} & {straddles}/12 & "
            f"{t_contains}/12 \\\\"
        )
    tex = "\n".join((
        r"\begingroup", r"\small",
        r"\captionsetup{justification=raggedright,singlelinecheck=false}",
        r"\begin{center}", r"\begin{minipage}{0.98\textwidth}",
        r"\captionof{table}{Global seed-cell ranges and configuration-level null straddling recomputed from all 72 saved configurations. The last two columns count 12 configurations per target and distinguish the observed five-seed range from the descriptive Student-$t$ interval.}",
        r"\label{tab:supp-stability-summary}", r"\centering",
        r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
        "Target & Global minimum & Global maximum & Range straddles & "
        "$t$-interval contains null \\\\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}",
        r"\end{minipage}", r"\end{center}", r"\endgroup", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def render_evidence_axis_audit(
    matrix: pd.DataFrame, claims: pd.DataFrame, output_path: Path,
) -> Path:
    """Render every qualitative target-axis decision with its next evidence need."""
    required = {
        "target_order", "target", "axis_order", "axis", "state",
        "source_claim_ids", "interpretation", "next_evidence",
    }
    if set(matrix.columns) != required:
        raise ValueError("evidence-axis audit schema mismatch")
    if "claim_id" not in claims.columns or set(claims["claim_id"].astype(str)) != {
        f"C{index:02d}" for index in range(1, 9)
    }:
        raise ValueError("evidence-axis audit requires complete C01--C08 claims")
    if len(matrix) != 30 or matrix.duplicated(["target", "axis"]).any():
        raise ValueError("evidence-axis audit requires 30 unique target-axis cells")
    if matrix.astype(str).apply(lambda column: column.str.strip().eq("").any()).any():
        raise ValueError("evidence-axis audit cannot contain blank semantic fields")
    known_claims = set(claims["claim_id"].astype(str))
    for value in matrix["source_claim_ids"].astype(str):
        if not set(value.split(";")).issubset(known_claims):
            raise ValueError(f"evidence-axis audit has an unknown claim link: {value}")
    state_labels = {
        "supported": "supported",
        "context_sensitive": "context-sensitive",
        "unsupported": "unsupported in frozen design",
        "unresolved": "unresolved",
        "not_evaluated": "not evaluated",
        "not_applicable": "not applicable",
    }
    if set(matrix["state"]) - set(state_labels):
        raise ValueError("evidence-axis audit contains an unknown state")
    rows = []
    ordered = matrix.sort_values(["target_order", "axis_order"])
    for row in ordered.itertuples(index=False):
        rows.append(
            f"{_escape(row.target)} & {_escape(row.axis)} & "
            f"{_escape(state_labels[row.state])} & {_escape(row.source_claim_ids)} & "
            f"{_escape(row.interpretation)} & {_escape(row.next_evidence)} \\\\"
        )
    tex = "\n".join((
        r"\begin{landscape}", r"\begingroup",
        r"\fontsize{9.5pt}{11pt}\selectfont",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{longtable}{@{}p{0.11\linewidth}p{0.12\linewidth}p{0.12\linewidth}p{0.07\linewidth}p{0.26\linewidth}p{0.26\linewidth}@{}}",
        r"\caption{Target-by-axis qualification audit. Each row links an evidence state to the audited claim source and states what evidence would be required to change that state.}",
        r"\label{tab:supp-evidence-axis-audit}\\",
        r"\toprule",
        "Target & Evidence axis & State & Claim & Current evidence & Next evidence needed \\\\",
        r"\midrule", r"\endfirsthead",
        r"\toprule",
        "Target & Evidence axis & State & Claim & Current evidence & Next evidence needed \\\\",
        r"\midrule", r"\endhead",
        *rows, r"\bottomrule", r"\end{longtable}", r"\endgroup",
        r"\end{landscape}", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def generate_submission_tables(
    source_root: Path, output_root: Path, table_specs=TABLES,
) -> dict[str, Path]:
    """Generate every table declared by ``submission_config.TABLES``."""
    source_root, output_root = Path(source_root), Path(output_root)
    registry = {
        "T1": (
            "tab:qualification-summary", "paper/generate_submission_tables.py", 1,
            render_qualification_summary,
        ),
        "S1": (
            "tab:supp-endpoint-hierarchy", "paper/generate_submission_tables.py", 1,
            render_endpoint_hierarchy,
        ),
        "S2": (
            "tab:supp-family", "paper/generate_submission_tables.py", 1,
            render_multiplicity_family,
        ),
        "S3": (
            "tab:supp-stability-summary", "paper/generate_submission_tables.py", 1,
            render_stability_summary,
        ),
        "S4": (
            "tab:supp-evidence-axis-audit", "paper/generate_submission_tables.py", 2,
            render_evidence_axis_audit,
        ),
    }
    specs = tuple(table_specs)
    table_ids = [spec.table_id for spec in specs]
    output_paths = [spec.output for spec in specs]
    if len(set(table_ids)) != len(table_ids):
        raise ValueError("duplicate table_id in table configuration")
    if len(set(output_paths)) != len(output_paths):
        raise ValueError("duplicate table output in table configuration")

    outputs: dict[str, Path] = {}
    for spec in specs:
        if spec.table_id not in registry:
            raise ValueError(f"unknown table id: {spec.table_id}")
        expected_label, expected_script, source_count, renderer = registry[spec.table_id]
        if spec.label != expected_label:
            raise ValueError(f"{spec.table_id} has an unexpected table label")
        if spec.script != expected_script:
            raise ValueError(f"{spec.table_id} has an unexpected renderer script")
        if len(spec.sources) != source_count:
            raise ValueError(f"{spec.table_id} has an unexpected source count")
        output_path = output_root / spec.output
        frames = [pd.read_csv(source_root / source) for source in spec.sources]
        renderer(*frames, output_path)
        outputs[spec.table_id] = output_path
    return outputs


if __name__ == "__main__":
    generate_submission_tables(ROOT, ROOT)
