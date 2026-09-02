---
document_id: fm8-tier4-discovery-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-31
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm8-tier4-discovery-protocol-ko.md
supersedes: projects/quantitative_foundation_model_validation/docs/protocols/fm8-residual-discovery-entry-audit-protocol-ko.md
supersession_scope: tier4_computational_entry_only_historical_no_go_and_tier3_review_gate_preserved
---

# FM8 Tier 4 잠재 디지털마커 탐색 프로토콜

## 1. 적용 범위와 과거 NO-GO의 보존

이 문서는 2026-08-25 entry audit을 삭제하거나 PASS로 바꾸지 않는다. 과거 audit과 최종
`NO-GO` 보고서는 shortcut 감사와 blinded pathology review까지 한 번에 요구한 당시 진입
판정의 역사적 근거로 보존한다. 본 프로토콜은 오직 다음 운영 경계를 명시적으로 바꾼다.

- ground truth, frozen embedding, 환자 단위 leakage control과 locked external 적용이
  준비된 endpoint는 번역 전 `FM8 Tier 4` 계산 탐색을 수행할 수 있다.
- Tier 3 이상 승격, 영상 localization, 병리 명명과 blinded review는 shortcut, 권한,
  외부 형태 반복과 측정 재현성의 별도 GO 전까지 금지한다.

논문 1 경로와 결과는 수정하지 않는다. 독립 tumor detector gate 실패 때문에 전체 범위는
`whole-tissue`이며 tumor-specific signal/mechanism이라는 표현을 금지한다.

## 2. endpoint 분리

| endpoint | source | external | 단위 | label | 상태 |
|---|---|---|---|---|---|
| progression | TCGA-PRAD | CHIMERA | patient | BCR event와 follow-up time | 실행 |
| cancer_presence | NADT | PANDA | patient | benign/cancer; uncertain 계열 보존 | NOT READY |
| grading | NADT cancer | PANDA cancer | patient | ordinal ISUP/Gleason; benign 제외 | NOT READY |

Cancer와 grading label은 섞지 않는다. HGPIN, atypical, uncertain, missing, not-evaluable을
benign 또는 낮은 grade로 바꾸지 않는다. 다른 프로젝트 generated output은 hash-locked
shared immutable manifest 없이 읽지 않는다.

## 3. tier와 기능 역할

`medical_metric_tier`와 `fm8_translation_tier`를 별도 저장한다. FM8 Tier 1--4는 각각 직접
식별 임상표현, 기존 의학과 연결된 정량표현, 반복 계측 가능한 신규 임상표현, 아직 번역되지
않은 안정 잠재신호다. 최초 latent score는 두 축 모두 T4 계열이지만 두 분류의 의미는 같다
고 가정하지 않는다.

기능 역할은 다중 label이다.

- standalone: source와 external latent-only C-index가 모두 0.5보다 크고 source 5-fold 중
  4개 이상이 같은 방향이다.
- complementary: source와 external에서 `C(additive)-C(baseline)>0`이다.
- interactive: source-fixed ISUP×latent 계수와 source/external의
  `C(interaction)-C(additive)`가 양의 재현을 보인다.
- redundant/supportive: standalone이면서 external additive 절대 증분이 0.01 이하이다.
- not qualified: 위 근거가 외부에서 재현되지 않거나 material shortcut과 분리할 수 없다.

CHIMERA의 작은 사건 수 때문에 CI가 0을 포함한다는 사실만으로 자동 실패시키지 않는다.
방향, CI, fold 안정성, undefined 수와 shortcut 상태를 모두 보고한다.

## 4. BCR 입력 잠금

- TCGA: 392명/80 events, 437 WSI, 27,968 tiles, 기존 5 patient folds, time days.
- CHIMERA: 95명/27 events, 190 WSI, 12,160 tiles, time months.
- CONCH 512차원과 Virchow 2,560차원 frozen embedding은 encoder별 별도 분석한다.
- tile mean → slide equal mean → patient equal mean으로 환자 표현을 만든다.
- input path, bytes, SHA-256, row/column, subject/event/slide/tile 수와 array shape를 기록한다.
- endpoint threshold/censoring equivalence는 확립되지 않았으므로 cohort를 pooling하지 않는다.

## 5. source-only nested 분석

각 outer training fold 안에서 다음 순서를 지킨다.

1. embedding mean/SD를 training 환자에서만 적합한다.
2. ISUP, mean tissue fraction, mean MPP, log1p(slide count)를 training 값으로 표준화한다.
3. known/QC panel 예측 ridge alpha `{1,10,100,1000}`을 inner-fold multivariate MSE와
   one-SE rule로 선택하고 계수 row-space를 제거한다. 분산 0인 panel 열은 기록 후 제외한다.
4. residual representation PCA rank `{4,8,16,32}`와 Cox alpha `{1,10,100,1000}`을 inner
   patient-fold C-index와 one-SE rule로 선택한다.
5. latent risk를 training risk mean/SD로 표준화한다. Outer-train stacked model에는 같은
   outer-train 환자의 inner-OOF latent risk만 입력한다.
6. baseline, latent-only, additive, interaction Cox alpha `{0.1,1,10,100}`을 inner fold에서
   선택한다. Held-out outer 환자는 정확히 한 번 예측한다.

전체 source에서 같은 5-fold 규칙으로 최종 설정을 정하고 모든 TCGA 환자로 최종 모델을
적합한다. CHIMERA에는 projection, PCA, rank, alpha, scaling, coefficient와 후보를 변경 없이
적용한다. External outcome을 사용한 선택·재보정·threshold 변경은 금지한다.

## 6. 평가와 불확실성

encoder·cohort별 baseline, latent-only, additive, interaction C-index,
`delta_additive`, `delta_interaction`, source additive latent coefficient/HR와 interaction
coefficient/HR를 보고한다. 환자 bootstrap 2,000회는 네 모델을 같은 draw로 비교하고,
single-event class 또는 no-comparable-pair replicate는 `undefined`로 남긴다. Source 5-fold
C-index와 선택된 rank/alpha의 안정성을 보존한다.

## 7. shortcut 감사

Site/TSS, site availability, grade, MPP, tissue fraction, slide count, crop RGB mean/SD,
brightness/saturation과 optical-density proxy의 candidate-score 연관을 cohort별로 보고한다.
Stain label, scanner, blur, fold, compression, specimen, tumor amount/purity가 없으면
`NOT_EVALUABLE`로 남긴다. Whole-tissue fraction은 tumor purity가 아니다. External site와
scanner를 평가할 수 없으면 shortcut 완전 배제를 주장하지 않는다.

사전 경보 기준은 연속 QC와 latent score의 `|Spearman rho| >= 0.30`, 범주형 site/scanner의
score 분산 `eta-squared >= 0.10`이다. 같은 방향의 연속 QC 경보가 source와 external에서
반복되거나 평가 가능한 acquisition domain 경보가 남으면 `FAIL_MATERIAL_ASSOCIATION`이다.
필수 external site/scanner가 없어 배제 여부를 계산할 수 없으면 양성 성능과 무관하게
`PARTIAL_NOT_EVALUABLE`이며 최종 후보 자격은 `not_qualified_shortcut_unresolved`로 제한한다.

## 8. 후보와 claim ceiling

후보 registry는 candidate ID, endpoint, encoder, source/external cohort, 두 tier, 네 기능
상태, shortcut, external reproduction, claim ceiling과 evidence path를 가진다. 한 encoder만
재현되면 encoder-specific 후보로 보존하되 공통 생물학이라고 부르지 않는다.

현재 최대 주장은 `externally evaluated whole-tissue Tier 4 latent digital-marker hypothesis`다.
Tier 3 승격에는 외부 재현 Tier 4 후보, tile 좌표 기여도, source/external 극단·대조 patch,
site/grade/MPP/color/tissue matched control, 반복 morphology, review 권한과 병리 승인 GO가
필요하다. 그 전에는 review package를 만들거나 형태 이름을 붙이지 않는다.

## 9. 중단·재현성

Hash, row order, patient fold, finite value, endpoint, OOF coverage 또는 external lock이 깨지면
분석을 중단한다. 환자별 prediction과 color/QC row는 local artifact에 두고 aggregate 표와
한국어 보고서는 milestone output에 둔다. seed, 환경, 실행시간, PID/tmux/GPU 상태와 모든
입출력 hash를 저장한다. 별도 clean rerun의 nonvolatile output hash exact match가 필요하다.
