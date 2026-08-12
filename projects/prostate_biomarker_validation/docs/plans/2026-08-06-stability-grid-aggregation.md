# Stability Grid Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify one CPU-only, fail-closed entry point that reconciles the frozen 360-cell stability grid and publishes deterministic canonical, summary, contrast, coordinate-manifest, provenance, QC, and figure-source outputs without modifying raw results.

**Architecture:** `resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py` exposes small pure validation and aggregation functions plus one filesystem orchestration function. It reads the frozen spec/folds and the six fixed runner directories, rejects any semantic or cardinality mismatch before publication, stages deterministic files in a temporary directory, verifies them, and atomically replaces only the approved derived paths. `tests/test_aggregate_stability_grid.py` drives each boundary with literal fixtures and includes a conditional full-repository integration guard.

**Tech Stack:** Python 3.11+, standard library, pandas, NumPy, SciPy, tifffile, `unittest`; execute with `.venv/bin/python`.

## Global Constraints

- Treat `resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv`, `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv`, all files under `resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/`, and run logs as immutable raw inputs.
- Never rewrite the frozen spec's 360 `pending` values; publish `raw_status` and a separate `reconciliation_status`.
- Require exactly 360 unique cells, 1,800 unique fold rows, five folds `{0,1,2,3,4}` per cell, six fixed runner directories, and 60 coordinate shards for the full-data run.
- Preserve structurally absent fields as missing; never convert them to zero or a negative outcome.
- Use `≤0.5` as chance-or-worse for AUROC/C-index and `≤0` for Spearman rho; exact ties are counted separately.
- Label five-seed Student-t intervals `sampling_seed_t_ci_*`; never present them as patient-level or population confidence intervals.
- Do not infer that TIFF warnings had no pixel-level effect; report only header-scan messages and observed coordinate retention.
- Record input pre/post hashes, software versions, elapsed time, explicit volatile timestamps, and non-self-referential output hashes.
- CSV serialization is deterministic: UTF-8, LF, fixed column order, `float_format="%.15g"`, and empty representation for missing values.
- No GPU/model inference, raw mutation, broad Git staging, commit, or push.

---

### Task 1: Exact raw schemas and cell/fold reconciliation

**Files:**
- Create: `resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py`
- Create: `tests/test_aggregate_stability_grid.py`

**Interfaces:**
- Produces: `StabilityGridIntegrityError`.
- Produces: `load_spec(path: Path) -> pd.DataFrame` and `load_assignments(path: Path) -> pd.DataFrame`.
- Produces: `load_runner_results(run_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[Path]]`.
- Produces: `reconcile_cells_and_folds(spec, assignments, raw_cells, raw_folds, *, require_full_grid: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict]`.
- Canonical cell output uses the exact spec columns plus `raw_runner_dir`, `raw_cell_results_path`, `raw_cell_results_sha256`, `raw_status`, `reconciliation_status`, `n_slides`, `n_source_patients`, `n_patients`, `n_events`, `slide_metric`, and `patient_metric`.
- Canonical fold output uses the cell semantics plus `raw_runner_dir`, `raw_fold_results_path`, `raw_fold_results_sha256`, `fold`, `fold_n_patients`, `fold_patient_metric`, `assignment_n_patients`, and `fold_assignment_reconciled`.

- [ ] **Step 1: Write failing schema and normalization tests**

Add tests that import the not-yet-existing module, construct one standard and one marker-7 raw row, and assert the canonical output preserves missing structural fields:

```python
def test_reconcile_preserves_structural_missingness_and_spec_status(self):
    spec, assignments, cells, folds = self.two_cell_fixture()
    canonical_cells, canonical_folds, qc = reconcile_cells_and_folds(
        spec, assignments, cells, folds, require_full_grid=False
    )
    self.assertEqual(canonical_cells["raw_status"].tolist(), ["complete", "complete"])
    self.assertEqual(canonical_cells["status"].tolist(), ["pending", "pending"])
    self.assertEqual(set(canonical_cells["reconciliation_status"]), {"reconciled"})
    self.assertTrue(pd.isna(canonical_cells.loc[0, "n_source_patients"]))
    self.assertTrue(pd.isna(canonical_cells.loc[1, "n_slides"]))
    self.assertEqual(len(canonical_folds), 10)
    self.assertTrue(canonical_folds["fold_assignment_reconciled"].all())
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_aggregate_stability_grid -v
```

Expected: import failure because `aggregate_stability_grid` does not exist.

- [ ] **Step 3: Add failing integrity tests**

Add literal mutations of the valid fixture and assert `StabilityGridIntegrityError` for:

```python
def test_reconcile_rejects_an_incomplete_cell(self):
    spec, assignments, cells, folds = self.two_cell_fixture()
    cells.loc[0, "status"] = "failed"
    with self.assertRaisesRegex(StabilityGridIntegrityError, "complete"):
        reconcile_cells_and_folds(
            spec, assignments, cells, folds, require_full_grid=False
        )

def test_reconcile_rejects_a_missing_fold(self):
    spec, assignments, cells, folds = self.two_cell_fixture()
    folds = folds.iloc[:-1].copy()
    with self.assertRaisesRegex(StabilityGridIntegrityError, "fold"):
        reconcile_cells_and_folds(
            spec, assignments, cells, folds, require_full_grid=False
        )
```

Add sibling tests, each with one literal mutation, for duplicate/missing/unexpected cell IDs,
spec/result metadata disagreement, reconstructed cell-ID disagreement, non-finite cell/fold
metrics, duplicate/extra fold keys, assignment-count disagreement, and reordered/extra raw CSV
headers. Each test names the production break it catches and mutates only one condition.

- [ ] **Step 4: Implement minimal loaders and reconciliation**

Implement fixed `RUNNER_SPECS`, exact ordered header constants, chunked SHA256, stable MPP formatting, cell-ID reconstruction, exact set equality, finite-metric checks, runner ownership, and fold/assignment reconciliation. Compare MPP using its two-decimal canonical string. In full mode additionally require the known 360/1,800 runner cardinalities and axes.

- [ ] **Step 5: Run focused tests and keep them GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_aggregate_stability_grid.ReconciliationTests -v
```

Expected: all reconciliation tests pass with no warnings.

### Task 2: Five-seed summaries and paired contrasts

**Files:**
- Modify: `resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py`
- Modify: `tests/test_aggregate_stability_grid.py`

**Interfaces:**
- Consumes: canonical cell table from Task 1.
- Produces: `build_stability_summary(cells: pd.DataFrame) -> pd.DataFrame` with exactly one row per marker×encoder×tiles×scale.
- Produces: `build_stability_contrasts(cells: pd.DataFrame) -> pd.DataFrame` with `native_vs_1.76`, `virchow_vs_conch_at_1.76`, and `tile64_vs16` rows.

- [ ] **Step 1: Write and run a failing summary test**

Use five literal SPOP values `[0.40, 0.45, 0.50, 0.55, 0.60]` and assert:

```python
def test_summary_labels_seed_variability_and_chance_ties(self):
    summary = build_stability_summary(self.spop_five_seed_cells())
    row = summary.iloc[0]
    self.assertAlmostEqual(row["mean"], 0.5)
    self.assertAlmostEqual(row["sample_sd"], 0.07905694150420947)
    self.assertAlmostEqual(row["sampling_seed_t_ci_low"], 0.40183784192612215)
    self.assertAlmostEqual(row["sampling_seed_t_ci_high"], 0.5981621580738778)
    self.assertEqual(row["n_chance_or_worse"], 3)
    self.assertEqual(row["n_ties"], 1)
    self.assertTrue(row["seed_null_straddle"])
```

Run this single test and verify it fails because the function is missing.

- [ ] **Step 2: Implement the minimal summary function and verify GREEN**

Use sample SD (`ddof=1`) and `scipy.stats.t.ppf(0.975, n_seeds-1)`. Reject groups that do not contain exactly seeds `{0,1,2,3,4}` in the full grid. Sort deterministically by marker, encoder, tiles, and MPP.

- [ ] **Step 3: Write and run failing contrast tests**

Build hand-checked cells whose values cross chance and assert exact row counts, labels, pair IDs, `delta_b_minus_a`, `relation_a`, `relation_b`, `null_crossing`, and `exact_tie`. The native mapping is literal `CONCH→0.88`, `Virchow→0.44`; the shared encoder comparison is only at 1.76; the tile comparison is exactly `64−16`.

- [ ] **Step 4: Implement contrasts and run all aggregation tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_aggregate_stability_grid.SummaryAndContrastTests -v
```

Expected: all tests pass and no p-value is produced.

### Task 3: Coordinate, metadata, log, and TIFF QC

**Files:**
- Modify: `resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py`
- Modify: `tests/test_aggregate_stability_grid.py`

**Interfaces:**
- Produces: `build_coordinate_manifest(run_root: Path, *, require_full_grid: bool) -> tuple[pd.DataFrame, dict, list[Path]]`.
- Produces: `summarize_logs(log_root: Path) -> tuple[pd.DataFrame, dict, list[Path]]`.
- Produces: `scan_nadt_tiff_headers(paths: Sequence[Path]) -> dict`.
- Coordinate manifest has one sorted row per shard and never concatenates shards into a published file.

- [ ] **Step 1: Write and run failing coordinate-manifest tests**

Create a temporary standard shard with one slide and literal ranks 0–63 plus its exact metadata row. Assert the manifest reports 64 rows, one slide/case, rank 0/63, no rank violations, matching metadata, SHA256, seed, scale, and encoder. Add separate failing cases for missing rank 63, duplicate rank, row metadata mismatch, unexpected field, and marker-7 cohort collision.

- [ ] **Step 2: Implement strict coordinate/meta validation and verify GREEN**

Use exact raw headers. Standard keys are `(file_name, case_id)`; marker-7 keys are `(cohort, file_name, case_id)`. Normalize only NADT `patient_id` to canonical `case_id` while leaving the raw file untouched. Require each entity's rank set to equal `{0,…,63}` and the coordinate entity set to equal the associated metadata entity set.

- [ ] **Step 3: Write and run failing log/TIFF tests**

Use a temporary log containing one `ERROR:tifffile … invalid page offset`, one unprefixed invalid offset, one two-line `FutureWarning`, one `[resume]`, and no traceback. Assert line counts remain separate from event interpretation. Use a valid temporary TIFF to assert header scanning records one scanned slide and no affected slide. The scanner must associate captured tifffile messages with the file being opened.

- [ ] **Step 4: Implement log and TIFF summaries and verify GREEN**

Treat historical log errors/warnings as reportable QC observations, not automatic failure after the data reconciliation succeeds. Record the resumed-log limitation. Do not state that an affected file has no pixel-level impact.

- [ ] **Step 5: Run focused QC tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_aggregate_stability_grid.CoordinateAndLogTests -v
```

Expected: all coordinate, metadata, log, and TIFF tests pass.

### Task 4: Fail-closed publication, manifests, CLI, and full-data guard

**Files:**
- Modify: `resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py`
- Modify: `tests/test_aggregate_stability_grid.py`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_run_manifest.csv`
- Generate locally: `resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json`
- Generate locally: `paper/figure_data/fig9_stability_grid.csv`
- Generate locally: `paper/figure_data/fig9_stability_contrasts.csv`

**Interfaces:**
- Consumes: all Task 1–3 functions.
- Produces: `build_all_frames(spec_path, assignments_path, run_root, log_root, *, scan_tiffs: bool, require_full_grid: bool) -> dict`.
- Produces: `run_aggregation(spec_path, assignments_path, run_root, log_root, output_dir, figure_data_dir, *, generated_at_utc=None, scan_tiffs=True, require_full_grid=True, elapsed_seconds_override=None) -> dict`.
- Produces: `parse_args()` and `main()` with approved defaults.

- [ ] **Step 1: Write and run failing publication tests**

Use a temporary output root and patched pure input frames to assert that `run_aggregation`:

```python
def test_publication_is_fail_closed_and_non_self_referential(self):
    paths = self.write_two_cell_files()
    paths["cell_results"].write_text("broken_header\n", encoding="utf-8")
    with self.assertRaises(StabilityGridIntegrityError):
        run_aggregation(
            paths["spec"], paths["assignments"], paths["run_root"],
            paths["log_root"], paths["output_dir"], paths["figure_dir"],
            generated_at_utc="2026-08-06T00:00:00Z", scan_tiffs=False,
            require_full_grid=False, elapsed_seconds_override=0.0,
        )
    self.assertEqual(list(paths["output_dir"].glob("stability_*")), [])

def test_publication_writes_the_exact_output_contract(self):
    paths = self.write_two_cell_files()
    result = run_aggregation(
        paths["spec"], paths["assignments"], paths["run_root"],
        paths["log_root"], paths["output_dir"], paths["figure_dir"],
        generated_at_utc="2026-08-06T00:00:00Z", scan_tiffs=False,
        require_full_grid=False, elapsed_seconds_override=0.0,
    )
    self.assertNotIn("stability_run_manifest.csv", result["output_sha256"])
    self.assertNotIn("stability_qc_report.json", result["output_sha256"])
```

Assert all nine approved files exist, CSV keys are unique, figure-source files are byte-identical projections of the saved canonical summary/contrast tables, and a second fixed-timestamp run produces byte-identical content.

- [ ] **Step 2: Implement staged deterministic publication and CLI**

Hash every consumed input before validation and after publication. Stage all files under a temporary directory, read them back to validate schemas/counts/keys, then call `os.replace` for each final path and publish the run manifest last. The manifest excludes itself and the QC report from output hashes; the QC report documents that exclusion. Isolate `generated_at_utc`, elapsed seconds, and mtime fields as explicitly volatile provenance.

- [ ] **Step 3: Add and run the conditional full-repository integration guard**

When the frozen inputs exist, call the pure aggregation pipeline and assert the literal repository contract:

```python
@unittest.skipUnless(FULL_SPEC.exists(), "local full grid is unavailable")
def test_full_repository_grid_reconciles(self):
    result = build_all_frames(
        FULL_SPEC,
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs",
        scan_tiffs=True,
        require_full_grid=True,
    )
    self.assertEqual(len(result["cells"]), 360)
    self.assertEqual(len(result["folds"]), 1800)
    self.assertEqual(len(result["summary"]), 72)
    self.assertEqual(len(result["coordinate_manifest"]), 60)
    self.assertEqual(int(result["qc"]["chance_or_worse_cells"]), 26)
    self.assertEqual(int(result["qc"]["marker7_common_source_patients"]), 498)
```

- [ ] **Step 4: Run syntax and full test verification**

Run:

```bash
.venv/bin/python -m py_compile resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py tests/test_aggregate_stability_grid.py
.venv/bin/python -m unittest tests.test_aggregate_stability_grid -v
.venv/bin/python -m unittest discover -s tests -v
```

Expected: all new tests and the 24-test baseline pass.

- [ ] **Step 5: Execute Gate A against the real frozen data**

Run:

```bash
.venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py \
  --spec resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv \
  --fold-assignments resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv \
  --run-root resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full \
  --log-root resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs
```

Expected: exit 0; output counts 360/1,800/72/60; no raw input hash change; QC records 26 chance-or-worse cells, 20 native-scale null crossings, 4 shared-scale encoder crossings, 9 five-seed null straddles, 498 common marker-7 source patients, 26 observed invalid-page-offset log lines, and two affected NADT TIFF slides without claiming zero pixel impact.

- [ ] **Step 6: Verify deterministic rerun and immutable source**

Run the entry point a second time, compare deterministic output hashes while excluding documented volatile provenance, and verify:

```bash
sha256sum 'resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv'
git status --short --untracked-files=all -- \
  resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py tests/test_aggregate_stability_grid.py \
  resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv \
  resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv \
  resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv resources/projects/prostate_biomarker_validation/model_workspace/stability_run_manifest.csv \
  resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json paper/figure_data
```

Expected immutable PRECISE SHA256: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.
