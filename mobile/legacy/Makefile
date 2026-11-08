CC ?= cc
CFLAGS ?= -std=c99 -O2 -Wall -Wextra -Wpedantic

CORE = zoe_legacy.c zoe_legacy.h

.PHONY: all check clean

all: build/zoe-legacy build/zoe_legacy_test

build:
	mkdir -p build

build/zoe-legacy: $(CORE) legacy_cli.c | build
	$(CC) $(CFLAGS) zoe_legacy.c legacy_cli.c -o $@

build/zoe_legacy_test: $(CORE) test_zoe_legacy.c | build
	$(CC) $(CFLAGS) zoe_legacy.c test_zoe_legacy.c -o $@

check: build/zoe_legacy_test build/zoe-legacy
	./build/zoe_legacy_test
	./build/zoe-legacy build/example.json 0.70,0.20,0.08,0.02 0.05
	test -f build/example.json

clean:
	rm -rf build
