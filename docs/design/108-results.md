> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 108 — 비활성 실행기 구현·최종 검토 완료 / 실제 원격 실행 대기

2026-11-02. 사용자 계속 지시에 따라 새108 실행기를 로컬에서 구현했다. **L2 R1 PASS9/0, R1 제품 결함1건 수리·통합HOST587·최종 L4 R2 PASS9/0 및 실제root 무승인 거절 확인 완료**다. 새 원격/SDK/SimulationApp/native/실물CAN 실행과 새 시뮬45분 생성은0이다. 게인64/16·cap·모델·원 물리기준·097의42초 후보와 기존 시간 gate를 유지한다.

## 구현 범위

새 source는 `src/simulation/clock_ready_resume_108/`의18파일, harness는 `outputs/isaac-clock-ready-108/`의13파일이다. 실질 변경은 A7/B10=17파일이며 물리/회수 source13개와 generic execute.ps1은 부모099 바이트 그대로다. driver 전체 AST는 명시namespace/protocol/plan 결속 외에 동일하다.

현재099 active config와 소비된 예산/실패 marker는 보존했다. 새config는 원 inactive template에서 remote root/experiment 두 필드만 바꾸고 deadline을정확int0으로 유지한다. configured native_limits 각1과 offline_only=false는 미래 구성 상한이며 실행 권한이 아니다. 별도 native-approval/runtime-budget/activation/execution-freeze/clock-query marker는 root에 없다.

검증 helper는 새108의 실제 L2 round/plan/hash와 부모099 최종 회귀를 읽도록 바꿨다. 새root에옛R1 freeze/clock208/L2R2가 있다고 가정하지 않는다. 보호 원장은 원5995+추가1966(중복8)의 정확합집합7953이며 빈원장·누락그룹·부모해시재설정 거절을 검사한다. 원USD 정책 증거는099가 핀한 동일바이트의 재사용이며 새SDK 실행이 아니다.

## R1에서 실행한 로컬 검사

| 구분 | 실제 결과 |
|---|---:|
| A | clock274 + repairs23 + recovery89 + scene29 =415 PASS |
| B | activation87 + timing64 + entry8 + analysis10 =169 PASS |
| 통합 | 원581 사례 전부 보존 + 새scope 경계3 =584 PASS |
| 별도 메타데이터 검증 | 양성2 + 음성15 =17 PASS |
| 별도 A AST 관측기 대조 | 정상메타데이터 양성1 + 비metadata 변조 음성2 =3 PASS |
| 기계 검사 | Python compile26·PowerShell parse PASS |
| 보호 원장 | 현재7953 파일 SHA 전건 일치 |

통합 실행은170.344초/rc0이었다. summary의 `gate_negative_controls=17`은 그룹 전체 수이며 그중 양성2/음성15로 구분한다. 음성17개를 수행했다고 표현하지 않는다. A의 초기AST 관측 정규화 오탐2회는 producer 변경 없이 원관측과 수정 관측을 기록했다. B의 초기 시간기록 label 정정도 원JSON을 별도 보존했다. 실패나 중간 관측을 지워 통과로 덮지 않았다.

원자료는 [통합 결과](../../outputs/isaac-clock-ready-108/host-summary.json), [메타데이터 검증](../../outputs/isaac-clock-ready-108/gate-host.json), [A 변경 영수증](../../outputs/isaac-clock-ready-108/rebind-A.json), [B 변경 영수증](../../outputs/isaac-clock-ready-108/rebind-B.json)에 있다. 현재source-freeze-r1 SHA는 `aff9d2178b3b6f8bcac84de02ffa3c463d4f81b7b411173e010b636d9eb2f253`이다. L4 전 정확한31코드파일·계획·핵심증거는 `review/r1-candidate/`와 영수증에 보존했다.

## R1 당시 실제 수용과 남은 단계 (최종 상태는 아래 R2 절)

검토는 A/B 별도 비작성자 렌즈와 통합AC1..9 지적합집합으로 진행한다. 동일계열 사용자승인 폴백이며 외부계열 부재의 공통편향은 남는다. L2 사용1/2, L4 R1/max2이며 기존099/103 등의 닫힌 회차를 재개하거나 class 임계를 초기화하지 않는다.

지금의 HOST는 소스·로컬 경계 검사다. 새시계 인증·정지·42초 관측·원격 회수 성능은 NOT_RUN이다. 최종 코드PASS가 나오면 실제root의 무승인 activator/coordinator가 budget/transport 전에 거절되는 로컬 음성을 추가 확인하고 상태·인계를 기록한다. 실제 원격은 해당108의 별도 명시45분 승인과 모든기존시간·안전 gate를 갖춘 뒤 import→정지수용→42초 순서로 진행한다.

NTP 쪽은 새 [107 읽기 사전상태](../../outputs/ntp-network-107/preflight-current.json)에서 기존 Wi-Fi/Public/192.0.2.10→192.0.2.10, W32Time Running/Manual이나 Leap3·Stratum0·Local CMOS·동기화오류1이었다. 핫스폿 수동 전환 가능 여부는 아직 답을 받지 않았으며 전환·NTP질의·resync·설정변경은 하지 않았다.105의 원34초 실패/전체BLOCK과 PD/포화UNKNOWN·moving-root독립교정NOT_DONE·물성가정/링보류를 유지한다.

## L4 R1 당시 판정과 수리 범위

A렌즈 PASS5/0, B렌즈 BLOCK3/2, 통합 BLOCK7/2로 고정됐다. 제품 결함은 `REVIEW_UNIT_IDENTITY_NOT_ENFORCED` 1건이다. 나머지 새108 plan/freeze·typedPASS 조건이 모두 맞는 scaffold에서 L4 JSON의 unit099 또는 unit 누락을 activation.context가 수용했다. 두 입력은 같은 누락의 한 instance다. 실제 옛099 PASS를 그대로 재사용할 수 있다는 주장은 아니며 그 경우에는 plan/freeze 핀이 다르다.

비작성자 B관측133경계와 통합관측122개는 각각 저장됐고 원코드·원R1freeze/31코드/판정은 보존했다. prepare-review의 L2 unit108 검사는 존재하며 oldunit 단독 입력을 실제 거절했다. source의 raw/time·103 monitor/restoration 계보와 다른 review-authority 식별 class1이다. 원계보/다음 재발 임계·닫힌회차는 초기화하지 않는다. gate 검증그룹17의2/15 구분은 소비 경로에서도 확인돼 두 번째 제품 결함으로 세지 않았다.

통합 AC5는 실제unit누락으로UNMET, AC9는 최종인계/로컬commit 미완료로UNMET다. AC9는 별도 제품 결함class가 아니다. 나머지7개를MET으로 판정했다. 실제root 두 진입을 로컬 process/network/SDK spy로 차단한 상태에서 missingL4 gate의 거절을 관측해 AC7로 수용했다. 유효PASS 뒤 nativeapproval만 없는 상태의 거절은 아직 postreview 확인 대상으로 남는다. [최초 관측](../../outputs/isaac-clock-ready-108/local-negatives/before-L4/result.json), [안전한 R1 사본 재현](../../outputs/isaac-clock-ready-108/local-negatives/before-L4/replay.py), [통합 판정](../../outputs/isaac-clock-ready-108/review/L4-r1.json)을 구분한다. 최초 인라인 절대경로는 기록자료로 남기고 실행 가능한 재현기는 파일 위치에서 root를 유도하도록 관측 스크립트의 lint 지적을 수정했다. 이것은 생산코드 수리가 아니다.

남은R2에서는 원B작성자가 activation의 exactunit108 조건과 HOST의 unit099/누락/int108 경계를 수정·추가한다. A7·source13·L2계획·기준은 바꾸지 않는다. 수리·통합 재검증과 코드checkpoint/진행 인계를 갖춘 뒤 마지막 비작성자 R2를 받는다. 새R3나 숨은 새단위로 실패를 지우지 않는다.

## R2 작성자 수리·통합 결과 (최종 검토 전 checkpoint)

변경은 `activate-budget.py`의 L4문서 unit이 정확문자열108인지 검사하는 조건과 `host_activation.py`의 fixture/세 단독 경계검사 두 파일이다. 기존 긍정fixture에 unit108을 명시하고 unit099·unit누락·int108은 context/activate/coordinator에서 unit오류로 거절돼 clock/budget/transport로 들어가지 않음을 확인했다. 원87 activation 사례를 보존해90개로 늘었다. A7·source18·나머지11 harness·물리기준·시간계약은 바꾸지 않았다.

R2 B172(activation90/timing64/entry8/analysis10), 전체 통합587(원581+scope3+reviewunit3), 별도메타그룹17(양성2/음성15), compile26/PSparse/원USDtyped핀·전체driverAST·후처리4exact 및 보호7953 전수SHA가 통과했다. 통합164.328초/rc0, 새source-freeze-r2 SHA `008dc8f8d5a10e09458c0144389f87cf9f4b1fa6518078aff78a1367138d0a57`다. [수리 기록](../../outputs/isaac-clock-ready-108/rebind-B-r2.json), [R2 통합 원결과](../../outputs/isaac-clock-ready-108/integration-r2-stdout.raw)를 보존한다.

새freeze의 실제root 두 진입도 L4-r2 파일이 없는 상태에서 process/network/SDK spy로 관측했다. 두 진입은 missingreview 단계에서 거절됐고 root 실행 marker·transport는0이다. 원R1과새R2의 [관측](../../outputs/isaac-clock-ready-108/local-negatives/before-L4-r2/result.json)을 구분한다. 작성자수리/호스트통과가 비작성자 F1폐쇄나 실제remote/native수용을 대신하지 않는다. 현재 코드후보와 원R1실패·수리검증·진행 인계를 로컬checkpoint로 남긴 뒤 남은R2를 받는다.

## 최종 R2 판정과 허용 closeout

A유지확인 PASS5/0·B R2 PASS5/0, 통합 **L4 R2 PASS9/0**, 신규·미해결0으로 고정됐다. [최종 판정](../../outputs/isaac-clock-ready-108/review/L4-r2.json) SHA `40cfe5437a856b90d87402a0bcc7b4381b5beeed44b7bf4be7c5e4a6e795c27b`다. F1은 원R1 동일 반례·정상108 양성·수리함수의 실제 진입 배선으로 union1/open0을 판정했고, 수리가 새동종 표면을 만들지 않았음을 확인했다. 원 raw/time 및103 계보·임계는 그대로다. L4는2/2로 종결하며R3는 없다.

비작성자 B는 독자73경계, 통합 검수자는 독자161검사와 실제commit38개blob을 직접 대조했다. 원581 회귀와 기존7953 전수 검사를 이유 없이 재실행한 수량은 아니다. A는 새7파일과source18/불변13이R1과 같고 B2만 달라졌음을 확인해 이전 별도기전 관측을 유지했다. 같은계열 잔여편향·실제 원격/물리 미검증을 유지한다.

소스와 당시 진행인계·원R1실패를 담은 코드checkpoint는 `18c7a3d97d9c19f18479920f1a442b541278ef19`다. 최종 검수는 실제존재한 이checkpoint를AC9 증거로 평가했으며, 아직 없던 자신의 최종 판정commit이나postreview 음성을 수행한 것으로 적지 않았다. 판정 원문은 수정하지 않는다.

그 뒤 실제현재root의 activator/coordinator에 유효한R2 PASS/현재freeze를 읽게 하고, process/socket/SDK spy를 강제한 상태에서 두 진입이 `native-approval.json` 부재로 거절되는 것을 추가 관측했다. [허용 closeout 결과](../../outputs/isaac-clock-ready-108/local-negatives/post-L4/result.json)에서 process/socket/SDK 호출0·core31 불변·deadlineint0·root승인/예산/activation/query marker 부재를 확인했다. 이는 실제native 실행시험이 아니라 무승인 경계의 로컬 확인이다.

로컬 준비·검토는 완료됐지만 실제108 세션은 별도의 명시45분 승인과 기존 시간/안전 gate를 통과해야 한다. 정지/42초 진단·원격 회수 성능은 여전히NOT_RUN이다. 종료 전에 읽기만 한 [현재NTP 도달성](../../outputs/ntp-network-107/after-local-prep-reachability.json)은 고정Microsoft 주소3표본 모두시간초과/rc0이었다. native rc0을 성공으로 세지 않았다. 최신상태도Leap3·Stratum0·Local CMOS·오류1이며,107 핫스폿 비교의 수동 전환 가능 여부는 아직미응답이다. 이3표본은 현재경로의 읽기진단이고 정식핫스폿A/B/A를 시작한 것이 아니다. 네트워크전환·resync·설정변경은0이다.
