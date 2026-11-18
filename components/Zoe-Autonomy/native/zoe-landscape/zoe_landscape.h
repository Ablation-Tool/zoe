#ifndef ZOE_LANDSCAPE_H
#define ZOE_LANDSCAPE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ZOE_LANDSCAPE_ABI_VERSION 1u
#define ZOE_LANDSCAPE_MAX_RUN_ID 64u
#define ZOE_LANDSCAPE_MAX_POINTS 4096u
#define ZOE_LANDSCAPE_MAX_SERIES 4096u

typedef enum {
    ZOE_DOMAIN_INTENT = 0,
    ZOE_DOMAIN_ACTION = 1,
    ZOE_DOMAIN_SELF = 2,
    ZOE_DOMAIN_ENVIRONMENT = 3,
    ZOE_DOMAIN_PLAY = 4,
    ZOE_DOMAIN_OTHER = 5
} zoe_domain_t;

typedef enum {
    ZOE_LANDSCAPE_OK = 0,
    ZOE_LANDSCAPE_ERROR_INVALID = 1,
    ZOE_LANDSCAPE_ERROR_ALLOCATION = 2,
    ZOE_LANDSCAPE_ERROR_CAPACITY = 3,
    ZOE_LANDSCAPE_ERROR_IO = 4,
    ZOE_LANDSCAPE_ERROR_FORMAT = 5,
    ZOE_LANDSCAPE_ERROR_NOT_FOUND = 6
} zoe_landscape_status_t;

typedef struct {
    uint32_t source_flags;
    uint64_t evidence_id;
    uint64_t update_step;
    float weight_user;
    float weight_policy;
    float weight_zoe;
} zoe_provenance_t;

typedef struct {
    uint64_t option_id;
    zoe_domain_t domain;
    float x;
    float y;
    float probability;
    zoe_provenance_t provenance;
} zoe_landscape_point_t;

typedef struct {
    zoe_domain_t domain;
    uint64_t t_index;
    float tau;
    uint32_t is_simulation;
    char run_id[ZOE_LANDSCAPE_MAX_RUN_ID];
    zoe_landscape_point_t *points;
    size_t num_points;
    size_t capacity;
} zoe_probability_landscape_t;

typedef struct {
    zoe_probability_landscape_t **landscapes;
    size_t num_landscapes;
    size_t capacity;
} zoe_landscape_series_t;

typedef void (*zoe_landscape_visitor_t)(const zoe_probability_landscape_t *landscape, void *user_data);

uint32_t zoe_landscape_abi_version(void);
const char *zoe_landscape_status_text(zoe_landscape_status_t status);

zoe_probability_landscape_t *zoe_landscape_create(
    zoe_domain_t domain,
    uint64_t t_index,
    float tau,
    uint32_t is_simulation,
    const char *run_id,
    size_t capacity);
void zoe_landscape_destroy(zoe_probability_landscape_t *landscape);

zoe_landscape_status_t zoe_landscape_set_point(
    zoe_probability_landscape_t *landscape,
    size_t index,
    uint64_t option_id,
    float x,
    float y,
    float probability,
    const zoe_provenance_t *provenance);

zoe_probability_landscape_t *zoe_landscape_from_arrays(
    zoe_domain_t domain,
    uint64_t t_index,
    float tau,
    uint32_t is_simulation,
    const char *run_id,
    const uint64_t *option_ids,
    const float *xs,
    const float *ys,
    const float *probabilities,
    const zoe_provenance_t *provenance,
    size_t count);

zoe_landscape_series_t *zoe_landscape_series_create(size_t capacity);
void zoe_landscape_series_destroy(zoe_landscape_series_t *series);
zoe_landscape_status_t zoe_landscape_series_add(
    zoe_landscape_series_t *series,
    zoe_probability_landscape_t *landscape);

size_t zoe_landscape_compute_A_tau(const zoe_probability_landscape_t *landscape, float tau);
zoe_landscape_status_t zoe_landscape_points_above_tau(
    const zoe_probability_landscape_t *landscape,
    float tau,
    size_t *out_indices,
    size_t max_out,
    size_t *out_count);
zoe_landscape_status_t zoe_landscape_delta_A_tau_series(
    const zoe_landscape_series_t *series,
    float tau,
    long *out_deltas,
    size_t max_deltas,
    size_t *out_count);
zoe_landscape_status_t zoe_landscape_find_neighbors(
    const zoe_probability_landscape_t *landscape,
    float x,
    float y,
    float radius,
    size_t *out_indices,
    size_t max_out,
    size_t *out_count);

const zoe_probability_landscape_t *zoe_landscape_get_at_time(
    const zoe_landscape_series_t *series,
    uint64_t t_index);
const zoe_probability_landscape_t *zoe_landscape_get_at_or_before(
    const zoe_landscape_series_t *series,
    uint64_t t_index);
zoe_landscape_status_t zoe_landscape_visit_range(
    const zoe_landscape_series_t *series,
    uint64_t t_start,
    uint64_t t_end,
    zoe_landscape_visitor_t visitor,
    void *user_data);

zoe_landscape_status_t zoe_landscape_write_svg(
    const zoe_probability_landscape_t *landscape,
    const char *path,
    unsigned int width,
    unsigned int height);
zoe_landscape_status_t zoe_landscape_write_file(
    const zoe_probability_landscape_t *landscape,
    const char *path);
zoe_probability_landscape_t *zoe_landscape_read_file(
    const char *path,
    zoe_landscape_status_t *status);

#ifdef __cplusplus
}
#endif

#endif
