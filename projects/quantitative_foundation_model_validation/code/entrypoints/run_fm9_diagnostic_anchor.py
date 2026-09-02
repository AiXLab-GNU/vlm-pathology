#!/usr/bin/env python3
"""Auditable FM9 entry point for the locked diagnostic-anchor path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LIB = ROOT / "projects/quantitative_foundation_model_validation/code/lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from fm9_anchor import build_preflight, write_json  # noqa: E402


DEFAULT_MODEL_REGISTRY = (
    ROOT
    / "projects/quantitative_foundation_model_validation/manifests/fm9_diagnostic_model_registry.yaml"
)
DEFAULT_COHORT_REGISTRY = (
    ROOT
    / "projects/quantitative_foundation_model_validation/manifests/prostate_diagnostic_cohort_portfolio.yaml"
)
DEFAULT_SOURCE_ROOT = (
    ROOT
    / "resources/projects/quantitative_foundation_model_validation/chimera_agent_biopsy_inference"
)
DEFAULT_OUTPUT = (
    ROOT
    / "resources/artifacts/quantitative_foundation_model_validation/"
    "fm9_prostate_diagnostic_anchor_and_discovery/anchor_preflight.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser(
        "preflight",
        help="audit the source, immutable model contract, and D0 gate without running predictions",
    )
    preflight.add_argument("--model-registry", type=Path, default=DEFAULT_MODEL_REGISTRY)
    preflight.add_argument("--cohort-registry", type=Path, default=DEFAULT_COHORT_REGISTRY)
    preflight.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    preflight.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    preflight.add_argument(
        "--require-ready",
        action="store_true",
        help="return exit code 2 when any readiness gate is not PASS",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "preflight":
        raise AssertionError(f"unhandled command: {args.command}")
    payload = build_preflight(
        registry_path=args.model_registry.resolve(),
        cohort_registry_path=args.cohort_registry.resolve(),
        source_root=args.source_root.resolve(),
    )
    write_json(payload, args.output.resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_ready and not payload["prediction_permitted"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
