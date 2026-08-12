네. 더 높은 수준으로 올릴 수 있습니다. 다만 핵심은 데이터셋·마커·모델 수를 무작정 늘리는 것이 아니라, 논문의 질문 자체를 다음처럼 한 단계 바꾸는 것입니다.

> “병리 파운데이션 모델에서 통계적으로 유의한 신호가 나왔다”가 아니라,
> **“그 신호가 등급·기관·스캐너·공발생 분자변이 같은 shortcut이 아니라, 다른 조건에서도 이식 가능한 target-specific evidence인지 어떻게 판정할 것인가?”**

이 방향이라면 현재의 SPOP null, AR site sensitivity, scale failure도 모두 논문의 핵심 결과가 됩니다.

## 1. 가장 추천하는 논문 프레이밍

가칭 제목:

> **A confounder-aware qualification framework for portable histomolecular evidence from frozen pathology foundation models**

조금 더 공격적으로는:

> **Separating portable biological signals from shortcuts in prostate pathology foundation-model biomarkers**

핵심 가설은 다음과 같습니다.

1. 고정된 파운데이션 모델과 선형 probe를 사용하면 다양한 마커의 apparent signal을 저비용으로 발견할 수 있다.
2. 그러나 그중 상당수는 등급, 기관, 스캐너, 염색, 동반 변이에 의존한다.
3. 사전 정의한 qualification gate를 통과한 신호만이 외부 코호트에서도 유지되는 정량적 evidence가 된다.
4. 이러한 검증된 evidence는 임상 예후 예측 또는 향후 VLM 추론에 추가적 가치를 제공한다.

이렇게 하면 논문의 주인공은 CONCH나 “6개 마커”가 아니라 **marker qualification framework**가 됩니다.

이는 중요합니다. 최근에는 이미 19개 파운데이션 모델·31개 과제를 비교한 연구가 있고, 2026년 7월에는 32개 모델·41개 과제를 frozen feature extraction과 linear probing으로 비교한 연구까지 나왔습니다. 따라서 “여러 모델과 여러 마커를 linear probe로 비교했다”만으로는 경쟁하기 어렵습니다. [Neidlinger et al.](https://www.nature.com/articles/s41551-025-01516-3), [Bareja et al.](https://www.nature.com/articles/s41467-026-76004-6_reference.pdf)

반면 최신 연구들은 병리 AI가 grade나 공발생 변이를 이용한 shortcut에 의존할 수 있고, 파운데이션 모델 임베딩에 기관·스캐너 정보가 강하게 남는다는 점을 보여줍니다. 바로 여기가 현재 프로젝트가 들어갈 수 있는 새로운 공간입니다. [Dawood et al.](https://www.nature.com/articles/s41551-026-01616-8), [PathoROB](https://www.nature.com/articles/s41467-026-73923-2)

## 2. 세 가지 확장 전략

| 전략                    | 중심 질문                              | 장점                           | 위험                            | 예상 저널 수준                                                           |
| --------------------- | ---------------------------------- | ---------------------------- | ----------------------------- | ------------------------------------------------------------------ |
| A. 이식성·confounding 검증 | “어떤 신호가 진짜 portable한가?”            | 현재 결과 대부분 활용 가능, null도 가치 있음 | 분석 설계가 매우 엄밀해야 함              | Scientific Reports 이상, 잘하면 npj Precision Oncology/Modern Pathology |
| B. 분자·공간적 검증          | “PTEN/ERG/AR 신호가 실제 해당 조직에 위치하는가?” | 생물학적 설득력이 가장 큼               | target-specific IHC 외부 코호트 필요 | Modern Pathology, Journal of Pathology 계열                          |
| C. VLM grounding      | “검증된 마커가 VLM 오류·환각을 줄이는가?”         | 최신성·차별성 큼                    | 평가 비용, 모델 변동성, 병리의 판독 필요      | npj Digital Medicine/Communications Medicine 가능                    |

제 권고는 **A를 본체로 하고 B를 강하게 추가하며, C는 작은 causal bridge experiment로만 넣는 것**입니다.

C를 본체로 하기에는 이미 PathoSage처럼 외부 도구의 증거를 조정해 병리 VQA 환각을 줄이는 agentic 연구가 등장했습니다. 단순히 “evidence를 VLM에 준다”는 것만으로는 빠르게 노벨티가 소진되고 있습니다. [PathoSage](https://arxiv.org/html/2606.07549v1)

## 3. 공개 데이터 확장 계획

### 가장 가치가 큰 코호트

| 데이터        | 논문에서 맡길 역할                    | 핵심 실험                                                             |
| ---------- | ----------------------------- | ----------------------------------------------------------------- |
| TCGA-PRAD  | 분자마커 discovery와 confounder 분석 | PTEN CNA–RNA–protein, ERG fusion–ERG expression, AR score 삼각검증    |
| PANDA      | 다기관 Gleason transport         | Radboud→Karolinska 및 역방향 zero-refit transfer                      |
| PANDA-PLUS | label noise와 공간적 grade 검증     | 기존 PANDA label과 재주석 label에서 결과 안정성 비교                             |
| SICAPv2    | 독립적 Gleason/cribriform 검증     | patch 및 slide 수준 QWK, 공간적 localization                            |
| DiagSet    | 암/정상 및 인간 불일치                 | 4,675 WSI 외부검증, 46 WSI의 9인 판독과 selective prediction 비교            |
| LEOPARD    | 임상 예후                         | 생화학적 재발 time-to-event, grade/PSA 대비 incremental value             |
| PRECISE    | H&E–IHC 공간 검증                 | malignant/benign gland 및 precursor lesion에서 evidence localization |
| PESO       | 상피·암 영역 검증                    | H&E prediction이 IHC-defined epithelium에 집중되는지 확인                  |

PANDA는 10,616개 개발용 biopsy와 독립적인 다기관 검증을 제공하며, 기존 최고 알고리즘의 외부 QWK가 약 0.86–0.87이므로 grade 결과의 현실적인 기준점이 됩니다. [PANDA study](https://www.nature.com/articles/s41591-021-01620-2)

PANDA-PLUS는 PANDA 중 546개 WSI를 pixel-level로 재주석했고, 기존 PANDA label과 특히 고등급에서 체계적인 불일치를 보고했습니다. 따라서 “label choice에 따라 marker validity가 변하는가?”라는 좋은 sensitivity analysis가 가능합니다. [PANDA-PLUS](https://scholarsarchive.byu.edu/facpub/9535/)

DiagSet은 4,675개 binary-labeled WSI와 9명 병리의가 독립 판독한 46개 WSI를 포함하므로, 단순 성능뿐 아니라 인간 불일치 영역에서의 abstention 실험에 적합합니다. [DiagSet](https://www.nature.com/articles/s41598-024-52183-4)

LEOPARD는 H&E prostatectomy WSI에 재발 여부와 추적시간을 제공하므로 “마커가 임상 결과에 추가 정보를 주는가?”를 확인하기 좋습니다. [LEOPARD open dataset](https://registry.opendata.aws/leopard/)

특히 2026년 공개된 PRECISE에는 25명 환자의 37개 prostate biopsy와 대응되는 H&E–IHC, 24,387개 전문가 주석이 있습니다. 크기는 작지만 evidence localization과 조직학적 특이성을 보여주는 데 매우 가치가 큽니다. [PRECISE dataset](https://zenodo.org/records/20721779)

단, 중요한 한계가 있습니다.

> 공개 데이터만으로는 PTEN·ERG의 진정한 독립 외부 분자검증이 충분하지 않을 가능성이 큽니다.

TCGA는 discovery에는 좋지만 CONCH나 Virchow의 사전학습에 포함되었을 가능성을 배제할 수 없습니다. 따라서 TCGA 결과를 “external validation”이라고 부르면 안 됩니다. 가능하다면 **H&E + ERG/PTEN IHC 또는 sequencing이 있는 독립 기관 코호트 150–300명**을 협력으로 확보하는 것이, 공개 grading 데이터셋 5개를 더 추가하는 것보다 논문의 급을 훨씬 크게 올립니다.

## 4. 반드시 해야 할 핵심 실험

### A. Confounder falsification

각 분자마커에 대해 다음 모델을 비교해야 합니다.

1. grade/site/age 등 임상변수만 사용
2. image embedding만 사용
3. 임상변수 + image embedding
4. image prediction을 grade·site로 residualization한 모델

그리고 다음 subgroup 분석을 합니다.

* 동일 Grade Group 내부
* 동일 tissue-source-site 내부
* 주요 공발생·상호배타 변이별
* tumor purity 층화
* specimen type별
* scanner 또는 염색 조건별

핵심 결과는 전체 AUROC가 아니라 다음입니다.

[
\Delta \mathrm{AUC}
===================

## \mathrm{AUC}_{clinical+image}

\mathrm{AUC}_{clinical}
]

즉, “병리 이미지가 이미 알고 있는 grade와 site를 넘어 무엇을 추가하는가?”입니다.

또한 label을 confounder strata 내부에서만 permutation해야 합니다. PTEN label을 전체 환자에서 무작위화하는 일반 permutation보다, 동일 grade·site 안에서 무작위화해야 shortcut을 더 엄밀히 검정할 수 있습니다.

### B. 진짜 transport experiment

외부 코호트에서 probe를 다시 학습시키면 그것은 “재현”이지 엄밀한 의미의 “이식”이 아닙니다. 두 결과를 분리하십시오.

* Replication: 외부 코호트에서 새 probe를 학습해 같은 방향의 신호가 나오는가?
* Transport: source에서 학습한 scaler와 coefficient를 완전히 고정하고 target에 그대로 적용해 성능·calibration이 유지되는가?

두 번째가 훨씬 강한 결과입니다.

### C. 생물학적 삼각검증

TCGA-PRAD 내부에서도 단일 label만 보지 말고 여러 assay를 연결할 수 있습니다.

* PTEN: CNA → PTEN mRNA → RPPA/protein
* ERG: fusion status → ERG expression → ERG-related pathway
* AR: AR expression → AR target-gene score → 임상 phenotype

하나의 image score가 서로 다른 assay에서 일관된 방향을 보이면 “단일 noisy label을 맞춘 것”보다 훨씬 설득력이 높습니다.

가능하면 target-specific IHC 코호트에서는 slide-level AUROC뿐 아니라:

* tumor region 대 benign region score
* IHC-positive 대 IHC-negative gland score
* heterogeneous PTEN loss 내부의 spatial concordance
* heatmap–IHC colocalization

까지 평가해야 합니다. ERG의 “왜 예측되는가?” 문제도 이 방법으로 상당 부분 해결할 수 있습니다.

### D. 임상적 추가가치

LEOPARD에서 단순 재발 분류가 아니라 survival analysis를 사용하십시오.

* Cox 또는 penalized Cox
* Harrell’s C-index
* time-dependent AUROC
* calibration
* 임상모델 대비 likelihood-ratio test
* decision-curve analysis

비교 순서는 다음이 좋습니다.

1. Grade/PSA/stage
2. 검증된 marker pool만
3. Grade/PSA/stage + marker pool

3번이 1번보다 유의하게 좋아야 “다축 evidence가 실제 가치가 있다”는 주장이 닫힙니다. 이것이 fusion 실험보다 임상적으로 훨씬 강합니다.

## 5. 마커 qualification gate를 사전에 고정해야 합니다

각 후보를 다음 네 가지로 분류하는 것을 추천합니다.

| 등급                               | 정의                                                                     |
| -------------------------------- | ---------------------------------------------------------------------- |
| Portable                         | 외부 zero-refit, cross-site, cross-encoder, confounder-adjusted 분석 모두 통과 |
| Replicable but non-transportable | 외부에서 다시 학습하면 재현되지만 source coefficient는 이전되지 않음                         |
| Context-sensitive                | 특정 site, grade, scanner 또는 encoder에서만 유지                               |
| Null/unsupported                 | 교정 후 유의하지 않거나 방향이 불안정                                                  |

통과 조건에는 최소한 다음이 들어가야 합니다.

* BH-FDR 통과
* 95% CI가 null을 배제
* 사전 정의한 최소 효과크기 충족
* site별 방향 일치
* 임상변수 대비 incremental value
* 외부 frozen transfer
* 최소 두 encoder에서 재현
* target cohort calibration

그러면 현재 결과는 다음과 같은 “reliability map”이 됩니다.

* 강한 portable candidate
* 약하지만 반복되는 candidate
* site-sensitive AR
* null SPOP
* hyperparameter-sensitive ERG fusion
* scale-sensitive transfer failure

이런 구조에서는 실패가 논문의 약점이 아니라 qualification framework가 필요한 근거가 됩니다.

## 6. VLM은 이렇게 해야 가치가 생깁니다

VLM benchmark를 단순 zero-shot 대 in-context 성능 비교로 끝내면 Ferber 등의 연구와 크게 겹칩니다. 이들은 이미 GPT-4V의 병리 분류가 zero-shot에서는 약하지만 ICL로 크게 개선된다는 것을 보였습니다. [Ferber et al.](https://www.nature.com/articles/s41467-024-51465-9)

대신 다음 네 조건을 무작위 교차시험처럼 비교하십시오.

1. Image only
2. Image + 올바른 검증 마커
3. Image + 환자 간 shuffled 마커
4. Marker only

측정값은:

* 진단 정확도
* unsupported finding rate
* calibration
* abstention
* 반복 응답 안정성
* evidence-faithfulness
* 위치 편향
* 올바른 evidence와 잘못된 evidence에 대한 민감도

특히 shuffled marker 조건이 중요합니다. 올바른 evidence를 줬을 때 성능이 좋아지는 것만으로는 VLM이 evidence를 이해했다고 할 수 없습니다. 잘못된 evidence를 줬을 때 맹목적으로 따라가는지까지 봐야 합니다.

이 실험이 성공하면 논문의 마지막 figure에서:

> qualified evidence → better and more faithful reasoning

이라는 bridge를 만들 수 있습니다. 실패해도 “검증된 evidence를 제공하는 것만으로는 안전한 reasoning이 보장되지 않는다”는 중요한 결과가 됩니다.

## 7. 논문의 급을 가장 많이 올리는 세 가지

우선순위를 압축하면 다음과 같습니다.

1. **독립적인 PTEN/ERG 분자 또는 IHC 코호트 확보**

   * 가장 큰 효과
   * 공개 grading 데이터 추가보다 우선

2. **LEOPARD에서 임상모델 대비 재발 예측의 incremental value 입증**

   * “통계적 신호”를 “환자 결과와 연결되는 evidence”로 전환

3. **confounder-controlled, zero-refit transportability matrix**

   * 현재 선행연구와 차별화되는 핵심 방법론

그다음이 공간적 IHC 검증, PANDA-PLUS label-noise 분석, VLM causal bridge 순입니다.

## 8. 현실적인 저널 전망

* 현재 결과 + QWK/그림/논문 재구성: Scientific Reports 가능
* 위 confounder·transport 분석 + LEOPARD: Scientific Reports보다 높은 수준, Journal of Pathology Informatics 또는 npj Precision Oncology 검토 가능
* 독립 PTEN/ERG IHC 코호트 + 공간검증 + 예후 추가가치: Modern Pathology 또는 유사 수준을 진지하게 노릴 수 있음
* 여기에 VLM grounding reader study까지 성공: npj Digital Medicine/Communications Medicine 방향 가능
* Nature Communications: prostate 공개 데이터만 늘리는 정도로는 어렵고, 다른 암종에도 qualification framework가 일반화되거나 독립 다기관 분자검증이 필요

제 최종 권고는 **“6개 마커를 더 잘 예측하는 논문”이 아니라 “통계적으로 보이는 병리 FM 신호 중 어떤 것을 믿을 수 있는지 판정하는 논문”으로 전환하는 것**입니다. 이 방향이 현재 가진 positive·weak·site-sensitive·null 결과를 모두 가장 효율적으로 살리며, 최신 문헌과도 가장 정확하게 맞닿습니다.
