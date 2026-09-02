---
document_id: 2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: superseded
created: 2026-09-01
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-design.md
implements: null
supersedes: null
superseded_by: projects/quantitative_foundation_model_validation/docs/designs/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-design.md
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm8_grading_criterion_qualification
  - resources/artifacts/quantitative_foundation_model_validation/fm8_grading_criterion_qualification
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm8_grading_criterion_qualification -v
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# Grading-criterion qualification design

## Decision

Residual discovery is paused. The grading lane must first establish, in order:

1. accuracy of a frozen-representation grading head on an independent cohort;
2. recoverability of the pathology criteria that define the cohort reference grade;
3. functional reliance of the locked grading decision on those criteria; and
4. an uncertainty-aware allocation of the decision reliance among correlated criteria.

Only after these gates pass may a grading residual be computed. Existing FM8 BCR Tier 4 results
remain historical and do not qualify the grading lane.

## Cohort roles

No cohort changes role after labels or results are opened.

| Cohort | Specimen | Locked role | Reference strength | Current use state |
|---|---|---|---|---|
| PANDA public development | needle biopsy | development of grading head and criterion probes only | routine/provider-specific slide labels; public table has no patient ID | local WSI and labels available; QFM source lock required |
| SICAPv2 official test | needle biopsy | independent criterion qualification and preconfirmatory grading transport | expert global primary/secondary Gleason plus pixel/patch GP3/4/5 and cribriform labels; patient-disjoint official test | local; previously opened for a different detector task, so not pristine confirmatory evidence |
| PAR S-BIAD2323 | needle biopsy | confirmatory external grading and scanner-repeatability cohort | 185 patients, 339 glass slides, three scanner versions; two near-complete independent readers and a 59-slide uropathologist subset; no supplied consensus | metadata/labels first, then WSI acquisition and hash lock |
| CHIMERA Task 1 | prostatectomy | secondary specimen-transport and BCR-use analysis | reported ISUP plus primary/secondary/tertiary Gleason; no central reread and 3/95 mapping discrepancies | local; governance reconciliation required |
| TCGA-PRAD | prostatectomy | BCR development only in this workstream | source clinical grade, not an independent grading reference | never used as evidence of external grading accuracy |

The hidden PANDA US external set has the strongest published consensus reference, but it is not a
locally obtainable public input. It may replace neither PAR nor SICAP unless access, immutable
membership, labels, and no-tuning execution rights are documented before opening predictions.

## Endpoint separation

Cancer detection and grading are different endpoints. Benign (`ISUP 0`) is evaluated in a separate
benign-versus-cancer analysis. Primary grading accuracy is computed among cancer-containing
specimens for ordinal ISUP 1--5. A six-class benign-plus-ISUP result is secondary and is never
described as pure grading accuracy.

Grading decisions and BCR decisions are also separate:

- the grading head asks whether the model assigns the reference grade;
- the BCR head asks whether grade-related representation contributes to recurrence risk.

Performance or erasure in one head is not evidence for the other.

## Clinical grading criteria

The prespecified image-derived criteria are specimen-specific:

1. dominant/primary Gleason pattern;
2. the biopsy secondary rule: with three patterns, the highest-grade remaining pattern enters the
   score rather than being reported as a separate tertiary pattern;
3. the prostatectomy secondary/minor rule: the second-most prevalent pattern enters the score,
   while a minor high-grade pattern below the reporting threshold is recorded separately;
4. GP3 morphology: individual, discrete, well-formed glands;
5. GP4 morphology: poorly formed, fused, cribriform, or glomeruloid glands;
6. GP5 morphology: lack of gland formation, including solid sheets, cords/single cells, or
   comedonecrosis;
7. proportions of GP3, GP4, and GP5 tissue where spatial truth exists;
8. cribriform morphology within GP4 where explicitly annotated; and
9. the deterministic Gleason-to-ISUP mapping, treated as the resulting label rather than an
   independent morphology.

Current sources do not provide separate truth for every GP4/GP5 subtype, intraductal carcinoma, or
variant morphology. Aggregate GP3/4/5 recoverability cannot be restated as recovery of each subtype.

Age, PSA, pathologic T stage, margin status, lymph-node involvement, seminal-vesicle invasion,
capsular penetration, and lymphovascular invasion are prognostic or staging covariates. They are
not grading criteria and are excluded from the grading-criterion attribution denominator.

## Model and accuracy lock

CONCH and Virchow remain frozen and are evaluated separately. QFM generates embeddings from the
registered source WSI; another project's generated embedding or model cache is prohibited.
Development uses PANDA only. External cohorts receive the unchanged preprocessing, aggregation,
ordinal head, criterion probes, and erasure rules.

The primary accuracy metric is patient-clustered quadratically weighted kappa among cancer cases.
Secondary metrics are MAE, exact agreement, within-one agreement, macro recall, class-specific
recall, severe error rate (`absolute grade error >= 2`), confusion matrix, and ordinal calibration.
Benign/cancer sensitivity and specificity are reported separately. Confidence intervals use
patient bootstrap; multiple slides or scanner repeats never count as independent patients.

PANDA public labels omit patient identity. Therefore its internal resampling scores are development
diagnostics only. No performance claim is made until a patient-identified external cohort is used.

## Representation and functional-use estimands

For each criterion `c`, three non-interchangeable quantities are reported:

1. **Recoverability:** cross-cohort discrimination or regression performance of a source-fitted
   probe for `c`, with label-permutation and prevalence-matched baselines.
2. **Decision reliance:** fixed-head loss after removing the source-fitted criterion direction or
   joint criterion subspace, compared with dimension- and variance-matched random erasure and a
   graded erasure dose-response.
3. **Allocated share:** patient-bootstrap Shapley/dominance allocation of the joint above-chance
   performance loss and ordinal-logit variance across the correlated criteria.

The primary normalized reliance is

`(QWK_full - QWK_erased) / max(QWK_full, epsilon)`

and is always accompanied by the absolute delta, confidence interval, and matched-random null.
The joint removal result is primary; individual shares need not sum stably when the full head is
near chance. Fixed-head erasure measures reliance. Refit-after-erasure is secondary and measures
replaceability/compensation, not absence of use.

For BCR, replace QWK with C-index and keep a separate table and denominator. A single universal
"clinical-feature use percentage" is prohibited.

## Gates before residual analysis

Residual entry requires all of the following:

- complete source hashes, patient/slide identity contracts, licenses, and QFM use declarations;
- PANDA development only and at least one untouched patient-identified external grading cohort;
- external QWK above chance with a clinically interpretable confusion profile in each encoder
  claimed;
- external recovery of primary/secondary Gleason or GP3/4/5 criterion truth;
- joint criterion erasure exceeding matched-random controls with a stable dose-response;
- patient-bootstrap intervals and source/external direction agreement;
- scanner/provider/color/tissue-amount audit and paired-scanner repeatability where available;
- no target-cohort tuning, no post hoc criterion definition, and no cross-project generated input.

Failure yields a narrower report, not a residual. PAR's lack of a supplied consensus label is
preserved: results are reader-conditioned, with a prespecified consensus sensitivity analysis only
where a non-tied consensus exists.

## Claim ceiling

Until the gates pass, allowed language is `frozen-representation grading qualification` or
`external agreement with the available pathology reference`. Clinical-grade diagnostic validity,
pathologist replacement, universal grading ability, causal mechanism, and residual biomarker
claims are prohibited.

## Grading-rule references

- [2019 ISUP grading consensus](https://pmc.ncbi.nlm.nih.gov/articles/PMC7382533/)
- [2014 ISUP Grade Group consensus](https://pubmed.ncbi.nlm.nih.gov/26492179/)
- [EAU classification and staging system](https://uroweb.org/guidelines/prostate-cancer/chapter/classification-and-staging-systems)
