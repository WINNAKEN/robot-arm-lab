"""SDK-free 069B controls; the exact inventory is enforced independently of outcomes."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys

EXPECTED = frozenset({
    'quintic_endpoints', 'quintic_monotone', 'program_inventory', 'program_2641_samples',
    'program_boundary_continuity', 'program_targets_fixed', 'program_bool_rejected', 'original_velocity_limits', 'position_limit_rejected',
    'velocity_limit_rejected', 'nine_name_permutation', 'duplicate_name_rejected',
    'missing_name_rejected', 'gravity_layout9', 'gravity_layout15_permuted',
    'gravity_bad_layout_rejected', 'gravity_reference_all9', 'ff_original_caps',
    'ff_overload_dynamic_failure', 'checkpoint_pass', 'checkpoint_position_failure',
    'checkpoint_velocity_failure', 'fresh_generation_pass', 'stale_rgb_rejected',
    'stale_reference_rejected', 'stale_dispatcher_rejected', 'old_reference_rejected',
    'unfinished_schedule_rejected', 'node_identity_rejected', 'rational_bool_rejected',
    'valid_shape_stale_rgb_rejected', 'renderer_failed_log_rejected', 'scheduling_failed_log_rejected',
    'blank_pixels_rejected', 'wrong_pixel_shape_rejected', 'valid_pixels',
})


def module(name):
    path = Path(__file__).parent/(name+'.py')
    spec = importlib.util.spec_from_file_location('_host069b_'+name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def run_tests(api=None, source=None):
    scene, capture, validator = module('scene'), module('capture'), module('validate')
    program = json.loads((Path(__file__).parent/'program.json').read_text(encoding='utf-8'))
    model_path = Path(__file__).resolve().parents[3]/'models/robot-arm-urdf-v3/robot_arm.urdf'
    model = validator.pmodel(model_path)
    outcomes = {}
    def checked(name, condition):
        if not condition:
            raise AssertionError(name)
        outcomes[name] = True
    def rejected(name, action):
        try:
            action()
        except (RuntimeError, ValueError, KeyError, TypeError):
            outcomes[name] = True
        else:
            raise AssertionError(name+': malformed input accepted')
    checked('quintic_endpoints', scene.quintic(0) == 0 and scene.quintic(1) == 1)
    sequence = [scene.quintic(i/1000) for i in range(1001)]
    checked('quintic_monotone', all(a <= b for a, b in zip(sequence, sequence[1:])))
    analysis = scene.validate_program(program, model)
    checked('program_inventory', len(analysis['capture_steps']) == 331 and analysis['capture_steps'][-1] == 2640)
    samples = [scene.target_at(program, i/120) for i in range(2641)]
    checked('program_2641_samples', len(samples) == 2641 and all(set(s['targets']) == set(model['movable']) for s in samples))
    checked('program_boundary_continuity', all(max(abs(scene.target_at(program,t-1e-7)['targets'][n]-scene.target_at(program,t+1e-7)['targets'][n]) for n in model['movable']) < 1e-9 for t in (1,4,9,12,15,18,19)))
    checked('program_targets_fixed', samples[480]['targets']['KG1_slide_A'] == .02 and abs(samples[1080]['targets']['KG1_pinion']-1.4814814814814814) < 1e-14 and abs(samples[1800]['targets']['J1']-math.radians(3)) < 1e-14 and samples[2160]['targets']['J1'] == 0)
    bad_program = copy.deepcopy(program);bad_program['segments'][-1]['gravity'] = 1
    rejected('program_bool_rejected',lambda:scene.validate_program(bad_program,model))
    checked('original_velocity_limits', all(analysis['peak_velocity_by_name'][n] <= model['joints'][n]['velocity'] for n in model['movable']))
    altered = copy.deepcopy(model);altered['joints']['KG1_slide_A']['upper'] = .001
    rejected('position_limit_rejected', lambda: scene.validate_program(program, altered))
    altered = copy.deepcopy(model);altered['joints']['KG1_slide_A']['velocity'] = .001
    rejected('velocity_limit_rejected', lambda: scene.validate_program(program, altered))
    names = list(reversed(model['movable']))
    values = list(range(9))
    expected = {n: float(values[names.index(n)]) for n in model['movable']}
    checked('nine_name_permutation', scene.named_columns(names, model['movable'], values) == expected)
    rejected('duplicate_name_rejected', lambda: scene.named_columns([names[0]]*9, model['movable'], values))
    rejected('missing_name_rejected', lambda: scene.named_columns(names[:-1], model['movable'], values[:-1]))
    mapped, columns = scene.map_gravity(names, model['movable'], values)
    checked('gravity_layout9', mapped == expected and columns == {n:names.index(n) for n in names})
    mapped, columns = scene.map_gravity(names, model['movable'], [-100.]*6+values)
    checked('gravity_layout15_permuted', mapped == expected and columns == {n:6+names.index(n) for n in names})
    rejected('gravity_bad_layout_rejected', lambda: scene.map_gravity(names, model['movable'], values+[0.]))
    gravity_errors = []
    masses = [{'name': n, 'mass': b['mass'], 'com': b['com']} for n,b in model['links'].items() if b['mass'] is not None]
    for step in (0,100,480,900,1440,1700,1800,1950,2300,2640):
        q = samples[step]['targets'];poses = validator.fk(model,q)
        actual = [{'name':n,'position':p,'orientation_wxyz':rotation_quaternion(r)} for n,(p,r) in poses.items() if model['links'][n]['mass'] is not None]
        producer = scene.gravity_reference(model, actual, masses)
        independent = validator.gravity(model, actual, masses)
        gravity_errors.append(max(abs(producer[n]-independent[n]) for n in model['movable']))
    checked('gravity_reference_all9', max(gravity_errors) < 1e-10)
    ff = {n: model['joints'][n]['effort']/3 for n in model['movable']}
    remaining, overloaded = scene.remaining_caps(model, ff)
    checked('ff_original_caps', not overloaded and all(abs(remaining[n]+abs(ff[n])-model['joints'][n]['effort']) < 1e-12 for n in ff))
    ff['J1'] = model['joints']['J1']['effort']+.1
    remaining, overloaded = scene.remaining_caps(model, ff)
    checked('ff_overload_dynamic_failure', overloaded == ['J1'] and remaining['J1'] < 0)
    target = samples[120]['targets']
    row = {'time_s':1.,'step':120,'targets':target,'q':target.copy(),'qd':{n:0. for n in target}}
    checked('checkpoint_pass', scene.checkpoint(program,row)['passed'])
    altered = copy.deepcopy(row);altered['q']['KG1_slide_B'] += .001
    checked('checkpoint_position_failure', not scene.checkpoint(program,altered)['passed'])
    altered = copy.deepcopy(row);altered['qd']['J6'] += math.radians(2)
    checked('checkpoint_velocity_failure', not scene.checkpoint(program,altered)['passed'])
    metrics = {'before':{},'after':{},'scheduled':[1,3],'dispatcher_reference':[2,3],
               'render_product_reference':[2,3],'render_product':'/Render/Products/069'}
    for i,n in enumerate(('rgb','reference','dispatcher')):
        metrics['before'][n] = {'path':'/Render/'+n,'id':i+1,'type':'native.'+n,'compute_count':4}
        metrics['after'][n] = {**metrics['before'][n], 'compute_count':5}
    checked('fresh_generation_pass', capture.validate_generation(metrics))
    for n in ('rgb','reference','dispatcher'):
        altered = copy.deepcopy(metrics);altered['after'][n]['compute_count'] = 4
        rejected('stale_'+n+'_rejected', lambda m=altered: capture.validate_generation(m))
    altered = copy.deepcopy(metrics);altered['render_product_reference'] = [1,3]
    rejected('old_reference_rejected', lambda: capture.validate_generation(altered))
    altered = copy.deepcopy(metrics);altered['scheduled'] = [1,1]
    rejected('unfinished_schedule_rejected', lambda: capture.validate_generation(altered))
    altered = copy.deepcopy(metrics);altered['after']['rgb']['id'] = 99
    rejected('node_identity_rejected', lambda: capture.validate_generation(altered))
    altered = copy.deepcopy(metrics);altered['scheduled'] = [True,1]
    rejected('rational_bool_rejected', lambda: capture.validate_generation(altered))
    altered = copy.deepcopy(metrics);altered['pixel_shape'] = [480,640,4];altered['pixel_dtype'] = 'uint8';altered['after']['rgb']['compute_count'] = 4
    rejected('valid_shape_stale_rgb_rejected', lambda: capture.validate_generation(altered))
    altered = copy.deepcopy(metrics);altered['renderer_log'] = 'renderer failed to advance to the scheduled frame'
    rejected('renderer_failed_log_rejected', lambda: capture.validate_generation(altered))
    altered = copy.deepcopy(metrics);altered['renderer_log'] = 'Orchestrator failed to schedule a capture'
    rejected('scheduling_failed_log_rejected', lambda: capture.validate_generation(altered))
    # Pixel objects exercise the shape/blank gate without needing an SDK or a renderer.
    class Pixels:
        dtype = 'uint8';shape = (480,640,4)
        def __getitem__(self,key):return self
        def max(self):return 200
        def min(self):return 10
        def std(self):return 30.
    pixels = Pixels();capture.validate_pixels(pixels);checked('valid_pixels',True)
    pixels.std = lambda:0.
    rejected('blank_pixels_rejected',lambda:capture.validate_pixels(pixels))
    pixels = Pixels();pixels.shape = (480,640,3)
    rejected('wrong_pixel_shape_rejected',lambda:capture.validate_pixels(pixels))
    checked_inventory = set(outcomes)
    if checked_inventory != EXPECTED or not all(outcomes.values()):
        raise AssertionError('Fixed scene control inventory mismatch: '+repr(checked_inventory ^ EXPECTED))
    result = {'schema_version':1,'status':'HOST_PASS','expected_count':len(EXPECTED),
              'passed_count':len(outcomes),'outcomes':outcomes,'maximum_gravity_math_difference':max(gravity_errors),
              'scope':'SDK-free host controls; native physics and RTX NOT_RUN'}
    if api is not None:
        api.write(Path(__file__).resolve().parents[3]/'outputs/isaac-gripper-v1/evidence/capture-host-tests.json',result)
    print(json.dumps(result,allow_nan=False))
    return 0


def rotation_quaternion(r):
    # Independent host fixture conversion; producer uses quaternion -> rotation only.
    trace = r[0][0]+r[1][1]+r[2][2]
    if trace > 0:
        s = math.sqrt(trace+1)*2
        return [s/4,(r[2][1]-r[1][2])/s,(r[0][2]-r[2][0])/s,(r[1][0]-r[0][1])/s]
    i = max(range(3),key=lambda j:r[j][j]);j=(i+1)%3;k=(i+2)%3
    s = math.sqrt(1+r[i][i]-r[j][j]-r[k][k])*2
    q = [0.]*4;q[0]=(r[k][j]-r[j][k])/s;q[i+1]=s/4;q[j+1]=(r[j][i]+r[i][j])/s;q[k+1]=(r[k][i]+r[i][k])/s
    return q


if __name__ == '__main__':
    raise SystemExit(run_tests(module('driver')))
