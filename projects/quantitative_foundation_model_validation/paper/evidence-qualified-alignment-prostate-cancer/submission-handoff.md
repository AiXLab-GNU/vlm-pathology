---
document_id: qfm-evidence-qualified-alignment-submission-handoff
owner_project: quantitative_foundation_model_validation
document_type: report
status: submitted
created: 2026-08-18
canonical_path: projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer/submission-handoff.md
---

# Scientific Reports submission handoff

**Status:** `submitted—revision scientific workstream closed and hash-locked; revision upload not yet performed`.
The corresponding author confirmed completion of the Scientific Reports initial submission on
2026-08-20. The submitted package includes the verified author list, affiliations,
corresponding-author details and ORCID, contribution and Funding statements,
competing-interests declaration, scientific text, source-linked figures and tables, cover letter,
and pdfLaTeX-compatible source ZIP. No journal manuscript identifier has been supplied for this
record, and none is inferred. The initial package remains immutable in `submission_orig/`;
locked siteheldout, LEOPARD, and CHIMERA functional-transport analyses are present only in the
revision working copy.

## Submission artifacts and counts

| Item | Final audit |
|---|---|
| Title | 13 words; within the journal's 20-word recommendation |
| Abstract | 198 words by `detex`; unstructured; no citations; within the 200-word limit |
| Main | 16 pages; 4,383 Introduction--Conclusion words; 1,231 Methods words; 5 figures + 1 table |
| Supplementary Information | 13 pages; 3,253 words including generated tables; 3 figures + 14 tables; one separate PDF |
| References | 19 numbered references; all citation keys resolved |
| `main.pdf` | SHA-256 `5aa98c3c1491d8991b793e07dcee519847738837fabd469087f2bd0c3da3c89f` |
| `supplement.pdf` | SHA-256 `8f3ee96ae07e08cc0e38a72f37562d291cd10de47474a679d6b51d7dcf12615c` |
| `cover_letter.pdf` | 1 page; SHA-256 `469db26460b0a42f81515f748ff4875abf0be64c4a81a0eda6a444558ed48b93` |
| Submission source ZIP | `submission-package.zip`; pdfLaTeX fresh-extraction build passed; SHA-256 `50e1022cc8c44fac0b5ada3290c366887f690703f7f9d745ac5db52f2b7ce50e` |
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

## Locked revision working copy — 2026-08-20

The revision experiment used seven TCGA held-out sites (289 patients; 69 events) and an
independent-patient LEOPARD reanalysis (508 patients; 87 events; 32,512 identical paired crops).
TCGA site-heldout evidence was encoder-specific: CONCH failed and Virchow passed. In LEOPARD,
CONCH had a positive erasure delta but its full-head interval crossed chance; Virchow failed head
validity and erasure sensitivity. The locked external family status is
`FAIL_OR_INCONCLUSIVE_EXTERNAL_FUNCTIONAL_TRANSPORT`, with no retuning.

| Revision item | Audit |
|---|---|
| Abstract | 194 words |
| Main | 17 pages; 4,498 Introduction--Conclusion words |
| Supplementary Information | 14 pages; includes locked site/external gate table |
| `main.pdf` | SHA-256 `2e72b1aed184fbaff365e8b7574f6dffddb1eab2776600a6447e2c0901a3165e` |
| `supplement.pdf` | SHA-256 `dbfe13aa2e8150dab38f46c604c3d3d54a0d119aacfac31d31e255867403394c` |
| Source manifest | 21/21 verified; SHA-256 `1b0199e5a4213ff5488e8b8c1e35162093b0fe0f1227a936d48ed7ed1bde5fcb` |
| Numeric QA mapping | 41/41 verified; SHA-256 `34518504bf5505e43b61c4af56b9075617763aadbe6d24e28dbcae138be7f7d6` |
| Semantic contracts | 61/61 passed |

LEOPARD is independent of TCGA by patient and institution, but lacks ISUP and treatment
covariates and had prior outcome access in an earlier reverse-transfer analysis. It is a newly
locked reanalysis, not a prospectively untouched confirmation. The accountable author confirmed
embargo completion; the exact external clearance document/URL remains unarchived and should be
stored before revision release.

## Locked CHIMERA revision — 2026-08-24

The preregistered CHIMERA analysis used 95 patients, 27 BCR events, 190 WSIs, and 12,160
outcome-blind whole-tissue crops. Both encoders recovered the TCGA-locked ISUP direction and
showed positive targeted-erasure effects. CONCH remained fail/inconclusive because its full-head
interval reached chance. Virchow passed head validity, positive erasure, matched-random and Holm
gates, qualifying encoder-specific external whole-tissue functional transport. This is not a
formal encoder-superiority, tumor-specific, indispensable-use, clinical-increment, strong-H2, or
new-biomarker claim.

| CHIMERA revision item | Audit |
|---|---|
| Abstract | 198 words |
| Main | 18 pages; 4,833 Introduction--Conclusion words; 1,559 Methods words |
| Supplementary Information | 15 pages; CHIMERA detailed gates and six-row external table included |
| `main.pdf` | SHA-256 `4e5897d85dda3f07863e803fef210ea4cde9587af58b15b0263487b6c7014f81` |
| `supplement.pdf` | SHA-256 `f2a697259f8f8b7544cc86b1a70bd2775be54b03397f426a45d48f06b33d8f74` |
| Source manifest | 24/24 verified; SHA-256 `7398334cbab06a48c20a272e9c3a874011b0825609b22b19c29c6be7c3172166` |
| Numeric QA mapping | 51/51 verified; SHA-256 `87e94d9216bfe32fe9fb6ef79659f7a6b73f57f44e5d70211f049371254bf80a` |
| Semantic contracts | 77/77 passed |
| Clean rerun | CHIMERA nonvolatile output hashes 6/6 exact |

On 2026-08-24 the accountable author determined, from publicly released studies using CHIMERA
data, that the publication embargo had ended and authorized aggregate-result promotion. This is
recorded as an author release determination, not as written organizer clearance. The official
challenge pages still express release as conditional on publication of the challenge and
baseline journal papers and do not provide a separate clearance certificate in the archived
project record.

The accountable author closed the revision scientific workstream on 2026-08-24. The Main and
Supplementary PDFs, source manifest, numeric mapping, semantic contracts, and CHIMERA clean-rerun
record in the table above are the closure baseline. No additional experiment, retuning, scientific
claim change, or manuscript edit is planned. Journal upload and creation of a public immutable
revision tag remain separate administrative release actions and do not keep the scientific
workstream open.

## Scientific and verification lock

The primary claim is that explicitly qualified morphologic, molecular, and outcome axes provide
contestable shared coordinates for auditing human--AI agreement, disagreement, explanation
withholding, and validation priorities. Grade/ISUP and phenotype have the strongest representation
evidence; PTEN and AR are conditional; SPOP is evaluated but unsupported; recurrence is
endpoint-sensitive. Two internal locked BCR heads were sensitive to an ISUP-correlated direction;
site transport was encoder-specific; LEOPARD external transport was not qualified; and Virchow
alone passed the CHIMERA whole-tissue gate. Qualified external functional transport is therefore
limited to the Virchow--CHIMERA frame. Indispensable/mechanistic use, universal transport,
clinical increment, improved clinician outcomes, complete explanation, residual-marker discovery,
and encoder superiority remain prohibited claims.

The 198-word abstract now states the study motivation explicitly: determine which
human-interpretable quantitative axes are encoded, whether they persist across cohort and
technical variation, and---for ISUP alone in this study---whether a locked downstream decision
is sensitive to the corresponding direction. Clinician-understandable reliability auditing is
the present contribution. Residual-signal or biomarker discovery remains a bounded future use
of the map, not a result reported here.

The initial-submission builder verified 19/19 registered sources, 33/33 numeric mappings, and
53/53 semantic contracts. The revision builder verifies 21/21 sources, 41/41 numeric mappings,
and 61/61 semantic contracts. The initial 29 PDF pages were raster-inspected; the interpretation-enhanced bundle has no clipping,
table overflow, empty page, unresolved citation/reference, or overfull box. QFM tests passed
97/97. File governance and worktree audits and `git diff --check` passed. The boundary validator's
sole failure is the pre-existing unregistered root file `webportal-refactoring.md`.

The public `v1.0.6-submission` tag was independently cloned and passed all six reviewer release
tests. That package verifies 12 aggregate inputs and 33 mapped values, regenerates eight figure
PDFs with exact committed hashes, verifies both reference-PDF hashes, and preserves hash-locked
snapshots of 10 source-analysis entry points for code audit. End-to-end source experiments still
require the original datasets, patient/fold manifests, embeddings, and weights identified by the
project provenance; this boundary is explicit in the public `REPRODUCIBILITY.md`.

The public tag predates the motivation-focused title, Funding and pdfLaTeX revisions used for the
initial submission. As a post-submission provenance action, export the submitted reference PDFs,
update their public artifact hashes, rerun the reviewer tests from a fresh clone, and create a new
immutable submission tag. Earlier submission tags remain immutable.

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

## Post-submission actions

The final author order, affiliations, corresponding-author details, Jin Hyun Kim ORCID
`0000-0002-2308-1638`, author-contribution roles, Funding statement, no-competing-interests
declaration, and public/deidentified secondary-analysis ethics statement were supplied on
2026-08-18 and are now present in the manuscript; the same author list and corresponding-author
ORCID appear on Supplementary page 1. A one-page Scientific Reports cover letter is included.
On 2026-08-18, the corresponding author completed the institutional-policy confirmation that this
deidentified secondary analysis requires no additional ethical approval or participant consent.
No committee name or determination identifier has been inferred or invented.

1. Record the journal manuscript identifier and editorial-screening status when they become
   available.
2. Refresh the public submission release with the submitted title, Funding statement,
   pdfLaTeX-compatible PDFs and source-package provenance; record the new immutable tag and commit
   in this handoff without moving an earlier tag.
3. Archive the exact LEOPARD official clearance URL or screenshot before any public revision
   release or journal upload.
4. On author approval, package the locked siteheldout/LEOPARD/CHIMERA revision results without
   retuning and create a new immutable revision tag; do not overwrite the initial tag.

An archive DOI is not required to identify the submitted code snapshot because the annotated tag
and full commit hash are fixed above. A Zenodo DOI may be added later if the authors connect the
public GitHub repository to an archival deposition service.

Recommended keywords: Computational pathology; Pathology foundation models; Explainable
artificial intelligence; Prostate cancer; Human--AI alignment; Model validation.
