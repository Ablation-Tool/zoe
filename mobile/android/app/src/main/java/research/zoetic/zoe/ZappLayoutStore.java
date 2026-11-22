package research.zoetic.zoe;

import android.content.Context;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

final class ZappLayoutStore {
    static final List<String> DEFAULT_ORDER = Collections.unmodifiableList(Arrays.asList(
            "vision",
            "talk",
            "live",
            "creative",
            "arcade",
            "vault",
            "journal",
            "studio",
            "maps",
            "volume",
            "trinity",
            "kit",
            "device",
            "safeconvert",
            "guide"));
    private static final String PREFS_NAME = "zoe_zapps_prefs";
    private static final String KEY_ORDER = "zapp_order_v1";

    private ZappLayoutStore() {
    }

    static List<String> normalizeOrder(List<String> raw) {
        Set<String> allowed = new LinkedHashSet<>(DEFAULT_ORDER);
        List<String> out = new ArrayList<>();
        if (raw != null) {
            for (String candidate : raw) {
                if (candidate != null) {
                    String trimmed = candidate.trim();
                    if (allowed.contains(trimmed) && !out.contains(trimmed)) {
                        out.add(trimmed);
                    }
                }
            }
        }
        for (String id : DEFAULT_ORDER) {
            if (!out.contains(id)) {
                out.add(id);
            }
        }
        return out;
    }

    static List<String> moveUp(List<String> order, String id) {
        List<String> next = normalizeOrder(order);
        int idx = next.indexOf(id);
        if (idx > 0) {
            Collections.swap(next, idx, idx - 1);
        }
        return next;
    }

    static List<String> moveDown(List<String> order, String id) {
        List<String> next = normalizeOrder(order);
        int idx = next.indexOf(id);
        if (idx >= 0 && idx < next.size() - 1) {
            Collections.swap(next, idx, idx + 1);
        }
        return next;
    }

    static List<String> moveToTop(List<String> order, String id) {
        List<String> next = normalizeOrder(order);
        if (id != null && DEFAULT_ORDER.contains(id)) {
            next.remove(id);
            next.add(0, id);
        }
        return next;
    }

    static String serialize(List<String> order) {
        return String.join(",", normalizeOrder(order));
    }

    static List<String> deserialize(String saved) {
        if (saved == null || saved.trim().isEmpty()) {
            return new ArrayList<>(DEFAULT_ORDER);
        }
        return normalizeOrder(Arrays.asList(saved.split(",")));
    }

    static List<String> loadOrder(Context context) {
        String raw = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(KEY_ORDER, "");
        return deserialize(raw);
    }

    static void saveOrder(Context context, List<String> order) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_ORDER, serialize(order))
                .apply();
    }

    static List<String> resetOrder(Context context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .remove(KEY_ORDER)
                .apply();
        return new ArrayList<>(DEFAULT_ORDER);
    }
}
