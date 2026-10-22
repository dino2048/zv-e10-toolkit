# ZV-E10 (CXD90045, ARMv7-A) fastboot payload.
#
# No ARM GCC is installed here; Apple clang cross-compiles to armv7a-none-eabi
# and the Homebrew binutils package provides the linker and object tools.

CC      := clang
LD      := arm-none-eabi-ld
OBJCOPY := arm-none-eabi-objcopy
OBJDUMP := arm-none-eabi-objdump
SIZE    := arm-none-eabi-size

TARGET  := fastboot
BUILD   := build

CFLAGS  := --target=armv7a-none-eabi -march=armv7-a -mthumb -mfloat-abi=soft \
           -mno-unaligned-access -ffreestanding -fno-builtin \
           -fno-stack-protector -fno-pic -fno-common \
           -fno-asynchronous-unwind-tables -fno-unwind-tables \
           -ffunction-sections -fdata-sections \
           -Os -g -std=gnu11 -Wall -Wextra -Wno-unused-parameter -Iinclude

LDFLAGS := -T link.ld -nostdlib --gc-sections -Map=$(BUILD)/$(TARGET).map \
           --build-id=none

SRCS_C := $(wildcard src/*.c)
SRCS_S := $(wildcard src/*.S)
OBJS   := $(patsubst src/%.S,$(BUILD)/%.o,$(SRCS_S)) \
          $(patsubst src/%.c,$(BUILD)/%.o,$(SRCS_C))

.PHONY: all clean disasm size

all: $(BUILD)/$(TARGET).bin

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@
	@echo "=== $@: $$(wc -c < $@) bytes (direct serial-boot budget: 8192) ==="

$(BUILD)/$(TARGET).elf: $(OBJS) link.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJS)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD)/%.o: src/%.S | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD):
	mkdir -p $(BUILD)

size: $(BUILD)/$(TARGET).elf
	$(SIZE) -A $<

disasm: $(BUILD)/$(TARGET).elf
	$(OBJDUMP) -d $< > $(BUILD)/$(TARGET).disasm.txt
	@echo $(BUILD)/$(TARGET).disasm.txt

clean:
	rm -rf $(BUILD)
