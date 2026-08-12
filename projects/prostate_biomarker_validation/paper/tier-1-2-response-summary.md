# Tier 1–2 revision: summary of changes vs. `stanford-review.md`'s Questions for Authors

**Date**: 2026-08-03. This maps each of the review's 10 "Questions for Authors" to what
changed in `paper/main.tex`, so a formal response-to-reviewers letter can be drafted from it.
All Tier 1 items (1.1–1.8) and both Tier 2 items (2.1–2.2) are complete; `main.tex` compiles
cleanly (xelatex, 2 passes, 0 errors, 20 pages).

---

**Q1. "Release the exact code and mapping table for the reconstructed TCGA-PRAD recurrence
label, and benchmark it against standard TCGA endpoints (PFI, DFS/RFS)."**

Done (§res-label-benchmark, new subsection). Benchmarked our GDC-`follow_ups`-derived label
against `prad_tcga_pan_can_atlas_2018`'s standardized PFS/DFS: 87.0%/93.2% raw event agreement
(Cohen's κ=0.57/0.52), strong follow-up-time correlation (ρ=+0.85/+0.95). Re-scored marker 7's
zero-shot transfer directly against PFS/DFS: C-index 0.586 (PFS) / 0.605 (DFS), attenuated from
0.673 but still above chance — reported as a partial validation + partial caveat (original
number is somewhat label-definition-specific). Code (`build_bcr_labels.py`) was already
available; a fully public per-patient provenance mapping table (raw follow-up → event/censoring
decision → exclusion reason) is not yet produced — this remains open, tracked in
`paper/revision_analysis_plan.md` P1-1.

**Q2. "AR-activity site instability: per-site effect sizes with CI (forest plot), and any
site-level covariates (scanner, staining) explaining the sign flip."**

Done (new Figure 6, `fig6_ar_site_forest.pdf`; §Confounder audit). Per-site leave-one-site-out
ρ with patient-cluster bootstrap 95% CI (2,000 reps): −0.13 to +0.27 across 6 sites, all CIs
overlapping zero individually, pooled ρ=+0.195 [0.07,0.31]. Site-level scanner/staining
covariates are **not** available in TCGA-PRAD's public metadata for this cohort — this specific
part of the question remains unanswered for lack of data, stated as such rather than omitted.

**Q3. "How are tiles selected (random/tissue-thresholded/stratified)? Sensitivity to tile count
(16–64) and sampling seeds?"**

Mostly done. Methods now states each cohort's exact method (NADT/PANDA/TCGA-PRAD: random-
uniform rejection sampling, tissue-fraction ≥0.35; LEOPARD: real-tissue-mask grid; PRECISE:
annotation-mask grid) with per-cohort tile counts and thresholds (§1.6). A bounded tile-count ×
scale sensitivity grid for one marker (PTEN) is new (§res-scale-sensitivity, Q7 below covers
the scale half of this). **Not done**: a multi-seed sweep (only one fixed seed was used) —
tracked as a gap in `revision_analysis_plan.md` §4.1.

**Q4. "Confounder audit for marker 7: adjust for PSA, T-stage, margins, age?"**

Done (§res-marker7-clinical, new Supplementary Table S2). Fully-adjusted clinical model (grade
+ age + T-stage + PSA + margin) on a complete-case subset (n=153/270, limited by PSA
availability): marker 7's added value is **no longer significant** (LRT p=0.215 vs. p=0.0011
against grade alone) — surgical margin status alone is a very strong predictor in this subset
(HR≈13). Reported as an honest downgrade of marker 7's characterization, not papered over.

**Q5. "Clarify LEOPARD data-use conditions; confirm approvals obtained."**

Done (new "Ethics and data-use statement" section in `main.tex`). States plainly that approval
has **not** been obtained, the embargo may still be in effect, and this will be re-confirmed
with organizers before submission — no language implying resolution.

**Q6. "PRECISE: per-image or per-patient aggregation? Multiple slides per patient? Biopsy vs.
resection?"**

Done (§PRECISE, Methods). Aggregation is per imaging session (25 patients, 27 sessions — not
"37" as a prior internal-docs typo had it, corrected). All 17 real-Gleason-compared sessions
come from 17 distinct patients, so session-level and patient-level aggregation are numerically
identical for that result — reported as a robustness check. Core-needle biopsy (not resection)
confirmed directly against the dataset's own README/manifest.

**Q7. "Systematic tile-scale sensitivity grid; consider scale-normalization procedures."**

Done, bounded scope as agreed (§res-scale-sensitivity, one marker: PTEN). 3×3 grid, tile count
{16,32,64} × scale {0.44,0.88,1.76} μm/px, on a fixed 90-slide stratified subsample. A real bug
was caught and fixed during this work (see note below) before the final numbers were produced.
Result: scale sensitivity is meaningful at 16 tiles/slide (AUROC range 0.49–0.64) and
attenuates at 32–64 tiles/slide (range narrows to ~0.02–0.03) — consistent with, and refining,
this project's existing 16–64 tile default. No formal scale-normalization procedure was
implemented (out of the agreed bounded scope); this is noted as a further option in
`revision_analysis_plan.md` P2.

**Q8. "SPOP null: ablations on class imbalance, QC filters, site-restricted analyses."**

Partially done. Class-weight ablation (`balanced` vs. none): nearly identical null result
(AUROC 0.508 vs. 0.506) — not an artifact of class-imbalance handling. Site-restricted
leave-one-site-out result (3 testable sites, AUROC 0.57–0.65) is now explicitly reported in the
paper for the first time (previously only in internal docs, not in `main.tex`) — noted as too
thin a basis (3 sites only) to overturn the null. Assay-QC-filter ablation was **not** done —
tracked as a gap.

**Q9. "Survival models: time-dependent AUC, integrated Brier scores, calibration plots, hazard
ratios."**

Done. LEOPARD 3-pool table now reports C-index, td-AUROC@5y, IBS, and calibration slope for all
three pools (new Table, §LEOPARD results). Marker 7's zero-shot transfer gained IBS (0.124),
calibration slope (0.53), and hazard ratio (1.71 [1.34, 2.18]). **Not done**: a full 1–5 year
td-AUC curve or a graphical calibration plot (only single-timepoint/single-number metrics) —
tracked as a gap (`revision_analysis_plan.md` P2).

**Q10. "List all 13 BH-FDR hypotheses explicitly with uncorrected p alongside q, in a
supplement."**

Done in full (new `paper/sections/supplement.tex`, Table S1). All 13 rows, patient-level effect
size, 95% CI, uncorrected p, and BH-FDR q side by side, with an explicit statement of family
membership and exclusion criteria.

---

## Honest net effect on the paper's claims

Two results genuinely **weakened** a prior claim (both are reported, not hidden):
- Marker 7 is grade-independent, but not independent of the full standard clinical covariate
  set (Q4) — its characterization in the reliability map / discussion was revised accordingly.
- Marker 7's headline C-index (0.673) is somewhat specific to our reconstructed label; against
  TCGA's standard PFS endpoint it attenuates to 0.586, still above chance (Q1).

Everything else either added transparency/rigor to an existing claim (Q2, Q3, Q5, Q6, Q9, Q10)
without changing its direction, or added a new, bounded robustness check consistent with
existing defaults (Q7, Q8).

## Remaining gaps (tracked in `paper/revision_analysis_plan.md`, not part of this Tier 1–2 pass)

- Public per-patient label-provenance mapping table (Q1).
- Multi-seed tile-sampling sensitivity (Q3).
- Assay-QC-filter ablation for SPOP (Q8).
- Full 1–5y survival curves / calibration plots rather than single-timepoint metrics (Q9).
- The deeper methodological redesign in `MajorRevision-v1.md` (nested cross-fitting, refit-based
  permutation tests) is a separate, larger undertaking not attempted in this pass — see that
  plan document for scope and priority.
