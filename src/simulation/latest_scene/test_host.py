"""SDK-free transport failure controls. All temporary runs use synthetic payloads."""
import copy
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

EXPECTED = {
    'valid_snapshot', 'missing_core_resealed', 'sha_mismatch', 'extra_inventory_resealed',
    'traversal', 'absolute_payload_path', 'directory_link', 'duplicate_json', 'nonfinite_json',
    'typed_job_version', 'typed_process_code', 'ledger_duplicate_purpose', 'ledger_failure_consumed',
    'actual_exit_reaped', 'actual_timeout_reaped', 'same_common_import_proof',
    'different_common_import_rejected', 'render_firstfault', 'terminal_inventory_extra', 'verified_module_snapshot', 'overflow_json',
    'model16_resealed', 'submission_census', 'submission_canonical_sha',
}
RETRY_EXPECTED={'prior_bad_job_digest','prior_pid_resealed','prior_bool_exit_resealed','prior_wrong_failure_resealed','prior_not_reaped_resealed','prior_missing_record_resealed','retry_empty_ledger','retry_prior_row_mismatch','retry_duplicate_run','retry_third_import','simulation_without_retry','simulation_old_failure_proof'}
EXPECTED |= RETRY_EXPECTED

LIFECYCLE_CASES = {
    'success': {},
    'collector_oserror': {'collector': OSError},
    'collector_keyboardinterrupt': {'collector': KeyboardInterrupt},
    'status_write_oserror': {'status': OSError},
    'status_write_keyboardinterrupt': {'status': KeyboardInterrupt},
    'terminal_write_oserror': {'terminal': OSError},
    'terminal_write_keyboardinterrupt': {'terminal': KeyboardInterrupt},
    'stderr_write_oserror': {'collector': OSError, 'stderr': OSError},
    'stderr_write_keyboardinterrupt': {'collector': OSError, 'stderr': KeyboardInterrupt},
    'stderr_flush_oserror': {'collector': OSError, 'flush': OSError},
    'stderr_flush_keyboardinterrupt': {'collector': OSError, 'flush': KeyboardInterrupt},
    'collector_terminal_oserror': {'collector': OSError, 'terminal': OSError},
    'collector_stderr_oserror': {'collector': OSError, 'stderr': OSError},
    'terminal_stderr_oserror': {'terminal': OSError, 'stderr': OSError},
    'triple_collector_terminal_stderr': {'collector': OSError, 'terminal': OSError, 'stderr': OSError, 'flush': OSError, 'failure_file': OSError, 'late_status': OSError},
    'triple_terminal_stderr_flush': {'terminal': OSError, 'stderr': OSError, 'flush': OSError},
    'close_oserror': {'close': OSError},
    'close_keyboardinterrupt': {'close': KeyboardInterrupt},
    'close_systemexit0': {'close_exit': 0},
    'close_systemexit7': {'close_exit': 7},
    'startup_partial_app_oserror': {'startup': OSError},
    'startup_partial_app_keyboardinterrupt': {'startup': KeyboardInterrupt},
    'postcheck_oserror': {'postcheck': OSError},
    'postcheck_keyboardinterrupt': {'postcheck': KeyboardInterrupt},
}
LIFECYCLE_COUNT = 24
LEGACY_BROKEN = {'status_write_oserror', 'status_write_keyboardinterrupt', 'stderr_write_oserror',
                 'stderr_write_keyboardinterrupt', 'stderr_flush_oserror', 'stderr_flush_keyboardinterrupt',
                 'collector_stderr_oserror', 'terminal_stderr_oserror', 'triple_collector_terminal_stderr',
                 'triple_terminal_stderr_flush'}


def lifecycle_controls(api, source, evidence):
    baseline = api.ROOT / api.OUT / '070/original/sdk.py'
    baseline_raw = baseline.read_bytes()
    api.need(api.digest(baseline_raw) == 'd1434d2e36a719ec1b247314423ca58ed9f92ef0bc0e4604bb0fb5c54f3e7726', 'Immutable 069 R2 lifecycle baseline')
    api.need(len(LIFECYCLE_CASES) == LIFECYCLE_COUNT, 'Fixed 24 lifecycle case census')
    shim = types.ModuleType('driver')
    for name in ('need', 'read', 'write', 'sha', 'load_module'):
        setattr(shim, name, getattr(api, name))
    previous_driver = sys.modules.get('driver')
    sys.modules['driver'] = shim
    versions = {'069_R2': baseline_raw, '070': source['sdk.py']}
    results = {name: {} for name in versions}

    def execute(raw, name, spec, folder):
        module = api.load_module('lifecycle_' + name, raw, baseline if name.startswith('069') else api.ROOT / 'src/simulation/latest_scene/sdk.py')
        run = Path(folder)
        out = run / 'output'
        out.mkdir()
        api.write(out / 'providers.json', {'observation': {}})
        ctx = types.SimpleNamespace(run=run, cfg={'sdk': {}}, job={'run_id': run.name, 'purpose': 'import'}, job_hash='c' * 64)
        observed = {'close_calls': 0, 'triggered': False, 'close_requested_code': None, 'stderr_write_calls': 0, 'stderr_flush_calls': 0}

        def fail(key, token):
            if key in spec:
                observed['triggered'] = True
                raise spec[key](token)

        class App:
            def close(self, **kwargs):
                observed['close_calls'] += 1
                observed['close_requested_code'] = kwargs['exit_code']
                fail('close', 'CLOSE_ORIGINAL')
                if 'close_exit' in spec:
                    raise SystemExit(spec['close_exit'])

        def postcheck(*args):
            fail('postcheck', 'POSTCHECK_ORIGINAL')

        def startup(current):
            current.app = App()
            current.observer = types.SimpleNamespace(identities=lambda: {})
            current.policy = types.SimpleNamespace(binding_contract=postcheck)
            current.api = {'binding_before': {}}
            current.kernel = types.SimpleNamespace(check_numeric=lambda *a: None)
            fail('startup', 'STARTUP_ORIGINAL')
            return current.app

        def collector(*args):
            fail('collector', 'COLLECTOR_ORIGINAL')

        def writer(path, value):
            name = Path(path).name
            if name == 'status.json':
                fail('status', 'STATUS_ORIGINAL')
                if observed['triggered']:
                    fail('late_status', 'STATUS_SECONDARY')
            if name == 'terminal.json':
                fail('terminal', 'TERMINAL_ORIGINAL')
            return api.write(path, value)

        class Stream(io.StringIO):
            def write(self, value):
                observed['stderr_write_calls'] += 1
                fail('stderr', 'STDERR_WRITE_SECONDARY')
                return super().write(value)

            def flush(self):
                observed['stderr_flush_calls'] += 1
                fail('flush', 'STDERR_FLUSH_SECONDARY')
                return super().flush()

        original_write_text = Path.write_text

        def write_text(path, *args, **kwargs):
            if path.name == 'failure.txt':
                fail('failure_file', 'FAILURE_FILE_SECONDARY')
            return original_write_text(path, *args, **kwargs)

        module.start = startup
        module.write = writer
        module.reference = lambda *args: types.SimpleNamespace(numeric=lambda *a: {})
        code = None
        outer = None
        with patch.object(sys, 'stderr', Stream()), patch.object(Path, 'write_text', write_text):
            try:
                code = module.lifecycle(ctx, collector)
            except BaseException as exc:
                outer = api.failure_text(exc)
        primary = getattr(ctx, 'first_fault', None)
        expected_code = 0 if not spec or spec == {'close_exit': 0} else 1
        expected_close = 0 if 'status' in spec else 1
        primary_token = ('STATUS_ORIGINAL' if 'status' in spec else 'STARTUP_ORIGINAL' if 'startup' in spec
                         else 'COLLECTOR_ORIGINAL' if 'collector' in spec else 'POSTCHECK_ORIGINAL' if 'postcheck' in spec
                         else 'TERMINAL_ORIGINAL' if 'terminal' in spec else 'CLOSE_ORIGINAL' if 'close' in spec else '7')
        passed = (outer is None and type(code) is int and code == expected_code and observed['close_calls'] == expected_close
                  and ((primary is None) if expected_code == 0 else (type(primary) is dict and primary_token in primary['error'])))
        return {'contract_pass': passed, 'code': code, 'outer_exception': outer, 'primary': primary,
                'actual': observed, 'lifecycle': getattr(ctx, 'lifecycle_observation', None),
                'secondary': getattr(ctx, 'lifecycle_terminal', {}).get('secondary_errors', [])}

    try:
        with tempfile.TemporaryDirectory(prefix='transport-lifecycle-', dir=evidence) as temporary:
            for version, raw in versions.items():
                for name, spec in LIFECYCLE_CASES.items():
                    folder = Path(temporary) / (version + '_' + name)
                    folder.mkdir()
                    results[version][name] = execute(raw, version + '_' + name, spec, folder)
            broken = {name for name, value in results['069_R2'].items() if not value['contract_pass']}
            api.need(broken == LEGACY_BROKEN, 'Preserved 069 R2 fixed failure census: ' + repr(sorted(broken)))
            api.need(set(results['070']) == set(LIFECYCLE_CASES) and all(r['contract_pass'] for r in results['070'].values()), 'All 24 repaired lifecycle contracts')
            # Independent entry-boundary controls requested by 070 root.
            boundary = {}

            class Unprintable(BaseException):
                def __str__(self):raise KeyboardInterrupt('format failed')
                def __repr__(self):raise OSError('repr failed')

            class BrokenStream:
                def write(self, value):raise KeyboardInterrupt('stream failed')
                def flush(self):raise OSError('flush failed')

            def broken_writer(*args):raise OSError('file failed')

            for name, error, old_primary in (
                ('native_dual_publication_failure', RuntimeError('ENTRY_ORIGINAL'), None),
                ('native_unprintable_exception', Unprintable(), None),
                ('native_preserves_primary', RuntimeError('OUTER_SECONDARY'), {'phase': 'COLLECTOR', 'error': 'FIRST_ORIGINAL'})):
                ctx = types.SimpleNamespace(run=Path(temporary), job={'purpose': 'import'}, job_hash='d' * 64)
                if old_primary is not None:ctx.first_fault = dict(old_primary)
                code = api.native_failure(ctx, Path(temporary), error, writer=broken_writer, stream=BrokenStream())
                api.need(code == 1 and ctx.native_failure_record['code'] == 1 and len(ctx.native_failure_record['publication_errors']) == 2, 'Native boundary survives failed channels')
                if old_primary is not None:api.need(ctx.first_fault == old_primary, 'Native boundary never replaces primary')
                if isinstance(error, Unprintable):api.need('formatting failed' in ctx.first_fault['error'], 'Guarded error formatting')
                boundary[name] = {'code': code, 'primary': ctx.first_fault, 'publication_errors': ctx.native_failure_record['publication_errors']}
            for name, spec in (('sdk_unprintable_exception', {'collector': Unprintable}),
                               ('sdk_existing_fault_close_systemexit0', {'collector': OSError, 'close_exit': 0})):
                folder = Path(temporary) / name
                folder.mkdir()
                value = execute(source['sdk.py'], name, spec, folder)
                if name == 'sdk_unprintable_exception':
                    api.need(value['code'] == 1 and value['outer_exception'] is None and value['actual']['close_calls'] == 1 and 'formatting failed' in value['primary']['error'], 'SDK formatting cannot bypass close')
                else:api.need(value['contract_pass'] and value['code'] == 1, 'SystemExit zero cannot upgrade prior fault')
                boundary[name] = value
            api.need(set(boundary) == {'native_dual_publication_failure', 'native_unprintable_exception', 'native_preserves_primary',
                                       'sdk_unprintable_exception', 'sdk_existing_fault_close_systemexit0'}, 'Fixed five boundary controls')
    finally:
        if previous_driver is None:sys.modules.pop('driver', None)
        else:sys.modules['driver'] = previous_driver
    report = {'status': 'HOST_LIFECYCLE_PASS', 'count': LIFECYCLE_COUNT, 'boundary_count': 5,
              'baseline_sha256': api.digest(baseline_raw), 'candidate_sha256': api.digest(source['sdk.py']),
              'legacy_broken_count': len(LEGACY_BROKEN), 'versions': results, 'boundary': boundary, 'sdk_launch': 'NOT_RUN'}
    api.write(api.ROOT / api.OUT / '071/lifecycle-host.json', report)
    return report


def run_tests(api, source=None):
    outcomes = {}
    observations = {}

    def rejected(name, action):
        try:
            action()
        except (ValueError, OSError, KeyError, TypeError):
            outcomes[name] = True
        else:
            raise AssertionError(name + ': malformed evidence accepted')

    evidence = api.ROOT / api.OUT / 'evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='transport-host-', dir=evidence) as temporary:
        base = Path(temporary).absolute()
        cfg = {'remote_root': api.parse(source['config.json'])['remote_root'], 'ssh_alias': 'host',
               'timeout_s': 600, 'sdk': {'hardware_approved': False, 'calibration_approved': False, 'training': 'NOT_RUN'},
               'hardware_approved': False, 'physical_calibration': False, 'training': 'NOT_RUN',
               'model_dir': 'models/robot-arm-urdf-v3',
               'model_submission': {'path': 'proof.json', 'sha256': api.digest(b'{}')},
               'refs': {'submission.json': {'path': 'proof.json', 'sha256': api.digest(b'{}')}}}
        payload = {'source/' + n: b'# synthetic host fixture\n' for n in api.SOURCE}
        payload['source/config.json'] = json.dumps(cfg).encode()
        payload['source/validate.py'] = (b'def verify_import(*a):return {"host_fixture":True}\n'
                                          b'def verify_simulation(*a):return {"dynamics_pass":True}\n')
        payload['source/sdk.py'] = b'def verify_records(*a):return {"host_fixture":True}\n'
        payload.update({'model/' + n: b'synthetic model' for n in api.MODEL})
        submission = {'canonical_urdf_sha256': api.digest(payload['model/robot_arm.urdf']),
                      'source_and_evidence_files': {cfg['model_dir'] + '/' + n: {'sha256': api.digest(payload['model/' + n]),
                                                    'bytes': len(payload['model/' + n])} for n in api.MODEL}}
        submission_raw = json.dumps(submission).encode()
        cfg['model_submission']['sha256'] = api.digest(submission_raw)
        cfg['refs']['submission.json']['sha256'] = api.digest(submission_raw)
        payload['source/config.json'] = json.dumps(cfg).encode()
        payload['ref/submission.json'] = submission_raw
        actual_cfg=api.parse(source['config.json']);auth=copy.deepcopy(actual_cfg['retry_authorization']);cfg['retry_authorization']=auth
        proof=api.read(api.ROOT/actual_cfg['refs'][auth['prior_proof_ref']]['path'])
        oldjob=api.parse(proof['files']['job.json']['raw_utf8'])
        for n in api.MODEL:oldjob['inputs']['model/'+n]=api.digest(payload['model/'+n])
        oldjob['common_signature']=api.common_signature(oldjob['inputs']);oldraw=json.dumps(oldjob).encode();auth['prior_job_sha256']=api.digest(oldraw)
        proof['files']['job.json']={'raw_utf8':oldraw.decode(),'sha256':api.digest(oldraw)}
        for n in ('terminal.json','exit.json','remote-shell.json'):
            value=api.parse(proof['files'][n]['raw_utf8']);value['job_sha256']=auth['prior_job_sha256'];raw=json.dumps(value).encode();proof['files'][n]={'raw_utf8':raw.decode(),'sha256':api.digest(raw)}
        raw=json.dumps(proof).encode();payload['ref/'+auth['prior_proof_ref']]=raw
        cfg['refs'][auth['prior_proof_ref']]={'path':'prior-failure.json','sha256':api.digest(raw)};payload['source/config.json']=json.dumps(cfg).encode()

        def changed_prior(data, name, mutate):
            value=api.parse(data['ref/'+auth['prior_proof_ref']])
            if name:
                record=api.parse(value['files'][name]['raw_utf8']);mutate(record);raw=json.dumps(record).encode();value['files'][name]={'raw_utf8':raw.decode(),'sha256':api.digest(raw)}
            else:mutate(value)
            raw=json.dumps(value).encode();data['ref/'+auth['prior_proof_ref']]=raw;conf=api.parse(data['source/config.json']);conf['refs'][auth['prior_proof_ref']]['sha256']=api.digest(raw);data['source/config.json']=json.dumps(conf).encode()

        def changed_auth(data):
            conf=api.parse(data['source/config.json']);conf['retry_authorization']['prior_job_sha256']='f'*64;data['source/config.json']=json.dumps(conf).encode()

        def changed_submission(data, mutation):
            changed = api.parse(data['ref/submission.json'])
            mutation(changed)
            raw = json.dumps(changed).encode()
            data['ref/submission.json'] = raw
            changed_cfg = api.parse(data['source/config.json'])
            changed_cfg['model_submission']['sha256'] = api.digest(raw)
            changed_cfg['refs']['submission.json']['sha256'] = api.digest(raw)
            data['source/config.json'] = json.dumps(changed_cfg).encode()

        def fixture(change=None):
            run = base / __import__('uuid').uuid4().hex
            data = copy.deepcopy(payload)
            if change:
                change(data)
            for key, raw in data.items():
                path = run / 'input' / key
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            inputs = {key: api.digest(raw) for key, raw in data.items()}
            job = {'schema_version': 1, 'run_id': run.name, 'purpose': 'import', 'inputs': inputs,
                   'common_signature': api.common_signature(inputs), 'plan_sha256': api.PLAN_SHA,
                   'hardware_approved': False}
            api.write(run / 'job.json', job)
            return api.snapshot(run, api.sha(run / 'job.json'))

        ctx = fixture()
        api.need(len(RETRY_EXPECTED)==12,'Fixed twelve retry controls')
        rejected('prior_bad_job_digest',lambda:fixture(changed_auth))
        rejected('prior_pid_resealed',lambda:fixture(lambda d:changed_prior(d,'terminal.json',lambda v:v.update(pid=v['pid']+1))))
        rejected('prior_bool_exit_resealed',lambda:fixture(lambda d:changed_prior(d,'exit.json',lambda v:v.update(actual_child_exit_code=True))))
        rejected('prior_wrong_failure_resealed',lambda:fixture(lambda d:changed_prior(d,'terminal.json',lambda v:v.update(primary_error='different failure'))))
        rejected('prior_not_reaped_resealed',lambda:fixture(lambda d:changed_prior(d,'exit.json',lambda v:v.update(child_state='RUNNING'))))
        rejected('prior_missing_record_resealed',lambda:fixture(lambda d:changed_prior(d,None,lambda v:v['files'].pop('exit.json'))))
        outcomes['valid_snapshot'] = set(ctx.data) == set(payload)
        rejected('missing_core_resealed', lambda: fixture(lambda data: data.pop('source/sdk.py')))
        rejected('extra_inventory_resealed', lambda: fixture(lambda data: data.update({'source/hidden.py': b'x'})))
        rejected('model16_resealed', lambda: fixture(lambda data: data.update({'model/robot_arm.urdf': b'changed but job resealed'})))
        rejected('submission_census', lambda: fixture(lambda data: changed_submission(data, lambda value: value['source_and_evidence_files'].pop(cfg['model_dir'] + '/robot_arm.urdf'))))
        rejected('submission_canonical_sha', lambda: fixture(lambda data: changed_submission(data, lambda value: value.update(canonical_urdf_sha256='a' * 64))))
        altered = fixture()
        (altered.run / 'input/source/sdk.py').write_bytes(b'changed')
        rejected('sha_mismatch', lambda: api.snapshot(altered.run, altered.job_hash))
        rejected('traversal', lambda: api.checked_path(base, '../escape'))
        rejected('absolute_payload_path', lambda: api.checked_path(base, '/escape'))
        rejected('duplicate_json', lambda: api.parse('{"x":1,"x":2}'))
        rejected('nonfinite_json', lambda: api.parse('{"x":NaN}'))
        rejected('overflow_json', lambda: api.parse('{"x":1e999}'))
        malformed = copy.deepcopy(ctx.job)
        malformed['schema_version'] = True
        rejected('typed_job_version', lambda: api.job_contract(malformed, ctx.run.name))
        imported = fixture(lambda data: data.update({'source/sdk.py': b'MARKER = "pinned"\n'}))
        (imported.run / 'input/source/sdk.py').write_bytes(b'raise RuntimeError("unverified disk code")\n')
        api.bind_sources(imported)
        api.need(importlib.import_module('sdk').MARKER == 'pinned', 'Bare module import must execute previously checked bytes')
        outcomes['verified_module_snapshot'] = True

        target = base / 'target'
        target.mkdir()
        (target / 'file').write_bytes(b'x')
        link = base / 'link'
        if os.name == 'nt':
            created = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
            api.need(created.returncode == 0, 'Host junction negative could not be established')
        else:
            link.symlink_to(target, target_is_directory=True)
        rejected('directory_link', lambda: api.file_bytes(link))
        if os.name == 'nt':
            os.rmdir(link)
        else:
            link.unlink()

        prior=api.prior_failure(ctx.cfg,ctx.data)
        def prior_ledger():return {'schema_version':1,'reservations':[{'purpose':'import','run_id':auth['prior_run_id'],'job_sha256':auth['prior_job_sha256'],'common_signature':prior['common_signature'],'reserved_unix':1.}]}
        rejected('retry_empty_ledger',lambda:api.reserve(ctx,{'schema_version':1,'reservations':[]}))
        wrong=prior_ledger();wrong['reservations'][0]['common_signature']='f'*64
        rejected('retry_prior_row_mismatch',lambda:api.reserve(ctx,wrong))
        duplicate=prior_ledger();duplicate['reservations'].append(copy.deepcopy(duplicate['reservations'][0]))
        rejected('retry_duplicate_run',lambda:api.reserve(ctx,duplicate))
        before_sim=types.SimpleNamespace(run=ctx.run,job={**ctx.job,'purpose':'simulate_capture'},job_hash=ctx.job_hash,cfg=ctx.cfg,data=ctx.data)
        rejected('simulation_without_retry',lambda:api.reserve(before_sim,prior_ledger()))
        ledger = prior_ledger()
        api.reserve(ctx, ledger)
        third=fixture();rejected('retry_third_import',lambda:api.reserve(third,copy.deepcopy(ledger)))
        bad_sim=types.SimpleNamespace(run=base/('f'*32),job={**ctx.job,'purpose':'simulate_capture'},job_hash='e'*64,cfg=ctx.cfg,data={**ctx.data,'import-proof/job.json':proof['files']['job.json']['raw_utf8'].encode()})
        rejected('simulation_old_failure_proof',lambda:api.reserve(bad_sim,copy.deepcopy(ledger)))
        rejected('ledger_duplicate_purpose', lambda: api.reserve(ctx, ledger))
        failed_ctx = fixture()
        rejected('ledger_failure_consumed', lambda: api.reserve(failed_ctx, ledger))

        native_out = base / 'actual-exit'
        native_out.mkdir()
        actual = api.run_child([sys.executable, '-I', '-B', '-c', "import sys;print('stdout-original');print('stderr-original',file=sys.stderr);raise SystemExit(7)"], native_out, 5)
        api.need(actual['actual_child_exit_code'] == actual['policy_exit_code'] == 7 and actual['child_state'] == 'REAPED'
                 and actual['timed_out'] is False, 'Actual child nonzero exit/reap')
        api.need((native_out / 'stdout.txt').read_bytes().strip() == b'stdout-original'
                 and (native_out / 'stderr.txt').read_bytes().strip() == b'stderr-original', 'Original child log bytes')
        outcomes['actual_exit_reaped'] = True
        observations['actual_exit'] = actual
        timeout_out = base / 'actual-timeout'
        timeout_out.mkdir()
        timed = api.run_child([sys.executable, '-I', '-B', '-c', 'import time;time.sleep(10)'], timeout_out, .1)
        api.need(timed['timed_out'] is True and timed['policy_exit_code'] == 124 and timed['actual_child_exit_code'] is not None
                 and timed['child_state'] == 'REAPED', 'Actual timeout termination/reap')
        outcomes['actual_timeout_reaped'] = True
        observations['actual_timeout'] = timed

        out = ctx.run / 'retrieved'
        out.mkdir()
        artifacts = {'static.json': b'{}', 'report.json': b'{}', 'model.usda': b'#usda 1.0\n'}
        for name, raw in artifacts.items():
            (out / name).write_bytes(raw)
        terminal = {'run_id': ctx.run.name, 'job_sha256': ctx.job_hash, 'purpose': 'import',
                    'pid': 102, 'parent_pid': 101, 'code': 0, 'status': 'CLOSED',
                    'files_sha256': {name: api.digest(raw) for name, raw in artifacts.items()}}
        ex = {'run_id': ctx.run.name, 'job_sha256': ctx.job_hash, 'purpose': 'import', 'pid': 101,
              'child_pid': 102, 'actual_child_exit_code': 0, 'policy_exit_code': 0, 'timed_out': False,
              'child_state': 'REAPED'}
        shell = {'run_id': ctx.run.name, 'job_sha256': ctx.job_hash, 'python_exit_code': 0}
        for name, value in (('terminal.json', terminal), ('exit.json', ex), ('remote-shell.json', shell)):
            api.write(out / name, value)
        (out / 'stdout.txt').write_bytes(b'')
        (out / 'stderr.txt').write_bytes(b'')
        api.write(ctx.run / 'transport.json', {'returncode': 0, 'timed_out': False})
        proof = {name: ((ctx.run / 'job.json') if name == 'job.json' else (out / name)).read_bytes() for name in api.PROOF}
        api.verify_import_proof(ctx, proof)
        outcomes['same_common_import_proof'] = True
        other = types.SimpleNamespace(job={**ctx.job, 'common_signature': 'a' * 64})
        rejected('different_common_import_rejected', lambda: api.verify_import_proof(other, proof))
        bad_ex = {**ex, 'actual_child_exit_code': False}
        rejected('typed_process_code', lambda: api.process_contract(ctx.job, ctx.job_hash, terminal, bad_ex, shell))
        code, result = api.consume(ctx)
        api.need(code == 0 and result['status'] == 'IMPORT_VERIFIED', 'Control import consumes')
        (out / 'stderr.txt').write_bytes(b'renderer failed to advance to the scheduled frame')
        rejected('render_firstfault', lambda: api.consume(ctx))
        (out / 'stderr.txt').write_bytes(b'')
        (out / 'unsealed-extra.json').write_bytes(b'{}')
        rejected('terminal_inventory_extra', lambda: api.consume(ctx))

    api.need(set(outcomes) == EXPECTED and all(value is True for value in outcomes.values()), 'Fixed complete host negative census')
    lifecycle = lifecycle_controls(api, source, evidence)
    report = {'status': 'HOST_TRANSPORT_PASS', 'count': len(EXPECTED) + LIFECYCLE_COUNT,
              'transport_count': len(EXPECTED), 'lifecycle_count': LIFECYCLE_COUNT, 'additional_boundary_count': 5,
              'tests': outcomes, 'observations': observations, 'lifecycle': lifecycle,
              'sdk_launch': 'NOT_RUN', 'hardware': 'NOT_RUN'}
    api.write(api.ROOT / api.OUT / '071/transport-host.json', report)
    api.write(api.ROOT / api.OUT / '071/transport-host.json', report)
    print(json.dumps({key: report[key] for key in ('status', 'count', 'transport_count', 'lifecycle_count', 'additional_boundary_count', 'sdk_launch')}))
    return 0
