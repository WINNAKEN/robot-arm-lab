> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 094 제안 — PhysX 자기충돌 OFF 작성 순서 수리 후 COM·큰 동작

상태: PROPOSED_NOT_STARTED. 093의 실제 정지는 실패했고, 원 소스/원장/실패·검토 예산은 종결 보존한다. 이 제안은 새 실행 승인이나 자동 재시도가 아니다.

## 최소 변경과 반례

실측 원인: Root 이동 후 Newton 자기충돌 false는 보존됐으나 새 PhysxArticulationAPI의 enabledSelfCollisions는 미작성 기본값 true였다. before/after 검사는 실제 OFF 설정 호출보다 앞에 있다. 저장 USD·trace·typed read 근거는093 결과에 있다. native fixed9·COM에는 미도달했다.

stopped timeline에서 prepare_self_collision_api가 반환한 typed bool attr에 false를 작성하고 읽기 확인한 뒤 after snapshot/고정기저 검사를 수행한다. 이후 기존 robot.set_enabled_self_collisions(False)도 유지한다. ROOT/COM 검사를 건너뛰거나 false 데이터를 대신 채우지 않는다. 기존의 bool(None) 관측과 명시적인 false를 구분한다.

before/after proof에는 실제 PhysX 자기충돌 attr의 존재/타입/작성 여부/시간샘플/유효값을 추가한다. 목적지에 새로 작성되는 **정확한 bool=false 속성 하나**를 허용 변경으로 검증하고, 그 뒤에만 해당 선언 속성을 제거해 나머지 USD 전체 불변을 검사한다. 그 외 API·값·joint·물성·제어·허용오차는 그대로다. 새 reader도 임의의 목록 자기선언으로 범위를 줄일 수 없게 정확 이름/타입을 고정한다.

HOST와 실제 USD에서 미설정 기본 true, 명시 true, 타입 오류, 시간변화, 속성 누락, 다른 PhysX 속성 변경, RigidBody 삭제, Newton 두 목록 누락을 모두 거부해야 한다. 실제 호출 순서도 검사한다. 기존358건과 원 실패를 보존한다. 비작성자는 초기화/증명 계약과 093 native 새 지적의 class·재발/소진 상태를 독립 판정한다.

## 제안하는 실행 한도

수리·HOST·실제 USD·비작성자 검토로 먼저 실행 소스를 확정한다. **새 native 45분 예산은 검토된 첫 native 발사 직전에 시작**하는 방식으로 제안한다. 코드 검토 시간을 실행 예산과 분리하는 변경이므로 사용자 승인 전에는 적용하지 않는다. 새 L2 max2/L4 max2를 검토 전에 고정하고, 원093의 한도/실패를 초기화하지 않는다. native import/정지/motion 각1회, 각600초, 새 발사 종료15분 전까지다.

새 import → 2초 정지의 native fixed_base=true/M9/C9/G9/원 root COM·clock·정착 기준 수용 → 통과할 때만52초 큰 동작이다. 실패하면 추가 발사 없이 최초 오류·원자료를 보존한다. 실제 영상 생성/전체 decode·프로세스와 lock 종료·인계·로컬 commit까지 포함한다.

실물 CAN/급전/flash/모터/실물 보정/설치/재부팅/전원정책/구매/학습/외부 업로드는 제외하고 hardware_approved=false를 유지한다. 동일 계열 비작성자 폴백의 기존 승인은 지속하되 공통 편향을 명시한다. 원 물성 가정·미확정·실패/소진·임계도 그대로다.
