import contextlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('actor103',HERE/'actor.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
@contextlib.contextmanager
def fixture():
 root=HERE.parents[2].resolve();base=(root/'outputs/ntp-filter-ab-103/host-fixtures').resolve()
 if not base.is_relative_to(root):raise RuntimeError('fixture outside workspace')
 base.mkdir(parents=True,exist_ok=True)
 # Kept as diagnostic evidence. No recursive cleanup in a sandbox Temp ACL.
 yield tempfile.mkdtemp(prefix='case-',dir=base)
class Fake:
 def __init__(self,case='success'):
  self.case=case;self.map={a.TARGET:True,'ms_tcpip':True,'other':False};self.inflight=False;self.events=[];self.restoring=False;self.window=0;self.accepted=False
 def mapping(self):return dict(self.map)
 def identity(self):self.events.append('identity')
 def ready(self):self.events.append('ready')
 def begin_window(self):self.window+=1;self.events.append('window')
 def end_window(self):self.restoring=False;self.events.append('window-end')
 def restored(self):self.events.append('restored')
 def restore_requested(self):return self.restoring
 def set_target(self,on):
  assert not self.inflight;self.inflight=True;self.events.append(('start',on))
  if self.case=='unknown' and not on:raise a.UnknownMutation('no terminal')
  self.map[a.TARGET]=on
  if self.case=='collateral' and not on:self.map['other']=True
  if self.case=='late' and not on:self.restoring=True
  self.inflight=False;self.events.append(('terminal',on))
  if self.case=='failed' and not on:raise a.TrialError('failed after mutation')
 def probe(self,name):
  self.events.append(('probe',name))
  if self.case=='already':ok=True
  elif self.case=='A1-good' and name=='A1':ok=True
  elif self.case=='B-fail' and name=='B1':ok=False
  elif self.case=='C-fail' and name=='C1':ok=False
  else:ok=name in ['B1','C1']
  n=2 if self.case=='partial' and name=='B1' else 3
  return [{'valid':ok} for _ in range(n)]
 def accept(self,proof):self.accepted=True;self.events.append('accepted')
class Policy(unittest.TestCase):
 def test_success(self):
  f=Fake();r=a.trial(f);self.assertEqual(r['status'],'CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED');self.assertFalse(f.map[a.TARGET]);self.assertTrue(f.accepted)
  self.assertEqual([e for e in f.events if isinstance(e,tuple) and e[0]=='start'],[('start',False),('start',True),('start',False)])
 def test_already_no_mutation(self):
  f=Fake('already');self.assertEqual(a.trial(f)['status'],'NO_CHANGE_NEEDED');self.assertFalse(any(isinstance(e,tuple) and e[0]=='start' for e in f.events))
 def test_partial_and_probe_failures_restore(self):
  for case in ['partial','B-fail','C-fail','A1-good','failed']:
   with self.subTest(case=case):
    f=Fake(case)
    with self.assertRaises(a.TrialError):a.trial(f)
    self.assertTrue(f.map[a.TARGET]);self.assertFalse(f.accepted)
 def test_collateral_no_B_probe_or_C(self):
  f=Fake('collateral')
  with self.assertRaisesRegex(a.TrialError,'complete map differs'):a.trial(f)
  self.assertTrue(f.map[a.TARGET]);self.assertTrue(f.map['other']);self.assertNotIn(('probe','B1'),f.events);self.assertFalse(f.accepted)
 def test_late_terminal_then_enable_not_parallel(self):
  f=Fake('late')
  with self.assertRaises(a.TrialError):a.trial(f)
  self.assertLess(f.events.index(('terminal',False)),f.events.index(('start',True)));self.assertNotIn(('probe','B1'),f.events)
 def test_unknown_terminal_never_competing_enable(self):
  f=Fake('unknown')
  with self.assertRaises(a.UnknownMutation):a.trial(f)
  self.assertNotIn(('start',True),f.events);self.assertFalse(f.accepted)
 def test_restore_requested_before_off_prevents_mutation(self):
  f=Fake();f.restoring=True
  with self.assertRaises(a.TrialError):a.trial(f)
  self.assertNotIn(('start',False),f.events)
 def test_baseline_off_is_no_authority(self):
  f=Fake();f.map[a.TARGET]=False
  with self.assertRaises(a.TrialError):a.trial(f)
  self.assertNotIn(('start',True),f.events)
class Packet(unittest.TestCase):
 def sample(self,change=None):
  class Sock:
   def settimeout(self,t):pass
   def sendto(self,p,target):self.request=p
   def recvfrom(self,n):
    b=bytearray(48);b[0]=0x24;b[1]=2;b[24:32]=self.request[40:48];ip=a.PEER
    if change=='LI':b[0]|=0xc0
    if change=='stratum':b[1]=0
    if change=='mode':b[0]=0x23
    if change=='origin':b[24:32]=bytes(8)
    if change=='ip':ip='127.0.0.1'
    if change=='short':b=b[:20]
    return bytes(b),(ip,123)
   def close(self):pass
  with patch.object(a.socket,'socket',return_value=Sock()):return a.ntp_sample()
 def test_valid_response(self):self.assertTrue(self.sample()['valid'])
 def test_reject_bad_packets(self):
  for case in ['LI','stratum','mode','origin','ip','short']:
   with self.subTest(case=case):self.assertFalse(self.sample(case)['valid'])
class NativeWait(unittest.TestCase):
 def test_timeouts_poll_without_kill_and_terminal_output(self):
  scripts=[]
  class Proc:
   returncode=0;n=0
   def communicate(self,timeout=None):
    self.n+=1
    if self.n<=2:raise subprocess.TimeoutExpired('fake',1)
    return b'{"terminal":"Completed","errors":[]}',b''
   def kill(self):raise AssertionError('mutation must not be killed')
  with fixture() as td:
   f=object.__new__(a.Live);f.run=Path(td);f.serial=0;f.inflight=False;f.progress=lambda *x,**y:None;f.restore_requested=lambda:False
   with patch.object(a.subprocess,'Popen',side_effect=lambda cmd,**kwargs:(scripts.append(cmd) or Proc())):f.set_target(False)
   self.assertFalse(f.inflight);self.assertTrue(scripts)
   import base64
   script=base64.b64decode(scripts[0][-1]).decode('utf-16-le');self.assertIn('-AsJob',script);self.assertIn('Receive-Job',script);self.assertNotIn('Stop-Job',script)
   p=subprocess.run(a.ps("$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::ParseInput([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+scripts[0][-1]+"')),[ref]$t,[ref]$e);if($e.Count){$e|Out-String;exit 1}"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
   self.assertEqual(p.returncode,0,p.stdout)
 def test_unexpected_terminal_stays_unknown(self):
  class Proc:
   returncode=1
   def communicate(self,timeout=None):return b'{"terminal":"Stopped"}',b''
  with fixture() as td:
   f=object.__new__(a.Live);f.run=Path(td);f.serial=0;f.inflight=False;f.progress=lambda *x,**y:None
   with patch.object(a.subprocess,'Popen',return_value=Proc()):
    with self.assertRaises(a.UnknownMutation):f.set_target(False)
   self.assertTrue(f.inflight)
class Gate(unittest.TestCase):
 def test_no_approval_no_process(self):
  with fixture() as td,patch.object(a.subprocess,'Popen',side_effect=AssertionError('no launch before gate')):
   with self.assertRaises(FileNotFoundError):a.execute(Path(td))
 def test_inactive_direct_live_no_bootstrap(self):
  with fixture() as td:
   with self.assertRaises((FileNotFoundError,RuntimeError)):a.gate(Path(td),live=True,request={})
 def test_pid_identity(self):
  import os
  stamp=a.process_stamp(os.getpid());self.assertTrue(a.process_alive(os.getpid(),stamp));self.assertFalse(a.process_alive(os.getpid(),stamp+1))


_real_live=a.Live
class MetaFake(Fake):
 def __init__(self,folder,kind='success'):
  super().__init__();self.run=Path(folder);self.request={'nonce':'host-fake','source_freeze_sha256':'host-fake'};self.deadline=None;self.permanent=False;self.force_restore=False;self.io_faults=[];self.rollback_confirmed=False;self.kind=kind;self.serial=0
  (self.run/'request.json').write_text(json.dumps(self.request),encoding='utf-8')
 def progress(self,phase,**kw):
  if self.kind=='progress-fail' and phase=='C-accepted':raise OSError('fake C progress failure')
 def accept(self,proof):
  if self.kind=='cutoff':
   with patch.object(self,'restore_requested',side_effect=[False,True]):return _real_live.accept(self,proof)
  return _real_live.accept(self,proof)
 def restored(self):self.rollback_confirmed=True;super().restored()
 abort=a.Live.abort;fault=a.Live.fault;heartbeat=a.Live.heartbeat
class Repairs(unittest.TestCase):
 def live(self,td):
  f=object.__new__(a.Live);f.run=Path(td);f.serial=0;f.inflight=False;f.progress=lambda *x,**y:None;f.restore_requested=lambda:False;f.io_faults=[];f.force_restore=False
  return f
 def proc(self,calls):
  class Proc:
   returncode=0
   def communicate(self,timeout=None):return b'{"terminal":"Completed","errors":[]}',b''
  return lambda *args,**kwargs:(calls.append(args[0]) or Proc())
 def test_rollback_progress_failure_does_not_block_enable(self):
  with fixture() as td:
   f=self.live(td);calls=[]
   f.progress=lambda *x,**y:(_ for _ in ()).throw(OSError('fake disk full'))
   with patch.object(a.subprocess,'Popen',side_effect=self.proc(calls)):f.set_target(True)
   self.assertEqual(len(calls),1);self.assertFalse(f.inflight);self.assertTrue(f.io_faults)
 def test_raw_failure_after_terminal_preserves_terminal_and_restore(self):
  with fixture() as td:
   f=self.live(td);calls=[]
   with patch.object(a.subprocess,'Popen',side_effect=self.proc(calls)),patch.object(Path,'write_bytes',side_effect=OSError('fake raw write failure')):
    with self.assertRaises(a.TrialError):f.set_target(False)
    self.assertFalse(f.inflight);f.set_target(True)
   self.assertEqual(len(calls),2);self.assertFalse(f.inflight)
 def test_C_abort_removes_canonical_receipt_and_permanent_flag(self):
  for kind in ['cutoff','progress-fail']:
   with self.subTest(kind=kind),fixture() as td:
    f=MetaFake(td,kind)
    with self.assertRaises((a.TrialError,OSError)):a.trial(f)
    self.assertTrue(f.map[a.TARGET]);self.assertFalse(f.permanent);self.assertFalse((Path(td)/'acceptance.json').exists());self.assertTrue(list(Path(td).glob('acceptance-revoked-*')))
 def test_stale_heartbeat_alive_actor_is_unknown_not_silent(self):
  with fixture() as td:
   run=Path(td);req={'nonce':'host-only','controller_pid':77,'controller_stamp':123}
   a.atomic(run/'actor-context.json',{'nonce':req['nonce'],'actor_pid':88,'actor_stamp':456,'started_monotonic':a.time.monotonic()-1000})
   a.atomic(run/'progress.json',{'actor_pid':88,'actor_stamp':456,'heartbeat_monotonic':a.time.monotonic()-1000,'temporary_deadline':None,'window_id':1,'permanent_accepted':False})
   calls=[0]
   def stop_sleep(t):
    calls[0]+=1
    if calls[0]>=2:raise StopIteration('bounded fake watchdog')
   with patch.object(a,'process_alive',return_value=True),patch.object(a.time,'sleep',side_effect=stop_sleep),patch.object(a.subprocess,'Popen',side_effect=AssertionError('watchdog never mutates')):
    with self.assertRaises(StopIteration):a.watchdog(run,req)
   self.assertEqual(a.read(run/'watchdog-unknown.json')['status'],'UNKNOWN_HEARTBEAT_STALE_RESTORE_REQUESTED');self.assertTrue((run/'restore-request.json').exists())
 def test_missing_creation_stamp_is_not_PID_only_success(self):
  with patch.object(a,'process_stamp',return_value=999):
   self.assertFalse(a.process_alive(77,None));self.assertFalse(a.process_alive(77,False));self.assertFalse(a.process_alive(77,123));self.assertTrue(a.process_alive(77,999))
 def test_missing_controller_stamp_blocks_before_UAC(self):
  with fixture() as td,patch.object(a,'gate',return_value={}),patch.object(a,'process_stamp',return_value=None),patch.object(a.subprocess,'Popen',side_effect=AssertionError('no UAC')):
   with self.assertRaisesRegex(RuntimeError,'controller creation'):a.execute(Path(td))
   self.assertFalse((Path(td)/a.REL/'execution').exists())
 def test_watchdog_missing_stamp_blocks_before_ready(self):
  with fixture() as td:
   run=Path(td);a.atomic(run/'actor-context.json',{'nonce':'host','actor_stamp':None})
   with self.assertRaisesRegex(RuntimeError,'full process'):a.watchdog(run,{'nonce':'host','controller_stamp':123})
   self.assertFalse((run/'watchdog-ready.json').exists())
 def test_publication_failure_reverts_success_receipt_and_binding_flag(self):
  with fixture() as td:
   root=Path(td);run=root/a.REL/'execution';run.mkdir(parents=True);f=MetaFake(run);request={'nonce':'host-fake','controller_pid':77,'controller_stamp':123,'source_freeze_sha256':'host-fake'};a.atomic(run/'request.json',request);f.request=request
   class Guard:
    pid=99
    def poll(self):return None
   a.atomic(run/'watchdog-ready.json',{'pid':99,'nonce':request['nonce']});normal=a.atomic
   def fail_success(p,v):
    if Path(p).name=='result.json' and v.get('status')=='CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED':raise OSError('fake final publication failure')
    return normal(p,v)
   with patch.object(a,'gate',return_value={}),patch.object(a,'process_stamp',return_value=456),patch.object(a,'bootstrap',return_value='host-fake'),patch.object(a.subprocess,'Popen',return_value=Guard()),patch.object(a,'Live',return_value=f),patch.object(a,'atomic',side_effect=fail_success):a.actor(root,a.sha((run/'request.json').read_bytes()))
   result=a.read(run/'result.json');self.assertEqual(result['status'],'UNKNOWN_OR_RESTORED_NO_ACCEPTANCE');self.assertFalse(result['binding_kept_disabled']);self.assertTrue(f.map[a.TARGET]);self.assertFalse(f.permanent);self.assertFalse((run/'acceptance.json').exists())
if __name__=='__main__':unittest.main(verbosity=2)
