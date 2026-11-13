"""137 offline-only producer. There is no SDK, network or remote-admission option."""
from __future__ import annotations
import pathlib as _bp
import os as _bo
import sys as _bs
from types import MappingProxyType as _mp
if '_BYTES137' not in globals():
    _br=_bp.Path(__file__).absolute().parents[3]
    _bn=('src/simulation/mp18_pinion_feedback_137/prepare.py','src/simulation/mp18_pinion_feedback_137/feedback.py',
         'src/simulation/mp18_pinion_feedback_137/test_feedback.py','src/simulation/mp18_pinion_feedback_137/test_prepare.py',
         'docs/design/137-measured-jaw-pinion-feedback.md')
    _bb={}
    for _n in _bn:
        _p=_br/_n
        for _a in (_p,)+tuple(_p.parents):
            _s=_bo.lstat(_a)
            if _bo.path.islink(_a) or getattr(_s,'st_file_attributes',0)&0x400:raise ValueError('Native reparse/symlink source ancestor')
        _bb[_n]=_p.read_bytes()
    _BYTES137=_mp(dict(_bb));del _bb
    _captured_code137=compile(_BYTES137[_bn[0]],__file__,'exec',dont_inherit=True)
    if _captured_code137!=_bs._getframe().f_code or _captured_code137.co_filename!=_bs._getframe().f_code.co_filename:raise ValueError('Initial producer code differs from captured bytes')
    exec(_captured_code137,globals())
else:
    import argparse,ast,copy,hashlib,io,json,marshal,math,pickle,re,sys,time,types
    from contextlib import contextmanager
    from pathlib import Path
    import numpy as np
    F=types.ModuleType('feedback137');F.__file__=str(Path(__file__).absolute().parent/'feedback.py')
    exec(compile(_BYTES137['src/simulation/mp18_pinion_feedback_137/feedback.py'],F.__file__,'exec',dont_inherit=True),F.__dict__)
    PLAN='docs/design/137-measured-jaw-pinion-feedback.md'
    PLAN_SHA='9170955aa9b9118acb6af658598039b5dbb3fa2e76b7c8c57d40d8b3a2091c78'
    F133='outputs/mp18-manipulation-133/author/source-freeze.json'
    F133SHA='3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f'
    NATIVE='outputs/mp18-manipulation-133/attempts/05/native-result.json'
    NATIVESHA='c4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2'
    MOTION='outputs/mp18-manipulation-133/attempts/05/retrieved/motion.ndjson'
    ROOT136='outputs/mp18-mating-analysis-136/'
    FIXED={ROOT136+'Root-final-result.json':'c5610c15a6a4bc0a192c99190479c5a41610473da318480d3ad5701dc0ad9aa3',
      ROOT136+'author/source-freeze.json':'07ae1e1bb61b2ea6c62caf9f48e9b29e4972c7d42d21951d74b2650c17513162',
      ROOT136+'review/L4-r1/report.json':'6fbb60c700a17d4ccf8685e421396654fe3f0a3fe8a2458730c57356d19094bf',
      ROOT136+'review/L4-r1/publication.json':'f0db30e8665c9b7df637ddd7a55181da8baf0602fca39b0c1918ff611923cc7e'}
    OWN='src/simulation/mp18_manipulation_133/'

    def sha(raw):return hashlib.sha256(raw).hexdigest()
    def encode(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')
    def parse(raw):
        def pairs(xs):
            d={}
            for k,v in xs:F.need(k not in d,'Duplicate JSON key');d[k]=v
            return d
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:F.need(False,'Nonfinite JSON'))
    def pin(raw):return {'sha256':sha(raw),'bytes':len(raw)}
    def no_reparse(p):
        for a in (p,)+tuple(p.parents):
            if not a.exists() and not a.is_symlink():continue
            s=a.lstat();F.need(not a.is_symlink() and not(getattr(s,'st_file_attributes',0)&0x400),'Native reparse/symlink ancestor rejected')
    def destination(root,name,create=False):
        F.need(type(name)is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',name)is not None,'Restricted fresh leaf slug')
        root=Path(root).absolute();p=root/'outputs/mp18-pinion-feedback-137'/name;no_reparse(p)
        if create:p.parent.mkdir(parents=True,exist_ok=True);no_reparse(p);p.mkdir(exist_ok=False)
        return p
    def bundle_check(root):
        for n,b in _BYTES137.items():no_reparse(root/n);F.need((root/n).read_bytes()==b,'Captured137 source drift')
        F.need(sha(_BYTES137[PLAN])==PLAN_SHA,'Accepted137 plan pin')

    class Inputs:
        def __init__(self,root):
            self.root=root;self.raw={};self.manifest={}
            frozen=parse(self.get(F133,F133SHA))
            F.need(frozen['unit']==133 and frozen['hardware_approved']is False,'Original frozen133 source')
            for name,e in frozen['files'].items():self.get(name,e['sha256'],e['bytes'])
            for name,s in FIXED.items():self.get(name,s)
            native=parse(self.get(NATIVE,NATIVESHA))
            F.need(native['run_id']=='850124eb93cc4cc4945ee02c3aa1ed0d' and native['job_sha256']=='816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae' and native['runtime_accepted']is True,'Actual133/05 identity')
            ref136=parse(self.raw[ROOT136+'author/source-freeze.json'])
            m136path=ref136['baseline']+'/input-manifest.json';m136=parse(self.get(m136path,ref136['evidence'][m136path]['sha256'],ref136['evidence'][m136path]['bytes']))
            e=m136[MOTION];motion=self.get(MOTION,native['files_sha256']['motion.ndjson'],e['bytes']);F.need(sha(motion)==e['sha256'],'Same actual motion pin')
            self.cfg=parse(self.raw[OWN+'config.json']);self.rows=[parse(line)for line in motion.splitlines()]
            F.need(len(self.rows)==11161,'Original11161 rows')
            for i,row in enumerate(self.rows):
                F.need(type(row['step'])is int and row['step']==i and abs(F.number(row['time_s'])-i/120)<1e-8,'Continuous actual133 rows')
                F.checked_clock(row['clock'],i)
                for key in ['q','qd','targets','velocity_targets','reference_velocity']:
                    F.need(set(row[key])==set(F.NAMES),'Raw nine DOFs')
                    for v in row[key].values():F.number(v)
                F.need(len(row['body_poses'])==11 and {p['name']for p in row['body_poses']}=={'Base','Link1','Link2','Link3','Link4','Link5','Link6','KG1','KG1_A','KG1_B','KG1_R'},'Original body census')
        def get(self,name,expected,bytes_expected=None):
            F.need(type(name)is str and not Path(name).is_absolute() and '..'not in Path(name).parts and ':'not in name,'Relative input path')
            no_reparse(self.root/name);raw=(self.root/name).read_bytes();F.need(sha(raw)==expected and(bytes_expected is None or len(raw)==bytes_expected),'Input pin:'+name)
            if name in self.raw:F.need(self.raw[name]==raw,'One consumed input version')
            self.raw[name]=raw;self.manifest[name]=pin(raw);return raw
        def recheck(self):
            for n,b in self.raw.items():no_reparse(self.root/n);F.need((self.root/n).read_bytes()==b,'Consumed input drift:'+n)

    def make_wrapper(native133,feedback_raw):
        text=native133.decode('utf-8');anchor="exec(compile(_text,str(_here/'base_native.py')+'#derived133','exec'),globals())"
        F.need(text.count(anchor)==1,'One133 final native execution anchor')
        loader="""import types as _types137
_feedback_raw137 = (_here/'feedback137.py').read_bytes()
if hashlib.sha256(_feedback_raw137).hexdigest() != FEEDBACK_SHA:
    raise ValueError('137 feedback bytes changed before execution')
_feedback137 = _types137.ModuleType('feedback137')
_feedback137.__file__ = str(_here/'feedback137.py')
exec(compile(_feedback_raw137,_feedback137.__file__,'exec'),_feedback137.__dict__)
_text,_anchors137 = _feedback137.derive_effective(_text)
""".replace('FEEDBACK_SHA',repr(sha(feedback_raw)))
        return text.replace(anchor,loader+anchor,1).encode('utf-8')

    def kit_values(inputs):
        cfg,raw=inputs.cfg,inputs.raw;deps=cfg['dependency_paths'];values={}
        for n in ['contract.py','config.json','jaw_components.json']:values['source/'+n]=raw[OWN+n]
        values['source/native.py']=make_wrapper(raw[OWN+'native.py'],_BYTES137['src/simulation/mp18_pinion_feedback_137/feedback.py'])
        values['source/feedback137.py']=_BYTES137['src/simulation/mp18_pinion_feedback_137/feedback.py']
        for n in ['contract','native']:values['source/base_'+n+'.py']=raw[deps['base_'+n]]
        values['source/planner132.py']=raw[deps['planner132']];values['source/scenario132.json']=raw[deps['scenario132']]
        program=parse(raw[deps['base_program']]);program['stages']={n:dict(program['stages'][n],duration_s=d)for n,d in [('hold',8),('small',31),('large',54)]};program['purpose']='PHYSICS_PICK_PLACE_133_LEGACY_ENVELOPE_8_31_54';program['settling']['large_check_s']=48
        values['source/program.json']=encode(program)
        for name,e in cfg['model_pins'].items():
            b=raw[cfg['model_dir']+'/'+name];F.need(pin(b)==e,'Original model member');values['model/'+name]=b
        for name,e in cfg['refs'].items():values['ref/'+name]=raw[e['path']]
        for name in values:
            F.need(not any(t in name.lower()for t in ['approval','driver','runner','proxy','lease','job.json','bootstrap']),'No old admission or transport in kit')
        return values

    def write_exclusive(p,raw):
        no_reparse(p);p.parent.mkdir(parents=True,exist_ok=True);no_reparse(p)
        with p.open('xb')as f:f.write(raw)
    def load_module(name,raw,path):
        m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(raw,str(path),'exec',dont_inherit=True),m.__dict__);return m
    def load_kit(folder,manifest):
        captured={}
        for name,e in manifest.items():
            no_reparse(folder/name);b=(folder/name).read_bytes();F.need(pin(b)==e,'Runtime kit pin:'+name);captured[name]=b
        # Sibling reads in the unchanged contract/native are guarded by their original fixed hashes.
        C=load_module('contract137_HOST',captured['source/contract.py'],folder/'source/contract.py')
        planner=load_module('planner137_HOST',captured['source/planner132.py'],folder/'source/planner132.py');C.configure(parse(captured['source/scenario132.json']),planner)
        N=load_module('native137_HOST',captured['source/native.py'],folder/'source/native.py')
        for name,b in captured.items():F.need((folder/name).read_bytes()==b,'Kit changed during module loading')
        F.need(N._feedback_raw137==captured['source/feedback137.py']and N._raw==captured['source/base_native.py'],'Actually consumed captured native sources')
        return captured,C,N

    def code_for_loop(N,restore_old=False):
        source=N._text
        if restore_old:
            F.need(source.count(F.SETTER_NEW)==1,'One corrected dispatch to restore');source=source.replace(F.SETTER_NEW,F.SETTER_OLD,1)
            F.need(source.count('return _feedback137.journal_row(row137,applied137)')==1,'One added receipt path to restore')
            source=source.replace('return _feedback137.journal_row(row137,applied137)','return row137',1)
        compiled=compile(source,N._native.__code__.co_filename,'exec');native_code=next(x for x in compiled.co_consts if isinstance(x,types.CodeType)and x.co_name=='_native')
        if not restore_old:F.need(marshal.dumps(native_code)==marshal.dumps(N._native.__code__),'Actual generated native function code binding')
        else:
            env=dict(N.__dict__);exec(compiled,env);F.need(marshal.dumps(env['_native'].__code__)==marshal.dumps(native_code),'Restored actual native compiled function')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)and n.name=='_native')
        selected=[]
        for n in node.body:
            if isinstance(n,ast.FunctionDef)and n.name in ['tcp','matrices','row_for']:selected.append(n)
            if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='applied137'for t in n.targets):selected.append(n)
            if isinstance(n,ast.With)and "motion.ndjson"in ast.get_source_segment(source,n):selected.append(n)
        F.need(len(selected)==5,'Actual tcp/matrices/receipt/row/journal-loop AST census')
        module=ast.Module(body=selected,type_ignores=[]);ast.fix_missing_locations(module)
        inventory={'actual_native_code_sha256':sha(marshal.dumps(native_code)),'code_binding_includes_execution_filename':True,'execution_filename':native_code.co_filename,'selected_AST_sha256':sha(ast.dump(module,include_attributes=True).encode()),'stable_selected_AST_sha256':sha(ast.dump(module,include_attributes=False).encode()),'source_sha256':sha(source.encode()),'restore_exact_old_setter':restore_old,'selected_top_level_nodes':len(selected)}
        return compile(module,'<137-actual-native-command-journal-loop>','exec'),inventory,source

    class Tensor:
        def __init__(self,value):self.value=np.asarray(value,dtype=float)
        def numpy(self):return self.value
    class HostRobot:
        def __init__(self,names,poison=False):self.names=names;self.calls=[];self.values={};self.poison=poison
        def set_dof_max_efforts(self,v):self.calls.append('max_efforts');self.values['max_efforts']=v
        def set_dof_position_targets(self,v):self.calls.append('position');self.values['position']=v
        def set_dof_velocity_targets(self,v):self.calls.append('velocity');self.values['velocity']=v
        def set_dof_efforts(self,v):self.calls.append('efforts');self.values['efforts']=v
        def get_dof_gravity_compensation_forces(self):return Tensor([[0.]*9])
        def get_dof_max_efforts(self):return Tensor(self.values['max_efforts'])
        def get_dof_position_targets(self):
            v=copy.deepcopy(self.values['position'])
            if self.poison:v[0][self.names.index(F.FOLLOWER)]+=.1
            return Tensor(v)
        def get_dof_velocity_targets(self):return Tensor(self.values['velocity'])

    def replay(folder,manifest,rows,names=None,restore_old=False,poison=False,mutate_current=None,steps_limit=None,callback=None,clock_advance_on_dispatch=False):
        captured,C,N=load_kit(folder,manifest);model=C.parse_model(folder/'model/robot_arm.urdf');F.model_ratio(model)
        names=list(F.NAMES if names is None else names);F.need(len(names)==9 and set(names)==set(F.NAMES),'HOST native order')
        code,binding,effective=code_for_loop(N,restore_old);program=parse(captured['source/program.json']);cfg=parse(captured['source/config.json']);robot=HostRobot(names,poison)
        # No dynamics/SDK/geometry/Task acceptance is simulated: only these callbacks are replaced.
        HostC=types.SimpleNamespace(**{n:getattr(C,n)for n in dir(C)if not n.startswith('__')})
        HostC.gravity_reference=lambda *a:{n:0. for n in F.NAMES};HostC.floor_and_bounds=lambda *a:(0.,{})
        HostC.phase_check=lambda *a:{'passed':True,'reasons':['HOST_ONLY_NO_PHYSICAL_ACCEPTANCE']}
        step=[0];receipts=[];records=[];peak={'abs_error_rad':-1};source_hash=sha(pickle.dumps(rows,protocol=5));initial_seen=[False];backend_enters=[0];clock_offset=[0.]
        def clock():
            value=copy.deepcopy(rows[step[0]]['clock']);value['engine_time_s']+=clock_offset[0];return value
        @contextmanager
        def host_backend(*a,**kw):
            backend_enters[0]+=1
            if clock_advance_on_dispatch and backend_enters[0]==2:clock_offset[0]=1/120
            yield
        def state():
            row=rows[step[0]];v={key:copy.deepcopy(row[key])for key in ['q','qd','body_poses','clock']};v['clock_before']=copy.deepcopy(v['clock']);v['clock_after']=copy.deepcopy(v['clock']);v['_host_reconstructed_clock_bounds']=True;v['object']=copy.deepcopy(row.get('object'))
            if mutate_current:mutate_current(v,step[0])
            return v
        def simstep(render=False):
            F.need(render is False,'Unchanged physics step call');step[0]+=1
        probe=types.SimpleNamespace(last={});ctx=types.SimpleNamespace(_contact_probe=probe,_fault_pending={},write=lambda *a:None)
        probe.sample=lambda n:probe.last.update(observer_changed_state=False,state_preservation_unverified=False)
        class Journal:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def flush(self):pass
            def write(self,text):
                row=parse(text);n=row['step']
                if n==0:
                    F.need(restore_old or row['applied137']=={'status':'NOT_APPLIED_INITIAL_ROW'},'No initial setter');initial_seen[0]=True;return
                source,logical=rows[n-1],rows[n]
                pos=dict(zip(names,robot.values['position'][0]));vel=dict(zip(names,robot.values['velocity'][0]))
                for name in F.NAMES:
                    F.need(abs(row['targets'][name]-logical['targets'][name])<1e-12,'Logical trajectory preserved')
                    F.need(row['q'][name]==logical['q'][name]and row['qd'][name]==logical['qd'][name],'Original actual state preserved')
                    if name!=F.FOLLOWER:F.need(pos[name]==C.binary32(logical['targets'][name])and vel[name]==logical['velocity_targets'][name],'Other8 transmitted references unchanged')
                error=pos[F.FOLLOWER]-(F.RATIO*source['q'][F.LEADER]);velocity_error=vel[F.FOLLOWER]-F.RATIO*source['qd'][F.LEADER]
                if abs(error)>peak['abs_error_rad']:peak.update(abs_error_rad=abs(error),signed_error_rad=error,command_step=n,source_step=n-1,source_time_s=source['time_s'],old_logical_pinion_rad=logical['targets'][F.FOLLOWER],actual_leader_m=source['q'][F.LEADER],transmitted_pinion_rad=pos[F.FOLLOWER])
                if not restore_old:
                    F.need(abs(error)<=1e-7 and abs(velocity_error)<=1e-7,'Applied measured coupling within binary32 rounding')
                    F.need(row['applied137']['source_step']==n-1 and row['applied137']['readback_verified'],'Applied receipt consumed by journal')
                    receipts.append(row['applied137'])
                records.append({'step':n,'source_step':n-1,'position_rad':pos[F.FOLLOWER],'velocity_rad_s':vel[F.FOLLOWER],'coupling_error_rad':error,'velocity_coupling_error_rad_s':velocity_error,'B_residual_rad':pos[F.FOLLOWER]-F.RATIO*source['q'][F.OTHER]})
                if callback:callback(row,pos,vel)
                if steps_limit is not None and n>=steps_limit:raise HostComplete()
        class HostPath:
            def __truediv__(self,name):F.need(name in ['motion.ndjson','report.partial.json'],'Actual journal/report filename');return self
            def open(self,mode,encoding,newline):F.need((mode,encoding,newline)==('x','utf-8','\n'),'Actual exclusive journal mode');return Journal()
        report={'completed_steps':0,'frames':[]};budget=types.SimpleNamespace(check=lambda:None,enter=lambda x:None)
        env=dict(N.__dict__);env.update(C=HostC,model=model,names=names,robot=robot,backend=types.SimpleNamespace(use_backend=host_backend),array=lambda x:x.numpy().copy(),clock=clock,state=state,sim=types.SimpleNamespace(step=simstep),ctx=ctx,report=report,program=program,budget=budget,current=state(),baseline=clock(),inertias={},caps=cfg['cap_modes']['sim_override_12_7'],support={},out=HostPath(),camera=types.SimpleNamespace(capture=lambda *a:{}),_task133=lambda *a,**k:None,_fault_begin=lambda *a:setattr(ctx,'_fault_pending',{}),_fault_observe=lambda *a:None,mark=lambda *a,**k:None)
        try:exec(code,env)
        except HostComplete:
            F.need(steps_limit is not None and step[0]==steps_limit,'Only the requested HOST prefix may stop early')
        F.need(source_hash==sha(pickle.dumps(rows,protocol=5)),'HOST replay never mutates original record')
        count=len(records);F.need(initial_seen[0]and count==(11160 if steps_limit is None else steps_limit),'All intended actual command branches reached')
        result={'command_count':count,'source_rows':len(rows),'setter_calls':len(robot.calls),'other8DOF_unchanged':True,'logical_trajectory_preserved':True,'original_actual_states_preserved':True,'actual_native_AST_binding':binding,'peak_position_reference_coupling_error':peak,'max_velocity_reference_coupling_error_rad_s':max(abs(v['velocity_coupling_error_rad_s'])for v in records),'B_reference_uses_A_not_average':True,'HOST_clock_before_after_reconstructed':True,'new_plant_response_generated':False,'new_runtime_accepted':False,'physical_gear_contact_verified':False,'mocked_outside_command_scope':['gravity force/reference','floor geometry','Task/contact acceptance','render/camera','fault diagnostic capture','phase result mark'],'exact_old_dispatch_restored':restore_old}
        return result,receipts,records,effective

    @contextmanager
    def empty_backend():yield
    class HostComplete(Exception):pass

    def render_report(summary,replay_result,old):
        return '\n'.join(['# 137 — 실측 jaw 기준 피니언 reference 준비', '',
          '오프라인 native 명령 배선 검증과 runtime kit 준비다. 새 SDK·원격 실행·동역학·그립 성공은 NOT_RUN이다.',
          f"원133 기록11161행/실제 command분기 {replay_result['command_count']}개를 재생했다. 다른8DOF·논리목표·원실측상태는 보존했다.",
          f"A 실측 위치 기준 전송결합 최대오차: {replay_result['peak_position_reference_coupling_error']['abs_error_rad']:.12g} rad (binary32 반올림).",
          f"같은 실제 setter 분기를 이전 목표값 연동으로 복원한 최대오차: {old['peak_position_reference_coupling_error']['abs_error_rad']:.12g} rad.",
          '실제 n-1 관측 q/qd와 같은 시계에서 피니언 위치/속도 reference만 계산한다. logical targets/기존 acceptance는 변경하지 않았다.',
          'HOST에서 clock_before/after는 원raw에 없으므로 row clock으로 재구성했다. 실제 live state()의 기존 전후시계 검산은 파생 코드에 남아 있다.',
          'fake SDK는 새 plant response를 만들지 않는다. 원실제 결합오차·원135 겹침·133수용 및 영상은 그대로다.',
          'kit는 명시 allowlist의 native/feedback/readonly 의존성만 포함하고 approval/job/lease/runner/driver/proxy/transport는 제외한다.',
          'PREPARED_NOT_RUN / new_runtime_approved=false / hardware_approved=false. 과거 grant나133 attempt6를 활성화하지 않는다.',
          '게인·cap·속도한도·기존 판정·CAD/URDF/STL·출력작업·실물CAN/RS485·설정은 변경하지 않았다.',
          '실제 pinion 추종·안정성·접촉·물리적 기어 치합은 새로 승인된 owner/SDK 검증의 별도 과제다.', ''])

    def run(name,root=None,before_publish=None):
        started=time.monotonic();root=Path(__file__).absolute().parents[3]if root is None else Path(root).absolute();bundle_check(root);out=destination(root,name,True);inputs=Inputs(root);values=kit_values(inputs);kit=out/'runtime-kit'
        for rel,raw in values.items():destination(root,name);write_exclusive(kit/rel,raw)
        manifest={n:pin(b)for n,b in values.items()};write_exclusive(out/'kit-manifest.json',encode(manifest))
        current,receipts,records,effective=replay(kit,manifest,inputs.rows)
        old,_,oldrecords,_=replay(kit,manifest,inputs.rows,restore_old=True)
        F.need(old['peak_position_reference_coupling_error']['abs_error_rad']>.01 and current['peak_position_reference_coupling_error']['abs_error_rad']<1e-7,'Numerical discrimination of exact old dispatch')
        write_exclusive(out/'effective-native137.py',effective.encode('utf-8'))
        source_manifest={n:pin(b)for n,b in _BYTES137.items()}
        summary={'unit':137,'schema':'offline-measured-pinion-preparation-v1','prepared_complete':True,'status':'PREPARED_NOT_RUN','new_runtime_approved':False,'hardware_approved':False,'command_count':current['command_count'],'source_rows':11161,'kit_files':len(values),'source_run_id':'850124eb93cc4cc4945ee02c3aa1ed0d','new_plant_response_generated':False,'new_SDK_SSH_Drive_hardware_actions':0,'old_approval_transport_excluded':True,'original_acceptance_changed':False,'original_geometry_changed':False,'source_binding':'IMMUTABLE_CAPTURED_137_BYTES_COMPILED_AND_EXECUTED','elapsed_s':time.monotonic()-started,'reproduction':'printforge/.venv/Scripts/python.exe -X utf8 -I -B -u robot-arm-lab/src/simulation/mp18_pinion_feedback_137/prepare.py --name NEW_UNIQUE_SLUG'}
        if before_publish:before_publish(inputs,out,kit,manifest)
        def boundary():F.need(destination(root,name)==out,'Fixed137 output authority');bundle_check(root);inputs.recheck()
        boundary()
        for rel,e in manifest.items():F.need(pin((kit/rel).read_bytes())==e,'Runtime kit changed before publication')
        for leaf,v in [('replay-summary.json',current),('old-dispatch-counterexample.json',old),('command-receipts.json',receipts),('command-observations.json',records),('old-command-observations.json',oldrecords),('input-manifest.json',inputs.manifest),('source-manifest.json',source_manifest),('PREPARED_NOT_RUN.json',{'unit':137,'new_runtime_approved':False,'hardware_approved':False,'SDK':'NOT_RUN','old_grants_rearmed':False})]:write_exclusive(out/leaf,encode(v))
        write_exclusive(out/'preparation-report.md',render_report(summary,current,old).encode('utf-8'))
        boundary()
        for rel,e in manifest.items():F.need(pin((kit/rel).read_bytes())==e,'Runtime kit changed during publication')
        summary['artifacts']={p.relative_to(out).as_posix():pin(p.read_bytes())for p in out.rglob('*')if p.is_file()}
        write_exclusive(out/'preparation.json',encode(summary));return summary,out

    def main():
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',required=True);a=p.parse_args();s,out=run(a.name);print(json.dumps({'prepared':s['prepared_complete'],'path':str(out),'commands':s['command_count'],'new_runtime_approved':False}),flush=True)
    if __name__=='__main__':main()
