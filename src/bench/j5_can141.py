"""Bounded USB receive and offline J5 preparation. No CAN transport or flash writer."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

READS = (0x31, 0x32, 0xF1, 0x3A)


def preparation(candidate_id=None):
    if candidate_id is not None and (type(candidate_id) is not int or candidate_id not in (1, 2)):
        raise ValueError('Only candidate IDs 1/2 are supported; J5 is not CAN ID5')
    return {
        'joint': 'J5', 'board': 'ESP32-S3-RS485-CAN_NON_U_USER_CONFIRMED',
        'existing_diagnostic': 'BLOCKED_UNCONFIRMED_PROFILE',
        'actual_id': None, 'candidate_id': candidate_id, 'actual_bitrate': None,
        'actual_tx_gpio': None, 'actual_rx_gpio': None,
        'expected_only': {'bitrate': 500000, 'tx_gpio': 15, 'rx_gpio': 16},
        'hardware_approved': False, 'host_CAN_requests': 0,
        'physical_CAN_test': 'NOT_RUN', 'onboard_app_CAN_activity': 'NOT_MONITORED',
        'frames': [] if candidate_id is None else [
            {'id': candidate_id, 'extended': False, 'rtr': False, 'dlc': 2,
             'data': [op, (candidate_id + op) & 255]} for op in READS],
        'meaning': 'OFFLINE_CANDIDATE_ONLY_NOT_TRANSMITTED',
    }


def capture(factory, clock=time.monotonic):
    """Factory is injected for HOST tests. Never call write or a reset sequence."""
    client = None
    data = bytearray()
    errors = []
    opened = False
    closed = False
    start = clock()
    previous = start
    try:
        client = factory(port=None, baudrate=115200, timeout=0.2,
                         xonxoff=False, rtscts=False, dsrdtr=False)
        client.dtr = False
        client.rts = False
        client.port = 'COM7'
        client.open()
        opened = True
        while len(data) < 65536:
            now = clock()
            if now < previous:
                raise RuntimeError('Monotonic clock moved backwards')
            previous = now
            if now - start >= 8:
                break
            client.timeout = min(0.2, 8 - (now - start))
            block = client.read(min(4096, 65536 - len(data)))
            if not isinstance(block, bytes) or len(block) > min(4096, 65536 - len(data)):
                raise ValueError('Invalid serial read result')
            data.extend(block)
    except Exception as exc:
        errors.append({'stage': 'open_or_read', 'type': type(exc).__name__, 'message': str(exc)})
    finally:
        if client is not None:
            try:
                client.close()
                closed = True
            except Exception as exc:
                errors.append({'stage': 'close', 'type': type(exc).__name__, 'message': str(exc)})
    return bytes(data), {
        'state': 'ERROR' if errors else 'CAPTURED' if data else 'SILENT_UNIDENTIFIED',
        'port': 'COM7', 'opened': opened, 'closed': closed, 'bytes_received': len(data),
        'rx_sha256': hashlib.sha256(data).hexdigest(), 'receive_schedule_s': 8, 'byte_limit': 65536,
        'read_timeout_cap_s': 0.2, 'elapsed_s': clock() - start, 'required_outer_timeout_s': 20,
        'OS_scheduling_and_close_time_included_in_elapsed': True,
        'USB_application_TX_bytes': 0, 'DTR_RTS_requested_before_open': [False, False],
        'OS_control_line_reset_not_excluded': True,
        'onboard_app_CAN_activity': 'NOT_MONITORED', 'host_CAN_requests': 0,
        'physical_CAN_test': 'NOT_RUN', 'motor_power': 'USER_REPORTED_OFF_NOT_INSTRUMENTED',
        'firmware_identity_from_capture': 'UNCONFIRMED_REQUIRES_CONTENT_REVIEW', 'errors': errors,
    }


def partition_table(raw):
    if len(raw) != 4096:
        raise ValueError('Exactly one 4KiB partition-table sector required')
    digest = hashlib.md5()
    checked = False
    entries = []
    terminated = False
    for pos in range(0, 0xC00, 32):
        row = raw[pos:pos + 32]
        if row == b'\xff' * 32:
            terminated = True
            if raw[pos:] != b'\xff' * (len(raw) - pos):
                raise ValueError('Non-erased data after partition terminator')
            break
        if row[:2] == b'\xeb\xeb':
            if checked or row[:16] != b'\xeb\xeb' + b'\xff' * 14 or row[16:] != digest.digest():
                raise ValueError('Invalid partition MD5 record')
            checked = True
            continue
        if checked:
            raise ValueError('Partition entries after MD5')
        magic, kind, subtype, offset, size, name, flags = struct.unpack('<HBBII16sI', row)
        if magic != 0x50AA or not size or offset < 0x9000 or offset + size > 0x1000000:
            raise ValueError('Invalid partition entry or unsupported flash range')
        if offset % 4096 or size % 4096:
            raise ValueError('Unaligned partition')
        label = name.split(b'\0', 1)[0].decode('ascii')
        if not label or any(ord(ch) < 32 or ord(ch) > 126 for ch in label):
            raise ValueError('Invalid partition name')
        if any(label == e['label'] or offset < e['offset'] + e['size'] and e['offset'] < offset + size for e in entries):
            raise ValueError('Duplicate label or overlapping partitions')
        entries.append({'type': kind, 'subtype': subtype, 'offset': offset,
                        'size': size, 'label': label, 'flags': flags})
        digest.update(row)
    if not checked or not terminated:
        raise ValueError('MD5 and partition terminator required')
    apps = [e for e in entries if e['type'] == 0]
    if len(apps) != 1:
        raise ValueError('Exactly one stored app required; OTA ambiguity is not resolved')
    app = apps[0]
    if app['flags'] != 0 or app['offset'] % 0x10000 or app['size'] < 4096:
        raise ValueError('Encrypted, unsupported or unaligned app partition')
    return {'state': 'SINGLE_STORED_APP_LOCATED', 'entries': entries, 'app': app,
            'execution_identity': 'UNCONFIRMED', 'read_bytes': 4096}


def app_descriptor(raw):
    if len(raw) != 4096 or raw[0] != 0xE9 or not 1 <= raw[1] <= 16:
        raise ValueError('Invalid or unsupported image prefix')
    if struct.unpack_from('<H', raw, 12)[0] != 9:
        raise ValueError('Image chip is not ESP32-S3')
    if struct.unpack_from('<I', raw, 28)[0] < 256:
        raise ValueError('First segment is too short for app descriptor')
    desc = raw[32:288]
    if struct.unpack_from('<I', desc)[0] != 0xABCD5432:
        raise ValueError('App descriptor magic missing at required offset')

    def field(start, length):
        value = desc[start:start + length].split(b'\0', 1)[0].decode('ascii')
        if not value or any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
            raise ValueError('Invalid descriptor text')
        return value

    return {'state': 'STORED_METADATA_PARSED', 'project': field(48, 32),
            'version': field(16, 32), 'build_time': field(80, 16),
            'build_date': field(96, 16), 'idf': field(112, 32),
            'elf_sha256_recorded_in_image': desc[144:176].hex(),
            'image_prefix_sha256': hashlib.sha256(raw).hexdigest(),
            'complete_image_integrity': 'NOT_VERIFIED', 'execution_identity': 'UNCONFIRMED',
            'CAN_behavior_safety': 'NOT_VERIFIED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('plan').add_argument('--candidate-id', type=int, choices=(1, 2))
    for mode in ('partition', 'app'):
        sub.add_parser(mode).add_argument('file', type=Path)
    observer = sub.add_parser('observe')
    observer.add_argument('--motor-power-off', action='store_true', required=True)
    observer.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'plan':
            result = preparation(args.candidate_id)
        elif args.command in ('partition', 'app'):
            if args.file.stat().st_size != 4096:
                raise ValueError('Input must be exactly 4096 bytes')
            raw = args.file.read_bytes()
            result = partition_table(raw) if args.command == 'partition' else app_descriptor(raw)
        else:
            import serial
            from serial.tools import list_ports
            matches = [p for p in list_ports.comports() if p.device.upper() == 'COM7'
                       and p.vid == 0x303A and p.pid == 0x1001]
            if len(matches) != 1:
                raise ValueError('Current COM7 must match exactly one Espressif USB device')
            args.out.mkdir(exist_ok=False)
            raw, result = capture(serial.Serial)
            (args.out / 'rx.bin').write_bytes(raw)
            (args.out / 'capture.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result.get('state') == 'ERROR' else 0
    except Exception as exc:
        print(json.dumps({'state': 'ERROR', 'type': type(exc).__name__, 'message': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
