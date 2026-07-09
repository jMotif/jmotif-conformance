#!/usr/bin/env python3
"""Shared RePair helpers for conformance drivers and verification."""

from __future__ import annotations

from collections import Counter
from typing import Any


def decompress_r0(r0_rule_string: str, rules_by_id: dict[int, dict[str, str]]) -> str:
    """Expand R0 using each rule's expanded_rule_string."""
    text = r0_rule_string
    while "R" in text:
        tokens = text.split(" ")
        out: list[str] = []
        changed = False
        for tok in tokens:
            if tok.startswith("R") and tok[1:].isdigit():
                rid = int(tok[1:])
                rule = rules_by_id.get(rid)
                if rule is not None and rid != 0:
                    out.append(rule["expanded_rule_string"])
                    changed = True
                    continue
            out.append(tok)
        new_text = " ".join(out)
        if new_text == text:
            break
        text = new_text
        if not changed:
            break
    return text


def r0_no_repeated_digram(r0_rule_string: str) -> bool:
    tokens = r0_rule_string.split()
    if len(tokens) < 2:
        return True
    counts = Counter((tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1))
    return all(count <= 1 for count in counts.values())


def normalize_repair_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure rules are sorted and derived fields are present."""
    rules = sorted(payload.get("rules", []), key=lambda item: item["rule_id"])
    rules_by_id = {item["rule_id"]: item for item in rules}
    r0 = rules_by_id.get(0, {})
    r0_rule_string = payload.get("r0_rule_string", r0.get("rule_string", "")).strip()
    input_text = payload["input"].strip()
    decompressed = payload.get("decompressed")
    if decompressed is None:
        decompressed = r0.get("expanded_rule_string") or decompress_r0(r0_rule_string, rules_by_id)
    decompressed = decompressed.strip()
    return {
        "input": input_text,
        "r0_rule_string": r0_rule_string,
        "rules": rules,
        "decompressed": decompressed,
        "r0_no_repeated_digram": payload.get(
            "r0_no_repeated_digram", r0_no_repeated_digram(r0_rule_string)
        ),
    }
