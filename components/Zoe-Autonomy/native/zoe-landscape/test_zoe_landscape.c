#include "zoe_landscape.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void make_provenance(zoe_provenance_t *provenance) {
    provenance->source_flags = 7u;
    provenance->evidence_id = 42u;
    provenance->update_step = 3u;
    provenance->weight_user = 0.2f;
    provenance->weight_policy = 0.1f;
    provenance->weight_zoe = 0.7f;
}

static zoe_probability_landscape_t *landscape(uint64_t t, const float *probabilities, size_t count) {
    zoe_probability_landscape_t *landscape = zoe_landscape_create(ZOE_DOMAIN_ACTION, t, 0.05f, t > 10u, "synthetic", count);
    zoe_provenance_t provenance;
    size_t index;
    assert(landscape != NULL);
    make_provenance(&provenance);
    for (index = 0u; index < count; index += 1u) {
        assert(zoe_landscape_set_point(
            landscape, index, 100u + index, (float)index, (float)(count - index),
            probabilities[index], &provenance) == ZOE_LANDSCAPE_OK);
    }
    return landscape;
}

static int visited;
static void visit(const zoe_probability_landscape_t *item, void *data) {
    (void)data;
    assert(item != NULL);
    visited += 1;
}

int main(void) {
    const float first_probs[] = {0.50f, 0.30f, 0.15f, 0.05f};
    const float second_probs[] = {0.90f, 0.10f};
    zoe_probability_landscape_t *first = landscape(1u, first_probs, 4u);
    zoe_probability_landscape_t *second = landscape(2u, second_probs, 2u);
    zoe_landscape_series_t *series = zoe_landscape_series_create(4u);
    size_t indices[4];
    size_t count = 0u;
    long deltas[2];
    zoe_landscape_status_t status;
    zoe_probability_landscape_t *restored;

    assert(zoe_landscape_abi_version() == 1u);
    assert(first != NULL && second != NULL && series != NULL);
    assert(zoe_landscape_compute_A_tau(first, 0.05f) == 3u);
    assert(zoe_landscape_points_above_tau(first, 0.05f, indices, 4u, &count) == ZOE_LANDSCAPE_OK);
    assert(count == 3u && indices[2] == 2u);
    assert(zoe_landscape_series_add(series, first) == ZOE_LANDSCAPE_OK);
    assert(zoe_landscape_series_add(series, second) == ZOE_LANDSCAPE_OK);
    assert(zoe_landscape_delta_A_tau_series(series, 0.05f, deltas, 2u, &count) == ZOE_LANDSCAPE_OK);
    assert(count == 2u && deltas[0] == 0L && deltas[1] == -1L);
    assert(zoe_landscape_find_neighbors(first, 1.0f, 3.0f, 1.1f, indices, 4u, &count) == ZOE_LANDSCAPE_OK);
    assert(count >= 1u);
    assert(zoe_landscape_get_at_time(series, 2u) == second);
    assert(zoe_landscape_get_at_or_before(series, 3u) == second);
    assert(zoe_landscape_visit_range(series, 1u, 2u, visit, NULL) == ZOE_LANDSCAPE_OK);
    assert(visited == 2);
    assert(zoe_landscape_write_file(first, "build/landscape.bin") == ZOE_LANDSCAPE_OK);
    assert(zoe_landscape_write_file(first, "build/landscape.bin") == ZOE_LANDSCAPE_ERROR_IO);
    restored = zoe_landscape_read_file("build/landscape.bin", &status);
    assert(status == ZOE_LANDSCAPE_OK && restored != NULL);
    assert(restored->num_points == first->num_points);
    assert(restored->t_index == first->t_index);
    assert(restored->points[2].probability == first->points[2].probability);
    zoe_landscape_destroy(restored);
    {
        const uint64_t ids[] = {10u, 11u};
        const float xs[] = {0.2f, 0.8f};
        const float ys[] = {0.3f, 0.7f};
        zoe_provenance_t sources[2];
        zoe_probability_landscape_t *built;
        make_provenance(&sources[0]);
        make_provenance(&sources[1]);
        built = zoe_landscape_from_arrays(
            ZOE_DOMAIN_ACTION, 9u, 0.05f, 0u, "array-test",
            ids, xs, ys, second_probs, sources, 2u);
        assert(built != NULL && built->num_points == 2u);
        zoe_landscape_destroy(built);
    }
    assert(zoe_landscape_write_svg(first, "build/landscape.svg", 960u, 540u) == ZOE_LANDSCAPE_OK);
    assert(zoe_landscape_write_svg(first, "build/landscape.svg", 960u, 540u) == ZOE_LANDSCAPE_ERROR_IO);
    {
        FILE *svg = fopen("build/landscape.svg", "rb");
        char text[256];
        size_t size;
        assert(svg != NULL);
        size = fread(text, 1u, sizeof(text) - 1u, svg);
        text[size] = '\0';
        assert(strstr(text, "<svg") != NULL);
        fclose(svg);
    }
    zoe_landscape_series_destroy(series);
    remove("build/landscape.bin");
    remove("build/landscape.svg");
    puts("zoe_landscape: all checks passed");
    return 0;
}
