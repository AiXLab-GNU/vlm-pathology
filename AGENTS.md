# AGENTS.md

## Repository purpose

This repository is a portfolio of independent pathology-VLM studies. Work must
be attributed to exactly one project unless it is genuinely reusable
infrastructure. Sharing a cohort does not merge scientific questions, labels,
governance records, or claims.

## Mandatory structure policy

Before creating, moving, renaming, or generating any file, read
`infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md` and
`infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md` and
`infrastructure/docs/repository/FILE_NAMING_CODEX.md` completely. Route the file to one owning
project, assign its file class and lifecycle, or use an explicitly permitted shared root. Do not create a new top-level directory,
generic `results`/`output`/`misc` tree, or compatibility-path file unless that Codex is
first amended.

Superpowers workflows do not own a directory. Route their project designs and plans to the
owning project's `docs/designs/` and `docs/plans/`; reserve `infrastructure/docs/superpowers/` for
repository-wide designs and plans. Use the required metadata header template. Auxiliary
Git worktrees must follow the `.worktrees/<project_id>/<slug>/` registry policy in the
Codex.

## Project routing

- PNI candidate triage: `projects/precise_pni_candidate_triage/AGENTS.md`
- Quantitative foundation-model validation:
  `projects/quantitative_foundation_model_validation/AGENTS.md`
- Prostate biomarker validation:
  `projects/prostate_biomarker_validation/AGENTS.md`

Read the applicable project instructions and approved design completely before
changing a study. Repository engineering designs remain under
`infrastructure/docs/superpowers/`. Do not redesign approved science unless the user explicitly
requests it.

At project entry, read `projects/<project_id>/00-project-sequence/README.md` to identify the
current stage and next gate. Update that ordered index when a stage is added, completed, or
reopened; do not renumber canonical executable directories.

## Cross-project boundaries

- A project may depend on `infrastructure/packages/`, `infrastructure/shared/`, and registered local assets.
- A project must not read another project's generated `outputs/` as an implicit
  input. Promote a genuinely shared immutable asset into a hash-locked shared
  manifest first.
- Keep protocol, approvals, results, paper, tests and claim-evidence records
  inside the owning project.
- Do not describe PNI candidate triage as whole-slide diagnosis or clinical
  validation.
- Do not interpret quantitative concept recoverability as disease prediction
  or functional utilization.

## Reproducibility

- Prefer one auditable entry point per analysis.
- Use fixed seeds and save input/output hashes, versions and execution time.
- Generate figures from saved source tables.
- Preserve missing/uncertain/not-evaluable values and report integrity errors.
- A clean rerun may differ only in explicitly documented volatile fields.
- After file creation or movement, run
  `.venv/bin/python infrastructure/scripts/audit_file_governance.py` in addition to the
  repository boundary validator.

## Python and data policy

Use `.venv/bin/python`. Before completion, run focused tests, syntax checks and
immutable-source hash checks. `resources/data/shared/opendataset/`, `resources/data/shared/song-datasets/`, `resources/data/prostate_biomarker_validation/local-data/`,
`resources/projects/prostate_biomarker_validation/model_workspace/`, `resources/artifacts/`, WSI, arrays, weights, caches and generated
outputs are local and must not be committed. Never use broad Git staging, and
never publish or configure remotes/LFS without explicit authorization.
