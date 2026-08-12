# File-governance baseline report

Date: 2026-08-12
Owner: Jin Hyun Kim (PM)
Scope: repository-managed documents, source code, tests, web assets, and structured records

## Outcome

The repository now has a file-level contract in addition to its directory-level contract.
Every managed file is assigned one owner, file class, lifecycle, provenance role, naming
status, metadata status, size, and SHA-256 digest in
`FILE_GOVERNANCE_BASELINE.csv`.

The final baseline contains 627 classified files and zero unclassified files, naming
violations, or required-metadata violations. Of these, 554 use canonical names and 73 retain
baseline-backed fixed contract names. The unusually large exception-scope count is not a
waiver for new disorder: it mostly reflects frozen P0/FM bundles, manuscript provenance,
generated evidence, 85 historical biomarker scripts, and 10 historical design records.
Closed legacy scopes reject files that were not present in the baseline.

## Decisions

- Active/new Markdown uses lowercase kebab-case; Python and shell use lower snake_case.
- `FILE_NAMING_CODEX.md` defines templates, reserved contract names, prohibited editorial
  tokens, and the required pre-hash/post-hash rename protocol.
- Designs and plans require dated names, explicit suffixes, and a metadata header.
- Stable clinician, publication, milestone, and provenance contracts keep their existing
  names; cleanup does not overwrite traceability.
- Generated records are regenerated from their entry point and are not hand-edited.
- Legacy biomarker code and `docs/study_design/` are closed to new files.
- Each project now has code/document indexes explaining its active, frozen, generated,
  and legacy surfaces.
- Each project has a required `00-project-sequence/README.md` that presents scientific
  stages in numbered order while preserving canonical executable and provenance paths.
- The repository boundary validator invokes the file-governance auditor automatically.
- Four safe active documents were renamed to canonical semantic basenames; the exact
  pre/post hashes and reference dispositions are recorded in `file-rename-map.csv`.

## Scientific effect

This migration changed organization metadata and policy only. It did not change study
labels, model scores, endpoints, analysis outputs, claims, or immutable clinical sources.

## Verification

The authoritative verification commands are:

```bash
.venv/bin/python infrastructure/scripts/audit_file_governance.py
.venv/bin/python infrastructure/scripts/validate_project_boundaries.py
.venv/bin/python -m unittest discover -s infrastructure/tests -p 'test_*.py' -v
```

The baseline catalog is deliberately excluded from cataloging itself so its content hash
does not create a self-referential record.

Final verification passed the file audit, repository boundary audit, immutable PNI hash,
broken-symlink scan, syntax check, and infrastructure 5/5, PNI 37/37, quantitative 30/30,
shared-metric 14/14, paper-artifact 34/34, and paper-package 39/39 tests. The manuscript
contract retained its known single Funding-declaration mismatch (53/54): the current
NRF/GNU declaration is intentionally not overwritten with the obsolete ICT wording expected
by that test. The governance portal responded on host loopback `127.0.0.1:8011`.
