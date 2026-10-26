/*
 * ZV-E10 serial-boot staging layout.
 *
 * The boot ROM's serial-boot protocol writes the payload to 0xFE020000 and
 * jumps to it (see ../pico/PROTOCOL.md). eSRAM is
 * 0xFE000000-0xFEFFFFFF; the ROM keeps state at 0xFE005xxx and 0xFE030008, so
 * the code window is kept inside 0xFE020000-0xFE02FFFF and the DMA arena is
 * put far above it at 0xFE100000, where the DWC3's AXI master always has a
 * valid target.
 */

ENTRY(_start)

MEMORY
{
    ESRAM  (rwx) : ORIGIN = 0xFE020000, LENGTH = 64K
    USBDMA (rw)  : ORIGIN = 0xFE100000, LENGTH = 2M
}

STACK_SIZE = 8K;

SECTIONS
{
    .text : {
        KEEP(*(.text.start))     /* _start must land at 0xFE020000 */
        *(.text .text.*)
    } > ESRAM

    .rodata : ALIGN(8) {
        *(.rodata .rodata.*)
    } > ESRAM

    .data : ALIGN(8) {
        *(.data .data.*)
    } > ESRAM

    .bss (NOLOAD) : ALIGN(16) {
        __bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(16);
        __bss_end = .;
    } > ESRAM

    .stack (NOLOAD) : ALIGN(16) {
        . += STACK_SIZE;
        __stack_top = .;
    } > ESRAM

    .usbdma (NOLOAD) : ALIGN(64) {
        __usbdma_start = .;
        *(.usbdma .usbdma.*)
        . = ALIGN(64);
        __usbdma_end = .;
    } > USBDMA

    /DISCARD/ : {
        *(.comment)
        *(.note.*)
        *(.eh_frame)
        *(.ARM.attributes)
        *(.ARM.exidx*)
    }
}
