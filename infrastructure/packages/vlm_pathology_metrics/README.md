# vlm-pathology-metrics

이 폴더는 설치 가능한 패키지, Tier 1–4 의료 정량지표, 별도 모델평가·통계·QC
레지스트리, 질병별 문헌 서베이와 사용 예제를 함께 담습니다. 기존 113개 목록은
과거 결과 추적용 `legacy measure registry`이며 의료 정량지표 수로 해석하지 않습니다.
전체 서베이 해설은 [SURVEY_KO.md](SURVEY_KO.md), 기계 판독 원본은
`src/vlm_pathology_metrics/data/{medical,analysis,legacy,survey}/`에 있습니다.

기존 frozen 분석을 자동으로 교체하지 않습니다. 특히 PRECISE frozen-score audit의
점수, 좌표, NMS, bootstrap 결과는 원래 entry point가 기준입니다. 생존분석처럼
endpoint 구성과 censoring 규칙에 강하게 의존하는 지표도 기존 검증된 pipeline이
계산 기준이며, 이 패키지에서는 정의와 provenance만 제공합니다.

## 설치 및 사용

```bash
.venv/bin/python -m pip install -e packages/vlm_pathology_metrics
vlm-pathology-metrics list --tier T1
vlm-pathology-metrics analysis-list --domain model_evaluation
vlm-pathology-metrics export --format markdown --output /tmp/metrics.md
vlm-pathology-metrics export-analysis --format csv --output /tmp/analysis-measures.csv
vlm-pathology-metrics diseases
vlm-pathology-metrics uses --disease prostate_pni
vlm-pathology-metrics recommend --disease prostate_pni
vlm-pathology-metrics metric-scope contour.contact_length
vlm-pathology-metrics export-survey --directory /tmp/metric-survey
```

설치하지 않고도 다음처럼 실행할 수 있습니다.

```bash
PYTHONPATH=infrastructure/packages/vlm_pathology_metrics/src \
  .venv/bin/python -m vlm_pathology_metrics summary
```

Python API:

```python
from vlm_pathology_metrics import (
    catalog,
    disease_uses,
    frozen_combined_score,
    recommend_combinations,
    top_k_precision,
)

tier1_metrics = catalog(tier="T1", status="active")
pni_uses = disease_uses(disease_id="prostate_pni")
pni_recipes = recommend_combinations("prostate_pni", readiness="ready_project")
score = frozen_combined_score(0.9, 0.8, 0.7)
precision = top_k_precision(captured=2, budget_count=5, evaluable_count=5)
```

`top_k_precision`은 budget 전체가 evaluable일 때만 값을 반환합니다. 미판독 후보를
음성으로 간주하지 않기 위해 coverage가 불완전하면 `NaN`입니다.

## 질병별 선택 규칙

질병별 항목은 `clinical_role`, `evidence_tier`, `package_readiness`를 함께 반환합니다.
`diagnostic_adjuvant`라고 해도 단독 진단기를 뜻하지 않습니다. 특히 패키지의
AMACR/HMWCK 수치는 연구용 영상 proxy이며 실제 IHC 판독값이 아닙니다. PNI 지표도
대부분 암 진단 자체가 아니라 병리 annotation, 후보 triage 또는 예후 특징입니다.

`ready_project`는 현재 프로젝트에서 허용된 범위가 있다는 뜻이고, 현재는 PRECISE의
선택된 후보 triage뿐입니다. 타 암종 PNI 조합은 문헌상 PNI의 중요성만 뒷받침되며
모델·prompt·좌표·threshold의 전이를 검증한 것이 아닙니다.

질병 use와 조합 API는 `medical_metric_ids`와 `analysis_measure_ids`를 별도로 반환합니다.
기존 `metric_ids` property는 하위호환용 합집합이며 새 보고서의 지표 수 계산에는
사용하지 않습니다.

## 폴더 구성

```text
vlm_pathology_metrics/
├── pyproject.toml
├── README.md
├── SURVEY_KO.md
├── examples/select_metrics.py
├── scripts/build_web_catalog.py       # TSV → 결정론적 웹 데이터
├── web/                               # Tier·parent 계보 그래프를 포함한 정적 웹페이지
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── data/catalog-data.js
└── src/vlm_pathology_metrics/
    ├── catalog.py          # 의료 tier와 별도 analysis measure 검색
    ├── core.py             # 안전장치를 둔 공통 계산
    ├── survey.py           # 질병·조합·근거 선택 API
    └── data/
        ├── medical/                  # Tier 1–4, tier별 독립 TSV
        ├── analysis/                 # 모델평가·통계·QC
        ├── legacy/                   # 원래 113-measure provenance
        └── survey/                   # 질병 use·조합·문헌
```

## Tier와 상태

- `T1 clinician_native`: 의료진·검사실이 직접 기록하는 기준축
- `T2 clinician_anchored_derived`: T1/전문의 annotation 기반 고정 파생계측
- `T3 research_computational`: 아직 일상 임상계측으로 검증되지 않은 영상 proxy
- `T4 model_derived`: T1–T3와 연결해 검증해야 하는 AI score/rank/representation

AUROC, R², C-index, bootstrap, permutation, FDR, missingness와 hash는 의료 tier에
들어가지 않으며 `analysis_catalog()`에서만 조회합니다.

- `active`: 현재 분석 또는 공식 산출물에서 사용
- `audit`: 품질관리·재현성·불확실성 기록에 사용
- `exploratory`: pilot 또는 보조 탐색에서 사용; 확증적 해석 금지
- `deferred`: 승인된 다음 단계 전에는 계산·해석하지 않는 예약 지표

## 웹 카탈로그

웹페이지는 Python API와 같은 tier별 TSV를 읽으며, 의료 지표와 분석량을 화면에서도
분리합니다. 데이터 갱신과 로컬 실행 방법은 [web/README.md](web/README.md)를
참조하세요.
