"""073 closed-payload, process, prerequisite, and reservation HOST controls."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import uuid

EXPECTED=frozenset({'payload_positive','missing_source','extra_inventory','model_resealed','submission_census','canonical_sha',
 'sha_mismatch','workspace_pin','json_duplicate','json_nonfinite','json_overflow','path_traversal','absolute_path','typed_job',
 'typed_process','native_nonzero','process_direct_pid','exit7_reaped','timeout_reaped','common_import','different_common',
 'import_seal','fresh_import','duplicate_import','wrong_experiment_ledger','duplicate_ledger_identity','config_bool_limits',
 'config_timeout_bool','smoke_requires_import','motion_requires_smoke','smoke_proof','smoke_wrong_b','smoke_bad_log',
 'smoke_bad_exit','stage_chain','retry_positive','retry_zero','retry_bool','retry_timeout','retry_unchanged_b',
 'retry_missing_review','retry_author','retry_domain','retry_budget','sdk_lifecycle_pinned','consume_dynamic_fail',
 'consume_render_error','consume_artifact_extra'})
EXPECTED_COUNT=48


def run_tests(api,source):
    results={};observations={};root=api.ROOT;out=root/api.OUT
    def passed(name,value=True):
        api.need(value is True,name);results[name]=True
    def rejected(name,action):
        try:action()
        except (ValueError,RuntimeError,KeyError,TypeError,OSError):results[name]=True
        else:raise AssertionError(name+': malformed HOST evidence accepted')
    encode=lambda value:json.dumps(value,sort_keys=True,allow_nan=False).encode()
    baseline=api.read(root/'outputs/isaac-gripper-v1/071/sdk-source-freeze.json')
    old_sdk=(root/'outputs/isaac-gripper-v1/071/original/sdk.py').read_bytes()
    current_tree=ast.parse(source['sdk.py']);old_tree=ast.parse(old_sdk)
    lifecycle=lambda tree:next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='lifecycle')
    passed('sdk_lifecycle_pinned',api.digest(source['sdk.py'])==baseline['sdk_sha256'] and
           ast.dump(lifecycle(current_tree),include_attributes=False)==ast.dump(lifecycle(old_tree),include_attributes=False))
    observations['lifecycle_prior_evidence']={'sdk_sha256':baseline['sdk_sha256'],
      '071_freeze_sha256':api.sha(root/'outputs/isaac-gripper-v1/071/sdk-source-freeze.json'),
      '070_confirmation_sha256':api.sha(root/'outputs/isaac-gripper-v1/070/host-confirmation.json'),'rerun':'NOT_RUN_IMMUTABLE_SDK'}
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='A-host-',dir=out) as temporary:
        base=Path(temporary).absolute();cfg=api.parse(source['config.json'])
        cfg['refs']={};cfg['model_submission']={'path':'HOST/submission.json','sha256':'a'*64}
        payload={'source/'+name:b'# HOST synthetic source\n' for name in api.SOURCE}
        payload.update({'model/'+name:b'HOST_MODEL_BYTES' for name in api.MODEL})
        payload['source/sdk.py']=b'def verify_records(*a,**k):return {"HOST":True}\n'
        payload['source/validate.py']=(b'def verify_workspace(*a,**k):return ({"HOST":True},{"HOST":True})\n'
           b'def verify_import(*a,**k):return {"HOST":True}\n'
           b'def verify_simulation(model,report,*a,**k):return {"dynamics_pass":report.get("HOST_DYNAMICS",True)}\n')
        submission={'canonical_urdf_sha256':api.digest(payload['model/robot_arm.urdf']),
          'source_and_evidence_files':{cfg['model_dir']+'/'+name:{'sha256':api.digest(payload['model/'+name]),'bytes':len(payload['model/'+name])} for name in api.MODEL}}
        references={'submission.json':encode(submission),'workspace.json':b'{"HOST":true}',
                    'sampling-oracle.py':b'# HOST independent sampling oracle\n'}
        for name,raw in references.items():
            cfg['refs'][name]={'path':'HOST/'+name,'sha256':api.digest(raw)};payload['ref/'+name]=raw
        cfg['model_submission']=dict(cfg['refs']['submission.json']);payload['source/config.json']=encode(cfg)
        import_proof={};smoke_proof={}

        def records(ctx,artifacts,code=0,failed=False):
            common={'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'purpose':ctx.job['purpose']}
            terminal={**common,'pid':9012,'parent_pid':9011,'code':code,'status':'FAILED' if failed else 'CLOSED',
              'phase':'APP_CLOSED','hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN',
              'files_sha256':{n:api.digest(v) for n,v in artifacts.items()}}
            if failed:terminal.update(primary_phase='COLLECTOR',primary_error='AttributeError: HOST missing actual capture API')
            parent={**common,'pid':9011,'child_pid':9012,'actual_child_exit_code':code,'policy_exit_code':code,
                    'timed_out':False,'child_state':'REAPED','started_unix':1.,'finished_unix':2.}
            shell={**common,'python_exit_code':code}
            return {'job.json':(ctx.run/'job.json').read_bytes(),'terminal.json':encode(terminal),'exit.json':encode(parent),
                    'remote-shell.json':encode(shell),**artifacts}

        def fixture(purpose='import',change=None,repair=None):
            data=copy.deepcopy(payload)
            if purpose!='import':data.update({'import-proof/'+n:raw for n,raw in import_proof.items()})
            if purpose=='motion':data.update({'smoke-proof/'+n:raw for n,raw in smoke_proof.items()})
            if change:change(data)
            if repair is not None:
                data['source/capture.py']=b'# HOST reviewed integration API repair\n'
                signature=api.b_signature({n:api.digest(raw) for n,raw in data.items()})
                review={'verdict':'PASS','phase':'L4','reviewer':'HOST_NON_AUTHOR','failed_run_id':api.parse(repair['job.json'])['run_id'],
                        'source_b_signature':signature,'new_defect_union':0}
                data.update({'retry-proof/'+n:raw for n,raw in repair.items()});data['retry-proof/review.json']=encode(review)
            run=base/uuid.uuid4().hex
            for name,raw in data.items():
                target=run/'input'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            inputs={n:api.digest(raw) for n,raw in data.items()}
            job={'schema_version':1,'run_id':run.name,'purpose':purpose,'inputs':inputs,'common_signature':api.common_signature(inputs),
                 'plan_sha256':api.PLAN_SHA,'hardware_approved':False,'experiment_id':api.EXPERIMENT}
            api.write(run/'job.json',job)
            return api.snapshot(run,api.sha(run/'job.json'))

        def mutate_submission(data,change):
            value=api.parse(data['ref/submission.json']);change(value);raw=encode(value);data['ref/submission.json']=raw
            config=api.parse(data['source/config.json']);config['refs']['submission.json']['sha256']=api.digest(raw)
            config['model_submission']=dict(config['refs']['submission.json']);data['source/config.json']=encode(config)

        ctx=fixture();passed('payload_positive',len(ctx.data)==len(api.SOURCE)+len(api.MODEL)+3)
        rejected('missing_source',lambda:fixture(change=lambda d:d.pop('source/sdk.py')))
        rejected('extra_inventory',lambda:fixture(change=lambda d:d.update({'source/unknown.py':b'x'})))
        rejected('model_resealed',lambda:fixture(change=lambda d:d.update({'model/robot_arm.urdf':b'resealed changed model'})))
        rejected('submission_census',lambda:fixture(change=lambda d:mutate_submission(d,lambda v:v['source_and_evidence_files'].pop(cfg['model_dir']+'/robot_arm.urdf'))))
        rejected('canonical_sha',lambda:fixture(change=lambda d:mutate_submission(d,lambda v:v.update(canonical_urdf_sha256='b'*64))))
        changed=fixture();(changed.run/'input/source/sdk.py').write_bytes(b'changed after seal')
        rejected('sha_mismatch',lambda:api.snapshot(changed.run,changed.job_hash))
        rejected('workspace_pin',lambda:fixture(change=lambda d:d.update({'ref/workspace.json':b'{"HOST":false}'})))
        rejected('json_duplicate',lambda:api.parse('{"x":1,"x":2}'))
        rejected('json_nonfinite',lambda:api.parse('{"x":NaN}'))
        rejected('json_overflow',lambda:api.parse('{"x":1e999}'))
        rejected('path_traversal',lambda:api.checked_path(base,'../escape'))
        rejected('absolute_path',lambda:api.checked_path(base,'/escape'))
        rejected('typed_job',lambda:api.job_contract({**ctx.job,'schema_version':True},ctx.run.name))
        bad=copy.deepcopy(cfg);bad['native_limits']['render_smoke']=True;rejected('config_bool_limits',lambda:api.config_contract(bad))
        bad=copy.deepcopy(cfg);bad['timeout_s']=True;rejected('config_timeout_bool',lambda:api.config_contract(bad))
        import_proof=records(ctx,{'static.json':b'{}','report.json':b'{}','model.usda':b'#usda 1.0\n'})
        api.verify_import_proof(ctx,import_proof);passed('common_import')
        other=types.SimpleNamespace(job={**ctx.job,'common_signature':'d'*64})
        rejected('different_common',lambda:api.verify_import_proof(other,import_proof))
        bad={**import_proof,'model.usda':b'changed USD'};rejected('import_seal',lambda:api.verify_import_proof(ctx,bad))
        terminal,parent,shell=(api.parse(import_proof[n]) for n in ('terminal.json','exit.json','remote-shell.json'))
        rejected('typed_process',lambda:api.process_contract(ctx.job,ctx.job_hash,terminal,{**parent,'actual_child_exit_code':False},shell))
        rejected('native_nonzero',lambda:api.process_contract(ctx.job,ctx.job_hash,{**terminal,'code':1},{**parent,'actual_child_exit_code':1,'policy_exit_code':1},{**shell,'python_exit_code':1}))
        rejected('process_direct_pid',lambda:api.process_contract(ctx.job,ctx.job_hash,{**terminal,'parent_pid':9010},parent,shell))
        for name,command,timeout in (('exit7_reaped','raise SystemExit(7)',5),('timeout_reaped','import time;time.sleep(10)',.1)):
            folder=base/name;folder.mkdir();value=api.run_child([sys.executable,'-I','-B','-c',command],folder,timeout)
            observations[name]=value
            passed(name,value['child_state']=='REAPED' and type(value['actual_child_exit_code']) is int
                   and (value['actual_child_exit_code']==value['policy_exit_code']==7 if name=='exit7_reaped' else value['timed_out'] is True and value['policy_exit_code']==124))
        ledger=lambda:{'schema_version':1,'experiment_id':api.EXPERIMENT,'reservations':[]}
        fresh=ledger();api.reserve(ctx,fresh);passed('fresh_import',len(fresh['reservations'])==1)
        rejected('duplicate_import',lambda:api.reserve(fixture(),fresh))
        wrong=ledger();wrong['experiment_id']='old';rejected('wrong_experiment_ledger',lambda:api.reserve(ctx,wrong))
        duplicate=copy.deepcopy(fresh);duplicate['reservations'].append(copy.deepcopy(duplicate['reservations'][0]))
        rejected('duplicate_ledger_identity',lambda:api.reserve(fixture(),duplicate))
        smoke=fixture('render_smoke');rejected('smoke_requires_import',lambda:api.reserve(smoke,ledger()))
        smoke_proof=records(smoke,{'report.json':b'{"HOST_DYNAMICS":true}','scene.usda':b'#usda 1.0\n'})
        smoke_proof.update({'stdout.txt':b'','stderr.txt':b''})
        motion=fixture('motion');api.verify_smoke_proof(motion);passed('smoke_proof')
        rejected('motion_requires_smoke',lambda:api.reserve(motion,copy.deepcopy(fresh)))
        changed=copy.deepcopy(motion);changed.job['inputs']['source/capture.py']=api.digest(b'other B')
        rejected('smoke_wrong_b',lambda:api.verify_smoke_proof(changed))
        changed=copy.deepcopy(motion);changed.data['smoke-proof/stderr.txt']=b'renderer failed to advance to the scheduled frame'
        rejected('smoke_bad_log',lambda:api.verify_smoke_proof(changed))
        changed=copy.deepcopy(motion);value=api.parse(changed.data['smoke-proof/exit.json']);value['actual_child_exit_code']=1
        changed.data['smoke-proof/exit.json']=encode(value);rejected('smoke_bad_exit',lambda:api.verify_smoke_proof(changed))
        chain=copy.deepcopy(fresh);api.reserve(smoke,chain);api.reserve(motion,chain);passed('stage_chain',len(chain['reservations'])==3)
        failure=records(smoke,{},code=1,failed=True);retry=fixture('render_smoke',repair=failure)
        api.verify_retry(retry);passed('retry_positive')
        def changed_retry(name,change):
            value=copy.deepcopy(retry);change(value);rejected(name,lambda:api.verify_retry(value))
        def edit(ctx,name,change):
            value=api.parse(ctx.data['retry-proof/'+name]);change(value);ctx.data['retry-proof/'+name]=encode(value)
        changed_retry('retry_zero',lambda c:edit(c,'exit.json',lambda v:v.update(actual_child_exit_code=0,policy_exit_code=0)))
        changed_retry('retry_bool',lambda c:edit(c,'terminal.json',lambda v:v.update(code=True)))
        changed_retry('retry_timeout',lambda c:edit(c,'exit.json',lambda v:v.update(timed_out=True)))
        changed_retry('retry_unchanged_b',lambda c:c.job['inputs'].update({n:h for n,h in smoke.job['inputs'].items() if n.startswith('source/') and n[7:] in api.SOURCE_B}))
        changed_retry('retry_missing_review',lambda c:c.data.pop('retry-proof/review.json'))
        changed_retry('retry_author',lambda c:edit(c,'review.json',lambda v:v.update(reviewer='author')))
        changed_retry('retry_domain',lambda c:c.job.update(common_signature='f'*64))
        retry_ledger=copy.deepcopy(fresh);api.reserve(smoke,retry_ledger)
        api.reserve(retry,retry_ledger)
        assert sum(r['purpose']=='render_smoke' for r in retry_ledger['reservations'])==2
        rejected('retry_budget',lambda:api.reserve(fixture('render_smoke',repair=failure),retry_ledger))
        retrieved=smoke.run/'retrieved';retrieved.mkdir()
        def consume_records(dynamic=True):
            files=records(smoke,{'report.json':encode({'HOST_DYNAMICS':dynamic}),'scene.usda':b'#usda 1.0\n'})
            files.update({'stdout.txt':b'','stderr.txt':b''})
            for name,raw in files.items():
                if name!='job.json':(retrieved/name).write_bytes(raw)
            api.write(smoke.run/'transport.json',{'returncode':0,'timed_out':False})
        consume_records(False);code,result=api.consume(smoke)
        passed('consume_dynamic_fail',code==1 and result['status']=='LATEST_SCENE_DYNAMICS_FAILED' and result['sdk_connected'] is True and result['actual_child_exit_code']==0)
        consume_records();(retrieved/'stderr.txt').write_bytes(b'Orchestrator failed to schedule a capture')
        rejected('consume_render_error',lambda:api.consume(smoke))
        consume_records();(retrieved/'unsealed.json').write_bytes(b'{}');rejected('consume_artifact_extra',lambda:api.consume(smoke))
    api.need(set(results)==EXPECTED and len(EXPECTED)==EXPECTED_COUNT and all(results.values()),'Fixed 48 A HOST census')
    report={'status':'A_HOST_PASS','count':EXPECTED_COUNT,'tests':results,'observations':observations,
            'fixture':'HOST_SYNTHETIC_PROTOCOL_NOT_NATIVE','native':'NOT_RUN','ssh':'NOT_RUN',
            'source_sha256':{n:api.digest(raw) for n,raw in source.items() if n in api.SOURCE_A}}
    api.write(out/'A-host.json',report);print(json.dumps({'status':report['status'],'count':EXPECTED_COUNT}));return 0
