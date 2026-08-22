#!/usr/bin/env python3
"""Generate the Parts Tally carrier schematic from reviewed design data.

The generated .kicad_sch is the editable source of truth. This script exists to
make the schematic reproducible and reviewable; it does not replace editing it
in KiCad.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def find_symbol_dir(explicit: str | None) -> Path:
    candidates = [
        explicit,
        os.environ.get("KICAD_SYMBOL_DIR"),
        os.environ.get("KICAD9_SYMBOL_DIR"),
        "/usr/share/kicad/symbols",
        "/usr/local/share/kicad/symbols",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise SystemExit("KiCad symbol libraries not found; pass --symbol-dir")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol-dir", help="directory containing KiCad .kicad_sym libraries")
    parser.add_argument("--output", default=str(Path(__file__).with_name("parts-tally.kicad_sch")))
    args = parser.parse_args()

    symbol_dir = find_symbol_dir(args.symbol_dir)
    os.environ["KICAD_SYMBOL_DIR"] = str(symbol_dir)

    from kicad_sch_api import create_schematic, get_symbol_cache

    here = Path(__file__).resolve().parent
    cache = get_symbol_cache()
    cache.discover_libraries([str(symbol_dir)])
    if not cache.add_library_path(str(here / "lib" / "parts-tally.kicad_sym")):
        raise SystemExit("Could not load project symbol library")

    sch = create_schematic("Parts Tally carrier schematic")
    sch.set_paper_size("A3")
    sch.set_title_block(
        title="Parts Tally USB/SELV carrier",
        date="2026-08-22",
        rev="A0 schematic",
        company="Open hardware design — rwrife/parts-tally",
        comments={
            1: "USB/SELV only; not legal-for-trade or safety certified",
            2: "NAU7802: 3.0 V AVDD, channel 1, PGA 128, 10 SPS baseline",
            3: "PCB layout, fabrication, assembly, and bench validation are pending",
        },
    )

    components: dict[str, object] = {}
    used_label_points: set[tuple[float, float, str]] = set()
    used_nc_points: set[tuple[float, float]] = set()
    lcsc_observations = {
        "C5180029": ("1427", "1 @ $1.7781"),
        "C3020560": ("926", "1 @ $1.0659"),
        "C189895": ("0", "1 @ $1.1182; out of stock"),
        "C17313": ("47400", "10 @ $0.0668 each"),
        "C15759": ("59660", "5 @ $0.0856 each"),
        "C107696": ("417400", "100 @ $0.0061 each"),
        "C3335156": ("337", "1 @ $0.6472"),
        "C97949": ("22", "1 @ $0.3351"),
        "C5555828": ("79", "1 @ $1.7772; JLCPCB extended part"),
    }

    def add(
        lib_id: str,
        ref: str,
        value: str,
        pos: tuple[float, float],
        footprint: str,
        *,
        manufacturer: str,
        mpn: str,
        supplier: str,
        supplier_pn: str,
        datasheet: str,
        cost: str,
        notes: str,
        rotation: float = 0,
        in_bom: bool = True,
    ):
        component = sch.components.add(
            lib_id,
            ref,
            value,
            position=pos,
            footprint=footprint,
            rotation=rotation,
        )
        stock, cost_basis = lcsc_observations.get(
            supplier_pn,
            ("Not verified — distributor API credentials unavailable", "Public distributor listing/search estimate; not a quote"),
        )
        for key, val in {
            "Manufacturer": manufacturer,
            "MPN": mpn,
            "Supplier": supplier,
            "Supplier PN": supplier_pn,
            "Datasheet": datasheet,
            "Estimated Unit Cost USD": cost,
            "Price Observed UTC": "2026-08-21",
            "Stock Observed": stock,
            "Cost Basis": cost_basis,
            "BOM Comments": notes,
        }.items():
            component.set_property(key, val)
        component.in_bom = in_bom
        components[ref] = component
        return component

    def pin_point(ref: str, pin_number: str):
        """Return a pin's absolute point for an unrotated component.

        kicad-sch-api 0.5.6's get_pin_position() applies the library Y axis in
        the wrong direction for generated symbols. All symbols in this design
        are deliberately unrotated, so use KiCad's explicit X+, Y- transform.
        """
        component = components[ref]
        if component.rotation != 0:
            raise ValueError(f"{ref} is rotated; pin_point only supports rotation 0")
        pin = component.get_pin(pin_number)
        if pin is None:
            raise ValueError(f"{ref} pin {pin_number} not found")
        from kicad_sch_api.core.types import Point
        return Point(component.position.x + pin.position.x, component.position.y - pin.position.y)

    def connect(ref: str, pin: str, net: str) -> None:
        point = pin_point(ref, pin)
        key = (round(point.x, 6), round(point.y, 6), net)
        if key not in used_label_points:
            sch.labels.add(net, (point.x, point.y))
            used_label_points.add(key)

    def no_connect(ref: str, pin: str) -> None:
        point = pin_point(ref, pin)
        key = (round(point.x, 6), round(point.y, 6))
        if key not in used_nc_points:
            sch.no_connects.add((point.x, point.y))
            used_nc_points.add(key)

    # USB-C power input and protection. The USB data pins are intentionally NC;
    # U1's own USB-C remains the supported firmware/recovery interface.
    add(
        "Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C POWER ONLY",
        (35, 48), "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
        manufacturer="Global Connector Technology", mpn="USB4105-GF-A",
        supplier="LCSC", supplier_pn="C3020560",
        datasheet="https://gct.co/files/drawings/usb4105.pdf", cost="1.0659",
        notes="Power-only UFP. CC1/CC2 each use 5.1k Rd. D+/D-/SBU are intentionally NC. Shell to GND.",
    )
    add(
        "Device:R", "R1", "5.1k 1%", (65, 36), "Resistor_SMD:R_0603_1608Metric",
        manufacturer="Yageo", mpn="RC0603FR-075K1L", supplier="DigiKey",
        supplier_pn="311-5.10KHRCT-ND", datasheet="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf",
        cost="0.02", notes="USB-C CC1 Rd; 5.1 kΩ to GND per USB Type-C sink power role.",
    )
    add(
        "Device:R", "R2", "5.1k 1%", (78, 36), "Resistor_SMD:R_0603_1608Metric",
        manufacturer="Yageo", mpn="RC0603FR-075K1L", supplier="DigiKey",
        supplier_pn="311-5.10KHRCT-ND", datasheet="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf",
        cost="0.02", notes="USB-C CC2 Rd; 5.1 kΩ to GND per USB Type-C sink power role.",
    )
    add(
        "Device:D_TVS", "D1", "SMF5.0A", (65, 56), "Diode_SMD:D_SOD-123F",
        manufacturer="Littelfuse", mpn="SMF5.0A", supplier="DigiKey",
        supplier_pn="F8583CT-ND", datasheet="https://www.littelfuse.com/assetdocs/tvs-diodes-smf-datasheet?assetguid=7eb8a5b6-bdd0-4561-8f19-0c3cc6f9b2af",
        cost="0.30", notes="VBUS transient clamp; place at J1 with short return to ground.",
    )
    add(
        "Device:Polyfuse", "F1", "500mA hold", (90, 48), "Fuse:Fuse_1812_4532Metric",
        manufacturer="Bourns", mpn="MF-MSMF050-2", supplier="LCSC",
        supplier_pn="C17313", datasheet="https://www.bourns.com/docs/product-datasheets/mf-msmf.pdf",
        cost="0.0668", notes="500 mA hold / 1 A trip PPTC; preserves <500 mA normal-current design target.",
    )
    add(
        "Device:D_Schottky", "D2", "B140-13-F", (108, 48), "Diode_SMD:D_SMA",
        manufacturer="Diodes Incorporated", mpn="B140-13-F", supplier="LCSC",
        supplier_pn="C15759", datasheet="https://www.diodes.com/assets/Datasheets/ds13002.pdf",
        cost="0.0856", notes="Series reverse-current block prevents carrier USB input from being back-fed by U1 USB.",
    )
    add(
        "Device:C", "C1", "4.7uF 10V X5R", (126, 48), "Capacitor_SMD:C_1206_3216Metric",
        manufacturer="Murata", mpn="GRM31CR61A475KA01L", supplier="DigiKey",
        supplier_pn="490-3902-1-ND", datasheet="https://www.murata.com/en-global/products/capacitor/mlcc/overview/lineup",
        cost="0.20", notes="Protected 5 V bulk capacitor; total carrier input capacitance remains below 10 uF nominal.",
    )
    add(
        "Device:C", "C2", "100nF 50V X7R", (139, 48), "Capacitor_SMD:C_0603_1608Metric",
        manufacturer="Murata", mpn="GRM188R71H104KA93D", supplier="DigiKey",
        supplier_pn="490-1519-1-ND", datasheet="https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM188R71H104KA93-01.pdf",
        cost="0.02", notes="High-frequency bypass on protected 5 V rail.",
    )
    add(
        "Device:C", "C11", "1uF 16V X7R", (52, 62), "Capacitor_SMD:C_0603_1608Metric",
        manufacturer="Murata", mpn="GRM188R71C105KA12D", supplier="DigiKey",
        supplier_pn="490-3897-1-ND", datasheet="https://www.murata.com/en-global/products/capacitor/mlcc/overview/lineup",
        cost="0.08", notes="Local VBUS input bypass; total nominal input capacitance remains below 10 uF.",
    )

    # Controller module. D4/GPIO6 and D5/GPIO7 are the reviewed I2C pins.
    add(
        "parts-tally:XIAO ESP32C3", "U1", "Seeed XIAO ESP32-C3", (175, 55),
        "parts-tally:XIAO_ESP32C3", manufacturer="Seeed Technology Co., Ltd.",
        mpn="113991054", supplier="Seeed Studio", supplier_pn="113991054",
        datasheet="https://files.seeedstudio.com/Bazaar/product_pdf/113991054.pdf",
        cost="4.99", notes="Module USB-C is the supported programming/recovery port; battery pads are DNP/unused.",
    )
    add(
        "Device:C", "C3", "10uF 10V X5R", (200, 33), "Capacitor_SMD:C_1206_3216Metric",
        manufacturer="Murata", mpn="GRM31CR61A106KA01L", supplier="LCSC",
        supplier_pn="C97949", datasheet="https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM31CR61A106KA01-01.pdf",
        cost="0.3351", notes="Local bulk capacitor on the XIAO 3V3 output; regulator is on the module.",
    )
    add(
        "Device:C", "C4", "100nF 50V X7R", (213, 33), "Capacitor_SMD:C_0603_1608Metric",
        manufacturer="Murata", mpn="GRM188R71H104KA93D", supplier="DigiKey",
        supplier_pn="490-1519-1-ND", datasheet="https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM188R71H104KA93-01.pdf",
        cost="0.02", notes="High-frequency bypass on the 3V3 rail.",
    )

    # Bridge ADC and Nuvoton Rev. 2.6 application components.
    add(
        "parts-tally:NAU7802SGI", "U2", "NAU7802SGI", (260, 62),
        "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", manufacturer="Nuvoton Technology Corporation",
        mpn="NAU7802SGI", supplier="LCSC", supplier_pn="C5180029",
        datasheet="https://www.nuvoton.com/export/resource-files/en-us--DS_NAU7802_DataSheet_EN_Rev2.6.pdf",
        cost="1.7781", notes="Configure internal LDO for 3.0 V AVDD, channel 1, PGA128, internal RC, 10 SPS; check CAL_ERR.",
    )
    for ref, value, pos, mpn, fp, cost, note in [
        ("C5", "1uF 16V X7R", (282, 40), "GRM188R71C105KA12D", "Capacitor_SMD:C_0603_1608Metric", "0.08", "DVDD local bypass; Nuvoton Rev. 2.6 p.24."),
        ("C6", "1uF 16V X7R", (295, 40), "GRM188R71C105KA12D", "Capacitor_SMD:C_0603_1608Metric", "0.08", "AVDD/LDO local bypass; low-ESR, Nuvoton Rev. 2.6 pp.6,24."),
        ("C7", "100nF 50V X7R", (308, 40), "GRM188R71H104KA93D", "Capacitor_SMD:C_0603_1608Metric", "0.02", "VBG bypass per Nuvoton Rev. 2.6 p.24."),
        ("C8", "100nF 50V X7R", (302, 70), "GRM188R71H104KA93D", "Capacitor_SMD:C_0603_1608Metric", "0.02", "Differential bridge-input filter after the two 47 Ω series resistors."),
        ("C9", "330pF 50V C0G", (302, 82), "GRM1885C1H331JA01D", "Capacitor_SMD:C_0603_1608Metric", "0.05", "Optional PGA-output Cfilter between VIN2P and VBG; enable PGA_CAP_EN; Nuvoton p.24."),
    ]:
        add("Device:C", ref, value, pos, fp, manufacturer="Murata", mpn=mpn,
            supplier="DigiKey", supplier_pn="TBD—verify before order",
            datasheet="https://www.murata.com/en-global/products/capacitor/mlcc/overview/lineup",
            cost=cost, notes=note)

    for ref, net_in, net_out, pos in [
        ("R3", "LC_S+", "AIN+", (232, 76)),
        ("R4", "LC_S-", "AIN-", (232, 88)),
    ]:
        add(
            "Device:R", ref, "47R 1%", pos, "Resistor_SMD:R_0603_1608Metric",
            manufacturer="Yageo", mpn="RC0603FR-0747RL", supplier="DigiKey",
            supplier_pn="311-47.0HRCT-ND", datasheet="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf",
            cost="0.02", notes="Bridge input series filter resistor per Nuvoton Rev. 2.6 p.24.",
        )
        connect(ref, "1", net_in)
        connect(ref, "2", net_out)

    for ref, net, pos in [("R5", "I2C_SDA", (236, 35)), ("R6", "I2C_SCL", (248, 35))]:
        add(
            "Device:R", ref, "4.7k 1%", pos, "Resistor_SMD:R_0603_1608Metric",
            manufacturer="Yageo", mpn="RC0603FR-074K7L", supplier="DigiKey",
            supplier_pn="311-4.70KHRCT-ND", datasheet="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf",
            cost="0.02", notes="Carrier-owned 3.3 V I2C pull-up; do not parallel strong module pull-ups.",
        )
        connect(ref, "1", "+3V3")
        connect(ref, "2", net)

    add(
        "Connector_Generic:Conn_01x04", "J2", "LOAD CELL E+/E-/S+/S-", (325, 68),
        "Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal",
        manufacturer="JST", mpn="SM04B-GHS-TB(LF)(SN)", supplier="LCSC", supplier_pn="C189895",
        datasheet="https://www.jst-mfg.com/product/pdf/eng/eGH.pdf", cost="1.1182",
        notes="Keyed carrier connector. Pin 1 E+, 2 E-, 3 S+ (green), 4 S- (white). LCSC C189895 was out of stock when checked; verify DigiKey/alternate stock before ordering. Mating housing and contacts are external BOM items.",
    )

    # Dedicated local control and three-channel status indicator.
    add(
        "Switch:SW_Push", "SW1", "TARE/CAL/RECOVERY", (125, 112),
        "Button_Switch_SMD:SW_SPST_PTS810", manufacturer="C&K (Littelfuse)",
        mpn="PTS810SJM250SMTRLFS", supplier="DigiKey", supplier_pn="CKN10502CT-ND",
        datasheet="https://www.ckswitches.com/media/1476/pts810.pdf", cost="0.20",
        notes="Dedicated user button, active low; firmware differentiates short/long hold. Not the XIAO BOOT/RESET control.",
    )
    add(
        "Device:R", "R7", "10k 1%", (105, 105), "Resistor_SMD:R_0603_1608Metric",
        manufacturer="Yageo", mpn="RC0603FR-0710KL", supplier="DigiKey",
        supplier_pn="311-10.0KHRCT-ND", datasheet="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf",
        cost="0.02", notes="External pull-up for dedicated active-low button.",
    )
    add(
        "Device:C", "C10", "100nF 50V X7R", (145, 112), "Capacitor_SMD:C_0603_1608Metric",
        manufacturer="Murata", mpn="GRM188R71H104KA93D", supplier="DigiKey",
        supplier_pn="490-1519-1-ND", datasheet="https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM188R71H104KA93-01.pdf",
        cost="0.02", notes="Button hardware debounce; firmware still applies bounded debounce and long-press timing.",
    )
    add(
        "LED:ASMT-YTC2-0AA02", "D3", "RGB STATUS", (210, 118),
        "LED_SMD:LED_Avago_PLCC6_3x2.8mm", manufacturer="Broadcom Limited",
        mpn="ASMT-YTC7-0AA02", supplier="JLCPCB", supplier_pn="C5555828",
        datasheet="https://docs.broadcom.com/docs/AV02-3819EN", cost="1.7772",
        notes="Current YTC7 replacement for obsolete YTC2. Datasheet lead map: 1 KB, 2 KG, 3 KR, 4 AR, 5 AG, 6 AB. Independently driven active-low cathodes; text/icon fault detail remains in the PWA.",
    )
    for ref, gpio_net, cathode_net, pos in [
        ("R8", "LED_R_GPIO", "LED_R_K", (180, 108)),
        ("R9", "LED_G_GPIO", "LED_G_K", (180, 118)),
        ("R10", "LED_B_GPIO", "LED_B_K", (180, 128)),
    ]:
        add(
            "Device:R", ref, "220R 1%", pos, "Resistor_SMD:R_0603_1608Metric",
            manufacturer="Yageo", mpn="RC0603FR-07220RL", supplier="LCSC",
            supplier_pn="C107696", datasheet="https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf",
            cost="0.0061", notes="RGB channel current limiting; final brightness/current is a bench-verification item.",
        )
        connect(ref, "1", gpio_net)
        connect(ref, "2", cathode_net)

    add(
        "Connector_Generic:Conn_01x04", "J3", "UART DEBUG 3V3", (285, 118),
        "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        manufacturer="Samtec", mpn="TSW-104-07-G-S", supplier="JLCPCB", supplier_pn="C3335156",
        datasheet="https://suddendocs.samtec.com/prints/tsw-1xx-xx-xxx-x-xx-xx-mkt.pdf",
        cost="0.6472", notes="Optional 3.3 V UART header: pin 1 3V3, 2 GND, 3 TX (D6/GPIO21), 4 RX (D7/GPIO20). Do not apply 5 V logic.",
    )

    # Net assignments: direct labels on pins keep connectivity explicit and
    # make the generated schematic compact without hiding design intent.
    for pin in ["A4", "A9", "B4", "B9"]:
        connect("J1", pin, "VBUS")
    for pin in ["A1", "A12", "B1", "B12", "S1"]:
        connect("J1", pin, "GND")
    connect("J1", "A5", "CC1")
    connect("J1", "B5", "CC2")
    for pin in ["A6", "A7", "A8", "B6", "B7", "B8"]:
        no_connect("J1", pin)

    connect("R1", "1", "CC1"); connect("R1", "2", "GND")
    connect("R2", "1", "CC2"); connect("R2", "2", "GND")
    connect("D1", "1", "VBUS"); connect("D1", "2", "GND")
    connect("F1", "1", "VBUS"); connect("F1", "2", "VBUS_FUSED")
    connect("D2", "2", "VBUS_FUSED"); connect("D2", "1", "+5V_XIAO")
    for ref in ["C1", "C2"]:
        connect(ref, "1", "+5V_XIAO"); connect(ref, "2", "GND")
    connect("C11", "1", "VBUS"); connect("C11", "2", "GND")

    connect("U1", "14", "+5V_XIAO")
    connect("U1", "13", "GND")
    connect("U1", "12", "+3V3")
    connect("U1", "2", "BUTTON_N")
    connect("U1", "3", "LED_R_GPIO")
    connect("U1", "4", "LED_G_GPIO")
    connect("U1", "5", "I2C_SDA")
    connect("U1", "6", "I2C_SCL")
    connect("U1", "7", "UART_TX")
    connect("U1", "8", "UART_RX")
    connect("U1", "11", "LED_B_GPIO")
    for pin in ["1", "9", "10", "B+", "B-"]:
        no_connect("U1", pin)
    for ref in ["C3", "C4"]:
        connect(ref, "1", "+3V3"); connect(ref, "2", "GND")

    connect("U2", "1", "AVDD_3V0")
    connect("U2", "2", "AIN-")
    connect("U2", "3", "AIN+")
    no_connect("U2", "4")
    connect("U2", "5", "PGA_CFILTER")
    connect("U2", "6", "VBG")
    connect("U2", "7", "GND")
    connect("U2", "8", "GND")
    connect("U2", "9", "GND")
    no_connect("U2", "10")
    no_connect("U2", "11")
    no_connect("U2", "12")
    connect("U2", "13", "I2C_SCL")
    connect("U2", "14", "I2C_SDA")
    connect("U2", "15", "+3V3")
    connect("U2", "16", "AVDD_3V0")
    connect("C5", "1", "+3V3"); connect("C5", "2", "GND")
    connect("C6", "1", "AVDD_3V0"); connect("C6", "2", "GND")
    connect("C7", "1", "VBG"); connect("C7", "2", "GND")
    connect("C8", "1", "AIN+"); connect("C8", "2", "AIN-")
    connect("C9", "1", "PGA_CFILTER"); connect("C9", "2", "VBG")

    connect("J2", "1", "AVDD_3V0")
    connect("J2", "2", "GND")
    connect("J2", "3", "LC_S+")
    connect("J2", "4", "LC_S-")

    connect("R7", "1", "+3V3"); connect("R7", "2", "BUTTON_N")
    connect("SW1", "1", "BUTTON_N"); connect("SW1", "2", "GND")
    connect("C10", "1", "BUTTON_N"); connect("C10", "2", "GND")
    for pin in ["4", "5", "6"]:
        connect("D3", pin, "+3V3")
    connect("D3", "3", "LED_R_K")
    connect("D3", "2", "LED_G_K")
    connect("D3", "1", "LED_B_K")
    connect("J3", "1", "+3V3")
    connect("J3", "2", "GND")
    connect("J3", "3", "UART_TX")
    connect("J3", "4", "UART_RX")

    # PWR_FLAG represents the external USB source for ERC.
    for idx, (net, pos) in enumerate([
        ("VBUS", (78, 60)), ("VBUS_FUSED", (92, 60)),
        ("+5V_XIAO", (108, 60)), ("GND", (210, 55)),
    ], start=1):
        ref = f"#FLG0{idx}"
        add(
            "power:PWR_FLAG", ref, "PWR_FLAG", pos, "",
            manufacturer="N/A", mpn="PCB_NET_FLAG", supplier="N/A", supplier_pn="N/A",
            datasheet="~", cost="0", notes="ERC declaration only; not a physical BOM item.", in_bom=False,
        )
        connect(ref, "1", net)

    # Accessible electrical test points; PCB copper features, not populated BOM parts.
    test_nets = [
        ("TP1", "VBUS"), ("TP2", "+5V_XIAO"), ("TP3", "+3V3"),
        ("TP4", "GND"), ("TP5", "AVDD_3V0"), ("TP6", "I2C_SDA"),
        ("TP7", "I2C_SCL"), ("TP8", "AIN+"), ("TP9", "AIN-"), ("TP10", "VBG"),
    ]
    for index, (ref, net) in enumerate(test_nets):
        add(
            "Connector:TestPoint", ref, net, (70 + (index % 5) * 25, 160 + (index // 5) * 14),
            "TestPoint:TestPoint_Pad_D1.5mm", manufacturer="N/A", mpn="PCB_TEST_PAD",
            supplier="N/A", supplier_pn="N/A", datasheet="~", cost="0",
            notes="Unpopulated labeled PCB test pad; safe probing limits follow the connected rail/signal.", in_bom=False,
        )
        connect(ref, "1", net)

    sch.add_text("USB-C POWER INPUT + PROTECTION", (24, 20), size=1.8, bold=True)
    sch.add_text("CONTROLLER MODULE / ON-MODULE 3V3 REGULATOR", (150, 20), size=1.8, bold=True)
    sch.add_text("24-BIT BRIDGE ADC + LOAD CELL", (235, 20), size=1.8, bold=True)
    sch.add_text("LOCAL BUTTON / RGB STATUS / 3V3 UART", (95, 98), size=1.8, bold=True)
    sch.add_text("Carrier J1 is power-only. Program/recover through U1's own USB-C and onboard BOOT/RESET controls.", (24, 88), size=1.1)
    sch.add_text("J2 pinout: 1 E+ (red), 2 E- (black), 3 S+ (green), 4 S- (white). Verify actual harness continuity.", (235, 95), size=1.1)
    sch.add_text("All evidence here is schematic/static. PCB layout, assembly, bench measurements, and calibration remain pending.", (24, 195), size=1.1, bold=True)

    issues = sch.validate()
    errors = [issue for issue in issues if getattr(issue, "severity", "") == "error"]
    if errors:
        raise SystemExit("Schematic API validation failed: " + "; ".join(str(x) for x in errors))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sch.save_as(output)
    print(f"generated {output} with {len(components)} symbols; validation issues={len(issues)} errors=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
