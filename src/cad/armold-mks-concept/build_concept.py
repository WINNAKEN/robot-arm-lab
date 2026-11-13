"""Original parametric B-rep concept, using the existing SolidCraft CLI only."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'models' / 'armold-mks-concept-v1'
EV = ROOT / '.dev' / 'armold-concept-evidence' / 'build'

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def rot(axis, deg):
    a=np.asarray(axis,dtype=float); a/=np.linalg.norm(a)
    x,y,z=a; t=math.radians(deg); c=math.cos(t); s=math.sin(t)
    return c*np.eye(3)+(1-c)*np.outer(a,a)+s*np.array([[0,-z,y],[z,0,-x],[-y,x,0]])

def frame(origin, axis, x_hint=None):
    z=np.asarray(axis,dtype=float); z/=np.linalg.norm(z)
    hint=np.array(x_hint if x_hint is not None else ([1,0,0] if abs(z[0])<.8 else [0,1,0]),dtype=float)
    x=hint-z*np.dot(hint,z); x/=np.linalg.norm(x); y=np.cross(z,x)
    return np.asarray(origin,dtype=float),np.column_stack([x,y,z])

class Model:
    def __init__(self): self.commands=[]; self.primitives=[]; self.names=[]
    def cmd(self, command_id, **p): self.commands.append({'command':command_id,'params':p})
    def begin(self,name):
        self.cmd('component.activate',component='root')
        self.cmd('component.create',name=name)
    def plane(self,name,O,R,z):
        self.cmd('sketch.create',name=name,plane={'origin':(O+R[:,2]*z).tolist(),'x_dir':R[:,0].tolist(),'y_dir':R[:,1].tolist()})
    def color(self,name,color): self.cmd('appearance.assign',bodies=[name],color=color)
    def cylinder(self,name,O,R,z,h,r,color,inner=0):
        self.plane(name+'_PROFILE',O,R,z)
        self.cmd('sketch.circle.center',center=[0,0],radius=float(r))
        self.cmd('sketch.finish')
        self.cmd('solid.extrude',distance=float(h),operation='new',body_name=name,name=name+'_EXTRUDE')
        if inner:
            self.plane(name+'_BORE',O,R,z)
            self.cmd('sketch.circle.center',center=[0,0],radius=float(inner))
            self.cmd('sketch.finish')
            self.cmd('solid.extrude',distance=float(h),operation='cut',targets=[name],name=name+'_CUT')
        self.color(name,color); self.names.append(name)
        self.primitives.append({'name':name,'kind':'ring' if inner else 'cylinder','origin':O.tolist(),'rotation':R.tolist(),'z':z,'h':h,'r':r,'inner':inner})
    def box(self,name,O,R,center,size,color,expr_sizes=None):
        c=np.asarray(center,dtype=float); s=np.asarray(size,dtype=float)
        self.plane(name+'_PROFILE',O+R@c,R,-s[2]/2)
        dims=expr_sizes if expr_sizes else s.tolist()
        lo=[f'-({a})/2' if isinstance(a,str) else -a/2 for a in dims[:2]]
        hi=[f'({a})/2' if isinstance(a,str) else a/2 for a in dims[:2]]
        self.cmd('sketch.line',points=[lo,[hi[0],lo[1]],hi,[lo[0],hi[1]]],closed=True)
        self.cmd('sketch.finish')
        self.cmd('solid.extrude',distance=dims[2],operation='new',body_name=name,name=name+'_EXTRUDE')
        self.color(name,color); self.names.append(name)
        self.primitives.append({'name':name,'kind':'box','origin':O.tolist(),'rotation':R.tolist(),'center':c.tolist(),'size':s.tolist()})

def run(cli,label,args):
    p=subprocess.run([str(cli),*map(str,args)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120,env=dict(os.environ,SOLIDCRAFT_GPU='cpu'))
    (EV/(label+'-stdout.txt')).write_text(p.stdout,encoding='utf-8')
    (EV/(label+'-stderr.txt')).write_text(p.stderr,encoding='utf-8')
    if p.returncode: raise RuntimeError(label+': '+p.stderr)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--cli',required=True,type=Path); args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True); EV.mkdir(parents=True,exist_ok=True)
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    axes=np.asarray(p['axis_parent_zero'],dtype=float); q=p['pose_deg']; sizes=p['reducer_diameters_mm']; d=p['reducer_depth_mm']
    offsets=[[0,0,p['joint1_height_mm']],[0,0,p['shoulder_rise_mm']],[p['upper_arm_mm'],0,0],[p['forearm_mm'],0,0],[p['wrist_offsets_mm'][0],0,0],[p['wrist_offsets_mm'][1],0,0]]
    joints=[]; o=np.zeros(3); R=np.eye(3)
    for j in range(6):
        o=o+R@np.asarray(offsets[j]); axis=R@axes[j]; pre=R.copy(); R=R@rot(axes[j],q[j])
        joints.append({'name':f'J{j+1}','parent': 'Base' if j==0 else f'Link{j}','child':f'Link{j+1}','origin_mm':o.tolist(),'axis_world':axis.tolist(),'axis_parent_zero':axes[j].tolist(),'pose_deg':q[j],'R_parent':pre.tolist(),'R_child':R.tolist()})
    m=Model(); graphite='#323b45'; orange='#ed7d31'; metal='#bac6d0'; motor='#496577'; driver='#d39b49'
    m.cmd('document.metadata.set',values={'project':'robot-arm-lab','part_number':'ARMOLD-TYPE-MKS-CONCEPT-V1','revision':'concept-v1','description':'Original Armold-type 6-axis MKS NEMA17 concept. Assumed keepouts. NOT FOR FABRICATION.','org.robotarmlab.concept':{'assumptions':p['assumptions'],'joints':joints,'motor_sets_ordered':2,'reducer_reference':'Faze4 mechanisms only; not copied whole-arm geometry or validated ratio.'}})
    for key in ('motor_frame_mm','motor_length_mm','driver_width_mm','driver_depth_mm','connector_clearance_mm','upper_arm_mm','forearm_mm'):
        m.cmd('parameters.change',name=key.replace('_mm',''),expression=f'{p[key]} mm',comment='Concept assumption; regenerate layout using parameters.json')
    # Seven root links. Stator/motor of joint i belongs to its parent; rotor belongs to child.
    for link in range(7):
        component='Base' if link==0 else f'Link{link}'
        m.begin(component)
        m.cmd('component.metadata.set',component=component,description='Concept rigid link; geometry and mounting not fabrication-approved',properties={'purpose':'MKS CAN MT six-axis layout','fit':'UNVERIFIED'})
        if link==0:
            O=np.zeros(3); Q=np.eye(3)
            m.box('BASE_PLATE_CONCEPT',O,Q,[0,0,p['base_thickness_mm']/2],[p['base_width_mm'],p['base_width_mm'],p['base_thickness_mm']],graphite)
            m.cylinder('BASE_HOLLOW_PEDESTAL',O,Q,12,63,62,graphite,38)
        else:
            j=joints[link-1]; O=np.array(j['origin_mm']); Q=np.array(j['R_child']); A=np.array(j['axis_world'])
            F=frame(O,A,Q[:,0] if abs(np.dot(Q[:,0],A))<.8 else Q[:,1])[1]
            m.cylinder(f'J{link}_OUTPUT_FLANGE',O,F,d/2,7,sizes[link-1]/2-8,metal,9)
            m.cylinder(f'J{link}_OUTPUT_SHAFT_CUE',O,F,-5,d/2+19,8,metal)
            if link==1:
                # Compact twin shoulder pillars, clear of the rear motor at J2.
                for side in (-1,1):
                    m.box(f'LINK1_SHOULDER_POST_{side:+}',O,Q,[side*35,0,51],[10,32,58],graphite)
            elif link==2:
                L=p['upper_arm_mm']
                m.box('LINK2_UPPER_SLIM_BEAM',O,Q,[(40+L-42)/2,32,0],[L-82,18,28],graphite)
                m.box('LINK2_ELBOW_STATOR_MOUNT',O,Q,[L-46,23,0],[14,16,28],graphite)
            elif link==3:
                L=p['forearm_mm']
                m.box('LINK3_FOREARM_SIDE_RAIL',O,Q,[(30+L-5)/2,38,0],[L-35,8,20],graphite)
                m.box('LINK3_FLANGE_RAIL_ADAPTER',O,Q,[30,31,0],[20,14,20],graphite)
            elif link in (4,5):
                L=p['wrist_offsets_mm'][link-4]
                # Offset thin spine leaves the axial motor/rear-driver stack visible.
                m.box(f'LINK{link}_WRIST_SPINE',O,Q,[(L+28)/2,44,0],[L-28,10,20],graphite)
                m.box(f'LINK{link}_WRIST_FLANGE_ADAPTER',O,Q,[28,31,0],[12,26,20],graphite)
                if link==4:
                    m.box(f'LINK{link}_NEXT_STATOR_ADAPTER',O,Q,[L-40,25,0],[12,38,20],graphite)
                else:
                    m.box(f'LINK{link}_NEXT_STATOR_ADAPTER',O,Q,[L-8,32,0],[16,24,20],graphite)
            else:
                m.cylinder('TOOL_PASSIVE_FLANGE_NO_GRIPPER_AXIS',O,F,30,8,23,orange,7)
        if link<6:
            j=joints[link]; O=np.array(j['origin_mm']); pre=np.array(j['R_parent']); A=np.array(j['axis_world'])
            F=frame(O,A,pre[:,0] if abs(np.dot(pre[:,0],A))<.8 else pre[:,1])[1]
            r=sizes[link]/2
            m.cylinder(f'J{link+1}_REDUCER_HOUSING_ENVELOPE',O,F,-d/2,d,r,graphite,r-6)
            m.cylinder(f'J{link+1}_REDUCER_UNDESIGNED_CORE',O,F,-d/2+3,d-6,r-8,'#c7652d',12)
            m.cylinder(f'J{link+1}_ORANGE_MODULE_BAND',O,F,-5,10,r+1,orange,r-1)
            m.cylinder(f'J{link+1}_MOTOR_ADAPTER_UNDESIGNED',O,F,-d/2-3,3,r-2,metal,12)
            ml=p['motor_length_mm']; dw=p['driver_width_mm']; dd=p['driver_depth_mm']; mf=p['motor_frame_mm']
            m.box(f'J{link+1}_MOTOR_ASSUMED_NEMA17',O,F,[0,0,-d/2-3-ml/2],[mf,mf,ml],motor,['motor_frame','motor_frame','motor_length'])
            rear=-d/2-3-ml-2-dd/2
            m.box(f'J{link+1}_DRIVER_HEATSINK_KEEP_OUT_ASSUMED',O,F,[0,0,rear],[dw,dw,dd],driver,['driver_width','driver_width','driver_depth'])
            m.box(f'J{link+1}_CONNECTOR_KEEP_OUT_ASSUMED',O,F,[-dw/2-p['connector_clearance_mm']/2,0,rear],[p['connector_clearance_mm'],20,dd], '#ead6a9',['connector_clearance',20,'driver_depth'])
    m.cmd('component.activate',component='root')
    m.cmd('occurrence.ground',occurrence='Base:1',grounded=True)
    for j in joints:
        m.cmd('joint.as_built',type='revolute',a=j['parent']+':1',b=j['child']+':1',at={'point':j['origin_mm'],'z':j['axis_world']},name=j['name']+'_CONCEPT_DISPLAY_ZERO',limits=[[-170,170]])
    m.cmd('component.list',compact=True,bodies=True); m.cmd('joint.list'); m.cmd('joint.inspect'); m.cmd('parameters.list')
    dump(OUT/'build-commands.json',{'commands':m.commands}); dump(OUT/'kinematics.json',{'units':'mm','joint_count':6,'joints':joints,'native_joint_zero':'Displayed pose, not geometric q=0','gripper':'Passive flange only; no seventh axis','limits':'±170 degrees are illustrative software bounds; not verified mechanical travel'})
    dump(OUT/'parameters.json',p); dump(EV/'primitive-expectations.json',m.primitives)
    native=OUT/'armold-type-mks-six-axis-concept.solidcraft'
    run(args.cli,'main-build',['run',OUT/'build-commands.json','--save',native,'--out',OUT/'armold-type-mks-six-axis-concept.step','--out',OUT/'armold-type-mks-six-axis-concept.3mf','--results','--json-out',EV/'main-build-result.json'])
    run(args.cli,'main-eval',['eval',native,'--json-out',EV/'main-eval.json'])
    for v,name in [('iso','iso.png'),('front','front.png'),('right','right.png')]:
        run(args.cli,'snapshot-'+v,['snapshot','--in',native,'--out',OUT/name,'--view',v,'--width','1600','--height','1200','--no-grid','--no-axes'])
    print(json.dumps({'native':str(native),'iso':str(OUT/'iso.png'),'bodies':len(m.names),'joint_count':6}))

if __name__=='__main__': main()
