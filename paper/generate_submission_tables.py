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
    ("ar", "AR"), ("spop", "SPOP"), ("marker7", "Recurrence risk"),
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
        r"\caption{Endpoint hierarchy retained from the audited source. Rows E01--E02 are primary frozen-score qualification, E03 is secondary held-out clinical increment, and E04--E05 are exploratory recurrence analyses. The metric column states the estimand used for each endpoint class; hierarchy levels are not interchangeable.}",
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
    display_labels = {
        "marker4_pten / grade_only": "PTEN / grade-only",
        "marker6_ar / grade_only": "AR / grade-only",
        "marker7_recurrence / grade_only": "Post-hoc recurrence risk / grade-only",
        "marker7_recurrence / fully_adjusted": (
            "Post-hoc recurrence risk / fully adjusted"
        ),
    }
    escaped = _escape(display_labels.get(str(value), value))
    for number, symbol in enumerate("①②③④⑤⑥", start=1):
        escaped = escaped.replace(symbol, rf"\textcircled{{{number}}}")
    return escaped


def _display_metric(value: object) -> str:
    labels = {
        "Spearman_rho": "Spearman rho",
        "delta_AUROC": "AUROC change",
        "delta_R2": "R-squared change",
        "delta_C-index": "C-index change",
    }
    return _escape(labels.get(str(value), value))


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
            f"{_display_test(row.test)} & {_display_metric(row.effect_metric)} & "
            f"{_scientific_tex(row.effect)} & {_scientific_tex(row.p_value)} & "
            f"{_scientific_tex(row.q_value_BH_FDR_17_tests)} \\\\"
        )
    tex = "\n".join((
        r"\begingroup", r"\small",
        r"\begin{longtable}{@{}p{0.38\textwidth}p{0.14\textwidth}rrr@{}}",
        r"\caption{Complete saved 17-row revision-analysis multiplicity family. Every discovery-family row is shown rather than a selected subset. Effects and probability values are copied from the audited source; $q$ is the Benjamini--Hochberg false-discovery-rate-adjusted value across all 17 rows.}",
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
        r"\begingroup",
        r"\fontsize{9.5pt}{11pt}\selectfont",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{longtable}{@{}p{0.11\linewidth}p{0.12\linewidth}p{0.12\linewidth}p{0.07\linewidth}p{0.26\linewidth}p{0.26\linewidth}@{}}",
        r"\caption{Target-by-axis qualification audit corresponding to main-text Figure 7. Each row links a target-specific evidence state to the audited claim source, states the current evidence, and specifies what evidence would be required to change that state. Not evaluated and not applicable are not negative results.}",
        r"\label{tab:supp-evidence-axis-audit}\\",
        r"\toprule",
        "Target & Evidence axis & State & Claim & Current evidence & Next evidence needed \\\\",
        r"\midrule", r"\endfirsthead",
        r"\toprule",
        "Target & Evidence axis & State & Claim & Current evidence & Next evidence needed \\\\",
        r"\midrule", r"\endhead",
        *rows, r"\bottomrule", r"\end{longtable}", r"\endgroup", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def _require_columns(frame: pd.DataFrame, columns: set[str], description: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{description} missing required columns: {missing}")


def render_analysis_frame_inventory(
    transport: pd.DataFrame,
    molecular: pd.DataFrame,
    confounder: pd.DataFrame,
    recurrence: pd.DataFrame,
    stability: pd.DataFrame,
    contrasts: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Render a source-reconciled inventory of all major analysis frames."""
    _require_columns(
        transport, {"semantic_key", "signal", "cohort", "institution", "analysis_unit", "n", "n_events"},
        "analysis-frame transport source",
    )
    _require_columns(
        molecular, {"semantic_key", "target", "component", "patient_denominator", "event_count"},
        "analysis-frame molecular source",
    )
    _require_columns(
        confounder, {"semantic_key", "audit_type", "site", "n_slides", "n_patients"},
        "analysis-frame confounder source",
    )
    _require_columns(
        recurrence, {"semantic_key", "endpoint_id", "result_type", "n", "n_events"},
        "analysis-frame recurrence source",
    )
    _require_columns(
        stability, {"marker", "encoder", "tiles_per_slide", "target_mpp", "n_seeds"},
        "analysis-frame stability source",
    )
    _require_columns(
        contrasts, {"pair_id", "contrast", "marker", "sampling_seed"},
        "analysis-frame contrast source",
    )
    if len(transport) != 7 or set(transport["semantic_key"]) != {
        "gleason:nadt", "phenotype:nadt", "gleason_panda:karolinska",
        "gleason_panda:radboud", "phenotype_panda:karolinska",
        "phenotype_panda:radboud", "gleason_precise:all",
    }:
        raise ValueError("analysis-frame inventory transport rows do not reconcile")
    primary = molecular.loc[molecular["component"].eq("frozen_primary")]
    if set(primary["target"]) != {"PTEN", "SPOP", "AR"} or not primary["patient_denominator"].eq(273).all():
        raise ValueError("analysis-frame inventory molecular frame does not reconcile")
    increments = confounder.loc[confounder["audit_type"].eq("grade_adjusted_increment")]
    if len(increments) != 4 or not increments["n_patients"].eq(273).all():
        raise ValueError("analysis-frame inventory increment frame does not reconcile")
    pooled_site = confounder.loc[
        confounder["audit_type"].eq("ar_site_transport") & confounder["site"].eq("Pooled")
    ]
    site_rows = confounder.loc[
        confounder["audit_type"].eq("ar_site_transport") & confounder["site"].ne("Pooled")
    ]
    if len(pooled_site) != 1 or len(site_rows) != 6:
        raise ValueError("analysis-frame inventory site frame does not reconcile")
    frozen = recurrence.loc[recurrence["result_type"].eq("frozen_risk_performance")]
    paired = recurrence.loc[recurrence["result_type"].eq("same_patient_same_draw_delta")]
    if len(frozen) != 2 or set(frozen["n"]) != {270} or set(frozen["n_events"]) != {42, 57}:
        raise ValueError("analysis-frame inventory recurrence target frame does not reconcile")
    if len(paired) != 20 or set(paired["n"]) != {153} or set(paired["n_events"]) != {15, 30}:
        raise ValueError("analysis-frame inventory paired recurrence frame does not reconcile")
    if len(stability) != 72 or stability["n_seeds"].sum() != 360:
        raise ValueError("analysis-frame inventory stability grid does not reconcile")
    if len(contrasts) != 390 or contrasts["pair_id"].duplicated().any():
        raise ValueError("analysis-frame inventory paired contrasts do not reconcile")

    rows = (
        ("Source fitting", "NADT-Prostate", "Grade; phenotype", "Patient", "39", "Source-cohort probe fitting and patient aggregation"),
        ("External transfer", "PANDA Karolinska", "Grade; phenotype", "Case image", "565; 469 tumor for phenotype", "Transfer without target-cohort refitting"),
        ("External transfer", "PANDA Radboud", "Grade; phenotype", "Case image", "572; 483 tumor for phenotype", "Transfer without target-cohort refitting"),
        ("Additional grade evaluation", "PRECISE", "Grade", "Imaging session", "17 evaluable sessions", "Independent resource and session-level analysis unit"),
        ("Molecular primary", "TCGA-PRAD", "PTEN; SPOP; AR", "Patient", "273", "Frozen pooled association"),
        ("Clinical increment", "TCGA-PRAD", "PTEN; AR", "Patient", "273", "Nested held-out increment beyond grade"),
        ("Site audit", "TCGA-PRAD", "AR", "Slide with patient clustering", "300 slides; 273 patients; 6 sites", "Site-specific uncertainty, not a causal scanner analysis"),
        ("Recurrence transfer", "TCGA-PRAD", "Post-hoc recurrence risk", "Patient", "270; 57 reconstructed and 42 Official-PFI events", "Endpoint-specific frozen-risk transfer"),
        ("Paired recurrence increment", "TCGA-PRAD", "Post-hoc recurrence risk", "Complete-case patient", "153; 30 reconstructed and 15 Official-PFI events", "Same-patient, same-bootstrap-draw model contrasts"),
        ("Correlated setting audit", "Multiple source cohorts", "Six targets", "Configuration and seed cell", "72 configurations; 360 cells; 390 paired contrasts", "Sensitivity analysis; cells are not independent validations"),
    )
    tex_rows = [" & ".join(_escape(value) for value in row) + r" \\" for row in rows]
    tex = "\n".join((
        r"\begingroup", r"\fontsize{9.5pt}{11pt}\selectfont",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{longtable}{@{}p{0.14\linewidth}p{0.14\linewidth}p{0.14\linewidth}p{0.14\linewidth}p{0.18\linewidth}p{0.20\linewidth}@{}}",
        r"\caption{Analysis-frame inventory. Each row identifies the resource, target, analysis unit, saved denominator or repeated structure, and scientific role of one evidence component. Counts must not be summed as independent patients or validations because patients, slides, folds, and settings can overlap across rows.}",
        r"\label{tab:supp-analysis-frame-inventory}\\", r"\toprule",
        "Evidence component & Resource & Target & Analysis unit & Saved frame & Role \\\\",
        r"\midrule", r"\endfirsthead", r"\toprule",
        "Evidence component & Resource & Target & Analysis unit & Saved frame & Role \\\\",
        r"\midrule", r"\endhead", *tex_rows, r"\bottomrule", r"\end{longtable}",
        r"\endgroup", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def render_stability_contrast_summary(frame: pd.DataFrame, output_path: Path) -> Path:
    """Summarize all 390 paired sensitivity contrasts without independence claims."""
    required = {"pair_id", "contrast", "marker", "delta_b_minus_a", "null_crossing"}
    _require_columns(frame, required, "stability contrast summary")
    if len(frame) != 390 or frame["pair_id"].duplicated().any():
        raise ValueError("stability contrast summary requires 390 unique pairs")
    contrasts = (
        ("native_vs_1.76", "Shared 1.76 mpp minus native"),
        ("virchow_vs_conch_at_1.76", "Virchow minus CONCH at 1.76 mpp"),
        ("tile64_vs16", "64 minus 16 tiles"),
    )
    markers = (
        ("gleason", "Gleason"), ("phenotype", "Phenotype"), ("pten", "PTEN"),
        ("ar", "AR"), ("spop", "SPOP"), ("marker7", "Recurrence risk"),
    )
    expected_counts = {"native_vs_1.76": 30, "virchow_vs_conch_at_1.76": 15, "tile64_vs16": 20}
    rows = []
    for contrast, contrast_label in contrasts:
        for marker, marker_label in markers:
            subset = frame.loc[frame["contrast"].eq(contrast) & frame["marker"].eq(marker)]
            if len(subset) != expected_counts[contrast]:
                raise ValueError(f"stability contrast summary count mismatch: {contrast}/{marker}")
            values = pd.to_numeric(subset["delta_b_minus_a"], errors="coerce")
            if values.isna().any():
                raise ValueError("stability contrast summary contains non-numeric differences")
            crossings = subset["null_crossing"].astype(str).str.lower()
            if not crossings.isin({"true", "false"}).all():
                raise ValueError("stability contrast summary has invalid null-crossing flags")
            rows.append(
                f"{_escape(contrast_label)} & {_escape(marker_label)} & {len(subset)} & "
                f"{values.median():+.3f} & {values.quantile(0.25):+.3f} to "
                f"{values.quantile(0.75):+.3f} & {int(crossings.eq('true').sum())}/{len(subset)} \\\\"
            )
    tex = "\n".join((
        r"\begingroup", r"\small", r"\setlength{\tabcolsep}{3pt}",
        r"\begin{longtable}{@{}p{0.29\textwidth}p{0.16\textwidth}rrrr@{}}",
        r"\caption{Descriptive summary corresponding to Supplementary Figure S4. All 390 seed-matched setting contrasts are partitioned by comparison family and target. Differences are B minus A; medians, interquartile ranges, and null-crossing counts summarize correlated sensitivity comparisons rather than independent replicates or hypothesis tests.}",
        r"\label{tab:supp-stability-contrast-summary}\\", r"\toprule",
        "Comparison & Target & Pairs & Median & Interquartile range & Null crossings \\\\",
        r"\midrule", r"\endfirsthead", r"\toprule",
        "Comparison & Target & Pairs & Median & Interquartile range & Null crossings \\\\",
        r"\midrule", r"\endhead", *rows, r"\bottomrule", r"\end{longtable}",
        r"\endgroup", "",
    ))
    _atomic_write(Path(output_path), tex)
    return Path(output_path)


def render_endpoint_concordance(frame: pd.DataFrame, output_path: Path) -> Path:
    """Render all saved comparisons against Official TCGA-CDR PFI."""
    required = {
        "reference_endpoint_id", "comparison_endpoint_id", "n_common_evaluable",
        "n_reference_events_common", "n_comparison_events_common", "event_agreement",
        "cohen_kappa", "time_spearman_rho", "status",
    }
    _require_columns(frame, required, "endpoint concordance table")
    labels = {
        "reconstructed_gdc_disease_response": "Reconstructed with-tumor",
        "cbioportal_tcga_cdr_pfs": "TCGA-CDR PFS",
        "cbioportal_tcga_cdr_dfs": "TCGA-CDR DFS",
        "gdc_recurrence_only_after_tumor_free": "Strict recurrence-only",
    }
    if len(frame) != 4 or set(frame["comparison_endpoint_id"]) != set(labels):
        raise ValueError("endpoint concordance table requires the complete four-row comparison set")
    if not frame["reference_endpoint_id"].eq("official_tcga_cdr_pfi").all() or not frame["status"].eq("complete").all():
        raise ValueError("endpoint concordance table requires complete Official-PFI comparisons")
    rows = []
    for endpoint_id, label in labels.items():
        row = frame.loc[frame["comparison_endpoint_id"].eq(endpoint_id)]
        if len(row) != 1:
            raise ValueError(f"endpoint concordance table row is not unique: {endpoint_id}")
        row = row.iloc[0]
        rows.append(
            f"{_escape(label)} & {int(row.n_common_evaluable)} & "
            f"{int(row.n_reference_events_common)}/{int(row.n_comparison_events_common)} & "
            f"{float(row.event_agreement):.3f} & {float(row.cohen_kappa):.3f} & "
            f"{float(row.time_spearman_rho):.3f} \\\\"
        )
    tex = "\n".join((
        r"\begin{table}[htbp]", r"\centering", r"\small",
        r"\caption{Saved endpoint concordance corresponding to Supplementary Figure S5, with Official TCGA Pan-Cancer Clinical Data Resource progression-free interval (PFI) as the reference. Common N is the shared evaluable frame; event counts are Official PFI/comparison; agreement is raw event agreement, kappa is chance-corrected event agreement, and time rho is Spearman follow-up-time correlation.}",
        r"\label{tab:supp-endpoint-concordance}",
        r"\begin{tabular}{@{}lrrrrr@{}}", r"\toprule",
        "Comparison endpoint & Common N & Events & Agreement & Kappa & Time rho \\\\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", "",
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
        "S5": (
            "tab:supp-analysis-frame-inventory", "paper/generate_submission_tables.py", 6,
            render_analysis_frame_inventory,
        ),
        "S6": (
            "tab:supp-stability-contrast-summary", "paper/generate_submission_tables.py", 1,
            render_stability_contrast_summary,
        ),
        "S7": (
            "tab:supp-endpoint-concordance", "paper/generate_submission_tables.py", 1,
            render_endpoint_concordance,
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
