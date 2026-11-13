"""Closed-export and actual-caller tests. Synthetic transport; no SDK/network."""
from pathlib import Path
from unittest.mock import patch
import copy,json,shutil,stat,subprocess,tempfile,types,uuid,warnings,zipfile

def run_tests(api,source):
    out=Path(__file__).resolve().parents[3]/'outputs/isaac-clock-ready-108';tests={}
    r=types.ModuleType('recovery096');exec(compile(source['recovery.py'],'recovery.py','exec'),r.__dict__)
    def yes(n,v):assert v,n;tests[n]=True
    def reject(n,f):
        try:f()
        except (ValueError,KeyError,TypeError,OSError,api.RecoveryTransportError,zipfile.BadZipFile):tests[n]=True
        else:raise AssertionError(n)
    def put(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
    def fixture(base,partial=False,code=0):
        run=base/uuid.uuid4().hex;(run/'input/source').mkdir(parents=True);o=run/'output';o.mkdir()
        cfg={'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','sdk':{'hardware_approved':False,'calibration_approved':False}}
        data={'source/driver.py':source['driver.py'],'source/recovery.py':source['recovery.py'],'source/config.json':json.dumps(cfg).encode()}
        for n,b in data.items():(run/'input'/n).write_bytes(b)
        j={'schema_version':1,'run_id':run.name,'purpose':'motion','inputs':{n:r.digest(b) for n,b in data.items()},'common_signature':'c'*64,'plan_sha256':api.PLAN_SHA,'hardware_approved':False,'experiment_id':'SYNTHETIC_HOST_096'}
        put(run/'job.json',j);h=r.sha(run/'job.json');identity={'run_id':run.name,'job_sha256':h,'purpose':'motion'}
        (o/'stdout.txt').write_bytes(b'HOST_CLOSED');(o/'stderr.txt').write_bytes(b'');name='report.partial.json' if partial else 'report.json';(o/name).write_bytes(b'{"HOST_ONLY":true}')
        ex={**identity,'pid':101,'child_pid':202,'actual_child_exit_code':1 if partial else code,'policy_exit_code':124 if partial else code,'timed_out':partial,'child_state':'REAPED','keep_awake_reset':True}
        put(o/'exit.json',ex);put(o/'remote-shell.json',{**identity,'python_exit_code':ex['policy_exit_code']})
        if partial:put(o/'recovery-manifest.json',{**identity,'kind':'FAILED_PARENT_RECOVERY_SNAPSHOT_NOT_NATIVE_TERMINAL','status':'FAILED','native_acceptance':False,'native_reexecuted':False,'exit':ex,'files_sha256':{n:v for n,v in r.inventory(o).items() if n!='remote-shell.json'}})
        else:put(o/'terminal.json',{**identity,'pid':202,'parent_pid':101,'code':code,'status':'CLOSED' if code==0 else 'FAILED','phase':'APP_CLOSED' if code==0 else 'COLLECTING','hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','files_sha256':{name:r.sha(o/name)}})
        return run,h,j['inputs']['source/driver.py'],j
    yes('source18_inventory',set(source)==api.SOURCE and len(source)==18)
    for role in ('prepare','run'):reject('public_'+role+'_blocked',lambda role=role:api.public(role))
    for role in ('supervise','native'):reject('remote_'+role+'_blocked',lambda role=role:api.entry('invalid','a'*64,'b'*64,role))
    reject('direct_prepare_blocked',lambda:api.prepare(source,'import'));reject('inactive_supervise_timing',lambda:api.launch_budget(api.parse(source['config.json']),'import'))
    cfg=api.parse(source['config.json']);yes('production_deadline0',type(cfg['deadline_unix']) is int and cfg['deadline_unix']==0)
    yes('native_budget1_inactive_deadline',cfg['offline_only'] is False and cfg['native_limits']=={'import':1,'render_smoke':1,'motion':1})
    yes('config_source18_census',set(cfg['source_A'])==api.SOURCE_A and set(cfg['source_B'])==api.SOURCE_B)
    for key,valid in (('export_timeout_s',300),('recovery_total_s',600)):
        for i,bad in enumerate((True,float(valid),None,valid+1)):
            value={**cfg,key:bad};reject(key+'_type_'+str(i),lambda value=value:api.recovery_limits(value))
    c={**cfg,'deadline_unix':3000.}
    yes('total600',api.recovery_deadline(c,1000)==1600);yes('global_cap',api.recovery_deadline({**c,'deadline_unix':1400.},1000)==1400)
    yes('call300',api.recovery_timeout(c,1600,1000)==300);yes('remaining50',api.recovery_timeout(c,1600,1550)==50)
    reject('deadline_equal',lambda:api.recovery_timeout(c,1600,1600));reject('bool_deadline',lambda:api.recovery_deadline({**c,'deadline_unix':True},1000));reject('nan_clock',lambda:api.recovery_deadline(c,float('nan')))
    for n in ('../x','/abs','a\\b','x:y','a//b','a/./b'):yes('unsafe_relative_'+n,not r.relative(n))
    yes('Windows_aliases_string_only_rejected',all(not r.relative(n) for n in ('.. ','file.','NUL','CON.txt','COM1','LPT1.log','x/COM2.txt')))
    with patch.object(Path,'is_symlink',side_effect=AssertionError('FILESYSTEM_QUERY_MUST_NOT_REACH_DEVICE')):
        reject('device_rejected_before_FS_query',lambda:r.safe(out/'COM1'))
    with tempfile.TemporaryDirectory(prefix='096-host-',dir=out) as tmp:
        base=Path(tmp).resolve();assert base.is_relative_to(out.resolve());run,h,ds,j=fixture(base)
        with patch.dict(api.entry.__globals__,{'snapshot':lambda *a:(_ for _ in ()).throw(AssertionError('SNAPSHOT_REACHED'))}):yes('actual_export_before_snapshot',api.entry(str(run),h,ds,'export')==0)
        packet=r.read(run/'recovery-receipt.json');yes('no_copy_acceptance',packet['native_acceptance'] is False and packet['native_reexecuted'] is False)
        yes('archive_hash_bound',r.verify_archive(run/'records.zip',packet,h,ds)['job_sha256']==h)
        r.unpack_verified(run/'records.zip',run/'recovery-receipt.json',run/'recovered',h,ds);yes('extracted_bytes_equal',r.inventory(run/'recovered')==r.inventory(run/'output'))
        old=(run/'records.zip').read_bytes();reject('repeat_export_reject',lambda:r.export_closed(run,h,ds,run));yes('repeat_keeps_archive',old==(run/'records.zip').read_bytes())
        reject('existing_destination',lambda:r.unpack_verified(run/'records.zip',run/'recovery-receipt.json',run/'recovered',h,ds))
        for variant in ('traversal','duplicate','link','case_alias','device_name'):
            bad=base/('zip-'+variant);bad.mkdir();archive=bad/'records.zip'
            with zipfile.ZipFile(run/'records.zip') as original,zipfile.ZipFile(archive,'x') as dest:
                for info in original.infolist():
                    data=original.read(info.filename)
                    if variant=='link' and info.filename=='stdout.txt':info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
                    dest.writestr(info,data)
                if variant=='traversal':dest.writestr('../outside',b'bad')
                if variant=='case_alias':dest.writestr('STDOUT.TXT',b'HOST_CLOSED')
                if variant=='device_name':dest.writestr('COM1',b'NEVER_EXTRACT')
                if variant=='duplicate':
                    with warnings.catch_warnings(record=True):dest.writestr('stdout.txt',b'HOST_CLOSED')
            value=copy.deepcopy(packet);value['archive_sha256']=r.sha(archive)
            if variant=='traversal':value['files_sha256']['../outside']=r.digest(b'bad')
            if variant=='case_alias':value['files_sha256']['STDOUT.TXT']=r.digest(b'HOST_CLOSED')
            if variant=='device_name':value['files_sha256']['COM1']=r.digest(b'NEVER_EXTRACT')
            reject('actual_zip_'+variant,lambda archive=archive,value=value:r.verify_archive(archive,value,h,ds))
        for name,change in {'receipt_acceptance':lambda x:x.update(native_acceptance=True),'receipt_reexecute':lambda x:x.update(native_reexecuted=True),'receipt_job':lambda x:x.update(job_sha256='d'*64),'receipt_driver':lambda x:x.update(driver_sha256='d'*64),'receipt_bool_code':lambda x:x.update(native_policy_exit_code=False),'receipt_archive_hash':lambda x:x.update(archive_sha256='0'*64),'receipt_extra':lambda x:x.update(extra=True),'receipt_kind':lambda x:x.update(kind='NATIVE_VERIFIED')}.items():
            value=copy.deepcopy(packet);change(value);reject(name,lambda value=value:r.verify_archive(run/'records.zip',value,h,ds))
        for partial,code,label in ((True,1,'timeout_partial'),(False,1,'native_failed')):
            rr,hh,dd,jj=fixture(base,partial,code);value=r.export_closed(rr,hh,dd,rr);yes(label+'_retained',value['native_policy_exit_code']==(124 if partial else 1) and value['native_acceptance'] is False)
        rr,hh,dd,jj=fixture(base);value=r.read(rr/'output/terminal.json');value.update(status='COMPLETE_PRE_CLOSE',phase='CLOSING_APP');put(rr/'output/terminal.json',value)
        yes('preclose_with_reaped_parent_supported',r.export_closed(rr,hh,dd,rr)['native_policy_exit_code']==0)
        for name,change in {'wrong_pid':lambda x:x.update(pid=203),'bool_pid':lambda x:x.update(pid=True),'wrong_job':lambda x:x.update(job_sha256='d'*64),'hardware_true':lambda x:x.update(hardware_approved=True),'bool_code':lambda x:x.update(code=False),'extra_inventory':lambda x:x['files_sha256'].update(extra='a'*64),
                'terminal_open_status':lambda x:x.update(status='RUNNING'),'terminal_missing_status':lambda x:x.pop('status'),
                'terminal_bad_phase':lambda x:x.update(phase='SDK_START'),'terminal_missing_phase':lambda x:x.pop('phase'),
                'terminal_zero_failed':lambda x:x.update(status='FAILED')}.items():
            rr,hh,dd,jj=fixture(base);value=r.read(rr/'output/terminal.json');change(value);put(rr/'output/terminal.json',value);reject(name,lambda rr=rr,hh=hh,dd=dd:r.export_closed(rr,hh,dd,rr))
        rr,hh,dd,jj=fixture(base);(rr/'output/report.json').write_bytes(b'TAMPER');reject('sealed_payload_tamper',lambda:r.export_closed(rr,hh,dd,rr))
        rr,hh,dd,jj=fixture(base);(rr/'input/source/driver.py').write_bytes(b'TAMPER');reject('source_tamper',lambda:r.export_closed(rr,hh,dd,rr))
        rr,hh,dd,jj=fixture(base);bad=b'raise AssertionError("UNREVIEWED_HELPER_EXECUTED")\n';(rr/'input/source/recovery.py').write_bytes(bad)
        jj['inputs']['source/recovery.py']=r.digest(bad);put(rr/'job.json',jj);hh=r.sha(rr/'job.json')
        reject('resealed_unreviewed_helper_rejected_before_exec',lambda:api.entry(str(rr),hh,dd,'export'))
        rr,hh,dd,jj=fixture(base,True);value=r.read(rr/'output/recovery-manifest.json');value['native_acceptance']=True;put(rr/'output/recovery-manifest.json',value);reject('partial_acceptance_reject',lambda:r.export_closed(rr,hh,dd,rr))
        for name,bad in (('partial_complete_status','COMPLETE'),('partial_missing_status',None)):
            rr,hh,dd,jj=fixture(base,True);value=r.read(rr/'output/recovery-manifest.json')
            if bad is None:value.pop('status')
            else:value['status']=bad
            put(rr/'output/recovery-manifest.json',value);reject(name,lambda rr=rr,hh=hh,dd=dd:r.export_closed(rr,hh,dd,rr))
        rr,hh,dd,jj=fixture(base);value=r.read(rr/'output/exit.json');value['child_state']='RUNNING';put(rr/'output/exit.json',value);reject('open_child_reject',lambda:r.export_closed(rr,hh,dd,rr))
        def mutant(text,name):
            obj=types.ModuleType(name);obj.__file__=str(Path(__file__).with_name('driver.py'));exec(compile(text,obj.__file__,'exec'),obj.__dict__);return obj
        changed=source['driver.py'].decode().replace("    if role=='export':","    if role=='export':\n        snapshot(run,job_hash,driver_sha)",1)
        m=mutant(changed,'old_dispatch_order');rr,hh,dd,jj=fixture(base)
        with patch.object(m,'snapshot',side_effect=ValueError('ORIGINAL_SNAPSHOT_FIRST')):reject('old_snapshot_order_detected',lambda:m.entry(str(rr),hh,dd,'export'))
        def caller(module,delay=130,copies=(5,5),native_code=0):
            rr,hh,dd,jj=fixture(base,False,native_code);r.export_closed(rr,hh,dd,rr);local=base/'local'/rr.name/rr.name;local.mkdir(parents=True);(local/'bundle.zip').write_bytes(b'HOST_BUNDLE')
            cc={**cfg,'deadline_unix':10000.};ctx=types.SimpleNamespace(run=local,cfg=cc,job=jj,job_hash=hh,data={'source/recovery.py':source['recovery.py']});prepared={'remote':cc['remote_root']+'/'+local.name,'bundle_sha256':module.sha(local/'bundle.zip')}
            now=[1000.];calls=[];remote_count=[0];copy_count=[0]
            def remote(script,alias,timeout=120):
                remote_count[0]+=1;i=remote_count[0];calls.append(('remote',i,timeout))
                if i==4:
                    if delay>timeout:now[0]+=timeout;raise subprocess.TimeoutExpired('SYNTHETIC_EXPORT',timeout)
                    now[0]+=delay
                return types.SimpleNamespace(returncode=native_code if i==3 else 0,stdout=b'HOST_ONLY',stderr=b'')
            def scp(argv,**kw):
                if argv[2].startswith('isaacpc:'):
                    i=copy_count[0];copy_count[0]+=1;duration=copies[i];calls.append(('copy',i,kw['timeout']))
                    if duration>kw['timeout']:now[0]+=kw['timeout'];raise subprocess.TimeoutExpired('SYNTHETIC_COPY',kw['timeout'])
                    now[0]+=duration;shutil.copyfile(rr/Path(argv[-1]).name,argv[-1])
                return types.SimpleNamespace(returncode=0)
            with patch.dict(module.launch.__globals__,{'remote':remote,'session_now':lambda cfg:now[0],'clock_probe':lambda ctx:None}),patch.object(module.subprocess,'run',side_effect=scp),patch.object(module.time,'time',side_effect=lambda:now[0]):
                try:module.launch(ctx,prepared);failed=False
                except module.RecoveryTransportError:failed=True
            return local,calls,failed,ctx
        local,calls,failed,ctx=caller(api);yes('actual_launch130s_success',not failed and calls[3]==('remote',4,300));yes('copy300_explicit',all(x[2]==300 for x in calls if x[0]=='copy'))
        yes('real_caller_verifies_receipt',r.read(local/'recovery-status.json')['status']=='CLOSED_ARTIFACT_COPY_VERIFIED_NOT_PHYSICS_ACCEPTANCE' and (local/'retrieved/report.json').exists())
        old=(local/'recovery-budget.json').read_bytes();reject('no_clock_reset',lambda:api.recover_transport(ctx,None,'unused','unused','unused'));yes('clock_retained',old==(local/'recovery-budget.json').read_bytes())
        local,calls,failed,ctx=caller(api,250,(250,150));yes('shared600_late_copy',failed and calls[-1][2]==100 and r.read(local/'recovery-budget.json')['deadline_unix']==1600)
        yes('recovery_failure_preserves_native0',r.read(local/'transport.json')=={'returncode':0,'timed_out':False} and r.read(local/'recovery-status.json')['status']=='RECOVERY_FAILED')
        local,calls,failed,ctx=caller(api,native_code=1);yes('native_failure_not_rewritten',not failed and r.read(local/'transport.json')['returncode']==1 and r.read(local/'recovery-receipt.json')['native_policy_exit_code']==1)
        changed=source['driver.py'].decode().replace("alias,recovery_timeout(ctx.cfg,end,session_now(ctx.cfg),mono_end,time.monotonic()))","alias,120)",1);m=mutant(changed,'old_timeout')
        local,calls,failed,ctx=caller(m);yes('old120_restoration_detected',failed and r.read(local/'recovery-status.json')['stage']=='EXPORT')
        # Exercise the actual public exception branch without allowing run/native.
        public_run=base/'runs'/uuid.uuid4().hex;public_run.mkdir(parents=True);jh='a'*64
        put(public_run/'prepared.json',{'run_id':public_run.name,'job_sha256':jh})
        put(public_run/'recovery-status.json',{'status':'RECOVERY_FAILED','native_transport':{'returncode':0,'timed_out':False}})
        context=types.SimpleNamespace(run=public_run,job_hash=jh,job={'purpose':'motion','inputs':{'source/'+n:r.digest(b) for n,b in source.items()}})
        with patch.dict(api.public.__globals__,{'OUT':base.relative_to(out.parents[1]).as_posix(),'snapshot':lambda *x:context,
                'consume':lambda *x:(_ for _ in ()).throw(api.RecoveryTransportError('HOST_EXPORT_FAILURE'))}):
            assert api.public('verify',str(public_run))==1
        value=r.read(public_run/'validation.json');yes('public_does_not_infer_SDK_not_started',value['status']=='RECOVERY_FAILED' and value['sdk_connected'] is None and value['native_execution']=='NOT_INFERRED_FROM_RECOVERY_FAILURE')
        put(public_run/'transport.json',{'returncode':0,'timed_out':False});put(public_run/'recovery-budget.json',{'started_unix':1000,'deadline_unix':1600})
        originals={n:(public_run/n).read_bytes() for n in ('validation.json','transport.json','recovery-status.json','recovery-budget.json')}
        with patch.dict(api.public.__globals__,{'OUT':base.relative_to(out.parents[1]).as_posix(),'snapshot':lambda *x:context}):
            assert api.public('verify',str(public_run))==1
            query=list(public_run.glob('validation-query-*.json'));v=r.read(query[0])
            yes('actual_missing_retrieved_requery_classification',len(query)==1 and v['status']=='RECOVERY_FAILED' and v['sdk_connected'] is None and v['initial_validation_sha256']==r.digest(originals['validation.json']))
            assert api.public('verify',str(public_run))==1
            yes('requeries_exclusive_primary_and_clock_unchanged',len(list(public_run.glob('validation-query-*.json')))==2 and all((public_run/n).read_bytes()==b for n,b in originals.items()))
            (public_run/'recovery-status.json').unlink()
            assert api.public('verify',str(public_run))==1
            newest=r.read(public_run/r.read(base/'current.json')['validation_file'])
            yes('requery_retains_known_primary_when_recovery_record_missing',newest['status']=='RECOVERY_FAILED' and newest['sdk_connected'] is None and (public_run/'validation.json').read_bytes()==originals['validation.json'])
        isolated=base/'runs'/uuid.uuid4().hex;isolated.mkdir();put(isolated/'prepared.json',{'run_id':isolated.name,'job_sha256':jh});unknown=types.SimpleNamespace(run=isolated,job_hash=jh,job=context.job)
        with patch.dict(api.public.__globals__,{'OUT':base.relative_to(out.parents[1]).as_posix(),'snapshot':lambda *x:unknown}):assert api.public('verify',str(isolated))==1
        v=r.read(isolated/'validation.json');yes('generic_local_failure_SDK_unknown',v['status']=='FAILED' and v['sdk_connected'] is None and v['native_execution']=='UNKNOWN_FROM_LOCAL_ERROR')
    assert len(tests)==89 and all(v is True for v in tests.values()),'Fixed recovery89 census'
    report={'status':'108_HOST_RECOVERY_PASS','count':len(tests),'tests':tests,'network':'NOT_RUN_SYNTHETIC_TRANSPORT','SDK':'NOT_RUN','native':'NOT_RUN','hardware_approved':False}
    (out/'recovery-host.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report));return 0
