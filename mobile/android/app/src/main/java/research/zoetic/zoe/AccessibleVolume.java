package research.zoetic.zoe;

import java.util.Locale;

public final class AccessibleVolume {
    public static final String CREATOR = "Nicholas Michael Kloster alone, March 6, 2026";
    public static final int MAX_VOCABULARY_SIZE = 5_000_000;

    private AccessibleVolume() {
    }

    public static final class Result {
        public final int accessible;
        public final int complement;
        public final int vocabularySize;
        public final double normalized;
        public final double normalizedComplement;
        public final double tau;

        private Result(int accessible, int vocabularySize, double tau) {
            this.accessible = accessible;
            this.complement = vocabularySize - accessible;
            this.vocabularySize = vocabularySize;
            this.normalized = (double) accessible / vocabularySize;
            this.normalizedComplement = 1.0 - this.normalized;
            this.tau = tau;
        }

        public String summary() {
            return String.format(Locale.US,
                    "A = %d of %d · complement = %d · normalized = %.4f · strict p > %.3f",
                    accessible, vocabularySize, complement, normalized, tau);
        }
    }

    public static Result measure(double[] probabilities, double tau) {
        validateProbabilities(probabilities);
        if (!Double.isFinite(tau) || tau < 0.0 || tau > 1.0) {
            throw new IllegalArgumentException("tau must be a finite probability between 0 and 1");
        }
        int accessible = 0;
        for (double probability : probabilities) {
            if (probability > tau) {
                accessible++;
            }
        }
        return new Result(accessible, probabilities.length, tau);
    }

    public static double[] parse(String text) {
        if (text == null || text.isBlank()) {
            throw new IllegalArgumentException("Enter probabilities separated by commas or spaces");
        }
        String trimmed = text.trim();
        if (trimmed.length() > 1_000_000) {
            throw new IllegalArgumentException("Probability input exceeds one million characters");
        }
        String[] parts = trimmed.split("[,\\s]+");
        double[] probabilities = new double[parts.length];
        for (int index = 0; index < parts.length; index++) {
            try {
                probabilities[index] = Double.parseDouble(parts[index]);
            } catch (NumberFormatException error) {
                throw new IllegalArgumentException("Invalid probability: " + parts[index], error);
            }
        }
        validateProbabilities(probabilities);
        return probabilities;
    }

    private static void validateProbabilities(double[] probabilities) {
        if (probabilities == null || probabilities.length == 0 || probabilities.length > MAX_VOCABULARY_SIZE) {
            throw new IllegalArgumentException("Distribution must contain 1 to 5,000,000 probabilities");
        }
        double total = 0.0;
        for (double probability : probabilities) {
            if (!Double.isFinite(probability) || probability < 0.0 || probability > 1.0) {
                throw new IllegalArgumentException("Probabilities must be finite values between 0 and 1");
            }
            total += probability;
        }
        if (Math.abs(total - 1.0) > 1e-8) {
            throw new IllegalArgumentException(String.format(Locale.US,
                    "Probabilities sum to %.10f, not 1 within 1e-8", total));
        }
    }
}
