# Scientific Reports Manuscript Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a readable, claim-consistent, CSV-driven Scientific Reports submission manuscript and separate supplementary PDF from the frozen analysis outputs.

**Architecture:** A single submission configuration defines active TeX sections, figures, tables, and source lineage. Small validators enforce journal structure, claim wording, figure sizing, and numeric provenance before the package builder renders six main figures, supplementary assets, generated tables, and two PDFs. Existing frozen analysis outputs remain immutable; only verified saved CSV/JSON results flow into submission artifacts.

**Tech Stack:** Python 3.11, pandas, NumPy, Matplotlib, SciPy, standard-library `unittest`, XeLaTeX.

## Global Constraints

- Follow `infrastructure/docs/superpowers/specs/2026-08-07-scientific-reports-manuscript-redesign-design.md`.
- Do not modify frozen model results, raw datasets, coordinates, embeddings, or reviewer inputs.
- Do not run new GPU inference, optional sampling experiments, or nested PCA selection.
- Do not mention internal work-package names, approval gates, or unused compute in submission-facing prose.
- Treat the 360 cells as a correlated sensitivity grid, never as independent validations or confirmatory tests.
- Preserve exact endpoint names and never rename reconstructed recurrence, PFS, or DFS as official PFI.
- Generate every active result figure and table from saved CSV sources.
- Preserve undefined bootstrap rows and report their count and fraction.
- Do not invent author contributions, funding, competing interests, ethics, or consent metadata.
- Do not stage, commit, push, create a remote, upload, or submit. Each task ends with an explicit diff/status checkpoint instead of a commit.
- Use `.venv/bin/python` for Python commands.

---

## File Structure

### New control and validation modules

- `paper/submission_config.py`: one source of truth for active TeX sections, six main figures, supplementary figures, tables, dimensions, and lineage paths.
- `paper/manuscript_contract.py`: TeX-aware title, abstract, section-order, word-count, forbidden-wording, and declaration validation.
- `paper/figures/style.py`: final-size journal plotting constants and shared Matplotlib configuration.
- `paper/generate_submission_tables.py`: fail-closed CSV-to-TeX table generation.
- `tests/test_scientific_reports_manuscript.py`: manuscript structure and claim-language contracts.
- `tests/test_scientific_reports_figures.py`: final-size figure style, source, and deterministic-render contracts.

### New submission-facing TeX

- `paper/sections/results.tex`: six decision-oriented Results subsections.
- `paper/sections/discussion.tex`: bounded interpretation, limitations, and conclusion.
- `paper/sections/methods.tex`: cohorts, frozen encoders, qualification design, statistics, endpoints, and reproducibility.
- `paper/sections/declarations.tex`: availability and verified declarations only.
- `paper/supplement_main.tex`: separate Supplementary Information document.
- `paper/sections/supplementary_information.tex`: detailed grids, endpoint sensitivities, bootstrap diagnostics, and provenance.

### Active figure system

- `paper/figures/fig1_qualification_map.py`
- `paper/figures/fig2_transportable_signals.py`
- `paper/figures/fig3_molecular_qualification.py`
- `paper/figures/fig4_confounder_site_audit.py`
- `paper/figures/fig5_marker7_transfer.py`
- `paper/figures/fig6_stability_overview.py`
- `paper/figures/sfig1_detailed_roc.py`
- `paper/figures/sfig2_marker7_survival.py`
- `paper/figures/sfig3_stability_heatmaps.py`

Existing figure scripts and outputs remain preserved but become inactive once the new manifests and TeX references pass.

---

### Task 1: Establish submission configuration and failing manuscript contracts

**Files:**
- Create: `paper/submission_config.py`
- Create: `paper/manuscript_contract.py`
- Create: `tests/test_scientific_reports_manuscript.py`
- Modify: `paper/build_revision_package.py`

**Interfaces:**
- Produces: `ACTIVE_MAIN_TEX: Sequence[str]`, `ACTIVE_SUPPLEMENT_TEX: Sequence[str]`, `MAIN_FIGURES: Sequence[FigureSpec]`, `SUPPLEMENT_FIGURES: Sequence[FigureSpec]`, `TABLES: Sequence[TableSpec]`.
- Produces: `validate_manuscript(root: Path) -> list[ContractResult]` where each result has `check_id`, `passed`, and `detail`.
- Consumes: current `paper/main.tex`, active section files, and the approved design.

- [ ] **Step 1: Add the configuration dataclasses and exact active-path contract**

```python
from collections.abc import Sequence
from dataclasses import dataclass

@dataclass(frozen=True)
class FigureSpec:
    figure_id: str
    label: str
    sources: Sequence[str]
    script: str
    output: str
    manuscript: str
    width_mm: int

ACTIVE_MAIN_TEX = (
    "paper/main.tex",
    "paper/sections/abstract.tex",
    "paper/sections/introduction.tex",
    "paper/sections/results.tex",
    "paper/sections/discussion.tex",
    "paper/sections/methods.tex",
    "paper/sections/declarations.tex",
    "paper/sections/bibliography.tex",
)
```

- [ ] **Step 2: Write manuscript contract tests that fail on the current draft**

```python
def test_submission_title_abstract_and_section_order():
    results = {row.check_id: row for row in validate_manuscript(ROOT)}
    assert results["TITLE_WORDS_LE_20"].passed
    assert results["ABSTRACT_WORDS_LE_200"].passed
    assert results["SECTION_ORDER"].passed

def test_submission_has_no_internal_workflow_or_embargo_block_text():
    failures = scan_forbidden_submission_language(ROOT)
    assert failures == []
```

The forbidden list must include `MajorRevision-v1`, `Gate A`, `Gate B`, `R1--R5`, `A3`, `Additional GPU`, `internal analysis`, `embargo pending`, and `To be completed`.

- [ ] **Step 3: Run the tests and capture the expected current-draft failures**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_manuscript -v`

Expected: FAIL for title length, abstract length, section order, declarations, and internal workflow wording.

- [ ] **Step 4: Implement TeX-aware contract helpers without weakening expectations**

Implement `strip_tex_commands(text: str) -> str`, `count_prose_words(text: str) -> int`, `extract_environment(text: str, name: str) -> str`, and `validate_manuscript(root: Path)`. Comments, labels, citations, math commands, and URLs must not inflate prose word counts.

- [ ] **Step 5: Run helper-level tests and inspect the explicit checkpoint**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_manuscript.ManuscriptContractUnitTests -v`

Expected: helper tests PASS while submission-draft tests remain FAIL.

Run: `git diff -- paper/submission_config.py paper/manuscript_contract.py tests/test_scientific_reports_manuscript.py paper/build_revision_package.py`

---

### Task 2: Freeze claim, endpoint, and numeric source contracts

**Files:**
- Modify: `resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py`
- Modify: `paper/claim_evidence_matrix.csv`
- Modify: `paper/claim_evidence_matrix.md`
- Modify: `paper/endpoint_hierarchy.csv`
- Modify: `paper/endpoint_hierarchy.md`
- Create: `paper/figure_data/fig1_qualification_map.csv`
- Create: `paper/figure_data/fig2_transportable_signals.csv`
- Create: `paper/figure_data/fig3_molecular_qualification.csv`
- Create: `paper/figure_data/fig4_confounder_site_audit.csv`
- Create: `paper/figure_data/fig5_marker7_transfer.csv`
- Create: `paper/figure_data/fig6_stability_overview.csv`
- Modify: `tests/test_paper_revision_artifacts.py`

**Interfaces:**
- Produces: six tidy, deterministic main-figure CSVs with `source_path`, `source_field`, and evidence-state fields.
- Produces: claim states limited to `transportable`, `context_sensitive`, and `unsupported_in_frozen_design` plus explicitly descriptive framework rows.
- Consumes: verified R1--R5 saved outputs; no model inference.

- [ ] **Step 1: Add failing exact-schema tests for all six figure source tables**

```python
EXPECTED_FIGURE_SOURCE_ROWS = {
    "fig1_qualification_map.csv": 7,
    "fig2_transportable_signals.csv": 4,
    "fig3_molecular_qualification.csv": 6,
}

def test_submission_figure_sources_have_lineage_and_allowed_states():
    for name, expected_minimum in EXPECTED_FIGURE_SOURCE_ROWS.items():
        frame = pd.read_csv(ROOT / "paper/figure_data" / name)
        assert len(frame) >= expected_minimum
        assert frame["source_path"].str.len().gt(0).all()
        assert frame["source_field"].str.len().gt(0).all()
```

For figures 4--6, test exact semantic keys rather than a remembered row count: all expected sites, both endpoints, and all six markers must be present.

- [ ] **Step 2: Run the focused tests and verify missing-source failure**

Run: `.venv/bin/python -m unittest tests.test_paper_revision_artifacts -v`

Expected: FAIL because the six submission source CSVs do not yet exist.

- [ ] **Step 3: Update the P0 builder to read frozen tables and emit submission sources atomically**

Use a temporary directory and publish only after validating:

```python
def build_submission_figure_sources(root: Path, output_dir: Path) -> dict[str, Path]:
    builders = {
        "fig1_qualification_map.csv": build_qualification_map,
        "fig2_transportable_signals.csv": build_transportable_signals,
        "fig3_molecular_qualification.csv": build_molecular_qualification,
        "fig4_confounder_site_audit.csv": build_confounder_site_audit,
        "fig5_marker7_transfer.csv": build_marker7_transfer,
        "fig6_stability_overview.csv": build_stability_overview,
    }
    written = {}
    for filename, builder in builders.items():
        frame = builder(root)
        validate_submission_source(filename, frame, root)
        path = output_dir / filename
        frame.to_csv(path, index=False)
        written[filename] = path
    return written
```

The builder must calculate presentation summaries from source rows, never from prose constants. Figure 6 summarizes the 72 saved configurations and uses the full grid only through saved Figure 9 CSVs.

Define the six builder functions with signature `(root: Path) -> pd.DataFrame` and these fixed inputs: qualification map from `claim_evidence_matrix.csv`; transportable signals from `statistical_corrections_summary.csv` plus the saved PANDA/PRECISE result sources; molecular qualification from `statistical_corrections_summary.csv`, `stability_summary.csv`, and `spop_site_summary.csv`; confounder/site audit from `confounder_nested_summary.csv`, `confounder_nested_virchow_summary.csv`, and `ar_site_forest_summary.csv`; marker 7 transfer from `pfi_performance_summary.csv` and `marker7_survival_paired_deltas.csv`; stability overview from `stability_summary.csv` and `stability_contrast_summary.csv`. `validate_submission_source` requires unique semantic keys, finite primary estimates, explicit missingness fields, repository-relative existing source paths, and source-field names present in the referenced CSV schema.

- [ ] **Step 4: Regenerate claim and endpoint artifacts**

Run: `.venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py`

Expected: all six source CSVs are created, endpoint `E08_official_pfi` remains distinct, and claim C04 does not use `robust null`.

- [ ] **Step 5: Verify frozen inputs did not change**

Run: `sha256sum resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv`

Compare against their input/run manifests. Any mismatch stops implementation before prose editing.

- [ ] **Step 6: Run focused tests and inspect the checkpoint**

Run: `.venv/bin/python -m unittest tests.test_paper_revision_artifacts -v`

Expected: PASS.

Run: `git diff -- resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py paper/claim_evidence_matrix.csv paper/claim_evidence_matrix.md paper/endpoint_hierarchy.csv paper/endpoint_hierarchy.md paper/figure_data tests/test_paper_revision_artifacts.py`

---

### Task 3: Implement a final-size figure style contract

**Files:**
- Create: `paper/figures/style.py`
- Create: `tests/test_scientific_reports_figures.py`
- Modify: `paper/submission_config.py`

**Interfaces:**
- Produces: `apply_journal_style() -> None`, `figure_size(width_mm: int, aspect: float) -> tuple[float, float]`, `save_vector_figure(fig, output: Path) -> None`.
- Produces constants: `MIN_FONT_PT = 8.0`, `AXIS_FONT_PT = 9.0`, `PANEL_FONT_PT = 11.0`, `MIN_LINE_PT = 1.0`, `SINGLE_COLUMN_MM = 89`, `DOUBLE_COLUMN_MM = 180`.

- [ ] **Step 1: Write failing style and geometry tests**

```python
def test_final_size_style_minima():
    apply_journal_style()
    assert mpl.rcParams["font.size"] >= 8.0
    assert mpl.rcParams["axes.linewidth"] >= 1.0
    assert mpl.rcParams["lines.linewidth"] >= 1.0

def test_double_column_width_is_180_mm():
    width, _ = figure_size(180, 0.62)
    assert abs(width - 180 / 25.4) < 1e-9
```

- [ ] **Step 2: Run and verify missing-module failure**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_figures.FigureStyleTests -v`

Expected: FAIL because `paper.figures.style` is absent.

- [ ] **Step 3: Implement the shared style**

Use DejaVu Sans, white backgrounds, the fixed palette `#0072B2`, `#D55E00`, `#009E73`, `#6B7280`, and deterministic PDF metadata. `save_vector_figure` must create parent directories, remove volatile PDF metadata, call `bbox_inches="tight"`, and close the figure.

- [ ] **Step 4: Run style tests and a two-render hash test**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_figures.FigureStyleTests -v`

Expected: PASS, including byte-identical PDFs from two renders of the fixture plot.

- [ ] **Step 5: Inspect the checkpoint**

Run: `git diff -- paper/figures/style.py paper/submission_config.py tests/test_scientific_reports_figures.py`

---

### Task 4: Render six legible main figures and three detailed supplementary figures

**Files:**
- Create: `paper/figures/fig1_qualification_map.py`
- Create: `paper/figures/fig2_transportable_signals.py`
- Create: `paper/figures/fig3_molecular_qualification.py`
- Create: `paper/figures/fig4_confounder_site_audit.py`
- Create: `paper/figures/fig5_marker7_transfer.py`
- Create: `paper/figures/fig6_stability_overview.py`
- Create: `paper/figures/sfig1_detailed_roc.py`
- Create: `paper/figures/sfig2_marker7_survival.py`
- Create: `paper/figures/sfig3_stability_heatmaps.py`
- Modify: `tests/test_scientific_reports_figures.py`
- Modify: `paper/submission_config.py`

**Interfaces:**
- Every module produces `load_sources(source_paths: Sequence[Path]) -> Sequence[pd.DataFrame]` and `render(source_paths: Sequence[Path], output_pdf: Path) -> None`.
- Main renderers consume only the six submission CSVs from Task 2.
- Supplement stability renderer consumes `fig9_stability_grid.csv` and `fig9_stability_contrasts.csv` and reuses the existing fail-closed validators.

- [ ] **Step 1: Add exact source-validation tests for each renderer**

Each test must mutate one required column, duplicate one semantic key, and remove one expected group. Every mutation must raise `ValueError` before plotting.

```python
def test_fig6_rejects_missing_marker(self):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.csv"
        frame = pd.read_csv(FIG6_SOURCE)
        frame.loc[frame.marker != "SPOP"].to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, "six markers"):
            load_sources([path])
```

- [ ] **Step 2: Run renderer tests and verify missing-module failures**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_figures -v`

Expected: FAIL for the nine absent renderer modules.

- [ ] **Step 3: Implement figures 1--3 at final dimensions**

Figure 1 uses a compact evidence-state matrix rather than a text-heavy flowchart. Figure 2 shows grade and phenotype transport with patient-level denominators and intervals. Figure 3 uses a common null-aligned scale or separated metric panels so AUROC and correlation are not visually conflated.

- [ ] **Step 4: Implement figures 4--6 at final dimensions**

Figure 4 separates pooled association from grade-adjusted increment and site transport. Figure 5 separates official PFI from reconstructed recurrence and labels the 153-patient complete-case contrast. Figure 6 shows marker-level range/null crossing and configuration sensitivity; it must not reproduce the full 360-cell heatmap in the main paper.

- [ ] **Step 5: Implement supplementary figures**

Supplementary Figure 1 contains detailed ROC curves, Supplementary Figure 2 contains marker-7 survival/calibration diagnostics, and Supplementary Figure 3 contains the full stability heatmaps and paired contrasts. Use at least 180 mm width and split across multiple pages/panels if any label would fall below 8 pt.

- [ ] **Step 6: Render twice and verify deterministic outputs**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_figures -v`

Expected: PASS for schema rejection, final-size constants, and two-render SHA256 equality for all nine PDFs.

- [ ] **Step 7: Inspect figures visually at final scale**

Rasterize each PDF at 150 dpi, inspect the nine page images, and record any clipped labels, overlapping legends, or illegible ticks in the test failure output. Correct every defect before proceeding.

- [ ] **Step 8: Inspect the checkpoint**

Run: `git diff -- paper/figures paper/submission_config.py tests/test_scientific_reports_figures.py`

---

### Task 5: Rewrite the main manuscript into Scientific Reports structure

**Files:**
- Modify: `paper/main.tex`
- Modify: `paper/sections/abstract.tex`
- Modify: `paper/sections/introduction.tex`
- Create: `paper/sections/results.tex`
- Create: `paper/sections/discussion.tex`
- Create: `paper/sections/methods.tex`
- Modify: `tests/test_scientific_reports_manuscript.py`

**Interfaces:**
- Consumes: Task 2 claim/endpoint artifacts and Task 4 main figures.
- Produces: title ≤20 words, abstract ≤200 words, main narrative ≤4,500 words excluding Methods, and section order Introduction--Results--Discussion--Methods.

- [ ] **Step 1: Extend failing tests for the six Results decisions and five Discussion parts**

```python
def test_results_use_approved_decision_order():
    text = active_main_text(ROOT)
    required = (
        "Study design and qualification criteria",
        "Transportable grade and phenotype signals",
        "Molecular target qualification",
        "Confounder and site audits",
        "Correlated stability analysis",
        "Endpoint-conditioned recurrence transfer",
    )
    assert appear_in_order(text, required)
```

Add forbidden-claim assertions for `robust null`, `universal encoder`, `360 independent`, `clinically validated`, `prognostic biomarker`, and any unqualified `external validation` claim.

- [ ] **Step 2: Run manuscript tests and capture expected structural failures**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_manuscript -v`

Expected: FAIL because the new sections are absent and the current abstract/title exceed limits.

- [ ] **Step 3: Replace title and abstract**

Use the approved working title, remove workflow-status lines and the draft date from the submission face, and write an abstract of 170--195 words containing objective, design, strongest results, bounded molecular/recurrence results, and conclusion.

- [ ] **Step 4: Rewrite the Introduction to three concise parts**

Limit to the problem, evidence gap, and study objective. Remove literature-review repetition and all claims that cannot be tied to verified primary references.

- [ ] **Step 5: Write the six-part Results section**

Each subsection must state cohort/analysis unit, primary estimate and interval, evidence state, and local limitation. Pull all numeric strings from generated TeX macros or validate them through `run_numeric_qa`; do not type a number that lacks a source field.

- [ ] **Step 6: Write Discussion and consolidated limitations**

Lead with the qualification result, explain target-specific context sensitivity, state the correlated-grid and endpoint limitations once, and end with research qualification rather than clinical deployment.

- [ ] **Step 7: Write Methods in reproducible order**

Include cohorts, label sources, embedding and aggregation, fixed probes/folds, qualification criteria, confounder/site analyses, stability-grid interpretation, recurrence endpoints, paired bootstrap, multiplicity, and software/provenance. Describe the PCA sweep only as exploratory sensitivity; do not mention internal experiment labels or unused computation.

- [ ] **Step 8: Run manuscript contracts and word counts**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_manuscript -v`

Expected: title, abstract, order, word-count, claim wording, and figure-reference tests PASS except declaration tests reserved for Task 6.

- [ ] **Step 9: Inspect the checkpoint**

Run: `git diff -- paper/main.tex paper/sections/abstract.tex paper/sections/introduction.tex paper/sections/results.tex paper/sections/discussion.tex paper/sections/methods.tex tests/test_scientific_reports_manuscript.py`

---

### Task 6: Separate supplementary information and add verified submission declarations

**Files:**
- Create: `paper/supplement_main.tex`
- Create: `paper/sections/supplementary_information.tex`
- Create: `paper/sections/declarations.tex`
- Modify: `paper/sections/bibliography.tex`
- Create: `paper/author_action_items.md`
- Modify: `tests/test_scientific_reports_manuscript.py`

**Interfaces:**
- Produces: independent `paper/supplement_main.pdf`.
- Produces: `author_action_items.md` containing only missing author-controlled facts, each with `blocking: yes|no`.
- Consumes: verified public sources for Scientific Reports formatting and LEOPARD publication status.

- [ ] **Step 1: Add failing tests for separate supplement and declarations**

Test that `main.tex` does not input supplementary content, `supplement_main.tex` does, and the main manuscript contains Data Availability, Code Availability, Author Contributions, Competing Interests, and Ethics statements.

- [ ] **Step 2: Verify every `[VERIFY]` bibliography entry against a primary source**

Use publisher pages, DOI records, PubMed, arXiv, OpenReview, or official dataset/model records. Record exact title, authors as allowed by the citation style, year, venue, DOI/URL, and access date. Do not cite search-result pages.

- [ ] **Step 3: Replace the stale LEOPARD entry**

Cite the 2026 MIDL challenge paper as a conference publication and the organizer baseline manuscript as a preprint. Remove every statement that publication is blocked by an unresolved embargo. Do not call the preprint a journal article.

- [ ] **Step 4: Write declarations from verified local facts**

Describe public/access-governed data separately, name reproducible code entry points without promising an unauthorized public repository, and preserve existing verified ethics/data-use facts. If author contribution, funding, conflict, or consent facts cannot be established, omit invented prose and add an exact blocking item to `paper/author_action_items.md`.

- [ ] **Step 5: Move detailed analyses to the supplement**

Include the 17-test family, full stability tables, detailed heatmaps, endpoint concordance, bootstrap undefined counts, common-498 sensitivity, AR/SPOP site-power details, and provenance. Remove internal gate/work-package vocabulary during the move.

- [ ] **Step 6: Run manuscript and citation contracts**

Run: `.venv/bin/python -m unittest tests.test_scientific_reports_manuscript -v`

Expected: PASS. Any unresolved author-controlled fact appears only in `author_action_items.md` and causes package status `partial`, not fabricated manuscript content.

- [ ] **Step 7: Inspect the checkpoint**

Run: `git diff -- paper/supplement_main.tex paper/sections/supplementary_information.tex paper/sections/declarations.tex paper/sections/bibliography.tex paper/author_action_items.md tests/test_scientific_reports_manuscript.py`

---

### Task 7: Generate tables, manifests, numeric QA, and both PDFs from one entry point

**Files:**
- Create: `paper/generate_submission_tables.py`
- Modify: `paper/build_revision_package.py`
- Modify: `paper/figure_manifest.csv`
- Modify: `paper/table_manifest.csv`
- Modify: `tests/test_revision_final_package.py`
- Modify: `tests/test_revision_final_figures.py`

**Interfaces:**
- Produces: `build_submission_package(output_root: Path, build_pdf: bool = True) -> PackageReport`.
- Produces: six main-figure rows, three supplementary-figure rows, and complete generated-table rows with source/script/output/manuscript hashes.
- Supports: `--output-root PATH` and `--skip-pdf`.

- [ ] **Step 1: Write failing tests for the new manifest and temporary-root contract**

```python
def test_manifest_covers_six_main_and_three_supplement_figures(tmp_path):
    report = build_submission_package(tmp_path, build_pdf=False)
    manifest = pd.read_csv(report.figure_manifest)
    assert set(manifest["figure_id"]) == {
        "F1", "F2", "F3", "F4", "F5", "F6", "SF1", "SF2", "SF3"
    }
```

Add tests for source/script/output SHA256, manuscript reference, stale output rejection, no absolute paths, and no self-referential manifest hashes.

- [ ] **Step 2: Run and verify failure against the nine-old-figure builder**

Run: `.venv/bin/python -m unittest tests.test_revision_final_package -v`

Expected: FAIL because the current builder hard-codes F1--F9 and writes into `paper/`.

- [ ] **Step 3: Implement CSV-to-TeX tables with fail-closed schemas**

Generate compact main tables and detailed supplementary tables. Each renderer receives a dataframe and output path, validates exact semantic keys, formats by a centralized rounding map, and writes deterministic TeX.

- [ ] **Step 4: Refactor the package builder around `submission_config.py`**

Remove duplicated hard-coded `FIGURE_SPECS` and `TABLE_SPECS`. Render all outputs into `output_root`, validate them, then publish to `paper/` only after a complete successful repository-root run.

- [ ] **Step 5: Expand numeric QA from remembered literals to source-field mappings**

Create a mapping table with `claim_id`, `source_path`, `row_key`, `field`, `display_format`, and `expected_tex_token`. Validate every main-text numeric token used for primary claims. Retain exact checks for official PFI, common-cohort deltas, undefined replicates, and stability counts.

- [ ] **Step 6: Build both TeX documents twice**

Run: `.venv/bin/python paper/build_revision_package.py`

Expected: main and supplement XeLaTeX each succeed twice, unresolved references/citations are zero, and no overfull box remains above 1 pt.

- [ ] **Step 7: Run temporary-root deterministic build**

Run: `submission_tmp=$(mktemp -d); .venv/bin/python paper/build_revision_package.py --output-root "$submission_tmp" --skip-pdf`

Repeat with a second temporary root and compare declared deterministic CSV, TeX, and PDF figure hashes. Remove neither directory until comparison results are recorded.

- [ ] **Step 8: Run final-package tests and inspect the checkpoint**

Run: `.venv/bin/python -m unittest tests.test_revision_final_package tests.test_revision_final_figures -v`

Expected: PASS.

Run: `git diff -- paper/generate_submission_tables.py paper/build_revision_package.py paper/figure_manifest.csv paper/table_manifest.csv tests/test_revision_final_package.py tests/test_revision_final_figures.py`

---

### Task 8: Perform complete scientific, visual, and reproducibility QA

**Files:**
- Modify: `paper/MajorRevision-v1-compliance-report.md`
- Modify: `paper/numeric_consistency_report.md`
- Modify: `paper/reproducibility_report.md`
- Modify: `paper/main.pdf`
- Create: `paper/supplement_main.pdf`

**Interfaces:**
- Consumes: all changed source files and frozen manifests.
- Produces: evidence-backed `complete`, `partial`, or `blocked` status and exact remaining author actions.

- [ ] **Step 1: Syntax-check every changed Python file**

Run: `.venv/bin/python -m py_compile paper/submission_config.py paper/manuscript_contract.py paper/generate_submission_tables.py paper/build_revision_package.py paper/figures/style.py paper/figures/fig1_qualification_map.py paper/figures/fig2_transportable_signals.py paper/figures/fig3_molecular_qualification.py paper/figures/fig4_confounder_site_audit.py paper/figures/fig5_marker7_transfer.py paper/figures/fig6_stability_overview.py paper/figures/sfig1_detailed_roc.py paper/figures/sfig2_marker7_survival.py paper/figures/sfig3_stability_heatmaps.py resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py`

Expected: exit 0.

- [ ] **Step 2: Run all focused manuscript and analysis tests**

Run: `.venv/bin/python -m unittest tests.test_paper_revision_artifacts tests.test_scientific_reports_manuscript tests.test_scientific_reports_figures tests.test_revision_final_figures tests.test_revision_final_package tests.test_tcga_cdr_pfi_evidence tests.test_marker7_survival_paired_analysis tests.test_marker7_common_source_sensitivity tests.test_ar_spop_evidence_closure tests.test_aggregate_stability_grid -v`

Expected: all tests PASS with zero skipped integrity checks for present real data.

- [ ] **Step 3: Run full test discovery**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test*.py' -v`

Expected: all tests PASS.

- [ ] **Step 4: Confirm immutable PRECISE source**

Run: `sha256sum 'resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv'`

Expected: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.

- [ ] **Step 5: Run prose, endpoint, secret, and path scans**

Scan active submission files for prohibited claims, internal workflow terms, unresolved citation markers, absolute workstation paths, credentials, endpoint substitutions, and bracketed drafting notes. Print only path and rule identifier for a possible credential finding, never the matched secret value.

- [ ] **Step 6: Visually inspect every PDF page**

Rasterize `paper/main.pdf` and `paper/supplement_main.pdf`. Inspect all pages for clipped text, font size, panel balance, table overflow, legend collisions, duplicated legends, blank pages, orphan headings, and inconsistent figure numbering. Any defect reopens the owning task.

- [ ] **Step 7: Record final artifact hashes and status**

Run: `sha256sum paper/main.pdf paper/supplement_main.pdf`

Record byte sizes, timestamps, source hashes, test totals, zero-mismatch counts, and author-action blockers in the three QA reports. Remove internal “GPU omitted/A3 omitted” lines from the submission compliance summary; internal scope is already governed by the design and plan.

- [ ] **Step 8: Review the explicit final diff without staging**

Run: `git status --short`

Run: `git diff --stat -- infrastructure/docs/superpowers/specs/2026-08-07-scientific-reports-manuscript-redesign-design.md infrastructure/docs/superpowers/plans/2026-08-07-scientific-reports-manuscript-redesign.md resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py paper tests`

Expected: only intended source, generated manuscript, figure, table, report, and test paths are changed; no dataset, frozen analysis output, cache, model weight, or credential file is modified.

---

## Plan Self-Review

- Spec coverage: central narrative, claim hierarchy, manuscript order, word limits, six main figures, supplementary split, final-size typography, CSV lineage, endpoint integrity, declarations, and full QA each map to Tasks 1--8.
- Scope: manuscript architecture, visual system, and QA are coupled by one submission configuration and one builder, so they form one testable package rather than independent projects.
- Type consistency: `FigureSpec`, `TableSpec`, `ContractResult`, and `PackageReport` are defined before their consumers; all figure modules expose the same `load_sources` and `render` boundary.
- Frozen-analysis safety: no task edits or regenerates raw R1--R5 result files; Task 2 verifies them before building derived presentation sources.
- Submission/internal separation: internal scope labels remain only in design, plan, and audit reports; active TeX scans reject them.
- Author metadata safety: missing author-controlled facts become explicit blocking actions and are never invented.
- Placeholder scan: implementation steps contain concrete files, interfaces, commands, expected failures, and pass conditions.
