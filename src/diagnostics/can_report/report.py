"""Review saved diagnostic NDJSON and observation records without device access."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
LIMIT = 1024 * 1024
MAX_RECORDS = 130
DISABLED = set('state hardware_approved CAN_started profile_readiness missing mismatch tick_hz'.split())
TERMINAL = set('state error overflow'.split())
HEALTH = set('last_alerts last_bus_state tx_pending rx_pending rx_missed rx_overrun tx_failed bus_errors arbitration_lost close_quiesced close_healthy'.split())
EVENT = set('kind error at_ms rx_dequeued_ms id dlc ext rtr value data'.split())
SOURCES = {
    'diagnostic.hpp': 'src/firmware/components/robot_diagnostic/include/robot_diagnostic/diagnostic.hpp',
    'execution.hpp': 'src/firmware/components/robot_diagnostic/include/robot_diagnostic/execution.hpp',
    'main.cpp': 'src/firmware/diagnostic/main/main.cpp',
    'diagnostic.cpp': 'src/firmware/components/robot_diagnostic/diagnostic.cpp',
    'can_port.hpp': 'src/firmware/components/robot_can/include/robot_can/can_port.hpp',
    'template': 'docs/specs/read-diagnostic-profile.template.json',
}
ENUMS = {
    'State': 'Idle Gap AwaitTx AwaitRx Complete Fault Rejected'.split(),
    'Error': 'None Profile Clock Service Timeout Port Busy Alert Frame UnexpectedRx Device JournalFull Close Request Schedule'.split(),
    'Kind': 'Begin Submit Accepted TxComplete RxRaw Value Failure Close'.split(),
    'Readiness': 'Pending Mismatch ReadyForReview'.split(),
    'BusState': 'Stopped Running BusOff Recovering'.split(),
}
ISSUES = 'Selection BoardIssue ProtocolIssue HardwareRecord FirmwareRecord IdIssue RateIssue PinIssue WiringIssue PowerOnIssue'.split()


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def integer(value, low=0, high=(1 << 64) - 1):
    need(type(value) is int and low <= value <= high, 'Integer type/range')
    return value


def boolean(value):
    need(type(value) is bool, 'Boolean type')


def keys(value, expected):
    need(type(value) is dict and set(value) == expected, 'Exact record fields')


def loads(raw):
    need(len(raw) <= LIMIT, 'Input exceeds 1MiB')

    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result

    def number(text):
        need(len(text) <= 21, 'Oversized integer')
        return integer(int(text), -(1 << 63), (1 << 64) - 1)

    def fraction(text):
        value = float(text)
        need(math.isfinite(value), 'Nonfinite JSON')
        return value

    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_int=number,
                      parse_float=fraction,
                      parse_constant=lambda text: need(False, 'Nonfinite JSON'))


def source_contract():
    raw = {name: (ROOT / path).read_bytes() for name, path in SOURCES.items()}
    header = raw['diagnostic.hpp'].decode('utf-8') + raw['execution.hpp'].decode('utf-8') + raw['can_port.hpp'].decode('utf-8')
    for name, expected in ENUMS.items():
        matched = re.findall(r'enum class ' + name + r'\s*(?::\s*std::uint8_t\s*)?\{([^}]+)\}', header)
        need(len(matched) == 1, 'Unsupported enum declaration: ' + name)
        actual = [part.strip() for part in matched[0].split(',')]
        need(actual == expected, 'Enum declaration changed: ' + name)
    issue = re.search(r'enum Issue\s*:\s*std::uint32_t\s*\{([^}]+)\}', header)
    need(issue is not None, 'Issue declaration missing')
    declarations = [re.fullmatch(r'\s*(\w+)\s*=\s*1u\s*<<\s*(\d+)\s*', part)
                    for part in issue.group(1).split(',')]
    need(all(item is not None for item in declarations), 'Unsupported Issue declaration')
    bits = [item.groups() for item in declarations]
    need(bits == [(name, str(index)) for index, name in enumerate(ISSUES)], 'Issue bits changed')
    return {name: digest(data) for name, data in raw.items()}, loads(raw['template'])


def enum_name(name, value):
    return ENUMS[name][integer(value, 0, len(ENUMS[name]) - 1)]


def profile_contract(profile, template):
    keys(profile, set(template))
    need(type(profile['schema_version']) is int and profile['schema_version'] == 1, 'Profile version')
    need(profile['purpose'] == template['purpose'], 'Record-only profile purpose')
    need(profile['hardware_approved'] is False, 'Physical approval forbidden')
    need(json.dumps(profile['expected'], sort_keys=True) == json.dumps(template['expected'], sort_keys=True), 'Expected constraints changed')
    observed = profile['observed']
    keys(observed, set(template['observed']))
    for name in ('board_model', 'driver_protocol', 'hardware_revision', 'firmware_version'):
        value = observed[name]
        need(value is None or (type(value) is str and len(value.encode('utf-8')) <= 256 and all(ord(c) >= 32 and ord(c) != 127 for c in value)), 'Observation string')
    for name, high in (('selected_axis', 2047), ('actual_can_id', 2047), ('tx_gpio', 48), ('rx_gpio', 48), ('bitrate', 1000000)):
        if observed[name] is not None:
            integer(observed[name], 0, high)
    for name in ('wiring_and_termination', 'power_on_motion_excluded'):
        need(observed[name] in ('UNCONFIRMED', 'PASS', 'FAIL'), 'Observation check state')
    evidence = profile['evidence']
    keys(evidence, set(template['evidence']))
    paths = evidence['photo_and_label_paths']
    need(type(paths) is list and len(paths) <= 128 and all(type(p) is str and len(p) <= 512 for p in paths), 'Photo path records')
    need(type(evidence['motor_body_label_observed']) is str and len(evidence['motor_body_label_observed']) <= 1024, 'Motor label record')
    need(evidence['CAN_hardware_test'] == evidence['RTOS_jitter_and_ISR_test'] == 'NOT_RUN', 'Physical evidence outside offline scope')


def log_contract(raw):
    need(len(raw) <= LIMIT, 'Input exceeds 1MiB')
    lines = [line for line in raw.splitlines() if line.strip()]
    need(len(lines) <= MAX_RECORDS, 'Too many records')
    records = [loads(line) for line in lines]
    need(all(type(row) is dict for row in records), 'JSON objects required')
    if not records:
        return {'status': 'INCOMPLETE', 'reason': 'No records', 'events': [], 'anomalies': []}
    first = records[0]
    if first.get('state') == 'DISABLED':
        keys(first, DISABLED)
        need(len(records) == 1 and first['hardware_approved'] is False and first['CAN_started'] is False, 'Disabled cannot start hardware')
        readiness = enum_name('Readiness', first['profile_readiness'])
        missing, mismatch = (integer(first[name], 0, 1023) for name in ('missing', 'mismatch'))
        expected = 'Mismatch' if mismatch else 'Pending' if missing else 'ReadyForReview'
        need(readiness == expected and type(first['tick_hz']) is int and first['tick_hz'] == 1000, 'Disabled profile/tick contradiction')
        return {'status': 'DISABLED', 'profile_readiness': readiness,
                'missing': [name for i, name in enumerate(ISSUES) if missing & (1 << i)],
                'mismatch': [name for i, name in enumerate(ISSUES) if mismatch & (1 << i)],
                'raw_disabled': first, 'events': [], 'anomalies': []}
    if set(first) != TERMINAL:
        need(set(first) in (HEALTH, EVENT), 'Unexpected record shape')
        terminal_missing = True
    else:
        terminal_missing = False
    terminal = None if terminal_missing else records[0]
    state = error = None
    if terminal is not None:
        keys(terminal, TERMINAL)
        state, error = enum_name('State', terminal['state']), enum_name('Error', terminal['error'])
        boolean(terminal['overflow'])
        need(not (state == 'Complete' and (error != 'None' or terminal['overflow'])), 'Complete error/overflow contradiction')
        need(not (state == 'Fault' and error == 'None'), 'Fault without error')
    tail = list(records if terminal_missing else records[1:])
    health = None
    if tail and set(tail[0]) == HEALTH:
        health = tail.pop(0)
        for name in HEALTH - {'close_quiesced', 'close_healthy'}:
            integer(health[name], 0, (1 << 32) - 1)
        enum_name('BusState', health['last_bus_state'])
        boolean(health['close_quiesced'])
        boolean(health['close_healthy'])
    events, regressions = [], []
    for index, event in enumerate(tail):
        keys(event, EVENT)
        kind = enum_name('Kind', event['kind'])
        event_error = enum_name('Error', event['error'])
        integer(event['at_ms'])
        integer(event['rx_dequeued_ms'])
        integer(event['id'], 0, (1 << 32) - 1)
        integer(event['dlc'], 0, 8)
        integer(event['value'], -(1 << 63), (1 << 63) - 1)
        boolean(event['ext'])
        boolean(event['rtr'])
        need(type(event['data']) is list and len(event['data']) == 8, 'Exactly eight data bytes')
        for byte in event['data']:
            integer(byte, 0, 255)
        if events and event['at_ms'] < events[-1]['at_ms']:
            regressions.append({'index': index, 'previous_at_ms': events[-1]['at_ms'], 'at_ms': event['at_ms']})
        events.append(dict(event, kind_name=kind, error_name=event_error))
    need(not (state == 'Complete' and regressions), 'Complete clock regression contradiction')
    incomplete = terminal_missing or health is None or not events or events[0]['kind_name'] != 'Begin' or events[-1]['kind_name'] != 'Close'
    if state not in ('Complete', 'Fault'):
        incomplete = True
    if state == 'Complete':
        values = [row['data'][0] for row in events if row['kind_name'] == 'Value']
        incomplete = incomplete or values != [0x3A, 0xF1, 0x31, 0x32]
    return {'status': 'INCOMPLETE' if incomplete else 'LOG_REVIEW_ONLY',
            'terminal': terminal, 'state_name': state,
            'error_name': error, 'health': health,
            'events': events, 'anomalies': regressions,
            'physical_interpretation': 'NOT_AUTHENTICATED_NO_WIRE_CAUSALITY_OR_STOP_ACCEPTANCE'}


def build_report(log_raw, profile_raw, synthetic=False):
    result = {'schema_version': 1, 'hardware_approved': False,
              'CAN_hardware_test': 'NOT_RUN', 'RTOS_jitter_and_ISR_test': 'NOT_RUN',
              'evidence_origin': 'SYNTHETIC_HOST' if synthetic else 'UNVERIFIED_LOCAL_FILE',
              'log_sha256': digest(log_raw), 'log_bytes': len(log_raw),
              'profile_sha256': digest(profile_raw), 'profile_bytes': len(profile_raw),
              'source_binding_meaning': 'PARSER_COMPATIBILITY_NOT_FIRMWARE_OR_DEVICE_AUTHENTICATION'}
    try:
        pins, template = source_contract()
        result['source_sha256'] = pins
        profile = loads(profile_raw)
        profile_contract(profile, template)
        result['observed'] = copy.deepcopy(profile['observed'])
        result['observed_evidence'] = copy.deepcopy(profile['evidence'])
        result['software_profile_readiness_evaluation'] = 'NOT_RUN_CPP_PREPARE_PROFILE_NOT_CALLED'
        result.update(log_contract(log_raw))
    except (ValueError, UnicodeError, RecursionError, OSError) as exc:
        result.update(status='INVALID_INPUT', reason=str(exc), events=[], anomalies=[])
    return result


def markdown(report):
    def cell(value):
        return json.dumps(value, ensure_ascii=False).replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')
    lines = ['# CAN 읽기 진단 오프라인 기록', '', '**' + report['status'] + '**', '',
             '출처: ' + report['evidence_origin'] + '. 파일/파서 대조 결과이며 실제 장치 출처 인증은 없습니다.', '',
             '물리 승인: false · 실제 CAN/RTOS 시험: NOT_RUN · 펌웨어 실행 설정으로 사용하지 않습니다.', '']
    if report.get('reason'):
        lines += ['사유: ' + cell(report['reason']), '']
    if report['status'] == 'DISABLED':
        lines += ['프로필 누락 비트: ' + cell(report['missing']),
                  '프로필 불일치 비트: ' + cell(report['mismatch']),
                  '비활성 원 기록: ' + cell(report['raw_disabled']), '']
    lines += ['| 관측 항목 | 원 기록 |', '|---|---|']
    lines += ['| ' + name + ' | ' + cell(value) + ' |' for name, value in report.get('observed', {}).items()]
    lines += ['', '진단 상태: ' + str(report.get('state_name', report.get('profile_readiness', '미확인'))),
              ' · 오류: ' + str(report.get('error_name', '미확인')), '']
    if report.get('terminal') is not None:
        lines += ['종료 원 기록: ' + cell(report['terminal']), '']
    lines += ['| 버스/종료 항목 | 원 기록 |', '|---|---|']
    for name, value in (report.get('health') or {}).items():
        label = cell(value)
        if name == 'last_bus_state':
            label += ' (' + enum_name('BusState', value) + ')'
        lines.append('| ' + name + ' | ' + label + ' |')
    lines += ['', '| 순서 | 사건 | 오류 | at_ms | RX dequeue_ms | ID | DLC | ext | rtr | DATA(원 10진 바이트) | 값 |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
    for i, event in enumerate(report.get('events', [])):
        row = [i, event['kind_name'], event['error_name'], event['at_ms'], event['rx_dequeued_ms'], event['id'], event['dlc'], event['ext'], event['rtr'], event['data'], event['value']]
        lines.append('| ' + ' | '.join(cell(value) for value in row) + ' |')
    lines += ['', '시각 역행(원 순서·값 보존): ' + cell(report.get('anomalies', [])), '',
              'RX dequeue 시각은 선로 도착 시각이 아닙니다. ReadyForReview/Complete는 물리 승인·정지·무토크 증명이 아닙니다.', '',
              '원 로그 SHA256: `' + report['log_sha256'] + '`',
              '관측 기록 SHA256: `' + report['profile_sha256'] + '`', '']
    lines += ['| 파서 호환 소스 | SHA256 |', '|---|---|']
    lines += ['| ' + name + ' | `' + pin + '` |' for name, pin in report.get('source_sha256', {}).items()]
    lines.append('')
    return '\n'.join(lines)


def read_bounded(path):
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    need(len(raw) <= LIMIT, 'Input exceeds 1MiB')
    return raw


def emit(log_path, profile_path, out, synthetic=False):
    need(not out.exists() and not out.is_symlink(), 'Output already exists')
    report = build_report(read_bounded(log_path), read_bounded(profile_path), synthetic)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    (out / 'report.md').write_text(markdown(report), encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--synthetic-host', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = emit(args.log, args.profile, args.out, args.synthetic_host)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'status': report['status'], 'hardware_approved': False, 'physical_CAN': 'NOT_RUN'}))
    return 2 if report['status'] == 'INVALID_INPUT' else 1 if report['status'] == 'INCOMPLETE' else 0


if __name__ == '__main__':
    raise SystemExit(main())
