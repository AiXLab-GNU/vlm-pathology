---
document_id: 2026-08-31-quantitative-foundation-model-validation-fm8-tier4-discovery-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: approved
created: 2026-08-31
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-08-31-quantitative-foundation-model-validation-fm8-tier4-discovery-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm8_bcr_tier4_discovery
  - resources/artifacts/quantitative_foundation_model_validation/fm8_bcr_tier4_discovery
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm8_bcr_tier4_discovery -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# FM8 Tier 4 latent digital-marker discovery design

## Decision and scientific identity

FM8 is a separate follow-up workstream that searches for ground-truth-supported latent digital
signals for three non-interchangeable endpoints: cancer presence, grading, and progression. It is
not an added experiment for the closed evidence-qualified-alignment manuscript and does not alter
that manuscript, its submission package, PDFs, provenance, or results.

The 2026-08-25 FM8 entry-audit `NO-GO` remains historical evidence for a workstream that joined
residual computation to shortcut clearance and blinded pathology review. This design introduces a
narrower two-gate architecture:

1. Tier 4 computational exploration may run when endpoint truth, frozen representations,
   patient-level leakage control, source-only selection, and locked external application are ready.
2. Tier 3 promotion, localization, morphology naming, and pathology review remain blocked until
   shortcut metadata, image-review authority, repeatability, and external morphology recurrence
   pass a separate GO decision.

The failed independent tumor-detector gate fixes all FM8 analyses at `whole-tissue`. No result may
be called tumor-specific, a tumor mechanism, a clinical biomarker, or a diagnostic model.

## Two independent classification axes

The existing `medical_metric_tier` describes distance from a medical reference: its T4 is a
model-derived value. `fm8_translation_tier` instead describes interpretability and translation:

- Tier 1: directly visible clinical expression;
- Tier 2: quantitative expression linked to established anatomy or pathophysiology;
- Tier 3: repeatably measurable new image expression that independently supports an endpoint;
- Tier 4: stable endpoint-supporting latent signal not yet translated to an image expression.

They are stored in separate fields. A newly discovered FM8 latent score is initially
`medical_metric_tier=T4_model_derived` and `fm8_translation_tier=Tier_4`.

Functional roles are multi-label, not mutually exclusive:

- standalone: latent-only information reproduces in source and external cohorts;
- complementary: additive `clinical + latent` improves on the clinical baseline externally;
- interactive: a prespecified clinical-by-latent interaction improves on the additive model in
  the same direction in source and external cohorts;
- redundant/supportive: latent-only prediction is present but clinical adjustment adds at most a
  prespecified negligible amount, consistent with re-expression of known information.

## Endpoint lanes

| Lane | Source -> external | Analysis unit | Label contract | Initial status |
|---|---|---|---|---|
| progression | TCGA-PRAD -> CHIMERA | patient | BCR event plus follow-up time; TCGA days and CHIMERA months remain separate | READY for Tier 4 computation |
| cancer presence | NADT -> PANDA | patient when a valid patient ID exists | benign/cancer only; HGPIN, atypical, uncertain and not-evaluable are not coerced | NOT READY pending shared immutable provenance and label map |
| grading | NADT tumor cases -> PANDA cancer cases | patient | ordinal ISUP/Gleason among cancer cases; benign is never a low grade | NOT READY pending shared immutable provenance and label map |

One endpoint's performance is never evidence for another endpoint. Code may share pure utilities,
but configurations, labels, outputs, candidate IDs, registries, and claims remain lane-specific.

## First locked experiment: BCR

The source is the existing TCGA-PRAD universe of 392 patients and 80 BCR events with five fixed
patient folds. The external cohort is all 95 CHIMERA patients and 27 BCR events. CONCH and Virchow
use separate frozen patient representations and separate candidates; passage by both encoders is
not required.

For each encoder, one prespecified candidate is evaluated:

- `FM8-BCR-CON-L001`
- `FM8-BCR-VIR-L001`

Within each source training fold, the representation is standardized and projected away from the
prespecified available known/QC panel: ISUP, mean tissue fraction, mean MPP, and log slide count.
Projection regularization is selected by inner patient-fold reconstruction error. PCA rank and Cox
ridge alpha for a single latent risk score are then selected by inner patient-fold C-index with a
one-standard-error preference for smaller rank and stronger regularization. The held-out source
patient is predicted exactly once.

The four models use the same source split:

1. baseline: standardized ISUP;
2. latent-only: the cross-fitted latent risk score;
3. additive: ISUP plus latent score;
4. interaction: ISUP, latent score, and their product.

Training observations for the additive and interaction models receive inner-OOF latent scores, so
an in-sample latent score is never used to train a stacked model that is evaluated out of fold.
After source OOF evaluation, hyperparameters are selected again using source folds only, a final
model is fit on all TCGA patients, and it is applied unchanged to CHIMERA. No CHIMERA refit,
recalibration, threshold, candidate, rank, alpha, or model-family selection is permitted.

## Prespecified evidence rules

All performance metrics are Harrell C-index. `delta_additive = C(additive)-C(baseline)` and
`delta_interaction = C(interaction)-C(additive)`. Patient bootstrap uses 2,000 paired draws;
no-comparable-pair draws remain undefined and are counted.

- standalone supported: latent-only C-index is above 0.5 in source and external and at least four
  of five source held-out folds have the same direction;
- complementary supported: `delta_additive > 0` in source and external;
- interactive supported: the source-fixed interaction coefficient is nonzero and
  `delta_interaction > 0` in source and external;
- redundant/supportive supported: standalone is supported and absolute external
  `delta_additive <= 0.01`;
- not qualified: no functional rule reproduces externally, or a material shortcut cannot be
  separated from the score.

Statistical non-significance is not an automatic failure in CHIMERA. Point direction, interval,
undefined draws, source-fold stability, and the prespecified rule are all reported. Criteria are
not changed after results are read.

## Shortcut and claim gates

The shortcut audit covers source TSS/site where available, external site availability, grade,
MPP, tissue fraction, slide count, and deterministic RGB/optical-density color summaries from the
locked shared crop cache. Stain, scanner, blur, fold, compression, specimen type, tumor amount, and
purity are reported as observed, missing, or not evaluable; they are never inferred. A score whose
external reproduction cannot be separated from a material shortcut remains a Tier 4 hypothesis
with `not_qualified` claim status.

Tier 3 work is prohibited unless a new GO record confirms shortcut clearance, patient-level image
review rights, pathologist burden and adjudication, coordinate-localizable candidate contribution,
matched controls, source/external morphology recurrence, and repeatable measurement. The present
run creates no pathology review package and assigns no new morphology name.

## Stop rules and reproducibility

Stop without scientific interpretation on source hash change, row/order mismatch, duplicate or
cross-fold patient, nonfinite representation, missing endpoint, cross-encoder crop mismatch, or
failure to give every source patient exactly one OOF prediction. Preserve missing and undefined
values. Patient-level tables and arrays remain local artifacts; aggregate evidence, configuration,
candidate registry, shortcut audit, and Korean report are tracked milestone outputs. A clean rerun
must exactly reproduce every protocol-declared nonvolatile output hash.
