# Changelog

All notable changes to jmotif-conformance are documented here.

## [Unreleased]

Cross-language golden-test harness for the jMotif SAX stack (Java, R, Python). No versioned
releases yet — the repo tracks `master` and pins upstream implementations in CI.

### Added
- **Tier-A cases:** sliding-window SAX, discord brute-force / HOT-SAX, RePair (tie-free and
  round-trip checks), SAX-VSM classification (CBF, Gun_Point).
- **Tier-B case:** RRA discord on ecg0606 (windows 100, 120) with ≥50% region overlap,
  ground-truth anchor, and cross-language consensus checks.
- **Drivers** for Java, R, and Python; `bootstrap.sh` / `run_all.sh` orchestration.
- **pytest suite** for `verify_consensus` / overlap logic; fail-fast CI step before heavy
  bootstrap.

### Changed
- **CI:** pin upstream implementations to commit SHAs instead of floating `master`;
  install `jmotif-gi` for GrammarViz dependency; run conformance on push/PR.
- **RRA tier-B docs:** expanded case-tier table and overlap thresholds in README.

### Fixed
- **RRA consensus:** require all aligned implementations to participate (not a subset).
- GrammarViz clone URL for CI/bootstrap; README badge URLs updated.
