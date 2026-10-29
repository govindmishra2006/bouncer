/* tinyparse test suite. SPDX-License-Identifier: MIT */
#include "tinyparse.h"
#include "tp_test.h"

#include <stdlib.h>

/* ---- url ---------------------------------------------------------------- */

static char *dec(const char *s, int flags)
{
    return tp_url_decode(s, strlen(s), flags, NULL);
}

static void test_hexval_digits(void) { CHECK(tp_hexval('0') == 0 && tp_hexval('9') == 9); }
static void test_hexval_lower(void) { CHECK(tp_hexval('a') == 10 && tp_hexval('f') == 15); }
static void test_hexval_upper(void) { CHECK(tp_hexval('A') == 10 && tp_hexval('F') == 15); }
static void test_hexval_invalid(void) { CHECK(tp_hexval('g') == -1 && tp_hexval('%') == -1); }

static void test_decode_plain(void)
{
    char *s = dec("hello", 0);
    CHECK_STR(s, "hello");
    free(s);
}

static void test_decode_escape(void)
{
    char *s = dec("a%20b", 0);
    CHECK_STR(s, "a b");
    free(s);
}

static void test_decode_lowercase_hex(void)
{
    char *s = dec("%2f%2F", 0);
    CHECK_STR(s, "//");
    free(s);
}

static void test_decode_plus_kept(void)
{
    char *s = dec("a+b", 0);
    CHECK_STR(s, "a+b");
    free(s);
}

static void test_decode_plus_as_space(void)
{
    char *s = dec("a+b", TP_URL_PLUS_AS_SPACE);
    CHECK_STR(s, "a b");
    free(s);
}

static void test_decode_invalid_escape_kept(void)
{
    char *s = dec("100%zz", 0);
    CHECK_STR(s, "100%zz");
    free(s);
}

static void test_decode_escape_at_end(void)
{
    char *s = dec("x%41", 0);
    CHECK_STR(s, "xA");
    free(s);
}

static void test_decode_empty(void)
{
    size_t n = 99;
    char *s = tp_url_decode("", 0, 0, &n);
    CHECK(s != NULL && n == 0 && s[0] == '\0');
    free(s);
}

static void test_decode_out_len(void)
{
    size_t n = 0;
    char *s = tp_url_decode("%41%42c", 7, 0, &n);
    CHECK(n == 3);
    CHECK_STR(s, "ABc");
    free(s);
}

static void test_decode_embedded_nul(void)
{
    size_t n = 0;
    char *s = tp_url_decode("a%00b", 5, 0, &n);
    CHECK(n == 3 && s[1] == '\0' && s[2] == 'b');
    free(s);
}

static void test_encode_unreserved(void)
{
    char *s = tp_url_encode("Az09-_.~", 8, NULL);
    CHECK_STR(s, "Az09-_.~");
    free(s);
}

static void test_encode_space(void)
{
    char *s = tp_url_encode("a b", 3, NULL);
    CHECK_STR(s, "a%20b");
    free(s);
}

static void test_encode_high_byte(void)
{
    char *s = tp_url_encode("\xff", 1, NULL);
    CHECK_STR(s, "%FF");
    free(s);
}

static void test_roundtrip(void)
{
    const char *orig = "key=a b&c/d?e";
    char *enc = tp_url_encode(orig, strlen(orig), NULL);
    char *back = dec(enc, 0);
    CHECK_STR(back, orig);
    free(enc);
    free(back);
}

/* ---- ini ---------------------------------------------------------------- */

struct collect {
    char buf[1024];
    int count;
};

static int collect_handler(void *user, const char *section, const char *key,
                           const char *value)
{
    struct collect *c = user;
    size_t used = strlen(c->buf);
    snprintf(c->buf + used, sizeof(c->buf) - used, "%s.%s=%s;", section, key,
             value);
    c->count++;
    return 0;
}

static int parse(const char *text, struct collect *c)
{
    memset(c, 0, sizeof(*c));
    return tp_ini_parse(text, strlen(text), collect_handler, c);
}

static void test_ini_simple(void)
{
    struct collect c;
    CHECK(parse("a=1\n", &c) == 0);
    CHECK_STR(c.buf, ".a=1;");
}

static void test_ini_section(void)
{
    struct collect c;
    CHECK(parse("[db]\nhost=localhost\n", &c) == 0);
    CHECK_STR(c.buf, "db.host=localhost;");
}

static void test_ini_whitespace(void)
{
    struct collect c;
    CHECK(parse("  [ s ]\n  k  =  v  \n", &c) == 0);
    CHECK(c.count == 1);
}

static void test_ini_comments(void)
{
    struct collect c;
    CHECK(parse("; c\n# c\nk=v\n", &c) == 0);
    CHECK(c.count == 1);
}

static void test_ini_crlf(void)
{
    struct collect c;
    CHECK(parse("k=v\r\nx=y\r\n", &c) == 0);
    CHECK_STR(c.buf, ".k=v;.x=y;");
}

static void test_ini_no_trailing_newline(void)
{
    struct collect c;
    CHECK(parse("k=v", &c) == 0);
    CHECK(c.count == 1);
}

static void test_ini_empty_value(void)
{
    struct collect c;
    CHECK(parse("k=\n", &c) == 0);
    CHECK_STR(c.buf, ".k=;");
}

static void test_ini_missing_equals(void)
{
    struct collect c;
    CHECK(parse("k=v\nbroken\n", &c) == 2);
}

static void test_ini_unclosed_section(void)
{
    struct collect c;
    CHECK(parse("[open\n", &c) == 1);
}

static void test_ini_empty_key(void)
{
    struct collect c;
    CHECK(parse("=v\n", &c) == 1);
}

static void test_ini_long_key_truncated(void)
{
    struct collect c;
    CHECK(parse("abcdefghijklmnopqrstuvwxyz0123456789=v\n", &c) == 0);
    CHECK(c.count == 1);
}

static void test_ini_long_value_truncated(void)
{
    char text[600];
    struct collect c;
    memset(text, 'v', sizeof(text));
    memcpy(text, "k=", 2);
    text[sizeof(text) - 1] = '\0';
    CHECK(parse(text, &c) == 0);
}

static void test_ini_get_found(void)
{
    const char *t = "[a]\nx=1\n[b]\nx=2\n";
    char out[16];
    CHECK(tp_ini_get(t, strlen(t), "b", "x", out, sizeof(out)) == 0);
    CHECK_STR(out, "2");
}

static void test_ini_get_missing(void)
{
    const char *t = "[a]\nx=1\n";
    char out[16];
    CHECK(tp_ini_get(t, strlen(t), "a", "y", out, sizeof(out)) == -1);
}

static void test_ini_get_small_buffer(void)
{
    const char *t = "k=abcdef\n";
    char out[4];
    CHECK(tp_ini_get(t, strlen(t), "", "k", out, sizeof(out)) == 0);
    CHECK_STR(out, "abc");
}

static void test_ini_value_with_equals(void)
{
    struct collect c;
    CHECK(parse("url=a=b\n", &c) == 0);
    CHECK_STR(c.buf, ".url=a=b;");
}

/* ---- str ---------------------------------------------------------------- */

static void test_trim_both(void)
{
    char s[] = "  hi  ";
    CHECK_STR(tp_str_trim(s), "hi");
}

static void test_trim_none(void)
{
    char s[] = "hi";
    CHECK_STR(tp_str_trim(s), "hi");
}

static void test_trim_all_space(void)
{
    char s[] = " \t\n ";
    CHECK_STR(tp_str_trim(s), "");
}

static void test_trim_empty(void)
{
    char s[] = "";
    CHECK_STR(tp_str_trim(s), "");
}

static void test_lower(void)
{
    char s[] = "MiXeD 123";
    CHECK_STR(tp_str_lower(s), "mixed 123");
}

static void test_starts_with(void)
{
    CHECK(tp_str_starts_with("tinyparse", "tiny"));
    CHECK(!tp_str_starts_with("tiny", "tinyparse"));
}

static void test_strlcpy_fits(void)
{
    char d[8];
    CHECK(tp_strlcpy(d, "abc", sizeof(d)) == 3);
    CHECK_STR(d, "abc");
}

static void test_strlcpy_truncates(void)
{
    char d[4];
    CHECK(tp_strlcpy(d, "abcdef", sizeof(d)) == 6);
    CHECK_STR(d, "abc");
}

static void test_ndup(void)
{
    char *s = tp_str_ndup("abcdef", 3);
    CHECK_STR(s, "abc");
    free(s);
}

static void test_split_basic(void)
{
    char *p[4];
    size_t n = tp_str_split("a,b,c", ',', p, 4);
    CHECK(n == 3);
    CHECK_STR(p[2], "c");
    for (size_t i = 0; i < n; i++)
        free(p[i]);
}

static void test_split_empty_fields(void)
{
    char *p[4];
    size_t n = tp_str_split("a,,b", ',', p, 4);
    CHECK(n == 3);
    CHECK_STR(p[1], "");
    for (size_t i = 0; i < n; i++)
        free(p[i]);
}

static void test_split_max_parts(void)
{
    char *p[2];
    size_t n = tp_str_split("a,b,c", ',', p, 2);
    CHECK(n == 2);
    CHECK_STR(p[1], "b,c");
    for (size_t i = 0; i < n; i++)
        free(p[i]);
}

static void test_split_zero_parts(void)
{
    CHECK(tp_str_split("a,b", ',', NULL, 0) == 0);
}

static void test_version(void) { CHECK(strncmp(TP_VERSION, "1.", 2) == 0); }

int main(void)
{
    RUN(test_hexval_digits);
    RUN(test_hexval_lower);
    RUN(test_hexval_upper);
    RUN(test_hexval_invalid);
    RUN(test_decode_plain);
    RUN(test_decode_escape);
    RUN(test_decode_lowercase_hex);
    RUN(test_decode_plus_kept);
    RUN(test_decode_plus_as_space);
    RUN(test_decode_invalid_escape_kept);
    RUN(test_decode_escape_at_end);
    RUN(test_decode_empty);
    RUN(test_decode_out_len);
    RUN(test_decode_embedded_nul);
    RUN(test_encode_unreserved);
    RUN(test_encode_space);
    RUN(test_encode_high_byte);
    RUN(test_roundtrip);
    RUN(test_ini_simple);
    RUN(test_ini_section);
    RUN(test_ini_whitespace);
    RUN(test_ini_comments);
    RUN(test_ini_crlf);
    RUN(test_ini_no_trailing_newline);
    RUN(test_ini_empty_value);
    RUN(test_ini_missing_equals);
    RUN(test_ini_unclosed_section);
    RUN(test_ini_empty_key);
    RUN(test_ini_long_key_truncated);
    RUN(test_ini_long_value_truncated);
    RUN(test_ini_get_found);
    RUN(test_ini_get_missing);
    RUN(test_ini_get_small_buffer);
    RUN(test_ini_value_with_equals);
    RUN(test_trim_both);
    RUN(test_trim_none);
    RUN(test_trim_all_space);
    RUN(test_trim_empty);
    RUN(test_lower);
    RUN(test_starts_with);
    RUN(test_strlcpy_fits);
    RUN(test_strlcpy_truncates);
    RUN(test_ndup);
    RUN(test_split_basic);
    RUN(test_split_empty_fields);
    RUN(test_split_max_parts);
    RUN(test_split_zero_parts);
    RUN(test_version);
    return TEST_SUMMARY();
}
