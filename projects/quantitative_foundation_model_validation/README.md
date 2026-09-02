# Quantitative Foundation-Model Validation

## 핵심 목표

동일 환자·동일 조직에서 독립적으로 측정한 **복수의 임상·병리 정량지표**가
CONCH와 Virchow의 frozen representation과 locked 질병예측 판단을 얼마나 완전하게
설명하는지 규명한다. 이어서 알려진 지표와 기술적 교란을 제거한 뒤에도 두
모델과 독립 외부 코호트에서 반복되는 residual morphology를 병리의가 감사할 수
있는 명시적 정량지표로 전환하고, 독립 assay·omics·임상 outcome으로 신규 마커
후보의 타당성을 검증한다.

이를 다음 증거 사슬로 구분한다.

1. **H1—복원성:** 사람의 정량지표가 각 frozen embedding에서 복원되는가?
2. **포함관계·완전성:** 복수 지표의 조합이 AI 표현과 판단을 얼마나 설명하는가?
3. **H2—기능적 활용:** 지표 관련 표현을 선택적으로 제거하면 locked disease head가
   matched control보다 더 저하되는가?
4. **Residual 발견:** 설명되지 않은 신호 중 모델·기관을 넘어 반복되는 병리 형태가 있는가?
5. **마커 전환:** 반복 형태를 측정 가능한 지표로 정의하고 외부·생물학적으로 검증할 수 있는가?

CONCH와 Virchow는 우열을 가리기 위한 대상이 아니라, 사전학습 방식이 다른 두 독립
측정기로 사용한다. 공통 신호와 모델 특이·기술적 신호를 분리하는 것이 목적이다.

## 현재 운영 범위

P0와 FM1–FM5는 완료되었다. FM6에서는 TCGA 392명/80 events의 whole-tissue 내부
ISUP 기능 민감도가 두 encoder에서 관찰됐고, 7-site holdout은 Virchow만 통과했다.
508명/87 events LEOPARD locked reanalysis에서는 두 encoder 모두 external transport
gate를 통과하지 못했다. CHIMERA 95명/27 events의 사전등록 whole-tissue 분석에서는
두 encoder 모두 ISUP 방향과 양의 targeted-erasure 효과를 보였으나, 유효한 BCR head와
matched-control gate까지 모두 통과한 것은 Virchow뿐이었다. 따라서 external T는
Virchow--CHIMERA에 한정한 encoder-specific evidence로 허용한다. Strong H2, encoder 우월성,
tumor-specific mechanism, 임상 증분과 신규 biomarker 주장은 계속 금지한다.

P0부터 FM/H2까지의 진행 순서는 [`00-project-sequence/`](00-project-sequence/)에서
번호순으로 확인한다.

별도 FM8 workstream에서는 역사적 entry-audit NO-GO를 보존한 채, frozen paired
embedding과 이용 가능한 QC만 요구하는 BCR Tier 4 계산 탐색을 분리해 수행했다.
TCGA-PRAD 392명/80 events에서만 nested fitting한 encoder별 잠재 점수를 CHIMERA
95명/27 events에 변경 없이 적용했다. CONCH와 Virchow 후보 모두 standalone 및
ISUP baseline 대비 complementary 계산 신호를 보였지만, source site/scanner와 external
color 연관 또는 잔여 ISUP 연관 때문에 shortcut 감사에 실패했다. 따라서 두 후보는
`not qualified`이고 whole-tissue Tier 4 가설일 뿐이다. 좌표 localization, morphology
명명, 병리전문의 검토와 Tier 3 승격은 계속 금지한다.

현재는 grading residual보다 먼저 M1 accuracy, M2 criterion representation, M3 functional
use/allocation, M4 shortcut-cleared residual의 네 순차 gate를 운영한다. PANDA 공개 10,616
biopsy는 development 전용, SICAPv2 공식 patient-disjoint Test는 prior-open qualification,
PAR 185명/339 biopsy Hamamatsu는 reader-conditioned confirmatory external cohort, CHIMERA는
prostatectomy/BCR secondary transport로 역할을 고정했다. M1에서 PANDA 10,615 eligible
slide의 paired embedding과 PANDA-only locked head, SICAP 21명/31 slide qualification,
PAR 185명/339 slide의 hash/openability·paired embedding·R1/R2/R3 confirmatory 평가를
완료했다. CONCH와 Virchow 모두 co-primary reader에서 chance를 초과했지만 사전 고정
adequacy 기준을 통과하지 못했다. 따라서 M1은 negative gate로 종결하며 M2--M4는 새
protocol과 PAR-독립 검증 코호트가 마련될 때까지 잠근다.

2026-09-02에 PAR 결과를 사용하지 않는 FM9 remediation 설계를 승인했다. 암 유무에는
DiagSet-A/B/C, grading에는 PBGG-1/2, 독립 병리 criterion에는 최신 PRECISE paired H&E–IHC release를
우선 포트폴리오로 선정했다. PANDA는 개발, SICAP은 prior-open positive control, PAR는
historical reader/scanner stress로 제한한다. 또한 task-specific 진단 성능 anchor와 frozen
CONCH/Virchow discovery를 분리하며, 전용 binary cancer head, 전체조직 coverage,
tumor-conditioned grading과 common/native scale을 새 구조로 고정했다. 외부 데이터 접근·hash
잠금 전에는 prediction을 열지 않는다.
현재 local PRECISE 사본은 25명/27 H&E WSI와 mask만 있고 IHC가 없으며 `sub-11` metadata가
malformed라서 FM9 입력에서 제외했다. 최신 paired-IHC release는 별도 획득 대상이다.

첫 재현 가능한 grading 양성 대조군으로 DIAGNijmegen CHIMERA-HViT의 source commit,
`weights-v1` SHA-256 10개, 0.5 micrometre/pixel 및 2048/256-pixel geometry와 5-fold/960-d
output 계약을 고정하고 fail-closed preflight를 구현했다. Source 계약은 일치했지만 명시적
license, digest/dependency-locked build, 실제 weight hash와 D0 external data가 아직 미해결이므로
상태는 `NOT_READY`이며 prediction은 생성하지 않았다. 이 모델은 grading 양성 대조군일 뿐
전용 암 판정기나 frozen CONCH/Virchow feature-use 근거가 아니다.

- 현재 상태: [실행 추적표](docs/research_plan/01-01-01-foundation-model-validation-execution-tracker-ko.md)
- 연구계획: [canonical plan](docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md)
- 마일스톤: [canonical milestones](docs/research_plan/01-01-foundation-model-validation-milestones-ko.md)
- 관련연구: [survey index](docs/surveys/README.md)
- 결과: [report index](reports/README.md)
- FM8 Tier 4 결과: [BCR discovery report](milestones/fm8_bcr_tier4_discovery/outputs/fm8-bcr-tier4-discovery-report-ko.md)
- FM8 grading gate: [grading-criterion entry audit](milestones/fm8_grading_criterion_qualification/outputs/fm8-grading-criterion-qualification-entry-report-ko.md)
- FM8 grading M1 결과: [CONCH·Virchow accuracy report](milestones/fm8_grading_criterion_qualification/outputs/fm8-grading-accuracy-report-ko.md)
- FM9 데이터 선정: [cohort selection survey](docs/surveys/prostate-diagnostic-cohort-selection-survey-ko.md)
- FM9 수정 구조: [diagnostic anchor/discovery design](docs/designs/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design.md)
- FM9 모델 잠금: [diagnostic model registry](manifests/fm9_diagnostic_model_registry.yaml)
- 논문: [paper entry point](paper/README.md)

## 재현

프로젝트에 필요한 공개·credentialed·restricted·custodian 자산과 실행 DAG는 저장소 공통
registry에 고정되어 있다.

```bash
.venv/bin/python infrastructure/scripts/reproduce_repository.py status \
  --project quantitative_foundation_model_validation
.venv/bin/python infrastructure/scripts/reproduce_repository.py plan \
  --project quantitative_foundation_model_validation
```

FM6 TCGA-PRAD는 `resources/data/manifests/tcga_prad_gdc_files.csv`의 437개 공개 GDC
UUID/size/MD5 snapshot을 사용한다. CONCH와 Virchow도 registry의 exact revision과 weight
SHA-256을 사용한다. P0/FM1–FM5 전체 재실행에는 PRECISE 공개 WSI 외에도 원 연구의
병리의 판독·잠금 exclusion과 PBV에서 생성된 NADT/LEOPARD frozen cache가 필요하다.
이 제한 자산이 없으면 CLI는 해당 단계를 재현 가능하다고 표시하지 않는다.
