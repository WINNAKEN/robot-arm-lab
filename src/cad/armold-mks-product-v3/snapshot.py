# -*- coding: utf-8 -*-
"""보호 폴더(v1 개념 모델 · v2 산출 · v2 생성기)의 모든 파일(추적 · 미추적 · 무시)을 상대 경로 · 바이트 해시 · 크기로 적는다.

L2 R1 F3 · R2-04: 「추적 파일 = HEAD」 만으로는 미추적 · 무시 · 추가 · 삭제를 못 본다 → 단위 시작 전에 이 스냅숏(before)을 남기고, 검사기가 실행 뒤 같은
꼴로 다시 떠서 추가 · 삭제 · 내용 변경을 본다. 보호 폴더 목록은 이 파일의 상수(`guard.PROTECTED_REL`)이며 스냅숏 파일에서 받지 않는다.
스냅숏 파일은 덮어쓰지 않는다(이미 있으면 멈춤) · 뜬 시각(UTC) · 명령 · 저장소 HEAD · 미리 있던 미추적 / 무시 줄을 함께 적고, 파일의 sha256 을 옆 파일에 남긴다.

사용: python snapshot.py --out <json> [--scratch-root <격리 작업 뿌리>]  (출력은 guard.checked_file 로 거른다)"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import PROTECTED_REL, checked_file, find_root  # noqa: E402


def snapshot(root: Path, rels=PROTECTED_REL):
    files = {}
    for rel in rels:
        base = root / rel
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.is_symlink():
                    files[p.relative_to(root).as_posix()] = {"symlink": os.readlink(p)}
                    continue
                b = p.read_bytes()
                files[p.relative_to(root).as_posix()] = {"sha256": hashlib.sha256(b).hexdigest(), "size": len(b)}
    return files


def git_state(root: Path, rels=PROTECTED_REL):
    if not (root / ".git").exists():
        return {"available": False}

    def g(*a):
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return {"available": True, "head": g("rev-parse", "HEAD").strip(), "status_porcelain": g("status", "--porcelain", "--ignored", "--", *rels).splitlines()}


def compare(before: dict, now: dict):
    added = sorted(set(now) - set(before))
    removed = sorted(set(before) - set(now))
    changed = sorted(k for k in set(before) & set(now) if before[k] != now[k])
    return {"added": added, "removed": removed, "changed": changed, "same": not (added or removed or changed), "files": len(now)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--scratch-root", type=Path, default=None)
    a = ap.parse_args()
    root = find_root(Path(__file__).resolve().parent)
    out = checked_file(a.out, root, a.scratch_root)
    if out.exists():
        raise SystemExit(f"snapshot exists, not overwriting: {out}")
    rec = {"what": "protected folders (v1 concept, v2 product, v2 generator): every file, bytes hashed", "roots": PROTECTED_REL,
           "taken_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "command": [Path(sys.executable).name, *sys.argv],
           "root": str(root), "files": snapshot(root), "git": git_state(root)}
    body = (json.dumps(rec, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    out.write_bytes(body)
    side = checked_file(out.with_suffix(out.suffix + ".sha256"), root, a.scratch_root)
    side.write_text(hashlib.sha256(body).hexdigest() + "  " + out.name + "\n", encoding="utf-8")
    print("files", len(rec["files"]), "git", rec["git"].get("head"), "sha256", hashlib.sha256(body).hexdigest())


if __name__ == "__main__":
    main()
