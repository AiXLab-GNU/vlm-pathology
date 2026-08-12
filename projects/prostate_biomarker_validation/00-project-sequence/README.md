# Prostate biomarker-validation sequence

이 디렉터리는 프로젝트의 진행 순서를 보여 주는 첫 진입점이다. 번호는 분석의 논리적
순서이며 실제 코드·논문 경로는 frozen provenance 때문에 그대로 유지한다.

| 순서 | 단계 | 현재 상태 | 주 폴더·문서 | 완료/진입 기준 |
|---:|---|---|---|---|
| 00 | 목적·claim boundary 확인 | 상시 | [`../README.md`](../README.md), [`../CLAIM_BOUNDARIES.md`](../CLAIM_BOUNDARIES.md) | qualification과 임상검증 구분 |
| 01 | 연구 설계·protocol freeze | 완료 | [`../docs/designs/`](../docs/designs/), [`../docs/plans/`](../docs/plans/), [`../docs/study_design/`](../docs/study_design/) | endpoint·analysis family 동결 |
| 02 | 대상별 분석 실행 | 완료/동결 | [`../code/legacy/`](../code/legacy/), [`../outputs/legacy/`](../outputs/legacy/) | 저장된 source·fold·hash reconciliation |
| 03 | confounder·site·stability 감사 | 완료 | [`../outputs/`](../outputs/), [`../tests/`](../tests/) | saved evidence와 claim scope 일치 |
| 04 | claim–evidence 통합 | 완료/유지 | [`../paper/claim_evidence_matrix.csv`](../paper/claim_evidence_matrix.csv), [`../paper/endpoint_hierarchy.csv`](../paper/endpoint_hierarchy.csv) | 모든 주장에 source row 연결 |
| 05 | 원고·그림·표 생성 | 진행/author action 남음 | [`../paper/`](../paper/) | figure/table lineage와 numeric QA |
| 06 | 제출 패키지 검증 | 부분 완료 | [`../paper/compliance_report.md`](../paper/compliance_report.md), [`../reports/`](../reports/) | 저자 funding·contribution·ethics 확인 |

`code/legacy/`와 `outputs/legacy/`는 두 번째 단계의 기본 신규 작업 위치가 아니라 과거
근거 보존면이다. 새로운 분석은 `code/active/` 또는 승인된 project code 위치로
추출하고 시험을 추가해야 한다.
