# -*- coding: utf-8 -*-
"""MP14 — 감속기(MP6 cycloid-27-v1) 조립도용 분해 그림(Blender · Workbench). 보여 주기 전용 — 치수 원천 아님.

부품 STL(models/cycloid-27-v1/parts — 조립 자리 그대로)을 쌓는 차례대로 위로 띄우고(차례 × GAP), 사는 부품(강철 다월 · 베어링 · 모터)은
cycloid.json · parameters.json 의 치수로 단순 원통 · 고리 · 상자로 그린 뒤 번호를 붙인다. 번호 → 이름 표는 같은 폴더의 parts.json.
색 = 지금까지 뽑은 색(흰 = 바닥판 · 덮개 · 하늘 = 그 밖 인쇄 부품 · 회색 = 강철 · 진회색 = 베어링 · 검정 = 모터).
사용: blender -b --factory-startup --python make_assembly_view.py -- <repo> <out.png> <parts.json>
"""
import json
import math
import sys
from pathlib import Path

import bpy

repo, out_png, out_json = Path(sys.argv[sys.argv.index("--") + 1]), sys.argv[sys.argv.index("--") + 2], Path(sys.argv[sys.argv.index("--") + 3])
M = repo / "models" / "cycloid-27-v1"
C = json.loads((M / "cycloid.json").read_text(encoding="utf-8"))
P = json.loads((repo / "src" / "cad" / "cycloid-27-v1" / "parameters.json").read_text(encoding="utf-8"))
st, rr = C["stack_mm"], C["radii_mm"]
GAP = 26.0
E = float(C["lambda"])

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


WHITE, SKY, STEEL = mat("white", (0.93, 0.93, 0.93)), mat("sky", (0.55, 0.82, 0.90)), mat("steel", (0.62, 0.64, 0.68))
BEAR, MOTOR, INK = mat("bearing", (0.28, 0.30, 0.34)), mat("motor", (0.12, 0.13, 0.15)), mat("ink", (0.05, 0.05, 0.05))


def put(o, material, k):
    o.data.materials.clear()
    o.data.materials.append(material)
    o.location.z += k * GAP
    return o


def stl(name, material, k):
    bpy.ops.wm.stl_import(filepath=str(M / "parts" / f"{name}.stl"))
    return put(bpy.context.selected_objects[0], material, k)


def cyl(r, z0, z1, material, k, x=0.0, y=0.0, r_in=None, n=64):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=z1 - z0, location=(x, y, (z0 + z1) / 2), vertices=n)
    o = put(bpy.context.object, material, k)
    if r_in:
        bpy.ops.mesh.primitive_cylinder_add(radius=r_in, depth=z1 - z0 + 1, location=(x, y, (z0 + z1) / 2 + k * GAP), vertices=n)
        cut = bpy.context.object
        cut.hide_render = True
        md = o.modifiers.new("hole", "BOOLEAN")
        md.operation, md.object = "DIFFERENCE", cut
    return o


def box(sx, sy, z0, z1, material, k):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (z0 + z1) / 2))
    o = bpy.context.object
    o.scale = (sx, sy, z1 - z0)
    return put(o, material, k)


B = P["bearings"]
labels = []                                                     # (번호, 이름, 높이 z(분해 뒤), 오른쪽 끝 반지름)


def lab(num, name, z0, z1, k, r):
    labels.append((num, name, (z0 + z1) / 2 + k * GAP, r))


# 1 모터(참고 · 몸 40 + 드라이버 13.5 · 파일럿 Ø22 × 2 · 축 Ø5 × 21.5)
mo = P["motor"]
box(mo["frame"], mo["frame"], -40.0, 0.0, MOTOR, -1.4)
box(mo["frame"] - 2, mo["frame"] - 2, -53.5, -40.0, MOTOR, -1.4)
cyl(mo["pilot_dia"] / 2, 0.0, mo["pilot_height"], MOTOR, -1.4)
cyl(mo["shaft_dia"] / 2, 0.0, mo["shaft_length"], STEEL, -1.4, n=32)
lab(1, "motor", -53.5, 0.0, -1.4, mo["frame"] / 2)
# 2 바닥판 · 3 고정 핀 28
stl("HOUSING_BASE", WHITE, 0)
lab(2, "HOUSING_BASE", *st["ring_pin_hole_base"], 0, rr["outer"])
N = P["ring"]["pins"] if "pins" in P.get("ring", {}) else 28
for i in range(N):
    a = 2 * math.pi * i / N
    cyl(2.0, *st["ring_pin"], STEEL, 0.55, x=rr["ring"] * math.cos(a), y=rr["ring"] * math.sin(a), n=16)
lab(3, "ring pins", *st["ring_pin"], 0.55, rr["ring"] + 2)
# 4 아래 편심 축
stl("CAM_LOWER", SKY, 1.7)
lab(4, "CAM_LOWER", *st["cam_lower"], 1.7, 7)
# 5 원판 1 + 6 6801 #1
d1 = stl("DISC_1", SKY, 2.7)
x1 = (d1.bound_box[0][0] + d1.bound_box[6][0]) / 2
lab(5, "DISC_1", *st["disc1"], 2.7, 27)
cyl(B["disc"]["od"] / 2, *st["disc_bearing1"], BEAR, 3.0, x=x1, r_in=B["disc"]["id"] / 2)
lab(6, "6801", *st["disc_bearing1"], 3.0, 10.5 + abs(x1))
# 7 위 편심 축
stl("CAM_UPPER", SKY, 3.6)
lab(7, "CAM_UPPER", *st["cam_upper"], 3.6, 7)
# 8 원판 2(180°) + 6 6801 #2
d2 = stl("DISC_2", SKY, 4.6)
x2 = (d2.bound_box[0][0] + d2.bound_box[6][0]) / 2
lab(8, "DISC_2", *st["disc2"], 4.6, 27)
cyl(B["disc"]["od"] / 2, *st["disc_bearing2"], BEAR, 4.9, x=x2, r_in=B["disc"]["id"] / 2)
# 9 와셔
stl("WASHER", SKY, 5.4)
lab(9, "WASHER", *st["washer"], 5.4, 7.2)
# 10 캐리어 + 11 출력 핀 6 + 12 6800
stl("CARRIER", SKY, 6.5)
lab(10, "CARRIER", *st["carrier_plate"], 6.5, 22.5)
op = P["output_pins"]
for i in range(op["count"]):
    a = 2 * math.pi * i / op["count"] + math.radians(op["phase_deg"])
    cyl(op["dia"] / 2, *st["output_pin"], STEEL, 6.5, x=op["radius"] * math.cos(a), y=op["radius"] * math.sin(a), n=16)
lab(11, "output pins", st["output_pin"][0], st["output_pin"][0] + 6, 6.5, op["radius"] + 2)
cyl(B["shaft_end"]["od"] / 2, *st["shaft_bearing"], BEAR, 7.2, r_in=B["shaft_end"]["id"] / 2)
lab(12, "6800", *st["shaft_bearing"], 7.2, B["shaft_end"]["od"] / 2)
# 13 덮개 + 14 6808
stl("HOUSING_CAP", WHITE, 8.4)
lab(13, "HOUSING_CAP", *st["cap"], 8.4, rr["outer"])
cyl(B["output"]["od"] / 2, *st["output_bearing"], BEAR, 9.2, r_in=B["output"]["id"] / 2)
lab(14, "6808", *st["output_bearing"], 9.2, B["output"]["od"] / 2)
# 15 누름 고리 · 16 출력 플랜지
stl("RETAINER", SKY, 9.9)
lab(15, "RETAINER", *st["retainer"], 9.9, rr["retainer_out"])
stl("OUTPUT_FLANGE", SKY, 10.7)
lab(16, "OUTPUT_FLANGE", st["flange"][0], st["flange"][1], 10.7, 22)

# 번호 + 끌줄(오른쪽 x 로)
XL = 62.0
for num, _name, z, r in labels:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=XL - r - 3, location=((XL + r - 3) / 2, 0, z), rotation=(0, math.pi / 2, 0), vertices=8)
    put(bpy.context.object, INK, 0)
    bpy.ops.object.text_add(location=(XL, 0, z - 3.5))
    t = bpy.context.object
    t.data.body = str(num)
    t.data.size = 9
    t.data.extrude = 0.2
    t.rotation_euler = (math.pi / 2, 0, 0)
    put(t, INK, 0)

# 카메라(정투영 · 앞 아래쪽이 아니라 앞에서 조금 위) · Workbench
zs = [z for _n, _m, z, _r in labels]
zc, h = (min(zs) + max(zs)) / 2, max(zs) - min(zs) + 90
cam_data = bpy.data.cameras.new("cam")
cam_data.type, cam_data.ortho_scale = "ORTHO", h * 1.02
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
d = (0.35, -1.0, 0.32)
nd = math.sqrt(sum(v * v for v in d))
cam.location = (12 + 600 * d[0] / nd, 600 * d[1] / nd, zc + 600 * d[2] / nd)
tgt = bpy.data.objects.new("tgt", None)
sc.collection.objects.link(tgt)
tgt.location = (12, 0, zc)
c = cam.constraints.new("TRACK_TO")
c.target, c.track_axis, c.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
sc.camera = cam
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light, sh.color_type, sh.show_object_outline, sh.show_cavity = "STUDIO", "MATERIAL", True, True
sc.world = bpy.data.worlds.new("w")
sc.world.color = (1, 1, 1)
sc.render.resolution_x, sc.render.resolution_y = 1100, int(1100 * h / 150)
sc.render.resolution_y = min(sc.render.resolution_y, 2600)
sc.render.filepath = out_png
bpy.ops.render.render(write_still=True)
out_json.write_text(json.dumps([{"no": n, "name": m} for n, m, _z, _r in labels], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("rendered", out_png, len(labels))
