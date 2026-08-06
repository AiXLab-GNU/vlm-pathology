한 문장으로 평가하면:

> **계획대로 엄밀하게 수행하면 Scientific Reports에는 충분히 경쟁력 있는 논문이며, LEOPARD에서 임상적 추가가치까지 명확히 나오면 Communications Medicine·Modern Pathology·npj Precision Oncology에 도전해 볼 수 있는 수준입니다.**
> 다만 독립 분자 코호트가 없으므로 Nature Communications 이상을 정면 목표로 하기에는 아직 한계가 있습니다.

## 결과에 따른 현실적인 저널 수준

| 최종 결과                                                                             | 논문의 수준                                                 | 적합한 목표                                                   |
| --------------------------------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------- |
| Confounder audit와 reliability map은 완성됐지만 LEOPARD는 단순 연관성, PRECISE/DiagSet 결과는 보조적 | 엄밀한 질환 특이적 verification study                          | **Scientific Reports**, Journal of Pathology Informatics |
| LEOPARD에서 qualified marker pool이 재발을 유의하게 층화하고 calibration도 양호                    | 임상 결과가 연결된 translational computational-pathology study | **Modern Pathology**, npj Precision Oncology 도전          |
| 임상모델 대비 qualified marker pool의 유의한 추가가치가 있고, unqualified pool보다 명확히 우수            | qualification의 임상적 필요성을 실증한 강한 방법론·중개연구                | **Communications Medicine** 우선 도전 가능                     |
| 독립 PTEN/ERG 코호트 또는 다암종 일반화까지 추가                                                   | 일반성이 있는 biomarker qualification 연구                     | Nature Communications 도전 가능                              |
| VLM bridge + 병리의 reader study + 임상 workflow 효과                                    | 임상 디지털 AI 연구                                           | npj Digital Medicine 가능                                  |

## 현재 계획의 예상 위치

현재 확정안은 단순한 Scientific Reports용 논문보다 한 단계 높은 잠재력이 있습니다. 이유는 결과의 범위가 넓어서가 아니라, 다음의 일관된 질문을 닫을 수 있기 때문입니다.

> “내부적으로 유의한 후보를 qualification하면, 실제로 더 이식 가능하고 더 잘 보정되며 임상 결과와 더 관련된 evidence pool이 되는가?”

그러나 현재 상태에서 가장 직접적으로 겹치는 강력한 선행연구가 있습니다.

* Dawood 등은 8,221명을 이용해 biomarker interdependency, grade confounding, 외부 코호트, incremental value를 분석하고 stratification-based evaluation framework를 이미 제안했습니다. [Nature Biomedical Engineering, 2026](https://www.nature.com/articles/s41551-026-01616-8)
* PathoROB은 20개 파운데이션 모델에서 기관·기술적 신호와 생물학적 신호를 분리하는 robustness benchmark를 제시했습니다. [Nature Communications, 2026](https://www.nature.com/articles/s41467-026-73923-2)
* Bareja 등은 32개 모델, 41개 과제를 standardized linear probing과 fusion으로 비교했습니다. [Nature Communications, 2026](https://www.nature.com/articles/s41467-026-76004-6_reference.pdf)

따라서 우리 논문이 “confounding을 검사했다”, “여러 모델을 비교했다”에서 끝나면 규모 면에서 이 논문들을 이기기 어렵습니다.

우리 논문의 차별점은 반드시 다음이어야 합니다.

> **단순히 confounding을 발견한 것이 아니라, qualification 결과에 따라 marker 선택이 달라지고, 그 선택이 독립 임상 결과에서 실제 차이를 만든다는 것.**

## 논문의 급을 결정할 가장 중요한 Figure

가장 중요한 결과는 marker별 AUROC forest plot만이 아닙니다. 다음 비교가 논문의 중심이 되어야 합니다.

### LEOPARD에서 비교할 세 가지 evidence pool

1. Naïve pool
   내부 p-value 또는 CV 성능만으로 선택한 후보

2. Qualified pool
   confounder, cross-encoder, scale, site, molecular concordance gate를 통과한 후보

3. All-candidate pool
   null·context-sensitive 후보까지 모두 포함

그리고 LEOPARD에서 다음을 비교합니다.

* C-index
* time-dependent AUROC
* integrated Brier score
* calibration
* risk stratification
* 가능하면 clinical baseline 대비 증가분
* decision-curve net benefit

만약 결과가 다음과 같이 나온다면 매우 강합니다.

> Qualified pool은 naïve/all-candidate pool보다 외부 재발 예측과 calibration이 우수했고, null 또는 context-sensitive marker를 포함하면 성능이 감소하거나 불안정해졌다.

이 결과가 나오면 qualification protocol은 단순 체크리스트가 아니라 **consequential validation strategy**, 즉 실제 결과를 개선하는 검증 전략이 됩니다.

## 상위 저널로 가기 위한 성공 조건

### Communications Medicine 도전 조건

Communications Medicine은 retrospective 연구도 받지만, 분야의 사고방식에 영향을 줄 정도의 임상·중개적 진전을 요구합니다. [공식 범위](https://www.nature.com/commsmed/aims)

다음 중 대부분이 필요합니다.

* protocol이 새 결과를 보기 전에 고정됨
* qualified pool이 LEOPARD 재발과 유의하게 연관
* clinical baseline이 있다면 유의한 incremental value
* naïve selection보다 qualification selection이 우수
* external calibration까지 보고
* DiagSet-C와 PRECISE가 동일한 reliability story를 지지
* 코드·split·qualification decision table 공개
* CLAIM/TRIPOD+AI에 맞춘 보고

이 조건이 충족되면 Communications Medicine에 한 번 도전할 가치가 있습니다. 다만 “임상 활용 가능성”보다 “실제 임상적 추가가치”를 요구받을 가능성이 큽니다.

### Modern Pathology 도전 조건

Modern Pathology는 computational science와 digital pathology를 범위에 포함하지만, 임상·중개 병리학적 의미가 명확해야 합니다. [공식 범위](https://www.sciencedirect.com/journal/modern-pathology)

이 저널에는 다음 스토리가 적합합니다.

* PTEN/ERG/AR의 molecular concordance
* grade 및 동반 변이 통제 후 남는 신호
* PRECISE의 공간적 localization
* 병리학적으로 해석 가능한 failure case
* 분자검사 대체가 아니라 triage/evidence 역할이라는 정직한 범위

다만 독립 PTEN/ERG IHC 코호트가 없다는 점은 큰 약점입니다. 따라서 Modern Pathology는 “도전 가능하지만 결과 의존성이 큰 목표”입니다.

### npj Precision Oncology 도전 조건

논문 주제는 매우 잘 맞지만, 공식 범위에서 biomarker 연구에 **생물학적 검증과 독립 코호트의 외부검증**을 명시적으로 요구하고 있습니다. AI 연구 역시 external validation과 임상적 잠재력을 요구합니다. [공식 범위](https://www.nature.com/npjprecisiononcology/aims)

현재 PTEN/ERG/AR은:

> internally supported but externally untested

이므로 약점이 명확합니다.

따라서 npj Precision Oncology에 투고하려면 molecular marker 자체보다:

> qualification을 통과한 multi-axis image evidence가 독립 LEOPARD 코호트에서 재발 위험과 연관된다

는 임상 결과 중심으로 작성해야 합니다. 그렇지 않으면 “분자마커 외부검증이 없다”는 이유로 desk rejection될 가능성이 있습니다.

### npj Digital Medicine은 현재는 부적합

VLM bridge가 부록급이고 실제 임상 구현이나 reader study가 없기 때문에 현재 본문으로는 맞지 않습니다. 이 저널은 off-the-shelf AI를 사용한 관찰·소규모 예비연구를 일반적으로 고려하지 않는다고 명시합니다. [공식 범위](https://www.nature.com/npjdigitalmed/aims)

VLM 부분은 후속 논문으로 분리하는 것이 맞습니다.

## Scientific Reports 가능성

Scientific Reports는 주로 기술적 타당성과 과학적 유효성을 기준으로 심사합니다. [공식 심사정책](https://www.nature.com/srep/journal-policies/peer-review)

현재 계획이 다음 조건을 충족하면 상당히 안정적입니다.

* protocol freeze
* 환자 단위 분석
* 명확한 primary/secondary endpoint
* 다중비교와 CI
* 결과에 따른 객관적 5단계 분류
* replication과 transport 구분
* null 결과 완전 보고
* calibration
* 재현 가능한 코드와 data manifest
* 과도한 molecular validation 주장 회피

제 주관적인 전망은 다음과 같습니다.

| 완성도                                           | Scientific Reports |                                                 상위 도전 저널 |
| --------------------------------------------- | -----------------: | -------------------------------------------------------: |
| A군만 완성                                        |           약 55–70% |                                                       낮음 |
| A군+B군, LEOPARD association                    |           약 65–80% |                         Modern Pathology/npj PO 약 15–25% |
| LEOPARD incremental value + qualified pool 우위 |           약 75–85% | Communications Medicine/Modern Pathology/npj PO 약 25–40% |
| 독립 molecular validation 추가                    |            충분히 안정적 |                                          상위 저널 가능성 크게 상승 |

이는 공식 통계가 아니라 현재 선행연구와 계획을 기준으로 한 전략적 추정치입니다.

## 제목도 약간 수정하는 것이 좋음

현재 제목:

> Confounder-aware qualification of pathology foundation-model biomarkers in prostate cancer

은 좋지만, `biomarkers`라는 말이 PTEN/ERG/AR의 외부검증을 암시할 수 있습니다.

더 안전한 제목은:

> **Confounder-aware qualification of candidate histomolecular signals from pathology foundation-model embeddings in prostate cancer**

또는 결과가 강할 경우:

> **Distinguishing reproducible histomolecular signals from shortcuts in prostate pathology foundation-model embeddings**

입니다.

## 최종 투고 전략

결과를 보기 전 저널을 하나로 고정하지 말고, 다음 go/no-go 기준으로 결정하는 것이 좋습니다.

1. LEOPARD에 임상 공변량이 있는가?
2. Qualified pool이 recurrence를 유의하게 예측하는가?
3. Clinical baseline 대비 incremental value가 있는가?
4. Qualified pool이 naïve/all-candidate pool보다 좋은가?
5. DiagSet-C와 PRECISE가 동일한 reliability story를 지지하는가?

* 1–5 중 4개 이상 성공: **Communications Medicine 우선 도전**
* 3개 정도 성공하고 병리학적 해석이 강함: **Modern Pathology 또는 npj Precision Oncology**
* LEOPARD가 연관성 수준이고 외부 분자검증이 없음: **Scientific Reports**
* qualification 결과 자체가 주로 기술적 benchmark 성격: **Journal of Pathology Informatics**

따라서 현재 최종안은 “Scientific Reports에 낼 수 있을까?” 수준을 넘어섰습니다. 정확한 표현은:

> **Scientific Reports는 현실적인 안정권이고, LEOPARD에서 qualification의 임상적 결과가 입증되면 Communications Medicine·Modern Pathology·npj Precision Oncology를 먼저 시도할 수 있는 논문 설계다.**

다만 논문의 급을 올리는 결정적 요소는 실험 수가 아니라 **qualification이 실제 marker 선택과 독립 임상 성능을 바꾼다는 한 개의 강한 결과**입니다.
