'use strict';
const http=require('node:http');
const {spawn}=require('node:child_process');
const readline=require('node:readline');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
class Fixture {
  constructor(exe,measured,control=''){
    this.events=[];this.commands=[];this.requests=[];this.timers=new Set();this.pending=[];this.chain=Promise.resolve();this.control=control;this.delayOp='';this.delayStatus=false;this.closed=false;
    this.start=process.hrtime.bigint();this.elapsed=()=>Number(process.hrtime.bigint()-this.start)/1e6;
    this.child=spawn(exe,[String(measured)],{stdio:['pipe','pipe','pipe']});this.stderr='';this.child.stderr.on('data',bytes=>{this.stderr+=bytes;});
    this.exited=new Promise(resolve=>this.child.once('exit',code=>{this.childCode=code;this.failure=Error('actor exited '+code+' '+this.stderr);for(const job of this.pending.splice(0))job.reject(this.failure);resolve(code);}));
    this.child.once('error',error=>{this.failure=error;for(const job of this.pending.splice(0))job.reject(error);});
    readline.createInterface({input:this.child.stdout}).on('line',line=>{const job=this.pending.shift();if(!job)return;try{job.resolve(JSON.parse(line));}catch(error){job.reject(error);}});
    this.root=path.resolve(__dirname,'../../components/robot_phone/web');this.html=fs.readFileSync(path.join(this.root,'index.html'));this.js=fs.readFileSync(path.join(this.root,'app.js'));
  }
  line(text){return new Promise((resolve,reject)=>{if(this.failure)return reject(this.failure);const timer=setTimeout(()=>{this.failure=Error('actor response timeout');this.child.kill();reject(this.failure);},3000);this.pending.push({resolve:x=>{clearTimeout(timer);resolve(x);},reject:e=>{clearTimeout(timer);reject(e);}});this.child.stdin.write(text+'\n');});}
  actor(text){
    const task=this.chain.then(async()=>{
      const host=this.elapsed();const target=this.clockBase+Math.floor(host-this.clockStart);
      const clock=await this.line('W '+target);const result=await this.line(text);
      this.events.push({kind:'actor',host_ms:this.elapsed(),clock:clock.at,text,result});return result;
    });this.chain=task.catch(()=>{});return task;
  }
  async begin(){
    const first=await this.line('P');this.clockBase=Number(first.at);this.clockStart=this.elapsed();this.events.push({kind:'clock_origin',host_ms:this.clockStart,core_ms:this.clockBase,fixture_auto_renew:false,command_favorable:false});
    this.pump=setInterval(()=>{if(!this.closed)this.actor('P').catch(error=>{this.failure=error;});},10);
    this.server=http.createServer((req,res)=>this.handle(req,res).catch(error=>{this.events.push({kind:'http_error',error:String(error)});if(!res.headersSent)res.writeHead(500);res.end();}));
    await new Promise((resolve,reject)=>{this.server.once('error',reject);this.server.listen(0,'127.0.0.1',resolve);});
    this.origin='http://127.0.0.1:'+this.server.address().port;return this;
  }
  async handle(req,res){
    const id=this.requests.length+1;const entry={id,method:req.method,url:req.url,host_ms:this.elapsed()};this.requests.push(entry);
    const headers={'Cache-Control':'no-store','Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'X-Session-Credential, X-Pairing-Credential, Content-Type','Access-Control-Allow-Methods':'POST, GET, OPTIONS'};
    const send=(code,value,type='application/json')=>{entry.reply_ms=this.elapsed();res.writeHead(code,{...headers,'Content-Type':type});res.end(typeof value==='object'&&!Buffer.isBuffer(value)?JSON.stringify(value):value);};
    if(req.method==='OPTIONS'){send(204,'');return;}
    if(req.url==='/'||req.url==='/index.html'){send(200,this.html,'text/html; charset=utf-8');return;}
    if(req.url==='/app.js'){const bytes=this.control==='wrong-asset'?Buffer.concat([this.js,Buffer.from('\n/* fixture corruption */')]):this.js;entry.sha256=sha(bytes);send(200,bytes,'text/javascript; charset=utf-8');return;}
    if(req.url==='/favicon.ico'){send(204,'');return;}
    let body='';for await(const bytes of req){body+=bytes.toString();if(body.length>256){send(413,{});return;}}
    entry.body=body;
    if(req.url==='/api/session'){send(req.headers['x-pairing-credential']==='a'.repeat(32)?200:401,{wire_error:0,credential:'b'.repeat(32)});return;}
    if(req.headers['x-session-credential']!=='b'.repeat(32)){send(401,{wire_error:4});return;}
    if(req.url==='/api/status'){
      const result=await this.actor('P');if(this.delayStatus)await this.hold(1200);send(200,result);return;
    }
    if(req.url==='/api/command'||req.url==='/api/stop'){
      const op=body.split('|')[5];const item={id,op,body,received_ms:this.elapsed(),forwarded:!(this.control==='missing-stop'&&op==='stop')};this.commands.push(item);
      item.result=item.forwarded?await this.actor('C '+body):{wire_error:0,core_error:0,lease:'0',ticket:'0',queued:true,accepted_at:'0'};
      item.core_done_ms=this.elapsed();if(this.delayOp===op)await this.hold(1100);item.reply_ms=this.elapsed();send(200,item.result);return;
    }
    send(404,{});
  }
  hold(ms){return new Promise(resolve=>{const timer=setTimeout(()=>{this.timers.delete(timer);resolve();},ms);this.timers.add(timer);});}
  async metrics(){const result=await this.actor('M');return this.control==='missing-fd'?{...result,moves:0,fd:[]}:result;}
  async close(){
    this.closed=true;clearInterval(this.pump);for(const timer of this.timers)clearTimeout(timer);this.timers.clear();
    if(this.server){this.server.closeAllConnections();await new Promise(resolve=>this.server.close(resolve));}
    await this.chain.catch(()=>{});this.child.stdin.end();const code=await Promise.race([this.exited,delay(2000).then(()=>null)]);
    if(code===null){this.child.kill();await this.exited;}return this.childCode;
  }
}
module.exports={Fixture,sha,delay};
