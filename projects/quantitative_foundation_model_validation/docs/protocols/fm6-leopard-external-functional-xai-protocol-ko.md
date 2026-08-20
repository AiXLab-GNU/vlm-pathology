---
document_id: fm6-leopard-external-functional-xai-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-20
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-leopard-external-functional-xai-protocol-ko.md
---

# FM6 LEOPARD 외부 기능적 XAI 검증 프로토콜

## 승인과 범위

책임저자는 2026-08-20 LEOPARD publication embargo가 종료됐음을 확인하고 재제출 분석
사용을 승인했다. 외부 확인 문서의 저장소 보관 상태는 `unrecorded`로 남긴다. CHIMERA의
별도 embargo는 해제하지 않는다.

본 분석은 TCGA에서만 고정한 BCR head와 ISUP-correlated direction을 독립 LEOPARD BCR
cohort에 한 번 적용한다. LEOPARD에는 ISUP/Gleason과 치료 공변량이 없으므로 external ISUP
recoverability, 임상 증분 또는 tumor-specific mechanism을 검증하지 않는다.

## 고정 자료와 전처리

- TCGA: 392명/80 events의 기존 FM6 development universe.
- LEOPARD: 508명/87 source-defined BCR events, 508 WSI와 508 tissue mask.
- label SHA-256: `04d8229b58348a317790d279ae134d84f6a795ab956fd52208c08f2279ff1186`.
- physical FOV: 394.24 micrometres.
- outcome-blind tissue-mask sampling: WSI당 최대 64, 최소 16 crop.
- canonical crop: 448 x 448 RGB; 두 encoder의 case·coordinate·crop hash·row order 동일.
- seed: 260820.

## 고정 모델과 개입

- StandardScaler와 PCA rank 64는 TCGA 전체에서만 적합한다.
- CoxPH alpha와 ISUP Ridge alpha는 모두 1000이다.
- TCGA standardized embedding에서 ISUP direction을 적합하고 LEOPARD embedding에서 같은
  direction을 제거한다.
- full representation과 target-erased representation에 동일한 고정 Cox head를 적용한다.
- TCGA training representation에서 제거분산을 맞춘 random direction 100개를 생성한다.
- LEOPARD에서 재학습, hyperparameter 선택, threshold 선택, subset 선택을 금지한다.

## 추정량과 통과 기준

Primary estimand는 LEOPARD patient-level C-index의 paired 감소
`delta_use = C(full) - C(target-erased)`다. 환자 bootstrap 2,000회로 95% CI를 계산하고,
matched-random one-sided p-value를 두 encoder에 Holm 보정한다.

Encoder 통과에는 다음이 모두 필요하다.

1. full-head C-index CI lower bound > 0.50;
2. target delta_use CI lower bound > 0;
3. Holm-adjusted target-versus-random p <= 0.05;
4. 508명이 모두 평가 가능하거나 outcome-blind technical exclusion 후 80 events 이상 유지.

두 encoder가 모두 통과해야
`PASS_REPLICATED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT`로 판정한다.

## 주장 경계

양성 결과는 `independent external BCR transport of whole-tissue functional sensitivity`만
지지한다. External ISUP R, tumor-specific use, endpoint equivalence, clinical increment,
indispensability, strong H2와 신규 biomarker는 계속 미확립 또는 금지 상태다. 결과가 음성이면
재튜닝 없이 그대로 잠근다.
