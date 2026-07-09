import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Random;
import net.seninp.gi.logic.RuleInterval;
import net.seninp.gi.repair.RePairFactory;
import net.seninp.gi.repair.RePairGrammar;
import net.seninp.gi.repair.RePairRule;
import net.seninp.grammarviz.anomaly.RRAImplementation;
import net.seninp.jmotif.sax.NumerosityReductionStrategy;
import net.seninp.jmotif.sax.SAXException;
import net.seninp.jmotif.sax.SAXProcessor;
import net.seninp.jmotif.sax.TSProcessor;
import net.seninp.jmotif.sax.alphabet.NormalAlphabet;
import net.seninp.jmotif.sax.datastructure.SAXRecords;
import net.seninp.jmotif.sax.discord.DiscordRecord;
import net.seninp.jmotif.sax.discord.DiscordRecords;
import net.seninp.jmotif.sax.discord.HOTSAXImplementation;

/**
 * Conformance driver for RRA (Rare Rule Anomaly) discord discovery.
 *
 * <p>Follows the saxpy / jmotif-R pipeline: SAX via window ({@code NONE}), RePair on the
 * composed SAX string, rule-frequency interval ranking, saxpy-style zero-coverage filtering, then
 * {@link RRAImplementation}.
 */
public class RRAConformanceRunner {

  public static void main(String[] args) throws Exception {
    String repoRoot = ".";
    String seriesPath = null;
    int sliceStart = 0;
    Integer sliceEnd = null;
    int window = 100;
    int paa = 4;
    int alphabet = 4;
    int numDiscords = 1;
    double threshold = 0.01;
    String nrStrategy = "NONE";
    int seed = 0;

    for (int i = 0; i < args.length; i++) {
      switch (args[i]) {
        case "--repo-root":
          repoRoot = args[++i];
          break;
        case "--series":
          seriesPath = args[++i];
          break;
        case "--slice-start":
          sliceStart = Integer.parseInt(args[++i]);
          break;
        case "--slice-end":
          sliceEnd = Integer.parseInt(args[++i]);
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
        case "--num-discords":
          numDiscords = Integer.parseInt(args[++i]);
          break;
        case "--threshold":
          threshold = Double.parseDouble(args[++i]);
          break;
        case "--nr-strategy":
          nrStrategy = args[++i];
          break;
        case "--seed":
          seed = Integer.parseInt(args[++i]);
          break;
        default:
          throw new IllegalArgumentException("unknown flag: " + args[i]);
      }
    }
    if (seriesPath == null) {
      throw new IllegalArgumentException("--series is required");
    }

    double[] series = loadSeries(Paths.get(repoRoot, seriesPath), sliceStart, sliceEnd);
    printResult(runRra(series, window, paa, alphabet, nrStrategy, threshold, numDiscords, seed));
  }

  static RraResult runRra(double[] series, int window, int paa, int alphabet, String nrStrategy,
      double threshold, int numDiscords, int seed) throws Exception {
    SAXRecords saxRecords = saxViaWindow(series, window, paa, alphabet, threshold, nrStrategy);
    saxRecords.buildIndex();

    RePairGrammar grammar = RePairFactory.buildGrammar(saxRecords.getSAXString(" "));
    grammar.expandRules();

    ArrayList<RuleInterval> intervals = new ArrayList<>();
    int[] coverageArray = new int[series.length];

    for (RePairRule rule : grammar.getRules().values()) {
      int freq = rule.getOccurrences().length;
      String[] tokens = rule.toExpandedRuleString().trim().split("\\s+");
      int tokenSpan = tokens.length;
      for (int strPos : rule.getOccurrences()) {
        Integer tsStart = saxRecords.mapStringIndexToTSPosition(strPos);
        Integer tsEndToken = saxRecords.mapStringIndexToTSPosition(strPos + tokenSpan - 1);
        if (tsStart == null || tsEndToken == null) {
          continue;
        }
        int start = tsStart;
        int end = tsEndToken + window;
        RuleInterval ri = new RuleInterval(rule.getId(), start, end, freq);
        intervals.add(ri);
        for (int j = start; j < end; j++) {
          coverageArray[j]++;
        }
      }
    }

    addZeroIntervals(intervals, coverageArray, paa);

    DiscordRecords discords = RRAImplementation.series2RRAAnomalies(series, numDiscords, intervals,
        threshold, new Random(seed));
    if (discords.getSize() == 0) {
      throw new IllegalStateException("RRA found no discords");
    }

    DiscordRecord top = discords.get(0);
    int start = top.getPosition();
    int end = start + top.getLength();

    DiscordRecords hot = HOTSAXImplementation.series2Discords(series, 1, window, paa, alphabet,
        parseNrStrategy(nrStrategy), threshold);
    int hotPos = hot.get(0).getPosition();

    return new RraResult(start, end, hotPos);
  }

  private static void addZeroIntervals(ArrayList<RuleInterval> intervals, int[] coverageArray,
      int paaSize) {
    int minUncovered = Math.max(2, paaSize);
    int start = -1;
    boolean inInterval = false;
    int zeroId = -1;
    for (int i = 0; i < coverageArray.length; i++) {
      if (coverageArray[i] == 0 && !inInterval) {
        start = i;
        inInterval = true;
      }
      if (coverageArray[i] > 0 && inInterval) {
        int runLen = i - start;
        if (runLen >= minUncovered) {
          intervals.add(new RuleInterval(zeroId, start, i, 0));
          zeroId--;
        }
        inInterval = false;
      }
    }
  }

  private static SAXRecords saxViaWindow(double[] series, int window, int paa, int alphabet,
      double threshold, String nrStrategy) throws SAXException {
    SAXProcessor sp = new SAXProcessor();
    NormalAlphabet na = new NormalAlphabet();
    SAXRecords res = sp.ts2saxViaWindow(series, window, paa, na.getCuts(alphabet),
        parseNrStrategy(nrStrategy), threshold);
    res.buildIndex();
    return res;
  }

  private static NumerosityReductionStrategy parseNrStrategy(String value) {
    return NumerosityReductionStrategy.valueOf(value.toUpperCase());
  }

  private static double[] loadSeries(Path path, int start, Integer end)
      throws IOException, SAXException {
    double[] full = TSProcessor.readFileColumn(path.toString(), 0, 0);
    int last = end == null ? full.length : Math.min(end, full.length);
    int length = Math.max(0, last - start);
    double[] slice = new double[length];
    System.arraycopy(full, start, slice, 0, length);
    return slice;
  }

  private static void printResult(RraResult result) {
    StringBuilder sb = new StringBuilder();
    sb.append("{\"top_discord\":{\"start\":").append(result.start).append(",\"end\":")
        .append(result.end).append("},\"hotsax_top_position\":").append(result.hotPos).append('}');
    System.out.println(sb);
  }

  static final class RraResult {
    final int start;
    final int end;
    final int hotPos;

    RraResult(int start, int end, int hotPos) {
      this.start = start;
      this.end = end;
      this.hotPos = hotPos;
    }
  }
}
