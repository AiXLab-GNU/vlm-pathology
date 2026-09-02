---
document_id: 2026-08-31-quantitative-foundation-model-validation-fm8-tier4-discovery-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: approved
created: 2026-08-31
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-08-31-quantitative-foundation-model-validation-fm8-tier4-discovery-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-08-31-quantitative-foundation-model-validation-fm8-tier4-discovery-design.md
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm8_bcr_tier4_discovery
  - resources/artifacts/quantitative_foundation_model_validation/fm8_bcr_tier4_discovery
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm8_bcr_tier4_discovery -v
  - .venv/bin/python -m py_compile projects/quantitative_foundation_model_validation/code/lib/fm8_tier4.py projects/quantitative_foundation_model_validation/code/entrypoints/run_fm8_bcr_tier4_discovery.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# FM8 Tier 4 discovery implementation plan

## Ordered work

1. Freeze the design, this implementation plan, and the active protocol while retaining the old
   NO-GO audit and report as historical evidence.
2. Audit the TCGA and CHIMERA clinical tables, fixed folds, tile manifests, paired encoder arrays,
   row order, counts, hashes, finite values, and endpoint semantics before model fitting.
3. Write focused tests for projection, source-only selection, patient OOF coverage, external lock,
   bootstrap undefined preservation, endpoint separation, and candidate-role rules.
4. Implement one canonical CLI with `audit`, `run`, and `compare-clean-rerun` stages. The BCR lane
   is the only executable lane; cancer presence and grading emit `NOT READY` readiness rows.
5. Generate deterministic patient representations and color/QC summaries from frozen artifacts,
   retaining patient-level products only in the local resource root.
6. Run nested source OOF analysis separately for CONCH and Virchow, fit final source-only models,
   and apply them unchanged to CHIMERA.
7. Save aggregate performance, bootstrap intervals, fold stability, adjusted latent and interaction
   effects, shortcut audit, endpoint-lane readiness, candidate registry, provenance/hash manifest,
   run configuration, and Korean result report.
8. Repeat the full analysis in a separate run directory and compare protocol-declared nonvolatile
   hashes exactly.
9. Synchronize the project sequence, canonical research plan, milestone log, execution tracker,
   `PROJECT.yaml`, code/docs/report indexes, and claim ceiling without editing paper 1.
10. Run focused tests, syntax checks, row/hash validation, boundary and governance audits,
    worktree audit, and `git diff --check`.

## Long-run record

If the analysis exceeds an interactive run, execute it in tmux and record session name, exact
command, PID, UTC start, log path, GPU use, completion state, and exit code in the run configuration.
The analysis uses frozen embeddings and is CPU-only; no GPU inference is planned.

## Stop and recovery

No failed or undefined result is deleted. A failed integrity check stops before outcome modeling.
A model failure is reported per encoder without substituting the other encoder. CHIMERA results
cannot change configuration. NADT/PANDA remain unexecuted until a QFM-owned or hash-locked shared
immutable manifest, explicit use authorization, patient identity contract, and endpoint-specific
label mapping exist.
