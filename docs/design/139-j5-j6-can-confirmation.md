> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 139 — J5·J6 CAN 현품 확인 반영

2026-11-11 KST. 사용자 「모터둘다 can」→축 배정 질문 「J5와 J6」. J5/J6 드라이버 통신형은 사용자 확인 CAN, 그리퍼는 미확인이다. 이 신규 사실로 CAN 우선 안내를 만든다. 138의 RS485 준비물/원시/F2/검토/예산은 그대로 보존한다.

범위: `docs/specs/j5-j6-can139.html` 새 한국어 안내와 이 계획만(S/2 source). 사실·PDF·검토/핀·상태는 `outputs/can-two-motor-update-139/`. 펌웨어·프로필·CAN ID/bitrate·전류·모델·구동기준 변경0, 포트/급전/flash/송수신/구동/원격/설치/Git/Drive0. hardware_approved=false, physical_tests=NOT_RUN. 원138 재개나 수리 예산 초기화가 아닌 사용자 변경 사실의 문서 반영이다.

문서만의 S 단위로 L2 생략, Root 작성→비작성자 L4 문서 대조→정확 핀·실제 렌더 확인·인계. 내부 reviewer cap1500초/closing180, 최대L4 2회/no5, 이전138 round/cap 불변. 기존 동일계열 비작성자 폴백 승인과 공통편향 잔여를 유지한다.

자료: 기존003 CAN 가이드의 전원·H/L·절연·양끝종단과 원 Makerbase CAN V1.0.9; 현재 robot_core/mks_codec.cpp의 표준DATA/DLC2/sum(ID+opcode)·ID1/2 제한; diagnostic/main/main.cpp의 physicalReadApproved=false/static_assert; execution.hpp의 CAN-U/500k/GPIO15/16은 기대 제약이고 실제 확인값이 아니다. 문서의 초기 ‘미구현’ 설명은 최신088과 현재 소스 대비 역사로 구분한다.

수용6: ①J5/J6 CAN 사용자확인·그리퍼미확인·실제SKU/FW/전원 미확인 분리 ②CAN H-H/L-L·전원분리·USB/DC/SGND·1축→2축/끝만120Ω ③ID1/2는제안이며관절번호5/6과구분·중복ID 상태동시연결금지 ④CAN프레임과RS485138 미호환·실제CAN펌웨어기본비활성/보드CAN-U기대값미승인 ⑤실제통신/송신/운전없음·범위보존 ⑥한국어PDF시각검사/원자료·후속판정·핀/동결일치. 표의8개읽기프레임은 별도 산술 검산하며 명령을 전송하지 않는다.
