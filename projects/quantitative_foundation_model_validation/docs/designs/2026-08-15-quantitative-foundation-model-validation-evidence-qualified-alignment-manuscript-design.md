---
document_id: 2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: approved
created: 2026-08-15
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer
verification:
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python -m unittest discover -s projects/quantitative_foundation_model_validation/tests -p 'test_*.py' -v
  - .venv/bin/python -m unittest discover -s projects/prostate_biomarker_validation/tests -p 'test_*.py' -v
---

# Evidence-qualified alignment manuscript redesign

## 1. 결정과 목적

본 설계는 `projects/prostate_biomarker_validation/paper/`의 frozen 분석과 claim lineage를
보존하면서, 그 과학적 메시지를 다음 질문 중심으로 재구성하는 QFM 소유의 신규 원고
작업공간을 정의한다.

> 전립선암의 형태학적·분자적·임상 outcome 축이 frozen pathology foundation-model
> representation에서 얼마나 복원되며, 그 alignment가 cohort, 임상 교란, 기관, encoder,
> 물리 scale, sampling 및 endpoint 변화에도 유지되는가?

작업 제목은 다음으로 고정한다.

> **Evidence-Qualified Alignment of Pathology Foundation Models with Morphologic,
> Molecular, and Outcome Axes in Prostate Cancer**

폴더 slug는 `evidence-qualified-alignment-prostate-cancer`다. 기존 원고를 이동하거나
편의상 복제하지 않는다. 원본 bundle은 `prostate_biomarker_validation`의 역사적·재현성
계약으로 남기고, 신규 QFM 원고에는 승인된 근거만 hash-locked manifest를 통해 승계한다.

## 2. 핵심 기여의 재정의

현재 원고의 `signal qualification framework`는 중요한 방법이지만 독자가 기억할 중심
과학 질문으로는 추상적이다. 신규 원고에서는 기여의 위계를 다음처럼 바꾼다.

1. **과학적 기여:** 사람에게 해석 가능한 전립선암 축과 foundation-model representation
   사이의 target-specific alignment map을 제시한다.
2. **경험적 기여:** morphology-linked grade/phenotype alignment는 가장 강한 transport를
   보였지만, PTEN·AR·SPOP과 recurrence alignment는 confounding, site, representation 또는
   endpoint에 조건적임을 보인다.
3. **방법론적 기여:** 단일 pooled AUROC/상관계수로 alignment를 선언하지 않고 transport,
   conditional increment, site, encoder/scale/sampling, endpoint fidelity를 함께 적용하는
   `evidence-qualified alignment` 절차를 제시한다.
4. **운영적 기여:** 모든 문장·수치·그림을 source row와 hash에 연결해 alignment의 범위와
   미해결 축을 재현 가능하게 보고한다.
5. **제한적 기능 기여:** ISUP에 한해 두 internal BCR head가 ISUP-correlated subspace의
   targeted erasure에 민감한지를 동일한 규칙과 matched-random control로 시험하고, 고정된
   head와 direction을 site-heldout, LEOPARD, CHIMERA에 적용한다. CHIMERA에서는 Virchow만
   사전지정 external whole-tissue functional-transport gate를 통과했다. 이는 encoder-specific
   transport이며 필수적 사용, human-equivalent mechanism, tumor-specific mechanism, encoder
   우월성 또는 임상 증분의 확립을 뜻하지 않는다.

Qualification은 논문의 최상위 질문이 아니라 alignment를 과장 없이 판정하는 검증
방법으로 배치한다.

원고 전체를 관통하는 최종 기조는 다음으로 승인한다.

> 사람과 AI가 공유하는 정량적 병리 지표는 AI 판단 전체를 완전히 설명하지는
> 않지만, AI 표현과 과제 신호를 임상적으로 해석·검증하는 공통 설명 좌표를
> 제공한다. 본 연구는 기존 내부·외부 cohort에서 이러한 지표의 복원 정확성과
> 재현성을 검증해 해석 좌표로서의 가능성과 적용 한계를 구분한다.

이 원고에서 `AI 판단` 표현을 쓰는 경우에는 frozen representation 위에서 학습된
과제 특이 probe의 출력임을 반드시 밝힌다. 복원 정확성과 외부 재현성은 지표가
representation에 존재하는지를 검증하지만, disease-prediction head가 그 지표를 실제로
사용했는지를 검증하지는 않는다.

## 3. Alignment의 조작적 정의

### 3.1 Representation–target alignment

Encoder (e), target (t)에 대해 alignment는 frozen representation에서 학습된 고정
규칙의 out-of-fold 또는 사전 고정 external probe score와 target 사이의 환자 단위
association/discrimination으로 정의한다.

- ordinal/continuous target: patient-level Spearman correlation 또는 사전 지정 연속형
  held-out measure
- binary target: patient-level AUROC
- time-to-event target: endpoint별 patient-level concordance와 사전 지정 paired increment

이는 `representation에 target 관련 정보가 복원 가능하다`는 뜻이다. Foundation model이
해당 정보를 자신의 원래 판단에 기능적으로 사용한다는 뜻은 아니다.

### 3.2 Evidence-qualified alignment

단일 alignment score를 새로운 합성척도로 만들지 않는다. 각 target은 다음 evidence
vector로 보고한다.

1. frozen-primary recoverability
2. cross-cohort transport without target-cohort refitting
3. grade/clinical covariate beyond-target increment
4. site uncertainty와 acquisition confounding
5. CONCH/Virchow, physical scale, tile budget와 seed sensitivity
6. endpoint fidelity와 paired outcome increment

이 벡터에서 사용 가능한 축만으로 `transportable`, `context-sensitive`, `unsupported in
the frozen design` 상태를 부여하고, 평가하지 못한 축은 `not evaluated`로 보존한다.

### 3.3 Target taxonomy

| Alignment 층 | Target | 해석 |
|---|---|---|
| Morphologic | Gleason/ISUP grade, evaluated tumor phenotype/content | routine H&E에서 직접 표현되는 임상·병리 축 |
| Molecular | PTEN loss, SPOP mutation, AR activity | H&E representation과 분자 label의 association; 직접 분자진단 주장이 아님 |
| Outcome | reconstructed recurrence, official PFI 및 등록된 sensitivity endpoints | endpoint별 탐색적 risk alignment; endpoint equivalence 주장이 아님 |

PTEN·SPOP 같은 binary label과 recurrence outcome을 모두 “사람의 정량지표”라고 부르지
않는다. 상위 용어는 `clinically interpretable morphologic, molecular, and outcome axes`,
probe 출력은 `AI-derived quantitative signal`로 통일한다.

## 4. Claim hierarchy

### 4.1 Primary claims

1. Morphology-linked grade와 phenotype은 가용한 외부 비교에서 가장 넓은 alignment
   transport 근거를 가진다.
2. Molecular alignment는 target마다 다르며 pooled detectability가 grade-independent
   information 또는 site transport를 자동으로 의미하지 않는다.
3. Recurrence alignment는 endpoint, covariate hierarchy, encoder와 physical scale에
   조건적이며 현재 근거에서 robust independent prognostic utility로 승격되지 않는다.
4. Evidence-qualified alignment map은 어떤 target이 다음 독립 검증으로 진행할 수 있고
   어떤 축이 미해결인지 한눈에 보여 준다.
5. CONCH와 Virchow의 internal BCR head 모두에서 ISUP-correlated direction의 fixed-head
   erasure effect가 matched-random control보다 컸다. 외부 결과는 model-specific했다:
   LEOPARD에서는 어느 encoder도 통과하지 못했지만 CHIMERA에서는 Virchow만 사전지정
   whole-tissue functional-transport gate를 통과했다. Refit 후 effect와 제한적 ISUP-only
   비교는 indispensable use 또는 clinical-increment 주장을 확립하지 못했다.

### 4.2 Supporting claims

- CONCH와 Virchow의 차이는 보편적 encoder 순위가 아니라 target/scale-dependent
  representation sensitivity다.
- 360 grid cells는 correlated sensitivity audit이며 독립 replication 수가 아니다.
- source-linked qualification은 computational reproducibility를 제공하지만 external 또는
  clinical validity를 대신하지 않는다.

### 4.3 금지되는 주장

신규 원고는 다음을 주장하지 않는다.

- grade 이외 지표의 functional use, 또는 grade가 human-equivalent mechanism으로 반드시
  사용된다는 강한 functional-use/mechanistic alignment
- 복수 사람 지표가 representation 또는 질병판단을 완전하게 설명한다는 completeness
- known target 제거 후 residual이 신규 marker라는 주장
- probe score가 foundation model이 자발적으로 발견한 고유 정량 마커라는 주장
- clinical validation, treatment utility, autonomous whole-slide diagnosis
- universal CONCH/Virchow superiority, site/scanner causality 또는 endpoint equivalence

본 원고는 FM6의 whole-tissue internal ISUP targeted-erasure와 사전등록된 site/LEOPARD/
CHIMERA 외부 결과를 제한적으로 승계한다. Virchow의 CHIMERA 통과는 encoder-specific
whole-tissue transport로만 해석한다. Tumor-specific functional use, completeness와 residual
marker discovery는 별도 후속 근거 사슬로 남긴다. SICAP secondary specificity 0.810은 내부 기술
근거로 수용하지만, PANDA Karolinska/Radboud sensitivity 0.562/0.679로 확인된 독립 domain
sensitivity 미해결을 main과 Supplement에 명시한다.

## 5. 프로젝트 소유권과 provenance 경계

### 5.1 원본 보존

- `projects/prostate_biomarker_validation/paper/`는 수정·이동·복제하지 않는 source
  manuscript bundle이다.
- 기존 figure/table paths, generated artifacts, claim matrix와 endpoint hierarchy의
  frozen provenance는 원래 프로젝트가 소유한다.
- 신규 QFM 작업공간은 기존 PDF나 TeX tree의 compatibility copy가 아니다.

### 5.2 근거 승계 gate

QFM 원고가 다른 프로젝트의 생성물을 암묵적으로 읽지 않도록 구현 전에 다음을 완료한다.

1. 사용할 source table, script, claim row, endpoint row와 output의 path·owner·SHA-256을
   inventory한다.
2. 각 항목을 `source reference only`, `immutable promoted evidence`, `historical manuscript
   context`, `prohibited dependency` 중 하나로 판정한다.
3. QFM claim에 필요한 immutable evidence만 명시적 cross-project source manifest로
   등록하고 양 프로젝트 claim boundary와 control documents에서 승인한다.
4. patient-level data, embeddings, folds와 local model workspace는 복사하지 않는다.
5. 소유권 승계가 승인되지 않은 claim은 새 원고에 넣지 않고 `not available`로 남긴다.

이 gate를 통과하기 전에는 새 TeX에 PBV 결과 수치를 수기로 옮기거나 기존 generated
figure를 복사하지 않는다.

## 6. Main manuscript 재편집 설계

Main과 Supplementary는 같은 claim matrix와 endpoint registry를 사용하되 독립 PDF로
빌드한다. Main은 다음 순서로 재작성한다.

1. **Title/Abstract:** alignment 질문, multi-axis design, morphology/molecular/outcome의
   서로 다른 evidence state, bounded conclusion
2. **Introduction:** 임상적으로 해석 가능한 축과 FM representation의 관계, pooled
   performance의 한계, evidence-qualified alignment의 필요성, 세 연구가설
3. **Results 1 — Alignment study map:** cohort, target, encoder, unit와 qualification axes
4. **Results 2 — Morphologic alignment:** grade/phenotype recoverability와 cross-cohort
   transport
5. **Results 3 — Molecular alignment:** PTEN, AR, SPOP의 pooled alignment와
   grade/site-conditioned narrowing
6. **Results 4 — Outcome alignment:** recurrence/official PFI와 paired clinical increment
7. **Results 5 — Representation sensitivity:** CONCH/Virchow, physical scale, tile/seed
   sensitivity; correlated audit 경계
8. **Results 6 — Internal ISUP functional sensitivity:** 두 locked BCR head의 targeted
   erasure, matched controls, refit compensation와 제한적 increment boundary
9. **Results 7 — Evidence-qualified alignment map:** target별 strongest supported state와
   unresolved axis
10. **Discussion:** principal alignment hierarchy, biological/clinical interpretation,
   qualification logic, QFM 후속 completeness/functional-use 질문, limitations
11. **Conclusion:** 공유 정량 좌표의 필요성, 이 연구가 확보한 representation 및 internal
    decision-sensitivity 수준, 미확보 clinical-use 수준을 분리해 최종 판정
12. **Methods/Declarations:** cohort·label·encoder·probe·fold·qualification·statistics·endpoint
    provenance와 availability statements

현재 uncapped scientific revision의 Main은 여섯 축의 근거 노출을 우선하여 7개 figure를
사용한다. 첫 그림은 qualification process 자체보다 `target × alignment evidence axis` map을
중심에 두고, morphology, molecular, outcome, representation sensitivity와 setting contrast를
모두 ISUP functional extension보다 먼저 제시한다. 제출용 page compression은 이 비교 구조가
검증된 뒤 별도 편집 단계에서 수행한다.

## 7. Supplementary Information 재편집 설계

Supplementary는 기존 세부 결과를 그대로 붙이는 보관소가 아니다. Main의 각 claim을
재현·반증 가능하게 만드는 순서로 전면 재편집한다.

1. cohort membership, analysis unit와 target definition
2. frozen encoder, scale, tile sampling, aggregation과 fold contracts
3. target별 alignment estimand와 null
4. complete primary estimates와 uncertainty accounting
5. external transport 세부표
6. PTEN/AR conditional increment와 confounder audits
7. site characteristics, AR/SPOP site uncertainty와 missing metadata
8. full CONCH/Virchow × scale × tile × seed grid와 paired contrasts
9. recurrence endpoint hierarchy, concordance와 paired survival increments
10. multiplicity, bootstrap undefined draws, power/underpowered rows
11. claim–evidence matrix, numeric lineage와 source hash manifest
12. reproducibility, code/data availability와 known limitations

Main의 figure/table 번호와 Supplement의 세부 근거가 양방향으로 연결되어야 한다.
Supplementary title, abstract-equivalent scope paragraph와 terminology도 새 main title 및
alignment 정의에 맞춰 함께 수정한다.

## 8. Figure·table·문장 시스템

- Figure 1: morphologic/molecular/outcome target과 evidence axes의 alignment map
- Figure 2: grade/phenotype cross-cohort alignment과 molecular primary recoverability
- Figure 3: PTEN/AR conditional increment와 AR/SPOP 전체 site 감사
- Figure 4: recurrence endpoint와 clinical-reference comparison family
- Figure 5: 여섯 target의 representation/setting sensitivity range
- Figure 6: encoder, physical scale, tile-budget의 matched contrast
- Figure 7: `임상 정량 좌표 → probe-defined AI feature → downstream judgment evidence`의
  3단 linkage map. ISUP만 locked-head intervention까지 도달하고, 다른 지표는
  representation evidence에서 끝남을 명시한다.
- Table 1: target별 evidence-qualified state, 허용 해석과 functional-use 경계
- Supplementary Tables: 여섯 축의 생물학적 의미·representation/BCR-head 근거 분리표와
  10개 primary/transport row의 완전표
- Supplementary Figure S1: 72개 configuration의 complete grid. Main Figures 5--6의 source
  table과 complete contrast summary는 Supplementary tables에서 보존한다.

Supplement에는 AR/SPOP site별 모든 행, 390개 contrast의 family × target 요약, 두
recurrence endpoint의 전체 22개 frozen/paired row와 promoted source의 missingness·bootstrap
accounting 상태를 표로 노출한다. complete raw/adjusted p-value table이 promoted evidence에
없는 경우 prose에서 재구성하지 않고 그 한계를 명시한다.

모든 그림과 표는 QFM 원고용 source manifest에 등록된 immutable table에서 새로 생성한다.
PBV generated PDF/PNG를 복사하지 않는다. Main의 모든 핵심 수치는 `claim_id`, source row,
field와 display format을 가진 numeric QA mapping에 연결한다.

## 9. QFM 프로그램과의 연결

본 원고가 답하는 범위는 `known-target recoverability, transport, qualification`과 ISUP에
대한 `internal whole-tissue functional sensitivity`까지다.
QFM 장기 연구는 이 결과를 다음처럼 확장한다.

```text
Known-target alignment and transport
    → scoped internal and encoder-specific external ISUP functional sensitivity (current paper)
    → multi-metric conditional uniqueness, joint completeness, multi-domain functional transport
    → cross-model/external residual (follow-up paper)
    → explicit new quantitative marker validation
```

신규 원고는 첫 층과 제한적인 internal 및 encoder-specific external bridge만 정리한다. 추가 AI feature/residual의
정량 marker 전환은 흥미로운 별도 발견 질문이므로 현재 원고에 넣지 않는다.

## 10. 완료 조건

설계 구현 완료는 다음을 모두 요구한다.

1. 원본 PBV paper tree와 frozen inputs의 hash가 변하지 않는다.
2. QFM source-evidence manifest에 모든 사용 claim·endpoint·numeric field가 등록된다.
3. Main과 Supplementary가 새 title·alignment 정의·claim hierarchy로 모두 재작성된다.
4. `alignment`, `recoverability`, `transport`, `functional use`, `completeness`와 `residual`이
   서로 바뀌어 사용되지 않는다.
5. 모든 figure/table/prose number가 source row에서 재생성되고 numeric mismatch가 0이다.
6. 두 PDF가 독립적으로 두 번 빌드되고 unresolved reference/citation이 0이다.
7. prohibited claim scan, secret/path scan, figure lineage와 endpoint audit가 통과한다.
8. QFM·PBV owning-project tests와 repository governance audit가 통과한다.
9. 남은 저자·funding·ethics 정보는 author action으로 분리하고 추정하지 않는다.

## 11. 승인 gate

본 문서는 2026-08-15 연구책임자의 명시적 원고 재편집 요청으로 승인되었다.

- QFM이 신규 alignment manuscript의 claim owner가 되는 것
- PBV evidence의 명시적 cross-project 승계 범위
- working title과 alignment 조작적 정의
- 저널 target·저자·funding·ethics metadata는 저자 확인 전까지 미정으로 남긴다.
- 기존 main 결과는 지표 복원 정확성, 외부 재현성, 조건부 축소와 표현·endpoint
  민감도를 보여 주는 순서로 전면 재배치한다.

승인은 PBV 원본을 삭제·이동하거나 기존 frozen science를 재명명하는 승인이 아니다.

## 12. 변경 기록

- 2026-08-15: 연구책임자가 QFM 소유 alignment 원고 재편집과 main·Supplementary
  전체 구성 변경을 승인했다. 핵심 주장을 `지표 복원 정확성·외부 재현성을 통한
  공통 설명 좌표의 가능성과 한계` 규명으로 고정했다.
- 2026-08-16: 교차전공 독자를 위한 editorial layer를 승인했다. 기존 PBV의 study-resource
  table과 clinical/analytical orientation을 복원하고, 각 Results block을 `Alignment
  question → Analysis frame → Evidence test → Interpretive boundary → Qualification rule`로
  통일한다. 이 반복 구조는 alignment 근거를 읽는 문법이며 qualification framework 자체를
  다시 주 기여로 올리지 않는다.
- 2026-08-16: Methods는 PBV의 cohort, label, encoder, probe, fold, multiplicity, confounder,
  site, stability, recurrence, bootstrap와 provenance 절차를 실질적으로 그대로 승계한다.
  다만 AI 독자를 위해 ridge/logistic regression, AUROC/Spearman/C-index, nested out-of-fold,
  permutation, FDR, bootstrap, Cox/PCA/IBS의 목적과 해석을 평이하게 보강하고, 첫머리에
  recoverability가 functional use가 아니라는 alignment interpretation contract를 둔다.
- 2026-08-16: Data Availability, Funding, Ethics and consent statement는 source PBV 선언문을
  문언 변경 없이 승계한다. Code Availability는 후속 승인에 따라 개발 branch와 local-only
  workspace 대신 공개 저장소의 PBV source-code 경로와 QFM manuscript/provenance/QA 경로를
  분리해 가리킨다. 제출 전 submission-specific release tag, immutable commit과 DOI 확정은
  blocking item으로 둔다. Author Contributions와 Competing Interests의 미확정 경고도 보존한다.
- 2026-08-16: 연구책임자의 결과 비중·다각도 근거 재감사 요청에 따라 기존 frozen source를
  새로 분석하지 않고 결과 노출을 확장한다. Main은 7개 figure와 3개 table로 primary,
  transport, conditional, site, setting-range, paired-setting 및 endpoint/comparator 축을
  분리한다. Supplement는 site, 390 contrasts, 22 outcome rows와 uncertainty accounting을
  완전하게 노출한다. 이는 claim ceiling이나 functional-use 상태를 변경하지 않는다.
- 2026-08-16: 연구책임자가 remediated SICAP specificity 0.810을 secondary internal evidence로
  수용하되 independent-domain sensitivity 미해결을 명시하도록 결정했다. FM6 whole-tissue
  ISUP targeted-erasure 결과는 `internal exploratory functional sensitivity`로 원고에
  승계한다. refit compensation과 제한적 ISUP-only 비교는 각각 indispensability와 임상
  증분의 미확립으로 해석하며, 특히 후자는 임상 증분 부재를 결론낼 만큼 충분한 평가가
  아님을 명시한다. residual/unknown AI feature의 신규 marker화는 후속 논문으로 분리한다.
- 2026-08-16: 연구책임자 검토에 따라 Discussion 말미의 결론 문단을 독립 `Conclusion`
  section과 `sections/conclusion.tex` manuscript source로 분리했다. Conclusion은 공유 정량
  좌표의 임상적 필요성과 장점을 재진술하고, 본 연구의 도달점을 representation,
  internal decision sensitivity, clinical use의 세 층으로 명시한다.
- 2026-08-16: 연구책임자 요청에 따라 임상 지표가 어떤 operational AI feature를 통해
  지지되고 실제 AI judgment와 어디까지 연결됐는지를 비교하는 Figure 7을 추가한다.
  AI feature는 probe-defined embedding direction/score로 한정하며, localized histologic
  primitive로 해석하지 않는다. Grade/ISUP만 locked-head erasure까지 도달하고 다른 지표의
  head-use 근거는 지표별 사유를 보존한 채 미확립 상태로 둔다.
- 2026-08-16: Results의 첫 표에서 여섯 전립선암 축이 서로 다른 생물학적·임상적 층위임을
  먼저 제시하고 representation evidence와 BCR-head functional contribution을 분리한다.
  `미검증` 상태는 하나의 음성 범주가 아니라 phenotype의 same-cohort truth 부재,
  PTEN·AR의 실행 가능하지만 미수행인 후속 실험, SPOP의 recoverability 미충족,
  recurrence의 input-erasure 질문 비적용으로 세분하여 Figure 7과 Discussion에 일관되게
  기록한다.
- 2026-08-16: 연구책임자의 20쪽 Main 요청에 따라 claim-essential evidence만 Main에 남긴다.
  Main은 alignment map, morphology/primary recoverability, molecular conditional narrowing,
  human-coordinate--AI-feature linkage의 4개 그림과 evidence-qualified synthesis Table 1로
  축약한다. Complete primary table, six-axis biological-definition table,
  representation/setting sensitivity 그림과 전체
  endpoint/comparator 그림은 수치·caption·claim boundary를 보존해 Supplementary로 이동한다.
  Main Methods는 재현에 필요한 설계·fold·metric·FM6 intervention을 유지하고 상세 통계·민감도
  구현은 Supplementary에 보존한다. Main PDF는 빌드 기준 20쪽 이하여야 한다.
- 2026-08-16: 연구책임자 판단에 따라 `Evidence-qualified candidate shared coordinates`를
  Supplementary audit table이 아니라 Main의 headline synthesis Table 1로 복귀시킨다.
  중복을 피하기 위해 six-axis biological-definition table을 Supplementary S1으로 이동하며,
  Introduction의 비호환 축 설명과 Main Table 1의 최종 evidence state를 상호 보완하게 한다.
- 2026-08-16: 모든 Main·Supplementary figure와 table을 독립적으로 해석할 수 있도록
  caption과 본문 callout을 완전성 감사한다. Main qualification-map code, evidence-state
  정의, row-specific metric과 delta 방향을 명시하고, Supplementary의 12개 표와 4개 그림을
  모두 본문에서 호출한다. 생성 표에서는 `marker7`, snake-case 상태값과 내부 contrast ID를
  출판용 target·comparison 이름으로 치환하되 source CSV는 변경하지 않는다. Outcome 표는
  full-clinical 및 M4/M5 covariate 구성을 설명하고 C-index와 IBS의 positive-direction을
  명시한다. Main 20쪽 제한과 source/numeric claim ceiling은 유지한다.
- 2026-08-16: Abstract와 Main Table 1을 동일한 six-axis claim summary로 잠근다. Grade/ISUP와
  tumor phenotype/content는 representation transport 상태는 같지만 functional-use 상태가
  다르므로 별도 행으로 분리한다. Abstract도 Grade, phenotype, PTEN, AR, SPOP, recurrence의
  representation evidence와 downstream functional-use 상태를 Table 1과 같은 강도로 모두
  기술한다. 특히 `PTEN recoverable`과 `AR positive pooled alignment`를 구분하고, 실제
  locked-head functional testing은 Grade/ISUP에만 한정한다.
- 2026-08-16: 전립선암 배경이 없는 AI 독자도 원고를 독립적으로 읽을 수 있도록 기존 PBV의
  임상·분석 orientation을 확장한다. Introduction 앞부분에서 Grade/ISUP, tumor
  phenotype/content, PTEN loss, SPOP mutation, AR activity, recurrence의 임상적 의미,
  자료형, 적합 metric과 metric-specific null을 먼저 정의한다. 이어 frozen encoder, tile,
  embedding, probe, transfer without refitting, held-out fold와 patient bootstrap을 평이하게
  설명한다. Methods는 ridge/logistic probe, Spearman, AUROC, $R^2$, C-index, IBS, FDR와
  confidence interval의 목적과 한계를 설명하되 분석값과 claim ceiling은 바꾸지 않는다.
  Figure 1도 immutable PBV source의 결합 morphology 행을 presentation layer에서만 여섯 축으로
  분리하고, functional-use 상태를 completed, blocked, feasible-but-not-run,
  not-qualified, not-applicable로 구별한다.
- 2026-08-16: 연구책임자가 ISUP 중심으로 읽히는 narrative를 거부하고 원고 전체를
  `six-axis comparison first, strongest finding second` 원칙으로 재검증하도록 승인했다.
  20쪽 제한은 과학적 구조가 안정될 때까지 임시 해제한다. Results와 Methods는 morphology,
  molecular, outcome, representation/setting audit을 먼저 제시하고 ISUP targeted-erasure를
  그 뒤의 secondary functional extension으로 이동한다. 이전 page compression으로
  Supplementary에 있던 outcome comparison, six-axis representation sensitivity와 matched
  setting contrast를 Main Figures 4--6으로 복귀시킨다. Abstract, Introduction, Discussion과
  Conclusion은 여섯 지표의 상이한 evidence state를 중심 결론으로 선언하고, ISUP은 가장
  완전한 evidence chain을 가진 사례이되 sole organizing target이 아님을 명시한다.
- 2026-08-16: Scientific Reports의 200-word abstract limit에 맞춰 Abstract를 195단어로
  축약한다. 여섯 target의 이름, morphology--molecular--outcome 비교 hierarchy, ISUP의
  secondary functional extension과 claim boundary는 유지한다. 지표별 functional-test
  미수행 사유, detector limitation과 residual-marker deferral의 상세 열거는 Table 1,
  Results와 Discussion에 보존한다. 발견의 활용점은 `transported coordinate를 임상의의
  agreement/disagreement audit에 사용`, `conditional/unsupported axis에서는 설명 보류`,
  `evidence gap으로 다음 external/functional validation 우선순위 지정`의 세 단계로 명시하되
  임상 효과를 관찰한 것으로 과장하지 않는다. 자동 원고 contract가 detex 기준 200단어
  이하를 검사한다.
- 2026-08-16: Abstract에 추가한 활용 주장을 Introduction contribution과 Conclusion에도
  동일하게 잠근다. 기여는 (1) contestable shared-coordinate 개념, (2) six-axis empirical
  hierarchy, (3) actionable audit vocabulary, (4) ISUP secondary functional extension의 네
  단계로 정리한다. Audit vocabulary는 transported coordinate를 agreement/disagreement
  review에 사용하고, conditional/unsupported axis에서는 설명을 보류하며, evidence gap으로
  다음 external/functional validation을 우선순위화한다. 이는 model audit, communication과
  study design의 활용 주장이지 clinician outcome 개선을 관찰했다는 주장이 아니다.
- 2026-08-16: slide-only input와 target-reference availability를 혼동하지 않도록 핵심 reading
  rule을 추가한다. 모든 보고 estimate는 slide-derived embedding과 같은 analysis unit의
  target-specific paired reference를 비교하지만, external·same-patient functional reference의
  폭은 target마다 다르다. Missing reference는 `not evaluated/blocked`이며 non-alignment가
  아니다. `Unsupported`는 reference가 존재한 비교에서 signal이 qualified되지 않은 경우로
  한정하며 SPOP을 대표 사례로 둔다. Introduction primer에 `Paired reference and availability`
  열을 추가하고, Results·Discussion·Conclusion에 같은 경계를 반복한다.
- 2026-08-16: Scientific Reports 독자의 진입 속도와 Main narrative 집중도를 높이기 위해
  Introduction을 약 2,047단어에서 1,065단어로 축약한다. 서론에는 calibrated reliance의
  필요성, evidence-stage 구분, 여섯 축의 비호환성, paired-reference reading rule, 연구의
  position과 네 가지 contribution만 남긴다. 상세 clinical-target/reference/metric primer와
  study-resource orientation 표는 Supplementary S1으로 이동하고, AUROC, C-index,
  patient bootstrap와 interval-null 해석은 Methods에 보존한다. ISUP은 six-axis 비교의
  organizing target이 아니라 가장 완전한 functional example이라는 경계를 유지한다.
- 2026-08-17: 연구책임자 승인에 따라 원고 종결 전 FM6 whole-tissue ISUP 분석을 기존
  protocol·cohort·fold·embedding·seed·control 규칙 그대로 clean rerun한다. 이 태스크는
  근거의 재현성 감사이며 새 실험 family나 사후 최적화가 아니다. Nonvolatile output hash,
  핵심 수치 또는 R/A/U/T 판정이 달라지면 원고 handoff를 중단하고, 일치할 때만
  author-controlled metadata 단계로 전환한다.
- 2026-08-24: 책임저자는 공개된 CHIMERA-data 연구를 근거로 embargo 종료를 최종 판단하고
  사전등록된 집계 결과의 revision 원고 편입을 승인했다. 두 encoder를 함께 보고하며,
  Virchow의 통과를 encoder-specific external whole-tissue functional transport로 제한한다.
  CONCH의 low-event-precision 실패/불확정, 27-event 정밀도, endpoint 비동등성,
  whole-tissue 및 encoder-우월성 금지 경계를 동시에 유지한다.
