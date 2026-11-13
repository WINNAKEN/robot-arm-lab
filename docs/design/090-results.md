> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 090 — CAN 진단 로그 오프라인 보고서 준비 완료

2026-10-31 KST. 실물 없는 범위에서 저장된 로그/관측 JSON만 읽는 표준 라이브러리 CLI를 구현했다. 포트·CAN·네트워크·플래시·급전·모터·설치·SDK 빌드/실행은 없다. 펌웨어·088 기록 틀·CAD/URDF/BOM은 수정하지 않았다.

## 동작과 수용 범위

`src/diagnostics/can_report/report.py`는 088 main 형식의 NDJSON과 기록용 프로필을 읽어 새로운 폴더에 JSON/Markdown을 만든다. enum/Issue 선언을 실제 현재 C++와 대조하고 source SHA를 결속한다. 원 로그/프로필 SHA도 남기지만 실제 생성 장치나 펌웨어를 인증했다고 쓰지 않는다. 기본 출처는 UNVERIFIED_LOCAL_FILE이며 합성 예시만 명시 옵션으로 SYNTHETIC_HOST를 표시한다.

DISABLED / LOG_REVIEW_ONLY / INCOMPLETE / INVALID_INPUT을 구분한다. hardware_approved=false·실제 CAN/RTOS NOT_RUN을 유지하며, expected를 observed로 채우지 않고 null/UNCONFIRMED를 그대로 보존한다. ReadyForReview를 물리 승인으로 사용하지 않고 C++ prepare_profile을 대신 실행한 것으로 표시하지 않는다. rc0은 보고서 생성 성공이다.

사람용 Markdown에는 missing/mismatch 이름, 원시 frame·ext/rtr·value·시간, bus 상태·close 전체, 원로그/프로필/현재 C++ SHA를 표시한다. Fault의 Close 시각 역행은 원순서·원값·최초 Clock 또는 다른 오류를 보존한 anomaly다. RX dequeue를 선로 시각으로 보지 않으며 이벤트 인과성·통신 PASS·물리 정지·무토크를 인증하지 않는다.

## 실제 검토·검증

- L2R1 BLOCK8/1: 실제 정상 Fault/Clock 로그의 역행을 입력 손상으로 분류하던 계획 결함을 수용했다. Clock 및 먼저 발생한 Service 오류를 보존하도록 수정해 L2R2 PASS9/0. 원R1 기록은 보존했다.
- 작성자 R1 HOST49·실제 의미 변형2개 검출 PASS. 독립 L4R1 BLOCK7/2에서 (1) Issue의 추가 미지원 선언을 부분 regex가 무시함 (2) Markdown이 JSON에 보존한 필수 bit/health/flags 정보를 생략함을 재현했다.
- R1 source3파일을 원바이트 사본으로 보존한 후 Issue 선언 전항목 fullmatch와 정확한10개 이름/비트를 강제했고, Markdown 누락 표를 추가했다. 작성자 및 독립 R2 HOST52·의미 변형2개 검출 PASS. 독립 원 추가선언 반례와 alias/newbit/bitindex 경계 거절, 실제 CLI 출처 표지/Markdown 내용을 재검증해 L4R2 PASS9/0이다.
- 지적 합집합3개 전건 폐쇄·열린0. 비작성자는 각 class 재발0/NOT_EXHAUSTED_AT_BUDGET_CLOSE로 판정했다. L2/L4 각2/2 예산은 종료했으며 같은 계열 검토의 공통 편향을 유지한다.
- 첫 테스트의 기본 sandbox TEMP 쓰기/정리는 PermissionDenied였다. 제품 승인 검사를 약화하지 않고 시험 임시 폴더만 소유 output 하위로 옮겼다. 실패를 `lineage.json`에 별도로 기록했다.

## 산출물과 다음

- `outputs/can-offline-report-090/examples/disabled/report.md`: 합성 기본 DISABLED, 누락10개·observed null 유지.
- `outputs/can-offline-report-090/examples/clock-fault/report.md`: 합성 Clock 실패, Close99/직전100의 역행과 원오류 보존.
- 각 예시의 report.json, 원 합성 NDJSON/profile, HOST/동결/L2/L4/원반례가 같은 output에 있다. 예시는 실제 CAN 결과가 아니다.

현품이 오면 기존 수령 체크리스트로 모델·드라이브 프로토콜·HW/FW·ID·배선/종단·전원 시 동작부터 실제 관측해야 한다. 이번 도구는 펌웨어 실행 설정도 장치 시험 허가도 아니다. 실물 읽기 실행은 별도 범위다. 자료 작성·변환과 실제 통신/RTOS/정지 수용을 분리한다.
