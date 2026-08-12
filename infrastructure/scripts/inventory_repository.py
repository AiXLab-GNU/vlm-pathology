#!/usr/bin/env python3
"""Inventory project-owned files before/after repository reorganization."""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "infrastructure/migrations/2026-08-12-project-separation"
EXCLUDED_DIRS = {
    ".git", ".venv", ".agents", ".claude", ".codex", ".superpowers",
    "__pycache__", "opendataset", "song-datasets", "local-data", "model-weights",
    "model_workspace", "workflow_history", "archives",
    "2026-08-12-project-separation",
}
MANAGED_ROOTS = (".worktrees", "infrastructure", "projects", "resources")
ROOT_FILES = {
    ".gitignore", "AGENTS.md", "CLAUDE.md", "LICENSE", "README.md",
    "environment.yml", "requirements-lock.txt",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def git_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return set(result.stdout.splitlines())


def classify(relative: str) -> tuple[str, str, str]:
    name = Path(relative).name.lower()
    lower = relative.lower()
    if relative.startswith("projects/"):
        project = relative.split("/", 2)[1]
        return project, relative, "already_reorganized"
    if "quantitative" in lower or "foundation_model_quantitative" in lower or any(
        token in name for token in ("quantitativ_ai", "medical_quantitative_metric")
    ):
        return "quantitative_foundation_model_validation", f"projects/quantitative_foundation_model_validation/docs/legacy/{Path(relative).name}", "move"
    if any(token in lower for token in ("precise_pni", "pni관련", "pni_contour")):
        bucket = "tests" if relative.startswith("tests/") else "code" if relative.startswith("resources/projects/prostate_biomarker_validation/model_workspace/") else "docs/legacy"
        return "precise_pni_candidate_triage", f"projects/precise_pni_candidate_triage/{bucket}/{Path(relative).name}", "move"
    if relative.startswith("resources/projects/prostate_biomarker_validation/model_workspace/") and "/" not in relative[7:]:
        bucket = "code/legacy" if relative.endswith((".py", ".sh")) else "outputs/legacy"
        return "prostate_biomarker_validation", f"projects/prostate_biomarker_validation/{bucket}/{Path(relative).name}", "move"
    if relative.startswith("resources/projects/prostate_biomarker_validation/model_workspace/"):
        return "LOCAL_MODEL_ASSET", relative.replace("resources/projects/prostate_biomarker_validation/model_workspace/", "resources/projects/prostate_biomarker_validation/model_workspace/", 1), "retain_or_link"
    if relative.startswith("infrastructure/packages/"):
        return "SHARED_PACKAGE", relative, "retain"
    if relative == "infrastructure/README.md":
        return "REPOSITORY_OPERATIONS", relative, "retain"
    if relative.startswith("infrastructure/scripts/"):
        return "REPOSITORY_OPERATIONS", relative, "retain"
    if relative.startswith("infrastructure/tests/"):
        return "REPOSITORY_INTEGRATION", relative, "retain"
    if relative.startswith("infrastructure/shared/") or relative.startswith("resources/"):
        return "SHARED_REGISTRY", relative, "retain"
    if relative.startswith(".worktrees/") or relative.startswith("infrastructure/docs/repository/"):
        return "REPOSITORY_GOVERNANCE", relative, "retain"
    if relative.startswith("infrastructure/docs/superpowers/"):
        return "REPOSITORY_GOVERNANCE", relative, "retain"
    if relative.startswith("infrastructure/docs/"):
        return "prostate_biomarker_validation", f"projects/prostate_biomarker_validation/docs/legacy/{Path(relative).name}", "move"
    if relative in {"AGENTS.md", "README.md", ".gitignore", "LICENSE", "environment.yml", "requirements-lock.txt", "CLAUDE.md"}:
        return "REPOSITORY_ROOT", relative, "retain"
    return "UNRESOLVED", relative, "review"


def iter_files():
    for item in sorted(ROOT.iterdir(), key=lambda path: path.name):
        if item.name in EXCLUDED_DIRS or item.name == "reorganization":
            continue
        if item.is_file() or item.is_symlink():
            if item.name in ROOT_FILES:
                yield item
            continue
        if item.name not in MANAGED_ROOTS:
            continue
        for base, dirs, files in os.walk(item):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".venv"))
            for filename in sorted(files):
                path = Path(base) / filename
                if path.is_file():
                    yield path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tracked = git_paths()
    rows = []
    classifications = []
    for path in iter_files():
        relative = path.relative_to(ROOT).as_posix()
        project, proposed, action = classify(relative)
        row = {
            "current_path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
            "git_tracked": relative in tracked,
            "project": project,
            "proposed_path": proposed,
            "action": action,
        }
        rows.append(row)
        classifications.append({key: row[key] for key in ("current_path", "project", "proposed_path", "action")})
    for filename, values in (
        ("current_file_inventory.csv", rows),
        ("project_classification.csv", classifications),
    ):
        with (OUT / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(values[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(values)
    unresolved = [row for row in classifications if row["project"] == "UNRESOLVED"]
    with (OUT / "unresolved_files.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(classifications[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(unresolved)
    print(f"inventoried={len(rows)} unresolved={len(unresolved)}")


if __name__ == "__main__":
    main()
