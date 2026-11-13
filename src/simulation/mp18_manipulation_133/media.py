"""133 actual task frames to labelled MP4; no simulator, network or hardware entry."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def invoke(argv,timeout=180):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    if p.returncode!=0:raise ValueError('Media tool failed:'+p.stderr.decode('utf-8','replace')[-2000:])
    return p.stdout


def invoke_png(argv,frames,timeout=180):
    """Feed the exact verified immutable PNG bytes; filenames are never reopened by the codec."""
    if not isinstance(frames,tuple) or not frames or not all(type(b) is bytes for b in frames):
        raise ValueError('Immutable actual PNG sequence required')
    if not math.isfinite(timeout) or timeout<=0:raise ValueError('Positive bounded codec timeout')
    process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
    stream=process.stdin;process.stdin=None
    audit={'bytes':0,'frames':0};errors=[];hasher=hashlib.sha256()
    def produce():
        try:
            for raw in frames:
                view=memoryview(raw);offset=0
                while offset<len(view):
                    n=stream.write(view[offset:offset+1024*1024])
                    if type(n) is not int or n<=0:raise ValueError('Partial native PNG pipe write')
                    hasher.update(view[offset:offset+n]);audit['bytes']+=n;offset+=n
                audit['frames']+=1
            stream.flush()
        except BaseException as exc:errors.append(exc)
        finally:
            try:stream.close()
            except BaseException as exc:errors.append(exc)
    writer=threading.Thread(target=produce,name='133-verified-PNG-pipe',daemon=True);writer.start()
    try:
        try:stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill();process.communicate(timeout=2)
            raise TimeoutError('Native PNG codec deadline; child killed and reaped') from exc
        writer.join(timeout=2)
        if writer.is_alive():raise RuntimeError('Native PNG producer did not finish after codec reap')
        if errors:raise ValueError('Native PNG input failed:'+type(errors[0]).__name__+': '+str(errors[0])) from errors[0]
        if process.returncode!=0:raise ValueError('Native PNG codec failed:'+stderr.decode('utf-8','replace')[-2000:])
        if audit['frames']!=len(frames) or audit['bytes']!=sum(map(len,frames)):raise ValueError('Incomplete actual PNG stream')
        return {'png_bytes':audit['bytes'],'png_frames':audit['frames'],'input_sha256':hasher.hexdigest(),
                'child_pid':process.pid,'child_state':'REAPED','actual_exit_code':process.returncode,'errors':[]}
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=2)
        writer.join(timeout=2)


def encode_video(attempt,snapshot):
    raw=snapshot['files'][HERE.relative_to(ROOT).as_posix()+'/runner.py']
    R=types.ModuleType('runner133_media');R.__file__=str(HERE/'runner.py');sys.modules[R.__name__]=R
    exec(compile(raw,R.__file__,'exec'),R.__dict__)
    R.current(snapshot);out=R.attempt_path(attempt)
    result_raw=R.read(out/'native-result.json');result=R.parse(result_raw)
    prepared,job,_=R._payload(snapshot,out)
    R.need(result['unit']==133 and result['runtime_accepted'] is True and result['source_freeze_sha256']==snapshot['freeze_sha256'] and result['review_sha256']==snapshot['review_sha256'] and result['run_id']==prepared['run_id'] and result['job_sha256']==prepared['job_sha256'],'Current successful physics result before media')
    folder=out/'retrieved';pins=result['files_sha256'];values={}
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    R.need(actual==set(pins),'Current actual source inventory before media')
    for name,pin in pins.items():
        data=R.read(folder/R._zip_name(name));R.need(R.digest(data)==pin,'Current sealed media source member')
        values[name]=data
    terminal,process=R.lifecycle(values,job,prepared)
    R.replay_task(snapshot,values)
    capitem=snapshot['cfg']['refs']['capture.py'];cap=R.load('capture133_media',snapshot['files'][capitem['path']],ROOT/capitem['path'])
    motion={}
    for line in values['motion.ndjson'].splitlines():
        row=R.parse(line)
        if row['step']%12==0:motion[row['step']]=row
    frame_names=sorted(n for n in pins if n.startswith('frames/') and n.endswith('.png'))
    R.need(len(frame_names)==931 and len(motion)==931,'Actual93s10fps task captures')
    rows=[]
    for i,name in enumerate(frame_names):
        expected='frames/frame-%04d.png'%i
        R.need(name==expected,'Contiguous actual source RGB')
        meta=R.parse(values[name[:-4]+'.json']);png=values[name]
        R.need(png[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',png[16:24])==(640,480),'Native PNG actual dimensions')
        R.need(meta['png']==name and meta['frame_index']==i and meta['sha256']==pins[name] and meta['pixel_shape']==[480,640,4] and meta['pixel_dtype']=='uint8','Actual RGB frame metadata')
        R.need(meta['state_index']==i*12 and abs(meta['physics_time_s']-i/10)<1e-6,'Native frame physics schedule')
        m=motion[i*12]
        R.need(meta['targets']==m['targets'] and meta['phase']==m['phase'] and meta['native_before']['clock']==m['clock'] and meta['native_before']['object']==m['object'],'Frame actually bound to same current object/robot state')
        cap.validate_generation(meta['freshness']);cap.validate_render_binding(meta['native_before'],meta['native_after'])
        rows.append(m)
    ffmpeg,ffprobe=[shutil.which(n) for n in ('ffmpeg','ffprobe')]
    R.need(ffmpeg and ffprobe,'Already-installed ffmpeg/ffprobe')
    font=Path(os.environ['WINDIR'])/'Fonts/arial.ttf';R.need(font.is_file(),'Installed Arial')
    fontarg=":fontfile='"+font.as_posix().replace(':','\\:')+"'"
    filters=["drawtext=text='V4 - physical pick and place - SIMULATION':x=8:y=8:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.65"+fontarg]
    start=0
    while start<len(rows):
        phase=rows[start]['manipulation']['phase'];end=start+1
        while end<len(rows) and rows[end]['manipulation']['phase']==phase:end+=1
        # Phase labels describe actual sealed frames. No fabricated object poses or animation.
        label=phase.replace('_',' ').upper()
        filters.append(("drawtext=text='%s':x=8:y=h-30:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.65:enable='gte(t,%.6f)*lt(t,%.6f)'"%(label,start/10,end/10))+fontarg)
        start=end
    delivery=out/'delivery';movie=delivery/'robot-arm-v4-pick-place-133.mp4'
    R.need(not movie.exists(),'Preserve existing video');R.safe(delivery,R.OUT).mkdir(parents=True,exist_ok=True)
    R.current(snapshot);R.need(R.read(out/'native-result.json')==result_raw,'Same accepted result before encode')
    encoder_input=invoke_png([ffmpeg,'-hide_banner','-v','error','-n','-f','image2pipe','-vcodec','png','-framerate','10','-i','pipe:0',
            '-frames:v','931','-vf',','.join(filters),'-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','-an','-map_metadata','-1',str(movie)],
            tuple(values[name] for name in frame_names))
    probe=R.parse(invoke([ffprobe,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=codec_name,width,height,r_frame_rate,nb_read_frames:format=duration,size','-of','json',str(movie)],timeout=30))
    R.need(len(probe['streams'])==1,'One video stream');v=probe['streams'][0]
    R.need(v['codec_name']=='h264' and [v['width'],v['height']]==[640,480] and v['r_frame_rate']=='10/1' and int(v['nb_read_frames'])==931 and abs(float(probe['format']['duration'])-93.1)<.02,'Decoded MP4 dimensions/fps/count/duration')
    invoke([ffmpeg,'-hide_banner','-v','error','-i',str(movie),'-f','null','-'])
    samples=[0,465,620,690,800,930]
    for index in samples:
        invoke([ffmpeg,'-hide_banner','-v','error','-n','-i',str(movie),'-vf','select=eq(n\\,%d)'%index,'-frames:v','1',str(delivery/('preview-%04d.png'%index))],timeout=30)
    R.current(snapshot);R.need(R.read(out/'native-result.json')==result_raw,'Same accepted result before delivery manifest')
    value={'unit':133,'attempt':attempt,'run_id':prepared['run_id'],'job_sha256':prepared['job_sha256'],'runtime_accepted':True,
           'source_freeze_sha256':snapshot['freeze_sha256'],'review_sha256':snapshot['review_sha256'],'native_result_sha256':R.digest(result_raw),
           'movie':str(movie),'movie_sha256':R.digest(R.read(movie)),'bytes':movie.stat().st_size,'frames':931,'duration_s':93.1,'ffprobe':probe,
           'sample_indices':samples,'visual_inspection':'PENDING_ROOT','source_capture':'ACTUAL_NEW_RTX_FREE_OBJECT_PHYSICS','hardware_approved':False,
           'encoder_input':encoder_input,
           'upload_allowlist':[movie.name],'limitations':['Simulation-defined home; no hardware safety certification.','Estimated materials; self-collision off and physical gears unverified.']}
    R.exclusive(delivery/'media-manifest.json',R.encode(value));return value
