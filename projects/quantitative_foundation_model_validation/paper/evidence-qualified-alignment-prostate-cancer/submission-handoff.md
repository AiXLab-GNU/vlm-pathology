---
document_id: qfm-evidence-qualified-alignment-submission-handoff
owner_project: quantitative_foundation_model_validation
document_type: report
status: submission-metadata-required
created: 2026-08-18
canonical_path: projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer/submission-handoff.md
---

# Scientific Reports submission handoff

**Readiness:** `partial—online submission metadata required`.
The author list, affiliations, corresponding-author details and ORCID, contribution
statement, Funding statement, competing-interests declaration, scientific text, source-linked
figures and tables, cover letter, build, and computational QA are ready for author review. The
public submission repository, immutable commit, and annotated submission tag are established.
The interpretation-enhanced manuscript has passed local scientific and layout QA and is fixed in
the public immutable submission release. No new scientific experiment or code release is pending.

## Submission artifacts and counts

| Item | Final audit |
|---|---|
| Title | 15 words; within the journal's 20-word recommendation |
| Abstract | 198 words by `detex`; unstructured; no citations; within the 200-word limit |
| Main | 16 pages; 4,383 Introduction--Conclusion words; 1,231 Methods words; 5 figures + 1 table |
| Supplementary Information | 13 pages; 3,253 words including generated tables; 3 figures + 14 tables; one separate PDF |
| References | 19 numbered references; all citation keys resolved |
| `main.pdf` | SHA-256 `cb2a2feb03b0c4d9068e509529f1a96ad0d7d1034730c307f7c9bb2495decc78` |
| `supplement.pdf` | SHA-256 `0e90c4c157aba2e57911db0c718007eeba2adaa85da6ab5d46ea73eb62e6c700` |
| `cover_letter.pdf` | 1 page; SHA-256 `7b5359238b9a988167c44584e50ecbbd76fd6c40f78122c6e6a41c68b4f49f23` |
| Source manifest | 19/19 verified; manifest SHA-256 `c1129408a803a4bc0841e4b6adc097070d7f8995f3f6d7ee793e58ce4f9ef5d0` |
| Numeric QA mapping | 33/33 verified; SHA-256 `c707818dd79ccec4ee04f8481ce980d1ac671bdfe10a3f6161884d654e77134c` |
| Public release repository | `https://github.com/AiXLab-GNU/evidence-qualified-alignment-prostate-cancer` |
| Submission release | tag `v1.0.6-submission`; commit `b3009b0001360975104e1d77cb3cb6a20a220a55` |
| Public manuscript boundary | `main.pdf` and `supplement.pdf` only; editable TeX source excluded |
| Reviewer reproduction | 12/12 aggregate sources, 33/33 numeric mappings, 8/8 byte-identical figures, 10/10 analysis-code snapshots, 6/6 release tests |

Scientific Reports states that page count and the 4,500-word main-text target are generally
recommendations rather than strict limits. The condensed Introduction--Conclusion text is below
that recommendation even when figure captions are included. The required six-axis comparison,
functional-sensitivity boundary, and limitations remain in the main text, and its six display
items are below the stated maximum. Official sources checked on 2026-08-18: [submission guidelines](https://www.nature.com/srep/author-instructions/submission-guidelines),
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

The 198-word abstract now states the study motivation explicitly: determine which
human-interpretable quantitative axes are encoded, whether they persist across cohort and
technical variation, and---for ISUP alone in this study---whether a locked downstream decision
is sensitive to the corresponding direction. Clinician-understandable reliability auditing is
the present contribution. Residual-signal or biomarker discovery remains a bounded future use
of the map, not a result reported here.

The manuscript builder verified 19/19 registered sources, 33/33 numeric mappings, and 53/53
semantic contracts. All 29 PDF pages were raster-inspected; the interpretation-enhanced bundle has no clipping,
table overflow, empty page, unresolved citation/reference, or overfull box. QFM tests passed
95/95. File governance and worktree audits and `git diff --check` passed. The boundary validator's
sole failure is the pre-existing unregistered root file `webportal-refactoring.md`.

The public `v1.0.6-submission` tag was independently cloned and passed all six reviewer release
tests. That package verifies 12 aggregate inputs and 33 mapped values, regenerates eight figure
PDFs with exact committed hashes, verifies both reference-PDF hashes, and preserves hash-locked
snapshots of 10 source-analysis entry points for code audit. End-to-end source experiments still
require the original datasets, patient/fold manifests, embeddings, and weights identified by the
project provenance; this boundary is explicit in the public `REPRODUCIBILITY.md`.

The public reference `main.pdf` has SHA-256
`cb2a2feb03b0c4d9068e509529f1a96ad0d7d1034730c307f7c9bb2495decc78`, matching the current
interpretation-enhanced working PDF. Earlier submission tags remain immutable.

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

The readable pre-condensation manuscript is fixed in the internal annotated tag
`qfm-manuscript-pre-condensation-v1.0.4` at commit `ace22870`. This immutable tag provides the
recovery point; a duplicate manuscript directory is therefore unnecessary.

## Accountable-author actions before upload

The final author order, affiliations, corresponding-author details, Jin Hyun Kim ORCID
`0000-0002-2308-1638`, author-contribution roles, Funding statement, no-competing-interests
declaration, and public/deidentified secondary-analysis ethics statement were supplied on
2026-08-18 and are now present in the manuscript; the same author list and corresponding-author
ORCID appear on Supplementary page 1. A one-page Scientific Reports cover letter is included.
On 2026-08-18, the corresponding author completed the institutional-policy confirmation that this
deidentified secondary analysis requires no additional ethical approval or participant consent.
No committee name or determination identifier has been inferred or invented.

1. Approve the six recommended keywords and the cover letter; supply reviewer
   suggestions/exclusions, the prior-editorial-discussion answer, submission date, and all
   online-system metadata.
2. Verify exact title/abstract parity across the manuscript, Supplementary Information, and
   submission system; upload the
   manuscript, five individual main figure PDFs, and the single Supplementary PDF.

An archive DOI is not required to identify the submitted code snapshot because the annotated tag
and full commit hash are fixed above. A Zenodo DOI may be added later if the authors connect the
public GitHub repository to an archival deposition service.

Recommended keywords: Computational pathology; Pathology foundation models; Explainable
artificial intelligence; Prostate cancer; Human--AI alignment; Model validation.
