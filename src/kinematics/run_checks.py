"""Run the positive suite before four independently executed behavioral mutants."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = ROOT/".dev/joint-contract-evidence"


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    build = EVIDENCE/"build"
    build.mkdir(exist_ok=True)
    source = (HERE/"joint_contract.py").read_text(encoding="utf-8")
    mutations = {
        "zero-confusion": ("local_axis = axis(joint[\"axis_parent\"])", "angle += joint[\"display_pose_rad\"]\n        local_axis = axis(joint[\"axis_parent\"])"),
        "missing-si": ("[x / 1000.0 for x in local_mm]", "[x for x in local_mm]"),
        "wrong-frame-order": ("r = mm(r, mm(rotation(local_axis, angle), matrix(joint[\"reference_rotation\"])))", "r = mm(rotation(local_axis, angle), mm(r, matrix(joint[\"reference_rotation\"])))"),
        "j6-sign": ("local_axis = axis(joint[\"axis_parent\"])", "angle = -angle if joint[\"name\"] == \"J6\" else angle\n        local_axis = axis(joint[\"axis_parent\"])"),
    }
    cases = [("positive", source)]
    for name, (before, after) in mutations.items():
        if source.count(before) != 1:
            raise ValueError(f"Nonunique mutation anchor: {name}")
        cases.append((name, source.replace(before, after)))
    results = []
    for name, text in cases:
        module = build/(name+".py")
        module.write_text(text, encoding="utf-8")
        compile(text, str(module), "exec")
        env = dict(os.environ, CONTRACT_TEST_MODULE=str(module))
        process = subprocess.run([sys.executable, str(HERE/"test_contract.py")], env=env,
                                 capture_output=True, text=True, encoding="utf-8", timeout=120)
        (EVIDENCE/(name+"-output.txt")).write_text(process.stdout+process.stderr, encoding="utf-8")
        results.append({"name": name, "compile": "PASS", "exit": process.returncode,
                        "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest()})
        (EVIDENCE/"checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        expected = 0 if name == "positive" else 1
        if process.returncode != expected:
            raise ValueError(f"Unexpected test exit: {name}: {process.returncode}")
        if name != "positive" and ("AssertionError" not in process.stderr or "ERROR:" in process.stderr):
            raise ValueError(f"Mutant must fail assertions, not infrastructure: {name}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
