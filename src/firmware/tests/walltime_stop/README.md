# Real host elapsed-time cold Boot / HTTP / Stop test — candidate

Read `.dev/walltime-stop-evidence/disposition.md` and final review before interpreting outputs. This is a mobile-size Chromium viewport on one PC, loopback transport and actual unchanged Owner/Boot/Run/Gate/codec with FakeCAN. It is not a physical phone/WiFi/ESP32/CAN/normal-Run stop test. No calibration, enable, movement, grants or maintenance commands are issued.

Native uses actual steady_clock and Windows high-resolution one-shot waitable1ms timer. No W/clock setter, backfill or past-ms polls. One control thread owns all core/fake state; reader records actual monotonic command receipt. The fake port clock is sampled at poll entry and held during synchronous fake API work; this does not measure target RTOS/API WCET or electrical timing. Actual gaps remain observable and can fault the unchanged>=10ms core guard. No timer-creation/wait fallback or global timer-resolution change.

`common.inc` is the exact existing035 prefix before main; `metrics.inc` is its diagnostics branch with continue→return. BootFake retains test-approved host profile and calibration-measuredfalse. Product/physical approval defaults are untouched. Serializers carry actual core fields; separate T metadata records pre-admission state and timestamps. Browser Date/timers are unmodified; fetch/JSON observation returns original promises/data and records performance.now. HTTP holds run outside native RPC ownership.

Commands from repo root (PowerShell7 is required to retain native stderr on compile failures):

```powershell
& 'C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe' -NoProfile -File src/firmware/tests/walltime_stop/run.ps1
$env:NODE_PATH='C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
node src/firmware/tests/walltime_stop/test_browser.cjs .dev/walltime-stop-evidence/build/bridge.exe NEW_DIRECTORY all
```

These are reproducibility commands, **not authorization to extend the exhausted finite037 author-run/review budget**. Original001 failed because generic sleep1 wakes16–17ms. Highres002 has5 PASS/1FAIL; held-replies observer metadata readiness race remains. Proposed patch is saved but not applied/tested. Do not silently rerun to obtain a favorable timing result. Product stop paths observed in passed cold cases require manual power cut; never label them verified physical stopping.

Active-stage watchdog20s closes browser context; navigation/actions have2.5s limits. Native RPC and teardown have separate bounded waits. This is not a guaranteed hard20s total process deadline. Screenshots/JSON preserve raw failures. External URLs blocked except test-only redirect of Stop address to loopback; no claim about real SDK CORS/sockets.
