# Major-revision reproduction entry points

Run commands from the repository root. Existing cached embeddings are required for the
CPU-only analyses; raw-slide stability reruns additionally require the local slide data and
model weights.

## Environment

```bash
conda env create -f environment.yml
conda activate vlm-pathology-revision
```

The current workspace also contains `models/.venv-conch`. The lock files capture the core
analysis package versions observed in that environment. CONCH and Virchow weights are not
vendored by these files.

## Rebuild documentation/provenance artifacts

```bash
models/.venv-conch/bin/python models/build_revision_p0_artifacts.py
```

## Core completed analyses

```bash
models/.venv-conch/bin/python models/pilot_confounder_audit_nested.py
models/.venv-conch/bin/python models/pilot_confounder_refit_permutation.py \
  --n-perm 2000 --suffix final2000
models/.venv-conch/bin/python models/pilot_marker7_clinical_hierarchy.py
models/.venv-conch/bin/python models/pilot_tcga_prad_label_benchmark.py
models/.venv-conch/bin/python models/pilot_marker7_survival_curves.py
models/.venv-conch/bin/python models/build_revision_global_fdr.py
```

## Freeze the pending stability-grid design

```bash
models/.venv-conch/bin/python models/build_stability_grid_spec.py
```

This creates the 360-cell minimum design and marker-specific patient fold assignments. The
GPU smoke/full runners must consume these files rather than constructing new folds per cell.

The coordinate-audited GPU runners are:

```bash
models/.venv-conch/bin/python models/run_stability_tcga.py --help
models/.venv-conch/bin/python models/run_stability_nadt.py --help
models/.venv-conch/bin/python models/run_stability_marker7.py --help
```

They save incremental outputs under `models/stability_runs/<tag>/`, including accepted tile
coordinates, per-tile embeddings, metadata, cell metrics, and fold metrics. Tile-count cells
reuse fixed prefixes of the same maximum-size sampled tile set.

### Durable full-grid session

The long-running full grid is supervised by tmux session `vlm_stability`, with windows
`tcga_conch`, `tcga_virchow`, `nadt_conch`, `nadt_virchow`, and `marker7`. It was migrated from
interactive PTYs after 96 cells had completed. All runners support configuration-level resume
and skip a configuration only when its complete cell rows and coordinate/embedding/meta cache
files all exist.

```bash
tmux attach -t vlm_stability
tmux list-windows -t vlm_stability
tail -f models/stability_runs/logs/tcga_conch.log
```

Inside tmux, use `Ctrl-b w` to select a window and `Ctrl-b d` to detach without stopping work.
The launch dispatcher is `models/run_stability_tmux.sh`.

The 2,000-permutation command can take substantial CPU time. Existing final CSVs should be
retained when only rebuilding the manuscript.

## Manuscript

```bash
cd paper
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

## Known remaining reproduction gaps

- The full 6-marker × 2-encoder × 5-seed tile/scale grid has not yet been run.
- Historical tile coordinates were not saved; new stability runs must save them.
- Official TCGA-CDR PFI has not yet been added; current benchmark files contain PFS/DFS.
- Some figure scripts still contain transcribed numerical values or absolute project paths.
- `protocol_provenance.json` is a retrospective checksum snapshot, not evidence of a historical
  Git protocol-freeze commit.
