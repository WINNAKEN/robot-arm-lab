# Offline ST3-D tests

From the project root, PowerShell:

```
& src/firmware/tests/phone/run.ps1 -Mutations
& src/firmware/tests/phone/run-http.ps1
& src/firmware/tests/phone/run-runtime.ps1
& src/firmware/tests/phone/run-ui.ps1
```

All C++ builds use existing project-local Zig, strict C++17
`-Wall -Wextra -Werror -pedantic`. Node uses the installed Node executable.
Scripts only write ignored `.dev/phone-runtime-evidence/build`; they do not
discover/access devices or start Wi-Fi/network/SDK on host. The two production
SDK translation units compile against explicit stub include paths.

- `test_phone.cpp`: strict parser/header/auth/phase/replay/rates/retained slots,
  stale normal/Stop priority/result correlation, latched late-Stop adapter
  safety failure with underlying core truth preserved, actual BootFake wire through
  Owner→Supervisor→real evidence→BenchRun, actual repeated FD beyond4s and lease
  expiration/no auto resume. Three compiled behavioral mutants independently
  bypass credential authentication, omit phase fence and reorder normal before
  Stop. Each must compile0 and fail1; failing assertions are expected evidence.
- `test_http.cpp`: actual production phone_http.cpp and linker-symbol assets
  embedded from the exact tracked web sources using assembly incbin. Both
  actual server configurations/URI handlers/open_fn/recv override run against
  stubs. Tests assert100ms socket settings, fragmented duplicate rejection
  before dispatch, Host/Origin/CORS/preflight, browser GET-without-Origin,
  withheld ordinary body/result allowing independent Stop handler,250ms
  absolute time and wrong/late result identities. This is a concurrency
  boundary model, not an actual TCP/FreeRTOS scheduler measurement.
- `test_runtime_wrapper.cpp`: includes the actual production phone_runtime.cpp
  and real portable cores, substituting only SDK queues/clock/port/Wi-Fi/RNG.
  Actual pump retains deferred Handoff job across ticks, delivers after18ms,
  cancels with independent Stop, rejects at49ms, times out at50ms and never
  reuses a late result. Actual startup ordering checks enable entropy, all RNG
  draws, disable entropy before Wi-Fi and source-false physical approvals.
  Stub xTaskCreate records the task; no real network or RTOS task starts.
- `test_ui.cjs`: explicit simulated status models, BigInt/string IDs, move
  sequence error and hidden/Stop cancellation, no reconnect/phase acquire,
  foreground-only renewal and explicitly combined Handoff+firstAcquire.
  Browser rendering/mobile usability is NOT_RUN.

The trace's fixture timing is an existence test of a handset-like explicit
sequence, not a guarantee that arbitrary Handoff timing will be accepted.
Unfavorable readiness is Busy, and no UI retry is added. Production assumptions
and retained-session limitation are in the component README.

Preserved diagnostic failures include raw phone-failure01–07 logs, initial
HTTP/runtime stub compile failures and Handoff timing-sweep logs. A failed
compile is never counted as mutant detection. Final result JSONs contain exact
executable hashes. Target builds/census/symbol/embedded byte verification and
independent L4 are separate parent-owned gates.
