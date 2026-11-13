# -*- coding: utf-8 -*-
"""MP7 동작 영상 대조용 .blend 사본 — 커밋된 장면을 열기만 하고, 한 가지씩 잘못을 넣은 사본을 격리 작업 뿌리에 저장한다(run_motion_controls.py 가 부름).

사용: blender.exe --background --factory-startup --python motion_control_blends.py -- <kmjh-arm-v3.blend> <작업 뿌리 안 폴더> <작업 뿌리>"""
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import checked_file, find_root  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
src, out_dir, scratch = Path(argv[0]), Path(argv[1]), Path(argv[2])
root = find_root(Path(__file__).resolve().parent)
if scratch.resolve() not in out_dir.resolve().parents:
    raise SystemExit("variants go under the scratch root only")


def body_objects():
    return [o for o in bpy.data.objects if o.type == "MESH" and o.get("role") is not None]


def nudged():
    bpy.data.objects["J2_MODULE"].data.vertices[0].co.x += 0.001            # 1 mm(장면 단위 m)


def hidden():
    for o in body_objects():
        if o.get("role") == "body":
            o.hide_render = True


def flipped():
    bpy.data.objects["LINK2_UPPER_BAR"].data.flip_normals()                  # 점은 그대로 · 감김만 뒤집힘


def modifier():
    bpy.data.objects["J2_MODULE"].modifiers.new("SOLIDIFY", "SOLIDIFY")


def collection_hidden():
    c = bpy.data.collections.new("HIDDEN_BODIES")
    bpy.context.scene.collection.children.link(c)
    c.hide_render = True
    for o in body_objects():
        if o.get("role") == "body":
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            c.objects.link(o)


def camera_ray_off():
    for o in body_objects():
        if o.get("role") == "body":
            o.visible_camera = False


def extra_object():
    e = bpy.data.objects.new("EXTRA_EMPTY", None)
    bpy.context.scene.collection.objects.link(e)


def material_alpha():
    bpy.data.materials["KMJH_White"].node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.0


def material_linked():
    nt = bpy.data.materials["KMJH_DeepNavy"].node_tree
    rgb = nt.nodes.new("ShaderNodeRGB")
    nt.links.new(rgb.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])


def layer_holdout():
    c = bpy.data.collections.new("MASK")
    bpy.context.scene.collection.children.link(c)
    c.objects.link(bpy.data.objects["J2_MODULE"])                           # 원래 경로는 그대로 · 하나 더 링크
    bpy.context.view_layer.layer_collection.children["MASK"].holdout = True


def shadow_catcher():
    bpy.data.objects["BASE_COLUMN"].is_shadow_catcher = True


def camera_shift():
    bpy.data.objects["CAMERA"].data.shift_x = 0.1


def empty_instancing():
    c = bpy.data.collections.new("INST")
    bpy.data.objects["KMJH_ARM_BASE"].instance_type = "COLLECTION"
    bpy.data.objects["KMJH_ARM_BASE"].instance_collection = c


def floor_modifier():
    bpy.data.objects["STUDIO_FLOOR"].modifiers.new("SOLIDIFY", "SOLIDIFY")


def resaved():
    pass                                                                    # 바꾼 것 없이 다시 저장 — 바이트(sha)만 다름


def floor_raised():
    bpy.data.objects["STUDIO_FLOOR"].location.z = 0.48                      # 장면 관문은 통과(위치는 안 봄) · 바닥이 로봇을 가려 프레임 줄 검사가 거부해야 함
    # 대조 계획에서 로봇 꼭대기 ≤ 0.384 m · 카메라 ≥ 0.579 m — 그 사이라 카메라에서 로봇으로 가는 광선이 모두 바닥을 먼저 지남
    # (첫 값 0.6 은 카메라보다 높아 천장이 되었을 뿐 가리지 못했다 — 2026-10-27 대조 47/48)


for name, fn in (("nudged", nudged), ("hidden", hidden), ("flipped", flipped), ("modifier", modifier),
                 ("collection-hidden", collection_hidden), ("camera-ray-off", camera_ray_off), ("extra-object", extra_object),
                 ("material-alpha", material_alpha), ("material-linked", material_linked), ("layer-holdout", layer_holdout),
                 ("shadow-catcher", shadow_catcher), ("camera-shift", camera_shift), ("empty-instancing", empty_instancing),
                 ("floor-modifier", floor_modifier), ("resaved", resaved), ("floor-raised", floor_raised)):
    bpy.ops.wm.open_mainfile(filepath=str(src), load_ui=False)
    fn()
    bpy.ops.wm.save_as_mainfile(filepath=str(checked_file(out_dir / f"blend-{name}.blend", root, scratch)), copy=True, compress=True)
print("VARIANTS_DONE")
