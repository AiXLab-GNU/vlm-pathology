# Medical Metric Atlas

`web/`은 `vlm_pathology_metrics`의 T1–T4 의료 정량지표 계층과 별도 분석
레지스트리를 탐색하는 정적 웹페이지입니다. 외부 프레임워크나 CDN에 의존하지
않으며, Python 패키지와 같은 TSV를 단일 원천으로 사용합니다.

전체 계보 그래프는 58개 의료·파생 지표를 Tier별 열에 배치하고 TSV의
`parent_metric_ids`를 선으로 연결합니다. 임상 기준축 필터, hover 연결 강조,
키보드 탐색 및 상세 패널 연동을 지원합니다.

## 데이터 갱신

패키지 루트에서 다음 명령을 실행합니다.

```bash
../../.venv/bin/python scripts/build_web_catalog.py
```

이 명령은 계층·parent 방향·레거시 분할을 검증한 뒤
`web/data/catalog-data.js`를 결정론적으로 다시 생성합니다.

## 로컬 실행

저장소 루트에서:

```bash
.venv/bin/python -m http.server 8000 --directory infrastructure/packages/vlm_pathology_metrics/web
```

브라우저에서 `http://localhost:8000`을 엽니다. 데이터 파일이 JavaScript로
생성되므로 `web/index.html`을 직접 열어도 기본 탐색 기능은 동작합니다.

이 화면은 연구용 분류체계이며 임상 검증 또는 진단 도구가 아닙니다.
