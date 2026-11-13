"""Actual local PowerShell byte proxy HOST fixtures. No SSH or SDK."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid
import zipfile

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('entry120',HERE/'driver.py')
M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
PS=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
EXE=sys._base_executable


def execute(code, data=b'', remaining=30.):
    command=M.proxy_command(EXE,code,remaining)
    started=time.monotonic()
    p=subprocess.run([str(PS),'-NoLogo','-NoProfile','-NonInteractive','-Command',command],input=data,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    return p,time.monotonic()-started


class ProxyTests(unittest.TestCase):
    def test_01_original_quoted_command_is_actual_parser_failure(self):
        old='"'+EXE+'" -I -B -c "print(123)"'
        p=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-Command',old],stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        self.assertNotEqual(p.returncode,0);self.assertEqual(p.stdout,b'')
        self.assertIn(b'UnexpectedToken',p.stderr)

    def test_02_all256_bytes_duplex_and_stderr_exit(self):
        data=bytes(range(256))*1024
        code="import sys;d=sys.stdin.buffer.read();sys.stdout.buffer.write(d);sys.stdout.buffer.flush();sys.stderr.buffer.write(d[::-1]);sys.stderr.buffer.flush();raise SystemExit(37)"
        p,elapsed=execute(code,data)
        self.assertEqual(p.returncode,37,p.stderr[-300:])
        self.assertEqual(p.stdout,data)
        self.assertTrue(p.stderr.endswith(data[::-1]))
        prefix=p.stderr[:-len(data)]
        baseline=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-Command','exit 0'],
                                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        self.assertEqual(prefix,baseline.stderr)
        M.write(M.OUT/'host-byte-result.json',{'HOST_ONLY':True,'bytes_each_direction':len(data),'all256':True,
                'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),
                'shell_startup_stderr_prefix_bytes':len(prefix),'prefix_matches_independent_baseline':True,
                'child_stderr_sha256':hashlib.sha256(p.stderr[-len(data):]).hexdigest(),
                'exit':p.returncode,'elapsed_s':elapsed,'SDK':0,'SSH':0})

    def test_03_eof_spaces_apostrophe_and_zero_values(self):
        code="import sys;d=sys.stdin.buffer.read();sys.stdout.buffer.write(b\"O'Brien space\\x00\"+d)"
        p,_=execute(code,b'EOF\x00\xff')
        self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace'))
        self.assertEqual(p.stdout,b"O'Brien space\x00EOF\x00\xff")

    def test_04_actual_blocked_child_deadline(self):
        p,elapsed=execute('import time;time.sleep(10)',remaining=20.35)
        self.assertEqual(p.returncode,124,p.stderr.decode('utf8','replace'))
        self.assertLess(elapsed,4)
        M.write(M.OUT/'host-deadline-result.json',{'HOST_ONLY':True,'proxy_limit_s':.35,'observed_elapsed_s':elapsed,'exit':124,'SDK':0,'SSH':0})

    def test_06_cleanup_wait_and_error_drain_use_remaining_end(self):
        command=M.proxy_command(EXE,'pass',30.)
        encoded=command.split("FromBase64String('",1)[1].split("'",1)[0]
        import base64
        script=base64.b64decode(encoded).decode('utf-16le')
        self.assertNotIn('WaitForExit(2000)',script)
        self.assertNotIn('Error.WriteLine',script)
        self.assertIn('$workLimit=[Math]::Max(0,$limit-2)',script)
        self.assertEqual(script.count('WaitForExit([Math]::Min(2000,(LeftMilliseconds)))'),2)
        missing=str(Path(EXE).with_name('HOST_MISSING_PYTHON_120.exe'))
        cmd=M.proxy_command(missing,'pass',30.)
        p=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-Command',cmd],input=b'',
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        self.assertEqual(p.returncode,125)
        self.assertEqual(p.stdout,b'')

    def test_05_frozen_bootstrap_full_payload_and_binary_zip(self):
        D=M.legacy()
        runid,nonce=uuid.uuid4().hex,uuid.uuid4().hex
        fake=("from pathlib import Path\nimport zipfile\n"
              "def remote_supervise(run,deadline):\n"
              " p=Path(run)/'records.zip'\n"
              " with zipfile.ZipFile(p,'x') as z:z.writestr('HOST_ONLY.bin',bytes(range(256))*100)\n"
              " return p\n").encode()
        job={'unit':119,'run_id':runid,'nonce':nonce,'hardware_approved':False,'inputs':{'source/driver.py':hashlib.sha256(fake).hexdigest()}}
        jr=json.dumps(job).encode();buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('job.json',jr);z.writestr('input/source/driver.py',fake)
        raw=buf.getvalue()
        args={'run_id':runid,'nonce':nonce,'driver_sha256':hashlib.sha256(fake).hexdigest(),
              'bundle_sha256':hashlib.sha256(raw).hexdigest(),'bundle_bytes':len(raw),'job_sha256':hashlib.sha256(jr).hexdigest(),
              'remote_root':(M.OUT/'HOST'/uuid.uuid4().hex/'robot-arm-lab/119/runs').as_posix(),'remaining':1000.}
        keys=('nonce','run_id','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')
        go=json.dumps(dict({n:args[n] for n in keys},kind='GO')).encode()+b'\n'
        p,elapsed=execute(D.bootstrap_code(args),go+raw,remaining=1000.)
        self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace'))
        ready,header,archive=p.stdout.split(b'\n',2)
        header=json.loads(header)
        self.assertEqual(json.loads(ready)['kind'],'READY')
        self.assertEqual(header['nonce'],nonce)
        self.assertEqual(len(archive),header['bytes'])
        self.assertEqual(hashlib.sha256(archive).hexdigest(),header['sha256'])
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(z.read('HOST_ONLY.bin'),bytes(range(256))*100)
        M.write(M.OUT/'host-bootstrap-result.json',{'HOST_ONLY':True,'archive_bytes':len(archive),
                'archive_sha256':header['sha256'],'elapsed_s':elapsed,'SDK':0,'SSH':0})


if __name__=='__main__':
    unittest.main(verbosity=2)
