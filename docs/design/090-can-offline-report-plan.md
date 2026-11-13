> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 090 — CAN 읽기 진단 로그의 오프라인 보고서 연결 계획

2026-10-31 KST. 상태 PLAN_REVIEW_PENDING / IMPLEMENTATION_NOT_RUN. 089의 시뮬레이션 재개와 별도 오프라인 M/검수급 단위다. 첫 시계 00:33:37Z, 종료01:18:37Z(한국10:18:37) 45분 상한, L2/L4 각최대2회다. 089 SDK 발사/종료 시각을 연장하지 않는다. 사용자 동일계열 비작성자 폴백 승인과 공통편향 잔여를 본 후속 검토에도 적용한다. 별도 실물/SDK/빌드 예산은 0이다.

## 목적과 입력 경계

088의 실제 `src/firmware/diagnostic/main/main.cpp` 출력과 `docs/specs/read-diagnostic-profile.template.json`을 사람이 확인할 한 묶음으로 보여준다. 입력은 사용자가 저장한 로컬 로그 파일과 기록용 관측 JSON뿐이다. 포트 열기·시리얼·CAN·SSH·웹·소켓·펌웨어 설정 쓰기 기능을 만들지 않는다. 기존 펌웨어·템플릿·수령 체크리스트·Isaac 코드는 수정하지 않는다.

main의 현재 출력에는 기본 DISABLED JSON과, 준비된 실행 경로의 terminal/health/event JSON이 있다. terminal의 state/error와 event의 kind/error는 C++ enum 순서의 숫자다. JSON 기록 템플릿은 펌웨어 실행 설정이 아니다. `ReadyForReview`와 기록상 Complete는 물리 승인이나 정지·무토크 검증이 아니다.

## 최소 제안

- 신규 `src/diagnostics/can_report/` 아래 표준 라이브러리만 쓰는 CLI와 검증기를 둔다. 원본 파일은 덮어쓰지 않고 신규 출력 폴더만 사용한다.
- 관측값 null/UNCONFIRMED는 그대로 보존한다. 예상값을 관측으로 복사하지 않는다. `hardware_approved=true` 입력은 수용하지 않으며 출력은 항상 false다. 사람의 관측 기록과 실제 `prepare_profile()` C++ 실행을 구분하고, Python만으로 ReadyForReview를 새로 확정하지 않는다.
- DISABLED 기본 로그의 Pending/missing1023/mismatch0, enum/bit 이름, 원시 시각·frame/value·bus/close, 종료/오류·누락 여부를 읽기 쉬운 표로 만든다. `rx_dequeued_ms`를 선로 도착 시각으로 표시하지 않는다.
- 원 로그와 관측 JSON의 실제 파일 SHA/크기 및 해석에 사용한 C++ source SHA를 보고서에 남긴다. 이 연결은 파일 동일성의 근거이며 실제 장치에서 생성됐다는 인증은 아니다. 현재 로그 자체에 firmware SHA/session/device 식별자가 없다는 한계를 표시한다.
- 결과는 DISABLED / LOG_REVIEW_ONLY / INCOMPLETE / INVALID_INPUT과 관측 미확인 목록을 구분한다. 로그 구조가 일치해도 PASS_READONLY나 물리 통신 PASS를 자동 생성하지 않는다. 실제 통신 수용에는 별도 현품 관측·실행 조건·장치 시험이 필요하다.
- 실제 main 형식의 기본 DISABLED 예시와 저장된 HOST 합성 로그를 각각 표시한다. 합성 로그는 SYNTHETIC_HOST로만 명시하고 실제 장치나 Isaac의 CAN 선로 시험으로 표시하지 않는다.

## 검토와 검증 후보

구현 전 L2, 최소 구조 검사 후 비작성자 L4를 둔다. 입력 parser는 duplicate key/nonfinite/타입오류/알 수 없는 enum/예상 외 필드/과도한 크기/잘린 JSON을 거절한다. Complete+error·overflow 또는 승인오염, 누락 terminal/health 등 모순·불완전 경로를 부정 예시로 확인한다. 원 main에서 따온 정상 shape 양성/정상 DISABLED 양성과 함께 실행한다. 숫자 이름 매핑만 맞는 것을 실제 통신·RTOS·정지 수용으로 확대하지 않는다.

## 이번 최소 구현 계약

소유는 `src/diagnostics/can_report/report.py`, `test_report.py`, `README.md`, `outputs/can-offline-report-090/`, 본계획/결과문서·최소인계뿐이다. 기존 펌웨어/088입력/템플릿/089소스·원장은 쓰지 않는다. 표준 라이브러리만 사용하며 CLI는 `--log`, `--profile`, `--out`을 명시한다. 입력각1MiB·NDJSON최대130행, 빈행은 무시하되 비JSON콘솔행은 INVALID_INPUT으로 닫는다. 입력은 JSON객체, 중복키/비유한/과대정수/잘못된타입/알수없는필드는 거절한다. 출력폴더는 기존경로가 아니어야 하고 원문덮어쓰기없음, UTF8 JSON/Markdown 두파일을 생성한다. rc0은 보고서 생성 성공일 뿐 물리PASS가 아니다.

기본 DISABLED는 실제main의 7키(state/hardware_approved/CAN_started/profile_readiness/missing/mismatch/tick_hz)만 허용한다. false2개·1000Hz·10bit범위·readiness와missing/mismatch의논리일치를 확인한다. 실행로그는 terminal3키(state/error/overflow), health12키(last_alerts/last_bus_state/tx_pending/rx_pending/rx_missed/rx_overrun/tx_failed/bus_errors/arbitration_lost/close_quiesced/close_healthy), 이후 event11키(kind/error/at_ms/rx_dequeued_ms/id/dlc/ext/rtr/value/data)를 정확히 구분한다. 실제키수는 main을 정본으로 하며 잘못 센 산문키수보다 나열한 집합이 우선이다. enum 이름은 현재 C++ 헤더의 선언순서를 읽어 source SHA와 함께 결속하고, 지원한 선언형식이 바뀌면 거절한다. flags/bool은 숫자와 구분하고 data8byte/DLC0..8/원시시각uint64/valueint64/IDuint32를 확인한다.

Complete+error/overflow, Fault+None, 승인오염은 INVALID_INPUT이다. 시각 역행은 원문 event 순서와 값을 바꾸지 않고 anomaly에 기록한다. Complete와 역행이 함께 있으면 모순으로 거절하지만, Fault에서는 먼저 발생한 오류가 Clock 이외일 수도 있으므로 원 오류를 보존한 진단 실패로 보고한다. `Runner::finish()`가 close 뒤 시계를 읽어 last_=now로 기록한다는 실제 경로를 따른다. terminal/health/Begin/Close 또는 Complete의4조회 Value이벤트가 빠지면 INCOMPLETE로 표시하며 성공으로 보완하지 않는다. event/fullwire 인과성·hardware RX시각·물리정지·실제통신 인증을 새로 주장하지 않는다. Complete 로그의 검토결과도 LOG_REVIEW_ONLY이며 실제CAN_hardware_test는 NOT_RUN을 유지한다. 잘린 JSON은 INVALID_INPUT, 행단위는완전하지만 종료가없는로그는INCOMPLETE다.

profile은 기존 template의 top/expected/observed/evidence 키집합 및 목적/버전/승인false를 대조한다. expected는 원template와 일치해야 하며 observed의후보기대값을채우지않는다. observed 숫자/문자열/null/UNCONFIRMED 값은 원문보존하고, Python이 prepare_profile ReadyForReview를 대신 확정하지 않는다. source enum 해시결속은 파서 호환성 증거이며 원로그가그펌웨어에서나왔다는 인증이 아니다. evidence에 실제통신/RTOS 시험값이 NOT_RUN이 아닌 기록은 이번 실물없는범위에서 거절한다.

테스트는 DISABLED/Pending 원형 양성·합성terminal양성·관측null보존·원본SHA·중복키/비유한/과대크기·미지enum/필드/타입·bool숫자혼동·data/DLC·terminal모순/승인오염·잘림/누락/시각역행·out기존경로거부를 포함한다. L2R1의 정상 Fault/Clock+Close 역행 반례를 양성으로 보존하고, 이미 존재한 다른 오류+Close 역행도 원 오류 보존을 확인한다. 기본CLI 출처는 UNVERIFIED_LOCAL_FILE이며 합성예시에만 `--synthetic-host` 표지를 명시한다(판정/물리승인 영향없음). 합성자료와기본예시 모두SYNTHETIC_HOST로표시하며 실제장치증거로승격하지않는다. L2 PASS→구현→HOST/변형→비작성자L4 PASS→예시보고서/결과저장순서이며 실제 장치 동작은 없다.
