#ifndef ZVE10_PARTITIONS_H
#define ZVE10_PARTITIONS_H

#include "io.h"

/*
 * The eMMC's block 0 holds Sony's SDM2 table, not an MBR:
 *   +0x00  "642800.1" style version string
 *   +0x08  entry count
 *   +0x20  16-byte entries: {start_bytes, size_bytes, type, flag}
 * The layout and supported entries were checked against a hardware read.
 */
#define PART_MAX        30
#define PART_NAME_LEN   12

struct partition {
    char name[PART_NAME_LEN];
    u32 dev;            /* 0 = user area, 1 = boot0, 2 = boot1 */
    u32 start_bytes;
    u32 size_bytes;
    u32 type;
    u32 flag;
};

/* Reads block 0 and fills the table. Returns MMC_OK or a negative error. */
int part_load(void);
void part_reset(void);
u32 part_block0_word(u32 index);

int part_count(void);
const struct partition *part_get(u32 index);
const struct partition *part_find(const char *name);

#endif /* ZVE10_PARTITIONS_H */
