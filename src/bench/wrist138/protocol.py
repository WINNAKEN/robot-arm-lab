"""Makerbase V1.0.9 native RS485 frames. Pure bytes, never a transport."""
from __future__ import annotations

READ_CODES = {0x31: 6, 0x32: 2, 0xF1: 1, 0x3A: 1}
STATE_NAMES = {1: 'stopped', 2: 'accelerating', 3: 'decelerating',
               4: 'constant_speed', 5: 'homing', 6: 'calibrating'}


def integer(value, lo, hi, name):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{name}: integer in [{lo}, {hi}] required')
    return value


def address(value):
    return integer(value, 1, 255, 'unicast address (broadcast 0 forbidden)')


def read_code(value):
    integer(value, 0, 255, 'opcode')
    if value not in READ_CODES:
        raise ValueError('Only read opcodes 31/32/F1/3A are supported')
    return value


def checksum(data):
    if not isinstance(data, bytes):
        raise ValueError('bytes required')
    return sum(data) & 0xFF


def query(node, code):
    raw = bytes([0xFA, address(node), read_code(code)])
    return raw + bytes([checksum(raw)])


def decode(node, code, raw):
    address(node)
    read_code(code)
    if not isinstance(raw, bytes) or len(raw) != READ_CODES[code] + 4:
        raise ValueError('Exact one reply length required; partial/trailing bytes rejected')
    if raw[:3] != bytes([0xFB, node, code]):
        raise ValueError('Reply header/address/opcode mismatch')
    if checksum(raw[:-1]) != raw[-1]:
        raise ValueError('Reply checksum mismatch')
    data = raw[3:-1]
    result = {'address': node, 'opcode_hex': f'{code:02X}', 'raw_hex': raw.hex(' ').upper(),
              'provenance': 'UNVERIFIED_OFFLINE_BYTES', 'physical_tests': 'NOT_RUN'}
    if code == 0x31:
        result.update(encoder_counts=int.from_bytes(data, 'big', signed=True),
                      counts_per_motor_revolution=16384,
                      sign_mapping='UNVERIFIED: manual direction prose and examples conflict')
    elif code == 0x32:
        result['motor_rpm'] = int.from_bytes(data, 'big', signed=True)
    elif code == 0x3A:
        if data[0] not in (0, 1):
            raise ValueError('Invalid enable status')
        result['enabled'] = bool(data[0])
    else:
        if data[0] == 0:
            raise ValueError('F1 query failed (status 0), not stopped')
        if data[0] not in STATE_NAMES:
            raise ValueError('Invalid operating status')
        result['run_state'] = STATE_NAMES[data[0]]
    return result


def pulse_preview(node, direction, rpm, acceleration, pulses):
    """Finite FD frame only for the checked offline planner. Never sent here."""
    address(node)
    integer(direction, 0, 1, 'direction')
    integer(rpm, 1, 5, 'preview motor rpm')
    integer(acceleration, 1, 255, 'positive acceleration')
    integer(pulses, 1, 0xFFFFFFFF, 'finite positive pulse count')
    raw = bytes([0xFA, node, 0xFD, (direction << 7) | (rpm >> 8), rpm & 255,
                 acceleration]) + pulses.to_bytes(4, 'big')
    return raw + bytes([checksum(raw)])
