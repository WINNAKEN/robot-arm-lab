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
import hashlib, types
def _load_checked_driver127():
    value = (HERE/'driver.py').read_bytes()
    if hashlib.sha256(value).hexdigest() != '1c295b127b19cb452a2874d4d641913be80855d22bcbf4decead611965330ff0': raise ValueError('Derived driver pin before media execution')
    module = types.ModuleType('media_driver127'); module.__file__ = str(HERE/'driver.py')
    sys.modules[module.__name__] = module
    exec(compile(value,module.__file__,'exec'),module.__dict__)
    return module
D = _load_checked_driver127()
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
    cfg = C.parse(D._payload_bytes(HERE/'config.json'))
    capture_item = cfg['refs']['capture.py']
    raw = D._payload_bytes(C.path_in(D.ROOT,capture_item['path']))
    C.need(hashlib.sha256(raw).hexdigest() == capture_item['sha256'], 'Captured native frame validator pin')
    C.need(D._payload_bytes(OUT/'user-decision.json') == (OUT/'user-decision.json').read_bytes(), 'Actual current cap decision')
    capture = D.load_module('media_capture119', raw, folder/'original-capture.py')
    rows = validate_frames(folder, recovery['files_sha256'], capture)
    ffmpeg, ffprobe = commands()
    delivery = OUT/'delivery'
    D._local_write_guard(delivery).mkdir(parents=True, exist_ok=True)
    movie = delivery/'robot-arm-v4-127.mp4'
    C.need(not movie.exists(), 'Preserve existing movie; no overwrite')
    vf = filter_text(rows, result['phases'], result['status'])
    D._local_write_guard(movie)
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
        D._local_write_guard(delivery/('preview-%04d.png' % index))
        invoke([ffmpeg, '-hide_banner', '-v', 'error', '-n', '-i', str(movie),
                '-vf', 'select=eq(n\\,%d)' % index, '-frames:v', '1', str(delivery/('preview-%04d.png' % index))], timeout=30)
    clean = {'unit': 127, 'model': 'MP18 URDF v4', 'simulation_only': True,
             'hardware_approved': False, 'physical_communications': 'NOT_RUN',
             'status': result['status'], 'phases': [{'name': p['name'], 'status': p['status']} for p in result['phases']],
             'capture_provenance': result['capture_provenance'],
             'cap_mode': D.read(OUT/'user-decision.json')['cap_mode'],
             'frames': len(rows), 'fps': 10, 'video_duration_s': len(rows)/10,
             'movie': movie.name, 'movie_sha256': C.sha(movie),
             'limitations': ['Estimated masses and inertias; no physical performance acceptance.',
                             'Self collision disabled; no self contact safety acceptance.']}
    D.write(delivery/'result.json', clean)
    D.write(OUT/'D/media-manifest.json', {'unit': 127, 'run_id': record['run_id'], 'movie': str(movie),
            'sha256': C.sha(movie), 'bytes': movie.stat().st_size, 'ffprobe': probe,
            'original_frames': len(rows), 'sample_indices': samples, 'visual_inspection': 'PENDING',
            'capture_provenance': result['capture_provenance'],
            'upload_allowlist': [movie.name], 'hardware_approved': False})
    return clean


def self_test():
    raise ValueError('Legacy Git/publisher/self-test retired in127')


# Retired original publisher metadata
# Retired original publisher metadata
# Retired original publisher metadata


def owned():
    raise ValueError('Legacy Git/publisher/self-test retired in127')


def inventory():
    raise ValueError('Legacy Git/publisher/self-test retired in127')


def publisher_inputs():
    raise ValueError('Legacy Git/publisher/self-test retired in127')


def publish(preflight=False):
    raise ValueError('Legacy Git/publisher/self-test retired in127')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('encode',));parser.parse_args();print(json.dumps(encode(),ensure_ascii=False))
