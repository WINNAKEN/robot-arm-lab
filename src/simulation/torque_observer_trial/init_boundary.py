"""Project-owned zero-time initialization adapter. No installed files are edited."""
import ast
import copy
import hashlib
import inspect
import marshal
from pathlib import Path
import textwrap

PIN='dc1a3fbabbb54a4a3f7c45bf10e25643a346b06a6d9577e8f974584df9869742'
def need(ok,message):
    if not ok:raise RuntimeError(message)
def safe_text(exc):
    try:return type(exc).__name__+":"+str(exc)
    except BaseException:return type(exc).__name__+':<format unavailable>'

def fingerprint(code):return hashlib.sha256(marshal.dumps(code)).hexdigest()
def transform(source):
    original=ast.parse(textwrap.dedent(source));tree=copy.deepcopy(original);count=0
    for call in ast.walk(tree):
        if isinstance(call,ast.Call) and ast.unparse(call.func)=='physx.update_simulation':
            need(len(call.args)==2 and not call.keywords and ast.unparse(call.args[0])=='cls.get_physics_dt()' and ast.literal_eval(call.args[1])==0.,'INIT_BOUNDARY_UNSUPPORTED: warmup call shape')
            call.args[0]=ast.Constant(0.0);count+=1
    need(count==2,'INIT_BOUNDARY_UNSUPPORTED: exact two warmup calls')
    return original,ast.fix_missing_locations(tree)

class Boundary:
    def __init__(self,ctx,manager,physx,settings,clock):
        self.ctx,self.manager,self.settings,self.clock=ctx,manager,settings,clock
        self.getter=None;self.events=[];self.faults=[];self.subscriptions=[]
        self.path=ctx.run/'output/init-boundary.json';self.stream=(ctx.run/'output/native-steps.ndjson').open('x',encoding='utf-8')
        self.saved_setting=settings.get('/app/player/playSimulations');self.original=manager.__dict__['_warmup_and_create_views']
        self.audit={'status':'INSTALLING','original_descriptor_restored':False,'events':self.events,'faults':self.faults}
        try:
            function=self.original.__func__;raw=Path(inspect.getsourcefile(function)).read_bytes()
            need(hashlib.sha256(raw).hexdigest()==PIN,'INIT_BOUNDARY_UNSUPPORTED: installed manager SHA')
            before,after=transform(inspect.getsource(function));self.audit.update(module_sha256=PIN,original_ast=hashlib.sha256(ast.dump(before).encode()).hexdigest(),transformed_ast=hashlib.sha256(ast.dump(after).encode()).hexdigest(),original_code_sha256=fingerprint(function.__code__))
            after.body[0].decorator_list=[];namespace={};exec(compile(after,'<074-zero-time-warmup>','exec'),function.__globals__,namespace)
            replacement=namespace[function.__name__];self.audit['runtime_code_sha256']=fingerprint(replacement.__code__)
            settings.set('/app/player/playSimulations',False);need(settings.get('/app/player/playSimulations') is False,'automatic physics disabled')
            for pre in (True,False):self.subscriptions.append(physx.subscribe_physics_on_step_events(lambda dt,pre=pre:self.observe(pre,dt),pre_step=pre,order=-1000 if pre else 1000))
            manager._warmup_and_create_views=classmethod(replacement);self.audit['status']='INSTALLED_BEFORE_CONTEXT';self.publish()
        except BaseException:
            self.close();raise
    def publish(self):self.ctx.write(self.path,self.audit)
    def observe(self,pre,dt):
        import json
        row={'phase':'pre' if pre else 'post','dt_s':float(dt),'state_available':False}
        try:
            row['engine_time_s']=float(self.clock())
            if self.getter is not None:row['state']=self.getter();row['state_available']=True
            if dt>0 and not row['state_available']:self.faults.append('INIT_OBSERVATION_GAP')
        except BaseException as exc:self.faults.append(safe_text(exc));row['error']=safe_text(exc)
        self.events.append(row);self.stream.write(json.dumps(row,allow_nan=False)+'\n');self.stream.flush()
    def after_reset(self):
        self.manager._warmup_and_create_views=self.original
        self.audit['original_descriptor_restored']=self.manager.__dict__['_warmup_and_create_views'] is self.original
        self.audit['reset_engine_time_s']=float(self.clock());self.audit['reset_positive_events']=sum(e['dt_s']>0 for e in self.events)
        self.audit['status']='RESET_OBSERVED';self.publish()
        need(self.audit['reset_engine_time_s']==0. and self.audit['reset_positive_events']==0 and not self.faults,'INIT_BOUNDARY_UNSUPPORTED: initialization advanced or observation gap')
    def ready(self,getter):
        self.getter=getter;state=getter();self.audit['initial_state']=state;self.audit['status']='VIEW_READY';self.publish()
        need(all(abs(v)<=1e-6 for v in list(state['q'].values())+list(state['qd'].values())),'INIT_BOUNDARY_UNSUPPORTED: initial q/qd moved')
    def finish(self,steps):
        self.audit['status']='COMPLETE';self.audit['expected_positive_steps']=steps
        self.audit['positive_pre']=sum(e['dt_s']>0 and e['phase']=='pre' for e in self.events);self.audit['positive_post']=sum(e['dt_s']>0 and e['phase']=='post' for e in self.events);self.publish()
        need(not self.faults and self.audit['positive_pre']==self.audit['positive_post']==steps,'INIT_OBSERVATION_GAP: native step coverage')
    def close(self):
        errors=self.audit.setdefault('cleanup_errors',[])
        actions=[('descriptor',lambda:setattr(self.manager,'_warmup_and_create_views',self.original)),
                 ('setting',lambda:self.settings.set('/app/player/playSimulations',self.saved_setting)),
                 ('subscriptions',lambda:self.subscriptions.clear()),('stream',lambda:self.stream.close())]
        for name,action in actions:
            try:action()
            except BaseException as exc:errors.append({'channel':name,'error':safe_text(exc)})
        self.audit['original_descriptor_restored']=self.manager.__dict__['_warmup_and_create_views'] is self.original
        try:self.publish()
        except BaseException as exc:errors.append({'channel':'publish','error':safe_text(exc)})
        return errors
