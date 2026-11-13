> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 093 제안 — Newton 제공 루트 API 이동 후 COM·큰 동작 확인

상태: PROPOSED_NOT_AUTHORIZED_AS_NEW_EXECUTION_BUDGET. 2026-10-31. 091/092의 기존 소스·예산·실패 계보는 무수정 보존한다. 현재 사용자의 원래 목표는 아직 미완료다.

## 검토 가능한 변경

실제 USD에서 확인한 제공 API 합성 결함에 답하는 후보는 `outputs/isaac-fixed-base-092/candidate/root_binding.py`다. PhysicsArticulationRootAPI와 이를 제공하는 NewtonArticulationRootAPI를 함께 Base에서 fixed joint 조상으로 옮기고, 작성된 Newton root 속성(현재 자기충돌 false)을 보존한다. 익명 stage에서 실제 후보 normalize의 유일 루트/현재 false 보존은 관측했으나, 최종 L4 R3의 두 지적 때문에 후보 범용 계약과 완전 delta 증명은 BLOCK이다. 그대로 실행 코드에 통합하지 않는다. 현재 후보의 synthetic packet 검증을 실제 SDK 수용으로 승격하지 않는다.

먼저 F1에 답해 원본의 작성 여부와 무관하게 Newton root schema의 모든 속성에 대해 목적지 기작성 충돌을 검사한다. 원본 미작성·목적지 true 반례가 거부돼야 한다. F2에는 API 메타데이터 원복 **전에** Base의 허용 두 API 제거와 Scope의 허용 세 API 추가를 정확히 검증하는 것으로 답한다. PhysicsRigidBodyAPI 추가 삭제 변형은 반드시 거부돼야 한다. 그 다음에만 선언한 속성 복사와 나머지 전체 USD 불변을 검사한다. 두 지적의 음성을 비작성자가 재현한 뒤 실제 before/after SDK 관측과 검증 계약에서도 제공 API·속성 값까지 결속한다.

## 제안하는 새 한도

사용자가 새 실행 예산을 승인하면 승인 시각부터 45분, 새 발사는 종료 15분 전까지, 각 native 최대600초, import/정지/큰 동작 각1회다. 이 계획의 제안만으로 시계를 시작하거나 예산을 만들지 않는다. 새 단위 L2 max2/L4 max2를 첫 검토 전에 고정하고, 이전 091/092 class와 최종 비작성자 판정을 재상정 입력으로 유지한다. Sonnet 표준 경로가 계속 차단되면 이미 승인된 동일 계열 비작성자 폴백과 잔여 편향을 명시한다.

## 수용·중단

HOST에는 Newton→Physics 합성 제공 관계, 제공 API 제거 누락, 기존 Base 중복 루트, provider 속성 누락/충돌/시간변화, 실제 full before/after body/joint/collider 불변을 포함한다. 원래 325건과 floating15/fixed9·COM 기준을 유지한다. 같은 물리 입력·게인·cap·52초 경로를 사용한다.

실제 import 수용 후 2초 정지에서 native fixed_base=true, M9/C9/G9 원차원, 실제 root COM/pose/velocity/clock 원기준과 기존 정착 기준을 모두 통과해야 큰 동작을 시작한다. 실패하면 원자료·원장·최초 오류를 보존하고 더 실행하지 않는다. 큰 동작 역시 원기준 수용·실제 PNG·전체 영상 decode·프로세스/lock 해제까지 보고한다. 미수용을 영상 성공이나 물리 완료로 표시하지 않는다.

실물 CAN·flash·급전·모터·보정·설치·재부팅·전원정책·구매·학습·외부 업로드는 포함하지 않으며 hardware_approved=false를 유지한다.
