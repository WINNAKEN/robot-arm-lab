# -*- coding: utf-8 -*-
"""MP7 동작 영상의 관절각 경로 — 파이썬 표준만 씀(블렌더 · printforge 가상환경 둘 다에서 같은 값).

motion_plan.json + gallery_poses.json → 시각 t(초)마다 관절각 q(도 · 기하 영점 기준).
이동 = 관절 공간 선형 보간에 부드러운 시간 함수 s = 3u² − 2u³(출발 · 도착 속도 0) · 모든 관절이 같이 출발 · 도착."""
from __future__ import annotations

import json
from pathlib import Path

# 경로 검사 · 렌더 · 묶기가 함께 쓰는 값(한 곳에만 — 검토 R3-PC-3: 두 파일에 따로 두면 어긋날 수 있다)
MIN_PER_FRAME = 8                   # path_check 샘플 밀도 하한 — 2026-10-27 8 배에서 샘플 사이 꼭짓점 이동 4.54 mm
MAX_STEP_MM = 5.0                   # 샘플 사이 꼭짓점 이동 상한
CANON_SETTINGS = {"size": [1280, 720], "samples": 32, "quality": 90}        # 저장소에 올리는 영상의 렌더 설정(README 「동작 영상」)


def load(plan_path, poses_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    poses = {p["name"]: [float(x) for x in p["q_deg"]] for p in json.loads(Path(poses_path).read_text(encoding="utf-8"))["poses"]}
    return plan, poses


def segments(plan, poses):
    """[(t0, t1, q_from, q_to, kind)] — kind = 'hold' | 'move'. 이어진 구간 · 빈틈 없음."""
    m = plan["motion"]
    out, t, cur = [], 0.0, poses[m["start"]]
    if m.get("hold_start_s", 0) > 0:
        out.append((t, t + m["hold_start_s"], cur, cur, "hold"))
        t += m["hold_start_s"]
    for st in m["steps"]:
        nxt = poses[st["to"]]
        out.append((t, t + st["move_s"], cur, nxt, "move"))
        t += st["move_s"]
        if st.get("hold_s", 0) > 0:
            out.append((t, t + st["hold_s"], nxt, nxt, "hold"))
            t += st["hold_s"]
        cur = nxt
    return out


def duration(plan, poses):
    return segments(plan, poses)[-1][1]


def q_at(plan, poses, t):
    segs = segments(plan, poses)
    for t0, t1, a, b, _k in segs:
        if t <= t1 + 1e-12:
            u = 0.0 if t1 <= t0 else min(1.0, max(0.0, (t - t0) / (t1 - t0)))
            s = u * u * (3.0 - 2.0 * u)
            return [x + (y - x) * s for x, y in zip(a, b)]
    return list(segs[-1][3])


def motion_frames(plan, poses):
    """프레임 번호 0 … N−1 의 시각 = f / fps · N = round(길이 × fps) + 1(마지막 자세 포함)."""
    fps = plan["fps"]
    n = int(round(duration(plan, poses) * fps)) + 1
    return [(f, f / fps, q_at(plan, poses, f / fps)) for f in range(n)]


def path_samples(plan, poses, per_frame=2):
    """겹침 검사용 시각 — 이동 구간은 프레임의 per_frame 배로 촘촘히(끝점 포함) · 머무는 구간은 시작점만(자세가 같음)."""
    fps = plan["fps"]
    out = []
    for t0, t1, a, _b, kind in segments(plan, poses):
        if kind == "hold":
            out.append((t0, list(a), "hold"))
            continue
        n = max(1, int(round((t1 - t0) * fps * per_frame)))
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            out.append((t, q_at(plan, poses, t), "move"))
    return out


def turntable_frames(plan):
    tt = plan["turntable"]
    n = int(round(tt["seconds"] * plan["fps"]))
    return [(f, 360.0 * f / n) for f in range(n)]          # 마지막 프레임은 360° 직전(이어 돌리면 끊김 없음)
