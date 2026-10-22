#ifndef ZVE10_STAGE2_SDHCI_H
#define ZVE10_STAGE2_SDHCI_H

#include "io.h"

/*
 * ZV-E10 eMMC0: Arasan SD Host Controller at 0xF0304000, 4 KB window.
 * arch/arm/mach-cxd900x0/udif/platform.c:258 (EMMC0_IO_BASE) is the
 * authoritative source; the register layout is standard SDHCI and matches the
 * CXD90057 payload's include/sdhci.h.
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

#define MMC_CMD_GO_IDLE_STATE       0
#define MMC_CMD_SEND_OP_COND        1
#define MMC_CMD_ALL_SEND_CID        2
#define MMC_CMD_SET_RELATIVE_ADDR   3
#define MMC_CMD_SELECT_CARD         7
#define MMC_CMD_SEND_CSD            9
#define MMC_CMD_SEND_STATUS         13
#define MMC_CMD_READ_SINGLE_BLOCK   17

/* R1 status bits */
#define MMC_R1_READY_FOR_DATA   BIT(8)
#define MMC_R1_STATE(r)         (((r) >> 9) & 0xf)
#define MMC_STATE_TRAN          4

#define MMC_OK                  0
#define MMC_ERR_INHIBIT         (-1)
#define MMC_ERR_CMD_TIMEOUT     (-2)
#define MMC_ERR_CMD_ERROR       (-3)
#define MMC_ERR_XFER            (-4)
#define MMC_ERR_DATA_TIMEOUT    (-5)

/* 0xFE308000: outside the stage-2 image, readable with `oem peek`. */
#define STAGE2_RESULT           0xFE308000u
#define STAGE2_DATA             0xFE310000u
#define STAGE2_PARAMS           0xFE320000u   /* [0]=block, [1]=count */
#define STAGE2_MAGIC            0x3031455Au     /* "ZE10" little-endian */

struct stage2_result {
    u32 magic;
    u32 step;
    u32 status;
    u32 ocr;
    u32 cid[4];
    u32 csd[4];
    u32 rca;
    u32 r1;
    u32 host_control;
    u32 clock_control;
    u32 caps;
    u32 host_version;
    u32 read_status;
    u32 read_block;
};

int stage2_main(void);

#endif /* ZVE10_STAGE2_SDHCI_H */
