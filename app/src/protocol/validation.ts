import Ajv2020, { type ErrorObject } from 'ajv/dist/2020';
import statusSchema from '../generated/schemas/status.schema.json';
import eventSchema from '../generated/schemas/event.schema.json';
import exportSchema from '../generated/schemas/export.schema.json';
import type { DeviceExport, DeviceStatus, ProtocolEvent } from './types';

const ajv = new Ajv2020({ allErrors: true, strict: false });
const statusValidator = ajv.compile(statusSchema);
const eventValidator = ajv.compile(eventSchema);
const exportValidator = ajv.compile(exportSchema);
const explain = (errors: ErrorObject[] | null | undefined) => errors?.map(e => `${e.instancePath || '/'} ${e.message}`).join('; ') || 'unknown validation error';

function assertWith<T>(value: unknown, validator: typeof statusValidator, label: string): asserts value is T {
  if (!validator(value)) throw new ProtocolValidationError(`${label}: ${explain(validator.errors)}`);
}
export class ProtocolValidationError extends Error { override name = 'ProtocolValidationError'; }
export function validateStatus(value: unknown): DeviceStatus { assertWith<DeviceStatus>(value, statusValidator, 'Incompatible device status'); return value; }
export function validateEvent(value: unknown): ProtocolEvent { assertWith<ProtocolEvent>(value, eventValidator, 'Incompatible device event'); return value; }
export function validateExport(value: unknown): DeviceExport { assertWith<DeviceExport>(value, exportValidator, 'Incompatible backup'); rejectSecrets(value); return value; }
export function validateProfiles(value: unknown): DeviceExport['profiles'] { const wrapped = { schemaVersion: 3, deviceName: 'Validation', profiles: value, history: [] }; return validateExport(wrapped).profiles; }
export function validateHistory(value: unknown): DeviceExport['history'] { const wrapped = { schemaVersion: 3, deviceName: 'Validation', profiles: [], history: value }; return validateExport(wrapped).history; }

const SECRET_KEYS = new Set(['wifissid','wifipassword','wifisecret','devicesecret','token','authorization']);
export function rejectSecrets(value: unknown): void {
  if (!value || typeof value !== 'object') return;
  for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
    if (SECRET_KEYS.has(key.toLowerCase())) throw new ProtocolValidationError(`Backup contains forbidden secret field: ${key}`);
    rejectSecrets(nested);
  }
}
