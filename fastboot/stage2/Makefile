CC      := clang
LD      := arm-none-eabi-ld
OBJCOPY := arm-none-eabi-objcopy
SIZE    := arm-none-eabi-size

TARGET  := stage2-fastboot-flash
BUILD   ?= build-flash
EXTRA_DEFS ?= -DHAVE_FLASH=1

CFLAGS  := --target=armv7a-none-eabi -march=armv7-a -mthumb -mfloat-abi=soft \
           -mno-unaligned-access -ffreestanding -fno-builtin \
           -fno-stack-protector -fno-pic -fno-common \
           -fno-asynchronous-unwind-tables -fno-unwind-tables \
           -ffunction-sections -fdata-sections \
           -Os -g -std=gnu11 -Wall -Wextra -Werror -Wno-unused-parameter -Iinclude \
           -DHAVE_FETCH \
           $(EXTRA_DEFS)

LDFLAGS := -T link.ld -nostdlib --gc-sections -Map=$(BUILD)/$(TARGET).map \
           --build-id=none

SRCS_C := $(wildcard src/*.c)
SRCS_S := $(wildcard src/*.S)
OBJS   := $(patsubst src/%.S,$(BUILD)/%.o,$(SRCS_S)) \
          $(patsubst src/%.c,$(BUILD)/%.o,$(SRCS_C))

all: check-abi $(BUILD)/$(TARGET).bin

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@
	@echo "=== $@: $$(wc -c < $@) bytes ==="

$(BUILD)/$(TARGET).elf: $(OBJS) link.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJS)

$(BUILD)/%.o: src/%.c $(wildcard include/*.h) | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD)/%.o: src/%.S | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD):
	mkdir -p $(BUILD)

size: $(BUILD)/$(TARGET).elf
	$(SIZE) -A $<

clean:
	rm -rf $(BUILD)

PYTHON ?= python3
.PHONY: check-abi test
check-abi:
	$(PYTHON) -B ../tools/check_abi.py --build
test:
	sh tests/run.sh

.PHONY: check-image
check-image: all
	$(PYTHON) -B ../tools/check_abi.py --build --image
