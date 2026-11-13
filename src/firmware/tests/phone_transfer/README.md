# 실제 인계 예약 연결 — 032

실물 보정은 미승인이고 링 형상은 보류 상태입니다. 장치 업로드·모터 운전은
수행하지 않습니다. 이 경로는 명시적으로 누른 인계 버튼에만 반응합니다.

1. `handoff-acquire`가 현재 Boot 사용자·축·권한을 확인하고 예약합니다.
2. 서버는 기존 Boot 만료와 접수+700ms 중 빠른 시각 전에 현재 정지 증명을
   확인하고 기존 Gate Acquire를 한 번만 실행합니다.
3. 휴대폰은 실제 Run 상태가 관측되면 `handoff-result`로 결과를 조회합니다.
   조회가 제어권을 재발급하거나 갱신하지 않습니다.
4. 실제 정상 권한이 확인돼야 다음 갱신·이동을 허용합니다. 숫자 이동은
   실물 보정 승인과 기존 Arm/Ticket/100pulse 단발 조건이 별도로 필요합니다.

첫 상태 조회 전의 Stop도 새 인계 요청의 동일 사용자·축·요청 ID와 예상 세대가
모두 일치하면 처리합니다. ACK를 기다리면서 누른 Stop 후에 늦은 응답으로 권한을
복원하지 않습니다. 기존 legacy Handoff API의 세대가 지난 Stop 제약은 별도
미해결 항목이며, 이 변경으로 전역 호환 문제가 모두 해결된 것은 아닙니다.
화면 숨김·연결 해제의 로컬 취소만으로 서버 예약이 즉시 철회되지는 않습니다.
서버가 취소 통신을 받지 못하면 기존 예약 기한 안에 권한을 발급할 수 있으며,
추가 갱신 없이 정상 lease 만료로 정지합니다. 이것을 즉시 원격 정지로 쓰면 안 됩니다.

프로토콜은 기존 v1 필드를 유지합니다. 예약 ID는 최초 `request`이고, 결과 조회와
새 인계 대기 중 Stop은 `ticket` 필드에 그 ID를 넣습니다. 인증 자격은 별도 헤더로
검증합니다. 결과의 `sequence_floor`는 내부 Acquire가 소비한 번호이며 다음
정상 명령은 그보다 커야 합니다. 상태: Pending1, Granted2, Cancelled3,
Expired4, Failed5. 정상 lease는 실제 발급 후800ms, 조회는 만료를 바꾸지 않습니다.

휴대폰은 서버 시계와 자신의 절대 시각을 비교하지 않습니다. 응답의
`lease_until - accepted_at`에서 요청 왕복 시간을 보수적으로 차감합니다.
새 경로는100ms를 추가 확보하고 첫50ms pulse에서 갱신할 수 있도록 준비합니다.
무한 네트워크 지연이나 모바일 백그라운드에서 성공을 보장하지 않습니다.

저장소 루트에서 장치 없이 실행:

```powershell
powershell -ExecutionPolicy Bypass -File src/firmware/tests/phone_transfer/run.ps1
node src/firmware/tests/phone_transfer/test_ui.cjs
py -X utf8 .dev/phone-transfer-evidence/control_runner.py new-control-run
```

브라우저 시험은 설치된 Chrome의 임시 headless 프로필과 loopback HTTP fixture를
사용합니다. 실제 C++ Owner/Boot/Run/Gate/codec/FakeCAN이지만 ESP32 HTTP 서버나
실제 휴대폰 Wi-Fi 시험은 아닙니다. 기존 사용자 Chrome 로그인·탭은 사용하지 않습니다.
시험용 operator slot은 읽기 전용 관측으로 고른 유리한 조작 시점입니다.
실제 사용자 조작성이나 모든 위상의 성공으로 해석하지 않습니다.

전체 통과 여부와 실패·미실행 항목은
`.dev/phone-transfer-evidence/disposition.md`가 정본입니다. 일부 시나리오 성공으로
030의 전체 브라우저 검증을 폐쇄하지 않습니다.
