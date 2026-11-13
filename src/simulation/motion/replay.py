"""Export actual 042 LINK telemetry as a local, CDN-free WebGL replay.

This is ACTUAL PHYSX TELEMETRY REPLAY / NOT ISAAC RENDER. The exporter never
generates LINK poses from targets or FK. Full-rate validation precedes the
30 Hz display selection; the renderer is not an acceptance verifier.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
LINKS = ['Base'] + [f'Link{i}' for i in range(1, 7)]
ACCEPTED = 'ACTUAL_PHYSX_GENERAL_MOTION_VERIFIED'
LABEL = 'ACTUAL PHYSX TELEMETRY REPLAY / NOT ISAAC RENDER'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def constant(value):
        raise ValueError('Nonfinite JSON: ' + value)
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=constant,
                      object_pairs_hook=unique)


def vector(value, length):
    need(isinstance(value, (list, tuple)) and len(value) == length, 'Invalid numeric vector length')
    need(all(type(x) in (int, float) and math.isfinite(x) for x in value), 'Nonfinite numeric vector')
    return list(value)


def rotation(q):
    w, x, y, z = vector(q, 4)
    norm = math.sqrt(w*w + x*x + y*y + z*z)
    need(abs(norm - 1) <= 1e-4, 'Actual LINK orientation is not unit wxyz')
    w, x, y, z = [value / norm for value in (w, x, y, z)]
    return [[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
            [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
            [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]]


def records(run, summary, stride=4):
    """Require the full captured sequence, even when explicitly inspecting invalid data."""
    need(summary.get('kind') == 'ACTUAL_PHYSX_DRIVE_TELEMETRY'
         and summary.get('sample_count') == 6781 and summary.get('physics_steps') == 6780,
         'A complete actual 6781-record capture is required; no placeholder poses')
    need(summary.get('hardware_approved') is False and summary.get('physical_calibration') is False
         and summary.get('ring_geometry') == 'DEFERRED', 'Simulation-only scope changed')
    expected = summary.get('files_sha256', {})
    need(set(expected) == {'static.json', 'samples.ndjson', 'scene.usda'}, 'Missing raw data hash manifest')
    for name, digest in expected.items():
        need(sha(run/name) == digest, 'Raw captured file hash changed: ' + name)
    selected, count = [], 0
    with (run/'samples.ndjson').open(encoding='utf-8') as stream:
        for index, line in enumerate(stream):
            need(line.strip(), 'Empty actual telemetry row')
            row = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            need(type(row.get('index')) is int and row['index'] == index and index <= 6780,
                 'Actual telemetry indices are incomplete or reordered')
            q, target = vector(row['q_rad'], 6), vector(row['target_q_rad'], 6)
            qd = vector(row['qd_rad_s'], 6)
            vector(row['target_qd_rad_s'], 6)
            need(type(row['schedule_time_s']) in (int, float)
                 and abs(row['schedule_time_s']-index/120) <= 1e-8, 'Invalid display schedule index/time')
            clock = row['clock']['time_after_s']
            need(type(clock) in (int, float) and math.isfinite(clock), 'Missing actual observed clock')
            need(isinstance(row['segment'], str) and (row['checkpoint'] is None or isinstance(row['checkpoint'], str)),
                 'Invalid segment/checkpoint labels')
            poses = row['links']
            need(isinstance(poses, list) and len(poses) == 7
                 and {pose['name'] for pose in poses} == set(LINKS), 'Seven unique actual LINK poses required')
            by_name = {pose['name']: pose for pose in poses}
            actual = []
            for name in LINKS:
                pose = by_name[name]
                position = vector(pose['position'], 3)
                quaternion = vector(pose['orientation_wxyz'], 4)
                rotation(quaternion)
                actual.append(position + quaternion)
            if index % stride == 0 or index == 6780:
                selected.append({'index': index, 'time_s': index/120, 'observed_time_s': clock,
                                 'segment': row['segment'], 'checkpoint': row['checkpoint'],
                                 'q': q, 'target': target, 'qd': qd, 'poses': actual})
            count += 1
    need(count == 6781 and len(selected) == (6780//stride+1), 'Full-rate or selected frame census mismatch')
    return selected


def stl(path):
    """Read binary or ASCII STL into complete triangle positions without decimation."""
    import numpy as np
    raw = Path(path).read_bytes()
    if len(raw) >= 84 and len(raw) == 84 + 50 * struct.unpack_from('<I', raw, 80)[0]:
        dtype = np.dtype([('normal', '<f4', 3), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
        triangles = np.frombuffer(raw, dtype=dtype, offset=84)['vertices'].astype(np.float64)
    else:
        values = []
        for line in raw.decode('ascii').splitlines():
            tokens = line.split()
            if tokens and tokens[0] == 'vertex':
                need(len(tokens) == 4, 'Malformed ASCII STL vertex')
                values.append([float(value) for value in tokens[1:]])
        need(values and len(values) % 3 == 0, 'Malformed or empty STL')
        triangles = np.array(values, dtype=np.float64).reshape((-1, 3, 3))
    need(triangles.size > 0 and bool(np.isfinite(triangles).all()), 'Empty/nonfinite STL')
    return triangles


def geometry(root, run, first_poses):
    """Bake URDF visual-local transforms only; animation always uses raw LINK poses."""
    import numpy as np
    package = root/'models/robot-arm-urdf-v1'
    manifest = load(package/'manifest.json')['files']
    urdf = package/'robot_arm.urdf'
    need(sha(urdf) == manifest['robot_arm.urdf'] == sha(run/'reference.urdf'), 'Replay URDF reference drift')
    job = load(run/'job.json')
    need(sha(urdf) == job['files_sha256']['reference.urdf'], 'Captured URDF input binding changed')
    tree = ET.parse(urdf).getroot()
    materials = {item.attrib['name']: [float(x) for x in item.find('color').attrib['rgba'].split()][:3]
                 for item in tree.findall('material')}
    chunks, meshes, sources, total_vertices, bounds = [], [], {}, 0, []
    links = {element.attrib['name']: element for element in tree.findall('link')}
    need(set(links) == set(LINKS), 'Seven canonical visual links required')
    for link_index, name in enumerate(LINKS):
        actual = first_poses[link_index]
        world_r = np.array(rotation(actual[3:]), dtype=np.float64)
        for visual in links[name].findall('visual'):
            mesh = visual.find('geometry/mesh')
            need(mesh is not None, 'Replay supports only the bound visual STL geometry')
            relative = mesh.attrib['filename']
            path = (package/relative).resolve()
            need(path.is_relative_to((package/'meshes').resolve()) and relative in manifest
                 and sha(path) == manifest[relative], 'STL manifest/path drift: ' + relative)
            sources[relative] = sha(path)
            triangles = stl(path)
            scale = np.array([float(x) for x in mesh.get('scale', '1 1 1').split()])
            need(scale.shape == (3,) and bool(np.isfinite(scale).all()) and bool((scale > 0).all()), 'Invalid visual scale')
            triangles *= scale
            origin = visual.find('origin')
            if origin is not None:
                # No current package visual has an origin; never silently ignore a future frame.
                need(origin.get('xyz', '0 0 0') == '0 0 0' and origin.get('rpy', '0 0 0') == '0 0 0',
                     'Nonidentity visual frame requires an explicit exporter update')
            normal = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
            magnitude = np.linalg.norm(normal, axis=1)
            degenerate = magnitude <= 1e-16
            normal[~degenerate] /= magnitude[~degenerate, None]
            normal[degenerate] = [0, 0, 1]
            vertices = triangles.reshape((-1, 3))
            normals = np.repeat(normal, 3, axis=0)
            chunks.append(np.concatenate((vertices, normals), axis=1).astype('<f4').tobytes())
            material = visual.find('material')
            color = materials[material.attrib['name']]
            count = len(vertices)
            meshes.append({'name': visual.attrib['name'], 'link': link_index, 'first': total_vertices,
                           'count': count, 'color': color, 'degenerate_faces': int(degenerate.sum())})
            world = vertices @ world_r.T + np.array(actual[:3])
            bounds.append((world.min(axis=0), world.max(axis=0)))
            total_vertices += count
    need(len(meshes) == 31 and len(sources) == 31 and total_vertices == 198280*3,
         'Expected all 31 source visuals and 198280 triangles')
    lower = np.array([pair[0] for pair in bounds]).min(axis=0)
    upper = np.array([pair[1] for pair in bounds]).max(axis=0)
    return b''.join(chunks), meshes, sources, {'center': ((lower+upper)/2).tolist(),
                                            'extent': float(max(upper-lower))}


def video_frame(binary, meshes, frame, camera, accepted, progress, width=960, height=640):
    """Software projection/painter of observed LINK poses, with visible provenance.

    This renderer approximates visibility by triangle depth sorting. It is not
    an Isaac viewport capture and does not evaluate contact or motion quality.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    values = np.frombuffer(binary, dtype='<f4').reshape((-1, 6))
    center = np.array(camera['center'])
    azimuth, elevation = -1.1 + .25*progress, .45
    distance = max(.5, camera['extent']*2.0)
    eye = center + distance*np.array([math.cos(elevation)*math.cos(azimuth),
                                     math.cos(elevation)*math.sin(azimuth), math.sin(elevation)])
    forward = center-eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 0, 1])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    view = np.array([right, up, forward])
    viewport_w, top, bottom = 680, 110, 565
    focal = (bottom-top)/(2*math.tan(math.pi/7))
    light = np.array([-.3, -.5, 1.])
    light /= np.linalg.norm(light)
    polygon_chunks, depth_chunks, color_chunks = [], [], []
    for mesh in meshes:
        pose = frame['poses'][mesh['link']]
        r = np.array(rotation(pose[3:]))
        local = values[mesh['first']:mesh['first']+mesh['count']]
        triangles = local[:, :3].reshape((-1, 3, 3)).astype(np.float64)
        normals = local[::3, 3:].astype(np.float64) @ r.T
        world = np.einsum('ij,nkj->nki', r, triangles) + np.array(pose[:3])
        camera_vertices = np.einsum('ij,nkj->nki', view, world-eye)
        z = camera_vertices[:, :, 2]
        safe_z = np.maximum(z, .005)
        screen = np.stack((viewport_w/2 + focal*camera_vertices[:, :, 0]/safe_z,
                           (top+bottom)/2 - focal*camera_vertices[:, :, 1]/safe_z), axis=2)
        delta1, delta2 = screen[:, 1]-screen[:, 0], screen[:, 2]-screen[:, 0]
        area2 = np.abs(delta1[:, 0]*delta2[:, 1]-delta1[:, 1]*delta2[:, 0])
        visible = ((z.min(axis=1) > .005) & (area2 > .15)
                   & ((normals*(eye-world.mean(axis=1))).sum(axis=1) > 0)
                   & (screen[:, :, 0].max(axis=1) >= 0) & (screen[:, :, 0].min(axis=1) < viewport_w)
                   & (screen[:, :, 1].max(axis=1) >= top) & (screen[:, :, 1].min(axis=1) < bottom))
        shade = .33 + .55*np.maximum(0, normals @ light) + .12*np.abs(normals[:, 2])
        color = np.clip((np.array(mesh['color'])[None, :]*shade[:, None])**.88*255, 0, 255).astype(np.uint8)
        polygon_chunks.append(np.rint(screen[visible]).astype(np.int32))
        depth_chunks.append(z.mean(axis=1)[visible])
        color_chunks.append(color[visible])
    image = Image.new('RGB', (width, height), '#0b1420')
    draw = ImageDraw.Draw(image)
    # A subdued projected floor grid is a display aid, not a collision object.
    for axis in range(2):
        for value in np.arange(-.7, .81, .1):
            points = np.array([[-.8, value, -.001], [.8, value, -.001]])
            if axis:
                points = points[:, [1, 0, 2]]
            p = (points-eye) @ view.T
            if p[:, 2].min() > .005:
                xy = np.column_stack((viewport_w/2+focal*p[:, 0]/p[:, 2],
                                      (top+bottom)/2-focal*p[:, 1]/p[:, 2]))
                draw.line(tuple(map(tuple, xy)), fill='#1c2d3d', width=1)
    polygons = np.concatenate(polygon_chunks)
    colors = np.concatenate(color_chunks)
    for index in np.argsort(np.concatenate(depth_chunks))[::-1]:
        draw.polygon([tuple(point) for point in polygons[index]], fill=tuple(int(x) for x in colors[index]))
    def font(size, bold=False):
        windows_dir = os.environ.get('WINDIR')
        if not windows_dir:
            return ImageFont.load_default(size=size)
        path = Path(windows_dir)/'Fonts'/('segoeuib.ttf' if bold else 'segoeui.ttf')
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            return ImageFont.load_default(size=size)
    normal, small, large = font(17), font(13), font(24, True)
    draw.rectangle((0, 0, width, top), fill='#0b1420')
    draw.text((22, 16), 'ROBOT ARM LAB / SIMULATION 042', font=small, fill='#78cdbf')
    draw.text((22, 38), '6-axis basic motion / actual observed LINK poses', font=large, fill='#e5eef6')
    draw.text((22, 76), LABEL, font=small, fill='#a9bfce')
    draw.rectangle((viewport_w, top, width, height), fill='#101d2b')
    draw.text((700, 130), 'JOINT ANGLES / DEGREES', font=normal, fill='#95afc0')
    draw.text((700, 164), 'Axis       Target        Actual', font=small, fill='#93a9ba')
    for i, (target, actual) in enumerate(zip(frame['target'], frame['q'])):
        y = 202+i*37
        draw.text((700, y), f'J{i+1}', font=normal, fill='#cad9e3')
        draw.text((745, y), f'{math.degrees(target):7.3f}', font=normal, fill='#93a9ba')
        draw.text((850, y), f'{math.degrees(actual):7.3f}', font=normal, fill='#8ee4cc')
    draw.text((700, 452), 'MASS / INERTIA ASSUMED', font=small, fill='#99b4c4')
    draw.text((700, 477), 'HARDWARE APPROVED: FALSE', font=small, fill='#99b4c4')
    draw.text((700, 502), 'RING GEOMETRY: DEFERRED', font=small, fill='#99b4c4')
    draw.text((700, 535), 'VALIDATED TELEMETRY' if accepted else 'INVALID / NO ACCEPTANCE',
              font=small, fill='#8ee4cc' if accepted else '#ff9cac')
    draw.rectangle((0, bottom, viewport_w, height), fill='#0b1420')
    draw.text((22, 577), frame['segment'], font=normal, fill='#b9e6da')
    draw.text((22, 608), f"Observed PhysX {frame['observed_time_s']:.6f} s / source sample {frame['index']}",
              font=small, fill='#9ab2c4')
    draw.text((452, 578), f"{frame['time_s']:6.2f} / 56.50 s", font=normal, fill='#c6dde8')
    draw.text((452, 609), '12 s compressed replay', font=small, fill='#9ab2c4')
    return image


def render_video(binary, meshes, frames, camera, accepted, path):
    """12 s / 24 fps MP4 from closest raw 120 Hz observations; no pose interpolation."""
    ffmpeg = shutil.which('ffmpeg')
    need(ffmpeg is not None, 'Existing ffmpeg on PATH is required for --video; no installation attempted')
    count, fps = 288, 24
    indices = [round(index*6780/(count-1)) for index in range(count)]
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostats', '-y',
               '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '960x640',
               '-framerate', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
               '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
               '-metadata', 'comment='+LABEL+'; MASS ASSUMED; HARDWARE FALSE; RING DEFERRED', str(path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        for number, index in enumerate(indices):
            image = video_frame(binary, meshes, frames[index], camera, accepted, number/(count-1))
            process.stdin.write(image.tobytes())
        process.stdin.close()
        process.stdin = None
        _, stderr = process.communicate(timeout=60)
        need(process.returncode == 0 and Path(path).is_file(), 'ffmpeg failed: '+stderr.decode('utf-8', errors='replace'))
    except Exception:
        process.kill()
        process.wait(timeout=10)
        if Path(path).is_file():
            Path(path).unlink()
        raise
    return {'kind': LABEL, 'file': Path(path).name, 'duration_s': 12, 'fps': fps, 'frame_count': count,
            'size': [960, 640], 'source_indices': indices, 'pose_interpolation': False,
            'renderer': 'NUMPY_PIL_SOFTWARE_PAINTER_NOT_ISAAC_VIEWPORT',
            'acceptance': ACCEPTED if accepted else 'INVALID / NO ACCEPTANCE'}


def export(run, root, out, allow_invalid=False, video=False):
    run, root, out = Path(run).resolve(), Path(root).resolve(), Path(out).resolve()
    summary, report = load(run/'summary.json'), load(run/'validation.json')
    need(summary.get('run_id') == run.name, 'Actual run directory identity differs')
    actual_frames = records(run, summary, stride=1)
    frames = actual_frames[::4]
    reasons, accepted = [], False
    try:
        need(report.get('status') == ACCEPTED and report.get('run_id') == summary['run_id']
             and report.get('runtime') == summary['runtime'], 'Public validation is not an accepted matching run')
        spec = importlib.util.spec_from_file_location('motion_replay_verifier', root/'src/simulation/motion/verify.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        fresh = verifier.verify_run(run, root)
        need(fresh['status'] == ACCEPTED and fresh['run_id'] == report['run_id']
             and fresh['runtime'] == report['runtime'], 'Fresh source/data binding verification did not accept this run')
        accepted = True
    except Exception as exc:
        reasons.append(f'{type(exc).__name__}: {exc}')
        if not allow_invalid:
            raise ValueError('Replay requires current accepted validation; --allow-invalid is inspection only: '+reasons[-1]) from exc
    binary, meshes, sources, camera = geometry(root, run, frames[0]['poses'])
    data = {'label': LABEL, 'run_id': summary['run_id'], 'accepted': accepted,
            'acceptance': ACCEPTED if accepted else 'INVALID / NO ACCEPTANCE', 'reasons': reasons,
            'mass_inertia': 'SIMULATION ASSUMPTION', 'hardware_approved': False,
            'physical_calibration': False, 'ring_geometry': 'DEFERRED',
            'render_source': 'OBSERVED_LINK_POSITION_AND_WXYZ_ONLY', 'display_hz': 30,
            'source_sample_count': 6781, 'display_frame_count': len(frames), 'triangles': 198280,
            'duration_s': 56.5, 'meshes': meshes, 'camera': camera, 'frames': frames}
    out.mkdir(parents=True, exist_ok=True)
    (out/'geometry.bin').write_bytes(binary)
    (out/'telemetry.json').write_text(json.dumps(data, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    (out/'index.html').write_text(HTML, encoding='utf-8')
    movie = render_video(binary, meshes, actual_frames, camera, accepted, out/'actual-telemetry-replay.mp4') if video else None
    binding = {'kind': LABEL, 'acceptance': data['acceptance'], 'run_dir': str(run),
               'sources_sha256': {name: sha(run/name) for name in ('summary.json', 'validation.json', 'samples.ndjson',
                                                                  'static.json', 'scene.usda', 'reference.urdf', 'job.json')},
               'visual_sources_sha256': sources, 'replay_py_sha256': sha(__file__),
               'outputs_sha256': {name: sha(out/name) for name in ('index.html', 'telemetry.json', 'geometry.bin')},
               'hardware_approved': False, 'ring_geometry': 'DEFERRED'}
    if movie:
        binding['video'] = movie
        binding['outputs_sha256'][movie['file']] = sha(out/movie['file'])
    (out/'replay-manifest.json').write_text(json.dumps(binding, indent=2)+'\n', encoding='utf-8')
    return {'out': str(out), 'acceptance': data['acceptance'], 'frames': len(frames), 'triangles': 198280,
            'video': movie['file'] if movie else 'NOT_REQUESTED'}


HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot Arm Lab · Actual telemetry replay</title><style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif;color:#dce8f2;background:#0a101a}*{box-sizing:border-box}body{margin:0}header{padding:22px 28px;border-bottom:1px solid #253140;display:flex;justify-content:space-between;gap:20px;align-items:center}h1{font-size:21px;margin:4px 0 8px;font-weight:650}.eyebrow{color:#6ad6c9;font-size:11px;letter-spacing:.13em;font-weight:700}.muted{color:#91a3b5;font-size:12px;line-height:1.6}.badge{border:1px solid #27786e;background:#13352f;color:#85e3cf;padding:9px 12px;border-radius:6px;font-size:11px;letter-spacing:.04em}.invalid .badge{background:#4b1823;border-color:#e47582;color:#ffb9c0}.layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;min-height:calc(100vh - 108px)}.stage{position:relative;min-height:580px;background:radial-gradient(ellipse at center,#172638,#0b121d 75%)}canvas{display:block;width:100%;height:100%;position:absolute;touch-action:none}.watermark{position:absolute;left:24px;top:20px;pointer-events:none;font:10px ui-monospace,monospace;color:#91b9bb;letter-spacing:.06em}.invalid .watermark{color:#ff9eaa;font-weight:700}.scene-note{position:absolute;left:24px;bottom:125px;pointer-events:none;color:#92a5ba;font-size:11px;line-height:1.7}.transport{position:absolute;left:20px;right:20px;bottom:20px;padding:15px 17px;background:#0a111de8;border:1px solid #2c4054;border-radius:10px;backdrop-filter:blur(8px)}.row{display:flex;gap:12px;align-items:center;justify-content:space-between}.controls{display:flex;gap:8px;align-items:center}button,select{border:1px solid #364d60;background:#1a2b3c;color:#e9f4ff;border-radius:5px;padding:7px 12px;font-size:12px}button:hover{background:#29475b}button.primary{background:#316b69;border-color:#4a9691}input[type=range]{width:100%;accent-color:#6ed3c5;margin:16px 0 9px}aside{background:#0e1724;border-left:1px solid #253344;padding:23px 20px}h2{font-size:12px;letter-spacing:.08em;color:#8fa8bf;text-transform:uppercase;margin:0 0 14px}.phase{font:15px ui-monospace,monospace;color:#a6e3d6;min-height:42px;overflow-wrap:anywhere}.card{padding-bottom:23px;margin-bottom:23px;border-bottom:1px solid #253344}table{width:100%;border-collapse:collapse;font:12px ui-monospace,monospace}th{color:#7e96ab;font-size:10px;font-weight:500;text-align:right;padding:8px 0}td{text-align:right;padding:9px 0;border-top:1px solid #202e3e}td:first-child,th:first-child{text-align:left}td:nth-child(3){color:#94e0cf}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:16px}.metric strong{display:block;font-size:16px;color:#d7e9f5;margin:4px 0}.metric small{font-size:10px;color:#859db2}.warning{color:#e8a4ac;font-size:11px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere}.clock{font:12px ui-monospace,monospace;color:#aec8d9}#error{position:absolute;inset:20%;padding:30px;background:#351923;border:1px solid #a75366;white-space:pre-wrap;display:none}#checkpoint{color:#7c9dac;font-size:10px;min-height:20px}details{font-size:11px;color:#7894ab;overflow-wrap:anywhere}summary{cursor:pointer}@media(max-width:900px){header{padding:16px;display:block}header>.badge{margin-top:12px;display:inline-block}.layout{grid-template-columns:1fr}.stage{min-height:64vh}aside{border-left:0;border-top:1px solid #253344}.watermark{font-size:8px;left:12px}.scene-note{left:14px}.transport{left:10px;right:10px}.metrics{grid-template-columns:repeat(4,1fr)}}
</style></head><body><header><div><div class="eyebrow">ROBOT ARM LAB / SIMULATION 042</div><h1>6축 일반동작 · 실제 관측 재생</h1><div class="muted">ACTUAL PHYSX TELEMETRY REPLAY / NOT ISAAC RENDER</div></div><div id="status" class="badge">Loading captured data…</div></header>
<main class="layout"><section class="stage"><canvas id="canvas"></canvas><div class="watermark" id="watermark">OBSERVED LINK POSES ONLY · NOT ISAAC RENDER</div><div class="scene-note">드래그: 회전 · 휠: 확대/축소<br>격자 100 mm · 표시 자세 대비 관절각 · 30 Hz 관측 표본</div><div class="transport"><div class="row"><div class="controls"><button id="play" class="primary">재생</button><button id="reset">처음</button><select id="speed"><option value=".25">0.25×</option><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></div><span class="clock" id="time">0.000 / 56.500 s</span></div><input id="seek" type="range" min="0" max="1695" value="0" step="1"><div class="row"><span class="muted" id="sample">Sample —</span><span class="muted" id="observed">PhysX time —</span></div></div><div id="error"></div></section>
<aside><section class="card"><h2>Motion segment</h2><div class="phase" id="phase">—</div><div id="checkpoint"></div><table><thead><tr><th>축</th><th>목표 °</th><th>관측 °</th><th>오차 °</th></tr></thead><tbody id="joints"></tbody></table></section><section class="card metrics"><div class="metric"><small>전체 관측</small><strong>6,781</strong><small>120 Hz source</small></div><div class="metric"><small>표시 프레임</small><strong>1,696</strong><small>30 Hz selected</small></div><div class="metric"><small>형상</small><strong>198,280</strong><small>31 STL · triangles</small></div><div class="metric"><small>최대 축속도</small><strong id="velocity">—</strong><small>관측 °/s</small></div></section><section class="card"><h2>Scope</h2><div class="muted">Mass / inertia: SIMULATION ASSUMPTION<br>Hardware approved: FALSE<br>Physical calibration: FALSE<br>Ring geometry: DEFERRED<br>Rendered transforms: actual LINK observations<br>Rendering: local WebGL, independent of Isaac renderer</div></section><div id="reason" class="warning"></div><details><summary>Run identity / source</summary><p id="identity"></p><p>원자료와 STL의 SHA256 결속은 replay-manifest.json에 보존합니다. 이 화면의 재생은 검증 판정을 수행하지 않습니다.</p></details></aside></main>
<script>
'use strict';
const $=id=>document.getElementById(id), canvas=$('canvas');
function fail(e){$('error').style.display='block';$('error').textContent='Replay unavailable\n'+e.message;$('status').textContent='NOT AVAILABLE';console.error(e)}
function mul(a,b){let r=new Float32Array(16);for(let c=0;c<4;c++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)r[c*4+row]+=a[k*4+row]*b[c*4+k];return r}
function pose(v){let [px,py,pz,w,x,y,z]=v,n=Math.hypot(w,x,y,z);w/=n;x/=n;y/=n;z/=n;return new Float32Array([1-2*(y*y+z*z),2*(x*y+w*z),2*(x*z-w*y),0,2*(x*y-w*z),1-2*(x*x+z*z),2*(y*z+w*x),0,2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y),0,px,py,pz,1])}
const norm=a=>{let n=Math.hypot(...a);return a.map(x=>x/n)},cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
function lookAt(eye,target){let z=norm(eye.map((v,i)=>v-target[i])),x=norm(cross([0,0,1],z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1])}
function perspective(aspect){let f=1/Math.tan(Math.PI/7),n=.005,far=100;return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+n)/(n-far),-1,0,0,2*far*n/(n-far),0])}
async function start(){
const [response,binaryResponse]=await Promise.all([fetch('telemetry.json'),fetch('geometry.bin')]);if(!response.ok||!binaryResponse.ok)throw Error('Serve this directory using a local HTTP server.');
const d=await response.json(),binary=await binaryResponse.arrayBuffer();if(d.render_source!=='OBSERVED_LINK_POSITION_AND_WXYZ_ONLY'||d.frames.length!==1696||binary.byteLength!==198280*3*6*4)throw Error('Display payload shape differs from the bound export.');
document.body.classList.toggle('invalid',!d.accepted);$('status').textContent=d.accepted?'ACTUAL TELEMETRY · VALIDATED':'INVALID / NO ACCEPTANCE';$('watermark').textContent=(d.accepted?'OBSERVED LINK POSES ONLY':'INVALID / NO ACCEPTANCE')+' · NOT ISAAC RENDER';$('reason').textContent=d.reasons.join('\n');$('identity').textContent=d.run_id;$('seek').max=d.frames.length-1;
const gl=canvas.getContext('webgl',{antialias:true,alpha:false});if(!gl)throw Error('WebGL is unavailable.');
function shader(type,source){let s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 aP;attribute vec3 aN;uniform mat4 uVP;uniform mat4 uM;varying vec3 vN;varying vec3 vP;void main(){vec4 p=uM*vec4(aP,1.0);vP=p.xyz;vN=mat3(uM)*aN;gl_Position=uVP*p;}'));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec3 vN;varying vec3 vP;uniform vec3 uColor;uniform float uUnlit;void main(){vec3 n=normalize(vN);float lit=.33+.55*max(0.0,dot(n,normalize(vec3(-.3,-.5,1.0))))+.12*abs(n.z);vec3 c=uColor*mix(lit,1.0,uUnlit);gl_FragColor=vec4(pow(c,vec3(.88)),1.0);}'));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
const aP=gl.getAttribLocation(program,'aP'),aN=gl.getAttribLocation(program,'aN'),uVP=gl.getUniformLocation(program,'uVP'),uM=gl.getUniformLocation(program,'uM'),uColor=gl.getUniformLocation(program,'uColor'),uUnlit=gl.getUniformLocation(program,'uUnlit');
const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,binary,gl.STATIC_DRAW);gl.enableVertexAttribArray(aP);gl.enableVertexAttribArray(aN);
const grid=[];for(let i=-10;i<=10;i++){let t=i*.1;grid.push(-1,t,-.001,0,0,1,1,t,-.001,0,0,1,t,-1,-.001,0,0,1,t,1,-.001,0,0,1)}let gridBuffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,gridBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(grid),gl.STATIC_DRAW);
const identity=new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);let azimuth=-1.1,elevation=.45,distance=Math.max(.5,d.camera.extent*1.9),center=d.camera.center,index=0,playing=false,last=0,playTime=0,displayed=-1;
function bind(b){gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.vertexAttribPointer(aP,3,gl.FLOAT,false,24,0);gl.vertexAttribPointer(aN,3,gl.FLOAT,false,24,12)}
function updateText(f){$('phase').textContent=f.segment;$('checkpoint').textContent=f.checkpoint?'CHECKPOINT · '+f.checkpoint:' ';$('time').textContent=f.time_s.toFixed(3)+' / 56.500 s';$('sample').textContent='Source sample '+f.index+' / 6780';$('observed').textContent='PhysX '+f.observed_time_s.toFixed(6)+' s';$('velocity').textContent=(Math.max(...f.qd.map(Math.abs))*180/Math.PI).toFixed(3);$('joints').innerHTML=f.q.map((q,i)=>'<tr><td>J'+(i+1)+'</td><td>'+(f.target[i]*180/Math.PI).toFixed(3)+'</td><td>'+(q*180/Math.PI).toFixed(3)+'</td><td>'+((q-f.target[i])*180/Math.PI).toFixed(3)+'</td></tr>').join('');$('seek').value=index}
function draw(now){const elapsed=last?Math.min(.1,(now-last)/1000):0;last=now;if(playing){playTime=Math.min(d.duration_s,playTime+elapsed*Number($('speed').value));index=Math.min(d.frames.length-1,Math.floor(playTime*30+1e-8));if(playTime>=d.duration_s){playing=false;$('play').textContent='재생'}}const f=d.frames[index];if(displayed!==index){updateText(f);displayed=index}let scale=Math.min(devicePixelRatio||1,2),w=Math.round(canvas.clientWidth*scale),h=Math.round(canvas.clientHeight*scale);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}gl.viewport(0,0,w,h);gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);gl.clearColor(.035,.06,.095,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);let eye=[center[0]+distance*Math.cos(elevation)*Math.cos(azimuth),center[1]+distance*Math.cos(elevation)*Math.sin(azimuth),center[2]+distance*Math.sin(elevation)];gl.uniformMatrix4fv(uVP,false,mul(perspective(w/h),lookAt(eye,center)));bind(gridBuffer);gl.uniformMatrix4fv(uM,false,identity);gl.uniform3fv(uColor,[.12,.20,.27]);gl.uniform1f(uUnlit,1);gl.drawArrays(gl.LINES,0,grid.length/6);bind(buffer);gl.uniform1f(uUnlit,0);const models=f.poses.map(pose);for(const mesh of d.meshes){gl.uniformMatrix4fv(uM,false,models[mesh.link]);gl.uniform3fv(uColor,mesh.color);gl.drawArrays(gl.TRIANGLES,mesh.first,mesh.count)}requestAnimationFrame(draw)}
$('play').onclick=()=>{if(index===d.frames.length-1){playTime=0;index=0}playing=!playing;$('play').textContent=playing?'일시정지':'재생'};$('reset').onclick=()=>{playing=false;playTime=0;index=0;$('play').textContent='재생'};$('seek').oninput=()=>{index=Number($('seek').value);playTime=d.frames[index].time_s};let drag=null;canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};canvas.onpointerup=()=>drag=null;canvas.onpointercancel=()=>drag=null;canvas.onpointermove=e=>{if(!drag)return;azimuth-=(e.clientX-drag[0])*.007;elevation=Math.max(.06,Math.min(1.48,elevation+(e.clientY-drag[1])*.007));drag=[e.clientX,e.clientY]};canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(.18,Math.min(5,distance*Math.exp(e.deltaY*.001)))},{passive:false});requestAnimationFrame(draw)
}start().catch(fail);
</script></body></html>'''


def self_test():
    """Small embedded parser/frame regressions, never represented as actual telemetry."""
    import numpy as np
    q = [math.sqrt(.5), 0, 0, math.sqrt(.5)]
    need(np.allclose(rotation(q), [[0, -1, 0], [1, 0, 0], [0, 0, 1]]), 'wxyz rotation convention')
    need(np.allclose(rotation(q), rotation([-x for x in q])), 'Quaternion sign equivalence')
    for bad in ([0, 0, 0, 0], [1, 0, 0], [float('nan'), 0, 0, 0]):
        try:
            rotation(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid quaternion accepted')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'triangle.stl'
        raw = bytes(80) + struct.pack('<I', 1) + struct.pack('<12fH', 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0)
        path.write_bytes(raw)
        binary = stl(path)
        path.write_text('solid s\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid s', encoding='ascii')
        need(np.array_equal(binary, stl(path)), 'ASCII/binary STL parser parity')
    need('https://' not in HTML and 'http://' not in HTML, 'Unexpected external renderer dependency')
    # This tiny in-memory fixture exercises projection only, and is never exported.
    triangle = np.array([[0, 0, 0, 0, 0, 1], [.1, 0, 0, 0, 0, 1],
                         [0, .1, 0, 0, 0, 1]], dtype='<f4').tobytes()
    frame = {'poses': [[0, 0, 0, 1, 0, 0, 0]]*7, 'q': [0]*6, 'target': [0]*6,
             'segment': 'HOST_SYNTHETIC_RENDERER_FIXTURE', 'observed_time_s': 0., 'index': 0, 'time_s': 0.}
    mesh = [{'link': 0, 'first': 0, 'count': 3, 'color': [.9, .6, .2]}]
    camera = {'center': [.05, .05, 0], 'extent': .2}
    image = video_frame(triangle, mesh, frame, camera, False, 0.)
    need(image.size == (960, 640) and image.mode == 'RGB', 'Video helper output shape')
    need(image.getpixel((15, 150)) != image.getpixel((700, 150)), 'Scene/sidebar rendering boundary')
    return {'status': 'HOST_REPLAY_HELPERS_ONLY', 'checks': 9, 'actual_telemetry_export': 'NOT_RUN',
            'actual_video_encode': 'NOT_RUN'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--allow-invalid', action='store_true', help='Inspect complete hash-bound failed data; NO ACCEPTANCE')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--video', action='store_true', help='Also encode a 12 s actual-pose telemetry replay MP4')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
        return 0
    parser.error('--run-dir is required') if args.run_dir is None else None
    out = args.out or args.root/'outputs/isaac-motion-v1/viewer'
    print(json.dumps(export(args.run_dir, args.root, out, args.allow_invalid, args.video)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
