# 기반 모델 정량지표 검증 사전실험 실행계획

- 문서 버전: 0.1
- 기준일: 2026-08-11
- 문서 성격: P0 사전실험의 마일스톤·태스크·To-do·의사결정 게이트
- 대상 모델: frozen CONCH와 frozen Virchow
- 후속 본 연구: `projects/quantitative_foundation_model_validation/docs/research_plan/14_FOUNDATION_MODEL_QUANTITATIVE_METRIC_VALIDATION_PLAN_KO.md`
- 적용 원칙: 일정이 아니라 사전 정의된 게이트 통과 여부가 다음 단계 진입을 결정한다.

## 1. 사전실험의 한 문장 목표

이미 정답과 수치형 표적이 있는 동일 표본에서 두 기반 모델이 독립적인 정량
병리개념을 실제로 복원할 수 있는지, 그 차이가 표본·좌표·물리적 시야·probe·누출이
아닌지를 작은 범위에서 먼저 검증하여 본 연구의 실행 가능성과 허용 범위를 결정한다.

## 2. 왜 별도의 P0 단계가 필요한가

본 연구는 의료 Tier 1–4 지표, 별도 모델평가·통계·QC analysis registry, 질병 endpoint, 외부 코호트와 신규 지표 후보를
동시에 다룬다. 바로 대규모 embedding 추출과 상보성 분석으로 진행하면 다음 위험을
구분하기 어렵다.

1. 두 모델이 실제로 서로 다른 표본을 본 데서 생긴 차이
2. pixel 크기는 같지만 물리적 시야가 다른 데서 생긴 차이
3. 환자 또는 slide 누출로 인한 과대평가
4. 정량지표 자체가 AI에서 파생된 순환 검증
5. probe 용량과 tuning budget 차이로 인한 불공정 비교
6. 표본 수가 작은데 반복 fold를 독립 관측치로 간주한 오류
7. 모델이 정량개념을 담지 못한 것과 계측 표적이 불안정한 것을 혼동하는 오류

P0의 목적은 임상 성능을 확정하는 것이 아니라 이러한 실패 가능성을 조기에 제거하고,
본 연구에 들어갈 모델·표적·시야·분석 단위를 좁히는 것이다.

## 3. 연구 목적과 비목적

### 3.1 목적

1. 기존 결과를 공통 표본 기준으로 재구성할 수 있는지 확인한다.
2. 두 모델을 동일 좌표와 동일 물리적 시야에서 1:1 비교할 수 있는지 확인한다.
3. 독립적으로 계측된 수치형 병리개념을 frozen embedding이 복원하는지 확인한다.
4. 모델 간 차이가 encoder, scale, sampling 또는 자료 품질 중 무엇과 연관되는지 분리한다.
5. P0 결과에 따라 본 연구 FM0–FM10 중 진행 가능한 단계를 명시적으로 잠금 해제한다.

### 3.2 비목적

- P0만으로 CONCH 또는 Virchow의 보편적 우월성을 선언하지 않는다.
- P0 결과를 whole-slide PNI 진단 성능, 유병률 또는 환자 예후로 해석하지 않는다.
- PRECISE 14개 nerve-positive focus를 독립 검증 코호트로 간주하지 않는다.
- contour가 잠기기 전에 nerve geometry를 1차 표적으로 사용하지 않는다.
- frozen-score audit의 score, prompt, exemplar, weights, 좌표, window 또는 NMS를 변경하지 않는다.
- unreviewed candidate, missing, uncertain 또는 not-evaluable을 음성으로 변환하지 않는다.
- 반복 seed, fold 또는 stability cell을 독립 validation sample로 세지 않는다.

## 4. P0 핵심 연구질문

| ID | 질문 | 최소 답변 형태 |
|---|---|---|
| P0-Q1 | 공통 표본과 정답이 두 모델에서 정확히 일치하는가? | membership·truth mismatch 감사표 |
| P0-Q2 | 독립 정량개념이 각 모델 표현에서 chance보다 잘 복원되는가? | OOF 효과량·grouped permutation |
| P0-Q3 | 어느 개념이 두 모델 공통이고 어느 개념이 모델 특이적인가? | paired delta·불확실성·방향성 |
| P0-Q4 | 결과가 FOV, scale, tile sampling과 probe에 얼마나 민감한가? | 사전 정의 sensitivity matrix |
| P0-Q5 | 기존의 강한·약한 표적 패턴을 공통 표본 재분석이 재현하는가? | positive/weak control 결과 |
| P0-Q6 | 본 연구에서 허용할 model–target–FOV 조합은 무엇인가? | gate 및 unlock matrix |

## 5. 사전실험 분석 프레임

### Frame A. NADT 공통 환자 양성대조

- 현재 CONCH와 Virchow 결과에서 정확히 공통인 39명 환자를 사용한다.
- Gleason과 tumor/benign phenotype을 source positive control로 사용한다.
- 두 모델별 파일을 따로 평가한 결과와 공통 환자만의 paired 결과를 구분한다.
- 39명은 feasibility 표본이며 일반화 성능을 확정할 표본으로 사용하지 않는다.

### Frame B. PANDA 공통 영상 표본 감사

- 현재 CONCH 1,137개 행, Virchow 1,169개 행 가운데 공통 image ID 1,123개를 잠근다.
- CONCH-only 14개와 Virchow-only 46개는 삭제하지 않고 제외 사유를 기록한다.
- 공통 표본에서 ISUP truth 불일치가 0인지 실행 때마다 확인한다.
- subject 연결이 검증되기 전에는 이 분석 단위를 `patient`가 아닌 `image/case`로 표기한다.
- PANDA는 membership과 외부 표본 기술의 감사 프레임이며, 동일 ROI paired tile을
  보장하지 않으면 표현 유사성의 주 분석으로 사용하지 않는다.

### Frame C. 기존 Gate A 안정·불안정 대조

- `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv`: 360개 설계 cell
- `resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv`: 360개 결과 cell
- `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv`: 1,800개 fold 결과
- `resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv`: 60개 좌표 manifest 행
- 예상 대조 역할은 다음과 같이 사전 고정한다.

| 역할 | 기존 표적 | P0에서의 용도 |
|---|---|---|
| 안정 양성대조 | Gleason, phenotype | 파이프라인이 명백한 병리 신호를 복원하는지 확인 |
| 상대적 안정 대조 | PTEN | 중간 난이도 concept 재현성 확인 |
| 불안정 대조 | SPOP | 표본·class·site 민감성 탐지 |
| encoder/scale 의존 대조 | recurrence | 모델·시야 의존성 탐지 |
| 약한 연속 대조 | AR | 무효에 가까운 결과를 과대해석하지 않는지 확인 |

360개 cell과 1,800개 fold는 동일 환자에서 반복된 상관 관측치이다. 유효 표본 수나
외부 검증 횟수로 계산하지 않고, 분석의 독립 단위는 subject 또는 적절한 case로 둔다.

### Frame D. PRECISE 동일 tile 정량개념 파일럿

PRECISE에서 pixel-level 전문가 주석과 필요한 품질 정보가 있는 모든 적격 tile을 먼저
선정한다. 14개 PNI focus나 미승인 contour를 주 분석에 사용하지 않는다.

동일 tile 중심과 동일 물리적 FOV에서 frozen CONCH와 frozen Virchow embedding을
추출한다. 주 분석의 정량 표적은 다음 세 개 family이다.

| 우선순위 | 정량 표적 | 기준원 | 필수 조건 |
|---|---|---|---|
| 1차 | tumor fraction | 전문가 tumor mask | AI score와 독립, 유효 pixel 분모 명시 |
| 1차 후보 | nuclear density/mm² | 독립·고정 nuclei 계측 | 검증 subset의 수동계수 또는 승인 성능 필요 |
| 1차 후보 | gland/lumen fraction | 전문가 주석 또는 독립·고정 segmentation | 계측 repeatability와 실패 로그 필요 |
| 2차 | stroma fraction | 독립 주석/segmentation | 종양·lumen 정의와 중복 규칙 명시 |
| 2차 | H&E texture entropy/homogeneity | 사전 고정 영상 계산 | 색·배율 민감성 분석 |
| QC | tissue/valid-pixel fraction | 영상 QC | biological endpoint로 사용 금지 |

`1차 후보`는 독립성·repeatability 게이트를 통과해야 1차 표적이 된다. 통과하지 못하면
2차 또는 기술적 분석으로 강등한다. 같은 CONCH/Virchow 표현이나 예측으로 만든 값을
독립 ground truth로 사용할 수 없다.

## 6. 분석 공통 원칙

- 모델 weights는 동결한다. 정량개념 probe만 학습할 수 있다.
- 두 모델은 같은 subject-grouped split과 같은 fold assignment를 공유한다.
- 같은 저용량 probe family와 같은 tuning budget을 적용한다.
- 모든 주 결과는 out-of-fold prediction에서 재계산 가능해야 한다.
- permutation은 subject/case grouping을 보존한다.
- 불확실성은 subject-cluster bootstrap 또는 paired bootstrap으로 계산한다.
- tile-level 수를 표본 수처럼 보고하지 않는다.
- primary family, 방향, 통계량, 제외 규칙과 sensitivity 범위를 결과 전에 고정한다.
- 결측값은 보존하며 누락 사유별로 집계한다.
- 음성대조에는 label permutation과 가능하면 좌표/sample permutation을 포함한다.

## 7. P0 마일스톤 요약

| ID | 마일스톤 | 핵심 산출물 | 판정 게이트 |
|---|---|---|---|
| P0-M0 | protocol·claim lock | 승인 protocol/run config | P0-G0 |
| P0-M1 | 지표 적격성·독립성 감사 | metric eligibility table | P0-G1 |
| P0-M2 | 공통 표본·truth 감사 | paired membership manifest | P0-G2 |
| P0-M3 | 기존 결과 공통표본 재분석 | positive/weak control report | P0-G3 |
| P0-M4 | PRECISE tile·정량표적 manifest | paired tile/target manifest | P0-G4 |
| P0-M5 | paired embedding·기술 QC | embedding manifest/QC | P0-G5 |
| P0-M6 | 정량 concept probe | OOF/permutation 결과 | P0-G6 |
| P0-M7 | 표현·scale·sampling·discordance 감사 | robustness report | P0-G7 |
| P0-M8 | 통합 판정 | gate/unlock matrix | P0-G8 |
| P0-M9 | clean rerun·인계 | reproducibility bundle | P0-G9 |

## 8. 마일스톤별 태스크·To-do·진행 조건

### P0-M0. Protocol·claim lock

목적: 결과 확인 전에 질문, 표적, 비교 단위와 허용 주장을 잠근다.

진입 조건:

- 본 문서와 본 연구 실행계획이 연구팀 검토 대상이 된다.
- 사용할 frozen model artifact를 식별할 수 있다.

To-do:

- [ ] P0 primary/secondary/exploratory 질문을 구분한다.
- [ ] CONCH와 Virchow의 model ID, revision과 weight hash를 기록한다.
- [ ] cohort별 source file과 예상 hash inventory를 만든다.
- [ ] subject, case, slide, ROI와 tile의 분석 단위를 정의한다.
- [ ] primary target, 측정 단위와 성공 방향을 지정한다.
- [ ] probe family, tuning budget, split, permutation과 bootstrap 계획을 고정한다.
- [ ] shared/native FOV와 허용 sensitivity 범위를 지정한다.
- [ ] exclusion, missing, uncertain, not-evaluable 처리 규칙을 잠근다.
- [ ] 허용 주장과 금지 주장을 `claim_evidence_matrix` 초안에 기록한다.
- [ ] frozen-score audit 산출물과 P0 산출물 경로를 분리한다.

필수 산출물:

- `PROTOCOL.md`, `run_config.json`, `source_inventory.csv`
- `claim_evidence_matrix.csv`, `deviation_log.csv`

P0-G0 통과 조건:

- 결과를 보기 전에 protocol ID와 승인 상태가 기록되어 있다.
- 모델·표적·분할·통계·주장 범위가 모두 기계 판독 가능하게 정의되어 있다.

실패 시:

- 승인 전 분석은 `exploratory`로만 보존한다.
- 승인되지 않은 분석 결과로 threshold나 표적을 다시 선택하지 않는다.

통과 후 열리는 단계: P0-M1, P0-M2와 본 연구 FM0의 준비 작업.

### P0-M1. 정량지표 적격성·독립성 감사

목적: 무엇이 생물학적 표적이고 무엇이 AI output, 임상 endpoint 또는 QC인지 분리한다.

진입 조건: P0-G0 통과.

To-do:

- [ ] P0 후보 지표마다 `metric_role`과 `analysis_unit`을 부여한다.
- [ ] reference source와 CONCH/Virchow로부터의 독립성을 기록한다.
- [ ] 알고리즘 계측이면 알고리즘 version, 고정 여부와 검증 근거를 기록한다.
- [ ] repeatability, 단위, 분모와 허용 범위를 확인한다.
- [ ] AI-derived 값이 primary biological target에 포함되지 않는지 확인한다.
- [ ] contour 미승인 지표를 `deferred`로 유지한다.
- [ ] QC와 performance metric이 환자 feature로 들어가지 않는지 검사한다.
- [ ] 의료 tier와 별도 analysis registry 전 행에서 P0 사용 가능·후속·제외 역할을 연결한다.

필수 산출물: `metric_eligibility.tsv`, `measurement_provenance.csv`.

P0-G1 통과 조건:

- 모든 P0 지표가 `primary`, `secondary`, `QC`, `exploratory`, `deferred`, `excluded`
  중 하나로 분류되어 있다.
- primary 표적은 두 encoder와 독립이며 계산 정의와 단위가 고정되어 있다.
- 계측 불확실성이 큰 지표는 primary에서 강등되어 있다.

실패 시:

- 독립성은 확보되지만 repeatability가 불충분하면 descriptive 분석만 허용한다.
- AI-derived이거나 reference provenance가 불명확하면 해당 지표를 제외한다.

통과 후 열리는 단계: P0-M3의 표적 분석, P0-M4, 본 연구 FM1.

### P0-M2. 공통 표본·정답·누출 감사

목적: 모델 차이가 표본 membership 또는 truth 차이에서 나오지 않도록 한다.

진입 조건: P0-G0 통과.

To-do:

- [ ] NADT 39명 공통 환자 ID와 truth를 재검증한다.
- [ ] PANDA 공통 1,123 image ID와 ISUP truth를 재검증한다.
- [ ] 각 모델에만 있는 표본을 별도 manifest로 보존한다.
- [ ] duplicate subject, slide, serial section과 재촬영 여부를 표시한다.
- [ ] train/validation/test 간 subject leakage를 검사한다.
- [ ] label provenance와 변환 규칙을 대조한다.
- [ ] exclusion flow와 mismatch 사유를 기계 판독 가능한 코드로 기록한다.
- [ ] 원본 파일의 pre-analysis hash를 기록한다.

필수 산출물:

- `common_sample_manifest.csv`, `membership_mismatch.csv`
- `truth_mismatch.csv`, `leakage_audit.csv`, `exclusion_flow.csv`

P0-G2 통과 조건:

- 공통 manifest의 ID가 고유하고 두 모델 membership이 1:1로 연결된다.
- 공통 표본의 primary truth mismatch가 0이다.
- subject leakage가 0이며, 모델별 전용 표본은 누락되지 않고 사유가 기록된다.

실패 시:

- ID 규칙 또는 병합 오류이면 수정 후 P0-M2를 처음부터 재실행한다.
- truth provenance가 화해되지 않으면 해당 cohort/endpoint를 중단한다.
- leakage가 제거되지 않으면 predictive evidence로 사용하지 않는다.

통과 후 열리는 단계: P0-M3, P0-M4와 본 연구 FM2의 제한적 준비.

### P0-M3. 기존 결과의 공통표본 paired 재분석

목적: 새 대규모 추출 전에 기존 파일로 평가 파이프라인과 대조군이 작동하는지 확인한다.

진입 조건: P0-G0–G2 통과.

To-do:

- [ ] NADT Gleason과 phenotype을 공통 39명에서 paired 재평가한다.
- [ ] PANDA는 검증된 분석 단위에서 공통표본 결과와 모델별 전체 결과를 분리 보고한다.
- [ ] 기존 stability 결과를 subject/case 단위로 재요약한다.
- [ ] Gleason/phenotype, PTEN, SPOP, recurrence, AR의 사전 역할과 관찰 결과를 비교한다.
- [ ] 두 모델에 같은 성능 계산과 불확실성 방법을 적용한다.
- [ ] 360 cell/1,800 fold를 독립 표본으로 사용하지 않았는지 검사한다.
- [ ] grouped label permutation 분포와 관찰 통계량을 저장한다.
- [ ] 예상과 다른 결과도 숨기지 않고 원인 가설만 분리 기록한다.

필수 산출물:

- `existing_common_sample_results.csv`, `existing_paired_deltas.csv`
- `existing_permutation_null.csv`, `positive_control_report.md`

P0-G3 통과 조건:

- 각 모델에서 사전 지정 source positive control 중 최소 하나가 subject/case-grouped
  permutation의 95백분위수를 초과한다.
- 모든 결과가 저장된 OOF 또는 subject/case-level prediction에서 재생성된다.
- 불안정 대조의 실패는 pipeline 실패와 구분되어 보고된다.

조건부 통과:

- 한 모델만 positive control을 통과하면 해당 모델의 파일럿은 계속할 수 있으나
  cross-model 우열 결론은 금지하고 다른 모델의 preprocessing/FOV를 먼저 감사한다.

실패 시:

- 두 모델 모두 source positive control을 통과하지 못하면 P0-M4 이후의 대규모 추출을
  중단하고 label, split, preprocessing과 평가 구현을 재감사한다.

통과 후 열리는 단계: P0-M4–M5와 본 연구 FM3 준비.

### P0-M4. PRECISE paired tile·정량표적 manifest

목적: 같은 조직 영역과 독립 정량표적이 있는 분석 universe를 결과 전에 고정한다.

진입 조건: P0-G1–G3 통과.

To-do:

- [ ] 모든 pixel-level 전문가 주석 tile의 전체 inventory를 만든다.
- [ ] subject/slide/ROI/tile ID와 중심 좌표를 연결한다.
- [ ] MPP, tile 크기와 물리적 FOV를 계산한다.
- [ ] tissue, blur, pen, fold, saturation 등 기술 QC를 계산한다.
- [ ] tumor fraction 분모와 valid-pixel 규칙을 검증한다.
- [ ] nuclei와 gland/lumen 계측의 독립성·repeatability 근거를 연결한다.
- [ ] target별 유효 subject 수, tile 수, 분포와 결측 사유를 보고한다.
- [ ] subject-grouped fold별 최소 표본과 값의 변이를 확인한다.
- [ ] 14개 PNI focus와 미승인 contour가 primary universe에 섞이지 않았는지 검사한다.
- [ ] 최종 inclusion/exclusion manifest를 hash와 함께 동결한다.

필수 산출물:

- `paired_tile_manifest.csv`, `quantitative_targets.csv`
- `target_availability.csv`, `tile_qc.csv`, `fold_assignments.csv`

P0-G4 통과 조건:

- 두 모델이 동일 중심과 동일 physical FOV를 사용할 수 있다.
- primary target별 적격 subject가 최소 20명이고 validation fold마다 최소 4명이 있다.
- primary target에 충분한 실제 변이가 있으며 ID 중복과 leakage가 없다.
- 이 최소치는 feasibility floor이지 본 연구의 power 정당화가 아니다.

조건부 통과:

- 표본 수 또는 fold 분포가 기준에 미달하면 predictive benchmark가 아니라 기술·서술형
  파일럿으로만 진행하고 본 연구 전에 별도 power 및 표본 확대 계획을 요구한다.

실패 시:

- 동일 좌표/FOV가 재구성되지 않거나 독립 표적이 없으면 Frame D 비교를 중단한다.

통과 후 열리는 단계: P0-M5와 본 연구 FM2의 paired-manifest 설계.

### P0-M5. CONCH–Virchow paired embedding 및 기술 QC

목적: 정확히 같은 표본에서 재현 가능한 frozen representation을 생성한다.

진입 조건: P0-G3 통과 및 P0-G4 통과 또는 서술형 조건부 통과.

To-do:

- [ ] 동일 tile ID·중심·FOV로 CONCH embedding을 생성한다.
- [ ] 동일 tile ID·중심·FOV로 Virchow embedding을 생성한다.
- [ ] shared FOV를 주 분석으로, native FOV를 sensitivity로 분리한다.
- [ ] 행 수, sample order, embedding 차원, dtype을 검사한다.
- [ ] NaN/Inf, norm outlier와 추출 실패를 집계한다.
- [ ] hardware, software, model revision과 execution time을 기록한다.
- [ ] 재시도·실패·제외의 원인을 로그에 남긴다.
- [ ] 정해진 subset을 두 번 추출하여 결정성 허용오차를 검사한다.
- [ ] embedding과 metadata hash를 기록한다.

필수 산출물:

- `paired_embedding_manifest.csv`, `embedding_qc.csv`
- `extraction_failures.csv`, `determinism_check.csv`

P0-G5 통과 조건:

- 두 모델의 sample ID와 순서가 100% 일치한다.
- 예상 행 수와 차원이 일치하고 NaN/Inf가 0이다.
- 원본 hash가 변하지 않았으며 재추출이 사전 허용오차 이내에서 일치한다.

실패 시:

- 모델 간 누락이 발생하면 교집합으로 몰래 축소하지 않고 원인을 수정한 뒤 manifest부터
  다시 잠근다. 해결되지 않으면 cross-model paired 분석을 중단한다.

통과 후 열리는 단계: P0-M6–M7와 본 연구 FM3의 제한적 실행.

### P0-M6. 정량개념 복원 probe 및 음성대조

목적: 각 frozen representation이 독립 수치형 표적을 chance보다 잘 복원하는지 확인한다.

진입 조건: P0-G1, G2, G4와 G5 통과.

To-do:

- [ ] 두 모델이 동일 fold assignment를 공유하도록 한다.
- [ ] 동일한 저용량 regularized probe와 tuning budget을 사용한다.
- [ ] target별 OOF prediction을 전부 저장한다.
- [ ] 연속 표적의 MAE, R²와 Spearman correlation을 계산한다.
- [ ] model A–B 차이를 subject-cluster paired bootstrap으로 계산한다.
- [ ] subject-grouped label permutation을 수행한다.
- [ ] sample/coordinate permutation 음성대조를 가능한 범위에서 수행한다.
- [ ] fold별 표본 수, target range와 undefined 통계량을 기록한다.
- [ ] train 성능과 OOF 성능 차이로 overfitting을 감사한다.
- [ ] primary family의 multiplicity 보정과 미보정 결과를 모두 저장한다.

필수 산출물:

- `concept_oof_predictions.csv`, `concept_summary.csv`
- `concept_permutation_null.csv`, `concept_bootstrap_replicates.csv`
- `concept_fold_diagnostics.csv`

P0-G6 강한 통과 조건:

- 각 모델에서 primary 정량표적 최소 하나의 OOF 연관이 grouped permutation 95백분위수를
  초과한다.
- 세 primary 표적 중 최소 두 개가 적어도 한 모델에서 같은 기준을 통과한다.
- 신호가 train-only가 아니며 leakage와 분석 구현 오류가 없다.

조건부 통과:

- 한 모델 또는 한 표적만 통과하면 해당 model–target 조합만 후속 탐색에 허용한다.
- 표본 부족으로 CI가 넓지만 방향이 일관되면 표본 확대를 전제로 descriptive evidence로 남긴다.

실패 시:

- 두 모델의 모든 primary 표적이 permutation과 구분되지 않으면 대규모 concept benchmark를
  중단하고 계측 reliability, FOV, 표본 수와 probe 적합성을 재검토한다.

통과 후 열리는 단계: P0-M7–M8와 본 연구 FM4의 승인 후보.

### P0-M7. 표현·scale·sampling·discordance 감사

목적: 유효 신호와 기술 민감성, 공통 신호와 모델특이 신호를 분리한다.

진입 조건: P0-G5 통과 및 P0-M6 완료.

To-do:

- [ ] CKA 또는 pairwise representational similarity를 동일 표본에서 계산한다.
- [ ] component-wise correlation은 embedding 차원이 다르므로 사용하지 않는다.
- [ ] shared/native FOV, scale과 tile budget sensitivity를 비교한다.
- [ ] sampling draw를 공유한 paired contrast를 계산한다.
- [ ] stain, blur, tissue fraction, scanner와 specimen metadata별 민감성을 기술한다.
- [ ] 모델별 residual과 A/B discordant tile manifest를 만든다.
- [ ] discordance가 QC나 exclusion 패턴으로 설명되는지 검사한다.
- [ ] label·sample·coordinate permutation에서 신호가 사라지는지 확인한다.
- [ ] 결과를 공통, 모델특이, scale-sensitive, unstable, unresolved로 분류한다.

필수 산출물:

- `representation_similarity.csv`, `scale_sampling_sensitivity.csv`
- `discordance_manifest.csv`, `robustness_report.md`

P0-G7 판정:

- **Green:** 주요 허용 scale에서 효과 방향이 유지되고 음성대조가 chance 수준이다.
- **Amber:** 한 scale, sampling 또는 encoder에 민감하지만 원인과 사용 범위를 정의할 수 있다.
- **Red:** sample/coordinate permutation에서도 신호가 남거나, QC·제외·membership 차이가
  결과를 지배하거나, paired premise가 성립하지 않는다.

실패 시:

- Amber는 model–target–FOV 범위를 축소하고 본 연구에서 confirmatory가 아닌 exploratory로 둔다.
- Red는 해당 조합을 중단하고 데이터 정합성 또는 구현 문제를 수정한 뒤 P0-M2/M4/M5로 돌아간다.

통과 후 열리는 단계: P0-M8과 본 연구 FM5의 승인 후보.

### P0-M8. 통합 Go/Conditional Go/Revise/Stop 판정

목적: 개별 통계의 선택적 해석 없이 P0 전체 근거로 다음 연구 범위를 결정한다.

진입 조건: P0-M0–M7의 필수 산출물이 모두 존재한다.

To-do:

- [ ] P0-G0–G7의 상태와 근거 파일을 한 행씩 연결한다.
- [ ] model–target–FOV별 허용 분석과 금지 분석을 표시한다.
- [ ] 미해결 deviation, 결측, undefined replicate와 기술 부채를 기록한다.
- [ ] P0 결과가 기존 연구 가설을 바꿨는지 구분하여 기록한다.
- [ ] 본 연구 FM0–FM10 unlock matrix를 작성한다.
- [ ] 연구책임자·병리·통계·ML 검토와 결정을 기록한다.

필수 산출물: `p0_gate_matrix.csv`, `main_study_unlock_matrix.csv`, `P0_REPORT.md`.

P0-G8 최종 판정:

| 판정 | 필수 조건 | 의미 |
|---|---|---|
| Go | G0–G6 통과, G7 Green 또는 원인이 명확한 Amber | 승인된 조합으로 본 연구 진행 |
| Conditional Go | 무결성 게이트 통과, G3/G6 조건부, G7 Amber | 모델·표적·FOV·주장을 좁혀 진행 |
| Revise and repeat | 수정 가능한 표본·계측·구현 문제 | 지정 milestone부터 재실행 |
| Stop | truth/ID/hash/leakage 실패 또는 두 모델의 양성대조 전부 실패 | 해당 연구 프레임 중단 |

`Go`는 방법론적 실행 가능성을 뜻하며 임상 검증, 외부 일반화 또는 biomarker 확립을
뜻하지 않는다.

통과 후 열리는 단계: P0-M9와 unlock matrix에 표시된 본 연구 단계.

### P0-M9. Clean rerun·재현성 잠금·본 연구 인계

목적: P0 판정이 수동 파일이나 일회성 메모리에 의존하지 않게 한다.

진입 조건: P0-G8에서 Go 또는 Conditional Go.

To-do:

- [ ] 하나의 auditable entry point로 P0를 clean rerun한다.
- [ ] seed, versions, model/source hashes와 execution time을 기록한다.
- [ ] 모든 표·그림을 저장된 CSV source table에서 다시 생성한다.
- [ ] 원본 source의 pre/post hash가 같은지 확인한다.
- [ ] 비결정적 필드를 제외한 산출물 hash가 재실행 간 일치하는지 확인한다.
- [ ] output hash가 자기 자신을 포함하지 않게 한다.
- [ ] 원본, WSI, embedding과 generated output이 commit 대상이 아닌지 확인한다.
- [ ] claim–evidence matrix와 deviation log를 닫거나 인계한다.
- [ ] 본 연구 protocol에 승인 model–target–FOV와 제한을 반영한다.

필수 산출물:

- `reproducibility_manifest.json`, `output_hashes.csv`
- `clean_rerun_comparison.csv`, `handoff_to_main_study.md`

P0-G9 통과 조건:

- clean rerun이 문서화된 timestamp 필드를 제외하고 재현된다.
- immutable source hash가 유지된다.
- 모든 주장과 숫자가 protocol, manifest와 source table로 추적된다.
- 본 연구의 승인 범위와 금지 범위가 명시되어 있다.

실패 시:

- 본 연구 FM3 이후의 확장 실행을 잠근 채 재현성 차이를 해결한다.

## 9. Gate 전체 요약

| Gate | 질문 | Pass | Conditional/Fail 시 조치 |
|---|---|---|---|
| P0-G0 | 결과 전에 설계가 잠겼는가? | protocol 승인·hash | 미승인 결과는 exploratory |
| P0-G1 | 표적이 독립·재현 가능한가? | 역할·단위·provenance 확정 | 강등 또는 제외 |
| P0-G2 | 표본·truth·split이 정합한가? | mismatch/leakage 0 | 수정 반복 또는 cohort 중단 |
| P0-G3 | 기존 양성대조가 작동하는가? | 모델별 ≥1 source control | 한 모델 제한 또는 전체 재감사 |
| P0-G4 | paired tile/target가 충분한가? | 동일 FOV·최소 feasibility floor | 서술형 축소 또는 중단 |
| P0-G5 | embedding이 기술적으로 유효한가? | 1:1·NaN 0·결정성 | 추출/manifest 재실행 |
| P0-G6 | 정량개념이 chance보다 복원되는가? | 모델별 ≥1, 전체 ≥2/3 target | 조합 축소 또는 benchmark 중단 |
| P0-G7 | 신호가 강건한가? | Green/해석 가능한 Amber | 범위 축소 또는 이전 단계 회귀 |
| P0-G8 | 본 연구로 갈 근거가 있는가? | Go/Conditional Go | Revise/Stop |
| P0-G9 | 결과가 재현·인계 가능한가? | clean rerun·hash·claim 추적 | FM3 이후 잠금 유지 |

## 10. 본 연구 FM0–FM10 진행 조건

P0와 본 연구는 완전히 직렬일 필요는 없다. 문서·catalog 작업은 병렬로 할 수 있지만,
대규모 추출·비교와 임상적 해석은 아래 조건 전에는 시작하지 않는다.

| 본 연구 단계 | P0와 병렬 가능한 범위 | 필수 P0 진입 조건 | 추가 진행 조건 |
|---|---|---|---|
| FM0 protocol 동결 | 가능 | P0-G0 이후 | P0-G8 결과를 반영해 최종 잠금 |
| FM1 의료 tier·analysis registry 감사 | 가능 | P0-G1 기준 사용 | 전 행 역할·독립성·parent linkage 완료 |
| FM2 paired manifest | 제한적 가능 | P0-G2와 G4 | 새 cohort도 같은 mismatch/leakage/FOV gate 통과 |
| FM3 paired extraction | 설계·smoke만 가능 | P0-G5, G8 Go/Conditional, G9 | 승인 model–target–FOV만 대규모 추출 |
| FM4 concept benchmark | 금지 | P0-G6, G8, G9 | 표본수/power와 metric family 승인 |
| FM5 cross-model 비교 | 금지 | P0-G7, G8, G9 | paired sample·scale·probe 원칙 유지 |
| FM6 지표–AI 상보성 | 금지 | P0-G8 Go/Conditional | 독립 metric, 충분한 subject/event, 외부 평가셋 |
| FM7 external transport | protocol 준비 가능 | P0-G9 | 복수 외부 site, target metadata, sentinel truth |
| FM8 residual review | interface 준비 가능 | FM5/7의 안정 residual | blinded review 승인·병리전문의 용량 |
| FM9 신규 지표 검증 | 금지 | 반복 residual 후보 | 고정 계측법, 독립 assay/outcome, 독립 cohort |
| FM10 패키지·보고 | 기반 작업 가능 | 관련 단계의 gate 통과 | clean rerun과 claim–evidence audit |

### 본 연구 진입의 절대 중단 조건

다음 중 하나라도 해결되지 않으면 해당 분석축은 다음 milestone로 이동하지 않는다.

- 공통 표본의 truth mismatch 또는 subject leakage
- model/source artifact hash 불명 또는 불변성 위반
- 모델 간 tile ID·좌표·FOV의 비대응
- primary target가 encoder output에서 파생된 순환 검증
- missing/uncertain/not-evaluable의 음성 변환
- source positive control의 두 모델 전부 실패
- sample/coordinate permutation에서도 유지되는 의심 신호
- clean rerun 실패 또는 결과 추적 불가

## 11. 역할과 승인 책임

| 역할 | 책임 | 승인 대상 |
|---|---|---|
| 연구책임자 | 질문·범위·주장·자원 결정 | G0, G8, G9 |
| 병리전문의 | 표적 의미·주석 적격성·형태 해석 | G1, G4, FM8 진입 |
| 통계 담당 | 분석 단위·분할·power·추론·다중검정 | G0, G3, G6, G8 |
| ML 담당 | frozen artifact·추출·probe·representation QC | G5, G7, G9 |
| 데이터 관리자 | ID·provenance·hash·결측·접근 통제 | G2, G4, G9 |

한 사람이 여러 역할을 맡을 수 있으나, 각 gate의 검토자와 승인 시각은 기록한다.

## 12. 예상 일정과 의존성

아래는 자원 계획용 예시이며, 날짜가 gate를 대체하지 않는다.

| 작업일 | 주 작업 | 종료 조건 |
|---|---|---|
| 1–2 | P0-M0 protocol/run config | G0 |
| 2–3 | P0-M1 metric audit | G1 |
| 2–4 | P0-M2 membership/truth audit | G2 |
| 4–5 | P0-M3 existing-output reanalysis | G3 |
| 4–6 | P0-M4 tile/target manifest | G4 |
| 6–8 | P0-M5 paired extraction/QC | G5 |
| 8–10 | P0-M6 probes/permutation | G6 |
| 10–11 | P0-M7 robustness/discordance | G7 |
| 12 | P0-M8 integrated decision | G8 |
| 13 | P0-M9 clean rerun/handoff | G9 |

G2, G4 또는 G5에서 문제가 발견되면 일정 압박과 관계없이 이전 milestone로 돌아간다.

## 13. 권장 산출물 구조

```text
projects/quantitative_foundation_model_validation/preexperiment/
├── PROTOCOL.md
├── run_config.json
├── source_inventory.csv
├── metric_eligibility.tsv
├── measurement_provenance.csv
├── common_sample_manifest.csv
├── membership_mismatch.csv
├── truth_mismatch.csv
├── leakage_audit.csv
├── exclusion_flow.csv
├── paired_tile_manifest.csv
├── quantitative_targets.csv
├── fold_assignments.csv
├── paired_embedding_manifest.csv
├── embedding_qc.csv
├── concept_oof_predictions.csv
├── concept_summary.csv
├── concept_permutation_null.csv
├── concept_bootstrap_replicates.csv
├── representation_similarity.csv
├── scale_sampling_sensitivity.csv
├── discordance_manifest.csv
├── p0_gate_matrix.csv
├── main_study_unlock_matrix.csv
├── deviation_log.csv
├── claim_evidence_matrix.csv
├── P0_REPORT.md
├── reproducibility_manifest.json
└── output_hashes.csv
```

WSI, 원본 dataset, embedding, model weights와 생성 분석 산출물은 로컬 보존 대상으로
취급하고 저장소에 commit하지 않는다. 코드·문서·빈 schema 또는 적절히 비식별화된 작은
예시는 프로젝트 정책에 따라 별도로 관리한다.

## 14. P0 완료 체크리스트

- [ ] P0-G0–G9 각각의 상태·승인자·근거 파일이 기록됐다.
- [ ] NADT와 PANDA 공통 membership/truth가 재검증됐다.
- [ ] 모델별 전용 표본과 모든 제외 사유가 보존됐다.
- [ ] primary 표적이 encoder와 독립이고 계측 단위가 고정됐다.
- [ ] 두 모델이 동일 좌표·동일 physical FOV·동일 fold를 사용했다.
- [ ] OOF prediction, grouped permutation과 subject-cluster bootstrap이 저장됐다.
- [ ] 반복 fold/cell/tile 수를 독립 환자 수로 보고하지 않았다.
- [ ] scale·sampling·QC·negative-control sensitivity가 완료됐다.
- [ ] Go/Conditional Go/Revise/Stop 결정과 허용 범위가 기록됐다.
- [ ] clean rerun과 source pre/post hash 검사가 통과했다.
- [ ] PRECISE의 주장이 candidate triage 및 선택 표본 범위를 넘지 않는다.
- [ ] 본 연구 FM0–FM10의 잠금/해제 상태가 인계됐다.

## 15. 즉시 착수 순서

1. P0-M0에서 이 계획의 primary 표적과 최소 feasibility floor를 연구팀이 승인한다.
2. P0-M1과 P0-M2를 병렬 수행해 독립 표적과 공통 표본을 잠근다.
3. 새 embedding을 만들기 전에 P0-M3로 기존 결과의 양성대조를 확인한다.
4. P0-M4에서 PRECISE의 실제 사용 가능한 pixel-level tile과 표적 수를 확정한다.
5. P0-G4 통과 범위에 한해 paired embedding smoke run 후 P0-M5를 완료한다.
6. P0-M6–M7에서 concept recoverability와 기술 민감성을 함께 평가한다.
7. P0-G8 합의와 P0-G9 clean rerun 이후에만 본 연구 FM3 이후를 확장한다.

## 16. 관련 문서

- 새 세션 실행 프롬프트: `docs/16_FOUNDATION_MODEL_QUANTITATIVE_VALIDATION_PREEXPERIMENT_SESSION_PROMPT_KO.md`
- 상위 연구 프로그램: `QUANTITATIVE_AI_VALIDATION_DISEASE_DIAGNOSIS_RESEARCH_PLAN_KO.md`
- 본 연구 기반 모델 실행계획: `projects/quantitative_foundation_model_validation/docs/research_plan/14_FOUNDATION_MODEL_QUANTITATIVE_METRIC_VALIDATION_PLAN_KO.md`
- 정량지표 패키지: `docs/12_QUANTITATIVE_METRICS_PACKAGE_KO.md`
- PRECISE 연구 로드맵: `docs/11_PRECISE_PNI_PROJECT_PURPOSE_GOALS_MILESTONES_KO.md`
- Frozen-score 승인 설계: `projects/precise_pni_candidate_triage/docs/designs/2026-08-05-precise-pni-frozen-score-audit-design.md`
- Morphology re-review 승인 설계: `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`
