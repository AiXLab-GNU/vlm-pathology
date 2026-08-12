# VLM Pathology Research Portfolio

이 저장소는 서로 다른 과학적 질문을 가진 세 연구 프로젝트와 공통 병리-VLM
인프라를 관리한다. 동일 영상이나 embedding을 재사용하더라도 endpoint, 승인 기록,
결과 및 claim boundary는 프로젝트별로 분리한다.

## Projects

- `projects/precise_pni_candidate_triage/`: PRECISE PNI 후보 영역 triage와 병리 재검토
- `projects/quantitative_foundation_model_validation/`: 의료 정량지표의 표현 복원성과
  질병예측에서의 기능적 활용 검증
- `projects/prostate_biomarker_validation/`: 전립선 분자표지자·재발·생존·외부검증 연구와
  해당 논문

## Root structure

- `projects/`: 프로젝트별 과학 문서·코드·시험·논문
- `resources/`: 프로젝트별 또는 shared 데이터·모델·환경·생성물
- `infrastructure/`: 공통 package·registry·운영 스크립트·구조 정책·migration 기록
- `.worktrees/`: 등록된 프로젝트별 보조 Git worktree

`.git`, `.venv`와 에이전트용 dot 디렉터리는 도구가 루트 위치를 요구하므로 유지한다.
그 밖의 모든 루트 디렉터리는 금지되며 구조 검증기가 이를 검사한다. 전체 목록과
존치 이유는 `infrastructure/docs/repository/ROOT_DIRECTORY_REGISTRY.csv`에 있다.

실제 WSI, 비공개 자료, 모델 weight, cache 및 생성 배열은 Git에 포함하지 않는다.
프로젝트는 다른 프로젝트의 output을 직접 입력으로 사용하지 않고, 필요한 공통 자산은
`infrastructure/shared/` manifest를 통해 참조한다.

각 연구의 과학적 제한과 실행법은 해당 프로젝트의 `README.md`와 `AGENTS.md`를 따른다.
새 파일을 만들거나 worktree·Superpowers 문서를 생성하기 전에는
`infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md`의 소유권·경로·명명 규칙을 적용한다.
