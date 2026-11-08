"""codereviewbot — rule-based PR review helper for unified diffs."""

__version__ = "0.1.0"

from .review import Finding, render_markdown, review_diff, review_file, verdict

__all__ = ["Finding", "render_markdown", "review_diff", "review_file", "verdict", "__version__"]
