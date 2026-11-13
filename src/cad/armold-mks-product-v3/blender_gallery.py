# -*- coding: utf-8 -*-
"""MP7 갤러리 — 커밋된 블렌더 장면(kmjh-arm-v3.blend)을 **읽기만** 하고(저장하지 않음) 자세 · 각도 · 색 조합을 바꿔 렌더한다.

사용(화면 없이):
  blender.exe --background --factory-startup --python blender_gallery.py -- --blend <kmjh-arm-v3.blend> --model <v3 모델 폴더>
      --kin <v1 kinematics.json> --poses gallery_poses.json --pose-check <pose_check.py 의 json> --out <갤러리 폴더>
      [--samples 96] [--width 1600] [--height 1200] [--quality 92] [--schemes brand,swap] [--only 이름,…] [--scratch-root <작업 뿌리>]

- 색 조합: brand = 브랜드 그대로 · swap = 흰 몸체 ↔ Cool Gray 를 맞바꿈(남색 · 민트 그대로) — 2026-10-27 사용자 「흰색이랑 회색이랑 역전해서도 만들어보고」.
- 자세: gallery_poses.json(q = 기하 영점 기준) → 빈 객체 Z 회전 = q − pose_deg. pose_check.py 가 같은 자세를 통과시킨 기록이 있어야 렌더한다.
- 조명은 카메라와 함께 수직축 둘레로 돈다(어느 방향에서 찍어도 같은 빛 — 로봇을 돌려 찍는 것과 같음).
- 검사(`gallery-report.json` 의 checks): 장면 메시 = 바디 STL(표시 자세) · 자세마다 모든 꼭짓점 = 표시 자세 점을 v1 축으로 돌린 값 · 재질 색 = 조합의 값 ·
  렌더마다 카메라 광선으로 로봇 · 흰(조합의 몸체) 바디 · 남색 · 민트 바디가 보임."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import checked_dir, checked_file, find_root  # noqa: E402
from stl_topology import stl_mesh  # noqa: E402

SCHEMES = {   # 재질 이름 → 색(브랜드 그림 표기값)
    "brand": {"KMJH_White": "#FFFFFF", "KMJH_DeepNavy": "#0B2545", "KMJH_CoolGray": "#6B7280", "KMJH_Mint": "#34D399"},
    "swap": {"KMJH_White": "#6B7280", "KMJH_DeepNavy": "#0B2545", "KMJH_CoolGray": "#FFFFFF", "KMJH_Mint": "#34D399"},
}
ROLE_MAT = {"body": "KMJH_White", "accent": "KMJH_DeepNavy", "frame": "KMJH_CoolGray", "highlight": "KMJH_Mint"}
HERO_DIR = (-0.55, -1.0, 0.55)


def shots():
    """(이름, 자세, 방향, 렌즈 mm, 대상) — 대상 'arm' = 로봇 전체 · 'wrist' = 링크 4 … 6 · 'logo' = 글자."""
    out = []
    for i in range(8):                                   # 표시 자세를 45 도마다 한 바퀴(앞 3/4 에서 시작)
        az = math.atan2(HERO_DIR[1], HERO_DIR[0]) + math.radians(45 * i)
        out.append((f"display-turn{i * 45:03d}", "display", (math.cos(az), math.sin(az), 0.5), 50, "arm"))
    out += [
        ("display-top", "display", (-0.3, -0.45, 1.6), 50, "arm"),
        ("display-low", "display", (-0.75, -1.0, 0.03), 35, "arm"),
        ("display-wrist", "display", (0.3, -1.0, 0.45), 85, "wrist"),
        ("display-logo", "display", None, 85, "logo"),
        ("home", "home", (-0.6, -1.0, 0.4), 50, "arm"),
        ("reach-up", "reach-up", (-0.45, -1.0, 0.3), 50, "arm"),
        ("pick", "pick", (0.25, -1.0, 0.45), 50, "arm"),
        ("side-reach", "side-reach", (1.0, -0.55, 0.5), 50, "arm"),
        ("wave", "wave", (-1.0, -0.35, 0.45), 50, "arm"),
        ("zero", "zero", (-0.35, -1.0, 0.45), 50, "arm"),
    ]
    return out


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True, type=Path)
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--kin", required=True, type=Path)
    ap.add_argument("--poses", required=True, type=Path)
    ap.add_argument("--pose-check", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--schemes", default="brand,swap")
    ap.add_argument("--only", default=None, help="쉼표로 고른 샷 이름만(시험용)")
    ap.add_argument("--scratch-root", type=Path, default=None)
    return ap.parse_args(sys.argv[sys.argv.index("--") + 1:])


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_linear(h):
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (1, 3, 5)) + (1.0,)


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


def match_points(ref_pts, world):
    from mathutils.kdtree import KDTree

    def tree(pts):
        t = KDTree(len(pts))
        for i, p in enumerate(pts):
            t.insert(p, i)
        t.balance()
        return t
    wl = [tuple(p) for p in world.tolist()]
    ta, tb = tree(ref_pts), tree(wl)
    return len(ref_pts), len(wl), max(max(tb.find(p)[2] for p in ref_pts), max(ta.find(p)[2] for p in wl))


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def main():
    import numpy as np
    a = args()
    root = find_root(Path(__file__).resolve().parent)
    out = checked_dir(a.out, root, a.scratch_root)

    def F_(p):
        return checked_file(p, root, a.scratch_root)
    poses = {p["name"]: [float(x) for x in p["q_deg"]] for p in json.loads(a.poses.read_text(encoding="utf-8"))["poses"]}
    pc = json.loads(a.pose_check.read_text(encoding="utf-8"))
    pc_q = {r["name"]: r["q_deg"] for r in pc["poses"]}
    if not pc.get("all_ok") or any(pc_q.get(n) != q for n, q in poses.items()):
        raise SystemExit("pose_check report is missing, failed, or checked different poses — run pose_check.py on this pose file first")
    kin = json.loads(a.kin.read_text(encoding="utf-8"))
    bd = json.loads((a.model / "bodies.json").read_text(encoding="utf-8"))
    schemes = [s for s in a.schemes.split(",") if s]
    assert all(s in SCHEMES for s in schemes), schemes
    plan = [s for s in shots() if a.only is None or s[0] in a.only.split(",")]
    blend_sha_before = sha(a.blend)
    out.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(a.blend), load_ui=False)
    scene = bpy.context.scene
    objs = {o.name: o for o in scene.objects if o.type == "MESH" and o.name != "STUDIO_FLOOR"}
    empties = [scene.objects[f"JOINT_J{k}"] for k in range(1, 7)]
    cam = scene.objects["CAMERA"]
    lights = [o for o in scene.objects if o.type == "LIGHT"]
    report = {"blend": str(a.blend.name), "blend_sha256": blend_sha_before, "poses_file_sha256": sha(a.poses), "pose_check_sha256": sha(a.pose_check),
              "schemes": {s: SCHEMES[s] for s in schemes}, "mesh_display": {}, "pose_errors": {}, "materials": {}, "renders": {}}

    # 장면 메시 = 바디 STL(표시 자세) — 모든 관절 0
    for e in empties:
        e.rotation_euler.z = 0.0
    bpy.context.view_layer.update()
    for b in bd["bodies"]:
        pts, _tris = stl_mesh(a.model / "meshes" / f"{b['name']}.stl")
        ob = objs.get(b["name"])
        if ob is None:
            report["mesh_display"][b["name"]] = {"ok": False, "missing": True}
            continue
        n0, n1, err = match_points(pts, world_points(ob))
        report["mesh_display"][b["name"]] = {"stl_vertices": n0, "blender_vertices": n1, "max_nearest_m": err,
                                             "link": ob.get("link"), "role": ob.get("role"),
                                             "ok": n0 == n1 and err <= 2e-7 and ob.get("link") == b["link"] and ob.get("role") == b["role"]}
    display = {n: world_points(o) for n, o in objs.items()}
    J = [(np.asarray(j["origin_mm"], float) / 1000.0, np.asarray(j["axis_world"], float)) for j in kin["joints"]]
    pose_deg = [float(j["pose_deg"]) for j in kin["joints"]]

    def set_pose(name):
        deltas = [q - p for q, p in zip(poses[name], pose_deg)]
        for e, d in zip(empties, deltas):
            e.rotation_euler.z = math.radians(d)
        bpy.context.view_layer.update()
        err = 0.0
        for n, ob in objs.items():
            Q = display[n].copy()
            for k in range(int(ob["link"]), 0, -1):
                if deltas[k - 1]:
                    O, A = J[k - 1]
                    Q = (Q - O) @ rot_np(A, deltas[k - 1]).T + O
            err = max(err, float(np.max(np.linalg.norm(world_points(ob) - Q, axis=1))))
        report["pose_errors"][name] = {"q_deg": poses[name], "max_err_m": err, "ok": err <= 2e-6}

    def set_scheme(s):
        for mname, hx in SCHEMES[s].items():
            m = bpy.data.materials[mname]
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = hex_linear(hx)
            m.diffuse_color = hex_linear(hx)
        rows = {}
        for n, ob in objs.items():
            want = SCHEMES[s][ROLE_MAT[ob["role"]]]
            slots = [m.name for m in ob.data.materials]
            col = tuple(ob.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)
            err = max(abs(x - y) for x, y in zip(col, hex_linear(want)))
            rows[n] = {"slots": slots, "want_hex": want, "err": err, "ok": slots == [ROLE_MAT[ob["role"]]] and err <= 1e-6}
        report["materials"][s] = {"all_ok": all(r["ok"] for r in rows.values()), "bad": [n for n, r in rows.items() if not r["ok"]]}

    def floor_fade(r0, r1, strength):
        """카메라 광선에만 — 로봇에서 r0 … r1 m 사이의 바닥을 카메라 배경색으로 서서히 바꾼다(세기 strength — 로봇 가까이 빛 받은 바닥의 밝기와 맞춘 값).
        낮은 각도 · 높은 자세에서 빛이 닿지 않는 먼 바닥이 검은 띠로 찍히는 것을 없앤다. 그림자 · 반사 광선은 그대로(장면 빛은 안 바뀜).
        2026-10-27 시험: 가까운 바닥 선형 밝기 0.44 ~ 0.56 · 배경색 선형 평균 0.85 → 세기 0.60."""
        wn = scene.world.node_tree.nodes
        mixw = [n for n in wn if n.type == "MIX_SHADER"]
        assert len(mixw) == 1, "world should hold one camera-ray mix (blender_scene.py)"
        cam_bg = mixw[0].inputs[2].links[0].from_node          # 「Is Camera Ray」 = 1 쪽 배경
        nt = bpy.data.materials["STUDIO_FLOOR"].node_tree
        N, L = nt.nodes, nt.links
        bsdf, mo = N["Principled BSDF"], N["Material Output"]
        geo = N.new("ShaderNodeNewGeometry")
        flat = N.new("ShaderNodeVectorMath")
        flat.operation = "MULTIPLY"
        flat.inputs[1].default_value = (1.0, 1.0, 0.0)
        ln = N.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        mr = N.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = r0, r1
        lp = N.new("ShaderNodeLightPath")
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        em = N.new("ShaderNodeEmission")
        cam_bg.inputs["Strength"].default_value = strength          # 카메라에 보이는 배경도 같은 세기로(지평선 경계 없이)
        em.inputs["Color"].default_value = tuple(cam_bg.inputs["Color"].default_value)
        em.inputs["Strength"].default_value = strength
        mix = N.new("ShaderNodeMixShader")
        L.new(geo.outputs["Position"], flat.inputs[0])
        L.new(flat.outputs["Vector"], ln.inputs[0])
        L.new(ln.outputs["Value"], mr.inputs["Value"])
        L.new(mr.outputs["Result"], mul.inputs[0])
        L.new(lp.outputs["Is Camera Ray"], mul.inputs[1])
        L.new(mul.outputs["Value"], mix.inputs["Fac"])
        L.new(bsdf.outputs["BSDF"], mix.inputs[1])
        L.new(em.outputs["Emission"], mix.inputs[2])
        L.new(mix.outputs["Shader"], mo.inputs["Surface"])
        report["floor_fade_m"] = [r0, r1]
        report["floor_fade_color_strength"] = [list(em.inputs["Color"].default_value), em.inputs["Strength"].default_value]

    floor_fade(0.55, 2.2, 0.60)

    def bounds(obs):
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        return (lo + hi) / 2, (hi - lo).length / 2

    light0 = {lo.name: lo.location.copy() for lo in lights}
    c_light = bounds(list(objs.values()))[0]
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
    robot = set(objs.values())

    def visible_hits(nx=64, ny=48):
        dg = bpy.context.evaluated_depsgraph_get()
        frame = [cam.matrix_world @ v for v in cam_data.view_frame(scene=scene)]
        o = cam.matrix_world.translation
        tr, br, bl, tl = frame
        hits, robot_rays = {}, 0
        for iy in range(ny):
            for ix in range(nx):
                u, v = (ix + 0.5) / nx, (iy + 0.5) / ny
                d = (tl.lerp(tr, u).lerp(bl.lerp(br, u), v) - o).normalized()
                ok, _l, _n, _i, ob, _m = scene.ray_cast(dg, o, d)
                if ok and ob in robot and not ob.hide_render:
                    robot_rays += 1
                    hits[ob.name] = hits.get(ob.name, 0) + 1
        return hits, robot_rays / (nx * ny)

    face_out = -Matrix(kin["joints"][1]["R_child"]).col[1]
    logo = [n for n in objs if "_LOGO_" in n]
    wrist = [n for n, o in objs.items() if int(o["link"]) >= 4]
    for s in schemes:
        set_scheme(s)
        for label, pose, direction, lens, target in plan:
            set_pose(pose)
            obs = list(objs.values()) if target == "arm" else [objs[n] for n in (logo if target == "logo" else wrist)]
            d = Vector(direction if direction is not None else (face_out + Vector((0, 0, 0.25)))).normalized()
            center, radius = bounds(obs)
            cam_data.lens = lens
            fov = 2 * math.atan(cam_data.sensor_width / 2 / lens) * min(1.0, a.height / a.width)
            cam.location = center + d * (radius / math.sin(fov / 2) * 0.82)
            look_at(cam, center)
            place_lights(d, bounds(list(objs.values()))[0])
            bpy.context.view_layer.update()
            hits, frac = visible_hits()
            by_role = {}
            for n, c in hits.items():
                by_role[objs[n]["role"]] = by_role.get(objs[n]["role"], 0) + 1
            path = F_(out / s / f"{s}-{label}.jpg")
            path.parent.mkdir(parents=True, exist_ok=True)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(str(path))
            w, h = img.size
            bpy.data.images.remove(img)
            if target == "arm":
                vis_ok = frac >= 0.05 and len(hits) >= 15 and by_role.get("body", 0) >= 6 and by_role.get("accent", 0) >= 3 and by_role.get("highlight", 0) >= 1
            elif target == "logo":
                vis_ok = all(n in hits for n in logo)
            else:
                vis_ok = sum(1 for n in wrist if n in hits) >= 5
            report["renders"][f"{s}/{label}"] = {"file": f"{s}/{path.name}", "scheme": s, "pose": pose, "lens_mm": lens, "direction": list(d),
                                                  "size": [w, h], "robot_ray_fraction": frac, "bodies_hit": len(hits), "bodies_hit_by_role": by_role,
                                                  "ok": [w, h] == [a.width, a.height] and vis_ok}
            print("GALLERY_RENDER", s, label, "ok" if report["renders"][f"{s}/{label}"]["ok"] else "BAD", flush=True)

    nb = len(bd["bodies"])
    checks = {
        "G_meshes_equal_stl_display_pose": len(report["mesh_display"]) == nb and all(r["ok"] for r in report["mesh_display"].values())
                                           and set(objs) == {b["name"] for b in bd["bodies"]},
        "G_pose_all_vertices_equal_rotated_display": len(report["pose_errors"]) > 0 and all(r["ok"] for r in report["pose_errors"].values()),
        "G_materials_equal_scheme": all(report["materials"][s]["all_ok"] for s in schemes),
        "G_renders_size_and_visible": len(report["renders"]) == len(plan) * len(schemes) and all(r["ok"] for r in report["renders"].values()),
        "G_blend_not_modified": sha(a.blend) == blend_sha_before,
    }
    report["checks"] = checks
    report["blender"] = bpy.app.version_string
    report["samples"] = a.samples
    F_(out / "gallery-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    print("GALLERY_CHECKS", json.dumps(checks))
    print("GALLERY_DONE" if all(checks.values()) else "GALLERY_FAILED")


if __name__ == "__main__":
    main()
