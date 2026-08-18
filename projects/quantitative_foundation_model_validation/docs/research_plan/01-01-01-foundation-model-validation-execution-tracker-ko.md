---
document_id: foundation-model-validation-execution-tracker
owner_project: quantitative_foundation_model_validation
document_type: execution_tracker
status: active
created: 2026-08-13
canonical_path: projects/quantitative_foundation_model_validation/docs/research_plan/01-01-01-foundation-model-validation-execution-tracker-ko.md
hierarchy_id: 01-01-01
parent_document: projects/quantitative_foundation_model_validation/docs/research_plan/01-01-foundation-model-validation-milestones-ko.md
---

# 정량 기반모델 검증 실행 추적표

- Governing research plan: [01-quantitative-ai-validation-disease-diagnosis-plan-ko.md](01-quantitative-ai-validation-disease-diagnosis-plan-ko.md)
- Current milestone: [FM6 clean-rerun 원고 편입·six-axis evidence-state 종결 완료; author-controlled metadata handoff](01-01-foundation-model-validation-milestones-ko.md)
- 프로그램 핵심 목표: 복수의 독립 임상·병리 지표가 CONCH/Virchow의 frozen 표현과 locked 질병판단을 얼마나 완전하게 설명하는지 검증하고, 알려진 지표·기술적 교란을 제거한 뒤 두 모델·외부 코호트에서 반복되는 residual을 명시적 신규 정량 마커 후보로 전환·검증
- 증거 사슬: `개별 복원성 → 조건부 고유정보·포함관계 → joint completeness → 기능적 활용 → 표현·판단 residual → 명시적 지표화 → 외부·생물학적 검증`
- 현재 상태: P0와 FM1–FM5 및 FM6 TCGA whole-tissue 내부 pilot 완료; 독립 detector 1차·train-only remediation을 실행했으나 새 PANDA holdout sensitivity gate 실패로 tumor-restricted H2와 T는 잠금. 원고는 SICAP secondary specificity를 내부 근거로 수용하고 domain limitation을 명시하는 scope로 고정
- 현재 과학적 위치: shared 394.24 µm `tumor_fraction` 내부 H1과 별도로, TCGA 392명/80 events에서 두 encoder의 ISUP recoverability·BCR head·ISUP-correlated fixed-head sensitivity를 내부 개발 수준으로 관찰했다. 이는 whole-tissue R/A/U exploratory evidence이며 strong H2·external transport·residual marker 근거가 아님
- 병렬 원고 workstream: PBV의 hash-locked 근거를 승계한 QFM alignment 원고를
  `기존 cohort의 지표 복원 정확성·외부 재현성 → 공통 해석 좌표의 가능성·한계`
  기조로 재편집했다. FM6의 ISUP fixed-head erasure 결과는 두 encoder에서 반복된
  `internal exploratory functional sensitivity`로 제한 승계한다. refit compensation,
  임상 증분의 불충분한 평가와 독립 domain sensitivity 미해결을 함께 보고하며 strong
  H2 claim ceiling은 변경하지 않는다. Residual/unknown AI feature marker는 후속 논문이다.
- 근거: 프로젝트 sequence, `PROJECT.yaml`, FM1–FM5 저장 산출물, FM6 entry-audit 산출물, CHIMERA acquisition 보고서·source manifest·semantic/power protocol과 governance record
- 주장 경계: tumor_fraction 내부 descriptive H1과 FM6 `internal whole-tissue R/A/U exploratory evidence`만 허용; T와 strong H2는 금지
- 최근 결정: 1차 SICAP detector는 test specificity 0.751로 실패했다. Train-only 3-fold 후보 비교로 HED+scale를 선택해 OOF AUROC/sensitivity/specificity 0.949/0.887/0.887을 얻었고, 열린 SICAP test 참고 재평가 specificity는 0.810으로 개선됐다. 그러나 새로 잠근 PANDA 100-slide holdout의 sensitivity가 Karolinska 0.563, Radboud 0.679로 모두 0.75 미만이어서 threshold를 사후 변경하지 않고 TCGA scoring을 중단했다.
- Blocker: detector의 cross-domain calibration/sensitivity, TCGA–CHIMERA PSA threshold·censoring equivalence와 CHIMERA publication embargo가 남는다. AI risk–tissue fraction rho 0.324/0.341은 whole-tissue composition confounding 가능성을 보인다. AGE·path-T는 보조 임상축일 뿐 독립 병리 metric family가 아니므로 복수 독립 병리지표 completeness도 미완료다.
- 현재 단일 다음 작업: 연구책임자가 author·affiliation·funding·ethics·journal format과 submission-specific release tag/commit/DOI를 확인하고 원고 submission status를 판정한다. 과학 수치와 claim ceiling은 더 이상 재튜닝하지 않는다.
- 다음 상태 전환 조건: author-controlled metadata와 공개 code/data release 위치가 확정되면 제출 패키지를 생성한다. Multi-domain detector·제3 acquisition-domain holdout과 residual marker 연구는 현재 원고와 분리된 후속 workstream으로 둔다.

## 완료 체크리스트

- [x] P0 feasibility와 clean-rerun handoff
- [x] FM1 metric eligibility
- [x] FM2 paired manifest
- [x] FM3 paired embeddings
- [x] FM4 descriptive-only scope 승인
- [x] 승인 범위 내 concept benchmark 실행
- [x] FM4 clean rerun과 source/output hash 감사
- [x] FM5 descriptive cross-model comparison 범위 고정
- [x] 기존 P0-G8/G9·FM4 승인 범위 확인
- [x] 승인 범위 FM5 실행·clean rerun
- [x] 핵심 목표와 단계별 증거 사슬을 상위 연구계획·마일스톤·실행 추적표에 동기화
- [x] ISUP grade group–BCR source-level 진입 적격성 감사
- [x] CHIMERA Task 1 외부 ISUP/Gleason–BCR source 확보·hash 등록·semantic QC flag 고정
- [x] TCGA-PRAD current-GDC BCR의 QFM development source package·remote WSI UUID 고정
- [x] TCGA development eligible WSI 143장 확보·437장 source size/GDC MD5 clean rerun
- [x] TCGA WSI outcome-blind header·thumbnail·MPP QC, 물리 FOV·patient aggregation·5-fold 고정
- [x] TCGA whole-tissue paired CONCH/Virchow embedding·BCR head·ISUP probe·variance-matched erasure pilot와 clean rerun
- [x] 내부 R/A/U exploratory 판정과 effect 기반 external power planning input 산출
- [x] outcome·ISUP·FM과 독립인 SICAP pixel-mask detector 1차 감사와 사전 고정 중단 규칙 적용
- [x] train-only 3-fold hyperparameter remediation과 미개봉 PANDA 100-slide holdout 감사
- [ ] multi-domain detector·제3 독립 pixel-annotation holdout gate 통과
- [ ] TCGA–CHIMERA endpoint equivalence·독립 tumor-region·정식 external power gate 통과
- [ ] CHIMERA 치료·semantic discrepancy·publication embargo gate 해소
- [ ] 추가 의료지표의 독립성·측정 반복성 gate 재평가
- [x] PBV 근거의 cross-project 소유·hash 승계 gate와 alignment main·Supplementary
  1차 전면 재편집
- [x] SICAP secondary specificity 수용·독립 domain sensitivity limitation과 FM6 internal
  ISUP functional-sensitivity 원고 scope lock
- [x] 제한적 ISUP-only 비교를 임상 증분 부재가 아닌 `증분 미확립·정식 평가 미수행`으로 교정
- [x] residual/unknown AI feature marker discovery를 후속 논문으로 분리
- [x] 새 scope의 main·Supplementary build, numeric/semantic·visual·governance QA
- [x] FM6 alignment 원고 종결용 locked clean rerun·20/20 nonvolatile hash와 핵심 수치 일치 감사
- [x] 원고 source 19개·numeric mapping 33개 provenance 재빌드
- [x] FM6 Methods/Results 정식 편입과 Figure 2--6·Table 1·Abstract/Discussion/Conclusion의
  six-axis evidence-state 종결 정합성 감사
- [ ] 연구책임자 author·affiliation·funding·ethics·journal/release metadata handoff

2026-08-17 locked clean-rerun QA: FM6 analysis nonvolatile output hash 20/20과 두 encoder의
핵심 수치·R/A/U/T 판정이 기존 기준선과 일치했다. Alignment manuscript builder는 source
19/19와 headline numeric mapping 33/33을 검증했고 Main 22쪽·Supplementary 13쪽을
재생성했다. 이후 FM6 clean-rerun 근거와 phenotype reference·SPOP available-label 경계를
Methods, Results, Discussion, Conclusion, Table 1, Figure 2--6과 Supplementary에 편입했다.
최종 QFM project tests 92/92와 worktree audit가 통과했다. File-governance는 활성
마일스톤 문서의 terminal hash를 동기화한 뒤 재감사하며, boundary validator의 기존
top-level `webportal-refactoring.md` 미등록 항목은 본 과제와 무관한 예외로 남긴다.
PBV 원본 tests는 322/323이 통과했고, 유일한 실패는 현재 NRF/GNU Funding 선언문과 과거
ICT funding 기대 문구의 기존 불일치로 이번 FM6 rerun 또는 QFM 원고 변경과 무관하다.

범위 변경은 이 추적표에서 독자적으로 결정하지 않는다. 변경이 필요하면
[연구계획](01-quantitative-ai-validation-disease-diagnosis-plan-ko.md),
[마일스톤](01-01-foundation-model-validation-milestones-ko.md), 이 실행 추적표 순서로 반영한다.
