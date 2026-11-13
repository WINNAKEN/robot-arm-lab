'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {PhoneControl}=require(process.env.SO_APP||'../../components/robot_phone/web/app.js');
const root=path.resolve(__dirname,'../../../..');
const native=JSON.parse(fs.readFileSync(path.join(root,'.dev/stop-capability-evidence/independent-r1/owner/pending.json'),'utf8'));
const terminal=native.final,stopping=native.immediate;let checks=0;
function ok(v,m){++checks;assert.ok(v,m);}
const boot=(id='11')=>({...terminal,boot:id,generation:'1',at:'1000',phase:0,stop_at:'0',fault_at:'0',core_fault:0,stop_verified:false,manual_power_cut_required:false});
function fixture(){let state=boot(),failed=false,pairs=0,time=100,hook=null,reply={wire_error:0,core_error:0};const calls=[];
 const c=new PhoneControl(async(url,o)=>{if(url==='/api/session'){calls.push({op:'pair'});if(failed)throw Error('pair failed');return {wire_error:0,credential:(++pairs===1?'b':'c').repeat(32)};}
  if(url==='/api/status'){calls.push({op:'status'});if(failed)throw Error('status failed');return hook?hook():state;}
  const f=o.body.split('|');calls.push({op:f[5]});if(f[5]==='handoff-acquire')return {wire_error:0,core_error:0,transfer_id:f[4],transfer_state:1};return reply;
 },()=>time);
 return {c,calls,set:s=>{state=s;},fail:v=>{failed=v;},hook:f=>{hook=f;},reply:r=>{reply=r;},advance:n=>{time+=n;}};
}
async function paired(){const f=fixture();await f.c.pair('a'.repeat(32));await f.c.poll();return f;}
async function observed(sample=terminal){const f=await paired();f.set({...sample});await f.c.poll();return f;}
async function retain(){for(const failure of ['status','offline']){const f=await observed();ok(f.c.snapshot.stop_verified,'real native Terminal consumed');if(failure==='status'){f.fail(true);await assert.rejects(f.c.poll());}else f.c.disconnect();const r=f.c.lastStopOutcome;ok(r?.stop_verified===true&&r?.at===terminal.at,'HISTORY_RETAINED_AFTER_FAILURE');ok(f.c.snapshot===null&&f.c.credential==='','live state/auth removed');ok(!f.c.canStop()&&!f.c.angleCanStart()&&f.c.authority==='','history never supplies control');}}
async function publish(){const f=await observed();ok(f.c.lastStopOutcome?.boot===terminal.boot,'AUTHENTICATED_OUTCOME_PUBLISHED');}
async function rollback(){const f=await observed();f.c.disconnect();await f.c.pair('a'.repeat(32));f.set({...terminal,at:'10999'});let rejected=false;try{await f.c.poll();}catch{rejected=true;}ok(rejected&&f.c.lastStopOutcome?.at===terminal.at,'ROLLBACK_REJECTED_ACROSS_DISCONNECT');}
(async()=>{
 const probe=process.argv.find(x=>x.startsWith('--probe='))?.slice(8);if(probe){await ({retain,publish,rollback}[probe])();console.log('OUTCOME PROBE PASS '+probe+' checks='+checks);return;}
 await retain();await publish();await rollback();
 {const f=await observed(),r=f.c.lastStopOutcome;ok(Object.isFrozen(r),'immutable primitive copy');assert.throws(()=>{r.stop_verified=false;});assert.throws(()=>{f.c.lastStopOutcome=null;});ok(!['credential','lease','ticket','nonce','positions','lease_owner'].some(k=>k in r),'no authority/secret fields');
  const before=[f.c.seq,f.c.lease,f.c.authority,f.c.received,f.c.epoch];const text=f.c.lastStopOutcomeText();ok(text.includes('과거 관측')&&text.includes('현재 안전 상태를 뜻하지 않음')&&text.includes('부팅 11'),'historical text');assert.deepEqual([f.c.seq,f.c.lease,f.c.authority,f.c.received,f.c.epoch],before);checks++;
  for(const action of [()=>f.c.clear(),()=>f.c.visible(false),()=>f.c.visible(true),()=>f.advance(1000),()=>f.c.pulse(),()=>f.c.disconnect()]){await action();ok(f.c.lastStopOutcome===r,'local lifecycle retains record');}
  await f.c.pair('a'.repeat(32));ok(f.c.lastStopOutcome===r,'explicit new pair retains');f.fail(true);await assert.rejects(f.c.pair('a'.repeat(32)));ok(f.c.lastStopOutcome===r,'failed pair retains');
 }
 {const f=await paired();f.c.update({...terminal});ok(f.c.lastStopOutcome===null,'raw update cannot publish');f.reply({...terminal,wire_error:0,core_error:0});await f.c.command('stop');ok(f.c.lastStopOutcome===null,'Stop ACK is not observation');}
 {const f=await observed();const r=f.c.lastStopOutcome;f.set(boot('12'));await f.c.poll();ok(f.c.lastStopOutcome===r&&f.c.snapshot.boot==='12','new boot nonterminal preserves prior provenance');f.set({...terminal,boot:'12',at:'10000'});await f.c.poll();ok(f.c.lastStopOutcome.boot==='12','new boot Terminal replacement');}
 {const f=await observed(),r=f.c.lastStopOutcome;f.set({...terminal,at:'11001',stop_verified:false,manual_power_cut_required:true,core_fault:12});await f.c.poll();ok(f.c.lastStopOutcome!==r&&f.c.lastStopOutcome.manual_power_cut_required===true,'new valid diagnostics replace');ok(f.c.lastStopOutcomeText().includes('수동 전원 차단 필요로 보고됨'),'manual-cut historical action');f.c.disconnect();ok(f.c.lastStopOutcome.manual_power_cut_required,'manual-cut persists offline');}
 {const f=await paired();const s={...terminal};f.set(s);await f.c.poll();s.stop_verified=false;s.at='1';ok(f.c.lastStopOutcome.stop_verified&&f.c.lastStopOutcome.at===terminal.at,'source aliases cannot mutate evidence');}
 {const f=await paired();f.set({...stopping});await f.c.poll();ok(f.c.lastStopOutcome===null,'Stopping not terminal evidence');}
 {const f=await observed(),r=f.c.lastStopOutcome;f.set({...terminal});await f.c.poll();assert.deepEqual(f.c.lastStopOutcome,r);checks++;}
 {const f=await observed();f.c.disconnect();await f.c.pair('a'.repeat(32));f.set({...terminal,generation:'3',at:'11001'});await assert.rejects(f.c.poll());ok(f.c.lastStopOutcome.generation==='4','lower generation rejected without live snapshot');}
 for(const patch of [{stop_verified:'true'},{manual_power_cut_required:undefined},{core_stop_verified:0},{queue_stop_late:'false'},{selected_axis:-1},{core_state:1.2},{core_fault:4294967296},{adapter_fault:undefined},{at:'18446744073709551616'}]){
  const f=await observed(),old=f.c.lastStopOutcome;f.set(boot('12'));await f.c.poll();await f.c.transferAndAcquire();const binding=f.c.stopBinding;f.set({...terminal,boot:'12',...patch});await assert.rejects(f.c.poll());ok(f.c.lastStopOutcome===old&&f.c.stopBinding===binding,'malformed final preserves evidence AND retirement auth');f.set({...terminal,boot:'12',at:'11001'});await f.c.poll();ok(f.c.lastStopOutcome.boot==='12'&&f.c.stopBinding===null,'valid readonly recovery completes after malformed final');
 }
 {const f=await paired(),s={...terminal};delete s.core_stop_verified;delete s.queue_stop_late;f.set(s);await f.c.poll();ok(f.c.lastStopOutcome.core_stop_verified===null&&f.c.lastStopOutcome.queue_stop_late===null,'optional facts unknown, not safe false');ok(f.c.lastStopOutcomeText().includes('미보고'),'unknown displayed');}
 {const f=await paired();const max='18446744073709551615';f.set({...terminal,boot:max,generation:max,at:max,stop_at:max,fault_at:max,selected_axis:0,core_fault:4294967295});await f.c.poll();ok(f.c.lastStopOutcome.at===max&&f.c.lastStopOutcome.generation===max&&f.c.lastStopOutcome.selected_axis===0,'uint64 saturation/unknown axis preserved');}
 {const f=await paired();f.set({...terminal,fault_at:'18446744073709551615',manual_power_cut_required:true});await f.c.poll();ok(f.c.lastStopOutcome.fault_at==='18446744073709551615','no invented relative fault-time validation');}
 {const f=await observed();let oldDone,newDone,n=0;f.hook(()=>new Promise(r=>{if(n++===0)oldDone=r;else newDone=r;}));const old=f.c.poll(),latest=f.c.poll();newDone({...terminal,at:'13000'});await latest;const record=f.c.lastStopOutcome;oldDone({...terminal,at:'12000',manual_power_cut_required:true});await old;ok(f.c.lastStopOutcome===record&&record.at==='13000','older completion ignored');}
 {const f=await observed();let done;f.hook(()=>new Promise(r=>{done=r;}));const old=f.c.poll();await f.c.pair('a'.repeat(32));f.hook(null);f.set(boot('12'));await f.c.poll();const record=f.c.lastStopOutcome;done({...terminal,at:'12000',manual_power_cut_required:true});await old;ok(f.c.lastStopOutcome===record&&f.c.snapshot.boot==='12','old session completion cannot overwrite');}
 console.log('STOP OUTCOME JS PASS checks='+checks+'; actual production JS, recorded actualOwner Terminal plus explicit synthetic diagnostics/mock transport; no DOM/hardware');
})().catch(e=>{console.error(e);process.exitCode=1;});
