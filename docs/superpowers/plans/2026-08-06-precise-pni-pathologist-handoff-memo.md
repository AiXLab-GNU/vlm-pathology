# PRECISE PNI Pathologist Handoff Memo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a concise Korean handoff memo that lets the pathologist understand and complete the blinded 14-focus PRECISE PNI morphology rereview without exposing prior labels or model information.

**Architecture:** One standalone Markdown memo will separate study context from actionable review instructions. Its wording will be derived from the approved morphology rereview design and will deliberately omit prior positive counts, previous morphology labels, candidate identities, scores, ranks, and strata.

**Tech Stack:** Korean Markdown documentation.

## Global Constraints

- The memo is for the blinded primary H&E rereview.
- Do not disclose the previous PNI-positive count or touching/surrounding distribution.
- Do not disclose original candidate IDs, subject/slide IDs, scores, ranks, or strata.
- Refer to cases only by temporary IDs in the form `MORPH-###`.
- State that missing, uncertain, and not-evaluable findings must not be converted to `no`.
- State that this is a 14-focus method-development pilot, not prevalence, prognosis, AI diagnostic-accuracy, or whole-slide sensitivity validation.

---

### Task 1: Write and verify the pathologist handoff memo

**Files:**
- Create: `docs/PRECISE_PNI_MORPHOLOGY_REREVIEW_PATHOLOGIST_MEMO_KO.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-06-precise-pni-morphology-rereview-design.md`
- Produces: A standalone Korean memo that can accompany `precise_pni_morphology_review.html`.

- [ ] **Step 1: Write the one-page memo**

Include: current goal, study purpose, progress, why rereview is needed, what to review, how to handle uncertainty, practical HTML/export instructions, and limitations.

- [ ] **Step 2: Verify blinded wording**

Confirm the memo contains none of the 14 original candidate IDs, prior positive counts, previous touching/surrounding counts, model scores, ranks, or strata.

- [ ] **Step 3: Verify actionability**

Confirm every structured review field from the approved design is either listed explicitly or grouped without losing meaning, and that the reviewer is told to export the completed CSV.

- [ ] **Step 4: Review readability**

Confirm the memo is concise, uses plain Korean, distinguishes the current morphology-label stage from the later contour stage, and has no placeholder language.

### Task 2: Add the final objective and research roadmap

**Files:**
- Modify: `docs/PRECISE_PNI_MORPHOLOGY_REREVIEW_PATHOLOGIST_MEMO_KO.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-06-precise-pni-pathologist-memo-roadmap-design.md`
- Produces: A clinician-facing roadmap that identifies the current rereview as the gate before contouring and quantitative analysis.

- [ ] **Step 1: Add the final research objective**

State that the long-term goal is a pathologist-in-the-loop pipeline combining AI candidate triage, specialist confirmation, morphology/contour quantification, and later larger-cohort clinical or molecular research. Explicitly exclude autonomous diagnosis and whole-slide sensitivity claims.

- [ ] **Step 2: Add the seven-stage roadmap**

List the frozen-score audit, current 14-focus rereview, review lock, contouring, PRECISE quantification, larger-cohort burden construction, and independent clinical/molecular validation. Mark stage 2 as the current requested pathologist task.

- [ ] **Step 3: Explain the current decision gate**

State that morphology labels must be evaluable and internally consistent before a case advances to contouring, and that uncertain/not-evaluable findings remain explicit.

- [ ] **Step 4: Verify scope and blinding**

Confirm the revised memo contains the final objective and all seven roadmap stages but no previous PNI-positive count, prior morphology distribution, original candidate ID, model score, rank, or stratum.
