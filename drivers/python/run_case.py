#!/usr/bin/env python3
"""Run one conformance case with the saxpy reference implementation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from case_lib import load_case, load_sax_string, load_series, load_ucr_data, nr_strategy_python, repo_root  # noqa: E402
from repair_lib import normalize_repair_output  # noqa: E402


def run_repair(sax_string: str) -> dict:
    from saxpy.repair import str_to_repair_grammar

    grammar = str_to_repair_grammar(sax_string)
    rules = []
    for rid in sorted(grammar.keys()):
        rule = grammar[rid]
        rules.append(
            {
                "rule_id": int(rid),
                "rule_string": rule.rule_string,
                "expanded_rule_string": rule.expanded_rule_string,
            }
        )
    return normalize_repair_output(
        {
            "input": sax_string,
            "r0_rule_string": grammar[0].rule_string,
            "rules": rules,
        }
    )


def run_case(case: dict) -> dict:
    import numpy as np
    from saxpy.discord import find_discords_brute_force
    from saxpy.hotsax import find_discords_hotsax
    from saxpy.sax import sax_via_window

    op = case["operation"]
    params = case.get("params", {})

    if op == "repair":
        return run_repair(load_sax_string(case, repo_root()))

    if op == "saxvsm_classify":
        from saxpy.saxvsm import classify_series, train_tfidf

        train = {
            label: [np.asarray(series, dtype=float) for series in series_list]
            for label, series_list in load_ucr_data(repo_root() / case["train"]).items()
        }
        test = load_ucr_data(repo_root() / case["test"])
        tfidf = train_tfidf(
            train,
            params["window"],
            params["paa"],
            params["alphabet"],
            nr_strategy=nr_strategy_python(params["nr_strategy"]),
            znorm_threshold=params["threshold"],
        )
        correct = 0
        total = 0
        for true_label, series_list in test.items():
            for series in series_list:
                total += 1
                predicted = classify_series(
                    np.asarray(series, dtype=float),
                    tfidf,
                    params["window"],
                    params["paa"],
                    params["alphabet"],
                    nr_strategy=nr_strategy_python(params["nr_strategy"]),
                    znorm_threshold=params["threshold"],
                )
                if predicted == true_label:
                    correct += 1
        accuracy = correct / total if total else 0.0
        return {
            "accuracy": accuracy,
            "error": 1.0 - accuracy,
            "correct": correct,
            "total": total,
        }

    if op == "rra_discord":
        from saxpy.hotsax import find_discords_hotsax
        from saxpy.rra import find_discords_rra

        series = np.asarray(load_series(case, repo_root()), dtype=float)
        discords = find_discords_rra(
            series,
            params["window"],
            params["paa"],
            params["alphabet"],
            nr_strategy=nr_strategy_python(params["nr_strategy"]),
            znorm_threshold=params["threshold"],
            num_discords=params["num_discords"],
            random_state=params.get("seed", 0),
        )
        if not discords:
            raise RuntimeError("RRA found no discords")
        top = discords[0]
        hot = find_discords_hotsax(
            series,
            win_size=params["window"],
            num_discords=1,
            paa_size=params["paa"],
            alphabet_size=params["alphabet"],
            znorm_threshold=params["threshold"],
        )
        return {
            "top_discord": {"start": int(top.start), "end": int(top.end)},
            "hotsax_top_position": int(hot[0][0]),
        }

    series = np.asarray(load_series(case, repo_root()), dtype=float)

    if op == "discord_bruteforce":
        rows = find_discords_brute_force(
            series,
            params["window"],
            params["num_discords"],
            znorm_threshold=params["threshold"],
        )
        return {
            "discords": [
                {"position": int(pos), "nn_distance": float(dist)} for pos, dist in rows
            ]
        }

    if op == "discord_hotsax":
        rows = find_discords_hotsax(
            series,
            win_size=params["window"],
            num_discords=params["num_discords"],
            paa_size=params["paa"],
            alphabet_size=params["alphabet"],
            znorm_threshold=params["threshold"],
        )
        return {
            "discords": [
                {"position": int(pos), "nn_distance": float(dist)} for pos, dist in rows
            ]
        }

    if op == "sax_via_window":
        sax = sax_via_window(
            series,
            win_size=params["window"],
            paa_size=params["paa"],
            alphabet_size=params["alphabet"],
            nr_strategy=nr_strategy_python(params["nr_strategy"]),
            znorm_threshold=params["threshold"],
        )
        windows = []
        for index in params["pinned_indices"]:
            word = None
            for candidate, indices in sax.items():
                if index in indices:
                    word = candidate
                    break
            if word is None:
                raise RuntimeError(f"no SAX word at index {index}")
            windows.append({"index": int(index), "word": word})
        return {"sax_windows": windows}

    raise ValueError(f"unsupported operation: {op}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_file", type=Path)
    args = parser.parse_args()
    case = load_case(args.case_file)
    print(json.dumps(run_case(case), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
