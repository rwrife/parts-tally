# Parts Tally local protocol v1

**Status:** implemented in firmware and native/contract-tested; target networking, NVS, button,
ADC, and WebSocket behavior still require physical verification.

The device exposes a direct AP on every boot and serves local UTF-8 JSON over HTTP under
`/api/v1`; WebSocket events use port 81 at `/api/v1/events`. If stored Wi-Fi credentials exist,
the target also starts an asynchronous STA association without taking down the AP. LAN failure
therefore does not remove the direct API. No Internet service is required. Transport is plaintext,
so a trusted local network is required and an on-path observer can see bearer traffic.

## Sessions and provisioning

Holding the dedicated GPIO3 button at power-up opens a five-minute physical-presence setup
session. `GET /api/v1/setup/session` requires no bearer but returns the setup token only while that
session is active. A setup token is accepted only under `/api/v1/setup/*`; an authenticated token is
accepted only on normal API routes.

`POST /api/v1/setup/provision` requires the setup bearer, exact configured Origin,
`application/json`, and an idempotency key. Its envelope includes `wifiSsid`, `wifiPassword`, and a
new `deviceSecret` of 16–128 characters. An empty SSID with an empty password selects direct-only
mode. Success atomically persists credentials, invalidates setup scope, starts STA when an SSID was
provided, and returns a fresh five-minute authenticated token.

`POST /api/v1/session` requires no prior bearer or idempotency key, but does require exact Origin,
`application/json`, the standard command envelope, and the persisted `deviceSecret`. Success returns
a fresh entropy-generated five-minute authenticated token. Wrong credentials return 401. Target
tokens come from `esp_random`; native tests inject deterministic token generation.

All other routes require an unexpired authenticated bearer. Mutations also require exact Origin,
`application/json`, a body no larger than 8192 bytes, and an `Idempotency-Key` of 1–128 characters.
The last 64 successful/client-error mutation results are replayed; server failures are not cached,
so the same idempotency key can retry after storage recovery. Reuse for different request content
returns 409.

## Routes

- `GET /api/v1/status`
- `GET /api/v1/profiles`
- `GET /api/v1/history?after=SEQUENCE&limit=COUNT` (`after` is an unsigned 64-bit decimal;
  `limit` defaults to 50 and must be 1–100; each parameter may appear at most once and no other
  query parameters are accepted)
- `GET /api/v1/export`
- `POST /api/v1/actions/tare`
- `POST /api/v1/actions/calibrate` (`knownCount` is 10–1,000,000; a fresh device with no scale
  factor also requires finite positive `knownSampleMassGrams` and derives its scale from that mass)
- `POST /api/v1/profiles`
- `PATCH /api/v1/profiles/{id}`
- `DELETE /api/v1/profiles/{id}`
- `POST /api/v1/counts/{eventId}/correction` (requires profile, bounded count, and a nonempty
  reason of at most 200 characters)
- `POST /api/v1/import/preview`
- `POST /api/v1/import/apply` (requires the exact preview token, unchanged import payload, same
  authenticated session, and use within 30 seconds)
- `DELETE /api/v1/history` (requires exact `CLEAR HISTORY` confirmation)

Mutation bodies contain `protocol`, `requestId`, and `deviceId`. Route-body schemas are in
`docs/schemas/api-v1`; checked fixtures cover every route family. Export/import schema v3 preserves
device name, complete profile calibration fields, per-profile thresholds, and up to 256 history
entries. Every history entry has a unique `eventId`; a correction has its own event ID and stores
the referenced count event in `relatedEventId`. Import validates those references, profile
ownership, and uniqueness. It rejects secret-bearing fields at any depth and keeps the device's
current credentials.

Wi-Fi SSID/password and device secret persist in ESP32 NVS but are absent from status, normal logs,
JSON export/import backup, and CSV data. NVS persistence is not encryption or a secure element: an
attacker with physical access and flash-extraction capability may recover credentials. Session
tokens are short-lived and not persisted.

## Measurements, events, and local button

No-count states are `uncalibrated`, `unstable`, `stale`, `disconnected`, `saturated`,
`overload_indicated`, `below_tare`, `calibration_invalid`, and `uncertainty_excessive`. In each,
`estimatedCount` and `uncertaintyPieces` are `null`.

WebSocket clients connect to the exact `/api/v1/events` path without credentials in the URL, then
must immediately send `{"type":"authenticate","token":"..."}`. Authorization is tracked per
client; setup tokens never authorize streaming, and expired or superseded authenticated sessions
receive no broadcasts.

The target broadcasts sequenced `measurement.updated` events at no more than 4 Hz and emits
`fault.raised` or `status.updated` on state transitions. Other defined event types are
`measurement.stability_changed`, `profile.changed`, `threshold.changed`, `fault.cleared`, and
`device.restarting`. A sequence gap makes clients refresh status, profiles, and their history cursor.
Stable count changes create bounded, persisted count-history events; corrections require both an
existing profile and the event ID of a count event owned by that same profile.

A short release of GPIO3 requests a local tare. Factory reset is recognized only when GPIO3 was
already held at power-up and remains held for ten seconds; releasing cancels it. Later long presses
do not erase storage. Reset erases NVS and restarts. These behaviors are host-tested state-machine
logic, not a claim of measured physical timing.

The device is USB 5 V SELV-only, not legal-for-trade, and not suitable for safety-critical use.
