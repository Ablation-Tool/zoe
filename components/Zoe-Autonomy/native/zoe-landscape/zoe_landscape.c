#define _POSIX_C_SOURCE 200809L

#include "zoe_landscape.h"

#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ZOE_FILE_MAGIC "ZOELND1\0"
#define ZOE_FILE_MAGIC_SIZE 8u

static int valid_domain(zoe_domain_t domain) {
    return domain >= ZOE_DOMAIN_INTENT && domain <= ZOE_DOMAIN_OTHER;
}

static int finite_float(float value) {
    return isfinite(value) != 0;
}

static int valid_probability(float probability) {
    return finite_float(probability) && probability >= 0.0f && probability <= 1.0f;
}

static int valid_tau(float tau) {
    return finite_float(tau) && tau > 0.0f && tau < 1.0f;
}

static int valid_provenance(const zoe_provenance_t *provenance) {
    float total;
    if (provenance == NULL) {
        return 0;
    }
    if (!valid_probability(provenance->weight_user) ||
        !valid_probability(provenance->weight_policy) ||
        !valid_probability(provenance->weight_zoe)) {
        return 0;
    }
    total = provenance->weight_user + provenance->weight_policy + provenance->weight_zoe;
    return total <= 1.0f + 1e-6f;
}

uint32_t zoe_landscape_abi_version(void) {
    return ZOE_LANDSCAPE_ABI_VERSION;
}

const char *zoe_landscape_status_text(zoe_landscape_status_t status) {
    switch (status) {
        case ZOE_LANDSCAPE_OK: return "ok";
        case ZOE_LANDSCAPE_ERROR_INVALID: return "invalid input";
        case ZOE_LANDSCAPE_ERROR_ALLOCATION: return "allocation failed";
        case ZOE_LANDSCAPE_ERROR_CAPACITY: return "capacity exceeded";
        case ZOE_LANDSCAPE_ERROR_IO: return "input/output error";
        case ZOE_LANDSCAPE_ERROR_FORMAT: return "invalid landscape format";
        case ZOE_LANDSCAPE_ERROR_NOT_FOUND: return "not found";
        default: return "unknown status";
    }
}

zoe_probability_landscape_t *zoe_landscape_create(
    zoe_domain_t domain,
    uint64_t t_index,
    float tau,
    uint32_t is_simulation,
    const char *run_id,
    size_t capacity) {
    zoe_probability_landscape_t *landscape;
    size_t run_length;

    if (!valid_domain(domain) || !valid_tau(tau) ||
        (is_simulation != 0u && is_simulation != 1u) ||
        capacity == 0u || capacity > ZOE_LANDSCAPE_MAX_POINTS) {
        return NULL;
    }
    landscape = calloc(1u, sizeof(*landscape));
    if (landscape == NULL) {
        return NULL;
    }
    landscape->points = calloc(capacity, sizeof(*landscape->points));
    if (landscape->points == NULL) {
        free(landscape);
        return NULL;
    }
    landscape->domain = domain;
    landscape->t_index = t_index;
    landscape->tau = tau;
    landscape->is_simulation = is_simulation;
    landscape->capacity = capacity;
    landscape->num_points = 0u;
    if (run_id != NULL) {
        run_length = strlen(run_id);
        if (run_length >= ZOE_LANDSCAPE_MAX_RUN_ID) {
            free(landscape->points);
            free(landscape);
            return NULL;
        }
        memcpy(landscape->run_id, run_id, run_length + 1u);
    }
    return landscape;
}

void zoe_landscape_destroy(zoe_probability_landscape_t *landscape) {
    if (landscape != NULL) {
        free(landscape->points);
        free(landscape);
    }
}

zoe_landscape_status_t zoe_landscape_set_point(
    zoe_probability_landscape_t *landscape,
    size_t index,
    uint64_t option_id,
    float x,
    float y,
    float probability,
    const zoe_provenance_t *provenance) {
    zoe_landscape_point_t *point;

    if (landscape == NULL || index >= landscape->capacity ||
        !finite_float(x) || !finite_float(y) ||
        !valid_probability(probability) || !valid_provenance(provenance)) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    point = &landscape->points[index];
    point->option_id = option_id;
    point->domain = landscape->domain;
    point->x = x;
    point->y = y;
    point->probability = probability;
    point->provenance = *provenance;
    if (index >= landscape->num_points) {
        landscape->num_points = index + 1u;
    }
    return ZOE_LANDSCAPE_OK;
}

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
    size_t count) {
    zoe_probability_landscape_t *landscape;
    size_t index;

    if (count == 0u || count > ZOE_LANDSCAPE_MAX_POINTS ||
        option_ids == NULL || xs == NULL || ys == NULL ||
        probabilities == NULL || provenance == NULL) {
        return NULL;
    }
    landscape = zoe_landscape_create(domain, t_index, tau, is_simulation, run_id, count);
    if (landscape == NULL) {
        return NULL;
    }
    for (index = 0u; index < count; index += 1u) {
        if (zoe_landscape_set_point(
                landscape, index, option_ids[index], xs[index], ys[index],
                probabilities[index], &provenance[index]) != ZOE_LANDSCAPE_OK) {
            zoe_landscape_destroy(landscape);
            return NULL;
        }
    }
    return landscape;
}

zoe_landscape_series_t *zoe_landscape_series_create(size_t capacity) {
    zoe_landscape_series_t *series;
    if (capacity == 0u || capacity > ZOE_LANDSCAPE_MAX_SERIES) {
        return NULL;
    }
    series = calloc(1u, sizeof(*series));
    if (series == NULL) {
        return NULL;
    }
    series->landscapes = calloc(capacity, sizeof(*series->landscapes));
    if (series->landscapes == NULL) {
        free(series);
        return NULL;
    }
    series->capacity = capacity;
    return series;
}

void zoe_landscape_series_destroy(zoe_landscape_series_t *series) {
    size_t index;
    if (series == NULL) {
        return;
    }
    for (index = 0u; index < series->num_landscapes; index += 1u) {
        zoe_landscape_destroy(series->landscapes[index]);
    }
    free(series->landscapes);
    free(series);
}

zoe_landscape_status_t zoe_landscape_series_add(
    zoe_landscape_series_t *series,
    zoe_probability_landscape_t *landscape) {
    size_t index;
    if (series == NULL || landscape == NULL) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    for (index = 0u; index < series->num_landscapes; index += 1u) {
        if (series->landscapes[index] == landscape) {
            return ZOE_LANDSCAPE_ERROR_INVALID;
        }
        if (series->landscapes[index]->t_index > landscape->t_index) {
            return ZOE_LANDSCAPE_ERROR_INVALID;
        }
    }
    if (series->num_landscapes >= series->capacity) {
        return ZOE_LANDSCAPE_ERROR_CAPACITY;
    }
    series->landscapes[series->num_landscapes] = landscape;
    series->num_landscapes += 1u;
    return ZOE_LANDSCAPE_OK;
}

size_t zoe_landscape_compute_A_tau(const zoe_probability_landscape_t *landscape, float tau) {
    size_t count = 0u;
    size_t index;
    if (landscape == NULL || !valid_tau(tau)) {
        return 0u;
    }
    for (index = 0u; index < landscape->num_points; index += 1u) {
        if (landscape->points[index].probability > tau) {
            count += 1u;
        }
    }
    return count;
}

zoe_landscape_status_t zoe_landscape_points_above_tau(
    const zoe_probability_landscape_t *landscape,
    float tau,
    size_t *out_indices,
    size_t max_out,
    size_t *out_count) {
    size_t index;
    size_t count = 0u;
    if (landscape == NULL || out_indices == NULL || out_count == NULL || !valid_tau(tau)) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    for (index = 0u; index < landscape->num_points; index += 1u) {
        if (landscape->points[index].probability > tau) {
            if (count < max_out) {
                out_indices[count] = index;
            }
            count += 1u;
        }
    }
    *out_count = count;
    return count <= max_out ? ZOE_LANDSCAPE_OK : ZOE_LANDSCAPE_ERROR_CAPACITY;
}

zoe_landscape_status_t zoe_landscape_delta_A_tau_series(
    const zoe_landscape_series_t *series,
    float tau,
    long *out_deltas,
    size_t max_deltas,
    size_t *out_count) {
    size_t index;
    size_t previous;
    size_t current;
    if (series == NULL || out_deltas == NULL || out_count == NULL || !valid_tau(tau)) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    if (series->num_landscapes > max_deltas) {
        return ZOE_LANDSCAPE_ERROR_CAPACITY;
    }
    if (series->num_landscapes == 0u) {
        *out_count = 0u;
        return ZOE_LANDSCAPE_OK;
    }
    previous = zoe_landscape_compute_A_tau(series->landscapes[0], tau);
    out_deltas[0] = 0L;
    for (index = 1u; index < series->num_landscapes; index += 1u) {
        if (series->landscapes[index - 1u]->t_index > series->landscapes[index]->t_index) {
            return ZOE_LANDSCAPE_ERROR_INVALID;
        }
        current = zoe_landscape_compute_A_tau(series->landscapes[index], tau);
        out_deltas[index] = (long)current - (long)previous;
        previous = current;
    }
    *out_count = series->num_landscapes;
    return ZOE_LANDSCAPE_OK;
}

zoe_landscape_status_t zoe_landscape_find_neighbors(
    const zoe_probability_landscape_t *landscape,
    float x,
    float y,
    float radius,
    size_t *out_indices,
    size_t max_out,
    size_t *out_count) {
    size_t index;
    size_t count = 0u;
    float limit;
    if (landscape == NULL || out_indices == NULL || out_count == NULL ||
        !finite_float(x) || !finite_float(y) || !finite_float(radius) || radius < 0.0f) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    limit = radius * radius;
    for (index = 0u; index < landscape->num_points; index += 1u) {
        float dx = landscape->points[index].x - x;
        float dy = landscape->points[index].y - y;
        if (dx * dx + dy * dy <= limit) {
            if (count < max_out) {
                out_indices[count] = index;
            }
            count += 1u;
        }
    }
    *out_count = count;
    return count <= max_out ? ZOE_LANDSCAPE_OK : ZOE_LANDSCAPE_ERROR_CAPACITY;
}

const zoe_probability_landscape_t *zoe_landscape_get_at_time(
    const zoe_landscape_series_t *series,
    uint64_t t_index) {
    size_t index;
    if (series == NULL) {
        return NULL;
    }
    for (index = 0u; index < series->num_landscapes; index += 1u) {
        if (series->landscapes[index]->t_index == t_index) {
            return series->landscapes[index];
        }
    }
    return NULL;
}

const zoe_probability_landscape_t *zoe_landscape_get_at_or_before(
    const zoe_landscape_series_t *series,
    uint64_t t_index) {
    const zoe_probability_landscape_t *best = NULL;
    size_t index;
    if (series == NULL) {
        return NULL;
    }
    for (index = 0u; index < series->num_landscapes; index += 1u) {
        if (series->landscapes[index]->t_index <= t_index &&
            (best == NULL || series->landscapes[index]->t_index > best->t_index)) {
            best = series->landscapes[index];
        }
    }
    return best;
}

zoe_landscape_status_t zoe_landscape_visit_range(
    const zoe_landscape_series_t *series,
    uint64_t t_start,
    uint64_t t_end,
    zoe_landscape_visitor_t visitor,
    void *user_data) {
    size_t index;
    if (series == NULL || visitor == NULL || t_start > t_end) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    for (index = 0u; index < series->num_landscapes; index += 1u) {
        if (series->landscapes[index]->t_index >= t_start &&
            series->landscapes[index]->t_index <= t_end) {
            visitor(series->landscapes[index], user_data);
        }
    }
    return ZOE_LANDSCAPE_OK;
}

static zoe_landscape_status_t write_exact(FILE *file, const void *data, size_t size) {
    return fwrite(data, 1u, size, file) == size ? ZOE_LANDSCAPE_OK : ZOE_LANDSCAPE_ERROR_IO;
}

static zoe_landscape_status_t read_exact(FILE *file, void *data, size_t size) {
    return fread(data, 1u, size, file) == size ? ZOE_LANDSCAPE_OK : ZOE_LANDSCAPE_ERROR_FORMAT;
}

zoe_landscape_status_t zoe_landscape_write_file(
    const zoe_probability_landscape_t *landscape,
    const char *path) {
    FILE *file;
    int descriptor;
    uint32_t abi = ZOE_LANDSCAPE_ABI_VERSION;
    uint32_t domain;
    uint64_t t_index;
    uint64_t count;
    size_t index;
    zoe_landscape_status_t status = ZOE_LANDSCAPE_OK;

    if (landscape == NULL || path == NULL) {
        return ZOE_LANDSCAPE_ERROR_INVALID;
    }
    descriptor = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (descriptor < 0) {
        return ZOE_LANDSCAPE_ERROR_IO;
    }
    file = fdopen(descriptor, "wb");
    if (file == NULL) {
        close(descriptor);
        return ZOE_LANDSCAPE_ERROR_IO;
    }
    domain = (uint32_t)landscape->domain;
    t_index = landscape->t_index;
    count = (uint64_t)landscape->num_points;
    if (write_exact(file, ZOE_FILE_MAGIC, ZOE_FILE_MAGIC_SIZE) != ZOE_LANDSCAPE_OK ||
        write_exact(file, &abi, sizeof(abi)) != ZOE_LANDSCAPE_OK ||
        write_exact(file, &domain, sizeof(domain)) != ZOE_LANDSCAPE_OK ||
        write_exact(file, &t_index, sizeof(t_index)) != ZOE_LANDSCAPE_OK ||
        write_exact(file, &landscape->tau, sizeof(landscape->tau)) != ZOE_LANDSCAPE_OK ||
        write_exact(file, &landscape->is_simulation, sizeof(landscape->is_simulation)) != ZOE_LANDSCAPE_OK ||
        write_exact(file, landscape->run_id, ZOE_LANDSCAPE_MAX_RUN_ID) != ZOE_LANDSCAPE_OK ||
        write_exact(file, &count, sizeof(count)) != ZOE_LANDSCAPE_OK) {
        status = ZOE_LANDSCAPE_ERROR_IO;
    }
    for (index = 0u; status == ZOE_LANDSCAPE_OK && index < landscape->num_points; index += 1u) {
        const zoe_landscape_point_t *point = &landscape->points[index];
        uint32_t point_domain = (uint32_t)point->domain;
        if (write_exact(file, &point->option_id, sizeof(point->option_id)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point_domain, sizeof(point_domain)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->x, sizeof(point->x)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->y, sizeof(point->y)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->probability, sizeof(point->probability)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->provenance.source_flags, sizeof(point->provenance.source_flags)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->provenance.evidence_id, sizeof(point->provenance.evidence_id)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->provenance.update_step, sizeof(point->provenance.update_step)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->provenance.weight_user, sizeof(point->provenance.weight_user)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->provenance.weight_policy, sizeof(point->provenance.weight_policy)) != ZOE_LANDSCAPE_OK ||
            write_exact(file, &point->provenance.weight_zoe, sizeof(point->provenance.weight_zoe)) != ZOE_LANDSCAPE_OK) {
            status = ZOE_LANDSCAPE_ERROR_IO;
        }
    }
    if (fclose(file) != 0 && status == ZOE_LANDSCAPE_OK) {
        status = ZOE_LANDSCAPE_ERROR_IO;
    }
    return status;
}

zoe_probability_landscape_t *zoe_landscape_read_file(
    const char *path,
    zoe_landscape_status_t *status) {
    FILE *file;
    char magic[ZOE_FILE_MAGIC_SIZE];
    uint32_t abi;
    uint32_t domain;
    uint64_t t_index;
    uint64_t count;
    float tau;
    uint32_t is_simulation;
    char run_id[ZOE_LANDSCAPE_MAX_RUN_ID];
    zoe_probability_landscape_t *landscape = NULL;
    zoe_landscape_status_t result = ZOE_LANDSCAPE_ERROR_FORMAT;
    size_t index;

    if (status == NULL || path == NULL) {
        return NULL;
    }
    file = fopen(path, "rb");
    if (file == NULL) {
        *status = ZOE_LANDSCAPE_ERROR_IO;
        return NULL;
    }
    if (read_exact(file, magic, sizeof(magic)) != ZOE_LANDSCAPE_OK ||
        memcmp(magic, ZOE_FILE_MAGIC, sizeof(magic)) != 0 ||
        read_exact(file, &abi, sizeof(abi)) != ZOE_LANDSCAPE_OK || abi != ZOE_LANDSCAPE_ABI_VERSION ||
        read_exact(file, &domain, sizeof(domain)) != ZOE_LANDSCAPE_OK ||
        read_exact(file, &t_index, sizeof(t_index)) != ZOE_LANDSCAPE_OK ||
        read_exact(file, &tau, sizeof(tau)) != ZOE_LANDSCAPE_OK ||
        read_exact(file, &is_simulation, sizeof(is_simulation)) != ZOE_LANDSCAPE_OK ||
        read_exact(file, run_id, sizeof(run_id)) != ZOE_LANDSCAPE_OK ||
        read_exact(file, &count, sizeof(count)) != ZOE_LANDSCAPE_OK ||
        count == 0u || count > ZOE_LANDSCAPE_MAX_POINTS) {
        fclose(file);
        *status = ZOE_LANDSCAPE_ERROR_FORMAT;
        return NULL;
    }
    run_id[ZOE_LANDSCAPE_MAX_RUN_ID - 1u] = '\0';
    landscape = zoe_landscape_create((zoe_domain_t)domain, t_index, tau, is_simulation, run_id, (size_t)count);
    if (landscape == NULL) {
        fclose(file);
        *status = ZOE_LANDSCAPE_ERROR_INVALID;
        return NULL;
    }
    result = ZOE_LANDSCAPE_OK;
    for (index = 0u; result == ZOE_LANDSCAPE_OK && index < count; index += 1u) {
        uint64_t option_id;
        uint32_t point_domain;
        float x;
        float y;
        float probability;
        zoe_provenance_t provenance;
        if (read_exact(file, &option_id, sizeof(option_id)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &point_domain, sizeof(point_domain)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &x, sizeof(x)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &y, sizeof(y)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &probability, sizeof(probability)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &provenance.source_flags, sizeof(provenance.source_flags)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &provenance.evidence_id, sizeof(provenance.evidence_id)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &provenance.update_step, sizeof(provenance.update_step)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &provenance.weight_user, sizeof(provenance.weight_user)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &provenance.weight_policy, sizeof(provenance.weight_policy)) != ZOE_LANDSCAPE_OK ||
            read_exact(file, &provenance.weight_zoe, sizeof(provenance.weight_zoe)) != ZOE_LANDSCAPE_OK ||
            point_domain != domain) {
            result = ZOE_LANDSCAPE_ERROR_FORMAT;
            break;
        }
        result = zoe_landscape_set_point(
            landscape, index, option_id, x, y, probability, &provenance);
    }
    if (fclose(file) != 0 && result == ZOE_LANDSCAPE_OK) {
        result = ZOE_LANDSCAPE_ERROR_IO;
    }
    if (result != ZOE_LANDSCAPE_OK) {
        zoe_landscape_destroy(landscape);
        *status = result;
        return NULL;
    }
    *status = ZOE_LANDSCAPE_OK;
    return landscape;
}
