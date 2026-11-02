#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "host_io.h"
#include "../src/partitions.c"
static u8 disk[512];
static int read_error;
int mmc_read_blocks(u32 block,void *out,u32 count) {
    assert(block==0 && count==1);
    if(read_error) return MMC_ERR_DATA_TIMEOUT;
    memcpy(out,disk,512); return 0;
}
u32 mmc_boot_partition_sectors(void) { return 0x2000; }   /* 4 MiB boot0 */
static void put(u32 off,u32 value) {
    for(u32 i=0;i<4;i++) disk[off+i]=(u8)(value>>(8*i));
}
static void valid(void) {
    /* Mock the u32 FIFO representation produced by mmc_read_blocks(),
     * rather than the card's raw byte stream. */
    memset(disk,0,512); put(0,0x36343238); put(4,0x30302e31); put(8,2);
    put(0x20,0x10000); put(0x24,0x7f0000);
    put(0x30,0x800000); put(0x34,0x1400000);
    part_reset(); read_error=0;
}
int main(void) {
    valid(); assert(!part_load() && part_count()==2);
    assert(part_find("nflasha1")->start_bytes==0x10000);
    assert(!part_find("nflasha3"));
    /* Virtual areas: boot0/boot1 from EXT_CSD, bare nflasha = whole user area. */
    assert(part_find("nflashaB0")->dev==1);
    assert(part_find("nflashaB1")->dev==2);
    assert(part_find("nflashaB0")->size_bytes==0x2000*512);
    assert(part_find("nflasha")->dev==0);
    assert(part_find("nflasha")->start_bytes==0);
    assert(part_find("nflasha")->size_bytes==0x800000+0x1400000);
    assert(!part_find("nflash"));
    part_reset(); assert(!part_find("nflasha1") && !part_count());
    valid(); disk[0]='X'; assert(part_load()==MMC_ERR_TABLE && !part_count());
    valid(); put(8,31); assert(part_load()==MMC_ERR_TABLE);
    valid(); put(8,0); assert(part_load()==MMC_ERR_TABLE);
    valid(); put(0x20,1); assert(part_load()==MMC_ERR_TABLE);
    valid(); put(0x20,0xfffffe00); put(0x24,1024); assert(part_load()==MMC_ERR_TABLE);
    valid(); put(0x30,0x10000); assert(part_load()==MMC_ERR_TABLE);
    valid(); read_error=1; assert(part_load()==MMC_ERR_DATA_TIMEOUT && !part_count());
    puts("PASS: partition table, reset, malformed header/count/alignment/overflow/overlap, read failure");
}
