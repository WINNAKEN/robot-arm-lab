'use strict';
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const readline=require('node:readline');
const {PhoneControl}=require(process.env.INTENT_JS||'../../components/robot_phone/web/app.js');
let checks=0;const ok=x=>{++checks;assert.ok(x);};
async function scenario(axis,measured,mode){
  const processBridge=spawn(process.argv[2],[String(axis),String(measured)],{stdio:['pipe','pipe','inherit']});
  const queue=[];let failed=null;
  const exited=new Promise(resolve=>processBridge.once('exit',code=>{failed=Error('bridge exit '+code);for(const p of queue.splice(0))p.reject(failed);resolve(code);}));
  processBridge.once('error',error=>{failed=error;for(const p of queue.splice(0))p.reject(error);});
  readline.createInterface({input:processBridge.stdout}).on('line',line=>{
    const pending=queue.shift();if(!pending)return;
    try{pending.resolve(JSON.parse(line));}catch(error){pending.reject(error);}
  });
  const request=line=>new Promise((resolve,reject)=>{if(failed)return reject(failed);queue.push({resolve,reject});processBridge.stdin.write(line+'\n');});
  const bytes=[],phases=[];let now=0,holdAck=false,releaseAck;
  const c=new PhoneControl(async(path,options)=>{
    if(path==='/api/session')return {wire_error:0,credential:'b'.repeat(32)};
    if(path==='/api/status'){const s=await request('S');now=Number(s.at);phases.push(s.phase);return s;}
    bytes.push(options.body);const result=await request('C '+options.body);
    if(result.wire_error||result.core_error){const trace={axis,measured,mode,body:options.body,result,snapshot:c.snapshot,actual:await request('S')};if(mode==='boundary')console.log('EXPECTED_ADMISSION_DENIAL '+JSON.stringify(trace));else console.error(JSON.stringify(trace));}
    if(holdAck&&options.body.split('|')[5]==='handoff')await new Promise(resolve=>{releaseAck=resolve;});
    return result;
  },()=>now);
  const tick=async(n=20)=>{await request('T '+n);await c.poll();await c.pulse();};
  const until=async predicate=>{for(let n=0;n<1800&&!predicate();++n)await tick(c.handoffIntent&&mode!=='boundary'?1:20);ok(predicate());};
  try{
    await c.pair('a'.repeat(32));await c.poll();ok(c.snapshot.phase===0&&c.snapshot.core_state===3);
    // Entire boot namespace is created by the actual JS, not by injecting seq/lease.
    await c.command('maintenance');await c.command('unloaded',{unloaded:true});await c.command('disable-all');
    await until(()=>c.snapshot.core_state===4);
    await c.command('finish-maintenance');await c.command('drive');await c.command('enable-selected');
    await until(()=>c.snapshot.core_state===8);for(let n=0;n<30;++n)await tick();
    ok(c.snapshot.phase===0&&c.authority==='boot');
    holdAck=mode==='delayed'||mode==='stop';
    const handoff=c.handoffAndAcquire();const handoffOutcome=handoff.then(()=>null,e=>e);
    // Synchronize the intentionally delayed transport with the actual C++ result.
    if(holdAck){for(let n=0;n<30&&!releaseAck;++n)await new Promise(resolve=>setImmediate(resolve));ok(typeof releaseAck==='function');}
    else await handoff;
    await c.poll();ok(phases.includes(1)||c.snapshot.phase===2);
    if(mode==='stop'){
      await c.command('stop');ok(c.busy);releaseAck();await handoffOutcome;await c.poll();
      ok(!bytes.some(b=>b.split('|')[5]==='acquire'));ok(!c.handoffIntent&&c.authority==='');ok((await request('M')).moves===0);return;
    }
    if(holdAck){await until(()=>c.snapshot.phase===2&&c.snapshot.ready);ok(c.handoffIntent&&c.busy);ok(!bytes.some(b=>b.split('|')[5]==='acquire'));releaseAck();await handoffOutcome;await c.poll();}
    if(mode==='boundary'){
      let failure;try{await until(()=>c.authority==='normal');}catch(error){failure=error;}
      ok(failure instanceof Error&&failure.message==='rejected wire=11 core=12');
      ok(bytes.filter(b=>b.split('|')[5]==='acquire').length===1);ok(c.authority===''&&!c.handoffIntent);
      await c.poll();ok(bytes.filter(b=>b.split('|')[5]==='acquire').length===1);ok((await request('M')).moves===0);return;
    }
    await until(()=>c.snapshot.phase===2&&c.snapshot.ready&&c.authority==='normal');
    await c.poll();ok(bytes.filter(b=>b.split('|')[5]==='acquire').length===1);ok(!c.handoffIntent);ok(c.snapshot.angle_available===measured);
    if(!measured){await assert.rejects(c.moveAngle('0.4166666666666667','deg'));ok((await request('M')).moves===0);return;}
    await c.moveAngle(axis===1?'0.4166666666666667':'0.02181661564992912',axis===1?'deg':'rad');
    ok((await request('M')).moves===1);await c.poll();ok(!c.snapshot.ready&&c.snapshot.angle_available);
    const lease=c.lease;for(let n=0;n<12;++n){await tick(200);ok(c.lease===lease&&c.authority==='normal');if(n>=3&&c.snapshot.ready)break;}
    ok(c.snapshot.ready&&c.snapshot.core_fault===0);ok(bytes.filter(b=>b.split('|')[5]==='renew').length>=3);
    await request('R');await c.poll();ok(!c.snapshot.angle_available&&c.authority==='');await assert.rejects(c.moveAngle('1','deg'));ok((await request('M')).moves===1);
  }finally{
    processBridge.stdin.end();const code=await exited;assert.equal(code,0);
  }
}
(async()=>{
  for(const axis of [1,2])for(const measured of [false,true])await scenario(axis,measured,'normal');
  await scenario(1,true,'delayed');await scenario(1,true,'stop');
  await scenario(2,false,'boundary');
  console.log(`INTENT BRIDGE PASS checks=${checks}; actual JS Boot namespace->Owner Handoff/Acquire->typed angle->Gate/codec/FakeCAN; transport/pair response stub; hardware/network=NOT_RUN`);
})().catch(error=>{console.error(error);process.exitCode=1;});
