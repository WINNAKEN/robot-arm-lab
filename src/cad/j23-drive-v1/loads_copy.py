# MP16 - writes a copy of MP5 joint_loads.py (source is read only) into the scratch folder given as argv[2]:
#  - payloads 0, 0.25, 0.5, 0.7, 1.0
#  - scenario S5: J2/J3 NEMA23-56, others NEMA17-40 (owned 42D)
#  - scenario S6: J2 NEMA23-76, J3 NEMA23-56, others NEMA17-40 (user 2026-11-06: J2 76 mm, J3 56 mm)
#  - per-joint driver and reducer-metal mass (J2/J3 = MP16 module values from ../sizing/module_mass.json)
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "review-mp5"
DST = Path(sys.argv[2])
DST.mkdir(parents=True, exist_ok=True)
mm = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) if len(sys.argv) > 1 else None
s = (SRC / "joint_loads.py").read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


rep('ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])',
    'ROOT = Path(%r)' % str(Path(__file__).resolve().parents[3]).replace(chr(92), '/'))
rep('read[str(Path(p).relative_to(ROOT))] = sha(p)', 'read[str(p)] = sha(p)')
old = '        "S4 J2 · J3 NEMA23-56(57D) · 나머지 NEMA17-48": {**{k: "NEMA17-48" for k in range(1, 7)}, 2: "NEMA23-56", 3: "NEMA23-56"},\n'
rep(old, old
    + '        "S5 J2 · J3 NEMA23-56(57D) · 나머지 NEMA17-40(보유 42D)": {**{k: "NEMA17-40" for k in range(1, 7)}, 2: "NEMA23-56", 3: "NEMA23-56"},\n'
    + '        "S6 J2 NEMA23-76 · J3 NEMA23-56(57D) · 나머지 NEMA17-40(보유 42D)": {**{k: "NEMA17-40" for k in range(1, 7)}, 2: "NEMA23-76", 3: "NEMA23-56"},\n')
rep('(f"J{k} motor", mot["mass_kg"], xk, side * abs(mo)), (f"J{k} driver", p["driver_kg"], xk, side * abs(do)),\n'
    '                (f"J{k} reducer metal", p["reducer_metal_kg"], x[k], 0.0)]',
    '(f"J{k} motor", mot["mass_kg"], xk, side * abs(mo)), (f"J{k} driver", p.get("driver_by_joint", {}).get(k, p["driver_kg"]) if mot["frame_mm"] > 50 else p["driver_kg"], xk, side * abs(do)),\n'
    '                (f"J{k} reducer metal", p.get("reducer_metal_by_joint", {}).get(k, p["reducer_metal_kg"]), x[k], 0.0)]')
if mm:
    rep('"sf": inp["safety_factor"]["value"],',
        '"sf": inp["safety_factor"]["value"], "driver_by_joint": {3: %r, 2: %r}, "reducer_metal_by_joint": {2: %r, 3: %r}, "j3_module_print_extra_kg": %r,'
        % (mm["driver_57d_kg"], mm["driver_57d_kg"], mm["metal_kg"], mm["metal_kg"], mm["print_extra_kg"]))
    # J3 module print grows with the MP16 module (extra printed mass on top of the MP5 scaled estimate)
    rep('return [(f"J{k} module print", module_print_g(k, infill) / 1000, x[k], module_lateral(k)),',
        'return [(f"J{k} module print", module_print_g(k, infill) / 1000 + (p.get("j3_module_print_extra_kg", 0.0) if k == 3 else 0.0), x[k], module_lateral(k)),')
(DST / "joint_loads_mp16.py").write_text(s, encoding="utf-8")
inp = json.loads((SRC / "inputs.json").read_text(encoding="utf-8"))
inp["payloads_kg"] = [0.0, 0.25, 0.5, 0.7, 1.0]
inp["motors"]["NEMA23-76"] = {"frame_mm": 57.0, "holding_Nm": 1.89, "mass_kg": 1.15, "length_mm": 76, "rated_A": 2.8, "driver": "MKS SERVO57D (0-5200 mA)",
                              "source": "ASSUMPTION (MP16) - common 57 x 76 mm hybrid stepper listings (about 1.9 N·m, about 1.1 - 1.2 kg); the MKS bundle listing (Motor Package 2, CAN MT) states no torque or mass on the pages read 2026-11-06"}
(DST / "inputs.json").write_text(json.dumps(inp, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", "with module mass" if mm else "baseline")
