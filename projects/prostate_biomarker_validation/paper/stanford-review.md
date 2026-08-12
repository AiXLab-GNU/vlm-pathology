Summary
This paper presents a prespecified, confounder-aware qualification protocol to assess whether associations recovered from frozen pathology foundation-model embeddings represent target-specific biology or shortcuts. The authors apply this protocol to seven candidate “histomolecular” signals in prostate cancer using two independently trained encoders (CONCH and Virchow) across multiple cohorts, integrating patient-disjoint cross-validation, multiple-comparison correction, confounder-adjusted tests, and cross-cohort replication. The study yields a five-tier reliability map, shows that grade and tumor/benign phenotype transfer zero-shot across institutions, that PTEN loss is grade-independent and replicable, that SPOP is null, that AR-activity is site-unstable (not a grade shortcut), and that qualification for one target does not imply transfer to a downstream outcome (biochemical recurrence), while also documenting encoder- and scale-dependent pitfalls.

Strengths
Technical novelty and innovation

A prespecified, end-to-end qualification protocol combining patient-disjoint evaluation, confounder auditing (likelihood-ratio and grade-stratified permutation tests), multiple-comparison control, and cross-encoder replication is thoughtfully assembled and consistently applied.
The five-tier reliability map provides an actionable, reusable framework for interpreting results from foundation-model-derived markers beyond mere statistical significance.
The paper surfaces concrete, generalizable pitfalls—tile-scale sensitivity, encoder-dependent transfer direction, and hyperparameter fragility—that are highly relevant to ongoing work in computational pathology.
Experimental rigor and validation

Patient-disjoint cross-validation, site-stratified replication (including leave-one-site-out analysis on TCGA-PRAD), and bootstrap confidence intervals are applied systematically.
Multiple datasets spanning different institutions and assays (NADT-Prostate, PANDA, TCGA-PRAD, PRECISE, LEOPARD) improve the robustness of conclusions.
Cross-encoder replication (CONCH vs. Virchow) is performed for all markers, strengthening claims about generalizability and revealing important asymmetries.
Confounder audits appropriately test grade-independence for molecular and outcome targets using complementary parametric and nonparametric approaches.
Clarity of presentation

The manuscript is unusually forthright about negative and unstable findings, with clear articulation of what the protocol demonstrates and what it does not.
Limitations, post-hoc aspects (marker 7), and differences in outcome definitions are explicitly acknowledged.
Significance of contributions

The work directly addresses widespread concerns about shortcut learning and transfer failure in pathology foundation models and provides a practical roadmap to audit claims.
Findings have immediate implications for the design and interpretation of biomarker studies using frozen encoders and lightweight probes, helping guard against overclaiming and under-audited results.
Weaknesses
Technical limitations or concerns

Several core analyses rely on small cohorts or small effective sample sizes (e.g., NADT-Prostate with 39 patients; PRECISE with 17 images used for Gleason correlation), which inflates variance and limits the precision of effect estimates.
The confounder audit conditions only on Gleason grade; for recurrence modeling, additional clinical confounders (PSA, T stage, margins, CAPRA(-S), age) are not incorporated where available (TCGA-PRAD), leaving residual confounding plausible.
TCGA-PRAD recurrence labels are reconstructed from GDC follow-up fields; this may introduce misclassification relative to standard PFI/RFS/BCR definitions and complicates external interpretability.
Averaging only 16–64 tiles per slide for embeddings risks under-sampling WSIs and may introduce sampling variance and sensitivity to tile selection heuristics.
Experimental gaps or methodological issues

ERG-stain→grade has no external molecular-stain cohort; while stated, the result remains internally supported only.
The zero-shot recurrence pool analysis on LEOPARD returns below-chance performance; while the authors diagnose likely noise amplification under limited events, additional exploratory robustness checks (e.g., dimensionality reduction, simple univariate shrinkage baselines, nested ensembling strategies) could further substantiate the conclusion.
The AR-activity site instability is documented, but per-site effect sizes and diagnostics (e.g., forest plot per site) are not shown, limiting interpretability.
Clarity or presentation issues

Occasional notation confusion (e.g., “p = 0.87” seemingly used for a correlation coefficient) and editorial placeholders (e.g., “VERIFY title/author list”) detract from polish.
Visual content is described rather than shown in the provided text; while extraction artifacts are noted, concise numeric summaries for all key plots would aid readability.
More precise documentation of tile sampling, scale settings, and their sensitivity analyses would strengthen reproducibility.
Missing related work or comparisons

Recent survival-from-H&E studies in prostate cancer that demonstrate independent prognostic value beyond CAPRA(-S) (e.g., deep outcome-driven MIL with large external validations) should be discussed for context and contrasted with the present zero-shot transfer findings.
Related work on robustness to scanner/site effects and representational audits (e.g., scanner-consistency regularization at downstream level; distributional robustness diagnostics like CRoMa) could enrich discussion and triangulate the reported pitfalls.
Additional references on slide-level pretraining paradigms (e.g., slide-scale SSL, multimodal whole-slide context) may help situate the chosen encoders and the decision to use frozen features.
Detailed Comments
Technical soundness evaluation

The protocol is coherent and well-motivated; the dual confounder checks (LRT and grade-stratified permutation) add robustness to claims of grade independence for PTEN and the recurrence marker in TCGA-PRAD.
Patient-disjoint splitting and leave-one-site-out analyses address pseudo-replication and site confounds; this is a strong methodological choice.
The choice to standardize hyperparameters across tests reduces researcher degrees of freedom; however, given task heterogeneity, a sensitivity appendix that demonstrates stability of key conclusions under modest, prespecified hyperparameter variations would further reassure readers.
The reliance on a single clinical covariate (grade) in confounder audits for survival endpoints underutilizes available TCGA data and leaves open questions about independence from other known prognostic factors.
Experimental evaluation assessment

The grade and phenotype results are convincing, with zero-shot transfer to PANDA and PRECISE (for grade) and thorough bootstrap uncertainty.
PTEN loss evidence is strengthened by multi-assay TCGA triangulation and grade-adjusted analyses; AUROC values are modest but consistent across sites, as expected for morphologically-expressive but not perfectly penetrant alterations.
The SPOP null appears carefully vetted; including a brief supplemental summary of the tested alternative explanations and sample size/power calculations would preempt concerns about type II error.
The LEOPARD analysis is thoughtfully split into protocol-frozen zero-shot tests and an exploratory domain-shift diagnostic; the latter’s cross-encoder reproducibility suggests genuine signal in embeddings. Reporting time-dependent AUCs, Brier scores, calibration slopes, and hazard ratio estimates (where applicable) would round out the survival evaluation.
Comparison with related work (using the summaries provided)

The study complements large-scale benchmarking (e.g., Gevaert/Bareja; Neidlinger et al.) by enforcing patient-disjoint splits and adding a confounder audit; it also aligns in spirit with Dawood et al.’s confounder-focused analysis, extending it to prostate cancer and cross-encoder replication.
Recent outcome-driven prostate cancer survival models from H&E show robust external generalization and incremental value beyond CAPRA(-S). Contrasting the present failure of zero-shot recurrence transfer with outcome-optimized models trained on survival endpoints would sharpen the central conclusion: target qualification does not readily translate to outcome prediction without outcome-specific training.
Work on scanner/site robustness and representation auditing (e.g., downstream consistency losses across scanners, CRoMa-style geometry diagnostics) could be cited as complementary toolkits that operationalize or quantify some of the pitfalls observed here.
Discussion of broader impact and significance

The reliability map and prespecified audit protocol are valuable community contributions likely to improve reporting standards and temper overinterpretation of significant associations from frozen embeddings.
The explicit documentation of failure modes (tile scale, encoder asymmetry, hyperparameter fragility) provides reproducible lessons that should be incorporated into future benchmark design and model selection.
The post-hoc recurrence marker emphasizes both opportunities (detectable prognostic signal in embeddings) and hazards (outcome-definition heterogeneity, encoder-transfer asymmetry); this nuance is important for responsible translation.
Questions for Authors
Can you release the exact code and mapping table used to reconstruct TCGA-PRAD recurrence-style labels from GDC, and benchmark this label against standard TCGA endpoints (PFI, DFS/RFS) to quantify concordance and potential misclassification?
For the AR-activity marker’s site instability, could you provide per-site effect sizes with confidence intervals (e.g., a forest plot) and any site-level covariates (scanner, staining) that might explain the sign flip?
How are tiles selected per slide (random uniform, tissue-thresholded, stratified by tissue class), and how sensitive are results to tile count (16–64) and sampling seeds? A brief sensitivity analysis would address under-sampling concerns.
In the TCGA-PRAD confounder audit for recurrence (marker 7), did you test models that adjust for additional clinical covariates available in TCGA (e.g., PSA, T stage, margins, age)? If so, how did the image-derived score perform?
Please clarify the LEOPARD data-use conditions and confirm that you have obtained the necessary approvals to report performance prior to official challenge publications.
For PRECISE, were predictions aggregated per image or per patient, and how were multiple slides per patient handled? Please also confirm slide types (biopsies vs resections) and any harmonization steps taken.
Could you provide a systematic tile-scale sensitivity study (e.g., train/test grid over scales) to quantify the extent and encoder-dependence of scale mismatch effects, and consider simple scale-normalization procedures?
The SPOP null contrasts with earlier single-institution positive reports. Can you share ablations on class imbalance handling, assay QC filters, and site-restricted analyses to rule out underpowered or cohort-specific effects?
For survival models (LEOPARD pools and TCGA transfer), can you provide time-dependent AUC curves, integrated Brier scores, and calibration plots, along with hazard ratios where appropriate?
You report BH-FDR across 13 hypotheses; please list these explicitly and provide the uncorrected p-values alongside q-values in a supplement for transparency.
Overall Assessment
This is a careful, timely, and constructive contribution that squarely addresses a critical issue in computational pathology: separating genuinely transportable biological signal from confounder-driven shortcuts when working with frozen foundation-model embeddings. The prespecified qualification protocol, cross-encoder replication, and explicit negative findings are valuable and, if broadly adopted, would likely raise the standard of evidence in the field. At the same time, aspects of the study would benefit from further strengthening before publication: clarify and release the TCGA recurrence reconstruction; incorporate additional clinical covariates where available for confounder audits; expand reporting of survival metrics and per-site analyses; improve clarity and polish (notation, figures); and broaden related work coverage. I recommend publication contingent on a major revision that addresses these methodological and reporting concerns, which will materially enhance the paper’s rigor, transparency, and impact.
