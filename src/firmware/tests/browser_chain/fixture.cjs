'use strict';
const http=require('node:http'),{spawn}=require('node:child_process'),readline=require('node:readline'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'../../../..');
class Fixture{
 constructor(exe,axis,mode,control=''){
  this.axis=axis;this.mode=mode;this.control=control;this.now=0;this.events=[];this.requests=[];this.work=[];this.pendingNative=[];this.sessions=new Set();this.inflight=[];this.serial=Promise.resolve();this.delays=false;this.stderr='';
  this.html=fs.readFileSync(path.join(ROOT,'src/firmware/components/robot_phone/web/index.html'));this.js=fs.readFileSync(path.join(ROOT,'src/firmware/components/robot_phone/web/app.js'));
  this.child=spawn(exe,[String(axis)],{stdio:['pipe','pipe','pipe']});this.child.stderr.on('data',b=>this.stderr+=b.toString());
  this.exited=new Promise(resolve=>this.child.once('exit',code=>{this.code=code;this.failure=Error('native exit '+code+' '+this.stderr);for(const p of this.inflight.splice(0))p.reject(this.failure);resolve(code);}));
  this.child.once('error',e=>{this.failure=e;for(const p of this.inflight.splice(0))p.reject(e);});
  readline.createInterface({input:this.child.stdout}).on('line',line=>{const p=this.inflight.shift();if(p){try{p.resolve(JSON.parse(line));}catch(e){p.reject(e);}}});
 }
 rpc(text){const task=this.serial.then(()=>new Promise((resolve,reject)=>{if(this.failure)return reject(this.failure);const timeout=setTimeout(()=>{reject(Error('native wall timeout'));this.child.kill();},3000);this.inflight.push({resolve:r=>{clearTimeout(timeout);this.events.push({at:this.now,text,result:r});resolve(r);},reject:e=>{clearTimeout(timeout);reject(e);}});this.child.stdin.write(text+'\n');}));this.serial=task.catch(()=>{});return task;}
 async begin(){
  this.cold=await this.rpc('M');assert.equal(this.cold.at,'0');assert.equal(this.cold.paired_mask,0);assert.equal(this.cold.moves,0);
  this.server=http.createServer((req,res)=>this.handle(req,res).catch(e=>{this.failure=e;try{res.writeHead(500);res.end();}catch{}}));await new Promise(r=>this.server.listen(0,'127.0.0.1',r));this.origin='http://127.0.0.1:'+this.server.address().port;
 }
 async handle(req,res){let body='';for await(const b of req){body+=b.toString();if(body.length>256){res.writeHead(413);res.end();return;}}
  const e={id:this.requests.length+1,at:this.now,path:req.url,method:req.method,body,api:req.url.startsWith('/api/'),sent:false,res,credential:req.headers['x-session-credential']||'',pairing:req.headers['x-pairing-credential']||''};this.requests.push(e);
  if(req.method==='OPTIONS'){this.send(e,204,'');return;}
  if(req.url==='/'){this.send(e,200,this.html,'text/html; charset=utf-8');return;}
  if(req.url==='/app.js'){this.send(e,200,this.control==='wrong-asset'?Buffer.concat([this.js,Buffer.from('\n/* changed asset */')]):this.js,'text/javascript; charset=utf-8');return;}
  if(req.url==='/favicon.ico'){this.send(e,204,'');return;}
  if(!e.api){this.send(e,404,{});return;}
  e.op=e.path==='/api/session'?'pair':e.path==='/api/status'?'status':body.split('|')[5];
  const qdelay=this.mode==='queue-age'&&e.op==='enable-selected'?50:0;e.queueDelay=qdelay;this.work.push({due:this.now+qdelay,kind:'dispatch',entry:e});
 }
 send(e,code,data,type='application/json'){
  e.sent=true;e.replyAt=this.now;e.http=code;const headers={'Content-Type':type,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type, X-Session-Credential, X-Pairing-Credential','Access-Control-Allow-Methods':'POST,GET,OPTIONS'};
  e.res.writeHead(code,headers);e.res.end(typeof data==='object'&&!Buffer.isBuffer(data)?JSON.stringify(data):data);
 }
 async dispatch(e){
  if(e.path==='/api/status'){
   if(!this.sessions.has(e.credential)){this.send(e,401,{});return;}
   e.result=await this.rpc('P');e.coreAt=this.now;const d=this.delays&&this.mode==='hidden-stop'?1200:0;this.work.push({due:this.now+d,kind:'reply',entry:e});return;
  }
  if(e.path!=='/api/session'&&e.path!=='/api/command'&&e.path!=='/api/stop'){this.send(e,404,{});return;}
  if(this.control==='missing-handoff'&&e.op==='handoff-acquire'){
   e.forwarded=false;e.result={wire_error:0,core_error:0,queued:true,transfer_id:e.body.split('|')[4],transfer_state:1,accepted_at:String(this.now)};e.coreAt=this.now;this.work.push({due:this.now,kind:'reply',entry:e});return;
  }
  if(this.control==='missing-stop'&&e.op==='stop'){
   e.forwarded=false;e.result={wire_error:0,core_error:0,queued:true,accepted_at:String(this.now)};e.coreAt=this.now;this.work.push({due:this.now,kind:'reply',entry:e});return;
  }
  e.forwarded=true;const kind=e.op==='pair'?'J':e.path==='/api/stop'?'X':'N';e.kind=kind;
  const credential=kind==='J'?e.pairing:e.credential;if(credential.length!==32){this.send(e,401,{});return;}
  const text=kind+' '+credential+(kind==='J'?'':' '+e.at+' '+e.body);const r=await this.rpc(text);e.coreAt=this.now;
  if(!r.ready){e.job=r.job;this.pendingNative.push(e);return;}this.result(e,r);
 }
 result(e,r){e.result=r;if(e.op==='pair'&&r.wire_error===0&&r.paired)this.sessions.add(r.credential);
  let d=0;if(this.mode==='hidden-stop'&&e.op==='handoff-acquire')d=1200;if(this.mode==='late-receipt'&&e.op==='handoff-result')d=1200;
  this.work.push({due:this.now+d,kind:'reply',entry:e});
 }
 async flush(){
  for(const e of [...this.pendingNative]){const r=await this.rpc('R '+(e.kind==='X'?'X':'N')+' '+e.job);if(r.ready){this.pendingNative.splice(this.pendingNative.indexOf(e),1);this.result(e,r);}}
  for(let n=0;n<100;++n){const i=this.work.findIndex(x=>x.due<=this.now);if(i<0)return;const w=this.work.splice(i,1)[0];if(w.kind==='dispatch')await this.dispatch(w.entry);else this.send(w.entry,200,w.entry.result);}
  throw Error('too many same-time jobs');
 }
 nextDue(){const future=this.work.map(w=>w.due).filter(t=>t>this.now);return future.length?Math.min(...future):Infinity;}
 async close(){if(this.server){this.server.closeAllConnections();await new Promise(r=>this.server.close(r));}await this.serial;this.child.stdin.end();const code=await Promise.race([this.exited,new Promise(r=>setTimeout(()=>r(null),2000))]);if(code===null)this.child.kill();}
 report(){return {cold:this.cold,requests:this.requests.map(({res,credential,pairing,...e})=>({...e,result:e.op==='pair'&&e.result?{...e.result,credential:'[fixture session returned]'}:e.result})),events:this.events.map(e=>e.result?.paired?{...e,result:{...e.result,credential:'[fixture session returned]'}}:e),native_code:this.code,stderr:this.stderr};}
}
module.exports={Fixture};
