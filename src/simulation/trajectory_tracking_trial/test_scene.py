"""073 fixed HOST controls; no SDK or renderer is initialized."""
import copy
import hashlib
import importlib.util
import json
import struct
import sys
import types
import math
import zlib
from pathlib import Path

EXPECTED=frozenset({'variable_duration_positive','duration_steps_mismatch','stride_fps_mismatch','count_mismatch',
 'phase_gravity_off','velocity_limit','joint_limit','mimic_opening_relation','nonfinite_workspace_point',
 'cloud_count_binding','forbidden_cloud_physics','material_opacity_range','camera_outside_envelope',
 'camera_covers_envelope','missing_node_api','stale_rgb_count','stale_ref_count','stale_dispatch_count',
 'unfinished_scheduled_rational','mismatched_rp_time','renderer_failure_log','blank_pixel',
 'physicsclock_advanced','valid_fresh_capture','purpose_hash_policy','actual_tcp_mapping',
 'semantic_node_type_stable','reference_clock_floor_encoding','reference_clock_one_tick_stale'})
EXPECTED_COUNT=29


def module(name):
    path=Path(__file__).parent/(name+'.py');spec=importlib.util.spec_from_file_location('_host073_'+name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[spec.name]=value;spec.loader.exec_module(value);return value


def run_tests(api=None,source=None):
    scene,capture,validator=module('scene'),module('capture'),module('validate')
    root=Path(__file__).resolve().parents[3]
    program=json.loads((Path(__file__).parent/'program.json').read_text(encoding='utf-8'))
    workspace=json.loads((root/'outputs/isaac-workspace-v1/data/workspace.json').read_text(encoding='utf-8'))
    model=validator.pmodel(root/'models/robot-arm-urdf-v3/robot_arm.urdf');results={}
    def checked(name,value):
        if value is not True:raise AssertionError(name)
        results[name]=True
    def rejected(name,call):
        try:call()
        except (RuntimeError,ValueError,KeyError,TypeError):results[name]=True
        else:raise AssertionError(name+' malformed input accepted')
    full=scene.program_for_purpose(program,'motion');smoke=scene.program_for_purpose(program,'render_smoke')
    analysis=scene.validate_program(full,model);short=scene.validate_program(smoke,model)
    checked('variable_duration_positive',len(analysis['capture_steps'])==521 and analysis['capture_steps'][-1]==6240
            and len(short['capture_steps'])==21 and short['capture_steps'][-1]==240 and all(p['gravity'] is True for p in full['segments']))
    bad=copy.deepcopy(full);bad['steps']-=1;rejected('duration_steps_mismatch',lambda:scene.validate_program(bad,model))
    bad=copy.deepcopy(full);bad['fps']=15;rejected('stride_fps_mismatch',lambda:scene.validate_program(bad,model))
    bad=copy.deepcopy(full);bad['capture_count']-=1;rejected('count_mismatch',lambda:scene.validate_program(bad,model))
    bad=copy.deepcopy(full);bad['segments'][1]['gravity']=False;rejected('phase_gravity_off',lambda:scene.validate_program(bad,model))
    badmodel=copy.deepcopy(model);badmodel['joints']['J2']['velocity']=1e-6;rejected('velocity_limit',lambda:scene.validate_program(full,badmodel))
    badmodel=copy.deepcopy(model);badmodel['joints']['J2']['upper']=-100.;rejected('joint_limit',lambda:scene.validate_program(full,badmodel))
    bad=copy.deepcopy(full);bad['initial_opening_m']=.05;rejected('mimic_opening_relation',lambda:scene.validate_program(bad,model))
    cloud={'cloud':copy.deepcopy(workspace['cloud'])}
    bad=copy.deepcopy(cloud);bad['cloud']['voxels'][bad['cloud']['render_indices'][0]]['position'][0]=float('nan')
    rejected('nonfinite_workspace_point',lambda:scene.cloud_points(bad))
    bad=copy.deepcopy(cloud);bad['cloud']['render_indices']=list(range(1601));rejected('cloud_count_binding',lambda:scene.cloud_points(bad))
    bad=copy.deepcopy(cloud);bad['cloud']['collision']=True;rejected('forbidden_cloud_physics',lambda:scene.cloud_points(bad))
    bad=copy.deepcopy(cloud);bad['cloud']['opacity']=1.;rejected('material_opacity_range',lambda:scene.cloud_points(bad))
    camera=capture.camera_for_workspace(full,workspace)
    checked('camera_covers_envelope',capture.validate_camera_envelope(camera)<=1/1.15)
    bad=copy.deepcopy(camera);bad['eye']=bad['target'];rejected('camera_outside_envelope',lambda:capture.validate_camera_envelope(bad))
    missing={name:capture.wrapper_metadata(object(),('get_compute_count',)) for name in ('rgb','reference','dispatcher')}
    rejected('missing_node_api',lambda:capture.validate_node_capabilities(missing))
    freshness={'before':{},'after':{},'scheduled':[1,3],'dispatcher_reference':[2,3],
               'render_product_reference':[2,3],'render_product':'/Render/Products/073'}
    freshness.update(source_engine_time_s=float(1/3),scheduled_binary64_hex=float(1/3).hex(),scheduled=capture.encode_scheduled_reference([1,3]),scheduled_source_raw=[1,3],quantization_rule=capture.SCHEDULE_QUANTIZATION)
    for i,name in enumerate(('rgb','reference','dispatcher')):
        freshness['before'][name]={'path':'/Render/'+name,'id':100+i,'id_kind':'PYTHON_WRAPPER','type':'HOST.'+name,'compute_count':4}
        freshness['after'][name]={**freshness['before'][name],'compute_count':5}
    for test,node in (('stale_rgb_count','rgb'),('stale_ref_count','reference'),('stale_dispatch_count','dispatcher')):
        bad=copy.deepcopy(freshness);bad['after'][node]['compute_count']=4;rejected(test,lambda:capture.validate_generation(bad))
    bad=copy.deepcopy(freshness);bad['scheduled']=[3,3];rejected('unfinished_scheduled_rational',lambda:capture.validate_generation(bad))
    bad=copy.deepcopy(freshness);bad['render_product_reference']=[1,3];rejected('mismatched_rp_time',lambda:capture.validate_generation(bad))
    bad=copy.deepcopy(freshness);bad['renderer_log']='Orchestrator failed to schedule a capture';rejected('renderer_failure_log',lambda:capture.validate_generation(bad))
    class Pixels:
        dtype='uint8';shape=(480,640,4)
        def __getitem__(self,key):return self
        def max(self):return 254
        def min(self):return 0
        def std(self):return 60.
        def tobytes(self,order='C'):return bytes(range(256))*(480*640*4//256)
    blank=Pixels();blank.std=lambda:0.;rejected('blank_pixel',lambda:capture.validate_pixels(blank))
    rejected('physicsclock_advanced',lambda:capture.validate_render_binding({'engine_time_s':0.,'lab_step':0},{'engine_time_s':1/120,'lab_step':1}))
    pixels=Pixels();capture.validate_generation(freshness);capture.validate_pixels(pixels)
    encoded,rgba_sha=capture.encode_rgba_png(pixels);pos=8;payload=b'';ihdr=None
    assert encoded[:8]==b'\x89PNG\r\n\x1a\n'
    while pos<len(encoded):
        length=struct.unpack_from('>I',encoded,pos)[0];kind=encoded[pos+4:pos+8];body=encoded[pos+8:pos+8+length]
        assert zlib.crc32(kind+body)&0xffffffff==struct.unpack_from('>I',encoded,pos+8+length)[0]
        if kind==b'IHDR':ihdr=struct.unpack('>IIBBBBB',body)
        if kind==b'IDAT':payload+=body
        pos+=length+12
    decoded=zlib.decompress(payload);stride=640*4+1
    assert all(decoded[i*stride]==0 for i in range(480))
    recovered=b''.join(decoded[i*stride+1:(i+1)*stride] for i in range(480))
    checked('valid_fresh_capture',ihdr==(640,480,8,6,0,0,0) and recovered==pixels.tobytes()
            and hashlib.sha256(recovered).hexdigest()==rgba_sha)
    stationary=capture.NativeCapture.__new__(capture.NativeCapture)
    stationary.hashes={'HOST_IDENTICAL_PIXELS'};stationary.directory=types.SimpleNamespace(glob=lambda pattern:[Path('HOST')]);stationary.warmup={}
    capture.NativeCapture.finish(stationary,1,purpose='render_smoke')
    rejected('purpose_hash_policy',lambda:capture.NativeCapture.finish(stationary,1,purpose='motion'))
    parent=model['joints']['tool0_mount']['parent'];angle=math.pi/4
    tcp=scene.actual_tcp_from_row(model,{'body_poses':[{'name':parent,'position':[1.,2.,3.],
         'orientation_wxyz':[math.cos(angle),math.sin(angle),0.,0.]}],
         'targets':{'ignored':99999}})
    offset=model['joints']['tool0_mount']['origin'][0]
    expected=[1.+offset[0],2.-offset[2],3.+offset[1]]
    checked('actual_tcp_mapping',max(abs(a-b) for a,b in zip(tcp['position'],expected))<1e-12)
    class Node:
        def get_prim_path(self):return '/HOST/Node'
        def get_node_type(self):return object()
        def get_type_name(self):return 'HOST.SemanticType'
        def get_compute_count(self):return 9
    native=capture.NativeCapture.__new__(capture.NativeCapture);native._nodes={name:Node() for name in ('rgb','reference','dispatcher')}
    before=native.nodes();after=native.nodes()
    checked('semantic_node_type_stable',all(before[n]['type']==after[n]['type']=='HOST.SemanticType' for n in before))
    checked('reference_clock_floor_encoding',capture.encode_scheduled_reference([1,30])==[33333333,1000000000])
    bad=copy.deepcopy(freshness);bad.update(source_engine_time_s=float(1/30),scheduled_binary64_hex=float(1/30).hex(),scheduled_source_raw=[1,30],scheduled=[33333333,1000000000],
        dispatcher_reference=[33333332,1000000000],render_product_reference=[33333332,1000000000])
    rejected('reference_clock_one_tick_stale',lambda:capture.validate_generation(bad))
    if set(results)!=EXPECTED or len(EXPECTED)!=EXPECTED_COUNT or not all(results.values()):raise AssertionError('Fixed HOST 29 census')
    report={'status':'HOST_WORKSPACE_SCENE_PASS','count':EXPECTED_COUNT,'tests':results,
            'png_roundtrip':'ACTUAL_RGBA_BYTES_EQUAL','native':'NOT_RUN','camera':camera,
            'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('scene.py','capture.py','program.json')}}
    target=root/'outputs/isaac-trajectory-tracking-v1/scene-host.json'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':report['status'],'count':EXPECTED_COUNT}));return 0


if __name__=='__main__':raise SystemExit(run_tests())
