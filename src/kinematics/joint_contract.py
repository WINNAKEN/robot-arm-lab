"""Read-only CAD snapshot -> canonical joint contract. No device or CAD execution."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import uuid
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    "kin": "models/armold-mks-concept-v1/kinematics.json",
    "v1": "src/cad/armold-mks-concept/parameters.json",
    "v2": "src/cad/armold-mks-product-v2/parameters.json",
    "commands": "models/armold-mks-product-v2/build-commands.json",
    "native": "models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft",
    "validation": "models/armold-mks-product-v2/validation.json",
}
ARTIFACTS = ("joint-map.json", "joint-map.md", "reference-poses.json", "simulation-readiness.json")
I = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]


def need(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    need(type(value) in (int, float), "Expected finite number, not bool")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("Number outside finite float range") from exc
    need(math.isfinite(result), "Expected finite number")
    return result


def vector(value, n=3):
    need(isinstance(value, list) and len(value) == n, f"Expected vector length {n}")
    return [number(x) for x in value]


def transpose(a):
    return [list(row) for row in zip(*a)]


def mv(a, v):
    return [sum(x*y for x, y in zip(row, v)) for row in a]


def mm(a, b):
    return [[sum(x*y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


def close(a, b, tolerance=1e-8):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tolerance) for x, y in zip(a, b))
    return abs(number(a)-number(b)) <= tolerance


def matrix(value):
    need(isinstance(value, list) and len(value) == 3, "Expected 3x3 rotation")
    r = [vector(row) for row in value]
    determinant = sum(r[0][j]*(r[1][(j+1)%3]*r[2][(j+2)%3]-r[1][(j+2)%3]*r[2][(j+1)%3]) for j in range(3))
    need(close(mm(transpose(r), r), I) and abs(determinant-1) < 1e-8, "Rotation must be SO(3)")
    return r


def axis(value):
    v = vector(value)
    need(abs(sum(x*x for x in v)-1) < 1e-8, "Axis must have unit length")
    return v


def rotation(a, angle):
    x, y, z = axis(a)
    c, s = math.cos(number(angle)), math.sin(angle)
    t = 1-c
    return [[c+x*x*t, x*y*t-z*s, x*z*t+y*s],
            [y*x*t+z*s, c+y*y*t, y*z*t-x*s],
            [z*x*t-y*s, z*y*t+x*s, c+z*z*t]]


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse(raw):
    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    try:
        result = json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=invalid_constant)
    except (RecursionError, OverflowError) as exc:
        raise ValueError("JSON exceeds numeric/nesting parser limits") from exc
    stack = [(result, 0)]
    while stack:
        value, depth = stack.pop()
        need(depth <= 64, "JSON nesting exceeds supported depth64")
        if isinstance(value, dict):
            stack.extend((v,depth+1) for v in value.values())
        elif isinstance(value, list):
            stack.extend((v,depth+1) for v in value)
        elif type(value) in (int,float):
            number(value)
    return result


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(root):
    data, hashes = {}, {}
    for name, relative in INPUTS.items():
        path = root / relative
        need(path.stat().st_size <= 64*1024*1024, "Input too large")
        raw = path.read_bytes()
        hashes[relative] = sha(raw)
        if name == "native":
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    entries = [e for e in archive.infolist() if e.filename == "document.json"]
                    need(len(entries) == 1 and entries[0].file_size <= 5*1024*1024, "Invalid native document entry")
                    entry = entries[0]
                    need(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "Unsupported native compression")
                    need(not entry.flag_bits & 1, "Encrypted native document unsupported")
                    data[name] = parse(archive.read(entry))
            except (zipfile.BadZipFile, RuntimeError, EOFError, zlib.error) as exc:
                raise ValueError(f"Invalid native archive: {exc}") from exc
        else:
            data[name] = parse(raw)
    return data, hashes


def extract(data):
    need(all(isinstance(data[k],dict) for k in INPUTS), "Source document roots must be objects")
    kin, v1, v2, native = (data[k] for k in ("kin", "v1", "v2", "native"))
    need(all(d["units"] == "mm" for d in (kin, v1, v2, native)), "Source units must be mm")
    need(native["format"] == "solidcraft/31", "Unsupported native format")
    need(type(kin["joint_count"]) is int and kin["joint_count"] == 6 and len(kin["joints"]) == 6, "Six joints required")
    pose = vector(v1["pose_deg"], 6)
    local_axes = [axis(a) for a in v1["axis_parent_zero"]]
    need(len(local_axes) == 6, "Six parameter axes required")
    offsets = [[0, 0, number(v1["joint1_height_mm"])], [0, 0, number(v1["shoulder_rise_mm"])],
               [number(v1["upper_arm_mm"]), 0, 0], [number(v1["forearm_mm"]), 0, 0]]
    wrists = vector(v1["wrist_offsets_mm"], 2)
    offsets += [[w, 0, 0] for w in wrists]
    need(all(all(x >= 0 for x in o) and sum(x*x for x in o) > 0 for o in offsets), "Positive nonzero layout offsets required")
    commands = [c["params"] for c in data["commands"]["commands"] if c["command"] == "joint.as_built"]
    nj = native["assembly"]["joints"]
    need(len(commands) == len(nj) == 6, "Exactly six native and command joints required")
    need(all(type(j["id"]) is int and j["id"] > 0 for j in nj) and len({j["id"] for j in nj}) == 6, "Invalid native joint IDs")
    names = [f"J{i}_DISPLAY_ZERO" for i in range(1, 7)]
    need({j["name"] for j in nj} == set(names) and {j["name"] for j in commands} == set(names), "Native/command joint identities mismatch")
    components, occurrences = native["components"], native["occurrences"]
    need(len(components) == len(occurrences) == 7, "Seven native links required")
    for c in components:
        need(type(c["id"]) is int and c["id"] > 0 and type(c["parent"]) is int and c["parent"] == 0, "Invalid component ID/parent")
    component_names = {c["id"]: c["name"] for c in components}
    need(len(component_names) == 7, "Duplicate native component IDs")
    occurrence_names = {}
    for o in occurrences:
        need(type(o["id"]) is int and o["id"] > 0 and type(o["component"]) is int and type(o["parent"]) is int and o["parent"] == 0, "Invalid occurrence identity")
        need(o["id"] not in occurrence_names, "Duplicate occurrence IDs")
        need(o["name"] == component_names[o["component"]]+":1", "Occurrence/component identity mismatch")
        need(type(o["grounded"]) is bool and o["grounded"] == (o["name"] == "Base:1"), "Expected grounded Base only")
        need(close(o["transform"], [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]), "Only static identity occurrence transforms supported")
        occurrence_names[o["id"]] = o["name"]
    need(set(occurrence_names.values()) == {n+":1" for n in ["Base"]+[f"Link{i}" for i in range(1,7)]}, "Native link chain mismatch")
    output_signs = vector(v2["exterior"]["output_side_sign"], 6)
    need(all(s in (-1, 1) for s in output_signs), "Invalid exterior side sign")
    previous_p, previous_r, joints = [0., 0., 0.], I, []
    for i, source in enumerate(kin["joints"]):
        name, parent, child = f"J{i+1}", "Base" if i == 0 else f"Link{i}", f"Link{i+1}"
        need((source["name"], source["parent"], source["child"]) == (name, parent, child), "Kinematic chain/order mismatch")
        p, rp, rc, aw = vector(source["origin_mm"]), matrix(source["R_parent"]), matrix(source["R_child"]), axis(source["axis_world"])
        need(close(rp, previous_r), "Parent rotation chain mismatch")
        al = mv(transpose(rp), aw)
        need(close(al, axis(source["axis_parent_zero"])) and close(al, local_axes[i]), "Local axis mismatch")
        need(number(source["pose_deg"]) == pose[i], "Display pose mismatch")
        need(close(mm(rp, rotation(al, math.radians(pose[i]))), rc), "Geometric reference rotation mismatch")
        local_mm = mv(transpose(rp), [x-y for x, y in zip(p, previous_p)])
        need(close(local_mm, offsets[i], 1e-7), "Layout length mismatch")
        command = next(j for j in commands if j["name"] == names[i])
        actual = next(j for j in nj if j["name"] == names[i])
        need(all(type(actual[end]["occurrence"]) is int for end in ("a", "b")), "Invalid joint occurrence ID")
        need((command["a"], command["b"], command["type"]) == (parent+":1", child+":1", "revolute"), "Command topology mismatch")
        need(close(vector(command["at"]["point"]), p) and close(axis(command["at"]["z"]), aw), "Command joint frame mismatch")
        need(occurrence_names[actual["a"]["occurrence"]] == parent+":1" and occurrence_names[actual["b"]["occurrence"]] == child+":1" and actual["kind"] == "revolute", "Native joint topology mismatch")
        need(type(actual["flip"]) is bool and close(vector(actual["values"], 1), [0]) and number(actual["angle"]) == 0 and number(actual["offset"]) == 0, "Expected static native zero")
        for end in ("a", "b"):
            snap = actual[end]["snap"]
            need(close(vector(snap.get("point", snap.get("origin"))), p) and close(axis(snap["z"]), aw), "Native joint frame mismatch")
        need(len(actual["limits"]) == len(command["limits"]) == 1, "Single CAD angle limit required")
        limits = vector(actual["limits"][0], 2)
        need(limits[0] < limits[1] and limits[0] <= 0 <= limits[1] and close(limits, [math.radians(x) for x in vector(command["limits"][0], 2)]), "Illustrative limit mismatch")
        joints.append({"name": name, "parent": parent, "child": child,
                       "offset_parent_m": [x / 1000.0 for x in local_mm],
                       "axis_parent": al, "reference_rotation": mm(transpose(rp), rc),
                       "display_pose_rad": math.radians(pose[i]), "native_static_angle_rad": 0,
                       "native_flip": actual["flip"], "native_positive_angle_to_delta": None,
                       "illustrative_cad_limits_rad": limits, "mechanical_limits_rad": None,
                       "packaging_output_side_sign": output_signs[i],
                       "motor": {k: None for k in ("can_id", "reduction_ratio", "direction_sign", "motor_zero_rad", "joint_zero_rad", "encoder_scale", "velocity_limit", "acceleration_limit", "torque_limit")}})
        previous_p, previous_r = p, rc
    checks = data["validation"]["checks"]
    need(checks.get("joints_match_v1") is True, "Historical joint-check evidence missing")
    reference_x = ring_reference(data, component_names)
    return {"schema": "robot-arm-canonical-joints/1", "status": "CANDIDATE_KINEMATICS_ONLY",
            "angle_coordinate": "right_hand_canonical_display_delta_rad_not_native_angle",
            "joints": joints, "geometry_reference_link6_m": [reference_x/1000, 0, 0],
            "tcp": None, "gripper": None, "mass_inertia": None, "physical_approval": False,
            "native_runtime_sign": "NOT_RUN", "isaac_world": "NOT_CREATED", "rl_environment": "NOT_CREATED"}


def ring_reference(data, component_names):
    """Tie the reference to an active native rectangle/revolve, not just dimensions."""
    tool = data["v2"]["links"]["tool"]
    depth = number(data["v1"]["reducer_depth_mm"])
    flange, thickness, radius = (number(tool[k]) for k in ("flange_t", "ring_t", "ring_r"))
    need(all(x > 0 for x in (depth, flange, thickness, radius)), "Invalid ring dimensions")
    back, front = depth/2+flange, depth/2+flange+thickness
    expected = [[back,0], [back,radius], [front,radius], [front,0]]
    commands = data["commands"]["commands"]
    indices = [i for i,c in enumerate(commands) if c.get("params",{}).get("name") == "LINK6_TOOL_RING_PROFILE"]
    need(len(indices) == 1, "Unique ring command profile required")
    sequence = commands[indices[0]:indices[0]+4]
    need([c["command"] for c in sequence] == ["sketch.create","sketch.line","sketch.finish","solid.revolve"], "Unsupported ring command sequence")
    plane = sequence[0]["params"]["plane"]
    points = [vector(p,2) for p in sequence[1]["params"]["points"]]
    need(sequence[1]["params"]["closed"] is True and close(points,expected), "Ring dimension/command profile mismatch")
    need(sequence[3]["params"]["axis"] == "x" and sequence[3]["params"]["operation"] == "new" and sequence[3]["params"]["body_name"] == "LINK6_TOOL_RING", "Ring command revolve mismatch")
    features = data["native"]["features"]
    profiles = [f for f in features if f["name"] == "LINK6_TOOL_RING_PROFILE"]
    revolves = [f for f in features if f["name"] == "LINK6_TOOL_RING_REVOLVE"]
    need(len(profiles) == len(revolves) == 1, "Unique native ring features required")
    profile, revolve = profiles[0], revolves[0]
    link6 = next(k for k,v in component_names.items() if v == "Link6")
    need(type(profile["component"]) is int and type(revolve["component"]) is int and type(revolve["sketch"]) is int, "Invalid native ring references")
    need(profile["type"] == "sketch" and profile["suppressed"] is False and profile["component"] == link6 and type(profile["id"]) is int, "Invalid native ring profile")
    need(revolve["type"] == "revolve" and revolve["suppressed"] is False and revolve["sketch"] == profile["id"] and revolve["component"] == link6 and revolve["body_names"] == ["LINK6_TOOL_RING"] and revolve["axis"] == {"type":"sketch_axis","axis":"x"} and revolve["angle"] == "360 deg" and revolve["operation"] == "new_body", "Invalid native ring revolve")
    need(profile["plane"]["type"] == "custom", "Native ring plane must be explicit")
    native_plane = profile["plane"]["plane"]
    last = data["kin"]["joints"][-1]
    expected_plane = {"origin":vector(last["origin_mm"]), "x_dir":list(zip(*last["R_child"]))[0], "y_dir":list(zip(*last["R_child"]))[2]}
    for key, values in expected_plane.items():
        need(close(vector(plane[key]), list(values)) and close(vector(native_plane[key]), list(values)), "Ring plane/frame mismatch")
    all_points = profile["sketch"]["points"]
    native_points = [vector(p["pos"],2) for p in all_points if p["id"] != "origin"]
    need(len(all_points) == 5 and close(native_points, points), "Ring command/native profile mismatch")
    curves = profile["sketch"]["curves"]
    need(len(curves) == 4 and all(c["type"] == "line" and c["construction"] is False and type(c["a"]) is int and type(c["b"]) is int for c in curves) and [(c["a"],c["b"]) for c in curves] == [(1,2),(2,3),(3,4),(4,1)], "Native ring must be the closed rectangle")
    return max(p[0] for p in native_points)


def fk(contract, q_delta):
    angles = vector(q_delta, 6)
    need(len(contract["joints"]) == 6, "Six contract joints required")
    p, r, result = [0., 0., 0.], I, []
    for joint, angle in zip(contract["joints"], angles):
        p = [a+b for a, b in zip(p, mv(r, vector(joint["offset_parent_m"])))]
        local_axis = axis(joint["axis_parent"])
        world_axis = mv(r, local_axis)
        r = mm(r, mm(rotation(local_axis, angle), matrix(joint["reference_rotation"])))
        result.append({"name": joint["name"], "origin_m": p[:], "axis_world": world_axis, "rotation_world": r})
    reference = [a+b for a, b in zip(p, mv(r, vector(contract["geometry_reference_link6_m"])))]
    return {"joints": result, "ring_reference_m_not_tcp": reference}


def geometric_to_delta(contract, angles):
    need(len(contract["joints"]) == 6, "Six contract joints required")
    return [q-j["display_pose_rad"] for q, j in zip(vector(angles, 6), contract["joints"])]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode("utf-8")


def atomic_json(path, value):
    temporary = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    temporary.write_bytes(encoded(value))
    os.replace(temporary, path)


def table(contract, run_id):
    rows = ["# 6축 관절 기준 — 후보 스냅샷", "", f"run_id: `{run_id}`. 역사 스냅샷이며 현재 사용 전 verify 명령이 필요합니다.", "",
            "CAD 원본/펌웨어를 수정하지 않았습니다. canonical delta0은 표시 자세입니다. 실제 CAD 양의 angle 부호, 모터 부호·감속비·CAN ID·실물 영점은 미확정입니다.", "",
            "| 관절 | 연결 | 부모 지역 축 | 부모 오프셋 m | 표시 기구학각 deg | 모터/CAN/감속비 |", "|---|---|---|---|---|---|"]
    for j in contract["joints"]:
        rows.append(f"| {j['name']} | {j['parent']} → {j['child']} | {[round(x,6) for x in j['axis_parent']]} | {[round(x,6) for x in j['offset_parent_m']]} | {math.degrees(j['display_pose_rad']):g} | 미정 |")
    rows += ["", "`q_geometric = q_delta + display_pose`. 양의 canonical 회전은 오른손 규칙입니다.",
             "J3의 외장 출력면 방향은 모터 부호가 아닙니다. ±170°는 CAD 예시이며 실물 가동범위가 아닙니다.",
             "J6 원점과 링 전면 형상 기준점은 TCP가 아닙니다. 그리퍼·실제 TCP·질량/관성·충돌/실물 제한이 없어 물리 시뮬레이션/RL 준비 완료가 아닙니다.", ""]
    return "\n".join(rows).encode("utf-8")


def build(root, out):
    out.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    current = out / "current.json"
    atomic_json(current, {"status": "BUILDING", "run_id": run_id})
    try:
        data, hashes = capture(root)
        contract = extract(data)
        bundle = out / "runs" / run_id
        bundle.mkdir(parents=True, exist_ok=False)
        payload = {
            "joint-map.json": encoded(contract), "joint-map.md": table(contract, run_id),
            "reference-poses.json": encoded({"canonical_delta_zero": fk(contract, [0]*6),
                                             "geometric_zero": fk(contract, geometric_to_delta(contract, [0]*6))}),
            "simulation-readiness.json": encoded({"status": "NOT_PHYSICS_READY", "kinematics": "CANDIDATE_ONLY",
                "missing": ["confirmed_model_revision", "motor_ids_signs_reduction_zeros_scale", "mechanical_limits", "mass_com_inertia", "collision_geometry", "actuator_friction_backlash", "tcp_gripper", "isaac_runtime_environment"],
                "installed_or_executed": False, "hardware_approved": False}),
        }
        for name, raw in payload.items():
            (bundle / name).write_bytes(raw)
        _, after = capture(root)
        need(hashes == after, "Source changed during extraction")
        manifest = {"run_id": run_id, "sources": hashes, "producer_sha256": sha(Path(__file__).read_bytes()),
                    "files": {n: sha(b) for n, b in payload.items()}}
        manifest_raw = encoded(manifest)
        (bundle / "manifest.json").write_bytes(manifest_raw)
        atomic_json(current, {"status": "PASS", "run_id": run_id, "manifest_sha256": sha(manifest_raw)})
        return verify(root, out)
    except (OSError, ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile) as exc:
        atomic_json(current, {"status": "FAILED", "run_id": run_id, "reason": str(exc)})
        raise


def verify(root, out):
    current = parse((out / "current.json").read_bytes())
    need(current["status"] == "PASS", "Current run is not PASS; no fallback")
    run_id = current["run_id"]
    need(isinstance(run_id, str) and re.fullmatch(r"[0-9a-f]{32}", run_id) is not None, "Invalid run ID")
    bundle = out / "runs" / run_id
    raw = (bundle / "manifest.json").read_bytes()
    need(sha(raw) == current["manifest_sha256"], "Manifest hash mismatch")
    manifest = parse(raw)
    need(manifest["run_id"] == run_id and set(manifest["files"]) == set(ARTIFACTS), "Bundle identity/files mismatch")
    need(manifest["producer_sha256"] == sha(Path(__file__).read_bytes()), "Producer changed; regenerate snapshot")
    _, hashes = capture(root)
    need(hashes == manifest["sources"], "Current source differs from snapshot")
    for name in ARTIFACTS:
        need(sha((bundle/name).read_bytes()) == manifest["files"][name], "Artifact hash mismatch")
    return {"status": "PASS", "run_id": run_id, "bundle": str(bundle), "sources": hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    out = args.out or args.root / "outputs/joint-control-v1"
    try:
        result = (build if args.action == "build" else verify)(args.root, out)
    except (OSError, ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
