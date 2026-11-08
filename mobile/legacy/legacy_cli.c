#include "zoe_legacy.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

static char *trim(char *text) {
    char *end;
    while (isspace((unsigned char)*text)) ++text;
    end = text + strlen(text);
    while (end > text && isspace((unsigned char)end[-1])) --end;
    *end = '\0';
    return text;
}

int main(int argc, char **argv) {
    char input[2048];
    const char *probabilities[LEGACY_MAX_PROBABILITIES];
    char *token;
    int count = 0;
    LegacyMeasurement result;
    LegacyStatus status;
    if (argc != 4) {
        fprintf(stderr, "usage: zoe-legacy OUTPUT.json PROBABILITIES TAU\n"
                        "example: zoe-legacy result.json 0.70,0.20,0.08,0.02 0.05\n");
        return 2;
    }
    if (strlen(argv[2]) >= sizeof(input) || *argv[2] == '\0'
        || argv[2][0] == ',' || argv[2][strlen(argv[2]) - 1] == ','
        || strstr(argv[2], ",,") != NULL) {
        fprintf(stderr, "invalid distribution\n");
        return 2;
    }
    strcpy(input, argv[2]);
    token = strtok(input, ",");
    while (token != NULL) {
        if (count >= LEGACY_MAX_PROBABILITIES) {
            fprintf(stderr, "distribution must contain 1 to 64 probabilities\n");
            return 2;
        }
        probabilities[count] = trim(token);
        if (*probabilities[count] == '\0') {
            fprintf(stderr, "invalid empty probability\n");
            return 2;
        }
        ++count;
        token = strtok(NULL, ",");
    }
    status = legacy_measure(probabilities, count, trim(argv[3]), &result);
    if (status != LEGACY_OK) {
        fprintf(stderr, "invalid measurement input\n");
        return 2;
    }
    status = legacy_write_json(argv[1], probabilities, count, trim(argv[3]), &result);
    if (status == LEGACY_EXISTS) {
        fprintf(stderr, "refusing to overwrite %s\n", argv[1]);
        return 3;
    }
    if (status != LEGACY_OK) {
        fprintf(stderr, "could not write %s\n", argv[1]);
        return 4;
    }
    printf("Zoe = %d of %d; Tiny = %d of %d\n",
           result.zoe_accessible, count, result.tiny_accessible, count);
    printf("request  %s\nresponse %s\n", result.request, result.response);
    return 0;
}
