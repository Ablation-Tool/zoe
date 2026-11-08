package research.zoetic.zoe;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

final class TrinityClient {
    private static final String ENDPOINT = "http://127.0.0.1:8767";
    private static final int MAX_RESPONSE_BYTES = 1_048_576;

    State fetch() throws IOException {
        return request("GET", "/api/state", null);
    }

    State measure(double[] probabilities, double tau) throws IOException {
        return request("POST", "/api/measure", TrinityMeasurement.measureJson("android", probabilities, tau));
    }

    State reset() throws IOException {
        return request("POST", "/api/reset", TrinityMeasurement.resetJson("android"));
    }

    private State request(String method, String path, String body) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(ENDPOINT + path).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setConnectTimeout(4000);
            connection.setReadTimeout(4000);
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("X-Zoe-Protocol", "1");
            connection.setRequestProperty("Accept", "application/json");
            if (body != null) {
                byte[] payload = body.getBytes(StandardCharsets.UTF_8);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setFixedLengthStreamingMode(payload.length);
                connection.getOutputStream().write(payload);
            }
            int status = connection.getResponseCode();
            InputStream stream = status == 200 ? connection.getInputStream() : connection.getErrorStream();
            String text = readBounded(stream);
            if (status != 200) {
                String message = "Laptop returned HTTP " + status;
                try {
                    message = new JSONObject(text).getString("error");
                } catch (JSONException ignored) {
                }
                throw new IOException(message);
            }
            return parseState(text);
        } catch (JSONException error) {
            throw new IOException("Laptop returned an invalid Trinity state", error);
        } finally {
            connection.disconnect();
        }
    }

    private static String readBounded(InputStream stream) throws IOException {
        if (stream == null) {
            throw new IOException("Laptop returned an empty response");
        }
        try (InputStream input = stream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int total = 0;
            int count;
            while ((count = input.read(buffer)) >= 0) {
                total += count;
                if (total > MAX_RESPONSE_BYTES) {
                    throw new IOException("Laptop response exceeds 1 MiB");
                }
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    static State parseState(String text) throws JSONException {
        JSONObject root = new JSONObject(text);
        if (root.getInt("protocol") != 1 || !root.getString("name").equals("Zoe Trinity")) {
            throw new JSONException("Unsupported Trinity protocol");
        }
        if (!root.getString("creator").equals(AccessibleVolume.CREATOR)) {
            throw new JSONException("Original equation credit is missing");
        }
        int revision = root.getInt("revision");
        if (revision < 0) {
            throw new JSONException("Invalid revision");
        }
        Active active = parseActive(root.getJSONObject("active"));
        JSONObject memory = root.getJSONObject("memory");
        if (!memory.getBoolean("tamperEvidenceOnly")) {
            throw new JSONException("Memory boundary is missing");
        }
        int records = memory.getInt("records");
        if (records < 0 || (memory.getBoolean("enabled") && records < revision)) {
            throw new JSONException("Invalid journal state");
        }
        JSONArray rawEvents = root.getJSONArray("events");
        if (rawEvents.length() > 24) {
            throw new JSONException("Too many retained events");
        }
        List<Event> events = new ArrayList<>();
        int previous = 0;
        for (int index = 0; index < rawEvents.length(); index++) {
            JSONObject value = rawEvents.getJSONObject(index);
            int ordinal = value.getInt("ordinal");
            String source = value.getString("source");
            if (ordinal <= previous || ordinal > revision
                    || !(source.equals("android") || source.equals("apple") || source.equals("laptop"))) {
                throw new JSONException("Invalid event sequence or source");
            }
            JSONObject zoe = value.getJSONObject("zoe");
            JSONObject tiny = value.getJSONObject("tiny");
            events.add(new Event(ordinal, source, value.getDouble("tau"),
                    zoe.getInt("accessible"), zoe.getInt("vocabularySize"),
                    tiny.getInt("accessible"), tiny.getInt("vocabularySize")));
            previous = ordinal;
        }
        return new State(revision, active, memory.getBoolean("enabled"), records, events);
    }

    private static Active parseActive(JSONObject value) throws JSONException {
        double[] probabilities = doubles(value.getJSONArray("probabilities"));
        double tau = value.getDouble("tau");
        TrinityMeasurement measurement = new TrinityMeasurement(probabilities, tau);
        JSONObject zoe = value.getJSONObject("zoe");
        AccessibleVolume.Result result = measurement.result();
        if (zoe.getInt("accessible") != result.accessible
                || zoe.getInt("complement") != result.complement
                || zoe.getInt("vocabularySize") != result.vocabularySize) {
            throw new JSONException("Mobile measurement does not match the distribution");
        }
        JSONObject rawTiny = value.getJSONObject("tiny");
        JSONArray rawUnits = rawTiny.getJSONArray("probabilities");
        if (rawUnits.length() != probabilities.length) {
            throw new JSONException("Tiny vector size differs from mobile");
        }
        int[] units = new int[rawUnits.length()];
        int sum = 0;
        int tinyTau = rawTiny.getInt("tau");
        if (tinyTau < 0 || tinyTau > CellCodec.SCALE) {
            throw new JSONException("Invalid quantized threshold");
        }
        for (int index = 0; index < units.length; index++) {
            units[index] = rawUnits.getInt(index);
            if (units[index] < 0 || units[index] > CellCodec.SCALE) {
                throw new JSONException("Invalid Q0.15 probability");
            }
            sum += units[index];
        }
        if (sum != CellCodec.SCALE) {
            throw new JSONException("Q0.15 probabilities do not sum to one");
        }
        int accessible = 0;
        for (int unit : units) {
            if (unit > tinyTau) {
                accessible++;
            }
        }
        int complement = units.length - accessible;
        if (rawTiny.getInt("accessible") != accessible
                || rawTiny.getInt("complement") != complement
                || rawTiny.getInt("vocabularySize") != units.length) {
            throw new JSONException("Tiny measurement does not match Q0.15 inputs");
        }
        byte[] request = new byte[7 + units.length * 2];
        request[0] = (byte) 0x80;
        request[1] = 0x02;
        request[4] = (byte) (2 + units.length * 2);
        putShort(request, 5, tinyTau);
        for (int index = 0; index < units.length; index++) {
            putShort(request, 7 + index * 2, units[index]);
        }
        byte[] response = new byte[10];
        putShort(response, 0, accessible);
        putShort(response, 2, complement);
        putShort(response, 4, units.length);
        putShort(response, 6, tinyTau);
        response[8] = (byte) 0x90;
        if (!rawTiny.getString("request").equals(CellCodec.hex(request))
                || !rawTiny.getString("response").equals(CellCodec.hex(response))) {
            throw new JSONException("Tiny APDU witness does not match its measurement");
        }
        boolean changed = accessible != result.accessible || tinyTau != (int) (tau * CellCodec.SCALE);
        if (value.getBoolean("quantizationChanged") != changed) {
            throw new JSONException("Quantization comparison is inconsistent");
        }
        return new Active(measurement, new TinyWitness(accessible, complement, units.length, tinyTau,
                CellCodec.hex(request), CellCodec.hex(response), changed));
    }

    private static double[] doubles(JSONArray array) throws JSONException {
        if (array.length() < 1 || array.length() > TrinityMeasurement.MAX_PROBABILITIES) {
            throw new JSONException("Invalid Trinity distribution size");
        }
        double[] values = new double[array.length()];
        for (int index = 0; index < values.length; index++) {
            values[index] = array.getDouble(index);
        }
        return values;
    }

    private static void putShort(byte[] data, int offset, int value) {
        data[offset] = (byte) (value >>> 8);
        data[offset + 1] = (byte) value;
    }

    static final class State {
        final int revision;
        final Active active;
        final boolean memoryEnabled;
        final int memoryRecords;
        final List<Event> events;

        State(int revision, Active active, boolean memoryEnabled, int memoryRecords, List<Event> events) {
            this.revision = revision;
            this.active = active;
            this.memoryEnabled = memoryEnabled;
            this.memoryRecords = memoryRecords;
            this.events = Collections.unmodifiableList(new ArrayList<>(events));
        }
    }

    static final class Active {
        final TrinityMeasurement mobile;
        final TinyWitness tiny;

        Active(TrinityMeasurement mobile, TinyWitness tiny) {
            this.mobile = mobile;
            this.tiny = tiny;
        }
    }

    static final class TinyWitness {
        final int accessible;
        final int complement;
        final int vocabularySize;
        final int tau;
        final String request;
        final String response;
        final boolean changed;

        TinyWitness(int accessible, int complement, int vocabularySize, int tau,
                    String request, String response, boolean changed) {
            this.accessible = accessible;
            this.complement = complement;
            this.vocabularySize = vocabularySize;
            this.tau = tau;
            this.request = request;
            this.response = response;
            this.changed = changed;
        }
    }

    static final class Event {
        final int ordinal;
        final String source;
        final double tau;
        final int zoeAccessible;
        final int zoeSize;
        final int tinyAccessible;
        final int tinySize;

        Event(int ordinal, String source, double tau, int zoeAccessible, int zoeSize,
              int tinyAccessible, int tinySize) {
            this.ordinal = ordinal;
            this.source = source;
            this.tau = tau;
            this.zoeAccessible = zoeAccessible;
            this.zoeSize = zoeSize;
            this.tinyAccessible = tinyAccessible;
            this.tinySize = tinySize;
        }
    }
}
