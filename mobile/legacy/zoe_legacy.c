#include "zoe_legacy.h"

#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

#define LEGACY_TEXT_SIZE 65
#define LEGACY_WORK_SIZE 128
#define LEGACY_SCALE 32768

typedef struct {
    char digits[LEGACY_TEXT_SIZE];
    int scale;
} Decimal;

typedef struct {
    int whole;
    char remainder[LEGACY_WORK_SIZE];
} Split;

typedef struct {
    Decimal decimal;
    Split split;
    int units;
    int order;
} Value;

typedef struct {
#ifdef _WIN32
    HANDLE handle;
#else
    FILE *stream;
#endif
} LegacyFile;

static int copy_text(char *destination, size_t capacity, const char *source) {
    size_t length;
    if (destination == NULL || source == NULL) return 0;
    length = strlen(source);
    if (length >= capacity) return 0;
    memcpy(destination, source, length + 1);
    return 1;
}

static int append_zeros(char *text, size_t capacity, int count) {
    size_t length = strlen(text);
    if (count < 0 || length + (size_t)count >= capacity) return 0;
    memset(text + length, '0', (size_t)count);
    text[length + (size_t)count] = '\0';
    return 1;
}

static int pad_left(char *text, size_t capacity, size_t width) {
    size_t length = strlen(text);
    if (length >= width) return 1;
    if (width >= capacity) return 0;
    memmove(text + width - length, text, length + 1);
    memset(text, '0', width - length);
    return 1;
}

static int parse_exponent(const char *text, int *exponent) {
    int sign = 1;
    int value = 0;
    int digits = 0;
    if (*text == '-') {
        sign = -1;
        ++text;
    } else if (*text == '+') {
        ++text;
    }
    while (isdigit((unsigned char)*text)) {
        if (value > 100) return 0;
        value = value * 10 + (*text - '0');
        ++text;
        ++digits;
    }
    if (!digits || *text != '\0' || value > 32) return 0;
    *exponent = sign * value;
    return 1;
}

static int decimal_parse(const char *text, Decimal *result) {
    const char *marker = strchr(text, 'e');
    const char *exponent_marker = strchr(text, 'E');
    const char *point;
    char mantissa[LEGACY_TEXT_SIZE];
    char digits[LEGACY_TEXT_SIZE];
    char *write = digits;
    const char *read;
    const char *first;
    int exponent = 0;
    int fraction = 0;
    size_t length;
    if (text == NULL || result == NULL || *text == '\0' || strlen(text) >= LEGACY_TEXT_SIZE) return 0;
    if (marker == NULL) marker = exponent_marker;
    if (marker != NULL && strchr(marker + 1, 'e') != NULL) return 0;
    if (marker != NULL && strchr(marker + 1, 'E') != NULL) return 0;
    length = marker == NULL ? strlen(text) : (size_t)(marker - text);
    if (length >= sizeof(mantissa)) return 0;
    memcpy(mantissa, text, length);
    mantissa[length] = '\0';
    if (marker != NULL && !parse_exponent(marker + 1, &exponent)) return 0;
    point = strchr(mantissa, '.');
    if (point != NULL && strchr(point + 1, '.') != NULL) return 0;
    for (read = mantissa; *read != '\0'; ++read) {
        if (read == point) {
            fraction = (int)(mantissa + length - read - 1);
            continue;
        }
        if (!isdigit((unsigned char)*read)) return 0;
        *write++ = *read;
    }
    *write = '\0';
    if (write == digits || (point == mantissa && fraction == 0)) return 0;
    first = digits;
    while (*first == '0') ++first;
    if (*first == '\0') {
        result->digits[0] = '0';
        result->digits[1] = '\0';
        result->scale = 0;
        return 1;
    }
    if (!copy_text(result->digits, sizeof(result->digits), first)) return 0;
    result->scale = fraction - exponent;
    return result->scale >= -32 && result->scale <= 32;
}

static int multiply_digits(const char *digits, char *result, size_t capacity) {
    size_t length = strlen(digits);
    size_t index;
    int carry = 0;
    if (!copy_text(result, capacity, digits)) return 0;
    for (index = length; index > 0; --index) {
        int value = (result[index - 1] - '0') * LEGACY_SCALE + carry;
        result[index - 1] = (char)('0' + value % 10);
        carry = value / 10;
    }
    while (carry) {
        int digit = carry % 10;
        length = strlen(result);
        if (length + 1 >= capacity) return 0;
        memmove(result + 1, result, length + 1);
        result[0] = (char)('0' + digit);
        carry /= 10;
    }
    return 1;
}

static int whole_value(const char *digits, int *whole) {
    int value = 0;
    const char *read;
    for (read = digits; *read != '\0'; ++read) {
        if (!isdigit((unsigned char)*read) || value > LEGACY_SCALE) return 0;
        value = value * 10 + (*read - '0');
    }
    if (value > LEGACY_SCALE) return 0;
    *whole = value;
    return 1;
}

static int decimal_split(const Decimal *decimal, Split *result) {
    char multiplied[LEGACY_WORK_SIZE];
    char whole[LEGACY_WORK_SIZE];
    size_t length;
    size_t precision;
    size_t split_at;
    if (!multiply_digits(decimal->digits, multiplied, sizeof(multiplied))) return 0;
    result->remainder[0] = '\0';
    if (decimal->scale <= 0) {
        if (!append_zeros(multiplied, sizeof(multiplied), -decimal->scale)) return 0;
        if (!whole_value(multiplied, &result->whole)) return 0;
        return copy_text(result->remainder, sizeof(result->remainder), "0");
    }
    precision = (size_t)decimal->scale;
    length = strlen(multiplied);
    if (length <= precision) {
        result->whole = 0;
        if (!copy_text(result->remainder, sizeof(result->remainder), multiplied)) return 0;
        return pad_left(result->remainder, sizeof(result->remainder), precision);
    }
    split_at = length - precision;
    if (!copy_text(whole, sizeof(whole), multiplied)) return 0;
    whole[split_at] = '\0';
    if (!whole_value(whole, &result->whole)) return 0;
    return copy_text(result->remainder, sizeof(result->remainder), multiplied + split_at);
}

static int compare_remainders(const Split *left, int left_scale, const Split *right, int right_scale) {
    char a[LEGACY_WORK_SIZE];
    char b[LEGACY_WORK_SIZE];
    size_t width = (size_t)(left_scale > right_scale ? left_scale : right_scale);
    if (width < 1) width = 1;
    if (!copy_text(a, sizeof(a), left->remainder) || !copy_text(b, sizeof(b), right->remainder)) return 0;
    if (!pad_left(a, sizeof(a), (size_t)(left_scale > 0 ? left_scale : 1))) return 0;
    if (!pad_left(b, sizeof(b), (size_t)(right_scale > 0 ? right_scale : 1))) return 0;
    if (!append_zeros(a, sizeof(a), (int)(width - strlen(a)))) return 0;
    if (!append_zeros(b, sizeof(b), (int)(width - strlen(b)))) return 0;
    if (strcmp(a, b) < 0) return -1;
    if (strcmp(a, b) > 0) return 1;
    return 0;
}

static int append_hex(char *text, size_t capacity, size_t *position, unsigned value) {
    int written;
    if (*position + 2 >= capacity) return 0;
    written = sprintf(text + *position, "%02X", value & 255U);
    if (written != 2) return 0;
    *position += 2;
    return 1;
}

static int append_short_hex(char *text, size_t capacity, size_t *position, int value) {
    return append_hex(text, capacity, position, (unsigned)((value >> 8) & 255))
        && append_hex(text, capacity, position, (unsigned)(value & 255));
}

static int finite_number(const char *text, double *value) {
    char *end = NULL;
    double parsed;
    if (text == NULL || *text == '\0') return 0;
    parsed = strtod(text, &end);
    if (end == text || *end != '\0' || !isfinite(parsed)) return 0;
    *value = parsed;
    return 1;
}

LegacyStatus legacy_measure(
    const char *probabilities[], int count, const char *tau,
    LegacyMeasurement *result) {
    Value values[LEGACY_MAX_PROBABILITIES];
    Decimal threshold;
    Split threshold_split;
    double total = 0.0;
    double tau_number;
    int sum = 0;
    int remaining;
    int index;
    size_t request_position = 0;
    size_t response_position = 0;
    if (probabilities == NULL || tau == NULL || result == NULL) return LEGACY_INVALID;
    if (count < 1 || count > LEGACY_MAX_PROBABILITIES) return LEGACY_INVALID;
    if (!finite_number(tau, &tau_number) || tau_number < 0.0 || tau_number > 1.0) return LEGACY_INVALID;
    if (!decimal_parse(tau, &threshold) || !decimal_split(&threshold, &threshold_split)) return LEGACY_INVALID;
    memset(result, 0, sizeof(*result));
    result->vocabulary_size = count;
    for (index = 0; index < count; ++index) {
        double number;
        if (!finite_number(probabilities[index], &number) || number < 0.0 || number > 1.0) return LEGACY_INVALID;
        if (!decimal_parse(probabilities[index], &values[index].decimal)) return LEGACY_INVALID;
        if (!decimal_split(&values[index].decimal, &values[index].split)) return LEGACY_INVALID;
        values[index].units = values[index].split.whole;
        values[index].order = index;
        sum += values[index].units;
        total += number;
        if (number > tau_number) ++result->zoe_accessible;
    }
    if (fabs(total - 1.0) > 1e-8) return LEGACY_INVALID;
    remaining = LEGACY_SCALE - sum;
    if (remaining < 0 || remaining > count) return LEGACY_INVALID;
    for (index = 1; index < count; ++index) {
        Value current = values[index];
        int position = index - 1;
        while (position >= 0 && compare_remainders(&current.split, current.decimal.scale,
                                                  &values[position].split, values[position].decimal.scale) > 0) {
            values[position + 1] = values[position];
            --position;
        }
        values[position + 1] = current;
    }
    for (index = 0; index < remaining; ++index) ++values[index].units;
    result->tiny_tau = threshold_split.whole;
    if (threshold.scale > 0) {
        char half[LEGACY_WORK_SIZE];
        Split half_split;
        int comparison;
        if (!copy_text(half, sizeof(half), "5") || !append_zeros(half, sizeof(half), threshold.scale - 1)) return LEGACY_OVERFLOW;
        half_split.whole = 0;
        half_split.remainder[0] = '\0';
        if (!copy_text(half_split.remainder, sizeof(half_split.remainder), half)) return LEGACY_OVERFLOW;
        comparison = compare_remainders(&threshold_split, threshold.scale, &half_split, threshold.scale);
        if (comparison > 0 || (comparison == 0 && (result->tiny_tau & 1))) ++result->tiny_tau;
    }
    for (index = 0; index < count; ++index) {
        int unit = values[index].units;
        result->units[values[index].order] = unit;
        if (unit > result->tiny_tau) ++result->tiny_accessible;
    }
    result->zoe_complement = count - result->zoe_accessible;
    result->tiny_complement = count - result->tiny_accessible;
    result->quantization_changed = result->zoe_accessible != result->tiny_accessible
        || result->tiny_tau != (int)(tau_number * LEGACY_SCALE);
    if (!append_hex(result->request, sizeof(result->request), &request_position, 0x80)
        || !append_hex(result->request, sizeof(result->request), &request_position, 0x02)
        || !append_hex(result->request, sizeof(result->request), &request_position, 0)
        || !append_hex(result->request, sizeof(result->request), &request_position, 0)
        || !append_hex(result->request, sizeof(result->request), &request_position, (unsigned)(2 + count * 2))
        || !append_short_hex(result->request, sizeof(result->request), &request_position, result->tiny_tau)) return LEGACY_OVERFLOW;
    for (index = 0; index < count; ++index) {
        if (!append_short_hex(result->request, sizeof(result->request), &request_position, result->units[index])) return LEGACY_OVERFLOW;
    }
    if (!append_short_hex(result->response, sizeof(result->response), &response_position, result->tiny_accessible)
        || !append_short_hex(result->response, sizeof(result->response), &response_position, result->tiny_complement)
        || !append_short_hex(result->response, sizeof(result->response), &response_position, count)
        || !append_short_hex(result->response, sizeof(result->response), &response_position, result->tiny_tau)
        || !append_hex(result->response, sizeof(result->response), &response_position, 0x90)
        || !append_hex(result->response, sizeof(result->response), &response_position, 0)) return LEGACY_OVERFLOW;
    return LEGACY_OK;
}

static LegacyStatus open_output(const char *path, LegacyFile *file) {
    if (path == NULL || file == NULL || *path == '\0' || strlen(path) >= 260) return LEGACY_INVALID;
#ifdef _WIN32
    file->handle = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file->handle == INVALID_HANDLE_VALUE) {
        return GetLastError() == ERROR_FILE_EXISTS ? LEGACY_EXISTS : LEGACY_IO_ERROR;
    }
#else
    {
        FILE *existing = fopen(path, "rb");
        if (existing != NULL) {
            fclose(existing);
            return LEGACY_EXISTS;
        }
        file->stream = fopen(path, "wb");
        if (file->stream == NULL) return LEGACY_IO_ERROR;
    }
#endif
    return LEGACY_OK;
}

static int write_text(LegacyFile *file, const char *text) {
    size_t length = strlen(text);
#ifdef _WIN32
    DWORD written = 0;
    return WriteFile(file->handle, text, (DWORD)length, &written, NULL) && written == (DWORD)length;
#else
    return fwrite(text, 1, length, file->stream) == length;
#endif
}

static void close_output(LegacyFile *file) {
#ifdef _WIN32
    CloseHandle(file->handle);
#else
    fclose(file->stream);
#endif
}

static void remove_output(const char *path) {
#ifdef _WIN32
    DeleteFileA(path);
#else
    remove(path);
#endif
}

LegacyStatus legacy_write_json(
    const char *path, const char *probabilities[], int count,
    const char *tau, const LegacyMeasurement *measurement) {
    LegacyFile file;
    LegacyMeasurement expected;
    LegacyStatus status;
    char buffer[512];
    int index;
    if (measurement == NULL) return LEGACY_INVALID;
    status = legacy_measure(probabilities, count, tau, &expected);
    if (status != LEGACY_OK) return status;
    if (memcmp(&expected, measurement, sizeof(expected)) != 0) return LEGACY_INVALID;
    status = open_output(path, &file);
    if (status != LEGACY_OK) return status;
    if (!write_text(&file, "{\n  \"schema\": \"zoe-legacy-measurement-v1\",\n"
                         "  \"equation\": {\"creator\": \"Nicholas Michael Kloster\", \"created\": \"2026-03-06\", \"strict\": \"p > tau\", \"equality\": \"excluded\"},\n"
                         "  \"probabilities\": [")) goto error;
    for (index = 0; index < count; ++index) {
        if (index > 0 && !write_text(&file, ", ")) goto error;
        if (!write_text(&file, probabilities[index])) goto error;
    }
    if (!write_text(&file, "],\n  \"tau\": ") || !write_text(&file, tau)) goto error;
    if (sprintf(buffer, ",\n  \"zoe\": {\"accessible\": %d, \"complement\": %d, \"vocabularySize\": %d},\n",
                measurement->zoe_accessible, measurement->zoe_complement, count) < 0) goto error;
    if (!write_text(&file, buffer)) goto error;
    if (!write_text(&file, "  \"tiny\": {\"probabilities\": [")) goto error;
    for (index = 0; index < count; ++index) {
        if (sprintf(buffer, "%d%s", measurement->units[index], index + 1 == count ? "" : ", ") < 0) goto error;
        if (!write_text(&file, buffer)) goto error;
    }
    if (sprintf(buffer, "], \"tau\": %d, \"request\": \"%s\", \"response\": \"%s\", \"accessible\": %d, \"complement\": %d, \"vocabularySize\": %d},\n",
                measurement->tiny_tau, measurement->request, measurement->response,
                measurement->tiny_accessible, measurement->tiny_complement, count) < 0) goto error;
    if (!write_text(&file, buffer)) goto error;
    if (sprintf(buffer, "  \"quantizationChanged\": %s,\n  \"clinicalClaim\": false,\n  \"legacy\": {\"runtime\": \"bounded C99\", \"windows95Or98Verified\": false}\n}\n",
                measurement->quantization_changed ? "true" : "false") < 0) goto error;
    if (!write_text(&file, buffer)) goto error;
    close_output(&file);
    return LEGACY_OK;
error:
    close_output(&file);
    remove_output(path);
    return LEGACY_IO_ERROR;
}
