# Evidence-qualified alignment in prostate cancer

Working title:

> **From Clinical Signal Recovery to Evidence-Qualified Interpretation of Prostate Cancer Pathology Foundation Models**

This is the closed, hash-locked QFM revision workspace for an alignment-centered narrative. It is not
a copy of `projects/prostate_biomarker_validation/paper/`. The source project retains the
frozen analyses; this workspace owns the derivative interpretation and newly rendered
manuscript bundle.

The accountable author closed the scientific revision workstream on 2026-08-24. Further
experiments or scientific edits require explicit reopening; journal upload and public release
tagging are separate administrative actions.

The original prostate-biomarker submission bundle remains the frozen provenance owner.
Only evidence enumerated in `provenance/source_evidence_manifest.csv` may enter the build.
The builder fails if a source byte count or SHA-256 differs from the approved handoff.

- Design: [`../../docs/designs/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-design.md`](../../docs/designs/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-design.md)
- Implementation plan: [`../../docs/plans/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-plan.md`](../../docs/plans/2026-08-15-quantitative-foundation-model-validation-evidence-qualified-alignment-manuscript-plan.md)
- Submission handoff: [`submission-handoff.md`](submission-handoff.md)
- Preserved original submission source package: [`submission_orig/`](submission_orig/)
- pdfLaTeX-compatible upload archive: [`submission-package.zip`](submission-package.zip)
- Cover letter: [`cover_letter.pdf`](cover_letter.pdf) with editable source in
  [`cover_letter.tex`](cover_letter.tex)
- Original source manuscript bundle: [`../../../prostate_biomarker_validation/paper/README.md`](../../../prostate_biomarker_validation/paper/README.md)

## Core interpretation

Existing cohorts test whether clinically interpretable targets are recoverable and reproducible
from frozen representations. FM6 additionally tests whether BCR heads are sensitive to an
ISUP-correlated direction. Internal sensitivity repeated across encoders, but TCGA site-heldout
evidence was encoder-specific and the locked 508-patient LEOPARD reanalysis did not qualify
external transport. In CHIMERA (95 patients; 27 events), only Virchow combined ISUP recovery,
valid locked-head discrimination, positive targeted erasure, matched-control separation, and
multiplicity control. This supports encoder-specific external whole-tissue functional transport,
not encoder superiority, universal or indispensable use, clinical increment, strong H2, or
complete explanation.
SICAP specificity is accepted as secondary internal detector evidence; poor sensitivity on
the independent PANDA providers remains an explicit domain limitation. Residual or unknown
AI-feature marker discovery is reserved for a separate follow-up study. Nothing in this
manuscript shows that presenting these coordinates improves clinician trust, reliance,
diagnostic performance, or clinical utility.

## Build

```bash
.venv/bin/python projects/quantitative_foundation_model_validation/paper/evidence-qualified-alignment-prostate-cancer/build_alignment_manuscript.py
```

Use `--output-root /tmp/<fresh-directory>` for an isolated clean build. The builder stages
the manuscript sources there, verifies the original repository evidence, and renders the complete
bundle without changing the tracked workspace.

The command verifies all promoted evidence, checks headline numeric mappings, renders seven
claim-essential main figures plus the supplementary full-grid audit, generates source-driven
tables, and builds `main.pdf` plus `supplement.pdf` when XeLaTeX is available. The current
scientific draft is intentionally uncapped while the six-axis evidence and FM6 clean-rerun
record are finalized; submission compression is a separate author-stage task. Complete
setting, endpoint, and evidence-audit material remains in the unrestricted Supplementary
Information. Both documents use the same target, claim, endpoint, and numeric provenance
contracts.
