import { describe, expect, it } from 'vitest';
import { MockDeviceTransport } from '../protocol/mockTransport';
import { loadCache, saveCache } from '../storage';

describe('browser cache validation',()=>{
 it('returns a cache with a valid runtime-validated snapshot',()=>{const snapshot=new MockDeviceTransport().snapshot;saveCache({baseUrl:'http://device.local',deviceId:'pt-mock',snapshot:{...snapshot,cachedAt:'2026-08-24T00:00:00.000Z'}});expect(loadCache()).toEqual({baseUrl:'http://device.local',deviceId:'pt-mock',snapshot:{...snapshot,cachedAt:'2026-08-24T00:00:00.000Z'}})});
 it.each([
  ['partial snapshot',{status:new MockDeviceTransport().snapshot.status,profiles:[]}],
  ['stale profile schema',{...new MockDeviceTransport().snapshot,profiles:[{id:'old',name:'Old',lowStockThreshold:1,calibrated:false,provisional:false,calibration:{schemaVersion:1}}]}],
  ['malformed history',{...new MockDeviceTransport().snapshot,history:[{sequence:'one'}]}],
 ])('ignores a %s without throwing',(_label,snapshot)=>{localStorage.setItem('parts-tally:non-secret-cache:v1',JSON.stringify({baseUrl:'http://device.local',deviceId:'pt-mock',snapshot}));expect(()=>loadCache()).not.toThrow();expect(loadCache()).toBeUndefined()});
});
