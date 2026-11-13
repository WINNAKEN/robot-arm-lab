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
    """Establish strict emptiness and preserve failed observations before raising."""
    import hashlib
    import math

    packet = {'schema_version': 1, 'verified': False, 'before': None,
              'after_new': None, 'after': None, 'cleared_layers': []}
    target = ctx.run / 'output/fresh-stage.json'

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def persist():
        ctx.write(target, packet)

    def stamp(name):
        value = float(clock())
        packet[name] = value if math.isfinite(value) else {'invalid': repr(value)}
        return value

    def census(stage):
        if stage is None:
            return None
        default = stage.GetDefaultPrim()
        return {
            'layer': str(stage.GetRootLayer().identifier),
            'session_layer': str(stage.GetSessionLayer().identifier),
            'layer_stack': [str(layer.identifier) for layer in stage.GetLayerStack()],
            'used_layers': [str(layer.identifier) for layer in stage.GetUsedLayers()],
            'default_prim': str(default.GetPath()) if default else None,
            'prims': [{'path': str(prim.GetPath()), 'type': str(prim.GetTypeName()),
                       'applied_schemas': list(prim.GetAppliedSchemas())}
                      for prim in stage.TraverseAll()],
        }

    def signature(layer):
        return hashlib.sha256(layer.ExportToString().encode('utf8')).hexdigest()

    try:
        persist()  # If observation cannot be saved, do not create or clear a stage.
        old = context.get_stage()
        old_roots = [] if old is None else [old.GetRootLayer(), old.GetSessionLayer()]
        old_layers = [] if old is None else list(old.GetLayerStack()) + list(old.GetUsedLayers())
        old_ids = {str(layer.identifier) for layer in old_layers}
        packet['before'] = census(old)
        before_time = stamp('engine_before_s')
        persist()
        require(math.isfinite(before_time) and before_time == 0., 'Zero engine clock before fresh stage')

        # Context-owned stages expose weak layer handles. FindOrOpen's factory
        # acquires strong ownership; merely keeping GetRootLayer()/Find() does not.
        if old_roots:
            from pxr import Sdf
            pinned_roots = []
            for layer in old_roots:
                identifier = str(layer.identifier)
                require(layer.anonymous is True and identifier.startswith('anon:'),
                        'Pin only existing anonymous old layers')
                pinned = Sdf.Layer.FindOrOpen(identifier)
                require(pinned is not None and bool(pinned) and pinned == layer and
                        str(pinned.identifier) == identifier and pinned.anonymous is True,
                        'Strong old layer pin must preserve exact layer identity')
                pinned_roots.append(pinned)
            old_roots = pinned_roots
        packet['old_layers_before_reset'] = {str(layer.identifier): signature(layer) for layer in old_roots}
        packet['old_layer_ownership'] = 'FindOrOpen_STRONG_BEFORE_NEW_STAGE'
        persist()

        result = context.new_stage()
        new = context.get_stage()
        packet['after_new'] = census(new)
        new_time = stamp('engine_after_new_s')
        persist()  # The original failure lost precisely this census.
        require(result is not False and new is not None, 'Actual fresh stage created')
        root, session = new.GetRootLayer(), new.GetSessionLayer()
        layers = [root, session]
        new_ids = {str(layer.identifier) for layer in layers}
        require(len(new_ids) == 2 and all(layer.anonymous is True for layer in layers),
                'Two distinct anonymous new layers required')
        require(not (new_ids & old_ids), 'New layers must not share any old layer')
        require(old is None or str(root.identifier) != packet['before']['layer'],
                'Distinct actual fresh root identity')
        require(math.isfinite(new_time) and new_time == before_time == 0.,
                'Zero engine clock after stage creation')
        packet['owned_reset_layers'] = sorted(new_ids)
        persist()

        for index, layer in enumerate(layers):
            current = context.get_stage()
            require(current is not None and current.GetRootLayer() == root and
                    current.GetSessionLayer() == session,
                    'Owned layers must remain current before Clear')
            value = stamp('engine_before_clear_%d_s' % index)
            require(math.isfinite(value) and value == 0., 'Zero engine clock before Clear')
            require(layer.anonymous is True and str(layer.identifier) in new_ids and
                    str(layer.identifier) not in old_ids, 'Clear only a fresh owned anonymous layer')
            layer.Clear()
            packet['cleared_layers'].append(str(layer.identifier))

        current = context.get_stage()
        packet['after'] = census(current)
        after_time = stamp('engine_after_s')
        packet['old_layers_after_reset'] = {str(layer.identifier): signature(layer) for layer in old_roots}
        persist()
        require(current is not None and current.GetRootLayer() == root and
                current.GetSessionLayer() == session, 'Owned layers remain current after Clear')
        require(all(layer.empty is True for layer in layers), 'Both owned layers must actually be empty')
        require(set(packet['after']['layer_stack']) == new_ids and
                not (set(packet['after']['used_layers']) & old_ids), 'No inherited old layer after reset')
        require(packet['after']['prims'] == [] and packet['after']['default_prim'] is None,
                'Fresh stage has no inherited roots or objects')
        require(math.isfinite(after_time) and after_time == new_time == before_time == 0.,
                'Fresh stage preserves zero engine clock')
        require(packet['old_layers_before_reset'] == packet['old_layers_after_reset'],
                'Old root and session content must remain unchanged')
        packet['verified'] = True
        persist()
        return current
    except Exception as primary:
        packet['verified'] = False
        packet['error'] = type(primary).__name__ + ': ' + str(primary)
        try:
            packet['failure_census'] = census(context.get_stage())
        except Exception as observation_error:
            packet['failure_census_error'] = type(observation_error).__name__ + ': ' + str(observation_error)
        try:
            persist()
        except Exception as write_error:
            primary.add_note('Failed to persist stage evidence: ' + type(write_error).__name__ + ': ' + str(write_error))
        raise


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


def _diag_owned(value, budget=None, depth=0):
    budget = [16384] if budget is None else budget
    budget[0] -= 1
    if budget[0] < 0 or depth > 12: raise ValueError('Diagnostic bounded copy overflow')
    if value is None or type(value) in (str, bool, int):
        return value[:2000] if type(value) is str else value
    if type(value) is float:
        return value if math.isfinite(value) else {'nonfinite': repr(value)}
    if isinstance(value, (list, tuple)):
        return [_diag_owned(v, budget, depth+1) for v in value]
    if isinstance(value, dict):
        return {str(k)[:200]: _diag_owned(v, budget, depth+1) for k,v in value.items()}
    raise ValueError('Diagnostic nonprimitive copy: '+type(value).__name__)


def _diag_secondary(ctx, label, exc):
    rows = getattr(ctx, '_diag_secondary', None)
    if rows is None: rows = []; ctx._diag_secondary = rows
    try: message=str(exc)[:1000]
    except BaseException: message='UNKNOWN_EXCEPTION_MESSAGE'
    if len(rows) < 12: rows.append({'where': label, 'type': type(exc).__name__, 'message': message})


def _diag_final_copy(ctx, label, value):
    try: return _diag_owned(value)
    except BaseException as exc:
        _diag_secondary(ctx,label,exc)
        return {'status':'UNKNOWN_DIAGNOSTIC_COPY_ERROR','type':type(exc).__name__}


def _fault_begin(ctx, phase, step, target, previous, proof, remaining):
    ctx._fault_pending = {'status':'UNVALIDATED', 'attempted_phase':phase, 'attempted_step':step,
        'current_state':None, 'current_state_status':'PENDING_READ', 'observed_state_index':None, 'accepted_journal':False}
    try:
        probe=getattr(ctx,'_contact_probe',None)
        if probe is not None:
            previous_contact=_diag_owned(probe.last)
            probe.last={'status':'UNKNOWN_NOT_OBSERVED_FOR_ATTEMPT','owner_step':step,
                'native_timestamp':'NOT_PROVIDED_BY_HEADER','previous_contact':previous_contact}
        ctx._fault_pending.update({'previous_state':_diag_owned(previous), 'target':_diag_owned(target),
            'FF':_diag_owned(proof), 'remaining_cap':_diag_owned(remaining)})
    except BaseException as exc: _diag_secondary(ctx, 'pending_context_copy', exc)


def _fault_raw(ctx, clock, names, q, qd):
    pending = getattr(ctx, '_fault_pending', None)
    if pending is None: return
    try:
        pending['raw_state_read'] = _diag_owned({'owner_read_clock':clock, 'names':list(names), 'q':list(q), 'qd':list(qd)})
    except BaseException as exc: _diag_secondary(ctx, 'raw_state_copy', exc)


def _fault_raw_poses(ctx, poses, after):
    pending = getattr(ctx, '_fault_pending', None)
    if pending is None: return
    try: pending['raw_pose_read'] = _diag_owned({'body_poses':poses,'owner_clock_after':after})
    except BaseException as exc: _diag_secondary(ctx, 'raw_pose_copy', exc)


def _fault_observe(ctx, current):
    pending = getattr(ctx, '_fault_pending', None)
    if pending is None: return
    try:
        observed = _diag_owned(current)
        index = observed['clock']['lab_step']
        pending['current_state'] = observed
        pending['observed_state_index'] = index
        pending['current_state_status'] = 'AVAILABLE_UNVALIDATED' if index == pending['attempted_step'] else 'STALE_NOT_CURRENT'
    except BaseException as exc:
        pending['current_state_status'] = 'UNAVAILABLE_COPY_FAILED'
        _diag_secondary(ctx, 'poststep_state_copy', exc)


def _save_first_fault(ctx, report, primary):
    if hasattr(ctx, '_first_fault'): return
    pending = getattr(ctx, '_fault_pending', None)
    if pending is None:
        pending = {'attempted_phase':'setup', 'attempted_step':report.get('completed_steps'),
            'current_state':None, 'current_state_status':'NOT_MEASURED_SETUP', 'observed_state_index':None,
            'accepted_journal':False}
    try:
        packet = _diag_final_copy(ctx,'first_fault_pending_copy',pending)
        if packet.get('status')=='UNKNOWN_DIAGNOSTIC_COPY_ERROR':
            packet={'status':'UNVALIDATED','attempted_phase':pending.get('attempted_phase','UNKNOWN'),
                'attempted_step':pending.get('attempted_step'), 'current_state':None,
                'current_state_status':'UNAVAILABLE_DIAGNOSTIC_COPY_ERROR','observed_state_index':None,'accepted_journal':False}
        if packet.get('current_state') is None and packet.get('current_state_status')=='PENDING_READ':
            packet['current_state_status']='UNAVAILABLE_STATE_READ_OR_STEP_FAILED'
        packet['current_measurement_available']=packet.get('current_state') is not None and packet.get('observed_state_index')==packet.get('attempted_step')
        contact=_diag_final_copy(ctx,'first_fault_contact_copy',getattr(getattr(ctx,'_contact_probe',None),'last',{'status':'UNKNOWN_NOT_OBSERVED'}))
        if contact.get('status')=='CURRENT_STEP_REPORT_COPIED':
            current_clock=(packet.get('current_state') or {}).get('clock')
            if contact.get('owner_step')!=packet.get('attempted_step') or contact.get('owner_clock_before')!=current_clock or contact.get('owner_clock_after')!=current_clock:
                contact={'status':'UNKNOWN_STALE_CONTACT_NOT_CURRENT','owner_step':packet.get('attempted_step'),'previous_contact':contact}
        packet.update({'schema_version':1, 'classification':'UNVALIDATED_FIRST_FAULT_NOT_ACCEPTED_TRAJECTORY',
            'run_id':ctx.job['run_id'], 'job_sha256':ctx.job_hash,
            'primary':{'type':type(primary).__name__, 'message':str(primary)[:2000]},
            'contact':contact,
            'velocity_limits':_diag_final_copy(ctx,'first_fault_velocity_copy',getattr(ctx, '_velocity_audit', {})),
            'secondary':_diag_final_copy(ctx,'first_fault_secondary_copy',getattr(ctx, '_diag_secondary', []))})
        ctx._first_fault = packet
        report['first_fault'] = {'path':'first-fault.json', 'classification':packet['classification'],
            'attempted_step':packet['attempted_step'], 'observed_state_index':packet['observed_state_index'],
            'current_state_status':packet['current_state_status'], 'saved':False}
        try:
            ctx.write(ctx.run/'output/first-fault.json', packet)
            report['first_fault']['saved'] = True
        except BaseException as exc: _diag_secondary(ctx, 'first_fault_write', exc)
    except BaseException as exc: _diag_secondary(ctx, 'first_fault_build', exc)


def _velocity_limits(ctx, robot, names, model, C, array, backend, clock, state=None, repair=False):
    phase = 'tensor_after_reset' if repair else 'usd_before_reset'
    if not hasattr(ctx, '_velocity_audit'): ctx._velocity_audit = {}
    record = {'status':'OBSERVING', 'names':list(names), 'source_SI':{n:model['joints'][n]['velocity'] for n in names},
        'set_same_source_values':False, 'phase':phase}
    ctx._velocity_audit[phase] = record
    need(len(names)==9 and len(set(names))==9 and set(names)==set(model['movable']), 'Velocity binding exact nine names')
    before_clock = _diag_owned(clock())
    need(before_clock == {'engine_time_s':0.0,'lab_step':0}, 'Velocity binding zero native clock')
    before_state = _diag_owned(state()) if state is not None else None
    if before_state is not None:
        need(all(v==0. for k in ('q','qd') for v in before_state[k].values()), 'Velocity binding zero q and qd')
    expected = {n:C.binary32(model['joints'][n]['velocity']) for n in names}
    def read():
        need(list(robot.dof_names)==list(names), 'Velocity binding stable DOF order')
        raw = array(robot.get_dof_max_velocities())
        need(raw.ndim==2 and tuple(raw.shape)==(1,9), 'Velocity binding exact (1,9) shape')
        return C.named_columns(names, model['movable'], raw[0])
    with backend.use_backend('tensor' if repair else 'usd', raise_on_unsupported=True, raise_on_fallback=True):
        actual = read();record['before_SI'] = actual
        if actual != expected:
            need(repair, 'USD source velocity readback differs')
            robot.set_dof_max_velocities([[expected[n] for n in names]])
            record['set_same_source_values'] = True
        final = read();record['after_SI'] = final
        need(final == expected, 'Actual tensor/source velocity readback differs')
    after_state = _diag_owned(state()) if state is not None else None
    after_clock = _diag_owned(clock())
    record.update({'owner_clock_before':before_clock, 'owner_clock_after':after_clock,
        'state_before':before_state, 'state_after':after_state})
    need(before_clock == after_clock and before_state == after_state, 'Velocity binding changes no clock/q/qd/pose')
    record['status'] = 'VERIFIED_SAME_ORIGINAL_SI_LIMITS'
    return record


def _diag_attribute(prim, name):
    try:
        attr = prim.GetAttribute(name)
        if not attr: return {'status':'UNKNOWN_NOT_AVAILABLE', 'authored':False, 'runtime_observed':False}
        return {'status':'USD_ATTRIBUTE_READ', 'authored':bool(attr.HasAuthoredValueOpinion()),
            'type':str(attr.GetTypeName()), 'value':_diag_owned(attr.Get()), 'runtime_observed':False}
    except BaseException as exc: return {'status':'UNKNOWN_READ_ERROR', 'error':type(exc).__name__+': '+str(exc)[:500], 'runtime_observed':False}


def _contact_settings(stage, paths):
    attrs = ('physxCollision:contactOffset','physxCollision:restOffset','physxRigidBody:maxDepenetrationVelocity',
        'physxArticulation:solverPositionIterationCount','physxArticulation:solverVelocityIterationCount',
        'physxScene:solverType','physxScene:minVelocityIterationCount','physxScene:maxVelocityIterationCount',
        'physxScene:solveArticulationContactLast')
    return {p:{a:_diag_attribute(stage.GetPrimAtPath(p),a) for a in attrs} for p in list(dict.fromkeys(paths))[:32]}


class _ContactProbe:
    def __init__(self, ctx, interface, stage, expected_stage, clock, decode, enabled, setup):
        self.ctx, self.interface, self.stage, self.expected_stage = ctx, interface, stage, expected_stage
        self.clock, self.decode, self.enabled, self.setup = clock, decode, enabled, setup
        self.closed = False
        self.state_reader = None
        self.stage_reader = None
        self.last = {'status':'UNKNOWN_NOT_OBSERVED', 'setup':setup}
    def sample(self, step):
        self.last = {'status':'UNKNOWN_NOT_OBSERVED', 'owner_step':step,
            'native_timestamp':'NOT_PROVIDED_BY_HEADER', 'setup':self.setup}
        try:
            need(not self.closed and self.enabled, 'Contact report unavailable or closed')
            before = _diag_owned(self.clock())
            pending=getattr(self.ctx,'_fault_pending',{})
            observed=pending.get('current_state')
            before_state={k:observed[k] for k in ('q','qd')} if observed is not None else None
            need(before['lab_step']==step, 'Contact observation current owner step')
            need(observed is not None and observed.get('clock')==before,'Contact owner clock matches poststep state')
            self.last['stage_provenance']={'expected_stage_id':self.expected_stage,'attached_stage_id':None,'header_stage_ids':[],'mode':'UNKNOWN'}
            need(callable(self.stage_reader),'Current contact stage proof callback required')
            stage_before=_diag_owned(self.stage_reader(),budget=[256])
            self.last['stage_provenance']['current']=stage_before
            attached = int(self.interface.get_attached_stage())
            self.last['stage_provenance']['attached_stage_id']=attached
            mode=_contact_stage_mode(stage_before,attached,self.expected_stage)
            self.last['stage_provenance']['mode']=mode
            raw = self.interface.get_contact_report()
            need(isinstance(raw,tuple) and len(raw) in (2,3), 'Contact report tuple2 or tuple3')
            headers, data = raw[:2]
            need(len(headers)<=64 and len(data)<=256 and (len(raw)==2 or len(raw[2])<=256), 'Contact report bounded vector overflow')
            self.last['stage_provenance']['header_stage_ids']=[int(h.stage_id) for h in headers]
            expanded=0
            for header in headers:
                offset,count=int(header.contact_data_offset),int(header.num_contact_data)
                need(offset>=0 and count>=0 and offset+count<=len(data), 'Contact offset/count range')
                expanded+=count
                need(expanded<=256, 'Contact cumulative expanded contacts overflow')
            owned=[];paths=[]
            for h in headers:
                need(int(h.stage_id)==self.expected_stage, 'Contact header current registered stage identity')
                offset,count=int(h.contact_data_offset),int(h.num_contact_data)
                need(offset>=0 and count>=0 and offset+count<=len(data), 'Contact offset/count range')
                row={'event':str(h.type), 'stage_id':int(h.stage_id), 'offset':offset, 'count':count}
                for key in ('actor0','actor1','collider0','collider1'):
                    value=getattr(h,key);decoded=str(self.decode(value))
                    need(len(decoded)<=2000 and decoded.startswith('/World/'), 'Contact decoded owned world path')
                    need(bool(self.stage.GetPrimAtPath(decoded)),'Contact actor/collider exists on owned current stage')
                    row[key]=decoded;paths.append(decoded)
                row['contacts']=[]
                for index in range(offset,offset+count):
                    p=data[index]
                    item={'position':[float(x) for x in p.position], 'normal':[float(x) for x in p.normal],
                        'impulse':[float(x) for x in p.impulse], 'separation':float(p.separation)}
                    need(all(len(item[k])==3 for k in ('position','normal','impulse')) and
                        all(math.isfinite(v) for k in ('position','normal','impulse') for v in item[k]) and
                        math.isfinite(item['separation']), 'Finite contact primitive vectors')
                    row['contacts'].append(item)
                owned.append(row)
            stage_after=_diag_owned(self.stage_reader(),budget=[256])
            self.last['stage_provenance']['after']=stage_after
            need(stage_before==stage_after,'Contact getter preserves current owned stage')
            after=_diag_owned(self.clock())
            after_state=_diag_owned(self.state_reader()) if callable(self.state_reader) else None
            if before!=after or before_state is not None and after_state is not None and before_state!=after_state:
                self.last['observer_changed_state']=True
                raise ValueError('Contact getter changes no native clock/q/qd')
            result={'status':'CURRENT_STEP_REPORT_COPIED', 'owner_step':step, 'owner_clock_before':before,
                'owner_clock_after':after, 'native_timestamp':'NOT_PROVIDED_BY_HEADER', 'attached_stage_id':attached,
                'tuple_arity':len(raw), 'headers':owned, 'reported_pairs':len(owned),
                'friction_anchors_count':len(raw[2]) if len(raw)==3 else None,
                'zero_pairs_mean':'NO_PAIRS_REPORTED_NOT_PROOF_OF_NO_PHYSICAL_CONTACT',
                'stage_provenance':self.last['stage_provenance'],
                'settings':_contact_settings(self.stage,paths+['/World/Robot','/World/physicsScene','/World/Floor'])}
            self.last=_diag_owned(result,budget=[8192])
        except BaseException as exc:
            self.last.update({'status':'UNKNOWN_OBSERVATION_ERROR', 'error':type(exc).__name__+': '+str(exc)[:1000]})
            _diag_secondary(self.ctx,'contact_sample',exc)
        finally:
            if 'before' in locals():
                try:
                    final_clock=_diag_owned(self.clock())
                    final_state=_diag_owned(self.state_reader()) if callable(self.state_reader) else None
                    if before!=final_clock or before_state is not None and final_state is not None and before_state!=final_state:
                        self.last.update({'status':'UNKNOWN_OBSERVER_STATE_CHANGED','observer_changed_state':True})
                except BaseException as secondary:
                    self.last['state_preservation_unverified']=True
                    _diag_secondary(self.ctx,'contact_state_preservation',secondary)
        return self.last
    def close(self):
        self.closed=True
        return {'mode':'DIRECT_GETTER_NO_SUBSCRIPTION', 'closed':True, 'physics_operations':0}


def _contact_setup(ctx, stage, body_paths, schema, interface, expected_stage, clock, decode):
    setup={'mode':'DIRECT_GETTER_NO_SUBSCRIPTION','threshold_requested':0.0,'bodies':[], 'enabled':False}
    enabled=False
    try:
        need(callable(getattr(interface,'get_contact_report',None)) and callable(getattr(interface,'get_attached_stage',None)), 'Direct contact API unsupported')
        for path in body_paths:
            api=schema.PhysxContactReportAPI.Apply(stage.GetPrimAtPath(path))
            maker=getattr(api,'CreateThresholdAttr',None)
            method='CreateThresholdAttr'
            if not callable(maker): maker=getattr(api,'CreatePhysxContactReportThresholdAttr',None);method='CreatePhysxContactReportThresholdAttr'
            need(callable(maker), 'Contact report threshold API unsupported')
            attr=maker()
            need(str(attr.GetName())=='physxContactReport:threshold' and str(attr.GetTypeName())=='float','Exact report-only threshold attribute')
            need(attr.Set(0.0) is True and float(attr.Get())==0., 'Report-only threshold zero readback')
            setup['bodies'].append({'path':path,'method':method,'threshold':0.0,'report_only':True})
        enabled=True;setup['enabled']=True
    except BaseException as exc:
        setup['status']='UNKNOWN_SETUP_ERROR';setup['error']=type(exc).__name__+': '+str(exc)[:1000]
        _diag_secondary(ctx,'contact_setup',exc)
    return _ContactProbe(ctx,interface,stage,expected_stage,clock,decode,enabled,setup)


def _decode_contact_path(tools, value):
    if type(value) is int:
        return tools.intToSdfPath(value)
    if isinstance(value,(tuple,list)) and len(value)==2 and all(type(x) is int for x in value):
        try: return tools.decodeSdfPath(value[0],value[1])
        except TypeError: return tools.decodeSdfPath(value)
    raise ValueError('UNKNOWN contact actor ID encoding')


def _constraint_order_cfg(PhysxCfg):
    baseline,candidate=PhysxCfg(),PhysxCfg(solve_articulation_contact_last=True)
    before,after=baseline.to_dict(),candidate.to_dict()
    need(type(before) is dict and type(after) is dict and set(before)==set(after),'Same official PhysxCfg fields')
    changed=[key for key in before if before[key]!=after[key]]
    need(changed==['solve_articulation_contact_last'] and before[changed[0]] is False and after[changed[0]] is True,'Only official constraint order bool changes')
    return candidate,{'changed_fields':changed,'default':False,'requested':True,'other_fields_equal':True,'field_count':len(before)}


def _constraint_order_readback(sim,stage,clock,state_reader=None):
    before=_diag_owned(clock())
    state_before=_diag_owned(state_reader()) if callable(state_reader) else None
    attr=stage.GetPrimAtPath('/World/physicsScene').GetAttribute('physxScene:solveArticulationContactLast')
    proof={'clock_before':before,'authored':bool(attr and attr.HasAuthoredValueOpinion()),
        'attribute_type':str(attr.GetTypeName()) if attr else 'UNKNOWN',
        'value':attr.Get() if attr else None,'resolved_config_value':sim.cfg.physics.solve_articulation_contact_last,
        'root_layer':str(stage.GetRootLayer().identifier),'session_layer':str(stage.GetSessionLayer().identifier)}
    after=_diag_owned(clock());state_after=_diag_owned(state_reader()) if callable(state_reader) else None
    proof.update(clock_after=after,state_before=state_before,state_after=state_after)
    need(before==after and before['engine_time_s']==0. and before['lab_step']==0 and state_before==state_after,'Constraint readback preserves zero clock/q/qd')
    need(sim.stage==stage and proof['authored'] and proof['attribute_type']=='bool' and proof['value'] is True and proof['resolved_config_value'] is True,'Current official constraint-order scene True')
    return proof


def _contact_stage_state(sim,stage,context,cache,lab_current,manager):
    # All observed IDs are copied before the consumer classifies their meaning.
    result={'status':'UNKNOWN_STAGE_PROOF','cache_id':None,'context_id':None,'device':str(sim.cfg.device),
        'backend_device':None,'root_layer':str(stage.GetRootLayer().identifier),'session_layer':str(stage.GetSessionLayer().identifier)}
    try:
        cache_id=cache.GetId(stage)
        result['cache_id']=int(cache_id.ToLongInt())
        result['context_id']=int(context.get_stage_id())
        result['backend_device']=str(manager.get_device())
        lab,kit=lab_current(),context.get_stage()
        result.update(sim_stage_same=sim.stage==stage,lab_stage_same=lab==stage,kit_stage_same=kit==stage,
            manager_owner_same=manager._sim is sim,cache_dereference_same=cache.Find(cache_id)==stage,
            context_registration_same=result['context_id']==result['cache_id'],
            lab_layers_same=lab is not None and lab.GetRootLayer()==stage.GetRootLayer() and lab.GetSessionLayer()==stage.GetSessionLayer(),
            kit_layers_same=kit is not None and kit.GetRootLayer()==stage.GetRootLayer() and kit.GetSessionLayer()==stage.GetSessionLayer())
        result['status']='OWNED_IDS_OBSERVED_NOT_YET_ADMITTED'
    except BaseException as exc:
        result['error']=type(exc).__name__+': '+str(exc)[:1000]
    return _diag_owned(result,budget=[256])


def _contact_stage_mode(proof,attached,expected):
    need(type(proof) is dict and proof.get('status')=='OWNED_IDS_OBSERVED_NOT_YET_ADMITTED','Complete current contact stage proof')
    need(type(expected) is int and expected>0 and proof.get('cache_id')==expected and proof.get('context_id')==expected,'Current registered contact stage IDs')
    need(all(proof.get(k) is True for k in ('sim_stage_same','lab_stage_same','kit_stage_same','manager_owner_same','cache_dereference_same','context_registration_same','lab_layers_same','kit_layers_same')),'Owned Lab/Kit/cache current stage identity')
    need(all(type(proof.get(k)) is str and 0<len(proof[k])<=2000 for k in ('root_layer','session_layer')),'Owned current stage layers')
    cpu=proof.get('device')=='cpu' and proof.get('backend_device')=='cpu'
    gpu=str(proof.get('device','')).startswith('cuda') and str(proof.get('backend_device','')).startswith('cuda')
    if attached==0:
        need(cpu,'Only proven CPU Kit implicit attachment has zero explicit interface ID')
        return 'CPU_KIT_IMPLICIT_CURRENT_STAGE'
    need(attached==expected and (cpu or gpu),'Exact explicit current contact stage identity')
    return 'GPU_EXPLICIT_CURRENT_STAGE' if gpu else 'CPU_EXPLICIT_CURRENT_STAGE'


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
    from isaaclab_physx.physics import PhysxCfg
    from isaaclab.sim.utils.stage import get_current_stage
    from pxr import Gf, UsdGeom, UsdPhysics, PhysxSchema, PhysicsSchemaTools, UsdUtils
    C, model, sdk, out = ctx.contract, ctx.model, ctx.scene_modules['sdk'], ctx.run/'output'
    program = ctx.cfg['program']
    imported = _import(ctx, app, budget)
    fresh_stage(ctx, omni.usd.get_context(), SimulationManager.get_simulation_time)
    budget.check()
    boundary = ctx.scene_modules['init_boundary'].Boundary(ctx, PhysxManager, omni.physx.get_physx_interface(),
        carb.settings.get_settings(), SimulationManager.get_simulation_time)
    ctx.init_boundary = boundary
    order_cfg,report['constraint_order'] = _constraint_order_cfg(PhysxCfg)
    sim = SimulationContext(SimulationCfg(physics=order_cfg,dt=1/120, device='cpu', gravity=(0., 0., -9.81),
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
    velocity_clock = lambda: {'engine_time_s':float(SimulationManager.get_simulation_time()), 'lab_step':int(sim.get_physics_step_count())}
    with backend.use_backend('usd', raise_on_unsupported=True, raise_on_fallback=True):
        robot.set_dof_drive_types('acceleration')
        robot.set_dof_gains([64.]*9, [16.]*9)
        robot.set_dof_max_efforts([caps[n] for n in names])
        robot.set_dof_max_velocities([model['joints'][n]['velocity'] for n in names])
        robot.set_enabled_self_collisions(False)
        robot.set_link_enabled_gravities(True)
    report['velocity_limits'] = {'usd_before_reset': _velocity_limits(ctx,robot,names,model,C,lambda v:v.numpy().copy(),backend,velocity_clock)}
    need(attr.Get() is False, 'Actual self-collision OFF remains')
    support, workspace = C.parse(ctx.data['ref/support.json']), C.parse(ctx.data['ref/workspace.json'])
    camera = ctx.scene_modules['capture'].NativeCapture(ctx, stage, program, workspace)
    ctx.native_camera = camera
    stage.Flatten().Export(str(out/'scene.usda'))
    try:
        interface = omni.physx.get_physx_simulation_interface()
        stage_id = int(UsdUtils.StageCache.Get().GetId(stage).ToLongInt())
        ctx._contact_probe = _contact_setup(ctx,stage,list(paths.values()),PhysxSchema,interface,stage_id,velocity_clock,
            lambda value:_decode_contact_path(PhysicsSchemaTools,value))
        ctx._contact_probe.stage_reader = lambda:_contact_stage_state(sim,stage,omni.usd.get_context(),UsdUtils.StageCache.Get(),get_current_stage,PhysxManager)
    except BaseException as diagnostic:
        _diag_secondary(ctx,'contact_interface_setup',diagnostic)
        ctx._contact_probe = _ContactProbe(ctx,None,stage,None,velocity_clock,None,False,{'status':'UNKNOWN_INTERFACE_SETUP'})
    report['contact_reporting'] = _diag_owned(ctx._contact_probe.setup)
    report['constraint_order']['before_reset'] = _constraint_order_readback(sim,stage,velocity_clock)
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
            raw_q = array(robot.get_dof_positions())[0].tolist()
            raw_qd = array(robot.get_dof_velocities())[0].tolist()
            _fault_raw(ctx,before,names,raw_q,raw_qd)
            q = C.named_columns(names, model['movable'], raw_q)
            qd = C.named_columns(names, model['movable'], raw_qd)
            poses = []
            for name, prim in links:
                pos, rotation = prim.get_world_poses()
                poses.append({'name': name, 'position': array(pos)[0].tolist(), 'orientation_wxyz': array(rotation)[0].tolist()})
        after = clock()
        _fault_raw_poses(ctx,poses,after)
        need(before == after, 'Stable native read clock')
        for pose in poses:
            need(all(math.isfinite(x) for x in pose['position']+pose['orientation_wxyz']), 'Finite actual body pose')
            C.quat(pose['orientation_wxyz'])
        return {'clock': after, 'clock_before': before, 'clock_after': after, 'q': q, 'qd': qd, 'body_poses': poses}
    def contact_state_read():
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            return {'q':C.named_columns(names,model['movable'],array(robot.get_dof_positions())[0]),
                    'qd':C.named_columns(names,model['movable'],array(robot.get_dof_velocities())[0])}
    ctx._contact_probe.state_reader = contact_state_read
    report['constraint_order']['after_reset'] = _constraint_order_readback(sim,stage,clock,contact_state_read)
    ctx.write(out/'constraint-order.json',report['constraint_order'])
    report['velocity_limits']['tensor_after_reset'] = _velocity_limits(ctx,robot,names,model,C,array,backend,clock,state,repair=True)
    ctx.write(out/'velocity-limits.json',ctx._velocity_audit)
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
                _fault_begin(ctx,stage_name,report['completed_steps']+1,target,current,proof,remaining)
                sim.step(render=False)
                report['completed_steps'] += 1
                current = state()
                _fault_observe(ctx,current)
                ctx._contact_probe.sample(report['completed_steps'])
                validate_clocks(current['clock'], baseline, report['completed_steps'], program['dt_s'])
                floor_z, bounds = C.floor_and_bounds(model, matrices(current), support)
                need(floor_z >= -.0001, 'Actual moving body clears desk')
                base = next(p for p in current['body_poses'] if p['name'] == 'Base')
                C.near(C.tf(base['position'], C.quat(base['orientation_wxyz'])), C.ident(), 2e-5)
                for name in names:
                    j = model['joints'][name]
                    need(j['lower']-1e-5 <= current['q'][name] <= j['upper']+1e-5, 'Actual source position limit:'+name)
                    need(abs(current['qd'][name]) <= j['velocity']+1e-4, 'Actual source speed limit:'+name)
                need(not ctx._contact_probe.last.get('observer_changed_state',False) and not ctx._contact_probe.last.get('state_preservation_unverified',False), 'Contact diagnostic changes no native clock/q/qd')
                row = row_for(stage_name, local_step, current, target, proof, remaining)
                row['minimum_moving_link_z_m'] = floor_z
                journal.write(json.dumps(row, allow_nan=False, separators=(',', ':'))+'\n'); journal.flush()
                ctx._fault_pending['accepted_journal'] = True
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
    """One collector; primary exceptions survive every diagnostic/finalization failure."""
    report = ledger(ctx)
    budget = ctx.native_budget if hasattr(ctx, 'native_budget') else arm_watchdog(ctx)
    primary = None
    primary_tb = None
    gate = False
    try:
        budget.check()
        ctx.write(ctx.run/'output/report.partial.json', report)
        _native(ctx, app, report, budget)
    except GateFailure as exc:
        primary, primary_tb, gate = exc, exc.__traceback__, True
        mark(report, budget.phase, 'FAIL', str(exc), completed_steps=report['completed_steps'])
        report['gate_failure'] = str(exc)
        _save_first_fault(ctx, report, exc)
        if hasattr(ctx, 'native_camera') and report['frames']:
            try: report['render'] = ctx.native_camera.finish(len(report['frames']), purpose='render_smoke')
            except BaseException as secondary: _diag_secondary(ctx,'camera_finish',secondary)
        if hasattr(ctx, 'init_boundary'):
            try: ctx.init_boundary.finish(report['completed_steps'])
            except BaseException as secondary: _diag_secondary(ctx,'boundary_finish',secondary)
    except BaseException as exc:
        primary, primary_tb = exc, exc.__traceback__
        mark(report, budget.phase, 'FAIL', type(exc).__name__+': '+str(exc), completed_steps=report['completed_steps'])
        report['exception'] = traceback.format_exc()
        _save_first_fault(ctx, report, exc)
    finally:
        if hasattr(ctx, '_contact_probe'):
            try: report['contact_cleanup'] = _diag_final_copy(ctx,'contact_cleanup_copy',ctx._contact_probe.close())
            except BaseException as secondary: _diag_secondary(ctx,'contact_close',secondary)
        if hasattr(ctx, 'init_boundary'):
            try:
                errors = ctx.init_boundary.close()
                report['init_cleanup_errors'] = _diag_final_copy(ctx,'init_cleanup_copy',errors)
                if errors:
                    if primary is None:
                        primary = RuntimeError('INIT_CLEANUP_FAILED:'+str(errors))
                        mark(report,budget.phase,'FAIL',str(primary))
                        _save_first_fault(ctx,report,primary)
                    else: _diag_secondary(ctx,'init_cleanup_errors',RuntimeError(str(errors)))
            except BaseException as secondary:
                if primary is None:
                    primary, primary_tb = secondary, secondary.__traceback__
                    mark(report,budget.phase,'FAIL','INIT_CLEANUP_EXCEPTION:'+str(secondary))
                    _save_first_fault(ctx,report,primary)
                else: _diag_secondary(ctx,'init_cleanup_exception',secondary)
        report['elapsed_native_s'] = time.monotonic()-ctx.started_monotonic
        report['native_deadline_monotonic'] = budget.end
        report['diagnostic_secondary'] = _diag_final_copy(ctx,'secondary_final_copy',getattr(ctx,'_diag_secondary',[]))
        if hasattr(ctx, '_contact_probe'): report['last_contact_observation'] = _diag_final_copy(ctx,'contact_final_copy',ctx._contact_probe.last)
        if hasattr(ctx,'_velocity_audit'): report['velocity_limits'] = _diag_final_copy(ctx,'velocity_final_copy',ctx._velocity_audit)
        try: ctx.write(ctx.run/'output/report.json', report)
        except BaseException as secondary:
            if primary is None: primary, primary_tb = secondary, secondary.__traceback__
            else: _diag_secondary(ctx,'final_report_write',secondary)
            report['diagnostic_secondary'] = _diag_owned(getattr(ctx,'_diag_secondary',[]))
    if primary is not None and not gate:
        raise primary.with_traceback(primary_tb)
    return report

