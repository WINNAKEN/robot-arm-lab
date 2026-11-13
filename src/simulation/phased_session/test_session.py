if __name__=='__main__':raise SystemExit('Use launch.ps1 -Role test')
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

def make(root,purpose='installation_audit'):
    root=Path(root);(root/'runs').mkdir(parents=True,exist_ok=True)
    source=dict(SOURCE);settings=json.loads(source['settings.json'])
    initial=S.read(S.ROOT/'outputs/isaac-phased-v1/evidence/initial-remote.json')
    legacy=base64.b64decode(initial['legacy_ledger_base64']);(root/'legacy.json').write_bytes(legacy)
    settings.update(remote_root=str(root/'runs'),legacy_ledger=str(root/'legacy.json'),legacy_sha256=S.digest(legacy))
    source['settings.json']=json.dumps(settings,indent=2).encode()
    run=root/'runs'/__import__('uuid').uuid4().hex;(run/'input/code').mkdir(parents=True)
    for n,v in S.CORE.items():(run/'input'/n).write_bytes(source[v])
    (run/'input/source-package.json').write_bytes(S.package(source))
    for n,item in settings['references'].items():
        p=run/'input'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((S.ROOT/item['path']).read_bytes())
    inputs={p.relative_to(run/'input').as_posix():S.sha(p) for p in (run/'input').rglob('*') if p.is_file()}
    job={'schema_version':1,'run_id':run.name,'purpose':purpose,'stage':'robot_connection','inputs':inputs,'hardware_approved':False}
    S.write(run/'job.json',job);pins={n:inputs[n] for n in (*S.CORE,'source-package.json')}
    S.write(run/'prepared.json',{'run_id':run.name,'job_sha256':S.sha(run/'job.json'),'pins':pins,'remote':settings['remote_root']+'/'+run.name,'bundle_sha256':'HOST_ONLY'})
    return S.snapshot(run,S.sha(run/'job.json'),pins),source

def shell(c,out,code):S.write(out/'remote-shell.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'python_exit_code':code})

def audit_records(c,out=None,finished=None):
    out=c.run/'output' if out is None else out;out.mkdir(exist_ok=True)
    finished=time.time()-1 if finished is None else finished
    S.write(out/'audit-report.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'pid':23,'status':'INSTALLATION_AUDITED','input_signature':S.signature(c.job),
        'seal_sha256':S.digest(c.data['prefix-seal.json']),'file_count':39919,'bytes':1,'sdk_modules':[],'finished_unix':finished,'host_fixture':True})
    S.write(out/'worker-terminal.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'installation_audit','pid':23,'parent_pid':21,'code':0,'report_sha256':S.sha(out/'audit-report.json')})
    S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'installation_audit','pid':21,'child_pid':23,'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,'started_unix':finished-1,'finished_unix':finished+.1})
    shell(c,out,0)

def row(c):return {'purpose':c.job['purpose'],'run_id':c.run.name,'job_sha256':c.job_hash,'input_signature':S.signature(c.job),'reserved_unix':time.time()}

def cli(c,source):
    folder=c.run.parent.parent/'project/src/simulation/phased_session';folder.mkdir(parents=True,exist_ok=True)
    for n,b in source.items():(folder/n).write_bytes(b)
    return subprocess.run([shutil.which('pwsh') or 'powershell','-NoProfile','-File',str(folder/'launch.ps1'),'-Role','verify','-RunDir',str(c.run)],capture_output=True,timeout=45,creationflags=S.HIDDEN)

class SessionTests(unittest.TestCase):
    def test_snapshot_single_bytes_closed_inputs_and_frozen_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);original=Path.read_bytes;reads=[]
            changed=S.read(c.run/'job.json');changed['purpose']='app_observation'
            def swapping(p):
                raw=original(p)
                if p==c.run/'job.json':reads.append(raw);S.write(p,changed)
                return raw
            with patch.object(Path,'read_bytes',swapping):fresh=S.snapshot(c.run,c.job_hash,c.pins)
            self.assertEqual(len(reads),1);self.assertEqual(fresh.job['purpose'],'installation_audit')
            with self.assertRaises(TypeError):fresh.job['purpose']='app_observation'
            with self.assertRaises(ValueError):S.snapshot(c.run,c.job_hash,c.pins)
            # Frozen numerical/collector definitions can load without initializing SDK.
            k,api=S.frozen_api(c);self.assertEqual(set(k.VALIDATORS),{'static','bodies','trace','contact'})
            self.assertEqual(api['cfg']['hardware_approved'],False)

    def test_streaming_full_audit_positive_changed_missing_and_path(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);c,_=make(td);prefix=td/'prefix';prefix.mkdir()
            (prefix/'a.bin').write_bytes(b'a'*(2*(1<<20)+17));(prefix/'b.txt').write_bytes(b'123')
            seal={'schema_version':1,'files':{p.name:S.sha(p) for p in prefix.iterdir()}}
            ac=c._replace(cfg=S.freeze({**S.plain(c.cfg),'installation_prefix':str(prefix)}),data=S.freeze({**c.data,'prefix-seal.json':json.dumps(seal).encode()}))
            a=S.load_module('audit',c.data['code/audit.py'],c.run/'input/code/audit.py')
            self.assertEqual(a.run(ac,S),0);report=S.read(c.run/'output/audit-report.json')
            self.assertEqual(report['file_count'],2);self.assertEqual(report['bytes'],2*(1<<20)+20);self.assertEqual(report['sdk_modules'],[])
            self.assertEqual(report['configured_workers'],4);self.assertEqual(report['configured_buffer_bytes_each'],1<<20)
            (prefix/'b.txt').write_bytes(b'wrong')
            with self.assertRaises(ValueError):a.run(ac,S)
            (prefix/'b.txt').unlink()
            with self.assertRaises(ValueError):a.run(ac,S)
            bad=copy.deepcopy(seal);bad['files']['../outside']='0'*64
            with self.assertRaises(ValueError):a.run(ac._replace(data=S.freeze({**ac.data,'prefix-seal.json':json.dumps(bad).encode()})),S)

    def test_once_transition_actual_proof_history_and_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            a,_=make(td);b,_=make(td,'app_observation');audit_records(a)
            ledger={'schema_version':1,'legacy_053':S.legacy(a),'reservations':[]}
            self.assertIsNone(S.reservation(a,ledger));ledger['reservations'].append(row(a))
            proof=S.reservation(b,ledger);self.assertIn('audit-report.json',proof)
            with self.assertRaises(ValueError):S.reservation(a,ledger)
            original=S.read(a.run/'output/exit.json')
            for field,value in (('actual_child_exit_code',1),('timed_out',True),('child_pid',99)):
                S.write(a.run/'output/exit.json',{**original,field:value})
                with self.assertRaises(ValueError):S.reservation(b,ledger)
            S.write(a.run/'output/exit.json',original)
            audit_records(a,finished=time.time()-400)
            with self.assertRaises(ValueError):S.reservation(b,ledger)
            # Read-only historical verification remains valid; new authorization expires.
            dest=a.run/'retrieved';shutil.copytree(a.run/'output',dest);S.write(a.run/'transport.json',{'returncode':0})
            self.assertEqual(S.consume(a)[0],0)
            with self.assertRaises(ValueError):S.admit_host(b)
            audit_records(a);shutil.rmtree(dest);shutil.copytree(a.run/'output',dest)
            S.admit_host(b)
            S.write(a.run/'transport.json',{'returncode':1})
            with self.assertRaises(ValueError):S.admit_host(b)
            S.write(a.run.parent.parent/'legacy.json',[])
            with self.assertRaises(ValueError):S.reservation(b,ledger)

    def test_actual_child7_and_timeout_codes_through_public_ps(self):
        with tempfile.TemporaryDirectory() as td:
            c,source=make(td);original=S.run_child
            def child7(argv,out,timeout):return original([sys.executable,'-I','-B','-c','raise SystemExit(7)'],out,10)
            with patch.dict(S.supervise.__globals__,{'run_child':child7}):self.assertEqual(S.supervise(c),7,S.read(c.run/'output/exit.json'))
            ex=S.read(c.run/'output/exit.json');self.assertEqual(ex['actual_child_exit_code'],7);self.assertEqual(ex['policy_exit_code'],7)
            shutil.copytree(c.run/'output',c.run/'retrieved');shell(c,c.run/'retrieved',7);S.write(c.run/'transport.json',{'returncode':1})
            self.assertEqual(S.consume(c)[0],7);p=cli(c,source);self.assertEqual(p.returncode,7,p.stderr)
            d,_=make(td)
            def forbidden(*args):raise AssertionError('must not launch')
            with patch.dict(S.supervise.__globals__,{'run_child':forbidden}):self.assertEqual(S.supervise(d),1)
            e,esource=make(Path(td)/'timeout');out=e.run/'output';out.mkdir()
            result=original([sys.executable,'-I','-B','-c','import time;time.sleep(10)'],out,.15)
            self.assertTrue(result['timed_out']);self.assertEqual(result['policy_exit_code'],124)
            self.assertIs(type(result['actual_child_exit_code']),int);self.assertNotEqual(result['actual_child_exit_code'],124);self.assertEqual(result['cleanup_exit_code'],0)
            print('HOST timeout actual wait code:',result['actual_child_exit_code'],'policy:',result['policy_exit_code'])
            S.write(out/'exit.json',{'run_id':e.run.name,'job_sha256':e.job_hash,'purpose':'installation_audit','pid':os.getpid(),**result})
            shutil.copytree(out,e.run/'retrieved');shell(e,e.run/'retrieved',124);S.write(e.run/'transport.json',{'returncode':1})
            self.assertEqual(S.consume(e)[0],124);p=cli(e,esource);self.assertEqual(p.returncode,124,p.stderr)

    def native_fixture(self,root):
        a,_=make(root);c,source=make(root,'app_observation');k,api=S.frozen_api(c)
        m=types.ModuleType('_fixture053');m.__file__=str(c.run/'input/fixture-053.py');m.API={'kernel':k,'source':{},'root':S.ROOT}
        exec(compile(c.data['fixture-053.py'],m.__file__,'exec'),m.__dict__)
        helper=m.ModelTests();helper.api=lambda run,pins:api
        helper.complete(c.run,c.pins)
        out=c.run/'retrieved';audit_records(a,finished=time.time()-30);proof=out/'audit-proof';proof.mkdir()
        (proof/'job.json').write_bytes((a.run/'job.json').read_bytes())
        for n in S.AUDIT_RECORDS:(proof/n).write_bytes((a.run/'output'/n).read_bytes())
        S.write(proof/'reservation.json',row(a));now=time.time()
        S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'app_observation','pid':11,'child_pid':13,
            'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,'started_unix':now-20,'audit_authorized_unix':now-19,'finished_unix':now})
        shell(c,out,0);S.write(c.run/'transport.json',{'returncode':0})
        return c,source

    def test_cleanup_exception_retains_timeout_and_nonportable_status_policy(self):
        class TimedProcess:
            pid=87654321
            def wait(self,timeout):raise subprocess.TimeoutExpired('HOST_MODEL_ONLY',timeout)
            def poll(self):return None
        with tempfile.TemporaryDirectory() as td:
            c,source=make(td);out=c.run/'output';out.mkdir()
            with patch.object(subprocess,'Popen',return_value=TimedProcess()),patch.object(subprocess,'run',side_effect=OSError('HOST simulated cleanup failure')):
                result=S.run_child(['HOST_MODEL_ONLY'],out,.1)
            self.assertTrue(result['timed_out']);self.assertEqual(result['policy_exit_code'],124);self.assertEqual(result['child_pid'],87654321)
            self.assertIsNone(result['actual_child_exit_code']);self.assertIn('cleanup_error',result);self.assertIn('reap_error',result)
            self.assertEqual(result['child_state'],'RUNNING_OR_NOT_REAPED')
            S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'installation_audit','pid':11,**result})
            shutil.copytree(out,c.run/'retrieved');shell(c,c.run/'retrieved',124);S.write(c.run/'transport.json',{'returncode':1})
            self.assertEqual(S.consume(c)[0],124);self.assertEqual(cli(c,source).returncode,124)
            for status in (3221225477,-1073741819):
                class FinishedProcess:
                    pid=87654321
                    def wait(self,timeout):return status
                d,dsource=make(Path(td)/str(status));dest=d.run/'output';dest.mkdir()
                with patch.object(subprocess,'Popen',return_value=FinishedProcess()):result=S.run_child(['HOST_MODEL_ONLY'],dest,1)
                self.assertFalse(result['timed_out']);self.assertEqual(result['actual_child_exit_code'],status);self.assertEqual(result['policy_exit_code'],1)
                self.assertEqual(result['policy_basis'],'NONPORTABLE_WORKER_EXIT')
                S.write(dest/'exit.json',{'run_id':d.run.name,'job_sha256':d.job_hash,'purpose':'installation_audit','pid':11,**result})
                shutil.copytree(dest,d.run/'retrieved');shell(d,d.run/'retrieved',1);S.write(d.run/'transport.json',{'returncode':1})
                self.assertEqual(S.consume(d)[0],1);self.assertEqual(cli(d,dsource).returncode,1)

    def test_complete_native_positive_mapping_force_inertia_and_transport(self):
        with tempfile.TemporaryDirectory() as td:
            c,source=self.native_fixture(td);out=c.run/'retrieved'
            self.assertTrue(S.consume(c)[1]['sdk_connected']);p=cli(c,source);self.assertEqual(p.returncode,0,p.stderr)
            original=S.read(out/'observations.json');terminal=S.read(out/'terminal.json')
            changes=[lambda p:p['facets']['contact']['mapping'].update(force_frame='LOCAL'),
                lambda p:p['facets']['contact']['sample']['normal_force_N'][0][0].__setitem__(0,99),
                lambda p:p['facets']['static']['bodies'][1]['inertia_diag'].__setitem__(0,p['facets']['static']['bodies'][1]['inertia_diag'][0]+5e-7)]
            for mutate in changes:
                packet=copy.deepcopy(original);mutate(packet);S.write(out/'observations.json',packet)
                S.write(out/'terminal.json',{**terminal,'files_sha256':{**terminal['files_sha256'],'observations.json':S.sha(out/'observations.json')}})
                with self.assertRaises(ValueError):S.consume(c)
            S.write(out/'observations.json',original);S.write(out/'terminal.json',terminal)
            S.write(c.run/'transport.json',{'returncode':1})
            with self.assertRaises(ValueError):S.consume(c)

    def test_actual_worker_audit_entry_contains_no_sdk(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);out=c.run/'output'
            # A direct-script invocation is rejected before adjacent imports.
            for n in ('session.py','audit.py','worker.py','test_session.py'):
                p=Path(td)/n;p.write_bytes(SOURCE[n])
                child=subprocess.run([sys.executable,'-I','-B',str(p)],capture_output=True,timeout=10,creationflags=S.HIDDEN)
                self.assertNotEqual(child.returncode,0)
            (c.run/'input/code/audit.py').write_bytes(b'changed')
            child=subprocess.run([sys.executable,'-I','-B','-c',S.literal(c,'worker')],capture_output=True,timeout=20,creationflags=S.HIDDEN)
            self.assertNotEqual(child.returncode,0);self.assertFalse((out/'audit-report.json').exists())

def run_tests(session,source):
    global S,SOURCE
    S,SOURCE=session,source
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SessionTests))
    return 0 if result.wasSuccessful() else 1
