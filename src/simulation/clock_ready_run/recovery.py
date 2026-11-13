"""Closed artifact copying only. No SDK, geometry, physics, network, or subprocess imports."""
from pathlib import Path,PurePosixPath,PureWindowsPath
import hashlib,json,math,re,stat,zipfile

UNSEALED={'terminal.json','status.json','stdout.txt','stderr.txt','exit.json','remote-shell.json','child-started.json','recovery-manifest.json'}
RECEIPT_KEYS={'schema_version','kind','run_id','job_sha256','driver_sha256','purpose','files_sha256','archive_name','archive_sha256',
              'seal_sha256','native_policy_exit_code','native_acceptance','native_reexecuted','hardware_approved'}

def need(value,reason):
    if not value:raise ValueError(reason)

def digest(raw):return hashlib.sha256(raw).hexdigest()
def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()
def pin(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None
def component(name):
    return bool(name) and name not in ('.','..') and not name.endswith((' ','.')) and not any(ord(x)<32 for x in name) and not PureWindowsPath(name).is_reserved()
def relative(name):
    return type(name) is str and bool(name) and '\\' not in name and ':' not in name and not name.startswith('/') and all(component(x) for x in name.split('/')) and str(PurePosixPath(name))==name
def safe(path):
    path=Path(path);need(path.is_absolute(),'Absolute recovery path')
    # String-only device/normalization rejection precedes every filesystem query.
    for part in (path,*path.parents):
        if part.name:need(component(part.name),'No reserved/normalized Windows recovery component')
    for part in (path,*path.parents):need(not part.is_symlink() and not part.is_junction(),'No recovery links')
    return path
def parse(raw):
    def pairs(rows):
        obj={}
        for key,value in rows:need(key not in obj,'Duplicate JSON key');obj[key]=value
        return obj
    def number(text):
        value=float(text);need(math.isfinite(value),'Finite JSON');return value
    def constant(text):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_float=number,parse_constant=constant)
def read(path):return parse(path.read_bytes().decode('utf-8-sig'))
def mapping(value):return type(value) is dict and all(relative(n) and pin(h) for n,h in value.items())
def inventory(folder):
    folder=safe(folder);need(folder.is_dir(),'Existing recovery directory');result={}
    for path in folder.rglob('*'):
        safe(path)
        if path.is_file():
            name=path.relative_to(folder).as_posix();need(relative(name),'Safe output name');result[name]=sha(path)
    need(len({name.casefold() for name in result})==len(result),'No Windows case aliases')
    return result
def integer(value,minimum=0,maximum=255):return type(value) is int and minimum<=value<=maximum

def identity(row,run_id,job_hash,purpose):
    need(type(row) is dict and row.get('run_id')==run_id and row.get('job_sha256')==job_hash,'Closed output identity')
    if 'purpose' in row:need(row['purpose']==purpose,'Closed output purpose')

def verify_output(run_id,job_hash,purpose,files,get):
    need(mapping(files) and {'exit.json','remote-shell.json','stdout.txt','stderr.txt'}<=set(files),'Original process files')
    ex,shell=parse(get('exit.json')),parse(get('remote-shell.json'))
    for row in (ex,shell):identity(row,run_id,job_hash,purpose)
    need(ex.get('purpose')==purpose and integer(ex.get('pid'),1,2**32-1),'Recorded parent PID')
    need(type(ex.get('timed_out')) is bool and integer(ex.get('policy_exit_code')) and integer(shell.get('python_exit_code'))
         and ex['policy_exit_code']==shell['python_exit_code'],'Typed original policy/shell result')
    if ex.get('child_state')=='REAPED':
        need(integer(ex.get('child_pid'),1,2**32-1) and integer(ex.get('actual_child_exit_code')),'Reaped child PID/result')
    else:
        need(ex.get('child_state')=='NOT_STARTED' and ex.get('child_pid') is None and ex.get('actual_child_exit_code') is None,'No open native process state')
    if 'recovery-manifest.json' in files:
        packet=parse(get('recovery-manifest.json'));identity(packet,run_id,job_hash,purpose)
        need(set(packet)=={'kind','status','native_acceptance','run_id','job_sha256','purpose','exit','files_sha256','native_reexecuted'}
             and packet.get('status')=='FAILED','Exact failed parent lifecycle marker/schema')
        need(packet.get('kind')=='FAILED_PARENT_RECOVERY_SNAPSHOT_NOT_NATIVE_TERMINAL' and packet.get('native_acceptance') is False
             and packet.get('native_reexecuted') is False and packet.get('exit')==ex and ex['policy_exit_code']!=0,'Failed parent snapshot semantics')
        pins=packet.get('files_sha256');need(mapping(pins) and set(pins)==set(files)-{'recovery-manifest.json','remote-shell.json'},'Exact failed snapshot inventory')
        need(all(files[n]==h for n,h in pins.items()),'Original failed snapshot hashes')
    if 'terminal.json' in files:
        terminal=parse(get('terminal.json'));identity(terminal,run_id,job_hash,purpose)
        need(terminal.get('purpose')==purpose and terminal.get('hardware_approved') is False and terminal.get('physical_calibration') is False
             and terminal.get('training')=='NOT_RUN','Native simulation-only terminal')
        status=terminal.get('status');phase=terminal.get('phase')
        need(type(status) is str and type(phase) is str and phase,'Typed native lifecycle status/phase')
        need((status=='CLOSED' and phase=='APP_CLOSED') or (status=='COMPLETE_PRE_CLOSE' and phase=='CLOSING_APP')
             or (status=='FAILED' and integer(terminal.get('code'),1)),'Supported closed/failed native lifecycle')
        need(ex['child_state']=='REAPED' and ex['timed_out'] is False and integer(terminal.get('code'))
             and terminal['code']==ex['actual_child_exit_code']==ex['policy_exit_code'],'Native terminal/parent/shell result binding')
        need(terminal.get('pid')==ex['child_pid'] and terminal.get('parent_pid')==ex['pid']
             and type(terminal.get('pid')) is int and type(terminal.get('parent_pid')) is int,'Native direct PID binding')
        pins=terminal.get('files_sha256');need(mapping(pins) and set(pins)==set(files)-UNSEALED,'Exact native sealed inventory')
        need(all(files[n]==h for n,h in pins.items()),'All original native sealed hashes')
        return 'CLOSED_NATIVE_ARTIFACT_COPY',files['terminal.json'],ex['policy_exit_code']
    need('recovery-manifest.json' in files,'Closed terminal or failed parent snapshot required')
    return 'FAILED_PARENT_SNAPSHOT_COPY',files['recovery-manifest.json'],ex['policy_exit_code']

def verify_closed(run,job_hash,driver_sha,output_name='output'):
    run=safe(run);need(pin(job_hash) and pin(driver_sha) and re.fullmatch('[0-9a-f]{32}',run.name),'Trusted closed run/hash')
    need(output_name in ('output','retrieved'),'Closed output location')
    job=read(safe(run/'job.json'));need(sha(run/'job.json')==job_hash,'Original job hash')
    need(type(job) is dict and set(job)=={'schema_version','run_id','purpose','inputs','common_signature','plan_sha256','hardware_approved','experiment_id'}
         and type(job['schema_version']) is int and job['schema_version']==1 and job['run_id']==run.name
         and job['purpose'] in ('import','render_smoke','motion') and job['hardware_approved'] is False
         and pin(job['plan_sha256']) and pin(job['common_signature']) and type(job['experiment_id']) is str,'Typed closed source job')
    inputs=job['inputs'];need(mapping(inputs) and inputs==inventory(run/'input'),'All original input bytes without semantic imports')
    need(inputs.get('source/driver.py')==driver_sha and 'source/config.json' in inputs,'Trusted executable/config pins')
    cfg=read(run/'input/source/config.json')
    need(cfg.get('hardware_approved') is False and cfg.get('physical_calibration') is False and cfg.get('training')=='NOT_RUN'
         and type(cfg.get('sdk')) is dict and cfg['sdk'].get('hardware_approved') is False and cfg['sdk'].get('calibration_approved') is False,'Closed simulation-only config')
    folder=safe(run/output_name);files=inventory(folder)
    kind,seal,code=verify_output(run.name,job_hash,job['purpose'],files,lambda n:(folder/n).read_bytes())
    return {'job':job,'folder':folder,'files':files,'kind':kind,'seal':seal,'code':code}

def export_closed(run,job_hash,driver_sha,archive_dir,output_name='output'):
    closed=verify_closed(run,job_hash,driver_sha,output_name);folder=closed['folder'];dest=safe(archive_dir)
    need(dest.is_dir(),'Existing owned archive directory')
    archive=safe(dest/'records.zip');receipt=safe(dest/'recovery-receipt.json')
    need(not archive.exists() and not receipt.exists(),'No recovery overwrite or automatic retry')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as stream:
        for name in sorted(closed['files']):stream.write(safe(folder/name),name)
    need(inventory(folder)==closed['files'],'Original output unchanged during copy')
    value={'schema_version':1,'kind':closed['kind'],'run_id':Path(run).name,'job_sha256':job_hash,'driver_sha256':driver_sha,
           'purpose':closed['job']['purpose'],'files_sha256':closed['files'],'archive_name':'records.zip','archive_sha256':sha(archive),
           'seal_sha256':closed['seal'],'native_policy_exit_code':closed['code'],'native_acceptance':False,'native_reexecuted':False,'hardware_approved':False}
    # Verify the bytes actually archived before publishing the exclusive receipt.
    verify_archive(archive,value,job_hash,driver_sha)
    with receipt.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
    return value

def verify_archive(archive,receipt,job_hash,driver_sha):
    archive=safe(archive);packet=read(safe(receipt)) if isinstance(receipt,Path) else receipt
    need(type(packet) is dict and set(packet)==RECEIPT_KEYS and type(packet['schema_version']) is int and packet['schema_version']==1,'Closed recovery receipt')
    need(packet['job_sha256']==job_hash and packet['driver_sha256']==driver_sha and pin(job_hash) and pin(driver_sha)
         and type(packet['run_id']) is str and re.fullmatch('[0-9a-f]{32}',packet['run_id']) and packet['purpose'] in ('import','render_smoke','motion'),'Recovery identity binding')
    need(packet['native_acceptance'] is False and packet['native_reexecuted'] is False and packet['hardware_approved'] is False,'Copy cannot grant acceptance or execute native')
    need(packet['archive_name']==archive.name=='records.zip' and pin(packet['archive_sha256']) and sha(archive)==packet['archive_sha256'],'Exact recovery archive hash/name')
    pins=packet['files_sha256'];need(mapping(pins) and pins,'Typed archive inventory')
    with zipfile.ZipFile(archive) as stream:
        names=stream.namelist();need(len(names)==len(set(names)) and len({n.casefold() for n in names})==len(names)
             and set(names)==set(pins) and all(relative(n) for n in names),'Unique safe exact ZIP inventory')
        for info in stream.infolist():
            need(not info.is_dir() and stat.S_IFMT(info.external_attr>>16)!=stat.S_IFLNK,'No archive links/directories')
            value=hashlib.sha256()
            with stream.open(info) as data:
                for block in iter(lambda:data.read(1024*1024),b''):value.update(block)
            need(value.hexdigest()==pins[info.filename],'Each written archive member hash/CRC')
        kind,seal,code=verify_output(packet['run_id'],job_hash,packet['purpose'],pins,stream.read)
    need((packet['kind'],packet['seal_sha256'],packet['native_policy_exit_code'])==(kind,seal,code)
         and type(packet['native_policy_exit_code']) is int,'Receipt bound to original process seal/result')
    return packet

def unpack_verified(archive,receipt,destination,job_hash,driver_sha):
    packet=verify_archive(Path(archive),Path(receipt),job_hash,driver_sha);dest=safe(destination)
    need(not dest.exists(),'Never overwrite original/recovered evidence');dest.mkdir()
    with zipfile.ZipFile(archive) as stream:
        for name in stream.namelist():
            path=safe(dest/name);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as data:data.write(stream.read(name))
    need(inventory(dest)==packet['files_sha256'],'Extracted original bytes verified')
    return packet
