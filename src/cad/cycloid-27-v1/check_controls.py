# -*- coding: utf-8 -*-
"""MP6 검사의 양성 대조 — 일부러 망가뜨린 입력에서 해당 검사가 실제로 실패하는가(검사가 「늘 통과」 하지 않는다는 증거).

계산(C1 ~ C4) — 매개변수 사본(표본을 줄여)을 `cycloid.compute()` 로:
  틈 C −0.05 → 보장 틈 < 0 · 편심 턱 Ø18 → 6801 바깥 고리에 닿음 · 덮개 인서트 깊이 3 → 맞는 나사 없음 · 원판 틈 0.5 → 간격 고리 1.5 ·
  게이지 1.2 → 아래 편심 축이 파일럿까지 밀리면 원판 1 이 나사 머리에 · 고리 하한 0.01 → 와셔가 6800 에 꼭 닿는다고 못 함.
저장 기록(검사 묶음 전체 · 기록 사본만 바꿈):
  계산 산출의 보장 틈을 음수로 → 다시 계산한 값과 달라 C2 실패 · printprep 보고서 없음 · 판 sha 둘 없음 · 판 폭 300 · 판의 부품 지문이 다름 → C7 실패 ·
  SolidCraft 기록이 간섭을 적음 · 기록의 부품 지문이 다름 → C5 실패(저장 기록은 실패 쪽으로만 쓰인다).
부품 형상(커밋된 부품 STL 사본 폴더에 바꾼 STL 을 실제 파일로 쓰고) — `verify_geometry` 가 **그 자리**를 잡는가(어느 쌍 · 어느 구멍) + 검사 묶음 전체 실패:
  덮개 핀 구멍 P0 Ø3.96 · 바닥판 핀 구멍 P0 아래 4 mm 막힘 · 위 편심 축 D 평면 45° · D 구멍 옆면 돌출(L4 R3 F2) · 편심 2 Ø12.6 · 편심 2 바깥 슬리브
  r 6.6 ~ 7.0(L4 R3 F2) · 원판 1 을 1.1 내림(틈 1.0 넘게) · 맞춤 확인 판 핀 구멍 PIN0 을 Ø+0.1 · 캐리어 출력 핀 구멍 P0 의 막힌 끝을 뚫음 · 맞춤 확인 기둥
  PEG00 을 Ø−0.1 · 캐리어 판을 Ø48 로 · (L4-N1) 맞춤 기둥 PEG00 바깥 슬리브 r 6.55 ~ 7.0 · 간격 고리 Ø19(두 6801 바깥 고리 끝면에 닿음) · 덮개 6808 자리
  Ø54 · 바닥판 핀 구멍 P0 의 바닥판 위쪽을 Ø4.8 로 · 캐리어 턱 윗면을 6808 속 고리 밑에서 0.5 내림(받침 없음).
  저장 기록에 메시 폴백 12.5 mm³(요약은 빈 채) → C5 실패(L4-N1 F3) · 「닿음」 행에 메시 12.5 → C5 실패(L4-N2 F2).
  (L4-N2) 덮개 6808 자리 위 지붕(누름 고리에 맞춤 오목) · 덮개 위 덮개(캐노피) · 맞춤 기둥 위 56 mm 의 가로대 → 들어오는 길 검사 실패.
계획 문서: 고정 핀 길이를 한 곳 26 으로 → 계획 대조 실패.
보정 원장: parameters.json 에 보정 키(pin_press_hole_dia)를 적은 사본 → 읽기가 멈춤(값의 출처는 src/cad/calibration/print-fits.json 하나).

사용: python check_controls.py --scratch <저장소 밖 임시 폴더> --out <check-controls.json>
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_cycloid as bd  # noqa: E402
import cycloid as cy  # noqa: E402
import verify_geometry as vg  # noqa: E402

ROOT = cy.DEFAULT_REPO
MODEL = ROOT / "models" / "cycloid-27-v1"
EVID = ROOT / ".dev" / "cycloid-27-evidence" / "build"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    P = cy.load_params(HERE / "parameters.json")
    z = cy.stack(P)
    rows = []

    def add(name, caught, detail):
        rows.append({"control": name, "caught": bool(caught), "detail": detail})
        print(f"{'CAUGHT' if caught else 'MISSED'}  {name}  {detail}")

    # ---- 보정 원장: parameters.json 에 보정 키를 적으면 읽기가 멈추는가(값이 두 곳에 갈라지지 않게) ----
    raw = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    raw["fits"]["pin_press_hole_dia"] = 3.9
    with tempfile.TemporaryDirectory(dir=a.scratch) as tmp:
        (Path(tmp) / "unit").mkdir()
        (Path(tmp) / "calibration").mkdir()
        shutil.copy2(HERE.parent / "calibration" / "print-fits.json", Path(tmp) / "calibration" / "print-fits.json")
        pq = Path(tmp) / "unit" / "parameters.json"
        pq.write_text(json.dumps(raw), encoding="utf-8")
        try:
            cy.load_params(pq)
            refused, why = False, "loaded"
        except ValueError as exc:
            refused, why = True, str(exc)
    add("a calibration key written in parameters.json -> loading refuses (the ledger is the only source)", refused, {"error": why})

    # ---- 계산 ----
    for label, path, value, test in (
            ("profile clearance -0.05 -> guaranteed ring-pin gap < 0 (C2)", ("fits", "profile_clearance"), -0.05,
             lambda o: (o["kinematics"]["disc1"]["ring_pin_gap_guaranteed_min"] < 0, round(o["kinematics"]["disc1"]["ring_pin_gap_guaranteed_min"], 4))),
            ("cam shoulder 18 -> touches the 6801 outer ring (C4)", ("cam", "shoulder_dia"), 18.0,
             lambda o: (any(not x["ok"] for x in o["ring_contacts"]), [x["shoulder"] for x in o["ring_contacts"] if not x["ok"]])),
            ("cap insert depth 3 -> no standard screw (C3)", ("housing", "cap_insert_depth"), 3.0,
             lambda o: (o["screws"]["cap"]["length_mm"] is None, o["screws"]["cap"])),
            ("disc gap 0.5 -> cam spacer 1.5 (C3)", ("disc", "axial_gap"), 0.5,
             lambda o: (o["walls"]["cam_spacer_axial"]["mm"] < P["min_material"] - cy.WALL_EPS, round(o["walls"]["cam_spacer_axial"]["mm"], 3))),
            ("gauge 1.2 -> disc 1 reaches the screw heads if the lower cam slides to the pilot (C4)", ("gauge", "thickness"), 1.2,
             lambda o: (not o["gaps"]["disc1_to_motor_screw_head_if_lower_cam_on_pilot_axial"]["mm"] > 0,
                        round(o["gaps"]["disc1_to_motor_screw_head_if_lower_cam_on_pilot_axial"]["mm"], 3))),
            ("ring min factor 0.01 -> washer not surely on the 6800 inner ring (C4)", ("bearings", "ring_section_min_factor"), 0.01,
             lambda o: (not next(x for x in o["ring_contacts"] if x["shoulder"] == "washer top (under 6800 inner)")["ok"],
                        next(x for x in o["ring_contacts"] if x["shoulder"] == "washer top (under 6800 inner)")["sure_overlap_mm"]))):
        Q = copy.deepcopy(P)
        Q[path[0]][path[1]] = value
        Q["checks"]["kinematic_steps_per_disc_turn"] = 2700
        with tempfile.TemporaryDirectory(dir=a.scratch) as tmp:
            pq = Path(tmp) / "parameters.json"
            pq.write_text(json.dumps(Q), encoding="utf-8")
            caught, detail = test(cy.compute(pq, ROOT))
        add(label, caught, {"value": detail})

    # ---- 저장 기록(검사 묶음 전체) ----
    calc0 = json.loads((MODEL / "cycloid.json").read_text(encoding="utf-8"))
    asm0 = json.loads((EVID / "assembly-checks.json").read_text(encoding="utf-8"))
    plate0 = json.loads((EVID / "print-plate.json").read_text(encoding="utf-8"))
    prep0 = json.loads((MODEL / "slicer" / "print_prep_report.json").read_text(encoding="utf-8"))

    def bundle(cid, calc=calc0, asm=asm0, plate=plate0, prep=prep0, parts=None, prep_missing=False):
        """cid 가 문자열이면 그 행이 FAIL · 튜플이면 그 행들이 모두 FAIL 이어야 잡힘."""
        with tempfile.TemporaryDirectory(dir=a.scratch) as tmp:
            files = {}
            for key, obj in (("calc", calc), ("assembly", asm), ("plate", plate), ("prep", prep)):
                files[key] = Path(tmp) / f"{key}.json"
                if not (key == "prep" and prep_missing):
                    files[key].write_text(json.dumps(obj), encoding="utf-8")
            extra = ["--parts", str(parts)] if parts else []
            q = subprocess.run([sys.executable, str(HERE / "check_cycloid.py"), *[x for k, f in files.items() for x in (f"--{k}", str(f))], *extra],
                               capture_output=True, encoding="utf-8")
        ids = (cid,) if isinstance(cid, str) else cid
        failed = [ln.split()[0] for ln in q.stdout.splitlines() if " FAIL " in ln]
        return q.returncode == 1 and all(c in failed for c in ids), {"returncode": q.returncode, "failed_rows": failed}

    c1 = copy.deepcopy(calc0)
    c1["kinematics"]["disc1"]["ring_pin_gap_guaranteed_min"] = -0.01
    add("stored calc says a negative guaranteed gap -> differs from the recomputation (C2)", *bundle("C2", calc=c1))
    add("printprep report missing (C7)", *bundle("C7", prep_missing=True))
    p2, r2 = copy.deepcopy(plate0), copy.deepcopy(prep0)
    p2.pop("plate_sha256", None)
    r2.get("model", {}).pop("sha256", None)
    add("plate and printprep sha256 both missing (C7)", *bundle("C7", plate=p2, prep=r2))
    p3 = copy.deepcopy(plate0)
    p3["plate_size_mm"][0] = 300.0
    add("plate row 300 mm wider than 280 (C7)", *bundle("C7", plate=p3))
    p4 = copy.deepcopy(plate0)
    p4["source_part_sha256"]["CAM_UPPER"] = "0" * 64
    add("plate report says it was made from a different CAM_UPPER STL (C7)", *bundle("C7", plate=p4))
    s5 = copy.deepcopy(asm0)
    first = next(iter(s5["by_theta"]))
    s5["by_theta"][first]["interference"] = [{"a": "CARRIER", "b": "CAM_UPPER", "volume_mm3": 12.5, "thinnest_mm": 1.0}]
    add(f"the stored SolidCraft record lists an interference ({first}) -> C5 fails (stored records only fail it)", *bundle("C5", asm=s5))
    s6 = copy.deepcopy(asm0)
    s6["part_stl_sha256"]["CAM_UPPER"] = "0" * 64
    add("the stored part fingerprint differs from the committed STL (C5)", *bundle("C5", asm=s6))
    s7 = copy.deepcopy(asm0)
    s7["by_theta"][first]["unchecked_resolved_by_mesh"] = [{"a": "CARRIER", "b": "CAM_UPPER", "mesh_intersection_mm3": 12.5, "reason": "exact kernel failed"}]
    add(f"the stored record's mesh fallback says 12.5 mm3 ({first}, summary left empty - L4-N1 F3) -> C5", *bundle("C5", asm=s7))
    s8 = copy.deepcopy(asm0)
    s8["by_theta"][first]["contacts"] = [{"a": "CARRIER", "b": "CAM_UPPER", "by": "mesh", "mesh_intersection_mm3": 12.5}]
    add(f"the stored record calls a 12.5 mm3 mesh pair a contact ({first} - L4-N2 F2) -> C5", *bundle("C5", asm=s8))

    # ---- 부품 형상: 바꾼 STL 을 실제 파일로 쓴 부품 폴더 사본 ----
    M = vg.m3d()
    holes, _shapes, bosses, _entries = vg.declared(P)
    hole = {(h[0], h[7]): h for h in holes}
    boss = {(b[0], b[6]): b for b in bosses}
    solid = {nm: vg.stl_solid(MODEL / "parts" / f"{nm}.stl") for nm in ("HOUSING_CAP", "HOUSING_BASE", "CAM_UPPER", "DISC_1", "FIT_STRIP", "CARRIER")}
    shaft_shape = {"kind": "d", "r": P["motor"]["shaft_dia"] / 2 + P["fits"]["d_bore_extra"] / 2 + P["fits"]["cam_upper_bore_extra"] / 2,
                   "flat": P["motor"]["shaft_flat_to_axis"] + P["fits"]["d_bore_extra"] / 2 + P["fits"]["cam_upper_bore_extra"] / 2, "ang": math.pi / 2}
    zu0, zu1 = z["cam_upper"]
    cap_p0, base_p0 = hole[("HOUSING_CAP", "P0")], hole[("HOUSING_BASE", "P0")]
    lobe2 = boss[("CAM_UPPER", "LOBE")]
    pin0, car_p0, peg = hole[("FIT_STRIP", "PIN0")], hole[("CARRIER", "P0")], boss[("FIT_STRIP", "PEG00")]
    bore_fill = vg.cyl(2.7, zu0, zu1)
    zt = z["output_bearing"][1]
    cap_roof = vg.ring(24.0, 26.5, zt, zt + 0.2)          # 검수자(L4-N2) 재현: 6808 자리 위 지붕 · 네 곳 r 0.65 구멍
    for ang in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        cap_roof = cap_roof - vg.cyl(0.65, zt - 0.01, zt + 0.21, 25.5 * math.cos(ang), 25.5 * math.sin(ang))
    solid["RETAINER"] = vg.stl_solid(MODEL / "parts" / "RETAINER.stl")
    cases = [
        ("cap pin hole P0 narrowed to 3.96", {"HOUSING_CAP": (solid["HOUSING_CAP"] + vg.cyl(2.2, cap_p0[3], cap_p0[3] + cap_p0[4], cap_p0[1], cap_p0[2]))
                                                            - vg.cyl(1.98, cap_p0[3] - 0.01, cap_p0[3] + cap_p0[4] + 0.01, cap_p0[1], cap_p0[2])},
         ["HOUSING_CAP:P0"], [("HOUSING_CAP", "RING_PIN_0")]),
        ("base pin hole P0 plugged 4 mm at its floor", {"HOUSING_BASE": solid["HOUSING_BASE"] + vg.cyl(base_p0[5] / 2, base_p0[3], base_p0[3] + 4.0,
                                                                                                     base_p0[1], base_p0[2])},
         ["HOUSING_BASE:P0"], [("HOUSING_BASE", "RING_PIN_0")]),
        ("upper cam D flat turned 45", {"CAM_UPPER": (solid["CAM_UPPER"] + bore_fill)
                                                     - vg.section({**shaft_shape, "ang": shaft_shape["ang"] + math.pi / 4}, 0.0, zu0 - 0.01, zu1 + 0.01, 0, 0)},
         ["CAM_UPPER:SHAFT"], [("CAM_UPPER", "MOTOR_D_SHAFT")]),
        ("upper cam D bore side intrusion (L4 R3 F2)", {"CAM_UPPER": solid["CAM_UPPER"] + M.Manifold.cube([1.0, 0.6, zu1 - zu0]).translate([2.1, 0.65, zu0])},
         ["CAM_UPPER:SHAFT"], [("CAM_UPPER", "MOTOR_D_SHAFT")]),
        ("upper cam lobe grown to 12.6", {"CAM_UPPER": (solid["CAM_UPPER"] + vg.cyl(6.3, lobe2[3], lobe2[3] + lobe2[4], lobe2[1], lobe2[2]))
                                                       - vg.section(shaft_shape, 0.0, zu0 - 0.01, zu1 + 0.01, 0, 0)},
         ["CAM_UPPER:LOBE"], [("CAM_UPPER", "BEARING_6801_2")]),
        ("upper cam lobe with an outer sleeve r 6.6 - 7.0 (L4 R3 F2)", {"CAM_UPPER": solid["CAM_UPPER"] + vg.ring(6.6, 7.0, lobe2[3] - 0.2, lobe2[3] + lobe2[4],
                                                                                                                lobe2[1], lobe2[2])},
         [], [("CAM_UPPER", "BEARING_6801_2")]),
        ("disc 1 lowered 1.1 (more than its 1.0 gap)", {"DISC_1": solid["DISC_1"].translate([0, 0, -1.1])},
         [], [("DISC_1", "MOTOR_SCREW_HEAD_0")]),
        ("fit-strip pin hole PIN0 widened by 0.1", {"FIT_STRIP": solid["FIT_STRIP"] - vg.cyl(pin0[5] / 2 + 0.05, pin0[3], pin0[3] + pin0[4] + 0.01, pin0[1], pin0[2])},
         ["FIT_STRIP:PIN0"], []),
        ("carrier output-pin hole P0 drilled through its blind end", {"CARRIER": solid["CARRIER"] - vg.cyl(car_p0[5] / 2, car_p0[3], car_p0[3] + car_p0[4] + 4.0,
                                                                                                         car_p0[1], car_p0[2])},
         ["CARRIER:P0"], []),
        ("fit-strip peg PEG00 thinned by 0.1", {"FIT_STRIP": solid["FIT_STRIP"] - vg.ring(peg[5] - 0.05, peg[5] + 1.0, peg[3], peg[3] + peg[4] + 0.01, peg[1], peg[2])},
         ["FIT_STRIP:PEG00"], []),
        ("carrier plate grown to 48", {"CARRIER": solid["CARRIER"] + vg.ring(22.0, 24.0, z["carrier_plate"][0], z["carrier_plate"][1])},
         [], [("CARRIER", "HOUSING_CAP")]),
        # L4-N1 의 반례 · 그 계열
        ("fit-strip peg PEG00 with a sleeve r 6.55 - 7.0 (L4-N1 F1)", {"FIT_STRIP": solid["FIT_STRIP"] + vg.ring(6.55, 7.0, peg[3] - 0.2, peg[3] + peg[4], peg[1], peg[2])},
         ["FIT_STRIP:PEG00"], []),
        ("cam spacer grown to 19 - touches both 6801 outer rings (L4-N1 F2)",
         {"CAM_UPPER": (solid["CAM_UPPER"] + vg.ring(6.5, 9.5, *z["cam_spacer"])).simplify(1e-5)},
         [], [("CAM_UPPER", "BEARING_6801_1:top:outer"), ("CAM_UPPER", "BEARING_6801_2:bottom:outer")]),
        ("cap 6808 seat widened to 54 (L4-N1 F2)", {"HOUSING_CAP": solid["HOUSING_CAP"] - vg.cyl(27.0, z["output_bearing"][0], z["output_bearing"][1] + 0.01)},
         ["HOUSING_CAP:SEAT6808"], []),
        ("base pin hole P0 widened to 4.8 above the base floor (L4-N1 note)",
         {"HOUSING_BASE": solid["HOUSING_BASE"] - vg.cyl(2.4, z["base_top"], z["joint"] + 0.01, base_p0[1], base_p0[2])},
         ["HOUSING_BASE:P0"], []),
        ("carrier collar top lowered 0.5 under the 6808 inner ring", {"CARRIER": solid["CARRIER"] - vg.ring(19.9, 22.6, z["collar"][1] - 0.5, z["collar"][1] + 0.01)},
         [], [("CARRIER", "BEARING_6808:bottom:inner")]),
        # L4-N2 의 반례 · 그 계열
        ("cap roof over the 6808 seat with a matching retainer recess (L4-N2 F1)",
         {"HOUSING_CAP": (solid["HOUSING_CAP"] + cap_roof).simplify(1e-5), "RETAINER": (solid["RETAINER"] - cap_roof).simplify(1e-5)},
         ["HOUSING_CAP:SEAT6808"], []),
        ("cap canopy over the 6808 seat (L4-N2 F1)",
         {"HOUSING_CAP": (solid["HOUSING_CAP"] + vg.ring(36.6, 39.0, z["output_bearing"][1] - 0.1, z["output_bearing"][1] + 2.9)
                          + vg.ring(24.0, 39.0, z["output_bearing"][1] + 2.7, z["output_bearing"][1] + 2.9)).simplify(1e-5)},
         ["HOUSING_CAP:SEAT6808"], []),
        ("fit-strip bar 56 mm above peg PEG00 on a post outside the bearing's way (L4-N2 note on a fixed 60 mm path)",
         {"FIT_STRIP": (solid["FIT_STRIP"] + M.Manifold.cube([1.0, 2.0, 63.0]).translate([108.0, peg[2] - 1.0, 6.0])
                        + M.Manifold.cube([19.0, 2.0, 2.0]).translate([90.0, peg[2] - 1.0, 67.0])).simplify(1e-5)},
         ["FIT_STRIP:PEG00"], []),
    ]
    import trimesh
    for label, changes, want_features, want_pairs in cases:
        with tempfile.TemporaryDirectory(dir=a.scratch) as tmp:
            pdir = Path(tmp) / "parts"
            shutil.copytree(MODEL / "parts", pdir)
            for nm, man in changes.items():
                raw = man.to_mesh()
                trimesh.Trimesh(vertices=np.asarray(raw.vert_properties)[:, :3], faces=np.asarray(raw.tri_verts), process=False).export(pdir / f"{nm}.stl")
            F = vg.features(P, pdir)
            A = vg.assembly(P, pdir)
            got_pairs = {(r_["a"], r_["b"]) for r_ in A["failed"]} | {(r_["b"], r_["a"]) for r_ in A["failed"]}
            geom_caught = all(f in F["failed"] for f in want_features) and all(pp in got_pairs for pp in want_pairs) and (want_features or want_pairs)
            whole, whole_detail = bundle(tuple(c for c, w in (("C6", want_features), ("C5", want_pairs)) if w), parts=pdir)
        add(f"{label}: the geometry check names it and the whole bundle fails", geom_caught and whole,
            {"features_failed": F["failed"][:6], "assembly_failed_pairs": sorted({(r_["a"], r_["b"]) for r_ in A["failed"]})[:6], "bundle": whole_detail})

    # ---- 계획 문서 ----
    plan = ROOT / "docs" / "design" / "029-cycloid-27-prototype.md"
    pin_len = f"{z['ring_pin'][1] - z['ring_pin'][0]:g}"
    with tempfile.TemporaryDirectory(dir=a.scratch) as tmp:
        bad_plan = Path(tmp) / plan.name
        bad_plan.write_text(plan.read_text(encoding="utf-8").replace(f"Ø4 강철 다월 × **{pin_len}**", "Ø4 강철 다월 × **26**"), encoding="utf-8")
        q = subprocess.run([sys.executable, str(HERE / "check_plan_sync.py"), "--calc", str(MODEL / "cycloid.json"), "--plan", str(bad_plan)],
                           capture_output=True, encoding="utf-8")
    add(f"plan says pin x 26 where the calculator says {pin_len} -> plan sync fails", q.returncode == 1 and "MISSING" in q.stdout, {"returncode": q.returncode})

    out = {"all_caught": all(r_["caught"] for r_ in rows), "controls": rows}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ALL CAUGHT" if out["all_caught"] else "SOME MISSED")
    return 0 if out["all_caught"] else 1


if __name__ == "__main__":
    sys.exit(main())
