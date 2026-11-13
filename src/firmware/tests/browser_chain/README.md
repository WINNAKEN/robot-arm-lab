# Browser cold Boot -> handoff -> Stop (controlled clock)

All production assets/core sources remain unchanged. The browser runs exact production HTML/JS, actual touch events and fetch against a loopback transport fixture and a LIVE actual C++ Owner/Boot/Run/Gate/codec/FakeCAN process. Actor begins cold with no session/lease/bootstrap/proof injection/fixture renew. Pairing and command auth/listeners are actual Owner public operations; status HTTP access is the fixture's set of credentials returned by actual pairing. Test-approved host profile and measuredfalse calibration do not change device approval defaults.

This is a selected CONTROLLED shared virtual-clock composition test. Playwright Date/timers and native fake-port ms start together; normal dispatch/reply logical latency is0. A transparent platform fetch/Response.json observer returns original promises/data and tracks host completion; MessageChannel drains microtasks without virtual timer jumps. See implementation-notes.md for this test instrumentation. It is not real wall-time phone/WiFi/ESP32 latency or full PB/motion/all-phase acceptance. Product50/250ms intervals/deadlines/auth stay unchanged. No movement is requested; FD0 throughout.

From repository root:

```powershell
powershell -ExecutionPolicy Bypass -File src/firmware/tests/browser_chain/run.ps1
node src/firmware/tests/browser_chain/test_bridge.cjs .dev/browser-chain-evidence/build/bridge.exe
$env:NODE_PATH='C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:PB_BROWSER='C:/Program Files/Google/Chrome/Application/chrome.exe'
node src/firmware/tests/browser_chain/test_browser.cjs .dev/browser-chain-evidence/build/bridge.exe NEW_OUTPUT_DIRECTORY
node src/firmware/tests/browser_chain/audit.cjs NEW_OUTPUT_DIRECTORY
py -X utf8 .dev/browser-chain-evidence/run_controls.py UNIQUE_CONTROL_DIRECTORY
```

Seven fixed cases: normal selected axes1/2, hidden/returned Stop while ACK/status held, offline Pending expiry, late grant receipt, actual queue-age50 denial then Stop, bad pairing. Hidden getter/event is explicitly synthetic DOM visibility, not OS background. First observable stopped slot chosen before send, no request retries or serial phase hunting. Old test-only renewal-age heuristic is removed, core guard unchanged. Core and historical DOM namespace/stop time are bound exactly; exact public verification line is checked (not the core_stop_verified suffix).

Actual forwarding controls: wrong valid asset; omitted Handoff with fake success; omitted Stop with fake success. Native core must detect missing phase/explicit stop BEFORE lease expiry; original before/after passes. No missingFD control claim for this no-move scope. Raw failures/early source copies/suites retained. Reviewed verdict and all limitations are canonical in `.dev/browser-chain-evidence/disposition.md` and l4-r1.md. Physical calibration unapproved, ring deferred, no hardware/flash/purchase/CAD/print.
