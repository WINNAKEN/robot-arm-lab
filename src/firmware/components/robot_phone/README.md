# Phone execution preparation (ST3-D)

`Owner` is the only owner of the exact CanPort, actual Boot Supervisor and actual
BenchRun. HTTP has only copied envelopes/results/snapshots. `wire.cpp` is shared
by target and host, including the 1024-byte raw-header guard. The target wrapper
is `main/phone_http.cpp`; actual queue pump, early entropy initialization and
SoftAP composition are in `main/phone_runtime.cpp`. See accepted plan018.

The default entry remains inactive. The separate
`CONFIG_ROBOT_LAB_PREPARED_RUNTIME` entry links the actual task and SDK routes,
but every physical profile approval is a source constant false. Menu approval
records and HTTP cannot change them. Host SDK stubs never execute device/network
APIs. Target compile/link is separate evidence, and on-board Wi-Fi/CAN/torque/
motion/response bounds remain NOT_RUN.

## Wire and identity

Exactly `v1|boot|phase|seq|request|op|lease|ticket|axis|direction|unloaded`, ASCII,
maximum256 bytes. Operation words (no cross-core numeric casts): `maintenance`,
`maintenance-renew`, `unloaded`, `disable-all`, `finish-maintenance`, `drive`,
`enable-selected`, `handoff`, `acquire`, `renew`, `arm`, `ticket`, `move`,
`release`, `stop`. Axis is checked by the actual immutable core profile; the
client uses its selected axis. IDs are uint64 decimal strings in JSON and JS.
Wire errors/results never replace the separately copied first core fault/time.

Actual target draws all boot/principal/pairing/session/WPA2 values from
`esp_fill_random`, bracketed by the pinned SDK's supported
`bootloader_random_enable/disable` before RF/ADC initialization. The target has
no deterministic fixture credential. Serial onboarding deliberately prints
only the WPA2/pairing values once; routine status exposes no credentials. Two
paired slots are retained for the boot lifetime. A third pairing receives
SessionFull: explicitly reboot to reclaim slots. No reconnection restores
authority, and status reads never renew it.

## Ingress and ownership

Normal HTTP80 (Host exactly192.168.4.1) and Stop HTTP8081 (Host
exactly192.168.4.1:8081) use different SDK tasks/control ports and single command
queues. POST/Stop OPTIONS require Origin exactlyhttp://192.168.4.1; authenticated
same-origin GET status may omit Origin, but a present wrong Origin is rejected.
Stop OPTIONS allows only POST and the exact content-type/session credential
header list. No wildcard/reflected Origin. Both have per-socket actual100ms
receive/send timeval settings, absolute250ms header/body deadline, bounded
results50ms and mandatory response Connection:close/session-close trigger. The
same connection's finished flag rejects any subsequent handler even if SDK had
buffered pipeline bytes. Raw duplicate/case-variant Host, Origin, authentication,
Content-Length and Content-Type are rejected before SDK header evidence loss;
Transfer-Encoding, folds, NUL, invalid CRLF and oversize headers fail closed.

The control task retains pending job IDs across ticks, prioritizes Stop,
invalidates queued normal work on accepted Stop and drains correlated results.
Ordinary enqueue age must be<50ms. A late Stop still calls the existing actual
core stop immediately and latches `queue_stop_late` plus distinct
`AdapterFault::StopQueueLate`; it never restarts an existing stop time. That
adapter fault permanently denies ordinary commands and makes effective
stop_verified=false/manual_power_cut_required=true, even if the separately
copied `core_stop_verified` later becomes true. The underlying core fault,
first-fault time and original actual stop_at remain verbatim. Queue/network
delay is separate from core stop acceptance
and no physical emergency-stop bound is claimed. Ordinary rate10/s burst4 per
paired session; independent authenticated status5/s. Stop has neither ordinary
rate dependency nor authority requirement. Network/Stop-listener denial of
service is outside the availability claim.

## Bounded Handoff readiness wait

An explicit Handoff authenticates the existing Boot owner once and consumes one
wire seq/request/rate token. If actual `take_evidence` is not yet ready, the
owner waits across normal1ms ticks only until immutable enqueue+49ms. It keeps
polling actual Boot, prioritizes Stop and checks the phase fence; it does not
spin or extend the grant/config/lease. The only repeated call is the core's
readiness/mint API; successful capability mint and Run consumption occur once.
No FD/F3/Acquire/Arm/Ticket/Move is retried. Missing readiness returns Busy and
the UI clears authority/renewal. This is a bounded readiness wait, not a command
retry. The actual stub pump proves deferred18ms delivery,49ms Busy, Stop
cancellation and late-job rejection. There is no claim every Granted instant
offers readiness within49ms: unfavorable explicit actions can be rejected.

The UI's labelled single user action explicitly requests both Handoff and the
first new normal Acquire. Only that saved intent may send Acquire once after
actual Run Ready, using the new generation. It expires after700ms, or on any
error/hidden/stale/disconnection; no retry or generic phase/reconnect acquire.
The original800ms drive grant remains unchanged. A successful fake-wire trace
uses an explicit action600ms after Granted, with foreground renewal beforehand;
this trace is not a universal response-time or mobile usability guarantee.

The page displays actual position validity/value/age and oldest actual config
read, lease/phase/core first fault, queued versus accepted and separate
stop_verified/manual_power_cut_required. Unknown positions are not zero.
Unchanged owner timestamp for600ms, hidden page, error or changed generation
clears local authority/tickets. The fixed100pulse button sends Arm/Ticket/Move
only after each actual response. Always-visible software Stop is distinct from
unloaded confirmation, torque disable and a physical emergency stop.
