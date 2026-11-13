> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 063 — 실제 SDK 연결과 2초 중력 진단 실행

2026-10-29 사용자 새 실행 예산 승인. 062의 감사만 실행/진단0/연결0과 원본을 보존한다. 새 작업 시작06:36UTC, 종료07:21UTC(45분). L2/L4 각각 최대2회, 실제 installation_audit/provider_diagnosis/provider_connection 각각 최대1회(실패도 사용). 추가 독립 SDK 실행0. 재부팅·설치·실물 보정·모터 운전·CAN·flash·구매·학습 없음. 질량/관성 가정, 링 보류, 047 전체동작 미해결 유지.

062 감사 완료06:31:45UTC에 대한 freshness300초는 새 설계 검토/실행 시점에 만료된다. timestamp/freshness 수정·062 재감사·예약 삭제 없이 신선한063 원장/입력으로 시작한다. 이는 사용자 승인 새 실행 범위이며, 이전 실패를 지우거나 동일062 purpose를 재시도하는 것이 아니다. 061/062 원장 및 기존 class 원장·first-fault를 그대로 보존한다.

소유: src/simulation/native_gravity_v1/ 9파일, outputs/isaac-native-gravity-v1/, 이 계획. .dev/CAD/BOM/047~062 소스·산출물 무수정. 062 최종 검토/host23 PASS 소스9개를 복사하되 namespace _checked062→_checked063, OUT/remote root와 README, legacy 검증/fixture에 필요한 실행 계보만 바꾼다. physics.py/robot.py/providers.py/worker.py는 원062와 byte-identical로 유지한다(이들에 namespace 문자열이 있으면 변경하지 않음). 실제 매핑·contact 정책·동역학/명령·clock·source API·종료코드 소비 계약은 수정하지 않는다.

새 legacy(c)는 원062 원장 SHA412b11f76d3268be2fab2c442eef28b0aece4c99f7b842a63b9492cbdefd3edb를 고정하고 schema_version1/legacy_061/reservations를 검사한다. 원062 reservations는 정확히 감사1개 run9954955318004a308730b70db75bc948이어야 한다. 기존061 기록은 이 원장 안에 해시 결속된 채 중첩 보존한다. 새063 원장은 schema_version1/legacy_062/reservations로 고정하고 새 purpose3개를 순서대로 각1개만 허용한다. settings references에 원062 delivery.json의 실제 SHA를 추가한다. 기존SDK/prefix seal·모든 frozen reference는 그대로다.

L2 후 구현, AST/바이트 비교/범위 whitespace 및 기존23개 호스트 회귀를 수행한다. fixture의 legacy 원본과 schema를 새 계보로 전환하고 nested 원본/허용 예약 정확성·변조/중복 purpose 거절 대조를 유지한다. L4 PASS 후 source 지문을 동결한다. author의 host 실행과 비작성자 정적 검토, 실제 SDK 결과를 구분한다. 외부 bridge hook 차단 이력의 재시도/우회 없이 same-family 비작성자 fallback 한계를 명시한다.

실제 시험은 새 prefix 설치 감사→fresh provider 진단→같은 입력 signature의 연결 순서다. 각각 900/300/600초의 기존 timeout과 freshness300을 유지하고, 원07:21UTC cap 전에 완료 가능한 단계만 착수한다. 각 실행의 원격 원장·직접 PID·actual/policy/shell/SSH/local exit·원본 결과·수송을 확인한다. 실패 시 원자료만 회수하며 native 재실행/solver·gain·cap·물성·threshold 튜닝을 하지 않는다. SDK/모듈 초기화 순서·NumPy/prefix Torch·CUDA 실효·Lab view9개·실제 엔진 clock을 같은 기존 계약으로 검사한다.

연결은 기존0g baseline10step/11state를 먼저 통과하고 같은 view/clock으로 g=[0,0,-9.81], gravity flags, zeroPD, cap[3,6,5,2,2,1]을 readback한다. native full6 또는12열/actual DOF 이름에서 J1~J6 absolute columns를 계산한다. 12열이면 앞6 root-wrench와 뒤6 DOF force를 구분해 기록하며 actual LINK/COM torque와 명령 전 최대1e-3Nm 일치가 필수다. 실패면 pending QUERY/SHAPE/RAW/MAPPED와 primary 오류를 보존하고 명령 전에 실패한다. root는 원본에서 독립 재계산한다.

적격성이 통과할 때만240step/241state, 실제 engine 시간2초를 수집한다. 자세 q<=0.5도/qd<=1도초, 미포화, probe 낙하>=.05m/1초후z=.025±.002m/바닥 양성힘>.1N, 원치않는 접촉<=1e-3N(Base-floor 장착면 제외)를 검사한다. float32 접촉 성분별 구간은062 승인 수식/총T<=1e-4N 및 원1e-6 결과 병기를 유지한다. 유효한 동역학 실패는 GRAVITY_DIAGNOSTIC_FAILED/local1, API·증거 오류는 FAILED/INVALID_EVIDENCE로 구분한다. baseline SDK연결 성공과 동역학 성공을 합치지 않는다.

마지막에 owned PID 잔존/Kit/lock과 원061·062 원장 불변을 확인하고 delivery/HANDOFF/manifest와 실제 metrics를 저장한다. 실제 매핑 수치·240/241·clock구간·최대 각도/속도/토크오차/접촉오차·probe 낙하·정착/힘을 근거와 함께 보고한다. 필요시 기존 자료로 후처리만 하며 SDK 추가 실행은 없다. 실제 시험 성공은047의56.5초 일반동작/28checkpoint·강화학습·실물 수용이 아니다. 소유 경로만 commit, push 없음.

L2/L4 브리프에 기존 provenance7 EXHAUSTED/physical6 EXHAUSTED/eligibility2 및 다음 동종 독립 실측+작성자수용1 충분 임계와 first-fault 이력을 명시한다. 062 부분관측 영속화 CC062-R1-1 정적CLOSED/한정 소스 미소진 판정은 보존한다. 예산 종결 시 class 착지·소진/미소진을 비작성자가 판정하고, 새 계보가 기존 소진을 초기화하지 않음을 확인한다.
