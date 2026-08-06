# CLAUDE.md

Read `AGENTS.md` completely before work. It is the shared project policy and
the authoritative repository-level instruction file.

## Critical project rules

- This is a pathology research repository. The current frozen CONCH system is
  a PNI candidate-triage tool, not a validated whole-slide diagnostic system.
- Read the applicable approved design in `docs/superpowers/specs/` before
  implementing or changing an analysis.
- Never edit the immutable clinician source
  `opendataset/PRECISE/precise_pni_review (1).csv`. Verify its SHA256 before and
  after analyses.
- Do not change frozen model scores, prompts, exemplars, score weights,
  coordinates, windows, or spatial NMS semantics during the frozen audit.
- Missing, blank, uncertain, and not-evaluable fields remain missing or
  explicitly non-evaluable; never infer `no`.
- Unreviewed top-k candidates are not negatives, and precision requires 100%
  evaluable-label coverage for the relevant budget.
- Keep and count bootstrap failures rather than dropping single-class
  replicates.

## Blinded morphology review

- The morphology pilot includes all 14 previously nerve-positive PRECISE
  candidates.
- Hide previous labels, confidence, model scores, ranks, strata, and
  provisional nerve circles during the primary review.
- Lock structured morphology labels before drawing or approving nerve
  contours.
- Do not infer population morphology distributions, prognosis, or AI
  morphology-classification accuracy from these 14 selected foci.

## Reproducibility and verification

- Use `.venv/bin/python`.
- Use fixed seeds, input/output hashes, environment versions, integrity
  reports, and timestamp-excepted clean-rerun comparisons.
- Generate figures from saved CSVs.
- Run the relevant test suite and syntax checks fresh before completion.
- Stop on candidate, manifest, coordinate, score, or NMS reconciliation
  failures instead of guessing.

Focused test command:

```bash
.venv/bin/python -m unittest tests.test_precise_pni_frozen_score_audit -v
```

## Git safety

- `opendataset/`, `song-datasets/`, WSI, model weights, arrays, virtual
  environments, caches, and generated results are intentionally Git-ignored.
- Never use broad staging in this approximately 79 GB workspace. Stage only
  explicit source and documentation paths, inspect the staged diff, and scan
  for credential-like content before committing.
- Do not configure a remote, push, publish, or initialize Git LFS unless the
  user explicitly requests it.
