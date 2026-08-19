# Module prototype wiring and carrier boundary

**Interface map version:** 1.0
**Status:** Planned; exact pins, MPNs, colors, and voltage levels are pending issue #2 manufacturer verification

This file defines logical nets and ownership. It intentionally does not invent GPIO numbers or trust generic wire colors. The built configuration must replace every `TBD-VERIFY` with manufacturer-document citations before power is applied.

## Planned module-prototype map

```text
USB 5 V SELV
  -> XIAO/controller supported USB input

XIAO/controller validated logic rail + ground
  -> selected bridge-ADC breakout supply + ground

Load cell E+ / E- (excitation)
  -> selected bridge ADC E+ / E- terminals
Load cell S+ / S- (differential signal)
  -> selected bridge ADC A+ / A- terminals

Bridge ADC DATA/READY
  -> controller GPIO_ADC_DATA (TBD-VERIFY exact pin and logic level)
Bridge ADC CLOCK
  -> controller GPIO_ADC_CLOCK (TBD-VERIFY exact pin and idle behavior)

Momentary button
  -> controller GPIO_BUTTON + validated pull/bounce network
Status indicator
  -> controller GPIO_STATUS + current limiting/level requirements

USB/UART recovery and ground
  -> manufacturer-supported connector/pads; remain accessible in fixture
```

## Wiring record required before assembly

| Logical connection | Source terminal/pin | Destination terminal/pin | Voltage/domain | Verification source | Status |
|---|---|---|---|---|---|
| USB input | Compliant USB-C supply | Controller USB input | 5 V SELV | Controller board manufacturer document | TBD-VERIFY |
| ADC supply | Controller validated rail | ADC breakout/IC supply | TBD-VERIFY | Controller + ADC manufacturer documents | TBD-VERIFY |
| Common ground | Controller GND | ADC GND | 0 V reference | Manufacturer pin tables | TBD-VERIFY |
| Excitation positive | ADC E+ | Load cell E+ | TBD-VERIFY | ADC application circuit + load-cell wiring table | TBD-VERIFY |
| Excitation negative | ADC E- | Load cell E- | TBD-VERIFY | ADC application circuit + load-cell wiring table | TBD-VERIFY |
| Signal positive | Load cell S+ | ADC A+ | Differential analog | Load-cell wiring table; polarity trial documented | TBD-VERIFY |
| Signal negative | Load cell S- | ADC A- | Differential analog | Load-cell wiring table; polarity trial documented | TBD-VERIFY |
| ADC data | ADC DATA/READY | GPIO_ADC_DATA | TBD-VERIFY logic | ADC/controller pin tables | TBD-VERIFY |
| ADC clock | GPIO_ADC_CLOCK | ADC CLOCK | TBD-VERIFY logic | ADC/controller pin tables | TBD-VERIFY |
| Button | Button network | GPIO_BUTTON | Logic | Selected button/controller docs | TBD-VERIFY |
| Status | GPIO_STATUS | LED network | Logic/current | Selected LED/controller docs | TBD-VERIFY |

Wire color alone is never pinout evidence. Before connection, use continuity/resistance checks that are permitted by the selected load-cell manufacturer and document the result.

## Harness and physical controls

- Keep excitation and signal conductors paired/short and away from USB, antenna, and digital edges.
- Add strain relief so cable movement cannot pull ADC/load-cell terminals.
- Label both ends with logical names; record connector orientation and pin 1.
- Preserve manufacturer antenna clearance from load-cell metal, fasteners, wiring loops, and enclosure features.
- Mount electronics outside the force path and away from overload-stop contact.
- Provide test access for USB 5 V, logic rail, GND, bridge excitation, ADC data/clock, and differential inputs where safe.

## Carrier-board boundary

The future carrier accepts:

- one verified USB/controller power boundary;
- one exact controller module/revision or justified replacement;
- one exact bridge ADC and manufacturer reference components;
- one keyed four-position load-cell connector with mating-half documentation;
- one physical button and one status indicator;
- recovery/programming access and named test points;
- mechanical mounting that carries no scale force.

The carrier schematic owns protection, decoupling, level compatibility, filter values, test points, net names, connector mapping, and symbol/footprint properties. The PCB owns return paths, analog spacing, antenna keepout rule areas, connector access, and silkscreen orientation.

## Interface invariants

1. Swapping `S+`/`S-` may change sign but is corrected in the documented wiring, not hidden as an unexplained software quirk.
2. Swapping excitation and signal pairs is prohibited.
3. No GPIO is assigned until its controller revision and boot/recovery constraints are verified.
4. No ADC module is powered until its supply and logic levels are verified against the controller.
5. A disconnected, stale, saturated, or overload-indicated sensor produces no count.
6. Networking is not required for the physical status/recovery path.
7. The exact built wiring revision is recorded with characterization data.

## Evidence boundary

This map is a planned logical configuration only. It is not a schematic, datasheet verification, continuity result, assembly record, or bench test.
