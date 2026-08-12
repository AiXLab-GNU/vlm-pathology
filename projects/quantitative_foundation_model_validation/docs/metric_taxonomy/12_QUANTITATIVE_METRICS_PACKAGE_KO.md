# 정량 지표 카탈로그와 패키지

## 결론

기존 113개 레지스트리는 의료 측정치, 모델 출력, 성능평가, 통계와 QC가 섞인
`legacy measure registry`였다. 이를 의료 정량지표라고 통칭하지 않는다. 새 기본
카탈로그는 임상의가 직접 기록하는 기준값과 그 명시적 파생값만 Tier 1–4로 분류한다.

- 의료 정량지표: `infrastructure/packages/vlm_pathology_metrics/src/vlm_pathology_metrics/data/medical/tier*.tsv`
- 분석량: `infrastructure/packages/vlm_pathology_metrics/src/vlm_pathology_metrics/data/analysis/analysis_measure_catalog.tsv`
- 레거시 113개 계산량: `infrastructure/packages/vlm_pathology_metrics/src/vlm_pathology_metrics/data/legacy/metric_catalog_113.tsv`
- 분류 설계: `docs/17_MEDICAL_QUANTITATIVE_METRIC_TIER_TAXONOMY_KO.md`

기본 `catalog()`에는 AUROC, R², bootstrap, permutation, FDR와 hash가 들어가지 않는다.
이들은 별도 `analysis_catalog()`에서 관리한다.

## 의료 Tier별 목록

| Tier | 지표 수 | 정의 |
|---|---:|---|
| T1 | 16 | 임상의·병리전문의·검사실·영상의가 직접 기록하는 의료 기준축 |
| T2 | 12 | T1 또는 전문의 annotation/contour에서 고정 계산한 파생계측 |
| T3 | 20 | 의료영상에서 계산한 연구용 image/spatial proxy |
| T4 | 10 | T1–T3와 연결해 검증해야 하는 model score/rank/representation |

의료 tier 밖의 analysis registry는 73개이며 모델평가, 통계, QC와 재현성 계산량을
포함한다.

## 상태별 해석

- `active`: 정의된 프로젝트 역할에서 사용 가능하며 임상 검증을 뜻하지 않는다.
- `exploratory`: 연구용 계산은 가능하지만 확증적·임상적 해석을 금지한다.
- `deferred`: 필요한 source, annotation 또는 승인 gate 전에는 계산·해석하지 않는다.
- `audit`: 의료 tier가 아니라 별도 analysis registry의 QC·재현성 상태다.

## 핵심 과학적 제한

PNI candidate score는 병리 진단확률이 아니라 공간적으로 구별된 검토 후보의 순위
점수다. Capture fraction은 선택된 120건에서 확인된 양성 focus의 집중도이며
whole-slide sensitivity가 아니다. Top-k precision은 해당 budget의 모든 후보가
평가 가능할 때만 정의한다. 미판독·빈칸·`uncertain`·`not_evaluable`은 음성으로
변환하지 않는다.

형태 재판독 비율은 선택된 14개 nerve-positive focus만 기술한다. PRECISE 환자의
PNI 형태 분포를 추정하지 않는다. 생존 지표는 endpoint 이름, censoring 규칙,
분석대상 수와 사건 수를 항상 함께 보고해야 한다. Sampling-seed Student-t 구간은
환자 수준 불확실성이나 독립 validation 횟수가 아니다.

## 패키지 사용

패키지 소스는 `infrastructure/packages/vlm_pathology_metrics/`에 있다. 설치 후 CLI로 전체 목록을
CSV 또는 Markdown으로 내보낼 수 있다.

```bash
.venv/bin/python -m pip install -e packages/vlm_pathology_metrics
vlm-pathology-metrics summary
vlm-pathology-metrics list --domain pni_audit
vlm-pathology-metrics export --format csv --output /tmp/vlm_pathology_metrics.csv
```

공통 API에는 고정 PRECISE 결합점수, capture/coverage/조건부 precision, exact
binomial CI, AUROC/AP의 single-class failure 보존, Spearman, raw agreement/kappa,
Dice, paired difference/log2 ratio, percentile bootstrap accounting, seed t interval,
BH-FDR가 포함된다. Endpoint 구성과 censoring에 종속되는 생존 계산 및 기존 frozen
audit 전체 pipeline은 중앙화하지 않았다. 해당 값의 계산 기준은 기존 검증된
entry point와 저장된 source table이다.

## 질병별 서베이와 조합 선택

같은 패키지 폴더의 `SURVEY_KO.md`에 광범위 문헌 서베이, 질병별 사용 역할과 제한,
20개 조합 레시피를 정리했다. 정규화된 단일 원천은 다음 세 TSV다.

- `disease_metric_uses.tsv`: 18개 질병·용도에 대한 19개 지표군 매핑
- `metric_combinations.tsv`: 외부 assay와 validation 요건을 포함한 20개 조합
- `survey_references.tsv`: PubMed 문헌 20건과 승인된 내부 설계 3건

Tiered 의료 지표와 별도 analysis measure 모두는 `all_metric_disease_scopes()`로 한 행씩
내보낼 수 있다. 질병과 직접 연결되지 않은 평가·통계·QC 값도 재현성 추적을 위해
`disease_agnostic_method`로 보존하지만 의료 정량지표 수에는 포함하지 않는다.

```bash
vlm-pathology-metrics diseases
vlm-pathology-metrics uses --disease prostate_pni
vlm-pathology-metrics recommend --disease prostate_pni
vlm-pathology-metrics metric-scope evaluation.roc_auc
vlm-pathology-metrics export-survey --directory /tmp/metric-survey
```

현재 `standalone_diagnostic_use=True`로 분류된 지표는 없다. 실제 AMACR/HMWCK 기반
항목도 package의 영상 proxy가 아니라 외부 임상 IHC와 H&E 전문의 형태 판독을 함께
요구하는 진단 보조 mapping이다. PNI 관련 항목은 후보 triage, 형태 annotation 또는
예후 특징이지 암 자체의 진단 지표가 아니다.
