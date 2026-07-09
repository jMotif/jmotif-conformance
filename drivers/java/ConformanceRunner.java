import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import net.seninp.gi.logic.GrammarRuleRecord;
import net.seninp.gi.logic.GrammarRules;
import net.seninp.gi.repair.RePairFactory;
import net.seninp.gi.repair.RePairGrammar;
import net.seninp.jmotif.sax.NumerosityReductionStrategy;
import net.seninp.jmotif.sax.SAXException;
import net.seninp.jmotif.sax.SAXProcessor;
import net.seninp.jmotif.sax.TSProcessor;
import net.seninp.jmotif.sax.alphabet.NormalAlphabet;
import net.seninp.jmotif.sax.datastructure.SAXRecords;
import net.seninp.jmotif.sax.discord.BruteForceDiscordImplementation;
import net.seninp.jmotif.sax.discord.DiscordRecord;
import net.seninp.jmotif.sax.discord.DiscordRecords;
import net.seninp.jmotif.sax.discord.HOTSAXImplementation;
import net.seninp.jmotif.sax.registry.LargeWindowAlgorithm;

/**
 * Conformance driver for jmotif-sax and jmotif-gi. Invoked by scripts/run_all.py with
 * explicit flags derived from a case JSON file.
 */
public class ConformanceRunner {

  private static final Pattern INT_LIST = Pattern.compile("\\[\\s*(\\d+(?:\\s*,\\s*\\d+)*)\\s*\\]");

  public static void main(String[] args) throws Exception {
    if (args.length < 1) {
      usage();
    }
    String operation = args[0];
    String repoRoot = ".";
    String seriesPath = null;
    String saxStringFile = null;
    int sliceStart = 0;
    Integer sliceEnd = null;
    int window = 100;
    int paa = 3;
    int alphabet = 3;
    int numDiscords = 2;
    double threshold = 0.01;
    String nrStrategy = "NONE";
    List<Integer> pinned = new ArrayList<>();

    for (int i = 1; i < args.length; i++) {
      switch (args[i]) {
        case "--repo-root":
          repoRoot = args[++i];
          break;
        case "--series":
          seriesPath = args[++i];
          break;
        case "--sax-string-file":
          saxStringFile = args[++i];
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
        case "--pinned-indices":
          pinned = parseIntList(args[++i]);
          break;
        default:
          throw new IllegalArgumentException("unknown flag: " + args[i]);
      }
    }

    switch (operation) {
      case "repair":
        if (saxStringFile == null) {
          throw new IllegalArgumentException("--sax-string-file is required");
        }
        String saxString = loadSaxString(Paths.get(repoRoot, saxStringFile));
        printRepairResult(saxString, repair(saxString));
        break;
      case "discord_bruteforce":
      case "discord_hotsax":
      case "sax_via_window":
        if (seriesPath == null) {
          throw new IllegalArgumentException("--series is required");
        }
        double[] series = loadSeries(Paths.get(repoRoot, seriesPath), sliceStart, sliceEnd);
        if ("discord_bruteforce".equals(operation)) {
          printDiscordResult(bruteForce(series, window, numDiscords, threshold));
        }
        else if ("discord_hotsax".equals(operation)) {
          printDiscordResult(hotSax(series, window, paa, alphabet, numDiscords, threshold, nrStrategy));
        }
        else {
          printSaxResult(saxViaWindow(series, window, paa, alphabet, threshold, nrStrategy), pinned);
        }
        break;
      default:
        throw new IllegalArgumentException("unsupported operation: " + operation);
    }
  }

  private static String loadSaxString(Path path) throws IOException {
    String text = Files.readString(path, StandardCharsets.UTF_8).trim();
    return String.join(" ", text.split("\\s+"));
  }

  private static GrammarRules repair(String saxString) {
    RePairGrammar grammar = RePairFactory.buildGrammar(saxString);
    grammar.expandRules();
    return grammar.toGrammarRulesData();
  }

  private static double[] loadSeries(Path path, int start, Integer end) throws IOException, SAXException {
    double[] full = TSProcessor.readFileColumn(path.toString(), 0, 0);
    int last = end == null ? full.length : Math.min(end, full.length);
    int length = Math.max(0, last - start);
    double[] slice = new double[length];
    System.arraycopy(full, start, slice, 0, length);
    return slice;
  }

  private static DiscordRecords bruteForce(double[] series, int window, int numDiscords, double threshold)
      throws Exception {
    return BruteForceDiscordImplementation.series2BruteForceDiscords(series, window, numDiscords,
        new LargeWindowAlgorithm(), threshold);
  }

  private static DiscordRecords hotSax(double[] series, int window, int paa, int alphabet, int numDiscords,
      double threshold, String nrStrategy) throws Exception {
    return HOTSAXImplementation.series2Discords(series, numDiscords, window, paa, alphabet,
        parseNrStrategy(nrStrategy), threshold);
  }

  private static SAXRecords saxViaWindow(double[] series, int window, int paa, int alphabet, double threshold,
      String nrStrategy) throws SAXException {
    SAXProcessor sp = new SAXProcessor();
    NormalAlphabet na = new NormalAlphabet();
    SAXRecords res = sp.ts2saxViaWindow(series, window, paa, na.getCuts(alphabet), parseNrStrategy(nrStrategy),
        threshold);
    res.buildIndex();
    return res;
  }

  private static NumerosityReductionStrategy parseNrStrategy(String value) {
    return NumerosityReductionStrategy.valueOf(value.toUpperCase());
  }

  private static List<Integer> parseIntList(String raw) {
    Matcher matcher = INT_LIST.matcher(raw.trim());
    if (!matcher.matches()) {
      throw new IllegalArgumentException("expected [1,2,3] style list, got: " + raw);
    }
    List<Integer> out = new ArrayList<>();
    for (String part : matcher.group(1).split(",")) {
      out.add(Integer.parseInt(part.trim()));
    }
    return out;
  }

  private static boolean r0NoRepeatedDigram(String r0RuleString) {
    String[] tokens = r0RuleString.trim().split("\\s+");
    if (tokens.length < 2) {
      return true;
    }
    java.util.HashSet<String> seen = new java.util.HashSet<>();
    for (int i = 0; i < tokens.length - 1; i++) {
      String digram = tokens[i] + " " + tokens[i + 1];
      if (!seen.add(digram)) {
        return false;
      }
    }
    return true;
  }

  private static void printRepairResult(String input, GrammarRules rules) {
    GrammarRuleRecord r0 = rules.get(0);
    String r0RuleString = r0.getRuleString().trim();
    String decompressed = r0.getExpandedRuleString().trim();
    StringBuilder sb = new StringBuilder("{\"input\":");
    appendJsonString(sb, input);
    sb.append(",\"r0_rule_string\":");
    appendJsonString(sb, r0RuleString);
    sb.append(",\"decompressed\":");
    appendJsonString(sb, decompressed);
    sb.append(",\"r0_no_repeated_digram\":").append(r0NoRepeatedDigram(r0RuleString));
    sb.append(",\"rules\":[");
    for (int i = 0; i < rules.size(); i++) {
      GrammarRuleRecord rec = rules.get(i);
      if (i > 0) {
        sb.append(',');
      }
      sb.append("{\"rule_id\":").append(rec.getRuleNumber()).append(",\"rule_string\":");
      appendJsonString(sb, rec.getRuleString().trim());
      sb.append(",\"expanded_rule_string\":");
      appendJsonString(sb, rec.getExpandedRuleString().trim());
      sb.append('}');
    }
    sb.append("]}");
    System.out.println(sb);
  }

  private static void appendJsonString(StringBuilder sb, String value) {
    sb.append('"');
    for (int i = 0; i < value.length(); i++) {
      char ch = value.charAt(i);
      if (ch == '\\' || ch == '"') {
        sb.append('\\').append(ch);
      }
      else {
        sb.append(ch);
      }
    }
    sb.append('"');
  }

  private static void printDiscordResult(DiscordRecords records) {
    StringBuilder sb = new StringBuilder("{\"discords\":[");
    for (int i = 0; i < records.getSize(); i++) {
      DiscordRecord d = records.get(i);
      if (i > 0) {
        sb.append(',');
      }
      sb.append("{\"position\":").append(d.getPosition()).append(",\"nn_distance\":")
          .append(trimDouble(d.getNNDistance())).append('}');
    }
    sb.append("]}");
    System.out.println(sb);
  }

  private static void printSaxResult(SAXRecords records, List<Integer> pinned) {
    StringBuilder sb = new StringBuilder("{\"sax_windows\":[");
    for (int i = 0; i < pinned.size(); i++) {
      int index = pinned.get(i);
      if (i > 0) {
        sb.append(',');
      }
      sb.append("{\"index\":").append(index).append(",\"word\":\"")
          .append(records.getByIndex(index).getPayload()).append("\"}");
    }
    sb.append("]}");
    System.out.println(sb);
  }

  private static String trimDouble(double value) {
    String text = Double.toString(value);
    if (text.contains("E") || text.contains("e")) {
      return String.format("%.15g", value);
    }
    return text;
  }

  private static void usage() {
    System.err.println("usage: ConformanceRunner <operation> [--repo-root PATH] "
        + "[--series PATH | --sax-string-file PATH] "
        + "[--slice-start N] [--slice-end N] [--window N] [--paa N] [--alphabet N] "
        + "[--num-discords N] [--threshold X] [--nr-strategy NAME] [--pinned-indices [0,1]]");
    System.exit(2);
  }
}
