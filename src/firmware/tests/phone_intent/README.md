# Phone control intent lifetimes — 028 offline candidate

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File src/firmware/tests/phone_intent/run.ps1 -Mutations
```

Production PhoneControl separately owns current authority/control epoch, a one-shot explicit Handoff acquisition record, and numeric angle context/revision. Calibration capability changes cancel the numeric context and ticket, without clearing an existing lease or the explicit Handoff intent. Normal readiness changes do not cancel the lease. Boot/axis/fault/Stop/hide/disconnect/stale events still invalidate the relevant authority. The existing 700ms Handoff and 600ms status limits are retained.

Only the user's Handoff action creates an acquisition record. Supported same-boot phase transitions preserve it; Ready consumes it once before sending Acquire. Delayed or cancelled responses cannot restore it. Numeric context stays locked until its asynchronous operation finishes, even after cancellation; Stop never releases the normal request's busy flag. A local cancellation blocks subsequent requests and does not promise to undo a request already delivered to CAN.

`test_ui.cjs` drives actual production JS with explicit simulated snapshots/transport. `test_bridge.cjs` uses actual JS command bytes from NeedsMaintenance through maintenance/unloaded/disable/drive/enable, Handoff, Acquire and typed angle motion into actual Owner/Boot/Run/Gate/codec/FakeCAN. No sequence or lease is injected into JS. Pairing response and transport are fixtures. The C++ bridge extracts the exact fixture prefix and status function from unchanged historical phone_angle tests at checked unique boundaries; all production C++ is compiled directly. Generated fixture bytes and command logs are retained with evidence.

Positive fixtures cover both axes and measured/unmeasured cases, an ACK held until Run readiness, and Stop while that ACK is held. A separate exact boundary schedule verifies that a previously ready snapshot may become inadmissible before Acquire: the server denies it and the client does not retry. This is separate from the favorable admission schedules, not a weakened timeout or proof threshold.

Three JS mutants must pass syntax checking and fail behavioral assertions: global clear on capability change, erase Handoff intent on generation transition, and ignore numeric revision (including an ABA capability/joint change). The runner explicitly exits0 only after all positives and expected mutant failures pass.

Physical calibration/hardware approval stays false. Only calibrated 100-pulse relative displacements are supported; arbitrary or absolute targets, automatic segmentation/retry, real browser/mobile/Wi-Fi/SDK target/physical CAN/flash remain outside this proof. Ring geometry remains deferred. Prior027 BLOCK/EXHAUSTED is preserved; independent028 review determines acceptance and inherited recurrence thresholds still apply.
