# -*- coding: utf-8 -*-
"""MP7 갤러리 모아 보기 — blender_gallery.py 의 렌더를 한 장에 모은다(휴대폰에서 한눈에).

사용: python gallery_sheet.py --gallery <갤러리 폴더> --poses gallery_poses.json [--tile 560] [--scratch-root <작업 뿌리>]
만드는 것: sheet-brand.jpg · sheet-swap.jpg(조합마다 모든 렌더) · compare-brand-swap.jpg(같은 샷을 두 조합으로 나란히).
gallery-report.json 의 checks 가 모두 참일 때만 만든다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import checked_file, find_root  # noqa: E402

ANGLE = {"turn000": "앞 3/4", "turn045": "앞", "turn090": "오른 앞 3/4", "turn135": "오른쪽", "turn180": "뒤 3/4", "turn225": "뒤",
         "turn270": "왼 뒤 3/4", "turn315": "왼쪽", "top": "위에서", "low": "낮게", "wrist": "손목 확대", "logo": "글자 확대"}
SCHEME = {"brand": "브랜드 색(흰 몸체)", "swap": "흰 ↔ 회색 바꿈(회색 몸체)"}
COMPARE = ["display-turn000", "display-turn135", "home", "pick", "reach-up", "side-reach"]
FONT = "C:/Windows/Fonts/malgun.ttf"


def caption(label, poses):
    if label.startswith("display-"):
        return f"{poses['display']} · {ANGLE[label.split('-', 1)[1]]}"
    return poses[label]


def tile(path, w, text, font):
    im = Image.open(path).convert("RGB")
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    pad = round(w * 0.075)
    canvas = Image.new("RGB", (w, im.height + pad), (255, 255, 255))
    canvas.paste(im, (0, 0))
    ImageDraw.Draw(canvas).text((round(w * 0.025), im.height + round(pad * 0.18)), text, fill=(11, 37, 69), font=font)
    return canvas


def grid(tiles, cols, title, font_big, gap=8):
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    head = round(w * 0.14)
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, head + rows * h + (rows + 1) * gap), (233, 237, 242))
    ImageDraw.Draw(sheet).text((gap * 2, round(head * 0.22)), title, fill=(11, 37, 69), font=font_big)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet.paste(t, (gap + c * (w + gap), head + gap + r * (h + gap)))
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gallery", required=True, type=Path)
    ap.add_argument("--poses", required=True, type=Path)
    ap.add_argument("--tile", type=int, default=560)
    ap.add_argument("--scratch-root", type=Path, default=None)
    a = ap.parse_args()
    root = find_root(Path(__file__).resolve().parent)
    rep = json.loads((a.gallery / "gallery-report.json").read_text(encoding="utf-8"))
    if not all(rep["checks"].values()):
        raise SystemExit("gallery checks are not all true — no sheet")
    poses = {p["name"]: p["label"] for p in json.loads(a.poses.read_text(encoding="utf-8"))["poses"]}
    font = ImageFont.truetype(FONT, round(a.tile * 0.042))
    font_big = ImageFont.truetype(FONT, round(a.tile * 0.075))
    by = {}
    for key, r in rep["renders"].items():
        s, label = key.split("/", 1)
        by.setdefault(s, {})[label] = a.gallery / r["file"]
    made = []
    for s, items in by.items():
        tiles = [tile(p, a.tile, caption(label, poses), font) for label, p in items.items()]
        out = checked_file(a.gallery / f"sheet-{s}.jpg", root, a.scratch_root)
        grid(tiles, 4, f"KMJH 6축 외장 v3 — {SCHEME[s]}", font_big).save(out, quality=88)
        made.append(out.name)
    if {"brand", "swap"} <= set(by):
        tiles = []
        for label in COMPARE:
            if label in by["brand"] and label in by["swap"]:
                tiles.append(tile(by["brand"][label], a.tile, f"{caption(label, poses)} — 흰 몸체", font))
                tiles.append(tile(by["swap"][label], a.tile, f"{caption(label, poses)} — 회색 몸체", font))
        out = checked_file(a.gallery / "compare-brand-swap.jpg", root, a.scratch_root)
        grid(tiles, 4, "흰 몸체(브랜드) ↔ 회색 몸체(바꿈) 나란히", font_big).save(out, quality=88)
        made.append(out.name)
    print("SHEETS", made)


if __name__ == "__main__":
    main()
