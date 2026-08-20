---
document_id: fm6-site-heldout-functional-xai-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: generated
created: 2026-08-20
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_site_heldout_functional_validation/outputs/fm6-site-heldout-functional-xai-report.md
---

# FM6 site-held-out functional XAI validation

## Evidence scope

This is TCGA tissue-source-site-held-out internal transport evidence. It is not an independent external-cohort validation, tumor-specific mechanism, clinical validation, or biomarker discovery result.

- Evaluation sites: EJ, G9, HC, J4, KK, V1, YL
- Held-out subjects/events: 289/69
- Overall prespecified status: **PARTIAL_ENCODER_SPECIFIC_SITE_HELDOUT_EVIDENCE**

## Prespecified results

### conch

- Site-held-out ISUP Spearman: 0.625
- Full-head stratified C-index: 0.612 (95% CI 0.524–0.696)
- Target-erased stratified C-index: 0.565
- Targeted delta_use: 0.048 (95% CI -0.005–0.102)
- Matched-random p95: 0.012; one-sided p=0.0099; Holm p=0.0198
- Positive site-specific deltas: 7/7
- Encoder gate: FAIL_OR_INCONCLUSIVE

### virchow

- Site-held-out ISUP Spearman: 0.665
- Full-head stratified C-index: 0.588 (95% CI 0.514–0.665)
- Target-erased stratified C-index: 0.555
- Targeted delta_use: 0.033 (95% CI 0.007–0.060)
- Matched-random p95: 0.005; one-sided p=0.0099; Holm p=0.0198
- Positive site-specific deltas: 6/7
- Encoder gate: PASS

## Interpretation boundary

The result is locked without retuning. Even a positive gate supports only multi-site held-out whole-tissue functional sensitivity within TCGA. CHIMERA remains excluded; LEOPARD independent external analysis is assessed separately, and this result alone does not establish independent external T or strong external H2.
