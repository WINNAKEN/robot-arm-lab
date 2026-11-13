"""Original exploded principle diagram. Blank discs intentionally cannot mesh."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from build_concept import Model, OUT, EV, ROOT, dump, run

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cli',required=True,type=Path);args=ap.parse_args()
    m=Model(); O=np.zeros(3);R=np.eye(3)
    m.cmd('document.metadata.set',values={'project':'robot-arm-lab','description':'NONFUNCTIONAL exploded cycloidal principle schematic: blank smooth discs, no cycloidal tooth profiles or matched dimensions. Reference Faze4 J2 27:1; not a verified ratio of this concept.'})
    m.begin('PRINCIPLE_ONLY_NOT_WORKING_REDUCER')
    m.cylinder('INPUT_SHAFT_SCHEMATIC',O,R,0,24,7,'#8ca2b5')
    m.cylinder('ECCENTRIC_JOURNAL_ASSUMED_1MM_OFFSET',np.array([1.,0,0]),R,24,8,4,'#ef7a36')
    m.cylinder('OUTER_HOUSING_HALF_CUT_SCHEMATIC',O,R,34,24,52,'#46535f',47)
    m.plane('HOUSING_SECTION_CUT',O,R,34)
    m.cmd('sketch.line',points=[[-55,0],[55,0],[55,55],[-55,55]],closed=True)
    m.cmd('sketch.finish')
    m.cmd('solid.extrude',distance=24,operation='cut',targets=['OUTER_HOUSING_HALF_CUT_SCHEMATIC'],name='SECTION_CUT_NONFUNCTIONAL')
    for i in range(28):
        a=2*math.pi*i/28
        m.cylinder(f'OUTER_PIN_{i+1:02}_SCHEMATIC',np.array([43.5*math.cos(a),43.5*math.sin(a),0]),R,34,24,1.5,'#b9c4cf')
    for i,z in enumerate((68,82)):
        center=np.array([1. if i==0 else -1.,0,0])
        m.cylinder(f'BLANK_DISC_{i+1}_NO_CYCLOIDAL_TEETH',center,R,z,4,79.75/2,'#d87737',5)
        for k in range(6):
            a=2*math.pi*k/6
            C=O+np.array([26*math.cos(a),26*math.sin(a),0])
            name=f'DISC_{i+1}_OUTPUT_CLEARANCE_{k+1}'
            m.plane(name,C,R,z);m.cmd('sketch.circle.center',center=[0,0],radius=3.5);m.cmd('sketch.finish')
            m.cmd('solid.extrude',distance=4,operation='cut',targets=[f'BLANK_DISC_{i+1}_NO_CYCLOIDAL_TEETH'],name=name+'_CUT')
    for k in range(6):
        a=2*math.pi*k/6
        m.cylinder(f'OUTPUT_PIN_{k+1}_SCHEMATIC',np.array([26*math.cos(a),26*math.sin(a),0]),R,96,20,2,'#b9c4cf')
    m.cylinder('OUTPUT_FLANGE_SCHEMATIC',O,R,116,7,37,'#ed7d31',8)
    m.cmd('component.list',compact=True,bodies=True)
    dump(OUT/'reducer-schematic-commands.json',{'commands':m.commands})
    native=OUT/'reducer-principle-schematic-NONFUNCTIONAL.solidcraft'
    run(args.cli,'schematic-build',['run',OUT/'reducer-schematic-commands.json','--save',native,'--results','--json-out',EV/'schematic-build-result.json'])
    run(args.cli,'schematic-eval',['eval',native,'--json-out',EV/'schematic-eval.json'])
    run(args.cli,'schematic-snapshot',['snapshot','--in',native,'--out',OUT/'reducer-schematic-raw.png','--view','iso','--width','1200','--height','1000','--no-grid','--no-axes'])
    canvas=Image.new('RGB',(1600,1000),'#eef2f7')
    with Image.open(OUT/'reducer-schematic-raw.png')as im: canvas.paste(im.convert('RGB'),(0,0))
    d=ImageDraw.Draw(canvas);f=ImageFont.load_default(size=22);h=ImageFont.load_default(size=30)
    d.text((1110,45),'REDUCER PRINCIPLE',font=h,fill='#283a49')
    notes=['ORIGINAL SCHEMATIC','NOT A WORKING GEARBOX','','Smooth blank discs:','NO cycloidal tooth profile.','','28 outer pins; dual blanks.','Reference: Faze4 J2 27:1.','This is NOT a validated ratio.','','1 mm eccentric is assumed.','79.75 mm blank is assumed','from reference mesh width.','','Axial spacing is exploded.','Pin clearances, bearings,','coupling and fits NOT designed.']
    for i,line in enumerate(notes): d.text((1110,105+i*36),line,font=f,fill='#344b5d')
    canvas.save(OUT/'reducer-principle-schematic.png')
    e=json.loads((EV/'schematic-eval.json').read_text());assert len(e['bodies'])==40
    assert all(b['volume_mm3']>0 and b.get('kernel',{}).get('shells')==1 for b in e['bodies'])
    dump(OUT/'reducer-schematic-validation.json',{'status':'PASS_DIAGRAM_ONLY','native_brep_bodies':len(e['bodies']),'all_positive_solid_shells':True,'functional_meshing':'NOT_DESIGNED','reduction_ratio':'NOT_VERIFIED','manufacturing':'NOT_APPROVED','actual_ref_joint6':'Faze4 J6 is planetary, not cycloidal','source':'Source-Robotics/Faze4-Robotic-arm/docs/B_Design_decisions.rst','license':'Original reference LICENSE CERN-OHL-S-2.0; README MIT badge conflicts'})
    print('Schematic ready: '+str(native))

if __name__=='__main__':main()
