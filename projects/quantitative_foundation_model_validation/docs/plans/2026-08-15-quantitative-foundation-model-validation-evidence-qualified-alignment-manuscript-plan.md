---
document_id: 2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: approved
created: 2026-08-15
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-design.md
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer
verification:
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python -m unittest discover -s projects/quantitative_foundation_model_validation/tests -p 'test_*.py' -v
  - .venv/bin/python -m unittest discover -s projects/prostate_biomarker_validation/tests -p 'test_*.py' -v
---

# Evidence-qualified alignment manuscript implementation plan

## 목표와 실행 원칙

목표는 기존 PBV submission bundle을 손상하거나 복사하지 않고, 승인된 immutable evidence를
QFM에 명시적으로 승계해 alignment 중심의 main manuscript와 Supplementary Information을
새로 만드는 것이다.

- Main과 Supplementary는 **모두 전면 재편집**한다.
- 기존 endpoint, fold, frozen estimates와 analysis family를 소급 변경하지 않는다.
- 신규 narrative가 기존 수치를 강화하거나 기능적 사용으로 재명명하지 못하게 fail-closed
  contract를 먼저 만든다.
- 각 task는 source hash·claim boundary·numeric QA를 통과해야 다음 task로 진행한다.

## 작업공간

```text
projects/quantitative_foundation_model_validation/
├── docs/designs/2026-08-15-...-manuscript-design.md
├── docs/plans/2026-08-15-...-manuscript-plan.md
└── paper/evidence-qualified-alignment-prostate-cancer/
    ├── README.md
    ├── main.tex                         # implementation gate 이후 생성
    ├── supplement.tex                   # implementation gate 이후 생성
    ├── sections/                        # main/supplement source
    ├── figures/                         # 새 renderer와 generated figures
    ├── generated/                       # source-driven tables/macros
    └── provenance/                      # source/claim/numeric manifests
```

현재 단계에서는 `README.md`만 만들고 PBV TeX, PDF, figure 또는 generated table을 복사하지
않는다.

## Task 0. 소유권·승계 승인

- [x] 연구책임자가 design Section 11의 원고 소유·주장 범위를 승인했다.
- [x] PBV `PROJECT.yaml`, claim boundary, canonical plan에서 기존 bundle의 frozen owner와
  신규 QFM manuscript owner를 구분한다.
- [x] QFM plan/milestone/tracker에 manuscript workstream의 범위와 현재 H1/H2 claim ceiling이
  변하지 않음을 기록한다.
- [x] 승인 시점 전에 title/abstract prose 외의 결과 수치를 새 workspace로 옮기지
  않았다.

**Gate 0:** `OWNERSHIP_AND_SCOPE_APPROVED` — 2026-08-15 PASS.

## Task 1. PBV source-evidence inventory와 immutable 승계

- [x] PBV claim–evidence matrix C01–C08, endpoint hierarchy E01–E09, active main/supplement
  sections, figure/table manifests와 numeric QA mapping을 inventory한다.
- [x] 원고에 실제 사용할 source CSV/JSON, 생성 script와 output의 SHA-256·bytes·owner를
  기록한다.
- [x] patient-level/local workspace 파일은 manifest pointer만 기록하고 복사하지 않는다.
- [x] `source reference only`, `immutable promoted evidence`, `historical context`,
  `prohibited dependency`를 각 행에 부여한다.
- [x] 허용된 항목으로 `provenance/source_evidence_manifest.csv`를 생성하고 양 프로젝트
  테스트에서 hash와 owner를 검증한다.
- [x] 승계 source 15개의 current hash·bytes를 고정하고 build에서 재검증한다.

**Gate 1:** implicit cross-project dependency 0건, unresolved source ownership 0건.

## Task 2. Alignment terminology·claim·endpoint contract

- [x] `provenance/alignment_target_registry.csv`에 target 층, unit, label source, metric, null,
  encoder, cohort와 permitted interpretation을 고정한다.
- [x] `provenance/claim_evidence_matrix.csv`를 신규 claim hierarchy로 만들되 PBV source
  claim ID와 lineage를 보존한다.
- [x] `provenance/endpoint_hierarchy.csv`에서 reconstructed recurrence, PFS, DFS와 official
  PFI를 분리한다.
- [x] claim matrix와 manuscript test에 functional-use·mechanistic·clinical 과장 금지 규칙을 추가한다.
- [x] `alignment`가 OOF/external probe association임을 Methods와 모든 legend에서 동일하게
  정의한다.

**Gate 2:** 모든 planned claim이 target registry, source claim과 endpoint row에 연결됨.

## Task 3. Main manuscript 구조 재작성

- [x] 작업 제목과 200-word 이하 narrative abstract를 작성한다.
- [x] Introduction을 `interpretable axes → alignment gap → qualification need → study
  hypotheses` 순서로 재작성한다.
- [x] Results를 design Section 6의 여섯 decision block으로 재작성한다.
- [x] Qualification framework를 첫 기여에서 alignment 판정 방법으로 내린다.
- [x] Discussion 첫 문장을 morphology/molecular/outcome alignment hierarchy로 시작한다.
- [x] 독립 Conclusion 절을 두고 공유 정량 좌표의 필요성·장점과 본 연구가 설명한 정도를
  representation, decision-sensitivity, clinical-use 수준으로 구분한다.
- [x] QFM의 completeness/functional use/residual 연구는 future work로만 연결한다.
- [x] Methods에 cohort, frozen representation, probe, unit, fold, uncertainty와 qualification
  axes를 재현 가능한 순서로 쓴다.
- [x] declaration의 author-controlled unknown은 명시적 author action으로 남긴다.

**Gate 3:** title/abstract/section order, claim-language, word-count와 citation contracts PASS.

## Task 4. Main figure·table 시스템 재편

- [x] Figure 1을 process diagram이 아니라 target × evidence-axis alignment map으로 만든다.
- [x] Morphologic, molecular, outcome alignment을 source-linked main figure에 배치한다.
- [x] CONCH/Virchow 차이는 paired target/setting sensitivity로 표현하고 순위를 만들지 않는다.
- [x] pooled estimate와 grade-adjusted/site/endpoint-conditioned 결과를 시각적으로 분리한다.
- [x] main headline number 20개를 `numeric_qa_mapping.csv`의 source row/field/format에 연결한다.
- [x] active main figure 4개와 synthesis table 1개로 중복을 줄인다.
- [x] PBV PDF/PNG를 복사하지 않고 immutable source table에서 새 renderer로 생성한다.

**Gate 4:** source/script/output hash, final-size legibility, two-render determinism PASS.

## Task 5. Supplementary Information 전면 재작성

- [x] Supplement title과 scope paragraph를 main과 동기화한다.
- [x] design Section 7의 12개 순서로 Supplementary Methods/Results/Tables/Figures를
  재배치한다.
- [x] full grid, paired contrasts, site missingness, endpoint concordance, underpowered/undefined
  rows를 누락 없이 보존한다.
- [x] Main claim마다 최소 한 개의 supplement subsection 또는 source table link를 둔다.
- [x] Supplement의 독립 figure/table numbering을 두 번의 XeLaTeX build로 검사한다.
- [x] Main에서 제거한 caveat가 supplement에만 숨어 claim을 강하게 만들지 않도록 핵심
  local limitation은 main에도 유지한다.

**Gate 5:** supplement completeness matrix 100%, orphan claim/table/figure 0건.

## Task 6. Main–Supplement 통합 numeric·semantic QA

- [x] headline quantity 20개는 main·Supplement에서 같은 source field와 rounding rule을 사용한다.
- [x] cohort denominator, event count, complete-case count, analysis unit와 interval type을
  자동 대조한다.
- [x] endpoint substitution, patient/slide unit mixing과 OOF/in-sample 혼용을 검사한다.
- [x] `transportable`, `context-sensitive`, `unsupported`, `not evaluated` 상태가 claim matrix와
  일치하는지 검사한다.
- [x] main과 supplement를 각각 두 번 build해 unresolved citation·figure·table reference 0건을 확인한다.
- [x] source manifest에 없는 headline 수치와 source ID를 fail로 처리하고, mapped display가
  지정 manuscript section에 실제 존재하는지 검사한다.

**Gate 6:** numeric mismatch 0, semantic mismatch 0, unresolved references 0.

## Task 7. 빌드·재현성·시각 QA

- [x] 단일 builder가 main과 supplement의 tables, figures, TeX와 PDF를 생성하도록 한다.
- [x] temporary output root 두 곳에서 clean build하고 비휘발성 hash를 비교한다.
- [x] XeLaTeX를 각 문서에 두 번 실행하고 unresolved reference/citation과 overfull defect를
  검사한다.
- [x] 모든 PDF page를 rasterize해 글자 크기, clipping, panel balance, table overflow와 빈
  page를 시각 검토한다.
- [x] 승계한 PBV source 15개의 hash·bytes가 build 전후 일치함을 확인한다.
- [x] QFM/PBV focused tests, full tests, file governance, boundary, worktree와 diff checks를
  실행한다.

**Gate 7:** 두 submission PDF 재현, 원본 hash 불변, 모든 의도된 audit PASS.

## Task 8. 연구책임자 handoff

- [x] 기여 문장, primary claims, evidence gaps와 prohibited claims를 한 페이지로 요약한다.
- [x] main/supplement page·word·figure/table counts와 artifact hashes를 기록한다.
- [x] author/funding/ethics/journal-format action item을 구분한다.
- [x] submission status를 `partial—author metadata required`로 근거와 함께 판정한다.
- [x] FM6 중 whole-tissue internal ISUP functional-sensitivity 근거만 명시적으로 승계하고,
  residual/new-marker 결과는 이 원고에 합치지 않는다는 경계를 확인한다.

## Task 9. 2026-08-16 교차전공 설명·통계 Methods 편집

- [x] Introduction에 resource별 target, analysis unit와 qualification role을 한 표로 복원한다.
- [x] pathology 용어와 AI workflow 용어를 함께 설명하는 Clinical and analytical
  orientation을 복원·확장한다.
- [x] 모든 Results block에 Alignment question, Analysis frame, Evidence test, Interpretive
  boundary, Qualification rule을 적용한다.
- [x] Figure 1에 대한 행·열·미검증 functional-use column 판독법을 명시한다.
- [x] PBV Methods의 분석 순서와 통계 절차를 유지하면서 통계 기법의 목적과 null·metric
  해석을 AI 연구자가 읽을 수 있는 수준으로 보강한다.
- [x] Data Availability, Funding, Ethics and consent statement를 PBV 원문과 동일하게
  승계한다. Code Availability는 공개 PBV 분석 코드와 QFM 원고 재현 코드의 실제 추적 경로를
  구분하고, release tag·commit·DOI 미확정 상태를 명시한다.
- [x] main·supplement 재빌드와 semantic/numeric/governance 회귀검사를 수행한다.

**Gate 9:** qualification 형식이 alignment 주장을 보조하고, 통계 설명이 분석 변경으로
오인되지 않으며, 선언문 문언과 source provenance가 일치해야 한다.

## Task 10. 2026-08-16 결과 비중과 다축 근거 확장

- [x] Main에 10개 primary/transport estimate의 cohort·unit·n·metric·interval 완전표를 둔다.
- [x] molecular figure에 PTEN/AR beyond-grade와 AR/SPOP 전체 site 감사를 함께 제시한다.
- [x] 390개 seed-matched scale/encoder/tile contrast를 target별 분포로 시각화한다.
- [x] reconstructed recurrence와 official PFI의 전체 paired comparison family를 제시한다.
- [x] Supplement에 전체 site row, contrast family 요약, 두 endpoint의 22개 결과 row와
  missingness/bootstrap accounting을 추가한다.
- [x] promoted source에 없는 complete raw/adjusted p-value table은 재구성하지 않고 한계로
  명시한다.
- [x] 6개 main figure·2개 main table과 확장 Supplement의 build, numeric, semantic,
  visual/governance QA를 통과한다.

**Gate 10:** 결과 확장은 기존 15개 hash-locked source만 사용하며, 새 학습·refit·endpoint
변경 없이 현 claim ceiling을 더 완전하게 보여 주어야 한다.

## Task 11. 2026-08-16 FM6 근거 승계와 최종 scope lock

- [x] FM6 internal summary, within-encoder contrast, SICAP secondary와 PANDA holdout 표를
  QFM-owned source manifest와 numeric QA mapping에 hash-lock한다.
- [x] ISUP fixed-head erasure effect를 두 encoder에서 반복된 `internal exploratory
  functional sensitivity`로만 보고한다.
- [x] refit interval이 zero를 포함하므로 indispensable use를 주장하지 않는다.
- [x] 제한적인 ISUP+AI 대 ISUP-only 비교는 `increment not established in this analysis`로
  쓰며, clinical increment 부재를 충분히 평가한 실험으로 해석하지 않는다.
- [x] SICAP specificity 0.810은 secondary internal evidence로 수용하되, PANDA 두 provider의
  sensitivity gate 실패를 independent-domain limitation으로 main과 supplement에 남긴다.
- [x] tumor-specific/external functional-use claim과 residual/unknown AI feature marker
  discovery를 후속 논문으로 분리한다.
- [x] 원고·그림·표를 재빌드하고 numeric/semantic/governance 회귀검사를 완료한다.

**Gate 11:** 현재 논문은 알려진 임상 지표의 alignment와 제한적 내부 기능 민감도만
주장하며, 독립 domain sensitivity와 임상 증분의 미평가 및 residual 후속 범위를 숨기지
않아야 한다.

Gate 11은 source 19개와 numeric mapping 33개의 builder 검증, main/Supplement PDF build,
원고 contract 9/9, QFM 87/87, file-governance PASS와 새 Figure 1·functional-results page
시각 점검으로 통과했다. Repository boundary validator의 유일한 실패는 본 작업과 무관한
기존 top-level `webportal-refactoring.md` 미등록 항목이다.

## Task 12. Human coordinate--AI feature--judgment 비교 시각화

- [x] 임상·병리 지표, 이를 조작화한 probe-defined embedding direction/score, downstream
  judgment evidence를 세 개 층으로 분리한다.
- [x] Grade/ISUP의 CONCH·Virchow recoverability와 locked BCR-head erasure effect를 연결한다.
- [x] Phenotype·PTEN·AR·SPOP은 representation evidence와 functional-use 미검증 경계를
  함께 표시한다.
- [x] Recurrence는 병리 측정치가 아니라 endpoint-sensitive outcome risk score로 구분한다.
- [x] Figure 수치가 기존 hash-locked source에서 직접 생성되고 원고 caption이 feature의
  생물학적·공간적 과해석을 금지하도록 한다.
- [x] Results 첫 표에서 여섯 축의 임상적 의미, frozen-representation 근거와 BCR-head
  기능 기여 상태를 먼저 비교한다.
- [x] `미검증`을 phenotype의 현재 data block, PTEN·AR의 실행 가능한 후속 실험,
  SPOP의 선행 recoverability 미충족, recurrence의 질문 비적용으로 구분하고 Discussion과
  Figure 7에 같은 경계를 사용한다.

**Gate 12:** 독자가 `무엇이 표현에서 복원됐는가`와 `무엇이 실제 head 판단에 기여했는가`를
그림만으로 구분할 수 있어야 한다.

## Task 13. Main 20쪽 이내 핵심 원고 축약

- [x] Main의 전체 primary 표와 six-axis biological-definition 표를 Supplementary로
  이동하고 evidence-qualified synthesis 표는 Main의 Table 1로 유지한다.
- [x] 전체 outcome/comparator, representation range와 390개 setting-contrast 그림을
  Supplementary로 이동하고 Main에는 핵심 수치와 해석 경계를 남긴다.
- [x] Main Methods에는 cohort·fold·probe·metric·FM6 intervention·claim boundary를 유지하고,
  상세 통계 정의·설정 민감도·endpoint·bootstrap 구현은 Supplementary에 보존한다.
- [x] Main 4개 figure·1개 table, Supplementary의 완전 근거 구조로 재빌드한다.
- [x] 자동 원고 검사에 Main 20쪽 이하 page-budget contract를 추가한다.

**Gate 13:** Main은 20쪽 이하여야 하며 primary claim, 핵심 수치, 기능 민감도와 limitation을
독립적으로 이해할 수 있어야 한다. 이동된 완전표·민감도·endpoint 근거는 Supplementary에서
누락 없이 재현되어야 한다.

## Task 14. Figure/table 설명 완전성 및 presentation 보강

- [x] Introduction resource orientation table을 인접 본문에서 명시적으로 호출하고,
  Main headline synthesis가 Table 1을 유지하도록 orientation table은 비번호 형식으로 둔다.
- [x] Main Figure 1의 모든 cell code와 Main Table 1의 evidence state 및 locked-head
  functional-use 경계를 caption에서 정의한다.
- [x] conditional figure와 표에서 row-specific metric, delta 산식과 positive direction을
  명시한다.
- [x] Supplementary 12개 표와 4개 그림을 모두 인접 본문에서 명시적으로 호출하고,
  같은 sensitivity frame을 독립 replication으로 오인하지 않도록 연결 관계를 설명한다.
- [x] endpoint hierarchy, M4/M5와 full-clinical model contents, C-index/IBS delta 방향 및
  paired-bootstrap 단위를 설명한다.
- [x] 생성 표와 그림에서 `marker7`, snake-case evidence state, raw contrast ID를 제거하고
  publication-facing 용어로 표시한다.
- [x] 반복 bootstrap accounting을 분자/분모가 보존되는 축약 형식으로 바꾸고 열 폭을
  조정하여 표 overflow와 불필요한 줄바꿈을 줄인다.
- [x] 자동 검사에 모든 label callout, 핵심 caption 정의, 내부 코드 비노출 회귀 contract를
  추가한다.

**Gate 14:** 모든 figure/table은 제목, 단위·metric, uncertainty 또는 delta 방향,
해석 경계를 caption이나 인접 callout만으로 복원할 수 있어야 한다. PDF에는 unresolved
reference와 overfull box가 없어야 하며 Main은 20쪽 이하여야 한다.

Gate 14는 source 19개·numeric mapping 33개 검증, QFM 원고 contract 포함 89/89 tests,
file-governance PASS, Main 20쪽·Supplementary 13쪽 build, unresolved reference와 overfull
box 0건 및 전체 figure/table page 시각 점검으로 통과했다. Repository boundary validator의
유일한 실패는 본 작업과 무관한 기존 top-level `webportal-refactoring.md` 미등록 항목이다.

## Task 15. Abstract--Table 1 six-axis claim parity

- [x] Table 1의 결합된 `Grade and phenotype` 행을 Grade/ISUP와 tumor phenotype/content로
  분리하여 여섯 축을 모두 독립 표시한다.
- [x] 두 morphology 축의 transportable state는 유지하되 Grade의 internal exploratory
  locked-head sensitivity와 phenotype의 same-cohort truth block을 분리한다.
- [x] Abstract에서 PTEN recoverability와 AR positive pooled alignment를 구분하고 각각의
  conditional limitation을 Table 1과 같은 수준으로 기술한다.
- [x] Abstract에서 SPOP의 unqualified direction, recurrence의 input-erasure 비적용,
  phenotype block과 PTEN·AR feasible-but-not-tested 상태를 모두 명시한다.
- [x] Abstract--Table 1 parity를 회귀검사로 고정하고 Main page budget과 시각 배치를
  재검증한다.

**Gate 15:** Abstract와 Table 1은 동일한 여섯 축, evidence state, permitted interpretation,
functional-use boundary를 사용해야 하며, 요약 문장이 Table 1보다 강한 주장을 해서는 안 된다.

Gate 15는 Abstract--Table 1 parity contract를 포함한 QFM 89/89 tests, Main 20쪽 build,
unresolved reference·overfull box 0건 및 Abstract/Table 1 페이지 시각 점검으로 통과했다.

## Task 16. Cross-disciplinary clinical and statistical primer

- [x] 이전 PBV 원고의 clinical/analytical orientation을 검토하고, 여섯 전립선암 축을
  morphology, molecular biology, post-treatment outcome으로 구분한다.
- [x] Grade/ISUP, tumor phenotype/content, PTEN loss, SPOP mutation, AR activity와 recurrence의
  정의, label type, 임상 reference와 오해하기 쉬운 경계를 Introduction 첫머리 표에 둔다.
- [x] Spearman $\rho$, AUROC, C-index, IBS, $R^2$, confidence interval의 읽는 법과 각 null을
  AI 독자가 결과 전에 확인할 수 있도록 Introduction과 Methods에 설명한다.
- [x] frozen encoder, tile, embedding, probe, transfer without refitting, patient-disjoint fold와
  patient bootstrap을 비병리 독자에게 평이하게 설명한다.
- [x] Abstract의 약어를 첫 사용에서 풀고 Results 첫 문단이 clinical primer를 명시적으로
  참조하도록 한다.
- [x] Figure 1의 결합 morphology 행을 Grade/ISUP와 phenotype으로 분리하고 functional-use
  상태를 IE, BL, NR, NQ, NA로 구별하여 Table 1의 여섯 축과 맞춘다.
- [x] source hash와 수치는 변경하지 않고 Main 20쪽 제한, caption 가독성 및 자동 contract를
  재검증한다.

**Gate 16:** 병리 배경이 없는 AI 독자가 각 지표가 무엇인지, 왜 서로 교환할 수 없는지,
어떤 metric과 null로 읽는지, representation recoverability와 downstream functional use가 왜
다른지를 Results 전에 이해할 수 있어야 한다. Abstract, Table 1, Figure 1은 같은 여섯 축과
기능 검증 상태를 사용해야 한다.

Gate 16은 immutable source 19개·numeric mapping 33개 검증, QFM 89/89 tests,
file-governance PASS, Main 20쪽 build, unresolved reference·overfull box 0건 및 임상 프라이머,
통계 프라이머, Figure 1 페이지 시각 점검으로 통과했다.

## Task 17. Six-axis comparative narrative restoration before compression

- [x] Abstract, Introduction, Results, Discussion, Conclusion과 Methods에서 ISUP-first 문장과
  section order를 감사한다.
- [x] 모든 핵심 요약은 Grade/ISUP, phenotype/content, PTEN, AR, SPOP, recurrence의 비교
  hierarchy를 먼저 제시하고 ISUP은 가장 완전한 evidence chain으로 두 번째에 강조한다.
- [x] Results를 morphology → molecular → outcome → representation/setting sensitivity →
  secondary ISUP functional extension → final synthesis 순으로 재배치한다.
- [x] 20쪽 page-budget contract를 임시 해제하고 압축 전 readable scientific draft를 만든다.
- [x] outcome comparison, six-axis representation sensitivity와 matched setting contrast를
  Main Figures 4--6으로 복귀시켜 모든 target family의 시각적 근거 비중을 회복한다.
- [x] Table 1과 Introduction orientation table의 글자 크기 및 Main 여백을 읽기 쉬운 상태로
  복원한다.
- [x] Discussion과 Conclusion은 single-target result가 아니라 six-axis target-specific
  hierarchy를 primary conclusion으로 선언하고 지표별 functional-testing status를 설명한다.
- [x] 자동 contract에 Results 순서, Main figure 복귀, uncapped build와 `ISUP is not the sole
  organizing target` 경계를 추가한다.

**Gate 17:** 원고의 어느 핵심 section에서도 ISUP이 연구 전체의 단일 중심 지표로 제시되지
않아야 한다. 여섯 축의 evidence state가 먼저 비교되고, ISUP은 그중 functional-use test까지
진행된 가장 발전된 사례로만 강조되어야 한다. 현 단계는 페이지 수보다 과학적 완전성·가독성을
우선하며, 제출용 재축약은 별도 후속 task로 수행한다.

Gate 17은 immutable source 19개·numeric mapping 33개 build, six-axis portfolio contract를
포함한 QFM 90/90 tests, file-governance PASS, Main 23쪽·Supplementary 11쪽 build,
unresolved reference·overfull box 0건 및 Main Figures 2--7 페이지 시각 점검으로 통과했다.
PBV 원본 회귀검사 323개 중 1개는 이번 QFM 변경과 무관한 기존 Funding 선언문--테스트 기대
문구 불일치로 실패했으며 PBV source는 수정하지 않았다. Repository boundary validator의
유일한 실패도 기존 미등록 top-level `webportal-refactoring.md`이다.

## Task 18. Scientific Reports abstract compression

- [x] Abstract의 detex 기준 단어 수를 측정한다.
- [x] Scientific Reports의 200단어 이하 기준에 맞춰 195단어로 축약한다.
- [x] 여섯 target과 target-specific hierarchy를 모두 보존한다.
- [x] ISUP을 most-developed functional example로 유지하되 sole organizing target이 아님을
  명시한다.
- [x] 지표별 미수행 사유와 detector/residual 세부사항은 Main Table 1, Results와 Discussion에
  보존한다.
- [x] evidence map의 활용을 agreement/disagreement audit, 설명 보류 경계, 다음 검증
  우선순위의 세 가지로 명시한다.
- [x] 200-word ceiling을 자동 원고 contract에 추가하고 PDF를 재생성한다.

**Gate 18:** Abstract는 비구조화 형식과 six-axis primary narrative를 유지하면서 detex 기준
200단어 이하여야 하며, 본문의 claim보다 강한 결론을 제시해서는 안 된다.

Gate 18은 Abstract 195단어, immutable source 19개·numeric mapping 33개 build와 QFM 90/90
tests로 통과했다.

## Task 19. Abstract--Introduction--Conclusion operational-claim parity

- [x] Introduction의 contribution을 conceptual, empirical, operational, functional의 네
  기여로 재구성한다.
- [x] actionable audit vocabulary를 독립 기여로 명시한다.
- [x] transported coordinate의 agreement/disagreement review, conditional/unsupported
  explanation withholding, evidence-gap-driven validation prioritization을 Abstract,
  Introduction과 Conclusion에 같은 수준으로 기술한다.
- [x] 활용 범위는 model audit, communication과 study design이며 clinical outcome 개선은
  미평가라는 경계를 세 section에 유지한다.
- [x] 세 section의 operational-claim parity를 자동 검사로 고정하고 PDF를 재생성한다.

**Gate 19:** 발견의 활용점은 Abstract에만 머물지 않고 Introduction의 명시적 contribution과
Conclusion의 최종 take-home message에 반복되어야 한다. 세 section 모두 같은 세 가지 audit
action과 clinical-use 미평가 경계를 사용해야 한다.

Gate 19는 immutable source 19개·numeric mapping 33개 build와 QFM 90/90 tests로 통과했다.

## Task 20. Paired-reference availability and evaluability boundary

- [x] Introduction에서 slide는 model input이며 각 estimate는 paired target reference와
  비교했다는 설계를 명시한다.
- [x] Clinical primer에 target별 reference source와 external/functional availability 열을
  추가한다.
- [x] Grade/phenotype의 broader external coverage, TCGA-confined molecular reference,
  non-equivalent recurrence endpoint를 구분한다.
- [x] `not evaluated/blocked`는 missing prerequisite이고 `unsupported`는 available-reference
  comparison에서 signal이 qualified되지 않은 상태로 정의한다.
- [x] SPOP의 unsupported state가 target-label 부재 때문이 아님을 명시한다.
- [x] Results, Discussion과 Conclusion에 동일한 reading rule을 반복한다.
- [x] 표 가독성, reference-boundary regression contract와 PDF를 검증한다.

**Gate 20:** 독자는 약한/없는 결과를 `슬라이드밖에 없어서 생긴 non-alignment`로 해석하지
않아야 한다. 각 estimate의 paired reference 존재 여부와 외부·기능 reference의 미충족이
분리되어야 하며, missing evidence와 negative evidence가 같은 범주로 표시되어서는 안 된다.

Gate 20은 immutable source 19개·numeric mapping 33개 build, QFM 91/91 tests, Main primer
page 시각 점검과 unresolved reference·overfull box 0건으로 통과했다.

## Task 21. Introduction compression and Supplementary S1 relocation

- [x] Introduction을 약 2,047단어에서 1,065단어로 줄여 PDF 기준 약 2쪽 분량으로 만든다.
- [x] calibrated reliance, recoverability--reproducibility--functional-use evidence order,
  six-axis non-interchangeability, paired-reference availability와 missing-versus-unsupported
  경계를 유지한다.
- [x] `Position of this study`와 네 가지 contribution을 보존하고 ISUP은 secondary internal
  functional-sensitivity example이며 sole organizing target이 아님을 명시한다.
- [x] clinical-target/reference/metric primer와 study-resource orientation 표를
  Supplementary S1으로 이동하고 Main Results에서 새 위치를 호출한다.
- [x] AUROC threshold, C-index calibration, patient-bootstrap unit와 interval-null의
  평이한 해석을 Methods에 보존한다.
- [x] Supplementary 표 순서를 고정하고 PDF에서 열 폭, 줄바꿈과 section/table 순서를
  시각적으로 확인한다.
- [x] 서론 1,200단어 ceiling, Main Introduction table 부재, Supplementary table callout과
  statistical-reader boundary를 자동 contract로 고정한다.

**Gate 21:** Introduction은 논문의 필요성, six-axis position, reference-availability 경계와
기여를 독립적으로 전달하되 상세 registry 역할을 겸하지 않아야 한다. 이동된 설명은
Supplementary S1과 Methods에서 손실 없이 복원되어야 한다.

Gate 21은 Introduction 1,065단어·약 2쪽, immutable source 19개·numeric mapping 33개 build,
QFM 91/91 tests, Main 22쪽·Supplementary 13쪽 build, unresolved reference·citation 및
overfull box 0건, Main Introduction과 Supplementary S1 첫 4쪽 시각 점검으로 통과했다.
Main 20쪽 제한은 Task 17의 six-axis evidence 복귀 결정에 따라 현재 비활성 상태이며,
제출용 재축약은 별도 후속 task로 수행한다.

## Task 22. FM6 locked clean rerun and manuscript handoff gate

- [x] 기존 analysis run-config의 nonvolatile output hash를 실행 전 기준선으로 확인한다.
- [x] 저장된 paired embeddings와 고정 folds에서 FM6 분석을 설정 변경 없이 재실행한다.
- [x] FM6 figure renderer와 alignment manuscript builder를 재실행한다.
- [x] 두 encoder의 recoverability, BCR-head validity, fixed-head erasure, refit compensation,
  matched controls와 제한적 ISUP increment가 기존 수치·interval·판정과 일치하는지 확인한다.
- [x] source 19개·numeric mapping 33개, QFM tests, PDF 및 governance를 재검증한다.
- [x] 통과 결과를 milestone과 execution tracker에 기록하고 author-controlled metadata
  handoff 상태로 전환한다.

**Gate 22:** 새로운 분석 선택 없이 FM6 nonvolatile outputs와 원고의 근거가 재현되어야
한다. 불일치 시 handoff를 중단하며, 통과해도 claim ceiling은 internal exploratory
functional sensitivity를 넘지 않는다.

Gate 22는 2026-08-17 FM6 nonvolatile output hash 20/20 일치, source 19/19·numeric mapping
33/33 manuscript build, QFM tests 91/91, Main 22쪽·Supplementary 13쪽 재생성으로 통과했다.
PBV 원본 tests는 322/323이 통과했으며 유일한 실패는 현재 NRF/GNU Funding 선언문과 과거
ICT funding 기대 문구의 기존 불일치다.
다음 작업은 과학 분석 추가가 아니라 author-controlled metadata와 submission release의
확정이다.

## Task 23. FM6 clean-rerun 근거 편입과 six-axis evidence-state 종결 정합성

- [x] FM6 Methods에 frozen encoders, patient-disjoint ridge ISUP probe, locked Cox BCR head,
  ISUP-direction projection, 100 matched-random controls, refit-after-erasure와 locked
  clean-rerun 절차를 명시한다.
- [x] Results에 392명/80 events, ISUP recoverability 0.615/0.658, BCR C-index
  0.627/0.632, fixed-head 감소 0.041/0.023, 두 matched-random p=0.0099와 refit 감소
  0.014/0.010의 해석 경계를 함께 보고한다.
- [x] 20/20 nonvolatile hash 일치를 계산 재현성으로 보고하되 독립 cohort 재현으로
  승격하지 않는다.
- [x] Figure 2--6과 Table 1에서 grade/phenotype transport, PTEN/AR conditional evidence,
  SPOP unsupported, recurrence endpoint sensitivity를 직접 읽을 수 있게 한다.
- [x] PANDA phenotype은 grade-derived tumor/benign reference이지 정확한 외부
  tumor-content truth가 아님을 Main과 Supplementary에 고정한다.
- [x] SPOP은 available genomic reference로 평가한 뒤 unsupported였음을 명시하여
  `not evaluated`와 분리한다.
- [x] Abstract, Table 1, Results, Discussion, Conclusion과 Supplementary의 evidence state,
  functional-use ceiling 및 R/A/U/T 판정을 대조한다.
- [x] source 19개·numeric mapping 33개, QFM tests, PDF reference/overflow와 시각 배치를
  재검증한다.

**Gate 23:** 네 결과군의 근거 상태와 FM6 기능 민감도 결과가 원고 전 구간에서 동일해야
하며, 계산 재현성·표현 복원성·기능적 사용·외부 transport를 서로 승격해서는 안 된다.

Gate 23은 2026-08-17 source 19/19·numeric mapping 33/33 build, QFM tests 92/92,
Main 23쪽·Supplementary 13쪽 재생성, unresolved citation/reference와 overfull box 0건,
Table 1 및 Main 10--11쪽·Supplementary 6·13쪽 시각 점검으로 통과했다. 과학적 결론은
`grade/phenotype = strongest representation evidence`, `PTEN/AR = context-sensitive`,
`SPOP = evaluated but unsupported`, `recurrence = endpoint-sensitive`, `ISUP = internal
exploratory functional sensitivity only`로 고정한다. 다음 작업은 author-controlled metadata와
submission release 확정이다.

## Task 24. 2026-08-18 Scientific Reports submission-readiness closure

- [x] 공식 Scientific Reports submission guideline, initial-submission checklist와 editorial
  policy를 확인하고 200-word abstract, 8-display-item, Supplementary, declaration, ethics,
  availability와 file-package 요구를 대조했다.
- [x] Data/Code Availability를 References 앞에, Acknowledgements·Author Contributions와
  Additional Information/Competing Interests를 References 뒤에 배치하고 ethics placeholder를
  Methods 안으로 이동했다.
- [x] builder에 53개 denominator/event/unit/interval/endpoint/OOF/headline-provenance 의미
  contract와 격리 `--output-root` build를 추가했다.
- [x] 두 fresh `/tmp` root의 tables, figures와 두 PDF가 byte-identical임을 확인하고 Main
  23쪽·Supplement 13쪽 전부를 rasterize해 시각 점검했다. Figure 3 주석 겹침과
  Supplementary caption clipping을 수정했다.
- [x] `submission-handoff.md`에 counts, hashes, claim ceiling, journal checklist와 단일
  author-action checklist를 기록했다.

**Gate 24:** source 19/19, numeric mapping 33/33, semantic contracts 53/53, QFM 94/94,
file-governance/worktree/diff PASS. PBV 322/323의 기존 Funding 기대값 실패와 boundary의
기존 `webportal-refactoring.md` 실패를 무관한 pre-existing issue로 보존한다. 제출 상태는
`partial—author metadata required`이며 추가 과학 실험은 필요하지 않다.

## Task 25. 2026-08-18 submission-specific public release

- [x] 독립 공개 저장소 `AiXLab-GNU/evidence-qualified-alignment-prostate-cancer`를 기존
  research monorepo의 submodule이 아닌 별도 publication package로 구성했다.
- [x] 공개 원고는 `main.pdf`와 `supplement.pdf`만 남기고 editable TeX 및 `sections/`를
  공개 이력에서 제외했다. claim/provenance registry, 실제 figure build에 필요한 12개
  aggregate source table과 public renderer는 유지했다.
- [x] WSI, patient-level prediction, embedding, weight, cache 및 access-governed LEOPARD
  artifact를 제외했다.
- [x] standalone public-artifact builder가 source hash 12/12와 numeric mapping 33/33을
  검증하고 figure PDF 8개를 독립 환경에서 재생성함을 확인했다.
- [x] release contract test 4/4를 통과하고 추적 파일의 `.tex` 및 `sections/`가 0개임을
  원격 tag의 새 clone에서 확인했다.
- [x] 공개 `main` branch와 annotated tag `v1.0.0-submission`을 commit
  `d19cca8b4de2e3109055b644bfc724ecbe85f5a8`의 단일 clean root history로 교체하고 원격
  tag를 새 clone에서 다시 검증했다.
- [x] 리비전 실험은 `vlm-pathology`의 owning project에서 수행하고, 검증된 aggregate
  artifact와 reference PDF만 공개 저장소의 `revision/rN` branch 및 새 immutable tag로
  export하도록 README와 handoff에 기록했다.

**Gate 25:** submission-specific code/data-display release와 immutable Git identifier는
완료했다. 남은 제출 작업은 keywords, cover letter, reviewer metadata, prior-editorial-
discussion 여부, submission date 및 online-system title/abstract parity의 책임저자 확인이다.

## Task 26. 2026-08-18 reviewer reproducibility reinforcement

- [x] 공개 package의 재현 범위를 aggregate artifact reproduction, source-analysis code audit,
  original-resource-required rerun, editable manuscript rebuild의 네 수준으로 구분했다.
- [x] 12개 aggregate source의 hash 검증과 33개 publication-facing numeric mapping을 한 번의
  release test 명령으로 재실행하도록 유지했다.
- [x] 격리 output root에서 main figure 7개와 supplementary figure 1개를 재생성하고, committed
  artifact manifest와 8/8 byte-identical hash를 자동 비교하도록 강화했다.
- [x] PBV 6개와 QFM/FM6 4개 source-analysis entrypoint의 정확한 snapshot, original path,
  size, SHA-256와 reproduction role을 공개했다.
- [x] `REPRODUCIBILITY.md`, public artifact manifest, analysis-code manifest와 GitHub Actions
  workflow를 추가하고 editable manuscript source 및 restricted artifact 부재를 검사했다.
- [x] `v1.0.1-submission` commit `d7d22220cbaa50b23ead5bbc3e9a1e13e40ef79a`을 새로 clone해
  reviewer release tests 6/6과 source 12/12, numeric 33/33, figure 8/8, code snapshot 10/10을
  확인했다.

**Gate 26:** 심사자는 공개 repository만으로 공개 집계 근거와 모든 publication figure를
정확히 재현하고 원 분석 entrypoint를 감사할 수 있다. WSI, patient/fold-level artifact,
embedding, weight와 access-governed source가 필요한 end-to-end experiment는 재배포하지 않으며,
그 제한을 재현 실패나 독립 replication으로 오인하지 않도록 공개 문서에 명시한다.

## Task 27. 2026-08-18 cover letter, corresponding-author ORCID, and internal submission lock

- [x] Jin Hyun Kim의 ORCID `0000-0002-2308-1638`을 Main과 Supplementary title page에
  동일하게 반영했다.
- [x] Scientific Reports용 1-page cover letter와 editable source를 manuscript workspace에
  생성하고 연구 적합성, 핵심 bounded finding, ethics, funding, competing interests와 public
  reproducibility release를 기술했다.
- [x] 확인되지 않은 reviewer suggestion/exclusion과 prior Editorial Board discussion 여부를
  추정하지 않고 online submission에서 accountable author가 선언할 항목으로 남겼다.
- [x] ORCID가 반영된 두 PDF를 public package와 동기화하고 `v1.0.2-submission` commit
  `664a542166219e7ececec00b6219e787863a70ed`을 새 clone에서 release tests 6/6으로 검증했다.
- [x] 공개·비식별 secondary analysis의 일반 ethics 문구를 유지하되 institutional
  non-human-participant/exempt determination과 존재하는 reference number는 accountable-author
  confirmation 없이 추정하지 않는 submission gate로 명시했다.

**Gate 27:** Main 22쪽, Supplementary 12쪽, cover letter 1쪽이 정상 렌더링되고, ORCID,
release tag와 reference PDF hashes가 원고·handoff·public manifest에서 일치해야 한다. 남은
차단 항목은 institutional ethics classification 확인과 online reviewer/editorial metadata다.

## Task 28. 2026-08-18 abstract motivation restoration and release synchronization

- [x] 200-word 제한 안에서 임상의가 확인해야 할 세 질문---어떤 정량 축이 표현되는가,
  cohort·technical variation에도 유지되는가, downstream decision이 사용하는가---를 초록
  도입부에 복원했다.
- [x] 여섯 축 모두에는 recoverability와 가능한 qualification을 적용하되, functional-use
  검증은 ISUP의 두 internal locked BCR head에만 해당함을 명시했다.
- [x] clinician-understandable reliability audit을 현재 기여로, residual-signal/new-biomarker
  discovery를 알려진 좌표와 confounder를 통제한 뒤 수행할 후속 가능성으로 구분했다.
- [x] 198-word abstract, 1,100-word Introduction, source 19/19, numeric mapping 33/33,
  semantic contracts 53/53과 manuscript contract tests 15/15를 확인했다.
- [x] 새 `main.pdf`를 공개 package에 반영하고 annotated tag `v1.0.3-submission`, commit
  `5c859a27467e7aecc8d9c624e5da06fff8d08c1a`을 fresh clone에서 release tests 6/6으로 검증했다.

**Gate 28:** 동기, 중요성, 지표별 evidence hierarchy와 claim ceiling이 198-word abstract와
Introduction에서 일치한다. 이 연구는 새 바이오마커를 발견했다고 주장하지 않으며,
functional use의 직접 검증 범위를 ISUP internal locked-head sensitivity 이상으로 확장하지 않는다.

## Task 29. 2026-08-18 Introduction/Conclusion motivation and discovery-space clarification

- [x] Introduction 앞부분에 prostate-cancer AI가 어떤 정량 축을 표현하는지, cohort·technical
  variation에도 유지되는지, downstream decision이 사용하는지를 지표별로 묻는 연구 동기를
  독립 문단으로 명시했다.
- [x] Conclusion에서 같은 세 질문을 다시 제시하고, 첫 두 질문은 여섯 축 비교로 다루되
  functional-use 질문은 internal ISUP example에만 한정됨을 명시했다.
- [x] 알려진 임상 좌표와 technical confounder를 분리한 뒤 남는 reproducible,
  decision-linked signal을 검증하는 것이 잠재적 새 바이오마커 탐색의 출발점임을 설명했다.
- [x] 새 바이오마커 발견은 현재 결과가 아니며 external replication, locked-head contribution,
  human-measurable feature와 biological/clinical validation이 필요한 후속 연구로 유지했다.
- [x] 198-word Abstract, 1,173-word Introduction, 747-word Conclusion과 manuscript contract
  tests 15/15를 확인하고 public tag `v1.0.4-submission`, commit
  `9dc1e137ab92e369cd2d29382602be41c198d2d5`에 새 `main.pdf`를 게시했다.

**Gate 29:** Abstract, Introduction과 Conclusion이 동일한 motivation, evidence-stage boundary,
clinical-audit significance와 bounded discovery-space claim을 사용한다.

## 완료 판정

본 plan은 main만 문장 수정하거나 Supplementary를 제목만 바꾼 상태에서는 완료가 아니다.
두 문서가 같은 alignment 정의, source manifest, claim matrix, endpoint registry와 numeric QA
contract로 새로 빌드되어야 완료다.
