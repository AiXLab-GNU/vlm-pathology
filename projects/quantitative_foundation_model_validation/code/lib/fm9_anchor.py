"""Integrity and readiness checks for the FM9 reproducible diagnostic anchor."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


REQUIRED_MODEL_ID = "chimera_hvit_biopsy_isup_off_the_shelf_weights_v1"
REQUIRED_DATASETS = ("DiagSet", "PBGG-1-2", "PRECISE")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a mapping in {path}")
    return payload


def select_model(registry: dict[str, Any], model_id: str = REQUIRED_MODEL_ID) -> dict[str, Any]:
    matches = [model for model in registry.get("models", []) if model.get("model_id") == model_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one model_id={model_id}, observed {len(matches)}")
    return matches[0]


def parse_sha256sums(path: Path) -> dict[str, str]:
    observed: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+(.+)", line)
        if match is None:
            raise ValueError(f"malformed SHA256SUMS line {line_number}: {raw_line!r}")
        digest, relative_path = match.groups()
        if relative_path in observed:
            raise ValueError(f"duplicate checksum path: {relative_path}")
        observed[relative_path] = digest
    return observed


def unpinned_requirements(path: Path) -> list[str]:
    unpinned: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        requirement = raw_line.split("#", 1)[0].strip()
        if not requirement or requirement.startswith(("-e ", "--hash=")):
            continue
        if "==" not in requirement:
            unpinned.append(requirement)
    return unpinned


def _git(source_root: Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(source_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def _check(check_id: str, status: str, expected: Any, observed: Any, detail: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }


def validate_model_contract(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if model.get("lane") != "diagnostic_anchor":
        errors.append("lane must be diagnostic_anchor")
    if model.get("mode") != "off_the_shelf_locked_inference":
        errors.append("mode must be off_the_shelf_locked_inference")
    if model.get("task") != "cancer_positive_biopsy_isup_0_to_5":
        errors.append("off-the-shelf task must remain cancer-positive biopsy ISUP grading")
    prohibited = set(model.get("prohibited_uses", []))
    for required in (
        "primary_binary_cancer_probability",
        "frozen_fm_feature_use_evidence",
        "panda_independent_external_validation",
        "target_cohort_model_selection",
    ):
        if required not in prohibited:
            errors.append(f"missing prohibited use: {required}")
    geometry = model.get("geometry", {})
    expected_geometry = {
        "spacing_microns_per_pixel": 0.5,
        "region_size_pixels": 2048,
        "patch_size_pixels": 256,
        "feature_dimension": 384,
    }
    if geometry != expected_geometry:
        errors.append(f"geometry differs from locked contract: {geometry!r}")
    ensemble = model.get("ensemble", {})
    if ensemble.get("folds") != 5 or ensemble.get("concatenated_latent_dimension") != 960:
        errors.append("ensemble must remain five folds with a 960-dimensional concatenated latent")
    weights = model.get("weight_sha256", {})
    if len(weights) != 10 or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in weights.values()):
        errors.append("exactly ten valid weight SHA-256 values are required")
    return errors


def audit_source(source_root: Path, model: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    checks: list[dict[str, Any]] = []
    file_hashes: dict[str, str] = {}
    if not source_root.is_dir():
        checks.append(_check("source_root", "BLOCKED", "existing directory", "missing", str(source_root)))
        return checks, file_hashes

    expected_commit = model["source"]["commit"]
    observed_commit = _git(source_root, "rev-parse", "HEAD")
    checks.append(
        _check(
            "source_commit",
            "PASS" if observed_commit == expected_commit else "FAIL",
            expected_commit,
            observed_commit,
            "The audited checkout must be the registry commit.",
        )
    )
    expected_url = model["source"]["repository_url"]
    observed_url = _git(source_root, "remote", "get-url", "origin")
    checks.append(
        _check(
            "source_remote",
            "PASS" if observed_url == expected_url else "FAIL",
            expected_url,
            observed_url,
            "The origin URL is evidence only; commit identity remains the immutable source lock.",
        )
    )

    required_files = (
        "Dockerfile",
        "README.md",
        "requirements.txt",
        "run.sh",
        "slide2vec-config.yaml",
        "aggregator/config/inference/panda-inference.yaml",
        model["source"]["checksum_manifest"],
    )
    missing = [relative for relative in required_files if not (source_root / relative).is_file()]
    for relative in required_files:
        path = source_root / relative
        if path.is_file():
            file_hashes[relative] = sha256_file(path)
    checks.append(
        _check(
            "required_source_files",
            "PASS" if not missing else "FAIL",
            list(required_files),
            missing,
            "Observed contains the missing-file list.",
        )
    )
    if missing:
        return checks, file_hashes

    expected_sums = model["weight_sha256"]
    observed_sums = parse_sha256sums(source_root / model["source"]["checksum_manifest"])
    checks.append(
        _check(
            "weight_checksum_contract",
            "PASS" if observed_sums == expected_sums else "FAIL",
            expected_sums,
            observed_sums,
            "This locks release checksums; it does not claim the weights are downloaded.",
        )
    )

    config = load_yaml(source_root / "slide2vec-config.yaml")
    observed_geometry = {
        "spacing_microns_per_pixel": config.get("tiling", {}).get("params", {}).get("spacing"),
        "region_size_pixels": config.get("tiling", {}).get("params", {}).get("tile_size"),
        "patch_size_pixels": config.get("model", {}).get("patch_size"),
    }
    expected_geometry = {
        key: model["geometry"][key]
        for key in ("spacing_microns_per_pixel", "region_size_pixels", "patch_size_pixels")
    }
    checks.append(
        _check(
            "input_geometry",
            "PASS" if observed_geometry == expected_geometry else "FAIL",
            expected_geometry,
            observed_geometry,
            "Model geometry cannot be tuned on PAR, PBGG, or another target cohort.",
        )
    )

    inference = load_yaml(source_root / "aggregator/config/inference/panda-inference.yaml")
    observed_ensemble = {
        "output_classes": list(range(inference.get("num_classes", -1))),
        "folds": len(expected_sums) // 2,
        "fold_latent_dimension": inference.get("model", {}).get("embed_dim_slide"),
    }
    expected_ensemble = {
        "output_classes": model["ensemble"]["output_classes"],
        "folds": model["ensemble"]["folds"],
        "fold_latent_dimension": model["ensemble"]["fold_latent_dimension"],
    }
    checks.append(
        _check(
            "ensemble_contract",
            "PASS" if observed_ensemble == expected_ensemble else "FAIL",
            expected_ensemble,
            observed_ensemble,
            "The off-the-shelf endpoint remains ISUP 0-5, not a dedicated cancer head.",
        )
    )

    license_files = sorted(
        path.name
        for path in source_root.iterdir()
        if path.is_file() and path.name.lower().startswith(("license", "copying"))
    )
    checks.append(
        _check(
            "license_evidence",
            "PASS" if license_files else "BLOCKED",
            "an explicit license or written permission",
            license_files,
            "Public readability alone does not establish permission to build or run the model.",
        )
    )

    dockerfile = (source_root / "Dockerfile").read_text(encoding="utf-8")
    from_match = re.search(r"^FROM\s+(\S+)", dockerfile, flags=re.MULTILINE)
    observed_base = from_match.group(1) if from_match else None
    digest = model["container"]["resolved_base_image_digest"]
    checks.append(
        _check(
            "base_image_digest_in_build_recipe",
            "PASS" if observed_base and "@sha256:" in observed_base else "BLOCKED",
            f"{model['container']['upstream_base_image']}@{digest}",
            observed_base,
            "Registry digest is resolved, but the upstream Dockerfile still uses a mutable tag.",
        )
    )

    unpinned = unpinned_requirements(source_root / "requirements.txt")
    checks.append(
        _check(
            "python_dependency_lock",
            "PASS" if not unpinned else "BLOCKED",
            [],
            unpinned,
            "Every installed dependency needs an exact version and artifact hash or a locked built image.",
        )
    )

    weight_states: dict[str, str] = {}
    for relative, expected_digest in expected_sums.items():
        path = source_root / relative
        if not path.is_file():
            weight_states[relative] = "missing"
        else:
            weight_states[relative] = "verified" if sha256_file(path) == expected_digest else "hash_mismatch"
    weight_status = "PASS" if weight_states and all(value == "verified" for value in weight_states.values()) else "BLOCKED"
    if any(value == "hash_mismatch" for value in weight_states.values()):
        weight_status = "FAIL"
    checks.append(
        _check(
            "weight_materialization",
            weight_status,
            "all ten release assets present with matching SHA-256",
            weight_states,
            "Weights are local-only and are not committed.",
        )
    )
    return checks, file_hashes


def audit_dataset_gate(cohort_registry: dict[str, Any]) -> dict[str, Any]:
    cohorts = {row.get("dataset_id"): row for row in cohort_registry.get("cohorts", [])}
    observed = {dataset: cohorts.get(dataset, {}).get("access_state", "missing") for dataset in REQUIRED_DATASETS}
    ready_tokens = ("acquired", "locked", "complete", "pass")
    not_ready = {
        dataset: state
        for dataset, state in observed.items()
        if not any(token in str(state).lower() for token in ready_tokens)
        or "not_acquired" in str(state).lower()
        or "failed" in str(state).lower()
    }
    return _check(
        "fm9_d0_dataset_gate",
        "PASS" if not not_ready else "BLOCKED",
        "DiagSet, PBGG-1/2, and paired-IHC PRECISE acquired with identity/hash locks",
        observed,
        "External predictions remain prohibited until D0 closes.",
    )


def build_preflight(
    *,
    registry_path: Path,
    cohort_registry_path: Path,
    source_root: Path,
) -> dict[str, Any]:
    registry = load_yaml(registry_path)
    model = select_model(registry)
    contract_errors = validate_model_contract(model)
    checks = [
        _check(
            "model_registry_contract",
            "PASS" if not contract_errors else "FAIL",
            [],
            contract_errors,
            "The model role, endpoint, geometry, and prohibited uses must remain locked.",
        )
    ]
    source_checks, file_hashes = audit_source(source_root, model)
    checks.extend(source_checks)
    checks.append(audit_dataset_gate(load_yaml(cohort_registry_path)))
    blockers = [row["check_id"] for row in checks if row["status"] != "PASS"]
    return {
        "schema_version": 1,
        "registry_id": registry["registry_id"],
        "model_id": model["model_id"],
        "run_mode": model["mode"],
        "readiness": "READY_FOR_LOCKED_INFERENCE" if not blockers else "NOT_READY",
        "prediction_permitted": not blockers,
        "blockers": blockers,
        "checks": checks,
        "audited_source_file_sha256": dict(sorted(file_hashes.items())),
        "claim_ceiling": "technical grading positive control; no cancer-primary, frozen-use, or clinical-grade claim",
    }


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
