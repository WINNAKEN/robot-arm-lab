# -*- coding: utf-8 -*-
"""MP4 A3 — J2(어깨) 모듈의 첫 분할: 실제 부품 여섯(뒤 하우징 · 감속기 하우징 · 출력 플랜지 · 베어링 누름판 · 색 링 · 끝 덮개)과 참조 몸체(모터 ·
드라이버 · 커넥터 가정 상자 · 감속기 공간 · 출력 베어링 자리 표시 · A2 의 자식 링크 허브와 관)를 J2 의 지역 좌표에 그리고 검사한다.

J2 의 지역 좌표: 출력 축 +Z(= Link2 의 +Y) · 관절 중심 원점 · 출력 면 z = +D/2 · +X = Link2 의 +X(표시 자세에서 상완이 뻗는 쪽) · +Y = −(Link2 의 +Z).
표시 자세의 A2 조립에서 +Z 는 v1 `kinematics.json` 의 J2 축(세계 [-0.2588, 0.9659, 0] — J1 의 표시 회전 15° 가 들어감)이다.

사용: python build_j2_split.py --cli <solidcraft-cli.exe> [--out <폴더>] [--evidence <폴더>]
산출(out): `j2-split.solidcraft` · STEP · `parts/<부품>.stl` · `iso.png` · `section.png` · `split.json`(부품 · 접속면 · 체결 · 검사) · `build-commands.json`.
검사: 부품끼리 체적 간섭 0 · 참조(모터 · 드라이버 · 커넥터 · 감속기 공간 · 베어링 자리)와 부품 간섭 0 · A2 의 자식 링크(허브 · 관)와 부품 간섭 0 · 부품이
A2 의 J2 외곽(모듈 ∪ 링 ∪ 덮개 — 같은 지역 좌표로 다시 그림) 안. 같은 평면에서 닿기만 하는 쌍은 「닿음」 으로 따로 적는다."""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from v2geom import Builder, Frame, Spec  # noqa: E402

ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), Path(r"C:\projects\robot-arm-lab"))
V1 = ROOT / "models" / "armold-mks-concept-v1"
ENV_SCALE = 1.001          # A2 외곽을 원점 기준으로 키우는 비율(검사용)
CONTACT_MM = 1e-3          # 간섭 상자의 가장 얇은 변이 이보다 얇으면 닿음(같은 평면의 접촉)으로 센다
REAR_FILLET = 5            # 뒷벽 바깥 모서리 둥글림 — A2 모듈(v2geom.Builder.module)과 같은 값
VOL_TOL_REL = 1e-5         # 곡면 부피의 테셀레이션 잡음 — 끝 덮개의 eval 부피가 해석값과 1.25e-5 · 외곽 교차의 합과 1.7e-6 다름(2026-10-23 실측)
MESH_CONTACT_MM3 = 0.01    # 메시 교차로 가를 때 「닿음」 의 상한 — inspect.clearance 의 기본 min_volume 과 같은 값


def mesh_intersection(path_a, path_b):
    """두 STL 의 교차 부피(mm³)와 그 상자 — 정확 커널이 못 한 쌍에만 쓴다."""
    import manifold3d as m3d
    import numpy as np
    import trimesh

    def solid(path):
        m = trimesh.load(path, force="mesh")
        return m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(m.vertices, dtype=np.float32), tri_verts=np.asarray(m.faces, dtype=np.uint32)))

    both = solid(path_a) ^ solid(path_b)
    volume = float(both.volume()) if hasattr(both, "volume") else float(both.get_volume())
    lo, hi = both.bounding_box()[:3], both.bounding_box()[3:]
    return volume, {"min": [float(x) for x in lo], "max": [float(x) for x in hi]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "armold-mks-product-v2" / "j2-split")
    ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "product-v2-evidence" / "j2-split")
    a = ap.parse_args()
    (a.out / "parts").mkdir(parents=True, exist_ok=True)
    a.evidence.mkdir(parents=True, exist_ok=True)
    spec = Spec(HERE / "parameters.json", V1)
    sp = spec.p["j2_split"]
    D, R, RC, LC, CAP = spec.D, spec.RD[1], spec.RC, spec.LC, spec.CAP
    RW, RT = spec.RING_W, spec.RING_T
    z_rear, z_top = -D / 2, D / 2
    z_can_end = z_rear - LC
    wall = sp["rear_wall_thickness_mm"]
    bore = RC - sp["can_wall_mm"]
    red_r, lip_r = sp["reducer_space_radius_mm"], sp["lip_inner_radius_mm"]
    b = sp["output_bearing_placeholder"]
    seat_r, bear_w = b["od_mm"] / 2, b["width_mm"]
    bt = sp["bearing_retainer"]
    # 고정된 쪽의 가장 높은 면(누름판 · 색 링의 윗면)은 출력 면보다 틈만큼 낮다 — 자식 링크(출력 면 z = +D/2 에서 시작)는 출력 플랜지에만 닿는다
    # (L4 R1 F1 · 감속기 하우징의 윗면은 그 밑 — 누름판 아랫면).
    z_static = z_top - sp["stationary_top_gap_mm"]
    z_ret0 = z_static - bt["thickness_mm"]                # 베어링 누름판의 아랫면 = 베어링 바깥 고리의 윗면
    z_seat0 = z_ret0 - bear_w
    z_lip0 = z_seat0 - sp["lip_height_mm"]
    z_ring0 = z_static - RW
    fl = sp["output_flange"]
    m = sp["motor_interface"]
    j = sp["joint_bolts"]
    mk = Builder(spec)
    F = Frame()
    parts = []

    def comp(name):
        mk.cmd("component.activate", component="root")
        mk.cmd("component.create", name=name)

    def rev(name, role, profile):
        mk.revolve(F, name, None, role, [0, 0, 0], [0, 0, 1], profile)

    def hole(body, x, y, z_face, depth, dia, tag, down=True):
        """z_face 면에서 깊이 depth 의 구멍 — down 이면 −Z 로, 아니면 +Z 로."""
        mk.cmd("sketch.create", name=f"{body}_H_{tag}", plane={"origin": [x, y, z_face], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
        mk.cmd("sketch.circle.center", center=[0, 0], radius=dia / 2)
        mk.cmd("sketch.finish")
        mk.cmd("solid.extrude", distance=depth, direction="negative" if down else "positive", operation="cut", targets=[body],
               name=f"{body}_HOLE_{tag}")

    def ring_pts(n, r, phase_deg):
        return [(r * math.cos(math.radians(phase_deg + 360 * i / n)), r * math.sin(math.radians(phase_deg + 360 * i / n))) for i in range(n)]

    # ---- 부품 1: 뒤 하우징 = 모터 캔 + 뒷벽 + 끝 덮개 기둥 셋(흰) ----
    comp("PART_REAR_HOUSING")
    name = "J2_REAR_HOUSING"
    rev(name, "body", [(z_can_end, bore), (z_can_end, RC), (z_rear, RC), (z_rear, R), (z_rear + wall, R), (z_rear + wall, 0), (z_rear, 0),
                       (z_rear, bore)])
    mk.fillet_circle(F, name, [0, 0, 0], [0, 0, 1], z_rear, R, REAR_FILLET)
    hole(name, 0, 0, z_rear + wall, wall, m["pilot_dia_mm"], "PILOT")
    for i, (x, y) in enumerate([(sx * m["bolt_square_mm"] / 2, sy * m["bolt_square_mm"] / 2) for sx in (-1, 1) for sy in (-1, 1)]):
        hole(name, x, y, z_rear + wall, wall, m["bolt_clearance_dia_mm"], f"M{i}")
    for i, (x, y) in enumerate(ring_pts(j["count"], j["radius_mm"], j["phase_deg"])):
        hole(name, x, y, z_rear + wall, wall, j["clearance_dia_mm"], f"J{i}")
        hole(name, x, y, z_rear, j["counterbore_depth_mm"], j["counterbore_dia_mm"], f"JC{i}", down=False)
    # 끝 덮개를 잡는 기둥: 뒷벽에서 덮개 턱의 윗면 조금 앞까지(출력 방향 — 뒷벽이 판에 닿고 캔이 위로 — 에서 내민 곳이 없다) · 캔 벽까지 이은 갈비 ·
    # 덮개 쪽 끝에 인서트 구멍. 각도는 모터 · 드라이버 · 커넥터 가정 상자를 피한 0 · 90 · 270°(커넥터 = −X). 기둥 끝과 턱 사이를 띄운다 — 덮개는
    # 캔 끝에만 닿는다(두 곳에 닿으면 과구속 · 같은 평면이면 교차 계산도 실패했다).
    cap = sp["end_cap"]
    z_pillar_end = z_can_end + cap["spigot_height_mm"] + cap["pillar_gap_to_spigot_mm"]
    pr = cap["screw_radius_mm"]
    for k, ang in enumerate(cap["screw_angles_deg"]):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        pn = f"{name}_PILLAR{k}"
        # 기둥 · 갈비는 뒷벽 속으로 1 mm 더 들어간다 — 윗면이 뒷벽 아랫면과 같은 평면이면 합치기가 실패한다(2026-10-23 실측 · 「no result」).
        h = z_rear + 1.0 - z_pillar_end
        mk.cmd("solid.cylinder", radius=cap["pillar_dia_mm"] / 2, height=h, base=[pr * c, pr * s, z_pillar_end], axis="Z",
               operation="new", body_name=pn, name=pn + "_C")
        mk.cmd("sketch.create", name=pn + "_RIB_P", plane={"origin": [pr * c, pr * s, z_pillar_end], "x_dir": [c, s, 0], "y_dir": [-s, c, 0]})
        half = cap["pillar_dia_mm"] / 2
        mk.cmd("sketch.line", points=[[0, -half], [cap["pillar_rib_to_radius_mm"] - pr, -half], [cap["pillar_rib_to_radius_mm"] - pr, half], [0, half]],
               closed=True)
        mk.cmd("sketch.finish")
        mk.cmd("solid.extrude", distance=h, operation="new", body_name=pn + "_RIB", name=pn + "_RIB_X")
        mk.cmd("solid.combine", target=pn, tools=[pn + "_RIB"], operation="join")
        mk.cmd("solid.combine", target=name, tools=[pn], operation="join")
        hole(name, pr * c, pr * s, z_pillar_end, cap["insert_depth_mm"], cap["insert_hole_dia_mm"], f"CI{k}", down=False)
    parts.append(name)

    # ---- 부품 2: 감속기 하우징 = 드럼 고리 · 감속기 공간 · 턱 · 출력 베어링 자리 · 색 링 자리 · 누름판 인서트(흰) ----
    comp("PART_REDUCER_HOUSING")
    name = "J2_REDUCER_HOUSING"
    zb = z_rear + wall
    rev(name, "body", [(zb, red_r), (zb, R), (z_ring0, R), (z_ring0, R - RT), (z_ret0, R - RT), (z_ret0, seat_r), (z_seat0, seat_r),
                       (z_seat0, lip_r), (z_lip0, lip_r), (z_lip0, red_r)])
    for i, (x, y) in enumerate(ring_pts(j["count"], j["radius_mm"], j["phase_deg"])):
        hole(name, x, y, zb, j["insert_depth_mm"], j["insert_hole_dia_mm"], f"I{i}", down=False)
    for i, (x, y) in enumerate(ring_pts(bt["screw_count"], bt["screw_radius_mm"], bt["screw_phase_deg"])):
        hole(name, x, y, z_ret0, bt["insert_depth_mm"], bt["insert_hole_dia_mm"], f"RI{i}")
    parts.append(name)

    # ---- 부품 3: 출력 플랜지 — 베어링 안 고리에 끼고, 아래는 감속기 출력 · 위(출력 면 z = +D/2)는 자식 링크(흰) ----
    comp("PART_OUTPUT_FLANGE")
    name = "J2_OUTPUT_FLANGE"
    fr, cr = b["id_mm"] / 2, fl["collar_radius_mm"]
    z_f0 = z_seat0 - fl["collar_height_mm"]
    z_f1 = z_top
    rev(name, "body", [(z_f0, 0), (z_f0, cr), (z_seat0, cr), (z_seat0, fr), (z_f1, fr), (z_f1, 0)])
    hole(name, 0, 0, z_f0, fl["reducer_pilot_depth_mm"], fl["reducer_pilot_dia_mm"], "RPILOT", down=False)
    for i, (x, y) in enumerate(ring_pts(fl["insert_count"], fl["insert_radius_mm"], 0)):
        hole(name, x, y, z_f0, fl["insert_depth_mm"], j["insert_hole_dia_mm"], f"RI{i}", down=False)
    for i, (x, y) in enumerate(ring_pts(fl["insert_count"], fl["insert_radius_mm"], 180 / fl["insert_count"])):
        hole(name, x, y, z_f1, fl["insert_depth_mm"], j["insert_hole_dia_mm"], f"CI{i}")
    parts.append(name)

    # ---- 부품 4: 베어링 누름판 — 베어링 바깥 고리를 위에서 누르고, 바깥 테두리로 색 링을 붙잡는다(흰 · M3 여섯) ----
    comp("PART_BEARING_RETAINER")
    name = "J2_BEARING_RETAINER"
    rev(name, "body", [(z_ret0, bt["inner_radius_mm"]), (z_ret0, bt["outer_radius_mm"]), (z_static, bt["outer_radius_mm"]), (z_static, bt["inner_radius_mm"])])
    for i, (x, y) in enumerate(ring_pts(bt["screw_count"], bt["screw_radius_mm"], bt["screw_phase_deg"])):
        hole(name, x, y, z_static, bt["thickness_mm"], bt["clearance_dia_mm"], f"C{i}")
        hole(name, x, y, z_static, bt["counterbore_depth_mm"], bt["counterbore_dia_mm"], f"CB{i}")
    parts.append(name)

    # ---- 부품 5 · 6: 색 링(누름판 테두리 밑에 걸림) · 끝 덮개(기둥 셋에 M3)(주황) ----
    comp("PART_ACCENT_RING")
    clr = sp["accent_ring_radial_clearance_mm"]
    notch_r = bt["outer_radius_mm"] + bt["radial_clearance_mm"]
    rev("J2_ACCENT_RING_PART", "accent", [(z_ring0, R - RT + clr), (z_ring0, R), (z_static, R), (z_static, notch_r), (z_ret0, notch_r), (z_ret0, R - RT + clr)])
    parts.append("J2_ACCENT_RING_PART")
    comp("PART_END_CAP")
    name = "J2_END_CAP_PART"
    sr = bore - cap["spigot_radial_clearance_mm"]
    rev(name, "accent", [(z_can_end - CAP, 0), (z_can_end - CAP, RC - 1), (z_can_end, RC - 1), (z_can_end, sr), (z_can_end + cap["spigot_height_mm"], sr),
                         (z_can_end + cap["spigot_height_mm"], sr - cap["spigot_wall_mm"]), (z_can_end, sr - cap["spigot_wall_mm"]), (z_can_end, 0)])
    mk.fillet_circle(F, name, [0, 0, 0], [0, 0, 1], z_can_end - CAP, RC - 1, cap["outer_fillet_mm"])
    hole(name, 0, 0, z_can_end, CAP, cap["cable_exit_dia_mm"], "CABLE")
    for k, ang in enumerate(cap["screw_angles_deg"]):
        x, y = pr * math.cos(math.radians(ang)), pr * math.sin(math.radians(ang))
        hole(name, x, y, z_can_end, CAP, cap["clearance_dia_mm"], f"S{k}")
        hole(name, x, y, z_can_end - CAP, cap["counterbore_depth_mm"], cap["counterbore_dia_mm"], f"SB{k}", down=False)
    parts.append(name)

    # ---- 참조 몸체(부품 아님): 모터 · 드라이버 · 커넥터 가정 상자(모터 면 = 뒷벽 아랫면) · 감속기 공간 · 베어링 자리 ----
    comp("REFERENCE")
    p1 = spec.v1
    refs = []

    def box(name, cx, cy, z0, sx, sy, h):
        mk.cmd("sketch.create", name=name + "_P", plane={"origin": [cx, cy, z0], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
        mk.cmd("sketch.line", points=[[-sx / 2, -sy / 2], [sx / 2, -sy / 2], [sx / 2, sy / 2], [-sx / 2, sy / 2]], closed=True)
        mk.cmd("sketch.finish")
        mk.cmd("solid.extrude", distance=h, operation="new", body_name=name, name=name + "_X")
        refs.append(name)

    mf, ml, dw, dd, cc = p1["motor_frame_mm"], p1["motor_length_mm"], p1["driver_width_mm"], p1["driver_depth_mm"], p1["connector_clearance_mm"]
    z_motor0 = z_rear - ml
    z_drv0 = z_motor0 - 2 - dd
    box("REF_MOTOR_ASSUMED", 0, 0, z_motor0, mf, mf, ml)
    box("REF_DRIVER_ASSUMED", 0, 0, z_drv0, dw, dw, dd)
    box("REF_CONNECTOR_ASSUMED", -dw / 2 - cc / 2, 0, z_drv0, cc, 20, dd)
    mk.cmd("solid.cylinder", radius=red_r, height=z_lip0 - zb, base=[0, 0, zb], axis="Z", operation="new", body_name="REF_REDUCER_SPACE", name="REF_RS")
    refs.append("REF_REDUCER_SPACE")
    mk.cmd("solid.cylinder", radius=seat_r, height=bear_w, base=[0, 0, z_seat0], axis="Z", operation="new", body_name="REF_OUTPUT_BEARING", name="REF_OB")
    mk.cmd("solid.cylinder", radius=b["id_mm"] / 2, height=bear_w, base=[0, 0, z_seat0], axis="Z", operation="cut", targets=["REF_OUTPUT_BEARING"], name="REF_OB_ID")
    refs.append("REF_OUTPUT_BEARING")
    for r in refs:
        mk.cmd("appearance.assign", bodies=[r], color="#5aa9e6", opacity=0.35)

    # ---- A2 의 자식 링크(Link2)의 허브 · 관 — A2 의 `v2geom.Builder.link(2)` 와 같은 치수 · 위 지역 좌표(Link2 의 (x, y, z) → (x, −z, y)) ----
    comp("A2_CHILD")
    u = spec.p["links"]["upper_arm"]
    child = ["A2_CHILD_HUB", "A2_CHILD_TUBE"]
    mk.hub(F, "A2_CHILD_HUB", None, [0, 0, 0], [0, 0, 1], u["hub_r"], z_top, z_top + u["hub_t"])
    mk.tube(F, "A2_CHILD_TUBE", None, [0, 0, z_top + u["hub_t"] / 2], [spec.offs[2][0], 0, z_top + u["hub_t"] / 2], u["tube_r"])
    for c_ in child:
        mk.cmd("appearance.assign", bodies=[c_], color="#e8e8e8", opacity=0.25)

    # ---- A2 의 J2 외곽(같은 지역 좌표 · 출력 +Z): 모듈 ∪ 링 ∪ 덮개 ----
    comp("A2_ENVELOPE")
    env = Builder(spec)
    env.module(F, 2, None, [0, 0, 0], [0, 0, 1])
    mk.commands += env.commands
    envelope = [x["name"] for x in env.bodies]
    # 외곽을 0.1 % 키운다 — 부품과 외곽의 면이 겹쳐 있으면(같은 덮개 · 같은 바깥 원통) 교차 계산이 실패하므로, 겹친 면을 떼어 「안에 든다」 만 본다.
    mk.cmd("solid.scale", bodies=envelope, factor=ENV_SCALE, origin=[0, 0, 0])
    for e in envelope:
        mk.cmd("appearance.assign", bodies=[e], color="#cccccc", opacity=0.15)

    mk.cmd("component.activate", component="root")
    for p in parts:
        mk.cmd("file.export", path=str(a.out / "parts" / f"{p}.stl"), bodies=[p])
    mk.cmd("inspect.interference", budget_s=900)
    # 부품끼리는 틈 검사도 한 번 — 같은 평면에서 맞닿는 쌍은 위 교차 계산이 「no result」 로 실패할 수 있다(뒤 하우징 ↔ 끝 덮개 · 2026-10-23 실측).
    # 그 쌍만 이 결과로 가린다: 겹침(0.01 mm³ 이상)이 없고 거리 0 이면 「닿음」.
    mk.cmd("inspect.clearance", bodies=parts, against=parts)
    script = a.out / "build-commands.json"
    script.write_text(json.dumps({"commands": mk.commands}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    native = a.out / "j2-split.solidcraft"
    env_os = dict(os.environ, SOLIDCRAFT_GPU="cpu")
    p = subprocess.run([str(a.cli), "run", str(script), "--save", str(native), "--out", str(a.out / "j2-split.step"), "--results", "--json-out",
                        str(a.evidence / "build-result.json")], capture_output=True, text=True, encoding="utf-8", timeout=3600, env=env_os)
    (a.evidence / "build-stderr.txt").write_text(p.stderr, encoding="utf-8")
    if p.returncode:
        raise SystemExit(f"build rc {p.returncode}: {p.stderr[-1500:]}")
    hide = [f"{x}:opacity=0.0" for x in envelope + child]
    # 단면은 XZ 면으로 자르고 +Y 쪽을 남긴다(flip) — 정면(−Y 에서 봄)에서 잘린 면이 보인다.
    for view, extra in (("iso", []), ("section", ["--section", "XZ,flip"])):
        argv = [str(a.cli), "snapshot", "--in", str(native), "--out", str(a.out / f"{view}.png"), "--view", "iso" if view == "iso" else "front",
                "--width", "1600", "--height", "1200", "--no-axes", *extra]
        for h in hide:
            argv += ["--body", h]
        s = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=900, env=env_os)
        if s.returncode:
            raise SystemExit(f"snapshot {view}: {s.stderr[-800:]}")

    res = json.loads((a.evidence / "build-result.json").read_text(encoding="utf-8"))
    found = [x for r in (res if isinstance(res, list) else res.get("results", [])) for x in (r, r.get("result") if isinstance(r, dict) else None)
             if isinstance(x, dict)]
    inter = next(x for x in found if "interferences" in x)
    clearance = next(x for x in found if "overlaps" in x and "near" in x)
    kind = {**{x: "part" for x in parts}, **{x: "ref" for x in refs}, **{x: "child" for x in child}, **{x: "env" for x in envelope}}
    vol = {}
    e = subprocess.run([str(a.cli), "eval", str(native), "--json-out", str(a.evidence / "eval.json")], capture_output=True, text=True, encoding="utf-8",
                       timeout=900, env=env_os)
    if e.returncode:
        raise SystemExit(f"eval rc {e.returncode}: {e.stderr[-800:]}")
    ev = json.loads((a.evidence / "eval.json").read_text(encoding="utf-8"))
    for bd in ev["bodies"]:
        vol[bd["name"]] = bd["volume_mm3"]
    part_part, part_ref, part_child, contacts, inside = [], [], [], [], {x: 0.0 for x in parts}
    for it in inter["interferences"]:
        ka, kb = kind.get(it["a"]), kind.get(it["b"])
        if "part" not in (ka, kb):
            continue
        v = float(it.get("volume_mm3") or 0)
        thin = min(hi - lo for hi, lo in zip(it["bbox"]["max"], it["bbox"]["min"]))
        if "env" not in (ka, kb) and thin <= CONTACT_MM:
            contacts.append({"a": it["a"], "b": it["b"], "volume_mm3": v, "thinnest_mm": thin})
            continue
        other = kb if ka == "part" else ka
        row = {"a": it["a"], "b": it["b"], "volume_mm3": v}
        if other == "part":
            part_part.append(row)
        elif other == "ref":
            part_ref.append(row)
        elif other == "child":
            part_child.append(row)
        elif other == "env":
            inside[it["a"] if ka == "part" else it["b"]] += v
    outside = {x: round(vol[x] - inside[x], 3) for x in parts}
    # 교차 계산이 실패한 부품끼리의 쌍 — 틈 검사에서 겹침이 있으면 간섭, 거리 0 이면 닿음. 틈 검사도 못 한 쌍(같은 축에 작은 틈으로 낀 원통 —
    # 끝 덮개의 턱 ↔ 캔 안 · 2026-10-23 실측)은 내보낸 부품 STL 끼리의 교차(manifold3d)로 가른다: 교차 부피 ≤ MESH_CONTACT_MM3 이면 닿음.
    unchecked = []
    pair = lambda r: frozenset((r["a"], r["b"]))  # noqa: E731
    over = {pair(r): r for r in clearance.get("overlaps", [])}
    near = {pair(r): r for r in clearance.get("near", [])}
    for u in inter.get("unchecked", []):
        k = pair(u)
        both_parts = kind.get(u["a"]) == kind.get(u["b"]) == "part"
        if both_parts and k in over:
            part_part.append({"a": u["a"], "b": u["b"], "volume_mm3": float(over[k]["volume_mm3"]), "by": "inspect.clearance"})
        elif both_parts and k in near and float(near[k]["distance_mm"]) == 0.0:
            contacts.append({"a": u["a"], "b": u["b"], "by": "inspect.clearance (interference: " + u["reason"] + ")",
                             "shared_volume_mm3": near[k].get("overlap_mm3"), "exact": near[k].get("exact", True)})
        elif both_parts:
            v, box = mesh_intersection(a.out / "parts" / f"{u['a']}.stl", a.out / "parts" / f"{u['b']}.stl")
            row = {"a": u["a"], "b": u["b"], "volume_mm3": v, "bbox": box, "by": "manifold3d on the exported STL (interference: " + u["reason"] + ")"}
            (contacts if v <= MESH_CONTACT_MM3 else part_part).append(row)
        else:
            unchecked.append(u)
    checks = {
        "unchecked_pairs_0": len(unchecked) == 0,
        "part_part_interference_0": not part_part,
        "part_reference_interference_0": not part_ref,
        "part_child_link_interference_0": not part_child,
        "parts_inside_a2_envelope": all(abs(v) <= VOL_TOL_REL * vol[x] for x, v in outside.items()),
    }
    design = {
        "units": "mm",
        "frame": "J2 local: output axis +Z (= Link2 +Y), joint centre at origin, output face z = +D/2 (= +18), +X = Link2 +X, +Y = -(Link2 +Z); "
                 "at the display pose +Z is the v1 J2 world axis [-0.2588, 0.9659, 0]",
        "parts": parts, "references": refs, "child_link_references": child,
        "interfaces": {
            "motor_face": {"z_mm": z_rear, "pilot_dia_mm": m["pilot_dia_mm"], "bolts": f"4 x M3, clearance {m['bolt_clearance_dia_mm']} on a {m['bolt_square_mm']} mm square",
                           "note": "motor face against the rear wall underside; screws from the reducer side into the motor"},
            "reducer_space": {"radius_mm": red_r, "z_from_mm": zb, "z_to_mm": z_lip0, "depth_mm": z_lip0 - zb, "type": "not selected (plan 014 B3)"},
            "reducer_output_to_flange": {"pilot_dia_mm": fl["reducer_pilot_dia_mm"], "pilot_depth_mm": fl["reducer_pilot_depth_mm"],
                                         "inserts": f"{fl['insert_count']} x M3 heat-set at r {fl['insert_radius_mm']} from the flange underside"},
            "child_link_to_flange": {"inserts": f"{fl['insert_count']} x M3 heat-set at r {fl['insert_radius_mm']} from the flange top (offset {180 / fl['insert_count']} deg)",
                                     "flange_top_z_mm": z_f1, "stationary_top_z_mm": z_static, "stationary_gap_mm": z_f1 - z_static},
            "output_bearing_seat": {**b, "z_from_mm": z_seat0, "z_to_mm": z_ret0, "shoulder": f"lip r {lip_r} .. {seat_r}, z {z_lip0} .. {z_seat0}",
                                    "outer_ring_held_by": "J2_BEARING_RETAINER from above"},
            "bearing_retainer": {**bt, "z_from_mm": z_ret0, "z_to_mm": z_static,
                                 "screws": f"{bt['screw_count']} x M3 button head through the retainer into heat-set inserts in the reducer housing"},
            "rear_housing_to_reducer_housing": {"bolts": f"{j['count']} x M3 at r {j['radius_mm']}", "rear": f"clearance {j['clearance_dia_mm']} + counterbore Ø{j['counterbore_dia_mm']} x {j['counterbore_depth_mm']}",
                                                "front": f"heat-set insert hole Ø{j['insert_hole_dia_mm']} x {j['insert_depth_mm']}"},
            "accent_ring": {"radial_clearance_mm": clr, "z_from_mm": z_ring0, "z_to_mm": z_static, "notch_inner_radius_mm": notch_r,
                            "held_by": "the retainer rim (r up to the retainer outer radius) above the ring's lower part"},
            "end_cap": {**cap, "can_bore_radius_mm": bore, "pillar_z_mm": [z_pillar_end, z_rear],
                        "screws": f"{len(cap['screw_angles_deg'])} x M3 button head through the cap into heat-set inserts in the rear-housing pillars"},
        },
        "fit_values_status": "placeholders until the fit coupons (models/fit-coupons-v1) are printed and judged",
        "min_wall_mm": {"can": sp["can_wall_mm"], "rear_wall": wall, "reducer_housing_side": R - red_r, "bearing_seat_side": R - RT - seat_r,
                        "flange_collar": cr - fr, "accent_ring_lower": RT - clr, "accent_ring_upper": R - notch_r, "cap_spigot": cap["spigot_wall_mm"],
                        "retainer_under_counterbore": bt["thickness_mm"] - bt["counterbore_depth_mm"],
                        "cap_under_counterbore": CAP - cap["counterbore_depth_mm"],
                        "joint_insert_to_reducer_space": j["radius_mm"] - j["insert_hole_dia_mm"] / 2 - red_r,
                        "joint_insert_to_outside": R - j["radius_mm"] - j["insert_hole_dia_mm"] / 2,
                        "retainer_insert_to_bearing_seat": bt["screw_radius_mm"] - bt["insert_hole_dia_mm"] / 2 - seat_r,
                        "retainer_insert_to_ring_seat": (R - RT) - bt["screw_radius_mm"] - bt["insert_hole_dia_mm"] / 2,
                        "pillar_around_insert": cap["pillar_dia_mm"] / 2 - cap["insert_hole_dia_mm"] / 2},
        # 볼트 머리 자리파기가 둥글림 · 다른 면에 닿지 않는 틈(모두 양수여야 한다)
        "clearances_mm": {"joint_counterbore_to_rear_fillet": (R - REAR_FILLET) - (j["radius_mm"] + j["counterbore_dia_mm"] / 2),
                          "joint_counterbore_to_can": (j["radius_mm"] - j["counterbore_dia_mm"] / 2) - RC,
                          "cap_counterbore_to_cap_fillet": (RC - 1 - cap["outer_fillet_mm"]) - (pr + cap["counterbore_dia_mm"] / 2),
                          "cap_screw_to_spigot": (sr - cap["spigot_wall_mm"]) - (pr + cap["clearance_dia_mm"] / 2),
                          "retainer_counterbore_to_inner_edge": (bt["screw_radius_mm"] - bt["counterbore_dia_mm"] / 2) - bt["inner_radius_mm"],
                          "retainer_counterbore_to_outer_edge": bt["outer_radius_mm"] - (bt["screw_radius_mm"] + bt["counterbore_dia_mm"] / 2),
                          "retainer_inner_edge_to_flange": bt["inner_radius_mm"] - fr},
        "print_orientation": {"J2_REAR_HOUSING": "rear-wall inner face (z = -12) on the bed, can and pillars upward",
                              "J2_REDUCER_HOUSING": "underside (z = -12) on the bed - the lip underside needs support",
                              "J2_OUTPUT_FLANGE": "underside (collar) on the bed", "J2_BEARING_RETAINER": "flat, counterbores upward",
                              "J2_ACCENT_RING_PART": "flat, notch upward", "J2_END_CAP_PART": "outer face on the bed, spigot upward"},
        "fasteners": {"m3_heat_set_inserts": j["count"] + bt["screw_count"] + 2 * fl["insert_count"] + len(cap["screw_angles_deg"]),
                      "m3_screws": {"motor": 4, "rear_to_reducer_housing": j["count"], "retainer_button_head": bt["screw_count"],
                                    "end_cap_button_head": len(cap["screw_angles_deg"])},
                      "note": "screw lengths are chosen after the fit coupons and the reducer; only inserts are on hand"},
        "checks": checks, "part_part": part_part, "part_reference": part_ref, "part_child_link": part_child,
        "contacts_thinner_than_mm": CONTACT_MM, "contacts": contacts,
        "envelope_scale_for_check": ENV_SCALE, "outside_envelope_mm3": outside, "outside_tolerance_relative": VOL_TOL_REL,
        "unchecked": unchecked, "interference_unchecked_raw": inter.get("unchecked", []),
    }
    (a.out / "split.json").write_text(json.dumps(design, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1))
    print("outside", outside)
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
