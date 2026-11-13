> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 107 — A0 완료 / 핫스폿 전환 불가·경로 인과 미확정

2026-11-02. 사용자 응답 「수동 전환·복구 가능, 비교 진행」에 따라 [107 절차](107-alternate-network-ntp-comparison.md)의 기존 Wi-Fi A0를 측정했다. 최신 응답은 「전환이 안 됨 / 원래 Wi-Fi 유지」다. **A0만 완료 / B 전환 불가**이며 전체 A0/B/A1 비교는 수행하지 못했다. 아래 대기 기록은 그 응답 전의 이력이다.

- [관측] 기존 Wi-Fi `EXAMPLE_WIFI`, IP `192.0.2.10`, gateway `192.0.2.10`, Public 프로필, NIC GUID `00000000-0000-0000-0000-000000000000`였다. 전체 바인딩20개는 106 기록과 같고 `nt_rtf64=true`다. A0 전후 NIC·경로·프로필·바인딩·NTP provider 값이 동일했다.
- [관측] 원103의 변경 없는 `ntp_sample` 함수로 고정 목적지 `52.231.114.183:123`에 2초 timeout의 요청을 정확히3회 전송했다. **3회 모두 timeout, 유효 응답0**이다. 원 요청 hex·로컬 source port·송신 호출/반환과 수신 대기/timeout UTC를 보존했다. 응답 packet은 관측되지 않았다.
- [관측] 시작 시 로컬·isaacpc의 Kit/Isaac/관련 Python 프로세스는0개였다. 원격 NTP 대조는 SSH 접속 후 `Get-Command py.exe`에서 실패해 Python/NTP 클라이언트 실행 전 종료됐다. 해당 원격 NTP 요청0·유효 서버 대조 미관측이며 원 stdout/stderr를 보존했다. 설치·자동 재시도는 하지 않았다.
- [미지] B·A1은 아직 측정하지 않았다. A0 timeout만으로 호스트·공유기·ISP·서버 중 원인을 정할 수 없다. 원격 대조도 완료되지 않아 서버 간헐성 혼재 요인이 남는다.
- 사용자에게 A0 완료 후 핫스폿 전환과 연결 완료 응답을 요청했다. 응답 전에는 B 연결을 완료한 것으로 취급하지 않는다. 다음은 같은 NIC·바인딩과 변경된 경로를 확인한 뒤 B3표본, 이후 사용자 원복 후 A1 3표본이다. 전환 대기 중 NTP 요청을 반복하지 않는다.

기록은 [진행 상태](../../outputs/ntp-network-107/comparison/state.json), [A0 결과](../../outputs/ntp-network-107/comparison/A0/summary.json), [A0 원표본](../../outputs/ntp-network-107/comparison/A0/samples.json), [원격 대조 미완료](../../outputs/ntp-network-107/comparison/remote-control/result.json)에 있다. 원103 함수 소스/해시와 실제 실행 명령은 `comparison/ntp-client-command.json`, A0 보존 해시는 `comparison/A0-preservation.json`에 저장했다. 이것은 기존 진단 함수의 읽기 전용 실행 기록이며 새 생산소스나 액추에이터 변경이 아니다.

에이전트의 네트워크·프로필·바인딩·시간서비스 설정 변경/resync·SDK/SimulationApp·실물CAN·급전·flash·모터·설치0이다. 읽기 전용 SSH 프로세스조회와 실패한 NTP 대조를 실제 수행한 사실은 위에 구분한다. 108 로컬 HOST587·L4 R2 PASS9/0는 유지하되 실제 정지/42초·시간정렬·새 원격45분은 미실행이다. 원099/103 실패·종결회차·임계·게인/cap/모델·원 수용기준은 그대로다.


## 핫스폿 전환 불가 후 실제 확인

사용자 답변을 받은 뒤 원래 Wi-Fi/NIC/경로/프로필/전체20 binding·NTP provider가 A0 종료 시점과 같은 것을 읽기만 했다. [원래 연결 확인](../../outputs/ntp-network-107/comparison/no-switch/result.json)은 성공했다. B와 A1 표본은 각각0이며 같은 A 경로를 B/A1로 이름만 바꾸어 재시험하지 않았다. 이번 응답 후 새 NTP 요청·네트워크/시계 설정 변경·UAC·SDK/native/CAN은0이다.

시뮬 진입의 상대 시각 조건을 구분하기 위한 별도 SSH OS 진단도 기록했다. 최초 대화형 조회는 READY 후 시각 응답이 없어 UNKNOWN이며 raw를 보존했다. 이후 별도 비대화형 단일 조회는 SSH 시작 지연까지 포함한 remote−local 구간 `[1.6648609638, 2.7080295086]`초를 얻었다. 전체 구간이 +1초 밖이며 현재 상대 정렬도 수용되지 않았다. [관측 원문](../../outputs/ntp-network-107/comparison/no-switch/clock-single-result.json)의 RTT는1.031초, 로컬 wall/monotonic 차이는0.011169초이고 원격 W32Time은 Stopped/Manual이다. 이 결과는108 admission certificate나 표준 UTC 동기화 인증이 아니다. 옛 +3.42초를 현재값으로 재사용하지 않는다.

107 경로 비교는 필요한 외부 연결 전환을 수행하지 못한 부분 결과로 남긴다. Realtek·WFP·호스트·공유기·ISP의 단독 원인은 미확정이다. [109 로컬 상대 시각 정렬 계획](109-relative-clock-alignment.md)은 NTP 원인 진단과 별도로 시뮬 재개 환경을 수리할 후보이며, 로컬 시각 변경과 새108 native45는 아직 미승인·미실행이다. 108 소스·게인/cap·물리/시간 gate는 바꾸지 않는다.


미완료 대화형 시각 조회의 정리도 구분해 기록했다. 로컬 SSH 종료만으로 원격 종결을 추정하지 않고 정확한 원 명령을 조회했더니 읽기 전용 PowerShell 두 개가 남아 있었다. 첫 정리 명령은 JSON 배열을 PID 하나로 취급한 오류로 핸들 획득/종료 API 전에 실패했고 원자료를 남겼다. 배열 해석을 고친 동일 범위 정리에서는 명령·PID·커널 생성시각을 핸들로 다시 고정한 뒤 자식9456의 terminal을 확인했고 wrapper37892는 이미 종료돼 추가 조작하지 않았다. [정리 결과](../../outputs/ntp-network-107/comparison/no-switch/clock-cleanup-action2.json)는 이 두 자기 진단 프로세스만의 증거이며 모든 원격 프로세스가 없다는 주장이 아니다. 시각 API/SDK/native/CAN 호출은 없었다.
