"""135 local original-solid comparison. No SDK, CAD producer or device execution."""
from __future__ import annotations

# Bootstrap captures the whole owned source bundle, then executes ONLY those
# immutable bytes. In particular, a later filesystem read cannot relabel code
# already imported by Python as though the replacement bytes had been executed.
import os as _boot_os
import pathlib as _boot_path
from types import MappingProxyType as _boot_proxy

if '_SOURCE_BYTES_135' not in globals():
    _boot_root = _boot_path.Path(__file__).absolute().parents[3]
    _boot_files = ('src/simulation/mp18_solid_compare_135/compare.py',
                   'src/simulation/mp18_solid_compare_135/solids.py',
                   'src/simulation/mp18_solid_compare_135/test_compare.py',
                   'src/simulation/mp18_solid_compare_135/test_solids.py',
                   'docs/design/135-v4-original-solid-comparison.md')
    _boot_bytes = {}
    for _boot_relative in _boot_files:
        _boot_location = _boot_root / _boot_relative
        for _boot_ancestor in (_boot_location,) + tuple(_boot_location.parents):
            _boot_info = _boot_os.lstat(_boot_ancestor)
            if _boot_os.path.islink(_boot_ancestor) or (getattr(_boot_info, 'st_file_attributes', 0) & 0x400):
                raise ValueError('Native reparse/symlink source ancestor rejected: '+str(_boot_ancestor))
        _boot_bytes[_boot_relative] = _boot_location.read_bytes()
    _SOURCE_BYTES_135 = _boot_proxy(dict(_boot_bytes))
    del _boot_bytes
    # Recompile this module too: its running outer bootstrap may have been read
    # by the interpreter earlier. Product functions all come from this snapshot.
    exec(compile(_SOURCE_BYTES_135[_boot_files[0]], __file__, 'exec', dont_inherit=True), globals())
else:

    import argparse
    import hashlib
    import importlib.metadata
    import io
    import json
    import logging
    import os
    import pathlib
    import re
    import sys
    import time
    from collections import Counter

    import numpy as np

    import types
    # The sibling is executed from the captured bytes, never reopened by import.
    _solid_relative = 'src/simulation/mp18_solid_compare_135/solids.py'
    solids = types.ModuleType('solids')
    solids.__file__ = str(pathlib.Path(__file__).absolute().parent/'solids.py')
    sys.modules['solids'] = solids
    exec(compile(_SOURCE_BYTES_135[_solid_relative], solids.__file__, 'exec', dont_inherit=True), solids.__dict__)

    RUN = '850124eb93cc4cc4945ee02c3aa1ed0d'
    JOB = '816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae'
    F6 = 'outputs/mp18-manipulation-133/author/source-freeze.json'
    F6_SHA = '3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f'
    NATIVE = 'outputs/mp18-manipulation-133/attempts/05/native-result.json'
    NATIVE_SHA = 'c4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2'
    AUDIT_ROOT = 'outputs/mp18-collision-audit-134/Root-audit-r1/'
    F2 = 'outputs/mp18-collision-audit-134/author/source-freeze-F2.json'
    F2_SHA = 'ef79786a074342406e7b750b476b3e41bd8a5c7f0f485a090ecdcb5410996cea'
    PLAN = 'docs/design/135-v4-original-solid-comparison.md'
    PLAN_SHA = 'bdf93df84c72f3e5ed5e5484db71b157be3a9a0baae8a7d9c5f55bd4cb06e08f'
    MODEL = 'models/robot-arm-urdf-v4/'
    JAW = 'src/simulation/mp18_manipulation_133/jaw_components.json'
    NAMES = ('Base', 'Link1', 'Link2', 'Link3', 'Link4', 'Link5', 'Link6', 'KG1', 'KG1_A', 'KG1_B', 'KG1_R')
    POSITIVE_134 = 'VERIFIED_SOURCE_ENVELOPE_OVERLAP_AT_SAMPLED_POSE'
    AUDIT_PINS = {
        'audit.json': ('1322ddfc994c9648361bcbe1bb31aa8933d0d8fb438007fa3815aa4b96fa4afc', 13105),
        'audit.md': ('6fb6df95f391e42ab2b9b978bd1e4642599cd5ae5d66896ece6ed5c308416972', 2841),
        'broadphase.json': ('d66f17d9afd6d15a68a0f1842cf87caaefd6d3c190f0b3921bc8e41da6c45ce6', 236436),
        'envelopes.json': ('49a2f173ae7681f5ecfc2103dfbeae14ed4388febb7e51c189434c348ec42666', 33263),
        'input-manifest.json': ('d36cd7746e3229ef4d87742530d12a4c8b4a9ba0415186cc5654552a2cdd1403', 4252),
        'pair-registry.json': ('c4caa0f6183699444d02d6931ab3c0ad9acc89119de0400ee6c19566ec5e4082', 83268),
        'source-manifest.json': ('a77d5e05c6a3fd5c2c0982ddb526b11e8a47407a444186018ab365b367233e1d', 830),
        'witnesses.json': ('1d7aeb1537b08b96288235d55b0ad1b1ea196aa0560db155e234bcab34003a76', 468647),
    }


    def digest(raw):
        return hashlib.sha256(raw).hexdigest()


    def parse(raw):
        def unique(items):
            result = {}
            for key, value in items:
                solids.require(key not in result, 'Duplicate JSON key: ' + key)
                result[key] = value
            return result
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))


    def no_reparse(path):
        """Inspect lexical native ancestors BEFORE any resolve; includes root and leaf."""
        path = pathlib.Path(os.path.abspath(path))
        for ancestor in reversed((path,) + tuple(path.parents)):
            try:
                info = os.lstat(ancestor)
            except FileNotFoundError:
                continue
            solids.require(not os.path.islink(ancestor) and not (getattr(info, 'st_file_attributes', 0) & 0x400),
                           'Native reparse/symlink ancestor rejected: ' + str(ancestor))


    def output_destination(root, name, create=False):
        solids.require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name), 'Restricted output leaf required')
        root = pathlib.Path(os.path.abspath(root))
        # Authority is this literal repo-relative location. A mutable resolved OUTPUT_ROOT cannot redefine it.
        allowed = root / 'outputs' / 'mp18-solid-compare-135'
        destination = allowed / name
        no_reparse(destination)
        solids.require(destination.parent == allowed and destination != allowed, 'Fixed 135 lexical authority')
        if create:
            allowed.mkdir(parents=True, exist_ok=True)
            no_reparse(destination)
            destination.mkdir(exist_ok=False)
        return destination


    def validate_native(native):
        solids.require(native['unit'] == 133 and native['attempt'] == 5 and native['run_id'] == RUN and
                       native['job_sha256'] == JOB and native['source_freeze_sha256'] == F6_SHA and
                       native['runtime_accepted'] is True and native['SDK_reaped'] is True and
                       native['hardware_approved'] is False and native['terminal_status'] == 'COMPLETE_PRE_CLOSE',
                       'Pinned actual133 runtime identity/acceptance')


    class Producer:
        def __init__(self, root):
            self.root = pathlib.Path(os.path.abspath(root))
            self.raw, self.manifest = {}, {}
            self.read(PLAN, PLAN_SHA)
            self.read(F6, F6_SHA)
            self.freeze = parse(self.raw[F6])
            self.read(NATIVE, NATIVE_SHA)
            native = parse(self.raw[NATIVE])
            validate_native(native)
            self.read(F2, F2_SHA)
            for rel, item in parse(self.raw[F2])['files'].items():
                self.read(rel, item['sha256'], item['bytes'])
            self.read('outputs/mp18-collision-audit-134/review/L4-r2/report.json',
                      'f8c550f17bb12ff66aa5166867bdf47737eaffb8d7fffc10c5dc1d321ea343b1')
            self.read('outputs/mp18-collision-audit-134/review/L4-r2/publication-complete.json',
                      '347ebc63f4823e92d24420a45bfc2ac8c23860ecd7be2b0e56ca7666debe5d84')
            for name, (sha, size) in AUDIT_PINS.items():
                self.read(AUDIT_ROOT + name, sha, size)
            old_inputs = parse(self.raw[AUDIT_ROOT + 'input-manifest.json'])
            for rel, item in old_inputs.items():
                self.read(rel, item['sha256'], item['bytes'])
            solids.require(parse(self.raw[AUDIT_ROOT+'source-manifest.json']) == parse(self.raw[F2])['files'], '134 source manifest/freeze equivalence')
            self.ledger = parse(self.source(MODEL+'asset-ledger.json'))
            self.provenance = parse(self.source(MODEL+'provenance.json'))
            self.read('src/simulation/urdf_mp18_v4/assets.py', self.provenance['assets_code_sha256'])
            # Source producer and input census are read as bytes, NEVER imported or executed.
            for part in self.ledger['geometry_components']:
                s = part['source']
                self.read(s['path'], s['sha256'])
            self.envelopes = parse(self.raw[AUDIT_ROOT+'envelopes.json'])
            self.registry = parse(self.raw[AUDIT_ROOT+'pair-registry.json'])['interbody']
            self.witnesses = parse(self.raw[AUDIT_ROOT+'witnesses.json'])
            self.jaws = parse(self.source(JAW))

        def read(self, relative, sha, size=None):
            path = pathlib.PurePosixPath(relative)
            solids.require(not path.is_absolute() and not pathlib.PureWindowsPath(relative).drive and
                           '..' not in path.parts and '\\' not in relative, 'Restricted input path')
            location = self.root / relative
            no_reparse(location)
            raw = location.read_bytes()
            solids.require(digest(raw) == sha and (size is None or len(raw) == size), 'Input SHA/bytes mismatch: '+relative)
            if relative in self.raw:
                solids.require(self.raw[relative] == raw, 'Input changed during consumption: '+relative)
            self.raw[relative], self.manifest[relative] = raw, {'sha256': digest(raw), 'bytes': len(raw)}
            return raw

        def source(self, relative):
            item = self.freeze['files'][relative]
            return self.read(relative, item['sha256'], item['bytes'])

        def recheck(self):
            for relative, item in self.manifest.items():
                no_reparse(self.root / relative)
                raw = (self.root / relative).read_bytes()
                solids.require(digest(raw) == item['sha256'] and len(raw) == item['bytes'], 'Input changed before publication: '+relative)


    def partition_originals(producer):
        components = producer.ledger['geometry_components']
        solids.require(len(components) == len({p['id'] for p in components}) == 274, '274 unique original part IDs')
        solids.require(Counter(p['source']['kind'] for p in components) == Counter(PRINTED_STL=111, PURCHASED_PRIMITIVE=49, CABLE_APPROX=114), 'Original kind census')
        solids.require({p['link'] for p in components} == set(NAMES) and sum(bool(p['collision_included']) for p in components) == 244,
                       '11 owners / 244 included original parts')
        parts, partitions = {}, []
        for owner in NAMES:
            rel = MODEL+'meshes/'+owner+'.stl'
            triangles = solids.binary_triangles(producer.source(rel))
            offset = 0
            for record in (p for p in components if p['link'] == owner):
                count = record['triangles']
                solids.require(type(count) is int and count > 0 and offset+count <= len(triangles), 'Original face partition range')
                raw = triangles[offset:offset+count]
                bounds = np.array([raw.min(axis=(0, 1)), raw.max(axis=(0, 1))])
                bounds_error = float(np.max(np.abs(bounds - np.asarray(record['bounds_m']))))
                solids.require(bounds_error <= solids.BOUNDS_M_ATOL and record['scale_to_m'] == .001, 'Original part bounds/SI: '+record['id'])
                source = record['source']
                source_evidence = {'kind': source['kind'], 'path': source['path'], 'sha256': source['sha256'],
                                   'current_source_hash_matches_ledger': True, 'current_physical_print_job_identity': 'UNKNOWN'}
                if source['path'].lower().endswith('.stl'):
                    original = solids.binary_triangles(producer.raw[source['path']])
                    matrix = np.asarray(record['T_link_from_source_mm'], dtype=float)
                    solids.require(matrix.shape == (4, 4) and np.isfinite(matrix).all() and
                                   np.allclose(matrix[3], [0, 0, 0, 1], atol=0, rtol=0), 'Original source transform')
                    transformed = (original @ matrix[:3, :3].T + matrix[:3, 3]) * .001
                    solids.require(transformed.shape == raw.shape, 'Source/canonical triangle count')
                    error = float(np.max(np.abs(transformed-raw)))
                    solids.require(error <= solids.BOUNDS_M_ATOL, 'Source/canonical transformed triangles: '+record['id'])
                    source_evidence.update(transformed_triangle_max_error_m=error, verification='RAW_STL_TRIANGLE_TRANSFORM_TO_CANONICAL_PART')
                else:
                    source_evidence.update(verification='PINNED_PROCEDURAL_SOURCE_AND_CANONICAL_APPEND_ORDER',
                                          assembly_metadata=source,
                                          generation_assets_code_sha256=producer.provenance['generation_assets_code_sha256'],
                                          current_assets_code_sha256=producer.provenance['assets_code_sha256'],
                                          original_snapshot_input_pins_ref=MODEL+'provenance.json#/input_census',
                                          source_generator_reexecuted=False)
                solid = solids.prepare_solid(record['id'], source['kind'], owner, raw * 1000)
                metadata = dict(record)
                metadata.update(face_start=offset, face_stop=offset+count, canonical_mesh=rel,
                                canonical_bounds_error_m=bounds_error, source_evidence=source_evidence, solid=solid.evidence)
                parts[record['id']] = {'record': metadata, 'solid': solid}
                offset += count
            solids.require(offset == len(triangles), 'Canonical owner has unassigned original triangles: '+owner)
            partitions.append({'owner': owner, 'canonical_mesh': rel, 'triangles': len(triangles), 'partitioned_triangles': offset,
                               'part_ids': [p['id'] for p in components if p['link'] == owner]})
        return parts, partitions


    def map_envelopes(producer, parts):
        mappings, jaw_map = {}, {}
        for owner in ('KG1_A', 'KG1_B'):
            included = [p['record'] for p in parts.values() if p['record']['link'] == owner and p['record']['collision_included']]
            raw = solids.binary_triangles(producer.source(MODEL+'meshes/collision/'+owner+'.stl'))
            blocks, offset = {}, 0
            for index, part in enumerate(included):
                hull = part['collision_hull']
                solids.require(hull['shell_index'] == index, 'Collision ledger shell append order')
                count = hull['faces']
                solids.require(type(count) is int and count > 0 and offset+count <= len(raw), 'Jaw collision face block')
                blocks[part['id']] = (offset, offset+count, np.unique(raw[offset:offset+count].reshape(-1, 3), axis=0))
                offset += count
            solids.require(offset == len(raw) and len(blocks) == 6, 'Complete six jaw collision blocks')
            components = producer.jaws['jaws'][owner]['components']
            solids.require(len(components) == 6 and {c['index'] for c in components} == set(range(6)), 'Six unique fixed jaw indices')
            assigned = set()
            for component in components:
                vertices = np.asarray(component['vertices_m'], dtype=float)
                faces = np.asarray(component['triangle_indices'])
                solids.require(vertices.shape == (component['original_vertices'], 3) and
                               faces.shape == (component['original_triangles'], 3) and np.issubdtype(faces.dtype, np.integer) and
                               faces.min() >= 0 and faces.max() < len(vertices), 'Component-local vertex-index faces')
                matches = [(pid, start, stop, solids.cloud_distance(vertices, cloud))
                           for pid, (start, stop, cloud) in blocks.items()
                           if len(cloud) == len(vertices) and stop-start == len(faces) and
                           solids.cloud_distance(vertices, cloud) <= solids.CLOUD_M_ATOL]
                solids.require(len(matches) == 1 and matches[0][0] not in assigned, 'Unique bilateral jaw original-part mapping')
                pid, start, stop, error = matches[0]
                assigned.add(pid)
                jaw_map[owner+':'+format(component['index'], '02d')] = {
                    'part_ids': [pid], 'mechanism': 'COLLISION_LEDGER_FACE_BLOCK_BILATERAL_VERTEX_CLOUD',
                    'collision_face_start': start, 'collision_face_stop': stop,
                    'component_local_face_count': len(faces), 'bilateral_cloud_error_m': error,
                    'tolerance_m': solids.CLOUD_M_ATOL, 'triangle_indices_meaning': 'COMPONENT_LOCAL_VERTEX_INDICES_NOT_GLOBAL_FACE_IDS'}
            solids.require(assigned == set(blocks), 'Every jaw original part assigned exactly once')
        solids.require(len(producer.envelopes) == 21 and len({e['id'] for e in producer.envelopes}) == 21, '21 unique source envelopes')
        for envelope in producer.envelopes:
            owner, eid = envelope['owner'], envelope['id']
            solids.require(owner in NAMES, 'Unexpected envelope owner')
            if 'component_index' in envelope:
                mapping = jaw_map[eid]
                solids.require(eid == owner+':'+format(envelope['component_index'], '02d'), 'Envelope fixed component index')
            else:
                solids.require(eid == owner and owner not in ('KG1_A', 'KG1_B'), 'Whole-source envelope identity')
                mapping = {'part_ids': [pid for pid, p in parts.items() if p['record']['link'] == owner and p['record']['collision_included']],
                           'mechanism': 'ALL_COLLISION_INCLUDED_ORIGINAL_OWNER_PARTS'}
            solids.require(mapping['part_ids'], 'Empty original source subset')
            mappings[eid] = dict(mapping, owner=owner)
        solids.require(len({pid for mapping in mappings.values() for pid in mapping['part_ids']}) == 244, '244 mapped included original parts')
        return mappings


    def select_cases(producer):
        audit = parse(producer.raw[AUDIT_ROOT+'audit.json'])
        solids.require(audit['audit_completed'] is True and audit['run_id'] == RUN and audit['job_sha256'] == JOB and
                       audit['sample_categories'][POSITIVE_134] == 91 and audit['pair_categories'][POSITIVE_134] == 18 and
                       audit['unchecked_candidate_pair_rows'] == 348214, 'Original134 scope')
        selected = [w for w in producer.witnesses if w['category'] == POSITIVE_134]
        solids.require(len(producer.witnesses) == 348 and len(selected) == len({(w['pair_id'], w['step']) for w in selected}) == 91 and
                       len({w['pair_id'] for w in selected}) == 18, 'Exactly 91 positive witnesses / 18 source pairs')
        registry = {p['id']: p for p in producer.registry}
        solids.require(len(registry) == len(producer.registry) == 180, 'Original interbody pair registry')
        steps = {w['step'] for w in selected}
        actual = {}
        motion = producer.raw['outputs/mp18-manipulation-133/attempts/05/retrieved/motion.ndjson']
        count = 0
        for index, line in enumerate(io.BytesIO(motion)):
            row = parse(line)
            solids.require(type(row['step']) is int and row['step'] == index and abs(row['time_s']-index/120) < 1e-8,
                           'Actual motion contiguous step/time')
            poses = row['body_poses']
            solids.require(len(poses) == 11 and {p['name'] for p in poses} == set(NAMES), 'Actual motion body census')
            for pose in poses:
                solids.rotation(pose['orientation_wxyz'])
                position = np.asarray(pose['position'], dtype=float)
                solids.require(position.shape == (3,) and np.isfinite(position).all(), 'Actual position shape/finite')
            if index in steps:
                actual[index] = {p['name']: p for p in poses}
            count += 1
        solids.require(count == 11161 and set(actual) == steps, 'Original11161 rows / every selected actual pose')
        cases = []
        for witness in selected:
            pair = registry[witness['pair_id']]
            envelopes = [producer.envelopes[i] for i in pair['indices']]
            solids.require([e['id'] for e in envelopes] == pair['envelopes'] and len({e['owner'] for e in envelopes}) == 2,
                           'Actual source-envelope pair registry binding')
            poses = {p['owner']: p for p in witness['poses']}
            solids.require(set(poses) == {e['owner'] for e in envelopes} and len(witness['poses']) == 2 and
                           witness['time_s'] == witness['step']/120, 'Witness pose owner/time')
            for owner, pose in poses.items():
                source = actual[witness['step']][owner]
                solids.require(pose['position_m'] == source['position'] and pose['original_orientation_wxyz'] == source['orientation_wxyz'],
                               'Witness/actual133 body pose exact mismatch')
            cases.append({'pair_id': witness['pair_id'], 'step': witness['step'], 'time_s': witness['time_s'],
                          'envelopes': pair['envelopes'], 'poses': witness['poses'],
                          'owner_a': envelopes[0]['owner'], 'owner_b': envelopes[1]['owner'],
                          'original134_category': witness['category'], 'actual_pose_exactly_verified': True})
        return cases


    def evaluate_cases(cases, mappings, parts, progress=True):
        results, cache = [], {}
        actual_boolean_calls = 0
        for ordinal, case in enumerate(cases, 1):
            a_ids, b_ids = [mappings[e]['part_ids'] for e in case['envelopes']]
            poses = {p['owner']: p for p in case['poses']}
            transform = solids.relative_transform(poses[case['owner_a']], poses[case['owner_b']])
            rows = []
            for a_id in a_ids:
                for b_id in b_ids:
                    key = (case['owner_a'], case['owner_b'], case['step'], a_id, b_id)
                    reused = key in cache
                    if not reused:
                        cache[key] = solids.compare_pair(parts[a_id]['solid'], parts[b_id]['solid'], transform)
                        actual_boolean_calls += cache[key]['boolean_calls']
                    rows.append(dict(cache[key], reused_exact_owner_step_part_pair=reused))
            solids.require(len(rows) == len(a_ids)*len(b_ids) and len({(r['part_a'], r['part_b']) for r in rows}) == len(rows),
                           'Complete unique original-part cross-product')
            categories = Counter(r['category'] for r in rows)
            overall = next(c for c in (solids.PRINTED, solids.APPROX, solids.UNKNOWN, solids.SMALL, solids.ZERO) if categories[c])
            result = dict(case, relative_b_in_a_mm=transform.tolist(), part_ids_a=a_ids, part_ids_b=b_ids,
                          expected_part_pairs=len(a_ids)*len(b_ids), evaluated_part_pairs=len(rows),
                          part_cross_product_complete=True, category=overall, category_counts=dict(categories),
                          unknown_part_pairs=categories[solids.UNKNOWN], uncertain_part_pairs=categories[solids.SMALL], pairs=rows)
            results.append(result)
            if progress and (ordinal % 10 == 0 or ordinal == len(cases)):
                print(json.dumps({'progress': ordinal, 'cases': len(cases), 'actual_boolean_calls': actual_boolean_calls}), flush=True)
        return results, {'actual_boolean_calls': actual_boolean_calls, 'unique_evaluated_part_pose_pairs': len(cache),
                         'reported_part_pairs': sum(len(r['pairs']) for r in results),
                         'reused_exact_part_pose_pairs': sum(bool(p['reused_exact_owner_step_part_pair']) for r in results for p in r['pairs'])}


    def render_report(summary, cases):
        text = ['# 135 — 원본 부품 입체 대조', '',
                '실제133/05의 93초 기록 중 134가 선정한 18 source-envelope 쌍 / 91 양성 표본만 대조했다.',
                '원본 canonical visual STL의 274 부품을 분할하고, collision 포함 244 부품을 source envelope에 대응했다.',
                '인쇄 중인 실제 작업/슬라이서/실물과 이 모델의 동일성은 UNKNOWN이다.', '',
                f"선정 표본 처리완료: {summary['selected_processing_complete']}; 원입체 UNKNOWN pair 수: {summary['part_pair_categories'].get(solids.UNKNOWN, 0)}.",
                f"원part-pose pair 판정: {json.dumps(summary['part_pair_categories'], ensure_ascii=False)}", '',
                'printed/printed 양성은 원본 STL 모델의 양의 부피 겹침이며 설계불량·실물충돌·출력 중단 판정이 아니다.',
                '구매품 primitive/케이블 approximation 양성은 근사 모델의 겹침이며 실제 부품 접촉 확정이 아니다.',
                '0 < 교차부피 ≤ 0.01 mm³는 SMALL_VOLUME_UNCERTAIN이다. 작은 양수를 0으로 반올림하지 않았다.',
                '134의 40 UNKNOWN source-pair와 348214 미판독 pair-row, collision 제외 30 부품은 그대로 미검증이다.',
                '표면 맞닿음·연속시간·전체 v4 무간섭·backend cooked contact·실물 안전을 인증하지 않는다.',
                'Manifold3D 한 커널의 결과이며 다른 커널에 의한 독립 Boolean 검증이 아니다.', '',
                '| source pair | step / s | 표본 판정 | 양성 부품쌍 | UNKNOWN |', '|---|---:|---|---:|---:|']
        for case in cases:
            positives = [p for p in case['pairs'] if p['category'] in (solids.PRINTED, solids.APPROX)]
            text.append(f"| {case['pair_id']} | {case['step']} / {case['time_s']:.6f} | {case['category']} | {len(positives)} | {case['unknown_part_pairs']} |")
        text += ['', '## 양성 원부품 추적', '', '| source pair / step | 원부품 A | 원부품 B | kind A / B | 교차 mm³ |', '|---|---|---|---|---:|']
        for case in cases:
            for pair in case['pairs']:
                if pair['category'] in (solids.PRINTED, solids.APPROX, solids.SMALL):
                    text.append(f"| {case['pair_id']} / {case['step']} | {pair['part_a']} | {pair['part_b']} | {pair['kind_a']} / {pair['kind_b']} | {pair['volume_mm3']:.12g} |")
        text += ['', '원삼각형·부피 검산 상태는 original-parts.json, source→원part 결속은 envelope-parts.json,',
                 '각 actual position/wxyz·상대 mm 변환·전체 cross-product/분리/Boolean 근거는 cases.json에 있다.',
                 '입력 및 source의 실제 소비 전후 해시는 input-manifest.json과 source-manifest.json에 있다.',
                 'CAD 수정·SDK 재실행·실물 급전/통신/운전·프린터 전송은 이 결과의 승인 범위가 아니다.', '']
        return '\n'.join(text)


    def run(name, root=None, before_publish=None):
        started = time.monotonic()
        root = pathlib.Path(__file__).absolute().parents[3] if root is None else pathlib.Path(root).absolute()
        source_manifest = {relative: {'sha256': digest(raw), 'bytes': len(raw)}
                           for relative, raw in _SOURCE_BYTES_135.items()}

        def recheck_sources():
            for relative, expected in source_manifest.items():
                no_reparse(root/relative)
                raw = (root/relative).read_bytes()
                solids.require(raw == _SOURCE_BYTES_135[relative] and digest(raw) == expected['sha256'] and
                               len(raw) == expected['bytes'], '135 captured source changed: '+relative)

        recheck_sources()
        destination = output_destination(root, name, create=True)
        recheck_sources()
        producer = Producer(root)
        solids.require(source_manifest[PLAN] == producer.manifest[PLAN], 'Captured plan/producer plan binding')
        parts, partitions = partition_originals(producer)
        mappings = map_envelopes(producer, parts)
        selected = select_cases(producer)
        results, counts = evaluate_cases(selected, mappings, parts)
        pair_categories = Counter(p['category'] for c in results for p in c['pairs'])
        summary = {'schema': 'mp18-original-solid-comparison-135-v1', 'unit': 135, 'run_id': RUN, 'job_sha256': JOB,
                   'selected_processing_complete': len(results) == 91 and all(c['part_cross_product_complete'] for c in results),
                   'selected_cases': len(results), 'selected_source_pairs': len({c['pair_id'] for c in results}),
                   'original_parts': len(parts), 'mapped_collision_included_parts': 244,
                   'collision_excluded_part_ids': [pid for pid, p in parts.items() if not p['record']['collision_included']],
                   'not_selected_part_ids': sorted(set(parts)-{pid for c in results for e in c['envelopes'] for pid in mappings[e]['part_ids']}),
                   'case_categories': dict(Counter(c['category'] for c in results)), 'part_pair_categories': dict(pair_categories),
                   'all_selected_original_pairs_valid_and_decisive': pair_categories[solids.UNKNOWN] == pair_categories[solids.SMALL] == 0,
                   'counts': counts, 'original134_unknown_source_pairs': 40, 'original134_unchecked_pair_rows': 348214,
                   'original134_selected_narrowphase_samples': 348, 'original133_recorded_rows': 11161,
                   'current_physical_print_job_identity': 'UNKNOWN', 'whole_v4_collision_free': 'NOT_CERTIFIED',
                   'continuous_collision_checked': False, 'physical_safety_certified': False, 'hardware_approved': False,
                   'same_kernel_independent_validation': False, 'small_volume_boundary_mm3': solids.SMALL_MM3,
                   'units': 'original body-local m; Boolean relative body A frame mm; volumes mm3',
                   'source_producer_execution': False, 'geometry_repair': False,
                   'source_execution_binding': 'COMPARE_AND_SOLIDS_COMPILED_FROM_IMMUTABLE_CAPTURED_BYTES_BEFORE_OUTPUT_LEAF',
                   'versions': {n: importlib.metadata.version(n) for n in ('numpy', 'trimesh', 'scipy', 'manifold3d')},
                   'elapsed_s': time.monotonic()-started,
                   'reproduction': 'printforge/.venv/Scripts/python.exe -X utf8 -I -B -u robot-arm-lab/src/simulation/mp18_solid_compare_135/compare.py --name NEW_UNIQUE_SLUG'}
        if before_publish is not None:
            before_publish(producer, destination)

        def boundary():
            solids.require(output_destination(root, name) == destination, 'Publication destination changed')

        def write(filename, value, text=False):
            boundary()
            payload = value.encode('utf-8') if text else (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
            with (destination/filename).open('xb') as stream:
                stream.write(payload)

        boundary()
        producer.recheck()
        recheck_sources()
        write('original-parts.json', {'partitions': partitions, 'parts': [p['record'] for p in parts.values()],
                                    'original_snapshot_input_pins': producer.provenance['input_census']})
        write('envelope-parts.json', mappings)
        write('cases.json', results)
        write('input-manifest.json', producer.manifest)
        write('source-manifest.json', source_manifest)
        write('comparison.md', render_report(summary, results), text=True)
        producer.recheck()
        recheck_sources()
        boundary()
        summary['artifacts'] = {p.name: {'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size}
                                for p in destination.iterdir() if p.is_file()}
        write('comparison.json', summary)  # completion record is deliberately published last
        return summary, destination


    def main():
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--name', required=True, help='New exclusive slug leaf under the fixed 135 output root')
        args = parser.parse_args()
        logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
        try:
            summary, destination = run(args.name)
            print(json.dumps({'completed': summary['selected_processing_complete'], 'path': str(destination),
                              'case_categories': summary['case_categories'], 'counts': summary['counts']}), flush=True)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
            logging.exception('135 comparison failed closed: %s', error)
            return 1
        return 0


    if __name__ == '__main__':
        raise SystemExit(main())
