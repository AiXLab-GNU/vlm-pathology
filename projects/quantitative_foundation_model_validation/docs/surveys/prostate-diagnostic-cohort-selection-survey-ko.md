---
document_id: prostate-diagnostic-cohort-selection-survey
owner_project: quantitative_foundation_model_validation
document_type: survey
status: active
created: 2026-09-02
canonical_path: projects/quantitative_foundation_model_validation/docs/surveys/prostate-diagnostic-cohort-selection-survey-ko.md
governing_research_plan: projects/quantitative_foundation_model_validation/docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md
survey_date: 2026-09-02
databases: [official_dataset_repositories, original_publications, official_project_github]
scope: prostate_needle_biopsy_cancer_detection_grading_and_spatial_criterion_truth
inclusion_criteria: patient_or_slide_evaluation_reference_generation_access_and_license_documented
exclusion_criteria: prostatectomy_only_hidden_inaccessible_or_patch_only_for_final_wsi_accuracy
authority_status: CURRENT
supported_research_questions: [cancer_presence_accuracy, cancer_only_grading_accuracy, criterion_recoverability_and_use]
supported_baseline_or_method_decisions: [role_specific_cohort_portfolio, diagnostic_anchor_and_frozen_fm_separation]
downstream_documents:
  - projects/quantitative_foundation_model_validation/docs/designs/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design.md
  - projects/quantitative_foundation_model_validation/docs/plans/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-plan.md
---

# 전립선 biopsy 암 판정·grading 코호트 선정 서베이

## 조사 계약

- 조사일: 2026-09-02
- 검색원: 데이터셋 공식 저장소·등록부, 원 논문, 프로젝트 공식 GitHub
- 범위: H&E 전립선 needle-biopsy WSI의 암 유무, Gleason/ISUP grading, 공간 병리 기준
- 포함: 표본 수, 환자 식별/군집화, 병리 reference 생성 방식, IHC 또는 다중 판독,
  공간 주석, 접근 조건을 확인할 수 있는 코호트
- 제외: prostatectomy-only outcome 코호트, 공개되지 않은 challenge hidden test,
  patch만 있고 WSI/환자 평가를 할 수 없는 자료를 최종 정확도 코호트로 사용하는 경우
- 지원 결정: 암 유무·grading 정확도와 criterion truth를 서로 다른 역할로 잠그고,
  PAR 결과를 이용하지 않는 remediation protocol을 설계한다.
- 후속 문서: `2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design.md`

## 선정 기준

최종 순위는 크기만으로 정하지 않는다. 다음 순서로 평가한다.

1. 개발 환자와 겹치지 않는 환자 단위 독립성 및 군집화 가능성
2. 암 유무에는 IHC 보조 또는 다중 판독, grading에는 consensus/multi-reader truth
3. 알려진 병리 기준을 모델 표현과 연결할 수 있는 공간 주석
4. HGPIN·AIP·IDC-P·불확실/IHC 필요 상태를 임의로 benign/cancer에 합치지 않는 label semantics
5. immutable membership, license, 원본 hash, scanner/MPP와 실제 접근 가능성

## 후보 비교

| 코호트 | 강점 | 결정적 한계 | 잠금 역할 | 판정 |
|---|---|---|---|---|
| PANDA public development | 10,616 biopsy WSI, 대규모 ISUP 개발 | 공개 train table에 patient ID 없음; 사용 후 독립 검증이 아님 | grading·암 검출 개발만 | 유지 |
| DiagSet-A/B/C | A: 430 fully annotated scan/260만+ patch, B: 4,675 binary WSI, C: 46 WSI를 9명이 독립 판독 | 등록·계정 활성화 필요; patient mapping과 subset 중복을 획득 후 확인해야 함 | 암 유무 개발·공간 기준·다중 판독 qualification | **1순위 신규 획득** |
| PBGG-1/2 | 각 50 biopsy, 각각 10/11개 국제 판독; majority 기준 GG1--5 균형 | 암 양성만 있어 detection 평가 불가; 의도적 균형 표본; 판독표는 서명 양식으로 요청 | grading consensus external qualification | **1순위 신규 획득** |
| PRECISE paired-IHC release | 25명/37 biopsy의 paired H&E–HMWCK/AMACR IHC, 24,387개 expert annotation, 7개 병변/조직 class | 작고 합의에 도달한 선택 사례; 최신 release는 현재 local에 없음 | 암 형태 criterion/IHC anchor와 오류 분석 | **1순위 criterion 신규 획득** |
| PRECISE local legacy release | 25명/27 session의 H&E WSI 27장과 mask 27장 | IHC 파일이 없고 `sub-11` metadata 열이 어긋남; README의 paired-IHC 기술과 payload 불일치 | integrity failure 기록; 교정 전 FM9 입력 금지 | 제외/교체 |
| SICAPv2 | patient-disjoint Test, GP3/4/5와 cribriform 공간 truth | 이전 detector 작업에서 Test를 이미 열었고 표본이 작음 | 개발·preconfirmatory criterion positive control | 유지, 확증 금지 |
| PAR S-BIAD2323 | 185명/339 glass slide, 세 scanner, 독립 reader 2명과 59-slide uropathologist subset | supplied consensus와 공간 criterion truth 없음; 이미 결과 개봉 | reader/scanner-conditioned 역사적 stress test | primary truth에서 제외 |
| SPROB20 | 460 case/2,611 biopsy, 약 35% cancer, case mapping·임상 metadata·ink annotation | 492.6 GB controlled access; PhD와 기관 서명권자 계약 필요; consensus 여부 제한 | 장기적 patient-level development/transport | 접근 신청 후보 |
| PANDA-PLUS | PANDA 일부 546 WSI의 expert-crowd pixel mask와 slide grade | PANDA에서 파생되어 PANDA 학습과 독립 아님 | 개발용 criterion/localization 보강 | 선택적 개발 보조 |
| CHIMERA/TCGA-PRAD | outcome과 prostatectomy grade 보유 | needle-biopsy 암 판정·grading reference가 아님 | BCR/표본형 transport만 | 현 정확도 질문에서 제외 |

## 최종 데이터 포트폴리오

한 데이터셋으로 세 질문을 모두 답하지 않는다.

### 암 유무

- 개발/내부 잠금: PANDA와, 환자 mapping·중복 감사가 통과한 DiagSet-B
- 공간 criterion: DiagSet-A와 새로 획득·감사한 PRECISE paired H&E–IHC release
- 다중 판독 qualification: DiagSet-C의 9-reader 결과; `uncertain/need IHC`를 제3 상태로 보존
- 후속 대규모 patient-level transport: SPROB20 접근 승인 후 사용

DiagSet-C는 46 WSI이므로 단독 임상 확증 코호트가 아니다. “multi-reader truth에서의
qualification”으로만 기술하고, 최종 임상 진단 정확성에는 별도의 더 큰 untouched
multi-reader/IHC 코호트가 여전히 필요하다.

### Grading

- 개발: PANDA public development; PANDA-PLUS/SICAP Train은 공간 criterion 보조만 가능
- criterion qualification: SICAP 공식 분할과 PBGG의 reader별/majority label
- 외부 consensus qualification: PBGG-1과 PBGG-2를 서로 분리하여 각각 평가
- 역사적 스트레스 테스트: PAR는 새 모델 선택·threshold 결정에 사용하지 않음

PBGG는 암 양성, GG1--5 각 10장으로 구성된 균형 표본이다. 따라서 QWK·reader agreement에는
유용하지만 실제 유병률 기반 암 유무, PPV/NPV, calibration을 추정하지 않는다.

### 알려진 병리 기준

- 암 유무: malignant/benign gland, stroma, IDC-P, HGPIN, AIP, artifact는 최신 PRECISE
  paired-IHC release를 새로 획득·감사한 뒤 H&E–IHC 대응 기준으로 확인한다. 현재 local
  H&E-only legacy payload를 paired-IHC 근거로 사용하지 않는다.
- Grading: GP3/4/5와 cribriform은 SICAP/PANDA-derived spatial truth로 개발·양성 대조하고,
  PBGG의 primary/secondary pattern 및 reader consensus 제공 범위에서 외부 확인한다.
- 별도 truth가 없는 poorly formed/fused/glomeruloid 및 GP5 subtype은 “복원됨”으로 주장하지
  않는다.

## 접근·오염 방지 순서

1. DiagSet 계정 활성화와 PBGG 판독표 사용 조건을 확보한다.
2. WSI·label을 내려받아 원본 membership/hash와 환자 mapping을 잠근다.
3. DiagSet A/B/C 간 환자 중복과 PANDA/PBGG/PAR 중복 가능성을 감사한다.
4. 외부 label을 이용한 모델 선택을 금지하는 run config를 고정한다.
5. 그 뒤에만 prediction을 생성한다. 현재 PAR는 이미 개봉되었으므로 이 순서의 외부
   확증셋으로 재사용하지 않는다.

## 근거 자료

- [DiagSet 공식 저장소](https://github.com/michalkoziarski/DiagSet)
- [DiagSet 원 논문](https://www.nature.com/articles/s41598-024-52183-4)
- [PBGG-1 Zenodo](https://zenodo.org/records/8102833)
- [PBGG-2 Zenodo](https://zenodo.org/records/8102929)
- [PBGG 연계 다기관 검증 논문](https://www.nature.com/articles/s41698-023-00424-6)
- [PRECISE 기술 논문](https://www.medrxiv.org/content/10.64898/2026.07.21.26358559v1.full)
- [SPROB20 AIDA 등록부](https://datahub.aida.scilifelab.se/10.23698/aida/sprob20)
- [PANDA challenge 원 논문](https://www.nature.com/articles/s41591-021-01620-2)

## 해석 한계

공개 데이터만으로 “임상 배치 가능한 최종 성능”을 확정할 수는 없다. DiagSet-C는 작고,
PBGG는 암 양성 균형 표본이며, PRECISE paired-IHC는 획득 후 criterion anchor다. 이 포트폴리오는 현재 공개·접근
가능 후보 중 연구 질문을 가장 정직하게 분해하지만, 마지막 임상 확증에는 새 대규모
untouched multi-reader 또는 IHC-adjudicated biopsy cohort가 필요하다.
