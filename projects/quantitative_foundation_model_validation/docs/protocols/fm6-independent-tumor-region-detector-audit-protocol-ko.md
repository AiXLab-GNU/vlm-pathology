---
document_id: fm6-independent-tumor-region-detector-audit-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-16
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-independent-tumor-region-detector-audit-protocol-ko.md
---

# FM6 독립 tumor-region detector 감사 프로토콜

## 목적과 주장 경계

TCGA-PRAD outcome, ISUP, CONCH, Virchow를 보지 않고 학습한 고정 detector로 기존
394.24 µm 타일의 종양 포함 가능성을 판정한다. 이 단계의 목적은 whole-tissue pilot을
detector-restricted 개발 분석으로 옮길 수 있는지 결정하는 것이다. Detector 통과는 TCGA
pixel-level tumor truth, 강한 H2, 외부 outcome transport 또는 신규 marker를 증명하지 않는다.

## 독립 학습·시험 자료

- 개발 자료: SICAPv2 10×, 512×512 H&E patch와 expert pixel mask.
- 고정 시험: SICAPv2 공식 `partition/Test/Train.xlsx`와 `Test.xlsx`; slide identifier가
  train/test 사이에 겹치지 않아야 한다.
- 외부 scanner-proxy 감사: PANDA의 `karolinska`와 `radboud` provider별 image와
  pixel mask. Provider는 scanner 자체가 아니라 acquisition-domain proxy로만 해석한다.
- 종양 truth: SICAPv2 mask의 값 3/4/5. PANDA Karolinska는 2, Radboud는 3/4/5.
- 어떠한 TCGA outcome, ISUP 또는 FM embedding도 detector 학습·threshold 선택에 쓰지 않는다.

## 물리 경계와 모델

- 목표 경계: 기존 FM6와 동일한 394.24 µm.
- SICAPv2는 공개 명세의 10×(약 1 µm/px)를 적용해 중앙 394×394 pixel을 사용하고
  detector 입력 224×224로 resize한다.
- PANDA는 TIFF XResolution로 page별 MPP를 계산하고 394.24 µm window를 사용한다.
- 모델은 로컬 hash가 고정된 ImageNet ResNet18이며 출력은 tumor-presence logit와
  tumor-fraction logit 두 개다. CONCH/Virchow는 detector에 사용하지 않는다.
- SICAPv2 공식 train 내부에서 slide-group 80/20 development/validation split을 seed 20260816으로
  한 번 고정한다. Test는 모델·threshold 선택에 사용하지 않는다.

## 학습과 threshold

- binary target: 중앙 crop의 tumor pixel fraction ≥ 0.10.
- 보조 연속 target: 같은 crop의 tumor pixel fraction.
- loss: binary BCE + 0.5 × fraction MSE; ImageNet normalization, flip/90도 회전 및 제한적
  color jitter만 허용한다.
- validation balanced accuracy 최대 threshold를 선택하며 동률이면 높은 sensitivity를 택한다.
- epoch 수, optimizer 및 선택 epoch는 run config에 저장한다.

## 선고정 detector gate

SICAPv2 공식 test에서 다음을 모두 만족해야 `PASS_INTERNAL`이다.

1. AUROC ≥ 0.90.
2. sensitivity ≥ 0.85.
3. specificity ≥ 0.80.
4. corrupt/missing/inference failure ≤ 1%.
5. patient/slide bootstrap 95% CI를 함께 보고한다.

PANDA provider별로 AUROC ≥ 0.80, sensitivity ≥ 0.75, specificity ≥ 0.70을 모두 만족해야
`PASS_EXTERNAL_SCANNER_PROXY`이다. 한 provider라도 실패하거나 평가 가능한 양성·음성이 각각
50개 미만이면 detector gate는 `NARROW_OR_FAIL`이다. Gate 기준은 결과를 본 뒤 변경하지 않는다.

## PANDA 표본 규칙

- provider × slide-level benign/cancer 층마다 mask가 있는 image 10개를 image ID 정렬 후
  seed 20260816으로 선택한다.
- 각 slide에서 mask-annotated tissue 중심으로 최대 32개의 394.24 µm patch를 생성하고,
  cancer slide에서는 가능한 한 tumor/non-tumor를 같은 수로 구성한다.
- PANDA mask의 알려진 annotation noise 때문에 이는 외부 scanner-proxy 감사이며 임상 검증이 아니다.

## TCGA 적용과 고정 집계 규칙

두 detector gate가 모두 통과한 경우에만 기존 outcome-blind 27,968개 canonical crop을 점수화한다.

- slide별 score ≥ validation threshold인 타일 가운데 최고 32개를 선택한다.
- 8개 미만이면 해당 slide를 detector-not-evaluable로 보존한다.
- 환자 표현은 선택 타일 평균 → slide 동일가중 평균 → patient 동일가중 평균이다.
- 결과를 본 뒤 타일 수, threshold, fold, head, erasure control을 바꾸지 않는다.
- TCGA pixel truth가 없으므로 이후 결과 명칭은 `detector-restricted exploratory R/A/U`이며
  `tumor-specific confirmatory`가 아니다.

## 재현성과 중단 규칙

- source/archive/member/model/output hash, seed, 환경, 실행시간과 실패를 저장한다.
- 두 번의 평가 rerun에서 volatile field 외 해시가 같아야 한다.
- detector gate 실패 시 TCGA filtering과 H2 분석을 실행하지 않고 실패 원인·필요 자료를 기록한다.
- gate 통과 후에도 CHIMERA endpoint equivalence와 embargo가 풀리기 전 external T는 실행하지 않는다.
