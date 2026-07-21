"""Unit tests for the RRA tier-B checks in scripts/verify_output.py.

These exercise the interval math and the cross-language consensus rules directly,
without needing a bootstrapped Java/R/Python stack, so a regression in the harness
logic is caught fast (the full run_all suite still validates end-to-end).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_output import _overlap, verify, verify_consensus  # noqa: E402


def _rra_case(window: int = 100) -> dict:
    return {
        "params": {"window": window},
        "aligned": ["java", "r", "python"],
        "expect": {
            "rra_overlaps_hotsax_window": True,
            "rra_min_overlap_fraction": 0.5,
            "rra_ground_truth": {"start": 400, "end": 560},
            "rra_consensus_min_fraction": 0.5,
        },
    }


def _span(start: int, end: int) -> dict:
    return {"top_discord": {"start": start, "end": end}, "hotsax_top_position": 430}


# --- _overlap (half-open intervals) -------------------------------------------------


def test_overlap_basic():
    assert _overlap(0, 10, 5, 15) == 5
    assert _overlap(430, 531, 430, 530) == 100


def test_overlap_disjoint_and_adjacent():
    assert _overlap(0, 10, 10, 20) == 0  # adjacent, half-open -> no overlap
    assert _overlap(0, 10, 20, 30) == 0
    assert _overlap(30, 40, 0, 10) == 0


# --- verify(): per-impl RRA region checks -------------------------------------------


def test_verify_rra_pass():
    case = _rra_case()
    # span [430,531): hotsax window [430,530) overlap 100/100; GT [400,560) overlap 101/100
    assert verify(_span(430, 531), case) == []


def test_verify_rra_hotsax_below_threshold_fails():
    case = _rra_case()
    # only 40 of the window overlaps the hotsax window [430,530)
    errs = verify({"top_discord": {"start": 490, "end": 800}, "hotsax_top_position": 430}, case)
    assert any("HOT-SAX" in e for e in errs), errs


def test_verify_rra_ground_truth_miss_fails():
    case = _rra_case()
    # far away from GT [400,560) and from hotsax window
    errs = verify({"top_discord": {"start": 2000, "end": 2101}, "hotsax_top_position": 2000}, case)
    assert any("ground-truth" in e for e in errs), errs


# --- verify_consensus(): cross-language rules ---------------------------------------


def test_consensus_all_present_ok():
    case = _rra_case()
    results = {"java": _span(431, 532), "r": _span(430, 531), "python": _span(430, 531)}
    assert verify_consensus(results, case, ["java", "r", "python"]) == []


def test_consensus_missing_aligned_impl_fails():
    """A partial run must NOT silently pass on the survivors."""
    case = _rra_case()
    results = {"r": _span(430, 531), "python": _span(430, 531)}  # java missing
    errs = verify_consensus(results, case, ["java", "r", "python"])
    assert any("missing/malformed" in e and "java" in e for e in errs), errs


def test_consensus_single_impl_skipped():
    """With <2 aligned impls attempted, cross-language consensus does not apply."""
    case = _rra_case()
    assert verify_consensus({"java": _span(430, 531)}, case, ["java"]) == []


def test_consensus_malformed_span_reports_error_no_crash():
    case = _rra_case()
    results = {
        "java": {"top_discord": {"start": 430}},  # missing 'end'
        "r": _span(430, 531),
        "python": _span(430, 531),
    }
    errs = verify_consensus(results, case, ["java", "r", "python"])
    assert any("missing/malformed" in e for e in errs), errs


def test_consensus_divergent_regions_fail():
    case = _rra_case()
    results = {
        "java": _span(2000, 2100),  # different region
        "r": _span(430, 531),
        "python": _span(430, 531),
    }
    errs = verify_consensus(results, case, ["java", "r", "python"])
    assert any("overlap" in e for e in errs), errs


def test_consensus_absent_when_key_unset():
    case = _rra_case()
    del case["expect"]["rra_consensus_min_fraction"]
    results = {"java": _span(2000, 2100), "r": _span(430, 531), "python": _span(430, 531)}
    assert verify_consensus(results, case, ["java", "r", "python"]) == []


def test_consensus_case_aligned_to_two_langs_ok():
    """A case aligned to only two languages checks consensus across exactly those two."""
    case = _rra_case()
    case["aligned"] = ["r", "python"]
    results = {"r": _span(430, 531), "python": _span(431, 532)}
    assert verify_consensus(results, case, ["r", "python"]) == []


def test_consensus_window_zero_reports_error():
    """A non-positive window is a misconfiguration and must fail loudly, not skip."""
    case = _rra_case(window=0)
    results = {"java": _span(430, 531), "r": _span(430, 531), "python": _span(430, 531)}
    errs = verify_consensus(results, case, ["java", "r", "python"])
    assert any("window" in e for e in errs), errs
