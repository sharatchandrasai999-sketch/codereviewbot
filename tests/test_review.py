"""Tests for codereviewbot."""

from pathlib import Path

import pytest

from codereviewbot.cli import main
from codereviewbot.review import render_markdown, review_diff, verdict

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample.patch"


def diff_for(body: str, filename: str = "src/app.py") -> str:
    """Wrap added lines in a minimal unified diff."""
    lines = "\n".join(f"+{line}" if line else "+" for line in body.splitlines())
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"--- a/{filename}\n"
        f"+++ b/{filename}\n"
        "@@ -1,1 +1,99 @@\n"
        " context\n"
        f"{lines}\n"
    )


def test_todo_is_flagged():
    findings = review_diff(diff_for('    # TODO: handle empty input\n    x = 1'))
    assert any(f.kind == "todo" for f in findings)


def test_hardcoded_api_key_is_high_severity():
    findings = review_diff(diff_for('    api_key = "abc123secret"'))
    secrets = [f for f in findings if f.kind == "secret"]
    assert secrets
    assert all(f.severity == "high" for f in secrets)


def test_clean_diff_approves_with_no_findings():
    findings = review_diff(diff_for("    x = 1\n    return x"))
    assert findings == []
    assert verdict(findings) == "APPROVE"


def test_secret_forces_request_changes():
    findings = review_diff(diff_for('    password = "hunter2"'))
    assert verdict(findings) == "REQUEST CHANGES"


def test_long_function_is_flagged():
    body = "def big():\n" + "\n".join(f"    step_{i} = {i}" for i in range(45))
    findings = review_diff(diff_for(body))
    assert any(f.kind == "long-function" for f in findings)


def test_open_without_try_is_flagged_but_guarded_is_not():
    unguarded = review_diff(diff_for('    data = open("notes.txt").read()'))
    assert any(f.kind == "error-handling" for f in unguarded)
    guarded = review_diff(
        diff_for(
            "    try:\n"
            '        data = open("notes.txt").read()\n'
            "    except OSError:\n"
            "        data = ''"
        )
    )
    assert not any(f.kind == "error-handling" for f in guarded)


def test_print_leftover_is_flagged():
    findings = review_diff(diff_for('    print("debug")'))
    assert any(f.kind == "debug" for f in findings)


def test_missing_diff_file_errors_cleanly(capsys):
    assert main(["does-not-exist.patch"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_out_writes_file_with_verdict(tmp_path):
    out = tmp_path / "review.md"
    assert main([str(SAMPLE), "--out", str(out)]) == 0
    text = out.read_text()
    assert "## Verdict: REQUEST CHANGES" in text
    assert "secret" in text
    assert "todo" in text


def test_sample_patch_demonstrates_findings():
    findings = review_diff(SAMPLE.read_text())
    kinds = {f.kind for f in findings}
    assert {"todo", "secret", "long-function", "debug"} <= kinds
    assert verdict(findings) == "REQUEST CHANGES"


def test_render_marks_summary_as_template():
    text = render_markdown(review_diff(diff_for('    # FIXME: later\n    x = 1')))
    assert "template, no LLM call" in text
    assert "## Verdict: APPROVE" in text
