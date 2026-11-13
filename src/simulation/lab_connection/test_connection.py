"""Closed-root and exact-set host controls. Never installs or invokes SSH/Kit."""
import copy
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
try:from . import setup as S
except ImportError:import setup as S


class ConnectionTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder);run=root/('a'*32);run.mkdir()
        source=Path(__file__).with_name('setup.py');shutil.copyfile(source,run/'setup.py')
        for name in S.PAYLOAD-{'setup.py'}:(run/name).write_text('{}' if name.endswith('.json') else '# host fixture\n',encoding='utf-8')
        self.reseal(run);return run

    def reseal(self,run,omit=None):
        m={'run_id':run.name,'hardware_approved':False,'files_sha256':{n:S.sha(run/n) for n in sorted(S.PAYLOAD) if n!=omit}}
        S.write(run/'job.json',m);return S.sha(run/'job.json')

    def entry(self,run,job_sha):
        code=S.shim(run,job_sha,'records')
        return subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=20)

    def test_actual_isolated_root_positive_control(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);done=self.entry(r,S.sha(r/'job.json'))
            self.assertEqual(done.returncode,0,done.stderr);self.assertTrue((r/'records.zip').is_file())

    def test_original_missing_core_witness_rejects_before_payload(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);marker=r/'UNAPPROVED_CORE_EXECUTED'
            (r/'core.py').write_text("from pathlib import Path\nPath("+repr(str(marker))+").touch()\nraise RuntimeError('sentinel')\n")
            done=self.entry(r,S.sha(r/'job.json'))
            self.assertNotEqual(done.returncode,0);self.assertIn(b'Unknown or missing executable',done.stderr)
            self.assertFalse(marker.exists());self.assertFalse((r/'records.zip').exists())

    def test_missing_mandatory_helper_resealed_manifest_rejects(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);digest=self.reseal(r,'frames.py');done=self.entry(r,digest)
            self.assertNotEqual(done.returncode,0);self.assertIn(b'Exact complete fixed payload',done.stderr)
            self.assertFalse((r/'records.zip').exists())

    def test_payload_byte_mutation_and_duplicate_key_reject(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);digest=S.sha(r/'job.json');(r/'native_probe.py').write_text('raise RuntimeError("sentinel")')
            done=self.entry(r,digest);self.assertNotEqual(done.returncode,0);self.assertIn(b'Unapproved payload bytes',done.stderr)
            (r/'job.json').write_text('{"run_id":1,"run_id":2}')
            with self.assertRaises(ValueError):S.read(r/'job.json')

    def test_root_hash_verified_before_project_code_executes(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);code=S.shim(r,S.sha(r/'job.json'),'records');marker=r/'UNAPPROVED_CORE_EXECUTED'
            (r/'setup.py').write_text("from pathlib import Path\nPath("+repr(str(marker))+").touch()\n")
            done=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=20)
            self.assertNotEqual(done.returncode,0);self.assertIn(b'Trusted root identity',done.stderr);self.assertFalse(marker.exists())

    def test_wrong_host_job_pin_rejects(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);done=self.entry(r,'0'*64)
            self.assertNotEqual(done.returncode,0);self.assertFalse((r/'records.zip').exists())

    def test_prefix_exact_inventory_and_resealed_seal_mutations(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f);p=root/'packages';p.mkdir();(p/'module.py').write_text('x=1\n');seal=root/'seal.json'
            S.write(seal,{'schema_version':1,'files':S.tree(p)});gold=S.sha(seal);S.verify_seal(p,seal,gold)
            (p/'new.py').write_text('raise RuntimeError("unapproved")')
            with self.assertRaisesRegex(ValueError,'inventory'):S.verify_seal(p,seal,gold)
            S.write(seal,{'schema_version':1,'files':S.tree(p)})
            with self.assertRaisesRegex(ValueError,'Host-pinned'):S.verify_seal(p,seal,gold)
            (p/'new.py').unlink();S.write(seal,{'schema_version':1,'files':S.tree(p)});gold=S.sha(seal)
            (p/'module.py').write_text('x=2\n')
            with self.assertRaises(ValueError):S.verify_seal(p,seal,gold)

    def test_module_report_cpu_or_foreign_origin_is_not_connected(self):
        with tempfile.TemporaryDirectory() as f:
            r=self.fixture(f);dest=r/'retrieved';dest.mkdir();remote=str((Path(f)/'remote'/r.name).resolve())
            S.write(r/'prepared.json',{'job_sha256':S.sha(r/'job.json'),'remote_run_dir':remote})
            versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','torchvision':'0.26.0+cu130','warp':'1.17.0','gymnasium':'1.3.0','rsl_rl':'5.5.1'}
            value={'status':'MODULE_GPU_DATA_CAPTURED','run_id':r.name,'pid':123,'parent_pid':12,'job_sha256':S.sha(r/'job.json'),'hardware_approved':False,
                'cuda':'13.0','tensor_device':'cuda:0','tensor_sum':6,'modules':{n:{'version':v,'origin':remote+'/packages/'+n+'/__init__.py'} for n,v in versions.items()}}
            S.write(dest/'modules-exit.json',{'exit_code':0,'child_pid':123});S.write(dest/'modules-result.json',value)
            self.assertEqual(S.evaluate(r,'modules')['status'],'MODULE_GPU_VERIFIED')
            for key,wrong in [('version','2.11.0+cpu'),('origin',str(Path(f)/'other/torch/__init__.py'))]:
                bad=copy.deepcopy(value);bad['modules']['torch'][key]=wrong;S.write(dest/'modules-result.json',bad)
                with self.assertRaises(ValueError):S.evaluate(r,'modules')
            value['run_id']='b'*32;S.write(dest/'modules-result.json',value)
            with self.assertRaises(ValueError):S.evaluate(r,'modules')

    def test_prepare_missing_input_marks_failed_and_preserves_old_run(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f);source=root/'src/simulation/lab_connection';source.mkdir(parents=True)
            for n in ('setup.py','native_probe.py','config.json'):shutil.copyfile(Path(__file__).with_name(n),source/n)
            with self.assertRaises(FileNotFoundError):S.prepare(root)
            self.assertEqual(S.read(root/S.OUT/'current.json')['status'],'FAILED')


if __name__=='__main__':unittest.main(verbosity=2)
