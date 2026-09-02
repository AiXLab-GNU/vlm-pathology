---
document_id: fm9-prostate-diagnostic-anchor-and-discovery-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-09-02
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm9-prostate-diagnostic-anchor-and-discovery-protocol-ko.md
---

# FM9 prostate diagnostic anchor and frozen-discovery protocol

## 고정 질문

1. 독립 biopsy reference에서 암 유무와 cancer-only grade를 충분히 정확하게 판정하는가?
2. 실제 reference를 구성하는 독립 병리 criterion이 frozen representation에 존재하는가?
3. 그 criterion을 제거하면 고정된 진단 head가 matched control보다 더 저하되는가?
4. 알려진 criterion의 joint reliance와 criterion별 allocation은 얼마인가?
5. 앞의 항목과 shortcut을 제거한 뒤 반복되는 잔여 신호가 있는가?

## 코호트와 개봉 순서

- PANDA: development only
- DiagSet-B/A: 각각 cancer head development와 spatial criterion development; subset/patient
  중복을 먼저 감사
- DiagSet-C: 9-reader cancer/no-cancer/uncertain-IHC qualification; model selection 금지
- PBGG-1/2: cancer-positive grading qualification; 두 part를 별도 결과로 보고
- PRECISE paired-IHC release: 신규 획득·integrity 통과 후 cancer criterion anchor; 최종
  accuracy denominator 금지. 현재 local H&E-only legacy payload는 IHC 0과 malformed metadata로 제외
- SICAP: prior-open criterion positive control; pristine confirmatory 표현 금지
- PAR: 이미 개봉된 historical reader/scanner stress; FM9 선택·gate의 primary cohort 금지
- SPROB20: controlled-access 승인 후 별도 patient-level transport만 허용

Access, license, membership, patient/case mapping, WSI/label hash를 잠근 뒤 prediction을 만든다.
PBGG reader table은 사용 양식의 조건을 기록하고 prediction 전에 immutable copy를 잠근다.

## 분리된 모델 경로

`diagnostic_anchor`와 `frozen_fm`은 weights, features, checkpoints, predictions, calibration과
claim namespace가 다르다.

### Diagnostic anchor

- 저배율 전체조직 coverage → 고배율 tumor/uncertain 후보의 coarse-to-fine 구조
- 전용 cancer/abstain head
- cancer ROI의 GP3/4/5 map, pattern proportion, primary/secondary pattern, deterministic ISUP
- task-specific 학습을 허용하되 외부 cohort tuning은 금지
- off-the-shelf grading 양성 대조군은
  `chimera_hvit_biopsy_isup_off_the_shelf_weights_v1`로 고정하고, 재학습 HViT는
  `qfm_hvit_biopsy_isup_retrained`로 분리한다.
- off-the-shelf 모델은 commit `2b17a75891e8f017e7a92201509c63770cd39fe5`,
  `weights-v1`의 10개 SHA-256, 0.5 micrometre/pixel, 2,048-pixel region, 256-pixel patch,
  5-fold와 960차원 latent 계약을 변경하지 않는다.
- 명시적 license/permission, weight materialization, digest/dependency-locked container와 D0
  data gate 중 하나라도 PASS가 아니면 fail-closed로 prediction을 금지한다.

### Frozen FM

- CONCH와 Virchow encoder weights는 고정
- 전용 cancer head와 cancer-conditioned grading head를 별도로 적합
- common physical-FOV branch와 model-card native-scale branch를 별도 산출
- encoder 비교의 common branch는 동일 tissue boundary와 decoded-RGB hash를 요구
- random maximum-64 tissue tile bag을 primary coverage로 사용하지 않음

## Endpoint

Cancer primary는 dedicated binary/abstaining output이다. Direct ordinal head의
`1-P(ISUP0)`는 coherence sensitivity만 허용한다. `uncertain/need IHC`, HGPIN, AIP, IDC-P는
사전 고정된 임상 endpoint mapping 밖에서는 결측/제3 상태로 보존한다.

Grading primary는 cancer-positive specimen의 ISUP 1--5다. GP3/4/5 spatial truth가 있으면
pattern proportion과 primary/secondary를 병행한다. Biopsy rule과 prostatectomy minor-pattern
rule을 섞지 않는다.

## 정확도·불확실성

- 독립 단위: patient 우선; patient ID가 제공되지 않으면 slide-level 한계를 명시
- bootstrap: 2,000회 cluster bootstrap; undefined replicate를 보존
- cancer: AUROC/AUPRC, sensitivity, specificity, PPV/NPV, calibration, decision threshold,
  abstention coverage-risk와 reader별 agreement
- grading: QWK, MAE, exact, within-one, macro/class recall, severe error, confusion, calibration

Frozen grading의 functional-entry는 PBGG-1과 PBGG-2 각각에서 majority QWK >= 0.70,
bootstrap lower 95% bound >= 0.60, within-one >= 0.90, severe error <= 0.05를 모두 요구한다.
Reader별 분포가 consensus 결과와 크게 어긋나는지도 별도 flag로 남긴다. Cancer functional-entry
threshold는 DiagSet acquisition 후 reader consensus/uncertain prevalence와 development power를
사용해 external prediction 전에 run config에 고정한다.

## Criterion truth

- PRECISE paired-IHC 신규 release: malignant/benign gland, stroma, IDC-P, HGPIN, AIP,
  artifact와 paired IHC; source/pairing/mask audit 통과 후에만 사용
- DiagSet-A: 제공되는 cancer/tissue/Gleason-region annotation
- SICAP: aggregate GP3/4/5와 cribriform G4C
- PBGG: 제공되는 reader/majority slide grade와 primary/secondary pattern 범위

독립 subtype truth가 없는 poorly formed/fused/glomeruloid/GP5 subtype은 aggregate GP4/5
복원으로 대체하지 않는다. Anchor prediction을 frozen probe truth로 사용하지 않는다.

## 기능적 사용과 allocation

정확도와 외부 recoverability를 통과한 frozen encoder–endpoint만 분석한다. Source-fitted
criterion direction을 고정하고 target에서 재적합하지 않는다. Individual 및 joint fixed-head
erasure를 100개 rank/variance-matched random subspace, label permutation과 비교한다.
0/25/50/75/100% dose response를 저장한다.

사용량은 단일 보편 백분율이 아니다. 다음을 함께 보고한다.

1. full 대비 absolute performance loss
2. `(performance_full - performance_erased) / max(performance_full, epsilon)`
3. ordinal/binary logit variance의 Shapley 또는 dominance allocation
4. joint effect, individual effect와 bootstrap uncertainty

Fixed-head는 reliance, refit-after-erasure는 replaceability다. Cancer와 grading, CONCH와
Virchow의 denominator를 합치지 않는다.

## 중단 규칙

다음 중 하나면 해당 lane을 중단한다: patient/source overlap 미해결, license/label semantics/
hash 불완전, diagnostic anchor 실패, frozen accuracy 실패, external criterion recoverability
실패, targeted erasure가 matched random을 넘지 못함, shortcut clearance 실패. 실패 후 PBGG,
DiagSet-C 또는 PAR 결과로 threshold/scale/sampling/head를 바꾸면 새 독립 cohort 없이는
exploratory다. D3와 D4가 통과하기 전에는 residual coordinate나 pathology review packet을
생성하지 않는다.

## 구현 상태 — 2026-09-02

공식 CHIMERA-HViT source checkout의 commit, source-file hash, upstream weight checksum,
geometry와 ensemble/output 계약을 preflight했다. 이 항목들은 PASS였지만 upstream source에
명시적 license 파일이 없고 Dockerfile base image가 mutable tag이며 requirements가 부분적으로만
고정돼 있다. Weight 10개와 D0 external data도 아직 local hash verification을 마치지 않았다.
따라서 상태는 `NOT_READY`, `prediction_permitted=false`이며 성능 결과는 생성하지 않았다.
