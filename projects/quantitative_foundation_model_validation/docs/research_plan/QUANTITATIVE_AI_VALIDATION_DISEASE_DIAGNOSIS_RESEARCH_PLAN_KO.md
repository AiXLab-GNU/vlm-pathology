# 정량화 기반 AI 검증 및 질병 진단 기술 연구계획서

- 문서 버전: 0.1
- 기준일: 2026-08-11
- 문서 성격: 연구 프로그램 개념계획서 및 단계별 사전 연구 로드맵
- 우선 적용 분야: 전립선암 병리, Gleason/ISUP, 분자표현형, 신경주위침윤(PNI)
- 확장 분야: 다암종 디지털 병리 진단 보조, 예후·치료반응 예측, 외부 코호트 AI 감시
- 현재 PRECISE AI의 검증된 역할: whole-slide 진단이 아니라 공간적으로 구별된 병리 검토 후보의 우선순위 제시

## 1. 연구 제목

### 국문

**정량화 기반 AI 검증 및 질병 진단 기술: 기존 병리 지표와 인공지능 표현의 일치성·상보성·외부 이식성 검증 및 신규 디지털 바이오마커 발굴**

### 영문

**Quantification-Based Validation of Artificial Intelligence for Disease Assessment: Concordance, Complementarity, Transportability, and Discovery of Digital Pathology Biomarkers**

## 2. 연구 요약

병리 진단은 핵 크기와 다형성, 유사분열, 선 구조, 침윤 깊이, 종양–기질 비율,
면역세포 밀도, 신경·혈관 침윤, IHC 발현 및 Gleason과 같은 정량·반정량 지표의
조합에 기반한다. 최근의 기반 모델과 VLM은 이러한 사람이 정의한 특징을 명시적으로
입력하지 않고도 질병, 등급, 분자 상태와 예후를 예측한다. 그러나 AI가 기존 병리
개념을 더 정밀하게 측정하는 것인지, 기존 지표와 상보적인 생물학적 정보를 발견한
것인지, 아니면 기관·염색·스캐너 등의 비생물학적 shortcut을 이용한 것인지는 충분히
구분되지 않았다.

본 연구는 독립적으로 측정 가능한 병리 정량지표를 생물학적 기준축으로 사용해
동결된 AI 모델의 판단을 검증한다. 개발 코호트에서 AI–정량지표 관계를 확립하고,
외부 코호트에서 그 관계의 보존성과 실제 성능 변화를 함께 측정한다. 기존 지표로
설명되지 않는 AI 잔차는 blinded 병리 재검토, 명시적 형태계측, IHC·유전체·공간
오믹스 및 독립 임상 endpoint를 통해 신규 바이오마커 후보와 shortcut으로 분리한다.

핵심 원칙은 다음과 같다.

> AI–정량지표 일치도는 정확도 자체가 아니다. 일치도는 의미적 안정성과 외부
> 이식가능성의 경보 지표이며, 실제 정확성은 독립 ground truth로 별도 검증한다.

## 3. 연구 배경 및 필요성

### 3.1 기존 병리 정량화의 역할

암 병리에서 다음 특징은 질병 유무, grade, 진행, 재발 및 생존과 연결되어 왔다.

- 핵 크기·형태·다형성, 핵/세포질 비율 및 유사분열 수
- gland/lumen의 크기, 원형도, 융합, cribriform 구조
- 종양 면적, 침윤 깊이, tumor budding 및 괴사
- 신경·혈관·림프관 침윤과 암–신경 접촉 구조
- 종양–기질 비율과 면역세포 밀도·공간분포
- IHC 양성 비율과 염색 강도
- Gleason, Nottingham grade 같은 형태 조합 점수

C-Path는 유방암 영상에서 6,642개 형태 특징을 추출하고 기존 grading에 충분히
포함되지 않았던 stromal 특징과 생존의 관계를 두 코호트에서 보였다. 이는 AI 이전의
정량영상 분석도 새로운 형태 지표를 발견할 수 있음을 보여준다.
[C-Path](https://pubmed.ncbi.nlm.nih.gov/22072638/)

### 3.2 기반 모델의 기회와 검증 공백

기반 모델은 대규모 병리 영상에서 범용 표현을 학습하여 적은 라벨로 다양한
downstream task를 수행할 수 있다. 그러나 높은 내부 성능만으로는 다음을 알 수 없다.

1. 모델이 어떤 병리 개념을 사용했는가?
2. 두 기반 모델이 같은 생물학적 feature를 보는가?
3. 모델의 신호가 기존 지표보다 증분 가치가 있는가?
4. 외부 기관에서 stain·scanner·specimen type이 변해도 관계가 유지되는가?
5. 기존 지표로 설명되지 않는 신호가 새 생물학인가, shortcut인가?

이 공백은 해석 가능성의 문제를 넘어 외부검증, 배포 후 감시, 실패 원인 분석 및
신규 바이오마커 발굴을 하나의 연구 체계로 연결해야 한다는 필요성을 만든다.

### 3.3 외부 코호트 성능 저하의 원인

본 연구는 외부 코호트 차이를 다음 네 층으로 분리한다.

| 변화 층 | 예 | 필요한 검증 |
|---|---|---|
| 기술적 품질 | 염색, 초점, fold, 절편 두께, 압축, 스캐너, 해상도 | slide QC, metadata, 물리 스케일 |
| 환자·검체 구성 | 유병률, grade, 병기, 인종, 치료, biopsy/resection | case-mix 층화와 임상 공변량 |
| 질병 표현형 | 희귀 형태, subtype, PNI 형태, 염증성 mimic | 전문의 재판독과 open-set/OOD 분석 |
| 참조표준 | 기관별 판독 기준, uncertain 처리, sampling | blinded adjudication과 label provenance |

전립선암 다기관 연구에서는 절편 두께와 염색 시간 변화가 AI grading 성능을 최대
8.6 percentage points 감소시켰다. 반면 biopsy로 학습한 AI가 독립 기관의
prostatectomy 표본에서 grade-group weighted kappa 0.89를 보인 연구도 있다. 따라서
domain 차이는 위험 신호이지만 성능 저하 그 자체는 아니다.
[전립선 데이터 변이 연구](https://pubmed.ncbi.nlm.nih.gov/41308537/),
[전립선 외부검증](https://pubmed.ncbi.nlm.nih.gov/38989669/)

## 4. 관련 연구 현황

### 4.1 연구 성숙도

| 연구축 | 성숙도 | 현재 한계 |
|---|---:|---|
| 기존 지표의 자동 검출·정량 | 높음 | 표준화·scanner/stain 재현성은 과제별 차이 |
| AI와 병리의 판정 비교 | 높음 | 사람–AI 협업 향상이 feature 일치의 직접 증거는 아님 |
| handcrafted와 deep feature 비교 | 중상 | 과제별 우열이 다르고 외부검증이 불균일 |
| 기존 지표와 AI 내부 표현의 대응 | 중간 | probe 과적합과 attention 해석 한계 |
| 기존 지표와 AI의 결합 | 중간 | 작은 후향 연구가 많고 calibration 검증 부족 |
| AI 기반 신규 형태·공간 지표 발견 | 중간·급성장 | 후보가 많고 임상 유효성 검증은 제한적 |
| 일치도를 외부 cohort acceptance gate로 사용 | 초기 | 실제 성능 저하에 대한 다기관 직접 검증 부족 |

### 4.2 해석 가능한 AI와 concept 연구

Diao 등은 5개 암종, 5,700개 이상 표본에서 세포·조직·공간 구조를 표현하는 607개
human-interpretable feature를 구성하고 여러 분자 phenotype에서 black-box에
근접한 성능을 보였다. 이는 AI 표현의 상당 부분을 사람이 이해할 수 있는 병리
개념으로 설명할 수 있다는 근거다.
[Diao 연구](https://pubmed.ncbi.nlm.nih.gov/33712588/)

전립선 Gleason 연구에서는 54명의 국제 병리의사가 정의한 형태 개념을 중간 출력으로
사용해 grade와 판단 근거를 함께 제시했다. MuTILs/PanopTILs는 종양·기질·림프구를
명시적 concept로 구성하고 계산 TIL 점수의 예후 정보를 평가했다.
[해석 가능한 Gleason AI](https://pubmed.ncbi.nlm.nih.gov/41062516/),
[MuTILs/PanopTILs](https://pubmed.ncbi.nlm.nih.gov/38942745/)

### 4.3 기존 특징과 deep feature의 중복·상보성

전립선암 소규모 연구에서는 암/비암 구분에서 pathomic feature와 ResNet 성능이
비슷했지만 세부 Gleason pattern에서는 deep feature가 더 우수했다. 간 전이암에서는
암종에 따라 handcrafted 또는 deep feature의 우위가 달랐고, 결합이 소폭 향상되는
경우가 있었다. 따라서 단순 일치성뿐 아니라 외부 코호트에서의 증분 성능을 평가해야
한다.
[전립선 비교 연구](https://pubmed.ncbi.nlm.nih.gov/36928230/),
[feature 결합 연구](https://pubmed.ncbi.nlm.nih.gov/37822044/)

### 4.4 H&E 기반 분자표현형과 신규 지표

H&E 영상에서 MSI, EGFR/KRAS/TP53, PTEN/ERG 등 분자 상태를 예측할 수 있다는
다기관 근거가 축적됐다. 그러나 grade, 종양 순도, 조직 subtype과 기관 signature가
실제 표적 대신 예측을 설명할 수 있다.
[국제 MSI 검증](https://pubmed.ncbi.nlm.nih.gov/32562722/),
[폐암 변이 예측](https://pubmed.ncbi.nlm.nih.gov/30224757/),
[전립선 PTEN/ERG](https://pubmed.ncbi.nlm.nih.gov/37307876/),
[분자 예측 confounding](https://pubmed.ncbi.nlm.nih.gov/41772176/)

TIL 공간구조, 전립선의 dense immune cluster, PathPrism의 대장암 공간특징 및 HEX의
virtual spatial proteomics는 AI feature를 명시적이고 측정 가능한 새 축으로 바꾸는
최근 사례다.
[TIL 공간구조](https://pubmed.ncbi.nlm.nih.gov/29617659/),
[전립선 면역 공간 바이오마커](https://pubmed.ncbi.nlm.nih.gov/42113020/),
[PathPrism](https://pubmed.ncbi.nlm.nih.gov/42276049/),
[HEX](https://pubmed.ncbi.nlm.nih.gov/41491099/)

### 4.5 품질·domain shift·배포 후 감시

HistoQC는 stain, blur, fold와 contrast를 자동 정량화한다. representation shift와
OOD uncertainty는 라벨이 없는 target cohort에서 위험 신호를 제공하지만 실제 성능
저하와 항상 일치하지 않는다. CheXstray와 ACR Assess-AI는 metadata, 영상 표현,
AI 출력 또는 surrogate label의 concordance를 결합한 감시 체계를 제시한다.
[HistoQC](https://pubmed.ncbi.nlm.nih.gov/30990737/),
[representation shift](https://pubmed.ncbi.nlm.nih.gov/33085623/),
[병리 OOD uncertainty](https://pubmed.ncbi.nlm.nih.gov/36306568/),
[CheXstray](https://doi.org/10.1007/978-3-031-43898-1_32),
[ACR Assess-AI](https://pubmed.ncbi.nlm.nih.gov/42066927/)

### 4.6 연구 공백

문헌의 구성요소는 충분하지만 다음을 한 체계에서 수행한 연구는 드물다.

- 독립 정량지표가 AI score를 설명하는 정도를 환자분리 방식으로 측정
- 두 개 이상의 독립 기반 모델에서 같은 concept를 비교
- 정량지표 일치도가 외부 실제 성능 저하를 추가로 예측하는지 검증
- 잔차를 신규 바이오마커와 shortcut으로 분해
- 병리전문의, IHC/omics 및 독립 임상 outcome으로 후보를 검증

## 5. 사전 연구 및 보유 기반

### 5.1 정량지표 패키지

본 저장소에는 기존 113개 안정 measure ID, 질병별 적용 맵, 20개 조합 및 문헌
카탈로그를 포함한 `vlm-pathology-metrics` 패키지가 있다. 이 113개에는 biological
feature뿐 아니라 AI output, 평가·통계·QC 값이 포함되어 있으므로 의료 정량지표
Tier 1–4와 별도 analysis registry로 분리한다.

| 제안 역할 | 예 | 본 연구에서의 사용 |
|---|---|---|
| `biological_feature` | gland, nuclear, texture, IHC, nerve geometry | AI 검증의 독립 기준축 |
| `ai_output` | probability, prototype/text score, attention, rank | 검증 대상 |
| `clinical_outcome` | 진단, grade, 분자 assay, 재발·생존 | criterion truth |
| `performance_metric` | AUROC, AP, QWK, C-index, calibration | 평가 결과 |
| `quality_control` | stain, focus, tissue fraction, registration | 원인·품질 층 |
| `derived_comparison` | paired delta, residual, stability index | 모델·코호트 비교 |

### 5.2 두 동결 기반 모델

현재 CONCH와 Virchow가 서로 다른 조직, 구조, 학습자료에서 만들어진 동결 인코더로
사용되고 있다. 모델 가중치는 연구 중 fine-tuning하지 않았다. 기존 분석은 동일
marker pool을 두 encoder로 평가하고 scale, tile budget과 sampling seed 민감도를
조사했다.

### 5.3 현재 확보된 정량 endpoint와 코호트

| 코호트 | 보유 endpoint | 현재 역할 |
|---|---|---|
| NADT-Prostate | Gleason, benign/tumor, ERG serial stain | source concept/probe 연구 |
| PANDA | ISUP grade, 두 기관 | grade/phenotype 외부검증 |
| TCGA-PRAD | Gleason, PTEN, SPOP, AR, ERG, outcome | 분자·예후 및 site audit |
| SICAPv2 | 전립선 조직·grade | 진단 sanity check |
| LEOPARD | BCR event/follow-up | recurrence source/transfer 연구 |
| PRECISE | Gleason, pixel annotation, paired H&E/IHC, PNI review | 공간 face-validity와 PNI 방법론 pilot |

### 5.4 사전 결과

- Grade와 phenotype은 NADT에서 학습한 probe가 PANDA에서 방향과 성능을 재현했다.
- PRECISE의 실제 Gleason 비교에서 기존 marker 1은 제한된 17개 session에서 높은
  순위상관을 보였으나, 작은 표본이므로 임상 grading 성능으로 일반화하지 않는다.
- Gleason, phenotype, PTEN은 CONCH와 Virchow가 비교적 유사했다.
- ERG 관련 연관은 Virchow에서 더 강했다.
- SPOP은 설정 민감성이 커 robust positive 또는 robust null로 확정되지 않았다.
- recurrence는 endpoint, encoder와 scale 의존성이 컸다.
- PRECISE frozen PNI ranker는 층화·블라인드 120후보 표본에서 관찰된 PNI focus를
  높은 순위에 집중시켰지만 whole-slide sensitivity나 진단 threshold를 검증하지 않았다.
- 14개 선택 nerve-positive focus의 morphology pilot은 contour 대상 선정을 위한
  방법론 단계이며 PNI 형태의 모집단 분포를 추정하지 않는다.

이 사전 결과는 “최고의 encoder”를 정하는 결과가 아니라 marker별로 두 모델의
공통성과 차이가 존재하며, 이를 독립 정량지표 수준에서 체계적으로 검증할 필요가
있다는 근거다.

## 6. 연구 질문과 가설

### 6.1 핵심 연구 질문

> AI 판단 중 기존 병리 정량지표로 재현되는 부분, 상보적인 생물학적 부분, 비생물학적
> shortcut 부분을 각각 얼마나 분리할 수 있으며, 이 분리가 외부 코호트에서의 실제
> 성능 저하를 예측하고 새로운 질병 지표를 발견하는 데 기여하는가?

### 6.2 세부 연구 질문

1. AI가 기존 정량지표를 사람 또는 기존 알고리즘보다 재현성 있게 측정하는가?
2. CONCH와 Virchow는 동일 정량지표와 동일한 방향으로 연관되는가?
3. 기존 지표 조합은 각 AI score를 외부 표본에서 어느 정도 재구성할 수 있는가?
4. 기존 지표와 AI를 결합하면 각각을 단독 사용했을 때보다 외부 성능과 calibration이
   개선되는가?
5. 정량지표 관계의 source–target 보존성이 QC, embedding shift와 uncertainty보다
   실제 성능 저하를 더 잘 예측하는가?
6. 기존 지표로 설명되지 않는 공통 또는 모델별 잔차에 재현 가능한 병리 형태가 있는가?

### 6.3 가설

- H1: AI score의 유의한 부분은 gland, nuclear, spatial, immune 및 nerve-interface
  지표로 out-of-sample 설명 가능하다.
- H2: 두 기반 모델에서 방향이 재현되는 concept는 한 모델에만 존재하는 concept보다
  외부 코호트에서 안정적이다.
- H3: semantic concordance는 기술 QC와 embedding shift를 넘어 외부 성능 저하에
  증분 설명력을 제공한다.
- H4: 기존 지표와 AI의 결합은 일부 endpoint에서만 증분 가치가 있으며, 높은 내부
  성능만 보이는 결합은 외부검증에서 감소한다.
- H5: 기존 지표로 설명되지 않는 AI 잔차는 생물학적 후보와 site/stain/scanner
  shortcut의 혼합이며, 독립 assay와 다기관 설계로 분리할 수 있다.

## 7. 연구 목적과 세부목표

### 7.1 최종 목적

독립 정량 병리개념, AI 표현, 기술 품질, 임상·분자 ground truth를 연결하여 기반
모델의 정확성·해석성·외부 이식성을 감사하고, 검증 가능한 신규 디지털 병리
바이오마커를 발굴하는 재현 가능한 질병 진단 보조 기술을 구축한다.

### 7.2 세부목표

1. **정량지표 거버넌스 구축**
   기존 113개 혼합 계산량을 clinician-native T1부터 model-derived T4까지의 의료·파생
   데이터와 별도 모델평가·통계·QC registry로 분리하고, 역할·독립성·측정성과 준비도를 관리한다.
2. **두 기반 모델의 정량개념 복원력 비교**
   동일 환자·좌표·물리 시야에서 CONCH와 Virchow가 정량지표를 얼마나 복원하는지
   paired benchmark한다.
3. **중복성과 상보성 규명**
   임상변수, 기존 지표, AI score 및 결합모델을 동일 split에서 비교한다.
4. **외부 이식성 감시체계 개발**
   technical QC, distribution shift, semantic concordance, sentinel ground truth의
   네 단계 gate를 구축한다.
5. **신규 지표 발굴과 생물학적 검증**
   AI residual에서 재현 가능한 형태·공간 concept를 정의하고 IHC/omics/outcome으로
   검증한다.
6. **질병별 확장과 임상 유용성 검증**
   전립선암에서 방법을 확립한 뒤 충분한 다기관 코호트에서 다른 암종과 임상 endpoint로
   확장한다.

## 8. 연구 개념모형

다음 기호를 사용한다.

- \(S\): 동결 AI의 연속 disease/candidate score
- \(E\): AI embedding 또는 공간 feature map
- \(M\): 독립 정량 병리 지표 벡터
- \(Q\): stain, focus, tissue area, scanner 등 기술 QC
- \(C\): grade, specimen type, site, 환자 구성과 임상 공변량
- \(Y\): 병리의, 분자 assay 또는 임상 outcome ground truth

개발 코호트에서 다음 관계를 환자분리 교차검증으로 확립한 뒤 고정한다.

\[
S = g(M,C,Q) + R
\]

- \(g(M,C,Q)\): 알려진 지표와 confounder로 설명되는 AI 판단
- \(R\): 설명되지 않는 AI 잔차

외부 코호트에서는 \(g\)를 재학습하지 않고 relation preservation, residual shift와
실제 성능 변화를 측정한다. \(R\)은 즉시 신규 바이오마커로 해석하지 않고 생물학적
후보와 shortcut 후보로 분리한다.

## 9. 연구 내용과 Work Package

### WP0. 지표 및 연구단위 거버넌스

- 지표별 `metric_role`, `analysis_unit`, `independence_source`, `measurement_status`,
  `allowed_claim`, `required_ground_truth`를 정의한다.
- candidate, focus, slide, subject, site와 cohort를 구분한다.
- AI에서 파생된 지표로 같은 AI를 검증하는 순환성을 차단한다.
- 결측, uncertain, not-evaluable을 음성으로 변환하지 않는다.

### WP1. 정량지표 측정 신뢰성

- 병리전문의 annotation과 contour의 intra/interobserver 재현성을 평가한다.
- 자동계측의 scanner, stain, magnification, segmentation 민감도를 측정한다.
- 물리 단위, MPP, 좌표계, registration 오차와 assay provenance를 기록한다.
- 승인 contour 전에는 nerve diameter, encasement, contact와 distance를 계산하지 않는다.

### WP2. AI–정량지표 일치성 및 concept 복원

- 개별 관계: partial Spearman 또는 적절한 generalized model
- 전체 설명력: patient-grouped nested-CV \(R^2\), MAE와 calibration
- 지표군 증분 설명력: gland, nuclear, texture, immune, nerve-interface별 평가
- 공간 일치: Dice/IoU, point–contour distance, spatial correlation
- 표현 일치: CKA, regularized CCA, representational similarity
- 인과 점검: semantic perturbation, ablation, 병리적으로 타당한 counterfactual

### WP3. 질병 판단의 중복성과 상보성

동일 환자 split에서 다음 네 모델을 비교한다.

1. 임상변수 \(C\)
2. \(C+M\)
3. \(C+S\) 또는 \(C+E\)
4. \(C+M+S\) 또는 \(C+M+E\)

결합모델은 외부 코호트에서 discrimination뿐 아니라 calibration, decision utility와
subgroup 성능이 개선돼야 상보성이 있다고 판정한다.

### WP4. 외부 코호트 이식성 및 성능 저하 감시

| Gate | 측정 내용 | 기능 |
|---|---|---|
| G1 Technical QC | blur, fold, stain, tissue area, resolution, scanner | 입력 적격성과 원인 파악 |
| G2 Distribution shift | MMD, Wasserstein, C2ST, embedding/output drift | 변화 발생 경보 |
| G3 Semantic concordance | source–target AI–지표 관계 보존과 residual shift | 의미적 안정성 경보 |
| G4 Sentinel truth | 병리의/assay 일부 재판독과 실제 성능·calibration | 정확성 확인 |

G1–G3은 audit trigger이며 진단 정확도의 대체물이 아니다. G4가 실제 성능을 확인한다.
여러 독립 site에서 실제 성능 변화 \(\Delta\)AUROC, \(\Delta\)QWK,
\(\Delta\)C-index와 calibration 변화를 종속변수로 두고 다음 감시모델을 비교한다.

- QC only
- embedding/output shift only
- uncertainty/OOD only
- quantitative semantic concordance only
- 위 신호의 결합

### WP5. AI 잔차 기반 신규 지표 발굴

1. 높은 양·음의 residual patch와 모델 간 discordant patch를 수집한다.
2. score, outcome, site를 가린 상태로 병리전문의가 검토한다.
3. 반복 형태를 prototype 또는 concept로 명명한다.
4. 핵·샘·세포·신경·공간 graph로 명시적 수치화한다.
5. 측정 재현성과 기술적 안정성을 검증한다.
6. 독립 코호트에서 endpoint 연관성과 기존 변수 이상의 증분 가치를 평가한다.
7. 가능하면 IHC, 유전체 또는 spatial omics로 생물학적 타당성을 검증한다.

### WP6. 질병별 검증과 임상 전환

- 전립선암: grade, tumor phenotype, PTEN/ERG/AR/SPOP 및 PNI부터 시작한다.
- PNI는 candidate triage, morphology, geometry와 burden 단계를 분리한다.
- 다른 암종에는 전립선 prompt, exemplar, weight, 좌표, NMS와 threshold를 그대로
  전이하지 않는다.
- 독립 개발·검증 코호트, 사전 명시 endpoint, 병리전문의 adjudication 및 임상적
  decision analysis를 통과한 후에만 진단 보조 기술로 승격한다.

## 10. 대상 데이터와 코호트 설계

### 10.1 단계별 표본

| 단계 | 표본 | 목적 |
|---|---|---|
| 방법개발 | 기존 NADT, TCGA-PRAD, PRECISE | 지표 적격성·probe·측정 가능성 |
| 내부 반복 | 동일 코호트 patient-grouped nested CV | optimism 억제와 재현성 |
| 외부검증 | PANDA, SICAPv2, LEOPARD 및 신규 기관 | zero-shot/locked transport |
| 다기관 감시 | 서로 다른 stain/scanner/specimen의 여러 site | 성능 저하 예측모델 검증 |
| 생물학적 검증 | IHC, 분자 assay, spatial omics가 있는 subset | 신규 지표 타당성 |
| 임상 유용성 | 전향 또는 temporal silent deployment | workflow와 안전성 |

### 10.2 표본수 원칙

- 패치 수가 아니라 독립 환자, 사건 수, 기관 수가 추론의 기준이다.
- site-level 성능 저하 예측은 여러 독립 site가 필요하며 두 target site만으로 threshold를
  확정하지 않는다.
- endpoint 유병률, expected effect, 군집구조와 다중검정을 반영한 사전 power simulation을
  수행한다.
- PNI와 같은 희귀 endpoint는 case enrichment와 population performance 평가를 분리한다.

## 11. 통계 및 평가 계획

### 11.1 공통 원칙

- 환자 단위 split와 bootstrap을 사용한다.
- 동일 환자·동일 draw의 모델 비교는 paired analysis로 수행한다.
- site와 specimen type을 명시하고 필요하면 hierarchical model을 사용한다.
- multiple marker family는 사전 정의하고 BH-FDR 또는 계층적 검정을 적용한다.
- undefined bootstrap replicate를 삭제하지 않고 수와 비율을 보고한다.
- sampling seed 반복을 독립 validation으로 간주하지 않는다.

### 11.2 Endpoint별 평가

| Endpoint | 핵심 지표 |
|---|---|
| 암 유무·분자 상태 | AUROC, AP, sensitivity/specificity, calibration |
| Gleason/ISUP | QWK, Spearman, MAE, grade-boundary confusion |
| 연속 형태계측 | CCC, Spearman, MAE, Bland–Altman |
| 공간·contour | Dice/IoU, surface distance, contact/encasement 오차 |
| PNI candidate triage | capture, review coverage, 완전 판독 budget의 precision |
| 재발·생존 | C-index, td-AUC, IBS, calibration, 사건·pair accounting |
| 외부 안정성 | effect preservation, residual shift, worst-site performance |

### 11.3 일치성 해석

| AI–지표 일치 | 실제 외부 성능 | 해석 |
|---|---|---|
| 높음 | 높음 | 기존 병리 개념의 안정적 transport 후보 |
| 낮음 | 낮음 | 기술 drift, 표현형 변화 또는 모델 실패 가능성 |
| 낮음 | 높음 | 유효한 새로운 신호 또는 기존 지표의 불완전성 |
| 높음 | 낮음 | shared shortcut 또는 reference shift 가능성; 최우선 감사 |

## 12. 단계별 로드맵

일정은 데이터·전문의·윤리 승인에 따라 조정하며, 각 단계는 앞선 gate 통과 후 시작한다.

| 단계 | 권장 기간 | 핵심 내용 | 종료 산출물/게이트 |
|---|---:|---|---|
| R0 기반 정리 | 0–3개월 | metric role, truth, 단위, cohort manifest 고정 | 지표 적격성표·분석계획 승인 |
| R1 paired benchmark | 3–9개월 | CONCH–Virchow concept 복원 및 기존 endpoint 재분석 | 동결 benchmark와 재현성 보고서 |
| R2 형태·공간 pilot | 6–12개월 | PRECISE contour 승인 후 morphology/geometry 계측 | 측정 feasibility·오차 보고서 |
| R3 외부 이식성 | 9–18개월 | source–target semantic relation과 실제 성능 비교 | 다기관 transportability 결과 |
| R4 상보성 검증 | 12–24개월 | C, C+M, C+AI, C+M+AI 외부 비교 | 증분 가치와 calibration 결과 |
| R5 신규 지표 발굴 | 18–30개월 | residual review, 명시적 지표화, assay 검증 | 후보 biomarker shortlist |
| R6 독립 확증 | 24–42개월 | 독립 환자·기관에서 locked 검증 | 확증 결과와 실패모드 감사 |
| R7 임상 전환 | 36–48개월 이상 | silent deployment, workflow/reader study | 사용범위·감시계획·임상 근거 |

## 13. 마일스톤과 성공 기준

| 마일스톤 | 성공 기준 | 실패 시 조치 |
|---|---|---|
| M0 지표 분류 잠금 | 모든 지표의 역할·단위·독립성·허용주장 기록 | 모호한 지표 제외 또는 deferred |
| M1 데이터 정합성 | 동일 sample/ROI/FOV와 truth provenance 확인 | 비교 중단 후 manifest 수정 |
| M2 두 모델 benchmark | paired 결과와 환자 bootstrap, clean rerun | 모델·스케일별 제한 명시 |
| M3 concept 복원 | out-of-sample 설명력과 residual table 생성 | 단순 in-sample 상관 주장 금지 |
| M4 외부 relation test | locked source 관계를 target에서 평가 | target 재학습 없이 실패 보고 |
| M5 성능 저하 예측 | semantic signal의 QC/OOD 이상 증분 가치 평가 | acceptance criterion 승격 금지 |
| M6 신규 concept 정의 | blinded morphology와 반복 가능한 공식 | novelty 대신 shortcut/noise로 분류 가능 |
| M7 생물학적 검증 | 독립 assay/outcome과 external replication | exploratory 후보로 유지 |
| M8 임상 유용성 | calibration·workflow·안전성의 전향 근거 | 연구용/진단 보조 이전 단계 유지 |

## 14. 주요 위험과 완화 전략

| 위험 | 결과 | 완화 |
|---|---|---|
| AI와 metric extractor가 같은 모델 사용 | 함께 틀리면서 높은 일치 | 독립 알고리즘·전문의·assay 기준 사용 |
| site/grade/tumor purity confounding | 가짜 생물학적 신호 | site holdout, grade-adjusted model, metadata audit |
| metric 수 대비 작은 표본 | 과적합·선택편향 | 사전 family, nested CV, shrinkage, 외부검증 |
| 해상도·tile 방식 차이 | encoder 비교 왜곡 | 동일 좌표·물리 FOV, shared/native scale 분리 |
| attention의 과해석 | 원인과 설명 혼동 | perturbation·counterfactual·전문의 검증 |
| 낮은 유병률과 불완전 판독 | 성능 과대평가 | coverage 보고, unreviewed≠negative, enrichment 분리 |
| target 재보정 | 외부검증 오염 | locked zero-shot test와 adaptation study 분리 |
| 새 지표 이름 붙이기 편향 | post-hoc biomarker 남발 | blinded review, 독립 정의·재현·assay gate |

## 15. 재현성·윤리·데이터 거버넌스

- 원본 clinician 파일과 승인된 source table을 변경하지 않는다.
- input hash, source pre/post hash, code version, seed, 실행시간과 output hash를 기록한다.
- 그림은 저장된 CSV source table에서 생성한다.
- clean rerun은 문서화된 timestamp를 제외하고 동일해야 한다.
- 환자·슬라이드·후보·focus의 식별과 분석 단위를 명시한다.
- 모델·probe·threshold·prompt·exemplar·좌표·window 변경 이력을 남긴다.
- 현재 frozen-score audit의 점수·prompt·weight·NMS는 재학습·재보정하지 않는다.
- 새 연구에서 adaptation을 수행할 경우 frozen audit과 별도 프로토콜·산출물로 분리한다.
- 개인·기관 정보, 데이터 이용조건과 publication embargo를 준수한다.

## 16. PRECISE PNI 적용 범위

### 현재 가능한 연구

- frozen candidate score와 독립 형태·공간지표의 관계를 평가하는 방법론 pilot
- top-ranked candidate의 형태 평가 가능성과 discordance 원인 분석
- contour 승인 후 nerve diameter, encasement, contact와 distance 계측 feasibility
- residual focus의 blinded hypothesis generation
- 후속 다기관 연구를 위한 feature shortlist 작성

### 현재 불가능한 주장

- whole-slide PNI 진단기 또는 100% sensitivity
- 임상적으로 충분한 고정 후보 budget
- 미판독 영역의 PNI 음성
- PRECISE 모집단의 PNI 유병률 또는 형태 분포
- 14 focus에서 도출한 신규 PNI biomarker의 확립
- 재발·생존·치료반응 및 타 암종 일반화

## 17. 기대성과

1. 의료 정량지표 Tier 1–4와 별도 모델평가·통계·QC registry의 역할과 증거 수준을 명확히 한 정량검증 표준
2. 두 기반 모델의 concept-level 공통성과 차이를 보여주는 paired benchmark
3. 외부 성능 저하를 조기에 경보하는 semantic transportability dashboard
4. 기존 지표와 AI의 실제 중복·상보성에 대한 외부검증 근거
5. shortcut을 배제한 신규 형태·공간 바이오마커 후보
6. 병리전문의가 감사 가능한 human-in-the-loop AI 검증 workflow
7. 질병별 확장 가능한 패키지, 카탈로그, 프로토콜과 재현성 산출물

## 18. 최종 성공 정의

본 연구의 성공은 특정 기반 모델을 우승자로 선정하거나 모든 질병을 진단하는 범용
지표를 만드는 것이 아니다. 다음 조건을 순서대로 충족하는 것으로 정의한다.

1. 정량지표가 독립적이고 재현 가능하게 측정된다.
2. AI–정량지표 관계가 환자분리 방식으로 평가된다.
3. 두 기반 모델의 공통·모델특이 신호가 구분된다.
4. 외부 코호트에서 관계 보존과 실제 성능이 함께 평가된다.
5. semantic concordance가 QC/OOD 이상의 정보를 주는지 검증된다.
6. 잔차 후보가 shortcut 감사를 통과한다.
7. 신규 지표가 독립 assay, outcome과 코호트에서 재현된다.
8. 임상적 주장은 전향·외부 근거가 허용하는 범위로 제한된다.

## 19. 핵심 참고문헌과 방법론

- Human-interpretable pathology features: [Diao et al.](https://pubmed.ncbi.nlm.nih.gov/33712588/)
- C-Path stromal biomarker discovery: [Beck et al.](https://pubmed.ncbi.nlm.nih.gov/22072638/)
- Interpretable Gleason concepts: [PubMed 41062516](https://pubmed.ncbi.nlm.nih.gov/41062516/)
- Concept bottleneck/TIL: [PubMed 38942745](https://pubmed.ncbi.nlm.nih.gov/38942745/)
- TCAV: [Kim et al.](https://proceedings.mlr.press/v80/kim18d.html)
- Concept Bottleneck Models: [Koh et al.](https://proceedings.mlr.press/v119/koh20a.html)
- CKA: [Kornblith et al.](https://proceedings.mlr.press/v97/kornblith19a.html)
- Counterfactual pathology: [MoPaDi](https://pubmed.ncbi.nlm.nih.gov/42308255/)
- Site-specific shortcuts: [Howard et al.](https://pubmed.ncbi.nlm.nih.gov/34285218/)
- Pathology foundation-model robustness: [PathoROB](https://pubmed.ncbi.nlm.nih.gov/42277006/)
- Data drift monitoring guidance: [multi-society statement](https://pmc.ncbi.nlm.nih.gov/articles/PMC10800328/)

## 20. 내부 문서 연결

- 정량지표 패키지 설명: `docs/12_QUANTITATIVE_METRICS_PACKAGE_KO.md`
- 지표·질병 서베이: `infrastructure/packages/vlm_pathology_metrics/SURVEY_KO.md`
- 두 기반 모델 세부 실행계획: `projects/quantitative_foundation_model_validation/docs/research_plan/14_FOUNDATION_MODEL_QUANTITATIVE_METRIC_VALIDATION_PLAN_KO.md`
- 기반 모델 정량검증 사전실험: `docs/15_FOUNDATION_MODEL_QUANTITATIVE_VALIDATION_PREEXPERIMENT_PLAN_KO.md`
- PRECISE 전체 로드맵: `docs/11_PRECISE_PNI_PROJECT_PURPOSE_GOALS_MILESTONES_KO.md`
- Frozen-score 승인 설계: `projects/precise_pni_candidate_triage/docs/designs/2026-08-05-precise-pni-frozen-score-audit-design.md`
- Morphology 승인 설계: `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`
