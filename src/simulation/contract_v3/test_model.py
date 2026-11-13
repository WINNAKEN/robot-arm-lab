if __name__=='__main__':raise SystemExit('Use launch.ps1 -Role test')
import copy,json,math,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
K=API['runner']

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
            source=td/'project/src/simulation/contract_v3';source.mkdir(parents=True)
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
            for module,registry in ((api['lib']['model'],'COLLECTORS'),(api['lib']['verify'],'VALIDATORS')):
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

    def fixture(self, folder):
        run=Path(folder)/('b'*32);base=run/'input';(base/'code').mkdir(parents=True)
        cfg=json.loads(API['source']['config.json'])
        for name in ('runner.py','verify.py','model.py','providers.py'):
            (base/'code'/name).write_bytes(API['source'][name])
        (base/'config.json').write_bytes(API['source']['config.json'])
        (base/'obligations.json').write_bytes(API['source']['obligations.json'])
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
        return K.api_for(run,job,data,cfg)

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
