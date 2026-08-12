# Quantitative validation code

Reusable code extracted from milestone entry points belongs here. For auditability, the
current executable entry points remain beside their frozen P0 and FM1–FM4 protocols.

- New shared project modules use lower-snake-case names in this directory.
- Milestone-local entry points remain with their protocol bundle when the path is part of
  the frozen run contract.
- New entry points use a clear verb prefix such as `run_`, `build_`, or `validate_`.
- Reusable repository code moves to `infrastructure/packages/` only after its scientific
  contract is identical across projects and covered by tests.
