#!/usr/bin/env python3
"""Flag hedging and legacy phrasing in jMotif stack READMEs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

README_PATHS = [
    REPO_ROOT / "saxpy" / "README.md",
    REPO_ROOT / "jmotif-R" / "README.md",
    REPO_ROOT / "jmotif-java" / "README.md",
    REPO_ROOT / "GI" / "README.md",
    REPO_ROOT / "grammarviz2_src" / "README.md",
    REPO_ROOT / "sax-vsm_classic" / "README.md",
    ROOT / "README.md",
    REPO_ROOT / "grammarviz2_site" / "README.md",
    REPO_ROOT / "sax-vsm_site" / "README.md",
]

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("hedging heading", re.compile(r"plausible explanation", re.I)),
    ("Note that", re.compile(r"\bNote,? that\b")),
    ("simply (weak)", re.compile(r"\bsimply\b", re.I)),
    ("I guess", re.compile(r"\bI guess\b", re.I)),
    ("as well...", re.compile(r"as well\.\.\.")),
    ("informative, not conformance", re.compile(r"informative, not conformance", re.I)),
]


def main() -> int:
    failures: list[str] = []
    for path in README_PATHS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path.name
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{rel}:{line}: {label}: {match.group(0)!r}")
    if failures:
        print("README tone check failed:\n", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print("README tone check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
