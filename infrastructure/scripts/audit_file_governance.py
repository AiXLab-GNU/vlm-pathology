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
RENAME_MAP = ROOT / "infrastructure/migrations/2026-08-13-document-hierarchy-naming/file-rename-map.csv"
PROJECT_IDS = (
    "precise_pni_candidate_triage",
    "prostate_biomarker_validation",
    "quantitative_foundation_model_validation",
)
CONTROL_KEYS = (
    "canonical_research_plan",
    "canonical_milestones",
    "canonical_execution_tracker",
)
SURVEY_STATUSES = {
    "PLANNED", "CURRENT", "SUPPORTING", "HISTORICAL", "SUPERSEDED",
}
CURRENT_SURVEY_METADATA = (
    "governing_research_plan:",
    "survey_date:",
    "databases:",
    "scope:",
    "inclusion_criteria:",
    "exclusion_criteria:",
    "authority_status:",
    "supported_research_questions:",
    "supported_baseline_or_method_decisions:",
    "downstream_documents:",
)
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
GENERAL_DOC_NAME = re.compile(
    r"^(?:\d{2}(?:-\d{2}){0,2}-)?[a-z0-9]+(?:-[a-z0-9]+)*(?:-ko)?\.md$"
)
HIERARCHY_DOC_NAME = re.compile(
    r"^(?P<hierarchy_id>(?:0[1-9]|[1-9][0-9])"
    r"(?:-(?:0[1-9]|[1-9][0-9])){0,2})-"
    r"[a-z0-9]+(?:-[a-z0-9]+)*(?:-ko)?\.md$"
)
HIERARCHY_DIRECTORIES = {
    "metric_taxonomy", "preexperiment_plan", "project_plan", "research_plan",
}
DESIGN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-design\.md$")
PLAN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-plan\.md$")
STRUCTURED_NAME = re.compile(r"^[a-z0-9]+(?:[_.-][a-z0-9]+)*\.(?:csv|json|jsonl|toml|tsv|ya?ml)$")
FORBIDDEN_EDITORIAL = re.compile(r"(?:^|[-_])(copy|final2|latest|new|temp)(?:[-_.]|$)", re.I)
FORBIDDEN_DOCUMENT_FINAL = re.compile(r"(?:^|[-_])final(?:[-_.]|$)", re.I)
ONE_DIGIT_VERSION = re.compile(r"(?:^|[-_])v\d(?:[-_.]|$)", re.I)
ENTRYPOINT_PREFIXES = (
    "audit_", "build_", "extract_", "fetch_", "pilot_", "prepare_", "run_",
    "validate_",
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^)]+)\)")


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

    if FORBIDDEN_EDITORIAL.search(name) or (
        suffix == ".md" and FORBIDDEN_DOCUMENT_FINAL.search(name)
    ):
        return fail_or_fixed_contract("forbidden editorial-state token in filename")
    if suffix == ".md" and ONE_DIGIT_VERSION.search(name):
        return fail_or_fixed_contract("one-digit filename version is prohibited; use two digits")
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


def is_hierarchy_document(relative: Path) -> bool:
    """Return whether a Markdown document belongs to a registered ancestry tree."""
    return (
        relative.suffix.lower() == ".md"
        and relative.name != "README.md"
        and "docs" in relative.parts
        and any(part in HIERARCHY_DIRECTORIES for part in relative.parts)
    )


def read_simple_yaml(path: Path) -> dict[str, str]:
    """Read the scalar project metadata used by the repository contract."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.lstrip().startswith("#") or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def hierarchy_id(path: Path) -> str | None:
    match = HIERARCHY_DOC_NAME.fullmatch(path.name)
    return match.group("hierarchy_id") if match else None


def check_markdown_links(path: Path, failures: list[str]) -> None:
    """Check repository-relative links on canonical entry and control documents."""
    text = path.read_text(encoding="utf-8", errors="replace")
    for match in MARKDOWN_LINK.finditer(text):
        target = match.group("target").split()[0].strip("<>")
        target = target.split("#", 1)[0]
        if not target or target.startswith(("/", "#", "http://", "https://", "mailto:")):
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            failures.append(f"link escapes repository: {path.relative_to(ROOT)} -> {target}")
            continue
        if not resolved.exists():
            failures.append(f"broken canonical link: {path.relative_to(ROOT)} -> {target}")


def validate_project_document_controls(
    failures: list[str], exceptions: list[dict[str, str]], baseline_paths: set[str]
) -> None:
    """Validate the single plan→milestones→tracker chain and survey authority index."""
    for project_id in PROJECT_IDS:
        project = ROOT / "projects" / project_id
        metadata_path = project / "PROJECT.yaml"
        if not metadata_path.is_file():
            failures.append(f"{project_id}: missing PROJECT.yaml")
            continue
        metadata = read_simple_yaml(metadata_path)
        control_paths: dict[str, Path] = {}
        for key in (*CONTROL_KEYS, "survey_index", "results_index"):
            value = metadata.get(key, "")
            if not value:
                failures.append(f"{project_id}: PROJECT.yaml missing {key}")
                continue
            path = project / value
            control_paths[key] = path
            if not path.is_file():
                failures.append(f"{project_id}: {key} target missing: {value}")

        if not all(key in control_paths and control_paths[key].is_file() for key in CONTROL_KEYS):
            continue
        plan = control_paths["canonical_research_plan"]
        milestones = control_paths["canonical_milestones"]
        tracker = control_paths["canonical_execution_tracker"]
        ids = [hierarchy_id(path) for path in (plan, milestones, tracker)]
        active_roots: set[Path] = set()
        for candidate in (project / "docs").rglob("*.md"):
            relative = candidate.relative_to(ROOT).as_posix()
            exception = exception_for(relative, exceptions)
            if exception and relative in baseline_paths:
                continue
            candidate_id = hierarchy_id(candidate)
            if candidate_id and len(candidate_id.split("-")) == 1:
                active_roots.add(candidate)
            if "milestones" in candidate.name and candidate != milestones:
                failures.append(
                    f"{project_id}: competing canonical milestone filename: "
                    f"{candidate.relative_to(project)}"
                )
            if "execution-tracker" in candidate.name and candidate != tracker:
                failures.append(
                    f"{project_id}: competing canonical execution tracker filename: "
                    f"{candidate.relative_to(project)}"
                )
        if active_roots != {plan}:
            rendered = ", ".join(sorted(path.relative_to(project).as_posix() for path in active_roots))
            failures.append(
                f"{project_id}: expected exactly one hierarchy root at canonical research plan; "
                f"found {rendered or 'none'}"
            )
        if ids[0] is None or len(ids[0].split("-")) != 1:
            failures.append(f"{project_id}: canonical research plan must be hierarchy level 1")
        if ids[1] is None or ids[0] is None or ids[1] != f"{ids[0]}-{ids[1].split('-')[-1]}":
            failures.append(f"{project_id}: canonical milestones must directly refine the plan")
        if ids[2] is None or ids[1] is None or ids[2] != f"{ids[1]}-{ids[2].split('-')[-1]}":
            failures.append(f"{project_id}: execution tracker must directly refine milestones")
        if "milestones" not in milestones.name:
            failures.append(f"{project_id}: canonical milestone filename lacks milestones role")
        if "execution-tracker" not in tracker.name:
            failures.append(f"{project_id}: canonical tracker filename lacks execution-tracker role")

        all_control_text = {
            path: path.read_text(encoding="utf-8", errors="replace")
            for path in (plan, milestones, tracker)
        }
        for path, text_value in all_control_text.items():
            for peer in (plan, milestones, tracker):
                if peer != path and peer.name not in text_value:
                    failures.append(
                        f"{project_id}: missing reciprocal control link in "
                        f"{path.relative_to(ROOT)} -> {peer.name}"
                    )

        root_entries = (
            project / "README.md",
            project / "MILESTONES.md",
            project / "00-project-sequence/README.md",
            project / "docs/README.md",
        )
        for entry in root_entries:
            if not entry.is_file():
                failures.append(f"{project_id}: missing canonical entry document {entry.relative_to(ROOT)}")
                continue
            entry_text = entry.read_text(encoding="utf-8", errors="replace")
            for control in (plan, milestones, tracker):
                if control.name not in entry_text:
                    failures.append(
                        f"{project_id}: {entry.relative_to(ROOT)} does not reference {control.name}"
                    )

        survey_index = control_paths.get("survey_index")
        if survey_index and survey_index.is_file():
            survey_text = survey_index.read_text(encoding="utf-8", errors="replace")
            survey_dir = survey_index.parent
            survey_ids: dict[str, Path] = {}
            for survey in sorted(survey_dir.glob("*.md")):
                if survey.name != "README.md" and survey.name not in survey_text:
                    failures.append(f"{project_id}: survey not registered in index: {survey.name}")
                survey_id = hierarchy_id(survey)
                if survey_id:
                    if survey_id in survey_ids:
                        failures.append(
                            f"{project_id}: duplicate survey hierarchy ID {survey_id}: "
                            f"{survey_ids[survey_id].name} and {survey.name}"
                        )
                    survey_ids[survey_id] = survey
            sibling_numbers: dict[str, list[int]] = {}
            for survey_id in survey_ids:
                segments = survey_id.split("-")
                parent = "-".join(segments[:-1])
                sibling_numbers.setdefault(parent, []).append(int(segments[-1]))
            for parent, numbers in sibling_numbers.items():
                ordered = sorted(numbers)
                if ordered != list(range(1, max(ordered) + 1)):
                    failures.append(
                        f"{project_id}: survey hierarchy has a gap under {parent or 'root'}: {ordered}"
                    )
            for line in survey_text.splitlines():
                statuses = SURVEY_STATUSES.intersection(line.split())
                if not statuses:
                    continue
                if "SUPERSEDED" in statuses and len(list(MARKDOWN_LINK.finditer(line))) < 2:
                    failures.append(f"{project_id}: SUPERSEDED survey lacks replacement link")
                if "CURRENT" in statuses:
                    current_links = [
                        match.group("target").split("#", 1)[0]
                        for match in MARKDOWN_LINK.finditer(line)
                        if match.group("target").split("#", 1)[0].endswith(".md")
                    ]
                    plan_text = all_control_text[plan]
                    for target in current_links:
                        if Path(target).name not in plan_text:
                            failures.append(
                                f"{project_id}: CURRENT survey is not linked from research plan: {target}"
                            )
                        current_path = survey_dir / target
                        if current_path.is_file():
                            current_text = current_path.read_text(
                                encoding="utf-8", errors="replace"
                            )
                            missing_metadata = [
                                field for field in CURRENT_SURVEY_METADATA
                                if field not in current_text
                            ]
                            if missing_metadata:
                                failures.append(
                                    f"{project_id}: CURRENT survey missing metadata "
                                    f"{Path(target).name}: {','.join(missing_metadata)}"
                                )

        linked_documents = (*root_entries, plan, milestones, tracker)
        if survey_index and survey_index.is_file():
            linked_documents = (*linked_documents, survey_index)
        for path in linked_documents:
            if path.is_file():
                check_markdown_links(path, failures)

    if RENAME_MAP.is_file():
        rename_rows = read_rows(RENAME_MAP)
        old_paths = [row["old_path"] for row in rename_rows]
        chained_paths = set(old_paths)
        for row in rename_rows:
            if not re.fullmatch(r"[0-9a-f]{64}", row.get("pre_sha256", "")):
                failures.append(f"rename map has invalid pre_sha256: {row.get('old_path', '')}")
            if not re.fullmatch(r"[0-9a-f]{64}", row.get("post_sha256", "")):
                failures.append(f"rename map has invalid post_sha256: {row.get('new_path', '')}")
            target = ROOT / row["new_path"]
            if row["new_path"] not in chained_paths:
                if not target.is_file():
                    failures.append(f"rename map terminal target missing: {row['new_path']}")
                elif digest(target) != row["post_sha256"]:
                    failures.append(f"rename map terminal hash mismatch: {row['new_path']}")
        for path in iter_managed_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith("infrastructure/migrations/"):
                continue
            exception = exception_for(relative, exceptions)
            if exception and exception.get("lifecycle") in {"frozen", "legacy", "archive"}:
                continue
            file_class, lifecycle, _ = classify(path.relative_to(ROOT))
            if lifecycle in {"frozen", "legacy", "generated", "archive"}:
                continue
            text_value = path.read_text(encoding="utf-8", errors="replace")
            for old_path in old_paths:
                old_name_pattern = re.compile(
                    rf"(?<![A-Za-z0-9-]){re.escape(Path(old_path).name)}"
                )
                if old_path in text_value or old_name_pattern.search(text_value):
                    failures.append(f"stale canonical path in {relative}: {old_path}")


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
    hierarchy_documents: list[tuple[str, str, str]] = []
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
        if is_hierarchy_document(relative_path):
            grandfathered = exception is not None and relative in baseline_paths
            if not grandfathered:
                match = HIERARCHY_DOC_NAME.fullmatch(relative_path.name)
                if match is None:
                    failures.append(
                        f"hierarchy naming violation: {relative}: "
                        "expected NN[-NN[-NN]] ancestry prefix"
                    )
                else:
                    hierarchy_documents.append(
                        (owner_for(relative_path), match.group("hierarchy_id"), relative)
                    )
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

    hierarchy_by_owner: dict[str, dict[str, str]] = {}
    for owner, hierarchy_id, relative in hierarchy_documents:
        owner_tree = hierarchy_by_owner.setdefault(owner, {})
        if hierarchy_id in owner_tree:
            failures.append(
                f"duplicate hierarchy identifier for {owner}: {hierarchy_id}: "
                f"{owner_tree[hierarchy_id]} and {relative}"
            )
        else:
            owner_tree[hierarchy_id] = relative

    for owner, owner_tree in hierarchy_by_owner.items():
        for hierarchy_id, relative in owner_tree.items():
            segments = hierarchy_id.split("-")
            if len(segments) == 1:
                if not re.search(r"-plan(?:-ko)?\.md$", Path(relative).name):
                    failures.append(
                        f"hierarchy root is not a governing plan: {relative}"
                    )
                continue
            parent_id = "-".join(segments[:-1])
            if parent_id not in owner_tree:
                failures.append(
                    f"missing hierarchy parent for {relative}: expected {parent_id}"
                )

    validate_project_document_controls(failures, exceptions, baseline_paths)

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
