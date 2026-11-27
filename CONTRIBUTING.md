# Contributing

Thanks for helping. Rule-based PR review helper that flags TODOs, hardcoded secrets, long functions, missing error handling and debug leftovers in unified diffs. This is a small, personal project, so keep changes small and easy to review.

## Before you send a change

- Run the tests from any folder: `pytest -q` (tests must not depend on the current working directory)
- Keep the offline path working: reviewing a local diff file must need no API key and no download.
- If you add a check, ship a sample diff that exercises it.

## Reporting a problem

Open an issue and include:

- The exact command you ran
- The input file, if it is about one
- What happened, and what you expected instead

Do not include API keys, private documents, or personal details.
