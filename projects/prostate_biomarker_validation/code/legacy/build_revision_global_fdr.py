"""Build the protocol-frozen BH family: 13 marker tests plus four refit audits."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bh_fdr(p_values):
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0, 1)
    return result


def main():
    marker = pd.read_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv"))
    marker_rows = pd.DataFrame({
        "family_member_type": "marker_hypothesis",
        "test": marker["test"],
        "effect_metric": marker["task"].map({"binary": "AUROC", "continuous": "Spearman_rho"}),
        "effect": marker["patient_metric"],
        "p_value": marker["patient_p"],
        "encoder": marker["encoder"],
        "validation_type": marker["validation_type"],
        "reliability_tier": marker["reliability_tier"],
    })
    audit = pd.read_csv(os.path.join(
        ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/confounder_refit_permutation_final2000_summary.csv"))
    audit_rows = pd.DataFrame({
        "family_member_type": "nested_refit_confounder_audit",
        "test": audit["marker"] + " / " + audit["analysis"],
        "effect_metric": audit["metric"],
        "effect": audit["observed_delta"],
        "p_value": audit["permutation_p_one_sided"],
        "encoder": "CONCH",
        "validation_type": "nested patient-disjoint CV + fully refit permutation",
        "reliability_tier": "Not independently tiered",
    })
    family = pd.concat([marker_rows, audit_rows], ignore_index=True)
    family["q_value_BH_FDR_17_tests"] = bh_fdr(family["p_value"])
    family.to_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/revision_global_fdr_summary.csv"), index=False)
    marker["patient_q_BH_FDR_17_tests"] = family.loc[
        family["family_member_type"] == "marker_hypothesis",
        "q_value_BH_FDR_17_tests"].to_numpy()
    marker.to_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv"), index=False)
    print(family.to_string(index=False))


if __name__ == "__main__":
    main()
