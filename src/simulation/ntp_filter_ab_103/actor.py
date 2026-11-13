"""Approved local NTP diagnosis; no Isaac or CAN imports. One binding actuator."""
from __future__ import annotations
import argparse,base64,contextlib,ctypes,datetime,hashlib,json,os,secrets,socket,struct,subprocess,sys,time
from pathlib import Path

GUID='00000000-0000-0000-0000-000000000000'
TARGET='nt_rtf64'; PEER='52.231.114.183'
REL=Path('outputs/ntp-filter-ab-103')
SOURCE=Path('src/simulation/ntp_filter_ab_103/actor.py')
PLAN=Path('docs/design/103-local-ntp-filter-ab.md')
def system_ps():
 buffer=ctypes.create_unicode_buffer(32768)
 n=ctypes.windll.kernel32.GetSystemDirectoryW(buffer,len(buffer))
 if not 0<n<len(buffer):raise RuntimeError('trusted system directory unavailable')
 return str(Path(buffer.value)/'WindowsPowerShell'/'v1.0'/'powershell.exe')
PS=system_ps()
APPROVED='비교 시험 후, 원인이 입증되면 해당 필터만 끈 상태로 복구 진행 (권장)'

def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def atomic(p,v):
 p=Path(p);q=p.with_name(p.name+'.'+secrets.token_hex(6)+'.tmp')
 try:
  with q.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(q,p)
 finally:
  if q.exists():q.unlink()
@contextlib.contextmanager
def state_lock(run):
 p=Path(run)/'acceptance.lock';end=time.monotonic()+2;fd=None
 while fd is None:
  try:fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  except FileExistsError:
   if time.monotonic()>=end:raise TrialError('state lock busy; no acceptance/request race')
   time.sleep(.05)
 try:yield
 finally:os.close(fd);p.unlink()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def process_stamp(pid):
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
 k.CloseHandle.argtypes=[ctypes.c_void_p];k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
 k.GetProcessTimes.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
 h=k.OpenProcess(0x1000,False,int(pid))
 if not h:return None
 try:
  code=ctypes.c_ulong();a=ctypes.c_ulonglong();b=ctypes.c_ulonglong();c=ctypes.c_ulonglong();d=ctypes.c_ulonglong()
  if not k.GetExitCodeProcess(h,ctypes.byref(code)) or code.value!=259:return None
  if not k.GetProcessTimes(h,ctypes.byref(a),ctypes.byref(b),ctypes.byref(c),ctypes.byref(d)):return None
  return a.value
 finally:k.CloseHandle(h)
def process_alive(pid,stamp=None):
 if type(stamp)!=int or stamp<=0:return False
 current=process_stamp(pid)
 return current is not None and stamp==current
def gate(root,live=False,request=None):
 root=Path(root).resolve();out=root/REL
 approval=read(out/'user-approval.json')
 if approval.get('explicit_user_approval') is not True or approval.get('user_answer')!=APPROVED:raise RuntimeError('103 conditional approval required')
 l2=read(out/'review/L2-r2.json')
 if l2.get('verdict')!='PASS' or l2['plan']['sha256']!=sha((root/PLAN).read_bytes()):raise RuntimeError('103 L2/plan mismatch')
 freeze=read(out/'source-freeze.json');freeze_sha=sha((out/'source-freeze.json').read_bytes())
 for entry in freeze['files']:
  if sha((root/entry['path']).read_bytes())!=entry['sha256']:raise RuntimeError('source freeze mismatch '+entry['path'])
 l4=None;l4path=None
 for n in [2,1]:
  p=out/f'review/L4-r{n}.json'
  if p.exists():l4=read(p);l4path=p;break
 if not l4 or l4.get('verdict')!='PASS' or l4.get('reviewed_freeze_sha256')!=freeze_sha:raise RuntimeError('103 current L4 PASS/freeze required')
 pins={'source_freeze_sha256':freeze_sha,'approval_sha256':sha((out/'user-approval.json').read_bytes()),'L4_sha256':sha(l4path.read_bytes()),'plan_sha256':sha((root/PLAN).read_bytes()),'source_sha256':sha((root/SOURCE).read_bytes())}
 if request:
  for k,v in pins.items():
   if request.get(k)!=v:raise RuntimeError('request pin mismatch '+k)
 if live:
  if globals().get('_bootstrap_source_sha')!=pins['source_sha256']:raise RuntimeError('live requires hash-checked in-memory bootstrap')
  if not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('administrator token required')
 return pins

def ps(script):
 return [PS,'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()]
def readonly(root,run,label,script,timeout=15):
 start=time.monotonic();p=subprocess.Popen(ps("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"+script),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:o,e=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  p.kill();o,e=p.communicate();(run/(label+'-stdout.raw')).write_bytes(o);(run/(label+'-stderr.raw')).write_bytes(e);raise RuntimeError('read-only timeout '+label)
 (run/(label+'-stdout.raw')).write_bytes(o);(run/(label+'-stderr.raw')).write_bytes(e)
 atomic(run/(label+'.json'),{'rc':p.returncode,'elapsed_s':time.monotonic()-start,'script':script})
 if p.returncode:raise RuntimeError('read-only error '+label+' rc '+str(p.returncode))
 return json.loads(o.decode('utf-8-sig'))

class TrialError(RuntimeError):pass
class UnknownMutation(TrialError):pass

def expected(base,enabled):
 d=dict(base);d[TARGET]=enabled;return d

def trial(ops):
 """The same state machine is run by live OS and fake terminal-order tests."""
 base=ops.mapping();ops.identity()
 if base.get(TARGET) is not True:raise TrialError('baseline target must be enabled')
 proof={'baseline':base,'phases':{}};touched=False;accepted=False
 def check(on):
  if ops.mapping()!=expected(base,on):raise TrialError('whole binding map mismatch')
 def probes(name,on):
  check(on);ops.ready();check(on)
  if not on and ops.restore_requested():raise TrialError('restore requested before probe')
  data=ops.probe(name);proof['phases'][name]=data;check(on)
  if not on and ops.restore_requested():raise TrialError('restore requested after probe')
  return sum(x.get('valid') is True for x in data)==3 and len(data)==3
 def set_to(on):
  nonlocal touched
  if not on and ops.restore_requested():raise TrialError('restore requested before new off')
  touched=True
  if not on:
   ops.begin_window()
   if ops.restore_requested():raise TrialError('restore requested before off dispatch')
  ops.set_target(on) # waits terminal and collects output; NEVER cancels mutation
  if not on and ops.restore_requested():raise TrialError('late mutation terminal: restore only')
  check(on)
  if on:ops.end_window()
 try:
  if probes('A0',True):return {'status':'NO_CHANGE_NEEDED','proof':proof,'binding_kept_disabled':False}
  if len(proof['phases']['A0'])!=3 or any(x.get('valid') for x in proof['phases']['A0']):raise TrialError('A0 partial/ambiguous')
  set_to(False)
  if not probes('B1',False):raise TrialError('B1 not three valid replies')
  set_to(True)
  if probes('A1',True) or any(x.get('valid') for x in proof['phases']['A1']) or len(proof['phases']['A1'])!=3:raise TrialError('A1 did not reproduce failure')
  set_to(False)
  if not probes('C1',False):raise TrialError('C1 not three valid replies')
  check(False)
  # Acceptance is an internal transition, not a mutable-file input.
  ops.accept(proof);accepted=True
  return {'status':'CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED','proof':proof,'binding_kept_disabled':True}
 finally:
  if touched and not accepted:
   if hasattr(ops,'abort'):ops.abort()
   if ops.inflight:raise UnknownMutation('mutation terminal unknown; no competing restore')
   ops.set_target(True)
   if ops.mapping()!=base:raise TrialError('rollback target on but complete map differs: UNKNOWN')
   ops.end_window();ops.restored()

def ntp_sample(ip=PEER,timeout=2.0):
 packet=bytearray(48);packet[0]=0x23;t=time.time()+2208988800;struct.pack_into('!II',packet,40,int(t)&0xffffffff,int((t%1)*2**32))
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(timeout);result={'request_hex':packet.hex(),'target':ip,'started_utc':utc(),'valid':False};start=time.monotonic()
 try:
  s.sendto(packet,(ip,123));data,addr=s.recvfrom(512);result.update({'response_hex':data.hex(),'from':addr})
  if len(data)>=48:result.update({'mode':data[0]&7,'leap':data[0]>>6,'stratum':data[1],'origin_matches':data[24:32]==packet[40:48]});result['valid']=len(data)>=48 and addr[0]==ip and addr[1]==123 and data[0]&7==4 and data[0]>>6!=3 and 1<=data[1]<=15 and data[24:32]==packet[40:48]
 except OSError as e:result.update({'error':str(e),'winerror':getattr(e,'winerror',None)})
 finally:s.close()
 result['elapsed_s']=time.monotonic()-start;return result

class Live:
 def __init__(self,root,run,request):
  gate(root,True,request);self.root=root;self.run=run;self.request=request;self.inflight=False;self.serial=0;self.deadline=None;self.permanent=False;self.window_id=0;self.actor_stamp=process_stamp(os.getpid());self.io_faults=[];self.force_restore=False;self.guard_process=None;self.rollback_confirmed=False
  if type(self.actor_stamp)!=int or self.actor_stamp<=0:raise TrialError('actor creation identity unavailable')
 def fault(self,where,error):
  if not hasattr(self,'io_faults'):self.io_faults=[]
  self.io_faults.append({'where':where,'error':repr(error)});self.force_restore=True
  try:print('103 recovery diagnostic failure '+where+': '+repr(error),file=sys.stderr,flush=True)
  except Exception as secondary:self.io_faults.append({'where':'stderr-fallback','error':repr(secondary)})
 def heartbeat(self,phase,**kw):
  try:self.progress(phase,**kw)
  except Exception as error:self.fault('progress:'+phase,error)
 def abort(self):
  self.permanent=False;self.force_restore=True
  current=self.run/'acceptance.json'
  try:
   if current.exists():os.replace(current,self.run/('acceptance-revoked-'+str(time.monotonic_ns())+'.json'))
  except Exception as error:self.fault('acceptance-revoke',error)
  self.heartbeat('acceptance-aborted-restoring')
 def label(self,prefix):self.serial+=1;return f'{self.serial:03d}-{prefix}'
 def progress(self,phase,**kw):
  atomic(self.run/'progress.json',{'phase':phase,'actor_pid':os.getpid(),'actor_stamp':self.actor_stamp,'controller_pid':self.request['controller_pid'],'heartbeat_monotonic':time.monotonic(),'temporary_deadline':self.deadline,'window_id':self.window_id,'permanent_accepted':self.permanent,**kw})
 def identity(self):
  self.heartbeat('read-identity')
  v=readonly(self.root,self.run,self.label('identity'),"$a=Get-NetAdapter -Name 'Wi-Fi';$p=Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\W32Time\\Parameters';@{guid=$a.InterfaceGuid.ToString();description=$a.InterfaceDescription;peer=$p.NtpServer;type=$p.Type}|ConvertTo-Json -Compress")
  if v['guid'].strip('{}').lower()!=GUID or 'AX211' not in v['description'] or v['peer']!='time.windows.com,0x9' or v['type']!='NTP':raise TrialError('target identity/peer differs')
 def mapping(self):
  self.heartbeat('read-map')
  rows=readonly(self.root,self.run,self.label('map'),"@(Get-NetAdapterBinding -Name 'Wi-Fi' -AllBindings|Select-Object ComponentID,Enabled)|ConvertTo-Json -Compress")
  if not isinstance(rows,list) or not rows or len({x['ComponentID'] for x in rows})!=len(rows) or any(type(x['Enabled'])!=bool for x in rows):raise TrialError('invalid map')
  return {x['ComponentID']:x['Enabled'] for x in rows}
 def ready(self):
  self.heartbeat('link-readiness')
  deadline=time.monotonic()+20
  while True:
   if self.deadline is not None and self.restore_requested():raise TrialError('restore requested while link waiting')
   v=readonly(self.root,self.run,self.label('link'),"@{up=((Get-NetAdapter -Name 'Wi-Fi').Status.ToString() -eq 'Up');ip=@(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4|ForEach-Object IPAddress)}|ConvertTo-Json -Compress",5)
   if v['up'] and '192.0.2.10' in v['ip']:return
   if time.monotonic()>=deadline:raise TrialError('link readiness cutoff')
   time.sleep(.25)
 def begin_window(self):
  self.rollback_confirmed=False;self.window_id+=1;self.deadline=time.monotonic()+45;self.progress('temporary-off-intent')
 def end_window(self):self.deadline=None;self.heartbeat('baseline-restored')
 def restore_requested(self):
  if getattr(self,'force_restore',False) or (self.run/'watchdog-unknown.json').exists():return True
  if self.guard_process is not None and self.guard_process.poll() is not None:return True
  if self.deadline is not None and time.monotonic()>=self.deadline:return True
  p=self.run/'restore-request.json'
  if p.exists():
   d=read(p)
   if d.get('window_id')==self.window_id:return True
  return not process_alive(self.request['controller_pid'],self.request['controller_stamp'])
 def set_target(self,on):
  if self.inflight:raise UnknownMutation('overlapping mutation prohibited')
  label=self.label('enable' if on else 'disable');command='Enable-NetAdapterBinding' if on else 'Disable-NetAdapterBinding'
  script="$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);$j=$null;try{$adapter=Get-NetAdapter -Name 'Wi-Fi';if($adapter.InterfaceGuid.ToString().Trim('{}') -ne '"+GUID+"'){throw 'adapter identity changed'};$binding=Get-NetAdapterBinding -Name 'Wi-Fi' -ComponentID 'nt_rtf64';if(@($binding).Count -ne 1){throw 'target binding ambiguous'};$j="+command+" -InputObject $binding -Confirm:$false -AsJob;while($j.State.ToString() -in @('Running','NotStarted','Blocked')){[void](Wait-Job -Job $j -Timeout 1)};$state=$j.State.ToString();$errors=@();$null=Receive-Job -Job $j -ErrorAction SilentlyContinue -ErrorVariable +errors;@{terminal=$state;errors=@($errors|ForEach-Object {$_.ToString()})}|ConvertTo-Json -Compress}catch{@{terminal=if($j){$j.State.ToString()}else{'NOT_CREATED'};error=$_.Exception.ToString()}|ConvertTo-Json -Compress;exit 1}"
  try:self.progress('mutation-intent',enabled_requested=on)
  except Exception as error:
   self.fault('mutation-intent',error)
   if not on:raise TrialError('no new off after diagnostic failure') from error
  self.inflight=True
  p=subprocess.Popen(ps(script),stdout=subprocess.PIPE,stderr=subprocess.PIPE);start=time.monotonic()
  while True:
   try:stdout,stderr=p.communicate(timeout=1);break
   except subprocess.TimeoutExpired:self.heartbeat('mutation-in-flight',enabled_requested=on,elapsed_s=time.monotonic()-start,restore_pending=self.restore_requested())
  # Determine terminal in memory BEFORE any diagnostic filesystem write.
  terminal_error=None;data=None
  try:
   data=json.loads(stdout.decode('utf-8-sig'))
   if data.get('terminal') not in ['Completed','Failed']:raise ValueError('unconfirmed terminal')
   self.inflight=False
  except (ValueError,UnicodeError) as error:terminal_error=error
  for name,content in [(label+'-stdout.raw',stdout),(label+'-stderr.raw',stderr)]:
   try:(self.run/name).write_bytes(content)
   except Exception as error:self.fault(name,error)
  try:atomic(self.run/(label+'.json'),{'rc':p.returncode,'script':script,'elapsed_s':time.monotonic()-start,'terminal_known':not self.inflight,'terminal_error':repr(terminal_error) if terminal_error else None})
  except Exception as error:self.fault(label+'-metadata',error)
  if terminal_error:raise UnknownMutation('missing or nonterminal mutation receipt') from terminal_error
  if p.returncode or data['terminal']!='Completed' or data.get('errors'):raise TrialError('binding command failed '+str(data))
  if not on and getattr(self,'force_restore',False):raise TrialError('diagnostic failure after off; restoration required')
 def probe(self,name):
  results=[]
  for i in range(3):
   if self.deadline is not None and self.restore_requested():raise TrialError('probe cutoff')
   self.progress('probe-'+name,sample=i);d=ntp_sample();results.append(d);atomic(self.run/(name+'-samples.json'),results)
  return results
 def accept(self,proof):
  with state_lock(self.run):
   if self.restore_requested():raise TrialError('restore requested before C acceptance')
   body={'proof':proof,'request_sha256':sha((self.run/'request.json').read_bytes()),'run_nonce':self.request['nonce'],'source_freeze_sha256':self.request['source_freeze_sha256'],'actor_pid':os.getpid(),'requires_final_result_status':'CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED','accepted_monotonic':time.monotonic()}
   atomic(self.run/'acceptance.json',{'body':body,'body_sha256':sha(json.dumps(body,sort_keys=True,separators=(',',':')).encode())})
   if self.restore_requested():raise TrialError('restore cutoff while persisting C proof')
   self.permanent=True;self.deadline=None;self.progress('C-accepted')
 def restored(self):
  self.rollback_confirmed=True;self.heartbeat('rollback-confirmed')

def watchdog(run,request):
 context=read(run/'actor-context.json')
 if context.get('nonce')!=request['nonce'] or type(context.get('actor_stamp'))!=int or context['actor_stamp']<=0 or type(request.get('controller_stamp'))!=int or request['controller_stamp']<=0:raise RuntimeError('watchdog requires full process identities')
 atomic(run/'watchdog-ready.json',{'pid':os.getpid(),'nonce':request['nonce']})
 while not (run/'result.json').exists():
  p=run/'progress.json'
  if not process_alive(context['actor_pid'],context['actor_stamp']):
   atomic(run/'watchdog-unknown.json',{'status':'UNKNOWN_ACTOR_LOST_NO_COMPETING_ENABLE','manual_restore':"Enable-NetAdapterBinding -Name 'Wi-Fi' -ComponentID 'nt_rtf64' -Confirm:$false"});return
  if p.exists():
   try:data=read(p)
   except (OSError,ValueError):time.sleep(.1);continue
  else:data={'actor_pid':context['actor_pid'],'actor_stamp':context['actor_stamp'],'heartbeat_monotonic':context['started_monotonic'],'temporary_deadline':None,'window_id':0,'permanent_accepted':False}
  stale=time.monotonic()-data.get('heartbeat_monotonic',context['started_monotonic'])>30
  due=data.get('temporary_deadline') is not None and time.monotonic()>=data['temporary_deadline']
  lost=not process_alive(request['controller_pid'],request['controller_stamp'])
  if stale or due or lost:
   try:
    with state_lock(run):
     current=read(p) if p.exists() else data
     stale_now=time.monotonic()-current.get('heartbeat_monotonic',context['started_monotonic'])>30
     due_now=current.get('temporary_deadline') is not None and time.monotonic()>=current['temporary_deadline']
     lost_now=not process_alive(request['controller_pid'],request['controller_stamp'])
     if stale_now:atomic(run/'watchdog-unknown.json',{'status':'UNKNOWN_HEARTBEAT_STALE_RESTORE_REQUESTED','age_s':time.monotonic()-current['heartbeat_monotonic']})
     if (stale_now or due_now or lost_now) and not current.get('permanent_accepted'):
      atomic(run/'restore-request.json',{'window_id':current['window_id'],'reason':'stale-cutoff-or-controller-loss','monotonic':time.monotonic()})
   except TrialError as error:atomic(run/'watchdog-lock-delay.json',{'error':str(error),'monotonic':time.monotonic()})
  time.sleep(.25)

def bootstrap(root,request_sha,mode):
 source=Path(root)/SOURCE;digest=sha(source.read_bytes())
 return "import pathlib,hashlib; p=pathlib.Path("+repr(str(source))+ "); b=p.read_bytes(); assert hashlib.sha256(b).hexdigest()=="+repr(digest)+"; exec(compile(b,str(p),'exec'),{'__name__':'__main__','__file__':str(p),'_bootstrap_source_sha':"+repr(digest)+",'_bootstrap_args':"+repr([mode,'--root',str(root),'--request-sha',request_sha])+"})"

def actor(root,request_sha):
 out=root/REL;run=out/'execution';request=read(run/'request.json')
 if sha((run/'request.json').read_bytes())!=request_sha:raise RuntimeError('request hash mismatch')
 gate(root,True,request)
 stamp=process_stamp(os.getpid())
 if type(stamp)!=int or stamp<=0 or type(request.get('controller_stamp'))!=int or request['controller_stamp']<=0:raise RuntimeError('process creation identity required before watchdog or mutation')
 atomic(run/'actor-context.json',{'actor_pid':os.getpid(),'actor_stamp':stamp,'nonce':request['nonce'],'started_monotonic':time.monotonic()})
 wout=(run/'watchdog-stdout.raw').open('xb');werr=(run/'watchdog-stderr.raw').open('xb')
 guard=subprocess.Popen([sys.executable,'-X','utf8','-I','-B','-c',bootstrap(root,request_sha,'watchdog')],stdout=wout,stderr=werr,creationflags=subprocess.CREATE_NO_WINDOW)
 wout.close();werr.close()
 deadline=time.monotonic()+10
 while not (run/'watchdog-ready.json').exists():
  if guard.poll() is not None or time.monotonic()>deadline:raise RuntimeError('watchdog not ready')
  time.sleep(.1)
 ready=read(run/'watchdog-ready.json')
 if ready.get('nonce')!=request['nonce'] or ready.get('pid')!=guard.pid:raise RuntimeError('watchdog readiness identity mismatch')
 ops=Live(root,run,request);ops.guard_process=guard;result={'started_utc':utc(),'network_mutations_before_gate':0}
 try:
  result.update(trial(ops));result.update({'finished_utc':utc(),'source_freeze_sha256':request['source_freeze_sha256'],'diagnostic_faults':ops.io_faults})
  atomic(run/'result.json',result)
 except Exception as error:
  if ops.permanent and not ops.inflight:
   ops.abort()
   try:
    ops.set_target(True)
    if ops.mapping()!=result.get('proof',{}).get('baseline'):raise TrialError('publication failure rollback map differs')
    ops.end_window();ops.restored()
   except Exception as restore_error:ops.fault('publication-rollback',restore_error)
  result.update({'status':'UNKNOWN_OR_RESTORED_NO_ACCEPTANCE','error':repr(error),'inflight_unknown':ops.inflight,'binding_kept_disabled':False if ops.rollback_confirmed else None,'authorized_keep_disabled':False,'diagnostic_faults':ops.io_faults,'finished_utc':utc(),'source_freeze_sha256':request['source_freeze_sha256']})
  atomic(run/'result.json',result)
 print(json.dumps(result,ensure_ascii=False),flush=True)

def execute(root):
 pins=gate(root);out=root/REL;run=out/'execution';stamp=process_stamp(os.getpid())
 if type(stamp)!=int or stamp<=0:raise RuntimeError('controller creation identity required before UAC')
 run.mkdir(exist_ok=False)
 request={**pins,'nonce':secrets.token_hex(24),'controller_pid':os.getpid(),'controller_stamp':stamp,'created_utc':utc(),'approved_target':TARGET,'approved_GUID':GUID}
 atomic(run/'request.json',request);request_sha=sha((run/'request.json').read_bytes());code=bootstrap(root,request_sha,'actor')
 args=subprocess.list2cmdline(['-X','utf8','-I','-B','-c',code]).replace("'","''");exe=sys.executable.replace("'","''")
 launch="$ErrorActionPreference='Stop';$p=Start-Process -FilePath '"+exe+"' -ArgumentList '"+args+"' -Verb RunAs -WindowStyle Hidden -PassThru;$p.WaitForExit();exit $p.ExitCode"
 p=subprocess.Popen([PS,'-NoProfile','-NonInteractive','-Command',launch],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 last=None
 while p.poll() is None:
  try:d=read(run/'progress.json');phase=d.get('phase')
  except (OSError,ValueError):phase='UAC-or-startup'
  if phase!=last:print('103 '+str(phase),flush=True);last=phase
  time.sleep(1)
 stdout,stderr=p.communicate();(run/'launcher-stdout.raw').write_bytes(stdout);(run/'launcher-stderr.raw').write_bytes(stderr);atomic(run/'launcher-result.json',{'rc':p.returncode})
 if not (run/'result.json').exists():raise RuntimeError('actuator result absent; inspect UAC/guard before any retry')
 print(json.dumps(read(run/'result.json'),ensure_ascii=False),flush=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['execute','actor','watchdog']);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--request-sha');args=parser.parse_args(globals().get('_bootstrap_args'))
 root=args.root.resolve()
 if args.mode=='execute':execute(root)
 elif args.mode=='actor':actor(root,args.request_sha)
 else:
  run=root/REL/'execution';request=read(run/'request.json')
  if sha((run/'request.json').read_bytes())!=args.request_sha:raise RuntimeError('watchdog request mismatch')
  watchdog(run,request)
if __name__=='__main__':main()
