# -*- coding: utf-8 -*-
"""MP7 블렌더 장면 — 외장 v3(KMJH)의 바디 STL 을 가져와 브랜드 재질 · 관절 빈 객체 · 조명 · 카메라를 붙이고 렌더 · .blend · GLB 를 만든다.

사용(화면 없이):
  blender.exe --background --factory-startup --python blender_scene.py -- --model <모델 폴더> --kin <v1 kinematics.json> --out <블렌더 폴더>
      [--samples 128] [--width 1600] [--height 1200] [--scratch-root <저장소 밖 작업 뿌리>] [--control <양성 대조>]

- 단위: 블렌더 = m(STL 의 mm × 0.001). 세계 좌표는 SolidCraft 조립(표시 자세) 그대로.
- 관절 빈 객체 JOINT_J1 … J6: 위치 = v1 관절 원점 · 로컬 Z = v1 관절 축. 관절의 자리 · 방향은 부모 역행렬에 두고 빈 객체 자신의 변환은 단위 —
  Z 회전 θ = 관절 축 둘레 θ. 링크 k 의 객체는 JOINT_Jk 의 자식(링크 0 = KMJH_ARM_BASE). **회전 0 = 표시 자세**(v1 pose_deg) · 기하 영점(q = 0)은
  Z 회전 = −pose_deg(빈 객체의 사용자 속성 `pose_deg`). URDF 를 대신하지 않는다(보기 · 렌더용 · 관절 범위 · 질량 · 충돌 없음 · 회전 시험은 충돌 검사가 아님).
- 검사(C7)는 `scene-report.json` 의 `checks`. 저장한 .blend · GLB 를 다시 여는 검사는 blender_verify.py."""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import checked_dir, checked_file, find_root  # noqa: E402
from stl_topology import mesh_tris_mapped, stl_mesh, topology_ok  # noqa: E402

ROLE_LOOK = {   # 역할 → (재질 이름, 거칠기) — 색은 bodies.json 의 브랜드 값
    "body": ("KMJH_White", 0.32),
    "accent": ("KMJH_DeepNavy", 0.38),
    "frame": ("KMJH_CoolGray", 0.42),
    "highlight": ("KMJH_Mint", 0.30),
}
CONTROLS = {
    "no_scale": "STL 을 mm 그대로(0.001 을 빠뜨림) — C7 메시 위치 검사가 잡아야 함",
    "flip_axis": "JOINT_J3 의 Z 를 반대로 — 빈 객체 축 검사 · 회전 검사가 잡아야 함",
    "wrong_parent": "링크 3 객체를 JOINT_J2 에 붙임 — 부모 검사 · 회전 검사가 잡아야 함",
    "mixed_material": "J2_MODULE 에 민트 재질 — 재질 검사가 잡아야 함",
    "hide_robot": "로봇을 렌더에서 숨김 — 렌더에 로봇이 보이는지 검사가 잡아야 함",
    "nudge_vertex": "J2_MODULE 꼭짓점 하나를 1 mm 옮김(점 수 · 상자 · 평균은 거의 같음) — 점 대조가 잡아야 함",
    "hide_body_white": "흰 몸체(역할 body)만 렌더에서 숨김 — 남색 · 민트는 그대로 보임(가시성 검사가 잡아야 함)",
    "camera_away": "정면 3/4 카메라를 로봇 반대쪽으로 — 가시성 검사가 잡아야 함",
    "flip_winding": "LINK2_UPPER_BAR 의 모든 면 감김을 뒤집음(점은 그대로) — 삼각면 대조가 잡아야 함",
}
COMBINED_DEG = [7.0, -5.0, 9.0, -11.0, 6.0, -8.0]


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--kin", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--scratch-root", type=Path, default=None)
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    ap.add_argument("--light-scale", type=float, default=0.12, help="조명 · 배경 세기 배율(노출 맞춤 — 0.12 = 흰 면이 거의 안 날아감 · 2026-10-27 시험)")
    return ap.parse_args(sys.argv[sys.argv.index("--") + 1:])


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_linear(h):
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (1, 3, 5)) + (1.0,)


def stl_points(path):
    """이진 STL 의 꼭짓점(중복 제거) — 블렌더 밖 기준(mm)."""
    b = Path(path).read_bytes()
    n = struct.unpack_from("<I", b, 80)[0]
    pts = set()
    for i in range(n):
        o = 84 + i * 50 + 12
        for v in range(3):
            pts.add(struct.unpack_from("<3f", b, o + 12 * v))
    return pts


def stats(points):
    pts = list(points)
    n = len(pts)
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    c = [sum(p[i] for p in pts) / n for i in range(3)]
    return n, lo, hi, c


def material(name, color_hex, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_linear(color_hex)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.35     # 밝은 배경이 비쳐 남색 · 민트가 옅어지지 않게
    m.diffuse_color = hex_linear(color_hex)
    m["brand_hex"] = color_hex
    return m


def import_stl(path, name, scale):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(path), global_scale=scale)
    new = [o for o in bpy.data.objects if o not in before]
    assert len(new) == 1, (path, len(new))
    ob = new[0]
    ob.name = name
    ob.data.name = name
    ob.data.transform(ob.matrix_basis)         # 가져오기가 축척을 객체에 둔다 → 메시 자료에 굽고 객체 변환은 단위로
    ob.matrix_basis = Matrix.Identity(4)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-9)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def basis_from_axis(z, hint):
    z = Vector(z).normalized()
    h = Vector(hint)
    x = (h - z * h.dot(z))
    x.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def parent_keep(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def world_points(ob):
    """객체의 세계 꼭짓점(numpy N × 3 · float64)."""
    import numpy as np
    co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(ob.matrix_world, dtype=np.float64)
    return co @ mw[:3, :3].T + mw[:3, 3]


def match_points(ref_pts, world):
    """STL 점(블렌더 밖에서 읽은 m) ↔ 블렌더 세계 꼭짓점 — 점 수 · 양방향 최근접 거리 최대(m). 통계(상자 · 평균)가 아니라 점 하나하나."""
    from mathutils.kdtree import KDTree

    def tree(pts):
        t = KDTree(len(pts))
        for i, p in enumerate(pts):
            t.insert(p, i)
        t.balance()
        return t
    wl = [tuple(p) for p in world.tolist()]
    ta, tb = tree(ref_pts), tree(wl)
    d1 = max(tb.find(p)[2] for p in ref_pts)
    d2 = max(ta.find(p)[2] for p in wl)
    return len(ref_pts), len(wl), max(d1, d2)


def rot_np(axis, deg):
    import numpy as np
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def main():
    a = args()
    root = find_root(Path(__file__).resolve().parent)
    out = checked_dir(a.out, root, a.scratch_root)
    if a.control:
        s = Path(a.scratch_root).resolve() if a.scratch_root else None
        if s is None or s not in out.parents:
            raise SystemExit("a control scene goes under --scratch-root only")

    def F_(p):
        return checked_file(p, root, a.scratch_root)
    out.mkdir(parents=True, exist_ok=True)
    bd = json.loads((a.model / "bodies.json").read_text(encoding="utf-8"))
    kin = json.loads(a.kin.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "MILLIMETERS"
    report = {"control": a.control, "mesh_import": {}, "mesh_after_parent": {}, "triangles": {}, "materials": {}, "parents": {}, "joints": [], "rotation_tests": [],
              "combined_pose": {}, "zero_pose": [], "renders": {}, "object_types": {}}

    mats = {role: material(nm, bd["colors"][role], rough) for role, (nm, rough) in ROLE_LOOK.items()}
    ref, ref_tris = {}, {}
    objs = {}
    for b in bd["bodies"]:
        path = a.model / "meshes" / f"{b['name']}.stl"
        ob = import_stl(path, b["name"], 1.0 if a.control == "no_scale" else 0.001)
        role = "highlight" if (a.control == "mixed_material" and b["name"] == "J2_MODULE") else b["role"]
        ob.data.materials.clear()
        ob.data.materials.append(mats[role])
        ob["link"] = b["link"]
        ob["role"] = b["role"]
        objs[b["name"]] = ob
        ref[b["name"]], ref_tris[b["name"]] = stl_mesh(path)
    if a.control == "nudge_vertex":
        objs["J2_MODULE"].data.vertices[0].co.z -= 0.001
    if a.control == "flip_winding":
        objs["LINK2_UPPER_BAR"].data.flip_normals()

    def mesh_rows(key):
        bpy.context.view_layer.update()
        for name, ob in objs.items():
            n0, n1, err = match_points(ref[name], world_points(ob))
            report[key][name] = {"stl_vertices": n0, "blender_vertices": n1, "max_nearest_m": err, "ok": n0 == n1 and err <= 2e-7}

    mesh_rows("mesh_import")
    from mathutils.kdtree import KDTree
    for name, ob in objs.items():
        tree = KDTree(len(ref[name]))
        for i, q in enumerate(ref[name]):
            tree.insert(q, i)
        tree.balance()
        polys = [list(pg.vertices) for pg in ob.data.polygons]
        tris, bad, nontri, collapsed = mesh_tris_mapped([tuple(q) for q in world_points(ob).tolist()], polys, tree, 2e-7)
        report["triangles"][name] = {"stl_triangles": sum(ref_tris[name].values()), "blender_faces": len(polys), "blender_triangles": sum(tris.values()),
                                     "unmapped": bad, "non_triangles": nontri, "collapsed": collapsed,
                                     "ok": topology_ok(ref_tris[name], polys, tris, bad, nontri, collapsed)}
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs.values():
        ob.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(objs.values()))
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))

    # 관절 빈 객체 · 부모 관계
    base = bpy.data.objects.new("KMJH_ARM_BASE", None)
    base.empty_display_type = "PLAIN_AXES"
    base.empty_display_size = 0.05
    scene.collection.objects.link(base)
    empties, prev = [], base
    for k, j in enumerate(kin["joints"], start=1):
        e = bpy.data.objects.new(f"JOINT_J{k}", None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.04
        scene.collection.objects.link(e)
        Rp = Matrix(j["R_parent"])
        ax = Vector(j["axis_world"]) * (-1.0 if (a.control == "flip_axis" and k == 3) else 1.0)
        B = basis_from_axis(ax, Rp.col[0] if abs(Rp.col[0].dot(ax)) < 0.8 else Rp.col[1])
        M = Matrix.Translation(Vector(j["origin_mm"]) / 1000.0) @ B.to_4x4()
        e.parent = prev
        e.matrix_parent_inverse = prev.matrix_world.inverted() @ M
        e.matrix_basis = Matrix.Identity(4)
        e.lock_location = (True, True, True)
        e.lock_rotation = (True, True, False)
        e.lock_scale = (True, True, True)
        e.rotation_mode = "XYZ"
        e["pose_deg"] = float(j["pose_deg"])
        e["note"] = "Z rotation 0 = display pose; geometric zero (q = 0) = Z rotation -pose_deg"
        bpy.context.view_layer.update()
        empties.append(e)
        prev = e
    for b in bd["bodies"]:
        lk = b["link"]
        if a.control == "wrong_parent" and lk == 3:
            lk = 2
        parent_keep(objs[b["name"]], base if lk == 0 else empties[lk - 1])
    bpy.context.view_layer.update()
    mesh_rows("mesh_after_parent")

    # 부모 · 변환
    for name, ob in objs.items():
        want = "KMJH_ARM_BASE" if ob["link"] == 0 else f"JOINT_J{ob['link']}"
        m3 = ob.matrix_world.to_3x3()
        ident = max(abs(m3[i][jj] - (1.0 if i == jj else 0.0)) for i in range(3) for jj in range(3))
        report["parents"][name] = {"parent": ob.parent.name if ob.parent else None, "want": want, "world_rot_scale_identity_err": ident,
                                   "ok": (ob.parent.name if ob.parent else None) == want and ident <= 1e-6}
    chain_ok = base.parent is None and base.matrix_world == Matrix.Identity(4) and all(
        e.parent == (base if i == 0 else empties[i - 1]) and tuple(e.lock_rotation) == (True, True, False) and tuple(e.lock_location) == (True, True, True)
        for i, e in enumerate(empties))

    # 재질: 슬롯 하나 · 모든 면 색인 0 · Base Color 값 = 그 역할의 브랜드 색
    for name, ob in objs.items():
        want = mats[ob["role"]]
        slots = [m.name for m in ob.data.materials]
        col = tuple(ob.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value) if slots else None
        idx_ok = all(p.material_index == 0 for p in ob.data.polygons)
        col_err = max(abs(x - y) for x, y in zip(col, hex_linear(bd["colors"][ob["role"]]))) if col else 1.0
        report["materials"][name] = {"want": want.name, "got": slots, "base_color_err": col_err, "ok": slots == [want.name] and idx_ok and col_err <= 1e-6}

    # 빈 객체 위치 · 축
    for k, (e, j) in enumerate(zip(empties, kin["joints"]), start=1):
        mw = e.matrix_world
        perr = (mw.translation - Vector(j["origin_mm"]) / 1000.0).length
        zerr = max(abs(c) for c in (mw.to_3x3().col[2].normalized() - Vector(j["axis_world"])))
        report["joints"].append({"joint": k, "origin_err_m": perr, "axis_err": zerr, "ok": perr <= 1e-6 and zerr <= 1e-6})   # 블렌더 = 단정밀도

    import numpy as np
    display = {n: world_points(o) for n, o in objs.items()}
    J = [(np.asarray(j["origin_mm"], float) / 1000.0, np.asarray(j["axis_world"], float)) for j in kin["joints"]]   # 블렌더 밖 기준(v1)

    def expected(link, P, deltas):
        """표시 자세의 점들 P(링크 link) — 관절 1 … link 를 deltas 만큼 돌렸을 때. 표시 자세의 축 기준으로 바깥 관절부터 안쪽으로 돌린다."""
        Q = P.copy()
        for k in range(link, 0, -1):
            if deltas[k - 1]:
                O, A = J[k - 1]
                Q = (Q - O) @ rot_np(A, deltas[k - 1]).T + O
        return Q

    def pose_err(deltas):
        for e, d in zip(empties, deltas):
            e.rotation_euler.z = math.radians(d)
        bpy.context.view_layer.update()
        err = 0.0
        for n, ob in objs.items():
            err = max(err, float(np.max(np.linalg.norm(world_points(ob) - expected(ob["link"], display[n], deltas), axis=1))))
        for e in empties:
            e.rotation_euler.z = 0.0
        bpy.context.view_layer.update()
        back = max(float(np.max(np.linalg.norm(world_points(ob) - display[n], axis=1))) for n, ob in objs.items())
        return err, back

    for k in range(1, 7):
        for sgn in (+1, -1):
            d = [0.0] * 6
            d[k - 1] = 10.0 * sgn
            err, back = pose_err(d)
            report["rotation_tests"].append({"joint": k, "deg": 10.0 * sgn, "max_err_m": err, "reset_err_m": back, "ok": err <= 1e-6 and back <= 1e-7})
    err, back = pose_err(COMBINED_DEG)
    report["combined_pose"] = {"deg": COMBINED_DEG, "max_err_m": err, "reset_err_m": back, "ok": err <= 2e-6 and back <= 1e-7}

    # 기하 영점: 모든 관절 −pose_deg → 관절 원점 = v1 길이로 낸 q = 0 순기구학 · 축 = axis_parent_zero
    p = json.loads((a.kin.parent / "parameters.json").read_text(encoding="utf-8"))
    offs = [[0, 0, p["joint1_height_mm"]], [0, 0, p["shoulder_rise_mm"]], [p["upper_arm_mm"], 0, 0], [p["forearm_mm"], 0, 0],
            [p["wrist_offsets_mm"][0], 0, 0], [p["wrist_offsets_mm"][1], 0, 0]]
    fk, acc = [], Vector((0, 0, 0))
    for o in offs:
        acc = acc + Vector(o)
        fk.append(acc / 1000.0)
    for e in empties:
        e.rotation_euler.z = math.radians(-e["pose_deg"])
    bpy.context.view_layer.update()
    for k, (e, want, ax) in enumerate(zip(empties, fk, p["axis_parent_zero"]), start=1):
        mw = e.matrix_world
        perr = (mw.translation - want).length
        zerr = max(abs(c) for c in (mw.to_3x3().col[2].normalized() - Vector(ax)))
        report["zero_pose"].append({"joint": k, "fk_origin_m": list(want), "origin_err_m": perr, "axis_err": zerr, "ok": perr <= 1e-6 and zerr <= 1e-6})

    # 장면: 바닥 · 세계 · 조명 · 카메라
    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.2, 0.0, 0.0))
    fl = bpy.context.active_object
    fl.name = "STUDIO_FLOOR"
    fm = bpy.data.materials.new("STUDIO_FLOOR")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = hex_linear("#D3D9E1")   # 옅은 회청 — 흰 몸체가 바닥과 갈리게
    fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.55
    fl.data.materials.append(fm)
    world = bpy.data.worlds.new("STUDIO_WORLD")
    scene.world = world
    world.use_nodes = True
    wn, wl = world.node_tree.nodes, world.node_tree.links
    bg_light = wn["Background"]                                   # 장면을 비추는 배경(약하게)
    bg_light.inputs["Color"].default_value = hex_linear("#E9EDF2")
    bg_light.inputs["Strength"].default_value = 0.35 * a.light_scale
    bg_cam = wn.new("ShaderNodeBackground")                       # 카메라에 보이는 배경(밝게 — 위쪽 어두운 띠 없이)
    bg_cam.inputs["Color"].default_value = hex_linear("#E9EDF2")
    bg_cam.inputs["Strength"].default_value = 0.75
    lp = wn.new("ShaderNodeLightPath")
    mix = wn.new("ShaderNodeMixShader")
    wl.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    wl.new(bg_light.outputs["Background"], mix.inputs[1])
    wl.new(bg_cam.outputs["Background"], mix.inputs[2])
    wl.new(mix.outputs["Shader"], wn["World Output"].inputs["Surface"])

    def area(name, loc, energy, size, target):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy * a.light_scale, size
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        look_at(lo, target)

    cam_data = bpy.data.cameras.new("CAMERA")
    cam = bpy.data.objects.new("CAMERA", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = a.width, a.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"     # 브랜드 색을 그대로(AgX 는 색을 옅게 만든다)
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    if a.control == "hide_robot":
        for ob in objs.values():
            ob.hide_render = True
    if a.control == "hide_body_white":
        for ob in objs.values():
            if ob["role"] == "body":
                ob.hide_render = True

    def bounds(obs):
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        return (lo + hi) / 2, (hi - lo).length / 2

    robot = set(objs.values())

    def visible_hits(nx=64, ny=48):
        """카메라에서 화면 격자로 광선을 쏘아 처음 맞는 객체를 센다 — 렌더에 숨긴 객체(hide_render)는 맞아도 안 보이는 것으로 친다."""
        dg = bpy.context.evaluated_depsgraph_get()
        frame = [cam.matrix_world @ v for v in cam_data.view_frame(scene=scene)]       # 오른위 · 오른아래 · 왼아래 · 왼위
        o = cam.matrix_world.translation
        tr, br, bl, tl = frame
        hits, robot_rays = {}, 0
        for iy in range(ny):
            for ix in range(nx):
                u, v = (ix + 0.5) / nx, (iy + 0.5) / ny
                top = tl.lerp(tr, u)
                bot = bl.lerp(br, u)
                d = (top.lerp(bot, v) - o).normalized()
                ok, _loc, _n, _i, ob, _m = scene.ray_cast(dg, o, d)
                if ok and ob in robot and not ob.hide_render:
                    robot_rays += 1
                    hits[ob.name] = hits.get(ob.name, 0) + 1
        return hits, robot_rays / (nx * ny)

    def shoot(label, direction, lens, obs, want):
        center, radius = bounds(obs)
        cam_data.lens = lens
        fov = 2 * math.atan(cam_data.sensor_width / 2 / lens) * min(1.0, a.height / a.width)
        cam.location = center + Vector(direction).normalized() * (radius / math.sin(fov / 2) * 0.82)
        look_at(cam, center + (Vector(direction).normalized() * 20.0 if (a.control == "camera_away" and label == "hero") else Vector()))
        bpy.context.view_layer.update()
        hits, frac = visible_hits()
        body_hit = sum(1 for n in hits if objs[n]["role"] == "body")
        path = F_(out / f"render-{label}.png")
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        w, h = img.size
        px = img.pixels[:]
        n = len(px) // 4
        dark = mint = 0
        step = 3
        for i in range(0, n, step):
            r, g, b = px[4 * i], px[4 * i + 1], px[4 * i + 2]
            if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.30 and b > r + 0.08:     # 남색(어둡고 파랑이 빨강보다 뚜렷이 큼 · 회색 그림자 제외)
                dark += 1
            if g > r + 0.15 and g > b + 0.02:                                       # 민트
                mint += 1
        cnt = n // step
        bpy.data.images.remove(img)
        if want == "arm":       # 전체 그림: 로봇이 화면의 5 % 이상 · 바디 20 개 이상 · 흰 몸체 8 개 이상이 광선에 보임
            vis_ok = frac >= 0.05 and len(hits) >= 20 and body_hit >= 8
        else:                   # 글자 그림: 글자 바디 다섯이 모두 보임
            vis_ok = all(nm in hits for nm in want)
        report["renders"][label] = {"file": path.name, "size": [w, h], "robot_ray_fraction": frac, "bodies_hit": len(hits), "white_bodies_hit": body_hit,
                                    "hits": hits, "navy_fraction": dark / cnt, "mint_fraction": mint / cnt,
                                    "ok": [w, h] == [a.width, a.height] and vis_ok and dark / cnt > 0.002 and mint / cnt > 0.0002}

    arm = list(objs.values())
    c0, _r0 = bounds(arm)
    area("KEY_LIGHT", c0 + Vector((-0.9, -1.1, 1.2)), 160, 1.2, c0)
    area("FILL_LIGHT", c0 + Vector((1.2, -0.8, 0.5)), 45, 1.4, c0)
    area("RIM_LIGHT", c0 + Vector((0.3, 1.3, 1.0)), 120, 1.0, c0)

    shoot("zero-pose", (-0.35, -1.0, 0.45), 50, arm, "arm")          # 아직 기하 영점 자세
    for e in empties:
        e.rotation_euler.z = 0.0
    bpy.context.view_layer.update()
    shoot("hero", (-0.55, -1.0, 0.55), 50, arm, "arm")
    shoot("front", (0.0, -1.0, 0.08), 70, arm, "arm")
    face_out = -Matrix(kin["joints"][1]["R_child"]).col[1]     # 상완(링크 2)의 −y = 글자 면의 바깥 법선(표시 자세)
    logo = [n for n in objs if "_LOGO_" in n]
    shoot("logo-detail", face_out + Vector((0, 0, 0.25)), 85, [objs[n] for n in logo], logo)

    types = {}
    for ob in scene.objects:
        types[ob.type] = types.get(ob.type, 0) + 1
    report["object_types"] = types
    bpy.ops.export_scene.gltf(filepath=str(F_(out / "kmjh-arm-v3.glb")), export_format="GLB", use_selection=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(F_(out / "kmjh-arm-v3.blend")), compress=True)

    nb = len(bd["bodies"])
    checks = {
        "C7_meshes_equal_stl_mm_to_m_after_import": len(report["mesh_import"]) == nb and all(r["ok"] for r in report["mesh_import"].values()),
        "C7_meshes_equal_stl_after_parenting": len(report["mesh_after_parent"]) == nb and all(r["ok"] for r in report["mesh_after_parent"].values()),
        "C7_object_types": types == {"MESH": nb + 1, "EMPTY": 7, "LIGHT": 3, "CAMERA": 1}
                           and {o.name for o in scene.objects if o.type == "MESH"} == set(objs) | {"STUDIO_FLOOR"},
        "C7_triangles_and_winding_equal_stl": len(report["triangles"]) == nb and all(r["ok"] for r in report["triangles"].values()),
        "C7_parents_and_lock_chain": chain_ok and all(r["ok"] for r in report["parents"].values()),
        "C7_materials_slot_index_and_base_color": all(r["ok"] for r in report["materials"].values()),
        "C7_joint_empties_at_v1_origins_axes": len(report["joints"]) == 6 and all(r["ok"] for r in report["joints"]),
        "C7_rotations_all_vertices_plus_minus_10": len(report["rotation_tests"]) == 12 and all(r["ok"] for r in report["rotation_tests"]),
        "C7_combined_pose_all_vertices": report["combined_pose"]["ok"],
        "C7_geometric_zero_matches_v1_forward_kinematics": len(report["zero_pose"]) == 6 and all(r["ok"] for r in report["zero_pose"]),
        "C7_renders_size_and_robot_visible": len(report["renders"]) == 4 and all(r["ok"] for r in report["renders"].values()),
        "C7_scene_units_metric_m": scene.unit_settings.system == "METRIC" and abs(scene.unit_settings.scale_length - 1.0) < 1e-12,
    }
    report["checks"] = checks
    report["blender"] = bpy.app.version_string
    F_(out / "scene-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    print("SCENE_CHECKS", json.dumps(checks))
    print("SCENE_DONE" if all(checks.values()) else "SCENE_FAILED")


if __name__ == "__main__":
    main()
