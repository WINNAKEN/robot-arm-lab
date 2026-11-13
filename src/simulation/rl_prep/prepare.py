"""Write-once offline preparation. No training, SDK, networking or motor dispatch."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
import uuid
try:
    from . import profile
    from .isaaclab_adapter import specification
    from .policy_io import untrained_contract,reference_request
    from .trajectory import segment
    from .task import JointReachTask,MockBackend
except ImportError:
    import profile
    from isaaclab_adapter import specification
    from policy_io import untrained_contract,reference_request
    from trajectory import segment
    from task import JointReachTask,MockBackend


SOURCE_DIR='src/simulation/rl_prep'
OUTPUT_DIR='outputs/rl-prep-v1'
SOURCE_NAMES=('profile.py','trajectory.py','task.py','isaaclab_adapter.py','policy_io.py','prepare.py','task_config.json','test_prep.py','README.md')


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def sources(root):
    names=[SOURCE_DIR+'/'+name for name in SOURCE_NAMES]+['docs/design/044-rl-smooth-motion-preparation.md']
    return {name:profile.sha(Path(root)/name) for name in names}


def reference_program(p):
    """Reference data only, not an observed trajectory or policy rollout."""
    a=[5,-5,5,3,-3,3];waypoints=[a,[-x for x in a],[0]*6];q=[0.]*6;rows=[];offset=0.
    for degrees in waypoints:
        goal=[math.radians(x) for x in degrees]
        part=segment(q,goal,p['config']['limits'])
        rows.extend([{**r,'t_s':offset+r['t_s']} for r in (part if not rows else part[1:])])
        offset=rows[-1]['t_s'];q=goal
    return {'status':'REFERENCE_ONLY_NOT_EXECUTED','profile_hash':p['profile_hash'],'coordinate':p['coordinate'],
        'joint_names':p['joint_names'],'waypoints_deg':waypoints,'physics_hz':120,'samples':rows,
        'hardware_approved':False,'physical_calibration':False}


def smoke(p,root):
    episodes=[]
    for seed in (7,19,41):
        task=JointReachTask(p,MockBackend(),root);obs,info=task.reset(seed=seed,randomize=False)
        rewards=[]
        for decision in range(16):
            increment=math.radians(p['config']['limits']['increment_deg'])
            action=[max(-1.,min(1.,(g-q)/increment)) for g,q in zip(task.goal,task.command)]
            obs,reward,terminated,truncated,info=task.step(action);rewards.append(reward)
            if terminated or truncated:break
        profile.require(info['success'] and not info['faults'],'Host mock interface failed')
        episodes.append({'seed':seed,'decisions':decision+1,'observation_dim':len(obs),'success':info['success'],
                         'scope':info['scope'],'total_reward':sum(rewards),'goal_rad':task.goal})
    return {'status':'HOST_KINEMATIC_CONTRACT_TEST_PASS','episodes':episodes,'learning':'NOT_RUN',
            'native_physics':'NOT_RUN','policy':'ANALYTICAL_GOAL_INCREMENT_RULE_NOT_LEARNED','hardware_approved':False}


def expected_artifacts(p,root):
    return {'profile.json':p,'environment-contract.json':specification(p,root),
        'ppo-candidate.json':p['config']['ppo_candidate'],'policy-untrained.json':untrained_contract(p,root),
        'reference-program.json':reference_program(p),'simulation-request.json':reference_request(p,[0.]*6,[1,-1,1,.5,-.5,.5],root),
        'host-smoke.json':smoke(p,root),'training-readiness.json':profile.readiness(p,root),
        'baseline-replay.json':{'scope':'PINNED_043_RESULT_GATE_REPLAY_NO_NEW_PHYSICS',**p['baseline']}}


def program_csv(program):
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    writer.writerow(['t_s']+[f'{field}_{joint}' for field in ('q_rad','qd_rad_s','qdd_rad_s2','jerk_rad_s3') for joint in profile.JOINTS])
    for row in program['samples']:writer.writerow([row['t_s']]+[x for key in ('q','qd','qdd','jerk') for x in row[key]])
    return stream.getvalue().encode('utf-8')


def verify_run(run,root=profile.ROOT):
    run=Path(run);root=Path(root);m=profile.read(run/'manifest.json')
    profile.require(run.name==m['run_id'] and m['status']=='READY_PREPARATION_ONLY','Run identity/status')
    profile.require(m['source_sha256']==sources(root),'Prepared executable source changed')
    p=profile.read(run/'profile.json');profile.validate(p,root)
    profile.require(m['profile_hash']==p['profile_hash'],'Run profile binding')
    for name,h in m['artifact_sha256'].items():
        relative=Path(name);target=(run/relative).resolve()
        profile.require(not relative.is_absolute() and target.is_relative_to(run.resolve()) and profile.sha(target)==h,'Run artifact changed: '+name)
    expected={'profile.json','environment-contract.json','ppo-candidate.json','policy-untrained.json','reference-program.json',
              'reference-program.csv','simulation-request.json','host-smoke.json','training-readiness.json','baseline-replay.json'}
    profile.require(set(m['artifact_sha256'])==expected,'Complete artifact inventory')
    derived=expected_artifacts(p,root)
    for name,value in derived.items():profile.require(profile.read(run/name)==value,'Derived artifact semantics changed: '+name)
    profile.require((run/'reference-program.csv').read_bytes()==program_csv(derived['reference-program.json']),'Derived CSV changed')
    return {'status':'PREPARATION_ARTIFACTS_VERIFIED','run_id':m['run_id'],'training':'NOT_RUN','hardware_approved':False}


def build(root=profile.ROOT):
    root=Path(root);out=root/OUTPUT_DIR;run_id=uuid.uuid4().hex;run=out/'runs'/run_id
    run.mkdir(parents=True,exist_ok=False)
    write(out/'current.json',{'status':'BUILDING','run_id':run_id,'training':'NOT_RUN','hardware_approved':False})
    try:
        before=sources(root);p=profile.build(root);artifacts=expected_artifacts(p,root)
        for name,value in artifacts.items():write(run/name,value)
        (run/'reference-program.csv').write_bytes(program_csv(artifacts['reference-program.json']))
        profile.require(before==sources(root),'Executable changed during preparation')
        profile.validate(p,root)
        names=set(artifacts)|{'reference-program.csv'}
        write(run/'manifest.json',{'status':'READY_PREPARATION_ONLY','run_id':run_id,'profile_hash':p['profile_hash'],
            'source_sha256':before,'artifact_sha256':{name:profile.sha(run/name) for name in sorted(names)},
            'training':'NOT_RUN','hardware_approved':False})
        verify_run(run,root)
        write(out/'current.json',{'status':'READY_PREPARATION_ONLY','run_id':run_id,'manifest_sha256':profile.sha(run/'manifest.json'),
            'training_readiness':'BLOCKED','training':'NOT_RUN','hardware_approved':False})
        return run
    except Exception as error:
        failure={'status':'FAILED','run_id':run_id,'error':type(error).__name__+': '+str(error),'training':'NOT_RUN','hardware_approved':False}
        write(run/'failure.json',failure);write(out/'current.json',failure)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('build','smoke','check-training','verify'))
    args=parser.parse_args()
    if args.command=='build':result={'run_dir':str(build()),'status':'READY_PREPARATION_ONLY'}
    elif args.command=='smoke':result=smoke(profile.build(),profile.ROOT)
    elif args.command=='check-training':result=profile.readiness(profile.build())
    else:
        current=profile.read(profile.ROOT/OUTPUT_DIR/'current.json')
        profile.require(current['status']=='READY_PREPARATION_ONLY','Current build not ready')
        run=profile.ROOT/OUTPUT_DIR/'runs'/current['run_id']
        profile.require(profile.sha(run/'manifest.json')==current['manifest_sha256'],'Current manifest changed')
        result=verify_run(run)
    print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
    return 2 if args.command=='check-training' and result['status']=='BLOCKED' else 0


if __name__=='__main__':raise SystemExit(main())
