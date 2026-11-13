# -*- coding: utf-8 -*-
"""MP7 검사 — 1:1 외장 v3(KMJH). 계획 045 의 C1 ~ C6(C7 = blender_scene.py · blender_verify.py 의 보고).

C1  관절 = v1: native 관절 여섯 revolute 의 원점 차 ≤ 1e-6 mm · 단위 축 성분 차 ≤ 1e-9.
C1a v1 순기구학: v1 parameters 의 길이 · 축과 pose_deg 로 이 검사기가 다시 계산한 관절 원점 · R_child = kinematics.json(1e-9).
C1b 회전체(관절 모듈 · 띠 · 덮개 · 허브 · 허브 덮개 · 베이스 · 어깨 덮개 · 공구)의 무게중심이 그 관절 축 위(≤ 1e-3 mm).
C1c native 구조: 컴포넌트 7(Base · Link1 … Link6) · 발생 7 은 단위 변환 · Base 만 고정 · 관절 사슬 Base:1 → Link1:1 → … → Link6:1 ·
    값 0(표시 자세) · **바디마다 그 바디를 만든 기능의 컴포넌트 = bodies.json 의 링크**(간섭 · 소속 판정은 native 소속으로 한다).
C1d 링크 좌표의 형상(메시 꼭짓점 · C1a 의 프레임): 관절 모듈의 축 방향 범위 · 드럼 반지름 · 캔 반지름 · 출력 쪽, 끝 덮개 · 띠 · 허브 · 막대(상완
    x 0 … 165 = 관절 거리) · 목 · 어깨 기둥 · 베이스 · 공구 범위가 **v1 · v2 의 값**(v3 parameters 가 아님)과 0.01 mm 안. v3 parameters 의 보호 값 = v2 값.
    MP9 2 단계(2026-10-28 · 계획 051): 공구 끝의 돌기(옛 고리) · 플랜지 인서트 구멍은 v2 가 아니라 **그리퍼 KG1 parameters · 끼움 원장**의 규격과 대조한다
    (expected_shapes.tool_interface_expected — 생성기와 따로 읽음) · v3 parameters 에 그 숫자가 다시 생기면 거짓.
C2  표시 자세 정확 커널 간섭: 검사 못 한 쌍 0 · 서로 다른 링크(native 소속) 사이 체적 간섭 0.
C2b 표시(끝 덮개 · 허브 덮개의 사선 · 허브 덮개 · KMJH 글자)는 어떤 바디와도 체적이 겹치지 않는다.
C3  v1 가정 상자 18 개가 그 관절 모듈 안에 100 % · 다른 링크와 간섭 0.
C4  보호 폴더(v1 개념 · v2 산출 · v2 생성기)의 모든 파일이 단위 시작 스냅숏과 같다(추가 · 삭제 · 내용) · v1 동결 목록 해시 불변 ·
    (저장소에 .git 이 있을 때) v2 추적 파일 = HEAD blob.
C5  색: native 에 **저장된** 바디 색 = 이름으로 정한 역할의 브랜드 색 · bodies.json 역할 = 이름 역할 · 바디 이름 집합 = native 평가 = 저장 색.
C6  메시: 바디마다 STL 하나(남는 파일 없음) · 닫힘 · native 평가와 바운딩 상자 0.05 mm · 무게중심 0.05 mm · 체적 · 넓이 0.2 %.
C6b 특징 체적(native, 독립 계산과 1e-6): 글자 · 사선 = 다각형 넓이 × 돋움 · 허브 덮개 = πr² × 1.0 · 막대 · 목 · 기둥 = 팔각 단면 × 길이
    (전완 · 손목은 45° 자르기를 trimesh + manifold 불리언으로 뺀 값).

C0  출처 묶음(L4 R1 F1): 지금 native · STL 이 생성기 기록(build/provenance.json)과 같은 바이트 · 간섭 결과와 평가(eval-now.json)가 지금 native 로 낸 것
    (check-provenance.json 의 sha256 = 지금 파일). 정상 실행은 간섭 · 평가를 지금 native 로 **새로** 낸다 — parse-only 는 저장 결과가 지금 native 의 것일 때만 참.
C1  는 SolidCraft joint.list 와 함께 native 문서(document.json)의 관절 양쪽 snap 도 직접 v1 과 대조한다.
C2  간섭 응답의 필수 키(interferences · unchecked · pairs_not_checked · budget_exceeded · truncated)가 있고 미검사 0 · 예산 초과 · 잘림 없음.

사용: python validate_product.py --cli <solidcraft-cli.exe> [--model <모델 폴더>] [--evidence <근거 폴더>] [--build-evidence <생성기 근거 폴더>]
      [--scratch-root <저장소 밖 작업 뿌리>] [--protected-root <보호 폴더 사본의 뿌리>] [--parse-only]
판정은 모델 폴더의 `validation.json` 의 `checks`(참거짓) · `not_run` · 하나라도 거짓이면 종료 값 1."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from expected_shapes import expected_bodies, surface_distance, tool_interface_expected  # noqa: E402
from guard import PROTECTED_REL, checked_dir, checked_file, find_root  # noqa: E402
from snapshot import compare, snapshot  # noqa: E402

ROOT = find_root(HERE)
V1 = ROOT / "models" / "armold-mks-concept-v1"
V2P = ROOT / "src" / "cad" / "armold-mks-product-v2" / "parameters.json"
NAME = "kmjh-arm-product-v3"
TOL = 0.01
SHAPE_TOL_MM = 0.03       # C1e: 기대 형상(720 등분 회전 · 정확한 각기둥) ↔ STL(SolidCraft fine — 곡면 현 오차 ≤ 몸 크기 × 5e-5) 양방향 최대 거리
C6_BBOX_COM_MM = 0.002    # C6: native 평가 ↔ STL 바운딩 상자 · 무게중심(관측 최대 1.5e-5 · 5e-4 mm) — C1d 0.01 + 이 값 = native 기준 0.012 mm


def frame(axis, hint):
    z = np.asarray(axis, float)
    z /= np.linalg.norm(z)
    x = np.asarray(hint, float) - z * np.dot(hint, z)
    x /= np.linalg.norm(x)
    return np.column_stack([x, np.cross(z, x), z])


def rot(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def fk_from_v1(p1, kin):
    """v1 parameters 의 길이 · axis_parent_zero 와 kinematics.json 의 pose_deg 로 관절 원점 · R_parent · R_child 를 다시 계산."""
    offs = [[0, 0, p1["joint1_height_mm"]], [0, 0, p1["shoulder_rise_mm"]], [p1["upper_arm_mm"], 0, 0], [p1["forearm_mm"], 0, 0],
            [p1["wrist_offsets_mm"][0], 0, 0], [p1["wrist_offsets_mm"][1], 0, 0]]
    O, R, out = np.zeros(3), np.eye(3), []
    for k in range(6):
        O = O + R @ np.asarray(offs[k], float)
        Rp = R
        R = Rp @ rot(p1["axis_parent_zero"][k], kin["joints"][k]["pose_deg"])
        out.append({"origin": O.copy(), "R_parent": Rp.copy(), "R_child": R.copy(), "axis": Rp @ np.asarray(p1["axis_parent_zero"][k], float)})
    return out


def unit_(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def v1_frozen():
    man = json.loads((V1 / "frozen-manifest.json").read_text(encoding="utf-8"))
    files = man.get("files") or man.get("frozen") or man
    items = files.items() if isinstance(files, dict) else [(f.get("path") or f.get("file"), f.get("sha256")) for f in files]
    out = {}
    for rel, want in items:
        path = ROOT / rel
        got = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        out[str(rel)] = {"manifest": want, "now": got, "same": want == got}
    return out


ROLE_RULES = [(r"^J\d_MODULE$|_HUB$|^LINK\d_.*_BAR$|^LINK1_POST$|^LINK4_NECK$|^BASE_COLUMN$|^LINK1_SHOULDER_CAP$", "body"),
              (r"_ACCENT_RING$|_END_CAP$|_HUB_CAP$|^LINK2_LOGO_[KMJH]$", "accent"),
              (r"^BASE_FOOT$|^LINK6_TOOL_FLANGE$", "frame"),
              (r"_SLASH$|^BASE_LIGHT_RING$|^LINK6_TOOL_RING$", "highlight")]


def role_by_name(name):
    hits = [role for pat, role in ROLE_RULES if re.search(pat, name)]
    return hits[0] if len(hits) == 1 else None


def joint_of_revolved(name):
    m = re.match(r"^J(\d)_(MODULE|ACCENT_RING|END_CAP)$", name)
    if m:
        return int(m.group(1))
    return {"BASE_FOOT": 1, "BASE_COLUMN": 1, "BASE_LIGHT_RING": 1, "LINK1_SHOULDER_CAP": 1, "LINK2_SHOULDER_HUB": 2, "LINK2_SHOULDER_HUB_CAP": 2,
            "LINK3_ELBOW_HUB": 3, "LINK3_ELBOW_HUB_CAP": 3, "LINK5_WRIST_HUB": 5, "LINK5_WRIST_HUB_CAP": 5, "LINK6_TOOL_FLANGE": 6,
            "LINK6_TOOL_RING": 6}.get(name)


def octagon(hw, hh, c):
    return [(hw, -hh + c), (hw, hh - c), (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c), (-hw + c, -hh), (hw - c, -hh)]


def bar_volume(hw, hh, c, L, yc=None, end_edge_y=None):
    """팔각 막대(단면 y-z · 길이 x) − 45° 끝 자르기 — trimesh + manifold 불리언(생성기와 다른 기하 엔진)."""
    import trimesh
    from shapely.geometry import Polygon
    bar = trimesh.creation.extrude_polygon(Polygon(octagon(hw, hh, c)), L)                    # (u, v, w) = (y - yc, z, x)
    if end_edge_y is None:
        return float(bar.volume)
    sg = 1.0 if yc > 0 else -1.0
    y_out = yc + sg * hw
    x_a = L - abs(y_out - end_edge_y)
    tri = [(x_a - 1, y_out + sg), (L + 1, y_out + sg), (L + 1, end_edge_y - sg)]                # (x, y)
    cut = trimesh.creation.extrude_polygon(Polygon(tri), 2 * hh + 2)                           # (x, y, z') · z' = z + hh + 1
    M = np.array([[0, 1, 0, -yc], [0, 0, 1, -hh - 1], [1, 0, 0, 0], [0, 0, 0, 1]], float)       # (x, y, z') → (y - yc, z, x)
    cut.apply_transform(M)
    return float(trimesh.boolean.difference([bar, cut], engine="manifold").volume)


def native_volume(b):
    return b["mass_g"] / b["density_g_cm3"] * 1000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "armold-mks-product-v3")
    ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "product-v3-evidence" / "check")
    ap.add_argument("--build-evidence", type=Path, default=ROOT / ".dev" / "product-v3-evidence" / "build")
    ap.add_argument("--snapshot", type=Path, default=ROOT / ".dev" / "product-v3-evidence" / "protected-snapshot-before.json")
    ap.add_argument("--protected-root", type=Path, default=None, help="보호 폴더 사본의 뿌리(양성 대조용) — 기본 = 저장소")
    ap.add_argument("--scratch-root", type=Path, default=None)
    ap.add_argument("--parse-only", action="store_true")
    a = ap.parse_args()
    model = checked_dir(a.model, ROOT, a.scratch_root)
    evidence = checked_dir(a.evidence, ROOT, a.scratch_root)
    out_json = checked_file(model / "validation.json", ROOT, a.scratch_root)
    control_mode = a.protected_root is not None
    if control_mode:
        pr = Path(os.path.abspath(a.protected_root)).resolve()
        checked_dir(a.protected_root, ROOT, a.scratch_root)          # 사본은 격리 작업 뿌리 아래에만
        if a.scratch_root is None or ROOT.resolve() in pr.parents or pr == ROOT.resolve():
            raise SystemExit("--protected-root is a control copy under --scratch-root only")
    evidence.mkdir(parents=True, exist_ok=True)
    native = model / f"{NAME}.solidcraft"
    bj = json.loads((model / "bodies.json").read_text(encoding="utf-8"))
    bodies = {b["name"]: b for b in bj["bodies"]}
    colors = bj["colors"]
    kin = json.loads((V1 / "kinematics.json").read_text(encoding="utf-8"))
    p1 = json.loads((V1 / "parameters.json").read_text(encoding="utf-8"))
    p2 = json.loads(V2P.read_text(encoding="utf-8"))
    p3 = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    sign = p2["exterior"]["output_side_sign"]
    D = float(p1["reducer_depth_mm"])
    RDs = [d / 2 for d in p1["reducer_diameters_mm"]]
    e2 = p2["exterior"]
    RC = float(e2["motor_can_radius_mm"])
    LC = float(3 + p1["motor_length_mm"] + 2 + p1["driver_depth_mm"] + e2["can_rear_clearance_mm"])
    CAP, RW, RT = float(e2["end_cap_thickness_mm"]), float(e2["accent_ring_width_mm"]), float(e2["accent_ring_depth_mm"])
    L2 = p2["links"]
    fk = fk_from_v1(p1, kin)
    from kmjh_logo import letters
    logo_rows, logo_w = letters()
    tif = tool_interface_expected(p3, HERE)                               # MP9 2 단계: 공구 끝 규격 = 그리퍼 parameters · 원장(따로 읽음)
    expected = expected_bodies(p1, p2, p3, fk, logo_rows, logo_w, tif)   # 바디 이름 · 소속 · 역할 · 기대 형상의 정답(생성기와 따로 만듦)

    # ---- SolidCraft: 가정 상자 + 관절 목록 + 간섭 ----
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
    cmds += [{"command": "joint.list", "params": {}}, {"command": "inspect.interference", "params": {"budget_s": 1200}}]
    script = checked_file(evidence / "check-commands.json", ROOT, a.scratch_root)
    result_path = checked_file(evidence / "check-result.json", ROOT, a.scratch_root)
    eval_path = checked_file(evidence / "eval-now.json", ROOT, a.scratch_root)
    cprov_path = checked_file(evidence / "check-provenance.json", ROOT, a.scratch_root)

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    native_sha = sha(native)
    if not a.parse_only:
        script.write_text(json.dumps({"commands": cmds}, indent=1) + "\n", encoding="utf-8")
        env = dict(os.environ, SOLIDCRAFT_GPU="cpu")
        p = subprocess.run([str(a.cli), "run", str(script), "--in", str(native), "--results", "--json-out", str(result_path)],
                           capture_output=True, text=True, encoding="utf-8", timeout=3600, env=env)
        checked_file(evidence / "check-stderr.txt", ROOT, a.scratch_root).write_text(p.stderr, encoding="utf-8")
        if p.returncode:
            raise SystemExit(f"check run rc {p.returncode}: {p.stderr[-1500:]}")
        p = subprocess.run([str(a.cli), "eval", str(native), "--json-out", str(eval_path)], capture_output=True, text=True, encoding="utf-8",
                           timeout=1800, env=env)
        if p.returncode:
            raise SystemExit(f"eval rc {p.returncode}: {p.stderr[-1500:]}")
        if sha(native) != native_sha:
            raise SystemExit("native changed while it was being checked")
        cprov_path.write_text(json.dumps({"native": native_sha, "check_result": sha(result_path), "eval_now": sha(eval_path)}, indent=1) + "\n",
                              encoding="utf-8")
    cprov = json.loads(cprov_path.read_text(encoding="utf-8")) if cprov_path.exists() else {}
    bprov_path = Path(a.build_evidence) / "provenance.json"
    bprov = json.loads(bprov_path.read_text(encoding="utf-8")) if bprov_path.exists() else {}
    bind = {
        "check_and_eval_made_from_this_native": cprov.get("native") == native_sha and cprov.get("check_result") == sha(result_path)
                                                and eval_path.exists() and cprov.get("eval_now") == sha(eval_path),
        "native_is_the_build_output": bprov.get("native") == native_sha,
        "every_stl_is_the_build_output": bool(bprov.get("stl")) and all((model / "meshes" / f"{n}.stl").exists()
                                                                        and sha(model / "meshes" / f"{n}.stl") == h for n, h in bprov["stl"].items())
                                         and sorted(bprov["stl"]) == sorted(q.stem for q in (model / "meshes").glob("*.stl")),
    }
    res = json.loads(result_path.read_text(encoding="utf-8"))
    results = res if isinstance(res, list) else res.get("results", [])
    inter = joints = None
    for r in results:
        for body in (r, r.get("result") if isinstance(r, dict) else None):
            if isinstance(body, dict) and "interferences" in body:
                inter = body
            if isinstance(body, dict) and "joints" in body and isinstance(body["joints"], list):
                joints = body["joints"]

    # ---- C1c native 구조 · 소속 ----
    with zipfile.ZipFile(native) as z:
        doc = json.loads(z.read("document.json"))
    comp_name = {c["id"]: c["name"] for c in doc["components"]}
    link_of_comp = {"Base": 0, **{f"Link{i}": i for i in range(1, 7)}}
    native_owner = {}
    for f in doc["features"]:
        if f.get("operation") == "new_body":
            for bn in f.get("body_names", []):
                native_owner[bn] = link_of_comp.get(comp_name.get(f["component"]))
    occ = doc["occurrences"]
    occ_name = {o["id"]: o["name"] for o in occ}
    eye = np.eye(4).tolist()
    chain = [(occ_name[j["a"]["occurrence"]], occ_name[j["b"]["occurrence"]]) for j in doc["assembly"]["joints"]]
    struct = {
        "components": sorted(comp_name.values()) == sorted(["Base"] + [f"Link{i}" for i in range(1, 7)]),
        "occurrences_identity": len(occ) == 7 and all(np.allclose(o["transform"], eye) for o in occ),
        "only_base_grounded": [o["name"] for o in occ if o.get("grounded")] == ["Base:1"],
        "joint_chain": chain == [("Base:1" if i == 0 else f"Link{i}:1", f"Link{i + 1}:1") for i in range(6)],
        "joints_revolute_display_zero": len(doc["assembly"]["joints"]) == 6 and all(
            j["kind"] == "revolute" and j.get("values") == [0.0] and j["name"] == f"J{i + 1}_DISPLAY_ZERO" for i, j in enumerate(doc["assembly"]["joints"])),
        "body_owner_equals_bodies_json": set(native_owner) == set(bodies) and all(native_owner[n] == bodies[n]["link"] for n in bodies),
        "body_names_equal_expected": set(native_owner) == set(expected) == set(bodies),
        "body_owner_equals_expected": all(native_owner.get(n) == e["link"] for n, e in expected.items()),
        "bodies_json_link_role_equal_expected": all(n in bodies and bodies[n]["link"] == e["link"] and bodies[n]["role"] == e["role"]
                                                    for n, e in expected.items()),
    }

    doc_rows = []
    dj = doc["assembly"]["joints"]
    for i, j in enumerate(kin["joints"]):
        if i >= len(dj):
            doc_rows.append({"joint": j["name"], "ok": False})
            continue
        sa, sb = dj[i]["a"]["snap"], dj[i]["b"]["snap"]
        O, A = np.asarray(j["origin_mm"], float), np.asarray(j["axis_world"], float)
        eo = max(float(np.max(np.abs(np.asarray(sa["point"], float) - O))), float(np.max(np.abs(np.asarray(sb["origin"], float) - O))))
        ea = max(float(np.max(np.abs(unit_(sa["z"]) - A))), float(np.max(np.abs(unit_(sb["z"]) - A))))
        doc_rows.append({"joint": j["name"], "origin_err_mm": eo, "axis_err": ea, "ok": eo <= 1e-6 and ea <= 1e-9})
    doc_joints_ok = len(doc_rows) == 6 and len(dj) == 6 and all(r["ok"] for r in doc_rows)
    inter_complete = (isinstance(inter, dict) and isinstance(inter.get("interferences"), list) and inter.get("unchecked") == []
                      and inter.get("pairs_not_checked") == 0 and inter.get("budget_exceeded") is False and inter.get("truncated") is False)

    def owner(name):
        """간섭의 링크 소속 — 독립 정답표(없는 이름이면 native 소속). 생성기 · native 가 함께 틀려도 간섭 판정은 정답표로 한다."""
        if name.startswith("KEEPOUT_"):
            return "keepout"
        return expected[name]["link"] if name in expected else native_owner.get(name)

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
    marks = sorted(n for n in bodies if n.endswith("_SLASH") or "_LOGO_" in n or n.endswith("_HUB_CAP"))
    buried_marks = [it for it in inter["interferences"] if (it["a"] in marks or it["b"] in marks)
                    and not (owner(it["a"]) == "keepout" or owner(it["b"]) == "keepout")]
    keep_rows = []
    for kp in keep:
        mod = f"J{kp['joint']}_MODULE"
        hits = kept.get(kp["name"], [])
        inside = sum(h["volume_mm3"] for h in hits if h["body"] == mod)
        other_links = [h for h in hits if h["link"] not in ("keepout", kp["owner_link"])]
        keep_rows.append({**kp, "inside_module_mm3": inside, "ratio": inside / kp["volume_mm3"], "other_link_overlaps": other_links})

    # ---- C1 관절 · C1a 순기구학 ----
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
            row["origin_err_mm"] = max(errs_o)
            row["axis_unit_component_err"] = max(errs_a)
            row["ok"] = got.get("type") == "revolute" and row["origin_err_mm"] <= 1e-6 and row["axis_unit_component_err"] <= 1e-9
        jok = jok and row.get("ok", False)
        jrows.append(row)
    fk_rows = []
    for k, (j, f) in enumerate(zip(kin["joints"], fk), start=1):
        e_o = float(np.max(np.abs(f["origin"] - np.asarray(j["origin_mm"], float))))
        e_r = float(np.max(np.abs(f["R_child"] - np.asarray(j["R_child"], float))))
        e_a = float(np.max(np.abs(f["axis"] - np.asarray(j["axis_world"], float))))
        fk_rows.append({"joint": k, "origin_err_mm": e_o, "R_child_err": e_r, "axis_err": e_a, "ok": e_o <= 1e-9 and e_r <= 1e-9 and e_a <= 1e-9})

    # ---- 평가 · 메시 ----
    ev = json.loads(eval_path.read_text(encoding="utf-8"))
    ev_bodies = {b["name"]: b for b in ev["bodies"]}
    import trimesh
    meshes = {}
    for n in bodies:
        path = model / "meshes" / f"{n}.stl"
        if path.exists():
            meshes[n] = trimesh.load_mesh(path)

    # ---- C1b 회전체 무게중심이 관절 축 위 ----
    com_rows = []
    for name, b in ev_bodies.items():
        k = joint_of_revolved(name)
        if k is None:
            continue
        O, A = fk[k - 1]["origin"], fk[k - 1]["axis"]
        c = np.asarray(b["center_of_mass"], float) - O
        dist = float(np.linalg.norm(c - A * np.dot(c, A)))
        com_rows.append({"body": name, "joint": k, "com_to_axis_mm": dist, "ok": dist <= 1e-3})
    revolved_expected = {n for n in bodies if joint_of_revolved(n) is not None}

    # ---- C1d 링크 좌표 형상 = v1 · v2 값 ----
    def axial_radial(n, k, sgn):
        v = np.asarray(meshes[n].vertices)
        A = fk[k - 1]["axis"] * sgn
        d = v - fk[k - 1]["origin"]
        t = d @ A
        r = np.linalg.norm(d - np.outer(t, A), axis=1)
        return t, r

    def in_link(n, link):
        v = np.asarray(meshes[n].vertices)
        if link == 0:
            return v
        return (v - fk[link - 1]["origin"]) @ fk[link - 1]["R_child"]

    geo = []

    def expect(label, got, want):
        geo.append({"what": label, "got": float(got), "want": float(want), "ok": abs(got - want) <= TOL})

    for k in range(1, 7):
        R = RDs[k - 1]
        if f"J{k}_MODULE" in meshes:
            t, r = axial_radial(f"J{k}_MODULE", k, sign[k - 1])
            expect(f"J{k}_MODULE axial min (motor can rear)", t.min(), -D / 2 - LC)
            expect(f"J{k}_MODULE axial max (output face)", t.max(), D / 2)
            expect(f"J{k}_MODULE max radius (drum)", r.max(), max(R, RC))
            expect(f"J{k}_MODULE can radius", r[t < -D / 2 - 2.5].max(), RC)
        if f"J{k}_ACCENT_RING" in meshes:
            t, r = axial_radial(f"J{k}_ACCENT_RING", k, sign[k - 1])
            expect(f"J{k}_ACCENT_RING axial min", t.min(), D / 2 - RW)
            expect(f"J{k}_ACCENT_RING axial max", t.max(), D / 2)
            expect(f"J{k}_ACCENT_RING outer radius", r.max(), R)
        if f"J{k}_END_CAP" in meshes:
            t, r = axial_radial(f"J{k}_END_CAP", k, sign[k - 1])
            expect(f"J{k}_END_CAP axial min", t.min(), -D / 2 - LC - CAP)
            expect(f"J{k}_END_CAP axial max", t.max(), -D / 2 - LC)
            expect(f"J{k}_END_CAP radius", r.max(), RC - 1)
    for n, k, link, key in (("LINK2_SHOULDER_HUB", 2, 2, "upper_arm"), ("LINK3_ELBOW_HUB", 3, 3, "forearm"), ("LINK5_WRIST_HUB", 5, 5, "wrist2")):
        if n in meshes:
            v = in_link(n, link)
            lo, hi = (-D / 2 - L2[key]["hub_t"], -D / 2) if link == 3 else (D / 2, D / 2 + L2[key]["hub_t"])
            expect(f"{n} y min", v[:, 1].min(), lo)
            expect(f"{n} y max", v[:, 1].max(), hi)
            expect(f"{n} radius", np.linalg.norm(v[:, [0, 2]], axis=1).max(), L2[key]["hub_r"])
    bars = (("LINK2_UPPER_BAR", 2, "upper_arm", p1["upper_arm_mm"], 1), ("LINK3_FOREARM_BAR", 3, "forearm", L2["forearm"]["tube_len"], -1),
            ("LINK5_WRIST_BAR", 5, "wrist2", L2["wrist2"]["tube_len"], 1))
    for n, link, key, L, sy in bars:
        if n in meshes:
            v = in_link(n, link)
            yc = sy * (D / 2 + L2[key]["hub_t"] / 2)
            hw = L2[key]["tube_r"]
            expect(f"{n} x min (joint {link} centre)", v[:, 0].min(), 0.0)
            expect(f"{n} x max", v[:, 0].max(), L)
            expect(f"{n} y min", v[:, 1].min(), yc - hw)
            expect(f"{n} y max", v[:, 1].max(), yc + hw)
            expect(f"{n} z half", np.abs(v[:, 2]).max(), hw)
    if "LINK4_NECK" in meshes:
        v = in_link("LINK4_NECK", 4)
        w = L2["wrist1"]
        expect("LINK4_NECK x min", v[:, 0].min(), D / 2)
        expect("LINK4_NECK x max", v[:, 0].max(), p1["wrist_offsets_mm"][0] - w["neck_gap"])
        expect("LINK4_NECK y half", np.abs(v[:, 1]).max(), w["neck_w"] / 2)
        expect("LINK4_NECK z half", np.abs(v[:, 2]).max(), w["neck_h"] / 2)
    if "LINK1_POST" in meshes:
        v = in_link("LINK1_POST", 1)
        c = L2["shoulder"]
        expect("LINK1_POST z min", v[:, 2].min(), D / 2)
        expect("LINK1_POST z max (joint 2)", v[:, 2].max(), p1["shoulder_rise_mm"])
        expect("LINK1_POST y min", v[:, 1].min(), c["post_y0"])
        expect("LINK1_POST y max", v[:, 1].max(), c["post_y1"])
        expect("LINK1_POST x half", np.abs(v[:, 0]).max(), c["post_half_w"])
    if "BASE_COLUMN" in meshes:
        v = meshes["BASE_COLUMN"].vertices
        b = L2["base"]
        expect("BASE_COLUMN z min", v[:, 2].min(), b["foot_h"])
        expect("BASE_COLUMN z max (J1 drum)", v[:, 2].max(), p1["joint1_height_mm"] - D / 2)
        expect("BASE_COLUMN radius", np.linalg.norm(v[:, :2], axis=1).max(), b["column_r"])
    if "BASE_FOOT" in meshes:
        v = meshes["BASE_FOOT"].vertices
        expect("BASE_FOOT z max", v[:, 2].max(), L2["base"]["foot_h"])
        expect("BASE_FOOT radius", np.linalg.norm(v[:, :2], axis=1).max(), L2["base"]["foot_r"])
    if "LINK6_TOOL_FLANGE" in meshes:
        v = in_link("LINK6_TOOL_FLANGE", 6)
        t = L2["tool"]
        expect("LINK6_TOOL_FLANGE x min", v[:, 0].min(), D / 2)
        expect("LINK6_TOOL_FLANGE x max", v[:, 0].max(), D / 2 + t["flange_t"])
        expect("LINK6_TOOL_FLANGE radius", np.linalg.norm(v[:, 1:], axis=1).max(), t["flange_r"])
    if "LINK6_TOOL_RING" in meshes:                                       # MP9 2 단계: 돌기 = 그리퍼 받침 맞춤 홈
        v = in_link("LINK6_TOOL_RING", 6)
        f1 = D / 2 + L2["tool"]["flange_t"]
        expect("LINK6_TOOL_RING (boss) x min", v[:, 0].min(), f1)
        expect("LINK6_TOOL_RING (boss) x max", v[:, 0].max(), f1 + tif["boss_t"])
        expect("LINK6_TOOL_RING (boss) radius", np.linalg.norm(v[:, 1:], axis=1).max(), tif["boss_r"])
    prot_keys = {"exterior": ["motor_can_radius_mm", "can_rear_clearance_mm", "end_cap_thickness_mm", "accent_ring_width_mm", "accent_ring_depth_mm",
                              "output_side_sign"]}
    param_rows = [{"key": f"exterior.{k}", "v3": p3["exterior"][k], "v2": e2[k], "ok": p3["exterior"][k] == e2[k]} for k in prot_keys["exterior"]]
    for link, kv in (("base", ["foot_r", "foot_h", "column_r", "band_z0", "band_z1", "column_top_r"]),
                     ("shoulder", ["cap_r", "cap_h", "post_half_w", "post_y0", "post_y1"]),
                     ("upper_arm", ["hub_r", "hub_t"]), ("forearm", ["hub_r", "hub_t", "tube_len"]),
                     ("wrist1", ["neck_w", "neck_h", "neck_gap"]), ("wrist2", ["hub_r", "hub_t", "tube_len"]),
                     ("tool", ["flange_r", "flange_t"])):
        for k in kv:
            param_rows.append({"key": f"links.{link}.{k}", "v3": p3["links"][link][k], "v2": L2[link][k], "ok": p3["links"][link][k] == L2[link][k]})
    # MP9 2 단계: 옛 고리 값(ring_r · ring_t = v2)은 v3 에서 지웠다 — 돌기 · 구멍 숫자가 v3 parameters 에 다시 생기면 거짓(원천 = 그리퍼 · 원장 하나)
    t3 = p3["links"]["tool"]
    tool_keys = ("flange_r", "flange_t", "flange_chamfer", "interface_from", "screw_hole_extra_depth", "screw_hole_min_floor", "interface_note", "limits_note")
    param_rows.append({"key": "links.tool has no ring_r/ring_t/boss/hole numbers (interface_from only)",
                       "v3": sorted(k for k in t3 if k not in tool_keys), "v2": [], "ok": not [k for k in t3 if k not in tool_keys]})
    param_rows.append({"key": "tool insert hole = ledger confirmed", "v3": tif["hole_status"], "v2": "confirmed", "ok": tif["hole_status"] == "confirmed"})
    # 검토 MP9-B1 · B5: 구멍 한계(플랜지 · 모따기 = v2 값 · 바닥 살 = v3 값)와 원장 재료 = 그리퍼 끼움 재료 — 생성기의 단언과 따로
    t2 = L2["tool"]
    lim_rows = [("tool hole depth <= flange_t - min_floor", tif["hole_depth"], t2["flange_t"] - t3["screw_hole_min_floor"], tif["hole_depth"] <= t2["flange_t"] - t3["screw_hole_min_floor"]),
                ("tool holes clear boss (pcd/2 - d/2 > boss_r)", tif["pcd"] / 2 - tif["hole_d"] / 2, tif["boss_r"], tif["pcd"] / 2 - tif["hole_d"] / 2 > tif["boss_r"]),
                ("tool holes inside flange face (pcd/2 + d/2 < flange_r - chamfer)", tif["pcd"] / 2 + tif["hole_d"] / 2, t2["flange_r"] - t3["flange_chamfer"],
                 tif["pcd"] / 2 + tif["hole_d"] / 2 < t2["flange_r"] - t3["flange_chamfer"]),
                ("tool interface material = gripper fits_from.material", tif["material"], tif["gripper_fits_material"], tif["material"] == tif["gripper_fits_material"])]
    for k, got, lim, ok in lim_rows:
        param_rows.append({"key": k, "v3": got, "v2": lim, "ok": bool(ok)})
    for link in ("upper_arm", "forearm", "wrist2"):
        for k in ("bar_half_w", "bar_half_h"):
            param_rows.append({"key": f"links.{link}.{k} = v2 tube_r", "v3": p3["links"][link][k], "v2": L2[link]["tube_r"],
                               "ok": p3["links"][link][k] == L2[link]["tube_r"]})

    # ---- C5 저장 색 ----
    stored = doc["appearances"]["bodies"]
    hexrgb = {role: [int(h[i:i + 2], 16) for i in (1, 3, 5)] for role, h in colors.items()}
    brand = {"body": "#FFFFFF", "accent": "#0B2545", "frame": "#6B7280", "highlight": "#34D399"}    # docs/brand/README.md 표기
    color_rows = []
    for name in sorted(set(bodies) | set(stored) | set(ev_bodies) | set(expected)):
        want = role_by_name(name)
        row = {"body": name, "role_by_name": want, "role_expected": expected.get(name, {}).get("role"),
               "role_in_bodies_json": bodies.get(name, {}).get("role"), "stored_rgb": (stored.get(name) or {}).get("color"), "in_eval": name in ev_bodies}
        row["ok"] = (want is not None and want == row["role_expected"] and row["role_in_bodies_json"] == want and row["stored_rgb"] == hexrgb[want]
                     and row["in_eval"] and (stored.get(name) or {}).get("opacity", 1.0) == 1.0)
        color_rows.append(row)
    palette_ok = {r: h.upper() for r, h in colors.items()} == brand

    # ---- C6 메시 = native ----
    mesh_rows = []
    for name in sorted(bodies):
        row = {"body": name, "exists": name in meshes}
        if name in meshes:
            m, b = meshes[name], ev_bodies[name]
            bb = b["bbox"]
            nv = native_volume(b)
            row.update({"faces": int(len(m.faces)), "watertight": bool(m.is_watertight),
                        "bbox_err_mm": float(max(np.max(np.abs(m.bounds[0] - np.asarray(bb["min"], float))),
                                                 np.max(np.abs(m.bounds[1] - np.asarray(bb["max"], float))))),
                        "com_err_mm": float(np.linalg.norm(m.center_mass - np.asarray(b["center_of_mass"], float))) if m.is_watertight else None,
                        "volume_rel": float(abs(m.volume - nv) / nv), "area_rel": float(abs(m.area - b["area_mm2"]) / b["area_mm2"])})
            row["ok"] = (row["faces"] > 0 and row["watertight"] and row["bbox_err_mm"] <= C6_BBOX_COM_MM and row["com_err_mm"] is not None
                         and row["com_err_mm"] <= C6_BBOX_COM_MM and row["volume_rel"] <= 2e-3 and row["area_rel"] <= 2e-3)
        else:
            row["ok"] = False
        mesh_rows.append(row)
    stray = sorted(p.stem for p in (model / "meshes").glob("*.stl") if p.stem not in bodies)

    # ---- C1e 독립 기대 형상 ↔ STL(양방향 표면 거리) ----
    shape_rows = []
    for name, e in expected.items():
        if name not in meshes:
            shape_rows.append({"body": name, "missing_mesh": True, "ok": False})
            continue
        d1, d2 = surface_distance(meshes[name], e["mesh"])
        shape_rows.append({"body": name, "stl_to_expected_mm": d1, "expected_to_stl_mm": d2, "ok": d1 <= SHAPE_TOL_MM and d2 <= SHAPE_TOL_MM})

    # ---- C6b 특징 체적(독립 계산) ----
    sys.path.insert(0, str(HERE))
    from kmjh_logo import letters
    from shapely.geometry import Polygon
    em = p3["marks"]["emboss_mm"]
    feat = []

    def fexpect(name, want, tol=1e-6):
        """tol: 평면으로만 된 바디 1e-6 · 원기둥 면이 있는 바디 2e-4(native 평가의 체적이 곡면을 잘게 나눈 값이라 원판은 약 6e-5 작게 나옴)."""
        if name in ev_bodies:
            got = native_volume(ev_bodies[name])
            feat.append({"body": name, "native_mm3": got, "independent_mm3": want, "rel": abs(got - want) / want, "tol": tol,
                         "ok": abs(got - want) / want <= tol})
        else:
            feat.append({"body": name, "missing": True, "ok": False})

    rows_l, _w = letters()
    h = p3["marks"]["logo"]["cap_height"]
    for nm, _role, pts in rows_l:
        fexpect(f"LINK2_LOGO_{nm}", Polygon(pts).area * h * h * em)
    cs = p3["marks"]["cap_slash"]
    for k in cs["joints"]:
        fexpect(f"J{k}_CAP_SLASH", cs["height"] * cs["width"] * em)
    for n, key, sc in (("LINK2_SHOULDER_HUB", "upper_arm", 1.0), ("LINK3_ELBOW_HUB", "forearm", 1.0), ("LINK5_WRIST_HUB", "wrist2", 0.8)):
        r = L2[key]["hub_r"] - p3["exterior"]["hub_chamfer_mm"] - 2
        fexpect(n + "_CAP", math.pi * r * r * 1.0, tol=2e-4)
        fexpect(n + "_SLASH", cs["height"] * sc * cs["width"] * sc * em)
    u, f_, w = p3["links"]["upper_arm"], p3["links"]["forearm"], p3["links"]["wrist2"]
    fexpect("LINK2_UPPER_BAR", bar_volume(u["bar_half_w"], u["bar_half_h"], u["bar_chamfer"], p1["upper_arm_mm"]))
    fexpect("LINK3_FOREARM_BAR", bar_volume(f_["bar_half_w"], f_["bar_half_h"], f_["bar_chamfer"], f_["tube_len"], yc=-(D / 2 + f_["hub_t"] / 2),
                                            end_edge_y=-math.sqrt((RC - 0.5) ** 2 - f_["bar_half_h"] ** 2)))
    fexpect("LINK5_WRIST_BAR", bar_volume(w["bar_half_w"], w["bar_half_h"], w["bar_chamfer"], w["tube_len"], yc=D / 2 + w["hub_t"] / 2,
                                          end_edge_y=math.sqrt((RC - 0.5) ** 2 - w["bar_half_h"] ** 2)))
    nk = p3["links"]["wrist1"]
    fexpect("LINK4_NECK", Polygon(octagon(nk["neck_w"] / 2, nk["neck_h"] / 2, nk["neck_chamfer"])).area * (p1["wrist_offsets_mm"][0] - nk["neck_gap"] - D / 2))
    sh = p3["links"]["shoulder"]
    fexpect("LINK1_POST", Polygon(octagon(sh["post_half_w"], (sh["post_y1"] - sh["post_y0"]) / 2, sh["post_chamfer"])).area * (p1["shoulder_rise_mm"] - D / 2))

    # ---- C4 보호 폴더 ----
    proot = a.protected_root or ROOT
    before = json.loads(a.snapshot.read_text(encoding="utf-8"))
    base_ok = before.get("roots") == PROTECTED_REL and all(any(k.startswith(r + "/") for k in before["files"]) for r in PROTECTED_REL)
    now = snapshot(proot, PROTECTED_REL)                     # 보호 폴더 목록은 상수 — 스냅숏 파일에서 받지 않는다
    prot = compare(before["files"], now)
    snap_sha = hashlib.sha256(a.snapshot.read_bytes()).hexdigest()
    frozen = v1_frozen()
    not_run = []
    head_rows = None
    if a.protected_root is None and (ROOT / ".git").exists():
        head_rows = {}
        for line in git("ls-files", "-s", "--", "models/armold-mks-product-v2", "src/cad/armold-mks-product-v2").splitlines():
            meta, path = line.split("\t", 1)
            head = git("rev-parse", f"HEAD:{path}").strip()
            nowb = git("hash-object", "--", path).strip() if (ROOT / path).exists() else None
            head_rows[path] = {"head": head, "worktree": nowb, "same": head == nowb}
    else:
        not_run.append("C4_v2_tracked_equal_head (no .git or protected-root copy)")

    checks = {
        "C1_joints_match_v1": jok,
        "C1a_kinematics_equal_v1_forward_kinematics": len(fk_rows) == 6 and all(r["ok"] for r in fk_rows),
        "C1b_revolved_bodies_on_their_joint_axis": len(com_rows) == len(revolved_expected) and all(r["ok"] for r in com_rows),
        "C1c_native_structure_and_body_owners": all(struct.values()),
        "C1d_link_frame_geometry_equals_v1_v2": bool(geo) and all(r["ok"] for r in geo) and all(r["ok"] for r in param_rows),
        "C1e_every_body_matches_independent_expected_shape": len(shape_rows) == len(expected) and all(r["ok"] for r in shape_rows),
        "C0_outputs_and_evidence_bound_to_current_native": all(bind.values()),
        "C1_native_document_joints_match_v1": doc_joints_ok,
        "C2_interference_complete": inter_complete,
        "C2_cross_link_interference_0": len(cross) == 0,
        "C2b_marks_overlap_no_body": bool(marks) and not buried_marks,
        "C3_keepout_boxes_18": len(keep_rows) == 18,
        "C3_keepouts_100pct_inside_their_module": all(abs(r["ratio"] - 1) <= 1e-9 for r in keep_rows),
        "C3_keepouts_no_other_link_overlap": all(not r["other_link_overlaps"] for r in keep_rows),
        ("C4_CONTROL_copy_equal_start_snapshot" if control_mode else "C4_protected_folders_equal_start_snapshot"): base_ok and prot["same"],
        "C4_v1_frozen_files_unchanged": all(v["same"] for v in frozen.values()),
        "C5_stored_colors_match_roles": palette_ok and bool(color_rows) and all(r["ok"] for r in color_rows) and set(bodies) == set(ev_bodies) == set(stored),
        "C6_one_faithful_mesh_per_body": bool(mesh_rows) and all(r["ok"] for r in mesh_rows) and not stray,
        "C6b_feature_volumes_independent": bool(feat) and all(r["ok"] for r in feat),
    }
    if head_rows is not None:
        checks["C4_v2_tracked_equal_head"] = bool(head_rows) and all(v["same"] for v in head_rows.values())
    out = {"mode": "control" if control_mode else "normal", "binding": bind, "check_provenance": cprov, "native_sha256": native_sha,
           "native_document_joints": doc_rows,
           "acceptance": (not control_mode) and all(checks.values()),
           "checks": checks, "not_run": not_run, "structure": struct, "cross_link": cross, "same_link_overlaps": same, "marks": marks,
           "buried_marks": buried_marks, "keepouts": keep_rows, "joints": jrows, "fk_v1": fk_rows, "revolved_com": com_rows, "geometry": geo,
           "independent_shapes": shape_rows, "expected_bodies": {n: {"link": e["link"], "role": e["role"]} for n, e in expected.items()},
           "protected_params": param_rows, "colors": color_rows, "meshes": mesh_rows, "stray_meshes": stray, "feature_volumes": feat,
           "protected_snapshot": {**prot, "root": str(proot), "baseline_roots_fixed": base_ok, "baseline_sha256": snap_sha},
           "v2_head": head_rows, "v1_frozen": frozen, "unchecked": inter.get("unchecked", []),
           "scope": ["Interference is checked at the display pose only (the pose the model is built in) - other poses and continuous rotation are not checked.",
                     "Blender rotation tests (C7) are kinematic checks, not collision checks.",
                     "Envelope bodies are solid; containment = keep-out box fully inside the solid module (v1 motor/driver/connector assumptions)."]}
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1))
    print("mode", out["mode"], "acceptance", out["acceptance"], "not_run", not_run)
    print("cross", len(cross), "same", len(same), "keepouts", len(keep_rows), "revolved", len(com_rows), "geometry", len(geo), "features", len(feat),
          "shapes", len(shape_rows), "max_shape_mm", max((max(r.get("stl_to_expected_mm", 9), r.get("expected_to_stl_mm", 9)) for r in shape_rows), default=None))
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
