---
document_id: 2026-08-20-quantitative-foundation-model-validation-leopard-external-functional-xai-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: approved
created: 2026-08-20
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-08-20-quantitative-foundation-model-validation-leopard-external-functional-xai-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-08-20-quantitative-foundation-model-validation-leopard-external-functional-xai-design.md
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm6_external_functional_validation
  - resources/artifacts/quantitative_foundation_model_validation/fm6_external_functional_validation
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm6_leopard_external_functional_xai -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# FM6 LEOPARD external functional XAI implementation plan

## Execution

1. Lock the LEOPARD label hash, WSI/mask membership, byte sizes, TIFF headers, physical
   resolution, and deterministic outcome-blind crop coordinates.
2. Implement tests and one auditable runner with `prepare`, `extract`, `analyze`, and `all`
   stages. Store raw crops, embeddings, and patient predictions only under QFM local artifact
   roots; commit only source, aggregate evidence, and provenance hashes.
3. Commit the authorization record, design, protocol, runner, tests, and prepared coordinate
   manifest before opening external outcome analysis.
4. Extract paired CONCH/Virchow embeddings on identical canonical crops and verify crop hashes,
   membership, row order, finite values, and exact repeat smoke tests.
5. Fit each final head/direction on TCGA only, apply it once to LEOPARD, generate target and
   matched-random effects, bootstrap intervals, and the prespecified gate.
6. Rerun the deterministic analysis stage and require all nonvolatile output hashes to match.
7. Update the manuscript, Supplementary Information, claim matrix, submission handoff, and
   project control chain only to the passed evidence level, then build and QA the revision PDFs.

## Stop rules

- Stop on source/hash/membership/resolution/crop-pair mismatch.
- Stop if fewer than 80 external events remain technically evaluable.
- Never tune on LEOPARD outcomes or use existing PBV LEOPARD embeddings.
- Do not call the result strong H2 or tumor-specific external validation.
