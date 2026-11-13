# Stop capability lifetime — offline host candidate

033 separates movement authority, cancellable result observation, numeric intent and an immutable in-memory Stop identity. hide/clear/stale/transport loss/failed Stop/receipt adoption cannot erase the continuing Stop identity. Only an authenticated ordered status request started with the same identity may retire it: matching-axis global Terminal with monotone generation, or changed boot. Stopping retains read-only recovery authentication through final verification/manual-cut outcome. It does not authorize movement, renew, automatic Stop or retries. Page/process loss is outside the in-memory guarantee.

Run from repository root:

```powershell
powershell -ExecutionPolicy Bypass -File src/firmware/tests/stop_capability/run.ps1
node src/firmware/tests/stop_capability/test_ui.cjs
node src/firmware/tests/stop_capability/test_owner.cjs .dev/stop-capability-evidence/build/bridge.exe NEW_OUTPUT_DIRECTORY
```

The test-only A credential/body envelope exercises actual Owner authentication. Actual Boot setup is the preserved032 public schedule, driven through production JS commands/responses; no client seq/lease/Ready/Acquire injection. Pair response is the existing seeded fixture. It is not new DOM/network evidence. Existing server/Gate/CAN/HTTP remain unchanged.

Controls: `.dev/stop-capability-evidence/run_controls.py` uses predecessor and three syntax-valid mutants, four intended assertion failures with new originals passing before/after. Its controls directory must not already exist; original evidence is append-only.

Browser runner is a new032 harness copy, selected `--scenario=handoff-stop` only. Planned DOM visibilitychange uses a document.hidden getter fixture; it would exercise actual DOM handlers but is NOT actual OS/tab background behavior. In browser-001 it never reached that injection: setup timed out before disable-all. Thus new DOM cancellation acceptance is NOT_RUN/NOT_ACCEPTED. No retry/phase hunting was performed. Full PB030/032 acceptance remains OPEN.

Final author/independent findings and exact status are in `.dev/stop-capability-evidence/disposition.md` and `l4-r1.md`. All physical approvals remainfalse; calibration unapproved, ring deferred. No flash/device/purchase/CAD/printing.
