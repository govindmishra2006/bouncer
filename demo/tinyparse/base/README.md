# tinyparse (fictional demo project)

A tiny C library for URL percent-decoding, INI parsing and string helpers.

**This project is fictional test data for Bouncer.** It contains two intentionally
planted bugs and must never be used in production.

    make            # build library and the `tp` tool
    make test       # run the test suite
    make SAN=1 test # same, with AddressSanitizer + UBSan
    printf 'a%%20b' | ./build/tp decode
