if __name__=='__main__':raise SystemExit('Use launch.ps1')
import os
from pathlib import Path
import sys
import time

def run(c,s):
    out=c.run/'output'
    def phase(name):s.write(out/'native-phase.json',{'phase':name,'pid':os.getpid(),'observed_unix':time.time()})
    phase('SDK_BOOTSTRAP')
    k=s.load_module('frozen053',c.data['code/kernel.py'],c.run/'input/code/kernel.py')
    k.sdk_initialize(c.cfg)
    for name in ('scipy_root','numpy_root'):sys.path.insert(0,str(Path(c.cfg[name]).resolve().parent))
    k,api=s.frozen_api(c,sdk=True)
    def numeric(value):
        s.write(out/'numeric-checkpoint.json',value);k.check_numeric(value,c.cfg,s.need)
    def frameworks(value):
        s.write(out/'frameworks-checkpoint.json',value);k.check_frameworks(value,c.cfg)
    api['check_numeric']=numeric;api['check_frameworks']=frameworks
    def start(api):
        phase('SDK_NUMERIC');api['numeric_before']=api['lib']['providers'].numeric(api)
        phase('ISAACSIM_IMPORT')
        import isaacsim
        api['write'](out/'sdk.json',api['lib']['providers'].sdk_record(api,str(Path(isaacsim.__file__).resolve())),True)
        phase('SIMULATION_APP')
        return isaacsim.SimulationApp({'headless':True,'fast_shutdown':True})
    phase('NATIVE_COLLECTOR')
    return api['lib']['robot'].run(api,start=start)
