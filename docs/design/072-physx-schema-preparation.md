> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 072 — native 설정 전에 PhysX articulation 스키마 선언

2026-10-30. 사용자 목표의 최신 모델 시뮬레이션·영상 보관을 위해 실제 오류의 후속 수리물을 준비한다. **추가 native 실행은 이번 단위에서 하지 않는다.** 071의 source/L4/원장과 성공 import 및 실패 simulation 기록을 보존한다.

## 근거와 한정 범위

실제 simulation run `f86568134ef94923849785af640ef5f8`은 timeline/명령 전에 `set_enabled_self_collisions(False)`에서 `Empty typeName ... Base.physxArticulation:enabledSelfCollisions`로 실패했다. SDK 원본 Articulation3599는 해당 attribute에 직접 Set하고 API를 자동 선언하지 않는다. 반면 gravity setter4355는 PhysxRigidBodyAPI를 ensure하므로 그 코드까지 임의 변경하지 않는다. 실제 imported Base에는 PhysicsArticulationRootAPI가 있지만 PhysxArticulationAPI가 없다.

소유는 **scene.py 한 파일**, 신규 `outputs/isaac-gripper-v1/072/` HOST 대조/원본/검토자료와 이 문서다. SDK/validate/driver/config/test_host 및 A6 공통서명·모델16·원 USD·다른 B4 파일을 보존한다. source 생성기/URDF/mimic/관절/물성/한계/동작프로그램은 변경하지 않는다. 실물 보정·모터/CAN·플래시·설치·재부팅·구매·학습 제외, 링 보류/가정 질량·관성 유지.

S 한정 source 준비이며 071 사용자 승인 예산의 **잔여 시간 안에서만**, 전체15:18:37UTC 상한을 늘리지 않는다. 실제관측에 근거한 API선언1파일의 좁은 수정이라 S 경량 L2는 생략하고, 기계/고정HOST 대조 이후 비작성자 L4 1회를 반드시 받는다. 071 L4 2/2를 재개하거나 기존 소진을 초기화하는 단위가 아니다. 별도 작성자와 비작성자, 같은계열 fallback/외부hook 재시도없음 한계를 기록한다.

## 수정과 대조

정확한 실제 ArticulationRootAPI 경로 한 곳을 고른 기존 inventory 검사 뒤, 그 prim에 PhysxArticulationAPI를 선언한다. self-collision attribute가 bool 타입이며 False를 설정·readback할 수 있는지 SDK wrapper 호출 전에 확인한다. timeline은 정지 상태여야 한다. 임의 다른 root 선택·추가 physical body/질량/관절 생성은 금지한다. SDK가 사용하는 같은 actual root prim에 선언해야 한다. 원 import 파일을 수정하지 않고 실행 stage의 강한 layer에만 구성한다.

원본의 미선언 typed-attribute 실패를 HOST stage 대역에서 재현한다. 수정 후 정확 root/스키마/타입/False readback·불변 geometry를 확인한다. missing/wrong root, Apply 실패, 잘못된 attribute 타입/readback, timeline running 거절을 고정 이름·개수로 대조한다. HOST 대역은 native 성공으로 승격하지 않는다. 수정 후 A6+model16+다른 B4 지문 불변을 확인한다.

## 다음 실행의 조건

071 실제 import `5681f5f717a34c92a10d78188e9ee8c7`는 **IMPORT_VERIFIED/actual0**이고, simulation은 **1/1 소비/actual1/policy1/no timeout/REAPED**, 움직임/프레임0이다. 추가 simulation은 사용자 처분과 새 한정 실행 권한이 필요하며 원장을 지우거나 실패를 미소비로 바꾸지 않는다.

다음 설계는 이 source 수리와 원 실패에 정확히 연결된 simulation 추가1회를 명시해야 한다. 이미 수용된 실제 import의 SDK·validator·model·도메인 입력이 같다는 증명을 보존한다. 순수 실행권한/전송 정책을 바꾸어야 한다면 전체 source 서명과 수입 모델의 domain 서명을 혼동하지 않으며, 이전 원본 import receipt를 그 당시의 봉인된 검증기로 재검사하고 현 도메인과 대조하는 별도 유한 경계를 검토한다. 071 공통서명이 다른 runner를 같은 서명으로 가장하거나 source를 수정한 뒤 옛 import를 조용히 재사용하지 않는다. 이 실행 정책 변경은 이번 072에서 구현하지 않는다.

native가 수용된 뒤 실제 RTX frame만 MP4로 만들고 새 Drive `2026-10-30` 폴더에 영상·출처를 저장한다. 이번의 미생성 영상을 성공 영상으로 대신하지 않는다.
