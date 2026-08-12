# Handoff prompt: paper revision, Tier 1–2 (external review response)

Paste everything below this line into a new Claude Code session in this repository
(`/home/jinhyun/prj_ws/prj_jin/vlm-pathology`).

---

## Context

This project audits candidate histomolecular markers derived from pathology
foundation-model embeddings (CONCH, Virchow) in prostate cancer, using a prespecified,
confounder-aware qualification protocol. A full paper draft already exists at
`paper/main.tex` (with sections in `paper/sections/*.tex` and figures in
`paper/figures/`, each figure backed by a `.py` generator script against real cached
data — regenerate, don't hand-edit the PDFs/PNGs). It compiles cleanly with `xelatex`.

An external review is saved at `paper/stanford-review.md`. Read it in full first. This
prompt covers **Tier 1 and Tier 2** of the resulting revision plan (agreed with the user
in the prior session) — do **not** attempt Tier 3 (new literature citations — these
require verified web research and are handled separately) or Tier 4 (nice-to-have
polish) unless explicitly asked.

**Before starting, read these for full context on conventions and prior findings:**
- `docs/03_experimental_results.md` and `docs/04_publication_strategy.md` — the
  project's running results log and publication strategy, both kept current.
- `docs/10_protocol_freeze.md` — the prespecified qualification protocol these
  revisions must stay consistent with.
- `resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit.py`, `resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_confounder_audit.py`,
  `resources/projects/prostate_biomarker_validation/model_workspace/pilot_leopard_survival_3pool.py`, `resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_site_split.py`,
  `resources/projects/prostate_biomarker_validation/model_workspace/pilot_precise_spatial_facevalidity.py`, `resources/projects/prostate_biomarker_validation/model_workspace/pilot_statistical_corrections.py`
  — existing scripts this work extends. Reuse their conventions (see below), don't
  reinvent them.

## Hard conventions (do not deviate without a documented reason)

- Python env: `HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python`
  (has CONCH, sksurv, lifelines, statsmodels, etc. already installed).
- Continuous probes: `StandardScaler + RidgeCV(alphas=np.logspace(-2,6,25))`.
  Binary probes: `StandardScaler + LogisticRegression(C=1.0, class_weight="balanced",
  max_iter=2000)`. One fixed protocol everywhere — do not tune per-test.
- Cross-validation: patient-disjoint `GroupKFold(n_splits=5)` wherever patient IDs
  exist. Report patient-level as primary, slide-level as secondary.
- Bootstrap CIs: patient-ID-cluster resampling, 2000 reps (not slide-level resampling
  — a patient's slides are not independent).
- New scripts go in `resources/projects/prostate_biomarker_validation/model_workspace/`, named `pilot_<topic>.py`, with a docstring explaining
  *why* (not just what) — follow the style of the existing `pilot_*.py` files.
- **Verify before trusting.** This project has been burned before by an unverified
  citation and by an untraceable label file (see `docs/03_experimental_results.md` §6e
  for the TCGA-PRAD-BCR incident). Before using any new external data field, confirm it
  via a direct API query and print/inspect actual values — don't assume a field name
  means what its label suggests.
- After each substantive result: (1) update `paper/sections/results.tex` and
  `paper/sections/discussion.tex` as needed, (2) update
  `docs/03_experimental_results.md` (new dated subsection) and, if it changes the
  paper's claims or journal-tier assessment, `docs/04_publication_strategy.md`, (3)
  recompile `paper/main.tex` with `xelatex` (run twice) and confirm zero errors before
  moving on.
- Figures: matplotlib, `Agg` backend, palette consistent with existing
  `paper/figures/fig*.py` (categorical blue `#2a78d6` / orange `#eb6834`, ordinal blue
  ramp `#86b6ef/#5598e7/#2a78d6/#1c5cab/#104281` for tiers). Render to PNG and **view
  the PNG with the Read tool before considering a figure done** — this project's prior
  figures needed two rounds of layout fixes each, caught only by looking, not by
  reading the code.

---

## Tier 1 tasks

### 1.1 Expand marker 7's confounder audit beyond grade

Reviewer's Question for Authors: *"did you test models that adjust for additional
clinical covariates available in TCGA (e.g., PSA, T stage, margins, age)?"*

These fields are confirmed available (verified via direct query in the prior session):
- GDC API: `diagnoses.ajcc_pathologic_t` (T-stage), `demographic.age_at_index` (age) —
  query pattern:
  `POST https://api.gdc.cancer.gov/cases` with
  `filters={"op":"in","content":{"field":"project.project_id","value":["TCGA-PRAD"]}}`,
  `fields="submitter_id,diagnoses.ajcc_pathologic_t,demographic.age_at_index"`.
- cBioPortal `prad_tcga_pub` clinical-sample JSON (already cached at
  `/tmp/claude-3033/-home-jinhyun-prj-ws-prj-jin-vlm-pathology/ad16bf49-b010-4779-ac3f-d4794d956202/scratchpad/prad_clinical_sample.json`
  — if that scratchpad path no longer exists, re-fetch via the cBioPortal REST API,
  study `prad_tcga_pub`): `PREOPERATIVE_PSA` (PSA) and `RESIDUAL_TUMOR` (surgical
  margin status) are patient-level attributes there.

Extend `resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_confounder_audit.py`'s Cox model comparison: instead of
just (grade) vs (grade + marker7_risk), build a fully-adjusted clinical model (grade +
PSA + T-stage + age + margin status, dropping any covariate with too much missingness
to be usable — check and report missingness honestly) and re-run the same
clinical-only / image-only / combined / LRT / grade-stratified-permutation structure
against this richer clinical baseline. Report whether marker7_risk still adds
significant information once ALL these covariates are accounted for, not just grade.
T-stage is categorical (T1–T4 with substages) — decide a sensible ordinal encoding
(e.g., major stage only: 1–4) and note the simplification explicitly.

### 1.2 Benchmark the reconstructed recurrence label against standard TCGA endpoints

Reviewer's Question for Authors (asked twice, in different words): *"benchmark this
label against standard TCGA endpoints (PFI, DFS/RFS) to quantify concordance and
potential misclassification."*

Confirmed available (verified in the prior session): cBioPortal study
**`prad_tcga_pan_can_atlas_2018`** (the TCGA Pan-Cancer Atlas study, which carries the
Liu et al. 2018 TCGA-CDR standardized clinical endpoints) has patient-level
`PFS_STATUS`/`PFS_MONTHS` and `DFS_STATUS`/`DFS_MONTHS` — fetch via the cBioPortal REST
API (same pattern as other cBioPortal pulls in this project;
`GET /api/studies/prad_tcga_pan_can_atlas_2018/clinical-data?clinicalDataType=PATIENT`
or the per-attribute fetch pattern already used elsewhere in this repo).

Compute, for the patients overlapping our existing embedded TCGA-PRAD cohort (270
patients in `resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/`):
1. Event-status agreement between our GDC-`follow_ups`-derived `event` (from
   `resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv`, built by `build_bcr_labels.py`) and PFS_STATUS /
   DFS_STATUS (Cohen's kappa or simple agreement rate; report the confusion matrix).
2. Time correlation between our `follow_up_y` and PFS_MONTHS / DFS_MONTHS (Spearman
   rho) for patients where both exist.
3. **Also re-run marker 7's zero-shot external-validation test
   (`resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_recurrence_external.py`'s core logic) using PFS and/or DFS
   directly as the outcome**, not just our reconstructed label. If marker7_risk also
   predicts PFS/DFS well, this substantially strengthens the marker-7 result and
   directly answers the reviewer's concern about label quality. If it doesn't, report
   that honestly — it would mean the original C-index=0.673 result is somewhat
   label-definition-specific, which is itself an important, honestly-reportable
   finding.

### 1.3 AR-activity (marker 6) per-site forest plot

Reviewer's Question for Authors: *"could you provide per-site effect sizes with
confidence intervals (e.g., a forest plot)?"*

The 6-site leave-one-site-out point estimates already exist (from
`resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_site_split.py`, see `docs/03_experimental_results.md` §3b for
the reported numbers: site rho ranging from about −0.13 at site CH to +0.27 at site
KK, mean 0.151 vs pooled 0.195). That script currently reports point estimates only.
Extend it (or write a focused variant) to also compute a per-site bootstrap 95% CI
(patient-cluster resample within each held-out site, 2000 reps — sample sizes per site
are small, ~20-60, so CIs will be wide; report that honestly rather than
under-representing the uncertainty). Produce a new figure
`paper/figures/fig6_ar_site_forest.py` in the same forest-plot style as
`paper/figures/fig5_forest_plot.py`, one row per site plus a pooled estimate row, and
add it to `paper/sections/results.tex` where AR/marker 6 site-instability is discussed.

### 1.4 BH-FDR supplementary table (all 13 hypotheses)

Reviewer's Question for Authors: *"please list these explicitly and provide the
uncorrected p-values alongside q-values in a supplement."*

Data already exists in `resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv` (13 rows: the 6
pool markers plus 7 non-promoted candidates, with `patient_metric`, `patient_p`,
`patient_ci_lo/hi`, `patient_q_BH_FDR`). Format this as a full LaTeX table (all 13
rows, not just the 6-marker pool subset already shown in the main-text
Table~\ref{tab:pool}) in a new `paper/sections/supplement.tex`, included from
`main.tex` after the bibliography (or before it, your call — just make sure it
compiles). Add a one-paragraph intro explaining the BH-FDR family definition (already
described in `methods.tex`, cross-reference it) and which tests were excluded from the
family and why (external-cohort re-tests, cross-encoder replications).

### 1.5 Clarify PRECISE aggregation unit

Reviewer's Question for Authors: *"were predictions aggregated per image or per
patient, and how were multiple slides per patient handled?"*

Check `resources/projects/prostate_biomarker_validation/model_workspace/pilot_precise_spatial_facevalidity.py`: aggregation is per `image_id`
(i.e. per `sub-XX_ses-YY`, a biopsy session), NOT per patient. Some PRECISE patients
have multiple sessions (e.g. `sub-01` has `ses-01`, `ses-02`, `ses-03` — check
`resources/data/shared/opendataset/PRECISE/participants.csv` for the full subject/session structure). Two
things to do:
1. State this explicitly and precisely in `paper/sections/methods.tex` (PRECISE
   subsection) and in the Results text around Spearman rho=0.865 — say "per biopsy
   session" not "per image" if that's ambiguous, and note how many of the 17
   Gleason-compared images share a patient.
2. As a robustness check, also compute the same real-Gleason correlation aggregated to
   the **patient** level (mean across a patient's sessions, one point per patient
   instead of per session) and report both numbers. If they diverge substantially,
   that's worth discussing; if not, it strengthens the result to show it's not an
   artifact of over-counting patients with more sessions.
Also confirm and state explicitly: PRECISE is core-biopsy tissue (not resection) — the
review asked for this to be confirmed; check `participants.csv` / the Zenodo README if
still present at `resources/data/shared/opendataset/PRECISE/README.md` and state it plainly rather than
assuming.

### 1.6 Tile-sampling method precision

Reviewer: *"How are tiles selected per slide (random uniform, tissue-thresholded,
stratified by tissue class)?"* — this is answerable from existing code, not a new
experiment. Re-read `resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_probe.py` (non-white-pixel threshold,
random search), `resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_leopard_embed.py` and
`resources/projects/prostate_biomarker_validation/model_workspace/pilot_precise_spatial_facevalidity.py` (provided-tissue-mask-based grid, not
random) and `resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_tcga_prad_multi.py`-family scripts (AppMag-derived
scale, non-white threshold). Rewrite the tile-sampling paragraph in
`paper/sections/methods.tex` to state the exact method PER COHORT (they are not all
the same — don't imply a single uniform method), including tissue-fraction thresholds
and tile-count-per-slide values actually used in each experiment reported in the
paper.

### 1.7 Expand survival-metric reporting

Reviewer: *"Reporting time-dependent AUCs, Brier scores, calibration slopes, and hazard
ratio estimates... would round out the survival evaluation."*

- LEOPARD 3-pool: `resources/projects/prostate_biomarker_validation/model_workspace/pilot_leopard_survival_3pool.py` **already computes**
  integrated Brier score and calibration slope for all three pools (check the script's
  output / rerun it) — these numbers exist but are under-reported in
  `paper/sections/results.tex`. Add a table with C-index, time-dependent AUROC@5y, IBS,
  and calibration slope for all three pools (naive/qualified/all-candidate).
- Marker 7 (TCGA-PRAD zero-shot transfer, `resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_recurrence_external.py`):
  IBS and calibration slope are **not yet computed** there. Add them, following the
  same `sksurv.metrics.integrated_brier_score` / calibration-Cox-regression pattern
  used in `pilot_leopard_survival_3pool.py`. Also report the marker7_risk coefficient
  as a hazard ratio ($e^{\text{coef}}$) with its CI, since Cox coefficients alone are
  less interpretable to clinical readers than HRs.

### 1.8 LEOPARD embargo — do not overclaim

Reviewer: *"Please clarify the LEOPARD data-use conditions and confirm that you have
obtained the necessary approvals to report performance prior to official challenge
publications."*

This is a **real, still-open** item — do not write anything implying approval has been
obtained; it has not. Check `paper/main.tex`'s Data and code availability section
(already flags the embargo) and make sure the language is accurate: results are
reported for internal/scientific-review purposes pending organizer confirmation, and
this must be resolved (e.g. via the drafted-but-unsent email at
`resources/data/shared/opendataset/LEOPARD/organizer_email_draft.txt`) before actual journal submission. If
you want, draft a brief explicit "Ethics/data-use" note for the paper stating this
status plainly — do not soften or imply resolution.

---

## Tier 2 tasks

### 2.1 Tile-count / scale sensitivity analysis (bounded scope)

Reviewer: *"a systematic tile-scale sensitivity study (e.g., train/test grid over
scales)... and consider simple scale-normalization procedures."* A full grid across
every marker/cohort is out of scope for this pass — bound it: pick **one** marker with
existing infrastructure at multiple scales (marker 1 or marker 4 on TCGA-PRAD, since
the AppMag-based `pick_level` function already supports arbitrary `target_mpp`) and
sweep tile count $\in \{16, 32, 64\}$ and physical scale $\in \{\approx0.44,
\approx0.88, \approx1.76\}\,\mu$m/px (reuse the pattern already used for the marker-7
Virchow scale-match experiment, `resources/projects/prostate_biomarker_validation/model_workspace/pilot_virchow_tcga_prad_recurrence_scalematch.py`,
as a template for re-embedding at a controlled scale). Report a small table of
patient-level effect size across this 3×3 grid. This directly answers the reviewer's
concern with a bounded, honest, real sensitivity check rather than a full combinatorial
study.

### 2.2 SPOP ablations (lower priority — do only if time remains)

Reviewer: *"ablations on class imbalance handling, assay QC filters, and site-restricted
analyses."* Site-restricted analysis already exists (§3b, leave-one-site-out, already
in the paper). If pursuing this further: (a) try `class_weight=None` vs the standard
`"balanced"` to check the null isn't an artifact of class-weighting choice, (b) note in
the paper that this was checked. Given SPOP is already null across two independent
encoders and a site-split, treat this as confirmatory rather than essential — skip if
Tier 1 + 2.1 already consumed the available time.

---

## Deliverable

By the end of this pass: `paper/main.tex` compiles cleanly with all Tier 1 items
incorporated into the relevant sections (plus a new supplement section for 1.4), at
least one new figure (`fig6_ar_site_forest`), `docs/03_experimental_results.md` and
`docs/04_publication_strategy.md` updated with dated entries for each new result
(following this project's existing documentation conventions — read a few recent dated
subsections in `docs/03_experimental_results.md` first to match the style), and a short
written summary of what changed relative to `paper/stanford-review.md`'s specific
Questions for Authors, so a response-to-reviewers letter can be drafted from it later.
