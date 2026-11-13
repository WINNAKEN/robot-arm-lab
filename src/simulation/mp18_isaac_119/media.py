"""119 actual native frames -> labelled MP4. No SDK/network/hardware entry points."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile
import uuid

HERE = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location('media_driver119', HERE/'driver.py')
D = importlib.util.module_from_spec(s)
sys.modules[s.name] = D
s.loader.exec_module(D)
C, OUT = D.C, D.OUT


def commands():
    result = [shutil.which(n) for n in ('ffmpeg', 'ffprobe')]
    C.need(all(result), 'Installed ffmpeg and ffprobe required; no installation')
    return [str(Path(n).resolve()) for n in result]


def invoke(argv, timeout=120):
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=timeout, check=False)
    C.need(p.returncode == 0, 'Media tool failed: '+p.stderr.decode('utf8', 'replace')[-2000:])
    return p.stdout


def validate_frames(folder, seal, capture):
    """Check original indexed PNGs, their sealed sidecars, and actual render/physics bindings."""
    frames = sorted((folder/'frames').glob('frame-*.png'))
    sidecars = sorted((folder/'frames').glob('frame-*.json'))
    C.need(frames and len(frames) == len(sidecars), 'Actual nonempty exact frame inventory')
    rows = []
    for i, path in enumerate(frames):
        name = 'frames/frame-%04d.png' % i
        sidecar_name = name[:-4]+'.json'
        C.need(path.name == Path(name).name and path.relative_to(folder).as_posix() == name,
               'Contiguous native frame sequence')
        C.need(name in seal and sidecar_name in seal and C.sha(path) == seal[name] and
               C.sha(C.path_in(folder, sidecar_name)) == seal[sidecar_name], 'Sealed native PNG/sidecar')
        row = D.read(folder/sidecar_name)
        C.need(row['png'] == name and row['frame_index'] == i and row['sha256'] == seal[name],
               'Native frame identity')
        C.need(row['pixel_shape'] == [480, 640, 4] and row['pixel_dtype'] == 'uint8', 'Native RGB dimensions')
        png = path.read_bytes()
        C.need(png[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', png[16:24]) == (640, 480),
               'Actual PNG dimensions')
        C.need(type(row['physics_time_s']) in (float, int) and math.isfinite(row['physics_time_s']) and
               abs(row['physics_time_s']-i/10) < 1e-6 and row['state_index'] == i*12,
               'Continuous actual physics time and 120Hz step / 10fps binding')
        C.need(row['phase'].split(':')[0] in ('hold', 'small', 'large'), 'Closed native frame stage')
        capture.validate_generation(row['freshness'])
        capture.validate_render_binding(row['native_before'], row['native_after'])
        rows.append(row)
    C.need({p.name for p in sidecars} == {'frame-%04d.json' % i for i in range(len(rows))},
           'No unmatched sidecars')
    return rows


def filter_text(rows, phases, overall_status=None):
    statuses = {p['name']: p['status'] for p in phases}
    C.need(set(statuses) == {'import', 'hold', 'small', 'large'} and
           all(v in ('PASS', 'FAIL', 'NOT_RUN') for v in statuses.values()), 'Closed phase statuses')
    overall_status = overall_status or ('PASS' if all(s == 'PASS' for s in statuses.values()) else 'FAIL')
    C.need(overall_status in ('PASS', 'FAIL'), 'Closed overall status')
    font = Path(os.environ['WINDIR'])/'Fonts/arial.ttf'
    C.need(font.is_file(), 'Installed Arial font required; no font installation')
    font_arg = ":fontfile='"+font.as_posix().replace(':', '\\:')+"'"
    base = ("drawtext=text='Isaac 119 - URDF v4 - RUN %s - Sim only':x=8:y=8:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.65" % overall_status)+font_arg
    filters, start = [base], 0
    while start < len(rows):
        phase = rows[start]['phase'].split(':')[0]
        end = start+1
        while end < len(rows) and rows[end]['phase'].split(':')[0] == phase:
            end += 1
        color = 'lime' if statuses[phase] == 'PASS' else 'yellow'
        text = phase.upper()+' '+statuses[phase]+' - real native RGB'
        filters.append(("drawtext=text='%s':x=8:y=h-32:fontsize=18:fontcolor=%s:box=1:boxcolor=black@0.65:enable='gte(t,%.9f)*lt(t,%.9f)'" %
                       (text, color, start/10, end/10))+font_arg)
        start = end
    return ','.join(filters)


def encode():
    D._review_gate()
    record = D.read(OUT/'prepared.json')
    run = OUT/'runs'/record['run_id']
    folder = run/'retrieved'
    # This consumer never opens SSH or SDK. FAIL remains FAIL while authentic diagnostic frames can be delivered.
    D.verify_native_result(run, record, folder)
    result = D.read(OUT/'native-result.json')
    report = D.read(folder/result['original_report'])
    recovery = D.read(folder/'recovery-seal.json')
    with zipfile.ZipFile(run/'bundle.zip') as z:
        raw = z.read('input/ref/capture.py')
        cfg = C.parse(z.read('input/source/config.json'))
        C.need(C.sha(OUT/'user-decision.json') == D.read(run/'job.json')['inputs']['approval.json'], 'Actual cap decision')
    capture = D.load_module('media_capture119', raw, folder/'original-capture.py')
    rows = validate_frames(folder, recovery['files_sha256'], capture)
    ffmpeg, ffprobe = commands()
    delivery = OUT/'delivery'
    delivery.mkdir(parents=True, exist_ok=True)
    movie = delivery/'robot-arm-v4-119.mp4'
    C.need(not movie.exists(), 'Preserve existing movie; no overwrite')
    vf = filter_text(rows, result['phases'], result['status'])
    invoke([ffmpeg, '-hide_banner', '-v', 'error', '-n', '-framerate', '10', '-start_number', '0',
            '-i', str(folder/'frames/frame-%04d.png'), '-frames:v', str(len(rows)), '-vf', vf,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart', '-an', '-map_metadata', '-1', str(movie)])
    probe_raw = invoke([ffprobe, '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration:format=duration,size',
                        '-of', 'json', str(movie)], timeout=30)
    probe = json.loads(probe_raw)
    C.need(len(probe['streams']) == 1, 'One video stream')
    v = probe['streams'][0]
    C.need(v['codec_name'] == 'h264' and [v['width'], v['height']] == [640, 480] and
           v['r_frame_rate'] == '10/1' and int(v['nb_read_frames']) == len(rows) and
           abs(float(probe['format']['duration'])-len(rows)/10) < .02 and
           int(probe['format']['size']) == movie.stat().st_size, 'Actual MP4 metadata/count/duration')
    invoke([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(movie), '-f', 'null', '-'])
    # Decode actual first/middle/last MP4 frames for independent visual inspection.
    samples = sorted(set((0, len(rows)//2, len(rows)-1)))
    for index in samples:
        invoke([ffmpeg, '-hide_banner', '-v', 'error', '-n', '-i', str(movie),
                '-vf', 'select=eq(n\\,%d)' % index, '-frames:v', '1', str(delivery/('preview-%04d.png' % index))], timeout=30)
    clean = {'unit': 119, 'model': 'MP18 URDF v4', 'simulation_only': True,
             'hardware_approved': False, 'physical_communications': 'NOT_RUN',
             'status': result['status'], 'phases': [{'name': p['name'], 'status': p['status']} for p in result['phases']],
             'capture_provenance': result['capture_provenance'],
             'cap_mode': D.read(OUT/'user-decision.json')['cap_mode'],
             'frames': len(rows), 'fps': 10, 'video_duration_s': len(rows)/10,
             'movie': movie.name, 'movie_sha256': C.sha(movie),
             'limitations': ['Estimated masses and inertias; no physical performance acceptance.',
                             'Self collision disabled; no self contact safety acceptance.']}
    D.write(delivery/'result.json', clean)
    D.write(OUT/'D/media-manifest.json', {'unit': 119, 'run_id': record['run_id'], 'movie': str(movie),
            'sha256': C.sha(movie), 'bytes': movie.stat().st_size, 'ffprobe': probe,
            'original_frames': len(rows), 'sample_indices': samples, 'visual_inspection': 'PENDING',
            'capture_provenance': result['capture_provenance'],
            'upload_allowlist': [movie.name, 'result.json'], 'hardware_approved': False})
    return clean


def self_test():
    """HOST-only regression fixtures; never generates or delivers a pretend native movie."""
    import unittest
    prior = D.ROOT/'outputs/blended-reference-trial-116/native-artifacts/runs/4f38ca9612b34716947baa6f56c96e05/retrieved'
    cfg = D.read(HERE/'config.json')
    item = cfg['refs']['capture.py']
    raw = C.path_in(D.ROOT, item['path']).read_bytes()
    import hashlib
    C.need(hashlib.sha256(raw).hexdigest() == item['sha256'], 'Frozen capture helper')
    capture = D.load_module('media_capture_host119', raw, prior/'HOST_ONLY_capture.py')
    fixture = OUT/'D'/('HOST_ONLY_'+uuid.uuid4().hex)
    (fixture/'frames').mkdir(parents=True, exist_ok=False)
    png = fixture/'frames/frame-0000.png'
    png.write_bytes((prior/'frames/frame-0000.png').read_bytes())
    source = D.read(prior/'frames/frame-0000.json')
    source['phase'] = 'hold'
    sidecar = fixture/'frames/frame-0000.json'
    def restore(row):
        D.write(sidecar, row)
        return {'frames/frame-0000.png': C.sha(png), 'frames/frame-0000.json': C.sha(sidecar)}

    class MediaTests(unittest.TestCase):
        def test_01_positive_original_native_format_fixture_only(self):
            self.assertEqual(len(validate_frames(fixture, restore(source), capture)), 1)

        def test_02_seal_gap_and_modified_pixels(self):
            seal = restore(source)
            with self.assertRaises(ValueError):
                validate_frames(fixture, {}, capture)
            altered = dict(seal, **{'frames/frame-0000.png': '0'*64})
            with self.assertRaises(ValueError):
                validate_frames(fixture, altered, capture)

        def test_03_clock_and_step_gaps(self):
            for field, value in [('physics_time_s', .1), ('state_index', 12)]:
                row = dict(source, **{field: value})
                with self.assertRaisesRegex(ValueError, 'physics time'):
                    validate_frames(fixture, restore(row), capture)

        def test_04_stale_generation_and_render_advancement(self):
            row = copy.deepcopy(source)
            row['freshness']['after']['rgb']['compute_count'] = row['freshness']['before']['rgb']['compute_count']
            with self.assertRaisesRegex(capture.CaptureError, 'Stale render'):
                validate_frames(fixture, restore(row), capture)
            row = copy.deepcopy(source)
            row['native_after']['clock']['engine_time_s'] += .01
            with self.assertRaisesRegex(capture.CaptureError, 'changed during render'):
                validate_frames(fixture, restore(row), capture)

        def test_05_closed_labels_preserve_failure(self):
            phases = [{'name': n, 'status': 'FAIL' if n == 'hold' else 'NOT_RUN'} for n in ('import', 'hold', 'small', 'large')]
            self.assertIn('HOLD FAIL', filter_text([source], phases))
            phases[1]['status'] = 'AUTO_PASS'
            with self.assertRaises(ValueError):
                filter_text([source], phases)

        def test_06_publisher_preflight_rejects_scope_and_section_mutants(self):
            global OUT
            original_root, original_out, original_gate = D.ROOT, OUT, D._review_gate
            sandbox = fixture/'publisher_HOST_ONLY'
            try:
                D.ROOT, OUT, D._review_gate = sandbox, sandbox/'outputs/mp18-isaac-119', lambda: None
                OUT.mkdir(parents=True)
                def put(relative, value):
                    p = sandbox/relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(value), encoding='utf8')
                freeze = 'outputs/mp18-isaac-119/review/source-freeze.json'
                selection_name = 'outputs/mp18-isaac-119/delivery-selection.json'
                sections_name = 'outputs/mp18-isaac-119/shared-own-sections.json'
                names = [PLAN, OWNED[0]+'/media.py', freeze, selection_name, sections_name]
                for n in names:
                    put(n, {'HOST_ONLY': True})
                selection = dict(unit=119, paths=names, freeze_path=freeze, freeze_sha256=C.sha(sandbox/freeze))
                section = {'unit': 119, 'sections': [{'header': HEADER, 'text': HEADER+'\nHOST ONLY\n'}]}
                put(selection_name, selection); put(sections_name, section)
                self.assertEqual(publish(preflight=True)['Git_mutations'], 0)
                for paths in (names+names[:1], names[:-1], names+['../escape'], names+['.dev/CODING_RULES.md']):
                    put(selection_name, dict(selection, paths=paths))
                    with self.assertRaises(ValueError):
                        publish(preflight=True)
                put(selection_name, selection)
                for text in ('# foreign\n', HEADER+'\n# another section\n', HEADER+'\n'+'x'*17000):
                    put(sections_name, {'unit': 119, 'sections': [{'header': HEADER, 'text': text}]})
                    with self.assertRaises(ValueError):
                        publish(preflight=True)
                put(sections_name, dict(section, unit=118))
                with self.assertRaises(ValueError):
                    publish(preflight=True)
            finally:
                D.ROOT, OUT, D._review_gate = original_root, original_out, original_gate

        def test_07_real_temporary_git_concurrent_shared_stage(self):
            global OUT
            import tempfile
            original_root, original_out, original_gate = D.ROOT, OUT, D._review_gate
            real_run, real_replace = subprocess.run, os.replace
            executable = shutil.which('git')
            C.need(executable is not None, 'Installed Git for isolated HOST fixture')
            with tempfile.TemporaryDirectory(dir=OUT/'D', prefix='HOST_TEMP_GIT_') as raw_temp:
                sandbox = Path(raw_temp).resolve()
                C.need(sandbox.parent == (original_out/'D').resolve() and
                       sandbox.name.startswith('HOST_TEMP_GIT_'), 'Exact owned temporary Git repository')
                def g(args, data=None, check=True):
                    p = real_run([executable, *args], cwd=sandbox, input=data, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=20)
                    if check:
                        self.assertEqual(p.returncode, 0, p.stderr.decode('utf8', 'replace'))
                    return p
                g(['init', '--quiet', '--initial-branch=codex/host'])
                g(['config', 'user.name', 'HOST Fixture'])
                g(['config', 'user.email', 'host@example.invalid'])
                for n in ('.dev/HANDOFF.md', '.dev/SESSION_HANDOFF.md', '.dev/CODING_RULES.md', 'unrelated.txt'):
                    p = sandbox/n
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('HOST BASE '+n+'\n', encoding='utf8')
                g(['add', '.dev/HANDOFF.md', '.dev/SESSION_HANDOFF.md', '.dev/CODING_RULES.md', 'unrelated.txt'])
                g(['commit', '--quiet', '-m', 'HOST initial'])
                worktree_before = {n: (sandbox/n).read_bytes() for n in ('.dev/HANDOFF.md', '.dev/SESSION_HANDOFF.md', '.dev/CODING_RULES.md')}
                before_blob = g(['hash-object', '-w', '--stdin'], b'FOREIGN STAGED BEFORE LOCK\n').stdout.decode().strip()
                after_blob = g(['hash-object', '-w', '--stdin'], b'FOREIGN STAGED AFTER LOCK\n').stdout.decode().strip()
                g(['update-index', '--cacheinfo', '100644,'+before_blob+',.dev/SESSION_HANDOFF.md'])
                try:
                    D.ROOT, OUT, D._review_gate = sandbox, sandbox/'outputs/mp18-isaac-119', lambda: None
                    OUT.mkdir(parents=True)
                    def put(relative, value):
                        p = sandbox/relative
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(json.dumps(value), encoding='utf8')
                    freeze = 'outputs/mp18-isaac-119/review/source-freeze.json'
                    selection_name = 'outputs/mp18-isaac-119/delivery-selection.json'
                    sections_name = 'outputs/mp18-isaac-119/shared-own-sections.json'
                    names = [PLAN, OWNED[0]+'/media.py', freeze, selection_name, sections_name]
                    for n in names:
                        put(n, {'HOST_ONLY': True})
                    put(selection_name, dict(unit=119, paths=names, freeze_path=freeze, freeze_sha256=C.sha(sandbox/freeze)))
                    put(sections_name, {'unit': 119, 'sections': [{'header': HEADER, 'text': HEADER+'\nHOST ONLY\n'}]})
                    race = {'CAS_stage_attempts': 0, 'lock_release_stage_attempts': 0}
                    foreign_lock = sandbox/'.git/index.lock'
                    foreign_lock.write_bytes(b'HOST FOREIGN LOCK')
                    head_before_lock = g(['rev-parse', 'HEAD']).stdout
                    with self.assertRaises(FileExistsError):
                        publish()
                    self.assertEqual(foreign_lock.read_bytes(), b'HOST FOREIGN LOCK')
                    self.assertEqual(g(['rev-parse', 'HEAD']).stdout, head_before_lock)
                    self.assertEqual(foreign_lock.parent.resolve(), (sandbox/'.git').resolve())
                    foreign_lock.unlink()  # Exact lock created by this HOST fixture, never a product cleanup action.
                    race['preexisting_lock_preserved_HEAD_unchanged'] = True
                    def observed_run(argv, **kwargs):
                        result = real_run(argv, **kwargs)
                        if 'update-ref' in argv and race['CAS_stage_attempts'] == 0:
                            race['CAS_stage_attempts'] += 1
                            actor = g(['update-index', '--cacheinfo', '100644,'+after_blob+',.dev/HANDOFF.md'], check=False)
                            race['CAS_stage_exit'] = actor.returncode
                            race['CAS_stage_lock_error'] = 'index.lock' in actor.stderr.decode('utf8', 'replace')
                        return result
                    def observed_replace(source_path, target_path, *args, **kwargs):
                        value = real_replace(source_path, target_path, *args, **kwargs)
                        if Path(source_path).name == 'index.lock' and Path(target_path).name == 'index':
                            race['lock_release_stage_attempts'] += 1
                            g(['update-index', '--cacheinfo', '100644,'+after_blob+',.dev/HANDOFF.md'])
                        return value
                    subprocess.run, os.replace = observed_run, observed_replace
                    delivered = publish()
                    self.assertFalse(delivered['push'])
                    self.assertEqual(race['CAS_stage_attempts'], 1)
                    self.assertNotEqual(race['CAS_stage_exit'], 0)
                    self.assertTrue(race['CAS_stage_lock_error'])
                    self.assertEqual(race['lock_release_stage_attempts'], 1)
                    self.assertEqual(g(['rev-parse', ':.dev/HANDOFF.md']).stdout.decode().strip(), after_blob)
                    self.assertEqual(g(['rev-parse', ':.dev/SESSION_HANDOFF.md']).stdout.decode().strip(), before_blob)
                    self.assertEqual(worktree_before, {n: (sandbox/n).read_bytes() for n in worktree_before})
                    self.assertFalse((sandbox/'.git/index.lock').exists())
                    race.update(HOST_ONLY=True, workspace_git_mutations=0, temporary_git_repository=True,
                                preserved_before_lock_blob=True, preserved_after_lock_blob=True)
                finally:
                    subprocess.run, os.replace = real_run, real_replace
                    D.ROOT, OUT, D._review_gate = original_root, original_out, original_gate
                D.write(OUT/'D/host-git-race.json', race)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MediaTests))
    restore(source)
    D.write(OUT/'D/host.json', {'tests': result.testsRun, 'failures': len(result.failures),
            'errors': len(result.errors), 'fixture': str(fixture), 'HOST_ONLY': True,
            'SDK': 0, 'SSH': 0, 'movie_generated': False, 'Drive_writes': 0})
    return 0 if result.wasSuccessful() else 1


OWNED = ('src/simulation/mp18_isaac_119', 'outputs/mp18-isaac-119')
PLAN = 'docs/design/119-mp18-isaac-video.md'
HEADER = '# 119 — MP18 URDF v4 Isaac 검증·영상 전달'


def owned(relative):
    C.relative(relative)
    C.need(relative == PLAN or any(relative.startswith(t+'/') for t in OWNED), 'Outside unit119 ownership')
    C.need(not any(p in ('.git', '__pycache__') for p in Path(relative).parts), 'Excluded owned path')
    path = C.path_in(D.ROOT, relative)
    C.need(path.is_file(), 'Missing owned file')
    return path


def inventory():
    result = {PLAN}
    def walk(folder):
        C.need(not folder.is_symlink() and not folder.is_junction(), 'Linked inventory rejected')
        for p in folder.iterdir():
            C.need(not p.is_symlink() and not p.is_junction(), 'Linked inventory entry rejected')
            if p.is_dir():
                yield from walk(p)
            elif p.is_file():
                yield p
    for relative in OWNED:
        for p in walk(D.ROOT/relative):
            if p.parent == OUT and (p.name.startswith('.git-index-') or p.name == 'git-delivery-receipt.json'):
                continue
            n = p.relative_to(D.ROOT).as_posix()
            owned(n)
            result.add(n)
    return result


def publisher_inputs():
    selection, sections = D.read(OUT/'delivery-selection.json'), D.read(OUT/'shared-own-sections.json')
    C.need(set(selection) == {'unit', 'paths', 'freeze_path', 'freeze_sha256'} and selection['unit'] == 119,
           'Closed unit119 selection')
    paths = selection['paths']
    C.need(type(paths) is list and all(type(p) is str for p in paths) and
           len(paths) == len(set(p.casefold() for p in paths)), 'Unique canonical selection')
    for p in paths:
        owned(p)
    C.need(set(paths) == inventory(), 'Exact owned inventory required')
    C.need(selection['freeze_path'] == 'outputs/mp18-isaac-119/review/source-freeze.json' and
           C.sha(owned(selection['freeze_path'])) == selection['freeze_sha256'], 'Actual source freeze')
    D._review_gate()
    C.need(set(sections) == {'unit', 'sections'} and sections['unit'] == 119 and len(sections['sections']) == 1,
           'Closed unit119 shared section')
    section = sections['sections'][0]
    C.need(set(section) == {'header', 'text'} and section['header'] == HEADER and type(section['text']) is str,
           'Actual unit119 section')
    text = section['text']
    C.need(text.startswith(HEADER+'\n') and len(text.encode('utf8')) <= 16384 and
           [x for x in text.splitlines() if x.startswith('# ')] == [HEADER], 'Closed owned shared-section body')
    return paths, text


def publish(preflight=False):
    """Local Git delivery only. Raw blobs, private index and CAS; never git add-all or push."""
    paths, section = publisher_inputs()
    if preflight:
        return {'unit': 119, 'preflight': 'PASS', 'paths': len(paths), 'Git_mutations': 0}
    C.need(not (OUT/'git-delivery-receipt.json').exists(), 'Delivery already recorded; implicit repeat rejected')
    executable = shutil.which('git')
    C.need(executable is not None, 'Installed git required')
    def git(args, data=None, env=None):
        p = subprocess.run([executable, *args], cwd=D.ROOT, input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, timeout=60, check=False)
        C.need(p.returncode == 0, 'Git command failed: '+p.stderr.decode('utf8', 'replace')[-1000:])
        return p.stdout
    def index(env=None):
        return {n.decode('utf8'): h.decode('ascii') for h, n in
                (x.split(b'\t', 1) for x in git(['ls-files', '--stage', '-z'], env=env).split(b'\0') if x)}
    parent, ref = git(['rev-parse', 'HEAD']).decode().strip(), git(['symbolic-ref', 'HEAD']).decode().strip()
    C.need(ref.startswith('refs/heads/codex/'), 'Current Codex branch required')
    shared = ('.dev/HANDOFF.md', '.dev/SESSION_HANDOFF.md')
    shared_sha = {n: C.sha(D.ROOT/n) for n in (*shared, '.dev/CODING_RULES.md')}
    entries, old_shared = {}, {}
    for n in paths:
        p = owned(n)
        digest, size = C.sha(p), p.stat().st_size
        blob = git(['hash-object', '-w', '--no-filters', str(p)]).decode().strip()
        C.need(C.sha(p) == digest, 'Owned source drift during hash')
        entries[n] = {'blob': blob, 'sha256': digest, 'bytes': size, 'source': 'OWNED_BYTES'}
    for n in shared:
        base = git(['show', parent+':'+n])
        old_shared[n] = git(['rev-parse', parent+':'+n]).decode().strip()
        C.need(HEADER.encode() not in base, 'Unit119 section already committed')
        value = section.encode()+base if n.endswith('/HANDOFF.md') else base+b'\n\n---\n\n'+section.encode()
        import hashlib
        entries[n] = {'blob': git(['hash-object', '-w', '--stdin'], value).decode().strip(),
                      'sha256': hashlib.sha256(value).hexdigest(), 'bytes': len(value), 'source': 'HEAD_PLUS_ONLY_UNIT119'}
    def verify(entries):
        import hashlib
        for n, r in entries.items():
            raw = git(['cat-file', 'blob', r['blob']])
            C.need(len(raw) == r['bytes'] and hashlib.sha256(raw).hexdigest() == r['sha256'], 'Actual raw blob hash')
    audits, temporary = [], []
    def commit(entries, parent, message):
        private = OUT/('.git-index-'+uuid.uuid4().hex)
        temporary.append(private)
        env = dict(os.environ, GIT_INDEX_FILE=str(private))
        git(['read-tree', parent], env=env)
        lines = ''.join('100644 '+r['blob']+'\t'+n+'\n' for n, r in entries.items()).encode()
        git(['update-index', '--index-info'], lines, env)
        changed = git(['diff', '--cached', '--name-only', '-z', parent], env=env).split(b'\0')
        C.need({n.decode() for n in changed if n} <= set(entries), 'Only selected index changes')
        audits.append(git(['diff', '--cached', '--name-status', parent], env=env).decode('utf8'))
        tree = git(['write-tree'], env=env).decode().strip()
        oid = git(['commit-tree', tree, '-p', parent], message.encode()).decode().strip()
        C.need(git(['symbolic-ref', 'HEAD']).decode().strip() == ref, 'Branch changed during delivery')
        git(['update-ref', ref, oid, parent])
        return oid
    verify(entries)
    gitdir = Path(git(['rev-parse', '--absolute-git-dir']).decode().strip()).resolve()
    index_path = Path(git(['rev-parse', '--git-path', 'index']).decode().strip())
    if not index_path.is_absolute():
        index_path = D.ROOT/index_path
    index_path = index_path.resolve()
    C.need(index_path.parent == gitdir and index_path.name == 'index' and index_path.is_file() and
           not index_path.is_symlink() and not index_path.is_junction(), 'Exact current Git index')
    lock_path = index_path.with_name('index.lock')
    # Ordinary Git writers honor this exclusive transaction. Never remove a preexisting lock.
    lock = lock_path.open('xb')
    lock_identity = (os.fstat(lock.fileno()).st_dev, os.fstat(lock.fileno()).st_ino)
    try:
        before = index()  # Fresh snapshot under the actual default-index lock, before the ref CAS.
        delivery = commit(entries, parent, 'Record reviewed unit119 Isaac validation and video delivery\n')
        safe = {n: r for n, r in entries.items() if n not in old_shared or
                n not in before or before[n].split()[1] == old_shared[n]}
        merged = OUT/('.git-index-merge-'+uuid.uuid4().hex)
        temporary.append(merged)
        merged.write_bytes(index_path.read_bytes())
        merge_env = dict(os.environ, GIT_INDEX_FILE=str(merged))
        git(['update-index', '--index-info'],
            ''.join('100644 '+r['blob']+'\t'+n+'\n' for n, r in safe.items()).encode(), merge_env)
        after = index(merge_env)
        C.need({n: r for n, r in before.items() if n not in entries} ==
               {n: r for n, r in after.items() if n not in entries}, 'Foreign index entries preserved')
        for n in old_shared:
            if n not in safe:
                C.need(after.get(n) == before.get(n), 'Concurrent shared staged blob preserved')
        C.need(shared_sha == {n: C.sha(D.ROOT/n) for n in shared_sha}, 'Foreign shared worktree bytes preserved')
        lock.write(merged.read_bytes())
        lock.flush()
        os.fsync(lock.fileno())
        lock.close()
        os.replace(lock_path, index_path)
    finally:
        if not lock.closed:
            lock.close()
        if lock_path.exists():
            status = lock_path.stat()
            if (status.st_dev, status.st_ino) == lock_identity:
                lock_path.unlink()  # Only this invocation's exact lock; another writer's lock is untouched.
    receipt = {'unit': 119, 'delivery_commit': delivery, 'parent': parent, 'ref': ref, 'files': entries,
               'raw_sha256_mismatch': 0, 'foreign_index_preserved': True, 'shared_worktree_preserved': True,
               'isolated_cached_diff': audits, 'push': False}
    receipt_path = OUT/'git-delivery-receipt.json'
    with receipt_path.open('x', encoding='utf8') as stream:
        json.dump(receipt, stream, indent=2)
    name = receipt_path.relative_to(D.ROOT).as_posix()
    entry = {name: {'blob': git(['hash-object', '-w', '--no-filters', str(receipt_path)]).decode().strip(),
                   'sha256': C.sha(receipt_path), 'bytes': receipt_path.stat().st_size}}
    verify(entry)
    final = commit(entry, delivery, 'Record unit119 raw-byte delivery receipt\n')
    git(['update-index', '--index-info'], ('100644 '+entry[name]['blob']+'\t'+name+'\n').encode())
    for p in temporary:
        C.need(p.parent == OUT and p.name.startswith('.git-index-') and not p.is_symlink() and not p.is_junction(),
               'Only exact owned temporary indices can be removed')
        p.unlink()
    return {'unit': 119, 'delivery_commit': delivery, 'receipt_commit': final, 'files': len(entries), 'push': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('role', choices=('encode', 'self-test', 'publish-preflight', 'publish'))
    role = parser.parse_args().role
    if role == 'self-test':
        raise SystemExit(self_test())
    print(json.dumps(publish(role == 'publish-preflight') if role.startswith('publish') else encode(), ensure_ascii=False), flush=True)
