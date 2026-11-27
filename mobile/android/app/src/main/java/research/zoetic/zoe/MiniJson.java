package research.zoetic.zoe;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class MiniJson {
    private final String source;
    private int index;

    private MiniJson(String source) {
        this.source = source == null ? "" : source;
    }

    static Map<String, Object> parseObject(String json) {
        Object value = parse(json);
        if (!(value instanceof Map)) {
            throw new IllegalArgumentException("Expected JSON object");
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> map = (Map<String, Object>) value;
        return map;
    }

    static List<Object> parseArray(String json) {
        Object value = parse(json);
        if (!(value instanceof List)) {
            throw new IllegalArgumentException("Expected JSON array");
        }
        @SuppressWarnings("unchecked")
        List<Object> list = (List<Object>) value;
        return list;
    }

    static Object parse(String json) {
        MiniJson parser = new MiniJson(json);
        parser.skipWhitespace();
        Object result = parser.readValue(0);
        parser.skipWhitespace();
        if (parser.index != parser.source.length()) {
            throw new IllegalArgumentException("Trailing characters at index " + parser.index);
        }
        return result;
    }

    static String stringify(Object value) {
        StringBuilder out = new StringBuilder();
        writeValue(out, value);
        return out.toString();
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> asObject(Object value) {
        return value instanceof Map ? (Map<String, Object>) value : null;
    }

    @SuppressWarnings("unchecked")
    static List<Object> asArray(Object value) {
        return value instanceof List ? (List<Object>) value : null;
    }

    static String asString(Map<String, Object> map, String key, String fallback) {
        Object value = map == null ? null : map.get(key);
        return value == null ? fallback : String.valueOf(value);
    }

    static boolean asBoolean(Map<String, Object> map, String key, boolean fallback) {
        Object value = map == null ? null : map.get(key);
        return value instanceof Boolean ? (Boolean) value : fallback;
    }

    static int asInt(Map<String, Object> map, String key, int fallback) {
        Object value = map == null ? null : map.get(key);
        return value instanceof Number ? ((Number) value).intValue() : fallback;
    }

    static double asDouble(Map<String, Object> map, String key, double fallback) {
        Object value = map == null ? null : map.get(key);
        return value instanceof Number ? ((Number) value).doubleValue() : fallback;
    }

    private Object readValue(int depth) {
        if (depth > 48) {
            throw new IllegalArgumentException("JSON nesting too deep");
        }
        skipWhitespace();
        if (index >= source.length()) {
            throw new IllegalArgumentException("Unexpected end of JSON");
        }
        char ch = source.charAt(index);
        if (ch == '{') {
            return readObject(depth + 1);
        }
        if (ch == '[') {
            return readArray(depth + 1);
        }
        if (ch == '"') {
            return readString();
        }
        if (ch == 't' && source.startsWith("true", index)) {
            index += 4;
            return Boolean.TRUE;
        }
        if (ch == 'f' && source.startsWith("false", index)) {
            index += 5;
            return Boolean.FALSE;
        }
        if (ch == 'n' && source.startsWith("null", index)) {
            index += 4;
            return null;
        }
        if (ch == '-' || (ch >= '0' && ch <= '9')) {
            return readNumber();
        }
        throw new IllegalArgumentException("Unexpected JSON token at " + index);
    }

    private Map<String, Object> readObject(int depth) {
        index++;
        Map<String, Object> map = new LinkedHashMap<>();
        skipWhitespace();
        if (index < source.length() && source.charAt(index) == '}') {
            index++;
            return map;
        }
        while (index < source.length()) {
            skipWhitespace();
            if (index >= source.length() || source.charAt(index) != '"') {
                throw new IllegalArgumentException("Expected object key at " + index);
            }
            String key = readString();
            skipWhitespace();
            if (index >= source.length() || source.charAt(index) != ':') {
                throw new IllegalArgumentException("Expected ':' at " + index);
            }
            index++;
            Object value = readValue(depth);
            map.put(key, value);
            skipWhitespace();
            if (index >= source.length()) {
                break;
            }
            char next = source.charAt(index++);
            if (next == '}') {
                return map;
            }
            if (next != ',') {
                throw new IllegalArgumentException("Expected ',' or '}' at " + (index - 1));
            }
        }
        throw new IllegalArgumentException("Unterminated JSON object");
    }

    private List<Object> readArray(int depth) {
        index++;
        List<Object> list = new ArrayList<>();
        skipWhitespace();
        if (index < source.length() && source.charAt(index) == ']') {
            index++;
            return list;
        }
        while (index < source.length()) {
            list.add(readValue(depth));
            skipWhitespace();
            if (index >= source.length()) {
                break;
            }
            char next = source.charAt(index++);
            if (next == ']') {
                return list;
            }
            if (next != ',') {
                throw new IllegalArgumentException("Expected ',' or ']' at " + (index - 1));
            }
        }
        throw new IllegalArgumentException("Unterminated JSON array");
    }

    private String readString() {
        index++;
        StringBuilder out = new StringBuilder();
        while (index < source.length()) {
            char ch = source.charAt(index++);
            if (ch == '"') {
                return out.toString();
            }
            if (ch == '\\') {
                if (index >= source.length()) {
                    throw new IllegalArgumentException("Incomplete escape");
                }
                char esc = source.charAt(index++);
                switch (esc) {
                    case '"', '\\', '/' -> out.append(esc);
                    case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f');
                    case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r');
                    case 't' -> out.append('\t');
                    case 'u' -> {
                        if (index + 4 > source.length()) {
                            throw new IllegalArgumentException("Incomplete unicode escape");
                        }
                        out.append((char) Integer.parseInt(source.substring(index, index + 4), 16));
                        index += 4;
                    }
                    default -> throw new IllegalArgumentException("Invalid escape \\" + esc);
                }
            } else {
                out.append(ch);
            }
        }
        throw new IllegalArgumentException("Unterminated JSON string");
    }

    private Number readNumber() {
        int start = index;
        boolean decimal = false;
        if (source.charAt(index) == '-') {
            index++;
        }
        while (index < source.length()) {
            char ch = source.charAt(index);
            if (ch >= '0' && ch <= '9') {
                index++;
            } else if (ch == '.' || ch == 'e' || ch == 'E' || ch == '+' || ch == '-') {
                decimal = true;
                index++;
            } else {
                break;
            }
        }
        String token = source.substring(start, index);
        try {
            if (!decimal) {
                long v = Long.parseLong(token);
                if (v >= Integer.MIN_VALUE && v <= Integer.MAX_VALUE) {
                    return (int) v;
                }
                return v;
            }
            return Double.parseDouble(token);
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException("Invalid JSON number: " + token, error);
        }
    }

    private void skipWhitespace() {
        while (index < source.length()) {
            char ch = source.charAt(index);
            if (ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r') {
                index++;
            } else {
                break;
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static void writeValue(StringBuilder out, Object value) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof Boolean || value instanceof Number) {
            out.append(value);
        } else if (value instanceof Map) {
            out.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeString(out, String.valueOf(entry.getKey()));
                out.append(':');
                writeValue(out, entry.getValue());
            }
            out.append('}');
        } else if (value instanceof List) {
            out.append('[');
            List<?> list = (List<?>) value;
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                writeValue(out, list.get(i));
            }
            out.append(']');
        } else {
            writeString(out, String.valueOf(value));
        }
    }

    private static void writeString(StringBuilder out, String text) {
        out.append('"');
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            switch (ch) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (ch < 0x20) {
                        out.append(String.format("\\u%04x", (int) ch));
                    } else {
                        out.append(ch);
                    }
                }
            }
        }
        out.append('"');
    }
}
