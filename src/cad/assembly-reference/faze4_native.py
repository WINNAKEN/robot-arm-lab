"""Create a static, coloured SolidCraft mesh reference with the installed CLI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

from faze4_build import ROOT, OUT, EVIDENCE, PALETTE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    args = parser.parse_args()
    provenance = json.loads((OUT / "provenance.json").read_text(encoding="utf-8"))
    names = [link["link"] for link in provenance["links"]]
    commands = [{"command": "file.insert_mesh", "params": {
        "path": (OUT / "faze4-zero-pose-metres.glb").as_posix(),
        "name": "Faze4 6-axis reference - MKS fit unverified", "up": "z"}}]
    commands.extend({"command": "appearance.assign", "params": {"bodies": [name], "color": color[:3]}}
                    for name, color in zip(names, PALETTE))
    commands.append({"command": "component.list", "params": {"compact": True, "bodies": True}})
    script = EVIDENCE / "native-import.json"
    script.write_text(json.dumps({"commands": commands}, indent=2), encoding="utf-8")
    native = OUT / "faze4-six-axis-reference.solidcraft"

    def run(label, *cli_args):
        result = subprocess.run([str(args.cli), *map(str, cli_args)], cwd=ROOT,
                                capture_output=True, text=True, timeout=120)
        (EVIDENCE / (label + "-stdout.txt")).write_text(result.stdout, encoding="utf-8")
        (EVIDENCE / (label + "-stderr.txt")).write_text(result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{label}: {result.stderr}")

    run("native-import", "run", script, "--save", native, "--results", "--json-out", EVIDENCE / "native-import-result.json")
    run("native-eval", "eval", native, "--json-out", EVIDENCE / "native-eval.json")
    for view, filename in [("iso", "iso.png"), ("front", "front.png"), ("right", "side.png")]:
        run("snapshot-" + view, "snapshot", "--in", native, "--out", OUT / filename,
            "--view", view, "--width", "1600", "--height", "1200", "--no-grid", "--no-axes")
    report = json.loads((EVIDENCE / "native-eval.json").read_text(encoding="utf-8"))
    actual = {body["name"]: body for body in report["bodies"]}
    comparisons = []
    assert set(actual) == set(names)
    for link in provenance["links"]:
        body = actual[link["link"]]
        expected = np.array(link["world_bbox_m"]) * 1000
        observed = np.array([body["bbox"]["min"], body["bbox"]["max"]])
        delta = float(np.max(np.abs(observed - expected)))
        comparisons.append({"link": link["link"], "max_bbox_delta_mm": delta,
                            "bbox_matches_at_0_001_mm": delta < .001,
                            "triangles": body["faces"], "triangles_match": body["faces"] == link["triangles"]})
        assert delta < .001 and body["faces"] == link["triangles"]
    hashes_unchanged = all(hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
                           for entry in provenance["source_files"])
    assert hashes_unchanged
    validation = {"static_reference_only": True, "native_bodies": len(actual),
                  "original_URDF_joint_count": 6, "native_importer_rigid_attachments": 7,
                  "attachment_note": "Importer rigid attachments are static geometry links, not URDF kinematic joints",
                  "source_hashes_unchanged": hashes_unchanged, "per_link_comparisons": comparisons,
                  "mass_note": "Native default-material mass is not actual robot mass and is not validated",
                  "GUI_display": "NOT_RUN: root opens GUI", "physical": "NOT_RUN"}
    (EVIDENCE / "native-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "native-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
