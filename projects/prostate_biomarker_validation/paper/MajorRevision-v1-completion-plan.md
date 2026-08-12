# MR-v1 보완 실행계획

**고정일:** 2026-08-03
**대상:** `paper/MajorRevision-v1.md`의 미완료·부분완료 항목
**원칙:** 핵심 과학적 대응과 명시 산출물 준수를 분리해 추적하고, 소급하여
`prespecified` 또는 과거 Git commit을 주장하지 않는다.

## 1. 현재 기준선

- Nested cross-fitting, 2,000회 refit permutation, M0--M5 clinical hierarchy와 그에
  따른 claim 하향은 완료됐다.
- 500-case TCGA-PRAD endpoint provenance와 PFS/DFS/strict-endpoint 민감도 분석은
  존재한다.
- 가장 큰 과학적 간극은 6-marker × 2-encoder × 5-seed tile/scale stability grid다.
- 가장 큰 재현성 간극은 claim--evidence matrix, endpoint hierarchy, cohort manifest,
  환경 명세, tile coordinates와 완전한 figure data lineage다.

## 2. 작업 패키지와 완료 기준

| 우선순위 | 작업 패키지 | 핵심 산출물 | 완료 기준 |
|---|---|---|---|
| P0 | 주장·endpoint·provenance 동결 | `claim_evidence_matrix.*`, `endpoint_hierarchy.*`, `protocol_provenance.json` | 모든 핵심 claim이 source CSV/script/원고 위치에 연결되고 PFI 미실행 등 격차가 명시됨 |
| P0 | cohort·환경 manifest | `cohort_manifest.csv`, `environment.yml`, `requirements-lock.txt`, `RUN_REPRODUCTION.md` | 사용된 cache representation과 분석 환경을 저장소 상대경로로 재구성 가능 |
| P1 | 전체 stability grid | tile/fold/cell/summary CSV | 6 markers, CONCH+Virchow, ≥5 seeds, tiles 16/32/64, encoder별 ≥2 scales; seed SD와 방향 반전 보고 |
| P2 | AR/SPOP 전용 보완 | site-characteristics/random-effects, SPOP ablation/power CSV | AR 분포·grade·scanner/stain 가용성 보고; SPOP class-weight/site/tile/tumor-enriched/encoder 분석 |
| P3 | 생존분석 | paired ΔC-index/ΔBrier bootstrap, nested PCA selection | 동일 환자 bootstrap으로 Δ성능 CI; PCA k를 inner CV 안에서 선택 |
| P4 | endpoint 정확화 | PFI/DFI mapping·concordance·performance CSV | PFS와 PFI를 혼용하지 않고 공식 source field/정의를 분리 보고 |
| P5 | figure lineage | `figure_manifest.csv`, CSV-driven figure scripts | 결과 수치 하드코딩 0건, 절대 프로젝트 경로 0건, 한 명령으로 재생성 |
| P6 | 최종 QA | compliance/numeric/reproducibility reports | MR-v1 항목별 complete/partial/not-done 판정, XeLaTeX 2회, unresolved reference 0건 |

## 3. P1 stability grid 사양

### 3.1 최소 정식 grid

- Marker: Gleason, phenotype, PTEN, SPOP, AR, marker 7
- Encoder: CONCH, Virchow
- Sampling seed: 5개 이상
- Tile count: 16, 32, 64
- Scale: encoder별 대표 2개 이상
- 128 tiles: 전체 수행이 가능하면 포함하고, 자원이 제한되면 PTEN/SPOP/AR/marker 7에
  우선 적용한다.
- CV fold는 marker/cohort별로 한 번 고정하고 모든 cell에서 동일하게 사용한다.

최소 grid는 6×2×5×3×2 = 360 cells다. 각 seed/scale에서 최대 tile 집합을 한 번
임베딩하고 16/32/64(/128)는 고정된 tile ordering의 prefix로 계산한다.

### 3.2 필수 저장 항목

- `tile_coordinates.csv`: slide, seed, encoder, target mpp, pyramid level, x/y, crop size,
  tissue fraction, tile rank
- `stability_fold_assignments.csv`: case, cohort, marker, fold
- `stability_cell_results.csv`: cell별 slide/patient metric
- `stability_fold_results.csv`: fold별 metric
- `stability_summary.csv`: seed mean/SD/CI, min/max, direction reversal, chance 통과 비율

## 4. 통계 보완 사양

### 4.1 AR

사이트별 n, effect, bootstrap CI에 AR-score 분포, Gleason 분포, scanner/stain metadata
가용성을 결합한다. Scanner/stain 정보가 없으면 추정하지 않고 `not_available`로 기록한다.
서로 다른 leave-one-site-out 모델의 random-effects estimate는 exploratory 보조값으로만
보고한다.

### 4.2 SPOP

Class weight on/off, CONCH/Virchow, 16/64/128 tiles, random/tumor-enriched sampling,
pooled/site-restricted, ≥5 seeds를 비교한다. 80%와 90% power 최소 검출 AUROC를 함께
보고하며 결론은 “큰 효과를 지지하지 않음”으로 제한한다.

### 4.3 생존분석

동일한 held-out 환자와 동일 bootstrap draw로 image-only−clinical-only,
combined−clinical-only, M5−M4와 LEOPARD pool 간 ΔC-index/ΔBrier를 계산한다. PCA 후보
`{4,8,16,32,64}`는 outer fold의 inner CV에서 선택하고, 전체 sweep은 sensitivity로
유지한다. Multiple imputation은 outer-training fold 내부에서 누출 없이 구현할 수 있을
때만 수행한다.

## 5. 실행 순서와 gate

1. **Gate A — P0:** 문서·manifest를 먼저 생성하고 현재 격차를 기계 판독 가능하게 고정
2. **Gate B — P1 사전 점검:** 1 marker × 2 encoders × 2 seeds smoke grid, 좌표·fold 저장 검증
3. **Gate C — P1 본실행:** 최소 360-cell grid; 실패 cell은 재시도 후 원인 기록
4. **Gate D — P2/P3/P4:** AR/SPOP, survival, 정확한 PFI 순으로 통계 보완
5. **Gate E — P5/P6:** figure lineage 정비, 수치 일치 검사, 원고와 compliance 보고서 갱신

## 6. 범위 축소 규칙

- GPU/시간 제약으로 128-tile 전체 grid를 못 하면 16/32/64 최소 grid를 우선 완료한다.
- 특정 cohort에 marker label이 구조적으로 없으면 억지로 공통 cohort를 만들지 않고
  canonical cohort와 `not_applicable` 사유를 기록한다.
- 과거 tile coordinate나 commit hash를 복구할 수 없으면 생성하지 않고, 새 실행부터
  저장한다.
- 약한 결과가 나오더라도 기존 결론을 보존하기 위해 분석 조건을 사후 변경하지 않는다.

## 7. 상태

- [x] 보완 실행계획 문서화
- [x] P0 주장·endpoint·protocol 산출물
- [x] P0 cohort·환경 manifest
- [x] P1 360-cell grid 사양·환자 fold 동결
- [x] P1 smoke grid
- [ ] P1 전체 grid — 2026-08-03 GPU 1--5에서 실행 시작; incremental outputs 저장 중
- [ ] P2 AR/SPOP
- [ ] P3 survival/PCA
- [ ] P4 exact PFI
- [ ] P5 figure lineage
- [ ] P6 최종 QA
