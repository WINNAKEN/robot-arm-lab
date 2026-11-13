# -*- coding: utf-8 -*-
"""MP14 — 감속기(MP6 cycloid-27-v1) 조립도 한 장(HTML · 그림을 안에 넣음 → 휴대폰에서도 열림).

그림 = make_assembly_view.py 의 분해 그림(exploded.png) + make_all 의 단면(section.png). 수(나사 길이 · 끼움 값 · 쌓임)는 cycloid.json ·
끼움 원장에서 읽는다(손으로 옮기지 않음). 조립 순서 글은 MP6 README 「조립 순서」 와 같은 차례(번호만 그림 번호로 붙임).
사용: python make_assembly_page.py <repo> <out.html>
"""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
M = repo / "models" / "cycloid-27-v1"
C = json.loads((M / "cycloid.json").read_text(encoding="utf-8"))
F = json.loads((repo / "src" / "cad" / "calibration" / "print-fits.json").read_text(encoding="utf-8"))["materials"]["PLA"]["values"]
fv = {k: v["value"] for k, v in F.items()}
sc = C["screws"]


def img(p, w):
    im = Image.open(p).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=86)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


d_low = 5.0 + fv["d_bore_extra"]
d_up = d_low + fv["cam_upper_bore_extra"]
parts = [
    (1, "모터 MKS SERVO42D(NEMA17 · 일체형 드라이버)", "1", "가진 것", "축 Ø5 D · 장착면 → 축 끝 21.5 · 턱 Ø22 × 2"),
    (2, "바닥판 HOUSING_BASE", "1", "흰 · 38 번 판", f"고정 핀 압입 구멍 Ø{fv['pin_press_hole_dia']:.2f} × 28"),
    (3, "고정 핀(강철 다월 Ø4 × 28)", "28", "산 것", "바닥판에 21.85 눌러 넣음 · 윗끝 6.15 는 덮개 구멍에"),
    (4, "아래 편심 축 CAM_LOWER", "1", "하늘 · 38 번 판", f"D 구멍 {d_low:.2f}(축에 눌러 끼움) · 게이지로 높이"),
    (5, "원판 1 DISC_1", "1", "하늘 · 28 번 판", "6801 을 눌러 넣음"),
    (6, "베어링 6801(12 × 21 × 5)", "2", "가진 것", "원판마다 하나"),
    (7, "위 편심 축 CAM_UPPER", "1", "하늘 · 38 번 판", f"D 구멍 {d_up:.2f}(손으로 미끄럼) · 아래 편심과 반대쪽"),
    (8, "원판 2(원판 1 과 같은 부품 · 180° 돌림)", "1", "하늘 · 28 번 판", "6801 을 눌러 넣음"),
    (9, "와셔(2.0 · 2.2 · 2.4 중 하나)", "1", "하늘 · 28 번 판", "8 단계에서 두께 고름"),
    (10, "캐리어 CARRIER", "1", "하늘 · 38 번 판", f"출력 핀 압입 구멍 Ø{fv['pin_press_hole_dia']:.2f} × 6 · 허브 인서트 4"),
    (11, "출력 핀(강철 다월 Ø4 × 20)", "6", "산 것", "캐리어에 눌러 넣음"),
    (12, "베어링 6800(10 × 19 × 5)", "1", "가진 것", "캐리어 가운데(바깥 고리 압입)"),
    (13, "덮개 HOUSING_CAP", "1", "흰 · 38 번 판", f"고정 핀 미끄럼 구멍 Ø{fv['pin_slip_hole_dia']:.2f} × 28 · 인서트 8"),
    (14, "베어링 6808(40 × 52 × 7)", "1", "확인 필요", "덮개 위에서 넣음"),
    (15, "누름 고리 RETAINER", "1", "하늘 · 28 번 판", f"M3 × {sc['retainer']['length_mm']} 넷으로 덮개에"),
    (16, "출력 플랜지 OUTPUT_FLANGE", "1", "하늘 · 28 번 판", f"M3 × {sc['flange']['length_mm']} 넷으로 캐리어 허브에"),
]
extra = [
    ("게이지 GAUGE(0.6)", "1", "하늘 · 28 번 판", "1 단계에서 아래 편심 축 높이 맞춤 — 뒤에 뺌"),
    ("M3 열압입 인서트(M3 × 5.7 × 4.2)", "12", "가진 것", "덮개 아래 4 · 덮개 위 4 · 캐리어 허브 4 — 베어링 넣기 전에 인두로"),
    (f"M3 둥근머리 × {sc['motor']['length_mm']}", "4", "확인 필요", "바닥판 위 → 모터(물림 4.0 · 모터 나사 깊이 4.5 는 가정)"),
    (f"M3 × {sc['cap']['length_mm']}", "4", "확인 필요", "바닥판 아래 → 덮개 인서트(물림 6.2)"),
    (f"M3 × {sc['retainer']['length_mm']}", "4", "확인 필요", "누름 고리 → 덮개 인서트"),
    (f"M3 × {sc['flange']['length_mm']}", "4", "확인 필요", "출력 플랜지 → 캐리어 허브 인서트(팔 · 짐을 같이 조이면 그만큼 길게)"),
]
steps = [
    "<b>먼저 인서트 12</b>(덮개 아래 4 · 덮개 위 4 · 캐리어 허브 4)를 인두로 넣는다 — 베어링 · 핀을 넣기 전에.",
    "<b>D 평면 확인</b>: 아래 편심 축 [4]를 모터 축에 손으로만 대 보아 축 끝에서 18.9 mm 넘게(턱 위 0.6 까지) D 평면을 따라 내려가는지 본다. "
    "평면이 그보다 짧으면 끝까지 안 들어간다 — 누르지 말고 멈춘다(편심 축 모양을 바꿔야 함).",
    "<b>모터만 따로 둔 채</b>: 게이지(0.6)를 모터 턱 위에 D 축을 끼고 놓고, 아래 편심 축 [4]를 D 축에 눌러 게이지에 닿게 한 뒤 게이지를 옆으로 뺀다.",
    f"모터 [1]를 바닥판 [2]에 M3 둥근머리 × {sc['motor']['length_mm']} 넷으로(편심 축 허브 Ø14 가 바닥판 턱 구멍 Ø22.3 을 지남 · 머리는 바닥판 위).",
    f"고정 핀 [3] 28 개를 바닥판 구멍(Ø{fv['pin_press_hole_dia']:.2f})에 <b>바이스 · 손바닥으로 곧게</b> 눌러 넣는다(위로 나온 길이를 같게 · 망치 X).",
    "6801 [6]을 원판 둘 [5] [8]에 눌러 넣는다 — 평평한 판 위에 원판을 놓고 <b>베어링 윗면 = 원판 윗면</b>이 될 때까지(아랫면 쪽은 1.0 들어감). 그 면이 위로 간다.",
    "원판 하나 [5]를 위에서 아래 편심에 <b>손으로 밀어</b> 끼운다(베어링 속 고리가 허브 윗면에 앉음 · 누르지 않는다).",
    "위 편심 축 [7](미끄럼)을 D 축에 내려 간격 고리가 6801 #1 속 고리에 얹히게 한다 — 세게 누르지 않는다(아래 편심 축이 밀리면 게이지 높이를 잃는다) · D 면 때문에 편심이 아래와 반대쪽.",
    "다른 원판 [8]을 <b>180° 돌려</b> 위 편심에 손으로 밀어 끼운다(원판 둘의 같은 표시가 반대쪽).",
    "와셔 [9](먼저 2.2)를 저널에 끼우고 <b>곧은 자를 바닥판 벽 윗면에 걸쳐 와셔 윗면과 견준다</b>: 자가 벽과 와셔에 함께 닿으면 맞음 · 자가 와셔에 떠 있으면 얇은 와셔(2.0) · "
    "와셔 위에 틈이 보이면 두꺼운 와셔(2.4). 2.4 로도 틈이 크면 아래 편심 축이 밀린 것 → 3 단계부터.",
    f"덮개 [13]에 6808 [14]를 위에서 넣고 누름 고리 [15]를 M3 × {sc['retainer']['length_mm']} 넷으로.",
    f"캐리어 [10]에 출력 핀 [11] 6 개 · 가운데에 6800 [12] 바깥 고리를 눌러 넣는다(캐리어만 따로) → 캐리어 허브를 아래에서 6808 속 고리에 밀어 넣고 "
    f"출력 플랜지 [16]를 M3 × {sc['flange']['length_mm']} 넷으로.",
    f"덮개 묶음을 내려 출력 핀이 원판 구멍 · 저널이 6800 속 고리(손으로) · 고정 핀 윗끝이 덮개 구멍(Ø{fv['pin_slip_hole_dia']:.2f} · 미끄럼)에 들어가게 하고, "
    f"바닥판 아래에서 M3 × {sc['cap']['length_mm']} 넷으로 덮개 인서트에 조인다. 다시 열 때는 이 넷만 풀면 덮개 묶음이 통째로 빠진다.",
]
checks = ["모터 축(입력)을 손으로 돌릴 때 걸림 · 뻑뻑한 자리(입력 몇 바퀴째 · 출력 각)", "출력 플랜지가 입력과 <b>반대로</b> 1/27 도는가",
          "출력을 손으로 좌우로 흔들 때 유격(대략 각 · 또는 「안 느껴짐」)", "원판 · 핀 · 캐리어 · 와셔 사이 긁힘 소리 · 자국",
          "고정 핀 · 출력 핀 · 편심 축이 빠지거나 헐거운가", "쓴 와셔 두께", "고정 핀 압입(4.20) · 덮개 씌우기(4.25) · 아래 편심 축 압입(5.20) 느낌"]
st = C["stack_mm"]
E = html.escape
rows = "".join(f"<tr><td class=n>{n}</td><td>{E(a)}</td><td>{q}</td><td>{E(c)}</td><td>{E(d)}</td></tr>" for n, a, q, c, d in parts)
rows2 = "".join(f"<tr><td class=n>·</td><td>{E(a)}</td><td>{q}</td><td>{E(c)}</td><td>{E(d)}</td></tr>" for a, q, c, d in extra)
doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>감속기 조립도</title><style>
:root{{--bg:#fff;--fg:#1d2433;--mute:#5b6577;--line:#d9dee7;--acc:#0f2a4a;--mint:#3fb9a2;--warn:#b5462f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#11161f;--fg:#e6eaf0;--mute:#9aa4b5;--line:#2a3342;--acc:#9cc3ef;--mint:#5fd3bb;--warn:#ff8a70}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:16px}} h1{{font-size:22px;color:var(--acc);margin:8px 0}} h2{{font-size:17px;border-left:4px solid var(--mint);padding-left:8px;margin-top:28px}}
.lead{{color:var(--mute)}} .figs{{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}} .figs figure{{margin:0;flex:1 1 300px}}
.figs img{{width:100%;border:1px solid var(--line);border-radius:6px;background:#fff}} figcaption{{color:var(--mute);font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:14px}} td,th{{border-bottom:1px solid var(--line);padding:6px 6px;text-align:left;vertical-align:top}}
td.n{{font-weight:700;color:var(--acc);width:2em}} ol li{{margin:6px 0}} .warn{{color:var(--warn);font-weight:600}}
.box{{border:1px solid var(--line);border-radius:6px;padding:10px 12px}}
</style></head><body><main>
<h1>사이클로이드 감속기 27:1 조립도</h1>
<p class="lead">robot-arm-lab MP6 <code>cycloid-27-v1</code> · 값 = 2026-11-05(MP13 핀 구멍 · MP14 모터 축) · 바깥 Ø78 · 높이 {st['output_face']:.1f} mm(모터 면 → 출력 플랜지 윗면) · 감속 27 : 1(출력은 입력과 반대 방향).</p>
<div class="figs"><figure><img src="{img(M / 'assembly' / 'exploded.png', 900)}" alt="분해도"><figcaption>분해도 — 번호는 아래 부품표 · 흰 = 바닥판 · 덮개 · 하늘 = 그 밖 인쇄 부품 · 회색 = 강철 다월 · 진회색 = 베어링</figcaption></figure>
<figure><img src="{img(M / 'section.png', 900)}" alt="단면"><figcaption>조립 단면(XZ) — 모터는 흐리게</figcaption></figure></div>
<h2>부품표</h2><table><tr><th>#</th><th>부품</th><th>수</th><th>어디서</th><th>메모</th></tr>{rows}{rows2}</table>
<p class="lead">「28 번 판」 = 10/30 에 뽑은 하늘 부품(지금 값과 같아 다시 안 뽑음) · 「38 번 판」 = 이번 판 · 6808 · M3 나사는 가진 것인지 확인 필요.</p>
<h2>조립 순서</h2><ol>{''.join(f'<li>{s}</li>' for s in steps)}</ol>
<div class="box"><span class="warn">주의</span> — 아직 시험 전인 값: D 구멍 {d_low:.2f} · {d_up:.2f}(맞춤 확인 판 범위 밖) · 핀 4.20 · 4.25 는 하늘 Pure 시편 판정(바닥판 · 덮개는 흰 Basic — 같은 판의 흰 핀 시편 36 으로 견줘 봄) ·
6808 자리 · 모터 나사 깊이. 맞지 않으면 억지로 누르지 말고 어디서 얼마나 걸렸는지 적어 주세요.<br>
모터를 책상에 잡아 둘 <b>모터 받침은 아직 없음</b>(다음 단위로 설계) — 손으로 돌려 보는 시험만 하고 모터 전원은 받침을 단 뒤에.</div>
<h2>손 시험 기록지(모터 전원 없이)</h2><table>{''.join(f'<tr><td>{c}</td><td style="width:40%"></td></tr>' for c in checks)}</table>
</main></body></html>
"""
out.write_text(doc, encoding="utf-8")
print("ok", out, round(out.stat().st_size / 1024), "KB")
