#ifndef ZOE_LEGACY_H
#define ZOE_LEGACY_H

#ifdef __cplusplus
extern "C" {
#endif

#define LEGACY_MAX_PROBABILITIES 64
#define LEGACY_REQUEST_HEX_SIZE 271
#define LEGACY_RESPONSE_HEX_SIZE 21

typedef enum {
    LEGACY_OK = 0,
    LEGACY_INVALID = 1,
    LEGACY_EXISTS = 2,
    LEGACY_IO_ERROR = 3,
    LEGACY_OVERFLOW = 4
} LegacyStatus;

typedef struct {
    int zoe_accessible;
    int zoe_complement;
    int tiny_accessible;
    int tiny_complement;
    int vocabulary_size;
    int tiny_tau;
    int units[LEGACY_MAX_PROBABILITIES];
    char request[LEGACY_REQUEST_HEX_SIZE];
    char response[LEGACY_RESPONSE_HEX_SIZE];
    int quantization_changed;
} LegacyMeasurement;

LegacyStatus legacy_measure(
    const char *probabilities[], int count, const char *tau,
    LegacyMeasurement *result);

LegacyStatus legacy_write_json(
    const char *path, const char *probabilities[], int count,
    const char *tau, const LegacyMeasurement *measurement);

#ifdef __cplusplus
}
#endif
#endif
