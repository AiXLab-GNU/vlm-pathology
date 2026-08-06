# AGENTS.md

## Project purpose

This repository develops reproducible pathology-VLM workflows, currently
focused on PRECISE prostate cancer perineural invasion (PNI). The validated AI
role is candidate triage: rank spatially distinct regions for pathologist
review. Do not describe the current system as a whole-slide PNI diagnostic
classifier or as clinically validated.

## Instruction and design precedence

1. Follow the user's current request and this file.
2. Read the applicable approved design under `docs/superpowers/specs/`
   completely before implementation.
3. For the frozen-score audit, the controlling design is
   `docs/superpowers/specs/2026-08-05-precise-pni-frozen-score-audit-design.md`.
4. For morphology re-review, the controlling design is
   `docs/superpowers/specs/2026-08-06-precise-pni-morphology-rereview-design.md`.
5. Do not redesign an approved study unless the user explicitly requests a
   design change.

## Immutable inputs and scientific boundaries

- Treat `opendataset/PRECISE/precise_pni_review (1).csv` as the immutable final
  clinician source. Never edit it. Its expected SHA256 is
  `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.
- Populate a missing reviewer ID such as `Song` only in explicitly derived
  normalized outputs.
- Never convert a missing, blank, uncertain, or not-evaluable outcome to `no`.
- Do not retrain, recalibrate, optimize, or relabel frozen scores, prompts,
  exemplars, weights, coordinates, or windows during a frozen audit.
- Reproduce the original spatial NMS logic exactly. Stop and report if the
  reconstructed candidate universe or manifest does not reconcile.
- Unreviewed candidates are not negatives. Calculate top-k precision only when
  every candidate in that budget has an evaluable label.
- Candidate-level ROC-AUC and average precision apply only to the selected,
  stratified reviewed sample.
- Keep undefined bootstrap replicates and report their count and fraction.
- Use no population-prevalence, whole-slide-sensitivity, prognostic, or
  external-validation claim unless a separately approved study supports it.

## Morphology re-review boundaries

- The fixed morphology pilot contains all 14 previously nerve-positive
  PRECISE candidates.
- The primary re-review is blinded to previous labels, confidence, model
  scores, strata, ranks, and provisional nerve circles.
- Record `uncertain` and `not_evaluable` explicitly.
- Morphology labels are completed and locked before pathologist-drawn contours.
- The 14 selected foci cannot estimate the distribution of PNI morphologies in
  PRECISE patients.

## Reproducibility requirements

- Prefer one auditable entry-point script per analysis.
- Use fixed random seeds and record them in run configuration files.
- Record input hashes, source pre/post hashes, software versions, execution
  time, and non-self-referential output hashes.
- Generate figures from saved CSV source tables, not transient in-memory-only
  results.
- A clean rerun must be identical except for explicitly documented timestamp
  fields.
- Preserve missing values and report integrity issues instead of silently
  repairing meaning-changing discrepancies.

## Python and verification

Use the existing workspace environment:

```bash
.venv/bin/python
```

Focused frozen-audit tests:

```bash
.venv/bin/python -m unittest tests.test_precise_pni_frozen_score_audit -v
```

Syntax check modified Python files with `.venv/bin/python -m py_compile`.
Before claiming completion, run fresh tests, validate expected output files and
counts, and confirm immutable source hashes.

## Git and data policy

- `opendataset/`, `song-datasets/`, WSI, arrays, model weights, virtual
  environments, caches, and generated audit outputs are local and must not be
  committed.
- Do not use broad staging commands such as `git add .` or `git add -A` in this
  large mixed workspace. Stage an explicit path allowlist and inspect the
  staged names, sizes, and diff before committing.
- Never commit tokens, credentials, private keys, or machine-specific secrets.
- Do not create remotes, push, publish, or configure Git LFS without explicit
  user authorization.
