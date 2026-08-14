# 의료 정량지표 Tier 분류체계

- 버전: 0.3
- 기준일: 2026-08-11
- 목적: 의료 정량지표와 모델평가·통계·QC 산출량을 분리하고, 의료 기준축에서 파생되는 정도를 명시한다.

## 1. 핵심 원칙

기존 `data/legacy/metric_catalog_113.tsv`의 113개 항목은 병리·임상 측정치뿐 아니라 AUROC, R²,
bootstrap, FDR, hash, rank와 모델 score를 함께 담고 있었다. 따라서 113을 모두
`의료 정량지표`라고 부르지 않는다.

새 기본 카탈로그는 다음 질문에 답하는 값만 포함한다.

> 이 값은 환자 의료 데이터의 임상 기준축인가, 아니면 그 기준축·annotation·영상에서
> 명시적으로 파생된 데이터인가?

AUROC, AP, R², C-index, bootstrap CI, permutation p, q-value, confusion matrix,
missingness와 hash reconciliation은 모델과 분석을 평가하는 **analysis measure**이며
의료 정량지표 tier에서 제외한다. 계산 API는 재현성을 위해 유지하지만 별도
`analysis_catalog()`로만 노출한다.

## 2. Tier 정의

| Tier | 이름 | 정의 | 예 |
|---|---|---|---|
| T1 | clinician-native | 임상의·병리전문의·검사실·영상의가 의료 데이터에 직접 기록하는 기준값 | PSA, Gleason pattern/score, ISUP grade group, 암 길이·침범률, 양성 core 수, PNI 존재, 임상 병기, 재발·추적시간 |
| T2 | clinician-anchored derived | T1 값 또는 전문의 annotation/contour에서 사전 고정 공식으로 계산 | PSA density, positive-core fraction, expert-mask tumor fraction, nerve diameter, encasement, contact length |
| T3 | research computational | 의료영상에서 계산되지만 일상 임상 계측으로 검증되지 않은 연구용 proxy | nuclear-density detector output, GLCM texture, lumen segmentation, chromogen proxy |
| T4 | model-derived | T1–T3와 연결해 검증해야 하는 AI score·rank·representation 파생값 | frozen PNI component score, combined score, NMS rank, embedding PCA |

Tier 번호는 증거의 우열이나 성능 순위가 아니다. **의료 기준축으로부터의 파생 거리**다.
각 하위 tier는 하나 이상의 상위 `parent_metric_ids`를 가져야 한다. T1은 parent를
가질 수 없다.

## 3. 의료 정량지표가 아닌 별도 분석량

다음은 중요하지만 의료 정량지표가 아니다.

- 모델 성능: AUROC, AP, MAE, R², Spearman, QWK, calibration
- 생존모델 평가: C-index, time-dependent AUC, IBS
- 통계 추론: bootstrap CI, permutation p, BH-FDR q, power/MDE
- 안정성·감사: seed SD, null crossing, undefined replicate count
- 재현성·QC: missingness, hash reconciliation, embedding norm
- cohort 기술통계: count, mean, median/IQR, min/max

이 값들은 `ANALYSIS_CATALOG`와 `analysis_catalog()`에서 관리한다. 의료 tier의 성능을
평가할 수는 있지만 그 자체가 환자의 병리·임상 상태를 나타내는 기준축은 아니다.

## 4. 현재 분류 결과

`data/medical/tier*.tsv`의 현재 초안은 58개다.

| Tier | 총수 | active | exploratory | deferred |
|---|---:|---:|---:|---:|
| T1 | 16 | 9 | 0 | 7 |
| T2 | 12 | 1 | 3 | 8 |
| T3 | 20 | 0 | 20 | 0 |
| T4 | 10 | 9 | 1 | 0 |

별도 analysis registry는 73개다. 기존 113개 레지스트리는 과거 결과 추적을 위한
`MEASURE_CATALOG`로 보존한다. 새 의료 카탈로그에는 기존 항목 40개와 누락됐던 T1/T2
임상 anchor 18개가 포함된다.

`active`는 현재 정의된 프로젝트 용도가 있다는 뜻이지 임상적으로 검증됐다는 뜻이
아니다. 특히 T4 active는 frozen candidate-triage 구현이 고정돼 있다는 의미일 뿐
진단확률이나 임상 cutoff를 뜻하지 않는다.

## 5. 전립선암 Tier 1 기준축

초기 T1은 현재 프로젝트와 공식 전립선 생검·분류 항목을 우선한다.

- Primary/secondary Gleason pattern, total Gleason score, ISUP grade group
- Percentage Gleason pattern 4
- Cancer-positive core count, total evaluable core count
- Cancer extent in mm or percentage
- Pathologist-reported PNI presence
- Serum PSA, prostate volume, clinical T stage
- Locked biochemical recurrence status and recurrence-free follow-up time

EAU는 전립선 생검 보고에서 primary/secondary Gleason grade, ISUP grade group,
pattern 4 비율, 암 양성 core 수와 암 범위(mm 또는 percentage)를 권고한다. 또한 PSA,
ISUP grade group과 임상 T stage를 위험층화의 주요 기준으로 사용한다.

- EAU classification/staging: https://uroweb.org/guidelines/prostate-cancer/chapter/classification-and-staging-systems
- EAU diagnostic evaluation: https://uroweb.org/guidelines/prostate-cancer/chapter/diagnostic-evaluation
- CAP current cancer protocols: https://www.cap.org/protocols-and-guidelines/cancer-protocols/current-cancer-protocols/

## 6. 본 연구 적용 규칙

1. 기반 모델 concept benchmark의 정답은 원칙적으로 T1 또는 독립성·repeatability를
   통과한 T2에서 선택한다.
2. T3는 exploratory target 또는 설명변수로만 사용하고, detector/segmentation과
   scanner·stain 민감도를 별도 검증한다.
3. T4는 biological truth로 사용할 수 없다. T1/T2와의 관계, 외부 이식성과 residual을
   평가하는 대상이다.
4. Analysis measure는 effect와 uncertainty를 보고하는 도구이지 target 수에 포함하지 않는다.
5. 하나의 값이 여러 역할을 갖는다면 환자별 source 값과 cohort/model 평가 결과를
   서로 다른 metric ID와 table로 분리한다.

## 7. 현재 P0 결과의 재해석

현재 P0에서 완전한 paired OOF/permutation까지 수행한 값은 T2
`candidate.tumor_fraction` 하나다. 이는 `58개 중 1개만 사용 가능`이라는 뜻이 아니다.
T1 9개는 각 원래 source-control/임상 endpoint 역할에서 active이고, 다른 T2/T3는
측정검증과 데이터 연결 상태에 따라 단계적으로 열린다.

다음 FM1의 목적은 각 T1의 실제 cohort availability와 provenance를 확인하고, T2/T3의
parent linkage·repeatability·missingness를 채워 본 연구의 target shortlist를 만드는 것이다.
