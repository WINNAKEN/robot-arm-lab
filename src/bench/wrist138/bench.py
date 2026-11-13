"""138 offline preparation CLI. No port, device, serial or network API exists."""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('wrist138_protocol', HERE / 'protocol.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
AXES = ('J5', 'J6', 'GRIPPER')
BASE = {'unit': 138, 'offline_only': True, 'hardware_approved': False,
        'physical_tests': 'NOT_RUN', 'transmitted_frames': 0}
TRUE_CONTROLLER = ('firmware_checked', 'terminal_labels_checked', 'isolated_reference_reviewed')
TRUE_POWER = ('disconnect_verified', 'usb_only_confirmed', 'polarity_checked')
TRUE_AXIS = ('neutral_confirmed', 'direction_confirmed', 'fixture_verified',
             'gravity_support_verified', 'stop_verified', 'disconnection_verified',
             'calibration_history_verified', 'auto_home_disabled', 'auto_resume_disabled',
             'gear_ratio_verified', 'step_angle_verified', 'microsteps_verified',
             'current_settings_verified', 'encoder_sign_verified')


def number(v, lo, hi):
    if type(v) not in (int, float) or not lo <= v <= hi:
        return False
    return type(v) is int or math.isfinite(v)


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_profile(path):
    p = Path(path).absolute()
    if '..' in p.parts or not p.is_relative_to(ROOT):
        raise ValueError('Profile must be inside this repository')
    for q in (p,) + tuple(p.parents):
        if q.exists():
            st = q.lstat()
            if q.is_symlink() or getattr(st, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Profile reparse/symlink ancestor')
    with p.open('rb') as handle:
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ValueError('Profile exceeds 64 KiB bound')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + s)))


def readiness(profile, axis):
    if axis not in AXES:
        raise ValueError('Unknown axis')
    reasons = []
    if not isinstance(profile, dict):
        return ['profile must be object']
    if profile.get('schema') != 'wrist-bench-138-v1':
        reasons.append('profile.schema')
    if profile.get('hardware_approved') is not False:
        reasons.append('profile.hardware_approved must remain false: this tool grants no physical authority')
    sections = {}
    for group in ('controller', 'power', 'axes'):
        value = profile.get(group)
        sections[group] = value if isinstance(value, dict) else {}
        if not isinstance(value, dict):
            reasons.append(group + ' object missing')
    controller, power = sections['controller'], sections['power']
    item = sections['axes'].get(axis)
    if not isinstance(item, dict):
        reasons.append(axis + ' object missing')
        item = {}
    for key in ('product', 'revision'):
        if not isinstance(controller.get(key), str) or not controller[key].strip():
            reasons.append('controller.' + key)
    for group, value, keys in [('controller', controller, TRUE_CONTROLLER),
                               ('power', power, TRUE_POWER), (axis, item, TRUE_AXIS)]:
        reasons.extend(group + '.' + key for key in keys if value.get(key) is not True)
    for key, lo, hi in [('voltage_v', 12, 24), ('current_limit_a', 0.001, 100),
                        ('fuse_rating_a', 0.001, 100)]:
        if not number(power.get(key), lo, hi):
            reasons.append('power.' + key)
    for key in ('driver_model', 'fw_version', 'hw_version', 'motor_model'):
        if not isinstance(item.get(key), str) or not item[key].strip():
            reasons.append(axis + '.' + key)
    for key, expected in [('transport', 'RS485'), ('protocol', 'MKS_NATIVE_FA_FB'),
                           ('uart_format', '8N1')]:
        if item.get(key) != expected:
            reasons.append(axis + '.' + key)
    if item.get('mode') not in ('SR_CLOSE', 'SR_vFOC'):
        reasons.append(axis + '.mode (verified encoder mode required)')
    for key, lo, hi in [('node_id', 1, 255), ('microsteps', 1, 256)]:
        if type(item.get(key)) is not int or not lo <= item[key] <= hi:
            reasons.append(axis + '.' + key)
    if type(item.get('baud')) is not int or item['baud'] not in (9600, 19200, 25000, 38400, 57600, 115200, 256000):
        reasons.append(axis + '.baud')
    for key, lo, hi in [('motor_step_angle_deg', 0.01, 360), ('gear_ratio', 1, 10000),
                        ('motor_rated_current_a', 0.001, 3), ('configured_current_a', 0.001, 3),
                        ('clearance_positive_motor_deg', 0.001, 360),
                        ('clearance_negative_motor_deg', 0.001, 360),
                        ('max_test_motor_rpm', 0.001, 5)]:
        if not number(item.get(key), lo, hi):
            reasons.append(axis + '.' + key)
    if number(item.get('motor_rated_current_a'), 0, 100) and number(item.get('configured_current_a'), 0, 100):
        if item['configured_current_a'] > item['motor_rated_current_a']:
            reasons.append(axis + '.configured_current_a exceeds motor label')
    for key in ('command0_motor_sign', 'output_sign_from_motor', 'encoder_sign_from_motor'):
        if type(item.get(key)) is not int or item[key] not in (-1, 1):
            reasons.append(axis + '.' + key)
    if axis == 'GRIPPER' and item.get('pinion_radius_mm') is not None:
        if not number(item['pinion_radius_mm'], 0.01, 100):
            reasons.append(axis + '.pinion_radius_mm')
    return reasons


def jog_plan(profile, axis, amount, unit='motor_deg', rpm=1, acceleration=1):
    if not number(amount, -1000000, 1000000) or amount == 0:
        raise ValueError('Finite nonzero nonboolean amount required')
    P.integer(rpm, 1, 5, 'rpm')
    P.integer(acceleration, 1, 255, 'positive acceleration')
    if unit not in ('motor_deg', 'output_deg', 'rack_mm'):
        raise ValueError('Unknown movement unit')
    reasons = readiness(profile, axis)
    axes = profile.get('axes') if isinstance(profile, dict) else None
    item = axes.get(axis) if isinstance(axes, dict) else None
    item = item if isinstance(item, dict) else {}
    if unit == 'rack_mm':
        if axis != 'GRIPPER':
            reasons.append('rack_mm requires GRIPPER')
        if not number(item.get('pinion_radius_mm'), 0.01, 100):
            reasons.append(axis + '.pinion_radius_mm must be physically confirmed')
        if item.get('pinion_radius_verified') is not True:
            reasons.append(axis + '.pinion_radius_verified')
    if reasons:
        return dict(BASE, status='BLOCKED', axis=axis, missing_or_invalid=reasons,
                    explanation='No FD or enable payload emitted; physical facts unresolved')
    sign, ratio = item['output_sign_from_motor'], item['gear_ratio']
    motor_deg = amount
    if unit == 'output_deg':
        motor_deg = amount * ratio / sign
    elif unit == 'rack_mm':
        motor_deg = math.degrees(amount / item['pinion_radius_mm']) * ratio / sign
    if not math.isfinite(motor_deg) or abs(motor_deg) > 5:
        raise ValueError('Requested movement exceeds 5 degree MOTOR ceiling')
    step = item['motor_step_angle_deg'] / item['microsteps']
    pulses = math.floor(abs(motor_deg) / step + 0.5)
    P.integer(pulses, 1, 0xFFFFFFFF, 'rounded pulse count')
    actual_motor = math.copysign(pulses * step, motor_deg)
    clearance = item['clearance_positive_motor_deg' if actual_motor > 0 else 'clearance_negative_motor_deg']
    if abs(actual_motor) > min(5, clearance) or rpm > item['max_test_motor_rpm']:
        raise ValueError('Rounded movement or rpm exceeds verified mechanical/test limit')
    direction = 0 if (1 if actual_motor > 0 else -1) == item['command0_motor_sign'] else 1
    frame = P.pulse_preview(item['node_id'], direction, rpm, acceleration, pulses)
    output_deg = actual_motor / ratio * sign
    result = dict(BASE, status='DRY_PLAN_ONLY', axis=axis, command='FD finite relative pulse PREVIEW',
                  frame_hex=frame.hex(' ').upper(), expected_bytes=len(frame), pulses=pulses,
                  requested={'amount': amount, 'unit': unit}, actual_motor_deg=actual_motor,
                  actual_output_deg=output_deg, rpm_motor=rpm, acceleration=acceleration,
                  auto_enable=False, auto_retry=False, automatic_home=False,
                  physical_execution_authorized=False)
    if axis == 'GRIPPER' and item.get('pinion_radius_verified') is True and number(item.get('pinion_radius_mm'), 0.01, 100):
        result['one_jaw_rack_travel_mm'] = math.radians(output_deg) * item['pinion_radius_mm']
        result['gap_change_mm'] = 2 * result['one_jaw_rack_travel_mm']
    return result


def read_plan(axis, node):
    if axis not in AXES:
        raise ValueError('Unknown axis')
    P.address(node)
    return dict(BASE, status='READ_PREVIEW_ONLY', axis=axis, single_axis_only=True,
                other_two_axes='POWER_OFF_AND_PHYSICALLY_DISCONNECTED',
                requests=[{'opcode_hex': f'{code:02X}', 'tx_hex': P.query(node, code).hex(' ').upper(),
                           'expected_reply_bytes': size + 4,
                           'bridge_line': f'READ {node} {code:02X}'} for code, size in P.READ_CODES.items()])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default=str(HERE / 'profile.template.json'))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    sub.add_parser('demo')
    p = sub.add_parser('read-plan'); p.add_argument('--axis', choices=AXES, required=True); p.add_argument('--address', type=int, required=True)
    p = sub.add_parser('decode'); p.add_argument('--address', type=int, required=True); p.add_argument('--code', type=lambda x: int(x, 16), required=True); p.add_argument('--hex', required=True)
    p = sub.add_parser('jog-plan'); p.add_argument('--axis', choices=AXES, required=True); p.add_argument('--amount', type=float, required=True); p.add_argument('--unit', choices=('motor_deg', 'output_deg', 'rack_mm'), default='motor_deg'); p.add_argument('--rpm', type=int, default=1); p.add_argument('--acceleration', type=int, default=1)
    args = parser.parse_args(argv)
    try:
        if args.command == 'status':
            profile = load_profile(args.profile)
            result = dict(BASE, status='PREPARED_NOT_RUN', axes={a: {'jog_plan': 'BLOCKED' if readiness(profile, a) else 'DRY_PLAN_ONLY', 'missing_or_invalid': readiness(profile, a)} for a in AXES})
        elif args.command == 'demo':
            raw = bytes.fromhex('FB 01 32 FF FE 2B')
            result = dict(BASE, status='SYNTHETIC_DEMO', synthetic=True, sample=P.decode(1, 0x32, raw))
        elif args.command == 'read-plan':
            result = read_plan(args.axis, args.address)
        elif args.command == 'decode':
            if len(args.hex) > 200:
                raise ValueError('Oversized reply text')
            result = dict(BASE, status='OFFLINE_CAPTURE_DECODED_NOT_AUTHENTICATED', decoded=P.decode(args.address, args.code, bytes.fromhex(args.hex)))
        else:
            result = jog_plan(load_profile(args.profile), args.axis, args.amount, args.unit, args.rpm, args.acceleration)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 3 if result['status'] == 'BLOCKED' else 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps(dict(BASE, status='ERROR', error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
