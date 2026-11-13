"""Generate original bench accessories; no printer control, network or slicing.

Requires an existing SolidCraft 0.18.2 CLI, numpy, trimesh and Pillow.
All geometry uses mm, positive XYZ and a flat bottom at Z=0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import trimesh


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
PART_NAMES = ("cable_tie_mount", "wire_label_tag", "parts_tray")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(command_id: str, **params: object) -> dict:
    return {"command": command_id, "params": params}


def rectangle(name: str, p0: list, p1: list, offset: object = 0) -> list:
    return [command("sketch.create", plane="XY", offset=offset, name=name),
            command("sketch.line", points=[p0, [p1[0], p0[1]], p1, [p0[0], p1[1]]], closed=True),
            command("sketch.finish")]


def model_script(name: str, p: dict) -> dict:
    commands = [command("parameters.change", name=("base_t" if k == "floor" else k), expression=f"{v} mm") for k, v in p.items()]
    commands += rectangle("OuterProfile", [0, 0], ["width", "depth"])
    commands.append(command("solid.extrude", distance="height", operation="new", body_name=name))
    if name == "cable_tie_mount":
        commands += rectangle("TieTunnel", ["(width-channel_width)/2", -1],
                              ["(width+channel_width)/2", "depth+1"], "base_t")
        commands.append(command("solid.extrude", distance="channel_height", operation="cut"))
    elif name == "wire_label_tag":
        commands += rectangle("TieSlot", ["slot_left", "(depth-slot_depth)/2"],
                              ["slot_left+slot_width", "(depth+slot_depth)/2"])
        commands.append(command("solid.extrude", distance="height", operation="cut"))
    else:
        commands += rectangle("TrayInterior", ["wall", "wall"], ["width-wall", "depth-wall"], "base_t")
        commands.append(command("solid.extrude", distance="height-base_t+1", operation="cut"))
    return {"commands": commands}


def validate_parameters(parts: dict) -> None:
    if set(parts) != set(PART_NAMES):
        raise ValueError("Exactly the three named bench parts are required")
    for name, p in parts.items():
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in p.values()):
            raise ValueError(f"{name}: dimensions must be finite positive numbers")
        w, d, h = (p[k] for k in ("width", "depth", "height"))
        if name == "cable_tie_mount" and not (p["channel_width"] < w and p["floor"] + p["channel_height"] < h):
            raise ValueError("Mount requires side walls, floor and roof")
        if name == "wire_label_tag" and not (p["slot_left"] + p["slot_width"] < w and p["slot_depth"] < d):
            raise ValueError("Tag slot must be strictly inside the plate")
        if name == "parts_tray" and not (2*p["wall"] < min(w, d) and p["floor"] < h):
            raise ValueError("Tray requires interior space and positive walls")


def inside(mesh: trimesh.Trimesh, point: list[float]) -> bool:
    """Generalized winding number of the exported mesh, no rtree dependency."""
    a, b, c = (mesh.triangles - np.asarray(point)).transpose(1, 0, 2)
    la, lb, lc = (np.linalg.norm(t, axis=1) for t in (a, b, c))
    numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
    denominator = (la*lb*lc + np.einsum("ij,ij->i", a, b)*lc
                   + np.einsum("ij,ij->i", b, c)*la + np.einsum("ij,ij->i", c, a)*lb)
    winding = float(np.sum(2*np.arctan2(numerator, denominator)) / (4*np.pi))
    return abs(winding) > 0.5


def validate_mesh(path: Path, name: str, p: dict) -> dict:
    mesh = trimesh.load_mesh(path, process=True)
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"{path}: expected one mesh")
    w, d, h = (p[k] for k in ("width", "depth", "height"))
    probes = []

    def probe(label: str, point: list, expected_inside: bool) -> None:
        observed = inside(mesh, point)
        probes.append({"label": label, "point_mm": point, "expected_inside": expected_inside,
                       "observed_inside": observed, "pass": observed == expected_inside})

    if name == "cable_tie_mount":
        cw, ch, f = (p[k] for k in ("channel_width", "channel_height", "floor"))
        expected_volume = w*d*h-cw*d*ch
        for y in (0.01, d/2, d-0.01):
            probe("tunnel open through both Y ends", [w/2, y, f+ch/2], False)
        probe("floor intact", [w/2, d/2, f/2], True)
        probe("roof intact", [w/2, d/2, (f+ch+h)/2], True)
        probe("left wall intact", [(w-cw)/4, d/2, f+ch/2], True)
        probe("right wall intact", [(3*w+cw)/4, d/2, f+ch/2], True)
        opening = {"type": "tunnel", "width_mm": cw, "height_mm": ch, "open_ends": ["Y=0", "Y=depth"]}
    elif name == "wire_label_tag":
        sw, sd, left = (p[k] for k in ("slot_width", "slot_depth", "slot_left"))
        expected_volume = w*d*h-sw*sd*h
        for z in (0.01, h/2, h-0.01):
            probe("slot through thickness", [left+sw/2, d/2, z], False)
        probe("slot left ligament", [left/2, d/2, h/2], True)
        probe("slot right ligament", [(left+sw+w)/2, d/2, h/2], True)
        probe("slot lower ligament", [left+sw/2, (d-sd)/4, h/2], True)
        probe("slot upper ligament", [left+sw/2, (3*d+sd)/4, h/2], True)
        opening = {"type": "through slot", "width_mm": sw, "depth_mm": sd,
                   "left_mm": left, "bottom_mm": (d-sd)/2}
    else:
        wall, f = p["wall"], p["floor"]
        expected_volume = w*d*h-(w-2*wall)*(d-2*wall)*(h-f)
        probe("interior empty", [w/2, d/2, (f+h)/2], False)
        probe("top open", [w/2, d/2, h-0.01], False)
        probe("floor intact", [w/2, d/2, f/2], True)
        for point in ([wall/2, d/2, h/2], [w-wall/2, d/2, h/2], [w/2, wall/2, h/2], [w/2, d-wall/2, h/2]):
            probe("wall intact", point, True)
        opening = {"type": "open tray", "interior_mm": [w-2*wall, d-2*wall, h-f], "wall_mm": wall, "floor_mm": f}
    checks = {
        "finite_vertices": bool(np.isfinite(mesh.vertices).all()),
        "watertight": bool(mesh.is_watertight),
        "consistent_winding": bool(mesh.is_winding_consistent),
        "single_connected_body": len(mesh.split(only_watertight=False)) == 1,
        "positive_volume": bool(mesh.volume > 0),
        "bounds_match": bool(np.allclose(mesh.bounds, [[0, 0, 0], [w, d, h]], atol=1e-5, rtol=0)),
        "volume_matches_box_minus_void": bool(np.isclose(mesh.volume, expected_volume, atol=1e-4, rtol=0)),
        "opening_and_wall_probes": all(q["pass"] for q in probes),
    }
    result = {"name": name, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
              "bounds_mm": mesh.bounds.tolist(), "dimensions_mm": mesh.extents.tolist(),
              "volume_mm3": float(mesh.volume), "expected_volume_mm3": expected_volume,
              "vertices": len(mesh.vertices), "triangles": len(mesh.faces), "connected_bodies": len(mesh.split(only_watertight=False)),
              "opening": opening, "probes": probes}
    if result["status"] != "PASS":
        raise ValueError(json.dumps(result, indent=2))
    return result


def run_cli(cli: Path, args: list[str]) -> str:
    env = dict(os.environ, SOLIDCRAFT_GPU="cpu")
    completed = subprocess.run([str(cli), *args], capture_output=True, text=True, encoding="utf-8",
                               timeout=120, check=False, env=env)
    if completed.returncode:
        raise RuntimeError(f"SolidCraft exit {completed.returncode}: {completed.stderr}\n{completed.stdout}")
    return completed.stdout


def preview(cli: Path, out: Path, parts: dict) -> None:
    canvas = Image.new("RGB", (1800, 900), "#f0f4f8")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=18)
    draw.text((30, 20), "BENCH PREP v1 | mm | Flat bottom: Z=0 | Geometry preview; physical print NOT_RUN", fill="#183044", font=font)
    for i, name in enumerate(PART_NAMES):
        p = parts[name]
        x = 600*i
        for row, view in enumerate(("iso", "front" if name == "cable_tie_mount" else "top")):
            shot = out / f"{name}_{view}.png"
            run_cli(cli, ["snapshot", str(out/f"{name}.solidcraft"), "--out", str(shot), "--width", "580", "--height", "320", "--view", view, "--no-grid", "--no-axes"])
            with Image.open(shot) as im:
                canvas.paste(im.convert("RGB"), (x+10, 130+row*345))
            draw.text((x+20, 440+row*345), view.upper(), fill="#425669", font=small)
        draw.text((x+20, 75), name.replace("_", " ").upper(), fill="#183044", font=font)
        draw.text((x+20, 108), f"{p['width']} x {p['depth']} x {p['height']} mm", fill="#425669", font=small)
        if name == "cable_tie_mount":
            note = f"{p['channel_width']} x {p['channel_height']} mm tunnel; test 1 first"
        elif name == "wire_label_tag":
            note = f"{p['slot_width']} x {p['slot_depth']} mm slot; write on the flat plate"
        else:
            note = f"{p['wall']} mm walls / {p['floor']} mm floor; optional 1"
        draw.text((x+20, 840), note, fill="#183044", font=small)
    canvas.save(out/"preview.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solidcraft", required=True, type=Path, help="Existing solidcraft-cli executable")
    parser.add_argument("--parameters", type=Path, default=SOURCE/"parameters.json")
    parser.add_argument("--output", type=Path, default=ROOT/"models"/"bench-prep-v1")
    args = parser.parse_args()
    cli, out = args.solidcraft.resolve(strict=True), args.output.resolve()
    data = json.loads(args.parameters.read_text(encoding="utf-8"))
    if data.get("units") != "mm":
        raise ValueError("Only mm units are supported")
    parts = data["parts"]
    validate_parameters(parts)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/"validation.json", {"schema_version": 1, "status": "IN_PROGRESS", "units": "mm"})
    results = []
    for name in PART_NAMES:
        script = out/f"{name}.json"
        write_json(script, model_script(name, parts[name]))
        output = run_cli(cli, ["run", str(script), "--out", str(out/f"{name}.stl"), "--out", str(out/f"{name}.step"),
                               "--save", str(out/f"{name}.solidcraft"), "--results"])
        (out/f"{name}_build.json").write_text(output, encoding="utf-8")
        result = validate_mesh(out/f"{name}.stl", name, parts[name])
        result["files"] = {ext: {"path": f"{name}.{ext}", "sha256": sha256(out/f"{name}.{ext}")} for ext in ("json", "stl", "step", "solidcraft")}
        results.append(result)
    preview(cli, out, parts)
    report = {"schema_version": 1, "units": "mm", "status": "PASS", "generator": "SolidCraft 0.18.2 CAD + reloaded STL validation",
              "tool_sha256": sha256(cli), "python": sys.version.split()[0], "trimesh": trimesh.__version__,
              "source_sha256": sha256(Path(__file__)), "parameters_sha256": sha256(args.parameters),
              "parts": results, "limits": {"slicing": "NOT_RUN_BY_THIS_GENERATOR", "physical_print": "NOT_RUN", "strength_and_fit": "NOT_RUN", "printer_material": "Bambu H2D / PLA user confirmed; nozzle, plate and exact filament unconfirmed"}}
    write_json(out/"validation.json", report)
    print(json.dumps({"status": "PASS", "parts": [{"name": r["name"], "dimensions_mm": r["dimensions_mm"], "volume_mm3": r["volume_mm3"]} for r in results], "output": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
