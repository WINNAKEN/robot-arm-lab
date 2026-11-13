# CAN 읽기 전용 진단 실행부 — 087 준비본

2026-10-30. 사용자 요청에 따라 구현한 장치 없는 준비본이다. **실물 CAN·모터 급전·보정·운전·플래시 미실행**, 실제 ESP-IDF target 빌드도 NOT_RUN이다. HOST와 SDK 선언 stub 결과를 실물 수용으로 읽지 않는다.

## 수령품 식별 상태

주문 화면의 보드는 Waveshare ESP32-S3-RS485-CAN-U다. 모터/드라이브는 도착했다는 사용자 보고와 사진을 보존했다. 모터 몸체 라벨 `MAKERBASE SERVO42D_485`는 관측했지만 그 라벨만으로 부착 드라이브가 CAN인지 RS485인지 확정할 수 없다. 드라이브 PCB/HW/FW/단자 표기·매뉴얼 버전은 여전히 미확인이다. 확인 전 물리 CAN 연결/급전으로 추측 시험하지 않는다. 원본 사진은 `.dev/can-readonly-evidence/intake/`와 SHA manifest에 있다.

## 구성

| 경로 | 역할 |
|---|---|
| `src/firmware/components/robot_diagnostic/` | CanPort를 소유하는 읽기 Runner·TX 프레임 허용 검사 |
| `src/firmware/diagnostic/` | 기존 app과 분리한 ESP32-S3용 비활성 진입점 |
| `src/firmware/tests/diagnostic/` | 실제 Runner+codec / FakeCanPort HOST·변형 시험 |
| `.dev/can-readonly-evidence/test-entry.py` | 실제 main.cpp를 SDK 선언 stub과 호스트 링크해 기본 무I/O 확인 |

기존 `src/firmware/main/`·TWAI·Boot/Run·웹은 바꾸지 않았다. 독립 앱은 `kPhysicalReadApproved=false`와 static_assert로 고정하며 menuconfig·시리얼 입력·웹에서 승인할 수 없다. 기본 실행은 DISABLED 기록만 남긴다. 실제 호출 경로에도 기본 false Profile을 둬 임의 설정으로 포트를 시작할 수 없다.

## 실행부 계약

기본 생성자/미승인 Profile은 CAN 호출0이다. 선택ID1/2·보드/프로토콜/bitrate/전원시무운전조건·하드웨어 검토가 모두 확인돼야 begin을 수용한다. HOST true Profile은 합성자료이며 실물 승인 기록이 아니다. begin은 한 객체당1회이며 거절·오류·완료 뒤 다시 열지 않는다.

한 ID에 **3A(enable) → F1(운전상태) → 31(원시위치) → 32(속도)**를 각1회 조회한다. 두 축은 별도 세션/확인 절차다. 실제 WireFrame을 submit 직전에 다시 검사한다: 선택ID와 일치·표준DATA·RTR/EXT=false·DLC2·opcode4종·checksum·미사용 바이트0. 공개 raw 송신 함수는 없다. F3/F7·설정·이동·홈·보정·heartbeat 쓰기와 자동 retry/restart/busoff복구를 보내지 않는다. checksum이 F3인 정상 F1 요청은 허용한다.

송신 접수와 실제 TX_SUCCESS를 구분한다. RX는 TX_COMPLETE 이후 단일 명령에 결속해 처리하며 ID·opcode·DLC·checksum·flags·dequeue 시각을 확인한다. 추가/중복/미요청 RX는 오류다. `dequeued_at=0`은 미확인 예약값으로 거절하고 submit 이전/현재 이후 시각도 거절한다. 이는 하드웨어 선로 도착 시각을 증명하지 않는다.

후보 시간은 시작/격리100ms미만·poll 간격 및 poll 처리10ms미만·TX완료250ms·응답500ms(둘 다 submit 직전 기준)·유효응답 뒤 다음 조회까지150ms·전체4000ms다. 경계에서 성공보다 만료가 우선한다. 전부 HOST 검증용 소프트웨어 조건이며 실제 지연·모터 정지 성능 기준이나 기존 Stop 규칙의 변경이 아니다.

enable1/F1조회실패0·상태2~6이면 중단하고 값을 원문으로 남긴다. 위치는 signed48 원시값, 속도는 signed16 rpm이며 영점·관절각·방향으로 변환하지 않는다. 잘못된 프레임·알림·bus/counter·시간·포트 오류는 종료한다. 마지막 값 뒤에도 잔여RX/health와 close의 quiesced/healthy·최종시간을 확인한다. Complete는 읽기 요청 묶음의 소프트웨어 완료이며 물리 정지·무토크 인증이 아니다.

## 원 로그와 출력

Runner는 Begin/Submit(시도)/Accepted/TX_COMPLETE/RX_RAW/Value/Failure/Close 사건을 고정128개까지 저장한다. 각 사건에는 관측 단조ms·원 프레임·RX dequeue시각·파싱값·오류가 있다. 용량은 HOST에서 더 작게 제한할 수 있고, 소진하면 fault로 닫으며 조용한 덮어쓰기는 없다. 값과 values_seen을 별도로 제공해 미관측0을 실측0으로 바꾸지 않는다. 마지막 관측 alerts/bus/counter와 close 결과도 보존한다.

준비된 앱 경로는 활성 poll 중 콘솔을 출력하지 않는다. 종료/close 뒤 요약과 사건을 NDJSON으로 내보내도록 구성했다. 기본 비활성 진입점에서는 CAN_STARTED=false인 DISABLED 한 줄만 나온다. 그 줄은 실제 연결시험 결과가 아니다.

## 장치 없는 시험 재현

기존 설치된 Zig만 사용한다. 새 설치·네트워크·장치 접근은 없다. 새 Tag는 원 로그 덮어쓰기를 막는다. Windows 샌드박스가 컴파일 캐시 rename을 거절할 수 있으며 이를 코드 실패와 별도로 기록한다.

```powershell
& ./src/firmware/tests/diagnostic/run.ps1 -Mutations -Tag NEW_UNIQUE_TAG
```

현재 HOST는 정상ID1/2·프로필 기본거절·모든256opcode허용검사·TX접수/완료·부호값·시간경계·RX/중복/타임스탬프·장치상태·bus/counter·close·저널소진·terminal이후무I/O를 검증한다. SDK entry 시험은 `.dev/can-readonly-evidence/entry-stub/result.json`을 참조한다. 실제 ESP-IDF 라이브러리/핀/ISR/USB/WiFi/CAN 선로 검증은 포함하지 않는다.

## 모듈 도착 후

기존 [수령 체크리스트](can-arrival-readonly-checklist.md)의 식별·무전원·보드 단독 확인부터 진행한다. 실제 드라이브의 CAN 옵션과 전원 시 자동 동작을 확인하기 전에는 포트를 시작하지 않는다. 현재 준비본은 장치 비활성이므로 수령만으로 바로 실제 요청이 나가지 않는다. 다음 별도 단위에서 실물 자료에 맞는 프로필, 실제 SDK target 빌드·포트 호환성·읽기 전용 하드웨어 시험 조건을 검토해야 한다. 플래시·보정·토크 변경·모터 운전은 이번 작업 범위에 포함되지 않는다.
