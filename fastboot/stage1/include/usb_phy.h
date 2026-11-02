#ifndef ZVE10_USB_PHY_H
#define ZVE10_USB_PHY_H

#include "io.h"

/*
 * CXD90045 USB glue. Unlike the CXD90057 there is no CR-port/SS-PHY firmware
 * path: the reference is Sony's own driver, drivers/usb/f_usb/usb_otg.c
 * (ZV-E10 GPL 2.02), registers in drivers/usb/f_usb/usb_otg_reg.h.
 *
 *   CLKRST_3   0xF2900000   arch/arm/mach-cxd900x0/include/mach/platform.h:111
 *   OTG        0xF2920000   platform.h:190 CXD900X0_USB_BASE, 0x3000 window
 *   ADDITIONAL 0xF0220000   platform.c:414 CXD900X0_USB_DRD_BASE + 0x20000
 *   DWC3       0xF0200000   platform.h:191 CXD900X0_USB_DRD_BASE
 */
#define USB_CLKRST3_BASE    0xF2900000u
#define USB_OTG_BASE        0xF2920000u
#define USB_ADDITIONAL_BASE 0xF0220000u

/* CLKRST_3 -- usb_otg_reg.h CLKRST_3 section. */
#define CLKRST_IPCLKEN1        (USB_CLKRST3_BASE + 0x0030)
#define CLKRST_IPCLKEN1_SET    (USB_CLKRST3_BASE + 0x0034)
#define CLKRST_IPCLKEN1_CLR    (USB_CLKRST3_BASE + 0x0038)
#define CLKRST_IPRESET2        (USB_CLKRST3_BASE + 0x00C0)
#define CLKRST_IPRESET2_SET    (USB_CLKRST3_BASE + 0x00C4)
#define CLKRST_IPRESET2_CLR    (USB_CLKRST3_BASE + 0x00C8)

#define CLKRST_USB30DRD_ACLK   BIT(14)
#define CLKRST_PRST_USB30      BIT(9)
#define CLKRST_PRST_USB30_PHY  BIT(10)

/* OTG block. */
#define OTG_USB_ID_EXT         (USB_OTG_BASE + 0x0010)
#define OTG_USB_VBUS           BIT(0)
#define OTG_USB_ID             BIT(1)
#define OTG_REFCLK_CTL         (USB_OTG_BASE + 0x0100)
#define OTG_REF_SSP_EN         BIT(16)
#define OTG_MULTIPLIER         (USB_OTG_BASE + 0x0120)

/* Additional (PHY tuning) block. */
#define USB_ADD_PCNTL1         (USB_ADDITIONAL_BASE + 0x0000)
#define USB_ADD_ADPADDR        (USB_ADDITIONAL_BASE + 0x11080)
#define USB_ADD_ADPDATA        (USB_ADDITIONAL_BASE + 0x11084)
#define ADD_TXVREFTUNE0_400MV  0x3u
#define ADD_ADPADDR_RX_SCOPE_LFPS_EN 0x00001026u
#define ADD_ADPDATA_VALUE      0x00000001u

/* DWC3 global register used by the same sequence. */
#define DWC3_GUSB3PIPECTL0     0xF020C2C0u
#define GUSB3PIPECTL_SONY_VAL  0x11080002u

enum usb_phy_status {
    USB_PHY_OK = 0,
    USB_PHY_ERR_TCA_TIMEOUT = -1,   /* kept for interface compatibility */
};

int usb_phy_init(void);

/* No TCA in the ZV-E10 GPL tree; returns OK without touching 0xF0210000. */
int usb_phy_tca_init(void);

/* 1 while VBUS is present on the OTG block (usb_otg_reg.h USB_ID_EXT bit 0). */
int usb_phy_vbus(void);

#endif /* ZVE10_USB_PHY_H */
