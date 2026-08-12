# PRECISE PNI Morphology Rereview Implementation Plan

> **For Codex:** Execute this plan with `superpowers:executing-plans` and implement each behavior using test-driven development.

**Goal:** Build a reproducible, blinded multiscale H&E rereview package for all 14 PRECISE candidates previously judged nerve-positive, and provide a strict finalize path for a later completed specialist export.

**Architecture:** A single Python entry point has `build` and `finalize` subcommands. `build` derives and validates the fixed 14-case set from immutable source inputs, assigns deterministic temporary IDs, embeds three centered H&E fields in a standalone HTML reviewer, and writes a private mapping, blank response template, integrity report, and provenance configuration. `finalize` validates a completed blinded export without coercing missing values, reports logical conflicts, and joins identities only into private locked outputs.

**Tech stack:** Python 3, pandas, NumPy, tifffile/zarr, Pillow, standalone HTML/CSS/JavaScript, unittest.

---

## Task 1: Define and test the fixed blinded review set

**Files:**
- Create: `tests/test_precise_pni_morphology_review.py`
- Create: `projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py`

1. Add failing tests for deriving exactly the source rows with `nerve_present=yes`, rejecting non-14 case counts, duplicate candidate IDs, and source/manifest geometry disagreement.
2. Run the focused unittest file and confirm failure because the module/API is absent.
3. Implement source loading, immutable-input SHA256 helpers, fixed-set validation, and deterministic seeded temporary-ID assignment.
4. Re-run focused tests and retain no original label, score, rank, stratum, subject, slide, or coordinate fields in the public case records.

## Task 2: Build and test multiscale H&E rendering

**Files:**
- Modify: `tests/test_precise_pni_morphology_review.py`
- Modify: `projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py`

1. Add failing tests for centered 300/600/1200 µm crop geometry, white edge padding, deterministic case order, and HTML-source blinding.
2. Confirm the new tests fail for the intended missing behavior.
3. Implement WSI resolution, crop extraction, JPEG embedding, and a standalone HTML interface with no overlays or prior annotations.
4. Implement the approved morphology fields: nerve presence, PNI certainty, overall relation, touching/surrounding/intraneural components, orientation, longitudinal tracking, branch point, multiplicity, field adequacy, confidence, and notes.
5. Add local autosave, completion display, JSON import/backup, and blinded CSV export keyed only by temporary case ID.
6. Re-run focused tests.

## Task 3: Add reproducible build outputs and integrity checks

**Files:**
- Modify: `tests/test_precise_pni_morphology_review.py`
- Modify: `projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py`

1. Add failing tests for the private mapping schema, blank response schema, build integrity rows, run configuration, input/output hashes, fixed seed, environment versions, and timestamp-isolated reproducibility.
2. Implement atomic output generation in `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/`:
   - `precise_pni_morphology_review.html`
   - `private_case_mapping.csv`
   - `morphology_review_template.csv`
   - `build_integrity_report.csv`
   - `run_config.json`
   - `README.md`
3. Ensure config output hashes exclude `run_config.json` itself and that reruns differ only in execution timestamp fields.
4. Re-run focused tests.

## Task 4: Implement and test strict finalization

**Files:**
- Modify: `tests/test_precise_pni_morphology_review.py`
- Modify: `projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py`

1. Add failing tests for allowed values, unknown/missing/duplicate temporary IDs, preservation of blank responses, and explicit logical-conflict reporting without automatic correction.
2. Confirm failures, then implement `finalize --completed-review ...`.
3. Generate only when a completed export is supplied:
   - `normalized_morphology_review.csv`
   - `morphology_data_integrity_report.csv`
   - `morphology_transition_table.csv`
   - `contour_eligibility_table.csv`
   - `MORPHOLOGY_RESULTS_REPORT.md`
4. Keep new morphology results descriptive; do not estimate prevalence, sensitivity, prognosis, or population morphology distributions.
5. Re-run focused tests.

## Task 5: Execute the real build and verify deliverables

**Files:**
- Generate ignored outputs under `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/`

1. Run the complete test suite with `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`.
2. Run the build command against the immutable clinician review, 120-case manifest/audit table, and PRECISE H&E WSIs.
3. Verify there are exactly 14 temporary cases from 10 slides/subjects, all required WSI inputs exist, all output hashes validate, and the original clinician CSV SHA256 is unchanged before/after.
4. Perform a clean rerun in a temporary directory and compare all non-timestamp content and hashes.
5. Scan the public HTML and blank template for all original candidate IDs, slide/subject IDs, prior labels, scores, ranks, strata, coordinates, and prohibited interpretation text; fail if any leak is found.
6. Record actual file sizes and verification evidence. Do not run `finalize` with fabricated specialist labels.

## Task 6: Review, commit, and hand off

1. Inspect the exact diff and generated-output inventory.
2. Re-run fresh verification according to `superpowers:verification-before-completion`.
3. Commit only the explicit source, test, and plan files on the feature branch; do not add ignored clinical data or generated review images.
4. Report the commit, review package path, exact case/slide/subject counts, how to open/export it, remaining specialist action, and the fact that quantitative morphology conclusions await completed rereview.
