"""119 v4 native collector. Importing this module never imports an SDK or numeric stack."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import time
import threading
import subprocess
import sys
import traceback

PHASES = ('import', 'hold', 'small', 'large')


def need(ok, message):
    if not ok:
        raise ValueError(message)


class GateFailure(RuntimeError):
    """An observed gate failure; later phases must remain NOT_RUN."""


WATCHDOG_CODE = r'''
import ctypes,json,math,os,queue,sys,threading,time
from ctypes import wintypes
pid=int(sys.argv[1]);deadline=float(sys.argv[2]);native_end=float(sys.argv[3])
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
k.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT];k.TerminateProcess.restype=wintypes.BOOL
k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
k.CloseHandle.argtypes=[wintypes.HANDLE]
k.GetProcessTimes.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME)]
handle=k.OpenProcess(0x100001|0x1000,False,pid)
if not handle:raise OSError(ctypes.get_last_error())
creation,exit,kernel,user=[wintypes.FILETIME() for _ in range(4)]
if not k.GetProcessTimes(handle,ctypes.byref(creation),ctypes.byref(exit),ctypes.byref(kernel),ctypes.byref(user)):raise OSError(ctypes.get_last_error())
birth=(creation.dwHighDateTime<<32)|creation.dwLowDateTime
if os.getppid()!=pid:raise RuntimeError('Watchdog parent mismatch')
messages=queue.Queue()
def reader():
    try:
        for line in sys.stdin:
            messages.put(json.loads(line))
        messages.put({'op':'eof'})
    except BaseException:messages.put({'op':'invalid'})
threading.Thread(target=reader,daemon=True).start()
print(json.dumps({'watchdog_pid':os.getpid(),'parent_pid':pid,'parent_birth':birth,'sdk_imports':sum(1 for n in sys.modules if n.split('.')[0] in ('isaacsim','isaaclab','omni','pxr','carb'))}),flush=True)
try:
    while True:
        if k.WaitForSingleObject(handle,0)==0:break
        remaining=min(deadline,native_end)-time.monotonic()
        if remaining<=0:
            if not k.TerminateProcess(handle,124):raise OSError(ctypes.get_last_error())
            k.WaitForSingleObject(handle,1000)
            break
        try:row=messages.get(timeout=min(.025,remaining))
        except queue.Empty:continue
        if row=={'op':'disarm'}:break
        if set(row)=={'op','deadline'} and row['op']=='phase' and type(row['deadline']) in (float,int) and math.isfinite(row['deadline']) and row['deadline']<=native_end:
            deadline=row['deadline']
        else:deadline=0.0
finally:k.CloseHandle(handle)
'''


def process_birth():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)]*4]
    values = [wintypes.FILETIME() for _ in range(4)]
    need(kernel.GetProcessTimes(kernel.GetCurrentProcess(), *[ctypes.byref(v) for v in values]), 'Actual parent process birth')
    return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime


class Budget:
    """One external stdlib deadline owner, unaffected by SDK calls holding the GIL."""
    def __init__(self, ctx, now=time.monotonic):
        self.now, self.cfg = now, ctx.cfg['limits']
        self.start = ctx.started_monotonic
        self.end = min(ctx.deadline, self.start+self.cfg['native_s'])
        self.phase, self.entered = 'import', self.start
        self.phase_end = self.start+self.cfg['import_s']
        self.lock = threading.RLock()
        self.armed, self.process, self.identity = False, None, None

    def enter(self, phase):
        need(phase in PHASES, 'Closed native phase')
        with self.lock:
            self.check()
            self.phase, self.entered = phase, self.now()
            self.phase_end = self.entered+self.cfg[phase+'_s']
            if self.end-self.entered < self.cfg[phase+'_s']+self.cfg['cleanup_s']:
                raise GateFailure('INSUFFICIENT_NATIVE_HEADROOM:'+phase)
            if self.armed:
                self._send({'op': 'phase', 'deadline': min(self.phase_end, self.end-self.cfg['cleanup_s'])})

    def check(self):
        with self.lock:
            at = self.now()
            if self.armed:
                need(self.process.poll() is None, 'External deadline owner unexpectedly exited')
            if at >= self.end-self.cfg['cleanup_s']:
                raise GateFailure('NATIVE_DEADLINE')
            if at >= self.phase_end:
                raise GateFailure('PHASE_DEADLINE:'+self.phase)
            return at

    def _send(self, row):
        need(self.process is not None and self.process.poll() is None, 'Live single watchdog')
        self.process.stdin.write(json.dumps(row, allow_nan=False)+'\n')
        self.process.stdin.flush()

    def arm(self):
        with self.lock:
            need(os.name == 'nt', '119 native owner is Windows only')
            need(not self.armed and self.process is None, 'One native watchdog only')
            end = self.end-self.cfg['cleanup_s']
            interpreter = getattr(sys, '_base_executable', sys.executable)
            need(Path(interpreter).is_file(), 'Actual current interpreter base executable')
            self.process = subprocess.Popen([interpreter, '-I', '-S', '-B', '-u', '-c', WATCHDOG_CODE,
                str(os.getpid()), repr(min(self.phase_end, end)), repr(end)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
            ready, observed = threading.Event(), {}
            def handshake():
                try:observed['line'] = self.process.stdout.readline()
                except BaseException as exc:observed['error'] = str(exc)
                finally:ready.set()
            thread = threading.Thread(target=handshake, name='native119-watchdog-handshake', daemon=True)
            thread.start()
            try:
                need(ready.wait(2.) and observed.get('line'), 'Bounded external watchdog handshake')
                identity = json.loads(observed['line'])
                need(identity == {'watchdog_pid': self.process.pid, 'parent_pid': os.getpid(),
                                  'parent_birth': process_birth(), 'sdk_imports': 0}, 'Actual watchdog binds original parent process handle')
                self.identity, self.armed = identity, True
            except BaseException:
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=1.)
                diagnostic = self.process.stderr.read()
                for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                    pipe.close()
                raise RuntimeError('WATCHDOG_HANDSHAKE_FAILED:'+diagnostic)
        return self

    def disarm(self):
        with self.lock:
            if self.process is None or not self.armed:
                return
            self._send({'op': 'disarm'})
            self.armed = False
        try:
            self.process.wait(timeout=1.)
            need(self.process.returncode == 0, 'External watchdog clean exit')
        except subprocess.TimeoutExpired:
            self.process.kill();self.process.wait(timeout=1.)
            raise RuntimeError('Watchdog did not disarm within cleanup budget')
        finally:
            for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                pipe.close()


def arm_watchdog(ctx):
    need(not hasattr(ctx, 'native_budget'), 'No second native deadline owner')
    ctx.native_budget = Budget(ctx).arm()
    return ctx.native_budget


def disarm_watchdog(ctx):
    if hasattr(ctx, 'native_budget'):
        ctx.native_budget.disarm()


def run(ctx):
    """Arm before pinned lifecycle.start so the 600-second import cap includes startup."""
    arm_watchdog(ctx)
    try:
        ctx.write(ctx.run/'output/report.partial.json', ledger(ctx))
        return ctx.scene_modules['sdk'].lifecycle(ctx, collect)
    finally:
        disarm_watchdog(ctx)


def ledger(ctx):
    return {'schema_version': 1, 'unit': 119, 'run_id': ctx.job['run_id'],
            'job_sha256': ctx.job_hash, 'pid': os.getpid(), 'hardware_approved': False,
            'model_sha256': ctx.sha(ctx.run/'input/model/robot_arm.urdf'),
            'cap_mode': ctx.cfg['approval']['cap_mode'], 'effective_caps': ctx.cfg['effective_caps'],
            'phases': [{'name': n, 'status': 'NOT_RUN', 'reason': 'PRECEDING_GATE'} for n in PHASES],
            'watchdog': getattr(getattr(ctx, 'native_budget', None), 'identity', None),
            'frames': [], 'completed_steps': 0, 'render': {'passed': False, 'reason': 'NOT_RUN'},
            'runtime_accepted': False, 'physics_scope': 'SIMULATION_ONLY_ESTIMATED_MATERIALS_SELF_COLLISION_OFF'}


def mark(report, name, status, reason='', **data):
    need(name in PHASES and status in ('PASS', 'FAIL', 'NOT_RUN'), 'Closed phase result')
    index = PHASES.index(name)
    if status == 'PASS':
        need(all(p['status'] == 'PASS' for p in report['phases'][:index]), 'Preceding phases must pass')
    report['phases'][index] = dict(name=name, status=status, reason=reason, **data)
    if status == 'FAIL':
        for i in range(index+1, len(PHASES)):
            report['phases'][i] = {'name': PHASES[i], 'status': 'NOT_RUN', 'reason': 'PRECEDING_'+name.upper()+'_FAIL'}
    report['runtime_accepted'] = all(p['status'] == 'PASS' for p in report['phases'])


def triangles(points, counts, indices, matrix):
    """Linear point/face conversion; no pairwise vertex deduplication or AABB proxy."""
    import numpy as np
    p, f, counts = np.asarray(points, dtype=float), np.asarray(indices, dtype=np.int64), np.asarray(counts)
    need(p.ndim == 2 and p.shape[1] == 3 and np.isfinite(p).all(), 'Finite actual mesh points')
    need(counts.ndim == 1 and len(counts) > 0 and bool((counts == 3).all()), 'Actual imported STL triangle topology')
    need(f.shape == (len(counts)*3,) and bool(((f >= 0) & (f < len(p))).all()), 'Complete bounded mesh indices')
    t = np.asarray(matrix, dtype=float)
    need(t.shape == (4, 4) and np.isfinite(t).all(), 'Finite mesh-to-owner transform')
    world = p @ t[:3, :3].T + t[:3, 3]
    return world[f].reshape((-1, 3, 3))


def fixed_world_joint(joints, base_path, scope):
    rows = [j for j in joints if j['name'] == 'root_joint']
    need(len(rows) == 1, 'Exactly one world fixed joint')
    j = rows[0]
    need(j['type'] == 'fixed' and j['enabled'] is True and j['body1'] == base_path and
         j['body0'] == scope, 'Enabled fixed Base to nonphysical world ancestor')
    return True


def validate_clocks(clock, baseline, step, dt):
    need(type(clock['lab_step']) is int and clock['lab_step']-baseline['lab_step'] == step,
         'Actual Lab physics step count')
    need(math.isfinite(clock['engine_time_s']) and
         abs(clock['engine_time_s']-baseline['engine_time_s']-step*dt) <= 1e-6,
         'Actual engine clock follows only commanded positive steps')


def _matrix(gf):
    # Gf row-vector convention -> contract column-vector convention.
    return [[float(gf[j][i]) for j in range(4)] for i in range(4)]


def _q(q):
    return [float(q.GetReal()), *[float(x) for x in q.GetImaginary()]]


def linear_rgba(color):
    need(len(color) == 4 and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in color), 'Finite source sRGB RGBA')
    return [x/12.92 if x <= .04045 else ((x+.055)/1.055)**2.4 for x in color[:3]]+[color[3]]


def source_visual_groups(model):
    groups, colors = {}, {}
    for link, body in model['links'].items():
        for visual in body['visuals']:
            linear = linear_rgba(visual['color'])
            key = link+'|'+json.dumps(linear, separators=(',', ':'))
            groups.setdefault(key, []).append(visual['file'])
            colors[key] = {'link': link, 'linear_rgba': linear}
    return groups, colors


def visual_group(link, actual_linear, groups):
    need(len(actual_linear) == 4 and all(math.isfinite(v) for v in actual_linear), 'Finite actual linear RGBA')
    matches = [key for key, value in groups.items() if value['link'] == link and
               max(abs(a-b) for a, b in zip(actual_linear, value['linear_rgba'])) <= 2e-5]
    need(len(matches) == 1, 'Unique source link/material group for actual linear color')
    return matches[0]


def _input_value(shader, material, name, evidence):
    value_input = shader.GetInput(name)
    if not value_input:
        return None
    attr = value_input.GetAttr()
    visited = set()
    stage = material.GetPrim().GetStage()
    material_path = str(material.GetPath())
    chain = []
    for _ in range(8):
        path = str(attr.GetPath())
        need(path not in visited, 'Material interface connection cycle')
        visited.add(path)
        connections = list(attr.GetConnections())
        chain.append({'attribute': path, 'connections': [str(p) for p in connections]})
        if not connections:
            value = attr.Get()
            evidence.append({'input': name, 'chain': chain, 'leaf': path})
            return value
        need(len(connections) == 1, 'Single material interface source')
        target = str(connections[0])
        need(target.startswith(material_path+'.inputs:') or target.startswith(material_path+'/') and '.inputs:' in target,
             'Connected source belongs to the bound material interface')
        attr = stage.GetAttributeAtPath(connections[0])
        need(bool(attr), 'Actual connected material attribute exists')
    raise ValueError('Material interface connection depth')


def _color(prim, evidence=None):
    from pxr import UsdGeom, UsdShade
    evidence = [] if evidence is None else evidence
    material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
    if material:
        shader = material.ComputeSurfaceSource()[0]
        need(bool(shader), 'Actual bound surface shader')
        value = _input_value(shader, material, 'diffuseColor', evidence)
        alpha = _input_value(shader, material, 'opacity', evidence)
        need(value is not None and len(value) == 3, 'Resolved actual bound diffuse color')
        return [*[float(x) for x in value], 1. if alpha is None else float(alpha)]
    value = UsdGeom.Gprim(prim).GetDisplayColorAttr().Get()
    opacity = UsdGeom.Gprim(prim).GetDisplayOpacityAttr().Get()
    need(value is not None and len(value) == 1, 'Actual uniform source visual material color')
    evidence.append({'display_color_prim': str(prim.GetPath())})
    return [*[float(x) for x in value[0]], float(opacity[0]) if opacity is not None and len(opacity) == 1 else 1.]


def _mimic(prim):
    # This installed importer emits NewtonMimicAPI metadata even for the PhysX backend.
    # Read schema fallback values through real USD attributes; never assume absent == 1/0.
    attrs, rels = {}, {}
    for attr in prim.GetAttributes():
        name = str(attr.GetName())
        if name.startswith('newton:mimic') or name.startswith('physxMimicJoint:'):
            value = attr.Get()
            attrs[name] = {'value': value, 'authored': bool(attr.HasAuthoredValueOpinion()),
                           'times': [float(x) for x in attr.GetTimeSamples()], 'type': str(attr.GetTypeName())}
    for rel in prim.GetRelationships():
        if str(rel.GetName()).startswith(('newton:mimic', 'physxMimicJoint:')):
            rels[str(rel.GetName())] = [str(p) for p in rel.GetTargets()]
    return {'schemas': list(prim.GetAppliedSchemas()), 'attributes': attrs, 'relationships': rels}


def verify_mimic(model, rows, near):
    lookup = {j['name']: j for j in rows}
    for name, source in model['joints'].items():
        if 'mimic' not in source:
            continue
        data, m = lookup[name]['mimic'], source['mimic']
        need('NewtonMimicAPI' in data['schemas'], 'Actual installed importer Newton mimic metadata')
        need(data['relationships'].get('newton:mimicJoint') == [lookup[m['joint']]['path']], 'Exact actual mimic leader')
        for key, value in (('newton:mimicCoef0', m['offset']), ('newton:mimicCoef1', m['multiplier'])):
            attr = data['attributes'].get(key)
            need(attr is not None and attr['times'] == [] and attr['value'] is not None, 'Actual USD schema coefficient/fallback readback')
            near(float(attr['value']), value, max(1e-6, abs(value)*1e-6))
    return {'source_followers': [n for n, j in model['joints'].items() if 'mimic' in j],
            'status': 'IMPORTED_METADATA_AND_EXPLICIT_NINE_DOF_COMMANDS',
            'physical_gear_contact': 'NOT_VERIFIED', 'physx_mimic_constraint': 'NOT_CLAIMED'}


def verify_coupled_targets(model, target, near):
    for name, source in model['joints'].items():
        if 'mimic' in source:
            m = source['mimic']
            near(target['targets'][name], target['targets'][m['joint']]*m['multiplier']+m['offset'], 1e-7)
            near(target['reference_velocity'][name], target['reference_velocity'][m['joint']]*m['multiplier'], 1e-7)
    return True


def observe(stage, ctx, geometry=True):
    """Actual composed USD readback. Numeric/SDK imports occur only after bootstrap."""
    import numpy as np
    from pxr import Gf, Usd, UsdGeom, UsdPhysics
    C, model = ctx.contract, ctx.model
    prims = list(Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()))
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    body_prims = {str(p.GetPath()): p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)}
    names = [p.GetName() for p in body_prims.values()]
    need(len(names) == len(set(names)) == 11 and set(names) == set(C.PHYSICAL), 'Exact eleven physical USD bodies')
    body_paths = {p.GetName(): path for path, p in body_prims.items()}
    kinds = {kind: {n: [] for n in C.PHYSICAL} for kind in ('visual', 'collision')}
    counts = {kind: {n: 0 for n in C.PHYSICAL} for kind in kinds}
    colors = {n: [] for n in C.PHYSICAL}
    visual_sources, group_colors = source_visual_groups(model)
    grouped_triangles = {key: [] for key in visual_sources}
    group_counts = {key: 0 for key in visual_sources}
    material_bindings = []
    collision_rows, owner_cache = [], {}
    def owner(prim):
        path = str(prim.GetPath())
        if path in owner_cache:
            return owner_cache[path]
        cursor, chain, collision, hidden = prim, [], False, False
        while cursor and not cursor.IsPseudoRoot():
            chain.append(str(cursor.GetPath()))
            collision = collision or cursor.HasAPI(UsdPhysics.CollisionAPI)
            if cursor.IsA(UsdGeom.Imageable):
                image = UsdGeom.Imageable(cursor)
                hidden = hidden or image.ComputeVisibility() == UsdGeom.Tokens.invisible
            if str(cursor.GetPath()) in body_prims:
                result = (cursor.GetName(), collision, hidden)
                owner_cache[path] = result
                return result
            cursor = cursor.GetParent()
        return None, collision, hidden
    for prim in prims:
        if not prim.IsA(UsdGeom.Mesh):
            continue
        name, collision, hidden = owner(prim)
        if name is None:
            continue
        kind = 'collision' if collision else 'visual'
        if kind == 'visual' and hidden:
            continue
        mesh = UsdGeom.Mesh(prim)
        counts[kind][name] += 1
        if kind == 'visual':
            color_evidence = []
            actual_color = _color(prim, color_evidence)
            colors[name].append(actual_color)
            group = visual_group(name, actual_color, group_colors)
            group_counts[group] += 1
            material_bindings.append({'mesh': str(prim.GetPath()), 'source_group': group, 'linear_rgba': actual_color, 'connections': color_evidence})
        else:
            collision_api = UsdPhysics.CollisionAPI(prim)
            enabled = collision_api.GetCollisionEnabledAttr().Get()
            need(enabled is True, 'Actual model collider enabled')
            approximation = UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() if prim.HasAPI(UsdPhysics.MeshCollisionAPI) else None
            collision_rows.append({'path': str(prim.GetPath()), 'owner': name, 'enabled': enabled,
                                   'approximation': None if approximation is None else str(approximation)})
        if geometry:
            transform = cache.GetLocalToWorldTransform(prim) * cache.GetLocalToWorldTransform(body_prims[body_paths[name]]).GetInverse()
            actual_triangles = triangles(mesh.GetPointsAttr().Get(), mesh.GetFaceVertexCountsAttr().Get(),
                                         mesh.GetFaceVertexIndicesAttr().Get(), _matrix(transform))
            kinds[kind][name].append(actual_triangles)
            if kind == 'visual':
                grouped_triangles[group].append(actual_triangles)
    need(all(group_counts[key] == len(files) for key, files in visual_sources.items()), 'Complete per-link material mesh group census')
    rows = []
    for path, prim in body_prims.items():
        mass = UsdPhysics.MassAPI(prim)
        need(prim.HasAPI(UsdPhysics.MassAPI), 'Authored native mass properties')
        attrs = [mass.GetMassAttr(), mass.GetCenterOfMassAttr(), mass.GetDiagonalInertiaAttr(), mass.GetPrincipalAxesAttr()]
        need(all(a.HasAuthoredValueOpinion() and not a.GetTimeSamples() for a in attrs), 'All static mass properties authored')
        diagonal = [float(x) for x in attrs[2].Get()]
        R = C.quat(_q(attrs[3].Get()))
        I = C.mm(C.mm(R, [[diagonal[i] if i == j else 0. for j in range(3)] for i in range(3)]), C.tr(R))
        name = prim.GetName()
        expected_colors = sorted(linear_rgba(v['color']) for v in model['links'][name]['visuals'])
        actual_colors = sorted(colors[name])
        C.near(actual_colors, expected_colors, 2e-5)
        rows.append({'name': name, 'path': path, 'mass': float(attrs[0].Get()),
                     'com': [float(x) for x in attrs[1].Get()], 'inertia_link_about_com': I,
                     'T_world': _matrix(cache.GetLocalToWorldTransform(prim)),
                     'visual_count': counts['visual'][name], 'collision_count': counts['collision'][name],
                     'visual_colors': actual_colors, 'applied_schemas': list(prim.GetAppliedSchemas())})
    def target(rel):
        result = [str(p) for p in rel.GetTargets()]
        need(len(result) <= 1, 'Unambiguous joint body')
        return result[0] if result else None
    joints = []
    for prim in prims:
        if not prim.IsA(UsdPhysics.Joint):
            continue
        j = UsdPhysics.Joint(prim)
        a, b = target(j.GetBody0Rel()), target(j.GetBody1Rel())
        revolute = prim.IsA(UsdPhysics.RevoluteJoint)
        prismatic = prim.IsA(UsdPhysics.PrismaticJoint)
        kind = 'revolute' if revolute else 'prismatic' if prismatic else 'fixed' if prim.IsA(UsdPhysics.FixedJoint) else None
        need(kind is not None, 'Supported actual joint type')
        row = {'name': prim.GetName(), 'path': str(prim.GetPath()), 'type': kind,
               'body0': a, 'body1': b, 'parent': Path(a).name if a else None, 'child': Path(b).name if b else None,
               'enabled': j.GetJointEnabledAttr().Get(), 'applied_schemas': list(prim.GetAppliedSchemas()),
               'anchor0': C.tf([float(x) for x in j.GetLocalPos0Attr().Get()], C.quat(_q(j.GetLocalRot0Attr().Get()))),
               'anchor1': C.tf([float(x) for x in j.GetLocalPos1Attr().Get()], C.quat(_q(j.GetLocalRot1Attr().Get()))),
               'mimic': _mimic(prim)}
        if revolute or prismatic:
            dynamic = UsdPhysics.RevoluteJoint(prim) if revolute else UsdPhysics.PrismaticJoint(prim)
            factor = math.pi/180 if revolute else 1.
            row.update(axis=str(dynamic.GetAxisAttr().Get()), lower=float(dynamic.GetLowerLimitAttr().Get())*factor,
                       upper=float(dynamic.GetUpperLimitAttr().Get())*factor)
        joints.append(row)
    roots = [str(p.GetPath()) for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    tool = [p for p in prims if p.GetName() == 'tool0']
    need(len(tool) == 1, 'One frame-only tool0')
    scope = '/World/Robot'
    fixed = fixed_world_joint(joints, body_paths['Base'], scope) if str(stage.GetDefaultPrim().GetPath()) == '/World' else False
    packet = {'material_bindings': material_bindings, 'visual_groups': visual_sources, 'links': rows, 'bodies': rows, 'joints': joints, 'colliders': collision_rows,
              'fixed_base': fixed, 'articulation_count': len(roots), 'articulation_path': roots[0] if len(roots) == 1 else None,
              'tool0': {'physical': tool[0].HasAPI(UsdPhysics.RigidBodyAPI) or tool[0].HasAPI(UsdPhysics.MassAPI),
                        'T_world': _matrix(cache.GetLocalToWorldTransform(tool[0]))},
              'units': {'meters': float(UsdGeom.GetStageMetersPerUnit(stage)), 'kilograms': float(UsdPhysics.GetStageKilogramsPerUnit(stage)), 'up': str(UsdGeom.GetStageUpAxis(stage))}}
    C.near(packet['units'], {'meters': 1., 'kilograms': 1., 'up': 'Z'}, 0)
    if geometry:
        for kind in kinds:
            for name in kinds[kind]:
                need(bool(kinds[kind][name]), 'Missing complete native mesh owner')
                kinds[kind][name] = np.concatenate(kinds[kind][name], axis=0)
        kinds['visual_groups'] = {key: np.concatenate(value, axis=0) for key, value in grouped_triangles.items()}
        kinds['visual_sources'] = visual_sources
    return packet, kinds


def _import(ctx, app, budget):
    from pxr import Usd
    import omni.timeline
    sdk = ctx.scene_modules['sdk']
    for ext in ('omni.scene.optimizer.core', 'isaacsim.robot.schema', 'isaacsim.asset.importer.urdf'):
        sdk.enable(ext)
    from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig
    timeline = omni.timeline.get_timeline_interface()
    need(timeline.is_stopped(), 'Importer starts with stopped timeline')
    out = ctx.run/'output'
    settings = {'urdf_path': str(ctx.run/'input/model/robot_arm.urdf'), 'usd_path': str(out/'imported'),
        'merge_mesh': False, 'merge_fixed_joints': False, 'collision_from_visuals': False,
        'allow_self_collision': False, 'fix_base': True, 'link_density': None, 'joint_drive_type': None,
        'joint_target_type': None, 'override_joint_stiffness': None, 'override_joint_damping': None,
        'run_asset_transformer': False, 'run_multi_physics_conversion': False}
    ctx.write(out/'import-settings.json', settings)
    asset = Path(URDFImporter(URDFImporterConfig(**settings)).import_urdf()).resolve()
    budget.check()
    need(asset.is_file() and asset.is_relative_to((out/'imported').resolve()), 'Owned actual importer result')
    # Do not activate an imported stage and leave its root beside the Lab scene.
    stage = Usd.Stage.Open(str(asset))
    need(bool(stage), 'Actual imported saved stage opens')
    stage.Flatten().Export(str(out/'raw-import.usda'))
    correction = sdk.normalize_tool(stage, ctx.model)
    stage.Flatten().Export(str(out/'model.usda'))
    ctx.write(out/'tool0-normalization.json', correction)
    need(timeline.is_stopped(), 'No physics during import and frame-only normalization')
    return out/'model.usda'


def fresh_stage(ctx, context, clock):
    """Prove old importer/current stage cannot leak an articulation into the new Lab scene."""
    old = context.get_stage()
    def census(stage):
        if stage is None:
            return None
        return {'layer': str(stage.GetRootLayer().identifier),
                'default_prim': str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else None,
                'prims': [{'path': str(p.GetPath()), 'type': str(p.GetTypeName()),
                           'applied_schemas': list(p.GetAppliedSchemas())} for p in stage.Traverse()]}
    before, engine_before = census(old), float(clock())
    need(engine_before == 0., 'No positive physics time before fresh Lab stage')
    result = context.new_stage()
    new = context.get_stage()
    after, engine_after = census(new), float(clock())
    need(result is not False and new is not None and after is not None, 'Actual fresh stage created')
    need(before is None or before['layer'] != after['layer'], 'Distinct actual fresh layer identity')
    need(after['prims'] == [] and after['default_prim'] is None, 'Fresh stage has no inherited roots or objects')
    need(engine_after == engine_before == 0., 'Fresh stage preserves zero engine clock')
    ctx.write(ctx.run/'output/fresh-stage.json', {'before': before, 'after': after,
              'engine_before_s': engine_before, 'engine_after_s': engine_after, 'verified': True})
    return new


def _root_packet(stage, packet):
    from pxr import Usd, UsdGeom, UsdPhysics
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    scope = '/World/Robot'
    prim = stage.GetPrimAtPath(scope)
    packet['world_anchors'] = {scope: {'rigid_body': prim.HasAPI(UsdPhysics.RigidBodyAPI),
        'mass_api': prim.HasAPI(UsdPhysics.MassAPI), 'type': str(prim.GetTypeName()),
        'world_matrix': [[float(cache.GetLocalToWorldTransform(prim)[i][j]) for j in range(4)] for i in range(4)],
        'time_samples': sum(len(UsdGeom.Xformable(prim).GetOrderedXformOps()[i].GetTimeSamples()) for i in range(len(UsdGeom.Xformable(prim).GetOrderedXformOps()))),
        'applied_schemas': list(prim.GetAppliedSchemas())}}
    return packet


def _native(ctx, app, report, budget):
    import carb
    import numpy as np
    import omni.timeline
    import omni.usd
    import omni.physx
    import isaacsim.core.experimental.utils.backend as backend
    import isaacsim.core.experimental.utils.stage as stage_utils
    from isaacsim.core.experimental.prims import Articulation, RigidPrim
    from isaacsim.core.simulation_manager import SimulationManager
    from isaaclab.sim import SimulationCfg, SimulationContext
    from isaaclab_physx.physics.physx_manager import PhysxManager
    from pxr import Gf, UsdGeom, UsdPhysics, PhysxSchema
    C, model, sdk, out = ctx.contract, ctx.model, ctx.scene_modules['sdk'], ctx.run/'output'
    program = ctx.cfg['program']
    imported = _import(ctx, app, budget)
    fresh_stage(ctx, omni.usd.get_context(), SimulationManager.get_simulation_time)
    budget.check()
    boundary = ctx.scene_modules['init_boundary'].Boundary(ctx, PhysxManager, omni.physx.get_physx_interface(),
        carb.settings.get_settings(), SimulationManager.get_simulation_time)
    ctx.init_boundary = boundary
    sim = SimulationContext(SimulationCfg(dt=1/120, device='cpu', gravity=(0., 0., -9.81),
        physics_prim_path='/World/physicsScene', use_newton_actuators=False))
    stage = sim.stage
    UsdGeom.Xform.Define(stage, '/World')
    stage_utils.set_stage_units(meters_per_unit=1., kilograms_per_unit=1.)
    stage_utils.set_stage_up_axis('Z')
    stage_utils.add_reference_to_stage(str(imported), '/World/Robot')
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    timeline = omni.timeline.get_timeline_interface()
    need(timeline.is_stopped(), 'New Lab stage begins stopped')
    floor = UsdGeom.Cube.Define(stage, program['floor']['path'])
    floor.GetSizeAttr().Set(program['floor']['size'])
    floor.AddTranslateOp().Set(Gf.Vec3d(*program['floor']['translation']))
    floor.AddScaleOp().Set(Gf.Vec3f(*program['floor']['scale']))
    UsdPhysics.CollisionAPI.Apply(floor.GetPrim()).GetCollisionEnabledAttr().Set(True)
    before, shapes = observe(stage, ctx)
    ctx.write(out/'import-static-before.json', before)
    before_path, after_path = out/'base-before.usda', out/'base-after.usda'
    stage.Flatten().Export(str(before_path))
    root = ctx.scene_modules['root_binding']
    normalization = root.normalize(stage, _root_packet(stage, before), [before['articulation_path']], timeline)
    root_prim = stage.GetPrimAtPath(normalization['after_root'])
    attr = PhysxSchema.PhysxArticulationAPI(root_prim).GetEnabledSelfCollisionsAttr()
    need(str(attr.GetPath()) == '/World/Robot.physxArticulation:enabledSelfCollisions' and str(attr.GetTypeName()) == 'bool', 'Exact typed PhysX policy')
    need(attr.Set(False) is True and attr.Get() is False, 'Authored self collision OFF')
    stage.Flatten().Export(str(after_path))
    report['fixed_base_binding'] = {'normalization': normalization, 'provider': root.prove_files(before_path, after_path)}
    packet, _ = observe(stage, ctx, geometry=False)
    report['import_static'] = C.verify_static(model, packet, ctx.cfg)
    report['mimic'] = verify_mimic(model, packet['joints'], C.near)
    report['geometry'] = {
        'visual': C.verify_geometry(model, shapes['visual_groups'], kind='visual',
            tolerance=ctx.cfg['geometry_tolerance_m'], visual_groups=shapes['visual_sources']),
        'collision': C.verify_geometry(model, shapes['collision'], kind='collision',
            tolerance=ctx.cfg['geometry_tolerance_m'])}
    del shapes
    ctx.write(out/'import-static.json', packet)
    paths = {r['name']: r['path'] for r in packet['links']}
    robot = Articulation('/World/Robot')
    links = [(name, RigidPrim(paths[name])) for name in C.PHYSICAL]
    names = list(robot.dof_names)
    C.named_columns(names, model['movable'], [0.]*len(names))
    caps = ctx.cfg['effective_caps']
    # Revalidate explicit approval at the last native use; never infer an override.
    C.near(caps, C.effective_caps(ctx.cfg, ctx.cfg['approval']), 0)
    with backend.use_backend('usd', raise_on_unsupported=True, raise_on_fallback=True):
        robot.set_dof_drive_types('acceleration')
        robot.set_dof_gains([64.]*9, [16.]*9)
        robot.set_dof_max_efforts([caps[n] for n in names])
        robot.set_dof_max_velocities([model['joints'][n]['velocity'] for n in names])
        robot.set_enabled_self_collisions(False)
        robot.set_link_enabled_gravities(True)
    need(attr.Get() is False, 'Actual self-collision OFF remains')
    support, workspace = C.parse(ctx.data['ref/support.json']), C.parse(ctx.data['ref/workspace.json'])
    camera = ctx.scene_modules['capture'].NativeCapture(ctx, stage, program, workspace)
    ctx.native_camera = camera
    stage.Flatten().Export(str(out/'scene.usda'))
    budget.check()
    sim.reset()
    boundary.after_reset()
    need(timeline.is_playing(), 'Lab reset starts timeline only after zero-time boundary')
    report['binding'] = sdk.bind(ctx, sim, [robot, *[prim for _, prim in links]])
    need(robot._physics_articulation_view.shared_metatype.fixed_base is True, 'Actual tensor fixed base')
    need(list(robot.dof_names) == names and set(robot.link_names) == set(C.PHYSICAL) and len(robot.link_names) == 11, 'Unchanged nine DOFs and eleven tensor links')
    inertias = sdk.runtime_inertias(ctx, links)
    report['runtime_inertias'] = C.check_runtime_inertias(model, inertias)
    ctx.write(out/'runtime-inertias.json', inertias)
    def array(value):
        return value.numpy().copy()
    def clock():
        return {'engine_time_s': float(SimulationManager.get_simulation_time()), 'lab_step': int(sim.get_physics_step_count())}
    def state():
        before = clock()
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            q = C.named_columns(names, model['movable'], array(robot.get_dof_positions())[0])
            qd = C.named_columns(names, model['movable'], array(robot.get_dof_velocities())[0])
            poses = []
            for name, prim in links:
                pos, rotation = prim.get_world_poses()
                poses.append({'name': name, 'position': array(pos)[0].tolist(), 'orientation_wxyz': array(rotation)[0].tolist()})
        after = clock()
        need(before == after, 'Stable native read clock')
        for pose in poses:
            need(all(math.isfinite(x) for x in pose['position']+pose['orientation_wxyz']), 'Finite actual body pose')
            C.quat(pose['orientation_wxyz'])
        return {'clock': after, 'clock_before': before, 'clock_after': after, 'q': q, 'qd': qd, 'body_poses': poses}
    with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
        robot.set_dof_gains([[64.]*9], [[16.]*9])
        kp, kd = robot.get_dof_gains()
        need(all(v == 64. for v in C.named_columns(names, model['movable'], array(kp)[0]).values()) and
             all(v == 16. for v in C.named_columns(names, model['movable'], array(kd)[0]).values()), 'Actual unchanged 64/16 gains')
    boundary.ready(lambda: {k: v for k, v in state().items() if k in ('q', 'qd')})
    baseline, current = clock(), state()
    need(baseline['engine_time_s'] == 0., 'Actual initialization time zero')
    report['initial_state'] = current
    budget.check()
    mark(report, 'import', 'PASS', elapsed_s=time.monotonic()-ctx.started_monotonic)
    ctx.write(out/'report.partial.json', report)
    def tcp(observed):
        pose = next(p for p in observed['body_poses'] if p['name'] == 'KG1')
        offset = model['joints']['tool0_mount']['origin'][0]
        return {'position': C.add(pose['position'], C.mv(C.quat(pose['orientation_wxyz']), offset)), 'source_body': 'KG1'}
    def matrices(observed):
        return {p['name']: C.tf(p['position'], C.quat(p['orientation_wxyz'])) for p in observed['body_poses']}
    def row_for(stage_name, local_step, observed, target, proof=None, remaining=None):
        return {'step': report['completed_steps'], 'time_s': report['completed_steps']/120,
                'stage_time_s': local_step/120, 'phase': stage_name, 'targets': target['targets'],
                'reference_velocity': target['reference_velocity'], 'velocity_targets': target['velocity_targets'],
                'q': observed['q'], 'qd': observed['qd'], 'body_poses': observed['body_poses'],
                'clock': observed['clock'], 'actual_tcp': tcp(observed), 'ff': proof, 'effort_remaining': remaining}
    with (out/'motion.ndjson').open('x', encoding='utf-8', newline='\n') as journal:
        initial = row_for('hold', 0, current, C.target_at(program, 'hold', 0))
        journal.write(json.dumps(initial, allow_nan=False)+'\n'); journal.flush()
        # An actual frame at engine time zero is retained even when legacy caps fail.
        report['frames'].append(camera.capture(0, initial, state))
        for stage_name in PHASES[1:]:
            duration = program['stages'][stage_name]['duration_s']
            budget.enter(stage_name)
            begin, start_step = time.monotonic(), report['completed_steps']
            checkpoints = []
            for local_step in range(1, round(duration*120)+1):
                budget.check()
                target = C.target_at(program, stage_name, local_step/120)
                verify_coupled_targets(model, target, C.near)
                query_before = clock()
                with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                    raw = array(robot.get_dof_gravity_compensation_forces())
                need(raw.ndim == 2 and raw.shape[0] == 1, 'One actual generalized-force row')
                need(query_before == clock() == current['clock'], 'Gravity query native clock stable')
                ff, columns = C.map_gravity(names, model['movable'], raw[0].tolist())
                expected = C.gravity_reference(model, current['body_poses'], inertias)
                difference = max(abs(ff[n]-expected[n]) for n in names)
                proof = {'native': ff, 'expected': expected, 'max_difference': difference,
                         'full': raw[0].tolist(), 'shape': list(raw.shape), 'columns': columns,
                         'source_clock': query_before, 'source_state_index': report['completed_steps']}
                need(difference <= 1e-3, 'Native FF agrees with independent actual world-COM virtual work')
                remaining, overloaded = C.remaining_caps(model, ff, caps)
                if overloaded:
                    report['stopped_command'] = {'stage': stage_name, 'target': target, 'ff': proof, 'remaining_caps': remaining, 'joints': overloaded}
                    raise GateFailure('FF_EXCEEDS_APPROVED_CAP:'+','.join(overloaded))
                with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                    robot.set_dof_max_efforts([[remaining[n] for n in names]])
                    robot.set_dof_position_targets([[C.binary32(target['targets'][n]) for n in names]])
                    robot.set_dof_velocity_targets([[target['velocity_targets'][n] for n in names]])
                    robot.set_dof_efforts([[ff[n] for n in names]])
                    # Actual command readbacks remain within the original velocity/cap/gain policy.
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_max_efforts())[0]), remaining, 2e-6)
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_position_targets())[0]),
                           {n: C.binary32(target['targets'][n]) for n in names}, 1e-7)
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_velocity_targets())[0]), target['velocity_targets'], 1e-7)
                sim.step(render=False)
                report['completed_steps'] += 1
                current = state()
                validate_clocks(current['clock'], baseline, report['completed_steps'], program['dt_s'])
                floor_z, bounds = C.floor_and_bounds(model, matrices(current), support)
                need(floor_z >= -.0001, 'Actual moving body clears desk')
                base = next(p for p in current['body_poses'] if p['name'] == 'Base')
                C.near(C.tf(base['position'], C.quat(base['orientation_wxyz'])), C.ident(), 2e-5)
                for name in names:
                    j = model['joints'][name]
                    need(j['lower']-1e-5 <= current['q'][name] <= j['upper']+1e-5, 'Actual source position limit:'+name)
                    need(abs(current['qd'][name]) <= j['velocity']+1e-4, 'Actual source speed limit:'+name)
                row = row_for(stage_name, local_step, current, target, proof, remaining)
                row['minimum_moving_link_z_m'] = floor_z
                journal.write(json.dumps(row, allow_nan=False, separators=(',', ':'))+'\n'); journal.flush()
                if report['completed_steps'] % program['capture_stride'] == 0:
                    report['frames'].append(camera.capture(len(report['frames']), row, state))
                    ctx.write(out/'report.partial.json', report)
                checkpoint = local_step == round(duration*120) or stage_name == 'large' and local_step == round(program['settling']['large_check_s']*120)
                if checkpoint:
                    result = C.phase_check(model, stage_name, current['q'], current['qd'], target, program, floor_z)
                    checkpoints.append(dict(result, stage_time_s=local_step/120, step=report['completed_steps']))
                    if not result['passed']:
                        report['failed_checkpoint'] = checkpoints[-1]
                        raise GateFailure('SETTLING:'+','.join(result['reasons']))
            mark(report, stage_name, 'PASS', elapsed_s=time.monotonic()-begin, completed_steps=report['completed_steps']-start_step, checkpoints=checkpoints)
            ctx.write(out/'report.partial.json', report)
    report['render'] = camera.finish(len(report['frames']), purpose='motion')
    boundary.finish(report['completed_steps'])
    report['initialization_boundary'] = boundary.audit


def collect(ctx, app):
    """Called once by the pinned lifecycle; all SDK ownership stays with that lifecycle."""
    report = ledger(ctx)
    budget = ctx.native_budget if hasattr(ctx, 'native_budget') else arm_watchdog(ctx)
    error = None
    try:
        budget.check()
        ctx.write(ctx.run/'output/report.partial.json', report)
        _native(ctx, app, report, budget)
    except GateFailure as exc:
        mark(report, budget.phase, 'FAIL', str(exc), completed_steps=report['completed_steps'])
        report['gate_failure'] = str(exc)
        if hasattr(ctx, 'native_camera') and report['frames']:
            report['render'] = ctx.native_camera.finish(len(report['frames']), purpose='render_smoke')
        if hasattr(ctx, 'init_boundary'):
            ctx.init_boundary.finish(report['completed_steps'])
    except BaseException as exc:
        error = exc
        mark(report, budget.phase, 'FAIL', type(exc).__name__+': '+str(exc), completed_steps=report['completed_steps'])
        report['exception'] = traceback.format_exc()
    finally:
        if hasattr(ctx, 'init_boundary'):
            try:
                errors = ctx.init_boundary.close()
                report['init_cleanup_errors'] = errors
                if errors:
                    mark(report, budget.phase, 'FAIL', 'INIT_CLEANUP_FAILED:'+str(errors))
                    if error is None:
                        error = RuntimeError('INIT_CLEANUP_FAILED')
            except BaseException as exc:
                mark(report, budget.phase, 'FAIL', 'INIT_CLEANUP_EXCEPTION:'+str(exc))
                if error is None:
                    error = exc
        report['elapsed_native_s'] = time.monotonic()-ctx.started_monotonic
        report['native_deadline_monotonic'] = budget.end
        ctx.write(ctx.run/'output/report.json', report)
    if error is not None:
        raise error
    return report
