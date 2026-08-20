---
document_id: 2026-08-20-quantitative-foundation-model-validation-site-heldout-functional-xai-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: approved
created: 2026-08-20
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-08-20-quantitative-foundation-model-validation-site-heldout-functional-xai-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-08-20-quantitative-foundation-model-validation-site-heldout-functional-xai-design.md
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm6_site_heldout_functional_validation
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm6_site_heldout_functional_xai -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# FM6 site-held-out functional XAI implementation plan

## Scope

Implement and execute the approved TCGA tissue-source-site-held-out functional sensitivity
analysis without opening CHIMERA outcomes or importing LEOPARD outcomes into this analysis
family. Existing FM6 embeddings are
immutable inputs; new generated products belong to
`milestones/fm6_site_heldout_functional_validation/outputs/`.

## Execution

1. Audit the 392-subject source, paired embedding identity, site counts, event counts, and
   eligible evaluation sites.
2. Implement one auditable runner using the fixed model, erasure, random-control, bootstrap,
   and evidence-gate rules in the approved design.
3. Add focused tests for site parsing, eligibility, stratified concordance, immutable input
   checks, and generated-output hashes.
4. Commit the protocol, design, plan, runner, and tests before executing the outcome family.
5. Run both encoders, generate all subject/site/control/interval/evidence outputs, and rerun
   once to verify nonvolatile output hashes.
6. Update the project sequence, canonical research-plan chain, claim boundaries, manuscript,
   Supplementary Information, and submission handoff only to the evidence level actually
   passed.
7. Build and QA the revision PDFs, then lock the revision evidence with a targeted commit.

## Stop rules

- Stop if the paired embedding audit or source universe hash differs from the completed FM6
  pilot.
- Do not replace the prespecified sites, hyperparameters, random-control family, or gate after
  results are available.
- Do not use CHIMERA outcomes. LEOPARD belongs only to its separately approved external
  functional-validation workstream.
- If both encoders fail the gate, report the result and retain the external-functional claim
  ceiling.
