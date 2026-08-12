# PNI project instructions

Before creating or moving files, read
`../../infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md` and
`../../infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md` and
`../../infrastructure/docs/repository/FILE_NAMING_CODEX.md` from the repository root. This project
owns only PNI candidate-triage materials; Superpowers designs/plans must be written under
this project's `docs/designs/` or `docs/plans/` with the required metadata header.

- Immutable clinician source:
  `resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv`, expected SHA-256
  `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.
- Never edit the source or turn missing, uncertain or not-evaluable labels into
  `no`. Add missing reviewer IDs only in explicit derived normalized outputs.
- Never retrain, recalibrate, optimize or relabel frozen scores, prompts,
  exemplars, weights, coordinates or windows during a frozen audit.
- Reproduce spatial NMS exactly and stop if the candidate universe does not
  reconcile. Unreviewed candidates are not negatives.
- The morphology pilot is the fixed set of 14 previously nerve-positive
  candidates. Primary review is blinded to previous labels, confidence, scores,
  strata, ranks and provisional circles. Lock morphology before contours.
- Do not make population-prevalence, whole-slide-sensitivity, prognostic,
  external-validation or clinical claims from these selected candidates.

Approved study designs are stored under `docs/designs/` in this project.
Read `00-project-sequence/README.md` before selecting a stage and keep its status synchronized
with approved milestone results.
