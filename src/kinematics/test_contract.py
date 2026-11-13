"""Offline public boundary/pose checks; only temporary copies are modified."""
import copy
import importlib.util
import json
import math
import os
import random
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE = Path(os.environ.get("CONTRACT_TEST_MODULE", Path(__file__).with_name("joint_contract.py")))
spec = importlib.util.spec_from_file_location("subject", MODULE)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REPO = Path(__file__).resolve().parents[2]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.hashes = c.capture(REPO)
        cls.contract = c.extract(cls.data)

    def assertNear(self, a, b, tolerance=1e-8):
        self.assertTrue(c.close(a, b, tolerance), (a, b))

    def test_display_reference_all_frames(self):
        actual = c.fk(self.contract, [0]*6)
        for expected, got in zip(self.data["kin"]["joints"], actual["joints"]):
            self.assertNear(got["origin_m"], [x/1000 for x in expected["origin_mm"]])
            self.assertNear(got["axis_world"], expected["axis_world"])
            self.assertNear(got["rotation_world"], expected["R_child"])

    def test_geometric_zero_independent_straight_chain(self):
        actual = c.fk(self.contract, c.geometric_to_delta(self.contract, [0]*6))
        for got, expected in zip(actual["joints"], [[0,0,.096],[0,0,.174],[.165,0,.174],[.305,0,.174],[.383,0,.174],[.523,0,.174]]):
            self.assertNear(got["origin_m"], expected)
            self.assertNear(got["rotation_world"], c.I)
        self.assertNear(actual["ring_reference_m_not_tcp"], [.555,0,.174])

    def test_all_axis_position_and_orientation_derivatives(self):
        for q in ([0]*6, [.21,-.16,.3,-.42,.27,.13]):
            base = c.fk(self.contract, q)
            for i in range(6):
                h = 1e-6
                plus, minus = list(q), list(q)
                plus[i] += h
                minus[i] -= h
                a, b = c.fk(self.contract, plus), c.fk(self.contract, minus)
                world_axis = base["joints"][i]["axis_world"]
                origin = base["joints"][i]["origin_m"]
                lever = [x-y for x,y in zip(base["ring_reference_m_not_tcp"], origin)]
                self.assertNear([(x-y)/(2*h) for x,y in zip(a["ring_reference_m_not_tcp"], b["ring_reference_m_not_tcp"])], cross(world_axis, lever), 1e-7)
                r = base["joints"][-1]["rotation_world"]
                ra, rb = a["joints"][-1]["rotation_world"], b["joints"][-1]["rotation_world"]
                for col in range(3):
                    self.assertNear([(ra[row][col]-rb[row][col])/(2*h) for row in range(3)], cross(world_axis, [r[row][col] for row in range(3)]), 1e-7)
                if i == 5:
                    self.assertNear(cross(world_axis, lever), [0,0,0])

    def test_random_poses_rigid_lengths_and_rotations(self):
        rng = random.Random(20261023)
        for _ in range(80):
            result = c.fk(self.contract, [rng.uniform(-2,2) for _ in range(6)])
            previous = [0.,0.,0.]
            for got, joint in zip(result["joints"], self.contract["joints"]):
                self.assertNear(sum((x-y)**2 for x,y in zip(got["origin_m"], previous)), sum(x*x for x in joint["offset_parent_m"]))
                self.assertNear(c.mm(c.transpose(got["rotation_world"]), got["rotation_world"]), c.I)
                previous = got["origin_m"]

    def test_unknowns_and_native_sign_not_invented(self):
        self.assertIsNone(self.contract["tcp"])
        self.assertIsNone(self.contract["gripper"])
        self.assertFalse(self.contract["physical_approval"])
        for j in self.contract["joints"]:
            self.assertIsNone(j["native_positive_angle_to_delta"])
            self.assertIsNone(j["mechanical_limits_rad"])
            self.assertTrue(all(x is None for x in j["motor"].values()))
        self.assertEqual(self.contract["joints"][2]["packaging_output_side_sign"], -1)

    def test_bad_source_shapes_frames_and_identity(self):
        changes = [
            ("kin", lambda d: d.update(units="m")),
            ("kin", lambda d: d.update(joint_count=True)),
            ("kin", lambda d: d["joints"][1].update(name="J1")),
            ("kin", lambda d: d["joints"][1].update(parent="Base")),
            ("kin", lambda d: d["joints"][0].update(axis_world=[0,0,2])),
            ("kin", lambda d: d["joints"][0].update(origin_mm=[True,0,96])),
            ("kin", lambda d: d["joints"][0].update(R_child=[[1,0,0],[0,1,0],[0,0,-1]])),
            ("kin", lambda d: d["joints"][0].update(R_parent=[[1,0,0],[0,1,0],[0,0,0]])),
            ("kin", lambda d: d["joints"][0].update(pose_deg=math.nan)),
            ("v1", lambda d: d.update(upper_arm_mm=160)),
            ("v1", lambda d: d.update(pose_deg=[0]*6)),
            ("native", lambda d: d["assembly"]["joints"][0].update(values=[.1])),
            ("native", lambda d: d["assembly"]["joints"][0]["a"].update(occurrence=999)),
            ("native", lambda d: d["assembly"]["joints"][0].update(kind="fixed")),
            ("native", lambda d: d["occurrences"][0]["transform"][0].__setitem__(3, 1)),
            ("native", lambda d: d["components"][0].update(id=True)),
            ("v2", lambda d: d["links"]["tool"].update(ring_t=40)),
            ("v2", lambda d: d["links"]["tool"].update(flange_t=20)),
            ("native", lambda d: next(f for f in d["features"] if f["name"] == "LINK6_TOOL_RING_PROFILE")["sketch"]["points"][-1].update(pos=[68,0])),
            ("native", lambda d: next(f for f in d["features"] if f["name"] == "LINK6_TOOL_RING_REVOLVE").update(suppressed=True)),
            ("native", lambda d: next(f for f in d["features"] if f["name"] == "LINK6_TOOL_RING_REVOLVE").update(sketch=1)),
            ("native", lambda d: next(f for f in d["features"] if f["name"] == "LINK6_TOOL_RING_PROFILE")["plane"]["plane"].update(x_dir=[1,0,0])),
            ("commands", lambda d: d["commands"][next(i for i,x in enumerate(d["commands"]) if x.get("params",{}).get("name") == "LINK6_TOOL_RING_PROFILE")+1]["params"]["points"][2].__setitem__(0,68)),
            ("kin", lambda d: d["joints"][0].update(pose_deg=10**400)),
            ("commands", lambda d: next(x for x in d["commands"] if x["command"] == "joint.as_built")["params"]["at"].update(z=[1,0,0])),
        ]
        for name, change in changes:
            with self.subTest(source=name, change=repr(change)):
                data = copy.deepcopy(self.data)
                change(data[name])
                with self.assertRaises((ValueError, KeyError, TypeError, IndexError)):
                    c.extract(data)
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'['*2000+b'0'+b']'*2000):
            with self.assertRaises(ValueError):
                c.parse(raw)

    def test_bad_angles(self):
        for angles in ([0]*5, [0]*7, [0,0,True,0,0,0], [0,0,math.nan,0,0,0], [math.inf]*6, [10**400]*6):
            with self.assertRaises(ValueError):
                c.fk(self.contract, angles)

    def copied_sources(self, folder):
        for relative in c.INPUTS.values():
            destination = folder / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((REPO/relative).read_bytes())

    def test_bundle_current_failure_and_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/"repo"
            out = Path(temporary)/"out"
            self.copied_sources(root)
            first = c.build(root, out)
            self.assertEqual(c.verify(root,out)["run_id"], first["run_id"])
            artifact = Path(first["bundle"])/"joint-map.md"
            artifact.write_bytes(artifact.read_bytes()+b"tampered")
            with self.assertRaisesRegex(ValueError, "Artifact hash"):
                c.verify(root,out)
            second = c.build(root,out)
            source = root/c.INPUTS["kin"]
            original = source.read_bytes()
            source.write_bytes(b"{}")
            with self.assertRaises(ValueError):
                c.verify(root,out)
            with self.assertRaises((ValueError,KeyError)):
                c.build(root,out)
            self.assertEqual(c.parse((out/"current.json").read_bytes())["status"], "FAILED")
            source.write_bytes(original)
            with self.assertRaisesRegex(ValueError,"not PASS"):
                c.verify(root,out)
            self.assertTrue((Path(second["bundle"])/"manifest.json").exists())
            c.build(root,out)
            current = c.parse((out/"current.json").read_bytes())
            manifest_path = out/"runs"/current["run_id"]/"manifest.json"
            manifest = c.parse(manifest_path.read_bytes())
            manifest["producer_sha256"] = "0"*64
            manifest_path.write_bytes(c.encoded(manifest))
            current["manifest_sha256"] = c.sha(manifest_path.read_bytes())
            c.atomic_json(out/"current.json", current)
            with self.assertRaisesRegex(ValueError,"Producer changed"):
                c.verify(root,out)
            c.build(root,out)
            current = c.parse((out/"current.json").read_bytes())
            current["run_id"] = "../escape"
            c.atomic_json(out/"current.json", current)
            with self.assertRaisesRegex(ValueError,"run ID"):
                c.verify(root,out)
            c.atomic_json(out/"current.json", {"status":"BUILDING","run_id":"0"*32})
            with self.assertRaisesRegex(ValueError,"not PASS"):
                c.verify(root,out)

    def test_native_zip_boundary_and_failed_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, out = Path(temporary)/"repo", Path(temporary)/"out"
            self.copied_sources(root)
            native = root/c.INPUTS["native"]
            original = native.read_bytes()
            for entries in ([('other.json', b'{}')], [('document.json', b'{}'), ('document.json', b'{}')], [('document.json', b' '*(5*1024*1024+1))]):
                native.write_bytes(original)
                c.build(root,out)
                with zipfile.ZipFile(native,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, raw in entries:
                        archive.writestr(name,raw)
                with self.assertRaises(ValueError):
                    c.build(root,out)
                self.assertEqual(c.parse((out/"current.json").read_bytes())["status"],"FAILED")
                native.write_bytes(original)
                with self.assertRaises(ValueError):
                    c.verify(root,out)

    def test_r1_failure_inputs_replace_prior_pass_with_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, out = Path(temporary)/"repo", Path(temporary)/"out"
            self.copied_sources(root)
            native = root/c.INPUTS["native"]
            original_native = native.read_bytes()
            for case in ("huge_integer", "compression", "encrypted", "ring_parameter", "deep_json"):
                self.copied_sources(root)
                c.build(root,out)
                if case == "deep_json":
                    (root/c.INPUTS["kin"]).write_bytes(b'['*2000+b'0'+b']'*2000)
                elif case == "huge_integer":
                    path = root/c.INPUTS["kin"]
                    value = c.parse(path.read_bytes())
                    value["joints"][0]["pose_deg"] = 10**400
                    path.write_bytes(c.encoded(value))
                elif case == "ring_parameter":
                    path = root/c.INPUTS["v2"]
                    value = c.parse(path.read_bytes())
                    value["links"]["tool"]["ring_t"] = 40
                    path.write_bytes(c.encoded(value))
                else:
                    with zipfile.ZipFile(native,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                        archive.writestr("document.json",c.encoded(self.data["native"]))
                    raw = bytearray(native.read_bytes())
                    central = raw.index(b"PK\x01\x02")
                    if case == "compression":
                        struct.pack_into("<H",raw,8,99)
                        struct.pack_into("<H",raw,central+10,99)
                    else:
                        struct.pack_into("<H",raw,6,1)
                        struct.pack_into("<H",raw,central+8,1)
                    native.write_bytes(raw)
                with self.assertRaises(ValueError):
                    c.build(root,out)
                self.assertEqual(c.parse((out/"current.json").read_bytes())["status"],"FAILED",case)
                self.copied_sources(root)
                native.write_bytes(original_native)
                with self.assertRaisesRegex(ValueError,"not PASS"):
                    c.verify(root,out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
