> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 039 — 038 최종 수정본의 전체 브라우저 실행 확인

2026-10-27 사용자 명시 지시: 최종 수정본 전체 브라우저 검증 재개, Windows 시간 조건 위반 별도 구분, 실물 보정·모터 운전 제외. 이번 실행 권한은 038의 이전 재실행 한도를 대체하는 새 유한 검증 범위이며 원래038/037 실패·소진·예산을 덮지 않는다.

## 불변 경계

제품·037 native actor/타이머·038 fixture/oracle/소비부/대조 코드를 그대로 사용한다. 코드 수정·기한 완화·우선순위/타이머/위상 튜닝·가상시계·과거tick보충·새 보정/승인 프로필 주입 없음. 장치/시리얼/플래시/실물 CAN/네트워크/운전/구매/모델링 없음. 브라우저 모바일 뷰포트+loopback HTTP+actual C++ Owner/Boot/Run/Gate/codec/FakeCAN까지이며 실제 휴대폰/WiFi/ESP32/정상Run/handoff/all-phase/전기적정지 수용이 아니다. FD/F3enable0·calibrationfalse 유지, coldStop의 verifiedfalse/manualcuttrue도 실제값으로 기록한다.

## 고정 실행 목록 / 예산

L2최대2 / L4최대2, 비작성자 검토. 작성자와 독립 검토자는 각각 다음을 한 번씩만 실행한다.

1. 현재038 최종 파일 해시와 이전149 원본을 확인하고, 작업 시작 firmware 전체 파일/경로 SHA256도 기록한다. 기존037 strict native builder를 한 번 compile/link하고 실행파일 해시/컴파일명령/출력을 이번 증거에 보존한다. unit34 및 final consumer/schema 결정론 검사도 현재 소스로 실행한다.
2. `walltime_observer/test_browser.cjs ... UNIQUE_DIRECTORY all`: readonly3초, baseline축1, baseline축2, held-status1200ms+held-StopACK1200ms, inboundStop100ms, badpair 각1회.
3. `walltime_observer/test_controls.cjs UNIQUE_DIRECTORY`: beforebaseline→valid-comment wrongasset→missingforward→afterbaseline. 기존 runner의 정상전제/환경중단 규칙 그대로. 환경/결함으로 중단된 나머지는 NOT_RUN/NOT_REACHED 및 credit0이지 통과가 아니다.

성공할 때까지 재실행하지 않는다. 환경 미도달/실패를 보존하고 같은 소스·타이밍·설정으로 원자료를 독립 검토한다. 현재소스에서 구현 결함을 발견하면 이번 verification-only 범위에서는 수정하지 않고 원장과 사용자 처분으로 넘긴다. L4재실행 한도를 검토 라운드 추가로 늘리지 않는다.

## 판정과 증거

각 실행의 verification PASS/FAIL/NOT_REACHED와 environment gap/native Time8/사전stop 사실을 원래038 방식대로 분리한다. 큰 gap 하나로 schema/인증/namespace/data 오류를 환경으로 덮지 않는다. 실제Time고장 선행으로 미도달한 사례는 ENV_SERVICE_VIOLATION·credit0, unknown은FAIL이다. 원래summary FAIL/exit1이 환경미도달을포함할수있으므로 원본파일을그대로보존하고 별도집계에서 차이를 설명한다.

전체선택목록 수용은 한 고정실행의6필수사례 PASS와 두 유효대조 및 양성bracket PASS가 모두 있어야 한다. 서로 다른 실행의부분PASS를합쳐 한 전체PASS로 만들지 않는다. 작성자/독립 실행별로 따로 판정한다. 환경미도달이면 관측된 namedcase만 부분수용하고 전체OPEN으로 남긴다. 어떤 결과든 Windows<10ms 보장이나 실제모터정지성공으로 확대하지 않는다.

증거 정본 `.dev/final-browser-evidence/disposition.md`: 원출력·JSON·스크린샷·실행exit/입력hash·단위검사·최종앞뒤해시, 독립L2/L4 및 집계. 이전038 최종수정후없었던 live 실행이라는공백을이번에실제로도달한범위만닫는다. 기존PA/terminal/startup/firstfault 소진이력·다음instance임계·037host-service보장소진/외부계열NOT_RUN·링보류·실물승인false를유지한다. 로컬소유범위커밋/push없음.
