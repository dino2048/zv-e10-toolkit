#include "partitions.h"
#include "optlog.h"
#include "sdhci.h"
#include "io.h"

static struct partition parts[PART_MAX];
/* mmc_read_blocks() stores through a u32*; an odd address here faults on
 * strict-alignment Cortex-A9 (the ROM leaves SCTLR.A set). */
static u8 table_block[512] __attribute__((aligned(4)));
static int loaded;
static int count;

/* The SDHCI FIFO assembles each four-byte group big-endian, so a 32-bit word
 * read from the buffer already carries the table's numeric value: start and
 * size match the documented partitions exactly. Strings are the big-endian
 * bytes of the word, e.g. 0x36343238 spells "6428". */
static u32 w32(const u8 *p)
{
    return *(const u32 *)p;
}

static void make_name(char *dst, u32 index)
{
    /* "nflasha" + decimal slot, 1-based. */
    static const char prefix[] = "nflasha";
    u32 i;
    u32 v = index + 1;
    char digits[4];
    u32 n = 0;

    for (i = 0; i < sizeof(prefix) - 1; i++)
        dst[i] = prefix[i];

    do {
        digits[n++] = (char)('0' + (v % 10));
        v /= 10;
    } while (v && n < sizeof(digits));

    while (n)
        dst[i++] = digits[--n];
    dst[i] = 0;
}

void part_reset(void)
{
    loaded = count = 0;
    for (u32 i=0; i<sizeof(table_block); i++) table_block[i] = 0;
}
u32 part_block0_word(u32 index)
{
    return index < 8 ? w32(table_block + index * 4) : 0;
}

int part_load(void)
{
    u32 i;
    int ret;

    if (loaded)
        return MMC_OK;

    opt_str("PA");
    ret = mmc_read_blocks(0, table_block, 1);
    opt_dec("PB",(u32)ret);
    if (ret)
        return ret;

    /* "642800.1" as two big-endian words. */
    opt_val("M0", w32(table_block));
    if (w32(table_block) != 0x36343238u || w32(table_block + 4) != 0x30302E31u)
        return MMC_ERR_TABLE;
    u32 entries = w32(table_block + 8);
    if (!entries || entries > PART_MAX) return MMC_ERR_TABLE;
    count = 0;

    for (i = 0; i < entries; i++) {
        const u8 *e = table_block + 0x20 + i * 16;

        make_name(parts[i].name, i);
        parts[i].dev         = 0;
        parts[i].start_bytes = w32(e + 0);
        parts[i].size_bytes  = w32(e + 4);
        parts[i].type        = w32(e + 8);
        parts[i].flag        = w32(e + 12);
        if ((parts[i].start_bytes | parts[i].size_bytes) & 511u) return MMC_ERR_TABLE;
        if (parts[i].size_bytes && parts[i].start_bytes + parts[i].size_bytes < parts[i].start_bytes)
            return MMC_ERR_TABLE;
        if (i && parts[i-1].start_bytes + parts[i-1].size_bytes > parts[i].start_bytes)
            return MMC_ERR_TABLE;
    }

    count = entries;
    loaded = 1;
    return MMC_OK;
}

int part_count(void)
{
    return count;
}

const struct partition *part_get(u32 index)
{
    if (!loaded || index >= (u32)count)
        return 0;
    return &parts[index];
}

static int str_eq(const char *a, const char *b)
{
    while (*a && *a == *b) {
        a++;
        b++;
    }
    return *a == *b;
}

static struct partition virt;

/* Areas the SDM2 table does not describe. Stage 2 only: the single-stage
 * image has no room under the injection limit. */
static const struct partition *part_find_virtual(const char *name)
{
    u32 i, extent = 0;

    if (str_eq(name, "nflashaB0") || str_eq(name, "nflashaB1")) {
        u32 sectors = mmc_boot_partition_sectors();

        if (!sectors)
            return 0;
        virt.dev         = str_eq(name, "nflashaB0") ? 1u : 2u;
        virt.start_bytes = 0;
        virt.size_bytes  = sectors * 512u;
        virt.type        = 1;
        virt.flag        = 0xffffffffu;
        return &virt;
    }

    if (str_eq(name, "nflasha")) {
        for (i = 0; i < (u32)count; i++) {
            u32 end = parts[i].start_bytes + parts[i].size_bytes;

            if (parts[i].size_bytes && end > extent)
                extent = end;
        }
        if (!extent)
            return 0;
        virt.dev         = 0;
        virt.start_bytes = 0;
        virt.size_bytes  = extent;
        virt.type        = 1;
        virt.flag        = 0xffffffffu;
        return &virt;
    }

    return 0;
}

const struct partition *part_find(const char *name)
{
    u32 i;

    if (!loaded)
        return 0;

    {
        const struct partition *v = part_find_virtual(name);

        if (v)
            return v;
    }

    for (i = 0; i < (u32)count; i++) {
        if (str_eq(parts[i].name, name))
            return &parts[i];
    }
    return 0;
}
