if __name__=='__main__':raise SystemExit('Use launch.ps1')
import os
from pathlib import Path
import sys
import time

def run(c,s):
    out=c.run/'output'
    def phase(name):s.write(out/'native-phase.json',{'phase':name,'pid':os.getpid(),'observed_unix':time.time()})
    phase('SDK_BOOTSTRAP')
    k=s.load_module('frozen053',c.data['code/kernel.py'],c.run/'input/code/kernel.py');k.sdk_initialize(c.cfg)
    for name in ('scipy_root','numpy_root'):sys.path.insert(0,str(Path(c.cfg[name]).resolve().parent))
    k,api=s.frozen_api(c,sdk=True)
    p=s.load_module('observer',c.data['code/provider_observer.py'],c.run/'input/code/provider_observer.py')
    def numeric(value):s.write(out/'numeric-checkpoint.json',value);k.check_numeric(value,c.cfg,s.need)
    def frameworks(value):s.write(out/'frameworks-checkpoint.json',value);k.check_frameworks(value,c.cfg)
    api['check_numeric']=numeric;api['check_frameworks']=frameworks
    api['driver_observation']=p.driver(s);s.write(out/'driver.json',api['driver_observation'])
    def start(api):
        phase('SDK_NUMERIC');api['numeric_before']=api['lib']['providers'].numeric(api)
        if c.job['profile']=='PREFIX_TORCH_PREAPP':
            phase('PIN_PREFIX_TORCH');p.bind_preapp(c,s,k,api)
        api['binding_before']=p.identities();s.write(out/'binding-before.json',api['binding_before'])
        phase('ISAACSIM_IMPORT')
        import isaacsim
        api['write'](out/'sdk.json',api['lib']['providers'].sdk_record(api,str(Path(isaacsim.__file__).resolve())),True)
        phase('SIMULATION_APP')
        return isaacsim.SimulationApp({'headless':True,'fast_shutdown':True})
    if c.job['purpose']=='provider_diagnosis':
        app=None;code=1
        terminal={'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':'provider_diagnosis','pid':os.getpid(),'parent_pid':os.getppid(),'code':1,'status':'FAILED','phase':'DIAGNOSING','hardware_approved':False,'training':'NOT_RUN'}
        try:
            app=start(api)
            if c.cfg['installation_prefix'] not in sys.path:sys.path.append(c.cfg['installation_prefix'])
            phase('PROVIDER_DIAGNOSIS');observation=p.observe(c,s,'diagnosis')
            after=api['lib']['providers'].numeric(api)
            s.diagnostic_observation(observation)
            report={'run_id':c.run.name,'job_sha256':c.job_hash,'pid':os.getpid(),'status':'PROVIDER_DIAGNOSIS_COMPLETE','input_signature':s.signature(c.job),
                'observation':observation,'numeric_before':api['numeric_before'],'numeric_after':after,'driver':api['driver_observation'],'finished_unix':time.time(),'hardware_approved':False,'training':'NOT_RUN'}
            s.write(out/'diagnosis-report.json',report)
            terminal.update(code=0,status='DIAGNOSIS_COMPLETE_PRE_CLOSE',phase='CLOSING_APP',files_sha256={n:s.sha(out/n) for n in ('diagnosis-report.json','sdk.json')});code=0
        except Exception as exc:terminal['primary_error']=repr(exc)
        finally:
            s.write(out/'diagnostic-terminal.json',terminal)
            if app is not None:
                try:app.close(wait_for_replicator=False,exit_code=code)
                except Exception as exc:code=1;terminal.update(code=1,status='FAILED',close_error=repr(exc))
            s.write(out/'diagnostic-terminal.json',terminal)
        return code
    s.need(c.job['purpose']=='provider_connection','Closed native purpose')
    api['lib']['providers'].frameworks=lambda api:p.frameworks(c,s,k,api)
    original=api['lib']['robot'].collect
    def collect(api):
        original(api)
        after=p.identities();s.binding_contract(api['binding_before'],after,c.job['profile'],api['provider_observation'])
        value=api['read'](out/'providers.json')
        value.update(provider_observation=api['provider_observation'],selected_profile=c.job['profile'],binding_before=api['binding_before'],binding_after=after)
        s.write(out/'providers.json',value)
    phase('NATIVE_COLLECTOR')
    return api['lib']['robot'].run(api,start=start,collect_fn=collect)
