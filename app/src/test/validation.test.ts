import { describe, expect, it } from 'vitest';
import stable from '../../../tests/fixtures/protocol/v1/status-stable.json';
import exported from '../../../tests/fixtures/protocol/v1/export-full.json';
import { ProtocolValidationError, validateExport, validateStatus } from '../protocol/validation';
import type { MeasurementState } from '../protocol/types';

describe('schema-derived runtime validation',()=>{
 it('accepts repository status and export fixtures',()=>{expect(validateStatus(stable).measurement.estimatedCount).toBe(42);expect(validateExport(exported).schemaVersion).toBe(3)});
 it.each<MeasurementState>(['uncalibrated','unstable','stale','disconnected','saturated','overload_indicated','below_tare','calibration_invalid','uncertainty_excessive'])('requires null count for %s',state=>{expect(()=>validateStatus({...stable,measurement:{...stable.measurement,state,stable:false,estimatedCount:null,uncertaintyPieces:null}})).not.toThrow();expect(()=>validateStatus({...stable,measurement:{...stable.measurement,state,stable:false}})).toThrow(ProtocolValidationError)});
 it('rejects incompatible versions and nested secrets',()=>{expect(()=>validateExport({...exported,schemaVersion:4})).toThrow(/Incompatible backup/);expect(()=>validateExport({...exported,profiles:[{...exported.profiles[0],deviceSecret:'leak'}]})).toThrow()});
});
