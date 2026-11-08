# codereviewbot

A small rule-based PR review helper. Give it a unified diff and it flags
things a reviewer would want to look at — no LLM, no API keys, no network.

## What it flags (added lines only)

- **Hardcoded secrets** (high severity): `api_key = "..."`, `password = "..."`,
  AWS keys (`AKIA...`), `sk-...` tokens, private key blocks.
- **TODO / FIXME / XXX** comments.
- **Long functions**: a crude heuristic — an added `def` followed by more
  than 40 added lines before the next `def` or end of file. It counts added
  lines only, so it is a nudge, not a measurement; genuinely long functions
  split across hunks can be missed.
- **Missing error handling**: an added `open(` or `requests.` call in a hunk
  with no `try`/`except` in the same hunk.
- **Debug leftovers**: `print(`, `console.log`, `pdb`, `breakpoint(`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
codereviewbot examples/sample.patch
codereviewbot mychange.patch --out review.md
```

Default output goes to stdout; `--out` writes a markdown file instead.
A missing diff file exits with code 2 and a plain error message.

## Example output

```markdown
# Code Review

## Findings

4 finding(s): debug (1), long-function (1), secret (2), todo (1).

### `src/auth.py`

- Line 4 [high] **secret**: hardcoded api_key
- Line 4 [high] **secret**: API key starting with sk-
- Line 4 [medium] **todo**: TODO comment left in code
- Line 5 [medium] **debug**: print() leftover

### `src/utils.py`

- Line 3 [medium] **long-function**: function 'process_records' has ~51 added lines (over the 40-line heuristic)

## Summary (template, no LLM call)

This diff adds 5 flagged item(s) across 2 file(s), covering: debug, long-function, secret, todo. The file with the most findings is `src/auth.py` — review it first.

## Verdict: REQUEST CHANGES
```

The "Summary" section is a deterministic template that counts findings by
type and names the riskiest file. **There is no LLM call anywhere in this
project** — the summary is filled in from the findings list, and it says so
in the output.

The verdict is `APPROVE` when there are no high-severity findings and
`REQUEST CHANGES` when a secret (or any other high-severity finding) is present.

## Tests

```bash
python -m pytest
```
