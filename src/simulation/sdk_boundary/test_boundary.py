if __name__ == '__main__':
    raise SystemExit('Use launch.ps1 -Role test')

import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

K=API['runtime']


class BoundaryTests(unittest.TestCase):
    def fixture(self, folder):
        run=Path(folder)/('b'*32);base=run/'input';(base/'code').mkdir(parents=True)
        cfg=json.loads(API['source']['config.json'])
        for name in ('runtime.py','audit.py','native.py'):
            (base/'code'/name).write_bytes(API['source'][name])
        (base/'config.json').write_bytes(API['source']['config.json'])
        for name,item in cfg['references'].items():
            p=base/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(API['root']/item['path'],p)
        install=API['root']/cfg['installation_record']
        shutil.copyfile(install/'prefix-seal.json',base/'prefix-seal.json')
        job={'schema_version':1,'run_id':run.name,'inputs':{},'hardware_approved':False}
        K.write(run/'job.json',job)
        return self.reseal(run)

    def reseal(self, run):
        job=K.read(run/'job.json');job['inputs']={k:K.sha(run/'input'/k) for k in sorted(K.FILES)};K.write(run/'job.json',job)
        pins={k:job['inputs'][k] for k in ('code/runtime.py','code/audit.py','code/native.py','config.json')}
        K.write(run/'prepared.json',{'run_id':run.name,'remote':K.read(run/'input/config.json')['remote_root']+'/'+run.name,
                'job_sha256':K.sha(run/'job.json'),'code':pins,'bundle_sha256':'HOST_FIXTURE'})
        return run,job,pins

    def api(self,run,pins):
        job,data,cfg=K.checked(run,K.sha(run/'job.json'),pins)
        return K.api_for(run,job,data,cfg)

    def complete(self,run,pins):
        api=self.api(run,pins);out=run/'retrieved';out.mkdir()
        s=copy.deepcopy(json.loads(api['data']['data/golden.json']))
        cfg=api['cfg'];job_hash=K.sha(run/'job.json');pid=13
        probe=s['environment']['probe_runtime_mass'];s['environment'].pop('contact_mapping');s['environment'].pop('probe_runtime_mass')
        s['runtime_masses'].append({'name':'probe',**probe})
        s.update(run_id=run.name,pid=pid,job_sha256=job_hash,configuration={'gravity':[0,0,0],'frequency_hz':120,
            'device':'cpu','manager':'isaaclab_physx.physics.physx_manager.PhysxManager'})
        s['actual_drives']={'kp':[0]*6,'kd':[0]*6,'effort':cfg['cap_Nm'],'types':['force']*6}
        K.write(out/'static.json',s)
        def quat(r):
            return [math.sqrt(max(0.,1+r[0][0]+r[1][1]+r[2][2]))/2,
                math.copysign(math.sqrt(max(0.,1+r[0][0]-r[1][1]-r[2][2]))/2,r[2][1]-r[1][2]),
                math.copysign(math.sqrt(max(0.,1-r[0][0]+r[1][1]-r[2][2]))/2,r[0][2]-r[2][0]),
                math.copysign(math.sqrt(max(0.,1-r[0][0]-r[1][1]+r[2][2]))/2,r[1][0]-r[0][1])]
        frames=api['lib']['frames'];fk=frames.fk(frames.decode(api['data']['data/kinematics.json']),[0.]*6)
        poses=[{'name':'Base','position':[0.,0.,0.],'orientation_wxyz':[1.,0.,0.,0.]}]
        poses += [{'name':f'Link{i}','position':r['origin_m'],'orientation_wxyz':quat(r['rotation_world'])} for i,r in enumerate(fk,1)]
        rows=[];previous=None;A=api['lib']['audit']
        for i in range(11):
            clock={'lab_step':20+i,'engine_event_index':i,'engine_time_s':1+i/120,'callback_time_s':i*A.CALLBACK_DT}
            rows.append({'index':i,'before_step':previous or clock,'read_before':clock,'read_after':clock,
                         'q_rad':[0.]*6,'qd_rad_s':[0.]*6,'links':poses,
                         'probe_pose':{'position':s['environment']['probe']['position'],'orientation_wxyz':[1.,0.,0.,0.]},'timeline_playing':True})
            previous=clock
        K.write(out/'rows.json',rows);(out/'scene.usda').write_text('HOST_FIXTURE_NOT_SDK\n',encoding='utf-8')
        versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1'}
        K.write(out/'modules.json',{'pid':pid,'job_sha256':job_hash,'cuda':'13.0','device':'cuda:0','sum':6.,
            'modules':{n:{'version':v,'origin':str(Path(cfg['installation_prefix'])/n/'__init__.py')} for n,v in versions.items()}})
        K.write(out/'sdk.json',{'pid':pid,'job_sha256':job_hash,'version':cfg['isaac_version'],
            'isaacsim_origin':str(Path(cfg['isaac_root'])/'exts/isaacsim.simulation_app/isaacsim/__init__.py'),
            'bootstrap_sha256':{k:v['sha256'] for k,v in cfg['sdk_files'].items()}})
        self.reseal_records(run)
        return api

    def reseal_records(self,run):
        out=run/'retrieved';h=K.sha(run/'job.json')
        K.write(out/'terminal.json',{'run_id':run.name,'job_sha256':h,'pid':13,'parent_pid':11,'code':0,
            'status':'CLOSED','phase':'APP_CLOSED','hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN',
            'files_sha256':{n:K.sha(out/n) for n in ('static.json','rows.json','scene.usda','modules.json','sdk.json')}})
        K.write(out/'exit.json',{'run_id':run.name,'job_sha256':h,'pid':11,'child_pid':13,'worker_pid':13,'child_exit_code':0,'status':'FINISHED'})

    def cli(self,source,role,run=None,cwd=None):
        argv=[shutil.which('pwsh') or 'powershell','-NoProfile','-File',str(source/'launch.ps1'),'-Role',role]
        if run is not None:argv+=['-RunDir',str(run)]
        return subprocess.run(argv,cwd=cwd,capture_output=True,timeout=45)

    def test_actual_frontdoor_complete_positive_and_original_local_shadow(self):
        with tempfile.TemporaryDirectory(prefix='050-frontdoor-') as td:
            td=Path(td);run,job,pins=self.fixture(td/'fixture');self.complete(run,pins)
            source=td/'project/src/simulation/sdk_boundary';source.mkdir(parents=True)
            for n,b in API['source'].items():(source/n).write_bytes(b)
            positive=self.cli(source,'verify',run);self.assertEqual(positive.returncode,0,positive.stderr)
            marker=td/'UNAPPROVED_NUMPY'
            (source/'numpy.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nraise RuntimeError("UNAPPROVED")\n')
            negative=self.cli(source,'verify',run);self.assertNotEqual(negative.returncode,0);self.assertFalse(marker.exists())
            (source/'numpy.py').unlink()
            cwd=td/'cwd';cwd.mkdir();(cwd/'numpy.py').write_text('raise RuntimeError("CWD_SHADOW")\n')
            good=self.cli(source,'verify',run,cwd);self.assertEqual(good.returncode,0,good.stderr)
            (source/'setup').mkdir();(source/'setup/__init__.py').write_text('raise RuntimeError("PACKAGE_SHADOW")\n')
            for role in ('prepare','native','verify'):
                self.assertNotEqual(self.cli(source,role,run).returncode,0)

    def test_direct_python_rejects_before_any_import(self):
        with tempfile.TemporaryDirectory(prefix='050-direct-') as td:
            td=Path(td);marker=td/'UNAPPROVED_JSON'
            (td/'json.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
            for name in ('runtime.py','native.py','audit.py','test_boundary.py'):
                p=td/name;p.write_bytes(API['source'][name])
                result=subprocess.run([sys.executable,'-B',str(p)],cwd=td,capture_output=True,timeout=15)
                self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())

    def test_mandatory_manifest_bytes_and_payload_package(self):
        with tempfile.TemporaryDirectory(prefix='050-manifest-') as td:
            run,job,pins=self.fixture(td)
            K.checked(run,K.sha(run/'job.json'),pins)
            job['inputs'].pop('code/audit.py');K.write(run/'job.json',job)
            with self.assertRaises(ValueError):K.checked(run,K.sha(run/'job.json'),pins)
            run,job,pins=self.reseal(run)
            p=run/'input/setup/__init__.py';p.parent.mkdir();p.write_text('raise RuntimeError("UNAPPROVED")')
            with self.assertRaises(ValueError):K.checked(run,K.sha(run/'job.json'),pins)
            p.unlink();p.parent.rmdir();(run/'input/code/audit.py').write_text('raise RuntimeError("UNAPPROVED")')
            with self.assertRaises(ValueError):K.checked(run,K.sha(run/'job.json'),pins)

    def test_complete_consumer_resealed_frame_clock_and_process_mutations(self):
        with tempfile.TemporaryDirectory(prefix='050-consumer-') as td:
            run,job,pins=self.fixture(td);api=self.complete(run,pins);A=api['lib']['audit'];out=run/'retrieved'
            self.assertTrue(A.consume(out,api)['sdk_connected'])
            original=K.read(out/'static.json')
            mutations=[lambda s:s.update(bodies=[]),lambda s:s['joints'][1].update(local_pos1=[99,0,0]),
                lambda s:s['bodies'][1].update(com=[99,0,0]),lambda s:s['bodies'][1].update(principal_axes_wxyz=[0,1,0,0]),
                lambda s:s['colliders'][0].update(body_path='/wrong'),lambda s:s['colliders'][0].update(local_basis=[[2,0,0],[0,1,0],[0,0,1]]),
                lambda s:s['colliders'][0].update(enabled=False)]
            for mutate in mutations:
                s=copy.deepcopy(original);mutate(s);K.write(out/'static.json',s);self.reseal_records(run)
                with self.assertRaises(ValueError):A.consume(out,api)
            K.write(out/'static.json',original);self.reseal_records(run)
            original_rows=K.read(out/'rows.json')
            for mutation in (lambda r:r[-1]['links'][6]['position'].__setitem__(0,99),lambda r:r[-1]['read_after'].__setitem__('lab_step',99)):
                rows=copy.deepcopy(original_rows);mutation(rows);K.write(out/'rows.json',rows);self.reseal_records(run)
                with self.assertRaises(ValueError):A.consume(out,api)
            K.write(out/'rows.json',original_rows);self.reseal_records(run)
            self.assertTrue(A.consume(out,api)['sdk_connected'])
            for key,value in (('child_exit_code',1),('worker_pid',99)):
                self.reseal_records(run);ex=K.read(out/'exit.json');ex[key]=value;K.write(out/'exit.json',ex)
                with self.assertRaises(ValueError):A.consume(out,api)

    def stub_entry(self,folder,discard=False,alter_sdk=False,alter_prefix=False,alter_root=False):
        run,job,pins=self.fixture(folder);cfg=K.read(run/'input/config.json');sdk=Path(folder)/'sdk';sdk.mkdir()
        (sdk/'VERSION').write_text(cfg['isaac_version'])
        marker=Path(folder)/'NATIVE_EXECUTED'
        files={}
        for name in ('sitecustomize.py','setup_python_env.bat','python.bat'):
            p=sdk/name;p.write_text('# approved host stub\n');files[name]={'path':str(p),'sha256':K.sha(p)}
        prefix=Path(folder)/'prefix';prefix.mkdir();K.write(run/'input/prefix-seal.json',{'schema_version':1,'files':{}})
        cfg.update(isaac_root=str(sdk),sdk_files=files,installation_prefix=str(prefix),installation_seal_sha256=K.sha(run/'input/prefix-seal.json'))
        K.write(run/'input/config.json',cfg)
        native="if __name__=='__main__':raise SystemExit(1)\ndef run(api):\n from pathlib import Path\n Path("+repr(str(marker))+").touch()\n return 7\n"
        (run/'input/code/native.py').write_text(native)
        if discard:
            p=run/'input/code/runtime.py';text=p.read_text(encoding='utf-8');needle="return api['lib']['native'].run(api)"
            self.assertEqual(text.count(needle),1);p.write_text(text.replace(needle,"api['lib']['native'].run(api)\n    return 0"),encoding='utf-8')
        run,job,pins=self.reseal(run)
        if alter_sdk:(sdk/'sitecustomize.py').write_text('raise RuntimeError("ALTERED_SDK")')
        if alter_prefix:(prefix/'unregistered.py').write_text('raise RuntimeError("ALTERED_PREFIX")')
        code=K.literal(run,K.sha(run/'job.json'),pins,'native')
        if alter_root:(run/'input/code/runtime.py').write_text('raise RuntimeError("ALTERED_ROOT")')
        child=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=40)
        return child,marker

    def test_actual_literal_return_propagation_and_exact_old_bug_countercontrol(self):
        with tempfile.TemporaryDirectory(prefix='050-exit-') as td:
            child,marker=self.stub_entry(Path(td)/'good');self.assertEqual(child.returncode,7,child.stderr);self.assertTrue(marker.exists())
            bad,marker=self.stub_entry(Path(td)/'discard',discard=True);self.assertEqual(bad.returncode,0,bad.stderr);self.assertTrue(marker.exists())
            self.assertNotEqual(bad.returncode,7,'Exact restored old bug must fail the expected-exit oracle')
            blocked,marker=self.stub_entry(Path(td)/'sdk-mutant',alter_sdk=True);self.assertNotEqual(blocked.returncode,0);self.assertFalse(marker.exists())
            for name,options in (('prefix-mutant',{'alter_prefix':True}),('root-mutant',{'alter_root':True})):
                blocked,marker=self.stub_entry(Path(td)/name,**options);self.assertNotEqual(blocked.returncode,0);self.assertFalse(marker.exists())

    def test_native_lifecycle_before_after_capture_and_close_failure(self):
        with tempfile.TemporaryDirectory(prefix='050-lifecycle-') as td:
            run,job,pins=self.fixture(td);api=self.api(run,pins);out=run/'output';out.mkdir()
            N=api['lib']['native']
            def throws(_):raise RuntimeError('BEFORE_APP')
            self.assertEqual(N.run(api,start=throws),1);self.assertIn('BEFORE_APP',K.read(out/'terminal.json')['primary_error'])
            (out/'status.json').unlink()
            class App:
                def close(self,**kwargs):self.code=kwargs['exit_code']
            app=App()
            def after(_):raise RuntimeError('AFTER_APP')
            self.assertEqual(N.run(api,start=lambda _:app,collect_fn=after),1);self.assertEqual(app.code,1)
            (out/'status.json').unlink()
            def capture(_):
                for n in ('static.json','rows.json','scene.usda','modules.json','sdk.json'):(out/n).write_text('HOST_MOCK')
            self.assertEqual(N.run(api,start=lambda _:app,collect_fn=capture),0);self.assertEqual(app.code,0)
            (out/'status.json').unlink()
            class BadClose:
                def close(self,**kwargs):raise RuntimeError('CLOSE_FAILURE')
            self.assertEqual(N.run(api,start=lambda _:BadClose(),collect_fn=capture),1)
            t=K.read(out/'terminal.json');self.assertEqual(t['code'],1);self.assertIn('CLOSE_FAILURE',t['close_error'])


def run_tests():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryTests))
    return 0 if result.wasSuccessful() else 1
