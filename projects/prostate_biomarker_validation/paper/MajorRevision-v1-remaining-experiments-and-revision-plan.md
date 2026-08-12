# MajorRevision-v1 잔여 실험·결과 통합·원고 개정 계획

- 작성 기준일: 2026-08-06 (US/Eastern)
- 선행 감사: `paper/MajorRevision-v1-experiment-status-2026-08-06.md`
- 기본 전략: 이미 끝난 360-cell 계산을 다시 하지 않고, claim을 닫는 최소 충분 분석과 결과 계보를 먼저 완성한다.
- 실행 상태: **계획만 작성됨. 이 문서에 적힌 구현·분석·외부 데이터 획득·GPU 작업은 아직 시작하지 않았다.**

## 1. 결정 요약

1. 360-cell grid는 재실행하지 않는다. 먼저 raw 결과를 하나의 fail-closed CPU entry point로 통합하고 QC/manifest/figure-source를 만든다.
2. SPOP “재현 가능한 null” claim은 유지하지 않는다. “frozen primary configuration에서 unsupported, scale/tile/sampling에 민감하며 modest effect를 배제하지 못함”으로 재작성한다.
3. Marker 7 “Virchow transfer failure”는 “CONCH에서 강하고 Virchow에서 약하지만 1.76 mpp에서 회복되는 encoder×scale-conditioned exploratory transfer”로 재작성한다.
4. AR “site-unstable”은 “pooled association은 재현되나 site transportability와 scanner/site 분리는 미해결”로 재작성한다. 겹치는 LOO training set에 대한 random-effects pooling은 수행하지 않는 것을 기본값으로 한다.
5. Official TCGA-CDR PFI는 MR-v1 endpoint 요구를 정확히 닫기 위해 필수이다. 로컬 source가 없으므로 별도 사용자 승인 후 공식 파일만 획득하며 PFS/DFS/reconstructed recurrence를 PFI로 재명명하지 않는다.
6. Same-patient/same-bootstrap-draw ΔC와 ΔIBS, 그리고 공통 complete-case cohort의 임상 모델 비교는 marker 7 incremental claim을 위해 필수이다.
7. Nested PCA는 **현재 sweep을 exploratory sensitivity로 제한하고 특정 k의 unbiased 성능·seed 안정성 문구를 삭제한다면 필수가 아니다.** 그 강한 문구를 유지하려는 경우에만 conditional-required이다.
8. Multiple imputation은 권장 sensitivity이다. 수행하지 않으면 n=153 complete-case 결론으로 명시적으로 제한한다.
9. SPOP tumor-enriched sampling은 biology 해석을 강화할 수 있어 권장한다. 128 tiles는 16–64 범위로 제한 보고할 수 있으므로 선택이다. 두 항목 모두 새 GPU 승인을 받은 뒤에만 실행한다.
10. 원고 수정은 integrated grid와 필수 CPU 분석이 동결된 뒤 시작한다. Figure/table을 저장 CSV에서 생성하고 마지막에 numeric/reproducibility QA와 XeLaTeX 2회를 수행한다.

## 2. 비협상 경계와 중단 원칙

- `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv`, 여섯 runner 결과와 60 coordinate shards를 raw/frozen input으로 취급하고 수정하지 않는다.
- Frozen spec의 360개 `pending` status를 덮어쓰지 않는다. 새 reconciliation status를 파생 output에 저장한다.
- Raw input의 pre/post SHA256가 다르면 즉시 중단한다.
- Missing, invalid, undefined bootstrap replicate를 success/negative로 바꾸거나 삭제하지 않는다. undefined count와 fraction을 저장한다.
- 다섯 sampling seed를 독립 환자 표본, external replication 또는 patient-level uncertainty로 해석하지 않는다.
- Marker 7 source cohort가 조건마다 498–502명인 상태에서 scale/seed 차이를 source-constant 효과라고 단정하지 않는다.
- 공식 PFI source가 없거나 case mapping이 ambiguous하면 endpoint를 재구성하지 않고 `blocked/not_done`으로 보고한다.
- 모든 그림과 result table은 저장된 CSV source에서만 생성한다.
- 새 GPU/장시간 실험은 사용자 승인 전 시작하지 않는다.
- 생성 분석 output은 local artifact이며 broad staging/commit/push를 하지 않는다.

## 3. 360-cell 결과 통합 설계

### 3.1 단일 auditable entry point

승인 후 다음 파일을 구현한다.

- Entry script: `resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py`
- Tests: `tests/test_aggregate_stability_grid.py`
- 실행 예:

```bash
.venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py \
  --spec resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv \
  --fold-assignments resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv \
  --run-root resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full \
  --log-root resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs
```

Script는 raw file을 in-place 수정하지 않고 모든 preflight 검증이 성공한 뒤 임시 directory에 출력하고, 최종 schema/count/hash 검증 후에만 atomic rename한다. 실패하면 기존 파생 output도 덮어쓰지 않는다.

### 3.2 입력

| 종류 | 입력 |
|---|---|
| Frozen design | `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv` |
| Frozen folds | `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv` |
| Cell results | `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/{conch,virchow,nadt_conch,nadt_virchow,marker7_conch,marker7_virchow}/cell_results.csv` |
| Fold results | 같은 여섯 directory의 `fold_results.csv` |
| Coordinates | 같은 여섯 directory의 `coordinates_s*_mpp*.csv` 60개 |
| Metadata | `meta_*`, marker 7의 `source_meta_*`와 `target_meta_*` |
| Logs | `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs/*.log` 여섯 개 |
| Code/environment provenance | 세 runner, grid builder, `RUN_REPRODUCTION.md`, `environment.yml`, `requirements-lock.txt`, Python/package versions |

대용량 coordinate를 하나의 거대 CSV로 복제하지 않는다. 60개 raw shard를 canonical source로 유지하고 shard-level manifest만 만든다.

### 3.3 출력 계약

| 출력 | 예상 크기/행 | 역할 |
|---|---:|---|
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv` | 360 | spec semantics를 붙인 canonical cell 결과; raw path/hash 포함 |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv` | 1,800 | canonical fold 결과; fold assignment reconciliation 포함 |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv` | 72 | marker×encoder×tiles×scale별 5-seed 요약 |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv` | 명시적 paired contrasts | native-vs-1.76, CONCH-vs-Virchow@1.76, 64-vs-16 기술 비교 |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv` | 60 | shard path/hash/rows/slides/patients/levels/rank 범위와 QC |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_run_manifest.csv` | input/output별 1행 | size, mtime, SHA256, role, runner/version, pre/post 상태 |
| `resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json` | 1 | 모든 assertion, warning 분류, TIFF 영향 slide, lineage limitation |
| `paper/figure_data/fig9_stability_grid.csv` | figure가 읽을 tidy rows | 전체 grid heatmap/interval panel의 유일한 수치 source |
| `paper/figure_data/fig9_stability_contrasts.csv` | figure가 읽을 paired rows | scale/encoder/tile contrast panel의 유일한 수치 source |

`stability_summary.csv`의 최소 필드는 `marker`, `metric`, `chance_value`, `encoder`, `tiles_per_slide`, `target_mpp`, `n_seeds`, `mean`, `sample_sd`, `sampling_seed_t_ci_low`, `sampling_seed_t_ci_high`, `min`, `max`, `n_chance_or_worse`, `chance_or_worse_rate`, `seed_null_straddle`, `n_ties`이다. `sampling_seed_t_ci_*`는 df=4의 Student-t interval이며 **patient-level CI가 아님**을 schema/data dictionary와 caption에 반복 명시한다.

Contrast output은 paired key와 두 raw cell IDs를 보존하고 다음을 분리한다.

- 같은 marker/encoder/seed/tile의 `1.76 − native`
- 같은 marker/seed/tile/1.76 mpp의 `Virchow − CONCH`
- 같은 marker/encoder/seed/scale의 `64 − 16`
- 각 pair의 null crossing, exact tie, metric direction
- fixed marker/encoder/tile/scale에서 five-seed `min < null < max` 여부

이 contrast에는 seed를 독립 replicate로 가정한 p-value를 만들지 않는다.

### 3.4 Fail-closed 검증 조건

출력 전에 아래를 모두 assertion으로 검사한다.

1. Spec 360행/360 IDs; actual 360 unique IDs; exact set equality; actual status 모두 `complete`.
2. Spec metadata와 actual marker/encoder/seed/tile/MPP의 exact equality.
3. Fold 1,800 unique `(cell_id, fold)`; 각 cell에 정확히 0–4; finite metric.
4. Fold별 patient count가 frozen assignments 및 cell total과 일치.
5. Coordinate shard가 정확히 60개이며 expected seed/MPP naming set과 일치.
6. 각 coordinate row의 field width와 seed/MPP/encoder provenance 일치; slide별 rank가 정확히 0–63.
7. TCGA는 모든 조건에서 300 slides/273 patients, phenotype frame은 463/39, Gleason evaluable subset은 334/39, marker 7 target은 297/270/57.
8. Marker 7 source retention 498–502와 common intersection 498을 계산·기록하고 source-constant라고 잘못 표시하지 않음.
9. 모든 primary metric finite; blank/NaN/inf가 있으면 fail.
10. Log의 traceback/error/warning을 별도 count하고 resumed-log limitation을 기록.
11. 두 NADT TIFF warning slide의 20/20-shard retention과 사용 pyramid level을 기록하되 pixel-level no-impact claim은 금지.
12. Raw input pre/post SHA256 exact equality.
13. Output의 행 수, key uniqueness, schema, non-self-referential hashes 검증.
14. Clean rerun에서 CSV/JSON byte content가 같음. `generated_at`처럼 허용된 volatile timestamp는 별도 manifest field로 격리하고 차이를 문서화.

### 3.5 테스트 설계

`tests/test_aggregate_stability_grid.py`에는 최소한 다음을 포함한다.

- 작은 synthetic fixture의 정상 통합과 deterministic output
- missing/duplicate/unexpected cell 실패
- spec/actual metadata mismatch 실패
- fold 4개 또는 6개, patient-count mismatch 실패
- non-finite metric 실패
- coordinate shard 누락, duplicate rank, rank 63 누락 실패
- marker 7 source-retention variation의 warning과 common intersection 계산
- chance threshold와 세 종류 reversal의 경계값/tie test
- seed t interval naming/계산 test
- manifest가 자기 자신의 hash를 포함하지 않는지 검사
- real data가 존재할 때 360/1,800/60 exact integration guard

## 4. 잔여 작업 우선순위

### 4.1 우선순위 요약

| ID | 우선순위 | 작업 | 새 GPU | 권고 결정 |
|---|---|---|---:|---|
| R1 | 필수 | 360-cell 통합·manifest·QC | 아니오 | 가장 먼저 수행 |
| R2 | 필수 | Marker 7 common-498 source sensitivity | 아니오 | scale claim 전 수행 |
| R3 | 필수 | Official TCGA-CDR PFI mapping/concordance/performance | 아니오, 외부 공식 파일 필요 | 사용자 승인 후 공식 source 획득 |
| R4 | 필수 | Same-draw paired ΔC/ΔIBS와 common-cohort survival 비교 | 아니오 | incremental claim 전 수행 |
| R5 | 필수 | AR descriptor/metadata와 SPOP site/power source table | 아니오 | 저비용 claim closure |
| R6 | 필수 | CSV-driven figure/table lineage와 P0 문서 갱신 | 아니오 | 분석 freeze 후 수행 |
| R7 | 필수 | Numeric/compliance/reproducibility QA와 PDF rebuild | 아니오 | 마지막 수행 |
| A1 | 권장 | SPOP tumor-enriched sampling | **예** | null biology를 논의하려면 수행 |
| A2 | 권장 | Fold-contained multiple imputation sensitivity | 아니오 | complete-case 선택 영향 평가 |
| A3 | 권장/조건부 필수 | Inner-nested PCA k selection | 아니오 | 강한 selected-k claim을 유지할 때만 필수 |
| O1 | 선택 | SPOP 128 tiles targeted run | **예** | 16–64 제한 보고로 생략 가능 |
| O2 | 선택/비권장 | AR random-effects summary | 아니오 | overlapping LOO 때문에 기본적으로 생략 |
| O3 | 선택/비권장 | 전체 marker 128-tile grid 또는 기존 grid 재실행 | **예** | 결론 변화 가능성 대비 비용이 낮지 않아 생략 |

시간은 현재 파일 크기와 기존 run을 바탕으로 한 planning estimate이다. 첫 실행 benchmark가 상한의 2배를 넘거나 memory/disk constraint가 생기면 중단하고 재추정한다.

## 5. 필수 작업 cards

### R1. 360-cell 통합·manifest·QC

| 필드 | 계획 |
|---|---|
| 연구 질문 | Frozen grid가 완전하며 marker/encoder/seed/tile/scale별 안정성 요약을 raw lineage와 함께 재현할 수 있는가? |
| 필요한 이유 | 360/360 계산 완료만으로 P1 deliverable과 원고 수치 계보가 닫히지 않음 |
| 재사용 결과 | Spec, fold assignments, 여섯 cell/fold CSV, 60 coordinate shards, logs 전체 |
| 추가 계산 범위 | CSV 통합, 기술통계, paired contrasts, hash/QC; 모델 재학습·embedding 재추출 없음 |
| 입력 데이터 | 3.2절의 frozen/raw inputs |
| 예상 산출물 | 3.3절의 9개 output와 test |
| CPU/GPU | CPU only; GPU 0 |
| 예상 시간 | 5–15분, full deterministic rerun 포함 30분 이내 |
| 중단 조건 | ID/count/schema/hash/cohort/fold/coordinate assertion 하나라도 실패; raw pre/post hash 변화 |
| 성공 기준 | 360/1,800/60 exact reconciliation, 모든 test 통과, 두 clean run의 deterministic field 동일 |
| 실패 시 원고 처리 | Grid를 통합 결과로 인용하지 않고 raw compute complete/aggregation blocked로 유지; mismatch를 보고 |
| 변경 위치 | Figure 9와 supplement의 stability 표, `claim_evidence_matrix`, `protocol_provenance`, `RUN_REPRODUCTION.md` |

### R2. Marker 7 common-498 sensitivity

| 필드 | 계획 |
|---|---|
| 연구 질문 | Marker 7의 scale/encoder 차이가 20개 source configuration에 공통인 498 patients에서도 유지되는가? |
| 필요한 이유 | 현재 source가 498–502명으로 달라 seed/scale 효과와 cohort retention이 얽힘 |
| 재사용 결과 | `source_meta_*`, 저장 embeddings, frozen target, current fold/spec와 common intersection |
| 추가 계산 범위 | Common-498 source만 사용해 frozen model/PCA/hyperparameter와 같은 target scoring을 CPU refit; target 270/57 고정 |
| 입력 데이터 | `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_{conch,virchow}/source_meta_*`, source/target embeddings, fold assignments |
| 예상 산출물 | `resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv`, paired delta table, run manifest, source-membership manifest |
| CPU/GPU | CPU only; 기존 embeddings 재사용 |
| 예상 시간 | 15–60분 |
| 중단 조건 | Common set이 498이 아니거나 source/target ID·embedding alignment 불일치; frozen training spec 재현 불가 |
| 성공 기준 | 60 marker-7 cells 전부 동일 498 source와 동일 270 target에서 완료; raw result와 방향 비교 가능 |
| 실패 시 원고 처리 | Scale/seed contrast를 source-retention-confounded sensitivity로만 보고하고 인과적 configuration 해석을 제한 |
| 변경 위치 | `downstream_recurrence_transfer.tex`, Figure 7/9, supplement source-retention table |

### R3. Official TCGA-CDR PFI

| 필드 | 계획 |
|---|---|
| 연구 질문 | 공식 TCGA-CDR PFI 정의에서 marker 7 risk의 방향·성능과 현재 reconstructed/PFS/DFS 결과의 일치 정도는 무엇인가? |
| 필요한 이유 | E08과 MR-v1 endpoint 요구를 정확히 닫는 유일한 방법이며 현재 PFS/DFS는 대체물이 아님 |
| 재사용 결과 | Frozen TCGA marker-7 predictions/risk, PFS/DFS/strict/reconstructed mappings와 benchmark code |
| 추가 계산 범위 | 공식 Liu et al. TCGA-CDR supplementary source 획득, immutable archive/hash/provenance, barcode mapping, patient-level concordance/reason codes, 같은 model spec의 PFI metrics |
| 입력 데이터 | 사용자 승인 후 공식 publisher/NCI 배포 TCGA-CDR Table S1의 PFI event/time fields; local risk predictions |
| 예상 산출물 | `resources/data/shared/opendataset/TCGA-CDR/`의 immutable source+hash/provenance(local, commit 금지), `resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv`, predictions/manifest |
| CPU/GPU | CPU only; 외부 공식 파일 접근 필요 |
| 예상 시간 | Source 확보 후 1–3시간 |
| 중단 조건 | 비공식/변형 source만 발견, field 정의 불명, duplicate/ambiguous barcode, time unit 불일치, source hash/provenance 기록 불가 |
| 성공 기준 | 모든 분석 환자의 one-to-one mapping 상태와 제외 이유 저장; official PFI를 독립 endpoint로 성능·uncertainty와 함께 보고 |
| 실패 시 원고 처리 | E08 `not_done`; current 결과를 “cBioPortal PFS/DFS endpoint sensitivities”로만 부르고 reviewer의 official PFI 요구 미충족을 limitation에 명시 |
| 변경 위치 | `endpoint_hierarchy`, `downstream_recurrence_transfer.tex`, limitations, endpoint concordance table/supplement |

### R4. Paired survival deltas와 common-cohort 비교

| 필드 | 계획 |
|---|---|
| 연구 질문 | 같은 held-out patients와 같은 bootstrap draws에서 image-only, clinical-only, combined, M4/M5의 ΔC와 ΔIBS가 무엇인가? |
| 필요한 이유 | 현재 M0–M5의 n이 270→165→153으로 바뀌고 paired ΔIBS/image−clinical 결과가 없어 incremental claim을 직접 지지하지 못함 |
| 재사용 결과 | `marker7_clinical_hierarchy_*`, `confounder_nested_*`, frozen folds/covariates/risk scores |
| 추가 계산 범위 | 공통 n=153에서 모든 model refit/OOF prediction; 동일 patient resample indices로 ≥2,000 bootstrap draws; C-index와 time-dependent survival probability 기반 IBS/Brier |
| 입력 데이터 | TCGA clinical covariates/outcomes, marker-7 risk, existing patient folds; endpoint는 reconstructed와 official PFI를 분리 |
| 예상 산출물 | `resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_common_cohort_summary.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_bootstrap_replicates.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_oof_survival_predictions.csv`, run manifest |
| CPU/GPU | CPU only |
| 예상 시간 | 30–120분; official PFI branch는 R3 이후 |
| 중단 조건 | 모델 간 patient/draw mismatch, survival probability 미정의, fold leakage, event<분석 사양 최소치, undefined replicate가 사전 허용 기준을 초과 |
| 성공 기준 | 모든 contrast가 같은 patient와 draw ID로 paired; point/CI, undefined count/fraction 저장; M4/M5와 pool 비교의 estimand 명확 |
| 실패 시 원고 처리 | Incremental claim 삭제 또는 C-index point estimate만 exploratory로 제한; IBS/calibration 비교를 수행했다고 쓰지 않음 |
| 변경 위치 | `downstream_recurrence_transfer.tex`, Figure 7/8, clinical hierarchy table, supplement bootstrap table |

### R5. AR/SPOP 저비용 evidence closure

| 필드 | 계획 |
|---|---|
| 연구 질문 | AR site transportability를 설명할 분포/metadata가 있는가, SPOP의 site uncertainty와 detectable effect 범위는 무엇인가? |
| 필요한 이유 | C04/C05의 현재 문구와 source linkage가 불완전하며 reviewer가 descriptor/power를 요구 |
| 재사용 결과 | `ar_site_forest_summary.csv`, TCGA meta/clinical JSON/SVS headers, `spop_classweight_ablation_summary.csv`, 기존 site predictions |
| 추가 계산 범위 | Site별 n, AR/Gleason quantiles, scanner/stain availability; SPOP site n/positives/patient AUROC/bootstrap CI; 80/90% MDE를 동일 근사로 저장 |
| 입력 데이터 | `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/meta.csv`, clinical JSON, SVS headers, 기존 SPOP OOF predictions |
| 예상 산출물 | `resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv`와 provenance |
| CPU/GPU | CPU only |
| 예상 시간 | 15–45분 |
| 중단 조건 | Site/patient mapping 불일치, metadata field 의미 불명, prediction lineage 불명; missing stain은 추정하지 않고 `not_available` |
| 성공 기준 | 모든 site의 denominator/missingness/CI가 저장되고 scanner-site confounding 및 MDE 근사 한계가 명시됨 |
| 실패 시 원고 처리 | Site 원인 해석 제거; “metadata unavailable/transportability unresolved”로 제한; SPOP effect exclusion 문구 삭제 |
| 변경 위치 | `confounder_site_audits.tex`, `failure_modes.tex`, Figure 6, supplement site/power tables |

### R6. P0·figure/table lineage 갱신

| 필드 | 계획 |
|---|---|
| 연구 질문 | 원고의 모든 수치가 저장 CSV와 generator로 추적되고 한 명령으로 재생성되는가? |
| 필요한 이유 | Figure 9가 stale이고 여러 figure/6개 table이 hard-coded이며 manifest가 없음 |
| 재사용 결과 | 기존 figure scripts/PDF, analysis CSV, claim/endpoint builder, integrated outputs |
| 추가 계산 범위 | `resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py`를 먼저 수정; figure-source CSV와 table renderer; absolute path 제거; same-name Figure 8 generator; paper build entry point |
| 입력 데이터 | Freeze된 R1–R5 결과 CSV와 기존 figure sources |
| 예상 산출물 | `paper/figure_manifest.csv`, `paper/table_manifest.csv`, `paper/figure_data/*.csv`, generated TeX table fragments, one-command build/validation script |
| CPU/GPU | CPU only |
| 예상 시간 | 0.5–2일 구현·검토 |
| 중단 조건 | 수치 source 불명, PDF가 source보다 오래됨, generator가 in-memory result를 저장 없이 plot, absolute/scratch dependency |
| 성공 기준 | 활성 figure/table 100% source+script+hash+manuscript location 연결; hard-coded result 0; repository-relative path; clean regeneration 성공 |
| 실패 시 원고 처리 | 계보가 없는 figure/table을 삭제하거나 숫자 없는 schematic으로 제한; compliance에서 partial로 표시 |
| 변경 위치 | 모든 figure/table, claim/endpoint/provenance/cohort manifest, `RUN_REPRODUCTION.md` |

### R7. Final numeric/compliance/reproducibility QA

| 필드 | 계획 |
|---|---|
| 연구 질문 | 제출 PDF의 모든 claim·수치·asset이 frozen source와 일치하고 clean rerun 가능한가? |
| 필요한 이유 | 현재 PDF가 grid 이전이고 QA report가 없음 |
| 재사용 결과 | R1–R6 outputs, tests, manifests, manuscript source |
| 추가 계산 범위 | Numeric equality, stale timestamp, path/secret scan, source hash, clean rerun, two-pass XeLaTeX, unresolved ref/citation check |
| 입력 데이터 | 전체 final derived outputs와 manuscript |
| 예상 산출물 | `paper/MajorRevision-v1-compliance-report.md`, numeric consistency report, reproducibility report, latest `main.pdf`와 build logs/hash manifest |
| CPU/GPU | CPU only |
| 예상 시간 | 1–3시간 + 발견된 오류 수정 시간 |
| 중단 조건 | Any numeric mismatch, unresolved reference/citation, immutable hash mismatch, non-deterministic undeclared output, stale asset, test failure |
| 성공 기준 | Section 10의 모든 gate 통과; failure/undefined count 보존; fresh PDF가 모든 source보다 새로움 |
| 실패 시 원고 처리 | 제출본 생성/완료 선언 금지; 해당 package를 partial/not_done으로 되돌리고 discrepancy report 유지 |
| 변경 위치 | 전체 manuscript와 submission package |

## 6. 권장 분석 cards

### A1. SPOP tumor-enriched sampling

| 필드 | 계획 |
|---|---|
| 연구 질문 | Random tissue sampling이 SPOP의 modest morphology signal을 희석하는가? |
| 필요한 이유 | Grid의 scale sensitivity와 탐색적 tumor-top result 때문에 dilution을 배제할 수 없음 |
| 재사용 결과 | Frozen SPOP folds, CONCH/Virchow cache, random 16/32/64 grid 결과 |
| 추가 계산 범위 | 사전 정의 tumor score로 top tiles 선택, 최소 5 seeds, 가능하면 두 encoders와 matched scales; random과 same-fold paired 비교 |
| 입력 데이터 | 기존 embeddings와 tumor ranking/segmentation output; 새 ranking이 필요하면 별도 provenance |
| 예상 산출물 | `resources/projects/prostate_biomarker_validation/model_workspace/spop_tumor_enriched_summary.csv`, fold/cell/contrast/manifest, figure-source CSV |
| CPU/GPU | 기존 tile embeddings와 tumor ranks가 완전하면 CPU; 새 tile inference가 필요하면 GPU |
| 예상 시간 | CPU 1–3시간 또는 GPU 4–12 GPU-hours의 조건부 추정 |
| 중단 조건 | Tumor rank coverage 불완전, label leakage, source 기준이 condition마다 달라짐, pilot에서 target tile retention 부족 |
| 성공 기준 | Random-vs-enriched를 same patients/folds/seeds에서 비교하고 uncertainty와 failure count 저장 |
| 실패 시 원고 처리 | SPOP을 random-tissue frozen design에 한정하고 tumor dilution을 미해결 limitation으로 보고 |
| 변경 위치 | `failure_modes.tex`, SPOP supplement/figure |

### A2. Fold-contained multiple imputation

| 필드 | 계획 |
|---|---|
| 연구 질문 | PSA 38.1%, margin 19.6% missingness로 생긴 n=153 complete-case selection이 clinical increment 결론을 바꾸는가? |
| 필요한 이유 | Complete-case cohort가 전체 270명과 다를 수 있음 |
| 재사용 결과 | R4 model/folds/paired bootstrap, observed covariates |
| 추가 계산 범위 | 각 outer-training fold 안에서만 imputer fit; test fold transform; imputation uncertainty를 fold/bootstrap과 일관되게 처리 |
| 입력 데이터 | TCGA clinical covariates, outcomes, marker risk, frozen folds |
| 예상 산출물 | `resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_mi_summary.csv`, paired deltas, missingness/imputation diagnostics, manifest |
| CPU/GPU | CPU only |
| 예상 시간 | 1–4시간 |
| 중단 조건 | Leakage-free implementation 불가, convergence/implausible values, event-per-parameter 불안정, imputation provenance 불충분 |
| 성공 기준 | Complete-case와 MI estimand를 분리해 같은 model contrasts 보고; imputation failures 보존 |
| 실패 시 원고 처리 | MI를 수행했다고 쓰지 않고 n=153 complete-case limitation과 missingness를 명시 |
| 변경 위치 | Methods, `downstream_recurrence_transfer.tex`, limitations, supplement |

### A3. Inner-nested PCA k selection

| 필드 | 계획 |
|---|---|
| 연구 질문 | k∈{4,8,16,32,64}를 inner CV에서 선택했을 때 unbiased outer-OOF recurrence performance가 유지되는가? |
| 필요한 이유 | 현재 k는 전체 OOF sweep을 본 뒤 해석되어 selected performance에 optimism이 있음 |
| 재사용 결과 | 두 encoder embeddings, outer folds, existing sweep |
| 추가 계산 범위 | Outer training 안의 inner CV로 k 선택, fold별 선택 k와 outer prediction 저장; sweep은 sensitivity로 유지 |
| 입력 데이터 | LEOPARD CONCH/Virchow cache, recurrence outcome, frozen outer folds |
| 예상 산출물 | `direct_recurrence_nested_pca_selection.csv`, fold selections, OOF predictions, manifest |
| CPU/GPU | CPU only |
| 예상 시간 | 30–120분 |
| 중단 조건 | Inner event 수 부족, fold leakage, deterministic tie rule 부재, selected-k prediction 저장 실패 |
| 성공 기준 | 모든 outer fold의 k가 training data만으로 선택되고 one-shot OOF metric/uncertainty가 저장됨 |
| 실패 시 원고 처리 | 특정 k 성능과 “stable across seeds” 문구를 삭제하고 기존 sweep을 exploratory sensitivity로만 보고 |
| 변경 위치 | Methods PCA paragraph, `downstream_recurrence_transfer.tex`, supplement |

본 계획의 기본 경로는 A3를 실행하지 않고 마지막 행의 제한 문구를 적용하는 것이다. Reviewer 대응상 selected-k 성능이 반드시 필요하다는 판단이 생기면 A3를 승격한다.

## 7. 선택 또는 비권장 분석 cards

### O1. SPOP 128 tiles targeted run

| 필드 | 계획 |
|---|---|
| 연구 질문 | Native-scale Virchow에서 16→64 증가가 128에서도 이어지는가? |
| 필요한 이유 | Plateau 여부에는 정보가 있으나 configuration-sensitive라는 핵심 결론을 바꿀 가능성은 제한적 |
| 재사용 결과 | 16/32/64 grid와 64-tile coordinate/cache |
| 추가 계산 범위 | SPOP만 두 encoders×5 seeds×2 scales×128 tiles; frozen folds |
| 입력 데이터 | WSI/encoder와 frozen coordinates/sampling protocol |
| 예상 산출물 | 20 cells, 100 fold rows, coordinates/cache/manifest/contrast |
| CPU/GPU | GPU 필요 |
| 예상 시간 | 6–18 GPU-hours 추정 |
| 중단 조건 | 128 accepted tiles coverage 부족, >2× 예상 시간, disk/memory 압박, 64-tile 추세가 claim decision과 무관 |
| 성공 기준 | 20/20 cells complete, same patients/folds, 64-vs128 paired summary |
| 실패 시 원고 처리 | Sensitivity 범위를 16–64 tiles로 정확히 제한 |
| 변경 위치 | SPOP Results/supplement만; core conclusion은 변경하지 않음 |

### O2. AR random-effects summary

| 필드 | 계획 |
|---|---|
| 연구 질문 | Site별 AR effect의 보조 pooled value를 만들 수 있는가? |
| 필요한 이유 | 원 계획에 있었으나 일반 meta-analysis 독립성 가정과 맞지 않음 |
| 재사용 결과 | 여섯 LOO site estimates/CI |
| 추가 계산 범위 | 수행하지 않는 것이 기본. 수행 시 dependence-aware estimand를 먼저 새로 설계해야 함 |
| 입력 데이터 | `resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv`와 shared-training 구조 |
| 예상 산출물 | 기본값 없음; 대신 non-independence rationale 문서화 |
| CPU/GPU | CPU, 계산비용 미미 |
| 예상 시간 | 새 통계 설계 없이는 실행하지 않음 |
| 중단 조건 | Ordinary inverse-variance pooling만 제안되거나 shared training dependence를 설명하지 못함 |
| 성공 기준 | 실행하지 않고 pooled internal-CV와 site-specific estimates를 분리 보고 |
| 실패 시 원고 처리 | Random-effects 수치를 삭제; site transportability unresolved 유지 |
| 변경 위치 | `confounder_site_audits.tex`, Figure 6 caption/limitations |

### O3. 전체 128-tile grid 또는 360-cell 재실행

| 필드 | 계획 |
|---|---|
| 연구 질문 | 이미 관찰된 방향이 더 큰 tile budget/완전 재실행에서 달라지는가? |
| 필요한 이유 | 일부 sensitivity는 늘지만 현재 MR claim gap과 직접 연결되지 않음 |
| 재사용 결과 | 완전한 360 cells/1,800 folds/60 shards |
| 추가 계산 범위 | 기본값 0; 재실행 금지 |
| 입력 데이터 | 해당 없음 |
| 예상 산출물 | 없음 |
| CPU/GPU | 큰 GPU 비용 |
| 예상 시간 | 기존 full run에 준하는 장시간 |
| 중단 조건 | R1 reconciliation이 성공하면 자동 생략; mismatch가 생겨도 먼저 root-cause audit, 전체 재실행은 별도 승인 |
| 성공 기준 | 불필요한 중복 계산을 하지 않음 |
| 실패 시 원고 처리 | 16–64/두 scale/5 seeds 범위로 정확히 제한 |
| 변경 위치 | Methods/limitations의 범위 문구만 |

## 8. Claim별 유지·하향·삭제·추가 결정

`resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py`를 먼저 수정한 뒤 CSV와 Markdown을 함께 재생성한다. 수동으로 두 representation을 따로 고치지 않는다.

| Claim | 결정 | 개정 문구의 핵심 | 필요한 최종 근거 |
|---|---|---|---|
| C01 qualification framework | **유지** | Operational qualification framework가 transportable/context-sensitive/unsupported signal을 구분 | 최신 claim matrix, 전체 result lineage, reliability map |
| C02 Gleason/phenotype transfer | **유지, 안정성 문구 갱신** | 두 marker의 방향은 encoders/5 seeds/16–64 tiles/두 scales에서 재현; Gleason effect size는 encoder/seed에 더 민감 | R1 summary, PANDA CONCH+Virchow source 연결 |
| C03 PTEN | **유지하되 범위 제한** | TCGA 내 pooled association은 모든 grid cell에서 chance 초과; held-out grade increment는 지지되지 않고 external validation은 아님 | R1, CONCH+Virchow nested/source pair |
| C04 SPOP | **하향·전면 재작성** | Frozen primary configuration에서 unsupported; configuration sensitivity가 크며 modest effect와 tumor dilution을 배제하지 못함 | R1, R5; A1을 하면 enriched result 추가 |
| C05 AR | **하향·재작성** | Pooled positive sign은 반복되지만 grade-independent increment와 site transportability는 미해결 | R1, R5, nested+site source pairs |
| C06 marker 7 transfer | **재작성** | Post-hoc exploratory, endpoint- and encoder×scale-conditioned; CONCH 강함, Virchow 1.76에서 일부 회복; official PFI 전에는 endpoint claim 미완료 | R1–R3, common-498, exact PFI |
| C07 marker 7 increment | **좁게 유지/조건부** | Grade-only baseline에서는 increment 가능; n=153 full clinical+site baseline에서는 추가 이득을 지지하지 않음. Same-draw ΔC/ΔIBS 후 확정 | R4, optional A2 |
| 새 stability claim | **보조 claim 추가** | Grid는 robustness/setting sensitivity audit이지 독립 외부 검증이나 360개 확증 검정이 아님 | R1 summary/QC와 supplement |

삭제할 표현은 다음과 같다.

- “SPOP reproducible/robust/clean null”
- “Virchow failed even after scale matching” 또는 모든 scale에 일반화한 encoder failure
- 모든 site에 일반화한 “AR site instability”
- PCA k=8이 unbiased selected optimum이거나 seed-stable하다는 근거 없는 문구
- PFS/DFS/reconstructed recurrence를 official PFI와 등치하는 문구
- 360 grid를 external validation 또는 independent replication으로 부르는 문구

## 9. 원고 section/table/figure 개정 계획

### 9.1 Abstract

- `paper/sections/abstract.tex`에서 SPOP robust-null과 categorical Virchow-failure 문구를 위 결정으로 교체한다.
- 360-cell grid를 숫자로 언급할 경우 “sensitivity grid”라고 부르고 6 markers, 2 encoders, 5 sampling seeds, 16/32/64 tiles, 2 scales의 범위를 함께 쓴다.
- Official PFI가 완료되지 않으면 PFI를 abstract에 쓰지 않는다.

### 9.2 Methods

| Section | 변경 |
|---|---|
| `prespecified_exploratory.tex` | Retrospective protocol snapshot과 historical freeze limitation, marker 7 post-hoc 지위, 360-grid 해석 범위 |
| `cohorts_encoders.tex` | NADT 463-slide frame과 Gleason 334-slide evaluable subset 분리; marker 7 source retention; encoder별 mpp |
| `qualification_gates.tex` | Chance threshold, direction reversal, seed t interval의 비추론적 성격, multiplicity 범위 |
| `core_marker_results.tex`의 methods 문맥 | Frozen folds, patient aggregation, 16/32/64 tiles, seeds/scales, coordinate reuse와 fail-closed QC |
| `confounder_site_audits.tex` | AR descriptor/metadata와 scanner-site confounding; SPOP class weight/site/power; random-effects 미실시 이유 |
| `downstream_recurrence_transfer.tex` | Common-498, official PFI source/mapping, same-draw paired bootstrap, common cohort, PCA 선택 지위, MI 여부 |
| `supplement.tex` | Complete schema, seeds/folds/coordinate manifest, TIFF QC, undefined replicate 규칙과 software/hash provenance |

### 9.3 Results

- `core_marker_results.tex`: Gleason, phenotype, PTEN의 60-cell marker summary와 정확한 variability 범위. Figure 9를 구 90-slide single-seed 결과에서 full grid로 교체한다.
- `confounder_site_audits.tex`: AR pooled positive와 site별 불확실성을 분리한다. Site-level CI가 모두 0을 포함한다는 사실과 metadata 가용성을 보고한다.
- `failure_modes.tex`: SPOP range 0.348–0.679, chance 이하 25/60, scale reversal을 보고하고 robust null을 삭제한다.
- `downstream_recurrence_transfer.tex`: Marker 7 CONCH/native/1.76와 Virchow/native/1.76을 함께 보여 주고 common-498 결과로 확인한다. Exact PFI와 R4 결과가 준비되기 전 확정 문구를 넣지 않는다.
- `limitations.tex`: Correlated grid, seed CI, source-retention variation, TIFF warning, historical runner lineage, complete-case missingness, small event counts, official PFI 상태를 명시한다.

### 9.4 Discussion

- `failure_modes.tex` 및 conclusion 성격의 문단에서 null을 biological absence로 읽지 않는다.
- Scale sensitivity를 model qualification의 핵심 결과로 논의하되 어느 encoder가 보편적으로 우월하다고 일반화하지 않는다.
- Marker 7은 endpoint 및 representation 조건에 민감한 post-hoc exploratory signal로 유지한다.
- AR은 pooled sign과 transportability를 분리하고 scanner/stain causal explanation을 피한다.
- Grid는 같은 cohort와 folds를 반복한 sensitivity analysis이지 population prevalence, clinical utility, external validation 근거가 아님을 반복한다.

### 9.5 Figures

| Figure | 결정 | Source-driven 변경 |
|---|---|---|
| Figure 1 protocol/reliability | 갱신 | 최신 C01–C07 tier/status를 CSV에서 읽음; hard-coded tier 제거 |
| Figure 2 marker 1 external | 유지·계보 보완 | 두 panel의 모든 수치를 figure-source CSV에 저장 |
| Figure 3 CONCH vs Virchow | 재생성 | 14 hard-coded metric 제거; integrated/source CSV와 최신 encoder×scale 결과 사용 |
| Figure 4 ROC | 계보 보완 | 재계산값을 먼저 figure-source CSV로 저장하고 renderer는 CSV만 읽음 |
| Figure 5 forest | stale check 후 재생성 | source CSV hash와 PDF mtime 연결 |
| Figure 6 PTEN/AR | 갱신 | AR descriptor/metadata, transportability wording 반영 |
| Figure 7 marker 7 transfer | 재작성 | common-498, exact endpoint, paired survival source; panel B hard-code 제거 |
| Figure 8 survival curves | same-name generator로 재생성 | 저장 OOF survival CSV만 읽고 alias/duplicate output 제거 |
| Figure 9 scale/tile | **완전 교체** | R1의 360-cell `fig9_stability_grid.csv`와 contrast CSV 사용 |

### 9.6 Tables

현재 여섯 inline result table(`tab:pool`, `tab:confounder-4-6`, `tab:leopard-survival`, `tab:confounder-7`, `tab:supp-bhfdr`, `tab:supp-marker7-clinical`)을 generated TeX fragments로 바꾼다. 추가/갱신할 표는 다음과 같다.

- Claim–evidence matrix와 endpoint hierarchy
- Full stability 72-configuration summary와 paired contrasts
- Marker 7 source retention/common-498
- AR site distributions/metadata와 SPOP site/power
- Common-cohort clinical hierarchy와 paired ΔC/ΔIBS
- Official PFI concordance/performance
- Figure/table manifest와 QA compliance table

### 9.7 Supplement

- 72행 seed summary와 360-cell canonical results
- Scale/encoder/tile paired contrast 전체
- 60-shard coordinate manifest와 cohort invariants
- NADT two-slide TIFF warning 표
- Marker 7 source retention과 common-498 sensitivity
- SPOP site/power 및 A1/O1을 수행한 경우 그 결과
- AR distribution/metadata availability
- Same-draw bootstrap replicate count와 undefined fraction
- Official PFI patient-level concordance/reason code
- PCA sweep; A3를 하면 outer-fold selected k
- A2를 하면 MI diagnostics, 아니면 complete-case limitation
- Input/output hashes, environment, historical lineage limitation

## 10. P0·재현성 문서 갱신 순서

1. `resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py`의 stale claim/source/path를 먼저 수정한다.
2. `paper/claim_evidence_matrix.csv/.md`를 한 번에 재생성한다.
3. `paper/endpoint_hierarchy.csv/.md`에서 E08을 R3 결과에 따라 갱신하되 PFS/DFS와 분리한다.
4. `paper/protocol_provenance.json`을 retrospective/current-run provenance로 재생성한다. Snapshot 이후 runner 변경과 최초 96-cell exact-code lineage 미해결을 숨기지 않는다.
5. `cohort_manifest.csv`에 full-grid representation과 embedding hash를 추가하고 data dictionary를 만든다.
6. `environment.yml`/`requirements-lock.txt`/`RUN_REPRODUCTION.md`의 실행 환경을 `.venv/bin/python` 또는 명시적으로 검증한 단일 환경으로 통일하고 complete lock/model IDs를 기록한다.
7. `paper/figure_manifest.csv`와 table manifest를 생성한다.
8. One-command paper build가 source validation → figures/tables → XeLaTeX로 이어지게 한다.

기존 retrospective provenance를 역사적 prespecification처럼 소급 수정하지 않는다. 새 manifest는 “현재 파일과 결과를 재현하는 provenance”와 “당시 코드 동결 증거”를 구분한다.

## 11. 실행 순서와 의존성

```text
사용자 Gate A: R1 통합 구현 승인 (CPU only)
    ↓
R1 raw reconciliation + tests + deterministic rerun
    ↓ fail이면 원인 보고 후 중단
사용자/과학 검토 Gate B: integrated SPOP·marker7·AR 해석 승인
    ├─ R2 common-498
    └─ R5 AR/SPOP 저비용 표
    ↓
사용자 Gate C: 공식 TCGA-CDR source 획득 승인
    └─ R3 exact PFI
    ↓
R4 common-cohort paired ΔC/ΔIBS
    ↓
PCA 결정: exploratory wording이면 A3 생략; 강한 claim이면 A3
    ↓
사용자 Gate D: 권장/선택 GPU 분석 필요성 재판정
    ├─ 필요 시 A1 tumor-enriched
    └─ 특별한 이유가 있을 때만 O1 128 tiles
    ↓
필수 결과 freeze + R6 manuscript/lineage 개정
    ↓
R7 final QA, clean rerun, PDF rebuild
```

R3와 R4의 reconstructed-endpoint branch는 일부 병렬화할 수 있지만, official-PFI branch는 R3에 의존한다. R6의 generator 구현은 선행할 수 있어도 최종 수치와 claim을 freeze하기 전 PDF를 final로 만들지 않는다.

## 12. 사용자 승인 지점

| Gate | 필요한 승인 | 승인 전 하지 않는 일 |
|---|---|---|
| A | `aggregate_stability_grid.py`와 test 구현·CPU 실행 | 통합 output 생성/원고 반영 |
| B | Grid가 요구하는 SPOP/marker7/AR claim 하향 문구 | claim matrix와 본문 확정 |
| C | 공식 TCGA-CDR source의 외부 획득·local archive | 다운로드, endpoint mapping |
| D | A1/O1 같은 새 GPU 분석 | GPU allocation, 새 tile/model inference |
| E | 필수 분석 freeze와 원고 rewrite 진행 | 결과 수치가 들어간 최종 figure/table/PDF 생성 |

현재 요청할 첫 승인은 Gate A뿐이다. Gate A는 raw 결과를 수정하지 않는 CPU 통합/QC 구현이며 새 GPU 작업을 포함하지 않는다.

## 13. 최종 QA 체크 순서

1. R1의 360/1,800/60 exact reconciliation과 raw pre/post hashes 확인.
2. R2–R5/A2/A3 중 승인된 분석의 tests, undefined replicate count/fraction, patient/fold/draw alignment 확인.
3. 모든 derived CSV를 freeze하고 non-self-referential output hashes 저장.
4. P0 builder로 claim matrix, endpoint hierarchy, provenance, cohort/data dictionary를 재생성.
5. Figure/table manifest의 모든 source/script/output/manuscript-location/hash가 존재하는지 검사.
6. Figure/table generator가 저장 CSV만 읽는지 정적·동적 검사; hard-coded result array 0건.
7. 원고 숫자와 source CSV를 기계적으로 대조하고 rounding rule을 기록.
8. Absolute project root, `/tmp/claude-*`, scratch path, credential/secret pattern을 검사.
9. 변경 Python에 `.venv/bin/python -m py_compile ...`; 관련 unit/integration tests를 fresh 실행.
10. AGENTS.md의 immutable PRECISE clinician source를 건드리지 않았음을 확인하고, 존재 시 `resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv` SHA256가 `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`인지 확인.
11. 새 temporary output root에서 clean rerun; 문서화된 timestamp field 외 byte-identical 여부 확인.
12. 모든 figure/table을 재생성하고 stale timestamp가 0인지 검사.
13. XeLaTeX를 연속 두 번 실행하고 두 command/exit status/log를 보존.
14. Unresolved reference/citation 0, numeric mismatch 0, missing manifest link 0을 확인.
15. 최신 `paper/main.pdf`의 SHA256, size, timestamp와 source/output manifest를 저장.
16. `complete/partial/not_done` compliance report를 새 evidence로 다시 계산하고 실패 항목을 숨기지 않는다.
17. `git status --short`와 explicit allowlist diff를 검토한다. Broad staging, commit, push는 사용자 별도 지시가 없으면 하지 않는다.

## 14. 완료 조건

MR-v1 보완 package는 다음이 모두 충족될 때만 complete로 선언한다.

- R1의 canonical outputs와 QC가 deterministic하게 재생성됨
- 바뀐 SPOP/marker7/AR claim이 integrated evidence와 일치함
- Official PFI가 완료되거나, 확보 불가를 명시하고 PFI 완료 claim을 완전히 제거함. 단, 원 MR-v1 요구 closure 상태는 후자의 경우 `not_done` 유지
- Same-patient/same-draw paired survival 결과와 undefined replicate 보고가 있음
- Nested PCA를 하지 않으면 selected-k/seed-stability claim이 없음
- MI를 하지 않으면 n=153 complete-case limitation이 abstract/results/discussion과 일관됨
- 모든 figure/table이 저장 source CSV와 manifest에 연결됨
- Numeric/compliance/reproducibility QA가 통과하고 최신 PDF가 두 번 빌드됨
- Raw/frozen input hashes가 보존되고 historical lineage limitation이 명시됨

이 계획은 가장 큰 새 계산을 추가하는 계획이 아니라, 이미 얻은 360-cell 결과가 요구하는 claim 수정과 최소 필수 endpoint/statistical closure를 우선하는 계획이다.
