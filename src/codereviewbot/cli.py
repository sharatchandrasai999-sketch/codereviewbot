"""Command-line interface for codereviewbot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .review import review_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codereviewbot",
        description="Review a unified diff for TODOs, hardcoded secrets, "
        "long functions, missing error handling and debug leftovers.",
    )
    parser.add_argument("diff", help="path to a unified diff (.patch) file")
    parser.add_argument("--out", help="write the markdown review to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.diff)
    if not path.is_file():
        print(f"codereviewbot: error: file not found: {args.diff}", file=sys.stderr)
        return 2
    try:
        report = review_file(path)
    except OSError as exc:
        print(f"codereviewbot: error: cannot read {args.diff}: {exc}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Review written to {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
