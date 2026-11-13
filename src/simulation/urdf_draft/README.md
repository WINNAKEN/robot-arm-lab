# 040 URDF draft generator

Creates `models/robot-arm-urdf-v1/` from the unchanged latest full v2 native CAD and its fresh31-body3MF export. All mass/COM/inertia/limits/actuator values are simulation assumptions. No Isaac import, training, calibration, motor operation, flash, purchase or CAD modification.

```powershell
py -X utf8 src/simulation/urdf_draft/build.py
py -X utf8 src/simulation/urdf_draft/verify.py models/robot-arm-urdf-v1
py -X utf8 src/simulation/urdf_draft/test_draft.py
```

Builder output is write-once; use `--out NEW_DIRECTORY` for another attempt. Status is written under `.dev/urdf-draft-evidence/build-status.json` before input/core/preview dependencies, and a writable ordinary failure records FAILED and exits nonzero. Existing artifacts are not reused as the new attempt. Storage failure/forced termination is outside that status guarantee. Original/native/kin/core pins and producer/input hashes distinguish accepted inputs from other revisions. A Python-module import alone does not read repository inputs or initialize a device.

Visual meshes are link-local metres with scale1; q0 is the CAD displayed pose, not physical zero. Seven links, six revolute joints,31bodySTLs; no gripper or physical motor mapping. Approximate AABB collision/box inertia must be replaced/checked before dynamics or sim-to-real. This validates export/coordinates, not ring topology/strength/collision-free motion. See package README and evidence disposition for limitations.

The approved021 math code is used as an FK reference only, read after BUILDING and pinned to its accepted source bytes. New URDF FK is reparsed from the written XML. Producer changes require a new package; public verify checks actual files, hashes and inputs. No new universal or historical blocked startup/geometry acceptance is implied.

The canonical inertial/collision frames have zero RPY. Each per-link assumption row is checked against the written STL bounds and URDF mass/COM/inertia. The 1e-7m bound comparison accommodates float32 STL serialization; the actual-STL inertia check propagates that length error through the box formula, while the recorded box/formula remains checked to 1e-12 kg m². These are file-conversion tolerances, not physical accuracy claims. Re-sealed semantic corruptions test these checks independently of manifest hashes.
