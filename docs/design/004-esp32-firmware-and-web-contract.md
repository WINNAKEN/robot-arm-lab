> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# ESP32 2축 제어 펌웨어·웹 통신 설계

2026-10-22 · 설계 v0.2 · 메소드 세션 · 상태: 논리 검토 수정본, 구현 전

## 1. 이번 작업과 첫 버전의 범위

문제: 부품 수령 전에도 제어 상태·오류 처리·휴대폰 화면·시험 입력을 준비해야 한다. 사용자 요청은 펌웨어와 화면의 **설계부터 진행**하는 것이다. 이번 결과물은 설계 문서, 실제 장치와 연결하지 않는 화면 시안, 검증 시나리오다. ESP32 실행 코드·SDK 설치·컴파일·업로드·실물 운전은 이번 작업에 포함하지 않는다.

선택 기준은 기존 [배선·CAN 가이드003](003-wiring-and-can-command-guide.md)다. 기구는 고정한 무부하 모터, 제어기는 Waveshare ESP32-S3-RS485-CAN-U, 드라이버는 MKS SERVO42D CAN MT 2대다. 모터·펌웨어 정격 확인 전 명령 지원을 확정하지 않는다.

| 항목 | 설계 결정 | 이유 / 적용 한계 |
|---|---|---|
| 휴대폰 접속 | ESP32 Wi-Fi AP에 직접 연결 | 공유기 없이 시작. 사용자 선택 확정은 휴대폰 웹 방식이며 AP는 이번 설계의 기본안 |
| 웹 자산 | ESP32 내부에 HTML/CSS/JS 저장 | 인터넷·CDN·클라우드 없이 로컬 사용 |
| 통신 | 같은 출처 HTTP + WebSocket | 상태와 명령을 한 세션에서 관리. 인터넷 공개·포트포워딩·OTA는 첫 버전 제외 |
| 조작권 | 명시적으로 획득하는 단일 제어권 | 여러 탭·휴대폰의 명령 충돌 방지. 접속 자체가 운전 허가가 아님 |
| 첫 이동 | D0/D1 각각 100펄스, speed5, acc2 고정 | 가이드003과 일치. 1.8°/16분할 확인 시11.25°. 자유 각도/속도 입력은 후속 |
| 동시성 | 전체 시스템에서 이동 요청 1개만 처리 | 축1·2 각각 시험 후 확장. 첫 버전에 동시 이동·조그·연속 반복·원점복귀 없음 |
| 정지 | 모든 축 소프트웨어 정지 + 별도 물리 차단 | 화면 버튼은 급전 차단장치가 아님. K1 상태를 측정하는 입력은 아직 없음 |
| 확장 | 축 설정 목록은 ID 기반 | 현재 수용 범위는 ID1/2. 6축+그리퍼 수용·기구 보간은 별도 설계 |

### 시험 축 프로필

`active_axes`는 `[1]`, `[2]`, `[1,2]` 중 명시적으로 고른 시험 구성이다. 첫 연결은 한 축 프로필, 두 축을 배선한 뒤2축 프로필로 바꾼다. CHECKING·조회·heartbeat·정지·완료 판정은 이 목록에만 적용한다. 비활성 축은 화면에서 '이번 시험 제외'로 표시하고 정상 응답처럼 꾸미지 않는다. **선택된 축이 응답하지 않으면 오류이며, 자동으로 목록에서 빼지 않는다.**

프로필 변경은 유지보수 경로에서만 한다. 이동 금지·조작권 회수·transport 격리를 완료하고 운영자가 모터 급전 차단을 확인한 뒤, 사전 정의된 구성 하나를 저장하고 ESP32를 재기동한다. 새boot/epoch에서 CHECKING부터 시작한다. 수동 급전 확인은 센서 측정이 아니며, 통신 누락을 숨기려고 자동으로1축 전환하는 동작은 없다. 다른 ID나 임의 축수 입력은 첫 버전에서 제공하지 않는다.

## 2. 구현 구조와 단일 상태 관리

```text
Phone browser -- Wi-Fi AP -- HTTP/WebSocket adapter
                                      |
                               validated intents
                                      |
                              Control supervisor
                           /          |           \
                    lease/state    CAN scheduler   event log
                                      |
                               MKS frame codec
                                      |
                               TWAI transport
                                      |
                              MKS ID1 / MKS ID2
```

네트워크 핸들러는 입력 검증 후 의도를 전달하며 CAN을 직접 송신하지 않는다. 하나의 supervisor가 조작권·축 상태·이동 허가·정지 우선순위를 바꾼다. CAN RX 인터럽트/콜백은 최소 이벤트만 전달하고 웹 송신·파일 저장을 수행하지 않는다.

| 모듈 | 책임 | 하지 않는 일 |
|---|---|---|
| board/config | GPIO15 TX,16 RX,500k,축 ID,시험 프로필 | 실물 미확인 전류값이나 PCB 버전 추정 |
| mks_codec | 명령 인코딩, DLC/checksum/부호/단위 검증 | 정책 결정, 유효하지 않은 프레임을 정상 상태로 변환 |
| can_transport | bounded 송신, RX·오류·bus-off 이벤트 | 이동 재시도, 복구 직후 자동 움직임 |
| supervisor | 상태·단일 제어권·시각·허가·정지·복구 | 네트워크 콜백별 분산 상태 변경 |
| web_adapter | HTTP 자산, WS 입력·상태 스냅샷 | UI의 버튼 disabled만 믿고 명령 허용 |
| event_log | 순번·시각·원인·TX/RX·상태 기록 | 로그 저장 지연으로 제어 루프 정지 |

첫 구현의 메모리 한계 후보: 활성 WS 세션2개(조작1+관찰1), 입력 메시지 최대1024바이트, 일반 의도 큐8개, 축별 미완료 읽기 요청은 명령코드당1개, 이동은 전역1개, 최근 로그 RAM256건. TWAI 송신은 전역담당1개·inflight1개·SW TX큐0으로 제한한다(§8). 큐 포화는 새 이동을 거절한다. STOP은 일반 큐와 별도의 래치로 수신하며 포화에 막히지 않는다. 최종 크기는 빌드·부하 시험으로 확인한다.

## 3. 상태와 복구 규칙

상태는 ESP32의 판단 결과이며 물리 안전 인증이 아니다. 화면은 명령 송신·드라이버 응답·관측 정지 상태를 구분한다.

| 상태 | 들어오는 조건 | 허용 동작 | 나가는 조건 |
|---|---|---|---|
| BOOT / CHECKING | 부팅, 수동 재점검 | 상태·프로필 확인, 정지, 제한된 유지보수 경로 | active_axes 전체의 지원 프로필·통신·비활성 상태가 확인되면 READY |
| READY | 관측상 정지, 운전 허가 없음 | 제어권 획득, 선택축 허가, 읽기 | 허가 절차 통과→ARMED |
| ARMING | 선택축 F3 enable 진행 | 정지, 읽기만 | F3 성공과 새3A=1 확인→ARMED; 실패→STOPPING |
| ARMED | 유효 제어권+선택축 enable 확인 | 선택축 이동1회, 정지, 정지상태에서 토크해제 | 이동 접수→MOVE_PENDING; 해제확인→READY |
| MOVE_PENDING | 이동 의도 수락, 실제 FD 송신/응답 대기 | 정지만, 새 이동 거절 | 시작응답→MOVING; 누락/실패→STOPPING |
| MOVING | FD 시작응답 관측 | 정지·필수 읽기 | 완료응답+새 상태·속도·위치 안정→ARMED; 이상→STOPPING |
| STOPPING | 정지버튼, 조작권 만료, 통신/명령 오류 | §5 정지 절차만 | 정지 확인→STOPPED_RECHECK; 확인 불가→FAULT |
| STOPPED_RECHECK | 정지 응답과 관측상 정지 | 읽기·기록, 유지보수 토크해제, 명시적 재점검 | 비활성 재확인→READY→새 제어권·재허가, ARMED 직접 복귀 금지 |
| FAULT | 정지 미확인, bus-off, 재기동/타임아웃 등 | 오류·기록·물리 차단 안내 | 사용자 재점검 요청+§5 복구 조건, 자동 해제 없음 |

초기 CHECKING에서는 이동/enable을 보내지 않는다. 기존 enable 상태가1이면 조회만으로 READY가 되지 않는다. 아래 유지보수 경로로 비활성을 확인한다. 전원이 켜진 직후 축이 비활성일 것이라고 가정하지 않는다.

유지보수 소유권은 CHECKING 또는 STOPPED_RECHECK에서 명시적으로 획득하며 운전 제어권과 동시에 존재하지 않는다. 허용 op는 읽기·정지·토크해제·프로필 변경뿐이고 arm/move/ticket 발급은 금지한다. F3 disable은 SR모드 확인, 유효 F1=정지·32=0·31 안정 관측, 운영자 무부하/하중없음 확인을 모두 충족할 때만 보낸다. disable ACK와 새3A=0을 모두 받아야 READY로 간다. 관측이 없거나 움직이는 중이면 토크해제를 거절하고 정지/물리 차단 경로로 간다. FAULT에서는 §5의 차단·진단 재개를 거친 뒤 CHECKING으로 들어와야 유지보수 소유권을 얻을 수 있다. 이 경로로 운전 허가 조건을 건너뛰지 않는다.

운전 허가는 축 ID에 결속한다. 축 탭 전환은 관찰 대상을 바꿀 뿐 허가를 옮기지 않는다. 첫 버전에서는 허가된 축이 최대1개다. 다른 축을 허가하려면 기존 축의 정지·토크해제 확인 후 새 축을 명시적으로 허가한다.

부팅 때 새 boot_id를 만들며 조작권·운전 허가·pending 이동·미사용 이동표는 저장하지 않는다. CAN 오류 복구·휴대폰 재접속·버튼 복귀가 이전 동작을 복원하지 않는다. Fault 이후 이미 큐에 있던 HTTP/WS 이벤트도 epoch가 다르면 폐기한다.

정지 관측 후보: STOP/완료의 이후에 취득한 F1=1, 속도32=0, 위치31의 3회 연속 샘플(100ms 간격)이 설정된 작은 오차 내에서 안정. 오차 임계는 현품 검증 전 미정이며 프로필 미확정이면 이동을 허용하지 않는다. 이 관측은 외부 계측에 의한 기계적 정지 검증과 다르다.

## 4. 명령 중복·지연·조작권

시간 판단은 ESP32 단조 증가 시계로 한다. 휴대폰의 날짜·클라이언트 타임스탬프를 신뢰해 유효기간을 늘리지 않는다.

| 후보값 | 용도 | 초과 처리 |
|---|---|---|
| 웹 상태 갱신200ms | 표시와 조작권 확인 | 표시500ms 이상 오래되면 조작 중지 표시 |
| 조작권 keepalive200ms / 만료800ms | 현재 전면 탭의 명시적 조작권 | 서버에서 만료 시 STOPPING. 단순 WS 연결 유지로 갱신하지 않음 |
| 이동표 유효500ms | 오래된 화면의 이동 의도 제한 | 서버 발행 후500ms가 지나면 거절; 새로고침으로 재전송 금지 |
| CAN 축별100ms당1조회 | F1/31 교대, 같은 코드는200ms 간격 | 읽기 응답 후보100ms 미수신 또는 해당 필수관측400ms stale→STOPPING |
| FD/F3 첫 응답 후보200ms | 시작/설정 ACK 확인 | 이동 재전송 없이 STOPPING |
| 이동 전체 제한2000ms 후보 | FD 실제송신 확인부터 완료+정지관측까지 | 정상조회·중복시작ACK로 연장하지 않음. 초과→STOPPING |
| CAN TX 최대대기50ms | 오래 대기한 이동 송신 방지 | 실패 처리, 송신 성공으로 표기하지 않음 |
| MKS heartbeat1000ms | 제어기 명령 단절 시 드라이버 급정지 | 매 부팅 설정·읽기 확인; 실제 동작 시험 전 보장값 아님 |

위 시간은 설계 후보이며 종단간 정지시간의 보장이 아니다. 부하·Wi-Fi·RTOS·드라이버를 실측해 조정하고 프로필 버전에 기록한다.

모든 만료 비교는 `now >= deadline`이면 만료다. supervisor가 이벤트를 처리할 때 현재 단조 시각으로 판단하며, 같은시각에정지/만료와완료/keepalive가경합하면정지·만료를우선한다. 오래된keepalive/seq는만료시각을갱신하지않는다. 이벤트가큐에서기다린동안이미만료됐으면수신당시유효했다는이유로살리지않는다.

서버는 READY/ARMED의 최신 상태에서 선택축에 묶인 **1회 이동표(ticket)**를 발행한다. ticket은 boot_id·제어권·axis_id·state_revision·만료 시각에 결속되고 원시 CAN 내용을 넣지 않는다. 클라이언트는 preset과D0/D1만 선택한다. 서버가 수락 직전과 실제 CAN 송신 직전에 상태·epoch·만료를 다시 확인한다.

메시지는 제어권별 단조 증가 seq와 request_id를 갖는다. 서버는 유효한 새 요청의 seq를 확정하고 ticket을 소비한 뒤 FD를 보낸다. 같은 seq/request_id는 저장된 결과를 돌려주거나 오래된 요청으로 거절하며 재송신하지 않는다. 결과 캐시가 지워져도 마지막 seq보다 작거나 같은 값은 실행하지 않는다. 캐시·메모리 부족이면 이동 거절. 새 부팅/새 조작권에 이전 식별자를 재사용하지 않는다.

이것은 ESP32 내부의 중복 방지다. MKS 응답에는 호스트 request_id가 없으므로 장치까지의 exactly-once를 증명하지 못한다. 상대 이동의 ACK가 없거나 지연·재기동이 의심되면 정지·재점검한다. 동일 FD를 통신 재시도 목적으로 재전송하지 않는다. 오래된 FD 완료 메시지 하나만으로 새 이동을 허용하지 않는다.

### RX 신선도와 장치 프로필의 전제

수신값은 길이/checksum뿐 아니라 pending 읽기(code·axis·TX세대·응답기한)에 맞아야 유효 샘플이 된다. 동일축·동일code 요청은 동시에1개만 존재한다. 요청 전에 드라이버에 남아 있던 RX, 이전epoch, timeout된 거래, 이미 소비된 읽기의 중복, pending이 없는 읽기응답은 raw 로그에만 남기고 last_valid_rx/허가/정지 판정에 사용하지 않는다. timeout 뒤 같은code를 즉시 재요청하지 않고 STOPPING으로 이동한다.

legacy TWAI는 프레임별 선로 수신 시각을 제공하는 설계로 취급하지 않는다. adapter가 드라이버 RX를 꺼낸 즉시 단조 시각을 붙이며 supervisor 처리시각으로 덮어쓰지 않는다. RX backlog/overflow·서비스 지연이 검증된 상한을 넘으면 그 구간 샘플은 invalid다. 소프트웨어 수신시각을 물리 도착시각으로 표시하지 않는다.

운전 가능한 프로필에는 **조회 응답 최대지연 Rmax와 호스트 RX 서비스 지연 상한**을 필수로 둔다. 현재 설계 후보는 Rmax100ms, RX서비스10ms, 추가격리20ms다. 같은code 재조회는 이전 TX 확인시점+Rmax+서비스상한+20ms보다 늦어야 하며 200ms 교대 간격은 이 전제가 검증될 때만 적용한다. 이 상한을 현품에서 확정하지 못하면 표시를 참고값으로 두고 arm/move는 차단한다. 과거응답이 상한을 넘어 늦게 재생될 수 있는 장치에서는 이 방식으로 신선도를 증명할 수 없다.

정지/재기동/timeout 경계는 transport 재초기화로 로컬 큐·옛 알림을 버린 뒤, 마지막 가능한TX로부터 위 지연창이 지나고 새epoch에서 조회한다. 신선도를 입증하지 못한 값은 정지확인·ARMED로 승격하지 않는다. FD 알림은 활성 이동의 시작/완료 순서·송신세대·전체deadline 안에서만 참고하고, 완료 판정에는 새 읽기·위치 변화의 일관성이 추가로 필요하다. CAN에 nonce가 없다는 한계는 남으므로 임의 외부 replay에 대한 보장을 주장하지 않으며, 지연상한·응답순서 전제가 깨지면 FAULT다.

## 5. 정지·단절·bus-off — 조회도 통제한다

사용자 stop, lease 만료, 임계 stale, TX/RX 오류는 동일한 STOPPING 진입 경로를 사용한다. 정지는 active_axes 전체를 대상으로 하고 새 이동과 운전 허가를 즉시 금지한다. K1이나 물리 정지 버튼을 ESP32가 직접 읽거나 제어한다고 가정하지 않는다.

최초 진입 때만 stop_episode_id·고정 진입시각·축별F7시도 여부·절대 감시기한을 만든다. STOPPING/FAULT 중 반복 stop/stale/lease만료는 같은 래치에 병합한다. **epoch 재생성, F7 재전송, 감시기한 연장으로 처리하지 않는다.** 새 stop episode는 기존 episode가 종료되고 명시적 재점검을 통과한 다음 운전 사이클에서만 만들 수 있다. 진행 중 진단이 다시 실패하면 FAULT를 유지하고 자동 F7 루프를 만들지 않는다.

1. supervisor epoch 증가, ticket·pending intent·제어권 폐기. 앱 대기 TX를 폐기하고 §8의 transport 격리 barrier를 통과한다. 이미 선로에 나간 프레임을 취소했다고 주장하지 않는다.
2. 격리 완료·통신 가능이면 active_axes 각각 F7을 **episode당 최대1회** 제한시간 안에 보낸다. STOP 중 반복 F7이나 진단 조회가 heartbeat를 계속 갱신하지 않도록 한다. 격리 미완료면 새 송신하지 않고 FAULT·물리 차단 안내로 간다.
3. F7 송신 이후 해당 축에 정상 조회·주기 keepalive·설정 명령을 보내지 않는다. CAN RX는 계속 수집한다. 수신 응답을 기록하지만 ACK만으로 정지 확정하지 않는다.
4. 마지막 가능한 TX 시점부터 보호1000ms+여유300ms 후보를 정지 감시 구간으로 둔다. episode 전체 절대상한 후보는 최초진입+1600ms이며, 어떤새이벤트도이를연장하지않는다. 마지막TX후1300ms 관측조건을 절대상한 안에 충족하지 못하거나 종료시각 불명확/bus-off이면 정지 미확인/FAULT로 간다. 타이머 만료만으로 정지 성공을 선언하지 않는다.
5. F7 성공 응답을 받았고 통신 오류가 없는 경우, 감시 구간 뒤 제한된 F1/31/32/3A 조회로 정지 상태를 확인한다. 확인되면 STOPPED_RECHECK, 아니면 FAULT다.
6. F7 성공이 미확인·bus-off·heartbeat 지원/설정 미확인인 경우 자동 조회 재개를 하지 않는다. 화면에 **정지 미확인 — 물리 전원 차단 필요**를 표시한다. 운영자 실제 차단·무부하 확인 후 명시적 진단 재개로 들어간다. 이는 입력 센서에 의한 차단 확인이 아니다.
7. 다시 운전하려면 원인 확인→통신/설정 읽기→새 제어권→명시적 허가 순서를 거친다. 정지/오류 전 이동을 이어서 실행하지 않는다.

Wi-Fi만 끊긴 경우도 이 규칙을 적용한다. ESP32가 CAN 조회를 계속하면서 휴대폰 단절을 드라이버 heartbeat에 맡기는 구조를 사용하지 않는다. bus-off 복구는 버스 상태 복구까지만 하고 READY나ARMED로 자동 승격하지 않는다. TWAI 하드웨어 재전송·버스 오류·큐 정리의 정확한 API 의미는 §8의 선택 버전에서 구현 전에 대조한다.

처음100펄스 이동은 1초heartbeat 시험보다 짧다. 별도 이동 조건과 외부 정지 관측을 확정하기 전 heartbeat 정지 성능 시험은 보류한다. 시험 중 대상 축 모든 TX를 끊고 수신/외부 관측만 하며, F7/물리차단을 사용했다면 heartbeat 자체의 정지로 판정하지 않는다.

## 6. 웹 메시지 계약 v0.1

웹은 숫자 CAN 바이트를 직접 입력받지 않는다. JSON의 unknown op/field·범위 밖 숫자·과대 길이·중복 JSON 키는 거절한다. 48bit 엔코더는 프레임에서 정수로 해석하고 웹에는 decimal string으로 보낸다. 화면은 유효한 측정이 없으면 `—`로 표시한다.

| 방향 / op | 필수 의미 | 결과 |
|---|---|---|
| server hello | protocol_version,boot_id,session_id,axis 목록,서버시각 | 모든 새 연결은 관찰 권한으로 시작 |
| client acquire | 현재 boot_id/session_id/request_id,kind=control 또는maintenance | 상태별 허용 kind만,free일 때 새 lease. maintenance는 arm/move 금지 |
| client keepalive | lease_id,seq | 현재 소유자·유효 세션일 때만 만료 갱신 |
| client arm | lease_id,seq,request_id,axis_id | 프로필/정지/통신 확인 후 F3와3A 검사 |
| client move | lease_id,seq,request_id,axis_id,ticket,preset,dir | preset=bench_100pulse,dir=D0/D1만. 서버에서 FD 생성 |
| client stop_all | 현재 boot_id/session_id,request_id | 유효 관찰 세션도 요청 가능. 이동권/ticket은 요구하지 않음 |
| client release_torque | 소유 lease,seq,request_id,axis_id | 정지 확인 상태에서 별도 확인 뒤 F3 disable/3A 검증 |
| client recheck | 현재 session,request_id,사유 | FAULT 조건·수동 확인에 따라 진단만 재개. 자동arm 금지 |
| client select_profile | maintenance lease,seq,request_id,profile_id,수동급전차단확인 | 사전정의1축/2축만,§1 조건 확인→저장·재기동. 누락축 자동제외 금지 |
| server result | request_id,accepted/tx/ack/observed/rejected,reason | accepted는 실제 이동/정지 완료가 아님 |
| server snapshot | server_time,revision,system_state,lease,축별 값·sample_age·valid | 실측·오래된 값·알 수 없음 구분 |

공통 envelope는 `v`, `boot_id`, `session_id`, `request_id`, `op`다. 조작 명령은 위 표의 lease/seq 등을 추가한다. 잘못된 boot/session은 오류를 반환하고 하드웨어에 전달하지 않는다. stop은 조작권이 없어도 현재의 정상 세션에서 허용하되 타 출처의 요청까지 허용하는 뜻은 아니다.

예시(설계용, 실제 연결 주소나 실행 명령 아님):

```json
{"v":1,"boot_id":"boot-demo","session_id":"tab-demo","request_id":"r17","op":"move","lease_id":"lease-demo","seq":17,"axis_id":1,"ticket":"ticket-demo","preset":"bench_100pulse","dir":"D0"}
```

snapshot 축 항목: `axis_id`, `state`, `position_counts`(문자열/없으면null), `position_deg`(프로필확정시에만), `speed_rpm`, `enabled`, `samples`(각 항목 last_rx/age/valid), `last_command`, `fault_reason`. Wi-Fi 연결 표시는 축 CAN 응답 상태와 따로 보낸다. degree는 모터축 기준이며 로봇 관절 좌표가 아니다.

## 7. 접속·저장·운영 제한

AP 이름은 보드별 식별자를 붙이고 충분히 긴 개별 암호를 설정한다. 출고 예제의 공용 기본 암호를 그대로 배포하지 않는다. 휴대폰은 인터넷 없는 Wi-Fi라는 안내가 나와도 해당AP에 연결을 유지해야 한다. 첫 버전은 자동 captive portal 대신 설명서에 로컬 접속 주소를 제공한다(예정192.168.4.1, 실제 AP설정으로 검증).

HTTP/WS는 AP 내부에서만 열며 Origin/Host와 세션을 검증한다. HTTP는 별도 TLS를 제공하는 설계가 아니므로 인터넷·공유망 공개를 범위에 넣지 않는다. 외부 사이트에서 들어온 브라우저 요청과 오래된 세션으로 조작하지 못하게 하되 이것을 보안 감사 통과로 표현하지 않는다.

NVS에는 장치 식별/접속 설정/검증된 프로필 버전만 저장한다. boot_id·lease·arm·이동·ticket·최근 seq는 RAM에 두고 재부팅하면 폐기한다. CAN raw 로그에는 Wi-Fi 암호나 제어권 토큰을 기록하지 않는다. 로그가 꽉 차면 오래된 항목을 버린 수를 표시하며 제어를 막지 않는다. 설정 갱신은 정지·미허가 상태에서만 적용하고 임의 전류·노드ID·microstep 수정 화면은 첫 버전에서 제외한다.

## 8. 개발 환경 선정과 구현 전 확인

**ESP-IDF v5.5.6 / target esp32s3 / legacy 비핸들 driver/twai.h / SoftAP / esp_http_server WebSocket**을 빌드 후보로 고정한다. 공식 릴리스·같은 태그 헤더/소스·제조사 데모ZIP를 대조한 선택이다. SDK 설치·보드 빌드·플래시 성공을 주장하지 않는다.

제조사 예제는 Arduino-ESP32 3.0.x, legacy TWAI, 기본250k이며 GPIO15/16을 사용한다. MKS 운전규칙을 제공하는 예제가 아니므로 통째로 복사하지 않는다. 이번은 네이티브IDF에서500k와 자체 상태계약을 구현하는 계획이다. Espressif가 신형 TWAI를 새 프로젝트에 권장하는 점은 인정하지만, 이번 후보는 예제와API가 맞고 복구 뒤STOPPED 상태를 명시적으로 관리할 수 있는 legacy를 선택했다. 신형 esp_twai 및 legacy _v2와 혼용하지 않는다.

### 전송 소유권과 격리 barrier

- NORMAL 모드, 표준 DATA 프레임, 전역 송신자/알림소비자1개, inflight1개, `tx_queue_len=0`, 모든 프레임의 `.ss=1`(single-shot), 비차단 `twai_transmit(...,0)`을 후보로 고정한다. 프레임의 다른 flags도 완전 초기화한다.
- `twai_transmit`의 ESP_OK는 수락/시작일 뿐 CAN TX성공도 MKS수신도 아니다. TX알림에는ID가 없어 전역직렬화와현재세대가 모두 맞을 때만 연관한다. 알림이 혼합되거나 경계가 불명확하면 UNKNOWN이다.
- 큐0에서는 `twai_clear_transmit_queue()`를 호출하지 않는다. 이 함수는 큐0에 지원되지 않고, 큐가 있어도 HW inflight를 취소하지 않는다. 앱epoch 변경만으로하위층취소완료를선언하지않는다.
- STOP/TXtimeout 때 일반송신을 닫은 뒤 RUNNING controller는 `twai_stop` 성공·STOPPED 확인→driver uninstall 성공까지 진행한다. 모든legacy 호출은 같은송신소유자가 직렬화하고 RX/alert대기는유한/비차단으로중단가능하게한다. 이 경계에서기존driver/pending/알림을폐기한다. uninstall 성공과옛소유자접근차단이 **로컬 잔류TX격리 완료** 조건이다. 이미전송된명령의취소조건은아니다.
- 재설치한 새driver는STOPPED로시작한다. 옛FD나일반조회는복원하지않는다. episode기한내정상경로에서만새세대로start해F7전용송신을허용한다. stop은진행중CAN프레임을중단해버스오류를만들수있으므로정상모터정지명령대신무조건호출하는기능으로설명하지않는다.
- BUS_OFF는현재TX불능상태로격리하고 정상running처럼stop을호출하지않는다. `twai_initiate_recovery`가TX큐를폐기하고STOPPED로복귀하는지확인한뒤uninstall/reinstall을거친다. 복구만으로start·F7·조회·이동을자동재개하지않고FAULT의수동진단경로를따른다.
- stop/uninstall/복구결과가불명확하면격리완료로표시하지않고새driver/송신도시작하지않는다. FAULT와물리차단필요를표시한다. API실패나하드웨어고장상태에서기존명령이절대로나가지않는다고보증하지않는다. 실물H08에서잔류프레임을포함한격리효과를검증해야한다.

구체 근거와공식URL은 `_research/esp32-firmware-sdk-20261022.md` §1~5. [v5.5.6 릴리스](https://github.com/espressif/esp-idf/releases/tag/v5.5.6), [legacy TWAI 소스](https://github.com/espressif/esp-idf/blob/v5.5.6/components/driver/twai/twai.c), [Waveshare 자료](https://docs.waveshare.net/ESP32-S3-RS485-CAN/Resources-And-Documents/).

현품·구현 전 확인: 실제 PCB와 핀/USB 방식, MKS HW/FW·heartbeat/읽기/응답 지원, 실제 enable/부팅 상태, 모터1.8°·전류, heartbeat 저장/교정 중 동작, K1·퓨즈·고정·정지거리, TX 큐 취소/재전송 정책, AP 재연결·휴대폰 백그라운드 동작. 미확정 상태는 런타임 프로필 승인 조건을 충족하지 못한 것으로 처리한다.

## 9. 부품 없이 준비할 순서와 완료 기준

| 순서 | 결과물 | 이번 상태 / 다음 조건 |
|---|---|---|
| D1 | 이 상태·통신 계약 | 초안 작성, 독립 논리 검토 후 수정 |
| D2 | 휴대폰 화면 사양과 비연결 시안 | 가상 상태를 고르는 디자인 프리뷰. 실제 제어 코드 아님 |
| D3 | 검증 시나리오 | 정상/중복/지연/단절/bus-off/재기동 기대 결과를 고정 |
| I1 후속 | codec와 상태 코어 + host tests | 설계 검토 및 구현 지시 이후. 먼저 실제CAN 없는 입력/출력으로 검증 |
| I2 후속 | 선택 SDK의 board adapter·내장 웹 | 하드웨어 없이 빌드 가능 여부 확인, fake/real 분리 |
| H1 도착후 | 실물 버전/전기 검사와 읽기부터 | 가이드003의 보호·고정 조건 통과, 실제 플래시/통신은 별도 수행 |

시안 버튼이나 시나리오 문서가 존재하는 것은 펌웨어 동작 검증이 아니다. 다음 단계로 넘길 수용 항목은 [시험 시나리오006](006-offline-and-hardware-acceptance-cases.md)에 기록한다. 동기운전·6축보간·그리퍼·자동홈·OTA·원격접속은 이번 범위의 완료 조건이 아니다.
