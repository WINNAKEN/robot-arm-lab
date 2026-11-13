'use strict';
const assert=require('node:assert/strict');
const {PhoneControl}=require(process.env.SC_APP||'../../components/robot_phone/web/app.js');
let checks=0;const ok=(v,m)=>{++checks;assert.ok(v,m);};
function fixture(){
 let now=100,phase=0,generation='1',at=1000,boot='11',axis=1,pairs=0;
 let hold='',release,fail='',pollHook=null,receiptMutation=x=>x;
 const calls=[];
 const status=()=>({boot,generation,at:String(++at),lease_owner:'0',lease_until:'0',config_oldest_at:'900',fault_at:'0',stop_at:phase>=3?'1050':'0',phase,core_state:phase===0?8:phase===1?1:phase===2?2:phase===3?7:9,core_fault:0,adapter_fault:0,selected_axis:axis,ready:false,angle_available:false,angle_joint:0,stop_verified:phase===4,manual_power_cut_required:false});
 const c=new PhoneControl(async(url,options)=>{
  if(url==='/api/session')return {wire_error:0,credential:(++pairs===1?'b':'c').repeat(32)};
  if(url==='/api/status'){calls.push({op:'status',credential:options.headers['X-Session-Credential']});return pollHook?pollHook():status();}
  const f=options.body.split('|');calls.push({op:f[5],body:f,credential:options.headers['X-Session-Credential']});
  if(hold===f[5])await new Promise(resolve=>{release=resolve;});
  if(fail===f[5])throw Error('fixture transport failure');
  if(f[5]==='handoff-acquire')return {wire_error:0,core_error:0,transfer_id:f[4],transfer_state:1};
  if(f[5]==='handoff-result')return receiptMutation({wire_error:0,core_error:0,transfer_id:f[7],transfer_state:2,transfer_generation:'3',lease:'8',accepted_at:'1000',lease_until:'1800',sequence_floor:'1',grant_at:'900',pending_until:'1100'});
  return {wire_error:0,core_error:0};
 },()=>now);
 return {c,calls,status,set:(p,g=String(p+1),a=1,b='11')=>{phase=p;generation=g;axis=a;boot=b;},hold:v=>{hold=v;},release:()=>release(),fail:v=>{fail=v;},poll:v=>{pollHook=v;},advance:v=>{now+=v;},mutate:v=>{receiptMutation=v;}};
}
async function paired(){const f=fixture();await f.c.pair('a'.repeat(32));await f.c.poll();return f;}
async function start(f,held=false){if(held)f.hold('handoff-acquire');const p=f.c.transferAndAcquire();if(!held)await p;return {promise:p,id:f.c.handoff.id};}
async function hide(){const f=await paired(),h=await start(f,true);f.c.visible(false);f.c.visible(true);await f.c.command('stop');const stop=f.calls.at(-1);ok(stop.body[7]===h.id,'HIDE_STOP_KEY');ok(stop.credential==='b'.repeat(32),'origin credential');ok(f.c.busy,'Stop cannot steal normal busy');f.release();await h.promise;ok(f.c.authority===''&&!f.c.handoffIntent,'late ACK cannot restore');}
async function retry(){const f=await paired(),h=await start(f);f.fail('stop');await assert.rejects(f.c.command('stop'));f.fail('');await f.c.command('stop');ok(f.calls.at(-1).body[7]===h.id,'RETRY_STOP_KEY');ok(f.c.stopBinding?.id===h.id,'ACK never consumes Stop identity');}
async function recovery(){const f=await paired(),h=await start(f);f.c.disconnect();ok(f.c.credential===''&&f.c.snapshot===null,'normal disconnect');ok(f.c.canStop(),'Stop-only connection retained');await f.c.command('stop');ok(f.calls.at(-1).credential==='b'.repeat(32)&&f.calls.at(-1).body[7]===h.id,'disconnected Stop origin');f.set(3,'3');await f.c.poll();ok(f.c.stopBinding?.id===h.id,'STOPPING_RECOVERY_AUTH');ok(f.c.credential===''&&f.c.authority==='','readonly recovery');f.set(4,'4');await f.c.poll();ok(f.calls.at(-1).credential==='b'.repeat(32),'final auth survived Stopping');ok(f.c.stopBinding===null&&f.c.snapshot.stop_verified,'final verification displayed before retirement');ok(!f.c.canStop(),'no fabricated ordinary credential');}
async function prebinding(){const f=await paired();let release;f.poll(()=>new Promise(r=>{release=r;}));const old=f.c.poll();const h=await start(f);f.set(4,'4');release(f.status());await old;ok(f.c.stopBinding?.id===h.id,'PREBINDING_STATUS');f.poll(null);await f.c.poll();ok(f.c.stopBinding===null,'new terminal poll retires');}
(async()=>{
 const selected=process.argv.find(x=>x.startsWith('--probe='))?.slice(8);
 if(selected){await ({hide,retry,recovery,prebinding}[selected])();console.log('SC PROBE PASS '+selected+' checks='+checks);return;}
 await hide();await retry();await recovery();
 {const f=await paired(),h=await start(f);ok(Object.isFrozen(f.c.stopBinding),'immutable binding');f.advance(1147);f.set(1);await f.c.poll();ok(!f.c.handoffIntent&&f.c.stopBinding.id===h.id,'observer expiry not Stop expiry');await f.c.command('stop');ok(f.calls.at(-1).body[7]===h.id,'expired observer Stop');}
 {const f=await paired(),h=await start(f);f.set(2);await f.c.poll();ok(f.c.authority==='normal'&&!f.c.handoffIntent&&f.c.stopBinding.id===h.id,'adoption retains key');await f.c.pulse();ok(f.calls.at(-1).op==='renew','existing normal renewal');f.c.visible(false);f.c.visible(true);await assert.rejects(f.c.command('acquire'));await f.c.command('stop');ok(f.calls.at(-1).body[7]===h.id,'adopted then hidden Stop');}
 {const f=await paired(),h=await start(f);await f.c.pair('a'.repeat(32));ok(f.c.credential==='c'.repeat(32),'explicit second session');await f.c.poll();await assert.rejects(f.c.command('maintenance'));ok(f.c.stopRecoveryOnly(),'new pair no movement');await f.c.command('stop');ok(f.calls.at(-1).credential==='b'.repeat(32)&&f.calls.at(-1).body[7]===h.id,'pair cannot replace origin Stop');}
 await prebinding();
 {const f=await paired(),h=await start(f);f.c.clear();let oldRelease,newRelease;let n=0;f.poll(()=>new Promise(r=>{if(n++===0)oldRelease=r;else newRelease=r;}));const old=f.c.poll(),latest=f.c.poll();f.set(1,'2');newRelease(f.status());await latest;f.set(4,'4');oldRelease(f.status());await old;ok(f.c.stopBinding?.id===h.id&&f.c.snapshot.phase===1,'OLDER_COMPLETION_IGNORED');}
 for(const [phase,g,axis] of [[0,'1',1],[1,'2',1],[2,'3',1],[3,'3',1],[3,'4',1],[4,'0',1],[4,'4',2]]){const f=await paired(),h=await start(f);f.c.clear();f.set(phase,g,axis);await f.c.poll();ok(f.c.stopBinding?.id===h.id,'wrong terminal witness '+[phase,g,axis]);}
 for(const g of ['2','3','4']){const f=await paired();await start(f);f.c.disconnect();f.set(4,g);await f.c.poll();ok(!f.c.stopBinding&&f.c.snapshot.stop_verified,'all shorter/direct terminal paths '+g);}
 {const f=await paired();f.set(0,'18446744073709551615');await f.c.poll();await start(f);f.c.disconnect();f.set(4,'18446744073709551615');await f.c.poll();ok(!f.c.stopBinding,'saturated Terminal');}
 {const f=await paired(),h=await start(f);f.set(4,'4');f.c.update(f.status());ok(f.c.stopBinding?.id===h.id,'direct update cannot authenticate retirement');await f.c.poll();ok(!f.c.stopBinding,'authenticated poll');}
 {const f=await paired();await start(f);f.c.disconnect();f.set(0,'1',1,'12');await f.c.poll();ok(!f.c.stopBinding&&f.c.authority==='','new authenticated boot retires without authority');}
 {const f=await paired();f.fail('handoff-acquire');await assert.rejects(f.c.transferAndAcquire());const id=f.calls.at(-1).body[4];ok(f.c.stopBinding?.id===id&&!f.c.handoffIntent,'unknown/rejected send retains key');f.fail('');await f.c.command('stop');ok(f.calls.at(-1).body[7]===id,'Boot no-reservation Stop binding');}
 {const f=await paired();await start(f);f.set(2);f.mutate(r=>({...r,transfer_id:'99'}));await assert.rejects(f.c.poll());ok(!!f.c.stopBinding&&f.c.authority==='','malformed receipt not Stop cancellation');}
 {const f=await paired();await start(f);f.c.disconnect();f.poll(()=>Promise.reject(Error('network')));await assert.rejects(f.c.poll());ok(!!f.c.stopBinding&&f.c.canStop(),'recovery errors retain key');}
 console.log('STOP CAPABILITY JS PASS checks='+checks+'; actual production JS, mock authenticated status/transport; hardware NOT_RUN');
})().catch(e=>{console.error(e);process.exitCode=1;});
