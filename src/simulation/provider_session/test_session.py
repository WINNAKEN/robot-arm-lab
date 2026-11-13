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

def make(root,purpose='installation_audit',profile=None):
    root=Path(root);(root/'runs').mkdir(parents=True,exist_ok=True)
    source=dict(SOURCE);settings=json.loads(source['settings.json'])
    initial=S.read(S.ROOT/'outputs/isaac-provider-v1/evidence/initial-remote.json')
    legacy=base64.b64decode(initial['ledger_base64']);(root/'legacy.json').write_bytes(legacy)
    settings.update(remote_root=str(root/'runs'),legacy_ledger=str(root/'legacy.json'),legacy_sha256=S.digest(legacy))
    source['settings.json']=json.dumps(settings,indent=2).encode()
    run=root/'runs'/__import__('uuid').uuid4().hex;(run/'input/code').mkdir(parents=True)
    for n,v in S.CORE.items():(run/'input'/n).write_bytes(source[v])
    (run/'input/source-package.json').write_bytes(S.package(source))
    for n,item in settings['references'].items():
        p=run/'input'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((S.ROOT/item['path']).read_bytes())
    inputs={p.relative_to(run/'input').as_posix():S.sha(p) for p in (run/'input').rglob('*') if p.is_file()}
    job={'schema_version':1,'run_id':run.name,'purpose':purpose,'stage':'robot_connection','inputs':inputs,'hardware_approved':False,'profile':profile}
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

def observation(c,good=True):
    modules={}
    for i,(name,version) in enumerate(S.EXPECTED.items()):
        root=c.cfg[name+'_root'] if name in ('warp','numpy','scipy') else c.cfg['installation_prefix']+'/'+name
        modules[name]={'status':'OBSERVED','origin':str(Path(root)/'__init__.py'),'version':version,'module_id':i+10,'distribution_version':version,'distribution_root':c.cfg['installation_prefix']}
    torch=modules['torch'];origin=torch['origin'] if good else c.cfg['isaac_root']+'/old/torch/__init__.py'
    version=torch['version'] if good else '2.7.0+cu128'
    torch.update(origin=origin,version=version)
    t={'state':'OBSERVED','origin':origin,'module_version':version,'module_id':torch['module_id'],'cuda_build':'13.0' if good else '12.8','availability':good,'availability_error':None,'gpu_error':None,'version_origin':str(Path(origin).parent/'version.py'),
        'c_extension_origin':str(Path(c.cfg['installation_prefix'])/'torch/_C.pyd'),'gpu':{'is_cuda':True,'device':'cuda:0','sum':6.} if good else None,
        'loaded_torch_modules':{'torch':origin}}
    if good:t.update(device_count=1,device_name='HOST MODEL GPU',capability=[8,9])
    return {'modules':modules,'torch':t,'sys_path':[]}

def diagnosis_records(a,c,finished=None):
    out=c.run/'output';out.mkdir(exist_ok=True);proof=out/'audit-proof';proof.mkdir(exist_ok=True)
    files={'job.json':(a.run/'job.json').read_bytes(),'reservation.json':json.dumps(row(a)).encode(),**{n:(a.run/'output'/n).read_bytes() for n in S.AUDIT_RECORDS}}
    for n,b in files.items():(proof/n).write_bytes(b)
    k,api=S.frozen_api(c);m=types.ModuleType('fixture');m.__file__=str(c.run/'input/fixture-053.py');m.API={'kernel':k,'source':{},'root':S.ROOT}
    exec(compile(c.data['fixture-053.py'],m.__file__,'exec'),m.__dict__);numeric=m.ModelTests().numeric(c.cfg)
    now=time.time();finished=now-1 if finished is None else finished
    report={'run_id':c.run.name,'job_sha256':c.job_hash,'pid':33,'status':'PROVIDER_DIAGNOSIS_COMPLETE','input_signature':S.signature(c.job),'observation':observation(c,False),
        'numeric_before':numeric,'numeric_after':numeric,'driver':{'status':'HOST_MODEL'},'finished_unix':finished,'hardware_approved':False,'training':'NOT_RUN'}
    S.write(out/'diagnosis-report.json',report)
    S.write(out/'sdk.json',{'pid':33,'job_sha256':c.job_hash,'version':c.cfg['isaac_version'],'isaacsim_origin':c.cfg['isaac_root']+'/isaacsim/__init__.py','bootstrap_sha256':{n:v['sha256'] for n,v in c.cfg['sdk_files'].items()}})
    S.write(out/'diagnostic-terminal.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'provider_diagnosis','pid':33,'parent_pid':31,'code':0,'status':'DIAGNOSIS_COMPLETE_PRE_CLOSE','phase':'CLOSING_APP','hardware_approved':False,'training':'NOT_RUN','files_sha256':{n:S.sha(out/n) for n in ('diagnosis-report.json','sdk.json')}})
    S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'provider_diagnosis','pid':31,'child_pid':33,'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,
        'started_unix':now-20,'audit_authorized_unix':now-19,'finished_unix':finished+.1,'prerequisite_sha256':{n:S.digest(v) for n,v in files.items()}})
    shell(c,out,0)

def cli(c,source):
    folder=c.run.parent.parent/'project/src/simulation/provider_session';folder.mkdir(parents=True,exist_ok=True)
    for n,b in source.items():(folder/n).write_bytes(b)
    return subprocess.run([shutil.which('pwsh') or 'powershell','-NoProfile','-File',str(folder/'launch.ps1'),'-Role','verify','-RunDir',str(c.run)],capture_output=True,timeout=45,creationflags=S.HIDDEN)

class SessionTests(unittest.TestCase):
    def test_worker_preapp_initialization_order_with_no_sdk(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td,'provider_connection','PREFIX_TORCH_PREAPP');events=[]
            w=S.load_module('worker',c.data['code/worker.py'],c.run/'input/code/worker.py')
            obs=observation(c);ids={n:obs['modules'][n]['module_id'] for n in ('numpy','scipy','warp','torch','torchvision')}
            k=types.SimpleNamespace(sdk_initialize=lambda cfg:events.append('bootstrap'))
            def numeric(api):events.append('numeric_sdk');return {'HOST':'numeric'}
            oldp=types.SimpleNamespace(numeric=numeric,sdk_record=lambda api,origin:{'HOST':'sdk'})
            def collect(api):
                api['lib']['providers'].frameworks(api);api['provider_observation']=obs;S.write(c.run/'output/providers.json',{})
            def run(api,start,collect_fn):start(api);collect_fn(api);return 0
            r=types.SimpleNamespace(run=run,collect=collect)
            api={'lib':{'providers':oldp,'robot':r},'read':S.read,'write':lambda path,value,*args:S.write(path,value)}
            p=types.SimpleNamespace(driver=lambda s:{'HOST':'driver'},bind_preapp=lambda *args:events.append('bind_prefix'),identities=lambda:ids,
                frameworks=lambda *args:events.append('frameworks_after_app'))
            def load(name,raw,path):return k if name=='frozen053' else p
            app=types.ModuleType('isaacsim');app.__file__=str(Path(c.cfg['isaac_root'])/'isaacsim/__init__.py')
            app.SimulationApp=lambda cfg:events.append('app')
            with patch.object(S,'load_module',side_effect=load),patch.object(S,'frozen_api',return_value=(k,api)),patch.dict(sys.modules,{'isaacsim':app}),patch.object(sys,'path',list(sys.path)):
                self.assertEqual(w.run(c,S),0)
            self.assertEqual(events,['bootstrap','numeric_sdk','bind_prefix','app','frameworks_after_app'])

    def test_observer_logs_before_cuda_and_root_selects_only_measured_profile(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);p=S.load_module('observer',c.data['code/provider_observer.py'],c.run/'input/code/provider_observer.py')
            target=c.run/'output/torch-host.json'
            def available():
                self.assertEqual(S.read(target)['state'],'BEFORE_AVAILABILITY')
                return False
            tm=types.SimpleNamespace(__file__=c.cfg['isaac_root']+'/torch/__init__.py',__version__='2.7',version=types.SimpleNamespace(cuda='12.8'),_C=types.SimpleNamespace(__file__=''),cuda=types.SimpleNamespace(is_available=available))
            v=p.observe_torch(c,S,'host',tm);self.assertFalse(v['availability']);self.assertEqual(S.read(target)['state'],'OBSERVED')
            def broken():raise RuntimeError('HOST probe error')
            tm.cuda.is_available=broken;v=p.observe_torch(c,S,'host-error',tm)
            self.assertIn('HOST probe error',v['availability_error']);self.assertTrue((c.run/'output/torch-host-error.json').exists())
            good=observation(c);self.assertEqual(S.choose_profile(good,c.cfg),'BASELINE_CONFIRMED')
            bad=observation(c,False);self.assertEqual(S.choose_profile(bad,c.cfg),'PREFIX_TORCH_PREAPP')
            bad=observation(c);bad['modules']['torchvision']={'status':'IMPORT_ERROR','error':'HOST secondary error'}
            self.assertEqual(S.choose_profile(bad,c.cfg),'PREFIX_TORCH_PREAPP')
            bad=observation(c);bad['torch']=None
            with self.assertRaises((ValueError,KeyError)):S.choose_profile(bad,c.cfg)
            for key in ('device_count','device_name','capability'):
                missing=observation(c);missing['torch'].pop(key)
                with self.assertRaises((ValueError,KeyError)):S.choose_profile(missing,c.cfg)
            explicit=observation(c)
            for key in ('device_count','device_name','capability'):explicit['torch'].pop(key)
            explicit['torch']['device_details_error']='HOST explicit query error'
            S.diagnostic_observation(explicit)
            for key in S.TORCH_FIELDS:
                bad=observation(c,False);bad['torch'].pop(key)
                with self.assertRaises((ValueError,KeyError)):S.choose_profile(bad,c.cfg)

    def test_three_stage_nested_proof_freshness_profile_and_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            a,_=make(td);d,_=make(td,'provider_diagnosis');c,_=make(td,'provider_connection','PREFIX_TORCH_PREAPP')
            audit_records(a,finished=time.time()-30);ledger={'schema_version':1,'legacy_054':S.legacy(a),'reservations':[]}
            self.assertIsNone(S.reservation(a,ledger));ledger['reservations'].append(row(a));proof=S.reservation(d,ledger)
            self.assertEqual(proof['directory'],'audit-proof')
            diagnosis_records(a,d);ledger['reservations'].append(row(d));proof=S.reservation(c,ledger)
            self.assertEqual(proof['directory'],'diagnostic-proof')
            with self.assertRaises(ValueError):S.reservation(d,ledger)
            wrong=c._replace(job=S.freeze({**S.plain(c.job),'profile':'BASELINE_CONFIRMED'}))
            with self.assertRaises(ValueError):S.reservation(wrong,ledger)
            dest=d.run/'retrieved';shutil.copytree(d.run/'output',dest);S.write(d.run/'transport.json',{'returncode':0})
            self.assertEqual(S.consume(d)[1]['status'],'PROVIDER_DIAGNOSIS_VERIFIED');self.assertFalse(S.consume(d)[1]['sdk_connected'])
            with patch.object(time,'time',return_value=time.time()+500):
                self.assertEqual(S.consume(d)[0],0)
                with self.assertRaises(ValueError):S.reservation(c,ledger)
            missing=d.run/'output/audit-proof/remote-shell.json';raw=missing.read_bytes();missing.unlink()
            with self.assertRaises((ValueError,OSError)):S.reservation(c,ledger)
            missing.write_bytes(raw)

    def test_complete_native_profile_bindings_and_data_only_observations(self):
        with tempfile.TemporaryDirectory() as td:
            a,_=make(td);d,_=make(td,'provider_diagnosis');c,source=make(td,'provider_connection','PREFIX_TORCH_PREAPP')
            audit_records(a,finished=time.time()-30);diagnosis_records(a,d,finished=time.time()-10)
            k,api=S.frozen_api(c);m=types.ModuleType('fixture');m.__file__=str(c.run/'input/fixture-053.py');m.API={'kernel':k,'source':{},'root':S.ROOT}
            exec(compile(c.data['fixture-053.py'],m.__file__,'exec'),m.__dict__);helper=m.ModelTests();helper.api=lambda run,pins:api;helper.complete(c.run,c.pins)
            out=c.run/'retrieved';proof=out/'diagnostic-proof';proof.mkdir()
            files={'job.json':(d.run/'job.json').read_bytes(),**S.diagnostic_bytes(d.run/'output'),'reservation.json':json.dumps(row(d)).encode()}
            for n,b in files.items():p=proof/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
            providers=S.read(out/'providers.json');obs=observation(c);ids={n:obs['modules'][n]['module_id'] for n in ('numpy','scipy','warp','torch','torchvision')}
            providers.update(provider_observation=obs,selected_profile=c.job['profile'],binding_before=ids,binding_after=ids);S.write(out/'providers.json',providers)
            terminal=S.read(out/'terminal.json');terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            now=time.time();S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'provider_connection','pid':11,'child_pid':13,'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,
                'started_unix':now-5,'diagnostic_authorized_unix':now-4,'finished_unix':now,'prerequisite_sha256':{n:S.digest(v) for n,v in files.items()}})
            shell(c,out,0);S.write(c.run/'transport.json',{'returncode':0});self.assertTrue(S.consume(c)[1]['sdk_connected'])
            self.assertEqual(cli(c,source).returncode,0)
            providers['binding_after']={**ids,'torch':999};S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            with self.assertRaises(ValueError):S.consume(c)
            providers['binding_before']={**ids,'torch':999};S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            with self.assertRaises(ValueError):S.consume(c)
            providers['binding_before']=ids
            providers['binding_after']=ids;S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            packet=S.read(out/'observations.json');packet['facets']['contact']['sample']['normal_force_N'][0][0]=[99.,0.,0.];S.write(out/'observations.json',packet)
            terminal['files_sha256']['observations.json']=S.sha(out/'observations.json');S.write(out/'terminal.json',terminal)
            with self.assertRaises(ValueError):S.consume(c)
    def test_snapshot_single_bytes_closed_inputs_and_frozen_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);original=Path.read_bytes;reads=[]
            changed=S.read(c.run/'job.json');changed['purpose']='provider_diagnosis'
            def swapping(p):
                raw=original(p)
                if p==c.run/'job.json':reads.append(raw);S.write(p,changed)
                return raw
            with patch.object(Path,'read_bytes',swapping):fresh=S.snapshot(c.run,c.job_hash,c.pins)
            self.assertEqual(len(reads),1);self.assertEqual(fresh.job['purpose'],'installation_audit')
            with self.assertRaises(TypeError):fresh.job['purpose']='provider_diagnosis'
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

    def test_actual_worker_audit_entry_contains_no_sdk(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);out=c.run/'output'
            # A direct-script invocation is rejected before adjacent imports.
            for n in ('session.py','providers.py','worker.py','test_session.py'):
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
