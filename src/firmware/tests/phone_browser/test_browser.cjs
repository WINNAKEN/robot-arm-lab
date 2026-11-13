'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const {Fixture,sha,delay}=require('./fixture.cjs');
const [exe,build]=process.argv.slice(2);const controls=process.argv.includes('--controls');
let checks=0;
const ok=(value,message)=>{++checks;assert.ok(value,message);};
async function until(predicate,message,ms=6000,interval=20){const start=Date.now();while(Date.now()-start<ms){if(await predicate())return;await delay(interval);}throw Error('timeout: '+message);}
const good=entry=>entry.result&&entry.result.wire_error===0&&entry.result.core_error===0;
async function scenario(browser,name,control=''){
  const fixture=new Fixture(exe,name!=='unapproved',control);let context,page;const errors=[],consoleErrors=[],redirects=[],network=[];
  const report={name,control,checks_start:checks,result:'RUNNING'};let expired;
  const timeout=new Promise((_,reject)=>{expired=setTimeout(()=>reject(Error('scenario total timeout')),30000);});
  const run=async()=>{
    await fixture.begin();context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
    await context.route('**/*',async route=>{
      const request=route.request(),url=request.url();
      if(url.startsWith(fixture.origin+'/')){await route.continue();return;}
      if(url==='http://192.168.4.1:8081/api/stop'){
        redirects.push({original:url,local:fixture.origin+'/api/stop',method:request.method(),host_ms:fixture.elapsed()});
        try{const response=await route.fetch({url:fixture.origin+'/api/stop',timeout:4000});await route.fulfill({response});}catch(error){await route.abort().catch(()=>{});}
        return;
      }
      network.push({blocked:url});await route.abort();
    });
    page=await context.newPage();page.setDefaultTimeout(5000);
    page.on('pageerror',error=>errors.push(String(error)));page.on('console',event=>{if(event.type()==='error')consoleErrors.push(event.text());});
    let actualAppHash='',actualHtmlHash='';
    page.on('response',async response=>{try{if(response.url()===fixture.origin+'/app.js')actualAppHash=sha(await response.body());if(response.url()===fixture.origin+'/')actualHtmlHash=sha(await response.body());}catch{}});
    await page.goto(fixture.origin+'/',{waitUntil:'load'});await until(()=>actualAppHash&&actualHtmlHash,'asset hashes');
    ok(actualAppHash===sha(fixture.js),'ASSET_IDENTITY app.js');ok(actualHtmlHash===sha(fixture.html),'ASSET_IDENTITY HTML');
    report.browser_version=browser.version();report.actual_app_sha256=actualAppHash;report.actual_html_sha256=actualHtmlHash;
    await page.locator('#pairing').fill('a'.repeat(32));await page.locator('#pair').click();
    const state=async n=>page.locator('#status').textContent().then(t=>t.includes('core state '+n+' · fault 0'));
    await until(()=>state(3),'NeedsMaintenance DOM');
    const clickOp=async(op)=>{
      const button=page.locator('[data-op="'+op+'"]');await button.scrollIntoViewIfNeeded();
      const box=await button.boundingBox();ok(box&&await button.isEnabled(),'DOM_ACTIONABLE '+op);
      // Explicit favorable operator phase, observed at the fake CAN boundary.
      // No clock jump, proof fabrication, port drain or automatic request retry.
      if(['maintenance','disable-all','finish-maintenance','drive','enable-selected'].includes(op))await until(async()=>{const sample=await fixture.metrics();return sample.operator_slot;},'observable stationary operator slot '+op,6000,1);
      const before=fixture.commands.length;await page.touchscreen.tap(box.x+box.width/2,box.y+box.height/2);
      await until(()=>fixture.commands.slice(before).some(x=>x.op===op&&x.reply_ms!==undefined),'reply '+op);
      const entry=fixture.commands.slice(before).find(x=>x.op===op);ok(good(entry),'COMMAND_ACCEPTED '+op+' '+JSON.stringify(entry.result));
    };
    await clickOp('maintenance');
    // Manual confirmation is clipped to the current lease. Observe the actual
    // client's first renewal before the separate explicit unloaded confirmation.
    await until(()=>fixture.commands.some(x=>x.op==='maintenance-renew'&&good(x)),'initial maintenance renewal');
    const unloadedButton=page.locator('[data-op="unloaded"]'),disableButton=page.locator('[data-op="disable-all"]');
    await disableButton.scrollIntoViewIfNeeded();const unloadedBox=await unloadedButton.boundingBox(),disableBox=await disableButton.boundingBox();
    await until(async()=>{const sample=await fixture.metrics();const renew=fixture.commands.filter(x=>x.op==='maintenance-renew'&&good(x)).at(-1);return sample.confirm_phase&&renew&&Number(sample.at)-Number(renew.result.accepted_at)<100;},'explicit fresh confirmation phase',6000,1);
    await page.touchscreen.tap(unloadedBox.x+unloadedBox.width/2,unloadedBox.y+unloadedBox.height/2);
    await until(()=>fixture.commands.some(x=>x.op==='unloaded'&&good(x)),'unloaded confirmation',1000,1);
    const confirmation=fixture.commands.find(x=>x.op==='unloaded');
    await page.waitForFunction(at=>document.querySelector('#message').textContent.includes('accepted at='+at),confirmation.result.accepted_at);
    await until(async()=>(await fixture.metrics()).operator_slot,'disable observed slot',1000,1);
    await page.touchscreen.tap(disableBox.x+disableBox.width/2,disableBox.y+disableBox.height/2);
    await until(()=>fixture.commands.some(x=>x.op==='disable-all'&&x.reply_ms!==undefined),'disable response');ok(good(fixture.commands.find(x=>x.op==='disable-all')),'COMMAND_ACCEPTED disable-all');
    // A second explicit operator confirmation, not an automatic extension of
    // ConfirmUnloaded by Renew. The earlier single-confirmation expiry stays
    // preserved in author-attempt-003/004/005 as a separate adverse schedule.
    await delay(450);report.operator_reconfirmations=1;await clickOp('unloaded');
    await until(()=>state(4),'ReadyDisabled DOM');
    await clickOp('finish-maintenance');await clickOp('drive');await clickOp('enable-selected');await until(()=>state(8),'Granted DOM');
    await delay(600); // explicit operator dwell, with unmodified 50ms client renewal running
    if(name==='handoff-stop')fixture.delayOp='handoff';
    await page.locator('#handoff').click();await until(()=>fixture.commands.some(x=>x.op==='handoff'&&x.core_done_ms!==undefined),'Handoff actual core');
    if(name==='handoff-stop'){
      await until(async()=>{const t=await page.locator('#status').textContent();return t.startsWith('운전 /')||t.startsWith('운전 확인 /');},'status generation before Stop');
      await page.locator('#stop').click();await until(()=>fixture.commands.some(x=>x.op==='stop'&&x.core_done_ms!==undefined),'Stop actual receipt');
      ok(fixture.commands.some(x=>x.op==='stop'&&x.forwarded&&good(x)),'STOP_FORWARDING');
      await until(()=>fixture.commands.find(x=>x.op==='handoff').reply_ms!==undefined,'held ACK delivered');await delay(400);
      ok(!fixture.commands.some(x=>x.op==='acquire'),'NO_ACQUIRE_AFTER_STOP');ok((await fixture.metrics()).moves===0,'FD_ZERO');
    }else{
      await until(()=>fixture.commands.some(x=>x.op==='acquire'&&x.reply_ms!==undefined),'Acquire actual result');
      const acquire=fixture.commands.find(x=>x.op==='acquire');ok(good(acquire),'CONDITIONAL_ACQUIRE_SUCCESS '+JSON.stringify(acquire.result));
      if(name==='unapproved'){
        await delay(350);ok(await page.locator('#angle-send').isDisabled(),'UNAPPROVED_DISABLED');ok((await fixture.metrics()).moves===0,'FD_ZERO');
        ok(!fixture.commands.some(x=>x.op==='joint-step'),'NO_UNAPPROVED_V2');
      }else{
        await until(async()=>await page.locator('#angle-send').isEnabled(),'numeric DOM enabled');
        if(name==='status-delay'){
          fixture.delayStatus=true;await delay(900);ok(await page.locator('#angle-send').isDisabled(),'STALE_DISABLED');ok((await fixture.metrics()).moves===0,'FD_ZERO');
        }else if(name==='offline'){
          await context.setOffline(true);await until(async()=>await page.locator('#angle-send').isDisabled(),'offline disabled');
          const count=fixture.commands.length;await context.setOffline(false);await delay(650);
          ok(await page.locator('#angle-send').isDisabled(),'EXPLICIT_REPAIR_REQUIRED');ok(fixture.commands.length===count,'NO_RECONNECT_AUTHORITY');
          await page.locator('#pairing').fill('a'.repeat(32));await page.locator('#pair').click();await delay(300);
          ok(!fixture.commands.slice(count).some(x=>x.op==='acquire'),'NO_AUTO_ACQUIRE_AFTER_PAIR');ok((await fixture.metrics()).moves===0,'FD_ZERO');
        }else{
          if(name==='arm-delay')fixture.delayOp='arm';if(name==='ticket-delay')fixture.delayOp='ticket';
          await page.locator('#angle-input').fill('0.4166666666666667');await page.locator('#angle-send').click();
          if(name==='arm-delay'||name==='ticket-delay'){
            const op=fixture.delayOp;await until(()=>fixture.commands.some(x=>x.op===op&&x.reply_ms!==undefined),'delayed numeric reply');await delay(300);
            ok(!fixture.commands.some(x=>x.op==='joint-step'),'NO_V2_AFTER_DELAY');ok((await fixture.metrics()).moves===0,'FD_ZERO');
          }else{
            await until(()=>fixture.commands.some(x=>x.op==='joint-step'&&x.reply_ms!==undefined),'numeric result');
            const joint=fixture.commands.find(x=>x.op==='joint-step');ok(good(joint),'CONDITIONAL_NUMERIC_SUCCESS '+JSON.stringify(joint.result));
            const metrics=await fixture.metrics();ok(metrics.moves===1&&metrics.fd.length===1&&metrics.fd[0].pulses===100,'FD_EXACTLY_ONE');
            await until(async()=>await page.locator('#angle-send').isEnabled(),'completed and ready again');await delay(500);
            ok(fixture.commands.filter(x=>x.op==='renew'&&good(x)).length>=2,'ACTUAL_NORMAL_RENEW');
            await page.screenshot({path:path.join(build,name+(control?'-'+control:'')+'.png'),fullPage:true});
            await page.locator('#stop').click();await until(()=>fixture.commands.some(x=>x.op==='stop'&&x.core_done_ms!==undefined),'Stop actual receipt');
            ok(fixture.commands.some(x=>x.op==='stop'&&x.forwarded&&good(x)),'STOP_FORWARDING');
            await until(async()=>{const s=await fixture.actor('P');return s.stop_verified;},'actual Stop verified');ok(redirects.some(x=>x.method==='POST'),'ACTUAL_STOP_URL_REDIRECT');
          }
        }
      }
    }
    const times=fixture.requests.filter(x=>x.url==='/api/status').map(x=>x.host_ms);const gaps=times.slice(1).map((x,i)=>x-times[i]);
    report.status_intervals_ms=gaps;report.normal_renew_times_ms=fixture.commands.filter(x=>x.op==='renew').map(x=>x.received_ms);
    ok(gaps.filter(x=>x>=150&&x<=500).length>=3,'ACTUAL_250MS_POLL_SCHEDULE');
    ok(errors.length===0,'NO_UNEXPECTED_PAGEERROR '+errors.join(';'));
    report.result='PASS';report.checks=checks-report.checks_start;
  };
  try{await Promise.race([run(),timeout]);}
  catch(error){report.result='FAIL';report.error=String(error);if(page)await page.screenshot({path:path.join(build,name+(control?'-'+control:'')+'-FAIL.png'),fullPage:true}).catch(()=>{});throw error;}
  finally{
    clearTimeout(expired);if(context)await context.close().catch(()=>{});await fixture.close();
    Object.assign(report,{page_errors:errors,console_errors:consoleErrors,redirects,blocked_requests:network,requests:fixture.requests,commands:fixture.commands,actor:fixture.events,actor_exit:fixture.childCode,actor_stderr:fixture.stderr});
    fs.writeFileSync(path.join(build,name+(control?'-'+control:'')+'.json'),JSON.stringify(report,null,2));
  }
  return report;
}
(async()=>{
  const browser=await chromium.launch({executablePath:process.env.PB_BROWSER,headless:true,args:['--disable-background-networking']});
  const results=[];
  try{
    for(const name of ['normal','unapproved','arm-delay','ticket-delay','handoff-stop','status-delay','offline']){console.log('BROWSER START '+name);const report=await scenario(browser,name);results.push({name,result:report.result,checks:report.checks});console.log('BROWSER PASS '+name+' checks='+report.checks);}
    if(controls)for(const [control,marker]of [['wrong-asset','ASSET_IDENTITY'],['missing-stop','STOP_FORWARDING'],['missing-fd','FD_EXACTLY_ONE']]){
      console.log('CONTROL START '+control);let error;try{await scenario(browser,'normal',control);}catch(e){error=e;}
      assert.ok(error instanceof assert.AssertionError&&error.message.includes(marker),'control must reach intended assertion '+control+' '+String(error));results.push({control,syntax:'UNCHANGED_VALID_PRODUCT',result:'EXPECTED_ASSERTION_FAILURE',marker});console.log('CONTROL KILLED '+control);
    }
    fs.writeFileSync(path.join(build,'results.json'),JSON.stringify({browser:browser.version(),checks,results,phone_hardware:'NOT_RUN',production_http_server:'NOT_RUN_FIXTURE_HTTP_ONLY',production_source_changed:false},null,2));
    console.log('BROWSER SUITE PASS checks='+checks+'; actual Chromium DOM/timers/fetch + loopback HTTP + actual C++ Owner/FakeCAN; ESP32/phone/WiFi NOT_RUN');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
