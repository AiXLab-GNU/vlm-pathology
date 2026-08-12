# P0 기반 모델 정량지표 검증 사전실험 protocol/decision sheet

- Protocol ID: `P0-QFMV-2026-08-11-APPROVED-001`
- 상태: **Approved — P0-G0 Pass**
- 작성 기준일: 2026-08-11
- 승인자: Jin Hyun Kim
- 역할: PM
- 승인시각(UTC): 2026-08-11T19:17:36Z
- 대상: frozen CONCH와 frozen Virchow
- 현재 허용 실행: P0-M0--M7와 shared-394.24µm descriptive tumor 조합의 P0-M8 통합 판정
- 현재 금지 실행: confirmatory PRECISE 분석, stroma secondary claim, encoder superiority 및 임상/PNI 주장

이 문서는 결과를 본 뒤 표적·FOV·probe·통계를 바꾸기 위한 문서가 아니다. 아래
decision sheet 네 묶음은 2026-08-11에 결과 분석 전에 승인되었다. P0-M3는 기존 frozen
embedding과 고정 fold만 사용하며, PRECISE 신규 extraction은 별도 gate를 통과할 때까지
실행하지 않는다.

## 1. 지침 우선순위와 적용 경계

다음 문서를 처음부터 끝까지 확인했다.

1. `AGENTS.md`
2. `docs/15_FOUNDATION_MODEL_QUANTITATIVE_VALIDATION_PREEXPERIMENT_PLAN_KO.md`
3. `projects/quantitative_foundation_model_validation/docs/research_plan/14_FOUNDATION_MODEL_QUANTITATIVE_METRIC_VALIDATION_PLAN_KO.md`
4. `QUANTITATIVE_AI_VALIDATION_DISEASE_DIAGNOSIS_RESEARCH_PLAN_KO.md`
5. `docs/12_QUANTITATIVE_METRICS_PACKAGE_KO.md`
6. `infrastructure/packages/vlm_pathology_metrics/SURVEY_KO.md`
7. `projects/precise_pni_candidate_triage/docs/designs/2026-08-05-precise-pni-frozen-score-audit-design.md`
8. `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`

적용 우선순위는 사용자 요청, `AGENTS.md`, 승인 설계, P0 계획, 본 연구 계획 순이다.
상위 본 연구 계획에는 gland/lumen, nuclear, nerve geometry 등 폭넓은 후보가 있으나,
P0 계획은 독립성과 repeatability가 입증되지 않은 지표를 primary로 올리지 못하게 한다.
따라서 현재 로컬 evidence가 없는 nuclei와 gland/lumen은 `deferred`다. 승인된 PNI
frozen-score audit와 14-focus morphology re-review는 별도 연구이며 본 P0가 score,
prompt, exemplar, weights, 좌표, NMS, label 또는 contour를 변경하지 않는다.

현재 PRECISE AI의 허용 역할은 공간적으로 구별된 후보의 pathologist review 순서를
정하는 candidate triage다. Whole-slide PNI 진단, sensitivity, prevalence, 고정 임상
budget 또는 임상 검증을 주장하지 않는다. 14개 선택 focus는 형태분포, 예후 또는
외부검증 코호트가 아니다. 미승인 contour에서 nerve geometry를 계산하지 않는다.

## 2. 관찰된 inventory snapshot

아래 값은 `run_preexperiment.py --stage pre-g0`가 원본과 cache에서 다시 계산한다.

| 항목 | 재검증 값 | 현재 해석 |
|---|---:|---|
| NADT Gleason 공통 | 334 slides, 39 subjects | 모델 membership·subject·truth 완전 일치 |
| NADT phenotype 공통 | 463 slides, 39 subjects | TUMOR/BENIGN만 포함; 다른 phenotype은 음성 변환 없이 제외 |
| PANDA CONCH | 1,137 unique images | image/case 단위 |
| PANDA Virchow | 1,169 unique images | image/case 단위 |
| PANDA 공통 | 1,123 unique images | source truth mismatch 0 |
| PANDA CONCH-only / Virchow-only | 14 / 46 | 삭제하지 않고 mismatch table에 보존 |
| PANDA neither-model | 17 | 결정적 1,200-image sampling universe에는 있으나 양쪽 cache에서 제외 |
| PANDA 공통 tile-count mismatch | 525 / 1,123 | paired-coordinate/FOV evidence로 사용 금지 |
| TCGA-PRAD 공통 | 300 slides, 273 cases | PTEN/SPOP/AR membership·case·truth 완전 일치 |
| LEOPARD recurrence 공통 | 508 cases, 87 events | 두 historical OOF file의 event/time 완전 일치 |
| Stability design/result | 360 / 360 cells | raw status complete, reconciliation complete |
| Stability fold results | 1,800 rows | 독립 표본이 아니라 반복 fold 결과 |
| Stability coordinate manifest | 60 rows | 60 독립 환자가 아니라 runner–seed–MPP manifest |

PANDA source에는 verified subject linkage가 없으므로 `patient`라는 분석 단위를 쓰지
않는다. 기존 PANDA cache에는 좌표가 없고 공통 표본에서도 tile 수가 다르므로, 공통
image ID는 동일 ROI·동일 sampling·동일 physical FOV를 의미하지 않는다.

## 3. P0 연구질문 lock 제안

### Primary

> 동일 PRECISE subject, tile center와 394.24-µm square FOV에서 frozen CONCH와
> frozen Virchow embedding이 독립 provided expert-mask 기반 tumor fraction을
> subject-grouped OOF 방식으로 chance보다 잘 복원하는가?

공식 PRECISE v1 record에서 두 expert uropathologist의 three-stage consensus와 IHC 기반
boundary definition은 확인됐다. 정량 repeatability 계수가 없으므로 tumor fraction은
confirmatory primary가 아니라 descriptive feasibility target으로 제한한다.

### Secondary

- 같은 조건에서 stroma fraction의 recoverability. Mask provenance 확인을 전제로 한다.
- 고정 preprocessing 후 H&E texture entropy/homogeneity의 탐색적 recoverability.
- 승인된 primary/secondary target에서 CONCH–Virchow paired delta와 native-FOV
  sensitivity. Encoder 우열의 일반화가 아니라 승인 조합 내 차이만 기술한다.
- P0-M3의 NADT Gleason/phenotype source positive controls, PTEN relative-stable
  control, SPOP unstable control, recurrence encoder/scale-dependent control, AR weak
  continuous control.

### Exploratory / deferred

- CKA/representation similarity와 discordance는 P0-G5/G6 이후 exploratory다.
- Nuclear density/mm²는 fixed independent detector와 manual/approved validation이 없어
  `deferred`다.
- Gland/lumen fraction은 expert lumen contour 또는 validated independent segmentation이
  없어 `deferred`다. PRECISE의 `Benign gland` tissue class를 lumen contour로 바꾸지 않는다.
- Nerve geometry는 locked morphology label과 approved contour 전까지 `deferred`다.

## 4. Primary target와 measurement definition 제안

### P0-G1 provenance 확인 기록 (P0-M4 실행 전)

- PRECISE Zenodo v1(`10.5281/zenodo.20721779`, published 2026-06-16)은 pixel-level
  annotation이 두 expert uropathologist의 structured three-stage consensus로 검증됐고,
  IHC가 boundary definition의 biological ground truth였다고 명시한다.
- 공개 record는 24,387 annotations와 tumor, benign gland, stroma, IDC-P, HGPIN, AIP,
  artifact class를 명시한다.
- 공개 GitHub utility는 미표지 tissue를 threshold/blur/dilation/erosion으로 찾아 class 7
  stroma를 보완하는 `add_stroma.py`를 명시한다. 따라서 stroma는 순수 수기 consensus
  표적으로 간주하지 않는다.
- 정량적 interobserver agreement 또는 repeatability coefficient는 공개 자료에서 확인되지
  않았다. Tumor fraction은 독립성과 consensus QA는 충족하지만 confirmatory repeatability는
  미충족이므로 **descriptive feasibility primary candidate**로만 사용한다. Stroma fraction은
  algorithm-assisted exploratory target으로 제한한다.

근거: https://zenodo.org/records/20721779 및
https://github.com/abelBEDOYA/PRECISE-data-utils. 이 판정은 P0-M4 target 결과를 계산하기
전에 기록했다.

### Tumor fraction

- Reference: PRECISE H&E pixel mask의 label `1`.
- Analysis unit: paired tile.
- Grouping/inference unit: subject. Session/slide/tile은 subject 안에 유지한다.
- Unit: `[0,1]` fraction.
- Numerator: fixed tile 안의 label `1` pixel 수.
- Proposed denominator: labels `{1,2,4,5,6,7}`의 pixel 수.
- Background `0`과 artifact `3`은 biological denominator에서 제외한다.
- Denominator가 0이면 missing/QC failure이며 0 또는 negative로 바꾸지 않는다.
- Mask와 H&E 좌표·shape 정합, label range, tissue denominator, missing reason을 M4에서
  tile별로 저장한다.

이 정의는 승인 전 제안이다. Artifact를 denominator에 포함하거나 valid-tissue 정의를
바꾸려면 결과 확인 전 G0에서 결정해야 한다.

## 5. 모델과 preprocessing lock 제안

### CONCH

- Model: `conch_ViT-B-16`, `MahmoodLab/conch`
- Hugging Face revision: `f9ca9f877171a28ade80228fb195ac5d79003357`
- Weight SHA256: `40a9644b9ba0e83a74576e0a5e5f7313599fa9c9cdaf3c20f8a3e271b0e9ae7c`
- Embedding: raw image embedding, 512 dimensions
- Input: 448×448 px; bicubic resize, center crop
- Normalize mean: `(0.48145466, 0.4578275, 0.40821073)`
- Normalize SD: `(0.26862954, 0.26130258, 0.27577711)`

### Virchow

- Model: `hf-hub:paige-ai/Virchow`
- Hugging Face revision: `19eebc84ae33e79f1b2d866e6ff90ae50e522f9a`
- Weight SHA256: `3416891b37a2349a2d9ce7ecf00b64a6277011b41351436c1ceb0abb80805408`
- Embedding: CLS token과 mean patch token 결합, 2,560 dimensions
- Input: 224×224 px; bicubic resize, center crop, crop_pct=1.0
- Normalize mean: `(0.485, 0.456, 0.406)`
- Normalize SD: `(0.229, 0.224, 0.225)`

모델은 frozen 상태다. Prompt, exemplar, score, threshold, calibration 또는 model weight를
P0에서 변경하지 않는다.

## 6. FOV와 좌표 lock 제안

### Primary shared FOV

- 동일 tile center에서 **394.24 µm × 394.24 µm** square tissue extent를 추출한다.
- WSI native MPP로 physical crop boundary를 계산하고, 같은 boundary를 두 모델 입력으로
  각각 resize한다.
- CONCH는 448×448 입력, Virchow는 224×224 입력을 유지한다.
- 좌표 rounding, edge padding/exclusion, interpolation과 mask resampling은 M4 전에 고정한다.
- Mask에는 nearest-neighbor만 사용하고 H&E에는 bicubic model preprocessing을 사용한다.

이 크기는 historical CONCH 448 px × 0.88 µm/px와 일치한다. 같은 FOV를 Virchow에
입력하면 effective content scale은 약 1.76 µm/input-pixel이 된다.

### Native-FOV sensitivity

- CONCH native historical FOV: 448 × 0.88 = 394.24 µm.
- Virchow native historical FOV: 224 × 0.44 = 98.56 µm.
- Native 결과는 primary shared-FOV 결과와 분리하며, physical content가 다르므로
  encoder effect와 scale effect를 분리하지 못하는 sensitivity로만 해석한다.

기존 stability의 `target_mpp=1.76`은 두 encoder에서 같은 physical FOV가 아니다:
CONCH는 788.48 µm, Virchow는 394.24 µm다. 따라서 기존 stability 결과는 P0-M3
control과 기술 민감성 근거로 재사용할 수 있지만 same-FOV encoder 우열 근거가 아니다.

### P0-M4 technical manifest lock

- Level-0 image origin `(0,0)`에 고정한 non-overlapping square grid를 사용한다.
- Level-0 crop pixel 수는 `round(394.24 / OME PhysicalSizeX)`이며 edge partial tile은
  padding하지 않고 제외한다. 두 모델은 이후 이 동일 level-0 boundary와 center를 사용한다.
- Target inventory는 mask pyramid level 3에서 해당 physical boundary를 floor/ceil mapping해
  계산한다. Mask interpolation이나 label 변환을 새로 수행하지 않는다.
- Primary technical eligibility는 valid biological mask fraction `>=0.50`, artifact fraction
  `<=0.05`, full boundary, valid denominator `>0`, locked 14 PNI focus와 overlap 없음이다.
- H&E QC는 pyramid level 4의 동일 physical boundary에서 brightness, grayscale SD,
  Laplacian variance, saturation, dark/fold 및 blue/green pen heuristic을 기록한다. 이 단계에서
  H&E QC 값으로 tile을 제외하지 않아 outcome-informed threshold를 만들지 않는다.
- Tumor fraction은 label 1 / labels `{1,2,4,5,6,7}`이다. Stroma fraction은 같은 분모의
  label 7이지만 exploratory다. Zero denominator는 missing으로 보존한다.
- Subject는 seed `20260811`로 한 번 shuffle한 뒤 round-robin 5-fold로 배정한다.

### P0-M5 technical extraction lock

- P0-M4의 `eligible_descriptive_tumor` 1,218개 tile과 그 row order를 그대로 사용한다.
- 각 level-0 TIFF에서 locked rectangle과 겹치는 encoded 512-px tile만 decode하고, 완전한
  RGB crop coverage 및 crop-byte SHA256을 기록한다. 두 encoder의 crop hash가 같아야 한다.
- CONCH는 local revision `f9ca...` weight에서 448×448 preprocessing 후
  `encode_image(proj_contrast=False, normalize=False)` 512차원 raw embedding을 저장한다.
- Virchow는 local revision `19e...` weight에서 224×224 bicubic/center preprocessing 후
  CLS token과 mean patch token을 결합한 2,560차원 raw embedding을 저장한다.
- Float32, autocast 없음, TF32 비활성, deterministic algorithm 활성화, encoder별 batch 8로
  고정한다. 결과나 속도에 따라 batch/preprocessing을 바꾸지 않는다.
- Seed `20260816`으로 사전 선택한 8개 tile을 같은 batch로 두 번 추론해 feature hash,
  exact equality와 max absolute difference를 저장한다.
- G5는 row/dimension/dtype, 모든 finite/nonzero norm, ID/order pairing, 두 encoder crop hash,
  8-tile exact repeat, WSI/model-weight pre/post hash가 모두 통과해야 Pass다.
- G5 Pass는 descriptive tumor target의 P0-M6 OOF/permutation만 연다. Recoverability,
  encoder superiority, confirmatory target 또는 clinical/PNI 주장은 아직 허용하지 않는다.

### P0-M6 descriptive concept-inference lock

- P0-M5의 1,218개 paired row와 M4의 tumor fraction/fold를 ID와 row order로 재조정 없이
  사용한다. 두 encoder는 동일 25-subject, 5-fold assignment를 공유한다.
- Encoder별 `StandardScaler + Ridge(solver=lsqr)`를 사용한다. 각 outer fold 안에서 나머지
  네 고정 fold를 inner validation으로 한 nested selection을 수행하며 alpha grid는
  `10^-4 ... 10^4`의 17개 값이다. Feature selection, PCA, nonlinear head, fine-tuning은 없다.
- 모든 tile OOF prediction과 fold별 선택 alpha를 저장한다. Tile MAE/R²/Spearman과
  subject-mean MAE/R²/Spearman을 함께 저장하되 primary gate statistic은 25 subject의
  mean OOF prediction과 mean tumor fraction 사이 Spearman이다.
- Primary negative control은 saved OOF에 조건부인 2,000회 subject-mean label permutation
  (`seed=20260811+replicate`)이다. Probe를 null replicate마다 재적합하지 않는다.
- 공간 대응 음성대조로 각 subject 안에서 prediction–coordinate 대응을 독립적으로 섞은
  2,000회 tile-coordinate permutation을 별도 저장한다. 이는 primary gate가 아니다.
- 불확실성은 같은 resampled subject를 두 encoder에 적용한 2,000회 subject-cluster paired
  bootstrap(`seed=20260812+replicate`)이다. Undefined replicate와 사유를 모두 보존한다.
- 두 model×tumor primary association의 empirical p에 BH-FDR을 적용하고 raw p와 q를 모두
  저장한다. G6 조합 통과는 observed subject-mean Spearman이 해당 grouped-permutation p95를
  초과하는지로 판정하며 q는 함께 보고한다.
- 독립적으로 허용된 target이 tumor fraction 하나뿐이므로 원 계획의 3-target strong-pass는
  구조적으로 불가능하다. 한 모델 이상 통과해도 G6는 최대 **Conditional Pass**이고 통과한
  model–tumor–394.24µm 조합만 P0-M7에 허용한다. 둘 다 실패하면 Stop/Revise다.
- Tumor target의 median=0 zero-inflation, train–OOF gap, fold별 target range와 방향성을
  명시한다. 이 단계에서 two-part model이나 target transformation을 사후 도입하지 않는다.

### P0-M7 robustness/sensitivity lock

- Shared primary는 기존 394.24µm OOF를 변경 없이 사용한다. Virchow native sensitivity는
  동일 tile center에서 `round(98.56/native MPP)` level-0 crop을 decode하고 224×224로
  preprocessing한 새 2,560차원 embedding이다. Outcome은 shared 394.24µm tumor fraction을
  유지하므로 이는 **input-context scale sensitivity**이며 native-window target 검증이 아니다.
- Virchow native extraction은 M5와 같은 local revision, float32, TF32 off, deterministic
  algorithm과 batch 8을 사용하고 8-tile exact repeat, crop/array/source hash를 저장한다.
- Native OOF는 M6와 동일 fold, Ridge, 17-alpha nested budget을 사용한다. Virchow shared의
  CLS-only 1,280차원과 patch-mean-only 1,280차원도 같은 probe budget으로 component/capacity
  sensitivity를 기록하며 이를 CONCH와의 공정한 dimension-matched 비교로 해석하지 않는다.
- Sampling sensitivity는 subject별 tile ID를 결과와 독립인 seed로 공유 추출한다. Budget
  `{4,8,16,32}`에서 20 draw와 all-tile을 사용하고, 부족한 subject는 보유 tile 전부를 쓴다.
  같은 draw ID는 모든 representation에서 동일 tile을 사용한다.
- Zero-inflation sensitivity는 기존 full-universe OOF에서 `truth>0` positive-only MAE/R²/
  Spearman과 `truth>0` presence AUROC/AP를 계산한다. Threshold는 정확히 0이며 조정하지 않는다.
  Subject-cluster bootstrap 2,000회로 CI를 저장한다. Primary M6 결과를 대체하지 않는다.
- Representation similarity는 centered linear CKA와 pairwise cosine-distance RSA Spearman을
  tile 및 subject-mean 단위에서 계산한다. 서로 다른 embedding dimension의 component-wise
  correlation은 계산하지 않는다.
- QC sensitivity는 brightness, grayscale SD, Laplacian variance, saturation, valid biological
  fraction, artifact fraction과 native MPP를 결과와 무관하게 지정한다. 각 연속 QC의 전체
  `|residual|` Spearman 및 global Q1/Q4에서 OOF Spearman을 기록한다. `|rho|>=0.5`이면 large
  QC association으로 표시하며, 상·하 stratum에서 방향이 뒤집히면 dominance flag다.
- Discordance는 `|error_CONCH|-|error_Virchow|`의 사전 정의 Q10/Q90으로 각 모델-worse tile을
  표시한다. 임계값은 설명용이며 성능 threshold나 임상 threshold가 아니다.
- M6 subject-label 및 within-subject coordinate null을 재사용한다. 관찰 Spearman이 null p95를
  넘지 못하거나 pairing/hash가 깨지면 Red다. Core 방향이 유지되지만 scale/sampling/QC 또는
  metadata 한계가 있으면 Amber다. Stain batch metadata가 없고 별도 MPP scanner group이 2명뿐이라
  G7은 사전적으로 최대 **Amber**다.
- Amber는 통과한 `model–tumor–FOV`의 descriptive 범위만 M8에 전달한다. Encoder superiority,
  confirmatory target, scanner/stain robustness, clinical/PNI 주장은 허용하지 않는다.

### P0-M8 integrated decision lock

- M8은 G0–G7의 저장된 결과만 통합하며 probe, target, FOV, threshold, fold,
  permutation 또는 bootstrap을 재선택하지 않는다.
- 결정 규칙은 다음과 같이 고정한다. G0/G2/G3/G5의 integrity/technical premise가
  깨지거나 G7이 Red이면 `Revise/Stop`이다. 필수 premise가 유지되고 G1/G4/G6 중
  하나라도 Conditional이거나 G7이 Amber이면 `Conditional Go`다. 모든 필수 gate가
  Pass이고 G7이 Green일 때만 `Go`다.
- 현재 증거는 G1/G4/G6 Conditional과 G7 Amber를 포함하므로 기계적 draft는
  `Conditional Go`로 제한된다. 이는 임상 Go가 아니라 정의된 범위의 방법론적
  feasibility 제안이다.
- G8은 연구책임자의 검토와 최종 승인이 기록되기 전에는
  `draft_conditional_go_pending_research_lead_approval`로 남긴다. 병리·통계·ML/데이터
  검토는 이 독립 연구에서 필요 시 받는 비차단 자문이다. 코드는 연구책임자의 서명을
  추정·대행하거나 G8을 자동 승인하지 않는다.
- G8 승인 전에 실제 main-study extraction, benchmark, cross-model 결론을 시작하지
  않는다. 코드/schema/smoke 준비만 허용하며 G9 clean rerun 후에도 각 조건의
  상위 한계를 넘지 않는다.
- 통합 산출물은 `integrated_gate_summary.csv`, `p0_question_answer_matrix.csv`,
  `model_target_fov_decision.csv`, `unresolved_risk_register.csv`, `P0_REPORT.md`이다. 모든
  요약 수치는 기존 saved CSV에서 읽고, report는 저장된 통합 table에서 생성한다.

## 7. Split, probe, tuning budget lock 제안

- P0-M3는 `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv`의 기존 subject/case grouped fold를
  재사용한다. 새 결과에 맞춰 fold를 다시 선택하지 않는다.
- 신규 PRECISE target은 subject 목록을 seed `20260811`로 한 번만 섞은 5-fold
  subject-grouped split을 사용한다.
- 동일 subject의 모든 session, slide, ROI와 tile은 같은 fold에 둔다.
- Primary target별 적격 subject 최소 20명 및 fold당 최소 4명은 feasibility floor다.
- 두 encoder는 완전히 같은 fold assignment를 사용한다.
- P0-M3의 단일 고정 qualification configuration은 sampling seed `0`, 최초 rank 16 tiles의
  mean pool, encoder별 historical native MPP(CONCH 0.88, Virchow 0.44)다. 이 configuration은
  기존 stability의 원 설정을 재현하기 위한 source control이며 same-FOV 모델 비교가 아니다.
- Continuous target probe: `StandardScaler` + L2 Ridge.
- Binary source control probe: `StandardScaler` + L2 logistic regression.
- 두 모델에 17개의 동일 log grid `1e-4 ... 1e4`와 동일 inner grouped-CV budget을
  사용한다. Binary `C`는 ridge alpha와 역방향으로 대응한다.
- Feature selection, nonlinear head, encoder fine-tuning과 target-cohort calibration은 금지한다.
- Virchow의 더 큰 dimension은 숨기지 않고 dimension/capacity sensitivity를 P0-M7에서
  별도 기술한다.

## 8. 평가, permutation, bootstrap과 multiplicity lock 제안

### Continuous target

- 최소 평가량: MAE, out-of-fold R², Spearman correlation.
- 모든 값은 saved OOF prediction에서 재계산한다.
- Fold별 subject 수, target range, missing 및 undefined statistic을 보존한다.

### Negative control

- Subject/case 단위 label permutation 2,000회, seed `20260811`.
- 한 subject의 모든 tile/slide label 관계를 유지한다.
- P0-M3의 source positive-control gate는 관찰 통계량이 각 encoder의 grouped
  permutation 95백분위수를 초과하는지 본다.
- P0-M3 permutation은 saved frozen OOF prediction에 조건부로 수행하며 replicate 안에서
  probe를 재적합하거나 hyperparameter를 다시 고르지 않는다. Subject/case-level outcome은
  group 사이에서 permutation하고, NADT slide phenotype은 subject별 class count를 보존하도록
  subject 안에서 label을 permutation한다.
- 좌표/sample permutation은 paired tile manifest가 잠긴 뒤 가능한 범위에서 별도 수행한다.

### Uncertainty

- Subject-cluster paired bootstrap 2,000회, seed `20260812`.
- 두 encoder를 같은 resampled subjects로 비교한다.
- Undefined replicate를 삭제하지 않고 전체 행, 사유, 수와 비율을 저장한다.
- 반복 seed, fold, stability cell 또는 tile을 독립 환자로 세지 않는다.

### Multiplicity

- 승인된 primary `model × target` association을 하나의 primary family로 정의하고
  BH-FDR을 적용한다.
- Raw p/value와 adjusted q/value를 모두 보존한다.
- Secondary, robustness와 residual discovery는 별도 exploratory family다.
- P0-G3의 사전 지정 source-positive-control gate는 threshold 선택용 분석이 아니라
  pipeline qualification이며 각 encoder에서 최소 하나의 지정 control 통과 여부를 기록한다.

## 9. Inclusion, exclusion, missing 규칙

- Source ID, truth와 subject/case mapping이 양쪽 모델 및 source에서 일치해야 common
  predictive universe에 들어간다.
- 모델별 전용 표본은 삭제하지 않고 `membership_mismatch.csv`에 보존한다.
- Missing, blank, uncertain, not-evaluable과 unreviewed를 `no`, 0 또는 negative로 바꾸지 않는다.
- Truth mismatch는 해결 전 해당 cohort/endpoint의 predictive 분석을 중단한다.
- Subject linkage가 없는 PANDA는 image/case membership audit로만 유지한다.
- Duplicate slide, serial section과 paired stain은 subject grouping을 넘지 않는다.
- PRECISE 14 PNI focus와 provisional nerve circles는 Frame D primary universe에서 제외한다.
- Source/model hash가 달라지면 즉시 중단하고 원인을 보고한다.

## 10. 허용 주장과 금지 주장

허용 가능한 최상위 P0 주장은 다음과 같다.

> 승인된 PRECISE target과 physical FOV에서 frozen embedding의 정량개념 복원에 대한
> 방법론적 feasibility와 허용 model–target–FOV 범위를 평가했다.

P0만으로 다음을 주장하지 않는다.

- CONCH 또는 Virchow의 보편적 우월성
- 임상 정확성, 임상 validation 또는 diagnostic threshold
- Whole-slide PNI sensitivity, prevalence, NPV 또는 미판독 영역의 음성
- PRECISE 14 focus의 모집단 형태분포, 예후 또는 외부 일반화
- AI-derived quantity를 독립 biological ground truth로 사용한 검증
- 미승인 contour 기반 확정 nerve geometry

상세 claim–evidence 연결은 `claim_evidence_matrix.csv`가 담당한다.

## 11. 마일스톤 실행 순서와 현재 blocker

1. **P0-M0 / G0**: **Pass**. Jin Hyun Kim(PM), 2026-08-11T19:17:36Z.
2. **P0-M1 / G1**: **Conditional Pass**. Tumor fraction은 descriptive only, stroma는
   algorithm-assisted exploratory이며 nuclei와 gland/lumen은 deferred다.
3. **P0-M2 / G2**: **Conditional Pass**. NADT·TCGA-PRAD·LEOPARD의 membership/truth/
   case linkage를 재검증했고 PANDA는 subject linkage 전까지 image/case-only다.
4. **P0-M3 / G3**: **Pass**. 기존 embedding과 fixed folds의 OOF refit, grouped
   permutation과 subject-cluster uncertainty에서 두 source positive control이 통과했다.
5. **P0-M4 / G4**: **Conditional Pass**. 고정 same-FOV grid, target/QC, subject folds와
   14-focus exclusion을 통과했으며 descriptive tumor target만 M5에 허용했다.
6. **P0-M5 / G5**: **Pass**. 1,218개 paired tile의 CONCH 512차원 및 Virchow
   2,560차원 frozen embedding, crop-byte pairing, finite/norm, 결정론과 source hash를 통과했다.
7. **P0-M6 / G6**: **Conditional Pass**. CONCH와 Virchow의 descriptive tumor 조합이
   subject-grouped permutation 기준을 넘었다. 단일 descriptive target이므로 strong pass는 아니다.
8. **P0-M7 / G7**: **Amber**. 두 shared-FOV 조합은 positive-only, sampling과 QC 방향을
   유지했지만 native input에서 tile 성능이 낮아졌고 scanner/stain robustness는 판정 불가다.
9. **P0-M8+**: shared-394.24µm descriptive tumor 조합의 통합 Conditional-Go 판정만
   열렸으며 confirmatory·임상·PNI 또는 encoder-superiority 결론은 열리지 않는다.

현재 직접 blocker는 quantitative annotation repeatability와 PANDA subject linkage다.
첫 항목은 confirmatory target claim, 둘째는 PANDA patient inference를 막는다. GPU driver는
샌드박스 밖에서 확인됐고 P0-M5는 shared-device 실행 한계를 기록한 채 완료했다.

## 12. Gate 책임과 증거

| Gate | 책임 | 직접 증거 |
|---|---|---|
| P0-G0 | 연구책임자 | 이 문서, `run_config.json`, claim matrix |
| P0-G1 | 연구책임자; 병리/통계 자문 가능 | metric eligibility, measurement provenance |
| P0-G2 | 연구책임자; 데이터 자문 가능 | common manifest, mismatch, leakage, exclusion flow |
| P0-G3 | 연구책임자; 통계 자문 가능 | saved OOF, permutation null, positive-control report |
| P0-G4 | 연구책임자; 병리/데이터 자문 가능 | paired tile/target manifest와 target availability |
| P0-G5 | 연구책임자; ML/데이터 자문 가능 | embedding manifest, determinism 및 technical QC |
| P0-G6 | 연구책임자; 통계 자문 가능 | concept OOF, permutation, bootstrap와 fold diagnostics |
| P0-G7 | 연구책임자; ML/통계 자문 가능 | representation/scale/sampling/discordance report |
| P0-G8 | 연구책임자 최종 승인 | P0 report, gate와 unlock matrix |
| P0-G9 | 자동 재현성 검사 + 연구책임자 인계 | clean rerun, pre/post 및 output hashes, handoff |

## 13. 산출물 schema와 생성 주체

`run_preexperiment.py`가 필수 table의 header와 행을 생성한다. 기계 판독 가능한 단일
schema 정의는 스크립트의 `TABLE_SCHEMAS` 상수다. Header-only issue table도 이 정의를
포함하며, 빈 바이트 파일을 만들지 않는다.

| 파일 | 생성 주체 | 현재 상태/내용 |
|---|---|---|
| `run_config.json` | entry point | model/config/hash/version, decision proposal, 실행시각 |
| `source_inventory.csv` | entry point | source/model pre/post hash, size, shape, role |
| `metric_eligibility.tsv` | entry point + pathology approval | 지표 role/단위/분모/독립성/repeatability |
| `measurement_provenance.csv` | entry point + data/pathology approval | source/algorithm/validator/provenance |
| `common_sample_manifest.csv` | entry point | endpoint별 common ID와 source truth reconciliation |
| `membership_mismatch.csv` | entry point | model-only/neither sample과 배제 사유 |
| `truth_mismatch.csv` | entry point | mismatch-only issue table; 현재 header + 0 issue rows 예상 |
| `leakage_audit.csv` | entry point | duplicate/group/fold/subject-linkage 감사 |
| `exclusion_flow.csv` | entry point | source universe부터 common universe까지 보존 |
| `claim_evidence_matrix.csv` | entry point + research lead | 허용/금지 주장과 증거 |
| `deviation_log.csv` | entry point + 각 owner | 예상/실제 차이, 영향, 조치 |
| `p0_gate_matrix.csv` | entry point + approvers | G0–G9 상태와 직접 evidence |
| `main_study_unlock_matrix.csv` | entry point + research lead | FM0–FM10 lock/unlock |

Generated CSV/TSV/JSON과 후속 분석 output은 `.gitignore` 대상이다. 이 protocol과 entry
point만 코드/문서 후보이며, 원본, WSI, embeddings, model weights와 generated audit
output은 commit하지 않는다.

P0-G0 승인 후 P0-M3 stage가 생성할 표는 다음 schema로 미리 제한한다. 승인 전에는
header-only 결과 파일도 만들지 않아, 결과가 존재하거나 gate가 실행된 것처럼 보이지 않게
한다.

- `existing_oof_predictions.csv`: `endpoint_id, encoder, config_id, sample_id, group_id,
  fold, truth, outcome_time, prediction, prediction_status, selected_hyperparameter,
  source_embedding_sha256, fold_manifest_sha256`
- `existing_common_sample_results.csv`: `endpoint_id, encoder, config_id, analysis_unit,
  metric_name, estimate, ci_low, ci_high, n_samples, n_groups, n_valid_bootstrap,
  n_undefined_bootstrap, permutation_p95, empirical_p, empirical_q, gate_exceedance`
- `existing_paired_deltas.csv`: `endpoint_id, config_id, metric_name, conch_estimate,
  virchow_estimate, paired_delta, ci_low, ci_high, n_valid, n_undefined`
- `existing_permutation_null.csv`: `endpoint_id, encoder, config_id, replicate_id,
  permutation_seed, metric_name, estimate, replicate_status, undefined_reason`
- `existing_bootstrap_replicates.csv`: `endpoint_id, encoder, config_id, replicate_id,
  bootstrap_seed, metric_name, estimate, replicate_status, undefined_reason`
- `positive_control_report.md`: 관찰 사실, grouped-permutation 결과, 통계적 추론,
  해석/가설, P0-G3 판정을 분리한 보고서

기존 stability cell/fold table만으로 P0-G3를 통과 처리하지 않는다. 위 OOF prediction과
grouped permutation을 frozen embedding 및 fixed fold에서 다시 생성해야 한다.

P0-M4 stage 산출물 schema는 다음과 같이 고정한다.

- `paired_tile_manifest.csv`: 두 encoder가 공유하는 level-0 tile boundary, physical FOV,
  mask mapping, inclusion/exclusion과 locked-PNI overlap.
- `quantitative_targets.csv`: fixed denominator의 tumor/stroma fraction과 pixel counts,
  missing/status.
- `tile_qc.csv`: mask 정합·label audit와 H&E descriptive QC.
- `fold_assignments.csv`: seed와 subject-grouped 5-fold 배정 및 tile counts.
- `target_availability.csv`: overall/fold별 subject·tile floor, 분포와 variation.
- `pni_focus_overlap_audit.csv`: 14개 locked focus의 overlap 및 exclusion 검증.
- `M4_FEASIBILITY_REPORT.md`: provenance, 기술 feasibility와 claim boundary.

P0-M5 stage 산출물 schema는 다음과 같이 고정한다.

- `precise_conch_shared_fov_embeddings.npy`: row-major float32 `[1218,512]`.
- `precise_virchow_shared_fov_embeddings.npy`: row-major float32 `[1218,2560]`.
- `paired_embedding_manifest.csv`: M4 row/order, shared boundary와 encoder별 crop hash/status.
- `embedding_determinism_audit.csv`: encoder별 사전 선택 8-tile 반복 feature hash와 차이.
- `embedding_technical_qc.csv`: array hash/shape/dtype/finite/norm/pairing/determinism gate.
- `M5_TECHNICAL_REPORT.md`: technical evidence와 해석 금지 경계.

P0-M6 stage 산출물 schema는 다음과 같이 고정한다.

- `concept_oof_predictions.csv`: paired tile별 truth, OOF prediction, fold/alpha와 input hash.
- `concept_summary.csv`: tile/subject-mean MAE·R²·Spearman, cluster CI, p95/p/q와 gate.
- `concept_paired_deltas.csv`: 동일 subject bootstrap의 CONCH-minus-Virchow 차이.
- `concept_permutation_null.csv`: subject-label 및 within-subject coordinate null 전체 행.
- `concept_bootstrap_replicates.csv`: undefined를 포함한 subject-cluster replicate 전체 행.
- `concept_fold_diagnostics.csv`: fold별 train/test 범위·성능·generalization gap.
- `M6_CONCEPT_REPORT.md`: 관찰 사실, 통계 추론, gate와 claim boundary.

P0-M7 stage 산출물 schema는 다음과 같이 고정한다.

- `m7_native_fov_manifest.csv`, `m7_native_embedding_qc.csv`, `m7_native_determinism_audit.csv`,
  `precise_virchow_native_fov_embeddings.npy`: native technical extraction.
- `m7_native_oof_predictions.csv`: native/CLS/patch-mean fixed-fold OOF.
- `representation_similarity.csv`: CKA와 pairwise-distance RSA.
- `scale_sampling_sensitivity.csv`: FOV/component 및 shared-draw tile-budget 결과.
- `zero_inflation_sensitivity.csv`: positive-only와 presence 분해 및 cluster CI.
- `qc_sensitivity.csv`: QC–error 및 Q1/Q4 성능 방향.
- `discordance_manifest.csv`, `discordance_qc_associations.csv`: paired residual discordance.
- `M7_ROBUSTNESS_REPORT.md`: Green/Amber/Red 판정과 허용 범위.

## 14. P0-G0 승인 기록

연구책임자는 결과 분석 전에 다음 네 묶음을 승인했다.

1. **Target/denominator**: sole primary를 provided-mask tumor fraction으로 두고,
   denominator를 labels `{1,2,4,5,6,7}`로 하는 안. Expert annotation provenance 확인이
   실패하면 primary를 중단/강등한다는 규칙.
2. **FOV**: primary shared FOV 394.24 µm, native sensitivity CONCH 394.24 µm와
   Virchow 98.56 µm.
3. **Probe/statistics**: subject-grouped 5-fold, 동일 L2 linear probe와 17-value budget,
   MAE/R²/Spearman, 2,000 grouped permutations, 2,000 paired bootstraps, primary-family BH-FDR.
4. **Claims/governance**: methodological feasibility만 허용하고 model superiority와 임상/
   whole-slide PNI 주장을 금지하며, 승인자 이름/역할과 approval timestamp를 기록한다.

승인 기록:

```text
P0-G0 승인: P0-QFMV-2026-08-11-DRAFT-001의 target/denominator, FOV,
probe/statistics, claims/governance를 승인한다.
승인자/역할: Jin Hyun Kim / PM
승인시각: 2026-08-11T19:17:36Z
```

승인된 네 묶음에 수정은 없었다. 이 승인으로 새 protocol ID를 `approved` 상태로
기록했다. P0-G1은 기존 source control에 한정한 Conditional Pass, P0-G2는 verified
subject/case linkage가 있는 NADT/TCGA/LEOPARD에 한정한 Conditional Pass로 적용하고,
PANDA patient inference와 PRECISE Frame D는 계속 잠근다.

## 15. Protocol amendment 001 — 독립 연구 승인 체계 비례화

- 결정자: Jin Hyun Kim / 연구책임자(PM)
- 지시 시각(UTC): 2026-08-12T13:12:04Z
- 적용 시점: P0-M8 결과 확인 후, P0-G8 최종 확정 전
- 변경 사유: 현재 연구는 단일 책임자가 독립적으로 수행하며, 다기관 공동연구 수준의
  역할별 필수 전자승인을 모든 단계에 적용할 필요가 없다.
- 변경 내용: P0-G8의 필수 승인은 연구책임자 한 명의 최종 승인으로 한다.
  병리·통계·ML/데이터 검토는 필요 시 기록하는 비차단 자문으로 전환한다. P0-G9는
  자동 재현성 검사 결과를 연구책임자가 확인하는 방식으로 한다.
- 투명성: 이 변경은 결과 확인 후 이루어진 governance amendment이며 사전지정 변경으로
  소급 표현하지 않는다. 기존 append-only 승인 기록은 삭제하지 않는다.
- 불변 항목: target, denominator, FOV, probe, fold, permutation/bootstrap, 통계 threshold,
  허용 조합과 과학적 claim 제한은 변경하지 않는다.
- 향후 적용: 다기관·다책임자 공동연구, 임상 의사결정 또는 규제 목적 단계에서는 별도
  protocol로 다학제·기관별 승인 체계를 다시 활성화한다.
