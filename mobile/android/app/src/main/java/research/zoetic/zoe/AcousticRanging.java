package research.zoetic.zoe;

import java.util.ArrayList;
import java.util.List;

final class AcousticRanging {
    static final double SPEED_OF_SOUND_METERS_PER_SECOND = 343.0;

    private AcousticRanging() {
    }

    static final class Peak {
        final int index;
        final double correlation;

        Peak(int index, double correlation) {
            this.index = index;
            this.correlation = correlation;
        }
    }

    static final class Measurement {
        final double rmsDbfs;
        final Double directLagSeconds;
        final Double echoLagSeconds;
        final Double candidateDistanceMeters;
        final Double correlation;

        Measurement(double rmsDbfs, Double directLagSeconds, Double echoLagSeconds,
                Double candidateDistanceMeters, Double correlation) {
            this.rmsDbfs = rmsDbfs;
            this.directLagSeconds = directLagSeconds;
            this.echoLagSeconds = echoLagSeconds;
            this.candidateDistanceMeters = candidateDistanceMeters;
            this.correlation = correlation;
        }
    }

    static short[] chirp(int sampleRate, double frequencyHz, double durationSeconds, double amplitude) {
        if (sampleRate <= 0 || frequencyHz <= 0 || durationSeconds <= 0 || amplitude <= 0 || amplitude > 0.25) {
            throw new IllegalArgumentException("invalid chirp parameters");
        }
        int length = (int) Math.round(sampleRate * durationSeconds);
        short[] result = new short[length];
        for (int index = 0; index < length; index++) {
            double window = 0.5 - 0.5 * Math.cos(2 * Math.PI * index / Math.max(1, length - 1));
            result[index] = (short) Math.round(Short.MAX_VALUE * amplitude * window
                    * Math.sin(2 * Math.PI * frequencyHz * index / sampleRate));
        }
        return result;
    }

    static Measurement analyze(short[] recorded, short[] reference, int sampleRate) {
        if (recorded == null || reference == null || recorded.length < reference.length || reference.length == 0 || sampleRate <= 0) {
            throw new IllegalArgumentException("invalid acoustic input");
        }
        double referenceEnergy = 0;
        double recordedEnergy = 0;
        for (short value : reference) {
            referenceEnergy += (double) value * value;
        }
        for (short value : recorded) {
            recordedEnergy += (double) value * value;
        }
        double rms = Math.sqrt(recordedEnergy / recorded.length) / Short.MAX_VALUE;
        double rmsDbfs = 20 * Math.log10(Math.max(rms, 1e-12));
        List<Peak> peaks = new ArrayList<>();
        double previousCorrelation = 0;
        boolean rising = false;
        for (int start = 0; start <= recorded.length - reference.length; start++) {
            double correlation = 0;
            double segmentEnergy = 0;
            for (int index = 0; index < reference.length; index++) {
                correlation += (double) recorded[start + index] * reference[index];
                segmentEnergy += (double) recorded[start + index] * recorded[start + index];
            }
            double normalized = segmentEnergy == 0 || referenceEnergy == 0 ? 0
                    : correlation / Math.sqrt(referenceEnergy * segmentEnergy);
            if (normalized > previousCorrelation) {
                rising = true;
            } else if (rising && normalized < previousCorrelation) {
                int candidate = start - 1;
                if (previousCorrelation >= 0.25) {
                    peaks.add(new Peak(candidate, previousCorrelation));
                }
                rising = false;
            }
            previousCorrelation = normalized;
        }
        if (peaks.isEmpty()) {
            return new Measurement(rmsDbfs, null, null, null, null);
        }
        Peak direct = peaks.get(0);
        for (Peak candidate : peaks) {
            if (candidate.correlation > direct.correlation) {
                direct = candidate;
            }
        }
        Double directLag = direct.index / (double) sampleRate;
        Peak echo = null;
        for (Peak candidate : peaks) {
            if (candidate.index > direct.index + reference.length
                    && (echo == null || candidate.correlation > echo.correlation)) {
                echo = candidate;
            }
        }
        if (echo == null) {
            return new Measurement(rmsDbfs, directLag, null, null, direct.correlation);
        }
        double echoLag = (echo.index - direct.index) / (double) sampleRate;
        double distance = SPEED_OF_SOUND_METERS_PER_SECOND * echoLag / 2;
        return new Measurement(rmsDbfs, directLag, echoLag, distance, echo.correlation);
    }
}
