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
    legacy=(S.ROOT/'outputs/isaac-gravity-v1/evidence/remote-ledger-061.json').read_bytes();(root/'legacy.json').write_bytes(legacy)
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

def physics_model(c,pid=13):
    p=S.load_module('physics_model',c.data['code/physics.py'],c.run/'input/code/physics.py')
    sources={n:{'origin':str(Path(c.cfg['installation_prefix'] if n.startswith('isaaclab') else c.cfg['isaac_root'])/'HOST_MODEL'/ (n+'.py')),'sha256':h} for n,h in p.PINNED.items()}
    return {'run_id':c.run.name,'job_sha256':c.job_hash,'pid':pid,'status':'READY','phase':'PRIMS_READY','sources':sources,'lab_manager':'isaaclab_physx.physics.physx_manager.PhysxManager','device':'cpu','lab_view_id':900,'lab_view_valid':True,'reference_modules':{n:42 for n in ('isaacsim.core.experimental.prims.impl.articulation','isaacsim.core.experimental.prims.impl.rigid_prim','isaacsim.core.experimental.prims.impl.prim')},'managers':[{'name':'isaacsim.core.simulation_manager.impl.simulation_manager.SimulationManager','id':42,'before_view_id':None,'after_view_id':900,'callbacks':dict.fromkeys(('warm_start','on_stop','stage_open','stage_close','post_warm_start'),False),'device':'cpu','engine':'physx'}],'prims':[{'type':n,'module':'isaacsim.core.experimental.prims.impl.articulation' if n=='Articulation' else 'isaacsim.core.experimental.prims.impl.rigid_prim','paths':[path],'manager_id':42,'view_id':900,'valid':True} for n,path in p.expected_prims()]}

def clock_model(c,rows,pid=13):
    r=S.load_module('clock_model',c.data['code/robot.py'],c.run/'input/code/robot.py')
    owner={'selected':r.CLOCK_SELECTED,'manager_name':r.CLOCK_MANAGER+'.SimulationManager','manager_id':42,'native_id':43,'native_type':r.CLOCK_BINDING+'.ISimulationManager','native_identity':True,
        'api_inventory':{'physx_get_simulation_time':False,'sdk_get_simulation_time':True,'lab_get_simulation_time':True},
        'sources':{n:{'origin':str(Path(c.cfg['isaac_root'])/v[0]),'sha256':v[1]} for n,v in r.CLOCK_PINS.items()}}
    return {'schema_version':1,'run_id':c.run.name,'job_sha256':c.job_hash,'pid':pid,'status':'READY','phase':'TRACE_COMPLETE','owner':owner,
        'samples':[{'index':i,'point':point,'clock':copy.deepcopy(row[point])} for i,row in enumerate(rows) for point in ('before_step','read_before','read_after')]}


def gravity_api_model(c,packet):
    physics=physics_model(c);module='isaacsim.core.experimental.prims.impl.articulation'
    return {'module':module,'class':'Articulation','method':'get_dof_gravity_compensation_forces','bound_identity':True,'source':copy.deepcopy(physics['sources'][module]),'paths':physics['prims'][0]['paths'][:],'dof_names':packet['facets']['bodies']['dof_names'][:]}


def gravity_model(c,packet,clock,pid=13,width=6):
    k,api=S.frozen_api(c);r=api['lib']['robot'];end=packet['facets']['trace']['rows'][-1];rows=[]
    for i in range(241):
        row=copy.deepcopy(end);row['index']=i
        def stamp(j):return {'lab_step':end['read_after']['lab_step']+j,'engine_event_index':j,'engine_time_s':end['read_after']['engine_time_s']+j/120,'callback_time_s':j*__import__('struct').unpack('f',__import__('struct').pack('f',1/120))[0]}
        row.update(before_step=stamp(max(0,i-1)),read_before=stamp(i),read_after=stamp(i),configuration={'gravity':list(r.GRAVITY),'link_names':list(r.LINKS),'link_enabled':[True]*7,'probe_enabled':[True],'kp':[0]*6,'kd':[0]*6,'effort':list(c.cfg['cap_Nm'])})
        row['probe_pose']['position'][2]=max(.025,end['probe_pose']['position'][2]-.5*9.81*(i/120)**2)
        sample=copy.deepcopy(packet['facets']['contact']['sample'])
        if row['probe_pose']['position'][2]==.025:
            sample['normal_force_N'][7][0]=[0.,0.,__import__('struct').unpack('f',__import__('struct').pack('f',.981))[0]];sample['counts'][7][0]=1
            sample['active']=[{'sensor':7,'filter':0,'force_N':__import__('struct').unpack('f',__import__('struct').pack('f',.981))[0],'point':[-.6,0.,0.],'normal':[0.,0.,1.],'separation_m':0.}]
        row['contact']=sample
        native=r.gravity_math(packet['facets']['static'],end['links'],k)
        offset=width-6;columns=[offset+packet['facets']['bodies']['dof_names'].index(n) for n in r.JOINTS];native_full=([100.,-200.,300.,-400.,500.,-600.] if offset else [])+[0.]*6
        for j,col in enumerate(columns):native_full[col]=native[j]
        row['actuation']=None if i==0 else {'source_index':i-1,'read_clock':row['before_step'],'native':native[:],'native_full':native_full,'native_shape':[1,width],'native_offset':offset,'native_layout':'DOFS_ONLY' if offset==0 else 'ROOT_WRENCH_THEN_DOFS','native_root_wrench':native_full[:offset],'native_dof_names':packet['facets']['bodies']['dof_names'][:],'native_columns':columns,'math':native[:],'command':native[:],'readback':native[:],'saturated':[False]*6}
        rows.append(row)
    return {'schema_version':1,'run_id':c.run.name,'job_sha256':c.job_hash,'pid':pid,'status':'COLLECTED','phase':'GRAVITY_COMPLETE','hardware_approved':False,'mode':'NATIVE_FF_ZERO_PD_2S','view_id':900,'clock_owner':copy.deepcopy(clock['owner']),'native_api':gravity_api_model(c,packet),'base_binding':{'source_fixed_joints':[j for j in packet['facets']['static']['joints'] if j['type']=='fixed'],'actual_base_pose_at_start':next(x for x in rows[0]['links'] if x['name']=='Base')},'gravity_before':[0.,0.,0.],'rows':rows,'contact_mapping':copy.deepcopy(packet['facets']['contact']['mapping']),'dimensions':{'sensor_count':8,'filter_count':9,'capacity':512}}


def audit_records(c,out=None,finished=None):
    out=c.run/'output' if out is None else out;out.mkdir(exist_ok=True)
    finished=time.time()-1 if finished is None else finished
    S.write(out/'audit-report.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'pid':23,'status':'INSTALLATION_AUDITED','input_signature':S.signature(c.job),
        'seal_sha256':S.digest(c.data['prefix-seal.json']),'file_count':39919,'bytes':1,'sdk_modules':[],'finished_unix':finished,'host_fixture':True})
    S.write(out/'worker-terminal.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'installation_audit','pid':23,'parent_pid':21,'code':0,'report_sha256':S.sha(out/'audit-report.json')})
    S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'installation_audit','pid':21,'child_pid':23,'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,'started_unix':finished-1,'finished_unix':finished+.1})
    shell(c,out,0)

def row(c):return {'purpose':c.job['purpose'],'run_id':c.run.name,'job_sha256':c.job_hash,'input_signature':S.signature(c.job),'reserved_unix':time.time()}

def model_inventory(t,files=None):
    # Typed metadata below is HOST MODEL, never actual055 metadata.
    root=Path(t['origin']).parent
    files={'torch':t['origin'],'torch._ops':str(root/'_ops.py'),'torch._classes':str(root/'_classes.py'),'torch.ops':'_ops.py','torch.classes':'_classes.py'} if files is None else dict(files)
    ids={n:i+100 for i,n in enumerate(files)};ids['torch']=t['module_id'];rows={}
    for n,p in files.items():
        rows[n]={'module_id':ids[n],'reported_file':p,'spec_origin':p if Path(p).is_absolute() else None,'loader_module':None,'loader_qualname':None,
            'type_module':'builtins','type_qualname':'module','type_definition_origin':None,'type_definition_module_id':None,'type_is_definition':False}
    for n,module,qualname in [('torch.ops','torch._ops','_Ops'),('torch.classes','torch._classes','_Classes')]:
        if n in rows:rows[n].update(type_module=module,type_qualname=qualname,type_definition_origin=files[module],type_definition_module_id=ids[module],type_is_definition=True)
    t.update(loaded_torch_modules=files,torch_inventory=rows,fileless_torch_modules={},torch_module_count=len(rows),inventory_scope='FILE_REPORTED_TORCH_MODULES')
    return t

def model_metadata(obs):
    for name,pin in S.BOUND.items():
        item=obs['modules'][name];root=str(Path(item['origin']).parent.parent)
        item['ambient_metadata']={'version':'HOST_AMBIENT_OTHER','root':'HOST_AMBIENT_ROOT','error':None}
        item.update(bound_state='ERROR',bound_proof=None,bound_error='HOST MODEL outside intended metadata',distribution_version=None,distribution_root=None)
        if item['version']==pin['version']:
            proof={'name':name,'version':pin['version'],'root':root,'module_relative':name+'/__init__.py','files':dict(pin['files'])}
            item.update(bound_state='VERIFIED',bound_proof=proof,bound_error=None,distribution_version=pin['version'],distribution_root=root)
    return obs

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
    model_inventory(t)
    return model_metadata({'modules':modules,'torch':t,'sys_path':[]})

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
    folder=c.run.parent.parent/'project/src/simulation/physics_session';folder.mkdir(parents=True,exist_ok=True)
    for n,b in source.items():(folder/n).write_bytes(b)
    return subprocess.run([shutil.which('pwsh') or 'powershell','-NoProfile','-File',str(folder/'launch.ps1'),'-Role','verify','-RunDir',str(c.run)],capture_output=True,timeout=45,creationflags=S.HIDDEN)

class SessionTests(unittest.TestCase):
    def test_contact_float32_interval_historical_control_and_faults(self):
        import struct
        f32=lambda x:struct.unpack('f',struct.pack('f',x))[0]
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);r=S.load_module('contact_interval',c.data['code/robot.py'],c.run/'input/code/robot.py')
            example=S.read(S.ROOT/'outputs/isaac-mapped-gravity-v1/evidence/historical-contact-example.json');terms=[(a['force_N'],a['normal'][2]) for a in example['contacts']]
            result=r.contact_component_interval(example['matrix'],terms,S.need);self.assertFalse(result['legacy_absolute_pass']);self.assertLessEqual(result['residual_N'],result['budget_N']);self.assertAlmostEqual(result['budget_N'],4.252151969945771e-6,places=16)
            for delta in (.001,.01):
                with self.assertRaisesRegex(ValueError,'intervals disagree'):r.contact_component_interval(f32(example['matrix']+delta),terms,S.need)
            with self.assertRaisesRegex(ValueError,'resolution budget'):r.contact_component_interval(10000.,[(10000.,1.)],S.need)
            for value in (.981,float('nan')):
                with self.assertRaises(ValueError):r.contact_component_interval(value,[],S.need)

    def test_generalized_mapper_preserves_prefix_and_exact_named_columns(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);r=S.load_module('mapper',c.data['code/robot.py'],c.run/'input/code/robot.py')
            names=['J6','J4','J2','J5','J1','J3'];torque=[0.,.2,.3,0.,.5,.6]
            for prefix in ([],[1000.,-2000.,3000.,-4000.,5000.,-6000.]):
                full=prefix+[torque[r.JOINTS.index(n)] for n in names];shape=[1,len(full)];mapped=r.map_generalized(shape,full,names,S.need)
                self.assertEqual(mapped['native'],torque);self.assertEqual(mapped['native_root_wrench'],prefix);self.assertEqual(mapped['native_offset'],len(prefix));self.assertEqual(mapped['native_columns'],[len(prefix)+names.index(n) for n in r.JOINTS]);self.assertEqual(mapped['native_full'],full)
            self.assertEqual(r.map_generalized([1,12],[0.]*12,r.JOINTS,S.need)['native'],[0.]*6)
            for shape,full,bad_names in (([1,8],[0.]*8,names),([2,6],[0.]*12,names),([1,12],[0.]*6,names),([True,6],[0.]*6,names),([1,6],[float('nan')]+[0.]*5,names),([1,6],[0.]*6,['J1']*6),([1,6],[0.]*6,names[:5])):
                with self.subTest(shape=shape,names=bad_names):
                    with self.assertRaises(ValueError):r.map_generalized(shape,full,bad_names,S.need)

    def test_gravity_api_identity_binds_original_source_method_and_object(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);k,api,packet,clock=self.gravity_fixture(c);r=api['lib']['robot'];physics=physics_model(c)
            # HOST_MODEL class with an explicitly pinned original source-file locator.
            path=Path(td)/'articulation.py';path.write_bytes((S.ROOT/'outputs/isaac-physics-v1/evidence/sdk-source/articulation.py').read_bytes())
            namespace={'__name__':r.G_API_MODULE};exec(compile('class Articulation:\n def get_dof_gravity_compensation_forces(self):return None\n',str(path),'exec'),namespace)
            obj=namespace['Articulation']();obj.paths=physics['prims'][0]['paths'];obj.dof_names=packet['facets']['bodies']['dof_names'];physics['sources'][r.G_API_MODULE]={'origin':str(path),'sha256':S.sha(path)}
            value=r.gravity_api_identity(obj,physics,S.need);self.assertTrue(value['bound_identity']);self.assertEqual(value['source']['sha256'],S.sha(path))
            other=namespace['Articulation']();obj.get_dof_gravity_compensation_forces=other.get_dof_gravity_compensation_forces
            with self.assertRaises(ValueError):r.gravity_api_identity(obj,physics,S.need)
            del obj.get_dof_gravity_compensation_forces
            path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaises(ValueError):r.gravity_api_identity(obj,physics,S.need)

    def gravity_fixture(self,c):
        k,api=S.frozen_api(c);m=types.ModuleType('gravity_fixture');m.__file__=str(c.run/'input/fixture-053.py');m.API={'kernel':k,'source':{},'root':S.ROOT}
        exec(compile(c.data['fixture-053.py'],m.__file__,'exec'),m.__dict__);helper=m.ModelTests();helper.api=lambda run,pins:api;helper.complete(c.run,c.pins)
        packet=S.read(c.run/'retrieved/observations.json');clock=clock_model(c,packet['facets']['trace']['rows'])
        return k,api,packet,clock

    def test_gravity_math_virtual_work_and_rotated_com(self):
        import math
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td,'provider_connection','PREFIX_TORCH_PREAPP');k,api,packet,clock=self.gravity_fixture(c);r=api['lib']['robot'];static=packet['facets']['static'];poses=packet['facets']['trace']['rows'][-1]['links']
            def mul(a,b):
                w,x,y,z=a;v,i,j,l=b
                return [w*v-x*i-y*j-z*l,w*i+x*v+y*l-z*j,w*j-x*l+y*v+z*i,w*l+x*j-y*i+z*v]
            def rotate(items,axis,anchor,angle,names):
                result=copy.deepcopy(items);rot=api['lib']['frames'].rotation(axis,angle);quat=[math.cos(angle/2),*[v*math.sin(angle/2) for v in axis]]
                for item in result:
                    if item['name'] in names:
                        item['position']=k.add(anchor,k.mv(rot,[v-a for v,a in zip(item['position'],anchor)]));item['orientation_wxyz']=mul(quat,item['orientation_wxyz'])
                return result
            for whole_rotation in (0.,.7):
                actual=rotate(poses,[0.,1.,0.],[0.,0.,0.],whole_rotation,r.LINKS);torque=r.gravity_math(static,actual,k);by_name={x['name']:x for x in actual};by_path={b['path']:b['name'] for b in static['bodies']}
                def energy(items):
                    ps={x['name']:x for x in items}
                    return sum(b['mass']*9.81*k.add(ps[b['name']]['position'],k.mv(k.quaternion(ps[b['name']]['orientation_wxyz']),b['com']))[2] for b in static['bodies'])
                for i,name in enumerate(r.JOINTS):
                    joint=next(j for j in static['joints'] if j['name']==name);parent=by_name[by_path[joint['body0']]];rot=k.quaternion(parent['orientation_wxyz']);anchor=k.add(parent['position'],k.mv(rot,joint['local_pos0']));axis=k.mv(k.mm(rot,k.quaternion(joint['local_rot0_wxyz'])),[float(joint['axis']==x) for x in 'XYZ']);eps=1e-5
                    derivative=(energy(rotate(actual,axis,anchor,eps,r.LINKS[i+1:]))-energy(rotate(actual,axis,anchor,-eps,r.LINKS[i+1:])))/(2*eps)
                    self.assertAlmostEqual(torque[i],derivative,places=7)

    def test_actual_gravity_collector_steps_force_readback_and_first_fault(self):
        class Vector(list):
            def tolist(self):return list(self)
        class Tensor:
            def __init__(self,value):self.value=Vector(value);self.shape=(1,len(value))
            def numpy(self):return self
            def copy(self):return self
            def __getitem__(self,key):return self.value
            def reshape(self,*args):return self.value
        for mode in ('good','missing_gravity','dual_fail','floating_layout','bad_shape','nan_force','math_mismatch','native_conversion_error'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as td:
                c,_=make(td,'provider_connection','PREFIX_TORCH_PREAPP');k,api,packet,clock=self.gravity_fixture(c);r=api['lib']['robot'];packet['pid']=os.getpid();clock['pid']=os.getpid();good=gravity_model(c,packet,clock,pid=os.getpid());model={'i':0,'g':[0.,0.,0.],'callback':None,'unsub':False,'command':[0.]*6,'calls':0}
                out=c.run/'output';out.mkdir();S.write(out/'clock-report.json',clock)
                def set_gravity(value):
                    if mode=='missing_gravity':raise RuntimeError('HOST gravity API unavailable')
                    model['g']=list(value)
                view=types.SimpleNamespace(get_gravity=lambda:model['g'],set_gravity=set_gravity)
                physics=physics_model(c,pid=os.getpid());physics['lab_view_id']=id(view);S.write(out/'physics-binding.json',physics)
                def clock_owner(api,sim,omni,owner):
                    owner.update(clock['owner'])
                    def getter():
                        if mode=='dual_fail':raise RuntimeError('HOST first gravity clock error')
                        return good['rows'][model['i']]['read_after']['engine_time_s']
                    return owner,getter
                def subscribe(callback,*args):
                    model['callback']=callback
                    def unsubscribe():
                        model['unsub']=True
                        if mode=='dual_fail':raise RuntimeError('HOST gravity cleanup error')
                    return types.SimpleNamespace(unsubscribe=unsubscribe)
                def step(render):model['i']+=1;model['callback'](__import__('struct').unpack('f',__import__('struct').pack('f',1/120))[0])
                def command(value,**kwargs):self.assertEqual(kwargs['dof_indices'],list(range(6)));model.update(command=list(value[0]),calls=model['calls']+1)
                robot=types.SimpleNamespace(dof_names=packet['facets']['bodies']['dof_names'],link_names=r.LINKS,get_dof_positions=lambda **kwargs:Tensor([0.]*6),get_dof_velocities=lambda **kwargs:Tensor([0.]*6),get_dof_gains=lambda **kwargs:(Tensor([0.]*6),Tensor([0.]*6)),get_dof_max_efforts=lambda **kwargs:Tensor(c.cfg['cap_Nm']),get_link_enabled_gravities=lambda:Tensor([True]*7),get_dof_gravity_compensation_forces=lambda **kwargs:Tensor(good['rows'][1]['actuation']['native']),set_dof_efforts=command,get_dof_efforts=lambda **kwargs:Tensor(model['command']))
                if mode=='floating_layout':
                    full=[100.,-200.,300.,-400.,500.,-600.]+good['rows'][1]['actuation']['native']
                    robot.get_dof_gravity_compensation_forces=lambda **kwargs:Tensor([full[i] for i in kwargs['dof_indices']] if 'dof_indices' in kwargs else full)
                if mode=='bad_shape':robot.get_dof_gravity_compensation_forces=lambda **kwargs:Tensor([0.]*8)
                if mode=='nan_force':robot.get_dof_gravity_compensation_forces=lambda **kwargs:Tensor([float('nan')]+[0.]*5)
                if mode=='math_mismatch':robot.get_dof_gravity_compensation_forces=lambda **kwargs:Tensor([0.]*6)
                if mode=='native_conversion_error':
                    class FailedNative:
                        shape=(1,12)
                        def numpy(self):raise RuntimeError('HOST native raw conversion failure')
                    robot.get_dof_gravity_compensation_forces=lambda **kwargs:FailedNative()
                links=[]
                for j in range(7):
                    def pose(j=j):
                        item=good['rows'][model['i']]['links'][j];return Tensor(item['position']),Tensor(item['orientation_wxyz'])
                    links.append(types.SimpleNamespace(get_world_poses=pose))
                probe=types.SimpleNamespace(get_world_poses=lambda:(Tensor(good['rows'][model['i']]['probe_pose']['position']),Tensor([1.,0.,0.,0.])),get_enabled_gravities=lambda:Tensor([True]))
                state={'sim':types.SimpleNamespace(physics_manager=types.SimpleNamespace(get_physics_sim_view=lambda:view),get_physics_step_count=lambda:good['rows'][model['i']]['read_after']['lab_step'],step=step),'robot':robot,'backend':types.SimpleNamespace(use_backend=lambda *a,**kw:__import__('contextlib').nullcontext()),'links':links,'probe':probe,'indices':list(range(6)),'omni':types.SimpleNamespace(physx=types.SimpleNamespace(get_physx_interface=lambda:types.SimpleNamespace(subscribe_physics_on_step_events=subscribe))),'timeline':types.SimpleNamespace(is_playing=lambda:True),'contact_reader':types.SimpleNamespace(mapping=good['contact_mapping'],view=types.SimpleNamespace(sensor_count=8,filter_count=9,max_contact_data_count=512),read=lambda dt:copy.deepcopy(good['rows'][model['i']]['contact']))}
                with patch.dict(sys.modules,{'carb':types.SimpleNamespace(Float3=lambda *x:list(x))}),patch.object(r,'clock_owner',side_effect=clock_owner),patch.object(r,'gravity_api_identity',return_value=gravity_api_model(c,packet)):
                    if mode in ('good','floating_layout'):
                        r.collect_gravity(api,state,packet);report=S.read(out/'gravity-report.json');metrics=r.check_gravity(report,packet,clock,api,physics)
                        self.assertTrue(metrics['dynamics_pass']);self.assertEqual(model['calls'],240);self.assertEqual(model['i'],240);self.assertTrue(model['unsub'])
                        if mode=='floating_layout':
                            act=report['rows'][1]['actuation'];self.assertEqual(act['native_offset'],6);self.assertEqual(act['native_columns'],list(range(6,12)));self.assertEqual(act['native_root_wrench'],[100.,-200.,300.,-400.,500.,-600.]);self.assertFalse(any(act['saturated']))
                    else:
                        self.assertEqual(r.run(api,start=lambda api:types.SimpleNamespace(close=lambda **kw:None),collect_fn=lambda api:r.collect_gravity(api,state,packet)),1)
                        report=S.read(out/'gravity-report.json');terminal=S.read(out/'terminal.json');self.assertEqual(report['status'],'FAILED');self.assertEqual(model['i'],0)
                        if mode=='dual_fail':self.assertIn('first gravity clock',terminal['primary_error']);self.assertIn('cleanup',report['cleanup_error'])
                        if mode in ('bad_shape','nan_force','math_mismatch','native_conversion_error'):
                            self.assertEqual(model['calls'],0);self.assertIsNotNone(report['pending_native'])
                            if mode=='nan_force':self.assertFalse(report['pending_native']['finite']);self.assertIn('nan',report['pending_native']['native_repr'])
                            if mode=='native_conversion_error':
                                self.assertEqual(report['pending_native']['stage'],'SHAPE_OBSERVED');self.assertEqual(report['pending_native']['native_shape'],[1,12]);self.assertNotIn('native_full',report['pending_native'])

    def test_native_clock_producer_exact_owner_and_installed_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);r=S.load_module('clock',c.data['code/robot.py'],c.run/'input/code/robot.py')
            native_type=type('ISimulationManager',(),{'__module__':r.CLOCK_BINDING,'get_simulation_time':lambda self:7.})
            native=native_type();owner=type('SimulationManager',(),{'__module__':r.CLOCK_MANAGER,'_simulation_manager_interface':native,'get_simulation_time':classmethod(lambda cls:cls._simulation_manager_interface.get_simulation_time())})
            modules={n:types.ModuleType(n) for n in r.CLOCK_PINS};pins={}
            for n,(relative,_) in r.CLOCK_PINS.items():
                path=Path(td)/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('HOST MODEL '+n).encode());modules[n].__file__=str(path);pins[n]=(relative,S.sha(path))
            modules[r.CLOCK_MANAGER].SimulationManager=owner;modules[r.CLOCK_EXTENSION].SimulationManager=owner
            modules[r.CLOCK_EXTENSION].acquire_simulation_manager_interface=lambda:native
            modules[r.CLOCK_BINDING].ISimulationManager=native_type
            api={'need':S.need,'cfg':{'isaac_root':td}};sim=types.SimpleNamespace(physics_manager=types.SimpleNamespace(get_simulation_time=lambda:999.))
            omni=types.SimpleNamespace(physx=types.SimpleNamespace(get_physx_interface=lambda:object()))
            with patch.dict(r.CLOCK_PINS,pins),patch.object(r.importlib,'import_module',side_effect=lambda n:modules[n]):
                record,getter=r.clock_owner(api,sim,omni,{})
                self.assertEqual(getter(),7.);self.assertTrue(record['native_identity']);self.assertFalse(record['api_inventory']['physx_get_simulation_time'])
                for mode in ('foreign_native','missing_getter','bytes'):
                    with self.subTest(mode=mode):
                        owner._simulation_manager_interface=object() if mode=='foreign_native' else native
                        saved=owner.get_simulation_time
                        if mode=='missing_getter':owner.get_simulation_time=None
                        target=Path(modules[r.CLOCK_BINDING].__file__);raw=target.read_bytes()
                        if mode=='bytes':target.write_bytes(raw+b'changed')
                        with self.assertRaises(ValueError):r.clock_owner(api,sim,omni,{})
                        owner.get_simulation_time=classmethod(lambda cls:cls._simulation_manager_interface.get_simulation_time());target.write_bytes(raw)

    def test_actual_trace_collector_native_clock_and_first_failure_exit(self):
        class Vector(list):
            def tolist(self):return list(self)
        class Tensor:
            def __init__(self,value):self.value=Vector(value)
            def numpy(self):return self
            def copy(self):return self
            def __getitem__(self,key):return self.value
        for mode in ('good','missing','exception','none','nan','negative','stale','reverse','read_drift','dual_fail','cleanup_only'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as td:
                c,_=make(td);r=S.load_module('clock',c.data['code/robot.py'],c.run/'input/code/robot.py');out=c.run/'output';out.mkdir()
                S.write(out/'physics-binding.json',physics_model(c,pid=os.getpid()))
                model={'time':7.,'step':0,'callback':None,'unsubscribed':False,'reads':0}
                def step(render):
                    model['step']+=1
                    model['time']+=0 if mode=='stale' else (-1 if mode=='reverse' else 1)/120
                    model['callback'](float(__import__('struct').unpack('f',__import__('struct').pack('f',1/120))[0]))
                def getter():
                    model['reads']+=1
                    if mode in ('exception','dual_fail'):raise RuntimeError('HOST native query failure')
                    if mode=='none':return None
                    if mode=='nan':return float('nan')
                    if mode=='negative':return -1.
                    if mode=='read_drift':return model['time']+model['reads']*.001
                    return model['time']
                def subscribe(fn,*args):
                    model['callback']=fn
                    def unsubscribe():
                        model.update(unsubscribed=True)
                        if mode in ('dual_fail','cleanup_only'):raise RuntimeError('HOST unsubscribe failure')
                    return types.SimpleNamespace(unsubscribe=unsubscribe)
                sim=types.SimpleNamespace(step=step,get_physics_step_count=lambda:model['step'])
                prim=types.SimpleNamespace(get_world_poses=lambda:(Tensor([0,0,0]),Tensor([1,0,0,0])))
                robot=types.SimpleNamespace(get_dof_positions=lambda:Tensor([0]*6),get_dof_velocities=lambda:Tensor([0]*6))
                api={'run':c.run,'sha':S.sha,'need':S.need,'write':lambda path,value,*args:S.write(path,value),'read':S.read,'cfg':c.cfg}
                state={'api':api,'sim':sim,'timeline':types.SimpleNamespace(is_playing=lambda:True),'backend':types.SimpleNamespace(use_backend=lambda *a,**k:__import__('contextlib').nullcontext()),'robot':robot,'indices':list(range(6)),'links':[prim]*7,'probe':prim,'omni':types.SimpleNamespace(physx=types.SimpleNamespace(get_physx_interface=lambda:types.SimpleNamespace(subscribe_physics_on_step_events=subscribe)))}
                def acquire(api,sim,omni,report):
                    if mode=='missing':raise ValueError('Native engine time getter available')
                    report.update(clock_model(c,[],pid=os.getpid())['owner']);return report,getter
                with patch.object(r,'clock_owner',side_effect=acquire):
                    if mode=='good':
                        trace=r.collect_trace(state);report=S.read(out/'clock-report.json')
                        r.check_clock(report,trace['rows'],c.run.name,c.job_hash,os.getpid(),c.cfg,S.read(out/'physics-binding.json'),S.need)
                        self.assertEqual(model['step'],10);self.assertEqual(len(report['samples']),33);self.assertTrue(model['unsubscribed'])
                    else:
                        app=types.SimpleNamespace(close=lambda **kwargs:None)
                        self.assertEqual(r.run(api,start=lambda api:app,collect_fn=lambda api:r.collect_trace(state)),1)
                        self.assertEqual(S.read(out/'terminal.json')['code'],1)
                        self.assertEqual(S.read(out/'clock-report.json')['status'],'FAILED')
                        self.assertLessEqual(model['step'],10 if mode=='cleanup_only' else 1)
                        if mode=='dual_fail':
                            self.assertIn('HOST native query failure',S.read(out/'terminal.json')['primary_error'])
                            self.assertIn('HOST unsubscribe failure',S.read(out/'clock-report.json')['cleanup_error'])
                        if mode=='cleanup_only':self.assertIn('HOST unsubscribe failure',S.read(out/'terminal.json')['primary_error'])
                        if mode!='missing':self.assertTrue(model['unsubscribed'])

    def test_clock_report_independent_progress_and_closed_samples(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);r=S.load_module('clock',c.data['code/robot.py'],c.run/'input/code/robot.py')
            rows=[]
            for i in range(11):
                clock=lambda j:{'lab_step':j,'engine_event_index':j,'engine_time_s':7.+j/120,'callback_time_s':j/120}
                rows.append({'index':i,'before_step':clock(max(0,i-1)),'read_before':clock(i),'read_after':clock(i)})
            good=clock_model(c,rows);physics=physics_model(c)
            r.check_clock(good,rows,c.run.name,c.job_hash,13,c.cfg,physics,S.need)
            for mode in ('stale','reverse','nonfinite','read_change','missing','owner','source','pid'):
                badrows=copy.deepcopy(rows);bad=copy.deepcopy(good)
                if mode in ('stale','reverse','nonfinite','read_change'):
                    for i,row in enumerate(badrows):
                        for point in ('before_step','read_before','read_after'):
                            if mode=='stale':row[point]['engine_time_s']=7.
                            elif mode=='reverse':row[point]['engine_time_s']=7.-i/120
                            elif mode=='nonfinite':row[point]['engine_time_s']=float('nan')
                            elif i==1 and point=='read_after':row[point]['engine_time_s']+=.001
                    bad=clock_model(c,badrows)
                elif mode=='missing':bad['samples'].pop()
                elif mode=='owner':bad['owner']['selected']='LAB_SELF_CLOCK'
                elif mode=='source':bad['owner']['sources'][r.CLOCK_MANAGER]['origin']='other.py'
                else:bad['pid']=14
                with self.subTest(mode=mode):
                    with self.assertRaises(ValueError):r.check_clock(bad,badrows,c.run.name,c.job_hash,13,c.cfg,physics,S.need)

    def test_physics_closed_callback_and_base_owner_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);p=S.load_module('physics',c.data['code/physics.py'],c.run/'input/code/physics.py');good=physics_model(c)
            p.check(good,c.run.name,c.job_hash,13,c.cfg,S.need)
            for key in good['managers'][0]['callbacks']:
                bad=copy.deepcopy(good);bad['managers'][0]['callbacks'].pop(key)
                with self.subTest(missing_callback=key):
                    with self.assertRaises(ValueError):p.check(bad,c.run.name,c.job_hash,13,c.cfg,S.need)
            bad=copy.deepcopy(good);bad['reference_modules'].pop('isaacsim.core.experimental.prims.impl.prim')
            with self.subTest(missing_base_reference=True):
                with self.assertRaises(ValueError):p.check(bad,c.run.name,c.job_hash,13,c.cfg,S.need)
            distinct=copy.deepcopy(good);distinct['managers'].append({**copy.deepcopy(distinct['managers'][0]),'id':43});distinct['reference_modules']['isaacsim.core.experimental.prims.impl.prim']=43
            p.check(distinct,c.run.name,c.job_hash,13,c.cfg,S.need)
            distinct['managers'].pop()
            with self.assertRaises(ValueError):p.check(distinct,c.run.name,c.job_hash,13,c.cfg,S.need)
    def test_physics_binding_uses_real_collector_order_and_fails_closed_without_sdk(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);p=S.load_module('physics',c.data['code/physics.py'],c.run/'input/code/physics.py');r=S.load_module('robot_model',c.data['code/robot.py'],c.run/'input/code/robot.py');model=physics_model(c)
            view=types.SimpleNamespace(is_valid=True)
            lab=type('PhysxManager',(),{'__module__':'isaaclab_physx.physics.physx_manager','get_physics_sim_view':classmethod(lambda cls:view)})
            callback_names=('warm_start','on_stop','stage_open','stage_close','post_warm_start')
            sdk=type('SimulationManager',(),{'__module__':'isaacsim.core.simulation_manager.impl.simulation_manager','_physics_sim_view__warp':None,'get_default_callback_status':classmethod(lambda cls:dict.fromkeys(callback_names,False)),'get_physics_sim_device':classmethod(lambda cls:'cpu'),'get_active_physics_engine':classmethod(lambda cls:'physx')})
            module=types.SimpleNamespace(SimulationManager=sdk)
            def ready(self,event):self.ready=sdk._physics_sim_view__warp is view
            def valid(self):return self.ready
            art=type('Articulation',(),{'__module__':'isaacsim.core.experimental.prims.impl.articulation','_on_physics_ready':ready,'is_physics_tensor_entity_valid':valid})
            rigid=type('RigidPrim',(),{'__module__':'isaacsim.core.experimental.prims.impl.rigid_prim','_on_physics_ready':ready,'is_physics_tensor_entity_valid':valid})
            prims=[]
            for name,path in p.expected_prims():
                q=(art if name=='Articulation' else rigid)();q.paths=[path];q.ready=False;prims.append(q)
            def gains(self):
                if not self.ready:raise RuntimeError('HOST tensor not ready')
                raise RuntimeError('HOST reached gains after binding')
            art.get_dof_gains=gains
            with self.assertRaisesRegex(RuntimeError,'not ready'):prims[0].get_dof_gains()
            sim=types.SimpleNamespace(physics_manager=lab,device='cpu',reset=lambda:None);out=c.run/'output'
            api={'run':c.run,'sha':S.sha,'need':S.need,'write':S.write,'cfg':c.cfg,'lib':{'physics':p}}
            state={'api':api,'sim':sim,'timeline':types.SimpleNamespace(is_playing=lambda:True),'static':{},'backend':types.SimpleNamespace(use_backend=lambda *a,**k:__import__('contextlib').nullcontext()),'robot':prims[0],'indices':list(range(6)),'links':prims[1:8],'probe':prims[8],'names':list(r.JOINTS),'environment':None}
            with patch.object(p,'source_hashes',return_value=model['sources']),patch.object(p.importlib,'import_module',return_value=module):
                with self.assertRaisesRegex(RuntimeError,'reached gains after binding'):r.collect_bodies(state)
                record=S.read(out/'physics-binding.json');self.assertEqual(record['status'],'READY');self.assertTrue(all(x.ready for x in prims))
                p.check(record,c.run.name,c.job_hash,os.getpid(),c.cfg,S.need)
                for mode in ('invalid_view','foreign','callbacks','device','bad_prim','missing_callback'):
                    sdk._physics_sim_view__warp=None;view.is_valid=True
                    callbacks=dict.fromkeys(callback_names,False)
                    if mode=='callbacks':callbacks['on_stop']=True
                    if mode=='missing_callback':callbacks.pop('post_warm_start')
                    with patch.object(sdk,'get_default_callback_status',return_value=callbacks),patch.object(sdk,'get_physics_sim_device',return_value='cuda:0' if mode=='device' else 'cpu'):
                        if mode=='invalid_view':view.is_valid=False
                        if mode=='foreign':sdk._physics_sim_view__warp=object()
                        with patch.object(art,'is_physics_tensor_entity_valid',return_value=mode!='bad_prim'):
                            with self.assertRaises(ValueError):p.bind(api,sim,prims)
                    self.assertEqual(S.read(out/'physics-binding.json')['status'],'FAILED')
    def test_bound_metadata_reads_actual_files_not_ambient_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);p=S.load_module('observer',c.data['code/provider_observer.py'],c.run/'input/code/provider_observer.py');root=Path(td)/'packages';(root/'torch').mkdir(parents=True)
            pin=copy.deepcopy(S.BOUND['torch']);dist=root/pin['dist_dir'];dist.mkdir();module=root/'torch/__init__.py';module.write_bytes(b'HOST MODEL module')
            meta=dist/'METADATA';meta.write_bytes(b'Name: torch\nVersion: 2.11.0+cu130\n')
            record=dist/'RECORD';digest=hashlib.sha256(module.read_bytes()).digest();record.write_text('torch/__init__.py,sha256='+base64.urlsafe_b64encode(digest).decode().rstrip('=')+','+str(module.stat().st_size)+'\n')
            pin['files']={n:S.sha(root/n) for n in pin['files']};m=types.SimpleNamespace(__file__=str(module),__version__=pin['version'])
            ambient=types.SimpleNamespace(version='2.11.0+cu128',locate_file=lambda _:Path(td)/'SDK')
            with patch.dict(p.BOUND,{'torch':pin}),patch.object(p.importlib.metadata,'distribution',return_value=ambient):
                info=p.module_info('torch',m);self.assertEqual(info['bound_state'],'VERIFIED');self.assertEqual(info['distribution_version'],pin['version']);self.assertEqual(info['ambient_metadata']['version'],'2.11.0+cu128')
                for target in (meta,record,module):
                    original=target.read_bytes();target.write_bytes(original+b'changed')
                    bad=p.module_info('torch',m);self.assertEqual(bad['bound_state'],'ERROR');self.assertIsNone(bad['distribution_version']);target.write_bytes(original)
                original=record.read_bytes();record.write_text('unowned,,\n');pin['files'][pin['dist_dir']+'/RECORD']=S.sha(record)
                with self.assertRaisesRegex(ValueError,'RECORD module ownership'):p.read_bound('torch',m,pin)
                signed=original.decode().replace('torch/','torch\\')
                record.write_text('torch/__init__.py,,\n'+signed);pin['files'][pin['dist_dir']+'/RECORD']=S.sha(record)
                self.assertEqual(p.read_bound('torch',m,pin)['version'],pin['version'])
                for invalid in ('torch/__init__.py,,\n','torch/__init__.py,sha256=wrong,19\n'+signed,'torch/__init__.py,,19\n'+signed,'../torch/__init__.py,'+signed.split(',',1)[1]):
                    record.write_text(invalid);pin['files'][pin['dist_dir']+'/RECORD']=S.sha(record)
                    with self.assertRaises(ValueError):p.read_bound('torch',m,pin)

    def test_read_only_retrieved_real_package_files(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);p=S.load_module('observer',c.data['code/provider_observer.py'],c.run/'input/code/provider_observer.py')
            root=S.ROOT/'outputs/isaac-metadata-v1/evidence/retrieved-package-files'
            for name,pin in S.BOUND.items():
                # Actual retrieved bytes, synthetic file locator; no package import/App.
                result=p.read_bound(name,types.SimpleNamespace(__file__=str(root/name/'__init__.py')),pin)
                self.assertEqual(result['files'],pin['files'])
    def test_actual_object_capture_dynamic_types_and_fileless_partition_without_sdk(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);p=S.load_module('observer',c.data['code/provider_observer.py'],c.run/'input/code/provider_observer.py')
            tm=types.ModuleType('torch');tm.__file__=str(Path(c.cfg['installation_prefix'])/'torch/__init__.py');tm.__version__='2.11.0+cu130'
            tm.version=types.SimpleNamespace(cuda='13.0',__file__=str(Path(tm.__file__).parent/'version.py'));tm._C=types.SimpleNamespace(__file__=str(Path(tm.__file__).parent/'_C.pyd'))
            tm.cuda=types.SimpleNamespace(is_available=lambda:True,device_count=lambda:1,get_device_name=lambda _: 'HOST MODEL GPU',get_device_capability=lambda _:(8,9))
            tm.ones=lambda *args,**kwargs:types.SimpleNamespace(is_cuda=True,device='cuda:0',sum=lambda:types.SimpleNamespace(item=lambda:6.))
            objects={'torch':tm,'torch._C.fileless':types.ModuleType('torch._C.fileless')}
            for name,qualname,marker in [('torch.ops','_Ops','_ops.py'),('torch.classes','_Classes','_classes.py')]:
                module='torch.'+marker[:-3];definition=types.ModuleType(module);definition.__file__=str(Path(tm.__file__).parent/marker)
                cls=type(qualname,(types.ModuleType,),{'__module__':module,'__file__':marker});setattr(definition,qualname,cls)
                objects[module]=definition;objects[name]=cls(name)
            with patch.dict(sys.modules,objects):
                t=p.observe_torch(c,S,'typed-host',tm);S.check_inventory(t);self.assertEqual(t['fileless_torch_modules'],{'torch._C.fileless':id(objects['torch._C.fileless'])})
                obs=observation(c);obs['torch']=t;obs['modules']['torch'].update(module_id=id(tm),origin=tm.__file__)
                self.assertEqual(S.choose_profile(obs,c.cfg),'BASELINE_CONFIRMED')
                objects['torch.ops'].__class__=types.ModuleType
                # A same-named ordinary module does not prove the expected dynamic type.
                objects['torch.ops'].__file__='_ops.py'
                bad=p.observe_torch(c,S,'wrong-type-host',tm)
                with self.assertRaises(ValueError):S.check_inventory(bad)
                with self.subTest(mode='absolute ordinary module with reserved name'):
                    objects['torch.ops'].__file__=str(Path(tm.__file__).parent/'ordinary_ops.py')
                    objects['torch.ops'].__spec__=types.SimpleNamespace(origin=objects['torch.ops'].__file__,loader=None)
                    bad=p.observe_torch(c,S,'absolute-wrong-type-host',tm)
                    with self.assertRaisesRegex(ValueError,'Measured dynamic namespace type'):S.check_inventory(bad)
                with self.subTest(mode='fileless ordinary module with reserved name'):
                    del objects['torch.ops'].__file__
                    bad=p.observe_torch(c,S,'fileless-wrong-type-host',tm)
                    with self.assertRaisesRegex(ValueError,'Reserved namespaces cannot be fileless'):S.check_inventory(bad)

    def test_frozen_055_raw_map_and_typed_inventory_mutations(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=make(td);path=S.ROOT/'outputs/isaac-provider-v1/runs/1bb1e9445d994df9b128e8e28723c1bc/retrieved/provider-diagnosis.json'
            raw=S.read(path);original=copy.deepcopy(raw);t=raw['torch'];self.assertEqual(len(t['loaded_torch_modules']),977)
            self.assertEqual({n:p for n,p in t['loaded_torch_modules'].items() if not Path(p).is_absolute()},{'torch.ops':'_ops.py','torch.classes':'_classes.py'})
            with self.assertRaises((ValueError,KeyError)):S.diagnostic_observation(raw)
            model_inventory(t,t['loaded_torch_modules']);model_metadata(raw);S.diagnostic_observation(raw);self.assertEqual(S.choose_profile(raw,c.cfg),'PREFIX_TORCH_PREAPP')
            self.assertEqual(S.read(path),original)
            positive=observation(c);self.assertEqual(S.choose_profile(positive,c.cfg),'BASELINE_CONFIRMED')
            mutations=[]
            for key in ('torch_inventory','fileless_torch_modules','torch_module_count','inventory_scope'):
                bad=copy.deepcopy(positive);bad['torch'].pop(key);mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_inventory']['torch.ops']['type_definition_module_id']=999;mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_inventory']['torch.ops']['type_module']='builtins';mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_inventory']['torch.ops']['type_is_definition']=False;mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_inventory']['torch.ops']['spec_origin']='_ops.py';mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_inventory'].pop('torch._ops');bad['torch']['loaded_torch_modules'].pop('torch._ops');bad['torch']['torch_module_count']-=1;mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['fileless_torch_modules']['torch']=1;bad['torch']['torch_module_count']+=1;mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_module_count']+=1;mutations.append(bad)
            for name,value in [('torch._ops','relative.py'),('torch._ops','../_ops.py')]:
                bad=copy.deepcopy(positive);bad['torch']['torch_inventory'][name]['reported_file']=value;bad['torch']['loaded_torch_modules'][name]=value;mutations.append(bad)
            bad=copy.deepcopy(positive);bad['torch']['torch_inventory']['torch._ops']['spec_origin']=str(Path(c.cfg['isaac_root'])/'other.py');mutations.append(bad)
            # Matching the two IDs does not make a foreign definition file acceptable.
            bad=copy.deepcopy(positive);tr=bad['torch'];tr['torch_inventory']['torch.ops']['type_definition_module_id']=999;tr['torch_inventory']['torch._ops']['module_id']=999
            foreign=str(Path(c.cfg['isaac_root'])/'foreign/_ops.py');tr['torch_inventory']['torch.ops']['type_definition_origin']=foreign
            tr['torch_inventory']['torch._ops'].update(reported_file=foreign,spec_origin=foreign);tr['loaded_torch_modules']['torch._ops']=foreign;mutations.append(bad)
            self.assertEqual(len(mutations),15)
            for bad in mutations:
                with self.subTest(index=mutations.index(bad)):
                    with self.assertRaises((ValueError,KeyError)):S.choose_profile(bad,c.cfg)
            outside=copy.deepcopy(positive);foreign=str(Path(c.cfg['isaac_root'])/'foreign.py');outside['torch']['torch_inventory']['torch.extra']=copy.deepcopy(outside['torch']['torch_inventory']['torch._ops'])
            outside['torch']['torch_inventory']['torch.extra'].update(reported_file=foreign,spec_origin=foreign);outside['torch']['loaded_torch_modules']['torch.extra']=foreign;outside['torch']['torch_module_count']+=1
            S.diagnostic_observation(outside);self.assertEqual(S.choose_profile(outside,c.cfg),'PREFIX_TORCH_PREAPP')
            with self.assertRaises(ValueError):S.require_observation(outside,c.cfg)

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
            audit_records(a,finished=time.time()-30);ledger={'schema_version':1,'legacy_061':S.legacy(a),'reservations':[]}
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
            S.write(out/'physics-binding.json',physics_model(c));terminal['files_sha256']['physics-binding.json']=S.sha(out/'physics-binding.json');S.write(out/'terminal.json',terminal)
            packet=S.read(out/'observations.json');S.write(out/'clock-report.json',clock_model(c,packet['facets']['trace']['rows']));terminal['files_sha256']['clock-report.json']=S.sha(out/'clock-report.json');S.write(out/'terminal.json',terminal)
            packet=S.read(out/'observations.json');clock=S.read(out/'clock-report.json');S.write(out/'gravity-report.json',gravity_model(c,packet,clock));terminal['files_sha256']['gravity-report.json']=S.sha(out/'gravity-report.json');S.write(out/'terminal.json',terminal)
            now=time.time();S.write(out/'exit.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'provider_connection','pid':11,'child_pid':13,'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,
                'started_unix':now-5,'diagnostic_authorized_unix':now-4,'finished_unix':now,'prerequisite_sha256':{n:S.digest(v) for n,v in files.items()}})
            shell(c,out,0);S.write(c.run/'transport.json',{'returncode':0});self.assertTrue(S.consume(c)[1]['sdk_connected'])
            self.assertEqual(cli(c,source).returncode,0)
            valid_gravity=S.read(out/'gravity-report.json')
            for mode in ('clock','command','field','view','gravity','contact','native_shape','native_columns','native_full','native_offset','native_prefix','native_names','api','base'):
                bad=copy.deepcopy(valid_gravity)
                if mode=='clock':bad['rows'][1]['read_after']['engine_time_s']+=.1
                elif mode=='command':bad['rows'][1]['actuation']['readback'][1]+=1.
                elif mode=='field':bad['rows'][1].pop('contact')
                elif mode=='view':bad['view_id']=901
                elif mode=='gravity':bad['rows'][1]['configuration']['gravity']=[0,0,0]
                elif mode=='contact':bad['rows'][30]['contact']['active']=[]
                elif mode=='native_shape':bad['rows'][1]['actuation']['native_shape']=[1,12]
                elif mode=='native_columns':bad['rows'][1]['actuation']['native_columns']=[5,4,3,2,1,0]
                elif mode=='native_full':bad['rows'][1]['actuation']['native_full'][1]+=1.
                elif mode=='native_offset':bad['rows'][1]['actuation']['native_offset']=6
                elif mode=='native_prefix':bad['rows'][1]['actuation']['native_root_wrench']=[0.]*6
                elif mode=='native_names':bad['rows'][1]['actuation']['native_dof_names']=['J1']*6
                elif mode=='api':bad['native_api']['method']='unbound_wrong_method'
                else:bad['base_binding']['source_fixed_joints']=[]
                S.write(out/'gravity-report.json',bad);terminal['files_sha256']['gravity-report.json']=S.sha(out/'gravity-report.json');S.write(out/'terminal.json',terminal)
                with self.subTest(gravity_resealed=mode):
                    with self.assertRaises((ValueError,KeyError)):S.consume(c)
            failed=copy.deepcopy(valid_gravity)
            for gravity_row in failed['rows']:gravity_row['contact']=copy.deepcopy(packet['facets']['contact']['sample']);gravity_row['probe_pose']=copy.deepcopy(packet['facets']['trace']['rows'][-1]['probe_pose'])
            S.write(out/'gravity-report.json',failed);terminal['files_sha256']['gravity-report.json']=S.sha(out/'gravity-report.json');S.write(out/'terminal.json',terminal)
            code,result=S.consume(c);self.assertEqual(code,1);self.assertEqual(result['status'],'GRAVITY_DIAGNOSTIC_FAILED');self.assertTrue(result['sdk_connected'])
            S.write(out/'gravity-report.json',valid_gravity);terminal['files_sha256']['gravity-report.json']=S.sha(out/'gravity-report.json');S.write(out/'terminal.json',terminal)
            permuted=copy.deepcopy(packet);permuted['facets']['bodies']['dof_names']=['J6','J4','J2','J5','J1','J3'];pm=gravity_model(c,permuted,S.read(out/'clock-report.json'));self.assertTrue(api['lib']['robot'].check_gravity(pm,permuted,S.read(out/'clock-report.json'),api,physics_model(c))['dynamics_pass'])
            pm12=gravity_model(c,permuted,S.read(out/'clock-report.json'),width=12);self.assertTrue(api['lib']['robot'].check_gravity(pm12,permuted,S.read(out/'clock-report.json'),api,physics_model(c))['dynamics_pass'])
            clock_good=S.read(out/'clock-report.json')
            for mode in ('time','owner','native','source','missing','sample'):
                bad=copy.deepcopy(clock_good)
                if mode=='time':bad['samples'][3]['clock']['engine_time_s']+=.2
                elif mode=='owner':bad['owner']['manager_id']=12345
                elif mode=='native':bad['owner']['native_identity']=False
                elif mode=='source':bad['owner']['sources'][next(iter(bad['owner']['sources']))]['sha256']='0'*64
                elif mode=='missing':bad['owner']['api_inventory'].pop('sdk_get_simulation_time')
                else:bad['samples'].pop()
                S.write(out/'clock-report.json',bad);terminal['files_sha256']['clock-report.json']=S.sha(out/'clock-report.json');S.write(out/'terminal.json',terminal)
                with self.subTest(clock_resealed=mode):
                    with self.assertRaises(ValueError):S.consume(c)
            S.write(out/'clock-report.json',clock_good);terminal['files_sha256']['clock-report.json']=S.sha(out/'clock-report.json');S.write(out/'terminal.json',terminal)
            valid_physics=S.read(out/'physics-binding.json');bad_physics=copy.deepcopy(valid_physics);bad_physics['prims'][0]['view_id']=901;S.write(out/'physics-binding.json',bad_physics);terminal['files_sha256']['physics-binding.json']=S.sha(out/'physics-binding.json');S.write(out/'terminal.json',terminal)
            with self.assertRaisesRegex(ValueError,'Actual consumer bound to Lab view'):S.consume(c)
            S.write(out/'physics-binding.json',valid_physics);terminal['files_sha256']['physics-binding.json']=S.sha(out/'physics-binding.json');S.write(out/'terminal.json',terminal)
            for mode in ('missing_callback','missing_base_ref','missing_base_owner'):
                bad=copy.deepcopy(valid_physics)
                if mode=='missing_callback':bad['managers'][0]['callbacks'].pop('post_warm_start')
                elif mode=='missing_base_ref':bad['reference_modules'].pop('isaacsim.core.experimental.prims.impl.prim')
                else:bad['reference_modules']['isaacsim.core.experimental.prims.impl.prim']=43
                S.write(out/'physics-binding.json',bad);terminal['files_sha256']['physics-binding.json']=S.sha(out/'physics-binding.json');S.write(out/'terminal.json',terminal)
                with self.subTest(physics_consumer=mode):
                    with self.assertRaises(ValueError):S.consume(c)
            S.write(out/'physics-binding.json',valid_physics);terminal['files_sha256']['physics-binding.json']=S.sha(out/'physics-binding.json');S.write(out/'terminal.json',terminal)
            # The real consumer rejects a resealed provider artifact at the typed predicate.
            saved=copy.deepcopy(providers)
            providers['provider_observation']['modules']['torch'].pop('bound_state')
            S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            with self.assertRaisesRegex(ValueError,'Complete bound metadata observation'):S.consume(c)
            providers=copy.deepcopy(saved)
            for mutation in ('hash','owner','fallback'):
                bad=copy.deepcopy(saved);item=bad['provider_observation']['modules']['torch']
                if mutation=='hash':item['bound_proof']['files'][S.BOUND['torch']['dist_dir']+'/METADATA']='0'*64
                elif mutation=='owner':item['bound_proof']['module_relative']='other/__init__.py'
                else:item.update(bound_state='ERROR',bound_proof=None,bound_error='HOST failed lookup despite ambient success',distribution_version=None,distribution_root=None)
                S.write(out/'providers.json',bad);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
                with self.assertRaises(ValueError):S.consume(c)
            providers['provider_observation']['torch']['torch_inventory']['torch.ops']['type_is_definition']=False
            S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            with self.assertRaisesRegex(ValueError,'Measured dynamic namespace type'):S.consume(c)
            providers=saved;S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
            for mode in ('absolute','fileless'):
                with self.subTest(consumer_namespace=mode):
                    bad=copy.deepcopy(saved);t=bad['provider_observation']['torch'];ns=t['torch_inventory']['torch.ops']
                    if mode=='absolute':
                        pretend=str(Path(t['origin']).parent/'ordinary_ops.py');ns.update(reported_file=pretend,spec_origin=pretend,type_module='builtins',type_qualname='module',type_is_definition=False,type_definition_origin=None,type_definition_module_id=None);t['loaded_torch_modules']['torch.ops']=pretend
                    else:
                        t['fileless_torch_modules']['torch.ops']=ns['module_id'];t['torch_inventory'].pop('torch.ops');t['loaded_torch_modules'].pop('torch.ops')
                    S.write(out/'providers.json',bad);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
                    with self.assertRaisesRegex(ValueError,'Measured dynamic namespace type|Reserved namespaces cannot be fileless'):S.consume(c)
            S.write(out/'providers.json',providers);terminal['files_sha256']['providers.json']=S.sha(out/'providers.json');S.write(out/'terminal.json',terminal)
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
