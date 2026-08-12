# MajorRevision-v1 compliance report

Verification date: 2026-08-07

## Outcome

- Package status: `partial`.
- Scientific re-review: Approved (Critical 0, Important 0, Minor 0).
- Visual re-review: Approved after inspection of all 30 final PDF pages at 180 dpi.
- Open author-controlled blockers: 8.

## Author-controlled blockers

1. Confirm the final author list and author-approved CRediT contributions.
2. Confirm competing-interest declarations for every author.
3. Confirm funding, grant identifiers, funder roles and acknowledgements.
4. Supply the responsible institution's ethics determination, identifier and consent or waiver wording.
5. Authorize derived-data deposition and provide an accession, or approve a justified request-based statement.
6. Decide the code-release licence and archive and provide a permanent URL or DOI and any restrictions.
7. Approve the large-language-model disclosure after confirming product/model details, dates, scope and author verification.
8. Confirm author names, affiliations and corresponding-author address and email.

These are the same eight blocking items in `paper/author_action_items.md`; none was inferred or silently filled.

## Final artifact record

| Artifact | Pages | Bytes | Modification timestamp | SHA256 |
|---|---:|---:|---|---|
| `paper/main.pdf` | 15 | 252,269 | `2026-08-07 10:40:19.178780446 -0400` | `60de69e8e386a5e4be571e7d4dedce62ce6f861a271c4bec895286a41e61b2fd` |
| `paper/supplement_main.pdf` | 15 | 178,165 | `2026-08-07 10:40:21.438821686 -0400` | `f0ee753fd1ea6d5aa6aafd087137f31f75b485d2f87c72ce055cb87c6cbd1f6b` |

- Immutable PRECISE clinician source SHA256: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3` (matched expected).
- Figure manifest: 9/9, SHA256 `ce94740c2f148170b1fcda6b773b270b8f6f2162af898bbbad0209ca682971a3`.
- Table manifest: 4/4, SHA256 `47bfa382a55bf48675f9b3980636d9060535dcaa8ed026b2bfe47e3e7003db6e`.
- Numeric mapping: 90/90 passed with 90 unique claim IDs and anchors; mismatches 0.
- Raw Results partition: 110 occurrences = 90 scientific + 9 structural + 11 technical.
- Saved numeric derivations: 14 rows.
- Active submission scan: 15 files; findings 0.
- Task-specific package module: 38/38 tests passed in 71.946 s.
- Focused ten-module suite: 310/310 tests passed in 477.434 s; failures 0, errors 0, skips 0.
- Full discovery: 334/334 tests passed in 500.726 s; failures 0, errors 0, skips 0.
- Both LaTeX logs are free of fatal errors, undefined control sequences, undefined references and unresolved citations.
- Deterministic 107-file core digest, excluding the three final-audit-owned reports to avoid self-reference: `d9bd047307bfdffd84aa66194279475a18fcb65db2f194b49a655ca8ab09d28f`.

The three QA reports are final-audit-owned and are copied, but never generated or overwritten, by the canonical builder. The builder-managed `paper/compliance_report.md` remains separate. Scientific, visual and mechanical checks passed, but the package must remain `partial` until all eight author-controlled blockers are resolved.
