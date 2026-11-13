> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 085 — CAN 도착 전 소프트웨어 준비 상태

2026-10-30 코드 읽기 대조. 실물 통신·플래시·모터 운전은 NOT_RUN이다. 선택 부품/배송과 큰 모터 사양 차이는 `084-motor-change-and-can-readiness.md`를 함께 본다.

현재 펌웨어의 실제 벤치 범위는 **축 ID 1과 2**다. `components/robot_core/mks_codec.cpp`의 `valid_axis()`가 이 두 ID만 허용한다. 보드 하나의 CAN 버스가 여러 노드에 연결될 수 있다는 설명과, 현 2축 벤치 펌웨어가 6~7축을 이미 지원한다는 주장은 구분해야 한다. 최종 6축·그리퍼 확장은 축 목록·버스 부하·허가/정지 상태·설정 증명·UI와 시험을 함께 확장할 별도 작업이다.

## 도착 전 확보할 기록

| 대상 | 기록할 내용 | 현재 상태 |
|---|---|---|
| 모터/드라이브 A·B | 모델, CAN MT 옵션, HW/FW, 정격, 실제 단자 사진 | 사용자 도착 보고 / 실물 대조 미확인 |
| 컨트롤러 | ESP32-S3-RS485-CAN-U 옵션·기판 리비전·CAN 단자·전원 범위 | 배송 대기 |
| 배선 | H/L 꼬임 쌍 식별, 기준 GND, 차폐 처리, 양 끝 종단 내장 여부 | 최종 무전원 대조 전 |
| 모터 설정 | 실제 CAN ID·bitrate, 출고 토크/전원 복귀 설정 | 미확인 / 메뉴 변경하지 않음 |
| 실제 통신 증거 | 원 TX/RX, ID·DLC·flags·checksum·시각·오류 counter | NOT_RUN |

구현 후보는 S3 TX15/RX16, 500 kbit/s다. 도착품 회로도/설정과 일치하는지 확인 전에는 이를 연결 지시로 쓰지 않는다. 보유 ESP32-WROOM에 S3 핀을 그대로 적용하지 않는다. 현재 codec은 Classical CAN 표준 데이터 프레임만 대상으로 한다. 명령 바이트 `0xFD`는 CAN FD 프레임을 사용한다는 의미가 아니다.

## 장치 없이 확인 가능한 실제 명령 범위

`components/robot_core/include/robot_core/mks_codec.hpp` 기준이다. 아래 목록은 코드에 존재하는 기능이며 지금 송신하라는 절차가 아니다.

| 읽기 코드 | 코드상 의미 | 범위 |
|---|---|---|
| 0x31 | 위치 | ID1/2, 수신 신선도는 codec 밖의 소유자가 확인 |
| 0x32 | 속도 | 동일 |
| 0xF1 | 운전 상태 | 동일 |
| 0x3A | enable 상태 | 동일 |

F3 허가/해제, F7 정지, FD 이동은 읽기 전용 확인과 구분한다. 인코딩 성공·송신 접수·응답 수신·물리 정지는 서로 다른 증거다. 현재 하드웨어 승인 false를 변경하지 않았으며 부팅/인계/정지의 실제 소유자를 우회하는 임의 송신 도구를 추가하지 않았다.

## 기존 검증 자료를 다시 사용할 때

- 기본/준비 실행부 설명: `src/firmware/README.md`, 최종 실행부 판정 `.dev/phone-runtime-evidence/disposition.md`.
- 부팅→인계→정지의 가상 시계 브라우저 대조: `src/firmware/tests/browser_chain/README.md`. 실제 휴대폰·Wi-Fi 지연 검증으로 취급하지 않는다.
- 실제 호스트 시계 관측부: `src/firmware/tests/walltime_observer/README.md` 및 `.dev/observer-controls-evidence/disposition.md`. Windows 시간 조건 위반은 NOT_REACHED/credit0이며 정지 성공으로 바꾸지 않는다.
- 도착 전 외관/고정/조건부 화면 확인: `docs/specs/bench-no-can-checklist.md`. 전원만으로 토크가 생길 수 있다는 경계를 유지한다.

위 기존 시험은 이번085에서 재실행하지 않았다. 기존 시나리오별 실행 횟수 제한을 새 허가 없이 재사용하지 않는다. 부품 도착 시 먼저 수령 정보와 무전원 배선을 대조하고 별도의 최소 통신 시험 계획을 확정한다. 보정·원점 복귀·토크 허가·회전 명령은 이번 범위에서 계속 제외한다.
