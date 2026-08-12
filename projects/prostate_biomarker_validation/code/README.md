# Prostate biomarker-validation code map

- `active/`: maintained analysis entry points and shared project modules.
- `legacy/`: provenance-preserved historical scripts. Do not add new analyses here.

New work should use one auditable lower-snake-case entry point in `active/`, with tests
under `../tests/`. A legacy script may be wrapped or extracted into tested active code;
its original path must remain unchanged when an existing result cites it.
