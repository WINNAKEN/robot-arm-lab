# -*- coding: utf-8 -*-
"""MP7 동작 영상 도구의 양성 대조 — 일부러 넣은 잘못을 목표 관문이 잡는지, 정상 입력은 통과하는지(2026-10-27 비작성자 검토 1 ~ 5 회 처분 뒤).

사용: python run_motion_controls.py --scratch-root <작업 뿌리> [--blender <blender.exe>]
- 모든 쓰기는 <작업 뿌리>/motion-controls 아래(가드)와 결과 파일 .dev/product-v3-evidence/motion-controls.json(가드) 뿐이다(파이썬 바이트코드 캐시는 예외).
- 대조하지 못한 갈래는 결과 파일의 not_covered 에 적는다.
- motion_encode 는 쓰기 전 검사 함수 preflight() 만 부른다 — 산출 경로가 저장소로 고정이라 main() 은 부르지 않는다(가드 시험은 함수로만).
- 블렌더 대조는 작은 화면(160 × 90 · 1 샘플)과 짧은 계획(0.5 초 이동 하나 = 13 프레임 · 한 바퀴 0.25 초 = 6 프레임)으로 돌린다."""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard import checked_dir, checked_file, find_root, safe_rmtree  # noqa: E402
import motion_encode  # noqa: E402
from pose_check import FLOOR_CLEAR_MM  # noqa: E402

PY = sys.executable
ROOT = find_root(HERE)
MODEL = ROOT / "models" / "armold-mks-product-v3"
KIN = ROOT / "models" / "armold-mks-concept-v1" / "kinematics.json"
POSES = HERE / "gallery_poses.json"
PLAN = HERE / "motion_plan.json"
BLEND = MODEL / "blender" / "kmjh-arm-v3.blend"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--blender", default=r"C:\tools\Blender-5.2.3\blender-5.2.3-windows-x64\blender.exe")
    a = ap.parse_args()
    SCR = Path(a.scratch_root).resolve()
    CTL = SCR / "motion-controls"

    def F_(p):
        return checked_file(p, ROOT, SCR)

    def D_(p):
        return checked_dir(p, ROOT, SCR)

    def copy_model(dst):
        D_(dst / "meshes").mkdir(parents=True)
        shutil.copyfile(MODEL / "bodies.json", F_(dst / "bodies.json"))
        for p in (MODEL / "meshes").glob("*.stl"):
            shutil.copyfile(p, F_(dst / "meshes" / p.name))

    def path_check(model, plan, out, per_frame=8, poses=POSES):
        r = subprocess.run([PY, str(HERE / "path_check.py"), "--model", str(model), "--kin", str(KIN), "--poses", str(poses), "--plan", str(plan),
                            "--out", str(out), "--scratch-root", str(SCR), "--workers", "3", "--per-frame", str(per_frame)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")        # 작업자 3 — 큰 렌더와 함께 돌 때 8 은 메모리가 모자라 풀이 깨짐(2026-10-27)
        return json.loads(Path(out).read_text(encoding="utf-8")) if Path(out).exists() else None

    def blender(frames, video="motion", model=None, plan=None, pathc=None, blend=None, extra=(), unpinned=False, scratch=True):
        cmd = [a.blender, "--background", "--factory-startup", "--python", str(HERE / "blender_motion.py"), "--", "--video", video, "--scheme", "brand",
               "--frames", str(frames), *(("--scratch-root", str(SCR)) if scratch else ()), "--blend", str(blend or BLEND), "--model", str(model or CTL / "model-ok"),
               "--kin", str(KIN), "--poses", str(POSES), "--plan", str(plan or CTL / "plan-tiny.json"), "--path-check", str(pathc or CTL / "path-ok.json"),
               "--width", "160", "--height", "90", "--samples", "1", *extra, *(("--unpinned-blend",) if unpinned else ())]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        txt = r.stdout + r.stderr
        keys = ("MOTION_", "SystemExit", "refus", "must", "different", "landscape", "does not match", "without", "too coarse", "failed or ran",
                "turntable pose", "materials", "pinned", "did not sample", "not JSON", "world / floor")
        return txt, [ln[:300] for ln in txt.splitlines() if any(k in ln for k in keys)][-6:]

    def expect_exit(fn, *args, **kw):
        try:
            fn(*args, **kw)
        except SystemExit as e:
            return True, str(e)[:400]
        return False, "returned normally"

    blend_before = sha(BLEND)
    safe_rmtree(CTL, ROOT, SCR)
    D_(CTL).mkdir(parents=True)
    rows = []

    def row(id_, target, ok, **kw):
        rows.append({"id": id_, "target": target, "ok": bool(ok), **kw})
        print(("OK  " if ok else "BAD ") + id_, flush=True)

    # 준비: 모델 사본(같은 바이트) · 닫히지 않은 사본 · 짧은 계획 · 대조 자세 넷 · .blend 사본 열여섯
    copy_model(CTL / "model-ok")
    copy_model(CTL / "model-broken")
    p = F_(CTL / "model-broken" / "meshes" / "J2_MODULE.stl")
    b = bytearray(p.read_bytes())
    n = struct.unpack_from("<I", b, 80)[0]
    b = b[:84 + (n - 1) * 50]
    struct.pack_into("<I", b, 80, n - 1)
    p.write_bytes(bytes(b))
    tiny = json.loads(PLAN.read_text(encoding="utf-8"))
    tiny["motion"]["hold_start_s"] = 0
    tiny["motion"]["steps"] = [{"to": "home", "move_s": 0.5, "hold_s": 0}]      # 0.25 초는 샘플 사이 이동 8.9 mm 로 밀도 관문(≤ 5 mm)에 걸림
    tiny["turntable"]["seconds"] = 0.25
    F_(CTL / "plan-tiny.json").write_text(json.dumps(tiny, ensure_ascii=False, indent=1), encoding="utf-8")
    fast = json.loads(json.dumps(tiny))
    fast["motion"]["steps"][0]["move_s"] = 0.25                               # per_frame 8 이어도 샘플 사이 8.9 mm — 밀도 관문의 「이동」 쪽만
    F_(CTL / "plan-fast.json").write_text(json.dumps(fast, ensure_ascii=False, indent=1), encoding="utf-8")
    slow = json.loads(json.dumps(tiny))
    slow["motion"]["steps"][0]["move_s"] = 1.0                                # per_frame 4 여도 샘플 사이 약 4.4 mm — 밀도 관문의 「per_frame」 쪽만
    F_(CTL / "plan-slow.json").write_text(json.dumps(slow, ensure_ascii=False, indent=1), encoding="utf-8")
    offgrid = json.loads(json.dumps(tiny))
    offgrid["motion"]["steps"][0]["move_s"] = 0.51                            # 이동 끝이 프레임 격자에 안 맞음 — 프레임 자세가 샘플에 없음
    F_(CTL / "plan-offgrid.json").write_text(json.dumps(offgrid, ensure_ascii=False, indent=1), encoding="utf-8")
    # path_check 판정 갈래마다 그 갈래에만 걸리는 자세(2026-10-27 pose_check.evaluate 로 고름 — 겹침 · 근접 · 바닥 · 관절 범위 중 하나만 거짓)
    hit = {"overlap": ("ctl-elbow-140", [0, -90, 140, 0, 0, 0]),       # 이웃 링크 2 · 3 이 겹침(720 mm³) · 이웃 아닌 근접 없음 · 바닥 26 mm
           "near": ("ctl-wrist-113", [0, -90, 90, 0, 113, 0]),          # 링크 3 · 5 꼭짓점 1.19 mm(< 2) · 겹침 0.007 mm³(< 0.05) · 바닥 114 mm
           "floor": ("ctl-dive", [0, 0, 90, 0, 0, 0]),                  # 바닥 아래 216 mm · 겹침 0.006 mm³ · 근접 없음
           "limit": ("ctl-j1-175", [175, -90, 90, 0, 0, 0])}            # J1 175 도(> 170) · ㄱ 자 대기를 돌린 것뿐 — 겹침 · 근접 · 바닥 정상
    pz = json.loads(POSES.read_text(encoding="utf-8"))
    pz["poses"] += [{"name": n, "q_deg": q} for n, q in hit.values()]
    F_(CTL / "poses-ctl.json").write_text(json.dumps(pz, ensure_ascii=False, indent=1), encoding="utf-8")
    for kind, (n, _q) in hit.items():
        hp = json.loads(json.dumps(tiny))
        hp["motion"]["start"] = "home"                                    # ㄱ 자 대기에서 출발 — 중간 자세가 다른 갈래에 걸리지 않게
        hp["motion"]["steps"][0]["to"] = n
        F_(CTL / f"plan-hit-{kind}.json").write_text(json.dumps(hp, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([a.blender, "--background", "--factory-startup", "--python", str(HERE / "motion_control_blends.py"), "--", str(BLEND), str(CTL), str(SCR)],
                   capture_output=True, text=True, check=True)

    # A — path_check
    rep = path_check(CTL / "model-ok", CTL / "plan-tiny.json", F_(CTL / "path-ok.json"))
    row("A0_path_check_baseline_passes", "path_check all_ok", rep and rep["all_ok"] and rep["turntable"]["ok"] and rep["inputs_unchanged_during_check"])
    rep = path_check(CTL / "model-broken", CTL / "plan-tiny.json", F_(CTL / "path-broken.json"))
    row("A1_open_mesh_fails_path_check", "path_check mesh_all_manifold", rep is not None and not rep["all_ok"] and rep["mesh_all_manifold"] is False)
    rep = path_check(CTL / "model-ok", CTL / "plan-slow.json", F_(CTL / "path-coarse.json"), per_frame=4)
    row("A2_coarse_path_check_written", "path_check per_frame 4 · step <= 5 mm", rep is not None and rep["all_ok"] and rep["per_frame"] == 4
        and rep["max_vertex_step_between_samples_mm"] <= 5.0, step=rep and rep["max_vertex_step_between_samples_mm"])
    pc = json.loads((CTL / "path-ok.json").read_text(encoding="utf-8"))
    pc.pop("turntable")
    F_(CTL / "path-no-turntable.json").write_text(json.dumps(pc), encoding="utf-8")
    rep = path_check(CTL / "model-ok", CTL / "plan-fast.json", F_(CTL / "path-fast.json"))
    row("A3_fast_path_check_written", "path_check per_frame 8 · step > 5 mm", rep is not None and rep["all_ok"] and rep["per_frame"] == 8
        and rep["max_vertex_step_between_samples_mm"] > 5.0, step=rep and rep["max_vertex_step_between_samples_mm"])
    rep = path_check(CTL / "model-ok", CTL / "plan-offgrid.json", F_(CTL / "path-offgrid.json"))
    row("A4_offgrid_path_check_written", "path_check off-grid plan", rep is not None and rep["all_ok"] and rep["max_vertex_step_between_samples_mm"] <= 5.0)
    # A5 ~ A8 — path_check 판정 갈래를 하나씩: 실패한 샘플마다 (겹침, 근접, 바닥, 관절 범위) 중 그 갈래 하나만 참이어야(검토 5 회)
    want = {"overlap": (True, False, False, False), "near": (False, True, False, False), "floor": (False, False, True, False), "limit": (False, False, False, True)}
    for tag, kind in (("A5_overlap_only_path_fails", "overlap"), ("A6_near_only_path_fails", "near"), ("A7_floor_only_path_fails", "floor"),
                      ("A8_limit_only_path_fails", "limit")):
        rep = path_check(CTL / "model-ok", CTL / f"plan-hit-{kind}.json", F_(CTL / f"path-hit-{kind}.json"), poses=CTL / "poses-ctl.json")
        bad = [r for r in rep["rows"] if not r["ok"]] if rep else []
        why = {(bool(r["overlaps_over_limit"]), bool(r["near_under_limit"]), r["moving_min_z_mm"] < FLOOR_CLEAR_MM, not r["within_limits"]) for r in bad}
        row(tag, f"path_check {kind} judgement (alone)", rep is not None and not rep["all_ok"] and rep["mesh_all_manifold"] and rep["inputs_unchanged_during_check"]
            and rep["turntable"]["ok"] and rep["rows"][0]["ok"] and not rep["rows"][-1]["ok"] and why == {want[kind]},
            failed=len(bad), samples=rep and rep["samples"], why=sorted(list(w) for w in why))

    # P — 장면 고정: 바꾼 것 없이 다시 저장한 .blend(sha 만 다름)는 고정 없이는 거부 · 고정을 풀면 렌더되지만 기록이 M_blend_pinned 거짓
    txt, tail = blender(CTL / "frames-P1", blend=CTL / "blend-resaved.blend")
    row("P1_unpinned_blend_refused", "blender pin gate", "not the pinned, verified scene" in txt and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-P2", blend=CTL / "blend-resaved.blend", unpinned=True)
    rp = json.loads((CTL / "frames-P2" / "frames-report.json").read_text(encoding="utf-8")) if (CTL / "frames-P2" / "frames-report.json").exists() else {}
    row("P2_unpinned_run_marked_not_pinned", "blender report M_blend_pinned", "MOTION_INCOMPLETE_OR_FAILED" in txt and rp.get("checks", {}).get("M_blend_pinned") is False
        and all(v for k, v in rp.get("checks", {}).items() if k != "M_blend_pinned"), tail=tail)
    # R — 프레임 줄 검사: 장면 관문은 지나지만(바닥 위치는 안 봄) 바닥이 로봇을 가리는 사본 → 프레임마다 BAD · 보고서 M_every_frame_ok 거짓
    txt, tail = blender(CTL / "frames-R1", blend=CTL / "blend-floor-raised.blend", unpinned=True)
    rr = json.loads((CTL / "frames-R1" / "frames-report.json").read_text(encoding="utf-8")) if (CTL / "frames-R1" / "frames-report.json").exists() else {}
    lr = [json.loads(ln) for ln in (CTL / "frames-R1" / "frames.jsonl").read_text(encoding="utf-8").splitlines()] if (CTL / "frames-R1" / "frames.jsonl").exists() else []
    only_vis = len(lr) == 13 and all(r["pose_err_m"] <= 2e-6 and r["robot_box_in_frame"] and r["robot_ray_fraction"] < 0.05 and not r["ok"] for r in lr)
    row("R1_occluded_frames_marked_bad", "blender per-frame row check (visibility)", txt.count("BAD") == 13 and "MOTION_INCOMPLETE_OR_FAILED" in txt
        and only_vis and rr.get("checks", {}).get("M_every_frame_ok") is False and rr.get("checks", {}).get("M_scene_equals_stl_and_bodies") is True,
        frames_bad=txt.count("BAD"), bad_only_from_visibility=only_vis, max_ray_fraction=max((r["robot_ray_fraction"] for r in lr), default=None), tail=tail)

    # B / K — blender_motion 의 검사 기록 관문
    txt, tail = blender(CTL / "frames-B1", model=CTL / "model-broken", pathc=CTL / "path-ok.json")
    row("B1_stale_path_check_refused", "blender inputs gate", "failed or ran on different inputs" in txt and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-B2", model=CTL / "model-broken", pathc=CTL / "path-broken.json")
    row("B2_failed_path_check_refused", "blender all_ok gate", "failed or ran on different inputs" in txt and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-B3", plan=CTL / "plan-slow.json", pathc=CTL / "path-coarse.json")
    row("B3_coarse_per_frame_refused", "blender density gate (per_frame)", "too coarse: per_frame 4 < 8" in txt and "vertex step" not in txt
        and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-B4", plan=CTL / "plan-fast.json", pathc=CTL / "path-fast.json")
    row("B4_large_vertex_step_refused", "blender density gate (vertex step)", "too coarse: vertex step" in txt and "per_frame" not in txt.split("too coarse")[-1][:40]
        and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-B5", plan=CTL / "plan-offgrid.json", pathc=CTL / "path-offgrid.json")
    row("B5_frames_not_sampled_refused", "blender frames-in-samples gate", "did not sample" in txt and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-K1", video="turntable", pathc=CTL / "path-no-turntable.json")
    row("K1_turntable_without_checked_pose_refused", "blender turntable gate", "turntable pose" in txt and "MOTION_FRAME" not in txt, tail=tail)
    pc = json.loads((CTL / "path-ok.json").read_text(encoding="utf-8"))
    pc["rows"] = pc["rows"][:-1]                                              # 판정 · 입력 · 밀도는 그대로 · 샘플 줄만 계획과 어긋남(손댄 기록)
    F_(CTL / "path-rows-edited.json").write_text(json.dumps(pc), encoding="utf-8")
    txt, tail = blender(CTL / "frames-B6", pathc=CTL / "path-rows-edited.json")
    row("B6_path_rows_not_plan_refused", "blender path rows gate", "checked a different plan / pose file" in txt and "MOTION_FRAME" not in txt, tail=tail)

    # C — 장면 관문(고정을 푼 .blend 사본 열넷 — 고정 위의 이중 방어) · 거부된 실행은 프레임 폴더 · meta 를 남기지 않음
    for name, needle in (("nudged", "J2_MODULE"), ("flipped", "LINK2_UPPER_BAR"), ("modifier", "J2_MODULE"), ("hidden", "BASE_COLUMN"),
                         ("collection-hidden", "BASE_COLUMN"), ("camera-ray-off", "BASE_COLUMN"), ("extra-object", "'EMPTY': 8"),
                         ("material-alpha", "'alpha'"), ("material-linked", "base color linked"), ("layer-holdout", "J2_MODULE"),
                         ("shadow-catcher", "BASE_COLUMN"), ("camera-shift", "camera_perspective_no_shift"),
                         ("empty-instancing", "empties_no_instancing"), ("floor-modifier", "floor_plain_quad")):
        fd = CTL / f"frames-C-{name}"
        txt, tail = blender(fd, blend=CTL / f"blend-{name}.blend", unpinned=True)
        row(f"C_{name}_refused", "blender scene gate", "does not match the body STLs" in txt and needle in txt and "MOTION_FRAME" not in txt
            and not fd.exists(), tail=tail)

    # G / D — 화면 방향 · 기록 관문
    txt, tail = blender(CTL / "frames-G", extra=("--width", "90", "--height", "160"))
    row("G_portrait_refused", "blender landscape gate", "landscape frames only" in txt and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-G2", scratch=False)
    row("G2_no_scratch_root_refused", "blender frames location gate", "frames go under --scratch-root only (the MP4" in txt and "MOTION_FRAME" not in txt
        and not (CTL / "frames-G2").exists(), tail=tail)
    D_(CTL / "frames-D").mkdir()
    F_(CTL / "frames-D" / "frames.jsonl").write_text('{"frame": 0}\n', encoding="utf-8")
    txt, tail = blender(CTL / "frames-D")
    row("D_log_without_meta_refused", "blender resume gate", "without frames-meta.json" in txt and "MOTION_FRAME" not in txt, tail=tail)

    # H — 기준선 · 이어 하기 · 설정 바꿈 · 끊긴 마지막 기록 줄
    txt, tail = blender(CTL / "frames-H")
    row("H0_baseline_renders_all", "blender motion", "MOTION_DONE" in txt and txt.count("MOTION_FRAME") == 13, frames=txt.count("MOTION_FRAME"), tail=tail)
    txt, tail = blender(CTL / "frames-H")
    row("H1_resume_skips_matching_frames", "blender resume", "MOTION_DONE" in txt and txt.count("MOTION_FRAME") == 0, frames=txt.count("MOTION_FRAME"))
    txt, tail = blender(CTL / "frames-H", extra=("--samples", "2"))
    row("H2_changed_settings_refused", "blender meta gate", "different inputs or settings" in txt and "MOTION_FRAME" not in txt, tail=tail)
    shutil.copytree(CTL / "frames-H", D_(CTL / "frames-H3"))
    lg = F_(CTL / "frames-H3" / "frames.jsonl")
    lines = lg.read_text(encoding="utf-8").splitlines()
    with open(lg, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines[:-1]) + "\n" + lines[-1][:40] + "\n")          # 마지막 줄을 중간에서 자름
    txt, tail = blender(CTL / "frames-H3")
    lines2 = lg.read_text(encoding="utf-8").splitlines()
    row("H3_truncated_last_log_line_rerenders_one", "blender resume (log)", "MOTION_LOG_LAST_LINE_DROPPED" in txt and txt.count("MOTION_FRAME") == 1
        and "MOTION_DONE" in txt and all(json.loads(x) for x in lines2), frames=txt.count("MOTION_FRAME"), tail=tail)
    shutil.copytree(CTL / "frames-H", D_(CTL / "frames-H4"))
    lg = F_(CTL / "frames-H4" / "frames.jsonl")
    lines = lg.read_text(encoding="utf-8").splitlines()
    lines[3] = lines[3][:30]                                                   # 가운데 줄이 깨짐 → 거부
    with open(lg, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    txt, tail = blender(CTL / "frames-H4")
    row("H4_corrupt_middle_log_line_refused", "blender resume (log)", "line 4 is not JSON" in txt and "MOTION_FRAME" not in txt, tail=tail)
    txt, tail = blender(CTL / "frames-K0", video="turntable")
    row("K0_turntable_baseline_renders_all", "blender turntable", "MOTION_DONE" in txt and txt.count("MOTION_FRAME") == 6, frames=txt.count("MOTION_FRAME"), tail=tail)
    txt, tail = blender(CTL / "frames-H5", extra=("--first", "0", "--last", "2"))   # 일부만 렌더 → 보고서가 덜 됨을 표시(묶기는 검사 목록 관문에서 거부 — E10 과 같은 관문)
    ck = json.loads((CTL / "frames-H5" / "frames-report.json").read_text(encoding="utf-8")).get("checks", {}) if (CTL / "frames-H5" / "frames-report.json").exists() else {}
    row("H5_partial_render_marked_incomplete", "blender report M_all_frames_rendered", txt.count("MOTION_FRAME") == 3 and "MOTION_INCOMPLETE_OR_FAILED" in txt
        and ck.get("M_all_frames_rendered") is False and ck.get("M_every_frame_ok") is False and len(ck) == 9
        and all(v for k, v in ck.items() if k not in ("M_all_frames_rendered", "M_every_frame_ok")), frames=txt.count("MOTION_FRAME"), tail=tail)

    # E — motion_encode.preflight(쓰기 없음)
    ctl_paths = {"model": CTL / "model-ok", "kin": KIN, "poses": POSES, "plan": CTL / "plan-tiny.json", "blend": BLEND, "path_check": CTL / "path-ok.json"}
    try:
        pf = motion_encode.preflight(ROOT, CTL / "frames-H", SCR, ctl_paths)
        row("E0_preflight_baseline_passes", "preflight", pf["n"] == 13 and pf["out"] == ROOT / "models/armold-mks-product-v3/blender/motion/motion-brand.mp4")
    except SystemExit as e:
        row("E0_preflight_baseline_passes", "preflight", False, msg=str(e)[:400])
    okx, msg = expect_exit(motion_encode.preflight, ROOT, CTL / "frames-H", SCR)
    row("E1_canonical_mode_refuses_control_frames", "preflight canonical inputs + settings", okx and "different inputs, code or settings" in msg, msg=msg)
    okx, msg = expect_exit(motion_encode.preflight, ROOT, CTL / "frames-H", SCR, dict(ctl_paths, plan=PLAN))
    row("E2_stale_plan_refused", "preflight inputs", okx and "inputs (STL / bodies.json" in msg, msg=msg)
    okx, msg = expect_exit(motion_encode.preflight, ROOT, CTL / "frames-H", SCR, ctl_paths, canon_settings=True)
    row("E9_noncanonical_settings_refused", "preflight canonical settings (alone)", okx and "!= canonical" in msg and "inputs (" not in msg
        and "blend not the pinned" not in msg, msg=msg)
    okx, msg = expect_exit(motion_encode.preflight, ROOT, CTL / "frames-P2", SCR, dict(ctl_paths, blend=CTL / "blend-resaved.blend"))
    row("E10_unpinned_frames_refused_by_checks", "preflight checks gate (M_blend_pinned false)", okx and "'M_blend_pinned': False" in msg, msg=msg)
    d = D_(CTL / "frames-E-pinmeta")
    shutil.copytree(CTL / "frames-H", d)
    m = json.loads((d / "frames-meta.json").read_text(encoding="utf-8"))
    m["blend_pinned"] = False
    F_(d / "frames-meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    r = json.loads((d / "frames-report.json").read_text(encoding="utf-8"))
    r["frames_meta_sha256"] = sha(d / "frames-meta.json")                     # meta sha 관문은 지나게 — 고정 표시 관문만 남김
    F_(d / "frames-report.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    okx, msg = expect_exit(motion_encode.preflight, ROOT, d, SCR, ctl_paths)
    row("E11_meta_not_pinned_refused", "preflight pin gate (meta)", okx and "blend not the pinned scene" in msg and "'frames-meta.json'" not in msg,
        msg=msg)
    okx, msg = expect_exit(motion_encode.preflight, ROOT, SCR, SCR, ctl_paths)
    row("E3_frames_not_inside_scratch_refused", "preflight frames location", okx and "inside --scratch-root" in msg, msg=msg)
    for tag, mut, needle in (("E4_extra_frame_refused", "extra", "count mismatch"), ("E5_changed_frame_refused", "changed", "changed since render"),
                             ("E6_other_render_script_refused", "script", "blender_motion.py"), ("E7_fewer_checks_refused", "checks", "expected set")):
        d = D_(CTL / f"frames-E-{mut}")
        shutil.copytree(CTL / "frames-H", d)
        if mut == "extra":
            shutil.copyfile(d / "0000.jpg", F_(d / "0013.jpg"))
        elif mut == "changed":
            q = F_(d / "0003.jpg")
            q.write_bytes(q.read_bytes() + b"\x00")
        elif mut == "script":
            m = json.loads((d / "frames-meta.json").read_text(encoding="utf-8"))
            m["script_sha256"] = "0" * 64
            F_(d / "frames-meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        else:
            r = json.loads((d / "frames-report.json").read_text(encoding="utf-8"))
            r["checks"].pop("M_scene_equals_stl_and_bodies")
            F_(d / "frames-report.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        okx, msg = expect_exit(motion_encode.preflight, ROOT, d, SCR, ctl_paths)
        row(tag, "preflight", okx and needle in msg, msg=msg)
    names_ok = motion_encode.expected_out(ROOT, "turntable", "swap") == ROOT / "models/armold-mks-product-v3/blender/motion/turntable-swap.mp4"
    okx, msg = expect_exit(motion_encode.expected_out, ROOT, "motion", "../../kmjh-arm-v3")
    row("E8_out_name_fixed", "expected_out", names_ok and okx, msg=msg)

    # E12 ~ E19 — 묶기 전 「다른 입력 · 코드 · 설정」 관문의 갈래를 하나씩: 거부 목록이 정확히 그 항목 하나여야(검토 5 회 — 대조 없이 남은 갈래)
    def variant(tag, meta_fn=None, rep_fn=None, resync=True):
        d = D_(CTL / f"frames-{tag}")
        shutil.copytree(CTL / "frames-H", d)
        if meta_fn:
            m = json.loads((d / "frames-meta.json").read_text(encoding="utf-8"))
            meta_fn(m)
            F_(d / "frames-meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        r = json.loads((d / "frames-report.json").read_text(encoding="utf-8"))
        if rep_fn:
            rep_fn(r)
        if resync:
            r["frames_meta_sha256"] = sha(d / "frames-meta.json")             # meta sha 관문은 지나게(E15 만 일부러 어긋나게)
        F_(d / "frames-report.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return d
    resaved, zero = sha(CTL / "blend-resaved.blend"), "0" * 64
    cases = (("E12_blend_sha_stale_refused", CTL / "frames-H", dict(ctl_paths, blend=CTL / "blend-resaved.blend"), "blend_sha256"),
             ("E13_path_check_sha_stale_refused", CTL / "frames-H", dict(ctl_paths, path_check=CTL / "path-offgrid.json"), "path_check_sha256"),
             ("E14_report_blend_not_pinned_refused", variant("E14", lambda m: m.update(blend_sha256=resaved), lambda r: r.update(blend_sha256=resaved)),
              dict(ctl_paths, blend=CTL / "blend-resaved.blend"), "blend not the pinned scene (motion_scene_pin.json)"),
             ("E15_meta_sha_mismatch_refused", variant("E15", lambda m: m.update(note="x"), resync=False), ctl_paths, "frames-meta.json"),
             ("E16_guard_sha_refused", variant("E16", lambda m: m.update(guard_sha256=zero)), ctl_paths, "guard.py"),
             ("E17_stl_topology_sha_refused", variant("E17", lambda m: m.update(stl_topology_sha256=zero)), ctl_paths, "stl_topology.py"),
             ("E18_report_script_mismatch_refused", variant("E18", rep_fn=lambda r: r.update(script_sha256=zero)), ctl_paths, "render script (report vs meta)"),
             ("E19_report_settings_mismatch_refused", variant("E19", rep_fn=lambda r: r.update(samples=r["samples"] + 1)), ctl_paths, "settings (report vs meta)"))
    for tag, d, paths, item in cases:
        okx, msg = expect_exit(motion_encode.preflight, ROOT, d, SCR, paths)
        row(tag, "preflight stale gate (one branch)", okx and msg.endswith(": " + repr([item])), msg=msg)

    code = {n: sha(HERE / n) for n in ("run_motion_controls.py", "motion_control_blends.py", "blender_motion.py", "motion_encode.py", "path_check.py",
                                       "pose_check.py", "motion_path.py", "guard.py", "stl_topology.py")}
    res = {"code_sha256": code, "blend_unchanged": sha(BLEND) == blend_before, "controls": rows,
           "not_covered": [
               "동시에 파일을 바꾸는 경우 — 렌더 중 path-check · 입력 · 스크립트 · .blend 가 바뀜(M_inputs / M_path_check / M_script_unchanged_during_run · "
               "M_blend_not_modified) · path_check 중 입력이 바뀜(inputs_unchanged_during_check): 동시 쓰기가 필요해 대조하지 않음",
               "묶기 전 검사의 path-check 다시 읽기(motion_encode.preflight 의 all_ok · inputs · 밀도 · turntable) — 같은 상수(motion_path)와 sha 로 묶여 렌더 관문과 "
               "판정이 갈릴 수 없음: 대조할 길 없음",
               "장면 관문(고정 장면 위의 이중 방어) 중 대조 사본이 없는 갈래 — 뷰 레이어 수 · 사용 끔 · 컬렉션 제외 · 간접 전용 · 객체 is_holdout · 숨긴 인스턴서 · "
               "바디 instance_type · 조명 · 카메라 수 · 카메라 형식(PERSP) · shift_y · 바닥 점 수 · 모양 키 · instance_type · 배경 장면 · 재질 덮어쓰기 · 재질 슬롯 수 · "
               "슬롯이 객체에 연결 · 재질 이름 · 노드 없음 · 표면이 Principled 아님 · 볼륨 / 변위 · 바디 링크 · 역할 ≠ bodies.json · 세계 / 바닥 노드 없음 · "
               "메시 수 · 바디 이름 집합 · 빠진 바디(메시를 더하거나 뺀 사본 없음)",
               "색 조합 관문(blender_motion 「robot materials do not match the colour scheme」) — 앞의 재질 관문이 역할마다 이름이 다른 재질 하나를 확인한 뒤 "
               "스크립트가 직접 칠하고 바로 읽는다: 앞 관문을 지나서는 거짓이 될 길이 없어 대조할 길 없음. 같은 까닭으로 보고서의 M_scene_equals_stl_and_bodies · "
               "M_materials_equal_scheme 는 거짓이면 관문이 먼저 멈춘다(보고서에서 거짓이 될 길 없음)",
               "프레임 폴더가 --scratch-root 밖인 경우(blender_motion · 가드는 저장소의 v3 산출 폴더도 허용) — 실 저장소 경로를 겨누는 대조는 하지 않는다"
               "(가드 시험 규칙). --scratch-root 가 없는 경우는 G2 · 묶기 쪽 같은 관문은 E3",
               "프레임 줄 검사 중 대조 없는 갈래 — 자세 오차(≤ 2e-6 m) · 화면 안(상자 꼭짓점 · 클립 범위) · 가시성 네 조건(광선 비율 · 바디 수 · 몸체 · 남색)을 "
               "하나씩(R1 은 네 조건을 한꺼번에 떨어뜨린다 — BAD 의 원인이 가시성 묶음인 것까지 확인)",
               "path_check 의 len(rows) == len(samples) — 같은 함수가 만든 목록이라 어긋날 길 없음",
               "합성 · 시퀀서 끄기 — 무조건 끄므로 대조 없음",
               "ffprobe 확인(E_*) · 게시 순서 · 임시 셋 정리 — motion_encode.main() 은 실제 묶기에서만 돈다(산출 경로가 저장소로 고정 · 그 결과는 영상 곁 기록)"],
           "all_ok": all(r["ok"] for r in rows) and sha(BLEND) == blend_before}
    F_(ROOT / ".dev" / "product-v3-evidence" / "motion-controls.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("CONTROLS", "ALL_OK" if res["all_ok"] else "FAILED", f"{sum(r['ok'] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
