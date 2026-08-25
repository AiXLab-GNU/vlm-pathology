---
document_id: 2026-08-21-quantitative-foundation-model-validation-chimera-external-functional-xai-design
owner_project: quantitative_foundation_model_validation
document_type: design
status: approved
created: 2026-08-21
owner: Jin Hyun Kim (PM)
canonical_path: projects/quantitative_foundation_model_validation/docs/designs/2026-08-21-quantitative-foundation-model-validation-chimera-external-functional-xai-design.md
implements: null
supersedes: null
artifact_roots:
  - projects/quantitative_foundation_model_validation/milestones/fm6_chimera_external_functional_validation
  - resources/artifacts/quantitative_foundation_model_validation/fm6_chimera_external_functional_validation
verification:
  - .venv/bin/python -m unittest projects.quantitative_foundation_model_validation.tests.test_fm6_chimera_external_functional_xai -v
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
  - .venv/bin/python infrastructure/scripts/audit_worktrees.py
  - git diff --check
---

# FM6 CHIMERA external functional XAI failure-decomposition design

## 1. Decision, ownership, and publication gate

### 2026-08-24 accountable-author release amendment

After reviewing publicly released studies using CHIMERA data, the accountable author determined
that the CHIMERA embargo had ended and authorized promotion of aggregate results into the
controlled revision manuscript. This decision does not assert that written organizer clearance
was obtained. It supersedes only the release prohibition below; it does not alter the
preregistered cohort, endpoint, model, intervention, uncertainty, gate, or claim boundary.
Patient-level predictions, embeddings, crops, WSI, and other restricted/local artifacts remain
unpublished.

This is a new FM6 analysis unit owned only by
`quantitative_foundation_model_validation`. It does not extend the acquisition milestone and
does not consume another project's generated output. The runner is active project source;
design, plan, and protocol are active controlled documents; every generated crop, embedding,
patient prediction, outcome-derived table, report, and run record is a local generated artifact
under the declared resource root.

The official CHIMERA data page and challenge rules were checked on 2026-08-21 before execution:

- `https://chimera.grand-challenge.org/dataset-download/`
- `https://chimera.grand-challenge.org/challenge-rules/`

Both state that results from CHIMERA public training data may not be published until both the
CHIMERA challenge journal paper and baseline journal paper are published. The official pages
still display that embargo, and no accountable-author written clearance artifact is present in
this repository. The locked state is therefore `EMBARGO_ACTIVE_NO_WRITTEN_CLEARANCE`; the
embargo end is not inferred from third-party papers or challenge completion.

The user authorizes internal analysis. During the embargo, no outcome-derived result may be
written to a tracked milestone output, manuscript, public repository, submission package,
release, or tag. Only this outcome-free preregistration package is committed before execution.

## 2. Scientific decomposition

The independent CHIMERA Task 1 cohort decomposes the locked LEOPARD failure in order:

1. external representation: does the TCGA-locked ISUP probe recover source-reported CHIMERA
   ISUP?
2. external head: does the TCGA-locked BCR head discriminate CHIMERA BCR?
3. functional sensitivity: does removing the TCGA-locked ISUP-correlated direction reduce
   CHIMERA BCR discrimination more than variance-matched random-direction removal?

No CHIMERA head, direction, threshold, crop rule, aggregation, endpoint, subset, or gate is
trained or selected. CHIMERA outcomes cannot be used for tuning even if the embargo later ends.

## 3. Locked sources and universe

- TCGA source: the immutable FM6 392-subject/80-event development representation used by the
  LEOPARD and site-held-out analyses.
- CHIMERA source: manifest `resources/data/manifests/chimera_task1.yaml`, local inventory hash
  `06cd367f8c28a47c8da55ed3198c81a5ba8effb1b971eef97e8809ec18eabca0`, and normalized
  clinical hash `95e62aa7c0a70d065fbaa3bf9d688f7f7d2c7fc0b27635cb190331ad042773bb`.
- Membership: 95 subjects, 27 BCR events, 190 prostatectomy WSI, and 190 paired official tissue
  masks. Every subject and every slide is required.
- BCR: source definition PSA at least 0.1 micrograms/L after surgery; time is months. This is
  not asserted to be endpoint-equivalent to TCGA.
- ISUP primary: unmodified source-reported Grade Group in all 95 subjects.
- ISUP sensitivity: the prespecified 92 subjects whose reported ISUP agrees with the standard
  primary/secondary Gleason mapping. The three discrepancies are never corrected or silently
  excluded, and neither result may be selected because it is more favorable.

A missing, duplicate, corrupt, unpaired, or unhashable source is an integrity failure with no
scientific interpretation.

## 4. Locked image and aggregation contract

- CONCH and Virchow are both frozen at the revisions and weight hashes used by TCGA FM6.
- Physical source FOV is 394.24 micrometres. Native MPP is read from TIFF resolution metadata
  by the existing TCGA routine; no nominal magnification substitution is allowed.
- Sampling uses only the official CHIMERA foreground/background tissue mask. It is not a tumor
  mask and creates only whole-tissue evidence.
- The LEOPARD deterministic tissue-fraction thresholds, coordinate ordering, maximum of 64
  crops per WSI, seed 260820, and canonical 448 by 448 RGB image are retained. Every one of the
  190 WSI must yield exactly 64 crops; otherwise execution stops before analysis.
- One shared canonical crop cache feeds both encoders. Slide, coordinate, tile identity,
  decoded source-RGB SHA-256, and row order must match one-to-one across encoders.
- Primary aggregation is crop mean within WSI, followed by equal-weight mean of slide
  embeddings within subject. Thus each of 95 patients has analysis weight one regardless of
  having 1 to 12 slides.
- Pooled-crop and tissue-area-weighted alternatives are not primary and are not executed in
  this analysis family.

## 5. TCGA-locked model and intervention

For each encoder, use exactly the final external model family already locked for LEOPARD:

- StandardScaler fitted on the complete TCGA development representation only;
- randomized PCA rank 64 with seed 260820;
- CoxPH ridge alpha 1000 fitted on TCGA BCR only;
- Ridge alpha 1000 fitted on TCGA ISUP in that same standardized representation;
- the Ridge coefficient is the locked rank-one ISUP-correlated erasure direction;
- 100 TCGA-training-derived variance-matched random directions;
- no CHIMERA fit, calibration, refit, feature selection, thresholding, or subset selection.

The unchanged head scores the full, target-erased, and random-erased CHIMERA representations.

## 6. Estimands and uncertainty

### A. External ISUP recoverability

Report Spearman rho and a 2,000-draw patient bootstrap 95% percentile interval for the all-95
primary universe and concordant-92 sensitivity. The scale and positive direction match TCGA.
The primary recoverability gate passes only when the all-95 interval lower bound is above zero;
the 92-subject result cannot replace it.

### B. External BCR-head validity

Report patient-level Harrell censored C-index and a 2,000-draw patient bootstrap 95% interval.
The fixed validity gate passes only when the lower bound exceeds 0.50.

### C. Functional erasure

Define `delta_use = C(full fixed head) - C(target-erased fixed head)`. Report its paired
patient-bootstrap interval, the 100 matched-random deltas, random p95, the finite-sample
one-sided permutation-style p-value `(1 + count(random_delta >= target_delta)) / 101`, and
Holm adjustment across CONCH and Virchow. An encoder passes only if all are true:

1. its full BCR-head validity gate passes;
2. target `delta_use` interval lower bound is greater than zero;
3. target delta is strictly greater than matched-random p95;
4. Holm-adjusted p-value is at most 0.05.

A positive erasure delta cannot rescue an invalid full head.

## 7. Prespecified cause states

Each encoder receives exactly one state in this order:

1. `INTEGRITY_FAILURE_NO_SCIENTIFIC_INTERPRETATION` for any source, membership, crop, row,
   finite-value, or paired-encoder failure;
2. `ISUP_NOT_RECOVERABLE_EXTERNAL_REPRESENTATION_SHIFT` when all-95 rho is non-positive;
3. `FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION` when a positive ISUP rho, full-head C-index above
   0.50, or positive target delta fails only because its patient-bootstrap interval includes
   its null boundary;
4. `ISUP_RECOVERABLE_BCR_HEAD_NOT_TRANSPORTED` when ISUP passes but the full-head point C-index
   is at or below 0.50;
5. `BCR_HEAD_TRANSPORTED_FUNCTIONAL_ERASURE_NOT_QUALIFIED` when ISUP and full-head gates pass
   but target erasure is non-positive or fails the matched-random/Holm criteria;
6. `QUALIFIED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT` when all three stages pass.

The overall state is the most conservative encoder state in the same order. All interpretations
must explicitly note that only 27 events constrain precision.

## 8. Reproducibility and stop rules

- Patient, never slide or crop, is the bootstrap unit.
- Coordinates and shards are deterministic and resumable; a completed cache is reused only
  after tile identity, shape, finiteness, and order validation.
- Save source/output SHA-256, preregistration code commit, package/model versions, CUDA/GPU
  identity, runtime, subjects, events, slides, masks, and crop counts locally.
- Execute a second clean analysis run and require exact equality of every nonvolatile aggregate
  and patient-level output hash.
- Stop without scientific interpretation on missing/duplicate rows, cross-encoder crop-hash
  mismatch, fewer or more than 64 crops for any WSI, nonfinite representation, source-hash
  mismatch, or altered TCGA immutable input.

## 9. Claim boundary

At most, a fully passing encoder supports internal embargo-controlled evidence of external
whole-tissue transport of a TCGA-locked functional sensitivity. It does not establish a tumor
mask, tumor-specific mechanism, endpoint equivalence, clinical deployment, clinical increment,
indispensability, encoder superiority, prospectively untouched confirmation, or a new biomarker.
At execution lock, numeric CHIMERA results were not public evidence. The 2026-08-24
accountable-author amendment permits aggregate-result promotion without changing this scientific
claim ceiling.
