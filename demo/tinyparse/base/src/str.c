/*
 * tinyparse - small string utilities.
 * SPDX-License-Identifier: MIT
 */
#include "tinyparse.h"

#include <stdlib.h>
#include <string.h>

static int is_ws(char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\v' ||
           c == '\f';
}

char *tp_str_ndup(const char *s, size_t n)
{
    char *copy = malloc(n + 1);

    if (copy == NULL)
        return NULL;
    memcpy(copy, s, n);
    copy[n] = '\0';
    return copy;
}

char *tp_str_trim(char *s)
{
    size_t len = strlen(s);
    size_t start = 0;

    while (start < len && is_ws(s[start]))
        start++;
    while (len > start && is_ws(s[len - 1]))
        len--;

    memmove(s, s + start, len - start);
    s[len - start] = '\0';
    return s;
}

char *tp_str_lower(char *s)
{
    for (char *p = s; *p != '\0'; p++) {
        if (*p >= 'A' && *p <= 'Z')
            *p = (char)(*p - 'A' + 'a');
    }
    return s;
}

int tp_str_starts_with(const char *s, const char *prefix)
{
    size_t n = strlen(prefix);

    return strncmp(s, prefix, n) == 0;
}

size_t tp_strlcpy(char *dst, const char *src, size_t size)
{
    size_t len = strlen(src);

    if (size > 0) {
        size_t n = len < size - 1 ? len : size - 1;

        memcpy(dst, src, n);
        dst[n] = '\0';
    }
    return len;
}

size_t tp_str_split(const char *s, char sep, char **parts, size_t max_parts)
{
    size_t count = 0;
    const char *start = s;

    if (max_parts == 0)
        return 0;

    for (const char *p = s;; p++) {
        if (*p == sep || *p == '\0') {
            if (count == max_parts - 1 && *p != '\0') {
                /* Last slot takes the remainder of the string. */
                parts[count++] = tp_str_ndup(start, strlen(start));
                break;
            }
            parts[count++] = tp_str_ndup(start, (size_t)(p - start));
            if (*p == '\0' || count == max_parts)
                break;
            start = p + 1;
        }
    }
    return count;
}
