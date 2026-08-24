import type { MeasurementState } from './protocol/types';
const presentation:Record<MeasurementState,{icon:string;label:string;detail:string;danger?:boolean}>={
 stable:{icon:'✓',label:'Stable count',detail:'The reading is stable; count and uncertainty are available.'},
 unstable:{icon:'≈',label:'Unstable — no count',detail:'Wait for vibration or movement to stop.'},
 disconnected:{icon:'⌁',label:'Sensor disconnected — no count',detail:'Check the load-cell and ADC connections.'},
 saturated:{icon:'⊘',label:'Sensor saturated — no count',detail:'Remove load and check sensor range.',danger:true},
 overload_indicated:{icon:'⚠',label:'Possible overload — no count',detail:'Remove the load immediately and inspect the mechanical stop.',danger:true},
 stale:{icon:'◷',label:'Reading stale — no count',detail:'No fresh sample is available.'},
 uncalibrated:{icon:'◇',label:'Calibration required — no count',detail:'Tare the empty bin, then calibrate with known parts.'},
 below_tare:{icon:'↓',label:'Below tare — no count',detail:'The measured load is below the stored empty-bin tare.'},
 calibration_invalid:{icon:'!',label:'Calibration invalid — no count',detail:'Repeat tare and known-count calibration.',danger:true},
 uncertainty_excessive:{icon:'±',label:'Uncertainty too high — no count',detail:'The device cannot produce a trustworthy count.'}
};
export function MeasurementStatus({state,count,uncertainty}:{state:MeasurementState;count:number|null;uncertainty:number|null}) { const p=presentation[state]; return <section className={`measurement ${p.danger?'danger':''}`} aria-labelledby="measurement-title"><div className="status-line"><span className="state-icon" aria-hidden="true">{p.icon}</span><h2 id="measurement-title">{p.label}</h2></div>{state==='stable'?<p className="count"><strong>{count}</strong> pieces <span>± {uncertainty}</span></p>:<p className="no-count">Count withheld</p>}<p>{p.detail}</p></section> }
