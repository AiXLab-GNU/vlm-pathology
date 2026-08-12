# Quantitative foundation-model validation sequence

이 디렉터리는 프로젝트의 단계별 진입점이다. 번호는 연구 진행 순서이고, 링크 대상은
재현성을 위해 유지하는 canonical 폴더다.

| 순서 | 단계 | 현재 상태 | 주 폴더·문서 | 완료/진입 기준 |
|---:|---|---|---|---|
| 00 | 목적·H1/H2·claim boundary 확인 | 상시 | [`../README.md`](../README.md), [`../CLAIM_BOUNDARIES.md`](../CLAIM_BOUNDARIES.md) | 의료지표와 모델 평가량 분리 |
| 01 | 지표 체계·연구계획 | 완료/갱신 중 | [`../docs/metric_taxonomy/`](../docs/metric_taxonomy/), [`../docs/research_plan/`](../docs/research_plan/) | T1–T4와 outcome 정의 |
| 02 | P0 사전실험·G8/G9 handoff | 완료 | [`../preexperiment/`](../preexperiment/) | clean rerun과 scope-capped handoff |
| 03 | FM1 지표 적격성 | 완료 | [`../milestones/fm1_metric_eligibility/`](../milestones/fm1_metric_eligibility/) | H1/H2 eligibility와 독립성 감사 |
| 04 | FM2 paired manifest | 완료 | [`../milestones/fm2_paired_manifest/`](../milestones/fm2_paired_manifest/) | membership·truth·FOV·fold 일치 |
| 05 | FM3 paired embeddings | 완료 | [`../milestones/fm3_paired_embeddings/`](../milestones/fm3_paired_embeddings/) | 두 encoder row/hash reconciliation |
| 06 | FM4 concept benchmark | 승인 대기 | [`../milestones/fm4_concept_benchmark/`](../milestones/fm4_concept_benchmark/), [`../governance_portal/`](../governance_portal/) | descriptive-only scope 승인 |
| 07 | 추가 의료지표 확장 | 잠금 | [`../metric_registry/`](../metric_registry/), [`../code/`](../code/) | 반복성 있는 독립 truth 확보 |
| 08 | H2 기능적 질병예측 검증 | 잠금 | [`../MILESTONES.md`](../MILESTONES.md) | 독립 metric–endpoint·충분한 사건·외부검증 |
| 09 | 보고·논문 | 단계별 | [`../reports/`](../reports/), [`../paper/`](../paper/) | claim gate를 통과한 근거만 사용 |

각 FM 마일스톤 종료 시 `docs/research_plan/`의 지정 계획서에 결과·배운 점·산출물·다음
진입 조건을 기록한다. 실제 실행 폴더에 숫자 접두사를 붙이지 않는 이유는 P0/FM
manifest와 시험의 canonical 경로를 보존하기 위해서다.
