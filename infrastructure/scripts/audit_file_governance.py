#!/usr/bin/env python3
"""Audit document/code ownership, class, lifecycle, placement, and naming."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_ROOT = ROOT / "infrastructure/docs/repository"
TYPE_REGISTRY = POLICY_ROOT / "FILE_TYPE_REGISTRY.csv"
EXCEPTION_REGISTRY = POLICY_ROOT / "FILE_GOVERNANCE_EXCEPTIONS.csv"
BASELINE = ROOT / "infrastructure/migrations/2026-08-12-file-governance/FILE_GOVERNANCE_BASELINE.csv"
ROOT_DOCUMENTS = {
    "AGENTS.md", "CLAUDE.md", "README.md", "environment.yml",
}
MANAGED_SUFFIXES = {
    ".css", ".csv", ".html", ".js", ".json", ".jsonl", ".md", ".py",
    ".sh", ".tex", ".toml", ".tsv", ".yaml", ".yml",
}
SKIP_PARTS = {".git", ".venv", "__pycache__"}
FIXED_NAMES = {
    "AGENTS.md", "CLAIM_BOUNDARIES.md", "CLAUDE.md", "MILESTONES.md",
    "PROJECT.yaml", "README.md",
}
POLICY_CONTRACT_NAMES = {
    "FILE_GOVERNANCE_CODEX.md",
    "FILE_GOVERNANCE_EXCEPTIONS.csv",
    "FILE_NAMING_CODEX.md",
    "FILE_TYPE_REGISTRY.csv",
    "PROJECT_STRUCTURE_CODEX.md",
    "ROOT_DIRECTORY_REGISTRY.csv",
    "SUPERPOWERS_DOCUMENT_HEADER.md",
}
PYTHON_NAME = re.compile(r"^(?:__init__|__main__|[a-z][a-z0-9_]*)\.py$")
SHELL_NAME = re.compile(r"^[a-z][a-z0-9_]*\.sh$")
WEB_NAME = re.compile(r"^[a-z][a-z0-9-]*\.(?:css|html|js)$")
GENERAL_DOC_NAME = re.compile(r"^(?:\d{2}-)?[a-z0-9]+(?:-[a-z0-9]+)*(?:-ko)?\.md$")
DESIGN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-design\.md$")
PLAN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-plan\.md$")
STRUCTURED_NAME = re.compile(r"^[a-z0-9]+(?:[_.-][a-z0-9]+)*\.(?:csv|json|jsonl|toml|tsv|ya?ml)$")
FORBIDDEN_EDITORIAL = re.compile(r"(?:^|[-_])(copy|final2|latest|new|temp)(?:[-_.]|$)", re.I)
ENTRYPOINT_PREFIXES = (
    "audit_", "build_", "extract_", "fetch_", "pilot_", "prepare_", "run_",
    "validate_",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def iter_managed_files():
    for name in sorted(ROOT_DOCUMENTS):
        path = ROOT / name
        if path.is_file():
            yield path
    for base in (ROOT / "projects", ROOT / "infrastructure"):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MANAGED_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.resolve() == BASELINE.resolve():
                continue
            yield path


def owner_for(relative: Path) -> str:
    if relative.parts and relative.parts[0] == "projects" and len(relative.parts) > 1:
        return relative.parts[1]
    return "repository"


def exception_for(relative: str, rows: list[dict[str, str]]) -> dict[str, str] | None:
    for row in rows:
        if fnmatch.fnmatchcase(relative, row["path_pattern"]):
            return row
    return None


def classify(relative: Path) -> tuple[str, str, str]:
    value = relative.as_posix()
    parts = relative.parts
    suffix = relative.suffix.lower()
    name = relative.name

    if name == "README.md":
        return "readme", "active", "source"
    if len(parts) == 1 or (len(parts) == 3 and parts[0] == "projects" and name in FIXED_NAMES):
        kind = "configuration" if suffix in {".yaml", ".yml"} else "project_policy"
        return kind, "active", "source"
    if "/docs/designs/" in f"/{value}" or "/docs/superpowers/specs/" in f"/{value}":
        return "design", "active", "source"
    if "/docs/plans/" in f"/{value}" or "/docs/superpowers/plans/" in f"/{value}":
        return "plan", "active", "source"
    if value.startswith("infrastructure/docs/repository/"):
        kind = "configuration" if suffix in {".csv", ".yaml", ".yml"} else "repository_policy"
        return kind, "active", "source"
    if value.startswith("infrastructure/migrations/"):
        return "migration_record", "frozen", "record"
    if "/tests/" in f"/{value}" and suffix == ".py":
        return "test", "active", "source"
    if value.startswith("infrastructure/scripts/") and suffix in {".py", ".sh"}:
        return "repository_operation", "active", "source"
    if value.startswith("infrastructure/packages/"):
        if "/web/" in f"/{value}" and suffix in {".css", ".html", ".js"}:
            return "web_asset", "active", "source"
        if "/data/" in f"/{value}" and suffix in {".csv", ".json", ".tsv"}:
            return "source_table", "frozen", "record"
        if suffix in {".py", ".toml"}:
            return "package_source", "active", "source"
    if "/code/legacy/" in f"/{value}":
        return "legacy_code", "legacy", "source"
    if "/paper/figures/" in f"/{value}" and suffix == ".py":
        return "figure_renderer", "active", "source"
    if "/paper/generated/" in f"/{value}":
        return "generated_manuscript", "generated", "generated"
    if "/paper/figure_data/" in f"/{value}" and suffix in {".csv", ".json", ".tsv"}:
        return "source_table", "frozen", "derived_source_table"
    if "/paper/" in f"/{value}":
        if suffix in {".py", ".sh"}:
            return ("analysis_entrypoint" if name.startswith(ENTRYPOINT_PREFIXES) else "library_module"), "active", "source"
        if suffix in {".csv", ".json", ".jsonl", ".tsv"}:
            return "manifest_record", "frozen", "record"
        return "manuscript_source", "active", "source"
    if "/docs/study_design/" in f"/{value}" or "/docs/legacy/" in f"/{value}":
        return "legacy_document", "legacy", "record"
    if "/docs/pathologist_protocol/" in f"/{value}" or "/docs/protocols/" in f"/{value}":
        return "protocol", "frozen", "source"
    if "/docs/research_plan/" in f"/{value}" or "/docs/project_plan/" in f"/{value}":
        return "research_plan", "active", "source"
    if "/docs/surveys/" in f"/{value}":
        return "survey", "active", "source"
    if "/docs/" in f"/{value}" and suffix == ".md":
        return "protocol", "active", "source"
    if "/governance_records/" in f"/{value}":
        return "governance_record", "frozen", "record"
    if "/milestones/" in f"/{value}" and "/outputs/" in f"/{value}":
        return "report" if suffix == ".md" else "evidence_table", "generated", "generated"
    if "/preexperiment/" in f"/{value}":
        if suffix in {".py", ".sh"}:
            return "analysis_entrypoint", "frozen", "source"
        return "governance_record", "frozen", "record"
    if "/governance_portal/" in f"/{value}":
        if suffix in {".css", ".html", ".js"}:
            return "web_asset", "active", "source"
        return "analysis_entrypoint", "active", "source"
    if "/code/" in f"/{value}" and suffix in {".py", ".sh"}:
        kind = "analysis_entrypoint" if name.startswith(ENTRYPOINT_PREFIXES) else "library_module"
        return kind, "active", "source"
    if "/manifests/" in f"/{value}" or "manifest" in name.lower():
        return "manifest_record", "frozen", "record"
    if "/reports/" in f"/{value}":
        return "report", "generated", "generated"
    if suffix in {".csv", ".json", ".jsonl", ".tsv"}:
        return "evidence_table", "generated", "record"
    if suffix in {".yaml", ".yml", ".toml"}:
        return "configuration", "active", "source"
    if suffix in {".css", ".html", ".js"}:
        return "web_asset", "active", "source"
    if suffix in {".py", ".sh"}:
        return "library_module", "active", "source"
    if suffix in {".md", ".tex"}:
        return "protocol", "active", "source"
    return "unclassified", "active", "unknown"


def naming_status(
    relative: Path,
    file_class: str,
    exception: dict[str, str] | None,
    baseline_paths: set[str],
) -> tuple[str, str]:
    name = relative.name
    suffix = relative.suffix.lower()

    def fail_or_fixed_contract(note: str) -> tuple[str, str]:
        if exception is not None and relative.as_posix() in baseline_paths:
            return "fixed_contract", exception["reason"]
        return "fail", note

    if FORBIDDEN_EDITORIAL.search(name):
        return fail_or_fixed_contract("forbidden editorial-state token in filename")
    if name in FIXED_NAMES or name in POLICY_CONTRACT_NAMES or name in {"environment.yml"}:
        return "pass", "fixed contract name"
    if file_class == "design":
        return ("pass", "dated design name") if DESIGN_NAME.fullmatch(name) else fail_or_fixed_contract("design name must end -design.md")
    if file_class == "plan":
        return ("pass", "dated plan name") if PLAN_NAME.fullmatch(name) else fail_or_fixed_contract("plan name must end -plan.md")
    if suffix == ".py":
        return ("pass", "snake-case Python") if PYTHON_NAME.fullmatch(name) else fail_or_fixed_contract("Python filename is not lower_snake_case")
    if suffix == ".sh":
        return ("pass", "snake-case shell") if SHELL_NAME.fullmatch(name) else fail_or_fixed_contract("shell filename is not lower_snake_case")
    if suffix in {".css", ".html", ".js"}:
        return ("pass", "lowercase web asset") if WEB_NAME.fullmatch(name) else fail_or_fixed_contract("web filename is not lowercase kebab-case")
    if suffix == ".md":
        return ("pass", "canonical Markdown name") if GENERAL_DOC_NAME.fullmatch(name) else fail_or_fixed_contract("Markdown filename is not canonical lowercase kebab-case")
    if suffix == ".tex":
        stem_ok = bool(re.fullmatch(r"[a-z][a-z0-9_]*", relative.stem))
        return ("pass", "snake-case TeX") if stem_ok else fail_or_fixed_contract("TeX filename is not lower_snake_case")
    if suffix in {".csv", ".json", ".jsonl", ".toml", ".tsv", ".yaml", ".yml"}:
        return ("pass", "canonical structured-record name") if STRUCTURED_NAME.fullmatch(name) else fail_or_fixed_contract("structured-record filename is not canonical lowercase")
    return "pass", "no additional naming rule"


def metadata_status(path: Path, file_class: str, exception: dict[str, str] | None) -> tuple[str, str]:
    if file_class not in {"design", "plan"} or exception is not None:
        return "not_required", ""
    text = path.read_text(encoding="utf-8", errors="replace")
    required = ("document_id:", "owner_project:", "document_type:", "status:", "canonical_path:")
    missing = [field for field in required if field not in text]
    if not text.startswith("---\n") or missing:
        return "fail", "missing metadata: " + ",".join(missing)
    return "pass", "required metadata present"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-catalog", type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    if not TYPE_REGISTRY.is_file() or not EXCEPTION_REGISTRY.is_file():
        print(json.dumps({"status": "FAIL", "failures": ["missing file governance registry"]}, indent=2))
        return 1
    registered_classes = {row["file_class"] for row in read_rows(TYPE_REGISTRY)}
    exceptions = read_rows(EXCEPTION_REGISTRY)
    baseline_paths: set[str] = set()
    if BASELINE.is_file():
        baseline_paths = {row["path"] for row in read_rows(BASELINE)}

    rows: list[dict[str, str | int]] = []
    for path in iter_managed_files():
        relative_path = path.relative_to(ROOT)
        relative = relative_path.as_posix()
        exception = exception_for(relative, exceptions)
        file_class, lifecycle, provenance = classify(relative_path)
        name_status, name_note = naming_status(
            relative_path, file_class, exception, baseline_paths
        )
        meta_status, meta_note = metadata_status(path, file_class, exception)
        if file_class not in registered_classes:
            failures.append(f"unregistered file class: {relative} -> {file_class}")
        if name_status == "fail":
            failures.append(f"naming violation: {relative}: {name_note}")
        if meta_status == "fail":
            failures.append(f"metadata violation: {relative}: {meta_note}")
        if (
            exception is not None
            and exception.get("disposition", "").startswith("no new")
            and baseline_paths
            and relative not in baseline_paths
        ):
            failures.append(f"new file in closed exception scope: {relative}")
        rows.append({
            "path": relative,
            "owner": owner_for(relative_path),
            "file_class": file_class,
            "lifecycle": lifecycle,
            "provenance_role": provenance,
            "naming_status": name_status,
            "metadata_status": meta_status,
            "exception_pattern": exception["path_pattern"] if exception else "",
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        })

    if args.write_catalog:
        args.write_catalog.parent.mkdir(parents=True, exist_ok=True)
        with args.write_catalog.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        key = str(row["file_class"])
        counts[key] = counts.get(key, 0) + 1
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "managed_file_count": len(rows),
        "classified_file_count": sum(row["file_class"] != "unclassified" for row in rows),
        "exception_file_count": sum(bool(row["exception_pattern"]) for row in rows),
        "canonical_name_count": sum(row["naming_status"] == "pass" for row in rows),
        "fixed_contract_name_count": sum(
            row["naming_status"] == "fixed_contract" for row in rows
        ),
        "class_counts": dict(sorted(counts.items())),
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
