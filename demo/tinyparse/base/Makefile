# tinyparse build. `make SAN=1` builds with AddressSanitizer + UBSan.
CC ?= cc
CFLAGS ?= -O1 -g
CFLAGS += -std=c11 -Wall -Wextra -Iinclude
ifeq ($(SAN),1)
CFLAGS += -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=undefined
LDFLAGS += -fsanitize=address,undefined
endif

SRC := src/url.c src/ini.c src/str.c
OBJ := $(SRC:src/%.c=build/%.o)
TESTS := $(patsubst tests/%.c,build/%,$(wildcard tests/test_*.c))

all: build/libtinyparse.a build/tp

build:
	mkdir -p build

build/%.o: src/%.c include/tinyparse.h | build
	$(CC) $(CFLAGS) -c $< -o $@

build/libtinyparse.a: $(OBJ)
	ar rcs $@ $^

build/tp: tools/tp.c build/libtinyparse.a
	$(CC) $(CFLAGS) $< build/libtinyparse.a $(LDFLAGS) -o $@

build/test_%: tests/test_%.c build/libtinyparse.a tests/tp_test.h
	$(CC) $(CFLAGS) $< build/libtinyparse.a $(LDFLAGS) -o $@

test: $(TESTS)
	@set -e; for t in $(TESTS); do echo "== $$t"; ./$$t; done

clean:
	rm -rf build

.PHONY: all test clean
