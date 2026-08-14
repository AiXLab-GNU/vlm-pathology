# Document hierarchy naming migration report

Date: 2026-08-13
Owner: repository
Status: completed structural migration

## Scope reviewed

The pre-migration governance catalog contained 627 managed files: 209 active, 238 frozen,
95 legacy, and 85 generated. Every managed filename was reviewed through its registered
file class, lifecycle, naming status, and exception status.

Seven active programme-document path transitions were recorded. The remaining paths were intentionally left
unchanged because they were already canonical or were protected by a fixed, frozen,
generated, legacy, clinician-facing, manuscript, or closed-migration contract. In
particular, the two P0 pre-experiment handoff documents and the misspelled legacy survey
retain their historical paths; this review does not rewrite frozen provenance for cosmetic
consistency.

## Hierarchy applied

```text
precise_pni_candidate_triage
└── 01  governing PNI project plan
    ├── 01-01  PNI research overview
    └── 01-02  canonical milestones
        └── 01-02-01  current execution tracker

quantitative_foundation_model_validation
└── 01  governing quantitative-AI research programme plan
    ├── 01-01  foundation-model validation milestones
    │   └── 01-01-01  current execution tracker
    └── 01-02  medical quantitative-metric taxonomy
        └── 01-02-01  quantitative-metrics package guide

prostate_biomarker_validation
└── 01  governing biomarker-qualification research plan
    └── 01-01  canonical milestones
        └── 01-01-01  current execution tracker
```

The root `MILESTONES.md` files remain fixed summary indexes. They link the single canonical
milestone authority and do not compete with it. Each `PROJECT.yaml`, root README, project
sequence, and docs index points to the same control chain.
Dated designs and implementation plans retain their chronological naming contract.

## Survey authority

- `precise_pni_candidate_triage`: no maintainable survey exists; the survey is `PLANNED`.
- `quantitative_foundation_model_validation`: `QUANTITATIV_AI_SURVEY.md` remains
  `HISTORICAL`; a source-audited successor is `PLANNED`.
- `prostate_biomarker_validation`: no maintainable survey exists; the survey is `PLANNED`.

No survey is labeled `CURRENT`, `SUPPORTING`, or `SUPERSEDED` in this migration. No
literature-search date, novelty conclusion, or completion claim was invented.

## Reference disposition

Active navigation documents and executable consumers were updated atomically. Frozen P0
protocol snapshots, generated historical run configurations, and closed migration
inventories retain old path strings as provenance. `file-rename-map.csv` is the canonical
old-to-new resolution record and stores pre/post SHA-256 values.

## Enforcement

The file-governance auditor now accepts one to three two-digit ancestry segments, requires
unique hierarchy identifiers per project, requires every child prefix to resolve to a
parent, and requires each level-1 hierarchy root to be a plan. It also validates the single
plan→milestones→tracker chain, reciprocal links, project metadata, canonical entry links,
survey registration/status rules, affected Markdown links, and stale active paths. The File
Naming Codex defines the same contract and explicitly places plans above milestone/workstream
descendants.

The full pre-change role/action assessment is in `document-inventory.csv`; the complete
old-to-new path and hash record is in `file-rename-map.csv`.

## Pre-existing broken link

```text
PRE_EXISTING_BROKEN_LINK
source: projects/prostate_biomarker_validation/docs/CODE_AVAILABILITY.md
target: LICENSE
이번 명명 작업과의 관련성: 없음; 이 파일은 이번 변경에서 수정하지 않음
권장 후속 조치: publication contract 검토 시 저장소 루트 LICENSE를 가리키는 상대경로로 별도 수정
```

## External and local-path risks

The supporting PNI research overview retains six absolute workstation links to local data or
generated artifacts. The historical QFM survey also retains absolute pre-separation paths.
They were not rewritten because the targets are local/ignored or the document is historical;
converting them requires a separate provenance-aware link audit rather than a cosmetic rename.
