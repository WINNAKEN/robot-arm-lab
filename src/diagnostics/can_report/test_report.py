"""Offline positive, failure-log, malformed-input and semantic-mutation checks."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
from unittest.mock import patch

SOURCE = Path(__file__).with_name('report.py')
spec = importlib.util.spec_from_file_location('can_report_under_test', SOURCE)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def encode(value):
    return json.dumps(value, allow_nan=False).encode('utf-8')


def event(kind, at=100, error=0, opcode=0):
    return dict(kind=kind, error=error, at_ms=at, rx_dequeued_ms=0, id=1, dlc=0,
                ext=False, rtr=False, value=0, data=[opcode] + [0] * 7)


def fixtures():
    profile = json.loads((report.ROOT / report.SOURCES['template']).read_text())
    disabled = dict(state='DISABLED', hardware_approved=False, CAN_started=False,
                    profile_readiness=0, missing=1023, mismatch=0, tick_hz=1000)
    health = {key: 0 for key in report.HEALTH}
    health.update(last_bus_state=1, close_quiesced=True, close_healthy=True)
    complete = [dict(state=4, error=0, overflow=False), health, event(0)]
    complete += [event(5, at=110 + i, opcode=opcode) for i, opcode in enumerate((0x3A, 0xF1, 0x31, 0x32))]
    complete += [event(7, at=120)]
    return profile, disabled, complete


def run_cases(api):
    profile, disabled, complete = fixtures()
    results = {}

    def check(name, rows, expected, observed=None, raw=None):
        data = raw if raw is not None else b'\n'.join(encode(row) for row in rows)
        answer = api.build_report(data, encode(profile if observed is None else observed), True)
        assert answer['status'] == expected, (name, answer)
        assert answer['hardware_approved'] is False and answer['CAN_hardware_test'] == 'NOT_RUN'
        assert answer['evidence_origin'] == 'SYNTHETIC_HOST'
        assert answer['log_sha256'] == hashlib.sha256(data).hexdigest()
        results[name] = True
        return answer

    disabled_answer = check('disabled_pending', [disabled], 'DISABLED')
    disabled_md = api.markdown(disabled_answer)
    assert all(name in disabled_md for name in report.ISSUES)
    results['markdown_missing_mismatch_present'] = True
    answer = check('complete_log_only', complete, 'LOG_REVIEW_ONLY')
    complete_md = api.markdown(answer)
    assert all(name in complete_md for name in report.HEALTH)
    assert '| ext | rtr |' in complete_md and 'Running' in complete_md
    assert all(pin in complete_md for pin in answer['source_sha256'].values())
    results['markdown_health_flags_and_source_hashes_present'] = True
    assert all(value is None for name, value in answer['observed'].items() if name not in ('wiring_and_termination', 'power_on_motion_excluded'))
    check('empty_incomplete', [], 'INCOMPLETE')
    check('missing_terminal_no_fabrication', complete[1:], 'INCOMPLETE')
    answer = api.build_report(b'\n'.join(encode(row) for row in complete[1:]), encode(profile))
    assert answer['terminal'] is None and answer['state_name'] is None
    check('missing_health', [complete[0]] + complete[2:], 'INCOMPLETE')
    check('missing_close', complete[:-1], 'INCOMPLETE')
    check('missing_value', complete[:4] + complete[5:], 'INCOMPLETE')
    for error, name in ((2, 'clock'), (3, 'prior_service')):
        rows = [dict(state=5, error=error, overflow=False), complete[1], event(0),
                event(6, error=error), event(7, at=99, error=error)]
        answer = check(name + '_close_regression_preserved', rows, 'LOG_REVIEW_ONLY')
        assert answer['terminal']['error'] == error and answer['events'][-1]['at_ms'] == 99
        assert answer['anomalies'] == [{'index': 2, 'previous_at_ms': 100, 'at_ms': 99}]
    cases = {
        'complete_error': lambda r: r[0].update(error=2),
        'complete_overflow': lambda r: r[0].update(overflow=True),
        'fault_none': lambda r: r[0].update(state=5),
        'unknown_state': lambda r: r[0].update(state=99),
        'unknown_error': lambda r: r[0].update(error=99),
        'unknown_kind': lambda r: r[2].update(kind=99),
        'unknown_bus': lambda r: r[1].update(last_bus_state=99),
        'extra_field': lambda r: r[2].update(unexpected=1),
        'boolean_as_state': lambda r: r[0].update(state=True),
        'integer_as_flag': lambda r: r[2].update(ext=0),
        'data_short': lambda r: r[2].update(data=[0]),
        'data_oversize_byte': lambda r: r[2]['data'].__setitem__(0, 256),
        'data_bool': lambda r: r[2]['data'].__setitem__(0, False),
        'dlc_too_large': lambda r: r[2].update(dlc=9),
        'negative_time': lambda r: r[2].update(at_ms=-1),
        'uint64_overflow': lambda r: r[2].update(at_ms=1 << 64),
        'complete_regression': lambda r: r[-1].update(at_ms=99),
        'duplicate_terminal': lambda r: r.append(dict(r[0])),
    }
    for name, mutate in cases.items():
        rows = copy.deepcopy(complete)
        mutate(rows)
        check(name, rows, 'INVALID_INPUT')
    for name, raw in {
        'duplicate_key': b'{"state":0,"state":1}', 'nonfinite': b'{"x":NaN}',
        'float_overflow': b'{"x":1e999}', 'truncated_json': b'{"state":',
        'non_json_console': b'ESP boot text', 'non_object': b'[]',
        'oversize_log': b' ' * (api.LIMIT + 1), 'too_many_records': b'{}\n' * 131,
    }.items():
        check(name, [], 'INVALID_INPUT', raw=raw)
    for name, mutate in {
        'physical_approval_pollution': lambda p: p.update(hardware_approved=True),
        'expected_bool_equals_int': lambda p: p['expected'].update(supported_selected_ids=[True, 2]),
        'observed_boolean': lambda p: p['observed'].update(actual_can_id=True),
        'profile_version_bool': lambda p: p.update(schema_version=True),
        'physical_result_pollution': lambda p: p['evidence'].update(CAN_hardware_test='PASS'),
        'profile_unknown_field': lambda p: p.update(extra=True),
    }.items():
        changed = copy.deepcopy(profile)
        mutate(changed)
        check(name, [disabled], 'INVALID_INPUT', changed)
    for name, mutate in {
        'disabled_starts_can': lambda d: d.update(CAN_started=True),
        'disabled_approved': lambda d: d.update(hardware_approved=True),
        'readiness_contradiction': lambda d: d.update(profile_readiness=2),
        'tick_bool': lambda d: d.update(tick_hz=True),
        'wrong_tick': lambda d: d.update(tick_hz=100),
        'missing_bit_range': lambda d: d.update(missing=1024),
    }.items():
        changed = dict(disabled)
        mutate(changed)
        check(name, [changed], 'INVALID_INPUT')
    original_read = Path.read_bytes
    execution = report.ROOT / report.SOURCES['execution.hpp']
    execution_bytes = execution.read_bytes()
    assert execution_bytes.count(b'PowerOnIssue=1u<<9') == 1
    drifted = execution_bytes.replace(b'PowerOnIssue=1u<<9', b'PowerOnIssue=1u<<9, UnsupportedExtra=1024')

    def read_drift(path):
        return drifted if path == execution else original_read(path)

    with patch.object(Path, 'read_bytes', read_drift):
        check('unsupported_issue_member_refused', [disabled], 'INVALID_INPUT')
    test_root = report.ROOT / 'outputs/can-offline-report-090/host-temp'
    assert test_root.resolve().is_relative_to(report.ROOT.resolve()) and not test_root.is_symlink()
    test_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='can-report-host-', dir=test_root) as folder:
        base = Path(folder)
        log, profile_path, out = base / 'log.ndjson', base / 'profile.json', base / 'new'
        log.write_bytes(encode(disabled))
        profile_path.write_bytes(encode(profile))
        before = log.read_bytes(), profile_path.read_bytes()
        saved = api.emit(log, profile_path, out, True)
        assert json.loads((out / 'report.json').read_text(encoding='utf-8')) == saved
        assert 'NOT_RUN' in (out / 'report.md').read_text(encoding='utf-8')
        assert before == (log.read_bytes(), profile_path.read_bytes())
        results['new_outputs_roundtrip_inputs_unchanged'] = True
        try:
            api.emit(log, profile_path, out)
        except ValueError:
            results['existing_output_refused'] = True
        else:
            raise AssertionError('Existing output overwritten')
    return results


def main():
    results = run_cases(report)
    mutations = {
        'allow_physical_approval': ("need(profile['hardware_approved'] is False,", 'need(True,'),
        'allow_complete_error': ("need(not (state == 'Complete' and (error != 'None' or terminal['overflow'])),", 'need(True,'),
    }
    detected = {}
    original = SOURCE.read_text(encoding='utf-8')
    for name, (before, after) in mutations.items():
        assert original.count(before) == 1
        mutant = types.ModuleType('mutant_' + name)
        mutant.__file__ = str(SOURCE)
        exec(compile(original.replace(before, after), str(SOURCE), 'exec'), mutant.__dict__)
        try:
            run_cases(mutant)
        except AssertionError:
            detected[name] = True
        else:
            raise AssertionError('Semantic mutation survived: ' + name)
    print(json.dumps({'status': 'CAN_OFFLINE_HOST_PASS', 'count': len(results), 'tests': results,
                      'semantic_mutants_detected': detected, 'hardware_approved': False,
                      'native_CAN': 'NOT_RUN', 'fixtures': 'SYNTHETIC_HOST'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
