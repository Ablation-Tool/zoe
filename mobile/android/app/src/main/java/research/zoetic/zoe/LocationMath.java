package research.zoetic.zoe;

final class LocationMath {
    private LocationMath() {
    }

    static double haversineMeters(double firstLatitude, double firstLongitude,
            double secondLatitude, double secondLongitude) {
        for (double value : new double[]{firstLatitude, firstLongitude, secondLatitude, secondLongitude}) {
            if (!Double.isFinite(value)) {
                throw new IllegalArgumentException("coordinates must be finite");
            }
        }
        if (Math.abs(firstLatitude) > 90 || Math.abs(secondLatitude) > 90
                || Math.abs(firstLongitude) > 180 || Math.abs(secondLongitude) > 180) {
            throw new IllegalArgumentException("coordinates are outside valid ranges");
        }
        double first = Math.toRadians(firstLatitude);
        double second = Math.toRadians(secondLatitude);
        double deltaLatitude = second - first;
        double deltaLongitude = Math.toRadians(secondLongitude - firstLongitude);
        double a = Math.sin(deltaLatitude / 2) * Math.sin(deltaLatitude / 2)
                + Math.cos(first) * Math.cos(second)
                * Math.sin(deltaLongitude / 2) * Math.sin(deltaLongitude / 2);
        return 2 * 6371008.8 * Math.asin(Math.min(1, Math.sqrt(a)));
    }
}
