# -*- coding: utf-8 -*-
"""MP8 — 그리퍼 KG1 보기 그림(블렌더 · 커밋된 부품 STL 만 읽음 · 서보 · 탄소 관은 기준 상자 · 원통). 보기용 — 검사는 verify_gripper.py.

사용: blender --background --factory-startup --python render_gripper.py -- --scratch-root <작업 뿌리> [--u 0 40]
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

COL = {"BASE": (0.42, 0.45, 0.50), "JAW_A": (0.93, 0.93, 0.93), "JAW_B": (0.88, 0.88, 0.90), "PINION": (0.043, 0.145, 0.27),
       "PAD_A_FLAT": (0.204, 0.827, 0.6), "PAD_B_FLAT": (0.204, 0.827, 0.6)}


def scene(parts, u, P):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    L, g, S, R = P["layout"], P["gear"], P["servo"], P["rod"]
    r, zc = g["module"] * g["teeth"] / 2, L["z_c"]
    for nm, c in COL.items():
        bpy.ops.wm.stl_import(filepath=str(parts / f"{nm}.stl"))
        ob = bpy.context.selected_objects[0]
        mw = Matrix.Scale(0.001, 4)
        if nm in ("JAW_A", "PAD_A_FLAT"):
            mw = Matrix.Translation((-u * 0.001, 0, 0)) @ mw
        if nm in ("JAW_B", "PAD_B_FLAT"):
            mw = Matrix.Translation((u * 0.001, 0, 0)) @ mw
        if nm == "PINION":
            piv = Vector((0, 0, zc * 0.001))
            mw = Matrix.Translation(piv) @ Matrix.Rotation(-u / r, 4, "Y") @ Matrix.Translation(-piv) @ mw
        ob.matrix_world = mw
        mat = bpy.data.materials.new(nm)
        mat.use_nodes = True
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*c, 1)
        b.inputs["Roughness"].default_value = 0.45
        ob.data.materials.append(mat)
    top = L["wall_y"][0]
    bpy.ops.mesh.primitive_cube_add(size=1)
    sv = bpy.context.active_object
    sv.scale = (S["body"][0] * 0.001, S["body"][2] * 0.001, S["body"][1] * 0.001)
    sv.location = ((-S["spline_from_out_end"] + S["body"][0] / 2) * 0.001, (top - S["body"][2] / 2) * 0.001, zc * 0.001)
    ms = bpy.data.materials.new("servo"); ms.use_nodes = True
    ms.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.06, 1)
    sv.data.materials.append(ms)
    for yy in L["rod_y_a"] + L["rod_y_b"]:
        bpy.ops.mesh.primitive_cylinder_add(radius=R["od"] / 2000, depth=R["length"] / 1000, location=(0, yy / 1000, L["rod_z"] / 1000),
                                            rotation=(0, math.pi / 2, 0))
        mr = bpy.data.materials.new("rod"); mr.use_nodes = True
        mr.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
        bpy.context.active_object.data.materials.append(mr)
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.93, 0.94, 0.96, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    for rot, en in (((40, 10, -30), 3.0), ((60, 0, 150), 1.2)):
        li = bpy.data.lights.new("sun", "SUN"); li.energy = en
        lo = bpy.data.objects.new("sun", li); sc.collection.objects.link(lo); lo.rotation_euler = tuple(math.radians(v) for v in rot)
    return sc


def shoot(sc, out, az, el, dist=0.40):
    cam = bpy.data.cameras.new("cam"); cam.lens = 55
    co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co
    t = Vector((0.0, -0.008, 0.050))
    a, e = math.radians(az), math.radians(el)
    co.location = t + Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e)))
    co.rotation_euler = (t - co.location).to_track_quat("-Z", "Y").to_euler()
    engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else ("BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "CYCLES")
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    try:
        sc.view_settings.view_transform = "Standard"     # 기본 AgX 는 흰 · 회색을 바래 보이게 한다
        sc.view_settings.exposure = -0.6
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)


def main():
    import json
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sroot = Path(argv[argv.index("--scratch-root") + 1])
    us = [float(v) for v in argv[argv.index("--u") + 1:]] if "--u" in argv else [0.0, 40.0]
    root = guard.find_root(HERE)
    model = guard.checked_dir(root / "models" / "kmjh-gripper-v1", root, sroot)
    P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    for u in us:
        sc = scene(model / "parts", u, P)
        tag = "closed" if u == 0 else f"open{int(round(2 * u))}"
        shoot(sc, guard.checked_file(model / f"render-{tag}.png", root, sroot), -35, 24)
        if u == us[-1]:
            shoot(sc, guard.checked_file(model / f"render-{tag}-back.png", root, sroot), 150, 20)


main()
