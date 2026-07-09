package net.seninp.jmotif;

import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import net.seninp.jmotif.sax.NumerosityReductionStrategy;
import net.seninp.jmotif.sax.SAXException;
import net.seninp.jmotif.text.Params;
import net.seninp.util.UCRUtils;

/**
 * Conformance driver for sax-vsm classification accuracy checks.
 */
public class SaxVSMConformanceRunner {

  public static void main(String[] args) throws Exception {
    String repoRoot = ".";
    String trainPath = null;
    String testPath = null;
    int window = 30;
    int paa = 4;
    int alphabet = 3;
    double threshold = 0.01;
    String nrStrategy = "EXACT";

    for (int i = 0; i < args.length; i++) {
      switch (args[i]) {
        case "--repo-root":
          repoRoot = args[++i];
          break;
        case "--train":
          trainPath = args[++i];
          break;
        case "--test":
          testPath = args[++i];
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
        case "--threshold":
          threshold = Double.parseDouble(args[++i]);
          break;
        case "--nr-strategy":
          nrStrategy = args[++i];
          break;
        default:
          throw new IllegalArgumentException("unknown flag: " + args[i]);
      }
    }

    if (trainPath == null || testPath == null) {
      usage();
    }

    Map<String, List<double[]>> train = UCRUtils
        .readUCRData(Paths.get(repoRoot, trainPath).toString());
    Map<String, List<double[]>> test = UCRUtils
        .readUCRData(Paths.get(repoRoot, testPath).toString());
    Params params = new Params(window, paa, alphabet, threshold,
        NumerosityReductionStrategy.valueOf(nrStrategy.toUpperCase()));
    SAXVSMEvaluator.Result result = SAXVSMEvaluator.evaluate(train, test, params);
    System.out.printf(
        "{\"accuracy\":%s,\"error\":%s,\"correct\":%d,\"total\":%d}%n",
        trimDouble(result.getAccuracy()),
        trimDouble(result.getError()),
        result.getCorrect(),
        result.getTotal());
  }

  private static String trimDouble(double value) {
    String text = Double.toString(value);
    if (text.contains("E") || text.contains("e")) {
      return String.format("%.15g", value);
    }
    return text;
  }

  private static void usage() {
    System.err.println("usage: SaxVSMConformanceRunner --train PATH --test PATH "
        + "[--repo-root PATH] [--window N] [--paa N] [--alphabet N] "
        + "[--threshold X] [--nr-strategy NAME]");
    System.exit(2);
  }
}
