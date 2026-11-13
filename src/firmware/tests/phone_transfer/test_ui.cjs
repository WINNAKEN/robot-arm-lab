'use strict';
const assert=require('node:assert/strict');
const {PhoneControl}=require('../../components/robot_phone/web/app.js');
let checks=0;function ok(value){++checks;assert.ok(value);}
function fixture(){
 let now=100,stage=0,hold='',resolve,mutate=x=>x;
 const bodies=[];
 const status=()=>({boot:'11',generation:String(stage+1),at:String(1000+stage),lease_owner:'0',lease_until:'0',config_oldest_at:'1000',fault_at:'0',stop_at:'0',phase:stage,core_state:stage===0?8:stage===1?1:2,core_fault:0,adapter_fault:0,selected_axis:1,ready:false,angle_available:false,angle_joint:0});
 const grant=id=>mutate({wire_error:0,core_error:0,transfer_id:id,transfer_state:2,transfer_generation:'3',lease:'8',accepted_at:'1000',lease_until:'1800',sequence_floor:'1',grant_at:'900',pending_until:'1100'});
 const c=new PhoneControl(async(path,options)=>{
  if(path==='/api/session')return {wire_error:0,credential:'b'.repeat(32)};
  if(path==='/api/status')return status();
  const body=options.body.split('|');bodies.push(body);
  let r={wire_error:0,core_error:0,lease:'0'};
  if(body[5]==='handoff-acquire')r={...r,transfer_id:body[4],transfer_state:1};
  if(body[5]==='handoff-result')r=grant(body[7]);
  if(hold===body[5])await new Promise(done=>{resolve=done;});
  return r;
 },()=>now);
 return {c,bodies,setStage:v=>{stage=v;},setHold:v=>{hold=v;},release:()=>resolve(),setMutation:f=>{mutate=f;},advance:n=>{now+=n;}};
}
async function paired(){const f=fixture();await f.c.pair('a'.repeat(32));await f.c.poll();return f;}
(async()=>{
 {const f=await paired();await f.c.transferAndAcquire();ok(f.c.handoffIntent&&f.c.authority==='');
  f.setStage(1);await f.c.poll();ok(!f.bodies.some(x=>x[5]==='handoff-result'));
  f.setStage(2);await f.c.poll();ok(f.c.authority==='normal'&&f.c.lease==='8'&&!f.c.handoffIntent);
  ok(!f.bodies.some(x=>x[5]==='acquire'));await f.c.pulse();ok(f.bodies.at(-1)[5]==='renew'&&BigInt(f.bodies.at(-1)[3])>1n);
 }
 {const f=await paired();f.setHold('handoff-acquire');const request=f.c.transferAndAcquire();ok(f.c.busy);
  await f.c.command('stop');ok(f.bodies.at(-1)[7]===f.bodies[0][4]&&f.bodies.at(-1)[2]==='1');
  ok(f.c.busy&&!f.c.handoffIntent);f.release();await request;ok(f.c.authority===''&&!f.c.handoffIntent);}
 {const f=await paired();await f.c.transferAndAcquire();f.setStage(2);f.setHold('handoff-result');const query=f.c.poll();
  for(let n=0;n<20&&!f.bodies.some(x=>x[5]==='handoff-result');++n)await new Promise(r=>setImmediate(r));
  ok(f.c.busy);await f.c.command('stop');ok(f.c.busy);f.release();await query;ok(f.c.authority===''&&!f.c.handoffIntent);}
 for(const mutate of [r=>({...r,transfer_id:'99'}),r=>({...r,transfer_generation:'4'}),r=>({...r,sequence_floor:'18446744073709551615'}),r=>({...r,lease_until:'1100'}),r=>({...r,transfer_state:4})]){
  const f=await paired();await f.c.transferAndAcquire();f.setMutation(mutate);f.setStage(2);
  await assert.rejects(f.c.poll());ok(!f.c.handoffIntent&&f.c.authority==='');
 }
 {const f=await paired();await f.c.transferAndAcquire();f.advance(1147);f.setStage(2);await f.c.poll();ok(!f.c.handoffIntent&&f.c.authority==='');}
 {const f=await paired();await f.c.transferAndAcquire();f.c.visible(false);f.setStage(2);await f.c.poll();ok(!f.bodies.some(x=>x[5]==='handoff-result')&&f.c.authority==='');}
 console.log('TRANSFER JS PASS checks='+checks+' actual production PhoneControl; transport/status fixture, not actual Owner');
})().catch(e=>{console.error(e);process.exitCode=1;});
