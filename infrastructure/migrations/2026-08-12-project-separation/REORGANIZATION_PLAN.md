# Repository project-separation plan

Date: 2026-08-12
Owner: Jin Hyun Kim (PM)

## Goal

Separate the former mixed repository into three independently governed scientific
projects while preserving reproducibility and old command paths:

1. PRECISE PNI candidate triage
2. Quantitative foundation-model validation
3. Prostate biomarker validation and its manuscript

Shared datasets, model assets, and utilities are registered separately. Sharing a cohort
or encoder does not share labels, endpoints, approvals, or claims.

## Migration milestones

- ORG-M0: inventory every managed file, record size/hash/tracking state, and classify it.
- ORG-M1: create canonical project roots and per-project scientific boundaries.
- ORG-M2: move documents, code, tests, outputs, and paper sources to their owner.
- ORG-M3: repair references, add compatibility symlinks, and validate tests and services.
- ORG-M4: publish the migration audit and record it in the quantitative study plan.

Historical result records are not textually rewritten. Compatibility links preserve their
old logical paths while new work uses canonical paths.
