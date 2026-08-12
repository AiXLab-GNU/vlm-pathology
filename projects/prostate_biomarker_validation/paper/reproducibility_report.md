# Reproducibility report

Verification date: 2026-08-07

## Ownership and immutable input

- This report is final-audit-owned. The canonical builder copies it to external packages but does not generate or overwrite it.
- The builder-managed package-state report is `paper/compliance_report.md`.
- PRECISE final clinician source: `resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv`.
- Expected and observed PRECISE SHA256: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.
- The source was not edited.

## Build outputs

The public entry point `.venv/bin/python paper/build_revision_package.py` completed with package status `partial`. The three final QA reports had identical SHA256 values before and after that fresh PDF build.

| Output | Pages | Bytes | Modification timestamp | SHA256 |
|---|---:|---:|---|---|
| `paper/main.pdf` | 15 | 252,269 | `2026-08-07 10:40:19.178780446 -0400` | `60de69e8e386a5e4be571e7d4dedce62ce6f861a271c4bec895286a41e61b2fd` |
| `paper/supplement_main.pdf` | 15 | 178,165 | `2026-08-07 10:40:21.438821686 -0400` | `f0ee753fd1ea6d5aa6aafd087137f31f75b485d2f87c72ce055cb87c6cbd1f6b` |

- Figure manifest: 9 rows, SHA256 `ce94740c2f148170b1fcda6b773b270b8f6f2162af898bbbad0209ca682971a3`.
- Table manifest: 4 rows, SHA256 `47bfa382a55bf48675f9b3980636d9060535dcaa8ed026b2bfe47e3e7003db6e`.
- Numeric claim mapping: 90 rows, SHA256 `085cf6db2400903d4cbe8de4292341526237cfa8c6680e8cf8b44f360a5c5194`.
- Numeric QA CSV: 90/90 passed and mismatches 0, SHA256 `140ac2147abc7a555cf010c07c43ef6b4d14b831308fd781f291befdac828e7f`.
- Numeric derivations: 14 rows, SHA256 `e35a1754464c878f5c43ceb43f82557f1fbd82d3af4306856c466e979b5f91a3`.
- Both LaTeX logs report 15-page outputs and contain no fatal errors, undefined control sequences, undefined references or unresolved citations.

## Determinism and tests

- Two independent external `--skip-pdf` builds contained 110 files each.
- Excluding the three final-audit-owned reports prevents a digest from referring to itself. The remaining 107 files were byte-identical with aggregate SHA256 `d9bd047307bfdffd84aa66194279475a18fcb65db2f194b49a655ca8ab09d28f`.
- The three excluded reports are verified separately by exact SHA256 equality between the repository and both external roots.
- Volatile timestamps are explicit only for the final PDFs above; generated manifests and deterministic reports contain no volatile build timestamp fields.
- Task-specific package module: 38/38 tests passed in 71.946 s.
- Focused ten-module suite: 310/310 passed in 477.434 s; failures 0, errors 0, skips 0.
- Full discovery: 334/334 passed in 500.726 s; failures 0, errors 0, skips 0.
- Final PDFs: all 30 pages were rasterized at 180 dpi and visually inspected; defects 0.
- Active submission scan: 15 files, findings 0.

The scientific, visual and reproducibility checks pass. The package nevertheless remains `partial` because all eight author-controlled items in `paper/author_action_items.md` are still blocking.
