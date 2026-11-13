# -*- coding: utf-8 -*-
"""MP17 팔 전체 v1 — 좌표틀 · 순기구학 · 부품 목록(생성기 · 검사기 · 출력 준비가 함께 쓴다).

좌표 = parameters.json frame(로봇 바닥 좌표 · q = 0 에서 모든 링크 좌표가 세계와 나란함). 부품 STL 은 저마다의 지역 좌표(FRAMES)로 저장하고,
조립 자리 = 링크 k 의 변환 T_k(q) · T_k(0)^-1 · FRAMES[틀]. 관절 원점 · 축 · 거리는 v1 parameters.json 에서 읽는다(kinematics.json 은 검사가 대조만).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = "manipulator-v1"
MODEL = ROOT / "models" / NAME
EV = ROOT / ".dev" / "mp17-evidence"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(params_path=HERE / "parameters.json"):
    p = Path(params_path)
    P = json.loads(p.read_text(encoding="utf-8"))
    src = P["sources"]

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    clash = sorted(set(src["fit_keys"]) & set(keys({k: v for k, v in P.items() if k != "sources"})))
    if clash:
        raise SystemExit(f"fit keys written in {p.name}: {clash} - they live only in the fits ledger")
    base = p.parent
    S = {k: (base / v).resolve() for k, v in src.items() if isinstance(v, str) and ("/" in v or "\\" in v or v.endswith(".json"))}
    mat = json.loads(S["fits_ledger"].read_text(encoding="utf-8"))["materials"][src["material"]]
    fit = {**{k: v for k, v in mat.get("pending", {}).items() if isinstance(v, dict)}, **mat["values"]}          # 확정(values) 우선 · 없으면 보류(pending)
    P["_fits"] = {k: float(fit[k]["value"]) for k in src["fit_keys"]}
    P["_fit_status"] = {k: fit[k]["status"] + ("" if k in mat["values"] else " (pending)") for k in src["fit_keys"]}
    P["_v1"] = json.loads((S["v1_dir"] / "parameters.json").read_text(encoding="utf-8"))
    P["_drive"] = json.loads(S["drive_params"].read_text(encoding="utf-8"))
    P["_paths"] = {k: str(v) for k, v in S.items()}
    return P


# ---------------- 변환 ----------------
def T(R=None, t=(0.0, 0.0, 0.0)):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = np.asarray(R, dtype=float)
    M[:3, 3] = np.asarray(t, dtype=float)
    return M


def cols(c1, c2, c3, t):
    """지역 축 x · y · z 가 세계에서 가리키는 방향(열) + 원점."""
    return T(np.array([c1, c2, c3], dtype=float).T, t)


def rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        R = [[1, 0, 0], [0, c, -s], [0, s, c]]
    elif axis == "y":
        R = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    else:
        R = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    return T(R)


def motor_face_x(P, joint):
    """J4 · J6 손목형 감속기(MP6)의 모터 앞면 x(세계 q = 0) = 관절 원점 + 18(출력 면) − 43.5(MP6 쌓임)."""
    w = P["wrist"]
    return float(joint_origins_q0(P)[joint][0] + w["output_face_from_joint"] - w["mp6_output_face"])


def frames(P):
    """지역 좌표 → 세계(q = 0)."""
    j1z = P["j1"]["motor_face_z"]
    y2, y3 = P["j2"]["module_axis_y0"], P["j3"]["module_axis_y0"]
    x4, x6 = motor_face_x(P, "J4"), motor_face_x(P, "J6")
    o = joint_origins_q0(P)
    zj = o["J2"][2]
    tf = P["tool_flange"]
    return {
        "W": T(),
        "J1": T(t=(0.0, 0.0, j1z)),
        "M2": cols((-1, 0, 0), (0, 0, 1), (0, 1, 0), (0.0, y2, zj)),
        "M3": cols((0, 0, 1), (-1, 0, 0), (0, -1, 0), (o["J3"][0], y3, zj)),
        "C4": cols((0, -1, 0), (0, 0, -1), (1, 0, 0), (x4, 0.0, zj)) @ rot("z", float(P["j4"].get("can_turn_deg", 0.0))),
        "J5M": cols((1, 0, 0), (0, 0, -1), (0, 1, 0), (o["J5"][0], -21.0, zj)),
        "C6": cols((0, -1, 0), (0, 0, -1), (1, 0, 0), (x6, 0.0, zj)),
        "G": cols((0, 1, 0), (0, 0, 1), (1, 0, 0), (x6 + P["wrist"]["mp6_output_face"] + tf["t"], 0.0, zj)),
    }


AXES = {"J1": "z", "J2": "y", "J3": "y", "J4": "x", "J5": "y", "J6": "x"}


def offsets(P):
    """관절 사이 거리(링크 좌표) = v1 parameters + kinematics_override(아래팔만)."""
    v = P["_v1"]
    fo = float(P.get("kinematics_override", {}).get("forearm_mm", v["forearm_mm"]))
    return {"J1": (0.0, 0.0, float(v["joint1_height_mm"])), "J2": (0.0, 0.0, float(v["shoulder_rise_mm"])),
            "J3": (float(v["upper_arm_mm"]), 0.0, 0.0), "J4": (fo, 0.0, 0.0),
            "J5": (float(v["wrist_offsets_mm"][0]), 0.0, 0.0), "J6": (float(v["wrist_offsets_mm"][1]), 0.0, 0.0)}


def link_transforms(P, q_deg):
    """T_k(q) — 링크 0(바닥) ~ 6 의 세계 변환."""
    off = offsets(P)
    Ts = [T()]
    M = T()
    for k, j in enumerate(["J1", "J2", "J3", "J4", "J5", "J6"]):
        M = M @ T(t=off[j]) @ rot(AXES[j], q_deg[k])
        Ts.append(M)
    return Ts


def joint_origins_q0(P):
    Ts = link_transforms(P, [0.0] * 6)
    return {j: Ts[k + 1][:3, 3].copy() for k, j in enumerate(["J1", "J2", "J3", "J4", "J5", "J6"])}


def placement(P, link, frame, q_deg, Ts0=None, Fr=None):
    """지역 좌표(frame) → 세계(자세 q)."""
    Ts0 = Ts0 or link_transforms(P, [0.0] * 6)
    Fr = Fr or frames(P)
    Tq = link_transforms(P, q_deg)
    return Tq[link] @ np.linalg.inv(Ts0[link]) @ Fr[frame]


# ---------------- 부품 목록 ----------------
WHITE, NAVY, GRAY, MINT = "#FFFFFF", "#0B2545", "#6B7280", "#34D399"          # KMJH(docs/brand/README.md)
NEW_PARTS = {          # 이름: (틀, 링크, 색)
    "FLOOR": ("J1", 0, GRAY), "BASE": ("J1", 0, WHITE), "BASE_RING": ("J1", 0, MINT), "J1_CAN_A": ("J1", 0, WHITE), "J1_CAN_B": ("J1", 0, WHITE),
    "TURRET": ("J1", 1, WHITE), "J1_SPACER": ("J1", 1, GRAY),
    "SHOULDER": ("W", 1, WHITE), "MOTOR_COVER_J2": ("M2", 1, WHITE),
    "J2_HUB": ("W", 2, NAVY), "UPPER_ARM": ("W", 2, WHITE), "UA_LOGO": ("W", 2, NAVY), "J2_CAP": ("W", 2, NAVY), "J2_CAP_MARK": ("W", 2, MINT),
    "MOTOR_COVER_J3": ("M3", 2, WHITE),
    "FOREARM": ("W", 3, WHITE), "J3_CAP": ("W", 3, NAVY), "J3_CAP_MARK": ("W", 3, MINT),
    "J4_CAN_A": ("C4", 3, WHITE), "J4_CAN_B": ("C4", 3, WHITE), "J4_REAR_COVER": ("C4", 3, NAVY),
    "LINK5": ("W", 5, WHITE), "J6_CAN_A": ("C6", 5, WHITE), "J6_CAN_B": ("C6", 5, WHITE), "J6_REAR_COVER": ("C6", 5, NAVY),
    "TOOL_FLANGE": ("C6", 6, MINT),
}
MARKS = {"UA_LOGO": "UPPER_ARM", "J2_CAP_MARK": "J2_CAP", "J3_CAP_MARK": "J3_CAP"}     # 돋움 표시 — 밑 부품과 한 물체로 출력(AMS 높이 구간 색)
COUPONS = {"J1_FIT_SLEEVE": GRAY, "J1_FIT_BORE": GRAY}         # 조립에 없는 출력 시편(실물 6818 끼워 보기 — 판 B 전에)
MP16_STATOR = ["HOUSING_BASE", "CAP", "GUARD", "RETAINER"]
MP16_ROTOR = ["CARRIER", "OUTPUT_FLANGE"]
MP16_INNER = ["DISC_1", "DISC_2", "CAM_LOWER", "CAM_UPPER", "WASHER_T1p4"]
MP6_STATOR = ["HOUSING_BASE", "HOUSING_CAP", "RETAINER"]
MP6_ROTOR = ["CARRIER", "OUTPUT_FLANGE"]
MP6_INNER = ["DISC_1", "DISC_2", "CAM_LOWER", "CAM_UPPER", "WASHER"]
MP10_STATOR = ["J5_STATOR_A", "J5_STATOR_B", "J5_REAR_COVER"]
MP10_ROTOR = ["J5_OUTPUT_HUB"]
KG1 = ["BASE", "JAW_A", "JAW_B", "PINION", "PAD_A_FLAT", "PAD_B_FLAT"]


def catalog(P):
    """조립 몸체 전부 — 이름 → {path, frame, link, kind, collide}. kind: new · reused · inner(겹침 검사 밖 — 그 단위가 이미 봄)."""
    d16 = Path(P["_paths"]["drive_dir"]) / "parts"
    d6 = Path(P["_paths"]["reducer_dir"]) / "parts"
    d10 = Path(P["_paths"]["wrist_dir"]) / "parts"
    dg = Path(P["_paths"]["gripper_dir"]) / "parts"
    c = {}
    for n, (fr, lk, col) in NEW_PARTS.items():
        c[n] = {"path": str(MODEL / "parts" / f"{n}.stl"), "frame": fr, "link": lk, "kind": "new", "color": col, "collide": True}
    for tag, fr, ls, lr in (("J2", "M2", 1, 2), ("J3", "M3", 2, 3)):
        for n in MP16_STATOR:      # 벨트 덮개 = 남색으로 뽑기 권장(v3 끝 덮개 느낌) — 그림 색
            c[f"{tag}.{n}"] = {"path": str(d16 / f"{n}.stl"), "frame": fr, "link": ls, "kind": "reused", "color": NAVY if n == "GUARD" else WHITE, "collide": True}
        for n in MP16_ROTOR:
            c[f"{tag}.{n}"] = {"path": str(d16 / f"{n}.stl"), "frame": fr, "link": lr, "kind": "reused", "color": "#6B7280", "collide": True}
        for n in MP16_INNER:
            c[f"{tag}.{n}"] = {"path": str(d16 / f"{n}.stl"), "frame": fr, "link": ls, "kind": "inner", "color": "#87CEEB", "collide": False}
    for tag, fr, ls, lr in (("J1", "J1", 0, 1), ("J4", "C4", 3, 4), ("J5", "J5M", 4, 5), ("J6", "C6", 5, 6)):
        for n in MP6_STATOR:
            c[f"{tag}.MP6.{n}"] = {"path": str(d6 / f"{n}.stl"), "frame": fr, "link": ls, "kind": "reused", "color": "#FFFFFF", "collide": True}
        for n in MP6_ROTOR:
            c[f"{tag}.MP6.{n}"] = {"path": str(d6 / f"{n}.stl"), "frame": fr, "link": lr, "kind": "reused", "color": "#6B7280", "collide": True}
        for n in MP6_INNER:
            c[f"{tag}.MP6.{n}"] = {"path": str(d6 / f"{n}.stl"), "frame": fr, "link": ls, "kind": "inner", "color": "#87CEEB", "collide": False}
    for n in MP10_STATOR:
        c[f"J5.{n}"] = {"path": str(d10 / f"{n}.stl"), "frame": "J5M", "link": 4, "kind": "reused", "color": "#0B2545" if "COVER" in n else "#FFFFFF", "collide": True}
    for n in MP10_ROTOR:
        c[f"J5.{n}"] = {"path": str(d10 / f"{n}.stl"), "frame": "J5M", "link": 5, "kind": "reused", "color": "#6B7280", "collide": True}
    for n in KG1:
        c[f"KG1.{n}"] = {"path": str(dg / f"{n}.stl"), "frame": "G", "link": 6, "kind": "reused", "color": "#FFFFFF" if n.startswith("JAW") else "#6B7280", "collide": True}
    return c


def motor42(P):
    """42D 모터 + 드라이버 어림 상자(원장 · MP10 과 같은 값) — (이름, 상자 [x0,x1,y0,y1,z0,z1]) 모듈 좌표(z 0 = 모터 앞면)."""
    m = json.loads(Path(P["_paths"]["motor_ledger"]).read_text(encoding="utf-8"))["items"]
    f, bl, ov, dw = (float(m[k]["value"]) for k in ("frame", "body_length", "overall_length", "driver_width"))
    gap = float(m["motor_driver_gap"]["value"])
    return [("BODY", [-f / 2, f / 2, -f / 2, f / 2, -bl, 0.0]), ("DRIVER", [-dw / 2, dw / 2, -dw / 2, dw / 2, -ov, -(bl + gap)])]


def motor57(P, joint):
    """57D 모터 + 보드 어림 상자(MP16 parameters motor · 모듈 좌표)."""
    m, C = P["_drive"]["motor"], belt_centre(P["_drive"])
    f, z0 = m["frame"], P["_drive"]["base"]["lobe_thickness"]
    return [("BODY", [C - f / 2, C + f / 2, -f / 2, f / 2, z0, z0 + m["body_length"][joint] + m["board_length"]])]


def belt_centre(D):
    bt = D["belt"]
    d1, d2 = bt["small_teeth"] * bt["pitch"] / math.pi, bt["big_teeth"] * bt["pitch"] / math.pi
    b = bt["length"] - math.pi * (d1 + d2) / 2
    return (b + math.sqrt(b * b - 2 * (d2 - d1) ** 2)) / 4


def refs(P):
    """구매품 어림 몸체 — 이름 → {frame, link, boxes | annulus}."""
    r = {}
    for tag, fr, lk in (("J1", "J1", 0), ("J4", "C4", 3), ("J5", "J5M", 4), ("J6", "C6", 5)):
        r[f"REF.{tag}.MOTOR42"] = {"frame": fr, "link": lk, "boxes": [b for _n, b in motor42(P)]}
    for tag, fr, lk, j in (("J2", "M2", 1, "J2"), ("J3", "M3", 2, "J3")):
        r[f"REF.{tag}.MOTOR57"] = {"frame": fr, "link": lk, "boxes": [b for _n, b in motor57(P, j)]}
    b = P["j1"]["bearing"]
    for i, (z0, z1) in enumerate(b["z"]):
        r[f"REF.J1.6818_{i + 1}"] = {"frame": "J1", "link": 0, "annulus": [b["id"] / 2, b["od"] / 2, z0, z1]}
    return r
