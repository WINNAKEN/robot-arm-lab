> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 108 — 별도 비활성 시뮬레이션 실행기 재결속·로컬 검증

2026-11-02. 사용자 `하면서 시뮬관련 병렬로 안될까/`와 후속 `작업이어가`에 따라105의 실행 준비 점검을 실제 로컬 준비물로 이어간다. 이번 승인은 로컬 준비·검토 범위다. 107 핫스폿 수동 전환 가능 여부는 미응답이며 네트워크를 바꾸지 않는다. 새 원격45분·SSH·SDK·native·실물CAN을 승인받은 것으로 해석하지 않는다.

## 목표와 소유

소비된099를 재발사하지 않고 검토 가능한 새 비활성 사본을 만든다. 소유는 `src/simulation/clock_ready_resume_108/`의 source18, `outputs/isaac-clock-ready-108/`의 harness13·HOST/검토·영수증, 본 계획/108-results.md와 최소 공유 인계다. old099/098 및095~107의 원소스·실패/예약·원장·검토/예산·CAD/URDF/BOM/펌웨어는 변경하지 않는다.

기반은099 최종 source18/harness13과 `config-before-budget.json`의 원 비활성 바이트다. 현재099 active config는 승인된 옛 deadline 한 토큰 변경 그대로 보존하며 새 기한으로 덮지 않는다. 새 program은097과 바이트 동일하다. 물리/회수 불변13파일은 sdk.py,scene.py,capture.py,launch.ps1,workspace.py,init_boundary.py,torque.py,reference.py,balance.py,root_binding.py,recovery.py,validate.py,program.json이다. generic execute.ps1도 바이트 복사한다.

## 닫힌 변경 census와 분할

실질 변경은17파일이며 L등급을 두 M단위로 분할한다. 코드 작성자는 타작업자가 함께 있음을 전제로 자기 소유만 수정한다.

| 단위 | 정확 소유 | 개수 |
|---|---|---:|
| A: source/clock HOST | source의 driver.py,config.json,README.md,test_host.py,test_scene.py; harness의 host_clock.py,host_repairs.py | 7 |
| B: 실행·승인/검증·후처리 | activate-budget.py,execute.py,host_activation.py,host_timing.py,host_entry.py,prepare-review.py,audit-native.py,analyze-hold.py,root-com-witness.py,encode-native-video.py | 10 |

A의 default clock274·repairs23·recovery89·scene29(기존415개)는 B 없이 검증할 수 있다. host_clock의 `--analysis`10개는 B의 analyze-hold.py에 결속되므로 B 완료 뒤에만 실행한다. B의 activation/entry/timing은 해당10파일·계획·approval의 결속을 모두 마친 뒤 검증한다. 원 clock 반례의 parent099 `review/l4-r1-candidate/source/driver.py`와SHA는 명시적 역사 입력으로 유지하며 새108에 존재한다고 가정하지 않는다. 최종에는 A/B의 모든 사례를 새root에서 통합 확인한다.

단위별 구현·검수급 투입 상한45분이며, 이는 실제 시뮬레이션용45분 승인이나 사용자에게10분마다 재승인을 묻는 시계가 아니다. A/B의 논리·코드 판정과 통합 판정을 구분한다. L2와L4는 각각 최대2라운드, 추가R3 없이 종결한다. L2는 읽기 중심 검수급에서 A/B 각각의 논리를 판정한다. L4는 A/B 별도 렌즈와 비작성자 통합 판정의 지적 합집합으로 결정한다. 같은계열 비작성자 폴백의 기존 사용자 승인을 재사용하며 공통편향을 남긴다. 표준 bridge의 기존 lint 차단을 수리·우회·재시도하지 않는다.

## 재결속과 비활성 계약

- 새 OUT/remote root/unit/experiment/source 경로·plan SHA를108로 재결속한다. 이전 unit 문자열을 무차별 치환하지 않는다. 코드의 경로/namespace/권한 scope/명시적 unit 토큰만 대조표로 바꾸며 이전 SHA·회귀 목록·실패 이력은 보존한다. Python AST에서 허용된 namespace·plan SHA·scope 결속 외 producer/clock/transport/회수 논리가099와 동일함을 검사한다.
- config는 원 inactive099 template에서 remote root/experiment만 변경한다. `deadline_unix`는 정확int0이다. configured native_limits 각1과offline_only=false는 기존 stamp 계약의 상한 데이터이며 실행 권한이 아니다. 별도108 approval.json은 로컬 준비/검토true·explicit_native_approval=false·hardwarefalse이며 새 native-approval/runtime-budget/activation/execution-freeze/clock-query marker는 만들지 않는다.
- 새 activation scope는 `108_LOCAL_INACTIVE_RESUME_AND_REVIEW_ONLY`, 향후 native scope는 `108_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S`다. old099 승인이나 다른 scope/PASS/freeze로 활성화하지 못해야 한다. 실제별도 사용자quote·새freeze/비작성자PASS와 닫힌 typed2700/목적각1 결속 전에는 budget/네트워크 전에 거절한다. 단순 UUID나 기한 reset으로 옛 시도를 재사용하지 않는다.
- 원 ±1초/.25초/age120/+2초 인증, C/D20/18/2 단일기한·raw/EOF/생성ID·무재시도/UNKNOWN 계약은 그대로다. 게인64/16·cap·원 물리기준·모델/물성·자기충돌OFF/바닥ON·097의42초 후보·정지 수용 선행을 유지한다. future2700/headroom1380/1680/watchdog600/900/회수300/600도 유지한다.

## 검증 하네스의 실제 변경

기존 prepare-review.py는 단순 namespace 치환으로 재사용하지 않는다. 옛 L2-r2 고정·새root에옛R1 freeze/clock208 증거가 있다는 전제·5995 고정 수량을 제거하고 다음을 명시한다.

1. `--l2-round`로 실제108 L2 PASS/plan SHA를 읽고 새 source18/harness13 census·로컬 authorityfalse·deadline0·새실행 marker 부재를 검사한다. 원099 최종 freeze/R2와 config-before-budget을 고정 부모 입력으로 읽는다.
2. namespace-only 후처리4개는 parent099 frozen 원문과 비교한다. clock HOST는 parent099 최종274개 및analysis10개의 실제 테스트 이름 집합을 보존하고, 나머지 기존 전체581 의미를 이름 매핑과 실제 결과로 대조한다. 새108 scope와old099 실제scope 거절을 격리한 회귀도 포함한다. 예상수량만 채워 원 사례를 지우지 않는다.
3. 이전 보호5995 목록/해시를 보존하고, 현재099 source/harness·소비/실패 영수증 및104~107의 확정 입력을 추가한 닫힌 합집합을108 보호 원장으로 저장한다. 기대 집합/수량은 생성 영수증과 정확히 일치하고 기존5995 항목 누락·빈 원장·누락된 필수그룹을 거절한다. 공유 HANDOFF/SESSION은 별도 raw snapshot 후 기존 바이트를 보존한다. 동시 외부CAD22는 별도 현재 지문으로 관리하며 다른 변경을 되돌리지 않는다.
4. 원USD 정책검사 stdout은 새SDK 실행 대신 parent099가 핀한 동일 바이트를 복사한다. 실제 source scene/root_binding SHA·typed 음성 필수 사례·SimulationApp false/step0을 검사한다. source13·program097·model/ref 핀과 producer AST를 대조한다.
5. A/B 구현 뒤 새root 안에서 실제 HOST/compile/PowerShell parse와 통합검사를 실행한다. 무승인 상태의 actual activator/coordinator 진입은 네트워크 spy/로컬 fake transport에서 거절돼야 한다. HOST fixture의 합성 실행과 root의 실제 activation 상태를 구분하며 루트에는 nativeapproval/소비 marker를 남기지 않는다. 원099 execute/기존 시험은 실행하지 않는다.

## 수용 기준

| ID | 필수 MET |
|---|---|
| AC1 | 로컬 authorityfalse·deadline int0·원격/CAN0·새실행 marker 부재와 old099 소비/실패 보존 |
| AC2 | 정확source18/harness13·mutable17의A7/B10·source13/generic wrapper/097 바이트 불변·허용범위외 AST 변화0 |
| AC3 | 원5995 보존+필수추가의 정확 union 원장·모델/ref 핀·공유원문/외부CAD 보존 |
| AC4 | parent099 최종 전체581 회귀 의미·clock274/analysis10 보존, 새scope/old099거절 양음성·compile/PSparse |
| AC5 | 새 plan/PASS/source/freeze/approval 결속·올바른 review round·없는 옛R1산출 전제0 |
| AC6 | 기존 시간인증·2700/headroom/watchdog/회수·typed필드·single attempt/raw/UNKNOWN 계약 무완화 |
| AC7 | 실제무승인 root activator/coordinator가 budget/네트워크 전에 거절, fixture 성공을native수용으로 세지 않음 |
| AC8 | A/B와통합 비작성자 지적union·class원장·기존임계/닫힌회차보존·L2/L4각max2·동일계열편향 |
| AC9 | freeze/결과/검토/원문인계·로컬commit, 실제native-ready와로컬검토수용 구분/외부게시·push0 |

원099 raw/time class 각합집합2→다음별개3 충분임계,103 monitor/restoration-I/O 각2→다음별개3,닫힌L2/L4 회차·정착15/velocity-only EXHAUSTED를 재명명으로 초기화하지 않는다. 새 동일class 발생 여부·소진 판단은 비작성자가 기존 원장과 함께 판정한다. 최종 PASS도 기존 시간 gate 통과나 실제 원격환경/정지/42초 성능을 보장하지 않는다. 실제 실행은 향후 새108 native 범위와 첫 원격부터 새45분 명시 승인 뒤에만 진행한다.
