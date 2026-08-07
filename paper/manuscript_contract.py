"""TeX-aware, submission-facing manuscript structure contracts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_SUBMISSION_LANGUAGE = (
    "MajorRevision-v1",
    "Gate A",
    "Gate B",
    "Gate C",
    "Gate D",
    "Gate E",
    "R1--R5",
    "A3",
    "Additional GPU",
    "unused compute",
    "not run optional experiments",
    "internal analysis",
    "embargo pending",
    "To be completed",
)

FORBIDDEN_SUBMISSION_PATTERNS = (
    r"(?<![A-Za-z0-9_-])MajorRevision-v1(?![A-Za-z0-9_-])",
    r"\bGate\s+[A-Za-z]\b",
    r"\bR[1-7]\b",
    r"\bA[1-3]\b",
    r"\bO[1-3]\b",
    r"\bAdditional\s+GPU\b",
    r"\bunused\s+(?:GPU\s+)?compute\b",
    r"\bGPU\s+(?:was\s+)?not\s+used\b",
    r"\bnot\s+using\s+(?:an?\s+)?GPU\b",
    r"\bnot\s+run(?:ning)?\s+(?:an?\s+)?optional\s+experiments?\b",
    r"\binternal\s+analysis\b",
    r"\bembargo\s+pending\b",
    r"\bTo\s+be\s+completed\b",
)

EXPECTED_SECTION_ORDER = (
    "Introduction",
    "Results",
    "Discussion",
    "Methods",
    "Data Availability",
    "Code Availability",
    "Author Contributions",
    "Competing Interests",
    "Ethics and consent statement",
    "References",
)


@dataclass(frozen=True)
class ContractResult:
    check_id: str
    passed: bool
    detail: str


def _without_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def strip_tex_commands(text: str) -> str:
    """Return visible prose while discarding TeX metadata, math, and URLs."""
    cleaned = _without_comments(text)
    cleaned = re.sub(r"\\href(?:\[[^\]]*\])?\{[^{}]*\}\{([^{}]*)\}", r"\1", cleaned)
    cleaned = re.sub(
        r"\\(?:[a-zA-Z@]*cite[a-zA-Z@]*)(?:\*)?(?:\s*\[[^\[\]]*\])*\s*\{[^{}]*\}",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\\(?:label|ref|pageref|url|includegraphics|input|bibliography)"
        r"(?:\[[^\]]*\])?\{[^{}]*\}",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\\begin\s*\{[^{}]*\}|\\end\s*\{[^{}]*\}", "", cleaned)
    cleaned = re.sub(r"\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)", "", cleaned)
    cleaned = re.sub(r"\$\$[\s\S]*?\$\$|\$[^$]*\$", "", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?", "", cleaned)
    cleaned = re.sub(r"\\[^a-zA-Z\s]", "", cleaned)
    cleaned = cleaned.replace("{", "").replace("}", "")
    return " ".join(cleaned.split())


def count_prose_words(text: str) -> int:
    """Count visible prose words after excluding TeX-only material."""
    visible = strip_tex_commands(text)
    return len(re.findall(r"(?u)\b[\w]+(?:['’\-][\w]+)*\b", visible))


def extract_environment(text: str, name: str) -> str:
    """Extract the first named TeX environment, including nested instances."""
    begin = re.compile(rf"\\begin\s*\{{\s*{re.escape(name)}\s*\}}")
    end = re.compile(rf"\\end\s*\{{\s*{re.escape(name)}\s*\}}")
    match = begin.search(text)
    if match is None:
        return ""
    depth = 1
    position = match.end()
    while depth:
        next_begin = begin.search(text, position)
        next_end = end.search(text, position)
        if next_end is None:
            return ""
        if next_begin is not None and next_begin.start() < next_end.start():
            depth += 1
            position = next_begin.end()
        else:
            depth -= 1
            if depth == 0:
                return text[match.end():next_end.start()]
            position = next_end.end()
    return ""


def _tex_path(root: Path, value: str, parent: Path) -> Path | None:
    candidate = Path(value)
    if candidate.suffix != ".tex":
        candidate = candidate.with_suffix(".tex")
    for base in (parent, root):
        path = base / candidate
        if path.is_file():
            return path
    return None


def _expand_inputs(path: Path, root: Path, seen: set[Path] | None = None) -> str:
    seen = set() if seen is None else seen
    resolved = path.resolve()
    if resolved in seen or not path.is_file():
        return ""
    seen.add(resolved)
    text = path.read_text(encoding="utf-8")

    def replace_input(match: re.Match[str]) -> str:
        included = _tex_path(root, match.group(1).strip(), path.parent)
        return _expand_inputs(included, root, seen) if included is not None else ""

    return re.sub(r"\\input\s*\{([^{}]+)\}", replace_input, text)


def _submission_text(root: Path) -> str:
    return _expand_inputs(root / "paper" / "main.tex", root)


def _command_argument(text: str, command: str) -> str:
    match = re.search(rf"\\{re.escape(command)}\s*\{{", text)
    if match is None:
        return ""
    start = match.end()
    depth = 1
    for index, character in enumerate(text[start:], start):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start:index]
    return ""


def _section_headings(text: str) -> list[str]:
    headings = []
    tokens = re.compile(
        r"\\section\*?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
        r"|\\begin\s*\{thebibliography\}"
    )
    for match in tokens.finditer(text):
        headings.append(
            strip_tex_commands(match.group(1)) if match.group(1) is not None else "References"
        )
    return headings


def _has_required_declarations(headings: list[str]) -> bool:
    normalized = [" ".join(heading.lower().split()) for heading in headings]
    required = {
        "data availability",
        "code availability",
        "author contributions",
        "competing interests",
    }
    return required.issubset(normalized) and any(
        "ethics" in heading or "consent" in heading for heading in normalized
    )


def scan_forbidden_submission_language(root: Path) -> list[str]:
    """List forbidden internal-workflow text in the active submission TeX."""
    text = _submission_text(root)
    findings = []
    for pattern in FORBIDDEN_SUBMISSION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            phrase = match.group(0)
            if phrase not in findings:
                findings.append(phrase)
    return findings


def validate_manuscript(root: Path) -> list[ContractResult]:
    """Validate Scientific Reports structure without modifying manuscript sources."""
    text = _submission_text(root)
    title_words = count_prose_words(_command_argument(text, "title"))
    abstract_words = count_prose_words(extract_environment(text, "abstract"))
    headings = _section_headings(text)
    results = [
        ContractResult(
            "TITLE_WORDS_LE_20", title_words <= 20,
            f"title prose words: {title_words} (limit: 20)",
        ),
        ContractResult(
            "ABSTRACT_WORDS_LE_200", abstract_words <= 200,
            f"abstract prose words: {abstract_words} (limit: 200)",
        ),
        ContractResult(
            "SECTION_ORDER", tuple(headings) == EXPECTED_SECTION_ORDER,
            f"found section order: {headings}",
        ),
        ContractResult(
            "DECLARATIONS_PRESENT", _has_required_declarations(headings),
            "required declarations: Data Availability, Code Availability, Author "
            "Contributions, Competing Interests, and ethics/consent",
        ),
    ]
    forbidden = scan_forbidden_submission_language(root)
    results.append(ContractResult(
        "FORBIDDEN_SUBMISSION_LANGUAGE", not forbidden,
        "forbidden phrases: " + (", ".join(forbidden) if forbidden else "none"),
    ))
    return results
