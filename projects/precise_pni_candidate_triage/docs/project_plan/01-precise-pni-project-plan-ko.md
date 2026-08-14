# PRECISE PNI 연구 목적·목표·마일스톤 및 현재 진행 현황

- 문서 ID: `pni-project-plan`
- 소유 프로젝트: `precise_pni_candidate_triage`
- 문서 유형: canonical research plan
- 상태: active
- Canonical path: `projects/precise_pni_candidate_triage/docs/project_plan/01-precise-pni-project-plan-ko.md`
- 문서 기준일: 2026-08-13
- 문서 성격: 연구 전체 로드맵 및 실행 현황을 관리하는 living document
- 현재 단계: M5 완료, M6 contour protocol·standalone HTML package 구축 및 synthetic one-case round-trip 완료, 실제 브라우저/QuPath one-case dry run과 전문의 contour 대기
- 연구 책임 범위: 병리의사 참여형 PNI 후보선별·형태표현형·정량화 연구
- 현재 AI의 검증된 역할: 확정 진단이 아니라 공간적으로 중복되지 않는 검토 후보의 우선순위 제시
- Canonical milestones: [01-02-pni-project-milestones-ko.md](01-02-pni-project-milestones-ko.md)
- Current execution tracker: [01-02-01-pni-project-execution-tracker-ko.md](01-02-01-pni-project-execution-tracker-ko.md)
- 관련연구 입력: [survey index](../surveys/README.md); 현재 `CURRENT` survey 없음

## 1. 한 문장으로 표현한 연구의 최종 목표

전립선암 WSI에서 AI가 공간적으로 중복되지 않는 PNI 의심 후보를 우선 제시하고, 병리전문의가 이를 확인·분류·윤곽화한 뒤, 슬라이드에서 실제로 관찰된 PNI의 부담, 암–신경 상호작용 형태, 신경 크기 및 공간적 미세환경을 재현성 있게 정량화하여 향후 임상·분자 특성과의 관계를 검증할 수 있는 병리의사 참여형 연구 체계를 구축한다.

이 최종 목표는 AI가 PNI를 단독으로 확진하거나, 현재 결과만으로 슬라이드 전체의 PNI 음성을 선언하거나, 임상적으로 충분한 판독 후보 수를 결정하는 것이 아니다.

## 2. 연구가 해결하려는 문제

### 2.1 실무적 문제

PNI는 WSI 전체에서 크기가 작고 산재할 수 있으므로, 모든 슬라이드와 모든 신경 주변을 병리전문의가 연구 목적으로 전수 탐색하면 판독 부담이 매우 커진다. 따라서 대규모 코호트 연구를 시작하기 전에 다음 질문에 답해야 한다.

> AI가 슬라이드마다 우선순위가 높은 소수의 공간적으로 중복되지 않는 후보를 제시했을 때, 이미 전문의가 확인한 PNI 병변이 그 작은 검토 예산 안에 집중되는가?

이 질문이 긍정적인 기술 신호를 보인 뒤에야 TCGA, SPROB20 또는 다른 생검 코호트에서 전문의 판독량을 줄이는 후보선별 절차를 설계할 수 있다.

### 2.2 병리학적 문제

단순한 `PNI 있음/없음`만으로는 다음의 차이를 표현할 수 없다.

- 암이 신경에 접촉하는지, 둘러싸는지, 신경 내부를 침범하는지
- 신경 장축을 따라 암이 이어지는지
- 신경 분지점이 침범되는지
- 단일 신경인지, 한 시야에 여러 신경이 존재하는지
- 침범된 신경의 크기와 단면 형태가 어떠한지
- 암이 신경 둘레를 얼마나 포위하며 접촉 길이가 얼마나 되는지
- 한 슬라이드에서 관찰되는 PNI 병변의 수와 밀도가 어느 정도인지

따라서 후보선별 감사 다음에는 형태 재판독과 전문의 승인 contour가 필요하다.

### 2.3 임상 연구 문제

형태 및 정량화 방법이 안정화되면 장기적으로 다음을 검정할 수 있다.

- 관찰된 slide-level PNI burden이 단순 PNI 유무보다 BCR을 더 잘 설명하는가?
- 신경 직경, 포위율, 접촉 길이, intraneural invasion 또는 longitudinal tracking이 병기·Gleason·분자 특성과 관련되는가?
- PTEN, ERG, SPOP, AR 등과 PNI 표현형이 관련되는가?
- 생검에서 관찰된 PNI 부담과 형태가 수술 후 결과와 관련되는가?
- 후보선별 및 형태 측정 절차가 다른 기관, 스캐너 및 코호트에서도 재현되는가?

이 질문들은 현재 PRECISE 14건만으로 답하는 질문이 아니다. 별도의 표본수 설계, 전문의 판독 및 독립 검증이 필요하다.

## 3. 목적과 구체적 목표

### 3.1 단기 목적: PRECISE 기술 검증

1. frozen CONCH 점수와 기존 spatial NMS를 변경하지 않고 후보선별기의 순위 집중 능력을 감사한다.
2. 미판독 후보를 음성으로 취급하지 않으면서 슬라이드당 검토 예산과 확인된 PNI focus 회수의 관계를 기술한다.
3. 이전에 신경이 확인된 14개 후보에서 구조화된 PNI 형태 재판독이 가능한지 평가한다.
4. 불확실성과 평가 불가를 `no`로 바꾸지 않고 그대로 보존한다.
5. 실제 신경·암–신경 경계를 그릴 후보와 추가 판정이 필요한 후보를 구분한다.

### 3.2 중기 목적: PNI 형태 및 공간 정량화 방법 구축

1. 병리전문의가 승인한 신경 contour와 암–신경 접촉 또는 침범 contour를 구축한다.
2. 신경의 단축·장축 직경, 단면적, 장단축비 및 원형도를 측정한다.
3. 암–신경 접촉 길이와 신경 포위율을 측정한다.
4. PNI 주변과 동일 슬라이드 원거리 암을 거리 구간별로 비교한다.
5. H&E 형태, HMWCK/AMACR 관련 색상 표현형 및 frozen embedding의 공간 gradient를 탐색한다.
6. 측정값의 좌표계, MPP, 등록 정확도 및 contour 재현성을 문서화한다.

### 3.3 장기 목적: 대규모 임상·분자 연구

1. 더 큰 코호트에서 pathologist-confirmed slide-level PNI burden을 구축한다.
2. 후보선별이 전문의 판독량을 실제로 줄이는지 측정한다.
3. PNI burden과 BCR, 병리 병기, Gleason 및 분자 아형의 연관성을 검정한다.
4. 개발 코호트와 독립 검증 코호트를 분리한다.
5. 최종적으로 재현 가능한 human-in-the-loop PNI phenotyping workflow를 보고한다.

## 4. 최종 성공 기준

이 프로젝트의 성공은 다음 조건을 순서대로 충족하는 것으로 정의한다.

1. 후보선별기 감사가 frozen 상태로 재현되고 입력·출력 무결성이 확인된다.
2. 전문의가 구조화된 형태 항목을 사용할 수 있고, 결측·불확실성·평가 불가가 정직하게 보존된다.
3. 실제 신경 및 암–신경 경계가 전문의에 의해 승인되어 정량 측정의 기준이 마련된다.
4. 정량 지표가 동일 좌표계와 고정 분석 규칙으로 재생성된다.
5. 확장 코호트에서 후보 검토 coverage와 판독 부담을 함께 보고한다.
6. 임상·분자 연관 분석이 적절한 환자 단위 통계와 독립 검증으로 수행된다.
7. 모든 결론이 분석 단위와 데이터가 허용하는 범위를 넘지 않는다.

성공 기준에는 현재 PRECISE 자료에서 임상용 민감도 100%를 입증하거나, 슬라이드당 특정 후보 수를 임상 기준으로 확정하는 일이 포함되지 않는다.

## 5. 연구 질문의 단계적 구조

| 단계 | 연구 질문 | 현재 답변 가능 범위 |
|---|---|---|
| Q1 후보선별 | 확인된 PNI가 높은 순위 후보에 집중되는가? | PRECISE 120개 층화 판독 표본 내에서 기술 가능 |
| Q2 형태 기록 | 14개 신경 후보에서 구조화된 형태 라벨을 기록할 수 있는가? | 현재 재판독 결과로 평가 가능 |
| Q3 윤곽·계측 | 승인된 신경 경계에서 직경·포위율·접촉 길이를 측정할 수 있는가? | 전문의 contour 후 가능 |
| Q4 공간 미세환경 | PNI 근접 암과 원거리 암의 H&E/IHC 표현형이 다른가? | PRECISE에서 탐색 가능, contour와 등록 QC 필요 |
| Q5 PNI 부담 | 슬라이드에서 관찰된 PNI 수·밀도·최대 중증도가 임상 변수와 관련되는가? | 더 큰 판독 코호트 필요 |
| Q6 예후·분자 | PNI 부담·형태가 BCR 및 PTEN/ERG 등과 관련되는가? | TCGA/생검 코호트의 신규 판독 필요 |
| Q7 일반화 | 다른 기관·스캐너·검체에서 동일 workflow가 작동하는가? | 독립 외부검증 필요 |

## 6. 과학적 경계와 금지 해석

### 6.1 현재 가능한 표현

> 층화·블라인드된 PRECISE 120개 후보 판독 표본에서 전문의 확인 PNI 7개는 모두 high-ranked stratum에 있었으며, frozen 후보선별기는 관찰된 PNI를 비교적 작은 슬라이드별 판독 예산 안에 집중시켰다.

> 선택된 이전 신경 양성 후보 14개에서 구조화된 H&E 형태 재판독을 수행하고, 후속 contour 작업을 위한 형태 정보와 평가 가능성을 기록했다.

### 6.2 현재 금지되는 표현

- 모델의 전체 WSI PNI 민감도는 100%이다.
- 슬라이드당 3개 또는 4개만 보면 임상적으로 충분하다.
- 미판독 영역에는 PNI가 없다.
- PRECISE 환자군의 PNI 유병률 또는 형태 분포를 추정했다.
- 현재 모델이 PNI를 확정 진단하거나 형태 아형을 정확히 분류한다.
- 14건의 형태 결과가 PRECISE 또는 전립선암 환자 전체에 일반화된다.
- 현재 결과가 BCR, 예후, 병기 또는 분자 아형과의 연관성을 입증한다.
- 예비 AMACR 분석이 미토콘드리아 양, OXPHOS 활성 또는 신경에서 암으로의 미토콘드리아 전달을 입증한다.

## 7. 데이터 및 분석 단위

### 7.1 PRECISE 후보선별 감사

- 전체 mask-filtered 후보: 2,264개
- 악성 슬라이드: 19개
- 대상 환자: 18명
- spatial NMS 이후 후보: 624개
- 층화·블라인드 전문의 판독 후보: 120개
- 판독 층: high 60, mid 30, low/random 30
- 전문의 확인 신경 후보: 14개
- 최초 판독에서 확인된 PNI: 7개
- 최초 PNI 형태: touching 4개, surrounding 3개

### 7.2 형태 재판독 파일럿

- 고정 대상: 최초 판독의 신경 양성 후보 14개 전부
- 슬라이드: 10개
- 환자: 10명
- 표시 영상: H&E 300 µm, 600 µm, 1,200 µm
- 블라인드 대상: 이전 라벨, 점수, rank, stratum, candidate ID, 좌표 및 임시 신경 원
- 현재 재판독 결과: definite 7, probable 1, absent 6

### 7.3 분석 단위의 구분

- candidate/focus 단위: 형태 라벨, 신경 크기, 포위율, 접촉 길이
- slide 단위: 후보 예산, 관찰된 PNI 수 및 면적당 밀도
- subject 단위: bootstrap, 임상·분자·예후 분석
- cohort 단위: 일반화와 외부검증

후보, focus, slide, subject를 동일한 독립 표본처럼 취급하지 않는다.

## 8. 전체 마일스톤 요약

| 마일스톤 | 내용 | 상태 | 다음 게이트 |
|---|---|---|---|
| M0 | 연구 범위·재현성·저장소 기반 정립 | 완료 | 승인 설계 준수 |
| M1 | frozen 후보 생성 및 120건 층화 판독 세트 구축 | 완료 | 전문의 판독 수령 |
| M2 | 120건 전문의 판독 및 frozen-score 기술 감사 | 완료 | 14건 형태 재판독 설계 |
| M3 | 14건 블라인드 형태 재판독 도구 구축 | 완료 | 전문의 재판독 수령 |
| M4 | 14건 재판독 수령·보완·무결성 검증 | 완료 | 공식 잠금 실행 |
| **M5** | **공식 잠금, 이전 라벨 연결, 형태 결과 및 contour 대상 확정** | **완료** | 잠금 산출물·clean rerun·원본 불변성 검증 완료 |
| **M6** | **전문의 신경·암–신경 interface contour** | **현재 단계 — package·자동 synthetic dry run 완료** | 실제 브라우저/QuPath one-case export dry run 후 전문의 contour·QC |
| M7 | PRECISE 형태계측·공간 분석 확정 파이프라인 | 대기 | 측정 재현성 및 등록 QC |
| M8 | 확장 코호트 후보선별 및 전문의 판독 운영 검증 | 계획 | coverage·workload 기준 충족 |
| M9 | PNI burden의 임상·분자·예후 분석 | 장기 계획 | 충분한 사건 수와 독립 검증 |
| M10 | 외부검증·논문화·재현성 공개 | 장기 계획 | claim-evidence 일치 |

## 9. 마일스톤별 상세 태스크

### M0. 연구 범위·재현성·저장소 기반 정립 — 완료

목적은 연구 질문과 허용되는 결론을 먼저 고정하고, 분석 과정에서 결과를 보고 설계를 바꾸는 일을 방지하는 것이다.

완료 태스크:

- [x] frozen-score 감사 설계 승인 및 문서화
- [x] 형태 재판독 설계 승인 및 문서화
- [x] 후보선별기를 임상 진단기가 아닌 candidate-triage 도구로 규정
- [x] 원본 임상의 판독 CSV를 불변 입력으로 지정
- [x] 원본 SHA256 기준값 고정
- [x] 결측값을 음성으로 자동 변환하지 않는 원칙 고정
- [x] 점수, 프롬프트, exemplar 및 가중치 재학습·재보정 금지
- [x] spatial NMS 재구성 실패 시 분석 중단 규칙 고정
- [x] 저장소 초기화, `.gitignore`, Codex/Claude 작업 지침 및 원격 저장소 등록
- [x] 코드·테스트·설계 문서와 대용량/임상/생성 데이터의 Git 정책 분리

주요 근거 문서:

- `projects/precise_pni_candidate_triage/docs/designs/2026-08-05-precise-pni-frozen-score-audit-design.md`
- `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`
- `AGENTS.md`

### M1. Frozen 후보 생성 및 120건 층화 판독 세트 구축 — 완료

목적은 모델 점수를 변경하지 않은 채 전문의가 검토할 후보 표본을 구성하는 것이다.

완료 태스크:

- [x] PRECISE 악성 19개 슬라이드에서 300 µm sliding-window 후보 생성
- [x] 조직 및 종양 마스크 조건 적용
- [x] prototype, text-PNI 및 nerve score 산출
- [x] 고정 가중치 `0.50/0.35/0.15`로 combined score 산출
- [x] 전체 mask-filtered 후보 2,264개 저장
- [x] 기존 spatial NMS 적용
- [x] 후보 간 공간 중복을 줄인 판독 후보군 구성
- [x] high 60, mid 30, low/random 30의 총 120개 층화 표본 구성
- [x] 19개 슬라이드에 걸친 후보 배분
- [x] 모델 점수와 선정 층을 숨긴 전문의 판독 HTML 생성
- [x] selection manifest와 build summary 저장

완료 기준:

- 후보 ID, slide ID, 좌표, window size, score 및 stratum이 manifest로 추적 가능하다.
- 판독 화면에서 점수와 층 정보가 노출되지 않는다.

### M2. 120건 전문의 판독 및 frozen-score 감사 — 완료

목적은 후보선별기의 실제 triage 가능성을 정직하게 감사하는 것이다.

완료 태스크:

- [x] 전문의 Song의 120개 후보 블라인드 판독 수령
- [x] 불변 원본과 파생 normalized review 분리
- [x] reviewer ID는 파생 표에서만 `Song`으로 보완
- [x] 후보 ID, slide ID, 좌표 및 window size 전수 대조
- [x] 기존 spatial NMS를 정확히 재구성
- [x] 2,264개 전체 후보에서 624개 NMS 잔존 후보 확인
- [x] 슬라이드당 `k=1..10` PNI focus capture curve 생성
- [x] nerve-positive focus capture curve 생성
- [x] touching 및 surrounding 결과 분리
- [x] high/mid/low-random 층별 PNI 및 신경 수 집계
- [x] 각 top-k budget의 실제 판독 label coverage 계산
- [x] coverage 100%가 아닌 budget의 precision 계산 금지 적용
- [x] 네 frozen score의 ROC-AUC 및 average precision 산출
- [x] 환자 cluster bootstrap 10,000회 실행
- [x] 단일 outcome class bootstrap 실패를 삭제하지 않고 수·비율 보고
- [x] error-review table 생성
- [x] 모든 표·보고서·그림을 단일 실행 스크립트로 재생성
- [x] clean rerun 및 입력 불변성 확인

주요 실제 결과:

- 전문의 확인 PNI: 7개
- 전문의 확인 신경: 14개
- high stratum: PNI 7개, 신경 14개
- mid 및 low/random stratum: 확인된 PNI와 신경 0개
- post-NMS PNI focus capture: `k=3`에서 7/7
- post-NMS nerve focus capture: `k=4`에서 14/14
- `k=1`만 evaluable-label coverage가 100%; `k>=2` precision은 계산하지 않음
- frozen combined score: reviewed 120개 내 ROC-AUC 0.814, AP 0.272
- text-PNI score: reviewed 120개 내 ROC-AUC 0.842, AP 0.304

해석 제한:

- `k=3`과 원래 rank의 top-4 관찰은 후향적·기술적 결과이다.
- 이는 whole-slide sensitivity 또는 임상 threshold가 아니다.
- ROC-AUC/AP는 층화 선택된 120개 표본 안에서만 해석한다.

### M3. 14건 형태 재판독 도구 구축 — 완료

목적은 최초 판독에서 신경이 확인된 14개 후보를 더 넓은 H&E 문맥에서 구조화해 다시 판독하는 것이다.

완료 태스크:

- [x] 이전 신경 양성 14개 전부를 고정 표본으로 선정
- [x] 원본 판독과 audit table의 candidate·geometry 일치 확인
- [x] 고정 seed `20260806`으로 임시 ID `MORPH-001..014` 부여
- [x] candidate ID와 임시 ID의 private mapping 분리
- [x] 300/600/1,200 µm H&E 문맥 영상 생성
- [x] 이전 라벨, 점수, rank, stratum, slide/subject ID 및 좌표 비노출
- [x] provisional nerve circle 비노출
- [x] HMWCK/AMACR 비노출
- [x] 11개 구조화 형태 항목과 자유 메모 필드 구현
- [x] 모든 범주형 형태 항목에 `uncertain` 또는 `not_evaluable` 허용
- [x] 브라우저 자동 저장, JSON 백업, CSV 내보내기 구현
- [x] 빌드 무결성 보고서와 run configuration 생성
- [x] 전용 단위 테스트 작성
- [x] 임상의 전달용 목표·로드맵·판독 지침 문서 작성

### M4. 형태 재판독 수령·보완·무결성 검증 — 완료

목적은 판독 원자료를 수정하지 않고 잠금 가능한 파생본을 만드는 것이다.

완료 태스크:

- [x] 최초 CSV 및 JSON 수령
- [x] CSV 14건과 JSON 14건의 모든 응답 일치 확인
- [x] 고정 임시 ID 집합 및 중복 여부 확인
- [x] 최초 수령본의 `MORPH-010 longitudinal_tracking` 공란 발견
- [x] 공란을 자동으로 `no`로 바꾸지 않고 전문의 보완 요청
- [x] 보완 CSV 수령
- [x] `MORPH-010 longitudinal_tracking=not_evaluable` 확인
- [x] 나머지 형태 필드 누락 0건 확인
- [x] 허용되지 않은 라벨 0건 확인
- [x] 논리 충돌 0건 확인
- [x] 판독자 확인 후 파생본에만 `reviewer_id=Song` 입력
- [x] 보완 원본 CSV가 변경되지 않았음을 SHA256으로 확인
- [x] 파생 정규화 파일에서 14건 모두 `Song`이며 다른 필드는 원본과 동일함을 확인

현재 형태 재판독의 잠금 전 집계:

| 항목 | 결과 |
|---|---:|
| 전체 후보 | 14 |
| nerve present=yes | 14 |
| PNI definite | 7 |
| PNI probable | 1 |
| PNI absent | 6 |
| overall touching | 5 |
| overall surrounding/encasement | 3 |
| overall none | 2 |
| overall not_evaluable | 4 |
| intraneural component=yes | 0 |
| longitudinal tracking=yes | 0 |
| branch-point involvement=yes | 0 |
| single nerve | 12 |
| multiple nerves | 2 |
| field adequate | 14 |
| overall confidence=high | 14 |

완료도 해석:

- 양식상 필수 항목 완료: 14/14
- PNI status 자체의 평가 가능: 14/14
- `uncertain`과 `not_evaluable`까지 평가 불가로 보는 보수적인 전체 core-field 완전 평가: 예비 계산 7/14
- 이 세 정의는 서로 다르므로 공식 결과 보고서에서 분리해야 한다.

현재 기준 파일:

- 전문의 보완 원본: `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/precise_pni_morphology_completed (1) (2).csv`
- 보완 원본 SHA256: `74f127a8dd7c0f4174b5b85406e34f6ac4e92125ca95861304d19d9b4e867e85`
- reviewer ID 파생 정규화본: `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/precise_pni_morphology_completed_normalized.csv`
- 파생본 SHA256: `2543201117de834726d6876009e648745c12299f9daf4ec0658417f0dbe06673`
- 불변 최초 120건 원본 SHA256: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`

주의:

- 기존 JSON 백업은 `MORPH-010` 보완 전 상태이므로 보완 CSV와 동일한 최종 백업으로 간주하지 않는다.
- 공식 잠금 입력은 SHA256이 기록된 보완 CSV와 그 판독 내용을 그대로 보존한 reviewer-ID 파생본이다.

### M5. 공식 잠금·전이 분석·contour 대상 확정 — 완료

목적은 블라인드 판독을 변경 불가능한 분석 입력으로 고정한 다음에만 private mapping과 이전 라벨을 연결하는 것이다.

세부 태스크:

- [x] 보완 원본과 reviewer-ID 파생본의 SHA256을 잠금 기록에 저장
- [x] 불변 120건 원본의 실행 전 SHA256 재확인
- [x] 공식 `finalize` 기능을 reviewer-ID 파생본에 실행
- [x] finalization 산출물을 별도 locked 디렉터리에 기록하여 build provenance 보존
- [x] temporary ID와 candidate ID를 one-to-one으로 연결
- [x] `normalized_morphology_review.csv` 생성
- [x] `morphology_data_integrity_report.csv` 생성
- [x] `morphology_transition_table.csv` 생성
- [x] `contour_eligibility_table.csv` 생성
- [x] `MORPHOLOGY_RESULTS_REPORT.md` 생성
- [x] finalize run configuration에 입력·출력 hash와 환경정보 기록
- [x] 누락 0건, 논리 충돌 0건 재확인
- [x] 이전 PNI/relation과 재판독 PNI/relation의 raw transition table 검토
- [x] definite, probable, absent, uncertain, not-evaluable 수를 분리 보고
- [x] touching, surrounding, intraneural 및 mixed 구성요소를 분리 보고
- [x] orientation, longitudinal tracking, branch point 및 multiplicity 요약
- [x] 양식 완료, PNI-status 평가 가능 및 strict all-core evaluability를 별도 지표로 보고
- [x] contour 대상, wider-context 대상 및 adjudication 대상을 확정
- [x] 공식 결과 문구에서 14개 선택 focus 이외의 일반화가 없는지 점검
- [x] 관련 단위 테스트와 clean rerun 재현성 검증
- [x] 실행 전후 원본 SHA256 불변 확인

진입 기준:

- 14개 fixed ID 일치
- reviewer ID 확정
- 모든 필수 형태 필드 응답 완료
- 논리 충돌 0건

진입 기준은 모두 충족되었고 M5 finalization을 완료하였다.

실제 잠금 결과:

- 공식 잠금 시각: `2026-08-11T12:19:17.485517+00:00`
- 잠금 대상: 14개 focus, temporary/candidate ID 1:1 유지
- Form completeness: 14/14
- Evaluable PNI status: 14/14
- Strict all-core morphology evaluability: 7/14
- PNI status: definite 7, probable 1, absent 6, uncertain 0, not-evaluable 0
- PNI transition: unchanged 12, upgraded 1, downgraded 1
- Overall-relation transition: unchanged 9, changed-category 5
- Contour disposition: eligible 13, adjudication required 1, wider context 0, not evaluable 0
- Adjudication 대상: `MORPH-003` / `PRECISE-PNI-004` (`pni_status=probable`)
- 전문의 보완 원본과 reviewer-ID 파생본은 `reviewer_id` 외 필드가 동일함을 재확인
- clean rerun에서 CSV·Markdown·output hash가 동일하고 `run_config.json`은 timestamp 외 동일
- 불변 120건 임상의 원본의 실행 전후 SHA256이 모두 `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`

완료 기준:

- 잠금 산출물 전부 존재
- 모든 수치가 저장 CSV로 추적 가능
- 이전 라벨 연결은 잠금 이후에만 이루어짐
- 재실행 결과가 timestamp를 제외하고 동일
- contour disposition이 각 후보에 대해 명시됨

### M6. 전문의 contour 및 adjudication — 다음 전문의 참여 단계

목적은 임시 원이 아닌 실제 병리 구조 경계를 정량 분석의 기준으로 만드는 것이다.

필수 사전 작업:

- [x] M5 contour disposition 확정: eligible 13건, adjudication 1건
- [x] contour protocol 승인용 초안 작성
- [x] 대상 10개 H&E WSI의 level-0 크기와 OME MPP 확인
- [x] contour protocol v1.0 승인
- [x] 어떤 구조를 그릴지 명확히 정의
- [x] 좌표계, WSI level, MPP 및 파일 형식 확정
- [x] H&E 단독 contour와 IHC 참고 adjudication을 구분
- [x] reviewer에게 이전 모델 score 또는 rank를 표시하지 않는 규칙 고정
- [x] 경계 불명확, 절단면, crush artifact 및 조직 결손 처리 규칙 정의

병리전문의 태스크:

- [ ] 대상 신경의 실제 외곽 경계 그리기 또는 수정
- [ ] 둘 이상의 신경이 있는 경우 각 신경을 별도 객체로 구분
- [ ] 암샘 또는 암세포 집단의 관련 경계 표시
- [ ] 암–신경 직접 접촉 segment 표시
- [ ] surrounding/encasement arc의 시작·종료점 확인
- [ ] intraneural 의심 영역이 있으면 별도 객체로 표시
- [ ] longitudinal tracking 구간이 보이면 시작·종료점 표시
- [ ] 분지점이 보이면 parent/branch 관계 표시
- [ ] contour가 부분적이거나 평가 불가하면 이유 기록
- [ ] probable PNI 또는 불확실 후보의 최종 disposition 결정
- [ ] 자동 또는 초안 contour를 사용한다면 승인·수정 여부 기록

분석팀 태스크:

- [x] QuPath 호환 GeoJSON locator와 annotation schema package 준비
- [x] 연구 목적·로드맵·현재 위치·검토 목표를 포함한 standalone contour HTML 준비
- [x] temporary/private ID와 WSI level-0 좌표의 안전한 연결
- [x] 원본 contour와 수정본의 revision 분리 규칙 고정
- [x] 객체별 unique ID 규칙 고정
- [x] self-intersection, 빈 polygon, WSI 범위 이탈 및 parent reference validator 구현
- [x] pixel 좌표를 µm 단위로 변환하는 WSI별 MPP 확인
- [x] 대표 eligible `MORPH-001` synthetic nerve/tumor/contact/encasement 객체의 case·combined GeoJSON 및 status CSV validator round-trip
- [x] level-0 좌표의 JSON 왕복과 WSI별 MPP pixel–µm–pixel 왕복 보존 확인
- [x] standalone HTML JavaScript 문법 검사 및 combined GeoJSON 좌표계 metadata 확인
- [ ] contour 면적과 둘레의 sanity check
- [ ] 전문의 승인 상태와 수정 이력 저장
- [x] package source hash, 10개 WSI hash 및 output hash 기록
- [ ] 실제 전문의 contour source hash와 revision output hash 기록

권장 전문의 판독 라운드:

1. 1차 contour: eligible focus의 신경 및 interface 경계 작성
2. QC 반환: 자동 geometry 오류 또는 측정 불가능 사례만 재확인
3. 선택적 adjudication: probable/uncertain/not-evaluable 또는 IHC 참고가 필요한 사례

완료 기준:

- 각 분석 대상 신경에 승인된 contour가 존재한다.
- provisional circle과 pathologist-approved contour가 명확히 구분된다.
- contour 없이 직경·포위율·접촉 길이를 확정 결과로 계산하지 않는다.

### M7. PRECISE 형태계측·공간 분석 — contour 승인 후

목적은 focus별 정성 라벨을 재현 가능한 연속형 정량 지표로 확장하는 것이다.

#### M7.1 신경 형태계측

- [ ] 신경 단축 직경
- [ ] 신경 장축 직경
- [ ] 단면적
- [ ] 둘레
- [ ] 장단축비
- [ ] 원형도
- [ ] transverse/oblique/longitudinal orientation에 따른 직경 해석 규칙
- [ ] multiple-nerve field의 객체별 및 focus-level 집계 규칙

#### M7.2 암–신경 상호작용 계측

- [ ] 암–신경 최소거리
- [ ] 직접 접촉 길이
- [ ] 신경 전체 둘레 대비 접촉 비율
- [ ] 포위율 또는 encasement fraction
- [ ] intraneural 면적 또는 길이
- [ ] longitudinal tracking 길이
- [ ] focus별 가장 심한 interaction pattern

#### M7.3 공간 gradient

- [ ] 신경 경계 기준 0–25 µm 영역
- [ ] 25–100 µm 영역
- [ ] 100–500 µm 영역
- [ ] 동일 슬라이드 원거리 암 대조 영역
- [ ] 링 면적, 종양 포함률 및 유효 조직률 기록
- [ ] 동일 focus/환자 내 paired comparison
- [ ] 픽셀 또는 세포를 독립 표본처럼 취급하지 않는 cluster-aware 분석

#### M7.4 영상 표현형

- [ ] H&E 핵 밀도 및 형태
- [ ] gland architecture와 lumen 관련 지표
- [ ] texture 및 색상 지표
- [ ] HMWCK/AMACR 연속절편 등록
- [ ] 등록 QC와 불확실 사례 제외 민감도 분석
- [ ] stain vector/threshold 보정
- [ ] frozen CONCH/Virchow 표현형의 focus 또는 ring-level 탐색

#### M7.5 기존 공간 pilot의 위치

기존 `pni_spatial_pilot`은 7개 PNI와 7개 신경 대조 focus에서 수행한 탐색적 기술 작업이다.

- 10개 paired IHC WSI 선택 추출 및 정합
- 14개 중 자동 등록 QC pass 11개, uncertain 3개
- PNI 7개 중 6개 pass, 1개 uncertain
- AMACR-associated intensity와 positive fraction의 방향이 환자 간 일관되지 않음
- frozen CONCH focus embedding 14개 생성
- provisional nerve circle을 사용했으므로 확정 형태계측으로 간주하지 않음

따라서 기존 pilot은 파이프라인 feasibility와 실패 지점을 알려주는 사전 실험이며, 승인 contour를 사용한 M7 분석을 대체하지 않는다.

완료 기준:

- 모든 주요 측정값이 승인 contour와 저장된 CSV에서 재생성된다.
- 등록 불확실성 및 contour 불확실성의 민감도 분석이 존재한다.
- 작은 표본의 기술·탐색 결과로만 해석한다.

### M8. 확장 코호트 후보선별 및 전문의 판독 운영 검증 — 계획

목적은 PRECISE에서 만든 workflow가 더 큰 자료에서 실제 판독 부담을 줄이면서 연구용 PNI burden을 구축할 수 있는지 평가하는 것이다.

공통 태스크:

- [ ] 코호트별 검체 유형, 환자 수, slide 수 및 접근 조건 확인
- [ ] slide MPP, scanner, stain 및 tissue-mask 품질 확인
- [ ] PNI ground truth와 해부학적 metadata 존재 여부 확인
- [ ] frozen ranker를 그대로 평가할지, 별도 개발 모델을 평가할지 명확히 분리
- [ ] PRECISE 결과를 이용한 threshold 최적화를 외부검증과 혼동하지 않음
- [ ] slide별 후보 수와 spatial NMS 규칙 사전 고정
- [ ] top-k coverage를 확보할 수 있는 판독 sampling 설계
- [ ] high 후보만 판독해 unreviewed 후보를 음성으로 만드는 오류 방지
- [ ] 일부 mid/low/random 또는 sentinel-negative 표본 포함
- [ ] 전문의 판독 시간, 후보당 시간, slide당 시간 및 재판독률 기록
- [ ] 환자·slide·focus 계층을 보존한 데이터 모델 구축
- [ ] 병리전문의 adjudication 규칙 사전 고정

코호트별 예상 역할:

| 코호트 | 우선 역할 | 반드시 확인할 제한 |
|---|---|---|
| SPROB20 | 대규모 전립선 생검에서 후보선별 workflow와 판독 부담 검증 | 통제 접근, core 위치정보와 endpoint 가용성 확인 필요 |
| TCGA-PRAD | 대표 전립선절제술 slide의 observed PNI burden과 BCR·분자 변수 분석 | 전립선 전체가 아닌 대표 절편 |
| PCa_Bx_3Dpathology | 생검 PNI burden·형태와 수술 후 BCR의 탐색 분석 | 50명 규모, recurrence code 원출처 확인 필요 |
| NADT-Prostate | 생검 PNI와 PTEN/ERG/AR/Ki67 등 IHC 표현형 | 장기 예후 자료 없음 |
| PAIP 2021 | 별도 PNI 모델 개발 또는 annotation 기반 기술 검증 | frozen PRECISE 감사와 별도 개발 트랙으로 분리 |
| PROSTATE-FUSED | apex–base 및 central/peripheral topography 파일럿 | PNI 신규 판독 필요, 병리 대상 규모가 작음 |
| PAR/PANDA | 스캐너·기관 일반화와 대규모 후보 제시 | PNI 독립 정답 라벨 부족, 신규 판독 필요 |

SPROB20의 구체적 기여:

- PRECISE보다 훨씬 큰 생검 환경에서 후보선별의 실무적 확장성 평가
- 병리전문의가 slide당 몇 개 후보를 실제로 검토하게 되는지 측정
- 후보 score 분포와 scanner/site 차이 확인
- PNI 확인 후 biopsy-level observed burden 구축
- core 위치와 임상정보가 존재할 경우 위치·치료결정 관련 탐색

SPROB20 접근 전에는 공개 설명만으로 core별 해부학적 위치와 endpoint를 확정하지 않는다.

완료 기준:

- 외부 코호트의 판독 protocol이 분석 전 고정된다.
- 판독 coverage와 workload가 함께 보고된다.
- 외부 자료에서 성능을 평가할 때 개발·튜닝 자료와 완전히 분리된다.

### M9. PNI burden의 임상·분자·예후 분석 — 장기 계획

목적은 PNI를 단순 이분형이 아니라 다차원 observed phenotype으로 표현하고 임상적 의미를 검정하는 것이다.

후보 변수:

- slide당 확인 PNI focus 수
- 분석 종양 면적당 PNI 밀도
- PNI 양성 slide/core 수
- 최대 및 평균 신경 직경
- 최대 및 평균 포위율
- 총 암–신경 접촉 길이
- intraneural invasion 여부와 부담
- longitudinal tracking 여부와 길이
- multiple-nerve 또는 branch-point pattern
- 환자별 가장 심한 interaction pattern

임상 분석 태스크:

- [ ] primary endpoint와 time origin 고정
- [ ] BCR 정의와 censoring 규칙 확인
- [ ] 환자 중복 slide 처리 규칙 고정
- [ ] 기본 임상 모델 사전 지정
- [ ] Gleason/grade group, stage, PSA 등 confounder 처리
- [ ] 결측 임상변수 처리 규칙 문서화
- [ ] 사건 수에 맞춘 변수 수 제한
- [ ] Cox proportional-hazards 가정 점검
- [ ] C-index, time-dependent AUC, Brier score 및 calibration 검토
- [ ] 단순 PNI 유무 대비 burden/morphology의 증분 가치 평가
- [ ] bootstrap 또는 nested cross-validation으로 optimism 평가
- [ ] 다수의 morphology 변수에 대한 과도한 p-value 탐색 방지

분자 분석 태스크:

- [ ] PTEN과 ERG를 우선 가설로 지정할지 결정
- [ ] SPOP, AR, TP53 등은 사건 수와 표본수에 따라 탐색 분석으로 구분
- [ ] 영상과 분자 자료의 환자 매핑 검증
- [ ] batch/site 및 tissue sampling confounding 검토
- [ ] bulk RNA 결과를 PNI 주변 세포 고유 신호로 과해석하지 않음
- [ ] OXPHOS 또는 mitochondrial signature와 실제 mitochondrial transfer를 구분

TCGA 분석의 필수 표현:

> 분석된 대표 슬라이드에서 관찰된 slide-level PNI burden

다음 표현은 금지한다.

> 환자 전체 전립선의 총 PNI burden

### M10. 외부검증·논문화·재현성 공개 — 장기 계획

목적은 개발, 내부 기술 감사, 형태 방법개발, 임상 분석 및 외부검증을 한 결론으로 혼동하지 않고 근거 수준별로 보고하는 것이다.

태스크:

- [ ] claim-evidence matrix 작성
- [ ] 개발·내부감사·외부검증 cohort 명확히 분리
- [ ] 병리전문의 판독자 수와 역할 공개
- [ ] 후보 표본 선정과 미판독 영역의 한계 공개
- [ ] protocol deviations와 adjudication 기록 공개
- [ ] 입력·출력 hash, seed, 환경 및 소프트웨어 버전 기록
- [ ] 모든 figure를 저장된 source CSV로부터 생성
- [ ] 코드·테스트·설계 문서는 Git으로 추적
- [ ] 임상 원본, WSI, 모델 weight 및 생성 대용량 결과는 Git에서 제외
- [ ] 독립 코호트 결과 없이 임상 threshold를 제안하지 않음
- [ ] 논문 결론을 후보선별, 형태 feasibility, 정량 phenotype, 임상 연관성으로 계층화

## 10. 임상 전문의 참여가 필요한 시점

| 판독 라운드 | 내용 | 상태 | 필수 여부 |
|---|---|---|---|
| R1 | PRECISE 후보 120개에서 신경·PNI 기본 판독 | 완료 | 완료됨 |
| R2 | 신경 양성 14개에서 블라인드 형태 재판독 | 완료 | 완료됨 |
| R3 | 실제 신경 및 암–신경 interface contour | 다음 단계 | 필수 |
| R4 | probable/uncertain/등록불량/contour QC 사례 adjudication | 조건부 다음 단계 | 필요 사례만 |
| R5 | SPROB20·TCGA 등 확장 코호트의 상위 후보 판독 | 향후 | 확장 연구에 필수 |
| R6 | 확장 코호트 일부 contour 또는 중증도 판독 | 향후 | 정량 연구에 필수 |
| R7 | 최종 오류 사례 및 외부검증 adjudication | 향후 | 논문화 전 권장 |

R2와 M5 공식 잠금, M6 protocol 승인, contour package 준비 및 synthetic one-case round-trip 검증까지 완료되었다. 실제 브라우저 상호작용과 QuPath 실행은 현재 자동검증 환경에서 수행할 수 없었으므로 성공 처리하지 않았다. 바로 필요한 작업은 실제 전문의 브라우저/QuPath 환경의 한-case round-trip dry run이며, 통과 후 R3 contour를 시작한다. 자유 형식 contour는 사용하지 않는다.

## 11. 즉시 실행할 다음 단계

### 11.1 분석팀이 먼저 수행할 작업

1. [x] `precise_pni_morphology_completed_normalized.csv`를 공식 finalize 입력으로 사용한다.
2. [x] 결과를 build 산출물과 구분되는 `locked/` 디렉터리에 생성한다.
3. [x] 잠금된 candidate ID 연결표, 무결성 보고서, 전이표 및 contour 대상표를 검토한다.
4. [x] 형태 primary endpoint를 세 가지 완료도 정의와 함께 명시한다.
5. [x] 이전 라벨과 달라진 후보를 자동 오류로 간주하지 않고 raw transition으로 보고한다.
6. [x] M5 disposition에서 definite와 absent nerve control 13건을 contour eligible로, probable 1건을 adjudication 대상으로 구분한다.
7. [x] `docs/pathologist_protocol/PRECISE_PNI_CONTOUR_PROTOCOL_KO.md`를 protocol v1.0으로 승인한다.
8. [x] 승인 protocol에 맞는 전문의용 contour package와 구조적 geometry QC validator를 구현한다.
9. [ ] 실제 전문의 브라우저 환경에서 한 case의 HTML GeoJSON export/validator level-0 round-trip dry run을 수행한다.
10. [x] 실제 package의 대표 eligible `MORPH-001`로 synthetic case/combined GeoJSON, status CSV, schema/validator, WSI bounds, parent reference, polygon/line geometry, 1.0 µm interface tolerance 및 MPP 왕복을 검증한다.

### 11.2 다음 전문의 요청 전 승인할 사항

- definite와 probable 모두 contour할지
- absent nerve control도 모두 contour할지 또는 대표 표본만 사용할지
- 신경 외곽 경계와 perineural space 경계를 각각 그릴지
- 종양 전체 경계와 접촉 segment 중 무엇이 필수인지
- multiple-nerve field에서 모든 신경을 그릴지, index nerve만 그릴지
- H&E만 사용할지, adjudication에서 HMWCK/AMACR를 허용할지
- 최소 contour 품질 기준과 재판독 기준
- annotation 파일 형식과 좌표 기준

이 항목들은 `docs/pathologist_protocol/PRECISE_PNI_CONTOUR_PROTOCOL_KO.md`의 protocol v1.0으로 승인되었다. 자동 synthetic round-trip을 통과한 contour package를 준비했으며, 실제 브라우저/QuPath one-case dry run 뒤 전문의 contour 수집을 시작한다. 승인 contour 전에는 확정 계측을 수행하지 않는다.

### 11.3 다음 게이트의 예상 산출물

- 잠금된 morphology review table
- morphology data-integrity report
- previous-versus-rereview transition table
- contour eligibility/adjudication table
- 상세 morphology results report
- contour protocol
- blinded 또는 controlled-unblinded contour interface
- contour QC checklist

## 12. 지금까지 수행한 작업 요약

### 12.1 연구·설계

- frozen-score 기술 감사 설계 승인 및 구현 완료
- 형태 재판독 설계 승인 및 review package 구현 완료
- 임상의용 연구 목적·로드맵·판독 지침 작성 완료
- AI 역할과 금지 해석을 저장소 지침으로 고정

### 12.2 데이터 및 전문의 판독

- 2,264개 frozen 후보 생성
- 120개 층화·블라인드 후보 판독 완료
- 신경 14개와 최초 PNI 7개 확인
- 신경 14개 전부에 대한 블라인드 형태 재판독 완료
- `MORPH-010` 누락 응답 보완 완료
- reviewer ID `Song`의 파생 정규화 완료
- 현재 판독 데이터의 논리 충돌과 필수 형태 항목 누락 0건

### 12.3 기술 감사 및 분석

- 기존 spatial NMS 정확 재현
- top-k focus capture, coverage, subtype, stratum 분석 완료
- ROC-AUC/AP와 환자 cluster bootstrap 완료
- 정의 불가 bootstrap replicate 실패율 보고 완료
- error-review table과 재현 가능한 그림 생성 완료
- 기존 PRECISE H&E–IHC 공간 pilot 수행 및 한계 확인

### 12.4 소프트웨어와 재현성

- frozen audit 단일 실행 스크립트 작성
- morphology build/finalize 단일 실행 스크립트 작성
- 관련 단위 테스트 작성
- 입력·출력 SHA256, seed, 환경 및 버전 기록
- 임상 원본과 생성 대용량 산출물을 Git 추적에서 제외
- Git 저장소 및 GitHub 원격 저장소 설정
- M5 공식 잠금 산출물, 입력·출력 hash 및 clean-rerun 결정성 검증 완료
- M6 standalone contour package clean rebuild와 10개 H&E WSI/input/output hash 재검증 완료
- 대표 eligible `MORPH-001` synthetic case/combined GeoJSON 및 status CSV의 validator round-trip 완료
- level-0 좌표·MPP 왕복, WSI bounds, 객체 유형·parent, polygon/line 및 1.0 µm interface tolerance 자동검증 완료

### 12.5 아직 완료되지 않은 핵심 작업

- 실제 전문의 브라우저/QuPath 환경의 한-case HTML GeoJSON export/validator round-trip dry run
- 전문의 contour 획득
- 승인 contour 기반 형태계측과 spatial 분석 재실행
- SPROB20/TCGA 등 확장 코호트 신규 전문의 판독
- BCR·분자 연관 분석
- 독립 외부검증

## 13. 위험요인과 완화 방법

| 위험 | 연구에 미치는 영향 | 완화 방법 |
|---|---|---|
| PNI 양성 수가 매우 적음 | 불안정한 추정과 과도한 결론 | 기술·방법개발로 제한하고 CI와 raw count 보고 |
| 층화 선택된 120개 | prevalence와 population AUC 왜곡 | reviewed-sample metric으로만 표현 |
| top-k 미판독 후보 존재 | precision 과대평가 가능 | coverage 100%일 때만 precision 계산 |
| 동일 reviewer 반복 판독 | interobserver reliability로 오해 | raw concordance/transition만 보고 |
| `not_evaluable`가 많은 형태 항목 | 형태 완료율 저하 | 결측과 구분하여 보존하고 context/adjudication 단계 운영 |
| provisional nerve circle | 직경·접촉 길이 왜곡 | 전문의 contour 이전에는 확정 계측 금지 |
| 연속절편 등록 오차 | 잘못된 IHC gradient | overlay 수동 QC 및 불확실 사례 민감도 분석 |
| TCGA 대표 절편 | 환자 전체 부담 과대해석 | slide-level observed burden으로 표현 |
| 코호트별 scanner/stain 차이 | 모델 점수 및 형태 측정 이동 | site/scanner audit와 외부검증 |
| 성능을 보고 score를 조정 | audit leakage | frozen audit와 새 모델 개발 트랙 분리 |
| 다수 변수와 적은 BCR event | overfitting 및 거짓 양성 | 우선 가설 제한, nested validation, 탐색/확증 분리 |

## 14. 의사결정 게이트

### Gate 1. 후보선별 감사 통과 — 완료

- 입력·manifest·NMS 일치
- 원본 불변
- 관찰 PNI의 rank concentration 확인
- 임상 threshold로 과해석하지 않음

### Gate 2. 형태 재판독 잠금 — 완료

- 14개 응답 완료
- reviewer ID 확인
- 논리 충돌 0건
- 공식 finalize와 입력·출력 hash 기록 완료
- clean rerun 및 불변 원본 전후 hash 확인 완료

### Gate 3. Contour 승인 — package 준비 완료, 전문의 contour 대기

- 대상 disposition 고정: contour eligible 13, adjudication 1
- contour protocol v1.0 승인
- contour package와 geometry QC validator 구현·결정성 검증 완료
- 대표 eligible case의 synthetic HTML-export 형식/validator/MPP round-trip 검증 완료
- 실제 전문의 브라우저/QuPath 환경에서 한-case HTML export/validator round-trip dry run 필요
- 병리전문의 승인 contour 확보
- 좌표·geometry QC 통과

### Gate 4. 정량 분석 승인

- MPP와 등록 QC 통과
- 측정 재현성 확인
- 분석 및 민감도 규칙 고정

### Gate 5. 확장 코호트 진입

- 판독 workload와 sampling protocol 사전 고정
- unreviewed candidate 처리 규칙 확정
- 개발/검증 cohort 분리

### Gate 6. 임상 결론 허용

- 충분한 환자와 사건 수
- 임상 공변량 포함
- 독립 검증
- claim-evidence 일치

## 15. 파일 및 코드 지도

### 승인 설계

- `projects/precise_pni_candidate_triage/docs/designs/2026-08-05-precise-pni-frozen-score-audit-design.md`
- `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`

### 주요 실행 코드

- `projects/precise_pni_candidate_triage/code/candidate_visualization/pilot_precise_pni_candidates.py`
- `projects/precise_pni_candidate_triage/code/candidate_visualization/build_precise_pni_review_html.py`
- `projects/precise_pni_candidate_triage/code/frozen_score_audit/audit_precise_pni_frozen_scores.py`
- `projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py`

### 주요 테스트

- `tests/test_precise_pni_frozen_score_audit.py`
- `tests/test_precise_pni_morphology_review.py`

### frozen audit 결과

- `resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit/RESULTS_REPORT.md`
- `resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit/candidate_audit_table.csv`
- `resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit/review_budget_capture.csv`
- `resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit/score_metric_summary.csv`
- `resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit/cluster_bootstrap_replicates.csv`
- `resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit/run_config.json`

### 형태 재판독

- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/precise_pni_morphology_review.html`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/private_case_mapping.csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/precise_pni_morphology_completed (1) (2).csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/precise_pni_morphology_completed_normalized.csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/normalized_morphology_review.csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/morphology_data_integrity_report.csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/morphology_transition_table.csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/contour_eligibility_table.csv`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/MORPHOLOGY_RESULTS_REPORT.md`
- `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/run_config.json`

### Contour 준비

- `projects/precise_pni_candidate_triage/docs/pathologist_protocol/PRECISE_PNI_CONTOUR_PROTOCOL_KO.md`
- `projects/precise_pni_candidate_triage/code/contour_review/build_precise_pni_contour_review.py`
- `tests/test_precise_pni_contour_review.py`
- `resources/data/shared/opendataset/PRECISE/pni_contour_review/private_contour_case_manifest.csv`
- `resources/data/shared/opendataset/PRECISE/pni_contour_review/contour_review_status_template.csv`
- `resources/data/shared/opendataset/PRECISE/pni_contour_review/contour_annotation_schema.json`
- `resources/data/shared/opendataset/PRECISE/pni_contour_review/contour_qc_report.csv`
- `resources/data/shared/opendataset/PRECISE/pni_contour_review/contour_run_config.json`
- `resources/data/shared/opendataset/PRECISE/pni_contour_review/precise_pni_contour_review.html`

### 기존 공간 pilot

- `resources/data/shared/opendataset/PRECISE/pni_spatial_pilot/RESULTS_REPORT.md`
- `resources/data/shared/opendataset/PRECISE/pni_spatial_pilot/nerve_annotations_v1.csv`
- `resources/data/shared/opendataset/PRECISE/pni_spatial_pilot/registration_qc.csv`
- `resources/data/shared/opendataset/PRECISE/pni_spatial_pilot/spatial_features.csv`

## 16. 현재 결론

후보선별기의 기술 감사, 14건 형태 재판독 수집 및 M5 공식 잠금·전이 분석은 완료되었다. 현재 결과는 AI가 PNI를 진단한다고 결론내리는 근거가 아니라, 선택된 PRECISE 표본에서 관찰된 PNI가 높은 후보 순위에 집중되었고 구조화된 형태 재판독과 후속 contour 대상 구분이 수행 가능했음을 보여주는 방법개발 근거이다.

Contour protocol v1.0 승인, 13건 primary/1건 adjudication standalone HTML package 구축, 대표 eligible `MORPH-001`의 synthetic GeoJSON/status/validator/MPP round-trip은 완료되었다. 실제 브라우저 클릭·다운로드와 QuPath 재반입은 자동검증 환경에서 수행할 수 없어 완료로 간주하지 않았다. 즉시 다음 작업은 실제 전문의 브라우저/QuPath 환경에서 한 case의 GeoJSON export/validator level-0 round-trip을 확인한 뒤, 병리전문의가 실제 신경 및 암–신경 interface contour를 작성·승인하는 것이다. 승인 contour가 확보된 뒤에야 신경 직경, 포위율, 접촉 길이 및 PNI 주변 공간 gradient를 확정적으로 계산할 수 있다.
