"""Tiered medical metrics plus a separate legacy analysis-measure registry."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Iterable


VALID_STATUSES = frozenset({"active", "audit", "exploratory", "deferred"})
VALID_TIERS = frozenset({"T1", "T2", "T3", "T4"})


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Legacy definition for any calculated measure, including evaluation statistics."""

    metric_id: str
    domain: str
    status: str
    name_ko: str
    name_en: str
    analysis_unit: str
    null_or_range: str
    formula: str
    interpretation: str
    source_paths: tuple[str, ...]

    def as_dict(self) -> dict[str, str]:
        row = asdict(self)
        row["source_paths"] = ";".join(self.source_paths)
        return row


@dataclass(frozen=True, slots=True)
class MedicalMetricDefinition:
    """Clinician-native or explicitly downstream medical-data quantity."""

    metric_id: str
    tier: str
    tier_name: str
    domain: str
    status: str
    name_ko: str
    name_en: str
    analysis_unit: str
    unit_or_scale: str
    source_type: str
    parent_metric_ids: tuple[str, ...]
    clinical_use: str
    interpretation: str
    evidence_basis: str

    def as_dict(self) -> dict[str, str]:
        row = asdict(self)
        row["parent_metric_ids"] = ";".join(self.parent_metric_ids)
        return row


def _resource_rows(name: str) -> list[dict[str, str]]:
    resource = files("vlm_pathology_metrics").joinpath(f"data/{name}")
    with resource.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _load_measure_catalog() -> tuple[MetricDefinition, ...]:
    definitions = tuple(
        MetricDefinition(
            metric_id=row["metric_id"], domain=row["domain"], status=row["status"],
            name_ko=row["name_ko"], name_en=row["name_en"],
            analysis_unit=row["analysis_unit"], null_or_range=row["null_or_range"],
            formula=row["formula"], interpretation=row["interpretation"],
            source_paths=tuple(filter(None, row["source_paths"].split(";"))),
        )
        for row in _resource_rows("legacy/metric_catalog_113.tsv")
    )
    _validate_measure_catalog(definitions)
    return definitions


def _load_medical_catalog() -> tuple[MedicalMetricDefinition, ...]:
    rows = []
    for name in (
        "medical/tier1_clinician_native.tsv",
        "medical/tier2_clinician_anchored.tsv",
        "medical/tier3_research_computational.tsv",
        "medical/tier4_model_derived.tsv",
    ):
        rows.extend(_resource_rows(name))
    definitions = tuple(
        MedicalMetricDefinition(
            metric_id=row["metric_id"], tier=row["tier"], tier_name=row["tier_name"],
            domain=row["domain"], status=row["status"], name_ko=row["name_ko"],
            name_en=row["name_en"], analysis_unit=row["analysis_unit"],
            unit_or_scale=row["unit_or_scale"], source_type=row["source_type"],
            parent_metric_ids=tuple(filter(None, row["parent_metric_ids"].split(";"))),
            clinical_use=row["clinical_use"], interpretation=row["interpretation"],
            evidence_basis=row["evidence_basis"],
        )
        for row in rows
    )
    _validate_medical_catalog(definitions)
    return definitions


def _load_analysis_catalog() -> tuple[MetricDefinition, ...]:
    definitions = tuple(
        MetricDefinition(
            metric_id=row["metric_id"], domain=row["domain"], status=row["status"],
            name_ko=row["name_ko"], name_en=row["name_en"],
            analysis_unit=row["analysis_unit"], null_or_range=row["null_or_range"],
            formula=row["formula"], interpretation=row["interpretation"],
            source_paths=tuple(filter(None, row["source_paths"].split(";"))),
        )
        for row in _resource_rows("analysis/analysis_measure_catalog.tsv")
    )
    _validate_measure_catalog(definitions)
    return definitions


def _duplicates(values: Iterable[str]) -> list[str]:
    values = tuple(values)
    return sorted({value for value in values if values.count(value) > 1})


def _validate_measure_catalog(definitions: Iterable[MetricDefinition]) -> None:
    definitions = tuple(definitions)
    duplicates = _duplicates(item.metric_id for item in definitions)
    if duplicates:
        raise ValueError(f"Duplicate measure IDs: {duplicates}")
    invalid = sorted({item.status for item in definitions} - VALID_STATUSES)
    if invalid:
        raise ValueError(f"Invalid measure statuses: {invalid}")
    for item in definitions:
        if not all((item.metric_id, item.domain, item.name_en, item.formula, item.source_paths)):
            raise ValueError(f"Incomplete measure definition: {item.metric_id}")


def _validate_medical_catalog(definitions: Iterable[MedicalMetricDefinition]) -> None:
    definitions = tuple(definitions)
    duplicates = _duplicates(item.metric_id for item in definitions)
    if duplicates:
        raise ValueError(f"Duplicate medical metric IDs: {duplicates}")
    ids = {item.metric_id for item in definitions}
    tier_number = {tier: int(tier[1:]) for tier in VALID_TIERS}
    by_id = {item.metric_id: item for item in definitions}
    for item in definitions:
        if item.tier not in VALID_TIERS or item.status not in VALID_STATUSES:
            raise ValueError(f"Invalid tier/status in {item.metric_id}: {item.tier}/{item.status}")
        if not all((item.metric_id, item.domain, item.name_en, item.analysis_unit,
                    item.source_type, item.clinical_use, item.evidence_basis)):
            raise ValueError(f"Incomplete medical metric definition: {item.metric_id}")
        if item.tier == "T1" and item.parent_metric_ids:
            raise ValueError(f"T1 metric cannot have a parent: {item.metric_id}")
        if item.tier != "T1" and not item.parent_metric_ids:
            raise ValueError(f"Derived metric needs a medical parent: {item.metric_id}")
        unknown = set(item.parent_metric_ids) - ids
        if unknown:
            raise ValueError(f"Unknown medical parents in {item.metric_id}: {sorted(unknown)}")
        for parent_id in item.parent_metric_ids:
            if tier_number[by_id[parent_id].tier] >= tier_number[item.tier]:
                raise ValueError(f"Parent must be in a higher tier: {parent_id} -> {item.metric_id}")


MEASURE_CATALOG = _load_measure_catalog()
MEDICAL_CATALOG = _load_medical_catalog()
CATALOG = MEDICAL_CATALOG
_MEDICAL_IDS = frozenset(item.metric_id for item in MEDICAL_CATALOG)
ANALYSIS_CATALOG = _load_analysis_catalog()
_LEGACY_MEDICAL_IDS = _MEDICAL_IDS & {item.metric_id for item in MEASURE_CATALOG}
if {item.metric_id for item in MEASURE_CATALOG} != (
    _LEGACY_MEDICAL_IDS | {item.metric_id for item in ANALYSIS_CATALOG}
):
    raise ValueError("Medical/analysis catalogs do not partition the legacy 113-measure registry")
if _MEDICAL_IDS & {item.metric_id for item in ANALYSIS_CATALOG}:
    raise ValueError("Medical and analysis catalogs overlap")
ALL_REGISTERED_MEASURES = MEDICAL_CATALOG + ANALYSIS_CATALOG


def catalog(
    *, domain: str | None = None, status: str | None = None, tier: str | None = None,
) -> tuple[MedicalMetricDefinition, ...]:
    """Return only tiered medical-data metrics; model evaluation is excluded."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    if tier is not None and tier not in VALID_TIERS:
        raise ValueError(f"tier must be one of {sorted(VALID_TIERS)}")
    return tuple(
        item for item in MEDICAL_CATALOG
        if (domain is None or item.domain == domain)
        and (status is None or item.status == status)
        and (tier is None or item.tier == tier)
    )


def analysis_catalog(
    *, domain: str | None = None, status: str | None = None,
) -> tuple[MetricDefinition, ...]:
    """Return evaluation, inference, QC, audit, and other non-medical measures."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    return tuple(
        item for item in ANALYSIS_CATALOG
        if (domain is None or item.domain == domain)
        and (status is None or item.status == status)
    )


def measure_catalog(
    *, domain: str | None = None, status: str | None = None,
) -> tuple[MetricDefinition, ...]:
    """Return the legacy 113-measure registry for reproducibility only."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    return tuple(
        item for item in MEASURE_CATALOG
        if (domain is None or item.domain == domain)
        and (status is None or item.status == status)
    )


def get_metric(metric_id: str) -> MedicalMetricDefinition:
    """Return one tiered medical metric; analysis measures deliberately do not match."""
    matches = [item for item in MEDICAL_CATALOG if item.metric_id == metric_id]
    if not matches:
        raise KeyError(metric_id)
    return matches[0]


def get_measure(metric_id: str) -> MetricDefinition | MedicalMetricDefinition:
    """Resolve either a medical metric or a legacy analysis measure."""
    medical = [item for item in MEDICAL_CATALOG if item.metric_id == metric_id]
    if medical:
        return medical[0]
    matches = [item for item in MEASURE_CATALOG if item.metric_id == metric_id]
    if not matches:
        raise KeyError(metric_id)
    return matches[0]


def _export(records: tuple[object, ...], path: str | Path, *, format: str) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = [item.as_dict() for item in records]
    if format == "csv":
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    elif format == "markdown":
        medical = isinstance(records[0], MedicalMetricDefinition)
        if medical:
            lines = ["| ID | Tier | 영역 | 상태 | 지표 | 임상 역할 |", "|---|---|---|---|---|---|"]
            for item in records:
                lines.append(
                    f"| `{item.metric_id}` | {item.tier} | {item.domain} | {item.status} | "
                    f"{item.name_ko} ({item.name_en}) | {item.clinical_use} |"
                )
        else:
            lines = ["| ID | 영역 | 상태 | 분석량 | 정의/공식 |", "|---|---|---|---|---|"]
            for item in records:
                formula = item.formula.replace("|", "\\|")
                lines.append(
                    f"| `{item.metric_id}` | {item.domain} | {item.status} | "
                    f"{item.name_ko} ({item.name_en}) | {formula} |"
                )
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ValueError("format must be 'csv' or 'markdown'")
    return destination


def export_catalog(path: str | Path, *, format: str = "csv") -> Path:
    """Export the tiered medical metric catalog only."""
    return _export(MEDICAL_CATALOG, path, format=format)


def export_analysis_catalog(path: str | Path, *, format: str = "csv") -> Path:
    """Export non-medical evaluation/statistics/QC measures."""
    return _export(ANALYSIS_CATALOG, path, format=format)


def export_measure_catalog(path: str | Path, *, format: str = "csv") -> Path:
    """Export the full legacy 113-measure registry for provenance."""
    return _export(MEASURE_CATALOG, path, format=format)
