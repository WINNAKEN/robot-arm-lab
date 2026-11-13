# -*- coding: utf-8 -*-
"""MP11 양성 대조 — check_exploded.py 가 읽은 묶음을 메모리 안에서만 하나씩 망가뜨려 맞는 검사가 거짓이 되는지 본다(저장소 파일은 바꾸지 않음).
먼저 망가뜨리지 않은 묶음이 모두 참인지 본다. 결과 = .dev/mp11-evidence/controls.json(guard 로 씀).

사용: python -I -B -X utf8 run_controls.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_exploded as ce  # noqa: E402
import guard  # noqa: E402


def drop_item(b):
    rows = dict(b["groups"])["링크 1"]
    rows[:] = [r for r in rows if r[0] != "LINK1_POST"]


def number_twice(b):
    head, rows = b["groups"][2]
    m, extra, name = rows[0]
    rows[0] = (m, extra + ["J2_MODULE"], name)


def output_sha(b):
    k = sorted(b["manifest"]["outputs"])[0]
    v = b["manifest"]["outputs"][k]
    b["manifest"]["outputs"][k] = ("0" if v[0] != "0" else "1") + v[1:]


def blend_sha(b):
    for r in b["reports"].values():
        r["blend_sha256"] = "0" * 64


def drop_joint_offset(b):
    del b["reports"]["straight"]["offsets_mm"]["JOINT_J3"]


CONTROLS = [("drop_item", drop_item, "C2"), ("number_twice", number_twice, "C2"), ("output_sha", output_sha, "C3"),
            ("blend_sha", blend_sha, "C1"), ("drop_joint_offset", drop_joint_offset, "C5")]


def main():
    repo = guard.find_root(HERE)
    base = ce.load(repo)
    clean = {c["id"]: c["ok"] for c in ce.checks(copy.deepcopy(base))}
    rows = []
    for name, fn, target in CONTROLS:
        b = copy.deepcopy(base)
        fn(b)
        res = {c["id"]: c["ok"] for c in ce.checks(b)}
        rows.append({"control": name, "target": target, "result": res, "ok": res[target] is False})
        print(name, target, "caught" if rows[-1]["ok"] else "MISSED", res)
    doc = {"what": "MP11 양성 대조(run_controls.py) — 메모리 안에서만 망가뜨림", "clean_all_true": all(clean.values()), "clean": clean,
           "rows": rows, "all_caught": all(r["ok"] for r in rows)}
    guard.write_bytes(repo / ".dev" / "mp11-evidence" / "controls.json", (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), repo, None)
    print("CLEAN", doc["clean_all_true"], "ALL_CAUGHT", doc["all_caught"])
    return 0 if doc["clean_all_true"] and doc["all_caught"] else 1


if __name__ == "__main__":
    sys.exit(main())
