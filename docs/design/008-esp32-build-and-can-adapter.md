> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# ESP32 빌드와 CAN 연결부 — ST2

2026-10-23 · L1 계획 · 사용자 요청: ESP32 빌드와 CAN 통신 연결부를 부품 도착 전에 검증.

## 범위와 검토

007의 정지 코어를 실제 ESP-IDF v5.5.6 / ESP32-S3에 빌드하고, 단일 소유자 TWAI 연결부와 장치 없는 통합시험을 추가한다. 현재 후속 지시는 이 구현과 필요한 프로젝트 전용 도구 설치를 허용한다. 플래시·전원인가·실물 송신·구매·원격 게시를 실행하지 않는다. 기본 app_main은 연결부를 포함하지만 driver를 시작하지 않는다. 전체 supervisor, 초기 설정/readback, 이동/enable, 휴대폰 웹 서버는 후속 단위다.

새 ST2 검토 예산은 L2 최대 2회, L4 최대 2회(초기+수정 재확인). 작성자/구현자와 독립된 검토자가 판단한다. 이번에도 정식 외부 bridge 읽기가 기존 절대경로 Python lint hook에 거절되었다. 중앙 도구 수정·우회 없이 동일 계열 독립 검토로 대체하고 외부 검토 NOT_RUN을 유지한다. 예산 소진은 통과 근거가 아니다. 004/005/006과 PDF, ST1 검토는 동결한다.

근거: `_research/twai-adapter-evidence-20261023.md`. SDK tag v5.5.6은 commit `880a203ae603d08a94d06aa01e0d6761958e5e9e`다. legacy TWAI의 **v2 handle API**만 사용한다. 이전 연구의 v1 선택보다 명시적 driver 수명을 우선하며 신형 node API와 혼용하지 않는다.

## 소유권과 인터페이스

- `robot_can/CanPort`: 단조 ms 시계, 새 driver 설치/시작, 명시적 close, zero-wait alert/status/RX/TX. wire frame ID는 uint32로 보존한다. driver의 dequeue 직후 시각을 함께 반환한다.
- `robot_can/StopLink`: 단일 task만 호출. StopCoordinator와 유일한 inflight token, 링크 fault, 고정 크기 raw event ring을 소유한다. 소유 객체를 복사하지 않는다. 모든 함수는 동기 호출이며 외부 TX/RX 사용자와 공유하지 않는다.
- `robot_twai/IdfTwaiPort`: private driver handle, pins TX15/RX16, 500k 후보, tx_queue_len=0, rx_queue_len=16, 표준 데이터 single-shot ss=1, self=0, transmit wait=0. 재전송·자동 bus-off 복구·지연 TX 큐 없음. status counter를 비교하여 alert 유실에 의한 오승격을 막는다.
- 코어는 `TransportFailure` fault 및 `on_transport_error(now)`만 확장한다. 기존 시간·진단 계약은 보존한다. 링크의 close 실패는 코어가 terminal이어도 링크 Fault로 표시한다.

## 수명과 시간

미승인 StopProfile은 driver 초기화 전에 거절한다. 유효한 host fixture 프로필에만 begin_stop을 허용한다. 새 episode의 Isolate action은 기존 driver가 있으면 상태 확인, RUNNING stop, STOPPED/tx=0 확인, uninstall, 새 install, STOPPED/빈 큐 확인, start, RUNNING/tx=0 확인 순이다. 기존 BUS_OFF/RECOVERING은 새 송신으로 복구하지 않는다. 새 install의 새 큐/알림/카운터 수명을 사용하므로 stop/start로 남은 알림을 승계하지 않는다. queue0에서 미지원인 clear_transmit_queue는 호출하지 않는다. 하나라도 실패하면 격리 실패, close 시도 후 fault. 격리 호출 전후 시각을 검사하여 100ms 미만 조건을 지킨다. API 실행시간의 상한은 실물 미검증이다.

StopLink 시작 이후 poll 간격과 한 poll의 처리시간은 각각 **10ms 미만**이어야 한다. 역행/경계 이상이면 수신을 새 관측으로 사용하지 않고 fault. 수신에는 hardware timestamp가 없어 dequeue 시각만으로 큐 체류시간을 입증할 수 없다. bounded batch 16개, 종료 시 잔여 RX가 있으면 fault. 이 검사는 서비스 가정 위반을 탐지하지만 ISR·task scheduling의 물리 상한은 입증하지 않는다. 실물 response_bounds_approved는 계속 false다.

송신 action은 코어 take_action(now)과 실제 submit 직전 양쪽에서 dispatch_before를 검사한다. submit은 반환 직후도 시각을 확인하여 늦은 접수를 성공으로 보지 않는다. 이는 preemption이 있는 CPU에서 늦은 frame이 선로에 절대 나가지 않았다는 보장이 아니다. 실패/만료 즉시 driver close로 후속 송신을 차단하며 기존 모터 동작 취소나 물리 정지를 주장하지 않는다.

## 한 poll의 우선순위

1. 시계/서비스 간격과 코어 만료 검사. 기한 경계 성공보다 만료가 우선.
2. alerts → status 검사. BUS_OFF/RECOVERING, RX 손실, ERR_PASS/PERIPH_RESET/TX_RETRIED 및 BUS_ERROR/ABOVE_ERR_WARN/ARB_LOST를 이번 단위에서 보수적으로 fault 처리한다. missed/overrun/failed/bus_error/arb_lost counter는 새 수명 0과 비교하며 변화는 fault(랩도 변화)다.
3. fault가 없을 때만 TX 완료 처리. TX_SUCCESS|TX_IDLE은 정상 후보, TX_IDLE 또는 빈 alert는 완료가 아니다. 성공+실패 모순, inflight 없는 terminal, tx_pending!=0인 완료는 fault. ESP_OK 송신 접수는 완료가 아니다.
4. RX를 최대16개 dequeue하고 각 frame 전달 전 alerts/status/시각을 다시 검사한다. 마지막 RX로 코어가 terminal이 되어도 batch 후 health/backlog 검사를 거쳐야 링크 성공으로 승격한다. 잘못된 ID/flags/DLC/checksum은 코어가 무시하고 결국 timeout하며 raw 기록에는 남긴다.
5. 코어 tick 및 action 처리. 제출 직전 다시 health/time 확인. 완료와 RX는 동일 poll에 허용하되 completion을 먼저 전달하여 정상 F7 ACK를 연결한다. quiet 중 어떤 TX도 생성하지 않는다.

링크 terminal 진입 시 close는 한 번 수행하고 `CloseResult {quiesced, healthy}`를 보존한다. close는 RUNNING이면 stop 후 STOPPED/tx=0 확인, **uninstall 전에 STOPPED 상태의 alerts/status/RX 잔여/모든 오류 counter를 다시 확인**한다. TX terminal bit 또는 fatal bit, 잔여 RX/TX, 오류 counter 하나라도 있으면 healthy=false다. TX_IDLE만은 허용한다. BUS_OFF는 uninstall하여 quiesced=true일 수 있어도 healthy=false다. RECOVERING/상태 오류/API 실패 역시 healthy=false. 실패 handle은 재사용/자동 재설치하지 않는다. quiesced는 handle 해제가 성공했음을, healthy는 관측 가능한 최종 SW 증거가 정상이었음을 각각 나타낸다. core가 terminal이어도 Link가 이 두 값을 별도 검사한다.

코어 StoppedRecheck이고 batch 종료 health, close.quiesced, close.healthy가 모두 참이어야 링크 StoppedRecheck다. close 반환 뒤에도 시계 역행·현재 poll 총 처리 10ms 이상·전체3600ms/진단1700ms 기한 도달을 링크가 직접 검사하여 성공 승격을 거절한다. close 실패로 코어 terminal state를 다시 쓰지 않고 링크의 Fault와 close 결과를 함께 보여준다. 재시작은 지원하지 않는다. 반복 stop은 최초 기한을 바꾸지 않는다. ring은 최근 이벤트만 보존하고 overwrite 수를 표시하며 driver RX 손실과 구분한다.

L2 R1의 FINALIZATION_EVIDENCE_LOSS 반례(마지막 health 이후 BUS_OFF 또는 RX 손실, close가 이를 폐기한 뒤 성공 표시)를 위 절차로 수정한다. 이는 **관측 가능한 SW 증거의 보존**이다. public stop API는 HAL pending interrupt를 clear하고 uninstall 때 ISR을 해제하므로, ISR에 아직 보고되지 않은 선로 사건까지 원자적으로 봉인했다는 보장은 없다. 이 물리 경합과 실제 지연은 HARDWARE_NOT_RUN이며 운전 프로필은 미승인으로 남긴다.

## 검증 기준

실제 production StopLink + 코어를 fake CanPort로 실행한다. 정상 ID1/ID2/2축, 단일 inflight, F7 횟수, quiet 무송신, 진단 완료; 접수만으로 성공 금지; success+idle; idle 단독; success+failed/bus-off/overflow; unexpected 완료; status counter 변화; close/격리 실패와 100ms 경계; poll 9/10ms, 긴 receive/submit, 시계 역행; RX batch 초과 및 마지막 frame 시점 오류; 미승인 무초기화; 만료 action 무제출; terminal 이후 무송신을 검사한다. 실제 IdfTwaiPort는 별도 SDK stub 시험으로 설정/플래그/zero-wait/상태·각 API 실패를 검증하고 real SDK compile/link로 stub과 실제 API 차이를 확인한다.

추가 finalization 시험은 마지막 health 뒤 close에서 BUS_OFF/오류 counter/잔여 RX가 드러나는 경우, quiesced=true/healthy=false, API 실패, close 중 시간 경계 도달 모두 링크 Fault임을 확인한다. 기존 ST1 host 및 2개 mutation 회귀를 다시 실행한다. target은 별도 build/sdkconfig 경로로 실제 compile/link/ELF/BIN 생성까지 수행하고 버전·명령·출력·해시를 기록한다. app_main 기본값에서 TWAI/Wi-Fi/모터 초기화 호출이 없는 것을 확인한다. host 성공, target 빌드 성공, 실물 시험 NOT_RUN을 구분한다. target 바이너리는 준비용이며 운전용으로 승인되지 않는다.

수정 범위: 새 components robot_can/robot_twai, robot_core의 generic transport fault, main/CMake, host adapter/SDK stub tests와 runner, .gitignore, README/ARCHITECTURE 및 .dev의 계획·검토·검증·인수인계. SDK 설치/빌드 캐시는 .dev/tools와 evidence 하위 ignored 경로. 기존 원본자료·구매표는 변경하지 않는다.
