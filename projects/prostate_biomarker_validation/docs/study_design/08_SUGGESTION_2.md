방향은 매우 좋습니다. 기존 논문보다 훨씬 강하고, 무엇보다 지금까지의 실패·null 결과가 모두 살아납니다.

다만 최종 포지션은 이렇게 잡는 것이 가장 안전합니다.

> **우리는 새로운 통계 프레임워크를 발명했다고 주장하지 않는다.
> 대신 병리 파운데이션 모델의 후보 신호를 체계적으로 감사하고, 그 감사를 재현 가능하게 수행하는 사전 정의된 qualification protocol을 실증했다.**

즉,

* 수행한 연구: systematic qualification audit
* 재사용 가능한 방법: prespecified qualification protocol
* 산출물: marker reliability map
* 일반화 가능한 발견: pathology-FM-specific failure modes

입니다.

## 1. “Audit인가, framework인가?”에 대한 최종 답

둘 중 하나를 고를 필요는 있지만, 동일한 비중으로 주장하면 안 됩니다.

### 논문의 실체: audit

실제로 수행한 것은 전립선암 후보 마커들에 대한 체계적인 검증입니다.

* confounder audit
* cross-site 재현성
* cross-encoder 재현성
* replication과 transport 구분
* assay 간 일관성
* 임상 결과와의 연관성
* calibration과 abstention
* null 및 불안정 결과 분류

따라서 결과 문장은 다음처럼 써야 합니다.

> We systematically audited candidate image-derived biomarkers from frozen pathology foundation-model embeddings.

이것은 과장 없이 방어할 수 있습니다.

### 논문의 방법론적 산출물: protocol

그러나 “audit 한 건 했다”로 끝내면 사례 연구처럼 보일 수 있습니다. 따라서 그 감사를 누구나 반복할 수 있도록:

* 입력 후보
* 평가 순서
* 필수 검정
* 통과 기준
* 실패 분류
* 최종 등급

을 고정한 **qualification protocol**로 제시해야 합니다.

> We operationalized a prespecified qualification protocol to distinguish portable, context-sensitive and unsupported signals.

여기서 중요한 단어는 “invented”가 아니라 “operationalized”입니다. 기존 통계 원리를 병리 FM biomarker qualification 과정으로 조합하고 실증했다는 뜻입니다.

### “Framework”는 제한적으로 사용 가능

`framework` 자체가 금지어는 아닙니다. 다만 다음 표현은 위험합니다.

> We propose a novel statistical framework.

반면 다음은 가능합니다.

> We present an empirically evaluated qualification framework.

또는 더 안전하게:

> We present a reusable qualification protocol and reporting structure.

제 추천은 제목과 Abstract에서는 `qualification` 또는 `verification`을 쓰고, Discussion에서만 “the framework can be reused…”라고 표현하는 것입니다.

## 2. 현재 계획에서 반드시 바로잡아야 할 세 가지

### ① LEOPARD는 현재 공식적으로 508명이라고 쓰는 것이 안전

LEOPARD 공식 데이터 페이지는 공개 training set을 **508 cases, 508 unique patients**로 명시합니다. 별도로 validation 99건과 hidden test가 있지만, 라벨 접근성과 환자 수를 구분해야 합니다. [LEOPARD data](https://leopard.grand-challenge.org/data/)

따라서 현재는:

> LEOPARD training cohort: 508 unique patients

라고 쓰고, 실제 다운로드 파일의 manifest를 확인해 570명의 라벨된 고유 환자가 존재할 때만 숫자를 변경해야 합니다. WSI 수와 환자 수, 공개 label과 hidden-test case를 혼합하면 안 됩니다.

### ② PRECISE는 cribriform 검증 데이터가 아님

PRECISE에는 다음 7개 주석이 있습니다.

* malignant glands
* benign glands
* stromal tissue
* IDC-P
* HGPIN
* AIP
* artifact

Cribriform annotation은 명시돼 있지 않습니다. 또한 invasive cribriform carcinoma와 IDC-P는 일부 형태가 겹치지만 동일한 진단이 아닙니다. [PRECISE dataset](https://zenodo.org/records/20721779)

따라서 PRECISE의 역할은 다음처럼 수정해야 합니다.

> H&E-derived phenotype score가 IHC-supported malignant/benign glands 및 intraductal proliferations에 공간적으로 대응하는지를 검증한다.

검증 가능한 것:

* malignant 대 benign gland localization
* model uncertainty와 atypical lesion의 관계
* IDC-P/HGPIN/AIP에서 score distribution
* H&E와 인접 IHC section 간 공간적 일관성
* artifact 영역에서의 false activation

검증할 수 없는 것:

* cribriform-specific localization
* PTEN/ERG/AR target-specific localization
* PRECISE만으로 cribriform mechanism 규명

Cribriform은 SICAPv2 등 실제 cribriform annotation이 있는 데이터로 별도로 다뤄야 합니다.

### ③ TCGA 삼각검증은 “생물학적 증명”이 아니라 “multi-assay concordance”

PTEN CNA–mRNA–RPPA가 모두 같은 방향을 보이는 것은 강한 증거입니다. 하지만 같은 환자 코호트의 서로 상관된 assay이므로 “진짜 생물학적 신호를 증명했다”고 하면 과장입니다.

적절한 표현은:

* biological plausibility
* molecular concordance
* consistency across molecular measurement levels
* multi-assay triangulation

입니다.

특히 강도의 차이를 구분해야 합니다.

| 타깃                            |  삼각검증 강도 | 이유                           |
| ----------------------------- | -------: | ---------------------------- |
| PTEN CNA–mRNA–RPPA            |       강함 | DNA, RNA, protein의 서로 다른 측정층 |
| ERG fusion–ERG expression     |       중간 | 구조변이와 RNA 발현의 일관성            |
| AR expression–AR target score | 상대적으로 약함 | 둘 다 RNA 데이터에서 파생될 가능성이 높음    |

따라서 AR은 “orthogonal assay validation”이 아니라 “pathway-level consistency”로 표현하는 것이 맞습니다.

그리고 이 결과가 grade confounding을 자동으로 배제하지는 않습니다. 반드시 동일 Grade Group 내부에서도 image score와 assay가 연관되는지 확인해야 합니다.

## 3. A·B·C군 평가

### A군: 전부 실행하는 것이 맞음

A군은 논문의 중심입니다.

단, qualification gate를 지금 고정하고, LEOPARD·DiagSet·PRECISE 결과를 보기 전에 timestamp가 남는 형태로 저장하는 것이 좋습니다.

최소한 다음을 사전에 고정하십시오.

* 전체 후보 마커 목록
* 각 마커의 primary label
* confounder 목록
* cross-validation 및 external transfer 방식
* 하이퍼파라미터
* tile size와 물리적 해상도
* primary metric
* 최소 효과크기
* qualification category 정의
* 실패 시 재분석 허용 범위

가능하면 OSF registration 또는 공개 GitHub commit으로 남기십시오. 그렇지 않으면 심사자가 “결과를 본 뒤 통과 기준을 만들었다”고 의심할 수 있습니다.

### B군: 좋지만 각 데이터의 역할을 좁혀야 함

#### LEOPARD: 최우선

가장 강력한 카드라는 판단에 동의합니다. 다만 실험은 새 recurrence 모델을 최적화하는 방향보다, 기존 marker score의 임상적 추가가치를 보는 것이 논문 질문에 맞습니다.

핵심 비교:

1. clinical baseline
2. qualified marker scores
3. clinical baseline + qualified marker scores
4. 전체 후보 마커를 무선별로 넣은 모델

특히 3번이 1번보다 좋고, 4번보다 안정적이면:

> qualification을 통과한 evidence만 사용해야 임상적 이득이 발생한다

는 매우 강한 결과가 됩니다.

지표:

* Harrell C-index
* time-dependent AUC
* integrated Brier score
* calibration slope
* likelihood-ratio test
* decision-curve analysis

주의할 점은 LEOPARD에 실제 제공되는 임상 공변량을 먼저 확인해야 한다는 것입니다. 공개 라벨이 재발 여부와 추적시간만 제공한다면 “grade·PSA·stage를 넘는 incremental value”를 주장할 수 없고, 대신 “outcome association and risk stratification”으로 범위를 줄여야 합니다. [LEOPARD open-data description](https://registry.opendata.aws/leopard/)

#### DiagSet-C: uncertainty validation에 매우 적절

46건으로 성능 비교를 하기에는 작지만, uncertainty 연구에는 적합합니다. [DiagSet](https://www.nature.com/articles/s41598-024-52183-4)

여기서 주요 질문은:

> 모델이 병리의 다수결과 일치하는가?

보다:

> 병리의 간 의견 불일치가 클수록 모델도 낮은 confidence를 보이는가?

가 더 좋습니다.

추천 지표:

* 병리의 판독 entropy
* 다수결 margin
* model predictive entropy
* entropy 간 Spearman correlation
* risk–coverage curve
* selective accuracy
* error detection AUROC
* calibration error

46건은 최종 성능 benchmark가 아니라 **ambiguity stress test**라고 명시해야 합니다.

또한 사람 간 불일치를 모델의 오류로 자동 간주하면 안 됩니다. consensus label, unanimous subset, discordant subset을 분리해야 합니다.

#### PRECISE: spatial validity에는 유용하지만 역할 제한

PRECISE는 phenotype/cancer localization과 ambiguous lesion 분석에는 좋습니다. 하지만 분자마커 pool 전체를 검증해 주지는 않습니다.

따라서 PRECISE 결과는:

> Spatial face validity of image-derived evidence

로 포지셔닝하는 것이 적절합니다.

인접 serial section 사이의 registration 오차도 있으므로 pixel-perfect Dice보다는 다음이 안전합니다.

* gland/ROI-level AUROC
* region-level score enrichment
* annotated-region 대 background effect size
* bootstrapping by patient
* registration tolerance sensitivity

### VLM bridge: 선택 실험으로 유지

Shuffled-marker 대조군까지 넣는 것은 반드시 필요합니다. 그러나 이 실험을 본 논문의 핵심으로 다시 키우지는 않는 것이 좋습니다.

추천 조건:

| 조건                                 | 확인하려는 것                 |
| ---------------------------------- | ----------------------- |
| Image only                         | 직접 시각 판단 baseline       |
| Image + correct evidence           | 검증된 evidence가 도움되는가     |
| Image + shuffled evidence          | 모델이 잘못된 evidence를 맹종하는가 |
| Marker only                        | 이미지 없이 marker만 복창하는가    |
| Image + uncertainty/abstention cue | 위험을 인식하고 보류할 수 있는가      |

이 실험은 최종 Figure 또는 Supplementary proof-of-concept가 적절합니다. 너무 크게 만들면 qualification, survival, uncertainty, spatial validation, VLM이라는 다섯 논문이 한 원고에 섞이는 “kitchen-sink paper”가 될 위험이 있습니다.

## 4. Reliability map의 등급을 조금 수정하는 것이 좋음

기존 네 등급은 좋은데, “portable”은 상당히 높은 표현입니다.

| 등급                       | 권장 정의                                           |
| ------------------------ | ----------------------------------------------- |
| Externally transportable | source probe를 고정한 채 독립 코호트에서 효과와 calibration 유지 |
| Cross-cohort replicable  | 외부 코호트에서 새 probe를 학습하면 같은 방향의 신호 재현             |
| Context-sensitive        | site, grade, scale, encoder 또는 assay에 따라 불안정    |
| Unsupported/null         | 효과크기·CI·다중비교·외부검증 기준 미충족                        |

필요하면 다섯 번째로:

* internally supported but externally untested

를 두는 것이 좋습니다. 현재 독립 분자 코호트가 없는 PTEN·ERG·AR를 무리하게 portable이라고 부르지 않을 수 있기 때문입니다.

예를 들어 TCGA 내부에서 PTEN이:

* CNA, mRNA, RPPA와 모두 일관됨
* grade/site 통제 후 유지됨
* CONCH/Virchow에서 재현됨

이라도 독립적인 PTEN-labeled cohort가 없다면:

> internally qualified and cross-encoder replicable, but externally unverified

가 가장 정확합니다.

## 5. 재사용 가능한 “병리 FM 특이적 교훈”은 이렇게 정리

단순 체크리스트 이상의 기여를 만들려면, 일반 통계 항목과 병리 특이 항목을 분리해야 합니다.

### 일반적인 qualification 원리

* patient-disjoint validation
* FDR와 CI
* calibration
* confounder adjustment
* external validation
* transport와 replication 구분

이것들은 새로 발명했다고 주장하지 않습니다.

### 이 연구에서 실증한 pathology-FM-specific pitfalls

* 물리적 tile scale 불일치가 transfer를 붕괴시킬 수 있음
* site signature가 molecular signal처럼 보일 수 있음
* grade–biomarker 연관이 target-specific morphology로 오인될 수 있음
* encoder가 달라지면 신호 방향 또는 강도가 달라질 수 있음
* assay label의 정의가 달라지면 같은 “마커”도 다른 결과를 낼 수 있음
* fusion은 항상 도움이 되는 것이 아니라, 각 채널의 독립적 유효성과 target alignment가 있을 때만 도움이 됨
* hyperparameter 탐색 차이만으로 경계선 결과가 뒤집힐 수 있음

이러한 함정을 실제 positive/null 사례와 연결하면 “또 하나의 checklist” 이상의 가치가 생깁니다.

다만 fusion 규칙은 다음처럼 조심스럽게 표현해야 합니다.

> Fusion benefited selected target-aligned, individually informative channels in our experiments.

“둘 다 강하면 fusion은 항상 좋아진다”는 일반 법칙으로 주장하면 과도합니다.

## 6. 추천 제목과 Contribution 문장

### 가장 안전한 제목

> **Confounder-aware qualification of pathology foundation-model biomarkers in prostate cancer**

부제 성격을 추가하면:

> **A reliability map across molecular assays, encoders, sites and clinical outcomes**

### 조금 더 구체적인 제목

> **Distinguishing reproducible signals from shortcuts in prostate pathology foundation-model embeddings**

### Abstract의 핵심 두 문장

> Pathology foundation models can yield statistically significant associations with clinical and molecular endpoints, but such associations may reflect grade, site, acquisition or biomarker interdependencies rather than target-specific morphology.

> We conducted a prespecified, confounder-aware qualification study of candidate prostate cancer signals and classified them according to cross-encoder reproducibility, cross-cohort transportability, molecular concordance and clinical relevance.

### Contributions

1. A prespecified and consistently applied qualification protocol—not a newly invented statistical method.
2. An empirical reliability map separating transportable, replicable, context-sensitive and unsupported signals.
3. Multi-assay molecular concordance and confounder-controlled evaluation of candidate markers.
4. Evaluation of whether qualified evidence is associated with actual biochemical recurrence.
5. Identification of reusable pathology-specific failure modes involving scale, site, encoder and fusion.
6. Optional causal test of whether qualified evidence improves or misleads VLM reasoning.

## 7. 실행 순서

1. **Protocol freeze**

   * gate, confounders, endpoints, metrics, scale, categories 고정

2. **A군 재분석**

   * TCGA multi-assay concordance
   * within-grade/site 분석
   * clinical-only/image-only/combined 비교
   * reliability map 초안

3. **LEOPARD**

   * 기존 probe의 zero-refit score 생성
   * survival association
   * 가능한 경우 clinical incremental value

4. **DiagSet-C**

   * uncertainty–human disagreement 분석

5. **PRECISE**

   * malignant/benign/atypical lesion spatial validation
   * cribriform 주장은 제외

6. **원고 핵심 결과가 성립한 뒤 VLM bridge**

   * 본문 또는 Supplement 결정

7. **마지막에 PANDA-PLUS 재검토**

   * 이미 논문이 충분히 강하면 생략 가능
   * label-noise sensitivity가 필요할 때만 추가

## 결론

최종적으로는 “audit 중 하나”라고 축소할 필요도 없고, “새 통계 프레임워크를 발명했다”고 과장할 필요도 없습니다.

가장 정확한 포지션은:

> **전립선암 병리 파운데이션 모델 신호에 대한 체계적인 qualification audit를 수행하고, 그 과정을 재사용 가능한 prespecified verification protocol과 reliability map으로 형식화한 연구**

입니다.

이 방향은 Scientific Reports에는 충분히 강합니다. LEOPARD에서 실제 임상 추가가치가 확인되고, confounder 통제 후에도 핵심 신호가 유지된다면 그보다 높은 저널도 검토할 수 있습니다. 다만 독립적인 PTEN/ERG ground-truth 코호트가 없으므로 “분자마커가 외부에서 임상적으로 검증됐다”는 주장은 여전히 제한해야 합니다.
