---
document_id: 2026-08-06-precise-pni-morphology-rereview-design
owner_project: precise_pni_candidate_triage
document_type: design
status: approved
created: 2026-08-06
owner: Jin Hyun Kim (PM)
canonical_path: projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/precise_pni_candidate_triage
verification:
  - .venv/bin/python -m unittest discover -s projects/precise_pni_candidate_triage/tests -p 'test_*.py' -v
---

# PRECISE PNI Morphology Re-review Study Design

Date: 2026-08-06
Status: Approved for design documentation
Study stage: Pathologist morphology-annotation pilot

## 1. Title

**Blinded morphology re-review of 14 pathologist-confirmed nerve-containing PRECISE candidates**

Korean working title:

> PRECISE 전문의 확인 신경 후보 14건의 PNI 형태 재판독 연구

## 2. Background and rationale

The frozen-score PRECISE audit evaluated 120 blinded, stratified candidates from
19 malignant slides. The pathologist identified 14 nerve-positive candidates,
including seven PNI-positive foci: four classified as `touching` and three as
`surrounding`. The audit showed that the frozen candidate ranker concentrated
these observed foci toward the top of the post-NMS per-slide ranking. It did not
validate whole-slide PNI sensitivity or a clinical diagnostic threshold.

The first review was designed to establish nerve and PNI status, not to provide
a complete morphology ontology. It therefore did not systematically record
intraneural invasion, section orientation, longitudinal tracking, branch-point
involvement, or nerve multiplicity. A focused re-review of all 14 nerve-positive
candidates is needed before nerve contours, interface measurements, spatial
gradients, or larger-cohort PNI-burden studies can be designed reliably.

## 3. Purpose

The purpose of this study is to determine whether a pathologist can apply a
structured, reproducible morphology annotation scheme to the 14 PRECISE
nerve-positive candidate foci when they are viewed with adequate H&E context.

This is a method-development pilot. It is not intended to estimate the
population distribution of PNI morphologies, establish prognosis, validate an
AI morphology classifier, or infer the absence of PNI outside the reviewed
fields.

## 4. Primary research question

> Among the 14 previously nerve-positive PRECISE candidate foci, can a
> pathologist assign structured and evaluable labels for nerve presence, PNI
> status, cancer–nerve relationship, section orientation, longitudinal
> tracking, and branch-point involvement using H&E morphology alone?

## 5. Secondary research questions

1. Which of the seven previously confirmed PNI foci remain definite PNI when
   reviewed in wider H&E context?
2. Do any of the seven previously PNI-negative nerve foci become probable or
   definite PNI, or remain adjacent/no-relation controls?
3. Can `touching`, `surrounding/encasement`, and `intraneural` components be
   distinguished without forcing uncertain fields into negative categories?
4. Can transverse, oblique, and longitudinal nerve sections be distinguished?
5. Are longitudinal tracking, branch-point involvement, and multiple-nerve
   involvement evaluable in the available fields?
6. Which foci are sufficiently clear to advance to pathologist-drawn nerve and
   cancer–nerve interface contours?

## 6. Study set

The fixed re-review set contains all 14 candidates previously labeled
`nerve_present=yes`. They represent 10 slides and 10 subjects.

| Candidate | Subject | Slide | Previous PNI label | Previous relation |
|---|---|---|---|---|
| PRECISE-PNI-004 | sub-09 | sub-09_ses-01 | yes | touching |
| PRECISE-PNI-008 | sub-04 | sub-04_ses-01 | yes | touching |
| PRECISE-PNI-014 | sub-20 | sub-20_ses-01 | no | none |
| PRECISE-PNI-019 | sub-02 | sub-02_ses-01 | no | none |
| PRECISE-PNI-039 | sub-22 | sub-22_ses-01 | no | none |
| PRECISE-PNI-044 | sub-03 | sub-03_ses-01 | no | adjacent |
| PRECISE-PNI-060 | sub-09 | sub-09_ses-01 | no | adjacent |
| PRECISE-PNI-061 | sub-02 | sub-02_ses-01 | yes | surrounding |
| PRECISE-PNI-068 | sub-01 | sub-01_ses-02 | yes | surrounding |
| PRECISE-PNI-070 | sub-12 | sub-12_ses-01 | yes | touching |
| PRECISE-PNI-081 | sub-20 | sub-20_ses-01 | no | none |
| PRECISE-PNI-087 | sub-20 | sub-20_ses-01 | yes | touching |
| PRECISE-PNI-093 | sub-06 | sub-06_ses-01 | no | none |
| PRECISE-PNI-118 | sub-05 | sub-05_ses-01 | yes | surrounding |

The previous labels above define provenance but will not be displayed during
the blinded primary re-review.

## 7. Scope of this stage

This stage records morphology labels only. It does not ask the reviewer to draw
nerve contours, cancer contours, or cancer–nerve contact segments. The existing
circles in `pni_spatial_pilot/nerve_annotations_v1.csv` are provisional visual
localizations and must not be shown as approved nerve boundaries during the
primary read.

Contour approval and correction will be a separate second-stage task performed
only after the morphology labels are locked.

## 8. Blinding and image presentation

- The reviewer will not see previous PNI labels, previous relationship labels,
  confidence, model scores, strata, or candidate ranks during the primary read.
- The 14 cases will be shown in a deterministic randomized order using a saved
  seed.
- The interface will display a new temporary morphology-review ID. The mapping
  to the original candidate ID will be stored in a separate manifest.
- H&E is the primary evidence source. Each case must include the original
  300-µm candidate field and at least one wider H&E context view sufficient to
  assess longitudinal course and branch points.
- Provisional nerve circles and prior annotations will not be overlaid.
- Paired HMWCK/AMACR images will not be used in the blinded primary morphology
  assignment. They may be consulted only in a separately identified
  adjudication stage if H&E remains not evaluable.

## 9. Structured re-review fields

Every categorical field must allow `uncertain` or `not_evaluable`. Missing
values must never be converted automatically to `no`.

### 9.1 Core confirmation

- `nerve_present`: `yes`, `no`, `uncertain`, `not_evaluable`
- `pni_status`: `definite`, `probable`, `absent`, `uncertain`, `not_evaluable`
- `overall_confidence`: `high`, `medium`, `low`

### 9.2 Cancer–nerve relationship

Record one best overall relationship:

- `none`
- `adjacent`
- `touching`
- `surrounding_encasement`
- `intraneural`
- `mixed`
- `uncertain`
- `not_evaluable`

Also record the following components separately so that potentially coexisting
patterns are not lost:

- `touching_component`: `yes`, `no`, `uncertain`, `not_evaluable`
- `surrounding_component`: `yes`, `no`, `uncertain`, `not_evaluable`
- `intraneural_component`: `yes`, `no`, `uncertain`, `not_evaluable`

### 9.3 Nerve and interaction morphology

- `section_orientation`: `transverse`, `oblique`, `longitudinal`, `mixed`,
  `uncertain`, `not_evaluable`
- `longitudinal_tracking`: `yes`, `no`, `uncertain`, `not_evaluable`
- `branch_point_involvement`: `yes`, `no`, `uncertain`, `not_evaluable`
- `nerve_multiplicity`: `single`, `multiple`, `uncertain`, `not_evaluable`
- `field_adequacy`: `adequate`, `wider_context_needed`, `not_evaluable`
- `reviewer_notes`: optional free text restricted to observed morphology,
  differential considerations, and context limitations

## 10. Review logic and data integrity

- `pni_status=definite` or `probable` requires an evaluable nerve and an
  evaluable cancer–nerve relationship.
- `pni_status=absent` must not be inferred from a missing field.
- `intraneural_component=yes` must be retained even if touching or surrounding
  components are also present.
- Logical conflicts will be flagged for reviewer resolution rather than
  silently corrected. Examples include `nerve_present=no` with
  `pni_status=definite`, or `field_adequacy=not_evaluable` with high confidence.
- The original 120-candidate review CSV and all spatial-pilot inputs remain
  immutable. Input and output SHA256 hashes will be recorded.
- The temporary review-ID mapping will remain separate from the blinded HTML
  and will be joined only after the primary review is locked.

## 11. Endpoints and analysis

### 11.1 Primary endpoint

The primary endpoint is the number and proportion of the 14 foci for which all
core morphology fields are evaluable and internally consistent.

### 11.2 Descriptive secondary endpoints

- counts of definite, probable, absent, uncertain, and not-evaluable PNI;
- counts of touching, surrounding/encasement, intraneural, and mixed patterns;
- counts by section orientation;
- counts of longitudinal tracking and branch-point involvement;
- counts of single- versus multiple-nerve fields;
- raw concordance and transition table between the previous and locked
  re-review PNI/relation labels;
- list of cases advanced to contour annotation;
- list and reasons for adjudication or wider-context review.

Because the original and repeated labels may come from the same reviewer and
the sample contains only 14 selected foci, the study will not present this as
an interobserver-reliability experiment. No hypothesis-testing p-values or
population prevalence estimates will be calculated.

## 12. Expected results

The expected deliverables are:

1. a feasible structured morphology annotation schema for PRECISE PNI;
2. a locked, provenance-preserving morphology table for all 14 nerve foci;
3. identification of labels that are reliably evaluable versus those requiring
   wider context or adjudication;
4. confirmation, revision, or downgrading of each previous PNI assignment
   without assuming that all seven previous positives must remain positive;
5. a documented set of definite/probable PNI and nerve controls suitable for
   second-stage contouring;
6. predefined morphology variables that can later be used in TCGA or other
   cohorts after independent validation.

The study may find no intraneural, longitudinal, or branch-point cases. Such a
result is informative for feasibility and must not be treated as evidence that
those patterns are absent from PRECISE generally.

## 13. Permitted interpretation

If the structured review is completed successfully, the permitted conclusion
is:

> A structured, blinded H&E re-review of 14 previously nerve-positive PRECISE
> candidate foci established the technical feasibility of recording detailed
> cancer–nerve interaction morphology and identified cases suitable for
> subsequent pathologist-drawn contour and spatial-quantification work.

Any numerical statement must explicitly refer to these 14 selected candidate
foci rather than the PRECISE population.

## 14. Prohibited interpretations

- The observed morphology counts estimate the distribution of PNI morphology
  in PRECISE patients.
- A morphology pattern is associated with BCR, prognosis, stage, or molecular
  subtype.
- The AI accurately classifies touching, surrounding, or intraneural PNI.
- Previously or newly PNI-negative candidate fields establish whole-slide PNI
  absence.
- Findings from 14 selected candidates generalize to external cohorts.
- The re-review validates a clinical diagnostic threshold or review budget.

## 15. Expected study artifacts

The subsequent implementation should generate, from one reproducible build
script:

- a blinded multiscale H&E morphology-review interface;
- a private temporary-ID-to-candidate-ID manifest;
- a documented blank export schema;
- a normalized locked morphology-review table;
- a data-integrity and logical-conflict report;
- a previous-versus-re-review transition table;
- a contour-eligibility/adjudication table;
- a concise descriptive results report;
- a run configuration containing seed, source hashes, software versions,
  execution time, and output hashes.

## 16. Next gate

The next stage may begin only after the 14-case morphology review is locked and
logical conflicts are resolved. The pathologist will then draw or correct
actual nerve boundaries and cancer–nerve interface segments for eligible foci.
Only those approved contours may be used for nerve diameter, area, aspect ratio,
encasement fraction, contact length, or distance-gradient analyses.
