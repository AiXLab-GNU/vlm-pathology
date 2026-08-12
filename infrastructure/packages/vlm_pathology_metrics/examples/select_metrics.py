"""Minimal disease-first selection example."""

from vlm_pathology_metrics import disease_uses, recommend_combinations


def main() -> None:
    disease_id = "prostate_pni"
    print("USES")
    for use in disease_uses(disease_id=disease_id):
        print(use.use_id, use.clinical_role, use.package_readiness)
        print("  medical:", ", ".join(use.medical_metric_ids) or "(none)")
        print("  analysis:", ", ".join(use.analysis_measure_ids) or "(none)")

    print("COMBINATIONS")
    for combination in recommend_combinations(disease_id):
        print(combination.combination_id, combination.combination_name_ko)
        print("  medical:", ", ".join(combination.medical_metric_ids) or "(none)")
        print("  analysis:", ", ".join(combination.analysis_measure_ids) or "(none)")


if __name__ == "__main__":
    main()
