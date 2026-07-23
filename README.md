# jmotif-conformance

[![conformance](https://github.com/jMotif/jmotif-conformance/actions/workflows/conformance.yml/badge.svg)](https://github.com/jMotif/jmotif-conformance/actions/workflows/conformance.yml)
[![License](https://img.shields.io/github/license/jMotif/jmotif-conformance)](https://www.gnu.org/licenses/gpl-2.0.html)

Shared golden tests for the jMotif SAX stack across **Java** ([jMotif/SAX](https://github.com/jMotif/SAX)), **R** ([jMotif/jmotif-R](https://github.com/jMotif/jmotif-R)), and **Python** ([seninp/saxpy](https://github.com/seninp/saxpy)).

[saxpy](https://github.com/seninp/saxpy) is the reference generator for expected values. Each implementation runs the same case definitions and is checked against the committed expectations.

**Published targets (Jul 2026):** saxpy **2.0.1**, jmotif **1.3.2**, jmotif-sax **2.0.2**. Tier-B RRA pins use bundled ecg0606 with `seed = 0`.

## RRA vs HOT-SAX wall-clock (informative, not conformance)

These tables measure **Java end-to-end wall time** on GrammarViz’s RRA and HOT-SAX paths. They are **not** golden conformance checks — tier-B RRA asserts **region overlap**, not identical spans or run time. NN distances between the two algorithms are not comparable (fixed-window z-norm vs length-normalized grammar spans).

Regenerate after stack upgrades (requires `./scripts/bootstrap.sh` first):

```bash
./scripts/bench_rra_hotsax.sh --update-readme
```

Case definitions live in [`cases/bench_rra_hotsax.json`](cases/bench_rra_hotsax.json). Long tiled rows repeat `chfdbchf15_1.csv` with a tiny per-cycle drift so cycles are not exact clones (verbatim tiling can stall HOT-SAX).

**Plausible explanation:** HOT-SAX prunes over SAX-word frequencies but still walks the full word index. RRA pays upfront parallel SAX + Re-Pair + interval construction, then searches fewer grammar-rule candidates. On short series that fixed cost dominates; on roughly **10k–15k** ECG-like points and beyond, RRA’s reduced search typically wins wall-clock. Crossover depends on `(window, PAA, alphabet)` and hardware.

<!-- bench-rra-hotsax:start -->
_Generated 2026-07-23 09:00 UTC by `./scripts/bench_rra_hotsax.sh --update-readme` (GrammarViz `grammarviz2_src`, jmotif-sax `jmotif-java`, `k=1`, `seed=0`, NR=`NONE`, z=`0.01`)._

**Short series (ecg0606, `n = 2,299`)**

| Parameters | HOT-SAX | RRA | RRA / HOT-SAX |
|------------|---------|-----|---------------|
| `w=120, p=4, a=4` | 50 ms | 76 ms | 1.52× slower |
| `w=100, p=4, a=4` | 45 ms | 77 ms | 1.71× slower |
| `w=150, p=7, a=4` | 91 ms | 82 ms | **0.90× faster** |

**Longer ECG-like series (`w=100, p=4, a=4`)**

| Series | `n` | HOT-SAX | RRA | RRA / HOT-SAX |
|--------|-----|---------|-----|---------------|
| ecg0606 baseline | 2,299 | 43 ms | 82 ms | 1.91× slower |
| chfdbchf15 | 15,000 | 235 ms | 317 ms | 1.35× slower |
| chfdb tiled+drift 50k | 50,000 | 10.5 s | 2447 ms | **0.23× faster** |
| chfdb tiled+drift 100k | 100,000 | 20.8 s | 7776 ms | **0.37× faster** |

Ratios **below 1.0×** (shown as “faster”) mean RRA had lower wall-clock on that row.
<!-- bench-rra-hotsax:end -->

Mirror on the [GrammarViz anomaly tutorial §2.4](https://grammarviz2.github.io/grammarviz2_site/anomaly/experience-a2/#24-wall-clock-scaling-rra-vs-hot-sax).

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
./scripts/bench_rra_hotsax.sh --update-readme   # optional: refresh RRA vs HOT-SAX tables in this README
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

## Case tiers

Every operation runs on **Java × R × Python** and is checked against committed
expectations. Cases fall into two tiers by how tightly the languages can agree:

- **Tier A — exact.** Deterministic outputs are compared value-for-value (integer
  positions and strings exactly; floats within an absolute tolerance).
- **Tier B — region-level.** RRA uses variable-length grammar-rule intervals, so
  exact spans legitimately differ; agreement is asserted on the anomaly *region*
  with a substantial-overlap threshold plus a ground-truth anchor and a
  cross-language consensus check.

| Operation | Tier | Datasets | Checked exactly (conform) | Tolerance |
|-----------|:----:|----------|---------------------------|-----------|
| `sax_via_window` (`NONE`) | A | `synthetic_window_60`, `ecg0606` | SAX word for every window index | exact |
| `discord_bruteforce` | A | `ecg0606` (full / slice / first-800) | discord `position`; `nn_distance` | `nn_distance` 1e-6 |
| `discord_hotsax` (`NONE`) | A | `ecg0606` | discord `position` + `nn_distance`; HOT-SAX top ∈ brute-force top discord | `nn_distance` 1e-6 |
| `repair` | A | `abab`, `paper`, `ecg_sax`, `jmotif_r_bugs` | R0 has no repeated digram; decompress == input; exact rule strings/IDs on tie-free inputs | exact |
| `saxvsm_classify` | A | CBF, Gun_Point | `correct`, `total`, `accuracy`, `error` | `accuracy` 1e-12 |
| `rra_discord` | B | `ecg0606` (window 100, 120) | see tier-B table below | ≥ 50% overlap |

RePair rule **numbering** is compared exactly only on tie-free inputs (paper
example, `a b a b`). Long SAX strings check the decompression round-trip and the
no-repeated-digram guarantee on R0 instead of per-rule IDs.

SAX-VSM cases pin train/test accuracy (`correct`, `total`, `accuracy`, `error`)
at operating points aligned with sax-vsm 2.0.1 / saxpy 2.0.1.

### RRA tier-B (`rra_discord`)

RRA (Rare Rule Anomaly) grammar-rule intervals vary in length across
implementations, so agreement is checked at the **region** level. Each check uses
a **≥ 50% of window** overlap threshold (not a single-sample touch):

| Checked (conform) | Not checked (de-conform) |
|-------------------|--------------------------|
| RRA top span overlaps the HOT-SAX discord window on ecg0606 by ≥ 50% of the window | Exact `start` / `end` of the top discord |
| RRA top span overlaps the ground-truth anomaly region `[400, 560)` by ≥ 50% of the window | Whether index 430 lies strictly inside the RRA span (Java NewRepair can shift by one vs saxpy/R) |
| All three languages' RRA top spans mutually overlap each other by ≥ 50% of the window (consensus) | `rule_id` of the winning interval |
| Robustness across two window sizes (100, 120) | Exact `nn_distance` (early-abandon is approximate) |
| | Distance-call count / search trajectory |
| | Multi-discord ordering beyond the primary region |

Thresholds are conservative: on the pinned stack the observed overlaps are
0.84–1.0, so a 0.5 floor leaves margin for the documented one-sample RePair
shift while still failing a genuinely divergent region (e.g. window 150, where
Java's top region jumps elsewhere).

The Java driver follows the saxpy / jmotif-R pipeline (RePair on the composed SAX
string, saxpy-style zero-coverage filtering, seeded phase-2 shuffle).
GrammarViz’s pruned-RRA CLI path is intentionally not used here.

## Git hooks (optional)

To block accidental commits of Cursor/Claude/audit artifacts, run once per clone:

```bash
./scripts/install-git-hooks.sh
```

`.gitignore` already excludes these paths; the hook is a second line of defense.

## Requirements

- JDK 21+
- Maven 3.9+
- R 4.0+ with Rcpp toolchain
- Python 3.10+ with numpy/scipy (saxpy dependencies)
- optional: [uv](https://github.com/astral-sh/uv) for Python env management

## License

GPL-2.0 — see [LICENSE](LICENSE).
