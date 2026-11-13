# -*- coding: utf-8 -*-
"""MP4 A2 검사 — 1:1 외장 v2 의 (1) 관절 원점 · 축 = v1 (2) 표시 자세에서 서로 다른 링크 사이 체적 간섭 0 (3) v1 가정 상자 18 개가 그 관절의
모듈 덩어리 안에 100 % · 다른 링크와 간섭 0 (4) v1 동결 파일 해시 불변.

사용: python validate_product.py --cli <solidcraft-cli.exe> --model <모델 폴더> --evidence <근거 폴더> [--parse-only]
판정은 `validation.json` 의 `checks` 에 참거짓으로 적고, 하나라도 거짓이면 종료 값 1."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), Path(r"C:\projects\robot-arm-lab"))
V1 = ROOT / "models" / "armold-mks-concept-v1"


def frame(axis, hint):
    z = np.asarray(axis, float)
    z /= np.linalg.norm(z)
    x = np.asarray(hint, float) - z * np.dot(hint, z)
    x /= np.linalg.norm(x)
    return np.column_stack([x, np.cross(z, x), z])


def frozen_hashes():
    man = json.loads((V1 / "frozen-manifest.json").read_text(encoding="utf-8"))
    files = man.get("files") or man.get("frozen") or man
    out = {}
    items = files.items() if isinstance(files, dict) else [(f.get("path") or f.get("file"), f.get("sha256")) for f in files]
    for rel, want in items:
        path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
        got = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        out[str(rel)] = {"manifest": want, "now": got, "same": want == got}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--parse-only", action="store_true")
    a = ap.parse_args()
    a.evidence.mkdir(parents=True, exist_ok=True)
    native = a.model / "armold-type-mks-product-v2.solidcraft"
    bodies = {b["name"]: b for b in json.loads((a.model / "bodies.json").read_text(encoding="utf-8"))["bodies"]}
    kin = json.loads((V1 / "kinematics.json").read_text(encoding="utf-8"))
    p1 = json.loads((V1 / "parameters.json").read_text(encoding="utf-8"))
    params = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    sign = params["exterior"]["output_side_sign"]
    D = float(p1["reducer_depth_mm"])

    cmds, keep = [], []
    for k, j in enumerate(kin["joints"], start=1):
        O = np.asarray(j["origin_mm"], float)
        A = np.asarray(j["axis_world"], float) * sign[k - 1]
        pre = np.asarray(j["R_parent"], float)
        F = frame(A, pre[:, 0] if abs(np.dot(pre[:, 0], A)) < 0.8 else pre[:, 1])
        ml, mf, dw, dd, cc = p1["motor_length_mm"], p1["motor_frame_mm"], p1["driver_width_mm"], p1["driver_depth_mm"], p1["connector_clearance_mm"]
        rear = -D / 2 - 3 - ml - 2 - dd / 2
        for tag, c, s in (("MOTOR", [0, 0, -D / 2 - 3 - ml / 2], [mf, mf, ml]), ("DRIVER", [0, 0, rear], [dw, dw, dd]),
                          ("CONNECTOR", [-dw / 2 - cc / 2, 0, rear], [cc, 20, dd])):
            name = f"KEEPOUT_J{k}_{tag}"
            c, s = np.asarray(c, float), np.asarray(s, float)
            cmds += [{"command": "sketch.create", "params": {"name": name + "_P", "plane": {"origin": (O + F @ (c - [0, 0, s[2] / 2])).tolist(),
                                                                                           "x_dir": F[:, 0].tolist(), "y_dir": F[:, 1].tolist()}}},
                     {"command": "sketch.line", "params": {"points": [[-s[0] / 2, -s[1] / 2], [s[0] / 2, -s[1] / 2], [s[0] / 2, s[1] / 2],
                                                                      [-s[0] / 2, s[1] / 2]], "closed": True}},
                     {"command": "sketch.finish", "params": {}},
                     {"command": "solid.extrude", "params": {"distance": float(s[2]), "operation": "new", "body_name": name, "name": name + "_X"}}]
            keep.append({"joint": k, "name": name, "volume_mm3": float(np.prod(s)), "owner_link": k - 1})
    cmds += [{"command": "joint.list", "params": {}}, {"command": "inspect.interference", "params": {"budget_s": 900}}]
    script = a.evidence / "check-commands.json"
    script.write_text(json.dumps({"commands": cmds}, indent=1) + "\n", encoding="utf-8")
    result_path = a.evidence / "check-result.json"
    if not a.parse_only:
        p = subprocess.run([str(a.cli), "run", str(script), "--in", str(native), "--results", "--json-out", str(result_path)],
                           capture_output=True, text=True, encoding="utf-8", timeout=3600, env=dict(os.environ, SOLIDCRAFT_GPU="cpu"))
        (a.evidence / "check-stderr.txt").write_text(p.stderr, encoding="utf-8")
        if p.returncode:
            raise SystemExit(f"check run rc {p.returncode}: {p.stderr[-1500:]}")
    res = json.loads(result_path.read_text(encoding="utf-8"))
    results = res if isinstance(res, list) else res.get("results", [])
    inter = joints = None
    for r in results:
        for body in (r, r.get("result") if isinstance(r, dict) else None):
            if isinstance(body, dict) and "interferences" in body:
                inter = body
            if isinstance(body, dict) and "joints" in body and isinstance(body["joints"], list):
                joints = body["joints"]

    def owner(name):
        if name.startswith("KEEPOUT_"):
            return "keepout"
        return bodies[name]["link"] if name in bodies else None

    cross, same, kept = [], [], {}
    for it in inter["interferences"]:
        oa, ob = owner(it["a"]), owner(it["b"])
        vol = float(it.get("volume_mm3") or 0)
        if "keepout" in (oa, ob):
            ko, other = (it["a"], it["b"]) if oa == "keepout" else (it["b"], it["a"])
            kept.setdefault(ko, []).append({"body": other, "link": owner(other), "volume_mm3": vol})
        elif oa == ob:
            same.append({"a": it["a"], "b": it["b"], "link": oa, "volume_mm3": vol})
        else:
            cross.append({"a": it["a"], "b": it["b"], "links": [oa, ob], "volume_mm3": vol})
    keep_rows = []
    for kp in keep:
        mod = f"J{kp['joint']}_MODULE"
        hits = kept.get(kp["name"], [])
        inside = sum(h["volume_mm3"] for h in hits if h["body"] == mod)
        other_links = [h for h in hits if h["link"] not in ("keepout", kp["owner_link"])]
        keep_rows.append({**kp, "inside_module_mm3": inside, "ratio": inside / kp["volume_mm3"], "other_link_overlaps": other_links})

    # 관절 원점 · 축 = v1
    jrows, jok = [], joints is not None and len(joints) == 6
    for j in kin["joints"]:
        got = next((x for x in (joints or []) if str(x.get("name", "")).startswith(j["name"] + "_")), None)
        row = {"joint": j["name"], "found": got is not None}
        if got is not None:
            errs_o, errs_a = [], []
            for side in ("frame_a", "frame_b"):
                fr = got.get(side) or {}
                gp, ga = fr.get("origin"), fr.get("z")
                if gp is None or ga is None:
                    errs_o.append(float("inf"))
                    errs_a.append(float("inf"))
                    continue
                errs_o.append(float(np.max(np.abs(np.asarray(gp, float) - np.asarray(j["origin_mm"], float)))))
                errs_a.append(float(np.max(np.abs(np.asarray(ga, float) / np.linalg.norm(ga) - np.asarray(j["axis_world"], float)))))
            row["native"] = {"frame_a": got.get("frame_a"), "frame_b": got.get("frame_b"), "type": got.get("type")}
            row["origin_err_mm"] = max(errs_o)
            row["axis_unit_component_err"] = max(errs_a)
            row["ok"] = got.get("type") == "revolute" and row["origin_err_mm"] <= 1e-6 and row["axis_unit_component_err"] <= 1e-9
        jok = jok and row.get("ok", False)
        jrows.append(row)

    frozen = frozen_hashes()
    checks = {
        "interference_unchecked_pairs_0": len(inter.get("unchecked", [])) == 0,
        "cross_link_interference_0": len(cross) == 0,
        "keepout_boxes_18": len(keep_rows) == 18,
        "keepouts_100pct_inside_their_module": all(abs(r["ratio"] - 1) <= 1e-9 for r in keep_rows),
        "keepouts_no_other_link_overlap": all(not r["other_link_overlaps"] for r in keep_rows),
        "joints_match_v1": jok,
        "v1_frozen_files_unchanged": all(v["same"] for v in frozen.values()),
    }
    out = {"checks": checks, "cross_link": cross, "same_link_overlaps": same, "keepouts": keep_rows, "joints": jrows, "v1_frozen": frozen,
           "unchecked": inter.get("unchecked", []), "notes": ["Envelope bodies are solid; containment = keep-out box fully inside the solid module.",
                                                              "Connector box outer corner radius 36.4 mm vs can radius 39 mm: 2.6 mm margin (not a wall thickness)."]}
    (a.model / "validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1))
    print("cross", len(cross), "same", len(same), "keepouts", len(keep_rows))
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
