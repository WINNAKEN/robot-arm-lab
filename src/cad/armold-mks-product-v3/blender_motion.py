# -*- coding: utf-8 -*-
"""MP7 동작 영상 프레임 — 커밋된 블렌더 장면(kmjh-arm-v3.blend)을 **읽기만** 하고(저장하지 않음) 프레임을 JPEG 로 렌더한다. MP4 묶기는 motion_encode.py.

사용(화면 없이):
  blender.exe --background --factory-startup --python blender_motion.py -- --video turntable|motion --scheme brand|swap
      --blend <kmjh-arm-v3.blend> --model <v3 모델 폴더> --kin <v1 kinematics.json> --poses gallery_poses.json --plan motion_plan.json
      --path-check <motion/path-check.json> --frames <프레임 폴더> --scratch-root <작업 뿌리>
      [--samples 32] [--width 1280] [--height 720] [--quality 90] [--first N] [--last N] [--unpinned-blend]

- 장면 고정(검토 3 회): .blend 의 sha256 이 motion_scene_pin.json 의 값(MP7 에서 blender_scene.py 가 만들고 blender_verify.py 가 확인한 파일)이어야 한다.
  `--unpinned-blend` 는 대조 시험 전용 — 그 실행의 기록은 M_blend_pinned 가 거짓이라 motion_encode.py 가 받지 않는다. 아래 장면 확인은 그 위의 이중 방어다.
- turntable = 표시 자세 그대로 카메라가 한 바퀴(거리 · 렌즈 고정 — 모든 방향에서 상자 꼭짓점이 화면 90 % 안에 드는 가장 먼 거리 · 조명도 카메라와 함께 돈다).
  motion = motion_plan.json 의 자세 이동 — 카메라 방향 · 렌즈는 고정이고 겨누는 점 · 거리만 프레임마다 부드럽게 따라간다(가우스 σ 0.33 초 · 그 프레임에 필요한 거리
  이상) · 조명은 카메라 방향 기준으로 겨누는 점을 따라 옮긴다.
- 자세 → 빈 객체 Z 회전 = q − pose_deg(갤러리와 같음). 두 영상 모두 path_check.py 기록이 통과(all_ok)했고 · 그 입력 sha256(bodies.json · STL 47 ·
  kinematics · 계획 · 자세 · 검사 코드)이 지금 파일과 같고 · 샘플 밀도 per_frame ≥ 8 · 샘플 사이 꼭짓점 이동 ≤ 5 mm(motion_path 의 값) 이고 · 샘플 목록이
  지금 계획과 같아야 렌더한다. motion 은 모든 프레임 자세가 그 샘플 중 하나 · turntable 은 그 기록의 turntable 줄(표시 자세)이 통과.
- 장면 확인(렌더 전 · 하나라도 어긋나면 프레임 폴더 · meta 를 쓰지 않음): 객체 종류 수(메시 = 바디 + 바닥 · 빈 객체 7 · 조명 3 · 카메라 1) · 빈 객체는
  인스턴스 없음 · 바닥은 점 4 · 모디파이어 없음 · 배경 장면 · 재질 덮어쓰기 없음 · 카메라는 원근 · 렌즈 이동 0 · 뷰 레이어 1 · 메시 객체 = bodies.json 의
  바디(이름 · 링크 · 역할) · 표시 자세의 점 = 그 STL 점(≤ 2e-7 m) · 삼각면과 감김 = STL · 모디파이어 · 모양 키 없음 · 렌더에 보임(객체 숨김 · 카메라 광선 ·
  홀드아웃 · 그림자 받이 · 숨긴 인스턴서 아님 · 컬렉션 숨김 · 뷰 레이어 제외 · 홀드아웃 · 간접 전용 경로가 하나도 없음) · 재질 = 역할의 재질 하나(데이터
  슬롯 · Principled 가 표면에 바로 · 기본색 · 알파 연결 없음 · 알파 1). 세계 · 바닥 노드도 meta 전에. 합성 · 시퀀서는 끈다.
- 프레임마다: 모든 꼭짓점 = 표시 자세 점을 v1 축으로 돌린 값(≤ 2e-6 m) · 로봇 상자 꼭짓점이 모두 화면 안 · 카메라 클립 범위 안 · 카메라 광선(64 × 36 · 렌더에
  안 나오는 객체 제외)으로 로봇이 화면의 5 % 이상 · 바디 12 개 이상 · 몸체 5 · 남색 2 이상 보임(민트는 세기만 하고 요구하지 않음) · 파일 sha256.
  기록 = <프레임 폴더>/frames.jsonl · frames-meta.json(입력 · 설정 · 코드 sha256 · 블렌더 버전 · 빌드 해시 — 다르면 거부). 이어 하기는 파일 sha256 · 관절각 ·
  카메라 자리가 모두 기록과 같은 프레임만 건너뛴다(쓰다 끊긴 마지막 기록 줄은 버리고 그 프레임을 다시 렌더 · 중간 줄이 깨졌으면 거부). 끝나면
  <프레임 폴더>/frames-report.json(path-check · 스크립트 · 입력 · .blend 가 실행 중 바뀌지 않았는지도 검사).
- 화면은 가로가 긴 것만(센서 맞춤 = 가로). 바닥 페이드 · 재질 색 · 조명 회전은 blender_gallery.py 와 같은 값(메모리에서만).
- 쓰기는 가드를 거친 프레임 폴더(작업 뿌리 안)뿐이다 — 파이썬 바이트코드 캐시(__pycache__ · git 제외)는 예외."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import motion_path  # noqa: E402
from guard import checked_dir, checked_file, find_root  # noqa: E402

SCHEMES = {
    "brand": {"KMJH_White": "#FFFFFF", "KMJH_DeepNavy": "#0B2545", "KMJH_CoolGray": "#6B7280", "KMJH_Mint": "#34D399"},
    "swap": {"KMJH_White": "#6B7280", "KMJH_DeepNavy": "#0B2545", "KMJH_CoolGray": "#FFFFFF", "KMJH_Mint": "#34D399"},
}
ROLE_MAT = {"body": "KMJH_White", "accent": "KMJH_DeepNavy", "frame": "KMJH_CoolGray", "highlight": "KMJH_Mint"}
HERO_DIR = (-0.55, -1.0, 0.55)
FLOOR_FADE = (0.55, 2.2, 0.60)      # blender_gallery.py 와 같은 값
MIN_PER_FRAME, MAX_STEP_MM, CANON = motion_path.MIN_PER_FRAME, motion_path.MAX_STEP_MM, motion_path.CANON_SETTINGS


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, choices=["turntable", "motion"])
    ap.add_argument("--scheme", required=True, choices=sorted(SCHEMES))
    ap.add_argument("--blend", required=True, type=Path)
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--kin", required=True, type=Path)
    ap.add_argument("--poses", required=True, type=Path)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--path-check", required=True, type=Path)
    ap.add_argument("--frames", required=True, type=Path)
    ap.add_argument("--scratch-root", type=Path, default=None)
    ap.add_argument("--samples", type=int, default=CANON["samples"])
    ap.add_argument("--width", type=int, default=CANON["size"][0])
    ap.add_argument("--height", type=int, default=CANON["size"][1])
    ap.add_argument("--quality", type=int, default=CANON["quality"])
    ap.add_argument("--first", type=int, default=None)
    ap.add_argument("--last", type=int, default=None)
    ap.add_argument("--unpinned-blend", action="store_true", help="대조 시험 전용 — 고정 장면이 아닌 .blend 를 받는다(그 기록은 묶기가 거부)")
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


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def input_hashes(model, kin, plan, poses):
    """path_check.input_hashes 와 같은 값(블렌더 파이썬에는 numpy · trimesh 묶음이 없어 같은 규칙을 여기에 둠)."""
    model = Path(model)
    bd = json.loads((model / "bodies.json").read_text(encoding="utf-8"))
    return {"bodies_json": sha(model / "bodies.json"), "kinematics": sha(kin), "plan": sha(plan), "poses": sha(poses),
            "stl": {b["name"]: sha(model / "meshes" / f"{b['name']}.stl") for b in bd["bodies"]},
            "code": {n: sha(HERE / n) for n in ("pose_check.py", "path_check.py", "motion_path.py")}}


def render_visible_objects(scene):
    """카메라 광선 렌더에 나올 수 있는 객체 이름(검토 R2-04 · R3 BM3-01). 뷰 레이어가 하나여야 한다.
    컬렉션 경로: 제외(exclude)된 경로는 건너뜀 · 숨김(hide_render)은 그 아래 전부 · 보이는 경로가 하나라도 있으면 렌더 대상(블렌더도 OR).
    홀드아웃 · 간접 전용은 블렌더가 객체 하나(Base)에 경로 OR 로 모으므로 **한 경로라도** 그러면 안 보이는 것으로. 객체: hide_render · visible_camera ·
    is_holdout · is_shadow_catcher · 렌더에서 숨긴 인스턴서(instance_type ≠ NONE 이고 show_instancer_for_render 끔)."""
    if len(scene.view_layers) != 1 or not scene.view_layers[0].use:
        return set()
    enabled, flagged = set(), set()

    def walk(lc, hidden, hold):
        if lc.exclude:
            return
        h = hidden or getattr(lc.collection, "hide_render", False)
        hd = hold or lc.holdout or lc.indirect_only
        for ob in lc.collection.objects:
            if not h:
                enabled.add(ob.name)
            if hd:
                flagged.add(ob.name)
        for ch in lc.children:
            walk(ch, h, hd)
    walk(scene.view_layers[0].layer_collection, False, False)
    out = set()
    for name in enabled - flagged:
        ob = scene.objects.get(name)
        if ob is None or ob.hide_render or not ob.visible_camera or ob.is_holdout or ob.is_shadow_catcher:
            continue
        if ob.instance_type != "NONE" and not ob.show_instancer_for_render:
            continue
        out.add(name)
    return out


def material_problems(ob, want):
    """바디 재질이 역할의 재질 하나로 그대로 렌더되는지(검토 R3 BM3-02) — 어긋난 것들의 이름 목록(비면 정상)."""
    p = []
    if len(ob.material_slots) != 1 or len(ob.data.materials) != 1:
        return ["slot count"]
    sl = ob.material_slots[0]
    if sl.link != "DATA":
        p.append("slot linked to object")
    m = sl.material
    if m is None or m.name != want or ob.data.materials[0] != m:
        return p + ["material"]
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF") if nt else None
    out = nt.get_output_node("CYCLES") if nt else None
    if bsdf is None or out is None:
        return p + ["nodes"]
    links = out.inputs["Surface"].links
    if len(links) != 1 or links[0].from_node != bsdf:
        p.append("surface is not the Principled BSDF")
    if out.inputs["Volume"].is_linked or out.inputs["Displacement"].is_linked:
        p.append("volume / displacement")
    if bsdf.inputs["Base Color"].is_linked:
        p.append("base color linked")
    if bsdf.inputs["Alpha"].is_linked or abs(bsdf.inputs["Alpha"].default_value - 1.0) > 1e-9:
        p.append("alpha")
    return p


def match_points(ref_pts, world):
    """STL 점(m) ↔ 블렌더 세계 꼭짓점 — 점 수 · 양방향 최근접 거리 최대(blender_gallery.py 와 같음)."""
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


def main():
    import numpy as np
    a = args()
    root = find_root(HERE)
    if a.scratch_root is None:
        raise SystemExit("frames go under --scratch-root only (the MP4 is written by motion_encode.py)")
    frames_dir = checked_dir(a.frames, root, a.scratch_root)
    if Path(a.scratch_root).resolve() not in frames_dir.parents:
        raise SystemExit("frames go under --scratch-root only")

    def F_(p):
        return checked_file(p, root, a.scratch_root)
    if a.width < a.height:          # 검토 BM-3: fit · in_frame 은 센서 폭 = 화면 가로를 전제(아래에서 sensor_fit = HORIZONTAL 로 고정)
        raise SystemExit("landscape frames only (width >= height)")
    pin = json.loads((HERE / "motion_scene_pin.json").read_text(encoding="utf-8"))
    blend_sha_before = sha(a.blend)
    pinned = blend_sha_before == pin["blend_sha256"]
    if not pinned and not a.unpinned_blend:
        raise SystemExit("the .blend is not the pinned, verified scene (motion_scene_pin.json)")
    plan, poses = motion_path.load(a.plan, a.poses)
    pathc_bytes = a.path_check.read_bytes()                       # 검토 R2-PC-C: 관문에 쓴 바로 그 바이트의 sha256 을 기록(끝에 다시 대조)
    pathc_sha = hashlib.sha256(pathc_bytes).hexdigest()
    pathc = json.loads(pathc_bytes.decode("utf-8"))
    inputs_now = input_hashes(a.model, a.kin, a.plan, a.poses)
    if not pathc.get("all_ok") or pathc.get("inputs") != inputs_now:     # 검토 PC-2: 메시 · 기구학 · 계획 · 검사 코드가 그 뒤 바뀌었으면 낡은 기록
        raise SystemExit("path_check failed or ran on different inputs (meshes, bodies.json, kinematics, plan, poses or checker code) — rerun path_check.py")
    coarse = []                                                   # 검토 R2-PC-A · R3-DOC-3: 두 조건을 따로 알림
    if pathc.get("per_frame", 0) < MIN_PER_FRAME:
        coarse.append(f"per_frame {pathc.get('per_frame')} < {MIN_PER_FRAME}")
    if pathc.get("max_vertex_step_between_samples_mm", 1e9) > MAX_STEP_MM:
        coarse.append(f"vertex step {pathc.get('max_vertex_step_between_samples_mm'):.3f} mm > {MAX_STEP_MM}")
    if coarse:
        raise SystemExit("path_check too coarse: " + "; ".join(coarse))
    want = [(round(t, 6), [round(x, 6) for x in q]) for t, q, _k in motion_path.path_samples(plan, poses, pathc["per_frame"])]
    if want != [(r["t_s"], r["q_deg"]) for r in pathc["rows"]]:
        raise SystemExit("path_check checked a different plan / pose file — rerun path_check.py")
    if a.video == "turntable":          # 검토 R2-PC-D: 한 바퀴 자세도 입력 sha256 이 있는 path-check 의 turntable 줄로
        tt = pathc.get("turntable") or {}
        if not (tt.get("pose") == plan["turntable"]["pose"] and tt.get("q_deg") == poses[plan["turntable"]["pose"]] and tt.get("ok")):
            raise SystemExit("path_check has not passed the turntable pose")
        frames = [(f, None, poses[plan["turntable"]["pose"]], ang) for f, ang in motion_path.turntable_frames(plan)]
    else:
        frames = [(f, t, q, None) for f, t, q in motion_path.motion_frames(plan, poses)]
        checked_q = [r["q_deg"] for r in pathc["rows"]]
        unchecked = [f for f, _t, q, _x in frames if not any(max(abs(x - y) for x, y in zip(q, c)) <= 1e-5 for c in checked_q)]
        if unchecked:          # 프레임 자세는 모두 경로 샘플 중 하나여야(샘플 = 프레임의 8 배 · 구간 경계가 프레임에 맞음)
            raise SystemExit(f"frames whose pose path_check did not sample: {unchecked[:10]}")
    lo_f = a.first if a.first is not None else 0
    hi_f = a.last if a.last is not None else frames[-1][0]
    todo = [fr for fr in frames if lo_f <= fr[0] <= hi_f]
    # 검토 BM-1 · R2-06: 프레임 자세 · 카메라 · 화소를 정하는 모든 입력(경로 코드 · 기구학 · 검사 기록 · 블렌더 빌드 포함)과 설정을 묶는다 — 다르면 이어 하지 않는다
    bh = bpy.app.build_hash
    meta = {"video": a.video, "scheme": a.scheme, "inputs": inputs_now, "blend_sha256": blend_sha_before, "blend_pinned": pinned,
            "path_check_sha256": pathc_sha, "size": [a.width, a.height], "samples": a.samples, "quality": a.quality, "script_sha256": sha(__file__),
            "guard_sha256": sha(HERE / "guard.py"), "stl_topology_sha256": sha(HERE / "stl_topology.py"), "pin_sha256": sha(HERE / "motion_scene_pin.json"),
            "blender": bpy.app.version_string, "blender_build": bh.decode() if isinstance(bh, bytes) else str(bh)}
    meta_path = F_(frames_dir / "frames-meta.json")
    log_path = F_(frames_dir / "frames.jsonl")
    if log_path.exists() and not meta_path.exists():
        raise SystemExit(f"{frames_dir} has a frame log without frames-meta.json — use a new frames folder")
    if meta_path.exists() and json.loads(meta_path.read_text(encoding="utf-8")) != meta:
        raise SystemExit(f"{frames_dir} holds frames from different inputs or settings — use a new frames folder")
    done, good_lines, dropped_last = {}, [], False
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        for k, line in enumerate(lines):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                if k == len(lines) - 1:          # 검토 R2-09: 쓰다 끊긴 마지막 줄만 버림(그 프레임은 다시 렌더 · 아래에서 기록을 다시 씀)
                    dropped_last = True
                    continue
                raise SystemExit(f"frames.jsonl line {k + 1} is not JSON — use a new frames folder")
            done[r["frame"]] = r
            good_lines.append(line)

    bpy.ops.wm.open_mainfile(filepath=str(a.blend), load_ui=False)
    scene = bpy.context.scene
    objs = {o.name: o for o in scene.objects if o.type == "MESH" and o.name != "STUDIO_FLOOR"}
    empties = [scene.objects[f"JOINT_J{k}"] for k in range(1, 7)]
    cam = scene.objects["CAMERA"]
    cam_data = cam.data
    lights = [o for o in scene.objects if o.type == "LIGHT"]
    kin = json.loads(a.kin.read_text(encoding="utf-8"))
    J = [(np.asarray(j["origin_mm"], float) / 1000.0, np.asarray(j["axis_world"], float)) for j in kin["joints"]]
    pose_deg = [float(j["pose_deg"]) for j in kin["joints"]]

    for e in empties:
        e.rotation_euler.z = 0.0
    bpy.context.view_layer.update()
    display = {n: world_points(o) for n, o in objs.items()}

    # 장면 확인(검토 BM-5 · R2-05 · R3): 고정 장면 위의 이중 방어 — 어긋나면 아무것도 쓰지 않고 멈춘다
    from mathutils.kdtree import KDTree
    from stl_topology import mesh_tris_mapped, stl_mesh, topology_ok
    bd = json.loads((a.model / "bodies.json").read_text(encoding="utf-8"))
    vis = render_visible_objects(scene)
    types = {}
    for o in scene.objects:
        types[o.type] = types.get(o.type, 0) + 1
    floor = scene.objects.get("STUDIO_FLOOR")
    census = {"types": types == {"MESH": len(bd["bodies"]) + 1, "EMPTY": 7, "LIGHT": 3, "CAMERA": 1},
              "floor_plain_quad": floor is not None and floor.type == "MESH" and len(floor.data.vertices) == 4 and len(floor.modifiers) == 0
              and floor.data.shape_keys is None and floor.instance_type == "NONE",
              "empties_no_instancing": all(o.instance_type == "NONE" for o in scene.objects if o.type == "EMPTY"),
              "no_background_set": scene.background_set is None,
              "no_material_override": len(scene.view_layers) == 1 and scene.view_layers[0].material_override is None,
              "camera_perspective_no_shift": cam_data.type == "PERSP" and cam_data.shift_x == 0.0 and cam_data.shift_y == 0.0}
    scene_rows = {}
    for b in bd["bodies"]:
        ob = objs.get(b["name"])
        if ob is None:
            scene_rows[b["name"]] = {"ok": False, "missing": True}
            continue
        pts, ref_tris = stl_mesh(a.model / "meshes" / f"{b['name']}.stl")
        n0, n1, err = match_points(pts, display[b["name"]])
        tree = KDTree(len(pts))
        for i, p in enumerate(pts):
            tree.insert(p, i)
        tree.balance()
        polys = [list(pg.vertices) for pg in ob.data.polygons]
        tris, bad, nontri, collapsed = mesh_tris_mapped([tuple(p) for p in display[b["name"]].tolist()], polys, tree, 2e-7)
        topo = topology_ok(ref_tris, polys, tris, bad, nontri, collapsed)
        plain = len(ob.modifiers) == 0 and ob.data.shape_keys is None and ob.instance_type == "NONE"
        mp = material_problems(ob, ROLE_MAT.get(ob.get("role"), "?"))
        scene_rows[b["name"]] = {"stl_vertices": n0, "blender_vertices": n1, "max_nearest_m": err, "triangles_winding_equal_stl": topo,
                                 "no_modifiers_shape_keys_instancing": plain, "render_visible": ob.name in vis, "material_problems": mp,
                                 "ok": n0 == n1 and err <= 2e-7 and topo and plain and ob.name in vis and not mp
                                 and ob.get("link") == b["link"] and ob.get("role") == b["role"]}
    scene_ok = all(census.values()) and set(objs) == {b["name"] for b in bd["bodies"]} and all(r["ok"] for r in scene_rows.values())
    if not scene_ok:
        raise SystemExit(f"the .blend does not match the body STLs / bodies.json (census {types} {[k for k, v in census.items() if not v]}): "
                         f"{[(n, r.get('material_problems')) if r.get('material_problems') else n for n, r in scene_rows.items() if not r['ok']][:10]}")

    for mname, hx in SCHEMES[a.scheme].items():                    # 재질 색(조합) — 위에서 기본색 · 알파가 연결 없이 쓰이는 것을 확인함
        m = bpy.data.materials[mname]
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = hex_linear(hx)
        m.diffuse_color = hex_linear(hx)
    mat_ok = all(max(abs(x - y) for x, y in zip(ob.material_slots[0].material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value,
                                                hex_linear(SCHEMES[a.scheme][ROLE_MAT[ob["role"]]]))) <= 1e-6 for ob in objs.values())
    if not mat_ok:                      # 검토 R2-08: 렌더 전에 멈춤
        raise SystemExit("robot materials do not match the colour scheme")

    # 바닥 페이드(카메라 광선만) — blender_gallery.floor_fade 와 같은 노드 · meta 를 쓰기 전에(검토 R3 BM3-04)
    wn = scene.world.node_tree.nodes
    mixw = [n for n in wn if n.type == "MIX_SHADER"]
    if len(mixw) != 1 or not mixw[0].inputs[2].links or "STUDIO_FLOOR" not in bpy.data.materials:
        raise SystemExit("the world / floor nodes are not the ones blender_scene.py builds")
    cam_bg = mixw[0].inputs[2].links[0].from_node
    r0, r1, strength = FLOOR_FADE
    nt = bpy.data.materials["STUDIO_FLOOR"].node_tree
    N, L = nt.nodes, nt.links
    if "Principled BSDF" not in N or "Material Output" not in N or "Color" not in cam_bg.inputs:
        raise SystemExit("the world / floor nodes are not the ones blender_scene.py builds")
    cam_bg.inputs["Strength"].default_value = strength
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
    scene.render.use_compositing = False          # 검토 R2-10: .blend 의 합성 노드(파일 출력 등)가 가드 밖에 쓰지 않게
    scene.render.use_sequencer = False

    # 모든 관문 통과 → 이제야 프레임 폴더 · meta 를 쓴다(검토 R2-01: 거부된 실행이 meta 를 남겨 다음 실행을 막지 않게)
    frames_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if dropped_last:
        with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(ln + "\n" for ln in good_lines))
        print("MOTION_LOG_LAST_LINE_DROPPED", flush=True)

    def bounds_pts(obs):
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        return lo, hi

    def set_q(q):
        deltas = [x - p for x, p in zip(q, pose_deg)]
        for e, d in zip(empties, deltas):
            e.rotation_euler.z = math.radians(d)
        bpy.context.view_layer.update()
        return deltas

    def pose_err(deltas):
        err = 0.0
        for n, ob in objs.items():
            Q = display[n].copy()
            for k in range(int(ob["link"]), 0, -1):
                if deltas[k - 1]:
                    O, A = J[k - 1]
                    Q = (Q - O) @ rot_np(A, deltas[k - 1]).T + O
            err = max(err, float(np.max(np.linalg.norm(world_points(ob) - Q, axis=1))))
        return err

    light0 = {lo.name: lo.location.copy() for lo in lights}
    lo0, hi0 = bounds_pts(list(objs.values()))
    c_light = (lo0 + hi0) / 2
    az0 = math.atan2(HERO_DIR[1], HERO_DIR[0])

    def place_lights(direction, center):
        R = Matrix.Rotation(math.atan2(direction[1], direction[0]) - az0, 4, "Z")
        for lo in lights:
            lo.location = center + (R @ (light0[lo.name] - c_light))
            look_at(lo, center)

    MARGIN = 0.90      # 화면 가로 · 세로의 90 % 안에

    def basis(d):
        f = -Vector(d).normalized()
        r = f.cross(Vector((0, 0, 1))).normalized()
        return f, r, r.cross(f)

    def fit(P, target, d, lens, shift=True):
        """점 P(N × 3 · 세계 m)가 카메라(target + d·D 에서 target 을 봄) 화면의 가로 · 세로 MARGIN 안에 드는 가장 짧은 D · 투영 가운데로 target 을 옮김(3 회)."""
        tx = cam_data.sensor_width / 2 / lens * MARGIN          # 센서 맞춤 = 가로(아래에서 고정) — 센서 폭 = 화면 가로
        ty = tx * a.height / a.width
        tgt = np.array(target, float)
        D = 1.0
        for _ in range(3 if shift else 1):
            f, r, u = (np.array(v) for v in basis(d))

            def ok(D_):
                v = P - (tgt + np.array(Vector(d).normalized()) * D_)
                z = v @ f
                return bool(np.all(z > 1e-3) and np.all(np.abs(v @ r) <= z * tx) and np.all(np.abs(v @ u) <= z * ty))
            lo_, hi_ = 0.05, 30.0
            for _ in range(60):
                mid = (lo_ + hi_) / 2
                lo_, hi_ = (lo_, mid) if ok(mid) else (mid, hi_)
            D = hi_
            v = P - (tgt + np.array(Vector(d).normalized()) * D)
            z = v @ f
            xs, ys = (v @ r) / z, (v @ u) / z
            zc = float(np.median(z))
            if shift:
                tgt = tgt + r * ((xs.max() + xs.min()) / 2 * zc) + u * ((ys.max() + ys.min()) / 2 * zc)
        return Vector(tgt), D

    def corners():
        return np.array([tuple(o.matrix_world @ Vector(c)) for o in objs.values() for c in o.bound_box], float)

    def aim(target, D, d, lens):
        cam_data.lens = lens
        cam.location = target + Vector(d).normalized() * D
        look_at(cam, target)

    # 카메라 자리 — turntable: 표시 자세 상자 꼭짓점이 모든 방향에서 들어가는 거리 하나(줌 고정) · motion: 프레임마다 따라가는 카메라(아래)
    cam_data.sensor_fit = "HORIZONTAL"          # 검토 BM-3: 센서 폭 = 화면 가로를 명시(fit · in_frame 의 전제)
    if a.video == "turntable":
        tt = plan["turntable"]
        set_q(poses[tt["pose"]])
        P = corners()
        lo, hi = bounds_pts(list(objs.values()))
        center = (lo + hi) / 2
        Ds = []
        for _f, _t, _q, ang in frames:
            base = math.atan2(HERO_DIR[1], HERO_DIR[0]) + math.radians(ang)
            Ds.append(fit(P, center, Vector((math.cos(base), math.sin(base), tt["elevation"])).normalized(), tt["lens_mm"], shift=False)[1])
        D_tt = max(Ds)
    else:
        # 따라가는 카메라: 방향 · 렌즈는 고정, 겨누는 점 · 거리만 프레임마다 — 프레임별 맞춤을 시간으로 부드럽게(가우스 σ = 0.33 초) 하고,
        # 거리는 ±0.75 초 안의 최대를 부드럽게 한 값과 그 프레임에 꼭 필요한 거리 중 큰 쪽(화면 밖으로 나가지 않게).
        mv = plan["motion"]
        d_m = Vector(mv["direction"]).normalized()
        Pf, T0 = [], []
        for _f, _t, q, _x in frames:
            set_q(q)
            P_ = corners()
            Pf.append(P_)
            T0.append(np.array(fit(P_, Vector(tuple((P_.min(axis=0) + P_.max(axis=0)) / 2)), d_m, mv["lens_mm"])[0]))
        fps = plan["fps"]
        sig, win = 0.33 * fps, int(round(0.75 * fps))
        n_f = len(frames)

        def gsmooth(arr):
            arr = np.asarray(arr, float)
            out = np.empty_like(arr)
            for i in range(n_f):
                j = np.arange(max(0, i - 3 * int(sig)), min(n_f, i + 3 * int(sig) + 1))
                w = np.exp(-0.5 * ((j - i) / sig) ** 2)
                out[i] = (w[:, None] * arr[j]).sum(axis=0) / w.sum() if arr.ndim == 2 else (w * arr[j]).sum() / w.sum()
            return out
        T_s = gsmooth(np.array(T0))
        D_need = np.array([fit(Pf[i], Vector(tuple(T_s[i])), d_m, mv["lens_mm"], shift=False)[1] for i in range(n_f)])
        D_max = np.array([D_need[max(0, i - win):i + win + 1].max() for i in range(n_f)])
        D_s = np.maximum(gsmooth(D_max), D_need)
        cam_path = {frames[i][0]: (Vector(tuple(T_s[i])), float(D_s[i])) for i in range(n_f)}

    def in_frame(P):
        """모든 점이 카메라 화면 안(여백 없이 100 %) · 클립 범위 안인지 — 지금 카메라 자리 · 방향(블렌더 카메라 행렬)으로."""
        fwd = np.array(cam.matrix_world.to_3x3() @ Vector((0, 0, -1)))
        rt = np.array(cam.matrix_world.to_3x3() @ Vector((1, 0, 0)))
        up = np.array(cam.matrix_world.to_3x3() @ Vector((0, 1, 0)))
        v = P - np.array(cam.location)
        z = v @ fwd
        tx = cam_data.sensor_width / 2 / cam_data.lens
        ty = tx * a.height / a.width
        return bool(np.all(z > cam_data.clip_start) and np.all(z < cam_data.clip_end)
                    and np.all(np.abs(v @ rt) <= z * tx) and np.all(np.abs(v @ up) <= z * ty))

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = a.width, a.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = a.quality
    robot = set(objs.values())

    def visible(nx=64, ny=36):
        dg = bpy.context.evaluated_depsgraph_get()
        tr, br, bl, tl = [cam.matrix_world @ v for v in cam_data.view_frame(scene=scene)]
        o = cam.matrix_world.translation
        hits, rays = {}, 0
        for iy in range(ny):
            for ix in range(nx):
                u, v = (ix + 0.5) / nx, (iy + 0.5) / ny
                d = (tl.lerp(tr, u).lerp(bl.lerp(br, u), v) - o).normalized()
                ok, _l, _n, _i, ob, _m = scene.ray_cast(dg, o, d)
                if ok and ob in robot and ob.name in vis:          # 검토 BM-2 · R2-04: 렌더에 안 나오는 객체는 안 보이는 것으로
                    rays += 1
                    hits[ob.name] = hits.get(ob.name, 0) + 1
        by_role = {}
        for n in hits:
            by_role[objs[n]["role"]] = by_role.get(objs[n]["role"], 0) + 1
        return rays / (nx * ny), len(hits), by_role

    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        for f, t, q, ang in todo:
            path = F_(frames_dir / f"{f:04d}.jpg")
            deltas = set_q(q)
            if a.video == "turntable":
                base = math.atan2(HERO_DIR[1], HERO_DIR[0]) + math.radians(ang)
                d = Vector((math.cos(base), math.sin(base), tt["elevation"])).normalized()
                aim(center, D_tt, d, tt["lens_mm"])                 # 수직축 둘레를 같은 거리로(줌 고정 · 화면 안 — fit 의 최대 거리)
                place_lights(d, center)
            else:
                tgt_f, D_f = cam_path[f]
                aim(tgt_f, D_f, d_m, mv["lens_mm"])
                place_lights(d_m, tgt_f)
            bpy.context.view_layer.update()
            if (f in done and path.exists() and sha(path) == done[f]["sha256"] and done[f]["q_deg"] == [round(x, 6) for x in q]
                    and done[f]["camera_location_m"] == [round(x, 6) for x in cam.location]):
                continue           # 이어 하기 — 파일 · 관절각 · 카메라 자리가 모두 기록과 같을 때만(검토 BM-1)
            err = pose_err(deltas)
            whole = in_frame(corners())
            frac, nb, by_role = visible()
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            row = {"frame": f, "t_s": t, "angle_deg": ang, "q_deg": [round(x, 6) for x in q], "pose_err_m": err,
                   "camera_location_m": [round(x, 6) for x in cam.location], "lens_mm": cam_data.lens, "robot_box_in_frame": whole,
                   "robot_ray_fraction": frac, "bodies_hit": nb, "bodies_hit_by_role": by_role, "sha256": sha(path),
                   "ok": err <= 2e-6 and whole and frac >= 0.05 and nb >= 12 and by_role.get("body", 0) >= 5 and by_role.get("accent", 0) >= 2}
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            done[f] = row
            print("MOTION_FRAME", a.video, a.scheme, f, "ok" if row["ok"] else "BAD", flush=True)

    all_frames = [fr[0] for fr in frames]
    complete = all(f in done for f in all_frames)
    rep = {"video": a.video, "scheme": a.scheme, "fps": plan["fps"], "frames_total": len(all_frames), "frames_done": sum(1 for f in all_frames if f in done),
           "size": [a.width, a.height], "samples": a.samples, "quality": a.quality, "blend_sha256": blend_sha_before, "plan_sha256": sha(a.plan),
           "poses_sha256": sha(a.poses), "path_check_sha256": pathc_sha, "blender": meta["blender"], "blender_build": meta["blender_build"],
           "inputs": inputs_now, "frames_meta_sha256": sha(meta_path), "script_sha256": meta["script_sha256"],
           "scene_vs_stl": {"bodies": len(scene_rows), "max_nearest_m": max(r.get("max_nearest_m", 1.0) for r in scene_rows.values()),
                            "census": types, "census_checks": census},
           "checks": {"M_all_frames_rendered": complete,
                      "M_every_frame_ok": complete and all(done[f]["ok"] for f in all_frames),
                      "M_blend_pinned": pinned,
                      "M_scene_equals_stl_and_bodies": scene_ok,
                      "M_materials_equal_scheme": mat_ok,
                      "M_inputs_unchanged_during_run": input_hashes(a.model, a.kin, a.plan, a.poses) == inputs_now,
                      "M_path_check_unchanged_during_run": sha(a.path_check) == pathc_sha,
                      "M_script_unchanged_during_run": sha(__file__) == meta["script_sha256"],
                      "M_blend_not_modified": sha(a.blend) == blend_sha_before},
           "max_pose_err_m": max((done[f]["pose_err_m"] for f in all_frames if f in done), default=None),
           "min_robot_ray_fraction": min((done[f]["robot_ray_fraction"] for f in all_frames if f in done), default=None),
           "frames_sha256": {str(f): done[f]["sha256"] for f in all_frames if f in done}}
    F_(frames_dir / "frames-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("MOTION_CHECKS", json.dumps(rep["checks"]))
    print("MOTION_DONE" if all(rep["checks"].values()) else "MOTION_INCOMPLETE_OR_FAILED")


if __name__ == "__main__":
    main()
