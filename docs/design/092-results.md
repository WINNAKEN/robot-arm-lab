> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 092 결과 — USD 루트 합성 결함 확인, COM 수용·큰 동작 미실행

2026-10-31. 사용자의 기저 COM 불일치 수정·큰 동작 요청을 수행했으나 완료하지 못했다. 실물 CAN/급전/flash/모터/실물 보정은 모두 NOT_RUN, hardware_approved=false다.

## 실제 실행

- 091: import `e0c7d1c1ce8d4f44be55cd7ca916deee`는 IMPORT_VERIFIED. 정지 실행 `88670c028b6a4cb8b63a6db3d0e15f0e`는 바닥 포함 scene에 import 전용 collider 검증 문맥을 사용한 작성자 결함으로 실패했다. 원결과·원장·소스는 그대로 보존했다.
- 092: `verify_import(..., floor=False)`를 명시적 문맥으로 확장하고 scene 호출만 floor=True로 연결했다. HOST 15그룹/325건, 비작성자 L2 R2·L4 R2는 각각 9 MET/0 UNMET이었다. 이 PASS는 실제 루트 수정 성공을 뜻하지 않았다.
- 새 import `93689a836af0408b92bb770f5d203442`는 IMPORT_VERIFIED/child0이다. 정지 실행 `995b18e04ed14579a9f5e2270b432ae4`는 151.031초·child1·REAPED·timeout=false로 FAILED였다. 최초 원인은 `ValueError: Actual unique new articulation root`다. floor 검증 이후 root_binding.normalize의 유일 루트 검사에서 중단했다.
- base-before.usda만 저장됐으며 base-after/report/PNG/양의 물리 step은 없다. 큰 동작 phase는 시작되지 않았다. generic consumer의 sdk_connected:false는 예외 기본 결과이며 SDK 미시작을 증명하지 않는다.

## 확정한 코드 결함과 아직 미확정인 물리 원인

설치된 `omni.usd.schema.newton`의 generatedSchema.usda 547–553행은 NewtonArticulationRootAPI에 `apiSchemas = ["PhysicsArticulationRootAPI"]`를 선언한다. 따라서 Base에서 PhysicsArticulationRootAPI만 RemoveAPI하면 Newton 제공 루트가 계속 합성된다. 091/092 코드와 기존 HOST mock은 이 제공 관계를 모델링하지 못했다.

물리 없는 실제 USD 재현에서 RemoveAPI는 True를 반환했지만 HasAPI는 여전히 True였고 루트는 `/World/Robot`과 `/World/Robot/Geometry/Base` 두 개였다. Newton 제공 API도 함께 옮기면 루트는 `/World/Robot` 하나가 된다. 이는 **이번 수정 시도 실패의 확정 원인**이다. 원래 089의 COM 위치·속도 불일치의 유일 원인이라는 뜻은 아니다. 고정 기저의 native fixed flag/완전한 M9·C9·G9/원 COM 일관성 수용은 아직 NOT_RUN이다.

근거는 `outputs/isaac-fixed-base-092/diagnostics/usd-probe-r2-stdout.txt`다. 실제 스냅샷 SHA256은 `dedd8e6836a571970ca08fef4dd43e1ab754d76865b23122c5ca2b1f85fe2e9c`이며 원파일 불변을 전후 검사했다. 최소 익명 stage와 실제 저장 USD의 익명 복사본 양쪽에서 재현했다. SimulationApp/timeline/physics는 시작하지 않았다.

## 별도 수정 후보

`outputs/isaac-fixed-base-092/candidate/root_binding.py`는 실행된 092 소스를 덮어쓰지 않은 후보다. 두 루트 API를 함께 이동하며, Newton 루트 API의 작성된 정적 속성을 새 루트에 복사한다. 실제 작성된 `newton:selfCollisionEnabled=false`도 유지한다. 원속성이 작성된 경우에 시간 샘플과 목적지 기작성 충돌을 검사한다. 원속성 미작성 경계의 결함은 아래 F1로 남았다. 질량·COM·관성·고정 joint·geometry·게인·cap·COM 허용오차는 바꾸지 않는다.

`diagnostics/candidate-r4-stdout.txt`의 USD 검사는 실제 후보 normalize 함수에서 루트 하나와 자기충돌 false, API 메타데이터를 원복한 뒤 USD 텍스트 일치를 관측했다. 입력 packet은 실제 import packet의 namespace만 scene에 맞춘 것이다. 후보 verify 검사는 synthetic after packet 범위다. 전체 실제 scene SDK observe/PhysX 초기화/동역학 검증이나 전체 HOST 325의 후보 재실행은 하지 않았다. 후보 SHA256은 `c87898e1bb96796f160558544089c6898848a40a7ee2c3c44c3809290c93091a`다.

최종 비작성자 R3는 두 결함을 실측해 수용을 차단했다. F1: 원본에서 속성이 미작성일 때 목적지에 이미 작성된 값이 있어도 후보의 충돌 검사를 건너뛴다. 현재 원스냅샷의 작성된 false 보존은 통과했으나 범용 계약은 충족하지 못한다. F2: 진단이 전체 apiSchemas 메타데이터를 원복하므로 허용되지 않은 PhysicsRigidBodyAPI 삭제도 가릴 수 있다. 따라서 raw stdout의 `authored_layer_delta_exactly_declared=true`는 **증명으로 수용하지 않는다**. 원복 후 텍스트 일치라는 관측만 유효하며 정확한 변경 집합의 완전성은 미증명이다. 원문 로그는 덮어쓰지 않는다. 후보와 진단의 추가 수리는 이번 예산에서 하지 않고 093에 두 지적을 전부 재상정한다.

진단 인자 전달 오류, 잘못된 import namespace 전제, 미등록 IsaacLinkAPI를 GetAppliedSchemas로 대조한 초기 검사 실패 로그도 보존했다. 최종 검사는 작성 apiSchemas 메타데이터를 대조한다. 이들은 SDK 재시도나 시뮬레이션 실행이 아니다.

## 정지 조건과 잔여 작업

091/092 각각 import1·smoke1·motion0 원장을 보존했다. 092의 목적별 1회·03:08 새 발사 마감·03:23 종료·연속 L2 max2/L4 max3을 늘리거나 초기화하지 않는다. 이 수리 후 추가 예산을 자동 생성하지 않는 계획에 따라 더 실행하지 않았다. 원격 최종 조회에서 양쪽 session.lock=false, 관련 python/kit 작업 0개였다.

비작성자 최종 L4 R3의 정본은 `review/L4-r3.json`이다. 실제 COM/큰 동작은 BLOCK이며 후보 범용 계약/완전 delta 검증도 BLOCK이다. 동일 계열 비작성자 폴백은 사용자 승인 범위이나 공통 계열 편향이 남는다. 이전 PASS와 실제 실패를 삭제하지 않는다. 089 COM 실패, 기존 정착 실패15, velocity-only EXHAUSTED, 물성 가정·링 보류·포그 숨김·바닥 ON·자기충돌 OFF도 보존한다. moving-root 교정/로봇 PD·포화 분해·실물 검증은 미완료다.

남은 순서는 후보의 새 실행 단위 통합·검토 → 실제 import → 2초 정지에서 fixed9/COM/원기준 수용 → 수용될 때만 52초 큰 동작이다. 다음 제안은 `093-root-provider-repair-proposal.md`이며 자동 착수하지 않는다.
