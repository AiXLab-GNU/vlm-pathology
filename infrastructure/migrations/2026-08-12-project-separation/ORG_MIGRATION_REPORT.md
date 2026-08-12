# ORG-M0–M5 project-separation and root-normalization report

Date: 2026-08-12
Owner: Jin Hyun Kim (PM)
Status: complete

## Outcome

The former mixed workspace is now organized around three canonical project roots:

- `projects/precise_pni_candidate_triage/`
- `projects/quantitative_foundation_model_validation/`
- `projects/prostate_biomarker_validation/`

The biomarker manuscript and its source tables belong to the biomarker project. PNI
candidate-triage code, protocols, and tests belong to the PNI project. Quantitative metric
taxonomy, P0 governance, and FM bundles belong to the quantitative project.

The repository root is closed. It contains only `projects/`, `resources/`,
`infrastructure/`, seven required tool/runtime dot-directories, and seven registered root
files. All former generic research roots and compatibility aliases were removed. The
mandatory placement contract is
`infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md`.

## Inventory and reconciliation

- Pre-migration inventory: 1,351 managed files; 5 required ownership review.
- ORG-M4 post-migration inventory: 671 managed, non-cache files; 0 unresolved.
- ORG-M5 root-normalization inventory: 682 managed, non-cache files; 0 unresolved.
- The 57-GB local model workspace, environments, third-party trees, caches, archives, and
  large generated products are excluded from the managed-file denominator. Their canonical
  owners are recorded in `resources/RESOURCE_OWNERSHIP.csv`.
- The immutable PNI clinician source retained SHA-256
  `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.

The count reduction is not deletion. Large ignored resources were physically retained and
assigned to a named project or explicit shared scope.

## Root normalization and provenance

Legacy root entries `models`, `paper`, `studies`, `docs`, `scripts`, `packages`, `shared`,
`data`, `artifacts`, `opendataset`, `song-datasets`, `local-data`, `model-weights`,
`reorganization`, and the paper backup root no longer exist. Code, tests, imports, service
entry points, and internal model-workspace symlinks now use canonical project/resource
paths. This prevents new files from silently accumulating in a compatibility tree.

Historical governance records and frozen result payloads were not rewritten. Old absolute
or logical paths inside them remain provenance, not current ownership declarations. Where
an immutable R1 manifest refers to the historical `models/...` namespace, a narrow runtime
lineage resolver maps that frozen string to the canonical resource path without creating a
filesystem alias.

The exhaustive root registry is
`infrastructure/docs/repository/ROOT_DIRECTORY_REGISTRY.csv`; the old-to-new mapping is
`ROOT_MIGRATION_MAP.csv`; local-resource ownership is
`resources/RESOURCE_OWNERSHIP.csv`.

## Verification

- Project-boundary and exact root-registry validator: PASS
- Worktree registry audit: PASS; 0 unregistered worktrees
- Repository integration tests: 2 passed
- PNI focused tests: 37 passed
- Quantitative focused tests: 30 passed
- Shared metric package tests: 14 passed
- Broken symbolic links: 0
- Post-normalization inventory: 682 files; 0 unresolved
- Biomarker full suite: 322/323 passed. The sole failure is the pre-existing mismatch
  between a historical ICT funding phrase expected by the test and the user-edited current
  NRF/GNU funding declaration; the user-authored declaration was preserved.
- Governance portal: canonical entry point, `127.0.0.1:8011` loopback-only service

## Lessons and remaining technical debt

- Sharing PRECISE images does not permit PNI review labels to become a quantitative-study
  endpoint. Dataset location and scientific truth ownership remain separate.
- Frozen records may retain an old logical path after physical migration; this does not
  require a root-level compatibility alias. A narrow resolver at the lineage boundary is
  safer and keeps the root closed.
- Git-ignored assets still need explicit scientific ownership. The resource registry
  prevents a generic data/model folder from becoming an implicit fourth project.
- Biomarker analysis code remains under `code/legacy/`, but imports and executable paths
  use its canonical project namespace. Extraction into shared packages should occur only
  after tests establish identical scientific assumptions.
- Repository reorganization does not expand any clinical, encoder-superiority, robustness,
  confirmatory-target, or H2 claim boundary.

## Audit artifacts

- `pre_migration_file_inventory.csv`
- `pre_migration_project_classification.csv`
- `post_migration_file_inventory.csv`
- `post_migration_project_classification.csv`
- `post_root_normalization_file_inventory.csv`
- `post_root_normalization_project_classification.csv`
- `post_root_normalization_unresolved_files.csv`
- `ROOT_MIGRATION_MAP.csv`
- `immutable_inputs.csv`
- `running_services.csv`
- `infrastructure/scripts/validate_project_boundaries.py`
- `infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md`
- `infrastructure/docs/repository/ROOT_DIRECTORY_REGISTRY.csv`
- `resources/RESOURCE_OWNERSHIP.csv`
- `.worktrees/README.md`
- `.worktrees/registry.csv`
- `infrastructure/scripts/audit_worktrees.py`
