## 핵심 결론

이 연구 방향은 충분히 가치가 있고, 현재 계산병리학에서 가장 중요한 연구 주제 가운데 하나입니다. 다만 연구 질문을 세 가지로 분리해야 합니다.

1. AI가 기존 정량 병리 지표를 더 정확하고 재현성 있게 측정하는가?
2. AI가 질병을 판단할 때 기존 지표와 동일한 정보를 사용하는가?
3. 기존 지표로 설명되지 않는 AI 신호가 새로운 생물학적·예후적 지표인가, 아니면 기관·염색·scanner 같은 shortcut인가?

첫 번째 분야는 상당히 성숙했습니다. 두 번째는 활발히 진행 중이며, 세 번째는 2025–2026년에 빠르게 발전했지만 아직 임상적으로 확립된 단계는 아닙니다.

이번 조사는 2026-08-11까지의 PubMed 등재 원저와 핵심 방법론 연구를 중심으로 검토한 구조화된 광범위 서베이입니다. 정식 PRISMA systematic review나 meta-analysis는 아닙니다.

## 1. 기존 정량 지표는 실제로 질병 유무와 진행 정도에 사용되어 왔나?

그렇습니다. 병리 진단 자체가 원래 정량·반정량 지표의 조합입니다.

대표적으로 다음이 있습니다.

* 종양세포와 정상세포의 핵 크기·형태·다형성
* 핵/세포질 비율
* 유사분열 수
* 샘 구조, 관강 크기·원형도·융합·cribriform 형태
* 종양 면적과 침윤 깊이
* tumor budding
* 신경·혈관·림프관 침윤
* 종양–기질 비율
* 면역세포 밀도와 공간적 분포
* IHC 양성 세포 비율과 염색 강도
* Gleason, Nottingham grade 등 형태 조합 점수

AI 이전에도 이러한 특징을 수치화해 암 유무, grade, 재발과 생존을 예측하려는 연구가 있었습니다. 2011년 C-Path 연구는 유방암 상피와 기질에서 6,642개 형태 특징을 추출했고, 기존 grading에서 충분히 고려되지 않던 세 가지 stromal 특징이 독립적으로 생존과 연관된다는 결과를 두 코호트에서 보였습니다. 이는 “새로운 정량 지표 발견”의 초기 대표 사례입니다. [C-Path 원저](https://pubmed.ncbi.nlm.nih.gov/22072638/)

전립선에서도 gland morphometry와 pathomic feature가 생화학적 재발을 구별할 가능성을 보였습니다. 다만 해당 연구는 78명 규모이므로 임상 지표라기보다 후보 biomarker 연구입니다. [전립선 재발 histomorphometry 연구](https://pubmed.ncbi.nlm.nih.gov/37898290/)

즉, 사용자의 가정이 맞습니다. 기존 지표는 이미 진단·등급·진행·예후에 사용되었고, 디지털 병리는 이것을 더 세밀하고 재현성 있게 확장하고 있습니다.

## 2. AI 특징과 기존 정량 지표가 유사한지에 대한 연구 수준

제가 문헌을 종합해 평가한 성숙도는 다음과 같습니다.


| 연구축                                       | 현재 성숙도  | 상태                                                                         |
| -------------------------------------------- | ------------ | ---------------------------------------------------------------------------- |
| 기존 병리지표의 자동 검출·정량              | 높음         | 핵·샘·유사분열·TIL·grade 등의 segmentation과 counting이 다기관 검증 단계 |
| AI 진단과 병리의사 판정 비교                 | 높음         | 전립선 Gleason 등에서 reader study와 전향적 다기관 연구까지 진행             |
| handcrafted feature와 deep feature 성능 비교 | 중간–높음   | 다양한 암종에서 비교됐지만 어느 쪽이 항상 우월하지 않음                      |
| 기존 지표와 AI 내부 표현의 직접적 대응       | 중간         | human-interpretable feature, concept model, probe 연구가 증가 중             |
| 알려진 지표와 AI feature의 결합              | 중간         | 상보적 개선 사례가 있지만 작은 후향 연구가 많음                              |
| AI만 발견한 새 형태·공간 지표               | 중간·급성장 | 다기관·다암종 proof-of-concept가 등장                                       |
| 새 AI 지표의 전향적 임상 유용성 입증         | 낮음–중간   | 임상 endpoint·치료결정까지 확립된 사례는 제한적                             |

따라서 “전혀 연구되지 않은 주제”는 아닙니다. 그러나 알려진 특징과 AI 특징을 체계적으로 비교하고, 잔여 신호에서 새로운 지표를 발견한 뒤 외부 생물학적 검증까지 하는 완전한 연구는 아직 드뭅니다.

## 3. AI가 기존 특징을 실제로 학습한다는 근거

### 해석 가능한 정량 특징으로 black-box 성능을 재현

2021년 Diao 연구는 5개 암종, 5,700개 이상의 표본과 병리의사 주석 160만 개를 사용해 세포·조직·공간 구조를 나타내는 607개 human-interpretable image feature를 만들었습니다. 이 특징만으로 다양한 분자 phenotype을 예측했고, 일부 과제에서 black-box 방식과 비슷한 성능을 보였습니다. [Diao human-interpretable feature 연구](https://pubmed.ncbi.nlm.nih.gov/33712588/)

이 연구의 의미는 “AI가 보는 모든 것이 불가해한 것만은 아니며, 상당 부분을 세포 조성·조직 구조·공간 관계로 설명할 수 있다”는 것입니다.

### 전립선 Gleason concept 모델

2025년 연구는 54명의 국제 병리의사가 정의한 세부 형태 용어를 중간 concept로 사용해 Gleason grading 모델을 만들었습니다. 직접 grade만 출력하는 모델과 비슷하거나 더 나은 segmentation 성능을 보이면서, 판단 근거를 병리 용어로 제시했습니다. [해석 가능한 Gleason AI 연구](https://pubmed.ncbi.nlm.nih.gov/41062516/)

이는 사용자가 제안한 “기존 정량 지표와 AI 판단을 연결하면 정확성과 해석력을 함께 높일 수 있다”는 가설을 직접 구현한 사례에 가깝습니다.

### TIL concept bottleneck

2024년 MuTILs 연구는 종양·기질·림프구를 명시적인 중간 concept로 만들었습니다. 계산된 TIL 점수는 병리의사 육안 점수와 중등도 상관을 보였고, 연구 내에서는 육안 점수보다 높은 예후 정보를 보였습니다. [PanopTILs/MuTILs 연구](https://pubmed.ncbi.nlm.nih.gov/38942745/)

## 4. 기존 특징과 deep feature 중 어느 것이 더 좋은가?

일률적인 답은 없습니다.

전립선암 47명에서 gland·shape·texture pathomic 모델과 ResNet을 직접 비교한 연구에서는 암/비암 구별 정확도가 각각 89%와 88%로 비슷했습니다. 그러나 세부 Gleason pattern 구별에서는 deep feature가 더 나았습니다. [전립선 handcrafted–deep 비교 연구](https://pubmed.ncbi.nlm.nih.gov/36928230/)

간 전이암의 원발 장기를 구별한 연구에서는 다음과 같은 결과가 나왔습니다.

* 일부 암종에서는 deep learning이 우수
* 일부에서는 handcrafted feature와 비슷
* 둘을 결합한 decision fusion은 대체로 조금 개선됐지만 항상 크게 개선된 것은 아님

[Handcrafted–deep feature 결합 연구](https://pubmed.ncbi.nlm.nih.gov/37822044/)

따라서 중요한 것은 “서로 얼마나 비슷한가”만이 아니라 “서로 얼마나 상보적인가”입니다.

* 높은 일치 + 결합 성능 증가 없음: AI가 기존 지표를 재현할 가능성
* 높은 일치 + 결합 성능 증가: AI가 기존 지표를 더 정밀하거나 비선형적으로 측정
* 낮은 일치 + 결합 성능 증가: 잠재적으로 새로운 정보
* 낮은 일치 + 성능 증가 없음: noise 또는 불안정한 특징
* 낮은 일치 + 내부 성능만 높음: shortcut 가능성을 가장 먼저 의심해야 함

## 5. AI와 기존 지표가 일치하면 정확도가 높아지는가?

가능하지만 자동적으로 그런 것은 아닙니다.

전립선 Gleason grading에서는 사람과 AI의 결합이 실제로 성능을 높인 사례가 있습니다.

* 20명의 일반 병리의사와 240개 biopsy를 비교한 reader study에서 AI 보조는 subspecialist consensus와의 일치를 69.7%에서 75.3%로 높였습니다. [JAMA Network Open 연구](https://pubmed.ncbi.nlm.nih.gov/33180129/)
* 14명의 판독자 연구에서는 quadratic weighted kappa가 0.799에서 0.872로 증가했고, 외부 표본에서도 개선됐습니다. [Modern Pathology 연구](https://pubmed.ncbi.nlm.nih.gov/32759979/)
* 2026년 전향적 다기관 연구에서는 AI 보조 후 grade group이 16.5%에서 변경됐고 판독 확신도도 상승했습니다. 다만 AI 보조 전 판정을 기준으로 비교한 순차 설계라는 한계가 있습니다. [전향적 다기관 연구](https://pubmed.ncbi.nlm.nih.gov/42269140/)

하지만 이것은 “AI 특징과 정량 지표의 상관이 높았기 때문에 성능이 좋아졌다”는 직접 증거는 아닙니다. AI가 사람의 누락을 보완하고 사람이 artifact나 예외를 걸러내는 상호보완 효과일 수 있습니다.

또한 기존 지표를 AI 입력에 넣는다고 반드시 좋아지는 것도 아닙니다. 기존 지표와 AI embedding이 같은 정보를 담고 있다면 중복만 늘어날 수 있습니다. 정확성 향상은 동일 환자·동일 fold에서 다음 네 모델을 직접 비교해야 입증됩니다.

1. 임상 변수만
2. 임상 변수 + 기존 정량 지표
3. 임상 변수 + AI score/embedding
4. 임상 변수 + 기존 지표 + AI

마지막 모델이 외부 코호트에서도 discrimination뿐 아니라 calibration과 임상적 의사결정을 개선해야 진정한 상보성이 입증됩니다.

## 6. AI가 기존 지표와 다른 것을 본다는 근거

그러한 근거도 상당합니다.

### H&E에서 분자 상태 예측

* 대장암 MSI는 일상 H&E 영상만으로 예측 가능하다는 연구가 2019년에 나왔습니다. [MSI 연구](https://pubmed.ncbi.nlm.nih.gov/31160815/)
* 이후 8,836개 대장암 표본과 국제 외부 코호트에서 dMMR/MSI 예측이 검증됐습니다. [다기관 MSI 검증](https://pubmed.ncbi.nlm.nih.gov/32562722/)
* 폐암에서는 정상·선암·편평상피암 구별뿐 아니라 EGFR, KRAS, TP53 등 일부 변이를 H&E에서 예측했습니다. [폐암 형태–변이 연구](https://pubmed.ncbi.nlm.nih.gov/30224757/)
* 28개 암종, 17,355개 슬라이드 분석에서는 deep feature가 여러 유전체 이상, 종양 구성과 예후에 연결됐습니다. [범암종 연구](https://pubmed.ncbi.nlm.nih.gov/35122049/)
* 전립선에서는 ERG와 PTEN 상태를 여러 prostatectomy 및 biopsy 코호트에서 예측했고, PTEN heterogeneous case에서 AI 예측 면적과 IHC loss 면적이 상관됐습니다. [전립선 PTEN/ERG 연구](https://pubmed.ncbi.nlm.nih.gov/37307876/)

이 결과들은 사람이 명시적으로 수치화하지 않았던 미세한 형태 신호가 영상에 존재할 가능성을 보여줍니다.

그러나 “AI가 새로운 생물학을 발견했다”는 결론으로 바로 넘어가면 안 됩니다. 분자표지와 grade, 종양 순도, 조직학적 subtype, 동반 변이 등이 서로 연관되어 있기 때문입니다.

2026년 다암종 분석은 일부 molecular prediction이 실제 표적 자체보다 grade와 동반 임상병리 특징을 학습하며, 기존 병리 특징을 넘어서는 이득이 제한적인 경우가 있다고 보고했습니다. [Dawood 등 confounding 연구](https://pubmed.ncbi.nlm.nih.gov/41772176/)

## 7. AI의 새로운 특징을 정량 지표로 바꿀 수 있는가?

가능하며 이미 실제 사례가 나오고 있습니다.

### 새로운 stromal·immune 공간 지표

* C-Path는 기존 grading에 포함되지 않던 stromal morphology를 예후 후보로 발견했습니다. [C-Path](https://pubmed.ncbi.nlm.nih.gov/22072638/)
* 13개 TCGA 암종에서 AI로 TIL 위치를 지도화하고, 단순 밀도뿐 아니라 TIL의 공간구조를 분자 subtype 및 생존과 연결했습니다. [TIL spatial organization 연구](https://pubmed.ncbi.nlm.nih.gov/29617659/)
* 2026년 전립선 연구에서는 면역세포 총량보다 spatially dense immune cluster가 고등급 국소 전립선암의 원격전이 위험과 연관됐고, 별도 validation cohort에서 방향이 재현됐습니다. [전립선 immune spatial biomarker 연구](https://pubmed.ncbi.nlm.nih.gov/42113020/)

### 대규모 공간 biomarker discovery

2026년 PathPrism은 11개 대장암 코호트, 약 7,000명을 이용해 조직구조를 사람이 이해할 수 있는 공간 특징으로 표현했습니다. 생존, MSI, BRAF/TP53 및 항암치료 이득과 관련된 수백 개 후보를 발견했습니다. 이것은 사용자가 구상한 “AI feature를 새로운 정량 지표로 변환”하는 최신 대표 사례입니다. 다만 후보 수가 많고 후향적 분석이므로 개별 biomarker의 임상 유효성은 별도로 검증해야 합니다. [PathPrism 연구](https://pubmed.ncbi.nlm.nih.gov/42276049/)

### H&E에서 virtual spatial protein 지표 생성

HEX 연구는 H&E에서 40개 단백질의 공간 발현을 예측하고, H&E와 virtual proteomics를 결합해 6개 독립 폐암 코호트에서 예후와 면역치료 반응을 평가했습니다. AI feature를 단순 embedding으로 남기지 않고 “공간 단백질 발현”이라는 해석 가능한 새 정량축으로 변환한 사례입니다. [HEX virtual spatial proteomics 연구](https://pubmed.ncbi.nlm.nih.gov/41491099/)

따라서 새로운 지표 생성은 충분히 가능합니다. 다만 새 지표가 되려면 다음 조건이 필요합니다.

* 사람이 재현 가능하게 정의할 수 있어야 함
* 물리 단위 또는 안정된 계산 단위를 가져야 함
* stain·scanner·magnification 변화에 안정적이어야 함
* 다른 환자와 기관에서 재현되어야 함
* IHC, 유전체, spatial omics 또는 임상 outcome과 연결되어야 함
* 기존 grade·stage·임상 변수 이상의 증분 정보를 보여야 함

## 8. “AI와 지표가 일치한다”는 것을 어떻게 측정해야 하나?

단순 상관계수 하나로는 부족합니다. 일치는 다섯 단계로 나눠야 합니다.


| 수준          | 질문                                                   | 적절한 방법                                            | 한계                                       |
| ------------- | ------------------------------------------------------ | ------------------------------------------------------ | ------------------------------------------ |
| 출력 일치     | AI score와 지표가 함께 증가하는가?                     | Spearman, partial correlation                          | 같은 내부 feature를 사용한다는 증거는 아님 |
| 재구성 가능성 | 기존 지표 조합으로 AI score를 얼마나 설명할 수 있는가? | 환자분리 nested-CV`R²`, MAE                           | 비선형 관계와 잔여 신호 분석 필요          |
| 공간 일치     | AI가 주목한 위치와 형태 지표 위치가 겹치는가?          | spatial correlation, Dice/IoU, point–contour distance | attention은 causal explanation이 아님      |
| concept 일치  | AI embedding에 특정 병리 concept가 존재하는가?         | concept probe, TCAV, concept bottleneck                | probe 자체가 과적합될 수 있음              |
| 인과적 의존성 | concept를 바꾸면 AI 판단이 예상대로 변하는가?          | semantic perturbation, ablation, counterfactual        | 생성 artifact와 현실성 검증 필요           |

대표 방법으로는 [TCAV](https://proceedings.mlr.press/v80/kim18d.html), [Concept Bottleneck Model](https://proceedings.mlr.press/v119/koh20a.html), 표현공간 비교를 위한 [CKA](https://proceedings.mlr.press/v97/kornblith19a.html)가 있습니다.

최근에는 counterfactual pathology image를 만들어 어떤 형태 변화가 예측을 바꾸는지 병리의사가 직접 확인하는 방법도 등장했습니다. MSI 예측에서는 mucinous differentiation, gland architecture, lymphocytic infiltration 등이 드러났습니다. 하지만 저자들도 이를 인과 증명보다는 모델 점검과 가설 생성 도구로 제한합니다. [MoPaDi counterfactual 연구](https://pubmed.ncbi.nlm.nih.gov/42308255/)

## 9. 가장 큰 위험: 새 특징이 아니라 shortcut일 수 있다

AI가 기존 지표와 다르다는 사실만으로 새로운 biomarker는 아닙니다.

AI가 볼 수 있는 비생물학적 특징에는 다음이 포함됩니다.

* 병원·기관 고유의 염색
* scanner 제조사와 압축방식
* tissue processing
* annotation 방식
* 슬라이드 테두리·pen mark·배경
* biopsy와 절제술의 차이
* grade, 종양 순도, 환자구성의 불균형

TCGA 분석에서는 기관을 영상만으로 쉽게 구별할 수 있었고, 이 site signature가 변이·병기·생존 예측 성능을 부풀릴 수 있었습니다. 색 정규화만으로도 완전히 제거되지 않았습니다. [site-specific signature 연구](https://pubmed.ncbi.nlm.nih.gov/34285218/)

2026년 PathoROB 연구에서는 평가된 20개 pathology foundation model 모두에서 비생물학적 변화에 대한 robustness 결함이 발견됐으며, 이것이 downstream 진단 오류로 연결될 수 있었습니다. [PathoROB 연구](https://pubmed.ncbi.nlm.nih.gov/42277006/)

따라서 “기존 지표로 설명되지 않는 AI 잔차”는 다음 두 가능성이 섞여 있습니다.

> 새로운 생물학적 형태 신호 + 비생물학적 shortcut

이 둘을 분리하는 것이 연구의 가장 중요한 부분입니다.

## 10. 현재 113개 패키지에 적용할 연구 설계

중요하게도 113개 모두를 AI 입력 feature로 사용하면 안 됩니다.

현재 레지스트리에는 서로 다른 역할이 함께 들어 있습니다.

* 형태·생물학 후보: lumen, nuclear, texture, morphology, contour, spatial IHC
* AI 출력: prototype score, text-PNI score, combined score, rank
* outcome·평가 지표: capture, precision, AUROC, AP, C-index
* 통계·QC: bootstrap, missingness, hash reconciliation

AUROC, C-index, bootstrap CI는 환자 특징이 아니라 평가 방법입니다. 이를 feature로 투입하면 의미 오류 또는 leakage가 생깁니다. 먼저 다음 `metric_role` 분류가 필요합니다.

* `biological_feature`
* `ai_output`
* `clinical_outcome`
* `performance_metric`
* `quality_control`
* `derived_comparison`

그다음 연구를 다음처럼 구성하는 것이 좋습니다.

### 단계 A: 기존 지표가 AI 판단을 얼마나 설명하는가

AI score를 `S`, 기존 정량 특징을 `M`, 임상·기관 변수를 `C`라고 두면:

* 개별 연관: `corr(S, Mj | C)`
* 전체 설명력: 환자분리 nested CV로 `M → S`의 out-of-sample `R²`
* 지표군별 설명력: gland, nuclear, texture, immune, nerve-interface별 incremental `R²`
* embedding 비교: CKA 또는 regularized CCA
* 공간 비교: AI attention 또는 candidate 위치와 feature map/contour의 일치

높은 cross-validated `R²`는 AI score의 상당 부분이 기존 지표로 설명된다는 의미입니다.

### 단계 B: 질병 예측에서 중복성과 상보성 평가

동일한 환자 split으로 다음을 비교합니다.

* `C`
* `C + M`
* `C + S`
* `C + M + S`

Endpoint별 평가는 다음처럼 달라야 합니다.

* 암 유무: AUROC, AP, sensitivity/specificity, calibration
* Gleason/ISUP: QWK, confusion matrix, clinically important grade boundary
* PNI 후보 triage: capture와 완전 판독 budget에서만 precision
* 재발·전이: C-index, time-dependent AUC, IBS, calibration
* 치료반응: 외부 또는 전향 cohort의 discrimination과 calibration

`C + M + S`가 외부검증에서 `C + M`과 `C + S`를 모두 넘어야 진정한 상보적 가치가 있습니다.

### 단계 C: AI 잔차에서 새 지표 탐색

다음 잔차를 만듭니다.

```
AI residual = observed AI score
              − score predicted from known metrics and confounders
```

그 후:

1. 높은 양·음의 잔차 patch를 수집
2. 환자·score·outcome을 가린 상태로 병리의사가 검토
3. 반복 형태를 prototype 또는 concept로 명명
4. 핵·샘·세포·공간 graph로 수치화
5. interobserver reproducibility와 자동측정 안정성 검증
6. 새로운 환자·기관에서 endpoint 연관성 재검증
7. IHC 또는 spatial omics로 생물학적 근거 확인

이 과정을 통과해야 “AI가 발견한 새 정량 지표”라고 부를 수 있습니다.

## 11. 우리 프로젝트에서의 현실적 가치

연구 아이디어 자체의 가치는 높습니다. 하지만 현재 PRECISE 자료만으로 가능한 주장에는 제한이 있습니다.

현재 검증된 시스템 역할은 공간적으로 구별된 PNI 후보를 병리 검토 순서로 정렬하는 것입니다. whole-slide PNI 진단기가 아닙니다.

또한:

* 선택된 audit 후보 120개
* morphology 재검토 focus 14개
* contour 지표는 전문의 경계 승인 전 계산 불가

이 규모로 수십 개 feature를 이용해 새로운 임상 biomarker를 학습하면 심각한 과적합과 선택편향이 발생합니다.

현재 자료로 가능한 연구:

* frozen AI score와 기존 형태·공간 지표의 정렬 가능성 평가
* AI가 기존 지표로 얼마나 설명되는지 확인하는 방법론 pilot
* residual prototype에 대한 blinded hypothesis generation
* 후속 다기관 연구의 feature shortlist 도출

현재 자료로 불가능한 주장:

* 새로운 PNI 진단 biomarker 확립
* whole-slide 민감도
* PRECISE 환자의 PNI 형태 분포
* 재발·생존 예측
* 타 암종으로의 전이 성능
* 임상 치료결정 유용성

## 최종 가치 판단

단순히 113개 지표와 AI score의 상관을 계산하는 연구라면 새로움은 제한적입니다.

반면 다음까지 수행하면 의미가 매우 커집니다.

> 기존 지표가 AI 판단을 얼마나 설명하는지 정량화하고, 기존 지표 이상의 예측 증분을 외부검증하며, 설명되지 않는 AI 잔차에서 새로운 형태·공간 concept를 발견하고, 이를 IHC·공간 omics·독립 임상 outcome으로 검증하는 연구

이 구조는 다음 네 가지를 동시에 제공합니다.

* AI의 정확성 및 안전성 감사
* 병리의사가 이해할 수 있는 설명
* 기존 지표와 AI의 상보성 검증
* 새로운 digital pathology biomarker 발견

따라서 연구 가치 자체는 높습니다. 가장 좋은 핵심 질문은 “AI와 기존 지표가 얼마나 일치하는가?”보다 한 단계 더 나아간 다음 질문입니다.

> AI 판단 중 기존 병리 지표로 재현되는 부분, 상보적인 생물학적 부분, 비생물학적 shortcut 부분을 각각 얼마나 분리할 수 있는가?
>




## 핵심 결론

네, 제안하신 방법은 충분히 가치가 있습니다. 다만 다음 구분이 중요합니다.

> **AI–정량지표 일치도는 외부 코호트에서 AI의 ‘정확도’를 직접 증명하는 지표가 아니라, AI가 학습 코호트에서 보던 병리학적 관계를 여전히 보고 있는지 평가하는 ‘의미적 안정성·이식가능성 지표’입니다.**

따라서 일치도를 다음 용도로 쓰는 것은 타당합니다.

* 외부 코호트 성능 저하의 조기경보
* 성능 재검증이 필요한 코호트·슬라이드 선별
* 기술적 domain shift와 생물학적 population shift의 원인 분석
* AI가 기존 지표와 다른 새로운 형태학적 신호를 사용하는지 탐색

하지만 ground truth 없이 일치도만으로 민감도·특이도·AUROC를 추정하거나 “안전하게 사용할 수 있다”고 판정해서는 안 됩니다.

## 1. 먼저 ‘코호트 품질’ 문제를 네 종류로 나눠야 합니다

외부 코호트에서 성능이 떨어지는 원인을 모두 영상 품질이라고 부르면 원인을 잘못 해석할 수 있습니다.

1. 기술적 품질 변화
   염색 강도, 절편 두께, 초점, tissue fold, 압축, 스캐너, 해상도 차이입니다.
2. 환자·검체 구성 변화
   암 유병률, grade, 병기, 치료 이력, 인종, 생검과 전립선절제술의 차이입니다.
3. 질병 표현형 변화
   학습 코호트에 적었던 희귀 형태, cribriform, intraductal carcinoma, 염증성 모방 병변, 다양한 PNI 형태가 증가하는 경우입니다.
4. 참조표준 변화
   기관별 판독 기준, 병리의 간 합의, uncertain 처리, sampling 방식이 다른 경우입니다.

전립선암에서는 이 문제가 실증적으로 확인됐습니다. 6개 코호트·25,591명·83,864개 이미지를 분석한 연구에서 절편 두께와 염색 시간 같은 표본 처리 변화가 AI grading 성능을 최대 8.6 percentage points 감소시켰습니다. 반면 고변이 데이터 학습과 domain-robust 방법은 성능을 상당 부분 회복했습니다. [전립선암 데이터 변이 연구](https://pubmed.ncbi.nlm.nih.gov/41308537/)

그러나 domain shift가 항상 성능 저하를 만드는 것은 아닙니다. 생검으로 학습된 전립선 AI를 별도 기관의 전립선절제술 표본에 적용한 연구에서는 전문가 기준과 grade-group weighted κ=0.89를 보였습니다. 즉, “코호트가 다르다”와 “AI가 틀린다”는 같은 명제가 아닙니다. [전립선 AI 외부검증 연구](https://pubmed.ncbi.nlm.nih.gov/38989669/)

## 2. 관련 연구는 어디까지 진행됐는가


| 연구 분야                                                   | 현재 성숙도 | 판단                                             |
| ----------------------------------------------------------- | ----------- | ------------------------------------------------ |
| 슬라이드 품질 정량화                                        | 높음        | 실제 운영 가능                                   |
| stain·scanner domain shift 측정                            | 중상        | 방법론과 다기관 검증이 상당함                    |
| OOD·불확실성 탐지                                          | 중간        | 경보에는 유용하나 실제 오류와 항상 일치하지 않음 |
| 라벨 없는 외부 성능 추정                                    | 초기–중간  | 빠르게 발전하지만 실패 조건이 많음               |
| AI와 해석 가능한 병리 개념의 대응                           | 중간        | 설명·생물학적 해석 연구가 활발                  |
| AI–기존 정량지표 관계를 외부 코호트 acceptance gate로 사용 | 초기        | 직접 검증은 드물고 연구 가치가 큼                |

HistoQC는 염색, blur, fold, contrast 등 슬라이드 품질을 자동으로 정량화했고, 이러한 QC 접근은 현재 가장 성숙한 층입니다. [HistoQC 연구](https://pubmed.ncbi.nlm.nih.gov/30990737/) 염색 차이가 4개 장기·9개 병리검사실 사이에서 CNN 일반화를 저하시킬 수 있다는 연구와, 미지의 스캐너를 포함한 MIDOG 연구도 기술적 domain shift를 확립했습니다. [염색 변이 연구](https://pubmed.ncbi.nlm.nih.gov/31466046/), [MIDOG 연구](https://pubmed.ncbi.nlm.nih.gov/36463832/)

그다음 단계는 이미지 또는 AI embedding의 분포 변화를 측정하는 것입니다. Stacke 등의 representation-shift 지표는 여러 종류의 histopathology domain shift에서 성능 저하와 높은 상관성을 보였습니다. [Representation-shift 연구](https://pubmed.ncbi.nlm.nih.gov/33085623/) OOD 불확실성도 전체 슬라이드 수준에서 상당한 탐지력을 보였지만, 가까운 OOD와 먼 OOD에서 최적 방법이 달랐고 예상되는 OOD에 맞춘 조정이 필요했습니다. [병리 OOD 불확실성 연구](https://pubmed.ncbi.nlm.nih.gov/36306568/)

중요하게도, 분포 변화 자체가 성능 저하와 동일하지는 않습니다. 최근 pathology VLM 연구에서는 두 외부 사이트 모두 큰 입력 shift를 보였지만 한 사이트에서는 AUROC가 약 0.25 하락한 반면 다른 사이트에서는 거의 하락하지 않았습니다. 이 연구는 아직 preprint이고 외부 사이트가 두 곳뿐이지만, 입력 shift만으로 실제 성능을 판단할 수 없다는 점을 잘 보여줍니다. [Pathology VLM degradation 연구](https://arxiv.org/abs/2601.00716)

실제 의료영상 운영에서도 비슷한 방향이 시작됐습니다.

* CheXstray는 영상 표현, metadata, AI 출력의 변화를 결합하여 라벨 없는 drift 경보를 만들었습니다. [CheXstray](https://doi.org/10.1007/978-3-031-43898-1_32)
* ACR Assess-AI는 AI 출력과 보고서에서 추출한 surrogate label의 concordance를 시간별로 모니터링하고 discordant case를 재검토하도록 설계됐습니다. [ACR Assess-AI](https://pubmed.ncbi.nlm.nih.gov/42066927/)
* 여러 영상의학 학회의 공동 지침도 AI–전문의 판독 concordance와 입력 데이터 drift를 함께 감시할 것을 제안합니다. [다학회 AI 모니터링 지침](https://pmc.ncbi.nlm.nih.gov/articles/PMC10800328/)

따라서 사용자의 아이디어는 기존 monitoring 연구와 직접 연결됩니다. 새로운 부분은 영상 metadata나 AI confidence를 넘어서, **독립적인 병리 정량지표를 생물학적 기준축으로 추가한다는 것**입니다.

## 3. 일치도를 어떻게 정의해야 하는가

AI의 이진 판정과 지표의 임의 threshold만 비교하면 정보가 많이 손실됩니다. 가능한 한 연속값과 공간정보를 보존해야 합니다.

기호를 다음과 같이 두겠습니다.

* \\(S\\): 동결된 AI의 연속 disease/candidate score
* \\(M\\): 기존 정량지표 벡터
* \\(Q\\): 염색·초점·조직량 등 기술적 QC
* \\(C\\): grade, specimen type, 기관, 환자 구성
* \\(Y\\): 병리의 또는 임상·분자학적 ground truth

학습 코호트에서 다음 관계를 교차검증으로 확립하고 고정합니다.

\\[ S \\approx g(M,C,Q) \\]외부 코호트에서는 모델을 다시 맞추지 않고 다음을 계산합니다.

* 개별 지표와 AI score의 partial Spearman correlation
* 여러 지표가 AI score를 설명하는 cross-validated \\(R^2\\)
* \\(S-g(M,C,Q)\\) residual의 source–target 변화
* 정량지표별 calibration slope와 intercept
* 병변·신경·세포 수준 spatial overlap 및 distance
* 범주형 결과라면 positive/negative agreement와 κ
* source와 target의 관계가 같은지를 보는 interaction test

여기서 가장 중요한 지표는 단순 상관계수보다 **관계의 보존성**입니다. 외부 코호트에서 정량지표 분포가 달라져도 \\(S\\)와 \\(M\\) 사이의 조건부 관계가 유지된다면, AI가 여전히 유사한 병리 개념을 사용하고 있다는 근거가 됩니다.

## 4. 권장하는 외부 코호트 판정 구조

단일 “일치도 점수”보다는 네 단계 gate가 안전합니다.

1. Technical QC gate
   blur, fold, stain, tissue area, resolution, scanner와 절편 조건을 검사합니다.
2. Distribution-shift gate
   색상·embedding·metadata·AI 출력 분포의 MMD, Wasserstein distance, domain-classifier AUROC 등을 측정합니다.
3. Semantic-concordance gate
   AI score와 독립적인 기존 정량지표 사이의 source 관계가 target에서도 유지되는지 평가합니다.
4. Sentinel-label gate
   외부 코호트의 일부를 무작위 또는 위험도 층화 방식으로 병리의가 판독하여 실제 민감도, 특이도, calibration 및 오류 유형을 측정합니다.

1–3단계는 “재검증이 필요한가?”를 판단하는 경보이고, 실제 정확성을 확정할 수 있는 것은 4단계입니다.

## 5. 일치도와 실제 성능의 해석


| AI–지표 일치도 | 실제 외부 성능 | 가능한 해석                                                                     |
| --------------- | -------------- | ------------------------------------------------------------------------------- |
| 높음            | 높음           | 기존 병리 개념을 안정적으로 transport                                           |
| 낮음            | 낮음           | 기술적 drift, 표현형 변화 또는 모델 실패 가능성                                 |
| 낮음            | 높음           | AI가 기존 지표에 없는 유효한 신호를 사용하거나 지표가 불완전                    |
| 높음            | 낮음           | 가장 위험: AI와 지표가 동일 artifact·grade·site shortcut에 함께 속았을 가능성 |

마지막 경우 때문에 “높은 일치도=높은 정확도”로 간주하면 안 됩니다. 예를 들어 AI와 정량지표 추출기가 모두 같은 segmentation model이나 stain-sensitive nucleus detector를 사용한다면 함께 틀리면서도 높은 일치도를 보일 수 있습니다.

## 6. 기존 113개 지표를 사용할 때의 핵심 조건

113개 전체를 일치도 분석에 동일하게 넣으면 안 됩니다. 역할별로 분리해야 합니다.

* 독립 biological/morphometric metrics
  신경 밀도, 종양–신경 거리, 신경 둘레 침범률, gland architecture, 핵 형태, tumor/stroma 비율, 염증세포 밀도 등
* Technical QC metrics
  stain, blur, tissue area, focus, compression 등
* Model-derived metrics
  AI probability, attention, 결합점수, percentile, rank 등
* Evaluation endpoints
  ROC-AUC, precision, capture fraction, C-index 등

AI 판단과의 독립적 concordance 기준에는 첫 번째 범주가 중심이 되어야 합니다. AI probability나 AI에서 만들어진 rank로 같은 AI를 검증하면 순환논리가 됩니다. QC는 원인 설명 변수이고, 평가 endpoint는 검증 결과이지 입력 지표가 아닙니다.

## 7. 새로운 정량지표 발견으로 연결하는 방법

기존 지표로 설명되지 않는 AI 신호는 다음 residual로 정의할 수 있습니다.

\\[ R\_{\\text{novel}}=S-g(M,C,Q) \\]높거나 낮은 residual 영역을 모아 병리의가 blinded review하면 됩니다. 새로운 지표 후보가 되려면 최소한 다음을 통과해야 합니다.

* 여러 스캐너·염색 조건에서 반복 측정 가능
* 기존 113개 지표로 설명되지 않는 incremental information
* 병리의가 명명하거나 재현 가능한 형태학적 정의를 부여할 수 있음
* 독립 코호트에서 질병·진행·예후와 연관
* 가능하면 IHC, spatial omics, genomic alteration 같은 별도 생물학적 측정과 연관
* AI 없이도 계산 가능한 명시적 알고리즘으로 환원

이 과정을 거치면 “AI attention이 특이해 보인다” 수준에서 실제 quantitative biomarker candidate로 발전시킬 수 있습니다.

## 8. 이 연구의 가치와 가장 강한 연구 질문

가장 강한 질문은 다음과 같습니다.

> 독립적인 병리 정량개념의 source–target 관계 보존성이 QC, embedding shift, AI uncertainty만 사용하는 방법보다 동결된 병리 AI의 외부 성능 저하를 더 잘 예측하는가?

비교군은 다음처럼 구성하는 것이 좋습니다.

* QC only
* image/embedding shift only
* AI confidence/OOD only
* quantitative-metric concordance only
* 위 신호를 모두 결합한 모델

여러 독립 기관에서 실제 성능 저하량—예: \\(\\Delta\\)AUROC, \\(\\Delta\\)weighted-κ, calibration error—을 측정하고, 어떤 경보가 이를 가장 잘 예측하는지 검증해야 합니다. 패치 수가 많아도 기관이 두 곳뿐이면 cohort-level 예측 연구로는 약합니다. 다양한 스캐너·염색·검체 유형을 가진 여러 독립 기관이 핵심입니다.

## PRECISE PNI 프로젝트에 대한 적용 범위

현재 PRECISE PNI 시스템의 검증된 역할은 **병리의 검토를 위한 공간적으로 구분된 후보 영역의 triage/ranking**입니다. 따라서 첫 연구의 endpoint도 다음처럼 제한해야 합니다.

* 외부 코호트에서 PNI 후보 score와 독립 신경–종양 정량지표의 관계 보존
* top-ranked candidate가 형태학적으로 평가 가능한지
* discordant candidate에서 오류 유형 또는 신규 형태가 발견되는지
* 소규모 sentinel review에서 candidate-level 성능 저하가 실제로 발생하는지

현재의 선별 검토 표본만으로 whole-slide PNI 진단 정확도, 환자 유병률, whole-slide sensitivity를 주장할 수는 없습니다. 또한 frozen-score audit 중에는 재학습이나 재보정을 하지 않고, 이 분석을 별도의 외부 이식성·의미적 일치성 연구로 설계해야 합니다.

최종 판단은 다음과 같습니다.

> **연구 가치는 높습니다.** 다만 “정량지표 일치도로 정확성을 대신한다”가 아니라, “정량지표 일치도를 기존 QC·OOD 방법에 추가하여 외부 성능 저하를 더 일찍, 더 생물학적으로 설명 가능하게 탐지한다”가 과학적으로 가장 강하고 안전한 주장입니다. 현재 문헌상 구성요소들은 충분히 존재하지만, 이를 병리 정량지표 수준에서 통합하고 다기관 실제 성능 저하에 대해 검증한 연구는 아직 드뭅니다. 이것이 바로 이 연구의 신규성과 의미입니다.


네. 오히려 가장 좋은 첫 실험입니다. 현재 프로젝트의 두 기반 모델을 CONCH와 Virchow로 보면, 이를 **동일 샘플·동일 좌표·동일 물리적 시야에서 비교하는 paired quantitative-concept benchmark**로 설계할 수 있습니다.

이미 두 모델은 동결 인코더로 사용 중이며 차원과 입력 크기가 다릅니다. [모델 정의 (line 32)](/home/jinhyun/prj\_ws/prj\_jin/vlm-pathology/paper/sections/cohorts\_encoders.tex:32)

## 무엇을 비교할 수 있나

각 정량지표 \\(M\_j\\)에 대해 두 모델의 출력을 비교합니다.


| 정량 표적                            | 평가 방법                                                      |
| ------------------------------------ | -------------------------------------------------------------- |
| Gleason/ISUP 같은 순서형 지표        | Spearman, QWK, MAE                                             |
| 종양/정상, PTEN loss 같은 이진 지표  | AUROC, AUPRC, calibration                                      |
| 핵·선구조·신경 거리 같은 연속 지표 | Spearman,\\(R^2\\), MAE, concordance correlation               |
| contour·공간 지표                   | Dice/IoU, contact length, encasement fraction, 거리오차        |
| 두 모델의 판단 유사성                | score correlation, categorical agreement, discordant-case 분석 |
| 내부 feature 유사성                  | CKA·CCA 또는 pairwise representation similarity               |

CONCH의 512차원과 Virchow의 2,560차원 좌표를 직접 상관시키면 안 됩니다. 대신 두 embedding에서 동일한 정량지표를 예측하는 작은 probe를 각각 만들거나, 차원에 무관한 CKA·representation similarity를 사용해야 합니다.

## 이미 상당 부분은 수행돼 있습니다

현재 연구에서는 Gleason, phenotype, ERG, PTEN, SPOP, AR, recurrence에 대해 두 모델을 비교했습니다.

* Gleason, phenotype, PTEN은 두 모델이 비교적 유사했습니다.
* ERG 관련 신호는 Virchow에서 더 강했습니다.
* SPOP은 두 모델과 설정에 따라 chance 위·아래를 오가며 불안정했습니다.
* recurrence는 CONCH와 Virchow 사이에서 가장 큰 차이를 보였고 scale에도 영향을 받았습니다.

즉, 이미 결과가 “모델들이 항상 같은 feature를 보는 것은 아니다”라는 사용자의 가설을 지지합니다. [현재 cross-encoder 결과 (line 87)](/home/jinhyun/prj\_ws/prj\_jin/vlm-pathology/paper/sections/core\_marker\_results.tex:87)

하지만 현재 분석은 주로 disease/molecular endpoint와의 연관성을 비교한 것입니다. 사용자가 제안한 연구는 이를 **세포·선구조·신경·공간 형태 지표까지 확장**하는 것입니다.

## 113개 전체를 넣으면 안 되는 이유

113개 중에는 생물학적 feature뿐 아니라 평가통계, bootstrap, 재현성, 모델 점수, 생존분석 지표가 섞여 있습니다. [113개 영역 구성 (line 15)](/home/jinhyun/prj\_ws/prj\_jin/vlm-pathology/docs/12\_QUANTITATIVE\_METRICS\_PACKAGE\_KO.md:15)

첫 비교에는 다음만 포함하는 것이 좋습니다.

* 독립적으로 측정된 morphology·contour·spatial·IHC 지표
* 실제 pathologist Gleason/ISUP
* 독립 분자검사 결과: PTEN, ERG, SPOP, AR 등
* 독립 임상 outcome

다음은 제외하거나 별도로 취급해야 합니다.

* CONCH score, combined score, rank처럼 한 모델에서 유래한 값
* AUROC, bootstrap CI 같은 평가 방법 자체
* 같은 AI segmentation으로 만들어져 두 모델과 독립적이지 않은 지표
* 아직 승인되지 않은 contour 지표

현재 contour 6개 지표는 병리의가 신경 경계와 암–신경 interface를 승인한 후에만 계산하도록 유보돼 있습니다. [지표 상태와 제한 (line 31)](/home/jinhyun/prj\_ws/prj\_jin/vlm-pathology/docs/12\_QUANTITATIVE\_METRICS\_PACKAGE\_KO.md:31)

## 공정한 비교 설계

두 모델에 반드시 같은 조건을 적용해야 합니다.

1. 동일 환자와 동일 ROI 좌표를 사용합니다.
2. 동일한 물리적 시야와 해상도에서 비교합니다.
3. 모델 가중치는 동결합니다.
4. 필요하면 동일 구조의 작은 linear probe만 source cohort에서 학습합니다.
5. 동일한 patient-grouped split을 두 모델에 적용합니다.
6. 결과는 같은 환자를 묶은 paired bootstrap으로 비교합니다.
7. native scale 결과와 shared scale 결과를 분리합니다.
8. 외부 코호트에는 probe와 threshold를 재학습하지 않습니다.

현재 Gate A가 native/shared scale, 16·32·64 tiles, 5개 sampling seed를 이미 다루고 있으므로 상당한 기반이 마련돼 있습니다. 다만 이 반복 설정들은 독립 코호트가 아니라 correlated sensitivity analysis입니다. [현재 안정성 설계 (line 86)](/home/jinhyun/prj\_ws/prj\_jin/vlm-pathology/paper/sections/cohorts\_encoders.tex:86)

## 결과 해석

* 두 모델 모두 같은 정량지표를 잘 복원하고 외부 코호트에서도 유지
  → 모델 종류를 넘어선 안정적 병리 신호일 가능성
* 한 모델만 정량지표와 일치
  → encoder-specific representation 또는 scale 영향
* 두 모델이 기존 지표와 불일치하지만 실제 질병 성능은 좋음
  → 새로운 형태학적 feature 후보
* 두 모델 모두 기존 지표와 일치하지만 실제 성능은 낮음
  → grade, stain, scanner 같은 공통 confounder에 함께 의존했을 가능성
* 두 모델끼리도 다르고 기존 지표와도 불일치
  → 불안정한 신호 또는 target cohort OOD 가능성

## 가장 현실적인 진행 순서

1. 기존 자료로 Gleason, phenotype, PTEN, ERG, AR, SPOP의 CONCH–Virchow paired benchmark를 재구성합니다.
2. PRECISE에서 이미 측정 가능한 spatial/IHC/texture 지표를 추가합니다.
3. 병리의 contour가 확정되면 nerve diameter, encasement fraction, contact length, distance gradient를 추가합니다.
4. 두 모델과 기존 지표가 설명하지 못하는 공통 residual을 새로운 정량지표 후보로 검토합니다.
5. 마지막으로 독립 외부 PNI 코호트에서 실제 성능 저하 예측력을 검증합니다.

다만 PRECISE의 14개 nerve-positive focus는 개념증명과 오류분석에는 사용할 수 있지만, 두 모델의 whole-slide PNI 진단 정확도나 전체 PNI 형태 분포를 비교하는 표본으로는 부족합니다.

따라서 결론은 **가능하며, 기존 인프라를 상당 부분 재사용할 수 있다**입니다. 현재 수행된 cross-encoder 분석을 “질병 endpoint 비교”에서 “독립 정량형태 지표에 대한 모델별 개념 복원 및 외부 안정성 비교”로 확장하는 것이 정확한 연구 설계입니다. 만약 말씀하신 두 모델이 CONCH·Virchow가 아니라 LLaVA-Med·Quilt-LLaVA를 의미한다면 동일한 틀을 적용하되, 자유형 응답을 먼저 고정된 수치 score로 변환하는 절차가 추가로 필요합니다.
