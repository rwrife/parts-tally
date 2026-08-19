# Parts Tally implementation plan

## Scope

Build a reproducible, local-first parts-counting platform in two increments:

1. **Module prototype:** XIAO ESP32-C3 + external bridge-ADC breakout + 5 kg bar load cell, mounted under a mechanically isolated platform. This validates noise, creep, calibration, filtering, and the app workflow before PCB commitment.
2. **Carrier-board revision:** an editable KiCad project that hosts the chosen controller/module, bridge ADC, protected load-cell connector, USB/power interface as appropriate, button, status LED, programming/debug access, and test points.

## Architecture

The versioned baseline is [docs/architecture.md](docs/architecture.md), with measurable requirements in [hardware/requirements.md](hardware/requirements.md), logical prototype/carrier interfaces in [hardware/interfaces.md](hardware/interfaces.md), planned evidence in [docs/verification-plan.md](docs/verification-plan.md), and residual risks in [docs/risk-register.md](docs/risk-register.md). `docs/architecture-contract.json` is checked in CI to prevent drift in safety scope, dependency gates, no-count states, test IDs, and evidence labels.

### Measurement path

`load cell bridge -> 24-bit ADC -> ESP32-C3 sampler -> outlier/filter/stability pipeline -> calibrated mass -> count estimate + uncertainty`

Calibration records include empty-bin tare, sample count, sample net mass, derived unit mass, timestamp, and optional tolerance. Count output must be withheld or marked unstable when drift/noise exceeds configured limits.

### Device services

- Non-blocking measurement task and watchdog-safe state machine
- Persistent configuration and profile storage with schema versioning
- Temporary setup AP for first-run provisioning; local LAN API thereafter
- Versioned JSON command/event protocol over HTTP and WebSocket
- Physical button actions available even when networking is unavailable
- Signed/hash-checked firmware artifacts and documented USB recovery path

### Companion app

- TypeScript PWA built with Vite and a small accessible component layer
- Responsive calibration wizard, live stable/unstable indication, profile list, thresholds, history, and import/export
- IndexedDB or browser storage only for app preferences/cache; authoritative device records are explicitly identified
- No mandatory backend, account, telemetry, or Internet dependency

## Technology choices

- **ESP32-C3 / XIAO ESP32C3:** inexpensive Wi-Fi/BLE-capable RISC-V MCU module with USB development path and a small module-prototype footprint.
- **PlatformIO + Arduino framework initially:** fast module bring-up and host-native tests; hardware-facing code remains behind interfaces so ESP-IDF migration is possible.
- **HX711 breakout candidate:** common load-cell prototype interface. It must be compared against NAU7802 and the chosen IC validated from manufacturer documentation before custom-PCB capture.
- **KiCad:** editable schematic/PCB, native symbol properties as the BOM source of truth, ERC/DRC evidence, and fabrication exports.
- **TypeScript/Vite PWA:** phone and desktop access without app-store distribution or cloud hosting.
- **JSON/CSV:** human-portable local backups with explicit schema versions.

## Planned repository layout

```text
app/                    PWA source and tests
bom/                    preliminary planning BOM, then exported bom.csv
config/                 example non-secret device/app configuration
 docs/                  protocol, bring-up, assembly, verification
firmware/               PlatformIO project and native tests
hardware/
  kicad/                real .kicad_pro/.kicad_sch/.kicad_pcb sources
  mechanical/           printable/measured fixture sources
  README.md
  requirements.md
```

No fake KiCad source files will be committed merely to satisfy a filename checklist.

## Milestones and dependency order

1. **Requirements and risk review**
   - Define load range, count accuracy targets, stability criteria, overload strategy, local networking, and cost gate.
2. **Datasheet-backed selection and module experiment**
   - Validate controller, bridge ADC, load cell, interfaces, voltage levels, mechanics, lifecycle, and availability.
3. **Schematic and BOM**
   - Create real KiCad sources, populate manufacturer/MPN fields, complete power/protection/debug/test-point design, run ERC, and export `bom/bom.csv`.
4. **Firmware and protocol**
   - Implement measurement pipeline, calibration, persistence, provisioning/API, update/recovery, native tests, and target build.
5. **Companion PWA**
   - Build setup/calibration/count/history/export workflows with accessible keyboard/screen-reader/touch behavior and mocked-device tests.
6. **PCB and mechanical integration**
   - Define outline/mounting, preserve RF keepout, route analog bridge signals carefully, provide ground strategy/testability, run DRC, and publish renders marked as renders.
7. **Bring-up and release**
   - Assembly, measured test procedure, troubleshooting, real evidence, Gerbers/drills/CPL as applicable, schematic PDF, validated BOM, release archives, and licenses.

## Testing strategy

### Static analysis

- KiCad ERC and DRC, with every waiver documented
- KiCad schematic/PCB analyzers and cross-domain checks
- BOM coverage validation against schematic properties and manufacturer datasheets
- Firmware formatting/static analysis and TypeScript lint/type checks

### Simulation and software tests

- Host-native tests for filtering, stability detection, calibration, count rounding/uncertainty, persistence migrations, and protocol parsing
- Golden vectors with synthetic drift, vibration, overload, and disconnect cases
- PWA unit/component tests and mock-device end-to-end flows
- Protocol schema compatibility tests

### Bench testing (only after hardware exists)

- Repeatability and hysteresis at multiple loads
- Warm-up drift, creep over time, off-center loading, cable disturbance, and power-cycle recovery
- Known-count trials across several uniform part types
- Wi-Fi loss/recovery and local-only behavior
- Overload-stop and enclosure load-path inspection

Field use is separate from bench validation and will not be claimed until performed.

## Packaging and distribution

- Firmware: versioned binary plus source-build instructions and hashes
- PWA: static bundle served by the device or installable from a local host; no mandatory public service
- Hardware: tagged KiCad sources, schematic PDF, Gerber/drill archive, CPL if assembly is supported, schematic-exported BOM, assembly drawings, and enclosure source
- Release archive: licenses and a manifest tying firmware, app, and board revisions together

## Risks and mitigations

This summary is navigational. The versioned [risk register](docs/risk-register.md) is authoritative for risk IDs, owners, verification stages, and residual status.

| Risk | Mitigation |
|---|---|
| Unit-mass variation makes counts misleading | Report uncertainty, require known-count calibration, allow correction, document unsuitable parts |
| Load-cell creep, vibration, or off-center force | Stability gate, filtering, warm-up guidance, rigid fixture, overload stops, bench characterization |
| Analog noise from Wi-Fi/USB power | Short differential wiring, quiet supply/layout, ground strategy, sampling schedule, compare ADC candidates |
| Platform load reaches PCB | Separate mechanical load path; PCB only senses/connects |
| Lost local credentials or bad update | Physical recovery/provisioning action, USB flashing path, versioned config backups |
| Sourcing changes | Manufacturer/MPN properties, datasheets, lifecycle/availability check before each release |
| Scope expansion into warehouse software | Keep MVP single-device, local profiles/history, no purchasing/ERP/cloud service |

## Explicit non-goals

- Certified measurement or sale-by-weight
- Mixed-part recognition, camera classification, or AI-based counting
- Multi-tenant cloud fleet management
- Battery charging, mains power, or unattended safety control
- Production claims before real prototypes and measured evidence
