package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;

public class ArExploreBrainTest {
    @Test
    public void springGlideMovesSmoothlyTowardTargetWithoutOvershoot() {
        ArExploreBrain.Vec3 cur = new ArExploreBrain.Vec3(0f, 0f, -1f);
        ArExploreBrain.Vec3 tgt = new ArExploreBrain.Vec3(1f, 0.5f, -2f);
        ArExploreBrain.Vec3 next = ArExploreBrain.stepGlide(cur, tgt, 0.05f, 3.0f);
        assertTrue(next.x > 0f && next.x < 1f);
        assertTrue(next.y > 0f && next.y < 0.5f);
        assertTrue(next.z < -1f && next.z > -2f);
        assertTrue(next.distanceTo(tgt) < cur.distanceTo(tgt));
    }

    @Test
    public void autonomousPlannerCyclesUnvisitedPlanesWithinComfortableRange() {
        ArExploreBrain brain = new ArExploreBrain();
        ArExploreBrain.Vec3 cam = new ArExploreBrain.Vec3(0f, 0f, 0f);
        List<ArExploreBrain.PlaneTarget> planes = Arrays.asList(
                new ArExploreBrain.PlaneTarget("too-close", new ArExploreBrain.Vec3(0f, 0f, -0.15f), 1f, 1f, false),
                new ArExploreBrain.PlaneTarget("desk", new ArExploreBrain.Vec3(0.2f, -0.3f, -1.3f), 1.5f, 1.0f, false),
                new ArExploreBrain.PlaneTarget("wall", new ArExploreBrain.Vec3(-0.8f, 0.1f, -1.8f), 0.9f, 0.7f, true),
                new ArExploreBrain.PlaneTarget("too-far", new ArExploreBrain.Vec3(0f, 0f, -6.0f), 2f, 2f, false)
        );
        ArExploreBrain.PlaneTarget first = brain.chooseNextExploreTarget(cam, planes);
        assertNotNull(first);
        assertEquals("desk", first.id);

        ArExploreBrain.PlaneTarget second = brain.chooseNextExploreTarget(cam, planes);
        assertNotNull(second);
        assertEquals("wall", second.id);
    }

    @Test
    public void discoveryJournalExtractsLabelsDeduplicatesNearbyAndAsksCuriousQuestions() {
        ArExploreBrain brain = new ArExploreBrain();
        String rep = "Labels: Guitar (91%), Musical instrument (84%). Visible text: \"FENDER\".";
        assertEquals("Guitar", ArExploreBrain.extractPrimaryLabel(rep));
        assertEquals("FENDER", ArExploreBrain.extractOcrSnippet(rep));

        ArExploreBrain.Vec3 pos = new ArExploreBrain.Vec3(0.4f, -0.1f, -1.4f);
        ArExploreBrain.SpatialDiscovery d1 = brain.recordDiscoveryIfNew(rep, pos, 1.45f, 1000L);
        assertNotNull(d1);

        // Same object nearby should NOT repeat!
        ArExploreBrain.SpatialDiscovery dup = brain.recordDiscoveryIfNew(
                rep, new ArExploreBrain.Vec3(0.45f, -0.1f, -1.38f), 1.44f, 5000L);
        assertNull(dup);

        // New object across the room records cleanly
        ArExploreBrain.SpatialDiscovery d2 = brain.recordDiscoveryIfNew(
                "Labels: Mug (88%).", new ArExploreBrain.Vec3(-0.9f, -0.2f, -1.1f), 1.42f, 9000L);
        assertNotNull(d2);
        assertEquals(2, brain.getDiscoveries().size());

        String question = ArExploreBrain.buildOfflineCuriousQuestion(d1);
        assertTrue(question.contains("guitar"));
        assertTrue(question.contains("FENDER"));
        assertTrue(question.endsWith("?"));

        String prompt = ArExploreBrain.buildCuriosityQuestionPrompt(d2, brain.summarizeRoomMemory());
        assertTrue(prompt.contains("Guitar"));
        assertTrue(prompt.contains("Mug"));
        assertFalse(prompt.toLowerCase().contains("alibaba"));
    }

    @Test
    public void spatialProjectionUnprojectionRoundTripsCleanlyForSixtyFpsAr() {
        float[] identity = {
                1f, 0f, 0f,
                0f, 1f, 0f,
                0f, 0f, 1f
        };
        float w = 1080f;
        float h = 2400f;
        float fov = ArExploreBrain.DEFAULT_SPATIAL_FOV_RAD;

        ArExploreBrain.Vec3 world = ArExploreBrain.unprojectTapToWorld(740f, 920f, w, h, fov, identity, 1.35f);
        assertEquals(1.35f, world.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f)), 0.02f);

        ArExploreBrain.ScreenProjection proj = ArExploreBrain.projectWorldToScreen(world, identity, w, h, fov);
        assertTrue(proj.inFront);
        assertTrue(proj.onScreen);
        assertEquals(740f, proj.screenX, 2.5f);
        assertEquals(920f, proj.screenY, 2.5f);

        // Point behind camera should report inFront = false, onScreen = false
        ArExploreBrain.ScreenProjection behind = ArExploreBrain.projectWorldToScreen(
                new ArExploreBrain.Vec3(0f, 0f, 1.5f), identity, w, h, fov);
        assertFalse(behind.inFront);
        assertFalse(behind.onScreen);

        // Spatial roam waypoint stays in front of camera at comfortable 1.0..1.6m range
        ArExploreBrain.Vec3 roam = ArExploreBrain.chooseSpatialRoamWaypoint(identity, 2);
        float d = roam.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f));
        assertTrue(d >= 0.9f && d <= 1.8f);
        assertTrue(roam.z < 0f);
    }
}
