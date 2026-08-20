---
document_id: 2026-08-20-quantitative-foundation-model-validation-site-heldout-functional-xai-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: approved
created: 2026-08-20
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-08-20-quantitative-foundation-model-validation-site-heldout-functional-xai-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm6_site_heldout_functional_validation
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm6_site_heldout_functional_xai -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
---

# FM6 site-held-out functional XAI validation design

## 1. Decision and rationale

The accountable author requested completion of the strongest functional XAI experiment that
can lawfully support manuscript resubmission. CHIMERA Task 1 remains under publication
embargo. LEOPARD is handled only by the separately approved external-functional protocol
after the accountable author's 2026-08-20 embargo-clearance confirmation.

The approved alternative is a result-locked, tissue-source-site-held-out validation using the
existing TCGA-PRAD FM6 development universe. It asks whether the internally observed
ISUP-correlated fixed-head sensitivity persists when every evaluated collection site is
absent from model fitting. This is a stronger distribution-shift test than patient-random OOF,
but it is not an independent external cohort and must not be named external validation.

## 2. Scientific question

For CONCH and Virchow separately, does removing the TCGA-training-derived ISUP-correlated
embedding direction reduce a BCR head's held-out discrimination across unseen TCGA tissue
source sites more than variance-matched random-direction removal?

The intervention tests functional sensitivity of a fitted BCR head to an ISUP-correlated
whole-tissue direction. It does not establish tumor-specific mechanism, indispensable use,
clinical utility, endpoint equivalence, or external-cohort transport.

## 3. Fixed analysis universe

- Source: the hash-locked FM6 TCGA-PRAD development universe, 392 subjects and 80 BCR events.
- Representation: existing paired whole-tissue CONCH and Virchow embeddings generated from
  identical 394.24 micrometre crop boundaries.
- Site identifier: the two-character TCGA tissue source site segment in `case_id`.
- Evaluation-site eligibility: at least 20 subjects and at least 5 BCR events, determined
  from source feasibility counts before representation outcomes are examined.
- Expected eligible sites: HC, EJ, G9, KK, V1, YL, and J4; 289 unique held-out subjects and
  69 events. All other subjects remain eligible for training but never contribute to the
  primary held-out estimate.

Each eligible site is held out once. Training uses every subject outside that site. No held-out
site outcome, ISUP value, representation, or prediction may select a model or threshold.

## 4. Locked model and intervention

The following values are inherited from the completed internal pilot and are not reselected:

- frozen encoders and paired patient aggregation;
- standardization fitted only on the current training partition;
- PCA rank 64;
- Cox ridge alpha 1000;
- ISUP Ridge alpha 1000;
- 100 variance-matched random directions per site and encoder;
- seed 260820;
- 2,000 stratified patient-bootstrap draws.

For each held-out site and encoder, the training partition fits one standardized PCA-Cox BCR
head and one standardized Ridge ISUP direction. The full head is then evaluated on the site
before and after orthogonal removal of the ISUP direction. Random controls are generated from
the training representation only and match the target direction's removed variance.

## 5. Estimands and uncertainty

The primary performance estimand is a within-site-comparable-pair-weighted C-index across the
seven held-out sites. Cross-site patient pairs are excluded so that site-level score offsets
cannot create apparent discrimination. The primary intervention estimand is

`delta_use = C-index(full fixed head) - C-index(ISUP-erased fixed head)`.

Secondary estimates are the ordinary pooled held-out C-index, site-specific deltas, the
site-held-out ISUP Spearman correlation, and the number of sites with positive delta.
Paired 95% intervals use 2,000 patient-bootstrap draws stratified by held-out site. The
matched-random one-sided p-value is `(1 + count(random_delta >= target_delta)) / 101` and is
Holm-adjusted across the two encoders.

## 6. Prespecified evidence gate

An encoder passes `SITE_HELDOUT_FUNCTIONAL_TRANSPORT` only if all conditions hold:

1. the full-head stratified C-index bootstrap lower bound is greater than 0.50;
2. the targeted `delta_use` bootstrap lower bound is greater than 0;
3. the Holm-adjusted target-versus-random one-sided p-value is at most 0.05;
4. at least five of seven eligible sites have positive site-specific `delta_use`.

Both encoders must pass for `PASS_REPLICATED_SITE_HELDOUT_FUNCTIONAL_TRANSPORT`. One passing
encoder yields `PARTIAL_ENCODER_SPECIFIC_SITE_HELDOUT_EVIDENCE`; neither yields
`FAIL_OR_INCONCLUSIVE_SITE_HELDOUT_EVIDENCE`. Results are reported regardless of direction.

## 7. Claim and publication boundary

- Allowed positive wording: multi-site held-out internal functional transport within TCGA.
- Prohibited wording: independent external validation, strong external H2, tumor-specific
  mechanism, clinical validation, or new biomarker discovery.
- CHIMERA model/outcome analysis remains prohibited. LEOPARD analysis is outside this
  site-held-out family and follows its separate locked external-functional protocol.
- A negative or inconclusive result strengthens the limitation; it does not trigger
  retuning, site removal, alternative thresholding, or a new unregistered result family.

## 8. Approval

The 2026-08-20 accountable-author instruction to complete the experiment for resubmission is
the approval for this bounded revision analysis. It does not authorize embargoed-cohort
publication or expansion beyond the fixed TCGA site-held-out family.
