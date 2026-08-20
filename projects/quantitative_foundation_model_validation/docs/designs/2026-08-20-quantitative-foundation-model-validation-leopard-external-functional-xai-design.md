---
document_id: 2026-08-20-quantitative-foundation-model-validation-leopard-external-functional-xai-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: approved
created: 2026-08-20
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-08-20-quantitative-foundation-model-validation-leopard-external-functional-xai-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm6_external_functional_validation
  - resources/artifacts/quantitative_foundation_model_validation/fm6_external_functional_validation
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm6_leopard_external_functional_xai -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
---

# FM6 LEOPARD external functional XAI validation design

## 1. Decision and authorization

The accountable author confirmed on 2026-08-20 that the LEOPARD publication embargo has
ended and authorized its use for manuscript resubmission. The repository dataset manifest
records that confirmation and also records that an external documentary clearance artifact
has not been archived. This design does not alter CHIMERA's separate embargo lock.

LEOPARD is selected as the independent external BCR cohort because it contains 508 unique
prostatectomy patients, one WSI per patient, and 87 source-defined BCR events. It does not
provide patient-level ISUP/Gleason labels or treatment covariates. Consequently, it can test
transport of a TCGA-locked functional intervention against external BCR, but cannot test
external ISUP recoverability, endpoint-threshold equivalence, clinical increment, or a
tumor-specific ISUP mechanism.

## 2. Scientific question

Does removing the TCGA-derived ISUP-correlated direction from LEOPARD whole-tissue CONCH or
Virchow representations reduce a fully TCGA-trained, fixed BCR head's discrimination of
LEOPARD BCR more than variance-matched random-direction removal?

No LEOPARD image, representation, event, or follow-up value may select preprocessing,
hyperparameters, subspace rank, direction, head, threshold, control, or analysis universe.

## 3. Fixed source and image boundary

- TCGA development: the existing 392-subject/80-event FM6 source and paired embeddings.
- LEOPARD external test: all 508 labeled cases with one WSI and one supplied tissue mask;
  expected 87 events.
- Physical field of view: 394.24 micrometres, identical for both encoders and TCGA.
- Tissue selection: supplied LEOPARD foreground mask, outcome-blind deterministic sampling.
- Maximum/minimum crops: 64/16 per WSI.
- Canonical decoded crop: 448 by 448 RGB; Virchow receives a deterministic 224 by 224 resize.
- Both encoders consume identical case, coordinate, physical boundary, crop hash, and row order.
- Seed: 260820.

Cases with fewer than 16 eligible tissue crops or a technical decode failure remain explicit
non-evaluable cases. No replacement, favorable subset, or outcome-informed resampling is
allowed.

## 4. Locked head and intervention

For each encoder, the full 392-subject TCGA development representation fits exactly one final
model using fixed parameters inherited from the completed internal pilot:

- StandardScaler fitted on TCGA only;
- PCA rank 64, randomized solver, seed 260820;
- CoxPH ridge alpha 1000;
- ISUP Ridge alpha 1000 fitted in the same TCGA-standardized representation;
- 100 TCGA-training-derived variance-matched random directions.

The unmodified and erased LEOPARD representations are passed through the same fixed scaler,
PCA, and Cox head. No refit on LEOPARD is permitted.

## 5. Estimands and controls

Primary disease-head validity is LEOPARD patient-level Harrell C-index. Primary functional
transport is

`external delta_use = C-index(full fixed head) - C-index(ISUP-erased fixed head)`.

Uncertainty uses 2,000 paired patient bootstrap draws. The target-versus-random one-sided
p-value is `(1 + count(random_delta >= target_delta)) / 101`, Holm-adjusted across CONCH and
Virchow. The internal effect direction must remain positive; no minimum effect-retention
fraction is introduced after observing results.

## 6. Prespecified gate

An encoder passes `EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT` only if:

1. external full-head C-index bootstrap lower bound is greater than 0.50;
2. external targeted `delta_use` bootstrap lower bound is greater than 0;
3. Holm-adjusted target-versus-random one-sided p-value is at most 0.05;
4. all 508 expected cases are evaluable, or any exclusions are technical, outcome-blind, and
   leave at least 80 external events.

Both encoders must pass for `PASS_REPLICATED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT`.
One pass yields `PARTIAL_ENCODER_SPECIFIC_EXTERNAL_FUNCTIONAL_TRANSPORT`; neither yields
`FAIL_OR_INCONCLUSIVE_EXTERNAL_FUNCTIONAL_TRANSPORT`.

## 7. Claim boundary

A positive result establishes independent external BCR transport of whole-tissue functional
sensitivity to a TCGA-derived ISUP-correlated direction. It does not establish external ISUP
recoverability, tumor-specific ISUP use, endpoint-threshold equivalence, clinical incremental
utility, indispensability, a human-equivalent mechanism, residual-marker novelty, or strong
H2. Those states remain not tested or prohibited.

A failed or inconclusive gate is reported without retuning. CHIMERA remains excluded.
