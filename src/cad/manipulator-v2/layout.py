# -*- coding: utf-8 -*-
"""MP18 팔 전체 v2(v3 초안 모양 전면 재설계 · 개념 B) — 좌표틀 · 순기구학 · 부품 목록(생성기 · 검사기 · 출력 준비가 함께 쓴다).
MP17 `src/cad/manipulator-v1/layout.py` 를 복사해 고침(MP17 파일은 그대로). 바뀐 것: J3 구동 모듈을 축 둘레로 j3.module_turn_deg 돌림(모터가 위팔 안 J2 쪽) · 부품 목록.

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
NAME = "manipulator-v2"
MODEL = ROOT / "models" / NAME
EV = ROOT / ".dev" / "mp18-evidence"


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
        "M3": cols((0, 0, 1), (-1, 0, 0), (0, -1, 0), (o["J3"][0], y3, zj)) @ rot("z", float(P["j3"]["module_turn_deg"])),   # MP18: 모터가 위팔 안(J2 쪽)
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
    "FLOOR": ("J1", 0, GRAY), "BASE": ("J1", 0, WHITE), "BASE_SKIN": ("J1", 0, WHITE), "BASE_SKIN_BAND": ("J1", 0, MINT), "J1_CAN_A": ("J1", 0, WHITE), "J1_CAN_B": ("J1", 0, WHITE),
    "TURRET": ("J1", 1, WHITE), "TURRET_BAND": ("J1", 1, NAVY), "J1_SPACER": ("J1", 1, GRAY),
    "SHOULDER": ("W", 1, WHITE), "SHOULDER_SHROUD": ("W", 1, WHITE), "J2_MOTOR_HOOD": ("W", 1, WHITE), "J2_HOOD_FACE": ("W", 1, NAVY),
    "J2_HUB": ("W", 2, NAVY), "UPPER_ARM": ("W", 2, WHITE), "UA_COVER": ("W", 2, WHITE), "UA_J3_BRACKET": ("W", 2, WHITE), "UA_LOGO": ("W", 2, NAVY),
    "UA_CAP_J2": ("W", 2, NAVY), "UA_CAP_J2_MARK": ("W", 2, MINT), "UA_CAP_J3": ("W", 2, NAVY), "UA_CAP_J3_MARK": ("W", 2, MINT),
    "FOREARM": ("W", 3, WHITE), "J3_CAP": ("W", 3, NAVY), "J3_CAP_MARK": ("W", 3, MINT),
    "J4_CAN_A": ("C4", 3, WHITE), "J4_CAN_B": ("C4", 3, WHITE), "J4_REAR_COVER": ("C4", 3, WHITE),
    "FA_TUBE": ("W", 3, WHITE), "FA_TUBE_CAP": ("W", 3, NAVY), "FA_TUBE_RING": ("W", 3, NAVY),
    "LINK5": ("W", 5, WHITE), "LINK5_CAP": ("W", 5, NAVY), "LINK5_CAP_MARK": ("W", 5, MINT),
    "J6_CAN_A": ("C6", 5, WHITE), "J6_CAN_B": ("C6", 5, WHITE), "J6_REAR_COVER": ("C6", 5, WHITE),
    "J6_TUBE": ("W", 5, WHITE), "J6_TUBE_CAP": ("W", 5, NAVY), "J6_TUBE_RING": ("W", 5, NAVY),
    "TOOL_FLANGE": ("C6", 6, MINT),
}
MARKS = {"UA_LOGO": "UA_COVER", "UA_CAP_J2_MARK": "UA_CAP_J2", "UA_CAP_J3_MARK": "UA_CAP_J3", "J3_CAP_MARK": "J3_CAP", "J2_HOOD_FACE": "J2_MOTOR_HOOD",
         "BASE_SKIN_BAND": "BASE_SKIN", "TURRET_BAND": "TURRET", "FA_TUBE_CAP": "FA_TUBE", "FA_TUBE_RING": "FA_TUBE", "J6_TUBE_CAP": "J6_TUBE",
         "J6_TUBE_RING": "J6_TUBE", "LINK5_CAP_MARK": "LINK5_CAP"}    # 한 물체로 출력(AMS 높이 구간 색) — 밑 부품 이름     # 돋움 표시 — 밑 부품과 한 물체로 출력(AMS 높이 구간 색)
COUPONS = {"J1_FIT_SLEEVE": GRAY, "J1_FIT_BORE": GRAY}         # 조립에 없는 출력 시편(실물 6818 끼워 보기 — 판 B 전에)
MP16_STATOR = ["HOUSING_BASE", "CAP", "RETAINER"]          # MP18: GUARD 안 씀(집이 벨트를 감쌈)
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


def term57(P, joint):
    """MP18 이어서: 57D 드라이버(가정 폭)와 선을 꽂은 단자 어림 상자 — 42D 배치 가정(parameters v2.term57) · 모듈 좌표(z 0 = 바닥판 · 모터 앞면 = lobe 위).
    뒤에서 볼 때 위 = 모터 4 단자 + 몸통 위 6 핀 커넥터 · 왼쪽 = 5+2 단자대(CAN) · 오른쪽 = 6 단자대(전원) · 아래 = 화면 · 단추.
    반환 = {이름: [x0,x1,y0,y1,z0,z1]} — DRIVER · TOP(4 단자) · LEFT(CAN) · RIGHT(전원) · CONN(모터 커넥터)."""
    t = P["v2"]["term57"]
    D = P["_drive"]
    m = D["motor"]
    C = belt_centre(D)
    hm = m["frame"] / 2
    hd = hm + t["driver_excess"]
    z0 = D["base"]["lobe_thickness"]
    zb = z0 + m["body_length"][joint]                      # 몸통 뒤 끝
    zd = zb + m["board_length"]                            # 보드 끝
    ux, uy = t["u_top_module"]
    rx, ry = uy, -ux                                       # 뒤에서 볼 때 오른쪽 = f × u (f = −z)
    zr = zd + t["rear_margin"]

    def face(dx, dy, r0, r1, half, za, zb_):
        if dx:
            xa, xb = sorted((C + dx * r0, C + dx * r1))
            return [xa, xb, -half, half, za, zb_]
        ya, yb = sorted((dy * r0, dy * r1))
        return [C - half, C + half, ya, yb, za, zb_]
    c = t["conn"]
    return {"DRIVER": [C - hd, C + hd, -hd, hd, zb, zd],
            "TOP": face(ux, uy, hd - 0.5, hd + t["clearance"], t["band_half"], zb, zr),
            "LEFT": face(-rx, -ry, hd - 0.5, hd + t["clearance"], t["band_half"], zb, zr),
            "RIGHT": face(rx, ry, hd - 0.5, hd + t["clearance"], t["band_half"], zb, zr),
            "CONN": face(ux, uy, hm - 0.5, hm + c["h"] + c["top_clear"], c["band_half"], zb - c["len"] - c["front_clear"], zb)}


def ua_box_section(P):
    """MP18 이어서 케이블 검토 R1-8: 위팔 상자 단면 계수(mm³ · 팔 평면 굽힘) — J3 모터 판 홈 자리(판이 벽까지 0.45 만 남음): 위 · 아래 벽(두께 wall · 폭 = 판 뒤 ~ 벽 끝)
    + 앞 덮개(두께 cover_t · 높이 = 막대 전체) · 판 띠 0.45 는 뺌."""
    u, W = P["v2"]["upper_arm"], P["v2"]["wall"]
    hb = u["bar_half_z"]
    b = u["wall_top_y"] - u["plate_y"][0]
    d = hb - W / 2
    return (2 * (b * W ** 3 / 12 + b * W * d * d) + u["cover_t"] * (2 * hb) ** 3 / 12) / hb


def cable_masses(P):
    """MP18 이어서 케이블 검토 R1-10d: 케이블 질량 어림 — [(이름, 링크, kg, 세계 q0 점)]: 고정 구간 = 길이 가중 가운데 · 고리 = 반씩 두 고정점(선 밀도 = v2.cable.cable_mass_g_per_m · 가정)."""
    cb = P["v2"]["cable"]
    dens = cb["cable_mass_g_per_m"]
    out = []
    for s in cb["segments"]:
        pts = np.asarray(s["pts"], float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        ln = float(seg.sum())
        if ln <= 0.0:
            continue
        mid = (((pts[:-1] + pts[1:]) / 2) * seg[:, None]).sum(0) / ln
        g_m = dens["bundle"] if s["d"] >= 6.0 else dens["gripper"]
        out.append((f"cable {s['name']}", s["link"], ln / 1000 * g_m / 1000, mid))
    for lp in cb["loops"]:
        g_m = dens["gripper"] if lp["joint"] == "J6" else dens["bundle"]
        kg = lp["length"] / 1000 * g_m / 1000
        for e_ in ("a", "b"):
            out.append((f"cable loop {lp['joint']}.{e_}", lp[e_]["link"], kg / 2, np.asarray(lp[e_]["p"], float)))
    return out


def capsule_mesh(p0, p1, r):
    """두 점 사이 캡슐(케이블 고정 구간 어림) — 세계 좌표 메시."""
    import trimesh
    a, b = np.asarray(p0, float), np.asarray(p1, float)
    v = b - a
    h = float(np.linalg.norm(v))
    m = trimesh.creation.capsule(height=max(h, 1e-3), radius=r, count=[16, 16])
    z = np.array([0.0, 0.0, 1.0])
    d = v / h if h > 1e-9 else z
    ax = np.cross(z, d)
    if np.linalg.norm(ax) > 1e-9:
        m.apply_transform(trimesh.transformations.rotation_matrix(math.acos(max(-1.0, min(1.0, float(np.dot(z, d))))), ax))
    elif d[2] < 0:
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    m.apply_translation((a + b) / 2)
    return m


def refs(P):
    """구매품 어림 몸체 — 이름 → {frame, link, boxes | annulus | capsule}. MP18 이어서: 57D 드라이버 · 단자(42D 배치 가정) · 케이블 고정 구간(세계 q0 · 틀 W)."""
    r = {}
    for tag, fr, lk in (("J1", "J1", 0), ("J4", "C4", 3), ("J5", "J5M", 4), ("J6", "C6", 5)):
        r[f"REF.{tag}.MOTOR42"] = {"frame": fr, "link": lk, "boxes": [b for _n, b in motor42(P)]}
    for tag, fr, lk, j in (("J2", "M2", 1, "J2"), ("J3", "M3", 2, "J3")):
        r[f"REF.{tag}.MOTOR57"] = {"frame": fr, "link": lk, "boxes": [b for _n, b in motor57(P, j)]}
        if "term57" in P["v2"]:
            tr = P["_drive"]["belt"]["slot_travel"]                          # 검토 R1-4: J3 모터는 벨트 홈 ±2.5 어디에나(장력) — 드라이버 · 단자 어림을 두 끝에도
            for k, b in term57(P, j).items():
                nm = "DRIVER57" if k == "DRIVER" else f"TERM57_{k}"
                r[f"REF.{tag}.{nm}"] = {"frame": fr, "link": lk, "boxes": [b]}
                if tag == "J3":
                    for e in P["v2"]["term57"].get("j3_slot_ends", [tr, -tr]):       # 모듈 x = 벨트 선(+ = J2 쪽 = 장력 · − = J3 쪽 — 가정 드라이버가 J3 뚜껑에 닿기 전 −1.5)
                        r[f"REF.{tag}.{nm}@{e:+g}"] = {"frame": fr, "link": lk, "boxes": [[b[0] + e, b[1] + e, *b[2:]]]}
    b = P["j1"]["bearing"]
    for i, (z0, z1) in enumerate(b["z"]):
        r[f"REF.J1.6818_{i + 1}"] = {"frame": "J1", "link": 0, "annulus": [b["id"] / 2, b["od"] / 2, z0, z1]}
    for s in P["v2"].get("cable", {}).get("segments", []):
        for i, (p0, p1) in enumerate(zip(s["pts"][:-1], s["pts"][1:])):
            r[f"REF.CABLE.{s['name']}.{i}"] = {"frame": "W", "link": s["link"], "capsule": [p0, p1, s["d"] / 2]}
    return r


def ref_mesh(r):
    """어림 몸체 하나의 지역 메시(틀 좌표) — 상자 · 고리 · 캡슐."""
    import trimesh
    if "boxes" in r:
        return trimesh.util.concatenate([trimesh.creation.box(bounds=[[b[0], b[2], b[4]], [b[1], b[3], b[5]]]) for b in r["boxes"]])
    if "capsule" in r:
        p0, p1, rad = r["capsule"]
        return capsule_mesh(p0, p1, rad)
    ri, ro, z0, z1 = r["annulus"]
    m = trimesh.creation.annulus(r_min=ri, r_max=ro, height=z1 - z0, sections=180)
    m.apply_translation([0, 0, (z0 + z1) / 2])
    return m
