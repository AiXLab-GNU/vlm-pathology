# Numeric consistency report

Verification date: 2026-08-07

## Result

All active quantitative Results claims are accounted for by explicit, context-bound source mappings. Numeric mismatches: 0.

| Contract | Result |
|---|---:|
| Raw quantitative occurrences in Results | 110 |
| Scientific occurrences | 90 |
| Exact structural occurrences | 9 |
| Exact technical-identifier occurrences | 11 |
| Unique scientific claim IDs | 90 |
| Unique scientific context anchors | 90 |
| Passed scientific mappings | 90/90 |
| Failed scientific mappings | 0 |
| Saved derivation rows | 14 |

The partition is exact: `110 = 90 + 9 + 11`. Structural and technical exclusions are disjoint exact locators; no pattern-wide or generic TeX-command mask is used. Missing, moved, duplicated or newly introduced quantitative prose therefore fails closed.

## Source and artifact record

- Immutable PRECISE clinician source SHA256: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.
- `paper/numeric_qa_mapping.csv`: 90 rows, SHA256 `085cf6db2400903d4cbe8de4292341526237cfa8c6680e8cf8b44f360a5c5194`.
- `paper/numeric_consistency_report.csv`: 90 rows, all passed, SHA256 `140ac2147abc7a555cf010c07c43ef6b4d14b831308fd781f291befdac828e7f`.
- `paper/results_numeric_derivations.csv`: 14 rows, SHA256 `e35a1754464c878f5c43ceb43f82557f1fbd82d3af4306856c466e979b5f91a3`.
- `paper/figure_manifest.csv`: 9 rows, SHA256 `ce94740c2f148170b1fcda6b773b270b8f6f2162af898bbbad0209ca682971a3`.
- `paper/table_manifest.csv`: 4 rows, SHA256 `47bfa382a55bf48675f9b3980636d9060535dcaa8ed026b2bfe47e3e7003db6e`.

## Final QA record

| Artifact | Pages | Bytes | Modification timestamp | SHA256 |
|---|---:|---:|---|---|
| `paper/main.pdf` | 15 | 252,269 | `2026-08-07 10:40:19.178780446 -0400` | `60de69e8e386a5e4be571e7d4dedce62ce6f861a271c4bec895286a41e61b2fd` |
| `paper/supplement_main.pdf` | 15 | 178,165 | `2026-08-07 10:40:21.438821686 -0400` | `f0ee753fd1ea6d5aa6aafd087137f31f75b485d2f87c72ce055cb87c6cbd1f6b` |

- Task-specific package module: 38/38 tests passed in 71.946 s.
- Focused ten-module suite: 310/310 passed in 477.434 s; failures 0, errors 0, skips 0.
- Full discovery: 334/334 passed in 500.726 s; failures 0, errors 0, skips 0.
- Active submission scan: 15 files, findings 0.
- Deterministic 107-file non-report core digest: `d9bd047307bfdffd84aa66194279475a18fcb65db2f194b49a655ca8ab09d28f`.
- Package status: `partial`; open author-controlled blockers: 8.

The reconstructed with-tumor endpoint and Official TCGA-CDR PFI retain distinct names and source fields. No endpoint substitution is presented as official PFI. No numeric mismatch, unmapped scientific occurrence or duplicate scientific anchor remained in the final check. This report is final-audit-owned and the canonical builder must preserve it byte for byte.
