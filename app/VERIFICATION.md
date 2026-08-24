# Companion app verification record

Verified in this worktree on 2026-08-24 with Node `v22.23.1`, npm `10.9.8`, Python `3.11.15`, and Playwright's pinned Chromium 151.0.7922.34 runtime.

## Clean app verification

The following exact command sequence completed with exit status 0:

```bash
cd app
npm ci
npm run generate
git diff --exit-code -- src/generated
npm run lint
npm run typecheck
npm test
npm run test:a11y
npm run build
npm run test:e2e
npm audit --audit-level=high
```

Actual results:

- `npm ci`: installed 555 locked packages successfully.
- generated-contract diff check: clean; generated schema copies match `docs/schemas/api-v1`.
- ESLint: passed with zero warnings (`--max-warnings 0`).
- TypeScript: passed with no emit.
- Vitest: 5 files, 25 tests passed. This includes schema/fixture validation, every protocol no-count state, real-firmware response-envelope compatibility, nested API error handling, session-expiry fail-closed behavior, newest-history pagination, active-profile selection, malformed-cache rejection, expired-preview recovery, component workflows, secret handling, and axe checks.
- focused accessibility run: 1 file, 1 test passed for signed-out and authenticated views.
- Vite production build: passed; generated `dist/manifest.webmanifest`, `dist/sw.js`, and seven precached shell entries (357.11 KiB reported by the PWA plugin).
- Playwright: 10 tests passed—five workflows in mobile Chromium (Pixel 7 emulation) and desktop Chromium. Covered first setup, known-count calibration, disconnect/sequence-gap refresh, overload fault/recovery, audited correction, JSON/CSV export, validated import preview/apply, and incompatible-schema rejection.
- npm audit: zero vulnerabilities at the high-severity gate.

Chromium was installed before the recorded Playwright run with:

```bash
cd app
npx playwright install chromium
```

CI uses `npx playwright install --with-deps chromium` on Ubuntu.

## Repository contracts

The following exact commands completed with exit status 0 from the repository root:

```bash
python3 scripts/validate_contract.py
python3 -m unittest discover -s tests -v
```

Actual results: all 11 architecture-contract checks passed, and all 33 Python contract/capture/protocol-schema tests passed.

## Evidence boundary

These are static, build, unit/component, automated accessibility, and mock-device browser results. No physical Parts Tally device, ESP32-C3 target, Wi-Fi/AP behavior, load cell, ADC, mobile handset, Safari/iOS, Firefox, or installed-PWA lifecycle was exercised. This record does not claim physical device integration, measured accessibility conformance, certified measurement, or legal-for-trade behavior.
