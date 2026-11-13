# -*- coding: utf-8 -*-
"""MP11 검사 — 커밋된 산출(manifest · render-report · label-grid · 그림)과 지금 입력 파일로 스스로 계산한다(그림 · 장면은 바꾸지 않음).
그림이 무엇을 그렸는지만 본다 — 겹침 · 강도 같은 설계 검사는 하지 않는다(보기용 단위).

- C1 장면 무변경: 리포트마다 blend_unchanged 참 · 리포트의 장면 sha256 = 지금 장면 파일 sha256.
- C2 번호 완전성: 그린 개체 = 정답표(v3 bodies.json 47 + 그리퍼 parameters 로 센 11) · 개체마다 GROUPS 번호 하나에만 · 번호 수 = 기대값 ·
  번호 그림의 번호 수 = 기대값.
- C3 산출 지문: manifest outputs = 지금 파일(글 파일은 CRLF → LF).
- C4 입력 지문: manifest inputs · scripts = 지금 파일(다르면 그림이 낡음).
- C5 벌림 기록: 관절 여섯 옮긴 양 ≠ 0 · 관절 안 · 바닥 작은 부품(발판 빼고) 옮긴 양 ≠ 0 · 축 점선 > 0 · 자세 · 샷 설정 = parameters.json · 갤러리 자세.

사용: python -I -B -X utf8 check_exploded.py [--write]   (--write 면 models/arm-v3-kg1-exploded/check.json 을 guard 로 씀)
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402
import label_parts  # noqa: E402
from make_all import SCRIPTS, fingerprint, input_paths, output_rel  # noqa: E402

SMALL = re.compile(r"(_END_CAP|_CAP_SLASH|_ACCENT_RING|_HUB_CAP|_HUB_SLASH|^LINK2_LOGO_.*|^LINK6_TOOL_RING)$")


def load(repo: Path) -> dict:
    base = repo / "models" / "arm-v3-kg1-exploded"
    prm = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    rd = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    gp = rd(repo / "src" / "cad" / "kmjh-gripper-v1" / "parameters.json")["layout"]
    pad = rd(repo / "src" / "cad" / "arm-v3-kg1-assembly" / "parameters.json")["gripper"]["padset"]
    n_rod = len(gp["rod_y_a"]) + len(gp["rod_y_b"])
    expect = ([b["name"] for b in rd(repo / "models" / "armold-mks-product-v3" / "bodies.json")["bodies"]]
              + [f"KG1_{n}" for n in ("BASE", "JAW_A", "JAW_B", "PINION", f"PAD_A_{pad}", f"PAD_B_{pad}", "SERVO")]
              + [f"KG1_ROD_{i}" for i in range(n_rod)])
    return {
        "prm": prm,
        "manifest": rd(base / "manifest.json"),
        "reports": {s["name"]: rd(base / "data" / f"render-report-{s['name']}.json") for s in prm["shots"]},
        "grids": {s["name"]: rd(base / "data" / f"label-grid-{s['name']}.json") for s in prm["shots"]},
        "now_out": {p: (fingerprint(base / p) if (base / p).is_file() else None) for p in output_rel(prm)},
        "now_in": {p: fingerprint(repo / p) for p in input_paths(repo)},
        "now_scripts": {f"src/cad/arm-v3-kg1-exploded/{n}": fingerprint(HERE / n) for n in SCRIPTS},
        "blend_sha": hashlib.sha256((repo / "models/armold-mks-product-v3/blender/kmjh-arm-v3.blend").read_bytes()).hexdigest(),
        "poses": {p["name"]: [float(x) for x in p["q_deg"]] for p in rd(repo / "src/cad/armold-mks-product-v3/gallery_poses.json")["poses"]},
        "expect_objects": expect,
        "groups": copy.deepcopy(label_parts.GROUPS),
    }


def checks(b: dict) -> list[dict]:
    out = []

    def put(cid, ok, detail):
        out.append({"id": cid, "ok": bool(ok), "detail": detail})

    # C1
    d1 = {n: {"blend_unchanged": r.get("blend_unchanged"), "sha_same": r.get("blend_sha256") == b["blend_sha"]} for n, r in b["reports"].items()}
    put("C1", all(v["blend_unchanged"] is True and v["sha_same"] for v in d1.values()), d1)

    # C2
    d2, ok2 = {}, True
    exp = sorted(b["expect_objects"])
    for n, g in b["grids"].items():
        names = g["names"]
        try:
            items = label_parts.group_items(names, b["groups"])
            err = None
        except AssertionError as e:
            items, err = [], f"GROUPS name not in scene: {e}"
        cnt = Counter(m for it in items for m in it[2])
        missing = sorted(set(names) - set(cnt))
        dup = sorted(m for m, c in cnt.items() if c > 1)
        same = sorted(names) == exp
        ok = err is None and same and not missing and not dup and len(items) == b["prm"]["numbered"]["expected_items"]
        ok2 &= ok
        d2[n] = {"objects": len(names), "expected_objects": len(exp), "objects_match_answer_table": same, "items": len(items),
                 "not_numbered": missing, "numbered_twice": dup, "error": err}
    lab = b["manifest"].get("numbered", {})
    ok_lab = lab.get("items") == b["prm"]["numbered"]["expected_items"]
    put("C2", ok2 and ok_lab, {"grids": d2, "numbered_image_items": lab.get("items"), "hidden_in_numbered": lab.get("hidden")})

    # C3
    man_out = b["manifest"]["outputs"]
    bad3 = sorted(p for p in set(man_out) | set(b["now_out"]) if man_out.get(p) != b["now_out"].get(p) or b["now_out"].get(p) is None)
    put("C3", not bad3, {"files": len(b["now_out"]), "mismatch_or_missing": bad3})

    # C4
    bad4 = sorted(p for p in set(b["manifest"]["inputs"]) | set(b["now_in"]) if b["manifest"]["inputs"].get(p) != b["now_in"].get(p))
    bad4 += sorted(p for p in set(b["manifest"]["scripts"]) | set(b["now_scripts"]) if b["manifest"]["scripts"].get(p) != b["now_scripts"].get(p))
    put("C4", not bad4, {"inputs": len(b["now_in"]), "scripts": len(b["now_scripts"]), "mismatch": bad4})

    # C5
    d5, ok5 = {}, True
    rp = b["prm"]["render"]
    for s in b["prm"]["shots"]:
        r = b["reports"][s["name"]]
        off = r.get("offsets_mm", {})
        norm = {k: math.sqrt(sum(x * x for x in v)) for k, v in off.items()}
        joints_ok = all(norm.get(f"JOINT_J{k}", 0) > 1e-6 for k in range(1, 7))
        small = [n for n in b["grids"][s["name"]]["names"] if SMALL.search(n) or (n.startswith("BASE_") and n != "BASE_FOOT") or n == "J1_MODULE"]
        small_zero = sorted(n for n in small if norm.get(n, 0) <= 1e-6)
        same_dir = all(abs(x - y) < 1e-5 for x, y in zip(r.get("dir", []), _unit(s["dir"]))) and len(r.get("dir", [])) == 3
        setting = (r.get("pose") == s["pose"] and r.get("q_deg") == b["poses"][s["pose"]] and r.get("f") == s["f"] and r.get("fill") == s["fill"]
                   and same_dir and r.get("samples") == rp["samples"] and r.get("size") == [rp["w"], rp["h"]])
        ok = joints_ok and not small_zero and len(small) > 0 and r.get("axis_line_dashes", 0) > 0 and setting
        ok5 &= ok
        d5[s["name"]] = {"joints_moved": joints_ok, "small_parts": len(small), "small_parts_not_moved": small_zero,
                         "axis_line_dashes": r.get("axis_line_dashes"), "settings_match": setting}
    put("C5", ok5, d5)
    return out


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def main():
    repo = guard.find_root(HERE)
    res = checks(load(repo))
    doc = {"what": "MP11 분해도 검사(check_exploded.py) — 그림이 무엇을 그렸는지만 · 설계 검사 아님", "all_true": all(c["ok"] for c in res), "checks": res}
    for c in res:
        print(c["id"], c["ok"])
    print("ALL", doc["all_true"])
    if "--write" in sys.argv:
        guard.write_bytes(repo / "models" / "arm-v3-kg1-exploded" / "check.json",
                          (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), repo, None)
    return 0 if doc["all_true"] else 1


if __name__ == "__main__":
    sys.exit(main())
