#!/usr/bin/env python3
"""Compare a driver result JSON object against a case expectation."""

from __future__ import annotations

import math
from typing import Any


def _close(actual: float, expected: float, tol: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tol)


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Length of the intersection of two half-open intervals (0 if disjoint)."""
    return max(0, min(a_end, b_end) - max(a_start, b_start))


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

    if "top_discord_contains_index" in expect:
        idx = expect["top_discord_contains_index"]
        tol = int(expect.get("top_discord_index_tolerance", 0))
        top = actual.get("top_discord")
        if not top:
            errors.append("missing top_discord in output")
        else:
            start = int(top["start"]) - tol
            end = int(top["end"])
            if not (start <= idx < end):
                errors.append(
                    f"top discord [{top['start']}, {top['end']}) "
                    f"does not contain index {idx} (tol={tol})"
                )

    if expect.get("hotsax_top_in_top_discord"):
        top = actual.get("top_discord")
        hot = actual.get("hotsax_top_position")
        if top is None or hot is None:
            errors.append("missing top_discord or hotsax_top_position for cross-check")
        elif not (int(top["start"]) <= int(hot) < int(top["end"])):
            errors.append(
                f"hotsax position {hot} not in top discord [{top['start']}, {top['end']})"
            )

    # RRA is tier-B: variable-length grammar-rule intervals, so exact spans are
    # not cross-checked. Instead we assert the top region lands where it should,
    # with a *substantial* overlap (a fraction of the window, not a single sample).
    window = int(case.get("params", {}).get("window", 0))
    min_frac = float(expect.get("rra_min_overlap_fraction", 0.5))

    if expect.get("rra_overlaps_hotsax_window"):
        top = actual.get("top_discord")
        hot = actual.get("hotsax_top_position")
        if top is None or hot is None or window <= 0:
            errors.append("missing top_discord, hotsax_top_position, or window for overlap check")
        else:
            ov = _overlap(int(top["start"]), int(top["end"]), int(hot), int(hot) + window)
            frac = ov / window
            if frac < min_frac:
                errors.append(
                    f"RRA span [{top['start']}, {top['end']}) overlaps HOT-SAX window "
                    f"[{hot}, {int(hot) + window}) by {ov}/{window}={frac:.2f} < {min_frac}"
                )

    if "rra_ground_truth" in expect:
        gt = expect["rra_ground_truth"]
        top = actual.get("top_discord")
        gt_frac = float(gt.get("min_overlap_fraction", min_frac))
        if top is None or window <= 0:
            errors.append("missing top_discord or window for ground-truth check")
        else:
            ov = _overlap(int(top["start"]), int(top["end"]), int(gt["start"]), int(gt["end"]))
            frac = ov / window
            if frac < gt_frac:
                errors.append(
                    f"RRA span [{top['start']}, {top['end']}) overlaps ground-truth region "
                    f"[{gt['start']}, {gt['end']}) by {ov}/{window}={frac:.2f} < {gt_frac}"
                )

    return errors


def verify_consensus(
    results: dict[str, dict[str, Any]],
    case: dict[str, Any],
    attempted: list[str],
) -> list[str]:
    """Cross-language checks that need every aligned implementation's output.

    For RRA (tier-B) we require the top discord regions found by each language to
    mutually overlap by a fraction of the window, so agreement is asserted between
    implementations directly, not only against each one's own HOT-SAX anchor.

    ``attempted`` is the list of implementations the harness actually ran for this
    case (aligned impls, filtered by any ``--impl`` selection). Consensus only
    applies when at least two of them ran; when it applies, EVERY participant must
    contribute a well-formed ``top_discord`` -- a missing or malformed span is a
    consensus failure, not a silent pass, so a partial run can never claim
    cross-language agreement.
    """
    expect = case.get("expect", {})
    frac = expect.get("rra_consensus_min_fraction")
    if frac is None:
        return []
    frac = float(frac)
    aligned = case.get("aligned", attempted)
    participants = [impl for impl in attempted if impl in aligned]
    if len(participants) < 2:
        # cross-language consensus is not meaningful with fewer than two impls
        return []
    window = int(case.get("params", {}).get("window", 0))
    if window <= 0:
        return [f"consensus: window <= 0 ({window}), cannot compute overlap"]

    errors: list[str] = []
    spans: dict[str, dict[str, Any]] = {}
    for impl in participants:
        r = results.get(impl)
        top = r.get("top_discord") if isinstance(r, dict) else None
        if not isinstance(top, dict) or "start" not in top or "end" not in top:
            errors.append(f"consensus: missing/malformed top_discord for aligned impl '{impl}'")
            continue
        spans[impl] = top
    if errors:
        # cannot assert consensus unless every participating impl produced a span
        return errors

    impls = sorted(spans)
    for i in range(len(impls)):
        for j in range(i + 1, len(impls)):
            a, b = spans[impls[i]], spans[impls[j]]
            ov = _overlap(int(a["start"]), int(a["end"]), int(b["start"]), int(b["end"]))
            f = ov / window
            if f < frac:
                errors.append(
                    f"{impls[i]} [{a['start']}, {a['end']}) vs {impls[j]} "
                    f"[{b['start']}, {b['end']}) overlap {ov}/{window}={f:.2f} < {frac}"
                )
    return errors
