"""Analytic HOST checks of certificates, including adversarial LP candidates."""
import itertools
import pathlib
import sys
import unittest
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import geometry as geo


def box(half=(.5, .5, .5), center=(0, 0, 0), rpy=(0, 0, 0)):
    points = np.array(list(itertools.product(*[(-h, h) for h in half])))
    return geo.transformed(geo.hull(points), geo.rpy_rotation(rpy), np.asarray(center))


class Certificates(unittest.TestCase):
    def test_axis_support_separation_directly_rechecks(self):
        a, b = box(), box(center=(2, 0, 0))
        result = geo.classify(a, b)
        self.assertEqual(result['category'], geo.SEPARATION)
        witness = result['witness']
        axis = np.array(witness['axis'])
        self.assertAlmostEqual(np.linalg.norm(axis), 1)
        self.assertAlmostEqual(min(b.vertices@axis)-max(a.vertices@axis), 1)
        self.assertIsNone(geo.support_certificate(a, b, [0, 1, 0]))
        self.assertIsNone(geo.support_certificate(a, b, [float('nan'), 0, 0]))

    def test_strict_overlap_witness_all_faces(self):
        a, b = box(), box(center=(.25, 0, 0))
        result = geo.classify(a, b)
        self.assertEqual(result['category'], geo.OVERLAP)
        point = np.array(result['witness']['point_world_m'])
        for shape in (a, b):
            self.assertLess(np.max(shape.equations[:, :3]@point+shape.equations[:, 3]), -geo.TOLERANCE_M)

    def test_containment_is_overlap(self):
        self.assertEqual(geo.classify(box(), box((.1, .1, .1)))['category'], geo.OVERLAP)

    def test_touching_and_tolerance_boundary_unknown(self):
        for shift in (1, 1+geo.TOLERANCE_M/2, 1-geo.TOLERANCE_M/2):
            self.assertEqual(geo.classify(box(), box(center=(shift, 0, 0)))['category'], geo.UNKNOWN)

    def test_rotated_aabb_false_positive(self):
        a = box((1, .05, .05), rpy=(0, 0, np.pi/4))
        b = box((1, .05, .05), center=(-.12/np.sqrt(2), .12/np.sqrt(2), 0), rpy=(0, 0, np.pi/4))
        gaps = geo.box_axis_gaps(a.corners.min(axis=0), a.corners.max(axis=0),
                                 b.corners.min(axis=0), b.corners.max(axis=0))
        self.assertLess(gaps.max(), 0)
        self.assertEqual(geo.classify(a, b)['category'], geo.SEPARATION)

    def test_solver_failures_do_not_pass(self):
        def failure(*args, **kwargs):
            raise RuntimeError('injected solver failure')
        for solver in (failure, lambda *a, **k: SimpleNamespace(success=False, status=4)):
            result = geo.classify(box(), box(center=(.25, 0, 0)), solver=solver)
            self.assertEqual(result['category'], geo.UNKNOWN)

    def test_corrupt_success_point_and_axis_cannot_forge_certificate(self):
        a, b = box(), box(center=(.25, 0, 0))
        def corrupt(*args, **kwargs):
            return SimpleNamespace(success=True, x=[100, 100, 100, 100],
                                   ineqlin=SimpleNamespace(marginals=np.ones(len(a.equations)+len(b.equations))))
        self.assertEqual(geo.classify(a, b, solver=corrupt)['category'], geo.UNKNOWN)
        self.assertIsNone(geo.point_certificate(a, b, [100, 100, 100]))

    def test_negative_world_unrestricted_bounds(self):
        from scipy.optimize import linprog
        def spy(*args, **kwargs):
            self.assertEqual(kwargs['bounds'], [(None, None)]*4)
            return linprog(*args, **kwargs)
        a, b = box(center=(-10, -20, -30)), box((.1, .1, .1), center=(-10, -20, -30))
        self.assertEqual(geo.classify(a, b, solver=spy)['category'], geo.OVERLAP)

    def test_world_corner_box_contains_rotated_source_vertices(self):
        shape = box((.5, .2, .1))
        rotation = geo.rpy_rotation((.8, -.3, .5))
        translation = np.array([-2, 3, 4])
        lower, upper = geo.world_boxes(shape, rotation[None], translation[None])
        actual = shape.vertices@rotation.T+translation
        self.assertTrue(np.all(actual >= lower[0]))
        self.assertTrue(np.all(actual <= upper[0]))
        q = np.array([[np.cos(.3), 0, 0, np.sin(.3)]])
        np.testing.assert_allclose(geo.rotations(q)[0], geo.rpy_rotation((0, 0, .6)), atol=1e-14)


if __name__ == '__main__':
    unittest.main(verbosity=2)
