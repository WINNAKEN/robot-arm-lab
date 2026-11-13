> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 109 — 로컬 상대 시각 1회 정렬 및 108 재개 제안

2026-11-02 KST. **계획만 / 시계 변경·새 원격45분·SDK/native 미승인·미실행**이다. 107 사용자 응답 「전환이 안 됨 / 원래 Wi-Fi 유지」에 따라 핫스폿 B와 A1은 실행하지 않는다. 원래 A 연결 유지 확인과 별도 읽기 전용 상대 시각 진단을 완료했다. 이 계획은 NTP 원인 해결을 주장하거나 기존 시계 gate를 완화하지 않는다.

## 근거와 한계

- 107 A0는 같은 Wi-Fi/NIC·바인딩20개에서 고정 NTP 주소3표본 모두 timeout이었다. B 전환을 수행하지 못해 호스트·원래 인터넷 경로·서버를 분리하지 못했다. 원격 Python 런처 부재로 NTP 대조도 실행 전 끝났고 실제 원격 NTP 요청0이다.
- 현재 비대화형 SSH의 Windows UTC 1회 읽기는 원격−로컬 차이 `[1.6648609638, 2.7080295086]`초를 관측했다. SSH 시작 지연을 포함하는 보수 구간이며 원격 ms 양자화도 포함했다. 구간 전체가 +1초 밖이다. 원격 W32Time은 Stopped/Manual이었다. 양쪽 UTC의 표준시 정확성을 입증한 자료가 아니다.
- 그 전 대화형 PowerShell 조회는 READY 이후 응답을 얻지 못해 UNKNOWN으로 보존했다. 이 미완료 자료를 성공으로 세지 않으며 같은 대화형 방식을 재시도하지 않는다. 비대화형 읽기는 다른 관측 기전이며 108의 admission certificate나 새 native 예산이 아니다.
- 검토 완료된108의 `clock_bounds`는 상대 차이의 전체 불확실 구간이 ±1초 안에 들 것을 요구한다. 공인 NTP 동기화 자체를 physics producer의 입력으로 요구하지는 않는다. 따라서 상대 시각 정렬은 별도 환경 수리 후보다. NTP 원인·표준 UTC 정확성은 계속 미확정으로 남긴다.

## 제안하는 변경과 소유

승인받으면 로컬 Windows 시스템 시각만 최대 절댓값5초 이내에서 **한 번** 조정한다. 원격 PC 시각·W32Time 상태/설정·NTP provider·방화벽·VPN·네트워크·바인딩은 바꾸지 않는다. 현재 약+2.19초라는 값을 나중에 그대로 적용하지 않으며, 관리자 준비가 끝난 뒤 새 측정을 얻는다.

로컬 준비물 후보는 새 `src/simulation/relative_clock_align_109/`의 승인 gate·측정/판정·단일 OS 시각 변경 래퍼·HOST 검사와 `outputs/relative-clock-align-109/`의 비활성 설정/검토/원자료다. 아직 생성하지 않았다. 기존103/104/108 소스·승인·소비/실패 marker·deadline·물리 기준을 고치지 않는다. 공유 인계에는 원문 보존 후 결과를 덧붙인다.

구현 전 L2 논리 검토, 구현 후 실제 HOST·기계 검사와 비작성자 L4를 수행한다. 검토는 각각 최대2회로 닫으며 같은 계열 폴백의 편향을 기록한다. L2 R1은 lifecycle 계약 누락1건으로 BLOCK4/2였고 원계획·판정은 `outputs/relative-clock-align-109/before-L2-r2/`에 보존했다. 이 R2에서는 아래 권한 수명·종결 계약만 보강한다. 기존099/103/108의 종결 회차·실패 class/다음 재발 임계는 재개하거나 초기화하지 않는다. 109에서 같은 class가 관측되면 기존 원장에 결속해 재분류한다. 이 계획 검토는 코드 L4나 OS 실행 수용이 아니다.

## 승인 후 순서와 강제 조건

1. 아직 native 예산이 시작되지 않았고 두 PC의 Kit/Isaac 작업이 없음을 확인한다. 로컬 한정 시각 보정과 별도108 native45의 승인 범위를 분리해 기록한다. 시각 보정이 거절되면 조회/계획 자료만 보존하고 변경 호출0으로 종료한다.
2. inactive helper와 HOST를 준비해 비작성자 검토를 먼저 끝낸다. 승인·계획·소스·검토 hash를 결속하고 OS mutation은 기본 거절한다. 실제 변경은 관리자 worker 내부의 동기 Win32 `SetSystemTime` 호출 하나로 한정하고 외부 Set-Date/PowerShell job·예약작업·서비스에 변경을 위임하지 않는다. 필요한 권한의 획득/원복은 해당 worker 토큰에만 한정한다. 구현·검토 중 UAC/Set-Date/SetSystemTime 실행0이다.
3. 실제 시계 변경 승인이 있고 사용자가 관리자 창에 응답할 수 있을 때 로컬 UAC 한 번을 요청한다. 취소/권한 부족/타임아웃은 미실행 또는 UNKNOWN으로 남기며 자동 재발사하지 않는다. 원격에는 관리자 요청을 하지 않는다.
4. UAC가 끝난 뒤 새 비대화형 SSH OS 시각 표본을 얻는다. SSH host-key 검증을 유지하고 peer/machine을 확인한다. 표본의 왕복은 단조시계로 재며 로컬 wall/monotonic 차이≤0.25초, 전체 불확실 폭≤1.5초, 표본 나이≤5초, 보정량 절댓값≤5초를 모두 강제한다. 부분 출력/해석 불가/조건 미충족은 변경0으로 종료한다. 실패 표본을 반복해 유리한 것만 고르지 않는다.
5. 새 구간 전체가 이미 ±1초 안이면 변경 없이 다음 검증으로 간다. 그 외에는 새 구간 중앙값으로 로컬 UTC를 한 번 보정한다. 변경 전후 UTC/단조시각·선택 delta·원자료·실제 API 반환을 보존한다. 설정값/과거 표본으로 delta를 대체할 수 없고 두 번째 조정이나 자동 clock rollback을 하지 않는다.
6. 새 읽기 전용 상대 시각 검증으로 ±1초 전체 구간과 wall/monotonic coherence를 확인한다. 불확실/실패하면 실제108 실행 전에 중단하고 수동 복구/후속 판단을 요청한다. 원래 잘못 맞던 시각으로 자동 되돌렸다고 복원 성공을 주장하지 않는다. 정렬 성공도 공인 UTC 정확성이나 NTP 원인 해결을 뜻하지 않는다.
7. 별도로 **108 첫 원격 실행부터 새2700초 예산**이 승인된 경우에만 현재 reviewed freeze/PASS에 결속된 native 승인과 예산을 만든다. 기존 gate를 그대로 통과한 뒤 import→정지 검증→정지가 수용된 경우42초 진단 순서다. 시각 보정/로컬 준비·검토 시간을 새 native45로 계산하거나, 시각 보정 승인만으로 native45를 승인받았다고 간주하지 않는다.

## R2 권한 수명·단일 소비·종결 계약

- 실제 실행을 승인받은 뒤, **UAC 전에** invocation nonce·시작boot/`GetTickCount64`·parent PID/생성시각·승인/계획/실제 실행 payload/검토 hash를 불변 인자로 묶는다. `attempt`를 배타 생성·flush/fsync한 뒤에만 UAC로 간다. 예약 실패는 변경0이며, 취소/UNKNOWN/결과 저장 실패 후에도 그 소비를 지우거나 자동 재진입하지 않는다. 파일 예약은 중복 방지 수단이며 실행 권한을 주는 수단이 아니다.
- UAC 대기부터 보정·후검증까지 **같은 boot의 단일 단조시계 구간180초**를 공유한다. 그중 마지막10초는 종결 확인 전용이다. UAC≤90초, 각 SSH 조회≤20초, 표본 후 변경까지≤5초이며 모든 단계는 남은 전체 구간으로 다시 제한한다. stage timeout·parent 상실·사용 구간 만료 후 새 OS 변경 권한은 없다. sample RTT/age 제한을 작업 lifecycle 상한으로 대신하지 않는다.
- 낮은 권한 controller는 UAC 호출을 별도 제어 흐름에서 요청하되 주 감독은 계속 deadline을 감시한다. UAC 호출 자체가 아직 반환하지 않아도 전체 상한을 관리한다. 이미 승인된 실행 payload를 메모리에 고정해 넘기고, 디스크의 다른 코드/인자를 나중에 다시 읽어 privileged 작업으로 대체하지 못하게 한다.
- UAC 전에 controller가 non-inheritable Windows Job Object를 만들고 `KILL_ON_JOB_CLOSE`를 설정한다. 관리자 worker는 고정 job/parent 생성시각/nonce를 확인하고 **자신을 그 job에 실제 배속한 뒤**, worker 쪽 job handle을 닫아 controller만 마지막 job handle을 소유하도록 한다. 실제 배속·handle 소유·부모 생존·남은 구간을 확인하기 전에는 시각 변경 API에 도달하지 않는다. job 배속/권한/IPC를 현재 호스트에서 확인할 수 없으면 변경0으로 종료하며 breakaway·보호 완화·다른 변경 경로로 폴백하지 않는다.
- 시각 변경 API는 그 worker 안에서만 실행한다. controller는 deadline/오류에서 job을 종료하고 **고정된 process handle의 terminal과 job 활성 process0**을 실제 확인한다. controller 자체가 사라지면 마지막 handle close로 worker도 종료되는 구조를 사용한다. 늦은 UAC 승인으로 worker가 뒤늦게 시작했을 때는 고정 job/parent/기한이 유효하지 않으므로 변경 호출0이어야 한다. IPC/파일 heartbeat만으로 살아 있음·종결·API 성공을 판정하지 않는다.
- API 호출 직전에 원 승인·소비·live controller/job·fresh 표본·전체/단계 deadline을 다시 확인하고 동기 호출을 최대1회 한다. controller timeout 뒤 살아남은 worker가 새 표본을 얻어 첫 API를 호출하는 R1 반례는 허용하지 않는다. 이 경로와 parent death·UAC late-start·배속 실패·권한 부족·조회 hang·API/결과 I/O 손실은 HOST와 별도 비변경 worker containment 관측으로 검증하며 실제 API 수용과 구분한다.
- deadline/예외 때 terminal을 확인하지 못하면 **IN_FLIGHT_UNKNOWN**으로 남긴다. 시각 변경0·종료 완료·복원 성공으로 쓰지 않고 추가 UAC/시각 변경/native 활성화를 모두 막는다. API에 도달한 뒤 결과가 사라졌으면 변경됐을 가능성도 명시하고 자동 재조정/rollback하지 않는다. terminal이 확인돼도 성공 증거가 없으면 UNKNOWN이며, 새 읽기에서 상대 시각이 맞아 보인다는 이유만으로 그 실패를 성공으로 바꾸지 않는다.
- 108 진입은109가 위 lifecycle을 종결하고 typed 성공 또는 실제 변경 없는 검증 성공을 얻었을 때만 가능하다. 별도의108 native45 승인과 원 gate는 그 다음에 적용한다. 구현 L4 전에는 이 containment가 실제 작동한다고 주장하지 않으며, 실제 실행에서 containment를 검증할 수 없는 호스트에는 OS mutation을 허용하지 않는다.

게인64/16·cap·모델/물성가정·097 후보·원 정지/운동 수용 기준·시간 gate·회수/watchdog 한도를 유지한다. 실물CAN·모터·급전·flash·교정/보정의 물리 작업·설치·구매는0이다. 원34초 BLOCK·정착15/velocity-only EXHAUSTED·PD/포화 UNKNOWN·moving-root 독립교정 NOT_DONE·링 보류는 그대로다.

## 검토할 수용 기준

| ID | 계획/후속 구현에서 강제할 조건 |
|---|---|
| AC1 | 107 B/A1 미실행과 NTP 원인 미확정, 두 가지 시각 조회의 실제 결과를 구분 |
| AC2 | OS 시계 변경·새 native45의 별도 명시 승인, inactive default-deny와 0회 변경 경로 |
| AC3 | fresh 표본·peer/hash·RTT/age/coherence/±5초 cap·UAC 전 소비·단일 단조권한 구간·실제 단일 변경·원시 증거 |
| AC4 | 실제 containment/terminal·late UAC/parent 상실/부분 실패/UNKNOWN 격리·자동 재시도/두 번째 변경/허위 복원·UTC 인증 없음 |
| AC5 | 수정 없는108 원 gate/import→정지→42초·새 예산 경계와 기존 실패/종결 회차 보존 |
| AC6 | 실물/설정/원격 시각 변경0 및 구현 전후 비작성자 검토·실제 runtime와 HOST 구분 |

원자료: `outputs/ntp-network-107/comparison/no-switch/`의 user-reply/state/result/clock-attempt/clock-result/clock-single-result와 각 raw. 승인 전에는 이 계획과 읽기 진단만 존재하며 실제 실행 준비 완료를 주장하지 않는다.
