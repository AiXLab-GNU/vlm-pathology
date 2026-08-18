---
document_id: fm6-tumor-region-detector-remediation-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-16
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-tumor-region-detector-remediation-protocol-ko.md
---

# FM6 tumor-region detector 재튜닝 프로토콜

## 재개 사유와 정보 분리

1차 detector는 SICAPv2 공식 test specificity 0.751과 PANDA Radboud sensitivity 0.299로
선고정 gate를 통과하지 못했다. 이 결과는 재개 사유일 뿐, 재튜닝의 loss·threshold·epoch
선택에는 사용하지 않는다. 이미 연 2,122개 SICAP test tile과 PANDA 40 slides는
`opened development evidence`로 표시하고 새로운 독립 holdout의 확증 근거로 재사용하지 않는다.

## 재튜닝 자료와 holdout 잠금

- 모델 선택은 SICAPv2 공식 train 9,959 tiles/124 slides의 3-fold
  `StratifiedGroupKFold(seed=20260816)` OOF 예측만 사용한다.
- 기존 PANDA 40 slides를 제외하고 provider × benign/cancer 각 25 slides, 총 100 slides를
  image ID 정렬·seed 20260817로 먼저 선택한다. Pixel과 detector score는 모델 고정 전
  읽지 않는다.
- 새 holdout manifest의 SHA-256을 후보 학습 전에 저장한다.
- TCGA, BCR, ISUP, CONCH, Virchow는 재튜닝과 holdout 선택에 사용하지 않는다.

## 제한된 후보군

모든 후보는 같은 ImageNet ResNet18, 394.24 µm boundary, binary/fraction multi-task target,
AdamW와 5 epoch를 사용한다.

1. `baseline`: 기존 color augmentation, negative weight 1.0.
2. `strong_color`: 강한 RGB stain-proxy augmentation, negative weight 1.25.
3. `hed_color`: HED 공간 stain perturbation, negative weight 1.25.
4. `hed_scale`: HED perturbation과 0.85–1.0 random scale, negative weight 1.25.

후보를 추가하거나 PANDA/SICAP opened 결과를 보고 범위를 바꾸지 않는다.

## OOF 선택과 calibration

- 각 fold에서 validation AUROC가 가장 높은 epoch의 OOF score를 저장한다.
- 후보별 pooled OOF에서 sensitivity와 specificity가 모두 0.82 이상인 threshold 중
  `min(sensitivity, specificity)`가 최대인 threshold를 선택한다. 동률은 AUROC, 낮은
  후보 복잡도 순으로 해소한다.
- 조건을 만족하는 후보가 없으면 remediation을 중단한다.
- 선택 후보를 SICAP train 전체에 5 epoch 재학습하고 OOF threshold를 그대로 잠근다.

## 새 PANDA holdout gate

Provider별 평가 가능한 양성·음성이 각각 100개 이상이어야 하며 다음을 모두 만족해야 한다.

- AUROC ≥ 0.80
- sensitivity ≥ 0.75
- specificity ≥ 0.70

두 provider가 모두 통과해야 `PASS_REMEDIATION_EXTERNAL_HOLDOUT`이다. 실패 시 test threshold를
바꾸지 않고 TCGA 적용을 중단한다. 통과하더라도 이는 scanner-proxy detector gate이며 TCGA
pixel truth나 strong H2가 아니다.
