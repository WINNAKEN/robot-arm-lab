"""Build the local, network-free model preparation index from the source catalog."""
from html import escape
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "models" / "bench-prep-v1"
CATALOG = Path(__file__).with_name("reference_catalog.json")


def local_link(path, label):
    return f'<a href="{quote("../../" + path, safe="/")}">{escape(label)}</a>'


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    if isinstance(catalog, dict):
        catalog = catalog["entries"]
    source_rows = []
    for entry in catalog:
        paths = entry["manufacturing_paths"]
        links = "<br>".join(local_link(p, Path(p).name) for p in paths) or "미확보"
        source_rows.append(
            "<tr><th>" + escape(entry["name"]) + "</th><td>"
            + escape(entry["geometry_summary"]) + "<div class='links'>" + links
            + "</div></td><td>" + escape(entry["compatibility_status"])
            + "<div class='note'>" + escape(entry["license_observation"]["label"] + " · " + entry["license_observation"]["note"]) + "</div></td></tr>"
        )
    cards = []
    parts = [
        ("01", "cable_tie_mount", "케이블타이 고정대", "24 × 18 × 5 mm", "1개 시험 → 필요하면 총 4개",
         "4mm 폭 타이를 통과시켜 배선을 느슨하게 정리합니다. 바닥을 아래로 놓고, 5mm 브리지와 통로가 막히지 않는지 첫 샘플로 확인합니다."),
        ("02", "wire_label_tag", "배선 표시 태그", "40 × 16 × 2 mm", "1개 시험 → 필요하면 총 6개",
         "빈 평면에 J1 · J2 · CAN · +24V · 0V 등을 적습니다. 구멍에 타이를 끼우며, 표시 면을 위로 출력합니다."),
        ("03", "parts_tray", "나사 정리 트레이", "90 × 60 × 12 mm", "선택 1개",
         "나사·너트·와셔를 담는 작은 트레이입니다. 열린 면을 위로 출력합니다. 전장품이나 활선 단자를 설치하는 외함으로 쓰지 않습니다."),
    ]
    for no, stem, name, dims, qty, desc in parts:
        cards.append(f'''<article class="card"><div class="number">{no}</div>
<h2>{name}</h2><p class="dims">{dims}</p><strong>{qty}</strong><p>{desc}</p>
<div class="downloads"><a href="{stem}.stl">출력용 STL</a><a href="{stem}.step">수정용 STEP</a><a href="{stem}.solidcraft">CAD 원본</a></div></article>''')
    manifest = json.loads((OUT / "slicer" / "slice_manifest.json").read_text(encoding="utf-8"))
    names = {p[1]: p[2] for p in parts}
    slice_rows = []
    for run in manifest["runs"]:
        stem = run["part"]
        current = hashlib.sha256((OUT / f"{stem}.stl").read_bytes()).hexdigest()
        if current != run["model_sha256_after"] or run["exit_code"] != 0 or run["verdict"] != "ready":
            raise ValueError(f"Re-slice the current model before publishing estimates: {stem}")
        estimate = run["estimate"]
        minutes, seconds = divmod(estimate["print_time_s"], 60)
        support = "있음" if estimate["support_generated"] else "없음"
        slice_rows.append(f'<tr><th>{names[stem]}</th><td>{minutes}분 {seconds:02d}초</td>'
                          f'<td>{estimate["filament_g"]:.2f} g</td><td>{support}</td>'
                          f'<td><a href="slicer/{stem}/{stem}.bambu.3mf">Bambu Studio에서 열기</a></td></tr>')
    total_minutes, total_seconds = divmod(sum(r["estimate"]["print_time_s"] for r in manifest["runs"]), 60)
    total_grams = sum(r["estimate"]["filament_g"] for r in manifest["runs"])
    slice_section = '''<h3>H2D · PLA 슬라이서 확인 결과</h3><p>각 부품 <strong>1개씩 별도 작업</strong>으로 계산한 추정치입니다. 0.4mm 노즐 · 0.20mm Standard · Bambu PLA Basic · Textured PEI 가정에서 세 파일 모두 슬라이스되었습니다. 자동 판단에서 서포트는 생성되지 않았습니다.</p>
<div class="tablewrap"><table><thead><tr><th>부품</th><th>예상 시간</th><th>예상 PLA</th><th>서포트</th><th>설정 포함 프로젝트</th></tr></thead><tbody>''' + "".join(slice_rows) + '''</tbody></table></div>
<p class="note">''' + f'3개를 각각 출력할 때의 계산 합계: {total_minutes}분 {total_seconds:02d}초 / {total_grams:.2f}g.' + ''' 한 판에 묶은 출력 시간은 따로 슬라이스해야 합니다. 전달한 3MF는 G-code가 없는 편집용 프로젝트입니다. Bambu Studio에서 실제 장비·PLA 설정과 배치를 확인하고 다시 슬라이스하세요. 실제 출력·맞춤은 미검증입니다. <a href="slicer/README.md">상세 조건</a></p>'''
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>robot-arm-lab · 출력 준비 01</title><style>
:root{--ink:#173147;--muted:#596975;--bg:#f4f5f2;--accent:#f07443;--line:#dbe1e3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Malgun Gothic",system-ui,sans-serif;line-height:1.65}
main{max-width:1240px;margin:auto;padding:44px 28px 64px}header{padding-bottom:28px;border-bottom:2px solid var(--ink)}
.eyebrow{font-size:13px;letter-spacing:.13em;font-weight:700}h1{font-size:38px;letter-spacing:-.04em;margin:12px 0}h2{font-size:21px;margin:8px 0}h3{font-size:24px;margin:32px 0 12px}
p{margin:10px 0}a{color:#145c8e;text-underline-offset:3px}small,.note{font-size:13px;color:var(--muted)}
.lead{font-size:18px;max-width:850px}.pill{display:inline-block;border-radius:20px;background:#dfebe7;color:#215d4a;font-size:13px;padding:4px 12px;margin-right:6px}
.pending{background:#fff0d8;color:#805516}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin:24px 0}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px}.number{font-size:14px;color:#b7491d;font-weight:800}
.dims{color:var(--muted);font-size:15px}.downloads{display:flex;flex-wrap:wrap;gap:12px;font-size:14px;margin-top:20px}
.hero{margin:24px 0;padding:16px;background:white;border:1px solid var(--line);border-radius:14px}.hero img{display:block;width:100%;height:auto}.hero figcaption{font-size:13px;color:var(--muted);padding:10px}
.callout{border-left:4px solid var(--accent);padding:14px 20px;background:#fff5ed;border-radius:0 8px 8px 0}.tablewrap{overflow:auto;background:white;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:16px;border-bottom:1px solid var(--line)}thead{background:#e8eef0}tbody th{min-width:130px}.links{margin-top:10px;overflow-wrap:anywhere}.note{margin-top:10px}
ol,ul{padding-left:24px}li{margin:8px 0}.split{display:grid;grid-template-columns:1fr 1fr;gap:28px}footer{margin-top:34px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
@media(max-width:850px){.grid,.split{grid-template-columns:1fr}main{padding:24px 16px}h1{font-size:29px}.card{padding:20px}}
@media print{body{background:white}main{padding:0}.grid{gap:10px}.card,figure,tr{break-inside:avoid}a{color:inherit}h3{break-after:avoid}.tablewrap{overflow:visible}}
</style><main><header><div class="eyebrow">ROBOT-ARM-LAB / MODEL PREP 01 / 2026.10.23</div>
<h1>부품이 오기 전, 먼저 준비할 출력물</h1><p class="lead">2축 시험대의 배선을 정리하고 조립을 돕는 보조품 3종입니다. 기존 로봇암 자료는 별도 목록으로 정리했습니다.</p>
<span class="pill">자체 설계 · mm 단위</span><span class="pill">H2D · PLA 기준</span><span class="pill pending">실제 출력·맞춤 미검증</span></header>
<figure class="hero"><img src="preview.png" alt="케이블타이 고정대, 배선 표시 태그, 나사 정리 트레이의 실제 생성 형상"><figcaption>생성한 형상 미리보기. 그림의 부품별 축척은 다를 수 있으므로 아래 mm 치수를 기준으로 보세요.</figcaption></figure>
<div class="grid">''' + "".join(cards) + '''</div>
''' + slice_section + '''
<div class="callout"><strong>첫 출력은 샘플부터.</strong> H2D · PLA를 기준으로 준비했습니다. 노즐 0.4mm · 레이어 0.20mm · Textured PEI 판 · Bambu PLA Basic 프로필은 준비용 가정이므로 실제 장착 노즐·판·보유 PLA에 맞춰 확인하세요. 100% 배율·mm 단위와 부품 치수, 고정대 통로·타이 맞춤을 확인한 뒤 나머지를 출력합니다. 메시 검증은 실제 출력 성공이나 강도 보증이 아닙니다.</div>
<div class="split"><section><h3>실측 뒤 모델링할 것</h3><ol>
<li><strong>타공판 연결부·받침:</strong> 판 두께, 구멍 지름·간격, 절곡 높이, 아래쪽 너트 공간을 확인합니다.</li>
<li><strong>WAGO·퓨즈 홀더 고정판:</strong> 실제 제품 외형과 레버 개방·퓨즈 교체 공간을 측정합니다.</li>
<li><strong>축 표시 부품·드라이버 주변 정리:</strong> 축 지름·돌출 길이, 드라이버 후면 간섭과 케이블 방향을 확인합니다. 회전체에 끼우는 부품은 아직 만들지 않았습니다.</li>
</ol></section><section><h3>이미 선택한 부품 활용</h3><ul>
<li>MKS 모터는 선택한 <strong>금속 NEMA17 L 브래킷</strong>으로 고정합니다. 프린트한 지지부로 교체하지 않습니다.</li>
<li>Waveshare CAN-U에는 기존 케이스가 있습니다. 별도 외함보다 장착 위치를 먼저 정합니다.</li>
<li>CAN 케이블은 <strong>CF888.021 총 1m</strong>입니다. 배치·굴곡 여유를 정한 뒤 절단하며, 타이로 강하게 눌러 고정하지 않습니다.</li>
<li>관절·기어·감속기·베어링 하우징은 본체 설계와 부품 규격을 결정한 뒤 준비합니다.</li>
</ul></section></div>
<h3>받아둔 로봇암 CAD</h3><p>아래는 확보 자료 목록이며 출력 승인 목록이 아닙니다. <strong>파일 수 ≠ 한 대의 출력 수량</strong>입니다. 기본품과 대체품, 시각화용 메시가 섞여 있습니다. 다른 설계의 관절이나 감속기를 임의로 섞지 않습니다.</p>
<div class="tablewrap"><table><thead><tr><th>프로젝트</th><th>확보 파일·바로 가기</th><th>이번 MKS 구성과의 관계</th></tr></thead><tbody>''' + "".join(source_rows) + '''</tbody></table></div>
<h3>수령하면 기록할 치수</h3><div class="tablewrap"><table><thead><tr><th>대상</th><th>측정·확인 항목</th><th>이후 설계에 사용</th></tr></thead><tbody>
<tr><th>모터 + 드라이버</th><td>모터 본체 길이·폭, 축 지름/평면부/돌출, 후면 드라이버 포함 전체 깊이, 커넥터 방향, 고정 나사 체결 깊이</td><td>축 표시 부품, 케이블 간섭, 향후 관절 설계</td></tr>
<tr><th>금속 브래킷 + 판</th><td>브래킷 밑면 슬롯과 두께, 판 구멍 지름/피치·절곡, 볼트·너트·공구 공간</td><td>받침, 어댑터, 부품 배치</td></tr>
<tr><th>WAGO·퓨즈·CAN-U</th><td>실제품 SKU·외형, 레버/교체 공간, DIN 걸쇠 접근, 케이블 출구와 굽힘 여유</td><td>전장 정리용 홀더</td></tr>
</tbody></table></div>
<h3>파일과 수정 방법</h3><p><a href="README.md">모델 사용 안내</a> · <a href="validation.json">실제 메시 검사 결과</a> · <a href="../../src/cad/bench-prep/parameters.json">형상 매개변수</a> · <a href="../../src/cad/bench-prep/build_models.py">모델 생성 스크립트</a> · <a href="../../_research/cad-source-inventory-20261023.md">원본 자료 조사 기록</a></p>
<footer>사용자 확인: 2축 시험용 보조부품 · Bambu H2D · PLA. 기존 PrintForge의 출력 준비 도구와 설치된 SolidCraft 모델링 도구를 활용합니다. 구매·프린터 전송·출력 시작·하드웨어 구동은 수행하지 않았습니다. 슬라이서 결과가 있어도 실제 노즐·판·필라멘트 설정과 첫 샘플을 확인한 뒤 출력하세요.</footer></main></html>'''
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "index.html"
    target.write_text(page, encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
