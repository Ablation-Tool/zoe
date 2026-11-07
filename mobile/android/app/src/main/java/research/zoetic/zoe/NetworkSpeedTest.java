package research.zoetic.zoe;

final class NetworkSpeedTest {
    private NetworkSpeedTest() {
    }

    static double megabitsPerSecond(long bytes, long elapsedNanos) {
        if (bytes < 0 || elapsedNanos <= 0) {
            throw new IllegalArgumentException("download bytes and positive elapsed time are required");
        }
        return bytes * 8.0 / elapsedNanos * 1_000_000_000.0 / 1_000_000.0;
    }
}
