package research.zoetic.zoe;

final class RadioRanging {
    private RadioRanging() {
    }

    static double pathLossDistance(int calibratedRssiAtOneMeter, int measuredRssi, double exponent) {
        if (!Double.isFinite(exponent) || exponent <= 0) {
            throw new IllegalArgumentException("path-loss exponent must be positive");
        }
        return Math.pow(10.0, (calibratedRssiAtOneMeter - measuredRssi) / (10.0 * exponent));
    }
}
