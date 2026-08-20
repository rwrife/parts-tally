# Datasheet-backed measurement-chain selection

**Selection revision:** 1.0<br>
**Reviewed:** 2026-08-20T00:24:42Z<br>
**Evidence class:** manufacturer-document review and current web sourcing; no physical assembly or measurements

## Decision

Use this exact module-prototype chain:

| Function | Manufacturer | Exact orderable MPN/SKU | Selected configuration |
|---|---|---|---|
| Controller board | Seeed Technology Co., Ltd. | **113991054** — Seeed Studio XIAO ESP32-C3 | USB-C 5 V input; 3.3 V rail; D4/GPIO6 SDA and D5/GPIO7 SCL |
| Bridge ADC module | SparkFun Electronics | **SEN-15242** — SparkFun Qwiic Scale, NAU7802 | 3.3 V Qwiic bus, channel 1, PGA 128, start at 10 SPS; characterize 80 SPS separately |
| Bridge ADC for later carrier | Nuvoton Technology Corporation | **NAU7802SGI** | SOP-16, 150 mil; reproduce and validate the Rev. 2.6 application circuit in KiCad |
| Load cell | SparkFun Electronics orderable SKU; HT Sensor underlying cell | **SEN-14729**, containing **TAL220B 5 kg** | Four-wire full bridge; 3–10 V excitation; planned 3.0 V nominal excitation from the ADC module |
| Controller-to-ADC cable | SparkFun Electronics | **CAB-17261** — flexible Qwiic female-jumper cable | Female Qwiic end at SEN-15242; individual jumpers to XIAO header pins |

The button, user-status LED, and carrier load-cell connector are intentionally **not selected in this issue**. The module prototype may use host commands for capture, but the later product still requires a dedicated button and text/icon/color-capable status. Reusing BOOT/RESET as the product control is rejected because those pins are part of recovery. The carrier connector is deferred until enclosure/strain-relief geometry exists. This is explicit deferral, not an undocumented BOM gap.

## Why NAU7802 rather than HX711

| Criterion | HX711 | NAU7802 | Decision effect |
|---|---|---|---|
| Supply/interface compatibility | 2.6–5.5 V; DVDD should match MCU supply; custom DOUT/PD_SCK interface | 2.7–5.5 V; standard I2C-style interface; fixed address 0x2A; DVDD follows host logic | Both work at 3.3 V; NAU7802 fits the XIAO I2C pins and allows register diagnostics/calibration |
| Gain/input range | Channel A gain 64/128; at 5 V, ±40/±20 mV; channel B gain 32 | PGA 1–128; full scale ±0.5 × VREF/PGA | Both support a 1 mV/V bridge; final span/headroom still requires real tare/platform data |
| Output rate | 10 or 80 SPS | 10, 20, 40, 80, or 320 SPS | NAU7802 permits controlled latency/noise studies; 10 SPS is the initial low-noise baseline |
| Filtering/noise | Simultaneous 50/60 Hz rejection; 50 nV RMS at 10 SPS and 90 nV at 80 SPS, gain 128 | Simultaneous 50/60 Hz rejection; 50 nV RMS at 10 SPS and 150 nV at 80 SPS, gain 128 | Neither datasheet number predicts assembled performance; run NOISE-01 with Wi-Fi states |
| Calibration/diagnostics | Pin-selected channel/gain; saturation codes documented | Internal/system calibration modes, CAL_ERR, data-ready state, temperature sensor, register configuration | NAU7802 exposes more health and configuration evidence for fail-closed firmware |
| Library support | SparkFun/community libraries exist; simple timing-sensitive DOUT/PD_SCK driver | SparkFun maintains a dedicated register-aware Arduino library and hookup guide for SEN-15242 | NAU7802 exposes more configuration and fault evidence through the selected library path |
| Current sourcing on review date | SparkFun SEN-13879 reported in stock at USD 4.95 and the HX711 IC appeared in stock at LCSC. The old BOM URL incorrectly pointed at retired predecessor SEN-13230 | SEN-15242 reported in stock at USD 5.95; NAU7802SGI appeared in stock at DigiKey/LCSC | Availability does not disqualify HX711; select NAU7802 for interface/diagnostics and correct the malformed old sourcing record |
| Package/carrier suitability | SOP-16 only in the reviewed Avia document | NAU7802SGI SOP-16; Nuvoton also documents PDIP-16 and QFN-16 variants | SOP-16 is hand-assembly friendly and has current manufacturer documentation |

### Source basis

- **NAU7802 Rev. 2.6, p. 4:** 2.7–5.5 V, AVDD regulator, RMS noise, PGA, rejection, I2C, temperature range, package variants.
- **NAU7802 Rev. 2.6, p. 6:** pin table (VIN1±, SDIO, SCLK, DRDY, DVDD, AVDD/LDO).
- **NAU7802 Rev. 2.6, pp. 12–13:** DVDD/AVDD and I2C power/interface behavior.
- **NAU7802 Rev. 2.6, p. 24:** 16-pin bridge application circuit and optional 330 pF filter at 3.3 V AVDD.
- **NAU7802 Rev. 2.6, p. 28:** conversion-rate register values (10/20/40/80/320 SPS) and CAL_ERR.
- **NAU7802 Rev. 2.6, p. 38:** NAU7802SGI ordering code and SOP-16 package.
- **HX711 manufacturer datasheet, pp. 1–5:** supply, noise/rates, pinout, input range, serial timing, saturation, and reference application.

## Electrical and application-circuit checks

### Controller

Seeed's 113991054 product datasheet identifies the exact SKU, 21 mm × 17.8 mm board, 5 V VIN, 3.3 V output capability, 75 mA typical Wi-Fi-active consumption, and −40 to +85 °C operating range (pp. 1, 4–5). The manufacturer pinout workbook maps D4 to GPIO6/SDA and D5 to GPIO7/SCL. The prototype remains USB/SELV-only; the battery input/charger is unused.

### ADC module and logic

Power SEN-15242 from XIAO **3V3**, never 5 V while it is connected to the XIAO I2C pins. SparkFun's Qwiic Scale schematic warns that the module can accept 2.7–5.5 V but a Qwiic bus must not exceed 3.3 V. The board provides 2.2 kΩ I2C pull-ups (hookup guide, “I2C Jumper”). Do not add another strong pull-up bank during the module experiment.

The Nuvoton datasheet requires DVDD to be at least 0.3 V above the selected internal AVDD setting. With 3.3 V module power, configure **3.0 V nominal AVDD** rather than the SparkFun library's commonly shown 3.3 V setting. This also sits at the TAL220B's documented 3 V minimum excitation. Because both constraints meet at the boundary, actual bridge excitation must be measured and any low-voltage behavior recorded before schematic capture. If 3.0 V cannot be maintained, the schematic must use a reviewed external/reference topology rather than silently violating either document.

Initial ADC settings:

- channel 1, PGA 128;
- internal RC oscillator;
- 10 SPS baseline for the documented 50/60 Hz rejection and lowest stated RMS noise;
- perform internal offset calibration after power-up and after sample-rate, gain, supply, or material temperature changes; reject data when `CAL_ERR` is set;
- discard at least the documented post-reset settling conversions before accepting stability;
- compare 80 SPS only as a separate latency/noise condition; do not merge its thresholds with 10 SPS data.

For the carrier schematic, begin from Nuvoton Rev. 2.6 p. 24: 47 Ω series input resistors, 0.1 µF differential input filtering, 0.1 µF VBG bypass, and 1 µF supply capacitors. Validate whether the module's 330 pF channel capacitor and SparkFun-specific jumpers should be reproduced. Values are starting requirements, not a released schematic.

### Load cell

The HT Sensor TAL220B sheet specifies for the family/order option reviewed:

- 5 kg selected capacity; aluminum parallel beam, IP65;
- safe overload 120% FS and ultimate overload 150% FS;
- rated output 1.0 ± 0.1 mV/V; excitation 3–10 VDC;
- combined error/non-linearity/hysteresis/repeatability each ±0.05% FS; creep ±0.1% FS over 3 minutes;
- −10 to +55 °C operating and −10 to +40 °C compensated range;
- nominal 200 mm four-wire cable: red E+, black E−, green S+, white S−.

SparkFun's SEN-14729 product record identifies the purchased 5 kg variant as 55 mm × 12.7 mm × 12.7 mm with two M5 through holes. Mechanical CAD must still trace the hole locations and mounting direction from the manufacturer drawing; the dimensions do not prove fixture fit. The project target of 10–35 °C is covered by the selected cell and electronics, but no thermal performance is inferred.

At 3.0 V excitation and 1.0 mV/V nominal rated output, the nominal full-load bridge span is 3.0 mV. This is comfortably below the NAU7802 gain-128 ratiometric full-scale magnitude of 0.5 × VREF/128 (about 11.7 mV for a 3.0 V reference). This is a datasheet calculation, not a measured headroom result; platform/bin dead load, offset, gain tolerance, wiring, and mechanical preload remain bench inputs.

## Availability, lifecycle, and cost snapshot

Observed 2026-08-20T00:24:42Z; web status is volatile and must be checked again immediately before ordering.

| Item | Source evidence | Unit estimate | Availability/lifecycle confidence |
|---|---|---:|---|
| Seeed 113991054 | Seeed product page metadata | USD 4.99 | “In stock” on manufacturer page; exact SKU established |
| SparkFun SEN-15242 | SparkFun product page metadata | USD 5.95 | “In stock” on manufacturer page; product and open hardware/library active |
| SparkFun SEN-14729 | SparkFun product page metadata | USD 15.50 | “In stock” on manufacturer page; some regional resellers report replacement/EOL, so re-check SparkFun/DigiKey before purchase |
| SparkFun CAB-17261 | SparkFun product/search record | USD 1.95 | Planning estimate; stock quantity not captured, so verify before order |
| NAU7802SGI carrier IC | Nuvoton product page plus DigiKey/LCSC listings | TBD—verify at schematic BOM quantity | Current Nuvoton product page/PLP and distributor listings found; no guarantee for future release |
| SparkFun SEN-13879 / HX711 (comparison only) | SparkFun current product page plus Avia datasheet/LCSC listing | USD 4.95 module; not selected | Module and IC reported in stock. Prior CSV mixed SEN-13879 with retired SEN-13230 URL; corrected here |

Selected electrical/cable planning subtotal: **USD 28.39** before USB supply, mechanical parts, shipping, tax, button, status indicator, carrier connector, and fabrication. The module-only subtotal excluding the optional jumper cable is USD 26.44. This supports but does not prove the USD 35–55 complete module-prototype target; all omitted items remain `TBD—verify`.

## Residual risks passed to schematic/firmware/mechanics

1. **Supply/filter margin:** 3.3 V DVDD and 3.0 V AVDD/excitation place the load cell at its minimum specified excitation. Measure excitation/noise; do not assume SparkFun defaults are optimal.
2. **RF coupling:** acquire separate Wi-Fi-off, idle, and active captures. Keep bridge leads short/paired and physically away from the XIAO antenna/USB cable.
3. **Single I2C address:** NAU7802 uses 0x2A. Record bus ownership and pull-ups in the schematic.
4. **Fault inference:** the ADC does not provide a complete load-cell disconnect guarantee. Firmware must combine saturation/stale/calibration/range behavior and later physical fault fixtures.
5. **Mechanical overload:** 120% safe overload is not permission to operate above 5 kg. A derated working load and stops require fixture geometry/tolerance evidence.
6. **Exact purchased cell:** SEN-14729 is the orderable SparkFun SKU, while the underlying HT Sensor ordering code is not fully printed on the storefront. Photograph/record markings only after a real unit exists and block substitutions from inheriting this validation.
7. **No prototype evidence:** no modules, fixture, instruments, photos, raw physical samples, or continuity checks are available in this repository. All bench rows remain unexecuted.
