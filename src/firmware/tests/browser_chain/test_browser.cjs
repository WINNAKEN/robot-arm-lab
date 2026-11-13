'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Fixture}=require('./fixture.cjs'),observer=require('./observer.cjs');
const [exe,output]=process.argv.slice(2),out=path.resolve(output);fs.mkdirSync(out,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),epoch=1000000000000;let checks=0;const ok=(v,m)=>{++checks;assert.ok(v,m);};
const good=e=>e.result&&e.result.wire_error===0&&e.result.core_error===0;
async function scenario(browser,mode,axis=1,control=''){
 const startChecks=checks;const f=new Fixture(exe,axis,mode,control),name=mode+'-axis'+axis+(control?'-'+control:''),report={name,result:'RUNNING',scope:'LIVE_UNCHANGED_DOM_HTTP_FIXTURE_ACTUAL_OWNER_FAKECAN; CONTROLLED_SHARED_CLOCK; selected zero-logical-latency schedule; NOT real-time WiFi/fullPB/physical'};
 let context,page,allowReject=false,seenJs='',seenHtml='';const blocked=[],pageErrors=[],drains=[],redirects=[];
 const fence=()=>page.evaluate(()=>window.__chainFence());
 async function drain(){
  const start=Date.now();for(let n=0;Date.now()-start<4000;++n){if(f.failure)throw f.failure;await f.flush();await fence();const observed=await page.evaluate(()=>window.__chainObserved());
   const entries=f.requests.filter(e=>e.api&&e.method!=='OPTIONS'),used=new Set();let settled=true;
   for(const r of observed){const p=new URL(r.url,f.origin).pathname;const e=entries.find(e=>!used.has(e.id)&&e.path===p&&e.body===r.body&&e.at===r.at-epoch);
    if(!e){if(!(allowReject&&r.fetchRejected))settled=false;continue;}
    used.add(e.id);if(r.fetchRejected&&!allowReject)throw Error('unexpected transport rejection '+p);
    if(e.sent&&!(r.fetchDone&&(r.fetchRejected||r.ok===false||r.jsonDone)))settled=false;
    if(!e.sent&&!f.pendingNative.includes(e)&&!f.work.some(w=>w.entry===e&&w.due>f.now))settled=false;
   }
   if(used.size!==entries.length)settled=false;
   if(settled){await fence();const again=await page.evaluate(()=>window.__chainObserved());if(again.length!==observed.length)continue;
    const date=await page.evaluate(()=>Date.now());assert.equal(date,epoch+f.now,'CLOCK_PARITY');drains.push({at:f.now,browser_date:date,fetch_count:again.length,http_count:entries.length,future_replies:f.work.length,native_pending:f.pendingNative.length});return;
   }
   await new Promise(r=>setTimeout(r,1));
  }
  const observed=await page.evaluate(()=>window.__chainObserved());throw Error('drain wall timeout '+JSON.stringify({at:f.now,observed,requests:f.requests.filter(e=>e.api).map(({res,credential,pairing,...e})=>e),work:f.work.map(w=>({due:w.due,kind:w.kind,id:w.entry.id}))}));
 }
 async function advance(ms){const target=f.now+ms;while(f.now<target){const delta=Math.min(target-f.now,50-f.now%50,f.nextDue()-f.now);assert.ok(delta>0);const next=f.now+delta;const r=await f.rpc('W '+next);assert.equal(Number(r.at),next);f.now=next;await page.clock.runFor(delta);await drain();}}
 const state=()=>f.rpc('P'),metrics=()=>f.rpc('M');
 async function until(fn,label,limit=6000,step=50){const end=f.now+limit;while(f.now<=end){if(await fn())return;if(f.now===end)break;await advance(Math.min(step,end-f.now));}throw Error('virtual timeout '+label+' at '+f.now);}
 async function actionable(selector){return page.locator(selector).evaluate(el=>{const r=el.getBoundingClientRect();return !el.disabled&&r.width>0&&r.height>0;});}
 async function tap(selector,slot=false){const el=page.locator(selector);await el.evaluate(e=>e.scrollIntoView({block:'center'}));
  if(slot)await until(async()=>{const m=await metrics();return m.operator_slot&&await actionable(selector);},'first observable enabled slot '+selector,2500,1);
  else await until(()=>actionable(selector),'enabled '+selector,1000,1);
  const box=await el.boundingBox();ok(!!box,'DOM_BOX '+selector);const point={x:box.x+box.width/2,y:box.y+box.height/2};
  ok(await el.evaluate((e,p)=>{const hit=document.elementFromPoint(p.x,p.y);return !e.disabled&&(hit===e||e.contains(hit));},point),'DOM_HIT '+selector);
  await page.touchscreen.tap(point.x,point.y);await drain();
 }
 async function op(name,slot=true,expectGood=true){const before=f.requests.length;await tap('[data-op="'+name+'"]',slot);await until(()=>f.requests.slice(before).some(e=>e.op===name&&e.sent),'one response '+name,120,1);
  const rows=f.requests.slice(before).filter(e=>e.op===name);ok(rows.length===1,'EXPLICIT_ONCE '+name);if(expectGood)ok(good(rows[0]),'COMMAND_ACCEPTED '+name+' '+JSON.stringify(rows[0].result));return rows[0];}
 try{
  await f.begin();context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});await context.addInitScript(observer);
  await context.route('**/*',async route=>{const request=route.request(),url=request.url();if(url.startsWith(f.origin+'/')){await route.continue();return;}if(url==='http://192.168.4.1:8081/api/stop'){
   redirects.push({at:f.now,method:request.method(),url});try{const response=await route.fetch({url:f.origin+'/api/stop',timeout:4000});await route.fulfill({response});}catch{await route.abort().catch(()=>{});}return;
  }blocked.push(url);await route.abort();});
  page=await context.newPage();page.on('pageerror',e=>pageErrors.push(String(e)));page.on('response',async r=>{try{if(r.url()===f.origin+'/app.js')seenJs=sha(await r.body());if(r.url()===f.origin+'/')seenHtml=sha(await r.body());}catch{}});
  await page.clock.install({time:epoch-1000});await page.clock.pauseAt(epoch);await page.goto(f.origin+'/',{waitUntil:'load'});await drain();
  const assetWait=Date.now();while((!seenJs||!seenHtml)&&Date.now()-assetWait<3000)await new Promise(r=>setTimeout(r,1));
  ok(!!seenJs&&!!seenHtml,'ASSETS_RECEIVED_BEFORE_IDENTITY');report.actual_app_sha256=seenJs;report.actual_html_sha256=seenHtml;report.expected_app_sha256=sha(f.js);report.expected_html_sha256=sha(f.html);report.browser=browser.version();
  ok(seenJs===sha(f.js)&&seenHtml===sha(f.html),'ASSET_IDENTITY');
  await page.locator('#pairing').fill((mode==='bad-pair'?'d':'a').repeat(32));await tap('#pair');
  const paired=f.requests.find(e=>e.op==='pair');ok(!!paired,'ACTUAL_OWNER_PAIR_REQUEST');
  if(mode==='bad-pair'){ok(paired.result.wire_error===2&&(await metrics()).paired_mask===0,'ACTUAL_OWNER_PAIR_DENIED');ok(await page.locator('#stop').isDisabled(),'NO_UNPAIRED_STOP');}
  else{
   ok(paired.result.paired&&paired.result.credential.length===32,'ACTUAL_OWNER_PAIR_RETURNED_SESSION');
   await until(async()=>(await page.locator('#status').textContent()).includes('core state 3 · fault 0'),'observed NeedsMaintenance DOM');
   await op('maintenance');await op('unloaded',false);const disable=await op('disable-all');
   await advance(200);await op('unloaded',false);
   await until(async()=>(await page.locator('#status').textContent()).includes('core state 4 · fault 0'),'actual ReadyDisabled DOM');
   await op('finish-maintenance');await op('drive');
   const enabled=await op('enable-selected',true,mode!=='queue-age');
   if(mode==='queue-age'){
    ok(enabled.result.wire_error===8&&enabled.queueDelay===50,'EXACT_QUEUE_AGE_REJECTED');ok(f.requests.filter(e=>e.op==='enable-selected').length===1,'NO_QUEUE_RETRY');
    await op('stop',false);const stopped=await state();ok(BigInt(stopped.stop_at)>0n&&Number(stopped.phase)>=3,'EXPLICIT_STOP_REACHED_CORE');
   }else{
    await until(async()=>(await page.locator('#status').textContent()).includes('core state 8 · fault 0'),'actual Granted DOM');
    // Explicit operator dwell, with real browser renewal callbacks under shared clock.
    await advance(600);if(mode==='hidden-stop')f.delays=true;
    await tap('#handoff',true);const combined=f.requests.find(e=>e.op==='handoff-acquire');await until(()=>combined?.result,'actual combined result',100,1);
    const after=await state();ok(good(combined)&&(after.phase===1||after.phase===2)&&after.generation!=='1','HANDOFF_REACHED_CORE');
    if(mode==='hidden-stop'){
     ok((await metrics()).transfer_attempts===0,'PENDING_BEFORE_STOP');report.visibility='synthetic visibilitychange + document.hidden getter; NOT OS background';
     await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});
     await op('stop',false);const stopped=await state(),stop=f.requests.find(e=>e.op==='stop');ok(BigInt(stopped.stop_at)>0n&&Number(stopped.stop_at)===stop.coreAt,'EXPLICIT_STOP_REACHED_CORE');ok(stop.body.split('|')[7]===combined.body.split('|')[4],'RETAINED_DOM_STOP_ID');
     await advance(1300);ok((await metrics()).transfer_attempts===0,'NO_GRANT_AFTER_PENDING_STOP');
    }else if(mode==='offline'){
     allowReject=true;await context.setOffline(true);await fence();await drain();await advance(1300);const m=await metrics(),s=await state();ok(m.transfer_attempts<=1&&BigInt(s.stop_at)>0n,'SERVER_EXPIRY_AFTER_OFFLINE');ok(!f.requests.some(e=>e.op==='renew'||e.op==='acquire'),'NO_OFFLINE_RENEW_OR_ACQUIRE');await context.setOffline(false);
    }else if(mode==='late-receipt'){
     await until(()=>f.requests.some(e=>e.op==='handoff-result'&&e.result?.transfer_state===2),'held real grant receipt');await advance(1600);ok(BigInt((await state()).stop_at)>0n,'ORIGINAL_LEASE_EXPIRED');ok(!f.requests.some(e=>e.op==='renew'||e.op==='acquire'),'NO_LATE_RECEIPT_AUTHORITY');
    }else{
     await until(()=>f.requests.some(e=>e.op==='handoff-result'&&e.sent&&e.result.transfer_state===2),'actual private grant delivered');ok((await metrics()).transfer_attempts===1,'ONE_INTERNAL_ACQUIRE');
     await until(()=>f.requests.filter(e=>e.op==='renew'&&good(e)).length>=2,'actual normal Renew');
     ok((await state()).angle_available===false&&await page.locator('#angle-send').isDisabled(),'RUN_CALIBRATION_UNAPPROVED');
     const stop=await op('stop',false);const s=await state();ok(BigInt(s.stop_at)>0n&&Number(s.stop_at)===stop.coreAt,'EXPLICIT_STOP_REACHED_CORE');
    }
   }
   await until(async()=>{const s=await state();return s.phase===4&&s.stop_verified;},'actual verified Terminal',6000,50);
   await until(async()=>/(?:^|\n)stop_verified=true(?:\s|$)/.test(await page.locator('#last-stop-outcome').textContent()),'live native historical DOM',3000,50);
   const history=await page.locator('#last-stop-outcome').textContent(),origin=await state();report.history=history;ok(history.includes('부팅 '+origin.boot+' / generation '+origin.generation),'HISTORY_SAME_NATIVE_NAMESPACE');ok(history.includes('stop_at='+origin.stop_at+' /'),'HISTORY_SAME_NATIVE_STOP');ok(history.includes('과거 관측'),'HISTORICAL_LABEL');allowReject=true;await context.setOffline(true);await fence();await drain();
   ok((await page.locator('#last-stop-outcome').textContent())===history,'FINAL_HISTORY_SURVIVES_OFFLINE');ok(await page.locator('#angle-send').isDisabled(),'CALIBRATION_UNAPPROVED_DOM');
   report.boot_disable_accepted_at=disable.result.accepted_at;
  }
  const final=await state(),frames=await f.rpc('F');ok(frames.moves===0&&frames.frames.every(r=>r.data[0]!==0xFD),'FD_ZERO');ok(frames.calibration_measured===false,'NO_MEASURED_PROFILE');
  if(mode!=='bad-pair'){
   const on=frames.frames.filter(r=>r.data[0]===0xF3&&r.data[1]===1),off=frames.frames.filter(r=>r.data[0]===0xF3&&r.data[1]===0);ok(mode==='queue-age'?on.length===0:on.length===1&&on[0].axis===axis,'SELECTED_AXIS_ENABLE_ONLY');ok(off.some(r=>r.axis===1)&&off.some(r=>r.axis===2),'ALL_AXIS_DISABLE_FRAMES');
  }
  ok(pageErrors.length===0&&blocked.length===0,'NO_UNEXPECTED_BROWSER_ERROR');report.final=final;report.metrics=frames;report.result='PASS';report.checks=checks-startChecks;
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});console.log('CHAIN PASS '+name+' at='+f.now);
 }catch(e){report.result='FAIL';report.error=String(e);if(page)await page.screenshot({path:path.join(out,name+'-FAIL.png'),fullPage:true}).catch(()=>{});throw e;}
 finally{if(page)report.observed=await page.evaluate(()=>window.__chainObserved?.()).catch(()=>null);if(context)await context.close().catch(()=>{});await f.close();Object.assign(report,f.report(),{drains,redirects,page_errors:pageErrors,blocked});fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(report,null,2));}
 return report;
}
(async()=>{const browser=await chromium.launch({executablePath:process.env.PB_BROWSER,headless:true,args:['--disable-background-networking']});try{
 const selected=process.argv.find(x=>x.startsWith('--case='))?.slice(7);const modes=selected?[selected]:['normal','normal-axis2','hidden-stop','offline','late-receipt','queue-age','bad-pair'];
 const control=process.argv.find(x=>x.startsWith('--control='))?.slice(10)||'';if(modes.some(m=>!['normal','normal-axis2','hidden-stop','offline','late-receipt','queue-age','bad-pair'].includes(m))||!['','wrong-asset','missing-handoff','missing-stop'].includes(control))throw Error('unknown case/control');const results=[];
 for(const m of modes)results.push(await scenario(browser,m==='normal-axis2'?'normal':m,m==='normal-axis2'?2:1,control));fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify({checks,result:'PASS',scope:'CONTROLLED_CLOCK_BOOT_HANDOFF_STOP_ONLY; real-time/fullPB/hardware OPEN',cases:results.map(r=>r.name)},null,2));console.log('CHAIN SUITE PASS checks='+checks);
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
