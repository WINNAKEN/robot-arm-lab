'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');const dir=process.argv[2],epoch=1000000000000;let checks=0;const check=(v,m)=>{++checks;assert.ok(v,m);};
for(const file of fs.readdirSync(dir).filter(x=>x.endsWith('.json')&&x!=='summary.json')){
 const r=JSON.parse(fs.readFileSync(path.join(dir,file),'utf8'));check(r.result==='PASS','positive report');let t=0;
 for(const e of r.events){if(e.text.startsWith('W ')){const next=Number(e.text.slice(2));check(next>=t&&Number(e.result.at)===next,'native exact monotone W');t=next;}
 else if(['P','M','F'].includes(e.text))check(Number(e.result.at)===t,'native publication is current clock');
 else if(['J','N','X'].includes(e.text[0])&&e.result.ready&&e.result.accepted_at!==undefined)check(Number(e.result.accepted_at)===t,'submit did not secretly advance native clock');}
 for(const d of r.drains)check(d.browser_date===epoch+d.at,'browser/native clock parity');
 const used=new Set(),entries=r.requests.filter(e=>e.api&&e.method!=='OPTIONS');
 for(const o of r.observed){const pathname=new URL(o.url,'http://fixture').pathname;const e=entries.find(e=>!used.has(e.id)&&e.path===pathname&&e.body===o.body&&e.at===o.at-epoch);
  if(!e){check(!!o.fetchRejected&&r.name.startsWith('offline'),'unmatched fetch is declared offline rejection');continue;}used.add(e.id);
  if(e.sent&&!o.fetchRejected){check(o.fetchAt===epoch+e.replyAt,'fetch settlement at declared reply boundary');if(o.jsonDone)check(o.jsonAt===epoch+e.replyAt,'JSON consumed at declared reply boundary');}
  if(r.name.startsWith('normal')&&e.sent)check(e.at===e.coreAt&&e.at===e.replyAt,'normal transport logical latency exactly0');
 }
 check(r.metrics.moves===0&&!r.metrics.frames.some(f=>f.data[0]===0xFD),'no movement injected');check(r.cold.paired_mask===0&&r.cold.at==='0','fresh Owner');
 console.log('AUDIT PASS '+r.name);
}
console.log('CLOCK/TRANSPORT AUDIT PASS checks='+checks+'; raw native/browser trace consistency, not new runtime coverage');
