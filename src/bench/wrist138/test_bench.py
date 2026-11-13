"""HOST controls: real CLI, native frames and actual firmware main.c with SDK seams."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('wrist138_bench_tested', HERE / 'bench.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
P = B.P
TEMPLATE = json.loads((HERE / 'profile.template.json').read_bytes())
FIXTURE = ROOT / 'outputs/wrist-bench-prep-138/author' / ('host-fixtures-' + uuid.uuid4().hex)
FIXTURE.mkdir(parents=True, exist_ok=False)


def synthetic_profile():
    p = copy.deepcopy(TEMPLATE)
    p['controller'].update(product='SYNTHETIC TEST FIXTURE', revision='SYNTHETIC')
    for key in B.TRUE_CONTROLLER: p['controller'][key] = True
    p['power'].update(voltage_v=12, current_limit_a=0.5, fuse_rating_a=1)
    for key in B.TRUE_POWER: p['power'][key] = True
    for index, item in enumerate(p['axes'].values(), 1):
        item.update(driver_model='SYNTHETIC SERVO42D RS485', fw_version='fixture', hw_version='fixture',
                    motor_model='SYNTHETIC', transport='RS485', protocol='MKS_NATIVE_FA_FB',
                    node_id=index, baud=38400, uart_format='8N1', mode='SR_CLOSE',
                    microsteps=16, motor_step_angle_deg=1.8, motor_rated_current_a=1,
                    configured_current_a=0.5, gear_ratio=27, command0_motor_sign=1,
                    output_sign_from_motor=-1, encoder_sign_from_motor=1, clearance_positive_motor_deg=5,
                    clearance_negative_motor_deg=5, max_test_motor_rpm=5)
        for key in B.TRUE_AXIS: item[key] = True
    p['axes']['GRIPPER'].update(pinion_radius_mm=13.5, pinion_radius_verified=True)
    p['status'] = 'SYNTHETIC_HOST_FIXTURE_NOT_PHYSICAL'
    return p


def reply(node, code, value, size):
    raw = bytes([0xFB, node, code]) + value.to_bytes(size, 'big', signed=code in (0x31, 0x32))
    return raw + bytes([sum(raw) & 255])


class ProtocolTests(unittest.TestCase):
    def test_exact_queries_and_boundaries(self):
        self.assertEqual(P.query(1, 0x31).hex(), 'fa01312c')
        self.assertEqual(P.query(1, 0x32).hex(), 'fa01322d')
        self.assertEqual(P.query(1, 0xF1).hex(), 'fa01f1ec')
        self.assertEqual(P.query(1, 0x3A).hex(), 'fa013a35')
        for addr in (0, 256, -1, True, 1.0):
            with self.assertRaises(ValueError): P.query(addr, 0x31)
        for code in (0xFD, 0xF3, 0xF7, 0x80, True):
            with self.assertRaises(ValueError): P.query(1, code)

    def test_signed_big_endian(self):
        for value in (-(1 << 47), -16384, -1, 0, 1, (1 << 47) - 1):
            self.assertEqual(P.decode(1, 0x31, reply(1, 0x31, value, 6))['encoder_counts'], value)
        for value in (-32768, -1, 0, 32767):
            self.assertEqual(P.decode(255, 0x32, reply(255, 0x32, value, 2))['motor_rpm'], value)

    def test_exact_reply_identity_length_checksum_and_status(self):
        raw = reply(1, 0x31, -1, 6)
        for bad in (raw[:-1], raw + b'\x00', bytes([0xFA]) + raw[1:],
                    reply(2, 0x31, -1, 6), raw[:-1] + bytes([raw[-1] ^ 1])):
            with self.assertRaises(ValueError): P.decode(1, 0x31, bad)
        for value in (0, 7, 255):
            with self.assertRaises(ValueError): P.decode(1, 0xF1, reply(1, 0xF1, value, 1))
        self.assertEqual(P.decode(1, 0xF1, reply(1, 0xF1, 1, 1))['run_state'], 'stopped')
        self.assertFalse(P.decode(1, 0x3A, reply(1, 0x3A, 0, 1))['enabled'])
        with self.assertRaises(ValueError): P.decode(1, 0x3A, reply(1, 0x3A, 2, 1))


class PlannerTests(unittest.TestCase):
    def test_all_unknown_blocks_every_axis_without_fd(self):
        for axis in B.AXES:
            r = B.jog_plan(TEMPLATE, axis, 1)
            self.assertEqual(r['status'], 'BLOCKED')
            self.assertGreater(len(r['missing_or_invalid']), 35)
            self.assertNotIn('frame_hex', r)
            self.assertFalse(r['hardware_approved'])

    def test_invalid_profile_sections_are_controlled(self):
        for group in ('axes', 'power', 'controller'):
            for value in (None, [], 7, True, 'bad'):
                p = synthetic_profile(); p[group] = value
                self.assertEqual(B.jog_plan(p, 'J5', 1)['status'], 'BLOCKED')
        for value in (None, [], 7, True, 'bad'):
            p = synthetic_profile(); p['axes']['J5'] = value
            self.assertEqual(B.jog_plan(p, 'J5', 1)['status'], 'BLOCKED')

    def test_profile_bool_nonfinite_wrong_settings_and_each_required_fact(self):
        p = synthetic_profile()
        for group, keys in [('controller', B.TRUE_CONTROLLER), ('power', B.TRUE_POWER)]:
            for key in keys:
                q = copy.deepcopy(p); q[group][key] = None
                self.assertEqual(B.jog_plan(q, 'J5', 1)['status'], 'BLOCKED')
        for key in B.TRUE_AXIS:
            q = copy.deepcopy(p); q['axes']['J5'][key] = 1
            self.assertEqual(B.jog_plan(q, 'J5', 1)['status'], 'BLOCKED')
        for key, value in [('gear_ratio', 0), ('microsteps', True), ('motor_step_angle_deg', math.nan),
                           ('mode', 'CR_vFOC'), ('transport', 'CAN'), ('protocol', 'MODBUS_RTU'),
                           ('node_id', 0), ('command0_motor_sign', True), ('configured_current_a', 2)]:
            q = copy.deepcopy(p); q['axes']['J5'][key] = value
            self.assertEqual(B.jog_plan(q, 'J5', 1)['status'], 'BLOCKED')

    def test_nonfinite_boolean_amount_rpm_acceleration(self):
        for amount in (False, True, math.nan, math.inf, -math.inf, 0):
            with self.assertRaises(ValueError): B.jog_plan(synthetic_profile(), 'J5', amount)
        for rpm in (True, 0, 6, 1.0):
            with self.assertRaises(ValueError): B.jog_plan(synthetic_profile(), 'J5', 1, rpm=rpm)
        for acc in (True, 0, 256):
            with self.assertRaises(ValueError): B.jog_plan(synthetic_profile(), 'J5', 1, acceleration=acc)

    def test_real_finite_move_bytes_and_rounding(self):
        p = synthetic_profile(); r = B.jog_plan(p, 'J5', 4.95, rpm=5, acceleration=2)
        self.assertEqual(r['pulses'], 44)
        self.assertEqual(r['frame_hex'], 'FA 01 FD 00 05 02 00 00 00 2C 2B')
        self.assertAlmostEqual(r['actual_motor_deg'], 4.95)
        self.assertFalse(r['auto_retry']); self.assertFalse(r['auto_enable'])
        self.assertEqual(r['transmitted_frames'], 0)
        q = copy.deepcopy(p); q['axes']['J5']['microsteps'] = 5
        with self.assertRaisesRegex(ValueError, 'Rounded'): B.jog_plan(q, 'J5', 5)
        with self.assertRaises(ValueError): B.jog_plan(p, 'J5', 0.001)
        q = copy.deepcopy(p); q['axes']['J5']['clearance_positive_motor_deg'] = 0.9
        with self.assertRaises(ValueError): B.jog_plan(q, 'J5', 1)

    def test_output_unit_sign_limits_and_single_jaw_gap(self):
        p = synthetic_profile()
        with self.assertRaisesRegex(ValueError, 'MOTOR'): B.jog_plan(p, 'J6', 1, 'output_deg')
        r = B.jog_plan(p, 'J6', 0.1, 'output_deg')
        self.assertLess(r['actual_motor_deg'], 0); self.assertGreater(r['actual_output_deg'], 0)
        r = B.jog_plan(p, 'GRIPPER', 0.02, 'rack_mm')
        self.assertAlmostEqual(r['gap_change_mm'], 2 * r['one_jaw_rack_travel_mm'])
        p['axes']['GRIPPER']['pinion_radius_verified'] = None
        self.assertEqual(B.jog_plan(p, 'GRIPPER', 0.02, 'rack_mm')['status'], 'BLOCKED')
        self.assertEqual(B.jog_plan(p, 'J5', 0.02, 'rack_mm')['status'], 'BLOCKED')


class CLITests(unittest.TestCase):
    def call(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', str(HERE / 'bench.py'), *args],
                              cwd=ROOT, capture_output=True, timeout=15)

    def test_actual_status_read_and_synthetic_demo(self):
        for args in [('status',), ('demo',), ('read-plan', '--axis', 'J5', '--address', '1')]:
            r = self.call(*args); self.assertEqual(r.returncode, 0, r.stderr)
            v = json.loads(r.stdout); self.assertTrue(v['offline_only']); self.assertEqual(v['transmitted_frames'], 0)
        self.assertTrue(json.loads(self.call('demo').stdout)['synthetic'])
        self.assertEqual(self.call('read-plan', '--axis', 'J5', '--address', '0').returncode, 2)
        self.assertEqual(self.call('--port', 'COM1', 'status').returncode, 2)

    def test_actual_jog_blocked_and_positive_fixture(self):
        r = self.call('jog-plan', '--axis', 'J5', '--amount', '1')
        self.assertEqual(r.returncode, 3); self.assertNotIn('frame_hex', json.loads(r.stdout))
        profile = FIXTURE / 'synthetic-profile.json'; profile.write_text(json.dumps(synthetic_profile()), encoding='utf-8')
        r = self.call('--profile', str(profile), 'jog-plan', '--axis', 'J6', '--amount', '-1')
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(json.loads(r.stdout)['status'], 'DRY_PLAN_ONLY')
        r = self.call('jog-plan', '--axis', 'J5', '--amount', 'nan')
        self.assertEqual(r.returncode, 2); self.assertEqual(json.loads(r.stderr)['status'], 'ERROR')

    def test_actual_invalid_sections_no_traceback(self):
        for index, (group, value) in enumerate([(g, x)for g in ('axes', 'controller', 'power')for x in (None, [])] + [('axis', None), ('axis', [])]):
            p = synthetic_profile()
            if group == 'axis': p['axes']['J5'] = value
            else: p[group] = value
            path = FIXTURE / f'invalid-{index}.json'; path.write_text(json.dumps(p), encoding='utf-8')
            r = self.call('--profile', str(path), 'jog-plan', '--axis', 'J5', '--amount', '1')
            self.assertEqual(r.returncode, 3, r.stderr); self.assertEqual(json.loads(r.stdout)['status'], 'BLOCKED')
            self.assertNotIn(b'Traceback', r.stderr)

    def test_decode_cli_strict_and_nonfinite_json(self):
        r = self.call('decode', '--address', '1', '--code', '32', '--hex', 'FB 01 32 FF FE 2B')
        self.assertEqual(r.returncode, 0); self.assertEqual(json.loads(r.stdout)['decoded']['motor_rpm'], -2)
        self.assertEqual(self.call('decode', '--address', '1', '--code', '32', '--hex', 'FB 01 32 FF FE 2B 00').returncode, 2)
        for i, raw in enumerate(['{"schema":1,"schema":2}', '{"value":NaN}']):
            p = FIXTURE / f'json-{i}.json'; p.write_text(raw, encoding='utf-8')
            r = self.call('--profile', str(p), 'status')
            self.assertEqual(r.returncode, 2); self.assertNotIn(b'Traceback', r.stderr)

    def test_profile_path_and_size_bound_before_parse(self):
        r = self.call('--profile', str(ROOT / '..' / 'DEV_PRINCIPLES.md'), 'status')
        self.assertEqual(r.returncode, 2)
        self.assertIn('inside this repository', json.loads(r.stderr)['error'])
        oversized = FIXTURE / 'oversized.json'; oversized.write_bytes(b' ' * 65537)
        r = self.call('--profile', str(oversized), 'status')
        self.assertEqual(r.returncode, 2)
        self.assertIn('64 KiB', json.loads(r.stderr)['error'])

    def test_huge_integer_numeric_fields_and_arguments_are_controlled(self):
        baseline = synthetic_profile()
        fields = [('power', None, key) for key, value in baseline['power'].items()
                  if type(value) in (int, float)]
        fields += [('axis', axis, key) for axis, item in baseline['axes'].items()
                   for key, value in item.items() if type(value) in (int, float)]
        records = []
        for index, (section, axis, key) in enumerate(fields):
            for sign in (-1, 1):
                p = copy.deepcopy(baseline)
                selected = axis or 'J5'
                target = p['power'] if section == 'power' else p['axes'][axis]
                target[key] = sign * 10**500
                file = FIXTURE / f'huge-{index}-{sign}.json'
                file.write_text(json.dumps(p), encoding='utf-8')
                self.assertLess(file.stat().st_size, 65536)
                status = self.call('--profile', str(file), 'status')
                self.assertEqual(status.returncode, 0, status.stderr)
                state = json.loads(status.stdout)
                self.assertEqual(state['axes'][selected]['jog_plan'], 'BLOCKED')
                result = self.call('--profile', str(file), 'jog-plan', '--axis', selected, '--amount', '1')
                self.assertEqual(result.returncode, 3, result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'BLOCKED')
                self.assertNotIn('frame_hex', value)
                self.assertEqual(value['transmitted_frames'], 0)
                self.assertNotIn(b'Traceback', status.stderr + result.stderr)
                records.append({'field': [section, axis, key], 'sign': sign,
                                'status_exit': 0, 'jog_exit': 3, 'FD_payload_emitted': False})
        profile = FIXTURE / 'huge-args-synthetic-profile.json'
        profile.write_text(json.dumps(baseline), encoding='utf-8')
        for name in ('amount', 'rpm', 'acceleration'):
            for sign in (-1, 1):
                args = ['--profile', str(profile), 'jog-plan', '--axis', 'J5', '--amount', '1']
                if name == 'amount': args[-1] = str(sign * 10**500)
                else: args += ['--' + name, str(sign * 10**500)]
                result = self.call(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                value = json.loads(result.stderr)
                self.assertEqual(value['status'], 'ERROR')
                self.assertNotIn('frame_hex', value)
                self.assertNotIn(b'Traceback', result.stderr)
        for sign in (-1, 1):
            with self.assertRaises(ValueError): B.jog_plan(baseline, 'J5', sign * 10**500)
        (FIXTURE / 'huge-number-regression-results.json').write_text(
            json.dumps({'numeric_profile_fields': len(fields), 'actual_CLI_cases': len(records) * 2 + 6,
                        'field_cases': records, 'argument_cases': 6, 'physical_tests': 'NOT_RUN'}, indent=2)+'\n',
            encoding='utf-8')

    def test_deep_json_profiles_are_controlled_without_fd(self):
        records = []
        for depth in (2000, 5000, 30000):
            file = FIXTURE / f'deep-json-{depth}.json'
            raw = ('{"x":' + '[' * depth + '0' + ']' * depth + '}').encode('ascii')
            file.write_bytes(raw)
            self.assertLess(len(raw), 65536)
            result = self.call('--profile', str(file), 'status')
            self.assertIn(result.returncode, (0, 2))
            if depth >= 5000: self.assertEqual(result.returncode, 2)
            value = json.loads(result.stderr if result.returncode else result.stdout)
            self.assertEqual(value['transmitted_frames'], 0)
            self.assertNotIn('frame_hex', value)
            self.assertNotIn(b'Traceback', result.stderr)
            records.append({'depth': depth, 'input_bytes': len(raw), 'exit': result.returncode,
                            'stdout': result.stdout.decode(), 'stderr': result.stderr.decode()})
        shallow = self.call('status')
        self.assertEqual(shallow.returncode, 0)
        self.assertEqual(json.loads(shallow.stdout)['transmitted_frames'], 0)
        (FIXTURE / 'deep-json-regression-results.json').write_text(
            json.dumps({'deep_cases': records, 'normal_template_exit': 0,
                        'class_and_closure': 'NONAUTHOR_EXCLUSIVE'}, indent=2)+'\n', encoding='utf-8')


class BehavioralMutationTests(unittest.TestCase):
    def test_exact_original_deep_json_bug_restored(self):
        source = (HERE / 'bench.py').read_text(encoding='utf-8')
        old = 'except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:'
        original = 'except (ValueError, OSError, KeyError, TypeError) as exc:'
        self.assertEqual(source.count(old), 1)
        folder = FIXTURE / 'exact_original_deep_json_bug'; folder.mkdir()
        file = folder / 'bench.py'; file.write_text(source.replace(old, original, 1), encoding='utf-8')
        (folder / 'protocol.py').write_bytes((HERE / 'protocol.py').read_bytes())
        case = folder / 'profile.json'; case.write_text('{"x":' + '[' * 5000 + '0' + ']' * 5000 + '}', encoding='ascii')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', str(file),
                                 '--profile', str(case), 'status'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'RecursionError:', result.stderr)
        self.assertEqual(result.stdout, b'')
        control = subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', str(HERE / 'bench.py'),
                                  '--profile', str(case), 'status'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(control.returncode, 2, control.stderr)
        self.assertEqual(json.loads(control.stderr)['status'], 'ERROR')
        self.assertNotIn(b'Traceback', control.stderr)
        record = {'case': 'exact original uncaught deep JSON recursion restored',
                  'mutant_exit': result.returncode, 'mutant_stdout': result.stdout.decode(),
                  'mutant_stderr': result.stderr.decode(), 'control_exit': control.returncode,
                  'control_stderr': control.stderr.decode(), 'detected': True,
                  'mutant_sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                  'class_and_closure': 'NONAUTHOR_EXCLUSIVE'}
        (FIXTURE / 'deep-json-exact-restoration.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

    def test_exact_original_huge_integer_bug_restored(self):
        source = (HERE / 'bench.py').read_text(encoding='utf-8')
        old = "if type(v) not in (int, float) or not lo <= v <= hi:\n        return False\n    return type(v) is int or math.isfinite(v)"
        original_bug = "return type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi"
        self.assertEqual(source.count(old), 1)
        folder = FIXTURE / 'exact_original_huge_integer_bug'; folder.mkdir()
        file = folder / 'bench.py'; file.write_text(source.replace(old, original_bug, 1), encoding='utf-8')
        (folder / 'protocol.py').write_bytes((HERE / 'protocol.py').read_bytes())
        profile = synthetic_profile(); profile['power']['voltage_v'] = 10**500
        case = folder / 'profile.json'; case.write_text(json.dumps(profile), encoding='utf-8')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', str(file),
                                 '--profile', str(case), 'status'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'OverflowError: int too large to convert to float', result.stderr)
        self.assertEqual(result.stdout, b'')
        control = subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', str(HERE / 'bench.py'),
                                  '--profile', str(case), 'status'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertEqual(json.loads(control.stdout)['axes']['J5']['jog_plan'], 'BLOCKED')
        record = {'case': 'exact original huge integer bug restored', 'mutant_exit': result.returncode,
                  'mutant_stdout': result.stdout.decode(), 'mutant_stderr': result.stderr.decode(),
                  'control_exit': control.returncode, 'control_status': 'PREPARED_NOT_RUN_JOG_BLOCKED',
                  'mutant_sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                  'detected': True, 'class_and_closure': 'NONAUTHOR_EXCLUSIVE'}
        (FIXTURE / 'huge-number-exact-restoration.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

    def test_actual_offline_planner_mutants_detected(self):
        source = (HERE / 'bench.py').read_text(encoding='utf-8')
        mutations = [
            ('rounded_motor_limit_removed',
             "if abs(actual_motor) > min(5, clearance) or rpm > item['max_test_motor_rpm']:",
             "if rpm > item['max_test_motor_rpm']:"),
            ('exact_original_axes_null_bug_restored',
             "axes = profile.get('axes') if isinstance(profile, dict) else None\n    item = axes.get(axis) if isinstance(axes, dict) else None\n    item = item if isinstance(item, dict) else {}",
             "item = profile.get('axes', {}).get(axis, {}) if isinstance(profile, dict) else {}"),
        ]
        records = []
        for name, old, new in mutations:
            self.assertEqual(source.count(old), 1)
            changed = source.replace(old, new, 1)
            folder = FIXTURE / name; folder.mkdir()
            file = folder / 'bench.py'; file.write_text(changed, encoding='utf-8')
            (folder / 'protocol.py').write_bytes((HERE / 'protocol.py').read_bytes())
            spec = importlib.util.spec_from_file_location(name, file)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            p = synthetic_profile()
            if name == 'rounded_motor_limit_removed':
                p['axes']['J5']['microsteps'] = 5
                with self.assertRaisesRegex(ValueError, 'Rounded'): B.jog_plan(p, 'J5', 5)
                result = m.jog_plan(p, 'J5', 5)
                self.assertEqual(result['status'], 'DRY_PLAN_ONLY')
                self.assertGreater(result['actual_motor_deg'], 5)
                observed = {'status': result['status'], 'actual_motor_deg': result['actual_motor_deg']}
            else:
                p['axes'] = None
                self.assertEqual(B.jog_plan(p, 'J5', 1)['status'], 'BLOCKED')
                with self.assertRaises(AttributeError): m.jog_plan(p, 'J5', 1)
                observed = {'exception': 'AttributeError', 'exact_original_bug_restored': True}
            records.append({'name': name, 'detected': True, 'observed': observed,
                            'mutant_sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        (FIXTURE / 'python-mutation-results.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')


STUB_HEADER = r'''
#ifndef WRIST138_TEST_STUB_H
#define WRIST138_TEST_STUB_H
#include <stddef.h>
#include <stdint.h>
#define ESP_OK 0
#define UART_NUM_1 1
#define UART_DATA_8_BITS 8
#define UART_PARITY_DISABLE 0
#define UART_STOP_BITS_1 1
#define UART_HW_FLOWCTRL_DISABLE 0
#define UART_SCLK_DEFAULT 0
#define UART_PIN_NO_CHANGE -1
#define UART_MODE_RS485_HALF_DUPLEX 2
#define pdMS_TO_TICKS(x) (x)
typedef struct {int baud_rate,data_bits,parity,stop_bits,flow_ctrl,source_clk;} uart_config_t;
typedef struct {int tx_buffer_size,rx_buffer_size;} usb_serial_jtag_driver_config_t;
int uart_flush_input(int p);
int uart_write_bytes(int p,const void *v,size_t n);
int uart_wait_tx_done(int p,unsigned t);
int uart_read_bytes(int p,void *v,unsigned n,unsigned t);
int uart_driver_install(int p,int r,int t,int q,void *o,int f);
int uart_param_config(int p,const uart_config_t *c);
int uart_set_pin(int p,int tx,int rx,int rts,int cts);
int uart_set_mode(int p,int m);
int uart_driver_delete(int p);
int usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t *c);
void usb_serial_jtag_driver_uninstall(void);
int usb_serial_jtag_write_bytes(const void *p,size_t n,unsigned t);
int usb_serial_jtag_read_bytes(void *p,size_t n,unsigned t);
int64_t esp_timer_get_time(void);
#endif
'''

SHIM = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "PRODUCT_MAIN"
static uint8_t response[12], written[4];
static size_t response_n,response_pos;
static int writes,usb_installs,uart_installs,mode_calls,pin_calls,chunk=11,tx_return=4,rx_error;
static int64_t now_us;
static const char *usb_input="";
static size_t usb_pos;
static char output[16384]; static size_t output_n;
int uart_flush_input(int p){assert(p==1);return 0;}
int uart_write_bytes(int p,const void *v,size_t n){assert(p==1&&n==4);++writes;memcpy(written,v,4);return tx_return;}
int uart_wait_tx_done(int p,unsigned t){assert(p==1&&t==100);return 0;}
int uart_read_bytes(int p,void *v,unsigned n,unsigned t){assert(p==1);if(rx_error)return -1;if(response_pos==response_n){now_us+=(int64_t)t*1000;return 0;}size_t k=response_n-response_pos;if(k>n)k=n;if(k>(size_t)chunk)k=(size_t)chunk;memcpy(v,response+response_pos,k);response_pos+=k;now_us+=100;return(int)k;}
int uart_driver_install(int p,int r,int t,int q,void *o,int f){assert(p==1&&r==256&&t==0&&q==0&&o==NULL&&f==0);++uart_installs;return 0;}
int uart_param_config(int p,const uart_config_t *c){assert(p==1&&c->baud_rate==38400&&c->data_bits==8&&c->parity==0&&c->stop_bits==1);return 0;}
int uart_set_pin(int p,int tx,int rx,int rts,int cts){assert(p==1&&tx==17&&rx==18&&rts==21&&cts==-1);++pin_calls;return 0;}
int uart_set_mode(int p,int m){assert(p==1&&m==UART_MODE_RS485_HALF_DUPLEX);++mode_calls;return 0;}
int uart_driver_delete(int p){assert(p==1);return 0;}
int usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t *c){assert(c->tx_buffer_size==512&&c->rx_buffer_size==512);++usb_installs;return 0;}
void usb_serial_jtag_driver_uninstall(void){}
int usb_serial_jtag_write_bytes(const void *p,size_t n,unsigned t){(void)t;assert(output_n+n<sizeof output);memcpy(output+output_n,p,n);output_n+=n;output[output_n]=0;return(int)n;}
int usb_serial_jtag_read_bytes(void *p,size_t n,unsigned t){(void)t;assert(n==1);if(!usb_input[usb_pos])return -1;*(char*)p=usb_input[usb_pos++];return 1;}
int64_t esp_timer_get_time(void){return now_us++;}
static void setup(unsigned code,unsigned node){response[0]=0xFB;response[1]=(uint8_t)node;response[2]=(uint8_t)code;response_n=code==0x31?10:code==0x32?6:5;for(size_t i=3;i<response_n-1;i++)response[i]=0;response[3]=code==0xF1?1:0;unsigned s=0;for(size_t i=0;i<response_n-1;i++)s+=response[i];response[response_n-1]=(uint8_t)s;response_pos=0;output_n=0;output[0]=0;writes=0;now_us=0;chunk=11;tx_return=4;rx_error=0;}
static void feed(LineState *line,const char *s,int64_t t){for(size_t i=0;s[i];i++)feed_byte(line,(uint8_t)s[i],t+(int64_t)i);}
int main(void){
 setup(0x31,1);app_main();
#if WRIST138_HARDWARE_PERMIT==0
 assert(writes==0&&usb_installs==0&&uart_installs==0&&mode_calls==0&&pin_calls==0);puts("DEFAULT_APP_EXPLICIT_IO_ZERO");
#else
 assert(writes==0&&usb_installs==1&&uart_installs==1&&mode_calls==1&&pin_calls==1);puts("ENABLED_APP_NO_STARTUP_TX");
 setup(0x31,1);usb_input="READ 1 31\n";usb_pos=0;app_main();assert(writes==1&&written[2]==0x31&&strstr(output,"READ_REPLY"));
 setup(0x31,1);usb_input="READ 1 FD\n";usb_pos=0;app_main();assert(writes==0);usb_input="";usb_pos=0;
#endif
 const char *bad[]={"READ 0 31","READ 256 31","READ -1 31","READ +1 31","READ 1 FD","READ 1 F3","READ 1 F7","READ 1 80","READ 1 01","READ 1 31 x","READ 1 3","READ 1 0031","READ 1 31 READ 2 31","read 1 31","READ 1\t31"};
 for(size_t i=0;i<sizeof bad/sizeof bad[0];i++){setup(0x31,1);assert(!serve_line(bad[i],strlen(bad[i])));assert(writes==0);}
 for(unsigned node=1;node<=255;node+=254)for(unsigned i=0;i<4;i++){unsigned code=(unsigned[]){0x31,0x32,0xF1,0x3A}[i];setup(code,node);char line[24];int n=snprintf(line,sizeof line,"READ %u %02X",node,code);chunk=1;assert(serve_line(line,(size_t)n));assert(writes==1&&written[0]==0xFA&&written[1]==node&&written[2]==code&&written[3]==((0xFA+node+code)&255));assert(strstr(output,"READ_REPLY"));}
 setup(0x31,1);response_n=9;assert(!serve_line("READ 1 31",9)&&writes==1);
 setup(0x31,1);response[10]=0;response_n=11;assert(!serve_line("READ 1 31",9)&&writes==1);
 setup(0x31,1);response[9]^=1;assert(!serve_line("READ 1 31",9)&&writes==1);
 setup(0x31,2);assert(!serve_line("READ 1 31",9)&&writes==1);
 setup(0x32,1);assert(!serve_line("READ 1 31",9)&&writes==1);
 setup(0xF1,1);response[3]=0;response[4]=(uint8_t)(0xFB+1+0xF1);assert(!serve_line("READ 1 F1",9));
 setup(0x3A,1);response[3]=2;response[4]=(uint8_t)(0xFB+1+0x3A+2);assert(!serve_line("READ 1 3A",9));
 setup(0x31,1);tx_return=3;assert(!serve_line("READ 1 31",9)&&writes==1&&response_pos==0);
 setup(0x31,1);rx_error=1;assert(!serve_line("READ 1 31",9)&&writes==1);
 LineState line={0};setup(0x31,1);feed(&line,"READ 1 ",0);expire_line(&line,500000);feed(&line,"31\n",500001);assert(writes==0);feed(&line,"READ 1 31\r\n",500010);assert(writes==1);
 line=(LineState){0};setup(0x31,1);feed(&line,"READ 1 ",1);feed_byte(&line,0,20);feed(&line,"31\n",21);assert(writes==0);feed(&line,"READ 1 31\n",30);assert(writes==1);
 line=(LineState){0};setup(0x31,1);for(unsigned i=0;i<50;i++)feed_byte(&line,'A',i+1);feed(&line,"READ 1 31\n",100);assert(writes==0);feed(&line,"READ 1 31\n",200);assert(writes==1);
 puts("ACTUAL_MAIN_C_PARSE_TX_RX_TIMEOUT_RECOVERY_PASS");return 0;
}
'''


class FirmwareTests(unittest.TestCase):
    def test_actual_source_default_and_permitted_read_only_seams(self):
        folder = FIXTURE / 'firmware'; folder.mkdir()
        for name in ['driver/uart.h', 'driver/usb_serial_jtag.h', 'esp_timer.h', 'freertos/FreeRTOS.h', 'freertos/task.h']:
            p = folder / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(STUB_HEADER, encoding='utf-8')
        source = HERE / 'firmware/main/main.c'
        shim = folder / 'shim.c'; shim.write_text(SHIM.replace('PRODUCT_MAIN', source.as_posix()), encoding='utf-8')
        compiler = ROOT / '.dev/tools/zig-x86_64-windows-0.17.0/zig.exe'
        cache = ROOT / 'outputs/wrist-bench-prep-138/author' / ('c-' + uuid.uuid4().hex[:8])
        cache.mkdir()
        (cache / 't').mkdir()
        env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(cache / 'g'), ZIG_LOCAL_CACHE_DIR=str(cache / 'l'),
                   TEMP=str(cache / 't'), TMP=str(cache / 't'))
        cases = []
        for permit in [0, 1]:
            exe = folder / f'firmware-{permit}.exe'
            command = [str(compiler), 'cc', '-std=c17', '-Wall', '-Wextra', '-Werror', '-I', str(folder), f'-DWRIST138_HARDWARE_PERMIT={permit}', str(shim), '-o', str(exe)]
            build = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
            (folder / f'compile-{permit}.stdout').write_bytes(build.stdout); (folder / f'compile-{permit}.stderr').write_bytes(build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr.decode(errors='replace'))
            run = subprocess.run([str(exe)], cwd=ROOT, capture_output=True, timeout=15)
            (folder / f'run-{permit}.stdout').write_bytes(run.stdout); (folder / f'run-{permit}.stderr').write_bytes(run.stderr)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn(b'ACTUAL_MAIN_C_PARSE_TX_RX_TIMEOUT_RECOVERY_PASS', run.stdout)
            cases.append({'permit': permit, 'build_exit': build.returncode, 'run_exit': run.returncode, 'stdout': run.stdout.decode()})
        source_text = source.read_text(encoding='utf-8')
        mutations = [
            ('read_whitelist_removed', 'if (!reply_size(op)) return false;', ''),
            ('incomplete_three_byte_uart_write', 'uart_write_bytes(BUS, tx, sizeof tx)', 'uart_write_bytes(BUS, tx, 3)'),
            ('partial_usb_timeout_disabled', 'if ((s->used || s->dropping) &&', 'if (false && (s->used || s->dropping) &&'),
            ('default_permit_guard_reversed', 'if (WRIST138_HARDWARE_PERMIT != 1) return;', 'if (WRIST138_HARDWARE_PERMIT == 1) return;'),
        ]
        mutation_records = []
        for name, old, new in mutations:
            self.assertEqual(source_text.count(old), 1)
            changed = folder / (name + '.c'); changed.write_text(source_text.replace(old, new, 1), encoding='utf-8')
            driver = folder / (name + '-driver.c'); driver.write_text(SHIM.replace('PRODUCT_MAIN', changed.as_posix()), encoding='utf-8')
            exe = folder / (name + '.exe')
            permit = 0 if name == 'default_permit_guard_reversed' else 1
            build = subprocess.run([str(compiler), 'cc', '-std=c17', '-Wall', '-Wextra', '-Werror', '-I', str(folder), f'-DWRIST138_HARDWARE_PERMIT={permit}', str(driver), '-o', str(exe)], cwd=ROOT, env=env, capture_output=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(exe)], cwd=ROOT, capture_output=True, timeout=15)
            (folder / (name + '.stdout')).write_bytes(run.stdout)
            (folder / (name + '.stderr')).write_bytes(run.stderr)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(b'Assertion failed', run.stderr)
            mutation_records.append({'name': name, 'detected': True, 'compile_exit': build.returncode, 'run_exit': run.returncode,
                                     'mutant_sha256': hashlib.sha256(changed.read_bytes()).hexdigest()})
        record = {'actual_source': source.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'cache_directory': str(cache),
                  'cases': cases, 'behavioral_mutations': mutation_records, 'physical_tests': 'NOT_RUN', 'mechanism': 'Actual main.c included and SDK calls intercepted by independent stub arrays'}
        (FIXTURE / 'firmware-results.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    print('HOST_FIXTURE=' + str(FIXTURE), flush=True)
    unittest.main(verbosity=2)
