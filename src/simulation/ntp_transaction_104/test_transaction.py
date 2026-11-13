import contextlib,importlib.util,json,os,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
t=module('txn104',HERE/'transaction.py')
base=t.load_base(ROOT,{'base_sha256':t.sha((ROOT/t.BASE).read_bytes())})
oldtests=module('prior103tests',ROOT/'src/simulation/ntp_filter_ab_103/test_actor.py')
@contextlib.contextmanager
def fixture():
 parent=(ROOT/t.REL/'host-fixtures').resolve()
 if not parent.is_relative_to(ROOT.resolve()):raise RuntimeError('fixture escapes workspace')
 parent.mkdir(parents=True,exist_ok=True);yield Path(tempfile.mkdtemp(prefix='case-',dir=parent))
def wired(run,case='success'):
 klass=t.backend_type(base)
 with patch.object(t,'validate',return_value={}),patch.object(base,'process_stamp',return_value=456):obj=klass(ROOT,run,{'nonce':'host-only','source_freeze_sha256':'host-only','controller_pid':77,'controller_stamp':123})
 oldtests.Fake.__init__(obj,case);obj.run=run;obj.request={'nonce':'host-only','source_freeze_sha256':'host-only','controller_pid':77,'controller_stamp':123};obj.io_faults=[];obj.force_restore=False;obj.deadline=None;obj.permanent=False;obj.rollback_confirmed=False
 for name in ['mapping','identity','ready','set_target','probe','begin_window','end_window']:
  setattr(obj,name,types.MethodType(getattr(oldtests.Fake,name),obj))
 def restored(self):self.rollback_confirmed=True;oldtests.Fake.restored(self)
 obj.restored=types.MethodType(restored,obj)
 base.atomic(run/'request.json',obj.request)
 return obj
class Wiring(unittest.TestCase):
 def test_old_forbidden_entries_not_reached_success(self):
  with fixture() as run,patch.object(base,'process_alive',return_value=True):
   forbid=lambda *a,**k:(_ for _ in ()).throw(AssertionError('forbidden old entry'))
   with patch.object(base,'gate',side_effect=forbid),patch.object(base,'actor',side_effect=forbid),patch.object(base,'watchdog',side_effect=forbid),patch.object(base,'execute',side_effect=forbid),patch.object(base.subprocess,'Popen',side_effect=forbid):
    ops=wired(run);result=t.run_transaction(base,ops,run,ops.request)
   self.assertEqual(result['status'],'CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED');self.assertFalse(ops.map[base.TARGET]);self.assertTrue((run/'acceptance.json').exists());self.assertEqual(result['request_nonce'],'host-only')
 def test_no_file_observation_even_corrupt_or_unreadable_progress(self):
  with fixture() as run,patch.object(base,'process_alive',return_value=True):
   obj=wired(run);(run/'progress.json').write_text('NOT JSON',encoding='utf-8');(run/'restore-request.json').write_text('NOT JSON',encoding='utf-8');(run/'watchdog-unknown.json').write_text('NOT JSON',encoding='utf-8')
   with patch.object(base,'read',side_effect=OSError('all progress reads fail')),patch.object(base,'atomic',side_effect=AssertionError('progress must stay in memory')):
    obj.progress('test');self.assertFalse(obj.restore_requested());obj.deadline=time.monotonic()-100;self.assertTrue(obj.restore_requested())
 def test_controller_identity_loss_and_memory_fault_force_restore(self):
  with fixture() as run:
   obj=wired(run)
   with patch.object(base,'process_alive',return_value=False):self.assertTrue(obj.restore_requested())
   with patch.object(base,'process_alive',return_value=True):obj.force_restore=True;self.assertTrue(obj.restore_requested())
 def test_new_wiring_failures_restore_or_unknown_no_C(self):
  for case in ['partial','B-fail','C-fail','A1-good','collateral','unknown','failed']:
   with self.subTest(case=case),fixture() as run,patch.object(base,'process_alive',return_value=True),patch.object(base.subprocess,'Popen',side_effect=AssertionError('host only')):
    obj=wired(run,case);r=t.run_transaction(base,obj,run,obj.request);self.assertEqual(r['status'],'UNKNOWN_OR_RESTORED_NO_ACCEPTANCE');self.assertFalse(obj.permanent);self.assertFalse((run/'acceptance.json').exists())
    if case!='unknown':self.assertTrue(obj.map[base.TARGET])
 def test_new_wiring_publication_failure_revokes_before_restore(self):
  with fixture() as run,patch.object(base,'process_alive',return_value=True):
   obj=wired(run);normal=base.atomic
   def fail(p,v):
    if Path(p).name=='result.json' and v.get('status')=='CAUSAL_ABA_C_CONFIRMED_TARGET_DISABLED':raise OSError('fake full disk at commit')
    return normal(p,v)
   with patch.object(base,'atomic',side_effect=fail):r=t.run_transaction(base,obj,run,obj.request)
   self.assertEqual(r['status'],'UNKNOWN_OR_RESTORED_NO_ACCEPTANCE');self.assertFalse(r['binding_kept_disabled']);self.assertTrue(obj.map[base.TARGET]);self.assertFalse(obj.permanent);self.assertFalse((run/'acceptance.json').exists())
 def test_creation_identity_required_before_backend(self):
  with fixture() as run,patch.object(t,'validate',return_value={}),patch.object(base,'process_stamp',return_value=None):
   with self.assertRaisesRegex(RuntimeError,'creation identities'):t.backend_type(base)(ROOT,run,{'controller_stamp':123})
class GateAndLoader(unittest.TestCase):
 def test_direct_backend_constructor_denied_without_gate(self):
  with fixture() as root,patch.object(base.subprocess,'Popen',side_effect=AssertionError('no native mutation')):
   with self.assertRaises((FileNotFoundError,RuntimeError)):t.backend_type(base)(root,root,{})
 def test_controller_denied_before_dependency_exec_or_UAC(self):
  with fixture() as root,patch.object(t,'load_base',side_effect=AssertionError('no exec')),patch.object(t.subprocess,'Popen',side_effect=AssertionError('no UAC')):
   with self.assertRaises((FileNotFoundError,RuntimeError)):t.execute(root)
 def test_actor_request_denied_before_dependency_exec(self):
  with fixture() as root,patch.object(t,'load_base',side_effect=AssertionError('no exec')):
   run=root/t.REL/'execution';run.mkdir(parents=True);(run/'request.json').write_text('{}',encoding='utf-8')
   with self.assertRaisesRegex(RuntimeError,'request bytes'):t.actor(root,'wrong')
 def test_dependency_bytes_reject_changed_code_before_exec(self):
  with fixture() as root,patch.object(t,'BASE',Path('base.py')):
   path=root/'base.py';path.write_text('raise AssertionError("must not execute")',encoding='utf-8')
   with self.assertRaisesRegex(RuntimeError,'dependency changed'):t.load_base(root,{'base_sha256':'wrong'})
 def test_dependency_execs_the_same_verified_buffer(self):
  with fixture() as root,patch.object(t,'BASE',Path('base.py')):
   path=root/'base.py';first=b'value="A"';path.write_bytes(first);original=Path.read_bytes
   def swap(p):
    data=original(p)
    if p==path:path.write_bytes(b'value="B"')
    return data
   with patch.object(Path,'read_bytes',swap):m=t.load_base(root,{'base_sha256':t.sha(first)})
   self.assertEqual(m.value,'A');self.assertIn(b'B',path.read_bytes())

class ControllerTimeout(unittest.TestCase):
 def test_native_timeout_unknown_prefix_and_never_kill(self):
  with fixture() as root:
   (root/t.REL).mkdir(parents=True)
   class Proc:
    def communicate(self,timeout=None):raise t.subprocess.TimeoutExpired('host-only',1,output=b'known-prefix',stderr=b'known-error')
    def kill(self):raise AssertionError('actor/proxy must not be killed')
   with patch.object(t,'validate',return_value={'source_sha256':'host-fake'}),patch.object(t,'load_base',return_value=base),patch.object(base,'process_stamp',return_value=123),patch.object(t,'bootstrap',return_value='host-fake'),patch.object(t.subprocess,'Popen',return_value=Proc()),patch.object(t.time,'monotonic',side_effect=[0,301,302]):
    with self.assertRaisesRegex(RuntimeError,'UNKNOWN'):t.execute(root)
   run=root/t.REL/'execution';self.assertEqual((run/'controller-partial-stdout.raw').read_bytes(),b'known-prefix');self.assertEqual((run/'controller-partial-stderr.raw').read_bytes(),b'known-error');self.assertEqual(t.read(run/'controller-observation-unknown.json')['capture'],'UNKNOWN_NO_EOF_NO_FALSE_EMPTY')

if __name__=='__main__':unittest.main(verbosity=2)
