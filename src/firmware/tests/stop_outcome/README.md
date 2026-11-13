# Last terminal observation — offline evidence consumer

034 keeps a private immutable whitelist of last authenticated Terminal facts separate from live snapshot/auth/StopBinding. It survives disconnect/offline/hidden/stale/new pairing/nonterminal newboot. It never grants current safety, connection freshness or control permission. Valid later Terminal replaces one record; there is no durable storage, alarm ledger or human acknowledgment feature. Refresh/process restart loses memory. Missing optional facts are unreported, never safe false.

From repository root:

```powershell
node src/firmware/tests/stop_outcome/test_ui.cjs
$env:NODE_PATH='C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:PB_BROWSER='C:/Program Files/Google/Chrome/Application/chrome.exe'
node src/firmware/tests/stop_outcome/test_browser.cjs NEW_OUTPUT_DIRECTORY
py -X utf8 .dev/stop-outcome-evidence/run_controls.py UNIQUE_RUN_NAME
```

Native source payload: committed033 independent-r1/owner/pending.json final. Reconfirmed equal to034 freshly compiled actualOwner132 run. Unit transport/pair response are mocked. Browser serves exact production HTML/JS over loopback, actual Chromium fetch/timers/events/render; status is RECORDED NATIVE OUTPUT, not live Owner in that browser. Manualcut=true/verifiedfalse diagnostics and later-boot variants are explicit synthetic protocol samples. No private client state/auth/lease injection into browser. The old fragile Boot operator setup is not part of this consumer test and remains unresolved, not waived.

Author57 JS checks, actual DOM13 checks, five intended behavioral controls (four JS incl predecessor, one real DOM) and appropriate regressions are detailed in `.dev/stop-outcome-evidence/author-summary.md`. L4 verdict/disposition is authoritative; do not infer full control/hardware approval. Physical calibration remains unapproved and ring deferred.
