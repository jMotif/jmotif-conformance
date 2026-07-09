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


def load_sax_string(case: dict[str, Any], root: Path) -> str:
    if "sax_string" in case:
        return case["sax_string"].strip()
    if "sax_string_file" not in case:
        raise KeyError("case requires sax_string or sax_string_file")
    text = (root / case["sax_string_file"]).read_text(encoding="utf-8").strip()
    return " ".join(text.split())


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


def load_ucr_data(path: Path) -> dict[str, list[list[float]]]:
    data: dict[str, list[list[float]]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            parts = [p for p in line.replace(",", " ").split() if p]
            if not parts:
                continue
            label = parts[0]
            try:
                label = str(int(round(float(label))))
            except ValueError:
                pass
            values = [float(x) for x in parts[1:]]
            data.setdefault(label, []).append(values)
    return data
