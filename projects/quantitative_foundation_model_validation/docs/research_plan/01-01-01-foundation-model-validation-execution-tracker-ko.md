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
- Current milestone: [FM8 residual-discovery entry audit NO-GO; Scientific Reports revision 과학 작업은 종결·잠금 유지](01-01-foundation-model-validation-milestones-ko.md)
- 프로그램 핵심 목표: 복수의 독립 임상·병리 지표가 CONCH/Virchow의 frozen 표현과 locked 질병판단을 얼마나 완전하게 설명하는지 검증하고, 알려진 지표·기술적 교란을 제거한 뒤 두 모델·외부 코호트에서 반복되는 residual을 명시적 신규 정량 마커 후보로 전환·검증
- 증거 사슬: `개별 복원성 → 조건부 고유정보·포함관계 → joint completeness → 기능적 활용 → 표현·판단 residual → 명시적 지표화 → 외부·생물학적 검증`
- 현재 상태: P0와 FM1–FM5, FM6 TCGA whole-tissue 내부 pilot, 7-site holdout, LEOPARD 및 CHIMERA locked external reanalysis와 revision 원고 편입·QA를 완료했다. Site와 CHIMERA는 Virchow만 통과했고 LEOPARD는 두 encoder 모두 fail/inconclusive다. 초기 제출본은 `submission_orig/`로 보존하며 revision 과학 workstream은 현재 결과로 종결·잠금한다. 별도 후속 FM8 entry audit은 shortcut metadata 부족으로 **NO-GO**이며 FM8 본 연구는 시작하지 않았다.
- 현재 과학적 위치: TCGA 392명/80 events의 internal R/A/U는 유지된다. Site transport는 encoder-specific이고 LEOPARD 508명/87 events에서는 External T가 통과하지 않았지만, CHIMERA 95명/27 events에서는 Virchow만 모든 prespecified whole-tissue gate를 통과했다. 이는 encoder·cohort-specific external T이며 strong H2·encoder 우월성·tumor-specific mechanism·residual marker 근거가 아니다.
- 병렬 원고 workstream: PBV의 hash-locked 근거를 승계한 QFM alignment 원고를
  `기존 cohort의 지표 복원 정확성·외부 재현성 → 공통 해석 좌표의 가능성·한계`
  기조로 재편집했다. FM6의 ISUP fixed-head erasure 결과는 두 encoder에서 반복된
  `internal exploratory functional sensitivity`로 제한 승계한다. refit compensation,
  임상 증분의 불충분한 평가와 독립 domain sensitivity 미해결을 함께 보고하며 strong
  H2 claim ceiling은 변경하지 않는다. CHIMERA는 Virchow에 한한 external whole-tissue
  transport로 편입하고, Residual/unknown AI feature marker는 후속 논문으로 유지한다.
- 근거: 프로젝트 sequence, `PROJECT.yaml`, FM1–FM5 저장 산출물, FM6 entry-audit 산출물, CHIMERA acquisition 보고서·source manifest·semantic/power protocol과 governance record, FM8 entry-audit protocol·availability/shortcut/external/review matrix와 최종 NO-GO 보고서
- 주장 경계: tumor_fraction descriptive H1, FM6 internal whole-tissue R/A/U, encoder-specific site evidence와 Virchow--CHIMERA external whole-tissue T만 허용; universal External T와 strong H2=`PROHIBITED`
- 최근 결정: 1차 SICAP detector는 test specificity 0.751로 실패했다. Train-only 3-fold 후보 비교로 HED+scale를 선택해 OOF AUROC/sensitivity/specificity 0.949/0.887/0.887을 얻었고, 열린 SICAP test 참고 재평가 specificity는 0.810으로 개선됐다. 그러나 새로 잠근 PANDA 100-slide holdout의 sensitivity가 Karolinska 0.563, Radboud 0.679로 모두 0.75 미만이어서 threshold를 사후 변경하지 않고 TCGA scoring을 중단했다.
- Blocker: FM8 G4는 source/external stain·color, scanner·MPP, blur/fold/compression, tumor amount/purity, specimen metadata 부족으로 FAIL이다. G6는 pathologist 승인·burden, reviewer access와 CHIMERA patient-level image-review clearance가 없어 NOT-EVALUABLE이고, residual stability도 NOT-EVALUABLE이다. TCGA age/path-T source가 PBV generated model workspace를 가리켜 cross-project provenance readiness도 FAIL이다. 독립 tumor-detector sensitivity 실패는 tumor-specific shortcut이 배제됐다는 근거가 아니다.
- 현재 단일 다음 작업: FM8 본 분석 대신 blocker-resolution packet을 만든다. QFM-owned 또는 hash-locked shared age/path-T source와 source·external shortcut/QC metadata를 확보하고, cohort별 image-review 허용 범위와 pathologist burden·repeat/adjudication 승인을 문서화한다. Journal revision upload/public tag는 이 후속 과학 작업과 분리된 행정·release 작업이다.
- 다음 상태 전환 조건: 동일 entry-audit protocol로 G1–G7이 모두 PASS이고 residual stability와 cross-project provenance readiness가 해소된 경우에만 FM8 본 연구를 별도 두 번째 논문 workstream으로 연다. NOT-EVALUABLE은 GO로 간주하지 않는다. 논문 1 revision은 새 편집부 요구와 책임저자의 명시적 재개 결정이 없는 한 계속 잠근다.

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
- [ ] TCGA–CHIMERA endpoint equivalence·독립 tumor-region·정식 confirmatory power gate 통과
- [x] CHIMERA aggregate external functional analysis 완료·clean rerun 및 책임저자 publication-release 판단 기록
- [ ] CHIMERA 치료 공변량·semantic discrepancy·주최 측 release 확인 보강
- [ ] 추가 의료지표의 독립성·측정 반복성 gate 재평가
- [x] PBV 근거의 cross-project 소유·hash 승계 gate와 alignment main·Supplementary
  1차 전면 재편집
- [x] SICAP secondary specificity 수용·독립 domain sensitivity limitation과 FM6 internal
  ISUP functional-sensitivity 원고 scope lock
- [x] 제한적 ISUP-only 비교를 임상 증분 부재가 아닌 `증분 미확립·정식 평가 미수행`으로 교정
- [x] residual/unknown AI feature marker discovery를 후속 논문으로 분리
- [x] FM8 residual-discovery entry audit protocol과 source/artifact availability matrix 고정
- [x] `Rscore`/`Rrepr` 분리 estimand, leakage control, source threshold·sampling rule 고정
- [x] shortcut/external recurrence/blinded-review feasibility와 근거 연결 gate 판정
- [x] FM8 entry audit **NO-GO** 및 논문 1 revision 종결·잠금 유지 기록
- [ ] FM8 source/external shortcut metadata와 QFM-owned 또는 hash-locked shared provenance 보강
- [ ] residual fold/seed/rank stability 및 blinded review 승인·clearance 확보 후 entry audit 재수행
- [x] 새 scope의 main·Supplementary build, numeric/semantic·visual·governance QA
- [x] FM6 alignment 원고 종결용 locked clean rerun·20/20 nonvolatile hash와 핵심 수치 일치 감사
- [x] TCGA 7-site holdout functional transport: CONCH fail, Virchow pass, family partial 판정
- [x] LEOPARD 508명/87 events external functional transport: paired crop audit·두 encoder fail/inconclusive·exact rerun
- [x] 원고 source 19개·numeric mapping 33개 provenance 재빌드
- [x] FM6 Methods/Results 정식 편입과 Figure 2--6·Table 1·Abstract/Discussion/Conclusion의
  six-axis evidence-state 종결 정합성 감사
- [x] 연구책임자 author·affiliation·funding·ethics·journal metadata 확인과 Scientific Reports 초기 제출
- [ ] motivation-focused title·pdfLaTeX 제출본의 새 public immutable release 동기화

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

2026-08-25 FM8 entry-audit QA: source integrity 13/13과 output integrity 12/12가 통과했고,
독립 clean rerun 비교 대상 11/11의 SHA-256이 정확히 일치했다. 신규 focused test 1/1과
Python syntax check, file-governance audit가 통과했다. Project-boundary validator의 유일한
실패는 작업 시작 전부터 존재한 미등록 top-level `webportal-refactoring.md`이며 FM8 파일,
프로젝트 간 입력 또는 논문 1 변경에서 발생한 실패가 아니다.

범위 변경은 이 추적표에서 독자적으로 결정하지 않는다. 변경이 필요하면
[연구계획](01-quantitative-ai-validation-disease-diagnosis-plan-ko.md),
[마일스톤](01-01-foundation-model-validation-milestones-ko.md), 이 실행 추적표 순서로 반영한다.
