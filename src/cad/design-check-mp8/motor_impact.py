# -*- coding: utf-8 -*-
"""MP8 — 모터 실측이 지금 모델에 미치는 영향 표(읽기만 · 결정론).

모터 실측 원장(`src/cad/calibration/motor-mks42d.json`)의 값으로, 지금 모델들이 쓰는 식 그대로 다시 계산한다. 관절 거리(v1 kinematics)는 그대로 둔다.
- 캔 바깥 길이 LC = 3 + 몸체 + 모터→드라이버 간격 + 드라이버 두께 + 뒤 여유(v2geom.py:31 · v3geom.py:49 와 같은 식 — 아래에서 두 Spec 의 LC 와 대조).
- J4 · J6 끝 덮개 바깥면 ↔ 부모 관절(J3 · J5) 드럼: 덮개 바깥면 x = 링크 길이 − 드럼 깊이/2 − LC − 덮개. 드럼(축 ⊥ X · 반지름 R)이 x ≤ R 를 차지한다.
  v2 꼴 = 덮개 면 그대로 · v3 = 덮개의 민트 사선이 이웃 드럼 쪽으로 emboss_mm(0.8) 돋음(v3 parameters marks.cap_slash.joints).
  모따기(드럼 · 덮개)는 재료를 깎을 뿐이라 이 틈을 줄이지 않는다.
- J1: 모터 장착면 z = J1 높이 − 드럼 깊이/2 − 3 · 드라이버 뒷면 z = 장착면 − (몸체 + 간격 + 드라이버) ↔ 발 윗면(v3 foot_h · v2 foot_h · v1 바닥판 두께 중 큰 값) ·
  캔 끝 z(LC) ↔ 바닥 z 0(발에 드라이버 자리를 팔 때의 기준).
- J2 분할(v2 j2-split · split.json 의 접속면): 드라이버 뒷면 = 모터 면 + 몸체 + 간격 + 드라이버. 커넥터 상자(−X · 폭 20)의 모서리는 덮개 턱(반지름
  턱 안 ~ 턱 바깥) 위라 턱 윗면에서 멈추고, 드라이버 모서리가 턱 안지름보다 안이면 덮개 판까지 간다. 기둥 끝(81.5)은 022 mp5-canfit 과 같은 보수 대용.
  지름 방향: 드라이버 반폭 ↔ 기둥 안 반지름 · 드라이버 · 커넥터 · 프레임 모서리 반지름 ↔ 캔 안 반지름. 축 끝 z ↔ 감속기 자리(자리 표시) 윗면.
- MP6 감속기: 모터 나사 끝 ↔ 구멍 바닥(cycloid.py pick 의 하한 0.5) · 축 끝 ↔ 편심 축 D 구멍 위끝 · 편심 축에 든 길이 ·
  필요한 D 평면 길이 = 축 길이 − (파일럿 높이 + 게이지) — MP6 검사 · 참조 축은 전 길이 D 로 놓았다(verify_geometry.py:122-123).
- 프레임 모서리 반지름 = hypot(h, h − c/√2) · h = 한 변/2 · c = 45° 모따기 면의 폭(c = 0 이면 꼭짓점 h√2).
- 손목 27:1 S1 여유는 유지 토크에 비례(질량 · 길이 그대로) → 여유 0 토크 = MP5 S1 토크 ÷ (1 + 여유)(loads-gripper/summary.json · 명목 · 비관).
원장 · 모델 파일은 읽기만 한다(v2geom · v3geom 은 LC 대조에만 가져오며 바이트코드도 쓰지 않음). 산출 = --out 폴더의 motor-impact.json · motor-impact.md.

사용: python motor_impact.py [--ledger <원장>] [--out <폴더>]   (기본 = 저장소의 원장 · .dev/mp8-evidence/)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])
SCENARIO_LENGTHS = (40.0, 48.0, 60.0)   # 022 의 시나리오 S1 · S2 · S3 몸체 길이
SHAFT_SCENARIOS = (23.0, 24.0)          # 판매처 그림 23(RS485 판 · 보스 포함) · 지금 가정 24
SCREW_FLOOR_GAP = 0.5                   # cycloid.py pick(): 나사 끝 ↔ 막힌 구멍 바닥 하한
ADAPTER = 3.0                           # LC 식의 3 — 드럼 뒷면 → 모터 장착면(v2geom.py:31 · v3geom.py:49)
MODEL_GAP = 2.0                         # LC 식의 2 — 모델이 쓰는 모터 → 드라이버 간격(같은 줄 · Spec LC 대조로 확인)
CONNECTOR_BOX_W = 20.0                  # 커넥터 가정 상자의 폭 — build_j2_split.py:210 · v2 validate_product.py:69 · v3 validate_product.py:205 · v1 build_concept.py:133
OVERALL_TOL = 0.5                       # 전체 길이 ↔ 1 + 2 + 3 합의 어긋남 허용(캘리퍼 세 번 잰 합 · 어림)
WRIST_CELL = "사이클로이드 1 단 27:1 | J4 · J5 · S1(17-40)"
LOAD_CASES = (("nominal", "nominal"), ("usable_0.4", "pessimistic"))
UNMEASURED = "미측정"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def impact(m, M):
    """m = {키: 값(None 가능)} · M = 모델 자료. 지금 모델 식으로 영향 값을 낸다(mm · N·m)."""
    v1 = M["v1"]
    D = float(v1["reducer_depth_mm"])
    RD = [d / 2 for d in v1["reducer_diameters_mm"]]
    stack = m["body_length"] + m["motor_driver_gap"] + m["driver_depth"]          # 장착면 → 드라이버 뒤 덮개 바깥면
    r = {"stack_mount_to_driver_rear": stack}
    # ---- J4 · J6 덮개 ↔ 부모 드럼(v2 꼴 · v3) ----
    for tag in ("v2", "v3"):
        e = M["ext"][tag]
        lc = ADAPTER + stack + float(e["can_rear_clearance_mm"])
        cap = float(e["end_cap_thickness_mm"])
        r[f"LC_{tag}"] = lc
        for j, off, rd in ((4, float(v1["forearm_mm"]), RD[2]), (6, float(v1["wrist_offsets_mm"][1]), RD[4])):
            face = off - D / 2 - lc - cap
            emb = M["emboss"][tag].get(j, 0.0)
            r[f"J{j}_cap_face_x_{tag}"] = face
            r[f"J{j}_cap_emboss_{tag}"] = emb
            r[f"J{j}_gap_to_J{j - 1}_drum_{tag}"] = face - emb - rd
    r["J3_drum_radius"], r["J5_drum_radius"] = RD[2], RD[4]
    # ---- J1 ----
    j1_face = float(v1["joint1_height_mm"]) - D / 2 - ADAPTER
    r["J1_mount_face_z"] = j1_face
    r["J1_driver_rear_z"] = j1_face - stack
    r["J1_foot_top_z"] = M["foot_top"]
    r["J1_driver_gap_to_foot_top"] = r["J1_driver_rear_z"] - M["foot_top"]
    r["J1_can_end_z"] = float(v1["joint1_height_mm"]) - D / 2 - r["LC_v3"]      # J1 은 덮개 없음(캔이 기둥 안에 숨음)
    # ---- J2 분할(관절 중심에서 뒤쪽으로 잰 크기) ----
    sp = M["split"]["interfaces"]
    ec = sp["end_cap"]
    face = abs(float(sp["motor_face"]["z_mm"]))
    pillar_tip = abs(float(ec["pillar_z_mm"][0]))
    cap_plate = pillar_tip + float(ec["pillar_gap_to_spigot_mm"]) + float(ec["spigot_height_mm"])
    spigot_top = cap_plate - float(ec["spigot_height_mm"])
    bore = float(ec["can_bore_radius_mm"])
    spig_out = bore - float(ec["spigot_radial_clearance_mm"])
    spig_in = spig_out - float(ec["spigot_wall_mm"])
    pillar_in = float(ec["screw_radius_mm"]) - float(ec["pillar_dia_mm"]) / 2
    half = m["driver_width"] / 2
    drv_corner = half * math.sqrt(2)
    con_corner = math.hypot(half + m["connector_clearance"], CONNECTOR_BOX_W / 2)
    drv_stop = spigot_top if drv_corner > spig_in else cap_plate
    con_stop = spigot_top if con_corner > spig_in else cap_plate
    rear = face + stack
    r.update({
        "J2split_motor_face": face, "J2split_driver_rear": rear,
        "J2split_pillar_tip": pillar_tip, "J2split_gap_to_pillar_tip": pillar_tip - rear, "J2split_pillar_overrun": max(0.0, rear - pillar_tip),
        "J2split_spigot_top": spigot_top, "J2split_cap_plate": cap_plate,
        "J2split_spigot_inner_radius": spig_in, "J2split_spigot_outer_radius": spig_out,
        "J2split_connector_stop": con_stop, "J2split_connector_gap": con_stop - rear,
        "J2split_driver_stop": drv_stop, "J2split_driver_gap": drv_stop - rear,
        "J2split_pillar_inner_radius": pillar_in, "J2split_driver_half_width": half, "J2split_driver_gap_to_pillar": pillar_in - half,
        "J2split_can_bore_radius": bore,
        "J2split_driver_corner_radius": drv_corner, "J2split_driver_corner_gap_to_bore": bore - drv_corner,
        "J2split_connector_corner_radius": con_corner, "J2split_connector_corner_gap_to_bore": bore - con_corner,
    })
    # ---- 프레임 모서리 ----
    h = m["frame"] / 2
    c = m.get("frame_corner_chamfer") or 0.0
    r["frame_corner_radius"] = math.hypot(h, h - c / math.sqrt(2))
    r["frame_corner_gap_to_bore"] = bore - r["frame_corner_radius"]
    # ---- 축(MP6 · J2 분할) ----
    L = m["shaft_length"]
    st = M["mp6"]["stack_mm"]
    z_d = m["pilot_height"] + M["gauge"]
    cam_top, upper0 = float(st["cam_bore"][1]), float(st["cam_upper"][0])
    r.update({
        "MP6_d_bore_start_z": z_d, "MP6_cam_bore_top_z": cam_top,
        "MP6_shaft_tip_below_cam_bore_top": cam_top - L,
        "MP6_shaft_in_cam": min(L, cam_top) - z_d, "MP6_shaft_in_upper_cam": max(0.0, min(L, cam_top) - upper0),
        "MP6_d_flat_needed": L - z_d, "MP6_d_flat_ledger": m.get("shaft_flat_length"),
    })
    tip = -face + L
    top = float(sp["reducer_space"]["z_to_mm"])
    r.update({"J2split_shaft_tip_z": tip, "J2split_reducer_space_top_z": top, "J2split_shaft_overrun": max(0.0, tip - top)})
    # ---- MP6 모터 나사 ----
    eng = float(M["mp6"]["screws"]["motor"]["engagement_mm"])
    r["MP6_motor_screw_engagement"] = eng
    r["MP6_screw_tip_to_floor"] = m["screw_thread_depth"] - eng
    # ---- 유지 토크 ↔ 손목 27:1 S1 여유 ----
    t_ref = M["t_ref"]
    T = m.get("label_holding_torque")
    for case, tag in LOAD_CASES:
        mg = M["margins"][case]
        r[f"wrist27_S1_margin_{tag}"] = mg
        r[f"wrist27_S1_zero_margin_torque_{tag}"] = t_ref / (1 + mg)
        r[f"wrist27_S1_margin_at_ledger_torque_{tag}"] = None if T is None else (1 + mg) * T / t_ref - 1
    ov = m.get("overall_length")
    r["overall_length_minus_sum"] = None if ov is None else ov - stack
    return r


def verdicts(r):
    flat = r["MP6_d_flat_ledger"]
    ov = r["overall_length_minus_sum"]
    v = {
        "J4_clear_of_J3_drum_v3": r["J4_gap_to_J3_drum_v3"] > 0, "J4_clear_of_J3_drum_v2": r["J4_gap_to_J3_drum_v2"] > 0,
        "J6_clear_of_J5_drum_v3": r["J6_gap_to_J5_drum_v3"] > 0, "J6_clear_of_J5_drum_v2": r["J6_gap_to_J5_drum_v2"] > 0,
        "J1_driver_above_foot_top": r["J1_driver_gap_to_foot_top"] > 0,
        "J1_can_above_floor": r["J1_can_end_z"] > 0,
        "J2split_within_pillar_tip": r["J2split_gap_to_pillar_tip"] >= 0,
        "J2split_connector_axial": r["J2split_connector_gap"] >= 0,
        "J2split_driver_axial": r["J2split_driver_gap"] >= 0,
        "J2split_driver_clear_of_pillars": r["J2split_driver_gap_to_pillar"] > 0,
        "J2split_driver_corner_in_bore": r["J2split_driver_corner_gap_to_bore"] >= 0,
        "J2split_connector_corner_in_bore": r["J2split_connector_corner_gap_to_bore"] >= 0,
        "frame_fits_can": r["frame_corner_gap_to_bore"] >= 0,
        "MP6_motor_screw_ok": r["MP6_screw_tip_to_floor"] >= SCREW_FLOOR_GAP - 1e-9,
        "MP6_shaft_below_cam_bore_top": r["MP6_shaft_tip_below_cam_bore_top"] > 0,
        "MP6_d_flat_needed": UNMEASURED if flat is None else flat >= r["MP6_d_flat_needed"] - 1e-9,
        "J2split_shaft_within_placeholder_reducer_space": r["J2split_shaft_overrun"] == 0,
        "overall_length_matches_sum": UNMEASURED if ov is None else abs(ov) <= OVERALL_TOL,
    }
    for _case, tag in LOAD_CASES:
        mt = r[f"wrist27_S1_margin_at_ledger_torque_{tag}"]
        v[f"wrist27_S1_margin_positive_{tag}"] = UNMEASURED if mt is None else mt > 0
    return v


LIMIT_NOTE = {
    "J4_vs_J3_drum_v3": "v3 외장 — J4 끝 덮개 민트 사선 0.8 돋움 포함",
    "J4_vs_J3_drum_v2": "v2 꼴(돋움 없음)",
    "J6_vs_J5_drum_v3": "v3 외장 — J6 끝 덮개 민트 사선 0.8 돋움 포함",
    "J6_vs_J5_drum_v2": "v2 꼴(돋움 없음)",
    "J1_driver_vs_foot_top": "J1 드라이버 ↔ 발 윗면 12 — 발을 파지 않으면(v1 바닥판도 통 12)",
    "J1_can_vs_floor": "발에 드라이버 자리를 파면 — 바닥(z 0) 기준(캔 끝)",
    "J2split_pillar_tip": "J2 분할 덮개 기둥 끝 81.5 — 보수 대용 · J2 분할을 새 LC 로 다시 그리면 풀림",
    "J2split_connector_vs_spigot_top": "J2 분할 커넥터 → 덮개 턱 윗면 82 — 다시 그리면 풀림",
    "J2split_driver_vs_cap_plate": "J2 분할 드라이버 → 덮개 판 85(모서리가 턱 안지름 안일 때) — 다시 그리면 풀림",
}


def limits(m, now):
    """관절 거리를 그대로 둘 때 몸체 길이의 상한(나머지 = 원장) — 각 틈이 0 이 되는 길이 · 전체 길이 상한 = 몸체 상한 + 간격 + 드라이버."""
    B = m["body_length"]
    body = {
        "J4_vs_J3_drum_v3": B + now["J4_gap_to_J3_drum_v3"], "J4_vs_J3_drum_v2": B + now["J4_gap_to_J3_drum_v2"],
        "J6_vs_J5_drum_v3": B + now["J6_gap_to_J5_drum_v3"], "J6_vs_J5_drum_v2": B + now["J6_gap_to_J5_drum_v2"],
        "J1_driver_vs_foot_top": B + now["J1_driver_gap_to_foot_top"], "J1_can_vs_floor": B + now["J1_can_end_z"],
        "J2split_pillar_tip": B + now["J2split_gap_to_pillar_tip"],
        "J2split_connector_vs_spigot_top": B + now["J2split_connector_gap"], "J2split_driver_vs_cap_plate": B + now["J2split_driver_gap"],
    }
    extra = m["motor_driver_gap"] + m["driver_depth"]
    overall = {k: v + extra for k, v in body.items()}
    bore, spig_in, half = now["J2split_can_bore_radius"], now["J2split_spigot_inner_radius"], now["J2split_driver_half_width"]
    other = {
        "shaft_length_MP6_below_cam_bore_top_lt": now["MP6_cam_bore_top_z"],
        "shaft_length_J2split_placeholder_reducer_space": now["J2split_motor_face"] + now["J2split_reducer_space_top_z"],
        "shaft_flat_length_MP6_min": now["MP6_d_flat_needed"],
        "screw_thread_depth_MP6_min": now["MP6_motor_screw_engagement"] + SCREW_FLOOR_GAP,
        "connector_clearance_J2split_bore_max": math.sqrt(bore ** 2 - (CONNECTOR_BOX_W / 2) ** 2) - half,
        "driver_width_J2split_pillars_max": 2 * now["J2split_pillar_inner_radius"],
        "driver_width_J2split_bore_max": 2 * bore / math.sqrt(2),
        "driver_width_J2split_spigot_axial_stop_shift": 2 * spig_in / math.sqrt(2),
        "frame_J2split_bore_max_no_chamfer": 2 * bore / math.sqrt(2),
    }
    for _case, tag in LOAD_CASES:
        other[f"holding_torque_wrist27_S1_zero_margin_{tag}"] = now[f"wrist27_S1_zero_margin_torque_{tag}"]
    return body, overall, other


def canfit_block(text):
    """022 의 mp5-canfit 블록 표 → {모터: (드라이버 뒤끝, 덮개 안쪽 면을 넘는 길이)}."""
    blk = text.split("<!-- mp5-canfit:begin -->", 1)[1].split("<!-- mp5-canfit:end -->", 1)[0]
    rows = {}
    for line in blk.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("NEMA"):
            rows[cells[0]] = (float(cells[1]), float(cells[2]))
    return rows


def model_spec_lc(folder, modname, params, v1_dir):
    """모델 생성기의 Spec 을 그대로 불러 LC 를 받는다(바이트코드를 쓰지 않음 · 경로는 끝나면 되돌림)."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(folder))
    try:
        mod = importlib.import_module(modname)
    finally:
        sys.path.remove(str(folder))
    return float(mod.Spec(params, v1_dir).LC)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=ROOT / "src" / "cad" / "calibration" / "motor-mks42d.json")
    ap.add_argument("--out", type=Path, default=ROOT / ".dev" / "mp8-evidence")
    a = ap.parse_args()
    v1_dir = ROOT / "models" / "armold-mks-concept-v1"
    v2_dir, v3_dir = ROOT / "src" / "cad" / "armold-mks-product-v2", ROOT / "src" / "cad" / "armold-mks-product-v3"
    files = {
        "ledger": a.ledger,
        "v1_parameters": v1_dir / "parameters.json",
        "v2_parameters": v2_dir / "parameters.json",
        "v3_parameters": v3_dir / "parameters.json",
        "j2_split": ROOT / "models" / "armold-mks-product-v2" / "j2-split" / "split.json",
        "mp6_cycloid": ROOT / "models" / "cycloid-27-v1" / "cycloid.json",
        "mp5_inputs": ROOT / "src" / "cad" / "review-mp5" / "inputs.json",
        "loads_gripper_summary": ROOT / ".dev" / "mp8-evidence" / "loads-gripper" / "summary.json",
    }
    code = {
        "v2geom": v2_dir / "v2geom.py",
        "v3geom": v3_dir / "v3geom.py",
        "build_j2_split": v2_dir / "build_j2_split.py",
        "doc_022": ROOT / "docs" / "design" / "022-modeling-reducer-review.md",
    }
    data = {k: json.loads(Path(p).read_text(encoding="utf-8")) for k, p in files.items()}
    v1, p2, p3, mp6 = data["v1_parameters"], data["v2_parameters"], data["v3_parameters"], data["mp6_cycloid"]
    marks = p3["marks"]
    M = {
        "v1": v1, "split": data["j2_split"], "mp6": mp6,
        "ext": {"v2": p2["exterior"], "v3": p3["exterior"]},
        "emboss": {"v2": {}, "v3": {j: float(marks["emboss_mm"]) for j in (4, 6) if j in marks["cap_slash"]["joints"]}},
        "foot_top": max(float(p3["links"]["base"]["foot_h"]), float(p2["links"]["base"]["foot_h"]), float(v1["base_thickness_mm"])),
        "gauge": float(mp6["assembly_datum"]["lower_cam_hub_above_pilot_mm"]),
        "t_ref": float(data["mp5_inputs"]["motors"]["NEMA17-40"]["holding_Nm"]),
        # 손목 여유 = 그리퍼 짐 요약의 기본 쥐는 점(트레이 집기 최악 — default_grasp_z_mm) 경우 · 부호 있는 여유(모자라면 음수)
        "margins": {case: float(data["loads_gripper_summary"]["cases"][f"{data['loads_gripper_summary']['default_grasp_z_mm']:g}"]["cells"][case][WRIST_CELL]
                                ["margin_pct_at_payload"]) / 100 for case, _t in LOAD_CASES},
        "grasp_z_mm": data["loads_gripper_summary"]["default_grasp_z_mm"],
    }
    led = data["ledger"]["items"]
    m = {k: led[k]["value"] for k in led}
    for need in ("body_length", "motor_driver_gap", "driver_depth", "driver_width", "connector_clearance", "frame", "pilot_height",
                 "screw_thread_depth", "shaft_length"):
        if not isinstance(m.get(need), (int, float)) or isinstance(m.get(need), bool):
            raise SystemExit(f"원장에 숫자 값이 없음: {need}")
    status = {k: led[k]["status"] for k in led}

    # ---- 대조: 이 식이 모델 파일의 식과 같은가(원장이 아니라 모델이 쓰는 값으로) ----
    model = dict(m, body_length=float(v1["motor_length_mm"]), motor_driver_gap=MODEL_GAP, driver_depth=float(v1["driver_depth_mm"]),
                 driver_width=float(v1["driver_width_mm"]), connector_clearance=float(v1["connector_clearance_mm"]))
    base = impact(model, M)
    lc2 = model_spec_lc(v2_dir, "v2geom", v2_dir / "parameters.json", v1_dir)
    lc3 = model_spec_lc(v3_dir, "v3geom", v3_dir / "parameters.json", v1_dir)
    assert abs(base["LC_v2"] - lc2) < 1e-9 and abs(base["LC_v3"] - lc3) < 1e-9, (base["LC_v2"], lc2, base["LC_v3"], lc3)
    cf = canfit_block(Path(code["doc_022"]).read_text(encoding="utf-8"))
    for L, name in ((40.0, "NEMA17-40"), (48.0, "NEMA17-48"), (60.0, "NEMA17-60")):
        r = impact(dict(model, body_length=L), M)
        assert (round(r["J2split_driver_rear"], 1), round(r["J2split_pillar_overrun"], 1)) == cf[name], (name, r["J2split_driver_rear"], r["J2split_pillar_overrun"], cf[name])
    st = mp6["stack_mm"]
    assert abs(float(st["motor_pilot_top"]) + M["gauge"] - float(st["cam_bore"][0])) < 1e-9, "MP6 D 구멍 시작 ≠ 파일럿 + 게이지"
    assert abs(float(mp6["gaps"]["motor_shaft_tip_below_cam_bore_top"]["mm"]) - (float(st["cam_bore"][1]) - float(st["motor_shaft"][1]))) < 1e-9

    now = impact(m, M)
    rows = {f"{L:g}": {"values": (r := impact(dict(m, body_length=L), M)), "verdicts": verdicts(r)} for L in SCENARIO_LENGTHS}
    shaft_rows = {f"{L:g}": {"values": (r := impact(dict(m, shaft_length=L), M)), "verdicts": verdicts(r)} for L in SHAFT_SCENARIOS}
    body_lim, overall_lim, other_lim = limits(m, now)
    binding = min(body_lim, key=body_lim.get)
    cond = f"드라이버 {m['driver_depth']:g} · 간격 {m['motor_driver_gap']:g} 가정 아래 — 실측한 1 · 2 · 3 을 원장에 넣고 영향 표를 다시 냄"
    out = {
        "what": "모터 실측 원장 → 지금 모델 식의 영향(관절 거리 그대로 둘 때). 읽기만 · 결정론.",
        "inputs_sha256": {**{k: sha(p) for k, p in files.items()}, **{k: sha(p) for k, p in code.items()}},
        "inputs_path": {k: str(Path(p).resolve().relative_to(ROOT)) if Path(p).resolve().is_relative_to(ROOT) else str(p)
                        for k, p in {**files, **code}.items()},
        "asserts": {"LC_equals_v2geom_Spec": lc2, "LC_equals_v3geom_Spec": lc3, "J2split_overrun_equals_022_mp5_canfit": {k: list(v) for k, v in cf.items()},
                    "MP6_d_bore_start_equals_pilot_plus_gauge": float(st["cam_bore"][0])},
        "ledger_status": status,
        "now": {"values": now, "verdicts": verdicts(now)},
        "scenarios_body_length": rows,
        "scenarios_shaft_length": shaft_rows,
        "body_length_limits_mm": body_lim,
        "body_length_limits_condition": cond,
        "body_length_limit_notes": LIMIT_NOTE,
        "body_length_limit_binding": binding,
        "overall_length_limits_mm": overall_lim,
        "other_limits": other_lim,
        "notes": [
            "틈은 축 방향 위치만 본다(캔 · 덮개를 원통으로). v3 는 J4 · J6 끝 덮개의 민트 사선이 이웃 드럼 쪽으로 0.8 돋아 그만큼 틈이 줄어든다 — 모따기(드럼 · 덮개)는 재료를 깎을 뿐 틈을 줄이지 않는다.",
            "J4 ↔ J3 드럼 · J6 ↔ J5 드럼은 서로 도는 링크라 겹치면 어느 자세에서도 부딪힌다(덮개 면은 드럼 축에서 늘 같은 거리).",
            "J3 · J5 캔은 제 관절 축과 같은 축의 원통(반지름 39 ≤ 드럼 반지름 45 · 39)이고, 자식 링크는 그 축에서 J4 · J6 덮개 바깥면 거리(드럼 틈 + 드럼 반지름) 밖에 있다 → 몸체가 길어져 캔이 제 축 방향(자식 링크 반대쪽)으로 늘어도 어느 자세에서든 안 닿는다. 팔을 접을 때 링크끼리 닿는 각(접힘 범위)이 줄어드는지는 이 표 밖.",
            "J1 캔은 베이스 기둥 안(같은 링크)이라 상대 운동은 없다 — 드라이버 뒷면이 발 윗면 12(v1 바닥판도 통 12) 밑으로 가면 발에 드라이버 자리를 파야 하고, 파면 기준은 바닥(z 0 · 캔 끝).",
            "J2 분할: 커넥터 상자(−X · 폭 20 — 모델에 박힌 값) 모서리는 덮개 턱(반지름 34.85 ~ 36.85) 위라 턱 윗면 82 에서 멈추고, 드라이버 모서리(32.5)는 턱 안을 지나 덮개 판 85 까지 간다. 덮개 기둥(0 · 90 · 270° · 끝 81.5)은 드라이버 옆면에서 4.5 떨어져 축 방향으로 막지 않는다 — 81.5 는 022 mp5-canfit 과 같은 보수 대용. J2 분할은 새 LC 로 다시 그리면 풀린다(관절 거리와 무관).",
            "J2 분할 감속기 자리(z −12 ~ 0.3)는 감속기를 고르기 전 자리 표시 — 축이 18.3 보다 길면 넘는다(지금 가정 24 · 공표 23 모두 넘음). 감속기를 고를 때 실측 축 길이로 다시 본다.",
            "MP6: 아래 편심 축 D 구멍은 z = 파일럿 높이 + 게이지 0.6 에서 시작하고 MP6 검사 · 참조 축은 전 길이 D 다(verify_geometry.py:122-123 · build_cycloid.py:253-257) → 실물 D 평면이 축 끝에서 (축 길이 − 2.6)보다 짧으면 아래 편심 축이 끝까지 안 들어간다. 원장 shaft_flat_length 가 null 이면 판정 = 미측정.",
            f"몸체 길이 상한 = {cond}. 뒤 여유 · 덮개 · 드라이버 폭 · 커넥터도 원장 · 모델 그대로. 전체 길이 상한(몸체 + 간격 + 드라이버)은 간격 · 두께의 나눔과 무관.",
            "손목 27:1 S1 여유는 유지 토크에 비례(질량 · 길이 그대로) — 여유 0 토크 = MP5 S1 0.40 ÷ (1 + 여유). 여유는 loads-gripper/summary.json 의 % (소수 첫째 자리) · 비관 = 쓸 수 있는 토크 비율 0.4.",
        ],
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "motor-impact.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))

    def f(x):
        return "—" if x is None else f"{x:+.1f}"

    def yn(x):
        return x if isinstance(x, str) else ("통과" if x else "걸림")
    md = ["# 모터 실측 영향 표 (MP8 · 자동 생성 — 손으로 고치지 않음)", "",
          "원장 상태: " + " · ".join(f"{k} {v}" for k, v in status.items()), "",
          f"조건: {cond}. 틈 = 양수면 떨어짐 · 음수면 겹침(mm).", "",
          "## 몸체 길이 (나머지 = 원장)", "",
          "| 몸체 길이 | LC | J4 덮개 ↔ J3 드럼 v3 / v2 | J6 덮개 ↔ J5 드럼 v3 / v2 | J1 드라이버 ↔ 발 윗면 | J1 캔 끝 z | J2 분할 커넥터 ↔ 턱 윗면 | J2 분할 드라이버 ↔ 덮개 판 | J2 분할 기둥 끝(보수) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for L, v in [("원장 " + f"{m['body_length']:g}", now)] + [(k, x["values"]) for k, x in rows.items()]:
        md.append(f"| {L} | {v['LC_v3']:.1f} | {f(v['J4_gap_to_J3_drum_v3'])} / {f(v['J4_gap_to_J3_drum_v2'])} | "
                  f"{f(v['J6_gap_to_J5_drum_v3'])} / {f(v['J6_gap_to_J5_drum_v2'])} | {f(v['J1_driver_gap_to_foot_top'])} | {v['J1_can_end_z']:.1f} | "
                  f"{f(v['J2split_connector_gap'])} | {f(v['J2split_driver_gap'])} | {f(v['J2split_gap_to_pillar_tip'])} |")
    md += ["", "## 몸체 길이 상한 (관절 거리 그대로 · 낮은 순)", "", "| 제약 | 몸체 상한 | 전체 길이 상한 | 조건 |", "|---|---|---|---|"]
    for k in sorted(body_lim, key=body_lim.get):
        md.append(f"| {k} | {body_lim[k]:.1f} | {overall_lim[k]:.1f} | {LIMIT_NOTE[k]} |")
    md += ["", f"가장 먼저 걸리는 것 = {binding}({body_lim[binding]:.1f}) — 몸체 상한은 {cond} · 전체 길이 상한은 그 나눔과 무관.", "",
           "## 축 길이 (나머지 = 원장)", "",
           f"| 축 길이 | MP6 축 끝 ↔ D 구멍 위끝 {now['MP6_cam_bore_top_z']:.2f}(양수여야) | MP6 편심 축에 든 길이(전체 / 위 편심 축) | "
           f"MP6 필요한 D 평면 길이(축 끝에서) | J2 분할 축 끝 z(감속기 자리 윗면 {now['J2split_reducer_space_top_z']:.1f} · 자리 표시) |",
           "|---|---|---|---|---|"]
    for L, v in [("원장 " + f"{m['shaft_length']:g}", now)] + [(k, x["values"]) for k, x in shaft_rows.items()]:
        md.append(f"| {L} | {v['MP6_shaft_tip_below_cam_bore_top']:+.2f} | {v['MP6_shaft_in_cam']:.2f} / {v['MP6_shaft_in_upper_cam']:.2f} | "
                  f"{v['MP6_d_flat_needed']:.2f} | {v['J2split_shaft_tip_z']:+.1f}(넘침 {v['J2split_shaft_overrun']:.1f}) |")
    vn = verdicts(now)
    flat = now["MP6_d_flat_ledger"]
    md += ["", f"D 평면 길이(원장 shaft_flat_length) = {'null' if flat is None else f'{flat:g}'} → MP6_d_flat_needed 판정 {yn(vn['MP6_d_flat_needed'])}"
           f"(필요 ≥ {now['MP6_d_flat_needed']:.1f} = 축 길이 − {now['MP6_d_bore_start_z']:.1f}).", "",
           "## 지름 방향 · 기타 (원장 값)", "", "| 항목 | 값 | 판정 | 상한 · 하한 |", "|---|---|---|---|",
           f"| J2 분할 드라이버 반폭 ↔ 기둥 안 반지름 {now['J2split_pillar_inner_radius']:.1f} | 틈 {now['J2split_driver_gap_to_pillar']:.2f} | "
           f"{yn(vn['J2split_driver_clear_of_pillars'])} | 드라이버 폭 ≤ {other_lim['driver_width_J2split_pillars_max']:.1f} |",
           f"| J2 분할 드라이버 모서리 반지름 {now['J2split_driver_corner_radius']:.2f} ↔ 캔 안 반지름 {now['J2split_can_bore_radius']:.0f} | "
           f"틈 {now['J2split_driver_corner_gap_to_bore']:.2f} | {yn(vn['J2split_driver_corner_in_bore'])} | 드라이버 폭 ≤ {other_lim['driver_width_J2split_bore_max']:.2f} |",
           f"| J2 분할 드라이버 모서리 ↔ 덮개 턱 안 반지름 {now['J2split_spigot_inner_radius']:.2f} | 멈춤 {now['J2split_driver_stop']:.1f} | 참고 | "
           f"드라이버 폭 > {other_lim['driver_width_J2split_spigot_axial_stop_shift']:.2f} 이면 멈춤 85 → 82 |",
           f"| J2 분할 커넥터 상자 모서리 반지름 {now['J2split_connector_corner_radius']:.2f} ↔ 캔 안 반지름 {now['J2split_can_bore_radius']:.0f} | "
           f"틈 {now['J2split_connector_corner_gap_to_bore']:.2f} | {yn(vn['J2split_connector_corner_in_bore'])} | 커넥터 길이 ≤ {other_lim['connector_clearance_J2split_bore_max']:.2f} |",
           f"| 프레임 모서리 반지름(모따기 {m.get('frame_corner_chamfer') or 0:g}) {now['frame_corner_radius']:.2f} ↔ 캔 안 반지름 | "
           f"틈 {now['frame_corner_gap_to_bore']:.2f} | {yn(vn['frame_fits_can'])} | 한 변 ≤ {other_lim['frame_J2split_bore_max_no_chamfer']:.1f}(모따기 0) |",
           f"| MP6 모터 나사 끝 ↔ 구멍 바닥(물림 {now['MP6_motor_screw_engagement']:g}) | {now['MP6_screw_tip_to_floor']:.1f} | {yn(vn['MP6_motor_screw_ok'])} | "
           f"나사 깊이 ≥ {other_lim['screw_thread_depth_MP6_min']:.1f} |",
           f"| 손목 27:1 S1 여유(원장 유지 토크 {m.get('label_holding_torque')}) 명목 / 비관 | "
           f"{now['wrist27_S1_margin_at_ledger_torque_nominal'] * 100:.1f} % / {now['wrist27_S1_margin_at_ledger_torque_pessimistic'] * 100:.1f} % | "
           f"{yn(vn['wrist27_S1_margin_positive_nominal'])} / {yn(vn['wrist27_S1_margin_positive_pessimistic'])} | "
           f"유지 토크 ≥ {now['wrist27_S1_zero_margin_torque_nominal']:.3f} / {now['wrist27_S1_zero_margin_torque_pessimistic']:.3f} N·m |"
           if m.get("label_holding_torque") is not None else
           f"| 손목 27:1 S1 여유 0 토크 명목 / 비관 | — | 미측정 | 유지 토크 ≥ {now['wrist27_S1_zero_margin_torque_nominal']:.3f} / "
           f"{now['wrist27_S1_zero_margin_torque_pessimistic']:.3f} N·m |",
           f"| 전체 길이 − (몸체 + 간격 + 드라이버) | {f(now['overall_length_minus_sum'])} | {yn(vn['overall_length_matches_sum'])} | 어긋남 ≤ {OVERALL_TOL:g} |",
           "", "## 메모", ""] + [f"- {n}" for n in out["notes"]]
    (a.out / "motor-impact.md").write_bytes(("\n".join(md) + "\n").encode("utf-8"))
    print(json.dumps({"now": vn, "body_limits": {k: round(v, 3) for k, v in body_lim.items()}, "binding": binding,
                      "other_limits": {k: round(v, 3) for k, v in other_lim.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
