"""042 host-only numerical contracts. Synthetic PASS is not Isaac acceptance."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

try:
    from . import core
except ImportError:
    import core


def source_fixture():
    """Analytic chain: six 1 kg bodies, Ixyz=(1,2,3), 1 m spacing."""
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    bodies = []
    for i, name in enumerate(['Base'] + [f'Link{x}' for x in range(1, 7)]):
        bodies.append({'name': name, 'path': '/' + name, 'position': [i, 0, 0],
                       'rotation': copy.deepcopy(identity), 'mass': 1, 'com': [0, 0, 0],
                       'inertia_diag': [1, 2, 3], 'principal_axes_wxyz': [1, 0, 0, 0]})
    joints = [{'name': f'J{i}', 'type': 'revolute',
               'body0': '/Base' if i == 1 else f'/Link{i - 1}', 'body1': f'/Link{i}',
               'axis': 'Z', 'local_pos0': [1, 0, 0], 'local_rot0_wxyz': [1, 0, 0, 0]}
              for i in range(1, 7)]
    joints.append({'name': 'root_joint', 'type': 'fixed'})
    return {'units': {'meters_per_unit': 1, 'kilograms_per_unit': 1, 'up_axis': 'Z'},
            'bodies': bodies, 'joints': joints}


class ProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.program = core.load_program(Path(__file__).with_name('program.json'))

    def test_complete_timeline_and_integer_step_checkpoint_census(self):
        self.assertEqual(core.total_time(self.program), 56.5)
        schedule = core.segments(self.program)
        self.assertEqual(len(schedule), 28)
        seen = []
        peak = 0
        for index in range(6781):
            point = core.sample(self.program, index / 120)
            peak = max(peak, *map(abs, point['qd_rad_s']))
            if point['checkpoint']:
                seen.append((point['checkpoint'], index / 120))
        self.assertEqual(seen, [(segment['name'], segment['end_s']) for segment in schedule])
        self.assertLessEqual(peak, 0.5)
        self.assertAlmostEqual(peak, math.radians(6.25), places=12)
        self.assertIsNone(core.sample(self.program, 0)['checkpoint'])
        self.assertEqual(core.sample(self.program, 56.5)['q_rad'], [0] * 6)

    def test_positive_negative_and_coordinated_targets_are_si(self):
        schedule = core.segments(self.program)
        for index in range(6):
            for offset, sign in [(1, 1), (3, -1)]:
                point = core.sample(self.program, schedule[4 * index + offset]['end_s'])
                expected = [0] * 6
                expected[index] = math.radians(sign * 5)
                self.assertEqual(point['q_rad'], expected)
                self.assertEqual(point['qd_rad_s'], [0] * 6)
        self.assertEqual(schedule[25]['q1_rad6'], [math.radians(x) for x in [5, -5, 5, 3, -3, 3]])
        self.assertEqual(schedule[26]['q1_rad6'], [-q for q in schedule[25]['q1_rad6']])

    def test_analytic_velocity_matches_finite_difference(self):
        epsilon = 1e-5
        for segment in core.segments(self.program)[1:]:
            for fraction in (0.1, 0.4, 0.8):
                t = segment['start_s'] + fraction * segment['move_s']
                before = core.sample(self.program, t - epsilon)['q_rad']
                after = core.sample(self.program, t + epsilon)['q_rad']
                velocity = core.sample(self.program, t)['qd_rad_s']
                for a, b, v in zip(before, after, velocity):
                    self.assertAlmostEqual((b - a) / (2 * epsilon), v, places=8)

    def test_position_velocity_continuous_at_move_hold_and_next_segment(self):
        for segment in core.segments(self.program):
            boundaries = [segment['start_s'] + segment['move_s'], segment['end_s']]
            for t in boundaries:
                if t <= 0 or t >= 56.5:
                    continue
                left, right = core.sample(self.program, t - 1e-7), core.sample(self.program, t + 1e-7)
                for key in ('q_rad', 'qd_rad_s'):
                    self.assertLess(max(abs(a - b) for a, b in zip(left[key], right[key])), 1e-6)

    def test_checkpoint_is_end_hold_only(self):
        for segment in core.segments(self.program):
            end = segment['end_s']
            self.assertEqual(core.sample(self.program, end + 5e-9)['checkpoint'], segment['name'])
            self.assertIsNone(core.sample(self.program, end - 1e-6)['checkpoint'])

    def test_invalid_times_rejected(self):
        for value in (-1e-9, 56.5001, float('nan'), float('inf'), True, '1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.sample(self.program, value)

    def test_mutated_programs_rejected(self):
        mutations = [lambda p: p.update(extra=True),
                     lambda p: p.update(rate_hz=True),
                     lambda p: p.update(joint_names=list(reversed(p['joint_names']))),
                     lambda p: p['units'].update(position='deg'),
                     lambda p: p['phases'].pop(),
                     lambda p: p['phases'][1].update(move_s=-1),
                     lambda p: p['phases'][1].update(hold_s=0),
                     lambda p: p['phases'][1]['target_rad6'].__setitem__(0, 5),
                     lambda p: p['phases'][1]['target_rad6'].__setitem__(0, float('nan')),
                     lambda p: p['phases'][1].update(extra=0)]
        for mutate in mutations:
            bad = copy.deepcopy(self.program)
            mutate(bad)
            with self.assertRaises(ValueError):
                core.segments(bad)

    def test_duplicate_fields_nonfinite_and_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'program.json'
            for raw in ('{"schema_version":1,"schema_version":1}', '{"x":NaN}'):
                path.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValueError):
                    core.load_program(path)
            with self.assertRaises(FileNotFoundError):
                core.load_program(Path(folder) / 'absent.json')


class GainTests(unittest.TestCase):
    def test_analytic_downstream_parallel_axis_and_gain_values(self):
        observed = core.gains(source_fixture())
        self.assertEqual(observed['i_eff'], [73, 45, 26, 14, 7, 3])
        self.assertEqual(observed['kp'], [4672, 2880, 1664, 896, 448, 192])
        self.assertEqual(observed['kd'], [1168, 720, 416, 224, 112, 48])
        self.assertEqual(observed['effort'], [3, 6, 5, 2, 2, 1])

    def test_principal_frame_and_quaternion_sign_equivalence(self):
        fixture = source_fixture()
        q = [math.sqrt(0.5), 0, math.sqrt(0.5), 0]
        fixture['bodies'][-1]['principal_axes_wxyz'] = q
        actual = core.gains(fixture)
        for value, expected in zip(actual['i_eff'], [71, 43, 24, 12, 5, 1]):
            self.assertAlmostEqual(value, expected)
        fixture['bodies'][-1]['principal_axes_wxyz'] = [-x for x in q]
        self.assertEqual(core.gains(fixture), actual)

    def test_com_is_rotated_from_link_frame(self):
        fixture = source_fixture()
        fixture['bodies'][-1]['com'] = [0.5, 0, 0]
        unrotated = core.gains(fixture)['i_eff'][0]
        fixture['bodies'][-1]['rotation'] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        rotated = core.gains(fixture)['i_eff'][0]
        self.assertEqual(unrotated, 78.25)
        self.assertEqual(rotated, 73.25)

    def test_joint_local_frame_rotates_axis_and_parent_rotates_anchor(self):
        fixture = source_fixture()
        fixture['joints'][5]['local_rot0_wxyz'] = [math.sqrt(0.5), 0, math.sqrt(0.5), 0]
        self.assertAlmostEqual(core.gains(fixture)['i_eff'][-1], 1)
        fixture = source_fixture()
        fixture['bodies'][5]['rotation'] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        self.assertEqual(core.gains(fixture)['i_eff'][-1], 5)

    def test_body_and_joint_order_do_not_determine_mapping(self):
        fixture = source_fixture()
        expected = core.gains(fixture)
        fixture['bodies'].reverse()
        fixture['joints'].reverse()
        self.assertEqual(core.gains(fixture), expected)

    def test_invalid_source_frames_and_mass_rejected(self):
        mutations = [lambda s: s['units'].update(meters_per_unit=0.001),
                     lambda s: s['bodies'].pop(),
                     lambda s: s['bodies'][1].update(name='Base'),
                     lambda s: s['bodies'][1].update(mass=0),
                     lambda s: s['bodies'][1].update(com=[0, float('nan'), 0]),
                     lambda s: s['bodies'][1].update(principal_axes_wxyz=[0, 0, 0, 0]),
                     lambda s: s['bodies'][1].update(rotation=[[-1, 0, 0], [0, 1, 0], [0, 0, 1]]),
                     lambda s: s['bodies'][1].update(inertia_diag=[1, -2, 3]),
                     lambda s: s['joints'][0].update(body0='/Link3'),
                     lambda s: s['joints'][0].update(axis='A'),
                     lambda s: s['joints'][0].update(local_rot0_wxyz=[1, 0, 0]),
                     lambda s: s['joints'][1].update(name='J1')]
        for mutate in mutations:
            bad = source_fixture()
            mutate(bad)
            with self.assertRaises(ValueError):
                core.gains(bad)


class CompletionGateTests(unittest.TestCase):
    """Bound-marker/process contract tests; these are not Isaac executions."""
    def setUp(self):
        try:
            from . import verify
        except ImportError:
            import verify
        self.verify = verify
        self.summary = {'status': 'DATA_CAPTURED', 'kind': 'ACTUAL_PHYSX_DRIVE_TELEMETRY',
            'run_id': 'a'*32, 'pid': 123, 'finished_unix': 150., 'final_before_stop': True,
            'runtime': {'run_id': 'a'*32, 'pid': 123, 'close_protocol': 'OFFICIAL_FAST_SHUTDOWN_EXPLICIT_EXIT'}}
        self.state = {'status': 'DATA_CAPTURED', 'phase': 'CLOSING_APP', 'run_id': 'a'*32,
            'pid': 123, 'runtime': copy.deepcopy(self.summary['runtime']),
            'started_unix': 100., 'summary_sha256': 'b'*64}
        self.process = {'run_id': 'a'*32, 'pid': 123, 'exit_code': 0, 'finished_unix': 160.}

    def call(self):
        return self.verify.completion_gate(self.summary, self.state, self.process, 'b'*64)

    def test_bound_fast_shutdown_and_post_close_paths(self):
        self.assertEqual(self.call(), 'BOUND_PRE_CLOSE_SUMMARY_AND_ACTUAL_EXIT0')
        self.state.update(status='CLOSED', phase='APP_CLOSED', closed_unix=155.)
        self.assertEqual(self.call(), 'POST_CLOSE_MARKER_AND_ACTUAL_EXIT0')

    def test_failed_timeout_incomplete_hash_identity_protocol_and_chronology_rejected(self):
        mutations = [lambda: self.process.update(exit_code=124),
            lambda: self.process.update(exit_code=1),
            lambda: self.process.update(exit_code=False),
            lambda: self.state.update(status='FAILED'),
            lambda: self.state.update(status='BUILDING'),
            lambda: self.state.update(phase='FINITE_DRIVE_SEQUENCE'),
            lambda: self.state.update(summary_sha256='c'*64),
            lambda: self.process.update(run_id='c'*32),
            lambda: self.process.update(pid=124),
            lambda: self.summary['runtime'].update(close_protocol='UNKNOWN'),
            lambda: self.state['runtime'].update(pid=124),
            lambda: self.summary.update(final_before_stop=False),
            lambda: self.summary.update(status='FAILED'),
            lambda: self.process.update(finished_unix=701.),
            lambda: self.process.update(finished_unix=149.)]
        for index in range(len(mutations)):
            self.setUp()
            with self.subTest(mutation=index):
                mutations[index]()
                with self.assertRaises(ValueError):
                    self.call()

    def test_post_close_time_is_required_and_ordered(self):
        self.state.update(status='CLOSED', phase='APP_CLOSED', closed_unix=149.)
        with self.assertRaises(ValueError):
            self.call()
        self.state['closed_unix'] = 161.
        with self.assertRaises(ValueError):
            self.call()


class TelemetryConsumerTests(unittest.TestCase):
    """Synthetic oracle probes only; no report or runtime acceptance is published."""
    @classmethod
    def setUpClass(cls):
        try:
            from . import verify
        except ImportError:
            import verify
        cls.verify = verify
        cls.root = Path(__file__).resolve().parents[3]
        (cls.reference_module, cls.reference, cls.frames, cls.layout,
         cls.core, cls.program) = verify.context(cls.root)
        source = (cls.root/'outputs/isaac-import-v1/runs/1c559d361bc24e50b90efa1d15518b28'
                  '/retrieved/1c559d361bc24e50b90efa1d15518b28/snapshot.json')
        raw = source.read_text(encoding='utf-8')
        s = json.loads(raw.replace('/robot_arm_lab_v2_simulation_draft', '/World/Robot'))
        s['default_prim'] = '/World'
        s['root_placement'] = {'path': '/World', 'position': [0., 0., 0.], 'rotation': verify.IDENTITY}
        s['robot_root'] = {**s['root_placement'], 'path': '/World/Robot'}
        s['configuration'] = {'engine': 'physx', 'device': 'cpu', 'gravity': [0., 0., 0.],
                              'frequency_hz': 120., 'self_collisions': False}
        s['dof_names'], s['gains'] = verify.JOINTS[:], core.gains(s)
        s['actual_drives'] = {k: s['gains'][k][:] for k in ('kp', 'kd', 'effort')}
        s['actual_drives']['types'] = ['force']*6
        s['runtime_masses'] = []
        for b in s['bodies']:
            r = verify.quaternion(b['principal_axes_wxyz'])
            d = [[b['inertia_diag'][i] if i == j else 0. for j in range(3)] for i in range(3)]
            s['runtime_masses'].append({'name': b['name'], 'mass': b['mass'], 'com': b['com'],
                'principal_axes_wxyz': b['principal_axes_wxyz'],
                'inertia_link_about_com': verify.mm(verify.mm(r, d), verify.transpose(r))})
        assumptions = verify.read_json(cls.root/verify.SOURCES['source-assumptions.json'])
        paths = {b['name']: b['path'] for b in s['bodies']}
        s['colliders'] = [{'path': paths[b['link']]+'/assumed_aabb_proxy',
            'body_path': paths[b['link']], 'enabled': False, 'size': 1.,
            'local_position': b['com_m'],
            'local_basis': [[b['box_size_m'][i] if i == j else 0. for j in range(3)] for i in range(3)]}
            for b in assumptions['links']]
        s['baseline_step'], s['baseline_time_s'] = 3, 3/120
        cls.static = s

    @staticmethod
    def quaternion(r):
        return [math.sqrt(max(0., 1+r[0][0]+r[1][1]+r[2][2]))/2,
                math.copysign(math.sqrt(max(0., 1+r[0][0]-r[1][1]-r[2][2]))/2, r[2][1]-r[1][2]),
                math.copysign(math.sqrt(max(0., 1-r[0][0]+r[1][1]-r[2][2]))/2, r[0][2]-r[2][0]),
                math.copysign(math.sqrt(max(0., 1-r[0][0]-r[1][1]+r[2][2]))/2, r[1][0]-r[0][1])]

    def records(self, mutate=None):
        for i in range(6781):
            c = core.sample(self.program, i/120)
            fk = self.frames.fk(self.layout, c['q_rad'])
            value = {'index': i, 'schedule_time_s': i/120, 'segment': c['segment'],
                'checkpoint': c['checkpoint'], 'target_q_rad': c['q_rad'][:],
                'target_qd_rad_s': c['qd_rad_s'][:], 'q_rad': c['q_rad'][:], 'qd_rad_s': c['qd_rad_s'][:],
                'timeline_paused': True, 'links': [{'name': 'Base', 'position': [0., 0., 0.],
                'orientation_wxyz': [1., 0., 0., 0.]}] + [{'name': f'Link{j}',
                'position': list(v['origin_m']), 'orientation_wxyz': self.quaternion(v['rotation_world'])}
                for j, v in enumerate(fk, 1)], 'clock': {'step_before': 3+max(0, i-1), 'step_after': 3+i,
                'time_before_s': (3+max(0, i-1))/120, 'time_after_s': (3+i)/120,
                'callback_count': i, 'callback_time_s': i*self.verify.CALLBACK_DT,
                'read_step_before': 3+i, 'read_step_after': 3+i}}
            if mutate:
                mutate(i, value)
            yield value

    def compare(self, values):
        return self.verify.compare_samples(self.static, values, self.program, self.frames, self.layout, core)

    def test_all_synthetic_frames_and_clock_are_host_checks_only(self):
        self.verify.validate_static(self.static, self.reference_module, self.reference, core, self.root)
        result = self.compare(self.records())
        self.assertEqual(result['status'], 'HOST_DATA_CHECKS_ONLY')
        self.assertEqual((result['sample_count'], len(result['checkpoints'])), (6781, 28))

    def test_quaternion_sign_is_not_a_frame_error(self):
        def negate(i, row):
            for link in row['links']:
                link['orientation_wxyz'] = [-v for v in link['orientation_wxyz']]
        self.assertEqual(self.compare(self.records(negate))['status'], 'HOST_DATA_CHECKS_ONLY')

    def test_float32_callback_representation_rejects_double_stale_and_drift(self):
        # The observed 6780-step representation difference is about 2.947us;
        # it is expected quantization, not a physics time/count deviation.
        self.assertAlmostEqual(6780*(self.verify.CALLBACK_DT-self.verify.DT),
                               2.946704626867469e-6, places=15)
        def at(index, action):
            return lambda i, row: action(row) if i == index else None
        mutations = [at(10, lambda r: r['clock'].update(callback_time_s=10/120)),
            at(1, lambda r: r['clock'].update(callback_time_s=0.)),
            at(1, lambda r: r['clock'].update(callback_time_s=self.verify.CALLBACK_DT+2e-9)),
            at(1, lambda r: r['clock'].update(time_after_s=r['clock']['time_after_s']+2e-6))]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                with self.assertRaises(ValueError):
                    self.compare(self.records(mutate))

    def test_static_frames_and_runtime_property_mutations_rejected(self):
        mutations = [lambda s: s['root_placement']['position'].__setitem__(0, .1),
            lambda s: s['dof_names'].__setitem__(0, 'J2'),
            lambda s: s['colliders'][0].update(enabled=True),
            lambda s: s['colliders'][0]['local_basis'][0].__setitem__(0, .5),
            lambda s: s['runtime_masses'][1]['com'].__setitem__(0, .1),
            lambda s: s['runtime_masses'][1]['inertia_link_about_com'][0].__setitem__(0, .1),
            lambda s: s['actual_drives']['effort'].__setitem__(0, 300.),
            lambda s: s['actual_drives']['types'].__setitem__(0, 'acceleration'),
            lambda s: next(j for j in s['joints'] if j['type'] == 'fixed').update(local_pos0=[.1, 0., 0.])]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                bad = copy.deepcopy(self.static)
                mutate(bad)
                with self.assertRaises(ValueError):
                    self.verify.validate_static(bad, self.reference_module, self.reference, core, self.root)

    def test_dynamic_sign_units_echo_stale_clock_and_missing_checkpoint_rejected(self):
        zero_links = next(self.records())['links']
        def at(index, action):
            return lambda i, row: action(row) if i == index else None
        mutations = [at(1, lambda r: r['clock'].update(read_step_after=5)),
            at(1, lambda r: r['clock'].update(callback_count=0)),
            at(1, lambda r: r['clock'].update(time_after_s=r['clock']['time_before_s'])),
            at(1, lambda r: r.update(timeline_paused=False)),
            at(360, lambda r: r.update(checkpoint=None)),
            at(360, lambda r: r['q_rad'].__setitem__(0, -r['q_rad'][0])),
            at(360, lambda r: r['q_rad'].__setitem__(0, math.degrees(r['q_rad'][0]))),
            at(360, lambda r: r.update(q_rad=[0., r['q_rad'][0], 0., 0., 0., 0.])),
            at(360, lambda r: r.update(links=copy.deepcopy(zero_links))),
            at(1, lambda r: r['links'][1]['position'].__setitem__(2, .9))]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                with self.assertRaises(ValueError):
                    self.compare(self.records(mutate))
        with self.assertRaises(ValueError):
            self.compare(row for row in self.records() if row['index'] != 2)

    def test_missing_run_fails_before_simulator_or_reference_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                self.verify.verify_run(Path(temporary), self.root)


if __name__ == '__main__':
    unittest.main()
