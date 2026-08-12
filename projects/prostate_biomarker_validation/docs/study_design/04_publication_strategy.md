# 더 강한 논문을 위한 전략

목표 저널: Scientific Reports를 기본으로 하되, 가능하면 더 높은 저널(npj Precision
Oncology / Communications Medicine 등)도 노려본다(2026-07-29 사용자 확인). 다만 Modern
Pathology급을 요구하는 "독립 IHC/시퀀싱 코호트 신규 확보"는 **범위 밖으로 확정 제외**한다
— 협력 가능한 병리과가 실제로 있으나, 새 코호트를 전향적으로 모으는 것은 시간·비용이
너무 크다고 사용자가 명시적으로 판단함(2026-07-29). 기존 후향적 자료(이미 염색된
IHC + 기존 판독 기록)가 있는지 물어보는 정도는 저비용 옵션으로 열어두되, 계획에
포함시키지는 않는다.

## 포지셔닝 — ✅ 결정 완료 (2026-07-29, 세 차례 외부 검토 끝에 확정)

**최종 프레이밍**: "VLM 직접 진단의 환각 문제를 우회한다"가 아니라 —

> **파운데이션 모델의 통계적으로 유의한 신호가 진짜 표적-특이적 생물학적 근거인지,
> 아니면 등급·기관·스캐너·타일스케일·공발생 분자변이 같은 shortcut인지를, 사전에
> 정의된 절차로 체계적으로 판정한다.**

**"Audit인가 Framework인가?" — 최종 답 (핵심 결정, 사용자가 직접 질문해서 확정됨)**:
- **논문의 실체는 audit이다**: "우리는 병리 파운데이션 모델에서 나온 후보 마커들을
  체계적으로 감사(systematically audited)했다" — 과장 없이 방어 가능.
- **재사용 가능한 산출물은 prespecified qualification protocol이다** — 단어 선택이
  중요: "invented"가 아니라 "operationalized." BH-FDR·bootstrap CI·patient-disjoint
  CV·transportability 같은 개별 기법은 전부 기존 원리이며, 우리가 새로 발명했다고
  주장하지 않는다.
- "Framework"라는 단어는 Discussion에서 제한적으로만 쓴다("the protocol/checklist
  can be reused..."). Title/Abstract에서 "we propose a novel statistical framework"
  같은 표현은 쓰지 않는다.
- 재사용 가능한 진짜 기여는 이 감사를 exhaustive하게 수행하면서 실증으로 드러난
  **병리-파운데이션-모델 특이적 함정들**이다: tile-scale mismatch가 조용히 transfer를
  붕괴시킴, site signature가 분자신호처럼 보임, grade-연관이 표적-특이적 형태로
  오인될 수 있음, encoder마다 신호 방향/강도가 다름, assay 라벨 정의에 따라 결과가
  달라짐, fusion은 조건부로만 도움(둘 다 강하고 타깃이 정렬될 때만), 하이퍼파라미터
  차이만으로 경계선 결과가 뒤집힘.

**추천 제목 (2026-07-29 수정, `docs/09_IMPROVING_SUGGESTION.md` 반영)**: "biomarkers"라는
단어가 PTEN/ERG/AR의 외부 분자 검증을 이미 마친 것처럼 보일 위험이 있어 —

> **"Confounder-aware qualification of candidate histomolecular signals from
> pathology foundation-model embeddings in prostate cancer"**

(결과가 강하게 나오면 더 공격적으로: "Distinguishing reproducible histomolecular
signals from shortcuts in prostate pathology foundation-model embeddings.") 부제:
"A reliability map across molecular assays, encoders, sites and clinical outcomes".

**직접 경쟁하는 선행연구 추가 확인 (2026-07-29)**: Dawood et al., "Confounding factors
and biases abound when predicting molecular biomarkers from histological images"
(*Nature Biomedical Engineering*, 2026-03, WebSearch로 확인) — 8,221명(유방/대장/폐/
자궁내막암, **전립선암 없음**), biomarker 상호의존성·grade confounding·임상 baseline
대비 gain 감소를 정확히 우리가 하려는 confounder-audit 방식으로 이미 대규모로 보였다.
**따라서 "confounder audit을 했다"만으로는 이제 이 논문(+Bareja+Neidlinger)과도
겹쳐 novelty가 부족하다.** 이 논문이 다루지 않은, 우리만의 차별점: (a) 전립선암
특이적, (b) cross-encoder(CONCH+Virchow) 재현, (c) **qualification이 실제 독립
임상 결과(LEOPARD 재발)에서 marker 선택을 바꾸는지까지 검증** — Dawood et al.은
바이오마커 상태 자체의 예측 성능만 다루고, 그 예측을 다시 실제 임상 outcome
예측에 연결하는 실험은 하지 않았다. 아래 7-2 LEOPARD 항목을 이 차별점이 명확히
드러나도록 재설계함(3-pool 비교).

**신뢰도 등급 5단계** (4단계에서 수정 — "internally supported, externally untested"
추가, PTEN/ERG/AR처럼 독립 코호트가 없는 경우를 위해 필요): Externally transportable /
Cross-cohort replicable / Internally supported, externally untested / Context-sensitive /
Unsupported·null. 상세 배치는 `docs/03_experimental_results.md` §1 참고.

이 결정과 그 근거(네 차례 외부 검토·검증 과정)의 자세한 경위는 `docs/06_CRITISISM_FROM_OTHERS.md`,
`docs/07_SUGGESTION.md`, `docs/08_SUGGESTION_2.md`, `docs/09_IMPROVING_SUGGESTION.md`
및 메모리 `project-vlm-pathology-status` 참고. `docs/01_motivation.md`,
`docs/02_approach_and_contributions.md`, `docs/03_experimental_results.md`가 이미
이 프레이밍으로 재작성됨.

## 채워야 할 구멍 (우선순위 순)

### 1) VLM 환각 동기의 citable화 — ✅ 완료, 단 이제 보조 동기로 격하 (2026-07-29)
- **인용 오류 수정 완료**: "GPT-4V 병리 환각률 46.8%(arXiv 2406.10185)"는 틀렸음이
  확인되어 정정함 — 46.8%는 Brin et al.(PMC11914349)의 방사선영상(CT/초음파/X-ray)
  수치이지 조직병리가 아님. arXiv 2406.10185는 Chen et al.의 Med-HallMark. 지금은
  Brin et al.을 "의료 영상 전반의 일반적 배경"으로만 인용. PMC11582649(Ferber et al.,
  in-context 반례)는 원문 대조 결과 정확함, 그대로 유지.
- **4개 모델(GPT-5.5, Claude, Quilt-LLaVA, LLaVA-Med) x 4개 과제 정식 벤치마크 실행
  완료**(SICAPv2 Test-split 75패치). 핵심 결과: 위치편향이 오픈소스 2개 모델에서
  95–100%로 독립 재현; 상용 모델은 57–59%로 훨씬 약함; GPT-5.5만 절대채점에서 실제
  등급과 강한 유의 상관(ρ=+0.50); in-context learning은 강제비교 정확도를 3개 모델
  전부에서 악화시킴. 전체 표: `report.tex` §9.6, `docs/01_motivation.md` §4.
- **포지셔닝 변경으로 이 절 전체가 이제 서론의 짧은 보조 동기다** — 이전처럼 논문
  전체의 핵심 축이 아니다. 벤치마크 자체(prompt sensitivity/instability/복수-rater
  보강 등)를 더 다듬을지는 VLM bridge 실험(§7-1 참고)과 함께 낮은 우선순위로 미룸.
- 재현 스크립트: `resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_{gpt5,claude,quilt,llavamed}.py`,
  원본 로그 `resources/projects/prostate_biomarker_validation/model_workspace/vlm_benchmark_cache/`.

### 2) 통계적 엄밀성 — ✅ 완료 (2026-07-28)
`resources/projects/prostate_biomarker_validation/model_workspace/pilot_statistical_corrections.py`로 13개 마커 가설 전부에 대해 일관된 프로토콜로
재계산함(`report.tex` §10.3, Table 20).
- **다중비교 보정(BH-FDR)**: 마커 풀 6개(①②③④⑤⑥) 전체가 보정 후에도 유의성 유지
  ($q<0.01$, ⑤는 보정 전후 모두 null). 추가 후보 7개 중 ETV4만 $q=0.050$으로 경계선에
  남고 나머지는 null.
- **부트스트랩 95% CI**: 환자 단위 클러스터 부트스트랩(2,000회)으로 전부 계산 완료.
- **부수 발견**: 하이퍼파라미터를 전부 고정 `C=1.0`으로 통일하자 ERG 융합 상태 결과가
  "경계선 유의"에서 "명확한 null"로 바뀜 — 이 자체가 §포지셔닝의 "하이퍼파라미터
  민감성" 교훈의 실제 사례.
- **표본 크기 사전 검정력 분석**: 미실시(우선순위 낮음).

### 3) 지표 환산 — ✅ 완료 (2026-07-31)
`pilot_qwk_comparison.py`로 5개 코호트(NADT/PANDA zero-shot/PANDA 재학습×2/TCGA-PRAD
zero-shot/PRECISE zero-shot) 전부 QWK로 재계산, 입력단위/평가단위/외부검증 여부를
명시한 표로 정리. **zero-shot QWK(0.26~0.39)는 PANDA 우승작 완전지도학습(~0.86)에
크게 못 미침** — 예상된 격차이며 이 논문의 SOTA-비경쟁 포지셔닝과 일치. PRECISE
zero-shot(실제 병리 Gleason 대비)만 예외적으로 QWK=0.788이나 n=17이라 과대해석
금지. 상세: `docs/03_experimental_results.md` §6g, `report.tex` "QWK 재계산과 SOTA
비교" 절.

### 4) 마커별 보강
- **① 등급, ② Phenotype**: PANDA zero-shot transfer로 "Externally transportable"
  등급 확보 — 신뢰도 지도에서 가장 강한 증거.
- **③ ERG**: "왜 되는지 모른다"는 미해결 질문이 그대로면 심사자가 반드시 지적함. 동형
  외부 코호트가 없음을 exhaustive하게 확인했으므로(§03 참고) "internally supported,
  externally untested"로 정직하게 표현. 최소 hematoxylin 채널만 분리해 재시험하는
  정도의 직접 검증이 있으면 더 강해짐.
- **④⑥ (PTEN, AR)**: ✅ TCGA-PRAD 자체 site-split 검증 완료. ④는 6개 사이트 전부
  일관(0.59~0.69) → Cross-cohort replicable. ⑥은 사이트 의존성 발견(한 사이트 부호
  반전) → Context-sensitive로 명확히 분류, "약하고 병원 출처에 민감한 마커"로 정직하게
  다룸.
- **⑤ SPOP**: null 보고 자체는 괜찮으나, Discussion에서 왜 문헌(Schaumberg et al.)과
  다른지 짧고 정직하게 다뤄야 함(이미 report.tex에 있음).

### 5) 그림 (전부 없음)
- ROC 곡선 (②④⑤ 등 이진 분류), 산점도(①③⑥ 회귀), forest plot(여러 마커·코호트),
  CONCH vs Virchow bar chart, **신뢰도 지도 자체를 시각화하는 표/그림**(5단계 x 마커,
  이 논문의 새 핵심 주장이므로 우선순위 높음)

### 6) 관련 연구와의 정량 비교표 — ✅ 완료 (2026-07-31, 항목 3과 통합 실행)
DeepGleason(F1 0.806), PANDA 우승작(QWK ~0.862/0.868)과 우리 수치를 나란히 놓은
표 완성 — 항목 3 참고.

### 7) 재현성/코드 공개
- GitHub 공개 저장소 + README + 데이터 접근 방법 정리(Data/Code availability statement).
- 공개 데이터셋(TCGA/PANDA/NADT/LEOPARD/DiagSet/PRECISE) 각각의 이용 약관에 따른
  인용/승인 문구 정확히 기입.

### 7-1) Confounder audit — ✅ 1차 완료 (2026-07-29 착수 → 2026-07-31 1차 완료)
- **Marker qualification gate 사전 고정**: ✅ 완료. `docs/10_protocol_freeze.md`로
  후보 목록·confounder 목록·CV/transfer 방식·하이퍼파라미터·tile scale·primary
  metric·최소 효과크기·5단계 정의를 새 실험(LEOPARD/DiagSet-C/PRECISE) 결과를 보기
  전에 문서로 고정(2026-07-30). git 저장소가 아니라 커밋 타임스탬프는 아직 없음 —
  파일 자체의 작성일로 대체.
- **(임상변수만) vs (이미지만) vs (임상변수+이미지) 비교, ΔAUROC/ΔR², LRT**: ✅ 완료
  (`resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit.py`, 2026-07-31). 마커④PTEN: 결합 모델이 양쪽
  단독을 모두 능가(AUROC 0.607→0.617→0.668), LRT p=0.010으로 grade를 넘어서는
  이미지 고유 정보 확인 → qualified pool 확정. 마커⑥AR: LRT p=0.003으로 유의하나
  이미 site-instability로 배제 확정된 상태라 pool 결정 변경 없음(grade-shortcut은
  아니라는 것만 추가 확인). 마커③은 타깃 자체가 grade라 이 audit 대상에서 제외
  (마커①과 동일 논리) — `docs/03_experimental_results.md` §6b.
- **grade-내부 permutation 검정**: ✅ 완료(`resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_permutation.py`,
  2026-07-31). LRT와 독립적인 비모수 검정으로 같은 결론 재확인: PTEN p=0.014, AR
  p=0.0025 (둘 다 grade-보존 permutation null을 유의하게 상회), ERG-fusion 비승격
  후보는 p=0.063으로 여전히 경계선. 두 방법(모수적 LRT, 비모수 permutation)이
  수렴한다는 것 자체가 결과의 견고성을 뒷받침.
- **TCGA 다중 assay 분자적 일치성**: ✅ 완료(`resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_multiassay_concordance.py`,
  2026-07-31, cBioPortal REST API로 PTEN/ERG mRNA·PTEN RPPA 신규 확보, AR
  mRNA/RPPA는 기존 캐시 재사용). **PTEN(강함, 실측으로 확인)**: CNA소실↔mRNA
  p=7.8e-30, CNA소실↔RPPA p=0.001, mRNA↔RPPA rho=+0.41 — 3개 층 전부 일치.
  이미지 프로브 점수도 mRNA와 유의(rho=-0.145, p=0.02, 방향 일치)하나 RPPA와는
  비유의(rho=-0.064, p=0.48, n=127로 작음) — 이미지가 CNA 콜링 아티팩트가 아니라
  실제 연속적 분자생물학을 일부 반영한다는 근거이나 과장하지 않음. **ERG(중간,
  실측 확인)**: fusion↔mRNA p=6e-43(교과서적), 그러나 이미지 프로브 점수는 mRNA와
  비유의(rho=+0.065, p=0.30) — 이 비승격 후보의 전반적 약함과 일관됨. **AR(약함,
  실측 확인)**: SCORE·mRNA·RPPA 세 층 상호 유의(rho 0.27~0.34)하나, 이미지 프로브는
  mRNA와만 유의(rho=+0.198, p=0.0006)하고 RPPA와는 완전 비유의(rho=-0.014,
  p=0.83) — 마커⑥이 이미 Context-sensitive로 배제된 것과 일관된 추가 증거.
  전체 상세: `docs/03_experimental_results.md` §6c.

### 7-2) 신규 공개 데이터 확장 (2026-07-29, 전부 실제 존재 WebFetch로 확인됨)
- **LEOPARD** (`leopard.grand-challenge.org`): 공식 학습셋 **508명 단일 기관
  (Radboudumc)**, 실제 생화학적 재발+추적시간 라벨. **주의: 570명/2개 기관이라는
  이전 기록은 틀렸음** — 반드시 공식 데이터 페이지 수치(508 train / 99 validation /
  824 hidden test)를 쓸 것, WSI 수와 환자 수, 공개 라벨과 hidden-test를 혼동하지
  말 것.
  - **2026-07-31 재확인**: grand-challenge.org 데이터 페이지 원문을 두 번 직접
    인용·대조해 508/Radboudumc/단일기관 수치를 재확인함(이번 세션 검색에서 "570명,
    Radboudumc+브라질 2기관"이라는 상충 정보가 나왔으나, 이는 LEOPARD 자체가 아니라
    LEOPARD를 활용한 다른 논문이 브라질 코호트를 자체적으로 추가한 별도 데이터셋으로
    보임 — 공식 소스가 우선).
  - **투고 판단 기준 #1 확정 답변: 공개 라벨에 임상 공변량 없음.** `training_labels.csv`는
    `case_id`/`event`/`follow_up_years` 3개 컬럼뿐, grade/PSA/병기 전혀 없음(공식
    페이지 원문 직접 인용으로 확인). 따라서 "incremental value over clinical
    baseline" 주장은 **"outcome association"으로 축소 확정** — 3-pool 비교 자체는
    가능하나 clinical-baseline 대비 추가가치 축은 이 데이터만으로는 성립 안 함.
  - **✅ 데이터 확보 완료(2026-07-31)**: grand-challenge.org 등록이 실제로는
    필요 없었다 — 공개 S3 버킷(`s3://leopard-challenge`, arn 확인·AWS Open Data
    Registry 등재)에 WSI뿐 아니라 라벨 파일도 확장자 없는 `training` 키로 이미
    올라와 있었음(다운로드 스크립트가 `training/`(디렉토리)와 이름이 충돌해 계속
    실패했던 것 — 등록 문제가 아니라 스크립트 버그). 508행(헤더 제외) 전부가 로컬
    WSI 1016개(508 WSI + 508 tissue mask)와 1:1 매칭, 결측 0. event=0(무재발) 421,
    event=1(재발) 87. `resources/data/shared/opendataset/LEOPARD/training_labels.csv`로 저장 완료.
    **단, embargo 조항은 접근 경로와 무관하게 "이 공개 데이터셋을 쓴 결과" 전체에
    적용되므로 여전히 유효 — organizer 확인은 계속 필요.**
  - **⚠️ Publication embargo 발견(2026-07-31, 4차례 외부 검토에서도 안 걸러짐)**:
    공식 데이터 페이지 원문 — "participants... as well as all non-participating
    researchers using the LEOPARD public training dataset, must adhere to the
    publication embargo period... only after the completion of the embargo period
    (after the publication of the LEOPARD challenge journal paper and... baseline
    journal paper)." 챌린지 미참가자에게도 적용되는 조항이며, 공식 챌린지/baseline
    논문이 이미 출판됐다는 증거를 찾지 못함(참가팀 개별 arXiv 논문 몇 편은 있으나
    참가 자격의 별도 규정일 가능성). **사용자 결정(2026-07-31): 데이터는 이미 확보됐으니
    내부 분석부터 진행하고, 실제 논문 투고 전에 embargo 해제 여부를 organizer에게 직접
    문의해 재확인한다.** 초안(`resources/data/shared/opendataset/LEOPARD/organizer_email_draft.txt`)이 이미
    있으나 등록 관련 질문은 이제 불필요(데이터는 S3에서 직접 확보됨) — embargo 질문만
    다듬어서 발송 여부는 사용자가 결정.
  - **핵심 실험 설계 (2026-07-29, `docs/09_IMPROVING_SUGGESTION.md` 반영 — 이 논문에서
  가장 중요한 단일 figure가 될 가능성이 큼)**: 단순히 "qualified marker가 재발과
  연관되는가"가 아니라, **qualification 절차 자체가 marker 선택을 바꾸고 그 선택이
  실제로 더 나은지**를 3개 evidence pool로 비교한다 —
  (1) **Naïve pool**: 내부 CV 성능/p-value만으로 고른 후보,
  (2) **Qualified pool**: confounder·cross-encoder·scale·site·molecular concordance
  게이트를 통과한 후보 — `docs/10_protocol_freeze.md` §8/§9로 확정: **①②③④**
  (③은 게이트4가 구조적으로 적용 안 됨을 확인하고 qualified 확정, ⑥은 site-instability로
  배제 확정),
  (3) **All-candidate pool**: null·context-sensitive 후보(⑤⑥ 등)까지 전부 포함.
  세 pool을 C-index, time-dependent AUROC, integrated Brier score, calibration
  slope, likelihood-ratio test(vs clinical baseline), decision-curve net benefit로
  비교. **"Qualified pool이 naïve/all-candidate pool보다 우수하고, null/context-sensitive
  후보를 포함하면 성능이 저하되거나 불안정해진다"**는 결과가 나오면, qualification
  protocol이 단순 체크리스트가 아니라 실제 결과를 바꾸는 "consequential validation
  strategy"임을 보여주는 이 논문 전체의 가장 강한 근거가 된다 — Dawood et al.도
  Bareja et al.도 이 비교는 하지 않았다.
  - **✅ 실행 완료 (2026-07-31) — 가설과 다른, 그러나 더 정직하고 일반적인 결과가
    나옴.** 508명 전부 CONCH 임베딩 완료(등록 없이 공개 S3 확보), zero-shot 마커
    점수 산출(①②④⑥, ③은 ERG 염색 이미지가 없어 LEOPARD엔 구조적으로 적용 불가),
    3-pool 비교 실행. **원가설("qualified가 naïve/all-candidate보다 우수")은
    기각됨** — 세 pool 전부 C-index 0.334–0.481로 우연(0.5) 이하. 진단 결과
    (라벨 정렬 재검증, 정규화 강도 무관하게 결과 불변) 이는 버그가 아니라 **개별
    마커 단변량 검정 자체가 전부 null**이기 때문(①0.496 ②0.506 ④0.496 ⑥0.525,
    전부 비유의) — 87건뿐인 이벤트 수로 null 공변량들을 다변량 결합하니 노이즈가
    증폭된 것. **도메인 이동 진단**(LEOPARD 자체 임베딩으로 처음부터 재발을
    직접 재학습, zero-shot 아닌 별도 탐색 실험)에서는 PCA 4–64성분 전 구간과
    3개 시드에서 C-index 0.60–0.66로 **일관된 신호를 확인** — 즉 LEOPARD
    임베딩엔 재발 신호가 실재하지만 우리 마커 probe가 그 방향을 못 잡는다는
    뜻. **새 결론**: "특정 타깃에 재현 검증된 마커라도 하류 임상 결과 예측을
    자동 보장하지 않는다 — 같은 임베딩에 그 결과 신호가 실제로 있는데도"라는,
    원가설보다 일반적이고 정직한 교훈으로 재구성. §포지셔닝의 "병리 FM 특유의
    함정" 목록에 추가할 새 항목. 상세: `docs/03_experimental_results.md` §6d,
    `report.tex` "LEOPARD 생존분석" 절.
  - **✅ 후속 검증 완료(같은 날): shortcut 재검토 + Virchow 교차모델 검증으로
    cross-encoder reproducible 등급까지 격상.** (a) 이 in-cohort 신호가
    "관찰기간 부족" 아티팩트가 아닌지 landmark 분석(3y/5y, 조기재발 포함)으로
    직접 검정 — 판별력이 유지/소폭 상승해 아티팩트 가설 기각. (b) 완전히
    다른 파운데이션 모델(Virchow)로 508명 독립 재임베딩 후 같은 진단을 재실행:
    C-index 0.622–0.675로 CONCH와 거의 동일 범위, landmark·censored-상관 검정도
    통과. **CONCH·Virchow 두 모델의 위험도 점수 자체가 ρ=+0.737(p=3e-88)로
    강하게 일치** — 독립 모델이 같은 근본 신호를 포착한다는 가장 강력한 증거.
    상세: `docs/03_experimental_results.md` §6d, `report.tex` "Virchow 교차모델
    검증" 절.
  - **✅ 마커⑦ 외부검증 완료(같은 날) — 새로운 긍정적 결과, 논문 자산으로
    추가할 가치 있음.** LEOPARD 508명으로 학습한 direct-recurrence 모델(고정
    PCA(8)+Cox 계수, 재학습 없음)을 TCGA-PRAD(270명, GDC API로 정상 재구축한
    재발-유사 라벨 — 기존 `bcr.csv`는 출처불명·데이터오류로 폐기하고
    `follow_ups.disease_response` 기반으로 재구축)에 zero-shot 적용한 결과
    **C-index=0.673** — LEOPARD 자체 in-cohort 성능(0.661)과 동등하거나
    높음, landmark 분석(3y/5y)에서도 유지. 마커①②의 PANDA zero-shot 전이와
    같은 급의 **"Externally transportable" 등급 증거**. 다만 (a) 이 마커는
    LEOPARD 결과를 본 뒤 사후 발견된 후보라 protocol freeze 사전 고정 대상이
    아니었음, (b) TCGA-PRAD의 재발-유사 라벨이 LEOPARD의 PSA 기반 정의보다
    거칠다는 점, (c) censored군 위험도-추적기간 상관이 LEOPARD보다 뚜렷함
    (원인 미확정)을 정직하게 명시해야 함. 상세: `docs/03_experimental_results.md`
    §6e, `report.tex` "마커⑦ 외부검증" 절.
  - **✅ 마커⑦ confounder audit 완료(같은 날) — (a) 한계는 해소.** 마커④⑥과
    같은 grade-독립성 감사(Cox 버전)를 TCGA-PRAD 270명에 적용: 임상만(grade)
    C-index 0.680 → 결합(grade+marker7) **0.732**, LRT χ²=10.696(p=0.0011),
    grade-내부 permutation(2,000회)도 독립 재확인(p=0.0015). **grade의 그림자가
    아니라 독립적 정보 확인** — 마커④와 같은 관문 통과. (b)(c) 한계는 여전히
    남음(사후 발견, 거친 outcome 정의, censored 상관). 상세:
    `docs/03_experimental_results.md` §6e, `report.tex` "마커⑦ confounder
    audit" 절.
  - **✅ Virchow 교차검증 완료(같은 날) — 부분 반례, 그러나 해석 가능하고
    §포지셔닝 기존 pitfall과 일관됨.** Virchow zero-shot은 실패(C-index=0.545),
    타일스케일(~2배 불일치) 의심해 TCGA-PRAD를 LEOPARD와 같은 스케일로
    재임베딩했으나 여전히 실패(0.533) — **스케일 가설 기각**. 그러나 같은
    임베딩으로 TCGA-PRAD 자체 in-cohort 재학습은 오히려 CONCH보다 강함
    (C-index 최대 0.795) — Virchow에 신호가 없는 게 아니라 **LEOPARD에서
    학습한 방향이 인코더별로 다르게 전이됨**. 이미 확립된 "인코더마다 신호
    방향/강도가 다르다" pitfall의 새 사례로 해석, CONCH 결과의 의미를
    오히려 보강. 상세: `docs/03_experimental_results.md` §6e,
    `report.tex` "Virchow 교차검증" 절.
- **DiagSet-C** (`ai-econsilio.diag.pl`, 등록 후 공개): 46건, 9인 병리의 독립 판독.
  역할: "ambiguity stress test" — 모델 불확실성이 병리의 간 판독 entropy와 상관되는지
  (risk-coverage curve, selective accuracy). **성능 벤치마크로 쓰지 말 것**(n=46).
  Consensus/unanimous/discordant subset을 분리해서 봐야 함(사람 불일치를 모델 오류로
  자동 간주하면 안 됨).
  - **⏸️ 우선순위 하향(2026-07-31)**: 등록 신청 완료, 관리자 승인 대기 중(최대 24시간,
    우회 경로 없음). LEOPARD 결과로 투고기준 1–4번이 이미 확정적으로 미충족돼
    저널 상한선이 Scientific Reports로 고정된 상태라, 5번(DiagSet-C+PRECISE가
    신뢰도 지도를 지지하는가)을 만점 받아도 등급이 바뀌지 않음 — 더 이상
    "거의 요구조건"이 아님. n=46의 증거력도 원래 제한적이었음. **승인이 나면
    보너스로 추가하되, 더 이상 우선순위로 대기/추적하지 않는다.** PRECISE는
    등록 장벽이 없어 그대로 진행.
- **PRECISE** (Zenodo 20721779): 25명/27세션(2026-08-03 정정 — 이전 "37건"은 검증 안 된
  오기, README/participants.csv 직접 대조로 27세션 확인, `docs/03` §8 참고), H&E-IHC 매칭,
  24,387 pixel 주석. **주의:
  cribriform 주석은 없음**(malignant/benign/stromal/IDC-P/HGPIN/AIP/artifact 7개뿐) —
  cribriform localization 검증에는 못 씀(SICAPv2로 별도 다뤄야 함). 역할:
  malignant/benign gland·atypical lesion의 공간적 face validity, artifact 영역
  false-activation 확인.
  - **✅ 실행 완료(2026-07-31) — 마커① 강한 양성 결과.** 등록 없이 Zenodo에서
    직접 확보(55.6GB). 표준 스케일(~394μm 창)로는 주석이 너무 작고 희소해
    (Benign gland 0.70%/전체픽셀) 실패 → 150μm 창으로 재설계. **마커①**은
    Benign gland(5.22) ≪ Stroma(7.66) < Tumor(8.72) 깨끗한 단조 순서, **실제
    병리 판독 Gleason 점수와 ρ=+0.865(p=7.6e-06, n=17)** — 이 프로젝트에서
    손꼽히게 강한 외부검증. **마커②**는 방향은 맞으나(Tumor>Benign>Stroma)
    미세 gland 단위 구분에서 포화(Benign도 중앙값 1.0) — 정직한 한계로 기록.
    상세: `docs/03_experimental_results.md` §6f, `report.tex` "PRECISE 공간적
    face-validity" 절.
- **DiagSet-C·PRECISE 공통 요구사항 (2026-07-29, `docs/09_IMPROVING_SUGGESTION.md`
  반영)**: 이 둘을 독립적인 보조 실험으로 따로 두지 말고, **위 신뢰도 지도(5단계 분류)와
  같은 스토리를 지지하는지 명시적으로 교차확인**할 것 — 예: "Externally transportable"로
  분류된 마커(①②)가 DiagSet-C에서도 병리의 불일치 케이스에 낮은 confidence를 보이고,
  PRECISE에서도 malignant/benign gland를 잘 구분하는지. Communications Medicine급을
  노린다면 이 일관성이 사실상 요구조건이다.
- **PANDA-PLUS**(546 WSI, pixel-level 재주석): 보류, 직접 다운로드 경로 불명확.
  label-noise sensitivity가 꼭 필요할 때만 마지막에 추가 고려.
- **제외**: 신규 독립 IHC/시퀀싱 코호트(위 상단 참고).

### 7-3) VLM bridge 실험 — 선택, 부록급 (2026-07-29)
Image-only / image+correct evidence / image+shuffled evidence / marker-only /
image+abstention-cue 5조건 비교(shuffled 조건이 핵심 — "evidence가 있으면 좋아지는
것"과 "잘못된 evidence도 맹종하는 것"을 구분). **핵심 결과가 먼저 확정된 뒤에 착수**,
본문이 아니라 Supplementary/보조 figure로. 5개 실험(qualification, survival,
uncertainty, spatial, VLM)을 전부 동등한 비중으로 키우면 "종합선물세트" 논문이 되니
VLM은 항상 가장 작게 유지.

## 실행 순서 (2026-07-29 확정)

1. **Protocol freeze** — ✅ 완료(2026-07-30), 위 7-1의 gate/confounder/기준을 먼저 고정
2. ✅ Confounder audit + grade/site 내부 층화 + TCGA 다중 assay 일치성 완료(2026-07-31,
   위 7-1). 신뢰도 지도(`docs/03_experimental_results.md` §1)는 이번 결과로 등급 변경이
   없어(④ qualified 확정은 이미 반영된 방향과 일치, ⑥ 배제 유지) 표 자체는 그대로 두고
   §6b/§6c에 근거만 추가함.
3. ✅ LEOPARD 생존분석 완료(2026-07-31). 임상 공변량 없음 확인, zero-shot 3-pool은
   null, in-cohort 도메인 이동 진단으로 실제 신호 존재는 확인 — 결과는 원가설과
   다르지만 새로운 핵심 발견으로 재구성됨(위 7-2 참고).
4. DiagSet-C ambiguity stress test — 등록 신청 완료, 승인 대기(우선순위 하향, 위 참고)
5. ✅ PRECISE 공간 face-validity 완료(2026-07-31). 마커① 강한 양성 결과(ρ=+0.865
   실제 Gleason 대비), 마커②는 포화 한계 기록(위 7-2 참고)
6. VLM bridge (core 결과 확정 후, 부록급)
7. PANDA-PLUS (선택, 맨 마지막)
8. ✅ QWK 재계산 + SOTA 비교표 완료(2026-07-31, 위 항목 3/6 참고). 그림 제작·코드
   공개는 아직 미실시
9. 논문 구조 재구성(Abstract–Intro–Methods–Results–Discussion)

## 논문 구조로의 재구성

지금 `report.tex`는 시간순 연구일지 구조. Abstract–Introduction–Methods–Results–
Discussion으로 재구성 필요. 특히:
- **Methods는 한 번만** 명확히 서술(지금은 스크립트마다 조금씩 다르게 설명됨)
- **Results는 표/그림 위주로 압축**, 정정 이력(erratum) 같은 연구 과정 디테일은
  Supplementary로 이동
- 방법론적 발견(해상도 버그, 스케일 불일치)은 실패 사례가 아니라 **"다른 연구자들이
  같은 실수를 피하도록 돕는 재사용 가능한 함정 목록"**으로 프레이밍(§포지셔닝 참고)

## 현재 상태 평가 및 저널 목표 (2026-07-29 갱신, `docs/09_IMPROVING_SUGGESTION.md` 반영)

**결과를 보기 전에 저널을 하나로 확정하지 않는다** — 아래 go/no-go 기준으로 결과가
나온 뒤에 결정한다.

| 완성도 | Scientific Reports | 상위 도전 저널 |
|---|---|---|
| A군(confounder audit+신뢰도 지도)만 완성 | 약 55–70% | 낮음 |
| A+B군, LEOPARD는 연관성 수준(사전 희망 시나리오, 실현 안 됨) | 해당 없음 — 아래로 대체 | 해당 없음 |
| **실제 결과(2026-07-31): LEOPARD zero-shot은 null + 도메인 이동 함정 발견** | 약 55–70%(A군과 동급, LEOPARD가 순증가 없음) | 낮음(LEOPARD 경로 도달 불가) |
| **[사전 가설, 미실현] LEOPARD 3-pool에서 qualified 우위 + incremental value** | — | 이 경로로는 도달 불가로 확정 |
| 독립 molecular validation 추가(범위 밖으로 확정 제외됨) | — | 상위 저널 가능성 크게 상승하나 미실시 |

(통계적 확률이 아니라 외부 검토들의 전략적 추정.)

**최종 투고 판단 기준 (5개 중 몇 개를 충족하는지로 결정) — 2026-07-31 LEOPARD 실행
결과로 1–4번 전부 확정됨**:
1. LEOPARD에 임상 공변량(grade/PSA)이 실제로 있는가? — **❌ 없음.** 공개
   `training_labels.csv`는 `case_id`/`event`/`follow_up_years` 뿐(§7-2 참고).
2. Qualified pool이 recurrence를 유의하게 예측하는가? — **❌ 아니오.** ①②④
   개별 단변량 전부 우연 수준(C-index 0.496–0.506, p 0.85–0.99), qualified
   pool 다변량도 C-index 0.334(우연 이하)로 null.
3. Clinical baseline 대비 incremental value가 있는가? — **❌ 검정 자체가 불가능**
   (1번이 없음이므로 원천적으로 성립 불가).
4. Qualified pool이 naïve/all-candidate pool보다 좋은가? — **❌ 아니오.** 세 pool
   전부 C-index 0.334–0.481로 우연 이하, 우열 자체가 무의미(§7-2 참고). 단,
   **도메인 이동 진단으로 "LEOPARD 임베딩엔 재발 신호가 실재하나 우리 probe가
   전이에 실패했다"는 대안적이고 정직한 발견**을 확보 — 이건 원가설과는 다르지만
   §포지셔닝의 "병리 FM 특유의 함정" 기여 목록에 넣을 수 있는 독자적 결과.
5. DiagSet-C와 PRECISE가 같은 신뢰도 지도 스토리를 지지하는가? — **PRECISE는
   지지함**(마커①이 §신뢰도 지도의 "Externally transportable" 등급과 일관되게
   PRECISE에서도 강한 외부검증 확보, ρ=+0.865). DiagSet-C는 승인 대기로 미실행.
   단, 위에서 이미 확정했듯 1–4번이 전부 미충족이라 5번이 만점이어도 저널
   등급 상한선(Scientific Reports)은 바뀌지 않음 — 그럼에도 PRECISE 결과는
   논문 본문에 넣을 가치가 있는 독자적 양성 증거.

**결론: LEOPARD 경로로는 1–4번 전부 미충족 확정 — Communications Medicine/
Modern Pathology/npj Precision Oncology의 "LEOPARD 임상 결과 중심" 경로는
막혔다.** 5번(DiagSet-C·PRECISE)이 전부 지지해도 LEOPARD 없이 남은 근거만으로는
최대 **Scientific Reports가 현실적 목표**로 하향 조정. 대신 이 논문의 서사는
"confounder audit+신뢰도 지도"를 핵심 기여로, LEOPARD 결과는 "qualification이
타깃 예측력은 보장해도 하류 임상결과 전이는 보장 못 한다"는 **정직한 부정적
결과이자 새로운 병리-FM 함정 사례**로 프레이밍하는 것이 방어 가능한 선택.
- qualification이 주로 기술적 벤치마크 성격 → Journal of Pathology Informatics도
  대안으로 열어둠.
- **npj Digital Medicine은 현재 범위 밖**: VLM bridge가 부록급이고 reader study·임상
  구현이 없어 이 저널 요구조건에 맞지 않음 — VLM 부분을 키우고 싶다면 별도 후속 논문으로.

## 외부 심사(Stanford 스타일) 응답, Tier 1–2 (2026-08-03)

`paper/StandfordReviewe.md`(major revision 권고, "careful, timely, constructive"로
평가)에 대한 1차 대응 완료 — 상세 실험/수치는 `docs/03_experimental_results.md` §8
참고. 저널 등급 평가나 위 go/no-go 기준 자체를 바꾸는 결과는 아니었으나(Scientific
Reports 목표 유지), 심사자가 명시적으로 요구한 투명성·재현성 항목들을 충족시켜
"major revision 통과 가능성"을 높이는 성격의 작업:

- 마커⑦의 grade-only confounder audit 결론이 **완전조정 임상모델(age/T-stage/PSA/margin)
  에서는 유의성을 잃음**(§8a) — 논문의 마커⑦ 주장 강도를 스스로 하향 조정한 정직한
  결과. Table 1(신뢰도 지도)의 마커⑦ 등급 자체는 바꾸지 않았으나(여전히 CONCH
  zero-shot는 externally-transportable 등급 증거), "grade로부터 독립적"이라는 문구가
  "표준 임상변수 전체로부터 독립적"으로 과잉 해석되지 않도록 본문에 명시.
- TCGA 재발 라벨을 표준 PFS/DFS와 벤치마크한 결과 **원 헤드라인 수치(C-index 0.673)가
  다소 라벨-정의-특이적**임을 확인(§8b) — 여전히 우연 이상으로 전이되므로 완전
  철회는 아니지만, 이 사실을 숨기지 않고 명시.
- 나머지 항목(AR forest plot §8c, BH-FDR 전체표 §8d, PRECISE 집계단위 §8e, 타일
  샘플링 명세 §8f, 생존지표 확장 §8g, LEOPARD embargo 문구 §8h, SPOP class-weight
  §8i, 타일/스케일 민감도 §8j)은 기존 결론을 유지하며 투명성·재현성만 강화.
- Tier 3(신규 문헌 인용, 검증된 웹 조사 필요)와 Tier 4(사소한 다듬기)는 이번 패스에
  포함하지 않음 — 별도 세션에서 처리 예정.
