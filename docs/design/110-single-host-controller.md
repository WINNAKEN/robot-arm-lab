> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 110 — 같은 호스트 controller로 시계 변경 경로 제거

2026-11-04 KST. 사용자 「결함두건을 포함해서 해결진행해」에 따른 신선 재설계다. [조사](../../_research/110-single-host-controller.md), [원109 최종 BLOCK](../../outputs/relative-clock-align-109/review/L4-r2.json)을 입력으로 한다. 원109 L2/L4 2/2 종결·소진·실패·미해결을 수정하거나 R3로 재개하지 않는다.

## 해결할 의무와 선택

1. **109-L4-R1-F2 actual 5초 cap**: OS 시계를 바꾸지 않는다. 새 실행 폐쇄에 SetSystemTime/SetLocalTime/시간서비스 변경과 UAC가 없도록 한다. 실제 보정량0을 새 구조에서 입증한다. last-userspace 값만 제한하는 것으로 원 actual cap을 완화하지 않는다. 원109의 setter 결함은 과거 OPEN으로 보존한다.
2. **109-L4-R2-WIN32-F1 pending launch**: ShellExecute/runas와 launch thread를 제거한다. 새 정상 사용자 자식은 main thread의 동기 CreateProcessW에서 JOB_LIST 속성으로 생성 순간 Job에 속한 채 suspended로 만든다. 실제 handle·배속·기한을 확인한 뒤 resume한다. 생성 호출이 돌아오기 전을 terminal로 게시하지 않는다. 반환 전 상위 사망에서도 마지막 비상속 Job handle이 닫혀 자식이 남지 않는지 실제 관측한다.
3. **추가 승계 배선**: 원108 literal의 admission 누락 의심을 실제 생성 caller로 확인하고 새110은 supervise/native의 다섯째 인자를 전달한다. export는 None이다. SDK 없이 기록용 entry로 양성/음성 대조한다.

별도 controller와 SDK를 기존 Isaac PC 안에서 실행해 같은 OS wall/monotonic 시간축을 쓴다. 현재 PC는 준비·전송·회수만 한다. 원108 자체는 보호된 읽기 입력이다. 전역 monkeypatch, PATH ssh shim, 과거 PASS/인증서/실패 영수증의 새 실행 승격은 없다.

## 소유·등급·예산

새 mutable source/harness는 정확히8개다. WinJob/bootstrap/driver의3그룹이므로 등급 보조 규칙상 **L**이며 아래 S2/S2/S4로 분할한다. 전체를 단일 M 작업이라고 축소 계수하지 않는다.

| 소유자 | 파일 | 역할 |
|---|---|---|
| worker A, S2/25분 | `src/simulation/single_host_controller_110/winjob.py`, `test_winjob.py` | 생성 순간 Job 배속·실제 handle 종료·raw 파일 |
| worker B, S2/25분 | 같은 폴더 `bootstrap.py`, `test_bootstrap.py` | 새 권한·폐쇄 패키지·첫 요청부터 예산·전송/회수 |
| root, S4/25분 | 같은 폴더 `driver.py`, `config.json`, `test_driver.py`; `outputs/single-host-controller-110/execute.py` | 실제 same-host transport·admission 배선·통합 진입점 |

각 구현 단위25분, 분할 후 통합 점검 검수급45분을 구별한다. 단위 A/B/C 각각 L2 최대2/L4 최대2이고 통합도 최대2다. 검수자가 한 발사에서 여러 단위를 보더라도 단위별 verdict/미해결/union을 명시하고 각각1회를 소비한다. L2는 모든 단위 및 연결 계약을 읽는 주렌즈와 WinJob/권한·예산 보조렌즈로 병렬 수행한다. L4도 실제 각 단위와 연결부 판정이 있어야 한다. 각 union과 충분 임계는 첫 발사 전에 보존한다. 1차 BLOCK이면 해당 작성자가 수리하고 남은1회에서 해당 단위와 영향 연결부를 전건 재검토한다. 닫힌 단위를 이름만 바꿔 다시 열지 않는다. 예산 끝에서 미완료면 BLOCK/UNKNOWN과 내용 자산을 남기고 추가 R3는 없다. 기존 승인된 동일계열 비작성자 폴백과 공통편향을 명시한다. 외부 bridge의 과거 lint 차단을 이번 작업의 실행 실패로 다시 계수하거나 도구를 고치지 않는다.

로컬 조사·구현·HOST·코드 검토는 원격 native45를 시작하지 않는다. 원격 실행은 모든 코드 검수 PASS와 별도의 typed 실행 권한을 갖춘 뒤만 가능하다. 기존 조건부 새45분 진행 지시와 이번 해결 지시를 권한 출처로 기록하되, 검수의 scope 판단 없이 자동 실행 승격하지 않는다. 2700초는 첫 원격 요청 직전 client monotonic부터 업로드·활성화·SDK·회수까지이며 재시작하지 않는다.

## 실제 dependency와 namespace

원108 source18/harness13, 모델16, 최상위 refs11의 경로/바이트/해시는 `outputs/single-host-controller-110/dependency-census.json`에 있다. 원 source18 중 driver/config를 새110 bytes로 대체하고 `winjob.py`를 더한 **실제 runtime source19**를 만든다. 나머지16개는 원 bytes 그대로다. 기존 test_host/test_scene/README/launch는 역사 입력이며 새 진입점에서 실행하지 않는다. 새 HOST를 별도 실행하고 `public('test')`는 허용하지 않는다. 새 actual source19/job/ZIP/freeze는 이 조합을 명시한다.

모델16과 refs11을 실제 소비 경로에 맞게 패키징한다. 참조7953 전체·옛 실행 폴더·옛 approval/budget/인증서는 복사하지 않는다. 원 SDK 설치와 고정 prefix는 재설치하지 않는다. 원격 actual SDK 파일·version·physics origin/pins는 기존 native 검증이 다시 확인한다. 불일치는 실패로 남긴다.

원108의 `source-freeze-r2.json`, `usd-check-r1-stdout.txt`, `activate-budget.py`의 고정 bytes는 검증 내용 자산으로 추가 승계한다. bootstrap context는 마지막 파일의 **순수 verify_usd만** 호출해 evidence SHA·scene/root_binding 동일성·typed8negative를 실제 검사한다. 원 context/activate/native_approval는 호출하지 않는다. 새 runtime19의 scene/root_binding도 그 원 SHA와 일치해야 한다. 이 gate는 새 로컬·원격 activation 및 offline 회수 검증에서 소유하며 옛 승인 재사용으로 오해해 제거하지 않는다.

원격 경계는 `C:/isaacsim_remote/robot-arm-lab/110/` 안이다. controller repository capsule은 `controller/<nonce>/`, SDK run은 `worker/runs/<uuid>/`에 둔다. 원108·109/과거 ledger/모델링/펌웨어를 쓰지 않는다. 원110 claim은 base의 `attempt.json`을 배타 생성하며 단일 실행 실패도 소비한다. 링크·junction·기존 목적지·경로 이탈·중복 ZIP 이름·예상 밖 파일은 거절한다. 파일 bytes를 한번 읽어 SHA 검증한 동일 bytes로 추출/실행한다.

## WinJob API 계약

`winjob.run(argv, out, timeout_s, *, cleanup_s=2, admit=None, stdin_path=None, input_sender=None)`은 stdout.txt/stderr.txt를 배타 생성한다. stdin_path(읽기 전용 파일)와 input_sender(callback)는 상호 배타다. sender가 있으면 비상속 parent write end와 allowlist된 child read end의 pipe를 쓰며 sender(stream, stdout_path, work_deadline)를 실제 resume 후 main thread에서 호출한다. callback도 같은 hard fence 안이고 blocking write/partial READY를 무제한 기다리지 않는다. 기본 stdin은 NUL이다. job handle/parent pipe end는 상속하지 않는다.

반환 record에는 `child_pid`, `actual_child_exit_code`, `policy_exit_code`, `policy_basis`, `timed_out`, `child_state`, `terminal`, `job_active_after`, `raw_complete`, `errors`가 있다. 원본 파일은 변경하지 않는다. work deadline은 시작+timeout_s, 전체 끝은 시작+timeout_s+cleanup_s다. caller의 global 남은 시간보다 작게 전달한다. 반환한 exit code는 실제 고정 handle의 값이다.

Job은 이름/상속/breakaway가 없고 KILL_ON_JOB_CLOSE다. STARTUPINFOEX의 JOB_LIST와 stdout/stderr/stdin만의 HANDLE_LIST를 사용한다. Job handle은 자식에게 상속하지 않는다. CREATE_SUSPENDED|CREATE_NO_WINDOW로 만들고 실제 IsProcessInJob·GetProcessTimes를 확인한 뒤 resume한다. PID 문자열을 대상으로 taskkill하지 않는다.

독립 hard fence는 `Fence(deadline_monotonic)` context와 close()로도 제공한다. 실제 watcher 본문이 armed event를 게시했음을 확인한 뒤만 admit/managed I/O/child 생성으로 간다. Thread.start 반환 자체를 armed/terminal로 취급하지 않는다. 시작/armed 확인 실패는 자식을 만들지 않으며 미종결 watcher를 낙관적으로 버리지 않는다. run의 admit는 fence armed 후·stdout/stderr/child 생성 전에 호출할 수 있어, bootstrap의 LIVE 검증 뒤에만 out 폴더를 만들 수 있다. out은 admit 완료 뒤 기존 안전 디렉터리인지 확인한다.

run의 정상 반환에서 fence를 해제하려면 생성 호출 반환·고정 child handle signal·Job accounting active0이 모두 필요하다. cleanup/query/wait/diagnostic 오류는 terminal 성공으로 바꾸지 않는다. deadline 때 file/stderr/Job close의 성공과 무관하게 자신의 process handle에 TerminateProcess, finally os._exit로 끝내는 IO 독립 경로를 쓴다. pending 생성 중 상위 사망은 JOB_LIST·last-handle-close의 실제 대조로 확인한다. 일반 소프트웨어가 OS 스케줄 정지 중 즉시 실행된다는 실시간 보장은 주장하지 않는다. 늦게 resume된 SDK entry도 원 deadline을 먼저 검사한다.

SDK native `run_child`와 local PowerShell/OS clock 자식 모두 이 helper를 실제 사용한다. 새 helper는 source19/닫힌 snapshot에 포함해 하위 supervise에서도 같은 bytes를 읽는다. stdio capture에는 reader thread와 query 후 reader-start 초기화가 없다. terminal/EOF 불명은 UNKNOWN이며 raw_complete=true로 덮지 않는다. 원 class의 과거 소진은 유지한다.

## Bootstrap 계약과 예산

`bootstrap.context(root, round, require_native=False)`는 exact unit110·plan/L2/source-freeze/L4 round와 모든8파일/의존 해시·typed bool/int·물리 기본false를 확인한다. PASS는 모든 AC가 MET이고 미해결0일 때만이다. native 권한은 별도 `native-approval.json`의 user quote/plan/freeze/final review/2700초/목적별1회/clock_mutation=false/hardware=false와 결속한다. 기본 execute는 status only, 명시 run과 유효 권한이 필요하다. `--controller`도 standalone 우회 권한이 아니다.

첫 SSH 직전 local `remote-attempt.json`을 배타 소비하며 시작 wall/monotonic·nonce를 저장한다. 모든 SSH는 local WinJob 자식이다. 첫 원격 명령은 기존 Isaac Python -I -S -B에서 **reviewed winjob.py의 압축 bytes와 SHA를 확인해 로드**하고, 원격 main process의 Fence20을 실제 armed시킨다. 그 전에 허용되는 것은 고정된 작은 코드의 decode/import뿐이다. managed 파일 읽기/쓰기·child 생성·archive extraction/SDK는 fence 전에 없다. stdout 오류를 포함한 원격 응답 I/O도 fence 안이다. 원격 SSH 서버 daemon/default-shell 자체를 우리 Job으로 소유했다고 주장하지 않으며, 그 transport의 종료는 SSH 원문/실제 return code로 별도 관측하고 불명은 UNKNOWN이다.

첫 remote main은 managed 파일 없이 순수 OS wall/monotonic/uptime·nonce·site_loaded=false의 READY를 stdout으로 보낸다. client input_sender는 **자신의18초 communication 기한 안에 실제 READY를 받은 뒤에만** LIVE 응답을 보낸다. 미리 쓴 nonce 파일을 LIVE로 대신하지 않는다. remote는 Fence20 안에서 LIVE를 읽고 기한/nonce/plan/freeze/권한을 재확인한 다음에만 base110 claim·out 폴더를 배타 생성한다. READY가 client 종료 뒤 늦게 발생한 경우 LIVE가 없으므로 claim/native 권한을 만들지 않는다. Kit/SimulationApp은 시작하지 않는다.

첫 교환은 측정 경과 E뿐 아니라 **고정20초 전부를 보수 차감**한다. remote started_unix=READY.wall−20, started_monotonic=READY.mono−20, deadline=started+2700이다. client가 READY를 받은 시각이 첫 요청 t0+20 이전임을 실제 기록하므로, 같은 elapsed 단위에서 READY의 실제 시각 R≤t0+20이고 끝 R+2680≤t0+2700이다. offset이 다른 두 PC wall을 비교하는 식이 아니다. 전체 SSH/고정 handle 종결/원문 수신 E도20초 안인지 확인하고, 초과/불명은 소비된 실패이며 upload/SDK로 가지 않는다. 첫 요청 후2700을 새로 주거나 실제20초보다 적게 차감하지 않는다. LIVE가 remote 자체20초 안에 오지 않으면 그 process가 IO 독립 self-fence로 종료한다. 원격 활성화는 같은 claim SHA/nonce/budget를 재검증하고 이미 지난 upload/entry 시간을 되돌리지 않는다.

이후 각 remote 명령은 먼저 동일 reviewed winjob bytes를 확인하고 **초기 Fence20을 armed한 뒤** claim 읽기를 한다. typed 원격 wall/mono와 고정 claim SHA를 확인하고 grant의 절대 remote deadline에 묶인 full Fence를 실제 armed한 뒤에만 초기 Fence를 close/join한다. watcher가 없는 틈이나 새2700초가 없다. full Fence 안에서 모든 managed read/write, stdout 대량 전송, extraction, controller/SDK child 생성·종결을 수행한다. shared budget·client 단절·child creator pending·I/O 실패에서 client Job의 terminal을 remote actor의 terminal로 대신 쓰지 않는다. remote main의 자기 종료/직접 자식 Job은 원격 소유자이며, actual/UNKNOWN과 SSH 결과를 구별한다.

새 코드/metadata/모델/ref의 폐쇄 ZIP은 로컬에서 준비한다. **SCP/SFTP는 사용하지 않는다.** local WinJob의 stdin_path로 ZIP 파일을 SSH에 보내고, 원격 fenced main이 고정 바이트 수·EOF·SHA를 확인하며 배타 partial 파일에 저장한 뒤 새 목적지로만 완료한다. download도 원격 full Fence 안에서 길이/SHA header·닫힌 ZIP bytes를 stdout으로 전송하며 local WinJob의 원본 stdout에 보존한다. 양쪽 실제 종료·정확 바이트 수·SHA·안전 ZIP·원 manifest를 검증해야 회수 성공이다. managed stdout relay도 fence 밖으로 빼지 않는다.

SSH 명령에는 압축 helper+해시와 그 operation의 작은 relay만 싣는다. actual Windows command line을 생성해8000자 미만을 HOST로 확인하며, 초과 시 전송 전에 거절한다. 무한 stdin decoder나 guard 없는 별도 remote loader를 새로 두지 않는다. relay 전 범위는 bootstrap.py의 검토된 bytes에서 만들며 remote command SHA/길이를 원문 metadata에 기록한다. 원격 claim 뒤 upload·SHA/안전 extraction·새 activation·Job controller·최종 회수는 모두 같은 local/remote 끝을 소비한다. old claim/변경 package/불명은 실패며 재시도하지 않는다.

runtime config는 inactive 원본에서 **deadline_unix만** 변경한 사본이다. review freeze는 inactive bytes, execution freeze는 그 사본과 원본 차이를 결속한다. unit110/plan/dependency/source8/원 invariants/원격 grant·budget은 매 경계 재확인한다. controller가 실행되기 전 runtime-budget/activation/execution-freeze를 배타 저장한다. 원108의 권한 파일은 소비하지 않는다.

## 같은 호스트 driver와 불변 기준

새 driver는 전송 경로와 identity만 명시적으로 바꾼다. `clock_argv/clock_exchange`는 **같은 PC의 독립 순수 OS 자식**을 WinJob으로 실행해 직접 파일 stdout/stderr를 보존한다. startup 포함 실제 send/receive bracket과 wall/mono를 인증서에 사용하고, 느린 시작을 숨기지 않는다. site_loaded=false·nonce·Kit0·actual exit·두 프로토콜 행을 확인한다. 원 ±1초/.25초/age120초 수치를 유지한다. 인위적 0 offset/가짜 certificate를 만들지 않는다.

`remote()`는 같은 PC의 실제 PowerShell 자식을 뜻하는 명시 local-process backend다. 두 SCP 경로는 안전한 별도 목적지의 실제 복사로 바꾸며 ZIP/receipt SHA·inventory·no-overwrite를 지킨다. 실제 child return code와 `transport_kind=LOCAL_PROCESS`를 저장·소비한다. SDK 자식은 같은 source19 snapshot·실제 admission·부모 PID/ledger/lock을 확인한다. helper timeout과 global remaining·cleanup reserve가 원 phase 한도 안에 있어야 한다.

2700초, import/정지600초, motion900초, headroom1380/1680초, export300/회수600초, 목적별1회와 기존 stop→42초 선행 조건을 유지한다. 원 shadow/background retry를 추가하지 않는다. 게인64/16/cap·097후보·물성가정·링 보류·원 모든 물리 gate·과거 실패/정착15/velocity-only 소진·PD/포화 UNKNOWN은 유지한다. 정지 검증 실패면42초 실행은 없다.

## AC와 검수 입력

| AC | MET 조건 |
|---|---|
| AC1 | 109 두 원 지적·원소진·종결 회차 보존. 새 no-clock-mutation/no-privileged-thread가 제품 의무에 답하는지 독립 판정. 전체 도메인 소진/원109 소급 성공 없음 |
| AC2 | source7/harness1 정확 census·immutable deps/model/ref 실제 해시·새 identity와 source19 배선·기본 deny/typed 새 승인·review/plan/freeze 결속 |
| AC3 | actual generated literal→entry에 동일 admission 전달. export None; 원 누락 음성 대조/변조 거절. root와 하위 supervise가 같은 actual helper/driver bytes 사용 |
| AC4 | 실제 생성 순간 JOB_LIST·suspended·비상속 last-handle-close·고정 handle wait/accounting. pending/return/IO/진단/생성·resume·query·cleanup 실패 모두 actual caller 대조. 거짓 terminal 금지 |
| AC5 | 첫 원격 요청 이전 단일 소비부터 upload/activation/SDK/recovery까지 같은2700초. 늦은 entry·client 단절·wall jump·기한 부족·이미 소비·불명은 실패, deadline reset/retry 없음 |
| AC6 | 실제 same-host OS child의 nonce/sitefalse/Kit0/raw/exit/time bracket, 원±1/.25/120 수치. LOCAL_PROCESS/실제 copy/ZIP/closed recovery·실제 return code, fake transport 성공 없음 |
| AC7 | 기존 모델/097program/게인/cap/물리 및 phase 시간 기준 그대로. import→정지 전건수용→42초 순서; SDK/실물 승인 구분·설치/CAN/flash/급전 없음 |
| AC8 | 의미 있는 HOST·compile·normal-user own child kernel probe, 독립 다른 기전 반례와 양성대조·원자료/실패/재현 경로 보존. 동일계열 잔여편향·class union·충분 임계와 착지·잔존/신규를 명시 |

L2는 이 계약의 논리 모순/누락만 판정한다. L4는 frozen8+composed runtime19+관련 consumers를 읽고 실제 무해 caller/kernel 대조를 수행한다. author 전체 시험 반복을 독립 관측으로 세지 않는다. Major1개라도 BLOCK, 전 AC MET/미해결0이어야 PASS다. 새 pending lifecycle 인스턴스가 있으면 원 union3 소진을 초기화하지 않고 착지/수리→생성 대응을 독립 판정한다. 원 FINITE_STAGE_BUDGET_ACCOUNTING2→다음3, heartbeat관측2→다음3, review unit1closed 등의 정확 class 계보도 그대로 제출한다.

이번 계획의 외부 실행은 PASS 후 기존 시뮬레이션 범위 안에서만 가능하다. 어떠한 경우에도 실물 CAN·급전·모터·flash·물리보정·설치·네트워크/시간 설정 변경은 하지 않는다.
