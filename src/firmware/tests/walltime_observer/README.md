# 038 observer completion and data-only controls

Read `.dev/observer-controls-evidence/disposition.md` for actual acceptance. Existing037 remains frozen BLOCK/exhausted. Product code, native actor, high-resolution wait, original timing guards and physical approval defaults are unchanged. No real device/network/calibration/motion is used.

The new fixture publishes an owned, recursively frozen `completed` only after native result + actual audit + actual post snapshot. Consumers cannot see partial result/audit properties. Audit/post failures publish no completion and fail. Pairing/status/Stop return actual product JSON; only the explicit missing-forward test fixture supplies fake success while preserving actual native snapshots/audit.

`oracle.cjs` tests Stop causality using data alone, without a control selector or forwarded flag. An actual Stop must newly bind positive accepted_at to actual post.stop_at and matching native audit/namespace. Wrong asset is checked from actually received bytes. Missing forwarding runs the same browser oracle; no unconditional negative assertion.

Environment obstruction is emitted only at named preconditions with native Time8+prior stop/fault timestamp and measured gap>=10. A large cumulative gap alone never converts assertion failure into environment. Original mismatches, missing metadata and unknown errors remain FAIL. Environmental preemption is NOT_REACHED/credit0, never a passed Stop. Raw suite summary FAIL means not every required case passed; individual report verification/environment fields distinguish the cause. No retry to obtain favorable timing.

Run commands from repository root, with unique new evidence directories:

```powershell
node src/firmware/tests/walltime_observer/test_observer.cjs
node src/firmware/tests/walltime_observer/test_consumer.cjs NEW_OUTPUT_JSON
# Native builder is exactly the unchanged037 builder; no flash command.
& 'C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe' -NoProfile -File src/firmware/tests/walltime_stop/run.ps1
$env:NODE_PATH='C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
node src/firmware/tests/walltime_observer/test_browser.cjs .dev/walltime-stop-evidence/build/bridge.exe NEW_SUITE_DIRECTORY all
node src/firmware/tests/walltime_observer/test_controls.cjs NEW_CONTROL_DIRECTORY
```

Each author/independent reviewer has one fixed full suite and one control bracket for038, not unlimited permission to repeat these commands. A native host scheduler violation is recorded, not repaired by tuning timers/priority/guard. Unit deferred promises are synthetic concurrency tests of the actual fixture handle, not wall-time acceptance. All reached cold stops can require manual power cut; they are not proof of physical braking, verified torque removal or normal Run stop. Mobile viewport+loopback is not actual phone/WiFi/ESP32 latency.

L4 R1 found malformed completion could be classified as environment before data validation. Final consumer validates complete schemas, namespace/axis, result errors and consistent prior-Time evidence before classification. Targeted `test_consumer.cjs` executes the exact current consumer source block, including deterministic malformed-with-Time combinations; optional additional directory arguments replay already-recorded data without launching a browser. Post-R1 changes have no new whole-browser run; original live facts are preserved separately from final deterministic consumer evidence.
