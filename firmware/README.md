# Parts Tally firmware

Pinned PlatformIO/C++17 project for Seeed XIAO ESP32-C3 (`seeed_xiao_esp32c3`, Arduino) and native tests. Install exactly `platformio==6.1.18`, then run `pio test -d firmware -e native` and `pio run -d firmware -e seeed_xiao_esp32c3`. Platforms and the ArduinoJson 7.4.2/WebSockets 2.7.1 dependencies are pinned in `platformio.ini`.

Hardware is behind narrow ADC, button, active-low RGB, clock, atomic storage and transport interfaces. Pins mirror `hardware/interfaces.md`: SDA 6, SCL 7, button 3, RGB 4/5/10 and UART TX/RX 21/20. The standard-C++ domain implements health-first faults, sustained-step acceptance, P95-P5/slope/outlier diagnostics, the >=2 s/>=20 sample gate, safe tare/calibration, deterministic rounding, conservative uncertainty and explicit null-count states. Persistence is versioned/checksummed, bounds history to 256 by default and never exports secret members.

## Target integration status

The target build contains the NAU7802 register/DRDY/fault adapter, verified two-slot Preferences records, full-NVS factory erasure, entropy-backed setup session, setup AP, HTTP route dispatch, and sequenced WebSocket server. These paths compile but have not run on a physical XIAO/NAU7802 assembly, so register waveforms, calibration completion, AP association, NVS interruption behavior, route latency, RF coexistence, and RGB/button timings remain bench checks. `/api/v1` policy and route behavior are independently exercised by native tests.

The direct AP starts on every boot. Hold dedicated GPIO3 during power-up to create the five-minute setup session, fetch `/api/v1/setup/session`, then call `/api/v1/setup/provision`. Provisioning supports empty SSID/password direct-only mode or starts asynchronous STA while retaining the AP. Later sessions are obtained from unauthenticated `POST /api/v1/session` using the persisted device secret and exact Origin/JSON checks. WebSocket clients connect to the exact `ws://192.168.4.1:81/api/v1/events` path and send `{"type":"authenticate","token":"SESSION"}` as their initial message; authorization and expiry are tracked per client, and setup sessions cannot stream events.

## Physical reset and USB recovery

The target implements this factory-reset gesture on dedicated GPIO3: power up while holding for 10 seconds, blink red/blue for the final three seconds, cancel if released early, erase the complete NVS partition (settings, profiles, thresholds, history, and Wi-Fi/device secrets), and restart only after successful erasure. A short release requests local tare; an arbitrary later long press cannot factory-reset. No network route resets the device. Host tests cover the state machine, but physical timing and erasure still require target/bench verification. Credentials persist in NVS and are excluded from normal logs/status/export/JSON backup/CSV, but NVS is not a secure element or a defense against physical flash extraction.

OTA is omitted. For USB recovery, power only from USB 5 V SELV, connect GPIO9/BOOT to GND, briefly press RESET, release BOOT, identify the serial port, then run `pio run -d firmware -e seeed_xiao_esp32c3 -t upload --upload-port PORT`. Press RESET without BOOT and inspect serial at 115200. If enumeration fails, use a known data cable, disconnect carrier peripherals, and repeat. Flashing is not guaranteed to erase NVS. BOOT is not the user button. Never connect mains.

This workshop aid is not legal-for-trade, certified, or suitable for safety-critical inventory decisions.
