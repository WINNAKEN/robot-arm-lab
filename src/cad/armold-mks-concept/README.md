# Generation and verification

Use the already installed SolidCraft CLI and PrintForge Python environment; no package installation is required. Units are millimetres. Model source is original geometric construction, with public reducer mechanisms used as references only.

1. Edit `parameters.json` after obtaining actual motor/driver dimensions.
2. Run `build_concept.py --cli <absolute path to solidcraft-cli.exe>`.
3. Run the saved `static-check-commands.json` through the CLI using the regenerated native as `--in` and `--results --json-out .dev/armold-concept-evidence/build/static-check-result.json`. This checks the displayed pose, then drives J1 by +5 degrees on an unsaved in-memory copy only.
4. Run `validate_concept.py` to compare all69 native B-rep solids with analytic bounds/volumes, check the revolute graph and verify the downstream FK probe. The native display remains unchanged.
5. Optional `build_reducer_schematic.py --cli <absolute path>` makes a separate nonfunctional exploded reducer principle model, using blank smooth discs, a pin ring, an eccentric cue and output flange. It does not generate a cycloidal tooth profile or a working reducer.

The example/native main assembly is69 B-rep bodies with actual sketch/extrusion/cut history. Five native parameter names drive motor/driver/connector profile dimensions. Global joint locations and fixed sketch origins regenerate from this source input; editing an isolated native dimension does not automatically resolve all mounting or placement changes.

Public reference documents are under `docs/references/packages/01/mechanical_refs/Faze4/upstream/`. The root evidence `reference-review.md` and `source-integrity-before.json` record the exact received source snapshot. The actual reference license is preserved in the output; README's MIT badge conflicts with that CERN-OHL-S-2.0 file. No paid Armold CAD or whole reference arm geometry was copied. No original source macro, hardware, printer or purchase operation is executed by these generators.
