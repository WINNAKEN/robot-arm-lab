> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 141 — 모터 무급전 ESP 펌웨어 확인과 J5 CAN 조회 준비

2026-11-12 KST. 사용자는 모터 전원을 끈 상태에서 ESP 펌웨어 확인과 J5 CAN 시험 준비를 지시했다. 현재 COM7 / USB VID303A PID1001은 OS 조회로 확인했지만 앱·보드 리비전은 미확인이다. 추가 사용자 확인은 ESP32-S3-RS485-CAN(U 없음)이며 원문은 outputs/esp-j5-can-prep-141/user-board-confirmation.json에 보존한다. J5/J6는 CAN이고 이번 대상은 J5 한 대다. J5 모터·전원 정격과 실제 CAN ID/속도는 아직 미확인이다.

## 범위와 결정

- 기존 CAN 진단 앱은 physicalReadApproved=false/static_assert로 차단되어 있다. 현재 ESP에 그것이 올라갔다고 가정하지 않는다. execution.hpp는 WaveshareCanU만 허용하므로 현재 non-U 보드는 기존 경로에서 BLOCKED_BOARD_ENUM_MISMATCH다. USB/chip 식별로 CAN-U로 승격하거나 기존 체크를 우회하지 않는다. 기존 앱/진단/RS485138/TTL140·CAD·프로필·gain/cap은 변경하지 않는다.
- USB 수동 로그 수신을 먼저 8초 수신 스케줄/64KiB로 한 번 수행한다. 매 read timeout은 최대0.2초이고 마지막에는 남은 시간으로 줄인다. 실제 경과시간에는 OS 스케줄·열기·닫기 지연이 포함되며 절대8초 종료를 보증하지 않는다. 외부 프로세스20초 상한을 별도 적용한다. pyserial3.5는 port=None으로 만든 후 DTR/RTS=false, flow control=false를 설정하고 COM7을 연다. write/reset 버튼/제어문자/초기화 명령은 보내지 않는다. OS/드라이버의 제어선 동작까지 무리셋으로 보증하지 않으며 캡처 침묵은 미식별로 판정한다.
- 로그만으로 식별되지 않으면 기존 esptool4.12.0의 read_flash만 사용한다. 모터 무급전 상태를 유지하고 USB Serial/JTAG의 ROM 진입·앱 복귀 리셋이 수반됨을 알린다. --chip esp32s3 --no-stub --connect-attempts1, --before usb_reset --after hard_reset. 세션당 최대45초, read 세션 최대2회/재시도0. 먼저 기본 파티션 주소0x8000의4KiB만 읽는다. 유효한 MD5 테이블에서 앱 파티션이 정확히 하나일 때 그 주소의 첫4KiB만 한 번 읽는다. 기본 주소가 맞지 않거나 OTA 다중 앱/암호화/보호/실패면 추정하지 않고 미식별로 남긴다. 호스트는 외부 전원 인가·CAN 요청/테스트·펌웨어 업로드/삭제·RAM stub·eFuse·보안 설정 변경을 수행하지 않는다. NVS와 전체 flash는 수집하지 않는다. USB ROM 요청 송신과 CAN 요청은 별도이며 미확인 앱의 리셋 전후 CAN 전기적 활동은 NOT_MONITORED다. 모터 무급전도 사용자 보고값이며 계측했다고 주장하지 않는다. 앱 복귀 후 앱 자체의 통신·동작·NVS 변경까지 무변경으로 보증하지 않는다. esptool 실패/timeout 시 ROM 모드 잔류 또는 앱 복귀 여부도 미확인일 수 있으며 복구를 위해 재시도/추가 reset 명령을 보내지 않고 상태를 기록한다.
- 앱 헤더 E9/첫 segment 및 esp_app_desc magic/문자 필드를 공식 SDK 구조와 대조하여 project/version/IDF/빌드시간/ELF SHA를 기록한다. 단일 앱의 저장 메타데이터와 현재 실행 로그 증거를 구분하며 앱 소스/동작 안전성 인증으로 표현하지 않는다. raw 로그의 MAC 등 식별자는 사용자 응답에 노출하지 않는다.
- J5 조회 준비 도구는 오프라인 프레임 미리보기만 제공한다. ID는1/2 중 실제 확인값만 후속 채택하며 J5라는 이유로5를 쓰지 않는다. ID 미확인은 default null, selected joint J5. 표준11bit DATA/DLC2, 읽기31/32/F1/3A만 산출하고 CAN/serial 송신 API를 갖지 않는다. baud/pin은 기대값500k/TX15/RX16과 실제 관측값 null을 분리한다. CAN-U 여부는 USB VID로 확정하지 않는다.
- 호스트가 모터 급전·J5 CAN 실제 요청/시험·설정/enable/정지/이동/교정/flash를 수행하지 않는다. 미확인 ESP 앱 자체의 CAN 활동은 NOT_MONITORED이며 전체 버스 TX0이나 장치 전체 안전성을 인증하지 않는다. 사용자에게 PSU V/A·모터 정격·보드/드라이버 리비전·실제ID/CanRate·무급전 고정·종단/배선 확인 대기를 전달한다. MKS 단독 예시 점퍼OFF와 일반 CAN 양끝120Ω 기준의 차이는 아직 실물 적용 확정이 아님을 기록한다.

## 산출·역할·검수

S/한 그룹/제품4파일: 이 계획, src/bench/j5_can141.py, src/bench/test_j5_can141.py, docs/specs/j5-can141.md. 증거는 outputs/esp-j5-can-prep-141/. Root 작성·구현, 비작성자 L2→HOST→L4 및 물리 USB 읽기 전 L4를 적용한다. 기존 승인된 동일계열 비작성자 폴백을 유지하고 공통편향을 명시한다. 외부 도구 불가의 과거 사실을 현재 실행 결과처럼 쓰지 않는다. 원138/139/140 예산·검토는 재개하지 않는다.

각 role 새 내부1500초/closing180, main reviewer L2/L4 공유, L2/L4 각최대2/총4/no5. 계획 기록 이전의 탐색·읽기 시간은 계측되지 않았으며 role clock의0초로 소급 표현하지 않는다. 실제 구현/검토 시작 qpc와 UTC, 최종 누적/잔여는 증거에 보존한다. 기존 실물 권한을 새로 열지 않는다. 사용자 지시로 허용된 이번 USB 확인과 모터 CAN 운전 권한을 구분한다. Git/설치/구매/네트워크/원격/Drive/외부 메시지0.

수용 기준: AC1 USB 장치와 앱·보드 확인 계층 구분. AC2 수신 도구 bounded/read-only/DTRRTS 사전설정/정리·오류 증거. AC3 ROM read 명령 allowlist·작은 범위·재시도0·reset 및 ROM USB TX 명시, 실패/다중앱은 미확인. AC4 헤더·MD5/문자·주소 검증 및 과도한 결론 금지. AC5 J5 기본차단/실제값 null·오프라인4읽기만·금지 opcode/실물 송신없음. AC6 기존 소스 보존·수리/독립 HOST 및 정확한 인계, 공통편향·미해결·NOT_RUN 층위 명시.
