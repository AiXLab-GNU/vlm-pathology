# 접근 방법과 목표 기여

> **2026-07-29 재구성**: `docs/01_motivation.md`의 새 프레이밍(confounder-aware
> qualification)에 맞춰 다시 씀. 핵심 변화: "6단계 절차 자체가 새로운 방법론"이라는
> 주장을 버리고, "이미 있는 검증 원칙들을 병리 파운데이션 모델 마커 발견에 일관되게
> **적용(operationalize)**했다"는 겸손하지만 방어 가능한 주장으로 바꿈. "감사(audit)냐
> 프레임워크냐"라는 질문에 대한 답: **논문의 실체는 audit이고, 재사용 가능한 산출물은
> prespecified qualification protocol이다.** "우리가 새 통계 프레임워크를 발명했다"는
> 절대 주장하지 않는다.

## 핵심 방법론: Qualification Protocol (발명이 아니라 적용)

BH-FDR, bootstrap CI, patient-disjoint cross-validation, external transport,
confounder 보정 같은 개별 기법은 전부 이미 있는 표준 통계/역학 원리다. 이 프로젝트의
방법론적 기여는 이들을 **병리 파운데이션 모델에서 나온 후보 마커 각각에 사전에 정의된
순서로 일관되게 적용**하고, 그 결과를 5단계 신뢰도 등급으로 분류하는 절차 자체다.

1. 고정된(재학습하지 않은), **판별형(비생성)** 파운데이션 모델(CONCH, Virchow)로 조직
   타일을 임베딩(숫자 벡터)으로 변환한다. 모델 본체는 건드리지 않는다.
2. 그 임베딩 위에 아주 가벼운 통계 모델(선형 회귀 RidgeCV / 로지스틱 회귀)만 새로
   학습시킨다.
3. 우리 자체 proxy가 아니라 **실제** 임상 진단(Gleason score, Phenotype) 또는 분자
   검사(PTEN_CNA, SPOP_MUTATION, AR_SCORE 등, cBioPortal 등 공인 소스) 라벨과 비교한다.
4. **환자 단위 분리 교차검증(patient-disjoint GroupKFold)**: 같은 환자의 슬라이드가
   학습/검증에 걸쳐 섞이지 않게 한다 — 이게 안 지켜지면 가짜 반복(pseudo-replication)으로
   상관관계가 부풀려진다.
5. **Confounder audit**: (임상변수만) vs (이미지 probe만) vs (임상변수+이미지)를
   비교해 이미지가 추가하는 정보(incremental value)를 확인하고, grade/site 층 내부에서도
   신호가 남는지 확인한다 — 등급이나 병원 출처를 그냥 재탐지한 것(shortcut)이 아닌지
   보는 단계.
6. **Cross-cohort/cross-encoder 재현**: 다른 기관 코호트(PANDA, TCGA-PRAD)와 다른
   파운데이션 모델(Virchow) 양쪽으로 재현되는지 확인한다. 이때 "계수를 고정한 채 그대로
   적용"(transport)과 "다른 코호트에서 새로 학습"(replication)을 구분해서 보고한다 —
   전자가 훨씬 강한 증거다.
7. 위 기준을 통과한 정도에 따라 마커를 5단계로 분류한다(아래 표). SPOP처럼 통과하지
   못하면 그 자체로 정직하게 null로 보고한다.

이 절차를 6개 주요 후보 + 7개 이상의 미확정/null 후보(TP53 변이·CNA, RB1, SPINK1,
ETV1/4, ERG 융합 상태)에 동일하게 적용했다.

## 신뢰도 등급 (Reliability Map, 5단계)

| 등급 | 정의 | 현재 해당 후보 |
|---|---|---|
| Externally transportable | 계수(coefficient)를 고정한 채 독립 코호트에 그대로 적용해도 신호·calibration 유지 | ① H&E→Gleason, ② H&E→Phenotype (PANDA zero-shot transfer로 확인) |
| Cross-cohort replicable | 외부 코호트에서 새로 학습(refit)하면 같은 방향으로 재현 | ④ H&E→PTEN 소실 (TCGA-PRAD leave-one-site-out 6개 사이트 일관) |
| Internally supported, externally untested | CONCH/Virchow 등 여러 인코더에서 내적으로 일관되지만, 독립 코호트가 존재하지 않아 진짜 외부 검증은 못함 | ③ ERG→Gleason (동형 코호트 부재 확인됨), ⑥ AR 활성도 (아래 참고, 단 site-불안정 겹침) |
| Context-sensitive | site/grade/scale/encoder에 따라 방향·강도가 불안정 | ⑥ H&E→AR 활성도 (한 사이트 부호 반전) |
| Unsupported/null | 사전 기준(BH-FDR, CI, 재현) 미충족 | ⑤ H&E→SPOP 변이 (CONCH·Virchow 둘 다 null) |

(⑥은 여러 인코더에서 방향은 일관되지만 site-split에서 불안정하므로 "internally
supported"와 "context-sensitive" 경계에 있다 — 최종 분류는 confounder audit 결과에
따라 확정한다.) 자세한 마커별 수치는 `docs/03_experimental_results.md` 참고.

## 목표 재정립의 배경

원래 목표는 자체 규칙 기반 알고리즘(`dab_ring`)이 옳다는 것을 증명하는 것이었으나,
이 알고리즘이 NADT-Prostate 39명 환자의 실제 Gleason score와 대조했을 때 환자 단위에서
null이었다(모든 지표 p>0.28). 이 결과가 "데이터에 신호가 없어서"인지 "알고리즘이
서툴러서"인지 구분할 수 없었던 것이 전환점이었다. 이후 CONCH 임베딩 + 경량 probe로
같은 데이터를 재검증하자 유의한 신호가 나왔다(환자 단위 ρ=+0.478, p=0.0021) — 즉
데이터엔 신호가 있었고, 우리 규칙 기반 알고리즘이 그걸 못 찾았을 뿐이었다. 이 발견이
목표를 "하나의 완벽한 알고리즘 증명"에서 "마커 후보들을 체계적으로 검증하는 절차
구축"으로 바꾼 계기다.

## 목표 기여 (Contributions)

1. **사전에 정의되고 일관되게 적용된 qualification protocol** — 새로 발명한 통계
   기법이 아니라, 이미 있는 원칙(confounder 보정, patient-disjoint CV, 외부 transport,
   교차 인코더 재현, 다중비교 보정)을 병리 파운데이션 모델 마커 발견에 일관되게
   적용(operationalize)한 것.
2. **실증적 신뢰도 지도(reliability map)** — 위 5단계로 분류된 후보들: 이식 가능(①②),
   재현 가능(④), 내적으로만 지지됨(③⑥), null(⑤).
3. **다중 assay 분자적 일치성(molecular concordance)과 confounder 통제 평가** — TCGA-PRAD
   내에서 PTEN(CNA→mRNA→RPPA), ERG(fusion→발현), AR(발현→target-gene score)처럼 같은
   타깃을 여러 측정층에서 교차 확인(강도는 타깃마다 다름 — PTEN이 가장 강한 삼각검증,
   AR은 둘 다 RNA 기반이라 상대적으로 약한 "pathway-level consistency"). **"생물학적
   증명"이라고 과장하지 않는다** — grade로 층화한 뒤에도 일치하는지까지 확인해야 완전하다.
4. **결합(fusion) 원칙의 실증**: "같은 타깃을 다른 채널(염색 또는 모델)로 측정한
   마커끼리 결합하면 이득이 있다"는 것을 염색 채널(①+③, H&E+ERG)과 모델 채널
   (CONCH+Virchow)에서 각각 독립적으로 확인했다. 단, 이건 "결합은 항상 좋다"는 일반
   법칙이 아니라 "우리 실험에서, 타깃이 일치하고 개별적으로 유효한 채널을 결합했을 때"로
   한정해 표현한다 — 다른 타깃끼리 결합하거나 한쪽이 압도적으로 강할 때는 오히려
   손해였다(⑥의 Virchow 단독 대비 앙상블 하락 사례).
5. **재사용 가능한 병리-파운데이션-모델 특이적 함정들** (일반 통계 원리가 아니라, 이
   qualification을 실제로 exhaustive하게 수행하면서 발견한 도메인 특이적 교훈):
   - 물리적 타일 스케일 불일치가 (인코더의 "권장 스케일"을 따르더라도) 교차 코호트
     전이를 완전히 붕괴시킬 수 있다.
   - 기관/스캐너 signature가 분자 신호처럼 보일 수 있다.
   - grade-바이오마커 연관이 표적-특이적 형태로 오인될 수 있다(confounder audit으로
     걸러야 함).
   - 인코더가 달라지면 신호의 방향·강도가 달라질 수 있다(⑥의 CONCH vs Virchow 차이).
   - assay 라벨의 정의가 달라지면 같은 "마커"도 다른 결과를 낼 수 있다.
   - fusion은 두 채널이 각각 독립적으로 유효하고 타깃이 정렬될 때만 도움이 된다.
   - 하이퍼파라미터 탐색 차이만으로 경계선 결과가 뒤집힐 수 있다(ERG 융합 상태가
     `LogisticRegressionCV`에서 표준화된 `C=1.0`으로 바뀌자 경계선 유의 → 명확한 null로
     바뀐 사례).
6. **(선택, 부록급) VLM evidence-grounding에 대한 소규모 인과 실험**: 검증된 마커를
   생성형 VLM에 evidence로 제공했을 때(정답 마커 vs 뒤섞은 마커 vs 마커만 vs 이미지만)
   추론이 실제로 좋아지는지, 아니면 잘못된 evidence도 맹목적으로 따라가는지 확인한다.
   이 실험은 본문의 핵심이 아니라 작은 부록/보조 figure로만 다룬다 — 성공해도 실패해도
   정직한 결과가 된다(§ `docs/04_publication_strategy.md` "VLM bridge" 참고).

## 무엇을 주장하지 않는가 (Scope 제한)

- **새로운 통계 기법이나 프레임워크를 발명했다고 주장하지 않는다** — BH-FDR, bootstrap
  CI, patient-disjoint CV, transportability 개념은 전부 기존 원리다. 우리 기여는 이를
  병리 파운데이션 모델 마커 발견에 일관되게 적용한 실증이다.
- **등급 예측 원시 정확도로 SOTA를 이긴다고 주장하지 않는다** — DeepGleason 등 전용
  모델이 여전히 더 정확하다. 우리의 기여는 정확도가 아니라 신뢰도 판정·재현성·다축성에
  있다.
- **PTEN/ERG/AR이 독립 코호트에서 외부 검증됐다고 주장하지 않는다** — 실제 독립적인
  PTEN/ERG-라벨 코호트가 없어서, 이들은 "내적으로 지지되지만 외부 미검증"으로만
  표현한다. 협력 가능한 병리과가 있으나, 새 코호트를 전향적으로 모으는 것은 이 논문의
  범위 밖이다(시간·비용 문제로 사용자가 명시적으로 제외 결정).
- **LLM이 실제로 이 마커들을 근거로 추론하는 시스템을 만들었다고 주장하지 않는다** —
  §기여 6의 작은 bridge 실험 정도만 다루고, 실제 배포 시스템은 후속 연구로 남긴다.
- **모든 마커가 임상적으로 강하다고 주장하지 않는다** — PTEN·AR 활성도는 통계적으로
  실제 신호이지만 약하고(AR은 특히 site-sensitive), 단독 진단 근거로는 부족하다는 것을
  정직하게 명시한다.
