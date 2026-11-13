# -*- coding: utf-8 -*-
"""MP7 동작 영상 묶기 — blender_motion.py 가 렌더한 프레임 폴더(작업 뿌리)를 MP4(H.264)로 묶어 v3 산출 폴더에 둔다.

사용: python motion_encode.py --frames <작업 뿌리/프레임 폴더> --scratch-root <작업 뿌리> [--crf 20] [--ffmpeg ffmpeg] [--ffprobe ffprobe]
- 입력은 저장소의 정본 파일로 고정(canonical_paths — v3 모델 · v1 기구학 · gallery_poses.json · motion_plan.json · kmjh-arm-v3.blend · motion/path-check.json) ·
  설정도 정본(1280 × 720 · 32 샘플 · JPEG 90)만. 산출 경로도 정해져 있다: models/armold-mks-product-v3/blender/motion/<video>-<scheme>.mp4 · 곁에 .json · -strip.jpg.
- 묶기 전에 확인(검토 ENC-1 · ENC-3 · ENC2-1 · ENC2-2): 프레임 폴더가 작업 뿌리 안 · frames-report.json 의 검사 목록이 정해진 아홉(EXPECTED_CHECKS)이고 모두 참 · 보고서와
  frames-meta.json 의 입력 sha256(STL · bodies.json · 기구학 · 계획 · 자세 · 검사 코드) · .blend · path-check 가 지금 파일과 같음 · 렌더 스크립트 · 가드 ·
  stl_topology 가 지금 코드와 같음 · .blend 가 고정 장면(motion_scene_pin.json · meta 의 blend_pinned) · path-check.json 을 다시 읽어 통과 · 밀도 ·
  한 바퀴 자세 확인 · 프레임 수 = 계획으로 다시 낸 수 = 폴더의 JPEG 수 · 모든 프레임 sha256 = 기록.
- 게시: MP4 · 모아 보기 · 곁 기록을 작업 뿌리에서 다 만든 뒤 옛 셋을 지우고 옮긴다(MP4 · 모아 보기를 옮겨 sha256 을 대조한 뒤 곁 기록이 마지막 — 중간에 멈추면
  파일이 빠질 뿐 짝이 어긋나지 않음 · 임시 셋은 다음 실행이 지움).
- 쓰기는 가드를 거친 산출 셋과 프레임 폴더 안 임시 파일뿐 — 파이썬 바이트코드 캐시(__pycache__ · git 제외)는 예외.
- ffmpeg 는 작업 뿌리 안 임시 파일로 → ffprobe 로 코덱 h264 · yuv420p · 제한 범위(tv) · 크기 · 프레임 수 · 속도 · 길이(프레임 수 / 속도 ± 1 프레임)를 확인 →
  가드를 거친 산출 경로로 복사."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_path  # noqa: E402
from guard import checked_dir, checked_file, find_root  # noqa: E402
from path_check import input_hashes  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def expected_out(root: Path, video: str, scheme: str) -> Path:
    """산출 MP4 의 유일한 자리 — 다른 이름 · 다른 폴더(예: .blend 위)로 쓰지 않는다(검토 ENC-3)."""
    if video not in ("turntable", "motion") or scheme not in ("brand", "swap"):
        raise SystemExit(f"unknown video / scheme in the frame report: {video} / {scheme}")
    return root / "models" / "armold-mks-product-v3" / "blender" / "motion" / f"{video}-{scheme}.mp4"


def expected_frames(plan, poses, video):
    return len(motion_path.turntable_frames(plan)) if video == "turntable" else len(motion_path.motion_frames(plan, poses))


HERE = Path(__file__).resolve().parent
CANON_SETTINGS = motion_path.CANON_SETTINGS          # 저장소에 올리는 영상은 이 설정만(README 「동작 영상」 · blender_motion 기본값과 같은 곳)
EXPECTED_CHECKS = {"M_all_frames_rendered", "M_every_frame_ok", "M_blend_pinned", "M_scene_equals_stl_and_bodies", "M_materials_equal_scheme",
                   "M_inputs_unchanged_during_run", "M_path_check_unchanged_during_run", "M_script_unchanged_during_run", "M_blend_not_modified"}
MIN_PER_FRAME, MAX_STEP_MM = motion_path.MIN_PER_FRAME, motion_path.MAX_STEP_MM      # blender_motion 과 같은 곳(검토 R3-PC-3)


def canonical_paths(root):
    """저장소의 정본 입력(검토 ENC2-1: 저장소 산출은 정본 입력으로 렌더한 프레임만)."""
    m = root / "models" / "armold-mks-product-v3"
    return {"model": m, "kin": root / "models" / "armold-mks-concept-v1" / "kinematics.json", "poses": HERE / "gallery_poses.json",
            "plan": HERE / "motion_plan.json", "blend": m / "blender" / "kmjh-arm-v3.blend", "path_check": m / "blender" / "motion" / "path-check.json"}


def preflight(root, frames, scratch_root, paths=None, canon_settings=None):
    """쓰기 전 검사 전부(아무것도 쓰지 않음) — 통과하면 묶을 재료를 돌려주고, 하나라도 어긋나면 SystemExit. 양성 대조는 이 함수만 부른다.
    paths = None 이면 정본 입력 + 정본 설정(main 은 언제나 이것) · 대조 시험만 다른 입력 묶음을 넘긴다(그때도 아무것도 쓰지 않음).
    canon_settings 를 따로 주면 설정 관문만 켜고 끌 수 있다(대조 시험 E9 — 설정 관문을 따로 확인)."""
    canonical = paths is None if canon_settings is None else canon_settings
    P = canonical_paths(root) if paths is None else paths
    frames = checked_dir(frames, root, scratch_root)
    if Path(scratch_root).resolve() not in frames.parents:
        raise SystemExit("the frames folder must be inside --scratch-root")
    rep_path = frames / "frames-report.json"
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    if set(rep.get("checks", {})) != EXPECTED_CHECKS or not all(rep["checks"].values()):      # 검토 ENC2-2: 검사 목록도 대조
        raise SystemExit(f"frame checks are not the expected set or not all true: {rep.get('checks')}")
    out = expected_out(root, rep["video"], rep["scheme"])
    meta_path = frames / "frames-meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    inputs_now = input_hashes(P["model"], P["kin"], P["plan"], P["poses"])
    stale = []
    if rep.get("inputs") != inputs_now or meta.get("inputs") != inputs_now:
        stale.append("inputs (STL / bodies.json / kinematics / plan / poses / checker code)")
    for key, p in (("blend_sha256", P["blend"]), ("path_check_sha256", P["path_check"])):
        if rep.get(key) != sha(p) or meta.get(key) != sha(p):
            stale.append(key)
    pin = json.loads((HERE / "motion_scene_pin.json").read_text(encoding="utf-8"))
    if meta.get("blend_pinned") is not True or rep.get("blend_sha256") != pin["blend_sha256"]:      # 검토 3 회: 고정 장면으로 렌더한 프레임만
        stale.append("blend not the pinned scene (motion_scene_pin.json)")
    if sha(meta_path) != rep.get("frames_meta_sha256"):
        stale.append("frames-meta.json")
    for key, fn in (("script_sha256", "blender_motion.py"), ("guard_sha256", "guard.py"), ("stl_topology_sha256", "stl_topology.py")):
        if meta.get(key) != sha(HERE / fn):                       # 검토 ENC2-2: 지금 코드로 렌더한 프레임만
            stale.append(fn)
    if rep.get("script_sha256") != meta.get("script_sha256"):
        stale.append("render script (report vs meta)")
    if any(rep.get(k) != meta.get(k) for k in ("size", "samples", "quality", "video", "scheme")):
        stale.append("settings (report vs meta)")
    if canonical and any(rep.get(k) != v for k, v in CANON_SETTINGS.items()):
        stale.append(f"settings {[rep.get(k) for k in CANON_SETTINGS]} != canonical {list(CANON_SETTINGS.values())}")
    if stale:
        raise SystemExit(f"frames were rendered from different inputs, code or settings than the current files: {stale}")
    pc = json.loads(Path(P["path_check"]).read_text(encoding="utf-8"))          # 검토 R2-PC-C: 검사 기록을 다시 읽어 판정도 본다
    tt_ok = rep["video"] != "turntable" or bool((pc.get("turntable") or {}).get("ok"))
    if not (pc.get("all_ok") and pc.get("inputs") == inputs_now and pc.get("per_frame", 0) >= MIN_PER_FRAME
            and pc.get("max_vertex_step_between_samples_mm", 1e9) <= MAX_STEP_MM and tt_ok):
        raise SystemExit("path-check.json no longer passes (all_ok / inputs / density / turntable pose)")
    plan, poses = motion_path.load(P["plan"], P["poses"])
    n = rep["frames_total"]
    jpgs = sorted(p.name for p in frames.glob("*.jpg"))
    if n != expected_frames(plan, poses, rep["video"]) or jpgs != [f"{i:04d}.jpg" for i in range(n)]:
        raise SystemExit(f"frame count mismatch: report {n}, plan {expected_frames(plan, poses, rep['video'])}, folder {len(jpgs)}")
    files = [frames / f"{i:04d}.jpg" for i in range(n)]
    bad = [p.name for i, p in enumerate(files) if sha(p) != rep["frames_sha256"].get(str(i))]
    if bad:
        raise SystemExit(f"frames changed since render: {bad[:10]}")
    return {"frames": frames, "rep": rep, "rep_path": rep_path, "n": n, "files": files, "out": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, type=Path)
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--ffprobe", default="ffprobe")
    a = ap.parse_args()
    root = find_root(Path(__file__).resolve().parent)
    pf = preflight(root, a.frames, a.scratch_root)
    frames, rep, rep_path, n, files = pf["frames"], pf["rep"], pf["rep_path"], pf["n"], pf["files"]
    out = checked_file(pf["out"], root, a.scratch_root)
    side = checked_file(out.with_suffix(".json"), root, a.scratch_root)
    strip = checked_file(out.with_name(out.stem + "-strip.jpg"), root, a.scratch_root)

    tmp = checked_file(frames / "_encode_tmp.mp4", root, a.scratch_root)
    for p in (tmp, frames / "_encode_tmp-strip.tmp", frames / "_encode_tmp.json"):     # 앞선 실행이 남긴 임시 셋
        p = checked_file(p, root, a.scratch_root)
        if p.exists():
            p.unlink()
    cmd = [a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(rep["fps"]), "-start_number", "0", "-i", str(frames / "%04d.jpg"),
           "-frames:v", str(n), "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
           "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    probe = json.loads(subprocess.run([a.ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                       "stream=codec_name,width,height,r_frame_rate,nb_read_frames,pix_fmt,color_range,color_space:format=duration",
                                       "-of", "json", str(tmp)], check=True, capture_output=True, text=True).stdout)
    st = probe["streams"][0]
    num, den = (int(x) for x in st["r_frame_rate"].split("/"))
    fps = rep["fps"]
    checks = {"E_codec_h264_yuv420p": st["codec_name"] == "h264" and st["pix_fmt"] == "yuv420p",
              "E_limited_range_tv": st.get("color_range") == "tv",
              "E_size_equals_frames": [st["width"], st["height"]] == rep["size"],
              "E_frame_count_equals_frames": int(st["nb_read_frames"]) == n,
              "E_frame_rate": num / den == fps,
              "E_duration_frames_over_fps": abs(float(probe["format"]["duration"]) - n / fps) <= 1.0 / fps}
    if not all(checks.values()):
        raise SystemExit(f"encoded video does not match the frames: {checks} {probe}")
    # 게시할 셋(MP4 · 모아 보기 · 곁 기록)을 모두 작업 뿌리에서 먼저 만든 뒤 → 옛 셋을 지우고 → 옮긴다(검토 R3 ENC3-3: 중간에 멈추면 짝이 안 맞는 셋 대신
    # 빠진 파일이 남는다 — 빠짐은 눈에 띄고, 곁 기록이 다른 MP4 를 가리키는 일은 없다)
    picks = [round(i * (n - 1) / 7) for i in range(8)]
    ims = [Image.open(files[i]).convert("RGB") for i in picks]
    w = 480
    h = round(ims[0].height * w / ims[0].width)
    sheet = Image.new("RGB", (w * 4, h * 2), (233, 237, 242))
    for k, im in enumerate(ims):
        sheet.paste(im.resize((w, h), Image.LANCZOS), ((k % 4) * w, (k // 4) * h))
    tmp_strip = checked_file(frames / "_encode_tmp-strip.tmp", root, a.scratch_root)   # 검토 R4-ENC-1: .jpg 가 아니어야 프레임 이름 관문에 안 걸림
    sheet.save(tmp_strip, format="JPEG", quality=88)
    ver = subprocess.run([a.ffmpeg, "-hide_banner", "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    rec = {"video": rep["video"], "scheme": rep["scheme"], "file": out.name, "sha256": sha(tmp), "bytes": tmp.stat().st_size,
           "frames": n, "fps": fps, "duration_s": n / fps, "size": rep["size"], "encode": {"crf": a.crf, "preset": "slow", "codec": "libx264", "ffmpeg": ver,
                                                                                          "filter": "scale=in_range=pc:out_range=tv,format=yuv420p"},
           "ffprobe": probe, "checks": checks, "frames_report_sha256": sha(rep_path), "frames_report_checks": rep["checks"],
           "frames_meta_sha256": rep.get("frames_meta_sha256"), "render_script_sha256": rep.get("script_sha256"), "encode_script_sha256": sha(__file__),
           "inputs": rep["inputs"], "blend_sha256": rep["blend_sha256"],
           "path_check_sha256": rep["path_check_sha256"], "samples": rep["samples"], "quality": rep["quality"], "blender": rep["blender"],
           "blender_build": rep.get("blender_build"),
           "max_pose_err_m": rep["max_pose_err_m"], "min_robot_ray_fraction": rep["min_robot_ray_fraction"], "strip_frames": picks,
           "frames_sha256": rep["frames_sha256"], "strip_sha256": sha(tmp_strip)}
    tmp_side = checked_file(frames / "_encode_tmp.json", root, a.scratch_root)
    tmp_side.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    for p in (side, strip, out):                     # 옛 셋 먼저 지움(곁 기록부터)
        if p.exists():
            p.unlink()
    shutil.copyfile(tmp, out)
    shutil.copyfile(tmp_strip, strip)
    if sha(out) != rec["sha256"] or sha(strip) != rec["strip_sha256"]:      # 검토 R4-ENC-2: 곁 기록을 놓기 전에 대조
        raise SystemExit("published files differ from the encoded ones")
    shutil.copyfile(tmp_side, side)                  # 곁 기록은 마지막 — 있으면 셋이 다 옮겨진 것
    for p in (tmp, tmp_strip, tmp_side):
        p.unlink()
    print("ENCODED", out.name, rec["bytes"], "bytes", n, "frames", checks)


if __name__ == "__main__":
    main()
