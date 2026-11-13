# -*- coding: utf-8 -*-
"""MP16 - J2 / J3 drive module sizing (NEMA23 + SERVO57D -> HTD 3M belt 3:1 -> printed cycloid 27:1 = 81:1).

User decisions (2026-11-06): 「네마 23 서보 57 사올테니」 · 「J2·J3 같은 모듈 81:1 (권장)」 · 「J2·J3 는 1 kg 기준 (권장)」 · 「J2는 그럼 76사올게」(J3 = 56 mm).
Every number below is a proposal (author) or an ASSUMPTION unless a source is named. Steel density 7.85 g/cm3.
Run: python sizing.py --scratch <folder outside the repo>   (module_mass.json + the copied MP5 load model run in the scratch; sizing.json / sizing.md -> .dev/mp16-evidence/sizing)
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import argparse
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
_ap = argparse.ArgumentParser()
_ap.add_argument("--scratch", required=True, type=Path)
_A = _ap.parse_args()
LOADS = _A.scratch.resolve() / "loads"
OUTD = REPO / ".dev" / "mp16-evidence" / "sizing"
OUTD.mkdir(parents=True, exist_ok=True)
assert REPO.resolve() not in LOADS.parents
sys.path.insert(0, str(REPO / "src/cad/cycloid-27-v1"))
from cycloid import curvature_radii  # noqa: E402  (read only - MP6 generator helper)

PY = sys.executable
STEEL = 7.85e-3  # g / mm3

D = {
    "ratio": {"belt_small_T": 20, "belt_big_T": 60, "pins": 28, "lobes": 27},
    "belt": {"type": "HTD 3M", "pitch": 3.0, "width": 15.0,
             "working_tension_N": 300.0,
             "working_tension_note": "ASSUMPTION - HTD 3M 15 mm glass-cord belt usable working tension class; no catalog checked in this unit"},
    "cycloid": {"ring_radius": 46.0, "pin_dia": 6.0, "pin_len": 45.0, "ecc": 1.2, "profile_clearance": 0.10,
                "disc_t": 12.0, "disc_gap": 1.0, "out_pins": 8, "out_pin_radius": 28.0, "out_pin_dia": 8.0, "out_pin_len": 45.0,
                "out_hole_clearance": 0.10, "out_pin_engagement": 11.0, "out_pin_arm_disc1": 20.0,
                "carrier_press_depth": 19.0,
                "stack_note": "from build_drive.geometry (R1): ring pins z 2 - 47, output pins z 11 - 56 pressed in the carrier z 37 - 56"},
    "bearings": {
        "disc": {"model": "6804", "d": 20, "D": 32, "B": 7, "C_kN": 4.0, "C0_kN": 2.47, "kg": 0.019, "n": 2},
        "output": {"model": "6812 (61812)", "d": 60, "D": 78, "B": 10, "C_kN": 11.9, "C0_kN": 11.4, "kg": 0.10, "n": 1},
        "shaft": {"model": "608", "d": 8, "D": 22, "B": 7, "C_kN": 3.45, "C0_kN": 1.37, "kg": 0.012, "n": 2},
        "note": "C / C0 / mass = common catalog class values remembered by the author - ASSUMPTION until a data sheet is checked"},
    "shaft": {"dia": 8.0, "len": 70.0, "type": "D-cut steel shaft (cut from 100 mm)"},
    "pulley_kg": {"big_60T": 0.065, "small_20T": 0.020, "belt": 0.010, "note": "ASSUMPTION - aluminium HTD 3M pulleys 15 mm"},
    "small_parts_kg": 0.04,
    "driver_57d_kg": 0.12, "driver_57d_note": "ASSUMPTION - SERVO57D board + aluminium housing (MT package); not weighed",
    "print_extra_kg": 0.35, "print_extra_note": "ASSUMPTION - MP16 module printed parts (housing about 118 mm, discs, carrier, motor plate, belt cover) above the MP5 scaled J3 module estimate (142 g)",
    "motor_rpm": 300, "input_rpm_note": "MP5 assumption 300 rpm at usable torque",
    "life_target_h": 2000,
}


def pin_g(d, L):
    return math.pi * (d / 2) ** 2 * L * STEEL


c, B = D["cycloid"], D["bearings"]
metal = {
    "ring pins": D["ratio"]["pins"] * pin_g(c["pin_dia"], c["pin_len"]) / 1000,
    "output pins": c["out_pins"] * pin_g(c["out_pin_dia"], c["out_pin_len"]) / 1000,
    "bearings": sum(b["kg"] * b["n"] for k, b in B.items() if k != "note"),
    "input shaft": pin_g(D["shaft"]["dia"], D["shaft"]["len"]) / 1000,
    "pulleys + belt": D["pulley_kg"]["big_60T"] + D["pulley_kg"]["small_20T"] + D["pulley_kg"]["belt"],
    "screws + inserts": D["small_parts_kg"],
}
mm = {"metal_kg": sum(metal.values()), "metal_parts_kg": metal, "driver_57d_kg": D["driver_57d_kg"], "print_extra_kg": D["print_extra_kg"]}
LOADS.mkdir(parents=True, exist_ok=True)
(LOADS / "module_mass.json").write_text(json.dumps(mm, indent=1), encoding="utf-8")

# rerun the copied MP5 load model with the module mass
subprocess.run([PY, "-B", str(HERE / "loads_copy.py"), str(LOADS / "module_mass.json"), str(LOADS)], check=True)
subprocess.run([PY, "-B", str(LOADS / "joint_loads_mp16.py"), "--out", str(LOADS / "out")], check=True, stdout=subprocess.DEVNULL)
L = json.loads((LOADS / "out" / "loads.json").read_text(encoding="utf-8"))
inp = json.loads((LOADS / "inputs.json").read_text(encoding="utf-8"))
S6 = L["results"]["S6 J2 NEMA23-76 · J3 NEMA23-56(57D) · 나머지 NEMA17-40(보유 42D)"]
usable = inp["usable_torque_fraction"]["value"]
eta = inp["efficiency_by_type"]["prestage_plus_cycloid"]["value"]
R = D["ratio"]["belt_big_T"] / D["ratio"]["belt_small_T"] * D["ratio"]["lobes"]
out = {"design": D, "module_mass": mm, "ratio": R}

# 1. torque margins (S6 - J2 76 mm, J3 56 mm)
marg = {}
for pl in ("0.5", "0.7", "1.0"):
    r = S6["payloads"][pl]
    row = {}
    for j, mot in (("J2", "NEMA23-76"), ("J3", "NEMA23-56")):
        have = inp["motors"][mot]["holding_Nm"] * usable * eta * R
        row[j] = {"need_Nm": r[j]["required_Nm"], "have_Nm": have, "margin": have / r[j]["required_Nm"] - 1, "motor": mot}
    for j in ("J4", "J5"):
        have = inp["motors"]["NEMA17-40"]["holding_Nm"] * usable * inp["efficiency_by_type"]["cycloid_printed"]["value"] * 27
        row[j] = {"need_Nm": r[j]["required_Nm"], "have_Nm": have, "margin": have / r[j]["required_Nm"] - 1, "motor": "NEMA17-40"}
    marg[pl] = row
out["margins_S6"] = marg
T = max(marg["1.0"]["J2"]["need_Nm"], marg["1.0"]["J3"]["need_Nm"])   # design output torque (SF 2 included)
out["design_torque_Nm"] = T
out["joint_speed_deg_s"] = D["motor_rpm"] * 6 / R

# 2. cycloid
rr = c["pin_dia"] / 2 + c["profile_clearance"]
conv, conc = curvature_radii(D["ratio"]["pins"], c["ring_radius"], rr, c["ecc"])
conv6, conc6 = curvature_radii(28, 28.0, 2.1, 0.7)
f3 = T / (3 * c["out_pin_radius"] / 1000)
f1 = 3 * f3
zl = c["out_pin_dia"] * c["out_pin_engagement"]
Wb = math.pi * (c["out_pin_dia"] / 1000) ** 3 / 32
hole_r = c["out_pin_dia"] / 2 + c["ecc"] + c["out_hole_clearance"]
pitch_ring = 2 * math.pi * c["ring_radius"] / D["ratio"]["pins"]
web_out = 2 * c["out_pin_radius"] * math.sin(math.pi / c["out_pins"]) - 2 * hole_r
disc_root = c["ring_radius"] - c["ecc"] - rr
fe = T / (D["ratio"]["lobes"] * c["ecc"] / 1000)
cam_wall = (B["disc"]["d"] - D["shaft"]["dia"]) / 2 - c["ecc"]
out["cycloid"] = {
    "EN_over_R": c["ecc"] * D["ratio"]["pins"] / c["ring_radius"], "EN_over_R_MP6": 0.7 * 28 / 28,
    "min_convex_radius_mm": conv, "min_concave_radius_mm": conc, "MP6_min_convex_radius_mm": conv6,
    "ring_pin_gap_mm": pitch_ring - c["pin_dia"],
    "disc_od_mm": 2 * (c["ring_radius"] + c["ecc"] - rr), "disc_root_radius_mm": disc_root,
    "out_hole_dia_mm": 2 * hole_r, "web_between_out_holes_mm": web_out,
    "wall_out_hole_to_disc_root_mm": disc_root - (c["out_pin_radius"] + hole_r),
    "wall_out_hole_to_disc_bearing_mm": c["out_pin_radius"] - hole_r - B["disc"]["D"] / 2,
    "cam_wall_min_mm": cam_wall,
    "out_pin_force_N_3pin": f3, "out_pin_force_N_1pin": f1,
    "pla_pressure_MPa_3pin": f3 / zl, "pla_pressure_MPa_1pin": f1 / zl,
    "MP6_wrist_pla_pressure_MPa_3pin_1pin": [3.48, 10.44],
    "out_pin_bending_MPa_3pin": f3 * c["out_pin_arm_disc1"] / 1000 / Wb / 1e6, "out_pin_bending_MPa_1pin": f1 * c["out_pin_arm_disc1"] / 1000 / Wb / 1e6,
    "carrier_hole_entrance_pressure_MPa_3pin": f3 / (c["out_pin_dia"] * c["carrier_press_depth"]) * (4 + 6 * c["out_pin_arm_disc1"] / c["carrier_press_depth"]),
    "carrier_hole_entrance_note": "R1 review estimate for a cantilever pin in a PLA hole: (F / d L)(4 + 6 a / L) - design torque (SF 2 included); the nominal load is about half",
    "eccentric_reaction_scale_N": fe,
}
# 3. bearings
rpm_in = D["motor_rpm"] / (D["ratio"]["belt_big_T"] / D["ratio"]["belt_small_T"])
P_disc = fe  # conservative: the whole scale on each disc bearing
L10_rev = (B["disc"]["C_kN"] * 1000 / P_disc) ** 3 * 1e6
lw = S6["payloads"]["1.0"]["J2_output_bearing"]
out["bearings"] = {
    "disc": {"P_N": P_disc, "static_SF": B["disc"]["C0_kN"] * 1000 / P_disc, "L10_h_at_input_rpm": L10_rev / rpm_in / 60, "input_rpm": rpm_in},
    "output": {"radial_N": lw["radial_N"], "tilt_Nm": lw["tilting_combined_Nm"],
               "equiv_radial_from_tilt_N_SF2": 2 * 2 * lw["tilting_combined_Nm"] / ((B["output"]["d"] + B["output"]["D"]) / 2 / 1000),
               "static_SF": B["output"]["C0_kN"] * 1000 / (lw["radial_N"] * 2 + 2 * 2 * lw["tilting_combined_Nm"] / ((B["output"]["d"] + B["output"]["D"]) / 2 / 1000))},
}
# 4. belt
p, z1, z2 = D["belt"]["pitch"], D["ratio"]["belt_small_T"], D["ratio"]["belt_big_T"]
d1, d2 = z1 * p / math.pi, z2 * p / math.pi
belt = {"pitch_dia_small": d1, "pitch_dia_big": d2}
for mot in ("NEMA23-76", "NEMA23-56"):
    belt[f"tension_N_at_holding_{mot}"] = inp["motors"][mot]["holding_Nm"] / (d1 / 2 / 1000)
belt["working_tension_N_assumed"] = D["belt"]["working_tension_N"]
lay = {}
for name, C in (("side (motor beside the reducer)", 91.0), ("behind (motor behind the pulley plane)", 55.0)):
    Lb = 2 * C + math.pi * (d1 + d2) / 2 + (d2 - d1) ** 2 / (4 * C)
    teeth = round(Lb / p)
    # centre distance for the nearest standard length (3 mm steps)
    Ls = teeth * p
    b = Ls - math.pi * (d1 + d2) / 2
    Cs = (b + math.sqrt(b * b - 2 * (d2 - d1) ** 2)) / 4
    wrap = 180 - 2 * math.degrees(math.asin((d2 - d1) / (2 * Cs)))
    lay[name] = {"C_try": C, "belt": f"3M-{int(Ls)}-15 ({teeth} T)", "C_for_that_belt": Cs, "wrap_small_deg": wrap, "teeth_in_mesh_small": z1 * wrap / 360}
belt["layouts"] = lay
out["belt"] = belt
(OUTD / "sizing.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def f(v, n=1):
    return f"{v:.{n}f}"


lines = [f"# MP16 sizing — ratio {R:g}:1 · design torque {f(T)} N·m (SF 2 incl., 1 kg) · joint speed {f(out['joint_speed_deg_s'])} °/s @ {D['motor_rpm']} rpm",
         "", "## module metal (kg)", *[f"- {k}: {f(v, 3)}" for k, v in metal.items()], f"- total: {f(mm['metal_kg'], 3)}", "", "## margins (S6)"]
for pl, row in marg.items():
    lines.append(f"- {pl} kg: " + " · ".join(f"{j} need {f(v['need_Nm'], 2)} have {f(v['have_Nm'], 2)} margin {f(v['margin'] * 100)} %" for j, v in row.items()))
lines += ["", "## cycloid"] + [f"- {k}: {v if isinstance(v, (list, str)) else f(v, 2)}" for k, v in out["cycloid"].items()]
lines += ["", "## bearings"] + [f"- {k}: " + " · ".join(f"{kk} {f(vv, 2)}" for kk, vv in v.items()) for k, v in out["bearings"].items()]
lines += ["", "## belt"] + [f"- {k}: {v if isinstance(v, dict) else f(v, 1)}" for k, v in belt.items() if k != "layouts"]
lines += [f"- {k}: {v['belt']} · C {f(v['C_for_that_belt'])} · wrap {f(v['wrap_small_deg'])}° · teeth in mesh {f(v['teeth_in_mesh_small'])}" for k, v in lay.items()]
(OUTD / "sizing.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
