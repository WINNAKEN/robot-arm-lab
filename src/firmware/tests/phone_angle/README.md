# Phone numeric relative angle — offline candidate

Run `powershell -ExecutionPolicy Bypass -File src/firmware/tests/phone_angle/run.ps1 -Mutations` from the repository root. Uses the existing local Zig toolchain and Node; no board or network is contacted.

The actual web client sends `v2|boot|phase|seq|request|joint-step|lease|ticket|axis|joint|deg-or-rad|signed-decimal`. Production parsing and Owner authentication feed the existing typed joint-step path, Gate, MKS codec and CanPort. Version 1 direction buttons retain their existing protocol.

Values describe a relative displacement, not an absolute target. Only the calibrated equivalent of exactly 100 pulses is admitted; other magnitudes are rejected without rounding, splitting or retry. Deg is CAD display displacement; rad is core displacement, without the geometric pose offset. Physical calibration stays unapproved by default. Synthetic calibration exists only in these tests.

`angle_available` describes immutable calibration capability and survives ordinary `ready=false` during motion. Starting a numeric operation additionally requires readiness, selected joint, a fresh Run snapshot and lease authority. The whole Arm/Ticket/JointStep sequence captures its context, excludes overlapping commands and cancels on context changes. Stop stays available.

`test_angle.cpp` exercises actual production parsing/Owner/Boot/Run/Gate/codec with FakeCAN. `test_ui.cjs` exercises the production JavaScript with a simulated transport. `test_bridge.cjs` sends its exact production JavaScript request bytes through the C++ fixture, including actual lease renewal while moving. Pairing/bootstrap and transport are fixtures, not real Wi-Fi or HTTP. Existing HTTP and runtime tests separately compile their production handlers against SDK stubs.

Real phone/browser, Wi-Fi, embedded target, flash, physical CAN, motor sign, ratio, encoder, zero, limits and stopping behavior remain NOT_RUN. This unit does not approve calibration, arbitrary-angle motion, trajectories, ring geometry, printing or purchases.
