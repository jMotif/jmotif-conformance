#!/usr/bin/env python3
"""Regenerate expect blocks in case JSON files from saxpy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from case_lib import load_case, repo_root  # noqa: E402

sys.path.insert(0, str(ROOT / "drivers" / "python"))
from run_case import run_case  # noqa: E402


def main() -> int:
    for case_path in sorted((repo_root() / "cases").glob("*.json")):
        case = load_case(case_path)
        result = run_case(case)
        if "discords" in result:
            case["expect"]["discords"] = result["discords"]
        if "sax_windows" in result:
            case["expect"]["sax_windows"] = result["sax_windows"]
        case["generated_by"] = "saxpy export_goldens.py"
        case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        print(f"updated {case_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
