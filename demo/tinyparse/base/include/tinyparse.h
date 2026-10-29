/*
 * tinyparse - a tiny URL, INI and string helper library.
 *
 * FICTIONAL DEMO PROJECT for Bouncer. It contains intentionally planted bugs
 * and must never be used in production.
 *
 * SPDX-License-Identifier: MIT
 */
#ifndef TINYPARSE_H
#define TINYPARSE_H

#include <stddef.h>

#define TP_VERSION "1.2.0"

/* ---- url.c ------------------------------------------------------------ */

/* Flags for tp_url_decode. */
#define TP_URL_PLUS_AS_SPACE 0x1

/* Returns the value (0-15) of a hex digit, or -1 when c is not a hex digit. */
int tp_hexval(char c);

/*
 * Decodes a percent-encoded buffer of len bytes. src does not need to be NUL
 * terminated. Returns a newly allocated NUL-terminated string (free with
 * free()) and stores its length in *out_len when out_len is not NULL.
 * Returns NULL on allocation failure.
 */
char *tp_url_decode(const char *src, size_t len, int flags, size_t *out_len);

/* Percent-encodes every byte that is not unreserved (RFC 3986). */
char *tp_url_encode(const char *src, size_t len, size_t *out_len);

/* ---- ini.c ------------------------------------------------------------ */

#define TP_INI_MAX_KEY 32
#define TP_INI_MAX_SECTION 32

/* Called once per key/value pair. Return non-zero to stop parsing. */
typedef int (*tp_ini_handler)(void *user, const char *section,
                              const char *key, const char *value);

/*
 * Parses INI text of len bytes. Lines may end with \n or \r\n.
 * Comments start with ';' or '#'. Returns 0 on success, or the 1-based line
 * number of the first malformed line.
 */
int tp_ini_parse(const char *text, size_t len, tp_ini_handler handler,
                 void *user);

/* Looks up section.key and copies the value into out (at most out_size - 1
 * bytes). Returns 0 when found, -1 otherwise. */
int tp_ini_get(const char *text, size_t len, const char *section,
               const char *key, char *out, size_t out_size);

/* ---- str.c ------------------------------------------------------------ */

/* Returns a newly allocated copy of the first n bytes of s. */
char *tp_str_ndup(const char *s, size_t n);

/* Trims ASCII whitespace from both ends of s in place; returns s. */
char *tp_str_trim(char *s);

/* Lower-cases ASCII letters in place; returns s. */
char *tp_str_lower(char *s);

/* Returns 1 when s starts with prefix. */
int tp_str_starts_with(const char *s, const char *prefix);

/* Copies src into dst (size bytes), always NUL terminating when size > 0.
 * Returns strlen(src). */
size_t tp_strlcpy(char *dst, const char *src, size_t size);

/*
 * Splits s on sep into at most max_parts newly allocated strings stored in
 * parts. Returns the number of parts written. Free each with free().
 */
size_t tp_str_split(const char *s, char sep, char **parts, size_t max_parts);

#endif /* TINYPARSE_H */
