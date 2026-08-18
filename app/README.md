# Companion app

## Purpose

A responsive local-first PWA provides setup, calibration, profile management, live count/status, thresholds, history, and portable export without requiring an app store, cloud backend, or user account.

## Target platforms

- Current iOS Safari/PWA-capable browsers
- Current Android Chrome/PWA-capable browsers
- Desktop Chromium/Firefox/Safari as a secondary target

The device-hosted or locally served web app communicates only with the selected Parts Tally device on the local network.

## Primary flows

1. Discover/connect by local address or setup flow
2. Create/edit a part profile and low-stock threshold
3. Guided empty-bin tare and known-sample calibration
4. Live count with explicit stable/unstable, fault, and uncertainty states
5. Manual correction with reason/history entry
6. JSON backup/restore and CSV history export
7. Clear history, reset device, and inspect firmware/hardware version

## Data ownership

- No mandatory remote service, analytics, ads, or account
- Device profiles/calibration are identified as authoritative device data
- Browser storage contains only selected-device metadata, UI settings, and an explicitly documented cache
- JSON/CSV exports are user-triggered and exclude Wi-Fi credentials and device secrets
- Import validates schema/version and previews changes before applying

## Permissions

- Local network access is required to communicate with the device
- BLE permission is requested only if BLE provisioning is selected and initiated
- File access is requested only through user-driven import/export pickers
- Notifications are out of MVP; any future low-stock notification is opt-in
- No location, contacts, camera, microphone, or background tracking permission

## Accessibility expectations

- WCAG 2.2 AA intent for contrast, labels, focus order, target size, and status communication
- Stable/unstable and stock state conveyed by text/icon as well as color
- Complete keyboard operation and screen-reader names
- Large touch targets suitable for workshop use
- Reduced-motion preference and no time-critical interaction
- Calibration instructions use plain language and expose raw/stable values for troubleshooting

## Protocol boundary

The app consumes the versioned contract in `../docs/protocol.md`. UI tests use a mock transport; no component should call `fetch` or WebSocket directly outside the transport adapter.

## Proposed tooling

TypeScript, Vite, a minimal PWA/service-worker plugin, Vitest, Testing Library, Playwright for mock-device end-to-end flows, and automated accessibility checks.

## Current status

No app skeleton or passing build exists yet.
