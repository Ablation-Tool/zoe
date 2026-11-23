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
        if (worldPos == null) {
            return new ScreenProjection(viewWidth * 0.5f, viewHeight * 0.5f, 1.2f, 1.0f, true, true);
        }
        return projectWorldToScreen(worldPos.x, worldPos.y, worldPos.z, rotMat3x3, viewWidth, viewHeight, fovRad);
    }

    /** Zero-Vec3-allocation overload for smooth 60/90fps onDraw projection. */
    static ScreenProjection projectWorldToScreen(
            float wx,
            float wy,
            float wz,
            float[] rotMat3x3,
            float viewWidth,
            float viewHeight,
            float fovRad) {
        if (rotMat3x3 == null || rotMat3x3.length < 9 || viewWidth <= 1f || viewHeight <= 1f) {
            return new ScreenProjection(viewWidth * 0.5f, viewHeight * 0.5f, 1.2f, 1.0f, true, true);
        }
        // Camera coordinates = R^T * worldPos (row-major 3x3 rotation matrix from SensorManager)
        float cx = rotMat3x3[0] * wx + rotMat3x3[3] * wy + rotMat3x3[6] * wz;
        float cy = rotMat3x3[1] * wx + rotMat3x3[4] * wy + rotMat3x3[7] * wz;
        float cz = rotMat3x3[2] * wx + rotMat3x3[5] * wy + rotMat3x3[8] * wz;

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
        float dist = (float) Math.sqrt(wx * wx + wy * wy + wz * wz);
        return new ScreenProjection(sx, sy, Math.max(0.2f, dist), scale, inFront, onScreen);
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
            return "I drifted over to a new corner of your space. What's something cool over here you want to show me?";
        }
        String distStr = String.format(Locale.US, "%.1f meters", Math.max(0.3f, discovery.distanceMeters));
        if (!discovery.ocrSnippet.isEmpty() && !discovery.primaryLabel.isEmpty()) {
            return "I floated over near what looks like a " + discovery.primaryLabel.toLowerCase(Locale.US)
                    + " about " + distStr + " away and spotted the text \"" + discovery.ocrSnippet
                    + "\". What's the story behind it?";
        }
        if (!discovery.ocrSnippet.isEmpty()) {
            return "Ooh, I drifted about " + distStr + " over and spotted text reading \"" + discovery.ocrSnippet
                    + "\". Is that something you're reading or working on right now?";
        }
        String lbl = discovery.primaryLabel.toLowerCase(Locale.US);
        if (lbl.contains("instrument") || lbl.contains("guitar") || lbl.contains("piano") || lbl.contains("music")) {
            return "I floated over near what looks like a " + lbl + ". Do you play it often, or have a favorite song on it?";
        }
        if (lbl.contains("book") || lbl.contains("paper") || lbl.contains("notebook")) {
            return "I drifted over by what looks like a " + lbl + " about " + distStr + " away. What are you diving into lately?";
        }
        if (lbl.contains("cup") || lbl.contains("mug") || lbl.contains("coffee") || lbl.contains("drink")) {
            return "I spotted what looks like a " + lbl + " nearby. What's fueling our exploration today?";
        }
        if (lbl.contains("plant") || lbl.contains("flower") || lbl.contains("tree")) {
            return "I floated over toward a " + lbl + " in your space. How long have you had it?";
        }
        if (lbl.contains("computer") || lbl.contains("laptop") || lbl.contains("keyboard") || lbl.contains("monitor")) {
            return "I drifted over near your " + lbl + " setup. What are we building or exploring on there next?";
        }
        return "I floated over to check out what looks like a " + lbl + " about " + distStr
                + " away. Tell me about it, what is it used for?";
    }

    /** Normalized viewport spot selected by Zoe's visual-curiosity saliency picker. */
    static final class CuriositySpot {
        final float u;
        final float v;
        final float distanceMeters;
        final float saliencyScore;

        CuriositySpot(float u, float v, float distanceMeters, float saliencyScore) {
            this.u = Math.max(0.18f, Math.min(0.82f, u));
            this.v = Math.max(0.22f, Math.min(0.70f, v));
            this.distanceMeters = Math.max(0.85f, Math.min(1.65f, distanceMeters));
            this.saliencyScore = Math.max(0f, saliencyScore);
        }
    }

    /**
     * Picks an intriguing visual hotspot inside the comfortable camera viewport using fast local
     * edge + chroma contrast while avoiding the spot Zoe just inspected.
     * Pure Java (zero Android dependencies) so it runs in <2 ms and is 100% unit-testable.
     */
    static CuriositySpot pickVisualCuriositySpot(
            int[] argbPixels, int width, int height, float lastU, float lastV, int stepIndex) {
        float[] fallbackU = {0.34f, 0.66f, 0.50f, 0.28f, 0.72f, 0.44f};
        float[] fallbackV = {0.42f, 0.36f, 0.54f, 0.52f, 0.48f, 0.34f};
        float[] dists = {1.12f, 1.24f, 1.05f, 1.30f, 1.18f, 1.08f};
        int fIdx = Math.abs(stepIndex) % fallbackU.length;
        if (argbPixels == null || width < 8 || height < 8 || argbPixels.length < width * height) {
            return new CuriositySpot(fallbackU[fIdx], fallbackV[fIdx], dists[fIdx], 0f);
        }

        final int cols = 4;
        final int rows = 3;
        float bestU = fallbackU[fIdx];
        float bestV = fallbackV[fIdx];
        float bestScore = -Float.MAX_VALUE;
        float maxRaw = 0f;

        for (int r = 0; r < rows; r++) {
            float cellV0 = 0.20f + (r * 0.50f / rows);
            float cellV1 = 0.20f + ((r + 1) * 0.50f / rows);
            float centerV = 0.5f * (cellV0 + cellV1);
            int y0 = Math.max(1, (int) (cellV0 * height));
            int y1 = Math.min(height - 2, (int) (cellV1 * height));

            for (int c = 0; c < cols; c++) {
                float cellU0 = 0.16f + (c * 0.68f / cols);
                float cellU1 = 0.16f + ((c + 1) * 0.68f / cols);
                float centerU = 0.5f * (cellU0 + cellU1);
                int x0 = Math.max(1, (int) (cellU0 * width));
                int x1 = Math.min(width - 2, (int) (cellU1 * width));

                double edgeSum = 0.0;
                double chromaSum = 0.0;
                int count = 0;
                int stepY = Math.max(1, (y1 - y0) / 8);
                int stepX = Math.max(1, (x1 - x0) / 8);

                for (int y = y0; y <= y1; y += stepY) {
                    int rowOff = y * width;
                    for (int x = x0; x <= x1; x += stepX) {
                        int p = argbPixels[rowOff + x];
                        int pr = argbPixels[rowOff + x + 1];
                        int pd = argbPixels[rowOff + width + x];

                        int r0 = (p >> 16) & 0xFF;
                        int g0 = (p >> 8) & 0xFF;
                        int b0 = p & 0xFF;
                        int lum0 = (r0 * 77 + g0 * 150 + b0 * 29) >> 8;

                        int lumR = (((pr >> 16) & 0xFF) * 77 + ((pr >> 8) & 0xFF) * 150 + (pr & 0xFF) * 29) >> 8;
                        int lumD = (((pd >> 16) & 0xFF) * 77 + ((pd >> 8) & 0xFF) * 150 + (pd & 0xFF) * 29) >> 8;
                        edgeSum += Math.abs(lum0 - lumR) + Math.abs(lum0 - lumD);

                        int maxC = Math.max(r0, Math.max(g0, b0));
                        int minC = Math.min(r0, Math.min(g0, b0));
                        chromaSum += (maxC - minC);
                        count++;
                    }
                }
                if (count == 0) {
                    continue;
                }
                float raw = (float) ((edgeSum / count) * 1.15 + (chromaSum / count) * 0.45);
                if (raw > maxRaw) {
                    maxRaw = raw;
                }
                float distFromLast = (float) Math.hypot(centerU - lastU, centerV - lastV);
                float noveltyPenalty = distFromLast < 0.24f ? (28f * (1f - distFromLast / 0.24f)) : 0f;
                float centerBonus = 4f * (1f - (float) Math.hypot(centerU - 0.5f, centerV - 0.46f));
                float score = raw + centerBonus - noveltyPenalty;
                if (score > bestScore) {
                    bestScore = score;
                    bestU = centerU;
                    bestV = centerV;
                }
            }
        }
        if (maxRaw < 6.0f) {
            return new CuriositySpot(fallbackU[fIdx], fallbackV[fIdx], dists[fIdx], maxRaw);
        }
        return new CuriositySpot(bestU, bestV, dists[fIdx], maxRaw);
    }

    /**
     * Builds a short, natural, genuinely curious question where Zoe leads the exploration
     * and asks YOU about what she floated over to ("Ooh, what's this?").
     */
    static String buildNaturalCuriousQuestion(
            String offlineReport, String learnedName, float distanceMeters, int stepIndex, boolean kidFriendly) {
        String cleanLearned = learnedName == null ? "" : learnedName.trim();
        if (!cleanLearned.isEmpty()) {
            String[] knownPrompts = {
                    "Hey, is that your " + cleanLearned + " right there?",
                    "Ooh, I spotted what looks like your " + cleanLearned + ". What are we doing with it?",
                    "That looks like your " + cleanLearned + "! Did I recognize it right?"
            };
            return knownPrompts[Math.abs(stepIndex) % knownPrompts.length];
        }

        String label = extractPrimaryLabel(offlineReport);
        String ocr = extractOcrSnippet(offlineReport);
        if (!ocr.isEmpty()) {
            return kidFriendly
                    ? "Ooh, what's this? I see the words \"" + ocr + "\". What is it?"
                    : "What's this? I spotted the text \"" + ocr + "\" right here. What is it?";
        }
        if (!label.isEmpty()) {
            String low = label.toLowerCase(Locale.US);
            // Skip overly vague scene labels and ask a playful direct "What's this?" instead
            boolean generic = low.equals("room") || low.equals("indoor") || low.equals("wall")
                    || low.equals("floor") || low.equals("ceiling") || low.equals("shadow")
                    || low.equals("light") || low.equals("pattern") || low.equals("material")
                    || low.equals("wood") || low.equals("plastic") || low.equals("metal")
                    || low.equals("rectangle") || low.equals("space") || low.equals("sky")
                    || low.equals("night") || low.equals("darkness") || low.equals("black")
                    || low.equals("grey") || low.equals("gray") || low.equals("monochrome")
                    || low.equals("blur") || low.equals("snapshot");
            if (!generic) {
                if (low.contains("guitar") || low.contains("piano") || low.contains("instrument")) {
                    return "Ooh, is that a " + low + "? Do you play it?";
                }
                if (low.contains("mug") || low.contains("cup") || low.contains("coffee") || low.contains("bottle")) {
                    return "Hey, what's in your " + low + " over here?";
                }
                if (low.contains("book") || low.contains("notebook")) {
                    return "Ooh, what's this " + low + " about?";
                }
                if (low.contains("plant") || low.contains("flower")) {
                    return "What kind of " + low + " is this right here?";
                }
                if (low.contains("dog") || low.contains("cat") || low.contains("pet")) {
                    return "Aww, who is this little " + low + "? What's their name?";
                }
                String[] labelPrompts = {
                        "What's this? Looks like a " + low + ". Tell me about it?",
                        "Ooh, what's this " + low + " over here?",
                        "Hey, is this a " + low + ", or something else?"
                };
                return labelPrompts[Math.abs(stepIndex) % labelPrompts.length];
            }
        }

        String[] openPrompts = kidFriendly
                ? new String[]{
                        "Ooh, what's this right here?",
                        "Hey, what's this cool thing over here?",
                        "What's this? Tell me what it's called!",
                        "Ooh, I'm curious. What is this?"
                }
                : new String[]{
                        "Ooh, what's this right here?",
                        "Hey, what's this over here?",
                        "What's this? I haven't learned this one yet.",
                        "Ooh, what is this thing I floated over to?"
                };
        return openPrompts[Math.abs(stepIndex) % openPrompts.length];
    }

    /**
     * Extracts a clean object name when the user answers Zoe's "What's this?" question
     * (e.g. "that's my red mug", "it's a raspberry pi", "my keyboard"), or returns ""
     * if the reply is a general conversational comment rather than an object name.
     */
    static String extractUserAnswerObjectName(String spoken) {
        if (spoken == null) {
            return "";
        }
        String raw = spoken.trim();
        if (raw.isEmpty() || raw.contains("?")) {
            return "";
        }
        String clean = raw.replaceAll("[.!]+$", "").trim();
        String low = clean.toLowerCase(Locale.US);
        if (low.startsWith("yes") || low.startsWith("yeah") || low.startsWith("yep")
                || low.startsWith("no") || low.startsWith("nope") || low.startsWith("nothing")
                || low.startsWith("i don't know") || low.startsWith("not sure")
                || low.startsWith("never mind") || low.startsWith("stop")
                || low.startsWith("what ") || low.startsWith("where ") || low.startsWith("how ")
                || low.startsWith("who ") || low.startsWith("why ") || low.startsWith("can you")) {
            return "";
        }

        String[] prefixes = {
                "that is my ", "that's my ", "thats my ",
                "that is a ", "that's a ", "thats a ",
                "that is an ", "that's an ", "thats an ",
                "that is the ", "that's the ", "thats the ",
                "that is ", "that's ", "thats ",
                "it is my ", "it's my ", "its my ",
                "it is a ", "it's a ", "its a ",
                "it is an ", "it's an ", "its an ",
                "it is the ", "it's the ", "its the ",
                "it is ", "it's ", "its ",
                "this is my ", "this is a ", "this is an ", "this is the ", "this is ",
                "those are my ", "those are ", "they are my ", "they're my ", "they are ",
                "it's called a ", "it's called ", "that's called a ", "that's called ",
                "called a ", "called ",
                "my ", "a ", "an ", "the "
        };
        boolean matchedPrefix = false;
        String candidate = clean;
        for (String p : prefixes) {
            if (low.startsWith(p)) {
                candidate = clean.substring(p.length()).trim();
                matchedPrefix = true;
                break;
            }
        }
        // Strip leading articles if stacked ("that's a red mug" -> already stripped, "that's my old ...")
        String cLow = candidate.toLowerCase(Locale.US);
        for (String art : new String[]{"a ", "an ", "the ", "my "}) {
            if (cLow.startsWith(art)) {
                candidate = candidate.substring(art.length()).trim();
                cLow = candidate.toLowerCase(Locale.US);
            }
        }
        if (candidate.length() < 2 || candidate.length() > 36) {
            return "";
        }
        String[] words = candidate.split("\\s+");
        if (!matchedPrefix && words.length > 3) {
            return "";
        }
        if (words.length > 5) {
            return "";
        }
        // Reject conversational filler phrases
        if (cLow.equals("ok") || cLow.equals("okay") || cLow.equals("cool")
                || cLow.equals("nice") || cLow.equals("good") || cLow.equals("thanks")
                || cLow.equals("thank you") || cLow.equals("hello") || cLow.equals("hi")
                || cLow.equals("hi zoe") || cLow.equals("hey zoe")) {
            return "";
        }
        return candidate;
    }

    /**
     * True when the user answers Zoe's "what's this?" with uncertainty ("i don't know", "not sure", "no idea"),
     * inviting Zoe to say "let's figure it out together" and investigate clues inside the selection box.
     */
    static boolean isDontKnowReply(String spoken) {
        if (spoken == null || spoken.trim().isEmpty()) {
            return false;
        }
        String low = spoken.toLowerCase(Locale.US)
                .replaceAll("[^a-z0-9\\s']", " ")
                .replaceAll("\\s+", " ")
                .trim();
        return low.contains("i don't know")
                || low.contains("i dont know")
                || low.equals("idk")
                || low.contains("not sure")
                || low.contains("no idea")
                || low.contains("dunno")
                || low.contains("beats me")
                || low.contains("you tell me")
                || low.contains("figure it out")
                || low.contains("not certain")
                || low.contains("no clue");
    }

    /**
     * Lightweight broad-phase / narrow-phase local AR feature geometry computed strictly
     * inside Zoe's Temporary Bounding Box (inspired by axis-oriented bounding volumes:
     * all AR inspection stays isolated inside the framed box instead of the whole room).
     */
    static final class BoxArAnalysis {
        final float focusU;
        final float focusV;
        final float zoePerchU;
        final float zoePerchV;
        final float subLeftU;
        final float subTopV;
        final float subRightU;
        final float subBottomV;
        final float detailScore;
        final float[] anchorUs;
        final float[] anchorVs;

        BoxArAnalysis(float focusU, float focusV, float zoePerchU, float zoePerchV,
                      float subLeftU, float subTopV, float subRightU, float subBottomV,
                      float detailScore, float[] anchorUs, float[] anchorVs) {
            this.focusU = focusU;
            this.focusV = focusV;
            this.zoePerchU = zoePerchU;
            this.zoePerchV = zoePerchV;
            this.subLeftU = subLeftU;
            this.subTopV = subTopV;
            this.subRightU = subRightU;
            this.subBottomV = subBottomV;
            this.detailScore = detailScore;
            this.anchorUs = anchorUs;
            this.anchorVs = anchorVs;
        }
    }

    /**
     * Inspects a small RGB crop strictly from inside the user's Temporary Bounding Box:
     * locates the tight inner subject cluster, top salient local AR anchor points,
     * and the calmest open interior corner where Zoe can hover inside the box without
     * covering the text or object.
     */
    static BoxArAnalysis analyzeBoundingBoxPixels(int[] pixels, int width, int height) {
        if (pixels == null || width < 8 || height < 8 || pixels.length < width * height) {
            return new BoxArAnalysis(
                    0.50f, 0.52f, 0.74f, 0.28f,
                    0.22f, 0.24f, 0.78f, 0.78f,
                    0f, new float[0], new float[0]);
        }
        final int grid = 6;
        float[][] cellEnergy = new float[grid][grid];
        float maxEnergy = 0f;
        float totalEnergy = 0f;
        int bestGx = grid / 2;
        int bestGy = grid / 2;

        for (int gy = 0; gy < grid; gy++) {
            int y0 = (gy * height) / grid;
            int y1 = Math.max(y0 + 1, ((gy + 1) * height) / grid);
            for (int gx = 0; gx < grid; gx++) {
                int x0 = (gx * width) / grid;
                int x1 = Math.max(x0 + 1, ((gx + 1) * width) / grid);
                float edgeSum = 0f;
                int count = 0;
                for (int y = Math.max(1, y0); y < Math.min(height - 1, y1); y++) {
                    int row = y * width;
                    for (int x = Math.max(1, x0); x < Math.min(width - 1, x1); x++) {
                        int c = pixels[row + x];
                        int r = (c >> 16) & 0xFF;
                        int g = (c >> 8) & 0xFF;
                        int b = c & 0xFF;
                        int luma = (r * 3 + g * 6 + b) / 10;

                        int cr = pixels[row + x + 1];
                        int lumaR = (((cr >> 16) & 0xFF) * 3 + ((cr >> 8) & 0xFF) * 6 + (cr & 0xFF)) / 10;
                        int cb = pixels[(y + 1) * width + x];
                        int lumaB = (((cb >> 16) & 0xFF) * 3 + ((cb >> 8) & 0xFF) * 6 + (cb & 0xFF)) / 10;

                        int grad = Math.abs(luma - lumaR) + Math.abs(luma - lumaB);
                        int sat = Math.max(r, Math.max(g, b)) - Math.min(r, Math.min(g, b));
                        edgeSum += grad * 1.45f + sat * 0.25f;
                        count++;
                    }
                }
                float meanE = count > 0 ? (edgeSum / count) : 0f;
                cellEnergy[gy][gx] = meanE;
                totalEnergy += meanE;
                if (meanE > maxEnergy) {
                    maxEnergy = meanE;
                    bestGx = gx;
                    bestGy = gy;
                }
            }
        }

        float meanGridEnergy = totalEnergy / (grid * grid);
        float detailScore = Math.max(0f, Math.min(1f, (maxEnergy - 6f) / 48f));
        float focusU = (bestGx + 0.5f) / grid;
        float focusV = (bestGy + 0.5f) / grid;

        // Narrow-phase tight inner bounding box hugging salient cells (> 52% of peak energy)
        float thresh = Math.max(meanGridEnergy * 1.15f, maxEnergy * 0.52f);
        float minU = 1f;
        float minV = 1f;
        float maxU = 0f;
        float maxV = 0f;
        boolean foundSalient = false;

        // Pick top 3 salient micro-anchor centers inside the bounding box
        int[] topGx = {-1, -1, -1};
        int[] topGy = {-1, -1, -1};
        float[] topVal = {0f, 0f, 0f};

        for (int gy = 0; gy < grid; gy++) {
            for (int gx = 0; gx < grid; gx++) {
                float e = cellEnergy[gy][gx];
                if (e >= thresh && e > 8f) {
                    foundSalient = true;
                    minU = Math.min(minU, (float) gx / grid);
                    minV = Math.min(minV, (float) gy / grid);
                    maxU = Math.max(maxU, (float) (gx + 1) / grid);
                    maxV = Math.max(maxV, (float) (gy + 1) / grid);
                }
                if (e > 10f) {
                    for (int k = 0; k < 3; k++) {
                        if (e > topVal[k]) {
                            for (int s = 2; s > k; s--) {
                                topVal[s] = topVal[s - 1];
                                topGx[s] = topGx[s - 1];
                                topGy[s] = topGy[s - 1];
                            }
                            topVal[k] = e;
                            topGx[k] = gx;
                            topGy[k] = gy;
                            break;
                        }
                    }
                }
            }
        }

        int anchorCount = 0;
        for (int k = 0; k < 3; k++) {
            if (topGx[k] >= 0) anchorCount++;
        }
        float[] anchorUs = new float[anchorCount];
        float[] anchorVs = new float[anchorCount];
        int ai = 0;
        for (int k = 0; k < 3; k++) {
            if (topGx[k] >= 0) {
                anchorUs[ai] = (topGx[k] + 0.5f) / grid;
                anchorVs[ai] = (topGy[k] + 0.5f) / grid;
                ai++;
            }
        }

        if (!foundSalient) {
            minU = 0.22f;
            minV = 0.24f;
            maxU = 0.78f;
            maxV = 0.78f;
        } else {
            minU = Math.max(0.08f, Math.min(0.70f, minU));
            minV = Math.max(0.08f, Math.min(0.70f, minV));
            maxU = Math.max(minU + 0.20f, Math.min(0.92f, maxU));
            maxV = Math.max(minV + 0.20f, Math.min(0.92f, maxV));
        }

        // Choose the calmest open interior perch corner inside the box so Zoe hovers beside
        // the framed object/text without blocking it (strictly inside [0.22, 0.78]).
        float[][] corners = {
                {0.76f, 0.24f}, // upper-right (natural friendly companion perch)
                {0.24f, 0.24f}, // upper-left
                {0.76f, 0.74f}, // lower-right
                {0.24f, 0.74f}  // lower-left
        };
        float bestPerchU = 0.76f;
        float bestPerchV = 0.24f;
        float bestPerchScore = -Float.MAX_VALUE;
        for (int i = 0; i < corners.length; i++) {
            float cu = corners[i][0];
            float cv = corners[i][1];
            int cgx = Math.max(0, Math.min(grid - 1, (int) (cu * grid)));
            int cgy = Math.max(0, Math.min(grid - 1, (int) (cv * grid)));
            float localBusy = cellEnergy[cgy][cgx];
            float distToFocus = (float) Math.hypot(cu - focusU, cv - focusV);
            // Prefer open (low-energy) corners clearly separated from the focal detail; mild top bias
            float score = distToFocus * 32f - localBusy * 0.85f + (i < 2 ? 4f : 0f);
            if (score > bestPerchScore) {
                bestPerchScore = score;
                bestPerchU = cu;
                bestPerchV = cv;
            }
        }

        return new BoxArAnalysis(
                focusU, focusV, bestPerchU, bestPerchV,
                minU, minV, maxU, maxV,
                detailScore, anchorUs, anchorVs);
    }

    /**
     * Builds a warm, collaborative "let's figure it out together" response using only real clues
     * measured inside the user's Temporary Bounding Box (zero hallucination, zero em dashes).
     */
    static String buildLetsFigureItOutReply(
            String offlineReport, String shapeSummary, String colorSummary, boolean kidFriendly) {
        String label = extractPrimaryLabel(offlineReport);
        String ocr = extractOcrSnippet(offlineReport);
        StringBuilder sb = new StringBuilder("let's figure it out together! ");
        boolean addedClue = false;
        if (!ocr.isEmpty()) {
            sb.append("inside the box i can read \"").append(ocr.toLowerCase(Locale.US)).append("\". ");
            addedClue = true;
        }
        if (!label.isEmpty()) {
            String lowLbl = label.toLowerCase(Locale.US);
            boolean generic = lowLbl.equals("room") || lowLbl.equals("indoor")
                    || lowLbl.equals("wall") || lowLbl.equals("floor") || lowLbl.equals("space")
                    || lowLbl.equals("sky") || lowLbl.equals("darkness") || lowLbl.equals("shadow");
            if (!generic) {
                sb.append("it looks a bit like a ").append(lowLbl).append(". ");
                addedClue = true;
            }
        }
        if (colorSummary != null && !colorSummary.trim().isEmpty()) {
            sb.append("i see ").append(colorSummary.trim().toLowerCase(Locale.US));
            if (shapeSummary != null && !shapeSummary.trim().isEmpty()) {
                sb.append(" with ").append(shapeSummary.trim().toLowerCase(Locale.US));
            }
            sb.append(". ");
            addedClue = true;
        } else if (shapeSummary != null && !shapeSummary.trim().isEmpty()) {
            sb.append("the shape looks like ").append(shapeSummary.trim().toLowerCase(Locale.US)).append(". ");
            addedClue = true;
        }
        if (kidFriendly) {
            sb.append(addedClue
                    ? "try sliding or tightening the box over any words or cool details on this still frame!"
                    : "try sliding the box over another spot on this still frame so we can spot a clue together!");
        } else {
            sb.append(addedClue
                    ? "you can resize or slide the box over any word or detail on this still frame to narrow it down."
                    : "you can slide the box over a clearer part of this still frame, or tap the refresh arrow for a new shot.");
        }
        return sb.toString().trim();
    }
}
