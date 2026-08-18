---
document_id: prostate-biomarker-validation-plan
owner_project: prostate_biomarker_validation
document_type: research_plan
status: active
created: 2026-08-13
canonical_path: projects/prostate_biomarker_validation/docs/research_plan/01-prostate-biomarker-validation-plan.md
hierarchy_id: 01
parent_document: null
---

# Prostate biomarker validation research plan

This is the governing research plan for qualification and transport of prostate pathology
foundation-model signals. It consolidates only scope already established by the project
entry documents and approved designs; it does not reopen frozen endpoints or analyses.

- Canonical milestones: [01-01-prostate-biomarker-validation-milestones.md](01-01-prostate-biomarker-validation-milestones.md)
- Current execution tracker: [01-01-01-prostate-biomarker-validation-execution-tracker.md](01-01-01-prostate-biomarker-validation-execution-tracker.md)
- Related-work input: [survey index](../surveys/README.md)
- Claim boundary: [CLAIM_BOUNDARIES.md](../../CLAIM_BOUNDARIES.md)

## Research problem and questions

The study asks which pathology foundation-model signals for grade, phenotype, molecular
markers, recurrence, and survival remain interpretable after qualification across cohorts,
sites, endpoints, encoders, scales, and confounders. The governing questions are:

1. Which evaluated signals transport across the available cohorts?
2. Which signals are materially context-sensitive to site, encoder, scale, endpoint, or
   sampling configuration?
3. Which proposed effects are unsupported in the frozen design without implying biological
   absence?
4. Can every manuscript claim be traced to a saved source table, endpoint definition, and
   approved analysis family?

## Working hypotheses

- Grade and evaluated phenotype signals will show stronger transport evidence than the
  molecular and recurrence signals in the current frozen study.
- Pooled discrimination alone is insufficient for qualification; site, confounder,
  endpoint, and stability audits may narrow an apparent effect.
- The 360-cell stability grid is correlated sensitivity analysis, not 360 independent
  validations.

These are study hypotheses and interpretation rules, not guaranteed outcomes.

## Scope and non-goals

The project owns TCGA-PRAD, NADT-Prostate, PANDA, and LEOPARD analyses for ERG, PTEN, SPOP,
AR, grade/phenotype, recurrence, and survival endpoints already registered in its frozen
records. It preserves cohort, site, endpoint, fold, and source provenance.

It does not claim clinical validation, treatment utility, population prevalence, causal
mechanism, autonomous whole-slide diagnosis, universal encoder superiority, or endpoint
equivalence. Frozen outputs, endpoints, folds, and prespecified analysis families are not
silently relabeled, recalibrated, or optimized.

## Evaluation units and evidence states

The analysis unit, denominator, event count, endpoint source, complete-case count, and
uncertainty construction must accompany each result. Evidence is reported as
`transportable`, `context-sensitive`, or `unsupported in the frozen design` only when the
saved analysis supports that state. Undefined and underpowered results remain explicit.

## Baseline and analysis direction

Comparisons use the frozen encoders, scales, folds, endpoints, clinical covariates, site
audits, external-cohort evaluations, and stability grid documented by the approved study
and manuscript designs. New analysis families require a separate approved design; paper
revision may summarize but must not change the frozen science.

## Success, narrowing, stopping, and pivot criteria

Success requires complete source-to-claim lineage, explicit endpoint distinctions,
reproducible figure/table generation from saved source tables, and claims bounded by the
available transport, confounder, site, and stability evidence. A target is narrowed when
its evidence is site-, endpoint-, encoder-, scale-, or configuration-dependent. A claim is
stopped when integrity reconciliation fails, an endpoint is substituted, the analysis is
underpowered or undefined, or the frozen design does not support it. Additional experiments
or external cohorts require an approved plan rather than retrospective reinterpretation.

## Cross-project manuscript handoff

The frozen analyses and source tables remain owned by this project. The derivative
alignment-centered manuscript under `quantitative_foundation_model_validation` may use only
items enumerated in its hash-locked source-evidence manifest. That manuscript may interpret
recoverability and transport as candidate shared interpretive coordinates, but it may not
reinterpret them as functional use by a disease-prediction head. The original PBV submission
bundle remains unchanged provenance and is not a compatibility copy of the derivative paper.
