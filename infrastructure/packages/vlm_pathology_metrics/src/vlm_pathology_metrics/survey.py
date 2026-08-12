"""Disease-use survey, curated combinations, and complete metric scope mapping."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from .catalog import ALL_REGISTERED_MEASURES, MEDICAL_CATALOG, get_measure


VALID_ROLES = frozenset({
    "diagnostic_adjuvant",
    "candidate_triage",
    "histopathology_annotation",
    "grading_risk_feature",
    "molecular_screening",
    "prognostic_stratification",
    "research_feature",
    "evaluation_only",
})
VALID_READINESS = frozenset({
    "ready_project",
    "literature_supported_unvalidated_transfer",
    "research_only",
    "external_panel_required",
    "deferred_until_contours",
    "unsupported_current_design",
})
VALID_EVIDENCE = frozenset({
    "project_validated_selected_sample",
    "guideline_or_consensus",
    "systematic_review_meta_analysis",
    "multi_cohort_validation",
    "single_cohort_or_narrative_review",
    "project_exploratory",
    "methodological_only",
})


@dataclass(frozen=True, slots=True)
class SurveyReference:
    reference_id: str
    citation: str
    year: int
    evidence_type: str
    diseases: tuple[str, ...]
    key_finding_ko: str
    url: str
    doi: str


@dataclass(frozen=True, slots=True)
class DiseaseMetricUse:
    use_id: str
    disease_id: str
    disease_name_ko: str
    disease_name_en: str
    medical_metric_ids: tuple[str, ...]
    analysis_measure_ids: tuple[str, ...]
    clinical_role: str
    evidence_tier: str
    package_readiness: str
    summary_ko: str
    limitations_ko: str
    reference_ids: tuple[str, ...]

    @property
    def metric_ids(self) -> tuple[str, ...]:
        """Backward-compatible union; use the two explicit fields in new outputs."""
        return self.medical_metric_ids + self.analysis_measure_ids


@dataclass(frozen=True, slots=True)
class MetricCombination:
    combination_id: str
    disease_id: str
    combination_name_ko: str
    medical_metric_ids: tuple[str, ...]
    analysis_measure_ids: tuple[str, ...]
    external_components: tuple[str, ...]
    intended_use_ko: str
    evidence_tier: str
    package_readiness: str
    decision_rule_ko: str
    limitations_ko: str
    reference_ids: tuple[str, ...]

    @property
    def metric_ids(self) -> tuple[str, ...]:
        """Backward-compatible union; medical and analysis IDs remain distinguishable."""
        return self.medical_metric_ids + self.analysis_measure_ids


@dataclass(frozen=True, slots=True)
class MetricDiseaseScope:
    metric_id: str
    metric_name_ko: str
    domain: str
    applicability_class: str
    disease_ids: tuple[str, ...]
    clinical_roles: tuple[str, ...]
    diagnostic_adjuvant_mapping: bool
    standalone_diagnostic_use: bool
    summary_ko: str


def _resource_rows(name: str) -> list[dict[str, str]]:
    resource = files("vlm_pathology_metrics").joinpath(f"data/survey/{name}")
    with resource.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _split(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.split(";") if part)


_MEDICAL_IDS = frozenset(item.metric_id for item in MEDICAL_CATALOG)


def _partition_metric_ids(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    identifiers = _split(value)
    medical = tuple(metric_id for metric_id in identifiers if metric_id in _MEDICAL_IDS)
    analysis = tuple(metric_id for metric_id in identifiers if metric_id not in _MEDICAL_IDS)
    return medical, analysis


def _load_references() -> tuple[SurveyReference, ...]:
    return tuple(
        SurveyReference(
            reference_id=row["reference_id"],
            citation=row["citation"],
            year=int(row["year"]),
            evidence_type=row["evidence_type"],
            diseases=_split(row["diseases"]),
            key_finding_ko=row["key_finding_ko"],
            url=row["url"],
            doi=row["doi"],
        )
        for row in _resource_rows("survey_references.tsv")
    )


def _load_uses() -> tuple[DiseaseMetricUse, ...]:
    records = []
    for row in _resource_rows("disease_metric_uses.tsv"):
        medical_ids, analysis_ids = _partition_metric_ids(row["metric_ids"])
        records.append(DiseaseMetricUse(
            use_id=row["use_id"],
            disease_id=row["disease_id"],
            disease_name_ko=row["disease_name_ko"],
            disease_name_en=row["disease_name_en"],
            medical_metric_ids=medical_ids,
            analysis_measure_ids=analysis_ids,
            clinical_role=row["clinical_role"],
            evidence_tier=row["evidence_tier"],
            package_readiness=row["package_readiness"],
            summary_ko=row["summary_ko"],
            limitations_ko=row["limitations_ko"],
            reference_ids=_split(row["reference_ids"]),
        ))
    return tuple(records)


def _load_combinations() -> tuple[MetricCombination, ...]:
    records = []
    for row in _resource_rows("metric_combinations.tsv"):
        medical_ids, analysis_ids = _partition_metric_ids(row["metric_ids"])
        records.append(MetricCombination(
            combination_id=row["combination_id"],
            disease_id=row["disease_id"],
            combination_name_ko=row["combination_name_ko"],
            medical_metric_ids=medical_ids,
            analysis_measure_ids=analysis_ids,
            external_components=_split(row["external_components"]),
            intended_use_ko=row["intended_use_ko"],
            evidence_tier=row["evidence_tier"],
            package_readiness=row["package_readiness"],
            decision_rule_ko=row["decision_rule_ko"],
            limitations_ko=row["limitations_ko"],
            reference_ids=_split(row["reference_ids"]),
        ))
    return tuple(records)


REFERENCES = _load_references()
DISEASE_USES = _load_uses()
COMBINATIONS = _load_combinations()


def _duplicates(values: Iterable[str]) -> set[str]:
    values = tuple(values)
    return {value for value in values if values.count(value) > 1}


def _validate_survey() -> None:
    metric_ids = {item.metric_id for item in ALL_REGISTERED_MEASURES}
    reference_ids = {item.reference_id for item in REFERENCES}
    for label, identifiers in (
        ("reference", [item.reference_id for item in REFERENCES]),
        ("disease use", [item.use_id for item in DISEASE_USES]),
        ("combination", [item.combination_id for item in COMBINATIONS]),
    ):
        duplicates = sorted(_duplicates(identifiers))
        if duplicates:
            raise ValueError(f"Duplicate {label} IDs: {duplicates}")
    for item in DISEASE_USES:
        if item.clinical_role not in VALID_ROLES:
            raise ValueError(f"Invalid clinical role in {item.use_id}: {item.clinical_role}")
        if item.package_readiness not in VALID_READINESS:
            raise ValueError(f"Invalid readiness in {item.use_id}: {item.package_readiness}")
        if item.evidence_tier not in VALID_EVIDENCE:
            raise ValueError(f"Invalid evidence tier in {item.use_id}: {item.evidence_tier}")
        unknown_metrics = set(item.metric_ids) - metric_ids
        unknown_references = set(item.reference_ids) - reference_ids
        if unknown_metrics or unknown_references:
            raise ValueError(
                f"Broken survey links in {item.use_id}: metrics={sorted(unknown_metrics)}, "
                f"references={sorted(unknown_references)}"
            )
    for item in COMBINATIONS:
        if len(item.metric_ids) < 2:
            raise ValueError(f"Combination {item.combination_id} needs at least two metrics")
        if item.package_readiness not in VALID_READINESS or item.evidence_tier not in VALID_EVIDENCE:
            raise ValueError(f"Invalid combination metadata in {item.combination_id}")
        unknown_metrics = set(item.metric_ids) - metric_ids
        unknown_references = set(item.reference_ids) - reference_ids
        if unknown_metrics or unknown_references:
            raise ValueError(
                f"Broken combination links in {item.combination_id}: "
                f"metrics={sorted(unknown_metrics)}, references={sorted(unknown_references)}"
            )


_validate_survey()


def survey_references() -> tuple[SurveyReference, ...]:
    return REFERENCES


def diseases() -> tuple[tuple[str, str, str], ...]:
    """Return stable disease IDs and bilingual display names."""
    rows = {
        (item.disease_id, item.disease_name_ko, item.disease_name_en)
        for item in DISEASE_USES
    }
    return tuple(sorted(rows))


def disease_uses(
    *, disease_id: str | None = None, clinical_role: str | None = None,
    readiness: str | None = None,
) -> tuple[DiseaseMetricUse, ...]:
    if clinical_role is not None and clinical_role not in VALID_ROLES:
        raise ValueError(f"clinical_role must be one of {sorted(VALID_ROLES)}")
    if readiness is not None and readiness not in VALID_READINESS:
        raise ValueError(f"readiness must be one of {sorted(VALID_READINESS)}")
    return tuple(
        item for item in DISEASE_USES
        if (disease_id is None or item.disease_id == disease_id)
        and (clinical_role is None or item.clinical_role == clinical_role)
        and (readiness is None or item.package_readiness == readiness)
    )


def metric_uses(metric_id: str) -> tuple[DiseaseMetricUse, ...]:
    get_measure(metric_id)
    return tuple(item for item in DISEASE_USES if metric_id in item.metric_ids)


def recommend_combinations(
    disease_id: str, *, readiness: str | None = None,
) -> tuple[MetricCombination, ...]:
    if readiness is not None and readiness not in VALID_READINESS:
        raise ValueError(f"readiness must be one of {sorted(VALID_READINESS)}")
    return tuple(
        item for item in COMBINATIONS
        if item.disease_id == disease_id
        and (readiness is None or item.package_readiness == readiness)
    )


def _fallback_scope(domain: str) -> tuple[str, str]:
    if domain in {"model_evaluation", "survival", "inference", "descriptive", "reproducibility"}:
        return (
            "disease_agnostic_method",
            "질병을 직접 진단하는 생물학적 지표가 아니라 어떤 질병 모델에도 적용 가능한 평가·통계·QC 방법이다.",
        )
    if domain == "candidate_generation":
        return (
            "project_specific_triage",
            "현재 고정 구현은 PRECISE 전립선암 PNI 후보 triage에만 해당하며 타 질병 전이는 재검증이 필요하다.",
        )
    if domain == "pni_audit":
        return (
            "selected_sample_evaluation",
            "선택된 전립선 PNI audit 표본의 ranking 평가이며 질병 진단 지표가 아니다.",
        )
    if domain in {"morphology", "contour"}:
        return (
            "cross_cancer_pni_feature",
            "여러 암종의 PNI 기술에 개념적으로 관련되지만 암종별 contour·판독 검증이 필요하다.",
        )
    if domain == "spatial_pilot":
        return (
            "project_exploratory_feature",
            "전립선 PNI serial-section pilot의 탐색 특징이며 진단용 assay로 보정되지 않았다.",
        )
    return (
        "nonspecific_morphology_feature",
        "여러 질병에서 사용할 수 있는 비특이적 형태 특징으로 질병별 학습·검증 또는 IHC panel이 필요하다.",
    )


def metric_disease_scope(metric_id: str) -> MetricDiseaseScope:
    """Explain disease applicability for a medical metric or analysis measure."""
    metric = get_measure(metric_id)
    uses = metric_uses(metric_id)
    if uses:
        disease_ids = tuple(sorted({item.disease_id for item in uses}))
        roles = tuple(sorted({item.clinical_role for item in uses}))
        diagnostic_adjuvant = "diagnostic_adjuvant" in roles
        applicability = "literature_mapped"
        summary = " ".join(dict.fromkeys(item.summary_ko for item in uses))
    else:
        disease_ids = ()
        diagnostic_adjuvant = False
        tier = getattr(metric, "tier", "")
        if tier == "T1":
            roles = ("histopathology_annotation",) if metric.domain == "pathology" else ("research_feature",)
            applicability = "clinician_native_anchor"
            summary = "임상의·병리전문의·검사실이 직접 기록하는 의료 기준축이며 AI 성능지표가 아니다."
        elif tier == "T2":
            roles = ("research_feature",)
            applicability = "clinician_anchored_derived"
            summary = "Tier 1 의료 기준축 또는 전문의 annotation에서 고정 계산한 파생계측이다."
        elif tier == "T3":
            roles = ("research_feature",)
            applicability = "research_computational_feature"
            summary = "의료영상에서 계산하지만 일상 임상지표로 검증되지 않은 연구 특징이다."
        elif tier == "T4":
            roles = ("candidate_triage",) if metric.clinical_use == "triage_only" else ("research_feature",)
            applicability = "model_derived_data"
            summary = "상위 의료 기준축과 연결해 검증해야 하는 모델 파생값이며 임상 측정치가 아니다."
        else:
            roles = ("evaluation_only",) if metric.domain in {
                "model_evaluation", "survival", "inference", "descriptive", "reproducibility"
            } else ("research_feature",)
            applicability, summary = _fallback_scope(metric.domain)
    return MetricDiseaseScope(
        metric_id=metric.metric_id,
        metric_name_ko=metric.name_ko,
        domain=metric.domain,
        applicability_class=applicability,
        disease_ids=disease_ids,
        clinical_roles=roles,
        diagnostic_adjuvant_mapping=diagnostic_adjuvant,
        standalone_diagnostic_use=False,
        summary_ko=summary,
    )


def all_metric_disease_scopes() -> tuple[MetricDiseaseScope, ...]:
    scopes = tuple(metric_disease_scope(item.metric_id) for item in ALL_REGISTERED_MEASURES)
    if len(scopes) != len(ALL_REGISTERED_MEASURES):
        raise AssertionError("Every registered metric must receive exactly one scope row")
    return scopes


def export_survey(directory: str | Path) -> tuple[Path, ...]:
    """Export normalized CSVs for uses, combinations, references, and all metric scopes."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    datasets = {
        "disease_metric_uses.csv": DISEASE_USES,
        "metric_combinations.csv": COMBINATIONS,
        "survey_references.csv": REFERENCES,
        "all_metric_disease_scopes.csv": all_metric_disease_scopes(),
    }
    outputs = []
    for name, records in datasets.items():
        path = root / name
        rows = []
        for record in records:
            row = asdict(record)
            for key, value in row.items():
                if isinstance(value, tuple):
                    row[key] = ";".join(str(part) for part in value)
            rows.append(row)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        outputs.append(path)
    return tuple(outputs)
