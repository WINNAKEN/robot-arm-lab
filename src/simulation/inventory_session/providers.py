if __name__=='__main__':raise SystemExit('Use launch.ps1')
import importlib
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys

NAMES={'torch':'torch','torchvision':'torchvision','isaaclab':'isaaclab','warp':'warp-lang','gymnasium':'gymnasium','rsl_rl':'rsl-rl-lib','numpy':'numpy','scipy':'scipy'}
BINDINGS=('numpy','scipy','warp','torch','torchvision')

def module_info(name,m):
    value={'status':'OBSERVED','origin':str(getattr(m,'__file__','')),'module_id':id(m),'version':None,
        'distribution_version':None,'distribution_root':None}
    try:
        dist=importlib.metadata.distribution(NAMES[name]);value.update(distribution_version=dist.version,distribution_root=str(dist.locate_file('')))
    except Exception as exc:value['metadata_error']=repr(exc)
    value['version']=str(m.__version__) if getattr(m,'__version__',None) is not None else value['distribution_version']
    return value

def torch_inventory():
    # One object snapshot; no re-import, guessed absolute path or producer-selected kind.
    objects={n:m for n,m in list(sys.modules.items()) if (n=='torch' or n.startswith('torch.')) and m is not None}
    files,rows,fileless={},{},{}
    for name,m in objects.items():
        reported=getattr(m,'__file__',None)
        if not reported:
            fileless[name]=id(m);continue
        if type(reported) is not str:raise ValueError('Non-string reported Torch file')
        cls=type(m);definition=objects.get(cls.__module__)
        spec=vars(m).get('__spec__');loader=getattr(spec,'loader',None) if spec is not None else vars(m).get('__loader__')
        rows[name]={'module_id':id(m),'reported_file':reported,'spec_origin':getattr(spec,'origin',None),
            'loader_module':type(loader).__module__ if loader is not None else None,
            'loader_qualname':type(loader).__qualname__ if loader is not None else None,
            'type_module':cls.__module__,'type_qualname':cls.__qualname__,
            'type_definition_origin':getattr(definition,'__file__',None) if definition is not None else None,
            'type_definition_module_id':id(definition) if definition is not None else None,
            'type_is_definition':definition is not None and vars(definition).get(cls.__name__) is cls}
        files[name]=reported
    return {'loaded_torch_modules':files,'torch_inventory':rows,'fileless_torch_modules':fileless,
        'torch_module_count':len(objects),'inventory_scope':'FILE_REPORTED_TORCH_MODULES'}

def observe_torch(c,s,tag,tm=None):
    if tm is None:tm=importlib.import_module('torch')
    out=c.run/'output';path=out/('torch-'+tag+'.json')
    value={'origin':str(getattr(tm,'__file__','')),'module_version':str(getattr(tm,'__version__','')),
        'module_id':id(tm),'cuda_build':getattr(getattr(tm,'version',None),'cuda',None),
        'version_origin':str(getattr(getattr(tm,'version',None),'__file__','')),'c_extension_origin':str(getattr(getattr(tm,'_C',None),'__file__','')),
        'availability':None,'availability_error':None,'gpu':None,'gpu_error':None,'state':'BEFORE_AVAILABILITY'}
    s.write(path,value)
    try:value['availability']=bool(tm.cuda.is_available())
    except Exception as exc:value['availability_error']=repr(exc)
    value['state']='AFTER_AVAILABILITY';s.write(path,value)
    if value['availability']:
        try:
            value['device_count']=int(tm.cuda.device_count());value['device_name']=str(tm.cuda.get_device_name(0));value['capability']=list(tm.cuda.get_device_capability(0))
        except Exception as exc:value['device_details_error']=repr(exc)
        s.write(path,value)
        try:
            x=tm.ones((2,3),device='cuda:0')
            value['gpu']={'is_cuda':bool(x.is_cuda),'device':str(x.device),'sum':float(x.sum().item())}
        except Exception as exc:value['gpu_error']=repr(exc)
    value.update(torch_inventory())
    value['state']='OBSERVED';s.write(path,value)
    return value

def observe(c,s,tag):
    value={'modules':{},'torch':None,'sys_path':list(sys.path)}
    path=c.run/'output'/('provider-'+tag+'.json')
    for name in NAMES:
        try:
            m=importlib.import_module(name);value['modules'][name]=module_info(name,m);s.write(path,value)
            if name=='torch':value['torch']=observe_torch(c,s,tag+'-initial',m)
        except Exception as exc:value['modules'][name]={'status':'IMPORT_ERROR','error':repr(exc)}
        s.write(path,value)
    if value['torch'] is not None:value['torch']=observe_torch(c,s,tag+'-final')
    value['sys_path']=list(sys.path);s.write(path,value)
    return value

def identities():return {n:id(sys.modules[n]) if n in sys.modules else None for n in BINDINGS}

def driver(s):
    exe=shutil.which('nvidia-smi')
    if not exe:return {'status':'UNAVAILABLE'}
    try:
        p=subprocess.run([exe,'--query-gpu=driver_version,name,memory.total','--format=csv,noheader,nounits'],capture_output=True,timeout=10,creationflags=s.HIDDEN)
        return {'status':'OBSERVED' if p.returncode==0 else 'FAILED','returncode':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}
    except Exception as exc:return {'status':'ERROR','error':repr(exc)}

def bind_preapp(c,s,k,api):
    # NumPy/SciPy are already initialized from the SDK. Keep SDK Warp before prefix exposure.
    sys.path.insert(0,str(Path(c.cfg['warp_root']).parent))
    warp=importlib.import_module('warp');s.need(k.owned_origin(warp.__file__,c.cfg['warp_root']) and str(warp.__version__)=='1.17.0','Pinned SDK Warp before app')
    sys.path.insert(0,c.cfg['installation_prefix'])
    for name in ('torch','torchvision'):
        m=importlib.import_module(name);s.write(c.run/'output'/('bound-'+name+'.json'),module_info(name,m))
    value=observe_torch(c,s,'bound-preapp')
    s.require_torch(value,c.cfg)
    tv=module_info('torchvision',sys.modules['torchvision'])
    s.need(k.owned_origin(tv['origin'],c.cfg['installation_prefix']) and tv['version']=='0.26.0+cu130','Pinned Torchvision before app')
    api['lib']['providers'].numeric(api)

def frameworks(c,s,k,api):
    if c.cfg['installation_prefix'] not in sys.path:sys.path.append(c.cfg['installation_prefix'])
    observation=observe(c,s,'connected')
    # Every observation above is written before any provider/CUDA acceptance predicate.
    s.require_observation(observation,c.cfg)
    t=observation['torch'];gpu=t['gpu']
    result={'modules':{n:{'origin':observation['modules'][n]['origin'],'version':observation['modules'][n]['version']} for n in NAMES if n not in ('torchvision','numpy','scipy')},
        'cuda':t['cuda_build'],'device':gpu['device'],'sum':gpu['sum']}
    api['provider_observation']=observation
    api['check_frameworks'](result)
    return result
