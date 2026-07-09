#!/usr/bin/env python3
"""Compare a driver result JSON object against a case expectation."""

from __future__ import annotations

import math
from typing import Any


def _close(actual: float, expected: float, tol: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tol)


def verify(actual: dict[str, Any], case: dict[str, Any]) -> list[str]:
    expect = case["expect"]
    errors: list[str] = []

    if "discords" in expect:
        tol = expect.get("tolerance", {}).get("nn_distance", 1e-6)
        got = actual.get("discords", [])
        want = expect["discords"]
        if len(got) != len(want):
            errors.append(f"discord count {len(got)} != {len(want)}")
            return errors
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            if g["position"] != w["position"]:
                errors.append(f"discord[{i}] position {g['position']} != {w['position']}")
            if not _close(float(g["nn_distance"]), float(w["nn_distance"]), tol):
                errors.append(
                    f"discord[{i}] distance {g['nn_distance']} != {w['nn_distance']} (tol={tol})"
                )

    if "sax_windows" in expect:
        got = {item["index"]: item["word"] for item in actual.get("sax_windows", [])}
        for item in expect["sax_windows"]:
            index = item["index"]
            word = got.get(index)
            if word != item["word"]:
                errors.append(f"sax index {index}: {word!r} != {item['word']!r}")

    return errors
