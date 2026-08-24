# Parts Tally companion PWA

This is the installable, responsive local companion for the Parts Tally device. It implements the HTTP/WebSocket contract in [`../docs/protocol.md`](../docs/protocol.md) and validates device status, events, and backup data at runtime against generated copies of [`../docs/schemas/api-v1`](../docs/schemas/api-v1).

## Reproducible development

Node 22.23.1 and npm 10.9.8 are pinned in `package.json`; every dependency is an exact version in `package-lock.json`.

```bash
cd app
npm ci
npm run generate
npm run lint
npm run typecheck
npm test
npm run test:a11y
npm run build
npx playwright install chromium   # first local run only
npm run test:e2e
```

`npm run generate` refreshes the runtime JSON Schema copies and their aggregate SHA-256 marker. UI components depend on `DeviceTransport`; only `src/protocol/httpTransport.ts` constructs `fetch` or `WebSocket`. Playwright uses the same adapter interface with an in-memory mock device. Those tests are software evidence only and do not claim a physical ESP32, load cell, ADC, radio, or browser/device combination was tested.

## Data boundaries and privacy

- Profiles, calibration, thresholds, history, measurements, and faults returned by a connected device are device-authoritative.
- The browser caches only the selected address, device ID, and the newest 100 validated profile/history/status records so an offline user can identify the device and inspect a clearly marked snapshot. Cached measurements are never presented as a live count.
- Device secrets, Wi-Fi passwords, setup tokens, session tokens, and authorization headers are memory-only and are not written to browser storage, JSON, CSV, the service-worker cache, or logs.
- JSON backup schema v3 contains device name, profiles, calibration, thresholds, and up to 256 device history entries. Import rejects incompatible schema versions and secret-bearing fields, displays the device preview, then requires an explicit apply action within the protocol's 30-second window.
- CSV export contains history columns only. Both exports require a user action.
- There are no accounts, analytics, ads, telemetry, cloud API, or background tracking. The app requests no camera, microphone, contacts, location, notification, or BLE permission.

## Offline and installation behavior

The generated service worker precaches the application shell (HTML, JavaScript, CSS, and icon). After one successful HTTPS or localhost load, a supporting browser can reopen and install the shell without Internet access. API responses are deliberately not service-worker cached. A device still must be reachable over its direct AP or trusted LAN for authentication, mutations, and current measurements. Browsers may evict installed-site data; JSON backup remains the portable copy.

The device protocol is plaintext HTTP/WebSocket. Use a trusted local network: an on-path observer can see bearer traffic. HTTPS-hosted public pages may also block plaintext local-device requests as mixed content, so device-hosted or explicitly trusted local serving is the practical deployment model.

## Platform scope and limitations

- Android Chromium: install prompts and standalone display are expected, but local-network permission prompts and background suspension vary by vendor/version.
- iOS/iPadOS Safari: installation is via Share → Add to Home Screen; service-worker storage can be evicted and WebSockets are normally suspended when backgrounded. There is no background counting or notification promise.
- Desktop Chromium supports installation; Firefox can use the web app and offline cache but does not consistently offer desktop PWA installation; Safari behavior varies by current macOS release.
- The automated matrix is mobile and desktop Chromium emulation. It does not prove Safari/iOS, Firefox, Android hardware, local-network routing, captive-portal behavior, or physical device integration.

## Accessibility and measurement safety

The UI is keyboard-operable, uses native landmarks/labels/tables/forms, visible focus, at least 44 px controls, text-and-icon state cues, an aria-live update region, responsive layouts, and reduced-motion handling. Vitest runs axe checks, but automation does not replace manual screen-reader, zoom, contrast, touch, and real-device testing.

Every protocol no-count state withholds the numeric count: uncalibrated, unstable, stale, disconnected, saturated, overload indicated, below tare, calibration invalid, and excessive uncertainty. Parts Tally is USB 5 V SELV-only, not legal-for-trade, not certified, and not suitable for safety-critical stock or measurement decisions. Observe load-cell ratings and mechanical overload protection.
