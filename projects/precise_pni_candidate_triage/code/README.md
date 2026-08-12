# PNI candidate-triage code map

This tree contains active code owned only by `precise_pni_candidate_triage`.

- `audit/`: frozen-score audit and evidence regeneration entry points.
- `candidate_generation/`: candidate-universe construction.
- `candidate_visualization/`: review HTML and candidate views.
- `morphology_review/`: blinded rereview interface and review normalization.
- `spatial_analysis/`: contour and spatial pilot analyses.
- `training/`: project-specific training utilities; no clinical claim is implied.

New executable workflows use a verb-prefixed lower-snake-case filename. Shared,
scientifically identical utilities may be promoted to `infrastructure/packages/` only
with tests and an explicit cross-project contract.
