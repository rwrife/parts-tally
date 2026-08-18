# Firmware

## Responsibilities

- Sample the selected bridge ADC without blocking networking or watchdog service
- Detect disconnect, saturation, overload indication, instability, drift, and stale samples
- Apply configurable filtering, tare, known-count calibration, mass conversion, count estimate, and uncertainty
- Store versioned device settings, profiles, thresholds, and bounded history locally
- Drive the physical button and status LED without app dependency
- Provision local connectivity and expose the versioned protocol in `../docs/protocol.md`
- Report firmware/hardware versions and provide a documented recovery/update route

## Proposed structure

```text
firmware/
  platformio.ini
  include/
  src/
    domain/       calibration, filters, stability, counting
    drivers/      ADC, button, LED, persistence adapters
    protocol/     request validation and event serialization
  test/           native host tests and hardware-target tests
```

Hardware access must sit behind narrow interfaces so core algorithms run in PlatformIO's native environment with deterministic synthetic samples.

## Interfaces

- `IAdcReader`: timestamped raw samples plus fault state
- `IMeasurementPipeline`: filtered mass, stability metrics, and uncertainty
- `ICalibrationStore`: versioned tare/unit-mass profiles
- `IProtocolTransport`: HTTP/WebSocket adapter independent of domain logic
- `IClock` and `IStorage`: injectable for tests

## Provisioning and updates

- Initial setup AP with a short-lived session; BLE provisioning is evaluated, not assumed
- Credentials stored only on-device using platform facilities; never exported in backups or logs
- USB flashing/recovery is mandatory
- OTA is optional after threat modeling; if implemented, images require integrity/authenticity checks and rollback behavior
- Factory reset requires an intentional physical action and preserves no credentials

## Test strategy

- Native tests: moving-window/outlier filters, stability gate, tare, calibration math, count/uncertainty, schema migrations, protocol parsing, and failure states
- Golden synthetic streams: step changes, vibration, drift, creep, disconnect, saturation, and power-cycle recovery
- Target build and smoke tests on ESP32-C3
- Bench measurements only after a real fixture exists, recorded separately from simulation/static test results

## Current status

No firmware project or passing build exists yet. The commands shown in the root README are intended acceptance targets.
