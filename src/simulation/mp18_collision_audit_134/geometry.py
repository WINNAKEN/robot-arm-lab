"""Source convex envelopes. No backend cooking, contacts, or continuous tests."""
from dataclasses import dataclass
from itertools import product

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull

TOLERANCE_M = 1e-6
SEPARATION = 'CERTIFIED_SOURCE_ENVELOPE_SEPARATION'
OVERLAP = 'VERIFIED_SOURCE_ENVELOPE_OVERLAP_AT_SAMPLED_POSE'
UNKNOWN = 'UNKNOWN_OR_UNCHECKED'


@dataclass(frozen=True)
class Hull:
    vertices: np.ndarray
    equations: np.ndarray
    corners: np.ndarray


def hull(points):
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError('Finite Nx3 source vertices required')
    result = ConvexHull(np.unique(points, axis=0))
    vertices = result.points[result.vertices].copy()
    equations = result.equations.copy()
    equations /= np.linalg.norm(equations[:, :3], axis=1)[:, None]
    residual = points @ equations[:, :3].T + equations[:, 3]
    if np.max(residual) > numeric_error(points):
        raise ValueError('Source hull does not enclose every source vertex')
    bounds = np.array([points.min(axis=0), points.max(axis=0)])
    corners = np.array(list(product(*zip(bounds[0], bounds[1]))))
    return Hull(vertices, equations, corners)


def numeric_error(*arrays):
    """Roundoff guard, separate from the fixed one micrometre geometric margin."""
    scale = max([1.] + [float(np.max(np.abs(a))) for a in arrays if np.size(a)])
    return 128 * np.finfo(np.float64).eps * scale


def rotations(wxyz):
    q = np.asarray(wxyz, dtype=np.float64)
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
                     2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
                     2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], axis=-1).reshape(q.shape[:-1]+(3, 3))


def rpy_rotation(rpy):
    r, p, y = np.asarray(rpy, dtype=np.float64)
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                     [-sp, cp*sr, cp*cr]])


def transformed(shape, rotation, translation):
    vertices = shape.vertices @ rotation.T + translation
    normals = shape.equations[:, :3] @ rotation.T
    offsets = shape.equations[:, 3] - normals @ translation
    corners = shape.corners @ rotation.T + translation
    return Hull(vertices, np.column_stack([normals, offsets]), corners)


def world_boxes(shape, rotation, translation):
    points = np.einsum('nij,kj->nki', rotation, shape.corners) + translation[:, None, :]
    guard = numeric_error(points)
    return points.min(axis=1)-guard, points.max(axis=1)+guard


def box_axis_gaps(a_min, a_max, b_min, b_max):
    return np.maximum(b_min-a_max, a_min-b_max)


def support_certificate(a, b, direction, tolerance=TOLERANCE_M):
    axis = np.asarray(direction, dtype=np.float64)
    if axis.shape != (3,) or not np.isfinite(axis).all():
        return None
    norm = np.linalg.norm(axis)
    if norm < 1e-14:
        return None
    axis = axis / norm
    a_projection, b_projection = a.vertices @ axis, b.vertices @ axis
    forward = float(b_projection.min()-a_projection.max())
    reverse = float(a_projection.min()-b_projection.max())
    if reverse > forward:
        axis = -axis
        a_projection, b_projection = -a_projection, -b_projection
    gap = float(b_projection.min()-a_projection.max())
    guard = numeric_error(a.vertices, b.vertices)
    if gap <= tolerance+guard:
        return None
    return {'axis': axis.tolist(), 'a_support_max_m': float(a_projection.max()),
            'b_support_min_m': float(b_projection.min()), 'gap_m': gap,
            'roundoff_guard_m': guard, 'required_margin_m': tolerance+guard}


def point_certificate(a, b, candidate, tolerance=TOLERANCE_M):
    point = np.asarray(candidate, dtype=np.float64)
    if point.shape != (3,) or not np.isfinite(point).all():
        return None
    slacks = [-np.max(s.equations[:, :3] @ point+s.equations[:, 3]) for s in (a, b)]
    guard = numeric_error(point, a.vertices, b.vertices)
    if min(slacks) <= tolerance+guard:
        return None
    return {'point_world_m': point.tolist(), 'minimum_face_slack_a_m': float(slacks[0]),
            'minimum_face_slack_b_m': float(slacks[1]), 'roundoff_guard_m': guard,
            'required_margin_m': tolerance+guard}


def classify(a, b, solver=linprog):
    """LP only proposes witnesses; original face/vertex arithmetic certifies them."""
    axes = np.vstack([a.equations[:, :3], b.equations[:, :3],
                      b.vertices.mean(axis=0)-a.vertices.mean(axis=0)])
    for axis in axes:
        cert = support_certificate(a, b, axis)
        if cert:
            return {'category': SEPARATION, 'mechanism': 'DIRECT_VERTEX_SUPPORT', 'witness': cert}
    equations = np.vstack([a.equations, b.equations])
    matrix = np.column_stack([equations[:, :3], np.ones(len(equations))])
    try:
        result = solver([0., 0., 0., -1.], A_ub=matrix, b_ub=-equations[:, 3],
                        bounds=[(None, None)]*4, method='highs')
    except Exception as exc:
        return {'category': UNKNOWN, 'reason': 'SOLVER_EXCEPTION', 'error': type(exc).__name__+': '+str(exc)}
    if not getattr(result, 'success', False):
        return {'category': UNKNOWN, 'reason': 'SOLVER_NOT_SUCCESSFUL', 'solver_status': str(getattr(result, 'status', None))}
    solution = np.asarray(getattr(result, 'x', []), dtype=float)
    if solution.shape != (4,) or not np.isfinite(solution).all():
        return {'category': UNKNOWN, 'reason': 'INVALID_SOLVER_CANDIDATE'}
    certificate = point_certificate(a, b, solution[:3])
    if certificate:
        return {'category': OVERLAP, 'mechanism': 'DIRECT_ALL_FACE_POINT_RECHECK', 'witness': certificate,
                'candidate_radius_m': float(solution[3])}
    ineqlin = getattr(result, 'ineqlin', None)
    dual = np.asarray(getattr(ineqlin, 'marginals', []), dtype=float)
    if dual.shape == (len(equations),) and np.isfinite(dual).all():
        axis = dual[:len(a.equations)] @ a.equations[:, :3]
        cert = support_certificate(a, b, axis)
        if cert:
            return {'category': SEPARATION, 'mechanism': 'LP_AXIS_DIRECT_VERTEX_SUPPORT_RECHECK', 'witness': cert}
    return {'category': UNKNOWN, 'reason': 'NO_STRICT_DIRECT_GEOMETRIC_CERTIFICATE',
            'candidate_radius_m': float(solution[3])}
