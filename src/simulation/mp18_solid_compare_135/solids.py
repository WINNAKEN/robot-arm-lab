"""135: untouched triangle solids, exact-index welding and millimetre Boolean."""
from __future__ import annotations

import logging
from dataclasses import dataclass
import struct

import manifold3d
import numpy as np
import trimesh
from scipy.spatial import cKDTree

LOG = logging.getLogger(__name__)
PRINTED = 'PRINTED_STL_MODEL_OVERLAP'
APPROX = 'MODELED_APPROX_COMPONENT_OVERLAP'
ZERO = 'NO_POSITIVE_ORIGINAL_VOLUME_INTERSECTION_AT_SELECTED_POSE'
SMALL = 'SMALL_VOLUME_UNCERTAIN'
UNKNOWN = 'UNKNOWN'
SMALL_MM3 = .01
BOUNDS_M_ATOL = 1e-8  # float32 STL serialization of ledger double coordinates
CLOUD_M_ATOL = 1e-9


def require(condition, message):
    if not condition:
        raise ValueError(message)


def binary_triangles(raw):
    """Read raw STL face order; no mesh importer sorting or automatic repairs."""
    require(len(raw) >= 84, 'Truncated binary STL header')
    count = struct.unpack_from('<I', raw, 80)[0]
    require(count > 0 and len(raw) == 84 + count * 50, 'STL face count/bytes')
    dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
    triangles = np.frombuffer(raw, dtype=dtype, offset=84, count=count)['vertices'].astype(np.float64)
    require(np.isfinite(triangles).all(), 'Nonfinite original triangle coordinate')
    return triangles


def indexed(triangles):
    triangles = np.asarray(triangles, dtype=np.float64)
    require(triangles.ndim == 3 and triangles.shape[1:] == (3, 3) and len(triangles) > 0,
            'Empty/invalid triangle shape')
    require(np.isfinite(triangles).all(), 'Nonfinite triangle input')
    vertices, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    return vertices, inverse.reshape(-1, 3)


def triangle_volume(triangles):
    # Independent original-triangle divergence sum, translated near the origin.
    shift = np.mean(triangles.reshape(-1, 3), axis=0)
    t = triangles - shift
    return float(np.sum(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2]))) / 6)


def cloud_distance(a, b):
    a, b = np.asarray(a, dtype=float).reshape(-1, 3), np.asarray(b, dtype=float).reshape(-1, 3)
    require(len(a) > 0 and len(b) > 0 and np.isfinite(a).all() and np.isfinite(b).all(), 'Invalid cloud')
    return max(float(cKDTree(a).query(b)[0].max()), float(cKDTree(b).query(a)[0].max()))


@dataclass
class Solid:
    id: str
    kind: str
    owner: str
    triangles_mm: np.ndarray
    bounds_mm: np.ndarray
    manifold: object | None
    evidence: dict


def prepare_solid(part_id, kind, owner, triangles_mm, constructor=None):
    """An invalid or empty Manifold import can never become a valid zero pair."""
    data = {'id': part_id, 'kind': kind, 'owner': owner, 'valid': False, 'status': UNKNOWN}
    triangles = np.asarray(triangles_mm, dtype=float)
    bounds = np.full((2, 3), np.nan)
    try:
        vertices, faces = indexed(triangles)
        bounds = np.array([vertices.min(axis=0), vertices.max(axis=0)])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        raw_volume = triangle_volume(triangles)
        data.update(triangles=len(faces), exact_unique_vertices=len(vertices), watertight=bool(mesh.is_watertight),
                    winding_consistent=bool(mesh.is_winding_consistent), triangle_volume_mm3=raw_volume,
                    trimesh_volume_mm3=float(mesh.volume))
        require(mesh.is_watertight and mesh.is_winding_consistent, 'Original triangles are not closed oriented two-manifold')
        require(np.isfinite(raw_volume) and raw_volume > 0, 'Original signed volume must be positive')
        require(abs(float(mesh.volume) - raw_volume) <= max(1e-8, raw_volume * 2e-8), 'Original triangle volume disagreement')
        constructor = manifold3d.Manifold if constructor is None else constructor
        solid = constructor(manifold3d.Mesh64(vert_properties=vertices, tri_verts=faces.astype(np.uint64)))
        status, empty, volume = solid.status(), bool(solid.is_empty()), float(solid.volume())
        data.update(manifold_status=str(status), manifold_empty=empty, manifold_volume_mm3=volume)
        require(status == manifold3d.Error.NoError, 'Manifold import error: ' + str(status))
        require(not empty and np.isfinite(volume) and volume > 0, 'Empty/nonpositive Manifold input')
        tolerance = max(1e-6, raw_volume * 2e-7)
        data['volume_comparison_tolerance_mm3'] = tolerance
        require(abs(volume - raw_volume) <= tolerance, 'Manifold import changed original volume')
        data.update(valid=True, status='VALID_ORIGINAL_TRIANGLE_SOLID')
        return Solid(part_id, kind, owner, triangles, bounds, solid, data)
    except (ValueError, RuntimeError, TypeError, IndexError) as error:
        LOG.warning('Original solid %s is UNKNOWN: %s', part_id, error)
        data['reason'] = str(error)
        return Solid(part_id, kind, owner, triangles, bounds, None, data)


def rotation(wxyz):
    q = np.asarray(wxyz, dtype=float)
    require(q.shape == (4,) and np.isfinite(q).all(), 'Invalid actual wxyz')
    norm = float(np.linalg.norm(q))
    require(abs(norm - 1) <= 1e-5, 'Actual quaternion not near unit')
    w, x, y, z = q / norm
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def relative_transform(pose_a, pose_b):
    ra, rb = [rotation(p['original_orientation_wxyz']) for p in (pose_a, pose_b)]
    pa, pb = [np.asarray(p['position_m'], dtype=float) for p in (pose_a, pose_b)]
    require(pa.shape == pb.shape == (3,) and np.isfinite(pa).all() and np.isfinite(pb).all(), 'Invalid actual position')
    t = np.eye(4)
    t[:3, :3] = ra.T @ rb
    t[:3, 3] = ra.T @ ((pb - pa) * 1000)
    return t


def transformed_bounds(bounds, transform):
    corners = np.array([[bounds[i, 0], bounds[j, 1], bounds[k, 2]]
                        for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    moved = corners @ transform[:3, :3].T + transform[:3, 3]
    return np.array([moved.min(axis=0), moved.max(axis=0)])


def category(volume_mm3, kind_a, kind_b):
    require(np.isfinite(volume_mm3) and volume_mm3 >= 0, 'Invalid intersection volume')
    if volume_mm3 == 0:
        return ZERO
    if volume_mm3 <= SMALL_MM3:
        return SMALL
    return PRINTED if kind_a == kind_b == 'PRINTED_STL' else APPROX


def compare_pair(a, b, b_in_a, intersection=None):
    result = {'part_a': a.id, 'part_b': b.id, 'kind_a': a.kind, 'kind_b': b.kind,
              'category': UNKNOWN, 'volume_mm3': None, 'boolean_calls': 0}
    if not a.evidence['valid'] or not b.evidence['valid']:
        result['reason'] = 'INVALID_ORIGINAL_SOLID_INPUT'
        return result
    moved_bounds = transformed_bounds(b.bounds_mm, b_in_a)
    gaps = np.maximum(a.bounds_mm[0] - moved_bounds[1], moved_bounds[0] - a.bounds_mm[1])
    guard = 128 * np.finfo(float).eps * max(1., float(np.abs(np.r_[a.bounds_mm.ravel(), moved_bounds.ravel()]).max()))
    if np.any(gaps > guard):
        result.update(category=ZERO, volume_mm3=0., mechanism='CONSERVATIVE_ORIGINAL_BOUNDS_SEPARATION',
                      axis_gaps_mm=gaps.tolist(), roundoff_guard_mm=guard)
        return result
    try:
        result['boolean_calls'] = 1
        moved = b.manifold.transform(b_in_a[:3, :])
        require(moved.status() == manifold3d.Error.NoError and not moved.is_empty(), 'Invalid transformed input')
        overlap = (a.manifold ^ moved) if intersection is None else intersection(a.manifold, moved)
        status, empty, volume = overlap.status(), bool(overlap.is_empty()), float(overlap.volume())
        result.update(manifold_status=str(status), intersection_empty=empty, mechanism='MANIFOLD_MESH64_INTERSECTION_MM')
        require(status == manifold3d.Error.NoError, 'Boolean error status: ' + str(status))
        require(np.isfinite(volume) and volume >= 0 and (not empty or volume == 0), 'Invalid Boolean volume/empty state')
        # A valid surface-touching intersection may be nonempty with exactly zero volume.
        require(volume <= min(a.evidence['manifold_volume_mm3'], b.evidence['manifold_volume_mm3']) +
                max(1e-6, volume * 2e-7), 'Intersection larger than original input')
        result.update(category=category(volume, a.kind, b.kind), volume_mm3=volume)
    except (ValueError, RuntimeError, TypeError) as error:
        LOG.warning('Boolean %s/%s is UNKNOWN: %s', a.id, b.id, error)
        result['reason'] = str(error)
    return result
