# -*- coding: utf-8 -*-
"""MP6 — 사이클로이드 27:1 시제품(손목 크기 · 1 호기용)의 결정론 계산(Mech-Sparring 원칙: 수치는 여기서만 나온다 · 형상 생성기도 이 모듈의
stack · radii · disc_pose · make_profile 를 쓴다).

하는 일:
1. 원판 윤곽(등거리 사이클로이드 — 기준 곡선에서 법선으로 핀 반지름 + 틈 C) · 점 수 = 현 오차 상한 · 단순성 · 로브 끝 · 골의 곡률 반지름.
2. 기구학: 원판 한 바퀴(입력 27 바퀴) 동안 원판 둘(둘째 = 같은 부품을 자기 중심에서 180° 돌려 끼움 — 27 로브는 180° 대칭이 아니므로 이것이 곧 반대
   편심에 필요한 반 로브 어긋남이다 · 편심 θ + 180° · 같은 출력 −θ/27 명목)과 고정 핀 · 출력 핀의 최소 틈. 표본 사이 움직임 상한을 빼 「보장 틈」 을 낸다.
3. 쌓임(z) · 반지름 · 벽(≥ 최소 재료) · 움직이는 쪽과 고정 쪽(또는 다른 속도) 사이 틈 · 베어링 고리 닿음(턱마다 같은 속도의 고리 하나에만 닿는가 —
   고리 단면은 가정 `ring_section_factor`).
4. 하중(어림): MP5 loads.json 의 손목 필요 토크(S1 ~ S4 · 짐 0.5 kg · 안전율 포함)로 모터 쪽 여유 · 출력 핀 힘(3 핀 / 1 핀) · PLA 면압 · 출력 핀 밑동 굽힘
   (원판 1 · 2 가운데까지의 팔) · 편심 반력 규모 T/(27E) · 두 원판 반력의 짝힘. 어깨(J2) 값은 「이 크기 대상 아님」 으로 함께 기록.

사용: python cycloid.py --out <cycloid.json> [--params parameters.json] [--repo <저장소>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon

HERE = Path(__file__).resolve().parent
WALL_EPS = 1e-9


def load_params(params_path):
    """parameters.json 을 읽고, `fits_from` 이 가리키는 끼움 보정 원장(재료별 · src/cad/calibration/print-fits.json)의 값을 fits 에 채운다 — 보정값의
    유일한 출처는 원장이다. 원본 parameters 에 원장 키가 적혀 있으면 멈춘다(두 곳에 적히면 어느 값이 쓰였는지 추적이 끊긴다). 이미 채운 사본(양성 대조가
    바꿔 쓴 것)은 그대로 둔다."""
    path = Path(params_path)
    P = json.loads(path.read_text(encoding="utf-8"))
    src = P.get("fits_from")
    if not src or "calibration" in P["fits"]:
        return P
    ledger_path = (path.parent / src["ledger"]).resolve()
    vals = json.loads(ledger_path.read_text(encoding="utf-8"))["materials"][src["material"]]["values"]
    clash = sorted(set(vals) & set(P["fits"]))
    if clash:
        raise ValueError(f"calibration keys written in {path.name}: {clash} - edit {ledger_path.name} instead")
    for k, v in vals.items():
        P["fits"][k] = v["value"]
    used = {k: v["value"] for k, v in vals.items()}
    P["fits"]["calibration"] = {"ledger": str(ledger_path), "material": src["material"], "values": used,
                                "values_sha256": calibration_fingerprint(src["material"], used)}
    return P


def calibration_fingerprint(material, values):
    """쓰인 보정값의 지문(재료 + 값) — 원장의 상태 · 메모 · 판정 기록만 바뀌면 그대로라 다시 만들 필요가 없다."""
    return hashlib.sha256(json.dumps({"material": material, "values": values}, sort_keys=True).encode("utf-8")).hexdigest()


# ---------------- 쌓임 · 반지름 · 고리 단면(형상 생성기와 같이 쓴다) ----------------
def stack(P):
    """쌓임(z · mm · 모터 면 = 0). 모든 부품 높이의 권위."""
    d, B, m = P["disc"], P["bearings"], P["motor"]
    base_t, g, mm = P["housing"]["base_thickness"], d["axial_gap"], P["min_material"]
    bw1, bw0, bwo = B["disc"]["width"], B["shaft_end"]["width"], B["output"]["width"]
    z = {"motor_face": 0.0, "motor_pilot_top": m["pilot_height"], "base_top": base_t}
    # 모터 나사 머리는 바닥판 위로 나온다(카운터보어를 두면 고정 핀 구멍과의 벽이 2 mm 아래) → 원판 1 을 머리 + 틈만큼 띄운다
    z["motor_screw_head"] = (base_t, base_t + m["screw_head_height"])
    z["disc1"] = (z["motor_screw_head"][1] + g, z["motor_screw_head"][1] + g + d["thickness"])
    # 두 원판은 같은 부품 — 6801 을 둘 다 원판 윗면과 같은 높이로(평평한 판 위에서 누름) 넣는다 · 아랫면 쪽은 1.0 들어감
    z["disc_bearing1"] = (z["disc1"][1] - bw1, z["disc1"][1])
    z["cam_hub"] = (m["pilot_height"] + P["gauge"]["thickness"], z["disc_bearing1"][0])         # 허브 밑 = 게이지 높이 · 윗면 = 6801 #1 속 고리 밑
    z["lobe1"] = (z["disc_bearing1"][0], z["disc_bearing1"][1])
    z["cam_lower"] = (z["cam_hub"][0], z["lobe1"][1])
    z["disc2"] = (z["disc1"][1] + g, z["disc1"][1] + g + d["thickness"])
    z["disc_bearing2"] = (z["disc2"][1] - bw1, z["disc2"][1])                                 # 원판 2 윗면과 같은 높이(원판 1 과 같게)
    z["cam_spacer"] = (z["lobe1"][1], z["disc_bearing2"][0])                                  # 두 6801 속 고리 사이(위 편심 축의 밑)
    z["lobe2"] = (z["disc_bearing2"][0], z["disc_bearing2"][1])
    z["washer"] = (z["disc_bearing2"][1], z["disc_bearing2"][1] + P["washer"]["thickness"])  # 6801 #2 속 고리 ↔ 6800 속 고리
    z["joint"] = z["washer"][1]                                                               # 아래 하우징 윗면 = 덮개 밑 = 캐리어 판 밑
    z["carrier_plate"] = (z["joint"], z["joint"] + P["carrier"]["plate_thickness"])
    z["shaft_bearing"] = (z["joint"], z["joint"] + bw0)                                       # 6800(캐리어 판 밑에서 들어간 자리)
    z["seat_relief"] = (z["shaft_bearing"][1], z["shaft_bearing"][1] + P["carrier"]["seat_relief_depth"])
    z["journal"] = (z["lobe2"][1], z["shaft_bearing"][1])
    z["cam_upper"] = (z["cam_spacer"][0], z["journal"][1])                                    # 간격 고리 + 편심 2 + 저널
    z["cam_bore"] = (z["cam_hub"][0], z["cam_upper"][1])                                      # D 구멍 — 두 편심 축을 관통
    z["ring_pin_hole_base"] = (mm, z["joint"])                                               # 바닥 아래 재료 = 최소 재료
    z["ring_pin"] = (mm, mm + P["ring"]["pin_length"])
    z["ring_pin_hole_cap"] = (z["joint"], z["ring_pin"][1] + 0.5)
    z["output_bearing"] = (z["ring_pin_hole_cap"][1] + mm, z["ring_pin_hole_cap"][1] + mm + bwo)
    z["collar"] = (z["carrier_plate"][1], z["output_bearing"][0])                             # 6808 속 고리 밑을 받침
    z["cap_lip"] = (z["carrier_plate"][1] + 0.5, z["output_bearing"][0])                      # 6808 바깥 고리 밑 — 캐리어 판 윗면에서 0.5 띄움
    z["carrier_hub"] = (z["collar"][1], z["output_bearing"][1])
    z["cap"] = (z["joint"], z["output_bearing"][1])
    z["retainer"] = (z["cap"][1], z["cap"][1] + P["housing"]["retainer_thickness"])           # 6808 바깥 고리 위
    z["flange"] = (z["carrier_hub"][1], z["carrier_hub"][1] + P["carrier"]["flange_thickness"])   # 6808 속 고리 위
    z["output_face"] = z["flange"][1]
    z["output_pin"] = (z["carrier_plate"][1] - P["output_pins"]["length"], z["carrier_plate"][1])
    z["motor_shaft"] = (0.0, m["shaft_length"])
    return z


def ring_sections(P):
    """베어링 고리 단면(가정): d + f_min(D − d) ≤ 안 고리 바깥지름 ≤ d + f(D − d) · D − f(D − d) ≤ 바깥 고리 안지름 ≤ D − f_min(D − d).
    다른 고리를 피하는 판정은 넓은 쪽(f) · 제 고리에 꼭 닿는 판정은 어느 베어링에나 있는 띠(f_min)로 한다(MP6 L4 R1 F5)."""
    f, fmin = P["bearings"]["ring_section_factor"], P["bearings"]["ring_section_min_factor"]
    out = {}
    for key in ("disc", "output", "shaft_end"):
        b = P["bearings"][key]
        w = b["od"] - b["id"]
        out[key] = {"inner_ring_od_max": b["id"] + f * w, "outer_ring_id_min": b["od"] - f * w,
                    "inner_ring_od_min": b["id"] + fmin * w, "outer_ring_id_max": b["od"] - fmin * w}
    return out


def radii(P):
    """반지름(mm) — 형상 생성기와 검사가 같이 쓴다."""
    f, B, op, E = P["fits"], P["bearings"], P["output_pins"], P["eccentricity"]
    rs = ring_sections(P)
    r = {"ring": P["ring"]["pin_circle_radius"], "pin_hole": f["pin_press_hole_dia"] / 2, "pin_slip_hole": f["pin_slip_hole_dia"] / 2,
         "outer": P["housing"]["outer_dia"] / 2,
         "pilot_hole": f["pilot_hole_dia"] / 2, "plate": P["carrier"]["plate_dia"] / 2}
    r["cap_bore"] = r["plate"] + 1.0
    r["seat_output"] = (B["output"]["od"] + f["bearing_seat_extra"]) / 2
    r["disc_bore"] = (B["disc"]["od"] + f["bearing_seat_extra"]) / 2
    r["shaft_seat"] = (B["shaft_end"]["od"] + f["bearing_seat_extra"]) / 2
    r["hub"] = (B["output"]["id"] + f["bearing_bore_extra"]) / 2           # 캐리어 허브 = 6808 속 고리 안
    r["lobe"] = (B["disc"]["id"] + f["bearing_bore_extra"]) / 2            # 편심 = 6801 속 고리 안
    r["journal"] = (B["shaft_end"]["id"] + f["bearing_bore_extra"]) / 2   # 저널 = 6800 속 고리 안
    r["inner_shoulder_output"] = P["carrier"]["shoulder_dia"] / 2         # 캐리어 턱 · 출력 플랜지(6808 속 고리)
    r["outer_shoulder_output"] = P["housing"]["outer_ring_shoulder_dia"] / 2   # 덮개 턱 · 누름 고리(6808 바깥 고리) — 안쪽 반지름
    r["cam_shoulder"] = P["cam"]["shoulder_dia"] / 2                      # 허브 · 간격 고리(6801 속 고리)
    r["seat_relief"] = (rs["shaft_end"]["inner_ring_od_max"] / 2 + rs["shaft_end"]["outer_ring_id_min"] / 2) / 2   # 6800 자리 위 오목
    r["washer_in"] = r["journal"] + f["washer_bore_clearance"]
    r["washer_out"] = P["washer"]["od"] / 2
    r["retainer_screw"] = (r["seat_output"] + r["outer"]) / 2
    r["retainer_out"] = r["retainer_screw"] + f["m3_clearance_dia"] / 2 + P["min_material"]
    r["cap_screw"] = P["housing"]["cap_screw_radius"]
    r["out_hole"] = op["dia"] / 2 + E + f["output_hole_clearance"]
    r["motor_bolt"] = math.hypot(P["motor"]["bolt_square"] / 2, P["motor"]["bolt_square"] / 2)
    r["output_insert"] = P["carrier"]["output_insert_radius"]
    return r


# ---------------- 윤곽 ----------------
def profile_xy(t, N, R, rr, E):
    psi = np.arctan2(np.sin((1 - N) * t), R / (E * N) - np.cos((1 - N) * t))
    x = R * np.cos(t) - rr * np.cos(t + psi) - E * np.cos(N * t)
    y = -R * np.sin(t) + rr * np.sin(t + psi) + E * np.sin(N * t)
    return np.column_stack([x, y])


def make_profile(N, R, rr, E, err_max):
    """현 오차(곡선의 구간 가운데 점 ↔ 그 구간 선분)의 최댓값이 err_max 이하가 될 때까지 점 수를 두 배로."""
    n = 27 * 16
    while True:
        t = np.linspace(0, 2 * np.pi, n, endpoint=False)
        pts = profile_xy(t, N, R, rr, E)
        mid = profile_xy(t + np.pi / n, N, R, rr, E)
        a, b = pts, np.roll(pts, -1, axis=0)
        ab = b - a
        u = np.clip(np.einsum("ij,ij->i", mid - a, ab) / np.einsum("ij,ij->i", ab, ab), 0, 1)
        err = float(np.max(np.linalg.norm(mid - (a + ab * u[:, None]), axis=1)))
        if err <= err_max:
            return pts, n, err
        n *= 2


def profile_for(P):
    """parameters 로 원판 윤곽(원판 좌표) — 형상 생성기도 이 함수로 같은 점을 얻는다."""
    ring = P["ring"]
    return make_profile(ring["pins"], ring["pin_circle_radius"], ring["pin_dia"] / 2 + P["fits"]["profile_clearance"], P["eccentricity"],
                        P["checks"]["profile_chord_error_max"])


def curvature_radii(N, R, rr, E, n=200000):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    h = 2 * np.pi / n
    p0, p1, p2 = profile_xy(t - h, N, R, rr, E), profile_xy(t, N, R, rr, E), profile_xy(t + h, N, R, rr, E)
    d1 = (p2 - p0) / (2 * h)
    d2 = (p2 - 2 * p1 + p0) / h ** 2
    k = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.linalg.norm(d1, axis=1) ** 3
    # 곡선이 도는 방향(넓이 부호)에 맞춰 부호를 바로잡는다 — 양수 = 바깥으로 볼록(로브 끝) · 음수 = 오목(골 — 핀이 앉는 곳)
    area2 = float(np.sum(p1[:, 0] * np.roll(p1[:, 1], -1) - np.roll(p1[:, 0], -1) * p1[:, 1]))
    k = k * (1.0 if area2 > 0 else -1.0)
    return float(np.min(1 / k[k > 0])) if np.any(k > 0) else None, float(np.min(1 / -k[k < 0])) if np.any(k < 0) else None


def rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def disc_pose(P, k, theta):
    """원판 k(1 · 2)의 중심 · 돌림(원판 좌표 → 세계). 둘째 = 같은 부품을 자기 중심에서 180° 돌려 끼움 · 편심 반대."""
    E = P["eccentricity"]
    lobes = P["ring"]["pins"] - 1
    sign, extra = (1.0, 0.0) if k == 1 else (-1.0, math.radians(P["disc"]["second_disc_phase_deg"]))
    return np.array([sign * E * math.cos(theta), sign * E * math.sin(theta)]), -theta / lobes + extra


def ring_contacts(P, r):
    """턱 · 고리마다: 닿아야 할 고리(같은 속도)와 겹치고, 다른 고리(다른 속도)에는 닿지 않는가. 반지름은 베어링 중심 기준(편심이면 그만큼 넓힘)."""
    rs, E = ring_sections(P), P["eccentricity"]
    B = P["bearings"]
    rows = []

    def row(name, key, ring, r_in, r_out, ecc=0.0):
        """턱이 베어링 중심에서 [r_in − ecc, r_out + ecc] 를 덮는다고 보고(편심 = 가장 나쁜 쪽) 판정."""
        d2, D2 = B[key]["id"] / 2, B[key]["od"] / 2
        inner = (d2, rs[key]["inner_ring_od_max"] / 2)             # 안 고리가 있을 수 있는 가장 넓은 띠(다른 고리 피하기)
        outer = (rs[key]["outer_ring_id_min"] / 2, D2)
        inner_sure = (d2, rs[key]["inner_ring_od_min"] / 2)        # 안 고리가 꼭 있는 띠(제 고리에 닿기)
        outer_sure = (rs[key]["outer_ring_id_max"] / 2, D2)
        lo, hi = max(r_in - ecc, 0.0), r_out + ecc
        lo_c, hi_c = r_in + ecc, max(r_out - ecc, 0.0)        # 어느 돌림에서도 꼭 덮는 띠
        sure = inner_sure if ring == "inner" else outer_sure
        overlap = min(hi_c, sure[1]) - max(lo_c, sure[0])
        touches = overlap > 0
        if ring == "inner":
            clear = hi < outer[0]
            margin = outer[0] - hi
        else:
            clear = lo > inner[1]
            margin = lo - inner[1]
        rows.append({"shoulder": name, "bearing": B[key]["model"], "ring": ring, "covers_mm": [round(lo, 3), round(hi, 3)],
                     "covers_surely_mm": [round(lo_c, 3), round(hi_c, 3)], "own_ring_sure_band_mm": [round(sure[0], 3), round(sure[1], 3)],
                     "sure_overlap_mm": round(overlap, 3), "touches_its_ring": bool(touches), "clear_of_other_ring": bool(clear),
                     "margin_mm": round(margin, 3), "ok": bool(touches and clear)})

    row("cam hub top (under 6801 #1 inner)", "disc", "inner", 0.0, r["cam_shoulder"], E)
    row("cam spacer bottom (over 6801 #1 inner)", "disc", "inner", 0.0, r["cam_shoulder"], E)
    row("cam spacer top (under 6801 #2 inner)", "disc", "inner", 0.0, r["cam_shoulder"], E)
    row("washer bottom (over 6801 #2 inner)", "disc", "inner", r["washer_in"], r["washer_out"], E)
    row("washer top (under 6800 inner)", "shaft_end", "inner", r["washer_in"], r["washer_out"])
    row("carrier seat ledge (over 6800 outer)", "shaft_end", "outer", r["seat_relief"], r["shaft_seat"])
    row("carrier collar (under 6808 inner)", "output", "inner", r["hub"], r["inner_shoulder_output"])
    row("output flange (over 6808 inner)", "output", "inner", 0.0, r["inner_shoulder_output"])
    row("cap lip (under 6808 outer)", "output", "outer", r["outer_shoulder_output"], r["seat_output"])
    row("retainer (over 6808 outer)", "output", "outer", r["outer_shoulder_output"], r["retainer_out"])
    return rows


DEFAULT_REPO = next((q for q in HERE.parents if (q / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    a = ap.parse_args()
    out = compute(a.params, a.repo)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    kin = {k: v for k, v in out["kinematics"].items() if k in ("disc1", "disc2")}
    print("profile", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out["profile"].items() if k != "note"})
    print("kinematics pass", out["kinematics"]["pass"], {k: round(float(v["ring_pin_gap_guaranteed_min"]), 4) for k, v in kin.items()},
          {k: round(float(v["output_pin_gap_guaranteed_min"]), 4) for k, v in kin.items()})
    print("walls_pass", out["walls_pass"], {k: round(v["mm"], 3) for k, v in out["walls"].items() if not v["ok"]})
    print("gaps_pass", out["gaps_pass"], {k: round(v["mm"], 3) for k, v in out["gaps"].items() if not v["ok"]})
    print("ring_contacts_pass", out["ring_contacts_pass"], [c["shoulder"] for c in out["ring_contacts"] if not c["ok"]])
    print("screws", {k: (v["length_mm"], round(v["engagement_mm"], 2) if v["engagement_mm"] is not None else None) for k, v in out["screws"].items()})


def compute(params_path, repo):
    """parameters 파일 → 산출 사전(cycloid.json 의 내용). 검사 묶음도 이 함수로 다시 계산해 저장본과 견준다(MP6 L4 R1 F3)."""
    P = load_params(params_path)
    ring, disc, op, fits, B = P["ring"], P["disc"], P["output_pins"], P["fits"], P["bearings"]
    N, R, E = ring["pins"], ring["pin_circle_radius"], P["eccentricity"]
    Rr, C, lobes, mm = ring["pin_dia"] / 2, fits["profile_clearance"], N - 1, P["min_material"]
    z, r = stack(P), radii(P)
    out = {"ratio": {"pins": N, "lobes": lobes, "output_per_input_nominal": -1 / lobes,
                     "note": "nominal - the profile and output-hole clearances give backlash, so the real output lags this"},
           "lambda": E * N / R, "stack_mm": z, "radii_mm": r, "ring_sections_assumed": ring_sections(P),
           "ring_section_factors": {"min": B["ring_section_min_factor"], "max": B["ring_section_factor"]}}

    # ---- 1. 윤곽 ----
    pts, n_pts, chord_err = profile_for(P)
    poly = Polygon(pts)
    rad = np.hypot(*pts.T)
    tip_r, valley_r = curvature_radii(N, R, Rr + C, E)
    out["profile"] = {"points": n_pts, "chord_error_mm": chord_err, "valid": bool(poly.is_valid), "simple": bool(poly.exterior.is_simple),
                      "radius_min": float(rad.min()), "radius_max": float(rad.max()), "lobe_tip_min_curvature_radius": tip_r,
                      "valley_min_curvature_radius": valley_r, "valley_vs_pin_plus_clearance": valley_r - (Rr + C), "area_mm2": float(poly.area),
                      "half_turn_hausdorff_mm": float(poly.hausdorff_distance(Polygon(-pts))),
                      "note": "the CAD extrudes this polygon, so the polygon itself is what the kinematic check measures; half_turn_hausdorff > 0 shows the "
                              "27-lobe outline is not 180-deg symmetric (the second disc's 180-deg turn is the needed half-lobe shift)"}

    # ---- 2. 기구학 ----
    pin_ang = np.radians(ring["pin_phase_deg"]) + 2 * np.pi * np.arange(N) / N
    ring_pins = np.column_stack([R * np.cos(pin_ang), R * np.sin(pin_ang)])
    M, Ro, rop = op["count"], op["radius"], op["dia"] / 2
    out_ang = np.radians(op["phase_deg"]) + 2 * np.pi * np.arange(M) / M
    hole_local = np.column_stack([Ro * np.cos(out_ang), Ro * np.sin(out_ang)])     # 원판 좌표의 구멍 자리(두 원판 같은 부품)
    ext = poly.exterior
    steps = P["checks"]["kinematic_steps_per_disc_turn"]
    dth = 2 * np.pi * lobes / steps
    move_ring = E * dth + rad.max() * dth / lobes          # 표본 사이 원판 점이 고정 핀에 대해 움직이는 거리 상한
    move_out = E * dth                                     # 출력 핀이 원판 구멍에 대해 움직이는 거리 상한(둘 다 −θ/27 로 돎 — 편심만 남음)
    kin = {}
    for k in (1, 2):
        ring_min, out_min, out_max = [], [], []
        for th in np.linspace(0, 2 * np.pi * lobes, steps, endpoint=False):
            c, a_d = disc_pose(P, k, th)
            Rm = rot(-a_d)
            loc = (Rm @ (ring_pins - c).T).T
            dist = shapely.distance(ext, shapely.points(loc))
            inside = shapely.contains_xy(poly, loc[:, 0], loc[:, 1])
            ring_min.append(float((np.where(inside, -dist, dist) - Rr).min()))
            pw = (rot(-th / lobes) @ hole_local.T).T                                 # 출력 핀(캐리어 = −θ/27 · θ = 0 에서 원판 1 구멍과 같은 각)
            ploc = (Rm @ (pw - c).T).T
            dd = np.linalg.norm(ploc[:, None, :] - hole_local[None, :, :], axis=2).min(axis=1)
            g = r["out_hole"] - dd - rop
            out_min.append(float(g.min()))
            out_max.append(float(g.max()))
        kin[f"disc{k}"] = {"ring_pin_gap_sampled_min": min(ring_min), "ring_pin_gap_sampled_max_of_min": max(ring_min),
                           "ring_pin_gap_guaranteed_min": min(ring_min) - move_ring,
                           "output_pin_gap_sampled_min": min(out_min), "output_pin_gap_sampled_max": max(out_max),
                           "output_pin_gap_guaranteed_min": min(out_min) - move_out}
    out["kinematics"] = {"steps_per_disc_turn": steps, "input_step_deg": math.degrees(dth), "between_samples_bound_ring_mm": float(move_ring),
                         "between_samples_bound_output_mm": float(move_out), **kin,
                         "pass": all(v["ring_pin_gap_guaranteed_min"] > 0 and v["output_pin_gap_guaranteed_min"] > 0 for v in kin.values())}

    # ---- 3. 벽(≥ 최소 재료) · 틈(> 0) · 고리 닿음 ----
    pin_edge_out = r["ring"] + r["pin_hole"]
    ins, m3 = fits["insert_hole_dia"] / 2, fits["m3_clearance_dia"] / 2
    hb = P["motor"]["bolt_square"] / 2
    bolts = np.array([[sx * hb, sy * hb] for sx in (-1, 1) for sy in (-1, 1)])
    head_r = P["motor"]["screw_head_dia"] / 2
    shaft_r = P["motor"]["shaft_dia"] / 2
    bore_up = shaft_r + (fits["d_bore_extra"] + fits["cam_upper_bore_extra"]) / 2   # 위 편심 축의 D 구멍 반지름(아래 축보다 크다 — 벽은 이것으로)
    circle = np.column_stack([np.cos(np.linspace(0, 2 * np.pi, 721)), np.sin(np.linspace(0, 2 * np.pi, 721))])
    walls = {
        "disc_bore_to_output_hole": (Ro - r["out_hole"]) - r["disc_bore"],
        "output_hole_to_profile": float(min(shapely.distance(ext, LineString(c + r["out_hole"] * circle)) for c in hole_local)),
        "output_hole_to_hole": 2 * Ro * math.sin(math.pi / M) - 2 * r["out_hole"],
        "ring_pin_hole_to_hole": 2 * R * math.sin(math.pi / N) - 2 * r["pin_hole"],
        "cap_slip_pin_hole_to_hole": 2 * R * math.sin(math.pi / N) - 2 * r["pin_slip_hole"],
        "cam_lobe_thin_side": r["lobe"] - E - bore_up,
        "cam_journal_wall": r["journal"] - bore_up,
        "cam_hub_and_spacer_wall": r["cam_shoulder"] - bore_up,
        "cam_spacer_axial": z["cam_spacer"][1] - z["cam_spacer"][0],          # 간격 고리 테두리의 축 두께(MP6 L4 R1 F4)
        "washer_radial_wall": r["washer_out"] - r["washer_in"],
        "washer_thinnest_variant": min(P["washer"]["variants"]),
        "carrier_output_pin_to_plate_edge": r["plate"] - (Ro + r["pin_hole"]),
        "carrier_shaft_seat_to_output_pin": (Ro - r["pin_hole"]) - r["shaft_seat"],
        "carrier_seat_relief_ledge": r["shaft_seat"] - r["seat_relief"],
        "carrier_output_insert_to_hub_edge": r["hub"] - (r["output_insert"] + ins),
        "carrier_output_insert_to_plate_holes_axial": (z["carrier_hub"][1] - fits["insert_depth"]) - z["carrier_plate"][1],
        "carrier_relief_roof_to_hub_top": z["carrier_hub"][1] - fits["insert_depth"] - z["seat_relief"][1],
        "carrier_collar_radial": r["inner_shoulder_output"] - r["hub"],
        "flange_screw_hole_to_edge": r["inner_shoulder_output"] - (r["output_insert"] + m3),
        "base_floor_under_pin_hole": z["ring_pin_hole_base"][0],
        "cap_skin_bore_to_slip_pin_hole": (r["ring"] - r["pin_slip_hole"]) - r["cap_bore"],
        "cap_floor_pin_hole_to_bearing_seat": z["output_bearing"][0] - z["ring_pin_hole_cap"][1],
        "cap_lip_radial": r["seat_output"] - r["outer_shoulder_output"],
        "cap_lip_axial": z["cap_lip"][1] - z["cap_lip"][0],
        "cap_screw_insert_floor_to_cap_top": z["cap"][1] - (z["joint"] + P["housing"]["cap_insert_depth"]),
        "cap_screw_hole_to_slip_pin_hole": (r["cap_screw"] - ins) - (r["ring"] + r["pin_slip_hole"]),
        "cap_screw_hole_to_outer": r["outer"] - (r["cap_screw"] + ins),
        "base_cap_screw_hole_to_pin_hole": (r["cap_screw"] - m3) - pin_edge_out,
        "retainer_insert_to_bearing_seat": (r["retainer_screw"] - ins) - r["seat_output"],
        "retainer_insert_to_outer": r["outer"] - (r["retainer_screw"] + ins),
        "retainer_screw_hole_to_inner_edge": (r["retainer_screw"] - m3) - r["outer_shoulder_output"],
        "retainer_screw_hole_to_outer_edge": r["retainer_out"] - (r["retainer_screw"] + m3),
        "motor_bolt_hole_to_pilot_hole": (r["motor_bolt"] - m3) - r["pilot_hole"],
        "motor_bolt_hole_to_pin_hole_actual": float(np.min(np.linalg.norm(bolts[:, None] - ring_pins[None], axis=2))) - m3 - r["pin_hole"],
    }
    out["walls"] = {k: {"mm": float(v), "ok": v >= mm - WALL_EPS} for k, v in walls.items()}   # 쌓임 덧셈의 부동소수 오차(1.9999999999999982 등)만 허용
    gaps = {   # 움직이는 쪽 ↔ 고정 쪽(또는 다른 속도) — 회전체 쌍은 모든 각에서 같다 · 원판 · 편심은 2 가 맡는다
        "disc_tip_to_housing_bore_radial": R - (float(rad.max()) + E),
        "disc1_to_motor_screw_head_axial": z["disc1"][0] - z["motor_screw_head"][1],
        # 아래 편심 축이 게이지 높이를 다 잃고 파일럿까지 밀려도 원판 1 이 나사 머리에 닿지 않는가(MP6 L4 R1 F1)
        "disc1_to_motor_screw_head_if_lower_cam_on_pilot_axial": (z["disc1"][0] - z["motor_screw_head"][1]) - (z["cam_hub"][0] - z["motor_pilot_top"]),
        "disc1_to_disc2_axial": z["disc2"][0] - z["disc1"][1],
        "disc2_and_its_bearing_to_carrier_plate_axial": z["carrier_plate"][0] - max(z["disc2"][1], z["disc_bearing2"][1]),
        "carrier_plate_to_cap_bore_radial": r["cap_bore"] - r["plate"],
        "carrier_collar_to_cap_lip_radial": r["outer_shoulder_output"] - r["inner_shoulder_output"],
        "carrier_plate_top_to_cap_lip_axial": z["cap_lip"][0] - z["carrier_plate"][1],
        "flange_to_retainer_radial": r["outer_shoulder_output"] - r["inner_shoulder_output"],
        "seat_relief_over_6800_inner_axial": z["seat_relief"][1] - z["shaft_bearing"][1],
        "journal_top_to_relief_roof_axial": z["seat_relief"][1] - z["journal"][1],
        "washer_to_carrier_seat_wall_radial": r["shaft_seat"] - r["washer_out"],
        "washer_to_disc2_bore_radial_with_eccentricity": r["disc_bore"] - E - r["washer_out"],
        "output_pin_bottom_to_base_top_axial": z["output_pin"][0] - z["base_top"],
        "cam_hub_to_motor_pilot_axial": z["cam_hub"][0] - z["motor_pilot_top"],
        "cam_hub_to_pilot_hole_radial": r["pilot_hole"] - r["cam_shoulder"],
        "cam_shoulder_to_disc_bores_radial_with_eccentricity": r["disc_bore"] - E - r["cam_shoulder"],
        "output_pin_to_cam_radial": (Ro - rop) - r["cam_shoulder"],
        "motor_shaft_tip_below_cam_bore_top": z["cam_bore"][1] - z["motor_shaft"][1],
        "motor_screw_head_to_ring_pin_actual": float(np.min(np.linalg.norm(bolts[:, None] - ring_pins[None], axis=2))) - head_r - Rr,
        "motor_screw_head_to_output_pin_radial": (r["motor_bolt"] - head_r) - (Ro + rop),
        "motor_screw_head_to_cam_hub_radial": (r["motor_bolt"] - head_r) - r["cam_shoulder"],
    }
    out["gaps"] = {k: {"mm": float(v), "ok": v > 0} for k, v in gaps.items()}
    # 나사 길이: 표준 길이 중 물림 ≥ 하한이면서 끝이 막힌 구멍 바닥에서 0.5 이상 떨어지는 가장 긴 것(쌓임 · 구멍 깊이에서)
    avail, hs = P["housing"]["screw_lengths_available"], P["housing"]
    screws = {}

    def pick(name, start, hole_from, hole_floor, min_engage, note):
        """start = 나사 머리 밑면 z · 나사는 hole_from(물림 시작 면) 쪽으로 · hole_floor = 막힌 구멍 바닥 z(머리에서 먼 쪽)."""
        sign = 1.0 if hole_floor > start else -1.0
        ok = [L for L in avail if abs((start + sign * L) - hole_from) >= min_engage and sign * (hole_floor - (start + sign * L)) >= 0.5
              and sign * ((start + sign * L) - hole_from) > 0]
        L = max(ok) if ok else None
        screws[name] = {"length_mm": L, "engagement_mm": None if L is None else abs(start + sign * L - hole_from),
                        "tip_to_hole_floor_mm": None if L is None else sign * (hole_floor - (start + sign * L)), "note": note}

    pick("motor", z["base_top"], 0.0, -P["motor"]["screw_thread_depth"], 2.5, "M3 button head on the base top into the motor flange (thread depth = ASSUMPTION)")
    pick("cap", 0.0, z["joint"], z["joint"] + hs["cap_insert_depth"], 4.0, "M3 from under the base into the cap inserts")
    pick("retainer", z["retainer"][1], z["cap"][1], z["cap"][1] - fits["insert_depth"], 3.0, "M3 through the retainer into the cap top inserts")
    pick("flange", z["flange"][1], z["carrier_hub"][1], z["carrier_hub"][1] - fits["insert_depth"], 3.0,
         "M3 through the output flange into the carrier hub inserts (longer if a test load or arm is clamped on top)")
    out["screws"] = screws
    out["screws_pass"] = all(v["length_mm"] is not None for v in screws.values())
    out["ring_contacts"] = ring_contacts(P, r)
    out["walls_pass"] = all(v["ok"] for v in out["walls"].values())
    out["gaps_pass"] = all(v["ok"] for v in out["gaps"].values())
    out["ring_contacts_pass"] = all(v["ok"] for v in out["ring_contacts"])
    out["axial_location"] = {
        "cam_lower": "D-bore press fit on the motor alone (before the motor goes on the base): GAUGE fork on the pilot, press the cam down onto it, remove the gauge",
        "disc_bearing1": "inner ring clamped between the cam hub top and the cam spacer bottom (both input speed); outer ring pressed in disc 1 flush with its top face",
        "cam_upper": "slip fit on the D shaft (fits.cam_upper_bore_extra) - lowered until the spacer bottom rests on the 6801 #1 inner ring; held down by the washer / 6800 / carrier stack",
        "disc_bearing2": "inner ring between the cam spacer top and the washer (both input speed); outer ring pressed in disc 2 flush with its top",
        "washer": "on the journal between the 6801 #2 inner ring and the 6800 inner ring; printed 2.0 / 2.2 / 2.4 to take up the stack tolerance",
        "shaft_bearing": "outer ring pressed in the carrier seat against the ledge (relief above the inner ring); inner ring on the journal",
        "carrier": "6808 inner ring clamped between the carrier collar and the output flange; 6808 outer ring between the cap lip and the retainer",
        "inner_ring_fits": "every inner ring on a printed shaft (6801 on both lobes, 6800 on the journal) is a hand push fit - never pressed, because the "
                           "force would go down through the stack into the lower cam's press fit (MP6 L4 R1 F1)",
        "note": "the press fits and the stack tolerance are placeholders until the fit strip is judged; the hand test sheet records rubbing",
    }
    # 조립 중 잴 수 있는 기준(README 가 쓴다): 와셔 윗면 = 바닥판 벽 윗면 = 덮개 · 캐리어 판 밑(z joint) — 곧은 자로 견준다
    out["assembly_datum"] = {"washer_top_minus_base_wall_top_mm": z["washer"][1] - z["joint"],
                             "lower_cam_hub_above_pilot_mm": z["cam_hub"][0] - z["motor_pilot_top"],
                             "ring_pin_into_cap_mm": z["ring_pin"][1] - z["joint"],
                             "ring_pin_pressed_in_base_mm": z["ring_pin_hole_base"][1] - z["ring_pin"][0]}

    # ---- 4. 하중(어림) ----
    tq = {"note": ("rough only: output torque at the output-pin circle shared by 3 pins (or 1 pin when backlash lets one carry); pin root bending = "
                   "force x arm from the carrier plate underside to a disc mid-plane; eccentric reaction scale = T / (27 E) (ideal static scale, not "
                   "the motor-bearing load); the two discs' opposite reactions at their mid-plane spacing give a couple that closes through the cam, "
                   "the motor shaft and the 6800 - not computed. The motor-side margin is not an acceptance of the shaft, pins or bearings")}
    loads_path = Path(repo) / ".dev" / "mp5-review-evidence" / "loads.json"
    inp_path = Path(repo) / "src" / "cad" / "review-mp5" / "inputs.json"
    L = json.loads(loads_path.read_text(encoding="utf-8"))
    I = json.loads(inp_path.read_text(encoding="utf-8"))
    eta, usable = I["efficiency_by_type"]["cycloid_printed"]["value"], I["usable_torque_fraction"]["value"]
    for sname, sres in L["results"].items():
        jr = sres["payloads"]["0.5"]
        need = max(jr["J4"]["required_Nm"], jr["J5"]["required_Nm"])
        mot = jr["J4"]["motor"]
        have = I["motors"][mot]["holding_Nm"] * usable * eta * lobes
        tq[sname.split(" ")[0]] = {"wrist_motor": mot, "wrist_need_Nm": need, "motor_side_available_Nm": have, "motor_side_margin": have / need - 1,
                                   "shoulder_J2_need_Nm_not_this_size": jr["J2"]["required_Nm"]}
    arm1 = z["carrier_plate"][0] - sum(z["disc1"]) / 2
    arm2 = z["carrier_plate"][0] - sum(z["disc2"]) / 2
    spacing = sum(z["disc2"]) / 2 - sum(z["disc1"]) / 2
    # 출력 핀이 원판마다 축 방향으로 걸치는 길이(MP6 L4 R2 F3 — 원판 1 은 핀 밑끝이 원판 밑면보다 위라 두께 전부가 아니다) · 면압은 짧은 쪽으로
    engage = {k: min(z["output_pin"][1], z[k][1]) - max(z["output_pin"][0], z[k][0]) for k in ("disc1", "disc2")}
    t_w = max(v["wrist_need_Nm"] for v in tq.values() if isinstance(v, dict))
    t_s = max(v["shoulder_J2_need_Nm_not_this_size"] for v in tq.values() if isinstance(v, dict))
    for name, T in (("wrist_max", t_w), ("shoulder_J2_max_not_this_size", t_s)):
        f3, f1 = T / (Ro / 1000 * 3), T / (Ro / 1000)
        fe = T / (lobes * E / 1000)
        tq[name] = {"T_Nm": T, "output_pin_force_N_3pin": f3, "output_pin_force_N_1pin": f1,
                    "pla_pressure_MPa_3pin": f3 / (op["dia"] * min(engage.values())), "pla_pressure_MPa_1pin": f1 / (op["dia"] * min(engage.values())),
                    "pla_pressure_note": "contact length = the shorter output-pin engagement of the two discs (output_pin_engagement_mm)",
                    "pin_root_bending_Nm_3pin_disc1_arm": f3 * arm1 / 1000, "pin_root_bending_Nm_1pin_disc1_arm": f1 * arm1 / 1000,
                    "pin_root_bending_Nm_3pin_disc2_arm": f3 * arm2 / 1000, "eccentric_reaction_scale_N": fe,
                    "two_disc_couple_scale_Nm": fe * spacing / 1000}
    tq["arms_mm"] = {"carrier_underside_to_disc1_mid": arm1, "carrier_underside_to_disc2_mid": arm2, "disc_mid_spacing": spacing}
    tq["output_pin_engagement_mm"] = engage
    out["loads_rough"] = tq
    cal = P["fits"].get("calibration")
    out["fit_calibration"] = None if cal is None else {"material": cal["material"], "ledger": Path(cal["ledger"]).name,
                                                       "values": {k: P["fits"][k] for k in cal["values"]}, "values_sha256": cal["values_sha256"]}
    out["inputs_sha256"] = {pth.name: hashlib.sha256(pth.read_bytes()).hexdigest() for pth in (Path(params_path), loads_path, inp_path)}
    return out


if __name__ == "__main__":
    main()
