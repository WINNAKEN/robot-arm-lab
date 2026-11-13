# -*- coding: utf-8 -*-
"""MP10 — J5 손목 v1 보기 렌더(블렌더 명령줄 · 새 장면 · 저장 안 함). 단위 = mm(블렌더 1 = 1 mm).

샷: assembled(조립) · exploded(분해) · open(반쪽 B 빼고 속 보기) · in_arm(v3 링크 0 ~ 3 + 모듈 · 표시 자세 — 링크 4 ~ 6 의 v3 덩어리는 뺌).
색 = KMJH(반쪽 흰 · 덮개 남 · 허브 회 · MP6 은 연한 회색 · 모터 · 드라이버 가정 상자는 짙은 회색).
사용: blender -b --factory-startup --python blender_j5.py -- --scratch-root <작업 뿌리> [--samples 48]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True                      # 블렌더 파이썬은 -B 가 없다 — 이 폴더에 __pycache__ 를 남기지 않게(검토 R-13)
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

PARTS = {"J5_STATOR_A": "#FFFFFF", "J5_STATOR_B": "#FFFFFF", "J5_REAR_COVER": "#0B2545", "J5_OUTPUT_HUB": "#6B7280"}
MP6 = ["HOUSING_BASE", "HOUSING_CAP", "RETAINER", "OUTPUT_FLANGE"]
MP6_COLOR, BOX_COLOR, ARM_ALPHA = "#C9CED6", "#3A3F47", 1.0


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"scratch": None, "samples": 48, "w": 1600, "h": 1200}
    for i, a in enumerate(argv):
        if a == "--scratch-root":
            out["scratch"] = Path(argv[i + 1])
        if a == "--samples":
            out["samples"] = int(argv[i + 1])
    return out


def hex_rgba(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


def material(name, hexcol, rough=0.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_rgba(hexcol)
    b.inputs["Roughness"].default_value = rough
    return m


def load(path, name, mat):
    bpy.ops.wm.stl_import(filepath=str(path))
    ob = bpy.context.selected_objects[0]
    ob.name = name
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def box(name, lo, hi, mat):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.active_object
    ob.name = name
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    ob.scale = tuple(hi - lo)
    ob.location = tuple((hi + lo) / 2)
    ob.data.materials.append(mat)
    return ob


def bounds(obs):
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, (hi - lo).length


def aim(cam, target, direction, dist):
    d = Vector(direction).normalized()
    cam.location = target + d * dist
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()


def main():
    a = args()
    root = guard.find_root(HERE)
    out_dir = guard.checked_dir(root / "models" / "j5-wrist-v1" / "renders", root, a["scratch"])
    out_dir.mkdir(parents=True, exist_ok=True)
    P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    mot = json.loads((HERE / P["sources"]["motor_ledger"]).resolve().read_text(encoding="utf-8"))["items"]
    v1 = (HERE / P["sources"]["v1_dir"]).resolve()
    kin = json.loads((v1 / "kinematics.json").read_text(encoding="utf-8"))
    p1 = json.loads((v1 / "parameters.json").read_text(encoding="utf-8"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = a["samples"]
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = a["w"], a["h"], 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 92
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = hex_rgba("#EEF1F5")
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    sun = bpy.data.objects.new("SUN", bpy.data.lights.new("SUN", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    scene.collection.objects.link(sun)
    cam_data = bpy.data.cameras.new("CAM")
    cam_data.lens = 70
    cam_data.clip_start, cam_data.clip_end = 1.0, 20000.0
    cam = bpy.data.objects.new("CAM", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    mats = {n: material(n, c) for n, c in PARTS.items()}
    m_mp6, m_box, m_arm = material("MP6", MP6_COLOR, 0.6), material("BOX", BOX_COLOR, 0.35), material("ARM", "#F4F6F8", 0.5)
    model = root / "models" / "j5-wrist-v1" / "parts"
    mp6_dir = (HERE / P["sources"]["reducer_parts"]).resolve()
    obs = {n: load(model / f"{n}.stl", n, mats[n]) for n in PARTS}
    for n in MP6:
        obs[n] = load(mp6_dir / f"{n}.stl", n, m_mp6)
    f = float(mot["frame"]["value"]) / 2
    bl, gap, ol, dw = (float(mot[k]["value"]) for k in ("body_length", "motor_driver_gap", "overall_length", "driver_width"))
    obs["MOTOR"] = box("MOTOR", (-f, -f, -bl), (f, f, 0.0), m_box)
    obs["DRIVER"] = box("DRIVER", (-dw / 2, -dw / 2, -ol), (dw / 2, dw / 2, -(bl + gap)), m_box)
    module = list(obs.values())
    for o in module:
        o.matrix_world = Matrix.Identity(4) @ o.matrix_world

    report = {"shots": {}, "note": "모듈 좌표 = MP6 좌표(z = J5 축) · in_arm = 표시 자세(v1 kinematics) · 링크 4 ~ 6 의 v3 덩어리는 뺌"}

    def shot(name, direction, objs, scale=1.15):
        c, size = bounds(objs)
        cam_data.sensor_fit = "HORIZONTAL"
        fov_x = cam_data.angle
        fov_y = 2 * math.atan(math.tan(fov_x / 2) * a["h"] / a["w"])        # 4:3 화면의 세로 화각(좁은 쪽)으로 거리 — 가로로 재면 위아래가 잘림
        aim(cam, c, direction, size * scale / (2 * math.tan(min(fov_x, fov_y) / 2)))
        sun.rotation_euler = (Vector(direction).to_track_quat("Z", "Y").to_euler())
        path = guard.checked_file(out_dir / f"{name}.jpg", root, a["scratch"])
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        report["shots"][name] = {"direction": list(direction), "objects": sorted(o.name for o in objs if not o.hide_render)}

    # 1 조립
    shot("assembled", (1.2, -1.6, 0.9), module)
    # 2 분해
    base = {o.name: o.location.copy() for o in module}
    obs["J5_STATOR_A"].location.x -= 45
    obs["J5_STATOR_B"].location.x += 45
    obs["J5_REAR_COVER"].location.z -= 35
    obs["J5_OUTPUT_HUB"].location.z += 30
    shot("exploded", (1.2, -1.6, 0.9), module, 1.05)
    for o in module:
        o.location = base[o.name]
    # 3 속 보기(반쪽 B · 덮개 숨김)
    obs["J5_STATOR_B"].hide_render = obs["J5_REAR_COVER"].hide_render = True
    shot("open", (1.6, -1.0, -0.6), [o for o in module if not o.hide_render])
    obs["J5_STATOR_B"].hide_render = obs["J5_REAR_COVER"].hide_render = False
    # 4 팔 안 자리(표시 자세)
    J4 = kin["joints"][3]
    R4, O4 = np.asarray(J4["R_child"], float), np.asarray(J4["origin_mm"], float)
    Mm = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])
    t_m = np.array([float(p1["wrist_offsets_mm"][0]), float(P["placement"]["motor_face_from_joint_along_axis"]), 0.0])
    Rw, tw = R4 @ Mm, O4 + R4 @ t_m
    T = Matrix([[*Rw[0], tw[0]], [*Rw[1], tw[1]], [*Rw[2], tw[2]], [0, 0, 0, 1]])
    for o in module:
        o.matrix_world = T @ o.matrix_world
    v3 = root / "models" / "armold-mks-product-v3"
    bodies = json.loads((v3 / "bodies.json").read_text(encoding="utf-8"))["bodies"]
    arm = []
    for b in bodies:
        if b["link"] <= 3:
            arm.append(load(v3 / "meshes" / f"{b['name']}.stl", "V3_" + b["name"], material("V3_" + b["name"], b["color"], 0.5)))
    shot("in_arm", (0.4, -1.6, 0.7), arm + module, 1.0)
    report["module_to_world"] = {"R": Rw.tolist(), "t_mm": tw.tolist()}
    report["samples"] = a["samples"]
    guard.write_bytes(out_dir / "render-report.json", (json.dumps(report, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, a["scratch"])
    print("RENDER_DONE", sorted(report["shots"]))


if __name__ == "__main__":
    main()
