# PRECISE PNI Pathologist Memo Roadmap Design

Date: 2026-08-06
Status: Approved
Audience: Pathologist performing the blinded 14-focus morphology rereview

## Purpose

Revise the pathologist handoff memo so that it explains not only the immediate
annotation task but also the final research objective, the current decision
gate, and the downstream roadmap. The memo must remain suitable for the
blinded primary H&E review.

## Final research objective

The final objective is to establish a pathologist-in-the-loop PNI research
pipeline in which an AI candidate ranker reduces the review burden,
pathologists confirm and characterize candidate foci, and approved morphology
and contours support reproducible slide-level PNI burden measurements for
later clinical and molecular studies.

The objective is not to establish an autonomous PNI diagnostic model, claim
whole-slide sensitivity, define a clinical top-k threshold, or infer prognosis
from the current 14 selected foci.

## Roadmap

The memo will show the following seven stages:

1. Frozen candidate-ranker technical audit — completed.
2. Blinded structured morphology rereview of 14 nerve-containing fields —
   current stage and current pathologist request.
3. Review lock, integrity/conflict resolution, and contour eligibility — next
   gate.
4. Pathologist-drawn or corrected nerve and cancer–nerve interface contours.
5. Quantification of nerve diameter, encasement, contact length, and spatial
   gradients in the PRECISE method-development set.
6. Pathologist-confirmed slide-level PNI burden construction in larger cohorts
   such as TCGA or biopsy datasets.
7. Clinical/molecular association analyses and independent validation.

## Why the current review is a gate

The first PRECISE candidate review recorded basic nerve and PNI status but did
not systematically capture intraneural involvement, section orientation,
longitudinal tracking, branch-point involvement, multiplicity, or field
adequacy. Contours and quantitative measurements would therefore be
ill-defined if performed before the morphology labels are reviewed and locked.

The pathologist's current task is to determine which fields and labels are
evaluable and internally consistent. Only locked, adequate fields may advance
to contouring. Uncertain, not-evaluable, or wider-context-needed findings must
remain explicit rather than being converted to negative labels.

## Blinding constraints

The revised memo must not disclose prior PNI-positive counts, prior
touching/surrounding counts, original candidate IDs, subject/slide IDs, model
scores, ranks, or strata. It may state that the fixed set comprises 14
previously nerve-containing candidate fields from 10 slides and 10 subjects.

## Document structure

The revised memo will use this order:

1. final research objective;
2. seven-stage roadmap with the current stage highlighted;
3. current progress;
4. why pathologist review is required now;
5. structured fields to review;
6. blinding and uncertainty rules;
7. practical HTML review and CSV submission instructions;
8. interpretation limits and immediate next step after submission.
