"""One local binding transaction. No file-progress observer or watchdog."""
from __future__ import annotations
import argparse,base64,ctypes,hashlib,json,os,secrets,subprocess,sys,time,types
from pathlib import Path

REL=Path('outputs/ntp-transaction-104')
SOURCE=Path('src/simulation/ntp_transaction_104/transaction.py')
BASE=Path('src/simulation/ntp_filter_ab_103/actor.py')
PLAN=Path('docs/design/104-direct-ntp-transaction.md')
AUTH=Path('outputs/ntp-filter-ab-103/user-approval.json')
APPROVED='비교 시험 후, 원인이 입증되면 해당 필터만 끈 상태로 복구 진행 (권장)'

def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def validate(root,live=False,request=None):
 root=Path(root).resolve();out=root/REL
 auth=read(root/AUTH)
 if auth.get('explicit_user_approval') is not True or auth.get('user_answer')!=APPROVED or auth.get('target_adapter_GUID','').lower()!='00000000-0000-0000-0000-000000000000':raise RuntimeError('same-target conditional repair approval required')
 l2=read(out/'review/L2-r1.json')
 if l2.get('verdict')!='PASS' or l2['plan']['sha256']!=sha((root/PLAN).read_bytes()):raise RuntimeError('104 L2/plan mismatch')
 raw=(out/'source-freeze.json').read_bytes();freeze=json.loads(raw);members={e['path']:e['sha256'] for e in freeze['files']}
 if len(members)!=len(freeze['files']) or not all(str(p).replace('\\','/') in members for p in [SOURCE,BASE,PLAN]):raise RuntimeError('104 required source census missing/duplicate')
 for entry in freeze['files']:
  if sha((root/entry['path']).read_bytes())!=entry['sha256']:raise RuntimeError('104 frozen input differs: '+entry['path'])
 review=None;review_path=None
 for n in [2,1]:
  f=out/f'review/L4-r{n}.json'
  if f.exists():review=read(f);review_path=f;break
 if not review or review.get('verdict')!='PASS' or review.get('reviewed_freeze_sha256')!=sha(raw):raise RuntimeError('104 current full-wiring L4 PASS required')
 pins={'source_freeze_sha256':sha(raw),'source_sha256':members[SOURCE.as_posix()],'base_sha256':members[BASE.as_posix()],'approval_sha256':sha((root/AUTH).read_bytes()),'review_sha256':sha(review_path.read_bytes())}
 if request:
  for k,v in pins.items():
   if request.get(k)!=v:raise RuntimeError('104 execution pin mismatch '+k)
 if live:
  if globals().get('_bootstrap_source_sha')!=pins['source_sha256'] or not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('reviewed in-memory bootstrap and admin token required')
 return pins

def load_base(root,pins):
 path=Path(root)/BASE;data=path.read_bytes()
 if sha(data)!=pins['base_sha256']:raise RuntimeError('103 dependency changed before exec')
 module=types.ModuleType('frozen_103_library');module.__file__=str(path)
 exec(compile(data,str(path),'exec'),module.__dict__)
 return module

def backend_type(base):
 class Direct(base.Live):
  def __init__(self,root,run,request):
   validate(root,True,request)
   self.root=root;self.run=run;self.request=request;self.inflight=False;self.serial=0;self.deadline=None;self.permanent=False;self.window_id=0;self.io_faults=[];self.force_restore=False;self.guard_process=None;self.rollback_confirmed=False;self.actor_stamp=base.process_stamp(os.getpid());self.last_progress={}
   if type(self.actor_stamp)!=int or self.actor_stamp<=0 or type(request.get('controller_stamp'))!=int or request['controller_stamp']<=0:raise RuntimeError('full process creation identities required')
  def progress(self,phase,**kw):
   # Diagnostic memory only: no filesystem read/write drives restore decisions.
   self.last_progress={'phase':phase,'monotonic':time.monotonic(),**kw}
  def restore_requested(self):
   return bool(self.force_restore or (self.deadline is not None and time.monotonic()>=self.deadline) or not base.process_alive(self.request['controller_pid'],self.request['controller_stamp']))
 return Direct

def run_transaction(base,ops,run,request):
 result={'scope':'104_DIRECT_LOCAL_TRANSACTION_NO_WATCHDOG','network_mutations_before_gate':0,'request_nonce':request['nonce'],'request_sha256':sha((run/'request.json').read_bytes())}
 try:
  result.update(base.trial(ops));result.update({'source_freeze_sha256':request['source_freeze_sha256'],'diagnostic_faults':ops.io_faults})
  base.atomic(run/'result.json',result)
 except Exception as error:
  if ops.permanent and not ops.inflight:
   ops.abort()
   try:
    ops.set_target(True)
    if ops.mapping()!=result.get('proof',{}).get('baseline'):raise RuntimeError('final publication rollback map differs')
    ops.end_window();ops.restored()
   except Exception as restore_error:ops.fault('final-publication-rollback',restore_error)
  result.update({'status':'UNKNOWN_OR_RESTORED_NO_ACCEPTANCE','error':repr(error),'binding_kept_disabled':False if ops.rollback_confirmed else None,'authorized_keep_disabled':False,'inflight_unknown':ops.inflight,'diagnostic_faults':ops.io_faults,'source_freeze_sha256':request['source_freeze_sha256']})
  base.atomic(run/'result.json',result)
 return result

def bootstrap(root,pins,request_sha):
 path=Path(root)/SOURCE
 return "import pathlib,hashlib;p=pathlib.Path("+repr(str(path))+");b=p.read_bytes();assert hashlib.sha256(b).hexdigest()=="+repr(pins['source_sha256'])+";exec(compile(b,str(p),'exec'),{'__name__':'__main__','__file__':str(p),'_bootstrap_source_sha':"+repr(pins['source_sha256'])+",'_args':"+repr(['actor','--root',str(root),'--request-sha',request_sha])+"})"

def actor(root,request_sha):
 run=root/REL/'execution';raw=(run/'request.json').read_bytes()
 if sha(raw)!=request_sha:raise RuntimeError('104 request bytes differ')
 request=json.loads(raw);pins=validate(root,True,request) # before dependency exec
 base=load_base(root,pins);ops=backend_type(base)(root,run,request)
 result=run_transaction(base,ops,run,request)
 # The final file, not console rendering, carries the acceptance contract.
 return result

def execute(root):
 pins=validate(root);base=load_base(root,pins)
 stamp=base.process_stamp(os.getpid())
 if type(stamp)!=int or stamp<=0:raise RuntimeError('controller creation identity missing before UAC')
 run=root/REL/'execution';run.mkdir(exist_ok=False)
 request={**pins,'nonce':secrets.token_hex(24),'controller_pid':os.getpid(),'controller_stamp':stamp,'target':'Wi-Fi/nt_rtf64','no_CAN_no_simulator':True}
 base.atomic(run/'request.json',request);code=bootstrap(root,pins,sha((run/'request.json').read_bytes()))
 args=subprocess.list2cmdline(['-X','utf8','-I','-B','-c',code]).replace("'","''");exe=sys.executable.replace("'","''")
 script="$ErrorActionPreference='Stop';$p=Start-Process -FilePath '"+exe+"' -ArgumentList '"+args+"' -Verb RunAs -WindowStyle Hidden -PassThru;$p.WaitForExit();exit $p.ExitCode"
 p=subprocess.Popen([base.PS,'-NoProfile','-NonInteractive','-Command',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE);start=time.monotonic()
 print('104 UAC/actuator native process pending; phase is unobserved',flush=True)
 while True:
  try:stdout,stderr=p.communicate(timeout=1);break
  except subprocess.TimeoutExpired as timeout:
   if time.monotonic()-start>300:
    # Partial diagnostics are preserved without pretending EOF/capture completion.
    for name,data in [('controller-partial-stdout.raw',timeout.stdout),('controller-partial-stderr.raw',timeout.stderr)]:
     if data is not None:(run/name).write_bytes(data)
    base.atomic(run/'controller-observation-unknown.json',{'status':'UNKNOWN_NATIVE_COMPLETION','capture':'UNKNOWN_NO_EOF_NO_FALSE_EMPTY','stdout_prefix_available':timeout.stdout is not None,'stderr_prefix_available':timeout.stderr is not None,'actor_killed':False,'elapsed_s':time.monotonic()-start})
    # No kill/cancel and no new writer. Controller exit becomes native PID loss.
    raise RuntimeError('104 native completion UNKNOWN after per-invocation bound; actor not killed; manual target-on verification required')
 (run/'launcher-stdout.raw').write_bytes(stdout);(run/'launcher-stderr.raw').write_bytes(stderr)
 base.atomic(run/'launcher-result.json',{'rc':p.returncode,'elapsed_s':time.monotonic()-start,'native_process_completed':True})
 result=read(run/'result.json') # single read after native completion; any read error is fatal UNKNOWN
 if result.get('source_freeze_sha256')!=pins['source_freeze_sha256'] or result.get('request_nonce')!=request['nonce'] or result.get('request_sha256')!=sha((run/'request.json').read_bytes()):raise RuntimeError('104 final result execution binding mismatch')
 if result.get('status')=='CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED':
  receipt=read(run/'acceptance.json');body=receipt['body']
  if receipt.get('body_sha256')!=sha(json.dumps(body,sort_keys=True,separators=(',',':')).encode()) or body.get('run_nonce')!=request['nonce'] or body.get('request_sha256')!=result['request_sha256'] or body.get('source_freeze_sha256')!=pins['source_freeze_sha256'] or body.get('proof')!=result.get('proof'):raise RuntimeError('104 C proof/receipt binding mismatch')
 print(json.dumps(result,ensure_ascii=False),flush=True)
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['execute','actor']);parser.add_argument('--root',required=True,type=Path);parser.add_argument('--request-sha');args=parser.parse_args(globals().get('_args'));root=args.root.resolve()
 if args.mode=='execute':result=execute(root)
 else:result=actor(root,args.request_sha)
 if result['status'] not in ['NO_CHANGE_NEEDED','CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED']:raise SystemExit(1)
if __name__=='__main__':main()
