#include "zoe_landscape.h"

#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    const uint64_t ids[] = {1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u};
    const float xs[] = {0.12f, 0.24f, 0.34f, 0.44f, 0.52f, 0.64f, 0.74f, 0.84f, 0.94f};
    const float ys[] = {0.18f, 0.26f, 0.40f, 0.55f, 0.72f, 0.80f, 0.66f, 0.52f, 0.44f};
    const float probabilities[] = {0.04f, 0.09f, 0.16f, 0.22f, 0.17f, 0.20f, 0.07f, 0.03f, 0.02f};
    zoe_provenance_t provenance[9];
    zoe_probability_landscape_t *landscape;
    size_t index;
    for (index = 0u; index < 9u; index += 1u) {
        zoe_provenance_t source = {7u, 42u, 0u, 0.2f, 0.1f, 0.7f};
        provenance[index] = source;
    }
    zoe_landscape_status_t status;
    if (argc != 2) {
        fprintf(stderr, "usage: zoe_landscape_demo NEW.svg\n");
        return 2;
    }
    landscape = zoe_landscape_from_arrays(
        ZOE_DOMAIN_INTENT, 0u, 0.05f, 1u, "synthetic-demo",
        ids, xs, ys, probabilities, provenance, 9u);
    if (landscape == NULL) {
        fprintf(stderr, "could not construct landscape\n");
        return 1;
    }
    status = zoe_landscape_write_svg(landscape, argv[1], 1600u, 900u);
    if (status != ZOE_LANDSCAPE_OK) {
        fprintf(stderr, "could not write SVG: %s\n", zoe_landscape_status_text(status));
        zoe_landscape_destroy(landscape);
        return 1;
    }
    printf("A_tau=%zu tau=0.050 simulation=true output=%s\n",
           zoe_landscape_compute_A_tau(landscape, 0.05f), argv[1]);
    zoe_landscape_destroy(landscape);
    return 0;
}
