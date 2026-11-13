'use strict';
// Run the actual current browser consumer block, with deterministic native inputs.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {completionShape,timeConsistent,explicitStop,serviceObstruction,EnvironmentObstruction}=require('./oracle.cjs');
const source=fs.readFileSync(path.join(__dirname,'test_browser.cjs'),'utf8');
const begin=source.indexOf('    const c=stop.completed,a=c?.audit;'),end=source.indexOf("    if(mode==='held-replies')",begin);
assert.ok(begin>=0&&end>begin,'unique actual consumer block exists');
const body=source.slice(begin,end),AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const run=new AsyncFunction('stop','before','ok','prerequisite','explicitStop','completionShape','timeConsistent','report',body);
const pre={boot:'11',generation:'1',selected_axis:1,phase:0,stop_at:'0',fault_at:'0',core_fault:0,adapter_fault:0};
const make=()=>({before:{...pre},result:{accepted_at:'20',wire_error:0,core_error:0},
 audit:{pre_phase:0,pre_stop:0,pre_fault:0,pre_adapter:0,accepted:20,post_stop:20},
 post:{...pre,generation:'2',phase:3,stop_at:'20'}});
const time={...pre,phase:4,generation:'2',core_fault:8,stop_at:'18',fault_at:'18'};
const clone=x=>JSON.parse(JSON.stringify(x));const rows=[],recorded=[];
async function check(label,c,gap,want,before=pre){
 const prerequisite=async(s,stage)=>{if(serviceObstruction(s,{max_gap:gap}))throw new EnvironmentObstruction(stage,s,{max_gap:gap});return s;};
 let result='PASS',error;
 try{await run({completed:c},before,(v,l)=>assert.ok(v,l),prerequisite,explicitStop,completionShape,timeConsistent,{});}catch(e){error=String(e);result=e instanceof EnvironmentObstruction?'ENV_SERVICE_VIOLATION':'FAIL';}
 rows.push({label,result,error});assert.equal(result,want,label);
}
(async()=>{
 await check('actual positive',make(),1,'PASS');
 await check('post-terminal cumulative gap does not erase positive',make(),99,'PASS');
 const validTime=make();validTime.before={...time};validTime.post={...time};validTime.audit={pre_phase:4,pre_stop:18,pre_fault:8,pre_adapter:0,accepted:20,post_stop:18};
 await check('well-formed actual prior Time may obstruct',validTime,18,'ENV_SERVICE_VIOLATION');
 await check('Time without actual measured gap remains FAIL',validTime,9,'FAIL');
 const nativeTime=clone(validTime);nativeTime.before={...pre};await check('Time begins only at native admission',nativeTime,18,'ENV_SERVICE_VIOLATION');
 const contradictoryNative=clone(nativeTime);contradictoryNative.audit.accepted=99;await check('native admission Time cannot hide audit mismatch',contradictoryNative,18,'FAIL');
 const mutators=[
  ['malformed audit',c=>c.audit={}],['malformed post',c=>c.post={}],
  ['invalid accepted stamp',c=>c.result.accepted_at='INVALID'],['missing audit',c=>delete c.audit],
  ['invalid audit scalar',c=>c.audit.pre_stop='0'],['missing before',c=>delete c.before],
  ['wrong namespace',c=>c.post.boot='12'],['wrong selected axis',c=>c.post.selected_axis=2],
  ['rejected authentication',c=>c.result.wire_error=2],['core rejection',c=>c.result.core_error=8],
  ['mismatched accepted audit',c=>c.audit.accepted=99],['contradictory native pre-state',c=>c.audit.pre_stop=17],
  ['wrong post generation',c=>c.post.generation='999'],['wrong before generation',c=>c.before.generation='999'],
  ['backdated accepted time',c=>{c.result.accepted_at='1';c.audit.accepted=1;}]
 ];
 for(const [label,mutate] of mutators){
  const c=make();mutate(c);await check(label+' clean',c,18,'FAIL');
  const t=clone(validTime);mutate(t);await check(label+' with actual Time preemption',t,18,'FAIL');
 }
 const omit=make();omit.post.stop_at='0';omit.result.accepted_at='19';await check('missing forward common oracle gap99',omit,99,'FAIL');
 assert.ok(!serviceObstruction({...time,boot:undefined},{max_gap:18}),'malformed native status never environment');
 // No network/browser rerun: apply final exact consumer to already-recorded real data.
 for(const directory of process.argv.slice(3)){
  const visit=folder=>{for(const item of fs.readdirSync(folder,{withFileTypes:true})){const p=path.join(folder,item.name);if(item.isDirectory())visit(p);else if(item.name.endsWith('.json')){
   const r=JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
   const stop=r.requests?.find(e=>e.op==='stop'&&e.completed);if(!stop||!r.pre_click)continue;
   if(r.result==='PASS')recorded.push({path:p,pre:r.pre_click,c:stop.completed,gap:r.clock.max_gap,want:'PASS'});
   else if(r.error?.includes('EXPLICIT_STOP_REACHED_CORE'))recorded.push({path:p,pre:r.pre_click,c:stop.completed,gap:r.clock.max_gap,want:'FAIL'});
  }}};visit(directory);
 }
 for(const r of recorded){await check('recorded actual data '+r.path,r.c,r.gap,r.want,r.pre);}
 if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify({source_block:body,checks:rows.length+1,rows},null,2));
 console.log('PASS actual consumer/schema priority checks='+(rows.length+1)+'; deterministic inputs, NOT wall-time acceptance');
})().catch(e=>{console.error(e);process.exitCode=1;});
