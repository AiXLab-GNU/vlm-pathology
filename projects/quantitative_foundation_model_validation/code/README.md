# Quantitative validation code

Reusable code extracted from milestone entry points belongs here. For auditability, the
current executable entry points remain beside their frozen P0 and FM1–FM4 protocols.

- New shared project modules use lower-snake-case names in this directory.
- Milestone-local entry points remain with their protocol bundle when the path is part of
  the frozen run contract.
- New entry points use a clear verb prefix such as `run_`, `build_`, or `validate_`.
- Reusable repository code moves to `infrastructure/packages/` only after its scientific
  contract is identical across projects and covered by tests.

## Active FM8/FM9 entry points

- `entrypoints/run_fm8_bcr_tier4_discovery.py`: one auditable `audit`, `run`, and
  `compare-clean-rerun` CLI for the TCGA-PRAD to CHIMERA whole-tissue BCR Tier 4 lane.
- `lib/fm8_tier4.py`: tested patient-level leakage control, nested source-only model selection,
  bootstrap, and candidate-role functions. It contains no endpoint-lane label mapping.
- `../milestones/fm8_grading_criterion_qualification/audit_fm8_grading_criterion_qualification.py`:
  milestone-local, read-only PANDA/SICAP/PAR/CHIMERA source and grading-entry audit. It does not fit
  a grading head or open residual analysis.
- `../milestones/fm8_grading_criterion_qualification/acquire_fm8_par_source.py`: resumable,
  primary-Hamamatsu-only PAR remote inventory, acquisition, size audit, and optional SHA-256 entry
  point; patient-level inventory and WSI remain in the local QFM data root.
- `../milestones/fm8_grading_criterion_qualification/run_fm8_grading_criterion_qualification.py`:
  outcome-blind PANDA/PAR tile preparation, paired frozen CONCH/Virchow extraction, locked
  PANDA-only ordinal MIL-head training, and no-tuning SICAP/PAR grading evaluation. Large arrays,
  checkpoints and per-slide caches are written only to the local QFM artifact root.
- `entrypoints/run_fm9_diagnostic_anchor.py`: CHIMERA-HViT source commit, weight-checksum
  contract, geometry/output, license/build/dependency/weight state와 D0 data gate를 prediction 없이
  감사하는 fail-closed FM9 entry point.
- `lib/fm9_anchor.py`: deterministic model-registry validation, source/hash audit와 readiness
  판정 함수. Off-the-shelf grading anchor를 cancer-primary 또는 frozen-feature-use 근거로
  재해석하지 못하게 한다.
