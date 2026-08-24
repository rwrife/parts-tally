import { PROTOCOL, type ConnectionInput, type DeviceExport, type DeviceSnapshot, type DeviceTransport, type ImportPreview, type MeasurementState, type Profile, type ProtocolEvent, type ProvisionInput } from './types';
import { validateExport } from './validation';

const calibration = { schemaVersion:2 as const,tareValid:false,valid:false,provisional:false,tareCode:0,gramsPerCode:0,unitMassGrams:0,unitUncertaintyGrams:0,calibrationResidualGrams:0,knownCount:0,createdMs:0 };
export class MockDeviceTransport implements DeviceTransport {
  snapshot: DeviceSnapshot = { status:{protocol:PROTOCOL,deviceId:'pt-mock',firmwareVersion:'0.1.0-mock',deviceName:'Workshop Parts Tally',measurement:{state:'uncalibrated',stable:false,estimatedCount:null,uncertaintyPieces:null,sampleAgeMs:20},faults:[]}, profiles:[], history:[] };
  private listener?: (event:ProtocolEvent)=>void; private down?:()=>void; private sequence=1; private preview?:{data:DeviceExport;token:string};
  async connect(input:ConnectionInput) { if (input.deviceSecret === 'wrong-secret-value') throw new Error('Authentication failed. Check the device secret.'); return structuredClone(this.snapshot); }
  async provision(input:ProvisionInput) { void input; return structuredClone(this.snapshot); }
  async refresh() { return structuredClone(this.snapshot); }
  subscribe(listener:(event:ProtocolEvent)=>void, disconnected:()=>void) { this.listener=listener; this.down=disconnected; return ()=>{this.listener=undefined}; }
  async createProfile(input:{profileId:string;name:string;lowStockThreshold:number}) { this.snapshot.profiles.push({id:input.profileId,name:input.name,lowStockThreshold:input.lowStockThreshold,calibrated:false,provisional:false,calibration:{...calibration}}); }
  async updateProfile(id:string,input:{name:string;lowStockThreshold:number}) { Object.assign(this.snapshot.profiles.find(p=>p.id===id)!,input); }
  async tare(profileId:string) { const p=this.profile(profileId); p.calibration.tareValid=true; this.snapshot.status.measurement={state:'uncalibrated',stable:false,estimatedCount:null,uncertaintyPieces:null,sampleAgeMs:10}; }
  async calibrate(profileId:string,knownCount:number,knownSampleMassGrams?:number) { const p=this.profile(profileId); p.calibrated=true; p.calibration={...calibration,tareValid:true,valid:true,knownCount,unitMassGrams:(knownSampleMassGrams??50)/knownCount,createdMs:Date.now()}; this.setState('stable',knownCount); }
  async correct(eventId:string,profileId:string,count:number,reason:string) { this.snapshot.history.push({sequence:++this.sequence,deviceUptimeMs:2000,profileId,kind:'correction',eventId:`correction-${this.sequence}`,relatedEventId:eventId,reason,count}); }
  async clearHistory(confirmation:'CLEAR HISTORY') { void confirmation; this.snapshot.history=[]; }
  async exportData():Promise<DeviceExport> { return validateExport({schemaVersion:3,deviceName:this.snapshot.status.deviceName??'Parts Tally',profiles:this.snapshot.profiles,history:this.snapshot.history}); }
  async previewImport(data:DeviceExport):Promise<ImportPreview> { validateExport(data); const token='preview-token-123456'; this.preview={data:structuredClone(data),token}; return {previewToken:token,profilesToReplace:data.profiles.length,historyToReplace:data.history.length,expiresInSeconds:30}; }
  async applyImport(data:DeviceExport,token:string) { if (!this.preview || token!==this.preview.token || JSON.stringify(data)!==JSON.stringify(this.preview.data)) throw new Error('Import preview expired or changed. Preview it again.'); this.snapshot.profiles=structuredClone(data.profiles);this.snapshot.history=structuredClone(data.history); }
  setState(state:MeasurementState,count:number|null=null,emit=true) { this.snapshot.status.measurement={state,stable:state==='stable',estimatedCount:state==='stable'?count:null,uncertaintyPieces:state==='stable'?1:null,sampleAgeMs:20}; this.snapshot.status.faults=['disconnected','saturated','overload_indicated'].includes(state)?[`mock_${state}`]:[]; if(emit)this.emit('measurement.updated'); }
  disconnect() { this.down?.(); }
  reconnectWithGap() { this.sequence+=2; this.listener?.({protocol:PROTOCOL,type:'status.updated',sequence:this.sequence,deviceUptimeMs:2200,payload:{sequenceGap:true}}); }
  addCount(profileId:string,count:number) { this.snapshot.history.push({sequence:++this.sequence,deviceUptimeMs:1500,profileId,kind:'count',eventId:`count-${this.sequence}`,reason:'',count}); this.emit('status.updated'); }
  private emit(type:ProtocolEvent['type']) { this.listener?.({protocol:PROTOCOL,type,sequence:++this.sequence,deviceUptimeMs:1000,payload:{}}); }
  private profile(id:string):Profile { const p=this.snapshot.profiles.find(x=>x.id===id); if(!p) throw new Error('Profile not found'); return p; }
}

declare global { interface Window { __partsTallyMock?: MockDeviceTransport } }
