---
document_id: 2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: active
created: 2026-09-02
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design.md
supersedes: projects/quantitative_foundation_model_validation/docs/plans/2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-plan.md
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm9_prostate_diagnostic_anchor_and_discovery
  - resources/artifacts/quantitative_foundation_model_validation/fm9_prostate_diagnostic_anchor_and_discovery
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm9_prostate_diagnostic_anchor_and_discovery -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# Prostate diagnostic anchor and frozen-representation discovery plan

## 의존성 규칙

FM8의 PAR 결과는 historical negative gate로 동결한다. FM9의 architecture, threshold,
sampling, scale과 stopping rule은 PANDA/DiagSet development 안에서만 선택한다. PBGG와
DiagSet-C prediction을 열고 나면 변경하려는 항목은 새 독립 코호트 없이는 exploratory다.

## D0 — 데이터 역할·접근 잠금

| Task | State | 완료 조건 |
|---|---|---|
| D0.1 역할별 portfolio registry | complete | 암 유무, grading, criterion, residual 역할과 금지 용도 명시 |
| D0.2 DiagSet 접근 | pending external access | 계정 활성화, license, A/B/C membership, 환자 mapping 확보 |
| D0.3 PBGG-1/2 접근 | pending external access | WSI와 판독표 사용 양식, reader/majority label, MD5/SHA-256 잠금 |
| D0.4 PRECISE local integrity | complete — FAIL | 25명/27 H&E WSI+27 mask, IHC 0, malformed `sub-11` row 확인; FM9 입력 금지 |
| D0.5 PRECISE paired-IHC acquisition | pending | 최신 25명/37 biopsy release의 H&E/IHC/mask/participant mapping과 hash 잠금 |
| D0.6 중복·오염 감사 | pending | PANDA/DiagSet/PBGG/PAR patient/source overlap과 prior-open 상태 기록 |

D0.2--D0.3은 계정 활성화·서명 양식 같은 외부 조치가 필요하다. 대용량 payload는 root,
예상 크기, license와 hash 계약이 고정된 뒤에만 받는다.

## D1 — 진단 성능 anchor

| Task | State | 완료 조건 |
|---|---|---|
| D1.1 exhaustive/coarse tissue coverage | pending | random 64-tile 의존 제거, 작은 focus coverage 통계 저장 |
| D1.2 전용 binary cancer model | pending | ISUP head와 분리, uncertain/IHC 상태와 abstention 구현 |
| D1.3 tumor localization | pending | 독립 pixel truth에서 sensitivity/FROC와 오류 지도 검증 |
| D1.4 criterion-explicit grading anchor | pending | cancer ROI의 GP3/4/5 map·proportion·primary/secondary→ISUP 구현 |
| D1.5 개발 gate | pending | patient/provider 분리 내부 성능·calibration·source shortcut 보고 |

Anchor 실패 시 frozen-FM에 문제가 있다고 결론 내리지 않고 데이터/coverage/label/집계 문제를
먼저 분리한다.

## D2 — frozen CONCH/Virchow 진단 경로

| Task | State | 완료 조건 |
|---|---|---|
| D2.1 common/native scale paired extraction | pending | physical boundary·decoded RGB hash 일치, encoder별 native-scale 기록 |
| D2.2 전용 frozen binary head | pending | 암 확률을 `1-P(ISUP0)`와 분리 |
| D2.3 tumor-conditioned frozen grading head | pending | cancer ROI coverage 후 ordinal/GP-aware 후보를 development에서 고정 |
| D2.4 calibration·abstention | pending | threshold/temperature/coverage rule을 development에서만 고정 |
| D2.5 immutable run lock | pending | seed, versions, folds, source/output schema, stop rule 저장 |

Anchor와 frozen head는 동일 external labels를 평가에 사용할 수 있지만 weights, feature map,
selection rule과 성능 주장은 분리한다.

## D3 — 독립 정확도 qualification

| Task | State | 완료 조건 |
|---|---|---|
| D3.1 DiagSet-C cancer evaluation | locked by D0/D2 | 9-reader와 uncertain/IHC 포함 coverage-risk, binary 성능·calibration |
| D3.2 PBGG-1 grading | locked by D0/D2 | majority와 reader별 QWK/within-one/severe error·bootstrap |
| D3.3 PBGG-2 grading | locked by D0/D2 | PBGG-1과 독립 표·gate 판정 |
| D3.4 SPROB20 transport | optional/controlled | 접근 승인 시 patient-level prevalence-aware external transport |
| D3.5 accuracy gate | locked | encoder·endpoint별 GO/NO-GO; 실패 encoder의 D4--D5 잠금 |

PBGG는 grading 전용이며 cancer detection denominator에 넣지 않는다. DiagSet-C는 작으므로
qualification이지 최종 clinical validation이 아니다.

## D4 — 알려진 병리 기준의 표현·사용·비중

| Task | State | 완료 조건 |
|---|---|---|
| D4.1 독립 criterion probes | locked by D3 | PRECISE/DiagSet-A/SICAP truth로 외부 recoverability |
| D4.2 fixed-head erasure | locked by D4.1 | 개별·joint 제거와 100 matched-random control |
| D4.3 dose response/refit | locked by D4.1 | reliance와 replaceability 분리 |
| D4.4 usage allocation | locked by D4.2 | absolute/normalized loss와 Shapley/dominance, bootstrap |
| D4.5 criterion completeness | locked by D4.2 | 알려진 panel의 설명 범위·누락 truth 명시 |

## D5 — residual discovery

| Task | State | 완료 조건 |
|---|---|---|
| D5.1 shortcut clearance | locked | site/scanner/stain/MPP/color/coverage/tumor burden 감사 |
| D5.2 residual stability | locked | fold/seed/rank/encoder/기관 반복 |
| D5.3 blinded pathology review | locked | 승인된 review packet, 반복 판독과 adjudication |
| D5.4 explicit marker definition | locked | 사람이 측정 가능한 형태·계측 rule과 분석 반복성 |
| D5.5 external/biological qualification | locked | 독립 cohort와 assay/omics/outcome 검증 |

## 현재 단일 다음 실행

DiagSet 등록·활성화와 PBGG-1/2 판독표 사용 양식을 확보하고, 다운로드 전 membership,
patient identity, license와 source-hash schema를 잠근다. 최신 PRECISE paired-IHC release도
별도 source root에 획득한다. 현재 local PRECISE는 H&E-only payload/metadata integrity failure
때문에 FM9 입력에서 제외한다. D0가 닫히기 전 외부 prediction은 만들지 않는다.
