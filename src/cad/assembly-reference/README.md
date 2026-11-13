# Thor saved-geometry diagnostic

`prepare_thor.py` reads the pinned Thor ZIP/XML/BREP data without invoking FreeCAD, Python proxies or macros. It is an investigation tool, **not a successful assembly exporter**. For this snapshot, SolidCraft 0.18.4 rejects some parts and also omits faces on accepted parts. The installation directory is named 0.18.2, but the CLI reports 0.18.4. See `models/six-axis-reference/THOR_DIAGNOSTIC.md`.

Use an existing Python environment with numpy and trimesh, and pass the existing SolidCraft executable explicitly:

```powershell
python src/cad/assembly-reference/prepare_thor.py --solidcraft <solidcraft-cli.exe> --inventory
python src/cad/assembly-reference/prepare_thor.py --solidcraft <solidcraft-cli.exe> --probe
```

`--inventory` writes a shape occurrence mapping and minimal cached-shape archives under `.dev/assembly-evidence/conversion/`. It is specific to this source snapshot: scaled links, arrays, cycles and unsupported LinkTransform values fail explicitly. Final Body geometry is selected once; hidden intermediate objects and datum shapes are excluded.

`--probe` measures the importer using one saved screw shape. The synthetic parent-placement probe is expected to reveal ignored parent placement; it is a limitation observation, not a pass criterion.

`--diagnostic` reproduces the bounded import investigation. Each CLI call has a 120 second timeout; no new call starts after a 300 second overall budget. It can therefore finish a final in-flight call after 300 seconds. All failures are recorded. Native checkpoints stay under `.dev`; this mode does not emit user-facing full assembly CAD. Warning-bearing accepted imports must be inspected; an exit code of zero is not CAD fidelity evidence.

The diagnostic script does not print, control a robot, access the network, install tools, alter the upstream packages, or change SolidCraft resource limits.
