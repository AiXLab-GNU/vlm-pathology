# File Governance Codex

Version: 1.2
Effective date: 2026-08-13
Owner: Jin Hyun Kim (PM)
Status: active repository policy

## 1. Purpose

This policy governs every document and source-code file after its owning project and root
location have been selected through `PROJECT_STRUCTURE_CODEX.md`. A file is not governed
merely because it is inside the correct project: it must also have one declared role, one
lifecycle state, a canonical name, and a defined source/generated relationship.

The current repository contains historical and frozen paths that are part of recorded
provenance. Those files are catalogued and quarantined rather than cosmetically renamed.
An exception preserves reproducibility; it does not establish a naming precedent.

## 2. Required file attributes

Every managed document or code file has exactly these attributes:

- `owner`: repository or one project ID;
- `file_class`: a value registered in `FILE_TYPE_REGISTRY.csv`;
- `lifecycle`: `active`, `frozen`, `generated`, `legacy`, `archive`, or `runtime`;
- `canonical_path`: its one authoritative location;
- `naming_status`: compliant or a documented exception;
- `provenance_role`: source, derived source table, generated product, or record.

Files without a class are prohibited. `misc`, `new`, `copy`, `temp`, `final2`, a person's
name, or an agent/tool name is not a valid class.

## 3. Document contract

### 3.1 Canonical locations

```text
projects/<project_id>/docs/
├── README.md          document index and lifecycle map
├── designs/           approved scientific designs
├── plans/             executable implementation plans
├── protocols/         machine-facing study protocols
├── pathologist_protocol/ clinician-facing fixed protocols, when applicable
├── research_plan/     numbered research-programme hierarchy
├── project_plan/      numbered project-plan hierarchy
├── metric_taxonomy/   controlled metric definitions
├── surveys/           literature/landscape synthesis
├── references/        local reference notes, not evidence outputs
└── legacy/            closed historical narrative; no new active documents
```

Only relevant directories are created. Reports belong in `reports/`, manifests in
`manifests/`, manuscript material in `paper/`, and generated evidence in an approved
milestone/output or resource artifact root.

### 3.1.1 Canonical control set and related-work authority

Every registered research project declares exactly one governing research plan, one
milestone refinement, one execution tracker, and one survey index through `PROJECT.yaml`.
The three control documents form a real ancestry chain; root `MILESTONES.md` is only a fixed
summary/navigation contract. The research plan owns questions, hypotheses, scope, claim
boundaries, evaluation units, baseline direction, and success/narrow/stop/pivot criteria.
Milestones own work packages, prerequisites, evidence gates, status, outputs, and completion
criteria. The tracker owns the current milestone, blocker, single next action, completion
checklist, recent decision, and next transition condition.

`docs/surveys/README.md` registers all maintainable surveys and notes using only
`PLANNED`, `CURRENT`, `SUPPORTING`, `HISTORICAL`, or `SUPERSEDED`. `SUPERSEDED` links its
replacement. A `CURRENT` survey is linked from the governing research plan and records, in
the document or a sidecar, the plan, survey date, databases, scope, inclusion/exclusion
criteria, supported questions, supported baseline/method decisions, and downstream
documents. Unknown fields remain `unrecorded` or explicit TODOs. Manuscript related-work
prose is a summary output, not a competing authority.

### 3.2 Document names

- General active Markdown: `lowercase-kebab-case.md`.
- Governing programme plan: `NN-<topic>-plan[-ko].md`.
- Child milestone/workstream: `NN-NN-<topic>[-ko].md`.
- Child task/support document: `NN-NN-NN-<topic>[-ko].md`.
- Design: `YYYY-MM-DD-<project-id>-<topic>-design.md`.
- Plan: `YYYY-MM-DD-<project-id>-<topic>-plan.md`.
- Report: `<milestone-id>-<topic>-report.md` or a protocol-defined stable identifier.
- Korean language is marked with `-ko`; English is unmarked unless another language must be
  distinguished.
- `README.md`, `AGENTS.md`, `CLAIM_BOUNDARIES.md`, `MILESTONES.md`, `PROJECT.yaml`, and
  approved clinician-facing identifiers are fixed contract names.

The numeric segments are ancestry identifiers, not flat sequence numbers. A child inherits
the complete parent prefix, and every parent must exist. The File Naming Codex is
authoritative for hierarchy depth, plan precedence, exclusions, and rename stability.

Do not encode editorial state with `new`, `latest`, `final`, `final2`, `copy`, or version
suffixes. Use front matter fields `status`, `supersedes`, and a dated change log.

### 3.3 Metadata

Every new design and plan must use
`infrastructure/docs/repository/templates/SUPERPOWERS_DOCUMENT_HEADER.md`. New protocols,
research plans, and formal reports must declare, either in YAML front matter or a registered
sidecar manifest: `document_id`, `owner_project`, `document_type`, `status`, `created`, and
`canonical_path`. Existing frozen contracts may use the repository file catalog as their
sidecar metadata.

Canonical research plans, milestones, and execution trackers additionally declare their
document ID, owner project, document type, status, canonical path, hierarchy ID, and parent
document (`null` for the level-1 plan).

## 4. Code contract

### 4.1 Canonical roles

```text
projects/<project_id>/code/
├── README.md          entry-point and module index
├── entrypoints/       one auditable CLI/orchestrator per analysis
├── lib/               importable project-specific pure/domain functions
├── adapters/          dataset/model/format integration boundaries
└── legacy/            frozen historical scripts; no new development
```

A scientifically meaningful domain directory may replace the generic role directory when
its `code/README.md` maps every file to one of these roles. Quantitative FM and frozen P0
entry points may remain beside their protocol/output bundles when the milestone itself is
the audit unit.

Repository operations go to `infrastructure/scripts/`; reusable installable code goes to
`infrastructure/packages/<package>/src/`; browser code stays with its owning web application.

### 4.2 Code names and interfaces

- Python and shell: `lower_snake_case.py` / `lower_snake_case.sh`.
- Tests: `test_<unit>.py` and one test file per auditable unit where practical.
- Analysis entry points begin with an action verb: `run_`, `build_`, `audit_`, `extract_`,
  `prepare_`, `validate_`, or a registered historical `pilot_`.
- Importable modules describe a domain noun or operation and do not use milestone prose.
- JavaScript/CSS/HTML assets use lowercase kebab-case, except fixed web entry names such as
  `app.js`, `index.html`, and `styles.css`.
- New scripts must not use absolute machine paths or import a compatibility root.

One analysis has one canonical entry point. Helper logic moves to `lib/` only when tested;
copying a helper between projects is prohibited.

## 5. Lifecycle rules

- `active`: may be edited under its current design and must satisfy current naming rules.
- `frozen`: input to an approved result or hash manifest; content and path do not change.
- `generated`: recreated from declared sources; never hand-edited.
- `legacy`: retained for provenance; no new feature work or new sibling files.
- `archive`: read-only historical snapshot under `resources/artifacts/.../archives/`.
- `runtime`: disposable service/tool state; not a scientific record.

Promotion from legacy to active is a controlled extraction: create tested canonical code,
record the old source hash, update consumers, then leave or archive the old path. Do not
silently modernize frozen code in place.

## 6. Manuscript bundle rule

`projects/prostate_biomarker_validation/paper/` is a specialized publication bundle. Its
configuration owns the exact paths of TeX sources, figure renderers, source tables, manifests,
and generated tables. Paths referenced by saved provenance remain stable. New revision notes
must go under `paper/revision/`; new renderers under `paper/figures/`; generated tables under
`paper/generated/`. Build logs and auxiliary files are ignored and are not documents.

## 7. Exceptions and enforcement

Grandfathered paths are listed by the narrowest possible pattern in
`FILE_GOVERNANCE_EXCEPTIONS.csv`, with owner, lifecycle, reason, and disposition. An exception
may permit a path to remain, but never permits another file to copy its irregular name.

Required checks:

1. `.venv/bin/python infrastructure/scripts/audit_file_governance.py`
2. `.venv/bin/python infrastructure/scripts/validate_project_boundaries.py`
3. owning-project tests and syntax checks
4. regenerate the catalog after an intentional structural migration

The current full catalog is an audit product, not a hand-maintained source of truth. The
auditor must classify every managed document/code file and report zero unclassified files
and zero unregistered naming violations.

Catalog checksums are point-in-time migration inventory values. Exact baseline checksum
enforcement applies to non-generated files. A file with lifecycle `generated` may contain
protocol-declared volatile fields, so its reproducibility and integrity are enforced by the
owning project's output manifest and tests rather than by the repository migration catalog.

An active rename is atomic: classify the source, record old/new paths and hashes in a dated
migration map, move once, update active code/configuration/tests/indexes/metadata, and verify
links and stale paths in the same change. Frozen, generated, legacy, archive, third-party,
external-template, and closed-migration records keep historical path strings when required
for provenance.

Filename syntax and rename procedure are governed by `FILE_NAMING_CODEX.md`. This document
defines ownership, class, lifecycle, and placement; the naming Codex is the authoritative
basename contract.
