# Project-local KiCad library

## XIAO ESP32-C3

`XIAO ESP32C3` and `XIAO_ESP32C3.kicad_mod` were adapted from the public `VectorSpaceHQ/XIAO_ESP32C3` KiCad library. The symbol uses the project-local footprint library identifier, and unavailable upstream 3D-model paths were removed. Upstream source:

- https://github.com/VectorSpaceHQ/XIAO_ESP32C3

Pin names/numbers were cross-checked against Seeed SKU 113991054 hardware documentation and the Seeed schematic listed in `../../datasheets/manifest.json`. The upstream GPL-3.0 license is preserved in `XIAO_ESP32C3_LICENSE`. Physical board dimensions and pad geometry must be checked again against the actual module during PCB layout before fabrication.

## NAU7802SGI

The `NAU7802SGI` symbol was authored for this project from Nuvoton datasheet Rev. 2.6 pin descriptions (p.6) and uses the standard KiCad `Package_SO:SOIC-16_3.9x9.9mm_P1.27mm` footprint. Its full pin map is duplicated in the structured extraction at `../../datasheets/extracted/NAU7802SGI.json` and checked by `../validate_hardware.py`.

## ASMT-YTC7-0AA02 RGB LED

KiCad 9's `LED:ASMT-YTC2-0AA02` symbol is reused as an electrical-symbol template for D3 because Broadcom AV02-3819EN gives the YTC7 the identical lead map: 1 KB, 2 KG, 3 KR, 4 AR, 5 AG, and 6 AB. The instance MPN and datasheet properties identify the populated YTC7 part. KiCad's `LED_Avago_PLCC6_3x2.8mm` footprint is explicitly tagged for the YTC7 family and matches the manufacturer's 3.0 mm × 2.8 mm package drawing. `../validate_hardware.py` locks the pin names, nets, MPN, and footprint pad set.
