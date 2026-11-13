"""120 explicit PowerShell binary Process proxy. Original119 invocation remains retired."""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT/'outputs/mp18-shell-entry-120'
OLD = ROOT/'outputs/mp18-isaac-119'
OLD_FREEZE = 'bad965dbc91fd5e5a076ddd41ef67d685e062cb2d9be2bd6fd4d85c35b562b6e'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path = Path(path)
    need(path.resolve().is_relative_to(OUT.resolve()), 'Only120 output')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False, indent=2)+'\n', encoding='utf8')


def legacy():
    freeze_path = OLD/'review/source-freeze-r2.json'
    need(sha(freeze_path) == OLD_FREEZE, 'Original119 reviewed freeze')
    freeze = read(freeze_path)
    for n in ('driver.py', 'contract.py'):
        path = ROOT/'src/simulation/mp18_isaac_119'/n
        need(sha(path) == freeze['files'][path.relative_to(ROOT).as_posix()]['sha256'], 'Pre-import original reference pin')
    path = ROOT/'src/simulation/mp18_isaac_119/driver.py'
    spec = importlib.util.spec_from_file_location('frozen119_for120', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ps_literal(value):
    need(type(value) is str and '\0' not in value, 'Closed PowerShell literal')
    return "'"+value.replace("'", "''")+"'"


def proxy_command(executable, code, remaining):
    """No PS native-command pipeline: all three child pipes use raw .NET BaseStreams."""
    need(Path(executable).is_absolute() and str(executable).lower().endswith('.exe'), 'Absolute Python executable')
    need(type(code) is str and type(remaining) in (int,float) and math.isfinite(remaining) and remaining > 20,
         'Finite proxy duration')
    arguments = subprocess.list2cmdline(['-I', '-B', '-c', code])
    script = r'''
$ErrorActionPreference='Stop'
$clock=[Diagnostics.Stopwatch]::StartNew()
$limit=LIMIT_SECONDS
function LeftMilliseconds { return [int][Math]::Max(0,[Math]::Floor(($limit-$clock.Elapsed.TotalSeconds)*1000)) }
$workLimit=[Math]::Max(0,$limit-2)
$p=New-Object Diagnostics.Process
$psi=New-Object Diagnostics.ProcessStartInfo
$psi.FileName=PYTHON_LITERAL
$psi.Arguments=ARGUMENT_LITERAL
$psi.UseShellExecute=$false
$psi.CreateNoWindow=$true
$psi.RedirectStandardInput=$true
$psi.RedirectStandardOutput=$true
$psi.RedirectStandardError=$true
$p.StartInfo=$psi
$started=$false
try {
  [void]$p.Start(); $started=$true
  $ti=[Console]::OpenStandardInput().CopyToAsync($p.StandardInput.BaseStream)
  $to=$p.StandardOutput.BaseStream.CopyToAsync([Console]::OpenStandardOutput())
  $te=$p.StandardError.BaseStream.CopyToAsync([Console]::OpenStandardError())
  $closed=$false
  while(-not $p.HasExited) {
    if($clock.Elapsed.TotalSeconds -ge $workLimit) {
      $p.Kill(); [void]$p.WaitForExit([Math]::Min(2000,(LeftMilliseconds))); exit 124
    }
    if($ti.IsCompleted -and -not $closed) {
      [void]$ti.GetAwaiter().GetResult(); $p.StandardInput.Close(); $closed=$true
    }
    [void]$p.WaitForExit(10)
  }
  $ms=LeftMilliseconds
  $tasks=[Threading.Tasks.Task[]]@($to,$te)
  if(-not [Threading.Tasks.Task]::WaitAll($tasks,$ms)) { exit 124 }
  [void]$to.GetAwaiter().GetResult(); [void]$te.GetAwaiter().GetResult()
  exit $p.ExitCode
} catch {
  $message=[Text.Encoding]::UTF8.GetBytes($_.Exception.ToString())
  try {
    if($started -and -not $p.HasExited) { $p.Kill(); [void]$p.WaitForExit([Math]::Min(2000,(LeftMilliseconds))) }
  } catch { }
  if((LeftMilliseconds) -gt 0) {
    $log=[Console]::OpenStandardError().WriteAsync($message,0,$message.Length)
    [void]$log.Wait((LeftMilliseconds))
  }
  exit 125
} finally { $p.Dispose() }
'''
    script = script.replace('LIMIT_SECONDS', repr(float(remaining-20))).replace('PYTHON_LITERAL', ps_literal(str(executable))).replace('ARGUMENT_LITERAL', ps_literal(arguments))
    encoded = base64.b64encode(script.encode('utf-16le')).decode()
    command = "& ([ScriptBlock]::Create([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+encoded+"'))))"
    need(len(command) < 30000, 'Bounded Windows command line')
    return command


def gates(D):
    freeze_path = OUT/'review/source-freeze.json'
    freeze = read(freeze_path)
    for name, r in freeze['files'].items():
        need(sha(D.C.path_in(ROOT,name)) == r['sha256'], '120 reviewed source drift')
    for who in ('main','lens'):
        report = read(OUT/('review/'+who+'-L4-final.json'))
        need(report['verdict'] == 'PASS' and report['unmet'] == 0 and report['source_freeze_sha256'] == sha(freeze_path), '120 final source acceptance')
    D._review_gate()


def prior_admission(D):
    record = D.read(OLD/'prepared.json')
    run = OLD/'runs'/record['run_id']
    D.verified_payload(run, record)
    original = D.read(OLD/'native-attempt.json')
    child = D.read(run/'transport.json')
    stdout, stderr = (run/'stdout.txt').read_bytes(), (run/'stderr.txt').read_bytes()
    error = stderr.decode('utf8','replace')
    need(original['run_id'] == record['run_id'] and original['SDK_attempts'] == 1 and original['retry'] == 0,
         'Original reservation identity')
    need(original['started_monotonic'] == 377051.359 and original['global_deadline_monotonic'] == 379751.359,
         'Original immutable end')
    need(stdout == b'' and child['actual_child_exit_code'] == 1 and child['job_active_after'] == 0 and
         child['child_state'] == 'UNKNOWN' and child['raw_complete'] is False and child['terminal'] is False and
         child['errors'] == ['work: ValueError: READY within bounded handshake'] and
         all(s in error for s in ('ParserError','UnexpectedToken','-I','-B','python.exe')), 'Exact original pre-Python parse failure only')
    need(not (run/'retrieved').exists() and not (OUT/'admission.json').exists(), 'First actual SDK grant only')
    return record, run, original


def run():
    D = legacy()
    gates(D)
    record, run_path, original = prior_admission(D)
    deadline = original['global_deadline_monotonic']
    start = time.monotonic()
    remaining = deadline-start
    need(remaining > 1222, 'Original global headroom for native plus recovery')
    cfg = D.read(D.HERE/'config.json')
    args = dict(record, remote_root=cfg['remote_root'], remaining=remaining)
    command = proxy_command(str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe'), D.bootstrap_code(args), remaining)
    transport = OUT/'transport'
    transport.mkdir(exist_ok=False)
    write(OUT/'admission.json', {'unit':120,'run_id':record['run_id'],'original_deadline_monotonic':deadline,
        'started_monotonic':start,'remaining_s':remaining,'SSH_cumulative_launches':2,'actual_prior_SDK':0,
        'SDK_grants_max':1,'SDK_retry':0,'original_state_retained':'UNKNOWN_RAW_FALSE_TERMINAL_FALSE',
        'original_marker_sha256':sha(OLD/'native-attempt.json'),'original_transport_sha256':sha(run_path/'transport.json')})
    raw_helper = D.C.path_in(ROOT,cfg['refs']['winjob.py']['path']).read_bytes()
    need(hashlib.sha256(raw_helper).hexdigest() == cfg['refs']['winjob.py']['sha256'], 'Immutable actual Windows Job helper')
    helper = D.load_module('local_job120', raw_helper, ROOT/cfg['refs']['winjob.py']['path'])
    ssh = Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe'
    argv = [str(ssh),'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],command]
    def sender(stream, stdout_path, end):
        ready = None
        while time.monotonic() < min(start+20,end):
            raw = stdout_path.read_bytes()
            if b'\n' in raw:
                ready = D.parse(raw.split(b'\n',1)[0]); break
            time.sleep(.01)
        expected = {n:args[n] for n in ('nonce','run_id','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
        need(ready is not None and time.monotonic() < start+20 and set(ready) == set(expected)|{'kind','remote_ready'} and
             ready['kind']=='READY' and {n:ready[n] for n in expected} == expected and
             type(ready['remote_ready']) in (float,int) and math.isfinite(ready['remote_ready']), '120 bounded original READY')
        write(OUT/'GO.json', {'run_id':record['run_id'],'old_deadline':deadline,'sent_monotonic':time.monotonic(),'GO_count':1,'hardware_approved':False})
        stream.write(json.dumps(dict(expected,kind='GO')).encode()+b'\n')
        with (run_path/'bundle.zip').open('rb') as payload:
            for block in iter(lambda:payload.read(1024*1024),b''):
                need(time.monotonic()<end,'120 upload within old end'); stream.write(block)
        stream.flush()
    process = helper.run(argv,transport,deadline-time.monotonic()-2,cleanup_s=2,input_sender=sender)
    write(OUT/'transport.json',process)
    need(process['raw_complete'] and process['terminal'] and process['child_state']=='REAPED' and
         process['job_active_after']==0 and not process['timed_out'] and process['actual_child_exit_code']==0, '120 byte proxy did not complete')
    raw = (transport/'stdout.txt').read_bytes()
    _, rest = raw.split(b'\n',1)
    header_raw, archive = rest.split(b'\n',1)
    header = D.parse(header_raw)
    need(header['kind']=='RESULT' and header['run_id']==record['run_id'] and header['nonce']==record['nonce'] and
         len(archive)==header['bytes'] and hashlib.sha256(archive).hexdigest()==header['sha256'], 'Original raw RESULT bytes')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist()
        need(len(infos)==len({i.filename.casefold() for i in infos}) and sum(i.file_size for i in infos)<2*1024**3,'Bounded original result inventory')
        for i in infos:
            D._safe_name(i.filename)
            need(not i.is_dir() and (i.external_attr>>16)&0o170000!=0o120000,'No result links')
        destination=run_path/'retrieved'
        destination.mkdir(exist_ok=False)
        (run_path/'retrieved.zip').write_bytes(archive)
        for i in infos:
            p=D.C.path_in(destination,i.filename);p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(z.read(i))
    result=D.verify_native_result(run_path,record,destination)
    write(OUT/'result.json',{'unit':120,'run_id':record['run_id'],'native_consumer_exit':result,
        'old_deadline':deadline,'finished_monotonic':time.monotonic(),'SSH_launches':2,'original_failed_state_preserved':True,
        'actual_SDK_max':1,'SDK_retry':0,'hardware_approved':False})
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('run',))
    parser.parse_args();raise SystemExit(run())
