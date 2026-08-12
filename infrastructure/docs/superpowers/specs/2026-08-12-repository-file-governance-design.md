---
document_id: 2026-08-12-repository-file-governance-design
owner_project: repository
document_type: design
status: implemented
created: 2026-08-12
owner: Jin Hyun Kim (PM)
canonical_path: infrastructure/docs/superpowers/specs/2026-08-12-repository-file-governance-design.md
implements: infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md
supersedes: null
artifact_roots:
  - infrastructure/docs/repository
  - infrastructure/scripts
  - infrastructure/migrations/2026-08-12-file-governance
verification:
  - .venv/bin/python infrastructure/scripts/audit_file_governance.py
  - .venv/bin/python infrastructure/scripts/validate_project_boundaries.py
---

# Repository File Governance Design

## Objective

Give every document and code file an enforceable owner, class, lifecycle, naming contract,
and canonical location without invalidating frozen scientific provenance.

## Decisions

1. Apply strict current naming to new and active files.
2. Preserve frozen, generated, and legacy names through narrow registered exceptions.
3. Quarantine legacy code: no new development is permitted in `code/legacy`.
4. Treat the biomarker paper as a configuration-owned publication bundle rather than a
   generic document directory.
5. Permit quantitative milestone entry points beside their frozen protocol/output unit.
6. Generate a full catalog mechanically and fail when any managed document or code file is
   unclassified or has an unregistered naming violation.

## Non-goals

- No scientific redesign, relabeling, result regeneration, or claim expansion.
- No cosmetic rename of frozen manifests, approved clinician handoffs, or saved paper paths.
- No extraction of legacy scientific code without focused equivalence tests.

## Completion criteria

- File Governance Codex and type/exception registries exist.
- Each project has a documentation and code routing index.
- The auditor classifies 100% of managed documents and source code.
- Boundary validation invokes the auditor.
- Baseline catalog reports zero unclassified files and zero unregistered violations.
