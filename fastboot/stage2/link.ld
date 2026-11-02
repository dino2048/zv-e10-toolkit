/* Fixed-address stage 2 at 0xFE300000. Stage 1 ABI is pinned in usb_link.h
 * and verified by tools/check_abi.py against the published bin + ELF. */
ENTRY(_start)

MEMORY
{
    STAGE2 (rwx) : ORIGIN = 0xFE300000, LENGTH = 64K
}

SECTIONS
{
    .text : {
        KEEP(*(.text.start))
        *(.text .text.*)
    } > STAGE2

    .rodata : ALIGN(8) { *(.rodata .rodata.*) } > STAGE2
    .data   : ALIGN(8) { *(.data .data.*) } > STAGE2

    .bss (NOLOAD) : ALIGN(8) {
        __bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(8);
        __bss_end = .;
    } > STAGE2

    /DISCARD/ : {
        *(.comment) *(.note.*) *(.eh_frame) *(.ARM.attributes) *(.ARM.exidx*)
    }
}

ASSERT((__bss_start & 3) == 0 && (__bss_end & 3) == 0, "BSS must be word aligned")
