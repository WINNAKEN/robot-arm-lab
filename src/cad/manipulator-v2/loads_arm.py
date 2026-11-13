# -*- coding: utf-8 -*-
"""MP18 팔 전체 v2 — 질량 · 무게중심 · 관절 토크 여유 · J1 베어링 · 주요 단면 어림(손계산 · 해석 도구 없음).

질량: 새 인쇄 부품 = 출력 준비 기록(슬라이서 g) · 무게중심 = STL 부피 중심 / MP16 인쇄 = MP16 출력 준비 기록 · 금속 = MP16 sizing / MP6 · MP10 = MP10 mass-properties /
그리퍼 = KG1 mass-properties / 모터 · 효율 · 쓸 수 있는 토크 몫 · 안전율 · 가속도 = MP5 inputs.json(읽기만) · 76 mm 모터 = MP16 가정 / 6818 = 이 단위 가정.
짐 = KG1 쥐는 점(G z 103 · J6 + 131). 결과 = .dev/mp18-evidence/loads/loads.json · loads.md
사용: python loads_arm.py [--params P] [--parts DIR] [--printprep F] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh

import layout as L

HERE = Path(__file__).resolve().parent
G = 9.81


def box_inertia(m, dx, dy, dz):
    return np.diag([m * (dy * dy + dz * dz) / 12, m * (dx * dx + dz * dz) / 12, m * (dx * dx + dy * dy) / 12])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--parts", type=Path, default=L.MODEL / "parts")
    ap.add_argument("--printprep", type=Path, default=L.EV / "printprep.json")
    ap.add_argument("--out", type=Path, default=L.EV / "loads")
    a = ap.parse_args()
    P = L.load(a.params)
    cat = L.catalog(P)
    Fr = L.frames(P)
    Ts0 = L.link_transforms(P, [0.0] * 6)
    ROOT = L.ROOT
    mp5 = json.loads((ROOT / "src/cad/review-mp5/inputs.json").read_text(encoding="utf-8"))
    pp = json.loads(a.printprep.read_text(encoding="utf-8"))
    pp16 = json.loads((ROOT / ".dev/mp16-evidence/printprep.json").read_text(encoding="utf-8"))
    sz16 = json.loads((ROOT / ".dev/mp16-evidence/sizing/sizing.json").read_text(encoding="utf-8"))
    mp10 = json.loads((ROOT / "models/j5-wrist-v1/mass-properties.json").read_text(encoding="utf-8"))
    kg1 = json.loads((ROOT / "models/kmjh-gripper-v1/mass-properties.json").read_text(encoding="utf-8"))
    D = P["_drive"]
    bodies = []          # (이름, 링크, 질량 kg, 무게중심 지역, 틀, 관성 지역(3x3, 무게중심 기준))

    def mesh_body(name, link, frame, mesh, mass_kg):
        c = mesh.center_mass if mesh.is_watertight else mesh.centroid
        I = mesh.moment_inertia * (mass_kg / mesh.volume) * 1e-6 if mesh.is_watertight else np.eye(3) * 0.0     # kg·m² (mm² → m²)
        bodies.append((name, link, mass_kg, np.asarray(c, float), frame, I))

    def point(name, link, frame, mass_kg, c, I=None):
        bodies.append((name, link, mass_kg, np.asarray(c, float), frame, np.zeros((3, 3)) if I is None else I))
    # 새 인쇄 부품
    for n, (fr, lk, _c) in L.NEW_PARTS.items():
        m = trimesh.load(a.parts / f"{n}.stl", force="mesh")
        mesh_body(n, lk, fr, m, pp["parts"][n]["mass_g"] / 1000)
    # MP16 J2 · J3
    d16 = Path(P["_paths"]["drive_dir"]) / "parts"
    C = L.belt_centre(D)
    for tag, fr, ls, lr, mot in (("J2", "M2", 1, 2, "NEMA23-76"), ("J3", "M3", 2, 3, "NEMA23-56")):
        for n in L.MP16_STATOR + L.MP16_INNER + L.MP16_ROTOR:
            pn = "DISC_1" if n == "DISC_2" else n
            pn = "WASHER_T1p4" if n.startswith("WASHER") else pn
            m = trimesh.load(d16 / f"{n}.stl", force="mesh")
            mesh_body(f"{tag}.{n}", lr if n in L.MP16_ROTOR else ls, fr, m, pp16["parts"][pn]["mass_g"] / 1000)
        mm = sz16["module_mass"]["metal_parts_kg"]
        point(f"{tag}.ring pins", ls, fr, mm["ring pins"], (0, 0, 24.5))
        point(f"{tag}.output pins", lr, fr, mm["output pins"], (0, 0, 35.0))
        point(f"{tag}.bearings", ls, fr, mm["bearings"], (0, 0, 40.0))
        point(f"{tag}.input shaft", ls, fr, mm["input shaft"], (0, 0, 4.5))
        point(f"{tag}.pulleys + belt", ls, fr, mm["pulleys + belt"], (C * 0.3, 0, -18.0))
        point(f"{tag}.screws + inserts", ls, fr, mm["screws + inserts"], (0, 0, 40.0))
        mk = (1.15 if mot == "NEMA23-76" else mp5["motors"][mot]["mass_kg"])
        mb = L.motor57(P, tag)[0][1]
        point(f"{tag}.motor {mot}", ls, fr, mk, ((mb[0] + mb[1]) / 2, 0, (mb[4] + mb[5] - 14.1) / 2), box_inertia(mk, 0.0564, 0.0564, (mb[5] - mb[4]) / 1000))
        point(f"{tag}.driver 57D", ls, fr, sz16["module_mass"]["driver_57d_kg"], ((mb[0] + mb[1]) / 2, 0, mb[5] - 7.0))
    # MP6 J1 · J4 · J5 · J6 (+ MP10 J5 캔)
    it10 = {i["name"]: i for i in mp10["items"]}
    rot6 = {"MP6 CARRIER", "MP6 OUTPUT_FLANGE"}
    for tag, fr, ls, lr in (("J1", "J1", 0, 1), ("J4", "C4", 3, 4), ("J5", "J5M", 4, 5), ("J6", "C6", 5, 6)):
        for k, it in it10.items():
            if k.startswith("MP6 "):
                point(f"{tag}.{k}", lr if k in rot6 else ls, fr, it["mass_g"] / 1000, it["com_mm"])
        point(f"{tag}.motor + driver 42D", ls, fr, it10["모터 + 드라이버(MKS SERVO42D CAN MT)"]["mass_g"] / 1000, it10["모터 + 드라이버(MKS SERVO42D CAN MT)"]["com_mm"],
              box_inertia(0.31, 0.0423, 0.0423, 0.0535))
        point(f"{tag}.dowels", ls, fr, it10["강철 다월 Ø4 × 28 (28) + Ø4 × 20 (6)"]["mass_g"] / 1000, it10["강철 다월 Ø4 × 28 (28) + Ø4 × 20 (6)"]["com_mm"])
        point(f"{tag}.bearings", ls, fr, it10["베어링 6808 + 6801 × 2 + 6800"]["mass_g"] / 1000, it10["베어링 6808 + 6801 × 2 + 6800"]["com_mm"])
        point(f"{tag}.screws + inserts", ls, fr, 0.015, (0, 0, 0))
    for k in ("J5_STATOR_A", "J5_STATOR_B", "J5_REAR_COVER", "J5_OUTPUT_HUB"):
        it = it10[k]
        point(f"J5.{k}", 5 if k == "J5_OUTPUT_HUB" else 4, "J5M", it["mass_g"] / 1000, it["com_mm"])
    point("J5.screws + inserts (MP10)", 4, "J5M", 0.012, (0, 0, -20.0))
    point("KG1 gripper (total)", 6, "G", kg1["total_mass_g"] / 1000, kg1["com_mm"])
    b = P["j1"]["bearing"]
    for i, (z0, z1) in enumerate(b["z"]):
        point(f"J1.6818 #{i + 1}", 1, "J1", b["kg_each"], (0, 0, (z0 + z1) / 2))
    point("MP18 screws + inserts (about 95)", 2, "W", 0.11, (80.0, 80.0, 174.0))
    if "cable" in P["v2"] and "cable_mass_g_per_m" in P["v2"]["cable"]:         # MP18 이어서 케이블 검토 R1-10d: 케이블 질량 어림(점 질량 · 세계 q0)
        for n_, lk_, kg_, c_ in L.cable_masses(P):
            point(n_, lk_, "W", kg_, c_)

    def world(q):
        Tq = L.link_transforms(P, q)
        out = []
        for name, lk, mkg, c, fr, I in bodies:
            M = Tq[lk] @ np.linalg.inv(Ts0[lk]) @ Fr[fr]
            out.append((name, lk, mkg, (M @ [*c, 1.0])[:3], M[:3, :3] @ I @ M[:3, :3].T))
        return out, Tq

    grasp = np.array(kg1["grasp_centre_mm"], float)

    def payload_point(q):
        Tq = L.link_transforms(P, q)
        M = Tq[6] @ np.linalg.inv(Ts0[6]) @ Fr["G"]
        return (M @ [*grasp, 1.0])[:3]
    joints = ["J1", "J2", "J3", "J4", "J5", "J6"]
    ax_i = {"x": 0, "y": 1, "z": 2}
    acc = mp5["angular_accel_rad_s2"]["value"]
    sf = mp5["safety_factor"]["value"]
    usable = mp5["usable_torque_fraction"]["value"]
    j6_off = mp5["j6_payload_offset_from_axis_m"]["value"] * 1000

    def torque(k, q, pay):
        """관절 k(0 ~ 5) 의 중력 토크 · 관성 토크(N·m) — 링크 k+1 이후 + 짐."""
        bl, Tq = world(q)
        o = Tq[k + 1][:3, 3]
        a = Tq[k + 1][:3, ax_i[L.AXES[joints[k]]]]
        tg, I = 0.0, 0.0
        pts = [(mkg, p, Ii) for _n, lk, mkg, p, Ii in bl if lk >= k + 1]
        pp_ = payload_point(q)
        if joints[k] == "J6":
            pp_ = pp_ + np.cross(a, [0, 0, 1.0]) / max(1e-9, np.linalg.norm(np.cross(a, [0, 0, 1.0]))) * j6_off
        pts.append((pay, pp_, np.zeros((3, 3))))
        for mkg, p, Ii in pts:
            r = (p - o) / 1000
            tg += float(np.dot(np.cross(r, [0, 0, -mkg * G]), a))
            d2 = float(np.dot(r, r) - np.dot(r, a) ** 2)
            I += mkg * d2 + float(a @ Ii @ a)
        return abs(tg), I * acc
    poses = {
        "J1": [[0, 0, 0, 0, 0, 0]],
        "J2": [[0, a2, a3, 0, 0, 0] for a2 in range(-180, 181, 10) for a3 in (0, 45, 90, -45)],
        "J3": [[0, a2, a3, 0, 0, 0] for a2 in (0, -45, -90, -135) for a3 in range(-180, 181, 10)],
        "J4": [[0, 0, 0, a4, a5, 0] for a4 in range(0, 181, 15) for a5 in (90, -90, 45)],
        "J5": [[0, 0, 0, 0, a5, 0] for a5 in range(-180, 181, 10)],
        "J6": [[0, 0, 0, 0, 0, a6] for a6 in range(0, 181, 15)],
    }
    motors = {"J1": "NEMA17-40", "J2": "NEMA23-76", "J3": "NEMA23-56", "J4": "NEMA17-40", "J5": "NEMA17-40", "J6": "NEMA17-40"}
    ratio = {"J1": 27, "J2": 81, "J3": 81, "J4": 27, "J5": 27, "J6": 27}
    eff = {j: mp5["efficiency_by_type"]["prestage_plus_cycloid" if ratio[j] == 81 else "cycloid_printed"]["value"] for j in joints}
    hold = {j: (1.89 if motors[j] == "NEMA23-76" else mp5["motors"][motors[j]]["holding_Nm"]) for j in joints}
    have = {j: hold[j] * usable * ratio[j] * eff[j] for j in joints}
    res = {}
    for pay in (0.5, 0.7, 1.0):
        row = {}
        for k, j in enumerate(joints):
            best = None
            for q in poses[j]:
                tg, ti = torque(k, [float(v) for v in q], pay)
                need = sf * (tg + ti)
                if best is None or need > best["need_Nm"]:
                    best = {"need_Nm": need, "gravity_Nm": tg, "inertia_Nm": ti, "pose_deg": q}
            best["have_Nm"] = have[j]
            best["margin"] = have[j] / best["need_Nm"] - 1
            row[j] = best
        res[str(pay)] = row
    # 짐 한계(안전율 2 · 같은 자세) — 필요 토크는 짐에 대해 1 차
    limit = {}
    for k, j in enumerate(joints):
        q = res["1.0"][j]["pose_deg"]
        n0 = sum(torque(k, [float(v) for v in q], 0.0)) * sf
        n1 = sum(torque(k, [float(v) for v in q], 1.0)) * sf
        limit[j] = (have[j] - n0) / (n1 - n0) if n1 > n0 else None
    # 질량 합 · 무게중심(q = 0 · 표시 자세)
    bl0, _ = world([0.0] * 6)
    by_link = {}
    for _n, lk, mkg, p, _I in bl0:
        by_link.setdefault(lk, 0.0)
        by_link[lk] += mkg
    tot = sum(m for _n, _l, m, _p, _I in bl0)
    com0 = sum(m * p for _n, _l, m, p, _I in bl0) / tot
    # J1 베어링(6818 두 개 · 간격) — 넘어뜨리는 모멘트 최대(J2 훑기 자세 · 짐 1 kg)
    zc = P["j1"]["motor_face_z"]
    zb = [zc + (z0 + z1) / 2 for z0, z1 in b["z"]]
    span = (zb[1] - zb[0]) / 1000
    worst = None
    for q in poses["J2"]:
        bl, _ = world([float(v) for v in q])
        pts = [(mkg, p) for _n, lk, mkg, p, _I in bl if lk >= 1] + [(1.0, payload_point([float(v) for v in q]))]
        W = sum(m for m, _p in pts) * G
        Mx = sum(m * G * (p[1]) / 1000 for m, p in pts)
        My = sum(m * G * (p[0]) / 1000 for m, p in pts)
        Mo = math.hypot(Mx, My)
        if worst is None or Mo > worst["moment_Nm"]:
            worst = {"moment_Nm": Mo, "axial_N": W, "pose_deg": q}
    worst["radial_per_bearing_N"] = worst["moment_Nm"] / span
    worst["span_mm"] = span * 1000
    worst["c0_assumed_kN"] = 19.0
    worst["static_sf"] = worst["c0_assumed_kN"] * 1000 / (worst["radial_per_bearing_N"] + 0.5 * worst["axial_N"])
    # 주요 단면(손계산 · 설계 토크 = 1 kg 필요 토크 · 안전율 2 포함)
    t2, t3, t5 = res["1.0"]["J2"]["need_Nm"], res["1.0"]["J3"]["need_Nm"], res["1.0"]["J5"]["need_Nm"]
    ua, fa, l5, sh = P["j3"]["upper_arm"], P["j3"]["forearm"], P["link5"], P["j2"]["shoulder"]

    def rect_z(t, h):
        return t * h * h / 6
    u2 = P["v2"]["upper_arm"]
    sections = {
        (f"upper arm box at the J3-motor plate notches (walls {P['v2']['wall']:g} x {u2['wall_top_y'] - u2['plate_y'][0]:g} + cover {u2['cover_t']:g} x {2 * u2['bar_half_z']:g} "
         f"- plate cut to 0.45 · W {L.ua_box_section(P):.0f} mm3 · design J2 torque taken there too)"): t2 * 1000 / L.ua_box_section(P),
        "forearm at the J3 disc edge (plate 10 x 60)": t3 * 1000 / rect_z(fa["plate_y"][1] - fa["plate_y"][0], 2 * fa["beam_half_z"]),
        "link 5 at the J5 boss edge (plate 10 x 60)": t5 * 1000 / rect_z(l5["plate_y"][1] - l5["plate_y"][0], 2 * l5["beam_half_z"]),
        "shoulder plate at the turret (8 x 188, J2 reaction in plane)": t2 * 1000 / rect_z(sh["plate_y"][1] - sh["plate_y"][0], sh["body_x"][1] - sh["body_x"][0]),
    }
    screw_shear = {"J2 hub screws (6 x M3 at r 22)": t2 / (6 * 0.022), "J3 forearm screws (6 x M3 at r 22)": t3 / (6 * 0.022)}
    margins_summary = {pay: {j: round(v["margin"], 3) for j, v in row.items()} for pay, row in res.items()}
    verdict = all(res["1.0"][j]["margin"] >= 0 for j in ("J1", "J2", "J3", "J6"))
    # 감속기 설계점 대조(검토 R1-17 · 18): J2 · J3 = MP16 sizing 설계 토크(안전율 2 포함) · 손목형 = MP6 cycloid.json loads_rough S1 의 검토 토크
    cyc = json.loads(Path(P["_paths"]["reducer_json"]).read_text(encoding="utf-8"))
    design = {"J2": sz16["design_torque_Nm"], "J3": sz16["design_torque_Nm"]}
    for j in ("J1", "J4", "J5", "J6"):
        design[j] = cyc["loads_rough"]["S1"]["wrist_need_Nm"]
    reducer = {pay: {j: {"need_Nm": row[j]["need_Nm"], "design_Nm": design[j], "reducer_sf": sf * design[j] / row[j]["need_Nm"]} for j in joints} for pay, row in res.items()}
    reducer_flags = [f"{j} {pay} kg: reducer SF {v['reducer_sf']:.2f} < {sf:g}" for pay, row in reducer.items() for j, v in row.items() if v["reducer_sf"] < sf - 1e-9]
    pay_at_design = {}
    for k, j in enumerate(joints):
        q = res["1.0"][j]["pose_deg"]
        n0 = sum(torque(k, [float(v) for v in q], 0.0)) * sf
        n1 = sum(torque(k, [float(v) for v in q], 1.0)) * sf
        pay_at_design[j] = (design[j] - n0) / (n1 - n0) if n1 > n0 else None
    # 출력 베어링 기울임(검토 R1-21): 관절 출력 베어링 가운데에서 그 관절 바깥 몸체 + 짐 1 kg 의 중력 모멘트 중 축에 수직인 몫(정지 · 최대)
    brg = {"J2": ("M2", (0.0, 0.0, 64.5), "6812"), "J3": ("M3", (0.0, 0.0, 64.5), "6812"), "J4": ("C4", (0.0, 0.0, 39.0), "6808"),
           "J5": ("J5M", (0.0, 0.0, 39.0), "6808"), "J6": ("C6", (0.0, 0.0, 39.0), "6808")}
    tilt = {}
    for k, j in enumerate(joints):
        if j not in brg:
            continue
        fr, cl, bname = brg[j]
        best = None
        for q in poses[j] + poses["J5"]:
            q = [float(v) for v in q]
            bl, Tq = world(q)
            lk = k + 1
            M = Tq[lk] @ np.linalg.inv(Ts0[lk]) @ Fr[fr]
            c = (M @ [*cl, 1.0])[:3]
            ax_ = M[:3, 2]
            mom = np.zeros(3)
            for _n, l2, mkg, p, _I in bl:
                if l2 >= lk:
                    mom += np.cross((p - c) / 1000, [0, 0, -mkg * G])
            mom += np.cross((payload_point(q) - c) / 1000, [0, 0, -1.0 * G])
            t_ = float(np.linalg.norm(mom - np.dot(mom, ax_) * ax_))
            if best is None or t_ > best["tilt_Nm"]:
                best = {"tilt_Nm": t_, "pose_deg": q, "bearing": bname}
        tilt[j] = best
    # 채움을 올렸을 때(검토 R1-22): 구조 부품(어깨 · 위팔 · 아래팔 · 링크 5 · 회전대 · 바닥판) 질량 × 1.4 → J2 · J3 필요(1 kg)
    heavy = {"SHOULDER", "UPPER_ARM", "FOREARM", "LINK5", "TURRET", "BASE"}
    saved = list(bodies)
    bodies[:] = [(n, lk, (m * 1.4 if n in heavy else m), c, fr, I) for n, lk, m, c, fr, I in saved]
    infill40 = {}
    for k, j in ((1, "J2"), (2, "J3")):
        q = res["1.0"][j]["pose_deg"]
        tg, ti = torque(k, [float(v) for v in q], 1.0)
        infill40[j] = {"need_Nm": sf * (tg + ti), "motor_margin": have[j] / (sf * (tg + ti)) - 1, "reducer_sf": sf * design[j] / (sf * (tg + ti))}
    bodies[:] = saved
    ins = {f"parts/{n}.stl": L.sha(a.parts / f"{n}.stl") for n in L.NEW_PARTS}
    ins.update({"printprep.json": L.sha(a.printprep), "inputs.json(MP5)": L.sha(ROOT / "src/cad/review-mp5/inputs.json"),
                "printprep.json(MP16)": L.sha(ROOT / ".dev/mp16-evidence/printprep.json"), "sizing.json(MP16)": L.sha(ROOT / ".dev/mp16-evidence/sizing/sizing.json"),
                "mass-properties.json(MP10)": L.sha(ROOT / "models/j5-wrist-v1/mass-properties.json"),
                "mass-properties.json(KG1)": L.sha(ROOT / "models/kmjh-gripper-v1/mass-properties.json"), "parameters.json": L.sha(a.params),
                "loads_arm.py": L.sha(__file__), "layout.py": L.sha(HERE / "layout.py")})
    out = {"what": "MP18 팔 전체 v2 하중 어림(손계산 · 해석 도구 없음) — 필요 = 안전율 × (중력 + 관성 α I) · 가진 것 = 유지 토크 × 쓸 몫 × 감속비 × 효율(MP5 가정)",
           "verdict": verdict, "verdict_rule": "J1 · J2 · J3 · J6 margin >= 0 at 1.0 kg (user basis for J2 · J3: 「J2·J3 는 1 kg 기준 (권장)」); J4 · J5 = wrist MP6 27:1 unchanged - reported with the payload limit",
           "assumptions": {"safety_factor": sf, "usable_torque_fraction": usable, "angular_accel_rad_s2": acc, "efficiency": eff, "holding_Nm": hold, "ratio": ratio,
                           "payload_point": "KG1 grasp centre G (0, 0, 103) = J6 + 131 (MP9)", "j6_payload_offset_mm": j6_off,
                           "nema23_76_mass_kg": 1.15, "nema23_76_holding_Nm": 1.89, "bearing_6818_kg": b["kg_each"], "c0_6818_kN": 19.0,
                           "cables": "point masses from the MP18 cable route (fixed segments at their length-weighted centre · loops half at each anchor) · linear density = v2.cable.cable_mass_g_per_m (ASSUMPTION)", "printed_mass": "slicer 0.20 Standard PLA (15 % infill) - COM = solid STL centroid"},
           "mass_kg": {"total": tot, "by_link": {str(k): v for k, v in sorted(by_link.items())}, "com_q0_mm": com0.tolist()},
           "margins": res, "margins_summary": margins_summary, "payload_limit_kg_sf2": limit, "j1_bearings": worst,
           "reducer_design": reducer, "reducer_flags": reducer_flags, "payload_at_reducer_design_kg": pay_at_design,
           "reducer_note": "design torque = MP16 sizing design_torque_Nm (J2 · J3, SF 2 included) / MP6 cycloid.json loads_rough S1 wrist_need_Nm (J1 · J4 · J5 · J6) - reducer_sf = 2 x design / need",
           "output_bearing_tilt_1kg": tilt, "infill40_structural": infill40,
           "sections_MPa_at_design_torque": sections, "screw_shear_N_each": screw_shear, "inputs_sha256": ins,
           "bodies": [{"name": n, "link": lk, "kg": round(m, 4)} for n, lk, m, _c, _f, _I in bodies]}
    a.out.mkdir(parents=True, exist_ok=True)

    def cl(o):
        if isinstance(o, dict):
            return {str(k): cl(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [cl(v) for v in o]
        if isinstance(o, (np.floating, float)):
            return round(float(o), 4)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return o
    (a.out / "loads.json").write_bytes((json.dumps(cl(out), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    lines = [f"# MP18 하중 어림(팔 전체 v2) — 판정 {verdict}", "", f"- 질량 합 {tot:.2f} kg(케이블 어림 포함 · 선 밀도 가정) · 링크별 " + " · ".join(f"L{k} {v:.2f}" for k, v in sorted(by_link.items())), ""]
    lines.append("| 짐 | " + " | ".join(joints) + " |")
    lines.append("|---|" + "---|" * len(joints))
    for pay, row in res.items():
        lines.append(f"| {pay} kg | " + " | ".join(f"{row[j]['need_Nm']:.2f} / {row[j]['have_Nm']:.2f} ({row[j]['margin'] * 100:+.0f} %)" for j in joints) + " |")
    lines += ["", "짐 한계(안전율 2): " + " · ".join(f"{j} {v:.2f} kg" if v is not None else f"{j} -" for j, v in limit.items()),
              f"J1 베어링: 넘어뜨리는 모멘트 최대 {worst['moment_Nm']:.1f} N·m · 베어링 하나 반경 {worst['radial_per_bearing_N']:.0f} N(간격 {worst['span_mm']:.0f} mm) · "
              f"C0 가정 19 kN 기준 정적 안전율 {worst['static_sf']:.0f}", "",
              "단면(설계 토크 · 안전율 2 포함): " + " · ".join(f"{k} {v:.1f} MPa" for k, v in sections.items()),
              "나사 전단(하나): " + " · ".join(f"{k} {v:.0f} N" for k, v in screw_shear.items()), "",
              "감속기 설계점(안전율): " + " · ".join(f"{pay} kg " + " · ".join(f"{j} {v['reducer_sf']:.2f}" for j, v in row.items()) for pay, row in reducer.items()),
              "감속기 설계점에 맞는 짐: " + " · ".join(f"{j} {v:.2f} kg" if v is not None else f"{j} -" for j, v in pay_at_design.items()),
              "출력 베어링 기울임(1 kg 정지 최대): " + " · ".join(f"{j} {v['bearing']} {v['tilt_Nm']:.2f} N·m" for j, v in tilt.items()),
              "구조 부품 채움 올림(질량 × 1.4): " + " · ".join(f"{j} 필요 {v['need_Nm']:.1f} N·m · 모터 여유 {v['motor_margin'] * 100:+.0f} % · 감속기 안전율 {v['reducer_sf']:.2f}" for j, v in infill40.items())]
    (a.out / "loads.md").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
