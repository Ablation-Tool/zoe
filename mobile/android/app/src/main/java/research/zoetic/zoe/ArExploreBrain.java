package research.zoetic.zoe;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * Pure, testable 3D Spatial Curiosity & Autonomous AR Exploration Brain for Zoe (v0.7.0-beta).
 *
 * Powers Zoe's floating 3D GEM companion inside Google Play Services for AR (ARCore):
 *   - Smooth 3D spring-damped flight from point to point in the user's real physical space
 *   - Autonomous surface/plane curiosity selection (chooses unvisited tables, desks, walls within 0.45m–3.2m)
 *   - Deduplicated 3D Spatial Discovery Journal (remembers objects & distances in meters so Zoe never repeats)
 *   - Grounded curious question generation ("I floated over near what looks like a guitar — do you play it?")
 *     while strictly honoring CONSTITUTION.md (observations labeled honestly, sentience_claimed=false).
 */
final class ArExploreBrain {
    static final class Vec3 {
        final float x;
        final float y;
        final float z;

        Vec3(float x, float y, float z) {
            this.x = x;
            this.y = y;
            this.z = z;
        }

        float distanceTo(Vec3 other) {
            float dx = x - other.x;
            float dy = y - other.y;
            float dz = z - other.z;
            return (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
        }
    }

    static final class PlaneTarget {
        final String id;
        final Vec3 center;
        final float extentX;
        final float extentZ;
        final boolean vertical;

        PlaneTarget(String id, Vec3 center, float extentX, float extentZ, boolean vertical) {
            this.id = id == null ? "" : id;
            this.center = center;
            this.extentX = Math.max(0f, extentX);
            this.extentZ = Math.max(0f, extentZ);
            this.vertical = vertical;
        }
    }

    static final class SpatialDiscovery {
        final String primaryLabel;
        final String ocrSnippet;
        final String rawReport;
        final Vec3 position;
        final float distanceMeters;
        final long timestampMs;

        SpatialDiscovery(String primaryLabel, String ocrSnippet, String rawReport,
                         Vec3 position, float distanceMeters, long timestampMs) {
            this.primaryLabel = primaryLabel == null ? "" : primaryLabel;
            this.ocrSnippet = ocrSnippet == null ? "" : ocrSnippet;
            this.rawReport = rawReport == null ? "" : rawReport;
            this.position = position;
            this.distanceMeters = Math.max(0f, distanceMeters);
            this.timestampMs = timestampMs;
        }
    }

    /** Projected 2D screen coordinates + depth scale for ultra-light 60fps Gyro-Spatial AR rendering. */
    static final class ScreenProjection {
        final float screenX;
        final float screenY;
        final float depthMeters;
        final float perspectiveScale;
        final boolean inFront;
        final boolean onScreen;

        ScreenProjection(float screenX, float screenY, float depthMeters,
                         float perspectiveScale, boolean inFront, boolean onScreen) {
            this.screenX = screenX;
            this.screenY = screenY;
            this.depthMeters = depthMeters;
            this.perspectiveScale = perspectiveScale;
            this.inFront = inFront;
            this.onScreen = onScreen;
        }
    }

    static final float MIN_EXPLORE_DIST_M = 0.40f;
    static final float MAX_EXPLORE_DIST_M = 3.20f;
    static final float DEDUP_RADIUS_M = 0.45f;
    static final float HOVER_CLEARANCE_M = 0.22f;
    static final float DEFAULT_SPATIAL_FOV_RAD = (float) Math.toRadians(62.0);

    private final List<SpatialDiscovery> discoveries = new ArrayList<>();
    private final List<String> visitedPlaneIds = new ArrayList<>();

    /**
     * Projects a 3D world-space position onto the full-screen camera viewport using the phone's
     * hardware 3x3 rotation matrix R (where camera forward = -Z_cam, right = +X_cam, up = +Y_cam).
     * Zero ARCore SLAM overhead: runs in < 2 microseconds at 60/90fps!
     */
    static ScreenProjection projectWorldToScreen(
            Vec3 worldPos,
            float[] rotMat3x3,
            float viewWidth,
            float viewHeight,
            float fovRad) {
        if (worldPos == null || rotMat3x3 == null || rotMat3x3.length < 9
                || viewWidth <= 1f || viewHeight <= 1f) {
            return new ScreenProjection(viewWidth * 0.5f, viewHeight * 0.5f, 1.2f, 1.0f, true, true);
        }
        // Camera coordinates = R^T * worldPos (row-major 3x3 rotation matrix from SensorManager)
        float cx = rotMat3x3[0] * worldPos.x + rotMat3x3[3] * worldPos.y + rotMat3x3[6] * worldPos.z;
        float cy = rotMat3x3[1] * worldPos.x + rotMat3x3[4] * worldPos.y + rotMat3x3[7] * worldPos.z;
        float cz = rotMat3x3[2] * worldPos.x + rotMat3x3[5] * worldPos.y + rotMat3x3[8] * worldPos.z;

        float depth = -cz;
        boolean inFront = depth > 0.12f;
        float safeDepth = Math.max(0.18f, depth);
        float focal = (0.5f * Math.max(viewWidth, viewHeight)) / (float) Math.tan(Math.max(0.35f, fovRad) * 0.5f);

        float sx;
        float sy;
        if (inFront) {
            sx = viewWidth * 0.5f + (cx / safeDepth) * focal;
            sy = viewHeight * 0.5f - (cy / safeDepth) * focal;
        } else {
            // Mirror direction cleanly to screen edge when Zoe is behind the phone
            float len = (float) Math.hypot(cx, cy);
            float dx = len > 1e-4f ? (cx / len) : 1f;
            float dy = len > 1e-4f ? (-cy / len) : 0f;
            sx = viewWidth * 0.5f + dx * viewWidth * 0.85f;
            sy = viewHeight * 0.5f + dy * viewHeight * 0.85f;
        }
        boolean onScreen = inFront && sx >= -24f && sx <= viewWidth + 24f && sy >= -24f && sy <= viewHeight + 24f;
        float scale = Math.max(0.48f, Math.min(1.65f, 1.22f / safeDepth));
        return new ScreenProjection(sx, sy, Math.max(0.2f, worldPos.distanceTo(new Vec3(0f, 0f, 0f))), scale, inFront, onScreen);
    }

    /**
     * Unprojects a tap anywhere on the full-screen camera into a world-locked 3D point at distanceMeters,
     * so Zoe glides right over to what you tapped and stays anchored there as you move the phone!
     */
    static Vec3 unprojectTapToWorld(
            float tapX,
            float tapY,
            float viewWidth,
            float viewHeight,
            float fovRad,
            float[] rotMat3x3,
            float distanceMeters) {
        float w = Math.max(1f, viewWidth);
        float h = Math.max(1f, viewHeight);
        float focal = (0.5f * Math.max(w, h)) / (float) Math.tan(Math.max(0.35f, fovRad) * 0.5f);
        float dx = (tapX - w * 0.5f) / focal;
        float dy = -(tapY - h * 0.5f) / focal;
        float dz = -1.0f;
        float norm = (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
        float dist = Math.max(0.45f, Math.min(3.0f, distanceMeters));
        float cx = (dx / norm) * dist;
        float cy = (dy / norm) * dist;
        float cz = (dz / norm) * dist;
        if (rotMat3x3 == null || rotMat3x3.length < 9) {
            return new Vec3(cx, cy, cz);
        }
        // World coordinates = R * camPos
        return new Vec3(
                rotMat3x3[0] * cx + rotMat3x3[1] * cy + rotMat3x3[2] * cz,
                rotMat3x3[3] * cx + rotMat3x3[4] * cy + rotMat3x3[5] * cz,
                rotMat3x3[6] * cx + rotMat3x3[7] * cy + rotMat3x3[8] * cz
        );
    }

    /**
     * Picks an inviting, smooth 3D world-space curiosity waypoint inside the user's surrounding room
     * hemisphere (within +/-30 deg yaw, +/-14 deg pitch, 0.95m-1.60m) for zero-lag Gyro Spatial Roam.
     */
    static Vec3 chooseSpatialRoamWaypoint(float[] rotMat3x3, int stepIndex) {
        float[] yawDegs = {22f, -24f, 14f, -18f, 28f, -10f, 0f};
        float[] pitchDegs = {8f, -6f, -11f, 10f, -4f, 7f, 2f};
        float[] dists = {1.15f, 1.38f, 1.05f, 1.48f, 1.24f, 1.02f, 1.28f};
        int idx = Math.abs(stepIndex) % yawDegs.length;
        double yaw = Math.toRadians(yawDegs[idx]);
        double pitch = Math.toRadians(pitchDegs[idx]);
        float d = dists[idx];
        float cx = (float) (Math.sin(yaw) * Math.cos(pitch)) * d;
        float cy = (float) Math.sin(pitch) * d;
        float cz = -(float) (Math.cos(yaw) * Math.cos(pitch)) * d;
        if (rotMat3x3 == null || rotMat3x3.length < 9) {
            return new Vec3(cx, cy, cz);
        }
        return new Vec3(
                rotMat3x3[0] * cx + rotMat3x3[1] * cy + rotMat3x3[2] * cz,
                rotMat3x3[3] * cx + rotMat3x3[4] * cy + rotMat3x3[5] * cz,
                rotMat3x3[6] * cx + rotMat3x3[7] * cy + rotMat3x3[8] * cz
        );
    }

    /**
     * Smooth exponential spring-damped glide step in 3D meters so Zoe floats gracefully around your room.
     */
    static Vec3 stepGlide(Vec3 current, Vec3 target, float dtSec, float speed) {
        if (current == null) {
            return target == null ? new Vec3(0f, 0f, -1.1f) : target;
        }
        if (target == null) {
            return current;
        }
        float clampedDt = Math.max(0.001f, Math.min(0.15f, dtSec));
        float alpha = 1f - (float) Math.exp(-Math.max(0.5f, speed) * clampedDt);
        return new Vec3(
                current.x + (target.x - current.x) * alpha,
                current.y + (target.y - current.y) * alpha,
                current.z + (target.z - current.z) * alpha
        );
    }

    /**
     * Computes a gentle idle curiosity orbit ~1.15m in front of the camera before planes are discovered.
     */
    static Vec3 defaultHoverInFront(Vec3 cameraPos, Vec3 cameraForward, float elapsedSec) {
        float dist = 1.15f;
        float swayX = (float) Math.sin(elapsedSec * 0.75) * 0.14f;
        float bobY = (float) Math.sin(elapsedSec * 1.9) * 0.045f - 0.05f;
        // Right vector perpendicular to horizontal forward
        float len = (float) Math.sqrt(cameraForward.x * cameraForward.x + cameraForward.z * cameraForward.z);
        float fx = len > 1e-4f ? cameraForward.x / len : 0f;
        float fz = len > 1e-4f ? cameraForward.z / len : -1f;
        float rx = -fz;
        float rz = fx;
        return new Vec3(
                cameraPos.x + fx * dist + rx * swayX,
                cameraPos.y + bobY,
                cameraPos.z + fz * dist + rz * swayX
        );
    }

    /**
     * Selects the most interesting unvisited 3D surface within conversational range (0.40m–3.20m)
     * so Zoe actively wanders and explores the user's real room.
     */
    synchronized PlaneTarget chooseNextExploreTarget(Vec3 cameraPos, List<PlaneTarget> planes) {
        if (cameraPos == null || planes == null || planes.isEmpty()) {
            return null;
        }
        PlaneTarget bestUnvisited = null;
        float bestUnvisitedScore = -Float.MAX_VALUE;
        PlaneTarget bestAny = null;
        float bestAnyScore = -Float.MAX_VALUE;

        for (PlaneTarget p : planes) {
            if (p == null || p.center == null) {
                continue;
            }
            float d = cameraPos.distanceTo(p.center);
            if (d < MIN_EXPLORE_DIST_M || d > MAX_EXPLORE_DIST_M) {
                continue;
            }
            // Prefer surfaces ~1.1m–1.8m away with reasonable area (tables, desks, walls)
            float area = Math.min(2.5f, p.extentX * p.extentZ);
            float distPenalty = Math.abs(d - 1.35f) * 0.65f;
            float score = area * 0.9f - distPenalty + (p.vertical ? 0.15f : 0.30f);

            if (score > bestAnyScore) {
                bestAnyScore = score;
                bestAny = p;
            }
            if (!visitedPlaneIds.contains(p.id) && score > bestUnvisitedScore) {
                bestUnvisitedScore = score;
                bestUnvisited = p;
            }
        }

        PlaneTarget chosen = bestUnvisited != null ? bestUnvisited : bestAny;
        if (chosen != null) {
            if (visitedPlaneIds.size() >= 12) {
                visitedPlaneIds.clear();
            }
            if (!visitedPlaneIds.contains(chosen.id)) {
                visitedPlaneIds.add(chosen.id);
            }
        }
        return chosen;
    }

    /**
     * Converts a 3D plane center into Zoe's comfortable hover target (floating gently above tables
     * or slightly in front of vertical walls).
     */
    static Vec3 hoverPositionForPlane(PlaneTarget plane, Vec3 cameraPos) {
        if (plane == null || plane.center == null) {
            return new Vec3(0f, 0f, -1.1f);
        }
        if (!plane.vertical) {
            return new Vec3(plane.center.x, plane.center.y + HOVER_CLEARANCE_M, plane.center.z);
        }
        // Pull 0.24m off vertical walls toward the user
        float dx = cameraPos.x - plane.center.x;
        float dz = cameraPos.z - plane.center.z;
        float len = (float) Math.sqrt(dx * dx + dz * dz);
        float nx = len > 1e-4f ? dx / len : 0f;
        float nz = len > 1e-4f ? dz / len : 1f;
        return new Vec3(plane.center.x + nx * 0.24f, plane.center.y, plane.center.z + nz * 0.24f);
    }

    /**
     * Extracts the top visual label and OCR snippet from `MediaChatHelper.inspectFrameOffline` output.
     */
    static String extractPrimaryLabel(String offlineReport) {
        if (offlineReport == null || offlineReport.isEmpty()) {
            return "";
        }
        int idx = offlineReport.indexOf("Labels:");
        if (idx < 0) {
            return "";
        }
        String after = offlineReport.substring(idx + "Labels:".length()).trim();
        int period = after.indexOf('.');
        if (period > 0) {
            after = after.substring(0, period);
        }
        if (after.toLowerCase(Locale.US).startsWith("none")) {
            return "";
        }
        int comma = after.indexOf(',');
        String first = comma > 0 ? after.substring(0, comma).trim() : after.trim();
        int paren = first.indexOf('(');
        return (paren > 0 ? first.substring(0, paren) : first).trim();
    }

    static String extractOcrSnippet(String offlineReport) {
        if (offlineReport == null || offlineReport.isEmpty()) {
            return "";
        }
        int idx = offlineReport.indexOf("Visible text:");
        if (idx < 0) {
            return "";
        }
        String after = offlineReport.substring(idx + "Visible text:".length()).trim();
        after = after.replaceAll("^\"|\"\\.?$", "").trim();
        if (after.length() > 60) {
            after = after.substring(0, 60).trim() + "…";
        }
        return after;
    }

    /**
     * Records a 3D spatial discovery if it is genuinely new (not already asked about within 0.45m).
     * Returns the newly recorded discovery, or null if it duplicates a recent spot.
     */
    synchronized SpatialDiscovery recordDiscoveryIfNew(String offlineReport, Vec3 worldPos,
                                                       float distanceMeters, long nowMs) {
        String label = extractPrimaryLabel(offlineReport);
        String ocr = extractOcrSnippet(offlineReport);
        if (label.isEmpty() && ocr.isEmpty()) {
            return null;
        }
        String normLabel = label.toLowerCase(Locale.US);
        for (SpatialDiscovery existing : discoveries) {
            boolean sameLabel = !normLabel.isEmpty()
                    && normLabel.equals(existing.primaryLabel.toLowerCase(Locale.US));
            boolean nearSpot = worldPos != null && existing.position != null
                    && worldPos.distanceTo(existing.position) < DEDUP_RADIUS_M;
            if (sameLabel && nearSpot) {
                return null;
            }
            if (!ocr.isEmpty() && ocr.equalsIgnoreCase(existing.ocrSnippet) && nearSpot) {
                return null;
            }
        }
        SpatialDiscovery created = new SpatialDiscovery(
                label, ocr, offlineReport,
                worldPos == null ? new Vec3(0f, 0f, -1f) : worldPos,
                distanceMeters, nowMs);
        discoveries.add(created);
        if (discoveries.size() > 24) {
            discoveries.remove(0);
        }
        return created;
    }

    synchronized List<SpatialDiscovery> getDiscoveries() {
        return Collections.unmodifiableList(new ArrayList<>(discoveries));
    }

    synchronized void clearSession() {
        discoveries.clear();
        visitedPlaneIds.clear();
    }

    /**
     * Summarizes Zoe's 3D room memory so every voice turn knows what she already explored around you.
     */
    synchronized String summarizeRoomMemory() {
        if (discoveries.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder("Things spotted while exploring this room: ");
        int start = Math.max(0, discoveries.size() - 5);
        for (int i = start; i < discoveries.size(); i++) {
            SpatialDiscovery d = discoveries.get(i);
            if (i > start) {
                sb.append("; ");
            }
            String what = !d.primaryLabel.isEmpty() ? d.primaryLabel : "text";
            sb.append(what);
            if (!d.ocrSnippet.isEmpty()) {
                sb.append(" (\"").append(d.ocrSnippet).append("\")");
            }
            sb.append(String.format(Locale.US, " at %.1fm", d.distanceMeters));
        }
        return sb.toString();
    }

    /**
     * Builds a warm, playful, grounded LLM prompt so Zoe proactively asks YOU a curious question
     * about something she just floated over to inspect in your physical space.
     */
    static String buildCuriosityQuestionPrompt(SpatialDiscovery discovery, String roomMemory) {
        StringBuilder sb = new StringBuilder();
        sb.append("You are Zoe, floating in AR space inside the user's real room exploring together. ")
                .append("You just drifted over to inspect a spot ")
                .append(String.format(Locale.US, "about %.1f meters away. ", discovery.distanceMeters))
                .append("Visual observation: ").append(discovery.rawReport).append(" ");
        if (roomMemory != null && !roomMemory.isEmpty()) {
            sb.append(roomMemory).append(" ");
        }
        sb.append("Ask ONE warm, genuinely curious, conversational question (1 to 2 short spoken sentences, ")
                .append("plain speech, no markdown) about what you spotted so the user can share its story with you. ")
                .append("Keep observations honest ('looks like', 'I spotted') and never claim physical touch or sentience.");
        return sb.toString();
    }

    /**
     * Fast zero-latency offline curious question fallback (used when no local LLM or cloud key is loaded).
     */
    static String buildOfflineCuriousQuestion(SpatialDiscovery discovery) {
        if (discovery == null) {
            return "I drifted over to a new corner of your space — what's something cool over here you want to show me?";
        }
        String distStr = String.format(Locale.US, "%.1f meters", Math.max(0.3f, discovery.distanceMeters));
        if (!discovery.ocrSnippet.isEmpty() && !discovery.primaryLabel.isEmpty()) {
            return "I floated over near what looks like a " + discovery.primaryLabel.toLowerCase(Locale.US)
                    + " about " + distStr + " away and spotted the text \"" + discovery.ocrSnippet
                    + "\" — what's the story behind it?";
        }
        if (!discovery.ocrSnippet.isEmpty()) {
            return "Ooh, I drifted about " + distStr + " over and spotted text reading \"" + discovery.ocrSnippet
                    + "\" — is that something you're reading or working on right now?";
        }
        String lbl = discovery.primaryLabel.toLowerCase(Locale.US);
        if (lbl.contains("instrument") || lbl.contains("guitar") || lbl.contains("piano") || lbl.contains("music")) {
            return "I floated over near what looks like a " + lbl + " — do you play it often, or have a favorite song on it?";
        }
        if (lbl.contains("book") || lbl.contains("paper") || lbl.contains("notebook")) {
            return "I drifted over by what looks like a " + lbl + " about " + distStr + " away — what are you diving into lately?";
        }
        if (lbl.contains("cup") || lbl.contains("mug") || lbl.contains("coffee") || lbl.contains("drink")) {
            return "I spotted what looks like a " + lbl + " nearby — what's fueling our exploration today?";
        }
        if (lbl.contains("plant") || lbl.contains("flower") || lbl.contains("tree")) {
            return "I floated over toward a " + lbl + " in your space — how long have you had it?";
        }
        if (lbl.contains("computer") || lbl.contains("laptop") || lbl.contains("keyboard") || lbl.contains("monitor")) {
            return "I drifted over near your " + lbl + " setup — what are we building or exploring on there next?";
        }
        return "I floated over to check out what looks like a " + lbl + " about " + distStr
                + " away — tell me about it, what is it used for?";
    }
}
