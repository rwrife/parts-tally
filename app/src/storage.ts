import type { DeviceSnapshot } from './protocol/types';
import { validateHistory, validateProfiles, validateStatus } from './protocol/validation';
const KEY='parts-tally:non-secret-cache:v1';
export interface BrowserCache { baseUrl:string; deviceId:string; snapshot?:DeviceSnapshot }
export function loadCache():BrowserCache|undefined { try { const value:unknown=JSON.parse(localStorage.getItem(KEY)??'null'); if(!value || typeof value!=='object')return;const cache=value as Record<string,unknown>;if(typeof cache.baseUrl!=='string'||typeof cache.deviceId!=='string')return;if(cache.snapshot===undefined)return {baseUrl:cache.baseUrl,deviceId:cache.deviceId};if(!cache.snapshot||typeof cache.snapshot!=='object')return;const snapshot=cache.snapshot as Record<string,unknown>;const cachedAt=snapshot.cachedAt;if(cachedAt!==undefined&&typeof cachedAt!=='string')return;return {baseUrl:cache.baseUrl,deviceId:cache.deviceId,snapshot:{status:validateStatus(snapshot.status),profiles:validateProfiles(snapshot.profiles),history:validateHistory(snapshot.history),...(cachedAt===undefined?{}:{cachedAt})}}; } catch { /* ignore corrupt or incompatible cache */ } }
export function saveCache(cache:BrowserCache) { localStorage.setItem(KEY,JSON.stringify(cache)); }
export function clearCache() { localStorage.removeItem(KEY); }
