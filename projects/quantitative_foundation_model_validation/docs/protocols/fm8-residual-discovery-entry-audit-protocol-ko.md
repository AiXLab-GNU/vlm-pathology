---
document_id: fm8-residual-discovery-entry-audit-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-25
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm8-residual-discovery-entry-audit-protocol-ko.md
---

# FM8 residual-discovery 진입 감사 프로토콜

## 1. 목적과 운영 경계

이 프로토콜의 목적은 FM8 본 연구를 실행하는 것이 아니라, 저장된 FM2--FM7/FM6
근거만으로 source-locked residual, paired CONCH--Virchow 비교, shortcut 감사, 독립
외부 반복과 blinded pathology review package를 편향 없이 만들 수 있는지 이진 판정하는
것이다. 판정은 `GO` 또는 `NO-GO`다.

Scientific Reports 논문 1의 revision 과학 workstream은 2026-08-24 closure baseline으로
종결·잠금한다. 이 감사에서는 paper workspace, `submission_orig/`, submission package,
Main/Supplement PDF, manuscript provenance를 수정하지 않는다. FM8 entry audit은 별도
후속 workstream이며 정식 FM8 residual-discovery 또는 두 번째 논문을 시작한 것으로
기록하지 않는다.

독립 tumor-region detector의 cross-domain sensitivity gate는 실패했다. 따라서 감사와
향후 후보 규칙은 whole-tissue로만 표현하며 tumor-specific residual, tumor-specific
mechanism 또는 tumor-specific shortcut 배제를 주장하지 않는다. Residual은 blinded
병리 검토, shortcut 감사, 외부 반복과 독립 biological/clinical validation 전에는
biomarker가 아니다.

## 2. 감사 evidence snapshot과 금지사항

- Evidence cutoff: 2026-08-25의 저장된 FM2--FM7/FM6 산출물과 QFM-owned local artifact.
- Source candidate: TCGA-PRAD 392명/80 BCR events, 437 WSI, 27,968 shared 394.24 µm
  whole-tissue crops, 기존 환자 5-fold.
- Independent external candidates: LEOPARD 508명/87 events와 CHIMERA 95명/27 events.
- Site-heldout 289명/69 events는 TCGA 내부 transport이며 독립 외부 cohort가 아니다.
- Target cohort의 score, residual 분포 또는 outcome을 보고 model family, threshold,
  quota, rank, regularization, calibration을 고르지 않는다.
- 다른 프로젝트의 generated output은 암묵적 입력으로 사용하지 않는다. FM6의
  `AGE`/`PATH_T_STAGE` source가 PBV model workspace를 가리키므로, FM8 재사용 전
  QFM-owned 원천 또는 hash-locked shared immutable manifest로 승격해야 한다.
- 실제 residual fitting, patch ranking, GPU inference, candidate export와 병리 검토는
  전체 entry gate가 GO가 되기 전 실행하지 않는다.

## 3. 분리 estimand와 leakage control

### 3.1 판단 residual

Encoder (k\in\{CONCH,Virchow\})의 환자 단위 locked disease score를 (S_k), 사전
지정 known pathology panel을 (M), 임상 공변량을 (C), 기술/QC 공변량을 (Q)라 한다.

\[
R^{score}_k=S_k-g_k(M,C,Q).
\]

- 단위는 환자이며 CONCH와 Virchow별로 별도 (g_k)와 별도 manifest를 사용한다.
- (S_k)는 기존 patient-grouped outer-fold의 OOF `full_risk`다. Score나 outcome으로
  threshold를 재최적화하지 않는다.
- (g_k)는 training fold 안에서만 fit한다. 연속형은 training mean/SD, 범주형은
  training vocabulary와 one-hot encoding, 결측은 training-fold median과 별도 missing
  indicator를 사용한다. Target-only category는 `unknown`으로 둔다.
- 후보 family는 ridge regression이고 alpha budget은
  `{0.01, 0.1, 1, 10, 100, 1000}`이다. Alpha는 inner patient-grouped CV의 MSE와 one-SE
  rule로 training fold 안에서 결정한다.
- 모든 환자는 held-out outer fold에서 한 번만 residual을 얻는다. Fold 밖 fit,
  전체표본 normalization, target recalibration과 post-hoc outcome threshold는 금지한다.

현재 실행 가능한 (M)은 주로 ISUP grade group이고 PRECISE에는 tumor fraction만 있다.
Age와 pathologic T stage는 (C), MPP와 tissue fraction은 (Q)다. 이 패널은 알려진
병리를 모두 포함하지 않으므로 허용 표현은 오직
`residual after the available prespecified metric panel`이다.

### 3.2 표현 residual

Frozen embedding을 (Z_k), source training fold에서만 추정한 known-metric subspace
projection을 (P_{M,k})라 한다.

\[
R^{repr}_k=(I-P_{M,k})Z_k.
\]

- 단위는 paired physical-FOV tile이며 slide와 patient ID를 함께 보존한다.
- Training fold 안에서 (C,Q)로 (M)을 먼저 residualize하고, standardized (Z_k)에서
  그 residualized (M)을 예측하는 ridge direction을 구한다.
- Ridge alpha budget은 판단 residual과 같고 inner patient-grouped CV에서만 정한다.
  Rank budget은 `{1, 2, 4, 8}` 중 metric 수와 training 환자 수보다 작은 값으로 제한하고,
  inner-CV reconstruction의 one-SE rule로 가장 작은 rank를 선택한다. 현재 ISUP 단일
  panel에서는 rank 1을 넘지 않는다.
- Projection, feature mean/SD, rank와 regularization을 encoder별 training fold 안에서만
  계산한다. 동일 embedding dimension 또는 component index를 encoder 간 대응시키지 않는다.
- Patch ranking scalar는 training-fold locked disease-head direction (w_k)에 대한
  `Trepr_k = zscore_train(w_k^T Rrepr_k)`로 사전 정의한다. 이는 tile-level ranking
  statistic일 뿐 판단 residual이나 biomarker와 합치지 않는다.

Rrepr과 Rscore은 서로 다른 단위, manifest, threshold, multiplicity family와 해석을
사용한다. 하나의 극단값이 다른 residual의 극단을 자동으로 뜻하지 않는다.

## 4. Source-lock 후보 규칙

이 규칙은 entry gate가 GO일 때만 활성화한다. 현재 감사가 NO-GO이면 값은 protocol
candidate로 남고 residual을 계산하거나 sample을 export하지 않는다.

- Source cohort: TCGA-PRAD 392명 전체; analysis unit은 Rscore=patient,
  Rrepr=paired 394.24 µm tile with slide/patient cluster.
- Inclusion: 저장된 5-fold, 두 encoder embedding, locked OOF score, ISUP, BCR 및
  manifest integrity가 모두 있는 환자. Exclusion은 machine-readable reason을 남긴다.
- Extreme thresholds: source OOF distribution의 lower/upper 10% quantile. Tie는
  `SHA256(protocol_id|seed|sample_id)` 오름차순으로 푼다.
- Encoder discordance: 두 encoder statistic을 각 source OOF distribution에서 percentile로
  바꾼 뒤 absolute percentile gap `>=0.50`; opposite-sign extreme은 별도 stratum이다.
- Common residual: 동일 physical FOV에서 두 encoder가 같은 sign extreme에 속하는
  sampling stratum이다. Blinded morphology 반복 전에는 common biology라 부르지 않는다.
- Encoder-specific residual: 한 encoder는 extreme이고 다른 encoder는 25--75 percentile.
- Matched non-extreme control: 두 encoder 모두 25--75 percentile이며 source site,
  grade, specimen, tissue-fraction quartile와 slide를 가능한 한 exact match한다.
- Technical/uncertain/not-evaluable은 별도 보존하고 candidate stratum으로 승격하지 않는다.
- Sampling cap: residual type별 환자당 8 tiles 이하, slide당 2 tiles 이하, 환자당 4 slides
  이하. 동일 환자는 reviewer split을 넘지 않는다.
- Quota: stratum 안에서 encoder, sign, site, ISUP, tissue-fraction quartile을 균형화한다.
  빈 cell을 다른 cell로 조용히 대체하지 않고 `not_evaluable_quota_cell`로 남긴다.
- Seed: `260825`; target cohort에서는 재학습, 재보정, threshold 또는 quota 변경을 금지한다.
- Uncertainty: patient-cluster bootstrap 2,000회. Rscore/Rrepr, encoder와 external cohort는
  별도 family로 두고 BH-FDR을 적용한다. Undefined replicate는 삭제하지 않는다.

최종 review sample size와 repeat-item 비율은 pathologist 수, item당 시간과 review burden을
확인한 뒤 residual/outcome을 보지 않고 별도 승인한다. 이를 정하지 못하면 review gate는
통과하지 않는다.

## 5. Shortcut 감사 최소 계약

Candidate 승격 전 최소한 site/acquisition domain, stain 또는 color statistics, scanner,
MPP/physical FOV, tissue fraction/area, tumor amount 또는 purity, grade/ISUP, specimen type,
blur/fold/compression/QC failure를 residual selection과 교차 감사해야 한다. 가능한 경우
age, treatment, stage와 molecular covariate를 포함한다.

각 변수는 source와 최소 한 외부 cohort에서 같은 의미·단위로 이용 가능해야 한다.
결측·unknown·not-evaluable은 값으로 보존한다. 독립 tumor detector gate 실패 때문에
whole-tissue tissue fraction 또는 grade adjustment를 tumor-specific shortcut 배제의
대체물로 사용하지 않는다. Shortcut과 morphology를 구분할 수 없는 item은 review
candidate로 승격하지 않는다.

## 6. 외부 반복 계약

- Source에서 fit한 (g_k), (P_{M,k}), normalization, head, threshold, quota와 seed를
  CHIMERA와 LEOPARD에 변경 없이 적용한다.
- CHIMERA는 prostatectomy, tissue-only mask, 95명/27 events, months 단위 PSA>=0.1
  BCR이며 TCGA endpoint equivalence는 미확정이다.
- LEOPARD는 508명/87 events와 paired crops/outcome을 제공하지만 ISUP/Gleason과 치료
  공변량이 없다. Source Rscore/Rrepr definition의 같은 (M,C,Q)를 적용할 수 없으면
  recurrence는 NOT-EVALUABLE이다.
- CHIMERA의 Virchow functional-transport 통과는 Virchow-specific stratum의 선행
  근거일 수 있으나 CONCH--Virchow common residual recurrence를 통과시키지 않는다.
- External recurrence는 같은 morphology의 source-locked ranking enrichment와 같은
  방향의 patient-level residual association을 별도 보고한다. Target 결과로 threshold를
  선택하지 않는다.

## 7. Blinded pathology review package 계약

Review 실행 전 다음을 모두 충족해야 한다.

- Reviewer 화면에는 encoder, residual type/sign/magnitude, outcome, site와 source/target을
  숨기고, 후보와 matched control을 seed 기반 무작위 순서로 제시한다.
- Morphology, artifact, adequacy, known concept, uncertainty와 `not_evaluable`을 별도 기록한다.
- 동일 환자/slide의 모든 item은 같은 reviewer split에 두고 repeat item만 명시적으로
  intraobserver set으로 복제한다.
- 내부 key table은 WSI, slide, physical coordinates, crop hash와 source provenance를
  유지하되 reviewer에게 숨기고 local encrypted access-controlled path에 둔다.
- Interobserver는 최소 2명, intraobserver repeat는 사전 지정 비율, disagreement는
  별도 adjudicator가 outcome을 가린 상태로 처리한다.
- Pathologist approval, 예상 item 수·분/item, review burden, adjudicator, data-access role,
  IRB/DUA와 CHIMERA patient-level image review 허용 근거를 review 전에 문서화한다.

Written organizer clearance 또는 동등한 patient-level review 권한, pathologist 승인과
접근통제 기록이 없으면 package 실행은 NOT-EVALUABLE이며 외부 image를 review package로
export하지 않는다.

## 8. GO/NO-GO gate

각 gate는 `PASS`, `FAIL`, `NOT-EVALUABLE` 중 하나로 판정한다.

1. Rrepr/Rscore을 leakage 없이 별도로 계산 가능
2. Source threshold와 sampling rule 고정 가능
3. 두 encoder의 paired comparison 가능
4. Shortcut 감사를 수행할 metadata 충분
5. 최소 하나의 독립 외부 cohort에서 source-locked recurrence 평가 가능
6. Blinded review package를 적법·재현 가능하게 생성 가능
7. Residual 해석을 available prespecified metric panel 범위로 제한 가능

필수 gate 하나라도 FAIL이면 전체는 NO-GO다. NOT-EVALUABLE은 GO로 대체하지 않으며,
해소 증거가 확보되기 전 FM8 본 연구를 시작하지 않는다. Residual seed/fold/rank 안정성,
review burden과 권한도 별도 readiness row로 감사한다.

## 9. 산출물과 중단 규칙

Entry audit은 availability, estimand/leakage, source-lock, shortcut, external recurrence,
blinded review, gate decision, blocker/action matrix와 evidence-linked report를 생성한다.
모든 표의 row count, required columns, 결측, unique patient와 SHA-256을 저장한다.

현재 evidence만으로 FAIL 또는 NOT-EVALUABLE이 확인되면 residual fitting·ranking·review
package 생성을 중단하고 blocker별 필요한 data/metadata/approval 목록만 남긴다. 논문 1,
기존 FM6 source/output와 local raw data는 수정하지 않는다.
