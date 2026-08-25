---
document_id: 2026-08-21-quantitative-foundation-model-validation-chimera-external-functional-xai-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: approved
created: 2026-08-21
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-08-21-quantitative-foundation-model-validation-chimera-external-functional-xai-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-08-21-quantitative-foundation-model-validation-chimera-external-functional-xai-design.md
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm6_chimera_external_functional_validation
  - resources/artifacts/quantitative_foundation_model_validation/fm6_chimera_external_functional_validation
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm6_chimera_external_functional_xai -v
  - .venv/bin/python -m py_compile projects/quantitative_foundation_model_validation/milestones/fm6_chimera_external_functional_validation/run_fm6_chimera_external_functional_xai.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_worktrees.py
  - git diff --check
---

# FM6 CHIMERA external functional XAI implementation plan

## Scope and ordering

1. Commit this approved design, implementation plan, Korean protocol, runner, focused tests,
   and project-sequence registration before producing model/outcome results.
2. Verify the tracked manifest hashes and the complete local 95-subject/190-WSI/190-mask
   membership. Perform one full local-object SHA-256 verification against the immutable source
   inventory.
3. Prepare 64 outcome-blind official-mask crops for every WSI and lock coordinates, decoded-RGB
   hashes, row order, patient linkage, and sampling QC in the ignored artifact root.
4. Select an unused GPU using `nvidia-smi`, set `CUDA_VISIBLE_DEVICES` explicitly, extract
   resumable CONCH and Virchow slide shards, assemble arrays, and pass the paired crop audit.
5. Apply the TCGA-only fixed probe, BCR head, target erasure, 100 matched-random controls, 2,000
   patient bootstraps, Holm adjustment, and cause-state rules once.
6. Repeat the full deterministic analysis into a separate clean-rerun directory and compare all
   nonvolatile output hashes exactly.
7. Run focused tests, syntax checks, governance/boundary/worktree audits, related project tests,
   `git diff --check`, and an explicit manuscript diff check.

## Embargo-controlled output route

All preparation products, canonical crops, embeddings, patient predictions, bootstrap intervals,
random-control tables, summaries, reports, logs, and run configurations are generated only under
`resources/artifacts/quantitative_foundation_model_validation/fm6_chimera_external_functional_validation/`.
No milestone `outputs/` directory is created. No result-lock commit is permitted while the
publication state remains `EMBARGO_ACTIVE_NO_WRITTEN_CLEARANCE`.

## Stop and recovery rules

- Stop before analysis on a source/hash/membership/pairing/MPP/crop/order failure.
- Reuse only validated immutable slide caches; never delete or overwrite a frozen source.
- Diagnose and patch reproducibly if extraction fails, then resume missing shards without
  duplicating rows.
- Do not change a locked setting after reading CHIMERA model results.
- Do not modify the manuscript, submission package, public tag, release, or remote.

## 2026-08-24 completion and aggregate-release amendment

- [x] All 95 subjects, 27 events, 190 WSI, and 12,160 shared whole-tissue crops passed integrity
  checks.
- [x] Both encoders passed external ISUP recoverability.
- [x] CONCH had positive targeted erasure but failed the strict full-head lower-CI gate and closed
  as `FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION`.
- [x] Virchow passed full-head validity, positive targeted erasure, matched-random, and Holm gates
  and closed as `QUALIFIED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT`.
- [x] A clean analysis rerun reproduced all six nonvolatile output hashes exactly.
- [x] The accountable author determined that the embargo had ended and authorized promotion of
  aggregate results only. Patient-level and representation artifacts remain local-only.

The release amendment supersedes the manuscript/output prohibition above but not the locked
analysis or claim boundary. The next action is controlled manuscript integration with both
encoders reported together and no encoder-superiority claim.
