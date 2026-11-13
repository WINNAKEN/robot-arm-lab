'use strict';
const assert=require('node:assert/strict'),{Readable}=require('node:stream');
const {Fixture}=require('./fixture.cjs'),{owned,explicitStop,serviceObstruction}=require('./oracle.cjs');
let checks=0;function ok(v,label){++checks;assert.ok(v,label);}
const pre={boot:'11',generation:'1',selected_axis:1,phase:0,stop_at:'0',fault_at:'0',core_fault:0,adapter_fault:0};
const native={ready:true,wire_error:0,core_error:0,accepted_at:'20'};
const audit={pre_phase:0,pre_stop:0,pre_fault:0,pre_adapter:0,accepted:20,post_stop:20};
const post={...pre,generation:'2',phase:3,stop_at:'20',positions:[{value:'0'}]};
const make=()=>JSON.parse(JSON.stringify({before:pre,result:native,audit,post}));
function deferred(){let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j;});return{promise,resolve,reject};}
async function wait(fn){for(let n=0;n<50;++n){if(fn())return;await new Promise(r=>setImmediate(r));}throw Error('unit condition timeout');}
async function publication(failure=''){
 const f=Object.create(Fixture.prototype),t=deferred(),p=deferred();let sawT=false,sawPost=false,sends=0;
 Object.assign(f,{requests:[],mode:'baseline',control:'',sessions:new Set(),elapsed:()=>1});
 const result={...native},meta={...audit},status=JSON.parse(JSON.stringify(post));let reads=0;
 f.rpc=async text=>{if(text==='P'){if(++reads===1)return{...pre};sawPost=true;return p.promise;}if(text==='T'){sawT=true;return t.promise;}return result;};
 f.send=(entry,code,value)=>{++sends;entry.sent=true;assert.equal(code,200);assert.equal(value,entry.completed.result);};
 const req=Readable.from(['v1|11|1|1|1|stop|0|0|1|0|0']);req.url='/api/stop';req.method='POST';req.headers={'x-session-credential':'b'.repeat(32)};
 const running=f.handle(req,{});const settled=running.then(()=>null,e=>e);
 await wait(()=>sawT);const entry=f.requests[0];ok(!entry.completed&&!('result' in entry)&&!('audit'in entry),'no partial publication after native result');ok(sends===0,'no HTTP before audit');
 if(failure==='T'){t.reject(Error('audit unavailable'));ok((await settled).message==='audit unavailable','T error propagated');ok(!entry.completed&&sends===0,'T failure no completion');return;}
 t.resolve(meta);await wait(()=>sawPost);ok(!entry.completed&&sends===0,'no partial publication before post status');
 if(failure==='P'){p.reject(Error('post unavailable'));ok((await settled).message==='post unavailable','post error propagated');ok(!entry.completed&&sends===0,'post failure no completion');return;}
 p.resolve(status);ok(await settled===null,'handle completes');const c=entry.completed;
 ok(sends===1&&Object.isFrozen(c)&&Object.isFrozen(c.result)&&Object.isFrozen(c.audit)&&Object.isFrozen(c.post.positions[0]),'owned deep immutable completion');
 result.accepted_at='999';meta.pre_stop=999;status.positions[0].value='999';
 ok(c.result.accepted_at==='20'&&c.audit.pre_stop===0&&c.post.positions[0].value==='0','RPC aliases cannot mutate completion');
 ok(explicitStop(pre,c),'actual fixture completion consumed by common oracle');
}
(async()=>{
 ok(explicitStop(pre,make()),'normal causal data accepted');
 for(const [label,mutate] of [
  ['missing forward post.stop0',c=>{c.post.stop_at='0';c.result.accepted_at='19';}],
  ['prior stop',c=>c.before.stop_at='1'],['audit absent',c=>delete c.audit],
  ['native prior fault',c=>c.audit.pre_fault=8],['wrong boot',c=>c.post.boot='12'],
  ['wrong axis',c=>c.post.selected_axis=2],['wrong generation',c=>c.post.generation='3'],
  ['wrong accepted',c=>c.result.accepted_at='21'],['auth rejected',c=>c.result.wire_error=2]
 ]){const c=make();mutate(c);ok(!explicitStop(pre,c),label);}
 const omission=make();omission.post.stop_at='0';ok(!explicitStop(pre,omission),'gap999 cannot change causal predicate');
 const time={...pre,phase:4,core_fault:8,stop_at:'18',fault_at:'18'};
 ok(serviceObstruction(time,{max_gap:18}),'actual Time fault with gap classified');
 ok(!serviceObstruction(time,{max_gap:9}),'Time fault without measured gap not environment');
 ok(!serviceObstruction({...time,core_fault:11},{max_gap:18}),'proof fault not environment');
 ok(!serviceObstruction({...time,fault_at:'19'},{max_gap:18}),'unbound prior fault not environment');
 ok(!serviceObstruction(pre,{max_gap:999}),'cumulative gap alone not environment');
 ok(!serviceObstruction(null,{max_gap:999}),'missing status not environment');
 const x={nested:{v:1}},frozen=owned(x);x.nested.v=2;ok(frozen.nested.v===1&&Object.isFrozen(frozen.nested),'owned copy helper');
 await publication();await publication('T');await publication('P');
 console.log('PASS observer publication/data-oracle/environment checks='+checks+'; deferred unit RPC, NOT wall-time acceptance');
})().catch(e=>{console.error(e);process.exitCode=1;});
