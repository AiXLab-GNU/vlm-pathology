# VLM Pathology Research Workspace

This repository contains reproducible pathology vision-language-model research
code and study documentation. The current primary work concerns perineural
invasion (PNI) candidate triage in PRECISE prostate cancer slides.

The frozen CONCH workflow ranks spatially distinct candidate regions for
pathologist review. It is not a clinically validated whole-slide PNI diagnostic
system. The completed 120-candidate audit and the planned 14-focus morphology
re-review are method-development studies with deliberately limited claims.

## Current study documents

- [Frozen-score audit design](docs/superpowers/specs/2026-08-05-precise-pni-frozen-score-audit-design.md)
- [Frozen-score audit implementation plan](docs/superpowers/plans/2026-08-05-precise-pni-frozen-score-audit.md)
- [PNI morphology re-review design](docs/superpowers/specs/2026-08-06-precise-pni-morphology-rereview-design.md)
- [Reproduction guide](RUN_REPRODUCTION.md)

## Environment and verification

Use the existing workspace Python environment:

```bash
.venv/bin/python -m unittest tests.test_precise_pni_frozen_score_audit -v
```

Regenerate the frozen-score audit locally with:

```bash
.venv/bin/python models/audit_precise_pni_frozen_scores.py
```

## Data policy

Pathology images, dataset mirrors, model weights, virtual environments, caches,
and generated analysis outputs are stored locally and intentionally excluded
from Git. Reproducibility is established through fixed entry points, manifests,
hashes, run configurations, tests, and approved study designs rather than by
committing large or derived data artifacts.

See [AGENTS.md](AGENTS.md) for the complete scientific, reproducibility, and Git
safety policy. Claude Code sessions should also read [CLAUDE.md](CLAUDE.md).

## License

Repository-authored software and documentation are released under the
[MIT License](LICENSE). This license does not apply to third-party datasets,
whole-slide images, pretrained model weights, or other externally governed
assets; those remain subject to their original providers' terms.
