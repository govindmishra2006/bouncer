/*
 * tinyparse - URL percent-encoding helpers.
 * SPDX-License-Identifier: MIT
 */
#include "tinyparse.h"

#include <stdlib.h>
#include <string.h>

int tp_hexval(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

static int is_unreserved(unsigned char c)
{
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9'))
        return 1;
    return c == '-' || c == '_' || c == '.' || c == '~';
}

char *tp_url_decode(const char *src, size_t len, int flags, size_t *out_len)
{
    /* Decoded output is never longer than the input. */
    char *out = malloc(len + 1);
    size_t o = 0;

    if (out == NULL)
        return NULL;

    for (size_t i = 0; i < len; i++) {
        char c = src[i];

        /* Fast path: an escape is '%' followed by two hex digits. */
        if (c == '%' && tp_hexval(src[i + 1]) >= 0 &&
            tp_hexval(src[i + 2]) >= 0) {
            out[o++] = (char)(tp_hexval(src[i + 1]) * 16 +
                              tp_hexval(src[i + 2]));
            i += 2;
        } else if (c == '+' && (flags & TP_URL_PLUS_AS_SPACE)) {
            out[o++] = ' ';
        } else {
            out[o++] = c;
        }
    }

    out[o] = '\0';
    if (out_len != NULL)
        *out_len = o;
    return out;
}

char *tp_url_encode(const char *src, size_t len, size_t *out_len)
{
    static const char hex[] = "0123456789ABCDEF";
    char *out = malloc(len * 3 + 1);
    size_t o = 0;

    if (out == NULL)
        return NULL;

    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)src[i];

        if (is_unreserved(c)) {
            out[o++] = (char)c;
        } else {
            out[o++] = '%';
            out[o++] = hex[c >> 4];
            out[o++] = hex[c & 0x0F];
        }
    }

    out[o] = '\0';
    if (out_len != NULL)
        *out_len = o;
    return out;
}
