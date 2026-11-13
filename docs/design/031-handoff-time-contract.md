> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 031 HT-20261025 — 인계 권한과 결과 관측 시간의 분리 설계·실행 모형

2026-10-25 사용자: 인계 시간·권한 만료·화면 조회의 시간 조건 재설계, 실물 보정 미승인/링 보류, 부품 없는 검증부터 계속. 이 단위는 **실제 소스·030 원기록에 근거한 설계와 실행 가능한 참조 모형**까지다. 생산 코드 연결은 이 모형의 통과로 대체하지 않고 후속 소비 경로 검증으로 남긴다. 030 GUI 수용 BLOCK/PB-R1-1과 028 host 제한수용은 그대로 보존한다. 새 설계 단위 예산 L2최대2/L4최대2를 첫 검토 전에 선언. 역사/재발 원장과 PA 다음 추가 독립실측+작성자수용 동일class1 즉시EXHAUSTED, startup/SB/firstfault 임계 유지. 새 번호는 원장/미완 증거 초기화가 아니다. 외부계열 기존 중앙 차단 NOT_RUN/우회 없음.

## 실제 소비 경로와 실패 원인

현재 app.js는 명시 handoffAndAcquire()로 click+700ms 의도를 만들고 250ms poll에서 phase2 && ready일 때 한 번 Acquire. pulse50ms/renew200ms, fresh600ms. Owner Handoff는 BootEvidence를 실제 Run으로 옮기며 기존 권한만료를 보존한다. Run acquire만 그 provisional deadline을 해제하고 Gate의800ms 정상 lease를 만든다. gate.handle Acquire는 stopped()를 요구한다. runtime.exchange는50ms 미만, HTTP 전체250ms 미만이다. 따라서 700ms HTTP long-poll이나 코어/HTTP sleep은 허용하지 않는다.

030006: renew6428/Boot만료7228, Handoff6558, 원래브라우저조회6673/6935/7179 모두readyfalse, actor관측6993/7162/7177 readytrue. Acquire0/FD0/fault_at=stop_at7228. readiness 스냅샷을 다음 요청 admission의 보증으로 쓸 수 없다. 현재 제품 소스를 수정하지 않는 원기록 분석과 새 정책 모형을 분리한다.

## 선택 설계: 명시적인 한 번의 인계 예약 + 짧은 결과 조회

‘인계 후 제어권 받기’라는 명시 사용자 행동 하나가 **서버의 한 번짜리 인계/Acquire 예약**을 만든다. 기존 legacy Handoff를 몰래 바꾸지 않는다. 새 typed operation/receipt 경로가 필요하며 아직 생산에 구현하지 않는다. 서버는 Ready를 위조/래치하지 않고 실제 Run.poll 이후 단일 actor에서 현재 proof가 유효할 때 기존 Gate Acquire를 **한 번만** 호출한다. 실패하면 재시도하지 않고 실패 종결/정지한다. 명시 예약 없는 상태조회·pair·재접속은 예약/Acquire/갱신을 만들 수 없다. 체크 중 제어권 미리 발급안은 버린다. Gate의 stopped/proof/Arm/Ticket/Move/Stop 조건·물리 승인false를 바꾸지 않는다.

예약키는 boot + authenticated session/principal + axis + one-shot intent ID/client nonce. 승인 전 기존 Boot owner/lease/selected axis/Granted를 실제 소비점에서 검증한다. 토큰만으로 principal을 교체할 수 없다. 동시에 하나, 중복/소비된 ID는 거부한다. 단일 actor 순서상 Stop가 먼저; 같은 시각 expiry가 grant보다 먼저. 원래 fault/stop시각을 덮지 않는다.

| 상태 | 허용 전이 / 필수 조건 | 권한 효과 |
|---|---|---|
| NONE | 명시 사용자 combined 요청 + 유효 Boot owner | PENDING; 정상 lease0 |
| PENDING | 현재시각 < D, 같은 identity, 실제 proof true, 실제 Gate Acquire 성공 | GRANTED 단 한번; 정상 lease 생성 |
| PENDING | Stop/identity변경/실패 또는 now>=D | CANCELLED/EXPIRED/FAILED; Acquire0 또는 실패1; 기존 정지 경로 |
| GRANTED | 인증된 동일 키 결과 조회 | 동일 receipt 반환만; Acquire/renew 없음 |
| GRANTED | Stop/정상 lease만료/identity변경 | REVOKED/EXPIRED; 남은 receipt로 복원 불가 |
| 모든 종결 | 늦은ACK/조회/재접속/같은ID | 새권한/이동0; 새 명시 행동만 다른 키 생성 가능 |

`D = min(U_boot, t_accept + 700ms)`; 덧셈 overflow는 거부/정지. U_boot는 최초 인계 시 실제 만료값이며 준비/조회/예약 tick으로 늘어나지 않는다. `now == D`에는 grant 금지. grant는 실제 Acquire 성공 시각G에만 일어나며 `U_normal = G+800ms`를 기존 Gate 규칙으로 발급한다. explicit normal Renew200ms는 이 단계 뒤에만 가능하다. 예약 그 자체/결과 조회는 어떤 lease도 연장하지 않는다. 조기정지 기한 D<=U_boot는 허용하되 실제 stop_at은 D를 소급해 쓰지 않고 첫 actor tick에서 발견한 실제시각으로 기록한다. tick간격<10ms 가정에서는 D..D+9ms 범위이며 최종 물리 timing은 미검증이다.

## 화면 조회와 권한을 분리한 시간 예산

서버에서의700ms 예약/기존 U_boot와 휴대폰의 ‘이미 발급된 결과를 읽는 시간’은 다르다. 클라이언트의 기존 click+700ms 한 객체를 늘려 사용하지 않고 pending consent / receipt observation / acquired authority 수명을 분리한다. 서버 예약 grant기한은 절대로 늘리지 않는다. 정상 authority는 receipt 결과가 현재 boot/session/axis/intent와 일치하고 취소되지 않았을 때만 클라이언트에 채택된다. Stop/hidden/disconnect/다른 boot나 axis는 관측까지 취소한다. phase Checking→Run은 같은 예약의 예상 전이만 허용; 일반적인 generation 무시 금지. receipt의 epoch/generation, server sequence floor를 새 정상 요청 namespace에 명시 적용해야 한다. server internally consumed Acquire seq를 client가 seq1로 재사용하면 Replay이므로 floor보다 큰 다음 요청을 보장한다. 예상되지 않은 세대/ID·늦은 오류는 새 권한을 지우거나 복원할 수 없다.

조건부 검증 계약(실측 WiFi 상한 아님): status P<=250ms, actor poll gap<10ms, 명령 request(전송+실행) C_req<=49ms, 명령 ACK 반환 C_rsp<=49ms, 조회 request(전송+조회 실행) Q_req<=49ms, 조회 response 반환 Q_rsp<=49ms, browser dispatch jitter J<=50ms. 통신 각 단계가 실제 HTTP250ms/exchange50ms를 지켜야 한다. 예약 accepted receipt는 즉시 짧게 반환하며, 결과조회는 read-only 짧은 요청이다. 50ms동안 서버 전체예약을 대기시키지 않는다.

G가 첫 유효 proof의 actor 처리시각이며 G<D라는 조건에서, 예약 ACK 수신시간A 이후 첫 결과조회 도착/채택 상한 `O <= max(G,A) + P + J + Q_req + Q_rsp`. 정상 lease가 아직 충분해야 하므로 `O + C_req + safety_margin < G+800`. 취소되지 않았다는 전제도 필수다. P+J+Q_req+Q_rsp=398ms이며 후속 C_req까지 합하면447ms다. A<=G인 경우 800-447=353ms(엄격부등식이므로 safety_margin<353)의 여유다. A<=C_req+C_rsp=98ms를 server acceptance와 click의 원점 차이를 명시해 계산한다. ACK가 늦는 경우 max(0,A-G)를 더한 부등식을 따로 판정한다. 원래실패계산 G100/A49/P250/J50/Q_req49/Q_rsp49는 O498을 허용하고 옛449상한이 FAIL임을 시험한다. safety_margin400은 올바른 식에서 실패해야 한다. 무한 통신지연/모바일background에서 성공 보장하지 않는다.

클라이언트 결과 대기 상한은 명령 request49 + 서버예약700 + 조회주기250 + jitter50 + 조회 request49 + 조회 response49 =1147ms(가정). 이는 서버 grant 허용시간이 아니라 늦은 **결과 관측을 정리하는 상한**이다. 실제 U_boot가 더 이르면 서버가 먼저 종결한다. 실패/관측불능이면 보유권한을 추정하지 않고 새 이동 금지; 서버는 원래 기한/정지로 종결한다. 1147이 넘거나 grant후 lease 만료 응답은 채택 금지. 숫자 이동은 별도로 원래 fresh ready/보정/Arm/Ticket/단발100pulse/소비시 재검사 필요하다. 인계 모형 성공은 전체 숫자GUI 성공이 아니다.

## 소유·실행 검증

새 `src/control_timing/` 참조 모형·시험/README, `.dev/handoff-time-evidence/` 증거, 이 계획/인계색인만 수정한다. 기존 firmware/030/028/CAD/승인값은 전부 불변. 원본 실패 JSON SHA와 실제 제품 소스 SHA/시간상수 추출을 고정하여 숫자를 새 실측으로 꾸미지 않는다. actual trace old-rule Acquire0 및 원래7228 만료를 재구성하고 actualC++ 재생은030 독립증거로만 인용한다. 새모형은 Gate/Owner나 실제 CAN이 아니다.

모형은 virtual deterministic actor event ordering으로 explicitreserve→tick→one grant→authenticated receipt→renew/cancel/expiry를 실행한다. proof oracle은 원기록6993/7162/7177의 시각 또는 표시된 합성 schedule이다. 원기록의 관측점 사이를 연속 ready로 추정하지 않는다. 실제point-only(435/604/619ms 상대시각) 사례와 별도명시 합성구간435<=t<445ms를 분리한다. 공통가상시계를 쓰는 모형이며 실장단계 server/client 단조시계 offset·RTT/신선도보수계산을 별도 검증한다. 양축·단위 전부 커버했다고 하지 않는다. phase offset0..249와 지연0/25/49, actor gap1/9의 조합을 실행하고 위 부등식이 성립하는 경우만 조건부성공을 단언한다. 동일시각 Stop/expiry 우선, D-1/D/D+1, no proof, principal/boot/session/axis/nonce 변경, phase세대/seqfloor, duplicate/late ACK, observed late after grant/lease expiry, no hidden renewal/no autoacquire, unapproved motion 차단을 별도 시험한다.

정상 모형 PASS후 정책변형을 실제 import한 시험에서 검출한다: (1)기한등호grant허용 (2)예약tick권한연장 (3)취소뒤receipt복원 (4)receipt조회가Acquire재발행. 구문/import실패는 kill로 세지 않는다. 원래코드 복구 후 PASS. 실패초기출력 보존, 무한재시도 없음. L2전계획→독립논리검토→구현/compile·실행·변형→독립L4소스/원기록/실행대조. class/exhaustion 착지와 충분다음임계 유지 판정 필수.

## 종결과 생산 구현 진입 조건

이 단위가 PASS여도 MODEL_ONLY_TIME_CONTRACT이며 제품 수정/030 GUI closure/실물 수용은 아니다. 다음 생산 연결 계획에서 combined operation의 실제 인증·Replay·seqfloor·취소/Stop·boot→run전이를 구현하고, 실제Owner/FakeCAN 시각/phase sweep와 DOM250/50 HTTP 정상FD 양성, 지연/Stop/offline/3controls 및 회귀로 검증해야 한다. PB-R1-1은 그 증거까지 열린다. 실제ESP32 target·WiFi·폰·CAN·토크·정지·실물 보정·플래시·구매·출력·CAD·링은 미승인/NOT_RUN/보류. HANDOFF/SESSION/BACKLOG/LESSONS/architecture와 scoped local commit/push없음을 보존한다.
R1 수정 원장: HT-L2-R1-1 query outbound49 누락 수용, 양방향 조회/명령ACK/후속명령/엄격여유/1147ms를 모두 수정했다. R1원문/receipt 보존. 외부Stop이 아직 관측되지 않은 순간에 클라이언트가 이를 안다고 가정하지 않는다. 그런 늦은receipt는 로컬에서 잠시채택될수있어도 실제서버는 이미종결이므로 이동/renew를거부해야하며, 로컬Stop/hidden/disconnect후 늦은receipt는 채택도금지한다. 새 timing산술/oracle class 첫지적 OPEN/NOT_EXHAUSTED, 기존PA등 임계는미도달/불변, PB-R1-1미해결이다.
