# Milestones

P0 사전실험 후 FM0–FM10을 따른다. 상세 계획과 각 완료 기록은
`docs/research_plan/01-01-foundation-model-validation-milestones-ko.md`에
보존한다. 계획서 갱신은 각 마일스톤 완료 조건의 일부다.

상위 프로그램 계획은
`docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md`이다. 이
파일은 고정 이름을 갖는 요약 인덱스이며 상위 계획을 대체하지 않는다.

현재 운영 상태와 단일 다음 작업은
[`docs/research_plan/01-01-01-foundation-model-validation-execution-tracker-ko.md`](docs/research_plan/01-01-01-foundation-model-validation-execution-tracker-ko.md)에서 관리한다.

FM8 BCR Tier 4 계산 탐색은 완료됐다. TCGA-PRAD에서만 적합한 두
encoder별 잠재 후보를 CHIMERA에 변경 없이 적용했으나, 둘 다 acquisition/color
shortcut을 분리하지 못해 `not qualified`다. 역사적 entry-audit NO-GO는 보존하며,
Tier 3 localization·병리 검토는 계속 잠근다. 상세 결과는
[`milestones/fm8_bcr_tier4_discovery/outputs/fm8-bcr-tier4-discovery-report-ko.md`](milestones/fm8_bcr_tier4_discovery/outputs/fm8-bcr-tier4-discovery-report-ko.md)에 있다.

현재 단일 작업은 grading residual에 앞선 네 개의 순차 gate다. M1은 frozen-representation
grading accuracy, M2는 cohort-specific clinical-criterion representation, M3는 fixed-head
functional use와 usage allocation, M4는 shortcut-cleared residual entry/discovery다. PANDA는
development, SICAPv2 공식 Test는 prior-open qualification, PAR Hamamatsu는 reader-conditioned
confirmatory external cohort로 잠갔다. M1의 PANDA 10,615-slide paired embedding,
PANDA-only locked head, SICAP grading qualification과 PAR 339-slide hash/openability·paired
embedding·R1/R2/R3 confirmatory 평가를 완료했다. CONCH와 Virchow는 co-primary reader에서
모두 `ABOVE_CHANCE`였지만 둘 다 `ADEQUATE_FOR_FUNCTIONAL_TESTING`에 실패했다. 16개 PAR
평가 산출물의 clean-rerun SHA-256은 16/16 일치했다. 따라서 M1은 재현 가능한 negative
gate로 종결하고 M2--M4를 잠근다. 동일 PAR 결과를 이용한 사후 tuning은 금지하며 재개에는
새 protocol과 PAR-독립 검증 코호트가 필요하다.
상세 태스크·산출물·중단 조건은
[`grading-criterion qualification plan`](docs/plans/2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-plan.md)에 있다.

FM9는 이 negative gate를 지우지 않고 새 코호트와 새 protocol로 재개한다. 데이터는
단일 gold set이 아니라 역할별로 잠갔다: DiagSet-A/B/C는 암 유무 개발·공간 truth·9-reader
qualification, PBGG-1/2는 암 양성 multi-reader grading qualification, 최신 PRECISE release는
paired-IHC criterion anchor다. 현재 local PRECISE는 H&E-only/metadata integrity failure로
제외했다. PANDA는 개발 전용이고 PAR는 historical stress test로만 남긴다.
모델도 task-specific diagnostic performance anchor와 frozen CONCH/Virchow discovery 경로를
분리한다. 첫 off-the-shelf grading anchor인 CHIMERA-HViT의 commit, weight checksum,
geometry와 output 계약을 고정하고 fail-closed preflight를 구현했다. Source 계약은 PASS지만
license, immutable container/dependency lock, 실제 weight와 D0 data가 미해결이어서 prediction은
`NOT_READY`다. 현재 단일 다음 작업은 이 model gate와 DiagSet/PBGG/PRECISE의 membership,
patient identity/source hash를 prediction 전에 잠그는 것이다. 상세 내용은
[`FM9 plan`](docs/plans/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-plan.md)에 있다.
