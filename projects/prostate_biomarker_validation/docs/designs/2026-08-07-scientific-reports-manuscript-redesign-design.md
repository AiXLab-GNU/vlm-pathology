---
document_id: 2026-08-07-scientific-reports-manuscript-redesign-design
owner_project: prostate_biomarker_validation
document_type: design
status: approved
created: 2026-08-07
owner: Jin Hyun Kim (PM)
canonical_path: projects/prostate_biomarker_validation/docs/designs/2026-08-07-scientific-reports-manuscript-redesign-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/prostate_biomarker_validation
verification:
  - .venv/bin/python -m unittest discover -s projects/prostate_biomarker_validation/tests -p 'test_*.py' -v
---

# Scientific Reports Manuscript Redesign Design

Date: 2026-08-07
Status: User-approved design; implementation pending
Scope: `paper/` manuscript, figures, tables, manifests, and submission QA

## 1. Objective

Transform the existing MajorRevision-v1 working manuscript into a concise,
internally consistent Scientific Reports submission package without changing
the frozen analyses, adding unapproved experiments, or overstating clinical or
biological conclusions.

The redesign must solve four linked problems:

1. the manuscript is substantially longer and less conventionally structured
   than the target journal recommends;
2. several figures contain text that becomes unreadable at final publication
   size;
3. the strength and scope of claims are not always proportional to the frozen
   evidence;
4. result lineage, endpoint distinctions, and submission declarations must be
   visible and mechanically auditable.

## 2. Governing scientific interpretation

The central narrative is a qualification study, not a claim that every
foundation-model-derived signal is a validated biomarker:

> Pathology foundation-model signals require joint qualification across
> external transport, clinical confounding, site sensitivity, and
> encoder/scale stability. Grade and phenotype signals were comparatively
> transportable, whereas molecular and recurrence signals were target- and
> context-dependent or unsupported.

The paper must distinguish three evidence states:

- `transportable`: supported by an appropriately external or cross-cohort
  evaluation with consistent direction;
- `context-sensitive`: a signal is present in some approved settings but its
  magnitude, direction, or increment depends materially on site, encoder,
  scale, endpoint, or sampling configuration;
- `unsupported in the frozen design`: the prespecified frozen configuration
  does not support the proposed effect. This is not evidence of biological
  absence.

No section may convert these study-specific states into clinical validation,
population prevalence, causal mechanism, whole-slide diagnostic performance,
or general biomarker validity.

## 3. Claim hierarchy

### 3.1 Primary claims

1. Gleason/grade and the evaluated phenotype signal provide the strongest
   evidence of cross-cohort transport among the tested targets.
2. Qualification requires more than pooled discrimination: confounder,
   site, endpoint, and analysis-setting audits can materially change the
   interpretation of a candidate signal.
3. The frozen sensitivity grid is a correlated robustness audit, not 360
   independent validations or confirmatory tests.

### 3.2 Target-specific claims

- **PTEN:** The within-TCGA pooled association is stable across the evaluated
  grid. Grade-independent increment is not established, and the study does
  not provide external PTEN validation.
- **AR:** The pooled positive direction is repeated, but site transportability
  and scanner/site separation remain unresolved. Site-level uncertainty must
  not be generalized to universal site instability.
- **SPOP:** The frozen primary configuration is unsupported and the broader
  result is configuration-sensitive. Modest effects and tumor-sampling
  dilution remain possible; “robust null” and biological-absence language are
  prohibited.
- **Marker 7:** The result is post-hoc and exploratory, with endpoint and
  encoder-by-scale dependence. The paper must not claim robust independent or
  incremental prognostic value when the full clinical/site comparison does not
  support it.

### 3.3 Prohibited wording

The revised manuscript must not state or imply:

- 360 independent validations, external replications, or confirmatory tests;
- universal encoder superiority or failure;
- a reproducible, clean, biological, or definitive SPOP null;
- universally site-unstable AR biology;
- equivalence between reconstructed recurrence, PFS, DFS, and official PFI;
- unbiased PCA model selection when nested selection was not performed;
- clinical utility, clinical validation, treatment guidance, or autonomous
  whole-slide diagnosis.

## 4. Internal analysis freeze and submission-facing disclosure

For implementation control, the redesign uses only the already approved and
saved analysis outputs and their auditable derivatives. It does not expand the
frozen experimental scope.

Internal work-package names (`R1`--`R7`, `A1`--`A3`, `O1`--`O3`, and approval
gate labels), decisions about additional GPU use, and decisions not to run
optional experiments must not appear in the submission manuscript, figure
legends, or supplementary scientific narrative.

The submission-facing Methods disclose only the scientifically relevant fact:
the existing PCA sweep is an exploratory sensitivity analysis and was not used
as nested, unbiased model selection. Any selected-k or seed-stability wording
that would require nested selection must therefore be removed. The manuscript
does not discuss the computing resource that was not used or enumerate
experiments that were considered but not performed.

Before a saved result enters the manuscript, implementation must verify its
schema, row count, patient alignment, endpoint label, input/output lineage,
and relevant run manifest. A mismatch is reported as a blocker; it is not
silently repaired or replaced by a remembered value.

LEOPARD is no longer treated as embargo-blocked based on the user's confirmed
status and public dissemination. The manuscript will cite the published MIDL
challenge paper and identify the organizer baseline manuscript accurately as
a preprint. Public availability must not be described as peer-reviewed journal
publication unless a journal DOI is verified.

## 5. Manuscript architecture

The submission manuscript will use the following order:

1. Title and author metadata
2. Abstract
3. Introduction
4. Results
5. Discussion
6. Methods
7. Data Availability
8. Code Availability
9. Author Contributions
10. Competing Interests
11. Ethics and consent statement where applicable
12. References
13. Figure legends

Supplementary methods, full grids, extended endpoint comparisons, bootstrap
diagnostics, and provenance tables will be separated from the main narrative.

### 5.1 Length and style constraints

- Working title: **Qualification of Pathology Foundation-Model Signals Across
  Cohorts, Sites and Clinical Endpoints**.
- Final title target: no more than 20 words.
- Abstract: no more than 200 words, no citations, and no claim exceeding the
  Results.
- Main narrative target: no more than 4,500 words excluding Abstract, Methods,
  references, legends, and supplementary material.
- Results state observations and uncertainty without repeating methods.
- Discussion begins with the principal finding, distinguishes supported from
  exploratory evidence, and ends with a bounded conclusion.
- One numerical result appears in one primary narrative location; other
  sections refer to it without duplicating long numeric strings.
- Internal workflow labels such as “MajorRevision-v1,” “Gate A,” or “interim
  working manuscript” do not appear in the submission-facing title or prose.

## 6. Results organization

The Results section will be organized by scientific decision rather than by
the chronology of analysis development:

1. Study design and qualification criteria
2. Transportable grade and phenotype signals
3. Molecular targets separate into stable, context-sensitive, and unsupported
   evidence states
4. Site and confounder audits narrow the AR and PTEN interpretations
5. The correlated stability grid exposes target-specific setting sensitivity
6. Recurrence transfer is endpoint- and representation-conditioned

Every subsection ends with the qualification decision supported by that
subsection. Detailed preprocessing, folds, bootstrap algorithms, and parameter
sweeps belong in Methods or Supplementary Information.

## 7. Discussion organization

The Discussion will use five bounded parts:

1. principal qualification result;
2. why grade/phenotype transport differs from molecular-target qualification;
3. what site, scale, encoder, and endpoint sensitivity means scientifically;
4. limitations, including correlated grid cells, seed intervals, endpoint
   heterogeneity, complete-case analysis, event counts, and post-hoc marker 7;
5. a conclusion limited to research qualification and prioritization.

Limitations will not be dispersed as repeated disclaimers throughout every
paragraph. Essential local caveats remain near the relevant result, and the
complete set is synthesized once in the Discussion.

## 8. Figure system

### 8.1 Main-figure set

The target is six main figures, with the exact count allowed to fall to five
if consolidation improves legibility:

1. qualification framework and cohort/evidence map;
2. strongest transported grade and phenotype results;
3. PTEN, AR, and SPOP qualification decisions;
4. confounder and site audits;
5. marker 7 endpoint/encoder/scale-conditioned transfer;
6. condensed stability overview.

Full ROC collections, detailed survival curves, the complete 72-configuration
summary, 360-cell heatmaps, paired contrasts, endpoint concordance, and
bootstrap diagnostics move to supplementary figures or tables unless they are
essential to a primary claim.

### 8.2 Graphic standards

All active renderers must share one style configuration and render from saved
CSV sources only.

- Design at final journal dimensions: 89 mm single-column or 180 mm
  double-column width.
- Minimum final-size text: 8 pt; preferred axis and legend text: 8.5--9 pt.
- Panel labels: bold lowercase letters, 10--11 pt.
- Minimum final-size line width: 1 pt.
- Sans-serif typeface used consistently.
- White background, high contrast, and a color-vision-deficiency-safe palette.
- No long title inside a panel; the figure legend carries the interpretive
  title.
- Legends must not cover data and should be shared across panels where
  possible.
- No panel is retained if it can only be made legible by shrinking below the
  minimum text size.
- Primary outputs are vector PDF; PNG previews remain secondary artifacts.

### 8.3 Stability figure

The current dense Figure 9 must not be reduced as a single large canvas. The
main-paper replacement shows only the decision-level comparison: marker-level
range relative to the null, setting sensitivity, and the limited interpretation
of the sampling-seed interval. The complete heatmap and contrast grid become
supplementary figures generated from
`paper/figure_data/fig9_stability_grid.csv` and
`paper/figure_data/fig9_stability_contrasts.csv`.

## 9. Tables and supplementary information

Main tables are limited to information that cannot be read more clearly from a
figure or a short paragraph. Detailed configuration, endpoint, site, power,
and bootstrap results move to the supplement.

Every active figure and table must have a manifest row containing:

- source CSV path and SHA256;
- renderer or generator path and SHA256;
- output path and SHA256;
- manuscript label and location;
- generation status and freshness check.

The claim--evidence matrix and endpoint hierarchy remain audit artifacts and
must be regenerated before final prose is frozen.

## 10. Statistical and endpoint integrity

The revised Methods and legends must report, where applicable:

- analysis unit, cohort denominator, event count, and complete-case count;
- exact endpoint name and source;
- test or model name, one- or two-sided status, alpha, and multiplicity rule;
- point estimate, interval type, and exact P value when a P value is reported;
- whether an interval is patient-level, bootstrap-based, or a descriptive
  sampling-seed Student-t interval;
- paired patient and paired bootstrap-draw construction for model contrasts;
- undefined bootstrap replicate count and fraction.

Sampling seeds are correlated sensitivity settings, not independent patient
replicates. Unreviewed or missing observations are never converted to negative
labels. Endpoint substitutions are never renamed as official PFI.

## 11. Submission declarations

The package must contain explicit Data Availability, Code Availability, Author
Contributions, Competing Interests, and ethics/consent statements. Unknown
author-specific information must not be invented. If required metadata are not
present locally, the QA report lists the exact missing field as a
submission-blocking author action.

Data Availability distinguishes public cohorts, access-controlled or
challenge-governed sources, and local derived artifacts. Code Availability
describes the reproducible entry points and any restrictions without promising
a repository or archive that has not been authorized for publication.

## 12. Implementation boundaries

Implementation will modify only explicit paths under `paper/`, the associated
figure/table builders, targeted tests, and reproducibility documentation.
Existing user changes, local datasets, model weights, caches, and frozen raw
analysis outputs are preserved.

No broad staging, commit, push, remote creation, upload, or external submission
is authorized. The immutable PRECISE clinician source must remain unchanged and
retain SHA256
`c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.

## 13. Verification and acceptance criteria

The redesign is complete only when all of the following are freshly verified:

1. title and abstract length checks pass;
2. the manuscript uses the approved section order and contains all required
   declarations;
3. every primary claim maps to an approved evidence row and prohibited wording
   scans return zero findings;
4. all active figures and tables are generated from saved sources and have
   complete manifest links;
5. final-size figure text and line-width checks meet Section 8.2;
6. numeric source-to-prose checks report zero mismatches;
7. endpoint-name and endpoint-source checks report zero substitutions;
8. changed Python files pass `py_compile`, focused tests, and full unittest
   discovery;
9. a clean temporary-root regeneration is deterministic except for explicitly
   documented timestamp fields;
10. all figures and tables are newer than their sources;
11. two consecutive XeLaTeX builds succeed with zero unresolved references or
    citations and zero unresolved overfull layout defects;
12. the PRECISE immutable source hash matches the required value;
13. `paper/main.pdf` is rebuilt and its SHA256, byte size, and timestamp are
    recorded;
14. the compliance report distinguishes complete, partial, and author-action
    items without concealing missing information.

The final handoff will state what was changed, which claims were strengthened
or narrowed, all verification commands and actual results, remaining author
actions, and the exact submission-package status.
