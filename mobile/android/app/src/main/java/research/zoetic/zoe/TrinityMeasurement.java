package research.zoetic.zoe;

import java.util.Locale;

final class TrinityMeasurement {
    static final int MAX_PROBABILITIES = 64;
    private final double[] probabilities;
    private final double tau;
    private final AccessibleVolume.Result result;

    TrinityMeasurement(double[] probabilities, double tau) {
        if (probabilities == null || probabilities.length < 1 || probabilities.length > MAX_PROBABILITIES) {
            throw new IllegalArgumentException("Trinity distributions must contain 1 to 64 probabilities");
        }
        this.probabilities = probabilities.clone();
        this.tau = tau;
        this.result = AccessibleVolume.measure(this.probabilities, tau);
    }

    double[] probabilities() {
        return probabilities.clone();
    }

    double tau() {
        return tau;
    }

    AccessibleVolume.Result result() {
        return result;
    }

    static String measureJson(String source, double[] probabilities, double tau) {
        new TrinityMeasurement(probabilities, tau);
        if (!source.equals("android") && !source.equals("apple") && !source.equals("laptop")) {
            throw new IllegalArgumentException("Unknown Trinity source");
        }
        StringBuilder json = new StringBuilder("{\"source\":\"").append(source).append("\",\"probabilities\":[");
        for (int index = 0; index < probabilities.length; index++) {
            if (index > 0) {
                json.append(',');
            }
            json.append(String.format(Locale.US, "%s", probabilities[index]));
        }
        return json.append("],\"tau\":").append(String.format(Locale.US, "%s", tau)).append('}').toString();
    }

    static String resetJson(String source) {
        if (!source.equals("android") && !source.equals("apple") && !source.equals("laptop")) {
            throw new IllegalArgumentException("Unknown Trinity source");
        }
        return "{\"source\":\"" + source + "\"}";
    }
}
