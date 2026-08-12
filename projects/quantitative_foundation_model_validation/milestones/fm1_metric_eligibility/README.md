# FM1 metric eligibility audit

Run from the repository root:

```bash
.venv/bin/python projects/quantitative_foundation_model_validation/milestones/fm1_metric_eligibility/run_fm1.py
```

The deterministic registry outputs are written to `outputs/`. FM1 classifies
medical metrics, preserves the separate analysis-measure boundary, audits the
initial H2 metric–endpoint pairs, and registers study-local molecular reference
candidates. It does not execute H2 or make model-performance claims.
