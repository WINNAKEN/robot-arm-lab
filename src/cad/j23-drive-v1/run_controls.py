# -*- coding: utf-8 -*-
"""MP16 — 양성 대조: build_drive.py --control <이름> 판(작업 폴더 아래)을 check_drive.py 가 잡는지. 기대한 검사가 거짓이어야 통과.
사용: python run_controls.py --cli <solidcraft-cli.exe> --scratch <작업 폴더>   (기록 = .dev/mp16-evidence/controls.json)"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from build_drive import CONTROLS  # noqa: E402

EXPECT = {"pin_tight": ["C7"], "disc_big": ["C2"], "plate_wide": ["C2"], "seat_small": ["C7", "C2"], "lobe_short": ["C5"], "guard_narrow": ["C2"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--scratch", required=True, type=Path)
    a = ap.parse_args()
    assert set(EXPECT) == set(CONTROLS), (set(EXPECT) ^ set(CONTROLS))
    rows = []
    for name in sorted(CONTROLS):
        out = a.scratch / "controls" / name
        b = subprocess.run([sys.executable, "-B", str(HERE / "build_drive.py"), "--cli", a.cli, "--scratch", str(a.scratch), "--control", name, "--out", str(out)],
                           capture_output=True, text=True, encoding="utf-8")
        if b.returncode:
            rows.append({"control": name, "means": CONTROLS[name], "built": False, "caught": False, "log": (b.stderr or b.stdout)[-600:]})
            continue
        c = subprocess.run([sys.executable, "-B", str(HERE / "check_drive.py"), "--parts", str(out / "parts"), "--record", str(out / "build-record.json"),
                            "--out", str(out / "check.json"), "--quick"], capture_output=True, text=True, encoding="utf-8")
        res = json.loads((out / "check.json").read_text(encoding="utf-8"))["results"]
        failed = sorted(k for k, v in res.items() if isinstance(v, dict) and v.get("ok") is False)
        caught = all(e in failed for e in EXPECT[name])
        rows.append({"control": name, "means": CONTROLS[name], "built": True, "expected_false": EXPECT[name], "failed_checks": failed, "caught": caught})
        print(name, "caught" if caught else "MISSED", failed)
    rec = {"what": "MP16 양성 대조 — 일부러 고친 판을 검사가 잡는가(기대한 검사가 거짓)", "rows": rows, "all_caught": all(r["caught"] for r in rows)}
    (ROOT / ".dev" / "mp16-evidence" / "controls.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print("all caught", rec["all_caught"])


if __name__ == "__main__":
    main()
