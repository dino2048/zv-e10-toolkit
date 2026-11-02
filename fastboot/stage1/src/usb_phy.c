#include "usb_phy.h"
#include "io.h"
#include "timer.h"

/*
 * Transcribed from Sony's own ZV-E10 USB driver, usb_otg.c, the
 * FUSB_CLKRST_3_CH case (usb_otg.c:304-327) and the identical resume path at
 * usb_otg.c:1398-1420.
 *
 * The CLKRST "SET"/"CLR" registers are write-1-to-act; writing a value that
 * omits a bit leaves it alone, which is why the sequence writes whole bit
 * values rather than read-modify-write.
 */
int usb_phy_init(void)
{
    u32 v;

    /* enable USB3.0 REFCLK */
    setbits32(OTG_REFCLK_CTL, OTG_REF_SSP_EN);

    /* clear LINK Reset (ARESETN) */
    write32(CLKRST_IPRESET2_SET, CLKRST_PRST_USB30);

    /* enable USB30DRD_ACLK */
    write32(CLKRST_IPCLKEN1_SET, CLKRST_USB30DRD_ACLK);

    /* set TXVREFTUNE (400mV), preserving the upper PCNTL1 fields */
    v = read32(USB_ADD_PCNTL1);
    v = (v & 0xfffffff0u) | ADD_TXVREFTUNE0_400MV;
    write32(USB_ADD_PCNTL1, v);

    /* clear PHY reset -- needs the 1 ms the driver waits for */
    write32(CLKRST_IPRESET2_SET, CLKRST_PRST_USB30_PHY);
    v = read32(CLKRST_IPRESET2);
    (void)v;
    dsb();
    mdelay(20);

    /* GUSB3PIPECTL: Sony's value, SUSPHY clear so the PHY stays awake */
    write32(DWC3_GUSB3PIPECTL0, GUSB3PIPECTL_SONY_VAL);

    /* RX_SCOPE_LFPS_EN */
    write32(USB_ADD_ADPADDR, ADD_ADPADDR_RX_SCOPE_LFPS_EN);
    write32(USB_ADD_ADPDATA, ADD_ADPDATA_VALUE);

    dsb();

    /* The driver also parks the PHY in suspend here; a device that is about
     * to be enumerated must not do that. */
    return USB_PHY_OK;
}

int usb_phy_tca_init(void)
{
    /* No TCA driver or TCA references anywhere in the ZV-E10 GPL tree.
     * Reading an absent block at 0xF0210000 would take an external abort. */
    return USB_PHY_OK;
}

int usb_phy_vbus(void)
{
    return (read32(OTG_USB_ID_EXT) & OTG_USB_VBUS) ? 1 : 0;
}
