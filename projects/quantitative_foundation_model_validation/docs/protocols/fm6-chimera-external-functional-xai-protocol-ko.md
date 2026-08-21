---
document_id: fm6-chimera-external-functional-xai-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-21
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-chimera-external-functional-xai-protocol-ko.md
---

# FM6 CHIMERA 외부 기능적 XAI 실패 원인 분해 프로토콜

## 출판 정책 gate

2026-08-21 공식 CHIMERA data page와 challenge rules를 확인했다.

- `https://chimera.grand-challenge.org/dataset-download/`
- `https://chimera.grand-challenge.org/challenge-rules/`

두 페이지는 CHIMERA public training data 결과를 challenge journal paper와 baseline journal
paper가 모두 출판된 뒤에만 출판할 수 있다고 명시한다. 공식 페이지의 embargo 문구는 현재도
유지되며 저장소에 책임저자의 서면 허가 artifact가 없다. 따라서 상태를
`EMBARGO_ACTIVE_NO_WRITTEN_CLEARANCE`로 고정한다. 종료일을 추정하지 않는다.

사용자가 승인한 내부 분석은 수행하되 embedding, 환자별 예측, outcome-derived 표·보고서와
실행 기록은 모두 QFM 소유 ignored local artifact에만 저장한다. clearance 전에는 milestone
tracked output, manuscript, submission package, public repository, tag 또는 release를 수정하지
않는다.

## 분석 universe와 영상 규칙

- CHIMERA Task 1 전체 95명/27 BCR events/190 prostatectomy WSI/190 official tissue masks.
- BCR은 수술 후 PSA `>=0.1 µg/L`, 시간 단위는 months다. TCGA endpoint와 완전 동등하다고
  주장하지 않는다.
- ISUP primary는 source-reported all-95이며 원본을 수정하지 않는다. 표준 Gleason mapping과
  일치하는 92명 결과를 사전 고정 sensitivity로 함께 저장한다.
- official mask는 foreground/background tissue mask이며 tumor mask가 아니다.
- FOV 394.24 µm, WSI당 64 crops, seed 260820, shared canonical 448×448 RGB crop을 사용한다.
- crop mean → slide mean, 이어서 patient 내 slide equal-weight mean을 primary로 고정한다.
- 두 encoder의 subject, slide, coordinates, tile ID, decoded-RGB SHA-256와 row order는 1:1로
  같아야 한다.

## 고정 TCGA 모델

CONCH와 Virchow 각각에서 기존 392명/80 events TCGA representation만 사용해 StandardScaler,
PCA rank 64, CoxPH alpha 1000 BCR head와 Ridge alpha 1000 ISUP probe/direction을 적합한다.
CHIMERA에서는 head, direction, threshold, sampling, aggregation, endpoint 또는 subset을
재학습·재튜닝하지 않는다. TCGA training representation에서 100개 variance-matched random
direction을 생성한다.

## A. External ISUP recoverability

TCGA-locked probe를 all-95에 적용한 Spearman rho와 환자 bootstrap 2,000회 95% CI를 primary로
보고한다. concordant-92에서도 같은 값을 sensitivity로 보고한다. primary CI 하한이 0보다 클
때만 recoverability gate를 통과한다.

## B. External BCR head validity

TCGA-locked full risk의 Harrell censored C-index와 환자 bootstrap 2,000회 95% CI를 보고한다.
CI 하한이 0.50보다 클 때만 validity gate를 통과한다.

## C. Functional erasure

TCGA-locked ISUP-correlated rank-one direction을 제거한 뒤 같은 고정 BCR head를 적용한다.
`delta_use = C(full) - C(target-erased)`의 paired bootstrap CI, 100개 matched-random null,
random p95, `(1 + count(random >= target))/101` p-value와 두 encoder Holm 보정값을 저장한다.
통과에는 full-head gate, delta CI 하한 `>0`, target delta `> random p95`, Holm p `<=0.05`가
모두 필요하다. full head가 실패하면 erasure만 양성이어도 통과하지 않는다.

## D. 고정 원인 상태

무결성 실패, ISUP 비복원, 양의 point estimate이지만 CI가 null을 포함하는 low-event
precision, ISUP 복원 후 BCR head 비전이, BCR head 전이 후 erasure 미적격, 전체 통과 순서로
다음 상태 중 하나를 encoder별로 부여한다.

- `INTEGRITY_FAILURE_NO_SCIENTIFIC_INTERPRETATION`
- `ISUP_NOT_RECOVERABLE_EXTERNAL_REPRESENTATION_SHIFT`
- `FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION`
- `ISUP_RECOVERABLE_BCR_HEAD_NOT_TRANSPORTED`
- `BCR_HEAD_TRANSPORTED_FUNCTIONAL_ERASURE_NOT_QUALIFIED`
- `QUALIFIED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT`

27 events로 인한 낮은 precision을 모든 결과 해석에 병기한다. 긍정 결과도 whole-tissue
functional sensitivity의 internal embargo-controlled evidence일 뿐 tumor-specific mechanism,
clinical deployment, clinical increment, endpoint equivalence, encoder 우월성 또는 신규 marker를
허용하지 않는다.

## 재현성

입력 manifest와 모든 local object SHA-256, 고정 seed, model revision/weight hash, package,
GPU, runtime, subject/event/slide/mask/crop 수, paired crop audit을 저장한다. bootstrap 단위는
환자다. 분석을 별도 clean-rerun 경로에서 다시 실행하고 모든 nonvolatile output hash의 exact
match를 요구한다.
