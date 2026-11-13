# -*- coding: utf-8 -*-
"""MP11 쓰기 가드 — 분해도 스크립트가 쓰는 폴더 · 파일을 분해도 산출 · MP11 근거 · 격리 작업 뿌리로만 제한한다(MP9 guard.py 를 옮겨 허용 · 보호 목록만 바꿈).

- 저장소 루트를 못 찾으면 멈춘다.
- 경로를 끝까지 풀어 허용 뿌리 아래인지 본다 · 이미 있는 경로 조각 중 심볼릭 링크 · 정션이 하나라도 있으면 거부 · 파일은 쓰기 직전에 `checked_file` 로
  다시 본다(링크 · 하드 링크 거부).
- 보호 폴더(v1 개념 · v2 · v3 · MP6 감속기 · MP5 검토 · 그리퍼 KG1 · MP8 근거 · MP9 조립 · MP10 손목 · URDF · 펌웨어 · 원장) 안이나 그 위는 거부.
- 작업 뿌리(`--scratch-root`)는 미리 만든 격리 폴더만: 표지 파일 `MP11_SCRATCH` · git 작업 트리 밖 · 보호 경로를 품지 않음 · 이 저장소와 겹치지 않음."""
from __future__ import annotations

import os
import stat
from pathlib import Path

PROTECTED_REL = ["models/armold-mks-concept-v1", "models/armold-mks-product-v2", "src/cad/armold-mks-product-v2",
                 "models/armold-mks-product-v3", "src/cad/armold-mks-product-v3", "models/cycloid-27-v1", "src/cad/cycloid-27-v1",
                 "src/cad/review-mp5", ".dev/mp5-review-evidence", "models/robot-arm-urdf-v1", "src/firmware", "src/cad/calibration",
                 "models/kmjh-gripper-v1", "src/cad/kmjh-gripper-v1", ".dev/mp8-evidence",
                 "models/arm-v3-kg1-assembly", "src/cad/arm-v3-kg1-assembly", ".dev/mp9-evidence",
                 "models/j5-wrist-v1", "src/cad/j5-wrist-v1", ".dev/mp10-evidence"]
ALLOWED_REL = ["models/arm-v3-kg1-exploded", ".dev/mp11-evidence"]
MARKER = "MP11_SCRATCH"


def find_root(here: Path) -> Path:
    for p in [here, *here.parents]:
        if (p / "models" / "armold-mks-concept-v1").is_dir() and (p / "src" / "cad").is_dir():
            return p
    raise SystemExit(f"repository root not found above {here}")


def _links_on_the_way(p: Path):
    out, cur = [], Path(p.anchor)
    for part in p.parts[1:]:
        cur = cur / part
        if not os.path.lexists(cur):
            break
        if cur.is_symlink() or cur.is_junction():
            out.append(str(cur))
    return out


def _scratch(root: Path, scratch_root):
    raw = Path(os.path.abspath(scratch_root))
    if _links_on_the_way(raw):
        raise SystemExit(f"scratch root goes through a link or junction: {raw}")
    s = raw.resolve()
    if not s.is_dir() or not (s / MARKER).is_file():
        raise SystemExit(f"scratch root must be an existing folder holding the marker file {MARKER}: {s}")
    for anc in [s, *s.parents]:
        if (anc / ".git").exists():
            raise SystemExit(f"scratch root is inside a git work tree ({anc}): {s}")
    for rel in PROTECTED_REL:
        if (s / rel).exists():
            raise SystemExit(f"scratch root holds a protected path ({rel}): {s}")
    r = root.resolve()
    if s == r or r in s.parents or s in r.parents:
        raise SystemExit(f"scratch root must be outside the repository (and not contain it): {s}")
    return s


def allowed_roots(root: Path, scratch_root):
    roots = [root / rel for rel in ALLOWED_REL]
    if scratch_root is not None:
        roots.append(_scratch(root, scratch_root))
    return roots


def checked_dir(path: Path, root: Path, scratch_root) -> Path:
    raw = Path(os.path.abspath(path))
    links = _links_on_the_way(raw)
    if links:
        raise SystemExit(f"refusing a path through a link or junction: {links}")
    p = raw.resolve()
    for rel in PROTECTED_REL:
        pr = (root / rel).resolve()
        if p == pr or pr in p.parents or p in pr.parents:
            raise SystemExit(f"refusing to write in or above a protected folder: {p} ({pr})")
    for ok in allowed_roots(root, scratch_root):
        okr = ok.resolve()
        if p == okr or okr in p.parents:
            return p
    raise SystemExit(f"refusing to write outside the exploded-view output, MP11 evidence or the scratch root: {p}")


def checked_file(path: Path, root: Path, scratch_root) -> Path:
    raw = Path(os.path.abspath(path))
    checked_dir(raw.parent, root, scratch_root)
    if os.path.lexists(raw) and (raw.is_symlink() or raw.is_junction()):
        raise SystemExit(f"refusing to write through a link: {raw}")
    if raw.is_file() and os.stat(raw).st_nlink > 1:
        raise SystemExit(f"refusing to write a file with more than one hard link: {raw}")
    return raw


def write_bytes(path: Path, data: bytes, root: Path, scratch_root):
    p = checked_file(path, root, scratch_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def safe_rmtree(path: Path, root: Path, scratch_root):
    """트리 안의 모든 폴더 · 파일을 먼저 검사하고(하나라도 걸리면 아무것도 안 지움) 다 통과하면 아래에서부터 지운다."""
    top = checked_dir(path, root, scratch_root)
    if not os.path.lexists(top):
        return
    if not top.is_dir() or top.is_symlink() or top.is_junction():
        raise SystemExit(f"refusing to delete: the top is not a plain folder: {top}")
    files, dirs = [], []
    for dirpath, dirnames, filenames in os.walk(top, topdown=True, followlinks=False):
        for d in dirnames:
            p = Path(dirpath) / d
            if p.is_symlink() or p.is_junction():
                raise SystemExit(f"refusing to delete a tree holding a link or junction: {p}")
            dirs.append(checked_dir(p, root, scratch_root))
        for f in filenames:
            files.append(checked_file(Path(dirpath) / f, root, scratch_root))
    for p in files:
        os.chmod(p, stat.S_IWRITE)
        os.unlink(p)
    for p in sorted(dirs, key=lambda q: len(q.parts), reverse=True):
        os.chmod(p, stat.S_IWRITE)
        os.rmdir(p)
    os.chmod(top, stat.S_IWRITE)
    os.rmdir(top)
