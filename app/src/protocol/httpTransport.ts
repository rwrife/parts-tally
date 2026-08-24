import { PROTOCOL, type ConnectionInput, type DeviceExport, type DeviceSnapshot, type DeviceTransport, type HistoryEntry, type ImportPreview, type Profile, type ProtocolEvent, type ProvisionInput } from './types';
import { validateEvent, validateExport, validateHistory, validateProfiles, validateStatus } from './validation';

type RequestOptions = { method?: string; body?: Record<string, unknown>; auth?: string; setup?: string };
export class HttpDeviceTransport implements DeviceTransport {
  private baseUrl = ''; private deviceId = ''; private token = ''; private sequence = 0; private socket?: WebSocket;
  private sessionExpiresAt = 0; private expiryTimer?: ReturnType<typeof setTimeout>;
  private envelope() { return { protocol: PROTOCOL, requestId: crypto.randomUUID().replaceAll('-', '_'), deviceId: this.deviceId }; }
  private async request(path: string, options: RequestOptions = {}): Promise<unknown> {
    const headers: Record<string,string> = { Accept: 'application/json' };
    if (options.body) { headers['Content-Type'] = 'application/json'; headers['Idempotency-Key'] = crypto.randomUUID(); }
    const bearer = options.setup ?? options.auth ?? this.token;
    if (bearer) headers.Authorization = `Bearer ${bearer}`;
    let response: Response;
    try { response = await fetch(`${this.baseUrl}${path}`, { method: options.method ?? 'GET', headers, body: options.body ? JSON.stringify(options.body) : undefined }); }
    catch (cause) { throw new Error('Could not reach the device. Check its address and local network.', { cause }); }
    const json = response.status === 204 ? {} : await response.json().catch(() => { throw new Error(`Device returned non-JSON data (${response.status}).`); });
    if (!response.ok) {
      const message = typeof (json as any)?.error?.message === 'string'
        ? (json as any).error.message
        : typeof (json as any)?.message === 'string'
          ? (json as any).message
          : `Device request failed (${response.status}).`;
      throw new Error(message);
    }
    return json;
  }
  private configure(input: ConnectionInput) { this.baseUrl = input.baseUrl.trim().replace(/\/$/, ''); this.deviceId = input.deviceId.trim(); }
  private beginSession(response: unknown, missingTokenMessage: string) {
    const session = response as Record<string, unknown>;
    if (typeof session.token !== 'string') throw new Error(missingTokenMessage);
    if (!Number.isSafeInteger(session.expiresInSeconds) || (session.expiresInSeconds as number) <= 0) {
      throw new Error('Device returned an invalid authentication lifetime.');
    }
    this.clearSubscription();
    this.token = session.token;
    this.sessionExpiresAt = Date.now() + (session.expiresInSeconds as number) * 1000;
  }
  private clearSubscription() {
    if (this.expiryTimer !== undefined) clearTimeout(this.expiryTimer);
    this.expiryTimer = undefined;
    this.socket?.close();
    this.socket = undefined;
  }
  async connect(input: ConnectionInput): Promise<DeviceSnapshot> {
    this.configure(input);
    const auth = await this.request('/api/v1/session', { method:'POST', auth:'', body:{...this.envelope(), deviceSecret:input.deviceSecret} });
    this.beginSession(auth, 'Device did not return an authentication token.');
    return this.refresh();
  }
  async provision(input: ProvisionInput): Promise<DeviceSnapshot> {
    this.configure(input);
    const session = await this.request('/api/v1/setup/session', { auth:'' }) as any;
    if (typeof session.token !== 'string') throw new Error('No physical-presence setup session is active. Hold the setup button at power-up and try again.');
    const result = await this.request('/api/v1/setup/provision', { method:'POST', setup:session.token, body:{...this.envelope(), wifiSsid:input.wifiSsid, wifiPassword:input.wifiPassword, deviceSecret:input.deviceSecret} });
    this.beginSession(result, 'Provisioning did not return an authentication token.');
    return this.refresh();
  }
  async refresh(): Promise<DeviceSnapshot> {
    const [status, profiles, history] = await Promise.all([this.request('/api/v1/status'), this.request('/api/v1/profiles'), this.history()]);
    return { status: validateStatus(status), profiles: validateProfiles(unwrap<Profile[]>(profiles, 'profiles')), history };
  }
  private async history(): Promise<HistoryEntry[]> {
    const history: HistoryEntry[] = [];
    let after = 0;
    while (history.length < 256) {
      const response = await this.request(`/api/v1/history?limit=100${after ? `&after=${after}` : ''}`);
      const page = validateHistory(unwrap<HistoryEntry[]>(response, 'history'));
      history.push(...page.slice(0, 256 - history.length));
      const nextAfter = (response as Record<string, unknown>)?.nextAfter;
      if (!Number.isSafeInteger(nextAfter) || (nextAfter as number) < 0) throw new Error('Device returned an invalid history cursor.');
      if (page.length === 0) {
        if (nextAfter !== after) throw new Error('Device returned an invalid history cursor.');
        break;
      }
      if ((nextAfter as number) <= after) throw new Error('Device returned a non-advancing history cursor.');
      after = nextAfter as number;
    }
    return history.slice(-100);
  }
  subscribe(listener: (event: ProtocolEvent) => void, disconnected: () => void): () => void {
    this.clearSubscription();
    let active = true;
    const disconnect = () => { if (!active) return; active = false; disconnected(); };
    const url = new URL(this.baseUrl); url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'; url.port = '81'; url.pathname = '/api/v1/events';
    this.socket = new WebSocket(url);
    this.socket.addEventListener('open', () => this.socket?.send(JSON.stringify({type:'authenticate', token:this.token})));
    this.socket.addEventListener('message', e => { try { const event = validateEvent(JSON.parse(String(e.data))); if (this.sequence && event.sequence !== this.sequence + 1) this.refresh().then(s => listener({protocol:PROTOCOL,type:'status.updated',sequence:event.sequence,deviceUptimeMs:event.deviceUptimeMs,payload:{refresh:s,sequenceGap:true}})).catch(disconnect); else listener(event); this.sequence = event.sequence; } catch { disconnect(); } });
    this.socket.addEventListener('close', disconnect); this.socket.addEventListener('error', disconnect);
    const expiresIn = Math.max(0, this.sessionExpiresAt - Date.now());
    this.expiryTimer = setTimeout(() => {
      disconnect();
      this.socket?.close();
      this.socket = undefined;
      this.expiryTimer = undefined;
    }, expiresIn);
    return () => { active = false; this.clearSubscription(); };
  }
  private async mutate(path:string, method:string, body:Record<string,unknown>) { await this.request(path,{method,body:{...this.envelope(),...body}}); }
  createProfile(i:{profileId:string;name:string;lowStockThreshold:number}) { return this.mutate('/api/v1/profiles','POST',i); }
  updateProfile(id:string,i:{name:string;lowStockThreshold:number}) { return this.mutate(`/api/v1/profiles/${encodeURIComponent(id)}`,'PATCH',i); }
  tare(profileId:string) { return this.mutate('/api/v1/actions/tare','POST',{profileId}); }
  calibrate(profileId:string,knownCount:number,knownSampleMassGrams?:number) { return this.mutate('/api/v1/actions/calibrate','POST',{profileId,knownCount,...(knownSampleMassGrams ? {knownSampleMassGrams}: {})}); }
  correct(eventId:string,profileId:string,count:number,reason:string) { return this.mutate(`/api/v1/counts/${encodeURIComponent(eventId)}/correction`,'POST',{profileId,count,reason}); }
  clearHistory(confirmation:'CLEAR HISTORY') { return this.mutate('/api/v1/history','DELETE',{confirmation}); }
  async exportData() { return validateExport(await this.request('/api/v1/export')); }
  async previewImport(data:DeviceExport): Promise<ImportPreview> {
    const response = await this.request('/api/v1/import/preview', {
      method:'POST', body:{...this.envelope(), import:validateExport(data)}
    }) as Record<string, unknown>;
    if (typeof response.previewToken !== 'string' ||
        typeof response.wouldReplaceProfiles !== 'number' ||
        typeof response.wouldReplaceHistory !== 'number') {
      throw new Error('Device returned an invalid import preview.');
    }
    return {
      previewToken: response.previewToken,
      profilesToReplace: response.wouldReplaceProfiles,
      historyToReplace: response.wouldReplaceHistory,
      expiresInSeconds: 30
    };
  }
  applyImport(data:DeviceExport,previewToken:string) { return this.mutate('/api/v1/import/apply','POST',{import:validateExport(data),previewToken}); }
}
function unwrap<T>(value: unknown, key: string): T { return (value && typeof value === 'object' && key in value) ? (value as any)[key] : value as T; }
