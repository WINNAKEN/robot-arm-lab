# -*- coding: utf-8 -*-
"""KMJH 글자 모양(작성자가 사용자 그림을 보고 다각형으로 그린 것 — 원본 로고 파일이 아님).

글자 높이 1 기준 좌표. letters() = [(이름, 역할, 바깥 꼭짓점 목록)] — 역할 navy(글자) · mint(K 의 위 사선).
겹치는 획은 shapely 로 합쳐 글자마다 바깥 윤곽 하나로 만든다(스케치에 겹친 고리를 넣지 않으려고)."""
from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import unary_union

S = 0.25          # 획 두께
GAP = 0.13        # 글자 사이


def _k(x0):
    w = 0.98
    stem = Polygon([(x0, 0), (x0 + S, 0), (x0 + S, 1), (x0, 1)])
    leg = Polygon([(x0 + S - 0.04, 0.62), (x0 + S + 0.25, 0.62), (x0 + w, 0), (x0 + w - 0.33, 0), (x0 + S - 0.04, 0.40)])
    slash = Polygon([(x0 + S + 0.10, 0.66), (x0 + S + 0.42, 0.66), (x0 + w + 0.04, 1), (x0 + w - 0.28, 1)])
    return [("K", "navy", unary_union([stem, leg])), ("K_SLASH", "mint", slash)], x0 + w


def _m(x0):
    w = 1.06
    left = Polygon([(x0, 0), (x0 + S, 0), (x0 + S, 1), (x0, 1)])
    right = Polygon([(x0 + w - S, 0), (x0 + w, 0), (x0 + w, 1), (x0 + w - S, 1)])
    v = Polygon([(x0, 1), (x0 + S + 0.02, 1), (x0 + w / 2, 0.52), (x0 + w - S - 0.02, 1), (x0 + w, 1), (x0 + w / 2, 0.22)])
    return [("M", "navy", unary_union([left, right, v]))], x0 + w


def _j(x0):
    w = 0.86
    stem = Polygon([(x0 + w - S, 0), (x0 + w, 0), (x0 + w, 1), (x0 + w - S, 1)])
    foot = Polygon([(x0, 0), (x0 + w, 0), (x0 + w, S), (x0, S)])
    hook = Polygon([(x0, 0), (x0 + S, 0), (x0 + S, 0.38), (x0, 0.38)])
    return [("J", "navy", unary_union([stem, foot, hook]))], x0 + w


def _h(x0):
    w = 0.98
    left = Polygon([(x0, 0), (x0 + S, 0), (x0 + S, 1), (x0, 1)])
    right = Polygon([(x0 + w - S, 0), (x0 + w, 0), (x0 + w, 1), (x0 + w - S, 1)])
    bar = Polygon([(x0, 0.40), (x0 + w, 0.40), (x0 + w, 0.40 + S), (x0, 0.40 + S)])
    return [("H", "navy", unary_union([left, right, bar]))], x0 + w


def letters():
    out, x = [], 0.0
    for f in (_k, _m, _j, _h):
        parts, x1 = f(x)
        out += parts
        x = x1 + GAP
    width = x - GAP
    rows = []
    for name, role, poly in out:
        assert poly.geom_type == "Polygon" and not poly.interiors, name
        pts = list(poly.exterior.coords)[:-1]
        if Polygon(pts).exterior.is_ccw is False:
            pts = pts[::-1]
        rows.append((name, role, [(float(px), float(py)) for px, py in pts]))
    return rows, width


if __name__ == "__main__":
    import sys

    from PIL import Image, ImageDraw
    rows, width = letters()
    scale, pad = 300, 60
    img = Image.new("RGB", (int(width * scale) + 2 * pad, scale + 2 * pad), "#F5F7FA")
    d = ImageDraw.Draw(img)
    for name, role, pts in rows:
        d.polygon([(pad + px * scale, pad + (1 - py) * scale) for px, py in pts], fill={"navy": "#0B2545", "mint": "#34D399"}[role])
    img.save(sys.argv[1])
    print("width", round(width, 3), [(n, len(p)) for n, _, p in rows])
