'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Fixture,sleep}=require('./fixture.cjs');
const {clean,completionShape,timeConsistent,explicitStop,serviceObstruction,EnvironmentObstruction}=require('./oracle.cjs');
const [exe,output,selected='all',control='']=process.argv.slice(2),out=path.resolve(output);fs.mkdirSync(out,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function observe(){
 const list=[],byResponse=new WeakMap(),fetchOriginal=window.fetch,jsonOriginal=Response.prototype.json;
 window.fetch=function(...args){const r={id:list.length+1,url:String(args[0]),body:args[1]?.body||'',start:performance.now()};list.push(r);
  const p=Reflect.apply(fetchOriginal,this,args);p.then(response=>{r.fetchEnd=performance.now();r.ok=response.ok;byResponse.set(response,r);},()=>{r.fetchEnd=performance.now();r.rejected=true;});return p;};
 Response.prototype.json=function(...args){const r=byResponse.get(this),p=Reflect.apply(jsonOriginal,this,args);if(r)p.then(()=>r.jsonEnd=performance.now(),()=>{r.jsonEnd=performance.now();r.jsonRejected=true;});return p;};
 Object.defineProperty(window,'__wallObserved',{value:()=>list.map(r=>({...r})),writable:false});
}
async function scenario(browser,mode,axis,control){
 const f=new Fixture(exe,axis,mode,control),name=mode+'-axis'+axis+(control?'-'+control:''),report={name,result:'RUNNING',scope:'REAL_HOST_WALLTIME_COLD_BOOT_STOP_ONLY; mobile viewport, loopback, actual core, FakeCAN; NOT phone/WiFi/ESP32/normalRun/physical'};
 let context,page,seenJs='',seenHtml='',checks=0;const errors=[],blocked=[];const deadline=Date.now()+20000;
 const watchdog=setTimeout(()=>{report.active_deadline_expired=true;if(context)context.close().catch(()=>{});},20000);
 const ok=(v,label)=>{++checks;assert.ok(v,label);};
 async function until(fn,label,ms=6000){const end=Math.min(deadline,Date.now()+ms);while(Date.now()<end){if(f.failure)throw f.failure;if(await fn())return;await sleep(5);}throw Error('WALL_TIMEOUT '+label);}
 async function tap(selector){const el=page.locator(selector);await el.scrollIntoViewIfNeeded();ok(await el.isEnabled(),'DOM_ENABLED '+selector);const box=await el.boundingBox();ok(!!box,'DOM_BOX '+selector);const x=box.x+box.width/2,y=box.y+box.height/2;
  ok(await el.evaluate((e,p)=>{const hit=document.elementFromPoint(p.x,p.y);return !e.disabled&&(hit===e||e.contains(hit));},{x,y}),'DOM_HIT '+selector);await page.touchscreen.tap(x,y);}
 async function prerequisite(s,stage){const t=await f.rpc('T');if(serviceObstruction(s,t))throw new EnvironmentObstruction(stage,s,t);return s;}
 try{
  await f.begin();context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});await context.addInitScript(observe);
  await context.route('**/*',async route=>{const url=route.request().url();if(url.startsWith(f.origin+'/')){await route.continue();return;}
   if(url==='http://192.168.4.1:8081/api/stop'){try{const response=await route.fetch({url:f.origin+'/api/stop',timeout:4000});await route.fulfill({response});}catch{await route.abort().catch(()=>{});}return;}
   blocked.push(url);await route.abort();});
  page=await context.newPage();page.setDefaultTimeout(2500);page.setDefaultNavigationTimeout(2500);page.on('pageerror',e=>errors.push(String(e)));
  page.on('response',async r=>{try{if(r.url()===f.origin+'/app.js')seenJs=sha(await r.body());if(r.url()===f.origin+'/')seenHtml=sha(await r.body());}catch{}});
  await page.goto(f.origin+'/',{waitUntil:'load'});await until(()=>seenJs&&seenHtml,'asset received');
  report.actual_js=seenJs;report.actual_html=seenHtml;report.expected_js=sha(f.js);report.expected_html=sha(f.html);report.browser=browser.version();
  ok(seenJs===sha(f.js)&&seenHtml===sha(f.html),'ASSET_IDENTITY');
  await page.locator('#pairing').fill((mode==='bad-pair'?'d':'a').repeat(32));await tap('#pair');
  await until(()=>f.requests.some(e=>e.op==='pair'&&e.sent),'actual Pair result');const paired=f.requests.find(e=>e.op==='pair');
  if(mode==='bad-pair'){
   const m=await f.rpc('M');ok(paired.completed.result.wire_error===2&&m.paired_mask===0,'ACTUAL_PAIR_AUTH_REJECTED');ok(await page.locator('#stop').isDisabled(),'UNPAIRED_STOP_DISABLED');
  }else{
   ok(paired.completed.result.wire_error===0&&paired.completed.result.paired&&paired.completed.result.credential.length===32,'ACTUAL_OWNER_PAIR');
   await until(()=>f.requests.some(e=>e.op==='status'&&e.sent),'authenticated actual status');
   if(mode==='readonly'){
    const at=f.elapsed();await sleep(3000);report.readonly_elapsed=f.elapsed()-at;
    ok(f.requests.filter(e=>e.op==='status'&&e.sent).length>=3,'READONLY_REAL_TIMER_POLLS');
    ok(f.requests.every(e=>!e.op||e.op==='pair'||e.op==='status'),'READONLY_NO_COMMAND');report.diagnostic_only=true;
   }else{
    await until(async()=>{await prerequisite(await f.rpc('P'),'await-NeedsMaintenance');return page.locator('#status').textContent().then(s=>s.includes('core state 3 · fault 0'));},'NeedsMaintenance DOM');
    if(mode==='held-replies'){
     f.holdStatus=true;await until(()=>f.requests.some(e=>e.op==='status'&&e.holdStart!==undefined&&!e.sent),'status response held');
    }
    const before=await prerequisite(await f.rpc('P'),'pre-click');report.pre_click=before;ok(clean(before),'PRE_CLICK_NO_PRIOR_FAULT_OR_STOP');
    report.click_node_ms=f.elapsed();await tap('#stop');
    await until(()=>f.requests.some(e=>e.op==='stop'&&e.completed),'actual Stop joined completion');const stop=f.requests.find(e=>e.op==='stop');
    const c=stop.completed,a=c?.audit;ok(completionShape(before,c),'COMPLETED_METADATA_SCHEMA');
    ok(c.result.wire_error===0&&c.result.core_error===0,'STOP_RESULT_REJECTED');
    if(c.before.core_fault===8)ok(timeConsistent(c,c.before,before),'ENV_COMPLETION_CONSISTENCY');
    await prerequisite(c.before,'before-dispatch');
    if(a.pre_fault===8&&a.pre_stop>0){ok(timeConsistent(c,c.post,before),'ENV_COMPLETION_CONSISTENCY');await prerequisite(c.post,'native-before-enqueue');}
    ok(explicitStop(before,c),'EXPLICIT_STOP_REACHED_CORE');report.stop_native=a;
    if(mode==='held-replies'){
     ok(!stop.sent&&stop.holdStart!==undefined,'STOP_CORE_BEFORE_HELD_ACK');
     ok(f.requests.some(e=>e.op==='status'&&e.holdStart!==undefined&&!e.sent),'STATUS_RESPONSE_STILL_HELD_AT_STOP');
    }
    if(mode==='request-delay'){
     ok(clean(stop.delayPre)&&clean(stop.delayPost),'NO_STOP_BEFORE_DELAYED_FORWARD');
     ok(stop.delayEnd-stop.delayStart>=99,'MEASURED_REQUEST_DELAY');
    }
    await until(async()=>{const s=await f.rpc('P');return s.phase===4;},'Terminal',6000);
    const terminal=await f.rpc('P');report.terminal=terminal;
    ok(terminal.stop_at===c.result.accepted_at,'TERMINAL_SAME_EXPLICIT_STOP');
    ok(terminal.stop_verified||terminal.manual_power_cut_required,'HONEST_TERMINAL_DISPOSITION');
    report.stop_result=terminal.stop_verified?'HOST_FAKE_VERIFIED':'HOST_FAKE_MANUAL_CUT_REQUIRED';
    await until(()=>stop.sent,'Stop ACK after core',3000);
    if(mode==='held-replies')ok(stop.holdEnd-stop.holdStart>=1199,'MEASURED_STOP_ACK_HOLD');
    await until(()=>page.locator('#last-stop-outcome').textContent().then(s=>s.includes('stop_at='+terminal.stop_at+' /')),'same Terminal DOM history',4000);
    report.history=await page.locator('#last-stop-outcome').textContent();ok(report.history.includes('과거 관측'),'HISTORY_NOT_CURRENT_SAFETY');
    ok(report.history.includes('manual_power_cut_required='+terminal.manual_power_cut_required),'HONEST_MANUAL_CUT_DISPLAY');
    report.native_stop_to_terminal_ms=Number(terminal.at)-Number(terminal.stop_at);
    ok(f.requests.filter(e=>e.op==='stop').length===1,'EXPLICIT_STOP_ONCE');
   }
  }
  const frames=await f.rpc('F');ok(frames.moves===0&&frames.frames.every(r=>r.data[0]!==0xFD),'FD_ZERO');
  ok(frames.frames.every(r=>r.data[0]!==0xF3||r.data[1]!==1),'F3_ENABLE_ZERO');ok(!frames.calibration_measured,'CALIBRATION_FALSE');
  ok(errors.length===0&&blocked.length===0,'NO_PAGE_ERROR_OR_EXTERNAL_URL');report.frames=frames;report.final=await f.rpc('P');report.clock=await f.rpc('T');
  report.result='PASS';report.verification='PASS';report.checks=checks;
 }catch(e){report.result=e instanceof EnvironmentObstruction?'ENV_SERVICE_VIOLATION':'FAIL';report.verification=e instanceof EnvironmentObstruction?'NOT_REACHED':'FAIL';report.error=String(e);report.checks=checks;
  if(e instanceof EnvironmentObstruction)report.environment_obstruction={stage:e.stage,native:e.native,clock:e.clock};
  try{report.failure_native=await f.rpc('P');report.clock=await f.rpc('T');report.frames=await f.rpc('F');}catch{}
 }finally{
  clearTimeout(watchdog);
  if(page){report.observed=await page.evaluate(()=>window.__wallObserved()).catch(()=>null);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true}).catch(()=>{});}
  if(context)await context.close();await f.close();Object.assign(report,f.report(),{page_errors:errors,blocked});
  report.environment={service_gap_observed:(report.clock?.max_gap||0)>=10,max_gap_ms:report.clock?.max_gap??null};
  report.rtt_ms=(report.observed||[]).filter(r=>r.jsonEnd!==undefined).map(r=>({op:new URL(r.url,f.origin).pathname==='/api/status'?'status':r.body.split('|')[5]||'pair',ms:r.jsonEnd-r.start}));
  fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(report,null,2));
 }
 console.log(report.result+' '+name+(report.error?' '+report.error:''));return report;
}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PB_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--no-proxy-server']});const results=[];
 try{
  const cases=[['readonly',1],['baseline',1],['baseline',2],['held-replies',1],['request-delay',1],['bad-pair',1]];
  for(const [mode,axis] of cases)if(selected==='all'||selected===mode+'-axis'+axis)results.push(await scenario(browser,mode,axis,control));
  if(!results.length)throw Error('unknown case');
 }finally{await browser.close();}
 const summary={result:results.every(r=>r.result==='PASS')?'PASS':'FAIL',cases:results.map(r=>({name:r.name,result:r.result,error:r.error,checks:r.checks,clock:r.clock})),scope:'Host real elapsed time only; no hardware/normalRun/calibration'};
 fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify(summary,null,2));if(summary.result!=='PASS')process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
