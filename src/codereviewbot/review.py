"""Rule-based review of unified diffs.

No LLM is involved: every finding comes from regexes and simple
heuristics over added lines. The "summary" in the report is a
deterministic template, not generated text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LONG_FUNCTION_LINES = 40

SECRET_PATTERNS = [
    (
        re.compile(r"""(?i)\b(api[_-]?key|apikey)\s*[:=]\s*['"][^'"]+['"]"""),
        "hardcoded api_key",
    ),
    (
        re.compile(r"""(?i)\b(password|passwd|pwd)\s*[:=]\s*['"][^'"]+['"]"""),
        "hardcoded password",
    ),
    (
        re.compile(r"""(?i)\b(secret|token)\s*[:=]\s*['"][^'"]+['"]"""),
        "hardcoded secret/token",
    ),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key ID"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "API key starting with sk-"),
    (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "private key block",
    ),
]

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX)\b")

DEBUG_PATTERNS = [
    (re.compile(r"\bprint\s*\("), "print() leftover"),
    (re.compile(r"\bconsole\.log\s*\("), "console.log() leftover"),
    (re.compile(r"\bpdb\b"), "pdb debugger leftover"),
    (re.compile(r"\bbreakpoint\s*\("), "breakpoint() leftover"),
]

RISKY_CALL_PATTERN = re.compile(r"\b(open\s*\(|requests\.\w+)")
TRY_PATTERN = re.compile(r"^\s*(try|except)\b")


@dataclass
class AddedLine:
    """One added line of a diff, with its file, new-file line number, and hunk."""

    file: str
    line_no: int
    text: str
    hunk: int


@dataclass
class Finding:
    file: str
    line: int
    severity: str  # "high" or "medium"
    kind: str
    message: str


def parse_diff(text: str) -> list[AddedLine]:
    """Extract added lines from a unified diff.

    Line numbers refer to the new version of each file. Removed lines
    do not advance the new-file line counter.
    """
    added: list[AddedLine] = []
    current_file = "unknown"
    new_line_no = 0
    hunk = -1
    hunk_header = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for raw in text.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            continue
        if raw.startswith("--- ") or raw.startswith("diff ") or raw.startswith("index "):
            continue
        match = hunk_header.match(raw)
        if match:
            hunk += 1
            new_line_no = int(match.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append(AddedLine(current_file, new_line_no, raw[1:], hunk))
            new_line_no += 1
        elif raw.startswith("-"):
            continue  # removed line: new-file counter does not move
        elif raw.startswith(" ") or raw == "":
            new_line_no += 1
    return added


def _flag_per_line(added: list[AddedLine]) -> list[Finding]:
    findings: list[Finding] = []
    for line in added:
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(line.text):
                findings.append(
                    Finding(line.file, line.line_no, "high", "secret", label)
                )
        match = TODO_PATTERN.search(line.text)
        if match:
            findings.append(
                Finding(
                    line.file,
                    line.line_no,
                    "medium",
                    "todo",
                    f"{match.group(1)} comment left in code",
                )
            )
        for pattern, label in DEBUG_PATTERNS:
            if pattern.search(line.text):
                findings.append(
                    Finding(line.file, line.line_no, "medium", "debug", label)
                )
    return findings


def _flag_long_functions(added: list[AddedLine]) -> list[Finding]:
    """Crude heuristic: a `def` followed by >40 added lines before the
    next `def` (or end of file) counts as a long function.

    It counts added lines only, so a function that mostly moves existing
    code will not trip it, and a genuinely long function split across
    several hunks can be missed. Treat it as a nudge, not a measurement.
    """
    findings: list[Finding] = []
    by_file: dict[str, list[AddedLine]] = {}
    for line in added:
        by_file.setdefault(line.file, []).append(line)

    def_pattern = re.compile(r"^\s*def\s+(\w+)\s*\(")
    for filename, lines in by_file.items():
        defs = [(i, m.group(1)) for i, m in
                ((i, def_pattern.search(ln.text)) for i, ln in enumerate(lines))
                if m]
        for idx, (pos, name) in enumerate(defs):
            end = defs[idx + 1][0] if idx + 1 < len(defs) else len(lines)
            body_lines = end - pos - 1
            if body_lines > LONG_FUNCTION_LINES:
                findings.append(
                    Finding(
                        filename,
                        lines[pos].line_no,
                        "medium",
                        "long-function",
                        f"function '{name}' has ~{body_lines} added lines "
                        f"(over the {LONG_FUNCTION_LINES}-line heuristic)",
                    )
                )
    return findings


def _flag_missing_error_handling(added: list[AddedLine]) -> list[Finding]:
    """Flag open()/requests. calls in a hunk with no try/except.

    "Nearby" means the same hunk: if any added line in the hunk is a
    try/except, the whole hunk is treated as guarded.
    """
    findings: list[Finding] = []
    by_hunk: dict[int, list[AddedLine]] = {}
    for line in added:
        by_hunk.setdefault(line.hunk, []).append(line)
    for lines in by_hunk.values():
        guarded = any(TRY_PATTERN.search(ln.text) for ln in lines)
        if guarded:
            continue
        for ln in lines:
            match = RISKY_CALL_PATTERN.search(ln.text)
            if match:
                findings.append(
                    Finding(
                        ln.file,
                        ln.line_no,
                        "medium",
                        "error-handling",
                        f"{match.group(1).rstrip('(')} call with no "
                        "try/except in the same hunk",
                    )
                )
    return findings


def review_diff(text: str) -> list[Finding]:
    """Run all checks over a unified diff and return sorted findings."""
    added = parse_diff(text)
    findings = (
        _flag_per_line(added)
        + _flag_long_functions(added)
        + _flag_missing_error_handling(added)
    )
    return sorted(findings, key=lambda f: (f.file, f.line, f.kind))


def verdict(findings: list[Finding]) -> str:
    return "REQUEST CHANGES" if any(f.severity == "high" for f in findings) else "APPROVE"


def render_markdown(findings: list[Finding]) -> str:
    """Render the review as markdown."""
    out = ["# Code Review", ""]
    if not findings:
        out.append("No issues found in the added lines.")
        out.append("")
    else:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        out.append("## Findings")
        out.append("")
        out.append(
            f"{len(findings)} finding(s): "
            + ", ".join(f"{kind} ({n})" for kind, n in sorted(counts.items()))
            + "."
        )
        out.append("")
        by_file: dict[str, list[Finding]] = {}
        for f in findings:
            by_file.setdefault(f.file, []).append(f)
        for filename in sorted(by_file):
            out.append(f"### `{filename}`")
            out.append("")
            for f in by_file[filename]:
                out.append(
                    f"- Line {f.line} [{f.severity}] **{f.kind}**: {f.message}"
                )
            out.append("")

    # Deterministic template summary — labelled as such, no LLM call.
    out.append("## Summary (template, no LLM call)")
    out.append("")
    if findings:
        riskiest = sorted(
            {f.file for f in findings},
            key=lambda name: sum(1 for f in findings if f.file == name),
            reverse=True,
        )[0]
        kinds = ", ".join(sorted({f.kind for f in findings}))
        out.append(
            f"This diff adds {len(findings)} flagged item(s) across "
            f"{len({f.file for f in findings})} file(s), covering: {kinds}. "
            f"The file with the most findings is `{riskiest}` — review it first."
        )
    else:
        out.append("Nothing flagged. The added lines look clean by these checks.")
    out.append("")
    out.append(f"## Verdict: {verdict(findings)}")
    out.append("")
    return "\n".join(out)


def review_file(path: str | Path) -> str:
    """Read a diff file and return the markdown review."""
    return render_markdown(review_diff(Path(path).read_text(encoding="utf-8")))
