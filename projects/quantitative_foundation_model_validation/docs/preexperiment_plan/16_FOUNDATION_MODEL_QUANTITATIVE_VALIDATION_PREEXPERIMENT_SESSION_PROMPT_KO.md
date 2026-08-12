# 기반 모델 정량지표 검증 사전실험용 새 세션 프롬프트

아래 프롬프트를 새 Codex 세션의 첫 메시지로 그대로 사용한다.

---

## 복사용 프롬프트

당신은 `/home/jinhyun/prj_ws/prj_jin/vlm-pathology` 저장소에서 기반 모델 정량지표
검증 사전실험(P0)을 실제로 준비하고 실행하는 연구·개발 에이전트입니다.

목표는 frozen CONCH와 frozen Virchow가 **동일 표본·동일 좌표·동일 물리적 FOV**에서
독립적으로 계측된 정량 병리개념을 얼마나 복원하는지 비교하고, 그 차이가 encoder,
scale, sampling, 표본 membership, 데이터 품질 또는 누출 때문인지 분리하는 것입니다.
사전실험의 성공은 임상 정확성이나 모델 우월성의 확정이 아니라, 본 연구 FM0–FM10을
진행할 수 있는 방법론적 타당성과 허용 범위를 결정하는 것입니다.

### 1. 시작 전에 반드시 읽을 문서

다음 파일을 **처음부터 끝까지** 읽고 서로의 우선순위와 제한을 확인하십시오.

1. `AGENTS.md`
2. `docs/15_FOUNDATION_MODEL_QUANTITATIVE_VALIDATION_PREEXPERIMENT_PLAN_KO.md`
3. `projects/quantitative_foundation_model_validation/docs/research_plan/14_FOUNDATION_MODEL_QUANTITATIVE_METRIC_VALIDATION_PLAN_KO.md`
4. `QUANTITATIVE_AI_VALIDATION_DISEASE_DIAGNOSIS_RESEARCH_PLAN_KO.md`
5. `docs/12_QUANTITATIVE_METRICS_PACKAGE_KO.md`
6. `infrastructure/packages/vlm_pathology_metrics/SURVEY_KO.md`
7. `projects/precise_pni_candidate_triage/docs/designs/2026-08-05-precise-pni-frozen-score-audit-design.md`
8. `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`

승인된 frozen-score audit와 morphology re-review 설계를 임의로 변경하지 마십시오.
문서 사이에 충돌이 있으면 `AGENTS.md`와 승인 설계를 우선하고, 충돌 내용을 명시적으로
보고하십시오.

### 2. 반드시 지켜야 할 과학적·데이터 경계

- 현재 PRECISE AI의 검증된 역할은 whole-slide PNI 진단이 아니라, 공간적으로 구별된
  후보 영역을 병리전문의 검토 순서로 정렬하는 candidate triage입니다.
- `resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv`는 불변의 최종 임상의 source입니다.
  절대 수정하지 말고 SHA256
  `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`를 확인하십시오.
- missing, blank, uncertain, not-evaluable 또는 unreviewed candidate를 `no`나 negative로
  변환하지 마십시오.
- frozen audit의 score, prompt, exemplar, weights, 좌표, window와 NMS를 재학습,
  재보정, 최적화 또는 변경하지 마십시오.
- PRECISE 14개 nerve-positive focus를 독립 cohort, 모집단 형태분포 또는 whole-slide
  sensitivity 추정에 사용하지 마십시오.
- 미승인 contour에서 nerve geometry를 확정값으로 계산하지 마십시오.
- 반복 seed, fold, stability cell 또는 tile을 독립 환자처럼 세지 마십시오.
- AI output에서 직접 파생된 값을 그 AI의 독립 biological ground truth로 사용하지 마십시오.
- 원본 데이터, WSI, embedding, model weights와 generated audit output은 commit하지 마십시오.
- 기존 작업트리의 사용자 변경을 보존하고, 명시적 허가 없이 commit, push 또는 remote
  설정을 하지 마십시오.

### 3. 실행 방식

사전실험은 `P0-M0`부터 `P0-M9`까지 순서대로 수행하십시오. 각 milestone에서 다음을
반드시 남기십시오.

1. 진입 조건 충족 여부
2. 수행한 태스크와 미완료 To-do
3. 입력과 출력 경로
4. source/model/config hash
5. 데이터 무결성·누출·결측 문제
6. 정량 결과와 불확실성
7. `Pass`, `Conditional Pass`, `Revise`, `Stop` 중 판정
8. 판정의 직접 근거가 되는 파일
9. 다음에 잠금 해제되는 milestone과 여전히 금지되는 분석

시간이 지났거나 코드가 실행됐다는 이유만으로 다음 단계로 넘어가지 마십시오.
`docs/15_...PREEXPERIMENT_PLAN_KO.md`의 P0-G0–P0-G9 기준을 실제 진행 기준으로
사용하십시오.

게이트 운용 원칙은 다음과 같습니다.

- `Pass`: 다음 milestone 진행
- `Conditional Pass`: 승인된 model–target–FOV와 주장 범위만 좁혀서 진행
- `Revise`: 문제의 원인이 시작된 milestone로 돌아가 재실행
- `Stop`: 해당 cohort, endpoint 또는 분석축을 중단하고 결과를 보존

truth mismatch, subject leakage, source/hash 불변성 위반, paired 좌표/FOV 실패,
순환 target 또는 두 모델의 source positive control 전면 실패는 자동 통과시킬 수 없습니다.

### 4. 이번 새 세션의 첫 번째 작업

먼저 P0-M0–P0-M3의 실행 가능성을 확정하십시오. 즉시 GPU 대규모 추출부터 시작하지
말고, 기존 산출물과 데이터 구조를 최대한 재사용하십시오.

#### Step A. 저장소와 입력 inventory

- `git status --short`로 기존 변경을 확인하고 관련 없는 변경을 건드리지 마십시오.
- `rg --files`를 우선 사용해 관련 코드, 결과 CSV, manifest, model metadata와 dataset
  경로를 찾으십시오. `rg`가 없으면 `find` 등으로 대체하십시오.
- 기존 실행 entry point와 테스트를 파악하십시오.
- `.venv/bin/python`과 현재 package/version 상태를 기록하십시오.
- model artifact의 실제 경로, revision, preprocessing, embedding 차원, tile 크기,
  MPP/FOV와 hash를 확인하십시오. 문서의 수치를 사실로 가정하지 마십시오.
- 예상 inventory와 실제 inventory의 차이를 `deviation_log.csv`에 기록하십시오.

현재 알려진 값은 검증 대상인 **예상 snapshot**이며 확정값이 아닙니다.

- NADT CONCH–Virchow 공통 환자: 예상 39명
- PANDA: CONCH 1,137행, Virchow 1,169행, 공통 image ID 예상 1,123개
- PANDA CONCH-only 예상 14개, Virchow-only 예상 46개
- 기존 stability 설계/result 예상 360 cells, fold 결과 예상 1,800행
- stability tile-coordinate manifest 예상 60행

모든 수를 원본 파일에서 다시 계산하고, ID와 truth mismatch를 별도로 검증하십시오.
PANDA는 subject 연결이 검증되기 전까지 분석 단위를 patient라고 부르지 마십시오.

#### Step B. P0 작업 디렉터리와 protocol 산출물

다음 로컬 작업 구조를 준비하십시오.

`projects/quantitative_foundation_model_validation/preexperiment/`

최소한 다음 파일의 초안 또는 schema를 만드십시오.

- `PROTOCOL.md`
- `run_config.json`
- `source_inventory.csv`
- `metric_eligibility.tsv`
- `measurement_provenance.csv`
- `common_sample_manifest.csv`
- `membership_mismatch.csv`
- `truth_mismatch.csv`
- `leakage_audit.csv`
- `exclusion_flow.csv`
- `claim_evidence_matrix.csv`
- `deviation_log.csv`
- `p0_gate_matrix.csv`
- `main_study_unlock_matrix.csv`

실데이터가 아직 없는 표는 빈 파일만 만드는 대신, 필수 열 정의와 생성 주체를
`PROTOCOL.md` 또는 schema 문서에 명시하십시오. generated output과 대용량 파일이 Git에
포함되지 않도록 기존 ignore 정책을 먼저 확인하십시오.

#### Step C. P0-M0 protocol lock 제안

결과 분석 전에 다음을 확정할 수 있는 decision sheet를 작성하십시오.

- primary, secondary, exploratory question
- primary target와 measurement provenance
- analysis unit과 grouping unit
- CONCH/Virchow model ID와 preprocessing
- shared/native FOV 정의
- subject-grouped fold 생성 방식과 seed
- 동일한 low-capacity probe family와 tuning budget
- 연속 표적 평가량: 최소 MAE, R², Spearman correlation
- subject/case-grouped label permutation
- subject-cluster paired bootstrap
- multiplicity family와 처리 방식
- inclusion/exclusion/missing 규칙
- 허용 주장과 금지 주장
- P0-G0–P0-G9 판정 책임과 증거 파일

P0-G0는 연구책임자의 protocol 승인이 필요한 정지점입니다. 이 프롬프트는 작업 시작
권한이지만, 결과를 본 뒤 protocol을 바꾸는 권한은 아닙니다. decision sheet와 잠글
항목을 제시한 뒤 내 승인을 요청하십시오. 다만 승인 대기 중에도 원본을 변경하지 않는
read-only inventory, schema 작성과 무결성 점검은 계속할 수 있습니다.

#### Step D. P0-M1 metric eligibility

우선 다음 PRECISE 정량 표적의 적격성을 감사하십시오.

1. `tumor fraction`: 전문가 tumor mask 기반인 경우 1차 후보
2. `nuclear density/mm²`: 독립·고정 nuclei detector와 검증 subset이 있어야 1차 후보
3. `gland/lumen fraction`: 전문가 주석 또는 독립·검증 segmentation이 있어야 1차 후보
4. `stroma fraction`, H&E texture: 2차 후보
5. `tissue/valid-pixel fraction`: QC 전용

각 지표에 `metric_role`, `analysis_unit`, `reference_source`,
`independence_from_model`, `measurement_status`, `allowed_role`, 단위, 분모,
repeatability, 결측 사유를 부여하십시오. 독립성 또는 repeatability가 불충분하면 primary로
올리지 말고 secondary, descriptive, deferred 또는 excluded로 분류하십시오.

#### Step E. P0-M2 membership·truth·leakage audit

- NADT와 PANDA의 CONCH/Virchow ID 교집합·차집합을 다시 계산하십시오.
- 공통 표본의 label/truth mismatch를 검사하십시오.
- 모델별 전용 표본을 삭제하지 말고 제외 사유와 함께 보존하십시오.
- duplicate subject/slide, serial section과 split leakage를 검사하십시오.
- 공통 표본을 고정한 후 manifest와 hash를 저장하십시오.
- mismatch 또는 leakage가 있으면 원인을 해결하기 전 predictive 분석으로 이동하지 마십시오.

#### Step F. P0-M3 기존 결과 양성대조

새 embedding 대규모 추출 전에 다음을 공통 표본 기준으로 재분석하십시오.

- NADT Gleason과 phenotype: source positive control
- PTEN: 상대적 안정 대조
- SPOP: 불안정 대조
- recurrence: encoder/scale 의존 대조
- AR: 약한 연속 대조

두 모델에 동일한 계산·불확실성·permutation 방식을 적용하십시오. 기존 360 cell과
1,800 fold를 독립 표본으로 취급하지 마십시오. 각 모델에서 사전 지정 source positive
control 최소 하나가 subject/case-grouped permutation의 95백분위수를 넘는지 확인하십시오.
한 모델만 통과하면 Conditional Pass이며, 두 모델 모두 실패하면 대규모 추출을 중단하고
label, split, preprocessing과 평가 구현을 재감사하십시오.

### 5. P0-M4 이후 실행 규칙

P0-G0–G3이 통과한 뒤에만 P0-M4 이후로 진행하십시오.

- P0-M4: 모든 적격 pixel-level 전문가 주석 tile로 paired tile/target manifest 동결
- P0-M5: 동일 중심·동일 physical FOV에서 frozen CONCH/Virchow embedding 및 기술 QC
- P0-M6: 동일 subject-grouped folds와 probe budget으로 정량개념 OOF 복원·permutation
- P0-M7: CKA/representation, scale, FOV, sampling, QC와 discordance 감사
- P0-M8: Go/Conditional Go/Revise/Stop 및 FM0–FM10 unlock matrix 결정
- P0-M9: clean rerun, source pre/post hash, output hash와 본 연구 인계

P0-M4의 최소 20명/primary target 및 fold당 4명은 feasibility floor일 뿐 power 근거가
아닙니다. 미달하면 기술·서술형 결과로만 제한하십시오. 동일 tile/FOV 또는 독립 target을
확보하지 못하면 Frame D를 중단하십시오.

P0-G8의 `Go`도 임상 검증을 뜻하지 않습니다. FM6에는 충분한 subject/event와 외부
평가셋, FM7에는 외부 site metadata와 sentinel truth, FM8에는 안정 residual과 blinded
병리 검토 승인, FM9에는 독립 assay/outcome/cohort가 별도로 필요합니다.

### 6. 구현과 재현성 요구사항

- 분석별로 가능하면 하나의 auditable entry-point script를 사용하십시오.
- 고정 seed를 사용하고 run configuration에 기록하십시오.
- 입력 hash, 모델 hash, software version, 시작·종료 시각과 non-self-referential output
  hash를 기록하십시오.
- 모든 표와 그림은 저장된 CSV source table에서 생성하십시오.
- clean rerun은 명시된 timestamp를 제외하고 동일해야 합니다.
- undefined bootstrap/permutation replicate를 삭제하지 말고 수와 비율을 보고하십시오.
- Python은 기존 `.venv/bin/python`을 사용하십시오.
- 수정한 Python은 `.venv/bin/python -m py_compile`로 검사하고, 관련 테스트를 신선하게
  실행하십시오.
- frozen-score audit 관련 코드를 변경했다면 최소한 다음 테스트를 실행하십시오.

  `.venv/bin/python -m unittest tests.test_precise_pni_frozen_score_audit -v`

- 데이터나 기존 결과의 의미를 조용히 수리하지 말고 integrity issue로 보고하십시오.

### 7. 사용자에게 보고하는 방식

작업 중 60초 이상 침묵하지 말고 다음을 짧게 업데이트하십시오.

- 현재 milestone과 gate
- 방금 확인한 중요한 수치 또는 문제
- 생성·수정한 파일
- 다음 판정까지 남은 작업

각 milestone 종료 보고는 다음 형식을 사용하십시오.

```text
Milestone:
판정: Pass / Conditional Pass / Revise / Stop
근거:
- 표본/분석 단위:
- 핵심 무결성 결과:
- 핵심 정량 결과와 불확실성:
- 근거 파일:
미해결 위험:
다음에 열리는 단계:
여전히 금지되는 분석:
```

과학적 결론은 관찰 사실, 통계적 추론, 연구자의 해석과 가설을 구분해 쓰십시오.
기존 결과와 다른 결과가 나오면 새 결과를 숨기거나 protocol을 사후 변경하지 말고,
재현 가능한 mismatch report와 가능한 원인을 제시하십시오.

### 8. 첫 응답에서 해야 할 일

먼저 작업 계획만 반복하지 말고 실제 read-only inventory를 시작하십시오. 첫 번째 의미
있는 업데이트 또는 산출물에는 다음이 포함되어야 합니다.

1. 읽은 필수 문서와 적용되는 제한 요약
2. 현재 git/workspace 상태와 관련 파일 inventory
3. 예상 snapshot 수치의 재검증 결과 또는 검증 명령
4. P0-M0–M3의 구체적 실행 순서와 현재 blocker
5. P0-G0 승인을 위해 내가 결정해야 할 최소 항목

추가 지시가 없어도 안전하고 비파괴적인 범위에서 계속 진행하십시오. 다만 P0-G0의
연구책임자 승인, 해결되지 않은 truth/leakage/hash 문제, 분석 범위를 바꾸는 결정 또는
원본·외부 시스템에 영향을 주는 작업은 임의로 승인하지 말고 명확히 보고하십시오.

---

## 사용 메모

- 새 세션의 작업 디렉터리가 저장소 루트인지 확인한 후 위 프롬프트를 붙여 넣는다.
- P0-G0 decision sheet가 제시되면 primary target, FOV, probe, 통계와 주장 범위를 검토해
  승인 또는 수정 지시를 한다.
- 장시간 GPU 실행 전에 P0-G2–G4 결과와 예상 실행비용을 확인하는 것이 좋다.
