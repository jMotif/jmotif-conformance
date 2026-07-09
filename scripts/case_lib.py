#!/usr/bin/env python3
"""Shared helpers for loading conformance cases and series."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_case(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_series(case: dict[str, Any], root: Path) -> list[float]:
    series_path = root / case["series"]
    values: list[float] = []
    with series_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            values.append(float(line.split(",")[0]))
    start, end = case.get("slice", [0, None])
    if end is None:
        end = len(values)
    return values[start:end]


def nr_strategy_python(value: str) -> str | None:
    if value.upper() == "NONE":
        return None
    return value.lower()


def nr_strategy_r(value: str) -> str:
    return value.lower()


def nr_strategy_java(value: str) -> str:
    return value.upper()
