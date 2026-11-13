if __name__=='__main__':raise SystemExit('Use launch.ps1 -Role test')
import copy,json,shutil,subprocess,sys,tempfile,types,unittest
from pathlib import Path
K=API['runner']


class RunnerTests(unittest.TestCase):
    def helper(self):return API['tests_B'].ModelTests()

    def test_A_actual_public_shadow_direct_guard_and_closed_payload(self):
        B=self.helper()
        with tempfile.TemporaryDirectory(prefix='052A-entry-') as td:
            td=Path(td);run,job,pins=B.fixture(td/'fixture');B.complete(run,pins)
            source=td/'project/src/simulation/contract_v3';source.mkdir(parents=True)
            for n,b in API['source'].items():(source/n).write_bytes(b)
            positive=B.cli(source,'verify',run);self.assertEqual(positive.returncode,0,positive.stderr)
            marker=td/'UNAPPROVED'
            (source/'numpy.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nraise RuntimeError("UNAPPROVED")')
            self.assertNotEqual(B.cli(source,'verify',run).returncode,0);self.assertFalse(marker.exists());(source/'numpy.py').unlink()
            cwd=td/'cwd';cwd.mkdir();(cwd/'numpy.py').write_text('raise RuntimeError("CWD_SHADOW")')
            self.assertEqual(B.cli(source,'verify',run,cwd).returncode,0)
            (source/'setup').mkdir();(source/'setup/__init__.py').write_text('raise RuntimeError("PACKAGE_SHADOW")')
            self.assertNotEqual(B.cli(source,'verify',run).returncode,0)
            direct=td/'direct';direct.mkdir();(direct/'json.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()')
            for n in ('runner.py','providers.py','model.py','verify.py','test_runner.py','test_model.py'):
                p=direct/n;p.write_bytes(API['source'][n]);child=subprocess.run([sys.executable,'-B',str(p)],cwd=direct,capture_output=True,timeout=15)
                self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())
            job['inputs'].pop('code/providers.py');K.write(run/'job.json',job)
            with self.assertRaises(ValueError):K.checked(run,K.sha(run/'job.json'),pins)

    def stub_exit(self,folder,discard=False,alter_sdk=False,alter_root=False,robot=False,alter_prefix=False):
        B=self.helper();run,job,pins=B.fixture(folder);cfg=K.read(run/'input/config.json');sdk=Path(folder)/'sdk';sdk.mkdir();(sdk/'VERSION').write_text(cfg['isaac_version'])
        for name in cfg['sdk_files']:
            p=sdk/name;p.write_text('# host approved stub\n');cfg['sdk_files'][name]={'path':str(p),'sha256':K.sha(p)}
        cfg.update(isaac_root=str(sdk),numpy_root=str(sdk/'numpy'),scipy_root=str(sdk/'scipy'))
        prefix=Path(folder)/'prefix';prefix.mkdir()
        K.write(run/'input/prefix-seal.json',{'schema_version':1,'files':{}})
        cfg.update(installation_prefix=str(prefix),installation_seal_sha256=K.sha(run/'input/prefix-seal.json'))
        K.write(run/'input/config.json',cfg);marker=Path(folder)/'WORKER_CALLED'
        (run/'input/code/providers.py').write_text("if __name__=='__main__':raise SystemExit(1)\ndef preflight(api):\n from pathlib import Path\n Path("+repr(str(marker))+").touch()\n return 7\n")
        if robot:
            (run/'input/code/model.py').write_text("if __name__=='__main__':raise SystemExit(1)\ndef bindings(api):\n api['need'](api['contract']['facets']==['static','bodies','trace','contact'],'all host stub obligations')\ndef run(api):\n from pathlib import Path\n Path("+repr(str(marker))+").touch()\n return 7\n")
        if discard:
            p=run/'input/code/runner.py';text=p.read_text(encoding='utf-8');needle="return api['lib']['providers'].preflight(api) if job['stage']=='sdk_preflight' else api['lib']['model'].run(api)"
            self.assertEqual(text.count(needle),1);p.write_text(text.replace(needle,needle.removeprefix('return ')+'\n    return 0'),encoding='utf-8')
        job['stage']='robot_connection' if robot else 'sdk_preflight';K.write(run/'job.json',job);run,job,pins=B.reseal(run)
        code=K.literal(run,K.sha(run/'job.json'),pins,'native')
        if alter_sdk:(sdk/'sitecustomize.py').write_text('raise RuntimeError("UNAPPROVED_SDK")')
        if alter_root:(run/'input/code/runner.py').write_text('raise RuntimeError("UNAPPROVED_ROOT")')
        if alter_prefix:(prefix/'unregistered.py').write_text('raise RuntimeError("UNAPPROVED_PREFIX")')
        return subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=40),marker

    def test_A_real_literal_exit_and_exact_discard_countercontrol(self):
        with tempfile.TemporaryDirectory(prefix='052A-exit-') as td:
            child,marker=self.stub_exit(Path(td)/'good');self.assertEqual(child.returncode,7,child.stderr);self.assertTrue(marker.exists())
            child,marker=self.stub_exit(Path(td)/'discard',discard=True);self.assertEqual(child.returncode,0);self.assertNotEqual(child.returncode,7)
            for name,options in (('sdk',{'alter_sdk':True}),('root',{'alter_root':True})):
                child,marker=self.stub_exit(Path(td)/name,**options);self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())
            child,marker=self.stub_exit(Path(td)/'prefix-positive',robot=True);self.assertEqual(child.returncode,7,child.stderr);self.assertTrue(marker.exists())
            child,marker=self.stub_exit(Path(td)/'prefix-negative',robot=True,alter_prefix=True);self.assertNotEqual(child.returncode,0);self.assertFalse(marker.exists())

    def reservation_case(self,folder,stage,prior=None,duplicate=False,drift=False,bad_pid=False):
        B=self.helper();run,job,pins=B.fixture(folder);job['stage']=stage;K.write(run/'job.json',job);run,job,pins=B.reseal(run)
        cfg=K.read(run/'input/config.json');cfg['remote_root']=str(run.parent)
        ledger=[]
        if prior is not None:
            path=run.parent/('a'*32);reservation=B.prior(run,path/'output',failed=prior=='failed')
            shutil.copyfile(path/'output/job.json',path/'job.json')
            if prior=='unfinished':(path/'output/terminal.json').unlink()
            if drift:reservation['input_signature']='wrong'
            if bad_pid:
                p=path/'output/terminal.json';t=K.read(p);t['parent_pid']=999;K.write(p,t)
            ledger.append(reservation)
        if duplicate and stage=='robot_connection':ledger.append({'stage':stage,'run_id':'d'*32,'job_sha256':'old','input_signature':K.signature(job),'reserved_unix':1.})
        K.write(run.parent/'stage-ledger.json',ledger)
        starts=[]
        class FakeP:
            pid=13
            def __init__(self,*args,**kwargs):starts.append(args)
            def wait(self,timeout):return 0
        class FakeSub:
            Popen=FakeP
            TimeoutExpired=subprocess.TimeoutExpired
            @staticmethod
            def run(*args,**kwargs):return types.SimpleNamespace(returncode=0,stdout=b'0',stderr=b'')
        g=K.supervise.__globals__;original=g['subprocess'];g['subprocess']=FakeSub
        try:code=K.supervise(run,K.sha(run/'job.json'),pins,cfg)
        finally:g['subprocess']=original
        return code,len(starts),K.read(run.parent/'stage-ledger.json')

    def test_A_stage_single_use_and_actual_prerequisite_controls(self):
        with tempfile.TemporaryDirectory(prefix='052A-stages-') as td:
            td=Path(td)
            code,starts,ledger=self.reservation_case(td/'first','sdk_preflight');self.assertEqual((code,starts,len(ledger)),(0,1,1))
            # The original050 success->new attempt witness is now denied for the same stage.
            for state in ('success','failed','unfinished'):
                code,starts,ledger=self.reservation_case(td/('sdk-repeat-'+state),'sdk_preflight',prior=state)
                self.assertNotEqual(code,0);self.assertEqual(starts,0);self.assertEqual(len(ledger),1)
            for label,options in (('missing',{}),('failed',{'prior':'failed'}),('unfinished',{'prior':'unfinished'}),
                                   ('signature',{'prior':'success','drift':True}),('pid',{'prior':'success','bad_pid':True}),
                                   ('repeat',{'prior':'success','duplicate':True})):
                code,starts,ledger=self.reservation_case(td/label,'robot_connection',**options)
                self.assertNotEqual(code,0);self.assertEqual(starts,0)
            code,starts,ledger=self.reservation_case(td/'valid-robot','robot_connection',prior='success')
            self.assertEqual((code,starts,len(ledger)),(0,1,2))

    def test_A_lifecycle_before_after_capture_and_close_failures(self):
        B=self.helper()
        with tempfile.TemporaryDirectory(prefix='052A-lifecycle-') as td:
            run,job,pins=B.fixture(td);api=B.api(run,pins);N=api['lib']['model'];out=run/'output';out.mkdir()
            def fail(_):raise RuntimeError('BEFORE_APP')
            self.assertEqual(N.run(api,start=fail),1);self.assertIn('BEFORE_APP',K.read(out/'terminal.json')['primary_error'])
            class App:
                def close(self,**kw):self.code=kw['exit_code']
            app=App();(out/'status.json').unlink()
            self.assertEqual(N.run(api,start=lambda _:app,collect_fn=fail),1);self.assertEqual(app.code,1)
            (out/'status.json').unlink()
            def capture(_):
                for name in ('observations.json','scene.usda','providers.json','sdk.json'):(out/name).write_text('HOST_MOCK')
            self.assertEqual(N.run(api,start=lambda _:app,collect_fn=capture),0);self.assertEqual(app.code,0)
            class BadClose:
                def close(self,**kw):raise RuntimeError('CLOSE_FAILURE')
            (out/'status.json').unlink();self.assertEqual(N.run(api,start=lambda _:BadClose(),collect_fn=capture),1)
            self.assertIn('CLOSE_FAILURE',K.read(out/'terminal.json')['close_error'])


def run_tests(model_tests):
    suite=unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(RunnerTests),
                            unittest.defaultTestLoader.loadTestsFromTestCase(model_tests.ModelTests)))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1
