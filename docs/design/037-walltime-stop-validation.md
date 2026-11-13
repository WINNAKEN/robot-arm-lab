> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 037 — 실제 경과시간 HTTP 지연·정지 경로 측정

2026-10-26 사용자 지시. 제품 소스/정책 무수정, 실물 보정·운전·장치·플래시 제외, 링 보류. L2 최대2 / L4 최대2. 비작성자 검토 필수; 외부계열 기존 차단/NOT_RUN 잔여 유지. 기존 PA/terminal/startup/firstfault 소진 원장과 충분다음 임계 보존. 실제 제품 반례 수용 시 원장대로 처분하고 자동 수정하지 않는다.

## 이번 범위

실제 Chromium 휴대폰 크기 DOM/touch/fetch → loopback HTTP 시험 전송부 → 실제 C++ Owner/Boot/Run/Gate/codec + FakeCAN. 실물 휴대폰/WiFi/ESP32/전기적 CAN의 지연이 아니다. 035 virtual-clock 전위상·인계·숫자이동 검증을 대체하지 않는다. **cold Boot 상태에서 인증·조회·독립 Stop만** 측정하며 유지보수/enable/인계/숫자명령은 보내지 않는다. 따라서 정상 Run 정지·토크해제 수용/전체 부팅 운영성 보장도 아니다.

## 시계·서비스·관측

새 시험 native actor는 steady_clock의 실제 경과ms로 FakeCAN now를 갱신하고 tick한다. sleep 약1ms는 OS에 맡긴다. 지연 후 과거1ms씩 tick 재생/가상 보충/시간 정지 금지. stdin reader 스레드는 실제 도착시각과 줄을 큐에 넣고, 제어 스레드만 Owner/포트에 접근한다. 명령 enqueue_at은 reader 실제 도착시각; Node에서 과거 시각을 공급하지 않는다. 실제 tick 간 최대 간격을 보고하며 모든 결과는 측정 사례에만 해당한다. 기존035 wire/결과/진단 직렬화를 재사용하되 W 명령은 거절한다.

브라우저 clock API·Date·timer 교체 없음. performance.now 기반 반환값 불변 fetch/Response.json 관측과 Node hrtime 기반 접수/dispatch/reply 시각, native steady clock/stop_at을 각각 기록한다. 서로 다른 시계의 절대값을 빼지 않는다. native 원점은 첫 응답과 Node 송수신 사이 구간으로만 대응하며 nativeStop 이후 응답 전송을 보는 인과 검사는 native before/after snapshot으로 판정한다. 왕복 지연·HTTP 접수→native 결과·응답보류시간·native Stop→Terminal은 동일 시계 차이로만 계산한다.

Node setTimeout으로 의도적 request-delay / response-delay를 분리한다. 지연은 최소치이며 실제 elapsed를 보고한다. status와 Stop은 독립 핸들러로 처리하고, native RPC는 단일 FIFO이지만 미래 HTTP 응답 대기 중 RPC를 점유하지 않는다. Stop 주소를 loopback으로 route하는 시험 어댑터는 SDK CORS/서버/소켓 분리를 증명하지 않는다. 모든 예상 외 URL 차단.

## 사전 고정 시나리오 (각 1회; 실패 후 위상 튜닝/재시도 없음)

0. 읽기 전용 진단: cold actual DOM pairing 후 3초 동안 원래250ms 조회를 유지한다. 실제 fetch 왕복/HTTP 처리시간·native tick gap을 기록한다. core가 먼저 고장 정지하더라도 그 사실을 보존하며, 진단 데이터 취득과 정지 양성 수용은 별개다.

1. 축1 baseline, 2. 축2 baseline: cold actual pairing→NeedsMaintenance 상태 조회→실제 DOM Stop→actual stop_at>0/종료 결과와 화면 과거관측. 동작/허가0. 미설정 heartbeat/boot proof 탓에 verified가 false이면 manual-cut true 등 실제 결과를 그대로 보고한다. verified false를 verified true 성공으로 부르지 않는다. Terminal 미도달은 실패.
3. 축1 status 응답1200ms 보류 + Stop 응답1200ms 보류: 먼저 인증된 baseline 상태를 받은 뒤 보류 상태요청을 기다리고 즉시 Stop 한 번. Stop ACK 전 native에서 actual Stop 시작을 확인한다. status/ACK 대기가 Stop admission을 막지 않는지 검사한다.
4. 축1 Stop 요청100ms 지연: 지연 중 native 상태에서 stop_at0, 그 뒤 전달 후 actual Stop 확인. 네트워크 전송 전에는 서버가 정지할 수 없음을 분리한다.
5. 실제 잘못된 pairing: Auth 거절/pairedmask0/FD0/F3on0.

양성에서 exact 현재 웹 asset hash·실제 인증·listener·stop namespace·stop_at·FD0·F3enable0·calibrationfalse·페이지오류/외부요청0 확인. cold actor 원래 proof가 없어 수동차단필요로 종료될 수 있음을 별도 분류하며, 검증된 정지 물리보장은 하지 않는다. timeout은 고정(각20초)·진단은 보존, 화면상태가 실패하면 성공 범위에 포함하지 않는다.

L2 R1 WT-P1-1 수용/수정: **모든 Stop 양성**은 클릭 직전 native phase0/stop_at0/core_fault0/adapter_fault0, 그리고 native가 Stop envelope를 처리하기 직전 같은 정상 상태를 별도 기록해야 한다. 실제 인증·Stop listener의 결과 wire/core_error0과 result.accepted_at가 해당 전이의 snapshot.stop_at와 정확히 같아야 한다. 큐/HTTP 지연 사이에 먼저 자동 Fault/정지가 발생하면 명시 Stop 양성 실패로 남긴다. native 명령 응답은 실제 enqueue 직전/후 상태를 시험 메타데이터로 별도 기록하며 product status/result 내용은 변경하지 않는다. Terminal만/stop_at>0만으로 성공 처리하지 않는다. 시간제약 완화·코어 수정·뒤늦은 과거시각 tick 보충 금지. R1 BLOCK8/1은 보존하고 L2 최종R2(2/2)에서 폐쇄 확인한다.

## 유효한 대조 및 종료

baseline 동일 조건 원본을 전후 실행(각1회; 실패면 대조무효/중단). (a) 실제 받는 JS에 유효 주석을 추가해 hash 불일치로 실패 (b) Stop 전달을 생략하고 허위 성공 응답: 접수 후 native stop_at0에서 explicit-stop 검사가 실패해야 한다. timeout/문법오류만은 검출 credit 없음. 모든 원출력·실패·스크린샷 보존. 제품 파일·기존035파일 전후 hash 비교. 독립 L4가 직접 새 브라우저 실행/대조와 원자료를 확인하고 범위대로 판정한다. 기존 SDK 재빌드는 생산 코드 무수정이므로 반복하지 않는다.

소유: `src/firmware/tests/walltime_stop/`, `.dev/walltime-stop-evidence/`, 이 계획과 인계 문서. 제품·모델·BOM 변경 없음. 다음 열린 범위는 실제 Run·인계·전체 phase/부팅 조작창·실물 WiFi/CAN이다.
