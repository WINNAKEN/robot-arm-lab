"""136 local mount/gear diagnosis from captured sources and recorded actual poses."""
from __future__ import annotations

import hashlib as _boot_hash
import os as _boot_os
from pathlib import Path as _boot_path
from types import MappingProxyType as _boot_proxy

if '_SOURCE_BYTES_136' not in globals():
    _boot_root = _boot_path(__file__).absolute().parents[3]
    _boot_freeze_path = 'outputs/mp18-solid-compare-135/author/source-freeze-F2.json'
    _boot_own = ('src/simulation/mp18_mating_analysis_136/analyze.py',
                 'src/simulation/mp18_mating_analysis_136/kinematics.py',
                 'src/simulation/mp18_mating_analysis_136/test_analyze.py',
                 'src/simulation/mp18_mating_analysis_136/test_kinematics.py',
                 'docs/design/136-v4-mount-gear-cause-analysis.md')

    def _boot_read(relative):
        location = _boot_root/relative
        for ancestor in reversed((location,)+tuple(location.parents)):
            info = _boot_os.lstat(ancestor)
            if _boot_os.path.islink(ancestor) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Native reparse/symlink source ancestor rejected: '+str(ancestor))
        return location.read_bytes()

    import json as _boot_json
    _boot_bytes = {_boot_freeze_path: _boot_read(_boot_freeze_path)}
    if _boot_hash.sha256(_boot_bytes[_boot_freeze_path]).hexdigest() != '7d3a1fdf10fccb90b576430363f8fdbfca67f718c4ae1841e1e5c4b34a32b61f':
        raise ValueError('Exact approved 135 F2 source freeze')
    _boot_dependencies = _boot_json.loads(_boot_bytes[_boot_freeze_path])['files']
    for _boot_relative in _boot_own+tuple(_boot_dependencies):
        _boot_raw = _boot_read(_boot_relative)
        if _boot_relative in _boot_dependencies:
            _boot_expected = _boot_dependencies[_boot_relative]
            if len(_boot_raw) != _boot_expected['bytes'] or _boot_hash.sha256(_boot_raw).hexdigest() != _boot_expected['sha256']:
                raise ValueError('Approved135 dependency changed: '+_boot_relative)
        _boot_bytes[_boot_relative] = _boot_raw
    _SOURCE_BYTES_136 = _boot_proxy(dict(_boot_bytes))
    del _boot_bytes
    exec(compile(_SOURCE_BYTES_136[_boot_own[0]], __file__, 'exec', dont_inherit=True), globals())
else:
    import argparse
    from collections import Counter, defaultdict
    import hashlib
    import io
    import json
    import math
    import os
    from pathlib import Path, PurePosixPath, PureWindowsPath
    import re
    import sys
    import time
    import types
    from types import MappingProxyType

    import numpy as np

    k = types.ModuleType('kinematics136')
    k.__file__ = str(Path(__file__).absolute().parent/'kinematics.py')
    sys.modules[k.__name__] = k
    exec(compile(_SOURCE_BYTES_136['src/simulation/mp18_mating_analysis_136/kinematics.py'], k.__file__, 'exec', dont_inherit=True), k.__dict__)
    PLAN = 'docs/design/136-v4-mount-gear-cause-analysis.md'
    PLAN_SHA = 'b77cf1a804b0d31168c36dc417fffe438f9038c9815d6c993baaafd92bcacef2'
    F135 = 'outputs/mp18-solid-compare-135/author/source-freeze-F2.json'
    F135_SHA = '7d3a1fdf10fccb90b576430363f8fdbfca67f718c4ae1841e1e5c4b34a32b61f'
    P135 = 'outputs/mp18-solid-compare-135/Root-compare-r1/'
    COMPARISON135_SHA = 'cd6c408d9c353e907578e497469469370b3f0526eb45aa55824813eb90470227'
    MOTION = 'outputs/mp18-manipulation-133/attempts/05/retrieved/motion.ndjson'
    MODEL = 'models/robot-arm-urdf-v4/'
    CAD_PARAMETERS = 'src/cad/kmjh-gripper-v1/parameters.json'
    CAD_VERIFY = 'src/cad/kmjh-gripper-v1/verify_gripper.py'
    MOUNT_PARAMETERS = 'src/cad/arm-v3-kg1-assembly/parameters.json'
    FIT_LEDGER = 'src/cad/calibration/print-fits.json'
    FIT_LEDGER_CURRENT_SHA = '7871d39930f7cdc0d58d27d4f4910cd49246dd91f211ea795cfae7ec8b00e1e8'
    CAD_PARAMETERS_SHA = '7c116e9f9bfeb49e4b45c5495f7b5f23ce6f3c7d60c1dc66680d604c98d42b8e'
    CAD_VERIFY_SHA = '27c5362ab1554deea4ac9462b4f5b0f4898cfa2cb8b0bd17db4f3d9e6d8e3c64'
    PAIRS = {('TOOL_FLANGE', 'KG1:BASE'): 6, ('KG1:JAW_A', 'KG1:PINION'): 1, ('KG1:JAW_B', 'KG1:PINION'): 1}

    def digest(raw):
        return hashlib.sha256(raw).hexdigest()

    def parse(raw):
        def unique(pairs):
            out = {}
            for name, value in pairs:
                k.require(name not in out, 'Duplicate JSON key')
                out[name] = value
            return out
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON '+x)))

    def no_reparse(path):
        path = Path(os.path.abspath(path))
        for ancestor in (path,)+tuple(path.parents):
            try:
                info = os.lstat(ancestor)
            except FileNotFoundError:
                continue
            k.require(not os.path.islink(ancestor) and not (getattr(info, 'st_file_attributes', 0) & 0x400), 'Native reparse/symlink ancestor rejected: '+str(ancestor))

    def destination(root, name, create=False):
        k.require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name), 'Restricted fresh output slug')
        root = Path(os.path.abspath(root))
        allowed = root/'outputs'/'mp18-mating-analysis-136'
        out = allowed/name
        no_reparse(out)
        k.require(out.parent == allowed, 'Fixed136 lexical output authority')
        if create:
            allowed.mkdir(parents=True, exist_ok=True)
            no_reparse(out)
            out.mkdir(exist_ok=False)
        return out

    def recheck_bundle(root):
        for path, raw in _SOURCE_BYTES_136.items():
            no_reparse(root/path)
            k.require((root/path).read_bytes() == raw, 'Captured source drift: '+path)

    def source_manifest():
        return {p: {'sha256': digest(b), 'bytes': len(b)} for p, b in _SOURCE_BYTES_136.items()}

    def dependency135(root):
        frozen = parse(_SOURCE_BYTES_136[F135])
        module = types.ModuleType('frozen_compare135_for136')
        module.__file__ = str(root/'src/simulation/mp18_solid_compare_135/compare.py')
        module._SOURCE_BYTES_135 = MappingProxyType({p: _SOURCE_BYTES_136[p] for p in frozen['files']})
        sys.modules[module.__name__] = module
        exec(compile(module._SOURCE_BYTES_135['src/simulation/mp18_solid_compare_135/compare.py'], module.__file__, 'exec', dont_inherit=True), module.__dict__)
        return module

    def inputs(root):
        base = dependency135(root)
        producer = base.Producer(root)
        producer.read(PLAN, PLAN_SHA)
        producer.read(F135, F135_SHA)
        producer.read('outputs/mp18-solid-compare-135/review/L4-r2/report.json', 'b7483f8f6e868fa564282cb325eca222332f64142ad9e480e0f5a9ec6565593a')
        producer.read('outputs/mp18-solid-compare-135/review/L4-r2/publication.json', '86b5088f9ebcd53b4b439375fbaa80f31b8a87450c6a298ab4965f30c8e09bd5')
        producer.read('outputs/mp18-solid-compare-135/Root-final-result.json', 'a446343e444e5014dbbdb394b7efb2608e6016db8b071d44c8c93c64be2341dd')
        previous = parse(producer.read(P135+'comparison.json', COMPARISON135_SHA))
        k.require(previous['unit'] == 135 and previous['selected_processing_complete'] is True and previous['selected_cases'] == 91, 'Completed actual135 scope')
        for p, e in previous['artifacts'].items():
            k.require(PurePosixPath(p).name == p and not PureWindowsPath(p).drive, 'Artifact leaf only')
            producer.read(P135+p, e['sha256'], e['bytes'])
        k.require(parse(producer.raw[P135+'source-manifest.json']) == parse(_SOURCE_BYTES_136[F135])['files'], '135 output/source frozen equivalence')
        producer.source(MODEL+'robot_arm.urdf')
        producer.source(MODEL+'numeric-ledger.json')
        params = parse(producer.read(CAD_PARAMETERS, CAD_PARAMETERS_SHA))
        generation = producer.provenance['input_census']
        k.require(generation[CAD_PARAMETERS]['sha256'] == CAD_PARAMETERS_SHA, 'CAD parameter generation binding')
        producer.read(CAD_VERIFY, CAD_VERIFY_SHA)
        historical_verify = generation[CAD_VERIFY]['sha256']
        k.require(historical_verify != CAD_VERIFY_SHA, 'Explicit recorded verifier version drift')
        mount_intent = parse(producer.read(MOUNT_PARAMETERS, generation[MOUNT_PARAMETERS]['sha256'], generation[MOUNT_PARAMETERS]['bytes']))
        current_fits = parse(producer.read(FIT_LEDGER, FIT_LEDGER_CURRENT_SHA))
        fit_pending = current_fits['materials']['PLA']['pending']
        return base, producer, previous, params, {'current_verify_sha256': CAD_VERIFY_SHA,
            'generation_verify_sha256': historical_verify, 'current_matches_generation': False,
            'current_code_used_only_as_current_intent_readonly': True, 'CAD_generator_or_verifier_executed': False,
            'mount_parameters_generation_pin_matches': True, 'mount_design_intent': mount_intent['mount'],
            'historical_mount_check_limit_mm3': mount_intent['checks']['grip_hit_mm3'],
            'historical_assembly_outputs_used_as_new_v4_evidence': False,
            'current_fit_ledger_sha256': FIT_LEDGER_CURRENT_SHA,
            'generation_fit_ledger_sha256': generation[FIT_LEDGER]['sha256'],
            'current_fit_matches_generation': FIT_LEDGER_CURRENT_SHA == generation[FIT_LEDGER]['sha256'],
            'current_pending_gear_fit_values': {n:{key:fit_pending[n][key]for key in ('value','status')}
                for n in ('gear_thinning_pinion','gear_thinning_rack')},
            'generation_fit_values_not_inferred_from_current_ledger': True}

    def select_printed(cases):
        rows = []
        seen = set()
        for case in cases:
            for pair in case['pairs']:
                if pair['category'] != 'PRINTED_STL_MODEL_OVERLAP':
                    continue
                key = (pair['part_a'], pair['part_b'])
                ident = (case['step'],)+key
                k.require(key in PAIRS and ident not in seen, 'Exact unique printed pair/step')
                seen.add(ident)
                rows.append({'case': case, 'part_a': key[0], 'part_b': key[1], 'original135': pair})
        k.require(len(rows) == 8 and Counter((x['part_a'], x['part_b']) for x in rows) == Counter(PAIRS), 'Exactly eight original printed witnesses in three pairs')
        k.require(all(x['case']['step'] == 6840 for x in rows if 'JAW_' in x['part_a']), 'Two original57s gear witnesses')
        return rows

    def motion_analysis(raw, joints, geometry, steps):
        picked, measurements, peaks, phase_counts = {}, [], {}, Counter()
        residual_peaks = {}
        names = {'J'+str(i) for i in range(1, 7)} | set(k.GRIPPER)
        for i, line in enumerate(io.BytesIO(raw)):
            row = parse(line)
            k.require(type(row['step']) is int and row['step'] == i and abs(k.number(row['time_s'])-i/120) < 1e-8, 'Contiguous11161 step/time')
            k.require(row['clock']['lab_step'] == i and abs(k.number(row['clock']['engine_time_s'])-row['time_s']) < 1e-8, 'Actual clock binding')
            k.require(set(row['q']) == set(row['targets']) == names, 'Actual/target joint census')
            q = {n: k.number(v) for n, v in row['q'].items()}
            targets = {n: k.number(v) for n, v in row['targets'].items()}
            k.require(len(row['body_poses']) == 11 and {b['name'] for b in row['body_poses']} == set(k.OWNERS), 'Exactly11 actual bodies')
            bodies = {p['name']: k.body_pose(p) for p in row['body_poses']}
            couplings = k.coupling(q, targets, geometry['mimic_rad_per_m'], geometry['mimic_offset_rad'], geometry['radius_mm'])
            phase = row['manipulation']['phase']
            k.require(isinstance(phase, str) and phase, 'Actual task phase')
            phase_counts[phase] += 1
            record = {'step': i, 'time_s': row['time_s'], 'phase': phase, **couplings}
            measurements.append(record)
            for metric, value in couplings.items():
                if metric not in peaks or abs(value) > abs(peaks[metric]['value']):
                    peaks[metric] = {'value': value, 'absolute_value': abs(value), 'step': i, 'time_s': row['time_s'], 'phase': phase}
            actual_mount = k.inverse(bodies['Link6'])@bodies['KG1']
            diagnostics = {'KG1_mount': k.residual(actual_mount, joints['KG1_mount']['zero'])}
            for name in k.GRIPPER:
                actual = k.inverse(bodies['KG1'])@bodies[joints[name]['child']]
                diagnostics[name] = {**k.residual(actual, k.joint_transform(joints[name], q[name])),
                                     **k.project_joint(actual, joints[name], q[name])}
            for name, values in diagnostics.items():
                for metric, value in values.items():
                    if isinstance(value, (int, float)) and metric not in ('projected_q', 'logged_q'):
                        key = name+':'+metric
                        if key not in residual_peaks or abs(value) > abs(residual_peaks[key]['value']):
                            residual_peaks[key] = {'value': value, 'step': i, 'time_s': row['time_s']}
            if i in steps:
                picked[i] = {'row': row, 'bodies': bodies, 'coupling': record, 'pose_diagnostics': diagnostics}
        k.require(len(measurements) == 11161 and set(picked) == steps, 'Full original11161 and all selected steps')
        by_phase = {}
        for phase, count in phase_counts.items():
            rows = [v for v in measurements if v['phase'] == phase]
            by_phase[phase] = {'rows': count, 'start_s': rows[0]['time_s'], 'end_s': rows[-1]['time_s'],
                'max_abs_phase_A_rad': max(abs(v['phase_A_rad']) for v in rows),
                'max_abs_phase_B_rad': max(abs(v['phase_B_rad']) for v in rows)}
        return picked, {'rows': 11161, 'peaks': peaks, 'by_phase': by_phase, 'actual_pose_vs_logged_q_residual_peaks': residual_peaks,
            'new_safety_acceptance_thresholds': False, 'prior133_acceptance_reclassified': False}, measurements

    def compare_variants(base, parts, selected, picked, joints, geometry):
        rows = []
        for item in selected:
            case = item['case']; observed = picked[case['step']]
            a, b = [parts[item[n]]['solid'] for n in ('part_a', 'part_b')]
            for p in case['poses']:
                actual = next(x for x in observed['row']['body_poses'] if x['name'] == p['owner'])
                k.require(actual['position'] == p['position_m'] and actual['orientation_wxyz'] == p['original_orientation_wxyz'], 'Original135/actual133 pose exactly bound')
            actual_t = k.inverse(observed['bodies'][a.owner])@observed['bodies'][b.owner]
            variants = {'actual_body_poses': actual_t}
            diagnostic = {}
            if item['part_a'] == 'TOOL_FLANGE':
                variants['URDF_nominal_mount'] = joints['KG1_mount']['zero']
                ledger = np.asarray(geometry['nominal_mount_ledger_mm'], dtype=float).copy()
                ledger[:3, 3] *= .001
                variants['numeric_ledger_nominal_mount'] = ledger
                diagnostic['actual_mount_vs_nominal'] = k.residual(actual_t, joints['KG1_mount']['zero'])
            else:
                q = dict(observed['row']['q']); targets = observed['row']['targets']
                jaw = 'KG1_slide_A' if a.owner == 'KG1_A' else 'KG1_slide_B'
                variant_q = {'FK_logged_actual_q': q,
                    'counterfactual_pinion_coupled_to_this_actual_jaw': dict(q, KG1_pinion=geometry['mimic_rad_per_m']*q[jaw]+geometry['mimic_offset_rad']),
                    'FK_logged_targets': targets,
                    'nominal_closed_source_u0': {n: (-.02 if n != 'KG1_pinion' else geometry['mimic_rad_per_m']*(-.02)) for n in k.GRIPPER},
                    'nominal_URDF_q0_open40mm': {n: 0. for n in k.GRIPPER}}
                coupled = variant_q['counterfactual_pinion_coupled_to_this_actual_jaw']
                for label, sign in [('phase_control_minus_1deg', -1), ('phase_control_plus_1deg', 1)]:
                    variant_q[label] = dict(coupled, KG1_pinion=coupled['KG1_pinion']+sign*math.pi/180)
                for label, positions in variant_q.items():
                    fk = k.gripper_fk(joints, positions)
                    variants[label] = k.inverse(fk[a.owner])@fk[b.owner]
                diagnostic.update(jaw=jaw, actual_joint_values={n:q[n] for n in k.GRIPPER},
                    logged_targets={n:targets[n] for n in k.GRIPPER}, coupling=observed['coupling'],
                    actual_pose_vs_logged_q=observed['pose_diagnostics'], variant_joint_values=variant_q,
                    counterfactual_is_simulated_new_runtime=False)
            evaluated = {}
            for label, transform in variants.items():
                mm = k.millimetres(transform)
                value = base.solids.compare_pair(a, b, mm)
                k.require(value['category'] != base.solids.UNKNOWN, 'Original solid/Boolean UNKNOWN in diagnostic variant')
                evaluated[label] = {'relative_b_in_a_mm': mm.tolist(), **value}
                if item['part_a'] == 'TOOL_FLANGE' and value['volume_mm3'] > 0:
                    overlap = a.manifold ^ b.manifold.transform(mm[:3, :])
                    bounds = np.asarray(overlap.bounding_box(), dtype=float).reshape(2, 3)
                    k.require(np.isfinite(bounds).all(), 'Finite actual intersection bounds')
                    corners = np.array([[bounds[i,0], bounds[j,1], bounds[h,2]] for i in (0,1) for j in (0,1) for h in (0,1)])
                    g_from_a = k.inverse(joints['KG1_mount']['zero'])
                    moved = corners@g_from_a[:3,:3].T+g_from_a[:3,3]*1000
                    evaluated[label]['intersection_bounds_Link6_mm'] = bounds.tolist()
                    evaluated[label]['intersection_bounds_nominal_G_mm'] = [moved.min(axis=0).tolist(), moved.max(axis=0).tolist()]
                    evaluated[label]['localization_mechanism'] = 'BOUNDS_OF_BOOLEAN_INTERSECTION_NOT_PHYSICAL_MEASUREMENT'
            actual_v = evaluated['actual_body_poses']['volume_mm3']; old_v = item['original135']['volume_mm3']
            k.require(abs(actual_v-old_v) <= max(1e-7, abs(old_v)*1e-8), 'Original135 actual-volume reproduction')
            hypotheses = {'actual_positive_reproduced': actual_v > .01,
                'confirmed_physical_or_design_defect': False, 'automatic_model_repair_performed': False}
            if 'URDF_nominal_mount' in evaluated:
                nominal_v = evaluated['URDF_nominal_mount']['volume_mm3']
                hypotheses.update(nominal_snapshot_positive_volume=nominal_v > .01,
                    dynamic_pose_error_alone_cannot_explain_nominal_positive=nominal_v > .01,
                    intended_mount_contact_or_export_geometry='UNRESOLVED')
            else:
                coupled_v = evaluated['counterfactual_pinion_coupled_to_this_actual_jaw']['volume_mm3']
                hypotheses.update(actual_positive_but_coupled_counterfactual_zero=(actual_v > .01 and coupled_v == 0),
                    phase_tracking_contribution_supported_by_counterfactual=(actual_v > .01 and coupled_v < actual_v),
                    repaired_runtime_or_physical_gear_contact='NOT_RUN_NOT_VERIFIED')
            rows.append({'step':case['step'],'time_s':case['time_s'],'source_pair':case['pair_id'],
                'part_a':a.id,'part_b':b.id,'original135_volume_mm3':old_v,
                'variants':evaluated,'diagnostics':diagnostic,'hypotheses':hypotheses})
        k.require(len(rows) == 8, 'Eight diagnostic cases completed')
        return rows

    def render_report(summary, cases, coupling):
        lines = ['# 136 — 장착면·기어 결합 원인 대조', '',
            '원133/05 기록과 동결된 원본 v4 메시를 사용한 로컬 진단이다. 원모델·동작 기준·실물은 변경하지 않았다.',
            '전11161행의 결합·추종을 분석했고, 입체 대조는 원135 printed 양성8표본/3쌍에 한정했다.',
            'actual body pose, logged q의 FK, logged targets의 FK, 결합을 강제한 반사실을 서로 구분한다.', '',
            '| 부품쌍 / 시간 | 실제 mm³ | 공칭 mount 또는 결합 반사실 mm³ | logged-q FK mm³ | target FK mm³ |', '|---|---:|---:|---:|---:|']
        for c in cases:
            v = c['variants']; middle = 'URDF_nominal_mount' if 'URDF_nominal_mount' in v else 'counterfactual_pinion_coupled_to_this_actual_jaw'
            values = [v['actual_body_poses']['volume_mm3'],v[middle]['volume_mm3'],v.get('FK_logged_actual_q',{}).get('volume_mm3'),v.get('FK_logged_targets',{}).get('volume_mm3')]
            pretty = ['—' if z is None else f'{z:.12g}' for z in values]
            lines.append(f"| {c['part_a']} / {c['part_b']} @ {c['time_s']:.9g}s | "+' | '.join(pretty)+' |')
        lines += ['', '## 결합과 추종', '',
            'epsilon = 실제 피니언각 − (XML mimic multiplier × 실제 jaw 이동 + offset). 등가 rack 오차는 epsilon × r(mm)이다.',
            '각 조인트가 목표를 추종하는 정도와 실제 피니언–jaw 결합 오차는 별도이다. 허용 기준을 새로 만들거나 원133 수용을 소급 변경하지 않았다.',
            f"피치 반경 {summary['geometry']['radius_mm']}mm, XML 비율 {summary['geometry']['mimic_rad_per_m']}rad/m.", '',
            '| metric | signed peak | 시간 s |', '|---|---:|---:|']
        for name,p in coupling['peaks'].items(): lines.append(f"| {name} | {p['value']:.12g} | {p['time_s']:.9g} |")
        mount = [c for c in cases if c['part_a']=='TOOL_FLANGE']; gear=[c for c in cases if c['part_a']!='TOOL_FLANGE']
        lines += ['', '## 가설의 관측 범위', '',
            f"공칭 mount에서도 양성 부피가 있는 표본: {sum(c['hypotheses']['nominal_snapshot_positive_volume'] for c in mount)}/6. 공칭 양성이면 동적 자세 오차만으로 원인을 설명할 수 없다. 장착 의도·원형상/수출 메시의 세부 원인은 미확정이다.",
            f"실제 양성이 결합 반사실에서 정확히0이 된 손가락 표본: {sum(c['hypotheses']['actual_positive_but_coupled_counterfactual_zero'] for c in gear)}/2. 이는 수치 진단이며 해당 제어를 적용한 실제 새 시뮬/실물 성공이 아니다.",
            '실제/공칭 변환, projected joint의 off-axis 잔차, 각 variant q, 원pair/시간/부피는 cases.json에 보존했다.',
            '현재 verify_gripper.py는 generation provenance와 해시가 다르므로 과거에 실행된 verifier라는 근거로 쓰지 않았다. parameter의 generation 일치와 현재 설계 의도 조회를 별도로 기록했다.',
            '현재 끼움 원장도 generation 해시와 다르다. 현재 pending 값을 과거 메시의 보정값으로 간주하지 않았으며, 동결된 원본 visual 메시로만 입체 계산했다.',
            'geometry 원부품은 닫힘 u=0이며 URDF q=0는 벌림40mm이다. 원body-local 메시에 CAD 변환이나 벌림을 중복 적용하지 않았다.', '',
            '## 제약과 보존', '',
            '0<V≤0.01mm³는 SMALL_VOLUME_UNCERTAIN이다. 이는 실물 공차가 아니다. 같은 Manifold 커널을 사용하며 이중 커널 독립 증명을 주장하지 않는다.',
            '표면 접촉·연속 동작의 전체 무간섭·전체 v4·실물 기어 치합/안전을 인증하지 않는다. 현재 출력 작업 버전도 UNKNOWN이다.',
            '원135의 다른 표본/제외 부품/미판독 범위와133 수용·영상, 원CAD/URDF/STL/원장·gain/cap/기준은 그대로 보존했다.',
            '새 SSH/SDK/Drive·CAN/RS485·포트·급전·플래시·설치·프린터 조작·설정/Git 작업은 없다.',
            '입력/실제 실행 source byte 해시는 input-manifest.json/source-manifest.json에, 전기록 요약과 peak는 coupling-summary.json에 있다.', '']
        return '\n'.join(lines)

    def run(name, root=None, before_publish=None):
        started = time.monotonic()
        root = Path(__file__).absolute().parents[3] if root is None else Path(os.path.abspath(root))
        recheck_bundle(root)
        out = destination(root, name, create=True)
        recheck_bundle(root)
        base, producer, previous, parameters, verifier = inputs(root)
        parts, partitions = base.partition_originals(producer)
        selected = select_printed(parse(producer.raw[P135+'cases.json']))
        ledger = parse(producer.raw[MODEL+'numeric-ledger.json'])
        joints, geometry = k.parse_urdf(producer.raw[MODEL+'robot_arm.urdf'], ledger, parameters)
        picked, coupling_summary, measurements = motion_analysis(producer.raw[MOTION], joints, geometry, {x['case']['step'] for x in selected})
        cases = compare_variants(base, parts, selected, picked, joints, geometry)
        summary = {'unit':136,'schema':'mp18-mating-cause-analysis-v1','selected_processing_complete':True,
            'selected_cases':len(cases),'selected_unique_part_pairs':len({(c['part_a'],c['part_b']) for c in cases}),
            'actual_motion_rows':coupling_summary['rows'],'source_run_id':base.RUN,'source_job_sha256':base.JOB,
            'original135_reproduction_complete':True,'geometry':geometry,'verifier_provenance':verifier,
            'scope':'8selected printed part-pose samples;11161 logged coupling/kinematic rows;not a whole-model collision test',
            'new_runtime_counterfactual_verified':False,'new_acceptance_criteria':False,'prior133_acceptance_changed':False,
            'model_geometry_repaired':False,'physical_safety_certified':False,'hardware_approved':False,
            'current_print_job_identity':'UNKNOWN','same_Boolean_kernel_independent_validation':False,
            'source_binding':'IMMUTABLE_CAPTURED_BYTES_COMPILED_FOR_136_AND_APPROVED135_DEPENDENCIES',
            'elapsed_s':time.monotonic()-started,
            'reproduction':'printforge/.venv/Scripts/python.exe -X utf8 -I -B -u robot-arm-lab/src/simulation/mp18_mating_analysis_136/analyze.py --name NEW_UNIQUE_SLUG'}
        if before_publish is not None: before_publish(producer, out)
        def check():
            k.require(destination(root,name)==out,'Publication output changed')
            recheck_bundle(root);producer.recheck()
        def write(leaf,value,plain=False):
            check()
            raw=value.encode('utf-8') if plain else (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
            with(out/leaf).open('xb')as f:f.write(raw)
        check()
        write('cases.json',cases)
        write('coupling-summary.json',coupling_summary)
        write('coupling-rows.json',measurements)
        write('source-manifest.json',source_manifest())
        write('input-manifest.json',producer.manifest)
        write('cause-report.md',render_report(summary,cases,coupling_summary),plain=True)
        check()
        summary['artifacts']={p.name:{'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size}for p in out.iterdir()if p.is_file()}
        write('analysis.json',summary)  # completion is deliberately last
        return summary,out

    def main():
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--name',required=True)
        args=parser.parse_args()
        summary,out=run(args.name)
        print(json.dumps({'completed':summary['selected_processing_complete'],'path':str(out),'cases':summary['selected_cases'],'rows':summary['actual_motion_rows']},ensure_ascii=False),flush=True)

    if __name__=='__main__': main()
