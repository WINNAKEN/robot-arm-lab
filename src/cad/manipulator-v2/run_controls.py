# -*- coding: utf-8 -*-
"""MP18 양성 대조(팔 전체 v2) — 생성기 · 배치 · 파일에 고장을 넣은 판을 검사기가 잡는지(잡아야 할 검사가 거짓인지).

형상 고장(다시 만듦) · 배치 고장(부품은 본판 · 매개변수만) · 파일 고장(본판 사본을 망가뜨림) · 범위 고장(바라는 범위를 못 미치게).
결과 = .dev/mp18-evidence/controls.json. 사용: python run_controls.py --cli <solidcraft-cli.exe> --scratch <작업 폴더> [--only a,b]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import layout as L

HERE = Path(__file__).resolve().parent


def rmtree_rw(path):
    """작업 폴더 지우기 — copytree 가 원본 parts 폴더의 읽기 전용 속성까지 옮겨 rmdir 가 「액세스 거부」(2026-11-06 open_mesh)."""
    def onexc(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=onexc)
PY = sys.executable
EXPECT = {      # 대조: (잡아야 할 검사들 — 하나 이상 거짓, 돌릴 검사)
    "shoulder_hole_small": (["C4"], "C1,C3,C4,C6"),
    "turret_high": (["C4"], "C1,C3,C4,C6"),
    "pad_insert_shallow": (["C3"], "C1,C3,C4,C6"),
    "turret_shoulder_touch": (["C6"], "C1,C3,C4,C6"),
    "floor_hole_big": (["C3"], "C1,C3,C4,C6"),
    "shoulder_cbore_none": (["C5"], "C3,C5"),
    "sleeve_tight": (["C6"], "C1,C3,C4,C6"),         # 틈 0.5(겹침 아님) — C6 의 STL 최소 틈 줄이 잡음(검토 R1-7 뒤 C4 로는 안 보임)
    "tool_boss_big": (["C6"], "C1,C3,C4,C6"),
    "j3_layer_shift": (["C4"], "C3,C4"),
    "can_turned": (["C3"], "C3,C4"),
    "open_mesh": (["C1"], "C1"),
    "record_mismatch": (["C0"], "C0"),
    "j2_range_wanted_wide": (["C5"], "C5"),
    "j3_turn_zero": (["C3", "C4"], "C1,C3,C4,C6"),
    "logo_one_letter": (["C1"], "C1"),
    "ua_j3_ribs_back": (["C9"], "C1,C4,C9"),          # 검토 R1-1 · R1-4: 넣는 길 검사가 잡아야 함
    "j3_bracket_post_out": (["C4"], "C1,C4"),
    "mark_floating": (["C4"], "C1,C4"),             # 검토 R1-12: 표시 짝 겹침 하한
    "hood_rib_tight": (["C4"], "C1,C4"),
    "shroud_small": (["C4"], "C1,C4"),
    "tube_slot_narrow": (["C4"], "C1,C4"),
    "ua_bar_low": (["C4"], "C1,C4"),                # MP18 이어서: J3 57D 단자 어림이 위팔 벽에
    "hood_no_pockets": (["C4"], "C1,C4"),           # J2 단자 어림이 두건에
    "hood_exit_closed": (["C4"], "C1,C4"),          # 케이블 고정 구간이 두건 앞면에
    "ua_entry_closed": (["C4"], "C1,C4"),           # 케이블 고정 구간이 위팔 J2 끝 벽에
    "skin_slot_small": (["C4"], "C1,C4"),           # 들고 나는 묶음이 원뿔 겉에
    "j2_loop_short": (["C10"], "C10"),              # 고리 길이 모자람
    "loop_anchor_off": (["C10"], "C10"),            # 고리 고정점이 고정 구간 끝에서 벗어남
    "j1_loop_fold": (["C10"], "C10"),               # 케이블 검토 R1-1: 접은 감김 각으로만 맞는 고리 길이
    "cable_in_j3_motor": (["C4"], "C4"),            # 케이블 검토 R1-3: 같은 링크 모터 어림을 지나는 케이블
    "tie_decl_off": (["C10"], "C10"),               # 케이블 검토 R1-2: 타이 구멍이 없는 자리
    "notch_no_travel": (["C4"], "C1,C4"),           # 케이블 검토 R1-4: 벨트 홈 끝 단자 어림이 판에
    "hood_vents_short": (["C1"], "C1"),             # 케이블 검토 R1-5: 막힌 통풍 홈
}


def run(cmd, log):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=7200, cwd=str(HERE))
    Path(log).write_bytes(((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"))
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    import build_arm as B
    root = a.scratch.resolve() / "controls"
    assert L.ROOT.resolve() not in root.parents
    names = a.only.split(",") if a.only else list(EXPECT)
    rows = []
    for n in names:
        want, checks = EXPECT[n]
        out = root / n
        if out.exists():
            rmtree_rw(out)
        out.mkdir(parents=True)
        params, parts, record = HERE / "parameters.json", L.MODEL / "parts", L.EV / "build" / "build-record.json"
        if n in B.CONTROLS and B.CONTROLS[n][2]:                                   # 형상 고장 — 다시 만듦
            rc = run([PY, "-B", "-X", "utf8", "build_arm.py", "--cli", str(a.cli), "--scratch", str(a.scratch), "--control", n, "--out", str(out)], out / "build.log")
            if rc:
                rows.append({"control": n, "built": False, "rc": rc, "caught": False, "why": "build failed - control invalid"})
                print(n, "BUILD FAILED", flush=True)
                continue
            params, parts, record = out / "parameters.json", out / "parts", out / "build-record.json"
        elif n in B.CONTROLS:                                                      # 배치 고장 — 매개변수 사본만
            params = B.write_control_params(HERE / "parameters.json", n, out)
        elif n == "open_mesh":
            shutil.copytree(L.MODEL / "parts", out / "parts")
            import trimesh
            m = trimesh.load(out / "parts" / "FOREARM.stl", force="mesh")
            m.update_faces([i for i in range(len(m.faces)) if i % 997 != 0])
            (out / "parts" / "FOREARM.stl").write_bytes(m.export(file_type="stl"))
            parts = out / "parts"
        elif n == "record_mismatch":
            rec = json.loads(record.read_text(encoding="utf-8"))
            k = sorted(rec["outputs_sha256"])[0]
            rec["outputs_sha256"][k] = "0" * 64
            record = out / "build-record.json"
            record.write_bytes((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
        elif n == "j2_range_wanted_wide":
            raw = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
            base = HERE
            raw["sources"] = {k: ((base / v).resolve().as_posix() if isinstance(v, str) and ("/" in v or v.endswith(".json")) else v) for k, v in raw["sources"].items()}
            raw["poses"]["wanted_ranges_deg"]["J2"] = [-175.0, 60.0]
            params = out / "parameters.json"
            params.write_bytes((json.dumps(raw, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        cmd = [PY, "-B", "-X", "utf8", "check_arm.py", "--params", str(params), "--parts", str(parts), "--record", str(record), "--out", str(out), "--checks", checks]
        if "C5" in checks:
            cmd.append("--fast")
        run(cmd, out / "check.log")
        res = json.loads((out / "check.json").read_text(encoding="utf-8"))["results"]
        false = sorted(k for k, v in res.items() if not v["ok"])
        caught = any(w in false for w in want)
        rows.append({"control": n, "means": B.CONTROLS[n][0] if n in B.CONTROLS else {"open_mesh": "FOREARM.stl copy with every 997th face removed",
                                                                                    "record_mismatch": "one output sha in the build record set to zeros",
                                                                                    "j2_range_wanted_wide": "wanted J2 range -175 .. +60 (beyond the J2 motor and the desk side)"}[n],
                     "expected_false": want, "checks_run": checks, "false": false, "caught": caught})
        print(n, "caught" if caught else "MISSED", false, flush=True)
    allc = all(r["caught"] for r in rows) and len(rows) == len(EXPECT)
    old = {}
    p = L.EV / "controls.json"
    if a.only and p.is_file():
        old = {r["control"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}
    for r in rows:
        old[r["control"]] = r
    merged = [old[k] for k in EXPECT if k in old]
    out = {"what": "MP18 양성 대조(팔 전체 v2) — 고장을 넣은 판에서 잡아야 할 검사가 거짓인지", "all_caught": all(r["caught"] for r in merged) and len(merged) == len(EXPECT),
           "rows": merged, "inputs_sha256": {"build_arm.py": L.sha(HERE / "build_arm.py"), "check_arm.py": L.sha(HERE / "check_arm.py"), "layout.py": L.sha(HERE / "layout.py"),
                                             "parameters.json": L.sha(HERE / "parameters.json")}}
    L.EV.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print("all caught", out["all_caught"], "(this run", allc, ")")


if __name__ == "__main__":
    main()
