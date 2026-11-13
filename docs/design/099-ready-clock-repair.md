> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 099 — 준비 완료 후 단일 연결 시각 인증 수리

2026-11-01. 사용자 지시: `좋아 다음 해결해`. 098의 시계 인증 실패를 수리·HOST 검증·비작성자 검토하는 범위다. 098의 소스·2700초 예약·최초 실패·검토 종결은 그대로 보존한다. 이번 새 원격/SDK/SimulationApp/물리/CAN 실행은 없다. 새 원격45분은 아직 승인·활성화하지 않는다. 수리와 검토가 끝난 실제 실행 후보를 먼저 제시한다.

## 원인과 범위

[관측] 098 SSH OS query는 종료0/유효JSON/당시Kit0이나 단일 span9.344초였다. offset 가능 구간[-.380145,+8.966639]초가±1초를 넘었다. `clock_probe`는 SSH/PowerShell/isolated Python 시작 전을 send로 잡아 시작 비용까지 구간에 넣는다. 실제 시계 offset이나 지연 성분별 원인은 UNKNOWN이며 실제9초 시계 오차로 해석하지 않는다. 098은 prepare/native 전 중단했다.

수리 대상은 프로세스 준비와 표본 왕복의 경계다. ±1초 clock_bounds, local wall/mono .25초, remote age120초/.25초, +2초 입장 상한, 1380/1680초 headroom, watchdog600/900·회수300/600·전역2700초를 바꾸지 않는다. 게인64/16·cap·물리 기준·모델·42초 후보·34초 실패 보존·과거 소진은 불변이다. 새 source namespace `src/simulation/clock_ready_run/`, evidence `outputs/isaac-clock-ready-099/`, experiment `clock_ready_099`, remote root `C:/isaacsim_remote/robot-arm-lab/099/runs`를 사용한다. 새 config deadline은 int0이다.

전체 production은 mutable18파일인 L 범위이므로 아래 A/B/C의 닫힌 순차 단위로 분할한다. 불변source13은 hash-only이며 mutable에서 제외한다. 통합 검토 자체는 read-heavy M/호출별45분이다. **099 전체 L2 최대2·L4 최대2**이며 단위별로 초기화하거나 추가 검토 라운드를 만들지 않는다. 작성자는 root, 비작성자는 기존 승인된 동일 계열 fallback reviewer다. 로스터/bridge 수리나 새 설치는 하지 않고 공통 편향을 기록한다. 검토자는 patch하지 않는다.

| 단위 | 닫힌 mutable 목록 | 등급·그룹 | 순차 gate |
|---|---|---|---|
| A 시각 채널 | source의 driver.py, outputs의 host_clock.py·host_timing.py·host_entry.py·host_repairs.py (5) | M, 시각 채널/그 호출 HOST의2그룹 | L2 통과 후 새 clock 실제 caller/로컬 child HOST 및 compile. legacy adapter는 B의 정적 scaffold를 사용하고 통합 회귀에서 다시 실행. 이 시점 host_clock.py는 clock HOST만 소유. gate의 driver/HOST hash를 기록하며 activation/transport는0 |
| B 실행기 결속 | source의 config.json·README.md·test_host.py·test_scene.py, outputs의 activate-budget.py·host_activation.py·prepare-review.py·execute.py·execute.ps1 (9) | M, source metadata/권한·실행 결속의2그룹 | A clock HOST 통과 후 실제prepare45/bundle46·기존 회귀·새 승인false/모든 actor입장차단·source/hash gate. config는 계속int0. B 통과 전 C 및 L4 후보동결 없음 |
| C 사후 데이터 도구·분석 HOST | outputs의 audit-native.py·analyze-hold.py·root-com-witness.py·encode-native-video.py 및 공유 host_clock.py (5, host_clock.py는 A와 중복) | M, 사후 원봉인 데이터/분석 HOST의2그룹 | B 통과 후 네 도구 namespace-only AST 비교·컴파일. host_clock.py에 아래 원10개 분석 HOST 경로를 추가하고, 그 변경 뒤 A clock HOST와 모든 B 회귀도 다시 검증해 최종 freeze. 새 native 자료가 없어 actual native 감사/새영상은NOT_RUN. A/B/C 통합증거를 묶어 L4에 제출 |

source 경로는 src/simulation/clock_ready_run, outputs 경로는 outputs/isaac-clock-ready-099다. A5/B9/C5는 공유파일1개를 포함하므로 **고유 mutable18개**다. C가 추가로 쓰는 공유 파일은host_clock.py 하나뿐이며 C는 driver/channel API를 변경하지 않는다. Agate 뒤 HOST 파일이 변경됐음을 hash로 기록하고 C/final gate에서 A clock HOST+B 전회귀를 다시 실행한다. B의prepare-review.py는 B gate에서는 C분석을 호출하지 않고 최종C gate에서만 분석10개와 전체source/harness freeze를 수행한다.

기존098 host_analysis.py의10개검사는 **새 host_clock.py --analysis** 안에서 신규analyze-hold.py의 실제summarize를 검사하도록 이식한다. 원10개사례/이름/조건을보존하고 namespace/OUT/source 결속만099로 바꾼다. 원098script를 실행해 원analysis-host.json을 덮지 않는다. 원스크립트의검증된바이트를098보호핀으로확인하고 소유 caller 안에서 경로를명시재결속해재생할수있으나 그변환/실제출력경로와10개명칭을감사한다. 별도 host_analysis.py와rebind.py는099제품/하네스로복사하지 않는다. 최종harness는outputs의고유13개(py12+execute.ps1)이며 source18과구분한다.

docs 계획/결과와shared handoff는 이 단위의 제품 코드를 추가하는 통로가 아니라 검토·인계 데이터다. 먼저 source 불변13 및 B의 비활성 정적 metadata scaffold만 복사해 A HOST 입력을 제공할 수 있으나, B의 활성화/실행 로직은 A gate 이후 구현·검증한다. 새 mutable 제품/하네스를 추가해야 하면 L2 남은 예산 안에서 census와 경계를 먼저 수정해 재확인하며, 상한 뒤 숨은추가파일/4번째단위/R3는 없다. L2는 이 분할·단계계약을 함께 판정하고 L4는 단위별 gate 증거와 실제 통합 caller/권한/보존을 함께 판정한다.

## 단일 연결 프로토콜

1. 기존 SSH→PowerShell→기존 isolated Python(-I -S -B)을 **1회** 연다. lifecycle 시작의 단조표본을 m0라 할 때, 전역 절대단조종료 G는 결속된 runtime-budget의 started_monotonic+2700이며 **D=min(m0+20,G)** 로 한 번 고정한다. 통신종료 C=D-2로2초를자기local SSH kill/reap 및 두reader join의 **공유 합계** 정리에 예약한다. m0<C가 아니면Popen0이다. 사전예약I/O·Popen·READY·challenge·표본·정상exit/양EOF는 C까지며, 실패 정리는 D까지다. 어떤 대기도 새상대20/새2초를 받지 않는다. 새 연결/재표본/실패 retry는0이다. 시작 비용도 전체2700초에서 소비한다.
2. remote는 stdlib만 import하고 Win32 GetTickCount64 getter를 준비한 뒤 nonce 결속 READY 한 줄을 flush한다. Kit OS probe는 같은 연결의 Python 시작 전이며 SDK/SimulationApp을 import하지 않는다. local은 READY protocol/nonce/site-disabled를 확인한 뒤에만 challenge를 보낸다. 098 실제 query9.344초 지연 및 느린 cold start를 모형과 실제 로컬 child 양쪽에서 재현한다.
3. local은 challenge write/flush **직전** UTC/mono를 기록한다. remote는 정확한 nonce 한 줄을 읽은 직후 UTC/uptime을 표본화해 nonce 결속 SAMPLE 한 줄을 flush한다. local stdout reader는 SAMPLE 줄 완성을 관측한 즉시 UTC/mono를 기록한다. process exit를 기다린 후의 시각으로 sample receive를 덮지 않는다.
4. offset은 원식 `[remoteUTC-localReceive-.002, remoteUTC-localSend+.002]`와 원±1초를 그대로 적용한다. local wall/mono 경과 일치도 원.25초다. SDK 입장에 쓰는 certificate의 닫힌8필드와 remote run/job/deadline·uptime 검증은 불변이다. nonce/READY/전체 과정 timing은 별도 raw query evidence에 남긴다.
5. remote 입력 대기는 고정20초 단조 timeout, EOF/잘못된/과장된 challenge를 거절한다. local도 단일 고정 기한이며 READY/SAMPLE 누락, malformed/중복/추가 stdout, nonce 불일치, Kit>0, nonzero exit, 시계 점프, 실제 느린 표본 왕복은 실패한다. 시작 비용을 제외한 표본 구간이 여전히 넓으면 발사0이다. midpoint/최소RTT 선택/offset 추정으로 보증을 완화하지 않는다.
6. Windows pipe는 stdout/stderr를 동시에 읽고 bounded byte/line buffer로 제한한다. 전체 stdout16KiB·stderr256KiB, line4KiB를 넘으면 overflow로 실패하고 한도까지의 원바이트와 truncated 표시를 남긴다. thread/event/queue는 고정 개수·한도다. 닫힌 두 stdout 줄만 성공이며 성공 전 child exit0와 양 pipe EOF를 확인한다. write 길이/flush 실패도 실패다.
7. 모든 실패에서 자기 local SSH process만 kill/reap하고 reader를 bounded join한다. 통신의 모든 대기 timeout은 C-currentMono, 정리의 wait/join은 호출마다 **같은 D-currentMono**의 min이며 serial wait/join에각2초를부여하지 않는다. C 이후 challenge/새통신0, D 이후 새 wait/join0이다. kill 및 OS pipe/process 생성 자체의 스케줄 지연을 hard realtime으로 보장했다고 주장하지 않는다. OS 호출이 늦게 반환하면 즉시 절대기한을 다시 검사해 FAILED_OVERRUN/cleanup UNKNOWN으로 남기고 한도내 성공으로 수용하지 않는다. 이미 소유한 자식에대한 best-effort local kill은 허용하되 새 SSH/native가 아니다. 다른 Kit/process 종료·서비스 변경·PC 시각 동기화는 하지 않는다. 원격 child는 stdin EOF/자체단조20초 timeout으로 종료한다. cleanup 상태 불명은 UNKNOWN/실패로 남기고 새 원격/native를 보내지 않는다. raw publication은 종료후 로컬데이터작업으로 분리하며 새 channel wait/기한을 만들지 않는다.
8. query 시작 전 raw4경로 및 **clock-query-attempt.json** 존재를 검사한다. 예약 marker를 **Popen 전에 xb 생성·flush·fsync**해확정하고, 예약을확정할수없으면 transport0이다. 부분예약/빈파일도 소비로 보수 판정한다. 어떤 raw/attempt 하나라도 존재하면 같은context의두번째호출은0이다. 이후 raw publication이 전부 실패해도 marker를 지우지 않으며 파일 삭제/새UUID로 query를 재시도하지 않는다. 성공/거절/timeout/pipe 실패 모두 한도내 raw stdout/stderr, 최초 시각/고정D·C/READY/challenge/sample/returncode/cleanup 관측을 보존한다. 기록 부차 실패는 원 오류를 덮지 않는다.

## 099 결속과 비활성 기본값

098 source18을 새 디렉터리로 복사한다. driver 외 config/README/test_host/test_scene의 namespace, experiment, plan hash와 inactive deadline만 새099에 결속한다. sdk/scene/capture/launch/workspace/init_boundary/torque/reference/balance/root_binding/recovery/validate/program은098과 바이트 동일이다. driver에서는 clock channel 및 고유 결속 외 나머지 AST 동일을 검사한다. 후보는097 바이트와도 같다. 098 harness는 새 namespace/review pins에만 결속하며 clock wire 계약을 가정한 HOST 부분은 새 실제 호출 경계에 맞춰 수정·명시한다. 원 테스트 삭제로 통과시키지 않고 각 대체 경계의 원본과 새 의미를 표로 남긴다. 원 276 HOST 중 비시각 의미는 유지하고 시각 의미는 새 채널로 재현한다. 추가 HOST 수량은 구현 전 임의 고정하지 않고 실제 테스트 이름/개수로 보고한다.

이전5808 baseline과098 커밋의 공유HANDOFF/SESSION 외187파일을 보호 목록에 합친다. 098 파생 HOST/ZIP은 기존 hash receipt를 보존한다. shared 문서는 이번 시작 raw snapshot을 남기고 최종 prepend/append 시 기존 바이트를 보존한다. 동시 변경은 발견 즉시 별도 base로 채택하고 되돌리지 않는다.

실행기는 검토 전 activation 금지와 explicit approval gate를 유지한다. 099 approval.json은 LOCAL_CLOCK_REPAIR_AND_REVIEW_ONLY/nativefalse로 동결하고그SHA도freeze에묶는다. 검토/소스가 완성돼도 이번에 새45분/SSH를 시작하지 않는다. 추후 사용자의 새45분 승인만 별도 native-approval.json에 기록할 수 있다. 이 영수증은 닫힌필드로명시승인booltrue·scope099_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S·정수2700·typed목적각1·검토후시작true·hardwarefalse·실제user_quote·실측source-freeze SHA·실측PASS review SHA를 요구한다. 098승인/다른round/변조/필드누락/승인false면 budget/네트워크 전 거절한다. 원 repair approval.json은 사후편집하지 않는다. activator가 native-approval SHA를runtime-budget에핀하고verify_execution도재검사한다. 이 데이터영수증과 deadline 한토큰외 제품/후보/기준변경은허용하지않는다. 부분 활성화/실패도 소비·재개 금지, 목적 각1·정지 수용 후42초만 허용하는 흐름은 유지한다.

## 검증과 통과 조건

| ID | 필수 MET 증거 |
|---|---|
| AC1 | 사용자 수리 범위·새 원격 승인false·deadline int0·실물CAN/SDK/native0·098예약/실패 보존 |
| AC2 | 098원자료187+기존5808 hash, 불변 source13와 driver 비시각 AST, 후보/모델/물리 기준 무변경 |
| AC3 | 실제 로컬 Windows PowerShell→isolated Python stdin/READY/challenge/SAMPLE/EOF 양성. SDK/SSH stub임을 명시 |
| AC4 | 실제 시각 caller에서 cold startup9.344초를 제외하되 총예산에는 포함; 준비 후 느린 표본/offset/jump/stale/reboot는 원기준 거절 |
| AC5 | 실제 Popen/pipe/timeout 경계에서 malformed/duplicate/nonce/Kit/nonzero/EOF/flood/flush/partial write/cleanup 실패·무재시도/raw 보존 재현 |
| AC6 | 전체 query 단일20/global deadline·challenge 직전 send/reader 즉시 receive·exit 대기로 receive 연장 없음·고정 byte/queue 한도 |
| AC7 | 기존 launch/Popen 최종입장·고정2700/1380/1680·monotonic 회수600·closed exporter·actualprepare45/bundle46의 비시각 회귀 유지 |
| AC8 | L2/L4 각최대2, 지적 union/class/착지/반복·재귀·소진 판정 포함. 과거 정착15/velocity-onlyEXHAUSTED·098L4 union4·새clock failure를 지우지 않음 |
| AC9 | 최종source/harness/HOST/hash/review 동결, 승인false로 activator와coordinator가 네트워크 전 거절하는 실제 경로, 결과/인계/스코프 로컬commit/no push |

검토 실패는 작성자 수리 후 남은 round에서 재검토하며 상한 뒤 추가 R3/우회 발사0이다. 비작성자는 5위험 범주(API/SSOT/ERROR/ORDER/AUTHORITY_SCOPE)별 리스크+근거,9 MET/UNMET, 지적 합집합·class별 다음 재발 임계를 판정한다. 작성자는 완화 효과의 소진 부정을 선언하지 않는다. 마지막 통과는 HOST/코드 계약 수용이며 실제 원격 성능이나 정지/42초 물리 수용이 아니다.

## L2 R1 수용과 R2 검토 대상

R1 BLOCK6/3의 F1 FINITE_STAGE_BUDGET_ACCOUNTING, F2 QUERY_ATTEMPT_NOT_RESERVED_BEFORE_TRANSPORT, F3 WORK_UNIT_GRADE_WITHOUT_MUTABLE_CENSUS를전부수용했다. 원계획SHA332822f5e16ca20839a61e9c0cdf42fe3b18f642d2685051245812a945a131d6와원판정/반례는review/r1-preserved및independent-r1에보존한다. 수정은D/C의단일산술, Popen전durable소비, 고유18파일의닫힌단위와gate다. R2에서계획논리폐쇄를받고실구현폐쇄는L4에서다룬다.

진행중R2 대상SHA2edf581fbe13f4dc8f9472db78ec16c9cf97429dcb6b23c54e831c4bb808cbad에서 비작성자가원analysis HOST10개누락을발견했다. F3미폐쇄분으로수용하고원중간계획/반례를r1-preserved/r2-in-progress-plan.md·r2-target-update.json에보존했다. 최종verdict전비작성자절차판정으로작성자1회 semantic대상갱신을허용받아 C5공유HOST소유와Agate후재검증을명시했다. metadata-only갱신이아니며 새round/기한reset없이같은R2의고정45분안에서전체논리를재핀한다.

F1은097L2R1F2와같은계보의합집합2번째다. 비작성자가R1에사전박제한 다음별개같은class누락(합집합3번째)=해당시간계산/검증접근법소진충분조건을유지한다. 미폐쇄상태새표면/수리→동종생성의더이른소진판정권도유지한다. 이 임계는제어게인/로봇/시뮬전체도메인소진으로확대하지않는다. F2/F3는각1이며원098L4union4/종결및모든기존임계는보존한다.

이번 로컬 완료 후 다음 원격 실행 조건은 새099에 대한 사용자 명시45분 승인, L4 PASS, 바이트 동결/승인 데이터 검증, 그리고 첫 원격 명령 직전 단일 시계 예약이다. 정지 검증 미통과 또는 시계 인증 실패면42초 진단은 NOT_RUN이다.
