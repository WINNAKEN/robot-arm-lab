// Pure transport observer; returns original native promises/data and reads no headers.
module.exports=function(){
 const records=[],byResponse=new WeakMap(),nativeFetch=window.fetch,nativeJson=Response.prototype.json;
 const settle=(p,r,kind)=>{p.then(()=>{r[kind+'Done']=true;r[kind+'At']=Date.now();},()=>{r[kind+'Done']=true;r[kind+'Rejected']=true;r[kind+'At']=Date.now();});return p;};
 window.fetch=function(...args){const input=args[0],o=args[1]||{};const r={id:records.length+1,url:String(input),body:typeof o.body==='string'?o.body:'',at:Date.now()};records.push(r);
  const p=Reflect.apply(nativeFetch,this,args);p.then(response=>{r.ok=response.ok;byResponse.set(response,r);},()=>{});return settle(p,r,'fetch');
 };
 Response.prototype.json=function(...args){const p=Reflect.apply(nativeJson,this,args),r=byResponse.get(this);if(r)settle(p,r,'json');return p;};
 Object.defineProperty(window,'__chainObserved',{value:()=>records.map(r=>({...r})),writable:false});
 Object.defineProperty(window,'__chainFence',{value:()=>new Promise(resolve=>{const channel=new MessageChannel();channel.port1.onmessage=()=>{channel.port1.close();channel.port2.close();resolve();};channel.port2.postMessage(0);}),writable:false});
};
