> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 134 — 완료된 v4 실제 궤적의 자기충돌 형상 감사

## 권한·목표·경계

2026-11-09 실제 사용자 지시: 「추가로 계속 작업 이어가, 승인해.」. 완료된133의 다음 단계로 남은 self-collision off/장착 겹침 UNKNOWN을 조사한다. 이는133 종료 수리의 재시도나 소진 계보 이름 변경이 아니다. 133 F6/실제05/영상/실패 이력/원class·EXH·예산은 무수정 보존한다. 이번134는 **기록된 실제 자세에 대한 로컬 형상 감사**이며 SDK·SSH·새 영상/Drive·CAD/URDF 수정·실물 CAN/RS485·포트·급전·flash·설치·네트워크/시계·Git 작업은0이다. 사용자 명시 분 예산을 받았다고 쓰지 않는다.

사용자에게 후속 우선순위의 선택 질문을 보냈으며 현재 기본은 자기충돌·간섭 검증이다. 응답은 계속 반영한다. 별도 응답 없이도 위 로컬 분석은 진행한다.

소유: `src/simulation/mp18_collision_audit_134/{audit.py,geometry.py,test_audit.py,test_geometry.py}` 4개와 이 계획1 = M, 2그룹(입력/실행·형상 판독). 산출은 `outputs/mp18-collision-audit-134/`; Root만 공유 HANDOFF·SESSION을 덧붙인다. 기존 코드/모델/입력 산출을 수정하지 않는다.

L1 Root → 비작성자 L2 → 별도 작성자 L3/HOST → 비작성자 L4 → Root 실제 감사 실행/판독/인계. `codex-operation.md` M 정책에 따라 작성자2700초, 주검토자 L2+L4 합2700초를 **내부 상한**으로 선언한다. 각각 첫 읽기/준비/테스트/수리/출판을 누적, 대기는 명시 동결만 분리, 마감예비300초. 작성자 읽기 준비는120초 이내 동결 후 L2 대기. L2/L4 각max2, 총4회/추가5회 없음. 기존 승인된 동일계열 비작성자 폴백을 사용하되 공통편향 잔여를 기록한다. 구133 시간·라운드 이전/초기화 없음.

## 고정 입력과 실효 결속

- 실제05 run `850124eb93cc4cc4945ee02c3aa1ed0d`, job `816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae`.
- F6 `author/source-freeze.json` SHA `3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f`; canonical `attempts/05/native-result.json` SHA `c4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2`.
- canonical runtime_accepted/원11161행/8·39·57·80·93 PASS/소유 SDK 실제exit0/reaped/active0/rawcomplete를 먼저 확인한다. 사용할 각 회수 파일은 canonical files_sha256과 대조, 사용할 소스·모델·URDF는 원F6의 경로/SHA/bytes와 대조한다. 존재 핀만으로 대체하지 않는다.
- `motion.ndjson`의 연속 step0..11160, 실제 시간0..93·dt1/120, `body_poses`의 이름으로 결속된 몸체11개/finite pose/단위 쿼터니언을 읽는다. 명령 targets 또는 FK를 실제 자세의 대체물로 쓰지 않는다. 허용 가능한 작은 쿼터니언 norm 오차의 정규화는 계산에서만 하고 원문과 최대 오차를 보고한다. 이름 중복/누락/부정확 clock/비유한 입력은 실패로 닫는다.

## source 검사 표현과 실제 authoring 표현의 구분

`manipulation-scene.json.jaw_component_overlay.after_reset`의 실제12 active child·old whole2 off·same owner/mass/inertia를 확인한다. 원 import-static의11 old collider 목록만을 최종 active/approximation 목록으로 쓰지 않는다. 그 뒤 적용된 `manipulation-scene.json.collision_approximation`도 반드시 읽어 원 prim path별 before/after를 결합한다. 실제 authoring은 기존 비-jaw collider prim9개 + jawA6 + jawB6 =21개/소유몸체11개다. 이것은 **authored collider prim 수**이며 backend cooked shape 수가 아니다. 각 child path→owner path/name→source component를 기록하고 count/vertices/faces/offset 등 제공된 readback과 원 component data를 대조한다.

검사 계산용 source-envelope는 비-jaw9개 각각 원URDF collision mesh의 전체 source convex hull, jaw12는 고정된 component vertices의 source convex hull로 만든다. **KG1 본체의 실제 after는 convexDecomposition**이고 `cooked_shape_validated=false`다. 따라서 KG1의 검사 전체 hull은 보수적인 source outer envelope일 뿐, 실제 authoring 근사와 동일한 singleton hull 또는 cooked shape라고 쓰지 않는다. 나머지8개의 최종 authored approximation도 원문에서 확인하고 provenance에 남긴다. 전체21 검사 envelope 수·21 authored prim 수·UNKNOWN backend cooked shape 수를 별도 필드로 유지한다.

SI scale·collision origin xyz/rpy·body-local frame을 원URDF/ledger/고정 component data에서 읽고 한 번만 적용한다. 실제body pose로 월드 변환한다. backend cooked vertices를 얻었다고 주장하지 않는다. 모델링 삼각형 원고체·검사용 convex outer envelope·실제 authored approximation을 혼동하지 않는다. 기하 분리는 source-envelope 범위에 한하며 contact/rest offset을 포함한 backend 접촉 여유도나 물리 무접촉 인증으로 승격하지 않는다.

총21 source-envelope choose2=210 중 같은 rigid owner 내부30쌍은 물리적으로 서로 다른 몸체의 충돌이 아니므로 별도 집계한다. 서로 다른 몸체의 authored-prim에 대응하는 source-envelope pair180개를 전수 등록하고, 대응 몸체쌍55개도 집계한다. 이 수를 backend cooked shape pair 전수로 쓰지 않는다. 관절 직접 인접 관계는 실제 joint body0/body1/name으로 표기만 하며, 인접/장착/기어라는 이유로 기하 판독에서 자동 누락하거나 충돌 허용으로 승인하지 않는다. Link6·jaw/pinion 같은 알려진 UNKNOWN을 따로 추적한다.

## 두 단계 판독과 주장 한계

1. **전11161행 broadphase**: source hull을 포함하는 각 body-local box의8corner를 실제 월드 pose로 변환하여 conservative world AABB를 만든다.180 interbody pair 전수의 축 간격, 후보행 수·시간구간·최소값 시점을 집계한다. 양의 축 분리는 source envelope의 분리를 증명하지만, 음의 box 간격을 침투깊이/충돌이라고 쓰지 않는다. 누락/계산 실패는 clean에 합치지 않는다.
2. **명시적으로 제한된 narrowphase**: 각 후보 collider pair에 대해 실제8/39/57/80/93 checkpoint와 가장 작은 AABB 간격 시점(중복 제거, 최대6개/pair)만 판독한다. 이외 broadphase overlap 행은 미판독 UNKNOWN으로 남긴다. 선정 행수/이유를 보고한다.
3. 정규화된 convex face halfspace의 Chebyshev-centre LP로 후보 common point/분리 방향을 구할 수 있다. LP 성공/status 자체를 판정 증거로 쓰지 않는다. **겹침 증거**는 반환점이 양쪽 source hull 모든 면 안에 보수오차보다 엄격히 들어가는지 원 halfspace로 직접 재검산한다. **분리 증거**는 후보 축(면/LP dual 등)의 정규화 후 실제 두 world vertex cloud support projection에서 양의 간격을 직접 재검산한다. Solver 오류·접함·미검증 방향·허용오차 경계는 UNKNOWN이다. LP 기본 nonnegative bounds를 쓰지 않고 xyz/r 변수를 명시 무제한으로 설정한다.
4. 보고 범주는 `CERTIFIED_SOURCE_ENVELOPE_SEPARATION`, `VERIFIED_SOURCE_ENVELOPE_OVERLAP_AT_SAMPLED_POSE`, `UNKNOWN_OR_UNCHECKED`. 허용오차(계획상1e-6m를 기준으로 수치 잔차와 연결)는 매개변수/결과에 고정한다. 표본 겹침은 원고체/물리접촉/충돌정지/안전 인증이 아니다. broadphase가 겹친 미판독 행이 있으면 전체 궤적 collision-free PASS를 내지 않는다. 시간 샘플 사이 연속 충돌 검증도 주장하지 않는다.

기술 근거: SciPy 공식 `linprog(method=highs)`는 inequality residual/marginals를 제공한다. 이는 후보 산출 API일 뿐 위 기하 인증의 대체물이 아니다. https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html . 실제 설치 버전/API도 HOST에서 확인하며 새 설치0.

## 수용·출력

HOST: 분리/회전 AABB false-positive/엄격 겹침/containment/접함·solver실패·오염된 후보 witness가 판독을 위조하지 못하는지 확인. 실제 입력 producer→11161행 처리→보고서 경로를 작은 실행 seam과 실제 baseline으로 모두 확인. 잘못된 run/hash/component owner/SI/중복·누락 body/마지막 행·clock을 거절한다. 독립 L4는 다른 기전의 analytic boxes·직접 support/point 검산·실제 경로 음성을 사용한다.

산출은 고정 입력·source SHA manifest, 재실행 명령, `audit.json`, 한국어 `audit.md`, pair registry와 선정 witness 근거다. 출력은 새134 하위에서 배타 생성하며 이전 결과를 덮어쓰거나 source/input 밖으로 쓰지 않는다. 감사 실행 완료와 collision-free 여부를 별도 필드로 둔다. 사용자에게 가장 큰/우선 해결할 후보와 남은 UNKNOWN을 설명하고, 그 근거로 다음 충돌 표현 수리/시뮬레이션 단계를 구체화한다. 이번에는 원133을 재실행하지 않는다.

비작성자 AC8: (1) 실제 원본 identity/hash와 입력 완전성 (2) 21/11/180/55 정확한 소유·쌍 집합과 KG1 포함 실제 override/provenance, source/authored/cooked 수의 분리 (3) SI/좌표/실제 자세 (4) 전행 conservative broadphase (5) narrow witness 직접 인증·한계 (6) 실제경로 양성/음성 HOST (7) 보존·권한/출력 경계 (8) source·보고서·예산·class/EXH 처분의 최종 일치. 결함 합집합과 소진은 비작성자가 판정하며 새로운 실제 인스턴스만 센다. 기존133 ledger를 이 감사의 거짓 재발 근거로 쓰지 않는다.

L2 R1 처분: supplemental-final-report a272f532…/supplemental-publication a93d7c00…의 Major 134-L2-R1-F1(COLLIDER_REPRESENTATION_PROVENANCE_ALIAS)을 수용했다. Root가 원계획을 `outputs/mp18-collision-audit-134/Root-plan-before-L2R2.md`로 무수정 보존한 뒤 위 source/authored/cooked 구분을 고쳤다. 초기R1 PASS와 최종 superseding BLOCK은 보존하며, 마지막 허용 L2 R2에서 같은 class의 폐쇄/소진을 비작성자가 판정한다. 원133 실제 수용·파일·예산·SDK 권한은 변하지 않는다.
