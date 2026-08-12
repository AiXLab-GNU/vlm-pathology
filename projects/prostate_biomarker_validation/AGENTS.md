# Prostate biomarker project instructions

Before creating or moving files, read
`../../infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md` and
`../../infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md` and
`../../infrastructure/docs/repository/FILE_NAMING_CODEX.md` from the repository root. Superpowers
designs/plans for this study belong under this project's `docs/designs/` or `docs/plans/`,
not in a new root folder, and require the structure-Codex metadata header.

- Frozen outputs, endpoints, fold assignments and prespecified analysis families
  must not be silently relabeled, optimized or recalibrated.
- Keep cohort/site/endpoint provenance explicit and preserve undefined or
  underpowered results.
- Internal association is not clinical validation, prognosis or transport.
- Manuscript numbers and figures must be regenerated from saved source tables.
- Patient-level data, embeddings, weights and local caches remain uncommitted.
- Read `00-project-sequence/README.md` before starting a work package and keep its ordered
  stage status synchronized with approved results.
