if __name__=='__main__':raise SystemExit('Use launch.ps1')
import concurrent.futures
import hashlib
import os
from pathlib import Path,PurePosixPath
import stat
import sys
import time

def inventory(root,need):
    root=Path(root);need(not root.is_symlink() and not root.is_junction(),'Prefix root link')
    files={};pending=[root]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for e in entries:
                info=e.stat(follow_symlinks=False)
                need(not e.is_symlink() and not getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024),'Prefix reparse/link')
                if e.is_dir(follow_symlinks=False):pending.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):files[Path(e.path).relative_to(root).as_posix()]=Path(e.path)
                else:need(False,'Unexpected prefix object')
    return files

def file_hash(path):
    h=hashlib.sha256();size=0;buf=bytearray(1<<20);view=memoryview(buf)
    with Path(path).open('rb') as f:
        before=os.fstat(f.fileno())
        while count:=f.readinto(buf):h.update(view[:count]);size+=count
        after=os.fstat(f.fileno())
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or size!=after.st_size:raise ValueError('File changed during audit')
    return h.hexdigest(),size

def run(c,s):
    started=time.monotonic();out=c.run/'output';seal=s.parse(c.data['prefix-seal.json']);need=s.need
    need(set(seal)=={'schema_version','files'} and seal['schema_version']==1,'Seal schema')
    for n,h in seal['files'].items():
        p=PurePosixPath(n);need(not p.is_absolute() and '\\' not in n and ':' not in n and all(x not in ('.','..') for x in n.split('/')) and len(h)==64,'Safe seal relative path')
    files=inventory(c.cfg['installation_prefix'],need);need(set(files)==set(seal['files']),'Exact full installation inventory')
    actual={};total=0;last=0.;it=iter(sorted(files))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending={}
        def submit():
            try:n=next(it)
            except StopIteration:return
            pending[pool.submit(file_hash,files[n])]=n
        for _ in range(4):submit()
        while pending:
            done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                n=pending.pop(future);h,size=future.result();need(h==seal['files'][n],'Installed file changed '+n);actual[n]=h;total+=size;submit()
            now=time.monotonic()
            if now-last>=1:
                s.write(out/'audit-progress.json',{'completed_files':len(actual),'expected_files':len(files),'bytes':total,'elapsed_s':now-started,'phase':'HASHING'});last=now
    modules=[n for n in sys.modules if n.split('.')[0] in ('numpy','scipy','isaacsim','carb','omni','pxr','warp','torch','isaaclab','isaaclab_physx')]
    need(actual==seal['files'] and not modules,'Complete SDK-free audit')
    s.write(out/'audit-report.json',{'run_id':c.run.name,'job_sha256':c.job_hash,'pid':os.getpid(),'status':'INSTALLATION_AUDITED',
        'input_signature':s.signature(c.job),'seal_sha256':s.digest(c.data['prefix-seal.json']),'file_count':len(actual),'bytes':total,
        'configured_workers':4,'configured_buffer_bytes_each':1<<20,'sdk_modules':modules,'finished_unix':time.time(),'duration_s':time.monotonic()-started})
    return 0
