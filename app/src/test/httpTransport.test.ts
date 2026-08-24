import { afterEach, describe, expect, it, vi } from 'vitest';
import exported from '../../../tests/fixtures/protocol/v1/export-full.json';
import status from '../../../tests/fixtures/protocol/v1/status-stable.json';
import { HttpDeviceTransport } from '../protocol/httpTransport';
import { validateExport } from '../protocol/validation';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

function json(value: unknown) {
  return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

function snapshotResponse(url: string) {
  if (url.endsWith('/status')) return json(status);
  if (url.endsWith('/profiles')) return json({ profiles: exported.profiles });
  if (url.includes('/history?')) return json({ history: [], nextAfter: 0 });
  throw new Error(`Unexpected URL: ${url}`);
}

class FakeWebSocket extends EventTarget {
  static instances: FakeWebSocket[] = [];
  send = vi.fn();
  close = vi.fn(() => this.dispatchEvent(new Event('close')));
  constructor(readonly url: string | URL) { super(); FakeWebSocket.instances.push(this); }
}

describe('HTTP transport wire compatibility', () => {
  it('maps the firmware import-preview envelope into the UI summary', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      protocol: 'parts-tally/v1',
      deviceId: 'pt-test',
      previewToken: 'preview-token-123456',
      wouldReplaceProfiles: 1,
      wouldReplaceHistory: 2
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const transport = new HttpDeviceTransport();
    Object.assign(transport, { baseUrl: 'http://device.local', deviceId: 'pt-test', token: 'session-token' });

    await expect(transport.previewImport(validateExport(exported))).resolves.toEqual({
      previewToken: 'preview-token-123456',
      profilesToReplace: 1,
      historyToReplace: 2,
      expiresInSeconds: 30
    });
  });

  it('surfaces the firmware nested error message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'credentials_invalid', message: 'credentials are invalid', retryable: false }
    }), { status: 401, headers: { 'Content-Type': 'application/json' } })));
    const transport = new HttpDeviceTransport();

    await expect(transport.connect({
      baseUrl: 'http://device.local', deviceId: 'pt-test', deviceSecret: 'wrong-secret-value'
    })).rejects.toThrow('credentials are invalid');
  });

  it('disconnects and closes a subscribed socket when the login session expires', async () => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(url.endsWith('/session')
        ? json({ token: 'session-token-1234', expiresInSeconds: 5 })
        : snapshotResponse(url));
    }));
    const transport = new HttpDeviceTransport();
    await transport.connect({ baseUrl: 'http://device.local', deviceId: 'pt-test', deviceSecret: 'correct-secret-value' });
    const disconnected = vi.fn();

    transport.subscribe(vi.fn(), disconnected);
    await vi.advanceTimersByTimeAsync(4_999);
    expect(disconnected).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);

    expect(disconnected).toHaveBeenCalledOnce();
    expect(FakeWebSocket.instances[0].close).toHaveBeenCalledOnce();
  });

  it('uses the provisioning session lifetime and clears its timer on unsubscribe', async () => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith('/setup/session')) return Promise.resolve(json({ token: 'setup-token-123456', expiresInSeconds: 20 }));
      if (url.endsWith('/setup/provision')) return Promise.resolve(json({ token: 'session-token-1234', expiresInSeconds: 7 }));
      return Promise.resolve(snapshotResponse(url));
    }));
    const transport = new HttpDeviceTransport();
    await transport.provision({ baseUrl: 'http://device.local', deviceId: 'pt-test', deviceSecret: 'correct-secret-value', wifiSsid: '', wifiPassword: '' });
    const disconnected = vi.fn();

    const unsubscribe = transport.subscribe(vi.fn(), disconnected);
    unsubscribe();
    await vi.advanceTimersByTimeAsync(7_000);

    expect(disconnected).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances[0].close).toHaveBeenCalledOnce();
  });

  it('paginates the bounded history and retains the newest 100 entries', async () => {
    const entries = Array.from({ length: 256 }, (_, index) => ({
      sequence: index + 1, deviceUptimeMs: index + 10, profileId: 'bolts', kind: 'count',
      eventId: `count-${index + 1}`, reason: '', count: index + 1
    }));
    const historyUrls: string[] = [];
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith('/status')) return Promise.resolve(json(status));
      if (url.endsWith('/profiles')) return Promise.resolve(json({ profiles: exported.profiles }));
      const parsed = new URL(url);
      const after = Number(parsed.searchParams.get('after') ?? 0);
      historyUrls.push(url);
      const page = entries.filter(entry => entry.sequence > after).slice(0, 100);
      return Promise.resolve(json({ history: page, nextAfter: page.at(-1)?.sequence ?? after }));
    }));
    const transport = new HttpDeviceTransport();
    Object.assign(transport, { baseUrl: 'http://device.local', deviceId: 'pt-test', token: 'session-token' });

    const snapshot = await transport.refresh();

    expect(historyUrls).toHaveLength(3);
    expect(snapshot.history.map(entry => entry.sequence)).toEqual(Array.from({ length: 100 }, (_, index) => index + 157));
  });
});
