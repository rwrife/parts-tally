/** Types are derived from docs/schemas/api-v1 and regenerated schema copies. */
export const PROTOCOL = 'parts-tally/v1' as const;
export type MeasurementState = 'stable' | 'uncalibrated' | 'unstable' | 'stale' | 'disconnected' | 'saturated' | 'overload_indicated' | 'below_tare' | 'calibration_invalid' | 'uncertainty_excessive';
export interface Measurement { state: MeasurementState; stable: boolean; estimatedCount: number | null; uncertaintyPieces: number | null; sampleAgeMs: number; netGrams?: number }
export interface DeviceStatus { protocol: typeof PROTOCOL; deviceId: string; firmwareVersion: string; measurement: Measurement; faults: string[]; deviceName?: string; activeProfileId?: string }
export interface Calibration { schemaVersion: 2; tareValid: boolean; valid: boolean; provisional: boolean; tareCode: number; gramsPerCode: number; unitMassGrams: number; unitUncertaintyGrams: number; calibrationResidualGrams: number; knownCount: number; createdMs: number }
export interface Profile { id: string; name: string; lowStockThreshold: number; calibrated: boolean; provisional: boolean; calibration: Calibration }
export interface HistoryEntry { sequence: number; deviceUptimeMs: number; profileId: string; kind: 'count' | 'correction'; eventId: string; relatedEventId?: string; reason: string; count: number }
export interface DeviceExport { schemaVersion: 3; deviceName: string; profiles: Profile[]; history: HistoryEntry[] }
export interface ProtocolEvent { protocol: typeof PROTOCOL; type: 'measurement.updated'|'measurement.stability_changed'|'profile.changed'|'threshold.changed'|'fault.raised'|'fault.cleared'|'status.updated'|'device.restarting'; sequence: number; deviceUptimeMs: number; payload: Record<string, unknown> }
export interface ConnectionInput { baseUrl: string; deviceId: string; deviceSecret: string }
export interface ProvisionInput extends ConnectionInput { wifiSsid: string; wifiPassword: string }
export interface ImportPreview { previewToken: string; profilesToReplace: number; historyToReplace: number; expiresInSeconds: number }
export interface DeviceSnapshot { status: DeviceStatus; profiles: Profile[]; history: HistoryEntry[]; cachedAt?: string }

export interface DeviceTransport {
  connect(input: ConnectionInput): Promise<DeviceSnapshot>;
  provision(input: ProvisionInput): Promise<DeviceSnapshot>;
  refresh(): Promise<DeviceSnapshot>;
  subscribe(listener: (event: ProtocolEvent) => void, disconnected: () => void): () => void;
  createProfile(input: { profileId: string; name: string; lowStockThreshold: number }): Promise<void>;
  updateProfile(id: string, input: { name: string; lowStockThreshold: number }): Promise<void>;
  tare(profileId: string): Promise<void>;
  calibrate(profileId: string, knownCount: number, knownSampleMassGrams?: number): Promise<void>;
  correct(eventId: string, profileId: string, count: number, reason: string): Promise<void>;
  clearHistory(confirmation: 'CLEAR HISTORY'): Promise<void>;
  exportData(): Promise<DeviceExport>;
  previewImport(data: DeviceExport): Promise<ImportPreview>;
  applyImport(data: DeviceExport, previewToken: string): Promise<void>;
}
