"""Read-only URDF/STL assembly conversion; does not run upstream code."""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import xml.etree.ElementTree as ET

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from trimesh.viewer.notebook import scene_to_html

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs/references/packages/01/mechanical_refs/Faze4"
UPSTREAM = SOURCE / "upstream"
PACKAGE = UPSTREAM / "URDF_FAZE4"
OUT = ROOT / "models/six-axis-reference/faze4"
EVIDENCE = ROOT / ".dev/assembly-evidence/faze4"
URDF = PACKAGE / "urdf/Final_light_assembly_URDF.urdf"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vec(text, default):
    return np.array([float(x) for x in (text or default).split()])


def origin(element):
    """URDF fixed-axis roll/pitch/yaw: T(xyz) @ Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    if element is None:
        return np.eye(4)
    r, p, y = vec(element.get("rpy"), "0 0 0")
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    result = np.eye(4)
    result[:3, :3] = rz @ ry @ rx
    result[:3, 3] = vec(element.get("xyz"), "0 0 0")
    return result


def preview(scene, target):
    """Orthographic painter preview, full original triangles; not a CAD screenshot."""
    meshes = []
    for node in scene.graph.nodes_geometry:
        matrix, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(matrix)
        meshes.append(mesh)
    triangles = np.concatenate([m.triangles for m in meshes])
    colors = np.concatenate([m.visual.face_colors[:, :3] for m in meshes])
    # Preserve the URDF base frame: Z is the principal upward direction.
    eye = np.array([1.1, -1.0, 0.7])
    eye /= np.linalg.norm(eye)
    right = np.cross([0, 0, 1], eye)
    right /= np.linalg.norm(right)
    up = np.cross(eye, right)
    basis = np.array([right, up, eye])
    projected = triangles @ basis.T
    lo = projected[:, :, :2].reshape(-1, 2).min(axis=0)
    hi = projected[:, :, :2].reshape(-1, 2).max(axis=0)
    scale = min(1030 / (hi[0] - lo[0]), 860 / (hi[1] - lo[1]))
    center = (hi + lo) / 2
    xy = (projected[:, :, :2] - center) * scale
    xy[:, :, 0] += 630
    xy[:, :, 1] = 630 - xy[:, :, 1]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-20)
    shade = .35 + .65 * np.abs(normals @ eye)
    colors = np.clip(colors * shade[:, None], 0, 255).astype(np.uint8)
    image = Image.new("RGB", (1600, 1200), "#edf1f7")
    draw = ImageDraw.Draw(image)
    for i in np.argsort(projected[:, :, 2].mean(axis=1)):
        draw.polygon([tuple(p) for p in xy[i]], fill=tuple(colors[i]))
    fontpath = Path(os.environ.get("WINDIR", "")) / "Fonts/malgun.ttf"
    font = ImageFont.truetype(str(fontpath), 24) if fontpath.exists() else ImageFont.load_default()
    title = ImageFont.truetype(str(fontpath), 34) if fontpath.exists() else font
    draw.rectangle((0, 0, 1600, 140), fill="#13263c")
    draw.text((35, 24), "FAZE4 · 6관절 전체 링크 시각화", fill="white", font=title)
    draw.text((35, 80), "원본 URDF의 모든 관절 q=0 · 7개 링크 · 281,208개 삼각형", fill="#b6d6ff", font=font)
    for i, (name, color) in enumerate(zip(scene.geometry, PALETTE)):
        draw.rectangle((1240, 240 + i * 65, 1268, 268 + i * 65), fill=tuple(color[:3]))
        draw.text((1280, 237 + i * 65), name, font=font, fill="#243c56")
    draw.text((35, 1100), "제조 상세 CAD 아님 · 그리퍼 개폐 모형 없음 · 최종 MKS 호환 미확인", fill="#963c18", font=font)
    draw.text((35, 1140), "형상 미변경 / 링크별 색상만 구분 · 실물·간섭·강도·출력 검증 NOT_RUN", fill="#45546b", font=font)
    image.save(target)


PALETTE = [[81, 100, 128, 255], [47, 138, 190, 255], [230, 132, 59, 255],
           [98, 169, 115, 255], [152, 113, 185, 255], [224, 181, 60, 255], [202, 92, 103, 255]]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(URDF).getroot()
    links = {x.get("name"): x for x in tree.findall("link")}
    joints = tree.findall("joint")
    children = {j.find("child").get("link") for j in joints}
    roots = set(links) - children
    assert len(roots) == 1 and len(links) == 7 and len(joints) == 6
    base = roots.pop()
    matrices = {base: np.eye(4)}
    pending = joints.copy()
    records = []
    while pending:
        progress = False
        for joint in pending.copy():
            parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
            if parent not in matrices:
                continue
            assert child not in matrices
            local = origin(joint.find("origin"))
            matrices[child] = matrices[parent] @ local  # q=0, so axis-angle rotation is identity.
            axis = vec(joint.find("axis").get("xyz"), "1 0 0")
            records.append({"name": joint.get("name"), "type": joint.get("type"), "parent": parent,
                            "child": child, "q_rad": 0, "axis_child_frame": axis.tolist(),
                            "origin_parent_to_child_m": local.tolist(), "world_from_child_m": matrices[child].tolist()})
            pending.remove(joint)
            progress = True
        assert progress, "Cycle or disconnected URDF"
    scene = trimesh.Scene(base_frame=base, metadata={"units": "m", "pose": "all q=0"})
    source_files = [URDF, UPSTREAM / "LICENSE", SOURCE / "SOURCE_MANIFEST.json"]
    link_records = []
    for index, (name, link) in enumerate(links.items()):
        visual = link.find("visual")
        mesh_spec = visual.find("geometry/mesh")
        path = PACKAGE / "meshes" / Path(mesh_spec.get("filename")).name
        source_files.append(path)
        mesh = trimesh.load_mesh(path, process=False)
        mesh.apply_scale(vec(mesh_spec.get("scale"), "1 1 1"))
        mesh.units = "m"
        assert np.isfinite(mesh.vertices).all()
        mesh.visual.face_colors = PALETTE[index]
        transform = matrices[name] @ origin(visual.find("origin"))
        scene.add_geometry(mesh, node_name=name + "_visual", geom_name=name, transform=transform)
        world_vertices = trimesh.transform_points(mesh.vertices, transform)
        link_records.append({"link": name, "triangles": len(mesh.faces), "source": path.relative_to(ROOT).as_posix(),
                             "visual_matrix_m": transform.tolist(), "world_bbox_m": [world_vertices.min(axis=0).tolist(), world_vertices.max(axis=0).tolist()]})
    total = sum(x["triangles"] for x in link_records)
    assert total == 281208
    # Source geometry and GLB remain metre-valued. Camera only changes the viewing direction.
    scene.set_camera(angles=[math.radians(68), 0, math.radians(38)], fov=[45, 35])
    scene.export(OUT / "faze4-zero-pose-metres.glb")
    mm = scene.copy()
    mm.apply_scale(1000)
    mm.units = "mm"
    mm.export(OUT / "faze4-zero-pose-mm.3mf")
    mm.to_mesh().export(OUT / "faze4-zero-pose-mm.stl")
    html = scene_to_html(scene)
    panel = '''<aside style="position:fixed;top:16px;left:16px;z-index:5;max-width:620px;padding:18px 22px;border-radius:14px;background:#13263ced;color:white;font:16px/1.55 system-ui;box-shadow:0 6px 30px #0003"><strong style="font-size:24px">FAZE4 · 6관절 전체 링크 시각화</strong><br>URDF q=0 · 7개 링크 · 281,208개 삼각형<br><span style="color:#ffd2a5">제조 상세 CAD 아님 · 그리퍼 개폐 모형 없음<br>최종 MKS 모터·드라이버 호환 미확인</span><br><small>드래그: 회전 · 휠: 확대 · 우클릭 드래그: 이동<br>GLB 좌표 단위 m / STL·3MF mm · 링크 색상만 구분<br>출처: Source-Robotics/Faze4-Robotic-arm<br>실제 LICENSE: CERN-OHL-S v2 / README MIT 배지와 불일치</small><br><a href="README.md" style="color:#9ad4ff">출처·변환·한계</a> · <a href="preview.png" style="color:#9ad4ff">정지 이미지</a></aside>'''
    html = html.replace('<html lang="en">', '<html lang="ko">').replace("<title>trimesh: threejs viewer</title>", "<title>Faze4 6관절 참조 — MKS 호환 미확인</title>").replace("<body>", "<body>" + panel)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    preview(scene, OUT / "preview.png")
    shutil.copyfile(UPSTREAM / "LICENSE", OUT / "LICENSE-CERN-OHL-S-2.0.txt")
    glb = trimesh.load_scene(OUT / "faze4-zero-pose-metres.glb")
    round3mf = trimesh.load_scene(OUT / "faze4-zero-pose-mm.3mf")
    roundstl = trimesh.load_mesh(OUT / "faze4-zero-pose-mm.stl", process=False)
    checks = {"links": len(links), "joints": len(joints), "meshes": len(scene.geometry), "triangles": total,
              "all_finite": all(np.isfinite(m.vertices).all() for m in scene.geometry.values()),
              "bbox_metres": scene.bounds.tolist(), "extents_mm": (scene.extents * 1000).tolist(),
              "glb_reload_meshes": len(glb.geometry), "glb_bbox_close": bool(np.allclose(glb.bounds, scene.bounds, atol=1e-6)),
              "3mf_reload_meshes": len(round3mf.geometry), "3mf_bbox_mm_close": bool(np.allclose(round3mf.bounds, scene.bounds * 1000, atol=.001)),
              "stl_reload_triangles": len(roundstl.faces), "stl_bbox_mm_close": bool(np.allclose(roundstl.bounds, scene.bounds * 1000, atol=.001)),
              "runtime_viewer": "NOT_RUN: parent opens GUI", "physical_fit_strength_collision_print": "NOT_RUN"}
    assert checks["glb_bbox_close"] and checks["3mf_bbox_mm_close"] and checks["stl_bbox_mm_close"]
    provenance = {"repository": "https://github.com/Source-Robotics/Faze4-Robotic-arm", "commit": "674f46cb608d25899c46fc2ea67741f008a8f016",
                  "license_actual": "CERN-OHL-S-2.0", "license_conflict": "README MIT badge differs from actual LICENSE; unresolved, not asserted MIT",
                  "pose": "All six continuous joints at zero; URDF continuous does not validate unlimited real motion",
                  "convention": "T_world_child = T_world_parent @ T(xyz) @ Rz(yaw) @ Ry(pitch) @ Rx(roll); q=0; visual origin applied once",
                  "units": {"source_URDF_STL": "metres", "GLB": "metres", "STL_3MF": "millimetres; all geometry and placements scaled 1000 once"},
                  "changes": "Link colors assigned for identification. No source geometry edits, no decimation, no inferred joints.",
                  "source_files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p), "bytes": p.stat().st_size} for p in source_files],
                  "joints": records, "links": link_records, "checks": checks}
    (OUT / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    (EVIDENCE / "validation.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text('''# Faze4 6관절 참조 링크 조립도

원본 URDF의 **7개 링크·6개 관절**을 모두 q=0인 저장 기준 배치로 연결한 시각화다. 제조 상세 CAD가 아니며 별도 그리퍼 개폐 모형은 없다. 현재 주문한 MKS SERVO42D CAN MT 호환, 최종 로봇 구조 선정, 출력·실물 운동·간섭·강도는 검증하지 않았다.

- `index.html`: Three.js와 GLB를 모두 내장한 오프라인 회전·확대 뷰어. 외부 CDN·요청 불필요.
- `preview.png`: 전체 원본 삼각형을 소프트웨어 투영한 정지 미리보기. CAD 프로그램 스크린샷이 아니다.
- `faze4-zero-pose-metres.glb`: 단위 m, 7개 링크 구분.
- `faze4-zero-pose-mm.3mf`: 단위 mm, 7개 링크 구분. 시각화 데이터이며 출력 승인 파일이 아니다.
- `faze4-zero-pose-mm.stl`: 단위 mm로 변환한 합본. STL은 단위 메타데이터가 없으므로 가져올 때 mm 지정.
- `faze4-six-axis-reference.solidcraft`: 설치된 SolidCraft로 읽은 정적 링크 조립. 링크 색상과 배치를 보존한다. 편집용 상세 솔리드/BREP가 아닌 메시다.
- `iso.png` / `front.png` / `side.png`: SolidCraft CLI의 실제 등각·정면·측면 렌더. `native-validation.json`은 각 링크의 월드 좌표 경계를 원본과 대조한다.
- `provenance.json`: 원본 해시·관절/링크 변환·좌표 경계·재가져오기 검사.

원본: https://github.com/Source-Robotics/Faze4-Robotic-arm — 커밋 `674f46cb608d25899c46fc2ea67741f008a8f016`. 실제 `LICENSE`는 **CERN-OHL-S v2**이며 동봉했다. README의 MIT 배지와 불일치는 미해결로 남긴다. MIT 라이선스로 단정하지 않는다. 변경은 링크 구분 색상, 파일 변환, 미리보기/뷰어 추가뿐이다. 원본 메시·URDF·코드는 수정하거나 실행하지 않았다.

URDF 기준 `T_world_child = T_world_parent × T(xyz) × Rz(yaw) × Ry(pitch) × Rx(roll)`이며 q=0이라 관절축 추가 회전은 단위행렬이다. visual origin을 한 번 적용했다. 원본 좌표와 GLB는 m, STL·3MF만 전체 장면을 1,000배 하여 mm로 변환했다. `continuous`는 원본의 기술이며 실제 무제한 회전 가능 판정이 아니다.

재현(프로젝트 루트): `C:/projects/printforge/.venv/Scripts/python.exe src/cad/assembly-reference/faze4_build.py`. 설치된 trimesh/numpy/Pillow만 사용. 프린터 전송·실물 운전 없음. 정지 미리보기는 원본 모든 삼각형을 사용하되 painter 방식이라 픽셀별 깊이 버퍼 렌더와 다를 수 있다.

SolidCraft 재현: 같은 Python으로 `src/cad/assembly-reference/faze4_native.py --cli <설치된-solidcraft-cli.exe>`를 실행한다. GLB 가져오기에 `up=z`를 지정하고 glTF의 m→mm 변환을 확인한다. 원본 URDF의 6개 관절 정보는 provenance에 보존한다. SolidCraft importer가 만든 7개 rigid attachment는 메시 배치를 고정하는 관계이며 6개 구동 관절의 기구학 모델이 아니다. 프로그램의 Default 재질 밀도로 계산되는 질량은 실제 로봇 질량이 아니다.
''', encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
