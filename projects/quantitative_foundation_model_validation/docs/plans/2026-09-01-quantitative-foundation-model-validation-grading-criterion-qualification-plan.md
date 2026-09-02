---
document_id: 2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-plan
owner_project: quantitative_foundation_model_validation
document_type: implementation_plan
status: superseded
created: 2026-09-01
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/plans/2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-plan.md
implements: projects/quantitative_foundation_model_validation/docs/designs/2026-09-01-quantitative-foundation-model-validation-grading-criterion-qualification-design.md
supersedes: null
superseded_by: projects/quantitative_foundation_model_validation/docs/plans/2026-09-02-quantitative-foundation-model-validation-prostate-diagnostic-anchor-and-discovery-plan.md
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm8_grading_criterion_qualification
  - resources/artifacts/quantitative_foundation_model_validation/fm8_grading_criterion_qualification
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm8_grading_criterion_qualification -v
  - .venv/bin/python -m py_compile projects/quantitative_foundation_model_validation/milestones/fm8_grading_criterion_qualification/audit_fm8_grading_criterion_qualification.py projects/quantitative_foundation_model_validation/milestones/fm8_grading_criterion_qualification/acquire_fm8_par_source.py projects/quantitative_foundation_model_validation/milestones/fm8_grading_criterion_qualification/run_fm8_grading_criterion_qualification.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - git diff --check
---

# Grading-criterion qualification implementation plan

## Dependency rule

The work is divided into four sequential milestones. A later milestone may prepare code or acquire
data, but it may not inspect its scientific result until the preceding milestone gate is decided.
Failure is preserved as a result; an external result must never trigger threshold, reader, scanner,
pooling, tile-selection, or endpoint changes without a new independent cohort.

## M1 — frozen-representation grading accuracy

Objective: determine whether a grading head developed only on PANDA frozen embeddings grades an
independent biopsy cohort. Cancer detection and cancer-only ISUP 1--5 grading are separate
estimands.

| Task | State | Work product | Completion condition |
|---|---|---|---|
| M1.1 Cohort/source lock | complete | PANDA/SICAP/PAR manifests, label distributions, source hashes | roles, identities, reader/scanner rules, missing masks fixed |
| M1.2 Outcome-blind tile preparation | complete | PANDA RGB-only tile cache and locked manifest | 10,616 slides accounted for; exclusions explicit; labels/masks attached only after coordinate selection |
| M1.3 Paired frozen embeddings | complete | QFM-owned CONCH/Virchow arrays and crop-hash audit | every eligible slide embedded; dimensions, weights and identical crop hashes PASS |
| M1.4 Grading-head development | complete | encoder-specific locked ordinal MIL heads and secondary mean-linear checks | architecture and epoch selected using PANDA only; no SICAP/PAR tuning |
| M1.5 PANDA development diagnostics | complete | fixed split predictions and metrics | slide-level diagnostic table complete; explicitly not external evidence |
| M1.6 SICAP qualification | complete | 21-patient/31-slide predictions and clustered intervals | unchanged heads evaluated; prior-open qualification status retained |
| M1.7 PAR confirmatory evaluation | complete | R1/R2 co-primary and R3 subset predictions | 339 Hamamatsu WSI complete/openable/hash-locked; unchanged heads evaluated |
| M1.8 Accuracy gate and clean rerun | complete — both encoders fail adequacy | gate matrix, report, independent rerun hashes | all prespecified metrics and 16/16 nonvolatile hashes reconciled |

The primary head is frozen-encoder gated-attention multiple-instance ordinal classification:
LayerNorm, 256-unit gated attention, weighted pooling of at most 64 outcome-blind tiles, and five
all-threshold logits for ISUP 0--5. Hyperparameters are fixed before external scoring: seed 260901,
batch 16 slides, AdamW learning rate `1e-4`, weight decay `1e-4`, maximum 30 epochs. Epoch selection
uses a single PANDA provider-by-grade stratified development split; the selected epoch is then
refitted on all eligible PANDA slides. A mean-pooled ordinal linear model is reported only as a
secondary architecture check. Its slide-mean features are standardized using PANDA development
statistics during epoch selection and all-PANDA statistics during refit; target-cohort statistics
are never used.

Primary grading accuracy is patient-clustered cancer-only QWK. Secondary endpoints are MAE, exact,
within-one, macro/class recall, severe error, confusion and ordinal calibration. Benign/cancer
AUROC, sensitivity and specificity are separate. PAR reader 1 and reader 2 are co-primary without
inventing a consensus; reader 3 is a prespecified uropathologist subset sensitivity analysis.

Two evidence levels are reported. `ABOVE_CHANCE` requires the patient-bootstrap QWK lower 95% bound
to exceed zero. `ADEQUATE_FOR_FUNCTIONAL_TESTING` additionally requires QWK at least 0.60,
within-one accuracy at least 0.90, and severe-error rate at most 0.05 for both PAR co-primary
readers. Failure blocks M2 functional interpretation and M4 residual entry, but all accuracy
results remain reportable. The gate is applied separately to each encoder: only an encoder that
passes both co-primary readers may enter M2--M3, and failure of one encoder does not invalidate a
passing encoder.

## M2 — cohort-specific clinical criterion representation

Objective: determine which actual grading criteria are recoverable from each frozen encoder, not
merely whether the final ISUP label is predictable.

| Task | State | Work product | Completion condition |
|---|---|---|---|
| M2.1 Specimen-specific rule registry | complete | biopsy/prostatectomy rule table | primary/secondary/minor-pattern rules separated |
| M2.2 Criterion truth registry | complete | GP3/4/5, primary/secondary, cribriform availability matrix | aggregate and subtype truth not conflated; missing truth explicit |
| M2.3 Probe development | locked by M1 failure | PANDA-development criterion directions | Radboud GP3/4/5 only; Karolinska pattern truth prohibited |
| M2.4 Independent recoverability | locked by M1 failure | SICAP Test and PAR reader-conditioned probe metrics | no target-cohort refit; patient-clustered intervals saved |
| M2.5 Representation gate | locked by M1 failure | encoder/criterion gate matrix | only externally recovered directions may enter M3 |

SICAP cribriform is the only currently available GP4 subtype truth. If a cribriform probe is
developed from SICAP Train, the official patient-disjoint Test remains untouched for its
qualification and the probe is explicitly distinguished from PANDA-developed GP3/4/5 probes.

## M3 — functional use and usage allocation

Objective: test whether qualified criterion directions causally support the locked grading head
under representation intervention, and quantify the reliance without claiming a universal single
percentage.

| Task | State | Work product | Completion condition |
|---|---|---|---|
| M3.1 Fixed-head individual erasure | locked by M1 failure | per-criterion accuracy deltas | paired patient bootstrap complete |
| M3.2 Joint erasure | locked by M1 failure | joint clinical-criterion subspace delta | primary functional test complete |
| M3.3 Negative controls and dose response | locked by M1 failure | 100 matched-random controls; 0/25/50/75/100% curves | observed effect exceeds prespecified controls |
| M3.4 Refit sensitivity | locked by M1 failure | replaceability results | clearly separated from fixed-head reliance |
| M3.5 Usage allocation | locked by M1 failure | explained variation, Shapley/dominance, normalized QWK loss | uncertainty and non-additivity reported |
| M3.6 BCR transport | locked by M1 failure | separate CHIMERA C-index reliance table | grading QWK share and BCR C-index share never pooled |

## M4 — shortcut-cleared residual entry and discovery

Objective: search for signal remaining only after known clinical criteria and technical shortcuts
have been removed.

| Task | State | Work product | Completion condition |
|---|---|---|---|
| M4.1 Entry re-audit | locked | updated G1--G10 matrix | M1 accuracy and M3 joint-erasure gates PASS |
| M4.2 Shortcut registry/clearance | locked | scanner/site/color/acquisition sensitivity package | unresolved shortcut candidates excluded |
| M4.3 Residual construction and stability | locked | fold/seed/rank-stable residual scores | patient-level leakage audit and clean rerun PASS |
| M4.4 Localization and blinded pathology review | locked | review packet and adjudication | review authority, protocol and clearance recorded |
| M4.5 External qualification | locked | independent residual replication | no claim before independent recurrence |

## Executed order and terminal state

1. Finish PANDA paired CONCH/Virchow embedding extraction and hash audit.
2. Fit and freeze the PANDA-only ordinal MIL head for each encoder.
3. Produce PANDA development diagnostics without promoting them as validation.
4. Score already embedded SICAP Test without tuning.
5. Complete PAR acquisition/hash/openability, embed Hamamatsu WSI, and run the locked confirmatory
   evaluation.
6. Decide M1 before inspecting M2/M3 scientific effects: both encoders failed
   `ADEQUATE_FOR_FUNCTIONAL_TESTING`, so the run stopped without opening M2--M4.

The executable source-preparation and embedding entry point is
`milestones/fm8_grading_criterion_qualification/run_fm8_grading_criterion_qualification.py`.
It enforces RGB-only coordinate selection, attaches masks afterward, limits GP3/4/5 truth to
Radboud annotations, and records identical decoded-crop hashes across encoders.

## Terminal stop state

PAR source, embedding and confirmatory evaluation are complete. CONCH and Virchow exceeded chance
for both co-primary readers, but neither satisfied all three prespecified adequacy thresholds for
both readers. M1 is therefore closed as a reproducible negative gate result. M2--M4 remain locked;
the PAR result must not be used to retune the head, threshold, pooling, tile rule or endpoint. Any
remediation requires a new protocol and a PAR-independent validation cohort. SICAP remains
prior-open qualification and cannot be relabeled as a pristine confirmatory holdout.
