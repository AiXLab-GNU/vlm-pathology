---
document_id: 2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: approved
created: 2026-09-02
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design.md
implements: null
supersedes: projects/quantitative_foundation_model_validation/docs/designs/2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-design.md
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm9_prostate_diagnostic_anchor_and_discovery
  - resources/artifacts/quantitative_foundation_model_validation/fm9_prostate_diagnostic_anchor_and_discovery
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm9_prostate_diagnostic_anchor_and_discovery -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# Prostate diagnostic anchor and frozen-representation discovery design

## 결정

FM8 M1의 실패는 CONCH/Virchow에 grading 정보가 없다는 결론이 아니라, `무작위 최대 64개
tissue tile + 단일 ISUP ordinal head`가 독립 reader에서 기능 분석을 허용할 정도로 정확하지
않았다는 결론이다. PAR 결과로 이 head를 조정하지 않는다.

후속 연구는 두 경로를 분리한다.

1. **진단 성능 anchor:** 전용 암 검출, 종양 위치, GP3/4/5와 slide/case 집계를 학습하는
   task-specific 모델로 데이터·truth·평가 파이프라인의 도달 가능한 성능을 확인한다.
2. **Frozen-FM discovery:** CONCH와 Virchow를 고정한 채 같은 진단 endpoint를 별도의 head로
   학습하고, 알려진 병리 기준의 표현·기능적 사용·사용량을 검정한다.

Anchor는 양성 대조군이며 frozen 모델의 자발적 표현 또는 사용을 증명하지 않는다. Frozen
경로가 정확도 gate를 통과하지 못하면 그 encoder의 기능적 사용·residual 분석은 중단한다.

## 역할별 데이터 잠금

선정 근거는 [전립선 진단 코호트 서베이](../surveys/prostate-diagnostic-cohort-selection-survey-ko.md)에
보존하고, machine-readable 역할은 `manifests/prostate_diagnostic_cohort_portfolio.yaml`에 둔다.

| 질문 | 개발 | 독립 qualification | criterion truth | 역사적/보조 |
|---|---|---|---|---|
| 암 유무 | PANDA + 중복/환자 감사 후 DiagSet-B | DiagSet-C 9-reader, SPROB20은 접근 후 별도 transport | DiagSet-A + 새로 획득할 PRECISE paired-IHC release | PAR reader-conditioned stress |
| Cancer-only grading | PANDA | PBGG-1, PBGG-2를 분리한 multi-reader/majority 평가 | SICAP GP3/4/5·cribriform, 개발 보조 PANDA-PLUS | PAR historical stress, CHIMERA specimen transport |
| Residual marker | 아직 없음 | 별도 untouched 외부 반복 필요 | blinded pathology + 독립 assay/outcome 필요 | TCGA/CHIMERA BCR은 별도 lane |

DiagSet, PBGG, PRECISE 가운데 하나도 전체 목적의 단일 gold standard가 아니다. DiagSet-C는
작고, PBGG는 암 양성 균형 표본이며, PRECISE paired-IHC는 선택된 IHC criterion anchor다.
현재 local PRECISE는 25명/27 H&E WSI와 27 mask뿐이고 IHC가 없으며 metadata 한 행이
malformed라서 새 release를 획득·감사하기 전에는 이 역할을 수행하지 못한다. 최종 임상
배치 주장은 더 큰 untouched multi-reader/IHC 코호트 없이 금지한다.

## Endpoint와 모델 구조

### 1. 암 유무

Primary cancer output은 전용 binary/abstaining head다. `1 - P(ISUP 0)`는 secondary coherence
check일 뿐 primary 암 확률이 아니다. 불확실/IHC 필요, HGPIN, AIP, IDC-P를 사전 규칙 없이
benign 또는 invasive cancer로 병합하지 않는다.

모델은 먼저 coarse-to-fine tumor probability map을 생성하고, slide와 환자/case 단위로
집계한다. Sensitivity, specificity, AUROC/AUPRC, NPV/PPV, calibration, abstention coverage-risk를
환자 단위로 보고한다.

### 1A. 재현 가능한 grading 양성 대조군

첫 off-the-shelf anchor는 `chimera_hvit_biopsy_isup_off_the_shelf_weights_v1`로 고정한다.
DIAGNijmegen의 CHIMERA biopsy inference commit
`2b17a75891e8f017e7a92201509c63770cd39fe5`와 `weights-v1`의 10개 SHA-256을 사용하며,
입력은 0.5 micrometre/pixel, 2,048-pixel region, 256-pixel patch로 변경하지 않는다. 5개
fold의 192차원 latent를 순서대로 결합한 960차원 표현과 ISUP 0--5 majority output을
보존한다. 이 모델은 grading 양성 대조군이며 전용 cancer head가 아니므로 `1-P(ISUP0)`를
primary 암 판정으로 승격하지 않는다.

공개 저장소라는 사실만으로 실행 권한과 재현성이 충족됐다고 간주하지 않는다. 명시적
license/permission, 실제 weight hash, digest-pinned base image 또는 잠긴 built image,
dependency lock과 D0 data gate가 모두 PASS일 때만 prediction을 허용한다. 같은 HViT 계열을
PANDA에서 재학습하는 모델은 별도 ID `qfm_hvit_biopsy_isup_retrained`로 관리하고
off-the-shelf 결과와 checkpoint·선택·주장을 합치지 않는다.

### 2. Grading

Grading은 cancer-positive tissue에서만 평가한다. 모델 출력은 GP3/4/5 spatial probability,
pattern proportion, primary/secondary pattern과 deterministic ISUP mapping으로 구성한다.
Direct ordinal ISUP head는 병렬 sensitivity model로 유지하되 알려진 기준을 명시적으로
구현한 anchor와 frozen-FM head를 혼동하지 않는다.

### 3. Coverage와 scale

기존 outcome-blind random 64-tile subsampling을 primary에서 폐기한다. 먼저 전체 조직의
저배율 coverage를 확보하고, tumor/불확실 후보를 고배율로 계층 표집한다. 작은 암 focus와
minor high-grade pattern을 놓치지 않도록 coverage statistic을 저장한다.

두 encoder 비교에는 동일 physical FOV/crop의 공통-scale branch가 필수다. 각 encoder의 공식
pretraining/model-card 해상도를 따르는 native-scale branch를 별도로 두고, interpolation으로
생긴 scale mismatch를 공통 표현 차이로 해석하지 않는다. 모든 paired 비교는 decoded RGB와
physical boundary hash를 일치시킨다.

## Accuracy gate

### 진단 성능 anchor

Anchor가 실패하면 데이터/label/preprocessing/aggregation 문제를 먼저 해결한다. Anchor가
통과해도 frozen-FM 기능 분석을 자동 허용하지 않는다.

### Frozen-FM

- 암 유무: DiagSet-C reader 분포와 uncertain/IHC 상태를 보존한 patient/slide-clustered 평가,
  개발셋에서만 고정한 threshold, sensitivity·specificity·calibration·coverage-risk 보고
- grading: PBGG-1과 PBGG-2 각각에서 majority consensus QWK, reader별 QWK 분포, exact,
  within-one, severe error, calibration 보고
- 최소 functional-entry 기준: consensus QWK point estimate >= 0.70, patient/slide bootstrap
  lower 95% bound >= 0.60, within-one >= 0.90, severe error <= 0.05를 두 PBGG part에서 충족
- 표본이 작아 interval이 불안정하면 `not qualified`로 남기며 threshold를 완화하지 않음

PBGG 원 연구의 pathologist 분포는 임상적 context이고 위 숫자는 본 연구의 사전 고정 gate다.
Reader consensus와 individual-reader 결과를 모두 보존한다.

## 알려진 기준의 표현과 사용

정확도를 통과한 frozen encoder에만 다음을 적용한다.

1. 획득·감사된 PRECISE paired-IHC/DiagSet-A/SICAP에서 독립 truth를 갖는 criterion probe의 recoverability
2. source-fitted criterion direction의 fixed-head targeted erasure
3. 같은 rank·variance의 matched-random 100회 및 0/25/50/75/100% dose response
4. joint criterion subspace 제거와 refit-after-erasure replaceability sensitivity
5. absolute performance loss, normalized loss, Shapley/dominance allocation을 각각 bootstrap

Anchor의 GP map을 frozen representation의 “알려진 criterion truth”로 순환 사용하지 않는다.
Criterion truth는 병리 주석/IHC/reader reference에서 독립적으로 온다.

## Residual 진입

Residual은 다음을 모두 통과한 endpoint–encoder에만 연다.

- 독립 정확도 gate
- 외부 criterion recoverability
- joint targeted erasure가 matched random보다 크고 안정적인 dose response
- site/scanner/stain/MPP/tissue amount/tumor burden shortcut clearance
- localization을 볼 수 있는 권리, 병리전문의 blinded review와 adjudication protocol
- 별도 외부 코호트 및 독립 assay/omics/outcome 반복 계획

통과 후에도 결과 명칭은 Tier 4 계산 신호 → Tier 3 반복 morphology → Tier 2 분석적 검증 →
Tier 1 임상 연관/유용성 순으로 승격한다. 단계 하나를 건너뛰지 않는다.

## 실행 우선순위

1. 고정 CHIMERA-HViT source·weight·geometry·container·license preflight를 실행하고 모든
   blocker를 닫는다.
2. DiagSet 접근과 PBGG-1/2 WSI·reader table 사용 권한을 확보한다.
3. PRECISE local H&E-only legacy source의 integrity failure를 보존하고 최신 paired-IHC
   release를 별도 root에 획득·감사한다.
4. 전용 암 head, 전체조직 coverage, tumor-conditioned grading과 common/native scale을 구현한다.
5. PANDA/DiagSet 개발만으로 모든 선택을 끝낸다.
6. DiagSet-C와 PBGG-1/2를 변경 없이 연다.
7. 통과한 frozen encoder만 criterion-use 분석으로 진행한다.

## 주장 경계

PBGG/DiagSet-C 결과는 `multi-reader qualification`, 획득·감사된 PRECISE paired-IHC 결과는 `IHC-supported criterion
anchor`다. 독립적인 대규모 임상 확증 전에는 clinical-grade validity, pathologist replacement,
universal grading, 새로운 바이오마커 또는 encoder 우월성을 주장하지 않는다.

## 변경 이력

- 2026-09-02: FM8 negative gate를 보존하고, 역할별 데이터 포트폴리오와 진단 anchor/
  frozen-discovery 이중 경로로 2026-09-01 grading-only 설계를 대체했다.
- 2026-09-02: CHIMERA-HViT off-the-shelf grading anchor의 commit·weight checksum·geometry와
  claim boundary를 고정했다. 실제 preflight에서 source 계약은 통과했지만 license,
  immutable build/dependency lock, weight materialization과 D0 data access가 미해결이므로
  prediction은 계속 차단했다.
