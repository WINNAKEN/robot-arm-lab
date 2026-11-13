> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 109 — 코드 최종 L4 R2 BLOCK / 실제 시각 변경·SDK 미실행

현재 결과: HOST263·compile7 통과, 코드 L4 R2 BLOCK4/2·2/2 종결이다. 시각 변경·UAC·SDK·native45·실물 CAN은 실행하지 않았다. 현재 읽기 관측은 원격이 5.273~5.300초 앞서 원래 ±1초 조건을 충족하지 못한다. 세부 최종 결과는 아래 2026-11-03 절에 있다.

## 2026-11-02 계획 단계 기록 (당시 상태)

2026-11-02 KST. 107의 핫스폿 전환 불가 응답 뒤 원래 Wi-Fi 유지와 상대 시각 불일치를 읽기만 했다. [109 계획](109-relative-clock-alignment.md)의 최종 비작성자 **L2 R2 PASS6/0**다. **계획 검토만 완료**했으며 새 도구 구현·HOST·코드 L4·OS 시각 변경은 아직 없다.

- [관측] 107 A0는 NTP 0/3, B 전환 불가/A1 미실행이다. 원래 NIC/경로/프로필·전체20 binding/NTP provider 유지가 확인됐다. 이번 응답 뒤 NTP 추가 요청0, 네트워크/시간 설정 변경0이다. 호스트·경로·서버의 NTP 인과는 미확정이다.
- [관측] 별도 OS 시각 읽기는 원격−로컬 구간 `[1.6648609638, 2.7080295086]`초를 얻어 전체가 +1초 밖이었다. 이 구간은 SSH 시작 지연과 ms 양자화를 포함한다. 원격 시간서비스는 Stopped/Manual이었다. 공인 UTC 정확성·108 admission certificate가 아니다. 이전 대화형 시각 조회는 미완료 UNKNOWN으로 보존했고, 그 자기 진단 자식만 명령/생성시각/핸들을 고정해 terminal을 확인했다. 초기 정리 명령의 배열 해석 실패도 지우지 않았다.
- [관측] L2 R1은 Major1건/4MET·2UNMET로 BLOCK이었다. 상위 종료 뒤 관리자 worker가 늦게 첫 변경을 하는 lifecycle 반례다. 원계획과 판정은 `before-L2-r2/`에 보존했다. R2에서 UAC 전 소비·단일 단조권한 구간·job containment·실제 terminal/IN_FLIGHT_UNKNOWN·후속 native 차단을 보강해 계획상 union1/open0/new0으로 폐쇄됐다. 기존103 class의 세 번째 실측 반례나 실제109 OS 결함이라고 계수하지 않았다. 모든 원계보와 임계는 유지한다.
- [관측] 최종 계획 SHA `6984878e7e5a10435c230594551017f500c4bed2330f0936d965536a04736b29`, [L2 R2 JSON](../../outputs/relative-clock-align-109/review/L2-r2.json) SHA `a3514ae18ef1a45daaa0d79871be3ca0fa5763ab287f4c1cbdd83e1ff0ebce6d`다. L2는2/2로 닫고R3는 없다. 동일계열 비작성자 폴백의 공통편향은 남는다.

제안 범위는 실제 승인 후 구현·HOST·비작성자 코드 L4를 먼저 끝내고, 새로 얻은 상대 시각 표본과 runtime containment가 모두 유효할 때만 **로컬 Windows 시각을 절댓값5초 이내에서1회 정렬**하는 것이다. 이미 ±1초 안이면 변경하지 않는다. 원격 시계·시간서비스/NTP 설정·방화벽·VPN·네트워크·바인딩은 바꾸지 않는다. 현재 약+2.19초라는 값을 나중에 그대로 적용하지 않는다. 시각 정렬이 공인 UTC 동기화나 NTP 차단 원인 해결을 의미하지 않는다.

별도로 승인된108 새45분은 실제108 첫 원격 실행부터 시작한다. 시각 정렬의 typed 성공/변경 없는 검증 성공과 종결 확인, 별도 native45 승인, 기존 시계/안전 gate를 모두 갖춘 뒤 import→정지 수용→42초 진단 순서로만 이어간다. UNKNOWN/containment 실패는 변경·native를 거절한다. 로컬 준비·코드 검토·시각 정렬 중에는 새 native 예산을 시작하지 않는다.

Win32 API 의미는 공식 [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [배속 권한·제약](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject), [SetSystemTime의 UTC·권한](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-setsystemtime)을 확인했다. 이 문헌은 현재 호스트의 관리자 배속/종결·미구현 코드의 실제 동작 증거가 아니다. 후속 구현의 HOST·비변경 containment 관측·L4와 runtime fail-closed 검증을 생략하지 않는다.

현재 source109 파일0·OS 시계 변경0·UAC0·새108 native45 승인/예산0·SDK/native/실물CAN0이다. 108의 검토된 source/harness31개와 deadline int0·미생성 native marker를 유지한다. 게인64/16/cap·모델·097후보·원 물리/시간 기준·기존 실패/종결 회차·물성가정/링 보류를 보존했다. 이 결과는 실행 준비 완료나 실제 정지/42초 성공을 뜻하지 않는다.


## 2026-11-03 실제 구현·최종 결과 (위 계획 단계 기록 이후)

사용자 「다음 작업 진행해」를 직전 제안의 로컬 시각 정렬 및 조건부108 새45분 진행 지시로 기록했다. source6/harness2의 M8 후보를 구현했고 HOST는 R1 198→R2 263(core46/Win32193/runner24), compile7이 통과했다. 실제 자기 비관리자 Job 자식의 종료·last-handle-close와 새 hard_stop의 controller Exit124→고정 worker terminal도 확인했다. 이는 관리자 시각 변경 수용이 아니다.

최종 **코드 L4 R2 BLOCK4/2**, L4 2/2 종결·R3 없음이다. [원 R1 판정](../../outputs/relative-clock-align-109/review/L4-r1.json)은 Major4건이었다. 원자료 reader-start 유실과 stderr에 의존한 안전 종료는 기존 class의 제3 임계에 도달해 그 구현·검증 source가 EXHAUSTED로 판정됐다. R2는 직접 파이프 읽기·독립 IO 없는 hard 종료 등으로 새 source를 설계했으나 [최종 판정](../../outputs/relative-clock-align-109/review/L4-r2.json)에서 두 문제가 남았다.

- 기존 실제5초 cap: guard 후 fresh target으로 원4초 지연 반례는 닫혔다. 그러나 마지막 UTC snapshot 뒤60ms 스케줄 정지에서 모의 setter 입구의 실제 보정량−5.005초/API ok가 재현됐다. 마지막 userspace 검사와 syscall entry 사이가 원 actual5초 조건을 보장한 것으로 취급할 수 없다.
- 새 pending-entry lifecycle: launch Thread.start가 반환했으나 target 첫 줄이 아직 실행되지 않은 상태를 terminal로 오판하고 hard fence를 해제했다. 그 뒤 첫 launch가 실행되는 반례가 재현됐다. 원 returned-handle 반례의 수리와 다른 새 표면이며, lifecycle의 연속 union3 임계와 수리→생성 대응으로 해당 소유/종결 source도 EXHAUSTED다.

원 raw/restoration 소진 상태는 해제하지 않았다. 전체 시뮬레이션·상대 정렬 도메인 소진이라는 판정은 아니다. R1 source8·원 BLOCK/관측·R2 source8과 모든 실패를 보존했으며, R1 보존본에서는 원4개 반례를 다시 재현할 수 있다. 동일계열 비작성자 폴백 편향도 남는다. 소스 추가 수리나109 L4 R3로 진행하지 않는다.

실제 root context(2)는 최종 BLOCK을 읽고 `L4 PASS required`로 거절했다. clock-approval/109 execution attempt/실제UAC/SetSystemTime은0이다. 원108 source/harness31·PASS9/0·deadline int0·native marker 부재를 유지했다. 실제 Isaac/정지/42초/native45/CAN 실행0이다.

검수자는 [원108 범위 판정](../../outputs/relative-clock-align-109/review/final-r2/scope-disposition-108.md)에서109 BLOCK을 원108 도메인 전체 취소로 확장하지 않았다. 그래서 실제109 pending 작업이 없는 상태에서 현재 시각을 별도 읽기만 했다. 첫 coarse 조회는 SSH 시작 지연 때문에 폭1.5초를 넘겨 UNKNOWN으로 남겼다. 이후 동결된108의 순수 OS READY/challenge producer만 사용해 시작 지연을 분리한 [독립 현재 관측](../../outputs/relative-clock-align-109/independent-ready-challenge/result.json)은 **원격−로컬 [5.2727070789,5.2999540825]초**였다. 도착 RTT0.016초·wall/monotonic 차이0.007247초·site_loaded=false/Kit0·두 원문 EOF/자기Job active0을 기록했다. clock_probe/session/budget/109mutator는 호출하지 않았고,108 인증서나109 성공 영수증을 만든 것도 아니다. 현재 원래 ±1초 조건이 실패하므로 원108 예산도 활성화하지 않았다.

후속 [110 단일 호스트 controller 초안](110-single-host-controller-draft.md)은 OS clock setter/UAC를 없애고 감독자와 SDK를 같은 PC 시간축에 두는 방향이다. 현재는 정적 접점 조사와 미확정 의존성 목록만 있으며 L2·코드·원격 실행은 없다. 기존109 실패/소진/종결 예산을 새 번호로 초기화하지 않는다.
