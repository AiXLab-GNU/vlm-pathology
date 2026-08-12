# MajorRevision-v1 실험·산출물 현황 감사

- 감사 기준일: 2026-08-06 (US/Eastern)
- 작업 범위: 현황 재검증, 결과 해석, 잔여 위험 식별
- 비범위: 원시 결과 수정, endpoint 재구성, 새 GPU/장시간 실험, 원고 수치 갱신
- 상태 기준 문서: `paper/MajorRevision-v1.md`, `paper/MajorRevision-v1-completion-plan.md`

## 1. Executive summary

1. 360-cell 안정성 grid의 **GPU 계산은 완료**되었다. 여섯 runner의 `cell_results.csv`를 frozen spec과 대조한 결과 360/360 고유 cell이 모두 `complete`였고 누락·예상 밖 결과·중복은 각각 0건이었다. `fold_results.csv`는 1,800/1,800행이며 모든 cell에 정확히 다섯 fold가 있다.
2. 그러나 P1의 **정식 산출물 패키지는 미완료**이다. 통합 cell/fold 결과, 72행 seed 요약, contrast 표, 좌표 manifest, run manifest, figure-source CSV와 QC 보고서가 없다. Frozen spec의 `status`도 360행 모두 `pending`으로 남아 있다. 따라서 P1의 엄격한 상태는 `partial`이다.
3. 새 grid는 현재 원고 해석을 실질적으로 바꾼다. SPOP은 강건한 null이라기보다 scale에 따라 chance 위·아래를 오가는 설정 민감 신호이다. Marker 7은 CONCH에서는 강하지만 Virchow가 전면 실패한 것이 아니라 0.44 mpp에서 약하고 1.76 mpp에서 회복되는 encoder×scale 의존 전이이다.
4. AR의 60개 grid cell은 모두 양의 rho였지만, 기존 leave-one-site-out의 모든 site CI는 0을 포함한다. 따라서 “site-unstable”보다는 “pooled association은 재현되나 site transportability는 미해결”이 근거에 맞다.
5. NADT TIFF 경고는 463개 slide 중 2개(0.432%)의 terminal page offset으로 추적되었다. 두 slide 모두 모든 NADT coordinate shard에 64 tiles로 유지되었고 cell 실패나 cohort 감소는 없었다. 이는 **제외가 없었다는 증거**이지 pixel-level 영향이 없다는 증거는 아니다.
6. P0–P6 엄격 상태는 `partial, partial, partial, partial, not_done, partial, not_done`이다. 상태를 complete=1, partial=0.5, not_done=0으로 동일 가중하면 2.5/7, 즉 **35.7%**이다. 이는 운영상 산출물 점수일 뿐 과학적 완성도 통계가 아니다.
7. 기존 11개 체크리스트를 “완전 완료만” 세면 5/11=45.5%이므로 이전의 45–50% 추정과 모순되지 않는다. 큰 계산 부담은 끝났지만, exact PFI, paired survival 비교, claim 수정, figure/table lineage, 최종 QA가 남아 과학적 claim closure는 아직 준비되지 않았다.
8. 감사 시점에 실행 중인 stability Python/GPU process는 없었다. `vlm_stability` tmux session에는 계산이 아닌 idle shell만 남아 있었다. 다른 사용자의 VLLM process는 본 감사 범위에서 제외했다.

## 2. 감사 방법과 상태 판정 기준

### 2.1 상태 정의

| 상태 | 판정 규칙 |
|---|---|
| `complete` | 계획된 핵심 분석, 저장 산출물, 해석 반영, 검증 조건이 모두 충족됨 |
| `partial` | 계산 또는 일부 산출물은 있으나 계획된 결과 패키지·계보·해석·QA 중 하나 이상이 남음 |
| `not_done` | 계획의 핵심 분석 또는 산출물이 시작되지 않았거나 근거 파일이 없음 |

`360/360 complete`는 runner 계산 상태이고, P1 `complete` 판정은 아니다. 또한 아래 기술통계는 여섯 raw runner CSV를 읽기 전용으로 합쳐 감사 중 계산한 값이다. 아직 정식 `resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv`가 아니므로 원고에 직접 전사해서는 안 된다.

### 2.2 확인한 무결성 조건

- `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv`의 360개 `cell_id`와 실제 결과의 exact set equality
- cell/fold duplicate, missing, unexpected, non-finite metric, 비정상 status
- cell당 fold 0–4와 frozen patient-fold count 일치
- runner별 cell/fold 행 수와 coordinate shard 60개 존재 여부
- coordinate 내부 seed/MPP 일치, slide별 tile rank 0–63의 완전성
- marker별 cohort slide/patient/event count의 조건 간 일관성
- 여섯 log의 traceback/error/warning 분리 집계
- 주요 input/result의 size, mtime, SHA256
- 계획 문서, claim/endpoint 문서, provenance, cohort/environment/figure/PDF 계보의 현재 상태

## 3. P0–P6 상태

| Package | 상태 | 확인된 근거 | 완료를 막는 핵심 격차 |
|---|---|---|---|
| P0 주장·endpoint·provenance | **partial** | `paper/claim_evidence_matrix.csv` 7 claims, `paper/endpoint_hierarchy.csv` 9 endpoints, `paper/protocol_provenance.json`, `cohort_manifest.csv` 4,890행, 환경 파일과 reproduction 문서 존재 | grid가 pending으로 남음; 일부 source가 불완전/교차 연결됨; runner 3개와 환경 2개의 provenance hash 불일치; embedding hash와 data dictionary 없음 |
| P1 stability grid | **partial** | 360/360 cells, 1,800/1,800 folds, 60 coordinate shards, 모든 metric finite | 통합 결과·summary·contrast·coordinate/run manifest·QC·figure source 부재; spec status 360행이 여전히 pending |
| P2 AR/SPOP | **partial** | `resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/spop_classweight_ablation_summary.csv`, 전체 grid의 AR/SPOP 120 cells | site 분포/metadata 표와 저장된 SPOP site 비교·90% MDE 부재; tumor enrichment와 128 tiles 미실시; 현재 claim 문구가 grid와 불일치 |
| P3 survival/PCA | **partial** | M5−M4 paired ΔC, clinical hierarchy, confounder nested 결과, 두 encoder의 PCA sweep 존재 | same-patient/same-draw ΔC 전체 비교와 ΔIBS 부재; M0–M5 공통 cohort 비교 부재; PCA k는 inner nested 선택이 아님; MI 미실시 |
| P4 exact PFI | **not_done** | `paper/endpoint_hierarchy.csv` E08이 정확히 `not_done`으로 표시 | 공식 TCGA-CDR PFI event/time source, concordance, 동일 사양 성능 분석이 없음 |
| P5 figure lineage | **partial** | 활성 PDF와 여러 생성 script/CSV 존재 | `paper/figure_manifest.csv` 없음; figure와 6개 result table에 hard-coded 수치; 절대경로; 한 명령 재생성 불가; Figure 9가 구 grid 사용 |
| P6 최종 QA | **not_done** | 기존 `paper/main.log`에서 unresolved citation/reference 경고는 발견되지 않음 | compliance/numeric/reproducibility report 없음; 두 번의 XeLaTeX 실행 증거 없음; PDF가 grid보다 58시간 24분 오래됨 |

### 3.1 완료율을 읽는 두 방법

| 관점 | 산식 | 결과 | 용도와 한계 |
|---|---:|---:|---|
| P0–P6 동일 가중 반점수 | `(5 partial × 0.5 + 2 not_done × 0) / 7` | **35.7%** | 현재 deliverable closure를 보수적으로 표현; package 크기 차이는 반영하지 않음 |
| 원 계획 11-item strict count | `5 fully complete / 11` | **45.5%** | 이전 45–50% 실무 추정과 비교 가능; partial의 진척도는 0으로 취급 |

과학적 중요도 관점에서는 단일 백분율을 권하지 않는다. 가장 비싼 grid 계산은 끝났지만, 이 결과가 두 핵심 narrative를 바꾸며 official PFI와 survival increment 검증도 남아 있다. 따라서 “계산 진척은 높고 claim closure는 낮다”가 가장 정확한 요약이다.

## 4. 360-cell grid 설계와 실행 무결성

### 4.1 Frozen axes

근거: `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv`.

| 축 | 값 | cell 수 |
|---|---|---:|
| Marker | AR, Gleason, marker 7, phenotype, PTEN, SPOP | 각 60 |
| Encoder | CONCH, Virchow | 각 180 |
| Sampling seed | 0, 1, 2, 3, 4 | 각 72 |
| Tiles/slide | 16, 32, 64 | 각 120 |
| Scale | CONCH 0.88/1.76 mpp; Virchow 0.44/1.76 mpp | encoder별 각 scale 90 |
| 총 조합 | 6×2×5×3×2 | **360** |

Primary metric은 AR/Gleason이 patient Spearman rho, phenotype/PTEN/SPOP이 patient AUROC, marker 7이 patient C-index이다.

### 4.2 Runner별 reconciliation

| Raw directory | Cells | Folds | 판정 |
|---|---:|---:|---|
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/` | 90/90 | 450/450 | complete |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/` | 90/90 | 450/450 | complete |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/` | 60/60 | 300/300 | complete |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/` | 60/60 | 300/300 | complete |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_conch/` | 30/30 | 150/150 | complete |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_virchow/` | 30/30 | 150/150 | complete |
| **합계** | **360/360** | **1,800/1,800** | exact match |

검증 결과는 다음과 같다.

- 고유 `cell_id` 360; missing 0, unexpected 0, duplicate 0.
- 실제 result metadata의 marker/encoder/seed/tile/MPP가 frozen spec과 전부 일치.
- 모든 runner cell의 `status=complete`; non-finite patient metric 0.
- 고유 `(cell_id, fold)` 1,800; 모든 cell에 fold 0–4가 한 번씩 존재.
- `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv`는 고유 `(marker, case_id)` 1,167행이다. AR/PTEN/SPOP은 fold별 55/55/55/54/54=273, Gleason/phenotype은 8/8/8/8/7=39, marker 7은 각 fold 54=270이다.
- 모든 cell에서 fold-level `n_patients` 합과 cell-level `n_patients`가 같고 frozen assignment count와 일치한다.
- Frozen spec의 `status=pending` 360행은 설계 동결값으로 보존하고, 완료 ledger는 새 파생 파일에서 관리해야 한다.

### 4.3 Coordinate와 cohort QC

근거: 여섯 `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/*/coordinates_s*_mpp*.csv` 집합과 대응 `meta_*` 파일.

- 예상 coordinate shard 60개가 모두 있고 missing/unexpected shard는 0이다.
- 모든 slide의 tile rank는 정확히 0–63이며 중복 rank는 없다.
- TCGA AR/PTEN/SPOP: 모든 조건에서 300 slides, 273 patients.
- NADT 전체 sampling/phenotype frame: 모든 조건에서 463 slides, 39 patients.
- NADT Gleason evaluable subset: 모든 조건에서 **334 slides, 39 patients**. 따라서 “NADT 분석 cohort가 모두 463 slides”라는 표현은 phenotype에는 맞지만 Gleason outcome에는 부정확하다.
- Marker 7 target: 모든 조건에서 297 TCGA slides, 270 patients, 57 events.
- Marker 7 source LEOPARD: CONCH 498–500 patients, Virchow 499–502 patients. `<64` accepted tiles인 slide를 제외하는 runner 동작 때문에 source retention이 seed/scale 비교에 얽혀 있다.
- 20개 marker 7 source configuration의 공통 교집합은 원래 508명 중 498명(98.0%)이다. Scale/seed 효과를 순수하게 해석하기 전 common-498 sensitivity 또는 명시적 제한 보고가 필요하다.

### 4.4 Log와 TIFF QC

근거: `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs/*.log` 및 463개 NADT TIFF의 read-only page-header scan.

| 항목 | 관찰값 | 해석 |
|---|---:|---|
| Traceback | 0 | 기록된 run에서 fatal Python exception 없음 |
| `invalid page offset` log lines | 26 | CONCH 14, Virchow 12; resumed log이므로 lifetime 총계는 아님 |
| 영향 slide | 2/463 (0.432%) | 모두 patient 1004 |
| `FutureWarning` | 3 events, 6 lines | deprecated `timm.models.layers` import |
| 영향 slide의 retention | 20/20 NADT shards에서 각 64 coordinates | slide 제외나 tile-count 감소는 관찰되지 않음 |

영향 파일은 `1004.Prostate.Bx5A.slide.04.HE.tiff`와 `1004.Prostate.Bx7A.slide.04.HE.tiff`이다. 두 파일은 CONCH 0.88에서 level 2, CONCH 1.76에서 level 3, Virchow 0.44에서 level 1, Virchow 1.76에서 level 3의 유효 page를 사용한 것으로 확인되었다. 이는 terminal page pointer 문제로 추정되지만, 정식 QC에는 “run-level 영향 미관찰”로만 쓰고 “pixel-level 영향 없음”으로 단정하지 않는다.

## 5. Marker별 결과 안정성

### 5.1 집계 정의

- `chance-or-worse`: AUROC/C-index는 `≤0.5`, Spearman rho는 `≤0`.
- Seed direction reversal: marker×encoder×tile×scale을 고정한 다섯 seed의 최소값과 최대값이 metric null의 서로 다른 쪽에 있는 경우. Exact tie는 별도 집계한다.
- Native-vs-1.76 또는 encoder reversal: 나머지 축을 모두 맞춘 paired 두 결과가 null의 서로 다른 쪽에 있는 경우.
- 아래 SD, range와 seed range는 기술통계이다. Seed는 같은 cohort를 반복 sampling한 것이므로 독립 환자 표본이나 외부 replication이 아니다.

### 5.2 전체 60 cells/marker 요약

근거: 여섯 raw `cell_results.csv` 파일. 정식 통합 CSV 생성 전 감사 계산값이다.

| Marker / metric | Mean ± sample SD | Min–max | Chance-or-worse | Median / max five-seed range |
|---|---:|---:|---:|---:|
| AR rho | 0.2296 ± 0.0400 | 0.1364–0.2969 | 0/60 | 0.0813 / 0.1366 |
| Gleason rho | 0.4643 ± 0.0802 | 0.2708–0.6465 | 0/60 | 0.1327 / 0.2376 |
| Marker 7 C-index | 0.6572 ± 0.0733 | 0.4809–0.7547 | 1/60 | 0.0384 / 0.1134 |
| Phenotype AUROC | 0.9154 ± 0.0347 | 0.8449–0.9652 | 0/60 | 0.0749 / 0.0936 |
| PTEN AUROC | 0.6022 ± 0.0437 | 0.5192–0.7171 | 0/60 | 0.0658 / 0.1390 |
| SPOP AUROC | 0.5228 ± 0.0708 | 0.3477–0.6793 | 25/60 | 0.1470 / 0.2771 |

전체 chance-or-worse는 26/360=7.22%이다. 이 중 25개가 SPOP이며 나머지 하나는 `marker7__virchow__s2__t32__mpp0.44`의 C=0.480888이다. Exact-null cell은 없었다.

### 5.3 Encoder와 scale

각 값은 encoder×scale의 15 cells(5 seeds×3 tile budgets) 평균이다.

| Marker | CONCH native | CONCH 1.76 | Virchow native | Virchow 1.76 |
|---|---:|---:|---:|---:|
| AR rho | 0.2352 (0.88) | 0.2199 | 0.2573 (0.44) | 0.2061 |
| Gleason rho | 0.4831 (0.88) | 0.5370 | 0.4187 (0.44) | 0.4184 |
| Marker 7 C-index | 0.6944 (0.88) | 0.7360 | 0.5497 (0.44) | 0.6488 |
| Phenotype AUROC | 0.9073 (0.88) | 0.9159 | 0.9045 (0.44) | 0.9340 |
| PTEN AUROC | 0.5944 (0.88) | 0.6489 | 0.5928 (0.44) | 0.5728 |
| SPOP AUROC | 0.5413 (0.88) | 0.4837 | 0.5884 (0.44) | 0.4779 |

Matched `1.76 − native` 평균은 AR −0.0332, Gleason +0.0268, marker 7 +0.0703, phenotype +0.0191, PTEN +0.0173, SPOP −0.0840이다. Shared 1.76 mpp에서 `Virchow − CONCH` 평균은 각각 AR −0.0138, Gleason −0.1186, marker 7 −0.0871, phenotype +0.0182, PTEN −0.0761, SPOP −0.0058이다.

Null-crossing reversal은 native-vs-1.76 paired 20/180(19 SPOP, 1 marker 7), shared-1.76 encoder paired 4/90(모두 SPOP), fixed configuration의 five-seed range 9/72(8 SPOP, 1 marker 7)였다.

### 5.4 Tile budget

Matched `64 − 16` 평균은 모든 marker에서 양수였지만 개별 pair는 혼합되어 있다.

| Marker | CONCH `64−16` | Virchow `64−16` |
|---|---:|---:|
| AR | +0.0299 | +0.0413 |
| Gleason | +0.0637 | +0.0757 |
| Marker 7 | +0.0118 | +0.0064 |
| Phenotype | +0.0281 | +0.0201 |
| PTEN | +0.0232 | −0.0132 |
| SPOP | +0.0167 | +0.0104 |

이 차이는 128 tiles의 효과를 보장하지 않으며 독립적인 통계 검정도 아니다.

### 5.5 기존 결론에 미치는 영향

| Claim 영역 | 감사 결과 | 현재 판단 |
|---|---|---|
| Gleason/phenotype | 모든 120 cells가 positive/chance 초과; phenotype은 특히 강함. Gleason은 encoder·seed 변동이 더 큼 | 방향 재현은 강화하되 “모든 설정에서 동일한 크기”로 표현하지 않음 |
| PTEN | 60/60 cells가 AUROC>0.5이나 encoder×scale에 따라 평균 0.573–0.649 | association은 강화; held-out grade increment나 외부 검증을 새로 입증하지는 않음 |
| SPOP | AUROC 0.348–0.679, 25/60 chance 이하. Virchow 0.44 mpp seed 평균은 tiles 16/32/64에서 0.575/0.591/0.599이나 1.76 mpp는 약 0.476–0.481 | “robust null” 삭제. “frozen primary configuration에서 unsupported이며 강한 configuration sensitivity; modest effect를 배제하지 못함”으로 하향·재작성 |
| AR | 60/60 positive rho. 기존 site별 CI는 모두 0 포함 | pooled sign은 강화; “site-unstable” 대신 site transportability unresolved. Grade-independent increment 주장은 여전히 지지되지 않음 |
| Marker 7 | CONCH 0.694/0.736, Virchow 0.550/0.649(native/1.76 평균) | “Virchow transfer failure” 삭제. CONCH robust, Virchow weaker and scale-conditioned. Official PFI 전까지 exploratory 유지 |

SPOP의 native-scale Virchow 다섯-seed 평균에 대한 t interval이 tile별로 chance 위에 놓이는 조건이 있지만, 이는 patient-level uncertainty가 아니라 동일 cohort의 sampling-repeat interval이다. 정식 summary에서는 컬럼명을 `sampling_seed_t_ci_*`로 명시하고 임상적 CI로 해석하지 않는다.

## 6. P0 재현성·계보 감사

### 6.1 존재하며 구조적으로 확인된 산출물

- `paper/claim_evidence_matrix.csv`와 `.md`: 7행이 서로 일치.
- `paper/endpoint_hierarchy.csv`와 `.md`: 9행이 서로 일치.
- `cohort_manifest.csv`: 4,890행, 9 cache representations, full-row와 `(cohort, encoder, slide)` 중복 0. 기록된 9개 metadata path와 SHA가 현재 파일과 일치하고 embedding path/size도 일치.
- `environment.yml`과 `requirements-lock.txt`: 열두 direct package version이 서로 같고 `resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch`의 해당 version과 일치.
- `RUN_REPRODUCTION.md`: 개별 실행 command와 XeLaTeX command를 제공.

### 6.2 고쳐야 할 stale 또는 불완전 연결

- Claim C02/C03/C04는 grid pending 또는 ≥5-seed pending이라고 적혀 있어 현재 실행 상태와 다르다.
- C04의 robust null 해석과 C06의 Virchow failure 해석은 새 grid와 충돌한다.
- C05의 `source_csv`와 `source_script`가 서로 다른 분석을 가리켜 nested audit와 AR site forest의 두 CSV/script pair가 모두 필요하다.
- C02는 PANDA/Virchow, C03은 Virchow nested 결과, C06은 original C=0.673, E04/E05는 성능 CSV, E09는 LEOPARD source 연결이 불완전하다.
- `manuscript_location`은 repository-root-relative라고 하지만 `paper/` prefix가 빠져 있다.
- `cohort_manifest.csv`는 embedding size만 기록하고 SHA256은 없으며 full grid representations를 포함하지 않는다.
- `RUN_REPRODUCTION.md`는 conda environment를 activate한 뒤 모든 분석을 `resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python`으로 실행한다. 현재 workspace 표준 `.venv/bin/python`과도 다르므로 실행 환경 설명을 통일해야 한다.
- `requirements-lock.txt`는 12개 direct version 목록이지 transitive/platform/model-weight lock이 아니다.

### 6.3 Protocol snapshot lineage gap

`paper/protocol_provenance.json`은 2026-08-03 20:11의 retrospective snapshot이며 historical prespecification을 입증하지 않는다고 스스로 경고한다. Snapshot 후 세 runner가 22:35에 변경되었다.

| File | Snapshot SHA256 | Current SHA256 |
|---|---|---|
| `resources/projects/prostate_biomarker_validation/model_workspace/run_stability_tcga.py` | `f666dce7…c3b0` | `551bd99c…24c` |
| `resources/projects/prostate_biomarker_validation/model_workspace/run_stability_nadt.py` | `089f5ade…6117` | `b9751946…8a9` |
| `resources/projects/prostate_biomarker_validation/model_workspace/run_stability_marker7.py` | `1f74459e…72df` | `2920e230…616e` |
| `environment.yml` | `aac63030…67cb` | `f4de3639…84f8` |
| `requirements-lock.txt` | `fc323837…feda` | `f4c24a5b…1d9a` |

`RUN_REPRODUCTION.md`는 migration/resume 전에 96 cells가 존재했다고 기록하고 log는 그 cell을 skip하며 시작한다. Run-level code/config manifest가 없어 최초 96 cells와 이후 cells가 어떤 exact runner version으로 생성되었는지 보존 자료만으로 완전 증명할 수 없다. 이는 결과를 자동 무효화하는 증거는 아니지만, 최종 provenance에 **해결되지 않은 historical lineage limitation**으로 남겨야 한다.

현재 Git HEAD는 `447525c372454d4f04abb97267ec34f78eb33be1`이지만 paper와 다수 분석 artifact가 untracked이므로 historical freeze를 소급해 만들 수 없다.

## 7. P2–P4 상세 현황

### 7.1 AR

`resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv`의 pooled internal-CV rho는 0.1947 [0.0745, 0.3100]이다. Site별 값은 CH −0.1285 [−0.5614, 0.3504]부터 KK +0.2653 [−0.0867, 0.5578]까지이며 모든 site CI가 0을 포함한다. Site training set이 겹치는 leave-one-site-out estimate에 일반 random-effects meta-analysis를 적용하는 것은 독립성 가정을 충족하지 않는다.

AR/Gleason descriptor는 기존 metadata에서 파생 가능하다. 여섯 site의 median Gleason은 모두 7이고 AR SD는 5.36–8.81이다. SVS header에는 ScanScope ID가 280/300, AppMag=40이 300/300 존재하며 명시적 stain field는 없다. Scanner가 site와 거의 confounded이므로 scanner의 인과 효과를 주장할 수 없다.

### 7.2 SPOP

`resources/projects/prostate_biomarker_validation/model_workspace/spop_classweight_ablation_summary.csv`의 balanced patient AUROC는 0.5188 [0.4077, 0.6274], unweighted는 0.5163 [0.4073, 0.6262], 같은 근사의 80% power MDE는 0.6614이다. 같은 고정-score 근사로 감사 중 계산한 90% MDE는 약 0.6848이지만 정식 source CSV에 저장되지 않았으므로 P2 완료 근거로 보지 않는다.

Full grid가 ≥5 seeds, 두 encoders, 두 scales, 16/32/64 tiles 요구를 대체한다. 128 tiles와 tumor-enriched sampling은 대체하지 않는다. 기존 cache를 이용한 탐색적 read-only 확인에서는 tumor-top-16이 random보다 올라갈 가능성이 있어 tissue dilution을 배제할 수 없으므로, 강한 null claim을 유지하려면 tumor enrichment가 필요하다. 본 계획은 강한 null을 삭제하는 쪽을 권고한다.

### 7.3 Survival와 PCA

- `resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_delta.csv`: M5−M4, 같은 153 patients/30 events, ΔC=−0.002441, 95% CI [−0.011848, 0.006413].
- `resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv`: grade-only cohort에서 clinical 0.6451, image 0.6641, combined 0.7070; combined−clinical ΔC=+0.0619 [0.0080, 0.1189]. Fully adjusted complete-case cohort에서는 clinical 0.8389, image 0.6429, combined 0.8405; combined−clinical ΔC=+0.0016 [−0.0119, 0.0150].
- M0/M1은 n=270, M2는 n=165, M3–M5는 n=153이므로 M0→M3의 상승을 covariate 추가 효과로 직접 읽을 수 없다. 공통 cohort 비교가 필요하다.
- Same-patient/same-draw image−clinical ΔC와 모든 paired ΔIBS/Brier output은 없다. 현재 prediction CSV에는 OOF survival probability가 없어 ΔIBS는 model refit이 필요하다.
- PCA sweep은 CONCH k 4/8/16/32/64에서 C=0.613/0.661/0.633/0.635/0.598, Virchow에서 0.629/0.622/0.675/0.671/0.626이다. PCA는 각 outer training fold 안에서 fit되지만 k 자체는 전체 OOF sweep을 본 뒤 선택되므로 inner nested selection이 아니다. “stable across random seeds”를 뒷받침하는 inspectable CSV도 없다.

현재 sweep은 “여러 k에서 exploratory in-cohort signal이 관찰됨”이라는 sensitivity로는 충분하다. 특정 k의 unbiased selected performance나 강한 재현성 claim을 유지하려면 inner nested selection이 필요하다.

### 7.4 Official TCGA-CDR PFI

Local clinical JSON에는 cBioPortal `PFS_*`와 `DFS_*`만 있고 official PFI/DFI field 또는 mapping은 없다. 현재 저장 결과는 PFS n=270/42 events, C=0.5862; DFS n=192/11, C=0.6052; strict recurrence n=220/7, C=0.6551이다. 이들을 official PFI로 바꾸어 부를 수 없다. E08은 `not_done` 상태를 유지해야 한다.

## 8. P5 figure/table lineage와 P6 QA

### 8.1 Figure/table lineage

- `paper/figure_manifest.csv`가 없다.
- 활성 Figure 10개 중 Figure 3은 14개 metric을, Figure 7 panel B는 6개 C-index와 표본수/interval을 hard-code한다.
- Figure 2 panel B와 Figure 1 reliability map에도 수동 수치가 있다.
- Figure 4는 저장된 figure-source CSV가 아니라 NPY/meta/JSON에서 즉시 재계산한다.
- Figure 8은 same-name generator가 없고 다른 filename의 PDF와 byte-identical하다.
- Figure 9는 완료된 360-cell grid가 아니라 `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_scale_tile_sensitivity_summary.csv`의 90-slide single-seed 구 grid를 사용한다.
- 여섯 inline result table은 TeX에 수치가 직접 입력되어 있고 result-table generator가 없다.
- 활성 figure script 네 개를 포함한 다섯 figure script에 absolute project root가 있다.
- 모든 table/figure/PDF를 검증·재생성하는 단일 entry command가 없다.

### 8.2 PDF와 최종 QA

`paper/main.pdf`의 mtime은 2026-08-03 17:29:12이고 마지막 grid result는 2026-08-06 03:53:19이다. PDF가 약 58시간 24분 먼저 생성되었으므로 새 grid를 포함할 수 없다. `paper/main.log` 한 개만으로 XeLaTeX 연속 2회 실행을 증명할 수도 없다. 최종 compliance, numeric-consistency, reproducibility report는 발견되지 않았다.

## 9. 주요 파일 hash inventory

### 9.1 Frozen grid와 runner 결과

| Path | Bytes | SHA256 |
|---|---:|---|
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv` | 50,706 | `9399e711080006cc851041a357030c27e5de3bea116983a837f7182f8098855d` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv` | 38,281 | `18a307ad2f9482d876b4237ce37a52163f7917be1e18d9f6f163eb33e4a62f97` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/cell_results.csv` | 9,548 | `aff9acd92b25b80e89d07460c47a41e891030c8db29154bc46074af6b154e8ec` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/fold_results.csv` | 33,158 | `77549a385f3c1b54d0b48d1f20745decdf25b38604cc9764a2ff204a45f85fca` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/cell_results.csv` | 9,907 | `5e03c7191e11c4776c2d975fb902c9ee15a73f020ce37bb0d9b798961de43f0d` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/fold_results.csv` | 34,865 | `69c9378b4af46304342202d90082d81c45b28f17096bffc599f2e5b393cab1ac` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/cell_results.csv` | 6,898 | `7dfb1c7462a4d5fb528fbd8e55410b1d56833ad8e137a48bcb168dffaa2cd925` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/fold_results.csv` | 23,354 | `342c2130f027f430f17f73ceff5c43f71caab7df82344bbd4d119a1d57b655d6` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/cell_results.csv` | 7,112 | `4cfac56df16c5a41a7816242d223eb24e9eff994bebf1d65d45bffd85f8f1016` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/fold_results.csv` | 24,498 | `d70c4b34b66711ee51522054c170fe7ff237e26780f1a577f2cef532ae2fc84f` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_conch/cell_results.csv` | 3,002 | `ae80241c199bb1265a18bab08b4f1e91474bf1e73ad59d4dc05cfe48512555c3` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_conch/fold_results.csv` | 12,222 | `998759837d3d8121521de802720d5fe2232a41b7d6bee908bf14be9873a050e7` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_virchow/cell_results.csv` | 3,123 | `d276262413ca96f679bc44473412dbc5d8e24152fe94e42c9dfc588ab4844e71` |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_virchow/fold_results.csv` | 12,792 | `2ee135e127e12b1fddc9a30ff112db7dc3b46ced4ccb7901a57c0a2e57dbe2e5` |

### 9.2 기준 문서와 재현성 입력

| Path | SHA256 |
|---|---|
| `paper/MajorRevision-v1.md` | `9f94795bd86918fc80e474899af954ea4eda1844abf8c331d67d1c18d3f3643e` |
| `paper/MajorRevision-v1-completion-plan.md` | `4a92b46acee94efe675e2be1e911445f20e8309ff8cacb8508d640f830f09f7a` |
| `paper/claim_evidence_matrix.csv` | `64aab4dd20d2114e8151b1dc7c79465ba836300a413f979a7d0fcc36b0fd4813` |
| `paper/endpoint_hierarchy.csv` | `05852b36189cec1daebf247521190f5737834d29cd26336f8b7bf51cefea60b1` |
| `paper/protocol_provenance.json` | `2c74e4eea1ad5ab695799ace8bde9bf6292636a42d471e2bf2f4535e00a40598` |
| `cohort_manifest.csv` | `5a0cc0956337308ab96034670d6acd5cd2c585a21b8316e5328371db153c9042` |
| `RUN_REPRODUCTION.md` | `c74a2e6b4f558de7f3f1b1d3047cb99993f7d0b2ae3331817728ee2486477fde` |
| `environment.yml` | `f4de36393fc1e556958ed09c6f5b524a8e462bd06fe0e15c48b9972182c884f8` |
| `requirements-lock.txt` | `f4c24a5b07f0bdf8c5b6db8b3866f9e9d9a3e15badaf7a6a3edf2b41751d1d9a` |

## 10. 미해결 과학적·통계적 위험

1. **설정 탐색과 추론의 혼동:** 360 cells는 correlated sensitivity grid이며 360개의 독립 검증이나 확증 검정이 아니다.
2. **Seed CI 오해:** 다섯 sampling seed의 t interval은 sampling repeat variability이며 patient/population uncertainty가 아니다.
3. **Marker 7 source retention:** seed/scale별 498–502명 차이가 configuration contrast와 얽힌다.
4. **SPOP narrative:** robust null과 clean failure는 새 grid가 지지하지 않는다. Tumor dilution과 modest effect는 배제되지 않는다.
5. **AR site 해석:** pooled positive와 site transportability 미해결을 구분해야 한다. 겹치는 LOO training set의 random-effects summary는 부적절할 수 있다.
6. **Survival paired estimand:** 서로 다른 n의 M0–M5 staircase를 covariate increment로 해석할 수 없고 paired ΔIBS가 없다.
7. **PCA selection:** k를 전체 OOF sweep 후 선택하면 selected performance에 optimism이 있다.
8. **Endpoint 정확성:** PFS/DFS/reconstructed recurrence는 official PFI가 아니다. 현재 event 수가 적고 censoring/observation-time 영향도 남는다.
9. **Historical code lineage:** 최초 96 grid cell의 exact runner version을 retained manifest로 증명할 수 없다.
10. **Numeric lineage:** hard-coded figure/table 수치와 최신 CSV의 기계적 동일성이 보장되지 않는다.

## 11. 현재 원고에 아직 반영되지 않은 결과

- 360-cell 전체 grid와 72개 fixed-configuration seed summary
- SPOP의 scale-conditioned chance crossing
- Marker 7 Virchow의 1.76 mpp recovery
- NADT Gleason 334-slide evaluable subset과 TIFF QC
- Marker 7 source retention 498–502와 common-498 intersection
- 완료된 grid에 따른 C02–C06 claim 상태 변경
- Paired survival gap, exact PFI gap, provenance mismatch와 최초 96-cell lineage limitation

현재 `paper/main.pdf`와 Figure 9를 근거로 이 결과가 반영되었다고 보고해서는 안 된다.

## 12. 결론

360-cell 본계산은 무결하게 종료되었지만 결과 통합과 원고 claim closure는 끝나지 않았다. 즉시 필요한 다음 단계는 새 GPU 실행이 아니라 (1) raw grid의 fail-closed 통합/QC, (2) 바뀐 SPOP·marker 7·AR 해석의 claim 반영, (3) exact PFI와 paired survival 비교 같은 최소 필수 gap, (4) CSV-driven figure/table lineage와 최종 재현성 QA이다. 구체적인 산출물, 중단 조건, 승인 gate는 `paper/MajorRevision-v1-remaining-experiments-and-revision-plan.md`에 정의한다.
