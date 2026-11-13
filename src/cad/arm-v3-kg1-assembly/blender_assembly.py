# -*- coding: utf-8 -*-
"""MP9 — 외장 v3 + 그리퍼 KG1 보기 렌더(계획 051). 커밋된 v3 블렌더 장면(kmjh-arm-v3.blend)을 **읽기만** 하고(저장하지 않음 — 전후 sha256 대조),
그리퍼 부품 STL 을 assembly.json 의 G → 세계(표시 자세) 행렬로 놓은 뒤 J6 빈 객체에 붙여 자세마다 렌더한다. 보기용 — 검사는 assemble.py.

사용(화면 없이):
  blender.exe --background --factory-startup --python blender_assembly.py -- --blend <kmjh-arm-v3.blend> --assembly <assembly.json>
      --check <check.json> --gripper-model <models/kmjh-gripper-v1> --gripper-params <kmjh-gripper-v1/parameters.json>
      --kin <v1 kinematics.json> --poses <gallery_poses.json> --out <렌더 폴더> [--samples 64] [--width 1600] [--height 1200]
      [--only 이름,…] [--scratch-root <작업 뿌리>]

- 벌림 · 손끝 종류 = MP9 parameters.json 의 gripper.render_u · padset(assemble.py 가 같은 벌림을 검사함).
- 서보 · 탄소 관은 그리퍼 렌더(render_gripper.py)와 같은 기준 상자 · 원통(보기용 — 서보는 한 상자: 검사기 기준 입체의 출력 쪽 단차 · 아래 돌기 · 커넥터 자리는 그리지 않음).
- 검사(`render-report.json` 의 checks): 그리퍼 메시 = 부품 STL 을 행렬로 옮긴 점(표시 자세) · 자세마다 그리퍼 점 = 표시 자세 점을 v1 축으로 돌린 값 ·
  렌더마다 크기 · 카메라 광선이 그리퍼와 팔을 봄 · .blend 바뀌지 않음 · 렌더하는 자세가 check.json 에서 검사한 모든 벌림(렌더 벌림 포함)으로
  팔과 겹치지 않고 바닥 여유 안이며 팔끼리도 겹치지 않음(아니면 렌더하지 않고 멈춤)."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
from pathlib import Path  # noqa: E402

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mp9_guard", HERE / "guard.py")
mguard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mguard)

HERO_DIR = (-0.55, -1.0, 0.55)
PRM = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
PADSET = PRM["gripper"]["padset"]
PARTS = {"BASE": ("KMJH_CoolGray", "F"), "JAW_A": ("KMJH_White", "A"), "JAW_B": ("KMJH_White", "B"), "PINION": ("KMJH_DeepNavy", "R"),
         f"PAD_A_{PADSET}": ("KMJH_CoolGray", "A"), f"PAD_B_{PADSET}": ("KMJH_CoolGray", "B")}


def shots():
    """(이름, 자세, 방향, 렌즈 mm, 대상) — 대상 'arm' = 팔 + 그리퍼 · 'tool' = 링크 4 … 6 + 그리퍼."""
    return [
        ("display", "display", HERO_DIR, 50, "arm"),
        ("display-tool", "display", (0.3, -1.0, 0.45), 85, "tool"),
        ("display-tool-back", "display", (1.0, 0.55, 0.35), 85, "tool"),
        ("home", "home", (-0.6, -1.0, 0.4), 50, "arm"),
        ("side-reach", "side-reach", (1.0, -0.55, 0.5), 50, "arm"),
        ("wave", "wave", (-1.0, -0.35, 0.45), 50, "arm"),
    ]


def args():
    ap = argparse.ArgumentParser()
    for k in ("blend", "assembly", "check", "gripper-model", "gripper-params", "kin", "poses", "out"):
        ap.add_argument(f"--{k}", required=True, type=Path)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--only", default=None)
    ap.add_argument("--scratch-root", type=Path, default=None)
    return ap.parse_args(sys.argv[sys.argv.index("--") + 1:])


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rot_np(axis, deg):
    import numpy as np
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def world_points(ob):
    import numpy as np
    co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(ob.matrix_world, dtype=np.float64)
    return co @ mw[:3, :3].T + mw[:3, 3]


def max_nearest(a, b):
    """두 점 묶음의 양방향 가장 가까운 거리의 최대(점 수가 달라도 됨 — STL 가져오기가 점을 합칠 수 있음)."""
    from mathutils.kdtree import KDTree

    def tree(pts):
        t = KDTree(len(pts))
        for i, p in enumerate(pts):
            t.insert(p, i)
        t.balance()
        return t
    al, bl = [tuple(p) for p in a.tolist()], [tuple(p) for p in b.tolist()]
    ta, tb = tree(al), tree(bl)
    return max(max(tb.find(p)[2] for p in al), max(ta.find(p)[2] for p in bl))


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def main():
    import numpy as np
    a = args()
    root = mguard.find_root(HERE)
    out = mguard.checked_dir(a.out, root, a.scratch_root)
    asm = json.loads(a.assembly.read_text(encoding="utf-8"))
    chk = json.loads(a.check.read_text(encoding="utf-8"))
    if not chk.get("all_ok"):
        raise SystemExit("check.json is not all_ok — run assemble.py first")
    P = json.loads(a.gripper_params.read_text(encoding="utf-8"))
    kin = json.loads(a.kin.read_text(encoding="utf-8"))
    poses = {p["name"]: [float(x) for x in p["q_deg"]] for p in json.loads(a.poses.read_text(encoding="utf-8"))["poses"]}
    plan = [s for s in shots() if a.only is None or s[0] in a.only.split(",")]
    u = float(PRM["gripper"]["render_u"])
    checked_u = {float(x) for x in chk.get("openings_checked_u", [])}
    if u not in checked_u:
        raise SystemExit(f"render_u {u} was not checked by assemble.py (openings_checked_u)")
    # 렌더하는 자세는 check.json 에서 검사한 모든 벌림(렌더 벌림 포함)으로 팔과 겹치지 않고 바닥 여유 안 · 팔끼리도 겹치지 않아야 한다
    gal = {}
    for r in chk["gallery"]:
        gal.setdefault(r["pose"], []).append(r)
    for _l, pose, *_ in plan:
        rows = gal.get(pose, [])
        if (not rows or {float(r["u"]) for r in rows} != checked_u
                or any(r["hit"] or not r["floor_ok"] or r["arm_self_hits"] or r["q_deg"] != poses[pose] for r in rows)):
            raise SystemExit(f"pose {pose} is not free in check.json (hit, floor, arm self, missing opening or different q)")
    blend_sha0 = sha(a.blend)
    out.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(a.blend), load_ui=False)
    scene = bpy.context.scene
    arm_objs = {o.name: o for o in scene.objects if o.type == "MESH" and o.name != "STUDIO_FLOOR"}
    empties = [scene.objects[f"JOINT_J{k}"] for k in range(1, 7)]
    cam = scene.objects["CAMERA"]
    lights = [o for o in scene.objects if o.type == "LIGHT"]
    for e in empties:
        e.rotation_euler.z = 0.0
    bpy.context.view_layer.update()

    Mg = np.asarray(asm["mount"]["g_to_world_display"], float)
    R3, t3 = Mg[:3, :3], Mg[:3, 3]
    Mb = Matrix([[R3[i][0], R3[i][1], R3[i][2], t3[i] / 1000.0] for i in range(3)] + [[0, 0, 0, 1]])
    S = Matrix.Scale(0.001, 4)
    L, g, Sv, Rd = P["layout"], P["gear"], P["servo"], P["rod"]
    r_p, zc = g["module"] * g["teeth"] / 2, L["z_c"]

    def local(grp):
        """G 안에서 벌림 u 만큼 움직임(mm) — 그리퍼 검사기 place() 와 같은 뜻: A = −x · B = +x · R = +y 축 둘레 −u / r."""
        if grp == "A":
            return Matrix.Translation((-u, 0, 0))
        if grp == "B":
            return Matrix.Translation((u, 0, 0))
        if grp == "R":
            return Matrix.Translation((0, 0, zc)) @ Matrix.Rotation(-u / r_p, 4, "Y") @ Matrix.Translation((0, 0, -zc))
        return Matrix.Identity(4)

    grip = {}
    report = {"blend": a.blend.name, "blend_sha256": blend_sha0, "assembly_sha256": sha(a.assembly), "check_sha256": sha(a.check), "u": u,
              "padset": PADSET, "params_sha256": sha(HERE / "parameters.json"), "grip_display": {}, "pose_errors": {}, "renders": {}}
    for nm, (mat, grp) in PARTS.items():
        bpy.ops.wm.stl_import(filepath=str(a.gripper_model / "parts" / f"{nm}.stl"))
        ob = bpy.context.selected_objects[0]
        ob.name = f"KG1_{nm}"
        ob.matrix_world = Mb @ S @ local(grp)
        ob.data.materials.clear()
        ob.data.materials.append(bpy.data.materials[mat])
        grip[ob.name] = ob
    # 기준 입체(보기용): 서보 몸통 상자 · 관 넷
    top = L["wall_y"][0]
    bpy.ops.mesh.primitive_cube_add(size=1)
    sv = bpy.context.active_object
    sv.name = "KG1_SERVO"
    ctr = Vector(((-Sv["spline_from_out_end"] + Sv["body"][0] / 2), (top - Sv["body"][2] / 2), zc))
    sv.matrix_world = Mb @ S @ Matrix.Translation(ctr) @ Matrix.Diagonal((Sv["body"][0], Sv["body"][2], Sv["body"][1], 1))
    ms = bpy.data.materials.new("KG1_servo")
    ms.use_nodes = True
    ms.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1)
    sv.data.materials.append(ms)
    grip[sv.name] = sv
    mr = bpy.data.materials.new("KG1_rod")
    mr.use_nodes = True
    mr.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.004, 0.004, 0.004, 1)
    mr.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.35
    for i, yy in enumerate(L["rod_y_a"] + L["rod_y_b"]):
        bpy.ops.mesh.primitive_cylinder_add(radius=Rd["od"] / 2, depth=Rd["length"], vertices=48)
        rc = bpy.context.active_object
        rc.name = f"KG1_ROD_{i}"
        rc.matrix_world = Mb @ S @ Matrix.Translation((0, yy, L["rod_z"])) @ Matrix.Rotation(math.pi / 2, 4, "Y")
        rc.data.materials.append(mr)
        grip[rc.name] = rc
    bpy.context.view_layer.update()

    # 표시 자세 점 검사: 부품 STL 점을 같은 행렬(numpy)로 옮긴 값과 블렌더 메시 점
    def stl_points(p):
        import struct
        b = Path(p).read_bytes()
        n = struct.unpack("<I", b[80:84])[0]
        arr = np.frombuffer(b[84:84 + n * 50], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
        return np.unique(arr["v"].reshape(-1, 3).astype(np.float64), axis=0)
    for nm, (mat, grp) in PARTS.items():
        Lm = np.array(local(grp), dtype=np.float64)
        pts = stl_points(a.gripper_model / "parts" / f"{nm}.stl")
        exp = (pts @ Lm[:3, :3].T + Lm[:3, 3]) @ R3.T / 1000.0 + t3 / 1000.0
        err = max_nearest(exp, world_points(grip[f"KG1_{nm}"]))
        report["grip_display"][nm] = {"max_nearest_m": err, "ok": err <= 2e-7}

    e6 = empties[5]
    for ob in grip.values():
        mw = ob.matrix_world.copy()
        ob.parent = e6
        ob.matrix_parent_inverse = e6.matrix_world.inverted()
        ob.matrix_world = mw
    bpy.context.view_layer.update()
    display = {n: world_points(o) for n, o in grip.items()}
    J = [(np.asarray(j["origin_mm"], float) / 1000.0, np.asarray(j["axis_world"], float)) for j in kin["joints"]]
    pose_deg = [float(j["pose_deg"]) for j in kin["joints"]]

    def set_pose(name):
        deltas = [q - p for q, p in zip(poses[name], pose_deg)]
        for e, d in zip(empties, deltas):
            e.rotation_euler.z = math.radians(d)
        bpy.context.view_layer.update()
        err = 0.0
        for n, ob in grip.items():
            Q = display[n].copy()
            for k in range(6, 0, -1):
                if deltas[k - 1]:
                    O, A = J[k - 1]
                    Q = (Q - O) @ rot_np(A, deltas[k - 1]).T + O
            err = max(err, float(np.max(np.linalg.norm(world_points(ob) - Q, axis=1))))
        report["pose_errors"][name] = {"q_deg": poses[name], "max_err_m": err, "ok": err <= 2e-6}

    # 바닥 멀리 흐리게 · 조명 — MP7 blender_gallery.py 와 같은 값(그 함수를 옮겨 씀 · 장면은 저장하지 않음)
    wn = scene.world.node_tree.nodes
    mixw = [n for n in wn if n.type == "MIX_SHADER"]
    assert len(mixw) == 1, "world should hold one camera-ray mix (blender_scene.py)"
    cam_bg = mixw[0].inputs[2].links[0].from_node
    nt = bpy.data.materials["STUDIO_FLOOR"].node_tree
    N_, L_ = nt.nodes, nt.links
    bsdf, mo = N_["Principled BSDF"], N_["Material Output"]
    geo, flat, ln, mrg = N_.new("ShaderNodeNewGeometry"), N_.new("ShaderNodeVectorMath"), N_.new("ShaderNodeVectorMath"), N_.new("ShaderNodeMapRange")
    flat.operation, ln.operation = "MULTIPLY", "LENGTH"
    flat.inputs[1].default_value = (1.0, 1.0, 0.0)
    mrg.interpolation_type = "SMOOTHSTEP"
    mrg.inputs["From Min"].default_value, mrg.inputs["From Max"].default_value = 0.55, 2.2
    lp, mul, em, mix = N_.new("ShaderNodeLightPath"), N_.new("ShaderNodeMath"), N_.new("ShaderNodeEmission"), N_.new("ShaderNodeMixShader")
    mul.operation = "MULTIPLY"
    cam_bg.inputs["Strength"].default_value = 0.60
    em.inputs["Color"].default_value = tuple(cam_bg.inputs["Color"].default_value)
    em.inputs["Strength"].default_value = 0.60
    for o_, i_ in ((geo.outputs["Position"], flat.inputs[0]), (flat.outputs["Vector"], ln.inputs[0]), (ln.outputs["Value"], mrg.inputs["Value"]),
                   (mrg.outputs["Result"], mul.inputs[0]), (lp.outputs["Is Camera Ray"], mul.inputs[1]), (mul.outputs["Value"], mix.inputs["Fac"]),
                   (bsdf.outputs["BSDF"], mix.inputs[1]), (em.outputs["Emission"], mix.inputs[2]), (mix.outputs["Shader"], mo.inputs["Surface"])):
        L_.new(o_, i_)

    def bounds(obs):
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        return (lo + hi) / 2, (hi - lo).length / 2

    light0 = {lo.name: lo.location.copy() for lo in lights}
    c_light = bounds(list(arm_objs.values()))[0]
    az0 = math.atan2(HERO_DIR[1], HERO_DIR[0])

    def place_lights(direction, center):
        R = Matrix.Rotation(math.atan2(direction[1], direction[0]) - az0, 4, "Z")
        for lo in lights:
            lo.location = center + (R @ (light0[lo.name] - c_light))
            look_at(lo, center)

    cam_data = cam.data
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = a.width, a.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = a.quality
    allobj = set(arm_objs.values()) | set(grip.values())

    def visible_hits(nx=128, ny=96):     # 2 단계: 팔 전체 샷에서 작은 그리퍼를 64 × 48 이 놓침(ㄱ 자 대기 2 바디) → 격자만 촘촘히 · 기준(≥ 3)은 그대로
        dg = bpy.context.evaluated_depsgraph_get()
        frame = [cam.matrix_world @ v for v in cam_data.view_frame(scene=scene)]
        o = cam.matrix_world.translation
        tr, br, bl, tl = frame
        hits = {}
        for iy in range(ny):
            for ix in range(nx):
                uu, vv = (ix + 0.5) / nx, (iy + 0.5) / ny
                d = (tl.lerp(tr, uu).lerp(bl.lerp(br, uu), vv) - o).normalized()
                ok, _l, _n, _i, ob, _m = scene.ray_cast(dg, o, d)
                if ok and ob in allobj:
                    hits[ob.name] = hits.get(ob.name, 0) + 1
        return hits

    tool = [o for o in arm_objs.values() if int(o["link"]) >= 4] + list(grip.values())
    for label, pose, direction, lens, target in plan:
        set_pose(pose)
        obs = list(allobj) if target == "arm" else tool
        d = Vector(direction).normalized()
        center, radius = bounds(obs)
        cam_data.lens = lens
        fov = 2 * math.atan(cam_data.sensor_width / 2 / lens) * min(1.0, a.height / a.width)
        cam.location = center + d * (radius / math.sin(fov / 2) * 0.82)
        look_at(cam, center)
        place_lights(d, bounds(list(allobj))[0])
        bpy.context.view_layer.update()
        hits = visible_hits()
        g_hit = sum(1 for n in hits if n.startswith("KG1_"))
        a_hit = sum(1 for n in hits if not n.startswith("KG1_"))
        path = mguard.checked_file(out / f"{label}.jpg", root, a.scratch_root)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        w, h = img.size
        bpy.data.images.remove(img)
        ok = [w, h] == [a.width, a.height] and g_hit >= 3 and a_hit >= (10 if target == "arm" else 4)
        report["renders"][label] = {"file": path.name, "pose": pose, "q_deg": poses[pose], "lens_mm": lens, "direction": list(d), "size": [w, h],
                                    "gripper_bodies_hit": g_hit, "arm_bodies_hit": a_hit, "ok": ok}
        print("ASM_RENDER", label, "ok" if ok else "BAD", flush=True)

    checks = {
        "R_gripper_display_equals_stl_moved": len(report["grip_display"]) == len(PARTS) and all(r["ok"] for r in report["grip_display"].values()),
        "R_pose_gripper_vertices_equal_rotated_display": len(report["pose_errors"]) > 0 and all(r["ok"] for r in report["pose_errors"].values()),
        "R_renders_size_and_visible": len(report["renders"]) == len(plan) and all(r["ok"] for r in report["renders"].values()),
        "R_blend_not_modified": sha(a.blend) == blend_sha0,
    }
    report["checks"] = checks
    report["blender"] = bpy.app.version_string
    report["samples"] = a.samples
    mguard.write_bytes(out / "render-report.json", (json.dumps(report, ensure_ascii=False, indent=1, default=float) + "\n").encode("utf-8"),
                       root, a.scratch_root)
    print("ASM_CHECKS", json.dumps(checks))
    print("ASM_RENDER_DONE" if all(checks.values()) else "ASM_RENDER_FAILED")


if __name__ == "__main__":
    main()
