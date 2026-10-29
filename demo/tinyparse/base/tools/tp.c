/*
 * tp - command-line front end for tinyparse.
 *
 *   tp decode [--plus]   decode percent-encoded stdin
 *   tp encode            percent-encode stdin
 *   tp ini               parse INI from stdin, print section.key=value
 *   tp get SECTION KEY   print one INI value from stdin
 *   tp trim              trim whitespace from stdin
 *   tp split SEP         split stdin on SEP, one part per line
 *
 * Input is read into a heap buffer of exactly the input's size.
 * SPDX-License-Identifier: MIT
 */
#include "tinyparse.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *read_all(FILE *f, size_t *len)
{
    size_t cap = 4096;
    size_t n = 0;
    char *buf = malloc(cap);

    if (buf == NULL)
        return NULL;
    for (;;) {
        size_t got = fread(buf + n, 1, cap - n, f);

        n += got;
        if (got == 0)
            break;
        if (n == cap) {
            char *grown = realloc(buf, cap * 2);

            if (grown == NULL) {
                free(buf);
                return NULL;
            }
            buf = grown;
            cap *= 2;
        }
    }

    /* Shrink to the exact size so tools behave like real callers. */
    char *exact = malloc(n > 0 ? n : 1);

    if (exact == NULL) {
        free(buf);
        return NULL;
    }
    memcpy(exact, buf, n);
    free(buf);
    *len = n;
    return exact;
}

static int print_pair(void *user, const char *section, const char *key,
                      const char *value)
{
    (void)user;
    if (section[0] != '\0')
        printf("%s.%s=%s\n", section, key, value);
    else
        printf("%s=%s\n", key, value);
    return 0;
}

static int usage(void)
{
    fprintf(stderr, "usage: tp decode [--plus] | encode | ini | "
                    "get SECTION KEY | trim | split SEP\n");
    return 2;
}

int main(int argc, char **argv)
{
    size_t len = 0;
    char *in;
    int rc = 0;

    if (argc < 2)
        return usage();

    in = read_all(stdin, &len);
    if (in == NULL) {
        fprintf(stderr, "tp: out of memory\n");
        return 1;
    }

    if (strcmp(argv[1], "decode") == 0) {
        int flags = (argc > 2 && strcmp(argv[2], "--plus") == 0)
                        ? TP_URL_PLUS_AS_SPACE
                        : 0;
        size_t out_len = 0;
        char *out = tp_url_decode(in, len, flags, &out_len);

        fwrite(out, 1, out_len, stdout);
        putchar('\n');
        free(out);
    } else if (strcmp(argv[1], "encode") == 0) {
        char *out = tp_url_encode(in, len, NULL);

        puts(out);
        free(out);
    } else if (strcmp(argv[1], "ini") == 0) {
        rc = tp_ini_parse(in, len, print_pair, NULL);
        if (rc != 0)
            fprintf(stderr, "tp: parse error on line %d\n", rc);
    } else if (strcmp(argv[1], "get") == 0 && argc == 4) {
        char value[256];

        rc = tp_ini_get(in, len, argv[2], argv[3], value, sizeof(value));
        if (rc == 0)
            puts(value);
        else
            fprintf(stderr, "tp: %s.%s not found\n", argv[2], argv[3]);
    } else if (strcmp(argv[1], "trim") == 0) {
        char *s = tp_str_ndup(in, len);

        printf("[%s]\n", tp_str_trim(s));
        free(s);
    } else if (strcmp(argv[1], "split") == 0 && argc == 3) {
        char *s = tp_str_ndup(in, len);
        char *parts[64];
        size_t n = tp_str_split(s, argv[2][0], parts, 64);

        for (size_t i = 0; i < n; i++) {
            printf("%s\n", parts[i]);
            free(parts[i]);
        }
        free(s);
    } else {
        rc = usage();
    }

    free(in);
    return rc == 0 ? 0 : 1;
}
