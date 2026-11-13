# -*- coding: utf-8 -*-
"""STL ↔ 블렌더 메시 삼각면 대조(L4 R1 F3) — 블렌더 안 · 밖 모두에서 쓰는 순수 파이썬(+ mathutils KD 트리는 부르는 쪽이 넘김).

- STL 의 점을 (float32 그대로) 중복 없이 번호 매기고, 삼각면을 감김 방향을 지킨 채 「가장 작은 번호가 앞」 으로 돌려 세운 꼴로 센다.
- 블렌더 쪽 꼭짓점을 가장 가까운 STL 점 번호로 옮겨 같은 꼴로 센 뒤 두 다중집합이 같은지 본다 — 점은 같고 면 연결 · 감김만 바뀐 것도 잡는다."""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path


def norm_tri(a, b, c):
    m = min(a, b, c)
    if m == a:
        return (a, b, c)
    if m == b:
        return (b, c, a)
    return (c, a, b)


def stl_mesh(path, scale=0.001):
    """이진 STL → (점 목록(× scale) · 감김을 지킨 삼각면 다중집합)."""
    b = Path(path).read_bytes()
    n = struct.unpack_from("<I", b, 80)[0]
    index, pts, tris = {}, [], Counter()
    for i in range(n):
        o = 84 + i * 50 + 12
        ids = []
        for v in range(3):
            key = struct.unpack_from("<3f", b, o + 12 * v)
            if key not in index:
                index[key] = len(pts)
                pts.append((key[0] * scale, key[1] * scale, key[2] * scale))
            ids.append(index[key])
        if len(set(ids)) == 3:
            tris[norm_tri(*ids)] += 1
    return pts, tris


def topology_ok(ref_tris, polys, tris, bad, nontri, collapsed):
    """수용식: 사상 실패 · 삼각형 아닌 면 · 사상 뒤 퇴화(버린 면) 모두 0 · 입력 면 수 = STL 삼각면 수 · 다중집합 같음(L4 R2-F3 — 버린 면을 세지 않던 빈틈)."""
    return bad == 0 and nontri == 0 and collapsed == 0 and len(polys) == sum(ref_tris.values()) and tris == ref_tris


def mesh_tris_mapped(world_pts, polys, ref_tree, tol):
    """블렌더 꼭짓점(세계) → 가장 가까운 STL 점 번호(거리 > tol 이면 None). polys = 꼭짓점 번호 목록들.
    돌려줌: (삼각면 다중집합 · 사상 실패 꼭짓점 수 · 삼각형 아닌 면 수 · 사상 뒤 퇴화해 버린 면 수)."""
    mapped, bad = [], 0
    for p in world_pts:
        _co, idx, d = ref_tree.find(p)
        if d > tol:
            bad += 1
            mapped.append(None)
        else:
            mapped.append(idx)
    tris, nontri, collapsed = Counter(), 0, 0
    for poly in polys:
        if len(poly) != 3:
            nontri += 1
            continue
        a, b_, c = (mapped[k] for k in poly)
        if None in (a, b_, c):                                  # 사상 실패(이미 bad 로 셈)
            continue
        if len({a, b_, c}) < 3:                                 # 퇴화 면 · 사상으로 두 점이 합쳐진 면 — 버리되 반드시 센다
            collapsed += 1
            continue
        tris[norm_tri(a, b_, c)] += 1
    return tris, bad, nontri, collapsed
