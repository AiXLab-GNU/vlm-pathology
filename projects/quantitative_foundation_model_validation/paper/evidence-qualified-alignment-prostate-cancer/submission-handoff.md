---
document_id: qfm-evidence-qualified-alignment-submission-handoff
owner_project: quantitative_foundation_model_validation
document_type: report
status: submission-metadata-required
created: 2026-08-18
canonical_path: projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer/submission-handoff.md
---

# Scientific Reports submission handoff

**Readiness:** `partial—online submission metadata and accountable-author ethics confirmation
required`. The author list, affiliations, corresponding-author details and ORCID, contribution
statement, Funding statement, competing-interests declaration, scientific text, source-linked
figures and tables, cover letter, build, and computational QA are ready for author review. The
public submission repository, immutable commit, and annotated submission tag are established.
Submission remains blocked only by author-controlled declarations and online submission materials,
not by a pending scientific experiment or code release.

## Submission artifacts and counts

| Item | Final audit |
|---|---|
| Title | 15 words; within the journal's 20-word recommendation |
| Abstract | 197 words by `detex`; unstructured; no citations; within the 200-word limit |
| Main | 22 pages; 6,566 Introduction--Conclusion words; 1,708 Methods words; 7 figures + 1 table |
| Supplementary Information | 12 pages; 3,137 words including generated tables; 1 figure + 14 tables; one separate PDF |
| References | 19 numbered references; all citation keys resolved |
| `main.pdf` | SHA-256 `b77e45487cc93eb718e5fd5626b34e80e5acf5e3ee58083fbd5014b2cafaf057` |
| `supplement.pdf` | SHA-256 `e423f2661938b32fb916517d2285430f6b09e524c5deb7af120b782ac8bc228d` |
| `cover_letter.pdf` | 1 page; SHA-256 `aaae226db0e6fda162011e7f3985a19882a98e0cec45dcc03f9c82ecda230089` |
| Source manifest | 19/19 verified; manifest SHA-256 `c1129408a803a4bc0841e4b6adc097070d7f8995f3f6d7ee793e58ce4f9ef5d0` |
| Numeric QA mapping | 33/33 verified; SHA-256 `c707818dd79ccec4ee04f8481ce980d1ac671bdfe10a3f6161884d654e77134c` |
| Public release repository | `https://github.com/AiXLab-GNU/evidence-qualified-alignment-prostate-cancer` |
| Submission release | tag `v1.0.2-submission`; commit `664a542166219e7ececec00b6219e787863a70ed` |
| Public manuscript boundary | `main.pdf` and `supplement.pdf` only; editable TeX source excluded |
| Reviewer reproduction | 12/12 aggregate sources, 33/33 numeric mappings, 8/8 byte-identical figures, 10/10 analysis-code snapshots, 6/6 release tests |

Scientific Reports states that page count and the 4,500-word main-text target are generally
recommendations rather than strict limits. The longer main text retains the required six-axis
comparison, functional-sensitivity boundary, and limitations. The eight main display items meet
the stated maximum. Official sources checked on 2026-08-18: [submission guidelines](https://www.nature.com/srep/author-instructions/submission-guidelines),
[initial-submission checklist](https://www.nature.com/documents/srep-checklist-for-initial-submissions.pdf),
and [editorial policies](https://www.nature.com/srep/journal-policies/editorial-policies).

## Scientific and verification lock

The primary claim is that explicitly qualified morphologic, molecular, and outcome axes provide
contestable shared coordinates for auditing human--AI agreement, disagreement, explanation
withholding, and validation priorities. Grade/ISUP and phenotype have the strongest representation
evidence; PTEN and AR are conditional; SPOP is evaluated but unsupported; recurrence is
endpoint-sensitive. Only two internal locked BCR heads were shown sensitive to an
ISUP-correlated direction. Indispensable/mechanistic use, external functional transport,
clinical increment, improved clinician outcomes, complete explanation, residual-marker discovery,
and encoder superiority remain prohibited claims.

Two fresh `/tmp` builds produced byte-identical generated tables, eight figure PDFs, `main.pdf`,
and `supplement.pdf`. All 34 PDF pages were raster-inspected; the corrected bundle has no clipping,
table overflow, empty page, unresolved citation/reference, or overfull box. QFM tests passed
94/94. PBV tests passed 322/323; the sole failure is the pre-existing Funding-text expectation.
File governance and worktree audits and `git diff --check` passed. The boundary validator's sole
failure is the pre-existing unregistered root file `webportal-refactoring.md`.

The public `v1.0.2-submission` tag was independently cloned and passed all six reviewer release
tests. That package verifies 12 aggregate inputs and 33 mapped values, regenerates eight figure
PDFs with exact committed hashes, verifies both reference-PDF hashes, and preserves hash-locked
snapshots of 10 source-analysis entry points for code audit. End-to-end source experiments still
require the original datasets, patient/fold manifests, embeddings, and weights identified by the
project provenance; this boundary is explicit in the public `REPRODUCIBILITY.md`.

## Revision experiment and release workflow

The public submission repository is a release destination, not an experimental workspace.
All reviewer-requested experiments, re-analysis, model execution, patient-level outputs, and
editable manuscript changes must remain in the owning project in `vlm-pathology`, under an
approved revision protocol or plan. The existing source manifests, claim boundaries, project
tests, and immutable data controls continue to govern those experiments.

After a revision analysis is locked and verified, export only approved aggregate source tables,
public figure-rendering code, figures, and the revised `main.pdf` and `supplement.pdf` to a public
repository branch such as `revision/r1`. Run the public release tests there before merging. Tag
the accepted revision with a new immutable identifier such as `v1.1.0-revision1`; do not move or
overwrite an earlier submission tag. The response-to-reviewers document and editable manuscript source
remain in the controlled research workspace and journal submission system.

## Accountable-author actions before upload

The final author order, affiliations, corresponding-author details, Jin Hyun Kim ORCID
`0000-0002-2308-1638`, author-contribution roles, Funding statement, no-competing-interests
declaration, and public/deidentified secondary-analysis ethics statement were supplied on
2026-08-18 and are now present in the manuscript; the same author list and corresponding-author
ORCID appear on Supplementary page 1. A one-page Scientific Reports cover letter is included.

1. Confirm under the accountable author's institutional policy that this deidentified secondary
   analysis is non-human-participant research or is exempt from additional review. If an
   institutional determination, committee name, or reference number exists, add it before upload;
   no identifier should be inferred or invented.
2. Approve the six recommended keywords and the cover letter; supply reviewer
   suggestions/exclusions, the prior-editorial-discussion answer, submission date, and all
   online-system metadata.
3. Verify exact title/abstract parity across the manuscript, Supplementary Information, and
   submission system; upload the
   manuscript, seven individual main figure PDFs, and the single Supplementary PDF.

An archive DOI is not required to identify the submitted code snapshot because the annotated tag
and full commit hash are fixed above. A Zenodo DOI may be added later if the authors connect the
public GitHub repository to an archival deposition service.

Recommended keywords: Computational pathology; Pathology foundation models; Explainable
artificial intelligence; Prostate cancer; Human--AI alignment; Model validation.
