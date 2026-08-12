#!/usr/bin/env python3
"""Audit auxiliary Git worktrees against the project-scoped registry."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKTREE_ROOT = ROOT / ".worktrees"
REGISTRY = WORKTREE_ROOT / "registry.csv"
PROJECTS = {
    "precise_pni_candidate_triage",
    "quantitative_foundation_model_validation",
    "prostate_biomarker_validation",
}
ALLOWED_STATUSES = {"reserved", "active", "merged", "abandoned", "removed"}


def listed_worktrees() -> list[dict[str, str]]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines() + [""]:
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return records


def main() -> int:
    failures: list[str] = []
    if not REGISTRY.is_file():
        failures.append("missing .worktrees/registry.csv")
        rows: list[dict[str, str]] = []
    else:
        with REGISTRY.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    paths: set[str] = set()
    branches: set[str] = set()
    active_by_path: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, 2):
        project = row.get("project_id", "")
        slug = row.get("purpose_slug", "")
        relative = row.get("relative_path", "")
        branch = row.get("branch", "")
        status = row.get("status", "")
        if project not in PROJECTS:
            failures.append(f"registry row {row_number}: unknown project_id {project!r}")
        expected_relative = f".worktrees/{project}/{slug}"
        if relative != expected_relative:
            failures.append(f"registry row {row_number}: expected relative_path {expected_relative!r}")
        expected_branch = f"work/{project}/{slug}"
        if branch != expected_branch:
            failures.append(f"registry row {row_number}: expected branch {expected_branch!r}")
        if status not in ALLOWED_STATUSES:
            failures.append(f"registry row {row_number}: invalid status {status!r}")
        if relative in paths:
            failures.append(f"duplicate registry path: {relative}")
        if branch in branches:
            failures.append(f"duplicate registry branch: {branch}")
        paths.add(relative)
        branches.add(branch)
        if status == "active":
            active_by_path[relative] = row

    try:
        worktrees = listed_worktrees()
    except (OSError, subprocess.CalledProcessError) as error:
        failures.append(f"cannot enumerate Git worktrees: {error}")
        worktrees = []

    observed_auxiliary: set[str] = set()
    for record in worktrees:
        path_value = record.get("worktree", "")
        path = Path(path_value).resolve()
        if path == ROOT.resolve():
            continue
        try:
            relative = path.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            failures.append(f"auxiliary worktree is outside repository control root: {path}")
            continue
        parts = Path(relative).parts
        if len(parts) != 3 or parts[0] != ".worktrees":
            failures.append(f"noncanonical auxiliary worktree path: {relative}")
            continue
        project, slug = parts[1], parts[2]
        if project not in PROJECTS:
            failures.append(f"worktree has unknown project: {relative}")
        expected_branch = f"refs/heads/work/{project}/{slug}"
        if record.get("branch") != expected_branch:
            failures.append(
                f"worktree branch mismatch: {relative} uses {record.get('branch', '<detached>')}"
            )
        if relative not in active_by_path:
            failures.append(f"active worktree missing active registry row: {relative}")
        observed_auxiliary.add(relative)

    for relative in sorted(set(active_by_path) - observed_auxiliary):
        failures.append(f"active registry row has no Git worktree: {relative}")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "registered_rows": len(rows),
        "active_auxiliary_worktrees": len(observed_auxiliary),
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
