"""041 actual saved-USD observations. No expected CAD frames or physics playback."""
import hashlib
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vector(value):
    return None if value is None else [float(x) for x in value]


def quaternion(value):
    if value is None:
        return None
    # Gf explicitly exposes real=w and imaginary=(x,y,z).
    return [float(value.GetReal()), *vector(value.GetImaginary())]


def observe_stage(stage, usd_path, runtime, timeline_stopped):
    """Read composed attributes and actual Mesh points from the reloaded stage."""
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdUtils

    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    prims = list(Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()))
    body_prims = {str(p.GetPath()): p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)}
    geometry = {path: {'min': None, 'max': None, 'meshes': [], 'point_count': 0} for path in body_prims}

    def placement(prim):
        transform = cache.GetLocalToWorldTransform(prim)
        position = vector(transform.Transform(Gf.Vec3d(0, 0, 0)))
        columns = [vector(transform.TransformDir(Gf.Vec3d(*(int(i == j) for i in range(3))))) for j in range(3)]
        # Preserve full basis, including scale/shear/reflection; validator must not
        # hide them by extracting a normalized quaternion.
        rotation = [[columns[j][i] for j in range(3)] for i in range(3)]
        return position, rotation

    for prim in prims:
        if not prim.IsA(UsdGeom.Mesh):
            continue
        owner, cursor, excluded = None, prim, False
        while cursor and not cursor.IsPseudoRoot():
            if cursor.HasAPI(UsdPhysics.CollisionAPI):
                excluded = True
            if cursor.IsA(UsdGeom.Imageable):
                imageable = UsdGeom.Imageable(cursor)
                if imageable.ComputePurpose() == UsdGeom.Tokens.guide:
                    excluded = True
                if imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
                    excluded = True
            if str(cursor.GetPath()) in body_prims:
                owner = str(cursor.GetPath())
                break
            cursor = cursor.GetParent()
        if owner is None or excluded:
            continue
        points = UsdGeom.Mesh(prim).GetPointsAttr().Get()
        if points is None or len(points) == 0:
            raise ValueError('Visual mesh has no actual points: ' + str(prim.GetPath()))
        transform = cache.GetLocalToWorldTransform(prim)
        entry = geometry[owner]
        entry['meshes'].append(str(prim.GetPath()))
        entry['point_count'] += len(points)
        for point in points:
            world = vector(transform.Transform(Gf.Vec3d(*vector(point))))
            if entry['min'] is None:
                entry['min'], entry['max'] = world[:], world[:]
            else:
                entry['min'] = [min(entry['min'][i], world[i]) for i in range(3)]
                entry['max'] = [max(entry['max'][i], world[i]) for i in range(3)]

    bodies = []
    for path, prim in sorted(body_prims.items()):
        position, rotation = placement(prim)
        mass_api = UsdPhysics.MassAPI(prim) if prim.HasAPI(UsdPhysics.MassAPI) else None
        attrs = {} if mass_api is None else {
            'mass': mass_api.GetMassAttr(), 'com': mass_api.GetCenterOfMassAttr(),
            'inertia_diag': mass_api.GetDiagonalInertiaAttr(), 'principal_axes': mass_api.GetPrincipalAxesAttr()}
        entry = geometry[path]
        mass = attrs['mass'].Get() if attrs else None
        bodies.append({
            'name': prim.GetName(), 'path': path, 'position': position, 'rotation': rotation,
            'mass': None if mass is None else float(mass),
            'com': vector(attrs['com'].Get()) if attrs else None,
            'inertia_diag': vector(attrs['inertia_diag'].Get()) if attrs else None,
            'principal_axes_wxyz': quaternion(attrs['principal_axes'].Get()) if attrs else None,
            'mass_api_applied': mass_api is not None,
            'mass_properties_authored': {name: bool(attr.HasAuthoredValueOpinion()) for name, attr in attrs.items()},
            'visual_bounds': None if entry['min'] is None else {'min': entry['min'], 'max': entry['max']},
            'visual_meshes': entry['meshes'], 'visual_point_count': entry['point_count'],
            'applied_schemas': list(prim.GetAppliedSchemas()),
        })

    def target(relationship):
        paths = relationship.GetTargets()
        if len(paths) > 1:
            raise ValueError('Ambiguous joint body relationship: ' + str(relationship.GetPath()))
        return str(paths[0]) if paths else None

    joints = []
    for prim in prims:
        if not prim.IsA(UsdPhysics.Joint):
            continue
        joint = UsdPhysics.Joint(prim)
        revolute = UsdPhysics.RevoluteJoint(prim) if prim.IsA(UsdPhysics.RevoluteJoint) else None
        kind = 'revolute' if revolute else 'fixed' if prim.IsA(UsdPhysics.FixedJoint) else prim.GetTypeName()
        joints.append({
            'name': prim.GetName(), 'path': str(prim.GetPath()), 'type': kind,
            'body0': target(joint.GetBody0Rel()), 'body1': target(joint.GetBody1Rel()),
            'axis': str(revolute.GetAxisAttr().Get()) if revolute else None,
            'local_pos0': vector(joint.GetLocalPos0Attr().Get()),
            'local_pos1': vector(joint.GetLocalPos1Attr().Get()),
            'local_rot0_wxyz': quaternion(joint.GetLocalRot0Attr().Get()),
            'local_rot1_wxyz': quaternion(joint.GetLocalRot1Attr().Get()),
            'lower_limit': float(revolute.GetLowerLimitAttr().Get()) if revolute else None,
            'upper_limit': float(revolute.GetUpperLimitAttr().Get()) if revolute else None,
            'applied_schemas': list(prim.GetAppliedSchemas()),
        })

    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(Sdf.AssetPath(str(usd_path)))
    metadata = {}
    for name in ('metersPerUnit', 'kilogramsPerUnit'):
        authored = bool(stage.HasAuthoredMetadata(name))
        metadata[name] = {'authored': authored, 'value': float(stage.GetMetadata(name)) if authored else None}
    default_prim = stage.GetDefaultPrim()
    root_placement = None
    if default_prim:
        pos, rot = placement(default_prim)
        root_placement = {'path': str(default_prim.GetPath()), 'position': pos, 'rotation': rot}
    return {
        'schema_version': 1, 'observation_kind': 'ACTUAL_RELOADED_USD_STATIC',
        'usd_path': str(Path(usd_path).resolve()), 'usd_sha256': sha256(usd_path),
        'timeline_stopped': bool(timeline_stopped),
        'units': {
            'meters_per_unit': float(UsdGeom.GetStageMetersPerUnit(stage)),
            'kilograms_per_unit': float(UsdPhysics.GetStageKilogramsPerUnit(stage)),
            'up_axis': str(UsdGeom.GetStageUpAxis(stage)),
            'meters_per_unit_authored': metadata['metersPerUnit']['authored'],
            'kilograms_per_unit_authored': metadata['kilogramsPerUnit']['authored'],
            'meters_per_unit_authored_value': metadata['metersPerUnit']['value'],
            'kilograms_per_unit_authored_value': metadata['kilogramsPerUnit']['value'],
        },
        'default_prim': str(default_prim.GetPath()) if default_prim else None,
        'root_placement': root_placement, 'bodies': bodies, 'joints': joints,
        'dependencies': {
            'layers': [str(layer.realPath or layer.identifier) for layer in layers],
            'assets': [str(asset) for asset in assets], 'unresolved': [str(asset) for asset in unresolved],
        },
        'runtime': runtime, 'physical_verified': False, 'hardware_approved': False,
        'ring_geometry': 'DEFERRED', 'dynamics_playback': 'NOT_RUN', 'rl_training': 'NOT_RUN',
    }
