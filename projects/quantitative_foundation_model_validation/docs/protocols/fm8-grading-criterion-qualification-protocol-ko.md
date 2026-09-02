---
document_id: fm8-grading-criterion-qualification-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: completed
created: 2026-09-01
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm8-grading-criterion-qualification-protocol-ko.md
superseded_by: projects/quantitative_foundation_model_validation/docs/protocols/fm9-prostate-diagnostic-anchor-and-discovery-protocol-ko.md
---

# FM8 grading-criterion qualification protocol

## 고정 질문

1. PANDA에서만 개발한 frozen-representation grading head가 독립 biopsy 코호트의
   cancer-only ISUP 1--5를 맞히는가?
2. 해당 코호트의 판정 근거인 primary/secondary Gleason 및 GP3/4/5, 가능한 경우
   cribriform/minor high-grade pattern이 frozen representation에서 복원되는가?
3. 이 criterion subspace를 제거할 때 locked grading head가 matched-random보다 더
   저하되는가?
4. joint reliance를 상관된 criterion들에 불확실성과 함께 얼마나 배분할 수 있는가?

## 코호트 잠금

- Development: PANDA public development 10,616 biopsy WSI. 외부 성능 근거로 사용하지 않는다.
- Qualification: SICAPv2 공식 Test partition 21 patients/31 WSI. 이전 detector 작업에서
  열렸음을 표시하고 pristine confirmatory라는 표현을 금지한다.
- Confirmatory external: PAR S-BIAD2323, 185 patients/339 glass slides. Hamamatsu scan을
  primary로 잠그고 Grundium/Leica는 paired scanner-repeatability 분석에 사용한다. 다운로드
  전에 reader와 consensus sensitivity rule을 run config에 고정한다.
- Secondary transport: CHIMERA 95 prostatectomy patients. Reported ISUP와 Gleason mapping의
  3개 discrepancy는 제외하지 않고 별도 sensitivity로 보존한다.

PAR Hamamatsu NDPI의 level-0 region decoding은 OpenSlide를 사용하고 Python/library version을
embedding cache에 기록한다. Tifffile metadata dimensions와 OpenSlide dimensions가 일치해야
하며, 양 encoder의 decoded-RGB SHA-256이 tile별로 동일해야 한다.

PANDA hidden validation/external data는 접근 권리와 immutable source가 확보되지 않는 한
계획된 입력으로 간주하지 않는다.

## 레이블과 임상 기준

Benign과 cancer grading을 분리한다. ISUP 0/negative는 cancer detection에만 포함하고,
grading primary estimand는 cancer case의 ISUP 1--5다. Gleason-to-ISUP mapping은 고정한다:

- 3+3 -> 1
- 3+4 -> 2
- 4+3 -> 3
- 4+4, 3+5, 5+3 -> 4
- 4+5, 5+4, 5+5 -> 5

Biopsy와 prostatectomy의 scoring rule을 분리한다. Biopsy에서 세 pattern이 있으면 가장 흔한
pattern을 primary로, 남은 것 중 최고등급 pattern을 secondary로 포함하고 tertiary를 별도
점수로 두지 않는다. Prostatectomy에서는 두 번째로 흔한 pattern과 minor high-grade pattern을
구분하며, 5% 미만 minor pattern 5는 score와 별도로 기록한다. CHIMERA tertiary는 이
prostatectomy 규칙 아래에서만 해석한다.

형태 기준은 GP3의 개별 well-formed gland, GP4의 poorly formed/fused/cribriform/glomeruloid
gland, GP5의 gland formation 소실·solid sheet·cord/single cell·comedonecrosis로 등록한다.
현재 데이터에서 subtype-level truth가 있는 것은 SICAP의 cribriform G4C뿐이며, 나머지는
aggregate GP3/4/5 truth다. 따라서 aggregate pattern 복원을 모든 세부 형태 복원으로
확대하지 않는다. Primary/secondary pattern, GP3/4/5 proportion, 가능한 minor high-grade와
cribriform GP4를 정량 criterion으로 사용한다. Age, PSA, pT, margin, node,
seminal-vesicle/capsular/lymphovascular invasion은 grading criterion registry에서 제외하고
BCR prognostic covariate registry에만 둔다.

## 정확도 estimand

- Primary: patient-clustered cancer-only QWK.
- Secondary: MAE, exact, within-one, macro/class recall, severe error, confusion, ordinal
  calibration; benign/cancer sensitivity와 specificity는 별도 표.
- PAR: 같은 glass slide의 세 scanner를 독립 표본으로 세지 않는다. Primary reader별
  agreement를 모두 제시하고, 제공되지 않은 consensus를 사후 생성해 gold standard라
  부르지 않는다.
- 불확실성: 2,000회 patient bootstrap. Undefined replicate는 삭제하지 않고 개수와 원인을
  저장한다.

Primary head는 encoder를 고정한 gated-attention multiple-instance ordinal head다. 최대 64개
outcome-blind tissue tile에 LayerNorm, 256-unit gated attention, weighted pooling과 ISUP
0--5용 다섯 all-threshold logit을 적용한다. Seed 260901, slide batch 16, AdamW learning rate
`1e-4`, weight decay `1e-4`, 최대 30 epoch를 고정한다. PANDA provider-by-grade stratified
development split에서 epoch를 선택하고 선택 epoch만큼 전체 PANDA를 처음부터 다시 적합한다.
SICAP 또는 PAR 결과를 epoch·threshold·pooling 선택에 사용하지 않는다. Mean-pooled ordinal
linear model은 secondary architecture check일 뿐 primary를 대체하지 않는다. 이 secondary
head의 feature 표준화도 epoch 선택 시 PANDA development, 최종 refit 시 전체 PANDA의 통계만
사용하며 SICAP/PAR 통계는 사용하지 않는다.

두 단계 정확도 판정을 저장한다. `ABOVE_CHANCE`는 patient-bootstrap QWK 95% 하한이 0보다
커야 한다. `ADEQUATE_FOR_FUNCTIONAL_TESTING`은 PAR reader 1과 reader 2 각각에서 QWK
0.60 이상, within-one 0.90 이상, severe-error 0.05 이하를 추가로 요구한다. Reader 1/2는
제공된 label 그대로 co-primary이며 사후 consensus를 만들지 않는다. Reader 3은 제공된
uropathologist subset sensitivity다. 이 gate가 실패하면 정확도 결과는 보고하되 기능적
사용 해석과 grading residual 진입은 중단한다. Gate는 encoder별로 적용하며, 두 co-primary
reader를 모두 통과한 encoder만 M2--M3로 진입한다. 한 encoder의 실패가 다른 encoder의
통과 결과를 무효화하지 않는다.

## 표현·사용·비중

GP3/4/5 criterion probe는 pattern truth가 있는 PANDA Radboud에서만 적합하고 외부에 변경
없이 적용한다. Karolinska의 cancer-only mask를 pattern truth로 사용하지 않는다. Cribriform은
PANDA에 subtype truth가 없으므로 SICAP 공식 Train에서만 probe를 개발할 수 있고,
patient-disjoint 공식 Test에서 고정 검증한다. 각 criterion마다 recoverability, fixed-head
erasure delta, matched-random percentile/p-value, 0/25/50/75/100% erasure dose-response를
저장한다. Joint criterion subspace 제거가 primary다.

사용 비중은 하나의 수로 합치지 않고 다음 세 축을 동시에 보고한다.

1. representation recoverability 및 joint explained-variation summary;
2. ordinal-logit variance의 Shapley/dominance allocation;
3. `QWK` 또는 BCR `C-index`의 absolute delta와 normalized reliance.

Fixed-head는 reliance, refit은 replaceability다. 개별 criterion의 합은 joint effect와 같다고
가정하지 않는다. Encoder와 outcome을 합산한 단일 사용률은 산출하지 않는다.

## 중단 규칙

원천 hash, patient identity, 외부 cohort 무튜닝, criterion truth, QFM 사용 선언 중 하나라도
실패하면 confirmatory run을 시작하지 않는다. 외부 accuracy가 chance 수준이거나 joint
erasure가 matched random을 넘지 못하면 residual을 계산하지 않는다. 결과를 본 뒤 threshold,
pooling, criterion, reader 또는 scanner를 바꾸면 새 confirmatory cohort 없이는 탐색 결과다.
