/*
 * tinyparse - minimal INI parser.
 * SPDX-License-Identifier: MIT
 */
#include "tinyparse.h"

#include <string.h>

static int is_space(char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

/* Returns the [start, end) range of line with surrounding whitespace removed. */
static void strip_range(const char **start, const char **end)
{
    while (*start < *end && is_space(**start))
        (*start)++;
    while (*end > *start && is_space(*(*end - 1)))
        (*end)--;
}

static void copy_bounded(char *dst, size_t dst_size, const char *src,
                         size_t n)
{
    if (n >= dst_size)
        n = dst_size - 1;
    memcpy(dst, src, n);
    dst[n] = '\0';
}

int tp_ini_parse(const char *text, size_t len, tp_ini_handler handler,
                 void *user)
{
    char section[TP_INI_MAX_SECTION] = "";
    char key[TP_INI_MAX_KEY];
    char value[256];
    const char *p = text;
    const char *end = text + len;
    int lineno = 0;

    while (p < end) {
        const char *line_start = p;
        const char *line_end = memchr(p, '\n', (size_t)(end - p));

        if (line_end == NULL)
            line_end = end;
        p = line_end < end ? line_end + 1 : end;
        lineno++;

        strip_range(&line_start, &line_end);
        if (line_start == line_end)
            continue;
        if (*line_start == ';' || *line_start == '#')
            continue;

        if (*line_start == '[') {
            const char *close = memchr(line_start, ']',
                                       (size_t)(line_end - line_start));
            if (close == NULL)
                return lineno;
            copy_bounded(section, sizeof(section), line_start + 1,
                         (size_t)(close - line_start - 1));
            continue;
        }

        const char *eq = memchr(line_start, '=',
                                (size_t)(line_end - line_start));
        if (eq == NULL)
            return lineno;

        const char *k_start = line_start;
        const char *k_end = eq;
        const char *v_start = eq + 1;
        const char *v_end = line_end;

        strip_range(&k_start, &k_end);
        strip_range(&v_start, &v_end);
        if (k_start == k_end)
            return lineno;

        size_t klen = (size_t)(k_end - k_start);
        if (klen > TP_INI_MAX_KEY)
            klen = TP_INI_MAX_KEY;
        memcpy(key, k_start, klen);
        key[klen] = '\0';

        copy_bounded(value, sizeof(value), v_start,
                     (size_t)(v_end - v_start));

        if (handler(user, section, key, value) != 0)
            break;
    }

    return 0;
}

struct get_ctx {
    const char *section;
    const char *key;
    char *out;
    size_t out_size;
    int found;
};

static int get_handler(void *user, const char *section, const char *key,
                       const char *value)
{
    struct get_ctx *ctx = user;

    if (strcmp(section, ctx->section) == 0 && strcmp(key, ctx->key) == 0) {
        tp_strlcpy(ctx->out, value, ctx->out_size);
        ctx->found = 1;
        return 1;
    }
    return 0;
}

int tp_ini_get(const char *text, size_t len, const char *section,
               const char *key, char *out, size_t out_size)
{
    struct get_ctx ctx = { section, key, out, out_size, 0 };

    tp_ini_parse(text, len, get_handler, &ctx);
    return ctx.found ? 0 : -1;
}
