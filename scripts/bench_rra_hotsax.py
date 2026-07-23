#!/usr/bin/env python3
"""Run RRA vs HOT-SAX wall-clock benchmark and optionally refresh README tables."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "scripts" / ".env.local"
CASES_FILE = ROOT / "cases" / "bench_rra_hotsax.json"
README = ROOT / "README.md"
MARKER_START = "<!-- bench-rra-hotsax:start -->"
MARKER_END = "<!-- bench-rra-hotsax:end -->"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key] = value
    return env


def resolve_bench_classpath(env: dict[str, str]) -> str:
    if env.get("JAVA_BENCH_CLASSPATH"):
        return env["JAVA_BENCH_CLASSPATH"]
    jar = env.get("GRAMMARVIZ_JAR")
    if jar and Path(jar).is_file():
        return f"{jar}:{ROOT / 'drivers' / 'java'}"
    gv_dir = env.get("GRAMMARVIZ_DIR")
    if gv_dir:
        candidates = sorted(Path(gv_dir).glob("target/grammarviz2-*-jar-with-dependencies.jar"))
        if candidates:
            return f"{candidates[-1]}:{ROOT / 'drivers' / 'java'}"
    raise SystemExit("missing GrammarViz jar — run ./scripts/bootstrap.sh first")


def compile_driver(env: dict[str, str]) -> str:
    classpath = resolve_bench_classpath(env)
    grammarviz_jar = classpath.split(":", 1)[0]
    driver = ROOT / "drivers" / "java" / "RRAvsHotsaxBench.java"
    out_dir = ROOT / "drivers" / "java"
    subprocess.run(
        ["javac", "-cp", grammarviz_jar, "-d", str(out_dir), str(driver)],
        check=True,
    )
    return classpath


def run_case(env: dict[str, str], case: dict, classpath: str) -> dict:
    cmd = [
        "java",
        "-Dorg.slf4j.simpleLogger.defaultLogLevel=warn",
        "-cp",
        classpath,
        "RRAvsHotsaxBench",
        "--repo-root",
        str(ROOT),
        "--group",
        case["group"],
        "--label",
        case["label"],
        "--dataset",
        case["dataset"],
        "--window",
        str(case["window"]),
        "--paa",
        str(case["paa"]),
        "--alphabet",
        str(case["alphabet"]),
        "--k",
        str(case.get("k", 1)),
        "--seed",
        str(case.get("seed", 0)),
    ]
    if case.get("tile_length"):
        cmd.extend(["--tile-length", str(case["tile_length"])])
    if case.get("tile_drift"):
        cmd.append("--tile-drift")

    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"no JSON result in stdout:\n{proc.stdout}\n{proc.stderr}")


def format_ms(ms: int) -> str:
    if ms >= 10_000:
        return f"{ms / 1000:.1f} s"
    return f"{ms} ms"


def format_ratio(ratio: float, hs_ms: int, hs_disc: int, rr_disc: int) -> str:
    if hs_disc == 0 or rr_disc == 0:
        return "n/a"
    if ratio < 1.0:
        return f"**{ratio:.2f}× faster**"
    return f"{ratio:.2f}× slower"


def render_table(title: str, rows: list[dict], *, long_table: bool) -> str:
    lines = [f"**{title}**", ""]
    if long_table:
        lines.extend(
            [
                "| Series | `n` | HOT-SAX | RRA | RRA / HOT-SAX |",
                "|--------|-----|---------|-----|---------------|",
            ]
        )
        for row in rows:
            lines.append(
                "| {label} | {n:,} | {hs} | {rr} | {ratio} |".format(
                    label=row["label"],
                    n=row["n"],
                    hs=format_ms(row["hotsax_ms"]),
                    rr=format_ms(row["rra_ms"]),
                    ratio=format_ratio(
                        row["ratio"], row["hotsax_ms"], row["hotsax_discords"], row["rra_discords"]
                    ),
                )
            )
    else:
        lines.extend(
            [
                "| Parameters | HOT-SAX | RRA | RRA / HOT-SAX |",
                "|------------|---------|-----|---------------|",
            ]
        )
        for row in rows:
            lines.append(
                "| `{label}` | {hs} | {rr} | {ratio} |".format(
                    label=row["label"],
                    hs=format_ms(row["hotsax_ms"]),
                    rr=format_ms(row["rra_ms"]),
                    ratio=format_ratio(
                        row["ratio"], row["hotsax_ms"], row["hotsax_discords"], row["rra_discords"]
                    ),
                )
            )
    lines.append("")
    return "\n".join(lines)


def render_section(results: list[dict], env: dict[str, str]) -> str:
    meta = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    short_rows = [r for r in results if r["group"] == "short"]
    long_rows = [r for r in results if r["group"] == "long"]

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    gv = Path(env.get("GRAMMARVIZ_DIR", "grammarviz2_src")).name
    sax = Path(env.get("JMOTIF_JAVA_DIR", "SAX")).name

    parts = [
        f"_Generated {stamp} by `./scripts/bench_rra_hotsax.sh --update-readme` "
        f"(GrammarViz `{gv}`, jmotif-sax `{sax}`, `k=1`, `seed=0`, NR=`NONE`, z=`0.01`)._",
        "",
        render_table("Short series (ecg0606, `n = 2,299`)", short_rows, long_table=False),
        render_table("Longer ECG-like series (`w=100, p=4, a=4`)", long_rows, long_table=True),
        "Ratios **below 1.0×** (shown as “faster”) mean RRA had lower wall-clock on that row.",
        "",
    ]
    return "\n".join(parts)


def patch_readme(section: str) -> bool:
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    replacement = f"{MARKER_START}\n{section.rstrip()}\n{MARKER_END}"
    if not pattern.search(text):
        raise SystemExit(f"README markers not found: {MARKER_START} … {MARKER_END}")
    new_text = pattern.sub(replacement, text, count=1)
    if new_text == text:
        return False
    README.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="rewrite the bench-rra-hotsax block in README.md",
    )
    parser.add_argument(
        "--check-readme",
        action="store_true",
        help="exit 1 if README bench block would change (CI-friendly)",
    )
    args = parser.parse_args()

    cases_doc = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    runs = cases_doc["runs"]
    for run in runs:
        run.setdefault("k", cases_doc.get("k", 1))
        run.setdefault("seed", cases_doc.get("seed", 0))

    env = load_env()
    if not env.get("GRAMMARVIZ_JAR") and not env.get("GRAMMARVIZ_DIR"):
        print("bootstrap required — run ./scripts/bootstrap.sh", file=sys.stderr)
        return 1

    classpath = compile_driver(env)

    results: list[dict] = []
    for run in runs:
        print(f"bench: {run['label']} …", flush=True)
        results.append(run_case(env, run, classpath))

    section = render_section(results, env)
    print(section)

    if args.update_readme:
        changed = patch_readme(section)
        print("README updated." if changed else "README already up to date.")
    elif args.check_readme:
        current = README.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
            re.DOTALL,
        )
        expected = f"{MARKER_START}\n{section.rstrip()}\n{MARKER_END}"
        match = pattern.search(current)
        if not match or match.group(0) != expected:
            print("README bench block is stale — run ./scripts/bench_rra_hotsax.sh --update-readme", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
