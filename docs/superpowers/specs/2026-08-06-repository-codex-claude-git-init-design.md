# Repository Codex, Claude, and Git Initialization Design

Date: 2026-08-06
Status: Approved approach — research code and documentation only

## 1. Objective

Initialize `/home/jinhyun/prj_ws/prj_jin/vlm-pathology` as a Git repository
that is safe for Codex and Claude-assisted research development without adding
the approximately 79 GB workspace contents to version control.

The initial repository will track research instructions, reproducibility
metadata, approved design documents, tests, and the PRECISE PNI analysis code.
Raw/open-dataset mirrors, WSI, model weights, virtual environments, caches, and
generated audit outputs will remain outside Git.

## 2. Agent initialization files

### `AGENTS.md`

The root Codex instruction file will define:

- the PRECISE PNI project purpose and current study boundaries;
- immutable clinician-source and frozen-score rules;
- requirements to read approved design documents before implementation;
- test-first, provenance, hashing, deterministic rerun, and cautious-claim
  requirements;
- paths that must not be modified or committed;
- the Python environment and standard verification commands;
- the rule that generated outputs and large pathology data are not Git-tracked.

### `CLAUDE.md`

The root Claude instruction file will contain the same project-level safety and
reproducibility rules, expressed for Claude Code. It will point to `AGENTS.md`
as the shared source of project policy and repeat the critical immutable-data,
blinding, interpretation, and verification requirements so either agent can
work safely when invoked independently.

Neither file will contain secrets, machine credentials, private tokens, or
instructions to access external services.

## 3. Ignore policy

The root `.gitignore` will exclude at minimum:

- `opendataset/` and `song-datasets/`;
- virtual environments including `.venv/` and `models/.venv-*`;
- model/download caches, Hugging Face caches, checkpoints, and common weight
  formats;
- `__pycache__`, pytest/mypy/ruff caches, notebook checkpoints, and temporary
  files;
- local Codex/Claude/agent state directories while retaining root
  `AGENTS.md` and `CLAUDE.md`;
- generated paper build artifacts and common operating-system/editor files;
- large pathology image and array formats such as SVS, TIFF, OME-TIFF, Zarr,
  NPY, NPZ, and HDF5.

The ignore file will be deny-by-default for data and binary artifacts but will
not broadly ignore Python, Markdown, JSON, CSV, YAML, TOML, TeX, or shell source
files outside the excluded data directories.

## 4. Initial tracked scope

The first commit will contain only the following categories:

1. Repository instructions:
   - `.gitignore`
   - `AGENTS.md`
   - `CLAUDE.md`
2. Reproducibility metadata already present at the root:
   - `README.md` if created as a concise repository entry point;
   - `RUN_REPRODUCTION.md`;
   - `environment.yml`;
   - `requirements-lock.txt`;
   - `cohort_manifest.csv`;
   - `PNI관련연구.md`.
3. Approved planning and design documents under `docs/`.
4. PRECISE PNI research entry points:
   - `models/pilot_precise_pni_candidates.py`;
   - `models/build_precise_pni_review_html.py`;
   - `models/audit_precise_pni_frozen_scores.py`;
   - `models/pilot_precise_spatial_facevalidity.py`.
5. The focused audit tests under `tests/`.

No other top-level model repository, third-party model code, paper backup,
dataset, generated audit table, figure, or binary artifact will be staged in
the initial commit.

## 5. README scope

If the root has no README, create a concise `README.md` containing:

- repository purpose;
- current PRECISE frozen-score audit and morphology re-review stages;
- environment and test entry points;
- pointers to the approved design and result locations;
- a clear statement that pathology data and generated outputs are stored
  locally and are intentionally not tracked.

The README will not duplicate full methods or claim clinical validation.

## 6. Git initialization and commit

- Confirm the existing `.git` directory is empty and contains no recoverable
  repository metadata.
- Run `git init -b main` at the workspace root. The user has explicitly
  authorized repository initialization.
- Do not delete or reset any existing worktree content.
- Stage only the exact paths in Section 4.
- Inspect `git status --short`, staged file sizes, and `git diff --cached`
  before committing.
- Fail before commit if a dataset directory, WSI/array/weight file, secret-like
  filename, or unexpectedly large file is staged.
- Use the initial commit message:

  `chore: initialize reproducible PNI research repository`

- Record the resulting branch, commit hash, committed file count, and clean or
  residual untracked status.

## 7. Verification

Before the initial commit:

1. run the focused PRECISE audit unit tests;
2. syntax-check the tracked Python entry points;
3. verify `git check-ignore` excludes representative dataset, WSI, virtual
   environment, cache, and model-weight paths;
4. verify no staged file exceeds the agreed source/document scope;
5. search staged text files for common credential assignments without printing
   any discovered secret values;
6. review the complete staged name list and diff summary.

After the commit:

1. verify `git show --stat --oneline HEAD`;
2. verify the intended branch is `main`;
3. report any deliberately untracked source-like files without adding them;
4. do not configure a remote or push unless the user separately requests it.

## 8. Safety boundaries

- The clinician source review CSV remains immutable and untracked.
- Frozen candidate scores, prompts, exemplars, and score weights remain
  immutable and untracked as data inputs.
- Initializing Git does not authorize deleting, moving, compressing, or
  rewriting any local dataset.
- No Git LFS setup, remote creation, push, PR, or publication is included.
- No generated audit result is treated as source of truth merely because it is
  outside Git; provenance continues to be recorded through hashes and run
  configurations.
