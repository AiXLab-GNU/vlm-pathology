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
- Current milestone: [FM9 D1.0 reproducible anchor preflight 구현·NOT READY; D0 접근과 FM8 negative gate 유지](01-01-foundation-model-validation-milestones-ko.md)
- 프로그램 핵심 목표: 복수의 독립 임상·병리 지표가 CONCH/Virchow의 frozen 표현과 locked 질병판단을 얼마나 완전하게 설명하는지 검증하고, 알려진 지표·기술적 교란을 제거한 뒤 두 모델·외부 코호트에서 반복되는 residual을 명시적 신규 정량 마커 후보로 전환·검증
- 증거 사슬: `개별 복원성 → 조건부 고유정보·포함관계 → joint completeness → 기능적 활용 → 표현·판단 residual → 명시적 지표화 → 외부·생물학적 검증`
- 현재 상태: P0와 FM1–FM8의 산출물·negative gate는 보존한다. 2026-09-02 FM9 remediation에서 DiagSet-A/B/C를 암 유무 개발·공간 truth·9-reader qualification, PBGG-1/2를 암 양성 multi-reader grading qualification, 최신 PRECISE release를 paired-IHC criterion anchor로 잠갔다. Local PRECISE preflight는 25명/27 H&E WSI+27 mask, IHC 0과 malformed `sub-11` row로 FAIL하여 FM9 입력에서 제외했다. PANDA는 development-only, SICAP은 prior-open positive control, PAR는 이미 개봉된 historical reader/scanner stress다. Task-specific diagnostic anchor와 frozen CONCH/Virchow discovery를 분리하고, 전용 binary cancer head, 전체조직 coverage, tumor-conditioned grading 및 common/native scale을 고정했다. CHIMERA-HViT off-the-shelf grading anchor의 source commit, weight checksum, 0.5 mpp/2048/256 geometry와 5-fold/960-d output 계약 및 fail-closed preflight를 구현했다. Source 계약은 PASS지만 license, immutable build/dependency lock, weight materialization과 D0 data gate가 BLOCKED이므로 새 prediction은 만들지 않았다. 논문 1은 종결·잠금을 유지한다.
- 현재 과학적 위치: TCGA 392명/80 events의 internal R/A/U와 Virchow--CHIMERA encoder-specific external T는 유지된다. FM8 BCR source-only nested 분석에서는 CONCH와 Virchow 후보가 각각 TCGA/CHIMERA latent C-index 0.615/0.659와 0.620/0.658, ISUP baseline 대비 additive delta +0.017/+0.036과 +0.012/+0.053을 보였다. 그러나 두 후보 모두 shortcut 감사에 실패해 `not qualified`이며, whole-tissue Tier 4 계산 가설을 넘어선 residual marker 근거가 아니다.
- 병렬 원고 workstream: PBV의 hash-locked 근거를 승계한 QFM alignment 원고를
  `기존 cohort의 지표 복원 정확성·외부 재현성 → 공통 해석 좌표의 가능성·한계`
  기조로 재편집했다. FM6의 ISUP fixed-head erasure 결과는 두 encoder에서 반복된
  `internal exploratory functional sensitivity`로 제한 승계한다. refit compensation,
  임상 증분의 불충분한 평가와 독립 domain sensitivity 미해결을 함께 보고하며 strong
  H2 claim ceiling은 변경하지 않는다. CHIMERA는 Virchow에 한한 external whole-tissue
  transport로 편입하고, Residual/unknown AI feature marker는 후속 논문으로 유지한다.
- 근거: 프로젝트 sequence, `PROJECT.yaml`, FM1–FM5 저장 산출물, FM6 entry-audit 산출물, CHIMERA acquisition 보고서·source manifest·semantic/power protocol과 governance record, FM8 역사적 entry-audit NO-GO 보고서, FM8 Tier 4 design·protocol·input/provenance·성능·effect·fold·candidate·shortcut source table과 clean-rerun 비교
- 주장 경계: tumor_fraction descriptive H1, FM6 internal whole-tissue R/A/U, encoder-specific site evidence와 Virchow--CHIMERA external whole-tissue T, FM8의 `whole-tissue Tier 4 computational hypothesis not qualified`만 허용; universal External T, strong H2, Tier 3 marker, morphology/tumor-specific mechanism과 임상 증분=`PROHIBITED`
- 최근 결정: 1차 SICAP detector는 test specificity 0.751로 실패했다. Train-only 3-fold 후보 비교로 HED+scale를 선택해 OOF AUROC/sensitivity/specificity 0.949/0.887/0.887을 얻었고, 열린 SICAP test 참고 재평가 specificity는 0.810으로 개선됐다. 그러나 새로 잠근 PANDA 100-slide holdout의 sensitivity가 Karolinska 0.563, Radboud 0.679로 모두 0.75 미만이어서 threshold를 사후 변경하지 않고 TCGA scoring을 중단했다.
- Blocker: CHIMERA-HViT locked commit에는 명시적 license 파일이 없고 upstream Dockerfile은 digest가 아닌 base-image tag와 부분 고정 requirements를 사용한다. Weight 10개도 아직 local materialization/hash verification 전이다. 별도로 DiagSet은 등록·관리자 활성화와 patient/subset mapping 확인이 필요하고, PBGG reader table은 작성한 사용 양식으로 별도 요청해야 하며 최신 PRECISE paired-IHC release도 아직 local에 없다. SPROB20은 기관 서명권자의 controlled-access 계약이 필요하다.
- 현재 단일 다음 작업: CHIMERA-HViT의 명시적 license/서면 허가를 확인하고 digest/dependency-locked build와 10개 weight hash를 닫는다. 동시에 DiagSet 계정을 활성화하고 PBGG-1/2 grading-result 사용 양식 및 최신 PRECISE paired-IHC release를 확보해 membership, patient identity, label semantics와 source hash를 잠근다.
- 다음 상태 전환 조건: D0 access·identity·overlap·hash gate가 통과하면 diagnostic anchor와 frozen-FM 경로를 분리 구현한다. DiagSet-C/PBGG 결과를 보기 전에 sampling, scale, threshold, calibration과 stop rule을 고정하며, 독립 accuracy와 joint criterion erasure를 모두 통과하기 전 residual은 열지 않는다. BCR Tier 3와 논문 1 잠금은 별도로 유지한다.

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
- [x] 역사적 FM8 entry-audit NO-GO와 별도 Tier 4 계산/Tier 3 병리 gate 분리
- [x] TCGA 392명/80 events source-only nested fitting과 환자 단위 OOF·leakage 감사
- [x] CHIMERA 95명/27 events 무튜닝 locked external transport 및 2,000회 환자 bootstrap
- [x] CONCH/Virchow 후보 registry와 standalone·complementary·interactive·redundant 역할 판정
- [x] Available QC/color 기반 shortcut 감사와 두 후보 `not_qualified_shortcut_unresolved` 판정
- [x] BCR/cancer presence/grading endpoint lane 분리 및 후자 두 lane `NOT_READY` 기록
- [x] FM8 Tier 4 독립 clean rerun과 nonvolatile output hash 비교
- [x] PANDA development·SICAP criterion qualification·PAR external·CHIMERA secondary transport 역할 잠금
- [x] Grading criterion과 BCR prognostic covariate 분리
- [x] PAR public label/file-list 확보·hash lock과 reader agreement 감사
- [x] PANDA mask 추출·archive/source inventory hash lock 완료
- [x] PANDA 10,616 WSI outcome-blind tile preparation; 10,615 eligible/1 insufficient-tissue 명시
- [x] SICAP 공식 Test 21명/31 slide/2,122 patch paired CONCH·Virchow embedding과 crop-hash 일치
- [x] PAR primary Hamamatsu WSI 339개 acquisition·openability·hash audit
- [x] M1.3 QFM-owned PANDA/PAR CONCH·Virchow embedding 생성과 paired crop-hash audit
- [x] M1.4 PANDA-only gated-attention ordinal MIL grading head lock
- [x] M1.5 PANDA development diagnostic 산출(외부 근거로 승격 금지)
- [x] M1.6 SICAP prior-open qualification grading accuracy 무튜닝 평가
- [x] M1.7 PAR R1/R2 co-primary·R3 subset confirmatory grading accuracy 무튜닝 평가
- [x] M1.8 accuracy gate 판정·16/16 nonvolatile output hash clean rerun
- [ ] M2 clinical criterion recoverability 실행 — M1 adequacy 실패로 잠금
- [ ] M3 joint erasure·negative control·dose response·usage allocation 실행 — M1 adequacy 실패로 잠금
- [x] Grading residual entry gate 재판정 — `NO_GO_FUNCTIONAL_INTERPRETATION_NO_GO_RESIDUAL`
- [x] FM9 DiagSet/PBGG/PRECISE 역할별 데이터 포트폴리오 선정과 금지 용도 잠금
- [x] Task-specific diagnostic anchor와 frozen CONCH/Virchow discovery 경로 분리 설계
- [x] 전용 cancer head, 전체조직 coverage, tumor-conditioned grading, common/native scale protocol 고정
- [x] CHIMERA-HViT off-the-shelf/retrained ID 분리와 source commit·weight checksum·geometry/output registry 고정
- [x] FM9 diagnostic-anchor fail-closed preflight 구현·source 계약 PASS 확인
- [ ] CHIMERA-HViT 명시적 license/permission·digest/dependency-locked build·10개 local weight hash PASS
- [ ] DiagSet registration·activation·patient/subset overlap·source hash 확보
- [ ] PBGG-1/2 WSI와 grading-result request 조건·reader/majority label hash 확보
- [x] PRECISE local integrity 재감사 — 25명/27 H&E WSI+27 mask, IHC 0, malformed `sub-11`; FM9 입력 제외
- [ ] 최신 PRECISE 25명/37 biopsy paired-IHC release 획득·pairing/mask/hash 감사
- [ ] FM9 diagnostic anchor와 frozen-FM 구현·development-only lock
- [ ] DiagSet-C cancer 및 PBGG-1/2 grading independent qualification
- [ ] FM8 BCR shortcut alert와 NOT-EVALUABLE acquisition/tumor metadata 해소
- [ ] FM8 Tier 3 localization·병리 review 권한·승인·외부 형태 반복 gate 통과
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

2026-09-01 FM8 BCR Tier 4 QA: input integrity 25행과 provenance 10행이 통과했고,
`primary`와 독립 `clean` 실행의 protocol-defined nonvolatile 산출물 SHA-256은 9/9 정확히
일치했다. 두 실행은 별도 tmux session에서 CPU-only로 종료 코드 0을 기록했다. QFM 전체
회귀검사는 125/125, Python syntax, file-governance와 worktree audit, `git diff --check`는
모두 통과했다. Project-boundary validator의 유일한 실패는 이번 작업과 무관한 기존 미등록
top-level `webportal-refactoring.md`다. 논문 1 경로에는 변경을 만들지 않았다.

범위 변경은 이 추적표에서 독자적으로 결정하지 않는다. 변경이 필요하면
[연구계획](01-quantitative-ai-validation-disease-diagnosis-plan-ko.md),
[마일스톤](01-01-foundation-model-validation-milestones-ko.md), 이 실행 추적표 순서로 반영한다.

2026-09-02 FM9 anchor preflight QA: 공식 source commit
`2b17a75891e8f017e7a92201509c63770cd39fe5`, upstream 10개 weight checksum, 0.5
micrometre/pixel·2048/256-pixel geometry, 5-fold ISUP 0--5와 960차원 latent 계약이 registry와
일치했다. Base image digest는
`sha256:b2a0cc0217aa152e507150e341b9ac7695c226599c9d4af0d74b01be67186eab`로
해결했지만 upstream Dockerfile에는 아직 tag로 남아 있다. License, dependency lock, 실제
weight와 D0 data가 미해결이라 `prediction_permitted=false`로 닫았다. Focused tests 6/6과
Python syntax check가 통과했다. Preflight JSON의 독립 재실행 SHA-256은 두 번 모두
`f15e3ebe277d3d8b6f4658e4c86bb7b4e04ef814441803a210a7a3409148d112`로 일치했다.
