"""133 remote owner; captured130 transport/SDK lifetime with checked new task inputs."""
from __future__ import annotations
import hashlib
from pathlib import Path

_here133=Path(__file__).resolve().parent
_base133=(_here133/'base_driver.py').read_bytes()
if hashlib.sha256(_base133).hexdigest()!='a9e9cce9fe9c56812123be8b207591092cf7ce75328a24e2c9a7e75b59d29dea':
    raise ValueError('Original130 driver bytes')
_text133=_base133.decode()
_anchor133="value = (HERE/'contract.py').read_bytes()"
if _text133.count(_anchor133)!=1:raise ValueError('Exact original basecontract loader')
_text133=_text133.replace(_anchor133,"value = (HERE/'base_contract.py').read_bytes()",1)
_anchor133="endswith('/robot-arm-lab/119/runs')"
if _text133.count(_anchor133)!=1:raise ValueError('Exact remote namespace')
_text133=_text133.replace(_anchor133,"endswith('/robot-arm-lab/133/runs')",1)
if _text133.count('limit = min(1800., remaining-602.)')!=1:raise ValueError('Exact original native parent cap')
_text133=_text133.replace('limit = min(1800., remaining-602.)','limit = min(2280., remaining-362.)',1)
for _old133,_new133 in [("local_remaining > handshake+602","local_remaining > handshake+362"),("remaining > 602","remaining > 362"),("owner['remote_deadline_monotonic']-600","owner['remote_deadline_monotonic']-360")]:
    if _text133.count(_old133)!=1:raise ValueError('Exact original linked reserve boundary:'+_old133)
    _text133=_text133.replace(_old133,_new133,1)
_process_anchor133='dict(record, parent_pid=os.getpid(), remote_deadline_monotonic=deadline,'
if _text133.count(_process_anchor133)!=1:raise ValueError('Exact parent process receipt boundary')
_text133=_text133.replace(_process_anchor133,'dict(record, watchdog_reason=_parent_watchdog_receipt133(ctx,record), parent_pid=os.getpid(), remote_deadline_monotonic=deadline,',1)
exec(compile(_text133,str(_here133/'base_driver.py')+'#133','exec'),globals())
_original_context133=_context


def _parent_watchdog_receipt133(ctx,record):
    """One bounded post-reap read, embedded in existing parent-owned process.json."""
    receipt={'status':'UNKNOWN_NOT_REAPED','run_id':ctx.job['run_id'],'job_sha256':ctx.job_hash,
        'parent_pid':record.get('child_pid'),'parent_birth':record.get('child_creation_time'),
        'OS_exit_causality':'NOT_INFERRED_FROM_INTENT_OR_EXIT_CODE','entries':[]}
    if not (record.get('child_state')=='REAPED' and record.get('job_active_after')==0 and record.get('raw_complete') is True):return receipt
    try:
        path=C.path_in(ctx.run,'watchdog-reason.ndjson')
        with path.open('rb') as stream:raw=stream.read(65537)
        if len(raw)>65536:
            receipt.update(status='UNKNOWN_LOG_UNBOUNDED',bounded_read_bytes=len(raw),prefix_sha256=hashlib.sha256(raw).hexdigest());return receipt
        receipt.update(raw_sha256=hashlib.sha256(raw).hexdigest(),raw_bytes=len(raw))
        if not raw:
            receipt['status']='UNKNOWN_LOG_EMPTY';return receipt
        entries=[parse(line) for line in raw.splitlines()]
        need(len(entries)<=16,'Bounded watchdog entries')
        allowed={'ARMED','PHASE_ARMED','NORMAL_DISARM','PARENT_EXITED','PHASE_DEADLINE','GLOBAL_DEADLINE','CONTROL_PIPE_EOF','CONTROL_PIPE_INVALID'}
        for row in entries:
            need(row['run_id']==ctx.job['run_id'] and row['job_sha256']==ctx.job_hash and row['parent_pid']==record['child_pid'] and
                 type(row['parent_birth']) is int and row['parent_birth']==record['child_creation_time'],'Owned watchdog intent identity')
            need(row['reason'] in allowed and row['phase'] in ('import','hold','small','large') and type(row['kill_intent']) is bool,'Typed watchdog intent semantics')
            need(all(type(row[k]) in (float,int) and math.isfinite(row[k]) for k in ('chosen_deadline_monotonic','phase_deadline_monotonic','native_end_monotonic','observed_monotonic')) and
                 row['chosen_deadline_monotonic']==min(row['phase_deadline_monotonic'],row['native_end_monotonic']),'Actual chosen watchdog deadline')
        terminal_reasons={'NORMAL_DISARM','PARENT_EXITED','PHASE_DEADLINE','GLOBAL_DEADLINE','CONTROL_PIPE_EOF','CONTROL_PIPE_INVALID'}
        receipt.update(status='OBSERVED_VALIDATED_ASYNC_INTENTS' if entries[-1]['reason'] in terminal_reasons else 'UNKNOWN_TERMINATION_INTENT_NOT_RECORDED',entries=entries)
    except FileNotFoundError:receipt['status']='UNKNOWN_LOG_NOT_FOUND'
    except Exception as exc:receipt.update(status='UNKNOWN_LOG_READ_OR_VALIDATION_ERROR',error_type=type(exc).__name__)
    return receipt


def _context(run,expected_job_sha256):
    ctx=_original_context133(run,expected_job_sha256)
    need(ctx.job.get('task_unit')==133 and ctx.job.get('purpose')=='physics_pick_place_133','New task with legacy SDK envelope')
    facade=load_module('contract133_'+ctx.job['run_id'],ctx.data['source/contract.py'],ctx.run/'input/source/contract.py')
    planner=load_module('planner132_'+ctx.job['run_id'],ctx.data['source/planner132.py'],ctx.run/'input/source/planner132.py')
    scenario=parse(ctx.data['source/scenario132.json'])
    facade.configure(scenario,planner)
    ctx.contract=facade;ctx.scenario=scenario;ctx.planner=planner;ctx.jaw_components=parse(ctx.data['source/jaw_components.json'])
    need(hashlib.sha256(ctx.data['source/current-user-approval.json']).hexdigest()==ctx.job['current_user_approval_sha256']=='5a2f2e4656fdb0d9b9ed4d082751a3d001ea2d9059f509bd14def3b0355611fc','Current explicit user authority in actual producer job')
    need(ctx.cfg['task_unit']==133 and ctx.cfg['hardware_approved'] is False,'Actual config133')
    need(ctx.cfg['limits']['native_s']==2280 and ctx.cfg['limits']['recovery_reserve_s']==360 and ctx.cfg['limits']['large_s']==1120 and ctx.cfg['limits']['handshake_s']==20 and ctx.cfg['limits']['cleanup_s']==2 and ctx.cfg['limits']['total_s']==2700,'Fixed linked2280/360/1120 limits inside2700')
    need(ctx.cfg['program']['dt_s']==1/120 and ctx.cfg['program']['capture_stride']==12,'Original physics/capture rate')
    need({n:ctx.cfg['program']['stages'][n]['duration_s'] for n in ('hold','small','large')}==facade.DURATIONS,'Legacy87actual_to85source adapter')
    return ctx


def bootstrap_code(args):
    """Exact captured function; no mutable inspect/getsource dependency."""
    import ast
    tree=ast.parse(_text133)
    names={'need','_safe_name','_unpack_payload','lease_end','_bootstrap'}
    blocks=[ast.get_source_segment(_text133,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    need(len(blocks)==len(names),'Closed bootstrap inventory')
    header='import sys,os,time,threading,hashlib,json,math,re,types,io,zipfile\nfrom pathlib import Path,PurePosixPath\n'
    # Original bootstrap parses only closed JSON, before any payload code is loaded.
    contract=_checked_contract_bytes().decode()
    parseblock=next(ast.get_source_segment(contract,n) for n in ast.parse(contract).body if isinstance(n,ast.FunctionDef) and n.name=='parse')
    return header+'\n\n'.join(blocks)+'\n'+parseblock+'\n_bootstrap('+repr(args)+')\n'
