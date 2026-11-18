CC ?= cc
BUILD_DIR ?= build
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic -Werror

.PHONY: all check clean

all: $(BUILD_DIR)/libzoe_landscape.a $(BUILD_DIR)/test_zoe_landscape

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/zoe_landscape.o: zoe_landscape.c zoe_landscape.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/libzoe_landscape.a: $(BUILD_DIR)/zoe_landscape.o
	ar rcs $@ $<

$(BUILD_DIR)/test_zoe_landscape: test_zoe_landscape.c zoe_landscape.h $(BUILD_DIR)/libzoe_landscape.a
	$(CC) $(CFLAGS) test_zoe_landscape.c $(BUILD_DIR)/libzoe_landscape.a -lm -o $@

check: all
	$(BUILD_DIR)/test_zoe_landscape

clean:
	rm -rf $(BUILD_DIR)
