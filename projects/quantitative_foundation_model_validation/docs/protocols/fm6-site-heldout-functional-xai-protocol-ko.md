---
document_id: fm6-site-heldout-functional-xai-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-20
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-site-heldout-functional-xai-protocol-ko.md
---

# FM6 기관 분리 기능적 XAI 검증 프로토콜

## 목적

기존 TCGA-PRAD FM6 whole-tissue 개발 분석의 ISUP-correlated fixed-head sensitivity가
학습에 전혀 포함되지 않은 TCGA tissue source site에서도 유지되는지 결과 확인 전에 고정한
규칙으로 검증한다. CHIMERA는 공식 출판 embargo 때문에 사용하지 않는다. LEOPARD 외부
분석은 책임저자의 별도 embargo 해제 확인 후 독립된 고정 프로토콜에서만 수행한다.

## 고정 자료와 분할

- 분석 universe: 392명, BCR 80 events의 hash-locked TCGA 개발 자료.
- 입력: 동일 394.24 micrometre crop에서 생성된 paired CONCH/Virchow embedding.
- 기관: TCGA case barcode의 tissue source site 두 글자.
- 평가 적격 기관: 20명 이상이면서 BCR event 5건 이상.
- 적격 기관: HC, EJ, G9, KK, V1, YL, J4; 평가 289명/69 events.
- 한 기관을 평가할 때 그 기관의 모든 환자를 학습에서 제외한다.
- 비적격 기관 환자는 학습에는 사용할 수 있지만 primary held-out estimate에는 포함하지 않는다.

## 고정 모델

- StandardScaler: 각 기관 제외 training partition에서만 적합.
- PCA: rank 64, randomized solver, seed 260820.
- CoxPH ridge alpha: 1000.
- ISUP Ridge alpha: 1000.
- encoder weight와 patient aggregation은 기존 FM6에서 변경하지 않는다.
- 기관별·encoder별 ISUP direction과 BCR head는 held-out 기관의 label 또는 embedding을 보지
  않고 training partition에서만 적합한다.

## 개입과 대조군

Standardized embedding에서 training-derived ISUP direction을 직교 제거하고 같은 고정 BCR
head를 적용한다. 기관·encoder별로 target direction과 제거분산이 같은 random direction
100개를 outcome-blind하게 생성한다. 결과 확인 후 direction rank, alpha, site 기준 또는
random family를 바꾸지 않는다.

## Primary estimand

기관 안에서만 comparable survival pair를 구성해 일치·불일치 pair를 7개 기관 전체에서
합산한 stratified C-index를 사용한다. Cross-site pair는 제외한다.

`delta_use = stratified C-index(full) - stratified C-index(target-erased)`

기관 내 환자 bootstrap 2,000회로 paired 95% CI를 계산한다. Target-versus-random p-value는
100개 random delta 중 target 이상인 개수로 계산하고 두 encoder에 Holm 보정한다.

## 통과 기준

Encoder별 통과에는 다음이 모두 필요하다.

1. full-head stratified C-index 95% CI lower bound > 0.50;
2. target `delta_use` 95% CI lower bound > 0;
3. Holm-adjusted target-versus-random p <= 0.05;
4. 7개 중 5개 이상 기관에서 site-specific delta > 0.

두 encoder 모두 통과하면 `PASS_REPLICATED_SITE_HELDOUT_FUNCTIONAL_TRANSPORT`, 하나만
통과하면 `PARTIAL_ENCODER_SPECIFIC_SITE_HELDOUT_EVIDENCE`, 모두 미통과하면
`FAIL_OR_INCONCLUSIVE_SITE_HELDOUT_EVIDENCE`로 잠근다.

## 주장 경계

양성 결과도 `TCGA 내 기관 분리 whole-tissue functional transport`만 지지한다. 독립 외부
cohort transport, tumor-specific mechanism, strong external H2, clinical utility와 신규
biomarker는 계속 금지한다. 음성 결과는 재튜닝하지 않고 그대로 보고한다.
