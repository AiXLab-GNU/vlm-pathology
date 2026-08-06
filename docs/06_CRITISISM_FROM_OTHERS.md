## 총평

연구 가치는 분명히 있습니다. 그러나 현재 적어 놓은 **“6단계 절차 자체가 새로운 방법론”**이나 **“VLM 환각을 우회하는 근거층”**이라는 주장은 그대로는 충분히 입증되지 않습니다.

제 판단은 다음과 같습니다.

* 연구 데이터와 실험 결과: 가치 있음
* Scientific Reports 적합성: 충분히 가능
* 현재 novelty 서술: 과장되거나 기존 연구와 겹치는 부분이 큼
* 가장 강한 방향: VLM 환각보다 **“confounder-aware, cross-cohort marker verification”**을 중심 기여로 재정립
* 현재 상태 그대로 제출: 권하지 않음
* 핵심 보강 후 제출: 경쟁력 있음

Scientific Reports는 Nature급 임팩트를 요구하지 않고 기술적 타당성과 과학적 유효성을 중시합니다. 하지만 “이미 알려진 방법을 여러 번 적용한 연구”로 보이면 novelty와 연구 질문의 명확성에서 공격받을 수 있습니다. [Scientific Reports peer-review policy](https://www.nature.com/srep/journal-policies/peer-review)

---

## 1. 최신 문헌을 고려하면 무엇이 이미 알려져 있는가

현재 6단계 절차의 구성 요소 대부분은 이미 확립돼 있습니다.

### 고정 파운데이션 모델 + 경량 probe

CONCH는 117만 개 이상의 병리 image–caption pair로 학습된 병리 VLM이고, Virchow는 대규모 병리 영상으로 학습된 vision-only foundation model입니다. 두 모델의 frozen embedding 위에 downstream classifier를 학습하는 방식은 이미 표준적인 평가 방법입니다. [CONCH](https://www.nature.com/articles/s41591-024-02856-4), [Virchow](https://www.nature.com/articles/s41591-024-03141-0)

2025년 Nature Biomedical Engineering 연구는 19개 파운데이션 모델, 31개 임상 과제, 19개 바이오마커, 13개 코호트를 사용해 외부검증과 CONCH–Virchow 계열의 ensemble까지 평가했습니다. [Neidlinger et al., 2025](https://www.nature.com/articles/s41551-025-01516-3)

더 중요한 것은 2026년 7월에 발표된 Nature Communications 연구입니다. 이 연구는:

* 32개 foundation model
* 41개 병리 과제
* frozen feature extraction
* standardized linear probing
* patient-level train/test separation
* TCGA, CPTAC 및 외부 데이터
* model fusion
* TCGA-PRAD ERG fusion
* TCGA-PRAD mRNA clustering
* SICAPv2 Gleason grading

까지 포함합니다. 즉, 현재 논문의 “frozen embedding–linear probe–다중 과제–교차 모델–fusion”이라는 넓은 구조와 상당히 겹칩니다. [Bareja et al., 2026](https://www.nature.com/articles/s41467-026-76004-6)

따라서 다음 주장은 novelty로 내세우기 어렵습니다.

> “파운데이션 모델을 고정하고 가벼운 probe를 학습하면 여러 마커를 저렴하게 확장할 수 있다.”

이것은 이제 새로운 발견이라기보다 foundation model의 일반적인 사용 방식에 가깝습니다.

### 전립선암의 PTEN·ERG·분자 subtype 예측

전립선암에 한정해도 선행연구가 강합니다.

* Erak et al.은 H&E에서 ERG와 PTEN을 예측했습니다. ERG는 여러 외부 코호트에서 AUROC 0.78–0.91, PTEN은 약 0.72–0.81이었습니다. [Modern Pathology, 2023](https://pubmed.ncbi.nlm.nih.gov/37307876/)
* Omar et al.은 TCGA-PRAD에서 TMPRSS2:ERG fusion을 예측해 내부 AUROC 0.72, 독립기관 AUROC 0.73을 보고했습니다. [Molecular Cancer Research, 2024](https://pure.johnshopkins.edu/en/publications/semi-supervised-attention-based-deep-learning-for-predicting-tmpr/)
* 2026년에는 prostate PAM50 및 PSC subtype을 UNIv2-MIL로 예측해 AUROC 0.863과 0.81을 보고했습니다. [npj Precision Oncology, 2026](https://www.nature.com/articles/s41698-026-01335-y)
* 연속형 바이오마커를 regression으로 예측하는 접근도 11,671명, 9개 암종에서 이미 제시됐습니다. [El Nahhas et al., 2024](https://www.nature.com/articles/s41467-024-45589-1)

따라서 “전립선암의 여러 임상·분자 마커를 영상에서 예측한다”만으로는 강한 novelty가 되기 어렵습니다.

---

## 2. VLM 환각 motivation에 중요한 인용 오류가 있습니다

현재 문서의 다음 내용은 반드시 고쳐야 합니다.

> “GPT-4V의 병리 영역 환각률 46.8%, Royer et al., arXiv 2406.10185”

이 연결은 정확하지 않습니다.

46.8%는 Brin et al.이 CT·X-ray·초음파 같은 **방사선 영상에서 병변(pathology)을 식별하게 한 실험**에서 보고한 hallucination rate입니다. 여기서 pathology는 조직병리학이 아니라 “영상에 나타난 병적 소견”이라는 뜻입니다. [Brin et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11914349/)

arXiv 2406.10185는 Royer et al.이 아니라 Chen et al.의 Med-HallMark 연구입니다. 이 논문은 일반적인 medical LVLM hallucination benchmark이지, 전립선 조직병리에서 46.8%를 보고한 연구가 아닙니다. [Chen et al., Med-HallMark](https://arxiv.org/abs/2406.10185)

따라서 원고에서 다음과 같이 처리해야 합니다.

* 46.8%를 histopathology 근거로 사용하지 않음
* Brin et al.은 “의료영상에서 generative VLM이 unsupported finding을 생성할 수 있다는 일반적 근거”로만 인용
* 병리-specific motivation은 자체 정식 벤치마크로 확보
* zero-shot이 낮고 ICL로 크게 개선되는 반례를 반드시 함께 제시

GPT-4V는 조직병리 zero-shot에서 거의 무작위 수준이었지만 10-shot ICL로 일부 과제에서 83–90%까지 개선됐습니다. [Ferber et al., 2024](https://www.nature.com/articles/s41467-024-51465-9) 또한 PathChat처럼 병리에 맞춰 대규모 instruction tuning을 한 생성형 모델도 존재합니다. [PathChat](https://www.nature.com/articles/s41586-024-07618-3)

그러므로 논문의 메시지는 다음이어야 합니다.

> Generative VLM이 본질적으로 병리 진단을 수행할 수 없는 것이 아니라, 단순 zero-shot prompting의 출력은 과제·프롬프트·예시·출력 위치에 민감하며 검증되지 않은 임상 근거로 사용할 수 없다.

---

## 3. 현재 가장 큰 논리적 문제: motivation과 실제 기여가 연결되지 않음

현재 프레이밍은 다음 구조입니다.

```text
VLM이 환각한다
→ 검증된 마커가 필요하다
→ frozen embedding으로 마커를 만든다
→ 미래에 LLM이 사용할 수 있다
```

문제는 마지막 연결을 실험하지 않았다는 것입니다. 현재 연구는 다음을 보여주지 않았습니다.

* 마커를 VLM에 주었을 때 진단 정확도가 올라가는지
* unsupported finding이 감소하는지
* confidence calibration이 좋아지는지
* 이미지 단독 판단보다 안전한지
* VLM이 실제로 마커를 올바르게 이용하는지

따라서 “VLM hallucination을 해결하는 방법”을 논문의 중심 주장으로 삼으면 심사자는 쉽게 이렇게 반박할 수 있습니다.

> “The proposed marker pool has not been integrated into or evaluated with any generative model; therefore, its relevance to hallucination mitigation remains speculative.”

이 문제를 해결하는 방법은 두 가지입니다.

### 빠르고 안전한 전략

VLM 환각은 Introduction의 보조 motivation과 Discussion의 미래 적용으로만 둡니다. 논문의 중심은 병리 marker verification으로 바꿉니다.

### 더 야심찬 전략

작은 bridge experiment를 추가합니다.

* image-only VLM
* image + validated marker values
* image + shuffled/incorrect marker values
* marker-only
* zero-shot와 ICL

을 비교하고 다음을 측정합니다.

* 진단 정확도
* unsupported finding rate
* abstention 적절성
* calibration
* marker 충돌 시 반응

이 실험이 있어야 VLM-grounding을 제목과 Abstract 전면에 세울 수 있습니다.

---

## 4. 제가 권하는 더 강한 핵심 프레이밍

현재 최신 문헌을 고려하면 다음 프레이밍이 가장 강합니다.

> **A confounder-aware, cross-cohort and cross-encoder verification framework for identifying portable prostate histomolecular signals from frozen pathology foundation-model embeddings**

한국어로는:

> **고정된 병리 파운데이션 모델 임베딩에서 발견된 신호가 기관·스캐너·등급·타일 스케일 또는 공변 바이오마커에 의한 shortcut이 아닌지 검증하고, 실제로 재현 가능한 전립선암 영상 기반 임상·분자 proxy만 선별하는 절차**

이것이 중요한 이유는 2026년 최신 연구가 병리 바이오마커 모델이 종종 biomarker 자체가 아니라 등급, 기관 또는 공변 분자 특성을 학습한다고 경고했기 때문입니다. [Dawood et al., 2026](https://www.nature.com/articles/s41551-026-01616-8) PathoROB 연구도 20개 병리 FM 모두에서 기관·염색·스캐너 정보가 embedding에 들어가 downstream 오류를 일으킬 수 있음을 보였습니다. [Kömen et al., 2026](https://www.nature.com/articles/s41467-026-73923-2)

이 방향에서는 null 결과와 실패가 오히려 기여가 됩니다.

* `dab_ring` null: 사람이 설계한 단순 proxy는 실패
* SPOP null: 기존 보고가 모든 파이프라인에서 재현되지는 않음
* ERG fusion null: IHC signal과 fusion status를 구분해야 함
* AR_SCORE의 site sensitivity: 통계적 유의성만으로 portable marker라 할 수 없음
* tile scale mismatch: 재현성을 무너뜨리는 실제 구현 함정

이 결과들은 “모든 마커를 잘 예측한다”보다 “어떤 신호를 믿어서는 안 되는지 판별한다”는 논문에 훨씬 잘 맞습니다.

---

## 5. 기여문은 다음처럼 수정하는 것이 좋습니다

현재의 “검증된 6개 마커”는 수정이 필요합니다. ⑤ SPOP이 null이면 6개 모두를 validated marker라고 부를 수 없습니다.

권장 표현은 다음과 같습니다.

1. 여러 임상·분자 endpoint에 동일하게 적용되는 **pre-specified verification gate**를 제안했다.
2. 후보 신호를 positive, cohort-sensitive, model-sensitive, null로 구분하는 **prostate marker reliability map**을 구축했다.
3. patient-disjoint validation, cross-site analysis, frozen cross-cohort transport, cross-encoder replication을 통해 portability를 평가했다.
4. 마커 간 결합 효과가 단순히 마커 수가 아니라 target alignment와 complementary information에 의존한다는 제한적 실증을 제시했다.
5. 향후 생성형 AI가 사용할 수 있는 정량적 근거를 만들기 위한 기반을 제공하지만, 생성형 AI의 실제 성능 향상은 본 연구의 범위 밖임을 명시했다.

“validated marker”보다는 다음 용어가 안전합니다.

* reproducible image-derived proxy
* externally replicated histomolecular signal
* candidate quantitative evidence variable
* site-sensitive exploratory marker
* negative/null candidate

---

## 6. 제출 전에 반드시 추가해야 할 분석

### A. Confounder audit — 가장 중요

각 분자 마커에 대해 최소한 다음을 비교해야 합니다.

1. clinicopathologic baseline
   Grade Group, tumor purity, specimen type, age, site

2. image probe only

3. baseline + image probe

핵심은 image probe가 기존 임상 정보에 비해 얼마나 추가 정보를 제공하는지입니다.

보고할 지표는:

* ΔAUROC 또는 ΔR²
* likelihood-ratio test 또는 nested-model comparison
* Grade Group 내 stratified performance
* site별 effect direction
* 공변 마커를 조정한 partial association
* label을 site 내에서 permutation한 null distribution

특히 PTEN, AR, ERG는 grade 및 서로 연관된 분자 축을 조정한 뒤에도 신호가 남는지 확인해야 합니다. 그렇지 않으면 “PTEN 형태를 학습한 것”이 아니라 “고등급 형태를 통해 PTEN을 간접 추측한 것”일 수 있습니다.

### B. 외부검증의 정의 명확화

다른 코호트에서 probe를 다시 학습했다면 이것은 independent replication입니다.

진정한 transport validation은 다음입니다.

```text
Cohort A에서 encoder preprocessing + probe coefficient 확정
→ 모든 파라미터 고정
→ Cohort B에 그대로 적용
```

이 둘을 원고에서 구분해야 합니다.

### C. Marker acceptance criteria 사전 정의

예를 들어 다음 조건을 모두 통과해야 verified pool에 포함한다고 정할 수 있습니다.

* BH-FDR q<0.05
* 95% CI가 null을 제외
* 최소 임상적으로 의미 있는 effect threshold 통과
* site별 방향 일관성
* 독립 코호트 또는 frozen transport 재현
* 두 번째 encoder에서 방향 재현
* grade/site baseline을 넘는 incremental value

단순히 표본이 커서 p<0.05인 약한 AUROC는 validated marker로 인정해서는 안 됩니다.

### D. Calibration

미래의 evidence layer를 주장하려면 AUROC나 상관계수만으로 부족합니다.

* Brier score
* calibration slope/intercept
* reliability curve
* ECE
* uncertainty 또는 prediction interval

을 추가하는 것이 좋습니다. “정량적 근거”는 순위뿐 아니라 값의 신뢰도도 필요하기 때문입니다.

---

## 7. QWK와 SOTA 비교에 대한 수정

QWK 재계산은 필요하지만 DeepGleason F1=0.806과 단순히 나란히 두어서는 안 됩니다.

* DeepGleason F1은 tile-level 분류에 가까움
* 현재 연구의 Spearman ρ는 patient-level ordinal association
* PANDA는 biopsy-level Grade Group QWK

로 분석 단위와 과제가 다릅니다.

가장 적절한 비교는 동일한 Grade Group 정의와 동일한 분석 단위에서 계산한 QWK입니다. PANDA의 외부검증 QWK는 미국·유럽 코호트에서 각각 약 0.862와 0.868이었습니다. [PANDA challenge](https://www.nature.com/articles/s41591-021-01620-2)

비교표에는 반드시 다음 열이 있어야 합니다.

| 연구          | 입력 단위      | 평가 단위   | 데이터셋       | 외부검증  | 지표     | 직접 비교 가능성 |
| ----------- | ---------- | ------- | ---------- | ----- | ------ | --------- |
| PANDA       | WSI/biopsy | biopsy  | 다기관        | 있음    | QWK    | 부분 가능     |
| DeepGleason | tile/WSI   | 주로 tile | 자체 코호트     | 제한적   | F1     | 직접 비교 불가  |
| 본 연구        | tile/환자    | 환자      | NADT/PANDA | 명시 필요 | ρ, QWK | 조건부 가능    |

목적은 SOTA를 이겼다는 것이 아니라 동일 과제에서 어느 정도의 정보가 보존되는지 보여주는 것입니다.

---

## 8. VLM 벤치마크를 실행할 때의 주의점

현재 계획한 4개 모델 × 4개 과제 × zero-shot/ICL은 좋습니다. 다만 endpoint를 구분해야 합니다.

* 잘못된 closed-set label: classification error
* 이미지에 없는 소견을 생성: unsupported-finding hallucination
* 좌우를 반복 선택: positional bias
* prompt에 따라 결과가 변함: prompt sensitivity
* 같은 입력을 반복했을 때 변화: instability

모든 오류를 “hallucination”이라고 묶으면 심사자가 정의 문제를 제기할 수 있습니다.

필수 설계는 다음과 같습니다.

* API 모델의 정확한 version/date 기록
* temperature와 decoding 조건 고정
* 동일 조건 반복 실행
* 이미지 순서와 좌우 위치 무작위화
* 환자 단위 bootstrap CI
* zero-shot, random ICL, similarity-selected ICL 분리
* 모델별 refusal/abstention 기록
* 병리 전문가가 unsupported finding을 판정
* 가능하면 두 명 이상 평가하고 inter-rater agreement 보고

이 실험은 논문의 motivation을 정식화할 수 있지만, marker 연구와 직접 연결하지 않는다면 Supplementary 또는 짧은 첫 Results subsection이 적절합니다.

---

## 9. Scientific Reports 제출 가능성

정성적 평가를 표로 정리하면 다음과 같습니다.

| 항목          | 현재 평가    | 필요한 조치                                 |
| ----------- | -------- | -------------------------------------- |
| 임상적 중요성     | 강함       | 유지                                     |
| 데이터·실험량     | 충분한 편    | cohort별 N 명확화                          |
| 환자 단위 분리    | 강점       | 모든 분석에서 일관성 확인                         |
| 다중비교·CI     | 양호       | 완료 내용 유지                               |
| 외부 일반화      | 중간       | frozen transport와 refit replication 구분 |
| 방법론 novelty | 현재 약함    | confounder-aware verification으로 전환     |
| VLM 연결      | 현재 추론적   | 보조 동기로 낮추거나 bridge experiment 추가       |
| 임상적 성능      | 일부 약함    | “진단 대체”가 아닌 proxy/triage로 제한           |
| 재현성         | 미완성      | 코드·환경·manifest 공개                      |
| 원고 완성도      | 연구 노트 수준 | 전면 재구성 필요                              |

주관적인 편집 판단치로는:

* 현재 `report.tex` 그대로: 약 30–40%
* 기존 액션만 완료하고 VLM 프레이밍 유지: 약 45–55%
* confounder-aware 프레이밍 + 실제 외부 transport + 코드 공개: 약 60–70%
* 여기에 marker-conditioned VLM bridge까지 성공: 그보다 다소 높아질 수 있음

이 수치는 통계적 확률이 아니라 유사 논문과 심사 리스크를 바탕으로 한 전략적 추정입니다. 2026년 Bareja et al. 논문이 매우 직접적으로 겹치기 때문에, 이전에 예상했던 “기존 보강만으로 60–70%”는 다소 낙관적입니다.

---

## 최종 권고

Scientific Reports를 목표로 한다면 저는 다음 순서를 권합니다.

1. 잘못된 46.8% 조직병리 인용 즉시 수정
2. 핵심 프레이밍을 **VLM 우회법**에서 **confounder-aware marker verification**으로 변경
3. “6 validated markers”를 “평가된 후보 중 재현된 신호·민감한 신호·null 결과”로 재분류
4. grade/site/tumor purity/co-biomarker confounder 분석 추가
5. frozen cross-cohort transport를 명확히 수행
6. QWK는 같은 분석 단위에서만 비교
7. calibration과 marker acceptance rule 추가
8. VLM 벤치마크는 정식 motivation으로 수행하되 오류 유형을 분리
9. 코드·환경·분할표·환자별 out-of-fold prediction을 공개
10. CLAIM 2024와 TRIPOD+AI 체크리스트로 최종 점검
    [CLAIM 2024](https://pubs.rsna.org/doi/10.1148/ryai.240300), [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378)

핵심적으로 이 논문의 가장 가치 있는 메시지는 “가벼운 probe로 무엇이든 예측할 수 있다”가 아닙니다. 오히려 다음이 더 강합니다.

> **병리 파운데이션 모델의 통계적으로 유의한 출력이 곧 신뢰할 수 있는 생물학적 근거는 아니다. 우리는 기관, 스케일, 모델, 임상 공변량 및 외부 코호트를 통과한 신호와 실패한 신호를 구분하는 재현 가능한 검증 절차를 제시한다.**

이 주장은 현재 결과의 성공과 실패를 모두 활용하면서 최신 문헌과도 정확히 맞물리고, Scientific Reports에 제출할 만한 분명한 과학적 기여가 될 수 있습니다.
