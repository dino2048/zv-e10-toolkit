/*
 * Stage 2 is downloaded into the 1 MB staging buffer by the main payload and
 * copied here with `oem load:0xfe300000`; `oem call:0xfe300001` enters it.
 * The result block lives at 0xFE308000, just past this image.
 */

ENTRY(_start)

MEMORY
{
    STAGE2 (rwx) : ORIGIN = 0xFE300000, LENGTH = 0x7000
}

SECTIONS
{
    .text : {
        KEEP(*(.text.start))
        *(.text .text.*)
    } > STAGE2

    .rodata : ALIGN(8) {
        *(.rodata .rodata.*)
    } > STAGE2

    .data : ALIGN(8) {
        *(.data .data.*)
    } > STAGE2

    .bss (NOLOAD) : ALIGN(8) {
        __bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(8);
        __bss_end = .;
    } > STAGE2

    /DISCARD/ : {
        *(.comment)
        *(.note.*)
        *(.eh_frame)
        *(.ARM.attributes)
        *(.ARM.exidx*)
    }
}
