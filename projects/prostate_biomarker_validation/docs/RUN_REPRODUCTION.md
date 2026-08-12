# Reproducing the qualification analyses and manuscript

Run commands from the repository root. The code preserves the saved analysis
units, endpoints, scores and configuration grids used by the manuscript. It
does not retrain or recalibrate the frozen pathology representations.

## Environment

Create the recorded environment with either:

```bash
conda env create -f environment.yml
conda activate vlm-pathology-revision
```

or install the exact Python package pins from `requirements-lock.txt` into an
isolated environment. The workspace commands below use `.venv/bin/python`.
CONCH and Virchow weights are not vendored.

## Data and model assets

Whole-slide images, source cohort data, pretrained weights, cached embeddings,
access-governed LEOPARD artifacts and patient-level derived outputs are not
redistributed. Obtain them from their original providers under the applicable
terms and place them at the paths documented by the corresponding entry-point
configuration. Publication-facing aggregate source tables and rendered
artifacts are kept separate from these restricted or bulky inputs.

## Audited analysis entry points

```bash
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/aggregate_stability_grid.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/build_tcga_cdr_pfi_evidence.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/build_marker7_survival_paired_analysis.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/run_marker7_common_source_sensitivity.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/build_ar_spop_evidence_closure.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/build_revision_p0_artifacts.py
```

Each final analysis entry point validates its input schema and semantic keys,
records source and output hashes, and fails closed on reconciliation errors.
The stability workflow uses the fixed specification and runners:

```bash
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/build_stability_grid_spec.py
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/run_stability_tcga.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/run_stability_nadt.py --help
.venv/bin/python projects/prostate_biomarker_validation/code/legacy/run_stability_marker7.py --help
```

The resulting encoder--scale--tile--seed cells are correlated sensitivity
settings, not independent patient replications or confirmatory tests.

## Manuscript package

With the saved publication source tables available, build an isolated package
without changing the repository artifacts:

```bash
MPLCONFIGDIR=/tmp/vlm-pathology-mpl \
  .venv/bin/python projects/prostate_biomarker_validation/paper/build_revision_package.py \
  --output-root /tmp/vlm-pathology-submission
```

This regenerates the active figures and tables, validates their manifests and
numeric source mappings, and compiles the main and supplementary PDFs twice.
Use `--skip-pdf` only for a focused non-PDF package check.

## Verification

```bash
MPLCONFIGDIR=/tmp/vlm-pathology-mpl \
  .venv/bin/python -m unittest discover -s projects/prostate_biomarker_validation/tests -v
.venv/bin/python -m py_compile \
  projects/prostate_biomarker_validation/code/legacy/build_revision_p0_artifacts.py \
  projects/prostate_biomarker_validation/code/legacy/aggregate_stability_grid.py \
  projects/prostate_biomarker_validation/code/legacy/build_tcga_cdr_pfi_evidence.py \
  projects/prostate_biomarker_validation/code/legacy/build_marker7_survival_paired_analysis.py \
  projects/prostate_biomarker_validation/code/legacy/run_marker7_common_source_sensitivity.py \
  projects/prostate_biomarker_validation/code/legacy/build_ar_spop_evidence_closure.py \
  projects/prostate_biomarker_validation/paper/build_revision_package.py
```

PNI clinician labels are not inputs to this project. Cohort and embedding assets are
registered separately in `infrastructure/shared/cohort_manifests/` and `resources/projects/prostate_biomarker_validation/model_workspace/`.
Endpoint names remain source-specific: reconstructed recurrence, PFS, DFS and
official TCGA-CDR PFI are not interchangeable.
