# -*- coding: utf-8 -*-
"""MP5 문서 동기 검사 — 보고서가 계산 산출물과 같은 수를 싣는지, 산출물이 지금 입력에서 나온 것인지 본다.

1. `loads.json` 의 `inputs_sha256` 이 지금 저장소 파일의 sha256 과 같다(입력이 바뀌었는데 산출물을 다시 만들지 않으면 실패).
2. 두 파일 모두 블록 이름마다 시작 · 끝 표지가 꼭 하나씩이고(중복 · 닫히지 않은 블록이면 실패), `loads.md` 의 `<!-- 이름:begin -->` ~ `<!-- 이름:end -->` 블록마다 보고서(`docs/design/022-modeling-reducer-review.md`)에 같은 이름의 블록이 있고
   줄이 글자 그대로 같다(계산이 바뀌었는데 문서를 고치지 않으면 실패).
3. 산출물을 지금 다시 계산한 결과와 견준다(`--rerun` — 임시 폴더에 만들어 `loads.md` · `loads.json` 과 바이트 비교).

사용: python check_doc_sync.py [--rerun]   종료 코드 0 = 모두 같음 · 1 = 다름(무엇이 다른지 출력)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])
EVID = ROOT / ".dev" / "mp5-review-evidence"
DOC = ROOT / "docs" / "design" / "022-modeling-reducer-review.md"
BLOCK = re.compile(r"<!-- (mp5-[a-z]+):begin -->\n(.*?)\n<!-- \1:end -->", re.S)
MARK = re.compile(r"<!-- (mp5-[a-z]+):(begin|end) -->")


def blocks(text, where, bad):
    """블록 이름 → 본문. 같은 이름이 두 번 이상이거나 시작 · 끝 표지가 짝이 맞지 않으면 bad 에 적는다(덮어써 놓치지 않게)."""
    text = text.replace("\r\n", "\n")
    marks = [(m.group(1), m.group(2)) for m in MARK.finditer(text)]
    for name in sorted({n for n, _ in marks}):
        nb = sum(1 for n, k in marks if n == name and k == "begin")
        ne = sum(1 for n, k in marks if n == name and k == "end")
        if nb != 1 or ne != 1:
            bad.append(f"{where}: block {name} has {nb} begin / {ne} end markers")
    found = [(m.group(1), m.group(2)) for m in BLOCK.finditer(text)]
    if len(found) * 2 != len(marks):
        bad.append(f"{where}: {len(marks)} markers but {len(found)} well-formed blocks")
    return dict(found)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun", action="store_true")
    a = ap.parse_args()
    bad = []
    data = json.loads((EVID / "loads.json").read_text(encoding="utf-8"))
    for rel, digest in sorted(data["inputs_sha256"].items()):
        now = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        if now != digest:
            bad.append(f"input changed since loads.json: {rel}")
    want = blocks((EVID / "loads.md").read_text(encoding="utf-8"), "loads.md", bad)
    have = blocks(DOC.read_text(encoding="utf-8"), "doc", bad)
    if not want:
        bad.append("loads.md has no blocks")
    for name, body in want.items():
        if name not in have:
            bad.append(f"doc lacks block {name}")
        elif have[name] != body:
            bad.append(f"doc block {name} differs from loads.md")
    for name in have:
        if name not in want:
            bad.append(f"doc has block {name} that loads.md does not")
    if a.rerun:
        with tempfile.TemporaryDirectory(dir=EVID.parent, ignore_cleanup_errors=True) as tmp:
            run = subprocess.run([sys.executable, str(HERE / "joint_loads.py"), "--out", tmp], capture_output=True)
            if run.returncode != 0:
                bad.append(f"rerun failed rc={run.returncode}: {run.stderr.decode('utf-8', 'replace')[-400:]}")
            else:
                for f in ("loads.md", "loads.json"):
                    if (Path(tmp) / f).read_bytes() != (EVID / f).read_bytes():
                        bad.append(f"rerun {f} differs from the stored {f}")
    print(f"inputs {len(data['inputs_sha256'])} · blocks {len(want)} · rerun {'yes' if a.rerun else 'no'}")
    for b in bad:
        print("FAIL", b)
    print("PASS" if not bad else f"FAIL {len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
