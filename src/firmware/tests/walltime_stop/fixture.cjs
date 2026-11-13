'use strict';
const http=require('node:http'),{spawn}=require('node:child_process'),readline=require('node:readline'),fs=require('node:fs'),path=require('node:path');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
class Fixture{
 constructor(exe,axis,mode,control=''){
  this.axis=axis;this.mode=mode;this.control=control;this.requests=[];this.events=[];this.serial=Promise.resolve();this.pending=[];this.sessions=new Set();this.holdStatus=false;
  const origin=process.hrtime.bigint();this.elapsed=()=>Number(process.hrtime.bigint()-origin)/1e6;
  const root=path.resolve(__dirname,'../../components/robot_phone/web');this.html=fs.readFileSync(path.join(root,'index.html'));this.js=fs.readFileSync(path.join(root,'app.js'));
  this.child=spawn(exe,[String(axis)],{stdio:['pipe','pipe','pipe']});this.stderr='';this.child.stderr.on('data',b=>this.stderr+=b);
  this.exited=new Promise(r=>this.child.once('exit',code=>{this.code=code;this.failure=Error('native exit '+code+' '+this.stderr);for(const p of this.pending.splice(0))p.reject(this.failure);r(code);}));
  this.child.once('error',e=>{this.failure=e;for(const p of this.pending.splice(0))p.reject(e);});
  readline.createInterface({input:this.child.stdout}).on('line',line=>{const p=this.pending.shift();if(p){try{p.resolve(JSON.parse(line));}catch(e){p.reject(e);}}});
 }
 rpc(text){const p=this.serial.then(()=>new Promise((resolve,reject)=>{
  if(this.failure)return reject(this.failure);const sent=this.elapsed();
  const timer=setTimeout(()=>{reject(Error('native timeout'));this.child.kill();},3000);
  this.pending.push({resolve:r=>{clearTimeout(timer);this.events.push({sent,received:this.elapsed(),text:text.replace(/^([JNX]) .{32}/,'$1 [credential]'),result:r.paired?{...r,credential:'[returned actual session]'}:r});resolve(r);},reject:e=>{clearTimeout(timer);reject(e);}});
  this.child.stdin.write(text+'\n');
 }));this.serial=p.catch(()=>{});return p;}
 async begin(){
  this.cold=await this.rpc('M');if(this.cold.paired_mask!==0||this.cold.moves!==0)throw Error('not cold');
  this.server=http.createServer((req,res)=>this.handle(req,res).catch(e=>{this.failure=e;if(!res.headersSent)res.writeHead(500);res.end();}));
  await new Promise(r=>this.server.listen(0,'127.0.0.1',r));this.origin='http://127.0.0.1:'+this.server.address().port;
 }
 send(e,code,value,type='application/json'){
  e.sentAt=this.elapsed();e.http=code;e.sent=true;
  e.res.writeHead(code,{'Content-Type':type,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type, X-Session-Credential, X-Pairing-Credential','Access-Control-Allow-Methods':'POST, GET, OPTIONS'});
  e.res.end(typeof value==='object'&&!Buffer.isBuffer(value)?JSON.stringify(value):value);
 }
 async handle(req,res){
  const e={id:this.requests.length+1,method:req.method,path:req.url,receivedAt:this.elapsed(),res,sent:false};this.requests.push(e);
  if(req.method==='OPTIONS'){this.send(e,204,'');return;}
  if(req.url==='/'){this.send(e,200,this.html,'text/html; charset=utf-8');return;}
  if(req.url==='/app.js'){this.send(e,200,this.control==='wrong-asset'?Buffer.concat([this.js,Buffer.from('\n/* valid asset control */')]):this.js,'text/javascript; charset=utf-8');return;}
  if(req.url==='/favicon.ico'){this.send(e,204,'');return;}
  let body='';for await(const b of req){body+=b;if(body.length>256){this.send(e,413,{});return;}}e.body=body;
  e.op=req.url==='/api/session'?'pair':req.url==='/api/status'?'status':body.split('|')[5];
  const cred=req.headers[e.op==='pair'?'x-pairing-credential':'x-session-credential']||'';
  if(cred.length!==32){this.send(e,401,{});return;}
  if(e.op==='status'){
   if(!this.sessions.has(cred)){this.send(e,401,{});return;}
   e.result=await this.rpc('P');e.coreDoneAt=this.elapsed();
   e.responseDelay=this.holdStatus?1200:0;
  }else if(['/api/session','/api/command','/api/stop'].includes(req.url)){
   e.requestDelay=this.mode==='request-delay'&&e.op==='stop'?100:0;
   if(e.requestDelay){e.delayPre=await this.rpc('P');e.delayStart=this.elapsed();await sleep(e.requestDelay);e.delayEnd=this.elapsed();e.delayPost=await this.rpc('P');}
   e.dispatchAt=this.elapsed();
   if(this.control==='missing-stop'&&e.op==='stop'){
    e.forwarded=false;e.result={ready:true,wire_error:0,core_error:0,queued:true,accepted_at:'0'};
    e.missingProbe=await this.rpc('P');
   }else{
    e.forwarded=true;const kind=e.op==='pair'?'J':req.url==='/api/stop'?'X':'N';
    let r=await this.rpc(kind+' '+cred+(kind==='J'?'':' 0 '+body));
    const deadline=this.elapsed()+2000,job=r.job;
    while(!r.ready){if(this.elapsed()>=deadline)throw Error('native pending result timeout');await sleep(1);r=await this.rpc('R '+(kind==='X'?'X':'N')+' '+job);}
    e.result=r;e.audit=await this.rpc('T');
    if(e.op==='pair'&&r.paired&&r.wire_error===0)this.sessions.add(r.credential);
   }
   e.coreDoneAt=this.elapsed();e.responseDelay=this.mode==='held-replies'&&e.op==='stop'?1200:0;
  }else{this.send(e,404,{});return;}
  if(e.responseDelay){e.holdStart=this.elapsed();await sleep(e.responseDelay);e.holdEnd=this.elapsed();}
  if(!res.destroyed)this.send(e,200,e.result);
 }
 async close(){
  if(this.server){this.server.closeAllConnections();await new Promise(r=>this.server.close(r));}
  await this.serial;this.child.stdin.end();await Promise.race([this.exited,sleep(2000)]);if(this.code===undefined){this.child.kill();await this.exited;}
 }
 report(){return{cold:this.cold,requests:this.requests.map(({res,...e})=>({...e,result:e.op==='pair'&&e.result?{...e.result,credential:'[returned actual session]'}:e.result})),events:this.events,native_exit:this.code,stderr:this.stderr};}
}
module.exports={Fixture,sleep};
