# jmotif-conformance

Shared golden tests for the jMotif SAX stack across **Java** ([jMotif/SAX](https://github.com/jMotif/SAX)), **R** ([jMotif/jmotif-R](https://github.com/jMotif/jmotif-R)), and **Python** ([seninp/saxpy](https://github.com/seninp/saxpy)).

[saxpy](https://github.com/seninp/saxpy) is the reference generator for expected values. Each implementation runs the same case definitions and is checked against the committed expectations.

## Conventions

These cases assume the 2.0.0 alignment rules:

- z-normalization uses the **population** standard deviation (divide by `n`)
- PAA uses fractional segment boundaries
- a value exactly on a Gaussian breakpoint maps to the symbol **above** the cut
- discord search compares **z-normalized** subsequences
- distance ties break on the **lowest index**
- trivial matches within ±(`window` − 1) are excluded

## Layout

```
cases/          JSON case definitions + expected outputs
datasets/       shared CSV inputs
drivers/        thin per-language runners
scripts/        bootstrap, run_all, export_goldens
```

## Quick start (poptiplex)

Sibling checkout layout:

```
~/git/
  jmotif-conformance/
  SAX/              # or jmotif-java/
  GI/
  sax-vsm_classic/
  grammarviz2_src/  # or GrammarViz2/
  jmotif-R/
  saxpy/
```

```bash
cd ~/git/jmotif-conformance
./scripts/bootstrap.sh      # build/install all three implementations
./scripts/run_all.sh        # run every case × every aligned implementation
```

Run a single implementation or case:

```bash
./scripts/run_all.sh --impl python
./scripts/run_all.sh --impl java --case cases/discord_bruteforce_ecg800.json
```

## Regenerating goldens

When all three implementations agree on an intentional behavior change, refresh expectations from saxpy:

```bash
cd saxpy && uv pip install -e .
cd ../jmotif-conformance
python3 scripts/export_goldens.py
git diff cases/
```

Review the diff carefully before committing.

## Case tiers (v1)

| Operation | Cross-lang |
|-----------|------------|
| `sax_via_window` (`NONE`) | yes |
| `discord_bruteforce` | yes |
| `discord_hotsax` (`NONE`, positions + distances) | yes |
| `repair` (RePair decompression + R0 invariants) | yes |
| `saxvsm_classify` (CBF, Gun_Point accuracy) | yes |
| `rra_discord` (ecg0606 top region, tier-B) | yes |

RePair rule **numbering** is compared exactly only on tie-free inputs (paper example, `a b a b`). Long SAX strings check decompression round-trip and the no-repeated-digram guarantee on R0 instead of per-rule IDs.

SAX-VSM cases pin train/test accuracy (`correct`, `total`, `accuracy`, `error`) at operating points aligned with sax-vsm 2.0.1 / saxpy 2.0.0.

### RRA tier-B (`rra_discord`)

RRA (Rare Rule Anomaly) uses variable-length grammar-rule intervals, so cross-language agreement is checked at the **region** level, not on exact span boundaries or distances:

| Checked (conform) | Not checked (de-conform) |
|-------------------|--------------------------|
| RRA top span overlaps the HOT-SAX discord window on ecg0606 (primary anomaly region) | Exact `start` / `end` of the top discord |
| | Whether index 430 lies strictly inside the RRA span (Java NewRepair can shift by one vs saxpy/R) |
| | `rule_id` of the winning interval |
| | Exact `nn_distance` (early-abandon is approximate) |
| | Distance-call count / search trajectory |
| | Multi-discord ordering beyond the primary region |

The Java driver follows the saxpy / jmotif-R pipeline (RePair on the composed SAX string, saxpy-style zero-coverage filtering, seeded phase-2 shuffle). GrammarViz’s pruned-RRA CLI path is intentionally not used here.

## Requirements

- JDK 21+
- Maven 3.9+
- R 4.0+ with Rcpp toolchain
- Python 3.10+ with numpy/scipy (saxpy dependencies)
- optional: [uv](https://github.com/astral-sh/uv) for Python env management

## License

GPL-2.0 — see [LICENSE](LICENSE).
