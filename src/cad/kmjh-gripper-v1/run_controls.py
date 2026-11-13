# -*- coding: utf-8 -*-
"""MP8 — 그리퍼 KG1 양성 대조: 일부러 넣은 잘못을 검사가 잡는지 — 거짓이 된 키 집합이 밝힌 기대 키 집합과 꼭 같고(실행 전에 까닭과 함께 적음),
G2 계열은 넘은 쌍 이름에 겨냥한 쌍이 들어 있어야 한다(want_pairs).

모든 대조는 격리 작업 뿌리(표지 MP8_SCRATCH)의 사본에서만 한다 — 실 저장소의 산출 · 근거는 읽기만(MP7 교훈 · 가드 시험은 가드 함수만).
형상 대조는 STL 을 바꾼 뒤 사본 기록의 출력 sha256 · 출력 준비 기록 · 질량 기록의 부품 sha256 도 그 파일로 맞춰(G0 가 함께 거짓이 되지 않게) 목표만 보게 한다.
parameters 를 바꾸는 대조는 사본 parameters 를 --params 로 주고 기록의 입력 sha256 도 맞춘다(실 파일은 그대로).
가드 대조는 꾸민 저장소 자리(표지 폴더)에서 guard 함수만 부르고, 거부 사유 조각까지 본다.

사용: python run_controls.py --scratch-root <작업 뿌리> [--out <json>] [--only <이름…>]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

ROOT = guard.find_root(HERE)
MODEL = ROOT / "models" / "kmjh-gripper-v1"
EVID = ROOT / ".dev" / "mp8-evidence" / "gripper"
U = ["0", "47"]
SCRATCH = None            # main() 에서 정함 — 사본 지우기 · 쓰기에 가드를 씀


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fresh_copy(dst):
    """기록의 출력 + 출력 준비 산출(판 STL · 슬라이서 파일 · 질량 기록) + 근거(만들기 기록 · 출력 준비 기록)를 사본으로."""
    if dst.exists():
        guard.safe_rmtree(dst, ROOT, SCRATCH)
    (dst / "model" / "parts").mkdir(parents=True)
    (dst / "ev").mkdir()
    rec = json.loads((EVID / "build-record.json").read_text(encoding="utf-8"))
    for rel in rec["outputs_sha256"]:
        (dst / "model" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MODEL / rel, dst / "model" / rel)
    for p in MODEL.glob("print-plate-*.stl"):
        shutil.copy2(p, dst / "model" / p.name)
    shutil.copy2(MODEL / "mass-properties.json", dst / "model" / "mass-properties.json")
    for p in (MODEL / "slicer").rglob("*"):
        if p.is_file():
            q = dst / "model" / p.relative_to(MODEL)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
    shutil.copy2(EVID / "print-prep.json", dst / "ev" / "print-prep.json")
    return rec


def write_rec(dst, rec):
    (dst / "ev" / "build-record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def edit_json(p, fn):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    fn(d)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def mutate_stl(dst, rec, name, fn):
    p = dst / "model" / "parts" / f"{name}.stl"
    m = trimesh.load(p, force="mesh")
    m = fn(m)
    m.export(p)
    h = sha(p)
    rec["outputs_sha256"][f"parts/{name}.stl"] = h

    def pp(d):
        if name in d.get("per_part", {}):
            d["per_part"][name]["stl_sha256"] = h

    def mp(d):
        if name in d.get("parts_sha256", {}):
            d["parts_sha256"][name] = h
    edit_json(dst / "ev" / "print-prep.json", pp)
    edit_json(dst / "model" / "mass-properties.json", mp)


def params_copy(dst, rec, fn):
    """사본 parameters(바꾼 것) — 기록의 입력 sha256 도 맞춘다."""
    P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    fn(P)
    p = dst / "parameters.json"
    p.write_text(json.dumps(P, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rec["inputs_sha256"]["parameters.json"] = sha(p)
    return rec


def run_verify(dst, u=U):
    out = dst / "verify.json"
    cmd = [sys.executable, str(HERE / "verify_gripper.py"), "--model", str(dst / "model"), "--evidence", str(dst / "ev"),
           "--out", str(out), "--scratch-root", str(SCRATCH), "--u", *u]
    if (dst / "parameters.json").is_file():
        cmd += ["--params", str(dst / "parameters.json")]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3600)
    if not out.is_file():
        return {"_error": (p.stderr or p.stdout)[-1500:]}, {}
    d = json.loads(out.read_text(encoding="utf-8"))
    return d["checks"], d["numbers"]


def translate(v):
    return lambda m: m.apply_translation(v) or m


def move_body(dst, rec, name, v):
    """부품 STL 을 v 만큼 옮기고, 기록이 선언한 그 부품의 구멍 자리도 같이 옮긴다(구멍 검사가 덩달아 거짓이 되지 않게 — 목표만 보게)."""
    mutate_stl(dst, rec, name, translate(v))
    idx = {"x": (1, 2, 0), "y": (0, 2, 1), "z": (0, 1, 2)}
    for h in rec["holes"]:
        if h["body"] != name:
            continue
        i1, i2, ia = idx[h["axis"]]
        h["c"] = [h["c"][0] + v[i1], h["c"][1] + v[i2]]
        h["span"] = [h["span"][0] + v[ia], h["span"][1] + v[ia]]
        if "bearing_spans" in h:
            h["bearing_spans"] = [[s0 + v[ia], s1 + v[ia]] for s0, s1 in h["bearing_spans"]]
    return rec


def ledge(m):
    """턱 B 에 받침 없는 처마(z 를 위로 출력할 때 +y 로 10 mm 나간 수평 판)를 붙인다."""
    b = trimesh.creation.box(extents=[20.0, 10.0, 2.0])
    b.apply_translation([-30.0, 23.5 + 5.0, 51.0])
    return trimesh.boolean.union([m, b], engine="manifold")


def lump(xr, yr, zr):
    """부품에 따로 떨어진(또는 면만 닿는) 상자 하나를 더한다."""
    def f(m):
        b = trimesh.creation.box(extents=[xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0]])
        b.apply_translation([(xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2])
        return trimesh.util.concatenate([m, b])
    return f


def ring_behind_pinion(m):
    """피니언 허브 뒷면(y −6)에 0.3 두께 고리(반지름 8.8 ~ 9.8 — 나사 · 가운데 구멍을 비킴)를 붙인다 = 혼 바깥면 안으로 0.3."""
    a = trimesh.creation.annulus(r_min=8.8, r_max=9.8, height=0.3, sections=96)     # +z 축 · 가운데 원점
    a.apply_transform(np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float))   # z → −y
    a.apply_translation([0.0, -6.15, 26.0])
    return trimesh.util.concatenate([m, a])


def steep(m):
    """턱 B 에 아래 면이 22° 로 눕은 쐐기(가파른 처마)를 붙인다."""
    from shapely.geometry import Polygon
    prof = Polygon([(23.5, 50.0), (23.5, 54.0), (33.5, 54.0)])
    w = trimesh.creation.extrude_polygon(prof, 20.0)          # (y, z) 단면을 +z 로 — 축을 돌려 x 로
    w.apply_transform(np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float))
    w.apply_translation([-40.0, 0, 0])
    return trimesh.boolean.union([m, w], engine="manifold")


def setp(path, value):
    def f(P):
        d = P
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = value
    return f


G2ALL = {"G2_no_interference", "G2_moving_pairs_clear_by_delta", "G2_variants_no_interference"}
P6 = 6.0 * np.pi * 1.5        # 랙 A 의 여섯째 이 사이 가운데(국소 x)

# (이름, 기대 거짓 키 집합, 준비 함수(dst, rec) → rec, --u, want_pairs{숫자 키: 들어 있어야 할 쌍}) — 기대 집합은 실행 전에 까닭과 함께 적었다
CASES = [
    # 턱 A 를 0.6 내림 = 랙이 피니언에 박힘(G3 둘) · 슬리브 구멍이 관 축에서 비킴(관과 겹침 · G8 축) · 손끝 대가 턱 B 슬리브에 0.1 걸림(G2 · 턱 B 를 못 뺌 G8 둘) ·
    # 쐐기가 벽 꼭대기에 0.1 걸림 — 겹친 채라 δ · 놀음 끝 검사도 거짓
    ("jaw_a_rack_into_pinion", G2ALL | {"G3_mesh_no_interference_sampled", "G3_min_backlash_under_play", "G8_jaw_b_slides_out",
                                        "G8_jaw_b_slides_with_jaw_a_sagged", "G8_rods_coaxial_posts_sleeves"},
     lambda d, r: move_body(d, r, "JAW_A", [0, 0, -0.6]), U, {"G2_over_limit": ["JAW_A|PINION"]}),
    # 턱 A 를 0.45 올림 = 랙이 피니언에서 떨어짐(0.4 밀어도 백래시 0.275 를 못 넘음 — G3 물림) · 관이 구멍 밖으로 비킴(놀음 0.145 — G2 셋 · G8 축).
    # (2026-10-28 첫 실행은 1.0 이었는데, 슬리브 위가 손끝 밑 · 물체 상자 밑(0.5 위)을 넘어 G4 물체 상자도 거짓이 됐다 — 겨냥을 좁히려고 0.45 로 바꿈)
    ("jaw_a_rack_lifted_disengaged", G2ALL | {"G3_mesh_engaged_sampled", "G8_rods_coaxial_posts_sleeves"},
     lambda d, r: move_body(d, r, "JAW_A", [0, 0, 0.45]), U, {"G2_over_limit": ["JAW_A|ROD_-15.0"]}),
    # 손끝 A 를 +x 0.5 = 닫힘에서 손끝 B 와 겹침(G2 셋 · 행정 2u) · 손끝 구멍이 나사 몸통에서 0.5 비킴
    ("pad_a_into_pad_b", G2ALL | {"G4_gap_equals_2u"}, lambda d, r: move_body(d, r, "PAD_A_FLAT", [0.5, 0, 0]), U,
     {"G2_over_limit": ["PAD_A|PAD_B", "PAD_A|PAD_A_SHANK_0"]}),
    # 피니언 허브 뒤 고리 0.3 = 혼 바깥면 안으로(같이 도는 묶음이라 δ · 놀음 끝 검사는 이 쌍을 안 봄) — 혼 기준 입체가 살아 있는지
    ("pinion_ring_into_horn", {"G2_no_interference"}, lambda d, r: (mutate_stl(d, r, "PINION", ring_behind_pinion), r)[1], U,
     {"G2_over_limit": ["PINION|HORN"]}),
    # 행정을 기둥 너머로(u 52) = 턱 A 슬리브가 L 기둥에 겹침
    ("stroke_past_posts_u52", G2ALL, lambda d, r: r, ["0", "52"], {"G2_over_limit": ["BASE|JAW_A"]}),
    # 손끝 B_V 파일 · 기록 키를 지움 = 부품 표 · 출력 키 집합 · 출력 준비 기록이 거짓 · 그 손끝 조합을 못 보므로 G2 셋 · 물체 상자도 거짓
    ("part_missing_pad_b_v", G2ALL | {"G1_part_list_matches_independent_table", "G4_object_box_fits", "G0_output_keys_match_independent_set",
                                      "G0_print_prep_matches_outputs"},
     lambda d, r: ((d / "model" / "parts" / "PAD_B_V.stl").unlink(), r["outputs_sha256"].pop("parts/PAD_B_V.stl"), r)[2], U, {}),
    # 기록이 구멍이라 한 자리에 구멍이 없음(손끝 인서트 둘 사이 z 82 — 재료가 꽉 참)
    ("insert_hole_recorded_where_solid", {"G5_holes_empty"},
     lambda d, r: (next(h for h in r["holes"] if h["kind"] == "insert" and h["body"] == "JAW_A")["c"].__setitem__(1, 82.0), r)[1], U, {}),
    # 기록 지름이 원장 · 실제 구멍(4.0)과 다름 — 지름 검사 + 둘레 탐침(껍질이 실제 구멍 안으로 들어가 재료가 모자람)
    ("insert_dia_recorded_3p8", {"G5_hole_dias_equal_source", "G5_holes_have_walls"},
     lambda d, r: (next(h for h in r["holes"] if h["kind"] == "insert").__setitem__("dia", 3.8), r)[1], U, {}),
    # 축을 z 로 적으면 출력 방향(y 위)에서 가로 구멍 — 같은 수가 (x, y) 로 읽혀 부품 밖을 재므로 둘레 재료도 없음
    ("insert_axis_horizontal_in_print", {"G5_inserts_vertical_in_print", "G5_holes_have_walls"},
     lambda d, r: (next(h for h in r["holes"] if h["kind"] == "insert" and h["body"] == "JAW_A").__setitem__("axis", "z"), r)[1], U, {}),
    ("hole_count_one_insert_dropped", {"G5_counts_match_independent_table"},
     lambda d, r: (r["holes"].remove(next(h for h in r["holes"] if h["kind"] == "insert" and h["body"] == "JAW_B")), r)[1], U, {}),
    ("record_fits_differ_from_ledger", {"G0_fits_used_equal_ledger"}, lambda d, r: (r["fits_used"].__setitem__("rod_slide_hole_dia", 6.3), r)[1], U, {}),
    ("record_input_hash_differs", {"G0_inputs_match_record"}, lambda d, r: (r["inputs_sha256"].__setitem__("kg1.py", "0" * 64), r)[1], U, {}),
    ("output_changed_without_record", {"G0_outputs_match_record"},
     lambda d, r: (lambda rr: (rr["outputs_sha256"].__setitem__("parts/BASE.stl", "0" * 64), rr)[1])(r), U, {}),
    ("unsupported_ledge_on_jaw_b", {"G6_bridges_short"}, lambda d, r: (mutate_stl(d, r, "JAW_B", ledge), r)[1], U, {}),
    # 조립 경로를 막는 혹(제자리에서는 아무것과도 0.3 넘게 떨어짐): 턱 B 에 피니언 뒤(y −5.6 ~ −5.2 · 반지름 ≥ 11 · 판(z 6.5)부터 서는 기둥)
    ("jaw_b_lump_blocks_slide", {"G8_jaw_b_slides_out", "G8_jaw_b_slides_with_jaw_a_sagged"},
     lambda d, r: (mutate_stl(d, r, "JAW_B", lump([11.0, 14.0], [-5.6, -5.2], [6.5, 28.0])), r)[1], U, {}),
    # 턱 A 에 피니언 허브 아래(y −5.65 ~ −5.35 · z 8 ~ 10 · 넓이 4 mm² — 출력 한계 5 아래) = 위로 빼면 허브에 걸림
    ("jaw_a_lump_blocks_lift", {"G8_jaw_a_lifts_out"},
     lambda d, r: (mutate_stl(d, r, "JAW_A", lump([-1.0, 1.0], [-5.65, -5.35], [8.0, 10.0])), r)[1], U, {}),
    # 기록의 슬리브 구멍 축을 1 mm 옮김 — 축 일치 검사 + 그 자리 탐침(안 · 둘레)이 함께 잡는다
    ("record_rod_bore_moved", {"G8_rods_coaxial_posts_sleeves", "G5_holes_empty", "G5_holes_have_walls"},
     lambda d, r: (next(h for h in r["holes"] if h["kind"] == "rod_slide" and h["body"] == "JAW_A")["c"].__setitem__(1, 51.0), r)[1], U, {}),
    ("steep_underside_on_jaw_b", {"G6_no_steep_overhang"}, lambda d, r: (mutate_stl(d, r, "JAW_B", steep), r)[1], U, {}),
    # --- 검토 뒤 더한 대조 ---
    # δ: 턱 B 세운 벽 앞에 0.3 판(y 5.2 ~ 5.5) = 피니언 앞면(5)과 0.2 — 겹침은 없고 δ 0.3 에서만 걸림(놀음 끝 −0.125 도 0.075 남음)
    ("delta_gap_jaw_b_plate", {"G2_moving_pairs_clear_by_delta"},
     lambda d, r: (mutate_stl(d, r, "JAW_B", lump([-20.0, -10.0], [5.2, 5.5], [20.0, 30.0])), r)[1], U, {"G2_delta_over_limit": ["JAW_B|PINION"]}),
    # 놀음 끝: 혼 높이 범위를 1.85 ~ 3.0 으로(사본 parameters) = 낮은 끝에서 피니언 뒤가 쐐기에 0.15 박힘(놀음 끝 G2 · 턱 A 를 못 뺌 G8) ·
    # 피니언 나사 끝이 서보 몸체에 0.15 들어감(구매품 쌍)
    ("horn_range_wider", {"G2_variants_no_interference", "G8_jaw_a_lifts_out", "G2_purchased_pair_checks"},
     lambda d, r: params_copy(d, r, setp(["servo", "horn_face_above_body_top"], [1.85, 3.0])), U, {"G2_variant_over_limit": ["horn_low:JAW_A|PINION"]}),
    # 최소 백래시: 관 지름을 5.6 으로(사본 parameters) = 슬리브 놀음 0.325 + 피니언 비킴 0.1 > 백래시 0.275(G3 최소 백래시 · 맞물림 놀음 끝 G2)
    ("backlash_eaten_by_play", {"G3_min_backlash_under_play", "G2_variants_no_interference"},
     lambda d, r: params_copy(d, r, setp(["rod", "od"], 5.6)), U, {"G2_variant_over_limit": ["mesh_a_tight:JAW_A|PINION"]}),
    # 위상 표본: 랙 A 여섯째 이 사이 바닥 0.85 를 메움 — 표본 u 0 · 47 에서는 피니언에서 멀고 위상 표본(23.5 ~ 28.25)에서만 피니언 이끝에 닿음
    ("rack_gap_filled_between_samples", {"G3_mesh_no_interference_sampled", "G3_min_backlash_under_play"},
     lambda d, r: (mutate_stl(d, r, "JAW_A", lump([P6 - 0.5, P6 + 0.5], [-5.0, 5.0], [40.6, 41.45])), r)[1], U, {}),
    # M2 홈을 메움(아래 x 8.3 자리) — 홈 탐침(G5) · 서보 나사 몸통 기준 입체(G2)가 함께 잡는다
    ("m2_slot_filled", {"G5_holes_empty", "G2_no_interference"},
     lambda d, r: (mutate_stl(d, r, "BASE", lump([7.3, 9.3], [-9.0, -7.8], [15.0, 16.7])), r)[1], U, {"G2_over_limit": ["BASE|M2_SHANK_18.41_-1"]}),
    # 물체 상자 높이 60(사본 parameters) = 손끝 끝에서 60 이면 슬리브(z 46 ~ 58)에 닿음
    ("object_box_taller", {"G4_object_box_fits"}, lambda d, r: params_copy(d, r, setp(["pad", "object_box"], [80.0, 20.0, 60.0])), U, {}),
    # 출력 준비 기록이 옛 부품을 가리킴
    ("print_prep_stale", {"G0_print_prep_matches_outputs"},
     lambda d, r: (edit_json(d / "ev" / "print-prep.json", lambda p: p["per_part"]["JAW_A"].__setitem__("stl_sha256", "0" * 64)), r)[1], U, {}),
    # 기록에서 출력 키 하나(3MF)를 뺌 — 남은 키는 다 맞으므로 출력 일치 검사는 참, 키 집합 검사만 거짓
    ("output_key_missing", {"G0_output_keys_match_independent_set"}, lambda d, r: (r["outputs_sha256"].pop("kmjh-gripper-v1.3mf"), r)[1], U, {}),
    # 턱 A 손끝 대 밑 0.3 판(z 58.2 ~ 58.5) = 턱 B 슬리브 위와 0.2 — 겹침 없음 · δ 에서 걸림 · 관 없는 턱 A 가 0.3 처지면 턱 B 를 못 넣음
    ("jaw_a_sag_blocks_b", {"G2_moving_pairs_clear_by_delta", "G8_jaw_b_slides_with_jaw_a_sagged"},
     lambda d, r: (mutate_stl(d, r, "JAW_A", lump([-13.0, -5.0], [1.0, 9.0], [58.2, 58.5])), r)[1], U, {"G2_delta_over_limit": ["JAW_A|JAW_B"]}),
    # 넣는 쪽을 R 로(사본 parameters) = 기록은 L 미끄럼 · R 고정이라 끼움 쪽 검사만 거짓(관 축 · 구멍 지름은 그대로)
    ("rod_insert_side_swapped", {"G8_rod_fit_sides"}, lambda d, r: params_copy(d, r, setp(["rod", "insert_from"], "R")), U, {}),
    # 구멍 축 위 처마: 턱 B 관 축(y 10.5 · z 52)에서 3.2 위 · 슬리브 끝 밖에 뜬 판(넓이 6 mm²) — 옛 구멍 가림(축 방향 범위 없음 · 반지름 3.245)이면 빠졌던 자리
    ("overhang_on_hole_axis", {"G6_bridges_short"},
     lambda d, r: (mutate_stl(d, r, "JAW_B", lump([-61.5, -55.5], [10.0, 11.0], [55.2, 55.7])), r)[1], U, {}),
]


def guard_cases(sroot):
    """가드 함수만 — 꾸민 저장소(표지 폴더 · git 밖)에서. 거부는 사유 조각까지 본다."""
    fake = sroot / "fake-repo"
    for rel in ("models/kmjh-gripper-v1/hl.txt", "models/kmjh-gripper-v1/tree/hl2.txt"):   # 앞 실행이 중간에 멈춰 남긴 하드 링크(safe_rmtree 가 거부함)
        if (fake / rel).is_file():
            os.unlink(fake / rel)
    if fake.exists():
        guard.safe_rmtree(fake, ROOT, SCRATCH)
    (fake / "models" / "armold-mks-concept-v1").mkdir(parents=True)
    (fake / "src" / "cad").mkdir(parents=True)
    for rel in guard.PROTECTED_REL + guard.ALLOWED_REL:
        (fake / rel).mkdir(parents=True, exist_ok=True)
    sc_ok = sroot / "scr-ok"
    sc_ok.mkdir(exist_ok=True)
    (sc_ok / guard.MARKER).write_text("", encoding="utf-8")
    sc_bad = sroot / "scr-nomarker"
    sc_bad.mkdir(exist_ok=True)
    res = []

    def refuses(name, fn, why):
        try:
            fn()
            res.append({"case": name, "refused": False, "ok": False})
        except SystemExit as e:
            res.append({"case": name, "refused": True, "why": str(e)[:200], "want_why": why, "ok": why in str(e)})

    def allows(name, fn):
        try:
            fn()
            res.append({"case": name, "refused": False, "ok": True})
        except SystemExit as e:
            res.append({"case": name, "refused": True, "why": str(e)[:200], "ok": False})

    allows("model folder allowed", lambda: guard.checked_dir(fake / "models" / "kmjh-gripper-v1" / "parts", fake, sc_ok))
    allows("evidence folder allowed", lambda: guard.checked_dir(fake / ".dev" / "mp8-evidence" / "gripper", fake, sc_ok))
    allows("scratch with marker allowed", lambda: guard.checked_dir(sc_ok / "x", fake, sc_ok))
    allows("verify --out into the evidence folder without a scratch root", lambda: guard.checked_file(fake / ".dev" / "mp8-evidence" / "gripper" / "verify.json", fake, None))
    for rel in guard.PROTECTED_REL:
        refuses(f"protected {rel}", lambda rel=rel: guard.checked_dir(fake / rel / "x", fake, sc_ok), "protected folder")
    refuses("above a protected folder (models)", lambda: guard.checked_dir(fake / "models", fake, sc_ok), "protected folder")
    refuses("other repo folder", lambda: guard.checked_dir(fake / "docs", fake, sc_ok), "outside the gripper output")
    refuses("ledger file in calibration", lambda: guard.checked_file(fake / "src" / "cad" / "calibration" / "print-fits.json", fake, sc_ok), "protected folder")
    refuses("verify --out = ledger (no scratch root)", lambda: guard.checked_file(fake / "src" / "cad" / "calibration" / "print-fits.json", fake, None),
            "protected folder")
    refuses("scratch path without a scratch root", lambda: guard.checked_file(sc_ok / "verify.json", fake, None), "outside the gripper output")
    refuses("scratch without marker", lambda: guard.checked_dir(sc_bad / "x", fake, sc_bad), "marker file")
    refuses("scratch = repo itself", lambda: ((fake / guard.MARKER).write_text(""), guard.checked_dir(fake / "models" / "kmjh-gripper-v1", fake, fake)),
            "holds a protected path")
    # 겹침 분기: 꾸민 저장소 안 하위 폴더(보호 경로를 품지 않고 .git 도 없음)를 작업 뿌리로
    sub = fake / "scratch-inside"
    sub.mkdir(exist_ok=True)
    (sub / guard.MARKER).write_text("", encoding="utf-8")
    refuses("scratch inside the repository", lambda: guard.checked_dir(sub / "x", fake, sub), "outside the repository")
    gitd = sroot / "scr-git"
    (gitd / ".git").mkdir(parents=True, exist_ok=True)
    (gitd / guard.MARKER).write_text("", encoding="utf-8")
    refuses("scratch inside a git tree", lambda: guard.checked_dir(gitd / "x", fake, gitd), "git work tree")
    # 하드 링크 파일(보호 폴더 파일과 바이트 공유)
    prot = fake / "models" / "armold-mks-product-v3" / "keep.txt"
    prot.write_text("keep", encoding="utf-8")
    hl = fake / "models" / "kmjh-gripper-v1" / "hl.txt"
    if hl.exists():
        hl.unlink()
    try:
        os.link(prot, hl)
        refuses("hard-linked file", lambda: guard.checked_file(hl, fake, sc_ok), "hard link")
        tree = fake / "models" / "kmjh-gripper-v1" / "tree"
        tree.mkdir(exist_ok=True)
        os.link(prot, tree / "hl2.txt")
        refuses("rmtree over a hard link", lambda: guard.safe_rmtree(tree, fake, sc_ok), "hard link")
        res.append({"case": "protected file untouched after refusals", "ok": prot.read_text(encoding="utf-8") == "keep"})
        os.unlink(tree / "hl2.txt")
        os.unlink(hl)
    except OSError as e:
        res.append({"case": "hard link", "ok": None, "not_covered": f"os.link failed: {e}"})
    # 정션(폴더 링크)
    j = fake / "models" / "kmjh-gripper-v1" / "junc"
    p = subprocess.run(["cmd", "/c", "mklink", "/J", str(j), str(fake / "models" / "armold-mks-product-v3")], capture_output=True, text=True)
    if p.returncode == 0:
        refuses("path through a junction", lambda: guard.checked_dir(j / "x", fake, sc_ok), "link or junction")
        os.rmdir(j)
    else:
        res.append({"case": "junction", "ok": None, "not_covered": (p.stderr or p.stdout)[:200]})
    return res


def main():
    global SCRATCH
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=EVID / "controls.json")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    SCRATCH = a.scratch_root
    sroot = guard._scratch(ROOT, a.scratch_root)
    croot = guard.checked_dir(sroot / "controls", ROOT, a.scratch_root)
    croot.mkdir(parents=True, exist_ok=True)
    results = []
    for name, want, prep, u, want_pairs in CASES:
        if a.only and name not in a.only:
            continue
        dst = croot / name
        rec = fresh_copy(dst)
        rec = prep(dst, copy.deepcopy(rec)) or rec
        write_rec(dst, rec)
        checks, nums = run_verify(dst, u)
        if "_error" in checks:
            results.append({"case": name, "ok": False, "error": checks["_error"]})
            print(name, "ERROR", checks["_error"][-300:])
            continue
        false = {k for k, v in checks.items() if not v}
        pairs_ok, pairs_got = True, {}
        for key, pl in want_pairs.items():
            got = sorted(nums.get(key, {}))
            pairs_got[key] = got
            pairs_ok = pairs_ok and all(p in got for p in pl)
        ok = false == want and pairs_ok
        results.append({"case": name, "want_false": sorted(want), "got_false": sorted(false), "want_pairs": want_pairs, "got_pairs": pairs_got, "ok": ok})
        print(name, "OK" if ok else f"MISMATCH got {sorted(false)} pairs {pairs_got}")
    g = guard_cases(sroot)
    covered = set().union(*[set(r["want_false"]) for r in results if r.get("ok")]) if results else set()
    verify_keys = set(json.loads((EVID / "verify.json").read_text(encoding="utf-8"))["checks"]) if (EVID / "verify.json").is_file() else set()
    out = {"what": "KG1 양성 대조(사본 · 밝힌 기대 키 집합과 꼭 같음 · G2 는 겨냥한 쌍 이름까지) + 가드 대조(가드 함수만 · 꾸민 저장소 · 거부 사유 조각)",
           "verify_u": U, "cases": results, "guard": g,
           "cases_ok": bool(results) and all(r["ok"] for r in results), "guard_ok": all(x["ok"] is not False for x in g),
           "keys_covered": sorted(covered), "keys_not_covered": sorted(verify_keys - covered),
           "not_covered": [x for x in g if x.get("ok") is None] + [
               {"what": "G6_fits_plate · G6_bed_contact", "why": "판보다 큰 부품 · 판에 닿는 면이 없는 부품을 꾸미지 않았다 — 값은 verify.json 의 G6_print 에 수로 남는다"},
               {"what": "G4_open_at_least_object_plus_10 · G4_servo_angle_within_300", "why": "parameters 의 행정 상수로만 정해지는 식(2 × 47 = 94 ≥ 90 · 47 / 13.5 rad = 199.5° ≤ 300) — 대조를 두지 않았다"},
               {"what": "G1_all_closed_positive_volume · G1_manifold_equals_mesh", "why": "열린 메시를 꾸미지 않았다(G1_manifold_equals_mesh 는 2026-10-28 실제 열린 받침 STL 이 G2 를 빈 입체로 조용히 통과시킨 일 뒤에 더함)"},
               {"what": "G0_build_tool_recorded", "why": "기록에 도구 칸(CLI 판 · sha256)이 있는지만 보는 식 — 대조를 두지 않았다"}],
           "code_sha256": {f: sha(HERE / f) for f in ("verify_gripper.py", "run_controls.py", "guard.py")}}
    guard.write_bytes(a.out, (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), ROOT, a.scratch_root)
    print(json.dumps({"cases_ok": out["cases_ok"], "guard_ok": out["guard_ok"], "n": len(results), "guard_n": len(g),
                      "keys_not_covered": out["keys_not_covered"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
