# -*- coding: utf-8 -*-
"""MP11 분해도 렌더에 번호 풍선 + 부품 목록을 붙인다(보기용).
입력 = 렌더 JPG + explode_arm.py 가 쓴 label-grid*.json(카메라 광선이 처음 맞은 부품 격자 · 부품 중심의 화면 자리).
풍선 자리 = 부품이 없는 빈칸 중 그 부품의 보이는 점에 가장 가까운 곳(다른 풍선 · 그림 가장자리 피함).
번호 묶음 = GROUPS(check_exploded.py 의 C2 가 같은 표로 완전성을 본다). 쓰기는 guard.py 로만.
사용: python label_parts.py <render.jpg> <label-grid.json> <out.jpg> [제목 둘째 줄] [--scratch-root <격리 폴더>]
"""
import io
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

NAVY, MINT, GRAY, INK = (11, 37, 69), (52, 211, 153), (107, 114, 128), (30, 34, 40)
FONT = r"C:\Windows\Fonts\malgun.ttf"
FONTB = r"C:\Windows\Fonts\malgunbd.ttf"

# (머리, [(대표 바디, 같은 번호로 묶는 바디들, 이름)])
GROUPS = [
    ("바닥", [("BASE_FOOT", [], "바닥 발판"), ("BASE_LIGHT_RING", [], "바닥 빛 띠(민트)"), ("BASE_COLUMN", [], "바닥 기둥"),
             ("J1_MODULE", [], "J1 관절 모듈"), ("J1_ACCENT_RING", [], "J1 띠 고리")]),
    ("링크 1", [("LINK1_SHOULDER_CAP", [], "어깨 받침"), ("LINK1_POST", [], "어깨 기둥"), ("J2_MODULE", [], "J2 관절 모듈"),
               ("J2_ACCENT_RING", [], "J2 띠 고리"), ("J2_END_CAP", ["J2_CAP_SLASH"], "J2 끝 덮개 + 사선")]),
    ("링크 2", [("LINK2_SHOULDER_HUB", [], "어깨 허브"), ("LINK2_SHOULDER_HUB_CAP", ["LINK2_SHOULDER_HUB_SLASH"], "어깨 허브 덮개 + 사선"),
               ("LINK2_UPPER_BAR", [], "위팔"), ("LINK2_LOGO_K", ["LINK2_LOGO_M", "LINK2_LOGO_J", "LINK2_LOGO_H", "LINK2_LOGO_K_SLASH"],
                                                   "로고 글자 KMJH + 사선"),
               ("J3_MODULE", [], "J3 관절 모듈"), ("J3_ACCENT_RING", [], "J3 띠 고리"), ("J3_END_CAP", ["J3_CAP_SLASH"], "J3 끝 덮개 + 사선")]),
    ("링크 3", [("LINK3_ELBOW_HUB", [], "팔꿈치 허브"), ("LINK3_ELBOW_HUB_CAP", ["LINK3_ELBOW_HUB_SLASH"], "팔꿈치 허브 덮개 + 사선"),
               ("LINK3_FOREARM_BAR", [], "아래팔"), ("J4_MODULE", [], "J4 관절 모듈"), ("J4_ACCENT_RING", [], "J4 띠 고리"),
               ("J4_END_CAP", ["J4_CAP_SLASH"], "J4 끝 덮개 + 사선")]),
    ("링크 4", [("LINK4_NECK", [], "목"), ("J5_MODULE", [], "J5 관절 모듈"), ("J5_ACCENT_RING", [], "J5 띠 고리"),
               ("J5_END_CAP", ["J5_CAP_SLASH"], "J5 끝 덮개 + 사선")]),
    ("링크 5", [("LINK5_WRIST_HUB", [], "손목 허브"), ("LINK5_WRIST_HUB_CAP", ["LINK5_WRIST_HUB_SLASH"], "손목 허브 덮개 + 사선"),
               ("LINK5_WRIST_BAR", [], "손목 막대"), ("J6_MODULE", [], "J6 관절 모듈"), ("J6_ACCENT_RING", [], "J6 띠 고리"),
               ("J6_END_CAP", ["J6_CAP_SLASH"], "J6 끝 덮개 + 사선")]),
    ("링크 6", [("LINK6_TOOL_FLANGE", [], "공구 플랜지(M3 인서트 넷)"), ("LINK6_TOOL_RING", [], "공구 돌기 Ø20(민트)")]),
    ("그리퍼 KG1", [("KG1_BASE", [], "그리퍼 바탕"), ("KG1_SERVO", [], "서보(구매품 · 상자로 그림)"), ("KG1_PINION", [], "피니언 m1.5 z18"),
                   ("KG1_ROD_0", ["KG1_ROD_1", "KG1_ROD_2", "KG1_ROD_3"], "탄소 관 Ø6 × 4(구매품)"), ("KG1_JAW_A", [], "턱 A"),
                   ("KG1_JAW_B", [], "턱 B"), ("KG1_PAD_A_*", [], "손끝 A"), ("KG1_PAD_B_*", [], "손끝 B")]),
]


def resolve(n, names):
    """GROUPS 의 이름(끝 * = 앞부분이 같은 개체 하나)을 장면 개체 이름으로."""
    if n.endswith("*"):
        m = [x for x in names if x.startswith(n[:-1])]
        assert len(m) == 1, n
        return m[0]
    assert n in names, n
    return n


def group_items(names, groups=None):
    """[(번호, 머리, [개체 이름], 이름)] — 번호는 GROUPS 차례대로 1 부터."""
    items, num = [], 0
    for head, rows in (GROUPS if groups is None else groups):
        for main_n, extra, title in rows:
            num += 1
            items.append((num, head, [resolve(main_n, names)] + [resolve(e, names) for e in extra], title))
    return items


def label(img_p, grid_p, out_p, sub, repo, scratch_root=None):
    G = json.loads(Path(grid_p).read_text(encoding="utf-8"))
    im = Image.open(img_p).convert("RGB")
    W, H = im.size
    NX, NY, names = G["nx"], G["ny"], G["names"]
    cw, ch = W / NX, H / NY
    k = W / 2400                                                        # 글자 · 풍선 크기 배율(2400 폭 기준)
    R = 21 * k
    fnum = ImageFont.truetype(FONTB, int(22 * k))

    occ = [[c >= 0 for c in row] for row in G["grid"]]
    # 빈칸 = 부품에서 2 칸 넘게 떨어진 칸
    pad = max(1, int(round(1.5 * R / cw)))
    free = [[True] * NX for _ in range(NY)]
    for iy in range(NY):
        for ix in range(NX):
            if occ[iy][ix]:
                for dy in range(-pad, pad + 1):
                    for dx in range(-pad, pad + 1):
                        y, x = iy + dy, ix + dx
                        if 0 <= y < NY and 0 <= x < NX:
                            free[y][x] = False
    items = group_items(names)
    placed, out_items = [], []
    margin = 40 * k
    for num, head, members, name in items:
        ids = {names.index(m) for m in members}
        px, py = G["proj"][members[0]]
        px, py = px * W, py * H
        cells = [(ix, iy) for iy in range(NY) for ix in range(NX) if G["grid"][iy][ix] in ids]
        hidden = not cells
        if cells:
            ax, ay = min((((ix + 0.5) * cw, (iy + 0.5) * ch) for ix, iy in cells),
                         key=lambda q: (q[0] - px) ** 2 + (q[1] - py) ** 2)
        else:
            ax, ay = px, py
        best, bd = None, 1e18
        for iy in range(NY):
            for ix in range(NX):
                if not free[iy][ix]:
                    continue
                x, y = (ix + 0.5) * cw, (iy + 0.5) * ch
                if x < margin or x > W - margin or y < margin or y > H - margin:
                    continue
                if any((x - qx) ** 2 + (y - qy) ** 2 < (2.6 * R) ** 2 for qx, qy, *_ in placed):
                    continue
                dd = math.hypot(x - ax, y - ay)
                if dd < 50 * k:
                    continue
                # 다른 풍선의 끌줄과 너무 붙는 자리 피함(약한 벌점)
                pen = sum(1 for qx, qy, bx, by in placed if _near_seg(x, y, qx, qy, bx, by, 1.6 * R)) * 60 * k
                if dd + pen < bd:
                    best, bd = (x, y), dd + pen
        placed.append((best[0], best[1], ax, ay))
        out_items.append((num, head, name, (ax, ay), best, hidden))

    dr = ImageDraw.Draw(im)
    for num, head, name, (ax, ay), (bx, by), hidden in out_items:
        d = math.hypot(bx - ax, by - ay)
        ex, ey = bx - (bx - ax) / d * R, by - (by - ay) / d * R
        dr.line([(ax, ay), (ex, ey)], fill=INK, width=max(1, int(2 * k)))
        rr = 4 * k
        dr.ellipse([ax - rr, ay - rr, ax + rr, ay + rr], fill=INK)
        dr.ellipse([bx - R, by - R, bx + R, by + R], fill=(255, 255, 255), outline=NAVY, width=max(2, int(3 * k)))
        t = str(num)
        tw = dr.textlength(t, font=fnum)
        dr.text((bx - tw / 2, by - 15 * k), t, font=fnum, fill=NAVY)

    # 오른쪽 목록 판
    PW = int(900 * k)
    canvas = Image.new("RGB", (W + PW, H), (248, 249, 251))
    canvas.paste(im, (0, 0))
    dc = ImageDraw.Draw(canvas)
    ft, fs, fh, fi = (ImageFont.truetype(FONTB, int(38 * k)), ImageFont.truetype(FONT, int(22 * k)),
                      ImageFont.truetype(FONTB, int(25 * k)), ImageFont.truetype(FONT, int(24 * k)))
    x0 = W + int(40 * k)
    dc.rectangle([W, 0, W + int(8 * k), H], fill=NAVY)
    dc.text((x0, int(36 * k)), "KMJH 6 축 팔 — 부품 분해도", font=ft, fill=NAVY)
    dc.text((x0, int(92 * k)), "외장 v3(rev1) + 그리퍼 KG1 · 점선 = 관절 축 · 보기용", font=fs, fill=GRAY)
    if sub:
        dc.text((x0, int(124 * k)), sub, font=fs, fill=GRAY)
    y = int(185 * k)
    colw = (PW - int(70 * k)) // 2
    col, yc = 0, y
    lh = int(40 * k)
    total = len(items) + len(GROUPS)
    per_col = math.ceil(total / 2)
    count = 0
    last_head = None
    for num, head, name, *_ in out_items:
        if head != last_head:
            if count >= per_col and col == 0:
                col, yc = 1, y
            dc.text((x0 + col * colw, yc), head, font=fh, fill=NAVY)
            dc.line([(x0 + col * colw, yc + int(36 * k)), (x0 + col * colw + colw - int(20 * k), yc + int(36 * k))], fill=MINT, width=max(1, int(2 * k)))
            yc += lh + int(4 * k)
            count += 1
            last_head = head
        rx = x0 + col * colw
        r = 15 * k
        cx, cy = rx + r, yc + r + 2 * k
        dc.ellipse([cx - r, cy - r, cx + r, cy + r], outline=NAVY, width=max(1, int(2 * k)), fill=(255, 255, 255))
        fn = ImageFont.truetype(FONTB, int(17 * k))
        tw = dc.textlength(str(num), font=fn)
        dc.text((cx - tw / 2, cy - 12 * k), str(num), font=fn, fill=NAVY)
        dc.text((rx + 2 * r + 10 * k, yc), name, font=fi, fill=INK)
        yc += lh
        count += 1
    hidden_list = [str(n) for n, _h, _l, _a, _b, hid in out_items if hid]
    foot = "가려진 부품(끌줄이 부품 중심을 가리킴): " + (", ".join(hidden_list) if hidden_list else "없음")
    dc.text((x0, H - int(50 * k)), foot, font=fs, fill=GRAY)
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    guard.write_bytes(Path(out_p), buf.getvalue(), repo, scratch_root)
    print("LABELED", len(out_items), "hidden", hidden_list)
    return {"items": len(out_items), "hidden": [int(h) for h in hidden_list], "size": list(canvas.size)}


def main():
    argv = sys.argv[1:]
    scratch = None
    if "--scratch-root" in argv:
        i = argv.index("--scratch-root")
        scratch = argv[i + 1]
        del argv[i:i + 2]
    label(Path(argv[0]), Path(argv[1]), Path(argv[2]), argv[3] if len(argv) > 3 else "", guard.find_root(HERE), scratch)


def _near_seg(x, y, x1, y1, x2, y2, r):
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((x - x1) * vx + (y - y1) * vy) / L2))
    return math.hypot(x - (x1 + t * vx), y - (y1 + t * vy)) < r


if __name__ == "__main__":
    main()
