#ifndef ZVE10_SDHCI_H
#define ZVE10_SDHCI_H

#include "io.h"

/*
 * ZV-E10 eMMC0: Arasan SD Host Controller at 0xF0304000, 4 KB window
 * (arch/arm/mach-cxd900x0/udif/platform.c:258 EMMC0_IO_BASE).
 * Register layout is standard SDHCI, same as the CXD90057 payload's header.
 */

#define SDHCI_BASE              0xF0304000u

#define SDHCI_DMA_ADDRESS       (SDHCI_BASE + 0x00)
#define SDHCI_BLOCK_SIZE        (SDHCI_BASE + 0x04)   /* 16-bit */
#define SDHCI_BLOCK_COUNT       (SDHCI_BASE + 0x06)   /* 16-bit */
#define SDHCI_ARGUMENT          (SDHCI_BASE + 0x08)
#define SDHCI_TRANSFER_MODE     (SDHCI_BASE + 0x0C)   /* 16-bit */
#define SDHCI_COMMAND           (SDHCI_BASE + 0x0E)   /* 16-bit */
#define SDHCI_RESPONSE          (SDHCI_BASE + 0x10)
#define SDHCI_BUFFER            (SDHCI_BASE + 0x20)
#define SDHCI_PRESENT_STATE     (SDHCI_BASE + 0x24)
#define SDHCI_HOST_CONTROL      (SDHCI_BASE + 0x28)   /* 8-bit  */
#define SDHCI_CLOCK_CONTROL     (SDHCI_BASE + 0x2C)   /* 16-bit */
#define SDHCI_SOFTWARE_RESET    (SDHCI_BASE + 0x2F)   /* 8-bit  */
#define SDHCI_INT_STATUS        (SDHCI_BASE + 0x30)   /* 16-bit */
#define SDHCI_ERR_INT_STATUS    (SDHCI_BASE + 0x32)   /* 16-bit */
#define SDHCI_INT_ENABLE        (SDHCI_BASE + 0x34)   /* 16-bit */
#define SDHCI_ERR_INT_ENABLE    (SDHCI_BASE + 0x36)   /* 16-bit */
#define SDHCI_CAPABILITIES      (SDHCI_BASE + 0x40)
#define SDHCI_HOST_VERSION      (SDHCI_BASE + 0xFE)   /* 16-bit */

#define SDHCI_CLK_INT_EN        BIT(0)
#define SDHCI_CLK_INT_STABLE    BIT(1)
#define SDHCI_CLK_SD_EN         BIT(2)
#define SDHCI_CLK_DIV_SHIFT     8
#define SDHCI_CLK_DIV_HI_SHIFT  6

#define SDHCI_RESET_ALL         BIT(0)
#define SDHCI_RESET_CMD         BIT(1)
#define SDHCI_RESET_DATA        BIT(2)

#define SDHCI_CMD_INHIBIT       BIT(0)
#define SDHCI_DATA_INHIBIT      BIT(1)

#define SDHCI_INT_CMD_COMPLETE  BIT(0)
#define SDHCI_INT_XFER_COMPLETE BIT(1)
#define SDHCI_INT_BUF_WRITE_RDY BIT(4)
#define SDHCI_INT_BUF_READ_RDY  BIT(5)
#define SDHCI_INT_ERROR         BIT(15)

#define SDHCI_TRNS_DMA          BIT(0)
#define SDHCI_TRNS_BLK_CNT_EN   BIT(1)
#define SDHCI_TRNS_AUTO_CMD12   BIT(2)
#define SDHCI_TRNS_READ         BIT(4)
#define SDHCI_TRNS_MULTI        BIT(5)

#define SDHCI_CMD_RESP_NONE     0x00
#define SDHCI_CMD_RESP_LONG     0x01
#define SDHCI_CMD_RESP_SHORT    0x02
#define SDHCI_CMD_RESP_BUSY     0x03
#define SDHCI_CMD_CRC_CHECK     BIT(3)
#define SDHCI_CMD_INDEX_CHECK   BIT(4)
#define SDHCI_CMD_DATA_PRESENT  BIT(5)
#define SDHCI_MAKE_CMD(idx, f)  (u16)(((idx) << 8) | (f))

/* MMC commands */
#define MMC_CMD_GO_IDLE_STATE        0
#define MMC_CMD_SEND_OP_COND         1
#define MMC_CMD_ALL_SEND_CID         2
#define MMC_CMD_SET_RELATIVE_ADDR    3
#define MMC_CMD_SWITCH               6
#define MMC_CMD_SELECT_CARD          7
#define MMC_CMD_SEND_EXT_CSD         8
#define MMC_CMD_SEND_CSD             9
#define MMC_CMD_SEND_STATUS          13
#define MMC_CMD_READ_SINGLE_BLOCK    17
#define MMC_CMD_READ_MULTIPLE_BLOCK  18
#define MMC_CMD_WRITE_BLOCK          24
#define MMC_CMD_WRITE_MULTIPLE_BLOCK 25

/* EXT_CSD byte indices */
#define EXT_CSD_PARTITION_CONFIG     179
#define EXT_CSD_BUS_WIDTH            183
#define EXT_CSD_HS_TIMING            185
#define EXT_CSD_BOOT_SIZE_MULT       226

#define MMC_BUS_WIDTH_1              0
#define MMC_BUS_WIDTH_4              1
#define MMC_BUS_WIDTH_8              2

/* R1 status */
#define MMC_R1_READY_FOR_DATA   BIT(8)
#define MMC_R1_STATE(r)         (((r) >> 9) & 0xf)
#define MMC_STATE_TRAN          4

#define MMC_ERR_RESET           (-7)
#define MMC_ERR_CLOCK           (-8)
#define MMC_ERR_CARD_STATUS     (-9)
#define MMC_ERR_ADDRESSING      (-10)
#define MMC_ERR_TABLE           (-11)
#define MMC_R1_ERROR_MASK       0xFDFFA080u

#define MMC_OK                  0
#define MMC_ERR_INHIBIT         (-1)
#define MMC_ERR_CMD_TIMEOUT     (-2)
#define MMC_ERR_CMD_ERROR       (-3)
#define MMC_ERR_XFER            (-4)
#define MMC_ERR_DATA_TIMEOUT    (-5)
#define MMC_ERR_WRITE_TIMEOUT   (-6)

extern u16 mmc_last_error;
extern u32 mmc_ocr, mmc_rca;
extern int mmc_ready;
extern u32 mmc_last_cmd, mmc_last_r1;

int mmc_init(void);
int mmc_read_blocks(u32 start_block, void *buf, u32 nblocks);
int mmc_write_blocks(u32 start_block, const void *buf, u32 nblocks);

/* Reads the 512-byte EXT_CSD; `buf` must be 4-byte aligned. */
int mmc_read_ext_csd(u8 *buf);
/* Size of boot0/boot1 in 512-byte sectors, from EXT_CSD[226]; 0 on failure. */
u32 mmc_boot_partition_sectors(void);
/* access: 0 = user area, 1 = boot0, 2 = boot1. Preserves BOOT_PARTITION_ENABLE
 * and BOOT_ACK in EXT_CSD[179]; a no-op when the area is already selected. */
int mmc_select_partition(u32 access);

#endif /* ZVE10_SDHCI_H */
