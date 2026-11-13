# -*- coding: utf-8 -*-
"""MP7 양성 대조 — 검사마다 일부러 넣은 잘못을 실제로 잡는지(목표 검사 키가 거짓) 본다. 모든 산출은 격리 작업 뿌리(표지 MP7_SCRATCH) 아래에만 쓴다 —
로그 · 사본 · 변조 파일 하나하나를 쓰거나 지우기 직전에 guard.checked_file 로 거른다(L4 R1 F2).

사용: python run_controls.py --cli <solidcraft-cli.exe> --blender <blender.exe> --scratch-root <격리 작업 뿌리> [--only 이름,…]
결과: `.dev/product-v3-evidence/controls.json`(대조마다 잘못 · 목표 검사 · 그 값 · 함께 거짓이 된 검사 · 종료 값)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard import allowed_roots, checked_dir, checked_file, find_root, safe_rmtree  # noqa: E402

ROOT = find_root(HERE)
PY = sys.executable
MODEL = ROOT / "models" / "armold-mks-product-v3"
EV = ROOT / ".dev" / "product-v3-evidence"
KIN = ROOT / "models" / "armold-mks-concept-v1" / "kinematics.json"
NATIVE = "kmjh-arm-product-v3.solidcraft"

BUILD_CONTROLS = [("logo_on_drum", "C2_cross_link_interference_0"), ("bar_shift", "C1d_link_frame_geometry_equals_v1_v2"),
                  ("joint_origin", "C1_joints_match_v1"), ("can_short", "C3_keepouts_100pct_inside_their_module"),
                  ("cap_color", "C5_stored_colors_match_roles"), ("owner_both", "C1c_native_structure_and_body_owners"),
                  ("drop_ring", "C1c_native_structure_and_body_owners"),
                  ("tool_holes_rotated", "C1e_every_body_matches_independent_expected_shape"),     # MP9 2 단계
                  ("tool_holes_dropped", "C1e_every_body_matches_independent_expected_shape"),
                  ("tool_hole_deeper", "C1e_every_body_matches_independent_expected_shape")]
BLENDER_CONTROLS = [("no_scale", "C7_meshes_equal_stl_mm_to_m_after_import"), ("flip_axis", "C7_joint_empties_at_v1_origins_axes"),
                    ("wrong_parent", "C7_parents_and_lock_chain"), ("mixed_material", "C7_materials_slot_index_and_base_color"),
                    ("hide_robot", "C7_renders_size_and_robot_visible"), ("nudge_vertex", "C7_meshes_equal_stl_mm_to_m_after_import"),
                    ("hide_body_white", "C7_renders_size_and_robot_visible"), ("camera_away", "C7_renders_size_and_robot_visible"),
                    ("flip_winding", "C7_triangles_and_winding_equal_stl")]
VERIFY_CONTROLS = [("blend_move_body", "C7v_blend_bodies_equal_stl_points"), ("glb_move_body", "C7v_glb_every_body_equals_stl_points_with_brand_color"),
                   ("blend_face_material", "C7v_blend_materials_slots_face_index_colors"),
                   ("blend_flip_winding", "C7v_blend_triangles_and_winding_equal_stl"),
                   ("glb_shuffle_faces", "C7v_glb_every_body_equals_stl_points_with_brand_color"), ("glb_extra_mesh", "C7v_glb_mesh_list_fixed"),
                   ("blend_degenerate_face", "C7v_blend_triangles_and_winding_equal_stl"),
                   ("glb_sliver_face", "C7v_glb_every_body_equals_stl_points_with_brand_color")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--blender", required=True, type=Path)
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    sr = a.scratch_root
    allowed_roots(ROOT, sr)                          # 표지 · git 밖 · 저장소와 겹치지 않음을 여기서 확인
    work = checked_dir(Path(sr) / "controls", ROOT, sr)
    work.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    out = {"scratch": str(work), "rows": []}

    def want(n):
        return not only or n in only

    def D(p):
        q = checked_dir(p, ROOT, sr)
        q.mkdir(parents=True, exist_ok=True)
        return q

    def F_(p):
        return checked_file(p, ROOT, sr)

    def rmtree_force(p):
        """사본 폴더 지우기 — guard.safe_rmtree: 트리 안 모든 폴더 · 파일을 먼저 가드(링크 · 정션 · 하드 링크면 아무것도 안 지우고 멈춤)한 뒤
        읽기 전용 속성을 풀고 지운다(v2 의 j2-split/parts 처럼 속성이 복사돼 온 사본)."""
        safe_rmtree(p, ROOT, sr)

    def run(argv, log):
        p = subprocess.run([str(x) for x in argv], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
        D(Path(log).parent)
        F_(log).write_text(p.stdout + "\n---- stderr ----\n" + p.stderr, encoding="utf-8")
        return p.returncode

    def checks_of(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))["checks"] if Path(path).exists() else None

    def row(name, mistake, target, checks, rc, extra_targets=()):
        caught = bool(checks) and checks.get(target) is False and all(checks.get(t) is False for t in extra_targets)
        return {"control": name, "mistake": mistake, "target_check": target, "extra_targets": list(extra_targets),
                "target_value": checks.get(target) if checks else None, "caught": caught,
                "also_false": sorted(k for k, v in (checks or {}).items() if v is False and k != target), "exit_code": rc}

    def copy_model(dst):
        """정상 모델의 사본(블렌더 제외) + 정상 검사의 저장 결과(간섭 · 평가 · 출처) — parse-only 대조용."""
        checked_dir(dst, ROOT, sr)
        if dst.exists():
            rmtree_force(dst)
        shutil.copytree(MODEL, dst, ignore=shutil.ignore_patterns("blender"))
        ev = dst.parent / (dst.name + "-check")
        if ev.exists():
            rmtree_force(ev)
        D(ev)
        for f in ("check-result.json", "check-provenance.json", "eval-now.json", "check-commands.json"):
            shutil.copy2(EV / "check" / f, F_(ev / f))
        return ev

    def validate(m, ev, log, extra=()):
        return run([PY, HERE / "validate_product.py", "--cli", a.cli, "--model", m, "--evidence", ev, "--scratch-root", sr, *extra], log)

    def rewrite_native(m, fn):
        """사본 native(zip)의 document.json 을 fn 으로 바꿔 다시 쓴다."""
        nat = F_(m / NATIVE)
        with zipfile.ZipFile(nat) as z:
            items = [(i, z.read(i.filename)) for i in z.infolist()]
        doc = json.loads(dict((i.filename, b) for i, b in items)["document.json"])
        fn(doc)
        tmp = F_(m / (NATIVE + ".tmp"))
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for i, b in items:
                z.writestr(i.filename, json.dumps(doc).encode("utf-8") if i.filename == "document.json" else b)
        os.replace(tmp, nat)

    # 1) 생성기 대조 — 틀린 모델을 작업 뿌리에 만들고 검사기 전체(간섭 · 평가를 새로)를 돌린다
    from v3geom import CONTROLS
    for name, target in BUILD_CONTROLS:
        if not want(name):
            continue
        m, e = work / name / "model", work / name / "build"
        rc_b = run([PY, HERE / "build_product.py", "--cli", a.cli, "--out", m, "--evidence", e, "--scratch-root", sr, "--control", name,
                    "--no-snapshots"], work / name / "build.log")
        rc = validate(m, work / name / "check", work / name / "validate.log", ["--build-evidence", e]) if rc_b == 0 else None
        extra = ("C1e_every_body_matches_independent_expected_shape",) if name == "drop_ring" else ()
        out["rows"].append({**row(name, CONTROLS[name], target, checks_of(m / "validation.json") if rc_b == 0 else None, rc, extra), "build_exit_code": rc_b})

    # 2) 보호 폴더 — 사본 변조(대조 모드 · 별도 키) · 정상 모드에서 좁힌 기준선
    before = json.loads((EV / "protected-snapshot-before.json").read_text(encoding="utf-8"))
    for name, how in (("protected_byte", "v2 산출 README 한 바이트"), ("protected_added", "v2 생성기 폴더에 새 파일"),
                      ("protected_removed", "v2 J2 분할 STL 하나 삭제")):
        if not want(name):
            continue
        pr = work / name / "protected"
        if pr.exists():
            rmtree_force(pr)
        D(pr)
        for rel in before["roots"]:
            shutil.copytree(ROOT / rel, pr / rel, symlinks=True)
        if name == "protected_byte":
            f = F_(pr / "models/armold-mks-product-v2/README.md")
            b = bytearray(f.read_bytes())
            b[10] ^= 0x01
            f.write_bytes(bytes(b))
        elif name == "protected_added":
            F_(pr / "src/cad/armold-mks-product-v2/extra.txt").write_text("x", encoding="utf-8")
        else:
            F_(next((pr / "models/armold-mks-product-v2/j2-split/parts").glob("*.stl"))).unlink()
        m = work / name / "model"
        ev = copy_model(m)
        rc = validate(m, ev, work / name / "validate.log", ["--protected-root", pr, "--parse-only"])
        out["rows"].append(row(name, how + " (보호 폴더 사본 · 대조 모드)", "C4_CONTROL_copy_equal_start_snapshot", checks_of(m / "validation.json"), rc))
    if want("protected_baseline_narrow"):
        name = "protected_baseline_narrow"
        D(work / name)
        nb = F_(work / name / "narrow-baseline.json")
        keep = "models/armold-mks-concept-v1/"
        nb.write_text(json.dumps({**before, "roots": ["models/armold-mks-concept-v1"],
                                  "files": {k: v for k, v in before["files"].items() if k.startswith(keep)}}), encoding="utf-8")
        m = work / name / "model"
        ev = copy_model(m)
        rc = validate(m, ev, work / name / "validate.log", ["--snapshot", nb, "--parse-only"])
        out["rows"].append(row(name, "기준선을 v1 한 폴더로 좁힘(정상 모드)", "C4_protected_folders_equal_start_snapshot", checks_of(m / "validation.json"), rc))

    # 3) 메시 · 평가 · 간섭 기록 · native 변조 — 사본 모델(parse-only: 저장 결과가 지금 파일의 것인지까지 본다)
    import numpy as np
    import trimesh
    import validate_product as vp
    p1 = json.loads((ROOT / "models/armold-mks-concept-v1/parameters.json").read_text(encoding="utf-8"))
    fk = vp.fk_from_v1(p1, json.loads(KIN.read_text(encoding="utf-8")))
    copy_controls = [
        ("mesh_box", "LINK2_LOGO_K.stl 을 그 바운딩 상자로", "C6_one_faithful_mesh_per_body"),
        ("mesh_open", "LINK3_FOREARM_BAR.stl 의 면 하나 지움", "C6_one_faithful_mesh_per_body"),
        ("mesh_local_chamfer", "LINK2_UPPER_BAR.stl 가운데 2 mm 에 모따기 면을 1.5 mm 파낸 홈(닫힌 메시)", "C1e_every_body_matches_independent_expected_shape"),
        ("eval_shift", "검사기 평가 기록(eval-now.json)의 LINK2_UPPER_BAR 상자 · 무게중심을 0.04 mm 옮김(STL · native 그대로)", "C6_one_faithful_mesh_per_body"),
        ("native_doc_joint", "native 문서의 J3 관절 양쪽 snap 을 x 로 1 mm(저장된 간섭 · 평가 기록 그대로)", "C1_native_document_joints_match_v1"),
        ("native_logo_extrude", "native 문서의 LINK2_LOGO_K 밀기 길이 0.8 → 1.6 mm(STL · 기록 그대로)", "C0_outputs_and_evidence_bound_to_current_native"),
        ("check_no_unchecked_key", "간섭 기록에서 unchecked 키를 지움", "C2_interference_complete"),
        ("check_pairs_not_checked", "간섭 기록의 pairs_not_checked = 1", "C2_interference_complete"),
        ("check_truncated", "간섭 기록의 truncated = true · budget_exceeded = true", "C2_interference_complete"),
    ]
    for name, how, target in copy_controls:
        if not want(name):
            continue
        m = work / name / "model"
        ev = copy_model(m)
        if name == "mesh_box":
            f = F_(m / "meshes" / "LINK2_LOGO_K.stl")
            k = trimesh.load_mesh(f)
            trimesh.creation.box(bounds=k.bounds).export(f)
        elif name == "mesh_open":
            f = F_(m / "meshes" / "LINK3_FOREARM_BAR.stl")
            b = trimesh.load_mesh(f)
            b.update_faces(np.arange(1, len(b.faces)))
            b.export(f)
        elif name == "mesh_local_chamfer":
            f = F_(m / "meshes" / "LINK2_UPPER_BAR.stl")
            b = trimesh.load_mesh(f)
            Rl, Ol = fk[1]["R_child"], fk[1]["origin"]
            corner = np.array([83.0, 40 + 22 - 4, 22 - 4])                     # 모따기 면(반폭 22 · 모따기 8)의 가운데
            nrm = np.array([0, 1, 1]) / np.sqrt(2)
            ex = np.array([1.0, 0, 0])
            box = trimesh.creation.box(extents=[2.0, 12.0, 3.0])
            T = np.eye(4)
            T[:3, :3] = Rl @ np.column_stack([ex, np.cross(nrm, ex), nrm])
            T[:3, 3] = Ol + Rl @ corner
            box.apply_transform(T)
            cut = trimesh.boolean.difference([b, box], engine="manifold")
            cut.export(f)
            out.setdefault("notes", {})["mesh_local_chamfer"] = {"volume_rel": float(abs(cut.volume - b.volume) / b.volume), "watertight": bool(cut.is_watertight)}
        elif name == "eval_shift":
            f = F_(ev / "eval-now.json")
            d = json.loads(f.read_text(encoding="utf-8"))
            x2 = fk[1]["R_child"][:, 0] * 0.04
            for bb in d["bodies"]:
                if bb["name"] == "LINK2_UPPER_BAR":
                    bb["center_of_mass"] = (np.asarray(bb["center_of_mass"]) + x2).tolist()
                    bb["bbox"] = {"min": (np.asarray(bb["bbox"]["min"]) + x2).tolist(), "max": (np.asarray(bb["bbox"]["max"]) + x2).tolist()}
            f.write_text(json.dumps(d), encoding="utf-8")
        elif name == "native_doc_joint":
            def fn(doc):
                j = doc["assembly"]["joints"][2]
                j["a"]["snap"]["point"][0] += 1.0
                j["b"]["snap"]["origin"][0] += 1.0
            rewrite_native(m, fn)
        elif name == "native_logo_extrude":
            def fn(doc):
                hit = [f_ for f_ in doc["features"] if f_.get("name") == "LINK2_LOGO_K_EXTRUDE"]
                assert len(hit) == 1
                hit[0]["extent"]["distance"] = "1.6"
            rewrite_native(m, fn)
        else:
            f = F_(ev / "check-result.json")
            d = json.loads(f.read_text(encoding="utf-8"))
            res = d if isinstance(d, list) else d.get("results", [])
            for r in res:
                for body in (r, r.get("result") if isinstance(r, dict) else None):
                    if isinstance(body, dict) and "interferences" in body:
                        if name == "check_no_unchecked_key":
                            body.pop("unchecked", None)
                        elif name == "check_pairs_not_checked":
                            body["pairs_not_checked"] = 1
                        else:
                            body["truncated"] = True
                            body["budget_exceeded"] = True
            f.write_text(json.dumps(d), encoding="utf-8")
        rc = validate(m, ev, work / name / "validate.log", ["--parse-only"])
        out["rows"].append(row(name, how, target, checks_of(m / "validation.json"), rc))

    # 4) 쓰기 가드 — 가드 함수만 꾸민 경로로(생성기 · 검사기의 main 을 실 저장소에 겨누지 않는다)
    if want("guard"):
        g = []
        gd = D(work / "guard")
        jtarget = D(gd / "target")
        okdir = D(gd / "out")
        junctions = [gd / "junction", okdir / "meshes"]
        for j in junctions:
            if not os.path.lexists(j):
                subprocess.run(["cmd", "/c", "mklink", "/J", str(j), str(jtarget)], capture_output=True, check=True)
        nomark = D(gd / "nomarker")
        hl, sl = okdir / "hardlink.log", okdir / "symlink.log"
        for old in (hl, sl):                       # 지난 실행의 링크 이름만 지운다(대상 파일은 작업 뿌리 안 · 그대로) — 부모는 가드
            checked_dir(old.parent, ROOT, sr)
            if os.path.lexists(old):
                os.unlink(old)
        hl_src = F_(jtarget / "plain.txt")
        hl_src.write_text("x", encoding="utf-8")
        os.link(hl_src, hl)
        try:
            os.symlink(hl_src, sl)
            sl_made = True
        except OSError:
            sl_made = False
        copy_root = next((p for p in (Path(r"C:\tools\mp7-l4r1"), Path(r"C:\tools\mp7-l2r2")) if (p / "models" / "armold-mks-concept-v1").is_dir()), None)
        cases = [("v2 산출 폴더", ROOT / "models/armold-mks-product-v2/x", ROOT, sr, False),
                 ("v2 생성기 폴더", ROOT / "src/cad/armold-mks-product-v2", ROOT, sr, False),
                 ("v1 개념 폴더", ROOT / "models/armold-mks-concept-v1/meshes", ROOT, sr, False),
                 ("저장소 루트", ROOT, ROOT, sr, False), ("models(보호 폴더의 위)", ROOT / "models", ROOT, sr, False),
                 ("대소문자 다른 v2 경로", Path(str(ROOT / "models/ARMOLD-MKS-PRODUCT-V2/x")), ROOT, sr, False),
                 ("상대 경로로 올라가 v2", ROOT / "models/armold-mks-product-v3/../armold-mks-product-v2", ROOT, sr, False),
                 ("작업 뿌리의 정션 안", gd / "junction" / "sub", ROOT, sr, False),
                 ("허용 폴더의 자식 정션(meshes)", okdir / "meshes", ROOT, sr, False),
                 ("저장소 안을 작업 뿌리로", ROOT / "tmp-scratch" / "x", ROOT, ROOT / "tmp-scratch", False),
                 ("실 저장소를 작업 뿌리로(저장소 기준)", ROOT / "models/armold-mks-product-v2/x", ROOT, ROOT, False),
                 ("표지 없는 작업 뿌리", nomark / "x", ROOT, nomark, False),
                 ("C:\\projects 를 작업 뿌리로", Path(r"C:\projects\robot-arm-lab\models\armold-mks-product-v2\x"), ROOT, Path(r"C:\projects"), False),
                 ("v3 산출(허용)", ROOT / "models/armold-mks-product-v3/meshes", ROOT, sr, True),
                 ("v3 근거(허용)", ROOT / ".dev/product-v3-evidence/check", ROOT, sr, True),
                 ("작업 뿌리(허용)", okdir / "ok", ROOT, sr, True)]
        if copy_root is not None:
            cases.append(("사본 기준에서 실 저장소를 작업 뿌리로(L2 R2-02)", ROOT / "models/armold-mks-product-v2/x", copy_root, ROOT, False))
        for label, path, rt, s, allowed in cases:
            try:
                checked_dir(path, rt, s)
                got = True
            except SystemExit:
                got = False
            g.append({"case": label, "path": str(path), "root": str(rt), "scratch": str(s), "want_allowed": allowed, "allowed": got, "ok": got == allowed})
        files = [("스냅숏 출력을 v2 로(checked_file)", ROOT / "models/armold-mks-product-v2/snap.json", False),
                 ("하드 링크 로그 파일(L4 R1 F2)", hl, False),
                 ("새 로그 파일(허용)", okdir / "new.log", True),
                 ("스냅숏 출력을 v3 근거로(허용)", ROOT / ".dev/product-v3-evidence/x.json", True)]
        if sl_made:
            files.append(("심볼릭 링크 로그 파일", sl, False))
        for label, path, allowed in files:
            try:
                checked_file(path, ROOT, sr)
                got = True
            except SystemExit:
                got = False
            g.append({"case": label, "path": str(path), "want_allowed": allowed, "allowed": got, "ok": got == allowed})
        # safe_rmtree: 하드 링크 · 정션이 든 트리는 아무것도 안 지우고 거부 · 보통 트리는 지움(작업 뿌리 안 모형)
        for label, kind in (("하드 링크가 든 트리 지우기(L4 R2-F2)", "hardlink"), ("정션이 든 트리 지우기", "junction"), ("보통 트리 지우기(허용)", "plain")):
            tr = D(gd / f"tree-{kind}")
            D(tr / "sub")
            F_(tr / "sub" / "a.txt").write_text("a", encoding="utf-8")
            if kind == "hardlink":
                if os.path.lexists(tr / "sub" / "h.txt"):
                    os.unlink(tr / "sub" / "h.txt")
                os.link(hl_src, tr / "sub" / "h.txt")
            elif kind == "junction" and not os.path.lexists(tr / "j"):
                subprocess.run(["cmd", "/c", "mklink", "/J", str(tr / "j"), str(jtarget)], capture_output=True, check=True)
            try:
                safe_rmtree(tr, ROOT, sr)
                got = True
            except SystemExit:
                got = False
            untouched = (tr / "sub" / "a.txt").exists() if not got else None
            g.append({"case": label, "path": str(tr), "want_allowed": kind == "plain", "allowed": got, "nothing_deleted_when_refused": untouched,
                      "ok": got == (kind == "plain") and (got or untouched)})
            if not got:                             # 거부된 모형 트리는 링크 이름부터 손으로 걷는다(대상은 작업 뿌리 안)
                for q in (tr / "sub" / "h.txt", ):
                    if os.path.lexists(q):
                        os.unlink(q)
                if os.path.lexists(tr / "j"):
                    os.rmdir(tr / "j")
                safe_rmtree(tr, ROOT, sr)
        # L4 R3-F2: 지울 대상 자리에 폴더 대신 **하드 링크 파일**(대상 = 읽기 전용 모형 「보호」 파일) — 거부 · 속성 · 바이트 · 이름 그대로
        import stat
        prot_like = jtarget / "protected-like.bin"
        checked_dir(okdir, ROOT, sr)
        if prot_like.exists():
            os.chmod(prot_like, stat.S_IWRITE)            # 읽기 전용 속성은 하드 링크끼리 공유 — 풀어야 이름을 지울 수 있다(작업 뿌리 안 모형)
        if os.path.lexists(okdir / "model-top"):
            os.unlink(okdir / "model-top")
        F_(prot_like).write_bytes(b"protected bytes")
        os.chmod(prot_like, stat.S_IREAD)
        os.link(prot_like, okdir / "model-top")
        try:
            safe_rmtree(okdir / "model-top", ROOT, sr)
            got = True
        except SystemExit:
            got = False
        st = os.stat(prot_like)
        kept = (not (st.st_mode & stat.S_IWRITE)) and prot_like.read_bytes() == b"protected bytes" and os.path.lexists(okdir / "model-top")
        g.append({"case": "지울 대상 자신이 하드 링크 파일(L4 R3-F2)", "path": str(okdir / "model-top"), "want_allowed": False, "allowed": got,
                  "readonly_bytes_and_name_kept": kept, "ok": (not got) and kept})
        os.chmod(prot_like, stat.S_IWRITE)
        os.unlink(okdir / "model-top")
        for j in junctions:
            checked_dir(j.parent, ROOT, sr)
            os.rmdir(j)            # 정션만 지운다(대상 폴더는 그대로)
        out["guard"] = g
        out["guard_symlink_file_case"] = "run" if sl_made else "NOT_RUN — 이 계정은 파일 심볼릭 링크를 만들 권한이 없음(하드 링크 · 정션 경우로 대신)"
        out["rows"].append({"control": "guard", "mistake": f"가드 함수에 거부해야 할 경로 {sum(1 for r in g if not r['want_allowed'])} · 허용 경로 "
                                                           f"{sum(1 for r in g if r['want_allowed'])}", "target_check": "guard.checked_dir / checked_file",
                            "caught": all(r["ok"] for r in g), "cases": len(g)})

    # 5) 블렌더 장면 대조 — 정상 모델(저장소)의 메시로 틀린 장면을 작업 뿌리에
    for name, target in BLENDER_CONTROLS:
        if not want(name):
            continue
        o = work / name / "blender"
        rc = run([a.blender, "--background", "--factory-startup", "--python", HERE / "blender_scene.py", "--", "--model", MODEL, "--kin", KIN,
                  "--out", o, "--scratch-root", sr, "--control", name, "--samples", "4", "--width", "320", "--height", "240"], work / name / "blender.log")
        out["rows"].append(row(name, f"블렌더 --control {name}", target, checks_of(o / "scene-report.json"), rc))

    # 6) 저장물 대조 — 정상 .blend · GLB 의 사본(작업 뿌리)을 다시 열어 바꾼 뒤 검사
    for name, target in VERIFY_CONTROLS:
        if not want(name):
            continue
        o = work / name / "blender"
        if o.exists():
            rmtree_force(o)
        D(o)
        for f in ("kmjh-arm-v3.blend", "kmjh-arm-v3.glb"):
            shutil.copy2(MODEL / "blender" / f, F_(o / f))
        rc = run([a.blender, "--background", "--factory-startup", "--python", HERE / "blender_verify.py", "--", "--blender-dir", o, "--model", MODEL,
                  "--kin", KIN, "--scratch-root", sr, "--control", name], work / name / "verify.log")
        out["rows"].append(row(name, f"블렌더 저장물 --control {name}", target, checks_of(o / f"verify-report-{name}.json"), rc))

    prev = json.loads((EV / "controls.json").read_text(encoding="utf-8")) if only and (EV / "controls.json").exists() else None
    if prev:
        done = {x["control"] for x in out["rows"]}
        out["rows"] = [r for r in prev["rows"] if r["control"] not in done] + out["rows"]
        out["guard"] = out.get("guard") or prev.get("guard")
        out["notes"] = out.get("notes") or prev.get("notes")
    out["all_caught"] = all(r["caught"] for r in out["rows"])
    F_(EV / "controls.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in out["rows"]:
        print(("CAUGHT " if r["caught"] else "MISSED ") + r["control"], r.get("target_check"), r.get("also_false", ""))
    print("ALL CAUGHT" if out["all_caught"] else "SOME MISSED")


if __name__ == "__main__":
    main()
