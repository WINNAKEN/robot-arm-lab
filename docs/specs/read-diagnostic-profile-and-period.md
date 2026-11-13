# 읽기 진단 프로필·실행 주기 — 088 준비본

2026-10-30. 모듈 없는 준비/시험용이다. 실제 CAN·급전·보정·모터 운전·플래시는 NOT_RUN이다. 087의 원 로그/100Hz 비활성 빌드를 바꾸지 않고 새088 결과로 구분한다.

## 프로필에 적는 값

기록 틀은 `read-diagnostic-profile.template.json`이다. **기록용이며 펌웨어가 로드하거나 승인값으로 사용하지 않는다.** 예상값을 실제 관측칸에 자동 복사하지 않는다.

| 구분 | 예상 제약 | 현재 실제 확인 |
|---|---|---|
| 보드 | Waveshare ESP32-S3-RS485-CAN-U | 주문 화면 확인, 현품 리비전 미확인 |
| 드라이브 통신 | Makerbase CAN | 부착 드라이브 HW/FW·CAN 단자 미확인 |
| 선택 ID | 1 또는2, 세션마다 하나 | 실제 ID 미확인 |
| bitrate | 500000 bit/s 후보 | 실제 설정 미확인 |
| CAN TX/RX | GPIO15/16 후보, 기존 TWAI 코드와 일치 | 현품/배선 대조 전 |
| HW/FW 기록 | 비공백·제어문자 없음·64byte 이하 | 미확인 |
| 배선·종단 / 전원시무운전 | 실제 확인 필요 | Unknown |

모터 몸체 `_485` 라벨을 실제 CAN/RS485 판정으로 사용하지 않는다. HW/FW 문자열이 형식에 맞는다고 실제 관측 사실을 인증한 것도 아니다. 예상/관측 비교는 오프라인 프로필 검토를 돕는 기능이다.

`execution.hpp::prepare_profile()`은 Pending(누락), Mismatch(불일치), ReadyForReview(형식/값 일치)를 구분하고 각각missing/mismatch bit를 제공한다. 일부 값이 틀리고 나머지가 비어 있으면 불일치를 숨기지 않는다. **모든 값이 맞아도 `transport.hardware_approved=false`**다. 반환값에는 원 string_view를 보관하지 않는다.

| bit | 확인 항목 |
|---|---|
| 0 | 선택 ID |
| 1 | 실제 보드 |
| 2 | 실제 프로토콜 |
| 3 / 4 | HW / FW 기록 |
| 5 / 6 / 7 | 실제 ID / bitrate / 핀 |
| 8 / 9 | 배선·종단 / 전원시자동동작배제 |

기본값은 Pending·missing1023·mismatch0이다. 물리 승인 미확인은 이10비트와 별도로항상false다. 기본 main은 이상태를DISABLED로표시하고CAN·RTOS대기·제어task를시작하지않는다. 메뉴/웹/JSON/시리얼 입력으로 승인하는 경로는 없다.

## ESP32 주기 후보

독립 진단 프로젝트의 `sdkconfig.defaults`는 **FreeRTOS1000Hz**를 요청한다. main은 실제CONFIG_FREERTOS_HZ1000과pdMS_TO_TICKS(1)>0를compile-time검사한다. 100Hz 또는0tick으로 빌드하려 하면 거절한다. 기존 일반 운전 프로젝트와087의100Hz 산출물을 바꾸지 않는다.

Cadence의 첫due는begin(now)의now다. 같은시각 재호출은Early이며추가Runner.poll이없다. 모든관측(Early포함)에서역행을검사한다. 직전서비스부터9ms는허용하지만10ms이상이면Schedule오류로닫는다. 늦은호출은최대1회만서비스하고next_due=현재+1ms로옮겨밀린슬롯만큼연속실행하지않는다. uint64끝에서는덧셈overflow를거절한다.

실제main의대기는xTaskDelayUntil의1tick절대주기다. 이미늦어대기하지못한pdFALSE는catch-up루프대신Schedule오류로종료한다. Schedule abort는CanPort.close만수행하고F7/토크명령은보내지않는다. Idle/terminal후sharedhelper와clockgetter는포트/시계I/O가없다. 기존Runner의송신허용·응답·10ms서비스·250/500/150/4000ms기준은그대로다.

**1000Hz설정/컴파일은물리1ms실행보장이아니다.** 실제ESP32의RTOS지터·ISR·CAN선로응답·물리정지/무토크성능은아직검증하지않았다. Cadence의소프트웨어완료나ReadyForReview를실물수용으로표시하지않는다.

## 장치 없는 재현과 남은 경계

```powershell
& ./src/firmware/tests/diagnostic/run.ps1 -Mutations -Tag NEW_UNIQUE_TAG
```

출력은 `.dev/can-read-profile-evidence/build/NEW_UNIQUE_TAG/`에남긴다. 기존코어읽기회귀에프로필누락/불일치/모두일치해도미승인·Cadence/Runner통합·9/10ms·역행/overflow·대기실패·종료무I/O를더했다. 기존3변형과프로필승인오염/주기경계완화2변형을검출한다. 별도entry-stub는실제main의기본무I/O/설정승인무시와100Hz/0tick static_assert거절을대조한다.

실제타깃빌드·독립검토·원자료상태는`.dev/can-read-profile-evidence/`와088 결과문서를따른다. 모듈수령후에는[기존수령체크리스트](can-arrival-readonly-checklist.md)의식별·무전원확인부터진행한다. 실제HW/FW/ID/bitrate·단자·전원시동작확인과별도하드웨어시험조건이필요하며이번변경은활성화/플래시허가가아니다.
