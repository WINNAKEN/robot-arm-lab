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
import ast
import uuid
from pathlib import Path

EXPECTED=frozenset({'variable_duration_positive','duration_steps_mismatch','stride_fps_mismatch','count_mismatch',
 'phase_gravity_off','velocity_limit','joint_limit','mimic_opening_relation','nonfinite_workspace_point',
 'cloud_count_binding','forbidden_cloud_physics','material_opacity_range','camera_outside_envelope',
 'camera_covers_envelope','missing_node_api','stale_rgb_count','stale_ref_count','stale_dispatch_count',
 'unfinished_scheduled_rational','mismatched_rp_time','renderer_failure_log','blank_pixel',
 'physicsclock_advanced','valid_fresh_capture','purpose_hash_policy','actual_tcp_mapping',
 'semantic_node_type_stable','reference_clock_floor_encoding','reference_clock_one_tick_stale'})
EXPECTED=EXPECTED|frozenset({'profile_present','missing_profile','profile_extra_key','profile_name_wrong',
 'profile_phase_wrong','profile_bool_numerator','profile_bool_denominator','profile_wrong_ratio',
 'profile_nonfinite','profile_smoke_preserved','reference_scope_full5041','consumer_reference_full5041',
 'workspace_reference_prefix4081','reference_derivative_finite_difference','analytic_profile_peak',
 'c2_endpoint_derivatives','source42_derives_sampler52','coherent_old_workspace_rejected',
 'writer_exclusive','writer_old_output_rejected','physical_ast_projection_preserved',
 'profile_missing_active_phase','original34_failure_preserved'})
EXPECTED_COUNT=52


def module(name):
    root=Path(__file__).resolve().parents[3]
    paths={'capture':root/'src/simulation/clock_ready_resume_108/capture.py',
           'legacy_scene':root/'src/simulation/clock_ready_resume_108/scene.py',
           'oracle':root/'src/simulation/latest_scene/validate.py'}
    path=paths[name] if name in paths else Path(__file__).parent/(name+'.py')
    spec=importlib.util.spec_from_file_location('_host116_'+name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[spec.name]=value;spec.loader.exec_module(value);return value


def run_tests(api=None,source=None):
    scene,capture,validator=module('scene'),module('capture'),module('validate')
    root=Path(__file__).resolve().parents[3]
    program=json.loads((Path(__file__).parent/'program.json').read_text(encoding='utf-8'))
    workspace=json.loads((root/'outputs/blended-reference-trial-116/workspace.json').read_text(encoding='utf-8'))
    evidence=root/'outputs/blended-reference-trial-116/E-implementation'/('host-'+uuid.uuid4().hex)
    evidence.mkdir(exist_ok=False)
    model=validator.pmodel(root/'models/robot-arm-urdf-v3/robot_arm.urdf');results={}
    def checked(name,value):
        if value is not True:raise AssertionError(name)
        results[name]=True
    def rejected(name,call):
        try:call()
        except (RuntimeError,ValueError,KeyError,TypeError,FileExistsError):results[name]=True
        else:raise AssertionError(name+' malformed input accepted')
    full=scene.program_for_purpose(program,'motion');smoke=scene.program_for_purpose(program,'render_smoke')
    analysis=scene.validate_program(full,model);short=scene.validate_program(smoke,model)
    checked('variable_duration_positive',len(analysis['capture_steps'])==421 and analysis['capture_steps'][-1]==5040
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
    generator,legacy,oracle=module('workspace'),module('legacy_scene'),module('oracle')
    profile={'name':'reach_high_right_half_quintic_septic_v1','phase':'reach_high_right',
             'blend_numerator':1,'blend_denominator':2}
    checked('profile_present',full['reference_profile']==profile and workspace['program']['reference_profile']==profile)
    for case,key,value in [('profile_name_wrong','name','unsupported'),('profile_phase_wrong','phase','raise'),
                           ('profile_bool_numerator','blend_numerator',True),('profile_bool_denominator','blend_denominator',True),
                           ('profile_wrong_ratio','blend_numerator',2),('profile_nonfinite','blend_denominator',float('inf'))]:
        bad=copy.deepcopy(full);bad['reference_profile'][key]=value
        rejected(case,lambda:scene.validate_program(bad,model))
    bad=copy.deepcopy(full);del bad['reference_profile'];rejected('missing_profile',lambda:scene.target_at(bad,30))
    bad=copy.deepcopy(full);bad['reference_profile']['extra']='ignored'
    rejected('profile_extra_key',lambda:scene.target_at(bad,30))
    bad=copy.deepcopy(full);bad['segments'][7]['name']='unknown_reference_phase'
    rejected('profile_missing_active_phase',lambda:scene.validate_program(bad,model))
    checked('profile_smoke_preserved',smoke['reference_profile']==profile and
            all(scene.target_at(smoke,i/120)==legacy.target_at(smoke,i/120) for i in range(241)))
    # Bernstein sums are independent of the producer's Horner polynomial.
    before=full['segments'][6]['arm'];after=full['segments'][7]['arm']
    outside=True;inside=True;consumer_equal=True;workspace_equal=True
    for i in range(5041):
        t=i/120;actual=scene.target_at(full,t)
        if t<=25 or t>=33:outside=outside and actual==legacy.target_at(full,t)
        else:
            u=(t-25)/8
            b5=sum(math.comb(5,k)*u**k*(1-u)**(5-k) for k in range(3,6))
            b7=sum(math.comb(7,k)*u**k*(1-u)**(7-k) for k in range(4,8))
            weight=(b5+b7)/2;rate=(15+70*u*(1-u))*(u*(1-u))**2/8
            inside=inside and all(abs(actual['targets'][n]-(before[n]+(after[n]-before[n])*weight))<1e-12
                                 and abs(actual['reference_velocity'][n]-(after[n]-before[n])*rate)<1e-12 for n in before)
        expected_q,expected_phase=validator.target(t,full)
        expected_v,expected_encoded=validator.reference_velocity(t,full)
        consumer_equal=consumer_equal and expected_phase==actual['phase'] and all(
            abs(expected_q[n]-actual['targets'][n])<1e-12 and abs(expected_v[n]-actual['reference_velocity'][n])<1e-12
            and expected_encoded[n]==actual['velocity_targets'][n] for n in model['movable'])
        if i<=4080:
            q,index,phase=generator.target_at(workspace['program'],t)
            workspace_equal=workspace_equal and phase==actual['phase'] and all(abs(q[n]-actual['targets'][n])<1e-12 for n in q)
    checked('reference_scope_full5041',outside and inside)
    checked('consumer_reference_full5041',consumer_equal)
    checked('workspace_reference_prefix4081',workspace_equal)
    h=1e-4
    derivative=True
    for t in [25.1,27.,29.,31.,32.9]:
        left=scene.target_at(full,t-h);right=scene.target_at(full,t+h);middle=scene.target_at(full,t)
        derivative=derivative and all(abs((right['targets'][n]-left['targets'][n])/(2*h)-middle['reference_velocity'][n])<2e-9 for n in before)
    checked('reference_derivative_finite_difference',derivative)
    delta=abs(after['J6']-before['J6']);z=(4+math.sqrt(86))/70;acc=30*z*math.sqrt(1-4*z)*(1+7*z)
    checked('analytic_profile_peak',abs(analysis['peak_velocity_by_name']['J6']-delta*(65/32)/8)<1e-14
            and abs(workspace['stats']['peak_velocity']['J6']-delta*(65/32)/8)<1e-14
            and abs(workspace['stats']['peak_acceleration']['J6']-delta*acc/64)<1e-14
            and scene.target_at(full,29)['velocity_targets']['J6']==struct.unpack('<f',struct.pack('<f',(after['J6']-before['J6'])*(65/32)/8))[0])
    ends=[scene.target_at(full,t) for t in [25,33]]
    nearends=[scene.target_at(full,t) for t in [25+h,33-h]]
    normalized_jerk=2*nearends[0]['reference_velocity']['J6']*8**3/((after['J6']-before['J6'])*h*h)
    checked('c2_endpoint_derivatives',all(v==0 for row in ends for v in row['reference_velocity'].values())
            and max(abs(v)/h for row in nearends for v in row['reference_velocity'].values())<1e-4
            and abs(normalized_jerk-30)<.002)
    derived=copy.deepcopy(workspace['program']);prefix=derived['segments'][:9];hold=copy.deepcopy(prefix[-1]);hold.update(name='reach_high_right_observe',duration_s=8)
    derived.update(segments=prefix+[hold],duration_s=42,steps=5040,capture_count=421)
    checked('source42_derives_sampler52',derived==full and workspace['program']==generator.make_program())
    olddata=json.loads((root/'outputs/isaac-workspace-v1/data/workspace.json').read_text(encoding='utf8'))
    olddata['generator_sha256']=generator.sha(generator.__file__);olddata['program']=generator.make_program()
    rejected('coherent_old_workspace_rejected',lambda:generator.validate_result(olddata,oracle.pmodel(root/'models/robot-arm-urdf-v3/robot_arm.urdf'),oracle,full=False))
    writer=evidence/'exclusive-writer.json';generator.write_json(writer,{'HOST_ONLY':True})
    rejected('writer_exclusive',lambda:generator.write_json(writer,{'HOST_ONLY':False}))
    rejected('writer_old_output_rejected',lambda:generator.write_json(root/'outputs/isaac-workspace-v1/forbidden116.json',{}))
    tree=ast.parse((Path(__file__).parent/'scene.py').read_bytes())
    tree.body=[n for n in tree.body if not(isinstance(n,ast.FunctionDef) and n.name in {'target_at','validate_program'})]
    checked('physical_ast_projection_preserved',hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()=='5babee70c8f3c8a85026ee51e86b52b12e04943fc6788206f901bfd59ab61f9f')
    row={'time_s':34,'step':4080,'targets':scene.target_at(full,34)['targets'],'q':scene.target_at(full,34)['targets'].copy(),'qd':{n:0.0 for n in model['movable']}}
    row['q']['J3']+=.01020520704727318;row['q']['J5']+=.009081552646485525
    check=scene.checkpoint(full,row);checked('original34_failure_preserved',not check['passed'] and check['failed_joints']==['J3','J5'])
    if set(results)!=EXPECTED or len(EXPECTED)!=EXPECTED_COUNT or not all(results.values()):raise AssertionError('Fixed HOST52 census')
    report={'status':'HOST_WORKSPACE_SCENE_PASS','count':EXPECTED_COUNT,'tests':results,
            'png_roundtrip':'ACTUAL_RGBA_BYTES_EQUAL','native':'NOT_RUN','camera':camera,
            'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('scene.py','program.json','workspace.py')},
            'immutable_capture_sha256':hashlib.sha256((root/'src/simulation/clock_ready_resume_108/capture.py').read_bytes()).hexdigest(),
            'source_program_s':42,'sampler_program_s':52,'shared_prefix_observations':4081,'full_observations':5041}
    target=evidence/'scene-host.json'
    with target.open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({'status':report['status'],'count':EXPECTED_COUNT,'evidence':str(target)}));return 0


if __name__=='__main__':raise SystemExit(run_tests())
