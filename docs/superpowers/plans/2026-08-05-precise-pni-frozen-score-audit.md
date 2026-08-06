# PRECISE PNI Frozen-Score Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one deterministic, auditable Python entry point that validates the frozen PRECISE candidate universe against Song's 120-candidate review and regenerates every required table, report, and figure without changing model scores or source review data.

**Architecture:** A single script exposes small pure functions for input normalization, exact spatial-NMS reconstruction, endpoint calculation, subject-cluster bootstrap, plotting from saved CSVs, and provenance recording. Tests use hand-built candidate fixtures to lock down missing-label handling, strict NMS geometry, incomplete top-k coverage, metric failures, and deterministic resampling before the real data are processed. The entry point fails closed before writing analytical results if identity, geometry, score, stratum, or NMS reconciliation fails.

**Tech Stack:** Python 3.11; pandas, NumPy, SciPy, scikit-learn, matplotlib; `unittest`, JSON, and SHA256 from the standard library. (`pytest` and `pip` are absent from the workspace environment, so the standard-library runner is used without changing the environment.)

## Global Constraints

- Treat `opendataset/PRECISE/precise_pni_review (1).csv` as immutable and prove byte identity with pre/post SHA256.
- Populate `reviewer_id=Song` only in the derived normalized table; preserve clinician labels and keep blank outcomes missing/not evaluable.
- Do not refit scores, recalibrate weights, alter prompts/exemplars, optimize thresholds, or impute unreviewed candidates as negative.
- Reproduce `build_precise_pni_review_html.py::spatial_nms` exactly: per-slide descending `combined_score`, center distance `< 0.75 * current window_px` suppressed, followed by pandas percentile rank.
- Stop before analysis if reviewed identities, coordinates, geometry, scores, strata, raw ranks, or reconstructed NMS membership do not match the manifest.
- Evaluate per-slide budgets `k=1..10`; leave precision undefined unless every candidate in the budget has an evaluable label.
- Interpret ROC AUC and average precision only within the stratified 120-candidate audit sample.
- Use subject-cluster bootstrap with seed `20260805`, `10,000` replicates, and retain undefined one-class replicates with failure reasons.
- Regenerate figures only after their source CSVs have been saved.
- A clean rerun must be identical except for timestamp-bearing provenance fields; do not initialize Git when repository metadata are invalid.

---

### Task 1: Lock Down Data Contracts and NMS Behavior

**Files:**
- Create: `tests/test_precise_pni_frozen_score_audit.py`
- Create: `models/audit_precise_pni_frozen_scores.py`

**Interfaces:**
- Consumes: pandas data frames matching the clinician export, manifest, and full-score schemas.
- Produces: `normalize_review(review) -> (DataFrame, list[dict])`, `normalize_full_score_header(scores, expected_ids) -> (DataFrame, dict)`, `spatial_nms(scores, distance_fraction=0.75) -> DataFrame`, and `validate_and_merge(review, manifest, nms) -> (DataFrame, list[dict])`.

- [ ] **Step 1: Write failing normalization tests**

  Add tests proving that blank outcomes remain `pd.NA`, blank reviewer IDs become `Song` only in the returned copy, source data are unchanged, malformed full-score first-column headers are accepted only when their values reconcile to manifest image IDs, and duplicate candidate/review-order records raise `AuditIntegrityError`.

- [ ] **Step 2: Run normalization tests and verify RED**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k 'normalize or duplicate' -v`

  Expected: import or missing-symbol failure because the audit module does not exist.

- [ ] **Step 3: Implement normalization and integrity-event records**

  Implement canonical whitespace/lowercase normalization only for analytic label columns while retaining verbatim copies as `<field>_source`; never map missing values to `no`. Define integrity records with `check`, `status`, `severity`, `n_affected`, and `details`, including the anomalous full-score header.

- [ ] **Step 4: Run normalization tests and verify GREEN**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k 'normalize or duplicate' -v`

  Expected: all selected tests pass.

- [ ] **Step 5: Write failing NMS and reconciliation tests**

  Use literal coordinates to prove that distance strictly below `0.75 * window_px` is suppressed, equality is retained, descending combined score controls retention, `nms_rank` is assigned after suppression, and a score/coordinate/stratum mismatch raises `AuditIntegrityError`.

- [ ] **Step 6: Run NMS tests and verify RED**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k 'nms or reconcile' -v`

  Expected: missing-symbol failures for NMS/reconciliation functions.

- [ ] **Step 7: Implement exact NMS reconstruction and fail-closed merge**

  Copy the original geometric comparison semantics, add deterministic `nms_rank`, derive `subject_id` with `image_id.rsplit("_", 1)[0]`, require one-to-one reviewed-manifest identity/geometry matching, and compare score/rank columns with exact or `1e-12` floating tolerance as appropriate.

- [ ] **Step 8: Run the full Task 1 tests**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k 'normalize or duplicate or nms or reconcile' -v`

  Expected: all selected tests pass.

### Task 2: Implement Capture, Coverage, and Score Endpoints

**Files:**
- Modify: `tests/test_precise_pni_frozen_score_audit.py`
- Modify: `models/audit_precise_pni_frozen_scores.py`

**Interfaces:**
- Consumes: reconciled reviewed candidates plus the full NMS-ranked universe.
- Produces: `compute_budget_capture(audit, nms, max_k=10) -> DataFrame`, `compute_score_metrics(audit) -> DataFrame`, `compute_subtype_and_stratum(audit) -> DataFrame`, and `build_error_review(audit) -> DataFrame`.

- [ ] **Step 1: Write failing endpoint tests**

  Create a two-slide literal fixture where one top-ranked candidate is unreviewed. Assert exact captured-positive counts, Clopper-Pearson limits, coverage denominators, missing `top_k_precision` below 100% evaluable coverage, valid precision only at full coverage, separated touching/surrounding curves, and stratum counts.

- [ ] **Step 2: Run endpoint tests and verify RED**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k 'budget or metrics or subtype or error' -v`

  Expected: missing endpoint functions.

- [ ] **Step 3: Implement endpoint functions**

  Calculate PNI, nerve, touching, and surrounding focus capture from confirmed reviewed positives only; calculate coverage against all NMS top-k candidates; use `scipy.stats.beta` for exact binomial intervals; compute ROC AUC and average precision for raw prototype, text-PNI, nerve, and frozen combined scores against evaluable `pni_present`; and generate deterministic error categories without invented histology.

- [ ] **Step 4: Run endpoint tests and verify GREEN**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k 'budget or metrics or subtype or error' -v`

  Expected: all selected tests pass.

### Task 3: Implement Subject-Cluster Bootstrap and Summaries

**Files:**
- Modify: `tests/test_precise_pni_frozen_score_audit.py`
- Modify: `models/audit_precise_pni_frozen_scores.py`

**Interfaces:**
- Consumes: reconciled audit data, fixed `seed`, and replicate count.
- Produces: `cluster_bootstrap(audit, seed, n_replicates, max_k=10) -> DataFrame` and `attach_bootstrap_summary(point_tables, replicates) -> tuple[DataFrame, DataFrame]`.

- [ ] **Step 1: Write failing bootstrap tests**

  Use three literal subjects to assert identical outputs from repeated calls with the same seed, subject-level rather than row-level resampling, retained rows for undefined one-class AUC/AP replicates, explicit `valid=False` and `failure_reason=single_outcome_class`, and valid/undefined counts that sum to the requested replicates.

- [ ] **Step 2: Run bootstrap tests and verify RED**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k bootstrap -v`

  Expected: missing bootstrap functions.

- [ ] **Step 3: Implement deterministic long-form replicate output**

  Resample unique subjects with replacement, attach cluster draw IDs so duplicated subjects contribute duplicated clusters, calculate all four capture endpoints for `k=1..10` plus AUC/AP for four scores, and emit one row per replicate/metric with estimate, validity, and failure reason.

- [ ] **Step 4: Implement percentile CI and failure accounting**

  Summarize only valid finite estimates for percentile bounds while reporting `n_bootstrap_requested`, `n_bootstrap_valid`, `n_bootstrap_undefined`, and `bootstrap_undefined_fraction` without deleting failed replicate rows.

- [ ] **Step 5: Run bootstrap and full unit tests**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -v`

  Expected: all tests pass.

### Task 4: Build the Reproducible Entry Point and Required Artifacts

**Files:**
- Modify: `models/audit_precise_pni_frozen_scores.py`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/normalized_review.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/data_integrity_report.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/candidate_audit_table.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/review_budget_capture.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/score_metric_summary.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/cluster_bootstrap_replicates.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/subtype_and_stratum_summary.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/error_review_table.csv`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/run_config.json`
- Create at runtime: `opendataset/PRECISE/pni_frozen_score_audit/RESULTS_REPORT.md`
- Create at runtime: four required PNG/PDF figures.

**Interfaces:**
- Consumes: the five fixed inputs and the original NMS implementation for provenance.
- Produces: `run_audit(output_dir, seed=20260805, n_bootstrap=10000) -> dict` and CLI `main()`.

- [ ] **Step 1: Write a failing end-to-end fixture test**

  Invoke `run_audit` on temporary fixture CSV/JSON files and assert the required filenames exist, plots are generated after their CSV inputs, output hashes exclude `run_config.json` to avoid self-reference, and the source-review hash is unchanged.

- [ ] **Step 2: Run the end-to-end test and verify RED**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -k end_to_end -v`

  Expected: missing entry-point behavior.

- [ ] **Step 3: Implement ordered output generation**

  Hash inputs before parsing; validate and analyze; write CSVs with stable row/column ordering and explicit missing values; read saved CSVs back for plotting; write a cautious report whose numeric claims reference output tables; record UTC execution time, command parameters, platform/Python/package versions, Git-unavailable state, input hashes, source-review pre/post hashes, and output hashes in `run_config.json`.

- [ ] **Step 4: Implement figures from saved tables**

  Plot the four capture curves with observed estimates and bootstrap intervals from `review_budget_capture.csv`; plot reviewed-sample PNI-positive versus PNI-negative distributions for the four scores from `candidate_audit_table.csv`. Save deterministic PNG metadata and PDF metadata to prevent timestamp-only binary drift.

- [ ] **Step 5: Run the end-to-end and full unit test suite**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -v`

  Expected: all tests pass.

### Task 5: Execute the Real Audit and Verify Reproducibility

**Files:**
- Regenerate: all files under `opendataset/PRECISE/pni_frozen_score_audit/`

**Interfaces:**
- Consumes: the completed entry point and fixed real inputs.
- Produces: verified final audit artifacts and an evidence-backed handoff.

- [ ] **Step 1: Record the source hash and execute the full audit**

  Run: `sha256sum 'opendataset/PRECISE/precise_pni_review (1).csv' && .venv/bin/python models/audit_precise_pni_frozen_scores.py`

  Expected: exit 0 after all reconciliation gates, 10,000 bootstrap replicates, tables, report, and figures.

- [ ] **Step 2: Run all related tests fresh**

  Run: `.venv/bin/python -m pytest tests/test_precise_pni_frozen_score_audit.py -v`

  Expected: zero failures.

- [ ] **Step 3: Verify required files and internal counts**

  Run a read-only verification script that checks 13 required output filenames, 120 normalized/audit rows, 2,264 full candidates, 624 NMS-retained candidates, 19 slides, 18 subjects, 14 nerve positives, 7 PNI positives, subtype counts 4 touching/3 surrounding, and no reported precision where coverage is below 100%.

- [ ] **Step 4: Verify clean-rerun determinism**

  Save hashes and normalized `run_config.json` with timestamp fields removed, rerun the single entry point, then compare every CSV, Markdown report, figure, and normalized configuration hash. Confirm the clinician source hash is unchanged before and after both runs.

- [ ] **Step 5: Re-read the design and inspect the report language**

  Check every design verification criterion and search the report for prohibited interpretations. Confirm that any top-4 statement is explicitly retrospective/descriptive and that the report distinguishes raw `image_rank` from post-NMS `nms_rank`.

- [ ] **Step 6: Report Git state without mutation**

  Run: `git rev-parse --is-inside-work-tree`

  Expected: if invalid, report that commits were impossible and do not run `git init`.
