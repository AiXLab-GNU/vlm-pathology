# PRECISE PNI project sequence

이 디렉터리는 프로젝트를 열었을 때 가장 먼저 읽는 진행 순서표다. 아래 번호는
연구의 논리적 순서이며 링크 대상은 변경하지 않는 canonical 실행 경로다.

| 순서 | 단계 | 현재 상태 | 주 폴더·문서 | 완료/진입 기준 |
|---:|---|---|---|---|
| 00 | 목적·claim boundary 확인 | 상시 | [`../README.md`](../README.md), [`../CLAIM_BOUNDARIES.md`](../CLAIM_BOUNDARIES.md) | candidate triage 범위 확인 |
| 01 | 연구 설계·실행계획 | 완료/유지 | [`01` 연구계획](../docs/project_plan/01-precise-pni-project-plan-ko.md), [`01-02` 마일스톤](../docs/project_plan/01-02-pni-project-milestones-ko.md), [`01-02-01` tracker](../docs/project_plan/01-02-01-pni-project-execution-tracker-ko.md), [`survey index`](../docs/surveys/README.md) | 승인 설계와 계획 일치 |
| 02 | 후보 생성·검토 화면 | 완료 | [`../code/candidate_visualization/`](../code/candidate_visualization/) | frozen candidate universe 재현 |
| 03 | Frozen-score audit | 완료 | [`../code/frozen_score_audit/`](../code/frozen_score_audit/), [`../reports/`](../reports/) | NMS·score·120개 review reconciliation |
| 04 | 14-focus blinded morphology rereview | 완료 | [`../code/morphology_rereview/`](../code/morphology_rereview/), [`../docs/pathologist_protocol/`](../docs/pathologist_protocol/) | 14건 label lock·conflict 해소 완료 |
| 05 | 병리의 contour review | **현재 단계** | [`../code/contour_review/`](../code/contour_review/), [`contour protocol v1.0`](../docs/pathologist_protocol/PRECISE_PNI_CONTOUR_PROTOCOL_KO.md) | 자동 synthetic round-trip 통과; 실제 브라우저/QuPath one-case dry run 후 적격 focus의 병리 contour 승인 |
| 06 | 공간 정량화·보고 | 잠금 | [`../reports/`](../reports/), [`../paper/`](../paper/) | 전문의 승인 contour와 별도 승인 분석계획 필요 |

`code/`, `docs/`, `tests/` 같은 실제 폴더명에 숫자를 붙이지 않는 이유는 기존 시험,
명령, frozen manifest의 경로를 보존하기 위해서다. 새 단계를 추가할 때는 이 표에서
번호·상태·진입 기준을 먼저 정한 뒤 canonical 폴더에 산출물을 둔다.
