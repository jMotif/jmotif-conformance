#!/usr/bin/env python3
"""Run every conformance case against every aligned implementation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from case_lib import load_case, repo_root  # noqa: E402
from verify_output import verify, verify_consensus  # noqa: E402


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"')
    return env


def java_rra_args(case: dict, root: Path) -> list[str]:
    params = case.get("params", {})
    args = [
        "java",
        "-Dorg.slf4j.simpleLogger.defaultLogLevel=off",
        "-cp",
        os.environ["JAVA_RRA_CLASSPATH"],
        "RRAConformanceRunner",
        "--repo-root",
        str(root),
        "--series",
        case["series"],
    ]
    start, end = case.get("slice", [0, None])
    args.extend(["--slice-start", str(start)])
    if end is not None:
        args.extend(["--slice-end", str(end)])
    args.extend(
        [
            "--window",
            str(params["window"]),
            "--paa",
            str(params["paa"]),
            "--alphabet",
            str(params["alphabet"]),
            "--num-discords",
            str(params["num_discords"]),
            "--threshold",
            str(params["threshold"]),
            "--nr-strategy",
            params["nr_strategy"],
            "--seed",
            str(params.get("seed", 0)),
        ]
    )
    return args


def java_saxvsm_args(case: dict, root: Path) -> list[str]:
    params = case.get("params", {})
    return [
        "java",
        "-cp",
        os.environ["JAVA_SAXVSM_CLASSPATH"],
        "net.seninp.jmotif.SaxVSMConformanceRunner",
        "--repo-root",
        str(root),
        "--train",
        case["train"],
        "--test",
        case["test"],
        "--window",
        str(params["window"]),
        "--paa",
        str(params["paa"]),
        "--alphabet",
        str(params["alphabet"]),
        "--threshold",
        str(params["threshold"]),
        "--nr-strategy",
        params["nr_strategy"],
    ]


def java_args(case: dict, root: Path) -> list[str]:
    if case["operation"] == "saxvsm_classify":
        return java_saxvsm_args(case, root)
    if case["operation"] == "rra_discord":
        return java_rra_args(case, root)

    params = case.get("params", {})
    args = [
        "java",
        "-Dorg.slf4j.simpleLogger.defaultLogLevel=off",
        "-cp",
        os.environ["JMOTIF_JAVA_CLASSPATH"],
        "ConformanceRunner",
        case["operation"],
        "--repo-root",
        str(root),
    ]
    if case["operation"] == "repair":
        args.extend(["--sax-string-file", case["sax_string_file"]])
        return args

    args.extend(["--series", case["series"]])
    start, end = case.get("slice", [0, None])
    args.extend(["--slice-start", str(start)])
    if end is not None:
        args.extend(["--slice-end", str(end)])
    if case["operation"] in {"discord_bruteforce", "discord_hotsax", "sax_via_window"}:
        args.extend(["--window", str(params["window"])])
    if case["operation"] in {"discord_hotsax", "sax_via_window"}:
        args.extend(["--paa", str(params["paa"]), "--alphabet", str(params["alphabet"])])
    if case["operation"] in {"discord_bruteforce", "discord_hotsax"}:
        args.extend(
            ["--num-discords", str(params["num_discords"]), "--threshold", str(params["threshold"])]
        )
    if case["operation"] == "sax_via_window":
        args.extend(
            [
                "--threshold",
                str(params["threshold"]),
                "--nr-strategy",
                params["nr_strategy"],
                "--pinned-indices",
                json.dumps(params["pinned_indices"]),
            ]
        )
    if case["operation"] == "discord_hotsax":
        args.append("--nr-strategy")
        args.append(params["nr_strategy"])
    return args


def run_impl(name: str, case_path: Path, case: dict, root: Path) -> dict:
    env = os.environ.copy()
    env["JMOTIF_CONFORMANCE_ROOT"] = str(root)
    if name == "python":
        python_bin = env.get("PYTHON_BIN", sys.executable)
        cmd = [python_bin, str(root / "drivers/python/run_case.py"), str(case_path)]
    elif name == "r":
        cmd = ["Rscript", str(root / "drivers/r/run_case.R"), str(case_path)]
        if "R_LIBS_USER" in env:
            env["R_LIBS"] = env["R_LIBS_USER"]
    elif name == "java":
        cmd = java_args(case, root)
    else:
        raise ValueError(name)
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env, cwd=root)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{name} failed ({proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    stdout = proc.stdout.strip()
    if name == "java":
        start = stdout.find("{")
        if start < 0:
            raise RuntimeError(f"java output missing JSON:\n{stdout}")
        stdout = stdout[start:]
    return json.loads(stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--impl",
        choices=["java", "r", "python", "all"],
        default="all",
        help="implementation to run",
    )
    parser.add_argument("--case", type=Path, help="single case file")
    args = parser.parse_args()

    pin = load_env(ROOT / "scripts" / "pin_versions.env")
    local = load_env(ROOT / "scripts" / ".env.local")
    os.environ.update(pin)
    os.environ.update(local)
    if args.impl in {"java", "all"} and "JMOTIF_JAVA_CLASSPATH" not in os.environ:
        print("JMOTIF_JAVA_CLASSPATH is not set; run scripts/bootstrap.sh first", file=sys.stderr)
        return 2
    if args.impl in {"java", "all"} and "JAVA_SAXVSM_CLASSPATH" not in os.environ:
        print("JAVA_SAXVSM_CLASSPATH is not set; run scripts/bootstrap.sh first", file=sys.stderr)
        return 2
    if args.impl in {"java", "all"} and "JAVA_RRA_CLASSPATH" not in os.environ:
        print("JAVA_RRA_CLASSPATH is not set; run scripts/bootstrap.sh first", file=sys.stderr)
        return 2

    root = repo_root()
    if args.case:
        case_paths = [args.case]
    else:
        case_paths = sorted(
            p for p in (root / "cases").glob("*.json") if not p.name.startswith("bench_")
        )
    impls = ["java", "r", "python"] if args.impl == "all" else [args.impl]

    failures = 0
    for case_path in case_paths:
        case = load_case(case_path)
        aligned = case.get("aligned", impls)
        results: dict[str, dict] = {}
        for impl in impls:
            if impl not in aligned:
                continue
            print(f"CASE {case['id']} IMPL {impl} ... ", end="", flush=True)
            try:
                actual = run_impl(impl, case_path, case, root)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FAIL")
                print(f"  {exc}")
                continue
            results[impl] = actual
            errors = verify(actual, case)
            if errors:
                failures += 1
                print("FAIL")
                for err in errors:
                    print(f"  {err}")
            else:
                print("OK")

        # Cross-language checks that compare implementations against each other.
        # Run whenever the case expects consensus and at least two aligned impls were
        # attempted, so a crashed/missing impl surfaces as a consensus FAIL rather than a
        # silent OK on the survivors.
        attempted = [impl for impl in impls if impl in aligned]
        expects_consensus = case.get("expect", {}).get("rra_consensus_min_fraction") is not None
        if expects_consensus and len(attempted) > 1:
            consensus_errors = verify_consensus(results, case, attempted)
            if consensus_errors:
                failures += 1
                print(f"CASE {case['id']} CONSENSUS ... FAIL")
                for err in consensus_errors:
                    print(f"  {err}")
            else:
                print(f"CASE {case['id']} CONSENSUS ... OK")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
