> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 093 결과 — 원 지적 수리, 실제 정지 시험은 자기충돌 초기화 순서에서 실패

2026-10-31. 요청한 원 결함 두 건과 비작성자가 추가 발견한 목록 누락 결함을 수리했으나, 실제 정지 시험은 통과하지 못했다. **고정 기저 native9/COM 수용과 큰 동작은 미도달**이다. 실물 CAN/급전/flash/모터/보정은 모두 NOT_RUN, hardware_approved=false다.

## 수리와 검토 범위

- F1: 원속성 작성 여부와 무관하게 목적지의 기작성값·시간샘플을 거부한다. F2: 작성/합성 API의 정확한 허용 변경을 검사한 뒤에만 메타데이터 원복과 나머지 USD 텍스트 비교를 한다. 실제 USD에서 원 F1, RigidBody API 삭제, 임의 API 추가, 질량 변경 음성을 검출했다.
- L2 R1 PASS9/0. L4 R1은 실제 두 속성을 양쪽 목록에서 함께 빼도 통과하는 누락을 독립 재현해 BLOCK8/1이었다. 정확한 두 Newton root 속성을 관측부와 HOST consumer 모두에 고정했다. 각 속성의 양쪽 누락 음성을 추가했다.
- 최종 HOST16그룹358건, 독립 HOST115건, L4 R2 PASS9/0이다. R1 소스17·원 HOST16보고서는 원 SHA와 일치하게 source-r1/·host-r1/에 보존했다. 첫 CRLF 복원 실패도 기록했고 바이트 단위 재대조 후 보존했다. 원091/092 및 보호979경로는 그대로다.
- 실제 USD-only 양성/음성은 통과했으나 물리 실행은 아니다. standalone USD의 미등록 UI metadata 경고를 원stderr에 보존한다. 동일 계열 비작성자 폴백의 공통 편향이 남는다. L4 R2의 PASS는 아래 실제 정지 실패를 취소하지 않는다.

## 실제 실행

import `270d815e3e8b44c68d6201c6396ba1cb`는 IMPORT_VERIFIED, child0/REAPED/timeout=false, native213.281초였다. 로컬 수용은03:49:02Z였다.

정지 `7279d864efba432aa6d0d4c19d764889`는 FAILED, child1/REAPED/timeout=false, native212.313초였다. 최초 오류는 `ValueError: Self collision remains false`다. scene424 → root_binding.verify162에서 멈췄다. base-before.usda와 base-after.usda는 저장됐으나 initial-setup/report/PNG는 없고 native-steps.ndjson은0바이트다. Articulation/Tensor 바인딩과 COM 검사에 도달하지 않았다. generic consumer의 sdk_connected:false는 예외 기본 결과이며 SDK 미시작을 뜻하지 않는다.

## 확정한 새 원인과 다음 수정

저장된 실제 after USD를 읽은 `inspect-native-stdout.txt`에서 RootAPI는 `/World/Robot` 한 곳이다. Newton 자기충돌은 작성된 false다. 반면 PhysxArticulationAPI의 enabledSelfCollisions는 **미작성 기본값 true**다. 이전 Base에는 PhysX API/속성이 없었으며 기존 SDK observer는 bool(None)을 false로 표시했다. 이를 명시적인 PhysX OFF 값의 관측으로 해석하면 안 된다.

현재 scene은 root 이동 뒤 prepare_self_collision_api에서 typed attr를 얻지만 값을 설정하지 않는다. after snapshot과 고정기저 바인딩 검사를 먼저 수행하고, 그 뒤 robot.set_enabled_self_collisions(False)를 호출한다. 새 API의 기본값 true를 먼저 검사해 실패한 **작성자 초기화 순서 결함**이다. 물리 재생 전에 중단됐으므로 자기충돌 ON으로 로봇 물리를 실행한 것은 아니다.

다음 수리는 stopped timeline에서 typed PhysX OFF를 실제 작성·읽기 확인한 후 after snapshot/검사를 수행하는 것이다. 완전 delta proof에는 정확히 이 bool=false 속성 하나의 생성과 전후 타입/작성 상태를 명시적으로 검증해야 한다. 누락/true/잘못된 타입과 허용 외 속성 변경을 거부하는 음성이 필요하다. 검증을 제거하거나 허용오차를 넓히는 수리는 하지 않는다. 제안은 `094-self-collision-policy-order-proposal.md`다. 이번에 실행 코드를 추가 변경하거나 재시도하지 않았다.

## 예산·종결

승인 확인03:22:19Z, 종료04:07:19Z, 새 발사03:52:19Z를 유지했다. 정지 로컬 FAILED 수용03:53:25Z는 발사 마감 이후였다. 큰 동작은 정지 실패와 시간 조건 모두로 NOT_RUN이다. 원장 import1/정지1/motion0, native 추가0, L2 1/2 사용·L4 2/2 종결이며 별도 사후 비작성자 runtime 검토는 NOT_RUN이다. 원 리뷰·원 native 실패를 무수정 보존한다.

03:57:54Z 원격 조회에서 session.lock=false, 관련 python/kit 프로세스0개였다. 전체 목표는 미완료다. 이번 새 native 지적에 대한 비작성자 소진 판정은 없으며 작성자가 소진/미소진을 새로 선언하지 않는다. 보수 정지·재상정 입력으로 남긴다. 원래 COM 원인의 유일성, moving-root 독립 교정, 로봇 PD/포화 분해는 미확정이고 기존 정착15실패·velocity-only EXHAUSTED를 유지한다. 물성 가정·링 보류·포그 숨김·자기충돌 OFF 목표·바닥 ON, CAD/URDF/BOM/펌웨어 무변경도 유지한다.
