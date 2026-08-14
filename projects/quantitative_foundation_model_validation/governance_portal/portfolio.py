"""Repository-portfolio data and append-only review surveys for the portal."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PORTAL_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PORTAL_ROOT.parents[2]
DEFAULT_REVIEW_ROOT = REPOSITORY_ROOT / "resources" / "artifacts"

PROJECTS: dict[str, dict[str, Any]] = {
    "precise_pni_candidate_triage": {
        "slug": "pni",
        "code": "PNI · CANDIDATE TRIAGE",
        "name": "PRECISE PNI Candidate Triage",
        "korean_name": "PNI 후보 영역 선별 및 병리 검토",
        "goal": (
            "동결된 점수로 공간적으로 구분된 PNI 후보 영역을 우선순위화하고, "
            "병리 전문의가 재현 가능하게 검토·승인할 수 있는 근거 흐름을 만든다."
        ),
        "plan": [
            "후보 생성과 frozen-score audit로 검토 대상을 고정한다.",
            "blinded morphology rereview와 contour review로 사람의 판단을 기록한다.",
            "승인된 contour에 한해서만 공간 정량화와 제한된 연구 보고로 진행한다.",
        ],
        "boundary": "후보 triage 연구이며 whole-slide PNI 진단 또는 임상 검증이 아니다.",
        "sequence": "projects/precise_pni_candidate_triage/00-project-sequence/README.md",
        "plan_document": "projects/precise_pni_candidate_triage/docs/project_plan/01-precise-pni-project-plan-ko.md",
        "milestone_document": "projects/precise_pni_candidate_triage/docs/project_plan/01-02-pni-project-milestones-ko.md",
        "review_focus": "후보의 형태학적 타당성, contour 품질, 실제 검토 흐름의 사용성",
    },
    "quantitative_foundation_model_validation": {
        "slug": "quantitative",
        "code": "QFM · H1 / H2 VALIDATION",
        "name": "Quantitative Foundation-Model Validation",
        "korean_name": "의료 정량지표 표현 복원성과 기능 검증",
        "goal": (
            "의료 정량지표가 foundation-model 표현에서 복원되는지(H1), 그리고 독립 "
            "질병 endpoint 예측에 기능적으로 사용되는지(H2)를 단계적으로 분리해 검증한다."
        ),
        "plan": [
            "T1–T4 의료지표 체계와 분석량 레지스트리를 분리해 기준축을 고정한다.",
            "paired manifest와 embedding을 통해 encoder 간 비교 기반을 재현한다.",
            "concept benchmark를 승인된 descriptive 범위에서 수행한 뒤 H2 gate를 별도로 연다.",
        ],
        "boundary": "정량 개념의 복원 가능성은 질병 예측 또는 임상적 활용을 뜻하지 않는다.",
        "sequence": "projects/quantitative_foundation_model_validation/00-project-sequence/README.md",
        "plan_document": "projects/quantitative_foundation_model_validation/docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md",
        "milestone_document": "projects/quantitative_foundation_model_validation/docs/research_plan/01-01-foundation-model-validation-milestones-ko.md",
        "review_focus": "지표 적격성, paired evidence, descriptive scope와 H1/H2 claim 분리",
    },
    "prostate_biomarker_validation": {
        "slug": "biomarker",
        "code": "PBV · BIOMARKER QUALIFICATION",
        "name": "Prostate Biomarker Validation",
        "korean_name": "전립선 분자표지자·재발·생존 근거 검증",
        "goal": (
            "전립선 병리 foundation-model 표현에서 분자표지자와 임상 endpoint의 근거를 "
            "외부검증·교란·안정성 분석과 함께 평가하고 주장과 근거를 추적 가능하게 연결한다."
        ),
        "plan": [
            "endpoint와 분석 family를 동결하고 cohort별 분석을 재현한다.",
            "site, confounder, stability, external-validation 축에서 신호의 한계를 감사한다.",
            "claim–evidence matrix를 통해 검증된 범위만 원고와 제출 패키지로 승격한다.",
        ],
        "boundary": "연구용 biomarker qualification이며 임상 성능 확정이나 진단기 허가 근거가 아니다.",
        "sequence": "projects/prostate_biomarker_validation/00-project-sequence/README.md",
        "plan_document": "projects/prostate_biomarker_validation/docs/research_plan/01-prostate-biomarker-validation-plan.md",
        "milestone_document": "projects/prostate_biomarker_validation/docs/research_plan/01-01-prostate-biomarker-validation-milestones.md",
        "review_focus": "endpoint 적합성, 외부 타당성, 교란·안정성, 논문 claim–evidence 정합성",
    },
}

ARTIFACTS: dict[str, dict[str, str]] = {
    "medical-metric-atlas": {
        "owner": "shared_infrastructure",
        "title": "Medical Metric Atlas",
        "label": "정량지표 계층·계보 맵",
        "description": "임상 기준지표 T1부터 모델 산출량 T4까지의 parent–child 계보와 별도 분석량 레지스트리.",
        "kind": "interactive",
        "route": "/assets/metric-atlas/index.html",
        "path": "infrastructure/packages/vlm_pathology_metrics/web/index.html",
    },
    "pbv-reliability-map": {
        "owner": "prostate_biomarker_validation",
        "title": "Reliability map",
        "label": "분석 신뢰도 맵",
        "description": "전립선 biomarker 분석 축의 신뢰도와 근거 상태를 요약한 논문 그림.",
        "kind": "image",
        "route": "/api/artifact/pbv-reliability-map",
        "path": "projects/prostate_biomarker_validation/paper/figures/fig1_reliability_map.png",
    },
    "pbv-external-validation": {
        "owner": "prostate_biomarker_validation",
        "title": "Marker 1 external validation",
        "label": "외부검증 결과",
        "description": "Marker 1의 내부·외부 cohort 성능을 비교한 저장된 source-derived figure.",
        "kind": "image",
        "route": "/api/artifact/pbv-external-validation",
        "path": "projects/prostate_biomarker_validation/paper/figures/fig2_marker1_external.png",
    },
    "pbv-encoder-comparison": {
        "owner": "prostate_biomarker_validation",
        "title": "CONCH vs Virchow",
        "label": "Encoder 비교",
        "description": "동일 분석 조건에서 두 foundation-model 표현의 결과를 비교한 논문 그림.",
        "kind": "image",
        "route": "/api/artifact/pbv-encoder-comparison",
        "path": "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.png",
    },
    "pbv-scale-tile-heatmap": {
        "owner": "prostate_biomarker_validation",
        "title": "Scale × tile heatmap",
        "label": "스케일·타일 안정성 맵",
        "description": "스케일과 tile 조건에 따른 정량 결과의 안정성을 보여 주는 heatmap.",
        "kind": "image",
        "route": "/api/artifact/pbv-scale-tile-heatmap",
        "path": "projects/prostate_biomarker_validation/paper/figures/fig9_scale_tile_heatmap.png",
    },
}

SURVEY_CONFIG = {
    "admin": {
        "decisions": {"ready", "revise", "hold"},
        "attestations": {
            "scope_confirmed",
            "evidence_traceable",
            "governance_complete",
            "data_integrity_confirmed",
        },
    },
    "clinician": {
        "decisions": {"clinically_acceptable", "revise", "not_evaluable"},
        "attestations": {
            "claim_boundary_clear",
            "visual_quality_adequate",
            "workflow_fit_reviewed",
        },
    },
}

_WRITE_LOCK = threading.Lock()
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


class PortfolioError(ValueError):
    """Raised when portfolio or survey data fail validation."""


def _plain_markdown(value: str) -> str:
    value = _MARKDOWN_LINK.sub(r"\1", value)
    return value.replace("`", "").replace("**", "").strip()


def _status_key(status: str) -> str:
    if "잠금" in status:
        return "locked"
    if "현재" in status or "대기" in status or "진행" in status or "부분" in status:
        return "active"
    if "완료" in status:
        return "complete"
    return "standing"


def sequence_rows(relative_path: str) -> list[dict[str, str]]:
    """Read the canonical project sequence table without following output links."""
    source = REPOSITORY_ROOT / relative_path
    rows: list[dict[str, str]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [_plain_markdown(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        status = cells[2]
        rows.append(
            {
                "order": cells[0],
                "stage": cells[1],
                "status": status,
                "status_key": _status_key(status),
                "entry_criterion": cells[4],
            }
        )
    if not rows:
        raise PortfolioError(f"프로젝트 순서표를 읽을 수 없습니다: {relative_path}")
    return rows


def _project_payload(project_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    rows = sequence_rows(spec["sequence"])
    measured = [row for row in rows if row["order"] != "00"]
    complete = sum(row["status_key"] == "complete" for row in measured)
    active = [row for row in rows if row["status_key"] == "active"]
    payload = {key: value for key, value in spec.items()}
    payload.update(
        {
            "id": project_id,
            "href": f"/{spec['slug']}.html",
            "milestones": rows,
            "completed_stages": complete,
            "total_stages": len(measured),
            "progress_percent": round(complete / len(measured) * 100) if measured else 0,
            "current_gate": active[0] if active else rows[-1],
        }
    )
    return payload


def _review_file(review_root: Path, project_id: str, survey_type: str) -> Path:
    return review_root / project_id / "portal_reviews" / f"{survey_type}_survey.jsonl"


def review_summary(review_root: Path = DEFAULT_REVIEW_ROOT) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for project_id in PROJECTS:
        project_summary: dict[str, int] = {}
        for survey_type in SURVEY_CONFIG:
            path = _review_file(review_root, project_id, survey_type)
            count = 0
            if path.is_file():
                with path.open(encoding="utf-8") as stream:
                    count = sum(1 for line in stream if line.strip())
            project_summary[survey_type] = count
        summary[project_id] = project_summary
    return summary


def portfolio_data(review_root: Path = DEFAULT_REVIEW_ROOT) -> dict[str, Any]:
    projects = [_project_payload(project_id, spec) for project_id, spec in PROJECTS.items()]
    artifacts = []
    for artifact_id, artifact in ARTIFACTS.items():
        path = REPOSITORY_ROOT / artifact["path"]
        artifacts.append(
            {
                "id": artifact_id,
                **{key: value for key, value in artifact.items() if key != "path"},
                "available": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "portfolio": {
            "title": "VLM Pathology Research Portfolio",
            "goal": (
                "서로 다른 병리-VLM 과학 질문을 독립적으로 검증하면서, 의료 기준축에서 "
                "모델 산출물·사람 검토·주장 근거까지의 흐름을 재현 가능하게 연결한다."
            ),
            "principles": [
                "질문·endpoint·승인·claim은 프로젝트별로 분리한다.",
                "정량지표와 모델 성능평가량을 구분하고 단계별 gate를 통과한다.",
                "임상의 검토와 관리자 판정을 append-only evidence로 남긴다.",
                "저장된 source table에서 산출물을 재생성하고 해석 한계를 함께 제시한다.",
            ],
        },
        "projects": projects,
        "artifacts": artifacts,
        "review_summary": review_summary(review_root),
    }


def artifact_path(artifact_id: str) -> Path:
    artifact = ARTIFACTS.get(artifact_id)
    if artifact is None:
        raise PortfolioError("등록되지 않은 산출물입니다.")
    path = (REPOSITORY_ROOT / artifact["path"]).resolve()
    if not path.is_file():
        raise PortfolioError("산출물 파일이 현재 workspace에 없습니다.")
    return path


def _required_text(payload: dict[str, object], key: str, maximum: int) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise PortfolioError(f"{key} 항목이 필요합니다.")
    if len(value) > maximum:
        raise PortfolioError(f"{key} 항목은 {maximum}자 이하여야 합니다.")
    return value


def _latest_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    last = ""
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                last = line
    if not last:
        return None
    try:
        return str(json.loads(last).get("record_sha256") or "") or None
    except json.JSONDecodeError as exc:
        raise PortfolioError("기존 설문 ledger 마지막 행이 손상되었습니다.") from exc


def append_review_survey(
    survey_type: str,
    payload: dict[str, object],
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> dict[str, object]:
    """Validate and append a project-owned, hash-chained review record."""
    config = SURVEY_CONFIG.get(survey_type)
    if config is None:
        raise PortfolioError("지원하지 않는 설문 유형입니다.")
    project_id = _required_text(payload, "project_id", 80)
    if project_id not in PROJECTS:
        raise PortfolioError("등록된 프로젝트를 선택해야 합니다.")
    reviewer_name = _required_text(payload, "reviewer_name", 120)
    reviewer_title = _required_text(payload, "reviewer_title", 120)
    signature = _required_text(payload, "signature", 120)
    if signature != reviewer_name:
        raise PortfolioError("전자서명은 검토자 이름과 정확히 같아야 합니다.")
    decision = _required_text(payload, "decision", 40)
    if decision not in config["decisions"]:
        raise PortfolioError("허용되지 않은 판정입니다.")
    missing = [key for key in config["attestations"] if payload.get(key) is not True]
    if missing:
        raise PortfolioError("필수 확인 항목을 모두 체크해야 합니다.")
    comment = str(payload.get("comment", "")).strip()
    if len(comment) > 4000:
        raise PortfolioError("검토 의견은 4000자 이하여야 합니다.")
    if decision in {"revise", "hold", "not_evaluable"} and not comment:
        raise PortfolioError("수정·보류·평가 불가 판정에는 검토 의견이 필요합니다.")

    confidence: int | None = None
    if survey_type == "clinician":
        try:
            confidence = int(payload.get("confidence", 0))
        except (TypeError, ValueError) as exc:
            raise PortfolioError("임상 확신도는 1–5 정수여야 합니다.") from exc
        if confidence not in range(1, 6):
            raise PortfolioError("임상 확신도는 1–5 정수여야 합니다.")

    path = _review_file(review_root, project_id, survey_type)
    with _WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        previous_hash = _latest_hash(path)
        record: dict[str, object] = {
            "schema_version": "1.0",
            "survey_type": survey_type,
            "project_id": project_id,
            "reviewer_name": reviewer_name,
            "reviewer_title": reviewer_title,
            "decision": decision,
            "attestations": {key: True for key in sorted(config["attestations"])},
            "comment": comment,
            "confidence": confidence,
            "submitted_at_utc": datetime.now(timezone.utc).isoformat(),
            "previous_record_sha256": previous_hash,
        }
        digest_source = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        record["record_sha256"] = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        path.chmod(0o600)
    return record
