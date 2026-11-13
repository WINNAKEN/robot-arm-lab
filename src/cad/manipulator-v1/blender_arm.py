# Blender script (MP17): import an assembly GLB (trimesh, z-up mm) and render views with Workbench (vertex colours).
# blender -b -P blender_arm.py -- <in.glb> <out_prefix> <views comma list>
import math
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, prefix = argv[0], argv[1]
views = (argv[2] if len(argv) > 2 else "iso").split(",")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
RX = Matrix.Rotation(math.radians(-90.0), 4, "X")          # glTF y-up 가져오기 → 원래 z-up
for o in bpy.context.scene.objects:
    if o.parent is None:
        o.matrix_world = RX @ o.matrix_world
bpy.context.view_layer.update()
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
        hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
ctr, size = (lo + hi) / 2, (hi - lo).length
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light, sh.color_type, sh.show_cavity, sh.show_shadows, sh.show_object_outline = "STUDIO", "VERTEX", True, True, True
sh.cavity_type = "BOTH"
sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
sc.world = bpy.data.worlds.new("w")
sc.world.color = (0.91, 0.93, 0.95)
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * 0.9
cam_data.clip_start, cam_data.clip_end = 0.1, size * 10.0
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
DIRS = {"iso": (0.9, -1.3, 0.75), "isoback": (0.9, 1.3, 0.8), "front": (0.0, -1.0, 0.0), "top": (0.0, 0.0, 1.0), "side": (1.0, 0.0, 0.0)}
for v in views:
    d = Vector(DIRS[v]).normalized()
    cam.location = ctr + d * size * 2.0
    cam.rotation_euler = (0.0, 0.0, 0.0) if v == "top" else (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{prefix}-{v}.png"
    bpy.ops.render.render(write_still=True)
print("done")
