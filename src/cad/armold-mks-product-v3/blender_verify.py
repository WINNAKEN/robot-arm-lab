# -*- coding: utf-8 -*-
"""MP7 C7 저장물 검사 — blender_scene.py 가 저장한 `.blend` 를 다시 열고, 내보낸 GLB 를 새 장면에 다시 가져와 본다(L2 R2-06).

사용: blender.exe --background --factory-startup --python blender_verify.py -- --blender-dir <블렌더 폴더> --model <모델 폴더> --kin <v1 kinematics.json>
      [--scratch-root <격리 작업 뿌리>] [--control blend_move_body|glb_move_body|blend_face_material]
- 바디마다 블렌더 밖에서 직접 읽은 STL 점(mm × 0.001)과 점 하나하나 대조(.blend 2e-7 m · GLB 단정밀도 2e-6 m) — 통계 아님.
- .blend: 재질 슬롯 · 모든 면 색인 0 · Base Color 값 · 부모 · 빈 객체 위치 · 축 · 잠금 · J2 회전(모든 꼭짓점) · 단위 · 객체 종류 수.
- GLB: 바디마다 점 대조 · 재질 색.
결과: <블렌더 폴더>/verify-report.json 의 `checks`(양성 대조는 verify-report-<대조>.json)."""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import checked_dir, checked_file, find_root  # noqa: E402
from stl_topology import mesh_tris_mapped, stl_mesh, topology_ok  # noqa: E402

MAT = {"body": "KMJH_White", "accent": "KMJH_DeepNavy", "frame": "KMJH_CoolGray", "highlight": "KMJH_Mint"}
CONTROLS = {"blend_move_body": "다시 연 .blend 에서 LINK3_ELBOW_HUB 를 1 mm 옮김", "glb_move_body": "다시 가져온 GLB 에서 LINK5_WRIST_BAR 를 1 mm 옮김",
            "blend_face_material": "다시 연 .blend 에서 J2_MODULE 에 둘째 재질 슬롯을 넣고 면 하나의 색인을 1 로",
            "blend_flip_winding": "다시 연 .blend 에서 LINK2_UPPER_BAR 의 면 감김을 모두 뒤집음(점 그대로)",
            "glb_shuffle_faces": "다시 가져온 GLB 의 LINK2_UPPER_BAR 면 연결을 섞음(점 · 면 수 그대로)",
            "glb_extra_mesh": "다시 가져온 GLB 장면에 예정 밖 메시 하나를 더함",
            "blend_degenerate_face": "다시 연 .blend 의 LINK2_UPPER_BAR 에 퇴화 면 [v0, v1, v0] 하나를 더함(점 그대로)",
            "glb_sliver_face": "다시 가져온 GLB 의 LINK2_UPPER_BAR 에 기존 점에서 1e-7 m 떨어진 새 점으로 가는 유한 면 하나를 더함"}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_linear(h):
    return [srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (1, 3, 5)]


def world_points(ob):
    co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", co)
    mw = np.array(ob.matrix_world, dtype=np.float64)
    return co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]


def stl_points_m(path):
    b = Path(path).read_bytes()
    n = struct.unpack_from("<I", b, 80)[0]
    pts = set()
    for i in range(n):
        o = 84 + i * 50 + 12
        for v in range(3):
            pts.add(struct.unpack_from("<3f", b, o + 12 * v))
    return [(x / 1000.0, y / 1000.0, z / 1000.0) for x, y, z in pts]


def match(ref, world):
    def tree(pts):
        t = KDTree(len(pts))
        for i, p in enumerate(pts):
            t.insert(p, i)
        t.balance()
        return t
    wl = [tuple(p) for p in world.tolist()]
    ta, tb = tree(ref), tree(wl)
    return max(max(tb.find(p)[2] for p in ref), max(ta.find(p)[2] for p in wl))


def rot_np(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def base_color(m):
    if m.use_nodes and m.node_tree and "Principled BSDF" in m.node_tree.nodes:
        return list(m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)[:3]
    return list(m.diffuse_color)[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender-dir", required=True, type=Path)
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--kin", required=True, type=Path)
    ap.add_argument("--scratch-root", type=Path, default=None)
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = find_root(Path(__file__).resolve().parent)
    out = checked_dir(a.blender_dir, root, a.scratch_root)
    if a.control and (a.scratch_root is None or Path(a.scratch_root).resolve() not in out.parents):
        raise SystemExit("a verify control runs on a copy under --scratch-root only")
    rep_path =checked_file(out / (f"verify-report-{a.control}.json" if a.control else "verify-report.json"), root, a.scratch_root)
    bd = json.loads((a.model / "bodies.json").read_text(encoding="utf-8"))
    kin = json.loads(a.kin.read_text(encoding="utf-8"))
    roles = {b["name"]: b["role"] for b in bd["bodies"]}
    links = {b["name"]: b["link"] for b in bd["bodies"]}
    ref, ref_tris = {}, {}
    for n in roles:
        ref[n], ref_tris[n] = stl_mesh(a.model / "meshes" / f"{n}.stl")
    trees = {}
    for n, pts in ref.items():
        tr = KDTree(len(pts))
        for i, q in enumerate(pts):
            tr.insert(q, i)
        tr.balance()
        trees[n] = tr

    def topo(n, o, tol):
        polys = [list(pg.vertices) for pg in o.data.polygons]
        tris, bad, nontri, collapsed = mesh_tris_mapped([tuple(q) for q in world_points(o).tolist()], polys, trees[n], tol)
        return {"stl_triangles": sum(ref_tris[n].values()), "faces": len(polys), "triangles": sum(tris.values()), "unmapped": bad, "non_triangles": nontri,
                "collapsed": collapsed, "ok": topology_ok(ref_tris[n], polys, tris, bad, nontri, collapsed)}
    rep = {"control": a.control, "blend": {}, "glb": {}}

    # ---- .blend 다시 열기 ----
    bpy.ops.wm.open_mainfile(filepath=str(out / "kmjh-arm-v3.blend"))
    objs = {n: bpy.data.objects.get(n) for n in roles}
    if a.control == "blend_move_body":
        objs["LINK3_ELBOW_HUB"].location.x += 0.001
    if a.control == "blend_face_material":
        o = objs["J2_MODULE"]
        o.data.materials.append(bpy.data.materials["KMJH_Mint"])
        o.data.polygons[0].material_index = 1
    if a.control == "blend_flip_winding":
        objs["LINK2_UPPER_BAR"].data.flip_normals()
    if a.control == "blend_degenerate_face":
        me = objs["LINK2_UPPER_BAR"].data
        verts = [tuple(v.co) for v in me.vertices]
        faces = [list(pg.vertices) for pg in me.polygons] + [[0, 1, 0]]
        me.clear_geometry()
        me.from_pydata(verts, [], faces)
        me.update()
    bpy.context.view_layer.update()
    missing = sorted(n for n, o in objs.items() if o is None)
    shapes, mats = {}, {}
    for n, o in objs.items():
        if o is None:
            continue
        err = match(ref[n], world_points(o))
        shapes[n] = {"max_nearest_m": err, "ok": err <= 2e-7, "topology": topo(n, o, 2e-7)}
        slots = [m.name for m in o.data.materials]
        cerr = max(abs(x - y) for x, y in zip(base_color(o.data.materials[0]), hex_linear(bd["colors"][roles[n]]))) if slots else 1.0
        idx_ok = all(p.material_index == 0 for p in o.data.polygons)
        mats[n] = {"slots": slots, "err": cerr, "face_index_0": idx_ok, "ok": slots == [MAT[roles[n]]] and cerr <= 1e-6 and idx_ok}
    base = bpy.data.objects.get("KMJH_ARM_BASE")
    emp = [bpy.data.objects.get(f"JOINT_J{k}") for k in range(1, 7)]
    parents = {n: (o.parent.name if o and o.parent else None) == ("KMJH_ARM_BASE" if links[n] == 0 else f"JOINT_J{links[n]}") for n, o in objs.items()}
    chain_ok = base is not None and base.parent is None and all(
        e is not None and e.parent == (base if i == 0 else emp[i - 1]) and tuple(e.lock_rotation) == (True, True, False)
        and tuple(e.lock_location) == (True, True, True) for i, e in enumerate(emp))
    jrows = []
    for k, (e, j) in enumerate(zip(emp, kin["joints"]), start=1):
        mw = np.array(e.matrix_world)
        jrows.append({"joint": k, "origin_err_m": float(np.linalg.norm(mw[:3, 3] - np.asarray(j["origin_mm"]) / 1000.0)),
                      "axis_err": float(np.max(np.abs(mw[:3, 2] / np.linalg.norm(mw[:3, 2]) - np.asarray(j["axis_world"])))),
                      "pose_deg_prop": e.get("pose_deg") == j["pose_deg"], "rot_z": float(e.rotation_euler.z)})
    before = {n: world_points(o) for n, o in objs.items() if o}
    emp[1].rotation_euler.z = math.radians(10.0)
    bpy.context.view_layer.update()
    O, A = np.asarray(kin["joints"][1]["origin_mm"]) / 1000.0, np.asarray(kin["joints"][1]["axis_world"])
    R = rot_np(A, 10.0)
    rot_err = 0.0
    for n, o in objs.items():
        if o is None:
            continue
        want = (before[n] - O) @ R.T + O if links[n] >= 2 else before[n]
        rot_err = max(rot_err, float(np.max(np.linalg.norm(world_points(o) - want, axis=1))))
    emp[1].rotation_euler.z = 0.0
    bpy.context.view_layer.update()
    types = {}
    for ob in bpy.context.scene.objects:
        types[ob.type] = types.get(ob.type, 0) + 1
    blend_mesh_names = {ob.name for ob in bpy.context.scene.objects if ob.type == "MESH"}
    rep["blend"] = {"missing": missing, "mesh_names_extra": sorted(blend_mesh_names - set(roles) - {"STUDIO_FLOOR"}), "shapes": shapes, "materials": mats, "parents_ok": all(parents.values()), "chain_ok": chain_ok, "joints": jrows,
                    "rotation_J2_err_m": rot_err, "types": types,
                    "units": [bpy.context.scene.unit_settings.system, bpy.context.scene.unit_settings.scale_length]}

    # ---- GLB 다시 가져오기(빈 장면) ----
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out / "kmjh-arm-v3.glb"))
    gl = {n: bpy.data.objects.get(n) for n in roles}
    if a.control == "glb_move_body" and gl.get("LINK5_WRIST_BAR"):
        gl["LINK5_WRIST_BAR"].location.x += 0.001
        bpy.context.view_layer.update()
    if a.control == "glb_shuffle_faces" and gl.get("LINK2_UPPER_BAR"):
        import random
        me = gl["LINK2_UPPER_BAR"].data
        verts = [tuple(v.co) for v in me.vertices]
        flat = [i for pg in me.polygons for i in pg.vertices]
        random.Random(42).shuffle(flat)
        faces = [flat[i:i + 3] for i in range(0, len(flat), 3)]
        me.clear_geometry()
        me.from_pydata(verts, [], faces)
        me.update()
    if a.control == "glb_extra_mesh":
        bpy.ops.mesh.primitive_cube_add(size=0.01)
    if a.control == "glb_sliver_face" and gl.get("LINK2_UPPER_BAR"):
        me = gl["LINK2_UPPER_BAR"].data
        verts = [tuple(v.co) for v in me.vertices]
        a0, a1 = verts[0], verts[1]
        verts.append((a1[0] + 1e-7, a1[1], a1[2]))             # 기존 점 a1 곁(1e-7) — 번호 사상에서 a1 과 합쳐짐
        faces = [list(pg.vertices) for pg in me.polygons] + [[0, 1, len(verts) - 1]]
        me.clear_geometry()
        me.from_pydata(verts, [], faces)
        me.update()
    bpy.context.view_layer.update()
    gmiss = sorted(n for n, o in gl.items() if o is None or o.type != "MESH")
    gm = {}
    for n, o in gl.items():
        if o is None or o.type != "MESH":
            continue
        err = match(ref[n], world_points(o))
        slots = list(o.data.materials)
        cerr = max(abs(x - y) for x, y in zip(base_color(slots[0]), hex_linear(bd["colors"][roles[n]]))) if slots else 1.0
        tp = topo(n, o, 2e-6)
        gm[n] = {"max_nearest_m": err, "color_err": cerr, "topology": tp, "ok": err <= 2e-6 and len(slots) == 1 and cerr <= 1e-4 and tp["ok"]}
    glb_mesh_names = {ob.name for ob in bpy.data.objects if ob.type == "MESH"}
    rep["glb"] = {"missing": gmiss, "bodies": gm, "mesh_names_extra": sorted(glb_mesh_names - set(roles) - {"STUDIO_FLOOR"}),
                  "mesh_count": len(glb_mesh_names)}

    nb = len(roles)
    checks = {
        "C7v_blend_reopens_with_every_body": not missing,
        "C7v_blend_bodies_equal_stl_points": len(shapes) == nb and all(r["ok"] for r in shapes.values()),
        "C7v_blend_triangles_and_winding_equal_stl": len(shapes) == nb and all(r["topology"]["ok"] for r in shapes.values()),
        "C7v_blend_mesh_list_fixed": not rep["blend"]["mesh_names_extra"] and not missing,
        "C7v_blend_materials_slots_face_index_colors": len(mats) == nb and all(r["ok"] for r in mats.values()),
        "C7v_blend_parents_and_lock_chain": all(parents.values()) and chain_ok,
        "C7v_blend_joint_empties": all(r["origin_err_m"] <= 1e-6 and r["axis_err"] <= 1e-6 and r["pose_deg_prop"] and r["rot_z"] == 0.0 for r in jrows),
        "C7v_blend_rotation_J2_all_vertices": rot_err <= 1e-6,
        "C7v_blend_units_and_types": rep["blend"]["units"] == ["METRIC", 1.0] and types == {"MESH": nb + 1, "EMPTY": 7, "LIGHT": 3, "CAMERA": 1},
        "C7v_glb_every_body_equals_stl_points_with_brand_color": not gmiss and len(gm) == nb and all(r["ok"] for r in gm.values()),
        "C7v_glb_mesh_list_fixed": not rep["glb"]["mesh_names_extra"] and not gmiss and rep["glb"]["mesh_count"] == nb + 1,
    }
    rep["checks"] = checks
    rep_path.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    print("VERIFY_CHECKS", json.dumps(checks))
    print("VERIFY_DONE" if all(checks.values()) else "VERIFY_FAILED")


if __name__ == "__main__":
    main()
