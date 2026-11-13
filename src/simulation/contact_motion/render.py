"""043 short video from actual LINK observations, with gravity/contact evidence labels."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from PIL import ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
BASE_REPLAY_SHA='bebe2eadd8078b532ada251e24e91d5cebf8fad7ca919127f742b89472abaaa8'


def load_module(name,path,approved_sha=None):
    if approved_sha is not None and hashlib.sha256(Path(path).read_bytes()).hexdigest()!=approved_sha:
        raise ValueError('Approved replay dependency hash drift')
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(run,root,out):
    v=load_module('_gravity_video_verifier',Path(__file__).with_name('verify.py'))
    report=json.loads((run/'validation.json').read_text(encoding='utf-8'))
    fresh=v.verify_run(run,root)
    if not fresh['evidence_valid'] or report['status']!=fresh['status'] or report['runtime']!=fresh['runtime']:
        raise ValueError('Video requires matching hash-bound complete actual evidence')
    accepted=report['status']=='GRAVITY_COLLISION_MOTION_PASS'
    replay_path=root/'src/simulation/motion/replay.py'
    replay=load_module('_gravity_video_primitives',replay_path,BASE_REPLAY_SHA)
    summary=json.loads((run/'summary.json').read_text())
    frames=replay.records(run,summary,stride=1)
    with (run/'samples.ndjson').open(encoding='utf-8') as stream:
        for frame,line in zip(frames,stream):
            row=json.loads(line)
            frame['probe_z_m']=row['probe_pose']['position'][2]
            frame['probe_force_N']=row['contacts']['normal_force_N'][7][0][2]
    binary,meshes,sources,camera=replay.geometry(root,run,frames[0]['poses'])
    original=replay.video_frame
    font_dir=Path(os.environ.get('WINDIR',''))/'Fonts'
    def font(size,bold=False):
        try:return ImageFont.truetype(str(font_dir/('segoeuib.ttf' if bold else 'segoeui.ttf')),size)
        except OSError:return ImageFont.load_default(size=size)
    def observed_frame(binary,meshes,frame,camera,accepted,progress):
        image=original(binary,meshes,frame,camera,accepted,progress)
        draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,960,110),fill='#0b1420')
        draw.text((22,16),'ROBOT ARM LAB / SIMULATION 043',font=font(13),fill='#78cdbf')
        draw.text((22,38),'6-axis motion / GRAVITY + COLLISION',font=font(24,True),fill='#e5eef6')
        draw.text((22,76),'ACTUAL PHYSX TELEMETRY REPLAY / NOT ISAAC RENDER',font=font(13),fill='#a9bfce')
        draw.rectangle((680,440,960,640),fill='#101d2b')
        lines=['GRAVITY: -9.81 m/s2','COLLISION: ON / SELF: ON',
            f"PROBE Z: {frame['probe_z_m']:.4f} m",f"PROBE FLOOR FORCE: {frame['probe_force_N']:.3f} N",
            'MASS / INERTIA: ASSUMED','HARDWARE / CALIBRATION: FALSE','RING GEOMETRY: DEFERRED',
            'DYNAMICS PASS' if accepted else 'DYNAMICS FAILED / NO ACCEPTANCE']
        for i,text in enumerate(lines):
            draw.text((700,451+i*22),text,font=font(12),fill=('#8ee4cc' if accepted else '#ff9cac') if i==7 else '#99b4c4')
        return image
    replay.video_frame=observed_frame  # Local adapter; the immutable 042 source file is not edited.
    out.mkdir(parents=True,exist_ok=True)
    try:
        movie=replay.render_video(binary,meshes,frames,camera,accepted,out/'gravity-collision-12s.mp4')
    finally:
        replay.video_frame=original
    movie['acceptance']=report['status']
    first=observed_frame(binary,meshes,frames[0],camera,accepted,0.)
    last=observed_frame(binary,meshes,frames[-1],camera,accepted,1.)
    first.save(out/'first.png');last.save(out/'last.png')
    binding={'status':report['status'],'render_source':'ACTUAL_OBSERVED_LINK_POSES_ONLY',
        'video':movie,'video_sha256':sha(out/movie['file']),'run_id':run.name,
        'raw_sha256':{n:sha(run/n) for n in ('samples.ndjson','summary.json','static.json','validation.json')},
        'code_sha256':{'render.py':sha(__file__),'042_replay.py':sha(replay_path)},'visual_sources_sha256':sources,
        'gravity_m_s2':[0,0,-9.81],'collision_enabled':True,'self_collisions':True,
        'physical_verified':False,'mass_inertia':'SIMULATION_ASSUMPTION','ring_geometry':'DEFERRED'}
    (out/'video-manifest.json').write_text(json.dumps(binding,indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'status':report['status'],'video':str(out/movie['file']),'duration_s':12}


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--run-dir',type=Path,required=True)
    cli.add_argument('--root',type=Path,default=ROOT);cli.add_argument('--out',type=Path)
    a=cli.parse_args();print(json.dumps(export(a.run_dir,a.root,a.out or a.root/'outputs/isaac-contact-v1/viewer')))
