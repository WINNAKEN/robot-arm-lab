# -*- coding: utf-8 -*-
"""MP7 쓰기 가드 — 생성기 · 검사기 · 스냅숏 · 블렌더 스크립트가 쓰는 폴더 · 파일을 v3 산출 · v3 근거 · 격리 작업 뿌리로만 제한한다.

L2 R1 F4 · R2-02 · R2-03:
- 저장소 루트를 못 찾으면 멈춘다(절대 경로로 돌아가지 않음).
- 경로를 끝까지 풀어(resolve) 허용 뿌리 아래인지 본다 · 이미 있는 경로 조각 중 심볼릭 링크 · 정션이 하나라도 있으면 거부(폴더 · 파일 모두 — 쓰기 직전의
  마지막 대상까지 `checked_file` 로 다시 본다).
- 보호 폴더(v1 개념 · v2 산출 · v2 생성기) 안이나 그 위는 거부.
- 작업 뿌리(`--scratch-root`)는 **미리 만든 격리 폴더만**: 그 안에 표지 파일 `MP7_SCRATCH` 가 있어야 하고 · git 작업 트리 안이 아니어야 하며(자기 · 조상에
  `.git` 없음) · 보호 폴더 경로를 품지 않고 · 이 저장소와 겹치지 않아야 한다(사본에서 실 저장소를 작업 뿌리로 지정하는 우회를 막음)."""
from __future__ import annotations

import os
from pathlib import Path

PROTECTED_REL = ["models/armold-mks-concept-v1", "models/armold-mks-product-v2", "src/cad/armold-mks-product-v2"]
MARKER = "MP7_SCRATCH"


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


def protected(root: Path):
    return [root / rel for rel in PROTECTED_REL]


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


def allowed_roots(root: Path, scratch_root: Path | None):
    roots = [root / "models" / "armold-mks-product-v3", root / ".dev" / "product-v3-evidence"]
    if scratch_root is not None:
        roots.append(_scratch(root, scratch_root))
    return roots


def checked_dir(path: Path, root: Path, scratch_root: Path | None) -> Path:
    """쓰려는 폴더를 검사해 풀린 경로를 돌려준다. 허용 밖이면 SystemExit — 아무것도 만들거나 지우기 전에 부른다."""
    raw = Path(os.path.abspath(path))
    links = _links_on_the_way(raw)
    if links:
        raise SystemExit(f"refusing a path through a link or junction: {links}")
    p = raw.resolve()
    for prot in protected(root):
        pr = prot.resolve()
        if p == pr or pr in p.parents or p in pr.parents:
            raise SystemExit(f"refusing to write in or above a protected folder: {p} ({pr})")
    for ok in allowed_roots(root, scratch_root):
        okr = ok.resolve()
        if p == okr or okr in p.parents:
            return p
    raise SystemExit(f"refusing to write outside the v3 output, v3 evidence or the scratch root: {p}")


def checked_file(path: Path, root: Path, scratch_root: Path | None) -> Path:
    """쓰거나 지우려는 파일 하나 — 부모 폴더를 checked_dir 로, 파일 자신이 링크 · 정션이면 거부."""
    raw = Path(os.path.abspath(path))
    checked_dir(raw.parent, root, scratch_root)
    if os.path.lexists(raw) and (raw.is_symlink() or raw.is_junction()):
        raise SystemExit(f"refusing to write through a link: {raw}")
    if raw.is_file() and os.stat(raw).st_nlink > 1:            # 하드 링크 — 다른 이름(보호 폴더일 수 있음)과 같은 바이트를 공유
        raise SystemExit(f"refusing to write a file with more than one hard link: {raw}")
    return raw


def safe_rmtree(path: Path, root: Path, scratch_root: Path | None):
    """폴더 트리 지우기(L4 R2-F2) — **먼저** 트리 안의 모든 폴더를 checked_dir(링크 · 정션 거부) · 모든 파일을 checked_file(링크 · 하드 링크 거부)로 보고,
    하나라도 걸리면 아무것도 지우지 않고 멈춘다. 다 통과했을 때만 아래에서부터 읽기 전용 속성을 풀고 지운다(속성은 검사를 통과한 이름에만 손댐).
    검사와 삭제 사이에 다른 프로세스가 트리를 바꾸는 경우는 막지 않는다(혼자 쓰는 격리 작업 뿌리 전제)."""
    import stat
    top = checked_dir(path, root, scratch_root)
    if not os.path.lexists(top):
        return
    if not top.is_dir() or top.is_symlink() or top.is_junction():      # L4 R3-F2: 지울 대상 자신이 파일(하드 링크일 수 있음)이면 아무것도 안 건드림
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
