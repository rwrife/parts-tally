# Parts Tally local protocol (draft v0)

This is an initial contract for issue-driven refinement. It does not describe an implemented endpoint.

## Boundary and transport

- Local-only HTTP JSON commands under `/api/v1`
- WebSocket event stream at `/api/v1/events`
- UTF-8 JSON; timestamps are RFC 3339 UTC where wall-clock time exists, otherwise monotonic sample age is reported
- Device-hosted PWA assets may share the same origin
- No Internet service is required

## Discovery and setup

The unprovisioned device may expose a temporary setup AP with a unique, non-secret SSID suffix. Setup must show a user-verifiable device identifier. Mutating setup actions use a short-lived physical-presence session opened by holding the device button. BLE provisioning remains an evaluated option, not part of v0.

## Security assumptions

- The LAN is not automatically trusted.
- After provisioning, mutating requests require a per-device secret established during a physical-presence setup session.
- Secrets never appear in normal logs, URLs, history exports, or JSON backups.
- Read-only status exposure defaults to authenticated; a user may explicitly enable limited unauthenticated status on a trusted LAN.
- State-changing requests validate origin/content type and use replay-resistant session tokens.
- Factory reset and credential rotation require a deliberate physical action.
- TLS on a self-hosted constrained device is an open design decision; documentation must state the actual protection and residual LAN risk rather than claiming end-to-end security prematurely.

## Common envelope

```json
{
  "protocol": "parts-tally/v1",
  "requestId": "client-generated-id",
  "deviceId": "non-secret-stable-id"
}
```

Errors:

```json
{
  "protocol": "parts-tally/v1",
  "requestId": "...",
  "error": {
    "code": "measurement_unstable",
    "message": "Wait for the platform to settle",
    "retryable": true
  }
}
```

## Read endpoints

### `GET /api/v1/status`

Returns version, connectivity, sensor/fault state, current profile, and measurement:

```json
{
  "protocol": "parts-tally/v1",
  "deviceId": "pt-...",
  "firmwareVersion": "0.1.0",
  "measurement": {
    "raw": 123456,
    "netGrams": 84.2,
    "stable": true,
    "noiseGrams": 0.03,
    "estimatedCount": 42,
    "uncertaintyPieces": 1,
    "sampleAgeMs": 80
  },
  "faults": []
}
```

### `GET /api/v1/profiles`

Returns versioned profile summaries. Calibration records include unit mass, sample count, tare, creation time, and revision.

### `GET /api/v1/history?cursor=...&limit=...`

Returns bounded, paginated count/calibration/correction events.

## Mutating commands

All require authentication and an idempotency/request identifier.

- `POST /api/v1/actions/tare`
- `POST /api/v1/actions/calibrate` with profile ID and known sample count
- `POST /api/v1/profiles`
- `PATCH /api/v1/profiles/{id}`
- `DELETE /api/v1/profiles/{id}`
- `POST /api/v1/counts/{eventId}/correction`
- `POST /api/v1/import/preview` then `POST /api/v1/import/apply`
- `DELETE /api/v1/history`

Tare/calibrate commands fail rather than commit when the reading is unstable, saturated, disconnected, or outside the validated range.

## Event stream

Events use `{type, sequence, deviceUptimeMs, payload}`. Initial types:

- `measurement.updated`
- `measurement.stability_changed`
- `profile.changed`
- `threshold.changed`
- `fault.raised`
- `fault.cleared`
- `device.restarting`

Clients detect sequence gaps and refresh status rather than assuming no data was missed.

## Export formats

- Backup: versioned JSON with profiles, calibrations, thresholds, and optional history
- History: CSV with explicit units and correction markers
- Credentials, session tokens, and Wi-Fi settings are never exported

## Compatibility

- Additive fields may appear within a major protocol version and must be ignored safely by clients.
- Breaking changes require a new major path/version.
- Firmware and PWA test suites share checked-in example messages and schema validation.
