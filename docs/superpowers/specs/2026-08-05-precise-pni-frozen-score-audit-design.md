# PRECISE PNI Frozen-Score Audit Design

Date: 2026-08-05

## 1. Objective

Audit the already-frozen PRECISE PNI candidate-ranking scores against Song's
completed blinded review of 120 candidates. The audit asks a workflow question:

> How many spatially distinct AI-ranked candidates per slide must a pathologist
> review to recover the pathologist-confirmed PNI foci observed in the reviewed
> sample?

This is a retrospective candidate-triage audit. It is not an estimate of
whole-slide PNI sensitivity, PNI prevalence, or clinical diagnostic accuracy.

## 2. Fixed inputs and provenance

The audit uses the following existing inputs without changing model scores or
candidate coordinates:

- `opendataset/PRECISE/precise_pni_review (1).csv`: final clinician export,
  retained read-only as the source record.
- `opendataset/PRECISE/pni_review_120_selection_manifest.csv`: blinded review
  selection manifest and frozen score components.
- `opendataset/PRECISE/pni_candidate_full/all_candidate_scores.csv`: all 2,264
  mask-filtered candidate windows from 19 malignant slides.
- `opendataset/PRECISE/pni_candidate_full/run_config.json`: frozen CONCH model,
  prompts, exemplar set, geometry, and score weights.
- `opendataset/PRECISE/pni_review_120_build_summary.json`: selection seed and
  sampling structure.

The review sample was constructed after spatial non-maximum suppression and
contains 60 high-ranked, 30 mid-ranked, and 30 low/random candidates balanced
across 19 slides. Model scores and strata were hidden from the reviewer.

## 3. Label normalization and validation

A derived normalized review table will be created; the source clinician CSV
will not be edited.

- Populate `reviewer_id=Song` in the derived table.
- Preserve every clinician-entered label verbatim.
- Treat blank outcome fields as missing/not evaluable; do not infer `no`.
- Check uniqueness of `candidate_id` and review order.
- Require exact candidate ID, slide ID, coordinate, and window-size agreement
  between the review export and selection manifest.
- Report all missing or internally inconsistent fields before metric
  calculation.
- Derive `subject_id` from the documented PRECISE image identifier and use it
  as the resampling cluster.

PNI-positive means `pni_present=yes`. Nerve-positive means
`nerve_present=yes`. `touching` and `surrounding` remain separate PNI subtypes.

## 4. Frozen ranking reconstruction

The audit will reproduce the original 300 micrometre window geometry and
spatial non-maximum suppression rule from
`models/build_precise_pni_review_html.py`. For each slide, retained candidates
will be ordered by the frozen `combined_score`. No label-derived refitting,
threshold optimization, prompt changes, exemplar changes, or score-weight
changes are permitted.

The combined score remains:

```
0.50 * prototype percentile
+ 0.35 * text-PNI percentile
+ 0.15 * nerve percentile
```

The reconstruction must reproduce all reviewed candidates' score values,
strata, and ranks. A failed match stops the analysis rather than silently
recomputing a different candidate universe.

## 5. Endpoints

### 5.1 Primary endpoint

PNI focus capture as a function of per-slide review budget after spatial NMS:

- budgets `k = 1, 2, ..., 10` candidates per slide;
- numerator: evaluable pathologist-confirmed PNI candidates whose NMS rank is
  at or below `k`;
- denominator: all evaluable pathologist-confirmed PNI candidates in the
  reviewed sample.

The full capture curve is primary. The smallest observed `k` that includes all
seven currently confirmed foci will be reported descriptively. Because `k=4`
was noticed after reviewing these data, it is not a prespecified confirmatory
threshold.

### 5.2 Secondary endpoints

- Nerve-positive focus capture for `k = 1, ..., 10`.
- PNI and nerve yield within high, mid, and low/random review strata.
- Review-label coverage at each per-slide budget, defined as the fraction of
  NMS-ranked top-`k` candidates that are present in the 120-candidate review
  set.
- Candidate-level ROC AUC and average precision for:
  - prototype score;
  - text-PNI score;
  - nerve score;
  - frozen combined score.
- Separate capture summaries for `touching` and `surrounding` PNI.
- Slide- and subject-level counts of reviewed candidates, nerves, and PNI.

Precision at a per-slide top-`k` budget will be reported only when every
candidate in that budget has an evaluable review label. Unreviewed candidates
will never be treated as negative. If coverage is incomplete, the report will
show the coverage and known-positive capture separately without calculating
top-`k` precision.

ROC AUC and average precision apply only to the stratified 120-candidate audit
sample and must not be presented as population-wide diagnostic performance.

## 6. Uncertainty and small-sample handling

- Report exact binomial confidence intervals for simple observed proportions.
- Use subject-cluster bootstrap confidence intervals for ranking metrics and
  capture summaries, with a fixed seed and saved replicate table.
- Resample subjects, retaining all their reviewed candidates and slides.
- If a bootstrap replicate contains only one outcome class, mark the relevant
  metric undefined and retain that replicate in the failure accounting.
- Report the number and fraction of valid and undefined replicates.
- Do not calculate asymptotic p-values for the seven-positive PNI analysis.

The cluster bootstrap quantifies sampling variability within this selected
audit set. It does not correct the review-set selection design or establish
whole-slide sensitivity.

## 7. Error analysis

Create a deterministic error-review table containing:

- high-ranked PNI-negative candidates;
- nerve-positive/PNI-negative candidates;
- confirmed PNI candidates ranked below smaller review budgets;
- score components, tissue fractions, slide and subject identifiers, and crop
  coordinates.

Histological error categories will be copied only from clinician-provided
labels or notes. The pipeline will not invent diagnoses such as ganglion,
vessel, smooth muscle, inflammation, or benign gland mimic. If more detailed
histological categories are needed, they require a subsequent pathologist
review and are outside this audit.

## 8. Outputs

Write outputs under a new directory:

`opendataset/PRECISE/pni_frozen_score_audit/`

Required files:

- `normalized_review.csv`
- `data_integrity_report.csv`
- `candidate_audit_table.csv`
- `review_budget_capture.csv`
- `score_metric_summary.csv`
- `cluster_bootstrap_replicates.csv`
- `subtype_and_stratum_summary.csv`
- `error_review_table.csv`
- `run_config.json`
- `RESULTS_REPORT.md`
- `fig_review_budget_capture.png` and `.pdf`
- `fig_score_distributions.png` and `.pdf`

All tables and figures must be regenerated from the fixed input files by one
auditable entry-point script. The run configuration records input hashes,
software versions, timestamp, seed, and output hashes.

## 9. Required report language

Permitted conclusion if the reconstruction confirms the currently observed
ordering:

> In the stratified, blinded 120-candidate PRECISE review sample, all seven
> pathologist-confirmed PNI foci occurred in the high-ranked stratum, and the
> frozen candidate ranker concentrated the observed foci within a small
> per-slide review budget.

Prohibited conclusions:

- “The model has 100% PNI sensitivity.”
- “Four candidates per slide are sufficient for clinical diagnosis.”
- “The model excludes PNI from unreviewed slide regions.”
- “The audit estimates PNI prevalence in PRECISE.”

Any numerical top-4 statement must explicitly say that it is retrospective,
descriptive, based on seven observed confirmed foci, and requires independent
validation.

## 10. Verification criteria

The audit is complete only if:

1. Source inputs remain byte-identical.
2. All 120 candidate IDs reconcile with the selection manifest.
3. Frozen score and NMS reconstruction checks pass.
4. Missing labels are enumerated and never silently imputed.
5. Every reported number is traceable to a CSV output.
6. Figures regenerate from those CSV outputs.
7. A clean rerun produces identical tabular results and hashes, except for the
   recorded execution timestamp.

## 11. Deferred work

The following are explicitly outside this design:

- refitting or recalibrating score weights on the 120 reviewed candidates;
- training a supervised PNI model from seven positives;
- claiming whole-slide sensitivity or negative predictive value;
- TCGA candidate generation or BCR modeling;
- pathologist correction of nerve contours;
- independent confirmation on PAIP2021, SPROB20, or a newly reviewed PRECISE
  sample.
