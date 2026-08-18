# 정량지표를 통한 기반 모델 검증 마일스톤

- 문서 버전: 0.6
- 기준일: 2026-08-15
- 문서 성격: 상위 연구계획을 work package, evidence gate, 완료 조건으로 분해한 canonical 마일스톤 문서
- 1차 비교 모델: frozen CONCH와 frozen Virchow
- 1차 질병영역: 전립선암 grade, phenotype, 분자표현형, 재발 및 PNI 형태·공간 특성
- 상위 연구계획: `01-quantitative-ai-validation-disease-diagnosis-plan-ko.md`
- 현재 실행 추적표: `01-01-01-foundation-model-validation-execution-tracker-ko.md`
- 관련연구 인덱스: `../surveys/README.md`
- 필수 사전실험: `docs/preexperiment_plan/15_FOUNDATION_MODEL_QUANTITATIVE_VALIDATION_PREEXPERIMENT_PLAN_KO.md`

버전 0.6은 상위 연구계획 버전 0.5의 핵심 목표와 TCGA-PRAD 개발 WSI acquisition·기술
QC·환자 집계 gate를 실행 수준으로 동기화한다. 단일 지표의
복원 가능성을 넘어 복수 지표의 조건부 고유정보·포함관계·joint completeness,
질병예측에서의 기능적 활용, 표현·판단 residual의 구분과 신규 정량 마커 전환을 하나의
증거 사슬로 연결한다. 이는 장기 프로그램의 방향을 명확히 하는 문서 개정이며, 기존 P0와
FM1–FM5 결과, frozen PNI audit의 score·좌표·NMS 및 현재 claim ceiling은 변경하지 않는다.

## 0. 본 연구 진입 전 필수 P0 gate

본 문서의 FM0–FM10은 사전실험 실행계획의 P0-M0–P0-M9 및 P0-G0–P0-G9와
연결된다. 단순히 앞 단계의 작업이 끝났다는 이유가 아니라, 해당 gate의 필수 산출물과
통과 근거가 있어야 다음 단계로 진행한다.

- FM0 protocol 준비와 FM1 지표 catalog 감사는 각각 P0-G0, P0-G1 이후 병렬 진행할 수 있다.
- FM2 manifest 준비는 P0-G2와 P0-G4의 ID·truth·FOV 원칙을 만족하는 범위에서만 허용한다.
- FM3의 smoke test는 P0-G5 이후 가능하지만, 대규모 추출은 P0-G8의 Go 또는
  Conditional Go와 P0-G9의 clean-rerun 인계가 필요하다.
- FM4–FM5는 각각 P0-G6과 P0-G7의 통과 범위로 제한한다.
- FM6의 기능적 활용·상보성 분석은 독립 metric–endpoint 쌍과 충분한 subject/event가
  추가로 필요하며, 강한 H2 판정에는 외부 평가셋이 필요하다.
- FM7–FM9는 P0 통과만으로 자동 개방되지 않는다. 외부 site와 sentinel truth,
  안정적인 residual, blinded review, 독립 assay/outcome 및 독립 cohort가 단계별로 필요하다.
- truth mismatch, subject leakage, hash 위반, paired FOV 실패 또는 순환 target이 해결되지
  않으면 해당 분석축은 중단한다.

세부 태스크, 정량 통과 기준, 실패·수정 경로와 FM0–FM10 unlock matrix는 사전실험
실행계획을 따른다. P0의 `Go`는 방법론적 실행 가능성일 뿐 임상 검증을 뜻하지 않는다.

## 1. 실행계획의 한 문장 목표

동일 환자·동일 조직에서 독립적으로 측정한 복수의 임상·병리 정량지표가 CONCH와
Virchow의 frozen representation과 locked 질병예측 판단을 얼마나 완전하게 설명하는지
규명하고, 알려진 지표와 기술적 교란을 제거한 뒤에도 두 모델과 독립 외부 코호트에서
반복되는 residual morphology를 명시적 정량지표로 전환하여 독립 assay·omics·임상
outcome으로 신규 마커 후보의 타당성을 검증한다.

실행 증거 사슬은 다음 순서를 따른다.

1. **개별 복원성:** 각 사람 지표가 frozen embedding에서 환자분리 방식으로 복원되는가?
2. **포함관계·완전성:** 다른 지표를 조건화한 고유정보와 복수 지표 패널의 joint
   completeness는 어느 정도인가?
3. **기능적 활용:** 지표 관련 표현을 제거할 때 locked disease head가 matched control보다
   선택적으로 저하되는가?
4. **Residual 분리:** 알려진 지표·임상변수·기술적 교란으로 설명되지 않는 표현 residual과
   판단 residual이 두 모델 및 외부 코호트에서 반복되는가?
5. **신규 지표 전환:** 반복 residual을 blinded 병리 검토와 명시적 계측식으로 바꾸고,
   repeatability·독립 assay·omics·outcome·외부 코호트로 검증할 수 있는가?

CONCH와 Virchow는 순위를 매길 대상이 아니라 서로 다른 학습 원천과 inductive bias에서
같은 신호가 반복되는지 확인하는 두 개의 독립적 측정 도구다. 한 모델에만 나타나는
residual은 곧바로 신규 생물학으로 해석하지 않고 encoder-specific 신호 또는 shortcut
가능성을 먼저 감사한다.

## 2. 연구 목적

### 2.1 단계 1 목적: 정량 표현 타당성(H1)

독립적으로 수치화 가능한 병리·분자·임상 표적에 대해 두 기반 모델의 frozen
representation에서 정량지표를 환자분리 OOF 방식으로 복원할 수 있는지 평가하고,
concept recoverability와 외부 이식성을 공정하게 비교한다.

> **H1—Quantitative representation:** 기반모델의 frozen representation에는 모델과
> 독립적으로 측정된 T1 또는 검증된 T2 정량지표를 복원할 수 있는 정보가 존재한다.

H1의 통과는 해당 정량지표가 representation에서 `decodable`하다는 뜻이다. 이것만으로
모델이 그 지표를 질병 판단에 사용하거나, 해당 지표가 질병 예측에 유용하다는 결론을
내리지 않는다.

### 2.2 최종 과학적 outcome 중 하나: 기능적 활용 타당성(H2)

H1을 통과한 정량지표 중 질병 endpoint와 독립적으로 정의된 지표에 대해, 그 지표와
관련된 표현 성분이 frozen embedding 위에 구축한 locked 질병예측기의 예측에 기능적으로
기여하는지 검증한다.

> **H2—Functional utilization:** 기반모델 representation에서 복원되는 정량지표 관련
> 표현 성분을 사전 정의된 방식으로 제거하면, 독립적으로 정의된 질병 endpoint에 대한
> locked 예측기의 성능 또는 환자별 예측이 matched control 제거보다 선택적으로 저하된다.

이 outcome은 다음 네 증거를 순서대로 요구한다.

1. **복원성(R):** \(Z\rightarrow M\)이 grouped-null보다 우수하다.
2. **질병 관련성(A):** cross-fitted \(\hat M\)이 임상·품질 변수 조건부에서도 \(Y\)와 관련된다.
3. **기능적 의존성(U):** \(M\) 관련 표현을 제거하면 locked 질병예측이 matched random
   subspace 제거보다 더 저하된다.
4. **외부 재현성(T):** source에서 고정한 probe, disease head, 제거 규칙과 방향성이 독립
   cohort에서 재학습 없이 유지된다.

`R`만 충족하면 표현 정보의 존재, `R+A`는 질병 관련 정보의 존재, `R+A+U`는 평가된
예측 시스템의 내부 기능적 활용 근거로 분류한다. 본 연구의 강한 H2 outcome은
`R+A+U+T`를 모두 충족한 경우로 제한한다.

### 2.3 “정량지표를 안다”와 “사용한다”의 구분

CONCH와 Virchow는 이 연구에서 frozen encoder이며 자체적으로 고정된 임상 질병
decision head를 제공하지 않는다. 따라서 본 연구에서 “기반모델이 정량지표를 직접
사용한다”는 문구는 다음의 조작적 정의로만 사용한다.

> frozen encoder embedding \(Z\) 위에 사전 고정된 절차로 학습한 질병예측기
> \(h(Z,C)\)가, cross-fitted 정량지표 \(M\) 관련 표현 성분에 선택적으로 의존한다.

이는 encoder가 인간과 같은 방식으로 지표를 인식하거나 인과적으로 추론한다는 뜻이
아니다. 단순 feature importance, attention, \(M\)–\(Y\) 상관 또는 `C+M+AI` 성능 향상만으로
H2를 통과시키지 않는다. H2에는 표적화된 표현 제거, matched negative control과 외부
재현이 필요하다.

### 2.4 2차 목적

1. 두 모델이 같은 정량지표를 같은 방향으로 표현하는지 평가한다.
2. 각 지표의 개별 복원성뿐 아니라 다른 지표 조건부 고유정보와 metric-family 포함관계를
   평가한다.
3. 복수 기존 지표 패널이 각 모델의 표현과 locked disease score를 얼마나 완전하게
   설명하는지 OOF와 외부 표본에서 평가한다.
4. 기존 지표와 AI 표현이 질병 endpoint에 중복 또는 상보적 정보를 주는지 검증한다.
5. 정량지표 관련 표현의 기능적 의존성이 모델·endpoint·site에 따라 달라지는지 평가한다.
6. stain, scanner, scale, tile sampling, grade, 치료와 site가 모델 간 차이 또는 residual을
   설명하는지 감사한다.
7. 표현 residual과 판단 residual을 분리하고, 두 모델·외부 코호트에서 반복되는 형태를
   신규 정량지표 후보로 전환한다.
8. 외부 코호트에서 semantic concordance, 기능적 의존성과 residual shift가 실제 성능
   저하를 예측하는지 평가한다.

### 2.5 비목적

- 두 encoder의 보편적 우열을 선언하지 않는다.
- 반복 seed와 scale 설정을 독립 validation cohort로 취급하지 않는다.
- PRECISE 14 focus로 whole-slide PNI 진단 정확도나 형태 분포를 추정하지 않는다.
- 높은 AI–지표 상관만으로 진단 정확성 또는 신규 바이오마커를 확정하지 않는다.
- 정량지표로 정의되거나 정량지표를 포함해 생성된 label을 H2 질병 endpoint로 사용하지 않는다.
- 선형 subspace 제거 한 번만으로 encoder 내부의 인과적 추론 기전을 확정하지 않는다.
- 현재 frozen-score audit의 점수, prompt, exemplar, weight, 좌표와 NMS를 최적화하지 않는다.

## 3. 연구 모델과 비교의 공정성

### 3.1 모델

| 모델 | 입력/표현 | 현재 역할 |
|---|---|---|
| CONCH | ViT-B/16, 512차원, 기존 448×448 tile | frozen pathology vision-language encoder |
| Virchow | ViT-H/14, 2,560차원, 기존 224×224 tile | frozen pathology foundation encoder |

두 모델의 embedding 차원이 다르므로 component-wise correlation을 사용하지 않는다.
동일 정량 표적을 예측하는 동일 구조의 probe, CKA, regularized CCA 또는 pairwise
representational similarity를 사용한다.

### 3.2 비교 원칙

- 동일 환자 membership과 동일 label provenance
- 동일 tissue ROI와 가능한 경우 정확히 같은 중심 좌표
- pixel 크기가 아니라 동일한 micrometre 단위 field of view
- native scale과 shared scale의 분리 보고
- 동일 tile budget, sampling draw와 patient split
- 동일 probe family와 hyperparameter search budget
- 모델 가중치 동결; source probe만 학습 가능
- target cohort에서 probe, threshold 또는 calibration 재학습 금지
- 모델 차이는 paired patient bootstrap과 동일 draw contrast로 평가

## 4. 정량지표 적격성 체계

### 4.1 필수 역할 분류

기존 113개 계산량을 모두 의료 정량지표로 간주하지 않는다. 먼저
`docs/metric_taxonomy/01-02-medical-quantitative-metric-tier-taxonomy-ko.md`에 따라 T1–T4 의료·파생
지표와 별도 모델평가·통계·QC analysis measure로 분리한다. 의료 tier 각각에는 다음
필드를 추가하거나 연구 manifest에서 관리한다.

| 필드 | 허용값 예 | 목적 |
|---|---|---|
| `metric_role` | biological_feature, ai_output, clinical_outcome, performance_metric, quality_control, derived_comparison | 누출·순환 방지 |
| `analysis_unit` | tile, focus, slide, session, subject, site, cohort | 독립 단위 명시 |
| `reference_source` | pathologist, assay, clinical record, algorithm, model | ground truth provenance |
| `independence_from_model` | independent, partly_shared, model_derived | 일치도 해석 |
| `measurement_status` | ready, exploratory, deferred | 실행 가능 여부 |
| `allowed_role` | input, target, stratifier, QC, endpoint | 분석 위치 |
| `external_validation` | none, internal, cross-site, independent cohort | 증거 수준 |
| `endpoint_independence` | independent, partly_defining, circular, unknown | 정량지표와 질병 label의 순환성 차단 |
| `utilization_eligibility` | eligible, exploratory_only, prohibited | H2 기능적 활용 실험 진입 여부 |

H2에 진입하려면 \(M\)과 \(Y\)의 provenance를 별도로 감사한다. 질병 label이 \(M\)의
threshold, 합산점수 또는 직접 파생식으로 정의됐거나, 판독자가 \(M\)을 보고 \(Y\)를
결정해 독립성을 분리할 수 없다면 `circular` 또는 `partly_defining`으로 기록한다.
`circular` 조합은 H2에서 제외하고, `partly_defining` 조합은 face-validity 또는
sensitivity analysis로만 보고한다.

### 4.2 1차 포함 지표

최종 프로그램에서는 최소 세 개의 사전 정의 metric family를 포함한다. 우선 family는
`gland architecture`, `nuclear morphology`, `tumor microenvironment/spatial context`이며,
독립 molecular·clinical 결과는 biological anchor 또는 endpoint로 별도 관리한다. 현재
실행된 `tumor_fraction` 단일 T2 분석은 이 다중 지표 패널의 완료가 아니라 H1
proof-of-concept다. 추가 family는 독립성·측정 반복성·표본 적격성 gate를 통과한 뒤에만
개방한다.

- 실제 Gleason/ISUP와 benign/tumor phenotype
- PTEN, ERG, SPOP 및 AR의 독립 assay/분자 결과
- 전문가 또는 승인 알고리즘 기반 gland/lumen 형태
- 핵 밀도·크기·형태·texture
- 종양·기질·면역세포의 밀도와 공간분포
- 승인 후의 nerve area/diameter/aspect ratio
- 승인 후의 encasement fraction/contact length/distance gradient
- 독립 recurrence/follow-up endpoint

### 4.3 제외 또는 별도 분석 지표

- CONCH prototype, text-PNI, nerve와 combined score를 CONCH 독립 기준으로 사용 금지
- AI attention/rank를 biological truth로 사용 금지
- AUROC, AP, QWK, C-index, bootstrap CI를 환자 feature로 사용 금지
- 같은 encoder 또는 같은 segmentation output에서 직접 파생된 지표는 독립 검증축에서 제외
- contour 미승인 지표는 `deferred` 유지
- 미판독·uncertain·not-evaluable은 음성으로 변환 금지

## 5. 연구 대상과 우선순위

| 우선순위 | 코호트/표적 | 분석 단위 | 두 모델 비교의 목적 |
|---:|---|---|---|
| 1 | NADT Gleason·phenotype·ERG | 환자/슬라이드 | source concept recoverability |
| 2 | PANDA ISUP·phenotype | 환자 | locked external transport |
| 3 | TCGA-PRAD PTEN·SPOP·AR·ERG | 환자/슬라이드 | 분자 concept와 site audit |
| 4 | PRECISE Gleason·pixel tissue annotation | session/환자/tile | fine-scale spatial face-validity |
| 5 | LEOPARD–TCGA recurrence | 환자 | endpoint·encoder·scale transfer |
| 6 | PRECISE PNI morphology·contour | 선택 focus | 방법론 pilot와 오류분석 |
| 7 | 신규 외부 PNI/전립선 cohort | 환자/slide/site | 실제 transportability 검증 |

### 5.1 H2 초기 metric–endpoint 후보군

아래는 확정 분석 목록이 아니라 FM1–FM2에서 availability, 독립성, 표본·사건 수를
감사할 우선 후보군이다. 결과를 본 뒤 조합을 선택하지 않도록 protocol lock 시점에
`eligible`, `exploratory_only`, `prohibited`를 확정한다.

| 정량지표 \(M\) | 독립 질병 endpoint \(Y\) | 현재 H2 상태 | 선행 요건 |
|---|---|---|---|
| Gleason/ISUP T1 | biochemical recurrence/time-to-recurrence | 우선 후보 | 같은 subject의 histology·outcome 연결, 사건 수·치료 공변량 감사, 외부 recurrence cohort |
| PTEN/ERG/SPOP/AR 독립 assay 결과 | recurrence 또는 assay와 독립인 임상 outcome | 후보·catalog 확장 필요 | assay를 T1 reference로 등록, 동일 환자 pairing, site·purity 감사 |
| 전문가 mask tumor fraction T2 | 독립 molecular phenotype 또는 recurrence | 보류 | PRECISE 외에 같은 환자에서 \(M\)과 독립 \(Y\)를 가진 cohort 필요 |
| 검증된 nuclear/gland/nerve 계측 | 독립 molecular 또는 recurrence endpoint | deferred | T2 measurement/repeatability gate, 같은 환자 endpoint, 외부 반복 |
| tumor fraction | tumor/benign label | **prohibited/circular** | label 정의와 중첩되므로 H1 face-validity로만 사용 |
| PNI 형태·geometry | PRECISE 14-focus 내 PNI status 또는 prognosis | **prohibited in current set** | 선택 표본이 아닌 독립 cohort, 전수/확률표본 truth와 outcome 필요 |

현재 P0의 T2 tumor fraction 결과는 H1 proof-of-concept다. PRECISE에 독립적인 질병
endpoint가 연결되지 않았으므로 그 결과만으로 H2를 수행하거나 통과시킬 수 없다.

## 6. 핵심 분석질문과 평가량

### Q1. 두 모델은 정량 표적을 얼마나 복원하는가?

| 표적 종류 | 주평가 | 보조평가 |
|---|---|---|
| 연속형 | Spearman, cross-validated R², MAE | CCC, Bland–Altman, calibration slope |
| 이진형 | AUROC, AP | sensitivity/specificity, Brier, calibration |
| 순서형 | QWK, Spearman | MAE, grade-boundary confusion |
| 생존형 | C-index | td-AUC, IBS, calibration, comparable pairs |
| 공간형 | Dice/IoU 또는 spatial correlation | point–contour/surface distance |

### Q2. 두 모델의 표현은 서로 얼마나 유사한가?

- 동일 sample의 representational similarity matrix 간 Spearman
- linear CKA와 sensitivity analysis로 regularized CCA
- metric별 probe prediction의 paired correlation 및 residual agreement
- 동일 환자에서 모델 A–B score difference와 clinicopathologic factor의 관계
- concordant high, concordant low, A-only, B-only의 네 discordance stratum

### Q3. 복수 기존 지표가 AI 표현과 판단을 얼마나 완전하게 설명하는가?

AI score \(S_k\), 복수 정량지표 벡터 \(M\), 임상·품질 변수 \(C,Q\)에 대해 모델별로
환자분리 OOF 설명력을 계산한다.

\[
S_k = g_k(M,C,Q) + R^{score}_k, \qquad k\in\{CONCH, Virchow\}
\]

- 지표별 개별 복원성과 partial association
- \(M_j\mid M_{-j},C,Q\)의 조건부 고유정보와 포함관계
- gland, nuclear, microenvironment/spatial 등 지표군별 incremental \(R^2\)
- 전체 지표 패널의 out-of-sample \(R^2\), MAE와 joint completeness
- source-fitted \(g_k\)의 target calibration 및 completeness transport
- \(R^{score}_{CONCH}\), \(R^{score}_{Virchow}\)의 공통성·차이와 기술적 교란

판단 residual \(R^{score}_k\)은 알려진 지표·임상·품질 변수로 설명되지 않은 locked
disease score의 부분이다. 이와 별도로 metric-family subspace를 embedding에서 제거한
표현 residual은 다음과 같이 정의한다.

\[
R^{repr}_k=Z^{-M}_k=(I-P_M)Z_k
\]

두 residual은 용도와 단위가 다르므로 합치지 않는다. \(R^{score}_k\)는 “판단에서 남은
오차·신호”, \(R^{repr}_k\)는 “표현 공간에 남은 정보”를 뜻한다. 어느 residual도 그
자체로 신규 마커가 아니며, Q6과 FM8–FM9의 반복·교란 감사·명시적 계측·독립 검증을
통과해야 한다.

### Q4A. 복원 가능한 정량지표가 질병 예측에 기능적으로 사용되는가?

표기는 frozen embedding을 \(Z\), 독립 정량지표를 \(M\), 질병 endpoint를 \(Y\), 임상·품질
공변량을 \(C,Q\)로 한다. 모든 concept subspace 추정과 disease-head fitting은 outer
training fold 안에서만 수행하고 held-out 환자에는 고정 적용한다.

각 encoder–metric–endpoint 조합에서 다음 네 예측기를 동일 outer split로 평가한다.

- \(h_C(C,Q)\): 임상·품질 기준모델
- \(h_M(C,Q,\hat M)\): cross-fitted 정량지표 복원값을 포함한 concept-only 모델
- \(h_Z(C,Q,Z)\): 전체 frozen embedding을 사용하는 disease predictor
- \(h_{-M}(C,Q,Z^{-M})\): \(M\) 관련 subspace를 제거한 embedding으로 다시 학습한 predictor

training fold에서 추정한 \(M\) 관련 projection을 \(P_M\)이라 할 때 1차 선형 제거는
다음과 같이 정의한다.

\[
Z^{-M}=(I-P_M)Z
\]

\(P_M\)의 1차 정의는 training fold 안에서 \(C,Q\)로 설명되는 부분을 제거한 \(M\)의
잔차를 예측하는 조건부 concept direction으로 한다. 여러 정량지표가 강하게 공선적이어서
metric-specific direction을 안정적으로 식별할 수 없으면 하나의 지표를 골라 주장하지
않고 사전 정의한 `metric-family subspace`의 기능적 활용으로 낮춰 보고한다.

단일 축이 아니라 사전 고정한 rank-\(r\) subspace가 필요한 경우 \(r\)은 결과를 보기
전에 tuning fold에서 정하고, 두 encoder에 동일한 search budget을 적용한다. 비선형
recoverability가 주결과인 경우 선형 제거 결과를 “미사용” 증거로 해석하지 않고 별도
비선형 conditional-randomization 또는 concept-erasure sensitivity를 요구한다.

기능적 활용의 주요 estimand는 다음과 같다.

\[
\Delta_{use}=Perf\{h_Z(Z)\}-Perf\{h_Z(Z^{-M})\}
\]

여기서 두 번째 항은 **같은 locked disease head**에 평가 시점의 \(Z^{-M}\)를 입력한
값이다. 이는 현재 predictor의 해당 subspace 의존성을 측정한다. 표현 제거 후 predictor를
다시 학습한 정보 잔여량은 다음과 같이 별도 보고한다.

\[
\Delta_{info}=Perf\{h_Z(Z)\}-Perf\{h_{-M}(Z^{-M})\}
\]

`fixed-head ablation`과 `refit-after-erasure`는 서로 다른 질문이므로 합치지 않는다.
\(\Delta_{use}>0\)이지만 \(\Delta_{info}\approx0\)이면 현재 head는 \(M\) 관련 방향을
사용하지만 다른 embedding 정보로 대체 가능한 중복 신호로 해석한다.

표적 제거의 특이성은 같은 rank, 분산 제거량과 정규화 조건을 갖춘 matched random
subspace \(P_{R,b}\)를 사용해 평가한다.

\[
\Delta_{specific}=\Delta_{use}-median_b\{\Delta_{random,b}\}
\]

matched random direction, label-permuted concept direction, 다른 metric direction을 각각
negative control로 둔다. gradient/attention attribution은 보조 설명자료일 뿐 H2 통과
근거로 사용하지 않는다.

### Q4B. 기존 지표와 AI가 질병 판단에서 상보적인가?

기능적 활용과 별도로, 동일 split과 동일 환자에서 다음을 비교한다.

- `C`: 임상변수만
- `C+M`: 임상변수+기존 정량지표
- `C+A`: 임상변수+CONCH score/embedding
- `C+B`: 임상변수+Virchow score/embedding
- `C+M+A`
- `C+M+B`
- 탐색적으로 `C+M+A+B`

주요 대비는 `C+M+A` 대 `C+M`, `C+M+B` 대 `C+M` 및 두 증분의 paired difference다.
마지막 결합은 sample size와 사전 power가 충분할 때만 수행한다.

상보성은 AI가 \(M\) 이외의 정보를 추가하는지를 묻고, Q4A는 AI disease predictor가
\(M\) 관련 표현에 의존하는지를 묻는다. `C+M+AI`가 개선돼도 Q4A의 제거 효과가 없으면
“AI가 \(M\)을 사용했다”고 결론 내리지 않는다.

### Q5. 외부 cohort에서 의미 관계가 보존되는가?

코호트별로 다음을 저장한다.

- Technical QC distance \(D_Q\)
- input/embedding shift \(D_E\)
- AI output/uncertainty shift \(D_S\)
- semantic relation shift \(D_M\)
- metric-targeted ablation effect shift \(D_U\)
- 실제 성능 변화 \(\Delta Perf\)

여러 site에서 다음 메타모델의 out-of-site 예측력을 비교한다.

\[
\Delta Perf \sim D_Q + D_E + D_S + D_M + D_U + \text{case-mix terms}
\]

semantic concordance 또는 기능적 활용성은 독립 site에서 \(\Delta Perf\)를 추가로
예측하고 방향이 재현될 때만 향후 acceptance criterion 후보가 된다.

### Q6. 반복 residual을 어떻게 신규 정량 마커 후보로 전환하는가?

1. Source training fold에서 \(R^{repr}_k\), \(R^{score}_k\), 극단 표본의 threshold와
   sampling rule을 outcome 검토 전에 고정한다.
2. 두 모델에서 같은 방향으로 나타나는 residual, encoder-specific residual과 양·음
   대조 표본을 분리한다.
3. Site, stain, scanner, MPP, scale, tissue area, grade, tumor purity, 치료와 동반 변이를
   감사해 기술적·임상적 설명을 먼저 제거한다.
4. 모델, score, outcome과 site를 가린 병리 검토에서 반복 morphology를 명명한다.
5. 반복 형태를 핵·샘·세포·신경·공간 graph의 명시적 공식과 물리 단위로 정의한다.
6. 측정 repeatability, inter/intraobserver agreement와 segmentation 의존성을 검증한다.
7. Source에서 잠근 측정식을 독립 외부 코호트에 적용하고 기존 grade·stage·clinical
   factor 이상의 증분 가치와 IHC·유전체·spatial omics 연관을 평가한다.

두 모델과 외부 코호트의 반복은 후보 선별 조건이지 바이오마커 확정 조건이 아니다.

## 7. 실험군

### E0. 프로토콜·데이터 잠금

- 두 모델 버전, preprocessing, weights hash와 inference code를 고정한다.
- cohort별 sample manifest, label source, analysis unit와 exclusions를 고정한다.
- endpoint별 primary metric과 multiplicity family를 사전 정의한다.
- H2 metric–endpoint 쌍, disease-head 최소 유효성, subspace rank search, erasure method와
  matched-control 수를 사전 정의한다.

### E1. 동일 좌표·물리 스케일 paired extraction

- 가능한 cohort에서는 같은 tile 중심과 physical FOV를 사용한다.
- 모델 native preprocessing은 유지하되, shared-scale setting을 별도 생성한다.
- 동일 draw에 대한 CONCH/Virchow embedding을 동일 sample ID로 저장한다.
- tissue filtering 차이와 실패 사례를 숨기지 않고 기록한다.

### E2. 정량 concept probe benchmark

- encoder는 frozen 상태로 유지한다.
- 두 encoder에 동일 probe family와 nested patient-grouped CV를 적용한다.
- dimension 차이로 인한 capacity 차이를 정규화 또는 규제해 sensitivity analysis한다.
- 복수 지표 확장에서는 개별 probe, 다른 지표 조건부 probe와 metric-family probe를
  분리하고, 최소 세 개의 사전 정의 family에서 joint completeness를 계산한다.
- probe output, fold membership, prediction과 residual을 저장한다.

### E3. 직접 표현 및 모델 간 일치 분석

- 원본 CKA/representation similarity와 human-metric-conditioned CKA
- 동일 metric prediction agreement
- 전체 지표 패널 설명 전후의 모델 간 rank, calibration과 residual agreement 차이
- discordant sample의 임상·기술 특성

### E4. 질병 endpoint 성능 비교

- grade, phenotype, molecular, recurrence를 endpoint별 적절한 척도로 비교한다.
- 각 metric–endpoint 쌍의 label-definition 독립성을 결과를 보기 전에 감사한다.
- 질병예측기의 구조, tuning budget과 calibration 절차를 encoder 간 동일하게 고정한다.
- 모델별 point estimate가 아니라 paired uncertainty와 worst-site를 보고한다.
- class prevalence와 label composition을 함께 기록한다.

### E5A. 정량지표 관련 표현의 기능적 활용 실험

- H1을 통과한 `eligible` T1/T2 지표만 표적 제거 대상으로 사용한다.
- concept probe와 projection은 outer training fold 안에서만 추정한다.
- full, fixed-head targeted ablation, refit-after-erasure와 concept-only 예측을 모두 저장한다.
- 같은 rank·분산 제거량의 matched random subspace를 최소 1,000회 생성한다.
- label-permuted concept와 사전 지정한 다른 metric direction을 negative control로 둔다.
- encoder별 \(\Delta_{use}\), \(\Delta_{info}\), \(\Delta_{specific}\)를 환자 단위 paired
  uncertainty와 함께 보고한다.
- 선형 projection 결과는 비선형 recoverability에 대한 필요성 부정 근거로 사용하지 않는다.
- source에서 잠근 제거 규칙과 disease head를 독립 cohort에 그대로 적용한다.

### E5B. 정량지표–AI 상보성

- `C`, `C+M`, `C+AI`, `C+M+AI`를 동일 fold에서 비교한다.
- 외부 validation에서 discrimination, calibration과 decision utility를 평가한다.
- 내부 성능만 좋아지는 결합은 상보성으로 인정하지 않는다.
- E5A의 기능적 활용과 E5B의 증분 예측가치를 별도 결과표와 claim으로 관리한다.

### E6. 외부 transportability와 감시 gate

1. technical QC
2. distribution shift
3. semantic concordance
4. metric-targeted ablation effect transport
5. sentinel ground truth

각 gate는 통과/실패를 임의 단일 cutoff로 먼저 만들지 않고 source reference interval과
독립 cohort의 실제 성능 관계를 축적한 후 사전 threshold를 검증한다.

### E7. Discordance와 residual 분석

- 판단 residual \(R^{score}\)과 표현 residual \(R^{repr}\)을 별도 manifest로 관리
- A와 B가 동의하지만 truth와 불일치
- A만 truth/metric과 일치
- B만 truth/metric과 일치
- 두 모델 모두 기존 지표와 다르지만 truth와 일치
- 두 모델 모두 불일치

각 stratum에서 site, stain, scanner, tissue fraction, grade, subtype, tumor purity와
치료, 동반 변이와 artifact를 blinded review한다. Source에서 고정한 residual 정의와
sampling rule은 외부 cohort에 재학습 없이 적용해 recurrence를 판정한다.

### E8. 신규 정량지표 후보화

- 두 모델 및 외부 cohort에서 반복되는 공통 residual과 모델특이 residual을 분리한다.
- 반복 가능한 morphology를 전문의가 blinded 상태로 명명한다.
- 사람이 이해 가능한 공식과 물리/안정 계산 단위로 환원한다.
- 기술적 repeatability, inter/intraobserver agreement, independent assay·omics·outcome과
  외부 cohort를 순차적으로 검증한다.

## 8. 데이터 구조와 필수 산출 열

### 8.1 Master sample manifest

최소 열:

```text
cohort_id, site_id, subject_id, session_id, slide_id, roi_id, tile_id,
x_um, y_um, fov_um, target_mpp, specimen_type, stain, scanner,
label_id, label_value, label_source, label_status, analysis_unit,
tissue_fraction, qc_status, exclusion_reason
```

### 8.2 Paired model table

```text
sample_id, encoder, model_version, weights_hash, preprocessing_id,
embedding_path, score_id, score_value, sampling_seed, tile_budget,
inference_status, failure_reason
```

### 8.3 Quantitative metric table

```text
sample_id, metric_id, metric_role, value, unit, reference_source,
independence_from_model, measurement_status, endpoint_independence,
utilization_eligibility, qc_flag, missing_reason
```

### 8.4 Result table

```text
experiment_id, endpoint_id, encoder, cohort, site, analysis_unit,
metric_name, estimate, ci_low, ci_high, p_value, q_value,
n_subjects, n_events, n_valid, n_undefined, protocol_id
```

### 8.5 환자별 기능적 활용 table

```text
sample_id, outer_fold, cohort_id, site_id, encoder, metric_id, endpoint_id,
endpoint_independence, concept_probe_id, disease_head_id, ablation_id,
ablation_type, subspace_rank, variance_removed, truth, metric_value,
concept_oof_prediction, prediction_full, prediction_ablated,
prediction_refit_erased, qc_status, protocol_id
```

`ablation_type`은 최소 `targeted_fixed_head`, `targeted_refit`, `matched_random`,
`label_permuted`, `other_metric_control`을 구분한다. 환자별 원 예측과 제거 후 예측을
저장하지 않은 aggregate 성능표만으로 H2 결과를 보고하지 않는다.

### 8.6 기능적 활용 요약 table

```text
encoder, metric_id, endpoint_id, cohort_id, disease_metric,
performance_full, performance_ablated, delta_use, delta_info,
delta_specific, ci_low, ci_high, random_p_value, q_value,
n_subjects, n_events, n_random_controls, external_direction_preserved,
utilization_class, protocol_id
```

## 9. 통계분석 계획

### 9.1 분할과 누출 방지

- 모든 tile/slide/session은 subject 기준으로 같은 fold에 둔다.
- serial stain 또는 paired H&E/IHC가 fold를 넘지 않게 한다.
- target cohort는 source의 feature selection, probe tuning, cutoff 결정에 사용하지 않는다.
- metric shortlist가 outcome을 보고 선택되면 discovery로 명시하고 새 confirmatory set을 둔다.

### 9.2 불확실성

- subject-cluster bootstrap을 기본으로 한다.
- site 수가 충분하면 hierarchical bootstrap 또는 random-effects를 고려한다.
- 동일 draw의 encoder 대비는 paired bootstrap을 사용한다.
- single-class 또는 no-comparable-pair replicate는 undefined로 보존한다.
- seed Student-t interval을 환자 수준 uncertainty로 사용하지 않는다.

### 9.3 다중검정

- metric family를 gland, nuclear, texture, immune, nerve, molecular, outcome으로 사전 지정한다.
- confirmatory family에는 BH-FDR 또는 계층적 gatekeeping을 사용한다.
- residual discovery는 exploratory family로 분리하고 독립 validation을 요구한다.

### 9.4 Calibration과 threshold

- calibration intercept/slope, Brier 또는 IBS를 discrimination과 함께 보고한다.
- source threshold를 target에서 재최적화하지 않는다.
- threshold adaptation 연구는 별도의 명시적 protocol로 수행한다.

### 9.5 결측과 평가 불가

- missing, blank, uncertain, not-evaluable을 `no` 또는 0으로 바꾸지 않는다.
- complete-case, missing-indicator 또는 multiple-imputation 전략은 endpoint별로 사전 명시한다.
- 결측률, 이유 및 모델·cohort별 차이를 결과와 함께 보고한다.

### 9.6 H2 기능적 활용의 사전 판정 규칙

모든 \(Perf\)는 값이 클수록 우수하도록 방향을 통일한다. MAE, IBS와 같은 loss는 부호를
반전하거나 `loss increase`로 별도 정의한다. metric–endpoint–encoder별 H2 분석은 다음
전제조건을 모두 만족할 때만 시작한다.

1. \(M\)은 모델과 독립적인 T1 또는 measurement gate를 통과한 T2다.
2. H1 recoverability가 사전 grouped-null을 넘고 OOF prediction이 저장돼 있다.
3. \(Y\)는 \(M\)으로 직접 정의·파생되지 않았고 `endpoint_independence=independent`다.
4. 질병예측기 \(h_Z\) 자체가 사전 정의된 최소 유효성 기준을 통과한다.
5. 표본·사건 수와 검정력이 protocol의 최소 분석 가능 조건을 충족한다.

내부 `functional_internal` 판정은 다음을 모두 요구한다.

- \(\Delta_{use}>0\)이고 subject-cluster paired bootstrap 95% CI가 0을 제외한다.
- matched random subspace \(B\ge1{,}000\)개에 대한
  \(p_{random}=(1+\sum_b I[\Delta_{random,b}\ge\Delta_{use}])/(B+1)\)가 0.05 미만이다.
- 사전 정의한 metric–endpoint family 내 BH-FDR `q<0.05`다.
- label-permuted concept 제거보다 효과가 크고, 제거 분산량 차이로 설명되지 않는다.
- primary erasure와 최소 한 개의 사전 정의 sensitivity method에서 방향이 같다.

`functional_external`은 위 내부 판정에 더해 source에서 고정한 concept probe, subspace rank,
disease head, preprocessing과 제거 규칙을 독립 cohort에 재학습 없이 적용했을 때
\(\Delta_{use}>0\), paired 95% CI의 0 제외와 matched-random `p<0.05`를 충족해야 한다.
외부에 여러 locked metric–endpoint 쌍을 반입하면 같은 family에서 BH-FDR `q<0.05`를
추가로 요구한다. target에서 유리한 subspace, threshold 또는 metric–endpoint 조합을
다시 선택하면 external이 아니라 exploratory adaptation으로 분류한다.

### 9.7 기능적 제거의 해석 한계

- fixed-head 제거는 평가 시 embedding을 변형하므로 off-manifold artifact 가능성이 있다.
  matched random 제거, 분산량 matching과 refit-after-erasure를 함께 보고한다.
- 선형 제거 후 성능이 유지돼도 비선형 또는 중복 표현의 미사용을 증명하지 않는다.
- concept direction이 상관된 다른 형태·분자 특징을 함께 담을 수 있으므로 조건부
  direction, 다른 metric control과 metric-family 분석이 일치하지 않으면 단일 지표
  특이적 사용을 주장하지 않는다.
- \(\Delta_{use}\)는 평가된 encoder–head 시스템의 기능적 의존성 근거이지 encoder 학습
  과정의 인과기전 또는 인간과 같은 개념 사용의 증거가 아니다.
- \(\hat M\)이 \(Y\)를 예측하는 것과 \(M\) subspace 제거가 \(Y\) 예측을 저하시키는 것은
  별개 결과이며 둘을 모두 보고한다.

## 10. 판정 매트릭스

| 관찰 | 1차 해석 | 다음 조치 |
|---|---|---|
| A·B 모두 metric/truth와 일치 | encoder-independent concept 후보 | 외부 site·scale 반복 |
| A만 일치 | A-specific 유효 신호 또는 B preprocessing 문제 | shared scale, QC, probe audit |
| B만 일치 | B-specific 유효 신호 또는 A granularity 문제 | 동일한 역분석 |
| A·B 서로 일치, truth와 불일치 | shared shortcut/reference issue 위험 | 최우선 blinded error review |
| A·B 모두 metric과 낮은 일치, truth 성능 높음 | 새로운/비측정 concept 후보 | residual morphology/assay 검증 |
| A·B 모두 낮은 일치·낮은 성능 | OOD, noise 또는 부적절 task | 모델 사용 중지·원인 분석 |
| source에서는 일치, target에서 붕괴 | transport failure | adaptation 전 sentinel truth 확대 |
| target에서 일치 유지, 실제 성능 하락 | shared confounding 또는 label shift | prevalence/reference audit |
| R 양성, A 음성 | 정량지표는 decodable하지만 해당 질병과 무관 | `decodable_only`; H2 주장 금지 |
| R·A 양성, U 음성 | 질병 관련 정보이나 predictor의 선택적 사용 근거 없음 | 중복·비선형 표현 sensitivity; 사용 주장 금지 |
| U 양성, refit 후 저하 없음 | 현재 head가 사용하지만 embedding 내 대체 정보 존재 | `functional_redundant`로 보고 |
| R·A·U 양성, 외부 T 음성 | source/site 특이 기능적 의존성 | 내부 근거로 제한; transport 원인 감사 |
| R·A·U·T 양성 | 외부 재현된 기능적 활용 근거 | 최종 H2 outcome 충족; 임상 유용성은 별도 평가 |
| Y가 M으로 정의됨 | 순환 endpoint | H2 분석 제외; face-validity로만 보고 |

## 11. 마일스톤

| ID | 마일스톤 | 진입 조건 | 상태 | 완료 기준 |
|---|---|---|---|---|
| FM0 | 연구질문·모델·endpoint 동결 | P0-G0; P0-G8 결과로 최종 잠금 | P0 범위 완료 | 승인 protocol ID와 hash manifest |
| FM1 | 의료 tier·analysis registry 역할·적격성 분류 | P0-G1 분류체계 승인 | 완료 | 모든 의료 지표와 분석량에 role/단위/독립성/상태 부여 |
| FM2 | paired sample·좌표 manifest | P0-G2·G4; 새 cohort 동일 gate | 완료 | 두 모델의 동일 sample membership 100% 대조 또는 사유 기록 |
| FM3 | CONCH–Virchow paired extraction | P0-G5·G8·G9 | 완료 | embedding/score/QC와 실패 로그 생성 |
| FM4 | concept probe benchmark | P0-G6·G8·G9; power/family 승인 | 단일 T2 H1 범위 완료 | nested-CV 결과와 patient-level predictions |
| FM5 | 모델 간 표현·성능 비교 | P0-G7·G8·G9; FM4 완료 | 단일 T2 descriptive 범위 완료 | paired effect·CKA·discordance table |
| FM6 | 복수지표 완전성·기능적 활용·AI 상보성 평가 | FM4–FM5; 적격 복수 지표와 독립 metric–endpoint 쌍, 충분한 subject/event | 개발·외부 source와 TCGA WSI/기술 QC/환자 fold 등록; endpoint/tumor-region/disease-head validity/power/embargo 잠금 | 조건부·joint completeness, targeted/matched-control ablation과 C/C+M/C+AI/C+M+AI 비교 |
| FM7 | external semantic·functional transport test | P0-G9; 복수 site metadata와 sentinel truth | 잠금 | source-locked 관계·제거효과·residual·실제 성능의 target 재현 |
| FM8 | residual/discordance 전문의 검토 | FM5/7 안정 residual; blinded review 승인 | 잠금 | 두 residual의 blinded review와 명시적 후보 concept 정의 |
| FM9 | 신규 지표 독립 검증 | FM8 반복 후보; 독립 assay/omics/outcome/cohort | 잠금·장기 | repeatability, assay/omics/outcome, external replication |
| FM10 | 패키지·보고서·논문 | 관련 단계 gate와 clean rerun 완료 | 잠금·장기 | clean rerun, source tables, claim-evidence audit |

## 12. 상세 태스크 및 To-do list

### FM0. 프로토콜 동결

- [ ] 1차 endpoint와 보조 endpoint를 명시한다.
- [ ] H1 recoverability와 H2 functional utilization 가설·estimand·claim을 분리해 등록한다.
- [ ] H2의 metric–endpoint 쌍과 순환성 제외 기준을 outcome 확인 전에 고정한다.
- [ ] disease-head 최소 유효성, primary \(Perf\), erasure family, subspace rank와
  matched-random 반복 수를 endpoint별로 고정한다.
- [ ] CONCH/Virchow model ID, revision, weights hash를 기록한다.
- [ ] preprocessing, MPP, FOV, tile size와 aggregation을 고정한다.
- [ ] source, validation, external target cohort를 명시한다.
- [ ] confirmatory와 exploratory hypothesis family를 분리한다.
- [ ] 허용·금지 주장을 protocol에 기록한다.
- [ ] frozen-score audit과 새 probe 연구의 산출물 경로를 분리한다.

완료 판정:

- 결과를 보기 전 승인된 protocol 및 run configuration 초안이 존재한다.

### FM1. 지표 적격성 감사

- [ ] Tier 1–4 의료 카탈로그와 별도 analysis registry의 경계를 전 행에서 확인한다.
- [ ] 각 지표의 `analysis_unit`을 검증한다.
- [ ] reference가 pathologist, assay, algorithm 또는 AI인지 기록한다.
- [ ] CONCH/Virchow와의 독립성을 분류한다.
- [ ] 바로 사용 가능한 biological feature를 shortlist한다.
- [ ] contour 승인 대기 지표를 deferred로 유지한다.
- [ ] performance/QC 지표가 의료 정량지표 수나 환자 feature로 들어가지 않는지 검사한다.
- [ ] metric별 허용 질병·임상 역할을 catalog와 대조한다.
- [ ] PTEN/ERG/SPOP/AR처럼 연구계획에는 있으나 중앙 의료 카탈로그에 없는 독립 assay
  reference를 T1 추가 후보 또는 study-local reference로 명시한다.
- [ ] 각 metric–endpoint 쌍의 `endpoint_independence`를 두 source의 provenance로 판정한다.
- [ ] H2 진입 가능성을 `eligible`, `exploratory_only`, `prohibited`로 분류한다.

완료 판정:

- 모든 지표가 포함·제외·QC·endpoint·deferred 중 하나로 설명되고, 모든 H2 후보
  metric–endpoint 쌍의 순환성 및 독립성 판정 근거가 저장된다.

### FM2. 데이터 및 좌표 정합성

- [ ] cohort별 subject/slide/session/ROI ID 규칙을 통일한다.
- [ ] 동일 환자의 중복 slide와 serial section을 표시한다.
- [ ] tile 중심을 micrometre 좌표로 변환한다.
- [ ] 동일 FOV 추출 가능 여부를 cohort별로 점검한다.
- [ ] scanner, stain, specimen type, MPP metadata를 수집한다.
- [ ] label provenance와 결측 사유를 기록한다.
- [ ] H2 후보에서 \(M\)과 \(Y\)의 subject 연결, 측정시점, specimen 및 label 생성 경로를 대조한다.
- [ ] \(Y\) 판독·생성 과정에 \(M\)이 사용됐는지 확인하고 불명확하면 `unknown`으로 잠근다.
- [ ] source 파일 hash와 불변성 검사를 구성한다.
- [ ] exclusion flow table을 생성할 schema를 고정한다.

완료 판정:

- 모델 간 sample 차이는 0이거나 모든 차이에 기계 판독 가능한 이유가 있다.

### FM3. Paired embedding/score 생성

- [ ] 동일 좌표에서 CONCH embedding을 생성·검증한다.
- [ ] 동일 좌표에서 Virchow embedding을 생성·검증한다.
- [ ] native scale과 shared scale을 별도 protocol ID로 관리한다.
- [ ] 16/32/64 tile budget의 동일 sampling draw를 보장한다.
- [ ] embedding norm, NaN/Inf, shape와 sample order를 검사한다.
- [ ] GPU/소프트웨어/model revision을 기록한다.
- [ ] 실행 실패와 재시도를 숨기지 않고 로그에 남긴다.
- [ ] embedding 파일과 metadata의 hash를 기록한다.

완료 판정:

- 동일 sample ID로 두 모델 표현이 1:1 연결되고 clean rerun이 일치한다.

### FM4. Concept probe

- [ ] endpoint별 patient-grouped folds를 한 번 생성하고 두 모델이 공유한다.
- [ ] 동일 probe family와 tuning budget을 적용한다.
- [ ] 연속·이진·순서·생존 endpoint별 평가 함수를 고정한다.
- [ ] 모든 out-of-fold prediction을 저장한다.
- [ ] fold별 표본·사건·class balance를 보고한다.
- [ ] probe dimension/capacity sensitivity를 수행한다.
- [ ] source에서만 fitting하고 target에는 locked 적용한다.
- [ ] undefined fold/replicate를 기록한다.
- [ ] H2 후보 metric의 OOF concept prediction을 disease prediction과 동일 subject/fold ID로 저장한다.
- [ ] 선형·비선형 recoverability를 구분해 적용 가능한 erasure family를 사전 지정한다.

완료 판정:

- 모든 reported metric이 저장된 patient-level prediction table에서 재생성된다.

### FM5. Cross-model 비교

- [ ] endpoint별 A–B paired performance delta를 계산한다.
- [ ] score/rank/calibration agreement를 계산한다.
- [ ] CKA와 representational similarity를 계산한다.
- [ ] native/shared scale 대비를 분리한다.
- [ ] site·scanner·stain·specimen별 subgroup을 기술한다.
- [ ] discordant sample manifest를 생성한다.
- [ ] 결과를 encoder league table로 과해석하지 않는지 확인한다.
- [ ] sampling seed를 독립 표본으로 간주하지 않았는지 점검한다.

완료 판정:

- 공통 concept, 모델특이 concept, 불안정 concept가 근거표와 함께 분류된다.

### FM6. 복수지표 완전성, 기능적 활용과 AI 상보성

- [ ] 최소 세 개의 사전 정의 metric family에서 개별·조건부 복원성과 포함관계를 계산한다.
- [ ] 복수 지표 패널의 표현·판단 joint completeness를 OOF와 외부 표본에서 계산한다.
- [ ] clinical-only baseline을 고정한다.
- [ ] metric-only/clinical+metric 모델을 구성한다.
- [ ] CONCH/clinical+CONCH 모델을 구성한다.
- [ ] Virchow/clinical+Virchow 모델을 구성한다.
- [ ] metric+각 AI 결합을 동일 split에서 비교한다.
- [ ] H1을 통과하고 endpoint와 독립적인 metric–endpoint 쌍만 H2 대상으로 잠근다.
- [ ] outer training fold에서만 encoder별 concept subspace와 rank를 추정한다.
- [ ] locked disease head의 full 대 targeted fixed-head ablation을 환자별로 저장한다.
- [ ] targeted refit-after-erasure를 수행해 대체 가능한 중복 정보를 구분한다.
- [ ] metric-only/concept-only 예측으로 정량지표 관련 subspace의 sufficiency를 평가한다.
- [ ] rank·제거분산량을 맞춘 random subspace를 최소 1,000회 평가한다.
- [ ] label-permuted concept와 other-metric direction negative control을 평가한다.
- [ ] \(\Delta_{use}\), \(\Delta_{info}\), \(\Delta_{specific}\)와 paired uncertainty를 저장한다.
- [ ] metric–endpoint family 내 multiplicity를 보정하고 undefined replicate를 보존한다.
- [ ] discrimination, calibration, decision utility를 함께 평가한다.
- [ ] 외부 cohort에서 incremental value를 재검증한다.
- [ ] 결합 성능이 개선되지 않은 negative result도 보존한다.

완료 판정:

- 개별·조건부 정보, metric-family 포함관계와 joint completeness가 환자분리 source
  table에서 재생성된다. 기능적 활용은 Section 9.6의 내부 판정 규칙으로 분류되고,
  상보성은 별도 결과로 분리된다. `C+M+AI` 향상만으로 활용을 주장하지 않으며 외부
  재현 전에는 H2 최종 outcome으로 승격하지 않는다.

### FM7. 외부 이식성 및 감시

- [ ] source QC/reference distribution을 고정한다.
- [ ] target의 stain/focus/tissue/scanner QC를 계산한다.
- [ ] MMD/Wasserstein/C2ST representation shift를 계산한다.
- [ ] confidence, entropy와 output drift를 계산한다.
- [ ] source-fitted AI–metric 관계를 target에 적용한다.
- [ ] source에서 잠근 concept probe, subspace와 disease head를 target에 재학습 없이 적용한다.
- [ ] target의 metric-targeted 제거효과와 matched-control null을 동일 규칙으로 계산한다.
- [ ] semantic residual shift와 relation interaction을 계산한다.
- [ ] source-locked \(R^{repr}\)·\(R^{score}\) 정의와 sampling rule의 외부 recurrence를 계산한다.
- [ ] sentinel label subset에서 실제 성능을 계산한다.
- [ ] QC-only/OOD-only/semantic/combined monitoring을 비교한다.
- [ ] site-held-out 방식으로 성능 저하 예측을 검증한다.
- [ ] 검증 전에는 단일 acceptance cutoff를 제시하지 않는다.

완료 판정:

- 일치도가 정확도를 대신하지 않으며 실제 성능에 대한 증분 경보 가치가 정량화된다.
  H2는 source-locked targeted ablation 효과가 외부 cohort에서 재현될 때만
  `functional_external`로 분류된다.

### FM8. Residual·discordance 검토

- [ ] \(R^{repr}\)과 \(R^{score}\)의 정의와 추출 threshold를 source에서 각각 고정한다.
- [ ] 높은 양·음 residual과 A/B discordant patch를 균형 있게 선정한다.
- [ ] 두 모델 공통·모델특이·외부 반복 residual을 별도 stratum으로 관리한다.
- [ ] 모델, score, endpoint와 site를 숨긴 blinded interface를 만든다.
- [ ] 병리전문의가 morphology, artifact, adequacy와 uncertainty를 기록한다.
- [ ] 반복 concept를 명명하고 명시적 계산 정의를 작성한다.
- [ ] inter/intraobserver 평가 가능성을 점검한다.
- [ ] shortcut 후보를 site/stain/scanner와 교차검증한다.
- [ ] 결과를 hypothesis generation으로 제한한다.

완료 판정:

- 각 residual 후보가 biological candidate, technical shortcut, known concept, uncertain,
  not-evaluable 중 하나로 분류된다.

### FM9. 신규 지표 검증

- [ ] 지표의 물리 또는 안정 계산 단위를 정의한다.
- [ ] 자동계측 repeatability와 segmentation 의존성을 평가한다.
- [ ] 다른 scanner, stain, MPP에서 robustness를 평가한다.
- [ ] 기존 grade/stage/clinical factor 이상의 증분 가치를 평가한다.
- [ ] IHC, genomic 또는 spatial-omics의 독립 biological anchor와 연관을 평가한다.
- [ ] 독립 기관에서 locked validation을 수행한다.
- [ ] 임상 cutoff가 필요하면 별도 개발·검증 protocol을 수립한다.
- [ ] 부정적·불확실 결과를 catalog에 반영한다.

완료 판정:

- 독립 반복과 생물학적 근거 전에는 `candidate biomarker` 이상의 용어를 사용하지 않는다.

### FM10. 재현성·보고·패키지화

- [ ] 하나의 auditable entry point로 각 분석을 재생성한다.
- [ ] figure source CSV와 table source CSV를 저장한다.
- [ ] run config에 seed, versions, hashes와 execution time을 기록한다.
- [ ] output hash가 자기 자신을 포함하지 않게 구성한다.
- [ ] clean rerun을 수행한다.
- [ ] 원본 source pre/post hash를 비교한다.
- [ ] claim–evidence matrix를 작성한다.
- [ ] metric catalog에 새 지표·증거·제한을 반영한다.
- [ ] methods, negative results, undefined replicate를 보고한다.
- [ ] H1과 H2의 claim–evidence chain 및 `R/A/U/T` 판정을 metric–endpoint별로 내보낸다.

완료 판정:

- 모든 주장과 숫자가 저장된 source table과 protocol로 추적된다.

## 13. PRECISE PNI 전용 태스크

### 즉시 가능한 작업

- [ ] frozen PNI candidate score와 현재 독립적으로 계산 가능한 tissue/spatial 지표의
  관계를 기술한다.
- [ ] 모델 score와 morphology review 결과를 candidate-level로 연결하되 선택설계를
  명시한다.
- [ ] 14 nerve-positive focus에서 평가 가능성과 discordance 유형을 파일럿 분석한다.
- [ ] 현재 분석을 whole-slide diagnostic comparison으로 표현하지 않는다.

### Contour 승인 후 가능한 작업

- [ ] nerve area, diameter, aspect ratio를 계산한다.
- [ ] encasement fraction과 contact length를 계산한다.
- [ ] tumor–nerve distance gradient를 계산한다.
- [ ] 같은 focus에서 CONCH/Virchow spatial representation을 paired 비교한다.
- [ ] morphology·geometry가 각 model score를 설명하는 정도를 계산한다.

### 외부 코호트 후 가능한 작업

- [ ] 새로운 환자의 전체 후보 universe와 review coverage를 구축한다.
- [ ] target score를 재학습하지 않고 semantic relation을 평가한다.
- [ ] sentinel review에서 실제 candidate-level performance를 평가한다.
- [ ] multiple site에서 concordance와 performance-drop 관계를 검증한다.
- [ ] 충분한 전수 또는 확률표본 판독 없이는 whole-slide sensitivity를 계산하지 않는다.

## 14. 예상 산출물

권장 연구 산출물 구조:

```text
projects/quantitative_foundation_model_validation/
├── PROTOCOL.md
├── run_config.json
├── metric_eligibility.tsv
├── sample_manifest.csv
├── paired_model_manifest.csv
├── patient_predictions.csv
├── metric_concept_results.csv
├── metric_conditional_information.csv
├── joint_completeness_results.csv
├── representation_similarity.csv
├── concept_use_patient_predictions.csv
├── concept_use_ablation_results.csv
├── concept_use_matched_null.csv
├── metric_endpoint_independence.tsv
├── complementarity_results.csv
├── transportability_results.csv
├── discordance_manifest.csv
├── representation_residual_manifest.csv
├── decision_residual_manifest.csv
├── residual_candidate_metrics.csv
├── bootstrap_replicates.csv
├── data_integrity_report.csv
├── claim_evidence_matrix.csv
├── RESULTS_REPORT.md
└── figure_source/
```

대용량 embedding, WSI, local source data와 generated outputs는 저장소에 commit하지 않는다.

## 15. 논문 또는 보고서의 핵심 표·그림

1. 연구 개념도: known metric, AI-common, AI-specific, shortcut 분해
2. cohort–endpoint–model–ground-truth matrix
3. CONCH 대 Virchow metric recoverability paired forest plot
4. 지표별 조건부 고유정보·포함관계와 joint completeness heatmap
5. 정량지표별 full 대 targeted/matched-control ablation paired forest plot
6. `decodable → associated → functionally used → externally transported` outcome cascade
7. `C`, `C+M`, `C+AI`, `C+M+AI` 외부 성능·calibration 비교
8. QC/embedding/semantic/functional drift와 실제 performance drop 관계
9. 표현 residual·판단 residual을 구분한 외부 반복 pathology atlas
10. 신규 지표 validation cascade와 negative-result table

## 16. 허용되는 결론 수준

### Level 1: 내부 concept evidence

> 해당 정량개념은 이 코호트의 환자분리 교차검증에서 모델 표현으로 복원됐다.

### Level 2: cross-encoder evidence

> 서로 독립적으로 학습된 CONCH와 Virchow에서 관계 방향이 재현됐다.

### Level 3: external transport evidence

> source에서 고정한 관계가 독립 target cohort에서 재학습 없이 유지됐다.

### Level 4: 내부 functional-utilization evidence

> frozen encoder 위의 locked 질병예측기는, 사전 정의된 targeted ablation과 matched
> control 비교에서 해당 정량지표 관련 표현 성분에 선택적으로 의존했다.

이는 평가된 encoder–head 시스템의 내부 기능적 의존성 근거이며 외부 일반화 또는
encoder 학습의 인과기전 주장이 아니다.

### Level 5: external functional-utilization evidence

> source에서 고정한 정량지표 관련 제거효과가 독립 cohort에서 재현됐고, 정량지표와
> 관련된 표현 성분에 대한 예측기의 기능적 의존성이 외부에서도 유지됐다.

### Level 6: incremental clinical evidence

> 정량지표와 AI의 결합이 독립 외부 cohort에서 기존 임상·병리 모델 이상의 성능과
> calibration을 보였다.

Level 5 기능적 활용의 외부 재현과 Level 6 증분 임상가치는 별도 estimand이며, 한쪽의
통과가 다른 쪽을 자동으로 의미하지 않는다.

### Level 7: candidate biomarker evidence

> 잔차에서 정의한 지표가 재현 가능한 측정법, 독립 생물학적 assay 및 외부 임상
> endpoint에서 검증됐다.

### 금지되는 결론

- cross-encoder agreement만으로 생물학적 진실을 확정
- 높은 concordance만으로 외부 진단 정확도를 확정
- PRECISE 선택 표본의 결과를 모집단 또는 whole-slide 성능으로 일반화
- 한 encoder의 높은 내부 점수로 보편적 우월성 주장
- contour 미승인 값을 실제 nerve geometry로 해석
- 정량지표가 decodable하거나 disease-associated라는 이유만으로 “모델이 사용한다”고 주장
- circular metric–endpoint 조합 또는 attention/feature importance만으로 H2를 통과시킴
- targeted linear erasure의 음성 결과로 비선형·중복 개념의 부재를 확정

## 17. 즉시 착수 순서

다음 순서가 가장 위험이 낮고 기존 자산을 많이 재사용한다.

1. P0-M0–M2: 사전실험 protocol, 지표 독립성과 공통 표본·truth를 잠근다.
2. P0-M3: 새 embedding 추출 전에 기존 결과로 양성대조가 작동하는지 확인한다.
3. P0-M4–M7: PRECISE paired tile에서 정량개념 복원과 기술 민감성을 파일럿한다.
4. P0-M8–M9: Go/Conditional Go/Revise/Stop을 결정하고 clean rerun으로 인계한다.
5. FM0–FM1: P0와 병렬 가능한 protocol 및 의료 tier/analysis registry 감사를 완료한다.
6. FM2–FM5: `main_study_unlock_matrix.csv`에서 열린 model–target–FOV 조합만 확장한다.
7. FM6: 독립 metric–endpoint 쌍과 충분한 표본·사건이 갖추어진 뒤 기능적 활용과
   상보성을 서로 다른 estimand로 검증한다.
8. FM7: 신규 외부 cohort와 sentinel labels에서 source-locked semantic relation과
   targeted ablation 효과를 함께 재현한다.
9. FM8–FM9: 외부 relation과 residual 안정성, 독립 검증 수단이 확인된 뒤 시작한다.

## 18. 의사결정 게이트

아래 G0–G7은 P0-G0–P0-G9 통과 후 적용되는 **본 연구 게이트**이다. 동일 번호대의
P0 gate와 혼동하지 않는다.

| Gate | 진입 조건 | 통과 조건 | 통과 실패 시 |
|---|---|---|---|
| G0 Protocol | 연구질문 합의 | 모델·metric·endpoint·claims 동결 | 설계 보완 |
| G1 Data | manifest·truth 확보 | paired sample과 provenance 정합 | 해당 cohort 제외/수정 |
| G2 Measurement | 독립 metric 사용 가능 | repeatability/QC 허용 | metric deferred |
| G3 Benchmark | paired model output 완료 | 재현 가능한 patient-level 결과 | 원인감사 후 제한 보고 |
| G4 Functional use/Transport | H1 통과 metric, 독립 endpoint와 외부 cohort 확보 | targeted effect가 matched control을 넘고 source-locked 외부 방향 재현 | decodable/내부 또는 모델·site-specific로 제한 |
| G5 Novelty | residual morphology 반복 | 명시적 정의·shortcut 배제 | hypothesis 폐기/보류 |
| G6 Biomarker | 독립 assay/outcome 확보 | external incremental validation | candidate 단계 유지 |
| G7 Clinical | 전향 workflow 가능 | calibration·안전성·유용성 충족 | 연구용으로 유지 |

## 19. 근거 검토·승인·재현성 포털

P0-G8부터는 검토와 승인 상태를 정적 문서의 서명란에 직접 덮어쓰지 않는다.
`projects/quantitative_foundation_model_validation/governance_portal/`의 loopback-only
웹 포털을 표준 진입점으로 사용한다.

포털의 순서는 다음과 같다.

1. 동일 evidence snapshot에서 P0-Q1–Q6, model–target–FOV 조합, 미해결 위험과
   금지 주장을 검토한다.
2. 이 독립 연구에서는 연구책임자가 판정과 실명 전자서명을 append-only ledger에
   기록한다. 병리, 통계, ML/데이터 검토는 필요 시 기록하는 비차단 자문이다.
3. 연구책임자의 최신 판정이 현재 snapshot에 대한 `Conditional Go`일 때만 P0-G8을
   확정한다.
4. G8 확정 후에만 별도 출력 디렉터리에서 P0-M9 full-GPU clean rerun을 수행한다.
5. deterministic 산출물의 byte hash, 문서화된 volatile field를 제외한
   `run_config.json`, source pre/post hash와 immutable clinician source hash가 모두
   일치할 때만 P0-G9 인계 manifest를 생성한다.

승인 원문, evidence snapshot, G8/G9 manifest와 clean-rerun 로그는
`preexperiment/governance_records/`에 보존한다. 기존 P0-M8 산출물과 원천 자료는
수정하지 않는다. 근거 snapshot이 바뀌면 기존 승인은 현재 승인으로 간주하지 않는다.

전자 승인은 governance 결손만 해소한다. 측정 반복성, 독립 metric–endpoint pair,
충분한 환자·사건 수, 외부 cohort, scanner/stain sentinel truth와 같이 데이터가 필요한
조건은 서명으로 대체할 수 없다. 따라서 P0-G8/G9 통과는 FM1, 범위 제한 FM2와
shared-FOV descriptive FM3만 인계하며 confirmatory target, H2 본 분석, 임상·진단 및
모델 우월성 주장은 각각의 추가 gate 전까지 잠근다.

이 단일책임자 체계는 독립 연구에 한정한다. 다기관 공동연구, 임상 의사결정 또는 규제
목적 단계에서는 기관·역할별 승인과 이해관계 조정 절차를 별도 protocol로 활성화한다.
이 변경은 P0-M8 결과 확인 후 이루어진 governance amendment이며 기존 과학적 분석
사전지정이나 claim gate를 변경하지 않는다.

## 20. 완료 정의

이 실행계획은 다음 조건을 모두 충족해야 완료된다.

- 두 모델이 동일 표본과 동일 물리적 조건에서 비교됐다.
- 의료 Tier 1–4와 별도 analysis measure의 역할과 독립성이 명시됐다.
- 결과는 환자 단위 paired uncertainty를 포함한다.
- concept 복원성, 질병 관련성, 기능적 활용, 상보성 및 external transport가 서로 분리됐다.
- 모든 H2 metric–endpoint 쌍의 label-definition 독립성과 순환성 감사가 완료됐다.
- 최소 한 개의 사전 지정 metric–endpoint 쌍에서 H2의 `R/A/U/T`가 평가됐으며, 실패한
  단계도 음성 결과로 보존됐다. 모든 쌍의 통과를 완료 조건으로 요구하지 않는다.
- 일치도가 정확성의 대체물로 사용되지 않았다.
- residual 후보는 shortcut 감사를 거쳤다.
- 모든 숫자와 그림이 저장된 source table에서 재생성된다.
- PRECISE PNI에 대한 주장은 candidate triage와 선택 표본의 범위를 넘지 않는다.

## 21. 마일스톤 실행 기록 및 문서 갱신 원칙

### 21.1 운영 원칙

FM0–FM10의 각 마일스톤은 분석 산출물 생성만으로 종료하지 않는다. 마일스톤을
완료 처리하는 같은 작업 단위에서 이 문서를 갱신하고 다음 내용을 남긴다.

1. 수행 범위와 완료 조건
2. 핵심 결과 및 수치
3. 새로 발견한 사실과 배운 점
4. 해소되지 않은 한계와 허용·금지 해석
5. 재현 가능한 산출물 경로와 다음 진입 조건

따라서 아래 실행 기록의 갱신은 각 마일스톤 완료 정의의 일부다. 범위 제한 또는
음성 결과도 생략하지 않으며, 후속 결과가 앞선 해석을 바꾸면 기존 기록을 삭제하지
않고 날짜가 있는 후속 항목으로 정정한다.

### 21.2 P0 사전실험 종료 및 본 연구 인계 — 2026-08-12

**수행·결과**

- P0-G8은 독립 연구의 연구책임자 Jin Hyun Kim이 제한적 `Conditional Go`로
  확정했다.
- 첫 P0-M9 clean rerun은 56개 비교 대상 중 숫자·표·배열은 모두 일치했으나,
  `positive_control_report.md`의 과거 상태 문장 1개가 현재 결정 논리와 달라
  `Revise`로 보존했다.
- 상태 문장을 현재 deterministic code와 일치시키고 전체 GPU 파이프라인을 처음부터
  다시 실행한 두 번째 clean rerun은 56/56 byte 비교가 일치해 P0-G9를 통과했다.
- 원천 파일 pre/post hash와 immutable clinician source SHA-256
  `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`도 일치했다.

**배운 점과 제한**

- 재현성은 수치만이 아니라 결과 해석 문장까지 현재 code path와 일치해야 한다.
- G8/G9 통과는 과학적 근거 부족을 대신하지 않는다. 이 인계가 해제한 범위는 FM1,
  범위 제한 FM2, shared-394.24 µm descriptive FM3뿐이다.
- 측정 반복성 없는 confirmatory target, PNI/임상 진단, encoder 우월성,
  scanner/stain 강건성 및 독립 metric–endpoint·표본·사건·외부 검증 없는 H2는
  계속 금지한다.

**산출물**

- `projects/quantitative_foundation_model_validation/preexperiment/governance_records/G8_FINAL_DECISION.md`
- `projects/quantitative_foundation_model_validation/preexperiment/governance_records/clean_rerun/attempt-20260812T133154Z/`
- `projects/quantitative_foundation_model_validation/preexperiment/governance_records/clean_rerun/attempt-20260812T135439Z/`
- `projects/quantitative_foundation_model_validation/preexperiment/governance_records/g9_handoff_manifest.json`
- `projects/quantitative_foundation_model_validation/preexperiment/governance_records/main_study_unlock_matrix_final.csv`

### 21.3 FM1 지표 적격성 감사 완료 — 2026-08-12

**수행·결과**

- 의료 정량지표 58개를 T1–T4 체계에서 전수 감사하고, 모델 성능·QC·감사에 쓰는
  analysis measure 73개를 의료 지표 수와 환자 feature에서 분리했다.
- 즉시 실행 가능한 H1 표적은 T2 `tumor_fraction` 1개이며, independent
  measurement repeatability가 없어 `descriptive_only`다.
- H2 metric–endpoint 후보 11쌍을 독립성·순환성 기준으로 감사했으나 현재 실행
  가능한 쌍은 0개다. 우선 준비 후보는 ISUP grade group–biochemical recurrence이나
  subject linkage, 사건 수, 치료 공변량과 외부 cohort가 없다.

**배운 점과 제한**

- “113개 중 1개”가 아니라, 의료 지표와 분석량을 섞어 센 기존 분모가 잘못된
  해석의 원인이었다. 현재 결과는 의료 지표 58개 중 PRECISE에서 즉시 paired truth로
  시험 가능한 지표가 1개라는 뜻이다.
- 지표를 embedding에서 복원하는 H1과 그 지표가 질병예측에 기능적으로 사용되는
  H2는 별개의 증거 단계다. FM1은 H2 실행을 해제하지 않았다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm1_metric_eligibility/outputs/FM1_REPORT.md`
- `.../medical_metric_eligibility.tsv`
- `.../analysis_measure_boundary.tsv`
- `.../metric_endpoint_independence.tsv`
- `.../study_local_reference_candidates.tsv`
- `.../fm1_summary.csv`
- `.../run_config.json`

### 21.4 FM2 paired sample·좌표 manifest 완료 — 2026-08-12

**수행·결과**

- 14,731개 inventory tile에서 승인 범위에 맞는 1,218개 paired tile, 25 subjects,
  27 sessions를 고정했다.
- CONCH와 Virchow의 membership mismatch, level-0 boundary mismatch, crop hash
  mismatch 및 tumor truth 결측은 모두 0이었다.
- subject/slide/session/sample ID, micrometre 좌표, 공통 394.24 µm FOV, fold와 label
  provenance를 한 행 단위로 연결했다.

**배운 점과 제한**

- 두 encoder 비교의 기본 단위는 임의로 비슷한 tile이 아니라 동일 crop hash와
  동일 물리 경계를 갖는 1:1 표본이어야 한다.
- scanner와 stain-batch metadata, H2 endpoint linkage는 존재하지 않는다. 이를
  추정하거나 보정하지 않고 `not_available`로 명시했으므로 해당 robustness/H2 주장은
  여전히 불가능하다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm2_paired_manifest/outputs/FM2_REPORT.md`
- `.../paired_sample_manifest.csv`
- `.../manifest_qc.csv`
- `.../exclusion_flow.csv`
- `.../run_config.json`

### 21.5 FM3 paired embedding bundle 완료 — 2026-08-12

**수행·결과**

- P0-G9 clean attempt에서 생성한 동일 1,218개 표본의 CONCH `1218×512`와
  Virchow `1218×2560` embedding을 본 연구 bundle로 등록했다.
- 두 배열 모두 NaN/Inf와 zero-norm row가 없었고 sample-order 및 저장 hash mismatch가
  0이었다. 대용량 배열은 복사하지 않고 clean-attempt의 immutable 경로를 hash로
  참조한다.

**배운 점과 제한**

- paired extraction의 핵심 산출물은 배열 자체뿐 아니라 row manifest, model revision,
  weights hash, physical FOV와 원본 배열 hash를 함께 고정한 bundle이다.
- 이 완료는 shared-394.24 µm tumor-fraction descriptive 분석만 준비한다. 새로운
  inference, confirmatory target, clinical/PNI, scanner/stain, encoder 우월성 또는 H2를
  해제하지 않는다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm3_paired_embeddings/outputs/FM3_REPORT.md`
- `.../embedding_bundle_manifest.csv`
- `.../embedding_row_manifest.csv`
- `.../run_config.json`

**다음 진입 조건**

FM4에서는 실제 concept benchmark 실행 전에 단일 descriptive target, 두 encoder,
25 subjects라는 제한에 맞는 분석 family·estimand·검정력/정밀도·다중비교·중단 기준을
문서로 고정하고 연구책임자의 범위 승인을 받아야 한다.

### 21.6 ORG-M0–M4 프로젝트 구조 분리 완료 — 2026-08-12

**수행·결과**

- 혼재하던 저장소를 `precise_pni_candidate_triage`,
  `quantitative_foundation_model_validation`, `prostate_biomarker_validation`의 세
  canonical 프로젝트로 물리 분리했다.
- 정량지표 taxonomy·P0 governance·FM1–FM4 bundle은 정량화 프로젝트에, PNI
  frozen audit·morphology/contour review는 PNI 프로젝트에, 현재 논문·분자표지자 및
  재발/생존 분석은 biomarker 프로젝트에 귀속했다.
- 이동 전 1,351개 파일의 크기·SHA-256·Git 상태·소유 후보를 기록하고, 이동 후
  관리 대상 671개를 재감사했다. 미분류 파일은 5개에서 0개로 감소했다. 57 GB의
  모델·환경·third-party·local result 루트는 `resources/projects/prostate_biomarker_validation/model_workspace/`로 분리되어 이동 후
  관리 파일 분모에서 제외된다.
- `models`, `paper`, 기존 quantitative `studies/...` 경로는 호환 symlink로 유지했다.
  따라서 기존 명령과 frozen provenance는 보존하되 신규 작업은 canonical 경로를 쓴다.
- 경계 검증기는 세 프로젝트의 필수 구조, 호환 링크, 프로젝트 간 Python import,
  immutable PNI clinician source hash를 검사하며 전 항목 PASS였다.
- 저장소 전역 `Project Structure Codex`를 제정해 새 파일의 소유 프로젝트와 허용
  위치를 의무화했다. Superpowers 문서는 프로젝트별 `docs/designs`·`docs/plans` 또는
  repository-wide `docs/superpowers`만 사용하며 metadata header를 갖는다. 보조 Git
  worktree는 `.worktrees/<project_id>/<slug>`와 registry로 통제한다.
- 관리 포털은 canonical 경로의 watchdog으로 재기동했고 `127.0.0.1:8011`에만
  bind한 상태로 API 응답을 확인했다.

**배운 점과 제한**

- 동일 PRECISE 영상의 재사용은 연구의 결합을 뜻하지 않는다. PNI review label은
  정량화 연구의 endpoint가 아니며, 공유해야 하는 것은 hash-locked image/embedding
  manifest뿐이다.
- 물리 경로를 바꾸더라도 과거 결과 안의 경로 문자열은 provenance의 일부다. 이를
  재작성하지 않고 호환 alias로 해석 가능하게 하는 편이 frozen 기록을 보존한다.
- biomarker legacy code의 `models`/`paper` import는 호환층에 남아 있다. 과학적 가정이
  동일하다는 시험 근거 없이 성급히 공통 package로 추출하지 않는다.
- 이 구조 변경은 FM4 실행 승인이나 confirmatory target, PNI/임상 진단, encoder
  우월성, scanner/stain robustness, H2 질병예측을 새로 허용하지 않는다.

**산출물**

- `infrastructure/migrations/2026-08-12-project-separation/REORGANIZATION_PLAN.md`
- `infrastructure/migrations/2026-08-12-project-separation/ORG_MIGRATION_REPORT.md`
- `infrastructure/migrations/2026-08-12-project-separation/pre_migration_file_inventory.csv`
- `infrastructure/migrations/2026-08-12-project-separation/post_migration_file_inventory.csv`
- `infrastructure/migrations/2026-08-12-project-separation/compatibility_aliases.csv`
- `infrastructure/migrations/2026-08-12-project-separation/immutable_inputs.csv`
- `infrastructure/migrations/2026-08-12-project-separation/running_services.csv`
- `infrastructure/scripts/validate_project_boundaries.py`
- `infrastructure/tests/test_project_boundaries.py`
- `infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md`
- `infrastructure/docs/repository/templates/SUPERPOWERS_DOCUMENT_HEADER.md`
- `.worktrees/README.md`
- `.worktrees/registry.csv`
- `infrastructure/scripts/audit_worktrees.py`

**다음 진입 조건**

프로젝트 구조 분리는 완료되었다. 정량화 연구의 다음 과학적 단계는 기존 계획대로
FM4 entry packet의 현재 evidence snapshot을 검토·승인한 뒤, 승인된 단일 descriptive
target 범위에서만 concept benchmark를 실행하는 것이다.

### 21.7 ORG-M5 루트 완전 정규화 완료 — 2026-08-12

**수행·결과**

- 루트에 남아 있던 일반 폴더와 호환 symlink를 전수 분류하고, 공통 운영 요소는
  `infrastructure/`, 로컬 데이터·모델·생성물은 `resources/`, 연구 코드·계획·결과·논문은
  `projects/<project_id>/`에 배치했다.
- 최종 루트는 세 canonical 관리 폴더, 도구·Git·실행환경에 필요한 일곱 dot 폴더,
  그리고 등록된 일곱 정책·환경 파일만 허용한다. `models`, `paper`, `studies`, `docs`,
  `scripts`, `packages`, `shared`, `data`, `artifacts`, `opendataset`, `song-datasets`,
  `local-data`, `model-weights`, `reorganization` 등 기존 일반 루트와 호환 alias는 모두
  제거했다.
- 루트 registry와 실제 항목을 1:1로 대조하는 자동 검증, 프로젝트별 resource
  ownership registry, 구 경로–신 경로 이관표를 추가했다. 정규화 후 관리 파일 682개를
  재분류했으며 미분류 파일은 0개였다.
- `.superpowers/`는 runtime state 전용으로 비웠다. 최종 설계·계획은 소유 프로젝트의
  `docs/designs`·`docs/plans` 또는 저장소 전역 `infrastructure/docs/superpowers`에만
  둘 수 있고, 연구문서가 runtime 폴더에 남으면 경계 검증이 실패한다.
- biomarker model workspace 안의 내부 symlink 157개를 canonical project/resource
  경로로 재결합했고, root compatibility symlink 없이 동작하도록 코드·시험·논문
  source lineage 경로를 갱신했다.
- 최종 검증에서 경계·root registry·worktree·broken-link·immutable source hash가 모두
  PASS였고, PNI 37/37, 정량 30/30, 공통 metric package 14/14, repository integration
  2/2가 통과했다. Biomarker는 322/323이 통과했으며 유일한 실패는 사용자가 갱신한
  현재 NRF/GNU Funding 문구와 과거 ICT 문구를 요구하는 기존 시험의 불일치다.
  현재 선언문은 연구구조 변경 대상이 아니므로 덮어쓰지 않았다.
- 관리 포털은 canonical entry point의 기존 `qfmv-governance` tmux session에서
  재기동했으며 `127.0.0.1:8011/api/status` 응답을 확인했다.

**배운 점과 제한**

- 폴더 이동만으로 프로젝트 분리가 끝나지 않는다. 허용 루트를 닫고, Git에서
  제외되는 데이터·weights·archive에도 소유자를 명시하며, 새 파일 생성 시 자동
  실패하는 경계 검사가 있어야 구조가 유지된다.
- 과거 동결 manifest의 `models/...` 문자열은 역사적 provenance이므로 원본을
  고치지 않았다. 대신 그 manifest를 검증하는 좁은 lineage resolver만 canonical
  resource path와 연결했다. 과거 경로 보존과 신규 호환 폴더 유지가 같은 요구는 아니다.
- 이번 변경은 저장 위치와 재현성 계약만 바꾼다. FM4 승인, confirmatory target,
  임상·PNI 진단, encoder 우월성, scanner/stain robustness 또는 H2 질병예측을
  추가로 허용하지 않는다.

**산출물**

- `infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md` (v2.0)
- `infrastructure/docs/repository/ROOT_DIRECTORY_REGISTRY.csv`
- `resources/RESOURCE_OWNERSHIP.csv`
- `infrastructure/migrations/2026-08-12-project-separation/ROOT_MIGRATION_MAP.csv`
- `.../post_root_normalization_file_inventory.csv`
- `.../post_root_normalization_project_classification.csv`
- `.../post_root_normalization_unresolved_files.csv`
- `infrastructure/scripts/validate_project_boundaries.py`
- `infrastructure/migrations/2026-08-12-project-separation/ORG_MIGRATION_REPORT.md`

**다음 진입 조건**

구조 정규화는 과학 마일스톤과 독립적으로 완료되었다. 정량화 연구는 기존 claim
ceiling을 유지한 채 FM4 entry packet의 범위 검토·승인으로 진행한다. 이후 각 FM
마일스톤 종료 시 본 문서에 수행·결과·배운 점·제한·산출물을 계속 누적한다.

### 21.8 ORG-M6 문서·코드 파일 거버넌스 기준선 완료 — 2026-08-12

**수행·결과**

- 폴더 위치뿐 아니라 저장소가 관리하는 Markdown, Python, shell, web asset,
  설정·표·manifest 등 622개 파일을 전수 감사했다. 모든 파일에 owner, file class,
  lifecycle, provenance role, naming/metadata status, 크기와 SHA-256을 부여했으며
  미분류·명명 위반·필수 metadata 위반은 각각 0개였다.
- active/new 문서에는 lowercase kebab-case, Python·shell에는 lower snake_case를
  기본으로 하고, design/plan에는 날짜·명시적 suffix·YAML metadata를 의무화했다.
  네 개의 기존 승인 design은 본문을 변경하지 않고 추적용 metadata header만 추가했다.
- 432개 exception 적용 파일은 자유 면제가 아니라 P0/FM 동결 bundle, 생성 evidence,
  논문 submission contract, legacy code/doc 같은 안정 경로 집합이다. 특히 biomarker
  `code/legacy/`의 85개 script와 `docs/study_design/`의 10개 기록은 기준선 이후 신규
  파일 생성을 자동 차단한다.
- 세 프로젝트의 `code/`·`docs/`와 biomarker `paper/`에 index README를 두어 active,
  frozen, generated, legacy 위치와 신규 파일의 목적지를 명시했다.
- file-governance auditor를 repository boundary validator와 integration test에 연결해,
  이후 경계 검사를 실행하면 파일 소유·유형·수명주기·명명·metadata도 함께 검사한다.

**배운 점과 제한**

- 규칙을 기존 파일에 일괄 rename으로 소급 적용하면 frozen manifest, clinician handoff,
  논문 lineage가 끊길 수 있다. 따라서 기존 경로는 hash 기준선과 좁은 예외로 보존하고,
  규칙은 신규·active 파일에 강제하는 방식이 재현성과 정돈을 동시에 지킨다.
- `legacy`는 삭제 대상이라는 뜻이 아니라 기본 실행 경로가 아닌 provenance 보존면을
  뜻한다. 새 기능은 active code와 test로 추출하되, 원본 역사 경로는 별도 이관 감사
  없이 변경하지 않는다.
- 이 마일스톤은 문서·코드 관리 계약만 확립했다. 의료 정량지표 수, H1/H2 estimand,
  모델 성능, FM4 승인 상태 또는 기존 과학적 claim ceiling은 바꾸지 않는다.

**산출물**

- `infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md`
- `infrastructure/docs/repository/FILE_TYPE_REGISTRY.csv`
- `infrastructure/docs/repository/FILE_GOVERNANCE_EXCEPTIONS.csv`
- `infrastructure/scripts/audit_file_governance.py`
- `infrastructure/tests/test_file_governance.py`
- `infrastructure/migrations/2026-08-12-file-governance/FILE_GOVERNANCE_BASELINE.csv`
- `infrastructure/migrations/2026-08-12-file-governance/file-governance-report.md`
- 세 프로젝트의 `code/README.md`, `docs/README.md` 및 biomarker `paper/README.md`

**다음 진입 조건**

파일 거버넌스는 완료되었으며 별도 연구 승인을 요구하지 않는다. 새 파일 생성 또는
이동 후 auditor와 boundary validator를 통과시키는 것을 상시 조건으로 유지한다.
정량화 연구의 다음 과학적 단계는 기존 계획대로 FM4 entry packet의 현재 evidence
snapshot과 descriptive-only 범위를 검토한 뒤 concept benchmark를 실행하는 것이다.

### 21.9 ORG-M7 파일 명명 Codex 적용 완료 — 2026-08-12

**수행·결과**

- 위치·유형 규칙과 분리된 `File Naming Codex`를 제정해 문서, 설계·계획, 보고서,
  Python, shell, test, web asset, 구조화 record와 figure의 표준 template을 정의했다.
- `copy`, `latest`, `new`, `temp`, `final2` 같은 편집상태 이름을 금지하고, 언어 suffix,
  날짜·milestone ID, version 사용, fixed contract 판정과 rename 절차를 명문화했다.
- 안전하게 이동 가능한 active 문서 4개를 실제 canonical basename으로 바꾸고 active
  참조를 함께 수정했다. old/new path, 변경 전후 SHA-256, 내용·참조 처리 방식은
  `file-rename-map.csv`에 기록했다.
- 전체 624개 관리 파일 중 551개는 canonical naming rule을 직접 통과하고, 73개만
  baseline-backed fixed contract로 남는다. 미분류와 naming violation은 0개다.
- 기존 exception directory 안에서도 새 파일은 자동 면제되지 않는다. canonical
  이름이면 통과하고, 비표준 이름이면 baseline에 있지 않는 한 실패하도록 auditor와
  회귀시험을 강화했다.
- 최종 검증은 infrastructure 5/5, PNI 37/37, 정량 30/30, 공통 metric package
  14/14, rename 영향권의 paper artifact 34/34와 package 39/39가 통과했다. Manuscript
  contract는 53/54가 통과했으며 유일한 실패는 앞서 확인된 현재 NRF/GNU Funding
  선언과 과거 ICT 문구를 요구하는 시험의 불일치로, 이름 변경과 무관하다. 관리
  포털도 호스트 `127.0.0.1:8011`에서 응답을 확인했다.

**배운 점과 제한**

- 일관성은 모든 옛 파일을 강제로 소문자화하는 것이 아니라, 새 이름에는 한 규칙을
  강제하면서 경로가 evidence인 파일은 명시적 fixed contract로 봉인할 때 얻어진다.
- clean-rerun bundle, clinician handoff, manuscript manifest/build contract, protocol-defined
  milestone output, 사용자 지정 milestone log는 rename 자체가 근거 변경이 될 수 있어
  이번 일괄 rename 대상에서 제외했다. 이 73개 이름은 신규 파일의 선례가 아니다.
- 파일명 migration은 과학적 결과를 바꾸지 않는다. 정량지표 taxonomy, H1/H2 gate,
  FM4 entry 승인과 claim ceiling은 그대로다.

**산출물**

- `infrastructure/docs/repository/FILE_NAMING_CODEX.md`
- `infrastructure/migrations/2026-08-12-file-governance/file-rename-map.csv`
- 갱신된 `infrastructure/scripts/audit_file_governance.py`
- 신규명 강제 회귀시험 `infrastructure/tests/test_file_governance.py`
- 갱신된 root/project `AGENTS.md`, `CLAUDE.md`, `PROJECT_STRUCTURE_CODEX.md`

**다음 진입 조건**

모든 신규 파일은 생성 전 owner·class·lifecycle과 canonical basename을 결정해야 한다.
fixed contract를 새로 추가하려면 rename 불가 사유와 exact path를 검토 가능한 registry에
기록해야 한다. 정량화 연구의 다음 과학 단계는 ORG 작업과 독립적으로 FM4 entry
packet의 descriptive-only 범위 검토 후 진행한다.

### 21.10 ORG-M8 프로젝트 진행순서 인덱스 완료 — 2026-08-12

**수행·결과**

- 세 프로젝트 루트에 정렬상 가장 먼저 나타나는 `00-project-sequence/`를 추가했다.
  각 `README.md`는 `00`부터 시작하는 단계 번호, 단계명, 현재 상태, canonical
  폴더·문서 링크, 완료 또는 다음 진입 기준을 한 표로 제공한다.
- PNI 프로젝트는 목적·설계 → 후보 생성 → frozen audit → morphology rereview →
  contour review → 공간 정량화·보고 순서로 구성했다.
- 정량 검증 프로젝트는 목적·지표체계 → P0 → FM1 → FM2 → FM3 → FM4 → 추가
  의료지표 → H2 → 보고·논문 순서로 구성했다.
- Biomarker 프로젝트는 목적·설계 → 대상별 분석 → confounder/site/stability →
  claim–evidence 통합 → 원고 생성 → 제출 검증 순서로 구성했다.
- repository boundary validator가 모든 프로젝트의 `00-project-sequence/README.md`를
  필수 구조로 검사하며, root/project `AGENTS.md`는 마일스톤 상태 변경 시 이 순서표도
  함께 갱신하도록 요구한다.

**배운 점과 제한**

- `code/`, `tests/`, `preexperiment/`, `milestones/`, `paper/` 자체에 숫자를 붙이면
  import, 실행 명령, test fixture, manuscript builder와 frozen manifest 경로가 깨진다.
  따라서 물리 경로의 안정성과 사람이 보는 진행순서를 분리하는 것이 안전하다.
- `00-project-sequence/`의 번호는 탐색 순서이지 새로운 과학적 승인 gate가 아니다.
  실제 허용 범위는 각 프로젝트의 승인 design, claim boundary와 milestone evidence가
  계속 결정한다.

**산출물**

- `projects/precise_pni_candidate_triage/00-project-sequence/README.md`
- `projects/quantitative_foundation_model_validation/00-project-sequence/README.md`
- `projects/prostate_biomarker_validation/00-project-sequence/README.md`
- 갱신된 `PROJECT_STRUCTURE_CODEX.md`, `FILE_NAMING_CODEX.md`, root/project
  `AGENTS.md`, `CLAUDE.md`, repository boundary validator

**다음 진입 조건**

새 연구 단계를 만들 때 먼저 해당 프로젝트의 순서표에 번호·상태·진입 기준을
정의하고, 산출물은 기존 canonical 폴더에 배치한다. 정량 검증의 다음 과학적 단계는
순서표의 06번 FM4 concept benchmark이며, descriptive-only 범위 승인이 필요하다.

### 21.11 FM4 승인 범위 concept benchmark 완료 — 2026-08-14

**수행·결과**

- 연구책임자 Jin Hyun Kim이 evidence snapshot
  `6616e0b18c44c8f4a34746b952e1ea36acd656b264dc6e82d4bc8e9aa3d91ca6`에 대해
  `tumor_fraction × CONCH/Virchow × shared 394.24 µm`의 exploratory/descriptive
  H1 범위를 승인·확정했다.
- FM2/FM3의 1,218개 paired tile, 25 subjects, 다섯 개 subject-grouped fold와 두
  embedding hash를 변경하지 않고 동일 ridge family와 inner tuning budget으로 분석했다.
- 1차 subject-mean OOF Spearman은 CONCH 0.9491 (95% subject-bootstrap CI
  0.8536–0.9777), Virchow 0.9460 (0.8289–0.9857)이었다. 두 값 모두 각 grouped-null
  p95를 넘었고 2개 encoder family의 BH q는 각각 0.0004998이었다.
- subject-mean Spearman의 paired Δ(CONCH−Virchow)는 0.0031 (95% CI
  -0.0790–0.0753)이었다. 이는 기술적 paired contrast이며 encoder 우월성 검정으로
  사용하지 않는다.
- 보조 fixed rank-64 PCA sensitivity의 subject-mean Spearman은 CONCH 0.9429,
  Virchow 0.9112로 양의 방향을 유지했다. 이 sensitivity는 1차 gate를 변경하지 않는다.
- canonical 실행과 독립 임시 디렉터리 clean rerun에서 11개 결정적 산출물이 11/11
  byte hash 일치했다.

**배운 점과 제한**

- 두 frozen representation 모두 이 내부 코호트에서 `tumor_fraction` 정보를 복원할
  수 있지만, 이는 정보의 decodability에 대한 H1 근거일 뿐 질병예측에서의 기능적
  사용을 뜻하지 않는다.
- 독립 반복 측정·ICC가 없고 표본이 25 subjects뿐이므로 measurement-validity 또는
  confirmatory target 주장은 불가능하다. 두 encoder의 1차 paired 차이 CI도 0을 포함한다.
- 질병예측/H2, 임상·whole-slide PNI, scanner/stain robustness, 외부 transport 및
  encoder 우월성은 계속 금지한다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm4_concept_benchmark/run_fm4_benchmark.py`
- `.../outputs/fm4-concept-benchmark-report.md`
- `.../outputs/fm4_oof_predictions.csv`
- `.../outputs/fm4_subject_predictions.csv`
- `.../outputs/fm4_summary.csv`
- `.../outputs/fm4_paired_deltas.csv`
- `.../outputs/fm4_permutation_null.csv`
- `.../outputs/fm4_bootstrap_replicates.csv`
- `.../outputs/fm4_fold_diagnostics.csv`
- `.../outputs/fm4_capacity_oof_predictions.csv`
- `.../outputs/fm4_capacity_sensitivity.csv`
- `.../outputs/fm4_claim_evidence.csv`
- `.../outputs/fm4_clean_rerun_comparison.csv`
- `.../outputs/benchmark_run_config.json`

**다음 진입 조건**

FM5는 P0-G7의 `Amber` 범위 안에서만 진입한다. paired representation similarity,
prediction agreement와 discordance를 기술할 수 있으나, scanner/stain metadata가 없고
단일 descriptive target뿐이므로 robustness 또는 encoder 우월성을 주장하지 않는다.
FM5 분석 family와 paired uncertainty, source table 및 금지 해석을 결과 실행 전에
고정한다. 추가 의료지표와 H2는 각각 반복성 있는 독립 truth와 독립 metric–endpoint,
충분한 subjects/events 및 외부 검증이 확보될 때까지 잠근다.

### 21.12 FM5 Amber 범위 entry packet 고정 — 2026-08-14

**수행·결과**

- FM4 승인 manifest, FM2/FM3 source hash, FM4 등록 output hash와 11/11 clean-rerun
  일치를 다시 검증했다.
- P0-G7 `Amber`, 연구책임자 P0-G8 `Conditional Go`, P0-G9 clean-rerun handoff와
  FM4의 동일 model–target–FOV 승인을 대조했다. FM5의 추가 진입 조건은 paired premise와
  결과 전 analysis family 고정이며 별도 재승인 문구는 없음을 확인했다.
- 동일 1,218 paired tiles, 25 subjects, 다섯 subject-grouped folds와 shared
  394.24 µm `tumor_fraction`만 대상으로 하는 FM5 entry packet을 고정했다.
- primary descriptive family는 subject OOF prediction agreement, residual agreement,
  paired absolute-error effect와 subject-mean linear CKA다. 2,000회 paired subject
  bootstrap을 사용하고 undefined replicate를 보존한다.
- multiplicity는 `descriptive_only_no_p_or_q_values`로 잠갔다. discordance는 각
  encoder의 subject prediction median을 사용한 `concordant_high`, `concordant_low`,
  `conch_only`, `virchow_only` 기술적 rank stratum으로 정의했다.
- 분석 entry point가 기존 G8/G9와 FM4 승인 manifest, entry source/output hash를 모두
  검증한 뒤에만 계산을 시작하도록 했다. 포털에는 이 기존 승인 근거와 FM5 결과 링크를
  표시한다.

**배운 점과 제한**

- FM4에서 두 encoder가 H1 gate를 통과했다는 사실만으로 범위를 넓힐 수는 없지만,
  기존 G8/G9와 FM4 승인은 entry packet에 고정된 동일 조합의 Amber descriptive FM5를
  포함한다. 추가 승인 기록을 임의로 요구하거나 생성하지 않는다.
- paired CI는 정밀도 기술이지 우월성 검정이 아니다. 단일 descriptive target의
  discordance는 모델특이 생물학 또는 보편적 encoder 차이로 일반화할 수 없다.
- scanner/stain metadata, 외부 cohort, 독립 metric–endpoint와 추가 반복측정 근거가
  없으므로 robustness, external transport, H2/질병예측과 추가 의료지표는 잠금 상태다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/run_fm5_preparation.py`
- `projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/run_fm5_comparison.py`
- `projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/outputs/fm5-entry-packet.md`
- `.../fm5_analysis_family.csv`
- `.../fm5_source_manifest.csv`
- `.../fm5_discordance_definition.csv`
- `.../fm5_entry_checklist.csv`
- `.../fm5_entry_run_config.json`

**다음 진입 조건**

기존 G8/G9·FM4 승인 manifest가 current source hash와 일치하고 FM5 entry packet의
estimand, paired uncertainty, multiplicity, discordance와 중단 기준이 고정되면 실행한다.

### 21.13 FM5 Amber 범위 cross-model comparison 완료 — 2026-08-14

**수행·결과**

- 동일 FM2/FM3의 1,218 paired tiles, 25 subjects, shared 394.24 µm FOV와 FM4 OOF
  prediction만 사용했다.
- subject-mean OOF prediction agreement Spearman은 0.9423 (95% paired
  subject-bootstrap CI 0.8265–0.9798)이었다.
- subject residual agreement Spearman은 0.5200 (0.1842–0.7453)이었다.
- subject mean absolute-error paired delta(CONCH−Virchow)는 0.002257
  (-0.010018–0.017356)로 CI가 0을 포함했다.
- centered linear CKA는 subject mean 0.7647 (0.6861–0.9084), tile point estimate
  0.5563이었다. P0-M7 source 값과 재계산 값의 절대차는 두 단위 모두
  `2.22e-16`으로 사전 tolerance `1e-12` 안이었다.
- 기술적 rank stratum은 concordant-high 12, concordant-low 11, CONCH-only 1,
  Virchow-only 1 subject였다. 이는 모델특이 생물학 또는 correctness 분류가 아니다.
- 모든 primary/secondary bootstrap은 2,000/2,000 valid, undefined 0이었다.
- 첫 실행은 P0-M7 source table의 기존 열 이름을 잘못 참조해 결과 파일 쓰기 전에
  중단됐다. 실제 schema로 audit lookup을 수정하고 entry code hash를 다시 고정한 뒤
  처음부터 재실행했다.
- canonical 실행과 별도 프로세스·임시 출력 디렉터리 clean rerun에서 결정적 산출물
  9/9가 byte hash 일치했다.

**배운 점과 제한**

- 두 encoder의 subject-level tumor-fraction OOF prediction은 높은 순위 일치를 보였지만
  residual agreement는 더 낮아 공통 신호와 모델별 오차 성분이 함께 존재한다.
- paired absolute-error delta CI가 0을 포함하고 분석 자체가 descriptive-only이므로
  encoder 우월성 근거가 아니다.
- 단일 T2 descriptive target과 25 subjects만으로 일반적 모델특이 concept,
  scanner/stain robustness, external transport 또는 질병예측/H2를 주장할 수 없다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/outputs/fm5-cross-model-comparison-report.md`
- `.../fm5_subject_comparison.csv`
- `.../fm5_tile_comparison.csv`
- `.../fm5_agreement_summary.csv`
- `.../fm5_representation_similarity.csv`
- `.../fm5_bootstrap_replicates.csv`
- `.../fm5_discordance_manifest.csv`
- `.../fm5_reproducibility_audit.csv`
- `.../fm5_claim_evidence.csv`
- `.../fm5_clean_rerun_comparison.csv`
- `.../fm5_run_config.json`

**다음 진입 조건**

FM6는 현재 실행 가능한 독립 metric–endpoint pair가 없으므로 잠금 상태다. 단일 다음
작업은 우선 후보인 ISUP grade group–biochemical recurrence의 subject linkage, 사건 수,
치료 공변량과 외부 recurrence cohort 가용성을 source manifest 수준에서 감사하는 것이다.

### 21.14 핵심 목표와 하위 실행 문서 동기화 — 2026-08-14

**수행·결과**

- 상위 연구계획 버전 0.2의 최상위 질문을 본 마일스톤 버전 0.3과 하위 실행 추적표에
  동기화했다.
- 실행 증거 사슬을 `개별 복원성 → 조건부 고유정보·포함관계 → joint completeness →
  기능적 활용 → 표현·판단 residual → 명시적 지표화 → 외부·생물학적 검증`으로 고정했다.
- 판단 residual \(R^{score}\)과 표현 residual \(R^{repr}\)을 구분하고 FM6–FM9의 진입조건,
  산출물과 완료기준에 각각 연결했다.

**범위와 제한**

- 이 개정은 연구 방향과 향후 gate를 명료화한 문서화 작업이다. 이미 완료된 FM4–FM5를
  복수지표 완전성, H2 또는 residual marker discovery 완료로 소급 해석하지 않는다.
- 현재 허용 범위는 25 subjects, 1,218 paired tiles, shared 394.24 µm
  `tumor_fraction`의 내부 descriptive H1과 승인된 FM5 비교에 한정된다.
- 추가 의료지표, 질병예측/H2, 외부 transport와 신규 마커 주장은 해당 단계의 독립성,
  측정 반복성, 표본·사건 수, 외부 cohort 및 blinded/orthogonal validation gate 전까지
  잠금 상태다.

**다음 진입 조건**

단일 다음 작업은 변경하지 않는다. ISUP grade group–biochemical recurrence 후보의
subject linkage, 사건 수, endpoint 독립성, 치료 공변량과 외부 recurrence cohort를 source
manifest 수준에서 감사한 뒤 FM6 protocol 진입 가능성을 판정한다.

### 21.15 FM6 ISUP–BCR 진입 적격성 감사 완료 — 2026-08-14

**수행·결과**

- `QFMV-FM6-ENTRY-AUDIT-2026-08-14-001`로 FM1의 H2-001 후보인 ISUP grade
  group–biochemical recurrence 조합을 감사했다. 이 조합의 정의상 독립성은
  `independent/noncircular`로 유지했다.
- LEOPARD 공식·로컬 training label은 508명/87 BCR events와 508 WSI를 제공하지만,
  같은 환자의 ISUP/Gleason 및 치료 공변량이 없어 외부 semantic validation set으로는
  불완전하다.
- 현재 GDC clinical field를 다시 조회한 결과 TCGA-PRAD 500명 모두에서 보고 ISUP 또는
  Gleason pattern/score 기반 고정식 ISUP 도출이 가능했다. 명시적 biochemical recurrence
  status/time, WSI와 ISUP가 연결되는 감사용 개발 후보는 392명/80 events였고, 이 중
  방사선·약물치료가 모두 documented인 부분집합은 308명/64 events였다.
- 기존 로컬 TCGA `disease_response=WT-With Tumor` endpoint 493명/111 events와
  `tumor-free → with-tumor` sensitivity endpoint 393명/11 events는 true BCR과 구분했다.
  두 endpoint를 이번 FM6 BCR estimand에 사용하거나 섞지 않았다.
- 다른 프로젝트의 생성 산출물은 입력으로 사용하지 않았다. QFM 소유 FM1 registry,
  repository dataset manifest, 공유 원천자료와 이번 공식 GDC snapshot만 감사했으며 모든
  source path·byte size·SHA-256을 저장했다.

**판정과 제한**

- 판정은 `BLOCKED_NO_COMPLETE_DEVELOPMENT_AND_EXTERNAL_PAIR`이다. TCGA-PRAD는
  개발 후보가 되었지만 현재 dataset manifest는 QFM 사용을 허가하지 않으며, endpoint
  inclusion/exclusion과 최소 사건 수·power 기준도 사전 고정되지 않았다.
- 동일 ISUP/Gleason metric truth, PSA 기반 true-BCR status/time 및 치료 공변량을 함께
  제공하는 독립 외부 cohort가 없다. LEOPARD는 true-BCR outcome 외부셋 후보일 뿐 현재
  상태로는 metric의 semantic transport를 검증할 수 없다.
- 이번 작업은 source-level eligibility audit이다. disease head 학습, targeted erasure,
  기능적 활용(H2), 외부 transport 또는 신규 residual marker 분석을 수행하지 않았다.
- claim ceiling은 shared 394.24 µm `tumor_fraction`의 내부 descriptive H1 및 승인된 FM5
  비교로 유지한다. 감사 표본 수를 질병예측 성능이나 임상 타당성 근거로 해석하지 않는다.

**산출물**

- `projects/quantitative_foundation_model_validation/milestones/fm6_entry_audit/run_fm6_entry_audit.py`
- `.../outputs/fm6-entry-audit-report.md`
- `.../outputs/fm6_cohort_eligibility.csv`
- `.../outputs/fm6_gdc_field_completeness.csv`
- `.../outputs/fm6_source_manifest.csv`
- `.../outputs/fm6_run_config.json`

**다음 단일 작업**

TCGA-PRAD current-GDC biochemical recurrence snapshot을 QFM용 hash-locked development
source package로 고정하고, endpoint inclusion/exclusion 및 최소 사건/power 기준을 결과 확인
전에 등록한다. 이 개발 subprotocol이 준비되더라도 강한 H2와 targeted erasure는 동일 metric
truth·치료 공변량을 가진 독립 외부 cohort가 등록되기 전까지 잠근다. 복수지표 completeness
축도 추가 독립 지표의 측정 반복성 gate 전까지 별도로 잠근다.

### 21.16 CHIMERA Task 1 외부 source 확보·semantic QC 등록 — 2026-08-15

**수행·결과**

- CHIMERA Task 1 `v2/task1`에서 임상 JSON 95개, prostatectomy H&E WSI 190장과
  foreground/background tissue mask 190장을 QFM local-data root에 확보했다. 영상·mask
  payload는 404,568,807,346 bytes다.
- 475개 source object, 총 404,568,845,344 bytes를 acquisition inventory의 SHA-256과
  전수 재대조해 불일치 0건을 확인했다. WSI/mask 380개 TIFF header와 최하위 pyramid
  decode도 전수 통과했고 빈 mask는 0개였다.
- 임상–WSI subject set은 95/95로 동일하고 WSI–mask는 190/190 pair다. 환자당 WSI는
  1–12장으로 가변적이므로 patient-level aggregation을 결과 전에 고정하도록 잠갔다.
- 공식 BCR reference-standard 시간 단위가 months임을 확인해 잘못된 `_years` 열을
  `_months`로 정정했다. 수술 후 PSA `>=0.1 ug/L` 정의를 명시적으로 등록했다.
- reported ISUP와 primary/secondary Gleason 표준 Grade Group 매핑은 92/95 concordant,
  3/95 source-discordant였다. 원본을 수정하지 않고 primary semantic universe 92명/27
  events와 all-subject sensitivity를 사전 고정했다.
- 연령, PSA, pT, margin, lymph-node, capsular, seminal-vesicle, lymphovascular와 earlier
  therapy를 정규화표에 보존하고 `x`, `unknown`, `missing_key`, `blank`, `null`을 음성으로
  바꾸지 않도록 수정했다.
- 실제 WSI TIFF tag는 190장 모두 0.485069 micrometre/pixel이었다. 명목 0.5를
  hard-code하지 않고 shared 394.24 micrometre FOV의 resampling/crop hash를 추출 전에
  고정하도록 protocol에 기록했다.

**판정과 제한**

- 외부 cohort는 `independent_external_isup_bcr_candidate_qc_hold`로 등록했다. source가
  확보됐다는 사실은 external transport, H2 또는 residual marker 분석을 해제하지 않는다.
- CHIMERA mask는 tumor mask가 아니므로 독립 tumor-region 규칙 없이는 ISUP H1/H2를
  실행하지 않는다. 수술 후 adjuvant/salvage 치료도 완전하지 않다.
- CHIMERA 27 events는 현재 feasibility/exploratory 규모다. development-only effect와
  censoring·matched-control 구조를 반영한 사전 simulation이 80% power gate를 통과하지
  않으면 strong external H2를 금지한다.
- 공식 publication embargo가 유지되므로 raw/patient-level 자료와 outcome-derived summary,
  향후 모델 결과는 포털에서 `never_serve`다. acquisition 보고서만 `project_internal`로
  분류한다. draft repository portal의 legacy allowlist에는 추가하지 않았다.
- 이번 단계에서는 CONCH/Virchow embedding, disease head, targeted erasure, 외부 outcome
  모델 또는 residual marker 분석을 수행하지 않았다. claim ceiling은 변하지 않는다.

**산출물**

- `resources/data/manifests/chimera_task1.yaml`
- `projects/quantitative_foundation_model_validation/docs/protocols/fm6-isup-bcr-source-and-power-protocol-ko.md`
- `projects/quantitative_foundation_model_validation/milestones/fm6_external_cohort_acquisition/run_fm6_external_cohort_acquisition.py`
- `.../outputs/fm6-external-cohort-acquisition-report.md`
- `.../outputs/fm6_external_cohort_eligibility.csv`
- `.../outputs/fm6_chimera_clinical_qc_summary.csv`
- `.../outputs/fm6_chimera_slide_count_summary.csv`
- `.../outputs/fm6_external_source_manifest.csv`
- `.../outputs/fm6_external_cohort_run_config.json`

**다음 단일 작업**

TCGA-PRAD current-GDC biochemical recurrence snapshot을 QFM 소유 hash-locked development
source package로 고정하고, CHIMERA와의 endpoint harmonization, disease-head 최소 유효성과
power simulation 입력을 확정한다. 이 작업이 끝나도 tumor-region·semantic·embargo와
power gate가 남으면 H2 실행은 계속 잠근다.

### 21.17 TCGA-PRAD current-GDC 개발 source package 고정 — 2026-08-15

**수행·결과**

- `QFMV-FM6-DEVELOPMENT-SOURCE-2026-08-15-001`로 current-GDC clinical snapshot,
  diagnostic WSI file UUID/size manifest, endpoint normalizer와 QFM patient-level 정규화표를
  하나의 source hash chain으로 고정했다.
- WSI·ISUP·명시적 biochemical recurrence status/time을 연결한 개발 universe는
  392명/80 events이며, 방사선·약물치료가 모두 documented인 부분집합은
  308명/64 events다.
- 이 universe의 remote-locked WSI는 437장, 환자당 1–9장이다. 현재 모든 해당 slide가
  local인 환자는 268명/45 events이고, local slide는 294/437장이다. 남은 143장은
  165,961,228,291 bytes다.
- TCGA dataset manifest를 공유 immutable asset으로 명시해 QFM 사용 프로젝트를 등록했다.
  환자별 임상·slide 표는 ignored QFM local-data에 두고 `never_serve`로 고정했다.
- TCGA event는 GDC에 biochemical recurrence type과 recurrence day가 명시된 경우이고,
  CHIMERA event는 수술 후 PSA `>=0.1 ug/L`다. days/months 단위 변환은 가능하지만 PSA
  threshold와 censoring 관찰과정의 동등성은 입증되지 않아 patient-level pooling을 금지했다.
- CHIMERA primary semantic universe 92명/27 events와 TCGA 392명/80 events를 power
  simulation 입력표에 등록했지만, locked disease-head 최소 유효성과 `delta_use` effect
  distribution이 없으므로 simulation은 `NOT_RUN_EFFECT_INPUT_UNAVAILABLE`로 보존했다.

**판정과 제한**

- 판정은 `DEVELOPMENT_SOURCE_HASH_LOCKED_ACQUISITION_AND_HARMONIZATION_HOLD_H2_LOCKED`다.
  source package 고정은 완료됐지만 development analysis-ready 또는 H2 unlock은 아니다.
- 미확보 WSI, tumor-region, patient aggregation, scanner/stain metadata와 TCGA–CHIMERA
  endpoint equivalence가 남았다. 이를 무시하고 268명 local subset만 선택하면 기존
  ERG-label 가용성에 따른 selection bias가 생길 수 있으므로 primary development cohort로
  사용하지 않는다.
- 이 단계에서는 embedding, probe, disease head, targeted erasure, outcome 성능 또는
  residual marker 분석을 수행하지 않았고 claim ceiling은 변하지 않는다.

**산출물**

- `resources/data/manifests/tcga_prad.yaml`
- `projects/quantitative_foundation_model_validation/milestones/fm6_development_source_package/run_fm6_development_source_package.py`
- `.../outputs/fm6-development-source-package-report.md`
- `.../outputs/fm6_tcga_development_eligibility.csv`
- `.../outputs/fm6_tcga_development_source_manifest.csv`
- `.../outputs/fm6_tcga_chimera_endpoint_harmonization.csv`
- `.../outputs/fm6_power_simulation_input_status.csv`
- `.../outputs/fm6_development_source_run_config.json`

**다음 단일 작업**

TCGA 개발 universe에 필요한 미확보 WSI 143장(165,961,228,291 bytes)을 file UUID·size와
대조해 확보한다. 이어지는 embedding 전 gate에서 outcome을 보지 않고 tumor-region,
환자당 가변 slide aggregation, 물리 FOV와 scanner/stain missingness 규칙을 고정한다.
그 전에는 현재 local 268명 subset으로 disease head를 학습하지 않는다.

### 21.18 TCGA-PRAD WSI acquisition·기술 QC·환자 집계 gate 완료 — 2026-08-15

**수행·결과**

- 개발 universe에 누락됐던 143장/165,961,228,291 bytes를 GDC file UUID로 재개 가능한
  방식으로 확보했다. 최종 437장/422,597,608,423 bytes의 local size가 remote lock과
  일치하며, GDC MD5를 두 번의 독립 실행에서 437/437 PASS로 확인했다.
- `QFMV-FM6-TCGA-WSI-QC-2026-08-15-001`로 outcome을 읽지 않고 TIFF/SVS header,
  lowest-pyramid thumbnail과 MPP를 검사했다. 세 항목 모두 437/437 PASS이고 AppMag는
  437장 모두 40이다. 12개 실측 MPP 값, 3개 압축 형식, 3/4 pyramid level과 scanner-ID
  missing 23장을 기술적 교란층으로 보존했다.
- `QFMV-FM6-TCGA-FOLDS-2026-08-15-001`로 같은 환자의 모든 slide를 한 fold에 둔 5-fold
  manifest를 고정했다. fold 크기는 79/79/78/78/78명, event는 각 16건, 치료 documented
  수는 62/62/62/61/61명이며 exact ISUP 분포의 fold 간 최대 차이는 2명이다.
- 394.24 micrometre source FOV를 slide별 MPP로 변환하고, outcome-blind tissue 후보에서
  slide 내 tile equal mean → 환자 내 slide equal mean → 환자 한 행의 primary 집계를
  사전 고정했다. 가변 slide 수가 환자 가중치가 되지 않도록 환자 총 가중치를 1로 둔다.
- TCGA에는 독립 tumor mask가 없고 CHIMERA mask도 tissue mask이므로, weak-attention 또는
  ISUP/BCR로 선택한 tile을 독립 tumor truth로 재사용하지 않는 경계를 유지했다.

**판정과 제한**

- 판정은 `DEVELOPMENT_SOURCE_PAYLOAD_VERIFIED_PREPROCESSING_GATE_H2_LOCKED`다. WSI
  acquisition, file integrity, 기술 QC, 환자 split, 물리 FOV와 primary aggregation gate는
  닫혔지만 development analysis-ready 또는 H2 unlock은 아니다.
- TCGA–CHIMERA BCR threshold/censoring equivalence, 독립 tumor-region 처리의 검증,
  locked disease-head 최소 유효성, development-only effect 기반 power와 CHIMERA embargo
  gate가 남는다. 따라서 disease head, targeted erasure, external outcome, residual marker
  탐색은 계속 잠근다.
- 이 단계는 본 프로젝트 목적에 직접 부합한다. 두 encoder에 동일 환자·동일 물리 FOV와
  동일 집계를 강제해 사람이 사용하는 ISUP와 모델 판단의 관계를 공정하게 시험할 기반을
  만들되, 아직 모델이 ISUP를 기능적으로 사용한다고 주장하지 않는다.

**산출물**

- `projects/quantitative_foundation_model_validation/docs/protocols/fm6-tcga-wsi-preprocessing-and-aggregation-protocol-ko.md`
- `projects/quantitative_foundation_model_validation/milestones/fm6_development_source_package/audit_fm6_tcga_wsi_headers.py`
- `.../prepare_fm6_tcga_subject_folds.py`
- `.../outputs/fm6-tcga-wsi-qc-report.md`
- `.../outputs/fm6_tcga_wsi_header_qc_summary.csv`
- `.../outputs/fm6_tcga_wsi_technical_distribution.csv`
- `.../outputs/fm6_tcga_outer_fold_balance.csv`
- `.../outputs/fm6_tcga_wsi_qc_run_config.json`
- `.../outputs/fm6_tcga_outer_fold_run_config.json`

**다음 단일 작업**

독립 tumor-region 처리 후보를 source label과 결과변수 없이 사전 지정하고, annotation 또는
검증된 고정 detector에서 sensitivity/specificity·실패율·scanner별 성능을 감사한다. 동시에
whole-tissue BCR disease-head를 최소 유효성·power 효과량 산출용으로 허용할지 별도 protocol과
승인 snapshot으로 판정한다. 이 gate 전에는 ISUP H1/subspace/targeted erasure를 실행하지 않는다.

### 21.19 Evidence-qualified alignment 원고 1차 전면 재편집 — 2026-08-15

**수행·결과**

- 연구책임자가 `임상 지표의 복원 정확성·외부 재현성을 통한 사람–AI 공통
  해석 좌표의 가능성과 한계` 규명을 원고 핵심 기조로 승인했다.
- PBV가 소유한 claim, endpoint, numeric QA, morphology·molecular·outcome·stability source
  15개를 path·bytes·SHA-256로 고정했다. patient-level 자료, embedding, 기존 PDF·PNG·TeX
  table은 복사하지 않았다.
- Main을 `recoverability/functional-use 분리 → morphology transport → molecular conditionality
  → endpoint-conditioned outcome → representation sensitivity → 최종 alignment map`으로 재작성했다.
- Supplementary를 cohort/unit, encoder/fold, estimand/null, primary estimate, external transport,
  conditional/site, full grid, endpoint, multiplicity, claim/numeric lineage, reproducibility의 12개 블록으로
  재작성했다.
- 신규 builder가 source hash 15/15, headline numeric mapping 20/20을 검증하고 main figure 4개,
  Supplementary full-grid figure 1개, main table 1개와 Supplementary table 6개를 새로 생성한다.

**판정과 제한**

- 현재 원고가 직접 보여 주는 것은 임상적으로 해석 가능한 target이 frozen
  representation에서 복원·재현되는지이다. disease-prediction head가 해당 target을
  기능적으로 사용하는지는 실험하지 않았다.
- grade/phenotype은 가장 넓은 transport 근거, PTEN/AR은 조건부 근거, SPOP은 frozen
  primary design에서 부적합, recurrence는 endpoint·reference·representation 조건부로 배치했다.
- 이 editorial workstream은 FM6 진입 gate나 현재 `internal descriptive recoverability` claim
  ceiling을 높이지 않는다.

**산출물**

- `projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer/main.tex`
- `.../supplement.tex`
- `.../provenance/source_evidence_manifest.csv`
- `.../provenance/alignment_target_registry.csv`
- `.../provenance/claim_evidence_matrix.csv`
- `.../provenance/endpoint_hierarchy.csv`
- `.../provenance/numeric_qa_mapping.csv`
- `.../build_alignment_manuscript.py`

**다음 원고 작업**

전 페이지 시각 QA, repository/PBV/QFM 통합 검증과 저자·funding·ethics·journal metadata
확인 후 submission-ready 상태를 판정한다. 기능적 사용 검증은 원고 문장 수정이 아니라
FM6 이후 locked-head/targeted-erasure 실험으로만 진행한다.

### 21.20 FM6 TCGA whole-tissue 내부 개발 pilot 완료 — 2026-08-16

**수행·기술 감사**

- 연구책임자의 실행 승인에 따라 별도
  `fm6-tcga-whole-tissue-internal-development-pilot-protocol-ko.md`를 고정하고,
  독립 tumor-region truth가 없는 상태의 증거 상한을 `internal whole-tissue development`
  로 제한했다.
- TCGA-PRAD 392명/80 BCR events, WSI 437장의 outcome-blind thumbnail tissue 후보에서
  slide당 64개, 총 27,968개의 394.24 µm boundary를 고정했다. ISUP/BCR/치료값은 좌표
  생성에 사용하지 않았다.
- 각 boundary를 448×448 canonical RGB cache로 한 번만 만들고 두 encoder가 공유했다.
  공식 CONCH/Virchow transform과 vectorized transform은 실제 crop에서 bitwise 동일했고,
  64-tile GPU 반복도 bitwise 동일했다.
- 최종 embedding은 CONCH 27,968×512, Virchow 27,968×2,560 float32다. 두 encoder 모두
  nonfinite와 zero-norm 행은 0이고, level-0 crop-hash array SHA-256은 동일하다.
- 분석단위는 환자이며 tile mean → slide equal mean → patient equal mean을 적용했다.
  모든 preprocessing, ridge/PCA-Cox, outer 5-fold, bootstrap과 control 규칙은 결과 전에
  고정했다.

**복원성·질병 head·기능 민감도 결과**

- Whole-tissue ISUP OOF recoverability는 CONCH rho 0.615, MAE 0.876, QWK 0.519;
  Virchow rho 0.658, MAE 0.813, QWK 0.561이었다. Fold-preserving 200 permutation의
  one-sided p는 두 모델 모두 0.005였다.
- Locked-rule 내부 BCR head OOF C-index는 CONCH 0.627 (patient bootstrap 95% CI
  0.553–0.694), Virchow 0.632 (0.564–0.691)로 사전 최소 유효성 하한 0.50을 통과했다.
- Training-fold SVD 고유축 혼합으로 rank 1과 제거분산을 정확히 맞춘 100개 random
  control을 구성했다. 제거분산 비율은 모든 fold/control에서 1.0이고 concept cosine
  중앙값/최대값은 CONCH 0.069/0.307, Virchow 0.044/0.190이었다.
- ISUP-correlated fixed-head C-index 감소는 CONCH 0.041 (paired bootstrap 95% CI
  0.011–0.073), Virchow 0.023 (0.007–0.040)이었다. matched-random p95는 0.009/0.003,
  one-sided p는 두 모델 모두 0.0099였다.
- Refit-after-erasure 감소는 0.014 (CI -0.006–0.035)와 0.010 (-0.003–0.022)로 CI가
  0을 포함했다. 즉 original head가 ISUP-correlated 방향에 민감하지만 제거 후 다른
  표현 정보가 상당 부분 대체 가능하다는 해석이 적절하다.

**다중지표·상보성·교란 감사**

- ISUP 단독 BCR C-index는 0.696이었다. ISUP+AI의 paired 증분은 CONCH -0.000
  (CI -0.039–0.039), Virchow -0.032 (-0.088–0.025)로 0을 포함했다. 따라서 이번
  pilot은 AI의 ISUP 기능 민감도를 지지하지만 이 제한된 비교에서 임상적 증분가치를
  확립하지 못했다. 이는 임상 증분 부재를 충분히 검증한 결과가 아니다.
- 보조 human-understood covariate로 hash-lock된 AGE와 pathologic T stage만 사용했다.
  OOF rho는 age 0.138/0.084, path-T 0.397/0.409였다. ISUP만으로 AI risk OOF R²의
  0.205/0.163을 설명했고 AGE+path-T를 더하면 0.218/0.167로 0.014/0.005만 증가했다.
  이 세 축은 세 개의 독립 병리 metric family가 아니라 탐색적 임상 패널이다.
- 두 encoder의 full risk rho는 0.750, ISUP probe prediction rho는 0.843, erasure
  score-change rho는 0.820이었다. 이는 내부 paired 공통성을 보이지만 external T가 아니다.
- AI risk와 thumbnail tissue fraction의 rho는 0.324/0.341이었다. MPP rho는
  -0.104/-0.119, slide 수 rho는 -0.038/0.050이다. 특히 tissue composition 상관은
  독립 tumor-region 감사 전 residual 신규성 주장을 금지하는 근거다.

**Power·재현성·판정**

- TCGA delta와 bootstrap SD를 27 external events로 event-scale한 계획 근사 power는
  CONCH 0.887, Virchow 0.924로 80%를 넘었다. 이는 CHIMERA model/outcome을 읽지 않은
  planning input이며 endpoint equivalence·embargo를 해제하지 않는다.
- 분석 CSV와 scope-capped report는 clean rerun에서 모두 SHA-256가 일치했다. PDF의
  CreationDate metadata를 제거한 뒤 3개 figure family의 PNG/PDF와 figure manifest도
  clean rerun hash가 모두 일치했다.
- R=`PASS_WHOLE_TISSUE_DEVELOPMENT`, A=`PASS_INTERNAL`,
  U=`PASS_EXPLORATORY_WHOLE_TISSUE`, T=`NOT_TESTED_LOCKED`로 두 encoder를 판정한다.
  독립 tumor-region truth와 external T가 없으므로 strong H2는 `PROHIBITED`다.

**산출물**

- `projects/quantitative_foundation_model_validation/docs/protocols/fm6-tcga-whole-tissue-internal-development-pilot-protocol-ko.md`
- `projects/quantitative_foundation_model_validation/milestones/fm6_internal_development_pilot/run_fm6_tcga_internal_pilot.py`
- `.../analyze_fm6_tcga_internal_pilot.py`
- `.../render_fm6_internal_pilot_figures.py`
- `.../outputs/fm6-tcga-internal-development-pilot-report.md`
- `.../outputs/fm6_tcga_internal_pilot_summary.csv`
- `.../outputs/fm6_tcga_within_encoder_contrasts.csv`
- `.../outputs/fm6_tcga_internal_evidence_chain.csv`
- `.../outputs/fm6_tcga_patient_oof_predictions.csv`
- `.../outputs/fm6_tcga_outer_fold_model_settings.csv`
- `.../outputs/fm6_external_power_planning_approximation.csv`
- `.../outputs/figures/`

**다음 단일 작업**

Outcome·ISUP와 독립인 tumor-region annotation 또는 고정 detector를 선정하고,
sensitivity/specificity·실패율·scanner별 성능을 감사한다. 그 gate를 통과한 뒤에만 같은
27,968 boundary universe와 locked folds/head/control 규칙으로 tumor-restricted R/A/U를
재평가한다. CHIMERA T는 endpoint equivalence, 정식 power, 치료 결손 해석과 publication
embargo가 모두 해제되기 전까지 실행하지 않는다.

### 21.21 FM6 독립 tumor-region detector gate 실행 — 2026-08-16

**선고정 설계와 자료**

- TCGA outcome·ISUP와 CONCH/Virchow 표현을 전혀 사용하지 않는 ImageNet ResNet18
  detector를 선택하고, 결과 확인 전에 SICAPv2 test AUROC 0.90, sensitivity 0.85,
  specificity 0.80, failure 1% 이하를 내부 gate로 고정했다.
- SICAPv2 18,783 image–pixel-mask 쌍을 감사했다. 공식 train 9,959 tiles/124 slides와
  test 2,122/31 사이 slide ID 중복은 0이었다. 394.24 µm 중앙 crop의 tumor fraction
  0.10 이상을 binary target으로, 연속 tumor fraction을 보조 target으로 학습했다.
- 공식 train 안에서만 slide-group development/validation을 나누고 8 epoch 중 validation
  AUROC가 가장 높은 epoch 3과 threshold 0.344998을 고정했다.

**독립 시험 결과와 판정**

- SICAPv2 공식 test에서 AUROC 0.920 (slide bootstrap 95% CI 0.870–0.951), AUPRC 0.898,
  sensitivity 0.928 (0.895–0.957), specificity 0.751 (0.614–0.842), balanced accuracy
  0.840이었다. Fraction Spearman은 0.819, MAE는 0.119, 실패율은 0이었다.
- AUROC와 sensitivity는 통과했으나 specificity가 선고정 0.80에 미달해
  `FAIL_INTERNAL`로 판정했다. Test를 본 뒤 threshold를 바꾸지 않았다.
- PANDA의 provider × benign/cancer 각 10 slides, 총 40 slides에서 394.24 µm patch를
  고정 추출했다. Karolinska는 n=637, AUROC 0.831, sensitivity 0.756, specificity
  0.765로 scanner-proxy gate를 통과했다. Radboud는 n=640, AUROC 0.798,
  sensitivity 0.299, specificity 0.984로 실패했다.
- 결합 판정은 `NARROW_OR_FAIL`이다. Protocol의 중단 규칙에 따라 TCGA tile scoring,
  tumor-restricted 재집계와 H2 분석은 실행하지 않았다. Whole-tissue pilot의 내부 결과는
  유지되지만 tumor-specific claim으로 승격되지 않는다.

**산출물과 다음 진입 조건**

- `docs/protocols/fm6-independent-tumor-region-detector-audit-protocol-ko.md`
- `milestones/fm6_tumor_region_detector_audit/run_fm6_tumor_region_detector_audit.py`
- `milestones/fm6_tumor_region_detector_audit/outputs/fm6-tumor-region-detector-audit-report.md`
- `.../fm6_sicap_detector_test_summary.csv`
- `.../fm6_sicap_detector_test_intervals.csv`
- `.../fm6_panda_detector_scanner_proxy_summary.csv`
- `.../fm6_tumor_region_detector_evidence_gate.csv`

다음 단일 작업은 이번 test에 맞춘 threshold 조정이 아니라, train-only multi-domain
stain/scale augmentation 또는 pixel segmentation detector를 새로 선고정하고 이미 열어 본
SICAP/PANDA와 구별되는 독립 holdout을 확보하는 것이다. 새 detector가 내부와 두
acquisition domain gate를 모두 통과하기 전 TCGA filtering은 계속 잠근다.

### 21.22 FM6 detector train-only 재튜닝과 새 holdout — 2026-08-16

**과적합 방지와 후보 선택**

- 1차 SICAP test와 PANDA 40 slides는 opened development evidence로 격하하고 후보·threshold
  선택에서 제외했다. 기존 40 slides와 겹치지 않는 PANDA provider × benign/cancer 각
  25 slides, 총 100 slides를 pixel/score 열람 전에 잠갔다.
- SICAP 공식 train 9,959 tiles/124 slides의 동일 3-fold StratifiedGroupKFold에서만
  baseline, strong RGB color, HED color, HED+scale 네 후보를 비교했다.
- HED+scale 후보가 pooled OOF AUROC 0.949, sensitivity 0.887, specificity 0.887로 선택됐다.
  OOF threshold 0.417947을 잠근 뒤 전체 SICAP train에서 5 epoch 학습했고 holdout을 보기
  전 checkpoint hash를 저장했다.

**재평가와 독립 holdout 결과**

- 이미 열었던 SICAP test의 비선택적 참고 재평가에서는 AUROC 0.919, sensitivity 0.875,
  specificity 0.810, balanced accuracy 0.842였다. 따라서 사용자가 지적한 specificity는
  0.751에서 0.810으로 개선됐지만 이는 새 독립 test가 아니므로 확증 근거로 승격하지 않는다.
- 새 PANDA holdout은 Karolinska n=1,584에서 AUROC 0.825, sensitivity 0.563,
  specificity 0.943이었다. Radboud n=1,600에서는 AUROC 0.888, sensitivity 0.679,
  specificity 0.913이었다.
- Radboud의 discrimination은 1차 표본보다 좋아졌으나 새 표본이므로 paired 개선으로
  해석하지 않는다. 두 provider 모두 sensitivity 0.75 gate에 미달해
  `FAIL_REMEDIATION_EXTERNAL_HOLDOUT`이다.
- Holdout을 본 뒤 threshold를 낮추지 않았다. TCGA scoring·filtering·tumor-restricted
  R/A/U는 계속 `NOT_RUN`, strong H2는 `PROHIBITED`다.

**산출물과 다음 조건**

- `docs/protocols/fm6-tumor-region-detector-remediation-protocol-ko.md`
- `milestones/fm6_tumor_region_detector_audit/tune_fm6_tumor_region_detector.py`
- `.../outputs/fm6_detector_remediation_cv_summary.csv`
- `.../outputs/fm6_sicap_remediation_opened_test_summary.csv`
- `.../outputs/fm6_panda_remediation_holdout_summary.csv`
- `.../outputs/fm6-tumor-region-detector-remediation-report.md`

다음 진입에는 SICAP-only 학습을 반복하는 대신 최소 두 acquisition domain의 label을
train/calibration에 포함하거나 pixel segmentation·stain normalization을 선고정하고,
PANDA-PLUS/TMAZ 같은 아직 열지 않은 제3 독립 pixel-annotation 자료가 필요하다.

### 21.23 Alignment 원고 FM6 근거 승계·scope lock — 2026-08-16

**연구책임자 결정**

- Remediated detector의 opened SICAP secondary specificity 0.810은 내부 기술 근거로
  수용한다. 다만 새 PANDA holdout의 Karolinska/Radboud sensitivity 0.563/0.679 실패는
  해결되지 않은 independent-domain sensitivity로 main과 Supplement에 명시한다.
- 현재 논문은 known clinical/pathology target의 recoverability·transport·qualification과,
  ISUP에 대한 두 internal BCR head의 scoped functional sensitivity까지만 담는다.
- ISUP-correlated fixed-head erasure effect가 CONCH와 Virchow에서 matched-random control을
  넘은 결과는 `internal exploratory functional sensitivity`로 허용한다. Refit 후 CI가
  zero를 포함하므로 indispensable use, human-equivalent mechanism, tumor-specific 또는
  external functional transport로 승격하지 않는다.
- ISUP+AI 대 ISUP-only 비교는 이 제한된 내부 분석에서 increment를 확립하지 못했을 뿐,
  임상 증분이 없음을 충분히 평가한 연구가 아니다. 원고는 `clinical increment absent`
  대신 `not established in this scoped comparison; comprehensive evaluation not performed`
  로 고정한다.
- Known target 제거 뒤 남는 residual/unknown AI feature의 신규 정량 marker화는 잠재적으로
  중요한 별도 발견이므로 현재 원고에서 제외하고 후속 논문으로 분리한다.

**현재 논문의 최종 claim ceiling**

1. 알려진 임상·병리 축 중 grade/phenotype은 가장 넓은 transport 근거를 제공한다.
2. PTEN·AR·SPOP·recurrence는 target별 conditional/unsupported boundary를 갖는다.
3. ISUP는 두 frozen representation의 internal BCR head에서 반복되는 functional
   sensitivity를 보였으나, 필수적·외부적·종양특이적·임상증분적 사용은 확립되지 않았다.
4. 이 결과는 사람과 AI가 공유하는 정량 좌표가 AI 판단을 감사하는 공통 설명 언어가 될
   가능성을 지지하지만, AI 판단 전체를 설명하거나 clinician outcome을 개선함을 뜻하지 않는다.

**다음 단일 작업**

FM6 네 개 source table을 hash-locked provenance에 승계하고 main·Supplementary·Figure 1,
claim matrix와 numeric QA를 함께 재빌드한다. 이어 수치·의미·시각·governance 회귀검사를
통과시킨 뒤 author-controlled metadata 확인 단계로 넘긴다. Multi-domain detector 개발과
residual marker discovery는 현재 원고를 지연시키지 않는 후속 workstream이다.

### 21.24 FM6 alignment 원고 종결용 locked clean rerun — 2026-08-17

**목적과 범위**

- FM6 whole-tissue ISUP functional-sensitivity 결과가 원고 종결 시점에도 고정 protocol과
  저장된 입력에서 동일하게 재생성되는지 확인한다.
- 이는 새로운 가설·cohort·endpoint·hyperparameter·threshold를 추가하는 실험이 아니다.
  기존 392명/80 BCR events, 437 WSI, 27,968 shared boundaries, 고정 5-fold, 저장된 CONCH와
  Virchow embeddings, 2,000 patient bootstraps, 100 matched-random controls와 20
  label-permuted controls를 그대로 사용한다.
- 영상 재선정이나 encoder 재학습 없이 고정 embedding에서 분석·그림·원고 provenance를
  clean rerun한다. 결과를 보고 설정을 변경하지 않는다.

**태스크와 통과 기준**

- [x] 실행 전 analysis run-config의 nonvolatile output hash 집합을 기준선으로 고정한다.
- [x] `analyze_fm6_tcga_internal_pilot.py`를 고정 환경에서 재실행한다.
- [x] `render_fm6_internal_pilot_figures.py`와 alignment manuscript builder를 재실행한다.
- [x] ISUP recoverability, BCR-head C-index, fixed-head erasure, matched-random 비교,
  refit-after-erasure와 제한적 ISUP-only increment의 수치·방향·interval을 대조한다.
- [x] 두 encoder의 R/A/U/T 판정과 strong-H2 금지 상태가 동일한지 확인한다.
- [x] nonvolatile output hash, source provenance 19개와 manuscript numeric mapping 33개를
  재검증한다.
- [x] QFM tests, PDF reference/overflow, file governance와 project boundary를 감사한다.

**실패·중단 규칙**

- nonvolatile hash 또는 핵심 수치가 불일치하면 원고 handoff를 중단하고 원인을 조사한다.
- 불일치를 해소하기 위해 사후 tuning, endpoint 교체, 환자 제외 또는 claim ceiling 확대를
  허용하지 않는다.
- 통과하더라도 판정 상한은 `internal whole-tissue R/A/U exploratory; T not tested`이며
  tumor-specific·external·indispensable·clinically incremental functional use를 주장하지 않는다.

**다음 상태 전환 조건**

모든 재현성 gate가 통과하면 원고를 연구책임자의 author·affiliation·funding·ethics·journal
format·release metadata 확인 단계로 넘긴다. Multi-domain detector와 residual marker 발견은
별도 후속 workstream으로 유지한다.

**실행 결과**

- FM6 analysis의 기존 20개 nonvolatile output hash와 clean-rerun hash는 20/20 일치했다.
- ISUP OOF Spearman은 CONCH 0.615, Virchow 0.658이고 BCR-head C-index는 0.627과
  0.632로 재현됐다.
- Fixed-head C-index 감소는 0.041과 0.023, matched-random one-sided p는 두 모델 모두
  0.0099로 재현됐다. Refit-after-erasure 감소는 0.014와 0.010이며 기존 interval 해석을
  변경하지 않는다.
- 두 encoder 모두 R=`PASS_WHOLE_TISSUE_DEVELOPMENT`, A=`PASS_INTERNAL`,
  U=`PASS_EXPLORATORY_WHOLE_TISSUE`, T=`NOT_TESTED_LOCKED`, strong H2=`PROHIBITED`로
  동일했다.
- Manuscript build는 source 19/19와 numeric mapping 33/33을 통과했고 Main 22쪽,
  Supplementary 13쪽을 생성했다. QFM tests는 91/91 통과했다.
- PBV 원본 회귀검사는 322/323이 통과했다. 유일한 실패는 현재 NRF/GNU Funding 선언문과
  과거 ICT funding 문구를 요구하는 기존 test의 불일치로, FM6 분석·QFM 원고 변경과
  무관하며 PBV 선언문이나 test를 소급 수정하지 않았다.
- 결론은 기존과 동일하다. ISUP-correlated direction에 대한 내부 기능 민감도는
  재현됐지만 indispensable, tumor-specific, external 또는 clinically incremental use는
  확립되지 않았다.

### 21.25 FM6 clean-rerun 원고 편입·six-axis evidence-state 종결 — 2026-08-17

**목적과 범위**

- Task 21.24에서 재현된 FM6 결과와 계산 재현성 기록을 Main Methods·Results와
  Supplementary에 정식 편입한다.
- 새로운 cohort, endpoint, hyperparameter 또는 GPU 실험을 추가하지 않고, grade/phenotype,
  PTEN/AR, SPOP, recurrence의 기존 근거를 Table 1과 Figure 2--6에서 명시적으로 대비한다.
- `not evaluated/blocked`와 `available reference로 평가했지만 unsupported`를 분리하고,
  internal clean rerun을 external replication으로 오해하지 못하게 한다.

**태스크와 통과 기준**

- [x] FM6 표본·probe·head·targeted erasure·matched control·refit·clean-rerun 방법을 Methods에
  재현 가능하게 기술한다.
- [x] 392명/80 events와 두 encoder의 recoverability, BCR C-index, fixed/refit erasure,
  matched-random p 및 20/20 hash를 Results와 Supplementary에 일치시킨다.
- [x] R/A/U는 내부 exploratory 통과, T는 미실행, strong H2는 금지임을 명시한다.
- [x] phenotype 외부 reference가 grade-derived tumor/benign status임을 Figure 2·Table 1·본문에
  명시하고 exact tumor-content transport 주장을 금지한다.
- [x] PTEN/AR의 조건부 근거와 functional-use 미실행, SPOP available-label unsupported,
  recurrence endpoint sensitivity를 Figure 3--6과 본문에서 구분한다.
- [x] Abstract, Table 1, Results, Discussion, Conclusion, Supplementary의 evidence state를
  회귀검사로 고정한다.
- [x] source 19/19, numeric mapping 33/33, QFM tests 92/92, Main 23쪽·Supplementary 13쪽,
  unresolved reference/citation·overfull 0건과 핵심 페이지 시각 점검을 통과한다.

**완료 해석과 다음 상태**

- Grade/phenotype은 평가 축 중 가장 강하고 넓은 representation evidence를 보이지만,
  phenotype transport는 정확한 외부 tumor fraction 재현이 아니다.
- PTEN 관련 신호와 AR pooled alignment는 관찰됐으나 grade 독립성·site 안정성·외부
  transport는 확립되지 않았고 BCR-head functional use는 미실행이다.
- SPOP은 label 부재가 아니라 available genomic reference에서 frozen design이 지지되지
  않은 결과이며, 생물학적 중요성의 부재를 뜻하지 않는다.
- Recurrence는 endpoint와 clinical comparator에 민감한 exploratory risk association이며
  robust prognostic utility 또는 외부 임상 유효성으로 승격하지 않는다.
- FM6 20/20 hash 일치는 내부 계산 재현성이고, 외부 cohort functional replication이 아니다.
  과학 분석은 종결하며 다음 작업은 연구책임자 metadata·release·submission 확정이다.
