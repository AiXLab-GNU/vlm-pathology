# Project Structure Codex

Version: 2.3
Effective date: 2026-08-13
Owner: Jin Hyun Kim (PM)
Status: active repository policy

## 1. Structural authority

This is the mandatory placement contract for every new, moved, or generated file. Before
writing, identify exactly one scientific owner or classify the item as shared repository
infrastructure. Root and project `AGENTS.md` files remain the scientific authority; this
Codex is the structural authority.

Directory placement alone is not sufficient. Every managed document and source file must
also comply with `FILE_GOVERNANCE_CODEX.md`, which defines file class, lifecycle,
metadata, exceptions, and the baseline audit, and `FILE_NAMING_CODEX.md`, which defines
canonical basenames, fixed contracts, and rename procedure.

No workflow, including Superpowers, may create an unregistered root directory, a second
project tree, a generic `results`/`output`/`misc`/`backup` folder, or a convenience copy of
an existing artifact.

## 2. Complete root contract

```text
vlm-pathology/
├── projects/          scientific code, protocols, tests, reports, and papers by project
├── resources/         local data, model workspaces, archives, and generated artifacts
├── infrastructure/    shared packages, registries, repository policy, tests, migrations
├── .worktrees/        registered auxiliary Git worktrees
├── .git/              Git-owned metadata
├── .venv/             repository Python environment; fixed command contract
├── .agents/           agent runtime state; tool-owned
├── .claude/           Claude runtime state; tool-owned
├── .codex/            Codex runtime state; tool-owned
├── .superpowers/      Superpowers runtime state only; no final research documents
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── LICENSE
├── environment.yml
├── requirements-lock.txt
└── .gitignore
```

No other root entry is allowed. In particular, legacy root paths `models`, `paper`,
`studies`, `docs`, `scripts`, `packages`, `shared`, `data`, `artifacts`, `opendataset`,
`song-datasets`, `local-data`, and `reorganization` are prohibited.

The exhaustive ownership and lifecycle table is
`infrastructure/docs/repository/ROOT_DIRECTORY_REGISTRY.csv`.

## 3. Project contract

Each project is rooted at `projects/<project_id>/` and owns:

```text
AGENTS.md  PROJECT.yaml  CLAIM_BOUNDARIES.md  MILESTONES.md  README.md
00-project-sequence/     code/      docs/      tests/          paper/      manifests/  reports/
```

`00-project-sequence/README.md` is the mandatory first navigation surface. It orders the
scientific stages, reports current status, and links each stage to its canonical folder.
Canonical executable folders are not numbered retroactively because their paths are part of
commands, imports, tests, manifests, and frozen provenance.

Active project and research programme documents under `docs/project_plan/`,
`docs/research_plan/`, and registered subordinate document directories use the ancestry
numbering contract in `FILE_NAMING_CODEX.md`. The level-1 plan governs level-2
milestone/workstream documents and level-3 task/support documents. Root `MILESTONES.md`
remains a fixed summary index and is not a second canonical plan.

Each registered research project declares exactly one canonical document-control chain in
`PROJECT.yaml`:

```text
canonical_research_plan       hierarchy level 1; scientific authority
canonical_milestones          hierarchy level 2; evidence-gate refinement
canonical_execution_tracker   hierarchy level 3; current operational state
survey_index                  docs/surveys/README.md
results_index                 project report/result entry point
```

The plan, milestones, and tracker link one another reciprocally. Scope and success-criterion
changes flow from plan to milestones to tracker. Root `README.md`, `MILESTONES.md`,
`00-project-sequence/README.md`, and `docs/README.md` must link the declared chain. A project
may retain other subordinate programme documents, but none may compete for one of these
three canonical roles.

Every project has `docs/surveys/README.md`, even when no maintainable survey exists. In that
case the index records the gap as `PLANNED`; it never fabricates a literature review. A
`CURRENT` survey is a formal research-plan input and must be linked from the governing plan.

Project-specific milestone or governance directories may be added only when registered in
the boundary validator. The three current project IDs are:

- `precise_pni_candidate_triage`
- `quantitative_foundation_model_validation`
- `prostate_biomarker_validation`

Scientific questions, labels, endpoints, approvals, outputs, reports, and manuscript claims
must remain with their owner. One project must not silently consume another project's
generated output; a deliberately shared immutable input requires a hash-locked manifest.

## 4. Resource contract

`resources/` is local-state storage arranged by owner:

```text
resources/
├── data/
│   ├── manifests/                         tracked pointer/hash/access records
│   ├── shared/                            datasets used by multiple projects
│   └── <project_id>/                      project-owned local datasets
├── projects/<project_id>/                 weights, environments, caches, model workspaces
└── artifacts/<project_id>/                generated results, archives, workflow history
```

Raw data, WSI, patient-level results, weights, environments, third-party repositories,
caches, and large generated products are ignored. Only README files and explicit manifests
are tracked. Moving a resource must preserve its content hash and update its manifest.

## 5. Infrastructure contract

```text
infrastructure/
├── packages/       tested reusable code with identical cross-project contracts
├── shared/         shared schema, cohort, model, and provenance registries
├── scripts/        repository operation and audit entry points
├── tests/          repository-level integration tests
├── docs/
│   ├── repository/ structure policy, registries, and templates
│   └── superpowers/ repository-wide approved designs and plans only
└── migrations/     dated, closed repository migration audits
```

Study estimands, endpoint logic, claim gates, and manuscript content never move into
`infrastructure/` merely because two scripts look similar.

## 6. Mandatory placement decision

1. Does the item express one study's science, approval, result, or claim? Put it under the
   owning project.
2. Is it raw/local/generated state? Put it under `resources/` and name the project owner or
   `shared` explicitly.
3. Is it tested reusable code, a cross-project contract, or repository operation? Put it
   under `infrastructure/`.
4. Is it temporary agent state? Use the appropriate tool-owned dot directory or `/tmp`, but
   never treat that location as a final artifact.
5. If ownership remains ambiguous, do not create the file. Resolve ownership in the plan
   first, then create one canonical copy.

## 7. Superpowers control

Superpowers is a workflow, not an owner.

- Project design:
  `projects/<project_id>/docs/designs/YYYY-MM-DD-<project_id>-<topic>-design.md`
- Project plan:
  `projects/<project_id>/docs/plans/YYYY-MM-DD-<project_id>-<topic>-plan.md`
- Repository design:
  `infrastructure/docs/superpowers/specs/YYYY-MM-DD-repository-<topic>-design.md`
- Repository plan:
  `infrastructure/docs/superpowers/plans/YYYY-MM-DD-repository-<topic>-plan.md`
- Intermediate briefs, diffs, review packages, and SDD progress:
  `resources/artifacts/<project_id>/workflow_history/`

Every final design or plan begins with the metadata fields from
`infrastructure/docs/repository/templates/SUPERPOWERS_DOCUMENT_HEADER.md`. One design has one
canonical plan set. Amend with a dated change log or `supersedes`; do not create `final2` or
near-duplicates. `.superpowers/` may contain runtime state only and must be empty of final
research documents after a workflow completes.

## 8. Worktree control

Auxiliary worktrees use `.worktrees/<project_id>/<short-purpose-slug>/` and branch
`work/<project_id>/<short-purpose-slug>`. Reserve and update a row in
`.worktrees/registry.csv`. A worktree may change only its registered project and declared
shared files. Store no unique data, weights, environments, or generated evidence inside it.
Remove with `git worktree remove` and `git worktree prune`, never filesystem deletion.

## 9. Required enforcement

After creating or moving files:

1. `.venv/bin/python infrastructure/scripts/validate_project_boundaries.py`
2. `.venv/bin/python infrastructure/scripts/audit_file_governance.py`
3. `.venv/bin/python infrastructure/scripts/audit_worktrees.py`
4. `.venv/bin/python -m unittest discover -s infrastructure/tests -p 'test_*.py' -v`
5. owning-project tests and Python syntax checks
6. broken-link audit, post-migration inventory, and `git diff --check`

The file-governance auditor enforces the declared document-control chain, survey index,
reciprocal links, canonical entry links, and active-reference cleanup after renames.

Structural PASS does not authorize a scientific claim or expand a project's claim ceiling.
