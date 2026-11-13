# -*- coding: utf-8 -*-
"""MP11 팔 전체 분해도(보기용) — 외장 v3 장면(kmjh-arm-v3.blend · rev1)을 읽기만 하고(저장 안 함 · 전후 sha256 대조)
그리퍼 KG1 을 MP9 assembly.json 의 행렬로 붙인 뒤, 관절마다 그 관절 축을 따라 자식 링크를 벌린다(누적).
관절 안: 끝 덮개 · 사선 · 띠 고리는 모듈에서 축 방향 밖으로, 허브 덮개는 그 관절 축으로, 로고 글자는 팔 면에서 밖으로.
그리퍼(G 좌표): 판 0 · 서보 −y · 피니언 +y · 턱 ±x 와 +z · 손끝 덮개 +z · 그리퍼 통째 +z(J6 축 밖).
샷 설정(자세 · 방향 · f · 채움 · 격자 · 렌더 크기) = 같은 폴더 parameters.json. 쓰기는 guard.py 로만(산출 · 근거 · 격리 작업 뿌리).

사용: blender -b --factory-startup --python explode_arm.py -- --shot home --renders <폴더> --data <폴더> [--scratch-root <격리 폴더>]
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
from pathlib import Path  # noqa: E402

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402


def args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    o = {"scratch-root": None}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        o[k] = argv[i + 1]
        i += 2
    o["repo"] = guard.find_root(HERE)
    prm = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    sh = [s for s in prm["shots"] if s["name"] == o["shot"]]
    assert len(sh) == 1, o["shot"]
    sh = sh[0]
    o["out"] = guard.checked_dir(Path(o["renders"]), o["repo"], o["scratch-root"])
    o["data"] = guard.checked_dir(Path(o["data"]), o["repo"], o["scratch-root"])
    o["pose"], o["tag"], o["f"], o["fill"] = sh["pose"], "-" + sh["name"], float(sh["f"]), float(sh["fill"])
    o["gx"], o["gy"], o["assembled"] = int(sh["grid"][0]), int(sh["grid"][1]), "1" if sh["assembled"] else "0"
    o["dir"] = Vector([float(x) for x in sh["dir"]]).normalized()
    r = prm["render"]
    o["samples"], o["w"], o["h"], o["lens"], o["scale"] = int(r["samples"]), int(r["w"]), int(r["h"]), float(r["lens"]), 1.0
    return o


def write_json(path, obj, a, **kw):
    guard.write_bytes(path, (json.dumps(obj, **kw) + ("\n" if kw.get("indent") else "")).encode("utf-8"), a["repo"], a["scratch-root"])


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def centroid(ob):
    """메시 꼭짓점 평균(세계 · m)."""
    mw = ob.matrix_world
    n = len(ob.data.vertices)
    s = Vector((0, 0, 0))
    for v in ob.data.vertices:
        s += mw @ v.co
    return s / max(n, 1)


def bounds(obs):
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
    hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
    return lo, hi


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def sgn(x, default=1.0):
    return default if abs(x) < 1e-6 else (1.0 if x > 0 else -1.0)


def main():
    a = args()
    repo = a["repo"]
    v3 = repo / "models" / "armold-mks-product-v3"
    blend = v3 / "blender" / "kmjh-arm-v3.blend"
    asm = json.loads((repo / "models" / "arm-v3-kg1-assembly" / "assembly.json").read_text(encoding="utf-8"))
    PRM = json.loads((repo / "src" / "cad" / "arm-v3-kg1-assembly" / "parameters.json").read_text(encoding="utf-8"))
    P = json.loads((repo / "src" / "cad" / "kmjh-gripper-v1" / "parameters.json").read_text(encoding="utf-8"))
    kin = json.loads((repo / "models" / "armold-mks-concept-v1" / "kinematics.json").read_text(encoding="utf-8"))
    poses = {p["name"]: [float(x) for x in p["q_deg"]] for p in
             json.loads((repo / "src" / "cad" / "armold-mks-product-v3" / "gallery_poses.json").read_text(encoding="utf-8"))["poses"]}
    blend_sha0 = sha(blend)
    a["out"].mkdir(parents=True, exist_ok=True)
    a["data"].mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False)
    scene = bpy.context.scene
    arm = {o.name: o for o in scene.objects if o.type == "MESH" and o.name != "STUDIO_FLOOR"}
    E = [scene.objects[f"JOINT_J{k}"] for k in range(1, 7)]
    cam = scene.objects["CAMERA"]
    lights = [o for o in scene.objects if o.type == "LIGHT"]
    for e in E:
        e.rotation_euler.z = 0.0
    bpy.context.view_layer.update()

    # ── 그리퍼(MP9 와 같은 행렬 · 같은 벌림 u) ──────────────────────────────
    PADSET, u = PRM["gripper"]["padset"], float(PRM["gripper"]["render_u"])
    L, g, Sv, Rd = P["layout"], P["gear"], P["servo"], P["rod"]
    r_p, zc = g["module"] * g["teeth"] / 2, L["z_c"]
    Mg = asm["mount"]["g_to_world_display"]
    Mb = Matrix([[Mg[i][0], Mg[i][1], Mg[i][2], Mg[i][3] / 1000.0] for i in range(3)] + [[0, 0, 0, 1]])
    S = Matrix.Scale(0.001, 4)
    F = a["f"]
    DG = 70.0 * F                                                         # 그리퍼 통째로 J6 축 밖(+z) · mm
    EXG = {"F": (0, 0, DG), "A": (-28 * F, 0, DG + 38 * F), "B": (28 * F, 0, DG + 38 * F), "R": (0, 42 * F, DG), "PA": (-28 * F, 0, DG + 78 * F),
           "PB": (28 * F, 0, DG + 78 * F), "S": (0, -48 * F, DG), "ROD": (0, 0, DG)}

    def local(grp):
        if grp in ("A", "PA"):
            return Matrix.Translation((-u, 0, 0))
        if grp in ("B", "PB"):
            return Matrix.Translation((u, 0, 0))
        if grp == "R":
            return Matrix.Translation((0, 0, zc)) @ Matrix.Rotation(-u / r_p, 4, "Y") @ Matrix.Translation((0, 0, -zc))
        return Matrix.Identity(4)

    GP = {"BASE": ("KMJH_CoolGray", "F"), "JAW_A": ("KMJH_White", "A"), "JAW_B": ("KMJH_White", "B"), "PINION": ("KMJH_DeepNavy", "R"),
          f"PAD_A_{PADSET}": ("KMJH_CoolGray", "PA"), f"PAD_B_{PADSET}": ("KMJH_CoolGray", "PB")}
    grip_place = {}

    def put(ob, grp, extra=Matrix.Identity(4)):
        place = Mb @ S @ Matrix.Translation(EXG[grp]) @ local(grp) @ extra
        grip_place[ob.name] = (place, Mb @ S @ local(grp) @ extra)
        ob.matrix_world = grip_place[ob.name][1]

    grip = {}
    for nm, (mat, grp) in GP.items():
        bpy.ops.wm.stl_import(filepath=str(repo / "models" / "kmjh-gripper-v1" / "parts" / f"{nm}.stl"))
        ob = bpy.context.selected_objects[0]
        ob.name = f"KG1_{nm}"
        ob.data.materials.clear()
        ob.data.materials.append(bpy.data.materials[mat])
        put(ob, grp)
        grip[ob.name] = ob
    top = L["wall_y"][0]
    bpy.ops.mesh.primitive_cube_add(size=1)
    sv = bpy.context.active_object
    sv.name = "KG1_SERVO"
    ctr = Vector(((-Sv["spline_from_out_end"] + Sv["body"][0] / 2), (top - Sv["body"][2] / 2), zc))
    put(sv, "S", Matrix.Translation(ctr) @ Matrix.Diagonal((Sv["body"][0], Sv["body"][2], Sv["body"][1], 1)))
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
        put(rc, "ROD", Matrix.Translation((0, yy, L["rod_z"])) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        rc.data.materials.append(mr)
        grip[rc.name] = rc
    bpy.context.view_layer.update()
    for ob in grip.values():
        mw = ob.matrix_world.copy()
        ob.parent = E[5]
        ob.matrix_parent_inverse = E[5].matrix_world.inverted()
        ob.matrix_world = mw
    bpy.context.view_layer.update()

    # ── 자세 ───────────────────────────────────────────────────────────────
    pose_deg = [float(j["pose_deg"]) for j in kin["joints"]]
    q = poses[a["pose"]]
    for e, qq, p0 in zip(E, q, pose_deg):
        e.rotation_euler.z = math.radians(qq - p0)
    bpy.context.view_layer.update()
    everything = list(arm.values()) + list(grip.values())

    # ── 바닥 · 조명(MP9 blender_assembly.py 와 같은 값) ───────────────────────
    wn = scene.world.node_tree.nodes
    mixw = [n for n in wn if n.type == "MIX_SHADER"]
    cam_bg = mixw[0].inputs[2].links[0].from_node
    nt = bpy.data.materials["STUDIO_FLOOR"].node_tree
    N_, L_ = nt.nodes, nt.links
    bsdf, mo = N_["Principled BSDF"], N_["Material Output"]
    geo, flat, ln, mrg = N_.new("ShaderNodeNewGeometry"), N_.new("ShaderNodeVectorMath"), N_.new("ShaderNodeVectorMath"), N_.new("ShaderNodeMapRange")
    flat.operation, ln.operation = "MULTIPLY", "LENGTH"
    flat.inputs[1].default_value = (1.0, 1.0, 0.0)
    mrg.interpolation_type = "SMOOTHSTEP"
    mrg.inputs["From Min"].default_value, mrg.inputs["From Max"].default_value = 0.8, 2.8
    lp, mul, em, mix = N_.new("ShaderNodeLightPath"), N_.new("ShaderNodeMath"), N_.new("ShaderNodeEmission"), N_.new("ShaderNodeMixShader")
    mul.operation = "MULTIPLY"
    cam_bg.inputs["Strength"].default_value = 0.60
    em.inputs["Color"].default_value = tuple(cam_bg.inputs["Color"].default_value)
    em.inputs["Strength"].default_value = 0.60
    for o_, i_ in ((geo.outputs["Position"], flat.inputs[0]), (flat.outputs["Vector"], ln.inputs[0]), (ln.outputs["Value"], mrg.inputs["Value"]),
                   (mrg.outputs["Result"], mul.inputs[0]), (lp.outputs["Is Camera Ray"], mul.inputs[1]), (mul.outputs["Value"], mix.inputs["Fac"]),
                   (bsdf.outputs["BSDF"], mix.inputs[1]), (em.outputs["Emission"], mix.inputs[2]), (mix.outputs["Shader"], mo.inputs["Surface"])):
        L_.new(o_, i_)
    light0 = {lo.name: lo.location.copy() for lo in lights}
    lo0, hi0 = bounds(list(arm.values()))
    c_light0 = (lo0 + hi0) / 2
    az0 = math.atan2(-1.0, -0.55)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = a["samples"]
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = a["w"], a["h"], 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 92
    cam_data = cam.data
    cam_data.clip_start, cam_data.clip_end = 0.01, 50.0
    report = {"blend": str(blend.relative_to(repo)), "blend_sha256": blend_sha0, "pose": a["pose"], "q_deg": q, "u_mm": u, "padset": PADSET,
              "samples": a["samples"], "size": [a["w"], a["h"]], "shots": {}, "offsets_mm": {}}

    def shot(name, obs):
        d = a["dir"]
        lo, hi = bounds(obs)
        center, radius = (lo + hi) / 2, (hi - lo).length / 2
        cam_data.lens = a["lens"]
        cam_data.sensor_fit = "HORIZONTAL"
        fov = 2 * math.atan(cam_data.sensor_width / 2 / a["lens"]) * min(1.0, a["h"] / a["w"])
        cam.location = center + d * (radius / math.sin(fov / 2) * 0.80 * a["scale"])
        look_at(cam, center)
        bpy.context.view_layer.update()
        # 화면 맞춤: 상자 모서리를 화면에 비춰 가운데로 옮기고 채움 비율로 거리 조정(몇 번 되풀이)
        fill = float(a.get("fill", 0.86))
        fx = 2 * math.atan(cam_data.sensor_width / 2 / a["lens"])
        fy = 2 * math.atan(math.tan(fx / 2) * a["h"] / a["w"])
        for _ in range(5):
            pts = [world_to_camera_view(scene, cam, o.matrix_world @ Vector(c)) for o in obs for c in o.bound_box]
            x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
            y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
            dist = (cam.location - center).length
            right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
            up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
            shift = right * ((x0 + x1) / 2 - 0.5) * 2 * dist * math.tan(fx / 2) + up * ((y0 + y1) / 2 - 0.5) * 2 * dist * math.tan(fy / 2)
            center = center + shift
            dist *= max((x1 - x0) / fill, (y1 - y0) / fill)
            cam.location = center + d * dist
            look_at(cam, center)
            bpy.context.view_layer.update()
        R = Matrix.Rotation(math.atan2(d[1], d[0]) - az0, 4, "Z")
        for lo_ in lights:
            lo_.location = center + (R @ (light0[lo_.name] - c_light0)) * 1.4
            look_at(lo_, center)
        bpy.context.view_layer.update()
        path = guard.checked_file(a["out"] / f"{name}{a['tag']}.jpg", a["repo"], a["scratch-root"])
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        # 부품 중심의 화면 자리(번호 붙이기용 · 0 ~ 1 · 아래가 0)
        labels = {}
        for o in obs:
            c = centroid(o)
            p = world_to_camera_view(scene, cam, c)
            labels[o.name] = [p.x, p.y, p.z]
        report["shots"][name] = {"file": path.name, "camera": list(cam.location), "center": list(center), "lens": a["lens"], "labels": labels}
        print("SHOT", name, flush=True)

    # 1 조립(같은 방향)
    if a.get("assembled", "1") == "1":
        shot("arm-assembled", everything)

    # ── 분해: 관절마다 자식 링크를 그 축으로(누적) ───────────────────────────
    def axis(k):
        return (E[k - 1].matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()

    D = {k: v * F for k, v in {1: 0.075, 2: 0.085, 3: 0.085, 4: 0.075, 5: 0.075, 6: 0.065}.items()}
    ATTACH = {1: "LINK1_SHOULDER_CAP", 2: "LINK2_SHOULDER_HUB", 3: "LINK3_ELBOW_HUB", 4: "LINK4_NECK", 5: "LINK5_WRIST_HUB", 6: "LINK6_TOOL_FLANGE"}
    # 바닥 묶음: 발 0 · 나머지는 높이 차례로 위로
    base = sorted([o for o in arm.values() if o.parent and o.parent.name == "KMJH_ARM_BASE"], key=lambda o: centroid(o).z)
    STEP0 = 0.035 * F
    base_off = {}
    lift = 0.0
    for o in base:
        if o.name == "BASE_FOOT":
            base_off[o.name] = 0.0
            continue
        lift += STEP0
        base_off[o.name] = lift
    j1_mod = arm["J1_MODULE"]
    base_lift_mod = base_off["J1_MODULE"]
    PK = {}
    for k in range(1, 7):
        a_k = axis(k)
        PK[k] = E[k - 1].matrix_world.translation.copy()               # 부모 쪽 관절 원점(자식을 옮기기 전)
        mod = arm[f"J{k}_MODULE"]
        s = sgn((centroid(arm[ATTACH[k]]) - centroid(mod)).dot(a_k))
        extra = base_lift_mod if k == 1 else 0.0
        v = a_k * s * D[k] + Vector((0, 0, extra))
        E[k - 1].matrix_world = Matrix.Translation(v) @ E[k - 1].matrix_world
        bpy.context.view_layer.update()
        report["offsets_mm"][f"JOINT_J{k}"] = [x * 1000 for x in v]

    # 관절 안 · 링크 안의 작은 부품(빈 객체를 다 옮긴 뒤 · 지금 세계 기준)
    sub = {}
    for o in base:
        sub[o.name] = Vector((0, 0, base_off[o.name]))
    for k in range(1, 7):
        a_k = axis(k)
        mod = arm[f"J{k}_MODULE"]
        mc = centroid(mod)
        s_child = sgn((centroid(arm[ATTACH[k]]) - mc).dot(a_k))
        cap = arm.get(f"J{k}_END_CAP")
        if cap is not None:
            s_cap = sgn((centroid(cap) - mc).dot(a_k), -s_child)
            sub[cap.name] = a_k * s_cap * 0.045
            sub[f"J{k}_CAP_SLASH"] = a_k * s_cap * 0.070
        ring = arm[f"J{k}_ACCENT_RING"]
        s_r = sgn((centroid(ring) - mc).dot(a_k), s_child)
        base_v = sub.get(ring.name, Vector((0, 0, 0)))
        sub[ring.name] = base_v + a_k * s_r * 0.028
    for hub, k in (("LINK2_SHOULDER_HUB", 2), ("LINK3_ELBOW_HUB", 3), ("LINK5_WRIST_HUB", 5)):
        a_k = axis(k)
        hc = centroid(arm[hub])
        s_h = sgn((centroid(arm[hub + "_CAP"]) - hc).dot(a_k))
        sub[hub + "_CAP"] = a_k * s_h * 0.040
        sub[hub + "_SLASH"] = a_k * s_h * 0.062
    # 로고: 위팔 면에서 밖으로(위팔 = J2 → J3 선에 수직)
    o2, o3 = E[1].matrix_world.translation, E[2].matrix_world.translation
    b = (o3 - o2).normalized()
    for nm in ("LINK2_LOGO_K", "LINK2_LOGO_M", "LINK2_LOGO_J", "LINK2_LOGO_H", "LINK2_LOGO_K_SLASH"):
        w = centroid(arm[nm]) - o2
        perp = (w - b * w.dot(b)).normalized()
        sub[nm] = perp * (0.040 if nm.endswith("SLASH") else 0.028)
    a6 = axis(6)
    s6 = sgn((centroid(arm["LINK6_TOOL_FLANGE"]) - centroid(arm["J6_MODULE"])).dot(a6))
    sub["LINK6_TOOL_RING"] = a6 * s6 * 0.030
    for nm, v in sub.items():
        v = v * F if not nm.startswith(("BASE_", "J1_MODULE")) else v
        ob = arm[nm]
        ob.matrix_world = Matrix.Translation(v) @ ob.matrix_world
        report["offsets_mm"][nm] = [x * 1000 for x in v]
    bpy.context.view_layer.update()
    # 그리퍼 G 안 벌림: 빈 객체 J6 아래에서 지금 행렬에 (분해 자리 · 조립 자리 차이)를 곱함
    for nm, ob in grip.items():
        place, home = grip_place[nm]
        ob.matrix_world = ob.matrix_world @ (home.inverted() @ place)
    bpy.context.view_layer.update()
    report["gripper_offsets_g_mm"] = EXG

    # 축 점선(중심선): 관절마다 그 축 위 부품들의 축 방향 자리 범위 + 여유
    LINE = {1: ["BASE_FOOT", "BASE_LIGHT_RING", "BASE_COLUMN", "J1_MODULE", "J1_ACCENT_RING", "LINK1_SHOULDER_CAP"],
            2: ["J2_MODULE", "J2_ACCENT_RING", "J2_END_CAP", "J2_CAP_SLASH", "LINK2_SHOULDER_HUB", "LINK2_SHOULDER_HUB_CAP", "LINK2_SHOULDER_HUB_SLASH"],
            3: ["J3_MODULE", "J3_ACCENT_RING", "J3_END_CAP", "J3_CAP_SLASH", "LINK3_ELBOW_HUB", "LINK3_ELBOW_HUB_CAP", "LINK3_ELBOW_HUB_SLASH"],
            4: ["J4_MODULE", "J4_ACCENT_RING", "J4_END_CAP", "J4_CAP_SLASH", "LINK4_NECK"],
            5: ["J5_MODULE", "J5_ACCENT_RING", "J5_END_CAP", "J5_CAP_SLASH", "LINK5_WRIST_HUB", "LINK5_WRIST_HUB_CAP", "LINK5_WRIST_HUB_SLASH"],
            6: ["J6_MODULE", "J6_ACCENT_RING", "J6_END_CAP", "J6_CAP_SLASH", "LINK6_TOOL_FLANGE", "LINK6_TOOL_RING", "KG1_BASE"]}
    allob = {**arm, **grip}
    ml = bpy.data.materials.new("AXLINE")
    ml.use_nodes = True
    ml.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.035, 0.045, 1)
    ml.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7
    DASH, GAP, RAD = 0.009, 0.005, 0.0008
    n_dash = 0
    for k, names in LINE.items():
        a_k = axis(k)
        ts = [(centroid(allob[n]) - PK[k]).dot(a_k) for n in names]
        t0, t1 = min(ts) - 0.02, max(ts) + 0.02
        rq = a_k.to_track_quat("Z", "Y")
        tt = t0
        while tt < t1:
            seg = min(DASH, t1 - tt)
            bpy.ops.mesh.primitive_cylinder_add(radius=RAD, depth=seg, vertices=12)
            c = bpy.context.active_object
            c.name = f"AXLINE_J{k}_{n_dash}"
            c.rotation_euler = rq.to_euler()
            c.location = PK[k] + a_k * (tt + seg / 2)
            c.data.materials.append(ml)
            n_dash += 1
            tt += DASH + GAP
    bpy.context.view_layer.update()
    report["axis_line_dashes"] = n_dash

    shot("arm-exploded", everything)
    # 번호 붙이기용 화면 격자: 카메라 광선이 처음 맞는 부품(점선 · 바닥은 빈칸)
    NX, NY = int(a.get("gx", 240)), int(a.get("gy", 160))
    dg = bpy.context.evaluated_depsgraph_get()
    frame = [cam.matrix_world @ v for v in cam.data.view_frame(scene=scene)]
    o = cam.matrix_world.translation
    tr, br, bl, tl = frame
    names = sorted(allob)
    idx = {n: i for i, n in enumerate(names)}
    grid = []
    for iy in range(NY):
        row = []
        for ix in range(NX):
            uu, vv = (ix + 0.5) / NX, (iy + 0.5) / NY
            d = (tl.lerp(tr, uu).lerp(bl.lerp(br, uu), vv) - o).normalized()
            ok, _l, _n, _i, ob, _m = scene.ray_cast(dg, o, d)
            row.append(idx[ob.name] if ok and ob.name in idx else -1)
        grid.append(row)
    proj = {}
    for n in names:
        p = world_to_camera_view(scene, cam, centroid(allob[n]))
        proj[n] = [p.x, 1 - p.y]                                         # 위가 0(그림 좌표)
    write_json(a["data"] / f"label-grid{a['tag']}.json", {"nx": NX, "ny": NY, "names": names, "grid": grid, "proj": proj,
                                                          "size": [a["w"], a["h"]]}, a)
    report["blend_unchanged"] = sha(blend) == blend_sha0
    report["blender"] = bpy.app.version_string
    report["shot"] = a["shot"]
    report["f"], report["fill"], report["dir"] = a["f"], a["fill"], list(a["dir"])
    write_json(a["data"] / f"render-report{a['tag']}.json", report, a, ensure_ascii=False, indent=1, default=list)
    print("DONE blend_unchanged", report["blend_unchanged"], flush=True)


if __name__ == "__main__":
    main()
