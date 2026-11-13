'use strict';
const assert=require('node:assert/strict');
const {PhoneControl}=require(process.env.ANGLE_JS||'../../components/robot_phone/web/app.js');
const base=()=>({boot:'9007199254740993',generation:'1',at:'1000',phase:2,core_fault:0,fault_at:'0',stop_at:'0',lease_owner:'1',lease_until:'1800',config_oldest_at:'900',selected_axis:1,angle_joint:1,angle_available:true,ready:true});
let checks=0;const ok=x=>{++checks;assert.ok(x);};
function fixture(){let now=1000,s=base(),held='',release;const calls=[];let promise=null;const c=new PhoneControl(async(path,opts)=>{if(path==='/api/session')return{wire_error:0,credential:'b'.repeat(32)};if(path==='/api/status')return s;const op=opts.body.split('|')[5];calls.push(opts.body);if(op===held)await promise;return{wire_error:0,core_error:0,lease:'9007199254740997',ticket:'9007199254740999'};},()=>now);return{c,calls,set:x=>{s=x;},time:x=>{now=x;},hold:op=>{held=op;promise=new Promise(r=>release=r);},release:()=>release()};}
async function setup(f){await f.c.pair('a'.repeat(32));await f.c.poll();await f.c.command('acquire');}
(async()=>{
 for(const unit of ['deg','rad']){const f=fixture();await setup(f);await f.c.moveAngle('-0.4166666666666667',unit);ok(f.calls.slice(-3).map(x=>x.split('|')[5]).join(',')==='arm,ticket,joint-step');ok(f.calls.at(-1).includes(`|1|1|${unit}|-0.4166666666666667`));ok(f.calls.at(-1).startsWith('v2|9007199254740993|'));ok(f.c.ticket==='0');}
 for(const raw of ['',0,'0','-0','0.0','+1','01','.5','1.','1e2','NaN','Infinity',' 1','1 ','1|0','1000000','1.0000000000000000000']){const f=fixture();await setup(f);const n=f.calls.length;await assert.rejects(f.c.moveAngle(raw,'deg'));ok(f.calls.length===n);}
 {const f=fixture();await setup(f);f.set({...base(),angle_available:false});await f.c.poll();await assert.rejects(f.c.moveAngle('1','deg'));ok(!f.calls.some(x=>x.startsWith('v2|')));}
 for(const hold of ['arm','ticket'])for(const change of ['stop','hide','stale','phase','axis','joint','capability']){
  const f=fixture();await setup(f);f.hold(hold);const pending=f.c.moveAngle('0.4166666666666667','deg');
  for(let n=0;n<10&&!f.calls.some(x=>x.split('|')[5]===hold);++n)await Promise.resolve();
  if(change==='stop')await f.c.command('stop');else if(change==='hide')f.c.visible(false);else if(change==='stale')f.time(1601);else{const s={...base(),at:'1001'};if(change==='phase')s.generation='2';if(change==='axis')s.selected_axis=2;if(change==='joint')s.angle_joint=2;if(change==='capability')s.angle_available=false;f.c.update(s);}
  f.release();await assert.rejects(pending);ok(!f.calls.some(x=>x.startsWith('v2|')));if(hold==='arm')ok(!f.calls.some(x=>x.split('|')[5]==='ticket'));
 }
 {const f=fixture();await setup(f);f.hold('arm');let input={raw:'0.4166666666666667',unit:'deg'};const moving=f.c.moveAngle(input.raw,input.unit);input.raw='50';input.unit='rad';await assert.rejects(f.c.moveAngle('1','deg'));await assert.rejects(f.c.command('release'));f.release();await moving;ok(f.calls.at(-1).endsWith('|deg|0.4166666666666667'));}
 {const f=fixture();await setup(f);const lease=f.c.lease;f.time(1201);f.set({...base(),at:'1201',ready:false});await f.c.poll();ok(f.c.authority==='normal'&&f.c.lease===lease);await f.c.pulse();ok(f.calls.at(-1).split('|')[5]==='renew');await assert.rejects(f.c.moveAngle('1','deg'));}
 console.log(`ANGLE UI PASS checks=${checks} actual_js=true browser=NOT_RUN`);
})().catch(e=>{console.error(e);process.exitCode=1;});
