'use strict';
const assert=require('node:assert/strict');
const {PhoneControl}=require(process.env.INTENT_JS||'../../components/robot_phone/web/app.js');
let checks=0;
const ok=x=>{++checks;assert.ok(x);};
const base=(phase=0)=>({boot:'9007199254740993',generation:String(phase+1),at:'1000',phase,ready:phase===2,core_fault:0,adapter_fault:0,fault_at:'0',stop_at:'0',lease_owner:'1',lease_until:'1800',config_oldest_at:'900',selected_axis:1,angle_available:phase===2,angle_joint:phase===2?1:0});
function fixture(){
  let time=1000,snapshot=base(),held='',release,reject,failed='',statusHold=null;
  const calls=[];
  const c=new PhoneControl(async(path,options)=>{
    if(path==='/api/session')return {wire_error:0,credential:'b'.repeat(32)};
    if(path==='/api/status')return statusHold?await statusHold:snapshot;
    const op=options.body.split('|')[5]; calls.push({op,body:options.body,path});
    if(op===held)await new Promise((yes,no)=>{release=yes;reject=no;});
    if(op===failed)return {wire_error:11,core_error:6};
    return {wire_error:0,core_error:0,lease:'9007199254740997',ticket:'9007199254740999'};
  },()=>time);
  return {c,calls,ops:()=>calls.map(x=>x.op),time:x=>{time=x;},set:s=>{snapshot=s;},hold:op=>{held=op;},release:()=>release(),reject:()=>reject(Error('late transport failure')),fail:op=>{failed=op;},status:p=>{statusHold=p;}};
}
async function paired(f){await f.c.pair('a'.repeat(32));await f.c.poll();}
const flush=async()=>{for(let n=0;n<12;++n)await Promise.resolve();};
async function normal(f){f.set(base(2));await paired(f);await f.c.command('acquire');}
function transition(f,phase,calibrated=true){f.set({...base(phase),at:String(1000+phase),angle_available:phase===2&&calibrated,angle_joint:phase===2&&calibrated?1:0});}
(async()=>{
  for(const calibrated of [false,true])for(const intermediate of [false,true]){
    const f=fixture();await paired(f);await f.c.handoffAndAcquire();
    await assert.rejects(f.c.handoffAndAcquire());await assert.rejects(f.c.command('drive'));
    if(intermediate){transition(f,1,calibrated);await f.c.poll();ok(f.c.handoffIntent);}
    transition(f,2,calibrated);await f.c.poll();await f.c.poll();
    ok(f.ops().join(',')==='handoff,acquire');ok(f.c.authority==='normal');ok(!f.c.handoffIntent);
  }
  // A real pending ACK must not defeat the later status generation or capability gain.
  {const f=fixture();await paired(f);f.hold('handoff');const ack=f.c.handoffAndAcquire();
    transition(f,1);await f.c.poll();transition(f,2);await f.c.poll();ok(f.c.handoffIntent&&f.c.busy);ok(f.ops().join(',')==='handoff');
    f.release();await ack;ok(f.c.handoffIntent);await f.c.poll();ok(f.ops().join(',')==='handoff,acquire');ok(f.c.authority==='normal');}
  for(const event of ['stop','hide','offline','stale','deadline','boot','axis','fault','adapter','reverse'])for(const error of [false,true]){
    const f=fixture();await paired(f);f.hold('handoff');const pending=f.c.handoffAndAcquire();const outcome=pending.then(()=>null,e=>e);
    transition(f,1);await f.c.poll();
    if(event==='stop'){await f.c.command('stop');ok(f.c.busy);await assert.rejects(f.c.command('drive'));}
    else if(event==='hide')f.c.visible(false);
    else if(event==='offline')f.c.disconnect();
    else if(event==='stale'){f.time(1601);await f.c.pulse();}
    else if(event==='deadline'){f.time(1700);transition(f,2);await f.c.poll();}
    else {const s={...base(2),at:'1003'};if(event==='boot')s.boot='21';if(event==='axis')s.selected_axis=2;if(event==='fault')s.core_fault=1;if(event==='adapter')s.adapter_fault=1;if(event==='reverse'){s.phase=0;s.generation='4';s.angle_available=false;s.angle_joint=0;}f.set(s);await f.c.poll();}
    if(error)f.reject();else f.release();await outcome;
    if(event==='hide')f.c.visible(true);
    if(f.c.credential){f.set({...base(2),at:'1004'});await f.c.poll();}
    ok(!f.c.handoffIntent&&f.c.authority==='');ok(!f.ops().includes('acquire'));ok(!f.c.busy);
  }
  // The intended Acquire is consumed once, even when its response is held.
  for(const event of ['stop','hide','offline','generation','stale']){
    const f=fixture();await paired(f);await f.c.handoffAndAcquire();f.hold('acquire');transition(f,2);
    const pending=f.c.poll();const outcome=pending.then(()=>null,e=>e);await flush();await f.c.poll();ok(f.ops().filter(x=>x==='acquire').length===1);
    if(event==='stop')await f.c.command('stop');else if(event==='hide')f.c.visible(false);else if(event==='offline')f.c.disconnect();else if(event==='stale')f.time(1601);else f.c.update({...base(2),generation:'4',at:'1003'});
    f.release();await outcome;ok(f.c.authority===''&&f.c.lease==='0');ok(!f.c.handoffIntent);
  }
  for(const event of ['stop','generation']){
    const f=fixture();await paired(f);await f.c.handoffAndAcquire();f.hold('acquire');transition(f,2);
    const pending=f.c.poll();const outcome=pending.then(()=>null,e=>e);await flush();
    if(event==='stop')await f.c.command('stop');else f.c.update({...base(2),generation:'4',at:'1003'});
    const credential=f.c.credential;f.reject();ok(await outcome instanceof Error);
    ok(f.c.credential===credential&&f.c.snapshot!==null);ok(f.c.lease==='0'&&!f.c.handoffIntent);
  }
  for(const hold of ['arm','ticket'])for(const change of ['capability','joint']){
    const f=fixture();await normal(f);const lease=f.c.lease;f.hold(hold);
    const pending=f.c.moveAngle('0.4166666666666667','deg');const outcome=pending.then(()=>null,e=>e);await flush();
    const changed={...base(2),at:'1001'};if(change==='capability')changed.angle_available=false;else changed.angle_joint=2;
    f.c.update(changed);f.c.update({...base(2),at:'1002'}); // ABA must not reanimate this intent.
    f.release();ok(await outcome instanceof Error);ok(!f.ops().includes('joint-step'));ok(f.c.lease===lease&&f.c.authority==='normal');ok(f.c.ticket==='0');
    if(hold==='arm')ok(!f.ops().includes('ticket'));
    f.time(1201);f.c.update({...base(2),at:'1201',ready:false});await f.c.pulse();ok(f.ops().at(-1)==='renew');
  }
  {const f=fixture();await normal(f);f.hold('arm');const pending=f.c.moveAngle('1','deg');const outcome=pending.then(()=>null,e=>e);await f.c.command('stop');ok(f.c.busy);await assert.rejects(f.c.command('acquire'));f.release();ok(await outcome instanceof Error);ok(!f.c.busy&&f.c.authority==='');}
  {const f=fixture();await normal(f);f.hold('joint-step');const pending=f.c.moveAngle('1','deg');const outcome=pending.then(()=>null,e=>e);await flush();await f.c.command('stop');f.release();ok(await outcome instanceof Error);ok(f.ops().includes('joint-step'));ok(f.calls.find(x=>x.op==='stop').path.endsWith(':8081/api/stop'));}
  // A response for an old session cannot overwrite or disconnect the new one.
  for(const error of [false,true]){
    const f=fixture();await paired(f);let resolve,reject;f.status(new Promise((yes,no)=>{resolve=yes;reject=no;}));const old=f.c.poll();const outcome=old.then(()=>null,e=>e);
    await f.c.pair('a'.repeat(32));f.status(null);transition(f,2);await f.c.poll();await f.c.command('acquire');
    if(error)reject(Error('old status error'));else resolve({...base(),boot:'21'});await outcome;
    ok(f.c.authority==='normal'&&f.c.snapshot.boot===base().boot&&f.c.credential!=='');
  }
  for(const op of ['handoff','arm','ticket']){const f=fixture();if(op==='handoff')await paired(f);else await normal(f);f.fail(op);await assert.rejects(op==='handoff'?f.c.handoffAndAcquire():f.c.moveAngle('1','deg'));ok(!f.c.handoffIntent&&f.c.lease==='0');}
  {const f=fixture();await normal(f);await f.c.poll();ok(!f.ops().includes('handoff')&&f.ops().filter(x=>x==='acquire').length===1);}
  console.log(`INTENT UI PASS checks=${checks}; actual production PhoneControl; status/transport simulated; browser=NOT_RUN`);
})().catch(e=>{console.error(e);process.exitCode=1;});
