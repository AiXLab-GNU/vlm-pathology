---
document_id: fm6-leopard-external-functional-xai-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: generated
created: 2026-08-20
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_external_functional_validation/outputs/fm6-leopard-external-functional-xai-report.md
---

# FM6 LEOPARD external functional XAI validation

## Evidence scope

This analysis applies TCGA-only locked heads and ISUP-correlated directions to the independent-patient LEOPARD BCR cohort. LEOPARD lacks ISUP and treatment covariates, and its outcomes were accessed in an earlier directionally reversed analysis in this research program; this is a newly locked external reanalysis rather than a prospectively untouched confirmation. External ISUP recoverability, tumor-specific use, endpoint-threshold equivalence, clinical increment, and strong H2 therefore remain unestablished.

- External subjects/events: 508/87
- Overall prespecified status: **FAIL_OR_INCONCLUSIVE_EXTERNAL_FUNCTIONAL_TRANSPORT**

## Prespecified results

### conch

- External full-head C-index: 0.517 (95% CI 0.449–0.590)
- Target-erased C-index: 0.479
- External delta_use: 0.038 (95% CI 0.014–0.066)
- Matched-random p95: 0.011; one-sided p=0.0099; Holm p=0.0198
- Encoder gate: FAIL_OR_INCONCLUSIVE

### virchow

- External full-head C-index: 0.457 (95% CI 0.386–0.528)
- Target-erased C-index: 0.455
- External delta_use: 0.002 (95% CI -0.008–0.011)
- Matched-random p95: 0.004; one-sided p=0.2277; Holm p=0.2277
- Encoder gate: FAIL_OR_INCONCLUSIVE

## Locked interpretation

The prespecified result is reported without target-cohort tuning. A positive gate supports independent-patient external BCR transport of whole-tissue functional sensitivity only. It does not establish a prospectively untouched confirmation, strong H2, or a tumor-specific human-equivalent mechanism.
