"""Native-independent HOST evidence; no SDK, remote process, or native acceptance."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = ROOT/'outputs/mp18-isaac-119/B'
EVIDENCE.mkdir(exist_ok=True)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


N = load('native119_host', HERE/'native.py')
C = load('contract119_host', HERE/'contract.py')


def ctx_at(start=10., end=1810.):
    cfg = {'limits': {'native_s': 1800, 'cleanup_s': 2, 'import_s': 600,
                       'hold_s': 300, 'small_s': 300, 'large_s': 900},
           'approval': {'cap_mode': 'legacy'}, 'effective_caps': {'J2': 6, 'J3': 5}}
    return types.SimpleNamespace(cfg=cfg, started_monotonic=start, deadline=end,
        run=Path('HOST_ONLY'), job={'run_id': 'HOST_ONLY'}, job_hash='f'*64, sha=lambda p: 'a'*64)


class NativeHost(unittest.TestCase):
    def test_import_never_loads_sdk_or_numeric_stack(self):
        code = ('import builtins,importlib.util\nold=builtins.__import__\n'
                'def guard(name,*a,**kw):\n'
                ' if name.split(".")[0] in ("numpy","scipy","trimesh","pxr","carb","omni","isaacsim","isaaclab","isaaclab_physx"): raise RuntimeError(name)\n'
                ' return old(name,*a,**kw)\n'
                'builtins.__import__=guard\n'
                's=importlib.util.spec_from_file_location("host_safe",'+repr(str(HERE/'native.py'))+');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print("HOST_IMPORT_SAFE")')
        p = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('HOST_IMPORT_SAFE', p.stdout)

    def test_budget_startup_consumes_import_budget(self):
        b = N.Budget(ctx_at(), now=lambda: 610.)
        with self.assertRaisesRegex(N.GateFailure, 'PHASE_DEADLINE:import'):
            b.check()

    def test_budget_phase_transition_keeps_original_native_end(self):
        at = [20.]
        b = N.Budget(ctx_at(), now=lambda: at[0])
        b.enter('hold')
        self.assertEqual(b.end, 1810.)
        self.assertEqual(b.phase_end, 320.)
        at[0] = 321.
        with self.assertRaisesRegex(N.GateFailure, 'hold'):
            b.check()

    def test_headroom_reserves_declared_wall_cap_not_simulation_duration(self):
        b = N.Budget(ctx_at(end=315.), now=lambda: 20.)
        with self.assertRaisesRegex(N.GateFailure, 'HEADROOM:hold'):
            b.enter('hold')

    def test_watchdog_blocking_sdk_start_really_exits124(self):
        code = ('import importlib.util,types,time,json,pathlib\n'
                's=importlib.util.spec_from_file_location("n",'+repr(str(HERE/'native.py'))+');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)\n'
                'cfg={"limits":{"native_s":4,"cleanup_s":.01,"import_s":.7,"hold_s":1.1,"small_s":1.1,"large_s":1.1},"approval":{"cap_mode":"legacy"},"effective_caps":{}}\n'
                'def lifecycle(ctx,collector):\n print("SDK_START_BLOCK_HOST_ONLY",flush=True);time.sleep(5)\n'
                'ctx=types.SimpleNamespace(cfg=cfg,started_monotonic=time.monotonic(),deadline=time.monotonic()+4,scene_modules={"sdk":types.SimpleNamespace(lifecycle=lifecycle)},run=pathlib.Path("HOST_ONLY"),job={"run_id":"HOST_ONLY"},job_hash="f"*64,sha=lambda p:"a"*64,write=lambda *a:None)\n'
                'n.run(ctx)\n')
        start = time.monotonic()
        p = subprocess.run([sys.executable, '-I', '-B', '-u', '-c', code], capture_output=True, text=True, timeout=3)
        elapsed = time.monotonic()-start
        print(json.dumps({'fixture': 'HOST_ONLY_SDK_START_BLOCK', 'exit': p.returncode, 'elapsed_s': elapsed,
                          'stdout': p.stdout, 'stderr': p.stderr}), flush=True)
        self.assertEqual(p.returncode, 124)
        self.assertIn('SDK_START_BLOCK_HOST_ONLY', p.stdout)
        self.assertLess(elapsed, 2.)

    def test_watchdog_phase_transition_replaces_old_deadline_and_then_exits(self):
        code = ('import importlib.util,types,time\n'
                's=importlib.util.spec_from_file_location("n",'+repr(str(HERE/'native.py'))+');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)\n'
                'ctx=types.SimpleNamespace(cfg={"limits":{"native_s":4,"cleanup_s":.01,"import_s":.8,"hold_s":1.1,"small_s":1.1,"large_s":1.1}},started_monotonic=time.monotonic(),deadline=time.monotonic()+4)\n'
                'b=n.Budget(ctx).arm();time.sleep(.04);b.enter("hold");time.sleep(.8);print("PAST_OLD_IMPORT_DEADLINE",flush=True);time.sleep(5)\n')
        p = subprocess.run([sys.executable, '-I', '-B', '-u', '-c', code], capture_output=True, text=True, timeout=3)
        print(json.dumps({'fixture': 'HOST_ONLY_PHASE_TRANSITION', 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}), flush=True)
        self.assertEqual(p.returncode, 124)
        self.assertIn('PAST_OLD_IMPORT_DEADLINE', p.stdout)

    def test_wrapper_startup_exception_disarms_original_watchdog(self):
        ctx = ctx_at(start=time.monotonic(), end=time.monotonic()+1800)
        ctx.write = lambda *a: None
        def bad(*args):
            raise RuntimeError('HOST_START_FAILURE')
        ctx.scene_modules = {'sdk': types.SimpleNamespace(lifecycle=bad)}
        with self.assertRaisesRegex(RuntimeError, 'HOST_START_FAILURE'):
            N.run(ctx)
        self.assertFalse(ctx.native_budget.armed)
        self.assertIsNotNone(ctx.native_budget.process.poll())
        print(json.dumps({'fixture':'HOST_ONLY_WATCHDOG_IDENTITY_DISARM','identity':ctx.native_budget.identity,'watchdog_exit':ctx.native_budget.process.returncode,'watchdog_reaped':ctx.native_budget.process.poll() is not None}),flush=True)

    def test_duplicate_watchdog_owner_rejected(self):
        ctx = ctx_at(start=time.monotonic(), end=time.monotonic()+1800)
        N.arm_watchdog(ctx)
        try:
            with self.assertRaisesRegex(ValueError, 'second'):
                N.arm_watchdog(ctx)
        finally:
            N.disarm_watchdog(ctx)

    def test_no_later_phase_pass_without_predecessor(self):
        r = N.ledger(ctx_at())
        with self.assertRaises(ValueError):
            N.mark(r, 'small', 'PASS')
        N.mark(r, 'import', 'PASS')
        N.mark(r, 'hold', 'FAIL', 'FF_EXCEEDS_APPROVED_CAP:J2,J3')
        self.assertEqual([p['status'] for p in r['phases']], ['PASS','FAIL','NOT_RUN','NOT_RUN'])
        self.assertFalse(r['runtime_accepted'])

    def test_fixed_base_requires_actual_world_anchor_and_enabled_joint(self):
        row = dict(name='root_joint',type='fixed',enabled=True,body0='/World/Robot',body1='/World/Robot/Geometry/Base')
        self.assertTrue(N.fixed_world_joint([row], row['body1'], row['body0']))
        for key, value in [('enabled',False),('type','revolute'),('body0','/World/Other'),('body1','/World/Robot/Other')]:
            bad = dict(row, **{key:value})
            with self.assertRaises(ValueError):
                N.fixed_world_joint([bad], row['body1'], row['body0'])
        with self.assertRaises(ValueError):
            N.fixed_world_joint([row,row], row['body1'], row['body0'])

    def test_triangle_conversion_full_vertices_and_translation(self):
        import numpy as np
        p = [[0,0,0],[1,0,0],[0,1,0],[.2,.3,.4]]
        t = C.ident();t[0][3]=.5
        actual = N.triangles(p,[3,3],[0,1,3,0,3,2],t)
        self.assertEqual(actual.shape,(2,3,3))
        np.testing.assert_array_equal(actual[0,2],[.7,.3,.4])

    def test_triangle_converter_rejects_nonfinite_topology_and_indices(self):
        cases = [([[0,0,float('nan')],[1,0,0],[0,1,0]],[3],[0,1,2]),
                 ([[0,0,0],[1,0,0],[0,1,0]],[4],[0,1,2,0]),
                 ([[0,0,0],[1,0,0],[0,1,0]],[3],[0,1,3]),
                 ([[0,0,0],[1,0,0],[0,1,0]],[3],[0,1,-1])]
        for p, counts, indices in cases:
            with self.assertRaises(ValueError):
                N.triangles(p,counts,indices,C.ident())

    def test_global_native_clock_never_resets_at_stage_boundaries(self):
        baseline={'lab_step':7,'engine_time_s':0.}
        N.validate_clocks({'lab_step':247,'engine_time_s':2.},baseline,240,1/120)
        N.validate_clocks({'lab_step':1687,'engine_time_s':14.},baseline,1680,1/120)
        for clock in ({'lab_step':247,'engine_time_s':0.}, {'lab_step':7,'engine_time_s':2.}, {'lab_step':247,'engine_time_s':float('nan')}):
            with self.assertRaises(ValueError):
                N.validate_clocks(clock,baseline,240,1/120)

    def test_actual_v4_legacy_caps_exceed_q0_without_clipping(self):
        model = C.parse_model(ROOT/'models/robot-arm-urdf-v4/robot_arm.urdf')
        world=C.fk(model,{})
        poses=[{'name':n,'position':[r[3] for r in world[n][:3]],'orientation_wxyz':[1,0,0,0]} for n in C.PHYSICAL]
        # Use actual source frame rotations to derive world COMs independently below.
        import numpy as np
        from scipy.spatial.transform import Rotation
        for p in poses:
            xyzw=Rotation.from_matrix(np.array(world[p['name']])[:3,:3]).as_quat()
            p['orientation_wxyz']=[float(xyzw[3]), *xyzw[:3].tolist()]
        masses=[{'name':n,'mass':model['links'][n]['mass'],'com':model['links'][n]['com']} for n in C.PHYSICAL]
        ff=C.gravity_reference(model,poses,masses)
        remaining,bad=C.remaining_caps(model,ff)
        self.assertIn('J2',bad);self.assertIn('J3',bad)
        self.assertLess(remaining['J2'],0);self.assertLess(remaining['J3'],0)
        self.assertEqual(model['joints']['J2']['effort'],6)
        self.assertAlmostEqual(abs(ff['J2']),9.418032982,places=5)

    def test_newton_metadata_and_explicit_commands_are_separate(self):
        model={'joints':{'A':{},'B':{'mimic':{'joint':'A','multiplier':-2.,'offset':.1}}}}
        rows=[{'name':'A','path':'/A'}, {'name':'B','path':'/B','mimic':{'schemas':['NewtonMimicAPI'],
             'attributes':{'newton:mimicCoef0':{'value':.1,'times':[],'authored':True},
                           'newton:mimicCoef1':{'value':-2.,'times':[],'authored':True}},
             'relationships':{'newton:mimicJoint':['/A']}}}]
        self.assertEqual(N.verify_mimic(model,rows,C.near)['physx_mimic_constraint'],'NOT_CLAIMED')
        bad=copy.deepcopy(rows);del bad[1]['mimic']['attributes']['newton:mimicCoef1']
        with self.assertRaises(ValueError):N.verify_mimic(model,bad,C.near)
        target={'targets':{'A':.2,'B':-.3},'reference_velocity':{'A':.1,'B':-.2}}
        self.assertTrue(N.verify_coupled_targets(model,target,C.near))
        target['targets']['B']=.3
        with self.assertRaises(ValueError):N.verify_coupled_targets(model,target,C.near)

    def test_actual_program_all_source_mimic_commands(self):
        model=C.parse_model(ROOT/'models/robot-arm-urdf-v4/robot_arm.urdf')
        program=C.parse((HERE/'program.json').read_bytes())
        for name in ('hold','small','large'):
            for t in (0,program['stages'][name]['duration_s']/2,program['stages'][name]['duration_s']):
                self.assertTrue(N.verify_coupled_targets(model,C.target_at(program,name,t),C.near))

    def test_collector_gate_retains_zero_frame_and_prevents_later_motion(self):
        ctx=ctx_at(start=time.monotonic(),end=time.monotonic()+1800)
        writes={};ctx.write=lambda p,data:writes.__setitem__(p.name,copy.deepcopy(data))
        ctx.native_camera=types.SimpleNamespace(finish=lambda n,purpose:{'passed':True,'frames':n,'purpose':purpose})
        boundary=types.SimpleNamespace(finish=mock.Mock(),close=mock.Mock(return_value=[]))
        ctx.init_boundary=boundary
        def diagnostic(ctx,app,report,budget):
            N.mark(report,'import','PASS');budget.enter('hold')
            report['frames'].append({'frame_index':0,'state_index':0,'physics_time_s':0.,'phase':'hold','synthetic_host_fixture':True})
            raise N.GateFailure('FF_EXCEEDS_APPROVED_CAP:J2,J3')
        with mock.patch.object(N,'_native',diagnostic):
            N.run(types.SimpleNamespace(**vars(ctx),scene_modules={'sdk':types.SimpleNamespace(lifecycle=lambda ctx,collect:collect(ctx,None))}))
        r=writes['report.json']
        self.assertEqual([p['status'] for p in r['phases']],['PASS','FAIL','NOT_RUN','NOT_RUN'])
        self.assertEqual(r['frames'][0]['physics_time_s'],0)
        self.assertFalse(r['runtime_accepted']);boundary.close.assert_called_once()

    def test_collector_programming_exception_is_reported_and_propagated(self):
        ctx=ctx_at(start=time.monotonic(),end=time.monotonic()+1800)
        writes={};ctx.write=lambda p,data:writes.__setitem__(p.name,copy.deepcopy(data))
        ctx.scene_modules={'sdk':types.SimpleNamespace(lifecycle=lambda ctx,collect:collect(ctx,None))}
        with mock.patch.object(N,'_native',side_effect=TypeError('HOST_BUG')):
            with self.assertRaisesRegex(TypeError,'HOST_BUG'):N.run(ctx)
        self.assertEqual(writes['report.json']['phases'][0]['status'],'FAIL')
        self.assertIn('HOST_BUG',writes['report.json']['exception'])
        self.assertIsNotNone(ctx.native_budget.process.poll())

    def test_fresh_stage_rejects_reused_or_nonempty_stage_and_positive_time(self):
        writes={}
        ctx=types.SimpleNamespace(run=Path('HOST_ONLY'),write=lambda p,data:writes.__setitem__(p.name,data))
        class Stage:
            def __init__(self, layer, prims=()):self.layer,self.prims=layer,prims
            def GetRootLayer(self):return types.SimpleNamespace(identifier=self.layer)
            def GetDefaultPrim(self):return None
            def Traverse(self):return list(self.prims)
        class Context:
            def __init__(self, old, new):self.stage,self.new=old,new
            def get_stage(self):return self.stage
            def new_stage(self):self.stage=self.new;return True
        old,new=Stage('old'),Stage('new')
        self.assertIs(N.fresh_stage(ctx,Context(old,new),lambda:0.),new)
        self.assertTrue(writes['fresh-stage.json']['verified'])
        with self.assertRaisesRegex(ValueError,'Distinct'):N.fresh_stage(ctx,Context(old,old),lambda:0.)
        prim=types.SimpleNamespace(GetPath=lambda:'/ForeignRoot',GetTypeName=lambda:'Xform',GetAppliedSchemas=lambda:[])
        with self.assertRaisesRegex(ValueError,'inherited'):N.fresh_stage(ctx,Context(old,Stage('new',[prim])),lambda:0.)
        with self.assertRaisesRegex(ValueError,'positive'):N.fresh_stage(ctx,Context(old,new),lambda:.01)

    def test_watchdog_disarm_prevents_late_process_kill(self):
        code = ('import importlib.util,types,time\n'
                's=importlib.util.spec_from_file_location("n",'+repr(str(HERE/'native.py'))+');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)\n'
                'ctx=types.SimpleNamespace(cfg={"limits":{"native_s":4,"cleanup_s":.01,"import_s":.6,"hold_s":1.1,"small_s":1.1,"large_s":1.1}},started_monotonic=time.monotonic(),deadline=time.monotonic()+4)\n'
                'b=n.Budget(ctx).arm();b.disarm();time.sleep(.7);print("DISARMED_PAST_DEADLINE",flush=True)\n')
        p=subprocess.run([sys.executable,'-I','-B','-u','-c',code],capture_output=True,text=True,timeout=3)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('DISARMED_PAST_DEADLINE',p.stdout)

    def test_external_watchdog_terminates_gil_held_blocking_call(self):
        code = ('import importlib.util,types,time,ctypes\n'
                's=importlib.util.spec_from_file_location("n",'+repr(str(HERE/'native.py'))+');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)\n'
                'ctx=types.SimpleNamespace(cfg={"limits":{"native_s":4,"cleanup_s":.01,"import_s":.8,"hold_s":1.1,"small_s":1.1,"large_s":1.1}},started_monotonic=time.monotonic(),deadline=time.monotonic()+4)\n'
                'b=n.Budget(ctx).arm();print("WATCHDOG_IDENTITY:"+__import__("json").dumps(b.identity),flush=True);print("ENTER_GIL_HELD_WINDOWS_SLEEP",flush=True);f=ctypes.PyDLL("kernel32").Sleep;f.argtypes=[ctypes.c_ulong];f.restype=None;f(5000)\n')
        start=time.monotonic()
        p=subprocess.run([sys.executable,'-I','-B','-u','-c',code],capture_output=True,text=True,timeout=3)
        elapsed=time.monotonic()-start
        print(json.dumps({'fixture':'HOST_ONLY_GIL_HELD_WINAPI_BLOCK','exit':p.returncode,'elapsed_s':elapsed,'stdout':p.stdout,'stderr':p.stderr}),flush=True)
        self.assertEqual(p.returncode,124,p.stderr)
        self.assertIn('ENTER_GIL_HELD_WINDOWS_SLEEP',p.stdout)
        self.assertLess(elapsed,2.)

    def test_connected_bound_material_interface_uses_actual_leaf_and_linear_color(self):
        import xml.etree.ElementTree as ET
        paths={}
        class Attr:
            def __init__(self,path,value=None,connections=()):self.path,self.value,self.connections=path,value,connections;paths[path]=self
            def GetPath(self):return self.path
            def Get(self):return self.value
            def GetConnections(self):return self.connections
        class Input:
            def __init__(self,attr):self.attr=attr
            def GetAttr(self):return self.attr
        class Stage:
            def GetAttributeAtPath(self,path):return paths.get(str(path))
        class Material:
            def GetPath(self):return '/M'
            def GetPrim(self):return types.SimpleNamespace(GetStage=lambda:Stage())
            def ComputeSurfaceSource(self):return [shader]
        leaf=Attr('/M.inputs:diffuseColor',[.14731897,.17064494,.21404111])
        diffuse=Attr('/M/Shader.inputs:diffuseColor',None,['/M.inputs:diffuseColor'])
        opacity=Attr('/M/Shader.inputs:opacity',1.)
        shader=types.SimpleNamespace(GetInput=lambda name:Input(diffuse if name=='diffuseColor' else opacity))
        pxr=types.ModuleType('pxr');pxr.UsdGeom=types.SimpleNamespace();pxr.UsdShade=types.SimpleNamespace(MaterialBindingAPI=lambda p:types.SimpleNamespace(ComputeBoundMaterial=lambda:(Material(),None)))
        evidence=[]
        with mock.patch.dict(sys.modules,{'pxr':pxr}):
            color=N._color(object(),evidence)
            C.near(color,N.linear_rgba([.42,.45,.5,1.]),1e-6)
            self.assertEqual(evidence[0]['leaf'],'/M.inputs:diffuseColor')
            self.assertEqual(evidence[0]['chain'][0]['connections'],['/M.inputs:diffuseColor'])
            diffuse.connections=['/Other.inputs:diffuseColor']
            with self.assertRaisesRegex(ValueError,'bound material'):N._color(object())
            diffuse.connections=['/M.inputs:diffuseColor'];leaf.connections=['/M/Shader.inputs:diffuseColor']
            with self.assertRaisesRegex(ValueError,'cycle'):N._color(object())
            leaf.connections=[];diffuse.connections=['/M.inputs:diffuseColor','/M.inputs:opacity']
            with self.assertRaisesRegex(ValueError,'Single'):N._color(object())
        raw=(ROOT/'outputs/blended-reference-trial-116/native-artifacts/runs/4f38ca9612b34716947baa6f56c96e05/retrieved/initial-setup.usda').read_text()
        self.assertIn('inputs:diffuseColor.connect',raw)
        self.assertIn('0.14731897',raw)
        robot=ET.parse(ROOT/'models/robot-arm-urdf-v3/robot_arm.urdf').getroot()
        material=next(m for m in robot.findall('.//material') if m.get('name')=='base_gray')
        self.assertEqual([float(x) for x in material.find('color').get('rgba').split()],[.42,.45,.5,1.])

    def test_actual_47_group_facets_reject_material_geometry_swap(self):
        import numpy as np
        import struct
        model=C.parse_model(ROOT/'models/robot-arm-urdf-v4/robot_arm.urdf')
        groups,colors=N.source_visual_groups(model)
        self.assertEqual(sum(len(v) for v in groups.values()),47)
        dtype=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attribute','<u2')])
        actual={}
        for key,files in groups.items():
            blocks=[]
            for file in files:
                raw=(Path(model['model_dir'])/file).read_bytes();count=struct.unpack_from('<I',raw,80)[0]
                blocks.append(np.frombuffer(raw,dtype=dtype,offset=84,count=count)['v'].astype(float))
            actual[key]=np.concatenate(blocks,axis=0)
            self.assertEqual(N.visual_group(colors[key]['link'],colors[key]['linear_rgba'],colors),key)
        metrics=C.verify_geometry(model,actual,visual_groups=groups)
        self.assertEqual(set(metrics),set(groups))
        pair=[k for k in groups if colors[k]['link']=='Base'][:2]
        mutant=dict(actual);mutant[pair[0]],mutant[pair[1]]=actual[pair[1]],actual[pair[0]]
        # The union of every facet is unchanged; only its material assignment is swapped.
        with self.assertRaises(ValueError):C.verify_geometry(model,mutant,visual_groups=groups)
        bad=dict(groups);bad.pop(pair[0])
        with self.assertRaises(ValueError):C.verify_geometry(model,{k:actual[k] for k in bad},visual_groups=bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)
