네. 이번 Major Revision은 “분석을 많이 추가하는 것”보다 핵심 주장에 대한 통계적 신뢰성을 먼저 복구하고, 그 결과에 맞춰 원고의 주장 범위를 재조정하는 방식으로 진행하는 것이 좋습니다.

## 개정 목표

최종 논문은 다음 여섯 주장만 명확히 입증하도록 재구성합니다.

1. qualification framework 자체의 유용성
2. Gleason·phenotype의 기관 간 zero-shot 전이
3. PTEN 신호의 grade 독립성과 다기관 안정성
4. SPOP의 재현 가능한 null
5. AR의 grade shortcut이 아닌 site-instability
6. marker 7의 탐색적 결과와 encoder-dependent transfer

## 1단계 — 주장과 프로토콜 동결

가장 먼저 분석 전에 개정판의 claim hierarchy를 고정합니다.

- “전체 연구가 prespecified”라는 표현 삭제
- “일부 downstream qualification 분석 전에 prospectively frozen”으로 변경
- marker 7은 모든 표·그림에서 `post-hoc exploratory marker`로 표시
- PTEN은 `cross-cohort validated` 대신 `multisite-stable within TCGA-PRAD`로 표현
- AR은 통계적 유의성과 관계없이 `context-sensitive` 유지
- protocol-freeze commit hash와 timestamp 기록
- primary/secondary/exploratory endpoint를 표로 고정

산출물:

- `revision_analysis_plan.md`
- claim–evidence matrix
- protocol 변경 이력표

## 2단계 — Confounder audit 재분석

이번 개정의 가장 중요한 작업입니다.

### 2.1 Nested cross-fitting

환자 단위 outer CV를 새로 구성합니다.

각 outer fold에서:

1. training 환자만 이용해 image probe 학습
2. training 내부에서 image score 생성 및 meta-model 학습
3. outer test 환자에는 완전히 고정된 모델 적용
4. grade-only와 grade+image 모델을 동일 test fold에서 비교

평가:

- PTEN: AUROC, ΔAUROC
- AR: Spearman ρ 또는 out-of-sample R²
- marker 7: C-index, ΔC-index
- 모든 증분 성능에 patient-cluster bootstrap 95% CI

### 2.2 올바른 permutation test

각 permutation에서 다음 전체 과정을 다시 수행합니다.

- grade 층 안에서 label permutation
- image probe 재학습
- nested CV 재실행
- held-out 증분 성능 계산

먼저 200회로 구현을 검증하고, 최종 결과는 2,000회 이상 수행합니다.

### 2.3 임상 공변량 확장

TCGA에서 확보 가능한 범위 내에서 다음 모델을 순차 비교합니다.

- M0: grade
- M1: grade + age
- M2: grade + PSA + pT stage
- M3: grade + PSA + stage + surgical margin
- M4: M3 + site
- M5: M4 + image score

결측률과 complete-case 표본 수를 모델별로 명시하고, 가능하면 multiple imputation 민감도 분석을 추가합니다.

판정 기준:

- PTEN이 재분석에서도 유의하면 `qualified`
- AR은 grade 독립성이 유지돼도 site 불안정으로 `context-sensitive`
- marker 7이 다변량 조정 후 유지되면 “incremental prognostic signal”
- 유지되지 않으면 “grade-associated exploratory signal”로 하향

## 3단계 — TCGA recurrence endpoint 검증

### 3.1 라벨 provenance 공개

환자별로 다음 필드를 갖는 mapping table을 생성합니다.

- 원시 follow-up 기록
- disease response
- event 판정 근거
- event time 또는 censoring time
- 제외 사유
- 최종 endpoint

개인정보를 포함하지 않는 TCGA case ID 수준으로 공개합니다.

### 3.2 Endpoint 민감도 분석

가능한 endpoint들을 별도로 구성합니다.

- 현재 `wt-with tumor` 기반 endpoint
- persistent/residual disease 제외 endpoint
- 표준 TCGA PFI
- 확보 가능한 경우 DFI 또는 RFS
- 3년 및 5년 landmark endpoint

각 정의 사이에 다음을 보고합니다.

- 환자 수와 event 수
- event concordance
- time concordance
- C-index
- time-dependent AUC
- marker 7 위험도와 censoring time의 상관

판정 기준:

- 여러 endpoint에서 방향과 성능이 유지되면 외부 전이 주장 유지
- 현재 정의에서만 유지되면 “endpoint-specific transfer”
- persistent disease를 제외하면 사라질 경우 recurrence claim 철회

## 4단계 — 모델·타일·기관 안정성 분석

### 4.1 타일 민감도

핵심 마커에 공통 grid를 적용합니다.

- tile count: 16, 32, 64, 가능하면 128
- sampling seed: 최소 5개
- scale: encoder별 대표 2–3개 mpp
- encoder: CONCH, Virchow

대상:

- Gleason
- phenotype
- PTEN
- SPOP
- AR
- marker 7

결과는 평균 성능뿐 아니라 seed 간 표준편차와 방향 반전 여부까지 보고합니다.

### 4.2 AR site forest plot

사이트별로 다음을 표시합니다.

- 환자 수
- 효과크기 ρ
- bootstrap 95% CI
- AR score 분포
- Gleason 분포
- scanner 또는 stain 정보
- pooled random-effects estimate는 보조적으로 제시

### 4.3 SPOP null 보강

- class-weight 적용/미적용
- 16/64/128 tiles
- tumor-enriched sampling
- site-restricted 분석
- CONCH/Virchow
- 검출 가능한 최소 AUROC 또는 precision 기반 power analysis

“유의하지 않았다”보다 “현재 설계에서 AUROC X 이상은 어느 정도 배제할 수 있다”는 결론을 목표로 합니다.

## 5단계 — 생존분석 보고 강화

기존 C-index와 5년 AUC에 다음을 추가합니다.

- 1–5년 time-dependent AUC curve
- integrated Brier score
- calibration slope
- 3년/5년 calibration plot
- hazard ratio와 95% CI
- clinical-only, image-only, combined 모델 비교
- bootstrap 기반 ΔC-index/ΔBrier CI

PCA component 수는 nested CV 안에서 선택하거나, `k=8`을 탐색적으로 선택했다고 명확히 표시합니다. 4–64 성분 sweep 결과는 sensitivity appendix로 이동합니다.

## 6단계 — 보고·재현성 정비

### 코드 및 데이터

- `/tmp/claude-...` 절대경로 제거
- TCGA clinical data 생성 스크립트 제공
- cohort manifest와 데이터 dictionary 추가
- 모든 seed, fold assignment, tile coordinate 저장
- 표와 그림을 원시 결과에서 자동 생성
- 환경 파일과 실행 명령 제공

### 통계표

13개 가설에 대해 한 표에 다음을 모두 포함합니다.

- n patients / n slides
- effect size
- patient-level 95% CI
- uncorrected p
- BH q
- encoder
- validation type
- reliability tier

현재처럼 patient metric 옆에 slide-level CI가 배치되지 않도록 수정합니다. Confounder audit에서 생긴 신규 검정까지 어떤 FDR family에 포함했는지도 명시합니다.

## 7단계 — 원고 재작성

현재 장문의 프로젝트 보고서를 직접 다듬기보다 qualification 논문을 별도의 투고 원고로 재구성하는 편이 좋습니다.

권장 본문 구조:

1. Introduction: shortcut과 qualification 문제
2. Prespecified components and exploratory components
3. Cohorts and frozen encoders
4. Qualification gates
5. Core marker results
6. Confounder and site audits
7. Downstream recurrence transfer
8. Failure modes
9. Limitations

핵심 그림:

- Figure 1: qualification protocol
- Figure 2: five-tier reliability map
- Figure 3: cross-cohort/cross-encoder marker 결과
- Figure 4: PTEN confounder audit 및 AR site forest plot
- Figure 5: recurrence transfer와 임상변수 증분 분석
- Figure 6: scale/tile/encoder sensitivity
- Supplement: 13개 가설, 전체 CI/p/q, endpoint 정의, 추가 ablation

## 실행 우선순위

1. Confounder audit 재설계
2. TCGA endpoint 재구축 및 검증
3. marker 7 다변량 생존분석
4. AR site forest plot
5. 타일·scale·seed sensitivity
6. SPOP power 분석
7. 재현성 패키지 정리
8. 원고와 rebuttal 작성

핵심 의사결정은 2단계와 3단계 결과 후에 내립니다. 해당 결과가 약해지더라도 분석을 추가해 기존 결론을 보존하려 하지 않고, reliability tier와 문구를 기계적으로 하향 조정하는 것이 이번 논문의 audit 철학과 가장 잘 맞습니다.