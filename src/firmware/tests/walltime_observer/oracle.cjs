'use strict';
function owned(value){const copy=JSON.parse(JSON.stringify(value));const freeze=x=>{if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};return freeze(copy);}
const clean=s=>!!s&&s.phase===0&&s.stop_at==='0'&&s.core_fault===0&&s.adapter_fault===0;
const uint=n=>Number.isSafeInteger(n)&&n>=0;
function stamp(s){return typeof s==='string'&&/^(0|[1-9][0-9]*)$/.test(s)&&BigInt(s)<=18446744073709551615n;}
function stateShape(s){return !!s&&stamp(s.boot)&&stamp(s.generation)&&stamp(s.stop_at)&&stamp(s.fault_at)&&
 uint(s.selected_axis)&&s.selected_axis>0&&s.selected_axis<=65535&&uint(s.phase)&&s.phase<=4&&uint(s.core_fault)&&uint(s.adapter_fault);}
function completionShape(pre,c){
 if(!stateShape(pre)||!c||!stateShape(c.before)||!stateShape(c.post)||!c.result||!c.audit)return false;
 if(pre.boot!==c.before.boot||pre.boot!==c.post.boot||pre.selected_axis!==c.before.selected_axis||pre.selected_axis!==c.post.selected_axis)return false;
 const r=c.result,a=c.audit;
 return stamp(r.accepted_at)&&uint(r.wire_error)&&uint(r.core_error)&&
  ['pre_phase','pre_stop','pre_fault','pre_adapter','accepted','post_stop'].every(k=>uint(a[k]))&&a.pre_phase<=4;
}
function explicitStop(pre,c){
 try{
  if(!completionShape(pre,c)||!clean(pre)||!clean(c.before))return false;
  const {result:r,audit:a,post:p}=c,at=BigInt(r.accepted_at);
  return r.wire_error===0&&r.core_error===0&&at>0n&&a.pre_phase===0&&a.pre_stop===0&&a.pre_fault===0&&a.pre_adapter===0&&
   BigInt(a.accepted)===at&&BigInt(a.post_stop)===at&&BigInt(p.stop_at)===at&&
   pre.boot===c.before.boot&&p.boot===pre.boot&&pre.generation===c.before.generation&&BigInt(p.generation)===BigInt(pre.generation)+1n&&
   pre.selected_axis===c.before.selected_axis&&p.selected_axis===pre.selected_axis;
 }catch{return false;}
}
function timeConsistent(c,s,pre){
 const a=c.audit,p=c.post;
 const generation=BigInt(pre.generation),beforeGeneration=BigInt(c.before.generation);
 if(BigInt(p.generation)!==generation+1n)return false;
 if(beforeGeneration!==(c.before.core_fault===8?generation+1n:generation))return false;
 return a.pre_phase>=3&&a.pre_fault===8&&a.pre_adapter===0&&a.pre_stop>0&&
  String(a.pre_stop)===s.stop_at&&String(a.post_stop)===s.stop_at&&p.stop_at===s.stop_at&&
  a.accepted>=a.pre_stop&&BigInt(a.accepted)===BigInt(c.result.accepted_at)&&p.core_fault===8&&p.adapter_fault===0&&p.phase>=3&&p.fault_at===p.stop_at;
}
// Only called at named prerequisites, never as a catch-all for failing invariants.
function serviceObstruction(s,t){
 return stateShape(s)&&!!t&&uint(t.max_gap)&&t.max_gap>=10&&s.phase>=3&&s.core_fault===8&&s.adapter_fault===0&&
  /^[1-9][0-9]*$/.test(s.stop_at)&&s.fault_at===s.stop_at;
}
class EnvironmentObstruction extends Error{constructor(stage,s,t){super('ENV_SERVICE_VIOLATION '+stage);this.stage=stage;this.native=s;this.clock=t;}}
module.exports={owned,clean,completionShape,timeConsistent,explicitStop,serviceObstruction,EnvironmentObstruction};
