# -*- coding: utf-8 -*-
"""MP15 — 모터 받침 v1(SolidCraft): 모터를 눕혀(축 = x) 몸통을 U 자 받침에 얹고 위 막대를 M3 인서트 둘로 조인다 · 바닥판에 고정 구멍 넷.

좌표 = parameters.json frame(모터 앞면 x 0 · 몸통 +x · 감속기 −x · z 위 · 책상 z 0). 받침(HOLDER)과 막대(BAR)는 조립 자리로 만든다
(막대 밑면 = 모터 윗면). 모터 · 감속기 치수는 sources 파일에서, 끼움은 원장(fits_from)에서 읽는다 — 손으로 옮긴 값은 connector_front 하나(검사 C4 가 대조).
쓰기는 models/motor-holder-v1 · .dev/mp15-evidence · 작업 폴더(--scratch)만. 양성 대조(--control)는 작업 폴더 아래에만 쓴다.
사용: python build_holder.py --cli <solidcraft-cli.exe> --scratch <작업 폴더> [--control <이름> --out <작업 폴더 아래>] [--preview]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = "motor-holder-v1"
BODIES = ("HOLDER", "BAR")
CONTROLS = {"tight": "cradle side clearance 0.0", "front": "cradle front at x 0.0 (on the reducer base plate - no stop play)",
            "nopocket": "no pockets for the lower cap screw heads", "far": "cradle front at x 4.5 (old R0 - the base plate is no backward stop)",
            "long": "cradle rear at x 28.5 (past connector front - gap)", "flush": "clamp gap 0.0 (wall top = motor top)", "barup": "bar 0.5 above the motor top",
            "thin": "wall 6.0 (insert wall 1.0)", "barhole": "bar holes 3.0 (under the M3 clearance)", "nocb": "no counterbore (M3 x 10 reaches 1.0 into the insert)",
            "low": "axis height 42 (reducer reaches the base)", "blind": "base holes stop 2.0 above the bottom face"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inside(p, *roots):
    p = Path(p).resolve()
    return any(p == r.resolve() or r.resolve() in p.parents for r in roots)


def dig(d, dotted):
    for k in dotted.split("."):
        d = d[k]
    return d


def load(params_path):
    """매개변수 + sources(모터 원장 · 감속기 산출 · J5 매개변수) + 끼움 원장 값 → 만들기 · 검사가 같이 쓰는 한 사전."""
    P = json.loads(Path(params_path).read_text(encoding="utf-8"))
    base = Path(params_path).resolve().parent
    src = P["sources"]
    paths = {"motor_ledger": base / src["motor_ledger"], "reducer_json": base / src["reducer_json"], "reducer_params": base / src["reducer_params"],
             "j5_params": base / src["j5_params"], "fits_ledger": base / P["fits_from"]["ledger"]}
    motor = json.loads(paths["motor_ledger"].read_text(encoding="utf-8"))
    red = json.loads(paths["reducer_json"].read_text(encoding="utf-8"))
    redp = json.loads(paths["reducer_params"].read_text(encoding="utf-8"))
    j5 = json.loads(paths["j5_params"].read_text(encoding="utf-8"))
    led = json.loads(paths["fits_ledger"].read_text(encoding="utf-8"))
    for k in P:
        assert k != "fits", "fit values belong in the ledger (fits_from), not in parameters.json"
    vals = led["materials"][P["fits_from"]["material"]]["values"]
    D = {"P": P, "paths": {k: str(v) for k, v in paths.items()}, "sha": {k: sha(v) for k, v in paths.items()},
         "frame": motor["items"]["frame"]["value"], "frame_status": motor["items"]["frame"]["status"],
         "reducer_r": dig(red, "radii_mm.outer"), "cap_screw_r": dig(red, "radii_mm.cap_screw"), "output_face": dig(red, "stack_mm.output_face"),
         "cap_screws": dig(redp, "housing.cap_screws"), "connector_front_j5": dig(j5, "motor_connector.measured.front_from_motor_face"),
         "connector_box_j5": [dig(j5, "motor_connector.measured.height_above_motor_face"), dig(j5, "motor_connector.measured.width"),
                              dig(j5, "motor_connector.y_center_estimate")], "body_length": motor["items"]["body_length"]["value"],
         "fits": {k: vals[k]["value"] for k in P["fits_from"]["keys"]}, "fit_status": {k: vals[k]["status"] for k in P["fits_from"]["keys"]}}
    return D


def geometry(D):
    """만들기와 검사가 같은 수를 쓰도록 형상 수를 한곳에서 낸다."""
    P = D["P"]
    c, w = P["cradle"], P["cradle"]["wall"]
    half_in = D["frame"] / 2 + c["side_clearance"]
    floor = P["axis_height"] - D["frame"] / 2
    motor_top = floor + D["frame"]
    G = {"x0": c["x"][0], "x1": c["x"][1], "half_in": half_in, "half_out": half_in + w, "floor": floor, "motor_top": motor_top,
         "wall_top": motor_top - c["clamp_gap"], "insert_y": half_in + w / 2, "insert_x": P["inserts"]["x"], "bar_x": [P["inserts"]["x"] - P["bar"]["width"] / 2,
                                                                                                                  P["inserts"]["x"] + P["bar"]["width"] / 2],
         "bar_z": [motor_top + P["bar"].get("lift", 0.0), motor_top + P["bar"].get("lift", 0.0) + P["bar"]["thickness"]]}
    return G


def cap_heads(D, axis_z):
    """덮개 나사 머리 중심(y, z) — 45° 대각선(모터 나사와 같은 대각선)."""
    out = []
    for i in range(D["cap_screws"]):
        a = math.pi / 4 + 2 * math.pi * i / D["cap_screws"]
        out.append((D["cap_screw_r"] * math.cos(a), axis_z + D["cap_screw_r"] * math.sin(a)))
    return out


def commands(D, control=None):
    P = D["P"]
    G = geometry(D)
    b, f = P["base"], D["fits"]
    cmds = []

    def cmd(c, **p):
        cmds.append({"command": c, "params": p})

    def plane_z(z):
        return {"origin": [0, 0, z], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}

    # 바닥판(둥근 모서리) — 몸체 HOLDER
    cmd("sketch.create", name="BASE_SK", plane=plane_z(0))
    cmd("sketch.rectangle.rounded", p0=[b["x"][0], -b["y_half"]], p1=[b["x"][1], b["y_half"]], radius=b["corner_r"])
    cmd("sketch.finish")
    cmd("solid.extrude", distance=b["thickness"], operation="new", body_name="HOLDER", name="BASE_X")
    # 받침 덩어리 — 밑면은 바닥판 안(z 1.0)에서 시작해 같은 면을 만들지 않는다
    cmd("solid.box", length=G["x1"] - G["x0"], width=2 * G["half_out"], height=G["wall_top"] - 1.0, corner=[G["x0"], -G["half_out"], 1.0],
        operation="join", targets=["HOLDER"], name="BLOCK")
    # U 자 홈(모터 몸통) — 앞뒤 · 위로 1 씩 넘쳐 자른다
    cmd("solid.box", length=G["x1"] - G["x0"] + 2.0, width=2 * G["half_in"], height=G["wall_top"] - G["floor"] + 1.0,
        corner=[G["x0"] - 1.0, -G["half_in"], G["floor"]], operation="cut", targets=["HOLDER"], name="CRADLE")
    # 덮개 나사 머리 주머니 — 벽 윗면보다 아래에 오는 머리만(앞면이 머리 높이 + 틈보다 앞일 때)
    hd = P["keepout"]["cap_screw_head"]
    x_end = hd["height"] + hd["pocket_depth_gap"]
    low = [(y, z) for y, z in cap_heads(D, P["axis_height"]) if z < G["wall_top"]]
    if G["x0"] < x_end and control != "nopocket":
        cmd("sketch.create", name="POCKET_SK", plane={"origin": [G["x0"] - 1.0, 0, 0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]})
        for y, z in low:
            cmd("sketch.circle.center", center=[y, z], radius=hd["dia"] / 2 + hd["pocket_gap"])
        cmd("sketch.finish")
        cmd("solid.extrude", distance=x_end - (G["x0"] - 1.0), operation="cut", targets=["HOLDER"], name="POCKET_X")
    # 벽 윗면 인서트 구멍 둘
    cmd("sketch.create", name="INS_SK", plane=plane_z(G["wall_top"]))
    for s in (1, -1):
        cmd("sketch.circle.center", center=[G["insert_x"], s * G["insert_y"]], radius=f["insert_hole_dia"] / 2)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=P["inserts"]["depth"], direction="negative", operation="cut", targets=["HOLDER"], name="INS_X")
    # 바닥판 고정 구멍 넷 — 공중(위 0.5)에서 아래로 두께 + 1 (대조 blind = 밑면 2.0 위에서 멈춤)
    h = b["holes"]
    cmd("sketch.create", name="BH_SK", plane=plane_z(b["thickness"] + 0.5))
    for x in h["x"]:
        for s in (1, -1):
            cmd("sketch.circle.center", center=[x, s * h["y"]], radius=h["dia"] / 2)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=(b["thickness"] + 0.5 - 2.0) if control == "blind" else b["thickness"] + 1.0, direction="negative", operation="cut",
        targets=["HOLDER"], name="BH_X")
    # 막대 — 조립 자리(밑면 = 모터 윗면) · 나사 구멍 둘
    cmd("sketch.create", name="BAR_SK", plane=plane_z(G["bar_z"][0]))
    cmd("sketch.rectangle.rounded", p0=[G["bar_x"][0], -G["half_out"]], p1=[G["bar_x"][1], G["half_out"]], radius=P["bar"]["corner_r"])
    cmd("sketch.finish")
    cmd("solid.extrude", distance=P["bar"]["thickness"], operation="new", body_name="BAR", name="BAR_X")
    cmd("sketch.create", name="BARH_SK", plane=plane_z(G["bar_z"][1] + 0.5))
    for s in (1, -1):
        cmd("sketch.circle.center", center=[G["insert_x"], s * G["insert_y"]], radius=f["m3_clearance_dia"] / 2)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=P["bar"]["thickness"] + 1.0, direction="negative", operation="cut", targets=["BAR"], name="BARH_X")
    if P["bar"]["counterbore_depth"] > 0:                  # 둥근머리 자리 — 가진 M3 × 10 이 인서트에 4.0 물리게
        cmd("sketch.create", name="BARCB_SK", plane=plane_z(G["bar_z"][1] + 0.5))
        for s in (1, -1):
            cmd("sketch.circle.center", center=[G["insert_x"], s * G["insert_y"]], radius=P["bar"]["counterbore_dia"] / 2)
        cmd("sketch.finish")
        cmd("solid.extrude", distance=P["bar"]["counterbore_depth"] + 0.5, direction="negative", operation="cut", targets=["BAR"], name="BARCB_X")
    return cmds, G


def preview_commands(D, G):
    """보여 주기 전용 — 모터 몸통 · 드라이버 · 감속기를 어림 상자 · 원기둥으로(STL · STEP 에 넣지 않음)."""
    P = D["P"]
    cmds = []

    def cmd(c, **p):
        cmds.append({"command": c, "params": p})

    a, fr = P["axis_height"], D["frame"]
    cmd("solid.box", length=D["body_length"], width=fr, height=fr, corner=[0.0, -fr / 2, G["floor"]], operation="new", body_name="REF_MOTOR")
    ch, cw, cy = D["connector_box_j5"]                    # 모터 커넥터(위로 둔 경우 · 뒤 끝은 몸통 끝으로 어림)
    cmd("solid.box", length=D["body_length"] - D["connector_front_j5"], width=cw, height=ch, corner=[D["connector_front_j5"], cy - cw / 2, G["motor_top"]],
        operation="new", body_name="REF_CONNECTOR")
    hd = P["keepout"]["cap_screw_head"]
    cmd("sketch.create", name="HEAD_SK", plane={"origin": [0, 0, 0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]})
    for y, z in cap_heads(D, a):
        cmd("sketch.circle.center", center=[y, z], radius=hd["dia"] / 2)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=hd["height"], operation="new", body_name="REF_HEADS")
    cmd("sketch.create", name="RED_SK", plane={"origin": [0, 0, 0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]})
    cmd("sketch.circle.center", center=[0.0, a], radius=D["reducer_r"])
    cmd("sketch.finish")
    cmd("solid.extrude", distance=D["output_face"], direction="negative", operation="new", body_name="REF_REDUCER")
    return cmds


def run(cli, script, native, step, work, env):
    p = subprocess.run([str(cli), "run", str(script), "--save", str(native)] + (["--out", str(step)] if step else []) +
                       ["--results", "--json-out", str(work / "result.json")], capture_output=True, text=True, encoding="utf-8", timeout=1200, env=env)
    (work / "run.log").write_bytes(((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-snapshot", action="store_true")
    a = ap.parse_args()
    scr = a.scratch.resolve()
    assert not inside(scr, ROOT), "scratch must be outside the repo"
    if a.control:
        assert a.out and inside(a.out, scr), "--control needs --out under --scratch"
        out, ev = a.out, a.out
    else:
        out, ev = ROOT / "models" / NAME, ROOT / ".dev" / "mp15-evidence" / "build"
    work = scr / ("build-" + (a.control or "main"))
    for d in (out, out / "parts", ev, work):
        assert inside(d, ROOT / "models" / NAME, ROOT / ".dev" / "mp15-evidence", scr), d
        d.mkdir(parents=True, exist_ok=True)
    D = load(a.params)
    if a.control:                                          # 고장 판 — 매개변수 사본만 바꾼다(파일은 그대로)
        P = copy.deepcopy(D["P"])
        if a.control == "tight":
            P["cradle"]["side_clearance"] = 0.0
        elif a.control == "front":
            P["cradle"]["x"][0] = 0.0
        elif a.control == "far":
            P["cradle"]["x"][0] = 4.5
        elif a.control == "long":
            P["cradle"]["x"][1] = 28.5
        elif a.control == "barup":
            P["bar"]["lift"] = 0.5
        elif a.control == "barhole":
            D["fits"] = {**D["fits"], "m3_clearance_dia": 3.0}
        elif a.control == "nocb":
            P["bar"]["counterbore_depth"] = 0.0
        elif a.control == "flush":
            P["cradle"]["clamp_gap"] = 0.0
        elif a.control == "thin":
            P["cradle"]["wall"] = 6.0
        elif a.control == "low":
            P["axis_height"] = 42.0
        D["P"] = P
    cmds, G = commands(D, a.control)
    stls = {n: out / "parts" / f"{n}.stl" for n in BODIES}
    for n, p in stls.items():
        cmds.append({"command": "file.save_mesh", "params": {"path": str(p), "format": "stl", "bodies": [n], "quality": D["P"]["quality"]}})
    script = work / "build.json"
    script.write_bytes((json.dumps({"commands": cmds}, ensure_ascii=False) + "\n").encode("utf-8"))
    native, step = out / f"{NAME}.solidcraft", out / f"{NAME}.step"
    env = dict(os.environ)
    env["PATH"] = str(a.cli.parent) + os.pathsep + env.get("PATH", "")
    p = run(a.cli, script, native, step, work, env)
    if p.returncode or not all(s.is_file() for s in stls.values()):
        raise SystemExit(f"solidcraft run rc {p.returncode}: {(p.stderr or p.stdout)[-1500:]}")
    bak = native.with_name(native.name + ".bak")           # SolidCraft 가 덮어쓸 때 남기는 옛 문서 — 산출물 아님
    if bak.is_file():
        bak.unlink()
    if not a.no_snapshot:                                  # 보여 주기 그림 — 모터 · 감속기 어림 몸체를 더한 따로 문서(저장소 밖)에서
        pw = scr / "preview"
        pw.mkdir(parents=True, exist_ok=True)
        ps = pw / "preview.json"
        ps.write_bytes((json.dumps({"commands": cmds[:-len(BODIES)] + preview_commands(D, G)}, ensure_ascii=False) + "\n").encode("utf-8"))
        pn = pw / "preview.solidcraft"
        q = run(a.cli, ps, pn, None, pw, env)
        for doc, views in ((native, ("iso",)), (pn if q.returncode == 0 else None, ("iso", "front"))):
            if doc is None:
                print(f"preview rc {q.returncode}")
                continue
            for view in views:
                png = out / (f"{view}.png" if doc == native else f"with-motor-{view}.png")
                r = subprocess.run([str(a.cli), "snapshot", "--in", str(doc), "--out", str(png), "--view", view, "--width", "1600", "--height", "1200"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=600, env=env)
                if r.returncode:
                    print(f"snapshot {png.name} rc {r.returncode}: {(r.stderr or r.stdout)[-400:]}")
    v = subprocess.run([str(a.cli), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    rec = {"what": "MP15 모터 받침 만들기 기록 — 이 sha 와 지금 파일이 같아야 검사가 지금 형상을 본 것이다", "control": a.control,
           "control_means": CONTROLS.get(a.control), "geometry": G, "frame_used": D["frame"], "fits_used": D["fits"],
           "tool": {"cli_version": (v.stdout or v.stderr or "").strip(), "cli_sha256": sha(a.cli)},
           "inputs_sha256": {"parameters.json": sha(a.params), "build_holder.py": sha(__file__), **D["sha"]},
           "outputs_sha256": {**{f"parts/{n}.stl": sha(s) for n, s in stls.items()}, f"{NAME}.solidcraft": sha(native), f"{NAME}.step": sha(step)},
           "command_count": len(cmds)}
    (ev / "build-record.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"control": a.control, "commands": len(cmds), "geometry": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in G.items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
