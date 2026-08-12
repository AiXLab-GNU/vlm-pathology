# File Naming Codex

Version: 1.0
Effective date: 2026-08-12
Owner: Jin Hyun Kim (PM)
Status: active repository policy

## 1. Authority and purpose

This Codex is the mandatory filename contract for every new or renamed repository file.
`PROJECT_STRUCTURE_CODEX.md` decides where a file belongs; `FILE_GOVERNANCE_CODEX.md`
decides its owner, class, and lifecycle; this document decides its basename. A file is not
ready to create until all three decisions are known.

The governing principle is semantic stability: a name identifies the file's durable role,
not its temporary editing state. Existing names that are part of frozen evidence,
clinician-facing handoffs, generated bundles, manuscript build contracts, or the user's
fixed milestone-log path are `fixed contract names`, not examples for new files.

## 2. Universal rules

- Use ASCII lowercase for ordinary names.
- Use `-` between words in prose documents and web assets.
- Use `_` between words in Python, shell, and machine-oriented record names.
- Use the actual file type extension once; do not encode format twice.
- Prefer a precise scientific noun over generic names such as `notes`, `misc`, `data`,
  `results`, or `output`.
- Never use editorial-state tokens such as `copy`, `latest`, `new`, `temp`, `final2`, or
  a person's desktop filename suffix.
- Encode language only when multiple language variants can coexist: `-ko`, `-en`.
- Encode versions only when the schema or protocol requires them. Prefer a date or a
  manifest field over `v2`, `v3`, or `revised-final`.
- A filename change never changes scientific meaning. Content revision and path migration
  are reviewed and recorded separately.

## 3. Naming templates by file class

| Class | Template | Example |
|---|---|---|
| design | `YYYY-MM-DD-<project>-<topic>-design.md` | `2026-08-12-repository-file-governance-design.md` |
| implementation plan | `YYYY-MM-DD-<project>-<topic>-plan.md` | `2026-08-12-repository-file-naming-plan.md` |
| ordered Korean document | `NN-<topic>-ko.md` | `17-medical-quantitative-metric-tier-taxonomy-ko.md` |
| protocol | `<scope>-protocol[-ko].md` | `contour-review-protocol-ko.md` |
| report | `<milestone>-report.md` | `fm4-concept-benchmark-report.md` |
| migration report | `<topic>-report.md` | `file-governance-report.md` |
| Python module | `<lower_snake_case>.py` | `audit_file_governance.py` |
| executable Python | `<verb>_<object>.py` | `validate_project_boundaries.py` |
| Python test | `test_<subject>.py` | `test_file_governance.py` |
| shell entry point | `<verb>_<object>.sh` | `run_portal_forever.sh` |
| HTML/CSS/JS | `<lower-kebab-case>.<ext>` | `metric-atlas.html` |
| CSV/TSV/JSON/YAML | `<lower_snake_case>.<ext>` | `paired_sample_manifest.csv` |
| figure source | `fig<index>_<topic>.py` | `fig3_molecular_qualification.py` |
| generated figure | same stem as renderer/source contract | `fig3_molecular_qualification.pdf` |

`README.md`, `AGENTS.md`, `CLAIM_BOUNDARIES.md`, `MILESTONES.md`, `PROJECT.yaml`, and
repository policy/registry names listed by the auditor are reserved contract names.

## 4. Scope and identity rules

- Each project reserves the directory name `00-project-sequence/` for its ordered stage
  index. No other numeric-prefix project-root directory is created without amending the
  Project Structure Codex.
- Do not add numeric prefixes to canonical executable or evidence directories merely to
  affect file-browser sorting. Represent logical order in `00-project-sequence/README.md`.
- Do not repeat the project ID when the owning directory already makes it unambiguous,
  except in dated design/plan names where global searchability is intentional.
- A milestone ID precedes the topic when it is the stable execution identity.
- Use `manifest`, `registry`, `schema`, `report`, `protocol`, `design`, or `plan` only when
  the file actually fulfills that class.
- A generated artifact inherits the stem defined by its generator or protocol. Ad hoc
  renaming of generated files is prohibited.
- Do not distinguish files only by capitalization. Names must remain unambiguous on
  case-insensitive filesystems.

## 5. Fixed contract names

A noncanonical historical name is permitted only when renaming would break one of these:

1. a frozen input/output hash or clean-rerun comparison;
2. a clinician-facing schema or approved handoff;
3. a manuscript builder, source manifest, or submission artifact contract;
4. a milestone bundle with protocol-defined output names;
5. an explicitly user-mandated canonical path;
6. a repository policy name reserved by the auditor.

Fixed contracts must already exist in the file-governance baseline or have an exact,
reviewed registry entry. They are closed precedents: a new file cannot copy their legacy
style. Broad exception directories do not exempt a new noncanonical filename.

## 6. Rename protocol

Before renaming an existing file:

1. classify it as active, frozen, generated, legacy, or fixed contract;
2. search code, tests, documents, manifests, and generated configuration for the old path;
3. stop if a frozen hash/path contract cannot be migrated without changing evidence;
4. record old path, new path, reason, pre-hash, post-hash, and reference disposition in a
   dated migration map;
5. rename once to the canonical name and update active references atomically;
6. do not rewrite closed migration inventories or frozen records merely to erase the old
   name; those records are historical evidence;
7. run file-governance, repository-boundary, owning-project tests, broken-link checks, and
   `git diff --check`.

No compatibility duplicate is created by default. If an executable contract genuinely
requires an alias, the alias must be registered, tested, and assigned a removal condition.

## 7. Enforcement for future files

The authoritative check is:

```bash
.venv/bin/python infrastructure/scripts/audit_file_governance.py
```

The auditor applies canonical rules first. A pre-existing noncanonical file passes only as
a baseline-backed fixed contract. A new noncanonical file fails even if it is placed under
a directory that contains historical exceptions. Closed legacy scopes reject every new
file, including canonically named files.

Root and project `AGENTS.md` files require this Codex before file creation. The repository
boundary validator invokes the auditor, and infrastructure tests enforce a complete,
unique, hash-bearing baseline.
