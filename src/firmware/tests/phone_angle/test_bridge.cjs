'use strict';
const assert=require('node:assert/strict');const {spawn}=require('node:child_process');const readline=require('node:readline');
const {PhoneControl}=require('../../components/robot_phone/web/app.js');
let checks=0;const ok=x=>{++checks;assert.ok(x);};
async function scenario(axis,measured,unit,negative){
 const p=spawn(process.argv[2],['--bridge',String(axis),String(measured)],{stdio:['pipe','pipe','inherit']});
 const lines=readline.createInterface({input:p.stdout});const waiting=[];let failure=null;
 lines.on('line',line=>{const job=waiting.shift();if(job){try{job.resolve(JSON.parse(line));}catch(e){job.reject(e);}}});
 p.on('exit',code=>{if(code){failure=Error('bridge exit '+code);for(const w of waiting.splice(0))w.reject(failure);}});
 const request=line=>new Promise((resolve,reject)=>{if(failure)return reject(failure);waiting.push({resolve,reject});p.stdin.write(line+'\n');});
 let now=0;const bytes=[];
 const c=new PhoneControl(async(path,opts)=>{if(path==='/api/session')return{wire_error:0,credential:'b'.repeat(32)};if(path==='/api/status'){const s=await request('S');now=Number(s.at);return s;}bytes.push(opts.body);return request('C '+opts.body);},()=>now);
 try{
  await c.pair('a'.repeat(32));await c.poll();ok(c.snapshot.angle_available===measured);await c.command('acquire');
  let angle=axis===1?(unit==='deg'?'0.4166666666666667':'0.00727220521664304'):(unit==='deg'?'1.25':'0.02181661564992912');if(negative)angle='-'+angle;
  if(!measured){await assert.rejects(c.moveAngle(angle,unit));ok(!bytes.some(b=>b.startsWith('v2|')));
   await c.command('arm');await c.command('ticket');const body=['v2',c.snapshot.boot,c.snapshot.generation,(++c.seq).toString(),c.seq.toString(),'joint-step',c.lease,c.ticket,axis,axis,unit,angle].join('|');const r=await request('C '+body);ok(r.wire_error!==0||r.core_error!==0);ok((await request('M')).moves===0);return;}
  await c.moveAngle(angle,unit);ok(bytes.at(-1).startsWith('v2|'));ok((await request('M')).moves===1);
  await c.poll();ok(c.snapshot.angle_available&&!c.snapshot.ready);const lease=c.lease;const owner=c.snapshot.lease_owner;
  for(let n=0;n<12;++n){await request('T 200');await c.poll();ok(c.lease===lease&&c.authority==='normal');await c.pulse();if(n>=3&&c.snapshot.ready)break;}
  await c.poll();ok(c.snapshot.ready&&c.snapshot.angle_available);ok(c.snapshot.lease_owner===owner);ok(c.snapshot.core_fault===0);ok(bytes.filter(b=>b.split('|')[5]==='renew').length>=3);
  await request('R');await c.poll();ok(!c.snapshot.angle_available);await assert.rejects(c.moveAngle(angle,unit));ok((await request('M')).moves===1);
 }finally{p.stdin.end();await new Promise(resolve=>p.once('exit',resolve));}
}
(async()=>{for(const axis of [1,2])for(const unit of ['deg','rad'])for(const negative of [false,true])await scenario(axis,true,unit,negative);await scenario(1,false,'deg',false);console.log(`ANGLE BRIDGE PASS checks=${checks}; actual PhoneControl bytes->parse->Owner->Boot/Run->Gate/codec->FakeCAN; transport/pair-response stub, fixture boot/pairing actual; network=NOT_RUN`);})().catch(e=>{console.error(e);process.exitCode=1;});
