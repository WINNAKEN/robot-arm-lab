'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {chromium}=require('playwright');const root=path.resolve(__dirname,'../../../..'),out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
const original=path.join(root,'src/firmware/components/robot_phone/web/app.js'),app=process.env.SO_APP||original;
const js=fs.readFileSync(app),html=fs.readFileSync(path.join(root,'src/firmware/components/robot_phone/web/index.html'));
const native=JSON.parse(fs.readFileSync(path.join(root,'.dev/stop-capability-evidence/independent-r1/owner/pending.json'),'utf8')).final;
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');let state={...native},fail=false,checks=0;const traffic=[],blocked=[],pageErrors=[];let context,browser,page,server;
const ok=(v,m)=>{++checks;assert.ok(v,m);};
async function until(fn,message){for(let n=0;n<100;++n){if(await fn())return;await new Promise(r=>setTimeout(r,30));}throw Error('timeout: '+message);}
const report={scope:'ACTUAL_DOM_HISTORY_RETENTION_ONLY; recorded033 actualOwner terminal HTTP payload; pairing/status fixture; NO live Owner/browser composition or OS background/physical approval',result:'RUNNING',app_path:path.relative(root,app),expected_js_sha256:sha(js),expected_html_sha256:sha(html)};
(async()=>{
 try{
  server=http.createServer(async(req,res)=>{let body='';for await(const b of req)body+=b;traffic.push({method:req.method,path:req.url,body});res.setHeader('Cache-Control','no-store');
   const send=(code,value,type='application/json')=>{res.writeHead(code,{'Content-Type':type});res.end(typeof value==='object'&&!Buffer.isBuffer(value)?JSON.stringify(value):value);};
   if(req.url==='/')return send(200,html,'text/html; charset=utf-8');if(req.url==='/app.js')return send(200,js,'text/javascript; charset=utf-8');if(req.url==='/favicon.ico')return send(204,'');
   if(req.url==='/api/session')return send(req.headers['x-pairing-credential']==='a'.repeat(32)?200:401,{wire_error:0,credential:'b'.repeat(32)});
   if(req.headers['x-session-credential']!=='b'.repeat(32))return send(401,{});
   if(req.url==='/api/status')return send(fail?503:200,fail?{}:state);
   return send(400,{wire_error:11,core_error:0});
  });await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:process.env.PB_BROWSER,headless:true,args:['--disable-background-networking']});report.browser=browser.version();
  context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});await context.route('**/*',async route=>{if(route.request().url().startsWith(origin+'/'))await route.continue();else{blocked.push(route.request().url());await route.abort();}});
  page=await context.newPage();page.on('pageerror',e=>pageErrors.push(String(e)));let seenJs='',seenHtml='';page.on('response',async r=>{try{if(r.url()===origin+'/app.js')seenJs=sha(await r.body());if(r.url()===origin+'/')seenHtml=sha(await r.body());}catch{}});
  await page.goto(origin+'/',{waitUntil:'load'});await until(()=>seenJs&&seenHtml,'served assets');ok(seenJs===sha(js)&&seenHtml===sha(html),'EXACT_ASSETS');
  const text=()=>page.locator('#last-stop-outcome').textContent();const live=()=>page.locator('#status').textContent();
  const pair=async()=>{await page.locator('#pairing').fill('a'.repeat(32));await page.locator('#pair').click();};
  await pair();await until(async()=>(await text()).includes('stop_verified=true'),'recorded native Terminal panel');const nativeText=await text();ok(nativeText.includes('과거 관측')&&nativeText.includes('부팅 11'),'HISTORICAL_SOURCE_LABEL');
  await context.setOffline(true);await until(async()=>(await live()).includes('연결 없음'),'actual browser offline or failed poll -> disconnect');
  ok((await text())===nativeText,'RECORD_VISIBLE_WHEN_DISCONNECTED');ok(await page.locator('#angle-send').isDisabled()&&await page.locator('#stop').isDisabled(),'HISTORY_NO_AUTHORITY');
  await page.screenshot({path:path.join(out,'verified-offline.png'),fullPage:true});
  await context.setOffline(false);state={...native,at:'11001',stop_verified:false,core_stop_verified:false,manual_power_cut_required:true,core_fault:12};report.synthetic_diagnostic_case='explicit manualcut=true/verifiedfalse payload variant; NOT real hardware/Owner fault measurement';
  await pair();await until(async()=>(await text()).includes('manual_power_cut_required=true'),'synthetic diagnostic visible');const diagnosticText=await text();ok(diagnosticText.includes('수동 전원 차단 필요로 보고됨')&&diagnosticText.includes('stop_verified=false'),'MANUAL_CUT_FACTS');
  fail=true;await until(async()=>(await live()).includes('연결 없음'),'503 disconnect');ok((await text())===diagnosticText,'MANUAL_CUT_RETAINED_AFTER_503');
  await page.screenshot({path:path.join(out,'manualcut-disconnected.png'),fullPage:true});
  fail=false;state={...native,boot:'12',generation:'1',at:'1000',phase:0,stop_verified:false,manual_power_cut_required:false,stop_at:'0',fault_at:'0',core_fault:0};await pair();
  await until(async()=>(await live()).includes('generation 1'),'new boot ordinary status');ok((await text())===diagnosticText,'NONTERMINAL_NEW_BOOT_PRESERVES_HISTORY');ok(await page.locator('#angle-send').isDisabled(),'PAIR_DOES_NOT_MOVE_FROM_HISTORY');
  state={...native,boot:'12',at:'11000'};await until(async()=>(await text()).includes('부팅 12'),'new authenticated Terminal replaces latest record');ok((await text()).includes('과거 관측'),'REPLACEMENT_STILL_HISTORICAL');
  ok(!traffic.some(x=>x.path==='/api/command'||x.path==='/api/stop')&&blocked.length===0,'NO_COMMAND_OR_RENEW_FROM_HISTORY');ok(pageErrors.length===0,'NO_PAGEERROR');
  const storage=await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}));ok(storage.local===0&&storage.session===0,'NO_STORAGE');ok(!(await page.content()).includes('b'.repeat(32)),'NO_SESSION_SECRET_IN_DOM');
  report.result='PASS';report.checks=checks;report.actual_js_sha256=seenJs;report.actual_html_sha256=seenHtml;console.log('OUTCOME DOM PASS checks='+checks+'; actual HTML/JS/fetch/disconnect/render, RECORDED_NATIVE_STATUS + synthetic diagnostics; full CAN/Boot/PB NOT_ACCEPTED');
 }catch(e){report.result='FAIL';report.error=String(e);if(page)await page.screenshot({path:path.join(out,'FAIL.png'),fullPage:true}).catch(()=>{});throw e;}
 finally{Object.assign(report,{traffic,blocked,page_errors:pageErrors});fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));if(context)await context.close();if(browser)await browser.close();if(server){server.closeAllConnections();await new Promise(r=>server.close(r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});
