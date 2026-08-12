#!/usr/bin/env python3
"""Validate the repository's project ownership and compatibility boundaries."""

from __future__ import annotations

import hashlib
import csv
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECTS = {
    "precise_pni_candidate_triage": ROOT / "projects/precise_pni_candidate_triage",
    "quantitative_foundation_model_validation": ROOT
    / "projects/quantitative_foundation_model_validation",
    "prostate_biomarker_validation": ROOT / "projects/prostate_biomarker_validation",
}
EXPECTED_PNI_SHA256 = "c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3"
PNI_SOURCE = ROOT / "resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv"
STRUCTURE_CODEX = ROOT / "infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md"
FILE_GOVERNANCE_CODEX = ROOT / "infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md"
FILE_NAMING_CODEX = ROOT / "infrastructure/docs/repository/FILE_NAMING_CODEX.md"
FILE_GOVERNANCE_AUDITOR = ROOT / "infrastructure/scripts/audit_file_governance.py"
ROOT_REGISTRY = ROOT / "infrastructure/docs/repository/ROOT_DIRECTORY_REGISTRY.csv"
RESOURCE_OWNERSHIP = ROOT / "resources/RESOURCE_OWNERSHIP.csv"
ALLOWED_TOP_LEVEL = {
    ".agents", ".claude", ".codex", ".git", ".gitignore", ".superpowers",
    ".venv", ".worktrees", "AGENTS.md", "CLAUDE.md", "LICENSE", "README.md",
    "environment.yml", "infrastructure", "projects", "requirements-lock.txt", "resources",
}
PROJECT_CHILDREN = {
    "precise_pni_candidate_triage": {
        "00-project-sequence", "AGENTS.md", "CLAIM_BOUNDARIES.md", "MILESTONES.md", "PROJECT.yaml", "README.md",
        "code", "docs", "manifests", "paper", "reports", "tests",
    },
    "quantitative_foundation_model_validation": {
        "00-project-sequence", "AGENTS.md", "CLAIM_BOUNDARIES.md", "MILESTONES.md", "PROJECT.yaml", "README.md",
        "code", "docs", "governance_portal", "manifests", "metric_registry", "milestones",
        "paper", "preexperiment", "reports", "tests",
    },
    "prostate_biomarker_validation": {
        "00-project-sequence", "AGENTS.md", "CLAIM_BOUNDARIES.md", "MILESTONES.md", "PROJECT.yaml", "README.md",
        "code", "docs", "manifests", "outputs", "paper", "reports", "tests",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def check_symlink(path: Path, expected: Path, failures: list[str]) -> None:
    check(path.is_symlink(), f"missing compatibility symlink: {path.relative_to(ROOT)}", failures)
    if path.is_symlink():
        check(
            path.resolve() == expected.resolve(),
            f"wrong symlink target: {path.relative_to(ROOT)} -> {path.resolve()}",
            failures,
        )


def main() -> int:
    failures: list[str] = []

    check(STRUCTURE_CODEX.is_file(), "missing Project Structure Codex", failures)
    check(FILE_GOVERNANCE_CODEX.is_file(), "missing File Governance Codex", failures)
    check(FILE_NAMING_CODEX.is_file(), "missing File Naming Codex", failures)
    check(FILE_GOVERNANCE_AUDITOR.is_file(), "missing file-governance auditor", failures)
    check(ROOT_REGISTRY.is_file(), "missing root directory registry", failures)
    check(RESOURCE_OWNERSHIP.is_file(), "missing resource ownership registry", failures)
    for instruction in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md", *(path / "AGENTS.md" for path in PROJECTS.values())):
        check(instruction.is_file(), f"missing instruction file: {instruction}", failures)
        if instruction.is_file():
            check(
                "PROJECT_STRUCTURE_CODEX.md" in instruction.read_text(encoding="utf-8"),
                f"instruction does not require Project Structure Codex: {instruction.relative_to(ROOT)}",
                failures,
            )
            check(
                "FILE_GOVERNANCE_CODEX.md" in instruction.read_text(encoding="utf-8"),
                f"instruction does not require File Governance Codex: {instruction.relative_to(ROOT)}",
                failures,
            )
            check(
                "FILE_NAMING_CODEX.md" in instruction.read_text(encoding="utf-8"),
                f"instruction does not require File Naming Codex: {instruction.relative_to(ROOT)}",
                failures,
            )

    actual_top_level = {path.name for path in ROOT.iterdir()}
    for unexpected in sorted(actual_top_level - ALLOWED_TOP_LEVEL):
        failures.append(f"unregistered top-level entry: {unexpected}")
    for missing in sorted(ALLOWED_TOP_LEVEL - actual_top_level):
        failures.append(f"missing required top-level entry: {missing}")
    if ROOT_REGISTRY.is_file():
        with ROOT_REGISTRY.open(encoding="utf-8", newline="") as handle:
            registry_rows = list(csv.DictReader(handle))
        registered = {row.get("root_entry", "") for row in registry_rows}
        check(
            registered == ALLOWED_TOP_LEVEL,
            "root registry entries do not exactly match the root contract",
            failures,
        )
        check(
            len(registry_rows) == len(registered),
            "root registry has duplicate entries",
            failures,
        )

    for name, project in PROJECTS.items():
        for required in ("README.md", "AGENTS.md", "PROJECT.yaml", "CLAIM_BOUNDARIES.md", "MILESTONES.md"):
            check((project / required).is_file(), f"{name}: missing {required}", failures)
        for required_dir in ("code", "docs", "tests", "paper", "manifests", "reports"):
            check((project / required_dir).is_dir(), f"{name}: missing {required_dir}/", failures)
        check(
            (project / "00-project-sequence/README.md").is_file(),
            f"{name}: missing 00-project-sequence/README.md",
            failures,
        )
        actual_children = {path.name for path in project.iterdir()}
        for unexpected in sorted(actual_children - PROJECT_CHILDREN[name]):
            failures.append(f"{name}: unregistered project-root entry: {unexpected}")

    superpowers_patterns = {
        "specs": re.compile(r"^\d{4}-\d{2}-\d{2}-repository-[a-z0-9-]+-design\.md$"),
        "plans": re.compile(r"^\d{4}-\d{2}-\d{2}-repository-[a-z0-9-]+-plan\.md$"),
    }
    for category, pattern in superpowers_patterns.items():
        directory = ROOT / "infrastructure/docs/superpowers" / category
        check(directory.is_dir(), f"missing infrastructure/docs/superpowers/{category}/", failures)
        if directory.is_dir():
            for path in directory.iterdir():
                if not path.is_file():
                    failures.append(f"unexpected Superpowers entry: {path.relative_to(ROOT)}")
                    continue
                check(bool(pattern.fullmatch(path.name)), f"noncanonical Superpowers filename: {path.relative_to(ROOT)}", failures)
                text = path.read_text(encoding="utf-8", errors="replace")
                check(text.startswith("---\n"), f"Superpowers metadata header missing: {path.relative_to(ROOT)}", failures)
                check("owner_project: repository" in text, f"Superpowers owner missing: {path.relative_to(ROOT)}", failures)

    runtime_superpowers = ROOT / ".superpowers"
    if runtime_superpowers.is_dir():
        forbidden_suffixes = {".csv", ".diff", ".md", ".pdf", ".py", ".tex", ".tsv"}
        for path in runtime_superpowers.rglob("*"):
            if path.is_file() and path.suffix.lower() in forbidden_suffixes:
                failures.append(
                    f"final/research document is not allowed in Superpowers runtime state: "
                    f"{path.relative_to(ROOT)}"
                )

    if RESOURCE_OWNERSHIP.is_file():
        with RESOURCE_OWNERSHIP.open(encoding="utf-8", newline="") as handle:
            resource_rows = list(csv.DictReader(handle))
        required_fields = {
            "resource_path", "resource_class", "owner_project", "git_policy", "provenance"
        }
        check(
            set(resource_rows[0]) == required_fields if resource_rows else False,
            "invalid resource ownership registry schema",
            failures,
        )
        for row in resource_rows:
            resource_path = row.get("resource_path", "")
            check(
                bool(resource_path) and (ROOT / resource_path).exists(),
                f"registered resource path is missing: {resource_path}",
                failures,
            )

    worktree_readme = ROOT / ".worktrees/README.md"
    worktree_registry = ROOT / ".worktrees/registry.csv"
    check(worktree_readme.is_file(), "missing .worktrees/README.md", failures)
    check(worktree_registry.is_file(), "missing .worktrees/registry.csv", failures)
    if worktree_registry.is_file():
        expected_header = "project_id,purpose_slug,relative_path,branch,owner,created,status,disposition"
        first_line = worktree_registry.read_text(encoding="utf-8").splitlines()[0]
        check(first_line == expected_header, "invalid .worktrees/registry.csv schema", failures)

    worktree_audit = subprocess.run(
        [sys.executable, str(ROOT / "infrastructure/scripts/audit_worktrees.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check(
        worktree_audit.returncode == 0,
        f"worktree audit failed: {worktree_audit.stdout.strip() or worktree_audit.stderr.strip()}",
        failures,
    )

    file_governance_audit = subprocess.run(
        [sys.executable, str(FILE_GOVERNANCE_AUDITOR)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check(
        file_governance_audit.returncode == 0,
        "file-governance audit failed: "
        f"{file_governance_audit.stdout.strip() or file_governance_audit.stderr.strip()}",
        failures,
    )

    removed_legacy_roots = (
        "models", "paper", "studies", "artifacts", "data", "docs", "packages", "scripts",
        "shared", "reorganization", "local-data", "model-weights", "opendataset",
        "song-datasets",
    )
    for removed_legacy_root in removed_legacy_roots:
        path = ROOT / removed_legacy_root
        check(
            not path.exists() and not path.is_symlink(),
            f"legacy root entry must be removed: {removed_legacy_root}",
            failures,
        )

    check(PNI_SOURCE.is_file(), f"missing immutable source: {PNI_SOURCE}", failures)
    if PNI_SOURCE.is_file():
        check(
            sha256(PNI_SOURCE) == EXPECTED_PNI_SHA256,
            "immutable PNI clinician source SHA-256 mismatch",
            failures,
        )

    cross_project_tokens = {
        "precise_pni_candidate_triage": (
            "projects.quantitative_foundation_model_validation",
            "projects.prostate_biomarker_validation",
        ),
        "quantitative_foundation_model_validation": (
            "projects.precise_pni_candidate_triage",
            "projects.prostate_biomarker_validation",
        ),
        "prostate_biomarker_validation": (
            "projects.precise_pni_candidate_triage",
            "projects.quantitative_foundation_model_validation",
        ),
    }
    for project_name, tokens in cross_project_tokens.items():
        for path in (PROJECTS[project_name] / "code").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in tokens:
                check(token not in text, f"cross-project Python import in {path}: {token}", failures)

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "projects": sorted(PROJECTS),
        "project_structure_codex_sha256": sha256(STRUCTURE_CODEX) if STRUCTURE_CODEX.is_file() else None,
        "file_naming_codex_sha256": (
            sha256(FILE_NAMING_CODEX) if FILE_NAMING_CODEX.is_file() else None
        ),
        "worktree_audit_status": "PASS" if worktree_audit.returncode == 0 else "FAIL",
        "file_governance_audit_status": (
            "PASS" if file_governance_audit.returncode == 0 else "FAIL"
        ),
        "immutable_pni_source_sha256": sha256(PNI_SOURCE) if PNI_SOURCE.is_file() else None,
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
