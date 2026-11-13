"""Analytic controls for136 frames, units, angle branches and coupling."""
from pathlib import Path
import math
import sys
import unittest
import xml.etree.ElementTree as ET
import json

import numpy as np

sys.path.insert(0,str(Path(__file__).absolute().parent))
import kinematics as k

ROOT=Path(__file__).absolute().parents[3]

class KinematicTests(unittest.TestCase):
    def test_rpy_order_with_noncommuting_rotations(self):
        r=k.rpy_rotation([math.pi/2,0,math.pi/2])
        self.assertTrue(np.allclose(r@np.array([0,1,0]),[0,0,1],atol=1e-14))
        self.assertTrue(np.allclose(r@np.array([0,0,1]),[1,0,0],atol=1e-14))

    def test_arbitrary_axis_rodrigues_and_bad_axes(self):
        axis=np.ones(3)/math.sqrt(3)
        self.assertTrue(np.allclose(k.axis_rotation(axis,2*math.pi/3)@[1,0,0],[0,1,0],atol=1e-14))
        for a in [[0,0,0],[2,0,0],[float('nan'),0,1]]:
            with self.subTest(a=a),self.assertRaises(ValueError):k.axis_rotation(a,.1)

    def test_joint_origin_before_motion_and_si(self):
        joint={'type':'prismatic','zero':k.origin([.028,0,0],[0,0,math.pi/2]),'axis':[-1,0,0]}
        t=k.joint_transform(joint,.002)
        self.assertTrue(np.allclose(t[:3,3],[.028,-.002,0],atol=1e-15))
        self.assertTrue(np.allclose(k.millimetres(t)[:3,3],[28,-2,0]))
        self.assertTrue(np.allclose(k.inverse(t)@t,np.eye(4),atol=1e-14))

    def test_quaternion_sign_and_near_unit_normalization(self):
        q=[math.cos(.3),0,math.sin(.3),0]
        self.assertTrue(np.allclose(k.quaternion(q),k.quaternion([-v for v in q])))
        self.assertTrue(np.allclose(k.quaternion(q),k.axis_rotation([0,1,0],.6)))
        with self.assertRaises(ValueError):k.quaternion([2,0,0,0])

    def test_projected_revolute_signed_angle_branch_and_off_axis(self):
        j={'type':'revolute','zero':k.origin([0,0,.026],[0,-1.481,0]),'axis':[0,1,0]}
        for q in [-6.0,-.4,.7,6.0]:
            v=k.project_joint(k.joint_transform(j,q),j,q)
            self.assertAlmostEqual(v['projected_q'],q,places=12)
            self.assertLess(v['off_axis_rotation_rad'],1e-12)
        moved=k.joint_transform(j,.7);moved[:3,3]+=[.001,0,0]
        self.assertAlmostEqual(k.project_joint(moved,j,.7)['off_axis_translation_mm'],1,places=10)

    def test_projected_prismatic_sign_and_off_axis(self):
        j={'type':'prismatic','zero':k.origin([-.02,0,0],[0,0,0]),'axis':[-1,0,0]}
        t=k.joint_transform(j,-.01);t[1,3]=.0002
        v=k.project_joint(t,j,-.01)
        self.assertAlmostEqual(v['projected_q'],-.01)
        self.assertAlmostEqual(v['off_axis_translation_mm'],.2)

    def test_coupling_distinguishes_actual_from_target_tracking(self):
        ratio=-1000/13.5
        target={'KG1_slide_A':-.0105,'KG1_slide_B':-.0105,'KG1_pinion':ratio*(-.0105)}
        actual=dict(target,KG1_slide_A=-.010,KG1_slide_B=-.010)
        v=k.coupling(actual,target,ratio,0,13.5)
        self.assertAlmostEqual(v['target_phase_A_rad'],0)
        self.assertAlmostEqual(v['pinion_tracking_rad'],0)
        self.assertAlmostEqual(v['jaw_A_tracking_mm'],.5)
        self.assertAlmostEqual(v['equivalent_rack_A_mm'],.5)
        self.assertNotEqual(v['phase_A_rad'],0)

    def test_xml_closed_asset_and_open_zero_and_corrupt_contracts(self):
        raw=(ROOT/'models/robot-arm-urdf-v4/robot_arm.urdf').read_bytes()
        ledger=json.loads((ROOT/'models/robot-arm-urdf-v4/numeric-ledger.json').read_text())
        params=json.loads((ROOT/'src/cad/kmjh-gripper-v1/parameters.json').read_text())
        j,g=k.parse_urdf(raw,ledger,params)
        q={name:0. for name in k.GRIPPER};fk=k.gripper_fk(j,q)
        self.assertAlmostEqual(fk['KG1_B'][0,3]-fk['KG1_A'][0,3],.04)
        q={'KG1_slide_A':-.02,'KG1_slide_B':-.02,'KG1_pinion':g['mimic_rad_per_m']*(-.02)}
        fk=k.gripper_fk(j,q)
        self.assertAlmostEqual(fk['KG1_A'][0,3],0)
        self.assertTrue(np.allclose(fk['KG1_R'][:3,:3],np.eye(3),atol=1e-14))
        for mutation in ['axis','offset','ratio','missing','duplicate']:
            t=ET.fromstring(raw);pin=t.find("joint[@name='KG1_pinion']")
            if mutation=='axis':pin.find('axis').set('xyz','0 -1 0')
            elif mutation=='offset':pin.find('mimic').set('offset','1')
            elif mutation=='ratio':pin.find('mimic').set('multiplier','-1')
            elif mutation=='missing':t.remove(pin)
            else:t.append(ET.fromstring(ET.tostring(pin)))
            with self.subTest(mutation=mutation),self.assertRaises((ValueError,KeyError)):k.parse_urdf(ET.tostring(t),ledger,params)

    def test_tiny_rotation_and_nonfinite_numbers_fail(self):
        self.assertAlmostEqual(k.rotation_angle(k.axis_rotation([0,1,0],1e-8)),1e-8,places=16)
        for value in [True,float('nan'),float('inf')]:
            with self.subTest(value=value),self.assertRaises(ValueError):k.number(value)

if __name__=='__main__':unittest.main(verbosity=2)
