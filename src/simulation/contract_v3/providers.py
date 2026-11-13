if __name__ == '__main__':
    raise SystemExit('Use launch.ps1; direct execution is forbidden')

import importlib
import importlib.metadata
import math
import os
from pathlib import Path
import sys


def numeric(api):
    """Exercise SDK C extensions before any project learning prefix is visible."""
    cfg,need=api['cfg'],api['need']
    import numpy as np
    import numpy.fft._pocketfft_umath as fft_extension
    import scipy
    from scipy.spatial.transform import Rotation
    need(np.__version__=='2.3.1' and scipy.__version__=='1.17.0','SDK numerical versions')
    fft=np.fft.rfft(np.asarray([0.,1.,2.,3.]))
    rotation=Rotation.from_rotvec([0.,0.,0.]).as_matrix()
    result={'numpy_version':np.__version__,'scipy_version':scipy.__version__,
        'numpy_origin':str(Path(np.__file__).resolve()),'scipy_origin':str(Path(scipy.__file__).resolve()),
        'fft_extension':str(Path(fft_extension.__file__).resolve()),
        'fft':[[float(x.real),float(x.imag)] for x in fft],'rotation':rotation.tolist(),
        'loaded_numeric_modules':{n:str(Path(m.__file__).resolve()) for n,m in list(sys.modules.items())
            if (n=='numpy' or n.startswith('numpy.') or n=='scipy' or n.startswith('scipy.')) and getattr(m,'__file__',None)}}
    check_numeric(result,cfg,need)
    return result


def check_numeric(value,cfg,need):
    need(set(value)=={'numpy_version','scipy_version','numpy_origin','scipy_origin','fft_extension','fft','rotation','loaded_numeric_modules'},'Complete numerical provider contract')
    need(value['numpy_version']=='2.3.1' and value['scipy_version']=='1.17.0','Numerical provider versions')
    nr,sr=Path(cfg['numpy_root']),Path(cfg['scipy_root'])
    need(Path(value['numpy_origin']).is_relative_to(nr) and Path(value['fft_extension']).is_relative_to(nr) and Path(value['scipy_origin']).is_relative_to(sr),'Single SDK NumPy/SciPy roots')
    need(type(value['loaded_numeric_modules']) is dict and {'numpy','scipy','numpy.fft._pocketfft_umath'}<=set(value['loaded_numeric_modules']),'Actual loaded numerical module inventory')
    for name,path in value['loaded_numeric_modules'].items():
        need(name=='numpy' or name.startswith('numpy.') or name=='scipy' or name.startswith('scipy.'),'Closed numeric module namespace')
        need(Path(path).is_relative_to(nr if name.split('.')[0]=='numpy' else sr),'Mixed numerical provider '+name)
    for actual,expected in ((value['fft'],[[6,0],[-2,2],[-2,0]]),(value['rotation'],[[1,0,0],[0,1,0],[0,0,1]])):
        need(type(actual) is list and len(actual)==len(expected),'Numerical result shape')
        for a,e in zip(actual,expected):
            need(type(a) is list and len(a)==len(e),'Numerical row shape')
            need(all(type(x) in (int,float) and math.isfinite(x) and abs(x-y)<1e-9 for x,y in zip(a,e)),'Actual FFT/Rotation calculation')


def sdk_record(api,origin=None):
    cfg=api['cfg']
    return {'pid':os.getpid(),'job_sha256':api['sha'](api['run']/'job.json'),'version':cfg['isaac_version'],
            'isaacsim_origin':origin,'bootstrap_sha256':{k:api['sha'](v['path']) for k,v in cfg['sdk_files'].items()}}


def preflight(api):
    out=api['run']/'output';write=api['write'];code=1
    terminal={'run_id':api['run'].name,'job_sha256':api['sha'](api['run']/'job.json'),'stage':'sdk_preflight',
              'pid':os.getpid(),'parent_pid':os.getppid(),'code':1,'status':'FAILED','phase':'SDK_DLL_PROBE',
              'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN'}
    try:
        write(out/'providers.json',{'pid':os.getpid(),'job_sha256':terminal['job_sha256'],'numeric':numeric(api)},True)
        write(out/'sdk.json',sdk_record(api),True)
        terminal.update(code=0,status='PREFLIGHT_COMPLETE',phase='SDK_DLL_PROBE_FINISHED',
            files_sha256={n:api['sha'](out/n) for n in ('providers.json','sdk.json')})
        code=0
    except Exception as exc:
        terminal['primary_error']=repr(exc)
    write(out/'terminal.json',terminal,True)
    return code


def create_app(api):
    # No learning prefix has been exposed at this point.
    api['numeric_before']=numeric(api)
    import isaacsim
    origin=str(Path(isaacsim.__file__).resolve())
    api['need'](Path(origin).is_relative_to(Path(api['cfg']['isaac_root'])),'SDK isaacsim provider')
    api['write'](api['run']/'output/sdk.json',sdk_record(api,origin),True)
    return isaacsim.SimulationApp({'headless':True,'fast_shutdown':True})


def frameworks(api):
    cfg,need=api['cfg'],api['need'];prefix=Path(cfg['installation_prefix']).resolve()
    # SDK and its numerical modules are initialized; append, never prepend.
    sys.path.append(str(prefix))
    result={}
    for name,dist,version in [('isaaclab','isaaclab','3.0.0'),('torch','torch','2.11.0+cu130'),
                              ('warp','warp-lang','1.17.0'),('gymnasium','gymnasium','1.4.0'),('rsl_rl','rsl-rl-lib','5.5.1')]:
        m=importlib.import_module(name);origin=Path(m.__file__).resolve()
        v=str(m.__version__) if name=='warp' else importlib.metadata.version(dist)
        allowed=Path(cfg['warp_root']).resolve() if name=='warp' else prefix
        need(origin.is_relative_to(allowed) and v==version,'Framework provider '+name)
        result[name]={'origin':str(origin),'version':v}
    import torch
    need(torch.cuda.is_available() and torch.version.cuda.startswith('13.'),'Actual CUDA13')
    x=torch.ones((2,3),device='cuda:0');total=float(x.sum().item())
    need(x.is_cuda and total==6.,'Actual GPU calculation')
    return {'modules':result,'cuda':torch.version.cuda,'device':str(x.device),'sum':total}
