"""Known physical/provenance witnesses against the actual new isolated entry."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
try:from . import kernel as K
except ImportError:import kernel as K


class KernelTests(unittest.TestCase):
    def fixture(self,folder):
        run=Path(folder)/('c'*32);base=run/'input';base.mkdir(parents=True);source=Path(__file__).parent
        cfg=K.read(source/'config.json')
        for name in ('kernel.py','control.py','verify.py','native.py'):
            p=base/'code'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(source/name,p)
        shutil.copyfile(source/'config.json',base/'config.json')
        for name,value in cfg['references'].items():
            p=base/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(K.ROOT/value['path'],p)
        prefix=Path(folder)/'sealed-libraries';prefix.mkdir();(prefix/'sentinel.txt').write_text('trusted bytes')
        K.write(base/'prefix-seal.json',{'schema_version':1,'files':{'sentinel.txt':K.sha(prefix/'sentinel.txt')}})
        job={'schema_version':1,'run_id':run.name,'hardware_approved':False,'prefix':str(prefix),
            'prefix_seal_sha256':K.sha(base/'prefix-seal.json'),'inputs':{n:K.sha(base/n) for n in K.FIXED}}
        K.write(run/'job.json',job);return run,job

    def entry(self,run,job_sha=None,kernel_sha=None):
        code=K.bootstrap(run,kernel_sha or K.sha(run/'input/code/kernel.py'),job_sha or K.sha(run/'job.json'),'inspect')
        return subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=30)

    def api(self,run):
        job,data=K.checked_bytes(run,K.sha(run/'job.json'));return K.capabilities(run,job,data)

    def static(self,api):
        s=copy.deepcopy(api['golden']);s.update(controller='ENGINE_COMPUTED_TORQUE_NATIVE_PD_ZERO',lab_manager='isaaclab_physx.PhysxManager',solver={'position_iterations':64,'velocity_iterations':16})
        s['gains']={'kp':[0.]*6,'kd':[0.]*6,'effort':[3,6,5,2,2,1]};s['actual_drives']['kp']=[0.]*6;s['actual_drives']['kd']=[0.]*6
        return s

    def test_actual_isolated_entry_positive(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);p=self.entry(r);self.assertEqual(p.returncode,0,p.stderr)
            result=K.read(r/'output/entry-proof.json');self.assertFalse(result['project_search_path'])
            self.assertIn('native',result['loaded'])

    def test_original_missing_core_and_mandatory_manifest_deletion_before_exec(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);marker=Path(f)/'UNAPPROVED_CORE_EXECUTED'
            (r/'input/code/core.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()')
            p=self.entry(r);self.assertNotEqual(p.returncode,0);self.assertFalse(marker.exists())
            (r/'input/code/core.py').unlink();j['inputs'].pop('lib/frames.py');K.write(r/'job.json',j)
            p=self.entry(r);self.assertNotEqual(p.returncode,0);self.assertIn(b'Fixed complete input',p.stderr)

    def test_original_package_shadow_is_rejected_inside_inputs(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);marker=Path(f)/'UNAPPROVED_PACKAGE_EXECUTED'
            p=r/'input/code/setup';p.mkdir();(p/'__init__.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()')
            result=self.entry(r);self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())

    def test_project_root_shadow_is_not_searchable(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);marker=Path(f)/'UNAPPROVED_PACKAGE_EXECUTED'
            for name in ('setup','frames','core'):
                p=r/name;p.mkdir();(p/'__init__.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()')
            result=self.entry(r);self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(marker.exists())
            self.assertFalse(K.read(r/'output/entry-proof.json')['project_search_path'])

    def test_modified_kernel_never_executes(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);old=K.sha(r/'input/code/kernel.py');marker=Path(f)/'BAD_ROOT'
            (r/'input/code/kernel.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()')
            result=self.entry(r,kernel_sha=old);self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())

    def test_payload_bytes_prefix_and_resealed_seal_reject(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);prefix=Path(j['prefix']);(prefix/'other.py').write_text('bad')
            result=self.entry(r);self.assertNotEqual(result.returncode,0)
            K.write(r/'input/prefix-seal.json',{'schema_version':1,'files':{}})
            result=self.entry(r);self.assertNotEqual(result.returncode,0)
            with (r/'input/code/native.py').open('a') as stream:stream.write('\n# drift\n')
            result=self.entry(r);self.assertNotEqual(result.returncode,0)

    def test_complete_source_static_positive_and_resealed_known_frame_mutations(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);api=self.api(r);V=api['lib']['verify'];s=self.static(api);V.validate_static_source(s,api['golden'])
            def side(x):x['joints'][1]['local_pos1']=[99,0,0]
            def body(x):x['bodies']=[]
            def com(x):x['bodies'][1]['com'][0]+=.01
            def inertia(x):x['bodies'][2]['principal_axes_wxyz']=[.5,.5,.5,.5]
            def collider(x):x['colliders'][0]['local_basis'][0][0]+=1
            def owner(x):x['colliders'][0]['body_path']='unknown'
            def enable(x):x['colliders'][0]['enabled']=False
            def missing(x):x.pop('colliders')
            for change in (side,body,com,inertia,collider,owner,enable,missing):
                altered=copy.deepcopy(s);change(altered);K.write(r/'snapshot.json',altered)
                # Re-sealing a mutable result hash cannot replace the fixed source authority.
                K.write(r/'result.json',{'snapshot_sha256':K.sha(r/'snapshot.json'),'status':'CONNECTED'})
                with self.assertRaises((ValueError,KeyError)):V.validate_static_source(K.read(r/'snapshot.json'),api['golden'])

    def test_control_full_mass_compensation_caps_and_reject_nonfinite(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);C=self.api(r)['lib']['control'];M=[[.01 if i==k else 0. for k in range(6)] for i in range(6)];ref={'q_rad':[0.]*6,'qd_rad_s':[0.]*6}
            answer=C.command([0.]*6,[0.]*6,ref,[0.]*6,M,[.1]*6,[.01]*6)
            self.assertTrue(all(abs(v-.11)<1e-12 for v in answer['tau']))
            answer=C.command([0.]*6,[0.]*6,{'q_rad':[1.]*6,'qd_rad_s':[0.]*6},[0.]*6,[[100. if i==k else 0. for k in range(6)] for i in range(6)],[0.]*6,[0.]*6)
            self.assertEqual(answer['tau'],C.CAP);self.assertTrue(all(answer['saturated']))
            for invalid in (True,float('nan'),float('inf'),'0'):
                with self.assertRaises(ValueError):C.command([invalid]*6,[0.]*6,ref,[0.]*6,M,[0.]*6,[0.]*6)
            M[0][1]=1
            with self.assertRaises(ValueError):C.command([0.]*6,[0.]*6,ref,[0.]*6,M,[0.]*6,[0.]*6)

    def test_all_old_failed_frames_and_late_corruption_checked(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);api=self.api(r);V=api['lib']['verify'];motion=api['lib']['motion'];frames=api['lib']['frames']
            program=motion.load_program(r/'input/data/program.json');layout=frames.decode((r/'input/data/kinematics.json').read_bytes())
            original=K.ROOT/'outputs/isaac-contact-v1/runs/501c7bfc27b6409b8351821408bff0de/retrieved/501c7bfc27b6409b8351821408bff0de'
            rows=[K.parse(line) for line in (original/'samples.ndjson').read_text(encoding='utf-8').splitlines()];s=copy.deepcopy(api['golden']);s['lab_baseline_step']=0
            for i,row in enumerate(rows):row['timeline_playing']=True;row['lab_step']=i;row['clock'].update(lab_read_before=i,lab_read_after=i)
            result=V.compare_samples(s,rows,program,frames,layout,motion);self.assertEqual(result['full_frame_samples'],6781);self.assertEqual(result['checkpoints_passed'],0)
            rows[-1]['links'][0]['position'][0]+=.01
            with self.assertRaises(ValueError):V.compare_samples(s,rows,program,frames,layout,motion)

    def test_complete_contact_and_control_replay(self):
        with tempfile.TemporaryDirectory() as f:
            r,j=self.fixture(f);api=self.api(r);V=api['lib']['verify'];C=api['lib']['control'];motion=api['lib']['motion']
            program=motion.load_program(r/'input/data/program.json')
            original=K.ROOT/'outputs/isaac-contact-v1/runs/501c7bfc27b6409b8351821408bff0de/retrieved/501c7bfc27b6409b8351821408bff0de'
            rows=[K.parse(line) for line in (original/'samples.ndjson').read_text(encoding='utf-8').splitlines()]
            M=[[.01 if i==k else 0. for k in range(6)] for i in range(6)]
            for i,row in enumerate(rows[1:],1):
                prev=rows[i-1];g=row['actuation']['ff'];c=[0.]*6;qdd=C.acceleration(motion,program,i/120);ref=motion.sample(program,i/120)
                effort=C.command(prev['q_rad'],prev['qd_rad_s'],ref,qdd,M,g,c)
                row['actuation']={**effort,'M':M,'g':g,'c':c,'qdd_ref':qdd,'source_index':i-1,'read_step':row['clock']['step_before'],
                    'tau_readback':effort['tau'],'torque_scope':'SIM_COMMAND_NOT_MEASURED_ACTUATOR_FORCE'}
            result=V.audit_contacts(api['golden'],rows,program)
            self.assertEqual(result['dynamic_failures'],[])
            rows[-1]['actuation']['tau_readback'][0]+=1
            with self.assertRaises(ValueError):V.audit_contacts(api['golden'],rows,program)


if __name__=='__main__':unittest.main(verbosity=2)
