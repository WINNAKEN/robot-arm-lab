"""043 explicit collision configuration, environment frames and actual contact tensors."""
import math

ROOT = '/World/Robot/Geometry/Base'
NAMES = ['Base']+[f'Link{i}' for i in range(1, 7)]
PATHS = [ROOT + ''.join('/Link'+str(j) for j in range(1, i+1)) for i in range(7)]
GROUND, PROBE, MATERIAL = '/World/Ground', '/World/ContactProbe', '/World/ContactMaterial'
SENSORS, FILTERS = PATHS+[PROBE], [GROUND]+PATHS+[PROBE]
CAPACITY = 512


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def setup(stage):
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade, PhysxSchema
    material = UsdShade.Material.Define(stage, MATERIAL)
    m = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    m.CreateStaticFrictionAttr(.6); m.CreateDynamicFrictionAttr(.5); m.CreateRestitutionAttr(0.)
    ground = UsdGeom.Cube.Define(stage, GROUND)
    ground.CreateSizeAttr(1.)
    ground.AddTranslateOp().Set(Gf.Vec3d(0, 0, -.05))
    ground.AddScaleOp().Set(Gf.Vec3f(4, 4, .1))
    probe = UsdGeom.Cube.Define(stage, PROBE)
    probe.CreateSizeAttr(.05)
    probe.AddTranslateOp().Set(Gf.Vec3d(-.6, 0, .2))
    UsdPhysics.RigidBodyAPI.Apply(probe.GetPrim())
    mass = UsdPhysics.MassAPI.Apply(probe.GetPrim())
    mass.CreateMassAttr(.1); mass.CreateCenterOfMassAttr(Gf.Vec3f(0))
    mass.CreateDiagonalInertiaAttr(Gf.Vec3f(.1*.05*.05/6))
    mass.CreatePrincipalAxesAttr(Gf.Quatf(1))
    for prim in (ground.GetPrim(), probe.GetPrim()):
        UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(True)
            prim.CreateRelationship('material:binding:physics').SetTargets([Sdf.Path(MATERIAL)])
    for path in SENSORS:
        PhysxSchema.PhysxContactReportAPI.Apply(stage.GetPrimAtPath(path)).CreateThresholdAttr(0.)
    PhysxSchema.PhysxArticulationAPI.Apply(stage.GetPrimAtPath(ROOT)).CreateEnabledSelfCollisionsAttr(True)
    for parent, child in zip(PATHS, PATHS[1:]):
        UsdPhysics.FilteredPairsAPI.Apply(stage.GetPrimAtPath(parent)).CreateFilteredPairsRel().SetTargets([Sdf.Path(child)])
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.RevoluteJoint):
            UsdPhysics.Joint(prim).CreateCollisionEnabledAttr(True)


def snapshot(stage):
    from pxr import Gf, Usd, UsdGeom, UsdPhysics, PhysxSchema
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    def pose(path):
        p = stage.GetPrimAtPath(path); t = cache.GetLocalToWorldTransform(p)
        return {'path': path, 'position': [float(x) for x in t.ExtractTranslation()],
                'basis': [[float(t[j][i]) for j in range(3)] for i in range(3)],
                'size': float(UsdGeom.Cube(p).GetSizeAttr().Get()),
                'collision_enabled': bool(UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get()),
                'rigid': p.HasAPI(UsdPhysics.RigidBodyAPI)}
    def quat(q):
        return [float(q.GetReal()), *[float(x) for x in q.GetImaginary()]]
    probe = UsdPhysics.MassAPI(stage.GetPrimAtPath(PROBE))
    mat = UsdPhysics.MaterialAPI(stage.GetPrimAtPath(MATERIAL))
    probe_world = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(PROBE))
    probe_local = probe_world * probe_world.GetInverse()  # Collider and body are the same Cube prim.
    return {'ground': pose(GROUND), 'probe': {**pose(PROBE), 'mass': float(probe.GetMassAttr().Get()),
        'com': list(probe.GetCenterOfMassAttr().Get()), 'inertia_diag': list(probe.GetDiagonalInertiaAttr().Get()),
        'principal_axes_wxyz': quat(probe.GetPrincipalAxesAttr().Get()), 'collider_owner_path': PROBE,
        'collider_local_position': [float(x) for x in probe_local.ExtractTranslation()],
        'collider_local_basis': [[float(probe_local[j][i]) for j in range(3)] for i in range(3)]},
        'material': {'path': MATERIAL, 'static_friction': float(mat.GetStaticFrictionAttr().Get()),
            'dynamic_friction': float(mat.GetDynamicFrictionAttr().Get()), 'restitution': float(mat.GetRestitutionAttr().Get())},
        'filters': {str(p.GetPath()): [str(x) for x in UsdPhysics.FilteredPairsAPI(p).GetFilteredPairsRel().GetTargets()]
            for p in stage.Traverse() if p.HasAPI(UsdPhysics.FilteredPairsAPI)},
        'joint_collisions': {p.GetName(): bool(UsdPhysics.Joint(p).GetCollisionEnabledAttr().Get())
            for p in stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)},
        'report_thresholds': {path: float(PhysxSchema.PhysxContactReportAPI(stage.GetPrimAtPath(path)).GetThresholdAttr().Get()) for path in SENSORS},
        'material_bindings': {str(p.GetPath()): [str(x) for x in p.GetRelationship('material:binding:physics').GetTargets()]
            for p in stage.Traverse() if p.HasAPI(UsdPhysics.CollisionAPI)},
        'actors': [str(p.GetPath()) for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)],
        'colliders': [str(p.GetPath()) for p in stage.Traverse() if p.HasAPI(UsdPhysics.CollisionAPI)]}


class ContactReader:
    def __init__(self, sim_view):
        self.view = sim_view.create_rigid_contact_view(SENSORS, [FILTERS[:] for _ in SENSORS], max_contact_data_count=CAPACITY)
        v = self.view
        self.sensors, raw_filters = list(v.sensor_paths), list(v.filter_paths)
        need(v.sensor_count == 8 and v.filter_count == 9 and v.max_contact_data_count == CAPACITY, 'Actual contact tensor dimensions')
        need(len(self.sensors) == 8 and set(self.sensors) == set(SENSORS), 'Actual contact sensor mapping')
        if len(raw_filters) == 9 and all(isinstance(x, str) for x in raw_filters):
            raw_filters = [raw_filters[:] for _ in range(8)]
        elif len(raw_filters) == 72 and all(isinstance(x, str) for x in raw_filters):
            raw_filters = [raw_filters[i*9:(i+1)*9] for i in range(8)]
        need(len(raw_filters) == 8 and all(len(x) == 9 and set(x) == set(FILTERS) for x in raw_filters), 'Actual contact filter mapping')
        self.filters = raw_filters
        self.mapping = {'sensor_paths': self.sensors, 'filter_paths': self.filters, 'canonical_sensors': SENSORS,
                        'canonical_filters': FILTERS, 'capacity': CAPACITY, 'force_frame': 'WORLD', 'force_units': 'N'}

    def read(self, dt):
        import numpy as np
        def host(x):
            return x.numpy().copy() if hasattr(x, 'numpy') else np.array(x, copy=True)
        matrix = host(self.view.get_normal_contact_force_matrix(dt))
        force, point, normal, separation, counts, starts = [host(x) for x in self.view.get_normal_contact_data(dt)]
        need(matrix.shape == (8, 9, 3) and np.isfinite(matrix).all(), 'Finite full contact matrix')
        need(counts.shape == starts.shape == (8, 9) and int(counts.sum()) < CAPACITY, 'Contact capacity/shape')
        result, nums, active = [], [], []
        for i, path in enumerate(SENSORS):
            si = self.sensors.index(path); row, ns = [], []
            for j, target in enumerate(FILTERS):
                fi = self.filters[si].index(target)
                n, start = int(counts[si, fi]), int(starts[si, fi])
                need(0 <= n < CAPACITY and (n == 0 or 0 <= start < start+n <= CAPACITY), 'Contact buffer range')
                row.append(matrix[si, fi].tolist()); ns.append(n)
                for k in range(start, start+n):
                    values = [float(force[k, 0]), *point[k].tolist(), *normal[k].tolist(), float(separation[k, 0])]
                    need(all(math.isfinite(x) for x in values), 'Finite active contact')
                    active.append({'sensor': i, 'filter': j, 'force_N': values[0], 'point': values[1:4],
                                   'normal': values[4:7], 'separation_m': values[7]})
            result.append(row); nums.append(ns)
        return {'normal_force_N': result, 'counts': nums, 'active': active, 'dt_s': dt}
