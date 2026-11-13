if __name__=='__main__':raise SystemExit('Use launch.ps1 -Role test')
import copy,json,math,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
K=API['kernel']

class ModelTests(unittest.TestCase):
    def numeric(self,cfg):
        return {'numpy_version':'2.3.1','scipy_version':'1.17.0','numpy_origin':str(Path(cfg['numpy_root'])/'__init__.py'),
            'scipy_origin':str(Path(cfg['scipy_root'])/'__init__.py'),'fft_extension':str(Path(cfg['numpy_root'])/'fft/_pocketfft_umath.pyd'),
            'fft':[[6.,0.],[-2.,2.],[-2.,0.]],'rotation':[[1,0,0],[0,1,0],[0,0,1]],
            'loaded_numeric_modules':{'numpy':str(Path(cfg['numpy_root'])/'__init__.py'),'scipy':str(Path(cfg['scipy_root'])/'__init__.py'),
                'numpy.fft._pocketfft_umath':str(Path(cfg['numpy_root'])/'fft/_pocketfft_umath.pyd')}}

    def prior(self,run,dest,mode='sdk_preflight',failed=False):
        dest.mkdir(parents=True,exist_ok=True);job=K.read(run/'job.json');job.update(stage=mode,run_id='a'*32)
        K.write(dest/'job.json',job);h=K.sha(dest/'job.json');cfg=K.read(run/'input/config.json')
        K.write(dest/'providers.json',{'pid':23,'job_sha256':h,'numeric':self.numeric(cfg)})
        K.write(dest/'sdk.json',{'pid':23,'job_sha256':h,'version':cfg['isaac_version'],'isaacsim_origin':None,
            'bootstrap_sha256':{k:v['sha256'] for k,v in cfg['sdk_files'].items()}})
        K.write(dest/'terminal.json',{'run_id':job['run_id'],'job_sha256':h,'pid':23,'parent_pid':21,'stage':mode,
            'code':1 if failed else 0,'status':'FAILED' if failed else 'PREFLIGHT_COMPLETE','phase':'SDK_DLL_PROBE_FINISHED',
            'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN',
            'files_sha256':{n:K.sha(dest/n) for n in ('providers.json','sdk.json')}})
        K.write(dest/'exit.json',{'run_id':job['run_id'],'job_sha256':h,'pid':21,'child_pid':23,'worker_pid':23,
            'status':'FINISHED','child_exit_code':1 if failed else 0})
        reservation={'stage':mode,'run_id':job['run_id'],'job_sha256':h,'input_signature':K.signature(job),'reserved_unix':1.}
        K.write(dest/'reservation.json',reservation)
        return reservation

    def reseal_records(self,run):
        out=run/'retrieved';h=K.sha(run/'job.json')
        K.write(out/'terminal.json',{'run_id':run.name,'job_sha256':h,'pid':13,'parent_pid':11,'stage':'robot_connection',
            'code':0,'status':'CLOSED','phase':'APP_CLOSED','hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN',
            'files_sha256':{n:K.sha(out/n) for n in ('observations.json','scene.usda','providers.json','sdk.json')}})
        K.write(out/'exit.json',{'run_id':run.name,'job_sha256':h,'pid':11,'child_pid':13,'worker_pid':13,'child_exit_code':0,'status':'FINISHED',
            'prerequisite_hashes':{p.name:K.sha(p) for p in (out/'prerequisite').iterdir() if p.is_file()}})

    def cli(self,source,role,run=None,cwd=None):
        args=[shutil.which('pwsh') or 'powershell','-NoProfile','-File',str(source/'launch.ps1'),'-Role',role]
        if run is not None:args+=['-RunDir',str(run)]
        return subprocess.run(args,cwd=cwd,capture_output=True,timeout=45)

    def test_B_complete_public_positive_missing_and_wrong_mapping(self):
        with tempfile.TemporaryDirectory(prefix='052B-contact-') as td:
            td=Path(td);run,job,pins=self.fixture(td/'fixture');api=self.complete(run,pins)
            source=td/'project/src/simulation/canonical_v4';source.mkdir(parents=True)
            for n,b in API['source'].items():(source/n).write_bytes(b)
            out=run/'retrieved';original=K.read(out/'observations.json')
            self.assertEqual(self.cli(source,'verify',run).returncode,0)
            changes=[lambda p:p['facets'].pop('contact'),lambda p:p['facets']['contact']['mapping'].update(sensor_paths=['/WrongActor']*8),
                lambda p:p['facets']['contact']['mapping'].update(filter_paths=[['/WrongCollider']*9]*8),
                lambda p:p['facets']['contact']['mapping'].update(force_frame='LOCAL'),lambda p:p['facets']['contact']['mapping'].update(force_units='kg'),
                lambda p:p['facets']['contact']['mapping'].update(capacity=0),lambda p:p['facets']['contact'].update(engine_event_index=9),
                lambda p:p['facets']['contact']['sample']['counts'][0].__setitem__(0,1),
                lambda p:p['facets']['contact']['sample']['normal_force_N'][0][0].__setitem__(0,True)]
            for mutate in changes:
                K.write(out/'observations.json',original);self.reseal_records(run)
                self.assertEqual(self.cli(source,'verify',run).returncode,0)
                packet=copy.deepcopy(original);mutate(packet);K.write(out/'observations.json',packet);self.reseal_records(run)
                self.assertNotEqual(self.cli(source,'verify',run).returncode,0)

    def test_B_source_frames_and_last_row_resealed(self):
        with tempfile.TemporaryDirectory(prefix='052B-frames-') as td:
            run,job,pins=self.fixture(td);api=self.complete(run,pins);out=run/'retrieved';V=api['lib']['verify'];original=K.read(out/'observations.json')
            changes=[lambda p:p['facets']['static'].update(bodies=[]),lambda p:p['facets']['static']['joints'][1].update(local_pos1=[99,0,0]),
                lambda p:p['facets']['static']['bodies'][1].update(com=[99,0,0]),lambda p:p['facets']['static']['bodies'][1].update(principal_axes_wxyz=[0,1,0,0]),
                lambda p:p['facets']['static']['colliders'][0].update(body_path='/Wrong'),lambda p:p['facets']['static']['colliders'][0].update(enabled=False),
                lambda p:p['facets']['static']['colliders'][0].update(local_basis=[[2,0,0],[0,1,0],[0,0,1]]),
                lambda p:p['facets']['trace']['rows'][-1]['links'][-1]['position'].__setitem__(0,99),
                lambda p:p['facets']['trace']['rows'][-1]['read_after'].__setitem__('engine_event_index',99)]
            for mutate in changes:
                K.write(out/'observations.json',original);self.reseal_records(run);self.assertTrue(V.consume(out,api)['sdk_connected'])
                packet=copy.deepcopy(original);mutate(packet);K.write(out/'observations.json',packet);self.reseal_records(run)
                with self.assertRaises((ValueError,KeyError)):V.consume(out,api)

    def test_B_all_obligation_registries_required(self):
        with tempfile.TemporaryDirectory(prefix='052B-coverage-') as td:
            run,job,pins=self.fixture(td);api=self.api(run,pins)
            for module,registry in ((api['lib']['robot'],'COLLECTORS'),(api['lib']['verify'],'VALIDATORS')):
                saved=getattr(module,registry).pop('contact')
                with self.assertRaises(ValueError):module.bindings(api)
                getattr(module,registry)['contact']=saved;module.bindings(api)
            contract=copy.deepcopy(api['contract']);contract['facets'].remove('contact')
            with self.assertRaises(ValueError):K.validate_contract(contract)

    def test_B_provider_pid_exit_and_prerequisite_failures(self):
        with tempfile.TemporaryDirectory(prefix='052B-binding-') as td:
            run,job,pins=self.fixture(td);api=self.complete(run,pins);out=run/'retrieved';V=api['lib']['verify']
            self.assertTrue(V.consume(out,api)['sdk_connected'])
            original=K.read(out/'providers.json');bad=copy.deepcopy(original);bad['numeric_after']['loaded_numeric_modules']['numpy.fft._pocketfft_umath']=str(Path(api['cfg']['installation_prefix'])/'numpy/fft/bad.pyd')
            K.write(out/'providers.json',bad);self.reseal_records(run)
            with self.assertRaises(ValueError):V.consume(out,api)
            K.write(out/'providers.json',original)
            for key,value in (('child_exit_code',1),('worker_pid',99)):
                self.reseal_records(run);self.assertTrue(V.consume(out,api)['sdk_connected'])
                ex=K.read(out/'exit.json');ex[key]=value;K.write(out/'exit.json',ex)
                with self.assertRaises(ValueError):V.consume(out,api)

    def test_canonical_source_inertia_and_contact_vector_reconstruction(self):
        with tempfile.TemporaryDirectory(prefix='053-values-') as td:
            run,job,pins=self.fixture(td);api=self.complete(run,pins);out=run/'retrieved';original=K.read(out/'observations.json')
            self.assertTrue(K.consume(out,api)['sdk_connected'])
            packet=copy.deepcopy(original)
            packet['facets']['contact']['sample']['normal_force_N'][0][0]=[99.,0.,0.]
            K.write(out/'observations.json',packet);self.reseal_records(run)
            with self.assertRaises(ValueError):K.consume(out,api)
            packet=copy.deepcopy(original);sample=packet['facets']['contact']['sample']
            sample['normal_force_N'][0][0]=[0.,0.,99.];sample['counts'][0][0]=1
            sample['active']=[{'sensor':0,'filter':0,'force_N':99.,'normal':[0.,0.,1.],'point':[0.,0.,0.],'separation_m':0.}]
            K.write(out/'observations.json',packet);self.reseal_records(run);self.assertTrue(K.consume(out,api)['sdk_connected'])
            packet['facets']['contact']['sample']['normal_force_N'][0][0]=[99.,0.,0.]
            K.write(out/'observations.json',packet);self.reseal_records(run)
            with self.assertRaises(ValueError):K.consume(out,api)
            packet=copy.deepcopy(original);body=packet['facets']['static']['bodies'][1]
            body['inertia_diag']=[x+5e-7 for x in body['inertia_diag']]
            for item in packet['facets']['bodies']['runtime_masses']:
                if item['name']==body['name']:
                    for i in range(3):item['inertia_link_about_com'][i][i]+=5e-7
            K.write(out/'observations.json',packet);self.reseal_records(run)
            with self.assertRaises(ValueError):K.consume(out,api)

    def test_canonical_origin_all_provider_records(self):
        with tempfile.TemporaryDirectory(prefix='053-origins-') as td:
            run,job,pins=self.fixture(td);api=self.complete(run,pins);out=run/'retrieved';original=K.read(out/'providers.json')
            mutations=[lambda p:p['numeric_after'].__setitem__('numpy_origin',api['cfg']['numpy_root']+'/../../UNAPPROVED/numpy/__init__.py'),
                lambda p:p['numeric_after'].__setitem__('fft_extension',api['cfg']['numpy_root']+'/../UNAPPROVED/fft.pyd'),
                lambda p:p['numeric_after']['loaded_numeric_modules'].__setitem__('scipy',api['cfg']['scipy_root']+'/../UNAPPROVED/scipy.py')]
            for name in original['frameworks']['modules']:
                root=api['cfg']['warp_root'] if name=='warp' else api['cfg']['installation_prefix']
                mutations.append(lambda p,n=name,r=root:p['frameworks']['modules'][n].__setitem__('origin',r+'/../UNAPPROVED/'+n+'/__init__.py'))
            for mutate in mutations:
                K.write(out/'providers.json',original);self.reseal_records(run);self.assertTrue(K.consume(out,api)['sdk_connected'])
                value=copy.deepcopy(original);mutate(value);K.write(out/'providers.json',value);self.reseal_records(run)
                with self.assertRaises(ValueError):K.consume(out,api)

    def fixture(self, folder):
        run=Path(folder)/('b'*32);base=run/'input';(base/'code').mkdir(parents=True)
        cfg=json.loads(API['source']['config.json'])
        for name in ('kernel.py','robot.py','providers.py'):
            (base/'code'/name).write_bytes(API['source'][name])
        (base/'config.json').write_bytes(API['source']['config.json'])
        (base/'contract.json').write_bytes(API['source']['contract.json'])
        for name,item in cfg['references'].items():
            p=base/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(API['root']/item['path'],p)
        install=API['root']/cfg['installation_record']
        shutil.copyfile(install/'prefix-seal.json',base/'prefix-seal.json')
        job={'schema_version':1,'run_id':run.name,'stage':'robot_connection','inputs':{},'hardware_approved':False}
        K.write(run/'job.json',job)
        return self.reseal(run)

    def reseal(self, run):
        job=K.read(run/'job.json');job['inputs']={k:K.sha(run/'input'/k) for k in sorted(K.FILES)};K.write(run/'job.json',job)
        pins={k:job['inputs'][k] for k in K.CORE}
        K.write(run/'prepared.json',{'run_id':run.name,'remote':K.read(run/'input/config.json')['remote_root']+'/'+run.name,
                'job_sha256':K.sha(run/'job.json'),'code':pins,'bundle_sha256':'HOST_FIXTURE'})
        return run,job,pins

    def api(self,run,pins):
        job,data,cfg=K.checked(run,K.sha(run/'job.json'),pins)
        return K.api_for(K.snapshot(run,K.sha(run/'job.json'),pins))

    def complete(self,run,pins):
        api=self.api(run,pins);out=run/'retrieved';out.mkdir()
        s=copy.deepcopy(json.loads(api['data']['data/golden.json']))
        cfg=api['cfg'];job_hash=K.sha(run/'job.json');pid=13
        mapping=copy.deepcopy(s['environment']['contact_mapping']);probe=s['environment']['probe_runtime_mass'];s['environment'].pop('contact_mapping');s['environment'].pop('probe_runtime_mass')
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
        rows=[];previous=None;A=api['lib']['verify']
        for i in range(11):
            clock={'lab_step':20+i,'engine_event_index':i,'engine_time_s':1+i/120,'callback_time_s':i*A.CALLBACK_DT}
            rows.append({'index':i,'before_step':previous or clock,'read_before':clock,'read_after':clock,
                'q_rad':[0.]*6,'qd_rad_s':[0.]*6,'links':poses,'probe_pose':{'position':s['environment']['probe']['position'],'orientation_wxyz':[1.,0.,0.,0.]},'timeline_playing':True})
            previous=clock
        static={k:s[k] for k in api['contract']['required_fields']['static']}
        bodies={k:s[k] for k in api['contract']['required_fields']['bodies']}
        contact={'mapping':mapping,'sample':{'normal_force_N':[[[0.,0.,0.] for j in range(9)] for i in range(8)],
            'counts':[[0]*9 for i in range(8)],'active':[],'dt_s':1/120},'engine_event_index':10,'sensor_count':8,'filter_count':9,'capacity':512}
        K.write(out/'observations.json',{'run_id':run.name,'job_sha256':job_hash,'pid':pid,'usd_sha256':api['job']['inputs']['data/model.usda'],
            'facets':{'static':static,'bodies':bodies,'trace':{'rows':rows},'contact':contact}})
        (out/'scene.usda').write_text('HOST_FIXTURE_NOT_SDK\n',encoding='utf-8')
        numeric=self.numeric(cfg)
        versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1'}
        framework={'cuda':'13.0','device':'cuda:0','sum':6.,'modules':{n:{'version':v,'origin':str((Path(cfg['warp_root']) if n=='warp' else Path(cfg['installation_prefix'])/n)/'__init__.py')} for n,v in versions.items()}}
        K.write(out/'providers.json',{'pid':pid,'job_sha256':job_hash,'numeric_before':numeric,'numeric_after':numeric,'frameworks':framework})
        K.write(out/'sdk.json',{'pid':pid,'job_sha256':job_hash,'version':cfg['isaac_version'],'isaacsim_origin':str(Path(cfg['isaac_root'])/'python_packages/isaacsim/__init__.py'),
            'bootstrap_sha256':{k:v['sha256'] for k,v in cfg['sdk_files'].items()}})
        self.prior(run,out/'prerequisite')
        self.reseal_records(run)
        return api

if __name__=='__main__':raise SystemExit('Use launch.ps1 -Role test')
import copy,json,shutil,subprocess,sys,tempfile,types,unittest
from pathlib import Path
K=API['kernel']


class RunnerTests(unittest.TestCase):
    def helper(self):return ModelTests()

    def test_job_snapshot_hash_and_parse_share_one_read(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='053-job-snapshot-') as td:
            run,job,pins=self.helper().fixture(td)
            expected=K.sha(run/'job.json')
            self.assertEqual(K.snapshot(run,expected,pins).job['stage'],'robot_connection')
            replacement=copy.deepcopy(job);replacement['stage']='sdk_preflight'
            original_read=Path.read_bytes;reads=[]
            def read_once(path):
                raw=original_read(path)
                if path==run/'job.json':
                    reads.append(raw)
                    K.write(path,replacement)
                return raw
            with patch.object(Path,'read_bytes',read_once):
                context=K.snapshot(run,expected,pins)
            self.assertEqual(len(reads),1)
            self.assertEqual(context.job_hash,expected)
            self.assertEqual(context.job['stage'],'robot_connection')
            self.assertEqual(K.read(run/'job.json')['stage'],'sdk_preflight')
            with self.assertRaises(TypeError):context.job['stage']='sdk_preflight'
            with self.assertRaises(ValueError):K.snapshot(run,expected,pins)

    def test_A_actual_public_shadow_direct_guard_and_closed_payload(self):
        B=self.helper()
        with tempfile.TemporaryDirectory(prefix='052A-entry-') as td:
            td=Path(td);run,job,pins=B.fixture(td/'fixture');B.complete(run,pins)
            source=td/'project/src/simulation/canonical_v4';source.mkdir(parents=True)
            for n,b in API['source'].items():(source/n).write_bytes(b)
            positive=B.cli(source,'verify',run);self.assertEqual(positive.returncode,0,positive.stderr)
            marker=td/'UNAPPROVED'
            (source/'numpy.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nraise RuntimeError("UNAPPROVED")')
            self.assertNotEqual(B.cli(source,'verify',run).returncode,0);self.assertFalse(marker.exists());(source/'numpy.py').unlink()
            cwd=td/'cwd';cwd.mkdir();(cwd/'numpy.py').write_text('raise RuntimeError("CWD_SHADOW")')
            self.assertEqual(B.cli(source,'verify',run,cwd).returncode,0)
            (source/'setup').mkdir();(source/'setup/__init__.py').write_text('raise RuntimeError("PACKAGE_SHADOW")')
            self.assertNotEqual(B.cli(source,'verify',run).returncode,0)
            direct=td/'direct';direct.mkdir();(direct/'json.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()')
            for n in ('kernel.py','providers.py','robot.py','test_kernel.py'):
                p=direct/n;p.write_bytes(API['source'][n]);child=subprocess.run([sys.executable,'-B',str(p)],cwd=direct,capture_output=True,timeout=15)
                self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())
            job['inputs'].pop('code/providers.py');K.write(run/'job.json',job)
            with self.assertRaises(ValueError):K.checked(run,K.sha(run/'job.json'),pins)

    def stub_exit(self,folder,discard=False,alter_sdk=False,alter_root=False,robot=False,alter_prefix=False):
        B=self.helper();run,job,pins=B.fixture(folder);cfg=K.read(run/'input/config.json');sdk=Path(folder)/'sdk';sdk.mkdir();(sdk/'VERSION').write_text(cfg['isaac_version'])
        for name in cfg['sdk_files']:
            p=sdk/name;p.write_text('# host approved stub\n');cfg['sdk_files'][name]={'path':str(p),'sha256':K.sha(p)}
        cfg.update(isaac_root=str(sdk),numpy_root=str(sdk/'numpy'),scipy_root=str(sdk/'scipy'))
        prefix=Path(folder)/'prefix';prefix.mkdir()
        K.write(run/'input/prefix-seal.json',{'schema_version':1,'files':{}})
        cfg.update(installation_prefix=str(prefix),installation_seal_sha256=K.sha(run/'input/prefix-seal.json'))
        K.write(run/'input/config.json',cfg);marker=Path(folder)/'WORKER_CALLED'
        (run/'input/code/providers.py').write_text("if __name__=='__main__':raise SystemExit(1)\ndef preflight(api):\n from pathlib import Path\n Path("+repr(str(marker))+").touch()\n return 7\n")
        if robot:
            (run/'input/code/robot.py').write_text("if __name__=='__main__':raise SystemExit(1)\ndef bindings(api):\n api['need'](api['contract']['facets']==['static','bodies','trace','contact'],'all host stub obligations')\ndef run(api):\n from pathlib import Path\n Path("+repr(str(marker))+").touch()\n return 7\n")
        if discard:
            p=run/'input/code/kernel.py';text=p.read_text(encoding='utf-8');needle="return api['lib']['providers'].preflight(api) if job['stage']=='sdk_preflight' else api['lib']['robot'].run(api)"
            self.assertEqual(text.count(needle),1);p.write_text(text.replace(needle,needle.removeprefix('return ')+'\n    return 0'),encoding='utf-8')
        job['stage']='robot_connection' if robot else 'sdk_preflight';K.write(run/'job.json',job);run,job,pins=B.reseal(run)
        code=K.literal(run,K.sha(run/'job.json'),pins,'native')
        if alter_sdk:(sdk/'sitecustomize.py').write_text('raise RuntimeError("UNAPPROVED_SDK")')
        if alter_root:(run/'input/code/kernel.py').write_text('raise RuntimeError("UNAPPROVED_ROOT")')
        if alter_prefix:(prefix/'unregistered.py').write_text('raise RuntimeError("UNAPPROVED_PREFIX")')
        return subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=40),marker

    def test_A_real_literal_exit_and_exact_discard_countercontrol(self):
        with tempfile.TemporaryDirectory(prefix='052A-exit-') as td:
            child,marker=self.stub_exit(Path(td)/'good');self.assertEqual(child.returncode,7,child.stderr);self.assertTrue(marker.exists())
            child,marker=self.stub_exit(Path(td)/'discard',discard=True);self.assertEqual(child.returncode,0);self.assertNotEqual(child.returncode,7)
            for name,options in (('sdk',{'alter_sdk':True}),('root',{'alter_root':True})):
                child,marker=self.stub_exit(Path(td)/name,**options);self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())
            child,marker=self.stub_exit(Path(td)/'prefix-positive',robot=True);self.assertEqual(child.returncode,7,child.stderr);self.assertTrue(marker.exists())
            child,marker=self.stub_exit(Path(td)/'prefix-negative',robot=True,alter_prefix=True);self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())

    def reservation_case(self,folder,stage,prior=None,duplicate=False,drift=False,bad_pid=False):
        B=self.helper();run,job,pins=B.fixture(folder);job['stage']=stage;K.write(run/'job.json',job);run,job,pins=B.reseal(run)
        cfg=K.read(run/'input/config.json');cfg['remote_root']=str(run.parent)
        ledger=[]
        if prior is not None:
            path=run.parent/('a'*32);reservation=B.prior(run,path/'output',failed=prior=='failed')
            shutil.copyfile(path/'output/job.json',path/'job.json')
            if prior=='unfinished':(path/'output/terminal.json').unlink()
            if drift:reservation['input_signature']='wrong'
            if bad_pid:
                p=path/'output/terminal.json';t=K.read(p);t['parent_pid']=999;K.write(p,t)
            ledger.append(reservation)
        if duplicate and stage=='robot_connection':ledger.append({'stage':stage,'run_id':'d'*32,'job_sha256':'old','input_signature':K.signature(job),'reserved_unix':1.})
        K.write(run.parent/'stage-ledger.json',ledger)
        starts=[]
        class FakeP:
            pid=13
            def __init__(self,*args,**kwargs):starts.append(args)
            def wait(self,timeout):return 0
        class FakeSub:
            Popen=FakeP
            TimeoutExpired=subprocess.TimeoutExpired
            @staticmethod
            def run(*args,**kwargs):return types.SimpleNamespace(returncode=0,stdout=b'0',stderr=b'')
        g=K.supervise.__globals__;original=g['subprocess'];g['subprocess']=FakeSub
        context=K.snapshot(run,K.sha(run/'job.json'),pins)._replace(cfg=K.freeze(cfg))
        try:code=K.supervise(context)
        finally:g['subprocess']=original
        return code,len(starts),K.read(run.parent/'stage-ledger.json')

    def test_A_stage_single_use_and_actual_prerequisite_controls(self):
        with tempfile.TemporaryDirectory(prefix='052A-stages-') as td:
            td=Path(td)
            code,starts,ledger=self.reservation_case(td/'first','sdk_preflight');self.assertEqual((code,starts,len(ledger)),(0,1,1))
            # The original050 success->new attempt witness is now denied for the same stage.
            for state in ('success','failed','unfinished'):
                code,starts,ledger=self.reservation_case(td/('sdk-repeat-'+state),'sdk_preflight',prior=state)
                self.assertNotEqual(code,0);self.assertEqual(starts,0);self.assertEqual(len(ledger),1)
            for label,options in (('missing',{}),('failed',{'prior':'failed'}),('unfinished',{'prior':'unfinished'}),
                                   ('signature',{'prior':'success','drift':True}),('pid',{'prior':'success','bad_pid':True}),
                                   ('repeat',{'prior':'success','duplicate':True})):
                code,starts,ledger=self.reservation_case(td/label,'robot_connection',**options)
                self.assertNotEqual(code,0);self.assertEqual(starts,0)
            code,starts,ledger=self.reservation_case(td/'valid-robot','robot_connection',prior='success')
            self.assertEqual((code,starts,len(ledger)),(0,1,2))

    def test_A_lifecycle_before_after_capture_and_close_failures(self):
        B=self.helper()
        with tempfile.TemporaryDirectory(prefix='052A-lifecycle-') as td:
            run,job,pins=B.fixture(td);api=B.api(run,pins);N=api['lib']['robot'];out=run/'output';out.mkdir()
            def fail(_):raise RuntimeError('BEFORE_APP')
            self.assertEqual(N.run(api,start=fail),1);self.assertIn('BEFORE_APP',K.read(out/'terminal.json')['primary_error'])
            class App:
                def close(self,**kw):self.code=kw['exit_code']
            app=App();(out/'status.json').unlink()
            self.assertEqual(N.run(api,start=lambda _:app,collect_fn=fail),1);self.assertEqual(app.code,1)
            (out/'status.json').unlink()
            def capture(_):
                for name in ('observations.json','scene.usda','providers.json','sdk.json'):(out/name).write_text('HOST_MOCK')
            self.assertEqual(N.run(api,start=lambda _:app,collect_fn=capture),0);self.assertEqual(app.code,0)
            class BadClose:
                def close(self,**kw):raise RuntimeError('CLOSE_FAILURE')
            (out/'status.json').unlink();self.assertEqual(N.run(api,start=lambda _:BadClose(),collect_fn=capture),1)
            self.assertIn('CLOSE_FAILURE',K.read(out/'terminal.json')['close_error'])



    def test_cached_snapshot_supervisor_and_worker_immutable(self):
        B=self.helper()
        with tempfile.TemporaryDirectory(prefix='053-cache-') as td:
            td=Path(td);run,job,pins=B.fixture(td/'fixture');job['stage']='sdk_preflight';K.write(run/'job.json',job);run,job,pins=B.reseal(run)
            context=K.snapshot(run,K.sha(run/'job.json'),pins)
            with self.assertRaises(TypeError):context.job['stage']='robot_connection'
            with self.assertRaises(TypeError):context.data['code/providers.py']=b'changed'
            cfg=copy.deepcopy(K.read(run/'input/config.json'));cfg['remote_root']=str(run.parent)
            context=context._replace(cfg=K.freeze(cfg))
            marker=td/'UNCHECKED_GATE_EXECUTED'
            (run/'input/code/providers.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nraise RuntimeError("UNAPPROVED")')
            starts=[]
            class P:
                pid=13
                def __init__(self,*a,**kw):starts.append(a)
                def wait(self,timeout):return 0
            class S:
                Popen=P
                TimeoutExpired=subprocess.TimeoutExpired
                @staticmethod
                def run(*a,**kw):return types.SimpleNamespace(returncode=0,stdout=b'0',stderr=b'')
            g=K.supervise.__globals__;old=g['subprocess'];g['subprocess']=S
            try:self.assertEqual(K.supervise(context),0)
            finally:g['subprocess']=old
            self.assertEqual(len(starts),1);self.assertFalse(marker.exists())
            # A real new child validates its own snapshot and rejects the changed bytes.
            child=subprocess.run([sys.executable,'-I','-B','-c',K.literal(run,context.job_hash,context.pins,'native')],capture_output=True,timeout=30)
            self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())
            # A reservation from frozen052 consumes the same stage's cumulative allowance.
            other,job,pins=B.fixture(td/'legacy-fixture');job['stage']='sdk_preflight';K.write(other/'job.json',job);other,job,pins=B.reseal(other)
            cfg=K.read(other/'input/config.json');cfg['remote_root']=str(other.parent);legacy=td/'frozen052.json'
            K.write(legacy,[{'stage':'sdk_preflight'}]);cfg['frozen_stage_ledgers']=[str(legacy)]
            ctx=K.snapshot(other,K.sha(other/'job.json'),pins)._replace(cfg=K.freeze(cfg));starts.clear()
            old=g['subprocess'];g['subprocess']=S
            try:self.assertNotEqual(K.supervise(ctx),0)
            finally:g['subprocess']=old
            self.assertEqual(starts,[])

def run_tests():
    suite=unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(RunnerTests),unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests)))
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if r.wasSuccessful() else 1
