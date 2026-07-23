# RRA vs HOT-SAX wall-clock (informative, not conformance)

This note documents **Java wall-clock scaling** between HOT-SAX and RRA on GrammarViz **3.0.4** / jmotif-sax **2.0.1**. It is **not** part of the golden conformance suite — tier-B RRA checks in `cases/rra_ecg_top_region*.json` assert **region overlap**, not identical spans or run time.

Cross-implementation alignment rules live in [README.md](../README.md#conventions). Performance characterization lives here.

## Method

- **Engine:** GrammarViz 3.0.4 classpath (`RRAImplementation`, `HOTSAXImplementation`, parallel SAX + Re-Pair).
- **Settings:** `k = 1` discord, `seed = 0`, numerosity **NONE**, z-normalization threshold **0.01**.
- **Timing:** end-to-end wall clock per algorithm on the same JVM (includes parallel SAX + Re-Pair + interval build for RRA).
- **Hardware:** MacBook-class Apple Silicon, Jul 2026 (your numbers will differ; ratios are the stable signal).

Long-series rows tile **`chfdbchf15_1.csv`** (15,000-point ECG shipped with GrammarViz) with a tiny per-cycle drift so cycles are not exact clones. **Do not** benchmark by verbatim repetition of ecg0606 — HOT-SAX can stall or report zero discords on perfectly periodic tilings.

## Short series — ecg0606 (`n = 2,299`)

| Parameters | HOT-SAX | RRA | RRA / HOT-SAX |
|------------|---------|-----|---------------|
| `w=120, p=4, a=4` | 50 ms | 75 ms | 1.50× slower |
| `w=100, p=4, a=4` | 19 ms | 29 ms | 1.53× slower |
| `w=150, p=7, a=4` | 77 ms | 71 ms | **0.92× faster** |

## Longer ECG-like series — `w=100, p=4, a=4`

| Series | `n` | HOT-SAX | RRA | RRA / HOT-SAX |
|--------|-----|---------|-----|---------------|
| ecg0606 | 2,299 | 44 ms | 82 ms | 1.86× slower |
| chfdbchf15 | 15,000 | 265 ms | 215 ms | **0.81× faster** |
| chfdb tiled + drift | 50,000 | 10.6 s | 2.3 s | **~0.21× (~5× faster)** |
| chfdb tiled + drift | 100,000 | 21.0 s | 7.8 s | **~0.37× (~2.7× faster)** |

Values below **1.0×** in the last column mean RRA was faster.

## Explanation

**HOT-SAX** reorders sliding-window candidates using SAX-word frequencies but still searches over the full word-index structure of the series. **RRA** pays upfront grammar work (SAX discretization, Re-Pair, rule intervals), then evaluates far fewer **variable-length** grammar-rule candidates. On long, compressible SAX strings the distance-call reduction dominates; on short series the grammar setup is not amortized and HOT-SAX often wins wall-clock.

Empirically, crossover on ECG-like data with `(w=100, p=4, a=4)` is around **10k–15k** points. Exact crossover depends on discretization parameters, hardware, and how repetitive the SAX token stream is.

## What this does *not* claim

| In scope here | Out of scope (see conformance tiers) |
|---------------|--------------------------------------|
| Wall-clock ratio trends vs series length | Exact top-discord `start` / `end` across Java, R, Python |
| Qualitative speed crossover | `nn_distance` equality (RRA uses length-normalized NN) |
| Parameter sensitivity on demo data | Distance-call or search-trajectory equality |

On long tiled runs, HOT-SAX and RRA may rank **different** top positions while both finding plausible discords — that is expected given different search spaces. Tier-B conformance instead checks **≥ 50% window overlap** with the HOT-SAX discord and the ecg0606 ground-truth region on pinned windows 100 and 120.

## Site mirror

The [GrammarViz anomaly tutorial](https://grammarviz2.github.io/grammarviz2_site/anomaly/experience-a2/) (§2.4) presents the same tables for site readers.

## Reproduce (optional)

A minimal driver used for these numbers:

```java
// RRAvsHotsaxBenchLong.java — compile against grammarviz2 target/classes + deps
// bench("chfdb tiled+drift 50k", tileDrift(chf, 50_000), 100, 4, 4, 1);
```

Keep `ParallelSAXImplementation.shutdown()` and `System.exit(0)` in harness code to avoid hung JVMs after batch runs.
