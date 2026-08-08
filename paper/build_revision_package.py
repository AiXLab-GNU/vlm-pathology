"""Build the Scientific Reports manuscript package through one audited entry point."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

try:
    from paper.generate_submission_tables import generate_submission_tables
    from paper.submission_config import MAIN_FIGURES, SUPPLEMENT_FIGURES, TABLES
except ModuleNotFoundError:  # pragma: no cover - direct script entry point
    from generate_submission_tables import generate_submission_tables
    from submission_config import MAIN_FIGURES, SUPPLEMENT_FIGURES, TABLES


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
PRECISE = ROOT / "opendataset/PRECISE/precise_pni_review (1).csv"
PRECISE_SHA256 = "c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3"
MANIFEST_COLUMNS = (
    "figure_id", "label", "source_paths", "source_bundle_sha256", "script_path",
    "script_sha256", "output_path", "output_sha256", "manuscript_path",
    "manuscript_sha256", "status", "fresh",
)
TABLE_MANIFEST_COLUMNS = (
    "table_id", "label", "source_paths", "source_bundle_sha256", "script_path",
    "script_sha256", "output_path", "output_sha256", "manuscript_path",
    "manuscript_sha256", "status", "fresh",
)
FINAL_AUDIT_REPORTS = (
    Path("paper/MajorRevision-v1-compliance-report.md"),
    Path("paper/numeric_consistency_report.md"),
    Path("paper/reproducibility_report.md"),
)


@dataclass(frozen=True)
class PackageReport:
    output_root: Path
    figure_manifest: Path
    table_manifest: Path
    numeric_mapping: Path
    numeric_report: Path
    reproducibility_report: Path
    compliance_report: Path
    main_pdf: Path | None
    supplement_pdf: Path | None
    status: str
    blocker_count: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _combined_source_hash(paths: tuple[str, ...] | list[str]) -> str:
    payload = "".join(f"{path}:{sha256(ROOT / path)}\n" for path in paths)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _copy_paper_sources(stage_root: Path) -> None:
    for relative in FINAL_AUDIT_REPORTS:
        source = PAPER / relative.name
        if not source.is_file():
            raise FileNotFoundError(f"missing final-audit report: {relative.name}")

    def ignored(_directory: str, names: list[str]) -> set[str]:
        suffixes = {".aux", ".log", ".out", ".toc", ".pdf"}
        return {
            name for name in names
            if name == "__pycache__"
            or Path(name).suffix.lower() in (*suffixes, ".pyc")
        }

    shutil.copytree(PAPER, stage_root / "paper", ignore=ignored, dirs_exist_ok=True)


def _render_figures(stage_root: Path) -> None:
    for spec in (*MAIN_FIGURES, *SUPPLEMENT_FIGURES):
        module = importlib.import_module(spec.script[:-3].replace("/", "."))
        sources = tuple(ROOT / source for source in spec.sources)
        output = stage_root / spec.output
        module.render(sources, output)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"{spec.figure_id} renderer did not emit a non-empty PDF")


def _manuscript_link(spec: object, stage_root: Path) -> tuple[Path, str]:
    manuscript = stage_root / spec.manuscript
    if not manuscript.is_file():
        raise ValueError(f"missing manuscript location: {spec.manuscript}")
    text = manuscript.read_text(encoding="utf-8")
    output_token = str(Path(spec.output).relative_to("paper"))
    if spec.label not in text or output_token not in text:
        raise ValueError(
            f"{spec.figure_id} requires label {spec.label} and {output_token} in "
            f"{spec.manuscript}"
        )
    return manuscript, sha256(manuscript)


def build_figure_manifest(stage_root: Path, output_csv: Path | None = None) -> pd.DataFrame:
    """Write complete lineage for the six main and three supplementary figures."""
    stage_root = Path(stage_root)
    rows = []
    for spec in (*MAIN_FIGURES, *SUPPLEMENT_FIGURES):
        output = stage_root / spec.output
        manuscript, manuscript_hash = _manuscript_link(spec, stage_root)
        dependencies = [ROOT / source for source in spec.sources] + [ROOT / spec.script]
        if not all(path.is_file() for path in dependencies) or not output.is_file():
            raise ValueError(f"{spec.figure_id} lineage contains a missing path")
        fresh = output.stat().st_mtime >= max(path.stat().st_mtime for path in dependencies)
        if not fresh:
            raise ValueError(f"{spec.figure_id} output is stale")
        rows.append({
            "figure_id": spec.figure_id, "label": spec.label,
            "source_paths": ";".join(spec.sources),
            "source_bundle_sha256": _combined_source_hash(tuple(spec.sources)),
            "script_path": spec.script, "script_sha256": sha256(ROOT / spec.script),
            "output_path": spec.output, "output_sha256": sha256(output),
            "manuscript_path": spec.manuscript, "manuscript_sha256": manuscript_hash,
            "status": "generated", "fresh": True,
        })
    frame = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    target = Path(output_csv or stage_root / "paper/figure_manifest.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, lineterminator="\n")
    return frame


def build_table_manifest(stage_root: Path, output_csv: Path | None = None) -> pd.DataFrame:
    """Write complete lineage for every generated table in submission_config."""
    stage_root = Path(stage_root)
    rows = []
    for spec in TABLES:
        output = stage_root / spec.output
        manuscript = stage_root / spec.manuscript
        dependencies = [ROOT / source for source in spec.sources] + [ROOT / spec.script]
        if not output.is_file() or not manuscript.is_file() or not all(
            path.is_file() for path in dependencies
        ):
            raise ValueError(f"{spec.table_id} lineage contains a missing path")
        output_text = output.read_text(encoding="utf-8")
        manuscript_text = manuscript.read_text(encoding="utf-8")
        output_token = str(Path(spec.output).relative_to("paper"))
        if spec.label not in output_text or output_token not in manuscript_text:
            raise ValueError(
                f"{spec.table_id} requires generated label {spec.label} and manuscript input"
            )
        fresh = output.stat().st_mtime >= max(path.stat().st_mtime for path in dependencies)
        if not fresh:
            raise ValueError(f"{spec.table_id} output is stale")
        rows.append({
            "table_id": spec.table_id, "label": spec.label,
            "source_paths": ";".join(spec.sources),
            "source_bundle_sha256": _combined_source_hash(tuple(spec.sources)),
            "script_path": spec.script, "script_sha256": sha256(ROOT / spec.script),
            "output_path": spec.output, "output_sha256": sha256(output),
            "manuscript_path": spec.manuscript, "manuscript_sha256": sha256(manuscript),
            "status": "generated", "fresh": True,
        })
    frame = pd.DataFrame(rows, columns=TABLE_MANIFEST_COLUMNS)
    target = Path(output_csv or stage_root / "paper/table_manifest.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, lineterminator="\n")
    return frame


def _select_csv(relative: str, row_key: str, package_root: Path = ROOT) -> pd.DataFrame:
    candidate = Path(package_root) / relative
    frame = pd.read_csv(candidate if candidate.is_file() else ROOT / relative)
    if row_key == "*":
        return frame
    for clause in row_key.split("|"):
        column, expected = clause.split("=", 1)
        if column not in frame:
            raise ValueError(f"numeric mapping column absent: {relative}:{column}")
        frame = frame[frame[column].astype(str) == expected]
    if frame.empty:
        raise ValueError(f"numeric mapping row absent: {relative}:{row_key}")
    return frame


def _format_value(value: float, display_format: str) -> str:
    if display_format == "int":
        return f"{int(value):d}"
    if display_format == "comma_int":
        return f"{int(value):,d}"
    if display_format == ".3f":
        return f"{float(value):.3f}"
    if display_format == "+.3f":
        return f"{float(value):+.3f}"
    raise ValueError(f"unsupported numeric display format: {display_format}")


def _python_constant(path: Path, name: str) -> float:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, (int, float)):
                return float(value)
    raise ValueError(f"saved analysis source lacks numeric constant {name}: {path}")


def _percentile_level(path: Path) -> float:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scalar_quantiles: set[float] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        function_name = (
            function.attr if isinstance(function, ast.Attribute)
            else function.id if isinstance(function, ast.Name) else ""
        )
        if function_name == "quantile":
            try:
                value = float(ast.literal_eval(node.args[-1]))
            except (ValueError, TypeError):
                pass
            else:
                scalar_quantiles.add(value)
            continue
        if function_name != "percentile":
            continue
        for argument in node.args[1:]:
            try:
                values = ast.literal_eval(argument)
            except (ValueError, TypeError):
                continue
            if values == [2.5, 97.5]:
                return 100.0 - 2.5 - 2.5
    if {0.025, 0.975}.issubset(scalar_quantiles):
        return 100.0 * (0.975 - 0.025)
    raise ValueError(f"saved analysis source lacks the 2.5/97.5 percentile rule: {path}")


def _generate_numeric_derivations(stage_root: Path) -> Path:
    """Materialize non-row-level counts with explicit formulas and input hashes."""
    panda_path = ROOT / "models/panda_conch_cache/panda_results.csv"
    panda_script = ROOT / "models/pilot_conch_panda_external.py"
    nadt_ci_script = ROOT / "models/pilot_statistical_corrections.py"
    pfi_ci_script = ROOT / "models/build_tcga_cdr_pfi_evidence.py"
    paired_ci_script = ROOT / "models/build_marker7_survival_paired_analysis.py"
    stability_path = ROOT / "paper/figure_data/fig6_stability_overview.csv"
    panda = pd.read_csv(panda_path)
    required = {"data_provider", "isup_grade"}
    if not required.issubset(panda.columns):
        raise ValueError("PANDA cache lacks provider/ISUP fields for numeric derivations")
    providers = sorted(panda["data_provider"].astype(str).unique())
    grades = sorted(pd.to_numeric(panda["isup_grade"]).astype(int).unique())
    if providers != ["karolinska", "radboud"] or grades != list(range(6)):
        raise ValueError("PANDA provider/ISUP strata do not reconcile for sampling derivation")
    cap = int(_python_constant(panda_script, "CELLS_CAP"))
    nadt_level = int(_percentile_level(nadt_ci_script))
    pfi_level = int(_percentile_level(pfi_ci_script))
    paired_level = int(_percentile_level(paired_ci_script))
    nadt_bootstrap = int(_python_constant(nadt_ci_script, "N_BOOTSTRAP"))
    stability = pd.read_csv(stability_path)
    grid = stability[stability["component"].eq("configuration_range")]
    if (len(grid) != 6 or grid["n_configurations"].nunique() != 1
            or grid["n_correlated_cells"].nunique() != 1):
        raise ValueError("stability overview does not reconcile to six marker summaries")
    n_configurations = int(grid["n_configurations"].iloc[0])
    cells_per_marker = int(grid["n_correlated_cells"].iloc[0])
    if cells_per_marker % n_configurations:
        raise ValueError("stability cell/configuration ratio is not integral")
    records: list[dict[str, object]] = []

    def add(key: str, value: int | None, numerator: int | None, denominator: int | None,
            derivation: str, sources: tuple[str, ...], fields: str) -> None:
        records.append({
            "semantic_key": key, "value": value, "numerator": numerator,
            "denominator": denominator, "derivation": derivation,
            "source_paths": ";".join(sources), "source_fields": fields,
            "source_bundle_sha256": _combined_source_hash(sources),
        })

    panda_sources = (
        "models/panda_conch_cache/panda_results.csv",
        "models/pilot_conch_panda_external.py",
    )
    add("PANDA_STRATUM_CAP", cap, None, None, "saved CELLS_CAP",
        panda_sources, "CELLS_CAP")
    add("PANDA_SAMPLED_N", len(providers) * len(grades) * cap, None, None,
        "n_provider * n_isup_grade * CELLS_CAP",
        panda_sources, "data_provider|isup_grade|CELLS_CAP")
    add("PANDA_FILTERED_N", len(panda), None, None, "saved cache row count",
        panda_sources, "row_count")
    for provider in providers:
        selected = panda[panda["data_provider"].astype(str) == provider]
        add(
            f"PANDA_{provider.upper()}_EVENTS", None,
            int((pd.to_numeric(selected["isup_grade"]) > 0).sum()), len(selected),
            "count(ISUP>0) / provider row count", panda_sources,
            "data_provider|isup_grade",
        )
    add("NADT_PERCENTILE_INTERVAL_LEVEL", nadt_level, None, None,
        "100 - lower percentile - upper tail percentile",
        ("models/pilot_statistical_corrections.py",), "np.percentile[2.5,97.5]")
    add("NADT_BOOTSTRAP_REQUESTED", nadt_bootstrap, None, None,
        "saved N_BOOTSTRAP", ("models/pilot_statistical_corrections.py",), "N_BOOTSTRAP")
    add("PFI_PERCENTILE_INTERVAL_LEVEL", pfi_level, None, None,
        "100 - lower percentile - upper tail percentile",
        ("models/build_tcga_cdr_pfi_evidence.py",), "np.percentile[2.5,97.5]")
    add("PAIRED_PERCENTILE_INTERVAL_LEVEL", paired_level, None, None,
        "100 - lower percentile - upper tail percentile",
        ("models/build_marker7_survival_paired_analysis.py",), "quantile[0.025,0.975]")
    stability_sources = ("paper/figure_data/fig6_stability_overview.csv",)
    add("STABILITY_MARKERS", len(grid), None, None, "configuration-range row count",
        stability_sources, "component")
    add("STABILITY_CONFIGURATIONS", n_configurations, None, None,
        "unique configurations per marker", stability_sources, "n_configurations")
    add("STABILITY_SEEDS", cells_per_marker // n_configurations, None, None,
        "n_correlated_cells / n_configurations", stability_sources,
        "n_correlated_cells|n_configurations")
    add("STABILITY_CELLS_PER_MARKER", cells_per_marker, None, None,
        "correlated cells per marker", stability_sources, "n_correlated_cells")
    add("STABILITY_TOTAL_CELLS", int(grid["n_correlated_cells"].sum()), None, None,
        "sum correlated cells over markers", stability_sources, "n_correlated_cells")
    output = Path(stage_root) / "paper/results_numeric_derivations.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).fillna("").to_csv(output, index=False, lineterminator="\n")
    return output


def _mapped_value(row: pd.DataFrame, field: str) -> float:
    if field == "row_count":
        return float(len(row))
    if field.startswith("count_true:"):
        expression = field.split(":", 1)[1]
        column, operator, threshold = re.fullmatch(r"([^><=]+)([><=]+)([-0-9.]+)", expression).groups()
        values = pd.to_numeric(row[column])
        if operator != ">":
            raise ValueError(f"unsupported count_true operator: {operator}")
        return float((values > float(threshold)).sum())
    if field.startswith("ratio_true:"):
        expression = field.split(":", 1)[1]
        column, operator, threshold = re.fullmatch(r"([^><=]+)([><=]+)([-0-9.]+)", expression).groups()
        values = pd.to_numeric(row[column])
        if operator != ">":
            raise ValueError(f"unsupported ratio_true operator: {operator}")
        return float((values > float(threshold)).sum()), float(len(row))  # type: ignore[return-value]
    if field.startswith("sum:"):
        return float(pd.to_numeric(row[field.split(":", 1)[1]]).sum())
    if "/" in field:
        numerator, denominator = field.split("/", 1)
        return float(row.iloc[0][numerator]), float(row.iloc[0][denominator])  # type: ignore[return-value]
    if len(row) != 1:
        values = pd.to_numeric(row[field])
        if values.nunique(dropna=False) != 1:
            raise ValueError(f"numeric mapping field is not unique: {field}")
        return float(values.iloc[0])
    return float(row.iloc[0][field])


def _numeric_rows() -> list[dict[str, str]]:
    """Declare each quantitative Results occurrence and its exact provenance."""
    tex_path = "paper/sections/results.tex"
    derived_path = "paper/results_numeric_derivations.csv"
    f2 = "paper/figure_data/fig2_transportable_signals.csv"
    f3 = "paper/figure_data/fig3_molecular_qualification.csv"
    f4 = "paper/figure_data/fig4_confounder_site_audit.csv"
    f5 = "paper/figure_data/fig5_marker7_transfer.csv"
    f6 = "paper/figure_data/fig6_stability_overview.csv"
    rows: list[dict[str, str]] = []

    def add(claim_id: str, source_path: str, row_key: str, field: str,
            display_format: str, value_token: str, anchor: str) -> None:
        if anchor.count("{token}") != 1:
            raise ValueError(f"{claim_id} must define exactly one token placeholder")
        rows.append({
            "claim_id": claim_id, "source_path": source_path, "row_key": row_key,
            "field": field, "display_format": display_format,
            "expected_tex_token": value_token, "tex_path": tex_path,
            "context_anchor": anchor,
        })

    def derived(claim_id: str, key: str, field: str, fmt: str, value_token: str,
                anchor: str) -> None:
        add(claim_id, derived_path, f"semantic_key={key}", field, fmt, value_token, anchor)

    derived("PANDA_STRATUM_CAP", "PANDA_STRATUM_CAP", "value", "int", "100",
            "PANDA used a {token}-case cap")
    derived("PANDA_SAMPLED_N", "PANDA_SAMPLED_N", "value", "comma_int", "1,200",
            "(ISUP) stratum: {token} sampled cases")
    derived("PANDA_FILTERED_N", "PANDA_FILTERED_N", "value", "comma_int", "1,137",
            "were drawn and {token} passed tissue filtering")
    add("NADT_GLEASON_N", f2, "semantic_key=gleason:nadt", "n", "int", "39",
        "Among {token} NADT-Prostate patients")
    add("NADT_GLEASON_ESTIMATE", f2, "semantic_key=gleason:nadt", "primary_estimate",
        ".3f", "0.478", "Gleason correlation was ${token}$")
    derived("NADT_GLEASON_CI_LEVEL", "NADT_PERCENTILE_INTERVAL_LEVEL", "value", "int",
            "95", "Gleason correlation was $0.478$ ({token}\\% percentile")
    add("NADT_GLEASON_CI_LOW", f2, "semantic_key=gleason:nadt", "ci_low", ".3f",
        "0.170", "Gleason correlation was $0.478$ (95\\% percentile patient-bootstrap interval ${token}$")
    add("NADT_GLEASON_CI_HIGH", f2, "semantic_key=gleason:nadt", "ci_high", ".3f",
        "0.712", "interval $0.170$--${token}$;")
    derived("NADT_GLEASON_BOOTSTRAPS", "NADT_BOOTSTRAP_REQUESTED", "value",
            "comma_int", "2,000", "$0.712$; {token} requested resamples")
    add("NADT_PHENOTYPE_ESTIMATE", f2, "semantic_key=phenotype:nadt",
        "primary_estimate", ".3f", "0.800", "phenotype correlation was ${token}$")
    derived("NADT_PHENOTYPE_CI_LEVEL", "NADT_PERCENTILE_INTERVAL_LEVEL", "value", "int",
            "95", "phenotype correlation was $0.800$ ({token}\\% percentile")
    add("NADT_PHENOTYPE_CI_LOW", f2, "semantic_key=phenotype:nadt", "ci_low", ".3f",
        "0.625", "phenotype correlation was $0.800$ (95\\% percentile patient-bootstrap interval ${token}$")
    add("NADT_PHENOTYPE_CI_HIGH", f2, "semantic_key=phenotype:nadt", "ci_high", ".3f",
        "0.909", "interval $0.625$--${token}$;")
    derived("NADT_PHENOTYPE_BOOTSTRAPS", "NADT_BOOTSTRAP_REQUESTED", "value",
            "comma_int", "2,000", "$0.909$; {token} requested resamples")
    add("PANDA_KAROLINSKA_GLEASON", f2, "semantic_key=gleason_panda:karolinska",
        "primary_estimate", ".3f", "0.354", "Gleason correlations were ${token}$ for 565")
    add("PANDA_KAROLINSKA_N", f2, "semantic_key=gleason_panda:karolinska", "n", "int",
        "565", "$0.354$ for {token} Karolinska cases")
    add("PANDA_RADBOUD_GLEASON", f2, "semantic_key=gleason_panda:radboud",
        "primary_estimate", ".3f", "0.519", "Karolinska cases and ${token}$ for 572")
    add("PANDA_RADBOUD_N", f2, "semantic_key=gleason_panda:radboud", "n", "int",
        "572", "$0.519$ for {token} Radboud cases")
    add("PANDA_KAROLINSKA_PHENOTYPE", f2, "semantic_key=phenotype_panda:karolinska",
        "primary_estimate", ".3f", "0.786", "phenotype AUROCs were ${token}$ and $0.871$")
    add("PANDA_RADBOUD_PHENOTYPE", f2, "semantic_key=phenotype_panda:radboud",
        "primary_estimate", ".3f", "0.871", "were $0.786$ and ${token}$, respectively")
    derived("PANDA_KAROLINSKA_EVENTS", "PANDA_KAROLINSKA_EVENTS",
            "numerator/denominator", "ratio", "469/565",
            "respectively, with {token} tumor cases at Karolinska")
    derived("PANDA_RADBOUD_EVENTS", "PANDA_RADBOUD_EVENTS",
            "numerator/denominator", "ratio", "483/572",
            "Karolinska and {token} tumor cases at Radboud")
    add("PRECISE_GLEASON_ESTIMATE", f2, "semantic_key=gleason_precise:all",
        "primary_estimate", ".3f", "0.865", "session-level Gleason correlation was ${token}$")
    add("PRECISE_GLEASON_N", f2, "semantic_key=gleason_precise:all", "n", "int", "17",
        "$0.865$ across {token} evaluable sessions")

    add("MOLECULAR_FRAME_N", f3, "semantic_key=pten:frozen_primary",
        "patient_denominator", "int", "273", "fixed {token}-patient TCGA-PRAD frame")
    molecular = (
        ("PTEN_PRIMARY_ESTIMATE", "pten:frozen_primary", "primary_estimate", ".3f", "0.632",
         "PTEN had a frozen-primary AUROC of ${token}$"),
        ("PTEN_PRIMARY_CI_LOW", "pten:frozen_primary", "interval_low", ".3f", "0.560",
         "AUROC of $0.632$ (patient-bootstrap interval ${token}$"),
        ("PTEN_PRIMARY_CI_HIGH", "pten:frozen_primary", "interval_high", ".3f", "0.706",
         "interval $0.560$--${token}$)"),
        ("PTEN_RANGE_LOW", "pten:configuration_summary", "range_low", ".3f", "0.519",
         "global seed-cell range of ${token}$--$0.717$"),
        ("PTEN_RANGE_HIGH", "pten:configuration_summary", "range_high", ".3f", "0.717",
         "range of $0.519$--${token}$"),
        ("AR_PRIMARY_ESTIMATE", "ar:frozen_primary", "primary_estimate", ".3f", "0.195",
         "AR had a frozen-primary Spearman correlation of ${token}$"),
        ("AR_PRIMARY_CI_LOW", "ar:frozen_primary", "interval_low", ".3f", "0.074",
         "correlation of $0.195$ (${token}$--$0.310$)"),
        ("AR_PRIMARY_CI_HIGH", "ar:frozen_primary", "interval_high", ".3f", "0.310",
         "$0.195$ ($0.074$--${token}$)"),
        ("AR_RANGE_LOW", "ar:configuration_summary", "range_low", ".3f", "0.136",
         "and a global seed-cell range of ${token}$--$0.297$"),
        ("AR_RANGE_HIGH", "ar:configuration_summary", "range_high", ".3f", "0.297",
         "range of $0.136$--${token}$"),
        ("SPOP_PRIMARY_ESTIMATE", "spop:frozen_primary", "primary_estimate", ".3f", "0.519",
         "SPOP had a frozen-primary AUROC of ${token}$"),
        ("SPOP_PRIMARY_CI_LOW", "spop:frozen_primary", "interval_low", ".3f", "0.408",
         "SPOP had a frozen-primary AUROC of $0.519$ (${token}$"),
        ("SPOP_PRIMARY_CI_HIGH", "spop:frozen_primary", "interval_high", ".3f", "0.627",
         "$0.519$ ($0.408$--${token}$)"),
        ("SPOP_RANGE_LOW", "spop:configuration_summary", "range_low", ".3f", "0.348",
         "global seed-cell range crossed chance (${token}$"),
        ("SPOP_RANGE_HIGH", "spop:configuration_summary", "range_high", ".3f", "0.679",
         "crossed chance ($0.348$--${token}$)"),
    )
    for item in molecular:
        add(item[0], f3, f"semantic_key={item[1]}", *item[2:])

    increments = (
        ("PTEN_CONCH_DELTA", "pten:CONCH:increment", "primary_estimate", "+.3f", "+0.019",
         "CONCH's held-out increment beyond grade was ${token}$"),
        ("PTEN_CONCH_CI_LOW", "pten:CONCH:increment", "ci_low", "+.3f", "-0.025",
         "CONCH's held-out increment beyond grade was $+0.019$ (patient-bootstrap interval ${token}$"),
        ("PTEN_CONCH_CI_HIGH", "pten:CONCH:increment", "ci_high", "+.3f", "+0.068",
         "interval $-0.025$ to ${token}$)"),
        ("PTEN_VIRCHOW_DELTA", "pten:Virchow:increment", "primary_estimate", "+.3f", "+0.035",
         "the Virchow increment was ${token}$"),
        ("PTEN_VIRCHOW_CI_LOW", "pten:Virchow:increment", "ci_low", "+.3f", "-0.013",
         "Virchow increment was $+0.035$ (${token}$"),
        ("PTEN_VIRCHOW_CI_HIGH", "pten:Virchow:increment", "ci_high", "+.3f", "+0.087",
         "$+0.035$ ($-0.013$ to ${token}$)"),
        ("AR_CONCH_DELTA", "ar:CONCH:increment", "primary_estimate", "+.3f", "+0.004",
         "AR increments in $R^2$ were ${token}$"),
        ("AR_CONCH_CI_LOW", "ar:CONCH:increment", "ci_low", "+.3f", "-0.036",
         "$R^2$ were $+0.004$ (${token}$"),
        ("AR_CONCH_CI_HIGH", "ar:CONCH:increment", "ci_high", "+.3f", "+0.042",
         "$+0.004$ ($-0.036$ to ${token}$)"),
        ("AR_VIRCHOW_DELTA", "ar:Virchow:increment", "primary_estimate", "+.3f", "+0.019",
         "$+0.042$) and ${token}$"),
        ("AR_VIRCHOW_CI_LOW", "ar:Virchow:increment", "ci_low", "+.3f", "-0.015",
         "and $+0.019$ (${token}$"),
        ("AR_VIRCHOW_CI_HIGH", "ar:Virchow:increment", "ci_high", "+.3f", "+0.051",
         "$+0.019$ ($-0.015$ to ${token}$)"),
    )
    for item in increments:
        add(item[0], f4, f"semantic_key={item[1]}", *item[2:])

    derived("STABILITY_CONFIGURATIONS", "STABILITY_CONFIGURATIONS", "value", "int", "12",
            "summarized across {token} encoder--scale--tile configurations")
    derived("STABILITY_CONFIGURATIONS_ARITHMETIC", "STABILITY_CONFIGURATIONS", "value",
            "int", "12", "$6\\times{token}\\times5=360$")
    derived("STABILITY_MARKERS", "STABILITY_MARKERS", "value", "int", "6",
            "giving ${token}\\times12\\times5=360$")
    derived("STABILITY_SEEDS", "STABILITY_SEEDS", "value", "int", "5",
            "$6\\times12\\times{token}=360$")
    derived("STABILITY_TOTAL_CELLS_DESIGN", "STABILITY_TOTAL_CELLS", "value", "int", "360",
            "$6\\times12\\times5={token}$ correlated seed cells")
    add("SPOP_NULL_STRADDLE_RESULT", f6, "semantic_key=spop:configuration_range",
        "n_null_crossings/n_configurations", "ratio", "8/12",
        "straddled the null for SPOP in ${token}$ configurations")
    add("MARKER7_NULL_STRADDLE_RESULT", f6, "semantic_key=marker7:configuration_range",
        "n_null_crossings/n_configurations", "ratio", "1/12",
        "recurrence risk signal in ${token}$. Across")
    derived("STABILITY_CELLS_PER_MARKER", "STABILITY_CELLS_PER_MARKER", "value", "int", "60",
            "Across the {token} seed cells for each target")
    for item in (
        ("GLEASON_STABILITY_LOW", "gleason:configuration_range", "range_low", ".3f", "0.271",
         "global seed-cell range was ${token}$--$0.646$ for Gleason"),
        ("GLEASON_STABILITY_HIGH", "gleason:configuration_range", "range_high", ".3f", "0.646",
         "range was $0.271$--${token}$ for Gleason"),
        ("PHENOTYPE_STABILITY_LOW", "phenotype:configuration_range", "range_low", ".3f", "0.845",
         "and ${token}$--$0.965$ for phenotype"),
        ("PHENOTYPE_STABILITY_HIGH", "phenotype:configuration_range", "range_high", ".3f", "0.965",
         "and $0.845$--${token}$ for phenotype"),
    ):
        add(item[0], f6, f"semantic_key={item[1]}", *item[2:])
    derived("STABILITY_TOTAL_CELLS_LIMITATION", "STABILITY_TOTAL_CELLS", "value", "int", "360",
            "The {token} cells are correlated sensitivity settings")
    add("SPOP_NULL_STRADDLE_LIMITATION", f6, "semantic_key=spop:configuration_range",
        "n_null_crossings/n_configurations", "ratio", "8/12",
        "the ${token}$ and $1/12$ counts")
    add("MARKER7_NULL_STRADDLE_LIMITATION", f6, "semantic_key=marker7:configuration_range",
        "n_null_crossings/n_configurations", "ratio", "1/12",
        "$8/12$ and ${token}$ counts")

    e04_risk = "semantic_key=E04_reconstructed_with_tumor:frozen_risk:c_index"
    e08_risk = "semantic_key=E08_official_pfi:frozen_risk:c_index"
    e04_delta = "semantic_key=E04_reconstructed_with_tumor:GRADE_COMBINED_VS_GRADE:c_index"
    e08_delta = "semantic_key=E08_official_pfi:GRADE_COMBINED_VS_GRADE:c_index"
    add("RECURRENCE_TARGET_N", f5, e04_risk, "n", "int", "270",
        "to a fixed {token}-patient TCGA-PRAD target frame")
    add("COMMON_COHORT_N", f5, e04_delta, "n", "int", "153",
        "used the same {token}-patient complete-case cohort")
    add("COMMON_RECON_EVENTS", f5, e04_delta, "n_events", "int", "30",
        "with {token} reconstructed-endpoint events")
    add("COMMON_OFFICIAL_EVENTS", f5, e08_delta, "n_events", "int", "15",
        "and {token} official PFI events")
    add("RECON_RISK_CINDEX", f5, e04_risk, "primary_estimate", ".3f", "0.673",
        "reconstructed endpoint, the concordance index (C-index) was ${token}$")
    derived("RECON_RISK_CI_LEVEL", "PFI_PERCENTILE_INTERVAL_LEVEL", "value", "int", "95",
            "concordance index (C-index) was $0.673$ ({token}\\%")
    add("RECON_RISK_CI_LOW", f5, e04_risk, "ci_low", ".3f", "0.587",
        "confidence interval (CI) ${token}$")
    add("RECON_RISK_CI_HIGH", f5, e04_risk, "ci_high", ".3f", "0.759",
        "$0.587$--${token}$;")
    add("RECON_RISK_N", f5, e04_risk, "n", "int", "270",
        "$0.759$; {token} patients")
    add("RECON_RISK_EVENTS", f5, e04_risk, "n_events", "int", "57",
        "$0.587$--$0.759$; 270 patients, {token} events)")
    add("OFFICIAL_PFI_CINDEX", f5, e08_risk, "primary_estimate", ".3f", "0.586",
        "official PFI C-index was {token}")
    derived("OFFICIAL_PFI_CI_LEVEL", "PFI_PERCENTILE_INTERVAL_LEVEL", "value", "int", "95",
            "official PFI C-index was 0.586 ({token}\\% CI")
    add("OFFICIAL_PFI_CI_LOW", f5, e08_risk, "ci_low", ".3f", "0.482",
        "0.586 (95\\% CI {token}")
    add("OFFICIAL_PFI_CI_HIGH", f5, e08_risk, "ci_high", ".3f", "0.689",
        "CI 0.482--{token};")
    add("OFFICIAL_PFI_N", f5, e08_risk, "n", "int", "270",
        "0.689; {token} patients")
    add("OFFICIAL_PFI_EVENTS", f5, e08_risk, "n_events", "int", "42",
        "official PFI C-index was 0.586 (95\\% CI 0.482--0.689; "
        "270 patients, {token} events)")
    add("RECON_GRADE_DELTA", f5, e04_delta, "primary_estimate", "+.3f", "+0.083",
        "grade-plus-image versus grade delta C-index was ${token}$")
    derived("RECON_GRADE_DELTA_CI_LEVEL", "PAIRED_PERCENTILE_INTERVAL_LEVEL", "value",
            "int", "95", "delta C-index was $+0.083$ ({token}\\% CI")
    add("RECON_GRADE_DELTA_CI_LOW", f5, e04_delta, "ci_low", "+.3f", "+0.012",
        "$+0.083$ (95\\% CI ${token}$")
    add("RECON_GRADE_DELTA_CI_HIGH", f5, e04_delta, "ci_high", "+.3f", "+0.157",
        "CI $+0.012$ to ${token}$)")
    add("OFFICIAL_GRADE_DELTA", f5, e08_delta, "primary_estimate", "+.3f", "+0.032",
        "official PFI grade-plus-image increment was ${token}$")
    add("OFFICIAL_GRADE_DELTA_CI_LOW", f5, e08_delta, "ci_low", "+.3f", "-0.040",
        "increment was $+0.032$ (${token}$")
    add("OFFICIAL_GRADE_DELTA_CI_HIGH", f5, e08_delta, "ci_high", "+.3f", "+0.126",
        "$+0.032$ ($-0.040$ to ${token}$)")

    if len({row["claim_id"] for row in rows}) != len(rows):
        raise ValueError("numeric occurrence claim_id values must be unique")
    return rows


_UNSIGNED_ASCII_NUMBER = (
    r"(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|"
    r"[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
_SIGNED_ASCII_NUMBER = rf"(?:\+|(?<!-)-)?{_UNSIGNED_ASCII_NUMBER}"
_ASCII_NUMERIC_TOKEN = re.compile(
    rf"(?P<number>{_SIGNED_ASCII_NUMBER}(?:/{_SIGNED_ASCII_NUMBER})?)"
)
_INFINITY_TOKEN = re.compile(r"(?:(?:[+\-−]|\\pm)\s*)?(?:∞|\\infty)")
_NONFINITE_TOKEN = re.compile(
    r"(?<![A-Za-z])(?:Infinity|NaN|Inf)(?![A-Za-z])", re.IGNORECASE
)
_ROMAN_QUANTITATIVE_TOKEN = re.compile(
    r"(?<![A-Za-z])(?:III|II|IV|V)[ABC]?(?![A-Za-z])", re.IGNORECASE
)


def _numeric_occurrences(text: str) -> list[tuple[int, int, str]]:
    spans = {
        (match.start("number"), match.end("number"), match.group("number"))
        for match in _ASCII_NUMERIC_TOKEN.finditer(text)
    }
    for pattern in (_INFINITY_TOKEN, _NONFINITE_TOKEN, _ROMAN_QUANTITATIVE_TOKEN):
        spans.update(
            (match.start(), match.end(), match.group())
            for match in pattern.finditer(text)
        )
    index = 0
    while index < len(text):
        if ord(text[index]) > 127 and text[index].isnumeric():
            end = index + 1
            while (end < len(text) and ord(text[end]) > 127
                   and text[end].isnumeric()):
                end += 1
            spans.add((index, end, text[index:end]))
            index = end
        else:
            index += 1
    return sorted(spans)


STRUCTURAL_NUMERIC_OCCURRENCES = (
    {
        "occurrence_id": "STRUCT_ISUP_BENIGN",
        "expected_token": "0",
        "context_anchor": "phenotype label defined ISUP {token} as benign",
    },
    {
        "occurrence_id": "STRUCT_ISUP_TUMOR",
        "expected_token": "1",
        "context_anchor": "ISUP $\\geq{token}$ as tumor",
    },
    {
        "occurrence_id": "STRUCT_R_SQUARED",
        "expected_token": "2",
        "context_anchor": "corresponding AR increments in $R^{token}$ were",
    },
    {
        "occurrence_id": "STRUCT_LEGACY_MARKER7_NAME",
        "expected_token": "7",
        "context_anchor": "This score is called ``marker {token}'' only in legacy analysis artifacts",
    },
)


TECHNICAL_NUMERIC_OCCURRENCES = (
    {
        "occurrence_id": "TECH_INPUT_TABLE1",
        "expected_token": "1",
        "context_anchor": r"\input{generated/table{token}_qualification_summary.tex}",
    },
    {
        "occurrence_id": "TECH_FIG1_PATH",
        "expected_token": "1",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig{token}_qualification_map.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_FIG2_PATH",
        "expected_token": "2",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig{token}_transportable_signals.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_FIG3_PATH",
        "expected_token": "3",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig{token}_molecular_qualification.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_FIG4_PATH",
        "expected_token": "4",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig{token}_confounder_site_audit.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_MARKER7_REF_STABILITY",
        "expected_token": "7",
        "context_anchor": (
            "endpoint-conditioned transfer summary "
            r"(Figure~\ref{fig:marker{token}-transfer}), and the decision-level grid summary"
        ),
    },
    {
        "occurrence_id": "TECH_FIG5_PATH",
        "expected_token": "5",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig{token}_marker7_transfer.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_FIG5_MARKER7_PATH",
        "expected_token": "7",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig5_marker{token}_transfer.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_MARKER7_LABEL",
        "expected_token": "7",
        "context_anchor": r"\label{fig:marker{token}-transfer}",
    },
    {
        "occurrence_id": "TECH_FIG6_PATH",
        "expected_token": "6",
        "context_anchor": (
            r"\includegraphics[width=\textwidth]"
            r"{figures/fig{token}_stability_overview.pdf}"
        ),
    },
    {
        "occurrence_id": "TECH_MARKER7_REF_RECURRENCE",
        "expected_token": "7",
        "context_anchor": (
            r"15 official PFI events (Figure~\ref{fig:marker{token}-transfer}). "
            r"\paragraph{Evidence state.}"
        ),
    },
)


def _anchor_matches(text: str, context_anchor: str, expected_token: str) -> list[re.Match[str]]:
    """Match an occurrence anchor while treating TeX source whitespace as insignificant."""
    if context_anchor.count("{token}") != 1:
        raise ValueError("numeric context_anchor must contain exactly one {token} placeholder")
    prefix, suffix = context_anchor.split("{token}")

    def flexible_whitespace(fragment: str) -> str:
        return r"\s+".join(re.escape(part) for part in re.split(r"\s+", fragment))

    pattern = (
        flexible_whitespace(prefix)
        + rf"(?P<token>{re.escape(expected_token)})"
        + flexible_whitespace(suffix)
    )
    return list(re.finditer(pattern, text))


def _resolve_numeric_locator_spans(
    text: str, occurrences: tuple[dict[str, str], ...], locator_kind: str,
) -> set[tuple[int, int, str]]:
    """Resolve a closed set of exact numeric locators, failing on any drift."""
    occurrence_ids = [item["occurrence_id"] for item in occurrences]
    anchors = [item["context_anchor"] for item in occurrences]
    if len(set(occurrence_ids)) != len(occurrence_ids):
        raise ValueError(f"{locator_kind} numeric occurrence_id values must be unique")
    if len(set(anchors)) != len(anchors):
        raise ValueError(f"{locator_kind} numeric context_anchor values must be unique")

    numeric_spans = set(_numeric_occurrences(text))
    resolved_spans: set[tuple[int, int, str]] = set()
    for item in occurrences:
        matches = _anchor_matches(text, item["context_anchor"], item["expected_token"])
        if len(matches) != 1:
            raise ValueError(
                f"{item['occurrence_id']} {locator_kind} locator must match exactly once; "
                f"found {len(matches)}"
            )
        match = matches[0]
        span = (match.start("token"), match.end("token"), item["expected_token"])
        if span not in numeric_spans:
            raise ValueError(f"{item['occurrence_id']} did not resolve to a numeric occurrence")
        if span in resolved_spans:
            raise ValueError(
                f"{item['occurrence_id']} duplicates a {locator_kind} numeric span"
            )
        resolved_spans.add(span)
    return resolved_spans


def _structural_numeric_spans(text: str) -> set[tuple[int, int, str]]:
    """Resolve the exact, closed set of non-data numeric Results occurrences."""
    return _resolve_numeric_locator_spans(
        text, STRUCTURAL_NUMERIC_OCCURRENCES, "structural"
    )


def _technical_numeric_spans(text: str) -> set[tuple[int, int, str]]:
    """Resolve the exact, closed set of technical numeric Results occurrences."""
    return _resolve_numeric_locator_spans(
        text, TECHNICAL_NUMERIC_OCCURRENCES, "technical"
    )


def run_numeric_qa(stage_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate each quantitative occurrence in its unique TeX context."""
    columns = [
        "claim_id", "source_path", "row_key", "field", "display_format",
        "expected_tex_token", "tex_path", "context_anchor",
    ]
    mapping = pd.DataFrame(_numeric_rows(), columns=columns).sort_values("claim_id")
    if mapping["context_anchor"].duplicated().any():
        raise ValueError("numeric mapping context_anchor values must be unique")
    checks = []
    mapped_spans: set[tuple[int, int, str]] = set()
    text_by_path: dict[str, str] = {}
    failures: list[str] = []
    for item in mapping.itertuples(index=False):
        tex_file = Path(stage_root) / item.tex_path
        if not tex_file.is_file():
            tex_file = ROOT / item.tex_path
        text = text_by_path.setdefault(item.tex_path, tex_file.read_text(encoding="utf-8"))
        anchor_matches = _anchor_matches(text, item.context_anchor, item.expected_tex_token)
        context_matches = len(anchor_matches)
        context_ok = context_matches == 1
        if context_ok:
            token_match = anchor_matches[0]
            span = (
                token_match.start("token"),
                token_match.end("token"),
                item.expected_tex_token,
            )
            if span in mapped_spans:
                raise ValueError(f"numeric occurrence mapped more than once: {item.claim_id}")
            mapped_spans.add(span)
        selected = _select_csv(item.source_path, item.row_key, package_root=stage_root)
        value = _mapped_value(selected, item.field)
        if item.display_format == "ratio":
            actual = f"{int(value[0])}/{int(value[1])}"  # type: ignore[index]
        else:
            actual = _format_value(value, item.display_format)
        passed = context_ok and actual == item.expected_tex_token
        checks.append({
            "claim_id": item.claim_id, "passed": passed,
            "context_matches": context_matches, "actual_tex_token": actual,
            "expected_tex_token": item.expected_tex_token,
        })
        if not passed:
            failures.append(item.claim_id)

    results_path = "paper/sections/results.tex"
    results = text_by_path.get(results_path)
    if results is None:
        raise ValueError("numeric mapping does not cover the Results source")
    structural_spans = _structural_numeric_spans(results)
    technical_spans = _technical_numeric_spans(results)
    if structural_spans & technical_spans:
        raise ValueError("structural and technical numeric spans must be disjoint")
    scientific_spans = (
        set(_numeric_occurrences(results)) - structural_spans - technical_spans
    )
    missing = sorted(scientific_spans - mapped_spans)
    extra = sorted(mapped_spans - scientific_spans)
    if missing or extra:
        preview = [f"{value_token}@{start}" for start, _end, value_token in missing[:8]]
        raise ValueError(
            f"numeric occurrence coverage failed; missing={preview}, extra={len(extra)}"
        )
    mapping_path = Path(stage_root) / "paper/numeric_qa_mapping.csv"
    report_path = Path(stage_root) / "paper/numeric_consistency_report.csv"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(mapping_path, index=False, lineterminator="\n")
    qa = pd.DataFrame(checks)
    qa.to_csv(report_path, index=False, lineterminator="\n")
    if failures:
        raise ValueError(f"numeric context/source QA failed: {failures}")
    return mapping, qa


def _build_tex(stage_root: Path, name: str) -> tuple[Path, Path]:
    paper = stage_root / "paper"
    logs = []
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = "0"
    for _ in range(2):
        run = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", name], cwd=paper,
            text=True, capture_output=True, env=environment,
        )
        logs.append(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError(f"XeLaTeX failed for {name}")
    log = logs[-1]
    unresolved = re.search(
        r"Citation .* undefined|Reference .* undefined|There were undefined references", log,
        flags=re.IGNORECASE,
    )
    overfull = [float(value) for value in re.findall(r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)", log)]
    if unresolved or any(value > 1.0 for value in overfull):
        raise RuntimeError(f"TeX QA failed for {name}: unresolved={bool(unresolved)}, overfull={overfull}")
    log_path = paper / f"{Path(name).stem}_build.log"
    log_path.write_text(log, encoding="utf-8", newline="\n")
    pdf = paper / f"{Path(name).stem}.pdf"
    if not pdf.is_file():
        raise RuntimeError(f"XeLaTeX emitted no PDF for {name}")
    return pdf, log_path


def validate_manifest_freshness(manifest_path: Path, package_root: Path) -> None:
    """Reject outputs that predate any declared source or renderer."""
    frame = pd.read_csv(manifest_path)
    for row in frame.to_dict("records"):
        output = Path(package_root) / row["output_path"]
        dependencies = [ROOT / path for path in row["source_paths"].split(";")]
        dependencies.append(ROOT / row["script_path"])
        if not output.is_file() or output.stat().st_mtime < max(
            dependency.stat().st_mtime for dependency in dependencies
        ):
            raise ValueError(f"{row.get('figure_id', row.get('table_id'))} output is stale")


def determine_package_status(author_actions_path: Path) -> tuple[str, int]:
    """Return the validated declared package state and open blocker count."""
    text = Path(author_actions_path).read_text(encoding="utf-8")
    statuses = re.findall(r"(?m)^package_status:\s*(\S+)\s*$", text)
    if len(statuses) != 1 or statuses[0] not in {"partial", "ready"}:
        raise ValueError("author actions must declare exactly one valid package_status")
    blocking_values = re.findall(r"(?m)^blocking:\s*(\S+)\s*$", text)
    if any(value not in {"yes", "no"} for value in blocking_values):
        raise ValueError("author actions contain an invalid blocking declaration")
    blocker_count = sum(value == "yes" for value in blocking_values)
    expected = "partial" if blocker_count else "ready"
    if statuses[0] != expected:
        raise ValueError(
            f"package_status is inconsistent with {blocker_count} open blocking actions"
        )
    return statuses[0], blocker_count


def _write_reports(
    stage_root: Path, build_pdf: bool, status: str, blocker_count: int,
) -> None:
    (stage_root / "paper/compliance_report.md").write_text(
        "# Submission compliance report\n\n"
        f"- Package status: {status}\n"
        f"- Open blocking author actions: {blocker_count}\n"
        "- Active figures: 6 main and 3 supplementary\n"
        f"- PDFs built twice: {'yes' if build_pdf else 'skipped by request'}\n"
        "- Author-controlled actions remain explicit and are not treated as build failures.\n",
        encoding="utf-8", newline="\n",
    )


OPTIONAL_BUILD_OUTPUTS = (
    Path("paper/main.pdf"),
    Path("paper/supplement_main.pdf"),
    Path("paper/main_build.log"),
    Path("paper/supplement_main_build.log"),
)
TRANSIENT_TEX_OUTPUTS = tuple(
    Path(f"paper/{stem}{suffix}")
    for stem in ("main", "supplement_main")
    for suffix in (".aux", ".log", ".out", ".toc")
)


def _atomic_copy(source: Path, target: Path) -> None:
    """Copy through a sibling temporary file so ``target`` is never partial."""
    target.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{target.name}.publish-", dir=target.parent, delete=False,
        ) as handle:
            staged = Path(handle.name)
        shutil.copy2(source, staged)
        os.replace(staged, target)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def _transactional_publish(stage_root: Path, output_root: Path, repository_run: bool) -> None:
    if repository_run:
        selected = [
            *(Path(spec.output) for spec in (*MAIN_FIGURES, *SUPPLEMENT_FIGURES)),
            *(Path(spec.output) for spec in TABLES),
            Path("paper/figure_manifest.csv"), Path("paper/table_manifest.csv"),
            Path("paper/numeric_qa_mapping.csv"), Path("paper/numeric_consistency_report.csv"),
            Path("paper/results_numeric_derivations.csv"),
            Path("paper/compliance_report.md"),
        ]
        for optional in OPTIONAL_BUILD_OUTPUTS:
            if (stage_root / optional).is_file():
                selected.append(optional)
    else:
        selected = sorted(
            path.relative_to(stage_root) for path in stage_root.rglob("*")
            if path.is_file() and path.relative_to(stage_root) not in TRANSIENT_TEX_OUTPUTS
        )

    stale_outputs = [] if repository_run else [
        relative for relative in (*OPTIONAL_BUILD_OUTPUTS, *TRANSIENT_TEX_OUTPUTS)
        if (output_root / relative).is_file()
        and (
            relative in TRANSIENT_TEX_OUTPUTS
            or not (stage_root / relative).is_file()
        )
    ]

    backup_parent = Path("/tmp") if repository_run else output_root.parent
    backup_root = Path(tempfile.mkdtemp(prefix="submission-backup-", dir=backup_parent))
    mutation_order: list[Path] = []
    backups: dict[Path, Path] = {}
    try:
        for relative in (*selected, *stale_outputs):
            target = output_root / relative
            if target.exists():
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backups[target] = backup

        for relative in stale_outputs:
            target = output_root / relative
            target.unlink()
            mutation_order.append(target)

        for relative in selected:
            source, target = stage_root / relative, output_root / relative
            _atomic_copy(source, target)
            mutation_order.append(target)
    except Exception:
        for target in reversed(mutation_order):
            backup = backups.get(target)
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_copy(backup, target)
        raise
    finally:
        shutil.rmtree(backup_root)


def build_submission_package(output_root: Path, build_pdf: bool = True) -> PackageReport:
    """Stage, validate, then transactionally publish a complete submission package."""
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    repository_run = output_root == ROOT.resolve()
    if not PRECISE.is_file() or sha256(PRECISE) != PRECISE_SHA256:
        raise ValueError("immutable PRECISE clinician source hash mismatch")
    status, blocker_count = determine_package_status(PAPER / "author_action_items.md")
    stage_parent = Path("/tmp") if repository_run else output_root.parent
    stage_root = Path(tempfile.mkdtemp(prefix="submission-stage-", dir=stage_parent))
    try:
        _copy_paper_sources(stage_root)
        generate_submission_tables(ROOT, stage_root)
        _render_figures(stage_root)
        build_figure_manifest(stage_root)
        build_table_manifest(stage_root)
        _generate_numeric_derivations(stage_root)
        run_numeric_qa(stage_root)
        main_pdf = supplement_pdf = None
        if build_pdf:
            main_pdf, _ = _build_tex(stage_root, "main.tex")
            supplement_pdf, _ = _build_tex(stage_root, "supplement_main.tex")
        _write_reports(stage_root, build_pdf, status, blocker_count)
        _transactional_publish(stage_root, output_root, repository_run)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

    paper = output_root / "paper"
    return PackageReport(
        output_root=output_root,
        figure_manifest=paper / "figure_manifest.csv",
        table_manifest=paper / "table_manifest.csv",
        numeric_mapping=paper / "numeric_qa_mapping.csv",
        numeric_report=paper / "numeric_consistency_report.csv",
        reproducibility_report=paper / "reproducibility_report.md",
        compliance_report=paper / "compliance_report.md",
        main_pdf=(paper / "main.pdf") if build_pdf else None,
        supplement_pdf=(paper / "supplement_main.pdf") if build_pdf else None,
        status=status,
        blocker_count=blocker_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()
    report = build_submission_package(args.output_root, build_pdf=not args.skip_pdf)
    print(f"submission package {report.status}: {report.output_root}")


if __name__ == "__main__":
    main()
