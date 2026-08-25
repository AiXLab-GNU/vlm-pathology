# Quantitative foundation-model validation sequence

이 디렉터리는 프로젝트의 단계별 진입점이다. 번호는 연구 진행 순서이고, 링크 대상은
재현성을 위해 유지하는 canonical 폴더다.

| 순서 | 단계 | 현재 상태 | 주 폴더·문서 | 완료/진입 기준 |
|---:|---|---|---|---|
| 00 | 목적·H1/H2·claim boundary 확인 | 상시 | [`../README.md`](../README.md), [`../CLAIM_BOUNDARIES.md`](../CLAIM_BOUNDARIES.md) | 의료지표와 모델 평가량 분리 |
| 01 | 지표 체계·연구계획 | 완료/갱신 중 | [`01` 연구계획](../docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md), [`01-01` 마일스톤](../docs/research_plan/01-01-foundation-model-validation-milestones-ko.md), [`01-01-01` tracker](../docs/research_plan/01-01-01-foundation-model-validation-execution-tracker-ko.md), [`01-02` 지표 체계](../docs/metric_taxonomy/01-02-medical-quantitative-metric-tier-taxonomy-ko.md), [`survey index`](../docs/surveys/README.md) | T1–T4와 outcome 정의 |
| 02 | P0 사전실험·G8/G9 handoff | 완료 | [`../preexperiment/`](../preexperiment/) | clean rerun과 scope-capped handoff |
| 03 | FM1 지표 적격성 | 완료 | [`../milestones/fm1_metric_eligibility/`](../milestones/fm1_metric_eligibility/) | H1/H2 eligibility와 독립성 감사 |
| 04 | FM2 paired manifest | 완료 | [`../milestones/fm2_paired_manifest/`](../milestones/fm2_paired_manifest/) | membership·truth·FOV·fold 일치 |
| 05 | FM3 paired embeddings | 완료 | [`../milestones/fm3_paired_embeddings/`](../milestones/fm3_paired_embeddings/) | 두 encoder row/hash reconciliation |
| 06 | FM4 concept benchmark | 완료 | [`../milestones/fm4_concept_benchmark/`](../milestones/fm4_concept_benchmark/), [`FM4 report`](../milestones/fm4_concept_benchmark/outputs/fm4-concept-benchmark-report.md) | 승인 범위 실행·OOF 저장·clean rerun 일치 |
| 07 | FM5 cross-model comparison | 완료 | [`FM5 report`](../milestones/fm5_cross_model_comparison/outputs/fm5-cross-model-comparison-report.md), [`FM5 entry packet`](../milestones/fm5_cross_model_comparison/outputs/fm5-entry-packet.md) | 기존 승인 범위 실행·paired uncertainty·9/9 clean rerun 일치 |
| 08 | 추가 의료지표 확장 | 잠금 | [`../metric_registry/`](../metric_registry/), [`../code/`](../code/) | 반복성 있는 독립 truth 확보 |
| 09 | H2 기능적 질병예측 검증 | whole-tissue internal 완료; site-heldout는 encoder-specific partial; LEOPARD는 두 encoder fail/inconclusive; CHIMERA는 Virchow만 모든 external gate 통과; strong H2 잠금 | [`FM6 internal pilot report`](../milestones/fm6_internal_development_pilot/outputs/fm6-tcga-internal-development-pilot-report.md), [`site-heldout report`](../milestones/fm6_site_heldout_functional_validation/outputs/fm6-site-heldout-functional-xai-report.md), [`LEOPARD report`](../milestones/fm6_external_functional_validation/outputs/fm6-leopard-external-functional-xai-report.md), [`CHIMERA report`](../milestones/fm6_chimera_external_functional_validation/outputs/fm6-chimera-external-functional-xai-report.md), [`CHIMERA protocol`](../docs/protocols/fm6-chimera-external-functional-xai-protocol-ko.md), [`tumor detector audit`](../milestones/fm6_tumor_region_detector_audit/outputs/fm6-tumor-region-detector-audit-report.md), [`../MILESTONES.md`](../MILESTONES.md) | Author release determination 기록; aggregate 결과만 원고 승격; target-cohort tuning 금지; encoder-specific whole-tissue ceiling 유지 |
| 10 | 보고·논문 | **Scientific Reports 초기 제출 완료; CHIMERA 포함 revision 과학 작업 완료·종결**; Main 18쪽·Supplement 15쪽 hash-locked working copy | [`../reports/`](../reports/), [`paper workspace`](../paper/evidence-qualified-alignment-prostate-cancer/), [`submission handoff`](../paper/evidence-qualified-alignment-prostate-cancer/submission-handoff.md), [`last public release`](https://github.com/AiXLab-GNU/evidence-qualified-alignment-prostate-cancer/tree/v1.0.6-submission), [`revision designs`](../docs/designs/) | 초기 제출본은 `submission_orig/`로 보존; 추가 과학 편집·실험 금지; revision public tag와 journal 재제출은 별도 행정 승인 후 수행 |
| 11 | FM8 residual-discovery 진입 감사 | **NO-GO; FM8 본 연구 미개시**; 논문 1 종결·잠금 유지 | [`entry-audit protocol`](../docs/protocols/fm8-residual-discovery-entry-audit-protocol-ko.md), [`audit directory`](../milestones/fm8_residual_discovery_entry_audit/), [`final report`](../milestones/fm8_residual_discovery_entry_audit/outputs/fm8-residual-discovery-entry-audit-report.md) | G1–G7 전부 PASS, source-fold residual stability 확인, QFM-owned/hash-locked shared provenance, shortcut metadata와 blinded-review 승인·clearance 확보 후에만 별도 두 번째 논문 workstream 개시 |

각 FM 마일스톤 종료 시 `docs/research_plan/01-01-foundation-model-validation-milestones-ko.md`에 결과·배운 점·산출물·다음
진입 조건을 기록한다. 실제 실행 폴더에 숫자 접두사를 붙이지 않는 이유는 P0/FM
manifest와 시험의 canonical 경로를 보존하기 위해서다.
