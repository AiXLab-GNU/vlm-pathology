---
document_id: fm6-isup-bcr-source-and-power-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-15
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-isup-bcr-source-and-power-protocol-ko.md
---

# FM6 ISUP–BCR source·power 진입 프로토콜

## 1. 목적과 현재 판정

이 프로토콜은 ISUP Grade Group (M)과 biochemical recurrence/time (Y)를 사용하는
FM6 후보의 source, 단위, 결측, 외부 적용과 power gate를 결과 전에 고정한다. 질병
head 학습, targeted erasure, 외부 outcome 분석 또는 H2 해제 프로토콜이 아니다.

현재 판정은
`WHOLE_TISSUE_INTERNAL_PILOT_COMPLETE_TUMOR_EXTERNAL_H2_LOCKED`다.
CHIMERA 외부 source와 TCGA 개발 source package가 등록됐고 TCGA eligible WSI 437장은
size·MD5·header·thumbnail·MPP 검사를 통과했다. 다만 endpoint equivalence,
독립 tumor-region truth는 완료되지 않았다. 별도 whole-tissue 내부 개발 pilot에서
head 유효성·효과크기와 event-scaled external planning power 입력은 산출했으나,
endpoint-equivalent external validation과 정식 power는 완료되지 않았으므로 기존
strong-H2 claim ceiling은 변하지 않는다.

## 2. 프로젝트 최종 목적과의 연결

ISUP은 사람이 사용하는 T1 병리 지표이고 BCR은 ISUP과 독립적으로 정의되는 임상
outcome이다. 따라서 이 쌍은 향후 다음 질문을 시험하기 위한 후보 축이다.

1. CONCH와 Virchow의 frozen representation에서 ISUP 정보를 복원할 수 있는가?
2. locked BCR head가 그 ISUP 관련 정보를 실제로 사용하는가?
3. ISUP 관련 subspace를 제거한 뒤 남는 공통 residual이 외부 코호트에서도 반복되는가?

이번 단계는 위 질문의 source와 오류 경계를 준비할 뿐, 어느 질문에도 양성 답을
제공하지 않는다.

## 3. Source 역할과 현재 규모

| 역할 | 코호트 | 현재 감사 규모 | 허용 상태 |
|---|---|---:|---|
| development source | TCGA-PRAD current-GDC | WSI·ISUP·명시적 BCR 연결 392명/80 events; 치료 documented subset 308명/64 events; eligible WSI 437장 전체 local | size·MD5·header·thumbnail·MPP·5-fold 환자 split 완료; 별도 protocol의 whole-tissue 내부 개발 pilot만 허용, tumor-specific H2 잠금 |
| independent external candidate | CHIMERA Task 1 | 95명/27 events, prostatectomy WSI 190장, tissue mask 190장 | source/QC 등록만 허용; semantic QC·embargo·power hold |

다른 프로젝트의 생성 output은 입력으로 사용할 수 없다. TCGA와 CHIMERA는 각 원천과
QFM manifest에서 직접 등록하며, source hash가 달라지면 분석을 중단한다.

## 4. Metric과 endpoint semantics

### 4.1 ISUP metric

- primary source value는 CHIMERA JSON의 `reported ISUP`이다.
- primary/secondary Gleason으로 표준 Grade Group을 별도 도출해 source consistency를
  검사한다.
- 95명 중 92명은 concordant이고 3명은 source-discordant다.
- 원본 reported ISUP이나 Gleason을 임의 수정하지 않는다.
- 향후 ISUP semantic/H2 primary 분석 universe는 concordant 92명/27 events로 제한한다.
- discordant 3명은 reported ISUP를 보존한 all-subject sensitivity에만 포함한다.
- 이 제외 규칙은 BCR 결과에 의해 정해진 것이 아니며 outcome 분석 전에 고정한다.

### 4.2 BCR endpoint

- CHIMERA BCR은 수술 후 PSA `>=0.1 ug/L`이며 시간 단위는 `months`다.
- event 환자는 수술부터 recurrence까지, non-event 환자는 수술부터 마지막 PSA까지의
  시간을 사용한다.
- `BCR_PSA`의 missing key, blank와 observed 상태를 서로 구분한다.
- TCGA의 biochemical-recurrence 정의와 단위를 source field 수준에서 대조하고 동일
  estimand가 아님이 확인되면 primary pooling을 금지한다.
- `disease_response`, `with tumor` 또는 tumor-free transition을 BCR로 대체하지 않는다.

### 4.3 공변량과 결측

연령, pre-operative PSA, pT stage, surgical margin, lymph-node status, capsular
penetration, seminal-vesicle invasion, lymphovascular invasion과 earlier therapy를
보존한다. `x`, `unknown`, `missing_key`, `blank`, `null`을 0이나 음성으로 바꾸지 않는다.
CHIMERA에는 수술 후 adjuvant/salvage 치료가 완전하게 제공되지 않으므로 이 결손을
보정된 것으로 간주하지 않는다.

## 5. 영상과 환자 분석단위

- 분석단위와 split/bootstrap 단위는 환자다.
- 환자당 WSI는 1–12장으로 가변적이다. outcome을 보고 대표 slide를 선택하지 않는다.
- 모든 eligible slide를 사용하되 patient contribution이 slide 수에 비례하지 않도록
  source에서 slide-to-subject aggregation을 고정한 뒤 외부에 그대로 적용한다.
- 제공 mask는 foreground/background tissue mask이지 tumor mask가 아니다. ISUP는
  tumor-specific metric이므로 독립적으로 검증된 tumor-region 규칙 없이는 ISUP H1/H2를
  실행하지 않는다.
- 공식 명목 해상도 대신 TIFF tag를 읽어 물리 FOV를 맞춘다. 현재 190장 tag 감사값은
  모두 0.485069 micrometre/pixel이며 shared 394.24 micrometre FOV의 resampling,
  interpolation, padding과 crop hash를 embedding 추출 전에 고정한다.
- CONCH와 Virchow는 동일 환자·slide·좌표·물리 FOV·row order를 사용한다.

## 6. Development·external 잠금 규칙

1. foundation-model encoder weight는 동결한다.
2. concept probe, disease head, preprocessing, subspace rank, erasure method, threshold와
   patient aggregation은 development training fold에서만 선택한다.
3. CHIMERA에서 재학습, hyperparameter 선택, threshold 재최적화 또는 favorable subset
   선택을 금지한다.
4. external failure를 adaptation으로 고치려면 별도 protocol과 결과 family로 분리한다.
5. embargo 해제와 내부 접근 승인을 확인하기 전에는 outcome-derived 표와 모델 결과를
   포털 또는 외부 산출물 route로 제공하지 않는다.

## 7. Power와 H2 진입 기준

CHIMERA primary semantic universe의 27 events만으로 strong external H2를 가정하지 않는다.
현재는 feasibility/exploratory external candidate다. H2 실행 전 다음을 모두 충족해야 한다.

2026-08-16 whole-tissue 내부 pilot의 fixed-head delta는 CONCH 0.041, Virchow 0.023이고
event-scaled 계획 근사 power는 0.887/0.924였다. 이는 Section 7의 effect input 후보를
제공하지만 CHIMERA model/outcome을 사용하지 않은 근사치다. 독립 tumor-region에서
effect 보존을 확인하고 external censoring·matched-control 구조를 반영한 정식 simulation을
승인하기 전에는 formal power gate를 통과시키지 않는다.

1. TCGA development source package와 환자·사건 universe가 hash-lock된다.
2. disease head 최소 유효성, primary performance measure와 `delta_use`가 고정된다.
3. development-only effect와 censoring·환자 군집·matched-control 구조를 이용한 simulation을
   수행한다.
4. 현재 외부 사건 수에서 사전 고정한 방향, paired 95% CI, matched-random 및 family
   multiplicity 판정 규칙을 충족할 확률이 80% 이상인지 결과 전에 평가한다.
5. 80% 기준을 충족하지 않거나 clinically meaningful effect threshold를 사전 합의하지
   못하면 external H2는 exploratory로만 보고하고 strong claim을 금지한다.
6. 강한 H2에는 내부 `R+A+U`와 외부 `T`가 모두 필요하며, 외부 cohort 존재만으로
   `T`를 통과시키지 않는다.

## 8. 포털·publication embargo 경계

| 자료 | 노출 등급 |
|---|---|
| WSI, mask, raw clinical JSON | `never_serve` |
| patient-level normalized clinical, object inventory | `never_serve` |
| ISUP별 BCR·희소 치료 summary | embargo 동안 `never_serve` |
| acquisition/QC 보고서 | `project_internal` |
| 향후 모델·outcome 결과 | embargo 해제와 별도 승인 전 `never_serve` |

repository research portal 설계는 아직 draft이므로 legacy portal allowlist에 CHIMERA
artifact를 추가하지 않는다. 향후 manifest-driven portal이 승인된 뒤에도 위 등급을
낮추려면 publication policy와 연구책임자 승인을 다시 확인한다.

## 9. 현재 허용 작업과 다음 gate

허용 작업은 source hash 검증, 임상 의미 QC, 물리 해상도·mask 감사, tumor-region 및
patient aggregation의 결과-비의존적 준비와 power simulation 설계다. 추가로
`fm6-tcga-whole-tissue-internal-development-pilot-protocol-ko.md`에 따라 TCGA 내부에서만
paired embedding, development BCR head, ISUP probe, whole-tissue ISUP-correlated subspace
sensitivity와 matched control을 실행할 수 있다. 이 결과는 tumor-specific targeted
erasure, strong H2, 외부 BCR 성능 또는 residual marker 탐색으로 보고하지 않는다.

다음 단일 작업은 TCGA-PRAD 437 WSI의 outcome-blind paired tile manifest를 고정하고
whole-tissue 내부 개발 pilot을 실행해 disease-head validity와 power effect input을
산출하는 것이었으며 완료됐다. 현재 다음 단일 작업은 독립 tumor-region annotation 또는
고정 detector의 sensitivity/specificity·실패율·scanner별 성능을 감사하는 것이다.
CHIMERA model/outcome 실행은 endpoint·formal power·embargo gate가 해제될 때까지 계속
금지한다.

## 10. 근거

- CHIMERA Task 1: https://chimera.grand-challenge.org/task-1-prostate-cancer-biochemical-recurrent-prediction/
- CHIMERA download/license/embargo: https://chimera.grand-challenge.org/dataset-download/
- Dataset manifest: `resources/data/manifests/chimera_task1.yaml`
- Acquisition report: `projects/quantitative_foundation_model_validation/milestones/fm6_external_cohort_acquisition/outputs/fm6-external-cohort-acquisition-report.md`
- FM6 entry audit: `projects/quantitative_foundation_model_validation/milestones/fm6_entry_audit/outputs/fm6-entry-audit-report.md`
- FM6 internal pilot: `projects/quantitative_foundation_model_validation/milestones/fm6_internal_development_pilot/outputs/fm6-tcga-internal-development-pilot-report.md`
- Governing plan: `projects/quantitative_foundation_model_validation/docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md`
