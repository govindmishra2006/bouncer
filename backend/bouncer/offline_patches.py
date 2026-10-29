"""Pre-written candidate patches used ONLY when no model is configured (no NEBIUS_API_KEY).

These are NOT model output. They exist so the patch loop's real machinery — the
anti-cheat scan, the regression-test-must-fail check, the sanitizer re-run and the full
test suite in a fresh sandbox — can be demonstrated offline on the fictional tinyparse
bug. The UI labels every attempt produced here as "offline scripted candidate".

Candidate 1 deliberately cheats (disables the function) so the anti-cheat scan can be
seen rejecting it; candidate 2 is a genuine bounds-check fix.
"""
from __future__ import annotations

URL_DECODE_REGRESSION_TEST = r'''/* Regression test drafted by Bouncer: tp_url_decode() must not read past
 * the end of a buffer that is not NUL-terminated (trailing or truncated '%'). */
#include "tinyparse.h"
#include "tp_test.h"

#include <stdlib.h>

static char *decode_exact(const char *s)
{
    size_t len = strlen(s);
    char *buf = malloc(len); /* exact size: no NUL terminator to hide an over-read */
    memcpy(buf, s, len);
    char *out = tp_url_decode(buf, len, 0, NULL);
    free(buf);
    return out;
}

static void test_trailing_percent(void)
{
    char *s = decode_exact("abc%");
    CHECK_STR(s, "abc%");
    free(s);
}

static void test_truncated_escape(void)
{
    char *s = decode_exact("abc%4");
    CHECK_STR(s, "abc%4");
    free(s);
}

static void test_escape_at_end_still_decodes(void)
{
    char *s = decode_exact("abc%41");
    CHECK_STR(s, "abcA");
    free(s);
}

int main(void)
{
    RUN(test_trailing_percent);
    RUN(test_truncated_escape);
    RUN(test_escape_at_end_still_decodes);
    return TEST_SUMMARY();
}
'''

CANDIDATES = {
    ("src/url.c", "tp_url_decode"): [
        {
            "rationale": "Stop decoding entirely: return an empty result so no escape is ever read.",
            "edits": [
                {
                    "file": "src/url.c",
                    "find": "    if (out == NULL)\n        return NULL;\n\n    for (size_t i = 0; i < len; i++) {\n        char c = src[i];\n\n        /* Fast path",
                    "replace": "    if (out == NULL)\n        return NULL;\n\n    out[0] = '\\0';\n    return out;\n\n    for (size_t i = 0; i < len; i++) {\n        char c = src[i];\n\n        /* Fast path",
                }
            ],
            "test_code": URL_DECODE_REGRESSION_TEST,
        },
        {
            "rationale": "Only treat '%' as an escape when two more bytes are inside the buffer (i + 2 < len), "
            "restoring the bounds check the 1.2 fast path dropped.",
            "edits": [
                {
                    "file": "src/url.c",
                    "find": "        if (c == '%' && tp_hexval(src[i + 1]) >= 0 &&\n            tp_hexval(src[i + 2]) >= 0) {",
                    "replace": "        if (c == '%' && i + 2 < len && tp_hexval(src[i + 1]) >= 0 &&\n            tp_hexval(src[i + 2]) >= 0) {",
                }
            ],
            "test_code": URL_DECODE_REGRESSION_TEST,
        },
    ]
}


def candidates_for(file: str, function: str) -> list[dict]:
    return CANDIDATES.get((file, function), [])
