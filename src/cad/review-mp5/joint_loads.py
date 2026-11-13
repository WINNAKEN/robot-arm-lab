# -*- coding: utf-8 -*-
"""MP5 — 관절 부하 · 필요 감속비 검토(Mech-Sparring 방식: 숫자는 이 스크립트가 낸다 · 입력은 저장소 파일과 inputs.json 의 출처 · 가정).

하는 일(위에서 아래로 · 아래 코드가 권위):
1. 출력 설정(벽 · 채움 · 필라멘트 밀도)을 시험편의 출력 준비 3MF(`models/fit-coupons-v1/slicer/*.bambu.3mf` 의 `Metadata/project_settings.config`)에서
   읽고, 출력 질량 모형(껍데기 + 채움 — 벽 두께를 모든 면에)을 그 판의 슬라이서 추정과 견준다.
2. 질량: 관절 모듈의 출력 부품 = J2 분할 여섯 부품의 모형 질량을 기준으로, 다른 관절은 A2 외곽(모듈 + 링 + 덮개)의 모형 질량 비로 키우거나 줄인다 ·
   링크 몸체 = A2 몸체(`main-eval.json` — 속이 찬 외곽)의 모형 질량 · 모터 · 드라이버 · 감속기 금속 = inputs.json.
3. 자리: 팔을 수평으로 곧게 편 자세. 링크 몸체 · 롤 관절(J4 · J6) 모듈의 팔 방향 자리 = A2 몸체의 중심(`main-eval.json` · 표시 자세)을 v1
   `kinematics.json` 의 관절 원점 · 축에 투영한 값(모듈은 모형 질량으로 가중) · 옆 자리(피치 축 방향) = 같은 중심의 그 축 성분 · 모터 · 드라이버 =
   캔 안의 자리(v2 외장 식 — 캔이 뻗는 쪽은 모듈 외곽의 중심 부호).
4. 관절마다 필요 토크 = 안전율 × (중력 + 관성). 관성 = 점질량 Σ m r² + 요소마다 가장 큰 드럼 반지름 원판의 자기 관성(어림 가정 — 상한 아님 ·
   긴 관의 가로축 관성은 이보다 클 수 있다 · 민감도에서 반지름 2 배) · 모터 회전자 · 감속기 안 회전체의 반사 관성은 없음 ·
   J4 = J5 를 90° 꺾었을 때 J4 축에 수직인 두 방향(J5→J6 줄 · J5 축)의 1차 모멘트 합의 크기 · J1 = 뻗은 팔 + J2 모듈의 관성만 · J6 = 짐이
   축에서 비킨 거리(가정) + 플랜지 · 링 원판. 필요 감속비 = 필요 토크 / (유지 토크 × 쓸 수 있는 비율 × 감속기 효율) · 관절 속도 = 모터 속도 / 감속비.
5. 민감도: S2 · 짐 0.5 kg 의 J2 필요 감속비를 한 번에 하나씩 바꾼 입력으로.
5b. 후보 구동 판정: inputs.json 의 구동(감속비 · 효율)마다 시나리오 · 관절별로 필요 토크를 내는 가장 큰 짐.
6. 감속기 공간: J2 분할이 남긴 축 방향 공간과 후보의 가정 쌓임.
J2 출력 베어링(정적 · 근사): 팔 무게(반경 힘) · 팔 무게중심이 베어링 중심에서 J2 축 방향으로 비킨 거리의 기울임 · J1 가속의 기울임(α Σ m x²).
7. 입력 파일마다 sha256 · 문서(`docs/design/022-modeling-reducer-review.md`)가 줄 그대로 싣는 블록(`<!-- mp5-…:begin -->`).

사용: python joint_loads.py [--out <폴더>]   (기본 = .dev/mp5-review-evidence/)
산출: loads.json · loads.md — `check_doc_sync.py` 가 입력 해시 · 문서 블록 · 다시 계산한 결과를 대조한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])
V1 = ROOT / "models" / "armold-mks-concept-v1"
V2 = ROOT / "models" / "armold-mks-product-v2"
SPLIT = V2 / "j2-split"
COUPON = ROOT / "models" / "fit-coupons-v1"
EVAL = ROOT / ".dev" / "product-v2-evidence" / "build" / "main-eval.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / ".dev" / "mp5-review-evidence")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    read = {}

    def load_json(p):
        read[str(Path(p).relative_to(ROOT))] = sha(p)
        return json.loads(Path(p).read_text(encoding="utf-8"))

    inp = load_json(HERE / "inputs.json")
    g = inp["g_m_s2"]
    j6_off = inp["j6_payload_offset_from_axis_m"]["value"]
    r_self_base = inp["self_inertia_radius_m"]["value"]
    p1 = load_json(V1 / "parameters.json")
    kin = load_json(V1 / "kinematics.json")
    p2 = load_json(ROOT / "src" / "cad" / "armold-mks-product-v2" / "parameters.json")
    ev = load_json(EVAL)
    split = load_json(SPLIT / "split.json")
    report = load_json(COUPON / "slicer" / "print_prep_report.json")

    # ---- 1. 출력 설정 · 질량 모형 ----
    proj = next(COUPON.glob("slicer/*.bambu.3mf"))
    read[str(proj.relative_to(ROOT))] = sha(proj)
    cfg = json.loads(zipfile.ZipFile(proj).read("Metadata/project_settings.config").decode("utf-8"))
    pla = {"density_g_cm3": float(cfg["filament_density"][0]),
           "shell_mm": float(cfg["outer_wall_line_width"]) + float(cfg["inner_wall_line_width"]) * (int(cfg["wall_loops"]) - 1),
           "infill": float(str(cfg["sparse_infill_density"]).rstrip("%")) / 100.0,
           "source": f"{proj.name} project_settings: outer {cfg['outer_wall_line_width']} + inner {cfg['inner_wall_line_width']} x (wall_loops "
                     f"{cfg['wall_loops']} - 1) · infill {cfg['sparse_infill_density']} · filament_density {cfg['filament_density'][0]} · "
                     f"top {cfg['top_shell_thickness']} mm / bottom {cfg['bottom_shell_layers']} layers — the model applies the wall thickness to every face "
                     f"(ASSUMPTION for top/bottom)"}

    def shell_mass_g(area_mm2, volume_mm3, infill=None):
        f = pla["infill"] if infill is None else infill
        shell = min(area_mm2 * pla["shell_mm"], volume_mm3)
        return pla["density_g_cm3"] * (shell + (volume_mm3 - shell) * f) / 1000.0

    plate_path = COUPON / "fit-coupons-v1-plate.stl"
    read[str(plate_path.relative_to(ROOT))] = sha(plate_path)
    plate = trimesh.load(plate_path, force="mesh")
    model_g = shell_mass_g(float(plate.area), float(plate.volume))
    out = {"pla": pla, "mass_model_check": {"plate_area_mm2": float(plate.area), "plate_volume_mm3": float(plate.volume), "model_g": model_g,
                                            "slicer_g": report["estimate"]["filament_g"], "model_over_slicer": model_g / report["estimate"]["filament_g"],
                                            "note": "one plate only — not a bound on other parts"}}

    # ---- 2. 질량 ----
    body = {b["name"]: b for b in ev["bodies"]}
    parts = []
    for name in split["parts"]:
        pth = SPLIT / "parts" / f"{name}.stl"
        read[str(pth.relative_to(ROOT))] = sha(pth)
        m = trimesh.load(pth, force="mesh")
        parts.append((float(m.area), float(m.volume)))

    def j2_parts_g(infill=None):
        return sum(shell_mass_g(ar, vo, infill) for ar, vo in parts)

    def env_bodies(k):
        return [n for n in (f"J{k}_MODULE", f"J{k}_ACCENT_RING", f"J{k}_END_CAP") if n in body]

    def body_g(name, infill=None):
        b = body[name]
        return shell_mass_g(b["area_mm2"], b["volume_mm3"], infill)

    def module_print_g(k, infill=None):
        e = lambda kk: sum(body_g(n, infill) for n in env_bodies(kk))  # noqa: E731
        return j2_parts_g(infill) * e(k) / e(2)

    # ---- 3. 자리(J2 축에서 팔 방향 거리 m · 표시 자세의 A2 중심을 관절 원점 · 축에 투영) ----
    J = {j["name"]: j for j in kin["joints"]}
    O = {k: np.array(J[f"J{k}"]["origin_mm"]) / 1000 for k in range(1, 7)}
    AX = {k: np.array(J[f"J{k}"]["axis_world"], dtype=float) for k in range(1, 7)}
    u = {2: O[3] - O[2], 3: O[4] - O[3], 4: O[5] - O[4], 5: O[6] - O[5]}
    seg = {k: float(np.linalg.norm(v)) for k, v in u.items()}
    u = {k: v / np.linalg.norm(v) for k, v in u.items()}
    u[6] = u[5]
    x = {2: 0.0, 3: seg[2], 4: seg[2] + seg[3], 5: seg[2] + seg[3] + seg[4], 6: seg[2] + seg[3] + seg[4] + seg[5]}
    link_of_body = {f"LINK{k}_": k for k in range(2, 7)}

    def along(name):
        """A2 몸체 중심을 그 몸체가 속한 마디 줄(관절 k 에서 k+1 쪽)에 투영해 J2 로부터의 팔 방향 거리로."""
        c = np.array(body[name]["center_of_mass"]) / 1000
        k = next(v for p, v in link_of_body.items() if name.startswith(p))
        return x[k] + float(np.dot(c - O[k], u[k]))

    def module_along(k):
        """롤 관절 모듈(외곽 셋)의 모형 질량 가중 중심을 자기 축(= 팔 방향)에 투영."""
        ws = [(body_g(n), np.array(body[n]["center_of_mass"]) / 1000) for n in env_bodies(k)]
        c = sum(w * cc for w, cc in ws) / sum(w for w, _ in ws)
        return x[k] + float(np.dot(c - O[k], AX[k]))

    def module_lateral(k):
        """피치 관절 모듈 외곽의 가중 중심이 자기 축 방향으로 비킨 거리(m · 부호 있음)."""
        ws = [(body_g(n), np.array(body[n]["center_of_mass"]) / 1000) for n in env_bodies(k)]
        c = sum(w * cc for w, cc in ws) / sum(w for w, _ in ws)
        return float(np.dot(c - O[k], AX[k]))

    D = p1["reducer_depth_mm"] / 1000
    dd = p1["driver_depth_mm"] / 1000
    tool = p2["links"]["tool"]
    flange_face = x[6] + D / 2 + (tool["flange_t"] + tool["ring_t"]) / 1000
    out["positions_m"] = {"J3": x[3], "J4": x[4], "J5": x[5], "J6": x[6], "flange_face": flange_face,
                          "J4_module_print": module_along(4), "J6_module_print": module_along(6),
                          "J5_module_print_lateral": module_lateral(5),
                          **{n: along(n) for n in body if n.startswith("LINK") and not n.startswith("LINK1")}}

    motor_face = abs(split["interfaces"]["motor_face"]["z_mm"]) / 1000  # J2 분할: 모터 면 = 관절 중심에서 18 mm(뒷벽 아랫면)
    motor_driver_gap = 0.002  # J2 분할 참조 상자: 모터 −58..−18 · 드라이버 −78..−60 mm(build-commands.json) — 사이 2 mm

    def motor_offsets(ml):
        """캔 안 모터 · 드라이버 중심의 자기 축 방향 자리(m · 캔 쪽이 음) — J2 분할의 모터 면 · 참조 상자 간격을 모든 관절에 쓴다(가정).
        모터가 길어져도 캔 · 인쇄 질량은 A2(모터 40 mm)로 둔다 — 문서가 그 한계를 적는다."""
        return -(motor_face + ml / 2), -(motor_face + ml + motor_driver_gap + dd / 2)

    tube_len = p2["links"]["wrist2"]["tube_len"] / 1000

    def can_side(k):
        """피치 관절(J2 · J3 · J5)의 캔이 자기 축의 어느 쪽으로 뻗는가(+1 / -1) — 모듈 외곽 가중 중심의 부호."""
        return 1.0 if module_lateral(k) > 0 else -1.0

    def lateral(name):
        """링크 몸체가 피치 축 방향(곧게 편 기하 영점에서 J2 ∥ J3 ∥ J5 — v1 axis_parent_zero 가 모두 [0, 1, 0])으로 비킨 거리(m).
        링크2 · 3 = 자기 관절 원점에서 그 축 방향 · 링크4 ~ 6 = J5 원점에서 J5 축 방향(J4 · J5 원점은 그 평면 위)."""
        c = np.array(body[name]["center_of_mass"]) / 1000
        k = 2 if name.startswith("LINK2") else 3 if name.startswith("LINK3") else 5
        return float(np.dot(c - O[k], AX[k]))

    def pitch_group(k, motors, p, infill):
        """피치 관절 k 의 모듈 출력 부품 · 모터 · 드라이버 · 감속기 금속 — (이름, kg, x, y)."""
        mot = inp["motors"][motors[k]]
        mo, do = motor_offsets(mot["length_mm"] / 1000)
        side = can_side(k)
        xk = p.get("j3_motor_x", x[3]) if k == 3 else x[k]
        return [(f"J{k} module print", module_print_g(k, infill) / 1000, x[k], module_lateral(k)),
                (f"J{k} motor", mot["mass_kg"], xk, side * abs(mo)), (f"J{k} driver", p["driver_kg"], xk, side * abs(do)),
                (f"J{k} reducer metal", p["reducer_metal_kg"], x[k], 0.0)]

    def elements(motors, p):
        """J2 너머 팔의 요소 (이름, kg, 팔 방향 x, 피치 축 방향 옆 y) — 수평으로 곧게 편 자세."""
        mot = inp["motors"]
        infill = p.get("infill")
        e = [(n, body_g(n, infill) / 1000, along(n), lateral(n)) for n in ("LINK2_SHOULDER_HUB", "LINK2_UPPER_TUBE")]
        e += pitch_group(3, motors, p, infill)
        e += [(n, body_g(n, infill) / 1000, along(n), lateral(n)) for n in ("LINK3_ELBOW_HUB", "LINK3_FOREARM_TUBE")]
        for k in (4, 6):  # 롤 관절 — 모듈 · 모터 · 드라이버가 팔 줄 위(옆 0)에서 뒤로 뻗는다
            mo, do = motor_offsets(mot[motors[k]]["length_mm"] / 1000)
            e += [(f"J{k} module print", module_print_g(k, infill) / 1000, module_along(k), 0.0),
                  (f"J{k} motor", mot[motors[k]]["mass_kg"], x[k] + mo, 0.0), (f"J{k} driver", p["driver_kg"], x[k] + do, 0.0),
                  (f"J{k} reducer metal", p["reducer_metal_kg"], x[k], 0.0)]
        e += pitch_group(5, motors, p, infill)
        e += [(n, body_g(n, infill) / 1000, along(n), lateral(n))
              for n in ("LINK4_NECK", "LINK5_WRIST_HUB", "LINK5_WRIST_TUBE", "LINK6_TOOL_FLANGE", "LINK6_TOOL_RING")]
        # 출력 질량 배율(민감도 — 판 하나의 슬라이서/모형 비)
        ps = p.get("print_scale", 1.0)
        if ps != 1.0:
            e = [(n, m * ps if (n.startswith("LINK") or n.endswith("module print")) else m, xx, y) for n, m, xx, y in e]
        # 손목 J5→J6 길이 바꿈(민감도): J6 쪽을 당기고 손목 관은 짧아진 만큼 질량 · 중심을 줄인다(관은 J5 에서 시작 — 표시 자세 중심 = 관 길이의 반)
        dw = p.get("wrist_shift_m", 0.0)
        if not dw:
            return e
        moved = []
        for n, m, xx, y in e:
            if n == "LINK5_WRIST_TUBE":
                keep = max(0.0, tube_len - dw) / tube_len
                moved.append((n, m * keep, x[5] + (xx - x[5]) * keep, y))
            else:
                moved.append((n, m, xx - dw if xx > x[5] + 1e-9 else xx, y))
        return moved

    def link_of(name):
        """요소가 붙은 링크 번호 — 관절 j 는 링크 번호 ≥ j 인 요소를 돌린다. 「J{k} …」 묶음은 관절 k 의 고정 쪽(링크 k-1) · 짐 = 링크6."""
        if name == "payload":
            return 6
        if name.startswith("LINK"):
            return int(name[4])
        return int(name[1]) - 1

    def link1_bodies():
        """J1 이 돌리는 링크1 몸체 — (이름, kg, J1 축에서의 수평 거리 m)."""
        rows = []
        for n in (b for b in body if b.startswith("LINK1_")):
            c = np.array(body[n]["center_of_mass"]) / 1000 - O[1]
            rows.append((n, body_g(n) / 1000, float(np.linalg.norm(c - np.dot(c, AX[1]) * AX[1]))))
        return rows

    def ceil1(v):
        """필요 감속비의 표시 값 = 소수 첫째 자리로 올림(고를 감속비는 이 값 이상)."""
        return math.ceil(v * 10 - 1e-9) / 10

    sp_bearing = split["interfaces"]["output_bearing_seat"]
    y_bearing = (sp_bearing["z_from_mm"] + sp_bearing["z_to_mm"]) / 2 / 1000  # J2 분할 좌표 +Z = J2 축(출력 쪽) · 원점 = 관절 중심

    def loads(motors, payload, p):
        r_self = p.get("r_self", r_self_base)
        els = elements(motors, p) + [("payload", payload, flange_face + p["payload_offset_m"] - p.get("wrist_shift_m", 0.0), 0.0)]
        alpha, res = p["alpha"], {}
        # 피치 관절(J2 · J3 · J5): 수평으로 곧게 편 팔 · 관절이 돌리는 요소 · 점질량 관성 + 요소마다 원판 자기 관성(어림 가정 — 상한 아님)
        for jn, x0 in (("J2", 0.0), ("J3", x[3]), ("J5", x[5])):
            beyond = [(m, xx - x0) for n, m, xx, _y in els if link_of(n) >= int(jn[1])]
            res[jn] = {"gravity_Nm": g * sum(m * r for m, r in beyond),
                       "inertia_Nm": alpha * sum(m * (r * r + 0.5 * r_self ** 2) for m, r in beyond)}
        # J4: J5 를 90° 꺾으면 J5 너머의 팔 방향 거리(x - x5)와 J5 축 방향 옆 거리(y)가 모두 J4 축에 수직 — 두 1차 모멘트 합의 크기
        # (J5 가 90° 까지 간다는 것은 가정 — kinematics.json 의 ±170° 는 「확인 안 된 표시용」)
        link4_on = [(m, (xx - x[5]) if link_of(n) >= 5 else 0.0, y) for n, m, xx, y in els if link_of(n) >= 4]
        mx = sum(m * d for m, d, _y in link4_on)
        my = sum(m * y for m, _d, y in link4_on)
        res["J4"] = {"gravity_Nm": g * math.hypot(mx, my), "inertia_Nm": alpha * sum(m * (d * d + y * y + 0.5 * r_self ** 2) for m, d, y in link4_on),
                     "moment_parts_kgm": {"along_J5_J6_line": mx, "along_J5_axis": my}}
        # J1: 뻗은 팔 + J2 묶음(링크1 위 · 옆으로 뻗은 캔) + 링크1 몸체의 관성만 — 수평 거리 = hypot(x, y)
        j1_els = els + pitch_group(2, motors, p, p.get("infill")) + [(n, m, r, 0.0) for n, m, r in link1_bodies()]
        res["J1"] = {"gravity_Nm": 0.0, "inertia_Nm": alpha * sum(m * (xx * xx + y * y + 0.5 * r_self ** 2) for _n, m, xx, y in j1_els)}
        fl = [(body_g("LINK6_TOOL_FLANGE") / 1000, tool["flange_r"] / 1000), (body_g("LINK6_TOOL_RING") / 1000, tool["ring_r"] / 1000)]
        i6 = sum(0.5 * m * r * r for m, r in fl) + payload * (j6_off ** 2 + 0.5 * r_self ** 2)
        res["J6"] = {"gravity_Nm": g * payload * j6_off, "inertia_Nm": alpha * i6}
        for jn, v in res.items():
            mot = inp["motors"][motors[int(jn[1])]]
            v["required_Nm"] = p["sf"] * (v["gravity_Nm"] + v["inertia_Nm"])
            v["motor"] = motors[int(jn[1])]
            v["ratio_needed"] = {t: v["required_Nm"] / (mot["holding_Nm"] * p["usable"] * e_) for t, e_ in p["eta"].items()}
            rn = ceil1(v["ratio_needed"]["cycloid_printed"])  # 표시하는 올림 비로 속도를 센다(같은 행의 비와 맞게)
            v["joint_speed_deg_s_at_cycloid_ratio"] = p["rpm"] * 6.0 / rn if rn >= 1.0 else None  # 감속이 필요 없으면 이 비로 속도를 말하지 않는다
        # J2 출력 베어링(정적 · 안전율 전): 팔 무게가 모두 출력 베어링으로 간다고 볼 때의 반경 힘과,
        # 팔 무게중심이 베어링 중심에서 J2 축 방향으로 비킨 거리에서 생기는 기울임 모멘트(J2 구동 토크와 다른 양 — 구동 토크는 감속기가 받는다)
        w = g * sum(m for _n, m, _x, _y in els)
        y_cm = sum(m * y for _n, m, _x, y in els) / sum(m for _n, m, _x, _y in els)
        # J1 이 가속하면 J2 너머 팔의 접선 관성력(J2 축 방향)이 팔 방향 거리 x 에서 J2 베어링을 기울인다 — 근사 α · Σ m x²(J1 관성 토크 중 팔 몫)
        tilt_static = w * abs(y_cm - y_bearing)
        tilt_j1 = alpha * sum(m * xx * xx for _n, m, xx, _y in els)
        res["J2_output_bearing"] = {"radial_N": w, "arm_cm_offset_along_J2_axis_mm": y_cm * 1000, "bearing_centre_mm": y_bearing * 1000,
                                    "tilting_static_Nm": tilt_static, "tilting_from_J1_accel_Nm": tilt_j1,
                                    "tilting_combined_Nm": math.hypot(tilt_static, tilt_j1)}
        return res, sum(m for _n, m, _x, _y in els if _n != "payload")

    base_p = {"driver_kg": inp["driver_board_mass_kg"]["value"], "reducer_metal_kg": inp["reducer_metal_mass_kg"]["value"],
              "payload_offset_m": inp["payload_offset_from_flange_m"]["value"], "alpha": inp["angular_accel_rad_s2"]["value"],
              "sf": inp["safety_factor"]["value"], "usable": inp["usable_torque_fraction"]["value"],
              "rpm": inp["speed_check"]["motor_rpm_at_usable_torque"]["value"], "eta": {k: v["value"] for k, v in inp["efficiency_by_type"].items()}}
    scenarios = {
        "S1 모두 NEMA17-40(v1 가정)": {k: "NEMA17-40" for k in range(1, 7)},
        "S2 모두 NEMA17-48": {k: "NEMA17-48" for k in range(1, 7)},
        "S3 J2 · J3 NEMA17-60 · 나머지 NEMA17-48": {**{k: "NEMA17-48" for k in range(1, 7)}, 2: "NEMA17-60", 3: "NEMA17-60"},
        "S4 J2 · J3 NEMA23-56(57D) · 나머지 NEMA17-48": {**{k: "NEMA17-48" for k in range(1, 7)}, 2: "NEMA23-56", 3: "NEMA23-56"},
    }
    results = {}
    for sname, motors in scenarios.items():
        sres = {"elements": [{"name": n, "kg": m, "x_m": xx, "y_m": y} for n, m, xx, y in elements(motors, base_p)], "payloads": {}}
        for pl in inp["payloads_kg"]:
            res, arm = loads(motors, pl, base_p)
            sres["payloads"][str(pl)] = res
            sres["arm_mass_beyond_J2_kg"] = arm
        results[sname] = sres
    out["results"] = results

    # ---- 5. 민감도(S2 · 짐 0.5 kg · J2 필요 감속비 — 사이클로이드 효율) ----
    s2 = scenarios["S2 모두 NEMA17-48"]

    def j2_ratio(motors=s2, **over):
        p = {**base_p, **{k: v for k, v in over.items() if k != "eta_cycloid"}}
        if "eta_cycloid" in over:
            p["eta"] = {**base_p["eta"], "cycloid_printed": over["eta_cycloid"]}
        res, _arm = loads(motors, 0.5, p)
        return res["J2"]["ratio_needed"]["cycloid_printed"]

    base = j2_ratio()
    cases = {
        "손목 J5→J6 140 → 72 mm(J6 캔 배치를 바꿔야 가능)": j2_ratio(wrist_shift_m=(p1["wrist_offsets_mm"][1] - 72) / 1000),
        "J3 모터 · 드라이버를 J2 축 위로": j2_ratio(j3_motor_x=0.0),
        "J4 ~ J6 모터 NEMA17-40(J2 · J3 는 48 그대로)": j2_ratio({**s2, 4: "NEMA17-40", 5: "NEMA17-40", 6: "NEMA17-40"}),
        "감속기 금속 0.15 → 0.10 kg": j2_ratio(reducer_metal_kg=0.10),
        "감속기 금속 0.15 → 0.25 kg": j2_ratio(reducer_metal_kg=0.25),
        "채움 15 → 10 %": j2_ratio(infill=0.10),
        "채움 15 → 25 %": j2_ratio(infill=0.25),
        "출력 질량 × 판의 슬라이서/모형 비": j2_ratio(print_scale=1.0 / out["mass_model_check"]["model_over_slicer"]),
        "쓸 수 있는 토크 0.5 → 0.4": j2_ratio(usable=0.4),
        "쓸 수 있는 토크 0.5 → 0.7": j2_ratio(usable=0.7),
        "사이클로이드 효율 0.75 → 0.65": j2_ratio(eta_cycloid=0.65),
        "사이클로이드 효율 0.75 → 0.85": j2_ratio(eta_cycloid=0.85),
        "안전율 2.0 → 1.5": j2_ratio(sf=1.5),
        "관절 가속 2 → 6 rad/s²": j2_ratio(alpha=6.0),
        "자기 관성 반지름 52 → 104 mm(그 항 4 배)": j2_ratio(r_self=2 * r_self_base),
        "짐 중심 = 플랜지 + 0.05 → 0.10 m": j2_ratio(payload_offset_m=0.10),
        "J2 모터만 NEMA23-56(J3 는 48 그대로)": j2_ratio({**s2, 2: "NEMA23-56"}),
    }
    out["sensitivity_J2"] = {"base_ratio": base, "cases": {k: {"ratio": v, "change_pct": 100 * (v / base - 1)} for k, v in cases.items()}}

    # ---- 5b. 후보 구동 판정: 감속비 R · 효율 η 인 구동이 어느 짐까지 필요 토크를 내는가(유지 토크 × 쓸 수 있는 비율 × η × R ≥ 필요) ----
    cand_rows = []
    for cd in inp["candidate_drives"]["list"]:
        eta = base_p["eta"][cd["efficiency"]]
        row = {"name": cd["name"], "ratio": cd["ratio"], "efficiency": eta, "joint_speed_deg_s": base_p["rpm"] * 6.0 / cd["ratio"], "cells": {}}
        for col, (sname, joints) in inp["candidate_drives"]["columns"].items():
            sres = results[next(n for n in results if n.startswith(sname + " "))]
            ok, margin = [], {}
            for pl, jr in sres["payloads"].items():
                assert len({jr[j]["motor"] for j in joints}) == 1, f"column {col}: joints with different motors"
                need = max(jr[j]["required_Nm"] for j in joints)
                have = inp["motors"][jr[joints[0]]["motor"]]["holding_Nm"] * base_p["usable"] * eta * cd["ratio"]
                ok.append(have >= need)
                margin[float(pl)] = have / need - 1.0
            assert ok == sorted(ok, reverse=True), f"column {col}: pass/fail not monotonic in payload"
            passed = [float(pl) for pl, good in zip(sres["payloads"], ok) if good]
            row["cells"][col] = {"max_payload_kg": max(passed), "margin": margin[max(passed)]} if passed else None
        cand_rows.append(row)
    out["candidate_drives"] = cand_rows

    # ---- 5c. 모터 · 캔 맞춤(지금 v2 캔에 그 모터가 드는가 — 축 방향 길이 · 반지름) ----
    ext = p2["exterior"]
    can_len = 3 + p1["motor_length_mm"] + 2 + p1["driver_depth_mm"] + ext["can_rear_clearance_mm"]  # v2geom.py 의 LC(바깥 길이)
    can_end = p1["reducer_depth_mm"] / 2 + can_len
    cap_inner = abs(split["interfaces"]["end_cap"]["pillar_z_mm"][0])  # J2 분할: 덮개 기둥이 닿는 덮개 안쪽 면(관절 중심에서)
    can_inner_r = split["interfaces"]["end_cap"]["can_bore_radius_mm"]
    fit_rows = {}
    for mname, mv in inp["motors"].items():
        rear = motor_face * 1000 + mv["length_mm"] + motor_driver_gap * 1000 + p1["driver_depth_mm"]
        half_diag = mv["frame_mm"] / math.sqrt(2)
        fit_rows[mname] = {"driver_rear_mm": rear, "can_end_mm": can_end, "cap_inner_face_mm": cap_inner, "rear_overrun_mm": max(0.0, rear - cap_inner),
                           "frame_half_diagonal_mm": half_diag, "can_inner_radius_mm": can_inner_r, "radial_overrun_mm": max(0.0, half_diag - can_inner_r)}
    out["motor_can_fit"] = {"note": "driver = MKS 42D size from v1 (width/depth) for every motor; the 57D board size is not checked", "rows": fit_rows}

    # ---- 6. 감속기 공간(J2) — 쌓임은 가정 ----
    jz = split["interfaces"]
    avail = {"reducer_space_mm": jz["reducer_space"]["depth_mm"], "reducer_space_radius_mm": jz["reducer_space"]["radius_mm"],
             "bearing_mm": jz["output_bearing_seat"]["width_mm"], "lip_mm": p2["j2_split"]["lip_height_mm"], "drum_depth_mm": p1["reducer_depth_mm"]}
    stacks = {k: v for k, v in inp["reducer_stacks_mm"].items() if k != "note"}
    out["reducer_space"] = {"available": avail, "note": inp["reducer_stacks_mm"]["note"],
                            "stacks": {n: {"parts_mm": s, "total_mm": sum(s.values()),
                                           "extra_depth_if_this_stack_mm": max(0.0, sum(s.values()) - avail["reducer_space_mm"])}
                                       for n, s in stacks.items()}}
    out["inputs_sha256"] = read

    # ---- 7. 표 · 문서용 요약 ----
    def r1(v):
        """필요 감속비는 소수 첫째 자리로 올림 — 표의 값 이상을 골라야 한다(내림 표시가 「충분」 판정을 속이지 않게)."""
        return f"{ceil1(v):.1f}"

    def spd(v):
        s_ = v["joint_speed_deg_s_at_cycloid_ratio"]
        return "-" if s_ is None else f"{math.floor(s_ * 10 + 1e-9) / 10:.1f}"  # 속도는 내림 표시

    blocks = {}  # 문서(022)가 줄 그대로 싣는 블록 — check_doc_sync.py 가 대조한다
    c = out["mass_model_check"]
    blocks["mp5-mass"] = [
        f"- 출력 설정(시험편 3MF에서 읽음): 벽 {pla['shell_mm']:.2f} mm · 채움 {pla['infill'] * 100:.0f} % · 필라멘트 밀도 {pla['density_g_cm3']:.2f} g/cm³",
        f"- 질량 모형 점검(끼움 시험편 판 하나): 모형 {c['model_g']:.1f} g · 슬라이서 {c['slicer_g']} g · 모형/슬라이서 {c['model_over_slicer']:.3f}",
        f"- J2 분할 여섯 부품의 모형 질량 = {j2_parts_g():.0f} g · 관절 모듈 출력 부품(외곽 비로 추정) = "
        + " · ".join(f"J{k} {module_print_g(k):.0f} g" for k in (3, 4, 5, 6)),
        "- J2 너머 팔 질량(짐 제외): " + " · ".join(f"{n.split(' ')[0]} {r['arm_mass_beyond_J2_kg']:.2f} kg" for n, r in results.items()),
    ]
    summary = ["| 시나리오(J2 · J3 모터) | 짐 kg | J2 필요 N·m | J2 필요 감속비: 사이클로이드 · 앞단+사이클로이드 · 복합 유성 | 사이클로이드 비일 때 J2 °/s | "
               "J3 필요 감속비(사이클로이드) | J4 필요 감속비 | J5 필요 감속비 | J1 필요 감속비(관성만) | J6 필요 감속비 |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for sname, sres in results.items():
        for pl, joints in sres["payloads"].items():
            r2 = joints["J2"]["ratio_needed"]
            summary.append(f"| {sname.split(' ')[0]} ({joints['J2']['motor']}) | {pl} | {joints['J2']['required_Nm']:.2f} | "
                           f"{r1(r2['cycloid_printed'])} · {r1(r2['prestage_plus_cycloid'])} · {r1(r2['compound_planetary_printed'])} | "
                           f"{spd(joints['J2'])} | {r1(joints['J3']['ratio_needed']['cycloid_printed'])} | "
                           f"{r1(joints['J4']['ratio_needed']['cycloid_printed'])} | {r1(joints['J5']['ratio_needed']['cycloid_printed'])} | "
                           f"{r1(joints['J1']['ratio_needed']['cycloid_printed'])} | {r1(joints['J6']['ratio_needed']['cycloid_printed'])} |")
    blocks["mp5-summary"] = summary
    sens = [f"- 기준(S2 · 짐 0.5 kg · J2 · 사이클로이드) = {r1(base)}", "", "| 한 번에 하나만 바꿈 | J2 필요 감속비 | 변화 % |", "|---|---|---|"]
    for k, v in sorted(out["sensitivity_J2"]["cases"].items(), key=lambda kv: -abs(kv[1]["change_pct"])):
        sens.append(f"| {k} | {r1(v['ratio'])} | {v['change_pct']:+.1f} |")
    blocks["mp5-sensitivity"] = sens
    space = [f"- 지금 J2 분할의 감속기 공간 = 깊이 {avail['reducer_space_mm']:.1f} mm · 반지름 {avail['reducer_space_radius_mm']} mm "
             f"(드럼 깊이 {avail['drum_depth_mm']} mm 안에 뒷벽 · 턱 {avail['lip_mm']} · 베어링 {avail['bearing_mm']} · 누름판이 함께 든다)", "",
             "| 후보(쌓임 두께는 모두 가정) | 가정 쌓임 mm | 그 가정대로면 더 필요한 깊이 mm |", "|---|---|---|"]
    for n, v in out["reducer_space"]["stacks"].items():
        space.append(f"| {n} | {v['total_mm']} | {v['extra_depth_if_this_stack_mm']:.1f} |")
    blocks["mp5-space"] = space

    cols = list(inp["candidate_drives"]["columns"])
    cand = ["| 구동(감속비 · 효율) | 관절 속도 °/s(모터 300 rpm) | " + " | ".join(cols) + " |", "|---" * (len(cols) + 2) + "|"]
    for row in cand_rows:
        cells = ["✗(0 kg 도 모자람)" if v is None else f"{v['max_payload_kg']:g} kg 까지(여유 {math.floor(v['margin'] * 1000) / 10:.1f} %)"
                 for v in row["cells"].values()]
        cand.append(f"| {row['name']} · η {row['efficiency']:g} | {math.floor(row['joint_speed_deg_s'] * 10) / 10:.1f} | " + " | ".join(cells) + " |")
    blocks["mp5-candidates"] = cand
    brg = ["| 시나리오 | 짐 kg | 반경 힘 N | 팔 무게중심의 J2 축 방향 자리 mm(베어링 중심 = "
           f"{y_bearing * 1000:.1f}) | 기울임: 정적 · J1 가속 · 합 N·m(안전율 전) | 참고: J2 구동 중력 토크 N·m(감속기가 받음) |", "|---|---|---|---|---|---|"]
    for sname, sres in results.items():
        for pl, joints in sres["payloads"].items():
            b = joints["J2_output_bearing"]
            brg.append(f"| {sname.split(' ')[0]} | {pl} | {b['radial_N']:.1f} | {b['arm_cm_offset_along_J2_axis_mm']:.1f} | {b['tilting_static_Nm']:.2f} · {b['tilting_from_J1_accel_Nm']:.2f} · {b['tilting_combined_Nm']:.2f} | "
                       f"{joints['J2']['gravity_Nm']:.2f} |")
    blocks["mp5-bearing"] = brg

    fitb = [f"- J2 분할 기준(관절 중심에서): 모터 면 {motor_face * 1000:.0f} mm · 모터 → 드라이버 간격 {motor_driver_gap * 1000:.0f} mm · "
            f"덮개 안쪽 면 {cap_inner:g} mm(덮개 기둥 끝) · 캔 안 반지름 {can_inner_r:g} mm — 바깥 캔 끝은 {can_end:.0f} mm(모터 {p1['motor_length_mm']} mm 기준). "
            "커넥터 · 57D 보드 크기 · 다른 관절의 실제 장착면은 보지 않았다.", "",
            "| 모터 | 드라이버 뒤끝 mm | 덮개 안쪽 면을 넘는 길이 mm | 프레임 대각선 반(모서리 안 깎은 상한) mm | 캔 안 반지름을 넘는 mm |", "|---|---|---|---|---|"]
    for mname, r in fit_rows.items():
        fitb.append(f"| {mname} | {r['driver_rear_mm']:.0f} | {r['rear_overrun_mm']:.1f} | {r['frame_half_diagonal_mm']:.1f} | {r['radial_overrun_mm']:.1f} |")
    blocks["mp5-canfit"] = fitb

    def fenced(name):
        return [f"<!-- {name}:begin -->"] + blocks[name] + [f"<!-- {name}:end -->"]

    md = ["# MP5 관절 부하 · 필요 감속비 (joint_loads.py 가 만든 표 — 손으로 고치지 않는다)", "",
          "- 필요 감속비는 소수 첫째 자리로 **올림** 표시 — 고를 감속비는 표의 값 이상이어야 한다.",
          f"- 출력 설정 출처: {pla['source']}", ""]
    md += ["## 질량", ""] + fenced("mp5-mass") + [""]
    for sname, sres in results.items():
        md += [f"## {sname} — J2 너머 팔 질량 {sres['arm_mass_beyond_J2_kg']:.2f} kg", "",
               "| 짐 kg | 관절 | 모터 | 중력 N·m | 관성 N·m | 필요(×안전율) N·m | 필요 감속비: 사이클로이드 · 앞단+사이클로이드 · 복합 유성 · 상용 기어헤드 | 관절 속도 °/s(사이클로이드 비) |",
               "|---|---|---|---|---|---|---|---|"]
        for pl, joints in sres["payloads"].items():
            for jn in ("J1", "J2", "J3", "J4", "J5", "J6"):
                v = joints[jn]
                r = v["ratio_needed"]
                md.append(f"| {pl} | {jn} | {v['motor']} | {v['gravity_Nm']:.2f} | {v['inertia_Nm']:.4f} | {v['required_Nm']:.2f} | "
                          f"{r1(r['cycloid_printed'])} · {r1(r['prestage_plus_cycloid'])} · {r1(r['compound_planetary_printed'])} · "
                          f"{r1(r['gearhead_commercial'])} | {spd(v)} |")
        md.append("")
    md += ["## 요약(J2 · J3 · J4 · J5)", ""] + fenced("mp5-summary") + [""]
    md += ["## 민감도", ""] + fenced("mp5-sensitivity") + [""]
    md += ["## 후보 구동 판정(필요 토크를 내는 가장 큰 짐)", ""] + fenced("mp5-candidates") + [""]
    md += ["## J2 출력 베어링 하중(정적 · 근사)", ""] + fenced("mp5-bearing") + [""]
    md += ["## 모터 · 캔 맞춤(지금 v2)", ""] + fenced("mp5-canfit") + [""]
    md += ["## J2 감속기 공간", ""] + fenced("mp5-space")
    out["doc_blocks"] = blocks
    (a.out / "loads.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "loads.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {a.out / 'loads.json'} and loads.md")


if __name__ == "__main__":
    main()
