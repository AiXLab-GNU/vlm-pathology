# Protocol Freeze (2026-07-30)

> **목적**: `docs/04_publication_strategy.md` 실행 순서의 1단계. 아래 8개 항목을
> **confounder audit, LEOPARD, DiagSet-C, PRECISE 실험 결과를 보기 전에** 고정한다.
> 이 문서를 커밋한 시점 이후 이 문서에 없는 기준으로 마커를 포함/제외하거나 임계값을
> 바꾸면 그 사유를 반드시 §9(변경 이력)에 타임스탬프와 함께 남긴다 — 조용히 수정하지
> 않는다. 이 문서가 존재하는 유일한 이유는 "결과를 본 뒤 기준을 만들었다"는 심사자
> 반론을 사전에 차단하는 것이다.
>
> 아래 수치는 전부 이미 실행된 실험(§03 신뢰도 지도, 통계 보정 §04 항목 2)에서
> 그대로 가져온 것이며 이 문서가 새로 발명한 것이 아니다. 새로 결정이 필요했던 항목
> (§6 최소 효과크기, §7 LEOPARD pool 소속 규칙)만 이 문서에서 처음 확정한다.

## 1. 후보 마커 목록 (고정)

이 시점 기준 마커 풀은 **6개 + 경계선 후보 1개**로 고정한다. 이후 새 마커를
추가하려면(예: RB1 재검토, cBioPortal 재마이닝) 그 자체를 새로운 가설로 취급하고
별도 BH-FDR family에 넣는다 — 아래 §6의 family에 사후적으로 끼워 넣지 않는다.

| # | 마커 | 타깃 | 현재 신뢰도 등급 (§03 기준) |
|---|---|---|---|
| ① | H&E → Gleason 등급 | 연속(등급) | Externally transportable |
| ② | H&E → Phenotype(정상/암) | 이진 | Externally transportable |
| ③ | ERG 염색 → Gleason 등급 | 연속(등급) | Internally supported, externally untested |
| ④ | H&E → PTEN 소실 | 이진 | Cross-cohort replicable |
| ⑤ | H&E → SPOP 변이 | 이진 | Unsupported/null |
| ⑥ | H&E → AR 활성도 | 연속 | Context-sensitive |
| (경계) | H&E → ETV4 이상 | 이진 | 미확정(q=0.050, n=14 양성) — **qualified pool 후보에서 사전 제외**, All-candidate pool에도 넣지 않음(마커 풀의 정식 멤버가 아니므로) |

## 2. Confounder 목록 (고정)

Confounder audit(§04 실행순서 2단계)에서 통제할 변수는 다음으로 고정한다. 이후
새 confounder를 추가하려면 §9에 사유를 기록한다.

- **Gleason grade**(가장 중요 — grade-내부 permutation으로 검정, 전체 무작위화 아님)
- **기관/site**(TCGA-PRAD tissue-source-site 22개 코드, PANDA Karolinska/Radboud)
- **Scanner**(코호트 간 스캐너 차이 — 명시적 스캐너 메타데이터가 없는 경우 기관을 proxy로 사용)
- **Tile scale(mpp)**(§4 참고 — 스케일 불일치 자체가 이미 확인된 confounder)
- **공발생 분자변이**(PTEN/ERG/AR/SPOP 상호 co-occurrence — TCGA-PRAD cBioPortal 데이터로 상호 보정)
- **검체 종류**(biopsy vs resection — NADT/PANDA는 biopsy, TCGA-PRAD는 resection)

## 3. CV / Transfer 방식 정의 (고정)

용어를 다음과 같이 엄격히 구분해서 쓴다 — 이미 §03에서 실제로 이렇게 구분해 왔던 것을
용어집으로 고정:

- **Internal CV**: patient-disjoint 5-fold `GroupKFold`(단일 코호트 내부)
- **Zero-shot transfer**: 원 코호트에서 학습한 계수를 **재학습 없이** 그대로 다른
  코호트에 적용(예: NADT→PANDA 마커①②)
- **Native refit**: 대상 코호트 자체에서 다시 학습(예: PANDA 기관 간 교차검증
  Karolinska→Radboud)
- **Leave-one-site-out**: 단일 코호트 내부의 여러 기관 코드를 이용한 부분적 교차기관
  검증(TCGA-PRAD 22개 site 중 ≥20건인 6개 사이트만 사용, `MIN_SITE_SLIDES=20`) —
  진짜 별도 코호트 zero-shot transfer와 **동일시하지 않는다**(§03 §1 "주의" 문단 참고)

"External validation"이라는 표현은 zero-shot transfer 또는 진짜 별도 코호트의 native
refit에만 쓰고, leave-one-site-out에는 "부분적 기관 간 검증"이라는 표현을 쓴다.

## 4. 하이퍼파라미터 · 타일 스케일 (고정)

이미 `pilot_statistical_corrections.py`에서 13개 가설 전체에 통일 적용된 값을
그대로 고정:

- 연속 타깃: `Pipeline(StandardScaler(), RidgeCV(alphas=logspace(-2, 6, 25)))`
- 이진 타깃: `LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")`
- CV: `GroupKFold(n_splits=5)`, 그룹 = patient ID
- 부트스트랩: patient-ID 클러스터 리샘플링, 2,000회, 95% CI

타일 스케일(mpp)은 데이터셋·모델 조합별로 다음 값으로 고정(§03 §4 방법론적 발견
반영 — "권장 스케일보다 코호트 간 물리적 스케일 일치가 우선"):

| 데이터셋 | CONCH | Virchow |
|---|---|---|
| NADT-Prostate | level 2, ~0.88 μm/px | level 1(~0.44μm/px, NADT 자체 성능용) / level 3(~1.76μm/px, PANDA 전이용) 둘 다 보고 |
| PANDA | ~0.88μm/px 근사(level 1, 실제 1.8~1.95μm/px) | ~1.76~1.94μm/px(NADT를 이 스케일로 재임베딩) |
| TCGA-PRAD | AppMag 기반 동적 계산(§03 §4 해상도 버그 수정판) | 동일 |

`TISSUE_FRACTION_MIN = 0.35` (조직 타일 판정 임계값)도 전 데이터셋 공통으로 고정.

## 5. Primary Metric (고정)

- **연속 타깃(①③⑥)**: patient-level Spearman ρ를 primary, slide-level ρ는 secondary
- **이진 타깃(②④⑤)**: patient-level AUROC를 primary, slide-level AUROC는 secondary
- Patient-level을 primary로 삼는 이유: NADT pseudo-replication 문제(§project 메모리)가
  slide-level에서만 나타났던 선례 때문 — 이 프로젝트 전체의 기존 관행을 그대로 고정

## 6. 다중비교 보정 · 최소 효과크기 (고정 — 이 문서에서 새로 확정)

- **BH-FDR family**: 이 프로젝트가 실행한 모든 신규 가설 검정(현재 13개 + confounder
  audit에서 새로 생기는 grade-보정 검정)을 **하나의 family**로 묶어 BH-FDR 적용.
  외부 코호트 재현(zero-shot transfer, cross-encoder 재현)은 family에서 제외(이미
  검정된 가설의 확인이지 새 비교가 아님) — §04 통계 보정 항목의 기존 결정을 그대로 계승.
- **유의성 임계값**: q < 0.05
- **최소 효과크기(신규 확정)**: qualified pool 진입에는 q<0.05 통과 **및** patient-level
  |ρ| ≥ 0.15 (연속) 또는 AUROC ≥ 0.55 (이진) 중 하나를 만족해야 함 — 이 임계값은
  현재 마커 풀의 최약체(③⑥의 순수 pooled 값이 아니라, "이미 unsupported로 분류된
  ⑤SPOP의 null 수준(AUROC≈0.51)"과 "qualified 후보 중 가장 약한 값" 사이에 선을
  긋기 위해 설정. 이 임계값 자체가 사후적으로 조정되면 §9에 기록.

## 7. 5단계 신뢰도 등급 정의 (고정, `docs/03_experimental_results.md` §1 그대로)

1. **Externally transportable**: 원 코호트 계수를 재학습 없이 별도 기관 코호트에
   적용해도 방향·유의성 유지
2. **Cross-cohort replicable**: 별도 기관(또는 코호트 내 site 분할)에서 재학습해도
   방향 재현
3. **Internally supported, externally untested**: 내부적으로 CONCH+Virchow 교차모델
   일치·다중 assay 일치가 있으나, 동형의 독립 외부 코호트 자체가 존재하지 않음
   (exhaustive search로 확인된 경우만 이 등급 사용 가능 — 단순히 "아직 안 해봄"과 구분)
4. **Context-sensitive**: site/scale/encoder/assay 중 하나 이상에서 방향·강도가
   불안정(부호 반전 포함)
5. **Unsupported/null**: BH-FDR 통과 실패 또는 다중 독립 모델에서 일관되게 null

## 8. LEOPARD 3-pool 소속 규칙 (고정 — 이 문서에서 새로 확정, 가장 중요)

confounder audit·LEOPARD 결과를 보기 전에, 마커가 각 pool에 들어가는 **규칙**을
고정한다. 아래 규칙을 결과에 기계적으로 적용하며, 특정 마커를 pool에 넣고 싶어서
규칙을 사후에 바꾸지 않는다.

- **(1) Naïve pool**: 단일 코호트 internal CV에서 **BH-FDR 보정 없이** 나온 nominal
  p<0.05 마커 전부 → 현재 규칙 적용 시 **①②③④⑥** (⑤는 nominal에서도 null이라 애초
  제외). site-instability(⑥)나 외부코호트 부재(③) 같은 사후 정보는 이 pool 구성에
  **쓰지 않는다** — "이것만 보고 순진하게 골랐다면 무엇이 뽑혔을까"를 재현하는 것이
  이 pool의 존재 이유.
- **(2) Qualified pool**: 다음 4개 게이트를 **전부** 통과한 마커만.
  1. BH-FDR q<0.05 (§6)
  2. §6 최소 효과크기 통과
  3. Cross-encoder(Virchow) 재현 — 방향 일치, 크기가 CONCH의 절반 미만으로 떨어지지 않음
  4. **Confounder audit 통과**(2단계에서 실행 예정) — grade-내부 permutation 후에도
     신호 유지, **AND** site-instability 등급(Context-sensitive)이 아닐 것
  - 이 규칙을 현재 알려진 정보에 기계적으로 적용하면: **①②는 게이트 1-3을 이미
    통과**(grade가 타깃 자체라 게이트4는 애초 적용 대상 아님, 아래 참고). **④는
    게이트4까지 전부 통과 확정**(2026-07-31, `models/pilot_confounder_audit.py`:
    grade-only AUROC=0.607, 이미지-only 0.617, 결합 0.668, LRT p=0.010 — 이미지가
    grade로 환원되지 않는 정보를 가진다는 직접 증거, `docs/03_experimental_results.md`
    §6b) → **qualified pool 정식 확정**. **⑥은 게이트4의 site-instability 조건에서
    사전 탈락이 확정적**(§03 §3b에서 이미 부호 반전 확인) — confounder audit에서
    grade-shortcut은 아님이 확인됐지만(LRT p=0.003, grade 단독 R²≈0) 이는 site
    배제 사유와 무관하므로 qualified pool 제외 결정은 그대로 유지. **③은 게이트4가
    구조적으로 적용되지 않는다**(2026-07-31 확인 — 마커③의 타깃 자체가 Gleason
    등급이라 "grade로 보정한 뒤에도 신호가 남는가"가 순환논리가 됨, 마커①과 동일한
    이유) — 게이트3을 Virchow로 대체 충족(동형 외부 코호트가 구조적으로 존재하지
    않음이 exhaustive search로 확인됐으므로, cross-encoder 재현을 외부검증의 대체
    증거로 인정)한 상태로 **qualified pool 확정**, 단 잔존 미해결 질문(residual
    hematoxylin-architecture 가설)은 Discussion에서 정직하게 유지.
- **(3) All-candidate pool**: qualified pool + **⑤(null) + ⑥(context-sensitive)**.
  ETV4는 마커 풀 정식 멤버가 아니므로(§1) 여기에도 넣지 않는다.

## 9. 변경 이력

- 2026-07-30: 최초 작성 및 고정.
- 2026-07-31: §8에 confounder audit(게이트4) 1차 실행 결과 반영 — ④ qualified 확정,
  ⑥ 배제 유지(사유는 grade-shortcut 아님, site-instability), ③은 게이트4가
  구조적으로 적용 불가함을 확인하고 qualified로 확정. §6~§8 자체의 사전 고정된
  규칙은 변경하지 않았다 — 규칙을 결과에 기계적으로 적용한 것뿐이므로 protocol
  freeze의 취지(결과를 보기 전에 기준을 고정)를 위반하지 않는다.
- 2026-07-31(같은 날, 후속): §2 confounder audit의 나머지 두 항목(grade-내부
  permutation, TCGA 다중 assay 분자적 일치성)도 실행 완료 — LRT와 독립적인
  permutation 검정이 같은 결론으로 수렴(PTEN p=0.014, AR p=0.0025, ERG-fusion
  비승격 후보 p=0.063)했고, PTEN/ERG/AR 세 층 분자적 일치성도 실측 확인됨
  (`docs/03_experimental_results.md` §6b/§6c, `report.tex`). 이 결과들도 §6~§8의
  고정 규칙을 바꾸지 않고 결과만 채워 넣었다.
- 2026-08-03(major-revision 재분석): 기존 full-cohort LRT/고정-score permutation보다
  엄격한 nested outer/inner cross-fitting과 매 permutation probe refit(2,000회)을 추가했다.
  환자수준 held-out 증분은 PTEN ΔAUROC=+0.019 (95% CI −0.025~+0.068, refit p=0.203),
  AR ΔR²=+0.004 (−0.036~+0.042, p=0.176)로 둘 다 지지되지 않았다. 따라서 §8의 규칙을
  새 결과에 기계적으로 적용하면 **향후 qualified pool에서 PTEN을 제외**해야 한다.
  이미 prospectively frozen 상태로 실행된 LEOPARD 3-pool 결과의 구성은 사후 변경하지
  않고 역사적 분석으로 유지하되, PTEN을 더 이상 grade-independent/qualified라고
  서술하지 않는다. Marker 7은 post-hoc이므로 frozen tier 대상이 아니며, grade-only
  증분만 유지(ΔC-index=+0.062, p=0.010), full clinical+site 조정 증분은 없음. §6이
  예정했던 family를 실제로 13 marker tests+4 nested audits=17 tests로 확장해 BH-FDR을
  재계산했다(`models/revision_global_fdr_summary.csv`). 규칙 자체의 사후 변경은 없다.

---
**서명/커밋**: 이 문서를 커밋한 시점이 공식 freeze 시각이다. 커밋 해시와 시각을
`report.tex` §10에도 상호참조로 기록할 것(§04 실행순서 2단계로 넘어가기 전).
