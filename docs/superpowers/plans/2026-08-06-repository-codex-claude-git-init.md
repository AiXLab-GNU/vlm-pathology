# Repository Codex, Claude, and Git Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize a safe `main`-branch Git repository with Codex/Claude project instructions and one audited source-and-documentation-only initial commit.

**Architecture:** Root instruction files share one research policy, while `.gitignore` blocks datasets, WSI, weights, environments, caches, and generated binary artifacts. Git staging uses an explicit path allowlist rather than recursive addition; pre-commit checks inspect names, sizes, ignore behavior, text credential patterns, tests, and syntax before creating the commit.

**Tech Stack:** Git; Markdown; `.gitignore`; Bash read-only audit commands; Python 3.11 `unittest` and `py_compile`.

## Global Constraints

- Initialize only `/home/jinhyun/prj_ws/prj_jin/vlm-pathology`; do not create a nested repository.
- The user explicitly authorized `git init`, but did not authorize remote creation, push, Git LFS, deletion, movement, or rewriting of data.
- Track only root instructions/reproducibility metadata, `docs/`, four PRECISE PNI Python entry points, and focused tests.
- Never stage `opendataset/`, `song-datasets/`, WSI/array/weight files, environments, caches, generated audit outputs, external model repositories, or paper backups.
- Preserve the clinician source review and all frozen candidate inputs byte-for-byte.
- Use branch `main` and commit message `chore: initialize reproducible PNI research repository`.
- Do not use `git add .` or `git add -A`; stage an exact allowlist.

---

### Task 1: Create Repository Policy and Entry-Point Documents

**Files:**
- Create: `.gitignore`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `README.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-06-repository-codex-claude-git-init-design.md` and the existing audit/morphology designs.
- Produces: root policies understood independently by Codex, Claude Code, Git, and human contributors.

- [ ] **Step 1: Verify the root policy files are absent**

  Run: `for f in .gitignore AGENTS.md CLAUDE.md README.md; do test ! -e "$f" || { echo "unexpected existing file: $f"; exit 1; }; done`

  Expected: exit 0 with no output, proving no user file will be overwritten.

- [ ] **Step 2: Create `.gitignore` with explicit data and artifact exclusions**

  Include these exact policy groups:

  ```gitignore
  opendataset/
  song-datasets/
  .venv/
  models/.venv-*/
  **/__pycache__/
  .pytest_cache/
  .mypy_cache/
  .ruff_cache/
  .ipynb_checkpoints/
  .codex/
  .agents/
  .claude/
  **/.cache/
  *.svs
  *.tif
  *.tiff
  *.ome.tif
  *.ome.tiff
  *.zarr/
  *.npy
  *.npz
  *.h5
  *.hdf5
  *.pt
  *.pth
  *.ckpt
  *.safetensors
  *.bin
  paper/*.aux
  paper/*.log
  paper/*.out
  paper/*.pdf
  .DS_Store
  *~
  ```

  Do not ignore root `AGENTS.md`, `CLAUDE.md`, source files, or `docs/`.

- [ ] **Step 3: Create `AGENTS.md` as the shared Codex policy**

  Include project scope, approved design precedence, immutable clinician/frozen-score inputs, no missing-to-negative imputation, exact NMS reproduction, triage-not-diagnosis language, deterministic hashing/rerun requirements, `.venv/bin/python` commands, focused test command, and Git data-exclusion rules.

- [ ] **Step 4: Create `CLAUDE.md` as a standalone Claude Code policy**

  Start with `Read AGENTS.md completely before work.` Repeat the immutable-data, approved-design, blinded-review, prohibited-claim, verification, and no-large-data-commit rules so a standalone Claude session cannot miss them.

- [ ] **Step 5: Create a concise `README.md`**

  Describe the candidate-triage scope; link the frozen-score audit design, morphology re-review design, and reproduction instructions; provide these commands:

  ```bash
  .venv/bin/python -m unittest tests.test_precise_pni_frozen_score_audit -v
  .venv/bin/python models/audit_precise_pni_frozen_scores.py
  ```

  State that pathology data and generated results are intentionally local and Git-ignored.

- [ ] **Step 6: Validate policy coverage and absence of placeholders**

  Run `rg` checks proving all four files exist, no unfinished placeholder marker exists, and `AGENTS.md`/`CLAUDE.md` contain `immutable`, `missing`, `triage`, `hash`, `test`, and `opendataset` concepts.

### Task 2: Initialize Git and Audit the Exact Staging Set

**Files:**
- Create metadata: `.git/`
- Stage only the exact allowlist below.

**Interfaces:**
- Consumes: Task 1 files plus existing approved source/docs.
- Produces: an initialized `main` branch and a fully inspected Git index, but no commit until every guard passes.

- [ ] **Step 1: Prove the existing `.git` directory is empty**

  Run a read-only directory listing and require zero entries other than `.` and `..`. If any Git object, config, index, or ref exists, stop without initialization.

- [ ] **Step 2: Initialize the repository**

  Run: `git init -b main`

  Expected: a valid repository whose `git branch --show-current` output is `main`.

- [ ] **Step 3: Verify ignore behavior with representative paths**

  Run `git check-ignore -v` for an existing `opendataset` file, an existing `.venv` file, an existing cache file, an existing `.npz`, and a synthetic weight pathname supplied with `--no-index`. Require every representative path to be ignored.

- [ ] **Step 4: Stage the exact allowlist**

  Run one non-recursive allowlist command containing only:

  ```text
  .gitignore
  AGENTS.md
  CLAUDE.md
  README.md
  RUN_REPRODUCTION.md
  environment.yml
  requirements-lock.txt
  cohort_manifest.csv
  PNI관련연구.md
  docs/
  models/pilot_precise_pni_candidates.py
  models/build_precise_pni_review_html.py
  models/audit_precise_pni_frozen_scores.py
  models/pilot_precise_spatial_facevalidity.py
  tests/test_precise_pni_frozen_score_audit.py
  ```

- [ ] **Step 5: Audit staged names, extensions, and sizes**

  Require that no staged path begins with `opendataset/`, `song-datasets/`, `.venv/`, `paper_backup`, or a nested model repository. Reject staged `.svs`, TIFF, Zarr, NPY/NPZ, HDF5, weight, cache, PDF, or bytecode files. Report every staged file above 1 MiB and verify it is the explicitly approved `cohort_manifest.csv`; reject any staged file above 5 MiB.

- [ ] **Step 6: Audit staged text for secret-like assignments**

  Search the staged blobs—not the worktree at large—for common token/key/password assignment patterns. Print only affected filenames and pattern categories, never matched values. Stop before commit if a credential-like assignment is found outside documented placeholders.

- [ ] **Step 7: Inspect the staged diff**

  Run: `git diff --cached --check`, `git diff --cached --stat`, and `git status --short`. Confirm the staged list equals the approved allowlist expansion and all other workspace content is either ignored or untracked.

### Task 3: Verify Research Code and Create the Initial Commit

**Files:**
- Commit: the audited staged files from Task 2.

**Interfaces:**
- Consumes: valid `main` repository and clean staged allowlist.
- Produces: one initial commit and an evidence-backed repository handoff.

- [ ] **Step 1: Run focused tests fresh**

  Run: `.venv/bin/python -m unittest tests.test_precise_pni_frozen_score_audit -v`

  Expected: 13 tests, zero failures.

- [ ] **Step 2: Syntax-check every staged Python file**

  Run `.venv/bin/python -m py_compile` on the four staged model scripts and focused test file.

  Expected: exit 0.

- [ ] **Step 3: Reconfirm immutable clinician-source SHA256**

  Run: `sha256sum 'opendataset/PRECISE/precise_pni_review (1).csv'`

  Expected: `c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3`.

- [ ] **Step 4: Create the initial commit**

  Run: `git commit -m "chore: initialize reproducible PNI research repository"`

  Do not alter global or local Git identity automatically. If author identity is missing, stop and report the exact blocker for user direction.

- [ ] **Step 5: Verify the committed repository**

  Run: `git branch --show-current`, `git log -1 --oneline`, `git show --stat --oneline --summary HEAD`, and `git status --short`.

  Confirm the branch is `main`, the commit contains only the audited allowlist, no ignored data are tracked, and any residual entries are reported without staging them.

- [ ] **Step 6: Report completion without remote mutation**

  Report the commit hash, file count, tests, clinician-source hash, deliberately ignored data categories, and residual untracked paths. Do not create a remote or push.
