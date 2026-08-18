---
document_id: fm6-tcga-whole-tissue-internal-development-pilot-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-16
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-tcga-whole-tissue-internal-development-pilot-protocol-ko.md
---

# FM6 TCGA whole-tissue 내부 개발 pilot 프로토콜

## 1. 목적과 증거 상한

이 pilot은 TCGA-PRAD 392명/80 BCR events에서 다음 FM6 진입조건을 실제 데이터로
평가한다.

1. 동일 whole-tissue frozen embedding 위의 규칙 고정 BCR head가 내부 OOF에서 최소
   유효성을 보이는가?
2. 같은 embedding에서 ISUP Grade Group을 환자분리 OOF로 복원할 수 있는가?
3. whole-tissue ISUP-correlated 선형 subspace 제거가 fixed BCR head에 미치는 변화가
   matched-random 제거보다 큰가?
4. 관측 효과가 독립 tumor-region H2와 외부 검증의 power 설계에 사용할 만큼 안정적인가?
5. ISUP에 연령과 pathologic T stage를 더한 사람이 이해할 수 있는 3축 패널이 단일
   ISUP보다 AI BCR score를 더 설명하는가?

독립 tumor-region truth가 없으므로 결과의 최고 등급은 `internal whole-tissue
development evidence`다. ISUP가 tumor-specific metric이라는 점 때문에 이 pilot을
tumor-specific H1/H2, 임상적 유효성, external transport 또는 신규 marker 근거로
승격하지 않는다.

## 2. 고정 분석 universe와 split

- source: current-GDC TCGA-PRAD development source package
- patient universe: ISUP, 명시적 BCR status/time, eligible WSI가 모두 있는 392명
- event count: 80
- WSI universe: 437장; 모든 slide는 GDC size·MD5와 기술 header QC를 통과해야 한다.
- outer split: `development_outer_folds.csv`의 고정 5-fold, seed 260815
- 같은 환자의 모든 slide는 같은 fold에 둔다.
- 환자당 기여도는 1이다. tile mean → slide mean → patient mean의 등가중 집계를 사용한다.
- BCR/ISUP를 보고 tile, slide 또는 환자를 선택하지 않는다.

## 3. 영상·embedding 규칙

- 물리 FOV: 394.24 µm 정사각형
- candidate coordinate: thumbnail tissue proxy만 사용하는 outcome-blind deterministic
  sampling; file ID와 seed 260816으로 고정한다.
- tile budget: slide당 최대 64개, 최소 16개. 부족 slide와 이유를 보존한다.
- 두 encoder는 동일 level-0 boundary를 사용하며, 해당 boundary를 PIL bicubic으로
  448×448에 outcome-blind resampling한 canonical RGB cache 자체를 공유한다. 감사용으로
  원 decoded level-0 RGB crop hash를 함께 보존한다.
- CONCH 입력 448 px, embedding 512차원; Virchow 입력 224 px, embedding 2560차원
- encoder weight는 동결하고 fine-tuning하지 않는다.
- feature는 float32로 저장하고 nonfinite·zero-norm·row order·determinism을 감사한다.

## 4. 내부 개발 분석

### 4.1 ISUP recoverability

Training fold에서만 표준화와 ridge alpha를 선택하고 outer-test ISUP 연속값을 예측한다.
Spearman, MAE, rounded QWK를 보고한다. Label permutation은 같은 outer folds를 유지한다.
이는 whole-tissue decodability이며 tumor-specific H1이 아니다.

### 4.2 BCR head validity

각 outer-training fold에서 표준화, PCA와 ridge-penalized Cox head를 학습하고 inner-CV로
penalty를 선택한다. Outer-test risk를 합쳐 Harrell C-index와 patient bootstrap CI를
보고한다. ISUP-only와 ISUP+AI score를 같은 folds에서 비교한다. 최소 유효성은 사전
규칙상 C-index 95% CI 하한이 0.50을 넘는 경우이며, 미달하면 erasure 결과는
mechanistic sensitivity가 아니라 실패 원인/효과크기 추정으로만 남긴다.

### 4.3 ISUP-correlated subspace sensitivity

각 outer-training fold에서 표준화 embedding으로 ISUP ridge direction을 학습한다.
Test embedding에서 해당 rank-1 projection을 제거하고 다음을 분리한다.

- fixed-head: 원래 BCR head를 그대로 적용한 판단 변화
- refit-after-erasure: 제거 embedding에서 BCR head를 다시 학습한 잔여 정보
- matched-random: 동일 rank이며 training-fold 제거분산이 ISUP direction과 가장 가까운
  random direction 제거
- label-permuted: training ISUP를 순열한 direction 제거

Primary effect는 full minus erased C-index다. 표적 효과가 random-control 분포의 95번째
백분위수를 넘는지, 환자별 score 변화가 두 encoder에서 같은 방향인지 보고한다.
종양영역 부재 때문에 명칭은 `ISUP-correlated subspace sensitivity`로 고정하고
`targeted tumor erasure` 또는 strong H2라고 부르지 않는다.

### 4.4 탐색적 다중지표 패널

공유 TCGA manifest에 hash-lock된 cBioPortal PanCancer Atlas 임상 source에서 `AGE`와
`PATH_T_STAGE`만 보조축으로 사용한다. PFS/DFS/OS/DSS field는 BCR endpoint 누출과
estimand 혼합을 막기 위해 읽지 않는다. AGE는 연속값, PATH_T_STAGE는 T2/T3/T4의
사전 순서값으로 다룬다. 각 축의 OOF recoverability와 `ISUP only` 대비
`ISUP+AGE+PATH_T_STAGE`의 AI OOF risk 설명력 증분을 complete-case에서 보고한다.
연령과 병기는 임상적으로 이해 가능한 covariate이지만 독립 형태계측 truth가 아니므로
세 개의 독립 병리 metric family를 충족한 것으로 간주하지 않는다.

## 5. 다중성·불확실성·실패 처리

- 환자 bootstrap 2,000회, seed 260817
- undefined bootstrap 수와 비율을 삭제하지 않고 기록한다.
- CONCH와 Virchow 비교는 같은 patient draw를 사용하는 paired analysis다.
- encoder 우월성은 본 pilot의 주장 대상이 아니다.
- 누락·불완전 slide/embedding은 음성이나 0으로 대체하지 않는다.
- clean rerun은 시간·장치 snapshot을 제외하고 동일 hash를 가져야 한다.

## 6. 외부 코호트 경계

CHIMERA는 이 pilot에 입력하지 않는다. CHIMERA embedding, BCR head 적용, erasure,
residual 또는 outcome 표는 endpoint equivalence, power, publication embargo와 별도 승인
gate가 해제되기 전까지 실행하지 않는다. TCGA 효과는 external power simulation의
입력일 뿐 외부 재현의 증거가 아니다.

## 7. 산출물

- milestone: `milestones/fm6_internal_development_pilot/`
- local array/cache: `resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot/`
- paired tile/embedding manifest와 hash audit
- OOF patient score, performance·bootstrap·erasure-control table
- power input update와 scope-capped report
