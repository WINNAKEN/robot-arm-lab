# -*- coding: utf-8 -*-
"""MP6 검사 묶음 — 계산(cycloid.json) · 조립(assembly-checks.json) · 출력 판(print-plate.json · 판 STL) · 출력 준비(print_prep_report.json — 필수)를
계획 029 의 C1 ~ C8 로 한 표에 판정한다(C9 무접촉은 커밋 도구가 따로). 종료 코드 0 = 모두 통과 · 증거 파일이 없으면 그 항목은 실패.

합격의 근거는 이 묶음이 스스로 계산한 것이다(MP6 L4 R1 · R2 · R3 — 계획 029 「검사 장치 재작성」):
- 계산은 `cycloid.compute()` 로 다시 해서 저장본과 값까지 같아야 한다(다르면 C1 ~ C4 · C8 실패) — 판정은 다시 계산한 값으로.
- 조립(C5) · 부품 형상(C6)은 `verify_geometry` 가 커밋된 부품 STL 만으로 계산한다 — 쌍 · 구멍 · 축 · 기준 입체 목록도 형상 생성기에서 만든다.
  저장된 SolidCraft 기록 · 지문은 실패 쪽으로만 쓴다(간섭을 적었거나 지금 파일과 다르면 실패).
- 출력 판(C7)은 판 STL 의 sha256 을 다시 계산하고, 판을 만든 부품 STL 의 지문을 지금 부품과 견준다.

사용: python check_cycloid.py --calc <cycloid.json> --assembly <assembly-checks.json> --plate <print-plate.json> --prep <print_prep_report.json>
      [--plate-stl <판 STL>] [--parts <부품 STL 폴더>] [--params <parameters.json>] [--out <checks.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_cycloid as bd  # noqa: E402
import cycloid as cy  # noqa: E402
import print_plate as pp  # noqa: E402
import verify_geometry as vg  # noqa: E402

ROW_WIDTH_MAX_MM = 280.0   # H2D 는 노즐 둘이라 한 노즐이 닿는 폭이 판 350 보다 좁다 — 338.5 mm 판을 Bambu Studio 가 「판 밖」 으로 거절(2026-10-25 · 계획 C7)
MODEL = cy.DEFAULT_REPO / "models" / "cycloid-27-v1"


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else None


def first_difference(a, b, path="", tol=1e-9):
    """두 JSON 값이 같은가(수는 tol 안) — 다르면 처음 다른 자리, 같으면 None."""
    if isinstance(a, bool) or isinstance(b, bool):
        return None if a is b else path or "/"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isfinite(a) and math.isfinite(b):
            return None if abs(a - b) <= tol * max(1.0, abs(a), abs(b)) else path or "/"
        return None if a == b else path or "/"
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return f"{path}/{{keys {sorted(set(a) ^ set(b))[:4]}}}"
        for k in a:
            d = first_difference(a[k], b[k], f"{path}/{k}", tol)
            if d:
                return d
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}/[len {len(a)} != {len(b)}]"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]", tol)
            if d:
                return d
        return None
    return None if a == b else path or "/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calc", type=Path, required=True)
    ap.add_argument("--assembly", type=Path, required=True)
    ap.add_argument("--plate", type=Path, required=True)
    ap.add_argument("--prep", type=Path, required=True)
    ap.add_argument("--plate-stl", type=Path, default=MODEL / "print-plate.stl")
    ap.add_argument("--parts", type=Path, default=MODEL / "parts")
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--repo", type=Path, default=cy.DEFAULT_REPO)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    c, s, p, prep = load(a.calc), load(a.assembly), load(a.plate), load(a.prep)
    P = cy.load_params(a.params)
    profile = cy.profile_for(P)[0]
    rows = []

    def add(cid, name, ok, detail):
        rows.append({"id": cid, "check": name, "pass": bool(ok), "detail": detail})

    # ---- C1 ~ C4 · C8: 다시 계산한 값으로 판정 · 저장본이 그것과 같아야 ----
    if c is None:
        for cid in ("C1", "C2", "C3", "C4", "C8"):
            add(cid, "calc evidence", False, {"missing": str(a.calc)})
    else:
        fresh = json.loads(json.dumps(cy.compute(a.params, a.repo)))
        diff = first_difference(c, fresh)
        same = {"stored_calc_equals_recomputed": diff is None, "first_difference": diff}
        pr = fresh["profile"]
        # 로브 끝 곡률 반지름은 계산 방식상 늘 양수라 판정에 쓰지 않는다(첨점 · 고리는 「단순」 이 잡는다 — 기록만)
        add("C1", "profile valid · simple (no cusp or loop) · valley > pin + C · chord error ≤ limit (recomputed)",
            diff is None and pr["valid"] and pr["simple"] and pr["valley_vs_pin_plus_clearance"] > 0 and pr["chord_error_mm"] <= P["checks"]["profile_chord_error_max"],
            {**same, **{k: pr[k] for k in ("points", "chord_error_mm", "lobe_tip_min_curvature_radius", "valley_min_curvature_radius",
                                           "valley_vs_pin_plus_clearance")}})
        k = fresh["kinematics"]
        guaranteed = [float(k[d][kk]) for d in ("disc1", "disc2") for kk in ("ring_pin_gap_guaranteed_min", "output_pin_gap_guaranteed_min")]
        add("C2", "kinematics: guaranteed gap > 0 (both discs · ring and output pins · recomputed)", diff is None and len(guaranteed) == 4 and min(guaranteed) > 0,
            {**same, **{d: {kk: round(float(vv), 4) for kk, vv in k[d].items() if "guaranteed" in kk} for d in ("disc1", "disc2")}})
        mm = P["min_material"]
        bad_w = {n: round(v["mm"], 3) for n, v in fresh["walls"].items() if not v["mm"] >= mm - cy.WALL_EPS}
        bad_s = [n for n, v in fresh["screws"].items() if v["length_mm"] is None]
        add("C3", f"walls ≥ min material ({len(fresh['walls'])} items) · a standard screw length fits every screwed joint ({len(fresh['screws'])})",
            diff is None and not bad_w and not bad_s and bool(fresh["screws"]),
            {**same, "walls_failed": bad_w, "screws_failed": bad_s, "min_wall_mm": round(min(v["mm"] for v in fresh["walls"].values()), 3),
             "screws": {n: v["length_mm"] for n, v in fresh["screws"].items()}})
        bad_g = {n: round(v["mm"], 3) for n, v in fresh["gaps"].items() if not v["mm"] > 0}
        bad_r = [x["shoulder"] for x in fresh["ring_contacts"] if not x["ok"]]
        add("C4", f"moving-vs-fixed gaps > 0 ({len(fresh['gaps'])} items) · each bearing shoulder touches its own ring only ({len(fresh['ring_contacts'])})",
            diff is None and not bad_g and not bad_r,
            {**same, "gaps_failed": bad_g, "ring_contacts_failed": bad_r, "min_gap_mm": round(min(v["mm"] for v in fresh["gaps"].values()), 3),
             "min_ring_margin_mm": min(x["margin_mm"] for x in fresh["ring_contacts"]),
             "min_own_ring_overlap_mm": min(x["sure_overlap_mm"] for x in fresh["ring_contacts"])})
        lr = fresh["loads_rough"]
        add("C8", "loads (rough · record only)", diff is None,
            {**same, **{kk: lr[kk] for kk in ("wrist_max", "shoulder_J2_max_not_this_size", "arms_mm", "output_pin_engagement_mm")}})

    # ---- C5 · C6: 커밋된 부품 STL 만으로 여기서 계산(verify_geometry) · 저장된 기록은 실패 쪽으로만 ----
    try:
        A = vg.assembly(P, a.parts)
        F = vg.features(P, a.parts)
        geom_error = None
    except Exception as exc:          # 부품 STL 이 없거나 읽히지 않으면 실패
        A = F = None
        geom_error = f"{type(exc).__name__}: {exc}"
    record = []
    if s is None:
        record.append(f"missing {a.assembly}")
    else:
        _sc, exp_parts, _refs, _pins = bd.build(P, profile, 0.0)
        names = exp_parts + bd.small_parts(P)[1]
        gen_now = {**{pth.name: bd.file_sha256(pth) for pth in (a.params, HERE / "cycloid.py", HERE / "build_cycloid.py")},
                   "fit_calibration_values": P["fits"]["calibration"]["values_sha256"]}
        if s.get("generator_sha256") != gen_now:
            record.append("the build record was made by another generator or parameters")
        if s.get("part_stl_sha256") != {nm: (bd.file_sha256(a.parts / f"{nm}.stl") if (a.parts / f"{nm}.stl").exists() else None) for nm in names}:
            record.append("the part STLs are not the ones the build record was made from")
        for tag, v in (s.get("by_theta") or {}).items():       # 저장 기록에 적힌 불합격 값은 무엇이든 실패(L4-N1 F3 — 요약 목록만 읽지 않는다)
            if v.get("interference"):
                record.append(f"{tag}: the SolidCraft exact-kernel record lists interference {[(x.get('a'), x.get('b')) for x in v['interference']][:4]}")
            for x in v.get("unchecked_resolved_by_mesh", []):
                mv = x.get("mesh_intersection_mm3")
                if not (isinstance(mv, (int, float)) and math.isfinite(mv) and mv <= bd.MESH_CONTACT_MM3):
                    record.append(f"{tag}: the record's mesh fallback {x.get('a')}~{x.get('b')} = {mv}")
            for x in v.get("contacts", []):      # 메시로 가른 「닿음」 도 그 교차값으로(L4-N2 F2)
                if "mesh_intersection_mm3" in x or x.get("by"):
                    mv = x.get("mesh_intersection_mm3")
                    if not (isinstance(mv, (int, float)) and math.isfinite(mv) and mv <= bd.MESH_CONTACT_MM3):
                        record.append(f"{tag}: the record calls {x.get('a')}~{x.get('b')} a contact but its mesh intersection is {mv}")
                elif not (isinstance(x.get("thinnest_mm"), (int, float)) and x["thinnest_mm"] <= bd.CONTACT_MM):
                    record.append(f"{tag}: the record calls {x.get('a')}~{x.get('b')} a contact but it is {x.get('thinnest_mm')} thick")
            st = v.get("interference_stats", {})
            if st.get("pairs_not_checked", 0) != 0 or st.get("budget_exceeded") is True or st.get("truncated") is True:
                record.append(f"{tag}: the record says pairs were left unchecked {st}")
    add("C5", "assembly computed here from the committed part STLs at 0 · 45 · 90° — every part pair · 28 fixed pins · 6 output pins · bearing spaces · "
              "motor D shaft / pilot / body / screw heads × every part ≤ 0.01 mm3 · bearing ring end faces: no other-speed part, designed supports present "
              "(the stored SolidCraft record and fingerprints can only fail it)",
        A is not None and A["ok"] and not record,
        {"error": geom_error, "build_record_problems": record,
         **({k: A[k] for k in ("thetas", "pairs_part_part", "pairs_reference", "ring_face_forbidden", "ring_face_required", "rows", "max_part_part_mm3",
                               "max_reference_mm3", "max_ring_face_forbidden_mm3", "min_ring_face_required_mm3", "failed")} if A else {}),
         "fit_gap_mm": vg.FIT_GAP_MM, "limit_mm3": vg.LIMIT_MM3})
    add("C6", "declared holes and bearing-seat shafts by solid containment on the committed STLs — hole core empty · skin full · blind floor full · "
              f"each hole's way in empty · shaft shell full · the bearing's whole way in empty ({F['holes'] if F else '?'} holes · {F['shafts'] if F else '?'} shafts from the generator)",
        F is not None and F["ok"],
        {"error": geom_error, **({k: F[k] for k in ("holes", "shafts", "failed", "worst")} if F else {}), "fit_gap_mm": vg.FIT_GAP_MM,
         "shell_mm": vg.SHELL_MM, "path_beyond_part_mm": vg.PATH_BEYOND_MM, "floor_mm": vg.FLOOR_MM, "limit_mm3": vg.LIMIT_MM3})

    # ---- C7: 판 STL 의 sha256 을 다시 계산 ----
    if p is None or prep is None or not a.plate_stl.exists():
        add("C7", "print evidence", False, {"missing": [str(x) for x, y in ((a.plate, p), (a.prep, prep)) if y is None]
                                            + ([] if a.plate_stl.exists() else [str(a.plate_stl)])})
    else:
        sha_file = hashlib.sha256(a.plate_stl.read_bytes()).hexdigest()
        sha_p, sha_r = p.get("plate_sha256"), prep.get("model", {}).get("sha256")
        sha_ok = isinstance(sha_p, str) and len(sha_p) == 64 and sha_p == sha_r == sha_file
        row_ok = p["plate_size_mm"][0] <= ROW_WIDTH_MAX_MM
        # 판이 지금 부품 STL 에서 나왔는가(MP6 L4 R2 F2): 판 보고서의 부품별 sha256 = 지금 파일 · 판의 부품 = 판 생성기 목록
        src = p.get("source_part_sha256") or {}
        plate_names = [nm for nm, _cnt in pp.PLATE]
        src_ok = set(src) == set(plate_names) and all((a.parts / f"{nm}.stl").exists() and src[nm] == bd.file_sha256(a.parts / f"{nm}.stl")
                                                      for nm in plate_names)
        count_ok = sorted(x["name"].split("#")[0] for x in p["parts"]) == sorted(nm for nm, cnt in pp.PLATE for _k in range(cnt))
        ok = (p["fits_bed"] and row_ok and not p["bbox_overlaps"] and all(x["watertight"] for x in p["parts"]) and prep.get("verdict") == "ready"
              and prep.get("support", {}).get("advised_by_studio") is False and sha_ok and src_ok and count_ok)
        add("C7", f"print plate made from the current part STLs · fits · row width ≤ {ROW_WIDTH_MAX_MM:g} · no overlaps · watertight · printprep ready "
                  "for this plate STL (sha256 re-hashed) · no advised support", ok,
            {"plate_size_mm": [round(v, 1) for v in p["plate_size_mm"]], "row_width_max_mm": ROW_WIDTH_MAX_MM, "row_width_used_mm": p.get("row_width_mm"),
             "plate_stl_sha256": sha_file, "plate_report_and_prep_match_the_file": sha_ok, "plate_made_from_current_part_stls": src_ok,
             "plate_part_list_matches_generator": count_ok,
             "printprep": {"verdict": prep.get("verdict"), "support": prep.get("support"), "estimate": prep.get("estimate")}})
    out = {"all_pass": all(r["pass"] for r in rows) and len(rows) == 8, "rows": sorted(rows, key=lambda r: r["id"])}
    for r in out["rows"]:
        print(f"{r['id']} {'PASS' if r['pass'] else 'FAIL'}  {r['check']}")
    print("ALL PASS" if out["all_pass"] else "SOME FAIL")
    if a.out:
        a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
