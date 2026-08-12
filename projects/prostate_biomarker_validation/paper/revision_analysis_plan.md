# 개정 실험 계획 (Revision Analysis Plan)

> **2026-08-03 보완:** 미완료 산출물과 전체 stability grid의 재실행 사양은
> `paper/MajorRevision-v1-completion-plan.md`에서 추적한다. 이 문서의 과거 완료율 표현보다
> 해당 보완계획의 항목별 상태를 우선한다.

**작성일**: 2026-08-03 (최초 작성) / **갱신**: 2026-08-03 (Tier1-2 전체 완료 반영)
**목적**: `paper/MajorRevision-v1.md`(원 개정 계획, 이하 "MR-v1")를 실행 가능한 구체 작업
목록으로 변환한다. MR-v1 §1단계가 산출물로 요구한 `revision_analysis_plan.md`가 바로 이
문서다.

## 0. 이 문서와 다른 두 문서의 관계

- **`MajorRevision-v1.md`** — 근본적 재분석·재작성 계획(nested cross-fitting 재설계,
  claim 문구 전수 조정, 원고 9-section 재구성 등). 이 문서가 실행 대상으로 삼는 원본.
- **`revision-prompt-tier-1-2.md`** — Stanford 스타일 외부 심사(`stanford-review.md`)의
  구체적 Questions for Authors에 대한 개별 대응. **✅ 전체 완료**(Tier 1 8/8, Tier 2 2/2 —
  2.1의 스케일-스냅 버그도 발견·수정·재실행까지 완료. 상세는
  `paper/tier-1-2-response-summary.md`). MR-v1과 겹치는 부분은 제한적(§1 참고).
- 두 문서는 목적이 다르므로 완료 상태를 섞어 세지 않는다. 이 문서는 MR-v1 기준으로만
  진행률을 추적한다. **Tier1-2가 끝났다고 MR-v1이 따라서 끝나는 게 아니다** — 아래 §1이
  이미 이를 반영하고 있음.

## 1. 현재 상태 스냅샷 (2026-08-03 갱신, Tier1-2 전체 완료 시점 기준)

| MR-v1 단계 | 상태 | 비고 |
|---|---|---|
| 1. 주장·프로토콜 동결 | 🟢 대부분 완료 (§1.1 P1-3) | six-initial-vs-post-hoc 구분, PTEN/AR/marker7 claim 하향이 원고 전체(abstract/results/discussion/supplement/reliability map 그림)에 전파됨. `paper/sections/*.tex` 전수 문구 감사까지는 아님 |
| 2.1 Nested cross-fitting | ✅ 완료 (§1.1 P0-1) | `pilot_confounder_audit_nested.py`, PTEN/AR/marker7 3개 대상 outer/inner cross-fitting |
| 2.2 Refit 기반 permutation | ✅ 완료 (§1.1 P0-2) | 200회 파일럿 → 2,000회 본실행(marker7-full은 1,998/2,000 유효) |
| 2.3 M0–M5 임상 공변량 계층 | 🟢 대부분 완료 (§1.1) | complete-case M0→M5 전부 실행, paired M5-M4 bootstrap. Multiple imputation만 미실행 |
| 3.1 라벨 provenance 공개 표 | ✅ 완료 (§1.1 P1-1) | 500-case provenance CSV + data dictionary, 원 `bcr.csv` 해시 보존 확인 |
| 3.2 Endpoint 민감도(다중 정의) | 🟢 대부분 완료 (§1.1) | PFS/DFS + persistent-disease 제외(strict recurrence-only, n=220/7 events) + 1–5년 td-AUC 곡선 + 3/5년 calibration까지 실행 |
| 4.1 전체 타일/스케일/시드/인코더 민감도 | 🟡 부분(정확함) | 마커④⑥⑤ 3개(P0-1 실행 세션에서 AR·SPOP까지 확장), tiles{16,32,64}×mpp{0.44,0.88,1.76}, 단일 시드, CONCH만, 90슬라이드 서브샘플. Virchow·5-seed·128-tile·tumor-enriched 미실행 |
| 4.2 AR site forest plot | ✅ 완료 | MR-v1 요구와 거의 일치 |
| 4.3 SPOP 강건성 전체 | 🟡 부분 개선 | class-weight + site-restricted + **80% power MDE(AUROC=0.661) 분석 추가**(§1.1 P2). tumor-enriched·Virchow·tile스윕 전용 실행은 미실행 |
| 5. 생존분석 보고 강화 | 🟢 대부분 완료 (§1.1 P2) | LEOPARD 3-pool(IBS/calib/HR) + 마커⑦ **1–5년 td-AUC 곡선 + 3/5년 calibration plot**(fig_marker7_survival_curves) 추가 — MR-v1이 명시한 항목 대부분 충족. bootstrap ΔC-index/ΔBrier CI만 미실행 |
| 6. 재현성 정비 | ✅ 대부분 완료 (§1.1 P1-2) | `/tmp/claude-*` 의존성 0개로 제거 확인, 13가설 CSV에 encoder/validation-type/reliability-tier + 17-test global q 추가 |
| 7. 원고 재구성(9-section) | ✅ 완료(2026-08-03) | Virchow 교차검증 완료 후 착수, `docs/03` §9c 참고. xelatex 검증·수치 앵커 검증 완료 |

**전체 완료율(2026-08-03 최종 갱신, P0/P1/P2 실행 + Virchow 교차검증 + 7단계 원고
재구성까지 반영)**: 약 **80–85%**. 남은 건 P2의 지엽적 확장뿐(multiple
imputation, Virchow 5-seed/128-tile/tumor-enriched, bootstrap ΔBrier) — 7단계(원고
재구성)까지 끝났으므로 MR-v1의 7개 단계 중 실질적으로 완료되지 않은 것은 없다.
처음 이 문서를 쓸 때 "MR-v1을 실제로 진행하려면 P0부터 새로 시작해야 한다"고 했던 게 실제로
다른 세션에서 그대로 실행된 것으로 확인됨(§1.1, `paper/revision_execution_summary.md`).

### 1.1 실행 갱신 (2026-08-03, 본 계획 실행 후)

- **P0-1 완료**: `resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested.py`; outer/inner patient-disjoint
  cross-fitting, 2,000 patient-bootstrap CI, fold/prediction/summary CSV 생성.
- **P0-2 완료**: 200회 파일럿 후 2,000회 본실행. PTEN/AR/marker7-grade는 2,000/2,000,
  marker7-full은 1,998/2,000 유효 fit. 결과는
  `resources/projects/prostate_biomarker_validation/model_workspace/confounder_refit_permutation_final2000_{summary,null}.csv`.
- **2.3 임상 계층 완료(complete-case)**: M0--M5와 missingness, paired M5--M4 bootstrap.
  Multiple imputation은 아직 수행하지 않음.
- **P1-1 완료**: 500-case provenance CSV + data dictionary + persistent-disease 제외
  sensitivity endpoint. 원 `bcr.csv` hash/라벨은 보존됨.
- **P1-2 완료**: `/tmp/claude-*` Python 의존성 0개, clinical fetch/cache 추가, 13가설
  CSV에 encoder/validation/reliability 및 17-test global q 추가.
- **P1-3 완료**: six-initial-vs-post-hoc 구분, PTEN/AR/marker7 claim 하향, 원고와
  reliability-map 그림 재생성.
- **P2 부분 확장**: endpoint/PFS/DFS/persistent-only, 1--5년 td-AUC 및 calibration,
  SPOP bootstrap CI/MDE, PTEN+AR+SPOP 공통 9-cell scale/tile grid를 실행. Virchow,
  5-seed, 128 tiles, tumor-enriched sampling은 미실행.
- **P3 미실행**: 9-section 재구성은 이 문서의 원래 권고대로 별도 편집 세션으로 남김.

핵심 판정은 기존 문구보다 약해졌다. PTEN과 AR의 nested held-out 증분은 지지되지 않고,
marker7은 grade-only에서만 증분이 있으며 full clinical+site 모델에는 추가 가치가 없다.
상세 수치는 `paper/revision_execution_summary.md`에 고정한다.

## 2. 코드 감사로 확인한, 계획 대비 실제 격차 (중요 — 재작업 방지용)

MR-v1 초안 작성 시점에 예상했던 것과 실제 기존 코드를 다시 읽어 확인한 내용이 다른
부분들. 아래를 무시하고 §2.1/2.2를 처음부터 재설계하면 이미 있는 것을 중복 구현하게 되므로
먼저 기록해 둔다.

- **markers 4/6의 image score는 이미 out-of-fold다** (`pilot_confounder_audit.py`의
  `image_oof_binary`/`image_oof_continuous`, patient-disjoint `GroupKFold(5)`). MR-v1 §2.1이
  요구하는 "training 환자만으로 probe 학습"은 이 부분에서 **이미 충족**돼 있다. 남은 진짜
  격차는: (a) 그 OOF 스코어를 이용한 LRT 자체는 **in-sample**로 계산된다는 점(전체
  코호트에 clinical-only/combined 모델을 적합해 카이제곱 검정) — outer-fold별
  ΔAUROC/ΔR²를 out-of-sample로 직접 산출하지 않음. (b) 마커⑦의 image score는 OOF조차
  아니고 **완전 고정된 zero-shot 점수**(LEOPARD에서 학습, TCGA-PRAD 데이터를 전혀 보지
  않음) — 이건 nested CV보다 오히려 더 엄격한 형태의 외부성이라, 마커⑦에는 nested
  cross-fitting을 다르게 적용해야 함(아래 P0-1 참고).
- **permutation test는 image score를 고정한 채 라벨만 섞는다**
  (`pilot_confounder_permutation.py`, `pilot_marker7_confounder_audit.py`의
  `permutation_test`) — MR-v1 §2.2가 요구하는 "permutation마다 probe 재학습"이 실제로
  빠져 있는 부분. **단, 재확인 결과 이 작업의 계산 비용은 처음 우려했던 것보다 낮다**:
  probe 자체가 512차원 임베딩 위 CPU 전용 선형모델(RidgeCV/LogisticRegression) 5-fold
  적합이라 1회당 1초 미만 — 2,000회 반복해도 마커당 수십 분 내로 끝날 가능성이 높다(3개
  마커 전부 해도 총 1–3시간 추정, GPU 불필요). §3 P0-2에서 실측 후 조정.

## 3. 우선순위와 실행 계획

### P0 — 핵심 주장 신뢰성에 직접 영향 (결과가 논문 결론을 바꿀 수 있음)

**P0-1. Nested cross-fitting 기반 증분 성능 (MR-v1 §2.1)**
- 대상: 마커④(PTEN), 마커⑥(AR), 마커⑦(recurrence).
- 마커④/⑥: outer `GroupKFold(5)` 각 fold에서 (a) clinical-only, (b) image-only(이미 있는
  OOF 스코어 재사용 가능), (c) combined 모델을 **train fold에서만 적합**하고 outer test
  fold에서 ΔAUROC/ΔR² 산출 → 5개 fold의 out-of-sample 증분을 patient-cluster 부트스트랩
  (2,000회)으로 CI화. 기존 in-sample LRT는 **보조 지표로 유지**(제거하지 않음 — 둘의
  일치/불일치 자체가 보고할 가치가 있음).
- 마커⑦: image score가 이미 zero-shot(LEOPARD 학습, TCGA-PRAD 미사용)이므로, outer CV는
  clinical 모델(grade 또는 fully-adjusted)만 train fold에서 적합하고, marker7_risk는
  그대로 고정 사용 — "nested"의 의미가 4/6과 다름을 명시.
- 산출물: `resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested.py`(신규, 기존 `pilot_confounder_audit.py`
  의 `load_data`/OOF 함수 재사용), 결과 CSV.
- 비용: CPU 전용, 5-fold × 3모델 적합 — 수 분 이내.
- **결정 필요**: 기존 in-sample LRT 결과(PTEN p=0.010, AR p=0.003, marker7 p=0.0011/0.215)와
  nested out-of-sample 결과가 어긋나면(가능성 있음, 특히 marker7의 fully-adjusted 케이스는
  이미 약해진 상태) 논문의 Table 4(confounder audit)를 어떻게 재구성할지 사용자 확인 필요.

**P0-2. Refit 기반 permutation test (MR-v1 §2.2)**
- 실행 순서: 먼저 **200회로 파일럿**(계획대로) 돌려 실제 걸리는 시간 측정 → 문제없으면
  2,000회로 본실행.
- 대상: PTEN, AR, marker7(grade-only와 fully-adjusted 버전 둘 다).
- 매 순열마다: 라벨을 grade-stratum 내에서 섞고 → probe를 train fold에서 재학습(nested,
  P0-1과 동일 outer CV 구조) → out-of-sample 증분 재계산 → null 분포에 저장.
- 기존 "OOF 스코어 고정" 버전 결과도 삭제하지 않고 **나란히 보고**(두 방법이 수렴하는지가
  강건성 근거).
- 비용: 위 §2 재확인대로 마커당 수십 분~1시간 추정(200회 파일럿으로 먼저 검증 후 정확한
  추정치 확보).

**우선순위 근거**: 이 둘이 끝나야 confounder audit 전체(Table `tab:confounder`,
`tab:supp-marker7-clinical`)를 nested/refit 기준으로 재작성할 수 있고, 이게 MR-v1이 가장
강조하는 "in-sample 결과를 신뢰할 수 있는가"라는 심사 우려에 직접 답한다.

### P1 — 투명성·재현성 (심사자 신뢰도에 영향, 계산 비용 낮음)

**P1-1. TCGA 재발 라벨 provenance 공개 표 (MR-v1 §3.1)**
- `resources/data/shared/opendataset/TCGA-PRAD-BCR/build_bcr_labels.py`를 확장해 환자별: 원시 follow-up 기록,
  disease_response 값, event/censoring 판정 근거, 제외 사유, 최종 라벨을 CSV로 출력.
- 개인정보 없음(TCGA case ID는 이미 공개 식별자) — 공개 가능.
- 비용: 낮음(이미 로드된 GDC 데이터 재포맷).

**P1-2. 재현성 정비 (MR-v1 §6)**
- `pilot_tcga_prad_site_split.py`, `pilot_statistical_corrections.py` 등 기존 스크립트의
  `CBIOPORTAL_SAMPLE_JSON` 스크래치패드 절대경로를 `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/`류
  저장소 상대경로로 교체(이미 Tier1-2에서 신규 스크립트는 이렇게 했음 — 기존 스크립트도
  맞춤).
- `resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv` 13행에 `encoder`, `validation_type`,
  `reliability_tier` 컬럼 추가(스크립트 재실행 없이 기존 결과에 메타데이터만 추가 가능).
- 비용: 낮음, 순수 리팩터링.

**P1-3. 1단계 claim 문구 조정 (MR-v1 §1)**
- 계산 작업 아님 — `paper/sections/*.tex` 전체를 훑으며: "prespecified" 전면 사용을
  "일부 downstream qualification 분석 전에 prospectively frozen"으로, 마커⑦을 모든
  표/그림에서 `post-hoc exploratory marker`로 라벨링, PTEN을 `cross-cohort validated`
  대신 `multisite-stable within TCGA-PRAD`로 표현 조정.
- **결정 필요**: 이미 Tier1-2에서 문구를 여러 곳 수정했으므로, 전면 재작업 전에 현재
  문구가 실제로 과장됐는지 항목별로 확인 후 조정(무작정 전부 바꾸지 않음).

### P2 — 있으면 좋음, 시간 허용 시

- **4.1 확장**: 스케일-스냅 버그는 **이미 수정 완료**(Tier1-2 2.1,
  `pilot_tcga_prad_scale_tile_sensitivity.py`의 `pick_level_for_scale` + windowed zarr read).
  이제 남은 건 이 검증된 로직을 그대로 재사용해 마커 범위만 확장하는 것(PTEN 외 1–2개,
  예: 마커①/⑥). Virchow·seed≥5·tile 128은 GPU 여유가 있을 때만.
- **4.3 확장**: tile count 스윕(16/64/128), tumor-enriched sampling, Virchow 교차, 최소
  검출가능 AUROC power 분석.
- **5단계 확장**: 1–5년 전체 td-AUC 곡선과 calibration plot(그림), bootstrap
  ΔC-index/ΔBrier CI.
- **3.2 확장**: persistent-disease 제외 라벨 변형, endpoint별 3/5년 landmark 재구성.

### P3 — 별도 세션 권장

- **7단계 원고 재구성**: 현재 장문 프로젝트 보고서 스타일을 Introduction–Prespecified
  components–Cohorts–Qualification gates–Core results–Confounder/site audits–Downstream
  transfer–Failure modes–Limitations의 9-section으로 재편성, Figure 1–6 재설계. 이는
  글쓰기 작업이며 위 P0/P1 결과가 먼저 나와야 무엇을 어떻게 재배치할지 정할 수 있으므로
  마지막에 진행.

## 4. 실행 순서 제안

1. P0-1 (nested cross-fitting) → 결과가 기존 in-sample 결론과 일치하는지 확인
2. P0-2 (200회 파일럿 → 실측 비용 확인 → 2,000회 본실행)
3. P0-1/P0-2 결과를 반영해 `results.tex`의 confounder audit 절 재작성 여부 결정
4. P1-1, P1-2 (병행 가능, 비용 낮음)
5. P1-3 (문구 조정 — P0 결과가 나온 뒤 톤을 맞추는 게 순서상 자연스러움)
6. 시간이 남으면 P2 항목 순서대로
7. P3(원고 재구성)는 P0/P1 완료 후 별도 세션

## 5. 사용자 확인이 필요한 열린 질문 (질문 1·3은 실행 완료로 해소됨)

1. ~~P0-1/P0-2에서 nested/refit 결과가 기존 in-sample 결과와 달라질 경우, 하향 조정할지~~
   — **해소됨**: 실제로 PTEN/AR의 nested 증분이 유의하지 않게 나왔고, MR-v1 원칙대로
   기계적으로 하향 조정됨(abstract/results/discussion/reliability map 전부 갱신).
   `docs/10_protocol_freeze.md` §9에 "PTEN을 향후 qualified pool에서 제외해야 한다"는
   판정과 함께, **이미 frozen 상태로 실행된 LEOPARD 3-pool 구성(마커4 포함)은 사후
   변경하지 않고 역사적 분석으로 유지**한다는 결정도 명시적으로 기록됨 — 이 결정이
   맞는지는 여전히 검토 가치가 있음(협의 필요 시 참고).
2. ~~P2/P3에 얼마나 시간을 투자할지~~ — **부분 해소됨(2026-08-03)**: 7단계 시작 전
   가장 리스크가 큰 잔여 항목(Virchow로 nested confounder audit 교차검증, PTEN/AR이
   CONCH 특이적 아티팩트가 아닌지 확인)을 먼저 실행 — **Virchow도 CONCH와 수렴**
   (PTEN ΔAUROC=+0.035 [-0.013,+0.087], AR ΔR²=+0.019 [-0.015,+0.051], 둘 다 CI가
   0을 포함해 같은 결론). §9b(`docs/03`) 참고. 남은 P2(multiple imputation, Virchow
   5-seed/128-tile/tumor-enriched, bootstrap ΔBrier)는 우선순위 낮음으로 보류하고
   **7단계(원고 재구성) 착수 가능**하다고 판단.
3. ~~P0-2 200회 파일럿 실측 비용~~ — **해소됨**: 2,000회 본실행 완료(marker7-full만
   1,998/2,000 유효, surgical-margin separation으로 인한 Cox 수렴 실패 2건은 0으로
   대체하지 않고 제외 처리).

## 6. 부록: 다른 세션에서 이어받을 때 필요한 정확한 참고자료

이 문서만 보고도(이 대화의 다른 맥락 없이) P0부터 바로 시작할 수 있도록, 이 계획을 세우며
실제로 확인한 소스·경로·산출물을 아래에 정리한다. 아래 파일 경로/라인 번호는 **2026-08-03
기준**이며, 이후 코드가 바뀌면 달라질 수 있다.

### 6.1 실행 환경

- Python: `HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python` (CONCH, sksurv,
  lifelines, statsmodels 등 이미 설치된 전용 venv).
- P0-1/P0-2(nested cross-fitting, refit permutation)는 **캐시된 임베딩만 재사용**하므로
  CPU 전용, GPU 불필요.
- 재임베딩이 필요한 작업(P2의 4.1/4.3 확장 등)만 GPU 필요 — `nvidia-smi`로 빈 GPU 확인 후
  `CUDA_VISIBLE_DEVICES=<free_gpu>` 지정(이 서버는 GPU 10개를 여러 세션이 공유하므로 항상
  몇 개는 사용 중일 수 있음).

### 6.2 먼저 읽을 문서 (순서대로)

1. `paper/stanford-review.md` — 원 외부 심사 전문(Questions for Authors 10개).
2. `paper/revision-prompt-tier-1-2.md` + `paper/tier-1-2-response-summary.md` — 이미 완료된
   1차 대응과, 리뷰어 질문 각각에 뭘 했는지의 매핑. 여기서 쓴 컨벤션(스크립트 네이밍,
   docstring 스타일, CSV 저장 방식)을 그대로 따를 것.
3. `paper/MajorRevision-v1.md` — 이 실험계획이 실행 대상으로 삼는 원본 계획.
4. `docs/10_protocol_freeze.md` — 마커 풀(6+경계 1개), confounder 목록, CV/transfer 용어
   정의, 하이퍼파라미터(고정), 5단계 신뢰도 등급, LEOPARD 3-pool 소속 규칙이 전부 여기
   고정돼 있음 — **새 실험도 이 규칙을 위반하면 안 되고, 위반이 불가피하면 이 문서 §9
   변경이력에 사유·타임스탬프를 남길 것**.
5. `docs/03_experimental_results.md` §6b/§6c(기존 confounder audit)·§8(Tier1-2 전체 상세,
   a~j) — 지금까지 나온 모든 수치의 근거.
6. `docs/04_publication_strategy.md` — 저널 목표, go/no-go 기준, 실행 우선순위.

### 6.3 재사용 가능한 캐시된 데이터 (재다운로드·재임베딩 불필요)

- `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/X.npy` + `meta.csv` — TCGA-PRAD 300슬라이드/273환자 CONCH
  임베딩(0.88μm/px, 16타일/슬라이드 표준 설정). `meta.csv` 컬럼: `file_name`, `case_id`,
  `erg_fusion`, `n_tiles`.
- `resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/X.npy` + `meta.csv` — LEOPARD 508환자 CONCH 임베딩
  (`case_id`/`event`/`follow_up_years` 포함).
- `resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv` — GDC 재구축 재발라벨(`case_id`/`event`/`follow_up_y`,
  493명, `build_bcr_labels.py`로 재현 가능).
- `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/{gdc_tstage_age.json, prad_pub_patient_clinical.json,
  prad_pancan_clinical.json}` — age/T-stage(GDC), PSA/margin(cBioPortal `prad_tcga_pub`
  patient-level), PFS/DFS(cBioPortal `prad_tcga_pan_can_atlas_2018`). 전부
  `resources/projects/prostate_biomarker_validation/model_workspace/fetch_tcga_prad_clinical_extra.py`로 재현 가능(재다운로드 없이 이미 로컬에 있음).
- cBioPortal `prad_tcga_pub` **sample-level** molecular JSON(REVIEWED_GLEASON_SUM,
  PTEN_CNA, AR_SCORE, SPOP_MUTATION 등, `pilot_confounder_audit.py`/
  `pilot_statistical_corrections.py`가 사용) — 현재 세션-스크래치패드 경로
  (`/tmp/claude-*/.../scratchpad/prad_clinical_sample.json`)에 있어 **다른 세션에서는
  사라져 있을 수 있음**. 없으면 `pilot_confounder_audit.py` 상단의 cBioPortal REST API
  패턴으로 재요청(등록 불필요, 공개 API).

### 6.4 Tier1-2에서 새로 생긴, P0/P1이 바로 재사용할 산출물

- `resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv`(13행: 6마커 풀 + 7 비승격 후보, patient/slide
  effect·CI·p·BH-FDR q).
- `resources/projects/prostate_biomarker_validation/model_workspace/marker7_extended_confounder_summary.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv`,
  `resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/spop_classweight_ablation_summary.csv`,
  `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_scale_tile_sensitivity_summary.csv`.
- `resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_confounder_audit.py`의 `load_extra_covariates()`(완전조정 임상
  공변량 로딩)와 `extended_confounder_audit()`(grade-only vs fully-adjusted 비교 구조) —
  P0-1이 마커⑦에 그대로 재사용 가능.
- `resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_scale_tile_sensitivity.py`의 `pick_level_for_scale()` — 타일
  스케일이 관련된 어떤 향후 작업도 **반드시 이 함수를 재사용**할 것(§1의 스냅 버그
  재발 방지, 직접 새로 짜지 말 것).

### 6.5 §2 코드 감사의 정확한 근거 (파일:라인, 2026-08-03 기준)

- `resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit.py:68` `load_data()`, `:87` `image_oof_binary()`, `:98`
  `image_oof_continuous()` — 마커4/6의 image score가 이미 5-fold `GroupKFold` OOF임을
  보여주는 실제 구현.
- `resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_permutation.py:45` `audit_binary_permutation()`, `:81`
  `audit_continuous_permutation()` — OOF 스코어를 고정한 채 라벨만 grade-stratum 내에서
  섞는 현재 permutation 구현.
- `resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_confounder_audit.py:74` `build_cohort()`(마커⑦ zero-shot 스코어 —
  TCGA-PRAD 데이터를 전혀 쓰지 않고 LEOPARD에서 고정), `:143` `extended_confounder_audit()`
  (완전조정 임상모델), `:225` `permutation_test()`(마찬가지로 스코어 고정).

### 6.6 이미 검증된 사실 (재검증 불필요 — "verify before trusting" 원칙에 따라 API 직접
조회로 확인됨)

- TCGA-PRAD SVS 파일의 실제 타일드 피라미드 레벨: native mpp $\approx\{0.25, 1.0, 4.0,
  8.0\}\,\mu$m/px뿐(레벨 1은 non-tiled 썸네일) — `tifffile`로 직접 확인(2026-08-03).
- cBioPortal `prad_tcga_pub` patient-level clinical-data에 `PREOPERATIVE_PSA`(167/270
  populated)·`RESIDUAL_TUMOR`(217/270)가 실제로 존재 — **sample-level JSON에는 없음**
  (혼동하지 말 것).
- cBioPortal `prad_tcga_pan_can_atlas_2018`에 `PFS_STATUS`/`PFS_MONTHS`(494/494),
  `DFS_STATUS`/`DFS_MONTHS`(334/494) 존재.
- GDC `cases` 엔드포인트에 `diagnoses.ajcc_pathologic_t`, `demographic.age_at_index`
  전체(500/500 TCGA-PRAD 케이스) 존재.
