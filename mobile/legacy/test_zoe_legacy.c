#include "zoe_legacy.h"

#include <stdio.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "check failed at line %d: %s\n", __LINE__, #condition); \
    return 1; \
} } while (0)

static int check_default(void) {
    static const char *probabilities[] = {"0.70", "0.20", "0.08", "0.02"};
    LegacyMeasurement result;
    CHECK(legacy_measure(probabilities, 4, "0.05", &result) == LEGACY_OK);
    CHECK(result.zoe_accessible == 3 && result.tiny_accessible == 3);
    CHECK(result.zoe_complement == 1 && result.tiny_complement == 1);
    CHECK(strcmp(result.request, "800200000A0666599A199A0A3D028F") == 0);
    CHECK(strcmp(result.response, "00030001000406669000") == 0);
    CHECK(!result.quantization_changed);
    CHECK(legacy_measure(probabilities, 4, "0.20", &result) == LEGACY_OK);
    CHECK(result.zoe_accessible == 1 && result.tiny_accessible == 1);
    return 0;
}

static int check_fixtures(void) {
    static const char *uniform[] = {"0.25", "0.25", "0.25", "0.25"};
    static const char *mixed[] = {"0.1", "0.2", "0.3", "0.4"};
    static const char *small[] = {"0.00001", "0.99999"};
    static const char *thirds[] = {
        "0.3333333333333333", "0.3333333333333333", "0.3333333333333334",
    };
    static const char *zeroes[] = {"1", "0", "0"};
    static const char *invalid[] = {"0.5", "0.4"};
    const char *maximum[64];
    LegacyMeasurement result;
    int index;
    CHECK(legacy_measure(uniform, 4, "1", &result) == LEGACY_OK);
    CHECK(result.zoe_accessible == 0 && result.tiny_accessible == 0);
    CHECK(legacy_measure(zeroes, 3, "0", &result) == LEGACY_OK);
    CHECK(result.zoe_accessible == 1 && result.tiny_accessible == 1);
    CHECK(legacy_measure(invalid, 2, "0.05", &result) == LEGACY_INVALID);
    for (index = 0; index < 64; ++index) maximum[index] = "0.015625";
    CHECK(legacy_measure(maximum, 64, "0", &result) == LEGACY_OK);
    CHECK(strlen(result.request) == 270);
    CHECK(strcmp(result.response, "00400000004000009000") == 0);
    CHECK(legacy_measure(mixed, 4, "0.2", &result) == LEGACY_OK);
    CHECK(strcmp(result.request, "800200000A199A0CCD199A26663333") == 0);
    CHECK(legacy_measure(uniform, 4, "0.25", &result) == LEGACY_OK);
    CHECK(strcmp(result.response, "00000004000420009000") == 0);
    CHECK(legacy_measure(small, 2, "0.00001", &result) == LEGACY_OK);
    CHECK(strcmp(result.request, "8002000006000000008000") == 0);
    CHECK(legacy_measure(thirds, 3, "0.3333333333333333", &result) == LEGACY_OK);
    CHECK(strcmp(result.request, "80020000082AAB2AAB2AAA2AAB") == 0);
    return 0;
}

static int check_json(void) {
    static const char *probabilities[] = {"0.70", "0.20", "0.08", "0.02"};
    static const char *path = "build/test-measurement.json";
    LegacyMeasurement result;
    LegacyStatus status;
    FILE *file;
    char buffer[4096];
    size_t size;
    CHECK(legacy_measure(probabilities, 4, "0.05", &result) == LEGACY_OK);
    CHECK(legacy_write_json(path, probabilities, 4, "0.05", &result) == LEGACY_OK);
    status = legacy_write_json(path, probabilities, 4, "0.05", &result);
#ifdef _WIN32
    CHECK(status == LEGACY_EXISTS);
#else
    CHECK(status == LEGACY_EXISTS || status == LEGACY_IO_ERROR);
#endif
    file = fopen(path, "rb");
    CHECK(file != NULL);
    size = fread(buffer, 1, sizeof(buffer) - 1, file);
    CHECK(size > 0 && size < sizeof(buffer) - 1);
    buffer[size] = '\0';
    fclose(file);
    CHECK(strstr(buffer, "Nicholas Michael Kloster") != NULL);
    CHECK(strstr(buffer, "p > tau") != NULL);
    CHECK(strstr(buffer, "\"accessible\": 3") != NULL);
    CHECK(strstr(buffer, "800200000A0666599A199A0A3D028F") != NULL);
    CHECK(strstr(buffer, "\"windows95Or98Verified\": false") != NULL);
    CHECK(remove(path) == 0);
    return 0;
}

int main(void) {
    if (check_default() != 0) return 1;
    if (check_fixtures() != 0) return 1;
    if (check_json() != 0) return 1;
    puts("Zoe legacy: 3 suites passed");
    return 0;
}
