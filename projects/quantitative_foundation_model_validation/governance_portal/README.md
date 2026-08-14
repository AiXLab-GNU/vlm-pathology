# VLM Pathology Research & Governance Portal

이 포털은 저장소의 세 독립 연구를 한 화면에서 탐색하고, 프로젝트별 목표·계획·현재
gate와 마일스톤을 확인하며, 관리자 및 임상의 검토를 기록하는 loopback-only 연구
포털이다. 기존 QFM P0/FM4 evidence review, 전자 판정과 clean rerun 콘솔도 별도
페이지로 유지한다.

## 주요 화면

- `/`: 전체 포트폴리오 목표, 운영 원칙, 프로젝트 진행 현황
- `/pni.html`: PRECISE PNI Candidate Triage 목표·계획·마일스톤
- `/quantitative.html`: Quantitative Foundation-Model Validation 목표·계획·마일스톤
- `/biomarker.html`: Prostate Biomarker Validation 목표·계획·마일스톤
- `/artifacts.html`: Medical Metric Atlas와 명시적으로 등록된 project-owned figure
- `/admin-review.html`: 범위·근거 추적성·governance·데이터 무결성 설문
- `/clinician-review.html`: 주장 경계·시각 품질·workflow 적합성 설문
- `/qfm-governance.html`: 기존 P0/FM4 상세 승인 및 clean rerun 콘솔

마일스톤 상태는 각 프로젝트의 `00-project-sequence/README.md`에서 시작 시점마다
읽는다. 포털에 노출하는 산출물은 `portfolio.py`의 명시적 registry에 한정되며,
다른 프로젝트의 output을 분석 입력으로 사용하지 않는다.

## 서버 시작과 접속

저장소 루트에서 다음 명령을 실행한다.

```bash
.venv/bin/python projects/quantitative_foundation_model_validation/governance_portal/portal_server.py --host 127.0.0.1 --port 8011
```

원격 서버에서는 방화벽 포트를 열거나 `0.0.0.0`으로 바인딩하지 않고 SSH tunnel을
사용한다.

```bash
ssh -N -L 8011:127.0.0.1:8011 <사용자>@<원격서버>
```

그 뒤 로컬 브라우저에서 `http://127.0.0.1:8011`을 연다. 장시간 실행은 기존
`run_portal_forever.sh` 또는 `tmux` 운영 방식을 사용한다.

## 검토 기록

일반 관리자·임상의 설문은 선택한 프로젝트를 소유자로 하여 다음 local artifact
경로에 append-only, hash-chained JSONL로 기록한다.

```text
resources/artifacts/<project_id>/portal_reviews/admin_survey.jsonl
resources/artifacts/<project_id>/portal_reviews/clinician_survey.jsonl
```

이 경로는 Git 비추적 local artifact 영역이다. 설문에는 환자 식별정보를 입력하지
않는다. 전자서명은 SSH 접근 통제 환경에서의 내부 attestation이며 인증서 기반 규제
전자서명이 아니다.

QFM 상세 승인 source ledger와 파생 manifest는 기존과 동일하게
`preexperiment/governance_records/`에 기록된다. QFM 검토·승인 절차와 clean rerun
gate는 `qfm-governance.html`에서 수행한다.

## 해석 제한

포털의 상태 표시나 검토 승인은 부족한 과학적 근거를 대체하지 않는다. 특히 PNI
후보 triage를 whole-slide 진단으로, 정량 개념 recoverability를 질병 예측으로,
biomarker qualification을 임상 성능 확정으로 해석하지 않는다.
