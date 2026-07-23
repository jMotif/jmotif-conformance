import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.Random;
import net.seninp.gi.repair.RePairFactory;
import net.seninp.gi.repair.RePairGrammar;
import net.seninp.grammarviz.anomaly.RRAImplementation;
import net.seninp.grammarviz.anomaly.RRAIntervalBuilder;
import net.seninp.jmotif.sax.NumerosityReductionStrategy;
import net.seninp.jmotif.sax.TSProcessor;
import net.seninp.jmotif.sax.datastructure.SAXRecords;
import net.seninp.jmotif.sax.discord.DiscordRecord;
import net.seninp.jmotif.sax.discord.DiscordRecords;
import net.seninp.jmotif.sax.discord.HOTSAXImplementation;
import net.seninp.jmotif.sax.parallel.ParallelSAXImplementation;

/** Single-case wall-clock benchmark for RRA vs HOT-SAX (informative, not conformance). */
public class RRAvsHotsaxBench {

  static class Timed {
    long ms;
    int topPos;
    double topNn;
    int discords;
  }

  static Timed hotsax(double[] series, int w, int p, int a, int k) throws Exception {
    long t0 = System.nanoTime();
    DiscordRecords d = HOTSAXImplementation.series2Discords(
        series, k, w, p, a, NumerosityReductionStrategy.NONE, 0.01);
    Timed r = new Timed();
    r.ms = (System.nanoTime() - t0) / 1_000_000;
    r.discords = d.getSize();
    if (d.getSize() > 0) {
      DiscordRecord top = d.get(0);
      r.topPos = top.getPosition();
      r.topNn = top.getNNDistance();
    }
    return r;
  }

  static Timed rra(double[] series, int w, int p, int a, int k, long seed) throws Exception {
    long t0 = System.nanoTime();
    ParallelSAXImplementation ps = new ParallelSAXImplementation();
    try {
      SAXRecords sax = ps.process(series, 2, w, p, a, NumerosityReductionStrategy.NONE, 0.01);
      RePairGrammar grammar = RePairFactory.buildGrammar(sax);
      grammar.expandRules();
      grammar.buildIntervals(sax, series, w);
      DiscordRecords d = RRAImplementation.series2RRAAnomalies(
          series, k,
          RRAIntervalBuilder.fromGrammarRules(grammar.toGrammarRulesData(), series.length),
          0.01, new Random(seed));
      Timed r = new Timed();
      r.ms = (System.nanoTime() - t0) / 1_000_000;
      r.discords = d.getSize();
      if (d.getSize() > 0) {
        DiscordRecord top = d.get(0);
        r.topPos = top.getPosition();
        r.topNn = top.getNNDistance();
      }
      return r;
    } finally {
      ps.shutdown();
    }
  }

  static double[] loadSeries(Path repoRoot, String dataset, Integer tileLength, boolean tileDrift)
      throws Exception {
    double[] base = TSProcessor.readFileColumn(
        repoRoot.resolve("datasets").resolve(dataset).toString(), 0, 0);
    if (tileLength == null || tileLength <= base.length) {
      return base;
    }
    double[] out = new double[tileLength];
    double drift = 0.0;
    for (int i = 0; i < tileLength; i++) {
      if (tileDrift && i > 0 && i % base.length == 0) {
        drift += 1e-4 * (i / base.length);
      }
      out[i] = base[i % base.length] + drift;
    }
    return out;
  }

  static String esc(String s) {
    return s.replace("\\", "\\\\").replace("\"", "\\\"");
  }

  public static void main(String[] args) throws Exception {
    Path repoRoot = Paths.get(".").toAbsolutePath().normalize();
    String group = "long";
    String label = "case";
    String dataset = "ecg0606_1.csv";
    Integer tileLength = null;
    boolean tileDrift = false;
    int window = 100;
    int paa = 4;
    int alphabet = 4;
    int k = 1;
    long seed = 0L;

    for (int i = 0; i < args.length; i++) {
      switch (args[i]) {
        case "--repo-root":
          repoRoot = Paths.get(args[++i]).toAbsolutePath().normalize();
          break;
        case "--group":
          group = args[++i];
          break;
        case "--label":
          label = args[++i];
          break;
        case "--dataset":
          dataset = args[++i];
          break;
        case "--tile-length":
          tileLength = Integer.parseInt(args[++i]);
          break;
        case "--tile-drift":
          tileDrift = true;
          break;
        case "--window":
          window = Integer.parseInt(args[++i]);
          break;
        case "--paa":
          paa = Integer.parseInt(args[++i]);
          break;
        case "--alphabet":
          alphabet = Integer.parseInt(args[++i]);
          break;
        case "--k":
          k = Integer.parseInt(args[++i]);
          break;
        case "--seed":
          seed = Long.parseLong(args[++i]);
          break;
        default:
          throw new IllegalArgumentException("unknown flag: " + args[i]);
      }
    }

    double[] series = loadSeries(repoRoot, dataset, tileLength, tileDrift);
    Timed hs = hotsax(series, window, paa, alphabet, k);
    Timed rr = rra(series, window, paa, alphabet, k, seed);
    double ratio = hs.ms > 0 ? rr.ms / (double) hs.ms : 0.0;

    StringBuilder out = new StringBuilder();
    out.append('{');
    out.append("\"generated_at\":\"").append(Instant.now()).append("\",");
    out.append("\"group\":\"").append(esc(group)).append("\",");
    out.append("\"label\":\"").append(esc(label)).append("\",");
    out.append("\"dataset\":\"").append(esc(dataset)).append("\",");
    out.append("\"n\":").append(series.length).append(',');
    out.append("\"window\":").append(window).append(',');
    out.append("\"paa\":").append(paa).append(',');
    out.append("\"alphabet\":").append(alphabet).append(',');
    out.append("\"k\":").append(k).append(',');
    out.append("\"seed\":").append(seed).append(',');
    out.append("\"hotsax_ms\":").append(hs.ms).append(',');
    out.append("\"rra_ms\":").append(rr.ms).append(',');
    out.append("\"ratio\":").append(String.format(java.util.Locale.US, "%.4f", ratio)).append(',');
    out.append("\"hotsax_discords\":").append(hs.discords).append(',');
    out.append("\"rra_discords\":").append(rr.discords).append(',');
    out.append("\"hotsax_top\":").append(hs.topPos).append(',');
    out.append("\"rra_top\":").append(rr.topPos);
    out.append('}');
    System.out.println(out);
  }
}
