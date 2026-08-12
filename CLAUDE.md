# CLAUDE.md

Read `AGENTS.md`, `infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md`, and
`infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md`, and
`infrastructure/docs/repository/FILE_NAMING_CODEX.md` completely before work.
Then read the `AGENTS.md` inside the project that owns the task. These files are the
authoritative scientific, safety, and file-placement policies.
Use that project's `00-project-sequence/README.md` as the ordered navigation surface for
the current stage and next gate.

## File creation and workflow control

- Assign every new file to one project or an approved infrastructure/shared/repository root before
  creating it. Do not create unregistered top-level, generic result, backup, or duplicate
  documentation trees.
- Superpowers project designs and plans belong in the owning project's `docs/designs/` and
  `docs/plans/`; `infrastructure/docs/superpowers/` is repository-wide only. Use the required metadata
  header template in `infrastructure/docs/repository/templates/`.
- Auxiliary worktrees belong under `.worktrees/<project_id>/<slug>/`, require a registry
  row and project-scoped branch, and must be removed with Git rather than filesystem
  deletion.
- Removed root paths such as `models`, `paper`, and the old quantitative `studies/...`
  tree must not be recreated as aliases or destinations.

## Scientific and data safety

- Never edit immutable clinical sources or silently change frozen labels, scores, prompts,
  weights, coordinates, windows, folds, or endpoint definitions.
- Preserve missing, uncertain, and not-evaluable states; never infer a negative label.
- Do not describe PNI candidate triage as whole-slide diagnosis or clinical validation.
- Do not interpret quantitative concept recoverability as disease prediction, functional
  utilization, encoder superiority, or external robustness.
- Keep datasets, WSI, patient-level data, arrays, weights, environments, caches, and
  generated local outputs out of Git.

## Verification and Git

Use `.venv/bin/python`, fixed seeds, hashes, saved source tables, and the owning project's
tests. Before completion run the repository boundary validator, file-governance auditor,
and `git diff --check`.
Never use broad staging. Do not create a remote, push, publish, or configure Git LFS
without explicit user authorization.
