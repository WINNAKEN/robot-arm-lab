"""HOST analytic and failure controls; this is not a second Boolean kernel."""
import pathlib
import sys
import unittest

import manifold3d
import numpy as np
import trimesh

sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent))
import solids


def box(name='box', size=2., center=(0, 0, 0), kind='PRINTED_STL'):
    mesh = trimesh.creation.box(extents=[size]*3)
    triangles = mesh.triangles + np.asarray(center)
    return solids.prepare_solid(name, kind, name, triangles)


class SolidTests(unittest.TestCase):
    def test_known_cube_intersection_containment_touching_and_separation(self):
        a = box('a')
        self.assertTrue(a.evidence['valid'])
        self.assertAlmostEqual(a.evidence['triangle_volume_mm3'], 8.)
        for center, expected in [((1, 0, 0), 4.), ((2, 0, 0), 0.), ((3, 0, 0), 0.), ((0, 0, 0), 8.)]:
            with self.subTest(center=center):
                result = solids.compare_pair(a, box('b', center=center), np.eye(4))
                self.assertAlmostEqual(result['volume_mm3'], expected, places=9)
                self.assertEqual(result['category'], solids.PRINTED if expected else solids.ZERO)
        inside = solids.compare_pair(box('outer', 4), a, np.eye(4))
        self.assertAlmostEqual(inside['volume_mm3'], 8.)

    def test_hollow_proxy_overlap_but_inside_hole_has_zero_original_volume(self):
        outer, inner = box('outer', 10), box('inner', 8)
        shell = outer.manifold - inner.manifold
        mesh = shell.to_mesh64()
        hollow = solids.prepare_solid('hollow', 'PRINTED_STL', 'a',
                                     np.asarray(mesh.vert_properties)[:, :3][np.asarray(mesh.tri_verts)])
        self.assertTrue(hollow.evidence['valid'])
        self.assertAlmostEqual(hollow.evidence['triangle_volume_mm3'], 488.)
        result = solids.compare_pair(hollow, box('inside', 2), np.eye(4))
        self.assertEqual(result['boolean_calls'], 1)
        self.assertEqual(result['category'], solids.ZERO)
        self.assertEqual(result['volume_mm3'], 0.)

    def test_rotation_pose_direction_and_metre_to_mm(self):
        a = {'position_m': [1, 2, 3], 'original_orientation_wxyz': [1, 0, 0, 0]}
        b = {'position_m': [1.001, 2, 3], 'original_orientation_wxyz': [np.sqrt(.5), 0, 0, np.sqrt(.5)]}
        t = solids.relative_transform(a, b)
        np.testing.assert_allclose(t[:3, 3], [1, 0, 0], atol=1e-10)
        np.testing.assert_allclose(t[:3, :3] @ [1, 0, 0], [0, 1, 0], atol=1e-14)
        np.testing.assert_allclose(solids.relative_transform(b, a) @ t, np.eye(4), atol=1e-10)
        self.assertAlmostEqual(solids.compare_pair(box('a'), box('b'), t)['volume_mm3'], 4.)
        self.assertEqual(a['original_orientation_wxyz'], [1, 0, 0, 0])

    def test_small_boundary_and_approximate_kind(self):
        for volume in (1e-14, .009, .01):
            self.assertEqual(solids.category(volume, 'PRINTED_STL', 'PRINTED_STL'), solids.SMALL)
        self.assertEqual(solids.category(.0100000001, 'PRINTED_STL', 'PRINTED_STL'), solids.PRINTED)
        for kind in ('PURCHASED_PRIMITIVE', 'CABLE_APPROX'):
            result = solids.compare_pair(box('a'), box('b', kind=kind), np.eye(4))
            self.assertEqual(result['category'], solids.APPROX)
        tiny = solids.compare_pair(box('a', .2), box('b', .2), np.eye(4))
        self.assertGreater(tiny['volume_mm3'], 0)
        self.assertLess(tiny['volume_mm3'], .01)
        self.assertEqual(tiny['category'], solids.SMALL)

    def test_invalid_empty_nonfinite_open_and_reversed_input_never_clean(self):
        a = box('a')
        examples = [np.empty((0, 3, 3)), a.triangles_mm[:-1], a.triangles_mm[:, ::-1],
                    np.full((1, 3, 3), np.nan)]
        for triangles in examples:
            bad = solids.prepare_solid('bad', 'PRINTED_STL', 'b', triangles)
            self.assertFalse(bad.evidence['valid'])
            result = solids.compare_pair(a, bad, np.eye(4))
            self.assertEqual(result['category'], solids.UNKNOWN)
            self.assertIsNone(result['volume_mm3'])

    def test_empty_import_with_NoError_does_not_become_clean(self):
        bad = solids.prepare_solid('bad', 'PRINTED_STL', 'b', box().triangles_mm,
                                   constructor=lambda mesh: manifold3d.Manifold())
        self.assertFalse(bad.evidence['valid'])
        self.assertEqual(solids.compare_pair(box(), bad, np.eye(4))['category'], solids.UNKNOWN)

    def test_import_volume_change_and_boolean_exception_closed(self):
        class DifferentVolume:
            def status(self): return manifold3d.Error.NoError
            def is_empty(self): return False
            def volume(self): return 9.
        bad = solids.prepare_solid('bad', 'PRINTED_STL', 'b', box().triangles_mm, constructor=lambda mesh: DifferentVolume())
        self.assertFalse(bad.evidence['valid'])
        def broken(a, b):
            raise RuntimeError('injected Boolean error')
        result = solids.compare_pair(box('a'), box('b'), np.eye(4), intersection=broken)
        self.assertEqual(result['boolean_calls'], 1)
        self.assertEqual(result['category'], solids.UNKNOWN)
        self.assertIsNone(result['volume_mm3'])

    def test_boolean_error_status_and_nonfinite_result_closed(self):
        class Failed:
            def __init__(self, status, volume): self._status, self._volume = status, volume
            def status(self): return self._status
            def is_empty(self): return True
            def volume(self): return self._volume
        for status, volume in [(manifold3d.Error.NotManifold, 0.), (manifold3d.Error.NoError, float('nan'))]:
            result = solids.compare_pair(box('a'), box('b'), np.eye(4), intersection=lambda a, b: Failed(status, volume))
            self.assertEqual(result['category'], solids.UNKNOWN)
            self.assertIsNone(result['volume_mm3'])

    def test_exact_weld_preserves_triangle_vertices_and_signed_volume(self):
        triangles = box().triangles_mm
        vertices, faces = solids.indexed(triangles)
        self.assertEqual(len(vertices), 8)
        np.testing.assert_array_equal(vertices[faces], triangles)
        self.assertAlmostEqual(solids.triangle_volume(triangles), 8.)
        with self.assertRaises(ValueError): solids.rotation([0, 0, 0, 0])
        with self.assertRaises(ValueError): solids.category(-1, 'PRINTED_STL', 'PRINTED_STL')


if __name__ == '__main__':
    unittest.main(verbosity=2)
