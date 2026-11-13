"""HOST adversarial contract tests. Synthetic fixtures never claim SDK/physics success."""
import copy
import ast
import json
import math
from pathlib import Path
import sys
import types
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def module(name,raw,path):
    m=types.ModuleType(name);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m


def setup():
    raw=(HERE/'contract.py').read_text();base=(ROOT/'src/simulation/mp18_isaac_130/contract.py').read_bytes()
    raw=raw.replace("_base = (HERE/'base_contract.py').read_bytes()",'_base = '+repr(base))
    C=module('contract133_HOST',raw.encode(),HERE/'contract.py')
    p=ROOT/'src/simulation/mp18_manipulation_plan_132/planner.py';P=module('planner132_HOST',p.read_bytes(),p)
    s=json.loads((p.parent/'scenario.json').read_text());C.configure(s,P)
    model=C.parse_model(ROOT/'models/robot-arm-urdf-v4/robot_arm.urdf')
    return C,P,s,model


def quaternion(R):
    # Independent test fixture conversion (SciPy is installed, no installation performed).
    from scipy.spatial.transform import Rotation
    x,y,z,w=Rotation.from_matrix(R).as_quat();return [float(w),float(x),float(y),float(z)]


def fixture(C,P,s,model,step):
    actual=step/120;t=C.actual_to_source(actual);ref=P.sample(s,t);q=dict(ref['targets']);qd={n:v*C.time_map(actual)[1] for n,v in ref['reference_velocity'].items()}
    if 50<=t<=68:
        q['KG1_slide_A']=q['KG1_slide_B']=-.01
    G=C.fk(model,q)['KG1'];R=[r[:3] for r in G[:3]];pos=[r[3] for r in G[:3]]
    if 51<t<=68:
        o=C.mm(G,C.tf([0,0,.104],[[1,0,0],[0,-1,0],[0,0,-1]]))
    elif t>68:o=s['object']['destination_T_world']
    else:o=s['object']['source_T_world']
    clock={'engine_time_s':actual,'lab_step':step}
    row={'step':step,'time_s':actual,'clock':clock,'q':q,'qd':qd,'targets':ref['targets'],
         'body_poses':[{'name':'KG1','position':pos,'orientation_wxyz':quaternion(R)}]}
    obj={'clock':clock,'pose':{'position':[r[3] for r in o[:3]],'orientation_wxyz':quaternion([r[:3] for r in o[:3]])},
         'linear_velocity':[0.,0.,0.],'angular_velocity':[0.,0.,0.],
         'binding':{'valid':True,'path':'/World/Task133/Object','kinematic':False,'gravity_enabled':True,'mass_kg':.002}}
    headers=[]
    if 50<=t<=68:
        for name in ('KG1_A','KG1_B'):
            headers.append({'actor0':'/World/Task133/Object','actor1':'/World/Robot/'+name,
                            'contacts':[{'separation':0.,'impulse':[.001,0,0]}]})
    contact={'status':'CURRENT_STEP_REPORT_COPIED','owner_step':step,'headers':headers}
    return row,obj,contact


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.C,cls.P,cls.s,cls.model=setup()

    def task(self):return self.C.Task(self.s,'/World/Task133/Object',{'KG1_A':'/World/Robot/KG1_A','KG1_B':'/World/Robot/KG1_B'})

    def test_01_full_85_second_HOST_fixture(self):
        task=self.task()
        for step in range(11161):task.observe(*fixture(self.C,self.P,self.s,self.model,step))
        result=task.finish();self.assertTrue(result['passed']);self.assertGreaterEqual(result['max_lift_m'],.02)
        self.assertGreaterEqual(result['max_transport_xy_m'],.15);self.assertEqual(len(result['subphases']),18)

    def test_02_all_phase_adapter_and_original_settling(self):
        for phase,start,duration in [('hold',0,8),('small',8,31),('large',39,54)]:
            for t in [0,duration/2,duration]:
                a=self.C.target_at({},phase,t);b=self.P.sample(self.s,self.C.actual_to_source(start+t))
                self.assertEqual(a['targets'],b['targets']);self.assertEqual(a['reference_velocity'],{n:v*self.C.time_map(start+t)[1] for n,v in b['reference_velocity'].items()})
        ref=self.P.sample(self.s,6);q=dict(ref['targets']);qd=dict(ref['reference_velocity'])
        self.assertTrue(self.C.settled(q,qd,ref)['passed']);q['J6']+=math.radians(.50001)
        self.assertFalse(self.C.settled(q,qd,ref)['passed'])

    def test_03_bad_units_and_fake_static_grasp(self):
        for key,value in [('joint_units',dict(self.s['joint_units'],KG1_slide_A='rad')),('runtime_grasp_status','PASS')]:
            s=copy.deepcopy(self.s);s[key]=value
            with self.assertRaises(ValueError):self.C.configure(s,self.P)
        self.C.configure(self.s,self.P)

    def test_04_bilateral_positive_current_contacts(self):
        _,_,c=fixture(self.C,self.P,self.s,self.model,6840)
        self.assertTrue(all(self.C.contact_pairs(c,'/World/Task133/Object',{'A':'/World/Robot/KG1_A','B':'/World/Robot/KG1_B'}).values()))
        c['headers'][1]['contacts'][0]['impulse']=[0,0,0]
        self.assertFalse(all(self.C.contact_pairs(c,'/World/Task133/Object',{'A':'/World/Robot/KG1_A','B':'/World/Robot/KG1_B'}).values()))
        c['status']='UNKNOWN_OBSERVATION_ERROR'
        with self.assertRaises(ValueError):self.C.contact_pairs(c,'/World/Task133/Object',{})

    def test_05_phantom_hull_grasp_and_single_jaw_rejected(self):
        for mutant in ('wide','single','stale','kinematic','mass','slip','rotation'):
            task=self.task();row,obj,contact=fixture(self.C,self.P,self.s,self.model,6840);task.last_step=6839
            if mutant=='wide':row['q']['KG1_slide_A']=row['q']['KG1_slide_B']=-.0055
            elif mutant=='single':contact['headers'].pop()
            elif mutant=='stale':contact['owner_step']-=1
            elif mutant=='kinematic':obj['binding']['kinematic']=True
            elif mutant=='mass':obj['binding']['mass_kg']=.02
            elif mutant=='slip':obj['pose']['position'][0]+=.004
            else:obj['pose']['orientation_wxyz']=[1,0,0,0]
            with self.subTest(mutant=mutant),self.assertRaises(ValueError):task.observe(row,obj,contact)

    def test_06_actual_object_clock_and_rows_contiguous(self):
        task=self.task();row,obj,contact=fixture(self.C,self.P,self.s,self.model,0);obj['clock']=dict(obj['clock'],lab_step=1)
        with self.assertRaises(ValueError):task.observe(row,obj,contact)
        with self.assertRaises(ValueError):self.task().observe(*fixture(self.C,self.P,self.s,self.model,1))
        with self.assertRaises(ValueError):self.task().finish()

    def test_07_release_false_position_speed_and_contact_separation(self):
        for mutant in ('wrong_target','moving','closed'):
            task=self.task();task.last_step=9359
            for step in range(9360,9601):
                row,obj,c=fixture(self.C,self.P,self.s,self.model,step)
                if mutant=='wrong_target':obj['pose']['position'][0]+=.004
                elif mutant=='moving':obj['linear_velocity'][0]=.01001
                else:row['q']['KG1_slide_A']=row['q']['KG1_slide_B']=-.01
                if step==9600:
                    with self.assertRaises(ValueError):task.observe(row,obj,c)
                else:task.observe(row,obj,c)
            self.assertLess(task.max_release_hold,120)

    def test_08_native_derivation_and_global_budget_intersection(self):
        source=(HERE/'native.py').read_text();base=(ROOT/'src/simulation/mp18_isaac_130/native.py').read_bytes()
        source=source.replace("_raw = (_here/'base_native.py').read_bytes()",'_raw = '+repr(base))
        N=module('native133_HOST',source.encode(),HERE/'native.py')
        class Clock:
            t=0.
            def __call__(self):return self.t
        clock=Clock();ctx=types.SimpleNamespace(cfg={'limits':{'native_s':1800,'cleanup_s':2,'import_s':600,'hold_s':200,'small_s':600,'large_s':1000}},started_monotonic=0.,deadline=1800.)
        b=N.Budget(ctx,now=clock);clock.t=500;b.enter('hold');self.assertEqual(b.phase_end,700)
        clock.t=650;b.enter('small');clock.t=1100;b.enter('large');self.assertEqual(b.phase_end,1798);self.assertEqual(b.end,1800)
        clock.t=1798
        with self.assertRaises(N.GateFailure):b.check()
        clock.t=1700;b.phase_end=1798;b.enter('large');self.assertEqual(b.phase_end,1798)
        clock.t=1800
        with self.assertRaises(N.GateFailure):b.enter('hold')

    def test_09_actual_nested_rigid_owner_collider_selection(self):
        source=(HERE/'native.py').read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_scene133')
        packet=json.loads((ROOT/'outputs/mp18-profile-repair-130/runs/dee4f7e320ea464aabd34bc41740efe1/retrieved/import-static.json').read_text())
        class Attr:
            value='convexHull'
            def Get(self):return self.value
            def Set(self,value):self.value=value;return True
            def GetTypeName(self):return 'bool'
            def GetPath(self):return '/World/Robot/Physics/KG1_pinion.newton:mimicEnabled'
        class Prim:
            def __init__(self,path):self.path=path;self.attr=Attr()
            def GetPath(self):return self.path
            def HasAPI(self,api):return True
            def IsA(self,kind):return True
            def GetApproximationAttr(self):return self.attr
            def CreateApproximationAttr(self):return self.attr
            def GetAttribute(self,name):return self.attr
        class API:
            @staticmethod
            def Apply(p):return p
        class PrefixDone(Exception):pass
        class Material:
            @staticmethod
            def Define(*args):raise PrefixDone()
        pxr=types.ModuleType('pxr');pxr.Gf=types.SimpleNamespace();pxr.UsdGeom=types.SimpleNamespace(Mesh=object())
        pxr.UsdPhysics=types.SimpleNamespace(CollisionAPI=object(),MeshCollisionAPI=API)
        pxr.UsdShade=types.SimpleNamespace(Material=Material);pxr.PhysxSchema=types.SimpleNamespace()
        fake=types.ModuleType('isaacsim.core.experimental.prims');fake.RigidPrim=object
        originals={k:sys.modules.get(k) for k in ('pxr','isaacsim','isaacsim.core','isaacsim.core.experimental','isaacsim.core.experimental.prims')}
        try:
            sys.modules['pxr']=pxr
            for key in ('isaacsim','isaacsim.core','isaacsim.core.experimental'):sys.modules[key]=types.ModuleType(key)
            sys.modules['isaacsim.core.experimental.prims']=fake
            ns={'need':self.C.need,'_offset133':lambda p:{'path':p.path}}
            exec(compile(ast.get_source_segment(source,node),'<actual133-scene-owner>','exec'),ns)
            paths={r['name']:r['path'] for r in packet['links']}
            prims=[Prim(r['path']) for r in packet['colliders']]+[Prim('/World/Floor')]
            pinion=Prim('/World/Robot/Physics/KG1_pinion');pinion.attr.value=True
            stage=types.SimpleNamespace(Traverse=lambda:prims,GetPrimAtPath=lambda path:pinion)
            with self.assertRaises(PrefixDone):ns['_scene133'](types.SimpleNamespace(contract=None,scenario={}),stage,paths,None,[],None,{},None)
            changed={p.path for p in prims if p.attr.value=='convexDecomposition'}
            expected={p.path for p in prims if p.path.startswith(paths['KG1']+'/') and not any(p.path.startswith(paths[n]+'/') for n in ('KG1_A','KG1_B','KG1_R'))}
            self.assertEqual(changed,expected);self.assertEqual(len(changed),1)
            self.assertEqual(prims[-1].attr.value,'convexHull')
            self.assertIs(pinion.attr.value,False)
        finally:
            for key,value in originals.items():
                if value is None:sys.modules.pop(key,None)
                else:sys.modules[key]=value

    def test_10_home_dwell_exact_map_and_original_eight_second_gate(self):
        for actual,expected in [(0,0),(6,6),(6.5,6),(8,6),(39,37),(57,51),(93,85)]:
            self.assertEqual(self.C.actual_to_source(actual),expected)
        task=self.task();task.last_step=719;row,obj,c=fixture(self.C,self.P,self.s,self.model,720)
        row['q']['J3']+=math.radians(.63);row['qd']['J3']=math.radians(1.16)
        task.observe(row,obj,c);self.assertEqual(task.checkpoints,[])
        task=self.task();task.last_step=959;row,obj,c=fixture(self.C,self.P,self.s,self.model,960)
        row['q']['J3']+=math.radians(.63);row['qd']['J3']=math.radians(1.16)
        with self.assertRaises(ValueError):task.observe(row,obj,c)
        task=self.task();task.last_step=959;task.observe(*fixture(self.C,self.P,self.s,self.model,960))
        self.assertEqual(task.checkpoints[0]['actual_time_s'],8);self.assertEqual(task.checkpoints[0]['time_s'],6)

    def test_11_actual_component_overlay_schema_and_reset_readbacks(self):
        source=(HERE/'native.py').read_text();namespace={'need':self.C.need}
        nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ('_offset133','_component_colliders133','_audit_components133')]
        for node in nodes:exec(compile(ast.get_source_segment(source,node),'<actual133-component-overlay>','exec'),namespace)
        class Attr:
            def __init__(self,value=None):self.value=value
            def Get(self):return self.value
            def Set(self,value):self.value=value;return True
        class Prim:
            def __init__(self,path,kind='Mesh'):self.path=path;self.kind=kind;self.api=set();self.attrs={};self.rels={}
            def GetPath(self):return self.path
            def HasAPI(self,api):return api in self.api
            def GetRelationship(self,name):return types.SimpleNamespace(GetTargets=lambda:self.rels.get(name,[]))
        class Schema:
            def __init__(self,p):self.p=p
            def GetPrim(self):return self.p
            @classmethod
            def Apply(cls,p):p.api.add(cls);return cls(p)
            def __getattr__(self,name):
                if name.startswith(('Get','Create')) and name.endswith('Attr'):
                    key=name[3:-4] if name.startswith('Get') else name[6:-4]
                    def attr(*args):
                        a=self.p.attrs.setdefault(key,Attr())
                        if args:a.value=args[0]
                        return a
                    return attr
                raise AttributeError(name)
        class Collision(Schema):pass
        class MeshCollision(Schema):pass
        class PhysCollision(Schema):pass
        class Body(Schema):pass
        class Mass(Schema):pass
        class Mesh(Schema):
            @classmethod
            def Define(cls,stage,path):p=Prim(path);stage.prims[path]=p;return cls(p)
        class Binding(Schema):
            def Bind(self,mat,*args):self.p.rels['material:binding:physics']=[mat.GetPath()]
        class Stage:
            def __init__(self):self.prims={}
            def Traverse(self):return list(self.prims.values())
            def GetPrimAtPath(self,path):return self.prims.get(path)
        pxr=types.ModuleType('pxr');pxr.Gf=types.SimpleNamespace(Vec3f=lambda *x:list(x));pxr.UsdGeom=types.SimpleNamespace(Mesh=Mesh)
        pxr.UsdPhysics=types.SimpleNamespace(CollisionAPI=Collision,MeshCollisionAPI=MeshCollision,RigidBodyAPI=Body,MassAPI=Mass)
        pxr.PhysxSchema=types.SimpleNamespace(PhysxCollisionAPI=PhysCollision)
        pxr.UsdShade=types.SimpleNamespace(MaterialBindingAPI=Binding,Tokens=types.SimpleNamespace(weakerThanDescendants='weak'))
        previous=sys.modules.get('pxr');sys.modules['pxr']=pxr
        try:
            stage=Stage();paths={n:'/World/Robot/KG1/'+n for n in ('KG1_A','KG1_B','KG1_R')};data=json.loads((HERE/'jaw_components.json').read_text())
            for name,path in paths.items():
                body=Prim(path,'Xform');body.api={Body,Mass};body.attrs={'Mass':Attr(1.234),'Inertia':Attr([1,2,3])};stage.prims[path]=body
                old=Prim(path+'/collision');old.api={Collision,MeshCollision};old.attrs={'CollisionEnabled':Attr(True),'Approximation':Attr('convexHull')};stage.prims[old.path]=old
            before={n:(stage.prims[p].attrs['Mass'].Get(),stage.prims[p].attrs['Inertia'].Get()) for n,p in paths.items()}
            ctx=types.SimpleNamespace(jaw_components=data,contract=self.C,run=Path('/HOST'),sha=lambda p:__import__('hashlib').sha256((ROOT/'models/robot-arm-urdf-v4/meshes/collision'/Path(p).name).read_bytes()).hexdigest())
            result=namespace['_component_colliders133'](ctx,stage,paths,types.SimpleNamespace(GetPath=lambda:'/World/TaskMaterial133'))
            self.assertEqual(result['before_reset']['count'],12)
            after=namespace['_audit_components133'](ctx,stage,ctx.task_jaw_overlay);self.assertEqual(after['count'],12)
            self.assertTrue(stage.prims[paths['KG1_R']+'/collision'].attrs['CollisionEnabled'].Get())
            self.assertEqual(before,{n:(stage.prims[p].attrs['Mass'].Get(),stage.prims[p].attrs['Inertia'].Get()) for n,p in paths.items()})
            old=stage.prims[paths['KG1_A']+'/collision'];old.attrs['CollisionEnabled'].Set(True)
            with self.assertRaises(ValueError):namespace['_audit_components133'](ctx,stage,ctx.task_jaw_overlay)
            old.attrs['CollisionEnabled'].Set(False)
            child=stage.prims[ctx.task_jaw_overlay[0]['new'][0]['path']];child.api.add(Body)
            with self.assertRaises(ValueError):namespace['_audit_components133'](ctx,stage,ctx.task_jaw_overlay)
        finally:
            if previous is None:sys.modules.pop('pxr',None)
            else:sys.modules['pxr']=previous

    def test_12_full93_reference_Jacobian_and_semantic_checkpoints(self):
        peak={n:0. for n in self.C.NAMES}
        for step in range(11161):
            t=step/120;logical,jac=self.C.time_map(t);p=self.P.sample(self.s,logical)
            phase,local=('hold',t) if t<=8 else ('small',t-8) if t<=39 else ('large',t-39)
            actual=self.C.target_at({},phase,local);self.assertEqual(actual['targets'],p['targets'])
            for n in self.C.NAMES:
                self.assertAlmostEqual(actual['reference_velocity'][n],p['reference_velocity'][n]*jac,places=12)
                peak[n]=max(peak[n],abs(actual['reference_velocity'][n]))
        self.assertAlmostEqual(peak['KG1_slide_A'],.009609375,places=9)
        for actual,logical in [(8,6),(39,37),(57,51),(80,72),(93,85)]:self.assertEqual(self.C.actual_to_source(actual),logical)
        for t,jac in [(7,0),(51,0),(54,.5),(76,.5),(20,1)]:self.assertEqual(self.C.time_map(t)[1],jac)

    def test_13_current_active_component_contact_source_and_actual03_rows(self):
        paths={'A':'/World/Robot/KG1_A','B':'/World/Robot/KG1_B'}
        active={n:{path+'/ExplicitJawColliders133/component_00'} for n,path in paths.items()}
        headers=[{'actor0':'/World/Task133/Object','actor1':path,'collider0':'/World/Task133/Object/Collision',
                  'collider1':next(iter(active[n])),'contacts':[{'separation':0.,'impulse':[.001,0,0]}]} for n,path in paths.items()]
        contact={'status':'CURRENT_STEP_REPORT_COPIED','headers':headers}
        self.assertTrue(all(self.C.contact_pairs(contact,'/World/Task133/Object',paths,active).values()))
        headers[0]['collider1']=paths['A']+'/old_whole_link_collision'
        with self.assertRaises(ValueError):self.C.contact_pairs(contact,'/World/Task133/Object',paths,active)
        # Authentic failed03 rows prove noninitial contact journaling and same Task read path.
        scene=json.loads((ROOT/'outputs/mp18-manipulation-133/attempts/03/retrieved/manipulation-scene.json').read_text())
        task=self.C.Task(self.s,scene['object']['path'],scene['jaw_paths'])
        with (ROOT/'outputs/mp18-manipulation-133/attempts/03/retrieved/motion.ndjson').open() as stream:
            for step in range(3):
                row=json.loads(next(stream));self.assertEqual(row['step'],step)
                task.observe(row,row['object'],row.get('object_contacts',{}))
        self.assertEqual(task.rows,3)

    def test_14_component_data_reconstructs_original_SI_hulls(self):
        import hashlib
        import numpy as np
        import trimesh
        data=json.loads((HERE/'jaw_components.json').read_text())
        for name,row in data['jaws'].items():
            source=ROOT/row['source'];self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),row['source_sha256'])
            mesh=trimesh.load(source,force='mesh',process=True);parts=list(mesh.split(only_watertight=False));parts.sort(key=lambda p:tuple(p.bounds.reshape(-1)))
            self.assertEqual(len(parts),6)
            for part,saved in zip(parts,row['components']):
                hull=part.convex_hull
                self.assertEqual(sorted(map(tuple,hull.vertices.tolist())),sorted(map(tuple,saved['vertices_m'])))
                np.testing.assert_allclose(trimesh.Trimesh(saved['vertices_m'],saved['triangle_indices'],process=False).bounds,hull.bounds,atol=1e-12)
                self.assertEqual(len(saved['triangle_indices']),len(hull.faces));self.assertEqual(saved['original_triangles'],len(part.faces))
                self.assertAlmostEqual(saved['volume_m3'],hull.volume,places=12)


if __name__=='__main__':unittest.main(verbosity=2)
