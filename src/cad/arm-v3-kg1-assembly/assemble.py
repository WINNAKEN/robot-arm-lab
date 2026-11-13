# -*- coding: utf-8 -*-
"""MP9 — 외장 v3 팔 끝(링크 6)에 그리퍼 KG1 을 붙인 조립 · 자세 검사 · 보기 GLB (계획 051).

커밋된 STL 만으로 스스로 계산한다(v3 · 그리퍼 생성기를 부르지 않는다). 그리퍼의 부품 배치(벌림 u) · 구매품 기준 입체(서보 · 혼 · 관 · 나사)는
그리퍼 검사기 `src/cad/kmjh-gripper-v1/verify_gripper.py` 의 references · assemble 을 모듈로 불러 읽기만 한다(바이트코드를 쓰지 않음).

- A 붙이기: 링크 6 바디 STL 에서 플랜지 · 고리의 축 방향 끝 · 반지름을 재고(v3 · v1 parameters 값과 대조), 고른 면(parameters mount.face)에
  그리퍼 G 원점을 둔다 → G → 세계(표시 자세) 4 × 4 = assembly.json.
  독립 대조(검토 MP9-R3): v1 parameters(관절 거리 · axis_parent_zero)만으로 순기구학을 따로 계산해, 여러 자세에서 ① 받침 아랫면의 축 방향 위치 =
  고리 끝(돌린 고리 STL 에서 잰 값) ② 손끝 끝 = 고리 끝 + 106 · 쥐는 점이 J6 축 위 ③ q6 = 0 에서 그리퍼 x = +J5 축(roll 0 의 뜻)을 본다.
- B 자세 검사: 갤러리 자세 × 벌림(parameters gripper.openings_u + render_u) — 그리퍼(인쇄 부품 + 구매품 기준 입체) ↔ 팔 링크 0 ~ 5 바디의 겹친 부피(manifold) ·
  바닥 여유 · 팔끼리 겹침 · 가장 가까운 틈(표면 표본점 근사 · 상자가 near_box_mm 안인 바디만 — 그 밖은 「넘음」) · 그리퍼 ↔ 링크 6 겹침(붙인 면 · 고정) ·
  J5 쓸기 · J6 쓸기(팔 겹침 · 바닥 여유를 따로). 쓸기에서 팔끼리 겹침은 그 관절 앞뒤로 갈리는 링크 쌍만 본다(나머지 쌍은 그 관절이 움직여도 상대 위치가 같음).
- 모든 바디 · 부품: manifold 부피 = 메시 부피 · 부피 > 0(열린 · 뒤집힌 메시가 조용히 통과하는 길을 막음 — MP8 교훈 ①).
- 양성 대조(돌 때마다 · 기대대로가 아니면 all_ok 거짓 · 실제 검사와 같은 함수): C1(1 단계: 플랜지 면에 붙임 → 옛 고리 겹침 · 2 단계부터 아래) · C2 축 반대로 60 밀어 넣음 → 팔 겹침 ·
  C3 면 열 개를 뺀 열린 메시 → manifold 키 거짓 · C4 바닥 아래로 1000 → 바닥 키 거짓 · C5 ㄱ 자 대기 자세에서 그리퍼를 J3 원점(팔꿈치)으로 옮김 → 링크 0 ~ 4 겹침 ·
  C6 J5 = 180(접어 넘김) → 팔끼리 겹침(split 5) · C7 free_interval 합성 입력의 답 · C8 돌림 +90° · 돌기 끝에 얹으면 독립 순기구학 대조가 거짓 ·
  (2 단계) C1 = 붙이는 면에서 1 mm 안으로 → 겹침 · C9 돌림 45° → 팔 나사가 플랜지 구멍을 벗어나 겹침 · C10 축에 수직으로 0.5 mm → 돌기가 홈 벽에 겹침(맞춤 쌍).
  (검토 B 뒤) C11 플랜지 구멍 재기가 각 · 개수 · 깊이 잘못을 잡는지.
- 2 단계(검토 B 뒤): 플랜지 나사 자리를 STL 에서 직접 재 그리퍼(팔 나사 원 · 각 · 수) · 원장(지름) · 나사 몸통 길이와 대조(measure_holes) ·
  붙인 그 자세(표시)에서 그리퍼가 팔에 박히면 판정 거짓.
- 겹치는 자세는 실패가 아니라 기록이다(표시 자세만 예외). all_ok = 입력 · 맞춤면 측정 · 구멍 · 붙인 자리 · 독립 순기구학 · manifold · 붙인 면 · 표시 자세 · 대조가 맞는지.

사용(저장소 뿌리에서): python -B assemble.py [--out <조립 산출 폴더>] [--scratch-root <작업 뿌리>] [--quick]
  --quick = 쓸기를 건너뜀(고치는 동안 빨리 보기 — 산출 폴더에는 쓰지 않는다)
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True           # 그리퍼 폴더(보호)에 __pycache__ 를 쓰지 않게(검토 MP9-R9)

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mp9_guard", HERE / "guard.py")
mguard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mguard)
ROOT = mguard.find_root(HERE)
PRM_PATH = HERE / "parameters.json"
PRM = json.loads(PRM_PATH.read_text(encoding="utf-8"))
INP = {k: (HERE / v).resolve() for k, v in PRM["inputs"].items()}
sys.path.insert(0, str(INP["gripper_src"]))
import verify_gripper as vg  # noqa: E402  — 읽기만(references · assemble · ledger · sign_check · m3d · vol)

NAME = "arm-v3-kg1-assembly"
GRIP_PARTS = ["BASE", "JAW_A", "JAW_B", "PINION", "PAD_A_FLAT", "PAD_B_FLAT", "PAD_A_V", "PAD_B_V"]
GRIP_COLORS = {"BASE": "#6B7280", "JAW_A": "#FFFFFF", "JAW_B": "#FFFFFF", "PINION": "#0B2545", "PAD_A": "#6B7280", "PAD_B": "#6B7280",
               "SERVO_BODY": "#141416", "SERVO_PLUGS": "#141416", "SPLINE": "#3A3A3A", "HORN": "#2A2A2A"}
ROD_COLOR, SCREW_COLOR = "#0A0A0A", "#9CA3AF"
CONTROL_MIN_MM3 = 1.0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rot(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def pose_points(P, link, deltas, J):
    """표시 자세의 점 → 자세(deltas = q − pose_deg). 바깥 관절부터 안쪽으로 표시 자세의 축으로 돌린다(MP7 pose_check 와 같은 규약 · 따로 씀)."""
    Q = P
    for k in range(link, 0, -1):
        d = deltas[k - 1]
        if d:
            O, A = J[k - 1]
            Q = (Q - O) @ rot(A, d).T + O
    return Q


def fk_v1(q):
    """독립 순기구학 — v1 parameters 의 관절 거리 · axis_parent_zero 만(kinematics.json 을 안 씀). 반환 = 관절 원점 · 세계 축 · 링크 회전(각 관절 뒤)."""
    p1 = json.loads(INP["v1_params"].read_text(encoding="utf-8"))
    offs = [[0, 0, p1["joint1_height_mm"]], [0, 0, p1["shoulder_rise_mm"]], [p1["upper_arm_mm"], 0, 0], [p1["forearm_mm"], 0, 0],
            [p1["wrist_offsets_mm"][0], 0, 0], [p1["wrist_offsets_mm"][1], 0, 0]]
    R, p = np.eye(3), np.zeros(3)
    O, A, Rc = [], [], []
    for k in range(6):
        ax = np.asarray(p1["axis_parent_zero"][k], float)
        p = p + R @ np.asarray(offs[k], float)
        O.append(p.copy())
        A.append(R @ ax)
        R = R @ rot(ax, q[k])
        Rc.append(R.copy())
    return O, A, Rc


def man(v, f):
    M = vg.m3d()
    return M.Manifold(M.Mesh(vert_properties=np.asarray(v, np.float32), tri_verts=np.asarray(f, np.uint32)))


def manifold_matches(v, f):
    """manifold 부피 = 메시 부피(상대 1e-4) 그리고 부피 > 0 — 열린 메시면 manifold 가 빈 입체 · 뒤집힌 메시면 음수라 거짓."""
    mesh_vol = float(trimesh.Trimesh(vertices=v, faces=f, process=False).volume)
    m = man(v, f)
    mv = vg.vol(m)
    return mesh_vol > 0 and abs(mv - mesh_vol) <= 1e-4 * max(1.0, abs(mesh_vol)), round(mesh_vol, 4), round(mv, 4), str(m.status())


def boxes_near(a, b, gap):
    return bool(np.all(a[0] <= b[1] + gap) and np.all(b[0] <= a[1] + gap))


def samples(v, f, spacing, seed):
    tm = trimesh.Trimesh(vertices=v, faces=f, process=False)
    n = max(64, int(tm.area / spacing ** 2))
    pts, _ = trimesh.sample.sample_surface(tm, n, seed=seed)
    return np.vstack([np.asarray(pts, float), np.asarray(v, float)])


def to_world(v, M):
    return v @ M[:3, :3].T + M[:3, 3]


# ---------------- 입력 ----------------
def load_arm(spacing):
    model = INP["v3_model"]
    bd = json.loads((model / "bodies.json").read_text(encoding="utf-8"))
    out = []
    for i, b in enumerate(bd["bodies"]):
        tm = trimesh.load(model / "meshes" / f"{b['name']}.stl", force="mesh", process=True)
        v, f = np.asarray(tm.vertices, float), np.asarray(tm.faces, np.int64)
        out.append({"name": b["name"], "link": int(b["link"]), "role": b["role"], "color": b["color"], "v": v, "f": f,
                    "s": samples(v, f, spacing, 1000 + i)})
    return out


def load_kin():
    kin = json.loads(INP["v1_kinematics"].read_text(encoding="utf-8"))
    J = [(np.asarray(j["origin_mm"], float), np.asarray(j["axis_world"], float) / np.linalg.norm(j["axis_world"])) for j in kin["joints"]]
    pose_deg = np.array([float(j["pose_deg"]) for j in kin["joints"]])
    R6 = np.asarray(kin["joints"][5]["R_child"], float)
    return J, pose_deg, R6


def load_gripper():
    P = json.loads((INP["gripper_src"] / "parameters.json").read_text(encoding="utf-8"))
    fits, _st = vg.ledger(P)
    vg.sign_check()                       # 피니언 돌림 부호(manifold rotate) — 그리퍼 검사기와 같은 확인
    parts = {}
    for nm in GRIP_PARTS:
        tm = trimesh.load(INP["gripper_model"] / "parts" / f"{nm}.stl", force="mesh", process=True)
        parts[nm] = {"v": np.asarray(tm.vertices, float), "f": np.asarray(tm.faces, np.int64)}
    mans = {nm: man(p["v"], p["f"]) for nm, p in parts.items()}
    refs = vg.references(P, fits)
    return P, parts, mans, refs


def gripper_items(P, mans, refs, u, padset):
    """G 좌표의 그리퍼(벌림 u) — 그리퍼 검사기의 assemble 그대로(인쇄 부품 + 구매품 기준 입체)."""
    r = P["gear"]["module"] * P["gear"]["teeth"] / 2
    out = []
    for lab, grp, printed, solid, _bb in vg.assemble(mans, refs, padset, u, r, P["layout"]["z_c"]):
        m = solid.to_mesh()
        out.append({"name": lab, "group": grp, "printed": bool(printed),
                    "v": np.asarray(m.vert_properties, float)[:, :3], "f": np.asarray(m.tri_verts, np.int64)})
    return out


# ---------------- A 붙이기 ----------------
def axial_radial(V, O, a):
    d = V - O
    ax = d @ a
    return ax, np.linalg.norm(d - np.outer(ax, a), axis=1)


def measure_interface(arm, J, R6, GP):
    """링크 6 플랜지 · 돌기(옛 고리 — 바디 이름 LINK6_TOOL_RING)를 STL 에서 잰다. 기대값: 플랜지 = v3 · v1 parameters · 돌기 = 그리퍼 받침 맞춤 홈(MP9 2 단계)."""
    O, a = J[5]
    got = {}
    for nm, key in (("LINK6_TOOL_FLANGE", "flange"), ("LINK6_TOOL_RING", "ring")):
        b = next(x for x in arm if x["name"] == nm)
        ax, rad = axial_radial(b["v"], O, a)
        got[f"{key}_end"] = float(ax.max())
        got[f"{key}_start"] = float(ax.min())
        got[f"{key}_r"] = float(rad.max())
        got[f"{key}_link"] = b["link"]
    v3p = json.loads(INP["v3_params"].read_text(encoding="utf-8"))
    v1p = json.loads(INP["v1_params"].read_text(encoding="utf-8"))
    t, half = v3p["links"]["tool"], float(v1p["reducer_depth_mm"]) / 2
    lay = GP["layout"]
    expect = {"flange_start": half, "flange_end": half + t["flange_t"], "flange_r": float(t["flange_r"]),
              "ring_start": half + t["flange_t"], "ring_end": half + t["flange_t"] + float(lay["recess_depth"]), "ring_r": float(lay["recess_dia"]) / 2}
    ok = all(abs(got[k] - expect[k]) <= 0.01 for k in expect) and got["flange_link"] == 6 and got["ring_link"] == 6
    axis_ok = bool(np.allclose(R6[:, 0], a, atol=1e-9) and abs(np.linalg.det(R6) - 1) < 1e-9)
    return {"measured_from_stl": {k: round(v, 4) if isinstance(v, float) else v for k, v in got.items()}, "expected_from_params": expect,
            "match": ok, "link6_x_is_j6_axis": axis_ok}


def flange_local(arm, J, R6):
    """플랜지 STL 꼭짓점의 링크 6 지역 좌표(x = J6 축 · 원점 J6)."""
    b = next(x for x in arm if x["name"] == "LINK6_TOOL_FLANGE")
    return (b["v"] - J[5][0]) @ R6


def measure_holes(vl, GP, refs, ledger_dia, flange_start, flange_end, min_floor=1.0):
    """검토 MP9-B5: 플랜지 나사 자리를 커밋된 STL 에서 직접 잰다(v3 parameters · 생성기를 안 씀). 플랜지는 회전체라 J6 축에서 반지름
    pcd/2 ± (d/2 + 0.3) · 뒷면에서 0.5 넘게 떨어진 꼭짓점은 구멍 벽(위 · 아래 원)뿐이다 → 각으로 묶어 구멍마다 중심 · 지름 · 바닥을 낸다.
    기대 = 그리퍼 parameters(팔 나사 원 · 각) · 기준 입체의 팔 나사 수(ARM_SHANK) · 원장 insert_hole_dia · 나사 몸통 길이(받침 아랫면 밑)."""
    lay = GP["layout"]
    pcd_r, d_exp = float(lay["arm_screw_pcd"]) / 2, float(ledger_dia)
    n_exp = sum(1 for nm, _s, _g in refs if nm.startswith("ARM_SHANK"))
    shank_below = float(GP["screws"]["arm_m3"]["length"]) - (float(lay["base_top"]) - float(lay["arm_screw_cbore"][1]))
    r = np.linalg.norm(vl[:, 1:], axis=1)
    sel = vl[(np.abs(r - pcd_r) <= d_exp / 2 + 0.3) & (vl[:, 0] >= flange_start + 0.5)]
    ang = np.degrees(np.arctan2(sel[:, 2], sel[:, 1])) % 360.0
    holes = []
    order = np.argsort(ang)                                               # 각이 10° 넘게 벌어지면 다른 구멍(구멍 하나의 각 폭 ≈ 15°)
    groups, cur = [], [order[0]] if len(order) else []
    for i0, i1 in zip(order[:-1], order[1:]):
        if ang[i1] - ang[i0] > 10.0:
            groups.append(cur)
            cur = []
        cur.append(i1)
    if cur:
        groups.append(cur)
    if len(groups) > 1 and (ang[groups[0][0]] + 360.0 - ang[groups[-1][-1]]) <= 10.0:   # 0° 를 걸친 묶음
        groups[0] = groups[-1] + groups[0]
        groups.pop()
    for gi in groups:
        P = sel[gi]
        top = P[np.abs(P[:, 0] - flange_end) <= 0.01]
        c = top[:, 1:].mean(axis=0) if len(top) else P[:, 1:].mean(axis=0)
        rad = np.linalg.norm(top[:, 1:] - c, axis=1) if len(top) else np.array([np.nan])
        holes.append({"angle_deg": round(float(np.degrees(np.arctan2(c[1], c[0])) % 360.0), 4), "pcd_r": round(float(np.linalg.norm(c)), 4),
                      "dia": round(float(2 * rad.mean()), 4), "dia_spread": round(float(2 * (rad.max() - rad.min())), 4),
                      "bottom_x": round(float(P[:, 0].min()), 4), "depth": round(float(flange_end - P[:, 0].min()), 4)})
    holes.sort(key=lambda h: h["angle_deg"])
    want_ang = sorted((float(lay["arm_screw_phase_deg"]) + i * 360.0 / n_exp) % 360.0 for i in range(n_exp)) if n_exp else []
    rows = {"count": len(holes) == n_exp,
            "angles": len(holes) == n_exp and all(min(abs(h["angle_deg"] - w), 360 - abs(h["angle_deg"] - w)) <= 0.2 for h, w in zip(holes, want_ang)),
            "pcd": all(abs(h["pcd_r"] - pcd_r) <= 0.02 for h in holes),
            "dia_ledger": all(abs(h["dia"] - d_exp) <= 0.02 for h in holes),
            "screw_tip_above_bottom": all(h["depth"] > shank_below for h in holes),
            "floor_left": all(h["bottom_x"] - flange_start >= min_floor for h in holes)}
    return {"holes": holes, "expected": {"count": n_exp, "angles_deg": want_ang, "pcd_r": pcd_r, "dia": d_exp, "shank_below_mm": shank_below,
                                         "min_floor_mm": min_floor}, "rows": rows, "ok": bool(holes) and all(rows.values())}


def mount_matrix(face_x, roll_deg, J, R6):
    """G → 세계(표시 자세). 링크 6 지역 좌표(원점 J6 · 축 R6 열)에서 G 원점 = (face_x, 0, 0) · gz = 지역 x · gx = 지역 y 를 x 둘레 roll 만큼 · gy = gz × gx."""
    c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
    Rg = np.column_stack([[0.0, c, s], [0.0, -s, c], [1.0, 0.0, 0.0]])
    M = np.eye(4)
    M[:3, :3] = R6 @ Rg
    M[:3, 3] = J[5][0] + R6 @ np.array([face_x, 0.0, 0.0])
    ML = np.eye(4)
    ML[:3, :3] = Rg
    ML[:3, 3] = [face_x, 0.0, 0.0]
    return M, ML


FACE_BODY = {"flange": "LINK6_TOOL_FLANGE", "ring": "LINK6_TOOL_RING"}


def independent_mount(arm, grip_w0, J, pose_deg, q_list, roll_deg, fingertip_g, M, face):
    """독립 대조: v1 parameters 순기구학(fk_v1)의 J6 원점 · 축 · J5 축으로, 자세마다 돌린 그리퍼 · 붙이는 면 바디의 점을 잰다(kinematics.json 은 pose_points 쪽만 씀)."""
    ring = next(b for b in arm if b["name"] == FACE_BODY[face])
    base = next(g for g in grip_w0 if g["name"] == "BASE")
    pads = [g for g in grip_w0 if g["name"] in ("PAD_A", "PAD_B")]
    tip = to_world(np.asarray([fingertip_g], float), M)
    gx2 = to_world(np.asarray([[0, 0, 0], [1, 0, 0]], float), M)
    rows = []
    for name, q in q_list:
        q = np.asarray(q, float)
        deltas = q - pose_deg
        O, A, _ = fk_v1(q)
        o6, a6 = O[5], A[5] / np.linalg.norm(A[5])
        ring_ax, _ = axial_radial(pose_points(ring["v"], 6, deltas, J), o6, a6)
        base_ax, _ = axial_radial(pose_points(base["v"], 6, deltas, J), o6, a6)
        pad_ax = max(float(axial_radial(pose_points(p["v"], 6, deltas, J), o6, a6)[0].max()) for p in pads)
        t_ax, t_rad = axial_radial(pose_points(tip, 6, deltas, J), o6, a6)
        q0 = q.copy()
        q0[5] = 0.0
        _, A0, _ = fk_v1(q0)
        g2 = pose_points(gx2, 6, q0 - pose_deg, J)
        gx = (g2[1] - g2[0]) / np.linalg.norm(g2[1] - g2[0])
        a5 = A0[4] / np.linalg.norm(A0[4])
        c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
        # roll 의 뜻: q6 = 0 에서 그리퍼 x = J5 축을 J6 축 둘레로 roll 만큼 돌린 것
        a6_0 = A0[5] / np.linalg.norm(A0[5])
        want_gx = c * a5 + s * np.cross(a6_0, a5)
        r = {"pose": name, "face_body": FACE_BODY[face], "face_end_mm": round(float(ring_ax.max()), 6), "base_bottom_mm": round(float(base_ax.min()), 6),
             "pad_tip_mm": round(pad_ax, 6), "grasp_axial_mm": round(float(t_ax[0]), 6), "grasp_off_axis_mm": float(t_rad[0]),
             "gx_dot_want_at_q6_0": round(float(gx @ want_gx), 9)}
        # STL 은 단정밀도라 읽은 점에 1e-5 mm 쯤 반올림이 있다(고리 끝 32.000013) → STL 끼리 견주는 값은 1e-3 mm · 계산만으로 나온 값은 1e-6
        r["ok"] = (abs(r["base_bottom_mm"] - r["face_end_mm"]) <= 1e-3 and abs(r["pad_tip_mm"] - (r["base_bottom_mm"] + 106.0)) <= 1e-3
                   and abs(r["grasp_axial_mm"] - (r["base_bottom_mm"] + fingertip_g[2])) <= 1e-6 and r["grasp_off_axis_mm"] <= 1e-6
                   and r["gx_dot_want_at_q6_0"] >= 1 - 1e-9)
        rows.append(r)
    return rows


FIT_PAIRS = {("BASE", "LINK6_TOOL_RING"): 0.05}
# 설계상 틈 0 인 맞춤(2 단계 — 돌기 Ø20 × 1.5 ↔ 받침 홈 Ø20 × 1.5 · 사용자 수치 공칭 그대로): 두 STL 이 원을 다른 다각형으로 잘라 공칭에서도
# 현 오차만큼 겹친다(0.9 mm³ 쯤). 이 쌍만 팔 쪽 돌기를 J6 축에서 반지름 방향으로 값(mm)만큼 들여 잰 겹침으로 판정하고, 원래 겹침은 fit_pairs 에 적는다.


def inset_radial(v, O, a, d):
    """J6 축(O · a) 둘레로 반지름을 d 만큼 줄인 점(축 위 점은 그대로)."""
    w = v - O
    ax = w @ a
    rv = w - np.outer(ax, a)
    r = np.linalg.norm(rv, axis=1)
    k = np.where(r > d, (r - d) / np.maximum(r, 1e-12), 0.0)
    return O + np.outer(ax, a) + rv * k[:, None]


def mount_contact(arm, grip_w, lim, J):
    """그리퍼(세계 · 표시 자세) ↔ 링크 6 바디 겹친 부피. MP9 2 단계부터 팔 쪽에 나사 자리가 있으므로 팔 나사 몸통(ARM_SHANK_*)도 판정에 넣는다
    (구멍에 들어가면 0 · 구멍이 어긋나면 겹침) — 따로 적은 arm_screw_into_arm 은 그 부분집합(보기 쉽게). 맞춤 쌍(FIT_PAIRS)은 위 설명대로."""
    O6, a6 = J[5]
    l6 = [b for b in arm if b["link"] == 6]
    rows, shank, fits = [], [], []
    for g in grip_w:
        gm, gb = None, (g["v"].min(0), g["v"].max(0))
        for b in l6:
            if not boxes_near(gb, (b["v"].min(0), b["v"].max(0)), 0.01):
                continue
            gm = gm if gm is not None else man(g["v"], g["f"])
            v = vg.vol(gm ^ man(b["v"], b["f"]))
            d = FIT_PAIRS.get((g["name"], b["name"]))
            if d is not None:
                vi = vg.vol(gm ^ man(inset_radial(b["v"], O6, a6, d), b["f"]))
                fits.append({"grip": g["name"], "arm": b["name"], "raw_mm3": round(v, 4), "inset_mm": d, "inset_mm3": round(vi, 4)})
                v = vi
            if v > 1e-6:
                (shank if g["name"].startswith("ARM_SHANK") else rows).append({"grip": g["name"], "arm": b["name"], "mm3": round(v, 4)})
    allr = rows + shank
    mx = max([r["mm3"] for r in allr], default=0.0)
    return {"max_mm3": mx, "ok": mx <= lim, "overlaps": sorted(allr, key=lambda r: -r["mm3"]), "arm_screw_into_arm": shank, "fit_pairs": fits}


# ---------------- B 자세 ----------------
class ArmPose:
    def __init__(self, arm, q, J, pose_deg):
        self.arm, self.J = arm, J
        self.deltas = np.asarray(q, float) - pose_deg
        self.V = [pose_points(b["v"], b["link"], self.deltas, J) for b in arm]
        self.box = [(v.min(0), v.max(0)) for v in self.V]
        self._M, self._T = {}, {}

    def m(self, i):
        if i not in self._M:
            self._M[i] = man(self.V[i], self.arm[i]["f"])
        return self._M[i]

    def tree(self, i):
        if i not in self._T:
            self._T[i] = cKDTree(pose_points(self.arm[i]["s"], self.arm[i]["link"], self.deltas, self.J))
        return self._T[i]


def floor_ok(GV, clear):
    z = min(float(v[:, 2].min()) for v in GV)
    return z >= clear, round(z, 3)


def grip_vs_arm(ap, grip_w, grip_s, lim, near_box):
    """그리퍼(세계 · 표시 자세 · 링크 6 과 함께 돎) ↔ 링크 0 ~ 5 바디: 겹친 부피 · 가장 가까운 틈(표본점 근사).
    틈은 상자가 near_box 안인 바디만 재고, near_box 보다 큰 값은 참 최소가 아닐 수 있어 「넘음」(None)으로 둔다(검토 MP9-R4)."""
    GV = [pose_points(g["v"], 6, ap.deltas, ap.J) for g in grip_w]
    hits = []
    gap = {"l5": [math.inf, None], "l0_4": [math.inf, None]}      # 링크 5(J6 고정자 · J5 만 움직이면 상대 위치 같음) · 링크 0 ~ 4
    for gi, g in enumerate(grip_w):
        gb = (GV[gi].min(0), GV[gi].max(0))
        gm, gs = None, None
        for ai, b in enumerate(ap.arm):
            if b["link"] > 5 or not boxes_near(gb, ap.box[ai], near_box):
                continue
            if boxes_near(gb, ap.box[ai], 0.01):
                gm = gm if gm is not None else man(GV[gi], g["f"])
                v = vg.vol(gm ^ ap.m(ai))
                if v > 1e-6:
                    hits.append({"grip": g["name"], "arm": b["name"], "link": b["link"], "mm3": round(v, 4)})
            gs = gs if gs is not None else pose_points(grip_s[gi], 6, ap.deltas, ap.J)
            d = float(ap.tree(ai).query(gs, k=1)[0].min())
            k = "l5" if b["link"] == 5 else "l0_4"
            if d < gap[k][0]:
                gap[k] = [d, [g["name"], b["name"]]]
    big = [h for h in hits if h["mm3"] > lim]
    out = {"hit": bool(big), "max_mm3": max([h["mm3"] for h in hits], default=0.0), "hits": sorted(big, key=lambda h: -h["mm3"])[:8]}
    for k in ("l0_4", "l5"):
        d, pair = gap[k]
        out[f"gap_{k}_approx_mm"] = None if d > near_box else round(d, 2)
        out[f"gap_{k}_pair"] = None if d > near_box else pair
    return out, GV


def arm_self(ap, lim, split=None):
    """팔 바디끼리(다른 링크) 겹친 부피. split = k 면 링크 < k 와 ≥ k 사이 쌍만(관절 k 쓸기)."""
    hits = []
    n = len(ap.arm)
    for i in range(n):
        for k in range(i + 1, n):
            li, lk = ap.arm[i]["link"], ap.arm[k]["link"]
            if li == lk or (split is not None and (min(li, lk) >= split or max(li, lk) < split)):
                continue
            if not boxes_near(ap.box[i], ap.box[k], 0.01):
                continue
            v = vg.vol(ap.m(i) ^ ap.m(k))
            if v > lim:
                hits.append({"a": ap.arm[i]["name"], "b": ap.arm[k]["name"], "links": [li, lk], "mm3": round(v, 4)})
    return sorted(hits, key=lambda h: -h["mm3"])


def free_interval(grid, base, bad):
    i0 = grid.index(base)
    if bad[i0]:
        return {"free": None, "base_blocked": True}
    lo, hi = i0, i0
    while lo > 0 and not bad[lo - 1]:
        lo -= 1
    while hi < len(grid) - 1 and not bad[hi + 1]:
        hi += 1
    return {"free": [grid[lo], grid[hi]], "first_blocked_below": grid[lo - 1] if lo > 0 else None,
            "first_blocked_above": grid[hi + 1] if hi < len(grid) - 1 else None}


def shift_to(ap, grip_w, target):
    """자세 ap 에서 그리퍼 G 원점이 target(세계 · 자세)에 오도록 표시 자세 점을 평행 이동한 사본 — 대조 C5 용."""
    g0 = next(g for g in grip_w if g["name"] == "BASE")
    o = np.asarray([[0.0, 0.0, 0.0]])
    P = np.vstack([o, np.eye(3)]) + g0["v"].mean(0)        # 아무 점 넷(평행 이동의 회전 부분을 얻으려고)
    Q = pose_points(P, 6, ap.deltas, ap.J)
    R = (Q[1:] - Q[0]).T                                   # 열 = 표시 자세 단위 벡터가 간 곳
    origin_disp = np.asarray(grip_w[0]["origin_disp"], float)
    origin_pose = pose_points(origin_disp[None, :], 6, ap.deltas, ap.J)[0]
    d = R.T @ (np.asarray(target, float) - origin_pose)
    return [{**g, "v": g["v"] + d} for g in grip_w]


# ---------------- 보기 GLB ----------------
def hex_rgba(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)] + [255]


def grip_color(name):
    if name in GRIP_COLORS:
        return GRIP_COLORS[name]
    return ROD_COLOR if name.startswith("ROD_") else SCREW_COLOR


def glb_bytes(arm, grip_w):
    """표시 자세 · m · Y 위(glTF) — (x, y, z) mm → 0.001 (x, z, −y)."""
    scene = trimesh.Scene()
    C = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float) * 0.001
    for name, v, f, col in [(b["name"], b["v"], b["f"], b["color"]) for b in arm] + [(f"KG1_{g['name']}", g["v"], g["f"], grip_color(g["name"])) for g in grip_w]:
        m = trimesh.Trimesh(vertices=v @ C.T, faces=f, process=False)
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=name, baseColorFactor=hex_rgba(col), metallicFactor=0.0, roughnessFactor=0.55))
        scene.add_geometry(m, node_name=name, geom_name=name)
    return scene.export(file_type="glb")


# ---------------- 실행 ----------------
def run(quick=False):
    t0 = time.time()
    C = PRM["checks"]
    spacing, near_box = float(C["sample_spacing_mm"]), float(C["near_box_mm"])
    arm = load_arm(spacing)
    J, pose_deg, R6 = load_kin()
    GP, parts, mans, refs = load_gripper()
    gcfg, mcfg = PRM["gripper"], PRM["mount"]
    padset = gcfg["padset"]
    us_check = sorted(set(map(float, gcfg["openings_u"])) | {float(gcfg["render_u"])})
    out = {"what": "MP9 외장 v3 + 그리퍼 KG1 조립 검사(커밋된 STL 로 스스로 계산 · 계획 051)", "checks": {}, "controls": {}, "numbers": {},
           "openings_checked_u": us_check}
    CK, CT, N = out["checks"], out["controls"], out["numbers"]

    # 입력 출처
    v3m = INP["v3_model"]
    inputs = {"v3 bodies.json": sha(v3m / "bodies.json"),
              "v3 meshes (이름순 sha 의 sha)": hashlib.sha256("".join(sha(v3m / "meshes" / f"{b['name']}.stl") for b in sorted(arm, key=lambda b: b["name"])).encode()).hexdigest(),
              "v1 kinematics.json": sha(INP["v1_kinematics"]), "v1 parameters.json": sha(INP["v1_params"]), "v3 parameters.json": sha(INP["v3_params"]),
              "gallery_poses.json": sha(INP["gallery_poses"]), "gripper parameters.json": sha(INP["gripper_src"] / "parameters.json"),
              "verify_gripper.py": sha(INP["gripper_src"] / "verify_gripper.py"),
              "print-fits.json": sha((INP["gripper_src"] / GP["fits_from"]["ledger"]).resolve()),
              **{f"gripper parts/{nm}.stl": sha(INP["gripper_model"] / "parts" / f"{nm}.stl") for nm in GRIP_PARTS},
              "assemble.py": sha(Path(__file__)), "parameters.json (MP9)": sha(PRM_PATH)}
    out["inputs_sha256"] = inputs

    # manifold = 메시 · 부피 > 0
    mrows = {}
    for b in arm:
        mrows[f"arm/{b['name']}"] = manifold_matches(b["v"], b["f"])
    for nm, p in parts.items():
        mrows[f"gripper/{nm}"] = manifold_matches(p["v"], p["f"])
    for g in gripper_items(GP, mans, refs, 0.0, padset):
        if not g["printed"]:
            mrows[f"gripper-ref/{g['name']}"] = manifold_matches(g["v"], g["f"])
    N["manifold_vs_mesh"] = {k: {"ok": r[0], "mesh_mm3": r[1], "manifold_mm3": r[2], "status": r[3]} for k, r in mrows.items()}
    CK["A_all_manifold_equal_mesh_positive"] = all(r[0] for r in mrows.values()) and len(mrows) == len(arm) + len(GRIP_PARTS) + len(refs)

    # 맞춤면 · 붙인 자리
    itf = measure_interface(arm, J, R6, GP)
    N["interface"] = itf
    CK["A_interface_measured_equals_params"] = itf["match"]
    led = json.loads((INP["gripper_src"] / GP["fits_from"]["ledger"]).resolve().read_text(encoding="utf-8"))
    ledger_dia = float(led["materials"][GP["fits_from"]["material"]]["values"]["insert_hole_dia"]["value"])
    vl = flange_local(arm, J, R6)
    fs, fe = itf["measured_from_stl"]["flange_start"], itf["measured_from_stl"]["flange_end"]
    th = measure_holes(vl, GP, refs, ledger_dia, fs, fe)
    N["tool_holes"] = th
    CK["A_tool_holes_match_gripper_and_ledger"] = th["ok"]
    CK["A_link6_x_is_j6_axis"] = itf["link6_x_is_j6_axis"]
    face_x = itf["measured_from_stl"][f"{mcfg['face']}_end"]
    roll = float(mcfg["roll_deg"])
    M, ML = mount_matrix(face_x, roll, J, R6)
    CK["A_mount_rotation_proper"] = bool(np.allclose(M[:3, :3].T @ M[:3, :3], np.eye(3), atol=1e-9) and abs(np.linalg.det(M[:3, :3]) - 1) < 1e-9)
    tip_w = to_world(np.asarray([gcfg["fingertip_g"]], float), M)[0]
    N["fingertip"] = {"world_display_mm": tip_w.round(4).tolist(), "g_mm": gcfg["fingertip_g"]}

    G = {u: gripper_items(GP, mans, refs, u, padset) for u in us_check}
    org = to_world(np.zeros((1, 3)), M)[0].tolist()
    GW = {u: [{**g, "v": to_world(g["v"], M), "origin_disp": org} for g in items] for u, items in G.items()}
    GS = {u: [samples(g["v"], g["f"], spacing, 50 + i) for i, g in enumerate(items)] for u, items in GW.items()}

    poses = json.loads(INP["gallery_poses"].read_text(encoding="utf-8"))["poses"]
    qmap = {p["name"]: list(map(float, p["q_deg"])) for p in poses}
    # 독립 순기구학 대조 — 표시 자세 + 갤러리 자세 + 표시 자세에서 J5 · J6 만 바꾼 둘
    fk_poses = [(n, q) for n, q in qmap.items()] + [("display_j5_m60_j6_90", [15, -50, 70, 15, -60, 90]), ("display_j6_m135", [15, -50, 70, 15, 25, -135])]
    fk = independent_mount(arm, GW[0.0], J, pose_deg, fk_poses, roll, gcfg["fingertip_g"], M, mcfg["face"])
    O_fk, _A, Rc_fk = fk_v1(pose_deg)
    kin_err = max(max(float(np.abs(O_fk[k] - J[k][0]).max()) for k in range(6)), float(np.abs(Rc_fk[5] - R6).max()))
    N["independent_fk"] = {"kinematics_json_vs_v1_params_max_err": kin_err, "poses": fk}
    CK["A_independent_fk_mount_and_roll"] = kin_err <= 1e-9 and all(r["ok"] for r in fk) and len(fk) == len(fk_poses)

    lim = float(C["grip_hit_mm3"])
    mc = mount_contact(arm, GW[0.0], lim, J)
    out["mount_contact"] = mc
    CK["A_mount_face_contact_only"] = mc["ok"]
    N["mount_gap_flange_to_base_mm"] = round(face_x - itf["measured_from_stl"]["flange_end"], 4)

    # 양성 대조
    Mi, _ = mount_matrix(face_x - 1.0, roll, J, R6)                      # 2 단계: 붙이는 면에서 1 mm 안으로 → 받침이 플랜지에 박힘
    c1 = mount_contact(arm, [{**g, "v": to_world(g["v"], Mi)} for g in G[0.0]], lim, J)
    CT["C1_mounted_1mm_inside_overlaps"] = {"max_mm3": c1["max_mm3"], "top": c1["overlaps"][:3], "ok": c1["max_mm3"] > CONTROL_MIN_MM3 and not c1["ok"]}
    Ms, _ = mount_matrix(face_x - 60.0, roll, J, R6)
    ap_disp = ArmPose(arm, pose_deg, J, pose_deg)
    gw_s = [{**g, "v": to_world(g["v"], Ms)} for g in G[0.0]]
    c2, _ = grip_vs_arm(ap_disp, gw_s, [samples(g["v"], g["f"], 6.0, 7) for g in gw_s], lim, near_box)
    CT["C2_pushed_60_into_arm_hits"] = {"max_mm3": c2["max_mm3"], "top": c2["hits"][:3], "ok": c2["hit"] and c2["max_mm3"] > CONTROL_MIN_MM3}
    bp = parts["BASE"]
    c3 = manifold_matches(bp["v"], bp["f"][10:])
    c3b = manifold_matches(bp["v"], bp["f"][:, ::-1])
    CT["C3_open_or_inverted_mesh_fails_manifold_key"] = {"open": {"mesh_mm3": c3[1], "manifold_mm3": c3[2]}, "inverted": {"mesh_mm3": c3b[1], "manifold_mm3": c3b[2]},
                                                         "ok": c3[0] is False and c3b[0] is False}
    c4 = floor_ok([g["v"] - np.array([0, 0, 1000.0]) for g in GW[0.0]], float(C["floor_clear_mm"]))
    CT["C4_below_floor_fails_floor_key"] = {"min_z": c4[1], "ok": c4[0] is False}
    ap_home = ArmPose(arm, qmap["home"], J, pose_deg)
    O_home, _, _ = fk_v1(np.asarray(qmap["home"], float))
    gw5 = shift_to(ap_home, GW[0.0], O_home[2])
    c5, _ = grip_vs_arm(ap_home, gw5, [samples(g["v"], g["f"], 6.0, 9) for g in gw5], lim, near_box)
    low = [h for h in c5["hits"] if h["link"] <= 4]
    CT["C5_home_moved_to_elbow_hits_links_0_4"] = {"max_mm3": c5["max_mm3"], "top": low[:3], "ok": bool(low) and low[0]["mm3"] > CONTROL_MIN_MM3}
    q_fold = list(qmap["home"])
    q_fold[4] = 180.0
    c6 = arm_self(ArmPose(arm, q_fold, J, pose_deg), float(C["arm_self_hit_mm3"]), split=5)
    CT["C6_j5_folded_180_arm_self_hits"] = {"top": c6[:2], "ok": bool(c6) and c6[0]["mm3"] > CONTROL_MIN_MM3}
    g_ = [0, 5, 10, 15, 20]
    c7 = [free_interval(g_, 10, [True, False, False, False, True]), free_interval(g_, 10, [False, False, True, False, False]),
          free_interval(g_, 0, [False] * 5)]
    CT["C7_free_interval_synthetic"] = {"got": c7, "ok": c7[0]["free"] == [5, 15] and c7[0]["first_blocked_below"] == 0 and c7[0]["first_blocked_above"] == 20
                                        and c7[1]["free"] is None and c7[2]["free"] == [0, 20] and c7[2]["first_blocked_above"] is None}
    M90, _ = mount_matrix(face_x, roll + 90.0, J, R6)
    c8a = independent_mount(arm, [{**g, "v": to_world(g["v"], M90)} for g in G[0.0]], J, pose_deg, fk_poses[:2], roll, gcfg["fingertip_g"], M90, mcfg["face"])
    Mb, _ = mount_matrix(face_x + float(GP["layout"]["recess_depth"]), roll, J, R6)   # 2 단계: 돌기 끝면에 얹음(홈에 안 들어감) → 받침 아랫면 ≠ 붙이는 면
    c8b = independent_mount(arm, [{**g, "v": to_world(g["v"], Mb)} for g in G[0.0]], J, pose_deg, fk_poses[:2], roll, gcfg["fingertip_g"], Mb, mcfg["face"])
    CT["C8_independent_fk_catches_roll_and_face"] = {"roll_plus_90_gx_dot": [r["gx_dot_want_at_q6_0"] for r in c8a],
                                                     "on_boss_top_base_bottom": [r["base_bottom_mm"] for r in c8b],
                                                     "ok": not any(r["ok"] for r in c8a) and not any(r["ok"] for r in c8b)}
    M45, _ = mount_matrix(face_x, roll + 45.0, J, R6)                    # 2 단계: 돌림 45° → 팔 나사가 플랜지 구멍을 벗어나 박힘
    c9 = mount_contact(arm, [{**g, "v": to_world(g["v"], M45)} for g in G[0.0]], lim, J)
    CT["C9_roll_45_screws_miss_holes"] = {"max_mm3": c9["max_mm3"], "shank_top": c9["arm_screw_into_arm"][:2],
                                          "ok": bool(c9["arm_screw_into_arm"]) and max(r["mm3"] for r in c9["arm_screw_into_arm"]) > CONTROL_MIN_MM3}
    sh = R6[:, 1] * 0.5                                                     # 2 단계: 그리퍼를 축에 수직으로 0.5 mm 밀면 돌기가 홈 벽에 박힘(맞춤 쌍도 잡히는지)
    c10 = mount_contact(arm, [{**g, "v": to_world(g["v"], M) + sh} for g in G[0.0]], lim, J)
    CT["C10_shift_0_5_boss_hits_recess_wall"] = {"max_mm3": c10["max_mm3"], "fit_pairs": c10["fit_pairs"], "top": c10["overlaps"][:2],
                                                "ok": any(r["inset_mm3"] > 10 * lim for r in c10["fit_pairs"]) and not c10["ok"]}
    # C11(검토 MP9-B5): 구멍 재기가 잘못을 잡는지 — 구멍 벽 꼭짓점을 20° 돌림 · 구멍 하나 지움 · 바닥을 2 mm 올림(나사 끝이 바닥에 닿음)
    rr = np.linalg.norm(vl[:, 1:], axis=1)
    band = (np.abs(rr - float(GP["layout"]["arm_screw_pcd"]) / 2) <= ledger_dia / 2 + 0.3) & (vl[:, 0] >= fs + 0.5)
    v_rot = vl.copy()
    cs, sn = math.cos(math.radians(20)), math.sin(math.radians(20))
    v_rot[band, 1], v_rot[band, 2] = vl[band, 1] * cs - vl[band, 2] * sn, vl[band, 1] * sn + vl[band, 2] * cs
    a_ = np.degrees(np.arctan2(vl[:, 2], vl[:, 1])) % 360.0
    v_drop = vl[~(band & ((a_ < 10) | (a_ > 350)))]
    v_shal = vl.copy()
    v_shal[band & (vl[:, 0] < fe - 0.01), 0] += 2.0
    c11 = {k: measure_holes(v, GP, refs, ledger_dia, fs, fe) for k, v in (("rotated_20", v_rot), ("one_dropped", v_drop), ("bottom_up_2", v_shal))}
    CT["C11_hole_measure_catches_angle_count_depth"] = {k: {"ok": v["ok"], "false_rows": [r for r, x in v["rows"].items() if not x]} for k, v in c11.items()}
    CT["C11_hole_measure_catches_angle_count_depth"]["ok"] = (not c11["rotated_20"]["rows"]["angles"] and not c11["one_dropped"]["rows"]["count"]
                                                              and not c11["bottom_up_2"]["rows"]["screw_tip_above_bottom"])
    CK["controls_all_as_expected"] = all(v["ok"] for v in CT.values())

    # 갤러리 자세
    gal = []
    for pz in poses:
        ap = ArmPose(arm, pz["q_deg"], J, pose_deg)
        self_hits = arm_self(ap, float(C["arm_self_hit_mm3"]))
        for u in us_check:
            r, GV = grip_vs_arm(ap, GW[u], GS[u], lim, near_box)
            fok, fz = floor_ok(GV, float(C["floor_clear_mm"]))
            gap04 = r["gap_l0_4_approx_mm"]
            gal.append({"pose": pz["name"], "label": pz.get("label"), "q_deg": pz["q_deg"], "u": u, **r, "floor_ok": fok, "grip_min_z_mm": fz,
                        "close_l0_4": gap04 is not None and gap04 < float(C["near_mm"]),
                        "arm_self_hits": self_hits[:5], "free": (not r["hit"]) and fok and not self_hits})
        print(f"pose {pz['name']:<11} " + " · ".join(f"u{g['u']:g} hit={g['hit']} max={g['max_mm3']:.3f} gap04={g['gap_l0_4_approx_mm']} floor_z={g['grip_min_z_mm']}"
                                                    for g in gal[-len(us_check):]), flush=True)
    out["gallery"] = gal
    # 검토 MP9-B1: 붙인 그 자세(표시)에서 그리퍼가 팔(링크 0 ~ 5 — J6 드럼 포함)에 박히면 붙이기 자체가 틀린 것 → 기록이 아니라 판정
    disp = [g for g in gal if g["pose"] == "display"]
    CK["A_display_pose_gripper_free_of_arm"] = len(disp) == len(us_check) and not any(g["hit"] for g in disp)

    if not quick:
        # J5 쓸기
        sw = C["j5_sweep"]
        grid = list(range(sw["from"], sw["to"] + 1, sw["step"]))
        j5 = {}
        for bname in sw["bases"]:
            q0 = list(qmap[bname])
            rows = []
            for q5 in grid:
                q = q0.copy()
                q[4] = float(q5)
                ap = ArmPose(arm, q, J, pose_deg)
                arm_hits = arm_self(ap, float(C["arm_self_hit_mm3"]), split=5)
                row = {"q5": q5, "arm_self_hit": bool(arm_hits), "arm_self_top": arm_hits[:2]}
                for u in gcfg["openings_u"]:
                    r, GV = grip_vs_arm(ap, GW[float(u)], GS[float(u)], lim, near_box)
                    fok, fz = floor_ok(GV, float(C["floor_clear_mm"]))
                    row[f"u{u:g}"] = {"hit": r["hit"], "max_mm3": r["max_mm3"], "top": r["hits"][:2], "gap_l0_4_approx_mm": r["gap_l0_4_approx_mm"],
                                      "gap_l0_4_pair": r["gap_l0_4_pair"], "floor_ok": fok, "grip_min_z_mm": fz}
                rows.append(row)
            base5 = int(round(q0[4]))
            summ = {"q_base": q0, "step_deg": sw["step"], "arm_only": free_interval(grid, base5, [r["arm_self_hit"] for r in rows])}
            for u in gcfg["openings_u"]:
                k = f"u{u:g}"
                summ[f"with_gripper_{k}"] = free_interval(grid, base5, [r["arm_self_hit"] or r[k]["hit"] for r in rows])
                summ[f"with_gripper_{k}_and_floor"] = free_interval(grid, base5, [r["arm_self_hit"] or r[k]["hit"] or not r[k]["floor_ok"] for r in rows])
                hit_q = [r["q5"] for r in rows if r[k]["hit"]]
                summ[f"gripper_first_hit_{k}"] = {"plus": min([q for q in hit_q if q > base5], default=None),
                                                  "minus": max([q for q in hit_q if q < base5], default=None)}
            j5[bname] = {"summary": summ, "rows": rows}
            print(f"J5 sweep {bname}: " + json.dumps({k: v.get("free") if isinstance(v, dict) and "free" in v else v
                                                       for k, v in summ.items() if k not in ("q_base", "step_deg")}, ensure_ascii=False), flush=True)
        out["j5_sweep"] = j5

        # J6 쓸기 — 팔 겹침과 바닥 여유를 따로(검토 MP9-R1)
        s6 = C["j6_sweep"]
        q0 = list(qmap[s6["base"]])
        rows = []
        for q6 in range(s6["from"], s6["to"] + 1, s6["step"]):
            q = q0.copy()
            q[5] = float(q6)
            ap = ArmPose(arm, q, J, pose_deg)
            row = {"q6": q6}
            for u in gcfg["openings_u"]:
                r, GV = grip_vs_arm(ap, GW[float(u)], GS[float(u)], lim, near_box)
                fok, fz = floor_ok(GV, float(C["floor_clear_mm"]))
                row[f"u{u:g}"] = {"hit": r["hit"], "max_mm3": r["max_mm3"], "top": r["hits"][:2], "gap_l5_approx_mm": r["gap_l5_approx_mm"],
                                  "gap_l5_pair": r["gap_l5_pair"], "gap_l0_4_approx_mm": r["gap_l0_4_approx_mm"], "floor_ok": fok, "grip_min_z_mm": fz}
            rows.append(row)
        summ6 = {"base": s6["base"], "step_deg": s6["step"], "arm_hit_q6": {}, "floor_short_q6": {}, "min_z_mm": {}}
        for u in gcfg["openings_u"]:
            k = f"u{u:g}"
            summ6["arm_hit_q6"][k] = [r["q6"] for r in rows if r[k]["hit"]]
            summ6["floor_short_q6"][k] = [r["q6"] for r in rows if not r[k]["floor_ok"]]
            mz = min(rows, key=lambda r: r[k]["grip_min_z_mm"])
            summ6["min_z_mm"][k] = {"q6": mz["q6"], "z": mz[k]["grip_min_z_mm"]}
        out["j6_sweep"] = {"summary": summ6, "rows": rows}
        print("J6 sweep", json.dumps(summ6, ensure_ascii=False), flush=True)

    out["all_ok"] = all(CK.values())
    out["seconds"] = round(time.time() - t0, 1)
    asm = {"what": "그리퍼 KG1 을 외장 v3 링크 6 에 붙인 자리(계획 051) — 좌표 G(그리퍼) → 세계(표시 자세 · v1 kinematics) · mm",
           "mount": {"face": mcfg["face"], "face_axial_mm": face_x, "roll_deg": roll,
                     "g_to_world_display": M.round(9).tolist(), "g_to_link6_local": ML.round(9).tolist(),
                     "link6_local": "원점 = J6 원점 · 축 = v1 kinematics J6 R_child 열(지역 x = J6 축) · 표시 자세", "j6_origin_mm": J[5][0].tolist(),
                     "j6_axis_world": J[5][1].tolist()},
           "interface": itf, "mount_gap_flange_to_base_mm": N["mount_gap_flange_to_base_mm"],
           "grasp_point": {"g_mm": gcfg["fingertip_g"], "world_display_mm": N["fingertip"]["world_display_mm"],
                           "axial_from_j6_mm": face_x + gcfg["fingertip_g"][2], "note": "J6 축 위 — 독립 순기구학 대조(check.json numbers.independent_fk)"},
           "arm_screw_into_arm": mc["arm_screw_into_arm"], "inputs_sha256": inputs}
    mp = INP["gripper_model"] / "mass-properties.json"
    if mp.is_file():
        mpj = json.loads(mp.read_text(encoding="utf-8"))
        asm["gripper_mass"] = {"total_mass_g": mpj["total_mass_g"], "com_g_mm": mpj["com_mm"],
                               "com_link6_local_mm": to_world(np.asarray([mpj["com_mm"]], float), ML)[0].round(4).tolist(),
                               "com_world_display_mm": to_world(np.asarray([mpj["com_mm"]], float), M)[0].round(4).tolist(),
                               "source": "models/kmjh-gripper-v1/mass-properties.json", "source_sha256": sha(mp)}
    return out, asm, arm, GW


def gap_txt(d, pair, near_box):
    return f"{near_box:g} 넘음" if d is None else f"{d} ({' ↔ '.join(pair or [])})"


def summary_md(out, asm):
    nb = PRM["checks"]["near_box_mm"]
    L = ["# 외장 v3 + 그리퍼 KG1 조립 검사 요약 (assemble.py 가 씀 · 원본 = check.json)", ""]
    m = asm["mount"]
    L.append(f"- 붙인 면 = `{m['face']}` (J6 원점에서 축 방향 {m['face_axial_mm']:.2f} mm) · 돌림 {m['roll_deg']}° · 플랜지 면 ↔ 받침 아랫면 틈 {asm['mount_gap_flange_to_base_mm']} mm")
    L.append(f"- 검사 장치 all_ok = **{out['all_ok']}** · " + " · ".join(f"{k} {v}" for k, v in out["checks"].items()))
    L.append("- 양성 대조: " + " · ".join(f"{k} {v['ok']}" for k, v in out["controls"].items()))
    sh = asm["arm_screw_into_arm"]
    L.append(f"- 팔 나사 몸통 ↔ 링크 6(2 단계부터 플랜지 인서트 구멍에 들어가야 0): {len(sh)} 쌍 · 최대 {max([s['mm3'] for s in sh], default=0)} mm³")
    for fp in out["mount_contact"].get("fit_pairs", []):
        L.append(f"- 맞춤 쌍(설계상 틈 0) {fp['grip']} ↔ {fp['arm']}: 원래 겹침 {fp['raw_mm3']} mm³(두 STL 의 원 다각형 차) · 돌기를 반지름 {fp['inset_mm']} mm 들여 잰 겹침 {fp['inset_mm3']} mm³(판정에 씀)")
    L += ["", f"## 갤러리 자세 (벌림 u = {', '.join(f'{u:g}' for u in out['openings_checked_u'])} · 손끝 사이 = 2u)", "",
          "| 자세 | u | 팔과 겹침 | 최대 mm³ | 링크 0 ~ 4 와 가장 가까운 틈(근사) | 링크 5 와 틈(근사) | 그리퍼 최저 z(바닥 0) | 팔끼리 겹침 |",
          "|---|---|---|---|---|---|---|---|"]
    for g in out["gallery"]:
        top = g["hits"][0]["grip"] + " ↔ " + g["hits"][0]["arm"] if g["hits"] else "—"
        L.append(f"| {g['pose']} | {g['u']:g} | {top if g['hit'] else '없음'} | {g['max_mm3']} | {gap_txt(g['gap_l0_4_approx_mm'], g['gap_l0_4_pair'], nb)} | "
                 f"{gap_txt(g['gap_l5_approx_mm'], g['gap_l5_pair'], nb)} | {g['grip_min_z_mm']}{'' if g['floor_ok'] else ' ⚠ 바닥 여유 미달'} | "
                 f"{len(g['arm_self_hits']) or '없음'} |")
    if "j5_sweep" in out:
        sw = PRM["checks"]["j5_sweep"]
        L += ["", f"## J5 쓸기 — 닿지 않는 구간(도 · {sw['from']} ~ {sw['to']} · {sw['step']}° 간격 · 기준 자세의 J5 를 포함하는 구간 · 경계는 ±{sw['step']}° 정밀도)", "",
              "| 기준 자세 | 팔만 | 그리퍼 닫힘 | 그리퍼 끝 벌림 | 닫힘 + 바닥 | 끝 벌림 + 바닥 | 그리퍼가 처음 팔에 닿는 각(닫힘 · 끝 벌림 · + / −) |", "|---|---|---|---|---|---|---|"]
        for b, v in out["j5_sweep"].items():
            s = v["summary"]
            us = [f"u{u:g}" for u in PRM["gripper"]["openings_u"]]
            first = " · ".join(f"{s[f'gripper_first_hit_{k}']['plus']} / {s[f'gripper_first_hit_{k}']['minus']}" for k in us)
            L.append(f"| {b} (J5 = {s['q_base'][4]:g}) | {s['arm_only'].get('free')} | " + " | ".join(str(s[f'with_gripper_{k}'].get("free")) for k in us) + " | "
                     + " | ".join(str(s[f'with_gripper_{k}_and_floor'].get("free")) for k in us) + f" | {first} |")
    if "j6_sweep" in out:
        s6 = out["j6_sweep"]["summary"]
        L += ["", f"## J6 쓸기 ({s6['base']} 자세 · {s6['step_deg']}° 간격 한 바퀴)", ""]
        for k in s6["arm_hit_q6"]:
            L.append(f"- {k}: 팔에 닿는 q6 = {s6['arm_hit_q6'][k] or '없음'} · 바닥 여유 미달 q6 = {s6['floor_short_q6'][k] or '없음'} · "
                     f"그리퍼 최저 z = {s6['min_z_mm'][k]['z']} mm (q6 = {s6['min_z_mm'][k]['q6']})")
    L += ["", f"가장 가까운 틈은 표면 표본점(약 {PRM['checks']['sample_spacing_mm']} mm 간격) 사이 거리라 실제 틈보다 조금 클 수 있다 · 상자가 {nb:g} mm 안인 바디만 재므로 "
          f"그보다 먼 것은 「넘음」. 겹침은 manifold 불리언으로 잰 부피다. 자세 사이 경로는 보지 않는다."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "models" / NAME)
    ap.add_argument("--scratch-root", type=Path)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if not a.quick:
        mguard.checked_dir(a.out, ROOT, a.scratch_root)           # 쓰기 자리를 먼저 본다(계산 전에 멈추게)
    out, asm, arm, GW = run(quick=a.quick)
    print("CHECKS", json.dumps(out["checks"], ensure_ascii=False))
    print("CONTROLS", json.dumps({k: v["ok"] for k, v in out["controls"].items()}))
    if a.quick:
        print("QUICK — 산출 폴더에 쓰지 않음 · all_ok", out["all_ok"])
        return
    od = mguard.checked_dir(a.out, ROOT, a.scratch_root)
    od.mkdir(parents=True, exist_ok=True)
    mguard.write_bytes(od / "check.json", (json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n").encode("utf-8"), ROOT, a.scratch_root)
    mguard.write_bytes(od / "assembly.json", (json.dumps(asm, ensure_ascii=False, indent=1, default=float) + "\n").encode("utf-8"), ROOT, a.scratch_root)
    mguard.write_bytes(od / "check.md", summary_md(out, asm).encode("utf-8"), ROOT, a.scratch_root)
    ru = float(PRM["gripper"]["render_u"])
    mguard.write_bytes(od / f"{NAME}-display.glb", glb_bytes(arm, GW[ru]), ROOT, a.scratch_root)
    print("ASSEMBLY", "OK" if out["all_ok"] else "FAILED", f"{out['seconds']} s")


if __name__ == "__main__":
    main()
