# 지금까지의 실험 결과

> **2026-07-29 참고**: 이 문서는 실제 실측 결과의 팩트 기록이며 이 자체는 바뀌지
> 않았다. 다만 해석 프레임은 `docs/01_motivation.md`/`docs/02_approach_and_contributions.md`의
> confounder-aware qualification 재구성에 맞춰, 아래 §1 표에 **신뢰도 등급(5단계)** 열을
> 추가했다. "6개 검증된 마커"라는 예전 표현 대신 마커별로 등급이 다르다는 걸 명시한다.
> Confounder audit(grade/site 층화 통제 후에도 신호가 남는지)과 LEOPARD/DiagSet-C/PRECISE
> 실험은 아직 실행 전이며(protocol freeze 이후 착수 예정, `docs/04_publication_strategy.md`
> 참고), 그 결과가 나오면 등급이 조정될 수 있다.

전부 patient-disjoint 5-fold GroupKFold 교차검증, 실제 임상/분자 ground truth 기준
(우리 자체 proxy 아님). 데이터셋: NADT-Prostate(39명, 자체 수집 아님, TCIA 공개),
PANDA(Kaggle, Karolinska/Radboud 두 기관), TCGA-PRAD(GDC + cBioPortal
`prad_tcga_pub`), SICAPv2, PCa_Bx_3Dpathology(ITAS3D).

## 1. 마커 후보 신뢰도 지도 (5단계 분류)

| # | 마커 | 슬라이드 단위 | 환자 단위 | 외부 기관 | 교차 모델(Virchow) | **신뢰도 등급** |
|---|---|---|---|---|---|---|
| ① | H&E→Gleason 등급 | ρ=+0.312(64타일 +0.411) | ρ=+0.478 | PANDA·TCGA-PRAD 재현 | 재현(NADT lvl3 patient ρ=+0.513, CONCH 능가) | **Externally transportable** (PANDA zero-shot, 계수 고정 그대로 적용) |
| ② | H&E→Phenotype(정상/암) | AUROC=0.824 | ρ=+0.805(**최강**) | PANDA 거의 동일 | 재현(NADT lvl1 AUROC=0.776) | **Externally transportable** (PANDA zero-shot) |
| ③ | ERG 염색→Gleason 등급 | ρ=+0.366 | ρ=+0.524~0.585 | 동형 코호트 없음(탐색 완료, 실질적으로 존재 안 함) | **Virchow가 더 강함**(ρ=+0.664) | Internally supported, externally untested |
| ④ | H&E→PTEN 소실 | AUROC=0.617 | AUROC=0.632(약함) | site-split 일관됨(0.59~0.69) | 재현(AUROC=0.608), 앙상블 0.636 | Cross-cohort replicable (TCGA-PRAD 내부 leave-one-site-out) |
| ⑤ | H&E→SPOP 변이 | AUROC=0.508(**null**) | AUROC=0.519(**null**) | site-split 애매(0.57~0.65, 사이트 3개뿐, CI 안에 포함돼 null 결론 유지) | **Virchow도 null**(0.424) — null 확정 | **Unsupported/null** |
| ⑥ | H&E→AR 활성도 | ρ=+0.183(약함) | ρ=+0.195(약함) | **site-split 불안정**(-0.13~+0.27, 한 사이트는 부호 반전) | Virchow가 더 강함(ρ=+0.230) | **Context-sensitive** (site 의존성) |

**주의**: ①②의 "Externally transportable"은 NADT에서 학습한 계수를 그대로(재학습 없이)
PANDA에 적용해서 나온 결과라는 점에서 진짜 강한 증거다 — ④의 "Cross-cohort replicable"은
TCGA-PRAD 내부 사이트 분할이라 22개 병원이 섞인 하나의 코호트 안에서의 재현이지, NADT/PANDA
같은 진짜 별도 기관 코호트로의 zero-refit transport는 아니다(그런 라벨을 가진 별도 코호트가
없음). ③은 ERG 염색 이미지가 필요해 나머지와 데이터 요구사항이 다르고, 동형의 별도 코호트가
존재하지 않는다는 것을 exhaustive하게 확인했다(§6 참고) — 그래서 "내적으로 지지되지만
외부 미검증"이 정확한 표현이다. 왜 등급을 예측하는지(잔여 hematoxylin 구조 신호 가설)는
미해결이지만, Virchow 교차검증으로 "CONCH만의 우연"이라는 반론은 강하게 반박됨.

## 2. 외부 기관 검증 (PANDA, 3번째 기관 TCGA-PRAD)

- **PANDA zero-shot transfer(NADT-fitted probe, 재학습 없이 적용)**: 마커① ρ=+0.398
  (Karolinska +0.354, Radboud +0.519), 마커② AUROC=0.823(Kar 0.786, Rad 0.871) —
  NADT 자체 성능과 거의 동일 → "39명 코호트 우연"이라는 반론에 대한 가장 강한 반박.
- **PANDA 기관 간 교차검증**: 마커① K→R ρ=+0.607, R→K ρ=+0.578. 마커② K→R
  AUROC=0.907, R→K AUROC=0.630(비대칭, 원인 미조사).
- **TCGA-PRAD(세 번째 기관)**: 마커① NADT-probe ρ=+0.363, PANDA-probe ρ=+0.417
  (해상도 버그 수정 후, 아래 §4 참고). TCGA-PRAD 자체 학습 시 ρ=+0.529.

## 3. 마커 결합(Fusion) 실험

| 결합 | 방식 | 결과 |
|---|---|---|
| ①+②(다른 타깃) | 학습형(RidgeCV) | 성능 악화(ρ 0.478→0.253) |
| ①+②(다른 타깃) | 고정 50:50 z-score | 단일 마커 수준 유지(ρ=+0.471) |
| ①+③(같은 타깃, 다른 염색) | 고정 50:50 z-score | **양쪽 단독 모두 능가, ρ=+0.626(전체 최고 기록)** |
| PANDA 규모 ①+②(NN 결합기) | 학습형(10-시드 앙상블) | 시드 안정적이나 고정 평균 대비 추가 이득 없음 |
| TCGA-PRAD CONCH+Virchow ① | 고정 50:50 z-score | 양쪽 능가(0.529/0.496→0.542) |
| TCGA-PRAD CONCH+Virchow ④ | 고정 50:50 z-score | 양쪽 능가(0.617/0.608→0.636) |
| TCGA-PRAD CONCH+Virchow ⑥ | 고정 50:50 z-score | **Virchow 단독보다 하락**(0.230→0.214) |

**교훈**: 같은 타깃을 다른 채널(염색 또는 모델)로 잰 마커끼리는 결합이 이득이 크고,
다른 타깃끼리는 이득이 제한적이다. 소표본에서는 학습형 결합이 불안정하므로 고정 규칙이
안전하다. 결합 대상 중 하나가 압도적으로 강하면(⑥의 Virchow처럼) 평균이 오히려 손해다.

## 3b. 마커④⑤⑥의 부분적 기관 간 검증 (TCGA-PRAD tissue-source-site 분할, 2026-07-28)

라벨(PTEN_CNA/SPOP_MUTATION/AR_SCORE)이 TCGA-PRAD 전용이라 NADT/PANDA 같은 진짜
외부 기관 검증이 불가능했던 ④⑤⑥에, TCGA-PRAD 자체가 22개 병원이 섞인 코호트라는
점을 이용해 leave-one-site-out(20건 이상 6개 사이트 각각 held-out) 검증을
추가했다(`pilot_tcga_prad_site_split.py`, 새 데이터·GPU 불필요).

- **④ PTEN 소실**: 6개 사이트 전부 AUROC 0.587~0.686(평균 0.623) — pooled 결과(0.632)와
  거의 일치, **병원 출처가 바뀌어도 안정적** → 신뢰도 강화.
- **⑤ SPOP 변이**: 테스트 가능한 사이트 3곳뿐(EJ/YL/KK), AUROC 0.573~0.648(평균
  0.611) — pooled null 결과의 부트스트랩 95% CI [0.375, 0.651] 안에 들어오므로
  **null 결론을 뒤집을 근거는 아님**. 사이트 수가 너무 적고, 병원별 SPOP 유병률
  차이가 섞였을 교란 가능성도 배제 못 함 — 정직하게 "모순은 아니지만 확정도 아님".
- **⑥ AR 활성도**: 6개 사이트 결과가 ρ=-0.128(CH)~+0.265(KK)로 크게 흩어짐, **한
  사이트는 부호까지 반전** — 평균 0.151로 pooled(0.195)보다 약하고, **병원 출처
  의존성이 새로운 우려 사항으로 추가됨**.

## 4. 방법론적 발견 (버그·한계)

- **TCGA-PRAD 해상도 버그(2026-07-28 발견·수정)**: TCGA-PRAD의 SVS 파일에
  XResolution 태그가 없어, 기존 코드가 실제 조직 레벨 대신 ~17μm/px 비타일 썸네일을
  써왔음이 뒤늦게 발견됨. AppMag 필드 기반으로 올바른 피라미드 레벨을 선택하도록
  수정 후 마커①③④⑤⑥·ERG 융합·tumor-focus 재검증 전부 재실행. 마커①은 NADT-probe
  ρ=+0.147→+0.363, PANDA-probe ρ=+0.215→+0.417로 대폭 강해짐 — "검체 종류(생검 vs
  절제)가 신호를 약화시킨다"던 이전 설명은 과장이었고 진짜 원인은 이 버그였음이 확인됨.
- **타일 스케일 불일치가 교차 코호트 전이를 완전히 무너뜨림**: Virchow의 NADT probe를
  Virchow 자체 권장 스케일(~0.44μm/px)로 학습시켜 PANDA(피라미드가 3단계뿐이라 실사용
  가능 레벨이 ~1.8μm/px)에 적용하자 완전히 붕괴(ρ=+0.008, AUROC=0.502, 우연 수준).
  NADT를 PANDA와 스케일을 맞춘 레벨로 재임베딩하자 회복(ρ=+0.253, AUROC=0.713).
  **교훈: 파운데이션 모델의 "권장 스케일"보다 학습·시험 코호트 간 물리적 스케일 일치가
  우선한다.**
- **SPOP null 대 문헌(Schaumberg et al., AUROC=0.86) 간 격차**: "무작위 타일이 정상
  조직을 섞어 신호를 희석시켰다"는 가설을 종양-포커스 재검증으로 직접 반증(SPOP 여전히
  null). 두 독립 모델(CONCH+Virchow) 모두 null로 확인 — 격차의 진짜 원인(더 정교한
  세포 단위 큐레이션, end-to-end 학습의 표현력, 또는 그 프리프린트 자체의 소표본 과적합)
  은 미해결로 남음.
- **소표본 학습 결과 불안정성**: attention-MIL 패치 집계, TP53 변이/ETV4 이상의 "유의
  하지만 방향이 뒤집힌" 결과 등 — 해상도 버그 수정 후 재검증 결과 TP53 변이는 완전한
  null로, ETV4는 방향이 정상으로 뒤집히며 유의해짐 → "안정성 확인 전엔 신뢰하지 않는다"
  는 원칙이 사후적으로 옳았음이 확인됨.

## 5. 확인된 null / 미확정 후보 (정직하게 보고)

| 후보 | 결과 |
|---|---|
| H&E→SPOP 변이 | **null**(CONCH·Virchow 둘 다) |
| H&E→TP53 변이 | **null**(해상도 수정 후 확정, AUROC=0.454) |
| H&E→TP53 CNA 소실 | 약한 경향, 유의하지 않음(AUROC=0.546, p=0.20) |
| H&E→RB1 CNA 소실 | 약한 경향이었으나 재검증 후 null로 복귀(AUROC=0.510) |
| H&E→SPINK1 과발현 | 약한 경향, 표본 작음(양성 13명), 미확정 |
| H&E→ETV1 이상 | 경계선(p=0.07), 미확정 |
| H&E→ETV4 이상 | 유의·방향 정상(AUROC=0.664)이나 표본 작음(n=14), 미확정 |
| H&E→TMPRSS2-ERG 융합 상태 | 약함/경계선(슬라이드 AUROC=0.594 p=0.005, 환자 0.567 p=0.057) |

## 6. 관련(그러나 우리 알고리즘이 아닌) 검증

- **PCa_Bx_3Dpathology(ITAS3D)**: 원저자가 배포한 3D segmentation을 그대로 집계 —
  내강 비율(cancer_lumen_frac) vs 실제 BCR 재발, AUC=0.868 [95% CI 0.764–0.951],
  암 조직량 통제 후에도 유의(p=0.0018). 우리 알고리즘 검증이 아니라 "선 구조 붕괴가
  악성도와 연관된다"는 병리학적 가설 자체의 독립 재현.
- **SICAPv2**: CONCH zero-shot 텍스트 프롬프트(AUC 0.710/0.495) vs 원시 임베딩 linear
  probe(AUC 0.992/0.828) — 문제는 CONCH가 담은 정보 부족이 아니라 텍스트 인터페이스의
  한계였음을 확인. 생성형 배제·판별형 채택이라는 방향 전환의 근거.
- **자체 규칙 기반 알고리즘(dab_ring)**: NADT 39명 환자 단위에서 null(모든 지표
  p>0.28) — 같은 데이터에서 CONCH probe는 유의했으므로, 이 null은 데이터 부재가 아니라
  방법(규칙 기반) 자체의 한계로 귀속됨.

## 6b. Confounder audit — grade 보정 후에도 이미지 신호가 남는가 (2026-07-31, 1차 완료)

`docs/10_protocol_freeze.md`로 고정한 절차대로, (임상변수=REVIEWED_GLEASON_SUM만) vs
(이미지만) vs (임상+이미지) 비교와 nested likelihood-ratio test(H0: grade만, H1:
grade+이미지)를 마커④(PTEN)·⑥(AR)·TCGA-PRAD H&E→ERG 융합 상태(비승격 후보)에
실행했다(`models/pilot_confounder_audit.py`, TCGA-PRAD 300슬라이드, 통계 보정과
동일한 표준 프로토콜). **마커①③은 대상에서 제외**했다 — 타깃 자체가 Gleason
등급(①)이거나 ERG 염색 이미지→등급(③)이라, "grade로 보정한 뒤에도 신호가
남는가"라는 질문이 순환논리가 되기 때문.

| 후보 | 임상만(grade) | 이미지만 | 결합 | Δ(결합-임상) | LRT p |
|---|---|---|---|---|---|
| ④ PTEN 소실(AUROC) | 0.607 | 0.617 | 0.668 | +0.062 | **0.010** |
| ⑥ AR 활성도(R²) | -0.006 | +0.023 | +0.018 | +0.024 | **0.003** |
| H&E→ERG 융합(비승격, AUROC) | 0.435 | 0.551 | 0.511 | +0.076 | 0.109 |

- **④ PTEN: 통과.** grade 단독으로도 AUROC 0.607이 나오지만(PTEN 소실이 고등급과
  실제 연관됨을 반영), 결합 모델이 양쪽을 모두 능가하고(0.668) LRT가 유의(p=0.010)
  — 이미지가 grade로 환원되지 않는 정보를 담고 있다는 직접 증거. `docs/10_protocol_freeze.md`
  §8 게이트4 통과 → qualified pool 정식 확정.
- **⑥ AR: LRT는 유의(p=0.003)하지만 pool 제외 결정은 그대로.** grade 자체가 AR
  점수를 거의 설명 못 하므로(R²≈0) grade-shortcut 의심은 오히려 약해지지만, §3b에서
  이미 확인된 site-instability(부호 반전 포함)가 이와 무관하게 배제 사유로 남는다.
- **H&E→ERG 융합(비승격 후보): 불명확.** clinical-only AUROC(0.435)가 0.5 미만이라
  grade가 이 타깃을 아예 설명 못 하고, 따라서 "이미지=grade 대리"라는 의심도 성립
  안 하지만, 전체 신호가 약해 결합 모델의 추가 기여가 이 표본 크기에서 유의에
  못 미친다(p=0.109). 이미 마커 풀 정식 멤버가 아니므로 pool 구성 변경 없음.
- **명명 주의**: 이 audit의 "ERG" 라벨은 §5의 "H&E→TMPRSS2-ERG 융합 상태"와 같은
  것이며 마커③(NADT ERG 염색 이미지→Gleason 등급)이 아니다 — 혼동하지 말 것.

**Grade-내부 permutation 검정** (`models/pilot_confounder_permutation.py`, 2026-07-31):
LRT와 독립적인 비모수 검정 — REVIEWED_GLEASON_SUM 값별(6/7/8/9/10) 층 안에서만 라벨을
2,000회 섞어 null 분포를 만들고, 실제 관측값이 그 안에서 얼마나 극단적인지 확인.

| 후보 | 관측 통계량 | permutation null 평균 | one-sided p |
|---|---|---|---|
| ④ PTEN 소실(AUROC) | 0.617 | 0.536 | **0.014** |
| ⑥ AR 활성도(ρ) | +0.183 | +0.030 | **0.0025** |
| H&E→ERG 융합(비승격, AUROC) | 0.551 | 0.499 | 0.063 |

LRT(§6b)와 permutation 두 방법이 **정확히 같은 결론으로 수렴**한다 — PTEN·AR은
grade를 보존한 채 라벨만 섞은 null보다 유의하게 강하고, ERG 융합 비승격 후보는
여전히 경계선(0.05를 살짝 넘음). 서로 다른 가정(모수적 vs 비모수적)의 두 검정이
일치한다는 것 자체가 결과의 견고성을 뒷받침한다.

## 6c. TCGA 다중 assay 분자적 일치성 (2026-07-31)

`models/pilot_tcga_multiassay_concordance.py`. cBioPortal REST API로 PTEN/ERG mRNA
(RNA Seq V2 RSEM)와 PTEN RPPA 단백질 데이터를 신규 확보(AR mRNA/RPPA는 기존
캐시에 이미 있었음). 두 가지를 구분해서 본다: **(A) assay 층 자체의 일치성**(CNA/fusion
라벨이 정말 다른 분자 층과도 맞는가 — 우리 이미지 모델과 무관), **(B) 이미지 프로브
점수가 그 연속적 분자 층과 직접 상관되는가**(학습에 쓴 이진 라벨뿐 아니라 더 깊은
생물학 자체를 반영하는지, 더 엄격한 검증).

| 마커 | Assay 일치성(A) | 이미지 프로브 vs mRNA(B) | 이미지 프로브 vs RPPA(B) |
|---|---|---|---|
| PTEN(강함) | CNA↔mRNA p=7.8e-30, CNA↔RPPA p=0.001, mRNA↔RPPA ρ=+0.41(p=3e-5) | ρ=-0.145(p=0.02, 방향 일치) | ρ=-0.064(p=0.48, n=127, 비유의) |
| ERG(중간) | fusion↔mRNA p=6e-43(교과서적) | ρ=+0.065(p=0.30, 비유의) | — |
| AR(약함) | SCORE↔mRNA ρ=+0.30, SCORE↔RPPA ρ=+0.27, mRNA↔RPPA ρ=+0.34(전부 p<1e-4) | ρ=+0.198(p=0.0006) | ρ=-0.014(p=0.83, 완전 비유의) |

- **PTEN**: (A) 3개 층(CNA/mRNA/RPPA) 전부 서로 일치 — docs/04의 "강함" 사전 판단이
  실측으로 뒷받침됨. (B) 이미지 프로브는 mRNA와는 유의(방향도 옳음: 이미지가 PTEN
  소실로 예측할수록 실제 mRNA 발현이 낮음)하나 RPPA와는 비유의(표본이 작음, n=127)
  — 이미지가 단순 CNA 콜링 아티팩트가 아니라 실제 연속 생물학의 일부를 반영한다는
  근거이나, RPPA까지 확실히 잡는다고 과장하지 않는다.
- **ERG**: (A) fusion 양성/음성 간 mRNA 차이가 압도적(중앙값 6777 vs 208) — 교과서적
  생물학 재현, 좋은 sanity check. (B) 그러나 이미지 프로브 점수는 mRNA와 무관 —
  이 비승격 후보가 전반적으로 약하다는 §6b/permutation 결과와 일관됨.
- **AR**: (A) SCORE·mRNA·RPPA 세 층이 서로 유의하게 연관되긴 하나(docs/04가 이미
  "약함, RNA 기반이라 완전 독립 아님"으로 정직하게 표현한 그대로), (B) 이미지
  프로브는 mRNA와만 유의하고 RPPA와는 완전히 무관(ρ=-0.014) — 마커⑥이 이미
  site-instability로 qualified pool에서 배제된 것과 일관된 추가 근거.

## 6d. LEOPARD 생존분석: zero-shot 전이는 null, 그러나 in-cohort 신호는 실재 (2026-07-31)

508명(Radboudumc, 등록 없이 공개 S3에서 확보 — `opendataset/LEOPARD/`) 대상,
마커①②④⑥(③은 ERG 염색 이미지가 없어 LEOPARD엔 구조적으로 적용 불가) zero-shot
전이 3-pool(naive/qualified/all-candidate) 비교.

**3-pool 비교는 null**: C-index 0.334–0.481로 전부 우연 이하. 진단 결과(라벨 정렬
508건 완전 일치 재확인, alpha 0.1–50 규제 강도 무관하게 결과 불변) 버그가 아니라
**개별 마커 단변량 검정 자체가 전부 null**임을 확인: ①0.496(p=0.99), ②0.506
(p=0.92), ④0.496(p=0.85), ⑥0.525(p=0.31, 비유의). 신호 없는 공변량을 87건뿐인
이벤트 수로 다변량 결합하니 노이즈가 증폭돼 우연 이하로 나온 것.

**도메인 이동 진단**: 같은 임베딩으로 LEOPARD 자체에서 처음부터 재발을
직접 재학습(zero-shot 아님, 탐색적 진단)시키면 — PCA 4/8/16/32/64성분 전
구간에서 C-index 0.598–0.661, time-dep AUROC@5y 0.601–0.703로 **일관되게
신호 있음**(3개 다른 시드로도 안정 재현). 즉 **LEOPARD 임베딩엔 재발 신호가
실재하지만, NADT/TCGA-PRAD에서 학습한 우리 마커 probe가 그 방향을 못 잡는다** —
"신호 자체 부재"가 아니라 "전이 실패"로 확정.

**해석**: 특정 타깃(등급/phenotype/PTEN/AR)에 대해 다기관·다인코더로 재현된다고
검증된 마커라도, 하류의 독립적 임상 결과(재발) 예측까지 자동 보장되지 않는다 —
심지어 같은 임베딩 공간에 그 결과 관련 신호가 실제로 있는데도. 원래 가설
("qualified pool이 naïve/all-candidate보다 우수")보다 더 일반적이고 정직한
교훈이며, §포지셔닝의 "병리 파운데이션 모델 특유의 함정" 목록에 추가할 새 항목.

**Shortcut 재검토(관찰기간 아티팩트 가능성 직접 검정, 2026-07-31)**: 이 in-cohort
신호가 "최근 등록돼 재발할 시간이 부족했을 뿐"인 관찰기간 아티팩트가 아닌지
직접 검정했다(스캔 날짜 메타데이터는 공개 배포 과정에서 지워져 직접 대조는
불가, 간접 검정 3가지 실시). (1) censored군만 놓고 위험도-추적기간 상관은
약하고 비유의(ρ=-0.088, p=0.07). (2) 실제 재발한 87명 안에서는 위험도가
높을수록 재발까지 걸린 시간이 유의하게 짧음(ρ=-0.422, p=4.7e-05) — 아티팩트로는
설명 안 되는, 진짜 예후신호의 특징. (3) **Landmark 분석**(3년/5년 시점까지
결과가 실제로 확정된 환자만, 조기 재발 포함): 전체 C-index 0.661 대비 3년
landmark(n=348) 0.666, 5년 landmark(n=284) 0.662로 **판별력이 유지되거나
오히려 소폭 상승** — 관찰기간 부족 가설과 반대. 세 검정 모두 "진짜 신호"
쪽을 가리킴.

**Virchow 교차모델 검증(2026-07-31)**: CONCH만의 우연/과적합이 아닌지 확인하기
위해 완전히 다른 파운데이션 모델(Virchow)로 508명 독립 재임베딩(같은
MAIN_LEVEL, 224px 타일, CLS+패치평균 2560차원 — 인코더만 바꾼 깨끗한 비교).
**결과: CONCH와 거의 같은 범위로 재현**(PCA 4–64성분: C-index 0.622–0.675,
td-AUROC 0.628–0.701, 3개 시드 안정: k=8 0.615/0.625/0.648). Landmark
재검증도 통과(3y/5y C-index 0.618–0.619), censored군 상관은 CONCH보다도
더 깨끗(ρ=-0.029, p=0.56). **가장 강력한 증거: CONCH·Virchow 두 모델의
out-of-fold 위험도 점수 자체가 강하게 일치**(ρ=+0.737, p=3e-88) — 독립적으로
같은 근본 신호를 포착하고 있다는 뜻. 고정 50:50 앙상블(0.656)은 더 강한
CONCH 단독(0.661)을 못 넘음 — "한쪽이 뚜렷이 강하면 평균이 손해"라는 이
프로젝트의 기존 fusion 원칙과 일관.

**결론 (2026-07-31 확정)**: 이 발견은 이제 단일 모델의 우연이 아니라
**cross-encoder reproducible** 등급의 증거다. §신뢰도 지도의 5단계 체계와
같은 논리로, "qualification이 하류 임상결과 전이를 보장 못 한다"는 새 pitfall
주장의 신뢰도가 한 단계 격상됐다. 단, 신호의 정확한 형태학적 실체(해석)는
여전히 미해결 — 별도 과제.

**범위 제약**: (1) 공개 라벨에 임상 공변량 없음(§04 참고) — "clinical baseline
대비 incremental value"는 이 데이터로 검정 불가, 전부 공변량 없는 null 모델
대비. (2) publication embargo 있음 — 실제 투고 전 organizer 재확인 필요.
(3) in-cohort 직접 재학습은 탐색적 진단이며 qualification protocol의 정식
검증 대상 아님, 신호의 실체(해석)는 별도 과제.

**예비 해석(탐색적, 미검증, 2026-07-31)**: (1) 기존 마커 점수와의 상관 —
마커⑥(AR)이 가장 강함(ρ=+0.275, p=2.9e-10, 방향은 그럴듯하나 분산의 7.6%만
공유), 마커①(Gleason)·④(PTEN)는 오히려 약한 역방향 상관(둘 다 LEOPARD
단독으로는 null이라 잡음일 가능성 큼). 타일 수는 전 슬라이드 64로 고정돼
조직량 혼입은 아님. (2) 위험도 극단 6명의 타일을 잘라 육안 검토한 결과,
저위험 타일은 반복적으로 진한 파상형 섬유근성 기질(양성 조직 패턴), 고위험
타일은 반복적으로 옅고 성긴 저밀도 조직으로 일관됨 — "조직화된 양성 기질의
소실"이라는 그럴듯한 해석이 가능하나, 한 타일에서 비정상적 녹색조가 관찰돼
염색/스캔 아티팩트 가능성도 배제하지 않음. **n=6명·타일 18장뿐인 정성적
관찰로, 가설 생성 수준일 뿐 검증된 결론이 아님** — 병리의 판독 동반 체계적
재현이 필요한 별도 후속 과제.

재현: `models/pilot_conch_leopard_embed.py`/`pilot_virchow_leopard_embed.py`
(임베딩), `pilot_leopard_marker_scores.py`(zero-shot 마커 점수),
`pilot_leopard_survival_3pool.py`(3-pool 비교), `pilot_leopard_direct_recurrence.py`
(도메인 이동 진단, CONCH·Virchow 공용), `pilot_leopard_recurrence_tile_viz.py`
(타일 시각화). `report.tex` "LEOPARD 생존분석"·"Virchow 교차모델 검증"·
"예비 해석" 절.

## 6e. 마커⑦ 외부검증: LEOPARD 학습 재발예측 모델이 TCGA-PRAD로 zero-shot 전이됨 (2026-07-31)

**라벨 재구축**: `opendataset/TCGA-PRAD-BCR/bcr.csv`(기존, 출처 불명)를 GDC
API로 표본 대조한 결과 데이터 오류 발견(무재발 환자에게 더 짧은 추적기간을
잘못 사용) — 폐기(`bcr_UNVERIFIED_old_DO_NOT_USE.csv`로 보존)하고
`build_bcr_labels.py`로 GDC `follow_ups.disease_response`("wt-with tumor"
=재발/잔존종양, 111명 / "tf-tumor free"·"unknown"=무재발, 382명) 기준 정상
재구축(493명 유효). **한계**: LEOPARD의 PSA 기반 생화학적 재발 정의보다
거친, 임상평가 기반 정의 — 동일시하지 않음.

**Zero-shot 전이**: LEOPARD 508명 전체로 학습한 고정 PCA(8)+Cox 계수를
TCGA-PRAD 기존 임베딩(270명, 라벨 매칭)에 재학습 없이 적용.

| 검증 | C-index | td-AUROC@5y |
|---|---|---|
| LEOPARD→TCGA-PRAD zero-shot(n=270) | **0.673** | 0.636 |
| 3년 landmark(n=155) | 0.675 | — |
| 5년 landmark(n=99) | 0.647 | — |

LEOPARD 자체 in-cohort 성능(0.661)과 동등하거나 오히려 높음 — 마커①②의
PANDA zero-shot 전이와 같은 급의 **진짜 "Externally transportable" 등급
증거**. Landmark에서도 유지돼 관찰기간 아티팩트는 아님. 단, censored군
위험도-추적기간 상관이 LEOPARD보다 뚜렷이 유의(ρ=-0.282, p=3.1e-05 vs
LEOPARD p=0.07) — TCGA-PRAD의 다기관 이질성·거친 재발 정의와 관련 가능성,
원인 미확정. landmark 분석이 그럼에도 유지된다는 점으로 순수 아티팩트는
아니라고 잠정 결론. TCGA-PRAD 자체 in-cohort 재학습도 강한 신호(C-index
0.721–0.742, LEOPARD보다도 높음) — 두 코호트 모두 독립적으로 재발 관련
신호를 담고 있음을 재확인.

**해석**: §6d의 "qualification이 하류 임상결과 전이를 보장 못 한다"는
결론과 모순되지 않고 보완한다 — 다른 타깃(등급 등)에 대해 정의된 마커는
전이 안 됐지만, **재발 자체를 타깃으로 직접 학습한 마커는 완전히 다른
코호트(미국·절제표본·다기관·다른 재발 정의)로도 전이된다.** "하류 결과
자체를 타깃 삼아 qualification하면 전이 가능한 신호를 얻는다"는 이 논문
방법론의 건설적 함의. 단, 이 마커⑦는 LEOPARD 결과를 본 뒤 사후에 나온
후보라 protocol freeze 사전 고정 대상이 아니었고, outcome 정의가 코호트마다
다르다는 점을 정직하게 명시해야 함.

**Virchow 교차검증: 타일스케일 가설 기각, 인코더별 신호 방향 차이로 재해석
(2026-07-31)**. Virchow로 같은 zero-shot 검정을 반복 — 처음(TCGA-PRAD 기존
Virchow 임베딩, ~0.5μm/px)은 거의 우연(C-index=0.545). LEOPARD Virchow가
CONCH와 비교하려 일부러 ~0.97μm/px로 맞춰져 있어 ~2배 스케일 불일치를
의심(NADT→PANDA에서 이미 확인된 "Virchow는 스케일에 민감" 패턴과 동일 우려).
**TCGA-PRAD를 LEOPARD와 같은 0.97μm/px로 재임베딩해 재검정했으나 여전히
실패**(C-index=0.533, landmark 0.548/0.509) — **타일스케일 가설 기각.**
그런데 같은 스케일매칭 임베딩으로 TCGA-PRAD 자체 in-cohort 재학습을 해보면
**오히려 매우 강한 신호**(C-index 0.661–0.795, CONCH의 in-cohort 성능
0.721–0.742보다도 높음) — Virchow 임베딩 자체엔 두 코호트 모두 신호가
풍부하나, **LEOPARD에서 학습한 특정 방향이 TCGA-PRAD로 zero-shot 전이만
안 되는 것**. §포지셔닝이 이미 마커①②④⑥ 전반에서 확인한 "인코더마다 신호
방향/강도가 다르다"는 pitfall의 새 사례로 해석 — CONCH 결과가 "아무
임베딩이나 되는 일"이 아니라는 걸 오히려 뒷받침하는 정직한 반례.

재현: `opendataset/TCGA-PRAD-BCR/build_bcr_labels.py`(라벨),
`models/pilot_tcga_prad_recurrence_external.py`(CONCH 검증),
`models/pilot_tcga_prad_recurrence_external_virchow.py`(Virchow 검증, 스케일불일치),
`models/pilot_virchow_tcga_prad_recurrence_scalematch.py`(스케일매칭 재임베딩).
`report.tex` "마커⑦ 외부검증"·"Virchow 교차검증" 절.

**마커⑦ confounder audit(2026-07-31)**: 마커④⑥과 달리 사후 발견 후보라 grade-독립성
감사가 없었음 — TCGA-PRAD(270명)에서 Cox 버전으로 보완(`pilot_marker7_confounder_audit.py`).
(임상=grade) C-index 0.680 vs (결합=grade+marker7) **0.732**로 실질 상승, LRT
χ²=10.696(p=0.0011), grade-내부 permutation(2,000회)도 독립 재확인(p=0.0015).
**마커⑦은 grade의 그림자가 아니라 독립적 정보를 담음** — 마커④가 통과한 것과 같은
관문 통과. 단, protocol freeze 이후 사후 발견이라는 한계 자체는 남음. `report.tex`
"마커⑦ confounder audit" 절.

## 6f. PRECISE 공간적 face-validity: 마커① 실제 Gleason과 강한 외부검증 (2026-07-31)

PRECISE(25명/27세션, H&E-IHC 짝, Zenodo DOI 10.5281/zenodo.20721779, 등록 불필요)로
마커①②의 공간적 face-validity 검증. 7개 클래스 중 cribriform 라벨은 없어
cribriform 위치 특정에는 못 씀.

**설계 수정**: 1차(표준 CONCH 스케일 ~0.88μm/px, 창 ~394μm)는 PRECISE 주석이
매우 작고 희소해(예: sub-19 이미지 전체의 Tumor 0.94%, Benign gland 0.70%,
배경 93.78%) 순수 Benign-gland 창을 하나도 못 찾음 — 창을 150μm(유효
~0.335μm/px)로 줄여 재실행(PRECISE 전용 의도적 이탈, 새 기본값 아님).

| 클래스(n) | 마커②(종양확률) 중앙값 | 마커①(예측등급) 평균 |
|---|---|---|
| Tumor(180) | 1.000 | 8.72 |
| Benign gland(165) | 1.000 | **5.22(최저)** |
| Stroma(540) | 0.99997 | 7.66 |
| Artifact(49) | ≈0 | 8.44 |

**마커①: 깨끗한 단조 순서**(Benign 5.22 ≪ Stroma 7.66 < Tumor 8.72) — Gleason
개념이 적용 안 되는 양성조직에서 최저, 종양에서 최고. **더 중요**: Tumor
타일을 이미지별 평균 내 PRECISE의 **실제 병리 판독 Gleason 점수**(우리 proxy
아님)와 대조하면 n=17 이미지에서 **Spearman ρ=+0.865, p=7.6e-06** — 재학습
없이, 완전히 새로운 독립 코호트에서 나온 이 프로젝트 전체를 통틀어 가장
강력한 축의 외부검증 증거.

**마커②: 방향은 맞으나 미세 구분에서 포화**(Tumor>Benign>Stroma 순서는 맞지만
Benign도 중앙값 1.0으로 거의 포화) — NADT의 굵은 슬라이드 단위 종양/양성
구분이 PRECISE의 세밀한 gland 단위 구분으로는 그대로 전이 안 됨. Artifact는
잘 억제됨(거짓 활성화 없음).

**한계**: HGPIN·Intraductal carcinoma는 n=1뿐이라 해석 불가. Artifact의
마커① 평균(8.44)이 다소 높으나 비조직 텍스처에 대한 등급 회귀는 애초에
정의되지 않은 영역.

재현: `models/pilot_precise_spatial_facevalidity.py`(150μm 버전이 최종,
394μm 버전은 설계 이슈 기록용으로 보존). `report.tex` "PRECISE 공간적
face-validity" 절.

## 6g. QWK 재계산 및 SOTA 비교 (2026-07-31)

마커①의 Spearman ρ는 문헌 F1/QWK와 단위가 달라 직접비교 불가 — QWK로
재계산(`pilot_qwk_comparison.py`, 연속 예측을 실제 등급 범주 수만큼
분위수로 이산화, 동일 프로토콜로 5개 코호트 통일).

| 검증 | n | 클래스 | QWK | 입력 | 외부검증 |
|---|---|---|---|---|---|
| NADT 자체(slide-level OOF) | 334 | 5 | 0.261 | biopsy | 아니오 |
| PANDA zero-shot | 1137 | 6 | 0.391 | biopsy | 예(2기관, 재학습 없음) |
| PANDA K→R 재학습 | 572 | 6 | 0.597 | biopsy | 예(재학습함) |
| PANDA R→K 재학습 | 565 | 6 | 0.567 | biopsy | 예(재학습함) |
| TCGA-PRAD zero-shot | 300 | 5 | 0.260 | **절제표본** | 예(3번째 기관) |
| PRECISE zero-shot(실제 Gleason) | 17 | 5 | **0.788** | core biopsy | 예(실제 라벨, 소표본) |
| *문헌: DeepGleason* | — | — | *F1=0.806* | *tile-level* | *QWK 아님, 비교불가* |
| *문헌: PANDA 우승작* | *수천* | 6 | *~0.862/0.868* | *biopsy* | *예, 완전지도학습* |

**정직한 해석**: zero-shot 전이(0.26~0.39)는 PANDA 우승작의 완전지도학습
QWK(~0.86)에 크게 못 미침 — 고정 임베딩 위 재학습 없는 선형 probe와
대규모 라벨 end-to-end 전용 모델의 차이이니 예상된 격차이며, 이 논문은
SOTA 정확도 경쟁이 아니라 신호의 재현성·전이가능성 감사이므로 프레이밍과
일치. PRECISE의 0.788은 예외적으로 높으나 n=17로 작아 과대해석 금지 —
방향(마커①이 진짜 등급 정보를 담음)은 지지되나 신뢰구간은 넓음. PANDA
기관간 재학습(0.57~0.60)이 zero-shot보다 체계적으로 높은 건 자연스러운
패턴(같은 기관 데이터 재보정 효과).

재현: `models/pilot_qwk_comparison.py`. `report.tex` "QWK 재계산과 SOTA
비교" 절.

## 8. 외부 심사(Stanford 스타일 리뷰) Tier 1–2 대응 (2026-08-03)

`paper/StandfordReviewe.md`의 Questions for Authors에 대한 응답. `paper/main.tex`
(`sections/results.tex`, `methods.tex`, 신규 `sections/supplement.tex`)에 전부 반영,
xelatex 2회 재컴파일로 에러 0건 확인.

### 8a. 마커⑦ 다변량 임상 공변량 확장 (Tier-1 1.1)

Grade만 통제하던 기존 confounder audit(§6e)을 age·T-stage(GDC `cases`,
`ajcc_pathologic_t`를 주요 병기 1–4로 단순화)·PSA·수술 절제연(margin, cBioPortal
`prad_tcga_pub` `PREOPERATIVE_PSA`/`RESIDUAL_TUMOR`, 둘 다 patient-level에 실측
존재 확인 — GDC API·cBioPortal API 직접 쿼리로 검증, `models/tcga_prad_clinical_extra/`에
원본 JSON 보존, `models/fetch_tcga_prad_clinical_extra.py`로 재현 가능)까지 포함한
완전조정 모델로 확장(`models/pilot_marker7_confounder_audit.py`
`extended_confounder_audit()`).

결측률: age 0%, T-stage 1%, margin 20%, **PSA 38%**(가장 제한적) — complete-case
n=153(270명 중). 결과: **margin_positive가 이 하위표본에서 매우 강한 예측인자**
(재발률 margin+ 67% vs margin− 7%, HR≈13) — 완전조정 후 마커⑦의 추가 정보량은
더 이상 유의하지 않음(LRT p=0.215, grade-내부 permutation p=0.245; grade만
통제했을 때는 p=0.0011/0.0015였음). n이 270→153, event가 57→30으로 줄어든 검정력
저하와 실제 margin에 의한 confounding을 완전히 분리할 수 없다는 점을 정직하게
병기. **마커⑦의 특징을 수정**: grade-독립적이나, 표준 임상 공변량 전체로부터
독립적이라는 주장은 성립하지 않음.

재현: `models/pilot_marker7_confounder_audit.py`(확장 함수),
`models/marker7_extended_confounder_summary.csv`. `paper/sections/results.tex`
§res-marker7-clinical, `paper/sections/supplement.tex` S2.

### 8b. TCGA 재발 라벨 vs 표준 TCGA-CDR 엔드포인트(PFS/DFS) 벤치마크 (Tier-1 1.2)

cBioPortal `prad_tcga_pan_can_atlas_2018`(Liu et al. 2018 TCGA-CDR 표준 엔드포인트
보유, PFS_STATUS/MONTHS 494/494명, DFS_STATUS/MONTHS 334/494명 확인)로 우리
GDC-재구축 라벨(§6e)을 벤치마크(`models/pilot_tcga_prad_label_benchmark.py`).

임베딩 코호트(n=270) 기준: **사건 일치도** — PFS 대비 87.0% 일치(Cohen's
κ=0.57), DFS 대비 93.2%(κ=0.52, DFS는 n=192로 정의상 더 작음). 우리 라벨이 PFS보다
"재발"로 더 많이 판정(25명 vs 반대방향 10명) — "wt-with tumor"(지속/재발 종양)
정의가 PFS의 진행-특이적 정의보다 넓은 구성개념임을 반영. **추적시간 상관**은
매우 높음(PFS ρ=+0.85, DFS ρ=+0.95, 둘 다 p<10⁻⁷⁵).

**마커⑦ zero-shot을 PFS/DFS로 직접 재검정**: PFS 대비 C-index=0.586(td-AUROC@5y=0.610,
n=270, 42 events), DFS 대비 C-index=0.605(td-AUROC@5y=0.592, n=192, 11 events뿐이라
검정력 낮음). 원래 라벨의 0.673보다 약화됐으나 우연(0.5) 이상이고 방향 일치 —
**부분 검증+부분 한계**: 우리 라벨에 특이적인 아티팩트는 아니나(표준 엔드포인트로도
전이됨), 원 헤드라인 수치(0.673)는 어느 정도 라벨 정의에 의존적.

재현: `models/pilot_tcga_prad_label_benchmark.py`,
`models/tcga_prad_label_benchmark_summary.csv`. `paper/sections/results.tex`
§res-label-benchmark.

### 8c. AR(마커⑥) 사이트별 forest plot + bootstrap CI (Tier-1 1.3)

§3b의 leave-one-site-out 점추정(사이트별 ρ)에 환자-클러스터 부트스트랩 95% CI(2,000회,
사이트별 재실행)를 추가(`models/pilot_ar_site_forest.py`). 결과: CH −0.13
[−0.56,+0.35], EJ +0.13[−0.12,+0.36], G9 +0.20[−0.26,+0.60], HC +0.22[−0.07,+0.47],
YL +0.23[−0.14,+0.54], KK +0.27[−0.09,+0.56] — 표본 크기가 작아(n=22–59) CI가 넓고
모든 사이트에서 CI가 0을 포함(개별 사이트 단독으로는 유의 안 함). 그러나 부호
자체는 CH만 음수이고 나머지 5개 사이트가 전부 양수라는 패턴과, pooled 추정
(ρ=+0.195[0.07,0.31], 전체 5-fold 내부 CV)의 훨씬 좁은 CI를 나란히 보여줌으로써
"context-sensitive" 분류의 근거를 시각화. 신규 그림
`paper/figures/fig6_ar_site_forest.py`(fig5_forest_plot.py와 동일 스타일), PNG로
레이아웃 확인 완료(범례가 마지막 행과 겹치는 1차 문제 발견 후 legend를 축 아래로
이동해 재생성).

재현: `models/pilot_ar_site_forest.py`, `models/ar_site_forest_summary.csv`,
`paper/figures/fig6_ar_site_forest.py`. `paper/sections/results.tex` 확인외
§Confounder audit 단락에 그림 삽입.

### 8d. BH-FDR 13개 가설 전체 표 (Tier-1 1.4)

기존 `models/statistical_corrections_summary.csv`(13행 전부 이미 존재)를 신규
`paper/sections/supplement.tex` S1의 LaTeX longtable로 전체 공개(본문 Table은
여전히 6개 pool 마커만, q값만 표시) — uncorrected p와 q를 나란히, family 소속/제외
기준(외부 코호트 재현·cross-encoder 복제는 family에서 제외한다는 기존 결정)도
명시. 신규 실험/계산은 없음(기존 CSV 재포맷).

### 8e. PRECISE 집계 단위 명확화 + patient-level 강건성 확인 (Tier-1 1.5)

`pilot_precise_spatial_facevalidity.py`의 집계 단위는 이미지(=세션,
`sub-XX_ses-YY`)임을 `methods.tex`/`results.tex`에 명시. **오류 정정**: 기존
문서에 반복된 "25명/37건"은 검증 안 된 수치였음 — README·participants.csv 직접
대조 결과 **25명, 27세션**(sub-01만 3세션, 나머지 24명은 각 1세션)이 맞음(§7f 및
`docs/04` 정정, "verify before trusting" 원칙 재확인 사례). 실제 Gleason 비교
n=17 세션은 전부 서로 다른 17명의 환자에서 나옴(sub-01의 다른 두 세션은 양성/무자격
타일이라 비교셋에서 애초 제외) — 즉 session-level과 patient-level 집계가 이
특정 비교에서는 수치적으로 동일(ρ=+0.865 양쪽 다). 핵심 결과가 다세션 환자
과대표집의 인공물이 아님을 확인. Core-biopsy(절제표본 아님)도 README의 "age at
biopsy" 필드로 재확인.

### 8f. 코호트별 타일 샘플링 방법 명세 (Tier-1 1.6)

`methods.tex`의 뭉뚱그린 "non-white-pixel or provided-mask" 문장을 실제 코드
대조로 코호트별 정확한 명세로 교체: NADT/PANDA/TCGA-PRAD는 랜덤-균일 좌표
rejection sampling(TISSUE_FRACTION_MIN=0.35, 16타일/슬라이드, TCGA-PRAD는
AppMag 기반 동적 스케일); LEOPARD는 제공된 실제 조직 마스크 기반 비중첩 grid
(mask fraction≥0.5, 64타일/슬라이드로 서브샘플); PRECISE는 픽셀 주석 마스크 기반
비중첩 grid(150μm 창, 클래스당 최대 20타일, 슬라이드 전체 아님). 신규 실험 없음,
기존 코드(`pilot_conch_nadt_probe.py`, `pilot_conch_tcga_prad_erg.py`,
`pilot_conch_leopard_embed.py`, `pilot_precise_spatial_facevalidity.py`) 재확인.

### 8g. 생존분석 지표 확장 (Tier-1 1.7)

LEOPARD 3-pool(`models/leopard_conch_cache/pool_comparison_summary.csv`, 이미
계산되어 있었으나 본문에 축소 보고됐던) IBS·calibration slope를 표로 승격 —
naive(IBS 0.127, slope −1.10), qualified(0.128, −4.01), all-candidate(0.124,
+0.33), 전부 C-index<0.5와 함께 나쁜 calibration slope로 "개별 null 마커를
다변량으로 합치면 불안정해진다"는 기존 결론을 보강. 마커⑦ zero-shot 전이에는
IBS(0.124, 0.5–10년)·calibration slope(+0.53, 1.0 미만은 TCGA-PRAD로 recalibration
없이 적용했을 때의 과분산을 시사)·HR(1.71 [1.34,2.18])을 신규 계산해 추가
(`pilot_tcga_prad_recurrence_external.py` 확장).

### 8h. LEOPARD embargo 문구 명확화 (Tier-1 1.8)

기존 `main.tex` Data/code availability 절 문구는 이미 승인을 함의하지 않고 정확했음
— 추가로 명시적인 "Ethics and data-use statement" 절을 신설해 embargo가 여전히
유효할 수 있음, 승인 미확보, organizer 문의 초안(`opendataset/LEOPARD/organizer_email_draft.txt`)
존재, 투고 전 재확인 필요함을 명시적으로 못박음. **실제 상태는 변경 없음** — 이
항목은 여전히 open이며 투고 전 organizer 응답이 필요.

### 8i. SPOP null 강건성: class-weight ablation (Tier-2 2.2)

`class_weight="balanced"`(표준) vs `None`(재가중 없음) 비교
(`models/pilot_spop_classweight_ablation.py`): slide AUROC 0.508 vs 0.506, patient
AUROC 0.519 vs 0.516, 둘 다 비유의 — SPOP null이 class-imbalance 처리 방식의
인공물이 아님을 확인. Site-restricted 분석(§3b)은 이미 존재했으나 지금까지
`paper/main.tex` 본문에는 반영되지 않았음을 발견 — 이번에 처음으로
`paper/sections/results.tex`에 실제 수치(3개 사이트만 검정 가능, AUROC
0.57–0.65, 사이트 수가 너무 적어 null 결론을 뒤집는 근거는 아님)로 명시.

### 8j. 타일수·물리스케일 민감도 그리드, 마커④ (Tier-2 2.1)

타일수 {16,32,64} × 물리스케일 {~0.44,~0.88,~1.76}μm/px 3×3 그리드를 마커④(PTEN
loss)에 적용(`models/pilot_tcga_prad_scale_tile_sensitivity.py`). **범위 조정**: 최초
300슬라이드 전체 실행이 ~0.44μm/px 셀에서 예상보다 훨씬 느려 중단하고, PTEN 상태로
층화한 90슬라이드 고정 서브샘플(전체 셀에 동일 시드·동일 슬라이드셋)로 재실행.

**버그 발견 및 수정(2026-08-03, 중요)**: 1차 재실행(서브샘플 적용 직후) 결과, 같은
타일수에서 mpp=0.44/0.88/1.76 세 스케일의 AUROC가 소수점까지 완전히 동일하게 나옴 —
직접 진단한 결과 TCGA-PRAD SVS 파일의 실제 타일드 피라미드 레벨이 {0.25, 1.0, 4.0,
8.0}μm/px 네 개뿐이라, 기존 `pick_level`이 세 타깃(0.44/0.88/1.76) 전부를 "가장 가까운"
1.0μm/px 레벨 하나로 스냅시키고 있었음(레벨0 완전 배제 + 가장 가까운 기존 레벨만
선택하는 방식의 부작용). PRECISE 스크립트에 이미 쓰던 방식(물리적 크기에 맞춘 native
윈도우를 zarr로 부분 읽기 + 리사이즈)으로 교체해 레벨0도 후보에 포함시키고, 실제로
서로 다른 유효 배율을 갖도록 수정. 이 수정은 부수적으로 속도 문제도 해결(전체 페이지
디코딩 대신 필요한 픽셀만 windowed 읽기 — 슬라이드당 2~20초로 단축, 이전 ~1분/슬라이드
대비 대폭 개선).

**최종 결과** (환자수준 AUROC, n=85, 90슬라이드 서브샘플, 단일 시드):

| 타일수\\스케일 | 0.44μm/px | 0.88μm/px | 1.76μm/px |
|---|---|---|---|
| 16 | 0.488 | 0.598 | 0.643 |
| 32 | 0.594 | 0.575 | 0.564 |
| 64 | 0.600 | 0.602 | 0.621 |

**해석**: 타일수 16에서는 스케일에 따라 AUROC가 0.488~0.643으로 크게 변함(폭 0.155) —
이 타일수에서는 스케일 선택이 결과에 실질적 영향을 줌. 타일수 32/64에서는 폭이 각각
0.03/0.02로 좁아져, 타일을 더 많이 평균할수록 정확한 물리 스케일에 대한 민감도가
완화되는(완전히 없어지지는 않는) 패턴. 마커 1개·시드 1개·서브샘플 1개에 국한된
검사라 일반화에는 한계가 있으나, 이 범위 내에서는 이 프로젝트가 기존에 써온
16–64타일/슬라이드 기본값이 합리적이며, 그중에서도 낮은 쪽(16타일)이 스케일에 더
민감하고 높은 쪽(64타일)이 더 안정적임을 시사. `paper/sections/results.tex`
§res-scale-sensitivity에 반영.

**Major-revision 확장:** 같은 9개 cell의 이미 계산된 embedding으로 AR과 SPOP도 함께
평가했다. AR patient ρ=0.114~0.355 (9셀 모두 양수; R²=−0.074~+0.175), SPOP patient
AUROC=0.341~0.601로 chance 양쪽을 오갔다. 단일 seed/85명 서브샘플이므로 primary
full-cohort 결과를 대체하지 않지만, AR의 크기 불안정성과 SPOP의 무방향성을 보강한다.

## 9. Major-revision nested/refit 재분석 (2026-08-03)

`paper/revision_analysis_plan.md`의 P0/P1을 실행했다. 기존 full-cohort LRT 및 고정-score
permutation과 달리 outer/inner patient-disjoint cross-fitting과 permutation별 probe
재학습을 사용했다. 최종 2,000회 결과는 PTEN ΔAUROC=+0.019 (95% CI
−0.025~+0.068, p=0.203), AR ΔR²=+0.004 (−0.036~+0.042, p=0.176), marker7
grade-only ΔC-index=+0.062 (+0.008~+0.119, p=0.010), marker7 fully adjusted
+0.002 (−0.012~+0.015, p=0.305)다. 따라서 PTEN/AR grade-independent increment
주장은 철회하고 marker7은 post-hoc/endpoint-sensitive exploratory signal로 제한한다.

13 marker tests와 4 nested audit를 하나의 17-test family로 BH 보정한 결과 marker7
grade-only audit만 신규 audit 중 유지(q=0.028); PTEN/AR/full-marker7 q는 각각
0.314/0.299/0.399다. ETV4는 q=0.056으로 0.05 아래가 아니다. M0--M5 계층에서는
M4(clinical+site) C-index=0.881, M5(+image)=0.879, paired Δ=−0.0024
(−0.0118~+0.0064)였다. 전체 파일/endpoint/재현성 산출물은
`paper/revision_execution_summary.md`에 정리했다.

## 9b. Nested confounder audit의 Virchow 교차검증 (2026-08-03)

§9의 PTEN/AR nested 결과(둘 다 held-out 증분의 95% CI가 0을 포함)가 CONCH 임베딩
고유의 아티팩트인지 확인하기 위해, 같은 nested bootstrap 파이프라인을 Virchow
임베딩(`models/virchow_tcga_prad_cache/X_spop.npy`, 같은 300슬라이드/273환자
universe, file_name/case_id 순서 직접 대조로 CONCH 캐시와 동일함 확인)으로
재실행했다(`models/pilot_confounder_audit_nested_virchow.py`, CPU 전용, 재임베딩
불필요). 마커⑦은 재검증하지 않았다 — Virchow zero-shot 전이가 이미 독립적으로
실패했으므로(§6e) 추가 정보가 없음.

**결과: Virchow가 CONCH와 수렴한다(발산하지 않음).** PTEN ΔAUROC=+0.035(95% CI
[−0.013, +0.087], CONCH는 +0.019 [−0.025, +0.068]), AR ΔR²=+0.019(95% CI
[−0.015, +0.051], CONCH는 +0.004 [−0.036, +0.042]) — 둘 다 방향은 양수, 크기는
작고, CI는 0을 포함해 CONCH와 같은 정성적 결론. 두 독립적으로 학습된 인코더가
"약하고 불확실하다"는 결론에서 일치한다는 것 자체가, 이 약한 신호가 CONCH
임베딩 공간 특이적 아티팩트가 아니라 grade-PTEN/AR 관계 자체의 속성일 가능성을
지지한다. `paper/sections/results.tex`(Confounder audit 절)와
`paper/sections/discussion.tex`에 반영. 이걸로 §5의 "7단계 시작 전 Virchow
교차검증" 항목이 해소됐다 — 7단계(원고 재구성) 착수 가능.

## 9c. 원고 9-section 재구성 (P3, 2026-08-03)

`paper/MajorRevision-v1.md` §7이 제안한 9-section 구조로 원고를 전면 재구성했다:
Introduction → Prespecified and exploratory components(신규) → Cohorts and frozen
encoders → Qualification gates → Core marker results → Confounder and site audits →
Downstream recurrence transfer → Failure modes → Limitations. 기존
Introduction/Methods/Results/Discussion 4-섹션 파일(`methods.tex`/`results.tex`/
`discussion.tex`)은 `paper/sections/_pre_restructure_archive/`로 보존하고 더 이상
컴파일에 포함하지 않는다 — 원본은 `paper_backup_pre_restructure_20260803_162622/`에
전체 백업 완료.

**내용 이동 원칙**: 사용자 결정에 따라 본문은 결론만, "여정" 서술(버그 발견→수정
과정, 축소 사유)은 Supplementary S3–S5로 이동. 예: 타일-스케일 그리드의 피라미드
레벨 스냅 버그 진단·수정 전체 서사는 S3로, TCGA 재발라벨 500-case provenance
표·strict endpoint 제외 규칙 상세는 S4로, Virchow 교차검증을 마커7엔 안 한 이유·
multiple imputation 미실시 사유는 S5로.

**신규/재구성 그림 4개**: (1) Figure 1 — qualification protocol schematic(신규,
6개 사전등록 마커→4-gate 프로토콜→5단계 신뢰도, 마커⑦은 별도 post-hoc 경로로
표시). (2) 마커④ nested confounder audit + 마커⑥ site forest plot을 2-panel로 결합
(기존 개별 그림 대체). (3) 마커⑦ nested increment + M0→M5 계층 C-index 계단식
그래프를 2-panel로 결합(신규 M0-M5 시각화). (4) 3마커(PTEN/AR/SPOP) 타일수×스케일
히트맵(신규, `models/tcga_prad_scale_tile_sensitivity_summary.csv`의 AR/SPOP 컬럼
전부 활용 — SPOP이 우연(0.5/0)을 반복적으로 넘나드는 패턴이 히트맵에서 직접 확인됨,
기존 서술과 정확히 일치). 전부 PNG로 직접 열어 레이아웃 확인 완료(1차에서 프로토콜
스키매틱의 마커⑦ 박스가 Gate 1과 겹치는 문제, 두 콤보 그림의 범례 겹침 문제 발견 후
재생성으로 해결).

**검증**: xelatex 2회 재컴파일 — 에러 0, 24페이지(재구성 전 21페이지, 신규 그림
2개+Supplement 확장분 증가로 설명됨). 활성 섹션 파일 간 `\label{}` 중복 없음 확인.
백업본 대비 핵심 수치 15개 앵커(0.673, 0.019, κ=0.57, 1.71, 0.881 등) 전부 활성
섹션에 보존 확인 — 재구성 과정에서 결과 누락 없음.

## 10. 다음 단계

- **Nested/refit confounder audit(§9)는 완료, Virchow 교차검증(§9b)도 완료.** 기존
  §6b/§6c 수치는 auxiliary로 유지.
- **LEOPARD(§6d)는 완료.** zero-shot 3-pool은 null, in-cohort 신호는 실재 확인.
- **마커⑦ 외부검증(§6e)은 완료하되 claim 하향.** CONCH 방향은 일부 endpoint에서
  유지되나 post-hoc, encoder-dependent, full-clinical increment 없음.
- **PRECISE 공간적 face-validity(§6f)는 완료.** 마커①이 강한 결과.
- **외부 심사(Stanford) Tier 1–2 대응(§8)은 완료.** Major-revision P0/P1도 완료.
- **다음 작업: 9-section 원고 재구성(P3) 착수 가능** — Virchow 교차검증까지 끝나
  구조를 다시 바꿀 만한 잔여 리스크는 낮다고 판단됨(2026-08-03).
- **남음(원고 재구성과 별개, 우선순위 낮음):** multiple imputation, Virchow
  5-seed/128-tile/tumor-enriched 확장, bootstrap ΔBrier.
- **DiagSet-C**(46건, 9인 병리의 독립 판독): 등록 신청, 관리자 승인 대기 중(우선순위
  하향, `docs/04` 참고). 모델 불확실성이 실제 병리의 간 의견불일치와 상관되는지
  (ambiguity stress test, 성능 벤치마크 아님).
- **VLM bridge**(선택, 부록급): 검증된 마커를 evidence로 준 조건 vs 뒤섞은 마커 조건
  비교.

## 참고: 자세한 수치와 정정 이력

전체 실험의 시간순 기록, 정정 이력(erratum), 코드 경로는
`song-datasets/_previews/latex/report.tex` §9.6, §10에 있음(주 기록 문서). 이 문서는
그 요약본이다.
