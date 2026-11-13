# Layout joint contract (020)

No device/CAD/network execution, third-party imports or package installation.
From the project root using the installed Windows Python launcher:

```
py src/kinematics/run_checks.py
py src/kinematics/joint_contract.py build
py src/kinematics/joint_contract.py verify
```

`build` reads six fixed repository sources and the bounded native ZIP document.
JSON nesting is limited to64, numbers must fit finite floats, and native archives
support unencrypted stored/deflated documents only. The ring reference is tied
to the actual active native sketch/revolve and matching command profile as well
as dimensions; it is not inferred from dimensions alone.
It creates a fresh immutable `outputs/joint-control-v1/runs/<run_id>/` bundle.
`current.json` is BUILDING/FAILED/PASS, never an implicit fallback to an older
successful result. `verify` checks current identity, manifest, current source
hashes, producer hash and all output bytes. Run verify before using a snapshot.
Historical Markdown is explicitly a snapshot, not a live acceptance indicator.

The contract uses **canonical right-hand display-delta radians**. Delta0
matches the static CAD display pose; geometric0 subtracts that pose's angles.
SolidCraft native positive-angle mapping is NOT_RUN/null even though all static
native values are0. The native flip flag and housing output-side sign cannot
establish the motor sign. Link frames are new joint-centred canonical frames,
not the CAD's identity-transform occurrence frames. Mesh re-expression is a
later export step. J6 origin/ring reference are not a calibrated TCP.

Motor IDs/reduction/sign/zeros/encoder scale and physical limits/dynamics remain
unknown. Two ordered bench motors are not automatically assigned to J1/J2.
No firmware change, six-axis transmission, physics simulation or RL execution.

The tests include independent straight-chain expectations, reference geometry,
mixed/random rigid chains, position and **orientation** finite derivatives for
every joint, malformed inputs and current-result lifecycle/tampering in temp
copies. J6's point derivative can be0 while its orientation derivative is not.
Four mutated copies must compile then fail assertions after the unmodified
suite succeeds. Test-only `CONTRACT_TEST_MODULE` selects these local generated
copies; production does not load a module from user data. Raw text results live
in `.dev/joint-contract-evidence/`; generated module cache lives under `build/`.

Independent L4 and actual CAD runtime rotation/motor signs/physical acceptance
remain separate from the author's test results. Plan:020; later roadmap:019.
