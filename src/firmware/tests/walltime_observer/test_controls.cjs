'use strict';
const {spawnSync}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../../..'),out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
const results=[];
function run(name,control=''){
 const dir=path.join(out,name),args=[path.join(__dirname,'test_browser.cjs'),path.join(root,'.dev/walltime-stop-evidence/build/bridge.exe'),dir,'baseline-axis1',control];
 const r=spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',timeout:25000});
 fs.writeFileSync(path.join(out,name+'-output.txt'),(r.stdout||'')+'\n'+(r.stderr||''));
 const p=path.join(dir,'baseline-axis1'+(control?'-'+control:'')+'.json');assert.ok(fs.existsSync(p),'scenario report exists');const report=JSON.parse(fs.readFileSync(p));results.push({name,exit:r.status,result:report.result,verification:report.verification,environment:report.environment,error:report.error});return{r,report};
}
try{
 let x=run('before');if(x.report.result==='ENV_SERVICE_VIOLATION')throw Object.assign(Error('baseline-before environment obstruction'),{environment:true});assert.equal(x.r.status,0);assert.equal(x.report.result,'PASS');
 x=run('wrong-asset','wrong-asset');assert.equal(x.r.status,1);assert.match(x.report.error,/ASSET_IDENTITY/);assert.notEqual(x.report.actual_js,x.report.expected_js);
 x=run('missing-stop','missing-stop');if(x.report.result==='ENV_SERVICE_VIOLATION')throw Object.assign(Error('missing-forward prerequisite environment obstruction'),{environment:true});assert.equal(x.r.status,1);assert.match(x.report.error,/EXPLICIT_STOP_REACHED_CORE/);
 const s=x.report.requests.find(e=>e.op==='stop'),c=s?.completed;assert.ok(c&&c.result.wire_error===0&&BigInt(c.result.accepted_at)>0n&&c.before.phase===0&&c.before.stop_at==='0'&&c.before.core_fault===0&&c.post.stop_at==='0'&&c.post.core_fault===0);
 assert.equal(x.report.pre_click.stop_at,'0');assert.equal(x.report.frames.moves,0);
 x=run('after');if(x.report.result==='ENV_SERVICE_VIOLATION')throw Object.assign(Error('baseline-after environment obstruction'),{environment:true});assert.equal(x.r.status,0);assert.equal(x.report.result,'PASS');
 fs.writeFileSync(path.join(out,'controls.json'),JSON.stringify({result:'PASS',effective:2,results},null,2));console.log('PASS 2 effective controls; original baseline before/after');
}catch(e){fs.writeFileSync(path.join(out,'controls.json'),JSON.stringify({result:e.environment?'ENV_SERVICE_VIOLATION':'FAIL',verification:e.environment?'NOT_REACHED':'FAIL',effective_credit:0,error:String(e),results},null,2));console.error(e);process.exitCode=1;}
