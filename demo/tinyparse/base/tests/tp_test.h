/* Minimal test harness for tinyparse. SPDX-License-Identifier: MIT */
#ifndef TP_TEST_H
#define TP_TEST_H

#include <stdio.h>
#include <string.h>

static int tp_failures = 0;
static int tp_run = 0;

#define CHECK(cond)                                                          \
    do {                                                                     \
        if (!(cond)) {                                                       \
            fprintf(stderr, "  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
            tp_failures++;                                                   \
            return;                                                          \
        }                                                                    \
    } while (0)

#define CHECK_STR(a, b) CHECK(strcmp((a), (b)) == 0)

#define RUN(test)                                                            \
    do {                                                                     \
        int before = tp_failures;                                            \
        tp_run++;                                                            \
        test();                                                              \
        printf("%s %s\n", tp_failures == before ? "ok  " : "FAIL", #test);   \
    } while (0)

#define TEST_SUMMARY()                                                       \
    (printf("%d tests, %d failed\n", tp_run, tp_failures), tp_failures ? 1 : 0)

#endif
