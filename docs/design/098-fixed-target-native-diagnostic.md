> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 098 — 실행기 통합과 42초 고정 목표 진단

2026-11-01 KST. 사용자가 098 실행기 통합·검토 후 첫 원격 실행부터 새45분을 승인했다. fresh import → 2초 정지 검증 → 42초 진단을 각1회 수행한다. 정지가 수용되지 않으면 motion을 발사하지 않는다. 게인64/16·cap·모델/물성·원 판정 기준은 유지하고 실물 CAN/serial/급전/모터/flash/보정/설치/재부팅/전원정책 변경/학습/구매/외부 업로드는 제외한다. hardware_approved=false다. 이전095~097의 예산·소진·실패를 초기화하지 않는다.

## 소유와 검토

새 src/simulation/hold_diagnostic_run/는 096 source18의 별도 사본이다. driver.py/config.json/test_host.py/README.md를 통합하고 program.json은 097 검토 후보의 정확한 바이트를 쓴다. sdk/validate/scene/capture/launch/workspace/init_boundary/torque/reference/balance/root_binding의11파일과 recovery.py는096과 바이트 동일하게 보존한다. test_scene.py의 기존52초 기대수량521/6240을 새후보의 정확421/5040으로 바꾸고 결과쓰기 경로도096에서098 소유namespace로 바꾼다. 나머지29개 검사의 로직/양음성은 유지한다. test_host 및 새 하네스의 모든 결과/임시쓰기 역시098 소유namespace에 한정한다. source18의 정확 목록을 유지한다. 원095/096/097·모든 기존 source·CAD/URDF/BOM/펌웨어는 수정하지 않는다.

소유 증거/하네스는 outputs/isaac-hold-diagnostic-098/, 문서는 본 계획과098-results.md, 공유 문서는 HANDOFF prepend/SESSION_HANDOFF append만이다. 097 보호5773에 현재097 소스/증거/검토/계획·결과를 더한 전후 SHA 목록을 만들고 기존 인계 원문도 보존한다. SSH는 기존 isaacpc와 기존 설치만 사용한다. 다른 프로세스·서비스·보안 설정은 바꾸지 않는다.

L2최대2/L4최대2, 매 투입 검수급45분 상한. 기존 사용자 승인에 따라 같은계열 비작성자 폴백을 재사용하며 표준 bridge 수리/재시도/설치는 없다. 공통편향을 기록하고 외부계열 가용 시 전제 재검증을 우선한다. 지적 합집합/class/착지/폐쇄/소진·다음 임계와 과거 실패를 매 라운드 요구한다. L4 R1이 통과하면 새 원격을 실행하고 남은R2를 결과의 독립 감사에 사용할 수 있다. R1 결함 수리로 R2를 먼저 소비하면 사후 감사는 작성자 범위임을 명시한다. 총2회 뒤 자동R3/수리/새예산은 없다. runtime에서 새 결함이 나면 실패 원본을 보존하고 추가 native 없이 재상정 입력으로 남긴다.

## 불변 프로그램과 판정

097 후보42초/5040step/5041관측/421capture를 그대로 결속한다. 첫9segment/0~34초4081명령은 원095와 같다. 33~42초1081명령의 전체9자유도 목표가 일정하고 속도 명령0이다. 34초 checkpoint는 유지하며42초 checkpoint만 더한다. 52초 전체 경로 재시험이 아니다.

기존 pure consumer와 native scene/물리/수용 코드는 수정하지 않는다. 위치0.5°/속도1°/s와 다른9DOF·COM/fixed9·한계·바닥·렌더 기준도 그대로다. 34초 실패 후42초 통과라도 전체 consumer의 실패는 보존하며, 별도 관측에서만 연장 hold의 진입/이탈을 보고한다. 원정착15·velocity-onlyEXHAUSTED, PD/포화UNKNOWN, moving-root 독립교정NOT_DONE, 물성가정·링보류·포그숨김·자기충돌OFF/바닥ON을 유지한다.

## 실행기 통합과 시계

새 namespace experiment hold_diagnostic_098 및 /098/runs만 허용한다. config는 native quota 각1·offline_only=false지만 deadline_unix는 정확int0이다. prepare/run과 remote supervise/native는 활성 deadline과 입력/hash 검사를 통과하기 전 SDK/SimulationApp/물리 실행에 도달하지 못한다. export는096처럼 일반 snapshot보다 앞의 검토 SHA 결속 stdlib-only closed-copy 경로를 유지한다. 재조회는 최초 validation을 덮지 않고 별도 query를 남긴다. 실패 snapshot/parent/native/seal 및 SDK UNKNOWN 의미도 유지한다.

검토 전 activation과 네트워크는0이다. L4가 계획/정확 source18/하네스/모델/기준/후보를 수용한 뒤, 검토된 coordinator/activator가 exclusive runtime-budget을 먼저 예약한다. 최초 시각+2700초가 단일 종료기한이고 부분 실패도 시계 소비다. config-before를 보존하고 config의 deadline 숫자 한 토큰만 바꾸어 execution-freeze/READY에 결속한다. 소스·후보·review/harness/hash 변조, bool/nonfinite, 이미 존재하는 활성화 파일, 재활성화·reset은 거절한다. 활성화 직후 바로 첫 원격 명령을 보내며, 중간 로컬 준비도 이45분에 포함한다. activated source의 config 외17파일은 검토 바이트 그대로다.

local budget에는 최초 UTC와 같은 PC에서 프로세스 사이에 공유되는 time.monotonic 표본을 함께 예약한다. driver의 순수 effective_clock(record,wall,mono)는 단조 경과>=0 및 typed finite anchor를 확인하고 expectedUTC=startUTC+(mono-startMono)를 계산한다. wall과expected 차이가0.25초를 넘으면 clock uncertainty로 거절한다. **소비시각은 expectedUTC만** 사용한다. wall이나max(wall,expected)를 상대기한 계산에 쓰지 않는다. activator/coordinator도 같은 검토 driver 함수를 사용한다. local prepare/launch/remote 대기/SCP/회수 시작·각단계·완료/cleanup의 모든 기한 소비 지점은 결속된runtime-budget과 이단조시각을 사용한다. 추가로 회수의exclusive예약에는startMono와endMono=startMono+600을 함께 기록한다. 각export/SCP timeout은min(300,endMono-currentMono,전역종료까지단조잔여시간)이며완료도currentMono<endMono를요구한다. 최초회수UTC의미세한offset이600초에더해질수없고,두anchor는예약후바뀌지않는다. time.time만 다시 읽어 새600초를 얻거나45분 시계를 바꾸는 경로는 없다. clock jump가 생기면 회수 실패/SDK UNKNOWN과 남은 자료를 보존하고 새원격·다음목적은0이다. 이미 실행한 worker의 고정 watchdog 정리는 유지한다. budget/READY/실행해시를 함께 재검사해 다른세션 anchor나변조/재부팅도 거절한다.

첫 원격 명령은 기존 SSH로 시각/uptime 및 Kit 존재 여부를 읽는 표준 라이브러리/OS 조회다. SimulationApp/native 목적 예약이 아니며 실패해도 시계는 소비된다. 각 목적에서도 upload/압축해제 후 supervisor 송신 직전에 새 원격 시각을 읽는다. clock 기록은 run/job/deadline에 결속해 literal supervise 인자로 넘기고 로컬 원본과 원격 output에 남긴다. 입력/job을 사후 덮지 않는다.

시각 표본은 local send/receive UTC와 monotonic 경과, remote UTC 및 Windows TickCount64(ms)를 포함한다. remote-local offset의 가능한 구간은 [remoteUTC-localReceive, remoteUTC-localSend]이며 양끝 모두 [-1,+1]초 안이어야 한다(밀리초 양자화 여유0.002초를 포함). local wall/monotonic 경과 차이≤0.25초, 순서/유한값/typed integer uptime도 확인한다. 불확실하면 발사0이다. remote supervisor는 같은 TickCount64를 읽어 표본 나이0~120초 및 remote wall 경과와 uptime 경과 차이≤0.25초를 확인한다. 재부팅/시계점프/오래된 표본/다른run·job·deadline은 거절한다. remote native 입장 시각은 remoteUTC+2초를 보수적인 localUTC 상한으로 사용한다. 이2초는 시간 가드이며 물리 판정 허용오차 변경이 아니다. 시간동기화/시스템 설정을 고치지 않는다.

watchdog은 import/정지600, motion900초. supervisor SSH transport는750/1050초, 회수는 export/SCP 각≤300초·단일총600초, 정리30초다. 남은 시간은 import/정지1380초, motion1680초를 **초과**해야 한다. equality는 거절한다. local coordinator/prepare/launch 첫입장, 업로드/확장/clock probe를 마친 supervisor 송신 직전, remote supervisor의 Kit probe/원장예약 후, run_child의 실제Popen 직전에 재검사한다. run_child의 선택 admit callback은 로그 open/keepawake 뒤 마지막에 호출해 앞선 준비의 시간 소비를 반영한다. timeout 산정도 절대 종료기한과 min이며 native watchdog을 늘리지 않는다.

원격 mkdir/upload/확장/clock/probe 등 모든 대기는 남은 절대시간으로 제한한다. 호출 실패로 다음 목적을 시작하지 않는다. 목적별 local attempt와 remote native reservation은 각각 exclusive/1회라서 transport 실패 뒤 재전송하거나 native 예약을 지워 재발사할 수 없다. 회수는 transport/native 결과와 별도 상태이며 기존600초 시계의 재시작/우회/SCP retry가 없다. archive/receipt 생성도 exclusive이고 입력/출력 hash·ZIP CRC·안전 경로·닫힌 PID/결과를 검증한다. 새 exporter의 첫 실제 원격 동작은 import 회수에서 확인한다.

세 목적 최악은4440초로45분을 넘는다. 빠른 실제 종료와 회수가 전제이며 시간 부족이면 motion NOT_RUN으로 종결한다. 원격 cleanup/PID/lock 확인도 종료기한 안에서 수행하고, 종료 후 새 remote/native를 보내지 않는다. 자기 worker의 watchdog 정리만 허용하며 다른 Kit를 종료하지 않는다. 로컬 분석·영상 인코딩·인계·커밋은 원격 시계 뒤에도 가능하다.

## HOST와 검토 입력

096 closed-copy/receipt·오류분류·재조회 보존·실제entry/launch 회귀를 새 source18에서 재현한다. 기존 offline-only 전용 검사는 새 deadline0 gate와quota1/namespace 검사로 바꾸고 scene HOST29는 위수량2개와 결과쓰기namespace를 맞춰 실행한다. protected096 등소유밖 쓰기trap으로구fixture의보고서덮기를검출하고새fixture가098에만쓰는지실측한다. 097 후보검증과 원34초 실패 재생을 새 program 바이트에서 확인한다. 기존095 actualUSD typed/hash 증거는 scene/root_binding 불변에 결속한 과거 로컬 증거로만 재검증하며 새 SDK 검사를 했다고 표시하지 않는다. fresh native import/정지가 실제 설치/물리 게이트다.

추가 HOST는 실제 launch/coordinator/remote supervise/run_child 경로에 가상 transport/clock/Popen을 대입한다. 준비 후 여유가 equality를 지나면 Popen0임을 확인하고, 송신 직전 검사 또는 run_child admit를 제거한 정확 변형이 대응 음성에서 FAIL이어야 한다. clock offset/시각점프/uptime/age/job/deadline 변조, 1380/1680 경계, watchdog/transport/300/600/절대기한, 목적별1회와 정지 실패 후 motion0, 활성화 한 토큰/false권한/중복예약/소스변조 음성과 정상 양성을 포함한다. 특히회수 actualcaller에첫300초뒤wall-500초/단조경과유지와wall정지/단조600초소비를대입해새SCP또는성공게시가거절되는지확인하고,기존time.time전용복원변형에서900초회수가성공하는반례를그대로검출한다. 전역2700초경계도같은anchor에서양음성검증한다. 코드 compile·PowerShell parse·보호 hash·기계검사가 L4보다 먼저다. R1 수리 시 원 source/하네스/증거/freeze를 보존한다.

## 실제 실행과 진단

검토 후 단일시계 활성화 → 첫 원격 OS 조회 → fresh import1 → 수용 시 정지1 → SMOKE_VERIFIED 및 시간여유가 있을 때 motion1 순서다. 매 단계 source/execution/budget와 원물리 게이트를 재검사한다. 실패·partial·TIMEOUT·회수 실패·기한초과는 원본 그대로 보존하고 다음 목적을 발사하지 않는다. SDK미실행 여부를 일반 회수 예외에서 추론하지 않는다.

full report/terminal과 parent/remote-shell/PID/job/source, 전체 봉인, journal5041행,421PNG의 CRC/clock·sidecar 및6endpoint를 대조한다. 실패partial이면 실제 확인한 prefix만 보고한다. 33~42초 중 같은 전체 목표/연속120Hz 관측만 분석한다. 원34초 endpoint와42초 endpoint, J3/J5 및 전체9축의 부호오차/속도·최초진입/이탈·통과 표본구간·마지막1초 범위를 분리한다. 기준 진입을 연속시간 안정성이나 유일 원인으로 확정하지 않는다. 1x/3x 영상은 확보 원PNG만으로 만들고 전체decode 및 첫/중간/끝을 직접 확인한다. 외부 업로드는 없다.

## 9개 이진 수용 기준

AC1 사용자 범위/실물false·새45 단일지연시작. AC2 원자료/과거소진/보호hash·소스12불변/인계바이트 보존. AC3 097 후보 byte·원34초/기준·전체물리consumer 유지. AC4 18소스/job/hash/리뷰/activation 한토큰 및 입력 경계 결속. AC5 local 단조경과/remote clock 증거·실제 Popen 직전 admission·절대대기/1380/1680. AC6 closed fast export300/단일600·최초실패/SDK UNKNOWN·무재시도. AC7 실제 caller/activation/clock/Popen의 양음성·정확변형·정지선행·기계검사. AC8 유한 L2/L4·지적union/class/소진/다음임계·동일계열 편향/실행권한 구분. AC9 실제 실행·부분/전체·정착 진단/영상·PID/lock·한계·인계/정확소유localcommit/push0.

계획/코드 PASS는 실제 정착 PASS가 아니다. 실제 결과에 따라 IMPORT_VERIFIED/SMOKE_VERIFIED/WORKSPACE_MOTION_VERIFIED 또는 실패/미실행을 기록하고, 원34초 실패가 남으면 전체 물리 BLOCK을 유지한다. 이번 승인 안에서 추가 native/튜닝/실물 CAN으로 확장하지 않는다.

## L4 R1 한정 구현수리 추가 — 원본문/R1 보존

R1의 BLOCK5/4와 원계획·source18·하네스13·HOST253·freeze는 review/l4-r1-preserved/에 보존한다. 비작성자는 다음4건을 승인된098 통합·42초 진단 범위의 제한된 L3 수리로 판정했다. L2 2/2는 종결 그대로이며 새L2/자동R3/새예산은 없다. 아래 명시한 범위가 앞선 사전계획의 충돌하는 구현 가정보다 우선한다. 마지막 L4 R2가 전건을 재현·폐쇄하지 못하면 source/runtime을 활성화하지 않는다.

F1: local 목적별1회는 run별 marker뿐 아니라 canonical runs 폴더의 purpose별 exclusive marker로 강제한다. prepare도 이미 소비한 목적을 새UUID로 다시 준비하지 못한다. coordinator의 정지 선행/실패 후 중단과 remote native quota각1은 그대로다.

F2: supervisor가 child를 시작하기 전에 거절한 경우에도 최초 stdout/stderr가 없으면 빈 원로그를 exclusive생성한 뒤 failed-parent snapshot을 봉인한다. 기존 로그를 덮거나 SDK/물리 실행으로 표시하지 않는다. NOT_STARTED/childPID null/원실패 code를 보존하고 frozen recovery.py의 닫힌 실패복사 경로로 검증한다.

F3: clock 조회의 raw stdout/stderr, local send/receive/monotonic 경과와 returncode를 검증보다 먼저 exclusive기록한다. remote실패/timeout/offset/Kit존재/parse/왕복후localclock거절의 원자료와 별도실패사유를 보존한다. 같은조회 context의 반복은 원자료를 바꾸거나 재전송하지 않고 거절한다.

F4: 원52초 workspace dataset/cloud/path6241 및 generator.validate_result(...,full=True)의 검증은 그대로 유지한다. **validate.py의 verify_workspace helper만** 마지막 실행program 결속을 수정한다. 검증한canonical52 program의 첫9segment와동일목표hold8초로 정확097의42초/5040/421후보를엄격구성하여실제input sourceprogram과near(...,0)로비교한다. baseline52 workspace sampling과actual42 execution의의미를분리한다. 다른validate함수·모든물리/정착/COM/한계/렌더수치기준·workspace.py·scene.py·SDK는변경하지않는다. 따라서이전12바이트불변목록에서validate.py의이helper만명시예외로하고나머지11파일은바이트동일이다. 모듈AST에서이helper외변경0을검사하며전체actualprepare→snapshot/job/bundle의양성·악성prefix/hold/기준/canonicaldata·원helper복원음성으로결속을검증한다. 이예외는새물리허용오차나일반프로그램fallback이아니다.
