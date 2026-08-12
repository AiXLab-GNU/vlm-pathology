"""Command-line access to the quantitative metric registry."""

from __future__ import annotations

import argparse
from collections import Counter

from .catalog import (
    ANALYSIS_CATALOG,
    CATALOG,
    VALID_STATUSES,
    VALID_TIERS,
    analysis_catalog,
    catalog,
    export_analysis_catalog,
    export_catalog,
)
from .survey import (
    VALID_READINESS,
    disease_uses,
    diseases,
    export_survey,
    metric_disease_scope,
    recommend_combinations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="vlm-pathology-metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="List tiered medical metrics")
    list_parser.add_argument("--domain")
    list_parser.add_argument("--status", choices=sorted(VALID_STATUSES))
    list_parser.add_argument("--tier", choices=sorted(VALID_TIERS))
    analysis_parser = subparsers.add_parser(
        "analysis-list", help="List non-medical evaluation/statistics/QC measures"
    )
    analysis_parser.add_argument("--domain")
    analysis_parser.add_argument("--status", choices=sorted(VALID_STATUSES))
    export_parser = subparsers.add_parser("export", help="Export tiered medical metrics")
    export_parser.add_argument("--format", choices=["csv", "markdown"], default="csv")
    export_parser.add_argument("--output", required=True)
    analysis_export = subparsers.add_parser(
        "export-analysis", help="Export evaluation/statistics/QC measures"
    )
    analysis_export.add_argument("--format", choices=["csv", "markdown"], default="csv")
    analysis_export.add_argument("--output", required=True)
    subparsers.add_parser("summary", help="Show counts by domain and status")
    subparsers.add_parser("diseases", help="List disease/use IDs in the survey catalog")

    uses_parser = subparsers.add_parser("uses", help="List metric uses for one disease")
    uses_parser.add_argument("--disease", required=True)
    uses_parser.add_argument("--readiness", choices=sorted(VALID_READINESS))

    metric_parser = subparsers.add_parser(
        "metric-scope", help="Explain the disease scope of one metric"
    )
    metric_parser.add_argument("metric_id")

    recommend_parser = subparsers.add_parser(
        "recommend", help="List curated metric combinations for one disease/use"
    )
    recommend_parser.add_argument("--disease", required=True)
    recommend_parser.add_argument("--readiness", choices=sorted(VALID_READINESS))

    survey_parser = subparsers.add_parser(
        "export-survey", help="Export normalized survey catalog CSV files"
    )
    survey_parser.add_argument("--directory", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "list":
        for item in catalog(domain=args.domain, status=args.status, tier=args.tier):
            print(
                f"{item.metric_id}\t{item.tier}\t{item.domain}\t{item.status}\t"
                f"{item.name_ko}\t{item.name_en}"
            )
    elif args.command == "analysis-list":
        for item in analysis_catalog(domain=args.domain, status=args.status):
            print(f"{item.metric_id}\t{item.domain}\t{item.status}\t{item.name_ko}\t{item.name_en}")
    elif args.command == "export":
        print(export_catalog(args.output, format=args.format))
    elif args.command == "export-analysis":
        print(export_analysis_catalog(args.output, format=args.format))
    elif args.command == "summary":
        print(f"medical_total\t{len(CATALOG)}")
        print(f"analysis_total\t{len(ANALYSIS_CATALOG)}")
        for tier, count in sorted(Counter(item.tier for item in CATALOG).items()):
            print(f"tier:{tier}\t{count}")
        for domain, count in sorted(Counter(item.domain for item in CATALOG).items()):
            print(f"medical_domain:{domain}\t{count}")
        for status, count in sorted(Counter(item.status for item in CATALOG).items()):
            print(f"medical_status:{status}\t{count}")
    elif args.command == "diseases":
        for disease_id, name_ko, name_en in diseases():
            print(f"{disease_id}\t{name_ko}\t{name_en}")
    elif args.command == "uses":
        for item in disease_uses(disease_id=args.disease, readiness=args.readiness):
            print(
                f"{item.use_id}\t{item.clinical_role}\t{item.package_readiness}\t"
                f"medical={';'.join(item.medical_metric_ids)}\t"
                f"analysis={';'.join(item.analysis_measure_ids)}\t{item.summary_ko}"
            )
    elif args.command == "metric-scope":
        item = metric_disease_scope(args.metric_id)
        print(
            f"{item.metric_id}\t{item.applicability_class}\t"
            f"{';'.join(item.disease_ids)}\t{';'.join(item.clinical_roles)}\t"
            f"diagnostic_adjuvant={item.diagnostic_adjuvant_mapping}\t"
            f"standalone_diagnostic={item.standalone_diagnostic_use}\t{item.summary_ko}"
        )
    elif args.command == "recommend":
        for item in recommend_combinations(args.disease, readiness=args.readiness):
            print(
                f"{item.combination_id}\t{item.package_readiness}\t"
                f"{item.combination_name_ko}\tmedical={';'.join(item.medical_metric_ids)}\t"
                f"analysis={';'.join(item.analysis_measure_ids)}"
            )
    elif args.command == "export-survey":
        for path in export_survey(args.directory):
            print(path)


if __name__ == "__main__":
    main()
