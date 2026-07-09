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

    if "r0_rule_string" in expect:
        got = actual.get("r0_rule_string")
        if got != expect["r0_rule_string"]:
            errors.append(f"r0_rule_string {got!r} != {expect['r0_rule_string']!r}")

    if "rules" in expect:
        got = {item["rule_id"]: item for item in actual.get("rules", [])}
        for want in expect["rules"]:
            rid = want["rule_id"]
            rule = got.get(rid)
            if rule is None:
                errors.append(f"missing rule_id {rid}")
                continue
            if "expanded_rule_string" in want and rule.get("expanded_rule_string") != want[
                "expanded_rule_string"
            ]:
                errors.append(
                    f"rule {rid} expanded {rule.get('expanded_rule_string')!r} "
                    f"!= {want['expanded_rule_string']!r}"
                )
            if "rule_string" in want and rule.get("rule_string") != want["rule_string"]:
                errors.append(
                    f"rule {rid} rule_string {rule.get('rule_string')!r} "
                    f"!= {want['rule_string']!r}"
                )

    if expect.get("decompress_equals_input"):
        if actual.get("decompressed") != actual.get("input"):
            errors.append("decompressed string != input")

    if expect.get("r0_no_repeated_digram") and not actual.get("r0_no_repeated_digram"):
        errors.append("R0 contains a repeated digram")

    if "accuracy" in expect:
        tol = expect.get("tolerance", {}).get("accuracy", 1e-12)
        for key in ("accuracy", "error"):
            if key in expect and not _close(float(actual.get(key, -1)), float(expect[key]), tol):
                errors.append(f"{key} {actual.get(key)!r} != {expect[key]!r} (tol={tol})")
        for key in ("correct", "total"):
            if key in expect and actual.get(key) != expect[key]:
                errors.append(f"{key} {actual.get(key)!r} != {expect[key]!r}")

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
